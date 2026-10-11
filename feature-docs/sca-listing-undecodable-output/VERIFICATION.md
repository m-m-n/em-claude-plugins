# Verification Document: sca-listing-undecodable-output

## Overview
**Feature**: sca-listing-undecodable-output / **SPEC.md**: `feature-docs/sca-listing-undecodable-output/SPEC.md` / **IMPLEMENTATION.md**: not produced (reduced tier, single task `tasks/task0001.md`) / **THREAT-MODEL.md**: `feature-docs/sca-listing-undecodable-output/THREAT-MODEL.md`

## Build Verification
- Command: none (both components, `repo-tests` and `plugin-invariants`, have an empty build_command)
- Expected: not applicable

## Test Verification
- Command (repo-tests): `python3 -m unittest discover -s tests`
- Command (plugin-invariants): `python3 em-workflow/scripts/check-plugin-invariants.py .`
- Expected: exit code 0 for both
- Coverage target: no coverage tool is configured; every scenario below is covered by at least one passing test or inspection item

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | CLI reproduction: a stub `task list` exits 0 and writes invalid UTF-8 (for example bytes 0xFF 0xFE followed by `[`) to stdout; `scan-dependencies.py file-tasks` is run as a subprocess with the stub as `--entry-point` | Exit code 0; stdout parses as one JSON summary; `degraded_reason` is `listing_output_undecodable`, `branch` is `report`, `degraded` is true; the report file is written; stderr contains no `Traceback` | Integration |
| TS-2 | Direct call of `list_security_tasks` with the TS-1 stub | `available=False`, `reason="listing_output_undecodable"`, no exception | Unit |
| TS-3 | `task list` exits non-zero with invalid UTF-8 bytes on stdout | Reason is `listing_exit_nonzero` | Unit |
| TS-4 | `task list` exits 0 with stdout `[]` and invalid UTF-8 bytes on stderr (stub emits them for `task list` only) | Listing is available; `branch` is `ntd`; the target package is in `filed_packages` | Integration |
| TS-5 | `task list` exits 0 with stdout containing a UTF-8-encoded surrogate (bytes 0xED 0xA0 0x80) | Reason is `listing_output_undecodable` (strict decoding) | Unit |
| TS-6 | `TestListingUnavailableReasons` extended with the sixth condition (exit 0, invalid UTF-8 stdout) | Each of the six conditions reaches the report branch; the set of reasons has size 6 | Unit |
| TS-7 | `ListingOutcome` docstring check | States six unavailable conditions and names all six tokens; the `list_security_tasks` docstring describes the same six in the same order | Unit |
| TS-8 | `task list` exits 0 with stdout that is a valid UTF-8 JSON array containing non-ASCII text (added at create-plan for FR1) | `available=True` with the entries parsed | Unit |
| TS-9 | Summary and report hygiene on the TS-1 run, with a distinctive ASCII marker included in the stub's stdout (added at create-plan for NFR3) | `degraded_reason` equals `listing_output_undecodable` exactly; neither the summary nor the report file contains the marker or decode-error wording | Integration |
| TS-10 | Regression: full test suite and invariants check (SPEC AC-7) | Both commands exit 0; test IDs recorded in `test-docs/**/*.tests.yaml` still resolve; the existing tests for the five existing reason tokens pass with unchanged expectations | Regression |
| TS-11 | Change scope and version fields (added at create-plan for NFR1, NFR5) | The integrated diff against the base touches only `em-workflow/scripts/scan-dependencies.py`, `tests/test_sca_task_filing.py`, `tests/test_sca_listing_undecodable_output.py`, and this feature's `feature-docs/` and `test-docs/` directories; `resolve_main_worktree_root` and the process invocation inside `_run_entry_point_with_references` are unchanged; the `version` in `em-workflow/.claude-plugin/plugin.json` and in the em-workflow entry of `.claude-plugin/marketplace.json` is unchanged | Inspection |
| TS-12 | Test dependencies (added at create-plan for NFR4) | The added and changed tests import only the standard library and contact no external task system; invalid bytes are written by the stubs as raw bytes | Inspection |

## Code Quality Verification
- Format: none configured / Static analysis: none configured

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | file-tasks with an undecodable `task list` stdout ends with exit code 0 and one JSON summary (`branch=report`, `degraded=true`, `degraded_reason=listing_output_undecodable`), no traceback, report written | TS-1, TS-9 |
| AC-2 | `list_security_tasks` returns `available=False`, `reason=listing_output_undecodable` without raising | TS-2, TS-5 |
| AC-3 | Non-zero exit with invalid stdout yields `listing_exit_nonzero` | TS-3 |
| AC-4 | Invalid bytes on stderr only leave the listing available and `file_tasks` takes `branch=ntd` | TS-4 |
| AC-5 | `TestListingUnavailableReasons` covers six conditions with six distinct reasons | TS-6 |
| AC-6 | `ListingOutcome` docstring states six conditions, consistent with `list_security_tasks` | TS-7 |
| AC-7 | Full test suite and invariants check pass | TS-10 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-2, TS-5, TS-8 |
| FR2 | task0001 | TS-3 |
| FR3 | task0001 | TS-1, TS-2, TS-5 |
| FR4 | task0001 | TS-4 |
| FR5 | task0001 | TS-1 |
| FR6 | task0001 | TS-7 |
| FR7 | task0001 | TS-6 |
| FR8 | task0001 | TS-1 |
| NFR1 | task0001 | TS-11 |
| NFR2 | task0001 | TS-6, TS-10 |
| NFR3 | task0001 | TS-9 |
| NFR4 | task0001 | TS-12 |
| NFR5 | task0001 | TS-11 |
| NFR6 | task0001 | TS-10 |

## Manual Testing (E2E Not Possible)
- [ ] TS-11: inspect the integrated diff against the base for the file set, the two unchanged functions and the unchanged version fields
- [ ] TS-12: inspect the imports and stub construction of the added and changed tests

## Performance / Security Verification (if applicable)
- TM-1: listing output captured as bytes, stdout strictly decoded as UTF-8 after the exit-code check, decode failure mapped to `listing_output_undecodable` and the degraded report branch — checked by TS-1 (no traceback, exit 0, summary printed), TS-2 and TS-5 (no exception escapes `list_security_tasks`)
- TM-2: stderr never decoded; availability decided from the exit code and stdout only — checked by TS-4
- TM-3: `degraded_reason` carries only the fixed token; no listing output or decode-error text in the summary or the report — checked by TS-9

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS-1 to TS-12) | 12 | 10 | 0 | 2 |
| SPEC success criteria (AC-1 to AC-7) | 7 | 7 | 0 | 0 |
| Security (TM-1 to TM-3) | 3 | 3 | 0 | 0 |
