# Verification Document: codex-guard-anon-fn-brace-close

## Overview
**Feature**: codex-guard-anon-fn-brace-close / **SPEC.md**: `feature-docs/codex-guard-anon-fn-brace-close/SPEC.md` / **IMPLEMENTATION.md**: not produced (reduced tier; single task, no file shared between tasks) / **THREAT-MODEL.md**: `feature-docs/codex-guard-anon-fn-brace-close/THREAT-MODEL.md`

## Build Verification
- Command: none (`project.components.main.build_command` is empty; the changed files are Python scripts run directly)
- Expected: not applicable

## Test Verification
- Command: `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests`
- Focused command: `python3 -m unittest tests.test_codex_hook_interactive_guard`
- Coverage target: not measured (no coverage tool configured); every scenario below must be backed by a passing test or by the stated check
- Every verdict scenario (deny / silent) is checked against both copies: `em-workflow/scripts/codex-hook-interactive-guard.py` and `em-review/scripts/codex-hook-interactive-guard.py`

### Test Scenarios from SPEC.md
Scenario numbers 1 to 14 match SPEC.md's test scenario numbers (SPEC.md writes them without the hyphen). TS-15 and TS-16 are SPEC.md's regression commands; TS-17 and TS-18 check FR6 and NFR4.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | `zsh -c 'python3 -i; function { : }'` | deny; present in `CASES` as deny | Unit |
| TS-2 | `zsh -c 'function { : }; python3 -i'` | deny; present in `CASES` as deny | Unit |
| TS-3 | `zsh -c 'function { python3 -i }'` | deny; present in `CASES` as deny | Unit |
| TS-4 | `zsh -c 'function () { python3 -i }'` | deny | Unit |
| TS-5 | `zsh -c '() { python3 -i }'` | deny | Unit |
| TS-6 | `zsh -c 'function { python3 -i } arg'` | deny | Unit |
| TS-7 | `zsh -c 'function { { : } }; python3 -i'` | deny | Unit |
| TS-8 | `zsh -c 'function { ( { python3 -i } ) }'` | deny | Unit |
| TS-9 | `zsh -c 'echo x \| function { python3 }'` | silent | Unit |
| TS-10 | `zsh -c '< /dev/null function { python3 }'` | silent | Unit |
| TS-11 | `zsh -c 'echo x \| function { { python3 } }'` | silent | Unit |
| TS-12 | `zsh -c "echo x \| function { echo '}'; python3 }"` | silent (the quoted brace does not close the body) | Unit |
| TS-13 | Existing `CASES` entry: top-level `{ python3 }` | silent, unchanged | Unit |
| TS-14 | `function {`, then N repetitions of ` { :`, then N repetitions of ` }` | finishes within the time limit the existing deep-input tests use | Unit (performance) |
| TS-15 | `python3 -m unittest tests.test_codex_hook_interactive_guard` | passes, including TestCopies, TestGuardDocumentation, TestMalformedAndDeepInput, TestNoRecursion, TestStaticConstraints and every pre-existing `CASES` entry | Unit |
| TS-16 | `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests` | exit code 0 | Integration |
| TS-17 | Step 4 of the module docstring, both copies | states the FR1, FR2 and FR5 closing rules | Manual (review) |
| TS-18 | Files changed by the feature, compared with the feature's base | no `.claude-plugin/plugin.json` of any plugin and no `.claude-plugin/marketplace.json` | Integration (diff check) |

## Code Quality Verification
- Format: none configured (`format_command` is empty)
- Static analysis: no linter configured; TestStaticConstraints (part of TS-15) covers NFR2's static constraints
- Copy identity: `cmp em-workflow/scripts/codex-hook-interactive-guard.py em-review/scripts/codex-hook-interactive-guard.py` exits 0 (also asserted by TestCopies in TS-15)

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | Both copies deny `zsh -c 'python3 -i; function { : }'` | TS-1 |
| AC2 | Both copies deny `zsh -c 'function { : }; python3 -i'` | TS-2 |
| AC3 | Both copies deny `zsh -c 'function { python3 -i }'` | TS-3 (TS-4, TS-5, TS-6 for the other head forms and arguments) |
| AC4 | `zsh -c 'function { { : } }; python3 -i'` is denied | TS-7 (TS-8 for an intervening `(` group) |
| AC5 | Commands finalized inside an anonymous-function body, and inside nested groups in it, inherit the body's connections | TS-9, TS-10, TS-11 |
| AC6 | A quoted `}` does not close a group | TS-12 |
| AC7 | Every existing `CASES` entry passes, including the top-level `{ python3 }` silent case | TS-13, TS-15 |
| AC8 | The focused test module passes with the named test classes | TS-15, TS-14 |
| AC9 | The full suite command passes | TS-16 |
| Done-1 | TS-1 to TS-3 are deny entries in `CASES` | Inspect `tests/test_codex_hook_interactive_guard.py` |
| Done-2 | The two copies are byte-identical | Copy identity check above; TestCopies (TS-15) |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2, TS-3, TS-4, TS-5, TS-6 |
| FR2 | task0001 | TS-7, TS-8, TS-11 |
| FR3 | task0001 | TS-3, TS-6, TS-9, TS-10, TS-11 |
| FR4 | task0001 | TS-12 |
| FR5 | task0001 | TS-13, TS-15 |
| FR6 | task0001 | TS-15, TS-17 |
| FR7 | task0001 | TS-1, TS-2, TS-3, TS-15 |
| FR8 | task0001 | TS-1, TS-2, TS-3 |
| NFR1 | task0001 | TS-14, TS-15 |
| NFR2 | task0001 | TS-15 |
| NFR3 | task0001 | TS-9, TS-10, TS-11, TS-12, TS-13, TS-16 |
| NFR4 | task0001 | TS-18 |

## Manual Testing (E2E Not Possible)
- [ ] Bug reproduction, per copy: feed a hook payload whose `tool_input.command` is each of the TS-1 to TS-3 commands to the script's standard input; each produces a deny output (before the fix there was no output). The semicolon form `zsh -c 'python3 -i; function { :; }'` still produces a deny output.
- [ ] TS-17: read step 4 of the module docstring in both copies and confirm it states the FR1, FR2 and FR5 closing rules.

## Performance / Security Verification
- NFR1: TS-14 finishes within the time limit the existing deep-input tests use; TestNoRecursion and TestMalformedAndDeepInput pass (TS-15).
- TM-1: a standalone bare `}` closes an anonymous-function body, or a `{` group inside one, even with words pending, after finalizing the pending command as a `;` would; a quoted, escaped, expanded, in-word or redirect-target `}` never closes — checked by TS-1 to TS-8 (deny in both copies), TS-12 (silent) and task0001's semicolon-equivalence test (AC-3).
- TM-2: the "within an anonymous-function body" check at each `}` reads a value fixed when the group opened, with no walk over enclosing groups — checked by TS-14 (timing) and by reviewing the change for any walk over enclosing groups.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios (TS-1 to TS-18) | 18 | 17 | 0 | 1 |
| Code quality (copy identity) | 1 | 1 | 0 | 0 |
| Manual testing (bug reproduction; TS-17 counted above) | 1 | 0 | 0 | 1 |
| Performance / Security (NFR1, TM-1, TM-2) | 3 | 3 | 0 | 0 |
| Total | 23 | 21 | 0 | 2 |
