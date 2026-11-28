# Spec Delta: agents

## ADDED Requirements

### Requirement: REQ-AGENT-014 An agent sees the files its question came with

`AgentPeer` SHALL declare `HookLocate` and, before each run, read back every file
the question's text links by a relative name, through `locate` and the link the
backend answers, whether a `file://` link or a local path. A file that is UTF-8
text MUST be in the question the model is sent, in an `<attachment>` element
naming it and its type, whole or up to 20,000 characters and then cut with a note
naming `read_attachment` and the line to read on from. A file that is not text
MUST be named with its type and size and its content MUST NOT be sent. A link the
backend has nothing for, or that is absolute, MUST leave the question as it was.
From the first question that came with a file it could read, the agent SHALL have
a `read_attachment(name, start, count)` tool that returns that line window of a
file the question, or a message its memory remembers, links; before that it MUST
NOT have one.

#### Scenario: AC-AGENT-014.1 A text file is in the question

- **GIVEN** an agent in a chat with `DatabaseBackend`
- **WHEN** it is asked `How many rows has [the data](data.csv)?` with `data.csv` attached
- **THEN** the model is sent the question followed by `data.csv`'s content in an `<attachment>` element

#### Scenario: AC-AGENT-014.2 A plain path is read too

- **GIVEN** a backend that links an attachment as a plain local path
- **WHEN** the agent is asked with a linked text file attached
- **THEN** its content is in the question the model is sent

#### Scenario: AC-AGENT-014.3 A file that is not text is named

- **WHEN** the agent is asked with a PNG linked and attached
- **THEN** the question names it with `image/png` and its size, and holds none of its bytes

#### Scenario: AC-AGENT-014.4 No file, no tool

- **WHEN** the agent is asked a question linking a name nothing was kept under, and an absolute URL
- **THEN** the model is sent the question's text alone and is given no `read_attachment`

#### Scenario: AC-AGENT-014.5 A long file is cut and read on

- **WHEN** the agent is asked with a 1,000-line text file attached
- **THEN** the question holds under 20,000 characters of it and a note naming the line to read on from, and `read_attachment` from that line returns the next lines

#### Scenario: AC-AGENT-014.6 A remembered file can be read again

- **GIVEN** an agent asked earlier with `plan.md` attached
- **WHEN** it is asked a question with no file and calls `read_attachment("plan.md", start=2)`
- **THEN** it reads the file's second line; a name no message links answers that there is no such file

#### Scenario: AC-AGENT-014.7 Links read back

- **WHEN** `read_link` is given a `file://` link, a plain absolute path, an `https` URL, a relative name, a missing file or nothing
- **THEN** it returns the bytes for the first two and None for the rest, and `linked_names` returns the relative targets once each
