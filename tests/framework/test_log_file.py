"""
Tests for the log file a chat that runs writes when ``CHATINHO_LOG_PATH`` asks it to.

Each test points the variable at a folder of its own, or removes it, and closes the log after itself,
so every test opens a file of its own.
"""

import logging
import os
import subprocess
import sys
import tempfile
from datetime import date
from typing import List, Tuple

import pytest

from chatinho import connector
from chatinho.logs import LOG_PATH_VARIABLE, close_log, log_file
from chatinho.session import ChatSession

TODAY = "chatinho.%s.log" % date.today().isoformat()


@pytest.fixture
def logs(tmp_path, monkeypatch):
    """``CHATINHO_LOG_PATH`` set to a folder of this test's; the log closed afterwards."""
    folder = tmp_path / "logs"
    folder.mkdir()
    monkeypatch.setenv(LOG_PATH_VARIABLE, str(folder))
    yield folder
    close_log()


@pytest.fixture
def unset(tmp_path, monkeypatch):
    """No ``CHATINHO_LOG_PATH``, and the temporary directory pointed at this test's folder."""
    monkeypatch.delenv(LOG_PATH_VARIABLE, raising=False)
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    yield tmp_path
    close_log()


@connector("logging")
class Logging:
    """A peer that logs what it is given while it serves, then returns, which ends the chat."""

    def __init__(self, *records: Tuple[str, int, str]) -> None:
        self.records = records
        self.served  = False

    async def serve(self) -> None:
        for name, level, text in self.records:
            logging.getLogger(name).log(level, text)
        self.served = True


def run(*records: Tuple[str, int, str]) -> Logging:
    peer = Logging(*records)
    ChatSession(connectors=[peer]).run()
    return peer


def lines(folder) -> List[str]:
    close_log()                       # flushes what the writer thread still holds
    path = folder / TODAY
    return path.read_text(encoding="utf-8").splitlines() if path.exists() else []


def every_log(root) -> List[str]:
    return sorted(str(p) for p in root.rglob("chatinho.*.log"))


class Collect(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records : List[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


# @ac AC-CORE-034.1
def test_a_chat_that_runs_writes_its_records_to_todays_file(logs):
    assert LOG_PATH_VARIABLE == "CHATINHO_LOG_PATH"
    assert log_file(logs) == logs / TODAY
    run(("chatinho.test", logging.DEBUG, "the first step"))
    found = [line for line in lines(logs) if "the first step" in line]
    assert len(found) == 1
    line = found[0]
    assert " DEBUG " in line
    assert "[%d]" % os.getpid() in line
    assert "chatinho.test" in line
    assert line[:4] == str(date.today().year)           # the time leads the line


# @ac AC-CORE-034.2
def test_the_file_is_appended_to_and_no_record_is_written_twice(logs):
    (logs / TODAY).write_text("an earlier line\n", encoding="utf-8")
    run(("chatinho.test", logging.INFO, "first run"))
    run(("chatinho.test", logging.INFO, "second run"))
    held = lines(logs)
    assert held[0] == "an earlier line"
    assert sum("first run" in line for line in held) == 1
    assert sum("second run" in line for line in held) == 1


# @ac AC-CORE-034.3
async def test_start_and_close_by_hand_write_no_file(logs):
    peer    = Logging(("chatinho.test", logging.WARNING, "by hand"))
    session = ChatSession(connectors=[peer])
    await session.start()
    await peer.serve()
    await session.close()
    assert not every_log(logs)


# @ac AC-CORE-034.3
def test_importing_chatinho_writes_no_file(tmp_path):
    done = subprocess.run(
        [sys.executable, "-c",
         "import logging, chatinho\n"
         "from chatinho import ChatSession, build_chat_session\n"
         "logging.getLogger('chatinho.test').warning('imported')\n"],
        capture_output=True, text=True, env={**os.environ, LOG_PATH_VARIABLE: str(tmp_path)})
    assert done.returncode == 0, done.stderr
    assert not every_log(tmp_path)


# @ac AC-CORE-034.4
def test_only_chatinhos_records_are_written(logs):
    run(("chatinho.test", logging.INFO, "ours"), ("elsewhere", logging.WARNING, "theirs"))
    held = lines(logs)
    assert any("ours" in line for line in held)
    assert not any("theirs" in line for line in held)


# @ac AC-CORE-034.5
def test_the_programs_own_logging_gets_what_it_got_before(logs):
    root     = logging.getLogger()
    program  = Collect()
    level    = root.level
    root.addHandler(program)
    root.setLevel(logging.INFO)                        # what basicConfig(level=INFO) does
    try:
        run(("chatinho.test", logging.DEBUG, "only for the file"),
            ("chatinho.test", logging.WARNING, "for everyone"))
    finally:
        root.removeHandler(program)
        root.setLevel(level)
    got = [r.getMessage() for r in program.records if r.name.startswith("chatinho")]
    assert "for everyone" in got
    assert "only for the file" not in got
    held = lines(logs)
    assert any("only for the file" in line for line in held)
    assert any("for everyone" in line for line in held)


# @ac AC-CORE-034.6
def test_a_path_that_cannot_be_a_directory_costs_the_file_not_the_chat(tmp_path, monkeypatch, capsys):
    blocked = tmp_path / "a-file"
    blocked.write_text("not a directory")
    monkeypatch.setenv(LOG_PATH_VARIABLE, str(blocked))
    try:
        peer = run(("chatinho.test", logging.INFO, "still running"))
    finally:
        close_log()
    assert peer.served
    said = [line for line in capsys.readouterr().err.splitlines() if str(blocked / TODAY) in line]
    assert len(said) == 1
    assert blocked.read_text() == "not a directory"


# @ac AC-CORE-034.7
def test_with_the_variable_unset_logging_is_off(unset):
    chatinho = logging.getLogger("chatinho")
    before   = (chatinho.level, list(chatinho.handlers), chatinho.propagate)
    peer = run(("chatinho.test", logging.WARNING, "nowhere to go"))
    assert peer.served
    assert (chatinho.level, list(chatinho.handlers), chatinho.propagate) == before
    assert not every_log(unset)


# @ac AC-CORE-034.8
def test_an_empty_variable_is_unset(unset, monkeypatch):
    monkeypatch.setenv(LOG_PATH_VARIABLE, "")
    chatinho = logging.getLogger("chatinho")
    before   = (chatinho.level, list(chatinho.handlers), chatinho.propagate)
    run(("chatinho.test", logging.WARNING, "nowhere to go"))
    assert (chatinho.level, list(chatinho.handlers), chatinho.propagate) == before
    assert not every_log(unset)


# @ac AC-CORE-034.9
@pytest.mark.skipif(sys.platform == "win32", reason="POSIX modes")
def test_a_missing_directory_is_made_for_its_owner(tmp_path, monkeypatch):
    folder = tmp_path / "state" / "chatinho"
    monkeypatch.setenv(LOG_PATH_VARIABLE, str(folder))
    try:
        run(("chatinho.test", logging.INFO, "made"))
    finally:
        close_log()
    assert folder.is_dir()
    assert folder.stat().st_mode & 0o777 == 0o700
    path = folder / TODAY
    assert path.stat().st_mode & 0o777 == 0o600
    assert any("made" in line for line in path.read_text().splitlines())


# @ac AC-CORE-034.10
@pytest.mark.skipif(sys.platform == "win32", reason="POSIX modes")
def test_an_existing_log_file_keeps_its_mode(logs):
    path = logs / TODAY
    path.write_text("")
    path.chmod(0o640)
    run(("chatinho.test", logging.INFO, "shared"))
    assert path.stat().st_mode & 0o777 == 0o640
    assert any("shared" in line for line in lines(logs))


# @ac AC-CORE-034.6
def test_a_run_after_a_failed_one_opens_the_file_once_it_can(tmp_path, monkeypatch, capsys):
    """Nothing latches a failure: fix the directory, and the next run() in the process logs (R6)."""
    blocked = tmp_path / "logs"
    blocked.write_text("not a directory yet")
    monkeypatch.setenv(LOG_PATH_VARIABLE, str(blocked))
    try:
        run(("chatinho.test", logging.INFO, "first"))
        assert len([line for line in capsys.readouterr().err.splitlines() if str(blocked) in line]) == 1
        blocked.unlink()
        run(("chatinho.test", logging.INFO, "second"))
    finally:
        close_log()
    held = (blocked / TODAY).read_text(encoding="utf-8").splitlines()
    assert any("second" in line for line in held)


# A link at the log's predictable name in a shared directory must not get the log appended to its
# target (R7): the file is opened once, never through a link, where the system can tell.
@pytest.mark.skipif(not hasattr(os, "O_NOFOLLOW"), reason="no O_NOFOLLOW on this system")
def test_a_symbolic_link_at_the_log_path_is_refused(logs, capsys):
    target = logs.parent / "someone-elses-file"
    target.write_text("untouched\n")
    (logs / TODAY).symlink_to(target)
    peer = run(("chatinho.test", logging.WARNING, "must not land there"))
    assert peer.served
    assert target.read_text() == "untouched\n"
    assert len([line for line in capsys.readouterr().err.splitlines() if str(logs / TODAY) in line]) == 1
