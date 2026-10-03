# Verification Document: destructive-guard-herestring-subst-only

## Overview
- **Feature**: destructive-guard-herestring-subst-only
- **SPEC.md**: `feature-docs/destructive-guard-herestring-subst-only/SPEC.md`
- **IMPLEMENTATION.md**: not written (reduced tier, single task)
- **THREAT-MODEL.md**: `feature-docs/destructive-guard-herestring-subst-only/THREAT-MODEL.md`

## Build Verification
- Command: none. Every component in workflow.yaml has an empty build command; the Python scripts run directly.
- Expected: not applicable.

## Test Verification
- hooks: `python3 em-workflow/hooks/tests/run-destructive-guard.py`. Expected: exit 0, and the final line reports every case passed.
- repo-tests: `python3 -m unittest discover -s tests`. Expected: exit 0.
- plugin-invariants: `python3 em-workflow/scripts/check-plugin-invariants.py .`. Expected: exit 0.
- Coverage target: not measured. The hook is verified by its expectation suite, which is case-based; no coverage tooling is configured.

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | The expectation suite passes `bash <<< $(echo hi); rm -rf /var/b` to the hook as a PreToolUse Bash input. | The hook exits 0, and the decision is `deny`. | Unit (case suite) |
| TS-2 | The expectation suite passes ``sh <<< `x`; rm -rf /var/b`` to the hook as a PreToolUse Bash input. | The hook exits 0, and the decision is `deny`. | Unit (case suite) |
| TS-3 | Run the full expectation suite. | Every case passes. This includes the existing here-string cases `bash <<<$(true) 'rm -rf /home/sakura/valuable'` (deny) and `bash <<<"$(cat script.sh)" 'rm -rf /home/sakura/valuable'` (allow). No existing case is removed, and no existing expected verdict changes. | Integration (case suite) |
| TS-4 | Write the base revision's `em-workflow/hooks/destructive-guard.py` (the implement base commit) to a scratch file. Run the expectation suite with that file as the runner's path argument; the case file is the feature's updated one. | Exactly the TS-1 and TS-2 cases report FAIL with got `(exit 1)`, and the runner exits non-zero. This shows the new cases detect the defect on unfixed code. | Regression detection |
| TS-5 | Inspect the feature's diff against the base revision. | Neither `em-workflow/.claude-plugin/plugin.json` nor `.claude-plugin/marketplace.json` is modified. | Inspection |
| TS-6 | Inspect the diff to `em-workflow/hooks/destructive-guard.py` against the base revision. | Only the here-string branch's condition right after the payload-index helper call changes. The helper's body, the `-c` branch and the `eval` branch are unchanged. | Inspection |
| TS-7 | Run `python3 -m unittest tests.test_destructive_guard_command_substitution`, then the repo-tests command `python3 -m unittest discover -s tests`. | Both exit 0. `TestCaseTableDiscipline.test_runner_reports_every_case_passing` passes without `subprocess.TimeoutExpired`. Its runner invocation has a finite timeout of at least 1 second per case in `em-workflow/hooks/tests/destructive-guard-cases.json`, and a test in the same module asserts that bound against the current case file. (VF-1) | Integration (repo test) |

Edge case (FR1): the statement `bash <<< $(echo hi)` has a single-element word list. Its first statement takes the here-string target fallback instead of reading past the end of the list. TS-1 covers this.

## Code Quality Verification
- Format: none configured (empty `format_command` for every component).
- Static analysis: none configured.

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | FR1-FR3 are implemented and tested. | TS-1, TS-2 and TS-4 pass, and the Functional Requirements Coverage table below has a task and a test for each. |
| SC-2 | TS-1 to TS-4 pass. | Run the hooks suite (TS-1 to TS-3) and the base-copy run (TS-4). |
| SC-3 | SPEC AC-1 to AC-4 are satisfied. | AC-1: TS-1. AC-2: TS-2. AC-3: TS-1, TS-2, TS-3. AC-4: TS-3. |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2 |
| FR2 | task0001 | TS-1, TS-2 |
| FR3 | task0001, task0002 | TS-1, TS-2 (cases present and passing), TS-4 (cases fail on unfixed code), TS-7 (the repo test that runs the whole suite finishes within its case-count-derived timeout) |
| NFR1 | task0001 | TS-3 (existing cases unchanged), TS-6 (diff scope) |
| NFR2 | task0001 | TS-5 |

## Manual Testing (E2E Not Possible)
- [ ] TS-5: the feature's diff leaves `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` unmodified.
- [ ] TS-6: the diff to `em-workflow/hooks/destructive-guard.py` is limited to the here-string branch's condition after the payload-index helper call.

## Performance / Security Verification (if applicable)
- TM-1: the here-string branch reads the candidate body word only when its index lies inside the word list; otherwise it takes the existing here-string target fallback. Checked by TS-1 and TS-2, where the hook exits 0 and denies the later `rm -rf /var/b`. TS-4 confirms the same inputs ended with `(exit 1)` before the fix.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios (TS-1 to TS-7) | 7 | 5 | 0 | 2 |
| Component test commands (hooks / repo-tests / plugin-invariants) | 3 | 3 | 0 | 0 |
| Security (TM-1) | 1 | 1 | 0 | 0 |
| Total | 11 | 9 | 0 | 2 |
