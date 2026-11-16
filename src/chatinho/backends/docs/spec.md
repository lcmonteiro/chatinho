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
