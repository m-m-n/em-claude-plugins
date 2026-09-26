# Implementation Plan: destructive-guard-grouping-spec-drift

## Overview

Close the grouping / compound-construct bypass in `em-workflow/hooks/destructive-guard.py`, limit the tar `-C` destination to extract mode, pin every detection-strength change with case-table rows, and revise the prior feature's SPEC.md / REQUIREMENTS.md so they describe the merged implementation. The work is split into three tasks that run fully in parallel: task0001 (grouping and closer handling), task0002 (tar extract mode, destination-family and rm pinning cases, mv relabel) and task0003 (prior-feature document revision).

## Technology Stack

- **Language**: Python 3, standard library only (NFR2).
- **Test harness**: `em-workflow/hooks/tests/run-destructive-guard.py` (case table, `CLAUDE_BATCH` cleared) and the repository unittest suite under `tests/`.
- **New dependencies**: none. No license entry is recorded (`project.license: none`).

## Layer Structure

One hook script, evaluated in three stages inside one process. Dependencies point strictly downward (a later stage never calls back into an earlier one).

1. **Deferral check** — decides whether the command is left to failed-run-cleanup-guard (`matches_target_shape()` over `strip_grouping_prefix()` / `_deferral_head()`). Unchanged by this feature (FR5).
2. **Statement shaping** — splits the command string into statements (including substitution bodies, shell-sink here-docs and the `-c` / eval / here-string payload re-scan) and reduces each statement to the simple command it runs (`statements()`, `head()`, closer handling). Owned by task0001.
3. **Per-statement checks** — `check_rm`, `check_git`, `check_file_destruction`, `check_external`, `check_permissions`, `check_self_modification` (including write-target extraction) and the substitution-headed route. They consume shaped statements and never interpret grouping syntax themselves. task0002 changes only the tar branch of destination extraction.

Verdict aggregation and the final `ALLOW_NON_DESTRUCTIVE` fall-through are unchanged.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| Shaped statement | The token sequence every per-statement check receives | Post: equals what the same command yields when written alone (details below). Pre for consumers: no check needs to recognise grouping syntax or closers itself | task0001 (produces), task0002 (consumes in the tar branch) |
| tar extract-mode rule | Decides whether a tar statement's `-C` / `--directory` value is a write target | Extract mode as defined below; only then is the value a write target | task0002 (implements), task0003 (documents) |
| Write-target sources | The complete list of places the write-target set is drawn from | Sources (a)-(d) as listed below, describing the post-feature implementation | task0002 (tar part of (d)), task0003 (documents all) |
| Case table | `em-workflow/hooks/tests/destructive-guard-cases.json` rows `[expected, label, command]` | Rules below; each task adds one contiguous block, existing rows unchanged except one label | task0001, task0002 |
| em-workflow version fields | `version` in `em-workflow/.claude-plugin/plugin.json` and the em-workflow entry of `.claude-plugin/marketplace.json` | Both equal exactly `0.2.13` after the feature; em-review untouched | task0001, task0002 |

### Shaped statement (contract detail)

Postconditions of statement shaping, which every per-statement check may rely on:

1. Grouping and compound syntax at command position — the subshell opener `(` (unquoted operator token only), the brace-group opener `{`, the reserved words `if` / `then` / `elif` / `else` / `while` / `until` / `do` / `!`, a case-pattern prefix, and a function-definition prefix — is not part of the command the checks see. The command word located by `head()` is the command the construct runs.
2. No bare closer token `)` is among the command's arguments. Closers and terminators (`)`, `}`, `fi`, `done`, `esac`, `;;`) yield no command of their own.
3. A closer fused with a following redirect operator (`)>`, `)>>`, `)2>` and similar) is handled as a closer plus a real redirect. The redirect target is visible to the checks only as a redirect target.
4. Redirects attached to a closer or terminator remain visible to write-target extraction.
5. `head()` keeps its existing 2-tuple return shape.

Consumer precondition: "the first argument" of a command means the first token after the command word that `head()` locates. A check never adds its own grouping or closer handling.

### tar extract-mode rule (contract detail)

- A tar statement is in extract mode when its arguments contain any of: `-x`; `--extract`; `--get`; a single-dash short-option cluster containing `x` (for example `-xzf`); or, as the first argument after the command word and not beginning with a dash, a word containing `x` (the traditional dashless form, for example `xzf`).
- In extract mode, the value of `-C` / `--directory` is a write target in every spelling the implementation already recognises: separate, attached, `=` form and short-option cluster tail.
- In every other mode (create `-c` / `--create`, list `-t` / `--list`, and any other) that value names a directory that is read and is not a write target.
- Each tar statement is decided from its own arguments only. The two sides of a pipeline of two tar commands are two independent decisions.
- Long options other than `--extract` and `--get` never indicate extract mode, even when their name contains the letter x.

### Write-target sources (contract detail)

The write-target set is drawn from exactly these sources after this feature:

- (a) output redirects;
- (b) `INPLACE_WRITERS` and `sed -i`;
- (c) rm / chmod / chown: every non-flag argument. mv: every non-flag argument (mv unlinks each source) plus the `-t` / `--target-directory` value. cp / ln: the last positional argument after value-flag stripping, or only the `-t` / `--target-directory` value when that flag is given;
- (d) command-specific destinations: rsync last positional argument (after value-flag stripping); git clone last positional argument when there are at least two positionals; tar `-C` / `--directory` in extract mode only; unzip `-d`; curl `-o` / `--output`; wget `-O` / `--output-document`.

### Case table (contract detail)

- Row format: expected verdict, label, command. The expected verdict is the verdict the runner observes with `CLAUDE_BATCH` cleared (NFR6).
- Each task adds its rows as one contiguous block. No existing row is deleted, reordered, or changed in command or expected verdict. The only change to an existing row is the mv label owned by task0002 (FR9).
- The command lists of task0001 and task0002 are disjoint by construction. A task never adds a command string that already exists in the table (NFR4). If an identical command already exists with the same expected verdict, the existing row already pins it and is not re-added. If it exists with a different expected verdict, the task stops and reports a plan deviation.

### em-workflow version fields (contract detail)

- Target value `0.2.13` in both places (a target value, not an increment). The em-review version is not changed.
- Every task that changes a file under `em-workflow/` (task0001, task0002) sets both fields to `0.2.13` in its own change set. task0003 changes no file under `em-workflow/` and does not touch either field.

## Conventions

- **Region ownership in destructive-guard.py**: task0001 edits statement shaping only (`statements()`, `head()`, closer handling, the `head()` and `strip_grouping_prefix()` docstrings, and the related `main()` comment). task0002 edits only the tar handling inside destination extraction. Neither task edits per-check logic to handle closers or grouping, and neither edits the other's region.
- **Test first (NFR3)**: add the task's case rows, run the runner, confirm red on the rows the change is meant to flip, then change the code. The red run is recorded in the task's test record.
- **Static analysis only (NFR1, NFR2)**: no command is run, no substitution is evaluated, no filesystem call or subprocess is added, and nothing outside the standard library is imported.
- **Locality**: any grouping-aware skip is documented as local to `destructive-guard.py`, following the `substitution_only` precedent. `em-workflow/hooks/failed-run-cleanup-guard.py` is never modified.
- **Stricter direction**: when a token's role cannot be told apart (a quoted `{` at command position carries no quote provenance), it is treated as the syntax that exposes a command, unless a case row in the SPEC pins the allow verdict.
- **Case labels**: follow the existing label style of the case table (short Japanese description of the construct and the expected outcome).

## Cross-task Design Decisions

### D1: Grouping and closers are handled once, in statement shaping

- **Decision**: grouping unwrap, closer removal and fused closer-redirect splitting happen in statement shaping, upstream of every per-statement check. No individual check is edited for closers or grouping.
- **Rationale**: FR3 and FR5 require the same behaviour in every check; a single place guarantees it, and it keeps task0001 out of the destination-extraction region task0002 edits.
- **Affected tasks**: task0001, task0002.

### D2: tar mode is decided per tar statement

- **Decision**: the tar extract-mode rule above is evaluated per statement from that statement's own arguments.
- **Rationale**: the pinned pipeline row pairs a create-mode tar with an extract-mode tar; each side must get its own decision.
- **Affected tasks**: task0002, task0003.

### D3: Prior-feature documents describe the post-feature behaviour

- **Decision**: task0003 documents the write-target sources and the tar extract-mode rule exactly as pinned in this document, even though the code in its own worktree still treats tar `-C` as a destination in every mode.
- **Rationale**: tasks run in parallel; the tar change lands through task0002. The shared contract above is the single source both tasks follow.
- **Affected tasks**: task0002, task0003.

### D4: Each em-workflow-changing task carries the version target value

- **Decision**: task0001 and task0002 each set both version fields to `0.2.13` in their own change set.
- **Rationale**: `.claude/rules/core-plugin-version-bump.md` requires the version change in the same change as the plugin content change, and the user-level plugin-version guard rejects commits that change plugin files without it. Identical edits on both task branches merge without conflict.
- **Affected tasks**: task0001, task0002.

### D5: Case-table merge policy is a union

- **Decision**: when the two task branches conflict in the case table, the resolution keeps both added blocks in full. Block order is irrelevant because every row is evaluated independently.
- **Rationale**: both tasks append rows near the same end of the array, so a textual conflict is likely even though the rows never overlap.
- **Affected tasks**: task0001, task0002.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Textual merge conflict in the case table between task0001 and task0002 | High | Low | D5 union policy; disjoint command lists |
| Grouping unwrap turns a currently allowed data-form command into ask / deny (false positive stops an unattended run) | Medium | High | FR1 group (7) and FR7 allow rows, all pre-existing rows kept, full runner must pass (NFR5) |
| Case context carried across statements misreads a subshell's trailing `)` as a case-pattern terminator | Medium | High | Pinned subshell rows (ask) plus case rows split by pipe and newline in task0001 |
| Shaping change silently alters a pinned verdict (deferral or silent rows) | Medium | High | Deferral stage untouched (FR5); invariant tests in the unittest suite |
| tar mode detection misreads an option value or long option as a mode indicator | Medium | Medium | tar extract-mode rule above; create / list / extract rows including the dashless and long-option forms |
| Plugin-version guard rejects a task commit that changes em-workflow files | Medium | Medium | D4; land the version change together with the task's em-workflow content change |
| Revised prior-feature documents drift from the code again | Low | Medium | D3 single shared contract; task0003 cross-checks the unchanged facts against the implementation |

## Open Questions

None.
