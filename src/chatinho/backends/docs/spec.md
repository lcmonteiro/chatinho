# backends

## Purpose

The archive: a peer that listens to the whole conversation and gives it back, forgets it on request, and keeps and links what messages attach, in a SQL database. It has no living spec yet; this records the behaviour it already has.

## Requirements

### Requirement: REQ-BACK-001 The archive keeps the conversation

`DatabaseBackend(database_url)` SHALL keep every message it hears, with its id, text, sender, addressee, the message it replies to, timestamp and status, and `load` SHALL give them back as messages. Hearing a message with an id it already holds MUST replace it, not add a row. Concurrent messages MUST all be kept, in the order they were said.

#### Scenario: AC-BACK-001.1 What goes in comes back out

- **WHEN** two messages are heard and the archive is loaded
- **THEN** both come back, in order

#### Scenario: AC-BACK-001.2 A message keeps its address and its thread

- **WHEN** a question and its answer are heard and loaded
- **THEN** each keeps its sender, its addressee and the message it replies to

#### Scenario: AC-BACK-001.3 The same message twice

- **WHEN** a message is heard, then heard again with the same id and new text
- **THEN** the archive holds one message, with the new text

#### Scenario: AC-BACK-001.4 Concurrent writes in memory

- **WHEN** fifty messages are heard at once by an in-memory archive
- **THEN** all fifty load back, in order

#### Scenario: AC-BACK-001.5 A failed reply stays failed

- **WHEN** a reply with status `error` is archived and the chat reopened
- **THEN** it comes back with status `error`, and a query leaving out errors leaves it out

### Requirement: REQ-BACK-002 Loading narrows by count and time

`load(since=None, limit=None)` SHALL return the archived messages oldest first: with `limit`, the newest that many; with `since`, those stamped at or after it.

#### Scenario: AC-BACK-002.1 The tail, oldest first

- **WHEN** five messages are archived and `load(limit=2)` is called
- **THEN** the two newest come back, oldest first

#### Scenario: AC-BACK-002.2 Narrowed by time

- **WHEN** `load(since=t)` is called
- **THEN** the messages from `t` on come back

### Requirement: REQ-BACK-003 Forgetting drops messages and what they carried

`forget(before=None)` SHALL drop the messages stamped before `before`, or every message with no cut, return how many it dropped, and drop the attachments of the messages it drops.

#### Scenario: AC-BACK-003.1 Only what is older

- **WHEN** five messages are archived and three are older than the cut
- **THEN** `forget` returns 3 and the two newer remain

#### Scenario: AC-BACK-003.2 Everything

- **WHEN** `forget()` is called with no cut
- **THEN** it returns how many there were and nothing remains

#### Scenario: AC-BACK-003.3 Attachments go with their message

- **WHEN** an older message and a newer one each carry an attachment, and the older is forgotten
- **THEN** only the newer one's attachment still links

#### Scenario: AC-BACK-003.4 Every attachment

- **WHEN** `forget()` is called with no cut
- **THEN** no attachment links any more

### Requirement: REQ-BACK-004 The archive's lifecycle

The archive SHALL connect at `initialize()` and dispose of its engine at `shutdown()`; using it before it is initialized MUST raise `RuntimeError` saying so. A keyword the constructor does not know MUST raise `TypeError`.

#### Scenario: AC-BACK-004.1 Used before initialize

- **WHEN** the archive is used before `initialize()`
- **THEN** it raises `RuntimeError` saying it is not initialized

#### Scenario: AC-BACK-004.2 Shutdown disposes of the engine

- **WHEN** an initialized archive is shut down
- **THEN** its engine is gone

#### Scenario: AC-BACK-004.3 An unknown keyword

- **WHEN** the archive is created with a keyword it does not take
- **THEN** it raises `TypeError`

### Requirement: REQ-BACK-005 A conversation outlives its session

As a session's backend, the archive SHALL give a reopened session the conversation an earlier one had, bounded by the session's `recall`, with each message's addressee, so a query for what a peer was asked still finds it. Messages said concurrently MUST all come back, in order, and a reopened chat MUST NOT overwrite what it archived.

#### Scenario: AC-BACK-005.1 It survives its session

- **WHEN** a message is said, the session closed, and a new one opened on the same database
- **THEN** the new session's context holds it

#### Scenario: AC-BACK-005.2 Concurrent messages

- **WHEN** fifty messages are said at once, and the chat closed and reopened
- **THEN** all fifty come back, in order

#### Scenario: AC-BACK-005.3 Bounded by recall

- **WHEN** a reopened session has `recall=2`
- **THEN** its context holds the two newest messages

#### Scenario: AC-BACK-005.4 Who it was asked of

- **WHEN** a say addressed to a peer is archived and the chat reopened
- **THEN** it is still addressed to that peer, and a query for that peer selects it

#### Scenario: AC-BACK-005.5 No id is reused

- **WHEN** a chat says a message and closes, and a new chat on the same database says another
- **THEN** both are archived, each with its own id and text

#### Scenario: AC-BACK-005.6 Forgotten in the session too

- **WHEN** a session forgets the messages before a cut
- **THEN** it returns how many, and its context holds only the newer one

### Requirement: REQ-BACK-007 The archive keeps and links attachments

`keep(msg_id, attachments)` SHALL store a message's attachments, one row per message and name, and `link(msg_id, name)` SHALL return a `file://` link to a file holding the attachment's content, written when the link is asked for, or `None` for a name never kept for that message. A name that is not a file name, or is only dots, still links to a file. Attachments outlive the session that kept them, and the files written are removed at `shutdown()`.

#### Scenario: AC-BACK-007.1 A kept attachment links to its data

- **WHEN** an attachment is kept and its link asked for
- **THEN** the link opens a file with its content

#### Scenario: AC-BACK-007.2 A name never kept

- **WHEN** a link is asked for a name, or a message, that kept no such attachment
- **THEN** it is `None`

#### Scenario: AC-BACK-007.3 Kept twice

- **WHEN** the same attachment is kept twice for one message
- **THEN** the archive holds one row

#### Scenario: AC-BACK-007.4 A name that is not a file name

- **WHEN** an attachment's name holds path separators
- **THEN** its link still opens its content

#### Scenario: AC-BACK-007.5 A name of dots

- **WHEN** an attachment is named with dots only
- **THEN** its link opens a file with its content

#### Scenario: AC-BACK-007.6 Files removed at shutdown

- **WHEN** a link was asked for and the archive is shut down
- **THEN** the file it wrote no longer exists

#### Scenario: AC-BACK-007.7 Across sessions

- **WHEN** an attachment is kept, the chat closes, and a new one opens on the same database
- **THEN** its link opens its content

### Requirement: REQ-BACK-008 An older archive still works

An archive made before the `asked_of` column was dropped SHALL still load its messages and save new ones.

#### Scenario: AC-BACK-008.1 The old asked_of column

- **WHEN** a session opens on an archive that has an `asked_of` column and says a message
- **THEN** the old message loads and both are saved

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

### Requirement: REQ-BACK-014 The archive logs what it loads, forgets and sends

`DatabaseBackend` and `HiveBackend` SHALL log, on the `chatinho` loggers at DEBUG or INFO, each `load` with how many messages it returned, each `forget` with how many messages went, and each attachment kept or linked, by message id and name. `HiveBackend` SHALL also log each batch it sends, with how many items of each kind went and how many still wait. No record MUST hold a message's text, an attachment's content or the key; its failures keep their warnings and errors.

#### Scenario: AC-BACK-014.1 The database archive

- **GIVEN** a `DatabaseBackend` holding three messages
- **WHEN** it loads them and then forgets two
- **THEN** records hold 3 for the load and 2 for the forget

#### Scenario: AC-BACK-014.2 A batch sent to the hive

- **GIVEN** a running hive and a `HiveBackend`
- **WHEN** two messages and a trace are said and sent
- **THEN** a record names the number of messages and traces sent and how many still wait

#### Scenario: AC-BACK-014.3 Nothing said, no key

- **GIVEN** a `HiveBackend` and a `DatabaseBackend`, each capturing every `chatinho` record from DEBUG up
- **WHEN** a message with a distinctive text and an attachment is kept, loaded and forgotten by each
- **THEN** no captured record holds the text, the attachment's content or the hive's key
