# Review: add-observer-server

Base: `origin/main`

## Findings

<!-- One line per drift between code, spec and design (API), from `specworks review` and from
reading the diff. `- [ ] R<n>` while open, `- [x] R<n>` once resolved. Write
"None." when there are no findings. -->

- [ ] R1 **quality** The page passes the admin key as ?key= on the stream (REQ-HIVE-007), and chatinho-hive serve runs uvicorn with its access log on, which writes the whole query string: every opened stream puts the admin key in the server's log (src/chatinho/hive/cli.py:106)
  - **Proposal**: back to code: run uvicorn with an access-log filter that replaces the key query value with *** (keep the access log otherwise), and add a test that the served log never holds the key
  - **Decision**: back to code: run uvicorn with an access-log filter that replaces the key query value with *** (keep the access log otherwise), and add a test that the served log never holds the key
  - done in code: create_app adds a filter to uvicorn.access that writes ?key= as ?key=***; test_the_access_log_never_holds_a_key_from_the_query serves the hive, opens a stream with a key and reads the log (it fails with the filter off)
- [ ] R2 **tag** src/chatinho/backends/__init__.py now imports DatabaseBackend lazily, which is what lets HiveBackend import with no SQLAlchemy (AC-BACK-009.6), but its __getattr__ carries no @req (src/chatinho/backends/__init__.py:24)
  - **Proposal**: back to code: tag the lazy __getattr__ with @req REQ-BACK-009
  - **Decision**: back to code: tag the lazy __getattr__ with @req REQ-BACK-009
  - done in code: backends/__init__.py __getattr__ tagged @req REQ-BACK-009
- [x] R3 **test-gap** AC-HIVE-008.2's browser test skips wherever Playwright and a matching Chromium are missing, which is CI and the dev extra: it never runs in the suite; it was run by hand here against the preinstalled Chromium, with screenshots at desktop and phone width (tests/hive/test_hive_page.py:46)
  - **Proposal**: accepted: CI has no browser, adding Playwright and a browser download to chatinho[dev] is heavy, and the page was checked by hand at both widths
  - **Decision**: accepted: CI has no browser and Playwright with a Chromium download is too heavy for chatinho[dev]; the test runs wherever a browser is available, and the page was checked by hand at desktop and phone width
- [ ] R4 **design-gap** design.md Interfaces drifted from the code: HiveCache takes (path, url, limit) not (path, url); the memory outbox is a class MemoryOutbox; Store also has has_message and has_chat, and NameTaken and Caller; the CLI also runs as python -m chatinho.hive.cli (src/chatinho/backends/hive_cache.py:92, src/chatinho/hive/store.py:27)
  - **Proposal**: back to design only: bring the Interfaces entries for hive_cache.py and store.py in line with the code
  - **Decision**: back to design only: bring the Interfaces entries for hive_cache.py and store.py in line with the code
  - done in design: Interfaces now name HiveCache(path, url, limit) and its methods, MemoryOutbox and Item, Store's NameTaken, Caller, has_chat, has_message and close, Live's unsubscribe and events, and python -m chatinho.hive.cli

## Changed files without tags

<!-- Every file `specworks review` lists under untracedSource/untracedTests,
with why it needs no tag (config, refactor, helper of REQ-...) or the
finding that covers it. -->

- `src/chatinho/backends/__init__.py`: R2
- `tests/fakes/hive.py`: a helper of the hive and HiveBackend tests (REQ-BACK-009 to REQ-BACK-013, REQ-HIVE-001 to REQ-HIVE-010): a real hive made with its own commands and served on a free port; no criterion of its own
- `tests/test_examples.py`: the reference example's hook count, seventeen to nineteen, follows REQ-CORE-033; no criterion of its own

## Summary

The suite passes (956, the browser test skipped). Four findings, none against the specs: the admin
key leaks into uvicorn's access log through the stream's `?key=` (R1), a missing tag (R2), a browser
test that only runs where Playwright does (R3), and Interfaces entries that drifted (R4).
