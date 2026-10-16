# Design

## Context

`_post` decides who is put to a message's `answer` from `msg.to` alone, minus the asker of a still-waiting `ask`. An answer is posted with `to` set to whoever asked, so any answer that nothing awaits — the reply to a `say(to=...)`, or to a say addressed to the lone answering peer — is put to the asker's `answer`. A say with `reply_to` set and no `to` is always a broadcast. See proposal.md (Why) for the three failures this causes; the requirements are in the two delta specs.

Callers that matter: `ChatFrontend` sends a tapped reply as `say(text, to=None, reply_to=target)`; `McpFrontend` asks with `say(text, to=peer)` and collects the answer in `listen`; `AgentConnector.listen` and the echo examples reply to the *user's* message with `say(..., reply_to=msg.id)`.

## Goals / Non-Goals

**Goals:**
- Whether a message reaches `answer` is decided by what the message is, not inferred from `to` and `reply_to`.
- No change to `ChatMessage`, to the archive, or to any grant's signature.

**Non-Goals:**
- Changing how the lone answering peer is chosen, or what `msg.is_broadcast` means to listeners (review item R4).
- Routing a reply to the frontend or to `TOOL` by inference.

## Decisions

### 1. An answer is marked where it is made, not recognised by its shape

`_post` takes a keyword `answer: bool = False`. When true, the message is stored, resolves a waiting `ask` as today, and is heard by listeners, but its `to` gets no delivery as a question. The session passes `answer=True` from the three places that post in a peer's name: `_answered` (what `answer` returned, and the "too many nested asks" reply) and the error reply in `_deliver`.

**Alternative rejected: infer it from the message.** "A reply to a message addressed to its speaker is an answer" looks sufficient and is what the review first sketched, but it cannot tell the user's follow-up from the bot's answer to it: the user replying to the bot's answer (addressed to the user) and the bot answering that follow-up (addressed to the bot) have the same shape. Either the follow-up is lost or the ping-pong returns one level down. Only the place the message was made knows which it is.

**Alternative rejected: a field on `ChatMessage`.** It would make the distinction visible to listeners and the archive, which do not need it, and every place that builds a message would have to set it. `status` already says how an answer describes itself; this is about delivery, which is the session's business.

### 2. A reply is routed to the replied message's author in `say`, at the same point as the lone-answerer rule

In `_say_for`, when `to` is None and the speaker is not `TOOL`:
- `reply_to` is None → the lone answering peer, as today;
- otherwise → the author of `self._store.find(reply_to)`, if it is in `_connectors`, is not the speaker and not `LOCAL`, and declares `HookAnswer`; else None.

The two rules share the exclusions (speaker, frontend, commands), so they live together. A helper `_answerer_of(frm, reply_to)` covers both and replaces `_only_answerer` at the call site.

A reply to a message no longer in the store (older than `recall`) stays a broadcast. That is the same window `context()` already has.

### 3. The depth limit keeps its drop clause, for replies said from `answer`

The traded-answers loop is gone, but a peer that answers by *saying* a reply from inside `answer` (instead of returning one) can still set up a chain, because that say is not an answer under decision 1. The existing branch in `_deliver` that drops a reply past the limit already covers it; only the spec wording and its test change.

## Risks / Trade-offs

- [A peer that said `say(to=x)` and read the reply in its own `answer` no longer gets it there] → It hears it in `listen` if it declares `HookListen`, as `McpFrontend` already does. No peer in the library or the examples relies on the old path; the proposal marks it BREAKING.
- [A reply to a peer's answer now costs that peer an `answer` call] → That is the point of the change, and it is bounded by the existing depth limit. A peer that should not be followed up on can simply not declare `HookAnswer`.
- [Late answers said with `say(reply_to=question)` are now routed to the question's author] → That is correct for a question a peer put to the user with `say(to=LOCAL)`; for a question that came from the user, the author is the frontend, which is excluded, so it stays a broadcast as today.

## Migration Plan

Single change in `session.py` with its tests. Rollback is reverting that commit. Docs (`docs/SPEC.md`, CLAUDE.md's routing table) are updated in the same change so the fitness tests and the spec agree.
