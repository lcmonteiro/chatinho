---
name: specworks-validate
description: Validate phase of spec-driven development - a final pass/fail check that a change is complete, correct and coherent before it is closed, recorded in validation.md with every failure as a finding routed to the phase that fixes it. Use when a specworks change has been reviewed and the user wants to know if it is ready, or says "validate the change", "is the change ready to close" or "specworks validate".
allowed-tools: Bash(specworks:*), Bash(uv run specworks:*), Bash(uvx --from git+https://github.com/lcmonteiro/specworks specworks:*), Bash(git diff:*), Bash(git log:*), Bash(git status:*), Bash(git add:*), Bash(git commit:*), Read, Grep, Glob
---

Validate phase: decide whether the change is ready to close, and record it in
`validation.md`. The CLI checks what can be measured; you check what needs
reading. The result is a clear PASS or FAIL, and every failure is a `V<n>`
finding in `validation.md`, routed to the phase that fixes it; that phase
reads it from there.

It is the sixth phase of `refine → specify → design → implement (test | code) → review → validate → close`.

**Phase boundary**: do not edit code, tests, specs, tasks, design or
review.md, and do not fix what you find, even when it is a one-line fix: record
it as a finding and point to the phase that owns it. The only writes allowed
are `validation.md`, through `specworks validate --write` and `specworks
finding`, and the change's phase marker. On PASS suggest `/specworks-close`; on
FAIL, the phase of the earliest open finding.

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

1. **Pick the change and start the phase once it is reviewed**

   Pick the change (above), then:
   ```bash
   specworks start validate --change "<ref>"      # same --base as below if the default is wrong
   ```
   It runs `gate review` (and the gates of any earlier phase left behind) and
   moves the change to validate only if they pass. If one fails, the verdict
   is FAIL: show the failing checks, offer the skill of the failed gate's
   phase as the recommended next step (`/specworks-review <ref>` for `gate
   review`) or "Stop here", and stop.

2. **Run the measurable checks and write validation.md**

   ```bash
   specworks validate --write --change "<ref>" --json      # add --base <branch> if the default is wrong
   ```

   It runs the project's test, lint and typecheck commands, reports three
   groups (each failed check has a `fix`, the phase skill that owns it) and
   keeps `validation.md` (its `path`) in step with them: a `V<n>` finding,
   with its `**Check**` line, for each failed blocking check, the ones it
   wrote before ticked (`confirmed in validate:`) once their check passes, and
   the verdict and the warnings in its Summary. Warnings are never findings.
   The groups:
   - **Completeness**: proposal, specs and tasks exist; every task done; every
     requirement has `@req` code; every criterion has an `@ac` test; review done
     (`review.md` with no open finding), and no open finding in
     `validation.md`.
   - **Correctness**: specs valid; tests, lint and typecheck pass; no tags to
     unknown IDs; removed requirements gone.
   - **Coherence**: every untagged changed file accounted for in `review.md`;
     diagram SVGs up to date; the change went through review.

3. **Check what needs reading, and confirm your own findings**

   Re-read the delta specs, design.md, review.md, validation.md and the diff
   (`git diff <base>...HEAD`). For each requirement, sample its `@req` code and
   the `@ac` tests of its criteria (`specworks trace --change "<ref>" --json`):
   - does each test exercise its scenario's WHEN and assert its THEN?
   - does the code follow the design decisions, or did review.md record why not?
   - is each `accepted` decision in review.md backed by a reason?
   - is anything in the diff clearly outside the change's scope?

   Report each problem as CRITICAL (the spec is not met, or a check above is
   unreliable) or WARNING (worth fixing, does not block), with the file and
   the phase that fixes it. Do not report taste. Add each CRITICAL one to
   `validation.md` as a finding routed to the step that fixes it (specify,
   design, implement, test, code or review); warnings stay in your report:
   ```bash
   specworks finding add <type> "<what is wrong, and where>" --proposal "back to <step>: <the change>" --artifact validation --change "<ref>"
   ```
   A finding you added in an earlier run (no `**Check**` line) that a step
   has marked `done in <step>:` is yours to confirm: check the work, then tick
   it, or leave it open and say why:
   ```bash
   specworks finding close V<n> --change "<ref>" "<what you confirmed>"
   ```
   The findings validate wrote itself (with a `**Check**` line) are ticked by
   `specworks validate --write` alone.
   Once you have added or ticked a finding, run step 2's command again, so
   the Summary holds the verdict with your findings in it.

4. **Report the verdict and stop**

   ```
   Validate <ref>: PASS | FAIL

   Completeness  5/5   Correctness  6/6   Coherence  3/3
   CRITICAL  every requirement has code: REQ-AUTH-002   -> /specworks-code
   WARNING   AC-AUTH-003.2 test checks the status only  -> /specworks-review
   ```

   The verdict is FAIL when validation.md has an open finding (the CLI's or
   yours). Commit (below) before the closing question.

   - **PASS** (no critical issue from the CLI or from your reading): "Ready to
     close." Then offer `1. /specworks-close <ref> (recommended): merge the
     specs into the living docs and archive the change` and `2. Stop here`.
   - **FAIL**: list the open findings grouped by the step each one is routed
     to, and offer the phase of the earliest one as the recommended option:
     `specworks cycle --change "<ref>" --json` gives it as `next` (its
     `startAt`), with `/specworks-specify <ref>` when `handOver` names it,
     otherwise `/specworks-build <ref>`, which runs the cycle the findings
     need; then "Stop here". Warnings are listed but do not block.

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

---

## Guardrails

- Never modify the project in this phase beyond validation.md. A fix here
  would skip the review and the records the other phases keep.
- A FAIL from `specworks validate` is never overridden by your judgement; your
  reading can only add findings. Never tick a finding to reach PASS: only
  `specworks validate --write` ticks the ones it wrote, and you tick yours
  only once their work is confirmed.
- Be specific: every issue names the check or file and the phase that fixes it.
- Re-read artifacts from disk; the user may have changed them since review.
