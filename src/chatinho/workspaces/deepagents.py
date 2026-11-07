"""
A workspace as a LangChain deep agents backend.

:class:`WorkspaceBackend` wraps a :class:`~chatinho.workspaces.Workspace`, or a
:class:`~chatinho.workspaces.WorkspaceView` of someone else's, so that
``create_deep_agent(backend=...)`` works in it with the file tools the agent
already has::

    backend = CompositeBackend(
        default = WorkspaceBackend(await self.workspace()),               # "/"
        routes  = {"/peers/dev/": WorkspaceBackend(await self.workspace("dev"))},
    )

It is a translation, not a second implementation: each protocol method goes
through the workspace's operation of the same purpose, so its lock, its path
rules and whatever a project's subclass does there all apply.

Three things differ from the protocol's defaults, deliberately:

- **Async only.** The chat runs a deep agent on its own loop, so only the
  ``a``-methods are implemented; the sync ones raise ``NotImplementedError``
  rather than reaching into the loop from a thread.
- **A view refuses writes with an error result**, as the protocol reports
  everything, rather than lacking the method: deep agents registers
  ``write_file`` whatever the backend.
- **No shell.** It is not a ``SandboxBackendProtocol``, so ``execute`` is deep
  agents' own "no shell" answer.

Needs ``pip install 'chatinho[deepagents]'``.
"""

import re
from typing import Any, List, Optional, Tuple

from deepagents.backends.protocol import (
    BackendProtocol,
    DeleteResult,
    EditResult,
    FileData,
    FileDownloadResponse,
    FileInfo,
    FileUploadResponse,
    GlobResult,
    GrepMatch,
    GrepResult,
    LsResult,
    ReadResult,
    WriteResult,
)

from .views import Workspace, WorkspaceView

#: The cap on matches when the caller sets none: the protocol's "every match".
_EVERY_MATCH : int = 10 ** 9


def _relative(path: Optional[str]) -> str:
    """A protocol path (absolute, ``/`` the workspace's root) as a workspace one."""
    if path is None:
        return "."
    return path.lstrip("/") or "."


def _absolute(path: str) -> str:
    """A workspace path as the protocol shows it: rooted at ``/``."""
    return "/" if path in ("", ".") else "/" + path.lstrip("/")


def _failed(exc: Exception) -> str:
    return "%s: %s" % (type(exc).__name__, exc)


def _download_error(exc: Exception) -> str:
    if isinstance(exc, FileNotFoundError):
        return "file_not_found"
    if isinstance(exc, IsADirectoryError):
        return "is_directory"
    if isinstance(exc, ValueError):
        return "invalid_path"
    return _failed(exc)


class WorkspaceBackend(BackendProtocol):
    """
    One workspace, or a view of one, as a deep agents backend.

    Args:
        workspace: A ``Workspace`` the agent may change, or a ``WorkspaceView``
            it may only read.
    """

    def __init__(self, workspace: WorkspaceView) -> None:
        self.workspace : WorkspaceView = workspace

    def __repr__(self) -> str:
        return "WorkspaceBackend(%r)" % (self.workspace,)

    # === Who may write ==============================================================

    def _writable(self) -> Optional[Workspace]:
        return self.workspace if isinstance(self.workspace, Workspace) else None

    def _read_only(self) -> str:
        return "read-only: this is %s's workspace, and only %s writes to it" % (
            self.workspace.name, self.workspace.name)

    # === Reading ====================================================================

    async def als(self, path: str) -> LsResult:
        """The entries of a directory, each with its absolute path; directories end with ``/``."""
        where = _relative(path)
        try:
            names = await self.workspace.ls(where)
        except Exception as exc:
            return LsResult(error=_failed(exc))
        base = "" if where == "." else where.rstrip("/") + "/"
        entries : List[FileInfo] = [
            {"path": _absolute(base + name), "is_dir": name.endswith("/")} for name in names]
        return LsResult(entries=entries)

    async def aread(self, file_path: str, offset: int = 0, limit: int = 2000) -> ReadResult:
        """A window of a file's lines, with the line it starts at."""
        try:
            got = await self.workspace.read(_relative(file_path), offset, limit)
        except Exception as exc:
            return ReadResult(error=_failed(exc))
        if limit <= 0:
            return ReadResult(file_data=FileData(content="", encoding="utf-8"), no_lines_requested=True)
        if not got.text:
            if max(offset, 0) > 0:
                return ReadResult(error="Line offset %d is past the end of %s" % (offset, file_path))
            return ReadResult(file_data=FileData(content="", encoding="utf-8"))
        count = len(got.text.splitlines(keepends=True))
        end   = got.start + count - 1
        text  = got.text.replace("\r\n", "\n").replace("\r", "\n")
        return ReadResult(file_data=FileData(content=text, encoding="utf-8"),
                          start_line=got.start, end_line=end, next_offset=end if got.more else None)

    async def aglob(self, pattern: str, path: Optional[str] = None) -> GlobResult:
        """The files, never directories, under *path* matching *pattern*."""
        if ".." in pattern.split("/"):
            return GlobResult(error="A glob pattern may not hold a '..' segment: %r" % pattern)
        try:
            found = await self.workspace.glob(pattern, _relative(path))
        except Exception as exc:
            return GlobResult(error=_failed(exc))
        return GlobResult(matches=[{"path": _absolute(name), "is_dir": False} for name in found])

    async def agrep(
        self,
        pattern   : str,
        path      : Optional[str] = None,
        glob      : Optional[str] = None,
        *,
        max_count : Optional[int] = None,
    ) -> GrepResult:
        """Where *pattern*, as literal text, occurs: one match per line."""
        if max_count is not None and max_count < 1:
            return GrepResult(matches=[], truncated=False)
        try:
            found = await self.workspace.grep(re.escape(pattern), _relative(path), glob,
                                              multiline=False, limit=max_count or _EVERY_MATCH)
        except Exception as exc:
            return GrepResult(error=_failed(exc))
        matches : List[GrepMatch] = [
            {"path": _absolute(m.path), "line": m.start, "text": m.text.rstrip("\r\n")}
            for m in found.matches]
        return GrepResult(matches=matches, truncated=found.truncated)

    async def adownload_files(self, paths: List[str]) -> List[FileDownloadResponse]:
        """Each file's bytes, or why it could not be read, in the order asked."""
        answered : List[FileDownloadResponse] = []
        for path in paths:
            try:
                data = await self.workspace.tree.read_bytes(_relative(path))
            except Exception as exc:
                answered.append(FileDownloadResponse(path=path, error=_download_error(exc)))
            else:
                answered.append(FileDownloadResponse(path=path, content=data))
        return answered

    # === Writing ====================================================================

    async def awrite(self, file_path: str, content: str) -> WriteResult:
        """Writes a file, creating it or replacing what it held."""
        ws = self._writable()
        if ws is None:
            return WriteResult(error=self._read_only())
        try:
            await ws.write(_relative(file_path), content)
        except Exception as exc:
            return WriteResult(error=_failed(exc))
        return WriteResult(path=_absolute(_relative(file_path)))

    async def aedit(self, file_path: str, old_string: str, new_string: str,
                    replace_all: bool = False) -> EditResult:
        """Replaces exact text, failing when it is missing or, without *replace_all*, not unique."""
        ws = self._writable()
        if ws is None:
            return EditResult(error=self._read_only())
        try:
            count = await ws.edit(_relative(file_path), old_string, new_string, replace_all)
        except Exception as exc:
            return EditResult(error=_failed(exc))
        return EditResult(path=_absolute(_relative(file_path)), occurrences=count)

    async def adelete(self, file_path: str) -> DeleteResult:
        """Removes a file, or a directory and everything under it."""
        ws = self._writable()
        if ws is None:
            return DeleteResult(error=self._read_only())
        try:
            await ws.delete(_relative(file_path))
        except Exception as exc:
            return DeleteResult(error=_failed(exc))
        return DeleteResult(path=_absolute(_relative(file_path)))

    async def aupload_files(self, files: List[Tuple[str, bytes]]) -> List[FileUploadResponse]:
        """Writes each file's bytes, under the workspace's lock, in the order given."""
        ws = self._writable()
        if ws is None:
            return [FileUploadResponse(path=path, error="permission_denied") for path, _ in files]
        answered : List[FileUploadResponse] = []
        for path, data in files:
            try:
                async with ws.tree.lock:
                    await ws.tree.write_bytes(_relative(path), data)
            except Exception as exc:
                answered.append(FileUploadResponse(path=path, error=_download_error(exc)))
            else:
                answered.append(FileUploadResponse(path=path))
        return answered

    # === The sync half: not here ====================================================

    def _sync(self, name: str) -> Any:
        raise NotImplementedError("WorkspaceBackend is async only: call a%s, not %s" % (name, name))

    def ls(self, path: str) -> LsResult:
        return self._sync("ls")

    def read(self, file_path: str, offset: int = 0, limit: int = 2000) -> ReadResult:
        return self._sync("read")

    def glob(self, pattern: str, path: Optional[str] = None) -> GlobResult:
        return self._sync("glob")

    def grep(self, pattern: str, path: Optional[str] = None, glob: Optional[str] = None, *,
             max_count: Optional[int] = None) -> GrepResult:
        return self._sync("grep")

    def write(self, file_path: str, content: str) -> WriteResult:
        return self._sync("write")

    def edit(self, file_path: str, old_string: str, new_string: str, replace_all: bool = False) -> EditResult:
        return self._sync("edit")

    def delete(self, file_path: str) -> DeleteResult:
        return self._sync("delete")

    def upload_files(self, files: List[Tuple[str, bytes]]) -> List[FileUploadResponse]:
        return self._sync("upload_files")

    def download_files(self, paths: List[str]) -> List[FileDownloadResponse]:
        return self._sync("download_files")
