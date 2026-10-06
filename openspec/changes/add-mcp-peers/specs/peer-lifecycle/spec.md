# Spec Delta

## Purpose

Lets peers join and leave a session while it runs, so that peers standing for remote askers can come and go with their connections.

## ADDED Requirements

### Requirement: Adding a peer to a running session
A peer added with `add_connector` after the session has started SHALL take part once `start()` is called again: it is initialized, gets its own queue task, and receives messages addressed to it and broadcasts from then on. Calling `start()` again MUST NOT reload the archive.

#### Scenario: Peer added after start
- **WHEN** a session is running, a new peer is added with `add_connector` and `start()` is called again
- **THEN** the new peer hears the next broadcast and can be asked by id

### Requirement: Removing a peer from a running session
`ChatSession` SHALL provide `remove_connector(peer_id)`, which detaches a peer from a running or stopped session. After it returns, the peer MUST receive no further messages, its queue task MUST be stopped, its id MUST no longer appear in `peers()`, and questions it was asked that are still waiting MUST fail with an error rather than wait forever. Messages the peer already said MUST stay in the conversation context with their sender id. Removing the frontend (`LOCAL`) or an id that is not in the session MUST raise `ValueError`.

#### Scenario: Removed peer hears nothing more
- **WHEN** a peer is removed and someone then says something to everyone
- **THEN** the removed peer does not hear it, and `peers()` no longer lists it

#### Scenario: Pending question fails
- **WHEN** a peer is asked a question and removed before it answers
- **THEN** the asker's `ask` raises an error instead of waiting forever

#### Scenario: History kept
- **WHEN** a peer said a message and is then removed
- **THEN** the message is still in `context()` with that peer's id as its sender

#### Scenario: Frontend cannot be removed
- **WHEN** `remove_connector(LOCAL)` is called
- **THEN** it raises `ValueError` and the frontend stays attached
