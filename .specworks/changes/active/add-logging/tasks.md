# Tasks: add-logging

The first round's tasks (the log file in the temporary directory, the session's and the
specializations' records, the docs) were all done and closed; this list is the reopened round:
logging turned on by `CHATINHO_LOG_PATH`.

## 1. The variable turns the log on

- [x] 1.1 Add `LOG_PATH_VARIABLE` and change `log_file` to `log_file(directory, day=None)` in `src/chatinho/logs.py`, with `open_log()` reading the variable as a stub for the new path (REQ-CORE-034); verify `uv run mypy src/chatinho examples`
- [x] 1.2 [test] Rewrite `tests/framework/test_log_file.py` for AC-CORE-034.1 to AC-CORE-034.10: the file tests set `CHATINHO_LOG_PATH` with `monkeypatch.setenv` (or delete it) instead of `tempfile.tempdir`, tagged `@ac`; verify the new criteria fail on the stub, not on imports
- [x] 1.3 [code] Implement `open_log()`: unset or empty returns None and touches nothing; set, make the directory 0700 with its parents, create the file 0600 when new, then open it as before (REQ-CORE-034) tagged `@req REQ-CORE-034`; verify `uv run ruff check src` and `uv run mypy src/chatinho`, and that a chat run with `ChatSession.run()` writes no file without the variable and `<dir>/chatinho.<today>.log` with `CHATINHO_LOG_PATH=<dir>`

## 2. Docs

- [x] 2.1 [code] Say in `CLAUDE.md`, `docs/architecture.md` and the examples' README that logging is off unless `CHATINHO_LOG_PATH` names a directory (REQ-CORE-034); verify `uv run ruff check src tests examples` and `uv run mypy src/chatinho examples`
