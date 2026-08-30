# Implementation Plan: recycled-task-id-contract

## Overview

Two parallel tasks with disjoint file sets: task0001 rewrites the
recycled-task-id contract in `em-workflow/references/implement-phase.md`
(adding a machine-readable hook classification table) and brings the test
suite up to a contract that actually fails on divergence; task0002 raises the
plugin version in both registries and pins it with its own test module.

## Technology Stack

- **Documentation SSOT**: Markdown — `em-workflow/references/implement-phase.md`
  is the normative source for the implement phase's protocol.
- **Tests**: Python standard library `unittest` only. No third-party package
  is introduced, so no new dependency and no new license enters the project
  (`project.license: none` — no license constraint applies; nothing to record
  beyond this line).
- **Runner**: `python3 -m unittest discover -s tests` from the repository
  root — the project's only runnable component command (no build, no format,
  no E2E command exists).

## Layer Structure

Three layers, with a one-way dependency direction:

1. **SSOT documentation layer** — `em-workflow/references/implement-phase.md`.
   States the recycled-task-id rule and hosts the machine-readable hook
   classification table. Depends on nothing.
2. **Test layer** — `tests/`. Reads layer 1 and layer 3 and asserts they
   agree. May depend on both layers below/above it, never the reverse.
3. **Hook implementation layer** — `em-workflow/hooks/*.py`. Read-only in
   this feature (NFR3). No file of this layer appears in any task's `files`
   list; a change here is a plan deviation, not an implementation choice.

The documentation layer never derives anything from the test layer: the
expected classification originates in layer 1 and is consumed by layer 2
(NFR4). Tests never restate a classification of their own.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| `em-workflow/references/implement-phase.md` | SSOT for the implement-phase protocol and the sole origin of the expected hook classification | Written by task0001 ONLY. Precondition for any reader: the document contains exactly one machine-readable hook classification table, locatable by a stable textual anchor. Postcondition of task0001's edit: every pre-existing assertion over this document in the other test modules still holds. task0002 may read it only for invariants that hold both before AND after task0001's edit; it must not assert on I.2.a or Supporting cast wording. | task0001 (writes), task0002 (reads, restricted) |
| Hook classification table (inside the document above) | Maps each of the four queue hooks named in I.2.a to whether it reads `tasks.{T}.status` | Row set = exactly the four queue hooks that I.2.a's classification sentence names; each row carries a repo-relative path reference to the hook source and one classification value drawn from a fixed two-value vocabulary ("reads" / "does not read"). An unknown classification value, a malformed row, or a path that does not resolve to an existing file is an error for any consumer — never a silent skip. | task0001 |
| Test suite (`tests/`, `python3 -m unittest discover -s tests`) | Single verification surface for the whole feature | Every task's own worktree must leave the FULL suite green — not merely the modules that task touched. Each task owns only its own new/edited modules; no task edits another task's module. | task0001, task0002 |
| Version registry pair (`em-workflow/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`) | Plugin version, duplicated in two places | Written by task0002 ONLY. Postcondition: both carry the identical version string, one patch increment above the pre-change value. | task0002 |

## Conventions

- **Test placement and naming** (NFR2): modules live at `tests/test_*.py`,
  classes are `Test<Behavior>`, methods `test_<condition>_<expected_result>`.
  Targets are referenced by repo-relative path, resolved from the module's own
  location — never by an absolute path and never by a current-working-
  directory assumption.
- **Standard library only** (NFR1): no third-party import in any test module.
  Importing a sibling module inside `tests/` is permitted (the discovery run
  puts `tests/` on the import path) and is not a third-party dependency.
- **Negative-proof discipline**: every new matcher gets a paired test proving
  it flags the wording/state it is meant to reject. A matcher that cannot
  fail is not a test. This is the established pattern in this suite
  (`TestValidationDetectsRegressions` / `TestPreChangeSampleGuards`).
- **Durable assertions over fixed literals**: a version assertion states an
  invariant that survives the next unrelated bump (family fixed, patch above
  a recorded baseline), never a hard-coded exact version. Same for any
  count-based guard: assert a floor, not an exact number, unless the exact
  number is itself the requirement.
- **No classification restated in test code** (NFR4): any test that needs to
  know which hooks read `tasks.{T}.status` obtains that from the parsed
  documentation table. Hook names and their classification are never spelled
  out as literals in test code. Non-vacuity guards (e.g. "at least one row of
  each classification value exists") are structural, not classifications, and
  are permitted.
- **Documentation edits are surgical**: change the wording the requirements
  name and nothing else. Reflowing an untouched paragraph is a regression
  risk here, because several pre-existing modules assert on exact line-wrap
  literals of this document.

## Cross-task Design Decisions

### D1: Two tasks with disjoint file sets

`em-workflow/references/implement-phase.md` and the two version registries
are the most conflict-prone files in this repository. Tasks run fully in
parallel with no ordering, so every file is assigned exactly one owning task:
task0001 owns the SSOT document and the two test modules that assert on it;
task0002 owns the two version registries and its own version-bump test module.
No file appears in both tasks' `files` lists, so the two merges cannot
conflict. Affected tasks: task0001, task0002.

### D2: The documentation edit and the test update are one task

The wording task0001 rewrites is asserted on, verbatim, by
`tests/test_recycled_task_id_consistency.py` today. Splitting the rewrite
from the test update would leave BOTH halves red in their own worktrees
(each half needs the other), which the "task done = tests pass" contract
forbids. They are therefore a single task, together with the new pin module
that consumes the table the same edit introduces. Affected tasks: task0001.

### D3: The classification table is the single origin of the expected classification

The table added to `implement-phase.md` is the only place the expected
per-hook classification is written down (NFR4). Both the new pin test and the
split assertions in `TestRecycledTaskIdRuleScopedToOrchestrator` derive their
expectations by parsing it, so a one-sided change — documentation only, or
implementation only — makes a test fail. The parse step is defined ONCE and
shared by both consumers; duplicating it would reintroduce two sources of
truth by the back door. Affected tasks: task0001.

### D4: Hook behaviour is frozen; the divergence is recorded, not fixed

No hook source is in any task's file set (NFR3). The known divergence — the
hooks classify a task as unlaunched purely from the absence of a journal
event for that id, without the `status != merged` condition the orchestrator's
own selection rule carries — is recorded in I.2.a with its reason, so the
SSOT stops reading as a promise of protection the hooks do not provide. This
is a documentation change only; the runtime path is untouched. Affected
tasks: task0001.

### D5: Pre-existing document-contract modules must survive

Thirteen test modules under `tests/` read
`em-workflow/references/implement-phase.md`, several of them asserting exact
line-wrap literals, paragraph byte-identity and section orderings. The
feature's own acceptance depends on the FULL suite passing, so both tasks
treat those modules as untouchable and as constraints on what the edit may
disturb. task0002's new module in particular must assert only invariants that
hold both before and after task0001's edit, because the two tasks merge in an
unspecified order. Affected tasks: task0001, task0002.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| The I.2.a rewrite breaks a pre-existing document-contract module (line-wrap literal, byte-identical paragraph, section ordering) | High | High — the feature's acceptance is the whole suite passing | Before editing, enumerate every module that reads this document and every literal it asserts; keep edits surgical; run the whole suite, not just the touched modules (D5) |
| A text-search-based observation rule misclassifies a hook because the file mentions the workflow state file only in prose | High | High — the pin test would pin the wrong fact and look green | The observation rule ignores comments and docstrings and looks only at executable content; the module carries a negative proof that the rule discriminates (task0001 design) |
| The pin test degenerates into a tautology (empty table, empty group loop) | Medium | High — a silently vacuous pin is worse than no pin | Non-vacuity guards: the parsed table must yield at least one row of each classification value, every parsed path must resolve to an existing file, and each group assertion asserts its group is non-empty before iterating |
| task0002's version-bump module asserts wording that task0001 changes | Medium | Medium — green in isolation, red after both merge | D5: task0002 asserts only pre/post-invariant facts about the document, or nothing about it at all |
| Under-specified table shape leads the parser and the table to disagree | Low | Medium | Both are produced by the same task; the table contract (row set, path form, two-value vocabulary, stable anchor) is pinned in Shared Components above |

## Open Questions

- [ ] None blocking. Every requirement (FR1-FR6, NFR1-NFR4) is `ok` in
      workflow.yaml and no TBD remains.
