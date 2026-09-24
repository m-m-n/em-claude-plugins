# Verification Document: recycled-carveout-reader-count-claims

## Overview

**Feature**: recycled-carveout-reader-count-claims / **SPEC.md**: `feature-docs/recycled-carveout-reader-count-claims/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/recycled-carveout-reader-count-claims/IMPLEMENTATION.md`

Scope of the change: lines 36 and 89 of `feature-docs/recycled-task-id-carveout/VERIFICATION.md`. `tests/test_recycled_task_id_consistency.py` is inspected only.

"Reader site" and "TS-13 criterion" are used as defined in IMPLEMENTATION.md Conventions.

## Build Verification

- Command: none (`project.components.main.build_command` is empty). Not applicable.

## Test Verification

- Command: `python3 -m unittest discover -s tests` (run from the repository root)
- Coverage target: not applicable (documentation-only change; no code is added or modified)

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Read line 36 (TS-13 row) and line 89 (Manual Testing item) of `feature-docs/recycled-task-id-carveout/VERIFICATION.md` | Both lines name only `HOOK_FILENAMES` and `JOURNAL_ONLY_HOOK_FILENAMES`. Both state the TS-13 criterion (retired with all references: no definition and 0 reader sites, or 2 or more reader sites) together with the reader-site definition (code references outside the definition line; comments and docstrings not counted). Neither contains wording addressing every module-level constant: `is left with fewer than two reader sites`, `every constant has 0 (retired with its readers) or >= 2` and `every module-level constant` are absent. Line 36 still carries `TS-13`, `(SPEC AC-6)` and Test Type `Inspection`. Line 89 still cites `TS-13`. | Inspection |
| TS-2 | In `tests/test_recycled_task_id_consistency.py`, count the references to `HOOK_FILENAMES` outside its definition line, excluding comments and docstrings; search for `JOURNAL_ONLY_HOOK_FILENAMES` | `HOOK_FILENAMES` has 2 or more reader sites (3 at SPEC measurement time). `JOURNAL_ONLY_HOOK_FILENAMES` has no definition and no reference. | Inspection |
| TS-3 | Search `tests/test_recycled_task_id_consistency.py` case-insensitively for `reader`, and read the module docstring | The module docstring contains no reader-count claim, and `leaving no module-level constant in this module with fewer than two reader sites` does not occur in the module. | Inspection |
| TS-4 | Run `git diff --stat` and a line-level diff of the integrated branch against the implement base commit (`workflow.yaml` implement step `base_commit`) | Changed paths are `feature-docs/recycled-task-id-carveout/VERIFICATION.md` plus paths under this feature's workflow-generated roots (`feature-docs/recycled-carveout-reader-count-claims/`, `test-docs/recycled-carveout-reader-count-claims/`). In `feature-docs/recycled-task-id-carveout/VERIFICATION.md`, only lines 36 and 89 differ and the line count is unchanged. No path under `em-workflow/`, no `.claude-plugin/marketplace.json`, no path under `tests/`, and none of the NFR2 files appear. | Inspection |
| TS-5 | Run `python3 -m unittest discover -s tests` from the repository root | Exit code 0 | Integration |

TS-4 includes `test-docs/recycled-carveout-reader-count-claims/` as an allowed root because FR4 permits this feature's own workflow-generated documents and the SPEC's Declared Change Set lists that root.

## Code Quality Verification

- Format: none configured (`project.components.main.format_command` is empty)
- Static analysis: none configured

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | The TS-13 row names only `HOOK_FILENAMES` and `JOURNAL_ONLY_HOOK_FILENAMES`; its Expected Result states the criterion and the reader-site definition; no universal wording about all module-level constants remains | TS-1 |
| AC-2 | Measured on the integrated `tests/test_recycled_task_id_consistency.py`, the TS-13 criterion holds (`HOOK_FILENAMES` 2 or more reader sites; `JOURNAL_ONLY_HOOK_FILENAMES` neither defined nor referenced) | TS-2 |
| AC-3 | The line-89 Manual Testing item is restricted to the same two constants, uses the same criterion and cites TS-13 | TS-1 |
| AC-4 | A case-insensitive search for `reader` finds no reader-count claim in the module docstring | TS-3 |
| AC-5 | The diff against base changes only lines 36 and 89 of `feature-docs/recycled-task-id-carveout/VERIFICATION.md` plus this feature's workflow-generated files | TS-4 |
| AC-6 | `python3 -m unittest discover -s tests` exits with code 0 | TS-5 |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2 |
| FR2 | task0001 | TS-1 |
| FR3 | task0001 | TS-3 |
| FR4 | task0001 | TS-4 |
| NFR1 | task0001 | TS-4 (no path under `em-workflow/` and no `.claude-plugin/marketplace.json` in the diff) |
| NFR2 | task0001 | TS-4 (none of the NFR2 files in the diff) |
| NFR3 | task0001 | TS-5 |

## Manual Testing (E2E Not Possible)

- [ ] TS-1: Read the rewritten line 36 and line 89 and confirm that each addresses only the two constants and states the criterion and the reader-site definition. Judging whether any remaining wording addresses every module-level constant needs a reader.
- [ ] TS-2: Count the reader sites of `HOOK_FILENAMES` using the reader-site definition. Deciding whether a hit is inside a comment or a docstring needs a reader.
- [ ] TS-3: Read the module docstring of `tests/test_recycled_task_id_consistency.py` and confirm there is no reader-count claim.
- [ ] TS-4: Review the line-level diff of `feature-docs/recycled-task-id-carveout/VERIFICATION.md` and the changed-path list against the allowed set.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test suite | 1 (TS-5) | 1 | 0 | 0 |
| Inspection | 4 (TS-1, TS-2, TS-3, TS-4) | 0 | 0 | 4 |
| Total | 5 | 1 | 0 | 4 |
