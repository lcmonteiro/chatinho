# Proposal

## Why

`A2AConnector` sends a payload that does not match the A2A protocol:
- there is no JSON-RPC envelope and no `messageId`;
- parts are marked `type` where the protocol uses `kind`;
- a Task response is read as raw JSON.

It also blocks the whole event loop with a synchronous `requests` call, up to a 30 s timeout, so a slow agent freezes every peer. Nothing in the library depends on it, and `McpConnector` already covers one session asking another. Keeping a connector that does not speak its protocol costs more than it gives.

## What Changes

- **BREAKING** `A2AConnector` is removed. `from chatinho import A2AConnector` raises `AttributeError`, and `chatinho.connectors.a2a` no longer exists. There is no alias and no deprecation period, since the package is still 0.1.x.
- **BREAKING** The `a2a` extra is removed, and `requests` leaves the `all` and `dev` extras. No other module uses it.
- `tests/test_a2a_payload.py` is removed with the connector.
- The README, `CLAUDE.md` and `examples/README.md` stop presenting the connector. The README gains a short removal note pointing at `McpConnector`.
- The mentions of A2A as the protocol that inspired credential delegation stay. They describe where an idea came from, not a component.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

None. No spec describes `A2AConnector`, so no requirement changes, and the change sets `skip_specs: true`.

## Impact

- **Code:**
  - `src/chatinho/connectors/a2a.py` is deleted;
  - in `src/chatinho/__init__.py`: the lazy table, the docstring's extras table, `__all__` and the `TYPE_CHECKING` block;
  - `src/chatinho/connectors/__init__.py`, in `_WHERE`.
- **Tests:** `tests/test_a2a_payload.py` is deleted. `tests/test_architecture.py` counts lazy names from the table and needs no edit.
- **Packaging:** `pyproject.toml` (the `a2a`, `all` and `dev` extras), and `uv.lock`, regenerated.
- **Docs:** `README.md`, `CLAUDE.md` and `examples/README.md`.
- **Users:** anyone constructing `A2AConnector` or installing `chatinho[a2a]` must drop it, and can use `McpConnector` to reach a remote chatinho session.
