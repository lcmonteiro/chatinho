# peer-lifecycle Specification

## Purpose

Defines how the session ends the life of the peers and commands it holds, so a peer that holds a resource, synchronous or asynchronous, can let it go when the chat ends.

## Requirements

### Requirement: shutdown may be a coroutine
At `close()`, after the deliveries in flight have finished or been cancelled, the session SHALL call `shutdown()` on every peer and command that has one. A `shutdown` that returns a coroutine MUST be awaited, and all such coroutines MUST be awaited together, bounded by the session's close timeout. A `shutdown` that raises MUST be logged without stopping the others; one still running at the deadline MUST be cancelled and a warning logged. `close()` MUST return in every case.

#### Scenario: An asynchronous shutdown is awaited
- **WHEN** a peer's `shutdown` is `async def` and records that it ran, and the chat is closed
- **THEN** it has run to the end by the time `close()` returns

#### Scenario: A synchronous shutdown still works
- **WHEN** a peer's `shutdown` is a plain method and the chat is closed
- **THEN** it is called once

#### Scenario: One failing shutdown does not stop the others
- **WHEN** two peers have asynchronous `shutdown`s and the first raises
- **THEN** the error is logged and the second still runs

#### Scenario: A shutdown that never returns
- **WHEN** a peer's asynchronous `shutdown` never returns and the chat is closed
- **THEN** `close()` returns within about the close timeout, and a warning is logged

### Requirement: Every peer keeps its own id
Every peer registered with a session SHALL keep a distinct id. A peer whose id the session chooses MUST get the lowest free number at or above the next one it would hand out, skipping any id a peer has already taken, whether that peer declared it (`@connector(name, id=...)`) or was registered at it. Registering a peer at an id that is already taken MUST raise `ValueError`, as it does today; no registration MAY silently replace a peer.

#### Scenario: A pinned peer, then a numbered one
- **WHEN** a session is built with a connector declaring `id=1`, then a connector declaring no id
- **THEN** the first has id 1, the second has id 2, and both are in the roster

#### Scenario: Two peers pinned to one id
- **WHEN** two connectors both declaring `id=1` are registered with one session
- **THEN** the second registration raises `ValueError`
