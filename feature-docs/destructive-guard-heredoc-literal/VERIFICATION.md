# Verification Document: destructive-guard-heredoc-literal

## Overview
**Feature**: destructive-guard-heredoc-literal / **SPEC.md**: `feature-docs/destructive-guard-heredoc-literal/SPEC.md` / **IMPLEMENTATION.md**: not produced (reduced tier; one task, no file shared between tasks) / **THREAT-MODEL.md**: `feature-docs/destructive-guard-heredoc-literal/THREAT-MODEL.md`

## Build Verification
- Command: none. `project.components.main.build_command` is empty; the changed files are a Python hook script and a JSON case file, which are not built.
- Expected: not applicable.

## Test Verification
- Command: `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests`
- Expected: exit code 0. The runner's last line is `N/N passed`, with both numbers equal to the number of cases in `em-workflow/hooks/tests/destructive-guard-cases.json` plus one (the unattended-demotion check), and no line carries a `[TIMEOUT` marker.
- Coverage target: not applicable. The expectation suite is case-based; every case must pass.

The commands of the cases are given line by line in `feature-docs/destructive-guard-heredoc-literal/tasks/task0001.md` (Design, Test cases). "Unchanged guard's decision" below means the decision `em-workflow/hooks/destructive-guard.py` at `workflow.implement.base_commit` returns for the same command.

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
| TS-9 | Python heredoc piped to `bash`: the SPEC form (prints `git reset --hard HEAD`) and the probe form (a literal holding a backtick command) | Runner `ok` for both; the probe form is `deny`; the SPEC form holds the unchanged guard's decision (SPEC AC-6 expects `deny`; see the note under SPEC.md Compliance) (FR2) | Integration (expectation suite) |
| TS-10 | Python heredoc inside `bash -c "$( )"`: the SPEC form and the probe form | Runner `ok` for both; the probe form is `deny`; the SPEC form holds the unchanged guard's decision (SPEC AC-6 expects `deny`; see the note under SPEC.md Compliance) (FR2) | Integration (expectation suite) |
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
| TS-24 | (planner-added) Read the diff of `em-workflow/hooks/destructive-guard.py` | The literal scan is one left-to-right pass and its masked text has the body's length with every line feed in place; no part of a heredoc body is evaluated, compiled, executed or imported; no import outside the standard library is added (NFR1, NFR2) | Inspection (code reading) |
| TS-25 | (planner-added) An f-string whose replacement field nests quotes of its own kind and a single-quoted literal holding a backtick `git branch -D example` | Runner `ok`, decision `deny`: the f-string makes the body undecidable and nothing is masked (FR4, FR6) | Integration (expectation suite) |
| TS-26 | (planner-added) The Python statement's other redirects make another input the program: a second heredoc with the descriptor move `3<&0`, a duplication `0<&3` onto standard input, and a `<` redirect after the heredoc, each with a literal holding a backtick command | Runner `ok`, decision `deny` for all three (FR2) | Integration (expectation suite) |
| TS-27 | (planner-added) An output redirect to a file on an eligible Python statement (`python3 - <<'PY' > /tmp/out.txt`), body holding a literal with a backtick command | Runner `ok`, decision `allow` (FR2) | Integration (expectation suite) |

## Code Quality Verification
- Format: none (`project.components.main.format_command` is empty).
- Static analysis: none configured. The case file must parse as JSON; the runner loads it before judging any case, so a malformed file fails TS-16.

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | FR1 to FR8 are implemented and tested | TS-1 to TS-15, TS-17 to TS-22 and TS-25 to TS-27 pass |
| SC-2 | TS-1 to TS-16 all pass | Test Verification command exits 0; TS-9 and TS-10 as stated in the table |
| SC-3 | NFR1 to NFR4 are met | TS-24 (NFR1, NFR2), TS-16 (NFR2, NFR4), TS-23 (NFR3), TS-22 (NFR4) |

Note on SPEC AC-6: the SPEC forms of TS-9 and TS-10 put `git reset --hard HEAD` only inside a Python `print` argument, which the current guard may not read as a command. The implementer records the unchanged guard's decision for both. When either is not `deny`, AC-6's premise ("deny のまま") did not hold; the case is pinned at the unchanged decision, as FR2 requires, and the probe forms carry the protective check. This feature adds no new detection for Python output.

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1 to TS-6, TS-17: runner `ok` as `allow` |
| FR2 | task0001 | TS-1, TS-2, TS-3, TS-5, TS-18, TS-27 (`allow`); TS-9, TS-10, TS-20, TS-21, TS-26 (`deny` or unchanged) |
| FR3 | task0001 | TS-4, TS-6, TS-17 (`allow`); TS-13 (`deny`) |
| FR4 | task0001 | TS-15: unchanged decision; TS-25: `deny` |
| FR5 | task0001 | TS-7, TS-8: `deny` |
| FR6 | task0001 | TS-14: unchanged decision; TS-25: `deny` |
| FR7 | task0001 | TS-11, TS-12 (`deny`); TS-19 (unchanged) |
| FR8 | task0001 | TS-1 to TS-15, TS-17 to TS-21 and TS-25 to TS-27 are cases in the file; TS-22 base-commit comparison |
| NFR1 | task0001 | TS-24: code reading |
| NFR2 | task0001 | TS-16: no `[TIMEOUT` marker; TS-24: single-pass scan |
| NFR3 | task0001 | TS-23: changed-file list |
| NFR4 | task0001 | TS-16: full suite passes; TS-22: no existing case removed or changed |

## Manual Testing (E2E Not Possible)
- [ ] TS-24: read the guard's diff for the single-pass scan, the same-length masked text, and the absence of evaluation, compilation, execution or import of body text.

## Performance / Security Verification (if applicable)
- NFR2: every case finishes within the runner's 10-second limit — no runner line carries a `[TIMEOUT 10s]` marker (TS-16).
- TM-1: a body that reaches a shell, an undetermined consumer or another interpreter keeps today's decision — checked by TS-9 and TS-10 (probe forms `deny`, SPEC forms unchanged), TS-11, TS-12 and TS-19.
- TM-2: a shell hidden behind the Python name, or a command-name override before or after the heredoc, keeps the body unmasked — checked by TS-20 (all four `deny`).
- TM-3: a body that is data for a script, `-c`, `-m`, another file descriptor, or a statement whose other redirects (a second heredoc, a descriptor duplication or move, a `<` redirect) make another input the program keeps the body unmasked — checked by TS-21 and TS-26 (all `deny`).
- TM-4: text outside literals stays read as commands, and any f-string (one nesting quotes of its own kind included) or an unclosed literal leaves the whole body unmasked — checked by TS-13 and TS-25 (`deny`), TS-14 and TS-15 (unchanged decisions).
- TM-5: with an unquoted delimiter, substitutions inside literals are still inspected — checked by TS-7 and TS-8 (`deny`).
- TM-6: the literal scan stays linear and within the existing scan budget — checked by TS-24 (single pass, same-length masked text) and TS-16 (no `[TIMEOUT` marker).
- TM-7: no part of a heredoc body is evaluated, compiled, executed or imported — checked by TS-24.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios, expectation suite (TS-1 to TS-21, TS-25 to TS-27) | 24 | 24 | 0 | 0 |
| Test scenarios, inspection (TS-22, TS-23, TS-24) | 3 | 2 | 0 | 1 |
| Performance (NFR2) | 1 | 1 | 0 | 0 |
| Security (TM-1 to TM-7) | 7 | 5 | 0 | 2 |
| Total | 35 | 32 | 0 | 3 |
