# Verification Document: build-format-both-excluded-tests

## Overview
**Feature**: build-format-both-excluded-tests / **SPEC.md**: `feature-docs/build-format-both-excluded-tests/SPEC.md` / **IMPLEMENTATION.md**: not written (reduced tier, single task, no file shared between tasks) / **THREAT-MODEL.md**: `feature-docs/build-format-both-excluded-tests/THREAT-MODEL.md`

## Build Verification
- Command: none (`project.components.main.build_command` is empty)
- Expected: not applicable

## Test Verification
- Command: `python3 -m unittest discover -s tests` (repository root)
- Expected: exit code 0, every module passes
- Coverage target: not applicable (document-contract tests; the project
  defines no coverage tool)

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS1 | Step 3 of implementer.md and the Command execution gate section of the worktree-task-workflow SKILL.md each contain exactly one FR1 sentence (format non-execution does not override another rule's `tests: "fail"`, citing the build-also-excluded case) | The FR1 matcher returns exactly one sentence per section, distinct from the existing format sentence | Unit |
| TS2 | The FR1 matcher is applied to the false sentence stating that even when build and format both fall outside the cd prefix form, `tests` follows the result of the test command | No match | Unit |
| TS3 | The FR1 matcher is applied to the false sentence without the build case, and to the existing format sentence (the GOOD_FORMAT wording) | No match for either | Unit |
| TS4 | Section extraction is applied to documents whose Step 3 / gate heading has been renamed | Extraction raises; the assertion never passes over an empty string | Unit |
| TS5 | `python3 -m unittest discover -s tests` is run, including the seven modules listed in SPEC NFR1, with none of them modified | Full pass | Unit |
| TS6 | The task branch's diff against its base is inspected for the two procedure documents and the version files (derived from SPEC AC3 / AC6) | The two documents show added lines only; `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` are unchanged | Diff check |

## Code Quality Verification
- Format: none (`project.components.main.format_command` is empty)
- Static analysis: none defined; the new module's standard-library-only
  import check runs inside the test suite (TS5)

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | Step 3 of implementer.md has exactly one FR1 sentence citing the build-also-excluded case | TS1 |
| AC2 | The gate section of SKILL.md has exactly one FR1 sentence with the same statement | TS1 |
| AC3 | Existing format / build / test sentences, the deny bullet and the Step 7 JSON field set are unchanged | TS5, TS6 |
| AC4 | The document test covers the both-excluded case and its matcher is paired with false sentences | TS2, TS3, TS4 |
| AC5 | NFR1 modules pass unmodified and the full suite passes | TS5 |
| AC6 | The plugin version is unchanged | TS6 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS1 |
| FR2 | task0001 | TS1, TS5 |
| FR3 | task0001 | TS1, TS2, TS3, TS4 |
| NFR1 | task0001 | TS5 |
| NFR2 | task0001 | TS5 |
| NFR3 | task0001 | TS5 |
| NFR4 | task0001 | TS6 |
| NFR5 | task0001 | TS5 |

## Manual Testing (E2E Not Possible)
- [ ] Read implementer.md Step 3 and the SKILL.md gate section around the new
  sentence: it reads as a qualification of the existing format sentence and
  contradicts neither the build sentence nor the deny bullet. Against the
  SPEC edge cases: build, format and test all excluded → `tests` is "fail";
  format excluded plus a hook deny → "fail"; only format excluded → `tests`
  follows the test command's result; an empty build / format string → the
  command does not exist and FR1 does not apply.

## Performance / Security Verification (if applicable)
- TM-1: both documents state that not running the format command does not
  override a `tests: "fail"` decided by another rule, citing the
  build-also-excluded case — checked by TS1 (exactly one such sentence per
  section) with the matcher's non-vacuity shown by TS2 and TS3.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios | 6 | 6 | 0 | 0 |
| Success criteria | 6 | 6 | 0 | 0 |
| Manual reading | 1 | 0 | 0 | 1 |
| Security (TM-n) | 1 | 1 | 0 | 0 |
