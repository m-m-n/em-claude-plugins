# Verification Document: codex-guard-anon-function

## Overview
**Feature**: codex-guard-anon-function / **SPEC.md**: `feature-docs/codex-guard-anon-function/SPEC.md` / **IMPLEMENTATION.md**: not produced (reduced tier; single task, so no file is declared by two tasks) / **THREAT-MODEL.md**: `feature-docs/codex-guard-anon-function/THREAT-MODEL.md`

All commands run from the repository root of the integration worktree. "Both copies" means `em-workflow/scripts/codex-hook-interactive-guard.py` and `em-review/scripts/codex-hook-interactive-guard.py`. "Fed to a copy" means the command string is given to that copy as `{"tool_input": {"command": ...}}` on standard input. "Base" means `workflow.implement.base_commit`.

## Build Verification
- Command: none (neither component, repo-tests nor plugin-invariants, declares a build command)
- Expected: not applicable

## Test Verification
- Command (repo-tests): `python3 -m unittest discover -s tests` — expected: exit code 0
- Command (plugin-invariants): `python3 em-workflow/scripts/check-plugin-invariants.py .` — expected: exit code 0
- Coverage target: not applicable (no coverage tool is configured); every FR / NFR maps to at least one scenario below

### Test Scenarios from SPEC.md
TS1 to TS6 are SPEC.md's own scenarios. TS7 to TS12 cover SPEC.md's edge cases and the NFRs that TS1 to TS6 do not exercise.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS1 | `zsh -c '! function () { python3 -i; }'` fed to both copies (CASES entry) | Each copy emits one deny JSON | Unit |
| TS2 | `zsh -c 'if true; then function () { python3 -i; }; fi'` fed to both copies (CASES entry) | Each copy emits deny | Unit |
| TS3 | `zsh -c 'function () { python3 -i; }'` fed to both copies (CASES entry) | Each copy emits deny | Unit |
| TS4 | `zsh -c "'function' () { python3 -i; }"` fed to both copies (CASES entry) | Each copy emits nothing (silent) | Unit |
| TS5 | `function function () { python3 -i; }` fed to both copies (CASES entry) | Each copy emits nothing (silent) | Unit |
| TS6 | `python3 -m unittest tests.test_codex_hook_interactive_guard` | Every test passes, including every pre-existing CASES entry, the byte-identity test of the two copies and the docstring wording tests | Unit |
| TS7 | `zsh -c '"function" () { python3 -i; }'` and `zsh -c '\function () { python3 -i; }'`, each fed to both copies | Each copy emits nothing (silent) for both commands | Integration |
| TS8 | `function () { python3 -i; }` (outer command line) and `bash -c 'function () { python3 -i; }'`, each fed to both copies | Each copy emits deny for both commands | Integration |
| TS9 | Read the module docstring's step 4, the `_Group` head description and the `_names_function` docstring | Each states that a lone `function` with neither quoting nor escaping, left after the reserved-word removal, is not a function name and the group after it is judged; the pinned phrases are still present (also enforced by TS6) | Inspection |
| TS10 | Diff of `tests/test_codex_hook_interactive_guard.py` between base and the integration branch | The only CASES change is the five added entries; no pre-existing entry is removed or altered | Inspection |
| TS11 | Diff of both copies between base and the integration branch | No new import outside the standard library; no self-call or call cycle; `_names_function` keeps its name and reads the words in one forward pass without modifying them | Inspection |
| TS12 | `git diff --stat` between base and the integration branch, limited to `em-workflow/.claude-plugin/plugin.json`, `em-review/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` | Empty output (none of the three files changed) | Automated |

## Code Quality Verification
- Format: none configured / Static analysis: none configured
- Byte identity of the two copies: covered by TS6

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | `zsh -c '! function () { python3 -i; }'` yields one deny JSON from both copies | TS1 |
| AC2 | The `then` form and the no-prefix form are denied by both copies | TS2, TS3 |
| AC3 | The single-quoted `'function'` form stays silent in both copies | TS4 |
| AC4 | `function function ()` stays silent in both copies | TS5 |
| AC5 | The five FR7 entries are in CASES and the guard suite passes | TS6, TS10 |
| SC-FR | All functional requirements are implemented and tested | Functional Requirements Coverage below |
| SC-TS | All test scenarios pass | TS1 to TS12 |
| SC-REVIEW | Code review is completed | Review phase record |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS1, TS2, TS3, TS8 |
| FR2 | task0001 | TS4, TS7 |
| FR3 | task0001 | TS4, TS7 |
| FR4 | task0001 | TS5 |
| FR5 | task0001 | TS9; pinned phrases by TS6 |
| FR6 | task0001 | TS6 (byte identity); TS1 to TS5 run against both copies |
| FR7 | task0001 | TS1, TS2, TS3, TS4, TS5 |
| NFR1 | task0001 | TS6, TS10 |
| NFR2 | task0001 | TS11 |
| NFR3 | task0001 | TS6 |
| NFR4 | task0001 | TS12 |

## Manual Testing (E2E Not Possible)
- [ ] TS9: docstring wording at the three locations
- [ ] TS10: pre-existing CASES entries preserved
- [ ] TS11: NFR2 implementation constraints preserved

## Performance / Security Verification (if applicable)
- NFR2: no recursion, standard library only, `_names_function` stays a single non-mutating forward pass — checked by TS11
- TM-1: a lone bare `function` left after the reserved-word removal is not a function name and the following groups are judged — checked by TS1, TS2, TS3 and TS8 (deny from both copies); TS4, TS5 and TS7 confirm that a quoted or escaped `function` and `function function ()` keep the definition reading

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test commands (repo-tests, plugin-invariants) | 2 | 2 | 0 | 0 |
| Test scenarios (TS1 to TS12) | 12 | 9 | 0 | 3 |
| Security (TM-1) | 1 | 1 | 0 | 0 |
| Total | 15 | 12 | 0 | 3 |
