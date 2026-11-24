# Verification Document: env-route-lex-flag-isolation

## Overview
**Feature**: env-route-lex-flag-isolation / **SPEC.md**: `feature-docs/env-route-lex-flag-isolation/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/env-route-lex-flag-isolation/IMPLEMENTATION.md`

## Build Verification
- Command: none (`project.components.main.build_command` is empty; the hook is a Python script with no build step)
- Expected: not applicable

## Test Verification
- Command: `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests`
- Expected: exit code 0; the runner reports every case as passing
- Coverage target: no coverage tool is configured; every scenario below has its own test or check

### Test Scenarios from SPEC.md
TS-1 to TS-7 come from SPEC.md. TS-8 to TS-11 are planner-defined: SPEC.md has no scenario for FR2, FR4, NFR2 and NFR4, and these four close that gap.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | `/usr/bin/env bash -c` whose body holds only a cat heredoc with the delimiter `${tag}` (harmless lines and the delimiter line), with `CLAUDE_BATCH` | allow (deny with unreadable-heredoc-delimiter before the fix) | Integration (decision case) |
| TS-2 | The TS-1 body through the lone-`-` env form, with `CLAUDE_BATCH` | allow | Integration (decision case) |
| TS-3 | The TS-1 body through plain `bash -c` (no env), with `CLAUDE_BATCH` | deny, rule unreadable-heredoc-delimiter (current decision pinned) | Integration (decision case) |
| TS-4 | An env-route `echo hi` statement and a top-level heredoc with an unreadable delimiter in one command, with `CLAUDE_BATCH` | deny, rule unreadable-heredoc-delimiter (the flag raised outside the env route survives) | Integration (decision case) |
| TS-5 | An env-route body holding an extended-pattern parenthesis inside an array and no notion call | allow (same as without the env-route reading) | Integration (decision case) |
| TS-6 | An env-route body whose notion-pair call with `git branch -D` as its command follows, after `;` on the same line, a line the extglob-off reading discards | deny, with its reason ID pinned; fails (allow) against an implementation with FR1 but without FR3 | Integration (decision case) |
| TS-7 | Regression: every existing case, the two existing mcp-bridge-function-shadow cases included, and the unittest discovery | all pass | Regression |
| TS-8 | Env-route reading exits by normal return, each early return, and a `LexBudgetExceeded` raised inside it, with entry flags both true and false | `_lex_unreadable_met`, `_lex_extglob_met` and `_lex_extglob` equal their entry values; the exception propagates unchanged | Unit |
| TS-9 | Both extglob readings return the same value; only one reading raises overrun or unrestorable | the value is returned once and charged once; overrun / unrestorable are reported | Unit |
| TS-10 | Env-route reading of a body with an extended-pattern parenthesis (both readings run) | the recorded extglob unit count is unchanged | Unit |
| TS-11 | Diff of the integration branch against `main` | neither `em-workflow/.claude-plugin/plugin.json` nor `.claude-plugin/marketplace.json` is changed | Diff check |

## Code Quality Verification
- Format: none configured (`format_command` is empty)
- Static analysis: none configured

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | The env-route form (`/usr/bin/env` and lone `-`) of a body with only a `${tag}` heredoc is allowed under `CLAUDE_BATCH` | TS-1, TS-2 |
| AC-2 | Plain `bash -c` and flags raised outside the env route keep their decisions | TS-3, TS-4 |
| AC-3 | Env-route notion-pair detection does not narrow; extended-pattern parentheses alone do not change the decision | TS-5, TS-6 |
| AC-4 | The runner and the unittest discovery pass; TS-1 to TS-6 are in `destructive-guard-cases.json` | TS-7, plus inspection of the case file for TS-1 to TS-6 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2, TS-4, TS-5 (decision cases); TS-8 (entry values restored) |
| FR2 | task0001 | TS-8 (restoration on the exception exit) |
| FR3 | task0001 | TS-5, TS-6 (decision cases); TS-8 (extglob setting restored) |
| FR4 | task0001 | TS-9 |
| FR5 | task0001 | TS-1 to TS-7 (cases present and passing) |
| NFR1 | task0001 | TS-3, TS-4, TS-5 |
| NFR2 | task0001 | TS-10 |
| NFR3 | task0001 | TS-7 |
| NFR4 | task0001 | TS-11 |

## Manual Testing (E2E Not Possible)
- None. Every scenario is automated or a diff check.

## Performance / Security Verification (if applicable)
- TM-1: the flags are restored to their entry values, never a fixed false — checked by TS-4 (deny, unreadable-heredoc-delimiter), which a restore-to-false variant fails.
- TM-2: the env-route body is read under both extglob settings and the notion pairs of either reading are checked — checked by TS-6 (deny), which an FR1-only variant fails.
- TM-3: the extglob setting is back to its entry value on every exit, exceptions included — checked by TS-8.
- TM-4: overrun and unrestorable raised by either reading are reported — checked by TS-9.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Decision cases (TS-1 to TS-6) | 6 | 6 | 0 | 0 |
| Regression (TS-7) | 1 | 1 | 0 | 0 |
| Unit (TS-8 to TS-10) | 3 | 3 | 0 | 0 |
| Diff check (TS-11) | 1 | 1 | 0 | 0 |
| Security (TM-1 to TM-4) | 4 | 4 | 0 | 0 |
| Total | 15 | 15 | 0 | 0 |
