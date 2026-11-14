---
name: specworks-test
description: Test half of the implement phase of spec-driven development - turn a change's acceptance criteria into failing tests (tagged @ac) written against the API agreed in the design phase, independently of the code half. Use when a specworks change has its interfaces and the user wants to write its acceptance tests first, or says "write the acceptance tests" or "specworks test".
allowed-tools: Bash(specworks:*), Bash(uv run specworks:*), Bash(uvx --from git+https://github.com/lcmonteiro/specworks specworks:*), Bash(git add:*), Bash(git commit:*), Read, Grep, Glob, Write, Edit
---

Test half of implement: write the tests that prove each acceptance
criterion, through the API stubs created in the design phase. The code half
(`/specworks-code`) writes the code from the same specs and design without
reading these tests, so the two are independent readings of the spec, and
review is where they meet.
At the end every acceptance criterion has at least one test tagged
`@ac <AC-ID>`, every `[test]` task is ticked, and the tests **fail for the
right reason** against the stubs (not implemented yet), not because they
cannot compile or import.

It is the test half of the fourth phase of `refine → specify → design → implement (test | code) → review → validate → close`.
In `/specworks-build` it runs in parallel with the code half, in its own git
worktree that holds only design's stubs.

**Phase boundary**: write tests only, against the interfaces recorded in
design.md. Do not add or change public interfaces here: if a test needs one,
go back to `/specworks-design`. No behaviour, no partial logic, even if it
looks easy. Work only on the `[test]` tasks: the `[code]` tasks are the
other half's. When the test gate passes, stop and suggest `/specworks-code`
(or `/specworks-review` when the code half is done).

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

1. **Pick the change and start implement once the interfaces are ready**

   - In a git worktree (`git rev-parse --git-dir` differs from
     `git rev-parse --git-common-dir`), first bring it up to the main
     checkout, whose HEAD holds design's committed stubs: the main checkout
     is the first entry of `git worktree list`; fast-forward to its HEAD
     with `git merge --ff-only <commit>`. If that is not a fast-forward,
     stop: in a build, return `Result: blocked` (the worktree cannot hold
     design's stubs; back to `/specworks-build`).
   - Pick the change (above) and start implement:
     ```bash
     specworks start implement --change "<ref>"
     ```
     It runs the gates of the phases left behind (`gate design`, and
     `gate specify` too if the change skips design) and moves the change to
     implement only if they pass. When the change is already in implement
     (the code half started it), it re-checks `gate design` only.
   - If a gate fails, stop: show the failing checks and suggest
     `/specworks-design <ref>` (or `/specworks-specify <ref>` when the specs
     themselves fail). Tests built on an undecided API test the wrong thing.
   - `commands.test` in the context is how this project runs its tests. If it
     is empty, find the test command from the repository (pyproject, package.json,
     go.mod, Cargo.toml, CMake, Makefile, CI config), and ask "Use `<command>` as
     the test command? (yes/no)"; on yes, save it with `specworks config set commands.test "<command>"`.

2. **Load the plan and the project's test conventions**

   Re-read from disk:
   - the delta specs (`specs/**/spec.md`): every ADDED and MODIFIED requirement
     and its acceptance criteria, and every REMOVED requirement;
   - `design.md`, above all **Interfaces**: the agreed public APIs, data
     shapes and CLI surfaces, and the files whose stubs the tests call;
   - the pending tasks: `specworks task list --change "<ref>" --pending`;
     yours are the ones marked `[test]`.

   Then study the existing tests next to the code each capability owns
   (`codePath` from `specworks spec show <ref> --json`): framework, folder
   layout, file and test naming, fixtures, helpers, how I/O, time and network
   are faked. New tests follow these conventions.

   Find the tests that already cover MODIFIED or REMOVED criteria:
   ```bash
   specworks trace --change "<ref>" --json
   ```
   (rows with `tests` for those IDs).

3. **Check the API covers every criterion**

   For each ADDED or MODIFIED acceptance criterion, find the interface in
   design.md (and its stub in the code) that a test will call. If one is
   missing or cannot express the WHEN/THEN (a missing parameter, error type
   or return field), stop and go back to `/specworks-design <ref>` to
   decide and stub it with the user; do not add it here.

4. **Write the tests, one acceptance criterion at a time**

   For each ADDED or MODIFIED acceptance criterion:
   - Write at least one test that checks exactly what its WHEN/THEN says,
     through the public interface (black box): GIVEN → arrange, WHEN → act,
     THEN → assert. Cover error scenarios with the real error type or status.
   - Put the tag in a comment right above the test, in the language's comment
     syntax, and name the test after the criterion:
     ```python
     # @ac AC-AUTH-003.2
     def test_ac_auth_003_2_expired_link_is_rejected(): ...
     ```
     ```ts
     // @ac AC-AUTH-003.2
     it("AC-AUTH-003.2 rejects an expired link", ...)
     ```
     One test may carry several criteria (`# @ac AC-AUTH-003.1, AC-AUTH-003.2`)
     when it truly checks all of them.
   - Pick the level the criterion needs: unit for logic, integration for
     storage, APIs and wiring, end-to-end only when the criterion is about the
     whole flow.
   - Keep tests deterministic: control time, randomness, network and
     filesystem the way the project already does.
   - Wording checks (tests that check text: skill wording, templates,
     instructions): Assert only the pinned phrases of design.md, verbatim
     (its **Pinned wording**); never phrases picked from the proposal.

   MODIFIED criteria: update the existing tests found in step 2 to the new
   behaviour and keep their `@ac` tags. REMOVED requirements, and criteria a
   MODIFIED block leaves out: delete their tests (they would fail once the
   behaviour is removed) and say which ones.

5. **Run the tests and confirm they fail for the right reason**

   ```bash
   specworks run test --change "<ref>"
   ```
   (runs `commands.test` in the change's module; when the suite is slow you
   may run the test tool directly on the new tests, which asks the user to
   approve that command). Expected:
   - every new or updated test **fails**, because the stub is not implemented
     or the assertion does not hold yet;
   - **no** syntax, compile, import or collection errors: fix those now, they
     are bugs in the tests or stubs, not "red";
   - unrelated existing tests still pass.

   A test that already passes either checks nothing new, or the behaviour
   already exists (outside a build, the code half may have run first): look
   at it, then strengthen the test or tell the user. Do not read or change
   the code half's work to make a test fit it: review compares the two.
   Never weaken an assertion, skip a test or mark it expected-to-fail to get
   the right colour.

6. **Tick the `[test]` tasks, gate and trace**

   ```bash
   specworks task done <N.M> [<N.M> ...] --change "<ref>"   # the [test] tasks you completed
   specworks gate test --change "<ref>"
   specworks trace --change "<ref>" --write
   ```

   The test gate checks only this half: every `[test]` task done, a test
   for every criterion, no tag to an unknown ID. Open `[code]` tasks do not
   affect it. Fix every failing blocking check (an untested criterion, a tag
   with a wrong ID) and re-run. Warnings: fix them or explain them.

   **Back from review**: when `specworks cycle --change "<ref>" --json`
   lists open findings whose `phase` is `test` (`R<n>` from review.md,
   `V<n>` from validation.md), you carried out their agreed proposal (the
   Decision, else the Proposal); once the gate passes, record each one by its
   ID (a finding routed to `implement` is recorded by the code half, so the two halves never write the same lines):
   ```bash
   specworks finding done <ID> --in test --change "<ref>" "<what changed>"
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

   Show a table, one row per acceptance criterion:

   ```
   Criterion       Test                                              Result
   AC-AUTH-003.1   tests/test_reset.py::test_ac_auth_003_1_request   fails: NotImplementedError
   AC-AUTH-003.2   tests/test_reset.py::test_ac_auth_003_2_expired   fails: NotImplementedError
   ```

   plus tests updated or deleted for MODIFIED/REMOVED criteria, and anything
   you had to decide. Mention that the
   test suite is red on purpose until the code half is done. End with:
   ```
   1. /specworks-code <ref> (recommended): the code half, from the specs and design
   2. /specworks-review <ref>: the code half is already done; the tests meet the code
   3. Stop here
   ```

---

## Guardrails

- No implementation and no new interfaces: tests call the stubs from the
  design phase. Behaviour belongs to `/specworks-code`, API changes to
  `/specworks-design`.
- Only this half: the `[test]` tasks and the test gate. Do not tick `[code]`
  tasks or run `gate code`.
- Tests verify the acceptance criteria as written. If a criterion is wrong,
  ambiguous or untestable, stop and suggest `/specworks-specify <ref>` to fix
  the spec instead of testing your own interpretation.
- IDs come from the specs. Never invent an AC ID or tag a test with an ID of
  another change.
- Do not skip, disable, or mark tests as expected failures, and do not loosen
  assertions, to reach the expected state.
- Re-read the specs, design and tasks from disk before using them.
