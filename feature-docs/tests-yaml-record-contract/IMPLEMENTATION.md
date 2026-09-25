# Implementation Plan: tests-yaml-record-contract

## Overview

Tighten the tests.yaml record contract owned by `em-workflow/agents/implementer.md`
(Step 4c, Step 6) so that `red_confirmed` and `final_failures` record only what was
actually observed, pin the new rules with a document-contract test under `tests/`, and
ship the change with an em-workflow patch version bump.
Source documents: `feature-docs/tests-yaml-record-contract/SPEC.md`,
`feature-docs/tests-yaml-record-contract/REQUIREMENTS.md`.

## Technology Stack

- **Contract document**: Markdown agent definition (`em-workflow/agents/implementer.md`).
- **Tests**: Python 3 standard library `unittest` only (NFR4), discovered by
  `python3 -m unittest discover -s tests` from the repository root.
- **Release metadata**: JSON manifests (`em-workflow/.claude-plugin/plugin.json`,
  `.claude-plugin/marketplace.json`).
- **New dependencies**: none. `project.license` is `none`; no license record is needed.

## Layer Structure

| Layer | Artifact | Responsibility | May depend on |
|-------|----------|----------------|---------------|
| Contract | `em-workflow/agents/implementer.md` Step 4c / Step 6 / Step 7 | Sole owner of the tests.yaml recording rules and the implementer report fields | nothing in this feature |
| Contract test | `tests/test_*.py` (new module) | Reads the contract document and asserts each rule is present | Contract layer (read-only) |
| Release metadata | plugin.json, marketplace.json | Carry the em-workflow version that invalidates the installed-plugin cache | nothing in this feature |

Dependency direction is one-way: the test reads the contract document; the contract
document never refers to the test.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| implementer.md Step 4c / Step 6 sections | Single owner of the tests.yaml recording rules (NFR3) | Post: each section stays locatable by its own heading (the heading that names Step 4c, and the heading that names Step 6). Any later change that renames or moves either heading must update the document-contract test in the same task, because the test extracts sections by those headings. | task0001 |

No other component is shared: the feature has a single task (see Cross-task Design
Decisions, D1).

## Conventions

- **Version bump**: any change under `em-workflow/` raises the em-workflow `version` by a
  patch increment in both `em-workflow/.claude-plugin/plugin.json` and the em-workflow
  entry of `.claude-plugin/marketplace.json`, to the same value, in the same commit as
  the plugin-file change. The increment is computed from the value present at the
  task's base (ASM-6), never from a hard-coded number.
- **Tests**: stdlib `unittest` only; module placed at `tests/test_*.py` so the existing
  discover command picks it up without configuration changes.
- **Single owner (NFR3)**: the tests.yaml recording rules are written only in
  `implementer.md`. No other document restates them; documents that need them refer to
  `implementer.md` Step 4c.
- **Wording style**: new text in `implementer.md` follows the language, heading style and
  terminology already used in that file (field names such as `red_confirmed`,
  `red_reason`, `baseline_failures`, `final_failures`, `unconfirmed_reds` are written
  exactly as the tests.yaml schema and the Step 7 report spell them).

## Cross-task Design Decisions

### D1: One task, not several

The Step 4c / Step 6 edits, the document-contract test that pins them, and the version
bump are planned as a single task (task0001).

- All tasks run fully in parallel in separate worktrees. A contract test planned in a
  different task from the document edit could never pass in its own worktree, and the
  SPEC requires the same test to be observed failing before the edit and passing after
  it (AC-7) — that is one task's own red-to-green cycle.
- The repository's commit guard rejects a commit that changes a file under
  `em-workflow/` without the matching version bump, so the bump cannot live in a
  separate task from the document edit.
- Splitting Step 4c between two tasks would put two parallel edits into the same section
  of the same file, with no benefit in reviewability.

Affected tasks: task0001.

### D2: Documents intentionally left unchanged

The following stay untouched by this feature (SPEC ASM-3, ASM-4, ASM-5):

- `test-docs/i2c-routeback-reconciliation/task0001.tests.yaml` (the existing example)
- `em-workflow/skills/tdd-testing/SKILL.md`
- `em-workflow/skills/worktree-task-workflow/SKILL.md`
- `em-workflow/references/implement-phase.md` (`tests_yaml_path` hand-off)

Any follow-up task created later for this feature keeps this boundary unless the SPEC
changes. No validator or hook for tests.yaml is added (NFR2).

Affected tasks: task0001 (and any later follow-up task).

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| The contract test pins whole sentences and breaks on harmless rewording | Medium | Low | Pin short, distinctive phrases per rule, scoped to the extracted section, rather than full sentences |
| A renamed heading makes section extraction return nothing, so negative checks pass vacuously | Low | Medium | The test asserts that each section is found and non-empty before any other check |
| New Step 4c wording contradicts the Step 7 report fields or the `tests_yaml_path` description in implement-phase.md | Low | Medium | Manual verification item in VERIFICATION.md cross-reads the three places |
| Another feature raises the em-workflow version on main while this feature is in flight | Medium | Low | Bump from the value at the task base; if the integration merge conflicts on the version, resolve to one patch above the higher value (ASM-6) |
| The negative check for the old "report's notes" routing also matches the new, legitimate mentions of `notes` (the redefinition prohibition, the skipped re-run statement) | Medium | Medium | The negative check targets the specific pre-change routing phrase, not the bare word `notes` |

## Open Questions

- [ ] None blocking. SPEC has no test scenario for NFR1 / NFR2 / NFR3; VERIFICATION.md
      adds planner-authored scenarios TS-9 and TS-10 for them.
