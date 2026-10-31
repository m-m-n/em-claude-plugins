# Verification Document: codex-consult-output-scratchpad

## Overview
**Feature**: codex-consult-output-scratchpad / **SPEC.md**: `feature-docs/codex-consult-output-scratchpad/SPEC.md` / **IMPLEMENTATION.md**: none (single-task feature at the reduced tier) / **THREAT-MODEL.md**: `feature-docs/codex-consult-output-scratchpad/THREAT-MODEL.md`

## Build Verification
- Command: none (`project.components.main.build_command` is empty; the change is documents and Python tests only)
- Expected: not applicable

## Test Verification
- Command: `python3 -m unittest discover -s tests`
- Expected: exit code 0, no failures or errors, no regression against the base revision
- Coverage target: not applicable (structural doc tests; no coverage tooling is configured)

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | question-resolution.md: extract the region between "2. **Wrapper invocation.**" and "3. **One turn per call.**", collapse its whitespace, and check for the scratchpad-placement phrase (naming stdout and stderr) and the project-root and current-directory-relative prohibition phrases | Both phrase groups are present; extraction fails loudly when either marker is missing or the markers are out of order | Unit |
| TS-2 | question-resolution.md negative twin: run the TS-1 matchers against a synthetic copy of the pre-fix step 2 text | Neither matcher matches | Unit |
| TS-3 | SKILL.md: within `TIER_SECTION`, slice from "3. **Codex 事前調査**" to "4. **no-work 停止**". Using `_contains`, check that the slice names `references/question-resolution.md`, "Codex consultation procedure" and "Wrapper invocation", and check that it does not restate the rule | The citation is present. The rule sentence(s) from question-resolution.md are absent verbatim, and the placement terms (scratchpad / スクラッチパッド / project root / プロジェクトルート) are absent | Unit |
| TS-4 | SKILL.md negative twin: run the TS-3 citation matcher against a synthetic copy of the pre-fix step 3 text | The citation matcher does not match | Unit |
| TS-5 | Retention. In `tests/test_question_resolution_doc.py`: the wrapper-invocation pins (including `test_codex_procedure_wrapper_invocation`), the document-wide negative pins and a new verbatim pin on the invocation line, the `--litellm` values and the 600000-millisecond timeout. In `tests/test_develop_tier_staged_procedure.py`: the call-order, AC-6 forbidden-token and locator tests | All pass unchanged | Unit |
| TS-6 | No undefined shell variable (planner-added for NFR1). Every shell-variable token in the step 2 region and in the step 3 region is either already present in that region's pre-fix text or in the `${VAR:-default}` form, and a synthetic region containing a bare `$S` redirect fails the check | The fixed regions pass and the synthetic `$S` region fails | Unit |
| TS-7 | Diff integrity (planner-added for FR3, NFR4, NFR5, NFR6). Inspect the feature diff against `workflow.implement.base_commit` | (a) `em-workflow/references/question-resolution.md` and `em-workflow/skills/develop/SKILL.md` show added lines only; (b) no Notion URL and no absolute path under a home directory in any added line; (c) no `plugin.json` and no `.claude-plugin/marketplace.json` in the changed-file set; (d) the step 2 addition is English and the step 3 addition is Japanese | Inspection |

SPEC.md lists TS-2 and TS-4 together under AC-5 (FR5, FR6). TS-2 is the
question-resolution.md half (FR5) and TS-4 the SKILL.md half (FR6).

## Code Quality Verification
- Format: none (`format_command` is empty)
- Static analysis: none configured

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | AC-1: the step 2 region states that saved wrapper output (stdout/stderr) is placed in the session scratchpad | TS-1 |
| SC-2 | AC-2: the step 2 region states that saved output is never written under the project root and never through a path relative to the current directory | TS-1 |
| SC-3 | AC-3: the invocation line and the `--litellm` variants are byte-for-byte unchanged, and `test_codex_procedure_wrapper_invocation` still passes | TS-5, TS-7 (a) |
| SC-4 | AC-4: the SKILL.md tier step 3 region cites `references/question-resolution.md`'s Codex consultation procedure step 2 and does not restate the rule | TS-3 |
| SC-5 | AC-5: the new assertions in both test modules pass, and each negative twin shows that the pre-fix wording fails its matcher | TS-1, TS-2, TS-3, TS-4 |
| SC-6 | AC-6: `python3 -m unittest discover -s tests` passes with no regressions | Test Verification command |
| SC-7 | All functional requirements are implemented and tested | Functional Requirements Coverage table below |
| SC-8 | All test scenarios pass | TS-1 through TS-7 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2 |
| FR2 | task0001 | TS-1, TS-2 |
| FR3 | task0001 | TS-5, TS-7 |
| FR4 | task0001 | TS-3, TS-4 |
| FR5 | task0001 | TS-1, TS-2 |
| FR6 | task0001 | TS-3, TS-4 |
| NFR1 | task0001 | TS-6 |
| NFR2 | task0001 | TS-5 |
| NFR3 | task0001 | TS-5 |
| NFR4 | task0001 | TS-7 |
| NFR5 | task0001 | TS-7 |
| NFR6 | task0001 | TS-7 |

## E2E Testing
Not applicable: no E2E framework is detected (`e2e_test_command` is empty).

## Manual Testing (E2E Not Possible)
- [ ] Read step 2 of the Codex consultation procedure as a whole. The added rule reads as covering every turn on both harness entries (`codex` and `litellm`, including after a mid-consultation move) and both streams, and as imposing nothing when output is not saved to a file.
- [ ] Read step 3 of the SKILL.md tier section. The added citation reads as covering a saved pre-survey JSON output, and the step's existing sentences are intact.

## Performance / Security Verification (if applicable)
- TM-1: When saved, wrapper output (stdout and stderr) goes only into the session scratchpad. It is never written under `{project_root}` and never through a cwd-relative redirect. The rule is defined once in step 2 and cited from the develop tier pre-survey. How it is checked: TS-1 and TS-2 (rule present in step 2, absent from the pre-fix text) and TS-3 (citation present in the tier pre-survey), all automated.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios | 7 | 6 | 0 | 1 |
| Success criteria | 8 | 8 | 0 | 0 |
| Manual read-through | 2 | 0 | 0 | 2 |
| Security (TM-n) | 1 | 1 | 0 | 0 |
