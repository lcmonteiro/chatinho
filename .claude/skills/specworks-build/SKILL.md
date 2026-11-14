---
name: specworks-build
description: Build a specified change end to end in cycles of design → implement → review, running each phase's own skill, with implement's test and code halves in parallel (the test half in its own git worktree); after each review with findings, ask whether to start a new cycle that runs only the steps the findings need (code findings → code half, review; test findings → test half, review; both, or back to implement → both halves, review; design/API findings → design, both halves, review; `back to design only:` → design, review). Use when a specworks change has been specified and the user wants to build it in one go, or says "build the change", "run the build cycle", "design test code review" or "specworks build".
allowed-tools: Bash(specworks:*), Bash(uv run specworks:*), Bash(uvx --from git+https://github.com/lcmonteiro/specworks specworks:*), Bash(git diff:*), Bash(git log:*), Bash(git status:*), Read, Grep, Glob, Write, Edit, Agent
---

Build: take a specified change through **design → implement → review** in
one run, then repeat the steps the review findings need until the review is
clean (or the user stops). Implement has two halves that run in parallel:
the **test** half writes the failing tests, the **code** half writes the
code, each from the specs and design only. Each phase and half is done
exactly as its own skill says; this skill only chains them and decides what
a new cycle runs.

It covers phases three to five of `refine → specify → design → implement (test | code) → review → validate → close`.

**Phase skills**: `specworks-design`, `specworks-test` (the test half),
`specworks-code` (the code half) and `specworks-review`, installed next to
this skill (`../specworks-<phase>/SKILL.md`).
Each runs in its own subagent (below), which follows that skill's steps,
checks and guardrails. You do not do a phase's work yourself: you start the
subagents, ask the user what they return, write the answers to disk, merge
the test half's worktree, and decide what each cycle runs.

**Boundary**: the build stops, and does not work around it, when a phase gate
fails and cannot be fixed within that phase, when the specs turn out wrong
(spec findings go to `/specworks-specify`), or when the user says stop.

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

**In a build**, add this fixed line to every phase's prompt:
```
This phase runs inside /specworks-build: also follow step 2 (open review
findings from an earlier cycle) and, in review, step 3 (propose, do not fix)
of <skills folder>/specworks-build/SKILL.md.
```

---

## Steps

1. **Pick the change and where to start**

   Pick the change (above), then:
   ```bash
   specworks gate specify --change "<ref>"
   specworks status --change "<ref>" --json
   specworks cycle --change "<ref>" --json
   ```

   - If `gate specify` fails, stop and suggest `/specworks-specify <ref>`.
   - Start point:
     - a previous review left open findings (`cycle` returns `startAt` and
       the steps in `phases`): resume with that cycle (step 4);
     - the change is already in `design` or `review`: resume at that phase;
     - the change is in `implement`: run the halves whose tasks are still
       open (`status` shows `halves`, e.g. `test 3/3, code 1/4`), then
       review;
     - otherwise start at `design`.
   - Say the plan, e.g. `Cycle 1: design → implement (test | code) → review`.

2. **Run the cycle's steps in order**

   For each step of the cycle (`design`, then the halves, then `review`),
   announce `Cycle <n> · <step>` and start its subagent (above), with
   `<phase>` set to the step: `test` and `code` for the two halves. The skill
   moves the change with `specworks start`, does the work and runs its gate.
   On `Result: done`, report its line and go on; on `Result: question`, ask,
   write the answer to disk and start a fresh subagent for the same step (for
   review, step 3 says what follows instead); on `Result: blocked`, stop and
   report where and why.

   **Implement: the two halves in parallel.** When the cycle has both
   halves, start them together (design's work is already committed by its own skill; the
   worktree may start from an older commit, so the test skill first
   fast-forwards it to the main checkout's HEAD, which holds design's stubs):
   - the **test** half in a subagent with its own git worktree (Claude Code:
     `Agent` with `isolation: "worktree"`); add to its prompt nothing but the
     fixed text. When it is done, its changes are on the worktree's branch:
     commit them there if the subagent did not;
   - the **code** half in a subagent in the main checkout, at the same time.

   Wait for both. Then merge the worktree's branch into the main checkout
   with `specworks merge <branch> --change "<ref>"`: it keeps every tick of
   `tasks.md` and regenerates `traceability.md`, and aborts the merge on any
   other conflict (a half worked outside its own files). If it fails, stop
   and report its error. After the merge, run
   `specworks gate implement --change "<ref>"`: every check must pass; it
   does not run the suite (the halves' tests meet the code in review).

   A question from one half does not stop the other: let it finish, ask the
   question, write the answer to disk and rerun only the half that asked.
   With only one half in the cycle, run it alone in the main checkout.
   **No worktree** (no subagent tool with isolation, or not a git
   repository): run the test half first, then the code half, both in the
   main checkout; the code half still does not read the test half's tests.

   From the second cycle on, each step works on the **open findings of the
   check artifacts** that belong to it (`R<n>` in review.md, `V<n>` in
   validation.md after a validate; `specworks cycle --change "<ref>" --json`
   lists each finding by its ID with its step in `phase`): carry out the agreed
   proposal in the finding's Decision, plus whatever the later steps need to
   follow it (a new API needs its tests and code). A finding routed to
   `implement` belongs to both halves. A finding marked `done in <step>:`
   has that step's part done already (e.g. the spec change from specify):
   carry out what it means for this step. Do not redo untouched work.

   If a gate fails, the phase fixes it as its skill says. If it cannot be
   fixed there (the specs are wrong, the user must decide something outside
   the build), the subagent returns `Result: blocked`: stop and report where
   and why.

3. **Review: propose, do not fix**

   The review subagent runs `specworks-review` as written, with one
   difference: in a build, every finding that needs work is recorded
   **open** with the phase that will carry it out, instead of being fixed
   inside review. It decides nothing with the user itself:

   - **First run**: it ticks its own (`R<n>`) findings from an earlier cycle
     that are now done (`- [x]`, with `specworks finding close`), marks each
     `V<n>` finding of validation.md it checked `done in review:` (with
     `specworks finding done V<n> --in review`; validate ticks it), adds every new
     finding open with the change it proposes (`specworks finding add`), then returns them all in one
     `Result: question` (small, obvious ones grouped into one yes/no
     question, as review does):
     ```markdown
     - [ ] R2 **design-gap** `reset()` returns None; callers need the token (REQ-AUTH-003)
       - **Proposal**: back to design: return `ResetToken` from `ResetService.request_reset`
     ```
   - **You** ask the user about each finding, one at a time, and turn each
     answer into the finding's `**Decision**:` line in review.md with
     `specworks finding decide R<n> --change "<ref>" "<decision>"`: the
     proposal as agreed (`back to <step>: ...`, where a step is specify,
     design, implement, test, code or review), the user's other choice,
     or `accepted: <reason>`, which ticks the box. Spec findings
     (`spec-gap`) get `back to specify: ...`.
   - **Then**, once every `**Decision**:` line is written, run
     `specworks gate review --change "<ref>" --allow-open` yourself; no
     second review subagent runs. If the gate rejects a Decision line,
     decide it again with `specworks finding decide` and run the gate again.

   The gate is `specworks gate review --change "<ref>" --allow-open`: open
   findings do not fail it here (step 4 turns them into the next cycle), nor
   does a failing suite while a finding is open (the findings carry it), but
   every other check (a test for every criterion, untagged files accounted
   for, tags, a known type or `back to <step>:` on every open finding)
   must.

4. **After the review: ask about a new cycle**

   ```bash
   specworks cycle --change "<ref>"
   ```

   - **No open findings**, or only findings waiting for validate (no
     `startAt`, `next: validate`): the build is done (go to step 5).
   - **A spec finding** (`handOver` is `/specworks-specify`): stop the build.
     Explain which requirement is missing or wrong, and offer:
     ```
     1. /specworks-specify <ref> (recommended): fix the specs; /specworks-build <ref> then continues
     2. Stop here
     ```
     Specify marks each finding it carried out `done in specify:
     ...`, so `cycle` then starts at design and the build resumes there.
   - **Otherwise** show the open findings and the step each one needs,
     then ask:

     ```
     Review found 2 open findings:
       R1 code-gap    lockout counter not reset on success   -> code
       R3 test-gap    AC-AUTH-003.2 only checks the status   -> test
     Start cycle 2: implement (test | code) → review? (yes/no)
     ```

     - **Yes**: go back to step 2 with the next cycle number and the steps
       in `phases`; the first step's subagent moves the change back with
       `specworks start <startAt>` (`design`, `implement` or `review`).
     - **No**: stop. The findings stay open in review.md; the user can run a
       single phase skill, or `/specworks-build <ref>` later to resume.

   The cycle runs only the steps the findings need (`phases`): code findings
   (`code-gap`, `tag`, `quality`) → code, review; test findings (`test-gap`)
   → test, review; both kinds, or `back to implement:` → test and code in
   parallel, review; design/API findings → design, test and code in
   parallel, review; `back to design only:` → design, review (no half, no
   worktree; with code or test findings as well, only their halves join). A
   `back to <step>: ...` in a finding's Decision overrides its type, and a
   `done in <step>: ...` line moves it on to the next step (design →
   implement, or review for `back to design only:`; implement, test or code →
   review).

   After the third cycle, say how many cycles have run and what keeps coming
   back before asking again: repeated findings usually mean the spec or the
   design needs a decision, not another cycle.

5. **Report and stop**

   Summarize per cycle: the steps run, the API agreed or changed, tests
   added, the code written, the worktree merge (and the files it resolved),
   and the findings (found, resolved, accepted).
   Run `specworks trace --change "<ref>" --write`. Say "The build is
   complete." and end with:
   ```
   1. /specworks-done <ref> (recommended): validate, then close
   2. /specworks-validate <ref>: the final check alone
   3. Stop here
   ```

---

## Guardrails

- Every phase follows its own skill, in its own subagent: same steps, same
  gates, same questions to the user, asked by you. The build never skips a
  gate or a decision to keep going.
- A subagent's prompt is the fixed text above with the phase, the ref and
  the skills folder filled in: nothing from this conversation. What it needs
  from the user, it reads from disk.
- You write only the user's answers, in the place the question is about;
  never a phase's own work.
- A new cycle only starts after the user says yes, and runs only the steps
  the open findings need.
- The two halves stay independent: the code half never gets the test half's
  tests, and a half never works on the other's tasks.
- Spec problems are not fixed inside the build: hand over to
  `/specworks-specify`.
- Do not weaken tests, skip gates or mark findings resolved to finish a cycle.
