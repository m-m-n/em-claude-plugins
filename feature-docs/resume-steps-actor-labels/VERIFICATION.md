# Verification Document: resume-steps-actor-labels

## Overview
**Feature**: resume-steps-actor-labels / **SPEC.md**: `feature-docs/resume-steps-actor-labels/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/resume-steps-actor-labels/IMPLEMENTATION.md`

## Build Verification
- Command: none (`project.components.main.build_command` is empty; the
  change is Markdown plus Python unittest modules)
- Expected: not applicable

## Test Verification
- Command: `python3 -m unittest discover -s tests`
- Expected: exit code 0, no failures or errors
- Focused run: `python3 -m unittest tests.test_resume_steps_actor_labels tests.test_batch_stop_contract tests.test_batch_quiet_output_skill_wiring tests.test_review_gate_abort_skill_wiring`
- Coverage target: no coverage tool is configured; instead every new
  matcher carries a negative proof and a non-vacuity guard (task0001 AC-6)

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Slice `## Field values` of `batch-terminal-line.md` to the `resume_conditions` bullet (up to the next top-level bullet) | The five fixed strings are present; a forged copy of the pre-change bullet fails the match | Unit |
| TS-2 | In the same bullet, check the AI-first ordering rule and the rule of writing 「判断の後、AI が」 inside the human step | Both are present; a forged bullet with the labels but no ordering rule fails | Unit |
| TS-3 | Slice `SKILL.md` from `## 停止時の報告（停止条件 2-4 のみ）` to `## バッチ構造化結果` | The block after the YAML エラー bullet names `references/batch-terminal-line.md` and states the interactive report takes the same form; the pre-change section text fails | Unit |
| TS-4 | Take the `## Result format` YAML block, decode the `resume_conditions` value, split on the decoded line feed | Each step starts with one of the two labels; no AI step follows a human step; each human label holds exactly one of the three reasons; the current unlabelled example fails; the example has eight lines and the eight keys | Unit |
| TS-5 | Run the whole test suite | The existing pins of `tests/test_batch_quiet_output_skill_wiring.py`, `tests/test_review_gate_abort_skill_wiring.py` and `tests/test_batch_stop_contract.py` pass, including the updated `RESULT_FORMAT_TEXT` | Integration |

## Code Quality Verification
- Format: none configured (`format_command` is empty) / Static analysis:
  none configured
- Change-set check: the integrated diff against the implement base commit
  changes only `em-workflow/references/batch-terminal-line.md`,
  `em-workflow/skills/develop/SKILL.md`, `tests/test_batch_stop_contract.py`,
  `tests/test_resume_steps_actor_labels.py` and files under
  `feature-docs/resume-steps-actor-labels/`
- Version check (NFR4): the same diff touches neither
  `em-workflow/.claude-plugin/plugin.json` nor
  `.claude-plugin/marketplace.json`

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | The `resume_conditions` bullet states the two labels and the three reasons (FR1, FR3, FR4) | TS-1 |
| AC2 | The same bullet states AI-first without exception and the fold-in rule (FR2) | TS-2 |
| AC3 | The stop-report section keeps its three bullets and a following paragraph cites `references/batch-terminal-line.md` and covers the interactive report (FR5) | TS-3 |
| AC4 | The Result format example's `resume_conditions` value is labelled, one physical line, AI first; eight lines and eight keys; `## Escaping` unchanged (FR6) | TS-4, TS-5 |
| AC5 | The new unittest module pins AC1-AC4 with a negative proof per matcher (FR7) | TS-1, TS-2, TS-3, TS-4 |
| AC6 | `python3 -m unittest discover -s tests` passes (NFR1, NFR2, NFR3) | TS-5 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1 |
| FR2 | task0001 | TS-2 |
| FR3 | task0001 | TS-1 |
| FR4 | task0001 | TS-1 |
| FR5 | task0001 | TS-3 |
| FR6 | task0001 | TS-4 |
| FR7 | task0001 | TS-1, TS-2, TS-3, TS-4 |
| NFR1 | task0001 | TS-5 |
| NFR2 | task0001 | TS-5 |
| NFR3 | task0001 | TS-5 |
| NFR4 | task0001 | Version check under Code Quality Verification (no test scenario) |

## Manual Testing (E2E Not Possible)
- [ ] Read the new `resume_conditions` rule and the new stop-report
      paragraph against the goal's motivating stop (fix VERIFICATION.md and
      commit, or allow the overwrite in an interactive run): each
      alternative becomes its own step with its own label, AI steps come
      first, and the human step's reason is one of the three fixed reasons.

## Performance / Security Verification (if applicable)
- TM-1: approval of a change that cannot be undone is one of exactly three
  fixed human reasons, so such a step is never labelled AI-doable — checked
  by TS-1 (the bullet holds 「戻せない変更の承認」 and the
  human-only-for-three-reasons statement; the pre-change bullet fails).
- TM-2: AI work that depends on a human decision is written inside the
  human step and no AI step follows a human step — checked by TS-2 (the
  ordering and fold-in statements are present; a labels-only forgery fails)
  and TS-4 (the labelled example has no AI step after a human step; a
  human-then-AI forgery fails).

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios | 5 | 5 | 0 | 0 |
| Code quality (change-set, version) | 2 | 2 | 0 | 0 |
| Success criteria | 6 | 6 | 0 | 0 |
| Manual review | 1 | 0 | 0 | 1 |
| Security (TM-n) | 2 | 2 | 0 | 0 |
