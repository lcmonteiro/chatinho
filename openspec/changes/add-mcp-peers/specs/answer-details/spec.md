# Spec Delta

## Purpose

Lets a peer say more about its answer than its text — that it answers with a question of its own, or that it failed — and lets the asker get that status and the answer's message id, so answers can be relayed faithfully, attachments included.

## ADDED Requirements

### Requirement: Answer status
`Reply` SHALL accept an optional `status`, one of `answered` (the default), `asked` (the answer is a question back to the asker, for example when more information is needed) and `error` (the peer could not answer). A peer that does not know MUST answer `answered`, saying so in the text. A plain string answer, and a `Reply` without a status, MUST count as `answered`. Any other status MUST be refused with `ValueError` when the `Reply` is created.

#### Scenario: Plain answer
- **WHEN** a peer's `answer` returns `"sunny"`
- **THEN** the answer's status is `answered`

#### Scenario: Answered with a question
- **WHEN** a peer's `answer` returns `Reply("Which login flow?", status="asked")`
- **THEN** the answer's status is `asked` and its text is `Which login flow?`

#### Scenario: Peer reports an error
- **WHEN** a peer's `answer` returns `Reply("the forecast service is down", status="error")`
- **THEN** the answer's status is `error`

#### Scenario: Invalid status
- **WHEN** code creates `Reply("x", status="maybe")`
- **THEN** it raises `ValueError`

### Requirement: Detailed answers for the asker
The `ask` grant SHALL accept `detail=True`, which returns an `Answer` with the answer's `text`, `status` and `msg_id` (the id of the answer message in the conversation) instead of the text alone. Without `detail`, `ask` MUST keep returning the text, unchanged. A peer that answers later by saying a reply to the question MUST yield status `answered`.

#### Scenario: Text only by default
- **WHEN** a peer asks with `ask(to, "weather?")`
- **THEN** it gets the answer's text, as before

#### Scenario: Detail requested
- **WHEN** a peer asks with `ask(to, "draw it", detail=True)` and the answer attaches `chart.svg`
- **THEN** it gets an `Answer` whose `msg_id` lets it `locate` `chart.svg`, and whose status is `answered`
