# framework

## Purpose

The framework is the chat itself: a session that registers peers and commands by what they declare, delivers every message between them without one holding up another, and gives each the conversation, the attachments and the workspaces it asked for. It has no living spec yet; this records the behaviour it already has.

## Requirements

### Requirement: REQ-CORE-001 Every peer has its own id

The session SHALL give every peer it registers a distinct integer id. The frontend is peer zero (`LOCAL`); a peer whose id the session chooses MUST get the next id the session would hand out, counting from one and skipping any id already taken; a peer MAY declare the id it answers to (`@connector(name, id=...)`), and the caller MAY pin a different one when registering it. Registering a peer at an id already taken MUST raise `ValueError`, and a declared id that is `TOOL` or not an integer MUST be refused with `ValueError` when the class is declared. A command has no id.

#### Scenario: AC-CORE-001.1 The user is zero and connectors are numbered

- **GIVEN** a session with a frontend, two connectors and one command
- **WHEN** the roster is read
- **THEN** the frontend is 0, the connectors are 1 and 2 in the order given, and the command's name has no id

#### Scenario: AC-CORE-001.2 A taken id is refused

- **WHEN** a peer is registered at an id another peer holds
- **THEN** `ValueError` is raised saying the id is already taken

#### Scenario: AC-CORE-001.3 A peer declares its id

- **GIVEN** a connector declared with `id=LOCAL` and another with no id
- **WHEN** both are given to a session
- **THEN** the first is 0 and the second is 1

#### Scenario: AC-CORE-001.4 A numbered peer skips a pinned id

- **GIVEN** a connector declared with `id=1`, then a connector declaring no id
- **WHEN** both are given to a session
- **THEN** the first has id 1 and the second id 2

#### Scenario: AC-CORE-001.5 Two peers pinned to one id

- **WHEN** two connectors both declared with `id=1` are registered with one session
- **THEN** the second registration raises `ValueError`

#### Scenario: AC-CORE-001.6 The caller pins another id

- **GIVEN** a connector declared with `id=LOCAL`
- **WHEN** it is registered with `at=7`
- **THEN** it is registered at 7

#### Scenario: AC-CORE-001.7 An id that cannot be declared

- **WHEN** a class is declared with `id=TOOL`, or with an id that is not an integer
- **THEN** the declaration raises `ValueError`

### Requirement: REQ-CORE-002 A name is not an address

Every peer and command SHALL have a visible name, set by `@connector`, `@tool`, `@frontend` or `@backend`, which an instance MAY override; an undecorated class falls back to its class name, and a name that is not a non-empty string MUST be refused with `ValueError`. Messages MUST be routed by id, never by name, so renaming a peer does not change where its messages go. A `@tool` also carries a description. A `@connector` MAY carry a one-line description of what the peer is for, which an instance MAY override; it defaults to empty, and a description that is not a string MUST be refused with `ValueError`.

#### Scenario: AC-CORE-002.1 Renaming keeps the address

- **GIVEN** a peer registered at id 1
- **WHEN** its name is changed and id 1 is asked
- **THEN** the same peer answers, and the session finds id 1 under the new name

#### Scenario: AC-CORE-002.2 A class names itself, an instance overrides

- **GIVEN** a class decorated `@connector("weather")`
- **WHEN** one instance sets its own `name`
- **THEN** that instance has the new name and the others keep `weather`

#### Scenario: AC-CORE-002.3 A tool carries its description

- **WHEN** a class is decorated `@tool("deploy", "Ship it")`
- **THEN** its name is `deploy` and its description `Ship it`

#### Scenario: AC-CORE-002.4 An undecorated class

- **WHEN** the name of an instance of an undecorated class is read
- **THEN** it is the class's own name

#### Scenario: AC-CORE-002.5 An empty name

- **WHEN** `connector`, `tool`, `backend` or `frontend` is given an empty, blank or non-string name
- **THEN** it raises `ValueError`

#### Scenario: AC-CORE-002.6 A peer carries its description

- **GIVEN** a class decorated `@connector("weather", description="Forecasts by city")`
- **WHEN** one instance sets its own `description`
- **THEN** that instance has the new description and the others keep `Forecasts by city`

#### Scenario: AC-CORE-002.7 No description

- **WHEN** a class is decorated `@connector("weather")`
- **THEN** its description is empty

#### Scenario: AC-CORE-002.8 A description that is not a string

- **WHEN** `connector` is given a description that is not a string
- **THEN** it raises `ValueError`

### Requirement: REQ-CORE-003 The frontend is peer zero

The session SHALL take the peer that speaks for the person as its `frontend`, register it at `LOCAL` before every other peer, and pin it there whether or not it declared `@frontend`. `@frontend(name)` MUST name a class and declare `LOCAL` as its id; its name defaults to `chat`, and using it without parentheses MUST raise `ValueError`. A session MUST have at most one frontend.

#### Scenario: AC-CORE-003.1 The frontend role

- **GIVEN** a class decorated `@frontend("terminal")`
- **WHEN** it is passed as `frontend` with one connector
- **THEN** it is peer 0 and the connector is peer 1

#### Scenario: AC-CORE-003.2 The parameter pins zero

- **GIVEN** a class decorated only `@connector("terminal")`
- **WHEN** it is passed as `frontend`
- **THEN** it is peer 0

#### Scenario: AC-CORE-003.3 One frontend

- **WHEN** a session is given a frontend and a connector that also declares `LOCAL`
- **THEN** `ValueError` is raised saying the id is already taken

#### Scenario: AC-CORE-003.4 Registered first

- **WHEN** a session is built with a frontend and two connectors
- **THEN** the roster lists 0, 1, 2 in that order

#### Scenario: AC-CORE-003.5 What @frontend declares

- **WHEN** a class is decorated `@frontend("terminal")`, and another `@frontend()`
- **THEN** the first is named `terminal` with declared id `LOCAL`, and the second is named `chat`

#### Scenario: AC-CORE-003.6 Without parentheses

- **WHEN** `@frontend` is applied without parentheses
- **THEN** it raises `ValueError`

### Requirement: REQ-CORE-004 A class declares its hooks

A peer or command SHALL declare each hook it uses with one `@require(hook, **options)`, stacked. A hook that demands a method MUST be checked when the class is declared: a missing or misspelled method raises `TypeError`. Passing two hooks to one `require`, or something that is not a hook, MUST raise `TypeError`. Options belong to the hook they were given with, are read back as a copy, and merge when a hook is declared twice, the declaration written highest winning. A subclass's declarations MUST NOT change its parent's.

#### Scenario: AC-CORE-004.1 A declared method that exists

- **WHEN** a class with a `listen` method declares `HookListen`
- **THEN** the declaration is accepted and the class declares that hook

#### Scenario: AC-CORE-004.2 A missing or misspelled method

- **WHEN** a class declares `HookListen` with no `listen`, or `HookAnswer` with a method called `answers`
- **THEN** the declaration raises `TypeError` naming the method

#### Scenario: AC-CORE-004.3 A hook that only grants

- **WHEN** a class with no methods declares `HookSay`
- **THEN** the declaration is accepted

#### Scenario: AC-CORE-004.4 Hooks stack

- **WHEN** a class stacks `@require(HookListen)` and `@require(HookAsk)`
- **THEN** it declares both

#### Scenario: AC-CORE-004.5 Two hooks in one require

- **WHEN** `require` is given two hooks
- **THEN** it raises `TypeError` saying to stack decorators

#### Scenario: AC-CORE-004.6 Not a hook

- **WHEN** `require` is given a string
- **THEN** it raises `TypeError`

#### Scenario: AC-CORE-004.7 Options ride with their hook

- **GIVEN** a class with `@require(HookAsk, timeout=30)` and `@require(HookListen, batch=5)`
- **WHEN** the options of each hook are read
- **THEN** `HookAsk` has `timeout=30`, `HookListen` has `batch=5`, and an undeclared hook has none

#### Scenario: AC-CORE-004.8 Options are a copy

- **WHEN** the options read back are changed
- **THEN** reading them again gives the declared values

#### Scenario: AC-CORE-004.9 Declared twice

- **WHEN** a class has `@require(HookAsk, timeout=1)` above `@require(HookAsk, timeout=99, retries=2)`
- **THEN** its options are `timeout=1` and `retries=2`

#### Scenario: AC-CORE-004.10 A subclass

- **GIVEN** a parent declaring `HookAsk` and a subclass declaring `HookListen`
- **WHEN** each one's hooks are read
- **THEN** the parent has `HookAsk` only and the subclass has both

### Requirement: REQ-CORE-005 A peer gets only what it declared

The session SHALL grant a registered peer or command exactly the callables of the hooks it declared, bound to its own id, and MUST call a method only when the hook that demands it was declared. A peer therefore cannot speak in another peer's name.

#### Scenario: AC-CORE-005.1 Only the declared grants

- **WHEN** a peer declaring only `HookSay` is registered
- **THEN** it has `say`, and has neither `ask` nor `context`

#### Scenario: AC-CORE-005.2 Declaring nothing

- **GIVEN** a class with a `listen` method and no declaration
- **WHEN** it is registered and a message is said
- **THEN** it declares no hooks and its `listen` is never called

#### Scenario: AC-CORE-005.3 The speaker is fixed

- **WHEN** a peer says a message
- **THEN** the message's `frm` is that peer's id

### Requirement: REQ-CORE-006 A say reaches everyone but the speaker

`say(text, reply_to=None)` SHALL post a message that every listening peer but the speaker hears, and return the new message's id. A reply to a say is another say, with `reply_to` set. A peer that listens MUST hear every message that crosses the session: says, asks, answers, command invocations and their answers.

#### Scenario: AC-CORE-006.1 Everyone but the speaker

- **WHEN** the user says a message in a chat with one listener
- **THEN** the listener hears it and the user does not

#### Scenario: AC-CORE-006.2 A reply is another say

- **WHEN** a peer says a message, then says another with `reply_to` set to the first
- **THEN** the conversation holds both, the second replying to the first

#### Scenario: AC-CORE-006.3 What is said reaches the one that listens

- **GIVEN** a backend that listens
- **WHEN** a message is said and the session is closed
- **THEN** the backend holds the message

### Requirement: REQ-CORE-007 An ask returns the answer

`ask(to, text)` SHALL post a message addressed to peer `to`, wait for that peer's reply, and return it as a `Reply` holding the answer's text and status, whatever the status. Asking an id that is no peer MUST raise `ValueError`. An `answer` that returns `None` leaves the ask waiting, and what the asked peer later says with `reply_to` set to the question resolves it. A peer MAY ask the user (`LOCAL`). When the asked peer's `answer` fails, the waiting `ask` MUST return the `error` reply the session posts for that failure, and MUST NOT raise the peer's error.

#### Scenario: AC-CORE-007.1 The answer comes back

- **WHEN** a peer asks another, whose `answer` returns `Reply("eco: ola")`
- **THEN** `ask` returns a `Reply` with text `eco: ola` and status `answered`

#### Scenario: AC-CORE-007.2 An unknown id

- **WHEN** a peer asks id 99 in a chat with no such peer
- **THEN** `ask` raises `ValueError`

#### Scenario: AC-CORE-007.3 Answered later

- **GIVEN** a peer whose `answer` returns `None`
- **WHEN** it later says a message with `reply_to` set to the question
- **THEN** the waiting `ask` returns that message's text

#### Scenario: AC-CORE-007.4 A peer asks the user

- **WHEN** a peer asks `LOCAL` and the frontend answers
- **THEN** `ask` returns the frontend's answer

#### Scenario: AC-CORE-007.5 The asked peer fails

- **GIVEN** a peer whose `answer` raises `RuntimeError`
- **WHEN** it is asked, and another peer is asked meanwhile
- **THEN** the first `ask` returns a `Reply` with status `error` naming the peer and `RuntimeError`, and the second returns its answer

#### Scenario: AC-CORE-007.6 A question back and a failure

- **WHEN** the answer is `Reply("which city?", status="asked")`, or `Reply("quota exceeded", status="error")`
- **THEN** `ask` returns a `Reply` with that text and that status, and an `error` answer is in the conversation with status `error`

### Requirement: REQ-CORE-008 Only the asked peer resolves an ask

A waiting `ask` SHALL be resolved only by a reply to its question from the peer the question is addressed to. Any other peer's reply to that question MUST be heard like any message and leave the ask waiting.

#### Scenario: AC-CORE-008.1 A bystander replies first

- **GIVEN** a peer that answers after 0.2 seconds and a listener that replies at once to every question it overhears
- **WHEN** the slow peer is asked
- **THEN** `ask` returns the slow peer's answer, and the conversation also holds the bystander's reply

#### Scenario: AC-CORE-008.2 The user answers a question put to them

- **WHEN** a peer asks the user and the user says a reply to that question
- **THEN** `ask` returns a `Reply` holding the user's text

### Requirement: REQ-CORE-009 A say may be addressed to one peer

`say` SHALL take an optional `to`, a peer id. A say with `to` MUST be put to that peer's `answer` without anyone waiting on it, its reply posted with `reply_to` set to the say, and every listener still hears the say. A `to` that is not another peer in the chat MUST raise `ValueError`.

#### Scenario: AC-CORE-009.1 Said to one peer

- **GIVEN** a chat where two peers answer
- **WHEN** a peer says a message with `to` set to one of them
- **THEN** only that peer is asked, and its answer replies to the say

#### Scenario: AC-CORE-009.2 Said to nobody

- **WHEN** a peer says a message with `to` set to an id that is not in the chat, or to itself
- **THEN** `say` raises `ValueError`

### Requirement: REQ-CORE-010 A Reply says what kind of answer it is

`Reply` SHALL carry text, attachments and a `status`: `answered` (the default), `asked` (a question back) or `error`. The status is a string enum, so its value is accepted too; any other status MUST raise `ValueError` when the `Reply` is created. `str()` of a `Reply` MUST be its text alone when it answered, and otherwise its status, a colon, a space and its text; its `repr` stays the dataclass's own.

#### Scenario: AC-CORE-010.1 Answered unless it says otherwise

- **WHEN** `Reply("sunny")` is created
- **THEN** its status is `answered`

#### Scenario: AC-CORE-010.2 The enum and its value

- **WHEN** a `Reply` is created with `status="asked"` or `status=ReplyStatus.ASKED`
- **THEN** both have status `asked`

#### Scenario: AC-CORE-010.3 An unknown status

- **WHEN** `Reply("x", status="maybe")` is created
- **THEN** it raises `ValueError`

#### Scenario: AC-CORE-010.4 Read as text

- **WHEN** `str()` is taken of an answered reply, a question back and a failure
- **THEN** it is `sunny`, `asked: which city?` and `error: quota exceeded`

#### Scenario: AC-CORE-010.5 The repr

- **WHEN** `repr(Reply("sunny"))` is taken
- **THEN** it names the text, the attachments and the status

### Requirement: REQ-CORE-011 An answer is a Reply, posted for the peer

A peer's `answer` SHALL return a `Reply` or `None`; anything else, a plain string included, MUST be treated as that peer failing with `TypeError`. The session SHALL post what `answer` returns in the peer's name: replying to the question, carrying the reply's status, and addressed to nobody. When `answer` fails, whether or not an `ask` is waiting, the session MUST post in the peer's name a reply with status `error`, replying to the question and addressed to nobody, whose text names the peer and the type of the error and never the error's message, and the chat carries on.

#### Scenario: AC-CORE-011.1 A string is refused

- **WHEN** a peer's `answer` returns a string
- **THEN** an `ask` of it returns a `Reply` with status `error` naming `TypeError`, and a say addressed to it gets an `error` reply

#### Scenario: AC-CORE-011.2 The status travels on the message

- **WHEN** a peer answers with `Reply("which city?", status="asked")`
- **THEN** the answer's message in the conversation has status `asked`

#### Scenario: AC-CORE-011.3 An answer is addressed to nobody

- **WHEN** a peer is asked and answers
- **THEN** the question's `to` is that peer, and the answer has `to` unset and `reply_to` set to the question

#### Scenario: AC-CORE-011.4 An error reply is addressed to nobody

- **GIVEN** a peer whose `answer` raises
- **WHEN** a say is addressed to it
- **THEN** the conversation holds a reply to the say with status `error` and `to` unset

#### Scenario: AC-CORE-011.5 A failed ask is in the conversation

- **GIVEN** a peer whose `answer` raises `RuntimeError("secret prompt")`
- **WHEN** it is asked
- **THEN** the conversation holds one reply to the question, from that peer, with status `error`, `to` unset, and text naming `RuntimeError` but not `secret prompt`

### Requirement: REQ-CORE-012 An answer is heard, not answered

A peer's `answer` SHALL be called for a message exactly when the message's `to` is that peer. An answer MUST NOT be handed to anyone's `answer`, whether or not an ask is waiting on it and even when the asker both listens and answers; it is heard by every listener. A peer that is addressed but does not declare `HookAnswer` is not asked.

#### Scenario: AC-CORE-012.1 A peer that listens and answers asks another

- **GIVEN** a peer that listens, answers and asks
- **WHEN** it is asked "go" and, while answering, asks another peer, which replies
- **THEN** its `answer` was called once, for "go", and it heard the reply as a listener

#### Scenario: AC-CORE-012.2 An answer to an addressed say

- **WHEN** a peer that answers says "hi" addressed to another peer that answers, which replies
- **THEN** the speaker's `answer` is not called, the conversation holds exactly the say and its answer, and a speaker that listens hears the answer

#### Scenario: AC-CORE-012.3 Two answering peers do not trade answers

- **GIVEN** a chat whose only answering peers are A and B, with the default router
- **WHEN** A says something neither addressed nor a reply
- **THEN** B's `answer` is called once, A's never, and the conversation holds two messages

#### Scenario: AC-CORE-012.4 A frontend that does not answer

- **GIVEN** a frontend that listens and does not declare `HookAnswer`
- **WHEN** it says something addressed to a peer, which answers
- **THEN** the frontend hears the answer and no warning is logged about a peer asked without `HookAnswer`

#### Scenario: AC-CORE-012.5 A late answer is not put to the asker

- **GIVEN** an asker that also answers, and a peer that returns `None` and says its reply later
- **WHEN** the asker asks that peer
- **THEN** `ask` returns the late reply, the asker's `answer` is never called, and the late reply has `to` unset

#### Scenario: AC-CORE-012.6 The user's answer to a question

- **WHEN** a peer asks the user and the user says a reply to the question
- **THEN** the user's reply has `to` unset

### Requirement: REQ-CORE-013 Commands run, they are not spoken to

A peer granted `invoke(name, args)` SHALL run the command of that name. The session MUST post the invocation as a message from the invoker addressed to `TOOL`, call the command's `execute(args, by=<invoker's id>)`, post what it returns as a message from `TOOL` replying to the invocation and addressed to nobody, and return its text. Invoking a name that is no command MUST return `None`. `execute` MUST return a `Reply` or `None`: a string raises `TypeError` and only the invocation is posted. A command granted `say` says as `TOOL`. Registering something that does not declare `HookExecute` as a command MUST raise `TypeError`.

#### Scenario: AC-CORE-013.1 The invocation and the answer are messages

- **WHEN** the user runs command `eco` with `ola`, and it returns `Reply("eco: ola")`
- **THEN** `invoke` returns `eco: ola`, and the conversation holds `/eco ola` from the user to `TOOL` and `eco: ola` from `TOOL` to nobody, replying to it

#### Scenario: AC-CORE-013.2 No such command

- **WHEN** a name that is no command is invoked
- **THEN** `invoke` returns `None`

#### Scenario: AC-CORE-013.3 A command that says

- **GIVEN** a command that declares `HookSay`, says "working" and returns `Reply("done")`
- **WHEN** it is run
- **THEN** the conversation holds the invocation, "working" and "done", in that order

#### Scenario: AC-CORE-013.4 Told who ran it

- **WHEN** the user runs a command
- **THEN** its `execute` receives `by=LOCAL`

#### Scenario: AC-CORE-013.5 Not a command

- **WHEN** an object that does not declare `HookExecute` is registered as a command
- **THEN** `TypeError` is raised naming `HookExecute`

#### Scenario: AC-CORE-013.6 A string result

- **WHEN** a command's `execute` returns a string
- **THEN** `invoke` raises `TypeError` saying it must return a `Reply`

### Requirement: REQ-CORE-014 Every delivery runs on its own

The session SHALL hand each message to each peer it is for without waiting for that or any other peer to finish with an earlier message, so a peer MAY be inside `answer` or `listen` for several messages at once. Posting a message MUST return once the message is in the conversation, before any peer has heard or answered it. The conversation's order is the order messages were posted. A listener that raises MUST NOT lose the message or stop the chat.

#### Scenario: AC-CORE-014.1 A peer answers two questions at once

- **WHEN** two asks are put to the same peer, whose `answer` takes 0.3 seconds
- **THEN** both answers arrive in under 0.45 seconds in total

#### Scenario: AC-CORE-014.2 A slow peer holds up nobody

- **WHEN** a peer that takes 0.3 seconds and one that answers at once are asked together
- **THEN** both answers arrive in under 0.45 seconds in total

#### Scenario: AC-CORE-014.3 Order is the order said

- **WHEN** a peer says two messages in a row and a listener is slower with the first than with the second
- **THEN** `context()` returns them in the order they were said

#### Scenario: AC-CORE-014.4 Say returns before anyone heard

- **GIVEN** a listener that takes time over each message
- **WHEN** a message is said
- **THEN** `say` has returned before the listener finished

#### Scenario: AC-CORE-014.5 A listener that fails

- **GIVEN** a backend whose `listen` raises
- **WHEN** a message is said
- **THEN** the message is still in the conversation

### Requirement: REQ-CORE-015 Asks may recurse, to a limit

A peer answering a question SHALL be able to ask any peer, including one waiting on an answer from it. The session SHALL track nesting: a question asked, or said with `to` or `reply_to`, by a peer while it answers a question of depth N has depth N + 1, and any other question, one asked from `listen` included, has depth 1. The limit is `max_depth`, 8 by default. A question deeper than the limit MUST NOT reach its peer: it gets a reply with status `error` saying there are too many nested asks, which a waiting `ask` returns; a say past the limit that replies to another message MUST be dropped with no error reply.

#### Scenario: AC-CORE-015.1 A asks B, and B asks A back

- **WHEN** the user asks A, A's `answer` asks B, and B's `answer` asks A before replying
- **THEN** A answers B, B answers A, and A answers the user

#### Scenario: AC-CORE-015.2 A loop stops at the limit

- **GIVEN** two peers that answer every question by asking the other
- **WHEN** the user asks one of them with the default limit
- **THEN** the question past the limit gets an `error` reply saying there are too many nested asks, and the user's question is answered

#### Scenario: AC-CORE-015.3 The limit is configurable

- **GIVEN** a session with `max_depth=2`
- **WHEN** a question is nested three deep
- **THEN** the third gets the `error` reply and its peer's `answer` is not called

#### Scenario: AC-CORE-015.4 The asker past the limit

- **WHEN** a peer asks a question that is past the limit
- **THEN** `ask` returns a `Reply` with status `error` whose text says there are too many nested asks

#### Scenario: AC-CORE-015.5 Unrelated questions

- **GIVEN** a session with `max_depth=1`
- **WHEN** the user asks a peer twice in a row
- **THEN** both are answered

#### Scenario: AC-CORE-015.6 Listening is not nesting

- **GIVEN** a session with `max_depth=1` and a peer that asks from `listen` when it hears an answer
- **WHEN** that answer is posted
- **THEN** the question asked from `listen` is answered

#### Scenario: AC-CORE-015.7 Replies traded past the limit

- **GIVEN** two peers that answer every question by saying a reply to it from inside `answer`
- **WHEN** one of them is asked
- **THEN** the exchange stops at the limit and no `error` reply is posted for the reply that was dropped

### Requirement: REQ-CORE-016 Starting, serving and closing

`start()` SHALL call `initialize()` on every peer, command and role that has one, awaiting it when it is a coroutine, and then deliver what was posted before the peer was started. Serving SHALL run every peer's `serve()` at once: the first to return ends the chat and the rest are cancelled, a `serve` that raises is not swallowed, and a session with nothing serving runs until it is interrupted. `close()` SHALL wait up to `CLOSE_TIMEOUT` (five seconds) for the deliveries in flight, log a warning and cancel what remains, and an ask whose answer was cancelled MUST fail rather than keep waiting.

#### Scenario: AC-CORE-016.1 An asynchronous initialize

- **GIVEN** a peer whose `initialize` is a coroutine
- **WHEN** the session is started
- **THEN** it has run by the time `start()` returns, and not before

#### Scenario: AC-CORE-016.2 Said before start

- **WHEN** a message is said before `start()` and a peer listens
- **THEN** the peer hears it after `start()`

#### Scenario: AC-CORE-016.3 A peer added after start

- **WHEN** a peer is registered after `start()`, a message is said, and the session is started again
- **THEN** the peer hears that message once it is started, and not before

#### Scenario: AC-CORE-016.4 The first to finish serving ends the chat

- **GIVEN** a peer whose `serve` returns and one whose `serve` never does
- **WHEN** the session serves
- **THEN** serving ends and the second is cancelled

#### Scenario: AC-CORE-016.5 Nothing serving

- **WHEN** a session with no `serve` serves
- **THEN** it keeps running until it is cancelled

#### Scenario: AC-CORE-016.6 A serve that fails

- **WHEN** a peer's `serve` raises
- **THEN** serving raises that error

#### Scenario: AC-CORE-016.7 Close lets a listener finish

- **GIVEN** a listener that takes 0.1 seconds over a message
- **WHEN** `close()` is called straight after the message is said
- **THEN** the listener has the message by the time `close()` returns

#### Scenario: AC-CORE-016.8 Close does not hang

- **GIVEN** a peer whose `answer` never returns
- **WHEN** `close()` is called
- **THEN** it returns within about the close timeout, logs a warning, and whoever waited on that answer gets an error

### Requirement: REQ-CORE-017 Shutdown may be a coroutine

At `close()`, after the deliveries have finished or been cancelled, the session SHALL call `shutdown()` on every peer and command that has one. Coroutines MUST be awaited together, bounded by the close timeout; one that raises is logged without stopping the others; one still running at the deadline is cancelled with a warning. `close()` MUST return in every case.

#### Scenario: AC-CORE-017.1 An asynchronous shutdown

- **WHEN** a peer's `shutdown` is a coroutine and the chat is closed
- **THEN** it has run to the end by the time `close()` returns

#### Scenario: AC-CORE-017.2 A synchronous shutdown

- **WHEN** a peer's `shutdown` is a plain method and the chat is closed
- **THEN** it is called once

#### Scenario: AC-CORE-017.3 One fails

- **GIVEN** two peers with asynchronous shutdowns, the first of which raises
- **WHEN** the chat is closed
- **THEN** the error is logged and the second still runs

#### Scenario: AC-CORE-017.4 One never returns

- **WHEN** a peer's asynchronous `shutdown` never returns and the chat is closed
- **THEN** `close()` returns within about the close timeout and a warning is logged

### Requirement: REQ-CORE-018 A Query says which messages

`Query` SHALL be an immutable, plain-data value whose fields are all optional and combined with AND: `peer` (messages from that peer, addressed to it, or replying to one of its messages), `thread` (a message's reply chain up to the root and every reply to a message in it), `errors` (False leaves out replies with status `error`), `since` (stamped at or after that moment) and `limit` (at most that many, the newest). `Query.last(n)` MUST return a copy with `limit=n`. `SELF` as the peer resolves to whoever asks, and applying it with nobody asking MUST raise `ValueError`.

#### Scenario: AC-CORE-018.1 Last twenty without errors

- **GIVEN** thirty messages, two of them error replies
- **WHEN** `Query(errors=False).last(20)` is applied
- **THEN** it selects the twenty newest of the twenty-eight that are not errors, oldest first

#### Scenario: AC-CORE-018.2 A thread

- **GIVEN** B replies to A, C replies to B, and D is unrelated
- **WHEN** `Query(thread=C.id)` is applied
- **THEN** it selects A, B and C, and not D

#### Scenario: AC-CORE-018.3 A thread includes replies to its chain

- **GIVEN** a message with two replies
- **WHEN** the thread of one reply is selected
- **THEN** the other reply is selected too

#### Scenario: AC-CORE-018.4 A peer and what replies to it

- **WHEN** `Query(peer=p)` is applied
- **THEN** it selects what `p` said, what was addressed to `p` (a routed say included) and the replies to `p`'s messages (an answer with `to` unset included)

#### Scenario: AC-CORE-018.5 SELF is whoever asks

- **GIVEN** a peer that was asked one question and asked a third peer another
- **WHEN** `Query(peer=SELF)` is applied for that peer
- **THEN** it selects that peer's own exchanges

#### Scenario: AC-CORE-018.6 Nobody asking

- **WHEN** `Query(peer=SELF)` is applied without saying who asks
- **THEN** it raises `ValueError`

#### Scenario: AC-CORE-018.7 Since

- **WHEN** `Query(since=t)` is applied
- **THEN** it selects the messages stamped at or after `t`

#### Scenario: AC-CORE-018.8 last makes a copy

- **WHEN** `last(n)` is called on a query
- **THEN** the result has `limit=n` and the original is unchanged

### Requirement: REQ-CORE-019 context returns the conversation

The `context` grant SHALL take one optional `Query` and return a copy of the messages it selects, oldest first, resolving `SELF` to the asking peer; with no query it returns the whole conversation in reach. It MUST NOT accept keywords such as `limit`. The conversation in reach is what was said this session and, before it, what the session loaded at `start()` from the backend that declares `HookLoad`, at most `recall` messages; the caller cannot tell the two apart. A backend that only listens is not an error.

#### Scenario: AC-CORE-019.1 Without a query

- **GIVEN** a conversation of seven messages
- **WHEN** a peer calls `context()`
- **THEN** it gets all seven, oldest first

#### Scenario: AC-CORE-019.2 Narrowed by count and time

- **GIVEN** five messages
- **WHEN** a peer calls `context(Query(limit=2))`, `context(Query(since=t))` and `context(Query(limit=0))`
- **THEN** it gets the two newest, those from `t` on, and none

#### Scenario: AC-CORE-019.3 A keyword is refused

- **WHEN** a peer calls `context(limit=5)`
- **THEN** it raises `TypeError`

#### Scenario: AC-CORE-019.4 A copy

- **WHEN** the list `context()` returned is emptied
- **THEN** the conversation still holds its messages

#### Scenario: AC-CORE-019.5 SELF through the grant

- **WHEN** a peer calls `context(Query(peer=SELF))`
- **THEN** it gets what passed between it and the others

#### Scenario: AC-CORE-019.6 Both tiers, one list

- **GIVEN** a backend that loads one message from yesterday
- **WHEN** a message is said today and `context()` is read
- **THEN** it returns yesterday's, then today's

#### Scenario: AC-CORE-019.7 Recall is bounded

- **GIVEN** a backend holding five messages and a session with `recall=2`
- **WHEN** the session starts
- **THEN** `context()` returns the two newest

#### Scenario: AC-CORE-019.8 A backend that only listens

- **GIVEN** a backend that declares only `HookListen`
- **WHEN** the session starts and a message is said
- **THEN** nothing fails, `context()` holds the message and the backend heard it

### Requirement: REQ-CORE-020 forget drops messages

`ChatSession.forget(before)` SHALL drop from the conversation the messages stamped before `before`, or every message when `before` is `None`, whether or not there is a backend; `context()` MUST NOT return them afterwards. It SHALL ask the backend that declares `HookForget` to drop them too, and return the number that backend reports, or 0 without one.

#### Scenario: AC-CORE-020.1 Without a backend

- **GIVEN** a session without a backend holding two messages
- **WHEN** `forget()` is called
- **THEN** it returns 0 and `context()` returns nothing

#### Scenario: AC-CORE-020.2 With a backend

- **GIVEN** a backend that holds one message
- **WHEN** `forget()` is called
- **THEN** it returns 1 and the backend holds nothing

### Requirement: REQ-CORE-021 Message ids

A message's `id` and `reply_to` SHALL be `MessageID` values, not strings. `str()` of one MUST be `msg-` followed by its hexadecimal characters; `MessageID.parse` reads that text back into an equal id, returns `None` for `None`, and raises `ValueError` for anything that is not `msg-` followed by lowercase hexadecimal characters. A `MessageID` MUST NOT equal a string. A new id has 16 random hexadecimal characters, does not depend on how many messages exist, and is safe to generate from several threads. `short` is the first 7 characters of an id with 16, and the whole text of any other.

#### Scenario: AC-CORE-021.1 The form of a new id

- **WHEN** a new id is made
- **THEN** its text matches `msg-[0-9a-f]{16}`

#### Scenario: AC-CORE-021.2 Unique across threads

- **WHEN** 10,000 ids are made from several threads
- **THEN** all of them are different

#### Scenario: AC-CORE-021.3 Not a string

- **WHEN** an id is compared with a string, its own text included
- **THEN** they are not equal, and `str()` of the id is `msg-` and its hex

#### Scenario: AC-CORE-021.4 Round trip

- **WHEN** `MessageID.parse` reads `str()` of an id
- **THEN** the result equals the id and has the same hash

#### Scenario: AC-CORE-021.5 Not an id

- **WHEN** `MessageID.parse` is given `abc`, `msg-` or `msg-3F9A`
- **THEN** it raises `ValueError`

#### Scenario: AC-CORE-021.6 No id

- **WHEN** `MessageID.parse` is given `None`
- **THEN** it returns `None`

#### Scenario: AC-CORE-021.7 Short

- **WHEN** `short` is read of `msg-3f9a1c2e7b04d5a6` and of `msg-3`
- **THEN** it is `3f9a1c2` and `msg-3`

### Requirement: REQ-CORE-022 The message store

`MessageStore` SHALL keep messages in the order they were added, find one by id (`None` when unknown), list the ids of the replies to a message (empty when unknown or unanswered), and hand out copies of its lists that share the messages themselves. `forget(before)` MUST drop the messages stamped before `before`, or all with no cut, from every index, return how many, and leave a kept reply's `reply_to` as it was.

#### Scenario: AC-CORE-022.1 Add and find

- **WHEN** a message is added
- **THEN** it is in `messages` and `find` returns it; `find` of an unknown id returns `None`

#### Scenario: AC-CORE-022.2 Replies are threaded

- **WHEN** a reply to a stored message is added
- **THEN** `replies` of that message lists the reply's id, and is empty for an unknown or unanswered message

#### Scenario: AC-CORE-022.3 Copies

- **WHEN** the lists `messages` and `replies` return are changed
- **THEN** the store is unchanged, and the messages in a copy are the stored ones

#### Scenario: AC-CORE-022.4 Forget

- **GIVEN** three messages, each replying to the one before
- **WHEN** `forget(before)` drops the two oldest
- **THEN** it returns 2, neither is found any more, and the one kept still has its `reply_to`

#### Scenario: AC-CORE-022.5 Forget everything

- **WHEN** `forget()` is called with no cut
- **THEN** the store is empty

### Requirement: REQ-CORE-023 Attachments go to the keeper

Messages SHALL carry text only. `say` and `ask` take `attachments`, and `answer` and `execute` return them on their `Reply`; in every case the session MUST hand them to the backend that declares `HookKeep`, under the new message's id, before anyone hears the message. An `Attachment` has a name, a media type and content, and cannot be changed after it is made. With no keeper they are dropped and the text posted as usual; a keeper that raises is logged and the text still posted. A command's invocation carries none.

#### Scenario: AC-CORE-023.1 Immutable, and not on the message

- **WHEN** an attachment's field is assigned, and a message's fields are listed
- **THEN** the assignment fails, and a message has no attachments field

#### Scenario: AC-CORE-023.2 Kept before anyone hears

- **GIVEN** a backend that keeps attachments
- **WHEN** a peer says a message with an attachment
- **THEN** the backend has kept it under the new message's id by the time a listener receives the message

#### Scenario: AC-CORE-023.3 Text only

- **WHEN** a peer says a message with attachments
- **THEN** every listener and `context()` get the text and no attachment content

#### Scenario: AC-CORE-023.4 No keeper

- **WHEN** a message with attachments is said in a session with no keeper
- **THEN** the text is posted and the attachments dropped

#### Scenario: AC-CORE-023.5 A keeper that fails

- **WHEN** the keeper raises
- **THEN** the failure is logged and the text is still posted

#### Scenario: AC-CORE-023.6 Under the question

- **WHEN** a peer asks with an attachment
- **THEN** it is kept under the question's id

#### Scenario: AC-CORE-023.7 Under the answer

- **WHEN** a peer's `answer` returns a `Reply` with an attachment, given as a tuple or a list
- **THEN** it is kept under the answer's id and `ask` returns the answer's text; a `Reply` with none keeps nothing

#### Scenario: AC-CORE-023.8 Under a command's result

- **WHEN** a command returns a `Reply` with an attachment
- **THEN** it is kept under the result's id and nothing under the invocation's

### Requirement: REQ-CORE-024 Peers locate attachments

A peer granted `locate(msg_id, name)` SHALL get what the backend that declares `HookLink` returns for that message and name. With no such backend, or when it raises, `locate` MUST return `None`; a failure is logged.

#### Scenario: AC-CORE-024.1 Through the backend

- **WHEN** a peer calls `locate` and the backend has a link for that message and name
- **THEN** `locate` returns the link

#### Scenario: AC-CORE-024.2 No backend

- **WHEN** a peer calls `locate` in a session with no linking backend
- **THEN** it returns `None`

#### Scenario: AC-CORE-024.3 The backend fails

- **WHEN** the backend raises while linking
- **THEN** the failure is logged and `locate` returns `None`

### Requirement: REQ-CORE-025 Credentials ride on the message

`ChatMessage` SHALL carry `credentials`, keys by name wrapped in `Secret`, empty by default. `say` MUST accept `credentials=` and put that very mapping on the message, so whoever lent it can clear it. A peer answering a message finds on it the credentials lent for it, so each message may bring different keys. A `Secret` MUST NOT show its value in `str` or `repr`, and credentials MUST NOT appear in the message's text or `repr`.

#### Scenario: AC-CORE-025.1 A key per message

- **WHEN** a peer answers three messages, the first lent `llm` = `sk-one`, the second `sk-two`, the third nothing
- **THEN** it finds `sk-one`, `sk-two` and no `llm`, in that order

#### Scenario: AC-CORE-025.2 The lender's mapping

- **WHEN** a mapping is passed as `credentials` and cleared after the message was said
- **THEN** the message carries no credential any more

#### Scenario: AC-CORE-025.3 Never shown

- **WHEN** a message carrying a credential, or a `Secret` itself, is printed
- **THEN** the value appears nowhere

### Requirement: REQ-CORE-026 The workspace provider is a role

The session SHALL take one workspace provider as `workspaces`: something that declares `HookProvision`. Like a command it is no peer: it has no id, is in no roster and hears nothing, but it is initialized at `start()`. Something that does not declare `HookProvision` MUST be refused with `TypeError`; a provider arriving as a connector or as a command MUST be refused with `ValueError`.

#### Scenario: AC-CORE-026.1 In no roster

- **WHEN** a session is given a provider
- **THEN** the roster holds only its peers, and the provider's name has no id

#### Scenario: AC-CORE-026.2 Started, and hears nothing

- **WHEN** a session with a provider starts and a message is said
- **THEN** the provider was initialized and is handed no message

#### Scenario: AC-CORE-026.3 A second provider

- **WHEN** a provider is registered as a connector
- **THEN** `ValueError` is raised naming `HookProvision`

#### Scenario: AC-CORE-026.4 Not a command either

- **WHEN** something that declares both `HookExecute` and `HookProvision` is given as a command
- **THEN** `ValueError` is raised

#### Scenario: AC-CORE-026.5 Declares nothing

- **WHEN** an object that does not declare `HookProvision` is given as `workspaces`
- **THEN** `TypeError` is raised naming `HookProvision`

### Requirement: REQ-CORE-027 The workspace grant

A peer granted `workspace(name=None, create=True)` SHALL get its own workspace, writable, with no name or with its own name, and a read-only view of another's with that peer's name. The owner is a name: a peer in the chat has a workspace from the first time anyone asks, and a name that is no peer must be a workspace that already exists, or `KeyError` is raised. With `create=False` nothing is made and a workspace that does not exist yet is a `KeyError`. A command owns none: it MUST name the workspace it reads, or `ValueError` is raised. With no provider the grant MUST raise `NoWorkspaceProvider`.

#### Scenario: AC-CORE-027.1 Its own workspace

- **WHEN** a peer calls `workspace()`, or `workspace` with its own name
- **THEN** it gets a writable workspace named after it

#### Scenario: AC-CORE-027.2 Another peer's is read-only

- **WHEN** a peer calls `workspace` with another peer's name
- **THEN** it gets a view that reads that peer's files and has no `write`, `edit`, `delete` or `commit`

#### Scenario: AC-CORE-027.3 Before its owner asked

- **GIVEN** a peer that never asked for its own workspace
- **WHEN** another peer asks for it by name
- **THEN** it gets a view of a workspace holding the base's files

#### Scenario: AC-CORE-027.4 No provider

- **WHEN** a peer calls `workspace()` in a session with no provider
- **THEN** `NoWorkspaceProvider` is raised

#### Scenario: AC-CORE-027.5 An unknown name

- **WHEN** a peer asks for the workspace of a name that is neither a peer nor an existing workspace
- **THEN** `KeyError` is raised

#### Scenario: AC-CORE-027.6 A workspace that outlived its peer

- **GIVEN** a workspace made for a name that is no longer a peer
- **WHEN** a peer asks for it by name
- **THEN** it gets a read-only view

#### Scenario: AC-CORE-027.7 A command reads a named one

- **WHEN** a command asks for a peer's workspace by name, and asks with no name
- **THEN** the first gives a view, and the second raises `ValueError` saying a command owns no workspace

#### Scenario: AC-CORE-027.8 Asking without creating

- **GIVEN** peers that have not asked for a workspace yet
- **WHEN** one asks with `create=False`, for another's and for its own
- **THEN** both raise `KeyError` and no workspace was made; once the owner has asked, the other gets a view

### Requirement: REQ-CORE-028 Where the public names live

The session, the messages and the hooks SHALL be importable from `chatinho.session`, `chatinho.message` and `chatinho.hooks`, and the package root exports the public API. The former `chatinho.chat_*` modules MUST NOT exist. Importing `chatinho` MUST NOT need any extra. A name that lives behind an extra is resolved when first read off the package, and reading it without its extra installed MUST raise `ImportError` naming the extra: `chatinho[tui]` for `ChatFrontend` and `ChatStyle`, `chatinho[langchain]` for the basic agent connector. The agent connectors are importable from `chatinho.connectors.agents`, and the former `AgentConnector` MUST NOT exist.

#### Scenario: AC-CORE-028.1 The core by its module names

- **WHEN** `ChatSession` is imported from `chatinho.session`
- **THEN** it is the class `chatinho` exports

#### Scenario: AC-CORE-028.2 The old module names

- **WHEN** `chatinho.chat_session` is imported
- **THEN** it fails with `ModuleNotFoundError`

#### Scenario: AC-CORE-028.3 The terminal wherever it is read

- **WHEN** `ChatFrontend` is read from `chatinho`, `chatinho.frontends` and `chatinho.frontends.chat`
- **THEN** it is the same class, and `ChatStyle` lives in `chatinho.frontends.chat`

#### Scenario: AC-CORE-028.4 The core stays light

- **WHEN** `chatinho` is imported in a process where no extra's library can be imported, and `chatinho.connectors` is imported with them installed
- **THEN** the first import succeeds, and the second loads no LangChain module

#### Scenario: AC-CORE-028.5 A name without its extra

- **WHEN** a name behind an extra is read off `chatinho` without that extra's library
- **THEN** `ImportError` is raised naming the extra to install

#### Scenario: AC-CORE-028.6 The workspaces are public

- **WHEN** the workspace names are read off `chatinho`
- **THEN** they are the ones `chatinho.support.parts.workspace` and `chatinho.workspaces` define

#### Scenario: AC-CORE-028.7 The agent connectors

- **WHEN** the basic and deep agent connectors are read off `chatinho` and `chatinho.connectors.agents`
- **THEN** they are the same classes, and `chatinho` has no `AgentConnector`

### Requirement: REQ-CORE-029 One builder per kind of session

`build_chat_session` and `build_mcp_session`, in `chatinho.builder` and exported from `chatinho`, SHALL each return a `ChatSession` whose frontend they built: a `ChatFrontend` or an `McpFrontend`. Both take the session's connectors, commands, backend and workspace provider. `build_mcp_session` MUST refuse a missing token with `ValueError`. Each builder needs both the `tui` and the `mcp` extras, and reading either off `chatinho` without both MUST raise `ImportError` naming `chatinho[tui,mcp]`; each frontend still needs only its own extra.

#### Scenario: AC-CORE-029.1 A chat with a terminal

- **WHEN** `build_chat_session(commands=[HelpCommand()], title="Demo")` is called
- **THEN** it returns a `ChatSession` whose peer zero is a `ChatFrontend` titled `Demo`, with `/help` available

#### Scenario: AC-CORE-029.2 A chat served over MCP

- **WHEN** `build_mcp_session(connectors=[agent], token="t", port=9000)` is called
- **THEN** it returns a `ChatSession` whose peer zero is an `McpFrontend` named `master` on port 9000, with `agent` as a peer

#### Scenario: AC-CORE-029.3 No token

- **WHEN** `build_mcp_session(token="")` is called
- **THEN** it raises `ValueError`

#### Scenario: AC-CORE-029.4 Both extras

- **WHEN** either builder is read off `chatinho` with one of the two libraries missing
- **THEN** `ImportError` is raised naming `chatinho[tui,mcp]`

#### Scenario: AC-CORE-029.5 A frontend needs only its own

- **WHEN** only one frontend's library is installed and that frontend is read off `chatinho`
- **THEN** it is returned

#### Scenario: AC-CORE-029.6 A built session serves workspaces

- **WHEN** either builder is given a workspace provider and a peer that declares `HookWorkspace`
- **THEN** the session's provider is the one given, and the peer gets its workspace

### Requirement: REQ-CORE-030 A peer traces the steps of a message

A peer or command that declares `HookTrace` SHALL be granted `trace(msg_id, state, text, prev=None)`, a coroutine that records one step of processing the message `msg_id` and returns the new trace's id. The trace SHALL hold its own id (unique across sessions, `trc-` and 16 hex characters as text), the message id, the state, the id of the trace it follows (or none), the text, the id of who traced it (`TOOL` for a command) and when. The state MUST be one of `running`, `done` and `error`, given as the state or its name. Text longer than `TRACE_TEXT_LIMIT` (2000 characters) MUST be cut to it, ending with `…`.

#### Scenario: AC-CORE-030.1 A trace is recorded

- **GIVEN** a session with a backend that declares `HookRecord`, and a peer that declares `HookTrace`
- **WHEN** the peer traces message `m` with state `running` and text `extract`
- **THEN** it gets back a trace id, and the backend's `record` is given one trace with that id, message `m`, state `running`, text `extract`, no `prev`, the peer's id as `frm` and a timestamp

#### Scenario: AC-CORE-030.2 One trace follows another

- **WHEN** a peer traces `t1` and then a second trace with `prev=t1`
- **THEN** the second trace recorded has `prev` equal to `t1`

#### Scenario: AC-CORE-030.3 The state by its name

- **WHEN** a peer traces with the state given as `"done"`
- **THEN** the recorded trace's state is `done`

#### Scenario: AC-CORE-030.4 An unknown state

- **WHEN** a peer traces with the state `"finished"`
- **THEN** `trace` raises `ValueError` naming the states it takes, and nothing is recorded

#### Scenario: AC-CORE-030.5 A long text is cut

- **WHEN** a peer traces a text of 5000 characters
- **THEN** the recorded text is `TRACE_TEXT_LIMIT` characters long and ends with `…`

#### Scenario: AC-CORE-030.6 A command traces as TOOL

- **WHEN** a command that declares `HookTrace` traces while it runs
- **THEN** the recorded trace's `frm` is `TOOL`

#### Scenario: AC-CORE-030.7 Not a message id

- **WHEN** a peer traces with a plain string as `msg_id`
- **THEN** `trace` raises `TypeError`, and nothing is recorded

### Requirement: REQ-CORE-031 A trace follows only a trace the session made

`trace` MUST refuse a `prev` that is not the id of a trace this session returned: it raises `ValueError` and records nothing. A trace id read back from elsewhere is not known to the session.

#### Scenario: AC-CORE-031.1 An unknown prev

- **WHEN** a peer traces with `prev` set to a trace id the session never returned
- **THEN** `trace` raises `ValueError`, and nothing is recorded

#### Scenario: AC-CORE-031.2 Another peer's trace

- **GIVEN** peer A traced `t1`
- **WHEN** peer B traces with `prev=t1`
- **THEN** the trace is recorded with `prev` equal to `t1`

### Requirement: REQ-CORE-032 Traces go to the recorder and nowhere else

The session SHALL hand every trace to the first peer that declares `HookRecord`, awaiting its `record` before `trace` returns. With no recorder the trace MUST be dropped and its id still returned. A recorder that raises MUST be logged and the id still returned: a broken store never fails the step being traced. A trace MUST NOT be a message: no peer hears it, nobody answers it, `context()` never returns it, and the message store does not hold it.

#### Scenario: AC-CORE-032.1 No recorder

- **GIVEN** a session where no peer declares `HookRecord`
- **WHEN** a peer traces
- **THEN** it gets back a trace id, and nothing fails

#### Scenario: AC-CORE-032.2 The recorder raises

- **GIVEN** a recorder whose `record` raises
- **WHEN** a peer traces
- **THEN** it gets back a trace id, and the failure is logged as an error

#### Scenario: AC-CORE-032.3 A trace is not heard

- **GIVEN** a peer that declares `HookListen`, and a recorder
- **WHEN** another peer traces a step of a message
- **THEN** the listener hears no trace, and `context()` returns the same messages as before the trace

#### Scenario: AC-CORE-032.4 A recorder is not addressed

- **WHEN** the recorder is also a peer that declares `HookListen`
- **THEN** it hears the messages as before, and receives traces only through `record`

### Requirement: REQ-CORE-033 Trace names are public

`ChatTrace`, `TraceID`, `TraceState`, `TRACE_TEXT_LIMIT`, `HookTrace`, `HookRecord` and the grant protocol `Trace` SHALL be importable from `chatinho` and need no extra. `HookTrace` grants only `trace`, and `HookRecord` demands only `record`.

#### Scenario: AC-CORE-033.1 The names off the package

- **WHEN** the trace names are read off `chatinho` in a process where no extra's library can be imported
- **THEN** each one is found

#### Scenario: AC-CORE-033.2 A recorder without record

- **WHEN** a class without a `record` method declares `HookRecord`
- **THEN** the declaration raises `TypeError` naming `record`
