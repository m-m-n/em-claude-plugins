# Verification Document: scenario-id-fence-scope

## Overview
**Feature**: scenario-id-fence-scope / **SPEC.md**: `feature-docs/scenario-id-fence-scope/SPEC.md` / **IMPLEMENTATION.md**: not written (one task, no cross-task decisions)

## Build Verification
- Command: none (`project.components.main.build_command` is empty)

## Test Verification
- Command: `python3 -m unittest discover -s tests`
- Expected: exit code 0, no failures
- Coverage target: none defined for this project

### Test Scenarios from SPEC.md
`<ID>` stands for a hyphen-less scenario ID. "Reported" means `find_hyphenless_scenario_ids` returns it.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | `<ID>` inside a line-start triple-backtick block, and after the fence characters on its opening line | Not reported | Unit |
| TS-2 | `<ID>` inside a line-start `~~~` block | Not reported | Unit |
| TS-3 | `<ID>` between inline triple backticks in the middle of a sentence | Reported | Unit |
| TS-4 | A line that starts with triple backticks, then `<ID>`, then triple backticks, then the words "for details." | Reported | Unit |
| TS-5 | `<ID>` enclosed by opening and closing lines that start with spaces or tabs | Not reported | Unit |
| TS-6 | `<ID>` on the line after a closing line longer than the opening line, and on the line after a closing line followed by spaces and tabs | Reported | Unit |
| TS-7 | `<ID>` on the line after a run shorter than the opening line, a run of the other character, or a run followed by other characters | Not reported; the block is still open | Unit |
| TS-8 | `<ID>` before and after an unclosed triple-backtick or `~~~` opening line | Only the ID before the opening line is reported | Unit |
| TS-9 | `<ID>` in an HTML comment, and `<ID>` outside a block after an HTML comment opener inside that block | The ID in the comment is not reported; the ID outside the block is reported | Unit |
| TS-10 | `<ID>` on the line right before a block, on the line right after it, and on the line right after a block at the start of the document | All reported | Unit |
| TS-11 | A CRLF document with `<ID>` inside a block and on the line right after the block | The ID inside the block is not reported; the ID after it is reported | Unit |
| TS-12 | `_strip_noise` and `extract_verification_scenario_ids` given a `~~~` block and inline triple backticks | Same result as before the change: the `~~~` block stays and the inline triple backticks are removed | Unit |
| TS-13 | Validation of a planner result whose VERIFICATION.md and task plan hold `<ID>` in a `~~~` block, and of one that holds `<ID>` between inline triple backticks | The first has no error; the second has a `scenario-id-form` error | Integration |
| TS-14 | Run the whole test suite | Passes, including the sha256 pin tests | Integration |

## Code Quality Verification
- Format: none (`project.components.main.format_command` is empty) / Static analysis: none configured

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| - | All functional requirements are implemented and tested | Functional Requirements Coverage below |
| - | All test scenarios pass | TS-1 to TS-14 |
| AC-1 | A hyphen-less ID in a line-start `~~~` block is not reported | TS-2, TS-5 |
| AC-2 | A hyphen-less ID between inline triple backticks is reported | TS-3, TS-4 |
| AC-3 | Opening and closing lines follow FR2 and FR3, and an unclosed opening line excludes to the end of the document | TS-1, TS-5, TS-6, TS-7, TS-8 |
| AC-4 | A hyphen-less ID in an HTML comment is not reported | TS-9 |
| AC-5 | `_strip_noise` and the read side give the same results, and the three documents have no diff | TS-12; the diff of `em-workflow/references/contracts/planner-contract.md`, `em-workflow/references/phases/create-plan-phase.md` and `em-workflow/skills/plan-writing/SKILL.md` against `implement.base_commit` is empty |
| AC-6 | Regression tests exist for `~~~` blocks and inline triple backticks | TS-2, TS-3 and TS-13 run from `tests/test_validate_worker_output.py` |
| AC-7 | `python3 -m unittest discover -s tests` passes, including the sha256 pin tests | TS-14 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2, TS-9, TS-10, TS-13 |
| FR2 | task0001 | TS-1, TS-2, TS-4, TS-5 |
| FR3 | task0001 | TS-5, TS-6, TS-7, TS-11 |
| FR4 | task0001 | TS-7, TS-8 |
| FR5 | task0001 | TS-3, TS-4, TS-13 |
| FR6 | task0001 | TS-10, TS-12; the document diff of AC-5 |
| FR7 | task0001 | TS-14 |
| FR8 | task0001 | TS-14 |
| NFR1 | task0001 | TS-14 (the suite holds the boundary-input test of task0001 AC-4) |

## Manual Testing (E2E Not Possible)
None.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios | 14 | 14 | 0 | 0 |
| Success criteria | 9 | 9 | 0 | 0 |
| Requirements coverage | 9 | 9 | 0 | 0 |
