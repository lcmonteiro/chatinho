---
name: specworks-baseline
description: Baseline one capability of a project that already has code - record the behaviour the code already has as requirements, tie them to the existing tests and code with @ac / @req tags, and hand the reviewed change over to /specworks-done (validate, then close) so the capability gets its living spec. No behaviour change. Use after /specworks-adopt, once per capability (each baseline closed before the next), whenever a specworks capability has no living spec yet, or when the user says "baseline", "baseline <capability>", "record what <capability> does today" or "specworks baseline".
allowed-tools: Bash(specworks:*), Bash(uv run specworks:*), Bash(uvx --from git+https://github.com/lcmonteiro/specworks specworks:*), Read, Grep, Glob, Write, Edit
---

Baseline: record the behaviour one capability already has, so later changes
can MODIFY its requirements instead of only ADDING them. A baseline is an
ordinary change named `baseline-<capability>` whose specs ADD the existing
behaviour. Its tests and code exist, so the test and code halves of
implement only add tags. This skill runs the change up to review; `/specworks-done` then
validates it and closes it, which writes the living spec exactly as for any
other change.

**One capability per run.** After `/specworks-adopt`, the capabilities are
baselined one after another, each closed before the next:

```
for each capability:
    /specworks-baseline <capability>
    /specworks-done baseline-<capability>     # validate, then close
```

When every capability has its living spec, each suspected bug the baselines
found (one change `fix-<name>` per bug, waiting in phase refine) is fixed
through the normal flow:

```
for each suspected bug change:
    /specworks-refine <ref>
    /specworks-specify <ref>
    /specworks-build <ref>
    /specworks-done <ref>
```

**Boundary**: a baseline changes no behaviour. It writes a change folder and
adds comment tags (and tests only for criteria no test covers); it never
fixes the code, even a bug it finds. A confirmed bug gets its own change,
with only a `refinement.md` (step 4).

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

1. **Pick the capability**

   ```bash
   specworks context --json
   ```

   - `"root": null`, or no capabilities: the project is not adopted yet.
     Stop and offer `/specworks-adopt`, which sets it up and maps the
     capabilities.
   - The capability is the one the user named. Otherwise list them:
     ```bash
     specworks spec list
     ```
     and offer the ones with 0 requirements (no living spec yet) as
     numbered options, in the order of the list, the first one
     recommended; go on with the user's pick. When every capability has
     requirements, say so and stop.
   - A capability that is not registered: stop and offer
     `/specworks-adopt` (or `specworks capability add`) first.
   - A change `baseline-<capability>` already in `changes`: continue it
     from its phase (`specworks status --change "baseline-<capability>"`)
     instead of creating a new one.

2. **Check the capability and create the change**

   ```bash
   specworks spec show "<capability>" --json
   ```

   A capability with requirements already has a living spec: it needs no
   baseline (offer `/specworks-refine` for what is missing).

   The test suite must be green: validate requires it, and a
   red suite cannot show that the baseline matches the code. Check it first:
   ```bash
   specworks run test
   ```
   If it fails, stop before creating anything: name the failing tests and
   offer:
   ```
   1. /specworks-refine fix-<tests> (recommended): fix the failing tests first, in their own change
   2. /specworks-baseline <another capability>: one whose tests pass
   3. Stop here
   ```
   Never narrow `commands.test` to hide the failures.

   Otherwise:
   ```bash
   specworks new "baseline-<capability>" --json
   specworks phase specify --change "baseline-<capability>"
   ```
   (`--module <m>` on `new` for a capability of another module.) Announce
   `Using change: <ref>` and use that `<ref>` in every command.

3. **Read the behaviour**

   Read the capability's code and its tests; requirements come from both:
   - existing tests: each one asserts behaviour someone decided on;
   - the code: public entry points, validation, error handling and side
     effects, including behaviour no test checks yet;
   - the README, docs, comments and changelog, to name and explain them.

   Record only observable behaviour (inputs, outputs, errors, side effects),
   not how the code does it. Keep a list of what looks like a bug or is
   unclear: it is not specified here (step 4). For each one, note the
   evidence: where it shows (file, function, test), what happens, and the
   correct behaviour; when more than one is plausible, the alternatives, with
   the one you recommend marked.

4. **Write proposal, delta spec and tasks**

   Use `specworks instructions proposal|specs|tasks --change "<ref>" --json`
   as `/specworks-specify` does, with these differences:
   - `proposal.md`: Why = "record the existing behaviour of `<capability>`";
     What Changes = "no behaviour change"; the capability under Modified
     Capabilities (it is registered); Out of Scope = the suspected bugs and
     unclear behaviour from step 3, each as a candidate for its own change.
   - The delta spec starts with `## Purpose` (one or two sentences: the
     capability has no living spec yet), then only `## ADDED Requirements`,
     IDs from `nextId`.
     Prefer fewer, meaningful requirements. A criterion read from the code
     alone is as valid as one a test shows; step 6 gives it a test, so
     do not mark it in the spec.
   - `tasks.md`: per requirement, one `[test]` task to tag the tests that
     check its criteria (`@ac`) and to write a test for any criterion with
     none, and one `[code]` task to tag the code that implements it (`@req`).

   ```bash
   specworks check --change "<ref>"
   ```

   Show the requirements and criteria table as `/specworks-specify` step 5
   does, with the source of each (the test that shows it, or `code only:
   <file>` for one that gets a new test in step 6), and the
   list of suspected bugs, numbered so the user can reject one by its
   number, each with its correct behaviour (or its alternatives, the
   recommended one marked) so the user confirms one. Ask: "Are these the right requirements, and are the listed bugs
   real bugs? (yes/no, or the numbers to change)". **Stop and wait** for
   the user to confirm: a baseline that records a bug as a requirement
   makes the bug the spec.

   Then give each bug the user confirmed its own change, so it outlives this
   baseline (a bug the user rejects gets none):
   ```bash
   specworks new "fix-<short-name>" --json      # --module <m> for a bug in another module
   specworks instructions refinement --change "<fix-ref>" --json
   ```
   Write its `refinement.md` at `outputPath` from the `template`: Problem
   and Context from the evidence (observed, with file and test), saying that
   the baseline of `<capability>` found it; `## Outcomes` = the behaviour the
   user confirmed; Options and Recommendation "Pending". Write nothing else in that change: it waits in phase refine until the
   bugs are fixed (step 9). In this baseline's proposal, name each bug's
   change ref under Out of Scope.

5. **Gate specify and record the API as unchanged**

   ```bash
   specworks trace --change "<ref>" --write
   specworks start design --change "<ref>"
   ```
   Write `design.md` with only:
   ```markdown
   ## Interfaces

   None: a baseline records existing behaviour and changes no API.
   ```
   For a capability with more than one component, add a `## Diagrams`
   section with a block diagram of its existing structure,
   `diagrams/<capability>-blocks.d2` (components as nested containers,
   connections labelled with what flows), following the
   D2 rules in `specworks instructions design --change "<ref>" --json`;
   close puts it in the capability's first living `design.md`. Render and
   embed it:
   ```bash
   specworks diagrams --change "<ref>"
   ```

6. **Tag the tests** (the test half of implement)

   ```bash
   specworks start implement --change "<ref>"
   ```
   Add `@ac <ID>` comments to the existing tests that check each criterion
   (one tag may list several IDs). Write a new test only for a criterion
   that none covers; it must pass against the current code (if it fails,
   the criterion is wrong or it is a bug: back to step 4, not a code fix).
   Tick the `[test]` tasks (`specworks task done --change "<ref>" <N.M>`),
   then run `specworks gate test --change "<ref>"`.

7. **Tag the code** (the code half of implement)

   Add `@req <ID>` comments where each requirement is implemented (the
   function or class that decides the behaviour, not every caller). Change
   nothing else. Tick the `[code]` tasks, then run
   `specworks gate code --change "<ref>"`.

8. **Review**

   ```bash
   specworks start review --change "<ref>"
   specworks review --change "<ref>" --json
   ```
   Write `review.md` (`specworks instructions review --change "<ref>" --json`).
   The only changed files should be tests and code that gained tags (and any
   new test); a code change other than a tag is a finding: undo it, then
   close the finding. Leave no finding open.

9. **Hand over to done**

   Show the summary: requirements and criteria recorded, tests tagged and
   added, files tagged, the bug changes created. Say: "The baseline of
   `<capability>` is reviewed. Run `/specworks-done
   baseline-<capability>` to validate it and write its living spec; then
   `/specworks-baseline` for the next capability." End with:
   ```
   1. /specworks-done baseline-<capability> (recommended): close it before the next baseline
   2. Stop here
   ```

   When this was the last capability without a living spec (`specworks spec
   list` shows no other with 0 requirements), also list, before those
   options, the bug changes still waiting, from every baseline:
   ```bash
   specworks list --all --json      # the fix-* changes in phase refine
   ```
   and add: "Once this baseline is closed, every capability has its living
   spec. Then fix each suspected bug through the normal flow, one change at a
   time: `/specworks-refine <ref>`, `/specworks-specify <ref>`,
   `/specworks-build <ref>`, `/specworks-done <ref>`. One that turns out not
   to be a bug is dropped with `specworks abandon <ref>`."

---

## Guardrails

- One capability per change, closed before the next one starts.
- Never change behaviour: no refactors, no bug fixes, no renames. A bug is
  reported (Out of Scope) and gets its own `fix-<name>` change, not fixed.
- Outside its own change folder, a baseline writes only the confirmed bugs'
  changes and their `refinement.md`.
- The user confirms the requirements and criteria before anything is tagged.
- Capability names, prefixes, IDs and delta paths come from the CLI
  (`spec show`, `instructions`), never invented.
- Record behaviour the code has, not behaviour it should have: what it
  should do is a new change, through `/specworks-refine`.
- Never edit the living docs (`<path>/<docs_dir>/`) by hand: `close` writes
  them.
