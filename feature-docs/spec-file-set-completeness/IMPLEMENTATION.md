# Implementation Plan: spec-file-set-completeness

## Overview

Two markdown template documents (`spec-document.md`, `requirements-document.md`)
gain an equivalent "declared change set" statement whose fixed default
membership is `feature-docs/{feature}/**` and `test-docs/{feature}/**`, the
plugin version is bumped in both registries, and four new stdlib-only
`unittest` document-contract modules pin the result. No executed behaviour
changes (NFR1).

## Technology Stack

- **Language**: Python 3 — verification only, standard library `unittest`
  discovered by `python3 -m unittest discover -s tests` from the repository
  root. No build command, no format command and no E2E harness is defined by
  this project; nothing in this feature adds one.
- **Documents**: Markdown, edited inside each template's outer fenced
  template body.
- **Registries**: JSON (`plugin.json`, `marketplace.json`), edited by value
  only.
- **New dependencies**: none. Nothing outside the Python standard library is
  imported and no package manifest gains an entry, so no third-party license
  enters the project. `project.license` is `none`, so no license
  compatibility constraint applies to this feature.

## Layer Structure

The change is document-level, not layered. Three groups exist, and the
dependency direction between them is one-way:

| Group | Members | Responsibility |
|---|---|---|
| Template layer | `em-workflow/references/templates/spec-document.md`, `em-workflow/references/templates/requirements-document.md` | The contract for every SPEC / REQUIREMENTS document rendered from now on |
| Registry layer | `em-workflow/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` | The plugin version, kept in sync across both registries |
| Verification layer | new modules under `tests/` | Document-contract assertions over the two layers above, plus invariant guards over documents this feature does not touch |

The verification layer reads the other two; neither of the other two ever
depends on the verification layer. No layer is added, removed or crossed in
a new way.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| Default-Membership Statement | The prose block both new template sections carry | Contract DM below — every DM row must hold in each section; wording follows the host document's language, content is identical | task0001, task0002, task0004 |
| Default-membership marker | The mechanical test for "this file carries the default-membership enumeration" | Contract MK below | task0001, task0002, task0004 |
| Section anchors | The heading literals used for section slicing and position assertions | Contract AN below | task0001, task0002, task0004 |
| Test-module inventory | Which new module each task owns | Contract MI below — one new module per task, exact filename fixed here, no task edits another task's module and no task edits a pre-existing module | all four |

### Contract DM — Default-Membership Statement

Precondition: the host document's fenced template body exists and the
insertion point named by the task plan is unambiguous.
Postcondition: the inserted section satisfies every row below. Each task
asserts only the rows for the document it owns; the "both sections"
scenarios (TS-5, TS-6, TS-7) are satisfied jointly and re-checked by the
integrated run in VERIFICATION.md.

| Row | Required content | Requirement |
|---|---|---|
| DM-1 | Both root literals appear verbatim: `feature-docs/{feature}/**` and `test-docs/{feature}/**` | FR3 / AC-3 |
| DM-2 | The feature-docs members are named verbatim: `REQUIREMENTS.md`, `SPEC.md`, `workflow.yaml`, `phase-state/`, `tasks/`, `reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, plus the design artifacts the design step produces | FR4 / AC-4 |
| DM-3 | The test-docs member is named verbatim as `{T}.tests.yaml`, with its path form `test-docs/{feature}/{T}.tests.yaml` | FR4 / AC-4 |
| DM-4 | `implement-phase.md` is CITED as the owner of the per-task test record's generation, and the phase documents / `references/phase-state.md` are CITED as the owners of the feature-docs artifacts — citation only; none of their rules is restated | FR4 / NFR2 |
| DM-5 | The default-unless-removed claim is stated: the default entries are part of the declaration unless the SPEC author explicitly removes them; removal is a deliberate narrowing, never an omission by silence | FR5 / AC-5 |
| DM-6 | The superset claim is stated: the declaration is a SUPERSET assertion and the actual change set must be CONTAINED IN it | FR5 / AC-5 |
| DM-7 | The zero-implement-task instance is named: a feature that produces no implement tasks generates no `test-docs/{feature}/` directory at all, and the declared `test-docs/{feature}/**` entry is still correct — a declared path that never materializes is not a violation | FR5 / AC-5 |
| DM-8 | A placeholder slot exists for the feature-specific paths the author enumerates, in the host document's placeholder convention | FR1 / FR2 |
| DM-9 | No rationale beyond what the requirements state, and no rule that excludes workflow-generated artifacts from the observed change set at verification time | NFR3 / FR6 |

### Contract MK — Default-membership marker

A file "carries the default-membership enumeration" **if and only if it
contains BOTH root literals `feature-docs/{feature}/**` and
`test-docs/{feature}/**`**. Single-literal matching is wrong and must not be
used: at the base revision `em-workflow/references/review-phase.md` already
contains the feature-docs root literal in an unrelated sentence, and
`em-workflow/references/implement-phase.md` already contains a
`test-docs/{feature}/` path without the double-star form. Under the
co-occurrence definition the marker matches zero files inside the plugin
directory at the base revision and exactly the two templates after both
template tasks merge.

Postcondition for task0001 / task0002: the section each writes makes its own
template match the marker. Postcondition for task0004: the set of files
under the plugin directory matching the marker is a SUBSET of the two
template paths (see decision D2 for why subset, not equality).

### Contract AN — Section anchors

| Document | Anchor of the new section | Preceding anchor | Following anchor |
|---|---|---|---|
| `spec-document.md` | `## Declared Change Set` | `### File Structure` | `## Test Scenarios` |
| `requirements-document.md` | `### 9.4 宣言された変更集合` | `### 9.3 スケジュール制約` | `## 10. 想定される課題とリスク` |

These literals are fixed here because three tasks depend on them: the two
that write the sections and the guard task that must not accidentally
redefine them. No task may vary the heading text.

### Contract MI — Test-module inventory

| Task | New module (created, never shared) |
|---|---|
| task0001 | `tests/test_spec_template_declared_change_set.py` |
| task0002 | `tests/test_requirements_template_declared_change_set.py` |
| task0003 | `tests/test_spec_file_set_completeness_version_bump.py` |
| task0004 | `tests/test_declared_change_set_invariants.py` |

Precondition: the filename does not already exist under `tests/`.
Postcondition: exactly one new module per task; every pre-existing module
under `tests/` stays byte-unchanged (NFR4); no two tasks write the same
file, so the four task branches merge into the parent branch without a
textual conflict.

## Conventions

- **Test-module pattern** (all four tasks, NFR5): follow the pattern of
  `tests/test_recycled_task_id_consistency.py` — a module docstring that
  maps each test class to the acceptance criterion and test scenario it
  covers, module-level path constants resolved from the repository root,
  heading-based section slicing, a whitespace-normalizing helper (the
  repository's `_normalize_ws` convention) used for prose assertions with
  raw un-normalized text reserved for byte-identity and offset assertions,
  and a dedicated negative-proof test class. Standard library only.
- **Negative proof and non-vacuity** (NFR5): every NEW matcher keeps the
  literal it matches in a single module-level constant shared by its
  positive test and its negative-proof test, and the negative proof runs
  against a verbatim captured pre-change sample (or, where no pre-change
  text exists, a synthetic sample that a violating document would contain).
  Every sample is guarded for non-vacuity by a positively asserted retained
  anchor, so a negative proof can never degrade into an assertion against
  empty text. Retention matchers and regression guards need no negative
  proof and are listed as explicitly exempt in the module docstring.
- **Per-worktree greenness** (all tasks): every test a task adds must pass
  in that task's own worktree, where no sibling task's edit exists. A task
  never asserts a post-merge-only condition.
- **Citation, not restatement** (NFR2): the template sections cite the
  document that owns an artifact's generation and never copy its rules. The
  same applies to the task plans and to this document.
- **No wildcard obligation over existing SPECs** (NFR6): no module added by
  this feature enumerates SPEC files by wildcard or directory walk under
  `feature-docs/` and requires the new section in them. Existing feature-docs
  are read only by explicit literal path, and only to assert retention of
  pre-existing content.
- **Naming**: new test modules use the `tests/test_<subject>.py` form per
  Contract MI; test classes are named for the scenario they cover.
- **Error handling policy**: N/A at runtime — this feature changes no
  executed behaviour. Contract violations surface as `unittest` failures
  and as verify-phase findings; no error code, log line or recovery path is
  introduced.

## Cross-task Design Decisions

### D1 — One template per task, no file overlap

The two template edits are separate files, so they are separate tasks; the
registry bump and the invariant guards are two more. The four tasks'
declared `files` sets are pairwise disjoint, so the parallel task branches
merge into the parent branch without a textual conflict. Affected: all
tasks.

### D2 — "Exactly two" is decomposed into a presence half and a subset half

TS-11 (NFR2) is stated over both templates at once, but no single worktree
holds both edits (D1). It is therefore split: the **presence** half — this
template carries the marker (Contract MK) — belongs to the task that writes
the section (task0001, task0002); the **subset** half — the set of files
under the plugin directory carrying the marker contains nothing outside the
two template paths — belongs to task0004 and holds in every worktree,
becoming the exact "only these two" statement once all branches have merged.
The integrated run in VERIFICATION.md is where the two halves meet.
Affected: task0001, task0002, task0004.

### D3 — The marker is a co-occurrence, not a single literal

Contract MK. Written here rather than in a task plan because the guard task
and both template tasks must agree on it, and because the two near-miss
files (`review-phase.md`, `implement-phase.md`) make the naive single-
literal matcher silently wrong. Affected: task0001, task0002, task0004.

### D4 — The version assertion is durable, not a pinned literal

FR9 sets `0.1.41` in both registries and AC-9 states that literal. The test
that pins it asserts the DURABLE invariant instead — the two registries
agree with each other, the version has the same major and minor as before,
and the patch number is strictly greater than the pre-change baseline `40`
— following the precedent recorded in
`tests/test_recycled_task_id_version_bump.py`, where a fixed literal was
rejected because the next unrelated bump makes it stale. The literal
`0.1.41` itself is verified by direct file read at verify time
(VERIFICATION.md, AC-9). Affected: task0003.

### D5 — Fence boundaries for the "inside the template body" assertion

Both templates consist of prose followed by a single outer fenced body that
opens with the file's first fenced-markdown line and closes with the file's
final fence line; both bodies already contain nested fenced blocks, so the
outer boundary must be determined from the first opening fence and the last
closing fence, never by scanning for the first fence terminator. The new
section's offset must fall strictly between them. Affected: task0001
(asserted as TS-2), task0002 (same structural requirement, asserted through
its own position scenario).

### D6 — Planning artifacts are outside the NFR2 scan scope

NFR2 / AC-10 scope the non-duplication rule to `em-workflow/references/`,
`em-workflow/agents/` and `em-workflow/skills/`. This document, the task
plans and VERIFICATION.md live under
`feature-docs/spec-file-set-completeness/` and necessarily restate the
required content so implementers can write it; that is not a third
restatement in the NFR2 sense, and TS-11's scan is scoped to the plugin
directory accordingly. Affected: all tasks (it is why the task plans may
quote Contract DM).

### D7 — Guard matchers must fail meaningfully in a worktree where nothing changed

task0004's scenarios assert the ABSENCE of something (a verify-side
exclusion rule, a third restatement, a wildcard obligation over existing
SPECs). Absence assertions pass trivially against an empty or mis-scoped
scan, so each one carries (a) a non-vacuity guard proving the scan actually
saw files, and (b) a negative proof running the same matcher over a
synthetic sample that a violating document would contain. Affected:
task0004; the same discipline is required of any absence assertion in the
other tasks.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| The two sections drift apart in content because two implementers write them independently | Medium | High (FR3/FR4/FR5 require equivalence) | Contract DM fixes the required literals and claims row by row; each task asserts its own rows |
| A guard scenario passes vacuously in the worktree that owns it | Medium | High (a test that can never fail is not a test) | D7: non-vacuity guards plus a negative proof per matcher |
| A naive single-literal duplication matcher flags `review-phase.md` / `implement-phase.md` and forces an unnecessary edit to a file FR6 forbids touching | Medium | High | Contract MK's co-occurrence definition, with both near misses named |
| New backtick-quoted tokens in the templates trip the repository's plugin-invariant sweeps (gate-id shape scan, stale-reference scan) | Low | Medium | Every new token is a path ending in a slash, a double star, `.md` or `.yaml`, all of which the existing shape scan already excludes; the full suite is run before the task reports done |
| A pinned version literal in a test goes stale at the next unrelated bump | Medium | Low | D4 |
| An implementer edits a pre-existing module under `tests/` to "fit in" the new assertions | Low | High (NFR4) | Contract MI: one new module per task, pre-existing modules byte-unchanged; asserted at verify time (TS-15) |

## Open Questions

- [ ] AC-9 states the version literal `0.1.41` while D4 pins the durable
      form in the test. If the verify phase advances the bump target (as the
      recycled-task-id-consistency feature did), the literal in SPEC/AC-9
      moves and the durable assertion still holds — verify must confirm the
      literal by direct file read rather than expect it from the suite.
- [ ] The catalogue of phrasings that count as a "verify-side exclusion
      rule" (FR6 / TS-8) is a judgment call fixed inside task0004's plan; a
      future document could express such a rule in wording the catalogue
      misses. The matcher is a guard, not a proof of impossibility.
