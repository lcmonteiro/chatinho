---
name: specworks-done
description: Finish a reviewed change in one run - validate it (the read-only PASS/FAIL check) and, only when it passes, close it (merge its specs into the living docs and archive it), running each phase's own skill in order. Use when a specworks change has been reviewed (a feature, a fix or a baseline-<capability>) and the user wants to finish it, or says "done", "finish the change", "validate and close" or "specworks done".
allowed-tools: Bash(specworks:*), Bash(uv run specworks:*), Bash(uvx --from git+https://github.com/lcmonteiro/specworks specworks:*), Bash(git diff:*), Bash(git log:*), Bash(git status:*), Read, Grep, Glob, Write, Edit, Agent
---

Done: take a reviewed change through **validate → close** in one run. The
change is closed only if validate passes: a FAIL stops here, with every
failure pointing to the phase that fixes it. Each phase is done exactly as
its own skill says; this skill only chains them, so `/specworks-done <ref>`
ends where `/specworks-validate <ref>` followed by `/specworks-close <ref>`
ends. It adds no check of its own and skips none.

It covers the last two phases of `refine → specify → design → implement (test | code) → review → validate → close`.

**Phase skills**: `specworks-validate` and `specworks-close`, installed next
to this skill (`../specworks-<phase>/SKILL.md`). Each phase runs in its own
subagent (below), which follows that skill's steps, checks and guardrails,
including every point where it asks the user (the merge plan in close): the
subagent returns the question and you ask it. You do not do a phase's work
yourself.

**Boundary**: validate changes nothing; close edits only the living docs
and, for new capabilities, the config. A failure is never fixed here: it
goes back to the phase that owns it.

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

**Phases in subagents**: each phase runs in a fresh subagent that depends
only on the project and the change's artifacts on disk, never on this
conversation. You are the coordinator: you start the subagents, ask the user
their questions, and write the answers to disk.

- **The prompt is fixed**: start each phase with your subagent tool (Claude
  Code: `Agent`) and this prompt, with only `<phase>`, `<ref>` and the skills
  folder (the one holding this skill's folder, e.g. `.claude/skills`) filled
  in (`<phase>` is the skill's name: `test` and `code` for the two halves of
  implement). Never add a summary of the conversation, an answer or a
  decision: what the phase needs from the user is on disk.
  ```
  Run the <phase> phase of the change <ref>: follow
  <skills folder>/specworks-<phase>/SKILL.md, reading only the project and
  the change's artifacts on disk. You cannot ask the user. When the answer
  to a question the skill would ask is already on disk, use it and go on; do
  not ask it again. When the skill would stop for the user, first write what
  you propose into your own artifact, then stop and return the question.
  Skip the skill's "Report and stop". End your last message with exactly
  one line:
  Result: done <one-line result; the gate passed>
  Result: question <the closing question as the skill asks it, options included>
  Result: blocked <what failed, and the phase or skill it goes back to>
  ```
- **On `Result: done`**: report its line and start the next phase.
- **On `Result: question`**: ask the user the question as it is. Write the
  answer where the next run of the phase reads it, then start a fresh
  subagent for the same phase with the same prompt (review in a build: see
  its step 3):

  | Question | Where the answer goes |
  |---|---|
  | design: the API | design.md `## Interfaces`: the subagent writes it with a line `Proposed: waiting for the user's agreement`; replace that line with `Agreed with the user` (and the user's changes) |
  | test, code: the test command | the config, written with `specworks config set commands.test "<command>"` |
  | code: an unclear task, an existing test against the spec, new work | the Decision in design.md, or a new task in tasks.md |
  | review: each finding | the finding's `**Decision**:` line in review.md, written with `specworks finding decide R<n> --change "<ref>" "<decision>"` |

  Write only the answer, in the place the question is about. Never do the
  phase's own work.
- **On `Result: blocked`**: stop and report where and why, as for a gate
  that cannot be fixed.
- **No subagent tool**: follow the phase skill yourself in this
  conversation, and still write every answer to disk as above.

**In a done run**, the phases add a fixed line to the prompt:
- validate: `End with the report of step 4 of the skill before the Result
  line: PASS is Result: done, FAIL is Result: blocked.`
- close, first run: `This phase runs inside /specworks-done: stop before
  step 4 of the skill. Return the capabilities to register (step 2) as the
  question, or, when none is left, the merge plan (step 3).`
- close, after the user's go-ahead on the merge plan, a second subagent with
  this line instead: `This phase runs inside /specworks-done: the merge plan
  is approved; continue from step 4 of the skill.`

---

## Steps

1. **Pick the change**

   Pick the change (above) and say the plan: `Done <ref>: validate → close`.
   Whatever phase the change is in, start with validate (step 2): its first
   step decides, as it does on its own, whether the change can enter
   validate (a change not yet reviewed fails there).

2. **Validate**

   Announce `Done · validate` and start its subagent (above), which will
   follow `specworks-validate`: it starts the phase, runs
   `specworks validate`, reads what the CLI cannot check, and returns
   validate's report with `Result: done` (PASS) or `Result: blocked` (FAIL).
   Validate changes nothing and asks nothing.

3. **Show the verdict and decide**

   Show validate's report exactly as its step 4 lays it out:
   ```
   Validate <ref>: PASS | FAIL

   Completeness  5/5   Correctness  6/6   Coherence  3/3
   WARNING   AC-AUTH-003.2 test checks the status only  -> /specworks-review
   ```
   - **FAIL** (a critical issue from the CLI or from your reading): stop.
     List the critical issues grouped by the phase to go back to, offer the
     earliest one as the recommended option (`specworks phase <phase>
     --change "<ref>"`, then `/specworks-<phase> <ref>`), with "Stop here" as
     the other, and say that `/specworks-done <ref>` finishes it once fixed.
     Nothing is closed.
   - **PASS**: list any warnings (they do not block) and go on to close.

4. **Close**

   Announce `Done · close` and start the first close subagent (above),
   which will follow `specworks-close`: it starts the phase (which runs the
   validate gate again on the same code) and returns a question:
   - **Register a capability** ("Register `<name>` in `<module>` at
     `<code path>`? (yes/no)"): ask the user, then write the answer to the
     project yourself (the user's module and path on no), and start the
     first close subagent again:
     ```bash
     specworks capability add <name> --path <code path> [--module <module>] [--prefix <P>] [--description "<one line>"]
     ```
   - **The merge plan** ("Merge and archive? (yes/no)"): ask the user. On
     yes, start the second close subagent (the merge plan is approved,
     continue from step 4): it updates the living design, merges and
     archives. On no, stop: nothing is written and the change stays in
     close.

5. **Report and stop**

   One summary for both phases:
   ```
   Done <ref>: closed

   Validate   PASS (2 warnings)
   Living docs  src/auth/docs/: spec.md, requirements.md, design.md
   Requirements  +2 added, 1 modified, 0 removed
   Archived   .specworks/changes/archive/2026-10-19-add-password-reset/
   ```

**Pushing**: after the commit, offer to push the change's branch (the checked-out
one, from `git status`): ask `Push <branch>? (yes/no)`. On yes, run
`git push -u origin <branch>` (never pre-approved: the user is asked either
way) and relay the "create a pull request" link the remote prints. When it
prints none and `origin` is a `github.com` or `gitlab.com` URL, build the link:
`<repo URL>/pull/new/<branch>` for GitHub,
`<repo URL>/-/merge_requests/new?merge_request[source_branch]=<branch>` for
GitLab; otherwise only report the push. On no, say the branch stays local.

Once the push question is answered, end with close's next steps as numbered
options: for a `baseline-<capability>` change, the next capability to
baseline (`/specworks-baseline <capability>`) or, when every capability has
a living spec, the first waiting bug change; plus "Stop here".

---

## Guardrails

- Never close a change that fails validate, whatever the reason; your
  reading can add critical issues, never remove the CLI's.
- Never fix a failure here: no code, test or spec edits. Send it to the
  phase that owns it.
- The user's go-ahead on the merge plan (close step 3) is still required;
  running both phases in one go does not skip it. Only that go-ahead starts
  the second close subagent.
- A subagent's prompt is the fixed text above with the phase, the ref and
  the skills folder filled in: nothing from this conversation.
- If the user stops after validate, the change stays in `validate`;
  `/specworks-close <ref>` or `/specworks-done <ref>` finishes it later.
