# Spec Delta: connectors

## Purpose

The peers that answer: a model behind any OpenAI-compatible endpoint, a remote chatinho session over MCP, and LangChain agents, basic and deep, given the chat as tools. It has no living spec yet; this records the behaviour it already has.

## ADDED Requirements

### Requirement: REQ-CONN-001 OpenAIConnector answers with the model's text

`OpenAIConnector` SHALL answer a question with a `Reply` holding the model's text, waiting for the model without blocking the session, so other peers keep working meanwhile.

#### Scenario: AC-CONN-001.1 The model's text is the answer

- **WHEN** the model replies "Sunny"
- **THEN** the connector answers with a `Reply` whose text is "Sunny" and whose status is `answered`

#### Scenario: AC-CONN-001.2 The chat keeps moving

- **WHEN** the connector is asked a question and the model takes a while
- **THEN** another peer's message is delivered before the model's reply arrives

### Requirement: REQ-CONN-002 OpenAIConnector takes an endpoint, a model and a system prompt

The connector SHALL take where to ask, which model and which key as one `Endpoint`, plus a `temperature`, an optional `max_tokens` and an optional `system` prompt. Requests MUST go to the endpoint's URL with its model; with no endpoint, or none set on it, they go to OpenAI itself with model `gpt-4o`. A `system` prompt MUST be the first message sent.

#### Scenario: AC-CONN-002.1 A system prompt leads

- **WHEN** a connector created with `system="You review code."` is asked something
- **THEN** the first message sent to the model is a `system` message with that text

#### Scenario: AC-CONN-002.2 Model, temperature and limit

- **WHEN** a connector with an endpoint for `http://localhost:11434/v1` and model `m-1`, `temperature=0.1` and `max_tokens=50` is asked
- **THEN** the request carries that model, temperature and limit, to that URL

#### Scenario: AC-CONN-002.3 Another endpoint

- **WHEN** a connector is created with an endpoint that has a URL, a model and a key
- **THEN** its requests go to that URL with that model and key

#### Scenario: AC-CONN-002.4 Another model on the same endpoint

- **WHEN** a connector is created with that endpoint's `with_model(...)`
- **THEN** its requests use the new model and the endpoint's URL and key

#### Scenario: AC-CONN-002.5 No endpoint

- **WHEN** a connector is created without an endpoint
- **THEN** it asks OpenAI itself, with model `gpt-4o`

### Requirement: REQ-CONN-003 OpenAIConnector remembers the conversation

The connector SHALL take a `memory` query (default `Query(peer=SELF, errors=False).last(20)`) and send the model the messages `context()` returns for it, oldest first, before the question. Its own earlier replies MUST be sent as `assistant` messages and every other message as a `user` message, a peer other than the user prefixed with its name. The question is sent once, last. With `memory=None` only the question is sent.

#### Scenario: AC-CONN-003.1 A follow-up question

- **WHEN** the user said "My name is Ana", the connector answered, and the user asks "What is my name?"
- **THEN** the model receives the first message as `user`, the answer as `assistant`, then the question

#### Scenario: AC-CONN-003.2 Another peer is named

- **WHEN** a connector whose memory selects everyone is asked after a peer named `coder` said something
- **THEN** the model receives that message as a `user` message prefixed `coder: `

#### Scenario: AC-CONN-003.3 Only its own exchanges by default

- **WHEN** a connector with the default memory is asked after two other peers talked to each other
- **THEN** their exchange is not sent to the model

#### Scenario: AC-CONN-003.4 No memory

- **WHEN** a connector created with `memory=None` is asked after a conversation
- **THEN** the model receives only the question

#### Scenario: AC-CONN-003.5 Bounded, and without errors

- **WHEN** a connector whose memory is the last two messages without errors answers a third say, the first having failed
- **THEN** the model receives the second say, its answer and the third, and no error reply

### Requirement: REQ-CONN-004 A lent key wins over the configured one

The connector SHALL answer with the credential lent on the message under its `credential` name (default `llm`) when there is one, for that message only, and otherwise with its endpoint's key, read when a question needs it and never shown. With neither, or when the endpoint's key source cannot yield a key, it MUST answer with an `error` reply without calling the model. A key MUST NOT appear in a reply or in the logs.

#### Scenario: AC-CONN-004.1 Answered with the asker's key

- **WHEN** a connector with its own key answers a message lent another key, then one lent nothing
- **THEN** the first request uses the lent key and the second its own

#### Scenario: AC-CONN-004.2 No key at all

- **WHEN** a connector whose endpoint has no key answers a message lent nothing
- **THEN** it answers with an `error` reply and the model is not called

#### Scenario: AC-CONN-004.3 A source that cannot read

- **WHEN** a connector whose key is `Env("OPENAI_API_KEY")` answers while the variable is unset
- **THEN** it answers with an `error` reply naming `OPENAI_API_KEY`, and the model is not called

#### Scenario: AC-CONN-004.4 A rotated key is used

- **WHEN** the connector's key is a file, it answers, the file is rewritten and it answers again
- **THEN** the second request uses the new key

#### Scenario: AC-CONN-004.5 The key is not shown

- **WHEN** a connector with its own key is printed, or its attributes listed
- **THEN** the key appears nowhere

#### Scenario: AC-CONN-004.6 A lent key stays out of replies and logs

- **WHEN** the endpoint refuses a request made with a lent key, with an error that quotes it
- **THEN** the `error` reply and the logs do not contain the key

### Requirement: REQ-CONN-005 OpenAIConnector's failures are answers

`initialize()` SHALL NOT call the model's API, so a chat starts even without a key. A failed request MUST become an `error` reply naming the connector and the kind of failure, without any key.

#### Scenario: AC-CONN-005.1 Starting without a key

- **WHEN** a session with a connector that has no key starts
- **THEN** it starts, and no request is made

#### Scenario: AC-CONN-005.2 The endpoint refuses

- **WHEN** the endpoint answers with an authentication error
- **THEN** the connector answers with an `error` reply naming itself and the failure, without the key

### Requirement: REQ-CONN-006 OpenAIConnector keeps one client per key

The connector SHALL build one client for its key and share it between questions asked at once. When the key changes, the client of the old key MUST be closed only once no question is using it. Its client is closed when the chat closes, and a connector that never built one closes without error.

#### Scenario: AC-CONN-006.1 Three questions at once

- **WHEN** the connector is asked three questions at once
- **THEN** each gets its own answer and one client was built

#### Scenario: AC-CONN-006.2 A rotated-out client

- **WHEN** the key changes while a question is still being answered with the old one
- **THEN** the old client stays open until that question is answered, and is closed after

#### Scenario: AC-CONN-006.3 Asked, then closed

- **WHEN** the connector answers a question and the chat is closed
- **THEN** the client it built is closed

#### Scenario: AC-CONN-006.4 Never asked

- **WHEN** the connector is never asked anything and the chat is closed
- **THEN** closing raises nothing

### Requirement: REQ-CONN-007 McpConnector connects to one remote session

`McpConnector` SHALL be built from exactly one server: an HTTP `url` with a bearer `token`, or an in-process `server`; none, both, or a URL without a token MUST raise `ValueError`. Its name in the chat is the `name` given, or the server's own name.

#### Scenario: AC-CONN-007.1 Exactly one server

- **WHEN** a connector is created with no server, with both a server and a URL, or with a URL and no token
- **THEN** each raises `ValueError`

#### Scenario: AC-CONN-007.2 Named by the connector

- **WHEN** `McpConnector(..., name="lab")` is added to a session
- **THEN** it appears in the chat as `lab`, and answers with what the remote session answered

#### Scenario: AC-CONN-007.3 Named by the server

- **WHEN** no `name` is given
- **THEN** the connector takes the server's name

### Requirement: REQ-CONN-008 McpConnector asks the remote session when it is asked

The connector SHALL send a question only when it is asked; it MUST NOT listen to the room. The question's text is sent as one ask of the remote peer: the `peer` given, or else the only remote peer that answers. Questions asked at once each get their own answer, and no connection stays open between questions.

#### Scenario: AC-CONN-008.1 Said to the room

- **WHEN** a peer says something to the room in a chat where another peer also answers
- **THEN** the connector sends nothing

#### Scenario: AC-CONN-008.2 The only answering peer here

- **WHEN** the connector is the only peer that answers and the user says something
- **THEN** the connector is asked it and asks the remote peer

#### Scenario: AC-CONN-008.3 Asked directly

- **WHEN** a peer asks the connector a question
- **THEN** the remote session's only answering peer is asked that text

#### Scenario: AC-CONN-008.4 Several remote peers

- **WHEN** the remote session has two peers that answer and the connector was built with `peer=`
- **THEN** each question is asked of the named peer

#### Scenario: AC-CONN-008.5 Questions at once

- **WHEN** several questions are asked of the connector at once
- **THEN** each gets the answer to its own question

#### Scenario: AC-CONN-008.6 No link stays open

- **WHEN** a question has been answered
- **THEN** the connector is no longer connected to the server

### Requirement: REQ-CONN-009 McpConnector answers every question once

For every question the connector SHALL answer exactly once: the remote answer's text with its attachments for `answered`; the remote peer's question, marked as a question back, for `asked`; and a short `error` reply naming itself for a remote error, for a remote session with no single peer that answers, and for a server that cannot be reached.

#### Scenario: AC-CONN-009.1 An answer with an attachment

- **WHEN** the remote answer carries an attachment
- **THEN** the connector replies with the text and the attachment, which the local backend keeps

#### Scenario: AC-CONN-009.2 A question back

- **WHEN** the remote result is `asked`
- **THEN** the connector replies with that question, with status `asked`

#### Scenario: AC-CONN-009.3 No single remote peer

- **WHEN** no `peer` was given and the remote session has no peer that answers
- **THEN** the connector answers with an `error` reply saying no single remote peer answers

#### Scenario: AC-CONN-009.4 A remote error

- **WHEN** the remote result is a tool error
- **THEN** the connector replies with a short `error` saying so

#### Scenario: AC-CONN-009.5 An unreachable server

- **WHEN** the server cannot be reached
- **THEN** the connector replies that it could not reach it

### Requirement: REQ-CONN-010 McpConnector lends only what it was told to

The connector SHALL delegate credentials only when configured with `delegate`, a mapping from a credential's name to a value, a function called once per question, or a key source read for each question. It MUST send only the configured credentials the server declared, with the question and not in its text. A source that cannot yield its key MUST make the connector answer that question with an `error` reply naming the reference, without sending the question.

#### Scenario: AC-CONN-010.1 Sent with the question

- **WHEN** a connector configured to delegate `llm` asks a server that declared `llm`
- **THEN** the remote peer that answers finds the credential on the message

#### Scenario: AC-CONN-010.2 Not declared, not sent

- **WHEN** the same connector asks a server that declared no credentials
- **THEN** no credential is sent

#### Scenario: AC-CONN-010.3 A token per question

- **WHEN** the configured value is a function
- **THEN** it is called once for each question and its result is what is lent

#### Scenario: AC-CONN-010.4 Nothing without delegate

- **WHEN** a connector without `delegate` asks a server that declared credentials
- **THEN** the request carries no credential

#### Scenario: AC-CONN-010.5 Lent from a key source

- **WHEN** the configured value is `Env(...)` and the variable is set
- **THEN** the variable's value is what is lent

#### Scenario: AC-CONN-010.6 A source that cannot read

- **WHEN** the configured value is `Env("UNSET")`
- **THEN** the connector answers with an `error` reply naming `UNSET`, and the question is not sent

### Requirement: REQ-CONN-011 BasicAgentConnector is built from create_agent's parameters

`BasicAgentConnector` SHALL take its name, a `model` and `tools`, plus any keyword argument `create_agent` accepts, and pass them on unchanged. A keyword argument `create_agent` does not accept, deep agents' options included, MUST raise `TypeError` naming it when the connector is created. A session can hold it, and no key is kept on it as text.

#### Scenario: AC-CONN-011.1 Options reach create_agent

- **WHEN** a connector is created with `system_prompt="Be brief."` and asked a question
- **THEN** the model receives that system prompt

#### Scenario: AC-CONN-011.2 An unknown option

- **WHEN** a connector is created with `temprature=0.2`, or with deep agents' `subagents`
- **THEN** creating it raises `TypeError` naming the argument

#### Scenario: AC-CONN-011.3 The key is not on the connector

- **WHEN** a connector is created with an `Endpoint` that has a key
- **THEN** the key appears nowhere in the connector's attributes

#### Scenario: AC-CONN-011.4 A session can hold it

- **WHEN** a session is created with the connector
- **THEN** it is created

### Requirement: REQ-CONN-012 One question, one run of the agent

Each question the agent connector is asked SHALL go through the same four steps: the chat's memory and the question become the agent's messages, the agent runs, the answer is checked for links to the run's files, and the text and files become the reply. The text MUST be that of the agent's last message, text blocks joined, or the structured response as JSON when `response_format` is set. A failure of the run MUST become a reply with status `error` naming the connector and the kind of failure. Several questions MAY run at once, and the agent is built once for them.

#### Scenario: AC-CONN-012.1 The last message is the answer

- **WHEN** the agent calls a tool and then answers
- **THEN** the connector answers with the last message's text

#### Scenario: AC-CONN-012.2 Text blocks are joined

- **WHEN** the last message's content is a list of blocks
- **THEN** the answer is its text blocks joined

#### Scenario: AC-CONN-012.3 A structured answer

- **WHEN** the connector has a `response_format` and the agent returns a structured response
- **THEN** the answer is that response as JSON

#### Scenario: AC-CONN-012.4 The model fails

- **WHEN** the model raises while the agent runs
- **THEN** the answer is an `error` reply naming the connector and the error's type

#### Scenario: AC-CONN-012.5 Two questions at once

- **WHEN** the connector is asked two questions at once
- **THEN** both are answered

#### Scenario: AC-CONN-012.6 The four steps

- **WHEN** the connector's graph is read
- **THEN** it runs `extract`, `agent`, `verify` and `load`, with `verify` able to send the run back to `agent`

#### Scenario: AC-CONN-012.7 Built once

- **WHEN** two first questions arrive at once, and then a third
- **THEN** the agent was built once

### Requirement: REQ-CONN-013 Files the agent made are attached

A tool result of the run whose artifact is an `Attachment`, or an object with a `name`, a `media_type` and `data`, SHALL become an attachment of the reply, in the order the tools returned them. Only the files of the current run are attached; when two share a name the later one is kept. The reply's attachments reach the backend that keeps them.

#### Scenario: AC-CONN-013.1 A tool makes a diagram

- **WHEN** a tool returns an artifact named `flow.svg` and the agent answers linking it
- **THEN** the reply carries that text and one attachment, `flow.svg`, with its media type

#### Scenario: AC-CONN-013.2 An Attachment as it is

- **WHEN** a tool's artifact is already an `Attachment`
- **THEN** the reply carries that same attachment

#### Scenario: AC-CONN-013.3 A plain answer

- **WHEN** no tool returns an artifact
- **THEN** the reply carries no attachments

#### Scenario: AC-CONN-013.4 Only this run's files

- **WHEN** the first question's run made a file and the second's makes none
- **THEN** the second reply carries no attachments

#### Scenario: AC-CONN-013.5 The last file of a name

- **WHEN** two files of one run share a name
- **THEN** the later one is attached

#### Scenario: AC-CONN-013.6 The files reach the backend

- **WHEN** the connector answers with a file in a session whose backend keeps attachments
- **THEN** the backend keeps the file under the answer

### Requirement: REQ-CONN-014 The answer links its files

When the answer does not link a file of the run as a Markdown link target, the model SHALL be sent back with a reminder naming the missing links, at most `link_retries` times (default 1; 0 sends none). The files MUST be attached whether or not the final answer links them.

#### Scenario: AC-CONN-014.1 A missing link is asked for

- **WHEN** a tool makes `report.svg`, the agent answers without linking it, and links it after the reminder
- **THEN** the model was reminded of `(report.svg)`, and the reply is the linked answer with the file attached

#### Scenario: AC-CONN-014.2 At most link_retries times

- **WHEN** `link_retries` is 1 and the agent never links the file
- **THEN** the model is called three times and the last answer is the reply, with the file attached

#### Scenario: AC-CONN-014.3 More retries

- **WHEN** `link_retries` is 2 and the agent links the file on its third answer
- **THEN** the model is called four times and the linked answer is the reply

#### Scenario: AC-CONN-014.4 Turned off

- **WHEN** `link_retries` is 0 and the agent does not link the file
- **THEN** the model is called twice and the file is still attached

#### Scenario: AC-CONN-014.5 Linked the first time

- **WHEN** the agent's first answer links the file
- **THEN** no reminder is sent

### Requirement: REQ-CONN-015 The user's says are responded to with a say

What the user says with `to` unset SHALL be responded to with a say from the agent connector replying to it, holding the text and attachments a question would get; when the run fails, the say names the connector and the kind of failure. What other peers say with `to` unset MUST NOT be responded to. A message addressed to the connector, a say the router gave it included, MUST be answered once as a question and not also responded to.

#### Scenario: AC-CONN-015.1 The user says something to everyone

- **WHEN** the user says something with `to` unset
- **THEN** the connector says its answer replying to that message, with the run's file attached

#### Scenario: AC-CONN-015.2 Another peer says something

- **WHEN** another peer says something with `to` unset
- **THEN** the connector says nothing and the model is not called

#### Scenario: AC-CONN-015.3 Asked directly

- **WHEN** the user asks the connector a question addressed to it
- **THEN** the model runs once and the connector answers with one reply

#### Scenario: AC-CONN-015.4 The only answering peer

- **WHEN** the connector is the only answering peer and the user says something
- **THEN** the model runs once and the connector answers once

#### Scenario: AC-CONN-015.5 The run fails on a say

- **WHEN** the user says something with `to` unset and the model raises
- **THEN** the connector says a message naming itself and the error's type, replying to the user's

### Requirement: REQ-CONN-016 The chat as the agent's tools

On a question the agent SHALL have, besides its own tools, an `ask_<peer>` tool per other peer that answers and a `run_<command>` tool per command, with `ask_user` only when asked for, limited to `peers=` and `commands=` when given, and reflecting who is in the chat when the question is asked. Names are made safe for a model API and kept apart; a tool of the caller's with the same name wins. An `ask_` tool returns the peer's `Reply`, which the model reads as its text, or as `error: ...` for an error reply; a peer that raises gives an `error` reply naming the peer and the kind of failure, and the run goes on. A peer asked through a tool MAY ask the connector back, bounded by the session's `max_depth`.

#### Scenario: AC-CONN-016.1 Asking another peer

- **WHEN** the agent calls `ask_coder` with a question
- **THEN** `coder` is asked it and its answer is the tool's result

#### Scenario: AC-CONN-016.2 Running a command

- **WHEN** the agent calls `run_help`
- **THEN** `/help` runs and what it answered is the tool's result

#### Scenario: AC-CONN-016.3 Never itself, never the user by default

- **WHEN** the agent is asked in a chat with the user, itself and one other peer
- **THEN** its chat tools are that peer's `ask_` tool and the commands' `run_` tools

#### Scenario: AC-CONN-016.4 ask_user when asked for

- **WHEN** the connector is created with `ask_user=True`
- **THEN** the agent has an `ask_user` tool that asks the user and returns the answer

#### Scenario: AC-CONN-016.5 Limited to the listed

- **WHEN** the connector is created with `peers=` and `commands=`
- **THEN** only the names listed become tools

#### Scenario: AC-CONN-016.6 A peer joins later

- **WHEN** a peer is added after the agent answered once, and the agent is asked again
- **THEN** the agent has that peer's `ask_` tool for the second question

#### Scenario: AC-CONN-016.7 Names made safe and kept apart

- **WHEN** the chat has peers `my coder` and `my_coder`
- **THEN** the tools are `ask_my_coder` and `ask_my_coder_2`

#### Scenario: AC-CONN-016.8 The caller's tool wins

- **WHEN** the caller gave a tool named `ask_coder` in a chat with a peer `coder`
- **THEN** the agent has the caller's tool only, and a warning says it hides the chat's

#### Scenario: AC-CONN-016.9 A peer's error reply

- **WHEN** the agent asks a peer that answers `Reply("quota exceeded", status="error")`
- **THEN** the model reads `error: quota exceeded`, and the agent still answers

#### Scenario: AC-CONN-016.10 An answer read as its text

- **WHEN** the agent asks a peer that answers
- **THEN** the model reads the answer's text alone

#### Scenario: AC-CONN-016.11 A failing peer

- **WHEN** the agent asks a peer whose `answer` raises
- **THEN** the tool returns an error naming the peer and the exception's type, and the agent still answers

#### Scenario: AC-CONN-016.12 Asked back

- **WHEN** the agent asks a peer, which asks the agent before answering
- **THEN** the agent answers the peer, the peer answers the agent, and the agent answers the user

#### Scenario: AC-CONN-016.13 A loop of agents

- **WHEN** two agents ask each other without end in a session with `max_depth=4`
- **THEN** the first question is answered with the limit's error, `too many nested asks (limit 4)`

### Requirement: REQ-CONN-017 The agent's memory comes from the chat

Before the question, the agent SHALL be given the messages `context()` returns for the connector's `memory` query, oldest first, with the same default as the OpenAI connector. Its own messages are assistant messages, the user's are user messages, and other peers' are user messages prefixed with the peer's name. The message each of its own replies answers MUST be in its memory just before that reply, even when the `memory` query does not select it: a say of the user it responded to, or a question that fell out of the query's limit. The questions it asked through its tools, and their answers, MUST be left out. With a `checkpointer`, each question MUST run on its own thread.

#### Scenario: AC-CONN-017.1 It remembers the conversation

- **WHEN** the user tells the agent something and then asks about it
- **THEN** the second run receives the first question and its answer before the new one

#### Scenario: AC-CONN-017.2 Its tool calls are not memory

- **WHEN** the agent asked a peer through a tool while answering the first question
- **THEN** the second run's history holds the first question and answer, not that ask

#### Scenario: AC-CONN-017.3 Other peers are named

- **WHEN** another peer's message is in the agent's memory
- **THEN** it is a user message prefixed with the peer's name

#### Scenario: AC-CONN-017.4 What the user said to everyone

- **WHEN** the user says something to everyone, the connector responds, and the user says something else
- **THEN** the second run receives the first say and the connector's response before the new message

#### Scenario: AC-CONN-017.5 One thread per question

- **WHEN** the connector has a checkpointer and is asked two questions
- **THEN** the two runs use different thread ids

### Requirement: REQ-CONN-018 The agent's model may be an Endpoint

`model` SHALL accept what the agent factory accepts and also an `Endpoint`, which becomes an OpenAI-compatible chat model whose key is read each time it is needed, never when the connector is created. A key that cannot be read, or an endpoint with none, MUST become an `error` reply naming the reason, without the key.

#### Scenario: AC-CONN-018.1 Created without the key

- **WHEN** a connector is created with an `Endpoint` whose key variable is not set, and asked
- **THEN** creating it succeeds, and the question gets an `error` reply saying the variable is not set

#### Scenario: AC-CONN-018.2 The key is read when the model is called

- **WHEN** the endpoint's key is a function
- **THEN** it is not called when the connector is created, is called when the model is, and its value is in neither the connector nor the reply

#### Scenario: AC-CONN-018.3 An endpoint without a key

- **WHEN** the endpoint has no key and the connector is asked
- **THEN** the reply says the endpoint has no API key configured

### Requirement: REQ-CONN-019 The agent's workspace as tools

An agent connector created with `workspace=True` in a session with a workspace provider SHALL give the agent a `ws_<op>` tool per operation of its own workspace and a `ws_<op>_of` tool per reading operation, taking the name of the peer whose workspace it reads, derived from the operations the provider's classes declare. A tool whose operation raises MUST return the failure as text naming the kind of error. A `diff` result becomes an attachment of the answer. Without `workspace=True` the agent has no `ws_` tools and no workspace is made for it; without a provider it still answers, with no `ws_` tools. A peer's workspace that appears later is reachable from the next question.

#### Scenario: AC-CONN-019.1 Its own workspace as tools

- **WHEN** the connector is created with `workspace=True` and asked
- **THEN** the agent has a `ws_` tool for each of the ten default operations

#### Scenario: AC-CONN-019.2 Writing through a tool

- **WHEN** the agent calls `ws_write`
- **THEN** the file is written in the connector's own workspace

#### Scenario: AC-CONN-019.3 Reading another peer's workspace

- **WHEN** the agent calls `ws_read_of` with another peer's name
- **THEN** the tool returns that peer's file, and there is no tool that writes to that peer's workspace

#### Scenario: AC-CONN-019.4 An added operation

- **WHEN** the provider's view class adds an operation `symbols`
- **THEN** the agent has `ws_symbols` and `ws_symbols_of`

#### Scenario: AC-CONN-019.5 A failing operation

- **WHEN** the agent calls `ws_read` with a path that leaves the workspace
- **THEN** the tool returns text naming `ValueError`, and the agent still answers

#### Scenario: AC-CONN-019.6 Not asked for

- **WHEN** the connector is created without `workspace=True` in a session with a provider
- **THEN** the agent has no `ws_` tools and no workspace is made for it

#### Scenario: AC-CONN-019.7 No provider

- **WHEN** the connector is created with `workspace=True` in a session with no provider
- **THEN** it answers, with no `ws_` tools, and logs that there is no provider

#### Scenario: AC-CONN-019.8 The diff is attached

- **WHEN** the agent calls `ws_diff`
- **THEN** the answer carries the diff as an attachment

#### Scenario: AC-CONN-019.9 A workspace that appears later

- **WHEN** another peer's workspace is made after the agent answered once
- **THEN** the agent is rebuilt for the next question, and was not rebuilt between the questions before

### Requirement: REQ-CONN-020 DeepAgentConnector is built from create_deep_agent's parameters

`DeepAgentConnector` SHALL take its name, a `model`, `tools`, the chat options and any keyword argument `create_deep_agent` accepts, passing them on unchanged, except that deep agents' own `memory` is given as `agent_memory`. A `backend` option MUST raise `TypeError` saying the workspace is the backend, and an unknown option `TypeError` naming it. It uses its workspace by default.

#### Scenario: AC-CONN-020.1 Deep agents' options reach the agent

- **WHEN** a connector is created with deep agents' `subagents` option and asked
- **THEN** creating it is accepted, it answers, and the agent has deep agents' `task` tool

#### Scenario: AC-CONN-020.2 memory and agent_memory

- **WHEN** a connector is created with `memory=Query().last(5)` and `agent_memory=["/AGENTS.md"]`
- **THEN** the question comes last, the oldest messages of a longer conversation are not sent, and the model's system prompt holds what `/AGENTS.md` says in the connector's workspace

#### Scenario: AC-CONN-020.3 A backend is refused

- **WHEN** a connector is created with `backend=...`
- **THEN** creating it raises `TypeError` saying the workspace is its backend

#### Scenario: AC-CONN-020.4 An unknown option

- **WHEN** a connector is created with an option `create_deep_agent` does not take
- **THEN** creating it raises `TypeError` naming it

#### Scenario: AC-CONN-020.5 Its workspace by default

- **WHEN** a connector is created with no `workspace` option
- **THEN** it uses its workspace

### Requirement: REQ-CONN-021 A deep agent's workspace is its backend

With a workspace provider, the deep agent's backend SHALL have the connector's own workspace at `/`, readable and writable, and each other peer's existing workspace at `/peers/<name>/`, read-only, so its own file tools work in its worktree, read the others' and cannot write them. Asking who has a workspace MUST make none. A peer's workspace that appears after a question is reachable from the next. Without a provider the connector still answers, on deep agents' default backend, with no `ws_` tools.

#### Scenario: AC-CONN-021.1 Working in its own workspace

- **WHEN** the deep agent calls `write_file` on `/src/fix.py`
- **THEN** `src/fix.py` is written in the connector's own worktree

#### Scenario: AC-CONN-021.2 Another peer's work

- **WHEN** the deep agent reads, then writes, a file under `/peers/reviewer/`
- **THEN** it gets reviewer's file, the write is refused as read-only, and reviewer's worktree is unchanged

#### Scenario: AC-CONN-021.3 A workspace that appears later

- **WHEN** a peer makes its workspace after the connector answered once, and the connector is asked again
- **THEN** the second run can read it under `/peers/`

#### Scenario: AC-CONN-021.4 Asking makes none

- **WHEN** the connector answers in a chat with another peer that never asked for a workspace
- **THEN** only the connector's own workspace exists

#### Scenario: AC-CONN-021.5 A chat without workspaces

- **WHEN** the connector is in a session with no provider and is asked
- **THEN** it answers, and has no `ws_` tools

### Requirement: REQ-CONN-022 A deep agent gets only the workspace tools its backend does not cover

With a workspace provider, the deep agent SHALL have `ws_` tools only for the operations its own file tools do not reach: by default `ws_diff`, `ws_log`, `ws_commit`, `ws_diff_of` and `ws_log_of`, plus those of any operation a project adds.

#### Scenario: AC-CONN-022.1 The default tools

- **WHEN** a connector with a workspace is asked
- **THEN** its `ws_` tools are `ws_diff`, `ws_log`, `ws_commit`, `ws_diff_of` and `ws_log_of`

#### Scenario: AC-CONN-022.2 A project operation

- **WHEN** the provider's view class adds an operation `symbols`
- **THEN** the deep agent has `ws_symbols` and `ws_symbols_of`

#### Scenario: AC-CONN-022.3 Committing

- **WHEN** the deep agent writes a file with its own tool and calls `ws_commit`
- **THEN** the commit is on the connector's branch

### Requirement: REQ-CONN-023 A deep agent is told where things are

With a workspace provider, the deep agent's system prompt SHALL begin with a paragraph saying where its own workspace and the other peers' are, followed by the `system_prompt` it was given, unchanged.

#### Scenario: AC-CONN-023.1 The user's prompt is kept

- **WHEN** a connector with a workspace is created with `system_prompt="Be brief."`
- **THEN** the model's system prompt mentions `/peers/` and then contains "Be brief."

### Requirement: REQ-CONN-024 DeepAgentConnector is the same peer in the chat

What `BasicAgentConnector` does in a chat SHALL hold for `DeepAgentConnector`. A run that ends interrupted, waiting for a decision nobody in the chat can give, MUST become an `error` reply, or a say, saying it was interrupted.

#### Scenario: AC-CONN-024.1 Asking another peer

- **WHEN** the deep agent calls `ask_coder`
- **THEN** `coder` is asked and its reply is the tool's result

#### Scenario: AC-CONN-024.2 The user's say

- **WHEN** the user says something with `to` unset
- **THEN** the connector says its answer replying to it

#### Scenario: AC-CONN-024.3 An interrupted question

- **WHEN** the connector has `interrupt_on` for a tool the agent calls while answering a question
- **THEN** the question gets an `error` reply saying the run was interrupted

#### Scenario: AC-CONN-024.4 An interrupted say

- **WHEN** the same happens on a say of the user's
- **THEN** the connector says once, replying to it, that the run was interrupted
