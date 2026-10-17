# Verification Document: codex-guard-brace-anon-arg-rescue

## Overview
**Feature**: codex-guard-brace-anon-arg-rescue / **SPEC.md**: `feature-docs/codex-guard-brace-anon-arg-rescue/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/codex-guard-brace-anon-arg-rescue/IMPLEMENTATION.md`

## Build Verification
- Command: none (`project.components.main.build_command` is empty; the guard is a Python script with no build step)
- Expected: not applicable

## Test Verification
- Command (project, from workflow.yaml): `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests`
- Command (guard-specific, from the project rule for codex-hook-interactive-guard): `python3 -m unittest tests.test_codex_hook_interactive_guard`
- Expected: exit code 0 for both
- Coverage target: no coverage tool is configured for the project; coverage is judged by every scenario below passing against both guard copies

### Test Scenarios from SPEC.md
Each command is a CASES entry run against both copies (`em-workflow/scripts/codex-hook-interactive-guard.py` and `em-review/scripts/codex-hook-interactive-guard.py`); `\n` stands for a newline. TS27 is added by this document for NFR4 and does not appear in SPEC.md.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS1 | Reproduction 1: `zsh -c 'setopt nobadpattern; { function { :; } foo(a; python3 -i; }'` | deny | Unit (CASES) |
| TS2 | Reproduction 2: `zsh -c 'setopt nobadpattern; function { function { :; } foo(a; python3 -i; }'` | deny | Unit (CASES) |
| TS3 | Lone `&` as the separator: `zsh -c 'setopt nobadpattern; { function { :; } foo(a & python3 -i; }'` | deny | Unit (CASES) |
| TS4 | A `)` in a comment does not block the rescue: `zsh -c 'setopt nobadpattern; { function { :; } foo(a; python3 -i; } #)'` | deny | Unit (CASES) |
| TS5 | Launch with no program argument: `zsh -c 'setopt nobadpattern; { function { :; } foo(a; python3; }'` | deny | Unit (CASES) |
| TS6 | Input redirect on the closed group reaches the command after the rescue: `zsh -c 'setopt nobadpattern; { function { :; } foo(a; python3; } < /dev/null'` | silent | Unit (CASES) |
| TS7 | Pipe into the closed group reaches the command after the rescue: `zsh -c 'setopt nobadpattern; echo x \| { function { :; } foo(a; python3; }'` | silent | Unit (CASES) |
| TS8 | Nested provisional groups rescued from the inside: `zsh -c 'setopt nobadpattern; { function { :; } foo(function { :; } bar(a; python3 -i; }'` | deny | Unit (CASES) |
| TS9 | A nested `{` group closes normally inside the provisional group: `zsh -c 'setopt nobadpattern; { function { :; } foo(a; { python3 -i; }; }'` | deny | Unit (CASES) |
| TS10 | `}` with pending words, base is in_anon, words finalized then closed: `zsh -c 'setopt nobadpattern; function { function { :; } foo(a; python3 -i }'` | deny | Unit (CASES) |
| TS11 | `}` with pending words in a non-anonymous `{` group stays a word: `zsh -c 'setopt nobadpattern; { function { :; } foo(a; echo }'` | silent | Unit (CASES) |
| TS12 | After a closed anonymous body the words are arguments; the launch after the separator is judged: `zsh -c 'setopt nobadpattern; function { function { :; } foo(a; :; } arg; python3 -i'` | deny | Unit (CASES) |
| TS13 | A word after a closed plain brace group is undecidable: `zsh -c 'setopt nobadpattern; { function { :; } foo(a; :; } arg'` | silent | Unit (CASES) |
| TS14 | Function-definition body is skipped: `zsh -c 'setopt nobadpattern; f() { function { :; } foo(a; python3 -i; }'` | silent | Unit (CASES) |
| TS15 | Launch after a function-definition body is judged: `zsh -c 'setopt nobadpattern; f() { function { :; } foo(a; :; }; python3 -i'` | deny | Unit (CASES) |
| TS16 | First separator is a newline: `zsh -c 'setopt nobadpattern; { function { :; } foo(a\npython3 -i; }'` | silent | Unit (CASES) |
| TS17 | First separator is `&&`: `zsh -c 'setopt nobadpattern; { function { :; } foo(a && python3 -i; }'` | silent | Unit (CASES) |
| TS18 | A quoted `}` does not close: `zsh -c 'setopt nobadpattern; { function { :; } foo(a; python3 -i; "}"'` | silent | Unit (CASES) |
| TS19 | A `}` joined to other characters does not close: `zsh -c 'setopt nobadpattern; { function { :; } foo(a; python3 -i; }x'` | silent | Unit (CASES) |
| TS20 | A `}` as a redirect target does not close: `zsh -c 'setopt nobadpattern; { function { :; } foo(a; python3 -i; echo > }'` | silent | Unit (CASES) |
| TS21 | Subshell form is out of scope and unchanged: `zsh -c 'setopt nobadpattern; ( function { :; } foo(a; python3 -i; )'` | silent | Unit (CASES) |
| TS22 | Deep unrescuable chain followed by many `}`: an opening `{ function { :; } x(a && `, then D repetitions of `function { :; } x(`, then M repetitions of `; }` | Both copies return within TestMalformedAndDeepInput's TIMEOUT, with no output | Performance (unit) |
| TS23 | Every pre-existing CASES verdict is unchanged (case 604: label reworded to the skipped meaning, verdict silent); both test commands above pass | All tests pass | Integration (full suite) |
| TS24 | The two copies are byte-identical | TestCopies passes | Unit |
| TS25 | The new marker sentence (a `}` after a rescued separator closes the enclosing `{` group) is in the module docstring and the `_Parser` docstring of both copies | TestGuardDocumentation passes | Unit |
| TS26 | No recursion; standard library only; no file, network or subprocess access | TestNoRecursion and TestStaticConstraints pass | Unit |
| TS27 | Plugin version fields are untouched: the diff from the feature's base commit modifies none of `em-workflow/.claude-plugin/plugin.json`, `em-review/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` | Empty diff for those three paths | Static (diff check) |

## Code Quality Verification
- Format: none configured (`project.components.main.format_command` is empty)
- Static analysis: none configured; the structural constraints are covered by TestCopies, TestNoRecursion and TestStaticConstraints (TS24, TS26)

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | Reproduction 1 returns deny in both copies | TS1 |
| AC2 | Reproduction 2 returns deny in both copies | TS2 |
| AC3 | The function-definition form is silent; the launch after the body is denied | TS14, TS15 |
| AC4 | Unrescuable forms stay silent (newline and `&&` separators, existing case 601, quoted / word-part / redirect-target `}`, subshell form) | TS16 to TS21, existing case 601 within TS23 |
| AC5 | Every existing CASES verdict is unchanged (case 604 label only); both test commands pass | TS23 |
| AC6 | Deep chains followed by many `}` answer within TIMEOUT in both copies | TS22 |
| AC7 | The two copies are byte-identical | TS24 |
| AC8 | The new marker sentence is in the module docstring and the `_Parser` docstring of both copies and is checked by TestGuardDocumentation | TS25 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS1, TS2, TS3, TS4, TS5, TS8, TS9, TS10, TS11, TS18, TS19, TS20 |
| FR2 | task0001 | TS6, TS7, TS12, TS13, TS14, TS15 |
| FR3 | task0001 | TS16, TS17, TS18, TS19, TS20, TS21 |
| FR4 | task0001 | TS1, TS2, TS14, TS15 |
| FR5 | task0001 | TS25 |
| FR6 | task0001 | TS1 to TS23 |
| FR7 | task0001 | TS21 |
| NFR1 | task0001 | TS22, TS26 |
| NFR2 | task0001 | TS24 |
| NFR3 | task0001 | TS26 |
| NFR4 | task0001 | TS27 |

## Manual Testing (E2E Not Possible)
- [ ] zsh reachability: with zsh installed, `zsh -f -c 'setopt nobadpattern; { function { :; } foo(a; printf REACHED; }'` prints REACHED, and the same holds for the anonymous-body form of reproduction 2 with `printf REACHED` in place of `python3 -i`. This confirms the denied forms are ones zsh actually executes.

## Performance / Security Verification (if applicable)
- NFR1: TS22 returns within TestMalformedAndDeepInput's TIMEOUT for both copies; TS26 (TestNoRecursion) passes.
- NFR3: TS26 (TestStaticConstraints) passes.
- TM-1: rescue at a lone `}` and close of the enclosing `{` group, in both copies — checked by TS1 to TS5, TS8 to TS10 (deny) and TS6, TS7, TS12 to TS15 (reading after the close).
- TM-2: no close where zsh does not close, and no state change on a failed check — checked by TS11, TS16 to TS21 (silent) and TS23 (every existing verdict unchanged).
- TM-3: amortized constant-time decision per `}`, no recursion — checked by TS22 and TS26.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Unit (CASES, TS1 to TS21) | 21 | 21 | 0 | 0 |
| Performance (TS22) | 1 | 1 | 0 | 0 |
| Integration (TS23) | 1 | 1 | 0 | 0 |
| Structural (TS24 to TS26) | 3 | 3 | 0 | 0 |
| Release diff check (TS27) | 1 | 1 | 0 | 0 |
| Security (TM-1 to TM-3) | 3 | 3 | 0 | 0 |
| Manual (zsh reachability) | 1 | 0 | 0 | 1 |
| **Total** | 31 | 30 | 0 | 1 |
