# Verification Document: sca-go-govulncheck-real-output

## Overview
**Feature**: sca-go-govulncheck-real-output / **SPEC.md**: `feature-docs/sca-go-govulncheck-real-output/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/sca-go-govulncheck-real-output/IMPLEMENTATION.md` / **THREAT-MODEL.md**: `feature-docs/sca-go-govulncheck-real-output/THREAT-MODEL.md`

## Build Verification
- Command: none (`build_command` is empty for both components, `repo-tests` and `plugin-invariants`)
- Expected: not applicable

## Test Verification
- Command (component `repo-tests`): `python3 -m unittest discover -s tests`
- Command (component `plugin-invariants`): `python3 em-workflow/scripts/check-plugin-invariants.py .`
- Expected: both exit 0 with no failures or errors
- Coverage target: not measured (no coverage tooling configured); every scenario below maps to at least one passing test

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS1 | (AC1; FR1, FR2, FR3, FR6, NFR1, NFR3) The Go stub prints the real capture verbatim; the bound unit's go.mod requires the vulnerable module directly | `skipped: false`, `skip_reason: null`; for the capture's advisory on that module, a high/critical finding or the summary note ` N go advisory\|advisories with undetermined severity (go_severity_undetermined).` with the expected count and no advisory text; never findings 0 without the note | Integration |
| TS2 | (AC2; FR3) Same capture; the vulnerable requirement marked `// indirect`, and separately removed from require | No finding and no undetermined count for that advisory | Integration |
| TS3 | (AC3; FR1, FR2) Streams derived from the capture whose OSV `severity` list holds CVSS:3.1 high plus critical vectors, a `CVSS_V4` entry only, or a malformed vector | Critical finding for the pair; undetermined for `CVSS_V4` only and for the malformed vector; a determinable below-high band is dropped and not counted | Integration |
| TS4 | (AC4; FR4) A stdlib (and a toolchain) finding with a go.mod lacking any require | Treated as direct: a finding or an undetermined count according to its severity | Integration |
| TS5 | (AC5; FR5) Module-, package- and symbol-level objects for one OSV id in one unit; two bound project units each holding the advisory | One result for the single unit; two findings for the two units, each labelled with its own unit's file | Integration |
| TS6 | (AC6; FR7, FR9) The single-object `{vulns}` payload, a stream without config, a config-only clean stream, empty stdout | `skipped: true` with `go_unparseable_output` for the first two; findings `[]`, `skipped: false` for the config-only stream; `go_empty_output` for empty stdout | Integration |
| TS7 | (AC7; FR8, NFR3, NFR4) A go.mod with invalid UTF-8 bytes in a bound unit, beside a completing npm unit | `skipped: true`; skip_reason holds `go_direct_manifest_unreadable` and no path text; npm findings kept; no Go findings | Integration |
| TS8 | (AC8; FR10) An OSV object with two `affected` entries for different modules, each with a different fixed event | The finding's fixed version comes from the entry whose `package.name` is the finding's module | Integration |
| TS9 | (AC9; FR6, NFR1, NFR2) Structural check of the capture and its provenance note | The capture decodes as an object stream holding a config object and at least one finding; neither file contains `/home/` or `/tmp/`; no capture string value begins with `/`; the provenance note records govulncheck version, go version, command, minimal go.mod and capture date | Unit |
| TS10 | (planner-added, no SPEC counterpart; NFR1, NFR5) Compatibility and test hygiene | The existing npm, cargo and pip tests pass with unchanged expectations; the Go test modules import only the standard library and launch no real go, govulncheck or network access | Unit / Integration |

## Code Quality Verification
- Format: none configured / Static analysis: none configured
- Plugin invariants: `python3 em-workflow/scripts/check-plugin-invariants.py .` (see Test Verification)
- Inspection: the `_merge_govulncheck_stream` docstring no longer promises single-object compatibility (FR7); `osv.database_specific.severity` is no longer read anywhere on the Go path (FR1)

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC1 | All functional requirements are implemented and tested | Functional Requirements Coverage below; TS1-TS9 pass |
| SC2 | All test scenarios pass | `python3 -m unittest discover -s tests` passes with TS1-TS10 present |
| SC3 | `python3 -m unittest discover -s tests` passes | Run the command; exit 0 |
| SC4 | `python3 em-workflow/scripts/check-plugin-invariants.py .` passes | Run the command; exit 0 |
| SC5 | Objective: a Go project with real vulnerabilities is not silently reported clean | TS1 (offline replay); manual item M1 |
| SC6 | Objective: regression is caught by a test replaying a real capture | TS1 and TS9 exist and pass |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS1, TS3 (automated); inspection (no `database_specific` read) |
| FR2 | task0001 | TS1, TS3 (automated) |
| FR3 | task0001 | TS1, TS2 (automated) |
| FR4 | task0001 | TS4 (automated) |
| FR5 | task0001 | TS5 (automated) |
| FR6 | task0001 | TS1, TS9 (automated) |
| FR7 | task0001 | TS6 (automated); docstring inspection |
| FR8 | task0001 | TS7 (automated) |
| FR9 | task0001 | TS6 (automated) |
| FR10 | task0001 | TS8 (automated) |
| NFR1 | task0001 | TS1, TS9, TS10 (automated) |
| NFR2 | task0001 | TS9 (automated) |
| NFR3 | task0001 | TS1, TS7 (automated); TM-3 |
| NFR4 | task0001 | TS7 (automated); TM-5 |
| NFR5 | task0001 | TS10 (automated) |

## Manual Testing (E2E Not Possible)
- [ ] M1 (SC5; the goal's reproduction steps): with a go toolchain and network access, run real govulncheck in JSON mode on the minimal vulnerable module recorded in the provenance note, run the SCA scan with that module's go.mod as the changed file, and confirm the result is not "findings 0, `skipped: false`, `skip_reason: null`" without the `go_severity_undetermined` note. When go or network access is unavailable at verify time, record that and rely on TS1, its offline equivalent.

## Performance / Security Verification (if applicable)
- TM-1: Go stdout completes only as a stream of JSON objects with a top-level config object; otherwise `go_unparseable_output` — checked by TS6 (automated)
- TM-2: severity band only from valid CVSS_V3 vectors; undeterminable direct advisories counted in the counts-only note, never treated as below threshold — checked by TS1 and TS3 (automated)
- TM-3: summary notes and skip reasons carry only counts and fixed tokens; advisory strings reach findings only through `truncate_untrusted` — checked by task0001 AC-9's test with instruction-like and path-like advisory text and an over-long details text (automated)
- TM-4: only non-indirect require entries make a module direct; the indirect marker is recognized only in its canonical form; other directives and comments contribute nothing — checked by TS2, TS4 and task0001 AC-5's directness cases (automated)
- TM-5: go.mod read only through project-relative confinement as a regular UTF-8 file; any failure gives `go_direct_manifest_unreadable` with no fallback — checked by TS7 and task0001 AC-7's direct normalizer cases, plus an unchanged project tree after the scan (automated)
- TM-6: machine-local absolute paths replaced by placeholders in the capture and provenance note — checked by TS9 (automated)

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS1-TS10) | 10 | 10 | 0 | 0 |
| Code quality (invariants, inspection) | 2 | 1 | 0 | 1 |
| Success criteria (SC1-SC6) | 6 | 5 | 0 | 1 |
| Security (TM-1-TM-6) | 6 | 6 | 0 | 0 |
| Manual testing (M1) | 1 | 0 | 0 | 1 |
