# Spec Delta: frontends

## ADDED Requirements

### Requirement: REQ-FRONT-029 Peer suggestions

Typing `@` at the start of the input SHALL list, by name and sorted, the peers that answer, the terminal never among them, filtered by what is typed after it; the list is hidden when nothing matches, when a space follows the name, and when no peer answers. Tab, or Enter, completes the highlighted peer as `@name ` instead of submitting; Up and Down move the highlight; Escape hides the list without changing the input. An `@` anywhere else in the line MUST NOT open the list. The peers are read as the person types, so one registered after the terminal started is listed.

#### Scenario: AC-FRONT-029.1 At alone lists every answering peer

- **GIVEN** a chat with two peers that answer
- **WHEN** `@` is typed
- **THEN** both are listed as `@name`, and the terminal is not

#### Scenario: AC-FRONT-029.2 A peer that does not answer is not listed

- **GIVEN** a chat with a peer that answers and one that only listens
- **WHEN** `@` is typed
- **THEN** only the peer that answers is listed

#### Scenario: AC-FRONT-029.3 Typing filters peers by prefix

- **WHEN** letters are typed after `@`
- **THEN** only the answering peers whose names start with them are listed

#### Scenario: AC-FRONT-029.4 No match hides the list

- **WHEN** what is typed after `@` matches no answering peer
- **THEN** the list is hidden

#### Scenario: AC-FRONT-029.5 Space after the name hides the list

- **WHEN** a space is typed after the peer's name
- **THEN** the list is hidden

#### Scenario: AC-FRONT-029.6 No answering peers means no list

- **GIVEN** a chat where no peer but the terminal answers
- **WHEN** `@` is typed
- **THEN** no list appears

#### Scenario: AC-FRONT-029.7 An at sign later in the line opens nothing

- **WHEN** `ask @` is typed
- **THEN** no list appears

#### Scenario: AC-FRONT-029.8 Tab completes the highlighted peer

- **WHEN** Tab is pressed with the list open
- **THEN** the input holds `@name ` of the highlighted peer and nothing is submitted

#### Scenario: AC-FRONT-029.9 Down then Up moves the highlight

- **WHEN** Down, then Tab, are pressed with two peers listed
- **THEN** the input holds the second peer; and Down, Up, then Tab gives the first

#### Scenario: AC-FRONT-029.10 Enter accepts the peer instead of submitting

- **WHEN** Enter is pressed with the list open
- **THEN** the peer is completed and nothing is submitted

#### Scenario: AC-FRONT-029.11 Escape hides the list without changing the input

- **WHEN** Escape is pressed with the list open
- **THEN** the list is hidden and the input unchanged

#### Scenario: AC-FRONT-029.12 A completed peer is asked

- **WHEN** a peer is completed from the list, text is typed after it and Enter is pressed
- **THEN** only that peer is asked, with the text after its name

#### Scenario: AC-FRONT-029.13 A peer registered later is listed

- **GIVEN** a peer that answers registered after the terminal started
- **WHEN** `@` is typed
- **THEN** that peer is listed
