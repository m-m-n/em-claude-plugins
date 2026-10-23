# Verification Document: codex-guard-delim-subst-undecidable

## Overview
**Feature**: codex-guard-delim-subst-undecidable / **SPEC.md**: `feature-docs/codex-guard-delim-subst-undecidable/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/codex-guard-delim-subst-undecidable/IMPLEMENTATION.md`

Scenario IDs TS1-TS15 keep SPEC.md's numbering literally; TS16-TS22 continue
it for the integrated checks.

## Build Verification
- Command: none (`project.components.main.build_command` is empty; the scripts are interpreted).
- Expected: not applicable.

## Test Verification
- Command: `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests`
- Focused command for this feature: `python3 -m unittest tests.test_codex_hook_interactive_guard`
- Coverage target: not measured (no coverage tool is configured for this project).

### Test Scenarios from SPEC.md
Commands are written as SPEC.md writes them (Python expressions); each CASES row runs against both script copies. "silent" means the guard prints nothing.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS1 | Reproduction (SPEC AC-1): `zsh -c` with an `if false; then` block whose heredoc delimiter is `${v:-$(echo <<EOF)}`, the matching terminator line, `fi`, then `python3 -i` | deny on both copies | Unit (CASES) |
| TS2 | `cat` with delimiter `${v:-$(echo <<EOF)}`, matching terminator line, then `python3 -i` | deny on both copies | Unit (CASES) |
| TS3 | Same delimiter as TS2, terminator line `EOF` only, then `python3 -i` | silent (the body does not close) | Unit (CASES) |
| TS4 | Delimiter `${v:-$( ((1 << 2)) )}`, matching terminator line, then `python3 -i` | deny on both copies | Unit (CASES) |
| TS5 | Same delimiter as TS4, short terminator line `2)) )}`, then `python3 -i` | silent (the body does not close) | Unit (CASES) |
| TS6 | Delimiter `${v:-$(for ((i=0;i<1<<2;i++)) do :; done)}`, matching terminator line, then `python3 -i` | deny on both copies | Unit (CASES) |
| TS7 | Delimiter `${v:-$(echo foo(case x))}`, matching terminator line, then `python3 -i` | deny on both copies | Unit (CASES) |
| TS8 | Same delimiter as TS7, short terminator line `x))}`, then `python3 -i` | silent (the body does not close) | Unit (CASES) |
| TS9 | Delimiter `${v:-$(echo foo(a;b))}`, matching terminator line, then `python3 -i` | deny on both copies | Unit (CASES) |
| TS10 | Regression (SPEC AC-4): `echo "$(echo foo(a;b))"; python3 -i` | deny on both copies (unchanged) | Unit (CASES) |
| TS11 | Regression (SPEC AC-4): `echo "$( ((echo a) ) )"; python3 -i` | deny on both copies (unchanged; `((` re-read as nested subshells) | Unit (CASES) |
| TS12 | Same-line heredoc in a double-quoted substitution: `echo "$(cat <<EOF)"; python3 -i` | deny on both copies | Unit (CASES) |
| TS13 | Newline inside a word parenthesis: delimiter split across lines as `${v:-$(echo *(e:true` / `:N))}`, matching terminator lines, then `python3 -i`; if the zsh 5.9 measurement during implementation disagrees, replaced by the same-line `*(#qN)` form `${v:-$(echo *(#qN))}` | deny on both copies (for whichever form the task report names) | Unit (CASES) |
| TS14 | Existing CASES row near line 967: heredoc inside a case item body within a substitution | silent (row kept unchanged) | Unit (CASES) |
| TS15 | Heredoc with a body inside a substitution: `echo "$(cat <<EOF\nbody\nEOF\n)"; python3 -i` | silent (undecidable, as today) | Unit (CASES) |
| TS16 | SPEC AC-1 through the real entry point: the TS1 command string placed in `tool_input.command` of a JSON object on each copy's stdin, each copy run as its own process | both copies print a deny decision | Integration |
| TS17 | Re-read cap: a generated input whose command-position `((` forms do not close as `))` and whose fallback re-reads exceed the skip's named limit | silent; finishes within the existing large-input time budget; no recursion error | Unit |
| TS18 | Copy identity: `cmp em-workflow/scripts/codex-hook-interactive-guard.py em-review/scripts/codex-hook-interactive-guard.py` | exit code 0 | Automated check |
| TS19 | Full project test command (SPEC AC-8), including the no-recursion test, the large-input timing test, the shared-reader test, the call-structure test and the documentation test | exit code 0 | Unit/Integration |
| TS20 | CASES retention: the diff of `tests/test_codex_hook_interactive_guard.py` from `workflow.implement.base_commit` to the integration HEAD removes no CASES row and changes no existing row's verdict | no removed or re-verdicted row | Automated check |
| TS21 | Version untouched: `git diff --name-only` from `workflow.implement.base_commit` to the integration HEAD lists neither `em-workflow/.claude-plugin/plugin.json`, `em-review/.claude-plugin/plugin.json` nor `.claude-plugin/marketplace.json` | none of the three listed | Automated check |
| TS22 | Docstring: the shared substitution skip's docstring describes the FR1-FR3 readings, keeps "a heredoc anywhere in the chunk (item bodies included)" for heredocs inside a case statement, and has no wording that a heredoc is always undecidable | all three hold; the documentation test passes | Manual + Unit |

## Code Quality Verification
- Format: none configured (`format_command` is empty).
- Static analysis: none configured.

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | Reproduction string on stdin gets deny from both copies | TS1, TS16 |
| AC-2 | `$( ((1 << 2)) )` and `$(for ((...)) do :; done)` delimiters get deny from both copies | TS4, TS6 |
| AC-3 | `$(echo foo(case x))` and `$(echo foo(a;b))` delimiters get deny from both copies | TS7, TS9 |
| AC-4 | `echo "$(echo foo(a;b))"; python3 -i` and `echo "$( ((echo a) ) )"; python3 -i` stay deny | TS10, TS11 |
| AC-5 | The two copies are byte-identical | TS18 |
| AC-6 | SPEC.md records the zsh 5.9 measurements | Manual: SPEC.md has the "zsh 5.9 Measurements" section with items 1-9 |
| AC-7 | The Test Scenarios rows are in CASES and run against both copies | TS1-TS15 present in CASES; TS19 |
| AC-8 | The project test command passes | TS19 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS1, TS2, TS3, TS12, TS14, TS15, TS16 |
| FR2 | task0001 | TS4, TS5, TS6, TS11, TS17 |
| FR3 | task0001 | TS7, TS8, TS9, TS10, TS13 |
| FR4 | task0001 | TS18 |
| FR5 | task0001 | TS19, TS20 |
| FR6 | task0001 | TS19, TS22 |
| NFR1 | task0001 | TS17, TS19 |
| NFR2 | task0001 | TS19 |
| NFR3 | task0001 | TS10, TS11, TS14, TS15, TS20 |
| NFR4 | task0001 | TS21 |

## Manual Testing (E2E Not Possible)
- [ ] AC-6: SPEC.md's "zsh 5.9 Measurements" section is present and lists measurements 1-9.
- [ ] TS13: the task report states whether the line-split form or the same-line `*(#qN)` form was used, and the zsh 5.9 observation behind that choice.
- [ ] TS22: read the shared substitution skip's docstring against the three conditions in TS22.

## Performance / Security Verification
- NFR1: linear time — TS17 and the large-input timing test in TS19 finish within their existing budgets; the no-recursion test passes.
- TM-1: the shared skip reads same-line `<<`, command-position `((` and word parentheses to zsh's delimiter end while case-internal and newline-followed `<<` stay undecidable, in both copies — checked by TS1-TS16 and TS18 (deny rows deny, silent rows silent, copies identical).
- TM-2: one fallback re-read per `((` with a total re-read cap that yields undecidable, explicit stack only — checked by TS17 (silent, within the time budget, no recursion error) and by the no-recursion and large-input timing tests in TS19.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios (CASES rows) | 15 (TS1-TS15) | 15 | 0 | 0 |
| Integration / generated-input tests | 2 (TS16, TS17) | 2 | 0 | 0 |
| Repository checks | 4 (TS18, TS19, TS20, TS21) | 4 | 0 | 0 |
| Docstring check | 1 (TS22) | 1 (documentation test) | 0 | 1 |
| Success criteria | 8 (AC-1 to AC-8) | 7 | 0 | 1 (AC-6) |
| Security mitigations | 2 (TM-1, TM-2) | 2 | 0 | 0 |
| Performance | 1 (NFR1) | 1 | 0 | 0 |
