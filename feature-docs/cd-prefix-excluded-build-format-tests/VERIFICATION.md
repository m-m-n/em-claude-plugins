# Verification Document: cd-prefix-excluded-build-format-tests

## Overview
**Feature**: cd-prefix-excluded-build-format-tests / **SPEC.md**: `feature-docs/cd-prefix-excluded-build-format-tests/SPEC.md` / **IMPLEMENTATION.md**: not created (there is one task, so no file is shared between tasks) / **THREAT-MODEL.md**: `feature-docs/cd-prefix-excluded-build-format-tests/THREAT-MODEL.md`

## Build Verification
- Command: none (`project.components.main.build_command` is empty)
- Expected: not applicable

## Test Verification
- Command: `python3 -m unittest discover -s tests`
- Expected: exit code 0 and no failing or erroring test
- Coverage target: not applicable (document-contract tests; no coverage tool is configured)

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS1 | Build statement in implementer.md "Step 3: Verify the worktree" and in the SKILL.md "Command execution gate" section (AC1, AC3; FR1, FR3) | Each section holds exactly one sentence with `project_commands.build`, `tests: "fail"`, `notes`, "not run" and the not-covered reason | Unit (document contract) |
| TS2 | Format statement in the same two sections (AC2, AC3; FR2, FR3) | Each section holds exactly one sentence with `project_commands.format`, `notes`, "not run", the not-covered reason, `tests` following the test command's result, and no "fail" from the format non-run alone | Unit (document contract) |
| TS3 | The build matcher against the existing test-command sentence and the gate section's deny sentence (AC5; FR5) | No match for either | Unit (document contract) |
| TS4 | The format matcher against a forged sentence that says the format non-run sets `tests: "fail"`, and against a forged sentence with no `notes` (AC5; FR5) | No match for either | Unit (document contract) |
| TS5 | Section extraction on a document whose heading has been renamed (FR5) | Extraction raises; no assertion passes over an empty string | Unit (document contract) |
| TS6 | The full suite, including the six NFR1 modules (AC4, AC6; FR4, NFR1, NFR2, NFR3, NFR5) | `python3 -m unittest discover -s tests` passes; the six NFR1 modules are unedited | Unit (suite run) |

## Code Quality Verification
- Format: none (`project.components.main.format_command` is empty)
- Static analysis: none configured
- The new test module imports only the standard library (checked inside TS6 by the module's own import assertion)

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | implementer.md Step 3 holds the build sentence (FR1, FR3) | TS1 (Step 3 part) |
| AC2 | implementer.md Step 3 holds the format sentence (FR2, FR3) | TS2 (Step 3 part) |
| AC3 | The SKILL.md Command execution gate section holds the same statements (FR1-FR3) | TS1 and TS2 (gate section part) |
| AC4 | The existing test-command sentence, the gate section's deny bullet and the Step 7 JSON block field set are unchanged (FR4) | TS6: `tests/test_implementer_cd_prefix_exclusion_docs.py` and `tests/test_implementer_untrusted_data_rule.py` pass unedited |
| AC5 | Document tests exist and every matcher is paired with forged sentences (FR5) | TS3, TS4 |
| AC6 | The NFR1 modules pass unchanged and the full suite passes (NFR1-NFR3, NFR5) | TS6, plus: the diff from `workflow.implement.base_commit` to the integration branch names none of the six NFR1 module paths |
| V-1 | The plugin version is unchanged (NFR4) | The diff from `workflow.implement.base_commit` to the integration branch names neither `em-workflow/.claude-plugin/plugin.json` nor `.claude-plugin/marketplace.json` |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS1 |
| FR2 | task0001 | TS2 |
| FR3 | task0001 | TS1, TS2 |
| FR4 | task0001 | TS6 |
| FR5 | task0001 | TS3, TS4, TS5 |
| NFR1 | task0001 | TS6, and the AC6 diff check |
| NFR2 | task0001 | TS6 |
| NFR3 | task0001 | TS6 |
| NFR4 | task0001 | V-1 (diff check; no test scenario) |
| NFR5 | task0001 | TS6 |

## Manual Testing (E2E Not Possible)
- [ ] M-1: Read the build and format sentences in implementer.md Step 3 and in the SKILL.md Command execution gate section. Both sections state the same `tests` value and the same `notes` content for each command (AC3).
- [ ] M-2: Read the four new sentences. None of them describes another way to run the build or format command that the cd prefix form does not cover: no alternative form, no later run, no partial run (TM-1).

## Performance / Security Verification (if applicable)
- TM-1: Each new build or format sentence states that the command is not run, and the existing handling sentence (not run with the cd prefix, not run without it, not rewritten or split) stays unchanged, exactly once per section. How it is checked:
  - TS1 and TS2: the new matchers require "not run" in each new sentence;
  - TS6: `tests/test_implementer_cd_prefix_exclusion_docs.py` still finds exactly one handling sentence in each section;
  - M-2.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS1-TS6) | 6 | 6 | 0 | 0 |
| Code quality | 1 | 1 | 0 | 0 |
| Success criteria (AC1-AC6, V-1) | 7 | 7 | 0 | 0 |
| Manual testing (M-1, M-2) | 2 | 0 | 0 | 2 |
| Security (TM-1) | 1 | 1 | 0 | 0 |
