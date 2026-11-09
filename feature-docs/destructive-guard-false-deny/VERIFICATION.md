# Verification Document: destructive-guard-false-deny

## Overview
**Feature**: destructive-guard-false-deny / **SPEC.md**: `feature-docs/destructive-guard-false-deny/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/destructive-guard-false-deny/IMPLEMENTATION.md`

## Build Verification
- Command: none. `project.components.main.build_command` is empty, and the hook is a Python script with no build step.
- Expected: not applicable.

## Test Verification
- Command: `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests`
- Expected: the runner reports every case `ok` and exits 0. Unittest discovery reports the same set of failing tests as at the implement base commit (NFR4).
- Coverage target: not measured. The suite is case-driven. Coverage is the scenarios below plus the fail-closed cases of task0001 AC-2 and task0002 AC-2.

### Test Scenarios from SPEC.md
The commands of TS-1 to TS-18 are in SPEC.md, section Test Scenarios. TS-19 to TS-22 were added by the rework of review round 1 (task0002); their commands are under "Commands of the rework scenarios" below. TS-1 to TS-17 and TS-19 to TS-22 are cases in `em-workflow/hooks/tests/destructive-guard-cases.json`, run by the runner.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Non-forced task-branch deletion from the integration worktree (the protocol form) | allow | Unit (case) |
| TS-2 | Forced deletion of a task branch | deny | Unit (case) |
| TS-3 | mcp-bridge comment whose single-quoted JSON argument holds a backtick substitution of a forced deletion | allow | Unit (case) |
| TS-4 | The same with a `$( )` substitution | allow | Unit (case) |
| TS-5 | mcp-bridge comment whose argument is a double-quoted substitution that reads a file | allow | Unit (case) |
| TS-6 | printf of an ANSI-C-quoted argument holding a backtick substitution | allow | Unit (case) |
| TS-7 | Unquoted backtick substitution of a forced deletion | deny | Unit (case) |
| TS-8 | Double-quoted backtick substitution | deny | Unit (case) |
| TS-9 | bash -c payload holding a backtick substitution | deny | Unit (case) |
| TS-10 | bash -c payload holding a `$( )` substitution | deny | Unit (case) |
| TS-11 | sh -c payload holding a `$( )` substitution | deny | Unit (case) |
| TS-12 | eval of a single-quoted argument holding a substitution | deny | Unit (case) |
| TS-13 | Here-string into bash holding a substitution | deny | Unit (case) |
| TS-14 | Single-quoted text piped into bash | deny | Unit (case) |
| TS-15 | Single-quoted text written to a file, which bash then runs | deny | Unit (case) |
| TS-16 | Single-quoted text inside a process-substitution body that bash runs | deny | Unit (case) |
| TS-17 | Single-quoted text inside a command-substitution body passed to eval | deny | Unit (case) |
| TS-18 | The whole case suite, pre-existing cases included, within the per-case time limit | every case ok, none timed out | Integration |
| TS-19 | A variable holds a single-quoted substitution of a forced deletion, and eval runs it inside a nested command substitution | deny | Unit (case) |
| TS-20 | The same variable, run by bash -c inside a process substitution | deny | Unit (case) |
| TS-21 | Single-quoted text holding a substitution, piped into sort whose compress program is sh | deny | Unit (case) |
| TS-22 | mcp-bridge comment whose single-quoted JSON argument holds set, let, function, `$[x]`, a `$( )` and a backtick substitution of a forced deletion | allow | Unit (case) |

#### Commands of the rework scenarios

TS-19:

```
X='$(git branch -D example)'; echo "$(eval "$X")"
```

TS-20:

```
X='$(git branch -D example)'; cat <(bash -c "$X")
```

TS-21:

```
printf '%s\n' '$(git branch -D example)' | sort -S 1b --compress-program=sh
```

TS-22:

```
mcp-bridge run --mcp notion --tool notion-create-comment --args-json '{"body":"set let function f() $[x] $(git branch -D example) `git branch -D example` と記載する"}'
```

## Code Quality Verification
- Format: none configured (`format_command` is empty).
- Static analysis: none configured.

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SPEC AC-1 | The protocol's non-forced task-branch deletion is allowed | TS-1 |
| SPEC AC-2 | Forced task-branch deletion stays denied | TS-2 |
| SPEC AC-3 | implement-phase.md Step I.2.b step 4 keeps the non-forced deletion and the sentence forbidding a forced fallback | `tests/test_protocol_git_ops_pass_destructive_guard.py` (run by unittest discovery), plus the manual check below |
| SPEC AC-4 | Data-argument forms are allowed | TS-3, TS-4, TS-5, TS-6, TS-22 |
| SPEC AC-5 | Executed forms stay denied | TS-7 to TS-17, TS-19, TS-20, TS-21 |
| SPEC AC-6 | No pre-existing case is removed or changed, and the runner passes | TS-18, plus the parsed-JSON comparison of task0001 AC-1 |
| SPEC AC-7 | The pre-fix run is recorded | Manual check below |
| Success Criteria: unit tests | `python3 -m unittest discover -s tests` gives the same result as before the change (NFR4) | Test Verification command |
| Success Criteria: review | Code review is completed | Review phase |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2; manual check of SPEC AC-3 |
| FR2 | task0001, task0002 | TS-3, TS-4, TS-5, TS-6, TS-22; task0001 AC-2 and task0002 AC-1 / AC-2 cases; manual check of the skip decision's shape |
| FR3 | task0001, task0002 | TS-18 (FR3 example cases); manual diff check |
| FR4 | task0001, task0002 | TS-7 to TS-17, TS-19, TS-20, TS-21 |
| FR5 | task0001, task0002 | TS-1 to TS-22 |
| FR6 | task0001, task0002 | Manual: commit order and pre-fix record |
| FR7 | task0001, task0002 | Manual: comment review |
| NFR1 | task0001, task0002 | TS-18 |
| NFR2 | task0001, task0002 | TS-18 (the runner's per-case time limit); manual diff check of the two budget constants |
| NFR3 | task0001, task0002 | Manual diff check |
| NFR4 | task0001, task0002 | Comparison of unittest discovery results |

## Manual Testing (E2E Not Possible)
- [ ] FR6 / SPEC AC-7: on task0001's branch, the commit that adds the cases comes before every commit that changes `em-workflow/hooks/destructive-guard.py`. task0001's test record holds the pre-fix runner result: the added deny-side cases pass, and TS-3, TS-4 and TS-6 come out deny.
- [ ] FR6 (rework): on task0002's branch, the commit that adds its cases comes before every commit that changes `em-workflow/hooks/destructive-guard.py`. task0002's test record holds the pre-fix run against the unmodified hook and the run against the hook at the implement base commit, in which every deny case task0002 adds comes out deny.
- [ ] FR2 (rework): the skip decision is one function separate from the queueing code; `_ARGS_NOT_EXECUTED_WORDS` and the other FR2-only word lists and raw-text patterns are gone; no code removes or reorders pending-stack entries after they are pushed.
- [ ] FR7: the HONOR_SINGLE_QUOTES paragraph of `scan_structure()`, the comments about the quote-agnostic scan and queueing in `statements()`, and the single-quote passages of the `_mark_quoted_substitutions()` and `extract_shell_payload_anchored()` docstrings all describe the FR2 / FR3 behaviour as task0002 narrows it. None still says that every single-quote candidate is re-scanned, and none describes the removed execution-word list or allowlist.
- [ ] FR1 / SPEC AC-3: the diff from the implement base commit leaves `em-workflow/references/implement-phase.md` unchanged. Step I.2.b step 4 still deletes the task branch from the integration worktree without force, and still forbids falling back to a forced deletion.
- [ ] NFR3: the diff from the implement base commit leaves unchanged the `version` in `em-workflow/.claude-plugin/plugin.json` and the em-workflow entry's `version` in `.claude-plugin/marketplace.json`.
- [ ] FR3: the diff leaves unchanged the top-level span computation, both marking passes, the extension of the run-global substitution list and the per-token flags in `statements()`.

## Performance / Security Verification
- NFR2: every runner case finishes within the runner's per-case limit (10 s), so no case is marked as a timeout. The diff leaves `scan_budget` and `MAX_SHELL_PAYLOAD_EXPANSIONS` unchanged.
- TM-1: the hook skips re-scanning only a single-quoted candidate that fills a data argument of one static `mcp-bridge run` or `printf '%s\n'` command making up the whole input, a subset of FR2 (a)-(d); anything it cannot decide is re-scanned. Checked by TS-7 to TS-17 and TS-19 to TS-21 coming out deny with the changed hook, and by every task0001 AC-2 and task0002 AC-2 case keeping its non-allow expected decision.
- TM-2: marking and token flags stay unchanged, and only queueing differs. Checked by the FR3 example cases of SPEC.md passing with unchanged expected decisions (TS-18), and by the FR3 manual diff check.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS-1 to TS-22) | 22 | 22 | 0 | 0 |
| Repository unit tests (NFR4) | 1 | 1 | 0 | 0 |
| Code quality | 0 | 0 | 0 | 0 |
| Manual checks (FR6, FR6 rework, FR2 rework, FR7, SPEC AC-3, NFR3, FR3 diff) | 7 | 0 | 0 | 7 |
| Performance / Security (NFR2, TM-1, TM-2) | 3 | 3 | 0 | 0 |
