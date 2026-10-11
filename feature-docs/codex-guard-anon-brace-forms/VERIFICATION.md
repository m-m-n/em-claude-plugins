# Verification Document: codex-guard-anon-brace-forms

## Overview
**Feature**: codex-guard-anon-brace-forms / **SPEC.md**: `feature-docs/codex-guard-anon-brace-forms/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/codex-guard-anon-brace-forms/IMPLEMENTATION.md`

All commands run at the repository root of the integration worktree.

## Build Verification
- Command: none. Both components (`repo-tests`, `plugin-invariants`) declare an empty build command; the hook runs as a Python script.
- Expected: not applicable

## Test Verification
- Command (`repo-tests`): `python3 -m unittest discover -s tests`
- Command (`plugin-invariants`): `python3 em-workflow/scripts/check-plugin-invariants.py .`
- Focused command (NFR4): `python3 -m unittest tests.test_codex_hook_interactive_guard`
- Expected: exit code 0, every test passes
- Coverage target: not measured (the suite is standard-library only, with no coverage tool). Coverage is by scenario: every command below is a cases-table entry or a named test, run against both hook copies.

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Parenless anonymous function `zsh -c 'function { python3 -i; }'`, both copies (SPEC AC1) | Exactly one deny object on stdout, exit 0, empty stderr | Unit (cases table, subprocess) |
| TS-2 | Arguments after the closing brace `zsh -c 'function () { python3 -i; } arg'`, both copies (SPEC AC1) | Exactly one deny object | Unit (cases table, subprocess) |
| TS-3 | `zsh -c 'function { python3 -i; } arg'`, `zsh -c '! function { python3 -i; }'`, `zsh -c '() { python3 -i; } arg'`, `zsh -c 'function ()\n{ python3 -i; } arg'` (`\n` is a newline), both copies (SPEC AC2) | Deny for each | Unit (cases table, subprocess) |
| TS-4 | Right side of a pipe: `echo x \| function { python3; }`, `echo x \| function () { python3; }`, `echo x \| () { python3; }`, `echo x \| function { { python3; }; }` inside `zsh -c '...'`; and `zsh -c 'echo x \| function { python3 -i; }'`, `zsh -c 'echo x \| function { cat; }; python3'`, both copies (SPEC AC3) | The first four silent; the last two deny | Unit (cases table, subprocess) |
| TS-5 | Arguments and preserved readings: `zsh -c 'function f { python3 -i; }'`, `zsh -c "'function' { python3 -i; }"`, `zsh -c 'function { echo hi; } python3'`, `zsh -c 'function () { python3; } arg < f'`, `zsh -c '{ python3 -i; } arg'`, `zsh -c 'f() { python3 -i; } arg'`, `zsh -c 'function f () { python3 -i; } arg'` silent; `zsh -c 'function { :; } arg; python3 -i'` deny, both copies (SPEC AC4) | As stated per command | Unit (cases table, subprocess) |
| TS-6 | Linearity: the existing reserved-word run followed by `function { python3 -i; }`, and the run, one non-reserved word and as many `function {` word pairs as the run has words, both copies (NFR3) | Each answered within the existing timeout test's limit, exit 0, empty stderr; the first one denied | Unit (timeout test, subprocess) |
| TS-7 | Whole focused module `python3 -m unittest tests.test_codex_hook_interactive_guard` (SPEC AC5) | All tests pass | Unit |
| TS-8 | Cases table holds every FR7 command with its FR7 verdict and the two extra commands of TS-5; no entry present at the base commit is removed or changed (FR7, NFR1) | All present; the diff of the cases table against the base commit only adds entries | Unit (table tests) + diff check |
| TS-9 | Documentation: the module docstring step 4, the `_Group` docstring and the parenless-form method's docstring state the three anonymous forms, the argument reading, the stdin redirect after the arguments and the pipe connection to the body; the old "delimit a group only as a standalone word at command position" phrase is gone; existing markers kept (FR5) | Documentation tests pass for both copies | Unit (AST / docstring tests) |
| TS-10 | The two hook copies are byte-identical (FR6) | Identity test passes | Unit |
| TS-11 | No recursion or function cycle, standard library only, `_names_function` still a method of `_Parser` (NFR2) | No-recursion, static-constraint and documentation tests pass for both copies | Unit (AST tests) |
| TS-12 | No plugin version edit: the change set against the implement base commit contains no `plugin.json` and no `marketplace.json` (NFR5) | No such path in the changed-file list | Diff check |

## Code Quality Verification
- Format: none configured / Static analysis: none configured. The test module's static-constraint and no-recursion tests stand in for both copies (TS-11).

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | `function { python3 -i; }` and `function () { python3 -i; } arg` under `zsh -c` give one deny object on both copies | TS-1, TS-2 |
| AC2 | The four further anonymous forms deny on both copies | TS-3 |
| AC3 | Pipe right side: four silent, two deny | TS-4 |
| AC4 | Named, quoted, argument and non-anonymous readings stay silent | TS-5 |
| AC5 | FR7 cases present; the focused module passes, including byte-identity, documentation and linearity tests | TS-6, TS-7, TS-8, TS-9, TS-10 |
| SC-1 | All functional requirements implemented and tested | TS-1 to TS-10 pass |
| SC-2 | All test scenarios pass | Both test commands above exit 0 |
| SC-3 | Performance goal: the parenless-form decision stays linear | TS-6 |
| SC-4 | Copies byte-identical | TS-10 |
| SC-5 | No version change | TS-12 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-3, TS-5 |
| FR2 | task0001 | TS-2, TS-3, TS-5 |
| FR3 | task0001 | TS-4 |
| FR4 | task0001 | TS-5 |
| FR5 | task0001 | TS-9 |
| FR6 | task0001 | TS-10 |
| FR7 | task0001 | TS-8 |
| NFR1 | task0001 | TS-7, TS-8 |
| NFR2 | task0001 | TS-11 |
| NFR3 | task0001 | TS-6 |
| NFR4 | task0001 | TS-7 |
| NFR5 | task0001 | TS-12 |

## Manual Testing (E2E Not Possible)
- [ ] Bug-report reproduction: pass `{"tool_input": {"command": "zsh -c 'function { python3 -i; }'"}}` and the same with `zsh -c 'function () { python3 -i; } arg'` to each hook copy on stdin; each prints one deny object (before the fix: no output).
- [ ] Read step 4 of the module docstring end to end in one copy: no sentence contradicts the new brace rule, the argument reading or the pipe connection to the body.

## Performance / Security Verification
- NFR3: the parenless-form decision stays linear — TS-6, within the existing timeout test's limit.
- TM-1: the body of every anonymous-function form is judged and the words after its closing brace are arguments — TS-1, TS-2 and TS-3 deny on both copies.
- TM-2: the argument span ends at the next separator and applies to anonymous bodies only; the pipe connection reaches the body and nothing after it; an explicit `-i` stays denied under it — TS-4 (`echo x | function { cat; }; python3` and `echo x | function { python3 -i; }` deny) and TS-5 (`function { :; } arg; python3 -i` deny, non-anonymous readings silent).
- TM-3: the parenless-form decision takes constant time per `{` and nothing recurses — TS-6 (the input with many `function {` pairs after a long reserved run answers in time) and TS-11.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios | 12 | 12 | 0 | 0 |
| SPEC success criteria | 10 | 10 | 0 | 0 |
| Requirements coverage | 12 | 12 | 0 | 0 |
| Performance / security (NFR3, TM-1, TM-2, TM-3) | 4 | 4 | 0 | 0 |
| Manual | 2 | 0 | 0 | 2 |
