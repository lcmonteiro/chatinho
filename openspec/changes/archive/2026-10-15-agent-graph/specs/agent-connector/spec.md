## MODIFIED Requirements

### Requirement: One question, one run of the agent
Each question the connector is asked, and each say of the user it responds to, SHALL go through the same steps: the chat's memory and the question become the agent's messages, the agent runs, the answer is checked for links to the files the run made, and the answer's text and those files become the result. The text MUST be that of the agent's last message; when that message's content is a list of blocks, the text blocks are joined. When `response_format` is set, the text MUST be the structured response as JSON. To a question, the result MUST be a `Reply` with that text and the run's files as attachments. Any failure of the run MUST become a reply with status `ERROR` naming the connector and the kind of failure, never an exception for whoever asked. Several questions MAY run at once, and none of them blocks the session.

#### Scenario: The last message is the answer
- **WHEN** the agent calls a tool and then answers "It is sunny."
- **THEN** the connector answers "It is sunny."

#### Scenario: A structured answer
- **WHEN** the connector has a `response_format` and the agent returns a structured response
- **THEN** the answer is that response as JSON

#### Scenario: The model fails
- **WHEN** the model raises while the agent runs
- **THEN** the answer is an `ERROR` reply naming the connector and the error's type

### Requirement: Memory comes from the chat
Before the question, the agent SHALL be given the messages `context()` returns for the connector's `memory` query, oldest first, with the same default as the OpenAI connector (what passed between it and anyone, without errors, the last twenty). Each say of the user that the connector responded to MUST be in its memory just before its response, even when the `memory` query does not select it. Its own messages MUST be assistant messages, the user's MUST be user messages, and other peers' MUST be user messages prefixed with the peer's name. The questions it asked through its tools, and their answers, MUST be left out. When a `checkpointer` is given, each question MUST run on its own thread (the question's id), never on a thread shared by several questions.

#### Scenario: It remembers the conversation
- **WHEN** the user tells the agent "My name is Ana" and then asks "What is my name?"
- **THEN** the second run receives the first question and its answer before the new question

#### Scenario: Its tool calls are not memory
- **WHEN** the agent asked `coder` through a tool while answering the first question
- **THEN** the second run's history holds the first question and answer, not the ask to `coder`

#### Scenario: One thread per question
- **WHEN** the connector has a checkpointer and is asked two questions
- **THEN** the two runs use two different thread ids

#### Scenario: It remembers what the user said to everyone
- **WHEN** the user says "My name is Ana" to everyone, the connector responds, and the user then says "What is my name?" to everyone
- **THEN** the second run receives "My name is Ana" and the connector's response before the new message

## ADDED Requirements

### Requirement: Files the agent made are attached
A tool result of the run whose artifact is an `Attachment`, or any object with a `name`, a `media_type` and `data` (text or bytes), SHALL become an attachment of the result, in the order the tools returned them; text data MUST be encoded as UTF-8. Only the files of the current run MUST be attached, never those of earlier messages in memory. When two files of one run share a name, the later one MUST be kept. A tool result with no such artifact MUST add no attachment.

#### Scenario: A tool makes a diagram
- **WHEN** the agent calls a tool that returns an artifact named `flow.svg` of type `image/svg+xml`, then answers "Here: [Flow](flow.svg)"
- **THEN** the reply's text is "Here: [Flow](flow.svg)" and it carries one attachment, `flow.svg`, of type `image/svg+xml`

#### Scenario: A plain answer has no attachments
- **WHEN** the agent answers without any tool returning an artifact
- **THEN** the reply carries no attachments

#### Scenario: Only this run's files
- **WHEN** the first question's run made `flow.svg`, and the second question's run makes no file
- **THEN** the second reply carries no attachments

### Requirement: The answer links its files
When the answer does not link a file of the run as a Markdown link target (`](<name>)`), the model SHALL be sent back with a reminder naming the missing links, and the answer after that SHALL be the result. The connector option `link_retries` (default `1`) MUST bound how many reminders one run sends; `0` MUST send none. The files MUST be attached whether or not the final answer links them.

#### Scenario: A missing link is asked for
- **WHEN** a tool makes `report.svg`, the agent answers "Ready.", and after the reminder answers "Here: [Report](report.svg)."
- **THEN** the model's third call ends with a reminder naming `(report.svg)`, and the reply is "Here: [Report](report.svg)." with `report.svg` attached

#### Scenario: Sent back at most link_retries times
- **WHEN** `link_retries` is `1`, a tool makes `report.svg`, and the agent answers "Ready." and then "Still ready."
- **THEN** the model is called three times, and the reply is "Still ready." with `report.svg` attached

#### Scenario: Verify turned off
- **WHEN** `link_retries` is `0`, a tool makes `report.svg`, and the agent answers "Ready."
- **THEN** the model is called twice, and the reply is "Ready." with `report.svg` attached

#### Scenario: Linked the first time
- **WHEN** a tool makes `flow.svg` and the agent answers "Here: [Flow](flow.svg)"
- **THEN** no reminder is sent

### Requirement: The user's says are responded to with a say
What the user says to everyone SHALL be responded to with a say from the connector replying to it, holding the same text and attachments a question would get. What other peers say to everyone MUST NOT be responded to; it reaches the agent only through memory. A message addressed to the connector MUST be answered as a question, never also responded to as a say. When the run fails, the response MUST be a say naming the connector and the kind of failure.

#### Scenario: The user says something to everyone
- **WHEN** the user says "Draw the login flow" to everyone and the agent answers "Here: [Login](login.svg)" after a tool made `login.svg`
- **THEN** the connector says "Here: [Login](login.svg)" replying to the user's message, with `login.svg` attached

#### Scenario: Another peer says something to everyone
- **WHEN** another peer says "hello" to everyone
- **THEN** the connector says nothing and the model is not called

#### Scenario: Asked directly
- **WHEN** the user asks the connector a question addressed to it
- **THEN** the model runs once and the connector answers with one reply, without also saying anything

#### Scenario: The run fails on a say
- **WHEN** the user says something to everyone and the model raises
- **THEN** the connector says a message naming itself and the error's type, replying to the user's message
