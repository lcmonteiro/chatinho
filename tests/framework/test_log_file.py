"""
Tests for the log file a chat that runs writes: where it is, what it holds, and what it leaves alone.

Each test points the temporary directory at its own folder and closes the log after itself, so
every test opens a file of its own.
"""

import logging
import subprocess
import sys
import tempfile
from datetime import date
from typing import List, Tuple

import pytest

from chatinho import connector
from chatinho.logs import close_log, log_file
from chatinho.session import ChatSession


@pytest.fixture
def tmp(tmp_path, monkeypatch):
    """The temporary directory, pointed at this test's folder; the log closed afterwards."""
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


def lines(tmp) -> List[str]:
    close_log()                       # flushes what the writer thread still holds
    path = tmp / ("chatinho.%s.log" % date.today().isoformat())
    return path.read_text(encoding="utf-8").splitlines() if path.exists() else []


class Collect(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records : List[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


# @ac AC-CORE-034.1
def test_a_chat_that_runs_writes_its_records_to_todays_file(tmp):
    assert log_file() == tmp / ("chatinho.%s.log" % date.today().isoformat())
    run(("chatinho.test", logging.DEBUG, "the first step"))
    found = [line for line in lines(tmp) if "the first step" in line]
    assert len(found) == 1
    line = found[0]
    assert " DEBUG " in line
    assert "[%d]" % __import__("os").getpid() in line
    assert "chatinho.test" in line
    assert line[:4] == str(date.today().year)           # the time leads the line


# @ac AC-CORE-034.2
def test_the_file_is_appended_to_and_no_record_is_written_twice(tmp):
    path = tmp / ("chatinho.%s.log" % date.today().isoformat())
    path.write_text("an earlier line\n", encoding="utf-8")
    run(("chatinho.test", logging.INFO, "first run"))
    run(("chatinho.test", logging.INFO, "second run"))
    held = lines(tmp)
    assert held[0] == "an earlier line"
    assert sum("first run" in line for line in held) == 1
    assert sum("second run" in line for line in held) == 1


# @ac AC-CORE-034.3
async def test_start_and_close_by_hand_write_no_file(tmp):
    peer    = Logging(("chatinho.test", logging.WARNING, "by hand"))
    session = ChatSession(connectors=[peer])
    await session.start()
    await peer.serve()
    await session.close()
    assert not list(tmp.glob("chatinho.*.log"))


# @ac AC-CORE-034.3
def test_importing_chatinho_writes_no_file(tmp_path):
    done = subprocess.run(
        [sys.executable, "-c",
         "import logging, chatinho\n"
         "from chatinho import ChatSession, build_chat_session\n"
         "logging.getLogger('chatinho.test').warning('imported')\n"],
        capture_output=True, text=True, env={**__import__("os").environ, "TMPDIR": str(tmp_path)})
    assert done.returncode == 0, done.stderr
    assert not list(tmp_path.glob("chatinho.*.log"))


# @ac AC-CORE-034.4
def test_only_chatinhos_records_are_written(tmp):
    run(("chatinho.test", logging.INFO, "ours"), ("elsewhere", logging.WARNING, "theirs"))
    held = lines(tmp)
    assert any("ours" in line for line in held)
    assert not any("theirs" in line for line in held)


# @ac AC-CORE-034.5
def test_the_programs_own_logging_gets_what_it_got_before(tmp):
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
    held = lines(tmp)
    assert any("only for the file" in line for line in held)
    assert any("for everyone" in line for line in held)


# @ac AC-CORE-034.6
def test_a_directory_that_cannot_be_written_costs_the_file_not_the_chat(tmp, monkeypatch, capsys):
    missing = tmp / "not" / "there"
    monkeypatch.setattr(tempfile, "tempdir", str(missing))
    peer = run(("chatinho.test", logging.INFO, "still running"))
    assert peer.served
    err = capsys.readouterr().err
    said = [line for line in err.splitlines() if str(missing) in line]
    assert len(said) == 1
    assert not missing.exists()
