# Verification Document: codex-guard-anon-heredoc-paren-delim

## Overview
**Feature**: codex-guard-anon-heredoc-paren-delim / **SPEC.md**: `feature-docs/codex-guard-anon-heredoc-paren-delim/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/codex-guard-anon-heredoc-paren-delim/IMPLEMENTATION.md`

## Build Verification
- Command: none (`project.components.main.build_command` is empty; the guard is a Python script run directly)
- Expected: not applicable; a syntax error in either copy fails the test run below

## Test Verification
- Command (full suite, from workflow.yaml): `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests`
- Command (focused): `python3 -m unittest tests.test_codex_hook_interactive_guard`
- Expected: exit code 0, every test passes, every `CASES` entry runs against both guard copies
- Coverage target: no coverage tool is configured; coverage is scenario-based (every TS-n below is present and passing)

### Test Scenarios from SPEC.md
TS-1 to TS-11 are SPEC.md's scenarios. TS-12 to TS-19 are planner-derived
(IMPLEMENTATION.md D2): TS-12 and TS-13 give FR3 and FR2 a discriminating
case, and TS-14 to TS-19 split the existing-suite checks named by SPEC.md
AC-9 / AC-10 into one ID per requirement. In the command texts, `\n` and `\t`
stand for a newline and a tab character; other backslashes are literal.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Reproduction: `zsh -c "function { :; } << foo('x')\nfoo('x')\npython3 -i\nfoo(x)"` | silent (no stdout, no stderr, exit 0) on both copies | Unit (`CASES`) |
| TS-2 | `zsh -c "function { :; } << foo('x')\nfoo(x)\npython3 -i"` | deny on both copies | Unit (`CASES`) |
| TS-3 | `zsh -c 'function { :; } << foo(python3)\nfoo\npython3 -i\nfoo(python3)'` | silent on both copies | Unit (`CASES`) |
| TS-4 | `zsh -c 'function { :; } << foo("x")\nfoo(x)\npython3 -i'` | deny on both copies | Unit (`CASES`) |
| TS-5 | `zsh -c 'function { :; } << foo(\x)\nfoo(x)\npython3 -i'` | deny on both copies | Unit (`CASES`) |
| TS-6 | `zsh -c "function { :; } <<- foo('x')\n\tfoo(x)\npython3 -i"` | deny on both copies | Unit (`CASES`) |
| TS-7 | `zsh -c "function { python3 -i; } << foo('x')\nfoo(x)"` | deny on both copies | Unit (`CASES`) |
| TS-8 | Delimiter `foo($'x')`; body lines `foo($'x')` and `python3 -i` | silent on both copies | Unit (`CASES`) |
| TS-9 | Delimiter `foo($"x")`; body lines `foo($"x")` and `python3 -i` | silent on both copies | Unit (`CASES`) |
| TS-10 | Delimiter `foo("$'")`; body line `foo($')`, then `python3 -i` | deny on both copies | Unit (`CASES`) |
| TS-11 | Delimiter `foo(\$'x')`; body line `foo($x)`, then `python3 -i` | deny on both copies | Unit (`CASES`) |
| TS-12 | Delimiter `foo($'x')`; body line `foo($x)`, then `python3 -i` (plain quote removal would deny) | silent on both copies | Unit (`CASES`) |
| TS-13 | Delimiter `a\\b("x")` (zsh reads `a\b(x)`); body line `a\b(x)`, then `python3 -i` (a second removal of the outside part would be silent) | deny on both copies | Unit (`CASES`) |
| TS-14 | Every `CASES` entry that existed before the change keeps its verdict and passes; the duplicate check passes | pass | Unit (existing) |
| TS-15 | The two guard copies are byte-identical | pass | Unit (existing) |
| TS-16 | Module docstring step 4 states the FR1 and FR3 rules; `TestGuardDocumentation` passes with its checked sentences unchanged | pass; the rule text is confirmed by reading (Manual Testing below) | Unit (existing) + Manual |
| TS-17 | Large input driving the delimiter-range path, ending with `python3 -i` after the last true terminator | deny within the existing deep-input test's time bound, on both copies; the existing deep-input timing test passes | Unit (new + existing) |
| TS-18 | Recursion AST check | pass | Unit (existing) |
| TS-19 | Standard-library / no file, network or child-process constraint check | pass | Unit (existing) |

TS-8 to TS-13 may be written unwrapped at top level (SPEC.md TS-note); when
wrapped in `zsh -c "..."`, each `$` is written `\$` in the outer text so the
input does not become dynamic and silent for the wrong reason.

## Code Quality Verification
- Format: none configured (`format_command` is empty)
- Static analysis: none configured; the recursion AST check (TS-18) and the constraint check (TS-19) in the focused test module cover the structural rules

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | The reproduction command is silent on both copies (no output, exit 0, empty stderr) and is a silent `CASES` entry | TS-1 |
| AC-2 | A launch after the true terminator is denied | TS-2 |
| AC-3 | A body line with only the part before the range does not end the body | TS-3 |
| AC-4 | Double quotes and backslashes in the range are removed, and the launch after the terminator is denied | TS-4, TS-5 |
| AC-5 | `<<-` compares after stripping leading tabs, and the launch is denied | TS-6 |
| AC-6 | The anonymous-function body's `-i` is denied after the heredoc closes | TS-7 |
| AC-7 | An unquoted `$'` / `$"` in the range makes the input unknowable (silent) | TS-8, TS-9, TS-12 |
| AC-8 | `$'` inside double quotes and an escaped `\$` do not trigger; the removed delimiter is used and the launch is denied | TS-10, TS-11 |
| AC-9 | The existing tests pass (duplicates, byte identity, deep-input timing, recursion) | TS-14, TS-15, TS-17, TS-18, TS-19 via the focused command |
| AC-10 | The module docstring states the FR1 and FR3 rules and the existing marker check passes | TS-16 (automated marker check + manual reading of the rule text) |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2, TS-3, TS-4, TS-5, TS-6, TS-7 |
| FR2 | task0001 | TS-13 |
| FR3 | task0001 | TS-8, TS-9, TS-10, TS-11, TS-12 |
| FR4 | task0001 | TS-14 |
| FR5 | task0001 | TS-15 |
| FR6 | task0001 | TS-16 |
| FR7 | task0001 | TS-1 to TS-11 present in `CASES` as `(expected verdict, label, command)` |
| NFR1 | task0001 | TS-17 |
| NFR2 | task0001 | TS-18 |
| NFR3 | task0001 | TS-19 |
| NFR4 | task0001 | TS-8, TS-9, TS-12, TS-14 |

## Manual Testing (E2E Not Possible)
- [ ] TS-16 (rule text): read step 4 of the module docstring in either copy and confirm it states that a `<<` / `<<-` delimiter range in an anonymous-function argument is quote-removed by the normal path's rules without reprocessing the part outside the range, and that an unquoted `$'` / `$"` in such a range makes the whole input unknowable

## Performance / Security Verification
- NFR1: TS-17 — on both copies, the large delimiter-range input returns deny within the time bound the existing deep-input timing test uses
- TM-1: the delimiter is derived from the range text only, by the normal path's rules, without reprocessing the outside part, and only an unquoted `$'` / `$"` makes the input unknowable — checked by TS-2, TS-4, TS-5, TS-6, TS-7 and TS-13 (deny after the true terminator or in the anonymous-function body) and TS-10, TS-11 (a quoted or escaped `$` still yields a deny), on both copies
- TM-2: the range work is one linear pass per range with the `PAREN_SCAN_FACTOR` bound unchanged — checked by TS-17 and the existing deep-input timing test

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios in `CASES` (TS-1 to TS-13) | 13 | 13 | 0 | 0 |
| Existing-suite / structural checks (TS-14, TS-15, TS-16, TS-18, TS-19) | 5 | 5 | 0 | 1 (TS-16 rule text) |
| Performance (TS-17) | 1 | 1 | 0 | 0 |
| Security (TM-1, TM-2) | 2 | 2 | 0 | 0 |
| Success criteria (AC-1 to AC-10) | 10 | 10 | 0 | 1 (AC-10 rule text) |
