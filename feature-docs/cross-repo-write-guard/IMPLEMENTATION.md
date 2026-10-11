# Implementation Plan: cross-repo-write-guard

## Overview

Add a self-contained PreToolUse hook to em-workflow that sends file writes
whose destination lies outside the cwd's git toplevel to confirmation (ask,
downgraded to deny under unattended runs), register it for the `Bash` and
`Write|Edit|MultiEdit` matchers, test it, and document it.

## Technology Stack

- **Language**: Python 3, standard library only (NFR1) — hook and tests.
- **Test runner**: the standard-library unit-test runner already used by the
  `repo-tests` component.
- **External program**: git, started only for the toplevel lookup (NFR2).
- **New dependencies**: none. `project.license` is `none`; no dependency
  license needs recording.

## Layer Structure

| Layer | Location | Responsibility | May depend on |
|-------|----------|----------------|---------------|
| Hook runtime | `em-workflow/hooks/cross-repo-write-guard.py` | Reads one PreToolUse payload, judges write destinations, emits at most one decision | Python standard library, git (as an external process) |
| Registration | `em-workflow/hooks/hooks.json` | Decides when Claude Code runs the hook | The hook's path (C1) |
| Tests | `tests/` | Verify hook behavior (as a subprocess) and registration (as data) | C1, C2, C3 |
| Documentation | `em-workflow/README.md`, `.claude/rules/hook-tests.md` | Describe the hook, its registration and its test procedure | C1, C2, C3 |

Dependency direction: tests and documentation depend on the contracts below;
the hook depends on nothing inside the repository (it imports no repository
module).

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| C1: Hook identity and registration layout | Where the hook lives and where it is registered | Script path `em-workflow/hooks/cross-repo-write-guard.py`. Command form `python3 "${CLAUDE_PLUGIN_ROOT}"/hooks/cross-repo-write-guard.py`, timeout 15, a statusMessage present. PreToolUse `Bash` group: immediately after `loop-command-guard.py`, immediately before `destructive-guard.py`; the group then holds 10 entries. PreToolUse `Write\|Edit\|MultiEdit` group: after `gitleaks-write-guard.sh`. The same single script serves both groups. | task0001 (implements), task0002 (documents) |
| C2: Hook decision behavior | What the hook outputs for a payload | Pre: one PreToolUse payload as JSON on stdin. Post: either no output, or exactly one decision whose `permissionDecision` is `ask` — `deny` when `CLAUDE_BATCH` is set to anything other than empty, `0`, `false`, `no` — with a reason prefixed `[cross-repo-write-guard]` naming each outside destination's absolute path and the toplevel (plus a downgrade notice on deny). `allow` is never output. Exit code is always 0. Judged: the `file_path` of Write / Edit / MultiEdit; for Bash, the statically resolvable destinations of the FR7 forms within the FR8 scope. Never judged: destinations under `/tmp` or `~/.claude/`, the listed `/dev` sinks (FR5), unresolvable destinations (FR9), relative destinations after a working-directory change (FR10). The comparison base is solely the payload cwd's `git rev-parse --show-toplevel` (FR3). Any failure yields no output (FR11). | task0001 (implements), task0002 (summarizes in README) |
| C3: Hook test module | How the hook's tests are run and extended | Module `tests/test_cross_repo_write_guard.py`, run with `python3 -m unittest tests.test_cross_repo_write_guard`. Bash judgment cases are rows of the module-level table `CASES`, each `(期待する判定, ラベル, コマンド)` with expected `ask` or `silent`. Write / Edit / MultiEdit, the `CLAUDE_BATCH` downgrade and invalid input are separate tests. | task0001 (implements), task0002 (documents in hook-tests.md) |

## Conventions

- **Fail-open**: every failure path of the hook ends with no output and exit
  code 0 (FR6, FR11). Documentation describes it that way.
- **Decision vocabulary**: `ask`, `deny` and `silent` (no output) are used
  with the same meaning in tests and documents.
- **destructive-guard.py**: no task modifies
  `em-workflow/hooks/destructive-guard.py` (FR16).
- **Plugin version fields**: no task edits a plugin version field; the
  repository's automation handles them.
- **Document language**: each document keeps its existing language and the
  style of its neighboring entries/sections.

## Cross-task Design Decisions

### D1: One self-contained hook file

- **Decision**: the whole judgment lives in the single file named by C1 and
  imports only the standard library; no helper module is added.
- **Rationale**: FR1 registers one script. Importing a sibling module from the
  plugin's hook directory would make the interpreter write a bytecode cache
  inside the installed plugin, contradicting NFR2 (the hook writes no files).
  A single new file also cannot be split across parallel tasks without an
  add/add merge conflict.
- **Affected tasks**: task0001 (implements), task0002 (documents one script).

### D2: Registration travels with the hook

- **Decision**: the hooks.json registration and the two registration-test
  updates belong to the same task as the hook script.
- **Rationale**: tasks run fully in parallel in isolated worktrees. Checks on
  the registration may require the registered script to be present, which
  holds only in the worktree that creates it.
- **Affected tasks**: task0001 (owns registration), task0002 (writes the
  README's count and order from C1, not from its own worktree's hooks.json,
  which still has the pre-change 9 Bash entries).

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| README's Bash hook count/order drifts from hooks.json | Low | Low | Both derive from C1; VERIFICATION.md TS-11 cross-checks them on the integrated tree |
| A false-positive ask stops unattended runs (ask becomes deny) | Medium | High | THREAT-MODEL.md TM-2; `silent` rows in `CASES` pin the non-write forms |
| A check that reads both hooks.json and README (for example the plugin-invariants check) passes only on the integrated tree | Low | Low | Run every component's test command in the verify phase on the integrated tree |

## Open Questions

- [ ] None blocking.
