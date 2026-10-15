## ADDED Requirements

### Requirement: A reply that resolves an ask is heard, not answered
A reply that resolves an ask still waiting SHALL be handed to the asker only as a listener, when it listens, and MUST NOT be handed to its `answer`, even when the asker both listens and answers. Only a message put to a peer, and not resolving one of its asks, SHALL reach that peer's `answer`.

#### Scenario: A peer that listens and answers asks another
- **WHEN** a peer that listens and answers is asked "go", and while answering asks another peer, which replies
- **THEN** its `answer` is called once, for "go", and it hears the reply as a listener
