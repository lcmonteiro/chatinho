# message-attachments Specification

## Purpose

Lets a peer attach pages, images and files to what it says. The backend keeps them and links them on request, any peer can locate them, and the terminal opens them, while messages themselves carry text only.

## Requirements

### Requirement: Attachments go to the backend
Messages SHALL carry text only: no listener, conversation context or archived message MUST contain attachment content. When a peer produces a message with attachments, the session MUST give them to the backend that keeps attachments, keyed by the new message's id, before the message is delivered to anyone. Each attachment MUST have a name, a media type and content bytes, and MUST NOT be modifiable after it is created. When no backend keeps attachments, they MUST be dropped and the text posted as usual. When keeping fails, the failure MUST be logged and the text MUST still be posted.

#### Scenario: Attachments kept before delivery
- **WHEN** a peer says `See the [chart](revenue.html)` with a `revenue.html` attachment and a backend keeps attachments
- **THEN** the backend has kept `revenue.html` for the new message's id by the time any listener receives the message

#### Scenario: Listeners receive text only
- **WHEN** a peer says a message with attachments
- **THEN** every listener and the conversation context receive the message's text, and no attachment content

#### Scenario: No backend
- **WHEN** a peer says a message with attachments and no backend keeps attachments
- **THEN** the text is posted as usual and the attachments are dropped

#### Scenario: Keeping fails
- **WHEN** the backend raises while keeping a message's attachments
- **THEN** the failure is logged and the message's text is still posted

### Requirement: Every verb can attach
Peers SHALL be able to attach to every message they produce:
- `say(text, *, reply_to=None, attachments=())`
- `ask(to, text, *, attachments=())`
- `answer` MUST be able to return either a string, as before, or a reply value that carries text and attachments
- a command's `execute` MUST return a reply value (or nothing). A plain string MUST be refused with `TypeError`, and no result is posted

In every case the attachments go to the backend, not onto the message. Command invocations (`/name args`) remain plain text and carry no attachments. `ask` and `invoke` MUST keep returning the reply's text.

#### Scenario: Ask with attachments
- **WHEN** a peer asks another with `ask(2, "Review [this](draft.md)", attachments=[draft.md])`
- **THEN** peer 2 receives the question's text, and the backend keeps `draft.md` for the question's id

#### Scenario: Answer with attachments
- **WHEN** a connector's `answer` returns a reply with text `Here: [report](report.html)` and a `report.html` attachment
- **THEN** the backend keeps `report.html` for the answer's id, and the asker's `ask` returns the text `Here: [report](report.html)`

#### Scenario: Command result with attachments
- **WHEN** a command's `execute` returns a reply with text `[export](data.csv)` and a `data.csv` attachment
- **THEN** the backend keeps `data.csv` for the result's id, nothing is kept for the invocation, and `invoke` returns the text

#### Scenario: String answers unchanged
- **WHEN** an existing `answer` returns a plain string
- **THEN** it is posted exactly as before, and nothing is kept

#### Scenario: Command returns a string
- **WHEN** a command's `execute` returns a plain string
- **THEN** `invoke` raises `TypeError`, and only the invocation message is posted

### Requirement: Backend links attachments
A backend that keeps attachments SHALL be able to return a link for one of them, given the message id and the attachment name. The link MUST be something a browser on the same machine can open. When the backend holds no attachment with that name for that message, it MUST return nothing.

#### Scenario: Known attachment
- **WHEN** the backend is asked for `msg-42` / `revenue.html` after keeping it
- **THEN** it returns a link that opens `revenue.html`'s content

#### Scenario: Unknown attachment
- **WHEN** the backend is asked for a name it never kept for that message
- **THEN** it returns nothing

### Requirement: Peers locate attachments
Any peer that declares the locate grant SHALL be able to call `locate(msg_id, name)`, which the session MUST route to the backend that links attachments and return its answer. When no backend links attachments, or the backend fails, `locate` MUST return nothing; a failure MUST be logged.

#### Scenario: Located through the backend
- **WHEN** a peer calls `locate("msg-42", "revenue.html")` and the backend has a link for it
- **THEN** `locate` returns that link

#### Scenario: No backend to ask
- **WHEN** a peer calls `locate` in a session with no backend that links attachments
- **THEN** `locate` returns nothing

### Requirement: Terminal opens attachment links
When the user activates a relative link in a message (no URL scheme, not starting with `/` or `#`), the terminal SHALL call `locate` with that message's id and the link target, with any leading `./` removed. It MUST open the link returned, and MUST tell the user "Not found" when `locate` returns nothing. Absolute links MUST keep opening as they did before this change.

#### Scenario: Attachment found
- **WHEN** the user activates `revenue.html` in message `msg-42` and `locate` returns a link
- **THEN** the terminal opens that link

#### Scenario: Attachment not found
- **WHEN** the user activates a relative link and `locate` returns nothing
- **THEN** nothing is opened and the terminal says "Not found"

#### Scenario: Absolute link
- **WHEN** the user activates `https://example.com` in a message
- **THEN** it opens as before, without calling `locate`

### Requirement: Database backend keeps attachments
`DatabaseBackend` SHALL keep attachments in its database, return a `file://` link for a kept attachment by writing its content to a file only when a link is asked for, and return its attachments' links again after the chat restarts on the same database. `forget` MUST drop the attachments of the messages it forgets, and files it wrote MUST be removed when the backend shuts down.

#### Scenario: Link after restart
- **WHEN** a message with an attachment is kept, the chat closes, and a new chat opens on the same database file
- **THEN** asking for that attachment's link returns a `file://` link to its content

#### Scenario: Forgotten with its message
- **WHEN** `forget` drops a message that had attachments
- **THEN** asking for any of that message's attachment links returns nothing

#### Scenario: Files cleaned at shutdown
- **WHEN** the backend wrote files to answer link requests and then shuts down
- **THEN** those files no longer exist
