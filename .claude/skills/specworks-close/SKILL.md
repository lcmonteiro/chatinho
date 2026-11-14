---
name: specworks-close
description: Close phase of spec-driven development - fold a verified change into the project's living documentation next to the code (spec, requirements index, design, diagrams), register new capabilities, and archive the change. Use when a specworks change has passed validate and the user wants to finish it, or says "close the change", "archive the change", "merge the specs" or "specworks close".
allowed-tools: Bash(specworks:*), Bash(uv run specworks:*), Bash(uvx --from git+https://github.com/lcmonteiro/specworks specworks:*), Bash(git add:*), Bash(git commit:*), Read, Grep, Glob, Write, Edit
---

Close phase: turn what the change decided into the project's lasting truth.
The deltas are merged into each capability's living docs next to its code,
the design knowledge worth keeping moves there too, and the change folder is
archived as the record of how it happened.

It is the last phase of `refine → specify → design → implement (test | code) → review → validate → close`.

**Phase boundary**: edit only the living docs (`<capability path>/<docs_dir>/`)
and, for new capabilities, the config. No code, tests or delta specs change
here; if something is wrong, go back to the phase that owns it.

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

1. **Pick the change and start the phase once it passes validate**

   Pick the change (above), then:
   ```bash
   specworks start close --change "<ref>"
   ```

   It runs `gate validate` (the same checks as `specworks validate`) and moves
   the change to close only if it passes. If it fails, stop and point to the
   phase each failed check names (`-> /specworks-<phase>`; `/specworks-validate`
   explains them). `specworks close` refuses a change that does not pass.

   The gate cannot see what `/specworks-validate` found by reading (step 3).
   If validate reported FAIL for this change in this conversation, its
   reading included, and nothing changed since, stop as well: closing it
   anyway would make `/specworks-validate` + `/specworks-close` close what
   `/specworks-done` refuses.

2. **Register new capabilities**

   For every capability under "New Capabilities" in proposal.md (or any delta
   whose `specworks spec show <ref> --json` says `"new": true`), ask "Register
   `<name>` in `<module>` at `<code path>`? (yes/no)" (on no, take the
   user's module and path), then:
   ```bash
   specworks capability add <name> --path <code path> [--module <module>] [--prefix <P>] [--description "<one line>"]
   ```
   Keep the prefix the delta's IDs already use (`spec show` gives it), or
   the IDs no longer match.

3. **Show the merge plan and get a go-ahead**

   ```bash
   specworks close --change "<ref>" --dry-run --no-run
   ```

   `--no-run` skips the test, lint and typecheck commands: step 1 just ran
   them and nothing but the config changed since. Step 5 runs them again
   before anything is written.

   Show, per capability: the living spec it writes (new or existing) and the
   requirements added, modified and removed. Ask: "Merge and archive? (yes/no)"
   Nothing is written until the user agrees.

4. **Update the living design and its diagrams (before archiving)**

   The change folder moves in the next step, so do this first. For each
   capability the change touched, in its docs folder (`docsPath` from
   `specworks context --json`):
   - **design.md**: the lasting design of the capability as it is now, not the
     story of this change: Overview, Decisions (each with why, alternatives,
     and the change that introduced it: `(add-password-reset)`), Interfaces
     (public APIs, data shapes, events), Constraints. Fold in the decisions
     from the change's design.md that still hold; drop the ones review.md
     overturned; leave out task-level detail.
   - **block diagram**: `design.md` keeps one block diagram of the capability
     as it is now. When the change's design has a block diagram of this
     capability (`diagrams/<capability>-blocks.d2`, a structural change), it
     replaces the living one in `<docsPath>/diagrams/` (the `.d2` source;
     update it if review changed the design) and is embedded in the living
     `design.md`; when it has none for this capability, or says "No
     structural change", the living one stays as it is.
   - **other diagrams**: copy the change's diagrams that describe the system
     as it now is into `<docsPath>/diagrams/` too. Render them all and embed
     them:
     ```bash
     specworks diagrams --dir "<docsPath>"
     ```
   Create the files if they do not exist yet. Keep them short and current;
   they are what the next refinement reads.

   Then the module's architecture, as below (`docsPath` of the change's
   module in `specworks context --json`); `specworks close` refuses a change
   whose module has none, and its dry run (step 3) names it under `missing`:
**The architecture**: the top level and every module have one architecture,
`<docsPath>/architecture.md` (`docsPath` of the module in `specworks context --json`),
with one block diagram,
`<docsPath>/diagrams/architecture-blocks.d2`,
rendered with `specworks diagrams --dir "<docsPath>"`. It is the picture of the
whole module that people and the phases read first; the list of capabilities,
with their paths, stays in `specworks context`. Its sections:
```markdown
# Architecture: <project or module>

## Overview
<what the system is for and how it is put together, in a few lines>

## Capabilities and how they interact
<one line per capability: what it uses from or gives to the others; each
module is one block, linking to its own `docs/architecture.md`>
<the block diagram `diagrams/architecture-blocks.d2`, embedded>

## Architectural decisions
<each decision that spans capabilities: what, why, and the change that made it `(<change>)`>

## Glossary
<each term with one meaning, under one name>
```
Keep it to about 150 lines: merge or drop entries rather than grow it.
At every close, check it against the change.
Update it when the change adds or removes a capability, changes what flows between capabilities, adds a decision that spans capabilities, or adds a term; otherwise leave it as it is.
When it is missing, write it now, before `specworks close`.

5. **Merge and archive**

   ```bash
   specworks close --change "<ref>"
   ```

   This applies every delta to `spec.md` (ADDED appended, MODIFIED replaced in
   place by ID, REMOVED deleted, everything else kept), regenerates
   `requirements.md` (index of requirements and criteria, plus a History line
   for this change), sets the phase to `done` and moves the change to
   `.specworks/changes/archive/<date>-<name>/`.

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

6. **Report and stop**

   Summarize: living docs written per capability (spec, requirements, design,
   diagrams), requirements added / modified / removed,
   capabilities registered, and the archive path. The living docs, the archive
   and the code are already committed together (above).

   When the change was a baseline (`baseline-<capability>`), name what is
   next: the next capability with 0 requirements in `specworks spec list`
   (`/specworks-baseline <capability>`), or, when none is left, that every
   capability now has a living spec and new work starts with
   `/specworks-refine` (the waiting `fix-*` changes of suspected bugs first).

**Pushing**: after the commit, offer to push the change's branch (the checked-out
one, from `git status`): ask `Push <branch>? (yes/no)`. On yes, run
`git push -u origin <branch>` (never pre-approved: the user is asked either
way) and relay the "create a pull request" link the remote prints. When it
prints none and `origin` is a `github.com` or `gitlab.com` URL, build the link:
`<repo URL>/pull/new/<branch>` for GitHub,
`<repo URL>/-/merge_requests/new?merge_request[source_branch]=<branch>` for
GitLab; otherwise only report the push. On no, say the branch stays local.

Once the push question is answered, end with the next steps as numbered
options, for example:
```
1. /specworks-baseline <next capability> (recommended): after a baseline, when one is left
2. Stop here
```
(after the last baseline: `/specworks-refine <fix-ref>` for the first
waiting bug change instead of option 1).

---

## Guardrails

- Never close a change that does not pass `specworks validate`.
- Do not edit spec.md or requirements.md by hand; they are produced by
  `specworks close` from the deltas. Change requirements through a new change.
- Living docs describe the system as it is now. History belongs in the
  archive and in requirements.md's History, not in design.md prose.
- Ask before merging (step 3) and before registering a capability (step 2).
