# Verification Document: codex-guard-heredoc-delim-brace-case

## Overview
**Feature**: codex-guard-heredoc-delim-brace-case / **SPEC.md**: `feature-docs/codex-guard-heredoc-delim-brace-case/SPEC.md` / **IMPLEMENTATION.md**: not written (reduced tier; one task, so no file is shared between tasks) / **THREAT-MODEL.md**: `feature-docs/codex-guard-heredoc-delim-brace-case/THREAT-MODEL.md`

## Build Verification
- Command: none (`build_command` is empty in workflow.yaml)
- Expected: not applicable

## Test Verification
- Command: `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests`
- Focused command: `python3 -m unittest tests.test_codex_hook_interactive_guard`
- Expected: exit code 0, no failures or errors
- Coverage target: not measured. The project has no coverage tool and uses
  the standard library only; coverage comes from the scenarios, each of which
  runs against both copies.

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS1 | Reproduction: `zsh -c` heredoc whose delimiter `${...}` holds a case-statement `$( )` with a double-quoted word, terminator written the same way, then `python3 -i` | `deny` on both copies | Unit (CASES) |
| TS2 | Same as TS1 at the top level (no `zsh -c`) | `deny` on both copies | Unit (CASES) |
| TS3 | Same delimiter; a line with the quotes removed, then `python3 -i`, then the line as written | `silent` (the quote-removed line does not close the body) | Unit (CASES) |
| TS4 | Delimiter `${...}` whose case body holds `echo "}"`; terminator written the same way; then `python3 -i` | `deny` (the `}` inside the quotes does not close `${...}`) | Unit (CASES) |
| TS5 | Case pattern with a leading `(` inside the delimiter `${...}`; terminator as written; then `python3 -i` | `deny` | Unit (CASES) |
| TS6 | Delimiter `${v:-$((1+2))}`; terminator as written; then `python3 -i` | `deny` | Unit (CASES) |
| TS7 | `<<-` with the TS2 delimiter; terminator line led by one tab; then `python3 -i` | `deny` | Unit (CASES) |
| TS8 | Delimiter `${...}` holding a case statement with no closing `esac`; then `python3 -i` | `silent` (undecidable) | Unit (CASES) |
| TS9 | `python3 -i`, then a heredoc whose delimiter `${...}` holds an undecidable case statement | `deny` (the launch before the checkpoint is judged) | Unit (CASES) |
| TS10 | Scale: an input over 100,000 characters of heredocs whose delimiter `${...}` holds a case-statement `$( )` with a quoted word, each closed by its true terminator, then `python3 -i` | `deny` on both copies within the TestMalformedAndDeepInput timeout, exit 0, empty standard error | Unit (performance) |
| TS11 | Every `CASES` row that existed before the feature, including the `${...}` delimiter rows of codex-guard-heredoc-delim-brace-quote and the parenthesised-range rows, unchanged | Each row passes on both copies; none removed or edited | Integration |
| TS12 | TestSharedQuotedUnitReader, TestSubstitutionSkipCallStructure, TestNoRecursion, unchanged | All pass on both copies | Integration (structure) |
| TS13 | TestCopies | Both copies exist and are byte-identical | Integration |
| TS14 | Documentation: the new documentation test, plus every existing documentation test unchanged | The stale `_read_quoted_unit` / `_skip_substitution` premises are gone, the four docstrings name the new reading, and every existing marker is present | Unit (documentation) |

TS1 to TS9 are the SPEC.md Test Scenarios. TS11 to TS13 number the SPEC.md
Integration Tests (AC3, AC4, AC5). TS10 verifies NFR1 and TS14 verifies the
docstring half of FR5.

## Code Quality Verification
- Format: none (`format_command` is empty in workflow.yaml)
- Static analysis: none configured
- Standard library only: neither copy adds an import outside the Python
  standard library (checked by reading the diff)

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | The reproduction command gives deny on both copies | TS1 |
| AC2 | TS1 to TS9 are in `CASES` and `python3 -m unittest tests.test_codex_hook_interactive_guard` passes | TS1 to TS9; focused command |
| AC3 | Every existing `CASES` row passes unchanged | TS11 |
| AC4 | The existing structure tests pass unchanged | TS12 |
| AC5 | The two copies are byte-identical | TS13 |
| Unit run | `python3 -m unittest tests.test_codex_hook_interactive_guard` passes | Focused command |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS1 to TS7 |
| FR2 | task0001 | TS1 to TS9 |
| FR3 | task0001 | TS11 |
| FR4 | task0001 | TS1 to TS9 present in `CASES` and run against both copies |
| FR5 | task0001 | TS13, TS14; manual docstring read below |
| NFR1 | task0001 | TS10 |
| NFR2 | task0001 | TS12 |
| NFR3 | task0001 | TS8, TS11; standard-library check above |

## Manual Testing (E2E Not Possible)
- [ ] Read the module docstring and the docstrings of `_remove_range_quotes`,
  `_read_quoted_unit` and `_skip_substitution` in the em-workflow copy.
  Confirm they describe the FR1 to FR3 reading: the braced range uses the
  case-aware skip through the shared reader, the parenthesised range and a
  direct `$( )` keep the paren scan, and the undecidable cases are stated.
  Marker tests cannot judge whether the description is accurate.

## Performance / Security Verification (if applicable)
- NFR1 (linear time): TS10 — the scale input is answered with deny within
  the TestMalformedAndDeepInput timeout on both copies.
- TM-1: a delimiter's `${ ... }` range skips an unquoted `$(` / `$((` with the
  case-aware skip and keeps it as written. Checked by TS1 to TS7 giving their
  verdicts on both copies and by TS11 (the other readings are unchanged).
- TM-2: an unlocatable close in that range ends only in the undecidable
  signal, under the checkpoint rule. Checked by TS8 (`silent`) and TS9 (the
  earlier launch is `deny`).
- TM-3: each `$( )` is skipped once, with no recursion or call cycle, and the
  skip is called only from the shared reader. Checked by TS10 and TS12.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios (SPEC.md TS1 to TS9) | 9 | 9 | 0 | 0 |
| Added scenarios (TS10 to TS14) | 5 | 5 | 0 | 0 |
| Success criteria | 6 | 6 | 0 | 0 |
| Code quality (standard library only) | 1 | 0 | 0 | 1 |
| Docstring accuracy | 1 | 0 | 0 | 1 |
| Performance (NFR1) | 1 | 1 | 0 | 0 |
| Security (TM-1, TM-2, TM-3) | 3 | 3 | 0 | 0 |
