# Verification Document: spec-file-set-completeness

## Overview

**Feature**: spec-file-set-completeness
**SPEC.md**: `feature-docs/spec-file-set-completeness/SPEC.md`
**IMPLEMENTATION.md**: `feature-docs/spec-file-set-completeness/IMPLEMENTATION.md`

This document covers the INTEGRATED verification run on the merged
integration branch. Per-task acceptance criteria live in
`feature-docs/spec-file-set-completeness/tasks/taskNNNN.md`.

## Build Verification

- Command: none — `project.components.main.build_command` is empty. This
  project has no build step; the deliverables are markdown documents, two
  JSON registries and Python test modules.
- Expected: N/A.

## Test Verification

- Command: `python3 -m unittest discover -s tests` (run from the repository
  root)
- Expected: exit code 0, zero failures, zero errors.
- Coverage target: N/A — no coverage tooling is configured in this project,
  and no coverage threshold is defined by SPEC.md. Requirement coverage is
  tracked by the mapping table below instead.

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | `## Declared Change Set` exists in `spec-document.md`, positioned after `### File Structure` and before `## Test Scenarios` | Assertion passes | Unit (task0001 module) |
| TS-2 | The new SPEC-template section lies inside the outer fenced template body | Assertion passes | Unit (task0001 module) |
| TS-3 | `### 9.4 宣言された変更集合` exists in `requirements-document.md`, positioned after `### 9.3 スケジュール制約` and before `## 10. 想定される課題とリスク` | Assertion passes | Unit (task0002 module) |
| TS-4 | Every pre-existing top-level heading `## 1. 概要` .. `## 15. 参考資料` is present with unchanged number and title | Assertion passes | Unit (task0002 module) |
| TS-5 | BOTH new sections contain `feature-docs/{feature}/**` and `test-docs/{feature}/**` | Both halves assert; both pass on the merged tree | Unit (task0001 + task0002 modules) |
| TS-6 | BOTH new sections enumerate the feature-docs members and the `{T}.tests.yaml` member, and cite `implement-phase.md` | Both halves assert; both pass on the merged tree | Unit (task0001 + task0002 modules) |
| TS-7 | BOTH new sections state the default-unless-removed rule and the containment (subset, not equality) rule, including the zero-implement-task non-violation case | Both halves assert; both pass on the merged tree | Unit (task0001 + task0002 modules) |
| TS-8 | None of `implement-phase.md`, `review-phase.md`, `review-protocol.md`, `phases/create-spec-phase.md`, `phases/create-plan-phase.md`, `rework-task-synthesis.md` or `references/contracts/*` contains a verify-side exclusion rule for workflow-generated artifacts | Offender list empty; scan proven non-vacuous | Integration (task0004 module) |
| TS-9 | `feature-docs/recycled-task-id-consistency/SPEC.md` still lists `test-docs/recycled-task-id-consistency/**` in FR8 and AC-8, and `REQUIREMENTS.md` in its corresponding constraint | Assertions pass (retention pin) | Integration (task0004 module) |
| TS-10 | Both registries carry the bumped version and agree; the `em-review` entry is unchanged | Assertions pass | Unit (task0003 module) |
| TS-11 | The default-membership enumeration appears in no file under `em-workflow/**` other than the two templates, and appears in both of them | Carrier set equals exactly the two template paths on the merged tree (subset half from task0004, presence half from task0001/task0002) | Integration (task0004 + task0001 + task0002 modules) |
| TS-12 | No matcher added by this feature applies the new section as a mandatory requirement to any file under `feature-docs/*/SPEC.md` | Offender list empty; scan proven non-vacuous | Integration (task0004 module) |
| TS-13 | Every new matcher of TS-1, TS-3, TS-5, TS-6, TS-7 and TS-8 reports absence when run against the captured pre-change sample, and every sample is guarded for non-vacuity | Negative proofs pass; every matcher in each new module is listed in its docstring against a proof or an explicit retention/regression exemption | Unit (all four modules) |
| TS-14 | Change containment: `git diff --name-only` from the implement base commit to the integration tip is a subset of FR8's declared set, with no path under `em-workflow/hooks/`, `em-workflow/scripts/`, `em-workflow/agents/`, `em-workflow/skills/`, `em-workflow/references/contracts/`, no path under `em-workflow/references/` other than the two templates, and no path under `feature-docs/recycled-task-id-consistency/` | Subset holds; forbidden-path count is zero | Manual (verify phase, git) |
| TS-15 | Every pre-existing module under `tests/` is byte-unchanged; the only `tests/` entries in the diff are the four newly added modules | Modified-pre-existing count is zero; full suite green | Manual (verify phase, git) + Unit (suite run) |

## Code Quality Verification

- Format: none — `project.components.main.format_command` is empty. No
  formatter is configured for this project and this feature adds none.
- Static analysis: no standalone linter is configured. The repository's
  structural invariants are checked inside the suite by
  `tests/test_check_plugin_invariants.py` (which drives
  `em-workflow/scripts/check-plugin-invariants.py`) and by
  `tests/test_reference_sweep.py`; both read the two edited templates and
  must stay green.

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | SPEC template has `## Declared Change Set` in the right position | TS-1, TS-2 |
| AC-2 | REQUIREMENTS template has `### 9.4 宣言された変更集合`; sections 1..15 unchanged | TS-3, TS-4 |
| AC-3 | Both sections contain both root literals | TS-5 |
| AC-4 | Both sections enumerate the members and cite the owning documents | TS-6, plus a read of both sections confirming citation rather than restatement |
| AC-5 | Both sections state default-unless-removed, containment, and the zero-implement-task case | TS-7 |
| AC-6 | No path under `em-workflow/references/` other than the two templates; no path under hooks / scripts / agents / skills / contracts; no verify-side exclusion rule introduced | TS-14, TS-8 |
| AC-7 | No path under `feature-docs/recycled-task-id-consistency/`; the pin test asserts retention | TS-14, TS-9 |
| AC-8 | The diff is a subset of FR8's declared set | TS-14 |
| AC-9 | Both registries read `"version": "0.1.41"`; the `em-review` entry is unchanged | Read both JSON files directly (the suite pins the durable invariant per IMPLEMENTATION.md D4; the literal is confirmed here) and TS-10 |
| AC-10 | A repository-wide search finds the default-membership enumeration only in the two templates | TS-11, plus a repository-wide search confirming no third document under `em-workflow/references/`, `em-workflow/agents/` or `em-workflow/skills/` restates it |
| AC-11 | Both additions sit inside their fenced template body; English + `{placeholder}` for the SPEC template, Japanese + `### N.M` for the REQUIREMENTS template | TS-2, TS-3, plus a style read of both additions |
| AC-12 | `python3 -m unittest discover -s tests` passes with every pre-existing module byte-unchanged | Test Verification run + TS-15 |
| AC-13 | The new modules exist, are discovered, implement TS-1..TS-13, import stdlib only, and give every new matcher a negative proof | TS-13, plus a read of each module's docstring inventory |
| AC-14 | Nothing added makes the new section mandatory for an existing SPEC or fails a SPEC without a closed file set; completed features' feature-docs stay byte-unchanged | TS-12, TS-14 |
| SC-1 | All functional requirements are implemented and tested | Coverage table below |
| SC-2 | All test scenarios pass | Test Verification run + the manual items |
| SC-3 | Performance goals | N/A — none defined |
| SC-4 | Security requirements | N/A — none defined |
| SC-5 | Documentation is complete | SPEC.md, REQUIREMENTS.md, IMPLEMENTATION.md, the four task plans and this document exist and agree |
| SC-6 | Code review is completed | Review phase result |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2 |
| FR2 | task0002 | TS-3, TS-4 |
| FR3 | task0001, task0002 | TS-5 |
| FR4 | task0001, task0002 | TS-6 |
| FR5 | task0001, task0002 | TS-7 |
| FR6 | task0004 | TS-8 |
| FR7 | task0004 | TS-9 |
| FR8 | task0001, task0002, task0003, task0004 | TS-14 |
| FR9 | task0003 | TS-10 |
| NFR1 | task0001, task0002, task0003, task0004 | TS-8, TS-14 |
| NFR2 | task0001, task0002, task0004 | TS-11 |
| NFR3 | task0001, task0002 | TS-2, TS-3 |
| NFR4 | task0001, task0002, task0003, task0004 | TS-15 |
| NFR5 | task0001, task0002, task0003, task0004 | TS-13 |
| NFR6 | task0001, task0002, task0004 | TS-12 |

## E2E Testing

N/A — `project.components.main.e2e_test_command` is empty and the project
defines no E2E framework. SPEC.md records the same ("Existing E2E tests:
None / Run command: Not detected"). Nothing in this feature adds an E2E
surface.

## Manual Testing (E2E Not Possible)

- [ ] TS-14 / AC-6 / AC-7 / AC-8: run `git diff --name-only` from the
      `implement` step's `base_commit` to the integration tip and confirm
      the path set is a subset of FR8's declared set, that no path falls
      under `em-workflow/hooks/`, `em-workflow/scripts/`,
      `em-workflow/agents/`, `em-workflow/skills/` or
      `em-workflow/references/contracts/`, that the only paths under
      `em-workflow/references/` are the two templates, and that no path
      falls under `feature-docs/recycled-task-id-consistency/`.
- [ ] TS-15 / AC-12: from the same diff, confirm every `tests/` entry is a
      newly added file and that no pre-existing module under `tests/` was
      modified.
- [ ] AC-9: read `em-workflow/.claude-plugin/plugin.json` and the
      `em-workflow` entry of `.claude-plugin/marketplace.json` and confirm
      both read `0.1.41` and that the `em-review` entry is unchanged.
- [ ] AC-4 / NFR2: read both new sections and confirm each CITES the owning
      document (`implement-phase.md` for the test record; the phase
      documents / `references/phase-state.md` for the feature-docs
      artifacts) instead of restating its rules.
- [ ] AC-10: run a repository-wide search for the default-membership
      enumeration and confirm no document under `em-workflow/references/`,
      `em-workflow/agents/` or `em-workflow/skills/` other than the two
      templates carries it.
- [ ] AC-11 / NFR3: read both additions and confirm the SPEC-template one is
      English with `{placeholder}` form and the REQUIREMENTS-template one is
      Japanese with `### N.M` numbering, that both sit inside their fenced
      template body, and that neither adds rationale beyond the
      requirements.
- [ ] AC-13: read each new module's docstring and confirm its matcher →
      negative-proof inventory covers every matcher in the module, each
      entry naming either a proof or an explicit retention / regression
      exemption.

No mockup comparison item applies: the `design` step is `skipped` for this
feature and no design artifact exists.

## Performance / Security Verification

N/A — SPEC.md defines no performance goal and no security requirement for
this change (no authenticated surface, no runtime input path, no data
handling). The new tests read repository documents only.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios | 15 | 13 (TS-1..TS-13) | 0 | 2 (TS-14, TS-15) |
| Acceptance criteria | 14 | 10 fully automated; 4 partly manual (AC-4, AC-9, AC-10, AC-11) | 0 | 7 manual checks listed above |
| Requirements | 15 | 15 mapped to ≥ 1 task and ≥ 1 scenario | 0 | — |
| Build / format | 0 | N/A (no command defined) | 0 | 0 |
