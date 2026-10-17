# Verification Document: codex-guard-anon-arg-paren-comment

## Overview
**Feature**: codex-guard-anon-arg-paren-comment / **SPEC.md**: `feature-docs/codex-guard-anon-arg-paren-comment/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/codex-guard-anon-arg-paren-comment/IMPLEMENTATION.md`

Scenario IDs: TS-1 to TS-17 correspond to SPEC.md TS1 to TS17 of the same
number. TS-18 to TS-20 cover the FR4 operators SPEC.md lists without a
scenario; TS-21 is SPEC.md's unnumbered integration test; TS-22 checks NFR3.
`<NL>` in a command is one newline character inside the command string.

## Build Verification
- Command: none (`build_command` is empty in workflow.yaml; Python scripts
  have no build step)
- Expected: not applicable

## Test Verification
- Command (project): `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests`
- Command (guard module): `python3 -m unittest tests.test_codex_hook_interactive_guard`
- Expected: exit code 0, no failures or errors
- Coverage target: no coverage tool is configured; every scenario below runs
  against both guard copies (`em-workflow/scripts/codex-hook-interactive-guard.py`,
  `em-review/scripts/codex-hook-interactive-guard.py`)

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | `zsh -c 'setopt nobadpattern; function { :; } foo(a; python3 -i #)'` (existing silent case converted, label revised) | deny, exactly one | Unit (`CASES`) |
| TS-2 | `zsh -c 'setopt nobadpattern; function { :; } foo(a & python3 -i #)'` | deny | Unit (`CASES`) |
| TS-3 | `zsh -c 'setopt nobadpattern; function { :; } foo(a<NL>python3 -i #)'` | silent | Unit (`CASES`) |
| TS-4 | `zsh -c 'setopt nobadpattern; function { :; } foo(a; python3 -i'` (no closing paren) | deny | Unit (`CASES`) |
| TS-5 | `zsh -c 'setopt nobadpattern; function { :; } (a; python3 -i #)'` (word-initial `(`) | deny | Unit (`CASES`) |
| TS-6 | `zsh -c 'setopt nobadpattern; function { :; } foo(a<NL>b; python3 -i #)'` (newline first) | silent | Unit (`CASES`) |
| TS-7 | `zsh -c 'setopt nobadpattern; function { :; } foo(a; b<NL>python3 -i #)'` (`;` first, newline later) | deny | Unit (`CASES`) |
| TS-8 | `zsh -c 'setopt nobadpattern; function { :; } foo(a && python3 -i #)'` | silent | Unit (`CASES`) |
| TS-9 | `zsh -c '(python3 -i #)'` | silent | Unit (`CASES`) |
| TS-10 | `zsh -c 'setopt nobadpattern; (function { :; } foo(a; python3 -i #)'` | silent | Unit (`CASES`) |
| TS-11 | `zsh -c 'function { python3 -i; } foo('` (existing case, unchanged) | silent | Unit (`CASES`) |
| TS-12 | `zsh -c 'setopt nobadpattern; function { :; } foo(a; python3 < /dev/null #)'` | silent | Unit (`CASES`) |
| TS-13 | `zsh -c 'setopt nobadpattern; echo x \| function { :; } foo(a; python3 #)'` | deny | Unit (`CASES`) |
| TS-14 | `zsh -c 'setopt nobadpattern; f() { function { :; } foo(a; python3 -i #)<NL>}'` | silent | Unit (`CASES`) |
| TS-15 | Existing closed forms `foo(a; python3 -i)`, `foo(a & python3 -i)`, `foo(a<NL>python3 -i)` | deny, unchanged | Unit (`CASES`) |
| TS-16 | Performance: `function { :; } x(` nested to the existing depth followed by `; python3 -i #`, a wide-tail variant (many short commands after the separator), and the existing `unclosed ranges` forms | Both copies respond within the existing time limit; recursion check passes | Unit (performance) |
| TS-17 | TestGuardDocumentation markers for the rescue rule (provisional group; `;` / lone `&` trigger; newline first not rescued; genuinely unclosed group gives no output); byte-identity test | Pass | Unit |
| TS-18 | TS-8 command with `&&` replaced by `\|\|`, by `\|` and by `\|&` | silent (each) | Unit (`CASES`) |
| TS-19 | `zsh -c 'setopt nobadpattern; function { :; } foo(a &>/dev/null python3 -i #)'` and `zsh -c 'setopt nobadpattern; function { :; } foo(a >& python3 -i #)'` | silent (each) | Unit (`CASES`) |
| TS-20 | TS-1 command with `;` written as `";"` and as `\;`; TS-2 command with `&` written as `"&"` and as `\&` | silent (each) | Unit (`CASES`) |
| TS-21 | `python3 -m unittest tests.test_codex_hook_interactive_guard` and the project test command, including the existing constraint tests (standard library only; no file, network or child process) | Pass | Integration |
| TS-22 | `git diff --name-only` from `workflow.implement.base_commit` to HEAD | Lists neither `em-workflow/.claude-plugin/plugin.json`, `em-review/.claude-plugin/plugin.json` nor `.claude-plugin/marketplace.json` | Integration (diff check) |

## Code Quality Verification
- Format: none configured (`format_command` is empty in workflow.yaml)
- Static analysis: none configured
- Byte identity of the two guard copies: covered by TS-17

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | `foo(a; python3 -i #)` gives one deny from both copies | TS-1 (with TS-4, TS-5, TS-7) |
| AC-2 | `foo(a & python3 -i #)` gives deny from both copies | TS-2 |
| AC-3 | `foo(a<NL>python3 -i #)` gives no output from both copies | TS-3, TS-6 |
| AC-4 | `&&` first gives no output | TS-8 (with TS-18 to TS-20) |
| AC-5 | Command-position unclosed `(` and an argument `(` without separator give no output | TS-9, TS-10, TS-11 |
| AC-6 | Input redirection after rescue gives no output; head pipe does not reach the rescued command; function-definition body is not judged | TS-12, TS-13, TS-14 |
| AC-7 | Docstrings state the rescue rule; documentation tests pass | TS-17 |
| AC-8 | Byte-identity test passes | TS-17 |
| AC-9 | Deeply nested provisional groups answered within the existing time limit; recursion check passes | TS-16 |
| AC-10 | Guard module and full test suite pass; existing deny cases remain | TS-15, TS-21 |
| SC | All functional requirements implemented and tested; all scenarios pass; performance goal met; documentation complete; code review completed | This document's scenario table; review phase result |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-4, TS-5, TS-7 |
| FR2 | task0001 | TS-2 |
| FR3 | task0001 | TS-3, TS-6 |
| FR4 | task0001 | TS-8, TS-18, TS-19, TS-20 |
| FR5 | task0001 | TS-9, TS-10, TS-11 |
| FR6 | task0001 | TS-12, TS-13, TS-14 |
| FR7 | task0001 | TS-17 |
| FR8 | task0001 | TS-17 |
| FR9 | task0001 | TS-1, TS-2, TS-3, TS-15, TS-21 |
| NFR1 | task0001 | TS-16 |
| NFR2 | task0001 | TS-21 |
| NFR3 | task0001 | TS-22 |

## Manual Testing (E2E Not Possible)
- None. Every scenario is automated.

## Performance / Security Verification (if applicable)
- NFR1: TS-16 — both copies within the existing time limit; no recursion.
- TM-1: rescue of an unclosed anonymous-function argument group at `;` / lone `&`, with rescued commands outside the head's connection — checked by TS-1, TS-2, TS-4, TS-5, TS-7 (deny) and TS-13 (deny despite the head pipe).
- TM-2: linear-time, non-recursive rescue — checked by TS-16 (TS-16 form and wide-tail variant within the existing time limit; recursion check).
- TM-3: verdict from the command string alone, no file, network or child process — checked by the existing constraint tests in TS-21.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios (TS-1 to TS-22) | 22 | 22 | 0 | 0 |
| Success criteria (AC-1 to AC-10, SC) | 11 | 11 | 0 | 0 |
| Performance (NFR1) | 1 | 1 | 0 | 0 |
| Security (TM-1 to TM-3) | 3 | 3 | 0 | 0 |
