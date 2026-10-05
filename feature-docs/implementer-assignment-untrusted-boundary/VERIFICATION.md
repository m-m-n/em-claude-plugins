# Verification Document: implementer-assignment-untrusted-boundary

## Overview
**Feature**: implementer-assignment-untrusted-boundary / **SPEC.md**: `feature-docs/implementer-assignment-untrusted-boundary/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/implementer-assignment-untrusted-boundary/IMPLEMENTATION.md`

## Build Verification
- Command: none (both components, `repo-tests` and `plugin-invariants`, declare an empty build command)
- Expected: not applicable

## Test Verification
- Command (repo-tests): `python3 -m unittest discover -s tests`
- Command (plugin-invariants): `python3 em-workflow/scripts/check-plugin-invariants.py .`
- Expected: both exit with code 0
- Coverage target: not measured (standard-library `unittest` only, no coverage tooling; NFR1)

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS1 | Document test reads the I.2.a payload block of `em-workflow/references/implement-phase.md` and its adjacent text | The `Untrusted data` label exists; the five data lines follow it; every trusted field (`task_id` to `tests_yaml_path`) precedes it; the one-line JSON rendering instruction and the boundary text are present; no AC-1 ordering anchor phrase appears in the new payload text (NFR7) | Unit |
| TS2 | `queue_launch_guard.py` runs as a subprocess on the new-format prompt and on variants carrying forged identifiers (JSON-escaped; raw line after the genuine identity lines) | A `launched` event is appended for the genuine `task_id`; no event is appended for the forged id | Integration |
| TS3 | `queue_agent_index.py` runs on the same prompts | The index entry carries the genuine `task_id` and `worktree_path` | Integration |
| TS4 | `queue_failure_net.py` runs on the same prompts | `failed` events are appended only for the genuine task | Integration |
| TS5 | Document test reads `em-workflow/agents/implementer.md` | It names the `Untrusted data` section, the three fields with their permitted uses, the JSON decode step, and the do-not-follow / record-in-notes rule; the Inputs section reflects the section; no line matches `^# Task assignment\s*$` | Unit |
| TS6 | Document test reads `em-workflow/skills/worktree-task-workflow/SKILL.md` | The Untrusted input section excludes the data-section values from the instruction sources; the Command execution gate section refers to the decoded value under the existing verbatim rule | Unit |
| TS7 | Run `python3 -m unittest discover -s tests` and `python3 em-workflow/scripts/check-plugin-invariants.py .` | Both pass, including the existing launch-order, worker-contract-docs and queue-hook test modules | Integration |

## Code Quality Verification
- Format: none declared. Static analysis: none declared.
- Diff-scope checks over the integrated diff (`base_commit` to the integration branch tip):
  - DS1 (NFR2, NFR5): every changed path is in the union of the tasks' `files` in workflow.yaml, `feature-docs/implementer-assignment-untrusted-boundary/**` or `test-docs/implementer-assignment-untrusted-boundary/**`. In particular no `.claude-plugin/plugin.json`, no `.claude-plugin/marketplace.json`, no `worker-envelope.md`, no `queue_launch_guard.py`, `queue_agent_index.py`, `queue_failure_net.py` or `bash_guard.py`, and no approval-store code appears in the diff.
  - DS2 (NFR4): no existing file under `tests/` is modified; only new modules are added.
  - DS3 (NFR1): every new test module imports only Python standard-library modules or existing modules under `tests/`.

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | Labelled untrusted-data section after all trusted fields, with boundary text (FR1) | TS1 |
| AC2 | One-line JSON rendering with newlines and control characters escaped (FR2) | TS1 |
| AC3 | Each queue hook extracts the genuine identity, with and without forged identifiers (FR3) | TS2, TS3, TS4 |
| AC4 | `implementer.md` states the data-not-instructions rule (FR4) | TS5 |
| AC5 | The skill excludes data-section values from instruction sources and refers to the decoded value in the command gate (FR5) | TS6 |
| AC6 | check-plugin-invariants and the full unittest suite pass (NFR3, NFR4) | TS7 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS1 |
| FR2 | task0001 | TS1 |
| FR3 | task0001, task0004 | TS2, TS3, TS4 |
| FR4 | task0002 | TS5 |
| FR5 | task0003 | TS6 |
| FR6 | task0001, task0002, task0003, task0004 | TS1, TS2, TS3, TS4, TS5, TS6 |
| NFR1 | task0001, task0002, task0003, task0004 | DS3 |
| NFR2 | none | DS1 |
| NFR3 | task0001, task0002, task0003 | TS5, TS7 |
| NFR4 | task0001, task0002, task0003, task0004 | TS7, DS2 |
| NFR5 | task0002, task0003, task0004 | DS1 |
| NFR6 | task0002, task0003 | TS6, manual review MR2 |
| NFR7 | task0001 | TS1, TS7 |

## Manual Testing (E2E Not Possible)
- [ ] MR1 (FR1): Read the payload block and its adjacent text in `em-workflow/references/implement-phase.md`; the label line and the boundary text plainly say that the section's values are workflow.yaml data and not instructions.
- [ ] MR2 (NFR6): Read the text added to `em-workflow/agents/implementer.md` and `em-workflow/skills/worktree-task-workflow/SKILL.md`; it makes no raw byte-equality claim beyond the existing verbatim rule.

## Performance / Security Verification (if applicable)
- Performance: not applicable.
- TM-1: labelled `Untrusted data` section after every trusted field, with boundary text — checked by TS1 (label position against every trusted field line and every data line; boundary text present).
- TM-2: one JSON literal per line with newlines and control characters escaped — checked by TS1 (rendering instruction present).
- TM-3: implementer data-not-instructions rule with permitted uses and notes reporting — checked by TS5.
- TM-4: instruction source limited to trusted fields and structure; decoded value run under the existing verbatim rule — checked by TS6.
- TM-5: identity lines before the data section; each hook takes the genuine identity when forged identifiers are present — checked by TS2, TS3, TS4.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios | 7 | 7 | 0 | 0 |
| Success criteria | 6 | 6 | 0 | 0 |
| Diff-scope checks | 3 | 2 | 0 | 1 |
| Manual review | 2 | 0 | 0 | 2 |
| Security (TM-n) | 5 | 5 | 0 | 0 |
| Total | 23 | 20 | 0 | 3 |
