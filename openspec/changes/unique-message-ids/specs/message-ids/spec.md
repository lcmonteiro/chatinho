# Spec Delta

## Purpose

Defines how the chat assigns message ids, so that every message can be told apart and referred to — by replies, archives and attachments — across every session that shares an archive.

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
