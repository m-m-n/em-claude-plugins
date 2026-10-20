# Verification Document: codex-guard-case-reading-fixes

## Overview
**Feature**: codex-guard-case-reading-fixes / **SPEC.md**: `feature-docs/codex-guard-case-reading-fixes/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/codex-guard-case-reading-fixes/IMPLEMENTATION.md`

Notation (from SPEC.md): `<NL>` is a newline; `\<NL>` is a backslash
directly followed by a newline (a continuation pair). "Both copies" means
`em-workflow/scripts/codex-hook-interactive-guard.py` and
`em-review/scripts/codex-hook-interactive-guard.py`.

## Build Verification
- Command: none (`project.components.main.build_command` is empty; Python
  scripts have no build step — the test run loads both copies).
- Expected: not applicable.

## Test Verification
- Command (project): `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests`
- Command (guard, repository rule): `python3 -m unittest tests.test_codex_hook_interactive_guard`
- Expected: exit code 0 for both.
- Coverage target: not measured (no coverage tooling is configured);
  coverage is by scenario — every row below must pass.

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS1 | Reproduction 1: `echo "$(case y in x) echo if esac;; y) echo "; python3 -i;";; esac)"` | silent, both copies | Unit (CASES) |
| TS2 | Reproduction 2: `echo "$(case x in x)#; esac<NL>:;; y) printf '%s' '"; python3 -i; #';; esac)"` | silent, both copies | Unit (CASES) |
| TS3 | Reproduction 3: `echo "$(case x \<NL>in x) :;; esac)"; python3 -i` | deny, both copies | Unit (CASES) |
| TS4 | Argument `then`: `echo "$(case y in x) echo then esac;; y) echo "; python3 -i;";; esac)"` | silent, both copies | Unit (CASES) |
| TS5 | Argument `!`: `echo "$(case y in x) echo ! esac;; y) echo "; python3 -i;";; esac)"` | silent, both copies | Unit (CASES) |
| TS6 | Quote-shift form: `echo "$(case x in x) echo then esac;; y) echo '"';; esac)"; python3 -i #'` | deny, both copies | Unit (CASES) |
| TS7 | Argument `case` outside an item body: `echo "$(echo then case x in x)"; python3 -i` | deny, both copies | Unit (CASES) |
| TS8 | `)` inside the comment after a pattern: `echo "$(case x in x)#)<NL>:;; esac)"; python3 -i` | deny, both copies | Unit (CASES) |
| TS9 | Continuation before the subject word: `echo "$(case \<NL>x in x) :;; esac)"; python3 -i` | deny, both copies | Unit (CASES) |
| TS10 | Continuation before an empty case's `esac`: `echo "$(case x in \<NL>esac)"; python3 -i` | deny, both copies | Unit (CASES) |
| TS11 | Continuation before the first pattern (deny today; regression guard): `echo "$(case x in \<NL>x) :;; esac)"; python3 -i` | deny, both copies | Unit (CASES) |
| TS12 | Continuation directly after `case`: `echo "$(case\<NL> x in x) echo "; python3 -i; ";; esac)"` | silent, both copies | Unit (CASES) |
| TS13 | Continuation splitting `case`: `echo "$(ca\<NL>se x in x) echo "; python3 -i; ";; esac)"` | silent, both copies | Unit (CASES) |
| TS14 | Continuation directly after `in`: `echo "$(case x in\<NL> x) :;; esac)"; python3 -i` | deny, both copies | Unit (CASES) |
| TS15 | Continuation directly after `esac`: `echo "$(case x in x) :;; esac\<NL>)"; python3 -i` | deny, both copies | Unit (CASES) |
| TS16 | Continuation splitting `in`: `echo "$(case x i\<NL>n x) :;; esac)"; python3 -i` | deny, both copies | Unit (CASES) |
| TS17 | Continuation splitting `esac`: `echo "$(case x in x) :;; es\<NL>ac)"; python3 -i` | deny, both copies | Unit (CASES) |
| TS18 | Pair-stripped `casex` is not a keyword; `x)` closes the substitution: `echo "$(ca\<NL>sex in x) echo "; python3 -i; ";; esac)"` | deny, both copies | Unit (CASES) |
| TS19 | Pair-stripped `esacx` is a pattern and closes nothing: `echo "$(case x in es\<NL>acx) echo "; python3 -i; ";; esac)"` | silent, both copies | Unit (CASES) |
| TS20 | `DEPTH` continuation pairs in each waiting phase (before the subject word, before `in`, at the pattern position) and between keyword characters, then `python3 -i` after the substitution | deny within `TIMEOUT`, both copies | Performance |
| TS21 | `DEPTH` split words like `c\<NL>a\<NL>s\<NL>x ` in an item body (failed keyword matches), then `python3 -i` after the substitution | deny within `TIMEOUT`, both copies | Performance |
| TS22 | `DEPTH` argument `then ` words in an item body, closed by `esac`, then `python3 -i` after the substitution | deny within `TIMEOUT`, both copies | Performance |
| TS23 | Every pre-existing `CASES` row (none removed, none re-verdicted) | original verdict, both copies | Integration |
| TS24 | `TestCopies` | both copies byte-identical | Integration |
| TS25 | `TestNoRecursion` and `TestSubstitutionSkipCallStructure` | pass | Integration |
| TS26 | `TestStaticConstraints` | pass | Integration |
| TS27 | `TestSubstitutionSkipDocumentation` | pass | Integration |
| TS28 | `python3 -m unittest discover -s tests` and the project test command | exit 0 | Integration |
| TS29 | Change set from `workflow.implement.base_commit` to the integration head: no change to `em-workflow/.claude-plugin/plugin.json`, `em-review/.claude-plugin/plugin.json` or `.claude-plugin/marketplace.json` | no such path in `git diff --name-only` | Integration (command check) |

`DEPTH` and `TIMEOUT` are the values used by `TestCaseStatementsInASubstitution`.

## Code Quality Verification
- Format: none configured (`format_command` is empty).
- Static analysis: `TestStaticConstraints` (TS26) — standard library only.
- Two-copy identity: `TestCopies` (TS24); spot check with `cmp em-workflow/scripts/codex-hook-interactive-guard.py em-review/scripts/codex-hook-interactive-guard.py` (no output, exit 0).

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | Reproductions 1–3 give the expected verdicts on both copies | TS1, TS2, TS3 |
| AC2 | Derived rows TS4–TS19 are in `CASES` and pass on both copies | TS4–TS19 |
| AC3 | Every pre-existing `CASES` row keeps its verdict; the guard test module passes | TS23; `python3 -m unittest tests.test_codex_hook_interactive_guard` |
| AC4 | `TestCopies` confirms byte identity | TS24 |
| AC5 | TS20–TS22 answer within the `TestCaseStatementsInASubstitution` scale and time limit and deny the later launch | TS20, TS21, TS22 |
| AC6 | `python3 -m unittest discover -s tests` passes | TS28 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS1, TS4, TS5, TS6, TS7, TS22, TS23 |
| FR2 | task0001 | TS1, TS4, TS5, TS6, TS7, TS23 |
| FR3 | task0001 | TS2, TS8, TS23 |
| FR4 | task0001 | TS3, TS9, TS10, TS11, TS20, TS23 |
| FR5 | task0001 | TS12–TS19, TS20, TS21, TS23 |
| FR6 | task0001 | TS24 |
| FR7 | task0001 | TS27; manual docstring review below |
| FR8 | task0001 | TS1–TS19 present in `CASES`; TS23 |
| NFR1 | task0001 | TS20, TS21, TS22 |
| NFR2 | task0001 | TS25 |
| NFR3 | task0001 | TS26 |
| NFR4 | task0001 | TS29 |

## Manual Testing (E2E Not Possible)
- [ ] Run the reproduction procedure from the feature goal against each copy: feed a PreToolUse(Bash) JSON whose `tool_input.command` is the TS1, TS2 and TS3 command to the hook's standard input (the command itself is not executed). Expected: no output for TS1 and TS2, a deny for TS3, identical for both copies.
- [ ] Read the rewritten `_skip_substitution` docstring and confirm it states the command-position state, the case open/close rule, the comment rule after a pattern `)`, the continuation-pair skipping in waiting phases and the pair-stripped keyword decision; if a keyword-check method remains, confirm its docstring states the pair-stripped rule (FR7).

## Performance / Security Verification
- NFR1: TS20, TS21 and TS22 return within `TIMEOUT` at `DEPTH` scale and deny, on both copies.
- TM-1: argument-position `case` / `esac` never opens or closes a statement and an argument-position reserved word or `!` gives no command position — checked by TS1, TS4, TS5 (silent) and TS6, TS7 (deny) on both copies.
- TM-2: a `#` directly after a pattern `)` starts a comment whose contents close and open nothing — checked by TS2 (silent) and TS8 (deny) on both copies.
- TM-3: continuation pairs keep waiting phases and keywords are decided on the pair-stripped sequence — checked by TS3, TS9, TS10, TS11, TS14–TS18 (deny) and TS12, TS13, TS19 (silent) on both copies.
- TM-4: reading stays linear on crafted long input — checked by TS20, TS21, TS22 (within `TIMEOUT` at `DEPTH`), with TS25 confirming no recursion.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Unit (CASES rows TS1–TS19) | 19 | 19 | 0 | 0 |
| Performance (TS20–TS22) | 3 | 3 | 0 | 0 |
| Integration (TS23–TS29) | 7 | 7 | 0 | 0 |
| Security (TM-1–TM-4) | 4 | 4 | 0 | 0 |
| Manual (reproduction via stdin, docstring review) | 2 | 0 | 0 | 2 |
| **Total** | 35 | 33 | 0 | 2 |
