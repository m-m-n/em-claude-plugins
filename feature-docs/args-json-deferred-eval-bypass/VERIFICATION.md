# Verification Document: args-json-deferred-eval-bypass

## Overview

**Feature**: args-json-deferred-eval-bypass / **SPEC.md**: `feature-docs/args-json-deferred-eval-bypass/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/args-json-deferred-eval-bypass/IMPLEMENTATION.md`

## Build Verification

- Command: none (`project.components.main.build_command` is empty; the hook is a Python script run as is)
- Expected: not applicable

## Test Verification

- Command: `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests`
- Expected: exit code 0; the runner prints no `FAIL` line
- Coverage target: not measured (no coverage tool; standard library only). Every Acceptance Criterion of task0001 and task0002 maps to at least one case-table entry or unit test.

### Test Scenarios from SPEC.md

TS-1 to TS-10 come from SPEC.md. TS-11 to TS-15 are added by the plan for the A3 / A4 boundaries, the forms task0001 adds to FR1, and the non-functional requirements.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | After `p=$'$\x7b declare -gn r=A[@]; }'` and `${p@P}`, the notion call with `--format "$r"` and `git branch -D example` in `--args-json` | deny, rule `git-branch-force-delete` | Integration (case table) |
| TS-2 | After a `$''{`-split value and an ANSI-C value are evaluated as an `(( a ))` array subscript, the same notion call | deny, rule `git-branch-force-delete` | Integration |
| TS-3 | After a value `read` from a quoted-delimiter heredoc, and a value `read` from a file, are evaluated, the same notion call | deny, rule `git-branch-force-delete` | Integration |
| TS-4 | One entry per FR1 construct before the notion call (expansion level: arithmetic expansion, bracket arithmetic, variable subscripts, `@P`, indirect expansion; command level: arithmetic command including `for ((...))`, `let`, `[[ ]]` arithmetic comparisons and `-v`, `declare` / `local` / `typeset` with `i`, assignment to `OPTIND` and to `PS4`, `set -x` / `set -o xtrace`), including forms inside a function body, a group, a conditional, a loop, double quotes, an unquoted-delimiter heredoc body and a here-string | deny, rule `git-branch-force-delete`; the unit tests read each chunk as uncertain | Integration + Unit |
| TS-5 | `fc`, `history`, `enable`, `compgen`, `complete`, `bind`, each alone and after `builtin` / `command`, before the notion call | deny, rule `git-branch-force-delete` | Integration + Unit |
| TS-6 | `printf -v`, a `printf` format holding `%n`, `read`, `getopts`, `wait -p`, `unset`, `test -v`, a function defined and called in the chunk, an unclassified name, before the notion call | deny, rule `git-branch-force-delete` | Integration + Unit |
| TS-7 | Every existing allow / deny / ask case of `destructive-guard-cases.json` and every existing unit test | same decision / same result as before | Integration + Unit |
| TS-8 | `A=(...); echo hello;` then the notion call with `--session "$SID"`, `declare -a`, `command -- echo`, the comment form: KIND_NOTHING; `((x=1));` then the call: KIND_INSPECTED (FR7) | as stated | Unit |
| TS-9 | A deferred-evaluation construct only inside a command substitution (also a backtick and a process substitution), the notion call with `--session "$SID"` outside it | allow; KIND_NOTHING | Integration + Unit |
| TS-10 | Every added deny entry carries `rule`, equal to an existing reason ID; `destructive-guard.py` gains no reason ID | runner passes; reason-ID set unchanged | Integration + Static check |
| TS-11 | `((`, `$((`, `@P`, `${!x}` inside single quotes and inside a quoted-delimiter heredoc body; `"${A[0]}"`, `"${A[@]}"`, `"${A[*]}"`; a compound assignment without subscripts; each before the notion call with `--session "$SID"` (A3, A4) | allow; KIND_NOTHING | Integration + Unit |
| TS-12 | A substring expansion whose offset or length is a name (`${s:p}`, `${s:0:n}`) before the notion call with `--format "$r"`; one with digit offsets (`${s:1:2}`) before the call with `--session "$SID"` | deny, rule `git-branch-force-delete`; allow | Integration + Unit |
| TS-13 | Asking the per-chunk answer of the same chunk twice runs the expansion-level reading once; `test_the_chain_is_walked_without_recursion` passes | as stated | Unit |
| TS-14 | A chunk text or an unquoted heredoc body the lexer cannot settle, a command name that cannot be restored, a `test` / `[` or `printf` word that cannot be restored | uncertain; no exception leaves the per-chunk scan or the heredoc removal step | Unit |
| TS-15 | The change set from the implement base commit to HEAD: the changed test modules import only standard-library modules; no path under `.claude-plugin/` is changed | as stated | Static check |

## Code Quality Verification

- Format: not configured (`project.components.main.format_command` is empty)
- Static analysis: not configured

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | All functional requirements are implemented and tested | Functional Requirements Coverage below: every row has a task and a passing scenario |
| SC-2 | All test scenarios pass | TS-1 to TS-15 |
| SC-3 | Security requirements are satisfied | Performance / Security Verification below (TM-1 to TM-4) |
| SC-4 | Code review is completed | the review phase result in `workflow.yaml` |
| SC-5 | `python3 em-workflow/hooks/tests/run-destructive-guard.py` and `python3 -m unittest discover -s tests` both succeed (AC7) | Test Verification command |
| SC-6 | SPEC.md's Interim Mitigation section states that no upstream fixed version exists and that this feature's fix is the response (AC8) | read SPEC.md `## Interim Mitigation` |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001, task0002 | TS-1, TS-2, TS-3, TS-4, TS-9, TS-11, TS-12 |
| FR2 | task0002 | TS-2, TS-4 |
| FR3 | task0002 | TS-3, TS-5, TS-6, TS-8 |
| FR4 | task0001 | TS-7 |
| FR5 | task0001, task0002 | TS-1, TS-2, TS-3, TS-4, TS-5, TS-6, TS-10 |
| FR6 | task0001, task0002 | TS-7, TS-8, TS-9, TS-11 |
| FR7 | task0002 | TS-8 |
| FR8 | task0001, task0002 | TS-10 |
| NFR1 | task0001, task0002 | TS-14 |
| NFR2 | task0001 | TS-13 |
| NFR3 | task0001, task0002 | TS-15 |
| NFR4 | task0001, task0002 | TS-15 |
| NFR5 | task0001, task0002 | TS-7 (both suites run in each task's change and in this verification) |

## Manual Testing (E2E Not Possible)

None required: every scenario is automated in the case table, the unit suite or a static check of the change set. SC-4 and SC-6 are read from `workflow.yaml` and SPEC.md.

## Performance / Security Verification (if applicable)

- TM-1: expansion-level detection of deferred-evaluation constructs at every read position, unquoted heredoc bodies included, subshell bodies and data positions excluded, with the round-3 literal check kept — checked by TS-1, TS-4, TS-9, TS-11, TS-12 and TS-7 (the round-3 entries).
- TM-2: command-name allowlist, the arithmetic command read as uncertain, unrestorable words read as uncertain — checked by TS-2, TS-3, TS-5, TS-6, TS-8 and TS-14.
- TM-3: command-level evaluation triggers (`[[ ]]` arithmetic comparisons and `-v`, `i` options of declaration builtins, assignment to integer-attribute variables and `PS4`, `set -x`, subscripts in declaration-builtin arguments) read as uncertain — checked by TS-4.
- TM-4: the new readings cannot be made to raise or to cost more than one pass per chunk: lexer failures read as uncertain without an exception, the answer is computed once per chunk and the outward walk does not recurse — checked by TS-13 and TS-14.
- NFR1 (static analysis only): review that neither reading executes or evaluates any part of the command; TS-14 for the fail-safe half.
- FR8 / TS-10 reason-ID check: the set of reason IDs passed to the decision function in `em-workflow/hooks/destructive-guard.py` at `workflow.implement.base_commit` equals the set at HEAD.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios | 15 | 15 | 0 | 0 |
| Success criteria | 6 | 4 | 0 | 2 |
| Security (TM-n) | 4 | 4 | 0 | 0 |
| Manual testing | 0 | 0 | 0 | 0 |
