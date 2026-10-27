# Verification Document: codex-hook-tty-reaper-anchor-identity

## Overview
**Feature**: codex-hook-tty-reaper-anchor-identity / **SPEC.md**: `feature-docs/codex-hook-tty-reaper-anchor-identity/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/codex-hook-tty-reaper-anchor-identity/IMPLEMENTATION.md` / **THREAT-MODEL.md**: `feature-docs/codex-hook-tty-reaper-anchor-identity/THREAT-MODEL.md`

## Build Verification
- Command: none (`project.components.main.build_command` is empty; the
  Python scripts are not built).
- Expected: not applicable.

## Test Verification
- Command: `python3 -m unittest discover -s tests` (workflow.yaml
  `project.components.main.test_command`).
- Targeted run: `python3 -m unittest tests.test_codex_hook_tty_reaper`.
- Expected: exit code 0, no failures and no errors.
- Coverage target: not measured (no coverage tooling is configured). The
  criterion is scenario coverage: every TS-n below has at least one passing
  test.

### Test Scenarios from SPEC.md
| ID | Source | Scenario | Expected Result | Test Type |
|----|--------|----------|-----------------|-----------|
| TS-1 | SPEC.md TS1 | In-process: after the ancestor-chain read and before the snapshot, the anchor PID's entry is replaced by a process X with a later start time; a descendant of X has stdin on `/dev/pts/*` | No SIGTERM / SIGKILL recorded and no pidfd opened (`world.sent` and `world.open_calls` empty); the test fails against the pre-fix script | Unit |
| TS-2 | SPEC.md TS2 | Same layout as TS-1, with X's start time exactly one tick after the anchor's | Nothing stopped, no pidfd opened | Unit |
| TS-3 | SPEC.md TS3 | After the ancestor-chain read and before the snapshot, only the anchor's ppid changes (same start time) | The anchor's descendant whose stdin is on `/dev/pts/*` is stopped | Unit |
| TS-4 | SPEC.md TS4 | Whole test suite, including the existing TestTargetSelection / TestAncestorChainRule / TestLinkRule / TestCopies / TestModuleDocstring, with no existing test case changed | All pass | Integration |
| TS-5 | SPEC.md Implementation Approach (behaviour decided by the check); REQUIREMENTS.md FR1 business rules | A process between the anchor and the hook is absent from the snapshot (exited during the run); the anchor's start time matches | The anchor's descendant whose stdin is on `/dev/pts/*` is still stopped | Unit |
| TS-6 | SPEC.md Error Handling; workflow goal (expected behaviour) | The snapshot has no entry for the anchor PID; additionally, the TS-1 layout run through the hook's entry point | Nothing stopped, no pidfd opened; on both paths exit code 0 and nothing written to stdout / stderr | Unit |

## Code Quality Verification
- Format: none declared (`format_command` is empty). Static analysis: none
  declared.
- Copy identity (FR2): the two copies `em-workflow/scripts/codex-hook-tty-reaper.py`
  and `em-review/scripts/codex-hook-tty-reaper.py` are byte-identical
  (covered by TestCopies in TS-4).
- Diff inspection (NFR1, NFR4): the diff of both copies from
  `workflow.implement.base_commit` to the integration tip adds no import
  outside the standard library and no PID-addressed signal delivery.

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | All functional requirements are implemented and tested | Functional Requirements Coverage below: every FR / NFR has task0001 and at least one passing TS-n |
| SC-2 | All test scenarios pass | TS-1 to TS-6 pass in the suite run |
| SC-3 | AC1 through AC5 are met | AC1 → TS-1, TS-2; AC2 → TS-3, TS-4; AC3 → TS-4 (TestCopies); AC4 → TS-4 (TestModuleDocstring); AC5 → TS-4 plus the diff inspection above |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2, TS-3, TS-5, TS-6 |
| FR2 | task0001 | TS-4 (TestCopies) |
| FR3 | task0001 | TS-4 (TestModuleDocstring); manual Flow reading below |
| FR4 | task0001 | TS-1, TS-2 |
| NFR1 | task0001 | TS-4; diff inspection |
| NFR2 | task0001 | TS-6; TS-4 |
| NFR3 | task0001 | TS-3; TS-4 (existing tests unchanged) |
| NFR4 | task0001 | TS-4; TM-2 diff inspection |

## E2E Testing
Not applicable: the project has no E2E framework (`e2e_test_command` is
empty).

## Manual Testing (E2E Not Possible)
- [ ] Read the updated module docstring Flow: the anchor identity check is
  described at the point it runs (after the snapshot, before target
  selection), and the 10 steps still read as one coherent flow.

## Performance / Security Verification (if applicable)
- Performance: none (SPEC.md Performance Tests: none).
- TM-1: anchor start-time identity check before any target selection —
  checked by TS-1, TS-2 and TS-6 (no signal and no pidfd on a mismatch or a
  missing anchor entry) and by TS-3 and TS-5 (no false mismatch).
- TM-2: no PID-addressed signal delivery added — checked by inspecting the
  diff of both copies from `workflow.implement.base_commit` to the
  integration tip: no new PID-addressed signal call; every signal send stays
  on the existing pidfd path.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS-1 to TS-6) | 6 | 6 | 0 | 0 |
| Code quality (copy identity, diff inspection) | 2 | 1 | 0 | 1 |
| SPEC.md success criteria | 3 | 3 | 0 | 0 |
| Manual testing | 1 | 0 | 0 | 1 |
| Security (TM-1, TM-2) | 2 | 1 | 0 | 1 |
