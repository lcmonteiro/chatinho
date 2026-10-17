## ADDED Requirements

### Requirement: A Reply reads as what it says
`str()` of a `Reply` SHALL be its text alone when its status is `answered`, and otherwise its status's value, a colon, a space and its text, so that whoever reads it as text, a model given a tool's result included, reads the answer and, when it did not answer, what it is instead. Attachments MUST NOT appear in it. `repr()` of a `Reply` MUST stay the dataclass's own.

#### Scenario: An answer reads as its text
- **WHEN** code takes `str(Reply("sunny"))`
- **THEN** it is `sunny`

#### Scenario: A question back says so
- **WHEN** code takes `str(Reply("which city?", status="asked"))`
- **THEN** it is `asked: which city?`

#### Scenario: A failure says so
- **WHEN** code takes `str(Reply("quota exceeded", status="error"))`
- **THEN** it is `error: quota exceeded`

#### Scenario: The repr is unchanged
- **WHEN** code takes `repr(Reply("sunny"))`
- **THEN** it names the text, the attachments and the status, as a dataclass's repr does
