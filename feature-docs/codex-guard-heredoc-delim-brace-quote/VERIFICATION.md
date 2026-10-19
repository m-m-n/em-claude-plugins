# Verification Document: codex-guard-heredoc-delim-brace-quote

## Overview
**Feature**: codex-guard-heredoc-delim-brace-quote / **SPEC.md**: `feature-docs/codex-guard-heredoc-delim-brace-quote/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/codex-guard-heredoc-delim-brace-quote/IMPLEMENTATION.md`

## Build Verification
- Command: none (workflow.yaml project.components.main.build_command is empty; the guard is a Python script loaded by the test run, so a syntax or import error surfaces as a failure of TS35 / TS36)
- Expected: not applicable

## Test Verification
- Command: `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests`
- Coverage target: not measured (no coverage tooling configured); every scenario TS1 to TS34 is one CASES row run against both guard copies

### Test Scenarios from SPEC.md
Scenario IDs keep SPEC.md's TSn form so they string-match workflow.yaml `requirements.*.tests`. TS1 to TS34 are SPEC.md's Unit Tests (each one CASES row, command = the scenario's line array joined with newlines). TS35 to TS42 are drawn from SPEC.md's Integration Tests, Performance Tests and AC8.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS1 | Reproduction inside `zsh -c`: delimiter `${v:-"x"}`, body ends at `${v:-x}`, launch after it | deny | Unit (CASES) |
| TS2 | Delimiter `${v:-"x"}`: the unremoved line `${v:-"x"}` does not end the body; launch inside the body | silent | Unit (CASES) |
| TS3 | Delimiter `${v:-'x'}` ends at `${v:-x}`; launch after it | deny | Unit (CASES) |
| TS4 | Delimiter `${v:-\x}` ends at `${v:-x}`; launch after it | deny | Unit (CASES) |
| TS5 | Delimiter `${v:-"x"y}` ends at `${v:-xy}`; launch after it | deny | Unit (CASES) |
| TS6 | Delimiter `${v#"x"}` ends at `${v#x}`; launch after it | deny | Unit (CASES) |
| TS7 | Delimiter `foo${v:-"x"}bar` ends at `foo${v:-x}bar`; launch after it | deny | Unit (CASES) |
| TS8 | `<<-` delimiter `${v:-"x"}` ends at a tab-prefixed `${v:-x}`; launch after it | deny | Unit (CASES) |
| TS9 | Delimiter `${v:-"a}b"}` ends at `${v:-a}b}`; launch after it | deny | Unit (CASES) |
| TS10 | Delimiter `${v:-'a}b'}` ends at `${v:-a}b}`; launch after it | deny | Unit (CASES) |
| TS11 | Delimiter `${v:-\}}` ends at `${v:-}}`; launch after it | deny | Unit (CASES) |
| TS12 | Delimiter `${a:-${b:-"x"}}` ends at `${a:-${b:-x}}`; launch after it | deny | Unit (CASES) |
| TS13 | Delimiter `${v:-$(echo "x")}` ends at the line written the same; launch after it | deny | Unit (CASES) |
| TS14 | Delimiter `${v:-$(echo "x")}`: line `${v:-$(echo x)}` does not end the body; launch inside the body | silent | Unit (CASES) |
| TS15 | Delimiter `${v:-$(echo "}")}` ends at the line written the same; launch after it | deny | Unit (CASES) |
| TS16 | Delimiter `${v:-"$'"}` ends at `${v:-$'}`; launch after it | deny | Unit (CASES) |
| TS17 | Delimiter `${v:-\$'x'}` ends at `${v:-$x}`; launch after it | deny | Unit (CASES) |
| TS18 | Delimiter `${v:-$'x'}` is undecidable; no checkpoint before it | silent | Unit (CASES) |
| TS19 | Delimiter `${v:-$"x"}` is undecidable; no checkpoint before it | silent | Unit (CASES) |
| TS20 | Delimiter `${v:-"a}` with the quote open to the end of text is undecidable | silent | Unit (CASES) |
| TS21 | Delimiter `$'x'` is undecidable | silent | Unit (CASES) |
| TS22 | Delimiter `$"x"` is undecidable | silent | Unit (CASES) |
| TS23 | Delimiter `foo$'x'` (mid-word) is undecidable | silent | Unit (CASES) |
| TS24 | Delimiter `"$'x'"` ends at `$'x'`; launch after it | deny | Unit (CASES) |
| TS25 | Delimiter `\$'x'` ends at `$x`; launch after it | deny | Unit (CASES) |
| TS26 | Launch on the line before an undecidable `${v:-$'x'}` delimiter | deny | Unit (CASES) |
| TS27 | Launch on the line before an undecidable `$"x"` delimiter | deny | Unit (CASES) |
| TS28 | Launch on the same line as an undecidable `$'x'` delimiter | silent | Unit (CASES) |
| TS29 | Non-delimiter `${v:-"x"}` followed by a launch | deny | Unit (CASES) |
| TS30 | `<<<` target `${v:-$'x'}` followed by a launch | deny | Unit (CASES) |
| TS31 | `<<<` target `$'x'` followed by a launch | deny | Unit (CASES) |
| TS32 | Non-delimiter `$"x"` followed by a launch | deny | Unit (CASES) |
| TS33 | Delimiter `"${v:-x}"` ends at `${v:-x}`; launch after it | deny | Unit (CASES) |
| TS34 | Delimiter with a backquote inside `${ ... }` ends at the line written the same; launch after it | deny | Unit (CASES) |
| TS35 | `python3 -m unittest tests.test_codex_hook_interactive_guard` with CASES holding the TS1 to TS34 rows, run against both copies | exit 0 | Integration |
| TS36 | Project test command `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests` | exit 0 | Integration |
| TS37 | Byte comparison of `em-workflow/scripts/codex-hook-interactive-guard.py` and `em-review/scripts/codex-hook-interactive-guard.py` | no difference | Static |
| TS38 | Existing length-cap and timing tests of the test module | pass, and unedited relative to the base revision | Performance |
| TS39 | Docstring marker tests (`DELIMITER_RANGE_MARKERS`, `CHECKPOINT_MARKERS`, `CHECKPOINT_PASSAGES` and the others) | pass, and unedited relative to the base revision | Unit + diff |
| TS40 | Diff of the CASES table against the base revision | every pre-existing row present with the same verdict, label and command; rows only added | Static (diff) |
| TS41 | Imports of both guard copies and the test module | standard-library modules only | Static |
| TS42 | Diff of the em-workflow and em-review plugin manifests and the root marketplace file against the base revision | no change | Static (diff) |

## Code Quality Verification
- Format: not configured (workflow.yaml format_command is empty) / Static analysis: not configured

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | Reproduction TS1 is deny | TS1 |
| AC2 | Delimiter-position `${ ... }` with quotes and backslashes removed ends the body; the unremoved line does not; `<<-` strips leading tabs; text outside the range is concatenated | TS2 to TS8 |
| AC3 | Delimiter-position `${ ... }` does not close at quoted, escaped, nested or substitution-internal `}`; `$( ... )` stays as written | TS9 to TS15, TS34 |
| AC4 | Unquoted `$'` / `$"` inside `${ ... }` and an undeterminable close are undecidable; double-quoted `$'` and escaped `$` are not | TS16 to TS20 |
| AC5 | Unquoted `$'` / `$"` outside `${ ... }`, mid-word included, are undecidable; double-quoted and escaped forms keep the current reading | TS21 to TS25 |
| AC6 | Launch before the checkpoint of an undecidable delimiter is deny; same-line launch is silent | TS26 to TS28 |
| AC7 | Non-delimiter readings, `<<<` targets and double-quoted `${ ... }` in the delimiter are unchanged | TS29 to TS33 |
| AC8 | Copies byte-identical; both unittest commands succeed | TS35 to TS41 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS1 to TS15, TS34 (CASES) |
| FR2 | task0001 | TS9 to TS20, TS34 (CASES) |
| FR3 | task0001 | TS16 to TS20 (CASES) |
| FR4 | task0001 | TS21 to TS25 (CASES) |
| FR5 | task0001 | TS29 to TS33 (CASES) |
| FR6 | task0001 | TS26 to TS28 (CASES) |
| FR7 | task0001 | TS35, TS36 |
| NFR1 | task0001 | TS37 |
| NFR2 | task0001 | TS38, manual linearity review |
| NFR3 | task0001 | TS39, manual docstring review |
| NFR4 | task0001 | TS40 |
| NFR5 | task0001 | TS41 |
| NFR6 | task0001 | TS42 |

## Manual Testing (E2E Not Possible)
- [ ] The module docstring of the guard describes the delimiter-position `${ ... }` close search, its quote removal and the undecidable delimiter forms (FR1 to FR6), and every newly written `-> no output` statement sits inside the section that states the checkpoint rule (NFR3).
- [ ] The delimiter-position scan examines each character of the `${ ... }` range a bounded number of times regardless of nesting depth, skipping a nested `$( ... )` once without re-reading it (NFR2, TM-3).

## Performance / Security Verification (if applicable)
- NFR2: existing length-cap and timing tests pass unedited (TS38); linearity review (Manual Testing)
- TM-1: zsh-equivalent close search and `_remove_range_quotes` quote removal for a delimiter-position `${ ... }` — checked by the CASES rows TS1 to TS15 and TS34 (deny where zsh's terminator precedes the launch; silent where the unremoved line does not end the body)
- TM-2: delimiter forms whose zsh reading is not reproduced raise the existing undecidable outcome instead of a guessed delimiter — checked by the CASES rows TS16 to TS28 (silent without a checkpoint, deny for a launch before the checkpoint, no false deny for TS21 to TS23)
- TM-3: linear-time delimiter-position scan — checked by TS38 and the linearity review in Manual Testing

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios, CASES rows (TS1 to TS34) | 34 | 34 | 0 | 0 |
| Integration, performance and static checks (TS35 to TS42) | 8 | 8 | 0 | 0 |
| Success criteria (AC1 to AC8) | 8 | 8 | 0 | 0 |
| Manual review (docstring, linearity) | 2 | 0 | 0 | 2 |
| Security (TM-1, TM-2, TM-3) | 3 | 3 | 0 | 0 |
| Total | 55 | 53 | 0 | 2 |
