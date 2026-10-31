# Implementation Plan: unattended-merge

## Overview

Add the batch-only skill `/em-workflow:merge`, which takes a feature completed by develop to its base branch without a human: deterministic decision scripts under `em-workflow/scripts/`, an orchestrating `em-workflow/skills/merge/SKILL.md` that performs every guard-sensitive operation as a direct Bash call, a merge-result contract with a renderer, and a narrowly scoped `gh pr merge` allow rule in destructive-guard.

## Technology Stack

- **Language**: Python 3, standard library, for every new script and test; Markdown for the skill and the contract document.
- **YAML reading**: PyYAML in safe-loading mode. Existing em-workflow Python scripts already use it, so it is not a new dependency (license: MIT).
- **External tools**: git and gh, invoked as child processes (not bundled).
- **Tests**: standard-library unittest under `tests/`; hook cases through `em-workflow/hooks/tests/run-destructive-guard.py`.
- **New third-party dependencies**: none (`project.license: none`).

## Layer Structure

| Layer | Members | Responsibility | May call |
|---|---|---|---|
| Invocation | loop-develop dispatcher through claude-batch | Starts `/em-workflow:merge --batch <feature>`; reads only the final assistant message | — |
| Orchestration | `em-workflow/skills/merge/SKILL.md` | Flow control, conflict-resolution judgment, every guard-sensitive operation, lock lifecycle, final message | Decision scripts, renderer, direct git / gh calls |
| Decision scripts | `merge-preflight.py`, `merge-git.py`, `merge-pr.py`, `merge-lock.py`, `merge-ci-wait.py` | Deterministic judgments; read-mostly | git, gh (read-only use), `em-workflow/hooks/bash_guard.py` list mode (preflight only) |
| Output | `merge-result.py`, `em-workflow/references/merge-result.md` | Render the structured result; own its contract | Nothing |
| Enforcement | `em-workflow/hooks/destructive-guard.py` and the other existing hooks | Judge every Bash call the skill makes | — |

Dependency direction: Orchestration calls Decision scripts and Output; nothing calls Orchestration back. Scripts never call or import one another (preflight's call to bash_guard's list mode is the only cross-file call).

## Shared Components

| Component | Responsibility | Contract (summary; detail below) | Used by tasks |
|---|---|---|---|
| C1 Script conventions | Invocation, output, exit codes, identifier validation, time limits | One JSON object on stdout; exit 0 = decision made (including stop) | task0001-task0006, task0008 |
| C2 Vocabularies | Result values, route values, closed reason-code set | Values below are the complete sets; `em-workflow/references/merge-result.md` is the product SSOT and lists exactly these | task0001-task0006, task0008 |
| C3 `merge-result.py` | Render the final result | One argument: path to a JSON input document; prints a conformant result | task0001, task0008 |
| C4 `merge-preflight.py` | Target resolution, precondition, review findings, command approval | Fixed check order; proceed fields below | task0002, task0003 (TS1 full chain), task0008 |
| C5 `merge-git.py` | Remote choice, local already-merged, worktree state, base integration, base-moved check, main-tree readiness | Subcommands below | task0003, task0008 |
| C6 `merge-pr.py` | GitHub repository resolution, PR lookup, pre-merge PR state | Subcommands below | task0004, task0008, task0010 |
| C7 `merge-lock.py` | Repository-wide merge lock | token / hold / verify below | task0005, task0008 |
| C8 `merge-ci-wait.py` | Bounded wait for PR checks | One bounded invocation per call; absolute deadline echoed | task0006, task0008 |
| C9 Canonical `gh pr merge` form | The single shape destructive-guard allows and the skill emits | Shape below | task0007, task0008, task0012 |

### C1 Script conventions

- **Location and name**: `em-workflow/scripts/<name>.py`, each starting with a python3 shebang; the skill invokes them with python3, the same way develop's SKILL.md invokes the plugin's scripts.
- **Arguments**: long options only (`--project-root`, `--feature`, ...). `--project-root` is the main working tree root that preflight reports; every script also works when called from any worktree of the repository.
- **Output**: exactly one JSON object on one stdout line. Common keys: `outcome` (per-subcommand token), `reason` (a C2 reason code when `outcome` is `stop`, otherwise null), `detail` (string, empty when there is nothing to add). Subcommand-specific keys are listed below. Diagnostics go to stderr only.
- **Exit codes**: 0 when a decision was produced, `stop` outcomes included; 2 for missing or malformed arguments; any other non-zero value for an internal failure. The skill maps a non-zero exit or a stdout that is not one JSON object to `internal_error`.
- **Identifier validation** (every script re-validates what it receives and what it emits):
  - feature name: `^[a-z0-9][a-z0-9-]*$`
  - commit SHA: 40 lowercase hexadecimal characters
  - PR number: positive decimal integer
  - lock token: 32 lowercase hexadecimal characters
  - branch name and remote name: a valid git name made only of letters, digits, `.`, `_`, `-`, `/`, not starting with `-`
- **Time limits**: every git / gh child process has a time limit, and one invocation finishes within 600 s (CI wait's default budget is 540 s).
- **Side effects**: only these three; everything else is read-only:
  - `merge-git.py integrate` fetches and merges inside the integration worktree
  - `merge-git.py base-check` fetches
  - `merge-lock.py hold` takes the lock and writes the holder record
- **Untrusted values**: values derived from repository files or gh output are emitted only after validation; free text goes only into `detail`.

### C2 Vocabularies

- **result**: `merged` | `already_merged` | `not_merged`
- **route**: `pr` | `local` | `none` (route not decided yet)
- **reason codes** (closed set; empty for `merged` / `already_merged`, mandatory for `not_merged`):

| Code | Condition | Emitted by |
|---|---|---|
| `invalid_arguments` | `--batch` given but the remaining arguments are not exactly one feature name | SKILL.md |
| `invalid_feature_name` | Feature name fails the pattern | SKILL.md, preflight |
| `integration_branch_missing` | `em-workflow/<feature>/integration` does not exist | preflight |
| `record_unreadable` | workflow.yaml or the latest review round record is missing, unparseable or malformed | preflight |
| `base_branch_invalid` | base_branch missing, unsafe, or (local route) absent locally | preflight, merge-git route |
| `precondition_unmet` | A step is not completed / skipped, or verify's result is fail | preflight |
| `unresolved_findings` | Latest round has critical/high findings whose resolution is neither fixed nor declined | preflight |
| `commands_unapproved` | A non-empty verification command is not approved, or approval cannot be confirmed | preflight |
| `remote_unresolved` | No remote can be chosen, an unsafe remote name, or gh's default repository differs from the chosen remote's | merge-git route, merge-pr repo |
| `remote_not_github` | gh cannot resolve the chosen remote to a GitHub repository | merge-pr repo |
| `pr_closed` | Only closed unmerged PRs exist, or the PR is no longer open at the pre-merge check | merge-pr |
| `pr_draft` | The open PR is a draft | merge-pr |
| `pr_conflicting` | gh reports the PR as conflicting at the pre-merge check | merge-pr state |
| `pr_create_failed` | `gh pr create` failed | SKILL.md |
| `lock_busy` | Another run holds the merge lock | merge-lock |
| `lock_lost` | This run does not (or no longer) hold the lock | merge-lock verify |
| `worktree_not_clean` | Integration worktree dirty, on another branch, or inconsistently registered | merge-git worktree-state |
| `conflict_unattributable` | A conflict cannot be attributed to a base-side feature with a readable spec | SKILL.md |
| `verification_failed` | A build / test / e2e command failed or timed out | SKILL.md |
| `push_rejected` | `git push` of the integration branch was rejected | SKILL.md |
| `ci_failed` | A PR check failed or was cancelled | merge-ci-wait |
| `ci_timeout` | Checks still pending at the 60-minute deadline | merge-ci-wait |
| `pr_head_moved` | The PR head differs from the pushed / verified SHA | merge-ci-wait, merge-pr state |
| `base_moving` | The base moved again after 3 redos | merge-git base-check |
| `main_tree_not_ready` | Main working tree not on base_branch or not clean | merge-git main-tree |
| `merge_failed` | `gh pr merge` or the main-tree `git merge` failed | SKILL.md |
| `git_failed` | An unexpected git failure (fetch, worktree add, non-conflict merge failure, merge abort) | merge-git, SKILL.md |
| `internal_error` | Script crash, unparseable script output, rejected renderer input | SKILL.md, merge-result |

### C3 `merge-result.py`

- **Input**: one positional argument, the path of a JSON input document the skill writes with its file-writing tool (never assembled through the shell). Fields: `result`, `feature`, `route`, `reason`, `pr_url`, `merge_commit`, `worktree_removed` (`true` / `false`), `detail`, and optional `project_root` (used only to make paths repository-relative; never printed).
- **Output keys, fixed order**: `merge_result`, `feature`, `route`, `reason`, `pr_url`, `merge_commit`, `worktree_removed`, `detail`. Every value is a string; the layout, quoting and escaping follow `em-workflow/references/batch-terminal-line.md`.
- **Postcondition**: stdout holds one conformant result and nothing else, exit 0. Invalid or unreadable input produces `not_merged` / `internal_error` instead (the invalid value is never echoed). Exit non-zero only when nothing could be printed; the skill then prints the contract document's fallback result verbatim.

### C4 `merge-preflight.py`

- **Arguments**: `--project-root`, `--feature`.
- **Check order** (first failure decides): feature pattern → integration branch exists → workflow.yaml readable at the branch tip → base_branch valid → precondition → latest review round → command approval.
- **Outcomes**: `proceed` | `stop` (`invalid_feature_name`, `integration_branch_missing`, `record_unreadable`, `base_branch_invalid`, `precondition_unmet`, `unresolved_findings`, `commands_unapproved`).
- **`proceed` fields**: `project_root` (absolute main working tree root), `worktree_path` (absolute `.claude/worktrees/em-workflow/<feature>/integration` under it), `integration_branch`, `integration_tip`, `base_branch`, `commands` (ordered list of `component` / `field` / `command`, non-empty build → test → e2e per component, components in name order), `review_round` (integer or null).

### C5 `merge-git.py`

| Subcommand | Arguments | Outcomes (stop reasons) | Extra fields |
|---|---|---|---|
| `route` | `--project-root`, `--base` | `local` / `remote` / stop (`remote_unresolved`, `base_branch_invalid`) | `remote` |
| `merged` | `--project-root`, `--feature`, `--base` | `merged` / `not_merged` (local route only) | — |
| `worktree-state` | `--project-root`, `--feature` | `absent` / `clean` / `merge_in_progress` / stop (`worktree_not_clean`) | `worktree_path` |
| `integrate` | `--project-root`, `--feature`, `--base`, optional `--remote` | `merged_clean` / `up_to_date` / `conflict` / stop (`git_failed`) | `integrated_base`, `head`, `conflicted_paths` (repository-relative) |
| `base-check` | `--project-root`, `--base`, optional `--remote`, `--integrated-base`, `--redo-count` | `unchanged` / `redo` / stop (`base_moving`, `git_failed`) | `current_base` |
| `main-tree` | `--project-root`, `--base` | `ready` / stop (`main_tree_not_ready`) | — |

- **`integrate` postcondition**: on `conflict`, the merge is left in progress for the skill and the integration tip is unchanged.
- **`base-check` postcondition**: `redo` when the base moved and `--redo-count` is 0-2; stop `base_moving` when it moved at count 3.

### C6 `merge-pr.py`

| Subcommand | Arguments | Outcomes (stop reasons) | Extra fields |
|---|---|---|---|
| `repo` | `--project-root`, `--remote` | `github` / stop (`remote_not_github`, `remote_unresolved`) | `repo` (owner/name) |
| `resolve` | `--project-root`, `--repo`, `--feature`, `--base`, `--integration-tip` | `merged` / `open` / `none` / stop (`pr_closed`, `pr_draft`) | `pr_number`, `pr_url`, `head`, `merge_commit`, `create_head`, `create_base` (those relevant to the outcome) |
| `state` | `--project-root`, `--repo`, `--pr`, `--head`, `--base` | `ready` / `merged` / stop (`pr_closed`, `pr_draft`, `pr_conflicting`, `pr_head_moved`) | `pr_url`, `merge_commit` (on `merged`) |

- Every argument in the table is mandatory; a missing one is exit 2.
- **`resolve` `merged`**: only a MERGED PR whose head commit equals `--integration-tip` (the integration commit the run is about to merge, or has just merged) counts. A MERGED PR with any other head is ignored, and the decision continues with the open / draft / closed / none classes.
- **`state` `merged`**: only when the PR's head equals `--head`; a merged PR with another head stops `pr_head_moved`.
- **`state` base**: a PR whose base branch differs from `--base` stops `pr_head_moved`.
- **SKILL.md values**: `--integration-tip` is preflight's `integration_tip` before integration and the verified `head_sha` after the merge; `--base` is base_branch.

### C7 `merge-lock.py`

| Subcommand | Arguments | Behavior |
|---|---|---|
| `token` | — | Prints outcome `token` with a fresh `token` |
| `hold` | `--project-root`, `--feature`, `--token` | Takes an exclusive non-blocking lock on `em-workflow-feature-merge.lock` in the git common dir, writes the holder record (feature, token, process id, acquisition time with UTC offset), prints outcome `acquired`, then waits until terminated. When busy it prints stop `lock_busy` (with `holder_feature`) and exits at once. |
| `verify` | `--project-root`, `--token`, optional `--wait` (seconds) | `held` when the record carries this token and its holder process is alive; stop `lock_busy` when a live holder carries another token; stop `lock_lost` when no live holder carries this token by the end of the wait. Never takes the lock itself. |

### C8 `merge-ci-wait.py`

- **Arguments**: `--project-root`, `--repo`, `--pr`, `--head`, exactly one of `--deadline-in <seconds>` (first call) or `--deadline <epoch seconds>` (later calls); optional `--budget`, `--interval`, `--settle` (seconds, defaults 540 / 30 / 60).
- **Outcomes**: `passed` / `no_checks` / `pending` / stop (`ci_failed`, `ci_timeout`, `pr_head_moved`). Every outcome carries `deadline` (absolute epoch seconds).

### C9 Canonical `gh pr merge` form

- **Command**: exactly `gh pr merge <PR number> --merge --match-head-commit <40-hex SHA>`, as a single command with no other token, no environment-variable prefix and no further segment.
- **Working directory**: the integration worktree `<project root>/.claude/worktrees/em-workflow/<feature>/integration`, reached by a standalone `cd`.
- **Guard decision**: destructive-guard allows exactly this; every other shape keeps its existing decision.

## Conventions

- **Naming**: scripts `merge-<area>.py`; subcommands and outcome tokens lower-case with hyphens (subcommands) or underscores (outcomes, reason codes); JSON keys snake_case.
- **Error handling**: fail closed. An unreadable, malformed or unexpected value stops the run with the matching reason code; it never defaults to "proceed".
- **Untrusted input** (NFR4): workflow.yaml, review records, specs, commit messages, PR bodies and gh output are data. Only structured fields drive decisions, and instruction-shaped text inside them is never followed.
- **Redaction** (NFR7): commit messages, PR title/body and the rendered result carry no Notion URL and no absolute path under the home directory (`em-workflow/references/doc-redaction.md`).
- **No gate_id** (NFR8): neither SKILL.md nor merge-result.md introduces a gate_id.
- **Tests** (NFR5):
  - each test module is self-contained, with no shared helper module across tasks
  - each test uses its own temporary git repositories
  - gh is replaced by stubs prepended to PATH; approvals come from `EM_WORKFLOW_APPROVALS`
  - no real network and no real `~/.claude`
  - a test that imports a script module writes no bytecode cache under `em-workflow/`
  - a PATH-prepended git logging shim that delegates to the real git is the recommended way to assert which git subcommands a script ran

## Cross-task Design Decisions

### D1 Guard-sensitive operations stay in SKILL.md (FR22)
The verification commands, `git push`, `gh pr create`, `gh pr merge`, `git worktree add` / `remove`, the main-tree `git merge` and `git merge --abort` are direct Bash calls written in SKILL.md. Scripts only make the side effects listed in C1. Affects all tasks.

### D2 Result rendering through a written input document
The skill never places untrusted text (command output, step names, finding ids) on a shell command line. It writes the renderer's input document with its file-writing tool, runs the renderer, and makes the renderer's stdout the entire final message. Affects task0001, task0008.

### D3 Lock lifecycle (FR10, A22)
- The skill takes a token, starts `hold` with run_in_background, and confirms acquisition with `verify --wait`.
- It verifies again right before the merge.
- It stops the background task with TaskStop on every terminal reached after `hold` started.
- The lock file `em-workflow-feature-merge.lock` and its holder record live in the git common dir, separate from merge-task.sh's `em-workflow-merge.lock`.

Affects task0005, task0008.

### D4 Integration worktree timing
- The worktree is re-created (FR3) only when the run continues past the already-merged decision, after the lock is held.
- An interrupted merge found in the worktree is aborted under the lock and the integration redone.
- Cleanup skips removal when the worktree is absent.
- A `not_merged` result keeps the worktree (FR19, A26).

Affects task0003, task0008.

### D5 FR9 timing
`merge-pr.py resolve` stops only on closed-only and draft PRs (A25). Mergeability, draft state, open state and head equality are re-checked by `state` right before the merge, because the base integration is what resolves a pre-existing conflict. Affects task0004, task0008.

### D6 Repository pinning
gh reads made by scripts name the resolved repository explicitly. `gh pr create` and the canonical `gh pr merge` rely on gh's default repository for the project, so `merge-pr.py repo` requires that default to equal the chosen remote's repository. Affects task0004, task0008.

### D7 In-run counters (NFR3, A27)
The redo count and the CI deadline are values the skill carries within one run; nothing is persisted. `base-check` enforces the limit of 3 redos, and `merge-ci-wait.py` echoes the absolute deadline it was given or computed. Affects task0003, task0006, task0008.

### D8 Precondition includes verify's result
Beyond every step being completed / skipped, a verify step whose `result` is `fail` fails the precondition (FR4's parenthetical). Affects task0002.

### D9 Merge commits and PR text
- Integration merges use `--no-ff --no-edit`.
- The main-tree merge is `git merge --no-ff --no-edit em-workflow/<feature>/integration`.
- Hooks are never bypassed.
- Commit messages and the PR title/body are fixed shapes filled only with validated identifiers (feature, base branch, integration branch).

Affects task0003, task0008.

### D10 Documentation ownership
- task0007 edits the destructive-guard row of the hook table in `em-workflow/README.md`.
- task0008 adds the merge row to the skill table in the same file.
- task0009 updates the descriptions in `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`, and raises the minor component of the em-workflow version in those two places to the same value (FR23).

### D11 TS1 ownership across parallel tasks
task0003 owns the local-route integration test. Its core case uses only `merge-git.py` plus emulation of the skill's direct operations. A second case prepends `merge-preflight.py`; it is skipped, with a reason naming the missing script, only when that script is absent (inside task0003's own worktree). The verify phase confirms that both cases ran.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| A write guard denies the renderer input location under CLAUDE_BATCH | Medium | High (no final result) | task0008 picks a location outside every working tree that the plugin's write guards leave silent under CLAUDE_BATCH; the contract's fallback result covers renderer failure |
| Checks not yet registered right after push read as "no checks" | Medium | High (merge without CI) | `--settle` window before concluding `no_checks` |
| A verification command needs more than 600 s | Low | Medium | Bash timeout → `verification_failed` with the command named |
| An earlier MERGED PR hides integration commits added after it merged | Low | Medium | `resolve` counts a MERGED PR only when its head is the current integration tip (C6), matching FR7's local-route criterion that the tip is contained |
| gh reports mergeable UNKNOWN right after push | Medium | Low | Treated as not conflicting; GitHub rejects a real conflict → `merge_failed` |
| TS1's full-chain case silently skipped | Low | Medium | VERIFICATION.md requires both TS1 cases to report ok |
| CLAUDE_BATCH ask→deny downgrade behaves differently for the new cases | Low | High | task0007 asserts both decisions per case through the runner |

## Open Questions

- [ ] The PR-route end-to-end flow (push, PR creation, CI wait, merge) needs a disposable GitHub repository; it is listed as a manual check.
- [x] FR7 and a MERGED PR whose head is not the current integration tip: resolved in review round 1 rework. Such a PR does not count as already merged (C6).
