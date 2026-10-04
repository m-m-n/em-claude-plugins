# Implementation Plan: sca-per-project-scan-binding

## Overview

Bind the SCA axis (`scan-dependencies.py scan`) to the project directory that
holds each changed manifest / lockfile: one scan unit per (ecosystem, project
directory), npm / cargo / go launched with that directory as their working
directory, and every project that cannot be bound reported as the path-free
reason `<ecosystem>_project_unbindable` instead of being folded into a
root-level scan.

## Technology Stack

- **Language**: Python 3, standard library only — the existing
  `em-workflow/scripts/scan-dependencies.py` (its optional PyYAML import is
  unchanged).
- **Data**: `em-workflow/references/vuln-scanners.yaml` (scanner registry, data
  only).
- **Tests**: `unittest` modules under `tests/`, standard library only; scanners
  are replaced by executable stubs on a temporary PATH (NFR4).
- **New dependencies**: none (`project.license: none`; nothing to record).

## Layer Structure

Inside `scan-dependencies.py scan`. Each layer only calls layers below it.

| # | Layer | Responsibility | Side effects |
|---|-------|----------------|--------------|
| 1 | Selection | select_ecosystems and the unsupported-manifest reasons (unchanged) | none |
| 2 | Ecosystem gate | validate_ecosystem_entry and executable resolution, once per ecosystem (FR9) | PATH lookup only |
| 3 | Grouping and binding | run_scan only: verified project grouping (FR1, FR10) and the binding check (FR4, FR5) | reads path metadata; never writes, never launches |
| 4 | Job construction | build_scan_job / build_scan_jobs (FR3, FR12) | none (pure) |
| 5 | Execution | run_ecosystem_command and judge_scan_outcome (unchanged) | launches one scanner per job |
| 6 | Normalization | per-ecosystem normalizers (unchanged) | reads manifests confined to the project root (existing) |
| 7 | Aggregation | skipped / skip_reason / findings / summary (FR7, FR8) | none |

build_scan_jobs is the pure counterpart of layers 2 + 4 with lexical grouping;
run_scan does not call it (A-11).

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| build_scan_job (cwd rule and target precondition owned by task0002) | Builds one job mapping from a validated registry entry, a target, the project root and an already-resolved absolute executable path | **Pre**: the entry passed validate_ecosystem_entry; for npm / cargo / go the target follows the Target convention below and is project-relative; a pip lockfile target comes with a prepared file. **Post**: a mapping with ecosystem / manifest (= the target) / argv / cwd / env. argv — npm / cargo / go: the executable path followed by the registry args verbatim; pip: its existing forms unchanged. cwd — npm / cargo / go: the project root joined lexically with the target's directory part, and exactly the string form of the project root when that part is empty; pip: the string form of the project root. env — that ecosystem's child environment. Opens no file, inspects no path on disk, launches nothing. **Violation**: an npm / cargo / go target that is absolute, contains a `..` segment or contains NUL, and a pip lockfile target without a prepared file, raise JobConstructionError (a ValueError); no job is produced. | task0001 (calls it per group from build_scan_jobs), task0002 (owns the cwd rule and the target precondition; calls it from run_scan) |
| Target convention | The single string used as an npm / cargo / go job's manifest and as every finding's `file` label for that job | Given a group directory D (project-relative, `/`-separated, no empty or `.` segment, `""` for the root) and the basename B of the file manifest_file_for selected from the group: target is B when D is `""`, otherwise D, `/`, B. pip keeps the raw selected changed-file string as its target. | task0001 (D is lexical), task0002 (D is verified on real paths) |
| manifest_file_for | Selects one target from changed files: pip lockfile-first, npm / cargo / go manifest-first, input order | Behavior unchanged. Called once per group with that group's files in their original input order (FR2). Neither task changes its selection rule; only task0002 may edit its docstring. | task0001, task0002 |
| Group order | Deterministic processing order | Ecosystems keep registry order; within one ecosystem, groups are processed in ascending plain-string order of D (the root `""` first) (FR1, NFR2). | task0001, task0002 |
| Registry npm args and go child-environment pins (owned by task0001) | Keep npm and go inside the bound project directory and read-only (FR11) | npm registry args: audit, --json, --workspaces=false. go pins: GOENV off, GOWORK off, GOFLAGS -mod=readonly (replacing the empty GOFLAGS pin), GOPROXY unchanged. npm, cargo and pip pins unchanged; nothing added for cargo. | task0001 (owner), task0002 (inherits them through build_scan_job; asserts nothing about them) |
| Skip-reason vocabulary | Machine-stable, path-free reason tokens | Existing tokens unchanged. New token `<ecosystem>_project_unbindable` (npm / cargo / go only) for any changed file, group or project that cannot be bound. A token never contains path or file-derived text (NFR3). An ecosystem-level reason appears at most once per ecosystem. | task0001 (build_scan_jobs), task0002 (run_scan) |

## Conventions

- **Region ownership inside scan-dependencies.py** (tasks are implemented in
  parallel): task0001 edits only build_scan_jobs, its own new private
  lexical-grouping helper, and the child-environment pin table with its comment
  block. task0002 edits build_scan_job, run_scan, the result helpers,
  manifest_file_for's docstring, and its own new private verified-grouping and
  binding helpers. New helper names carry their own concern ("lexical" for
  task0001, "verified" / "binding" for task0002), so the two tasks never define
  the same name.
- **Test-file ownership**: tests/test_sca_scan_invocation.py → task0001.
  tests/test_sca_scan_normalization.py → task0001 for the command-assembly
  expectation only, task0002 for the run_scan fixtures only.
  tests/test_sca_scan_execution.py and tests/test_sca_pip_lockfile_audit.py →
  task0002. em-workflow/references/review-phase.md → task0003. Each task puts
  its new assertions in its own new test module.
- **Error handling**: an exception raised while resolving or inspecting a
  reviewed path is contained and turned into that ecosystem's path-free reason;
  it never escapes `scan`, and it never triggers a fallback to the root or an
  ancestor directory.
- **Tests**: standard library only; no real scanner is executed; updated
  fixtures keep every assertion they had (FR14).

## Cross-task Design Decisions

### D1: Filesystem binding checks live in run_scan; job construction stays pure

FR12 / A-11. build_scan_jobs groups lexically and filters only what is
lexically impossible to bind (an absolute, `..`-escaping or NUL-containing
npm / cargo / go path), adding `<ecosystem>_project_unbindable`; run_scan
groups on real paths and performs every filesystem check. Affected: task0001,
task0002.

### D2: The cwd rule ships with run_scan

run_scan's end-to-end working-directory assertions depend on build_scan_job's
cwd rule, so task0002 owns that change. task0001's build_scan_jobs tests assert
grouping through job manifests and reasons, never through cwd. Affected:
task0001, task0002.

### D3: pip grouping never rejects a path

FR10 keeps pip's validation unchanged, so pip grouping only partitions: no pip
path is filtered or turned into an unbindable reason, and the existing pip flow
keeps reporting its existing reasons for absolute, escaping or unresolvable pip
paths. Affected: task0001, task0002.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| task0001 and task0002 edit scan-dependencies.py at the same time and collide | Medium | Low | Region ownership above; adjacent hunks are resolved by the parent-side adoption protocol |
| Existing run_scan tests keep passing for the wrong reason once binding exists (a substring such as "npm" also matches npm_project_unbindable) | Medium | Medium | FR14 fixtures create manifest + anchor so the original launch path runs; task0002 confirms those tests still launch their stub |
| Real-path resolution behaves unusually for odd paths (NUL, very long names, dangling symlinks) | Low | Medium | Exceptions are contained as unbindable; dedicated cases in TS-5 |
| build_scan_jobs (lexical D) and run_scan (verified D) spell the same target differently | Low | Low | Target convention pinned above; both sides tested against it |

## Open Questions

- [ ] None.
