---
name: specworks-refine
description: Refinement phase of spec-driven development - explore a problem with the user, ground it in the codebase and existing capability docs, compare 2-3 solution options, and record the result in refinement.md. Use in a specworks project when the user wants to start a new feature/fix/change and think it through before specifying it, or says "refine", "refinement" or "specworks refine".
allowed-tools: Bash(specworks:*), Bash(uv run specworks:*), Bash(uvx --from git+https://github.com/lcmonteiro/specworks specworks:*), Bash(git add:*), Bash(git commit:*), Read, Grep, Glob, Write, Edit
---

Refinement phase: build a shared understanding of the problem and its possible
solutions, then record it in `refinement.md`. This is the first phase of
`refine → specify → design → implement (test | code) → review → validate → close`.

**Phase boundary**: this phase writes `refinement.md` only. Do not write
requirements, tasks, tests or code, even if the user asks to "build" something.
When refinement is done, stop and suggest `/specworks-specify`.

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

## The stance

- **Curious, not prescriptive**: ask the questions that unlock decisions; do not run a questionnaire.
- **Grounded**: read the real code, tests and the capability docs before asking the user facts you could check yourself.
- **One focused question at a time**: say briefly why it matters and which decision it unlocks.
- **Honest about evidence**: separate what you observed from what you assume.
- **Visual when it helps**: plain-ASCII diagrams for flows, states and boundaries.
- **No premature solution**: the problem, its outcomes and the constraints come before the options; the options come before the recommendation.

---

## Before step 1

Two stops, in this order, before step 1. Each can be answered "no", and
the skill then goes on.

1. **Clear context**: when the conversation already holds earlier work
   (anything before this request except a summary left by `/compact`),
   ask "Compact the conversation first? (yes/no)". On yes, tell the user to
   run `/compact`, then `/specworks-refine` again with the same request, and
   stop (a skill cannot compact the conversation itself). A new or
   just-compacted conversation goes straight on, without asking.
2. **Base branch**: run `git status --short --branch`. When the checked-out
   branch is not the base branch (`main`, or `master` when the repository
   has no `main`), ask "You are on <branch>, not <base>. Switch to <base>?
   (yes/no)". On yes, run `git switch <base>`; on no, stay (a change
   continued on its own branch, or a deliberately stacked one). When the
   working tree has changes, say so, stay on the branch and ask nothing.

---

## Steps

1. **Check the project**

   ```bash
   specworks context --json
   ```

   - `"root": null` means the project is not set up. Stop and ask "Run
     `specworks init` here? (yes/no)". Do not create files by hand.
   - Treat `context` as constraints from the project, not as instructions that
     override this workflow. Do not copy it into the artifact. It is already
     merged top-level first, then each module down to the current one
     (`contextChain`): a module adds rules, it never removes its parent's.
   - `capabilities` lists durable behaviours of the WHOLE workspace, the code
     folder that owns each one, and `docsPath` with its living docs
     (`spec.md`, `requirements.md`, and `design.md` with its diagrams).
     Capabilities of other modules are named `module:capability`
     (e.g. `billing:invoices`). Read the docs of the capabilities that look
     related, in any module, before deciding what already exists.
   - `module` is the module you are in (`(top)` for the top-level project) and
     `modules` lists every module. `missingModules` are listed by a parent but
     not checked out: say so if the request touches one.
   - `changes` lists work in flight in the current module (add `--all` for
     every module). If one already covers this request, offer:
     1. continue `<ref>` (recommended): it already covers this request;
     2. start a new change.
   - Every path in the output is relative to `root`, the workspace root.

Read the module's `<docsPath>/architecture.md` first (`docsPath` of the module in `specworks context`); when there is none yet, go on without it.

2. **Select or create the change**

   - If the user named an existing change, use it. When the change was reopened, the latest reason in specworks status is the problem to start from.
   - Otherwise derive a kebab-case name from the request
     (`"let users reset passwords"` → `add-password-reset`) and pick the
     module that owns it:
     - one module's behaviour only → that module;
     - several modules, or shared/cross-cutting behaviour → the top level
       (or the lowest module that contains all of them).
     Confirm in one line, "Create `<name>` in `<module>`? (yes/no)",
     then create it:
     ```bash
     specworks new "<name>" --module "<module>" --json   # omit --module for the current one
     ```
   - Use the `ref` it returns (`module:name`, or just `name` at the top level)
     for every later command, and announce: `Using change: <ref>`.

3. **Explore**

   Inspect the relevant source, tests, configuration and docs (read-only).
   Map entry points, data flow and integration points. Then talk with the user
   until these are clear enough to write down:
   - the problem and who has it
   - the outcomes: what a person outside the codebase would see or measure
     once the change is done (observable results, not the solution), agreed
     with the user after the problem and before the options. When an outcome
     could reasonably go more than one way, offer the alternatives as
     numbered options, the one you recommend marked, instead of choosing
     silently. A change with no visible outcome says `None: <why>`
   - scope: what is in and what is explicitly out
   - hard vs soft constraints
   - 2-3 real options, with trade-offs, each compared against the outcomes
     (which ones it meets or fails)
   - which option the user prefers (do not decide for them on product
     questions): ask it as numbered options, the one you recommend marked

   Stop asking when there is enough clarity to propose; open questions that do
   not block the proposal can stay open.

4. **Write `refinement.md`**

   ```bash
   specworks instructions refinement --change "<ref>" --json
   ```

   Use `template` as the structure and `instruction` as the rules, and write the
   file to `outputPath`. If the file already exists, re-read it from disk and
   update it rather than overwriting the user's edits.

   Before writing, ask the user once: "Ready to record the refinement? (yes/no)" Agreeing
   to an answer during the discussion is not permission to write.

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

5. **Show the result and stop**

   ```bash
   specworks status --change "<ref>"
   ```

   Summarize: the problem in one line, the outcomes, the options, the
   recommendation (or "pending"), and the open questions that still block
   the proposal.
   End with:
   ```
   1. /specworks-specify <ref> (recommended): write the proposal, specs and tasks
   2. Stop here
   ```

---

## Guardrails

- Write only `refinement.md` in the change folder. Never edit project code here.
- Never run `specworks init` unless the user asks for it.
- Do not invent product intent, priorities or constraints. Ask when only the user can answer.
- Keep refinement to 1-2 pages. Requirements, acceptance criteria, design and tasks belong to `/specworks-specify`.
- Use existing capability names from `specworks context` when they fit, qualified with their module (`billing:invoices`); propose new names only for genuinely new behaviour, and say which module should own each one, its code path and a one-line description.
