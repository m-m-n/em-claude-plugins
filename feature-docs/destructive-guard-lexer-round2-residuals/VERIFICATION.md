# Verification Document: destructive-guard-lexer-round2-residuals

## Overview
**Feature**: destructive-guard-lexer-round2-residuals / **SPEC.md**: `feature-docs/destructive-guard-lexer-round2-residuals/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/destructive-guard-lexer-round2-residuals/IMPLEMENTATION.md`

This document covers the integrated verification after all four tasks are
merged. Task-level acceptance criteria live in `tasks/task0001.md` to
`tasks/task0004.md`.

## Build Verification
- Command: none (workflow.yaml `project.components.main.build_command` is empty; the hook is a Python script with no build step).
- Expected: not applicable.

## Test Verification
- Command (project test suite): `python3 -m unittest discover -s tests`
- Command (lexer agreement suite): `python3 -m unittest tests.test_destructive_guard_lexer_agreement`
- Command (case table runner): `python3 em-workflow/hooks/tests/run-destructive-guard.py`
- Expected: every command exits 0 with no failure or error.
- Coverage target: not measured (no coverage tooling is configured for this project); completeness is judged by the scenarios below.

### Test Scenarios from SPEC.md
Inputs use the case table's JSON string notation (`\n` is a newline). TAIL
is `\nrm -rf /home/sakura/valuable\n2`.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | `for ((i=0;i<1;i++)) { ((1<<2)); }`, `for ((;0;)){ ((1<<2)); }`, `if :; then for ((;0;)) { ((1<<2)); }; fi`, each + TAIL (SPEC TS1) | deny without and with `CLAUDE_BATCH=1`; the body `((1<<2))` is an arithmetic-command region, no here-document operator; the forms are in the case table and `COMMAND_POSITION_FORMS` | Unit + case runner |
| TS-2 | `time -- ((1<<2))`, `time -p -- ((1<<2))`, `time -- ! ((1<<2))`, each + TAIL (SPEC TS2) | deny in both modes; `((1<<2))` is an arithmetic-command region; the forms are in the case table and `COMMAND_POSITION_FORMS` | Unit + case runner |
| TS-3 | `a[1<<2]=x` + TAIL (SPEC TS3) | deny in both modes; no here-document operator; the subscript lies inside one region | Unit + case runner |
| TS-4 | `cat <<END-X\nbody\nEND-X\nrm -rf /home/sakura/valuable\nEND`, `cat <<E.X\nbody\nE.X\nrm -rf /home/sakura/valuable\nE`, `cat <<E\\X\nbody\nEX\nrm -rf /home/sakura/valuable\nE` (SPEC TS4) | deny in both modes; one operator each with delimiter `END-X` / `E.X` / `EX`, quoted false / false / true, body `body\n` | Unit + case runner |
| TS-5 | L28 and L100 (`x=$((echo N) \| wc -c)` lines, N = 0..27 and 0..99) and S40 (`((cd /tmp/aN && ls) \|\| echo no)`, N = 0..39) (SPEC TS5) | allow in both modes (no scan-budget ask) | Case runner + unit |
| TS-6 | k = 200 and k = 400 lines of each FR5 unit (SPEC TS6) | 400-line work ≤ 2.5 × 200-line work + 100 and ≤ `LEX_WORK_FACTOR` × length + 1024 | Unit (linearity) |
| TS-7 | Whole existing suites (base: case runner 628/628, lexer agreement 78 tests) plus everything added (SPEC TS7) | all pass; existing linearity, budget, determinism and module-contract tests unchanged and passing | Regression |
| TS-8 | `cat a[1] <<EOF\nhi\nEOF` (SPEC AC6) | one real operator, delimiter `EOF`, unquoted, body `hi\n`, no region, allow; `echo a[1<<2]` still registers its `<<` | Unit |
| TS-9 | Fail-safe readings: unclosed subscript `a[1<<2\nrm -rf /home/sakura/valuable\n2`; delimiter with no word before the newline; delimiter word holding `$(` or a backtick followed by a destructive line; quote not closed on the operator's line (SPEC FR3 / FR4 / NFR6) | no here-document body is taken; the destructive line gets a decision other than allow (the open-quote form is pinned lexically only) | Unit |
| TS-10 | Map equivalence for the non-adjacent-close re-reading over the case table and fixed forms, plus nested, double-quoted and here-document-pending edge forms (SPEC FR5 edge cases) | regions, here-document operators, candidates, unopened openers and tail start equal the whole-text-restart reading; identical map after a cache clear | Unit |
| TS-11 | Case placement and order (SPEC AC4, FR6, FR8) | no label at index < 627 carries 453963d025537b11, 681fab61e1d9ff2c, 9381769d7116fab2 or 29bbf9032dd762a0; every new case sits at index ≥ 627; the first 627 entries are unchanged; in each task's history the case-adding commit precedes its hook-changing commits | Unit + history check |
| TS-12 | ~60 KB input of `x=$((echo N) \| wc -c)` lines (SPEC NFR2) | allow within the 10-second hook bound | Integration (timed hook run) |
| TS-13 | Work bound exceeded on an input with non-adjacent closes (SPEC NFR3) | budget-exceeded condition raised; decision ask (deny with `CLAUDE_BATCH=1`), never allow | Unit (in-process) |

## Code Quality Verification
- Format: none configured (workflow.yaml `format_command` is empty).
- Static analysis: none configured. `TestModuleContract` checks that the hook and the agreement test import only the standard library and that the lexer reads no file and evaluates nothing (NFR5).

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | The 10 attack forms of round2.yaml deny in normal runs and with `CLAUDE_BATCH=1` | TS-1, TS-2, TS-3, TS-4 |
| AC2 | L28, L100 and S40 are allowed | TS-5 |
| AC3 | A test pins work proportional to input length for k repeated `$((cmd) ...)` | TS-6 |
| AC4 | New cases were added in a commit before the fix | TS-11 (history: `git log` of the integration branch shows, per task, the case-table commit before the hook commits) |
| AC5 | No existing deny / ask case removed; both suites pass | TS-7, TS-11; `git diff` of the case table against the feature base shows additions only after the 627th entry |
| AC6 | `cat a[1] <<EOF\nhi\nEOF` keeps its real operator and stays allow | TS-8 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1 |
| FR2 | task0001 | TS-2 |
| FR3 | task0002 | TS-3, TS-8, TS-9 |
| FR4 | task0003 | TS-4, TS-9 |
| FR5 | task0004 | TS-5, TS-6, TS-10 |
| FR6 | task0001, task0002, task0003, task0004 | TS-1, TS-2, TS-3, TS-4, TS-5, TS-11 |
| FR7 | task0001, task0004 | TS-1, TS-2, TS-6, TS-11 |
| FR8 | task0001, task0002, task0003, task0004 | TS-7, TS-11 |
| NFR1 | task0002, task0003, task0004 | TS-6 |
| NFR2 | task0004 | TS-7, TS-12 |
| NFR3 | task0004 | TS-7, TS-13 |
| NFR4 | task0004 | TS-7, TS-10 |
| NFR5 | task0001, task0002, task0003, task0004 | TS-7 |
| NFR6 | task0001, task0002, task0003 | TS-8, TS-9 |

## E2E Testing
The project's E2E command (workflow.yaml `e2e_test_command`) runs every
case-table entry through the hook's stdin / stdout contract.
- [ ] `python3 em-workflow/hooks/tests/run-destructive-guard.py` passes every case, including the blocks the four tasks appended.

## Manual Testing (E2E Not Possible)
- [ ] bash 5.3 spot check: for each of the 10 attack forms with `rm` replaced by `echo`, bash 5.3 executes the line after the first, so each deny case corresponds to a real bypass; the edge forms the tasks added as cases are listed with their bash 5.3 outcome in the task reports.

## Performance / Security Verification (if applicable)
- NFR1: `lex_shell()` work ≤ `LEX_WORK_FACTOR` × input length + 1024 for the FR5 forms and the existing unclosed-opener / rework forms; doubling the input keeps work ≤ 2.5 × + 100 (TS-6, TS-7).
- NFR2: one hook evaluation of ~60 KB finishes within 10 seconds (TS-12, TS-7).
- NFR3: exceeding the work bound gives ask (deny in batch), never allow (TS-13, TS-7).
- TM-1: `{` after a closer and `--` after `time` / `time -p` keep the command position, so `((...))` there registers no here-document operator — checked by TS-1 and TS-2 (lexical expectation plus deny in both modes).
- TM-2: an assignment-word subscript is read to its matching `]` with no operator inside, and an unclosed subscript is settled so following lines stay inspected — checked by TS-3 and TS-9.
- TM-3: the delimiter is the quote-removed whole word, close lines accept it, and an unreadable delimiter takes no body — checked by TS-4 and TS-9.
- TM-4: non-adjacent closes are re-read within the linear bound and a bound overflow never becomes allow — checked by TS-5, TS-6, TS-12 and TS-13.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS-1 to TS-13) | 13 | 13 | 0 | 0 |
| SPEC success criteria (AC1 to AC6) | 6 | 6 | 0 | 0 |
| E2E (case table runner) | 1 | 0 | 1 | 0 |
| Manual (bash 5.3 spot check) | 1 | 0 | 0 | 1 |
| Performance (NFR1 to NFR3) | 3 | 3 | 0 | 0 |
| Security (TM-1 to TM-4) | 4 | 4 | 0 | 0 |
