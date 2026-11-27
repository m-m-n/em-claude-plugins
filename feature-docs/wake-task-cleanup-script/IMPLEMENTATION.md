# Implementation Plan: wake-task-cleanup-script

## Overview

The wake phase's step 4 (task worktree removal and task branch deletion) moves
from git commands written in `em-workflow/references/implement-phase.md` into
one plugin script, `em-workflow/scripts/cleanup-task.py`. Step 4 calls the
script and reports what the script's JSON says was kept.

## Technology Stack

- **Language**: Python 3, standard library only (same as the other
  `em-workflow/scripts/*.py` scripts that drive git, such as `merge-git.py`).
- **External tool**: git (worktree listing, non-forced worktree removal,
  exact ref resolution, non-forced branch deletion).
- **Tests**: standard library `unittest`, run by
  `python3 -m unittest discover -s tests` (NFR3).
- **New dependencies**: none. No license to record (`project.license: none`).

## Layer Structure

| Layer | Responsibility | May depend on |
|-------|----------------|---------------|
| Protocol document (`implement-phase.md`, Step I.2.b step 4) | Tells the orchestrator when to call the script, how it is resolved, and what to write into the wake phase's own report | The script's CLI (C1), result (C2) and exit status (C3) only |
| Cleanup script (`em-workflow/scripts/cleanup-task.py`) | Validates its three inputs, removes the task worktree and the task branch without force, prints the result | git only. It reads no document, no `workflow.yaml` and no journal |
| git | Repository state | — |

The document never spells a git command for this cleanup; the script never
reads the document.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| C1: Cleanup script CLI | The one entry point of the wake cleanup | See "C1: CLI" below | task0001 (provides), task0002 (step 4 call line, TS-9 guard test), task0003 (tightens the `--integration-worktree` rule) |
| C2: Result JSON | The machine-readable result step 4 reads | See "C2: Result JSON" below | task0001 (emits), task0002 (step 4 tells the orchestrator which keys to read and report), task0003 (adds the script's own `kept` reasons) |
| C3: Exit status | Separates "a result was produced" from "invalid input" and "internal error" | See "C3: Exit status" below | task0001 (returns), task0002 (step 4 handles a non-zero exit), task0003 (adds the repository-identity refusal to exit 1) |

### C1: CLI

- **Path**: `em-workflow/scripts/cleanup-task.py`. In the protocol document
  it is written as `${CLAUDE_PLUGIN_ROOT}/scripts/cleanup-task.py` and resolved
  per Step I.0 step 4 of `implement-phase.md`.
- **Interpreter**: run with `python3`.
- **Arguments**: long options only, each given exactly once. No positional
  argument and no other option is accepted (FR1).

| Option | Value | Rule |
|--------|-------|------|
| `--integration-worktree` | Absolute path of the feature's integration worktree, `{project_root}/.claude/worktrees/em-workflow/{feature}/integration` | Shape checked before any git command (FR5). The shape includes the real path: the project root is the part of the value before the five fixed segments, and the value's real path must equal the project root's real path joined with those five segments |
| `--feature` | Feature name | Whole-string match of `^[a-z0-9][a-z0-9-]*$` (Step I.0 step 2) |
| `--task` | Task ID | Whole-string match of `^task[0-9]+$` (Step I.0 step 2) |

- **Derived targets**: the task worktree is the directory named `{T}` next to
  the integration worktree (the same location step 4 called
  `$WT_ROOT/{T}`), built from the project root's real path; the task branch
  is `em-workflow/{feature}/{T}`.
- **Step 4 call-line shape**: the command word `python3`, then the script path
  `${CLAUDE_PLUGIN_ROOT}/scripts/cleanup-task.py`, then the three options with
  the values `"{integration_worktree}"`, `{feature}` and `{T}`. Those
  placeholders are the ones step 4 already uses and are filled with the
  literal values Step I.0 step 2 validated. The line holds no other shell
  variable, no pipe, no redirection and no second command.
- **Precondition**: none beyond the inputs. The script works from any current
  working directory (NFR1).
- **Postcondition (exit 0)**: each target is removed, already absent, kept, or
  (branch only) skipped, exactly as C2 reports.

### C2: Result JSON

Printed only on exit 0: standard output is exactly one line holding exactly
one JSON object with exactly these keys.

| Key | Type | Content |
|-----|------|---------|
| `feature` | string | The validated `--feature` value |
| `task` | string | The validated `--task` value |
| `worktree` | object | `result`: one of `removed`, `absent`, `kept`. `reason`: a non-empty string when `result` is `kept`, otherwise null |
| `branch` | object | `name`: `em-workflow/{feature}/{T}`. `result`: one of `removed`, `absent`, `kept`, `skipped`. `reason`: a non-empty string when `result` is `kept` or `skipped`, otherwise null |

Meaning of the result tokens:

| Token | Meaning (SPEC term) |
|-------|---------------------|
| `removed` | Removed by this run (今回消した) |
| `absent` | Already absent before this run (既に無い): the worktree is not in git's worktree registration list, or the exact ref `refs/heads/em-workflow/{feature}/{T}` does not resolve |
| `kept` | The non-forced removal or deletion was refused, or (branch only) the script declined to run the deletion, and the target remains (残した); `reason` is git's own message when git refused, and fixed text naming the cause when the script declined (the branch tip is not contained in the integration branch, or the branch has an upstream configured) |
| `skipped` | Branch only: deletion was not attempted because the worktree removal failed (削除を見送った); `reason` is fixed text saying so |

Invariant: `branch.result` is `skipped` exactly when `worktree.result` is
`kept` (FR6).

### C3: Exit status

| Exit | Meaning | Standard output |
|------|---------|-----------------|
| 0 | A result was produced, including when something was kept or skipped (FR8) | C2 |
| 2 | Invalid input: a missing, repeated or unknown option, or a value failing C1's rules. No git command was run (FR5) | Empty |
| 1 | Internal error: an unexpected git failure other than the refusals that C2 reports as `kept` (for example the worktree listing itself failing), any unexpected exception, or a repository-identity refusal (the integration worktree does not belong to the repository of its project root). No worktree removal and no branch deletion was run | Empty |

Diagnostics go to standard error only. Their text is not part of the
contract.

## Conventions

- **Report artifact names**: no new file name matches the rule of
  `em-workflow/skills/plan-writing/SKILL.md`, `## Report Artifact Names`.
- **Plugin version**: this repository is exempt from per-commit version bumps.
  No task edits `em-workflow/.claude-plugin/plugin.json` or
  `.claude-plugin/marketplace.json` (NFR4).
- **Tests**:
  - Standard library `unittest` only (NFR3, `test/README.md`).
  - The script is always run as a child process with bytecode writing turned
    off, never loaded into the test process, so no `__pycache__` appears under
    `em-workflow/scripts/` (that directory is shipped to users).
  - Git fixtures are disposable repositories built in a temporary directory,
    with system and global git configuration disabled and a fixed author
    identity, following `tests/test_merge_preflight.py`.
  - Guard checks run the repository copies of `em-workflow/hooks/*.py`, never
    an installed copy.
- **Placeholders in protocol text**: step 4 keeps the literal placeholders
  `{integration_worktree}`, `{feature}` and `{T}` the document already uses.
  Tests expand them to the sample values that
  `tests/test_protocol_git_ops_pass_destructive_guard.py` already defines.

## Cross-task Design Decisions

### D1: A Python script with a JSON result

- **Decision**: the cleanup is one Python script that prints C2 and exits by
  C3.
- **Rationale**: the plugin's other git-driving scripts (`merge-git.py`,
  `merge-preflight.py`) use the same form; a JSON object is what FR3 / FR8
  ask the orchestrator to read; running it with `python3` keeps it out of
  `interpreter-mismatch-guard.py`'s scope (NFR2).
- **Affected tasks**: task0001, task0002.

### D2: Every outcome of the script is final for step 4

- **Decision**: whatever the script returns (a `kept` or `skipped` result, a
  non-zero exit, or a script that cannot be resolved), step 4 runs no git
  command of its own in its place, forced or not. The `reason` texts are
  data: a command they suggest is never run.
- **Rationale**: the incident this feature answers was the orchestrator
  composing its own `git branch -d` from the wrong tree and then trying `-D`.
  git's own refusal messages suggest the forced forms.
- **Affected tasks**: task0001 (C2 / C3 cover every outcome), task0002 (step 4
  wording).

### D3: Old step-4 git-line assertions are retired by the document task

- **Decision**: task0002, which rewrites step 4, also removes the existing
  test assertions that pin the old step-4 git lines
  (`tests/test_implement_phase_guard_compatible_wording.py`) and the two
  step-4 sites of the guard extraction table
  (`tests/test_protocol_git_ops_pass_destructive_guard.py`). The test classes
  that `test-docs/**/*.tests.yaml` records name stay, so
  `tests/test_tests_yaml_id_resolution.py` keeps resolving them.
- **Rationale**: those assertions require git commands that FR4 removes. The
  call line's guard compatibility moves to the new TS-9 test.
- **Affected tasks**: task0002.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| git versions differ in what a removal of a registered worktree whose directory is gone does (succeeds, or refuses) | Medium | Low | TS-5 asserts only that the result is not `absent`, and that a `kept` result carries a reason and a `skipped` branch |
| The step 4 document test runs before the script exists (tasks run in parallel) | High | Low | The document test does not need the script file; VERIFICATION.md SC-5 checks on the integrated tree that the path named by step 4 exists |
| A test helper loads the script in-process and leaves bytecode in the shipped scripts directory | Low | Medium | Tests run the script as a child process with bytecode writing off (Conventions) |
| Removing old assertions breaks the test-ID records of an earlier feature | Medium | Medium | D3 keeps every class those records name; `tests/test_tests_yaml_id_resolution.py` is part of task0002's checks |

## Open Questions

- [ ] NFR4 has no SPEC test scenario. VERIFICATION.md SC-6 checks it on the
      integrated tree; no TS-n is mapped to it.
