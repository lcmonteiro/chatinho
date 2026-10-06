# Spec Delta

## Purpose

Lets a peer that needs an LLM ask the chat for a completion on behalf of the message it is answering, so that the intelligence — and the API key paying for it — belongs to whoever asked, not to the peer.

## ADDED Requirements

### Requirement: Sample hook
chatinho SHALL provide `HookSample`, a grant-only hook that gives a peer `sample(msg_id, messages, *, max_tokens=None, system=None) -> str`: a request for a completion of `messages` (a list of `{"role": "user" | "assistant", "content": str}`) on behalf of message `msg_id`. The session MUST route the request to the frontend if the frontend declares `HookServeSample`, a hook demanding `serve_sample(msg_id, messages, max_tokens, system) -> str`; with no frontend serving samples, `sample` MUST raise `SamplingUnavailable`.

#### Scenario: Frontend serves the sample
- **WHEN** a peer declaring `HookSample` calls `sample(msg_id, [{"role": "user", "content": "hi"}])` and the frontend serves samples
- **THEN** the frontend's `serve_sample` is called with that message id and those messages, and its text is returned to the peer

#### Scenario: Nobody serves samples
- **WHEN** a peer calls `sample` in a session whose frontend does not declare `HookServeSample`
- **THEN** `sample` raises `SamplingUnavailable`

#### Scenario: Documented like every hook
- **WHEN** the hook reference in `docs/SPEC.md` is checked against the hooks the package defines
- **THEN** it has a section for `HookSample` and for `HookServeSample`
