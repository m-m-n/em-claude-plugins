# Verification Document: codex-guard-anon-fn-pipe

## Overview
**Feature**: codex-guard-anon-fn-pipe / **SPEC.md**: `feature-docs/codex-guard-anon-fn-pipe/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/codex-guard-anon-fn-pipe/IMPLEMENTATION.md`

## Build Verification
- Command: none (`project.components.main.build_command` is empty; the hook is a script run as is)
- Expected: not applicable

## Test Verification
- Command: `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests` (workflow.yaml `test_command`), run from the repository root
- Focused command: `python3 -m unittest tests.test_codex_hook_interactive_guard`
- Expected: exit code 0, no failures or errors
- Coverage target: not measured (standard-library unittest only, NFR3); every CASES entry runs against both hook copies

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS1 | `tests.test_codex_hook_interactive_guard.TestCasesTable.test_cases_run_against_both_copies` runs the CASES table, the three FR4 entries included, against both copies | Passes: both silent entries give exit 0 with empty standard output and standard error on each copy; the deny entry gives one deny object on each copy | Unit |
| TS2 | `tests.test_codex_hook_interactive_guard.TestCasesTable.test_cases_are_unique` | Passes: no added command duplicates an existing one | Unit |
| TS3 | `tests.test_codex_hook_interactive_guard.TestCopies.test_the_two_copies_are_byte_identical` | Passes: the two hook copies are byte-identical | Unit |
| TS4 | Diff of `tests/test_codex_hook_interactive_guard.py` against `ceefe2b5` | The diff consists only of added CASES lines: no existing entry removed or changed, no import added | Diff review |
| TS5 | Diff of `em-workflow/.claude-plugin/plugin.json`, `em-review/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` against the feature's implement base commit | No change to any version field | Diff review |

## Code Quality Verification
- Format: none (`format_command` is empty)
- Static analysis: none configured; `TestStaticConstraints` in the focused command checks that both hook copies stay within the standard library and touch no file, network connection or child process

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | Both copies give exit 0 and empty standard output and standard error for `zsh -c 'printf "print(1)\n" \| function () { python3; }'` | TS1 |
| AC2 | Both copies give a deny decision for `zsh -c 'printf "print(1)\n" \| function () { python3 -i; }'` | TS1 |
| AC3 | Both copies give exit 0 and empty standard output and standard error for `zsh -c 'function < /dev/null () { python3; }'` | TS1 |
| AC4 | CASES holds the three FR4 entries and the focused command passes, `test_cases_are_unique` and `test_cases_run_against_both_copies` included | TS1, TS2, focused command |
| AC5 | `TestCopies.test_the_two_copies_are_byte_identical` passes | TS3 |
| AC6 | Every CASES entry present at `ceefe2b5` remains unchanged | TS4 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS1 |
| FR2 | task0001 | TS1 |
| FR3 | task0001 | TS1 |
| FR4 | task0001 | TS1, TS2 |
| FR5 | task0001 | TS3 |
| NFR1 | task0001 | TS3 |
| NFR2 | task0001 | TS4 |
| NFR3 | task0001 | TS4 |
| NFR4 | task0001 | TS5 |

## Manual Testing (E2E Not Possible)
- [ ] TS4 diff review
- [ ] TS5 diff review

## Performance / Security Verification (if applicable)
- TM-1: the head's connection reaches the anonymous body alone and an explicit `-i` stays denied — checked by the focused command: every pre-existing CASES entry, the deny entries that bound the anonymous-body connection included, and the new piped `-i` deny entry pass on both copies. When the hook copies differ from the implement base commit, their diff is also read to confirm it changes only how the head's connection reaches the body.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS1-TS3) | 3 | 3 | 0 | 0 |
| Diff review (TS4, TS5) | 2 | 0 | 0 | 2 |
| Success criteria (AC1-AC6) | 6 | 5 | 0 | 1 |
| Security (TM-1) | 1 | 1 | 0 | 0 |
| Total | 12 | 9 | 0 | 3 |
