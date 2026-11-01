# Verification Document: approval-unicode-whitespace

## Overview
**Feature**: approval-unicode-whitespace / **SPEC.md**: `feature-docs/approval-unicode-whitespace/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/approval-unicode-whitespace/IMPLEMENTATION.md`

## Build Verification
- Command: none (`project.components.main.build_command` is empty; the changed files are Python scripts and Markdown that are not built)
- Expected: not applicable

## Test Verification
- Command: `python3 -m unittest discover -s tests`
- Expected: exit code 0, no failures or errors
- Coverage target: not measured (the project uses standard-library unittest only, NFR3); every scenario below maps to at least one test

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | merge-preflight.py with `/usr/bin/true` approved and `test_command` carrying U+00A0, U+000B or U+000C before, after or on both sides, alone and mixed with spaces or tabs | stop with `commands_unapproved` naming `main.test_command` | Unit (script subprocess) |
| TS-2 | Attack scenario: `test_command` = U+00A0 + `/usr/bin/true`, an executable at the work-tree-relative path U+00A0 + `/usr/bin/true`, `/usr/bin/true` approved; run merge-preflight.py and the hook on that value | preflight stops with `commands_unapproved`; the hook gives no allow | Unit (script and hook subprocess) |
| TS-3 | `test_fr4_ac3_preflight_agrees_with_bash_guards_own_approval_decision` with its form-feed-and-vertical-tab case and its no-break-space case | both cases are not approved by either script; agreement holds on every case; both verdicts are exercised | Unit (script and hook subprocess) |
| TS-4 | merge-preflight.py with a `test_command` made only of U+00A0, and with one made only of spaces and tabs | U+00A0-only value stops with `commands_unapproved`; space/tab-only value is skipped | Unit (script subprocess) |
| TS-5 | Hook with `/usr/bin/true` approved and a command carrying U+00A0, U+000B or U+000C before, after or on both sides; the same value declared in a working-tree workflow.yaml, and not declared; a command empty after the space/tab trim | never allowed; declared → deny as unapproved; not declared → no decision; empty → no decision | Unit (hook subprocess) |
| TS-6 | Hook with an approved string followed by a trailing LF, or by a backslash and LF, standalone and as a cd prefix remainder; the two existing trailing line feed cases in the cd prefix test modules | not allowed in any form; the two existing cases expect a decision other than ALLOW | Unit (hook subprocess) |
| TS-7 | Hook with a cd prefix form whose remainder has U+00A0, U+000B or U+000C before or after an approved string | not allowed | Unit (hook subprocess) |
| TS-8 | Store holding an approved-looking entry with U+00A0, U+000B, U+000C, CR or LF before or after it; run `--list` and the hook on the entry's fully stripped form | `--list` does not print the entry; the hook does not allow the stripped form | Unit (CLI and hook subprocess) |
| TS-9 | `--record` and `--remove` given stdin with at least one non-matchable line (U+00A0, U+000B or U+000C before or after, or a CRLF line) next to matchable lines; a store that exists and one that does not | exit code 1, each such line reported on stderr, no "approved:" output, store file byte-identical or still absent, no leftover temporary file | Unit (CLI subprocess) |
| TS-10 | U+0085, U+2000, U+3000 or U+001F at either end of a command value (preflight), a Bash command (hook), a stdin line (`--record`) and a stored entry (`--list`) | not approved on any of the four paths | Unit (subprocess) |
| TS-11 | `make<U+00A0>test` against an approved `make test` in merge-preflight.py and the hook; `make<U+00A0>test` recorded through `--record` | no match in either script; recorded and listed as it is; does not approve `make test` | Unit (subprocess) |
| TS-12 | Spaces and tabs alone around a command in merge-preflight.py, the hook's exact match, the cd prefix form, `--record` / `--remove` lines and stored entries | approved exactly as before (existing space/tab cases keep passing) | Unit (subprocess) |
| TS-13 | Trim wording in `em-workflow/references/command-execution-protocol.md`, the bash_guard.py module docstring and the merge-preflight.py module docstring and `check_approval` comment | each states that only spaces and tabs are removed and that other surrounding whitespace is not approved; the superseded phrases are gone; `tests/test_cd_prefix_operator_exclusion_docs.py` passes | Unit (document tests) |
| TS-14 | Full suite, including `TestAc7StandardLibraryOnly` and `tests/test_hook_classification_pin.py`; new tests isolate the store with `EM_WORKFLOW_APPROVALS` | `python3 -m unittest discover -s tests` exits 0; bash_guard.py imports the standard library only and contains no substring `status` | Unit (suite) |
| TS-15 | Diff of the integration branch against the implement base commit | no change to any `plugin.json` version field or to `.claude-plugin/marketplace.json` | Static (git diff) |

## Code Quality Verification
- Format: none configured (`project.components.main.format_command` is empty)
- Static analysis: none configured; the standard-library-only rule (NFR1) and the classification pin (NFR2) are checked by existing tests through TS-14

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | Padded `test_command` around approved `/usr/bin/true` stops preflight with `commands_unapproved` | TS-1 |
| AC2 | The hook does not allow a padded command; a declared padded value is denied | TS-5 |
| AC3 | A cd prefix remainder padded before or after is not allowed | TS-7 |
| AC4 | The attack scenario is approved by neither script | TS-2 |
| AC5 | The agreement test's two cases become "not approved" with agreement kept | TS-3 |
| AC6 | Trailing LF and backslash + LF are not allowed standalone or cd-prefixed; the two existing tests stop expecting ALLOW | TS-6 |
| AC7 | `--record` / `--remove` with a non-matchable line (CRLF included) exit 1 and leave the store unchanged | TS-9 |
| AC8 | Non-matchable stored entries are neither approved nor listed | TS-8 |
| AC9 | A U+00A0-only value stops preflight as unapproved | TS-4 |
| AC10 | Space/tab-only surroundings still approve | TS-12 |
| AC11 | Documents state the space/tab-only trim; the full suite passes | TS-13, TS-14 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001, task0002 | TS-1, TS-5, TS-10, TS-11, TS-12 |
| FR2 | task0001 | TS-1, TS-2, TS-3 |
| FR3 | task0001 | TS-4 |
| FR4 | task0001 | TS-2, TS-3, TS-5, TS-6 |
| FR5 | task0001 | TS-6, TS-7 |
| FR6 | task0002 | TS-8 |
| FR7 | task0002 | TS-9 |
| FR8 | task0001 | TS-5 |
| FR9 | task0001, task0003 | TS-13 |
| NFR1 | task0001, task0002 | TS-14 |
| NFR2 | task0001, task0002 | TS-14 |
| NFR3 | task0001, task0002, task0003 | TS-14 |
| NFR4 | task0001, task0002, task0003 | TS-15 |

## Manual Testing (E2E Not Possible)
- [ ] In the integrated `em-workflow/hooks/bash_guard.py`, the two shared trim helpers (`trim_blanks`, `is_matchable`) are defined exactly once, at the placement IMPLEMENTATION.md C2 fixes
- [ ] In the integrated `em-workflow/hooks/bash_guard.py` and `em-workflow/scripts/merge-preflight.py`, no approval path in IMPLEMENTATION.md C1's per-path table still removes whitespace other than spaces and tabs

## Performance / Security Verification (if applicable)
- TM-1: preflight trims spaces and tabs only and stops every non-matchable value as `commands_unapproved` — checked by TS-1 and TS-2
- TM-2: only values empty after the space/tab trim are skipped by preflight — checked by TS-4
- TM-3: the hook entry trims spaces and tabs only and never allows a non-matchable command — checked by TS-2, TS-5 and TS-6
- TM-4: the cd prefix remainder is trimmed by spaces and tabs only and a non-matchable remainder is excluded — checked by TS-6 and TS-7
- TM-5: declared-command extraction keeps padded values declared, so the hook denies them — checked by TS-5 (declared case)
- TM-6: `--record` / `--remove` refuse an input with a non-matchable line and leave the store unchanged — checked by TS-9
- TM-7: `approved_for` and `--list` drop non-matchable stored entries — checked by TS-8

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios | 15 | 15 | 0 | 0 |
| Code quality | 0 | 0 | 0 | 0 |
| Success criteria | 11 | 11 | 0 | 0 |
| Security (TM-n) | 7 | 7 | 0 | 0 |
| Manual review | 2 | 0 | 0 | 2 |
| Total | 35 | 33 | 0 | 2 |
