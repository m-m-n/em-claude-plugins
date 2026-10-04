# Implementation Plan: sca-python-lockfile-audit

## Overview
The pip axis of `scan-dependencies.py scan` audits a changed poetry.lock /
Pipfile.lock by turning its pins into exact `name==version` requirement lines
handed to pip-audit, and returns fixed skip reasons when the lockfile or its
direct-dependency declaration file cannot be resolved. The work is one task
(task0001); this document fixes the stage structure and contracts that task
and any later rework task on this path must keep.

## Technology Stack
- **Language**: Python 3 — the existing script `em-workflow/scripts/scan-dependencies.py` and the existing unittest suite under `tests/`.
- **Parsing**: the standard-library TOML parser (poetry.lock, pyproject.toml, Pipfile) and the standard-library JSON parser (Pipfile.lock) only (NFR4).
- **External tool**: pip-audit, already registered in `em-workflow/references/vuln-scanners.yaml` (entry unchanged, FR3).
- **New dependencies**: none. `project.license` is `none`, so there is no license constraint and no new dependency license to record.

## Layer Structure
The pip lockfile path inside `scan`, in call order. `run_scan` calls each
stage; no stage calls back into an earlier one.

1. **Selection** (pure) — which changed file is pip's target (C2).
2. **Preparation** (reads project files; writes only outside the project
   root) — lockfile conversion (C3), then the declaration check (C4), then the
   prepared-file scope (C5).
3. **Job construction** (pure) — `build_scan_job` builds one job per prepared
   file (C6). It never reads or writes a file and never launches a process
   (NFR2).
4. **Execution** — the existing `run_ecosystem_command`, once per job,
   unchanged.
5. **Normalization** — the existing `normalize_pip`, called with the
   lockfile's project-relative path as the manifest, so the finding `file` is
   the lockfile (FR10); directness compares canonical names (C1, FR9).
6. **Aggregation** — `run_scan`: findings, skip reasons (existing
   `skip_reasons` path, FR12) and summary notes.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| C1 Canonical package name | PEP 503 name form for comparison, de-duplication and grouping | Pre: any string. Post: lower-cased, every run of `-`, `_` and `.` replaced by a single `-`; pure. | task0001 |
| C2 pip target selection (`manifest_file_for`, pip branch) | Which changed file pip audits | Pre: pip was selected (existing `select_ecosystems`). Post: the first changed file, in `changed_files` order, whose basename is in the existing pip lockfile set; when there is none, the same file as before this feature. npm / cargo / go results unchanged. | task0001 |
| C3 Lockfile conversion | Lockfile content to auditable pins | Pre: project root and a project-relative path whose basename is poetry.lock or Pipfile.lock. Post: exactly one of (a) unconvertible, or (b) an ordered list of one or more requirement groups plus a non-negative excluded-entry count. Each group is a sorted list of `canonical-name==version` lines in which each canonical name appears at most once. Reads only that file, and only when its resolved real path is inside the project root. Writes nothing. Never raises for any file content. Same input, same output. | task0001 |
| C4 Declaration check | Resolves the FR7 declaration file before any launch (A4) | Pre: project root and the selected lockfile path. Post: `resolved` or `not found`. poetry.lock maps to the sibling pyproject.toml and Pipfile.lock to the sibling Pipfile (the same mapping `_pip_manifest_candidate` returns). `not found` when the file is missing, unreadable, not valid TOML, or resolves outside the project root. Reads only; never raises. | task0001 |
| C5 Prepared-file scope | Lifetime of the temporary requirements files | Pre: the groups from C3. Post: inside the scope there is one file per group, in group order, holding exactly that group's lines; each file is outside the project root, created exclusively under a unique unpredictable name with owner-only access (TM-6). On scope exit, normal or exceptional, every file is removed (NFR1). No file path appears in the scan result (NFR3). | task0001 |
| C6 `build_scan_job` lockfile form | Job for one prepared file | Pre: a validated pip registry entry, an already-resolved absolute executable path, the lockfile's project-relative path, and a prepared file path. Post: argument vector = executable, the registry `target_flag`, the prepared file path, `--no-deps`, `--disable-pip`, then the registry `args` — with today's registry exactly the FR3 form; job manifest = the lockfile path; pure. Jobs for requirements.txt / pyproject.toml are unchanged. A pip lockfile manifest without a prepared file is rejected; the directory form is never produced for a lockfile. | task0001 |

## Conventions
- **Untrusted content never raises out of `scan`**: every read, parse or
  shape failure of the lockfile or the declaration file maps to a fixed skip
  reason or to an entry exclusion (TM-4).
- **No fallback**: a lockfile target never falls back to a manifest audit or
  a directory audit (FR5, TM-2).
- **Machine-stable identifiers**: `pip_lockfile_unconvertible` and
  `pip_direct_manifest_not_found` are pip skip reasons and travel the existing
  `skip_reasons` path (sorted, joined with `+`, FR12);
  `pip_lockfile_entries_unpinnable` is a counts-only summary note in the FR6
  wording. No text taken from a lockfile or a declaration file enters the
  result.
- **Left as is**: the registry pip entry, `ALLOWED_EXECUTABLES`,
  `ECOSYSTEM_LOCKFILES`, the child-environment pins (NFR6), the pyproject.toml
  direct-name parser (A7), `tests/test_sca_scan_normalization.py` (TS10) and
  `test-docs/review-sca-axis/task0010.tests.yaml` (A9).
- **Tests**: standard library only; the script is loaded by file path; a stub
  scanner on a restricted PATH; no real pip-audit and no network (NFR5).
- **Plugin version**: this repository is exempt — version bumps are
  automated after merge — so no task edits a `plugin.json` or
  `.claude-plugin/marketplace.json` (NFR7).

## Cross-task Design Decisions

### D1: One task
Every end-to-end scenario (TS1, TS2, TS4-TS7, TS9, TS11) exercises selection,
conversion, the declaration check, the job form and aggregation together.
Tasks run fully in parallel, so splitting these stages would leave the owner
of the wiring unable to pass its own tests in its worktree. The change stays
one task even though its Acceptance Criteria exceed the usual size guideline.
Affected: task0001.

### D2: Requirement lines use the canonical name
De-duplication (FR2) and splitting (FR4) work on C1 names, so every line is
written with the canonical name. "A name appears once per file" is then
checkable by text, and FR9 makes the spelling irrelevant to directness.
Affected: task0001.

### D3: Check order and the unpinnable note
Conversion runs first, then the declaration check. The first failure decides
pip's single reason, and pip-audit is launched only after both pass (A4). The
`pip_lockfile_entries_unpinnable` note appears only when at least one
pip-audit run was launched for the lockfile and at least one entry was
excluded. It goes after the existing `pip_severity_undetermined` note.
Affected: task0001.

### D4: Version order for splitting
FR4 / A5 order each name's distinct versions by plain string order. PEP 440
ordering would need a non-standard-library package (NFR4). The order only
decides which file holds which version, and every version is audited.
Affected: task0001.

### D5: Partial failure of split runs
Following A6, pip counts as scanned when at least one run completed. The
reasons of runs that did not complete are de-duplicated and added to the skip
reasons, and the findings of completed runs are kept, in run order.
Affected: task0001.

### D6: Interpreter without the standard-library TOML parser
The module still loads (the same guarded-import shape the script already uses
for its optional YAML dependency). Any TOML input is then treated as
unparseable, so poetry.lock targets become `pip_lockfile_unconvertible` and
TOML declaration files `not found`. npm / cargo / go keep working.
Affected: task0001.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| The real pip-audit treats the lockfile argument vector differently from the stub used in tests | Low | High (every lockfile scan not completed) | The argument vector is fixed by FR3; one manual check with the real tool in VERIFICATION.md |
| pip-audit reports a name spelled differently from the declaration | Medium | High (a direct dependency read as transitive, finding dropped) | C1 on both sides (FR9) |
| Python older than the standard-library TOML parser | Low | Medium | D6 |
| String order differs from PEP 440 order | Medium | Low | D4: only file placement depends on it |
| Wide edits to one large script collide with unrelated concurrent work | Low | Medium | D1 keeps the change in one task; existing regions outside the pip path stay untouched |

## Open Questions
- [ ] Changes that touch more than one pip project are out of scope (A8); SPEC.md says a follow-up task is filed for them, and no task in this plan files it.
