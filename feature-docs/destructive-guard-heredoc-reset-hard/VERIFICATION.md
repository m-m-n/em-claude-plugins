# Verification Document: destructive-guard-heredoc-reset-hard

## Overview
**Feature**: destructive-guard-heredoc-reset-hard / **SPEC.md**: `feature-docs/destructive-guard-heredoc-reset-hard/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/destructive-guard-heredoc-reset-hard/IMPLEMENTATION.md`

## Build Verification
- Command: none. `project.components.main.build_command` is empty because the code is interpreted Python.
- Expected: not applicable. Syntax errors in the guard surface through the test commands below.

## Test Verification
- Command (project unit tests): `python3 -m unittest discover -s tests`. Expected: exit code 0.
- Command (guard expectation suite, `e2e_test_command`): `python3 em-workflow/hooks/tests/run-destructive-guard.py`. Expected: exit code 0, and the summary line reports that every case passed.
- Coverage target: not measured, because no coverage tooling is configured. Completeness means every scenario below is present in the cases file.

### Test Scenarios from SPEC.md
Where the scenarios come from:
- TS-1 to TS-14 come from SPEC.md.
- TS-15 to TS-20 were added by the planner. They cover SPEC.md's FR5 edge case, FR2's versioned spelling, FR8 and the NFRs.
- TS-21 to TS-27 were added by the planner for IMPLEMENTATION.md D2, the batch Codex-resolved interpretation of FR5.

The scenario commands are listed in full in `tasks/task0001.md` under "Expectation cases". "Case" means one entry in `em-workflow/hooks/tests/destructive-guard-cases.json`, run by the expectation suite.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Ticket minimal reproduction: prose mentioning `git reset --hard` in a quoted-delimiter heredoc body written to a file, followed by `echo done` | allow | Case |
| TS-2 | The path that actually failed: a heredoc written to `$S/prompt.md`, then `run_codex_exec.sh readonly "$(cat $S/prompt.md)"` | allow | Case |
| TS-3 | `python3 x.py;` followed by a heredoc written to a file, with body `git reset --hard HEAD` | allow | Case |
| TS-4 | Two heredocs on one line, both written to files; only the second body contains `git reset --hard HEAD` | allow | Case |
| TS-5 | `bash <<'EOF'` with body `git reset --hard HEAD` | deny | Case |
| TS-6 | `cat <<'EOF' \| bash` with body `git reset --hard HEAD` | deny | Case |
| TS-7 | `sudo bash <<'EOF'` with body `git reset --hard HEAD` | deny | Case |
| TS-8 | `/bin/sh <<'EOF'` with body `git reset --hard HEAD` | deny | Case |
| TS-9 | Two heredocs on one line; only the second (`bash <<'B'`) goes to a sink, and its body contains `git reset --hard HEAD` | deny | Case |
| TS-10 | A heredoc written to a file, then a real `git reset --hard HEAD` after the delimiter line | deny | Case |
| TS-11 | `echo 'git reset --hard HEAD'` | allow | Case |
| TS-12 | `git commit -m "docs: explain why git reset --hard is forbidden"` | allow | Case |
| TS-13 | `bash -c "$(cat <<'EOF' ... EOF)"` with body `git reset --hard HEAD` | deny | Case |
| TS-14 | Full expectation suite | every case passes; every pre-existing deny / ask case is kept, with its verdict unchanged | Integration |
| TS-15 | (planner-added, FR5) A heredoc with a reset body written to a file, where the chunk then fails to lex (`echo "bash` has an unbalanced quote) | deny (falls back to the chunk-wide sink match) | Case |
| TS-16 | (planner-added, FR2) `python3.12 <<'EOF'` with body `git reset --hard HEAD` | deny | Case |
| TS-17 | (planner-added, FR5) `{ bash; } <<'EOF'` with body `git reset --hard HEAD`; the operator is attached to a compound command's closer | deny (falls back to the chunk-wide sink match) | Case |
| TS-18 | (planner-added, FR8) Version consistency | the em-workflow version in `em-workflow/.claude-plugin/plugin.json` is the base value raised by one patch step; the em-workflow entry in `.claude-plugin/marketplace.json` holds the same value; both files parse as JSON; no other plugin's version changes | Inspection |
| TS-19 | (planner-added, NFR1 / NFR2 / NFR4) Change-set and dependency inspection | the diff against the base touches only the four task files; `hooks.json` and `run-destructive-guard.py` are unchanged; there is no import from outside the standard library; the heredoc path adds no filesystem access, process execution or evaluation of command text | Inspection |
| TS-20 | (planner-added, NFR3) Heredoc stress measurement: two generated inputs of about 2,000 and 4,000 lines, each line holding several heredoc operators aimed at a data command, some of them never terminated | the larger input finishes in under 2 seconds and takes at most three times as long as the smaller one | Performance (ad hoc) |
| TS-21 | (planner-added, FR5 / D2) `timeout 10 bash <<'EOF'` with body `git reset --hard HEAD`; the host command word is an execution prefix outside the wrapper set | deny (undeterminable, so it falls back to the chunk-wide sink match) | Case |
| TS-22 | (planner-added, FR5 / D2) `exec bash <<EOF` with body `git reset --hard HEAD` | deny (undeterminable, so it falls back to the chunk-wide sink match) | Case |
| TS-23 | (planner-added, FR1 (iii) / D2) `echo "$(cat <<'EOF' ... EOF)" \| bash` with body `git reset --hard HEAD`; the enclosing statement pipes into a sink | deny | Case |
| TS-24 | (planner-added, FR1 (iii) / D2, control for TS-23) `echo "$(cat <<'EOF' ... EOF)"` with body `git reset --hard HEAD`; the enclosing command word `echo` is a data command, with no sink downstream | allow | Case |
| TS-25 | (planner-added, FR5 / D2, per-heredoc fallback control) `python3 x.py; timeout 5 cat <<'A' ; cat > /tmp/b <<'B'`; A is undeterminable and has a harmless body, B is a data heredoc whose body contains `git reset --hard HEAD` | allow (the fallback does not spill onto B) | Case |
| TS-26 | (planner-added, FR5 / D2) `timeout 10 bash -c "$(cat <<'EOF' ... EOF)"` with body `git reset --hard HEAD`; the enclosing command word is an execution prefix outside the wrapper set | deny (undeterminable, so it falls back to the chunk-wide sink match) | Case |
| TS-27 | (planner-added, FR5 / D2) `tee >(bash) <<'EOF'` with body `git reset --hard HEAD`; a process substitution on the host statement can consume the body | deny (undeterminable, so it falls back to the chunk-wide sink match) | Case |

## Code Quality Verification
- Format: none configured (`format_command` is empty).
- Static analysis: none configured.

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | The ticket reproduction is allowed and present as an allow case | TS-1 |
| AC-2 | The real-path shape is allowed, including when a `python3` or `bash` word appears elsewhere in the chunk | TS-2, TS-3, TS-25 |
| AC-3 | Two heredocs on one line, with the reset only in the second body, are allowed | TS-4 |
| AC-4 | Detection of heredocs that go to a sink is kept. Covered shapes: bare, pipeline, wrapper, absolute path, second of two, enclosing substitution, execution prefix, process substitution, and the existing case "bash ヒアドキュメントは実行" | TS-5, TS-6, TS-7, TS-8, TS-9, TS-13, TS-14, TS-21, TS-22, TS-23, TS-26, TS-27 |
| AC-5 | A real reset after the heredoc is denied | TS-10 |
| AC-6 | A reset inside quoted strings is allowed and present as allow cases | TS-11, TS-12 |
| AC-7 | The suite passes and every pre-existing deny / ask case is kept | TS-14 |
| AC-8 | The version is raised by one patch step, and plugin.json and marketplace.json agree | TS-18 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2, TS-3, TS-5, TS-6, TS-7, TS-8, TS-13, TS-23, TS-24 |
| FR2 | task0001 | TS-2, TS-3, TS-7, TS-8, TS-16, TS-25 |
| FR3 | task0001 | TS-4, TS-9 |
| FR4 | task0001 | TS-10 |
| FR5 | task0001 | TS-15, TS-17, TS-21, TS-22, TS-25, TS-26, TS-27 |
| FR6 | task0001 | TS-1, TS-2, TS-3, TS-4, TS-5, TS-6, TS-9, TS-10, TS-11, TS-12, TS-14 |
| FR7 | task0001 | TS-14 |
| FR8 | task0001 | TS-18 |
| NFR1 | task0001 | TS-14, TS-19 |
| NFR2 | task0001 | TS-19 |
| NFR3 | task0001 | TS-20 |
| NFR4 | task0001 | TS-19 |

## E2E Testing
The project's E2E command is the guard expectation suite. For each case, it runs the real hook script as a subprocess with a PreToolUse payload.
- [ ] TS-14: `python3 em-workflow/hooks/tests/run-destructive-guard.py` passes, with TS-1 to TS-13, TS-15 to TS-17 and TS-21 to TS-27 present in the cases file

## Manual Testing (E2E Not Possible)
- [ ] TS-18: compare the version fields of `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` against the base revision
- [ ] TS-19: inspect the diff against the base revision for the set of changed files, the imports, and any new filesystem access, process execution or evaluation in the heredoc path

## Performance / Security Verification
- NFR3: TS-20. The generated stress inputs finish within the thresholds stated there, well inside the 10-second `hooks.json` timeout.
- TM-1: bodies that go to a sink are still rescanned. The decision is made per heredoc destination, including the downstream pipeline of an enclosing statement, and the sink vocabulary is not reduced. Checked by these cases:
  - denied: TS-5, TS-6, TS-7, TS-8, TS-9, TS-13, TS-16, TS-23
  - allowed: TS-1, TS-2, TS-3, TS-4, TS-24
- TM-2: body consumption stops at each operator's own delimiter line, and text after the last delimiter line is still checked. Checked by these cases:
  - denied: TS-9, TS-10
  - allowed: TS-4
- TM-3: when a heredoc's destination cannot be determined, that heredoc falls back to the current chunk-wide sink match. The fallback stays confined to that heredoc. Checked by these cases:
  - denied: TS-15 (unlexable chunk), TS-17 (compound-command closer), TS-21 and TS-22 (execution prefix on the host statement), TS-26 (execution prefix on the enclosing statement), TS-27 (process substitution)
  - allowed: TS-25 (confinement)
- TM-4: existing verdicts are preserved. Checked by TS-14 (the full suite passes) and by a cases-file diff that shows additions only.
- TM-5: heredoc processing cost stays proportional to input size. Checked by TS-20.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Expectation cases (TS-1 to TS-13, TS-15 to TS-17, TS-21 to TS-27) | 23 | 23 | 23 | 0 |
| Integration (TS-14) | 1 | 1 | 1 | 0 |
| Inspection (TS-18, TS-19) | 2 | 0 | 0 | 2 |
| Performance (TS-20) | 1 | 0 | 0 | 1 |
| Security mitigations (TM-1 to TM-5) | 5 | 4 | 4 | 1 |
