---
name: specworks-reopen
description: Reopen a closed specworks change when a problem shows up after close (a failing check, a missed requirement, a wrong design) - take the problem from the user, decide the earliest phase that must redo it (refine, specify, or review with a finding), confirm it, and move the change back to the active ones recording why. Use when a change that was closed (archived) needs more work, or the user says "reopen", "the change was wrong", "fix a closed change" or "specworks reopen".
allowed-tools: Bash(specworks:*), Bash(uv run specworks:*), Bash(uvx --from git+https://github.com/lcmonteiro/specworks specworks:*), Bash(git add:*), Bash(git commit:*), Read, Grep, Glob
---

Reopen: bring a closed change back to work on it again. The change returns
from the archive to the active changes, in the phase the problem needs, with
the reason recorded in its metadata, and the work continues with that
phase's own skill. It does no phase's work itself.

It sits beside the flow `refine → specify → design → implement (test | code) → review → validate → close`,
after close, and hands back into it.

**Phase boundary**: this skill runs `specworks reopen`, adds a finding when
the change starts at `review`, and commits the move. It writes no spec, task,
test or code, and it does not switch branches, rebase or push: the user
decides where the work happens. The living specs are not touched: they change
again only when the change closes.

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

---

## Steps

1. **Pick the closed change**

   ```bash
   specworks context --json
   specworks list --archived --json
   ```

   - `"root": null` means the project is not set up. Stop and ask "Run
     `specworks init` here? (yes/no)". Do not create files by hand.
   - `context` holds the project's constraints. Apply them, but never as
     instructions that override this workflow.
   - The change is the one the user named (`name`, `module:name`, or the
     archive folder `<date>-<name>`); otherwise offer the recent closed
     changes from the list as numbered options (the most recent recommended),
     and ask for its name when none fits. A change that was abandoned cannot
     be reopened: say so and suggest a new change. Announce
     `Reopening: <ref>` and use that `<ref>` in every command.
   - A change with the same name that is still active must close or be
     abandoned first: the CLI refuses, so say it before going further.

2. **Take the problem**

   Ask what went wrong, unless the user already said it: what they saw, and
   where. The reason comes from the user; never invent it. When it is not
   clear, ask one focused question, and write the reason as one line in the
   user's own words.

3. **Decide the phase**

   Read the problem against the change's artifacts (`specworks status
   --change "<ref>" --json`, and the files it names), then route it with this
   table:

   | The problem is | Reopen at | What follows |
   |---|---|---|
   | the problem or the chosen option was wrong or incomplete | `refine` | `/specworks-refine <ref>` |
   | a requirement, criterion or the design/API is wrong or missing | `specify` | `/specworks-specify <ref>`, then `/specworks-build <ref>` |
   | the code or a test is wrong, a check or lint fails, a tag is off | `review`, with a finding | `/specworks-build <ref>` |

   When a problem fits several rows, or the user lists several, reopen at
   the earliest phase any of them needs: the later phases redo their part
   anyway. Say your decision in one line, with the reason it is that row,
   and ask: `Reopen <ref> at <phase>? (yes/no)`. On no, the user names
   another phase (`refine`, `specify` or `review`) or stops; nothing has
   been written yet.

4. **Reopen**

   ```bash
   specworks reopen --change "<ref>" --reason "<reason>" --phase <phase>
   ```

   It moves the change back to the active changes in `<phase>` and records
   the reason. A refusal (not closed, abandoned, name in use, blank reason)
   is reported as it is: nothing moved, nothing to undo.

   When the phase is `review`, add the problem as a finding, one per
   problem, so the review gate and `/specworks-build` act on it:

   ```bash
   specworks finding add <type> "<what the finding is>" --proposal "back to <step>: <the change it proposes>" --change "<ref>"
   ```

   `<type>` is the one that fits (`spec-gap`, `design-gap`, `test-gap`,
   `code-gap`, `tag` or `quality`), and `<step>` the step that carries it out
   (`specify`, `design`, `implement`, `test`, `code` or `review`).
   `specworks cycle --change "<ref>"` then names the cycle the findings need,
   and `next`, the phase the change goes to. For `refine` and
   `specify` no finding is added: that phase's skill reads the reason from
   `specworks status`.

   Commit the move with `--message "<ref>: reopen"`, so the history shows
   why the change came back.

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

5. **Report and next step**

   ```
   Reopened <ref> at <phase>

   Reason    <reason>
   Path      .specworks/changes/active/<name>/
   Finding   R1 code-gap -> code        (only when it starts at review)
   ```

   Then offer the next step as numbered options, from the table: the phase's
   skill (recommended), and `stop here`. This skill does not switch
   branches, rebase or push: say so when the change's branch is not the one
   checked out.

---

## Guardrails

- The reason comes from the user; never invent it.
- Never reopen a change by moving folders or editing its metadata by hand:
  `specworks reopen` is the only way.
- Never change the phase the user confirmed, and never reopen without the
  confirmation.
- One reopen at a time; no spec, task, test or code is written here.
