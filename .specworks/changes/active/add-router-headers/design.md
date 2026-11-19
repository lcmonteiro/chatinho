# Design: add-router-headers

## Context

See `proposal.md`. `LLMRouter` (`src/chatinho/routers/llm.py`) builds an
`AsyncOpenAI` in two places: `_own_client` (cached per key digest, retired
clients closed at `shutdown`) and `_choose` for a lent key (opened and closed
per say). Both take only `api_key` and `base_url`. The tests swap
`AsyncOpenAI` for `tests/fakes/llm.py`'s `FakeOpenAI`, which records each
client's key and base URL.

## Goals / Non-Goals

**Goals:**
- One keyword, validated once, applied to every client the router builds.

**Non-Goals:**
- Headers on `OpenAIConnector` or `Endpoint`; per-say headers.

## Decisions

### `headers` is a keyword of `LLMRouter.__init__`, sent as `default_headers`

The SDK sends a client's `default_headers` with every request, so passing them
where each client is built covers both key paths in two lines, and the cached
client needs no change to its digest: the headers are fixed for the router's
life. Alternative: a client factory, turned down in refinement. Serves:
REQ-ROUTE-012.

### Validated and copied at build time, `Authorization` refused

`__init__` checks the mapping (a `Mapping`, every name and value a `str`) and
refuses a name equal to `authorization` ignoring case, raising `ValueError`
that names the header and never its value, beside the existing `timeout`
check. It keeps `dict(headers)`, or None for None or an empty mapping, so a
router without headers builds its clients exactly as today
(`default_headers=None`). `Authorization` is refused because the SDK merges
`default_headers` over its own auth header, which would silently replace a lent
key (REQ-ROUTE-010). Serves: REQ-ROUTE-012.

### Values kept out of sight

`__repr__` already shows only `model` and `base_url`, and the warnings name an
error's type, never its message; neither changes. The headers live on a private
attribute, `_headers`, so nothing that prints the router's public fields shows
them. Serves: REQ-ROUTE-012.

## Interfaces

- `src/chatinho/routers/llm.py`: `LLMRouter.__init__(self, endpoint=None, *, memory=ROUTING_MEMORY, timeout=10.0, credential="llm", headers: Optional[Mapping[str, str]] = None)`; raises `ValueError` for malformed headers or `Authorization` (REQ-ROUTE-012)
- `tests/fakes/llm.py`: `FakeOpenAI.__init__` gains `default_headers: Optional[Mapping[str, str]] = None`, recorded as `self.default_headers` (test support, REQ-ROUTE-012)

## Diagrams

No structural change.

## Risks / Trade-offs

- [A header the SDK also sets, such as `User-Agent`, overrides the SDK's] -> allowed, as it is the caller's choice; only `Authorization` is refused.
- [The fake records headers rather than an HTTP request seeing them] -> the SDK's `default_headers` behaviour is its documented contract; one test may build a real `AsyncOpenAI` and read its `default_headers` property to pin it, with no request made.

## Open Questions

None.
