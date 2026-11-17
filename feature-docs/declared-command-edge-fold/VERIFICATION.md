# Verification Document: declared-command-edge-fold

## Overview
**Feature**: declared-command-edge-fold / **SPEC.md**: `feature-docs/declared-command-edge-fold/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/declared-command-edge-fold/IMPLEMENTATION.md`

## Build Verification
- Command: none (workflow.yaml `project.components.main.build_command` is empty)
- Expected: not applicable

## Test Verification
- Command: `python3 -m unittest discover -s tests`
- Expected: exit code 0, no failures or errors
- Coverage target: none configured for this component

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | `declared_commands` is called directly, the module loaded without writing bytecode as the existing `_load_guard_module` does. The existing AC-4 / AC-5 set-comparison tests of `tests/test_bash_guard_declared_yaml_breaks.py` run unmodified. | The declared set is unchanged: the existing tests pass. For a declaration of `"<U+0085>./unapproved<U+2028>"` the set holds exactly the raw value and `./unapproved`. | Unit |
| TS-2 | New file `tests/test_bash_guard_declared_edge_fold.py` with its own fixture. One temporary git repository per declaration (one declaration each) and one without declarations; the store holds only `/usr/bin/true`. Declarations are double- and single-quoted with raw characters; the YAML-parsed forms are passed to the hook subprocess. | Every YAML-parsed form of SPEC.md AC1-AC4 is denied with a reason containing 未承認. Without the declaration, each gets no decision. No form gets allow. `/usr/bin/true` itself is allowed. `./unapproved` padded with U+00A0 gets no decision in a declaring repository. | Integration |
| TS-3 | `/usr/bin/true` padded at an end with LF, U+0085, U+2028 or U+2029, in a repository declaring `/usr/bin/true` and in one without declarations | Deny (未承認) in the declaring repository and no decision in the other | Integration |
| TS-4 | `test_ac6_no_padded_or_end_stripped_unapproved_command_is_allowed` with changed expectations | Deny for forms padded at both ends with U+0020, U+0009, U+0085, U+2028 or U+2029; no decision for U+00A0; no allow for any form | Integration |
| TS-5 | Full suite: `python3 -m unittest discover -s tests` | Passes, including the standard-library-only, classification pin, raw-character, helper-order and docstring-phrase tests (NFR1-NFR6) | Integration |
| TS-6 | A declaration made only of newline characters, `"<U+0085><U+2028><U+2029>"`, whose YAML-parsed form `<U+2028><U+2029>` is empty once both ends are stripped | No decision: the empty end-stripped form is not declared (recorded as out of scope) | Integration |
| TS-7 | The cd-prefixed form, cd into the repository then `&&` and the declared value followed by U+2028 | No allow, and the same verdict as before the change | Integration |
| TS-8 | The approval store file is absent and only the declaration exists (the early-return path), with the YAML-parsed form of SPEC.md AC1 | Deny (未承認) | Integration |
| TS-9 | The four documents of other features named by FR5, and the `bash_guard.py` docstring and comments, compared with workflow.yaml's `create-spec` `completed_at_commit` | The four documents gain only added lines. Those lines cover the three points of FR5. `feature-docs/*/reviews/round1.yaml` and `em-workflow/references/command-execution-protocol.md` show no change. The docstring and comments describe the end-stripped declared match. | Inspection |

## Code Quality Verification
- Format: none (workflow.yaml `format_command` is empty)
- Static analysis: none configured. The classification pin, standard-library-only and raw-character checks are part of the test suite (TS-5).

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | YAML-parsed forms of `"<U+0085>./unapproved<U+2028>"` / `"<U+0085>./unapproved<U+2029>"` are denied, as are the raw form and `./unapproved` | TS-2 |
| AC2 | YAML-parsed forms of the reversed declarations are denied | TS-2 |
| AC3 | YAML-parsed forms of same-end consecutive declarations are denied | TS-2 |
| AC4 | The same holds for single-quoted declarations | TS-2 |
| AC5 | No decision without the declaration, never allow, `/usr/bin/true` allowed, U+00A0 padding gets no decision | TS-2, TS-6, TS-7 |
| AC6 | Approved `/usr/bin/true` padded with newline characters is denied when declared and gets no decision otherwise | TS-3 |
| AC7 | `declared_commands` returns the same set; the AC-4 / AC-5 set comparisons pass unmodified | TS-1 |
| AC8 | `test_ac6_no_padded_or_end_stripped_unapproved_command_is_allowed` has the changed expectations | TS-4 |
| AC9 | The four documents carry the three points; existing text, `round1.yaml` and `command-execution-protocol.md` are unchanged | TS-9 |
| AC10 | The suite passes (NFR1-NFR6). For NFR7, the feature diff does not touch `em-workflow/.claude-plugin/plugin.json` or `.claude-plugin/marketplace.json` | TS-5, plus the diff check for NFR7 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-2, TS-6, TS-7, TS-8 |
| FR2 | task0001 | TS-1, TS-7 (and the no-allow checks of TS-2) |
| FR3 | task0001 | TS-3 |
| FR4 | task0001 | TS-2, TS-4 |
| FR5 | task0001 (docstring and comments); the four other-feature documents were amended by the planner | TS-9 |
| NFR1 | task0001 | TS-5 |
| NFR2 | task0001 | TS-5 |
| NFR3 | task0001 | TS-5 |
| NFR4 | task0001 | TS-5 |
| NFR5 | task0001 | TS-5 |
| NFR6 | task0001 | TS-5 |
| NFR7 | task0001 | TS-5 and the diff check for NFR7 |

## Manual Testing (E2E Not Possible)
- [ ] TS-9: inspect the diff of the four other-feature documents and of the `bash_guard.py` docstring and comments as stated in the scenario table.

## Performance / Security Verification
- TM-1: the hook also matches the six-character end-stripped form (when non-empty) against the declared set at all three declared checks. Checked by TS-2 and TS-8: every YAML-parsed form of a mixed or repeated end declaration is denied as unapproved, also on the early-return path.
- TM-2: the end-stripped form decides only whether a command is declared, and the allow paths and declared-set extraction are unchanged. Checked by TS-1 (declared set unchanged), TS-2 (no form gets allow; `/usr/bin/true` still allowed), TS-3 (padded approved value is denied, not allowed) and TS-7 (cd-prefixed form gets no allow and keeps its verdict).

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios | 9 | 8 | 0 | 1 |
| SPEC success criteria | 10 | 9 | 0 | 1 |
| Security (TM-n) | 2 | 2 | 0 | 0 |
