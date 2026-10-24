# Verification Document: self-write-digest-path-normalization

## Overview
**Feature**: self-write-digest-path-normalization / **SPEC.md**: `feature-docs/self-write-digest-path-normalization/SPEC.md` / **IMPLEMENTATION.md**: none (single task, reduced tier) / **THREAT-MODEL.md**: `feature-docs/self-write-digest-path-normalization/THREAT-MODEL.md`

## Build Verification
- Command: none (`project.components.main.build_command` is empty; Python scripts are not built)
- Expected: not applicable

## Test Verification
- Command: `python3 -m unittest discover -s tests` (run from the repository root)
- Focused run: `python3 -m unittest tests.test_self_write_digest tests.test_self_write_digest_docs tests.test_validate_worker_output`
- Coverage target: not applicable (the project configures no coverage tool). Completeness is judged by the scenario coverage below.

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | (FR2, FR1, FR4) Reproduction through the CLI. `identify_and_substitute` runs in a child process with `allowed_write_roots=["./feature-docs/example/tasks/"]` and `feature-docs/example/tasks/task0004.md` observed as `created` | `self_write_set` contains `feature-docs/example/tasks/task0004.md`. The R1 digest of the substituted `digest_source` equals the dispatch-time digest | Integration |
| TS-2 | (FR1, FR4) A root containing `.` keeps its boundary. Root `./docs/x`, with `docs/x/a.md`, `docs/x2/a.md`, `docs/x` and `docs/x/../y/a.md` as `created` | Only `docs/x/a.md` is contained | Unit |
| TS-3 | (FR1, FR4) `\` separators. Root `docs\x` with `docs/x/a.md`; root `docs/x` with `docs\x\a.md` and `docs\x\..\y.md`, all `created` | The first two are contained and the one with `..` is not, matching `path_is_contained_in_root` | Unit |
| TS-4 | (FR1, FR4, NFR2) Roots with no segments left. Roots `.` and `./`, with `a.md` and `docs/x/a.md` as `created` and as `modified`; roots `""` and `/`, with `a.md` as `created` | Under `.` and `./`, both `created` paths are contained and the `modified` ones are not. Under `""` and `/`, nothing is contained | Unit |
| TS-5 | (FR1, FR4; TM-1) Cross-check of the two implementations over a shared (path, root) table. The table covers `.` and empty segments, `\` separators, `.`-only, `./`-only and `\`-only roots, NUL, `..`, absolute paths and roots, and the empty-string root | The script's membership agrees with `path_is_contained_in_root` on every row; the table holds both true and false reference results | Unit |
| TS-6 | (NFR1, NFR2) Full suite and isolation | `python3 -m unittest discover -s tests` passes. The existing `CONTAINMENT_CASES` rows, `TestIsolation` and `TestScriptFileProperties` keep their content and pass. The script imports no module-loading facility | Integration |
| TS-7 | (FR3) The documented containment rule. Rule R1's containment bullet in `worker-envelope.md` and the docstrings of `self-write-digest.py` (module `allowed_write_roots` description, `_segments`, `_check_allowed_roots`) are checked | Both state the FR1 normalization. The block still holds "compares path segments, never string prefixes" and the absolute-or-`..` bullet | Unit (document) |
| TS-8 | (NFR2, NFR3) Files outside the change set. `git diff --name-only` runs from `workflow.implement.base_commit` to the integrated HEAD | Lists none of `em-workflow/scripts/validate-worker-output.py`, `tests/test_validate_worker_output.py`, `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` | Static (diff) |

## Code Quality Verification
- Format: none (`project.components.main.format_command` is empty) / Static analysis: none configured

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | The reproduction write enters `self_write_set` and the substituted digest equals the dispatch-time digest | TS-1 |
| AC-2 | Containment agrees with `path_is_contained_in_root` over the (path, root) table | TS-2, TS-3, TS-4, TS-5 |
| AC-3 | Rule R1's containment bullet and the script docstrings state the FR1 normalization | TS-7 |
| AC-4 | The full suite passes; existing `CONTAINMENT_CASES` rows and `TestIsolation` pass unchanged | TS-6 |
| SC-1 | All functional requirements are implemented and tested | Functional Requirements Coverage below |
| SC-2 | All test scenarios pass | TS-1 through TS-8 |
| SC-3 | `python3 -m unittest discover -s tests` passes | TS-6 |
| SC-4 | Documentation is complete | TS-7 and the manual check below |
| SC-5 | Code review is completed | review step of workflow.yaml is `completed` |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2, TS-3, TS-4, TS-5 |
| FR2 | task0001 | TS-1 |
| FR3 | task0001 | TS-7 |
| FR4 | task0001 | TS-1, TS-2, TS-3, TS-4, TS-5 |
| NFR1 | task0001 | TS-6 |
| NFR2 | task0001 | TS-4, TS-6, TS-8 |
| NFR3 | task0001 | TS-8 |

## Manual Testing (E2E Not Possible)
- [ ] Read Rule R1's containment bullet in `em-workflow/references/contracts/worker-envelope.md` next to the `allowed_write_roots` description in `self-write-digest.py`'s module docstring. Confirm they describe the same rule as SPEC.md FR1 without contradicting the bullet's remaining sentences (strict containment, trailing slash, the root itself).

## Performance / Security Verification (if applicable)
- TM-1: The containment decision rejects a side that is empty, absolute, holds NUL, or has a `..` segment with `\` as a separator, and otherwise requires a strict segment prefix, with the same truth value as `path_is_contained_in_root`. Checked by TS-5: no row whose reference result is false yields membership. TS-2 and TS-3 cover the `..` and `\` cases through the identification path.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios | 8 | 8 | 0 | 0 |
| Code quality | 0 | 0 | 0 | 0 |
| Success criteria | 9 | 8 | 0 | 1 |
| Manual testing | 1 | 0 | 0 | 1 |
| Security (TM-n) | 1 | 1 | 0 | 0 |
