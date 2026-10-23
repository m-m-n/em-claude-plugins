# Verification Document: codex-guard-delim-brace-quote-per-shell

## Overview
**Feature**: codex-guard-delim-brace-quote-per-shell / **SPEC.md**: `feature-docs/codex-guard-delim-brace-quote-per-shell/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/codex-guard-delim-brace-quote-per-shell/IMPLEMENTATION.md`

## Build Verification
- Command: none. `project.components.main.build_command` is empty, and the Python sources run as they are.
- Expected: not applicable.

## Test Verification
- Command (project test command): `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests`
- Command (guard suite): `python3 -m unittest tests.test_codex_hook_interactive_guard`
- Coverage target: not applicable, because no coverage tool is configured. Coverage is the CASES table, which runs against both copies, plus the structural and documentation tests.

### Test Scenarios from SPEC.md
TS1 to TS32 are the SPEC.md Test Scenarios rows. Each is a CASES row `(expected, label, command)`, built by SPEC.md's command-construction rule and run against both copies. TS33 to TS42 were added by this plan, for requirements that SPEC.md verifies only through its integration runs.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS1 | The reproduction: in a bash -c string, the terminator line is written as `${v:-"x"}`, then the launch follows | deny | Unit (CASES) |
| TS2 | bash -c: a line with the quote-removed form does not close the body | silent | Unit (CASES) |
| TS3 | bash -c keeps the single quotes of the range | deny | Unit (CASES) |
| TS4 | bash -c keeps the backslash of the range | deny | Unit (CASES) |
| TS5 | bash -c: a `}` inside double quotes does not close the range, and the range is registered as written | deny | Unit (CASES) |
| TS6 | bash -c: a nested `${ ... }` is registered as written | deny | Unit (CASES) |
| TS7 | bash -c: a `$( )` in the range is kept as written | deny | Unit (CASES) |
| TS8 | bash -c: a backslash-newline outside quotes in the range is dropped | deny | Unit (CASES) |
| TS9 | bash -c: a backslash-newline inside double quotes in the range is dropped, and the quotes stay | deny | Unit (CASES) |
| TS10 | bash -c: a quote before the range makes the whole word quote-removed | deny | Unit (CASES) |
| TS11 | bash -c: a quote after the range makes the whole word quote-removed | deny | Unit (CASES) |
| TS12 | bash -c: with a quote after the range, a line with the written range does not close the body | silent | Unit (CASES) |
| TS13 | bash -c: a double quote before the range also removes the range's single quotes | deny | Unit (CASES) |
| TS14 | bash -c: an unquoted `$'` in the range stays undecidable | silent | Unit (CASES) |
| TS15 | bash -c: `<<-` compares the written range after stripping leading tabs | deny | Unit (CASES) |
| TS16 | A suffixed bash reached through env reads in bash form | deny | Unit (CASES) |
| TS17 | bash --posix reads in bash form | deny | Unit (CASES) |
| TS18 | sh -c: a launch after the bash-form terminator is denied while the quote-removal reading is undecidable | deny | Unit (CASES) |
| TS19 | sh -c: a launch after the quote-removal terminator is denied while the bash-form reading is undecidable | deny | Unit (CASES) |
| TS20 | sh -c: a launch after the written terminator and before the quote-removed line | deny | Unit (CASES) |
| TS21 | sh -c: a launch after the quote-removed terminator and before the written line | deny | Unit (CASES) |
| TS22 | sh -c: a launch that is inside the body under both readings | silent | Unit (CASES) |
| TS23 | sh given with a path also reads both ways | deny | Unit (CASES) |
| TS24 | dash -c uses quote removal only, so a written line does not close the body | silent | Unit (CASES) |
| TS25 | dash -c: a launch after the quote-removed terminator | deny | Unit (CASES) |
| TS26 | ksh -c reads both ways: a launch after the written terminator | deny | Unit (CASES) |
| TS27 | ksh -c reads both ways: a launch after the quote-removed terminator | deny | Unit (CASES) |
| TS28 | zsh -c reading unchanged | silent | Unit (CASES) |
| TS29 | The hook command's own reading unchanged | silent | Unit (CASES) |
| TS30 | A bash -c string inside a zsh -c string reads in bash form | deny | Unit (CASES) |
| TS31 | A zsh -c string inside a bash -c string reads as zsh | silent | Unit (CASES) |
| TS32 | bash -c: a backslash-newline outside the range is dropped and counts as no quote | deny | Unit (CASES) |
| TS33 | (added by plan) `python3 -m unittest tests.test_codex_hook_interactive_guard` | Succeeds. Includes the CASES table on both copies, the pre-existing rows, TestNestedParseErrorContainment, TestNoRecursion, TestRereadFallback, TestNestedReadLimit, TestSharedQuotedUnitReader, TestSubstitutionSkipCallStructure, the time-bound tests and every documentation marker test | Integration |
| TS34 | (added by plan) `python3 -m unittest discover -s tests`, and the project test command | Both succeed | Integration |
| TS35 | (added by plan) The two guard copies are compared | Byte-identical (TestCopies) | Unit |
| TS36 | (added by plan) NESTED_READ_LIMIT for dual-read strings | A second-level sh-held string read under both readings counts once at its length: deny exactly at the limit, silent with one more character. A third-level string present in both readings counts each time it is walked. When the readings coincide, the third-level string counts once. | Unit (process) |
| TS37 | (added by plan) The test file's CASES rows that existed before this feature, compared with the base revision | No row is removed and no expected verdict changes | Review (diff) |
| TS38 | (added by plan) The import statements of both guard copies and of the test file | Standard-library modules only | Review |
| TS39 | (added by plan) The feature diff against the base revision, restricted to `.claude-plugin/plugin.json` files and `.claude-plugin/marketplace.json` | Empty | Review (diff) |
| TS40 | (added by plan) The module docstring (step 4's delimiter passage, step 7, step 9) and the docstrings of the changed components, read against FR1 to FR5 | They agree. The new per-holder marker test passes, and the existing marker tests pass unchanged. | Unit + Manual |
| TS41 | (added by plan) A first-level sh-held string longer than 100,000 characters, with many heredocs whose ranges differ between the readings | Answered within the 60-second timeout with exit status 0 and empty stderr. The launch after the last bash-form terminator is denied. | Unit (process) |
| TS42 | (added by plan) In-memory runs of the parse driver on an sh-held string with a differing delimiter, with one reading's parsers forced to fail | A forced `_Undecidable`, or a forced exception of any other class, in either reading leaves the other reading's commands in the result. When both readings fail with other exceptions, the exception leaves the driver. Coinciding forms build only one reading's parsers. Differing forms build both readings' parsers. | Unit (in-memory) |

## Code Quality Verification
- Format: none. `project.components.main.format_command` is empty.
- Static analysis: none configured. The structural tests in TS33 (no recursion, one try around the nested parse call, the shared-reader call structure) take its place.

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | The reproduction TS1 is denied | TS1 in TS33 |
| AC2 | bash -c registers the written range and drops backslash-newline as specified; `<<-`, suffixed, env and `--posix` bash behave the same | TS2 to TS9, TS15 to TS17, TS32 in TS33 |
| AC3 | A quote outside the range makes the whole word quote-removed | TS10 to TS13 in TS33 |
| AC4 | An unquoted `$'` in the range stays undecidable under bash | TS14 in TS33 |
| AC5 | sh and ksh are denied when either reading denies; silent when both keep the launch in the body | TS18 to TS23, TS26, TS27 in TS33; TS42 |
| AC6 | dash, zsh and the hook command readings are unchanged | TS24, TS25, TS28, TS29 in TS33 |
| AC7 | The direct holder decides the reading | TS30, TS31 in TS33 |
| AC8 | The copies are byte-identical and both unittest commands succeed | TS33, TS34, TS35 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS1, TS16, TS17, TS23 to TS31 (CASES on both copies) |
| FR2 | task0001 | TS1 to TS15, TS32 (CASES on both copies) |
| FR3 | task0001 | TS18 to TS23, TS26, TS27 (CASES); TS42 (in-memory combination) |
| FR4 | task0001 | TS33 (pre-existing CASES rows for the readings outside the delimiter position); TS37 |
| FR5 | task0001 | TS36 |
| FR6 | task0001 | TS33, TS34 |
| NFR1 | task0001 | TS35 |
| NFR2 | task0001 | TS41; the time-bound tests in TS33 |
| NFR3 | task0001 | TS33 |
| NFR4 | task0001 | TS40 |
| NFR5 | task0001 | TS37; TS33 |
| NFR6 | task0001 | TS38 |
| NFR7 | task0001 | TS39 |

## Manual Testing (E2E Not Possible)
- [ ] Read the module docstring's step 4 delimiter passage, step 7 and step 9 against FR1 to FR5. Check the holder table, the bash form's condition, the dual reading with deny-if-either, and that a string counts once (TS40).
- [ ] Run the reproduction from workflow.yaml's goal by hand against each copy. Pipe the PreToolUse JSON in on stdin, with the TS1 command in `tool_input.command`. Exactly one deny object comes back.

## Performance / Security Verification (if applicable)
- NFR2: a dual-read string at scale (TS41), plus the existing time-bound tests in TestMalformedAndDeepInput, TestCaseStatementsInASubstitution and TestArithmeticRereadBudget (TS33). All are answered within their timeouts.
- TM-1: the guard reads the delimiter range by the rule of the shell that directly holds the string. Checked by TS1 to TS32 passing on both copies. Under the bash form, the written terminator closes the body and the launch after it is denied. sh and ksh are denied when either reading denies.
- TM-2: the two readings are combined independently, and the second reading is skipped only on the D3 condition. Checked by TS42, and by TS18 and TS19, where one reading is undecidable and the other still denies.
- TM-3: a string gets at most two readings of at most two reads each, counts once at its length, and each nested walk counts again. Checked by TS36 and TS41.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| CASES rows (TS1 to TS32) | 32 | 32 | 0 | 0 |
| Integration runs (TS33, TS34) | 2 | 2 | 0 | 0 |
| Added unit tests (TS35, TS36, TS41, TS42) | 4 | 4 | 0 | 0 |
| Review checks (TS37, TS38, TS39) | 3 | 0 | 0 | 3 |
| Docstring alignment (TS40) | 1 | 1 | 0 | 1 |
| Manual reproduction | 1 | 0 | 0 | 1 |
| Security items (TM-1, TM-2, TM-3) | 3 | 3 | 0 | 0 |
| Performance item (NFR2) | 1 | 1 | 0 | 0 |
