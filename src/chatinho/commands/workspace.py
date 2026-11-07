"""The ``/ws`` command: lists the workspaces, shows one's diff, merges or drops it."""

from typing import Any

from ..hooks import HookExecute, require, tool
from ..message import LOCAL, Attachment, Reply

USAGE = "Usage: /ws | /ws diff <name> | /ws merge <name> | /ws drop <name>"


@tool("ws", "Lists the workspaces; diff, merge or drop one")
@require(HookExecute)
class WorkspaceCommand:
    """
    What the user does with the workspaces a provider keeps.

    Listing and diffing are for anyone. Merging and dropping change what the
    user owns — the base branch, and work that is not merged — so they are
    refused unless the user ran the command: a model that has ``run_ws`` as a
    tool can look, and not merge. That refusal is policy in this command, not
    structure; it is written down so it is not taken for an oversight.

    Args:
        provider: The provider the session was given, such as
            :class:`~chatinho.workspaces.GitWorktrees`.
    """

    def __init__(self, provider: Any) -> None:
        self.provider = provider

    async def execute(self, args: str = "", by: int = LOCAL, **kwargs: Any) -> Reply:
        """
        Runs one subcommand.

        Args:
            args: Empty to list; ``diff``, ``merge`` or ``drop`` and a name otherwise.
            by: The id of who ran it.
            **kwargs: Ignored.

        Returns:
            Reply: The listing, the diff as an attachment, or what was done.

        Raises:
            ValueError: An unknown subcommand, or one missing its name.
            KeyError: No workspace by that name.
            PermissionError: ``merge`` or ``drop`` run by anyone but the user.
            MergeConflict: The merge conflicted and was aborted.
        """
        del kwargs
        words = args.split()
        if not words:
            return await self._listing()
        action, rest = words[0], words[1:]
        if action not in ("diff", "merge", "drop") or len(rest) != 1:
            raise ValueError("Unknown /ws %s. %s" % (args.strip(), USAGE))
        name = rest[0]
        if action != "diff" and by != LOCAL:
            raise PermissionError("Only the user can %s a workspace" % action)
        if name not in await self.provider.names():
            raise KeyError("No workspace named %r" % name)
        if action == "diff":
            view = await self.provider.provision(None, name, create=False)
            diff = await view.diff()
            if not diff:
                return Reply("%s's workspace has no changes." % name)
            attached = "%s.diff" % name
            return Reply("%s's work: [%s](%s)" % (name, attached, attached),
                         (Attachment(attached, "text/x-diff", diff.encode("utf-8")),))
        if action == "merge":
            await self.provider.merge(name)
            return Reply("Merged %s's workspace into %s." % (name, self.provider.base))
        await self.provider.drop(name)
        return Reply("Dropped %s's workspace." % name)

    async def _listing(self) -> Reply:
        names = await self.provider.names()
        if not names:
            return Reply("No workspaces yet.")
        lines = []
        for name in names:
            ahead = await self.provider.ahead(name)
            lines.append("%s  peer/%s  %d commit%s ahead of %s"
                         % (name, name, ahead, "" if ahead == 1 else "s", self.provider.base))
        return Reply("Workspaces:\n  " + "\n  ".join(lines))
