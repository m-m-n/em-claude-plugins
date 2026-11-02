# Verification Document: scenario-id-ts-hyphen

## Overview
**Feature**: scenario-id-ts-hyphen / **SPEC.md**: `feature-docs/scenario-id-ts-hyphen/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/scenario-id-ts-hyphen/IMPLEMENTATION.md`

## Build Verification
- Command: none (`project.components.main.build_command` is empty; the
  component is Python run from source)
- Expected: not applicable

## Test Verification
- Command: `python3 -m unittest discover -s tests` (from the repository root)
- Expected: exit code 0, every test passes
- Coverage target: not measured (no coverage tooling is configured).
  Coverage is judged by the scenario and requirement mapping below.
- Targeted runs, useful while diagnosing:
  - `python3 -m unittest tests.test_validate_worker_output tests.test_gate_option_vocabulary tests.test_requirements_tests_replace tests.test_digest_contract_alignment`
  - `python3 -m unittest tests.test_scenario_id_spec_writer_docs tests.test_scenario_id_plan_writing_rule tests.test_scenario_id_planner_docs`

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Completed implementation-planner result; the feature directory's VERIFICATION.md Test Scenarios section carries a hyphen-less ID | The validator returns a `scenario-id-form` error whose message names VERIFICATION.md and the ID | Unit |
| TS-2 | Completed implementation-planner result; the plan of a tasks_patch entry (`tasks/task0001.md`) carries a hyphen-less ID in its body | A `scenario-id-form` error naming the task, the plan path and the ID | Unit |
| TS-3 | VERIFICATION.md and every task plan use only hyphenated IDs | No `scenario-id-form` error | Unit |
| TS-4 | VERIFICATION.md carries both the hyphenated and the hyphen-less spelling of the same number | A `scenario-id-form` error listing only the hyphen-less spelling | Unit |
| TS-5 | Hyphen-less IDs appear only inside fenced code blocks or HTML comments | No `scenario-id-form` error | Unit |
| TS-6 | An ASCII letter or digit directly precedes `TS` and its digits (the SPEC's X- and U-prefixed examples) | No `scenario-id-form` error | Unit |
| TS-7 | A tasks_patch entry whose plan's final path segment is `TASK.md`, with a hyphen-less ID in its body | No `scenario-id-form` error from this check | Unit |
| TS-8 | rework-planner result; the feature directory's VERIFICATION.md uses the hyphen-less form | No `scenario-id-form` error; the existing rework_index checks still judge hyphen-less IDs in old and new documents | Unit |
| TS-9 | `TestScenarioIdExtractionAcceptsBothForms`, `TestReworkIndexNoveltyWithBothScenarioIdForms` and `tests/test_requirements_tests_replace.py` run with no change to their expectations | All pass | Unit |
| TS-10 | spec-writer.md, spec-document.md, spec-writer-contract.md and the plan-writing SKILL.md require the hyphenated form for new documents; the plan-writing rule limits the hyphen-less form to reading existing documents | The document-content tests pass | Unit (document content) |
| TS-11 | create-plan-phase.md section 9's validator-implemented list and the planner documents (implementation-planner.md, planner-contract.md) describe the scenario-ID form check | The document-content tests pass | Unit (document content) |
| TS-12 | The sha256 pins in `tests/test_gate_option_vocabulary.py` match the new contents of the validator and its test module | The pin tests pass and `python3 -m unittest discover -s tests` passes in full | Integration (full suite) |

### Edge cases (mapped to task Acceptance Criteria)
- No `--feature-dir`: the check does not run (task0001 AC-4).
- Implementation-planner result whose status is not `completed`, with a
  hyphen-less VERIFICATION.md left from an earlier run: no
  `scenario-id-form` error (task0001 AC-4; IMPLEMENTATION.md D1).
- No VERIFICATION.md in the feature directory (minimal tier): no error for
  that target (task0001 AC-4).
- Plan files of carried task ids (not named by any `tasks_patch.entries`
  item): not checked (task0001 AC-4).
- A hyphen-less ID inside an inline code span, at the very start of the
  document, or directly after Japanese text: reported (task0001 AC-3).
- A re-plan that rewrites a formerly hyphen-less VERIFICATION.md: the
  rewritten file must use the hyphenated form, otherwise
  `scenario-id-form` (task0001 AC-1).
- A SPEC.md that uses the hyphen-less form: the plan-writing rule tells the
  planner to write the same numbers in the hyphenated form and leave SPEC.md
  as it is (task0003 AC-4).
- `tests_replace` from a hyphen-less ID to its hyphenated spelling keeps
  being accepted (TS-9).

## Code Quality Verification
- Format: none configured (`project.components.main.format_command` is empty)
- Static analysis: none configured

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | New SPEC.md, VERIFICATION.md and tasks/*.md use the TS-n form (spec-writer.md, spec-document.md, spec-writer-contract.md and plan-writing SKILL.md require it) | TS-10, TS-11 |
| AC-2 | An implementation-planner result whose new VERIFICATION.md or task plans contain a hyphen-less ID is rejected by `validate-worker-output.py` | TS-1, TS-2, TS-4, TS-7, plus TS-3, TS-5, TS-6 for the negative side |
| AC-3 | Reading and rework validation of features with existing hyphen-less documents work as before | TS-8, TS-9 |
| AC-4 | `python3 -m unittest discover -s tests` passes in full and the sha256 pins are updated | TS-12 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0002 | TS-10 (document-content tests in `tests/test_scenario_id_spec_writer_docs.py`) |
| FR2 | task0003 | TS-10 (document-content tests in `tests/test_scenario_id_plan_writing_rule.py`) |
| FR3 | task0001 | TS-1, TS-2, TS-3, TS-4, TS-5, TS-6, TS-7, TS-8 (unit tests in `tests/test_validate_worker_output.py`) |
| FR4 | task0001 | TS-8, TS-9 |
| FR5 | task0004 | TS-11 (document-content tests in `tests/test_scenario_id_planner_docs.py`) |
| NFR1 | task0001 | TS-9 |
| NFR2 | task0001 | TS-12 |
| NFR3 | task0001, task0002, task0003, task0004 | TS-12 |

## E2E Testing
Not applicable: the project has no E2E framework (SPEC.md: "Existing E2E
tests: None").

## Manual Testing (E2E Not Possible)
None. The behavior of the LLM workers is constrained through the
document-content tests (TS-10, TS-11) and enforced for the planner by the
validator check (TS-1 to TS-8).

## Performance / Security Verification (if applicable)
- TM-1: the check reads a plan only after it passes the existing plan-path
  checks, and reads VERIFICATION.md only when it is a regular, non-symlink
  file — checked by task0001 AC-5's unit tests. An absolute, `..` or
  symlinked `plan` produces only the existing task-plan errors, even when its
  target holds a hyphen-less ID. A symlinked VERIFICATION.md produces one
  `scenario-id-form` error, and no ID from its target appears in any message.
- TM-2: the VERIFICATION.md read is bounded, and an unreadable file is
  reported, never raised or silently skipped — checked by task0001 AC-6's unit
  tests. A VERIFICATION.md above the plan-read byte limit, a directory named
  VERIFICATION.md, or a non-UTF-8 VERIFICATION.md each produce one
  `scenario-id-form` error. The validation function returns without raising,
  and the command line exits 1, not 2.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Validator check behavior (TS-1 to TS-8) | 8 | 8 | 0 | 0 |
| Existing read-side compatibility (TS-9) | 1 | 1 | 0 | 0 |
| Document content (TS-10, TS-11) | 2 | 2 | 0 | 0 |
| Pins and full suite (TS-12) | 1 | 1 | 0 | 0 |
| Security mitigations (TM-1, TM-2) | 2 | 2 | 0 | 0 |
| **Total** | 14 | 14 | 0 | 0 |
