# Spec Delta

## Purpose

Lets a chat message carry attachments (pages, images, files) that its markdown text links to by relative name, so peers and presentations receive them as part of the message and can open them in a browser.

## ADDED Requirements

### Requirement: Attachments on a message
A message SHALL carry a list of attachments, empty by default. Each attachment MUST have a name, a media type and content bytes. A name MUST be a single relative path segment: non-empty, without `/` or `\`, and neither `.` nor `..`. Names MUST be unique within one message. An attachment that breaks these rules MUST be rejected with `ValueError` before the message is posted.

#### Scenario: Message without attachments
- **WHEN** a peer says, asks or answers with plain text and no attachments
- **THEN** the posted message has an empty attachment list and is delivered exactly as before this change

#### Scenario: Invalid attachment name
- **WHEN** a peer attaches an attachment named `../secret.txt`, `a/b.html` or an empty string
- **THEN** the call raises `ValueError` and no message is posted

#### Scenario: Duplicate names
- **WHEN** a peer attaches two attachments named `chart.html` to one message
- **THEN** the call raises `ValueError` and no message is posted

### Requirement: Only linked attachments travel
A message's text SHALL be treated as markdown. An attachment MUST be kept on the posted message only when the text contains a relative inline link or image whose target is the attachment's name, optionally prefixed with `./`. Attachments the text does not link to MUST be dropped before the message is stored or delivered, so no peer, context reader or backend ever receives them. Absolute targets (with a URL scheme, starting with `/` or `//`) and fragment-only targets (starting with `#`) MUST NOT be treated as attachment links.

#### Scenario: Linked attachment kept
- **WHEN** a peer says `See the [chart](revenue.html)` with an attachment named `revenue.html`
- **THEN** every listener receives the message with that attachment

#### Scenario: Image link kept
- **WHEN** a peer says `![plot](./plot.png)` with an attachment named `plot.png`
- **THEN** the posted message keeps `plot.png`

#### Scenario: Unlinked attachment dropped
- **WHEN** a peer says `See the [chart](revenue.html)` with attachments `revenue.html` and `raw.csv`
- **THEN** the posted message carries only `revenue.html`, and no peer receives `raw.csv`

#### Scenario: Absolute links ignored
- **WHEN** a message links to `https://example.com/a.html` and to `#top`
- **THEN** neither link needs a matching attachment, and the message is posted normally

### Requirement: A link to a missing attachment is rejected
When a message's text contains a relative inline link or image whose target does not match any of the message's attachment names, the message MUST NOT be posted, and a `ValueError` naming the missing target MUST be raised to the code that produced it.

#### Scenario: Missing target on say
- **WHEN** a peer says `See the [chart](revenue.html)` without an attachment named `revenue.html`
- **THEN** `say` raises `ValueError` naming `revenue.html`, and no message is posted

#### Scenario: Missing target in an answer
- **WHEN** a peer's `answer` returns a reply whose text links to a name it did not attach
- **THEN** no reply is posted and the failure is logged the way any failing peer is, without stopping the chat

### Requirement: Every verb can attach
Peers SHALL be able to attach to every message they produce:
- `say(text, *, reply_to=None, attachments=())`
- `ask(to, text, *, attachments=())`
- `answer` and a command's `execute` MUST be able to return either a string, as before, or a reply value that carries text and attachments

The link rules above MUST apply to all of them. Command invocations (`/name args`) remain plain text and carry no attachments. `ask` MUST keep returning the answer's text.

#### Scenario: Ask with attachments
- **WHEN** a peer asks another with `ask(2, "Review [this](draft.md)", attachments=[draft.md])`
- **THEN** peer 2 receives the question with `draft.md` attached

#### Scenario: Answer with attachments
- **WHEN** a connector's `answer` returns a reply with text `Here: [report](report.html)` and a `report.html` attachment
- **THEN** the posted answer carries `report.html`, and the asker's `ask` returns the text `Here: [report](report.html)`

#### Scenario: Command result with attachments
- **WHEN** a command's `execute` returns a reply with text `[export](data.csv)` and a `data.csv` attachment
- **THEN** the posted command result carries `data.csv`, and `invoke` returns the text

#### Scenario: String returns unchanged
- **WHEN** an existing `answer` or `execute` returns a plain string
- **THEN** it is posted exactly as before, with no attachments

### Requirement: Terminal resolves attachment links
The terminal presentation SHALL accept an optional attachment base URL. When the user activates a relative link in a message that carries an attachment with that name, it MUST open `<base>/m/<message id>/<name>`. When no base URL is configured, it MUST NOT open anything and MUST tell the user that no attachment server is configured. Absolute links MUST keep opening as they do today.

#### Scenario: Base URL configured
- **WHEN** the base URL is `http://localhost:8765` and the user activates the link `revenue.html` in message `msg-42`
- **THEN** the terminal opens `http://localhost:8765/m/msg-42/revenue.html`

#### Scenario: No base URL
- **WHEN** no base URL is configured and the user activates an attachment link
- **THEN** nothing is opened and a notice says no attachment server is configured

#### Scenario: Absolute link
- **WHEN** the user activates `https://example.com` in a message
- **THEN** it opens as before, whether or not a base URL is configured
