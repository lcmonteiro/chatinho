## ADDED Requirements

### Requirement: Every peer keeps its own id
Every peer registered with a session SHALL keep a distinct id. A peer whose id the session chooses MUST get the lowest free number at or above the next one it would hand out, skipping any id a peer has already taken, whether that peer declared it (`@connector(name, id=...)`) or was registered at it. Registering a peer at an id that is already taken MUST raise `ValueError`, as it does today; no registration MAY silently replace a peer.

#### Scenario: A pinned peer, then a numbered one
- **WHEN** a session is built with a connector declaring `id=1`, then a connector declaring no id
- **THEN** the first has id 1, the second has id 2, and both are in the roster

#### Scenario: Two peers pinned to one id
- **WHEN** two connectors both declaring `id=1` are registered with one session
- **THEN** the second registration raises `ValueError`
