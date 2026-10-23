# Verification Document: completion-tip-single-capture

## Overview
**Feature**: completion-tip-single-capture / **SPEC.md**: `feature-docs/completion-tip-single-capture/SPEC.md` / **IMPLEMENTATION.md**: not written (single task, no cross-task decisions) / **THREAT-MODEL.md**: `feature-docs/completion-tip-single-capture/THREAT-MODEL.md` (verdict: `no-trust-boundary`)

## Build Verification
- Command: none (`project.components.main.build_command` is empty)
- Expected: not applicable

## Test Verification
- Command: `python3 -m unittest discover -s tests`
- Expected: exit code 0, no failures or errors
- Coverage target: not measured (no coverage tooling is configured for this
  component); every scenario below is backed by a passing test or check

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS1 | In the whitespace-normalized Step I.3 section of `em-workflow/references/implement-phase.md`, take the span from "on the worktree just refreshed" up to the following "commit-docs.sh" | The span contains `completed_at_commit` and `$COMPLETION_TIP` | Unit (new) |
| TS2 | The same span as TS1 | The span contains no "rev-parse" and no "$(git" | Unit (new) |
| TS3 | Step I.3's exit-4 retry wording | Step I.3 states that `completed_at_commit` is re-written from the re-captured `$COMPLETION_TIP` on an exit-4 retry | Unit (new) |
| TS4 | The TS1/TS2 matchers applied to a verbatim pre-change sample of the step 3 text | TS1's matcher fails on the sample; a non-vacuity guard shows the sample contains `completed_at_commit` | Unit (new) |
| TS5 | Existing tests `test_completed_at_commit_wording_is_unchanged`, `TestStepI3CompletionWriteHasTipArgument`, `TestStepI3PinnedCompletionSentenceByteIdentical`, and the `tests/test_tip_capture_idiom_uniformity.py` per-site classes for `COMPLETION_TIP` | All pass, with their test files unmodified | Unit (existing) |
| TS6 | Diff scope: `git diff --name-only main...em-workflow/completion-tip-single-capture/integration` | Lists only `em-workflow/references/implement-phase.md`, paths under `tests/`, `feature-docs/completion-tip-single-capture/**` and `test-docs/completion-tip-single-capture/**`; `em-workflow/scripts/commit-docs.sh`, hook files, other scripts, agent definitions, `tests/test_rework_synthesis_contract.py` and `tests/test_tip_capture_idiom_uniformity.py` are absent | Diff check |
| TS7 | Version fields: the same diff as TS6 | `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` are absent | Diff check |

TS1-TS5 come from SPEC.md's Test Scenarios. TS6 and TS7 check SPEC.md AC-3
and AC-6 (diff absence) and give NFR1 and NFR3 a verifying scenario.

SPEC.md edge cases are covered as follows: exit-4 retry by TS3; pinned
sentence adjacency by TS5 and the manual check below; section-scoped
first-match matchers by TS5.

## Code Quality Verification
- Format: none configured (`format_command` is empty)
- Static analysis: none configured

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | Step I.3 step 3 states that the written `completed_at_commit` is `$COMPLETION_TIP` from step 1 and that the pinned sentence's expression is not evaluated separately | TS1, TS2 |
| AC-2 | Step I.3 states that on an exit-4 retry `completed_at_commit` is re-written from the fresh `$COMPLETION_TIP` | TS3 |
| AC-3 | The pinned sentence is present byte-for-byte and `tests/test_rework_synthesis_contract.py` is absent from the diff | TS5, TS6 |
| AC-4 | A test fails against the current step 3 wording, passes after the change, and imports only the standard library | TS4, plus inspection of the new test module's imports |
| AC-5 | `python3 -m unittest discover -s tests` exits 0 | Test Verification command |
| AC-6 | `em-workflow/scripts/commit-docs.sh`, `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` are absent from the diff | TS6, TS7 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS1, TS2 |
| FR2 | task0001 | TS3 |
| FR3 | task0001 | TS5, TS6 |
| FR4 | task0001 | TS4 |
| NFR1 | task0001 | TS6 |
| NFR2 | task0001 | TS5, TS6 |
| NFR3 | task0001 | TS7 |

## Manual Testing (E2E Not Possible)
- [ ] Reproduction check: read Step I.3 step 1 and step 3 together and
  confirm that the single-capture origin of `completed_at_commit` follows
  from the command sequence alone, with no second capture implied.
- [ ] Pinned sentence adjacency: read the text around the pinned sentence and
  confirm no new wording sits inside it and its lines are not re-wrapped.

## Performance / Security Verification (if applicable)
- Not applicable: SPEC.md states no performance requirement, and
  THREAT-MODEL.md's verdict is `no-trust-boundary`, so there is no TM-n item.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Unit tests (TS1-TS5) | 5 | 5 | 0 | 0 |
| Diff checks (TS6-TS7) | 2 | 2 | 0 | 0 |
| Manual checks | 2 | 0 | 0 | 2 |
| Security (TM-n) | 0 | 0 | 0 | 0 |
| Total | 9 | 7 | 0 | 2 |
