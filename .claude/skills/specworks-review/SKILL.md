---
name: specworks-review
description: Review phase of spec-driven development - compare a change's code with its specs in both directions, find drift (behaviour no requirement describes, requirements the code misses, tests that do not really check their criterion, an API or design the code proved wrong, wrong tags), propose for each one a change to the code, the spec or the design/API, apply it with the user or send the change back to the phase that owns it, and record every decision in review.md. Use after the implement phase (test and code halves) of a specworks change, or when the user says "review the change", "sync code and spec", "check for drift" or "specworks review".
allowed-tools: Bash(specworks:*), Bash(uv run specworks:*), Bash(uvx --from git+https://github.com/lcmonteiro/specworks specworks:*), Bash(git diff:*), Bash(git log:*), Bash(git status:*), Bash(git add:*), Bash(git commit:*), Read, Grep, Glob, Write, Edit
---

Review phase: make the code, the specs and the design (API) say the same
thing. Implementation always teaches something the plan did not know; this
phase decides, for each difference, which one is right and proposes the
change to the others: the **code**, the **spec** or the **design/API**.
Small, local changes are applied here with the user; larger ones send the
change back to the phase that owns them. Every decision goes in `review.md`.

It is the fifth phase of `refine → specify → design → implement (test | code) → review → validate → close`.
The two halves of implement wrote the tests and the code independently, from
the same specs and design: review is where they meet for the first time.

**Phase boundary**: this phase may change code, tests, the change's delta
specs and design.md, but only to remove drift, and only in small, local
steps. Larger changes go back to `/specworks-specify`, `/specworks-design`,
`/specworks-test` or `/specworks-code`. New features are out of scope: note them for a future
change. Every spec, design or API change and every accepted difference is
agreed with the user. When the gate passes, stop and suggest
`/specworks-validate`.

**Inside `/specworks-build`**: do not apply fixes here. Record every finding
that needs work as open, with the agreed proposal as `back to
<specify|design|implement|test|code>: ...`, or `back to design only: ...`
when the design fix needs no test or code change; the build runs the steps
those findings need next (`specworks cycle --change "<ref>"`): only the code
half, only the test half, both halves (`implement`), design and then both, or
design alone.

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

1. **Pick the change and start the phase once it is implemented**

   Pick the change (above), then:
   ```bash
   specworks start review --change "<ref>"
   ```
   It runs implement's gate, `gate test` then `gate code`, and moves the
   change to review only if both pass. Neither gate runs the suite: it
   first runs in the next step, at `specworks run test`. If `gate test`
   fails (open `[test]` tasks, criteria without tests), stop and suggest
   `/specworks-test <ref>`; if `gate code` fails (open `[code]` tasks,
   untagged requirements), suggest `/specworks-code <ref>`. Reviewing
   unfinished work finds noise.

   Then run the suite: this is the first time the change's tests meet its
   code.
   ```bash
   specworks run test --change "<ref>"
   ```
   Every failing test is a finding (step 4), never something to make green
   quietly. Read the test, its criterion and the code, and say which one is
   wrong: the **code** (`code-gap`: it does not do what the criterion says),
   the **test** (`test-gap`: it checks something the criterion does not
   say), or the **spec** (`spec-gap`: the criterion is ambiguous, and the
   two halves read it differently).

Read the module's `<docsPath>/architecture.md` first (`docsPath` of the module in `specworks context`); when there is none yet, go on without it.

2. **Collect the drift candidates**

   ```bash
   specworks review --change "<ref>" --json          # add --base <branch> if the default is wrong
   ```

   - spec → code: `reqWithoutCode`, `acWithoutTests`, `removedStillTagged`,
     `unknownTags`;
   - code → spec: `untracedSource` (changed code with no `@req`) and
     `untracedTests` (changed tests with no `@ac`).

   They are candidates. The real review is reading the code.

3. **Read the diff against the specs, in both directions**

   ```bash
   git diff <base>...HEAD     # plus uncommitted changes: git diff, git status
   ```

   Re-read the delta specs and design.md from disk, then check:
   - **Each requirement and criterion → code**: does the tagged code do exactly
     what the requirement says, including errors, limits and edge cases in the
     scenarios? Is anything only partly done?
   - **Each change in the code → spec**: is every new or changed behaviour
     (inputs accepted, outputs, errors, side effects, defaults, limits) covered
     by a requirement? Untagged code is either plumbing for a tagged
     requirement, a pure refactor, or behaviour the spec is missing.
   - **Each test → its criterion**: does it assert the THEN, through the public
     interface, and would it fail if the behaviour broke? A test that asserts
     too little is a finding.
   - **Tags**: on the code that really implements the requirement, none
     missing, none to wrong IDs.
   - **Design / API**: does the code expose exactly the interfaces under
     `## Interfaces` in design.md (names, parameters, return and error types,
     files)? Does it follow the Decisions? Where it differs, which one is
     right: did the code drift, or did implementing it prove the agreed API or
     decision wrong (awkward to call, leaking internals, missing an error,
     impossible to test)?
   - **Quality that matters**: security, data loss, error handling or obvious
     bugs in the changed code, even when no spec covers them.

4. **Propose a change for each finding and decide it with the user**

   Classify each one (`spec-gap`, `code-gap`, `design-gap`, `test-gap`, `tag`,
   `quality`). For a disagreement, say what the code does, what the spec and
   design.md say, and **propose the change**: to the code, to the spec, or to
   the design/API, with what exactly would change. Then ask, as numbered
   options (change the code, the spec or the design/API, or accept it as
   it is), the one you propose marked recommended with its reason. Group
   small, obvious ones into one yes/no question ("Apply these fixes?
   (yes/no)") to keep the questions few.

   Apply it here when it is small and local; otherwise send the change back:

   | Change to | Here (small, local) | Back to (larger) |
   |---|---|---|
   | **code** | fix the code, run `specworks run test --change "<ref>"` | `/specworks-code`: a requirement is far from done |
   | **test** | fix the test so it checks its criterion, run the tests | `/specworks-test`: several tests, or a criterion with none |
   | **spec** | edit the delta spec (ADDED with the next free ID from `specworks spec show <cap> --json`, MODIFIED with the whole block), add its test (`@ac`), tag (`@req`) and task, run `specworks check --change "<ref>"` | `/specworks-specify`: several requirements, a new capability, or the proposal's scope changes |
   | **design / API** | one interface, no other callers: update `## Interfaces` (or the Decision) in design.md, the code and its tests together, run the tests | `/specworks-design`: the API changes for other callers or several interfaces; both halves of implement follow again |

   To send it back: record the finding as open with the agreed proposal, then
   ```bash
   specworks phase <specify|design|implement> --change "<ref>"
   ```
   (`implement` for the test or the code half) and offer the matching skill
   (`/specworks-specify`, `/specworks-design`, `/specworks-test` or
   `/specworks-code`) as the recommended next step. When the change comes
   back to review, check that the proposal was carried out (a `done in
   <step>: ...` line under the finding says what changed) and close the
   finding:
   ```bash
   specworks finding close R<n> --change "<ref>" "<what was confirmed>"
   ```
   - **accepted**: only with the user's explicit agreement, with the reason.

   **Findings of validation.md**: `specworks cycle --change "<ref>" --json`
   lists every open finding of the check artifacts, each by its ID. A `V<n>`
   finding is validate's: check the work a step marked `done in <step>:`
   under it, and carry out the ones routed `back to review:` (e.g. account
   for a file); then record what you checked, and never tick it:
   ```bash
   specworks finding done V<n> --in review --change "<ref>" "<what was checked>"
   ```
   It is then routed to validate, which confirms and ticks it; `cycle` gives
   it no build cycle and says `next: validate`. A `V<n>` finding whose work
   is not done yet is a finding of this review: add it to review.md as usual.

   **Findings of inspection.md**: an `I<n>` finding is a reviewer's note from
   `/specworks-inspect`. Treat it as a `V<n>`: answer a `question` (or turn
   it into a finding of this review), check the work a step marked `done in
   <step>:` under the others, and record what you checked, never ticking it:
   ```bash
   specworks finding done I<n> --in review --change "<ref>" "<what was checked or answered>"
   ```
   It is then routed to inspect, which confirms and ticks it on its next
   run; `cycle` gives it no build cycle. An `I<n>` finding whose work is not
   done yet is a finding of this review: add it to review.md as usual.

5. **Write `review.md`**

   ```bash
   specworks instructions review --change "<ref>" --json
   ```

   Write the findings with the `specworks finding` commands, never by
   editing their lines: each takes the next free ID, checks the type, step
   and Decision, and writes only what `specworks cycle` and the gate read
   back.
   ```bash
   specworks finding add <type> "<what drifts, with REQ/AC IDs and file:line>" --proposal "<the change proposed>" --change "<ref>"
   specworks finding decide R<n> --change "<ref>" "back to <step>: <proposal>"   # or "accepted: <reason>", which ticks it
   specworks finding close R<n> --change "<ref>" "<what was fixed or confirmed>"
   ```
   Propose `back to design only: <proposal>` when the design fix needs no test
   or code change (design.md text only): the next cycle runs design, then
   review, with no implement half.
   A finding fixed here is added, then closed with what changed; one sent
   back stays open with its Decision. Follow `template` and `instruction`
   for the rest: every file from `untracedSource` / `untracedTests` under
   "Changed files without tags" with why it needs no tag or which finding
   covers it, and the summary.

6. **Gate and trace**

   ```bash
   specworks gate review --change "<ref>"            # same --base as step 2
   specworks trace --change "<ref>" --write
   ```

   The gate checks: valid specs, `review.md` written with no open finding,
   every open finding with a known type (or a `back to <step>:`), every requirement with code and every criterion with a test, no unknown
   tags, removed requirements gone, every untagged changed file accounted for,
   and the test suite passing. Fix and re-run until it passes.

   Inside `/specworks-build`, run it with `--allow-open`: the open findings
   are the hand-off to the next cycle, so they are reported as a warning,
   and so is a failing suite while a finding is open (the findings carry
   it); every other check must still pass.

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

   Summarize the findings by type and decision, the spec changes (IDs added or
   modified), the design/API changes, the code changes, anything accepted, and
   any change sent back to an earlier phase or half (then stop there instead
   of suggesting validate). End with:
   ```
   1. /specworks-done <ref> (recommended): validate, then close
   2. /specworks-validate <ref>: the final check alone
   3. Stop here
   ```

---

## Guardrails

- Never change a spec or an API silently: every spec, design or API update
  and every accepted difference is agreed with the user and recorded in
  review.md.
- Fix drift, do not add features. Out-of-scope ideas go in the summary as
  candidates for a new change.
- Do not weaken tests or delete failing ones to pass the gate.
- Keep IDs stable: a changed behaviour is a MODIFIED requirement with the same
  ID; new behaviour gets the next free ID.
- Re-read specs, design, tasks and review.md from disk before relying on them.
