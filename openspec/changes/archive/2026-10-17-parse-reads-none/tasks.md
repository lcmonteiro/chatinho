# Tasks

## 1. Confirm the shipped behavior matches the spec

- [x] 1.1 Confirm `MessageID.parse(None)` returns `None` and every other non-id input still raises `ValueError`, and verify `pytest -q tests/test_message_store.py tests/test_database_backend.py` passes.
