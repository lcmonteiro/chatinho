# hive

## Purpose

The hive is the server every chat is kept and seen in: each chat, by its name
and key, writes its conversation, attachments and traces there and reads them
back, and an admin watches every chat live, down to the trace graph of a
message.

## Requirements

### Requirement: REQ-HIVE-001 A chat is a name and a key

`chatinho-hive chat add <name>` SHALL create a chat and print its key once; the hive MUST store only a hash of the key. A name MUST be 1 to 64 characters of lower-case letters, digits, `-` and `_`. `chatinho-hive chat list` SHALL print every chat's name and when it was made, never a key, and `chatinho-hive chat remove <name>` SHALL delete a chat and everything kept for it. Every command takes `--db <url>`, the database the hive uses (a SQLite file `hive.db` by default).

#### Scenario: AC-HIVE-001.1 Adding a chat

- **WHEN** `chatinho-hive chat add team` is run
- **THEN** it prints a key, and the database holds the chat `team` with a hash that is not the key

#### Scenario: AC-HIVE-001.2 A name taken

- **GIVEN** a chat `team`
- **WHEN** `chatinho-hive chat add team` is run
- **THEN** it exits non-zero saying the name is taken, and `team`'s key still works

#### Scenario: AC-HIVE-001.3 A bad name

- **WHEN** `chatinho-hive chat add "Team One"` is run
- **THEN** it exits non-zero saying which characters a name may have

#### Scenario: AC-HIVE-001.4 Listing hides keys

- **WHEN** `chatinho-hive chat list` is run with two chats
- **THEN** it prints both names and no key or hash

#### Scenario: AC-HIVE-001.5 Removing a chat

- **GIVEN** a chat with messages and traces
- **WHEN** `chatinho-hive chat remove team` is run
- **THEN** the chat, its messages, attachments and traces are gone, and its key is refused

### Requirement: REQ-HIVE-002 Admin keys read every chat

`chatinho-hive admin add` SHALL print a new admin key once and store only its hash. An admin key MAY read every chat and its stream; it MUST NOT write to a chat.

#### Scenario: AC-HIVE-002.1 Adding an admin key

- **WHEN** `chatinho-hive admin add` is run
- **THEN** it prints a key that the hive accepts on the chat list

#### Scenario: AC-HIVE-002.2 An admin cannot write

- **WHEN** an admin key posts messages
- **THEN** the hive answers 403

### Requirement: REQ-HIVE-003 Every request carries a key

Every request under `/api` MUST carry a key in the `X-Hive-Key` header; the stream also accepts it as the `key` query parameter, since a browser cannot set headers on one. A missing or unknown key MUST be answered 401, and a key used where it may not act 403. A chat key SHALL read and write its own chat only, and never learns another chat exists.

#### Scenario: AC-HIVE-003.1 No key

- **WHEN** a request to `/api/messages` carries no key
- **THEN** the hive answers 401

#### Scenario: AC-HIVE-003.2 An unknown key

- **WHEN** a request carries a key the hive never made
- **THEN** the hive answers 401

#### Scenario: AC-HIVE-003.3 A chat key on the admin views

- **WHEN** a chat key asks for the list of chats or another chat's messages
- **THEN** the hive answers 403

#### Scenario: AC-HIVE-003.4 Writes land in the key's chat

- **GIVEN** chats `a` and `b`
- **WHEN** `a`'s key posts a message
- **THEN** `a` holds it and `b` does not

### Requirement: REQ-HIVE-004 A chat writes and reads its conversation

With its key a chat SHALL post messages in batches, load them back oldest first narrowed by `since` and `limit`, and forget those older than `before`, which also drops their attachments and traces and answers how many messages went. Posting a message the chat already holds MUST NOT duplicate it, so a resend is safe. A body that is not a valid batch MUST be answered 422 and store nothing.

#### Scenario: AC-HIVE-004.1 Post and load

- **WHEN** a chat posts three messages and loads with `limit=2`
- **THEN** it gets the last two, oldest first, with every field it posted

#### Scenario: AC-HIVE-004.2 A resend

- **WHEN** a chat posts the same message twice
- **THEN** loading returns it once

#### Scenario: AC-HIVE-004.3 Forget

- **WHEN** a chat forgets before the time of its third of five messages
- **THEN** the answer is 2, and the two messages, their attachments and traces are gone

#### Scenario: AC-HIVE-004.4 A bad batch

- **WHEN** a chat posts a message with no id
- **THEN** the hive answers 422, and nothing of the batch is stored

### Requirement: REQ-HIVE-005 A chat keeps attachments and traces

With its key a chat SHALL put an attachment under a message id and name and get it back byte for byte; an attachment the chat does not hold MUST be answered 404. It SHALL post traces in batches, a resent trace not duplicated, and each kept with its id, message id, state, `prev`, text, `frm` and time, whether or not its message has arrived yet.

#### Scenario: AC-HIVE-005.1 An attachment round trip

- **WHEN** a chat puts `notes.md` under a message and gets it back
- **THEN** the bytes are the same

#### Scenario: AC-HIVE-005.2 Not there

- **WHEN** a chat asks for an attachment it never put
- **THEN** the hive answers 404

#### Scenario: AC-HIVE-005.3 Traces kept

- **WHEN** a chat posts two traces, the second following the first, and posts them again
- **THEN** the hive holds two traces, with every field and the link between them

#### Scenario: AC-HIVE-005.4 A trace before its message

- **WHEN** a trace arrives for a message the hive does not hold yet
- **THEN** it is kept, and appears under that message once it arrives

### Requirement: REQ-HIVE-006 An admin sees every chat

With an admin key the hive SHALL list every chat with its name, how many messages it holds and when it was last written to; give any chat's messages, narrowed like `load`; and give a message's traces, each with its `prev`, oldest first. An unknown chat or message MUST be answered 404.

#### Scenario: AC-HIVE-006.1 The list of chats

- **GIVEN** chats `a` with two messages and `b` with none
- **WHEN** an admin asks for the chats
- **THEN** both are listed, `a` with 2 messages and its last write's time, `b` with 0

#### Scenario: AC-HIVE-006.2 A chat's messages

- **WHEN** an admin asks for `a`'s messages
- **THEN** it gets them oldest first

#### Scenario: AC-HIVE-006.3 A message's traces

- **GIVEN** a message with three traces, two following the first
- **WHEN** an admin asks for that message's traces
- **THEN** it gets the three, oldest first, with their `prev`

#### Scenario: AC-HIVE-006.4 An unknown chat

- **WHEN** an admin asks for the messages of a chat that does not exist
- **THEN** the hive answers 404

### Requirement: REQ-HIVE-007 A chat is watched live

`/api/chats/<name>/stream` SHALL be a server-sent event stream, for an admin key, of every message and trace the chat stores after the stream opened, each as one event saying whether it is a message or a trace, in the order they were stored. A resent message or trace already held MUST NOT be sent again.

#### Scenario: AC-HIVE-007.1 A message appears

- **GIVEN** an admin watching chat `a`
- **WHEN** `a` posts a message and then a trace
- **THEN** the stream sends a message event and then a trace event, with their fields

#### Scenario: AC-HIVE-007.2 Another chat is not shown

- **GIVEN** an admin watching chat `a`
- **WHEN** `b` posts a message
- **THEN** the stream sends nothing

#### Scenario: AC-HIVE-007.3 A chat key cannot watch

- **WHEN** a chat key opens a stream
- **THEN** the hive answers 403

### Requirement: REQ-HIVE-008 The viewer page

The hive SHALL serve a page at `/` that asks for an admin key, lists the chats, shows the chosen chat's messages and adds new ones as they arrive, and shows a message's traces as a graph, each trace linked to the one it follows, with its state and text. The page MUST work in a phone's browser and need nothing outside the hive: no build step and no file from another host. The key is kept in the browser only, and the page is served without one.

#### Scenario: AC-HIVE-008.1 The page is served

- **WHEN** `/` is fetched with no key
- **THEN** the hive answers 200 with an HTML page that loads nothing from another host

#### Scenario: AC-HIVE-008.2 The page uses the API

- **WHEN** the page is opened in a browser with an admin key, on a chat holding a message with two linked traces
- **THEN** it lists the chat, shows the message, and draws both traces with a link between them

### Requirement: REQ-HIVE-009 The hive documents its API

The hive SHALL serve its API's description as OpenAPI at `/openapi.json` and a page to read it at `/docs`, each operation with its key and answers.

#### Scenario: AC-HIVE-009.1 The description

- **WHEN** `/openapi.json` is fetched
- **THEN** it describes the messages, attachments, traces, chats and stream operations and the `X-Hive-Key` header

### Requirement: REQ-HIVE-010 Installing and running the hive

The hive SHALL be installed with `chatinho[hive]` and run with `chatinho-hive serve`, which takes `--db`, `--host` (`127.0.0.1` by default) and `--port` (8700 by default). Importing `chatinho` MUST NOT import the hive's libraries, and importing `chatinho.hive` without them MUST raise `ImportError` naming `chatinho[hive]`. The hive MUST NOT import the session or another specialization.

#### Scenario: AC-HIVE-010.1 Without the extra

- **WHEN** `chatinho.hive` is imported in a process where `fastapi` cannot be imported
- **THEN** `ImportError` is raised naming `chatinho[hive]`

#### Scenario: AC-HIVE-010.2 The core stays light

- **WHEN** `chatinho` is imported
- **THEN** no `fastapi`, `uvicorn` or `sqlalchemy` module is loaded

#### Scenario: AC-HIVE-010.3 Serving

- **WHEN** `chatinho-hive serve --port <free port> --db <a temporary file>` runs
- **THEN** `/` answers 200 on that port
