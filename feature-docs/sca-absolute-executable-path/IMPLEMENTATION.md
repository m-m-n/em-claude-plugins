# Implementation Plan: sca-absolute-executable-path

## Overview
The SCA scan in `em-workflow/scripts/scan-dependencies.py` stops using empty
and relative PATH entries. Executable resolution searches only absolute
entries, so every scan job's argv[0] is an absolute path whatever its cwd. The
PATH handed to each scanner child keeps only absolute entries. task0001 owns
resolution (FR1-FR3) and task0002 owns the child PATH (FR4). The FR5 comment
updates are split between the two tasks by location (D2).

## Technology Stack
- **Language**: Python 3, standard library only (NFR1).
- **Tests**: standard-library unittest, run as `python3 -m unittest discover -s tests`.
- **New dependencies**: none. Nothing to record against `project.license`.

## Layer Structure
The layers inside `scan-dependencies.py` stay as they are:

1. **Planning**: `build_scan_jobs` validates each selected registry entry,
   resolves its executable once (`resolve_executable`) and emits `ScanPlan`s
   that carry that executable. task0001 changes resolution here.
2. **Job construction** (pure, NFR1): `build_scan_job` composes argv
   (argv[0] = the plan's executable, never re-resolved), cwd and env
   (`build_child_env`). task0002 changes `build_child_env` only.
3. **Run**: `run_scan` executes the plans, and `run_ecosystem_command`
   launches argv with the job's cwd and env. This layer does not change.

Dependencies still run planning -> construction -> run. No new call edge is
added.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| Absolute-entry rule (a rule each task applies itself, not a shared symbol; see D1) | Decide which entries of a path-list value may be used | Pre: a path-list string, split on the platform's path-list separator. Post: exactly the entries that are non-empty and absolute by the platform's absolute-path test. Each is kept as written (no normalization, no trailing-separator trimming, no de-duplication) and in its original order. `~` and environment variables are never expanded, so `~/bin` is relative. No implicit current-directory entry is added on any platform. | task0001 (search list), task0002 (child PATH) |
| `resolve_executable(name)` | Resolve one scanner executable during planning | Pre: `name` is an allowlisted bare executable name (planning validates the registry entry before it resolves). Search list: the process PATH when the variable is present (an empty value counts as present and yields no entries); otherwise the platform default search path that SPEC FR1 names (`os.defpath`), read at call time. Post: for the first absolute entry, in original order, that holds an existing, non-directory file named `name` that the current user may execute, returns that entry joined with `name`, unnormalized and therefore absolute. Returns none when no entry qualifies. The one-argument signature is unchanged. | owner task0001; every launch exercised by task0002's run_scan tests goes through it |
| `build_child_env(ecosystem, environ=None)` | Build the explicit child environment of one scan job | Pre: `environ` is a mapping and defaults to the process environment. Post: the pass-through keys other than PATH are copied as before. PATH is set to the rule's entries from `environ`'s PATH, joined with the platform path-list separator. There is no PATH key when `environ` has no PATH or no entry survives. The ecosystem pins are applied on top as before. The function is lexical only: it opens no file, inspects no filesystem state and starts no process. The signature is unchanged. | owner task0002; every launch exercised by task0001's run_scan tests goes through it |
| Scan job / launch path (unchanged) | `build_scan_job` + `run_ecosystem_command` | argv[0] is the plan's executable. env is `build_child_env`'s result. The cwd rules do not change (root for pip, bound project directory for go, isolation directory for npm / cargo). | task0001, task0002 (integration tests through run_scan) |

## Conventions
- **Error handling**: an empty or relative entry is skipped silently, with no
  exception, warning or new output. A scanner found only under such entries
  produces the existing `<ecosystem>_tool_not_found` reason, once per
  ecosystem and with no plan. No new skip reason is added. Reasons stay fixed
  tokens and carry no path text.
- **Unchanged surfaces (NFR2)**: `ALLOWED_EXECUTABLES`, `ECOSYSTEM_ENV_PINS`,
  `ECOSYSTEM_LOCKFILES`, the key list of `CHILD_ENV_BASE_KEYS`,
  `em-workflow/references/vuln-scanners.yaml`, the skip-reason vocabulary and
  `em-workflow/references/review-phase.md`. The git and task-system
  entry-point invocations are not touched (SPEC A3).
- **Test modules**: each task adds its own new module under `tests/` (the
  names are fixed in the task plans). The module loads the script by file
  path and owns its stubs and harness: it copies existing patterns and never
  imports from another test module. A test restores any process cwd,
  environment variable or module attribute it changes. New `tests/test_sca_*.py`
  modules import only standard-library modules.
- **Cross-task test independence**: every test passes whether or not the
  other task's change is merged. task0001's tests never assert the child
  environment's PATH. task0002's tests never assert argv[0], and they place no
  executable under the relative PATH entries they use.
- **Comments and docstrings**: in English, matching the module's existing
  style.

## Cross-task Design Decisions

### D1: The absolute-entry rule is applied in two places, with no shared helper symbol
The rule is a single filtering step. Each task applies it inside its own
function (resolution in task0001, the child PATH in task0002). Neither task
introduces a module-level helper for it, because two tasks running in parallel
would both have to create the same symbol. The Shared Components row is the
single statement of the rule, so both sides implement the same behavior.
Affected: task0001, task0002.

### D2: FR5 comment ownership by location
- task0001: the `resolve_executable` docstring, the "Scan job construction"
  section comment and the `build_scan_jobs` docstring.
- task0002: the comment directly above `CHILD_ENV_BASE_KEYS` and the
  `build_child_env` docstring.

Neither task edits the other's locations. The section comment ends one line
above the `CHILD_ENV_BASE_KEYS` comment (see Risk Assessment).

### D3: FR3 follows from the resolver's postcondition; job construction is unchanged
`build_scan_job` keeps using the plan's executable as argv[0]. No
re-resolution and no new absolute-path check are added there. This keeps
`build_scan_job` pure, and existing tests that pass placeholder absolute
executables keep working. Once resolution returns only absolute paths, every
job's argv[0] is absolute for every cwd (root, nested go project directory,
npm / cargo isolation directory). Affected: task0001 (verifies it), task0002
(relies on the unchanged launch path).

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| task0001's edit to the "Scan job construction" section comment and task0002's edit to the adjacent `CHILD_ENV_BASE_KEYS` comment conflict on merge | Medium | Low | D2 splits the locations. A conflict is resolved by the parent-side adoption protocol. |
| On Windows the standard resolver may search the current directory implicitly | Low (the repository runs on Linux) | High | The shared contract forbids any implicit current-directory entry and requires an absolute result |
| A reviewer whose scanner is reachable only through relative PATH entries now gets `<ecosystem>_tool_not_found` | Low | Low | This is the intended behavior (FR2). The reason is visible in the scan result. |
| With PATH unset, the search list is now the default search path constant, while the previous resolver consulted the system configuration path first | Low | Low | SPEC FR1 / A1 pin this. TS-9 covers it. |
| Existing tests that rely on a relative PATH value | Low | Low | Only the `test_ac2` fixture in `tests/test_sca_scan_unchanged_surfaces.py` does, and task0002 changes it (NFR3). The other fixtures use absolute temporary directories. |

## Open Questions
- [ ] None
