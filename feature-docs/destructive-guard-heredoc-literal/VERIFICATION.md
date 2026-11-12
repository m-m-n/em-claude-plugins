# Verification Document: destructive-guard-heredoc-literal

## Overview
**Feature**: destructive-guard-heredoc-literal / **SPEC.md**: `feature-docs/destructive-guard-heredoc-literal/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/destructive-guard-heredoc-literal/IMPLEMENTATION.md` / **THREAT-MODEL.md**: `feature-docs/destructive-guard-heredoc-literal/THREAT-MODEL.md`

## Build Verification
- Command: none. `project.components.main.build_command` is empty; the changed files are a Python hook script and a JSON case file, which are not built.
- Expected: not applicable.

## Test Verification
- Command: `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests`
- Expected: exit code 0. The runner's last line is `N/N passed`, with both numbers equal to the number of cases in `em-workflow/hooks/tests/destructive-guard-cases.json` plus one (the unattended-demotion check), and no line carries a `[TIMEOUT` marker.
- Coverage target: not applicable. The expectation suite is case-based; every case must pass.

The commands of the cases are given line by line in `feature-docs/destructive-guard-heredoc-literal/tasks/task0001.md` (TS-1 to TS-15 and TS-17 to TS-27) and `feature-docs/destructive-guard-heredoc-literal/tasks/task0002.md` (TS-28 to TS-31 and TS-33 to TS-44), each under Design, Test cases. "Unchanged guard's decision" below means the decision `em-workflow/hooks/destructive-guard.py` at `workflow.implement.base_commit` returns for the same command. "The assignment form" below is a first statement, then `x="$(python3 <<'PY'` with a body that prints a subscript holding `$(git branch -D example)`, closed by `PY` and `)"`.

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Python heredoc, quoted delimiter, double-quoted literal holding a backtick `git branch -D example` | Runner `ok`, decision `allow` (FR1, FR2) | Integration (expectation suite) |
| TS-2 | `python3 -` heredoc writing an audit record whose literal quotes `git branch -D example` and `rm -rf /home/user/valuable` | Runner `ok`, decision `allow` (FR1, FR2) | Integration (expectation suite) |
| TS-3 | Single-quoted literal holding `$(git reset --hard HEAD)` | Runner `ok`, decision `allow` (FR1, FR2) | Integration (expectation suite) |
| TS-4 | Triple-quoted literal spanning lines, with a `git reset --hard HEAD` line inside | Runner `ok`, decision `allow` (FR1, FR3) | Integration (expectation suite) |
| TS-5 | `python3.12` heredoc with `r'...'` and `b"..."` literals holding backtick commands | Runner `ok`, decision `allow` (FR1, FR2) | Integration (expectation suite) |
| TS-6 | A comment holding an apostrophe, then a literal holding a backtick command | Runner `ok`, decision `allow` (FR1, FR3) | Integration (expectation suite) |
| TS-7 | Unquoted delimiter `<<PY`, literal holding `$(git branch -D example)` | Runner `ok`, decision `deny` (FR5) | Integration (expectation suite) |
| TS-8 | Unquoted delimiter `<<PY`, literal holding a backtick `git branch -D example` | Runner `ok`, decision `deny` (FR5) | Integration (expectation suite) |
| TS-9 | Python heredoc piped to `bash`: the print form (prints `git reset --hard HEAD`) and the probe form (a literal holding a backtick command) | Runner `ok` for both; the print form is `allow`, the unchanged guard's decision; the probe form is `deny` (FR2, SPEC AC-6) | Integration (expectation suite) |
| TS-10 | Python heredoc inside `bash -c "$( )"`: the print form and the probe form | Runner `ok` for both; the print form is `allow`, the unchanged guard's decision; the probe form is `deny` (FR2, SPEC AC-6) | Integration (expectation suite) |
| TS-11 | `bash` heredoc whose body holds a backtick `git branch -D example` | Runner `ok`, decision `deny` (FR7) | Integration (expectation suite) |
| TS-12 | `perl` heredoc whose body holds a backtick `git branch -D example` | Runner `ok`, decision `deny` (FR7) | Integration (expectation suite) |
| TS-13 | A literal, then a line `git reset --hard HEAD` outside every literal | Runner `ok`, decision `deny` (FR3) | Integration (expectation suite) |
| TS-14 | A Python body with an unclosed literal holding a backtick command | Runner `ok`, decision equal to the unchanged guard's decision (FR6) | Integration (expectation suite) |
| TS-15 | An f-string holding a backtick command | Runner `ok`, decision equal to the unchanged guard's decision (FR4) | Integration (expectation suite) |
| TS-16 | Run the Test Verification command over the whole suite | Exit code 0, `N/N passed`, no `[TIMEOUT` marker; every existing deny / ask case passes (NFR2, NFR4) | Integration (expectation suite + unittest) |
| TS-17 | (planner-added) A comment glued to code (`x = 1# it's`) leaves an unmatched shell quote, so the body goes through the parse-failure fallback; a later literal holds a backtick command | Runner `ok`, decision `allow` (FR1 fallback clause, FR3) | Integration (expectation suite) |
| TS-18 | (planner-added) Eligible shapes: an assignment-enclosed substitution, a downstream `grep`, and the option cluster `-I` before `-`, each with a literal holding a backtick command | Runner `ok`, decision `allow` for all three (FR2) | Integration (expectation suite) |
| TS-19 | (planner-added) Other destinations: a `cat` heredoc piped into `python3`, `timeout 5 python3`, `exec python3`, and a group `{ python3; }` taking the heredoc, each with a literal holding a backtick command | Runner `ok`; each decision equal to the unchanged guard's decision, expected `deny` (FR7) | Integration (expectation suite) |
| TS-20 | (planner-added) A shell behind the Python name: `env -S 'bash -s' python3`, a function named `python3` defined before the heredoc, a `PATH=` prefix, and `alias python3=bash` after the heredoc | Runner `ok`, decision `deny` for all four (FR2) | Integration (expectation suite) |
| TS-21 | (planner-added) The body is not the Python program: `python3 -c`, `python3 tool.py`, `python3 -m tool`, and `python3 - 3<<'PY'` | Runner `ok`, decision `deny` for all four (FR2) | Integration (expectation suite) |
| TS-22 | (planner-added) Parse the case file at `workflow.implement.base_commit` and the current one, and compare | Every base case is present with the same decision, label and command; every new case has three elements (FR8, NFR4) | Inspection (file comparison) |
| TS-23 | (planner-added) List the files the integration branch changes relative to `workflow.implement.base_commit`, outside `feature-docs/destructive-guard-heredoc-literal/` and `test-docs/destructive-guard-heredoc-literal/` | Only `em-workflow/hooks/destructive-guard.py` and `em-workflow/hooks/tests/destructive-guard-cases.json`; neither `em-workflow/.claude-plugin/plugin.json` nor `.claude-plugin/marketplace.json` (NFR3) | Inspection (changed-file list) |
| TS-24 | (planner-added) Read the diff of `em-workflow/hooks/destructive-guard.py` for the literal scan | The literal scan is one left-to-right pass and its masked text has the body's length with every line feed in place; no part of a heredoc body is evaluated, compiled, executed or imported; no import outside the standard library is added (NFR1, NFR2) | Inspection (code reading) |
| TS-25 | (planner-added) An f-string whose replacement field nests quotes of its own kind and a single-quoted literal holding a backtick `git branch -D example` | Runner `ok`, decision `deny`: the f-string makes the body undecidable and nothing is masked (FR4, FR6) | Integration (expectation suite) |
| TS-26 | (planner-added) The Python statement's other redirects make another input the program: a second heredoc with the descriptor move `3<&0`, a duplication `0<&3` onto standard input, and a `<` redirect after the heredoc, each with a literal holding a backtick command | Runner `ok`, decision `deny` for all three (FR2) | Integration (expectation suite) |
| TS-27 | (planner-added) An output redirect to a file on an eligible Python statement (`python3 - <<'PY' > /tmp/out.txt`), body holding a literal with a backtick command | Runner `ok`, decision `allow` (FR2) | Integration (expectation suite) |
| TS-28 | A state-changing builtin behind nested `builtin` / `command` words or `builtin --`: `builtin builtin declare -i x`, `builtin command declare -i x` and `builtin -- declare -i x`, each in the assignment form, and `builtin builtin source ./env.sh` before a Python heredoc whose literal holds a backtick command | Runner `ok`, decision `deny` for all four (FR9) | Integration (expectation suite) |
| TS-29 | `b=builtin; builtin builtin $b declare -i x`, whose word after the removed `builtin` words is not statically determinable, in the assignment form | Runner `ok`, decision `deny` (FR9) | Integration (expectation suite) |
| TS-30 | `builtin builtin alias python3=bash` and `builtin builtin hash -p /bin/bash python3`, each before a Python heredoc whose literal holds a backtick command | Runner `ok`, decision `deny` for both (FR9, NFR5) | Integration (expectation suite) |
| TS-31 | A command holding `builtin builtin alias q=bash` and `python3 x.py`, whose `cat` heredoc writes a `git reset --hard HEAD` line to a file | Runner `ok`, decision equal to the unchanged guard's decision, confirmed by running that guard before the masking-stop check was changed (FR7, NFR5) | Integration (expectation suite) |
| TS-32 | Read the changed `em-workflow/hooks/destructive-guard.py` | The words that stop masking are derived from the command-name override vocabulary, with no word written in two lists; the removal of `builtin` / `command` words with their options and `--` for that decision is in one function (NFR5) | Inspection (code reading) |
| TS-33 | A brace-expansion command word `{declare,-i} x` in the assignment form | Runner `ok`, decision `deny` (FR9) | Integration (expectation suite) |
| TS-34 | Pathname-expansion command words `decl?re -i x`, `[d]eclare -i x` and `decl*re -i x`, each in the assignment form | Runner `ok`, decision `deny` for all three (FR9) | Integration (expectation suite) |
| TS-35 | Pathname or brace expansion after `builtin`: `builtin {declare,-i,x}`, `builtin decl?re -i x` and `builtin {builtin,declare,-i,x}` in the assignment form, and `builtin {hash,-p,/bin/bash,python3}` before a Python heredoc whose literal holds a backtick command | Runner `ok`, decision `deny` for all four (FR9) | Integration (expectation suite) |
| TS-36 | Extended-glob command words `@(declare)`, `?(declare)`, `+(declare)`, `*(declare)` and `!(never)`, each with `-i x`, in the assignment form | Runner `ok`, decision `deny` for all five (FR9) | Integration (expectation suite) |
| TS-37 | Tilde-expansion command words: `HOME=declare; ~ -i x` and `PWD=declare; ~+ -i x`, each in the assignment form | Runner `ok`, decision `deny` for both (FR9) | Integration (expectation suite) |
| TS-38 | Command words with quotes or escapes: `decl\are`, `de"cl"are`, `'declare'`, `$'decla\x72e'`, `$"declare"` (each with `-i x`) and `builtin 'builtin' de"cl"are -i x`, each in the assignment form | Runner `ok`, decision `deny` for all six: restorable words are matched as `declare`, the locale-quoted word is undeterminable (FR9) | Integration (expectation suite) |
| TS-39 | A brace-expansion command word `{declare,-i} x` after a Python heredoc whose literal holds a backtick command | Runner `ok`, decision `deny` (FR9) | Integration (expectation suite) |
| TS-40 | Shapes that must not stop masking: a quoted harmless command word (`'echo' ok`) before a Python heredoc, and a Python body holding a list expression line (`[1, 2]`), each with a literal holding a backtick command | Runner `ok`, decision `allow` for both (FR9, FR1) | Integration (expectation suite) |
| TS-41 | (planner-added) `builtin command -p -- declare -i x`, a command word that is a whole substitution (`$(printf declare) -i x`), and `builtin $(printf declare) -i x`, each in the assignment form | Runner `ok`, decision `deny` for all three (FR9) | Integration (expectation suite) |
| TS-42 | (planner-added) An unquoted-delimiter Python heredoc whose literal holds `$(decl?re -i y)` (a substitution the shell evaluates, with a pathname-expansion command word), followed by a quoted-delimiter Python heredoc whose literal holds a backtick command | Runner `ok`, decision `deny`: the evaluated substitution is not exempt from FR9 (3) (FR9) | Integration (expectation suite) |
| TS-43 | (planner-added) A Python body holding the lines `*rest, last = [1, 2]`, `{"a","b"}` and `~0`, then a literal holding a backtick command | Runner `ok`, decision `allow`: the body's code read as shell is exempt from FR9 (3) (FR9) | Integration (expectation suite) |
| TS-44 | (planner-added) Command words that restore to `echo`: `$'echo' ok`, `e"ch"o ok` and `ec\ho ok`, each before a Python heredoc whose literal holds a backtick command | Runner `ok`, decision `allow` for all three (FR9) | Integration (expectation suite) |
| TS-45 | (planner-added) Read the diff of `em-workflow/hooks/destructive-guard.py` for the masking-stop check | Whether a word is determinable is decided from the word as written with the lexer's region kinds, never from a token value after quote removal; the peel visits each word at most once and the word reading reads each character a bounded number of times; no word is evaluated; no import outside the standard library is added; the Python-body mark is set on the chunks queued from a Python-program body and inherited by derived chunks, except the substitutions the shell evaluates in an unquoted-delimiter body (NFR1, NFR2, FR9) | Inspection (code reading) |

## Code Quality Verification
- Format: none (`project.components.main.format_command` is empty).
- Static analysis: none configured. The case file must parse as JSON; the runner loads it before judging any case, so a malformed file fails TS-16.

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | FR1 to FR9 are implemented and tested | TS-1 to TS-15, TS-17 to TS-22, TS-25 to TS-31 and TS-33 to TS-44 pass |
| SC-2 | TS-1 to TS-16 and TS-28 to TS-40 all pass | Test Verification command exits 0 (TS-1 to TS-16, TS-28 to TS-31, TS-33 to TS-40); TS-32 by code reading |
| SC-3 | NFR1 to NFR5 are met | TS-24 and TS-45 (NFR1, NFR2), TS-16 (NFR2, NFR4), TS-23 (NFR3), TS-22 (NFR4), TS-30, TS-31 and TS-32 (NFR5) |

SPEC AC-6: the print forms of TS-9 and TS-10 put `git reset --hard HEAD` only inside a Python `print` argument, and the unchanged guard returns `allow` for both; they stay `allow`. The probe forms, with the same outer shape, are `deny`. Both forms are cases in the file (labels with TS-9, TS-10, TS-9-probe and TS-10-probe).

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1 to TS-6, TS-17: runner `ok` as `allow` |
| FR2 | task0001 | TS-1, TS-2, TS-3, TS-5, TS-18, TS-27 (`allow`); TS-9, TS-10 (print forms `allow`, probe forms `deny`); TS-20, TS-21, TS-26 (`deny`) |
| FR3 | task0001 | TS-4, TS-6, TS-17 (`allow`); TS-13 (`deny`) |
| FR4 | task0001 | TS-15: unchanged decision; TS-25: `deny` |
| FR5 | task0001 | TS-7, TS-8: `deny` |
| FR6 | task0001 | TS-14: unchanged decision; TS-25: `deny` |
| FR7 | task0001, task0002 | TS-11, TS-12 (`deny`); TS-19, TS-31 (unchanged decisions) |
| FR8 | task0001, task0002 | TS-1 to TS-15, TS-17 to TS-21, TS-25 to TS-31 and TS-33 to TS-44 are cases in the file; TS-22 base-commit comparison |
| FR9 | task0002 | TS-28, TS-29, TS-30, TS-33 to TS-39, TS-41, TS-42 (`deny`); TS-40, TS-43, TS-44 (`allow`); TS-45: code reading |
| NFR1 | task0001, task0002 | TS-24, TS-45: code reading |
| NFR2 | task0001, task0002 | TS-16: no `[TIMEOUT` marker; TS-24: single-pass scan; TS-45: bounded masking-stop check |
| NFR3 | task0001, task0002 | TS-23: changed-file list |
| NFR4 | task0001, task0002 | TS-16: full suite passes; TS-22: no existing case removed or changed |
| NFR5 | task0002 | TS-30 (`deny`: an override word behind nested `builtin` stops masking); TS-31 (the FR7 data-heredoc judgment unchanged); TS-32: code reading |

## Manual Testing (E2E Not Possible)
- [ ] TS-24: read the guard's diff for the single-pass literal scan, the same-length masked text, and the absence of evaluation, compilation, execution or import of body text.
- [ ] TS-32: read the guard's diff for the derived stop vocabulary and the single function that removes `builtin` / `command` words.
- [ ] TS-45: read the guard's diff for the as-written word reading, the bounded cost of the masking-stop check, and where the Python-body mark is set and inherited.

## Performance / Security Verification (if applicable)
- NFR2: every case finishes within the runner's 10-second limit — no runner line carries a `[TIMEOUT 10s]` marker (TS-16).
- TM-1: a body that reaches a shell, an undetermined consumer or another interpreter keeps today's decision — checked by TS-9 and TS-10 (probe forms `deny`, print forms `allow` as unchanged), TS-11, TS-12 and TS-19.
- TM-2: a shell hidden behind the Python name, or a command-name override before or after the heredoc, keeps the body unmasked — checked by TS-20 (all four `deny`).
- TM-3: a body that is data for a script, `-c`, `-m`, another file descriptor, or a statement whose other redirects (a second heredoc, a descriptor duplication or move, a `<` redirect) make another input the program keeps the body unmasked — checked by TS-21 and TS-26 (all `deny`).
- TM-4: text outside literals stays read as commands, and any f-string (one nesting quotes of its own kind included) or an unclosed literal leaves the whole body unmasked — checked by TS-13 and TS-25 (`deny`), TS-14 and TS-15 (unchanged decisions).
- TM-5: with an unquoted delimiter, substitutions inside literals are still inspected — checked by TS-7 and TS-8 (`deny`).
- TM-6: the literal scan stays linear and within the existing scan budget — checked by TS-24 (single pass, same-length masked text) and TS-16 (no `[TIMEOUT` marker).
- TM-7: no part of a heredoc body is evaluated, compiled, executed or imported — checked by TS-24.
- TM-8: an override builtin behind nested `builtin` / `command` words stops masking, and the stop vocabulary is derived from the override vocabulary — checked by TS-30 (both `deny`), with the derivation confirmed by TS-32.
- TM-9: a state-changing builtin behind nested `builtin` / `command` words, their options or `--`, a command word that is not statically determinable, or one spelled with quotes, escapes or an ANSI-C quote, stops masking for the whole command — checked by TS-28, TS-29, TS-33 to TS-39 and TS-41 (all `deny`).
- TM-10: a substitution the shell evaluates in an unquoted-delimiter Python body is not exempt from FR9 (3) — checked by TS-42 (`deny`).
- TM-11: the masking-stop check stays linear in the statement's length — checked by TS-45 (each word visited at most once, bounded character reads) and TS-16 (no `[TIMEOUT` marker).

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios, expectation suite (TS-1 to TS-21, TS-25 to TS-31, TS-33 to TS-44) | 40 | 40 | 0 | 0 |
| Test scenarios, inspection (TS-22, TS-23, TS-24, TS-32, TS-45) | 5 | 2 | 0 | 3 |
| Performance (NFR2) | 1 | 1 | 0 | 0 |
| Security (TM-1 to TM-11) | 11 | 8 | 0 | 3 |
| Total | 57 | 51 | 0 | 6 |
