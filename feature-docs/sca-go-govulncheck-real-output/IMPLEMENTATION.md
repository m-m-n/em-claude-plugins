# Implementation Plan: sca-go-govulncheck-real-output

## Overview
The Go path of the SCA scan (`em-workflow/scripts/scan-dependencies.py`) is
redefined against real `govulncheck -json` output, and a real capture
replaces the synthetic Go fixture in the repository-root tests. The work is
one task (task0001); this document pins the contracts and conventions that
task and any later rework task share.

## Technology Stack
- **Language**: Python 3, standard library only (the existing script and its tests)
- **Tests**: stdlib `unittest`, run offline from the repository-root `tests/`
- **Capture tooling** (implementer-side, one run, not a project dependency): the Go toolchain and govulncheck (golang.org/x/vuln, BSD-3-Clause) at a pinned version, used only to produce the capture (FR6); never run at test time (NFR1)
- **New dependencies**: none (`project.license: none`)

## Layer Structure
The Go path inside `scan-dependencies.py`, top to bottom; each layer calls
only the layer below it.

| Layer | Existing entry point | Responsibility |
|-------|----------------------|----------------|
| Run aggregation | `run_scan` | Combines unit audits into one review-output object; owns `skipped` / `skip_reason` and the summary notes |
| Unit aggregation | `_scan_bound_group` | Runs one bound Go unit and turns its outcome into a unit audit |
| Normalization | stream reduction (`_merge_govulncheck_stream`) and the Go normalizer (`normalize_go`) | Completed payload to findings, undetermined count and an optional not-completed reason |
| Intake | `judge_scan_outcome` | Process stdout and exit status to a completed payload or a not-completed reason |

Intake never reads project files. Normalization never launches a process and
never writes. npm, cargo and pip branches of every layer stay as they are
(NFR5).

## Shared Components
| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| Go normalizer | Turns one completed Go unit payload into findings | Inputs: the go registry entry, the completed Go payload (a stream that passed the Go validity rule), the unit target (project-relative path of the unit's go.mod or go.sum, already bound) and the project root. Output: the unit's findings, its undetermined count (an integer, zero or more) and an optional not-completed reason. Postconditions: when a reason is returned it is exactly `go_direct_manifest_unreadable`, findings are empty and the count is zero; the only file read is the unit's go.mod through the existing project-relative confinement; nothing is written. Called with the project root, as the cargo normalizer is | task0001 |
| Go stream validity rule | Decides whether Go stdout is a completed scan | Completed only when stdout decodes as a sequence of one or more JSON values, every value is an object, and at least one top-level object has a `config` key whose value is an object. Empty stdout keeps `go_empty_output` first; the documented exit statuses `{0, 3}` and the undocumented-exit-status reason are unchanged; every other failure is `go_unparseable_output` | task0001 |
| Real capture fixture | The single source of Go test streams | `tests/sca_govulncheck_capture.txt` holds govulncheck `-json` stdout verbatim, with each machine-local absolute path replaced by a placeholder token; `tests/sca_govulncheck_capture_provenance.md` records, each under its own label, the govulncheck version, the go version, the exact command, the minimal module's go.mod and the capture date. Both are text files | task0001 |
| Raw-text stub mode | Lets a test tool stub print Go output byte-for-byte | The stub writers in the existing test modules accept either text, printed verbatim, or a JSON-serializable value, encoded as today. npm, cargo and pip callers keep passing values and see no change | task0001 |
| Go token vocabulary | Fixed, path-free tokens of the Go path | Skip reasons: `go_empty_output`, `go_unparseable_output`, `go_undocumented_exit_status` (existing), `go_direct_manifest_unreadable` (new). Summary note token: `go_severity_undetermined` (new; a note, never a skip reason) | task0001 |

## Conventions
- **Path-free outputs**: skip reasons and summary notes carry only counts and the fixed tokens above, never advisory-sourced or path text (NFR3).
- **Advisory text**: advisory-sourced strings enter findings only through the existing finding builder, so `truncate_untrusted` applies (NFR3).
- **Fail closed on uninterpretable input**: an invalid stream and an unreadable go.mod make the unit not completed; an undeterminable severity is counted in a note. None of them may yield a silent clean result.
- **`skipped` meaning unchanged**: `skipped` / `skip_reason` still mean only "did every selected unit complete"; reasons stay sorted, de-duplicated and `+`-joined.
- **Tests**: stdlib only, offline (tool stubs on a PATH restricted to the stub directory, no go, govulncheck or network), the script loaded by file path, files under the repository-root `tests/` (NFR1). Go stubs print raw text.

## Cross-task Design Decisions

### D1: One task
The feature is a single task. Every behavioral Go test needs both the real
capture and the rewritten normalization, and the stricter stream validity
breaks the existing synthetic Go fixtures unless the capture lands in the
same change. Tasks run fully in parallel and cannot test against each other's
output, so any split leaves one side with tests it cannot pass. The task
therefore carries nine Acceptance Criteria, above the usual size guide, by
design. Affected: task0001, and any rework task, which must keep the Shared
Components contracts above.

### D2: The capture is the only source of Go test streams
Replays print the capture text verbatim. The clean config-only stream is the
verbatim text of the capture's config object, cut from the capture text and
not re-serialized. Scenario streams are derived from the capture's own
objects with the smallest edit the scenario needs. No Go stream is written
from scratch. Affected: task0001 and every later Go test.

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| The implementer cannot produce a real capture (no go toolchain or no network) | Medium | High: the task blocks and the feature cannot complete | FR6: report blocked; never hand-craft a stream |
| The capture's OSV records carry no top-level `severity` list | High | Low | TS1 then asserts the undetermined note; TS3 covers band selection with derived streams |
| The minimal module yields no symbol-level finding | Medium | Low | TS5 derives the missing levels from the capture's own finding objects |
| Machine-local absolute paths leak into the committed capture | Medium | Medium | Placeholders; TS9 rejects them (TM-6) |
| A govulncheck version that emits no config object is rejected | Low | Medium | Reported as `go_unparseable_output` (visible skip, not a silent clean); the pinned version is recorded in the provenance note |

## Open Questions
- [ ] The capture embeds OSV records served by the Go vulnerability database. SPEC does not ask the provenance note to record the data license of those records; left to the license review perspective.
