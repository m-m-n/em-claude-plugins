# Feature: sca-file-tasks-robustness

## Overview

This feature makes the SCA file-tasks flow robust in four areas: advisory titles that contain whitespace runs (newlines included) are collapsed so every finding round-trips from scan to file_tasks; an OSError raised while filing becomes EntryPointError and goes through the existing break-and-return path; the triage_filing receipt in review-phase.md records partial failures and the packages that were never attempted; and run_scan consumes the plans returned by build_scan_jobs. Requirements document: `feature-docs/sca-file-tasks-robustness/REQUIREMENTS.md`.

## Objectives

- file-tasks can turn every vulnerability finding the scan produces into a task or a report entry.
- If filing fails partway through, file-tasks does not crash, and it keeps the record of the packages it already filed.
- The committed round record shows the difference between a partial filing failure and a full success. It also names the packages that were never filed.
- The tests and production use the same code path: run_scan uses build_scan_jobs.

## User Stories

Not applicable. The feature has no UI; the change is limited to a Python script, a Markdown reference and tests. Acceptance criteria are listed under Success Criteria.

## Technical Requirements

### Functional Requirements
- **FR1:** Collapse whitespace in titles. Before `_build_finding` assembles a title, it collapses every whitespace run in the advisory's short title (newlines included) to a single space, then strips the ends. The collapse happens before `truncate_untrusted` truncates the title. This covers pip's `_pip_advisory_headline` and the title sources for npm, cargo and go.
- **FR2:** Round trip from scan to file_tasks. Each normalizer builds titles from advisories whose text spans several lines. `recover_package_advisory` gets the original (package, advisory_id) back from each of these titles, `group_findings_by_package` does not classify them as malformed, and `file_tasks` turns them into tasks or report entries.
- **FR3:** OSError in the filing helpers becomes EntryPointError. `create_security_task` and `append_security_task_references` can raise OSError when launching the subprocess or writing the temp file. That OSError becomes EntryPointError and goes through the existing break-and-return path, which stays the only way to fail partway through. The summary records the packages already filed, plus `failed_package` and `failure_reason` (`task_create_failed` / `task_update_failed`). `main` prints exactly one JSON object on stdout and exits 0.
- **FR4:** Extend the triage_filing receipt. review-phase.md defines the receipt in three places: R4 "The receipt", the R5 YAML example, and the R5 prose. In all three, the receipt gains `failed_package`, `failure_reason`, `malformed_findings` and `listing_dropped_count`, plus `unattempted_packages` (FR5). When the disposition is another-round, these are null / null / [] / 0 / [].
- **FR5:** Record and surface packages that were never attempted. `file_tasks` adds a fifth summary key, `unattempted_packages`. It holds the failed package and every later package that was never attempted, in the order the groups were processed (the order after recovery, de-duplication and truncation; malformed findings are excluded). Every return branch includes it: [] on full success, [] on the report branch and the degraded report branch. The `file_tasks` docstring changes from four added keys to five. review-phase.md says that there is no automatic retry. When `unattempted_packages` is non-empty, the run reports "triage filing incomplete" with those packages in R6 and in the batch final result (in batch mode, R6 by itself is not shown). The review completion condition does not change. Running file-tasks again files only the remainder through duplicate detection, and this works only if the latest listing already shows the filed packages.
- **FR6:** run_scan uses build_scan_jobs (plan-units). `build_scan_jobs` becomes the only planning stage. It validates, resolves, groups by real path through `_verified_groups`, and selects targets, then returns (plans, skip_reasons). Each plan is one group's unit that has not been launched: ecosystem, directory/real root, files, target, executable. `run_scan` uses exactly those plans and does not select targets again. The run side keeps the binding check, the per-group isolation directory, pip lockfile preparation and `build_scan_job`, in their current order: no path checks when validation or resolution fails, and the isolation directory is prepared only after the binding check passes. Group order, the handling of unverified pip paths, the output object and the reason strings stay the same. Remove the `build_scan_jobs` docstring sentence "run_scan does not use this function". Tests that expected built job dicts from `build_scan_jobs` are rewritten to check plans. The argv/env/cwd assertions move to the `build_scan_job` and `run_scan` tests.

### Non-Functional Requirements
- **NFR1 - run_scan external behaviour:** What `run_scan` shows from outside stays the same: the output object, the skip_reason tokens, grouping by real path, the binding checks, the per-group isolation directories and their removal, pip lockfile preparation, the summary notes, and group order.
- **NFR2 - Untrusted text:** Text from advisories or from OSError messages never goes into `failure_reason`, the malformed reason, `unattempted_packages` or the receipt. It goes to stderr only. Reasons stay fixed tokens.
- **NFR3 - Dependencies:** The script and the tests use only the standard library (test/README.md).
- **NFR4 - Plugin version:** Plugin versions do not change (.claude/rules/core-plugin-version-bump.md).
- **NFR5 - Summary compatibility:** Existing `file_tasks` summary keys keep their names and meanings. The summary only gains `unattempted_packages`.
- **NFR6 - Gates:** The triage_filing receipt and the "triage filing incomplete" report add no gate identifier and never affect the completion gate.

## Implementation Approach

### Architecture

Not applicable (no layered application). The affected units are:

- Finding construction: `_build_finding`, `_pip_advisory_headline`, the npm / cargo / go title sources, `truncate_untrusted` (FR1).
- Filing: `recover_package_advisory`, `group_findings_by_package`, `file_tasks`, `create_security_task`, `append_security_task_references`, `main` (FR2, FR3, FR5).
- Scan planning and execution: `build_scan_jobs`, `_verified_groups`, `run_scan`, `build_scan_job` (FR6).
- review-phase.md: R4, R5 (YAML example and prose), R6 (FR4, FR5).

### Data Flow

Title construction (FR1, FR2):

```
advisory short title
  → collapse whitespace runs to one space, strip ends
  → truncate_untrusted
  → finding title
  → recover_package_advisory / group_findings_by_package
  → file_tasks → task or report entry
```

Scan planning (FR6):

```
build_scan_jobs: validate → resolve → _verified_groups (group by real path) → select targets
  → (plans, skip_reasons)
run_scan, per plan (current order kept):
  binding check → per-group isolation directory → pip lockfile preparation → build_scan_job
```

### Interfaces

#### `build_scan_jobs`

- Returns `(plans, skip_reasons)`.
- Each plan is one group's unit that has not been launched, carrying: ecosystem, directory/real root, files, target, executable.

#### `file_tasks` summary

- Gains a fifth added key, `unattempted_packages` (list). Present on every return branch.
- On a partial failure the summary records the packages already filed, `failed_package` and `failure_reason` (`task_create_failed` / `task_update_failed`).
- Existing keys keep their names and meanings (NFR5).

#### `main`

- Prints exactly one JSON object on stdout and exits 0, including when filing fails partway through (FR3).

#### triage_filing receipt (review-phase.md R4, R5 YAML example, R5 prose)

| Field | Value when disposition is another-round |
|-------|------------------------------------------|
| `failed_package` | null |
| `failure_reason` | null |
| `malformed_findings` | [] |
| `listing_dropped_count` | 0 |
| `unattempted_packages` | [] |

### Database Schema

Not applicable.

### Dependencies

**Internal Dependencies:**
- review-phase.md: defines the triage_filing receipt (R4, R5) and the R6 report.

**External Dependencies:**
- Python standard library only (NFR3).

### File Structure

Not specified here; the feature-specific paths are derived at create-plan (see Declared Change Set).

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/sca-file-tasks-robustness/**`
- `test-docs/sca-file-tasks-robustness/**`

`feature-docs/sca-file-tasks-robustness/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/sca-file-tasks-robustness/**` covers `test-docs/sca-file-tasks-robustness/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/sca-file-tasks-robustness/` directory at all; the declared
`test-docs/sca-file-tasks-robustness/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Scenarios
- [ ] TS1 (AC1/AC2; FR1, FR2): For each of the pip, npm, cargo and go normalizers, feed advisories with LF, CRLF, tabs and Unicode whitespace in the text; titles made only of whitespace; and titles longer than 4096 bytes. Check that the finding title has no newline and that `recover_package_advisory` returns the original (package, advisory_id). Run the result through `file_tasks` and check that a task or report entry is produced.
- [ ] TS2 (AC3; FR3, FR5): Use a stand-in entry point whose create launch fails with OSError on the 2nd package (a bad shebang placed after listing). Check exit 0, one JSON object, filed=[1st], `failed_package`=2nd, `failure_reason`=`task_create_failed`, `unattempted_packages`=[2nd, 3rd].
- [ ] TS3 (AC3; FR3, FR5): The same as TS2 on the append path (an existing incomplete task): `failure_reason`=`task_update_failed`.
- [ ] TS4 (AC4; FR3, FR5): The temp-file write raises OSError: handled like TS2.
- [ ] TS5 (AC8; FR5): The first package fails: filed is empty, `unattempted_packages` contains every package in processing order, and malformed findings are excluded.
- [ ] TS6 (AC8; FR5): Full success, report branch and degraded report branch: `unattempted_packages` == [].
- [ ] TS7 (AC5; FR3): The existing `listing_launch_failed` degraded case is unchanged.
- [ ] TS8 (AC6/AC7; FR4, FR5, NFR6): Document-text tests on review-phase.md: the five fields in R4, the R5 YAML and the R5 prose; the rule for packages that were never attempted; the R6 / batch final result report; and the pins that already exist.
- [ ] TS9 (AC9; FR6): Rewrite the `build_scan_jobs` grouping/order/reason tests as plan checks, including real-path grouping for aliases and ".." paths. Move the argv/env/cwd checks to `build_scan_job` and `run_scan`. Show that `run_scan` goes through `build_scan_jobs`, for example by replacing it with a test double.
- [ ] TS10 (NFR1; FR6): The existing `run_scan` end-to-end suites (execution, normalization, binding, isolation, pip lockfile) pass without changes to the behaviour they observe.

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected
- [ ] Full suite: `python3 -m unittest discover -s tests` passes in full (AC10).

### Edge Cases
- [ ] Titles made only of whitespace (TS1).
- [ ] Titles longer than 4096 bytes, truncated after the whitespace collapse (TS1).
- [ ] LF, CRLF, tabs and Unicode whitespace in advisory text (TS1).
- [ ] Package names or advisory ids that contain whitespace stay classified as malformed.
- [ ] The first package fails: every non-malformed package is in `unattempted_packages` (TS5).

### Performance Tests
Not applicable.

## Security Considerations

- **Authentication:** Not applicable.
- **Authorization:** Not applicable.
- **Input Validation:** Reasons stay fixed tokens (NFR2).
- **Data Protection:** Text from advisories or from OSError messages never goes into `failure_reason`, the malformed reason, `unattempted_packages` or the receipt; it goes to stderr only (NFR2).
- **XSS Prevention:** Not applicable.
- **SQL Injection Prevention:** Not applicable.
- **CSRF Protection:** Not applicable.

## Error Handling

### Error Codes

| Code | Description | Exit status | Output |
|------|-------------|-------------|--------|
| `task_create_failed` | OSError while launching the subprocess or writing the temp file in `create_security_task` | 0 | One JSON object on stdout |
| `task_update_failed` | OSError while launching the subprocess or writing the temp file in `append_security_task_references` | 0 | One JSON object on stdout |
| `listing_launch_failed` | Existing degraded behaviour; unchanged (AC5) | — | — |

### Error Flow

```
OSError in create_security_task / append_security_task_references
  → EntryPointError
  → existing break-and-return path
  → summary: packages already filed, failed_package, failure_reason, unattempted_packages
  → main prints exactly one JSON object on stdout, exit 0
  (OSError message text → stderr only)
```

## Performance Optimization

Not applicable.

## Success Criteria

- [ ] AC1: A pip advisory whose description contains newlines (with a CVSS vector) produces a finding whose title has no newline. `recover_package_advisory` recovers it, and `file_tasks` turns it into a task or a report entry.
- [ ] AC2: A round-trip test covers all four normalizers, including text that spans lines and titles truncated past 4096 bytes. The test fails without the fix.
- [ ] AC3: In a batch of 3 packages, launching create or update for the 2nd package fails with OSError. Exit code is 0 and stdout has exactly one JSON object. `filed_packages` (or `appended_packages`) contains the 1st package, `failed_package` is the 2nd, `unattempted_packages` is [2nd, 3rd], the 3rd is never attempted, and there is no traceback.
- [ ] AC4: A failure to write the temp file is handled the same way as AC3.
- [ ] AC5: The existing `listing_launch_failed` degraded behaviour (a bad shebang from the start) does not change.
- [ ] AC6: All three receipt places in review-phase.md carry `failed_package` / `failure_reason` / `malformed_findings` / `listing_dropped_count` / `unattempted_packages`. The existing strings that `test_sca_axis_triage_timing` pins stay (including "empty when this round's disposition was `another-round`", "introduces no new gate identifier", "never affects the completion gate", and triage_filing placed after rework_required).
- [ ] AC7: review-phase.md states: no automatic retry; "triage filing incomplete" with the packages appears in R6 and in the batch final result; the completion condition does not change; running again files only the remainder, provided the listing reflects the filed packages.
- [ ] AC8: `unattempted_packages` is [] on full success and on the report branch and the degraded report branch. A failure on the first package puts every non-malformed package into it. Malformed findings never appear in it.
- [ ] AC9: `run_scan` calls `build_scan_jobs` and consumes the plans it returns. Both the `run_scan` end-to-end tests and the `build_scan_jobs` plan tests exercise this path. The argv/env/cwd assertions live in the `build_scan_job` and `run_scan` tests.
- [ ] AC10: `python3 -m unittest discover -s tests` passes in full.

## Assumptions

- **a-build-scan-jobs-unification** (q-build-scan-jobs-unification): Unify with plan-units: `build_scan_jobs` returns (plans, skip_reasons) of per-group units that have not been launched. `run_scan` keeps the binding check, isolation, pip lockfile preparation and `build_scan_job` in their current order. Tests that expected built job dicts are rewritten to check plans.
- **a-unattempted-policy** (q-unattempted-policy): Record and surface: the fifth summary key `unattempted_packages` (the failed package plus every later package never attempted, in processing order, malformed findings excluded) is present on every return branch and recorded in all three receipt places. There is no automatic retry. "triage filing incomplete" appears in R6 and in the batch final result, and the completion condition does not change.
- **a-design-step-skip** (q-design-step): Skip the design step.
- **a-roundtrip-domain**: The round-trip guarantee covers package names and advisory ids that contain no whitespace. Names or ids that contain whitespace stay classified as malformed.
- **a-report-write-oserror-out-of-scope**: An OSError in `write_report` or `mkdir` on the report branch is outside this feature.

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

None.

## References

- Requirements document: `feature-docs/sca-file-tasks-robustness/REQUIREMENTS.md`
- review-phase.md: triage_filing receipt (R4, R5) and R6
- test/README.md: standard-library-only rule for tests
- .claude/rules/core-plugin-version-bump.md: plugin version handling
