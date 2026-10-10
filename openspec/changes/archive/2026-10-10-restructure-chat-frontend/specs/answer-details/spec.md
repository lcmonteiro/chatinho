# Spec Delta

## MODIFIED Requirements

### Requirement: The terminal asks with @name
In the terminal (`ChatFrontend`), a line that starts with `@<name>`, where `<name>` is a peer in the chat other than the terminal, followed by whitespace and some text, SHALL be an ask of that peer: it MUST be said addressed to that peer (`say(text, to=peer)`), with the text after the name only, so `@<name>` never reaches the message. Any other line, including `@<name>` alone or a name no peer has, MUST be said as typed.

#### Scenario: Asked by name
- **WHEN** the user types `@sol will it rain?` in a chat with peers `sol` and `lua`
- **THEN** only `sol` is asked, with the text `will it rain?`, and its answer replies to that message

#### Scenario: Not a peer
- **WHEN** the user types `@nobody hi`
- **THEN** `@nobody hi` is said to everyone, as typed
