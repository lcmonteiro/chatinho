# Tasks

## 1. Connector

- [x] 1.1 Rewrite `src/chatinho/connectors/openai.py`:
  - the constructor is `OpenAIConnector(name, api_key=None, *, model, temperature, max_tokens, base_url, system, history=20, credential="llm")`;
  - `@require(HookAnswer)`, `@require(HookContext)` and `@require(HookPeers)`, with the grants annotated (`context: Context`, `peers: Peers`);
  - no `initialize()`, no `**kwargs`, no `self.config`.

  Verify that `python -c "from chatinho import OpenAIConnector; OpenAIConnector(name='gpt')"` makes no network call.
- [x] 1.2 Build the messages in a helper:
  - the optional `system` prompt first;
  - then up to `history` earlier messages from `context()`, without the message being answered and without `error` replies, mapped to `assistant` (own id, found via `peers()`), `user` (LOCAL) or `user` with a `name: text` prefix (other peers);
  - then the question last.

  Verify with the unit tests in 2.2.
- [x] 1.3 Choose the key: the lent `msg.credentials[credential]` first, else `api_key`, else return an `error` reply without calling the model. A lent key gets a short-lived `AsyncOpenAI` closed after the call. The configured key gets one lazily created client reused across calls. Both pass `base_url`. Verify with the tests in 2.3.
- [x] 1.4 Call `chat.completions.create` with `model`, `messages`, `temperature` and `max_tokens` (only when set), and return `Reply(content or "")`. Catch `openai.OpenAIError` and transport errors and return `Reply("<name>: could not get an answer (<ErrorClass>)", status=ERROR)`, with no key in the text or the log. Verify with the tests in 2.4.

## 2. Tests (`tests/test_openai_connector.py`, against a stubbed `AsyncOpenAI`)

- [x] 2.1 Non-blocking: with a stub whose `create` awaits an event, another peer's message is delivered before the reply. The reply text is the stub's content, with status `answered`.
- [x] 2.2 Messages:
  - the system prompt comes first;
  - the follow-up scenario gives `user`, `assistant`, `user` in order;
  - another peer is prefixed with its name;
  - `history=0` sends only the question;
  - the question appears exactly once;
  - error replies are left out.
- [x] 2.3 Keys:
  - a lent `llm` is used for that message and the configured key for the next;
  - with no key at all, the reply is an `error` reply naming the credential, and `create` is never called;
  - `base_url` reaches the client.
- [x] 2.4 Failures: an authentication error from the stub becomes an `error` reply naming the connector and the error class, and the key's value appears neither in the reply nor in the captured logs. Starting a session with a key-less connector makes no request.

## 3. Docs

- [x] 3.1 Update `README.md`:
  - the batteries example shows `system=`;
  - a short "OpenAIConnector" paragraph covers `base_url` (compatible endpoints), `history` and `credential`;
  - the BREAKING notes cover `initialize()` and the removed per-call kwargs.

  Update `CLAUDE.md` to describe the connector's hooks and options. Verify that `grep -n "conversation_history\|system_message" README.md CLAUDE.md src` returns only the README's BREAKING note.

## 4. Verification

- [x] 4.1 Run the CI steps locally:
  - `ruff check src tests examples` must be clean;
  - `mypy src/chatinho` must report no issues;
  - `pytest -q` must pass;
  - `openspec validate --all --strict --no-interactive` must pass.
