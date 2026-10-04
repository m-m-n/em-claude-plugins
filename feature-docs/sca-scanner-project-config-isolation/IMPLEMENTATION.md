# Implementation Plan: sca-scanner-project-config-isolation

## Overview

Axis-2 npm and cargo scans run inside a per-group isolation directory created outside the reviewed tree that holds only copies of the validated scan inputs, so the scanners no longer discover the reviewed project's own `.npmrc` / `.cargo/audit.toml`. pip and go scans, the environment pins, grouping, the binding check, processing order and result labels stay as they are.

## Technology Stack

- **Language**: Python 3, standard library only — `em-workflow/scripts/scan-dependencies.py`
- **Registry**: YAML — `em-workflow/references/vuln-scanners.yaml`
- **Tests**: standard-library unittest with offline recording stubs placed on PATH (NFR4); run by `python3 -m unittest discover -s tests`
- **New dependencies**: none. No license entry is needed (`project.license` is `none` and nothing new is introduced).

## Layer Structure

1. **Registry** (`vuln-scanners.yaml`) — per-ecosystem scanner argv building blocks, including the cargo entry's explicit lockfile target flag.
2. **Job assembly** (`build_scan_job`) — pure: from the registry entry, the scan group and, for npm / cargo, the prepared isolation paths, it produces argv, cwd and the label. It never opens a file and never starts a process (NFR1).
3. **Run side** (`_scan_bound_group`, `run_ecosystem_command`) — binding check (unchanged) → isolation preparation (npm / cargo only) → job assembly → scanner launch with the job's cwd → outcome judgment (unchanged) → isolation removal.
4. **Aggregation** (`run_scan`) — group iteration, processing order and `skip_reason` assembly unchanged; the new reason tokens enter through the existing assembly rule.
5. **Documentation** (`em-workflow/references/review-phase.md`, axis 2) — describes the contracts below for readers of the review phase and states nothing beyond them.

Allowed dependency direction: aggregation → run side → job assembly → registry. Job assembly never calls back into the run side.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| Isolation failure reason tokens | Identify a scan unit whose isolation failed | Exactly two fixed tokens: `npm_isolation_failed` and `cargo_isolation_failed`. The unit's status is `not_completed`. The token carries no path and no other variable text. It enters `skip_reason` through the existing assembly rule. | task0001 (produces), task0002 (documents) |
| npm / cargo execution-location contract | Where and how the two scanners run | Pre: the group passed the binding check. Post (npm): the child runs with cwd = a per-group isolation directory whose real path is outside the real project root, containing copies of `package.json` and the selected anchor (`npm-shrinkwrap.json` preferred over `package-lock.json`); argv stays `[<npm>, audit, --json, --workspaces=false]`. Post (cargo): the child runs with cwd = a per-group isolation directory containing a copy of `Cargo.lock`; argv is `[<cargo-audit>, audit, --file, <copy path>, --json]` with no `--url` and no `--db`. The isolation directory is removed on every outcome. There is never a fallback to running inside the reviewed tree. | task0001 (produces), task0002 (documents) |
| Unchanged scan surfaces | What this feature must not change | `run_scan`'s entry signature and result shape are unchanged apart from the two new reason tokens. pip and go jobs (argv / cwd / env) are unchanged. `ECOSYSTEM_ENV_PINS` keeps every ecosystem's current value. Each child's environment is the runner's environment with the existing pins applied: HOME is passed as is and no new pin is added. | task0001 (preserves), task0002 (guards with tests) |
| Trusted configuration scope (FR11) | One statement of what the reviewer controls | HOME, the npm globalconfig, the Cargo-home `audit.toml` and the advisory DB are managed by the reviewer and cannot be changed by the PR author. This feature disables or overrides none of them. | task0001 (code comment at `ECOSYSTEM_ENV_PINS`), task0002 (`review-phase.md`) |

## Conventions

- **Error handling**: a failure in creating, copying or validating the isolation directory means the scanner is not launched, anything already created is removed, and the unit becomes `not_completed` with its ecosystem's isolation token. The remaining groups are still scanned, and completed groups' findings stay in the result. Execution never falls back to the reviewed tree.
- **No paths in reasons**: `skip_reason` and summary carry fixed tokens only, never a path string (NFR3). Exception text from filesystem operations does not reach them.
- **No writes under the reviewed tree**: nothing is created or written under the real project root (NFR2). Containment decisions compare real paths by path components, not by string prefix.
- **Tests**: standard-library unittest only, offline and deterministic, never requiring a real npm or cargo-audit (NFR4). Recording stubs are placed on PATH by the test itself. Each new test file owns its own stub harness. No test helper module is shared across tasks, so each task stays self-contained in its worktree. A test restores every environment variable and process-wide temp-directory setting it changes.
- **Documentation (FR13)**: docstrings, comments and `review-phase.md` describe the isolation directory as the npm / cargo execution location and contain no remaining statement that those scanners run with the reviewed project root as cwd.

## Cross-task Design Decisions

### D1: Isolation directory instead of additional environment pins

Decision: npm and cargo are protected by running them from an isolation directory outside the reviewed tree (FR1, FR2). The existing environment pins are kept unchanged, and no new pin overrides reviewer-managed configuration (FR10, FR11).
Affected tasks: task0001 (implements), task0002 (documents and guards the unchanged pins).

### D2: Task split along files, not along the execution chain

Decision: all code changes and their run-level regression tests are in task0001. task0002 owns the `review-phase.md` documentation and guard tests for the unchanged surfaces. The two tasks touch disjoint files.
Rationale: tasks run fully in parallel. The run-level stub tests (FR12) exercise the whole chain together (isolation, job assembly, launch, removal), so any split along that chain would leave each half unable to pass its own tests in its own worktree. task0002's guard tests assert only behavior that holds both before and after task0001 merges.
Affected tasks: task0001, task0002.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Existing SCA tests assert the old npm / cargo cwd or the old cargo argv | High | Medium | task0001 lists the existing SCA test files and updates those assertions to the new contract. It keeps the coverage they provide. |
| The process-wide temp-directory selection is cached, so a redirection in one test leaks into later tests | Medium | Medium | Each redirection case resets that setting and restores it afterwards (Conventions, Tests) |
| A scanner leaves files in the isolation directory, or is still running at timeout, so removal fails | Low | Low | Removal is recursive and runs after the run step has returned, on every outcome |
| task0001 accidentally changes a pip / go job or a pin value | Low | High | task0002's guard tests fail on the merged suite in the verify phase |
| The owner-only permission assertion relies on POSIX permission semantics | Low | Low | The project's test environment is POSIX (Linux) |

## Open Questions

- [ ] Configuration planted by another local account in an ancestor of the system temp directory is not addressed by any SPEC.md / REQUIREMENTS.md requirement. REQUIREMENTS.md 2.2 lists the reviewer and the PR author only. No mitigation is planned in this feature.
- [ ] SPEC.md does not define the behavior when removing the isolation directory itself fails. task0001 leaves the scan unit's recorded outcome unchanged in that case and emits no path (NFR3).
