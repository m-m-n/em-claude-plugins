# Implementation Plan: sca-file-tasks-robustness

## Overview

Four independent fixes to the SCA axis: advisory short titles are whitespace-collapsed so every finding round-trips into file-tasks (task0001); an OS error inside the two filing helpers becomes the existing entry-point failure and the summary names the packages never attempted (task0002); review-phase.md's triage_filing receipt records partial failures and the incomplete-filing report, and batch-mode.md's batch report item list points at it (task0003); run_scan consumes the plans build_scan_jobs returns (task0004).

## Technology Stack

- **Language**: Python 3, standard library only, for the script and every test module (NFR3).
- **Test framework**: standard-library unittest, run as `python3 -m unittest discover -s tests`.
- **New dependencies**: none. `project.license` is `none`; no license record is needed.

## Layer Structure

Not a layered application. Four artifact kinds are touched:

| Artifact | Role | May depend on |
|----------|------|---------------|
| `em-workflow/scripts/scan-dependencies.py` | One CLI with two subcommands (`scan`, `file-tasks`) | standard library only |
| `em-workflow/references/review-phase.md` | Protocol the orchestrator follows; defines how the `file-tasks` summary is persisted (receipt) and reported (R6, batch final result) | the `file-tasks` summary contract below |
| `em-workflow/references/batch-mode.md` | Batch-run protocol; its `## Reporting` item list and audit-item source map are what the batch final report is assembled from | the triage_filing receipt review-phase.md defines (pointed at, never redefined) |
| `tests/test_*.py` | unittest modules; load the script by file path (its name contains a hyphen) | the script and the references, read-only |

The script never reads review-phase.md. review-phase.md describes the script's output; it never redefines it. batch-mode.md points at the receipt review-phase.md defines; it never restates it.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| `file-tasks` summary (the object `file_tasks` returns and the CLI prints) | One machine-readable record of a filing run | Post: on every return branch the object carries exactly these twelve keys — `branch`, `filed_packages`, `appended_packages`, `suppressed`, `report_path`, `degraded`, `degraded_reason`, `malformed_findings`, `listing_dropped_count`, `failed_package`, `failure_reason`, `unattempted_packages`. The first eleven keep their current names and meanings (NFR5). `unattempted_packages` is a list of package names: on a mid-batch failure, the failed package followed by every later package never attempted, in processing order (the group order after title recovery, de-duplication and truncation); malformed findings never appear in it; it is empty on full success, on the report branch and on the degraded report branch. Package names in it are the same canonical (truncated) strings `filed_packages` uses. | task0002 (produces), task0003 (documents its persistence), task0001 (its tests read only the first eleven keys) |
| `failure_reason` vocabulary | Machine-stable reason for a mid-batch filing failure | Exactly one of: null (no failure), `task_create_failed` (failure inside the task-create helper), `task_update_failed` (failure inside the reference-append helper). Never carries OS-error or advisory-sourced text. | task0002, task0003 |
| triage_filing receipt ← summary mapping | How the orchestrator copies the summary into the round record | `branch` → `branch`; `filed_packages` → `filed`; `appended_packages` → `appended`; `suppressed` → `duplicates_suppressed`; `report_path` → `report_path`; and the five keys `failed_package`, `failure_reason`, `malformed_findings`, `listing_dropped_count`, `unattempted_packages` copy one-to-one under the same names. When the disposition is `another-round` the five new fields are null / null / [] / 0 / []. Receipt values come from the summary only; nothing else is added. | task0003 (writes the text), task0002 (source of the values) |
| Finding text-encoding contract (existing shape, kept) | Finding title shape that `recover_package_advisory` parses back | Title is the package, then a colon and one space, then the advisory id, then a space, an em dash and a space, then the advisory short title. After this feature the short title contains no whitespace character other than single ASCII spaces, never starts or ends with whitespace, and is collapsed before the title is truncated. Package and advisory id are not altered. The recovery pattern itself is unchanged. | task0001 (produces), task0002 and task0004 (unchanged consumers; their tests build titles in this shape) |

## Conventions

- **Untrusted-text policy (NFR2)**: advisory-sourced text and OS-error message text go to stderr only. Every reason field (`failure_reason`, a malformed finding's reason, skip reasons) is a fixed token. `unattempted_packages` and the receipt carry only package names and fixed tokens.
- **Single partial-failure route in file-tasks (FR3)**: the entry-point failure caught in the filing loop is the only way a filing run ends early. No other exception type is added to that loop's handling.
- **Exit codes**: unchanged. `ExecutionError` (exit 2) stays reserved for invalid CLI input; a filing failure partway through still exits 0 with one JSON object on stdout.
- **Tests**: every task adds its new tests in its own new module under `tests/` and gives that module the standard-library-only import assertion that sibling SCA test modules carry. Existing modules are modified only where a task's Files list names them.
- **Plugin manifests**: no task edits a `plugin.json` or `.claude-plugin/marketplace.json` (NFR4).

## Cross-task Design Decisions

### D1: Region ownership inside `scan-dependencies.py`

Three tasks modify the same script in parallel. Each owns a disjoint region and touches nothing outside it, including neighbouring docstrings and section comments:

- task0001: `_build_finding` and any new helper it calls for short-title normalization (placed next to it). `_pip_advisory_headline`, `recover_package_advisory` and the title-recovery pattern stay as they are.
- task0002: the external task-system section and the `file-tasks` subcommand section — `_write_references_tempfile`, `create_security_task`, `append_security_task_references`, `file_tasks` (including its docstring).
- task0004: `manifest_file_for`'s docstring, the scan-job-construction section comment, `build_scan_jobs`, `_lexical_project_directory` (removed), `_scan_bound_group`, `_scan_pip_group` and `run_scan`.

Rationale: keeps parent-side adoption merges mechanical. Affected: task0001, task0002, task0004.

### D2: Existing test modules change only where a task names them

`tests/test_sca_task_filing.py` and `tests/test_sca_axis_triage_timing.py` are not modified by any task; they must keep passing as-is, which is how NFR5 and AC6's existing pins are demonstrated. Two tasks modify existing modules, on disjoint sets: task0004 rewrites the three that call `build_scan_jobs`; task0003 moves, in place, the seven-item / seven-row pins on batch-mode.md's `## Reporting` list and audit-item source map to eight in the four modules that carry them, deleting no assertion. Affected: all tasks.

### D3: Round-trip tests do not depend on the new summary key

task0001's tests that run findings through `file_tasks` assert only on the eleven pre-existing summary keys and on report content, so they pass whether or not task0002 has merged. Affected: task0001, task0002.

### D4: Fix the title at its source, keep recovery strict

The whitespace collapse happens at the single title-assembly point every normalizer calls, before truncation. The recovery pattern is not relaxed (no multi-line matching), so a title that still violates the contract stays classified malformed and package names or advisory ids containing whitespace stay malformed (SPEC assumption a-roundtrip-domain). Affected: task0001; task0002's malformed handling is unchanged.

### D5: Receipt names equal summary names for the five new fields

`failed_package`, `failure_reason`, `malformed_findings`, `listing_dropped_count` and `unattempted_packages` keep the summary key names in the receipt (Shared Components mapping), so no translation rule is needed. Affected: task0002, task0003.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Parallel edits to `scan-dependencies.py` conflict at merge | Low | Low | D1 region ownership; parent-side adoption protocol |
| Moving `build_scan_jobs` from lexical to real-path grouping changes expectations of existing grouping tests (symlinked aliases) | Medium | Medium | task0004 rewrites those tests as plan checks and adds alias / `..` cases (TS-9) |
| A refactor of the run side drops or reorders the binding check relative to isolation and launch | Low | High | task0004 AC-5 pins the order with a symlink swapped after planning (TM-5) |
| batch-mode.md's new Reporting item or source-map row restates receipt definitions owned by review-phase.md and drifts from them | Low | Medium | task0003 AC-8 (pointer only; negative phrase checks) |
| The added source-map row and Reporting item break the seven-row / seven-item pins in four existing batch-mode test modules | High | Low | task0003 owns moving those pins in place (D2, task0003 AC-7) |
| Docstring phrases pinned by `tests/test_sca_scanner_project_config_isolation.py` are lost while rewriting run-side docstrings | Medium | Low | task0004 AC-7 |

## Open Questions

- [x] Should `references/batch-mode.md`'s `## Reporting` list and its audit-item source map also name "triage filing incomplete"? Resolved by create-plan-q0001 (`add-batch-mode-reporting`): task0003 adds one Reporting item and one source-map row pointing at `reviews/roundN.yaml` `triage_filing.unattempted_packages` / `failed_package`, with review-phase.md staying the definition owner.

No open questions remain.
