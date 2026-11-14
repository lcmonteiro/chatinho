---
name: specworks-inspect
description: Inspect a change, open or closed - walk its scenarios most uncertain and important first, each with its code, its test and the design that argues for it, in a circle the reviewer breaks, and leave the reviewer's notes as findings in inspection.md only when there are any. Use when the user wants to read, audit or understand what a specworks change did, or says "inspect", "inspect the change", "walk me through the change" or "specworks inspect".
allowed-tools: Bash(specworks:*), Bash(uv run specworks:*), Bash(uvx --from git+https://github.com/lcmonteiro/specworks specworks:*), Bash(git diff:*), Bash(git log:*), Bash(git status:*), Read, Grep, Glob
---

Inspect: walk a change with a human reviewer, open (before merge) or closed
(after the fact), one block at a time: a scenario's WHEN with the code that
implements it, its THEN with the test that proves it, and the design that
argues for it. The reviewer reads, asks and leaves notes; the skill keeps
the notes as findings in `inspection.md`, so the flow can act on them.

It sits beside the flow `refine → specify → design → implement (test | code) → review → validate → close`,
not in it: no gate reads inspection.md, and validate and close behave as
before.

**Phase boundary**: this skill is read-only but for two commands:
`specworks finding add` with `--artifact inspection` (and `specworks finding
close` on an `I<n>` ID), which writes the reviewer's notes to inspection.md,
and `specworks commit`, which commits them. It reads with `specworks status`, `specworks trace` (without
`--write`), `specworks cycle` (an open change only), `specworks list --archived`, read-only git
(`git diff`, `git log`, `git status`) and the files. It never fixes what it
finds and never decides a note: deciding is for `/specworks-review` (open
change) and `/specworks-reopen` (closed change).

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

A closed change is picked the same way, from
`specworks list --archived --json` (by its name or its archive folder
`<date>-<name>`) when no active change has that name.

---

## Steps

1. **Pick the change and its trace**

   Pick the change (above), then:
   ```bash
   specworks status --change "<ref>" --json
   specworks trace --change "<ref>" --json
   ```
   `status` says whether it is closed (`"archived": true`) and gives its
   folder (`path`). `trace` gives,
   per requirement and criterion, its tasks and the `file:line` of its tests
   (`@ac`) and code (`@req`); for a closed change it reads today's code and
   lists in `changed` the locations whose file changed since the close
   (`changedSinceClose`, or a note when that cannot be told).

   The open findings, `I<n>` among them:
   - an open change: `specworks cycle --change "<ref>" --json` lists them;
   - a closed change: `cycle` refuses an archived change, so read the open
     `- [ ] I<n>` lines of `inspection.md` in its archive folder (`path`),
     when there is one.

   Never run `trace --write`: inspection writes nothing but inspection.md.

2. **Say why**

   In three or four lines, from proposal.md's Why and What Changes: the
   problem, and what the change does about it. Then how many blocks there
   are to walk.

3. **Build the blocks and rank them**

   - One block per scenario of the delta specs (`Scenario: AC-...`), with its
     requirement. A change marked skip-specs has no scenarios: one block per
     task of tasks.md instead, each with the part of the diff that carries it
     out (`git diff <base>...HEAD` for an open change; for a closed one, the
     commits `git log --oneline --grep "<ref>:"` lists, read with
     `git log -p`).
   - One more block for a doubt that spans several of them (two requirements
     that read the same, a design decision the code follows in one place
     and not in another), when there is one.
   - Open `I<n>` findings routed to inspect (`done in review:` under them)
     come first, before any block: each is one block, to confirm.

   Rank the blocks **most uncertain and important first**:
   - uncertainty: a hint to give (below), a test that looks weak for its
     THEN, code changed since the close, a design decision not obviously
     followed;
   - importance: ADDED or MODIFIED behaviour before unchanged, error and
     security paths, how much code depends on it.

   Each step says in one line why it is where it is (e.g.
   `Rank 1 of 9: MODIFIED, error path, its test checks only the status`).

4. **Walk one block per step**

   For a scenario:
   - **WHEN** and the code that implements it: the requirement's `@req`
     locations, cut to the lines that matter for this WHEN, each with its
     `file:line` (and `(changed since close)` when trace marks it);
   - **THEN** and the test that proves it: the criterion's `@ac` test, cut
     to the lines that check this THEN, with its `file:line`;
   - the design excerpt that argues for it (a Decision of design.md), when
     there is one;
   - **at most three hints**, one line each, only when there is something to
     say: a question the reviewer should ask, an unclear or ambiguous spot in
     the code or the spec, or the alternative readings when more than one
     fits. A clear scenario passes without comment.

   A block with no test or no code says so: that is a hint, not a gap to
   fill. Show only what the step needs; more is one option away. End every
   step with:
   ```
   1. Next block (recommended): <the next block's one-line rank reason>
   2. Add a note
   3. Show more
   4. Come back later
   5. Jump to a requirement
   6. Stop here
   ```
   - **Show more**: the whole function, the other tests of the criterion, or
     the rest of the design decision; then the same options.
   - **Come back later**: the block is deferred; go on with the next one.
   - **Jump to a requirement**: ask which (`REQ-...` or `AC-...`) and walk
     its blocks next.
   - **Stop here**: go to step 7. Stopping is a normal end, at any step.

5. **A note becomes a finding**

   On **Add a note**, take the reviewer's note in their words, propose its
   type and route (a `question` for review to answer when it is a doubt,
   otherwise `spec-gap`, `design-gap`, `test-gap`, `code-gap`, `tag` or
   `quality`, each with `back to <step>: ...`), ask, and on yes write it:
   ```bash
   specworks finding add <type> "<the note, with file:line>" --proposal "back to <step>: <what to change>" --artifact inspection --change "<ref>"
   ```
   When the note comes with a change to propose (a code diff, a
   requirement's new text), pass it on standard input with
   `--suggestion - --lang <diff|markdown|...>` (or `--suggestion <file>` for a
   file the reviewer already has):
   ```bash
   specworks finding add code-gap "<the note>" --proposal "back to code: <what to change>" --artifact inspection --suggestion - --lang diff --change "<ref>" <<'EOF'
   <the suggested diff>
   EOF
   ```
   The suggestion is shown under the finding and routes nothing. For a
   closed change, the finding goes into its archive folder.

   An open `I<n>` routed to inspect (step 3) is confirmed when its work is
   there in the code: on the reviewer's yes,
   ```bash
   specworks finding close I<n> --change "<ref>" "<what was confirmed>"
   ```
   which ticks it with `confirmed in inspect:`. When the work is not there,
   leave it open and add a new note that says what is missing.

6. **Round the circle**

   After the last block, go back to the deferred ones (**come back later**),
   with what was learned since, until none is left or the reviewer says
   stop here.
   The circle is the reviewer's to break: never end it for them.

7. **End**

   Say how many blocks were walked out of how many, and the notes written
   (their IDs).

   **No notes: nothing is written.** The human review is its own record
   (e.g. the pull request's approval). End with:
   ```
   1. Stop here (recommended): nothing to act on
   2. Inspect another change
   ```

   With notes, commit inspection.md:
   ```bash
   git status --short
   specworks commit --change "<ref>" --message "<ref>: inspect"
   ```
   `specworks commit` stages every file changed since the change's phase
   started: when `git status` shows other changed files besides
   inspection.md, name them and ask before committing. Follow the project's
   commit convention (`--message`, `--trailer`) and never push. Then hand
   over:
   - an open change:
     ```
     1. /specworks-review <ref> (recommended): review decides each note and routes it
     2. Stop here
     ```
   - a closed change: inspection.md is the problem to reopen it with.
     ```
     1. /specworks-reopen <ref> (recommended): with inspection.md as the problem
     2. Stop here
     ```

---

## Guardrails

- Read-only but for inspection.md: no fix, no spec, test or code edit, no
  `trace --write`, no Decision on a note.
- Every excerpt names its `file:line`; on a closed change it says when the
  file changed since the close.
- Hints only when there is something to say, and at most three a step.
- Notes are written only with `specworks finding`, never by editing
  inspection.md's lines.
- The reviewer breaks the circle; stopping early is a normal end.
