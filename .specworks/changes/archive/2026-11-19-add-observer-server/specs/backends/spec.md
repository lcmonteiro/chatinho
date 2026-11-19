# Spec Delta: backends

## ADDED Requirements

### Requirement: REQ-BACK-009 A chat is kept in a hive

`HiveBackend(url, key)` SHALL be a backend that keeps the chat's conversation in a hive: it hears every message, gives the conversation back on `load(since=, limit=)` oldest first, forgets on `forget(before=)` and returns how many messages went, and records every trace it is given. Every request MUST carry the chat's key, read from a key source when the request is made and never logged. It MUST need no extra: importing it loads nothing beyond the standard library, and no network call blocks the loop.

#### Scenario: AC-BACK-009.1 The conversation goes to the hive and comes back

- **GIVEN** a running hive with a chat `team`, and a session whose backend is `HiveBackend` with `team`'s key
- **WHEN** two messages are said, the session is closed, and a new session with the same backend starts
- **THEN** the new session's `context()` holds both messages, with their ids, authors, `to`, `reply_to` and status

#### Scenario: AC-BACK-009.2 Loading narrows

- **GIVEN** a hive holding five messages of the chat
- **WHEN** `load(limit=2)` and `load(since=<the third's time>)` are called
- **THEN** the first returns the last two and the second the last three, oldest first

#### Scenario: AC-BACK-009.3 Forgetting

- **WHEN** `forget(before=<the third message's time>)` is called on a chat of five messages
- **THEN** it returns 2, and a later `load()` returns the last three

#### Scenario: AC-BACK-009.4 Traces are recorded

- **WHEN** a peer traces two steps of a message in a session backed by the hive
- **THEN** the hive holds both traces for that message, with their state, text and `prev`

#### Scenario: AC-BACK-009.5 The key is read late

- **GIVEN** a backend given its key as a key source whose value changes between two messages
- **WHEN** both messages are sent
- **THEN** each request carries the value the source had when it was sent

#### Scenario: AC-BACK-009.6 No extra needed

- **WHEN** `HiveBackend` is imported in a process where `fastapi`, `uvicorn`, `sqlalchemy` and `httpx` cannot be imported
- **THEN** the import succeeds

### Requirement: REQ-BACK-010 A hive keeps and links attachments

`HiveBackend` SHALL send what a message attaches to the hive, and `link(msg_id, name)` SHALL fetch it from the hive into a local file and return that file's path, or None when the hive has nothing by that name for that message. The local files MUST be removed at `shutdown`.

#### Scenario: AC-BACK-010.1 An attachment comes back

- **GIVEN** a message said with an attachment `notes.md`
- **WHEN** `link(msg_id, "notes.md")` is called
- **THEN** it returns a path to a file with the attachment's bytes

#### Scenario: AC-BACK-010.2 Nothing by that name

- **WHEN** `link(msg_id, "missing.md")` is called
- **THEN** it returns None

#### Scenario: AC-BACK-010.3 Files go at shutdown

- **GIVEN** a linked attachment
- **WHEN** the backend shuts down
- **THEN** the local file no longer exists

### Requirement: REQ-BACK-011 A hive that is down never holds up the chat

What `HiveBackend` sends (messages, attachments and traces) SHALL be queued in memory and sent in the order it was given, so `listen`, `keep` and `record` return without waiting on the network. When the hive cannot be reached, it MUST keep the queue, retry with a growing delay of at most 30 seconds, and send what waited, in order, once the hive answers. The queue MUST hold at most `queue_limit` items (10000 by default): past it the oldest is dropped and a warning says how many were dropped. At `shutdown` it SHALL try to send what is left for at most `flush_timeout` seconds (3 by default), then warn how many items were lost, or, with a cache (REQ-BACK-013), how many are kept for the next run. When the hive cannot be reached at `load`, it MUST warn and return no messages, or, with a cache, what the cache holds. `forget` and `link` that cannot reach the hive MUST raise `HiveUnavailable` and return None respectively, the latter with a warning.

#### Scenario: AC-BACK-011.1 Saying does not wait

- **GIVEN** a hive that takes two seconds to answer
- **WHEN** a peer says a message
- **THEN** `listen` returns in well under a second

#### Scenario: AC-BACK-011.2 Sent in order when the hive is back

- **GIVEN** a hive that is down
- **WHEN** three messages and a trace are said and traced, and the hive comes up
- **THEN** the hive receives all four, in the order they were given

#### Scenario: AC-BACK-011.3 The queue is full

- **GIVEN** a backend with `queue_limit=2` and a hive that is down
- **WHEN** three messages are said
- **THEN** the oldest is dropped, a warning says one item was dropped, and the hive later receives the last two

#### Scenario: AC-BACK-011.4 Lost at shutdown

- **GIVEN** a backend with no cache, a hive that is down and two queued messages
- **WHEN** the backend shuts down
- **THEN** it returns within `flush_timeout` plus a second, and a warning says two items were lost (with no cache)

#### Scenario: AC-BACK-011.5 Starting without the hive

- **GIVEN** a backend with no cache, and a hive that cannot be reached
- **WHEN** a session backed by it starts
- **THEN** with no cache it starts with an empty conversation, and a warning names the hive's URL

#### Scenario: AC-BACK-011.6 Forgetting without the hive

- **WHEN** `forget` is called while the hive cannot be reached
- **THEN** it raises `HiveUnavailable`

#### Scenario: AC-BACK-011.7 A bad URL or limit

- **WHEN** `HiveBackend` is given a URL that is not `http` or `https`, or a `queue_limit` below 1
- **THEN** it raises `ValueError`

### Requirement: REQ-BACK-012 A refused key is not retried

When the hive refuses the key (unauthorised or forbidden), `HiveBackend` MUST NOT retry: it SHALL log one error naming the hive's URL and not the key, drop what it was sending, and count it as lost. `load` with a refused key MUST log the same error and return no messages.

#### Scenario: AC-BACK-012.1 A wrong key while sending

- **GIVEN** a backend with a key the hive does not know
- **WHEN** a message is said
- **THEN** one error is logged naming the URL, the key does not appear in any log, and the message is not retried

#### Scenario: AC-BACK-012.2 A wrong key at start

- **WHEN** a session backed by a hive that refuses its key starts
- **THEN** it starts with an empty conversation, and an error is logged

### Requirement: REQ-BACK-013 A local cache keeps the chat offline

`HiveBackend(url, key, cache=<path>)` SHALL keep a local SQLite file, made when missing and needing only the standard library, that holds the chat's messages, the attachments it sent or linked, and the outbox of what is waiting to reach the hive. What `listen`, `keep` and `record` are given MUST be in the outbox before they return, without waiting on the network, and leave it only once the hive accepted it; an outbox left by an earlier run is sent first, in order. Every message heard or loaded from the hive SHALL be written to the cache. `load` SHALL answer from the hive when it can, and from the cache, narrowed the same way and with a warning, when the hive cannot be reached or refuses the key. `forget` SHALL forget in the cache too, and `link` SHALL answer from the cache when the hive cannot. The outbox is bounded by `queue_limit` as the in-memory queue is. A cache made for another hive URL MUST be refused with `ValueError` when the backend starts.

#### Scenario: AC-BACK-013.1 History offline

- **GIVEN** a session that said three messages through a backend with a cache, and was closed
- **WHEN** a new session with the same backend starts while the hive cannot be reached
- **THEN** its `context()` holds the three messages, and a warning says they came from the cache

#### Scenario: AC-BACK-013.2 Nothing lost across a restart

- **GIVEN** a backend with a cache, and a hive that is down
- **WHEN** two messages and a trace are said and traced, the session is closed, and a new session with the same cache starts once the hive is up
- **THEN** the hive receives all three, in the order they were given, and the shutdown warned that three items were kept for the next run

#### Scenario: AC-BACK-013.3 The cache follows the hive

- **GIVEN** a hive holding messages the cache has never seen
- **WHEN** a session with a cache starts while the hive is up
- **THEN** it loads them from the hive, and a later start with the hive down returns them from the cache

#### Scenario: AC-BACK-013.4 Forget reaches the cache

- **WHEN** `forget(before=<the third message's time>)` is called on a chat of five messages with a cache
- **THEN** a later start with the hive down returns the last three

#### Scenario: AC-BACK-013.5 An attachment offline

- **GIVEN** a message said with an attachment through a backend with a cache
- **WHEN** `link` is called while the hive cannot be reached
- **THEN** it returns a path to a file with the attachment's bytes

#### Scenario: AC-BACK-013.6 A cache for another hive

- **GIVEN** a cache file made by a backend for `http://a:8700`
- **WHEN** a backend for `http://b:8700` starts with that file
- **THEN** it raises `ValueError` naming both URLs
