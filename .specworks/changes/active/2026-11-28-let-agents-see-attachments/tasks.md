# Tasks: let-agents-see-attachments

## 1. An agent sees the files its question came with

- [x] 1.1 Move `linked_names` and `read_link` to `src/chatinho/support/parts/attachments.py`, reading a plain path too, and import them in `frontends/mcp.py` (REQ-AGENT-014)
- [x] 1.2 [test] In `tests/agents/test_agent_attachments.py`, tests tagged `@ac AC-AGENT-014.1` to `@ac AC-AGENT-014.7` (REQ-AGENT-014)
- [x] 1.3 [code] `src/chatinho/support/kits/agent/attachments.py` (`read_attached`, `inlined`, `read_attachment_tool`); `AgentPeer` declares `HookLocate`, reads before the run, passes `attached` into the graph and the question into `configurable`; `Shape` gains whether a file was seen; tagged `@req REQ-AGENT-014`; verify `ruff check src tests examples`, `mypy src/chatinho examples`, `pytest -q`
- [ ] 1.4 `/specworks-done`: validate and close (the CLI was not reachable from the session that built this)
