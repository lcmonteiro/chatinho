# Spec Delta

## Purpose

Defines how the chat assigns message ids, so that every message can be told apart and referred to — by replies, archives and attachments — across every session that shares an archive, and how the terminal shows them in a short form.

## ADDED Requirements

### Requirement: Unique message ids
The session SHALL give every message it creates an id of the form `msg-` followed by 16 lowercase hexadecimal characters drawn at random. Ids MUST NOT depend on how many messages the session, or any earlier session, has created, and MUST be safe to generate from several threads at once.

#### Scenario: Id format
- **WHEN** a peer says a message
- **THEN** the returned id matches `msg-[0-9a-f]{16}`

#### Scenario: Many ids in one session
- **WHEN** 10,000 ids are generated in one session, from several threads
- **THEN** all of them are different

### Requirement: Reopened chats do not reuse ids
A chat that starts on an archive holding earlier messages SHALL create new messages with ids that differ from every archived one, so that no archived message, reply thread or attachment is overwritten.

#### Scenario: Reopen on the same archive
- **WHEN** a chat says a message and closes, and a new chat on the same database file says another message
- **THEN** the archive holds both messages, each with its own id and text

### Requirement: Terminal shows short ids
Wherever the terminal shows a message id — the message header, the quote of the message being replied to, the notice after copying a message, and the reply placeholder — it SHALL show the short id: the first 7 hexadecimal characters of an id of the form `msg-` + 16 hexadecimal characters. An id not in that form MUST be shown unchanged. The short id is for display only: every id the library returns, stores or accepts MUST remain the full id.

#### Scenario: Header shows the short id
- **WHEN** a message with id `msg-3f9a1c2e7b04d5a6` is rendered
- **THEN** its header shows `3f9a1c2`, and not the full id

#### Scenario: Reply and copy use the short id
- **WHEN** the user selects that message as the reply target and copies it
- **THEN** the placeholder reads `Reply to 3f9a1c2…` and the copy notice is titled `Copied 3f9a1c2`, while the reply sent carries the full id in `reply_to`

#### Scenario: Other ids unchanged
- **WHEN** a message with the explicit id `msg-3` is rendered
- **THEN** its header shows `msg-3`
