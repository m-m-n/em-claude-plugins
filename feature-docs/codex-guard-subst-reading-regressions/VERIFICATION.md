# Verification Document: codex-guard-subst-reading-regressions

## Overview
**Feature**: codex-guard-subst-reading-regressions / **SPEC.md**: `feature-docs/codex-guard-subst-reading-regressions/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/codex-guard-subst-reading-regressions/IMPLEMENTATION.md`

Integrated verification of the three tasks merged into the integration branch. Task-level acceptance criteria live in `tasks/task0001.md` to `tasks/task0003.md`. Notation follows SPEC.md: `<NL>` is a newline, `\<NL>` a backslash directly followed by a newline, `wrap_bash(s)` is `'bash -c ' + shlex.quote(s)` and `wrap_zsh(s)` is `'zsh -c ' + shlex.quote(s)`.

## Build Verification
- Command: none (`build_command` is empty; the guard is a Python script run as is)
- Expected: not applicable

## Test Verification
- Command: `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests`
- Focused command: `python3 -m unittest tests.test_codex_hook_interactive_guard`
- Coverage target: not measured (no coverage tool is configured); every scenario below passes against both copies

### Test Scenarios from SPEC.md
TS1 to TS27 are SPEC.md's scenarios; their commands are written in SPEC.md (Test Scenarios). TS28 to TS33 pin clauses of FR1, FR2, FR3 and FR6 that no SPEC.md scenario isolates. TS34 to TS40 are the integration checks of SPEC.md's Integration Tests and Success Criteria. Rows marked CASES run through `test_cases_run_against_both_copies`.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS1 | Defect 1 reproduction: a `#` comment holding a `"` in a zsh `for` word list (SPEC.md command) | deny on both copies | Unit (CASES) |
| TS2 | Defect 2 reproduction: `f(\<NL>)` before a function body with a case statement, `bash -c` wrapped (SPEC.md command) | deny on both copies | Unit (CASES) |
| TS3 | Defect 3 reproduction: zsh `coproc echo case x in x` (SPEC.md command) | deny on both copies | Unit (CASES) |
| TS4 | bash `repeat x case y in y` (SPEC.md command) | deny on both copies | Unit (CASES) |
| TS5 | A `)` inside a word-list comment does not close the list (SPEC.md command) | deny on both copies | Unit (CASES) |
| TS6 | Quoted `python3 -i` in the case body after a commented word list (SPEC.md command) | silent on both copies | Unit (CASES) |
| TS7 | A `case` after a newline inside the word list opens no statement (SPEC.md command) | deny on both copies | Unit (CASES) |
| TS8 | A comment directly after the word list's `(` (SPEC.md command) | deny on both copies | Unit (CASES) |
| TS9 | Pair after `f (` (SPEC.md command) | deny on both copies | Unit (CASES) |
| TS10 | Pair after `function f(` (SPEC.md command) | deny on both copies | Unit (CASES) |
| TS11 | Blanks mixed with several pairs inside an empty `()` (SPEC.md command) | deny on both copies | Unit (CASES) |
| TS12 | Quoted `python3 -i` in the body of a function whose `()` holds a pair (SPEC.md command) | silent on both copies | Unit (CASES) |
| TS13 | `wrap_bash` of the earlier feature's `coproc c {` row: bash coproc NAME then `{` (SPEC.md) | deny on both copies | Unit (CASES) |
| TS14 | bash: a `case` after `coproc WORD` opens a statement (SPEC.md command) | deny on both copies | Unit (CASES) |
| TS15 | `wrap_zsh` of the earlier feature's `repeat 1 {` row (SPEC.md) | deny on both copies | Unit (CASES) |
| TS16 | `wrap_zsh` of the earlier feature's `coproc {` row (SPEC.md) | deny on both copies | Unit (CASES) |
| TS17 | `wrap_zsh` of the earlier feature's silent `coproc {` body row (SPEC.md) | silent on both copies | Unit (CASES) |
| TS18 | bash `repeat 1 { case x in x` keeps `{` and `case` as arguments (SPEC.md command) | deny on both copies | Unit (CASES) |
| TS19 | Top level, unknown kind, coproc form: first read undecidable, re-read decides (SPEC.md command) | deny on both copies | Unit (CASES) |
| TS20 | Top level, unknown kind, repeat form: first read undecidable, re-read decides (SPEC.md command) | deny on both copies | Unit (CASES) |
| TS21 | `sh -c` string is unknown kind and is re-read (SPEC.md command) | deny on both copies | Unit (CASES) |
| TS22 | Re-read also fails: the first read's commands up to its checkpoint are judged (SPEC.md command) | deny on both copies | Unit (CASES) |
| TS23 | A bash string is never re-read: the case opened after `coproc echo` stays unclosed (SPEC.md command) | silent on both copies | Unit (CASES) |
| TS24 | `wrap_bash` of TS3: the inner `zsh -c` string is read as zsh (SPEC.md) | deny on both copies | Unit (CASES) |
| TS25 | DEPTH pairs inside `f(`...`)`, `bash -c` wrapped (SPEC.md) | deny on both copies within DEPTH and TIMEOUT | Performance (`TestCaseStatementsInASubstitution`) |
| TS26 | DEPTH commented lines in a zsh `for` word list (SPEC.md) | deny on both copies within DEPTH and TIMEOUT | Performance (`TestCaseStatementsInASubstitution`) |
| TS27 | Top-level coproc form followed by DEPTH words: two linear reads (SPEC.md) | deny on both copies within DEPTH and TIMEOUT | Performance (`TestCaseStatementsInASubstitution`) |
| TS28 | Nested parentheses in a word list keep their words off command position: `echo "$(for x (a(case x in x)) { :; })"; python3 -i` | deny on both copies | Unit (CASES) |
| TS29 | A backslash not followed by a newline is no pair, so the `()` is not empty: `echo "$(f(\ ) { case x in x) printf '%s' '"';; esac; }; f)"; python3 -i` (the characters after `f(` are a backslash, a space and `)`) | silent on both copies | Unit (CASES) |
| TS30 | zsh reached through `env` and a path: `'env /usr/bin/zsh -c ' + shlex.quote(s)` where `s` is the inner string of TS14 | silent on both copies | Unit (CASES) |
| TS31 | bash with a version suffix reached through `env` is not re-read: `'env bash5.2 -c ' + shlex.quote(s)` where `s` is the inner string of TS23 | silent on both copies | Unit (CASES) |
| TS32 | A second-level `sh -c` string that needs the re-read counts once toward NESTED_READ_LIMIT: with a second second-level string carrying `python3 -i`, the two lengths add up exactly to the limit | deny on both copies | Integration (`TestNestedReadLimit`) |
| TS33 | A re-read that raises an exception other than `_Undecidable` falls back to the first read's `_Undecidable` and its checkpoint commands | holds for both copies (syntax-tree check of the module-level parse, or a forced failure that leaves no bytecode cache) | Unit (structure) |
| TS34 | `TestCopies`: both copies exist, are byte-identical, and a run leaves no bytecode cache | pass | Integration |
| TS35 | `TestSubstitutionSkipDocumentation` and `TestGuardDocumentation` | pass | Integration |
| TS36 | `TestNoRecursion`, `TestSubstitutionSkipCallStructure` and `TestSharedQuotedUnitReader` | pass | Integration |
| TS37 | `TestStaticConstraints` | pass | Integration |
| TS38 | No plugin version changed: `git diff <implement base commit>..HEAD -- em-workflow/.claude-plugin/plugin.json em-review/.claude-plugin/plugin.json .claude-plugin/marketplace.json` (base: `workflow.implement.base_commit` in workflow.yaml) | empty output | Integration |
| TS39 | `TestNestedParseErrorContainment` and `test_scan_walks_the_nested_strings_and_find_deny_keeps_its_signature` | pass | Integration |
| TS40 | Pre-existing CASES rows unchanged: the diff of the CASES table against the implement base commit adds rows only, and `TestCasesTable` passes (unique commands, every row on both copies, including the earlier feature's top-level coproc and repeat rows) | pass | Integration |

## Code Quality Verification
- Format: none configured (`format_command` is empty)
- Static analysis: `cmp em-workflow/scripts/codex-hook-interactive-guard.py em-review/scripts/codex-hook-interactive-guard.py` prints nothing (also covered by TS34)

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | TS1 to TS3 and the bash repeat form TS4 are deny on both copies | CASES rows TS1 to TS4 |
| AC2 | TS19, TS20 and the `sh -c` form TS21 are deny on both copies | CASES rows TS19 to TS21 |
| AC3 | The derived rows TS5 to TS18 and TS22 to TS24 are in CASES with the expected verdicts on both copies | CASES rows TS5 to TS18, TS22 to TS24 (plus TS28 to TS31) |
| AC4 | Every pre-existing CASES row keeps its verdict, the earlier feature's TS47 / TS50 rows included | TS40 |
| AC5 | Both copies byte-identical | TS34 |
| AC6 | TS25 to TS27 answer within DEPTH and TIMEOUT and are deny | `TestCaseStatementsInASubstitution` (TS25 to TS27) |
| AC7 | `TestNoRecursion`, `TestSubstitutionSkipCallStructure`, `TestNestedParseErrorContainment`, `TestStaticConstraints`, `TestSubstitutionSkipDocumentation` pass | TS35, TS36, TS37, TS39 |
| AC8 | `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests` passes | Run the test command above; exit status 0 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | CASES TS1, TS5, TS6, TS7, TS8, TS28; timing TS26 |
| FR2 | task0002 | CASES TS2, TS9, TS10, TS11, TS12, TS29; timing TS25 |
| FR3 | task0003 | CASES TS3, TS4, TS13 to TS18, TS21, TS23, TS24, TS30, TS31 |
| FR4 | task0003 | CASES TS3, TS13, TS14, TS16, TS17, TS23, TS30, TS31 |
| FR5 | task0003 | CASES TS4, TS15, TS18 |
| FR6 | task0003 | CASES TS19 to TS23, TS31; timing TS27; TS32; TS33; TS40 |
| FR7 | task0001, task0002, task0003 | TS34 |
| FR8 | task0001, task0002, task0003 | TS35; manual docstring review below |
| FR9 | task0001, task0002, task0003 | CASES TS1 to TS24, TS28 to TS31; timing TS25 to TS27; TS40 |
| NFR1 | task0001, task0002, task0003 | TS25, TS26, TS27, TS32 |
| NFR2 | task0001, task0002, task0003 | TS36 |
| NFR3 | task0001, task0002, task0003 | TS37 |
| NFR4 | task0001, task0002, task0003 | TS38 |
| NFR5 | task0003 | TS39 |

## Manual Testing (E2E Not Possible)
- [ ] Docstring review (FR8): the Contexts on the stack passage (context a is arithmetic only; the word-list context reads comments and newlines), the `_empty_parens_end` docstring and the rule 6 empty `()` sentences (continuation pairs), the `HEAD_*` / `HEAD_AFTER_WORD` comments, the rule 6 coproc and repeat sentences, and the `_read_command_word`, `_Parser`, module-level `parse`, `_judge` and `_scan` docstrings and module docstring steps 7 and 9 (shell kind, re-read, fallback) describe the merged behaviour; the earlier feature's SPEC is unchanged (A5).
- [ ] FR6 residual (IMPLEMENTATION.md Risk Assessment, THREAT-MODEL.md Rationale): confirm the re-read is adopted exactly as FR6 specifies, and record whether a SPEC change is wanted.

## Performance / Security Verification (if applicable)
- NFR1: TS25, TS26 and TS27 answer within the class TIMEOUT (60 s) at the class DEPTH (6000) on both copies; TS32 confirms a re-read string counts once toward NESTED_READ_LIMIT.
- TM-1: every new reading is a forward scan with constant-size state, a string is read at most twice and counted once — checked by TS25, TS26, TS27 and TS32.
- TM-2: the commented word list, the paired empty `()`, zsh `coproc WORD` and bash `repeat` are read to the end and the launch after them is denied — checked by TS1, TS2, TS3, TS4, TS19, TS20 and TS21.
- TM-3: a failed re-read, whatever its exception class, falls back to the first read's `_Undecidable` and its checkpoint commands, and `_scan` keeps its single try — checked by TS22, TS33 and TS39.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Unit (CASES rows) | 28 (TS1 to TS24, TS28 to TS31) | 28 | 0 | 0 |
| Unit (structure) | 1 (TS33) | 1 | 0 | 0 |
| Performance | 3 (TS25 to TS27) | 3 | 0 | 0 |
| Integration | 8 (TS32, TS34 to TS40) | 8 | 0 | 0 |
| Security (TM-1 to TM-3) | 3 | 3 | 0 | 0 |
| Manual review | 2 | 0 | 0 | 2 |
