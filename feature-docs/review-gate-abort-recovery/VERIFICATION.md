# Verification Document: review-gate-abort-recovery

## Overview
**Feature**: review-gate-abort-recovery / **SPEC.md**: `feature-docs/review-gate-abort-recovery/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/review-gate-abort-recovery/IMPLEMENTATION.md`

## Build Verification
- Command: none — `build_command` is empty for both components (`repo-tests`, `plugin-invariants`) in workflow.yaml
- Expected: not applicable

## Test Verification
- Command (repo-tests): `python3 -m unittest discover -s tests`
- Command (plugin-invariants): `python3 em-workflow/scripts/check-plugin-invariants.py .`
- Expected: exit code 0 for both
- Coverage target: not applicable — the added tests are document-structure tests and no coverage tool is configured

### Test Scenarios from SPEC.md
SPEC.md numbers its scenarios TS1–TS7; they appear here as TS-1–TS-7. TS-8
(from NFR6) and TS-9 (from FR2 / FR4, integrated citation resolution) are
added by this plan.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | (AC1) Slice review-phase.md Phase R5 and check the gate-abort rule: `workflow[review].status` is written `pending`; `review.status = pending` and `review.needs_rework = true` are kept; `failed` is written to neither; the targets are enumerated (Classification gate stop / inapplicable, origin-membership failure, malformed pairing). Inputs lacking each wording are rejected | The rule is present in the SC1 block exactly once, every element matcher passes, and each negative twin is rejected | Unit |
| TS-2 | (AC2) SKILL.md Step B 「spec-change 遷移のゲート呼び出し（バッチのみ）」 paragraph cites the Phase R5 definition, and every phrase `tests/test_gate_outcome_packet_lifecycle.py` pins remains | The citation names `references/review-phase.md`, `Phase R5` and the SC1 label; the paragraph restates no rule value; the existing module passes unedited; the stop-condition-3 blocks NFR1 protects are unchanged | Unit |
| TS-3 | (AC3) The Phase R5 definition states the resume path: Step B selects review (`pending`), stop condition 3 does not fire, a review round re-runs, the obsolete packet is not re-presented | Every resume-path element matcher passes and each negative twin is rejected | Unit |
| TS-4 | (AC4) Near the sentence "`status: failed` is reserved for the two structural degradation triggers of Phase R3b", the `perspective_runs` evaluator entry is stated as its target; workflow-schema.md's status values are unchanged | The scope statement is present in the same paragraph and the matcher rejects the pre-change paragraph; the workflow-schema.md value sets equal {pending, in_progress, completed, failed, needs_update} for steps and {pending, in_progress, completed, failed} for the review block | Unit |
| TS-5 | (AC5) The recovery procedure states its applicability (`workflow[review].status` is `failed` and the last `classification` entry in `phase-state/rework.yaml` has `decision: stop`), the restored values (both statuses `pending`, `needs_rework` `true`), the `commit-docs.sh` commit, and non-application when the record does not confirm; SKILL.md 「停止時の報告（停止条件 2-4 のみ）」 and `resume_conditions` refer to it | Every SC2 element matcher passes; the stop-report paragraph cites the SC2 label and states in-full carriage in the report and `resume_conditions`; each negative twin is rejected | Unit |
| TS-6 | (AC6) Every added matcher has a negative twin that fails on input without the wording | Each negative-twin test passes (its matcher rejects the twin) and every sliced region passes its non-vacuity check | Unit |
| TS-7 | (AC7) Run `python3 -m unittest discover -s tests`, including `test_classification_gate.py`, `test_rework_synthesis_contract.py`, `test_gate_outcome_packet_lifecycle.py` and the two new modules, and `python3 em-workflow/scripts/check-plugin-invariants.py .` | Both exit 0 with no existing test module modified | Integration |
| TS-8 | (NFR6) The integrated diff against `workflow.implement.base_commit` leaves the plugin version fields untouched | Neither `em-workflow/.claude-plugin/plugin.json` nor `.claude-plugin/marketplace.json` appears in the diff | Integration |
| TS-9 | (FR2, FR4, NFR3) On the integrated tree, each label SKILL.md cites (SC1 in the Step B gate-call paragraph, SC2 in the stop-report section) resolves in review-phase.md | Each cited label text occurs in its bold definition form exactly once inside review-phase.md Phase R5, and SKILL.md's two citations name that text verbatim | Integration |

## Code Quality Verification
- Format: none configured (`format_command` is empty for both components)
- Static analysis: `python3 em-workflow/scripts/check-plugin-invariants.py .` (run under Test Verification)

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | review-phase.md R5 defines the FR1 rule in one place, enumerates the targeted gate aborts, and has no step writing `failed` to either status | TS-1 |
| AC2 | SKILL.md Step B's spec-change gate-call paragraph cites the AC1 definition and keeps the existing pinned wording | TS-2, TS-9 |
| AC3 | The SSOT text implies that resuming develop after a gate abort lets Step B select review (`pending`), stop condition 3 does not fire, a review round re-runs, and the obsolete packet is not re-presented | TS-3, Manual MT-1 |
| AC4 | The failed reservation is stated to cover the `perspective_runs` evaluator entry, consistent with the review step's status handling, and workflow-schema.md's allowed values are unchanged | TS-4 |
| AC5 | The legacy `review: failed` recovery procedure (applicability, restored values, commit) is in the SSOT, and the stop report and `resume_conditions` for stop condition 3 on review's `failed` refer to it | TS-5, TS-9 |
| AC6 | The added tests pin AC1–AC5's wording and every matcher has a negative twin | TS-6 |
| AC7 | `python3 -m unittest discover -s tests` passes | TS-7 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1 |
| FR2 | task0002 | TS-2, TS-9 |
| FR3 | task0001 | TS-3, Manual MT-1 |
| FR4 | task0001, task0002 | TS-5, TS-9 |
| FR5 | task0001 | TS-4 |
| FR6 | task0001, task0002 | TS-6 |
| NFR1 | task0002 | TS-2, TS-7, Manual MT-2 |
| NFR2 | task0001, task0002 | TS-2, TS-7 |
| NFR3 | task0001, task0002 | TS-1, TS-2, TS-9 |
| NFR4 | task0001, task0002 | TS-2, TS-7 |
| NFR5 | task0001 | TS-4 |
| NFR6 | task0001, task0002 | TS-8 |
| NFR7 | task0001, task0002 | TS-7 |

## Manual Testing (E2E Not Possible)
- [ ] MT-1 Reproduction walkthrough: walk the five reproduction steps recorded in workflow.yaml `goal` against the integrated SSOT text — at step 3 the SSOT prescribes `workflow[review].status: pending` and forbids `failed` (review-phase.md Phase R5, SC1 block); at step 5 Step B selects `review` as `pending`, stop condition 3 does not fire, and the next review round leads into the ordinary rework path.
- [ ] MT-2 Diff scope (NFR1): the integrated diff against `workflow.implement.base_commit` touches only `em-workflow/references/review-phase.md`, `em-workflow/skills/develop/SKILL.md`, the two new test modules and this feature's `feature-docs/` / `test-docs/` paths, and SKILL.md's diff consists of the two insertions only (the Step B gate-call paragraph and the 停止時の報告 section).
- [ ] MT-3 Legacy recovery readability (FR4): reading the SC2 block on its own, a reader can tell when it applies, which values to restore, how the write is committed, and that it is not applied when the `classification` record does not confirm the gate abort.

## Performance / Security Verification (if applicable)
- Not applicable: SPEC.md states no performance requirement, and THREAT-MODEL.md's verdict is `no-trust-boundary` (no TM-n).

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS-1–TS-9) | 9 | 9 | 0 | 0 |
| Success criteria (AC1–AC7) | 7 | 7 | 0 | 1 (AC3 also MT-1) |
| Requirements coverage (FR1–FR6, NFR1–NFR7) | 13 | 13 | 0 | 2 (FR3 MT-1, NFR1 MT-2) |
| Manual checks (MT-1–MT-3) | 3 | 0 | 0 | 3 |
| Security (TM-n) | 0 | 0 | 0 | 0 |
