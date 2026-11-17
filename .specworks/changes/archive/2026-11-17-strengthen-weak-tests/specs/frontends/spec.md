# Spec Delta: frontends

## MODIFIED Requirements

### Requirement: REQ-FRONT-020 Copying a message

The copy key SHALL copy the selected message, or say what to do when none is selected; it can be moved and is validated like the quit key. Copying takes both routes, OSC 52 and a clipboard helper when the system has one, and the confirmation is a popup that names the routes taken and shows what was copied on one line. The helper is the first found on `PATH`, is fed the text on standard input, and one that fails is logged, not raised; with none installed nothing fails.

#### Scenario: AC-FRONT-020.1 The copy key copies the selected message

- **WHEN** a message is selected and the copy key pressed
- **THEN** its text is copied

#### Scenario: AC-FRONT-020.2 The copy key says what to do when nothing is selected

- **WHEN** the copy key is pressed with nothing selected
- **THEN** a notice says to select a message first

#### Scenario: AC-FRONT-020.3 The copy key can be moved and is validated like the quit key

- **WHEN** another copy key is given, and one a terminal cannot send
- **THEN** the first copies and the second is refused

#### Scenario: AC-FRONT-020.4 Copying takes both routes and names them

- **WHEN** a message is copied on a system with a helper
- **THEN** the notice names OSC 52 and the helper

#### Scenario: AC-FRONT-020.5 With no helper the notification says only osc 52

- **WHEN** a message is copied on a system with no helper
- **THEN** the notice names OSC 52 only

#### Scenario: AC-FRONT-020.6 The confirmation is a popup that actually appears

- **WHEN** a message is copied with notifications on
- **THEN** a popup is on screen

#### Scenario: AC-FRONT-020.7 The confirmation shows what was copied on one line

- **WHEN** the text shown in the confirmation is made from a short text, a text with line breaks and runs of spaces, and a long text
- **THEN** the first is unchanged, the second has single spaces instead, and the third is cut at 60 characters ending with an ellipsis

#### Scenario: AC-FRONT-020.8 No helper installed is not a failure

- **WHEN** no clipboard helper is installed
- **THEN** copying reports no helper and raises nothing

#### Scenario: AC-FRONT-020.9 The first helper on path wins

- **WHEN** several helpers are on `PATH`
- **THEN** the first in the list is used

#### Scenario: AC-FRONT-020.10 The text is fed to the helper on stdin

- **WHEN** text is copied through a helper
- **THEN** the helper receives it on standard input

#### Scenario: AC-FRONT-020.11 A helper that fails is logged and not raised

- **WHEN** running the helper raises
- **THEN** copying raises nothing, reports no helper, and logs a warning naming the helper

#### Scenario: AC-FRONT-020.12 Put really runs the helper

- **WHEN** text is copied with a real helper on `PATH`
- **THEN** the helper ran and received the text

#### Scenario: AC-FRONT-020.13 The app really reaches the clipboard

- **WHEN** the terminal copies a message with a real helper on `PATH`
- **THEN** the helper received the message's text

### Requirement: REQ-FRONT-025 Asking one peer over MCP

`ask(peer, text)` SHALL say the text in the session addressed to the peer of that name and return that peer's answer as one result with its status, `answered` or `asked`, its text and its attachments. A name no other peer has, a peer that does not answer, a peer that fails, and a reply whose status is `error` MUST each yield a tool error.

#### Scenario: AC-FRONT-025.1 Ask a peer by name

- **WHEN** a client asks `weather` in a session with two peers
- **THEN** only `weather` is asked and its answer is the result

#### Scenario: AC-FRONT-025.2 Answered

- **WHEN** the asked peer answers `sunny`
- **THEN** the result is `answered` with text `sunny`

#### Scenario: AC-FRONT-025.3 Answered with a question

- **WHEN** the asked peer answers with status `asked`
- **THEN** the result is `asked` with its text

#### Scenario: AC-FRONT-025.4 Ask keeps the status

- **WHEN** the asked peer answers with a question back
- **THEN** the result's status is `asked`

#### Scenario: AC-FRONT-025.5 A failing peer is an error

- **WHEN** the asked peer's `answer` raises
- **THEN** the result is a tool error saying what failed

#### Scenario: AC-FRONT-025.7 Ask who cannot answer

- **WHEN** a client asks a name no peer has, or a peer that does not answer
- **THEN** the result is a tool error

#### Scenario: AC-FRONT-025.8 Attachments come back

- **WHEN** the answering peer attaches a file
- **THEN** the result carries its name, media type and content

#### Scenario: AC-FRONT-025.9 A reply with status error

- **WHEN** the asked peer answers `Reply("quota exceeded", status=error)`
- **THEN** the result is a tool error whose text is `quota exceeded`

