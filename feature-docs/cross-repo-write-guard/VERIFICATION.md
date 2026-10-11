# Verification Document: cross-repo-write-guard

## Overview

**Feature**: cross-repo-write-guard / **SPEC.md**: `feature-docs/cross-repo-write-guard/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/cross-repo-write-guard/IMPLEMENTATION.md` / **THREAT-MODEL.md**: `feature-docs/cross-repo-write-guard/THREAT-MODEL.md`

All checks run on the integrated tree.

## Build Verification

- Command: none — both components (`repo-tests`, `plugin-invariants`) declare an empty `build_command`.
- Expected: not applicable.

## Test Verification

- Command (`repo-tests`): `python3 -m unittest discover -s tests`
- Command (`plugin-invariants`): `python3 em-workflow/scripts/check-plugin-invariants.py .`
- Focused command (FR13): `python3 -m unittest tests.test_cross_repo_write_guard`
- Expected: exit code 0 for each command, no failures or errors.
- Coverage target: not measured (no coverage tool in the components). Every scenario below maps to at least one automated test or an inspection item.

### Test Scenarios from SPEC.md

TS-1 to TS-11 come from SPEC.md. TS-12 to TS-15 cover NFR1 to NFR4.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Write / Edit / MultiEdit inside and outside (AC-2): fixture repository inside, outside, under `/tmp`, under the substituted `HOME`'s `.claude`, relative `file_path` | Outside → one `ask`; every other case → no output | Unit (hook as subprocess) |
| TS-2 | cwd outside a repository and invalid input (AC-3): cwd not in any git repository, broken JSON, other `tool_name`, empty `command`, missing `cwd` | No output, exit code 0 | Unit |
| TS-3 | Worktree to main working tree (AC-4): cwd in a worktree made with `git worktree add`, destination in the main working tree | `ask` | Unit (fixture worktree) |
| TS-4 | Symbolic links and boundaries (AC-5): not-yet-existing file reached through a link under the toplevel that points outside; `repo` vs `repo-other` | `ask` for both | Unit (fixture) |
| TS-5 | `/dev` exclusion list (AC-6): `> /dev/null`, `2>/dev/null`, `&>/dev/null`, `/dev/fd/1`, a `/dev` path outside the list | Listed paths → no output; unlisted `/dev` path → `ask` | Unit (`CASES`) |
| TS-6 | Write forms (AC-7): `>`, `>>`, `>\|`, `&>`, `2>`, `>&2` (not a destination), `tee -a`, `sed -i`, `sed -i.bak -e`, `cp a b`, `cp -t DIR a`, `mv a b`, single-operand `cp` | Outside destinations → `ask`; inside destinations, `>&2`, `mv` source and single-operand `cp` → no output | Unit (`CASES`) |
| TS-7 | Nesting and non-command text (AC-8): `( )`, `{ ; }`, `sudo` / `env` / `nohup` / `time` / `command` / `nice`, `bash -c '...'`, `x=$(...)`, `bash -c` with an outer redirection, heredoc body, quotes, comments | Outside writes in subshell / brace group / after wrappers → `ask`; writes only inside `bash -c` strings, `$( )` bodies, heredoc bodies, quotes, comments → no output; outer redirection of `bash -c` → `ask` | Unit (`CASES`) |
| TS-8 | Unresolvable destinations and `~` (AC-9): `$VAR`, `${HOME}`, `$(pwd)/x`, glob, quoted `'~/x'`, unquoted `~/x` | Unquoted `~/x` (HOME outside the repository) → `ask`; the others → no output | Unit (`CASES`) |
| TS-9 | After a working-directory change (AC-10): `cd /x && echo > a`, `cd /x && echo > /outside/a`, `(cd /x && echo > a); echo > ../outside`, `pushd`, `env -C` | `cd /x && echo > a` → no output; absolute outside after `cd` → `ask`; relative outside after a subshell `cd` → `ask`; relative after `pushd` / `env -C` → no output | Unit (`CASES`) |
| TS-10 | Unattended downgrade (AC-11): `CLAUDE_BATCH=1`; `0`, `false`, `no`, unset; reason wording | `1` → `deny` with a downgrade notice; `0` / `false` / `no` / unset → `ask`; reason begins with `[cross-repo-write-guard]` and names the outside path and the toplevel; `allow` never appears | Unit |
| TS-11 | Registration and documentation (AC-1, AC-12, AC-13): `tests/test_hooks_registration.py`, `tests/test_guardrail_hooks_migration.py`, `tests/test_cross_repo_write_guard.py`; README and hook-tests.md content; `destructive-guard.py` unchanged | All three modules pass; README and hook-tests.md content per AC-12 / AC-13; no diff on `destructive-guard.py` | Unit + Inspection |
| TS-12 | Dependencies (NFR1) | Every module imported by the hook and by its test module is a standard-library module | Unit (hook) + Inspection (test module) |
| TS-13 | Side effects (NFR2): stub git first on `PATH` counting invocations; commands whose destinations are all excluded or unresolvable; commands with one or several outside destinations | git started 0 times in the first case and exactly once in the second; the fixture repository and substituted `HOME` gain no files | Unit (stub git) |
| TS-14 | git time limit (NFR3): stub git that does not answer | No output, exit code 0, total runtime under 15 seconds | Unit (stub git) |
| TS-15 | Test isolation (NFR4) | Every hook run in the test module uses a substituted `HOME`; fixture repositories are created under a temporary root outside `/tmp`; the real `~/.claude` is never written | Inspection |

## Code Quality Verification

- Format: none configured (`format_command` is empty for both components).
- Static analysis: none configured.

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | Hook registered in the `Bash` group right after `loop-command-guard.py` and right before `destructive-guard.py`, and in the `Write\|Edit\|MultiEdit` group; both registration tests pass | TS-11 |
| AC-2 | Write / Edit / MultiEdit: outside → `ask`; inside, `/tmp`, `~/.claude` → no output | TS-1 |
| AC-3 | cwd outside a repository or invalid payload → no output, exit code 0 | TS-2 |
| AC-4 | Worktree cwd writing into the main working tree → `ask` | TS-3 |
| AC-5 | Symbolic link to outside (including not-yet-existing files) and `repo-other` → `ask` | TS-4 |
| AC-6 | Listed `/dev` paths → no output; other `/dev` paths judged | TS-5 |
| AC-7 | Redirection / `tee` / `sed -i` / `cp` / `mv` destinations judged | TS-6 |
| AC-8 | Nesting scope and non-command text | TS-7 |
| AC-9 | Unresolvable destinations not judged; unquoted `~/` expanded | TS-8 |
| AC-10 | Relative destinations after `cd` not judged; subshell `cd` not carried out | TS-9 |
| AC-11 | `CLAUDE_BATCH` downgrade; `allow` never output | TS-10 |
| AC-12 | hook-tests.md section exists; `python3 -m unittest tests.test_cross_repo_write_guard` passes | TS-11 (inspection of `.claude/rules/hook-tests.md` + focused command) |
| AC-13 | README table, Bash count and order agree; `destructive-guard.py` unchanged | TS-11 (inspection of `em-workflow/README.md`; `git diff` from `workflow.implement.base_commit` to the integrated HEAD on `em-workflow/hooks/destructive-guard.py` is empty) |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-11 |
| FR2 | task0001 | TS-1, TS-2 |
| FR3 | task0001 | TS-2, TS-3 |
| FR4 | task0001 | TS-4, TS-8 |
| FR5 | task0001 | TS-1, TS-5 |
| FR6 | task0001 | TS-1, TS-10 |
| FR7 | task0001 | TS-6 |
| FR8 | task0001 | TS-7 |
| FR9 | task0001 | TS-8 |
| FR10 | task0001 | TS-9 |
| FR11 | task0001 | TS-2 |
| FR12 | task0001 | TS-11 |
| FR13 | task0002 | TS-11 |
| FR14 | task0001 | TS-11 |
| FR15 | task0002 | TS-11 |
| FR16 | task0001 | TS-11 |
| NFR1 | task0001 | TS-12 |
| NFR2 | task0001 | TS-13 |
| NFR3 | task0001 | TS-14 |
| NFR4 | task0001 | TS-15 |

## E2E Testing

Not applicable: SPEC.md declares no E2E framework and no E2E command.

## Manual Testing (E2E Not Possible)

- [ ] TS-11 (documentation part): `em-workflow/README.md` has the `cross-repo-write-guard.py` row with both events, states 10 PreToolUse(Bash) hooks in the IMPLEMENTATION.md C1 order, and its opening sentence states no hook count; `.claude/rules/hook-tests.md` has the `## cross-repo-write-guard` section with the run command and the `CASES` shape.
- [ ] TS-12 (test-module part): `tests/test_cross_repo_write_guard.py` imports standard-library modules only.
- [ ] TS-15: every hook run in `tests/test_cross_repo_write_guard.py` passes a substituted `HOME`, and fixture repositories are created under a temporary root outside `/tmp`.

## Performance / Security Verification

- NFR3: git time limit shorter than the hook's 15-second timeout — TS-14.
- TM-1: hook registered on both the `Bash` and `Write|Edit|MultiEdit` matchers, and every FR7 write form within every FR8 scope recognized — checked by TS-11 (registration tests) and the `ask` rows of TS-6 and TS-7.
- TM-2: non-write text (heredoc bodies, quoted strings, comments, `bash -c` strings, `$( )` bodies), descriptor duplication, the listed `/dev` sinks, unresolvable and post-`cd` relative destinations, and unparseable commands produce no output — checked by the no-output rows of TS-5, TS-6, TS-7, TS-8 and TS-9.
- TM-3: comparison only against the cwd's own toplevel, after real-path resolution of destination, toplevel and exclusion roots, at path-component boundaries — checked by TS-3 and TS-4.
- TM-4: git started as an argument vector with no shell; payload text never becomes command-line text — checked by the shell-metacharacter cwd test in `tests/test_cross_repo_write_guard.py` (marker file absent, decision correct).
- TM-5: git time limit with termination and no output on expiry — checked by TS-14.
- TM-6: `allow` never output on any path — checked by TS-10 and by the no-`allow` assertion applied to every hook run in `tests/test_cross_repo_write_guard.py`.
- TM-7: `deny` with a downgrade notice when `CLAUDE_BATCH` is active — checked by TS-10.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS-1 to TS-15) | 15 | 14 | 0 | 1 |
| Success criteria (AC-1 to AC-13) | 13 | 11 | 0 | 2 |
| Requirements coverage (FR1 to FR16, NFR1 to NFR4) | 20 | 17 | 0 | 3 |
| Manual inspection items | 3 | 0 | 0 | 3 |
| Security mitigations (TM-1 to TM-7) | 7 | 7 | 0 | 0 |
| Performance (NFR3) | 1 | 1 | 0 | 0 |
