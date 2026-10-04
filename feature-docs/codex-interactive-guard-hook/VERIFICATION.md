# Verification Document: codex-interactive-guard-hook

## Overview
**Feature**: codex-interactive-guard-hook / **SPEC.md**: `feature-docs/codex-interactive-guard-hook/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/codex-interactive-guard-hook/IMPLEMENTATION.md` / **THREAT-MODEL.md**: `feature-docs/codex-interactive-guard-hook/THREAT-MODEL.md`

Scenario IDs TS-1 to TS-8 correspond to SPEC.md TS1 to TS8. TS-9 to TS-12 are added by this plan.

## Build Verification
- Command: none. Both components (`repo-tests`, `plugin-invariants`) have an empty `build_command`.
- Expected: not applicable.

## Test Verification
- Command (repo-tests): `python3 -m unittest discover -s tests`, run from the repository root
- Command (hook only): `python3 -m unittest tests.test_codex_hook_interactive_guard`
- Expected: exit code 0, with no failures and no errors
- Coverage target: not measured; no coverage tool is configured for these components. Completeness is judged by the scenario table below and the requirement coverage table.

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | The hook receives a PreToolUse JSON (tool_name Bash) for each SPEC AC4 and AC5 command (task0001 AC-1, AC-2), and this is checked against both copies | `hookSpecificOutput.permissionDecision` is `deny` | Unit |
| TS-2 | The hook receives each SPEC AC6 command, with `ruby -i` in its in-place-edit form, plus `python3 -i` inside quotes, after a comment, and inside a heredoc body, and a second-level shell literal. Checked against both copies. | stdout is empty, stderr is empty, exit 0 | Unit |
| TS-3 | The hook receives each of the following: non-JSON stdin, a non-object JSON value, a missing `tool_input`, a missing `command`, a non-string `command`, an unclosed quote, an unterminated heredoc, `env -i python3` | stdout is empty, stderr is empty, exit 0 | Unit |
| TS-4 | Non-vacuity check on the CASES table | The table holds at least one `deny` case and one `silent` case | Unit |
| TS-5 | Byte comparison of `em-workflow/scripts/codex-hook-interactive-guard.py` and `em-review/scripts/codex-hook-interactive-guard.py` | The two files are byte-identical | Unit |
| TS-6 | A stub `codex` records the argv of em-workflow default (readonly, readwrite), em-workflow `--litellm MODEL` (readonly, readwrite) and em-review (readonly, readwrite) | Each argv contains a `-c` value setting `hooks.PreToolUse` (matcher `Bash`, command = Python 3 plus the absolute path of that plugin's hook) and `--dangerously-bypass-hook-trust`. `--ignore-user-config`, `--ignore-rules` and the existing `-c` overrides stay as they are today. `-p litellm -m MODEL` stays contiguous. There is exactly one launch per run. | Integration |
| TS-7 | Read the Step 4 section of both `codex-reviewer.md` files | Each contains a rule forbidding interactive-mode launches and naming `python3 -c` | Unit |
| TS-8 | Run the whole suite with `python3 -m unittest discover -s tests` | All existing and new tests pass, and existing modules are unmodified | Integration |
| TS-9 | Check the output of a denied command | Exactly one JSON object on stdout, with hookEventName `PreToolUse`, permissionDecision `deny`, and a Japanese reason that contains `python3 -c` and `python3 - <<EOF` and mentions a script file. Exit 0. | Unit |
| TS-10 | Run each wrapper from a copy of its `scripts/` directory placed under a path containing a space and a single quote | The recorded `-c` value parses as TOML, and its command resolves to exactly the copied hook path | Integration |
| TS-11 | Static inspection of the hook source | It imports only standard-library modules, imports no network or process-spawning module, and opens no file for writing | Unit |
| TS-12 | Verify-phase integrated check on the merged tree. For each wrapper path, record the argv with a stub `codex`, take the hook command from the `-c` value, and run it as Codex would: once with a PreToolUse JSON for `python3 -i`, once for `python3 -c 'print(1)'`. | The first prints the deny object. The second prints nothing. Both exit 0. | Integration |

## Code Quality Verification
- Format: none configured (`format_command` is empty for both components).
- Static analysis / invariants: `python3 em-workflow/scripts/check-plugin-invariants.py .` exits 0.
- Rule documentation: `.claude/rules/hook-tests.md` has a section for this hook that gives `python3 -m unittest tests.test_codex_hook_interactive_guard` and the `(期待する判定, ラベル, コマンド)` case format (task0001 AC-7).

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | All functional requirements are implemented and tested | The Functional Requirements Coverage table below has no empty row |
| SC-2 | All test scenarios pass | TS-1 to TS-12 pass |
| SC-3 | SPEC AC1 to AC9 are met | AC1–AC2: TS-6. AC3: TS-5. AC4–AC5: TS-1. AC6: TS-2. AC7: TS-3. AC8: TS-7. AC9: TS-6, TS-8. |
| SC-4 | `python3 -m unittest discover -s tests` passes in full | TS-8 |
| SC-5 | Documentation is complete | The hook-tests.md section is present (Code Quality Verification), and the reviewer guidance is present (TS-7) |
| SC-6 | Code review is completed | The review phase finishes with no residual critical or high findings |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0002 | TS-6, TS-10, TS-12 |
| FR2 | task0002 | TS-6, TS-12 |
| FR3 | task0002 | TS-6, TS-10, TS-12 |
| FR4 | task0002 | TS-6 |
| FR5 | task0001 | TS-5, TS-11 |
| FR6 | task0001 | TS-1, TS-2 |
| FR7 | task0001 | TS-1, TS-2 |
| FR8 | task0001 | TS-1, TS-2 |
| FR9 | task0001 | TS-1, TS-2 |
| FR10 | task0001 | TS-2 |
| FR11 | task0001 | TS-3 |
| FR12 | task0001 | TS-9 |
| FR13 | task0003 | TS-7 |
| FR14 | task0001, task0002 | TS-4, TS-5, TS-6 |
| NFR1 | task0001 | TS-11 |
| NFR2 | task0001 | TS-2, TS-3 |
| NFR3 | task0002, task0003 | TS-6, TS-8 |
| NFR4 | task0002 | TS-6, TS-8 |
| NFR5 | task0002 | TS-6 |

## E2E Testing
None. The project has no E2E framework (`e2e_test_command` is empty).

## Manual Testing (E2E Not Possible)
- [ ] M-1: On a real Codex 0.160.0, launch through each wrapper path that is available: em-workflow default, em-workflow `--litellm` (when a LiteLLM endpoint is configured), and em-review.
  - Asking Codex to run `python3 -i` is denied, the Japanese reason is shown, and no new python process remains afterwards.
  - Asking Codex to run `python3 -c 'print(1)'` runs normally.
  - No `PreToolUse Failed` message appears, which shows the hook is registered and starts.
  - This also confirms the hook configuration key names and command-execution form that task0002 recorded (SPEC A6).
- [ ] M-2: Read the deny reason and the new Step 4 guidance. Both read naturally, and both point to the same three alternatives: `python3 -c`, a script file, and `python3 - <<EOF`.

## Performance / Security Verification (if applicable)
- TM-1: the hook denies interactive-mode and no-source launches (FR6–FR9) — checked by TS-1 and TS-9.
- TM-2: the hook denies only positively identified launches and fails open on anything else — checked by TS-2 and TS-3.
- TM-3: the hook path is escaped for the command-execution layer and the TOML layer — checked by TS-10.
- TM-4: the bypass flag only appears alongside each launch's current config-isolation flags — checked by TS-6, with assertions on `--ignore-user-config` and `--ignore-rules` per launch path.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS-1 to TS-12) | 12 | 12 | 0 | 0 |
| Code quality (plugin invariants, rule section) | 2 | 1 | 0 | 1 |
| Security (TM-1 to TM-4) | 4 | 4 | 0 | 0 |
| Manual (M-1, M-2) | 2 | 0 | 0 | 2 |
| **Total** | 20 | 17 | 0 | 3 |
