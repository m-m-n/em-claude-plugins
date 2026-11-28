# Implementation Plan: sca-pip-no-build-exec

## Overview

Every pip scan unit of SCA axis 2 is audited by starting pip-audit only on prepared requirements files that hold statically extracted, validated `name==version` lines. The flag and arguments come from a per-target-form table in the registry, and an input that cannot be fully pinned reports a fixed `skip_reason` token.

## Technology Stack

- **Language**: Python 3, standard library. `tomllib` is used only through the script's existing guarded import, and PyYAML only through the script's existing registry loader.
- **Tests**: `unittest`, standard library only, run by `python3 -m unittest discover -s tests`. Scanners are executable stubs on a PATH that holds only the stub directory.
- **New dependencies**: none (no license to record).

## Layer Structure

All layers live in `em-workflow/scripts/scan-dependencies.py`, except the registry.

1. **Registry (data)**: `em-workflow/references/vuln-scanners.yaml` names which tool serves pip, and the target form with its flag and arguments.
2. **Planning (pure)**: `validate_ecosystem_entry` and `build_scan_jobs`. The planning flow is unchanged; validation gains the target-form check.
3. **Extraction (pure, read-only)**: static pin extraction from a pip manifest (new). It depends only on the existing confinement, include, logical-line and option-splitting helpers and on `_pip_pin_is_valid` / `canonical_pip_name`.
4. **Run side**: `_scan_pip_group` (manifest route, changed) and `_scan_pip_lockfile` (lockfile route, unchanged except where its flags come from). Both call the prepared-file scope, `build_scan_job`, `run_ecosystem_command` and `normalize_pip`.
5. **Result composition**: `run_scan` (unchanged). Reasons become `skip_reason`, findings are kept, and the summary notes are added.

Dependencies point downward only: the run side uses extraction and the registry, and extraction uses nothing from the run side.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| pip target form (registry data) | The only source of pip's target flag and arguments | The pip entry carries `target_forms` holding the form `prepared_requirements`, with `target_flag` (a non-empty string) and `args` (a list of strings), both under the existing `args` token rule. The pip entry has no top-level `args` or `target_flag`. Post: `validate_ecosystem_entry` returns None for it. Any violation yields `pip_target_forms_invalid` and no pip plan | task0001 |
| `extract_pip_manifest_pins(project_root, manifest_file)` returns `(pins, excluded_count)` | Statically extracts auditable pins from one pip manifest unit | Pre: the basename of `manifest_file` is `requirements.txt` or `pyproject.toml`, and the path is the plan's raw target. Post: `pins` is a set of (PEP 503 canonical name, version) pairs, each matching the pin rule and passing `_pip_pin_is_valid`. `excluded_count` is a non-negative integer counting the items left out. The function reads only files whose resolved location lies inside `project_root`, opens no constraint file, writes nothing, starts no process, uses no network and never raises for any content, shape or path. The same input gives the same output | task0001 |
| Prepared-file scope (existing `prepared_requirements_files(groups)`) | Holds the inputs pip-audit is allowed to read | Unchanged contract: one file per group, in group order, holding exactly that group's lines. Each file is created with a unique, unpredictable name and owner-only access in the system temporary directory. Every file created is removed on scope exit, normal or exceptional | task0001 |
| pip job construction (`build_scan_job` for ecosystem pip) | Builds the only pip command form | Pre: `prepared_file` is non-empty and the entry carries the `prepared_requirements` form. Post: argv is the executable path, then the form's `target_flag`, then the prepared file, then the form's `args` in order. The cwd is the project root, the job's manifest is the reviewed file (the label), and the environment is unchanged. A missing prepared file or form raises `JobConstructionError`. This holds for every pip manifest kind | task0001 |
| Manifest-unit skip tokens | Fixed reasons for partly pinnable and unpinnable manifest units | `pip_manifest_entries_unpinnable`: at least one item was excluded and the pins were audited. `pip_manifest_unpinnable`: no auditable item, so nothing is launched. Both are module-level constants that reach `skip_reason` through the unit's reasons. They carry no count, name or path | task0001 |

Every later rework task of this feature is bound by the same contracts.

## Conventions

- **Untrusted text**: no new reason, summary text or result field carries a package name, a path, the project root or scanner output. Only fixed tokens and counts are used (NFR4).
- **Content containment**: reading or parsing a reviewed file never raises out of `scan`. Only an exception from the launch step propagates, as it does on the lockfile route today.
- **One change for registry and pins**: the registry shape, the script that reads it and every test pin that encodes either one change together. A partial application caused the original inconsistency.
- **Tests**: modules import only the standard library. No real scanner is started. Tests that inspect prepared files point the process temporary directory at a test-owned directory outside the project root. Test modules read the registry text with module-local restricted parsers, never with a YAML library.
- **Docstrings and comments** that describe pip's command forms in the script and the registry header are updated in the same change, so they do not describe removed forms.

## Cross-task Design Decisions

### D1: One task

The registry shape, the pip job form, the static extraction and the test pins must change in one change (goal constraint). The extraction cannot be tested apart from the manifest route without a placeholder, and a placeholder would leave the suite failing in a parallel worktree. The work is therefore one task (task0001).

### D2: Every pip route converges on the prepared-file form

The directory form (`pip-audit <dir>`) and the direct reviewed-file form (`-r <reviewed file>`) are removed rather than guarded: no helper that builds them remains. The lockfile route changes only where its two flags come from, which is the registry form instead of literals in `build_scan_job`.

### D3: Reporting split between the two routes

The manifest route reports exclusions only through the two skip tokens, and the lockfile route keeps its `pip_lockfile_entries_unpinnable` summary note (as-lockfile-note-unchanged). A manifest unit's excluded count never feeds the lockfile note. A unit with no auditable item reports `pip_manifest_unpinnable` alone, never together with `pip_manifest_entries_unpinnable`.

### D4: Target-form validation at planning time

`validate_ecosystem_entry` checks the form with the same token rule as `args`, and requires the pip entry to declare `prepared_requirements`. A violation returns the fixed reason `<ecosystem>_target_forms_invalid` (for pip, `pip_target_forms_invalid`). `build_scan_jobs` already turns a validation reason into one skip reason and no plan, so a pip job is never attempted without its form.

### D5: `build_command` keeps its contract

`build_command` still returns the executable followed by the entry's top-level `args`. For pip this is the executable alone, because pip no longer has top-level `args`. The test expectation changes accordingly (FR7).

### D6: Directness and labels are unchanged

Direct names still come from the reviewed manifest through the existing resolvers. The job's manifest label stays the reviewed file and never becomes the prepared file (as-direct-names-unchanged).

### D7: Order of the pyproject checks

For a unit whose direct names come from pyproject.toml, the existing `pip_toml_parser_unavailable` check still runs first. Extraction runs only after it passes.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Test pins change across about ten modules, so a behavior regression could hide inside an updated expectation | Medium | High | The lockfile suite and the environment-pin expectations stay unedited (task0001 AC-9). Review compares each changed expectation with the SPEC rule it encodes |
| The pin rule diverges between requirements lines and `[project].dependencies` items | Low | Medium | One pin rule serves both (task0001 Design) |
| A restricted test parser silently skips the nested `target_forms` block | Medium | Medium | TS-6 asserts the parsed form values literally |
| The reviewer's system temporary directory lies inside the reviewed tree | Low | Medium | Not addressed here: the lockfile route has the same property, and the directory is the reviewer's own environment. Listed under Open Questions |
| pip-audit rejects a prepared file whose version string passes the rule | Low | Low | That run does not complete and reports its existing reason. The other groups continue |

## Open Questions

- [ ] FR9: the checks of npm / cargo / go and their record belong in SPEC.md, and the follow-up tasks belong in the external task system. Neither is a task file, and this planning dispatch cannot write SPEC.md, so no task implements FR9. The orchestrator side has to run the check, update SPEC.md and file the follow-ups.
- [ ] FR8 is already satisfied by SPEC.md's section on consistency with review-sca-axis. No task implements it.
- [ ] Should the pip routes refuse a system temporary directory that lies inside the project root, as the npm / cargo isolation does? Neither pip route checks this today.
