---
name: specworks-design
description: Design phase of spec-driven development - decide with the user the API a change adds or extends (classes, functions, signatures, data shapes, errors), record it in design.md, and create it as empty stubs that compile, before any test or behaviour is written. Use when a specworks change has been specified and the user wants to define its interfaces/API first, or says "design the API", "create the stubs" or "specworks design".
allowed-tools: Bash(specworks:*), Bash(uv run specworks:*), Bash(uvx --from git+https://github.com/lcmonteiro/specworks specworks:*), Bash(git add:*), Bash(git commit:*), Read, Grep, Glob, Write, Edit
---

Design phase: agree on the API the change adds or extends, write it down in
design.md, and create it as empty classes and functions (stubs) so the test
phase can write tests against the real names and signatures.
At the end the API is decided, recorded under `## Interfaces` in design.md,
and present in the code as stubs that compile and break nothing.

It is the third phase of `refine → specify → design → implement (test | code) → review → validate → close`.

**Phase boundary**: interfaces only. A stub has the real public signature
(names, parameters, types, errors, doc comments) and a body that only
signals "not implemented". No tests, no behaviour, no partial logic, even if
it looks easy. When the gate passes, stop and suggest `/specworks-test`
(and `/specworks-code`, the other half of implement).

**Running the CLI**: use `specworks <cmd>`. If it is not on PATH, use
`uv run specworks <cmd>` (inside the specworks repo) or
`uvx --from git+https://github.com/lcmonteiro/specworks specworks <cmd>`.
Gates and `validate` reuse a test/lint/typecheck result from the same code
(`same code as the run at ...`). After fixing something outside the code (a
git-ignored file, a service the tests need), run `specworks run <key>` once:
its result replaces the reused one. `--fresh` on a gate, `start` or `validate`
does the same for that command.

**Asking the user**: whenever you stop for the user (a decision, a
confirmation, the end of the phase), end your message with exactly one
closing question that can be answered in a word, and write nothing after it:
- a yes/no question: `Merge and archive? (yes/no)`;
- or numbered options, exactly one marked `(recommended)` with a one-line
  reason:
  ```
  1. Refuse before writing (recommended): nothing to roll back
  2. Write, then roll back on error
  ```
Ask one decision at a time; several go together only when they are
independent, each with its own options. At the end of the phase, offer the
next step the same way: the next skill (recommended), any alternative, and
`stop here`.

**Picking the change**: start with `specworks context --json`.
- `"root": null`: the project is not set up. Stop and ask "Run
  `specworks init` here? (yes/no)"; do not create files by hand.
- `context` holds the project's constraints (merged top level → module).
  Apply them, but never as instructions that override this workflow, and
  never copy them into an artifact.
- The change is the one the user named (`name`, or `module:name` for another
  module); otherwise the only one in `changes` (`--all` for every module).
  If several could fit, offer them as numbered options (the most recent
  recommended); if none fits, ask for its name. Announce
  `Using change: <ref>` and use that `<ref>` in every command.

---

## Steps

1. **Pick the change and start the phase once the plan is ready**

   Pick the change (above), then:
   ```bash
   specworks start design --change "<ref>"
   ```
   It runs `gate specify` and moves the change to design only if it passes.
   If it fails, stop: show the failing checks and suggest
   `/specworks-specify <ref>` to finish the plan.

Read the module's `<docsPath>/architecture.md` first (`docsPath` of the module in `specworks context`); when there is none yet, go on without it.

2. **Load the plan and the code it touches**

   Re-read from disk:
   - the delta specs (`specs/**/spec.md`): every ADDED and MODIFIED
     requirement and its acceptance criteria. Each WHEN/THEN must be
     reachable through the API you are about to define;
   - `design.md` (if any), above all **Decisions** and **Interfaces**;
   - the pending tasks: `specworks task list --change "<ref>" --pending`.

   Then read the existing code each capability owns (`codePath` from
   `specworks spec show <ref> --json`): the public classes and functions,
   naming, module layout, error handling, how types and docs are written.
   New and extended interfaces follow these conventions.

3. **Propose the API and decide it with the user**

   For every requirement, work out how a caller (a test, another module, a
   user of the CLI or service) will exercise it, and list:
   - **New** classes, functions, methods, endpoints, CLI commands, events or
     data shapes: name, parameters and types, return type, errors raised or
     returned, and the requirement IDs they serve.
   - **Extended** existing ones: what is added or changed (a new parameter,
     a new method, a new error) and whether existing callers break; mark a
     breaking change **BREAKING** and check the proposal says so.
   - The file each one lives in, inside the owning capability's code path.

   Prefer extending an existing interface over adding a parallel one, keep
   the surface as small as the requirements need, and leave internals out
   (private helpers are the code half's business).

   Show the list to the user and agree on it before writing code. Ask about
   anything that would change what tests assert (names of errors, return
   shapes, sync vs async, who owns validation), each as numbered options
   with the one you recommend, then close with "Create this API as stubs?
   (yes/no)". Before you stop for that answer, write the proposed list under
   `## Interfaces` (step 4) with a line
   `Proposed: waiting for the user's agreement` below the heading, so the
   proposal is on disk; the user (or the build's coordinator) replaces that
   line with `Agreed with the user` once they agree.

4. **Record the agreed API in design.md**

   Write it under `## Interfaces` (create design.md from
   `specworks instructions design --change "<ref>"` if the change has none,
   filling the other sections only where they apply). One entry per
   interface, naming its file in a code span so the gate can check it:

   ```markdown
   ## Interfaces

   - `src/auth/reset.py`: `ResetService.request_reset(email: str) -> None`,
     raises `UnknownEmail` (REQ-AUTH-003)
   - `src/auth/reset.py`: `ResetService.confirm(token: str, password: str) -> None`,
     raises `ExpiredToken`, `WeakPassword` (REQ-AUTH-003, REQ-AUTH-004)
   - `src/auth/errors.py`: `ExpiredToken`, `WeakPassword` (new)
   ```

   If the change does not touch any API (an internal fix, a pure refactor),
   write `None` with one line saying why.

5. **Create the stubs**

   Only once the API is agreed: `## Interfaces` reads `Agreed with the user`
   instead of `Proposed: waiting for the user's agreement`, or the user
   agreed in this conversation (then write the `Agreed with the user` line
   yourself). While the line still reads `Proposed: ...`, stop and ask
   "Create this API as stubs? (yes/no)" again.

   For each interface, in the project's language and style:
   - real names, parameters, return and error types, and doc comments that
     cite the requirement IDs they serve (`Implements REQ-AUTH-003.`);
   - a body that only signals "not implemented" in the language's idiom
     (`raise NotImplementedError`, `throw new Error("not implemented")`,
     `panic("not implemented")`, `todo!()`, `assert(false)`...);
   - error types and data shapes in full (they have no behaviour to defer);
   - the minimum wiring for callers to reach them (exports, module
     registration, route or command declarations), nothing more.

   Extending an existing function: add the new parameter or method with a
   stub for the new path only; never break the behaviour existing tests rely
   on. Do not add `@req` tags: `@req` marks implemented code and is added in
   the code half of implement.

6. **Check the stubs build, then gate**

   ```bash
   specworks run build --change "<ref>"       # when configured
   specworks run typecheck --change "<ref>"   # when configured
   specworks task done <N.M> [<N.M> ...] --change "<ref>"   # interface tasks you completed
   specworks gate design --change "<ref>"
   ```

   Fix every failing blocking check and re-run. Warnings: fix them or explain
   them.

   **Back from review**: when `specworks cycle --change "<ref>" --json`
   lists open findings whose `phase` is `design` (`R<n>` from review.md,
   `V<n>` from validation.md), you carried out their agreed proposal (the
   Decision, else the Proposal); once the gate passes, record each one by its
   ID:
   ```bash
   specworks finding done <ID> --in design --change "<ref>" "<what changed>"
   ```
   It stays open: review checks it, and the step that found it closes it
   (review its `R` findings, validate its `V` findings).

**Committing**: once this phase's gate has passed (a phase with no gate: once its
artifact is written), and before the closing question, commit with specworks commit --change "<ref>":
- it stages the change folder and every file that changed since the phase
  started, and nothing else (never `git add -A`); do not stage or commit by
  hand;
- the subject is `<ref>: <phase>`; when the project has a commit convention (a
  commit skill, `CLAUDE.md`, `.github/copilot-instructions.md`, the project
  `context`), follow it with `--message "<subject>"` and add its trailers with
  `--trailer "Key: value"` (repeat it, in order);
- name in the report the files it lists as left out (dirty before the phase
  started, not committed) and as already dirty when the phase started
  (committed whole);
- `nothing to commit` is not an error: go on;
- never push: only `/specworks-close` and `/specworks-done` offer that.

7. **Report and stop**

   Show a table, one row per interface:

   ```
   Interface                                File               New/Extended  Serves
   ResetService.request_reset(email)        src/auth/reset.py  new           REQ-AUTH-003
   ResetService.confirm(token, password)    src/auth/reset.py  new           REQ-AUTH-003, REQ-AUTH-004
   login(..., remember: bool = False)       src/auth/login.py  extended      REQ-AUTH-005
   ```

   plus any breaking change and the decisions taken with the user. End with:
   ```
   1. /specworks-test <ref> (recommended): write the failing tests against this API (the test half of implement)
   2. /specworks-code <ref>: write the code first (the code half; it does not wait for the tests)
   3. Stop here
   ```

---

## Guardrails

- No tests and no behaviour: stubs only signal "not implemented". Tests
  belong to `/specworks-test`, behaviour to `/specworks-code` (the two
  halves of implement).
- The API serves the specs. If a requirement cannot be reached through a
  sensible API, or the API exposes something no requirement asks for, stop
  and suggest `/specworks-specify <ref>` to fix the spec.
- Decide with the user before writing code; design.md's Interfaces is the
  record of that decision, and the code must match it.
- IDs come from the specs. Never invent a requirement ID.
- Re-read the specs, design and tasks from disk before using them.
