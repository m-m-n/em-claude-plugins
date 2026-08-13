# Implementation Plan: implement-routeback-gate

## Overview

Documentation-only change: correct Step I.2.c's route-back-to-planning path in
`em-workflow/references/implement-phase.md` (reachability, gate condition,
merged-task terminal, delegation citation), extend the Branch & Worktree
Model's exit-4 call-site enumeration, add a document-contract test module
guarding the new wording, and patch-bump the plugin version.

## Technology Stack

- **Documents**: Markdown protocol references under `em-workflow/references/`
  (English narrative) — the deliverable itself.
- **Tests**: Python standard-library `unittest`, run by
  `python3 -m unittest discover -s tests`. Structural/textual assertions over
  protocol markdown, following the existing document-contract test modules
  under `tests/`.
- **New dependencies**: none. No package manifest is touched, so
  `project.license: none` raises no license constraint for this feature.

## Layer Structure

Three document layers, with a one-way dependency direction:

1. **Owner SSOT documents** — `em-workflow/skills/develop/SKILL.md` (Step B's
   stop-condition-3 precedence) and `em-workflow/references/workflow-patch.md`
   (`replace_all` permission conditions). Out of scope for this feature: they
   are cited, never edited, never restated.
2. **Phase protocol document** — `em-workflow/references/implement-phase.md`.
   The only protocol document edited. It may cite layer 1; it must not copy
   rules owned there.
3. **Document-contract tests** — `tests/`. Tests depend on layers 1–2 by
   reading them; the documents never depend on the tests. A test asserts on
   the *contract* the document must express (presence, absence, relative
   ordering, byte-identity where required), not on incidental prose.

## Shared Components

The two tasks have disjoint file sets and share no component. What they share
are the following invariants, which each task must satisfy independently
inside its own worktree.

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| Feature-wide change containment | Keep the change's name-only file list to `em-workflow/references/implement-phase.md`, `em-workflow/.claude-plugin/plugin.json`, `feature-docs/implement-routeback-gate/**`, and the test module added by this feature | Pre: the task's declared `files` set. Post: no file outside that set is created, modified or deleted by the task | task0001, task0002 |
| Independent green suite | `python3 -m unittest discover -s tests` passes inside each task's own worktree, with no dependence on any other task's changes | Pre: the worktree contains only this task's edits on top of the integration base. Post: exit code 0, and no assertion in the suite requires another task's file | task0001, task0002 |
| Untouched-SSOT set | `em-workflow/skills/develop/SKILL.md`, `em-workflow/references/rework-task-synthesis.md`, `em-workflow/references/workflow-patch.md`, `em-workflow/references/contracts/*`, `tests/test_review_implement_develop_lock_contracts.py`, `tests/test_develop_skill_rewiring.py`, root `.claude-plugin/marketplace.json` | Pre/Post: byte-identical before and after every task | task0001, task0002 |

## Conventions

- **SSOT citation, never restatement**: implement-phase.md names the owning
  document and clause for any rule owned elsewhere, and states only the
  consequence local to the implement phase.
- **Commit instructions go through `commit-docs.sh`**: no line of
  implement-phase.md may begin with `git ` while also containing `commit` or
  `add -A`. Worktree/branch cleanup lines (`git worktree remove`,
  `git branch -D`) are unaffected by that rule and stay as they are.
  Every `commit-docs.sh` call site states its expected-tip third argument the
  same way the file's existing call sites do, and points at the Branch &
  Worktree Model's exit-4 recovery rule.
- **Heading literals are test anchors**: existing document-contract tests
  slice implement-phase.md on exact headings (`### I.2.b: Wake phase`,
  `### I.2.c: Failed handling`). Heading text is byte-stable; edits happen
  inside sections.
- **Test module naming**: `tests/test_<topic>.py`, one module per feature
  topic, module-level constants resolving the plugin root relative to the
  test file's own location — the pattern the existing document-contract
  modules already use.
- **Assertion style**: assert the presence of the semantic tokens a
  requirement names, the absence of the strings a requirement removes, and
  relative ordering by position within a section slice. Whole-paragraph
  equality is used only where a requirement literally demands byte-identity.
- **Prose style**: English narrative, existing bullet structure and backtick
  conventions, no justification beyond what the requirement states.

## Cross-task Design Decisions

### D1: implement-phase.md edits stay in a single task

Every edit to `em-workflow/references/implement-phase.md` (I.2.c's route-back
bullet, its gate sentence, its merged-task branch, its delegation sentence,
and the Branch & Worktree Model's exit-4 call-site enumeration) belongs to
task0001. The tasks of this feature run fully in parallel and merge
independently; splitting one file across two tasks would guarantee a merge
conflict for no benefit. Affected tasks: task0001.

### D2: the document-contract tests ship with the document edit

The new test module asserts on the edited wording of implement-phase.md, so it
can only be green in a worktree that also contains those edits. It is
therefore part of task0001, not a separate task. Affected tasks: task0001.

### D3: no test may assert a specific plugin version

The version bump (task0002) and the document edits (task0001) live in
separate worktrees that never see each other before merge. Consequently no
test added by this feature may assert a literal value of
`em-workflow/.claude-plugin/plugin.json`'s `version` field: such an assertion
would fail in task0001's worktree, and would additionally have to be edited
on every future bump. Verification of the bump is an inspection item in
VERIFICATION.md instead. Affected tasks: task0001, task0002.

### D4: existing regression suites are contracts, not editable collateral

`tests/test_review_implement_develop_lock_contracts.py` and
`tests/test_develop_skill_rewiring.py` are not modified by any task. If an
intended edit would break one of them, the edit is wrong — not the test. In
particular the wake-phase slice (the text between the `### I.2.b: Wake phase`
and `### I.2.c: Failed handling` headings) and the exit-4 assertions
(`exit-4 recovery`, `retry \`commit-docs.sh\` once`, `second exit 4`,
`stops the phase`) must survive the edit. Affected tasks: task0001.

### D5: version bump scope

Per this repository's convention, a plugin's version lives only in
`em-workflow/.claude-plugin/plugin.json`; the root
`.claude-plugin/marketplace.json` entries carry no `version` field and are
therefore untouched. Affected tasks: task0002.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Edit breaks the `### I.2.c: Failed handling` slice anchor used by an existing regression | Low | High (existing suite red) | Heading text byte-stable; run the full suite before completing (D4) |
| A new commit instruction is written as a raw git line, violating the no-bare-commit audit | Medium | High (existing suite red) | Route the instruction through `commit-docs.sh` (Conventions) |
| The exit-4 bullet rewrite drops a substring an existing assertion depends on | Medium | High | Extend the call-site enumeration only; leave the recovery sentences intact (D4) |
| New assertions bind to incidental prose and turn brittle | Medium | Medium | Assert semantic tokens, absences and ordering; byte-identity only where required (Conventions) |
| Version bump trips an unrelated plugin-invariant test | Low | Medium | task0002 runs the full suite in its own worktree; a failure is reported, not worked around by editing the invariant test |
| Removing the rework/`append` sentence leaves the merged-task case without a terminal | Low | High | The merged-task branch explicitly names the `failed` retention and develop's stop condition 3 as its terminal (task0001 AC-5) |

## Open Questions

- [ ] Three verification items (plugin version value, prose-style
      consistency, changed-file name-only audit) have no automated coverage:
      the project defines no build/format/e2e command, and pinning the
      version in a test is forbidden by D3. They are recorded as inspection
      items in VERIFICATION.md and are resolved by the verify phase.
