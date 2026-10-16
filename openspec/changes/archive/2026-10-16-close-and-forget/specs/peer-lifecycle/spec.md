## Purpose

Defines how the session ends the life of the peers and commands it holds, so a peer that holds a resource, synchronous or asynchronous, can let it go when the chat ends.

## ADDED Requirements

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
