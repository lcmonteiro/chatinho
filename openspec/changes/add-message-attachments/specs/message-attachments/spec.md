# Spec Delta

## Purpose

Lets a chat message carry attachments (pages, images, files) that its markdown text can link to by name, so every peer and presentation receives them as part of the message and a backend can check, keep and serve them.

## ADDED Requirements

### Requirement: Attachments on a message
A message SHALL carry a list of attachments, empty by default. Each attachment MUST have a name, a media type and content bytes, and MUST NOT be modifiable after it is created. The session MUST deliver attachments exactly as the speaker attached them, in the same order, without checking or dropping any.

#### Scenario: Message without attachments
- **WHEN** a peer says, asks or answers with plain text and no attachments
- **THEN** the posted message has an empty attachment list and is delivered exactly as before this change

#### Scenario: Attachments delivered as given
- **WHEN** a peer says `See the [chart](revenue.html)` with attachments `revenue.html` and `raw.csv`
- **THEN** every listener and the conversation context receive the message with both attachments, in that order

### Requirement: Every verb can attach
Peers SHALL be able to attach to every message they produce:
- `say(text, *, reply_to=None, attachments=())`
- `ask(to, text, *, attachments=())`
- `answer` and a command's `execute` MUST be able to return either a string, as before, or a reply value that carries text and attachments

Command invocations (`/name args`) remain plain text and carry no attachments. `ask` and `invoke` MUST keep returning the reply's text.

#### Scenario: Ask with attachments
- **WHEN** a peer asks another with `ask(2, "Review [this](draft.md)", attachments=[draft.md])`
- **THEN** peer 2 receives the question with `draft.md` attached

#### Scenario: Answer with attachments
- **WHEN** a connector's `answer` returns a reply with text `Here: [report](report.html)` and a `report.html` attachment
- **THEN** the posted answer carries `report.html`, and the asker's `ask` returns the text `Here: [report](report.html)`

#### Scenario: Command result with attachments
- **WHEN** a command's `execute` returns a reply with text `[export](data.csv)` and a `data.csv` attachment
- **THEN** the posted command result carries `data.csv`, the invocation message carries none, and `invoke` returns the text

#### Scenario: String returns unchanged
- **WHEN** an existing `answer` or `execute` returns a plain string
- **THEN** it is posted exactly as before, with no attachments
