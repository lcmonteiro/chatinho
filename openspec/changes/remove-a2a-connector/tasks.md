# Tasks

## 1. Branch

- [ ] 1.1 Start `claude/remove-a2a-connector` from the latest `origin/main`. Verify that `git log origin/main..HEAD` is empty before the first commit.

## 2. Code

- [ ] 2.1 Delete `src/chatinho/connectors/a2a.py` and `tests/test_a2a_payload.py` with `git rm`. Verify that `git status` lists both as deleted.
- [ ] 2.2 In `src/chatinho/__init__.py`, remove `A2AConnector` from these four places:
  - the `_BEHIND_AN_EXTRA` table;
  - the `TYPE_CHECKING` import block;
  - `__all__`;
  - the docstring's extras table, whose count becomes "Nine names".

  Verify that `python -c "import chatinho; assert 'A2AConnector' not in chatinho.__all__"` succeeds, and that reading `chatinho.A2AConnector` raises `AttributeError`.
- [ ] 2.3 Remove `A2AConnector` from `_WHERE` in `src/chatinho/connectors/__init__.py`. Verify that `from chatinho.connectors import McpConnector, OpenAIConnector` still works.

## 3. Packaging

- [ ] 3.1 In `pyproject.toml`, delete the `a2a` extra and drop `requests>=2.25.0` from the `all` and `dev` extras. Verify that `grep -n requests pyproject.toml` returns nothing.
- [ ] 3.2 Regenerate `uv.lock` with `uv lock`. Verify that the lock no longer names the `a2a` extra.

## 4. Docs

- [ ] 4.1 Update `README.md`:
  - drop the `A2AConnector` row from the extras table;
  - drop `A2AConnector` from the combined example;
  - add a removal note next to the existing rename note, pointing at `McpConnector`;
  - keep the "the way A2A delegates them" line about credential delegation.
- [ ] 4.2 Update `CLAUDE.md`:
  - the opening example uses another connector;
  - the layout loses `a2a.py`;
  - the test list loses `test_a2a_payload.py`;
  - the extras table loses its A2A row;
  - the Public API section loses the name and has the corrected export count;
  - the lazy-names count is corrected.
- [ ] 4.3 Update `examples/README.md` so it no longer says the demo ships `A2AConnector`.
- [ ] 4.4 Verify the docs. `grep -rn "A2AConnector\|chatinho\[a2a\]\|test_a2a" src tests examples docs README.md CLAUDE.md pyproject.toml` must return only the README removal note. The protocol mentions in `openspec/specs/credential-delegation` and the README credential line stay.

## 5. Verification

- [ ] 5.1 Run the repository's CI steps locally:
  - `ruff check src tests examples` must be clean;
  - `mypy src/chatinho` must report no issues;
  - `pytest -q` must pass;
  - `openspec validate --all --strict --no-interactive` must pass.

  The `test_architecture.py` extras tests must pass unchanged.
