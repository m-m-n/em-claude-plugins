# Verification Document: codex-guard-case-reading-fixes

## Overview
**Feature**: codex-guard-case-reading-fixes / **SPEC.md**: `feature-docs/codex-guard-case-reading-fixes/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/codex-guard-case-reading-fixes/IMPLEMENTATION.md`

Notation (from SPEC.md): `<NL>` is a newline; `\<NL>` is a backslash
directly followed by a newline (a continuation pair). "Both copies" means
`em-workflow/scripts/codex-hook-interactive-guard.py` and
`em-review/scripts/codex-hook-interactive-guard.py`. TS1–TS60 are SPEC.md's
scenarios; TS61 onward are defined by this plan.

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
| TS11 | Continuation before the first pattern (regression guard): `echo "$(case x in \<NL>x) :;; esac)"; python3 -i` | deny, both copies | Unit (CASES) |
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
| TS23 | Finding 8aed11cf08b2dc4c, `then` after a subshell `)`: `echo "$(if (:) then case x in x) printf '%s' '"';; esac; fi)"; python3 -i` | deny, both copies | Unit (CASES) |
| TS24 | `then` after `]]`: `echo "$(if [[ x ]] then case x in x) printf '%s' '"';; esac; fi)"; python3 -i` | deny, both copies | Unit (CASES) |
| TS25 | `do` after a subshell `)`: `echo "$(while (false) do case x in x) printf '%s' '"';; esac; done)"; python3 -i` | deny, both copies | Unit (CASES) |
| TS26 | `then` after `))`: `echo "$(if ((1)) then case x in x) printf '%s' '"';; esac; fi)"; python3 -i` | deny, both copies | Unit (CASES) |
| TS27 | `then` after `fi`: `echo "$(if if :; then :; fi then case x in x) printf '%s' '"';; esac; fi)"; python3 -i` | deny, both copies | Unit (CASES) |
| TS28 | `then` after `done`: `echo "$(if while false; do :; done then case x in x) printf '%s' '"';; esac; fi)"; python3 -i` | deny, both copies | Unit (CASES) |
| TS29 | `then` after `}`: `echo "$(if { :; } then case x in x) printf '%s' '"';; esac; fi)"; python3 -i` | deny, both copies | Unit (CASES) |
| TS30 | `then` after `esac`: `echo "$(if case y in y) :;; esac then case x in x) printf '%s' '"';; esac; fi)"; python3 -i` | deny, both copies | Unit (CASES) |
| TS31 | zsh short form, `{` after `]]`: `echo "$(if [[ x ]] { case x in x) printf '%s' '"';; esac; })"; python3 -i` | deny, both copies | Unit (CASES) |
| TS32 | Finding 2fe94b219da49a89, false-deny form: `echo "$(f() { case x in x) echo "; python3 -i;";; esac; }; f)"` | silent, both copies | Unit (CASES) |
| TS33 | Finding 2fe94b219da49a89, missed-deny form (`{` after `f()`): `echo "$(f() { case x in x) printf '%s' '"';; esac; }; f)"; python3 -i` | deny, both copies | Unit (CASES) |
| TS34 | `()` after a blank: `echo "$(f () { case x in x) printf '%s' '"';; esac; }; f)"; python3 -i` | deny, both copies | Unit (CASES) |
| TS35 | `{` after `function name`: `echo "$(function f { case x in x) printf '%s' '"';; esac; }; f)"; python3 -i` | deny, both copies | Unit (CASES) |
| TS36 | `{` after `function name()`: `echo "$(function f() { case x in x) printf '%s' '"';; esac; }; f)"; python3 -i` | deny, both copies | Unit (CASES) |
| TS37 | `then` after a word-internal substitution close is an argument: `echo "$(echo "$(:)" then case x in x)"; python3 -i` | deny, both copies | Unit (CASES) |
| TS38 | `then` after a word-internal `( )` (zsh glob qualifier) is an argument: `echo "$(echo x(N) then case x in x)"; python3 -i` | deny, both copies | Unit (CASES) |
| TS39 | `then` after a `]]` with no open `[[` is an argument: `echo "$(echo ]] then case x in x)"; python3 -i` | deny, both copies | Unit (CASES) |
| TS40 | `then` after an argument-position `fi` is an argument: `echo "$(echo fi then case x in x)"; python3 -i` | deny, both copies | Unit (CASES) |
| TS41 | `if (:) then ` nested `DEPTH` levels around `case x in x) :;; esac`, closed by `; fi` × `DEPTH`, then `python3 -i` after the substitution (SPEC.md input expression) | deny within `TIMEOUT`, both copies | Performance |
| TS42 | `f() { ` nested `DEPTH` levels around `case x in x) :;; esac`, closed by `; }` × `DEPTH`, then `python3 -i` after the substitution (SPEC.md input expression) | deny within `TIMEOUT`, both copies | Performance |
| TS43 | `echo ` followed by `]] fi done then ` × `DEPTH` and `case x in x)`, then `python3 -i` after the substitution (SPEC.md input expression) | deny within `TIMEOUT`, both copies | Performance |
| TS44 | `do` after an arithmetic for's `))`: `echo "$(for ((i=0;i<1;i++)) do case x in x) printf '%s' '"';; esac; done)"; python3 -i` | deny, both copies | Unit (CASES) |
| TS45 | `do` after `for name`: `echo "$(for x do case x in x) printf '%s' '"';; esac; done)"; python3 -i` | deny, both copies | Unit (CASES) |
| TS46 | `{` after `coproc`: `echo "$(coproc { case x in x) printf '%s' '"';; esac; })"; python3 -i` | deny, both copies | Unit (CASES) |
| TS47 | `{` after `coproc NAME`: `echo "$(coproc c { case x in x) printf '%s' '"';; esac; })"; python3 -i` | deny, both copies | Unit (CASES) |
| TS48 | The for name `case` is not a keyword, and a later argument `case` opens nothing: `echo "$(for case in x; do :; done; echo case x in x)"; python3 -i` | deny, both copies | Unit (CASES) |
| TS49 | `{` after zsh `for name (words)`: `echo "$(for x (a) { case x in x) printf '%s' '"';; esac; })"; python3 -i` | deny, both copies | Unit (CASES) |
| TS50 | `{` after zsh `repeat word`: `echo "$(repeat 1 { case x in x) printf '%s' '"';; esac; })"; python3 -i` | deny, both copies | Unit (CASES) |
| TS51 | `do` after `select name`: `echo "$(select x do case x in x) printf '%s' '"';; esac; done)"; python3 -i` | deny, both copies | Unit (CASES) |
| TS52 | Quoted launch in a case body after `for name`: `echo "$(for x do case x in x) echo "; python3 -i;";; esac; done)"` | silent, both copies | Unit (CASES) |
| TS53 | Quoted launch in a case body after `coproc`: `echo "$(coproc { case x in x) echo "; python3 -i;";; esac; })"` | silent, both copies | Unit (CASES) |
| TS54 | Quoted launch in a case body after zsh `for name (words)`: `echo "$(for x (a) { case x in x) echo "; python3 -i;";; esac; })"` | silent, both copies | Unit (CASES) |
| TS55 | Quoted launch in a case body after zsh `repeat word`: `echo "$(repeat 1 { case x in x) echo "; python3 -i;";; esac; })"` | silent, both copies | Unit (CASES) |
| TS56 | Argument-position `for` starts no head: `echo "$(echo for x do case x in x)"; python3 -i` | deny, both copies | Unit (CASES) |
| TS57 | Quoted `for` starts no head: `echo "$("for" x do case x in x)"; python3 -i` | deny, both copies | Unit (CASES) |
| TS58 | Argument-position `coproc` starts no head: `echo "$(echo coproc { case x in x)"; python3 -i` | deny, both copies | Unit (CASES) |
| TS59 | Argument-position `repeat` starts no head: `echo "$(echo repeat 1 { case x in x)"; python3 -i` | deny, both copies | Unit (CASES) |
| TS60 | `for x do ` nested `DEPTH` levels around `case x in x) :;; esac`, closed by `; done` × `DEPTH`, then `python3 -i` after the substitution (SPEC.md input expression) | deny within `TIMEOUT`, both copies | Performance |
| TS61 | Plan-defined: a reserved, closing or head word split by a continuation pair is read as that word — three rows, `echo "$(if (:) th\<NL>en case x in x) printf '%s' '"';; esac; fi)"; python3 -i`, `echo "$(if if :; then :; f\<NL>i then case x in x) printf '%s' '"';; esac; fi)"; python3 -i` and `echo "$(f\<NL>or x do case x in x) printf '%s' '"';; esac; done)"; python3 -i` | deny for each row, both copies | Unit (CASES) |
| TS62 | Every `CASES` row present before task0002 (pre-feature rows and TS1–TS19; none removed, none re-verdicted) | original verdict, both copies | Integration |
| TS63 | `TestCopies` | both copies byte-identical | Integration |
| TS64 | `TestNoRecursion` and `TestSubstitutionSkipCallStructure` | pass | Integration |
| TS65 | `TestStaticConstraints` | pass | Integration |
| TS66 | `TestSubstitutionSkipDocumentation` | pass | Integration |
| TS67 | `python3 -m unittest discover -s tests` and the project test command | exit 0 | Integration |
| TS68 | Change set from `workflow.implement.base_commit` to the integration head: no change to `em-workflow/.claude-plugin/plugin.json`, `em-review/.claude-plugin/plugin.json` or `.claude-plugin/marketplace.json` | no such path in `git diff --name-only` | Integration (command check) |

`DEPTH` and `TIMEOUT` are the values used by `TestCaseStatementsInASubstitution`;
TS20–TS22, TS41–TS43 and TS60 live in that class (SPEC.md FR8).

## Code Quality Verification
- Format: none configured (`format_command` is empty).
- Static analysis: `TestStaticConstraints` (TS65) — standard library only.
- Two-copy identity: `TestCopies` (TS63); spot check with `cmp em-workflow/scripts/codex-hook-interactive-guard.py em-review/scripts/codex-hook-interactive-guard.py` (no output, exit 0).

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | Reproductions 1–3 give the expected verdicts on both copies | TS1, TS2, TS3 |
| AC2 | Derived rows TS4–TS19 are in `CASES` and pass on both copies | TS4–TS19 |
| AC3 | Every pre-existing `CASES` row keeps its verdict; the guard test module passes | TS62; `python3 -m unittest tests.test_codex_hook_interactive_guard` |
| AC4 | `TestCopies` confirms byte identity | TS63 |
| AC5 | TS20–TS22 answer within the `TestCaseStatementsInASubstitution` scale and time limit and deny the later launch | TS20, TS21, TS22 |
| AC6 | `python3 -m unittest discover -s tests` passes | TS67 |
| AC7 | Review round 1 findings: TS23 deny (8aed11cf08b2dc4c); TS32 silent and TS33 deny (2fe94b219da49a89), on both copies | TS23, TS32, TS33 |
| AC8 | Compound-closing and function-head rows TS24–TS31, TS34–TS40 are in `CASES` and pass on both copies | TS24–TS31, TS34–TS40 |
| AC9 | TS41–TS43 and TS60 answer within the `TestCaseStatementsInASubstitution` scale and time limit and deny the later launch | TS41, TS42, TS43, TS60 |
| AC10 | Loop and coproc head rows TS44–TS59 are in `CASES` and pass on both copies | TS44–TS59 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001, task0002 | TS1, TS4, TS5, TS6, TS7, TS22, TS23, TS37, TS38, TS61, TS62 |
| FR2 | task0001, task0002 | TS1, TS4, TS5, TS6, TS7, TS37, TS38, TS39, TS40, TS43, TS48, TS56, TS57, TS58, TS59, TS62 |
| FR3 | task0001 | TS2, TS8, TS62 |
| FR4 | task0001 | TS3, TS9, TS10, TS11, TS20, TS62 |
| FR5 | task0001 | TS12–TS21, TS62 |
| FR6 | task0001, task0002 | TS63 |
| FR7 | task0001, task0002 | TS66; manual docstring review below |
| FR8 | task0001, task0002 | TS1–TS19, TS23–TS40, TS44–TS59 present in `CASES`; TS62 |
| FR9 | task0002 | TS23–TS31, TS37, TS38, TS39, TS40, TS41, TS61 |
| FR10 | task0002 | TS32–TS36, TS42 |
| FR11 | task0002 | TS44–TS60, TS61 |
| NFR1 | task0001, task0002 | TS20, TS21, TS22, TS41, TS42, TS43, TS60 |
| NFR2 | task0001, task0002 | TS64 |
| NFR3 | task0001, task0002 | TS65 |
| NFR4 | task0001, task0002 | TS68 |

## Manual Testing (E2E Not Possible)
- [ ] Run the reproduction procedure from the feature goal against each copy: feed a PreToolUse(Bash) JSON whose `tool_input.command` is the TS1, TS2, TS3, TS23, TS32 and TS33 command to the hook's standard input (the command itself is not executed). Expected: no output for TS1, TS2 and TS32, a deny for TS3, TS23 and TS33, identical for both copies.
- [ ] Read the rewritten `_skip_substitution` docstring and confirm it states the command-position state, the case open/close rule, the comment rule after a pattern `)`, the continuation-pair skipping in waiting phases, the pair-stripped decision for keywords and reserved words, the compound closings that give command position (and the word-internal closings that do not), the function heads, and the loop and coproc heads; if a keyword-check method remains, confirm its docstring states the pair-stripped rule (FR7).

## Performance / Security Verification
- NFR1: TS20, TS21, TS22, TS41, TS42, TS43 and TS60 return within `TIMEOUT` at `DEPTH` scale and deny, on both copies.
- TM-1: argument-position `case` / `esac` never opens or closes a statement and an argument-position reserved word or `!` gives no command position — checked by TS1, TS4, TS5 (silent) and TS6, TS7 (deny) on both copies.
- TM-2: a `#` directly after a pattern `)` starts a comment whose contents close and open nothing — checked by TS2 (silent) and TS8 (deny) on both copies.
- TM-3: continuation pairs keep waiting phases and keywords are decided on the pair-stripped sequence — checked by TS3, TS9, TS10, TS11, TS14–TS18 (deny) and TS12, TS13, TS19 (silent) on both copies.
- TM-4: reading stays linear on crafted long input — checked by TS20, TS21, TS22 (within `TIMEOUT` at `DEPTH`), with TS64 confirming no recursion.
- TM-5: exactly the FR9 compound closings give the next word command position, and word-internal closes, an unmatched `]]` and argument-position closing words do not — checked by TS23–TS31 and TS37–TS40 (deny) and the TS61 rows (deny) on both copies.
- TM-6: function heads give the next word command position, the name after `function` is never a keyword, and an argument-position or quoted `function` starts no head — checked by TS32 (silent) and TS33–TS36 (deny) on both copies.
- TM-7: loop and coproc heads give the FR11 positions command position, the for name, the repeat count and the zsh word list are ordinary words, and an argument-position or quoted head word starts no head — checked by TS44–TS51 and TS56–TS59 (deny), TS52–TS55 (silent) and the `f\<NL>or` row of TS61 (deny) on both copies.
- TM-8: the new state keeps reading linear on crafted long input — checked by TS41, TS42, TS43 and TS60 (within `TIMEOUT` at `DEPTH`), with TS64 confirming no recursion.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Unit (CASES rows TS1–TS19, TS23–TS40, TS44–TS59) | 53 | 53 | 0 | 0 |
| Unit (plan-defined CASES rows, TS61) | 1 | 1 | 0 | 0 |
| Performance (TS20–TS22, TS41–TS43, TS60) | 7 | 7 | 0 | 0 |
| Integration (TS62–TS68) | 7 | 7 | 0 | 0 |
| Security (TM-1–TM-8) | 8 | 8 | 0 | 0 |
| Manual (reproduction via stdin, docstring review) | 2 | 0 | 0 | 2 |
| **Total** | 78 | 76 | 0 | 2 |
