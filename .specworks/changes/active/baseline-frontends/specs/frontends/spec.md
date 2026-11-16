# Spec Delta: frontends

## Purpose

Who speaks for the person: the terminal, drawn with Textual, and the session served over MCP for clients that ask its peers. It has no living spec yet; this records the behaviour it already has.

## ADDED Requirements

### Requirement: REQ-FRONT-001 The terminal says what the person types

`ChatFrontend` SHALL say what the person submits as the person's own message and return its id; blank input says nothing, and a line that is neither a command nor an ask of a peer is said as typed. A message that arrives from another thread MUST still reach the log.

#### Scenario: AC-FRONT-001.1 Say returns an id and stores

- **WHEN** the terminal says a message
- **THEN** it gets the message's id and the conversation holds it

#### Scenario: AC-FRONT-001.2 Submitting text says it

- **WHEN** text is submitted in the input
- **THEN** it is said

#### Scenario: AC-FRONT-001.3 Blank input says nothing

- **WHEN** blank input is submitted
- **THEN** nothing is said

#### Scenario: AC-FRONT-001.4 Anything else is said as typed

- **WHEN** a line starts with `@` and a name no peer has, or `@name` alone
- **THEN** it is said as typed

#### Scenario: AC-FRONT-001.5 A message from another thread reaches the log

- **WHEN** a message is posted from another thread
- **THEN** the log shows it

### Requirement: REQ-FRONT-002 The terminal asks a peer with @name

A line that starts with `@<name>`, a peer other than the terminal, followed by text SHALL be said addressed to that peer with the text after the name only. A reply typed to an answer MUST be asked of whoever gave that answer.

#### Scenario: AC-FRONT-002.1 An at name asks that peer without the name

- **WHEN** the person types `@sol will it rain?` in a chat with two peers
- **THEN** only `sol` is asked, with `will it rain?`

#### Scenario: AC-FRONT-002.2 A follow up to an answer is asked of whoever answered

- **WHEN** the person replies to a peer's answer
- **THEN** the reply is asked of that peer

### Requirement: REQ-FRONT-003 The terminal does not say its own notices

The terminal SHALL show its welcome text as a banner at the top of the log and its own notices as notifications, never as messages: no peer hears them or is asked them. An unknown command and a command that fails are notices, and the terminal keeps running.

#### Scenario: AC-FRONT-003.1 The welcome message is a banner not a message

- **WHEN** the terminal opens with a welcome text
- **THEN** the text is shown and the conversation is empty

#### Scenario: AC-FRONT-003.2 No welcome no banner

- **WHEN** the terminal opens with no welcome text
- **THEN** there is no banner

#### Scenario: AC-FRONT-003.3 The terminal never puts its own notices to a peer

- **WHEN** the terminal opens with a welcome and an unknown command is run, in a chat with one answering peer
- **THEN** that peer is never asked

#### Scenario: AC-FRONT-003.4 An unknown command is a notice not a message

- **WHEN** the person runs a command that does not exist
- **THEN** the person is notified and no message says so

#### Scenario: AC-FRONT-003.5 An unknown command says so instead of vanishing

- **WHEN** the person submits `/` and a name that is no command
- **THEN** a notification says the command is unknown

#### Scenario: AC-FRONT-003.6 A failing command is a notice and the terminal stays

- **WHEN** the person runs a command whose `execute` raises
- **THEN** the person is notified that it failed and the terminal is still running

### Requirement: REQ-FRONT-004 Commands run from the terminal

A line that starts with `/` and a command's name SHALL run that command with the rest of the line. The invocation and the command's answer are messages in the log, the answer rendered as a reply to the invocation, and what a command says is not the person speaking. `/help` lists what can be run and who can be asked.

#### Scenario: AC-FRONT-004.1 Submitting a slash runs the tool

- **WHEN** `/name args` is submitted
- **THEN** the command runs with those arguments

#### Scenario: AC-FRONT-004.2 Running a command is recorded whole

- **WHEN** a command is run from the terminal
- **THEN** the conversation holds the invocation and the answer

#### Scenario: AC-FRONT-004.3 What a command writes is not the user speaking

- **WHEN** a command says something while it runs
- **THEN** the message is from `TOOL`, not from the person

#### Scenario: AC-FRONT-004.4 A commands answer is rendered as a reply to it

- **WHEN** a command's answer is rendered
- **THEN** it quotes the invocation it answers

#### Scenario: AC-FRONT-004.5 Help lists the tools that can be asked

- **WHEN** `/help` is run
- **THEN** its answer lists the commands and the peers

### Requirement: REQ-FRONT-005 The terminal never waits on others

Whatever the person sends SHALL return to the terminal as soon as it is posted, without waiting for a peer, a command or the router. A running command's invocation is shown while it runs. A question put to the person keeps only its asker waiting, and the person's reply answers it.

#### Scenario: AC-FRONT-005.1 A slow command does not freeze the input

- **WHEN** the person runs a slow command and then sends a message
- **THEN** the message is posted before the command answers

#### Scenario: AC-FRONT-005.2 A slow command shows while it runs

- **WHEN** a slow command is running
- **THEN** its invocation is already in the log

#### Scenario: AC-FRONT-005.3 A slow peer does not freeze the input

- **WHEN** the person asks a slow peer and then says something else
- **THEN** the second message is posted before the answer arrives

#### Scenario: AC-FRONT-005.4 A slow router does not hold the input

- **WHEN** the router is slow to route a say
- **THEN** submitting returns before it has

#### Scenario: AC-FRONT-005.5 A question to the user keeps only its asker waiting

- **WHEN** a peer asks the person and waits
- **THEN** the terminal still sends what the person types

#### Scenario: AC-FRONT-005.6 A connector can ask the user and the reply answers it

- **WHEN** a peer asks the person and the person replies to the question
- **THEN** the peer's ask returns the reply

### Requirement: REQ-FRONT-006 Replying to a message

Selecting a message SHALL make it the reply target: what is typed next replies to it, and with no target replies to nothing. A reply is rendered quoting the message it answers, a long one cut with an ellipsis, and the replies to a message can be read back.

#### Scenario: AC-FRONT-006.1 What is typed replies to the selected target

- **WHEN** a message is selected and text is submitted
- **THEN** the message said replies to the selected one

#### Scenario: AC-FRONT-006.2 Without a target what is typed replies to nothing

- **WHEN** text is submitted with nothing selected
- **THEN** the message said replies to nothing

#### Scenario: AC-FRONT-006.3 Get replies reads the thread back

- **WHEN** the replies to a message are read
- **THEN** they are the messages that reply to it

#### Scenario: AC-FRONT-006.4 A long original is quoted cut with an ellipsis

- **WHEN** a reply to a long message is rendered
- **THEN** the quote is cut and ends with an ellipsis

### Requirement: REQ-FRONT-007 The log renders the conversation

The log SHALL render the messages the session's context holds, only the newest window of them, and measure a bubble's width in terminal cells rather than characters.

#### Scenario: AC-FRONT-007.1 The log renders what the history holds

- **WHEN** the terminal starts on a conversation that already has messages
- **THEN** the log shows them

#### Scenario: AC-FRONT-007.2 Only the window is rendered

- **WHEN** the conversation is longer than the log's window
- **THEN** only the newest window is rendered

#### Scenario: AC-FRONT-007.3 A bubble is measured in cells not characters

- **WHEN** a message holds characters two cells wide
- **THEN** its bubble is measured in cells

### Requirement: REQ-FRONT-008 The terminal shows short ids

Wherever the terminal shows a message id (the header, the reply placeholder, the copy notice) it SHALL show the id's short form, while a reply sent carries the whole id.

#### Scenario: AC-FRONT-008.1 The header shows the short id and not the full one

- **WHEN** a message is rendered
- **THEN** its header shows the short id and not the full one

#### Scenario: AC-FRONT-008.2 The reply placeholder names the short id

- **WHEN** a message is selected as the reply target
- **THEN** the input's placeholder names its short id

#### Scenario: AC-FRONT-008.3 A reply still carries the full id

- **WHEN** a reply is sent to the selected message
- **THEN** its `reply_to` is the whole id

#### Scenario: AC-FRONT-008.4 The copy notice is titled with the short id

- **WHEN** a message is copied
- **THEN** the notice is titled with its short id

### Requirement: REQ-FRONT-009 The terminal's keys are checked when it is built

The quit key SHALL default to Textual's own and, when given, replace it without touching the other bindings. A key a terminal can never send, such as `ctrl+h`, MUST be refused with `ValueError` when the terminal is built, naming which key it was given for; the list of such keys is read from Textual. A single character and a named key are accepted.

#### Scenario: AC-FRONT-009.1 The quit key defaults to textuals own

- **WHEN** no quit key is given
- **THEN** the quit binding is Textual's default

#### Scenario: AC-FRONT-009.2 A given quit key replaces the default rather than joining it

- **WHEN** a quit key is given
- **THEN** it is the only quit binding

#### Scenario: AC-FRONT-009.3 The quit key actually quits and the old one does not

- **WHEN** the given quit key is pressed, and the default one
- **THEN** the first quits and the second does not

#### Scenario: AC-FRONT-009.4 Rebinding quit leaves the other bindings alone

- **WHEN** the quit key is rebound
- **THEN** the other bindings are unchanged

#### Scenario: AC-FRONT-009.5 A quit key textual could never receive is refused

- **WHEN** a quit key that is no key at all is given
- **THEN** building the terminal raises `ValueError`

#### Scenario: AC-FRONT-009.6 A quit key the terminal cannot send is refused

- **WHEN** a quit key a terminal sends as another key is given
- **THEN** building the terminal raises `ValueError`

#### Scenario: AC-FRONT-009.7 The swallowed keys are read from textual not listed here

- **WHEN** the keys a terminal swallows are computed
- **THEN** they are the ones Textual's own key table maps to another key

#### Scenario: AC-FRONT-009.8 A single character and a named key are both accepted

- **WHEN** a single character, or a named key, is given as the quit key
- **THEN** both are accepted

#### Scenario: AC-FRONT-009.9 A bad copy key is named as the copy key

- **WHEN** a bad copy key is given
- **THEN** the error names the copy key

### Requirement: REQ-FRONT-010 The terminal serves until the person quits

`build_chat_session` SHALL return the session with the terminal as its frontend, and the terminal's `serve()` SHALL run until the person quits.

#### Scenario: AC-FRONT-010.1 Build chat returns the session with the terminal attached

- **WHEN** `build_chat_session` is called
- **THEN** it returns a session whose frontend is the terminal

#### Scenario: AC-FRONT-010.2 The terminal serves until the user quits

- **WHEN** the terminal is serving
- **THEN** `serve()` is still running while the terminal is up

### Requirement: REQ-FRONT-011 A bubble is an outline sized to its text

A message SHALL be drawn as a bordered bubble as wide as its widest line, never past the window or under the scrollbar, with no background until it is the reply target, when it alone is filled. Who spoke is marked on the message's container. Around its text a bubble keeps one blank row below, a space under its header, and one blank row before the next message; a line measured to fit does not wrap, and paragraphs stay separated.

#### Scenario: AC-FRONT-011.1 A bubble is as wide as its widest line

- **WHEN** messages of different lengths are rendered
- **THEN** a short message takes a short bubble and a long one stops at the style's maximum bubble width

#### Scenario: AC-FRONT-011.2 A bubble has no background until it is the reply target

- **WHEN** a message is rendered, then selected
- **THEN** it has no background until it is selected

#### Scenario: AC-FRONT-011.3 Selecting a bubble fills it and nothing else

- **WHEN** a message is selected
- **THEN** its bubble is filled and nothing else changes

#### Scenario: AC-FRONT-011.4 Who spoke is on the container whichever side it takes

- **WHEN** messages from the person and from a peer are rendered
- **THEN** each container is marked with who spoke

#### Scenario: AC-FRONT-011.5 A bubble never runs past the window or under the scrollbar

- **WHEN** a long message is rendered in a narrow window
- **THEN** its bubble stays inside the window and clear of the scrollbar

#### Scenario: AC-FRONT-011.6 The bubble clears its header by a space

- **WHEN** a short message is rendered
- **THEN** its bubble is wider than its header by a space

#### Scenario: AC-FRONT-011.7 A line measured to fit does not wrap

- **WHEN** a line as wide as the bubble's measure is rendered
- **THEN** it stays on one row

#### Scenario: AC-FRONT-011.8 There is one blank row under the text not two

- **WHEN** a one-line message is rendered
- **THEN** there is one blank row under its text

#### Scenario: AC-FRONT-011.9 Paragraphs are still separated from each other

- **WHEN** a message with two paragraphs is rendered
- **THEN** a blank row separates them

#### Scenario: AC-FRONT-011.10 One blank row separates one message from the next

- **WHEN** two messages are rendered
- **THEN** one blank row separates them

### Requirement: REQ-FRONT-012 The input takes more than one line

Enter SHALL send; a newline key (`ctrl+j` among them, which needs no enhanced keyboard protocol) or the escape character typed before Enter opens a line instead. The escape is a space by default, is consumed, is looked for at the cursor so a message that really ends in it can still be sent, can be changed or turned off, and one that could never fire MUST be refused. The input grows with its lines up to a maximum, and Up moves the cursor when no suggestion is open.

#### Scenario: AC-FRONT-012.1 A newline key opens a line and enter sends both

- **WHEN** a newline key is pressed between two lines and Enter after
- **THEN** one message with both lines is sent

#### Scenario: AC-FRONT-012.2 A space before enter opens a line and is consumed

- **WHEN** a space is typed before Enter
- **THEN** a line is opened and the space is removed

#### Scenario: AC-FRONT-012.3 A message that really ends in the escape can still be sent

- **WHEN** the cursor is moved off the end of a line that ends in the escape and Enter is pressed
- **THEN** the message is sent

#### Scenario: AC-FRONT-012.4 The escape is configurable and can be turned off

- **WHEN** another escape character, or `None`, is given
- **THEN** the given character opens a line, and with `None` nothing does

#### Scenario: AC-FRONT-012.5 An escape that could never fire is refused

- **WHEN** an escape that is not a single character, or is a newline, is given
- **THEN** it raises `ValueError`

#### Scenario: AC-FRONT-012.6 At least one newline key arrives without the enhanced protocol

- **WHEN** the newline keys are listed
- **THEN** at least one of them is sent by a terminal without the enhanced keyboard protocol

#### Scenario: AC-FRONT-012.7 The input grows with the lines up to its maximum

- **WHEN** lines are added to the input
- **THEN** it grows with them up to its maximum height

#### Scenario: AC-FRONT-012.8 Up moves the cursor when no suggestion is open

- **WHEN** Up is pressed in a multi-line input with no suggestions open
- **THEN** the cursor moves up a line

### Requirement: REQ-FRONT-013 Each peer has its own colour

A message's header SHALL sit above its bubble, outside it, in the colour the palette gives that peer's id, and the bubble's border is that colour too. A command has no peer slot, the palette wraps round when there are more peers than colours, and a palette with no colours MUST be refused. A bubble is never narrower than its header.

#### Scenario: AC-FRONT-013.1 Each peer gets its own header colour

- **WHEN** messages from two peers are rendered
- **THEN** their headers have different colours

#### Scenario: AC-FRONT-013.2 A command is not given a peer slot

- **WHEN** a command's message is rendered
- **THEN** it uses the tool colour, not a peer's

#### Scenario: AC-FRONT-013.3 The palette wraps round rather than running out

- **WHEN** there are more peers than colours
- **THEN** the colours wrap round

#### Scenario: AC-FRONT-013.4 A palette with no colours is refused

- **WHEN** a style is made with an empty palette
- **THEN** it raises `ValueError`

#### Scenario: AC-FRONT-013.5 The header is above the bubble and outside it

- **WHEN** a message is rendered
- **THEN** its header is above its bubble and not inside it

#### Scenario: AC-FRONT-013.6 The bubble border is the headers colour

- **WHEN** a message is rendered
- **THEN** its bubble's border is its header's colour

#### Scenario: AC-FRONT-013.7 A bubble is never narrower than the header above it

- **WHEN** a very short message is rendered
- **THEN** its bubble is at least as wide as its header

### Requirement: REQ-FRONT-014 The scrollbars wear the palette

The log's scrollbar and the input's SHALL take their colours and width from the style: one cell wide by default, a width below one refused when the style is made, a track that shows the chat's background until the pointer reaches for it, and both bars in the same column against the edge.

#### Scenario: AC-FRONT-014.1 The scrollbar wears the palette too

- **WHEN** the log is rendered
- **THEN** its scrollbar has the style's colours

#### Scenario: AC-FRONT-014.2 The scrollbar is one cell wide

- **WHEN** the log is rendered with the default style
- **THEN** its scrollbar reserves one cell

#### Scenario: AC-FRONT-014.3 The scrollbar width is a style field

- **WHEN** a style with another scrollbar width is used
- **THEN** the scrollbar reserves that width

#### Scenario: AC-FRONT-014.4 A scrollbar with no width is refused at construction

- **WHEN** a style is made with a scrollbar width below one
- **THEN** it raises `ValueError`

#### Scenario: AC-FRONT-014.5 The track is the chat behind it until you reach for it

- **WHEN** the scrollbar is at rest, and then under the pointer
- **THEN** its track is the chat's background at rest and the track colour under the pointer

#### Scenario: AC-FRONT-014.6 A transparent track follows the chat background

- **WHEN** the chat's background is recoloured
- **THEN** the track at rest follows it

#### Scenario: AC-FRONT-014.7 The input scrollbar wears the same palette as the log

- **WHEN** the input scrolls
- **THEN** its scrollbar has the style's colours and width

#### Scenario: AC-FRONT-014.8 Both scrollbars line up against the edge

- **WHEN** the log and the input both show a scrollbar
- **THEN** both are in the last column

### Requirement: REQ-FRONT-015 One tap selects a message, two copy it

A tap on a message SHALL select it as the reply target, and a second tap within a short time and a cell of the first copies it, without relying on Textual's own double-click count. A press that travelled, or that left text selected, is not a tap.

#### Scenario: AC-FRONT-015.1 One tap still selects the reply target

- **WHEN** a message is tapped once
- **THEN** it becomes the reply target

#### Scenario: AC-FRONT-015.2 Two taps copy the message

- **WHEN** a message is tapped twice
- **THEN** its text is copied

#### Scenario: AC-FRONT-015.3 Two taps far apart in time are two taps

- **WHEN** a message is tapped twice with a long pause between
- **THEN** nothing is copied

#### Scenario: AC-FRONT-015.4 The double tap does not use textuals chain count

- **WHEN** the tap handler and its thresholds are read
- **THEN** the handler does not use Textual's click chain, and it allows a longer pause than Textual's double click and a cell of travel

#### Scenario: AC-FRONT-015.5 A press that travelled down is not a tap

- **WHEN** the pointer is released several rows from where it was pressed
- **THEN** nothing is selected

#### Scenario: AC-FRONT-015.6 A tap that barely moves is still a tap

- **WHEN** the pointer is released a cell from where it was pressed
- **THEN** the message is selected

#### Scenario: AC-FRONT-015.7 Selecting sideways does not retarget the reply

- **WHEN** the pointer is dragged along a line of text
- **THEN** the reply target does not change

#### Scenario: AC-FRONT-015.8 Selecting one character is not a tap either

- **WHEN** a drag selects a single character
- **THEN** the reply target does not change

#### Scenario: AC-FRONT-015.9 A tap that selects nothing still taps

- **WHEN** a tap leaves no text selected
- **THEN** the message is selected

### Requirement: REQ-FRONT-016 A drag selects text, or pans the log

A drag that starts on text SHALL select it while the log holds still, and a drag that starts on the background pans the log.

#### Scenario: AC-FRONT-016.1 Dragging across text selects it and the log holds still

- **WHEN** the pointer is dragged across a message's text
- **THEN** the text is selected and the log does not scroll

#### Scenario: AC-FRONT-016.2 Dragging the background still pans the log

- **WHEN** the pointer is dragged from the background
- **THEN** the log scrolls

### Requirement: REQ-FRONT-017 The input is ruled off

The input SHALL be framed by a rule above and one below, with open sides, in neutral colours that brighten while it has focus; a boxed frame is available, and a frame that is neither MUST be refused when the style is made.

#### Scenario: AC-FRONT-017.1 The input is ruled off above and below with open sides

- **WHEN** the input is rendered with the default style
- **THEN** it has a rule above and below and none at the sides

#### Scenario: AC-FRONT-017.2 The rules brighten while the input has focus

- **WHEN** the input gains and loses focus
- **THEN** its rules are brighter while it has focus

#### Scenario: AC-FRONT-017.3 The input rules carry no hue of their own

- **WHEN** the default style's rule colours are read
- **THEN** neither has a hue

#### Scenario: AC-FRONT-017.4 The box is still there for whoever prefers it

- **WHEN** the style's frame is `box`
- **THEN** the input has a border on every side

#### Scenario: AC-FRONT-017.5 A frame that is neither shape is refused at construction

- **WHEN** a style is made with another frame
- **THEN** it raises `ValueError`

### Requirement: REQ-FRONT-018 A newline typed is a newline shown

A message typed over several lines SHALL be shown over the same lines in its bubble: a lone newline is a line break, while a fenced block still renders as code.

#### Scenario: AC-FRONT-018.1 The chat parser turns a soft break into a hard one

- **WHEN** the chat's Markdown parser reads text with a lone newline
- **THEN** it yields a hard break

#### Scenario: AC-FRONT-018.2 The parser leaves a fenced block alone

- **WHEN** the parser reads a fenced block
- **THEN** the block is unchanged

#### Scenario: AC-FRONT-018.3 A message typed over three lines is three lines in the bubble

- **WHEN** a message of three short lines is rendered
- **THEN** its bubble shows three lines

#### Scenario: AC-FRONT-018.4 The enters reach the bubble from the keyboard

- **WHEN** three lines are typed with the newline key and sent
- **THEN** the bubble shows three lines

#### Scenario: AC-FRONT-018.5 A fenced block still renders as code in a bubble

- **WHEN** a message with a fenced block is rendered
- **THEN** it renders as code

### Requirement: REQ-FRONT-019 The header names who spoke

A message's header SHALL name its speaker as `@name`, a peer that is gone by its number. The terminal's own name can be given, defaults to its class's, and a blank one MUST be refused. A header stays inside a narrow terminal and hugs the same edge as its bubble.

#### Scenario: AC-FRONT-019.1 The header names the peer with an at and no brackets

- **WHEN** a peer's message is rendered
- **THEN** its header names the peer as `@name`

#### Scenario: AC-FRONT-019.2 A peer that is gone is named by its number

- **WHEN** a message from a peer no longer in the chat is rendered
- **THEN** its header names the peer's number

#### Scenario: AC-FRONT-019.3 The terminal can be named something you would call yourself

- **WHEN** the terminal is built with a name
- **THEN** the person's messages carry that name

#### Scenario: AC-FRONT-019.4 Naming the terminal is optional and defaults to the class

- **WHEN** the terminal is built with no name
- **THEN** it has its class's name

#### Scenario: AC-FRONT-019.5 A blank terminal name is refused

- **WHEN** the terminal is built with a blank name
- **THEN** it raises `ValueError`

#### Scenario: AC-FRONT-019.6 Naming an instance works only because the decorator shadows the property

- **WHEN** a name is assigned to an instance of a plain Textual app, and the terminal's class is read
- **THEN** the first raises `AttributeError`, and the terminal's class carries the name its decorator gave it

#### Scenario: AC-FRONT-019.7 The header stays inside a phone width terminal

- **WHEN** a message is rendered at 40, 50 and 60 columns
- **THEN** its header's text is inside the window

#### Scenario: AC-FRONT-019.8 A header hugs the same edge its bubble does

- **WHEN** the person's message is rendered on the right
- **THEN** its header's text ends at the bubble's edge

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

- **WHEN** the helper exits with an error
- **THEN** the failure is logged and nothing is raised

#### Scenario: AC-FRONT-020.12 Put really runs the helper

- **WHEN** text is copied with a real helper on `PATH`
- **THEN** the helper ran and received the text

#### Scenario: AC-FRONT-020.13 The app really reaches the clipboard

- **WHEN** the terminal copies a message with a real helper on `PATH`
- **THEN** the helper received the message's text

### Requirement: REQ-FRONT-021 Where the chat sits

The chat SHALL be centred and capped at a maximum width on a wide terminal and take all of a narrow one, with the input at the bottom of that body. The person's messages are on the right by default; `local_align="left"` puts everyone in one column, and a value that is neither side MUST be refused.

#### Scenario: AC-FRONT-021.1 The chat is centred and capped on a wide terminal

- **WHEN** the terminal is wider than the chat's maximum
- **THEN** the chat is centred at that width

#### Scenario: AC-FRONT-021.2 A narrow terminal gives the chat all of it

- **WHEN** the terminal is narrower than the maximum
- **THEN** the chat takes the whole width

#### Scenario: AC-FRONT-021.3 The input is still at the bottom of the centred body

- **WHEN** the chat is centred
- **THEN** the input is at the bottom of the centred body

#### Scenario: AC-FRONT-021.4 Your own messages are on the right by default

- **WHEN** the person's and a peer's messages are rendered
- **THEN** the person's are on the right and the peer's on the left

#### Scenario: AC-FRONT-021.5 Local align left puts everyone in one column

- **WHEN** the style's `local_align` is `left`
- **THEN** everyone's messages are on the left

#### Scenario: AC-FRONT-021.6 A local align that is not a side is refused

- **WHEN** a style is made with another `local_align`
- **THEN** it raises `ValueError`

### Requirement: REQ-FRONT-022 The terminal opens attachment links

Activating a relative link in a message SHALL ask `locate` for that message and name and open what it returns, or say "Not found" when it returns nothing or there is no backend. An absolute link opens without asking.

#### Scenario: AC-FRONT-022.1 An attachment link opens where the backend says

- **WHEN** a relative link is activated and the backend has the attachment
- **THEN** what the backend returned is opened

#### Scenario: AC-FRONT-022.2 An attachment the backend does not have is not found

- **WHEN** a relative link is activated and the backend has no such attachment
- **THEN** nothing is opened and the person is told it was not found

#### Scenario: AC-FRONT-022.3 Without a backend an attachment link is not found

- **WHEN** a relative link is activated in a chat with no backend
- **THEN** the person is told it was not found

#### Scenario: AC-FRONT-022.4 An absolute link opens without asking the backend

- **WHEN** an absolute link is activated
- **THEN** it opens and `locate` is not called

### Requirement: REQ-FRONT-023 Command suggestions

Typing `/` at the start of the input SHALL list the session's commands, filtered by what is typed after it, and hide the list when nothing matches or a space follows the name. Tab, or Enter, completes the highlighted suggestion instead of submitting; Down moves the highlight; Escape hides the list without changing the input. With no suggestions Tab moves focus as usual, and with no commands there is no list.

#### Scenario: AC-FRONT-023.1 No suggestions without registered commands

- **WHEN** `/` is typed in a chat with no commands
- **THEN** no list appears

#### Scenario: AC-FRONT-023.2 Slash alone lists all commands

- **WHEN** `/` is typed
- **THEN** every command is listed

#### Scenario: AC-FRONT-023.3 Typing filters suggestions by prefix

- **WHEN** letters are typed after `/`
- **THEN** only the commands that start with them are listed

#### Scenario: AC-FRONT-023.4 No match hides suggestions

- **WHEN** what is typed matches no command
- **THEN** the list is hidden

#### Scenario: AC-FRONT-023.5 Space after token hides suggestions

- **WHEN** a space is typed after the command's name
- **THEN** the list is hidden

#### Scenario: AC-FRONT-023.6 Tab completes highlighted suggestion

- **WHEN** Tab is pressed with the list open
- **THEN** the input holds the highlighted command

#### Scenario: AC-FRONT-023.7 Down moves highlight then tab completes it

- **WHEN** Down and then Tab are pressed
- **THEN** the input holds the second command

#### Scenario: AC-FRONT-023.8 Enter accepts suggestion instead of submitting

- **WHEN** Enter is pressed with the list open
- **THEN** the suggestion is accepted and nothing is submitted

#### Scenario: AC-FRONT-023.9 Escape hides suggestions without changing input

- **WHEN** Escape is pressed with the list open
- **THEN** the list is hidden and the input unchanged

#### Scenario: AC-FRONT-023.10 Tab falls through to focus next without suggestions

- **WHEN** Tab is pressed with no list open
- **THEN** focus moves to the next widget

### Requirement: REQ-FRONT-024 McpFrontend serves the session over MCP

`McpFrontend` SHALL be a frontend that serves the session over MCP, named `master` unless another name is given, exposing exactly the tools `ask`, `peers`, `tools` and `invoke`. It MUST be created with a bearer token, which may be a key source read when the frontend is created, and MUST refuse every HTTP request without it. It does not declare `HookAnswer`, so no peer can ask it.

#### Scenario: AC-FRONT-024.1 Named master by default

- **WHEN** a session is created with `McpFrontend(token=...)` and no name
- **THEN** the frontend is `master` in the session

#### Scenario: AC-FRONT-024.2 A token is required

- **WHEN** an `McpFrontend` is created without a token
- **THEN** it is refused

#### Scenario: AC-FRONT-024.3 What a terminal can do

- **WHEN** a client lists the server's tools
- **THEN** they are `ask`, `peers`, `tools` and `invoke`

#### Scenario: AC-FRONT-024.4 The frontend is never asked

- **WHEN** the frontend's hooks are read
- **THEN** it does not declare `HookAnswer`

#### Scenario: AC-FRONT-024.5 Http refuses requests without the token and serves those with it

- **WHEN** HTTP requests reach the server without the token, and with it
- **THEN** the first are refused and the second served

#### Scenario: AC-FRONT-024.6 Tokens from key sources

- **WHEN** the frontend is created with `token=Env(...)` and the variable set
- **THEN** requests carrying the variable's value are let in

#### Scenario: AC-FRONT-024.7 A missing token fails at startup

- **WHEN** the frontend is created with a key source that cannot be read
- **THEN** creating it raises the source's error

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

#### Scenario: AC-FRONT-025.6 Ask a peer that fails

- **WHEN** the asked peer answers with status `error`, or raises
- **THEN** the result is a tool error

#### Scenario: AC-FRONT-025.7 Ask who cannot answer

- **WHEN** a client asks a name no peer has, or a peer that does not answer
- **THEN** the result is a tool error

#### Scenario: AC-FRONT-025.8 Attachments come back

- **WHEN** the answering peer attaches a file
- **THEN** the result carries its name, media type and content

### Requirement: REQ-FRONT-026 The MCP frontend speaks for every client

The frontend SHALL handle every client itself, adding no peer per client: each question is said as its own message addressed to the asked peer, and that peer's reply goes back on that call alone. Another peer's reply to the question MUST NOT end the call. When the question can no longer be found in the conversation, the first reply to it ends the call.

#### Scenario: AC-FRONT-026.1 The reply goes back to its client

- **WHEN** a client asks a peer
- **THEN** the peer's reply is that call's result

#### Scenario: AC-FRONT-026.2 Two clients at once

- **WHEN** two clients each ask while the other's question still waits
- **THEN** each gets the reply to its own question, and no peer was added

#### Scenario: AC-FRONT-026.3 Another peers reply does not end the call

- **WHEN** a bystander replies to the question before the asked peer
- **THEN** the result is the asked peer's answer

#### Scenario: AC-FRONT-026.4 A forgotten question still takes the first reply

- **WHEN** the question is forgotten while its call is open, and a reply to it arrives
- **THEN** the call ends with that reply

### Requirement: REQ-FRONT-027 The roster and the tools over MCP

`peers()` SHALL list every peer but the frontend, each with its name and whether it answers; `tools()` the session's commands with their descriptions; and `invoke(name, args)` SHALL run a command and return what it answered. An unknown command MUST yield a tool error.

#### Scenario: AC-FRONT-027.1 Peers

- **WHEN** a client calls `peers`
- **THEN** it lists each peer but the frontend, and whether it answers

#### Scenario: AC-FRONT-027.2 Tools

- **WHEN** a client calls `tools`
- **THEN** it lists the commands with their descriptions

#### Scenario: AC-FRONT-027.3 Invoke a tool

- **WHEN** a client invokes a command
- **THEN** the result is `answered` with what it answered

#### Scenario: AC-FRONT-027.4 Invoke a tool that does not exist

- **WHEN** a client invokes a name that is no command
- **THEN** the result is a tool error

### Requirement: REQ-FRONT-028 Credentials lent to the MCP server

The frontend SHALL accept the names of the credentials its peers may use and announce them to clients at discovery. A credential a client lends with a question rides on that question's message only, reaches the peer that answers it, and is cleared when the result is returned or the client gives up; one the server did not declare is ignored. A lent credential MUST NOT appear in the conversation.

#### Scenario: AC-FRONT-028.1 Declared at discovery

- **WHEN** a server declaring `llm` is discovered by a client
- **THEN** the client sees `llm` and its description

#### Scenario: AC-FRONT-028.2 Ask lends credentials

- **WHEN** a client asks with a credential the server declared
- **THEN** the answering peer finds it on the message

#### Scenario: AC-FRONT-028.3 A lent credential reaches the peer and undeclared ones do not

- **WHEN** a client lends a declared credential and an undeclared one
- **THEN** the peer finds the first and not the second

#### Scenario: AC-FRONT-028.4 Each message brings its own key

- **WHEN** two questions are asked with different keys
- **THEN** each message carries its own

#### Scenario: AC-FRONT-028.5 A credential is gone after the reply

- **WHEN** a question that came with a credential has been answered
- **THEN** its message carries no credential any more

#### Scenario: AC-FRONT-028.6 A credential is gone when the client gives up

- **WHEN** a client ends a call that came with a credential before any reply
- **THEN** the credential is discarded then

#### Scenario: AC-FRONT-028.7 A credential is never in the conversation

- **WHEN** the conversation is read after a question with a lent credential
- **THEN** the credential's value appears nowhere
