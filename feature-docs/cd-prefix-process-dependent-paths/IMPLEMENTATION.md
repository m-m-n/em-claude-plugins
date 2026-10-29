# Implementation Plan: cd-prefix-process-dependent-paths

## Overview

The cd prefix path check `is_below(path, area)` in `em-workflow/hooks/bash_guard.py` refuses every path that is, or passes through, a location under /proc or /dev/fd (FR1, FR2). A refused form is judged as if it had no cd prefix (FR3). The rule is stated in the hook's module docstring and in the protocol's Verbatim execution rule (FR5), and is pinned by regression tests (FR6).

## Technology Stack

- **Language**: Python 3, standard library only (NFR1, NFR6).
- **Test runner**: the standard unittest discovery over `tests/` (workflow.yaml `project.components.main.test_command`).
- **New dependencies**: none. `project.license` is `none`; no license record is needed beyond this line.

## Layer Structure

| Layer | Location | Responsibility | May depend on |
|-------|----------|----------------|---------------|
| Hook decision table | `hook_main` in `bash_guard.py` | refusal, exact approval, cd prefix allow, unapproved deny, silence | cd prefix candidate |
| cd prefix candidate | `is_cd_prefixed_approved` | syntax, approval, area lookup, then the path check | path check |
| Path check | `is_below(path, area)` and its private helpers | the FR1 exclusion, then the existing logical/physical rule | the file system (read-only queries), no child process |
| Documentation | module docstring of `bash_guard.py`, `em-workflow/references/command-execution-protocol.md` | state the same rule in prose | nothing |
| Tests | `tests/test_bash_guard_cd_prefix.py` | contract tests through the hook subprocess and through the loaded module | the hook module, the protocol text |

The decision table and the cd prefix candidate do not change (NFR7, FR4). All behavioral change is confined to the path check.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| `is_below(path, area)` | path check of the cd prefix allow | Pre: `path` is the double-quoted text from the cd prefix, `area` is the realpath of the worktree area. Post: False when the "under /proc or /dev/fd" predicate below holds for (a) the path as written, (b) any stage reached while resolving the logical path component by component, including the target of each link followed, or (c) any stage reached while resolving the physical path component by component, including the target of each link followed. When none holds, the result is exactly what the existing logical/physical rule returns today. A link loop or exceeding the followed-link bound is False (NFR5). Any OSError or ValueError is False (NFR4). Signature, caller and return type are unchanged (NFR7). Starts no child process (NFR3). | task0001 (implements), task0002 (documents) |
| "Under /proc or /dev/fd" predicate | lexical classification of one path text | Split the path into components; ignore empty components and `.`. True when the first remaining component is `proc`, or the first two are `dev` then `fd`. /proc itself and /dev/fd itself are included. `..` is not interpreted (the resolution stages cover `/x/../proc`). False for `/procfoo`, for `/dev` alone, and for a `proc` or `dev/fd` directory that is not directly below the root. Pure: no file-system access. | task0001 (implements), task0002 (documents) |
| Shared test infrastructure in `tests/test_bash_guard_cd_prefix.py` | fixture, hook runner, module loader, wording helpers | `Fixture`, `decide`, `_load_guard_module`, `_verbatim_execution_rule`, `_states_new_path_condition` and `_states_single_realpath_condition` keep their current behavior. `Fixture.run_hook(command, cwd, store=None, extra_env=None)` gains one optional keyword parameter for the hook subprocess's own working directory; when it is omitted the subprocess runs in `cwd`, so every existing call keeps its meaning. | task0001 (adds the parameter), task0002 (uses the wording helpers read-only) |

## Conventions

- **Error policy**: the path check never raises and never writes to stderr; every failure inside it, including the new stage checks, makes it False (NFR4). The hook keeps exit code 0.
- **Executable text**: no identifier or string literal in `bash_guard.py` contains the substring `status` (NFR2). Docstrings are exempt.
- **Test case style**: hook-level cases use the existing `(expected decision, label, command template)` tuples with `@TOKEN@` placeholders and `subTest` per case; module-level cases call the loaded module's `is_below` with the fixture area.
- **Platform guard**: a test that needs /proc skips itself when `/proc/self` is not a directory (FR6).
- **Isolation**: new tests use only the standard library and the existing `Fixture` isolation; no real `~/.claude` state and no real `workflow.yaml` is read (NFR6). New fixture layout lives in the new test classes' own setup or under a dedicated subdirectory of the area, so the layout seen by existing tests is unchanged.
- **Placement in the shared test file**: task0001 adds its new test classes after `TestNonDirectoryBeforeDotDot` and before the wording helpers; task0002 adds its tests inside or directly after `TestPathConditionWording`. Neither task edits the other's region. Only task0001 edits the test module docstring.
- **Placement in `bash_guard.py`**: task0001 edits only the path-check functions and their docstrings; task0002 edits only the module docstring.
- **Plugin version**: this repository bumps plugin versions through its own automation, so no task lists `plugin.json` or `marketplace.json` among its files and no plan text addresses the version.

## Cross-task Design Decisions

### D1: One rule, stated identically in code and prose

The meaning pinned under Shared Components is the single source for both the implementation (task0001, including the function docstring of `is_below`) and the two prose places (task0002). In prose the rule reads: a path under /proc or /dev/fd fails the path check; this is judged on the path as written, on each stage reached while resolving the logical path and the physical path component by component, and on the target of each link followed, never on the final realpath alone. Affected: task0001, task0002.

### D2: No exception for the /proc/self/root/.. prefix

A path that starts with /proc/self/root is refused like any other /proc path (FR2). This overrides feature is-below-physical-fallback's FR3/AC-1; that feature's documents stay untouched (SPEC A2). Neither prose place may say the prefix form is allowed. Affected: task0001 (the two existing tests change), task0002 (wording).

### D3: Scope limits

A procfs mounted elsewhere than /proc, other per-process file systems (SPEC A4), and a link changed between the hook's decision and Bash's cd (SPEC A5) stay out of scope. No task adds handling or wording for them. Affected: task0001, task0002.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| The stage-by-stage walk resolves differently from the kernel and skips a stage that Bash visits | Medium | High | The walk mirrors kernel resolution (absolute link target restarts at the root, `..` applies to the location already reached); link-target cases in task0001 AC-3 cover the indirect routes |
| The walk treats a missing component as an error, turning the existing fallback-allow forms (logical path absent) into False | Medium | Medium | task0001 Design: an absent component or a non-directory with components remaining ends the walk without refusal; the existing fallback-allow cases must keep passing (task0001 AC-7) |
| A prose edit inserts a blank line into the `cd prefix:` paragraph, cutting it short and failing `STATEMENT_PATTERNS` | Low | Medium | task0002 AC-1 |
| Both tasks edit `bash_guard.py` and `tests/test_bash_guard_cd_prefix.py` in parallel | High | Low | Disjoint regions per the placement conventions; conflicts follow the parent-side adoption protocol |
| /proc-based tests fail on a platform without /proc | Low | Low | Platform guard convention |

## Open Questions

- None.
