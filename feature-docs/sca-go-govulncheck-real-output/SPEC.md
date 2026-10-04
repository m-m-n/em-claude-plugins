# Feature: sca-go-govulncheck-real-output

## Overview

The SCA axis's Go normalization is changed so that a Go project with real
vulnerabilities is never silently reported as clean. Severity, directness,
per-unit collapsing, stream validity and fixed-version lookup are defined
against real `govulncheck -json` output, and a real capture replaces the
synthetic Go fixture in the tests.

Requirements document: `feature-docs/sca-go-govulncheck-real-output/REQUIREMENTS.md`

## Objectives

- Running the SCA axis on a Go project with real vulnerabilities must not silently report "no vulnerabilities" (findings 0, skipped false, skip_reason null, with no signal).
- Regression is caught by a test that replays a real `govulncheck -json` capture through the Go normalization.

## User Stories

None. Acceptance criteria are listed below.

## Acceptance Criteria

- [ ] AC1 (FR1, FR2, FR3, FR6): Replaying the real capture with a go.mod that requires the vulnerable module directly (no `// indirect`) produces either a finding at high/critical (when the advisory has a valid CVSS v3 vector) or a summary note counting it under `go_severity_undetermined`. It never returns findings 0 + skipped false + skip_reason null with no undetermined note.
- [ ] AC2 (FR3): The same capture with the vulnerable module listed only as `// indirect` (or absent from require) yields no finding and no undetermined count for that advisory.
- [ ] AC3 (FR1): With several CVSS_V3 entries, the highest valid band wins. CVSS_V4-only or malformed vectors yield undetermined.
- [ ] AC4 (FR4): A stdlib (or toolchain) finding is treated as direct regardless of go.mod content.
- [ ] AC5 (FR5): Several finding objects with the same OSV id and module in one unit yield one finding (or one undetermined count). The same advisory in two project units yields one finding per unit.
- [ ] AC6 (FR7, FR9): A single-object `{"vulns": [...]}` payload and a stream without a config object give skipped true with `go_unparseable_output`. A config-bearing stream with no finding objects completes with findings [] and skipped false. Empty stdout still gives `go_empty_output`.
- [ ] AC7 (FR8): An unreadable or non-UTF-8 go.mod in a bound unit gives skipped true with skip_reason containing `go_direct_manifest_unreadable`, and keeps other units' findings.
- [ ] AC8 (FR10): A finding's fixed version in the description comes from the affected entry whose `package.name` matches its module, even when other affected entries carry fixed events.
- [ ] AC9 (FR6): The capture file and its provenance note exist under `tests/`. The provenance note records the govulncheck version, go version, command, minimal go.mod and capture date. The capture contains no machine-local absolute path.
- [ ] AC10: `python3 -m unittest discover -s tests` and `python3 em-workflow/scripts/check-plugin-invariants.py .` both pass.

## Technical Requirements

### Functional Requirements
- **FR1:** Severity from emitted CVSS v3 vectors. Go advisory severity comes only from the OSV object's top-level `severity[]` array. Every entry of type `CVSS_V3` whose score vector starts with `CVSS:3.0/` or `CVSS:3.1/` and is parsed by `_cvss_severity_band` is considered. The highest resulting band is taken, then mapped through the registry `severity_map`. Entries of type `CVSS_V4` or any other type are ignored. `osv.database_specific.severity` is no longer read.
- **FR2:** Undetermined severity is counted, not treated as below threshold. An advisory with no valid CVSS v3 vector per FR1 is undetermined. It is left out of findings. If it is direct (FR3/FR4), it is counted. Each scan unit's undetermined count is summed over the run. When the sum is non-zero, `run_scan` appends a counts-only summary note in the pip form: ` N go advisory|advisories with undetermined severity (go_severity_undetermined).` The note never carries advisory text. Undetermined severity never adds a skip reason; skipped/skip_reason keep meaning only "every unit completed". An advisory whose band is determinable but below high is dropped as before.
- **FR3:** Directness from go.mod require entries. A finding's module (`trace[0].module`) is direct when it exactly equals the module path of a require entry in the bound project's go.mod that is not marked `// indirect`. Both the single-line `require m v` form and `require ( ... )` blocks count, and quoted module paths are unquoted. Other directives (`module`, `go`, `toolchain`, `replace`, `exclude`, `retract`, `tool`) and comments contribute nothing. go.mod is read from the bound project directory. When the unit's target is go.sum, the go.mod beside it in the same directory is used, resolved via the existing project-relative confinement. `normalize_go` receives `project_root`, as the cargo normalizer does. The trace length no longer affects directness.
- **FR4:** stdlib/toolchain treated as direct. Findings whose module is `stdlib` or `toolchain` are treated as direct, then go through the same severity rules (FR1, FR2).
- **FR5:** One finding per (OSV id, module) per scan unit. Within one scan unit (one bound project directory), every govulncheck finding object with the same OSV id and module, at any level and with any number of traces, collapses into one scan finding. Directness and the undetermined count apply to that collapsed advisory once. Collapsing and counting happen per project unit. Findings from different project units are all kept.
- **FR6:** Real govulncheck capture fixture with provenance. `GO_FIXTURE` is replaced by a real capture. The capture is `govulncheck -json` stdout, produced by running `go run golang.org/x/vuln/cmd/govulncheck@<pinned version> -json ./...` against a minimal Go module that requires a known-vulnerable dependency version. It is saved verbatim as a text file under the repository-root `tests/`, with machine-local absolute paths replaced by placeholders. Next to it sits a provenance note giving the govulncheck version, go version, exact command, the minimal module's go.mod, and the capture date. Test stubs print the raw stream text verbatim (not `json.dumps` of a parsed object). Tests replay offline. If the capture cannot be produced, the implementing task reports blocked instead of hand-crafting a stream.
- **FR7:** Synthetic single-object shape dropped. The go path no longer accepts the synthetic single-object `{"vulns": [...]}` payload. Such a payload has no config object, so FR9 yields `go_unparseable_output`. `GO_PAYLOAD` and the go stubs in `tests/test_sca_per_project_scan_binding.py` switch to a real no-vulnerability stream with a config object. The `_merge_govulncheck_stream` docstring no longer promises single-object compatibility.
- **FR8:** Unreadable go.mod is a not-completed unit. When the bound project's go.mod cannot be opened, read or UTF-8 decoded at normalization time, that Go unit produces no findings and reports the path-free reason `go_direct_manifest_unreadable`. The run becomes `skipped: true` with that reason combined as usual (sorted, de-duplicated, `+`-joined). Findings of other units are kept. There is no fallback to an empty direct set.
- **FR9:** Go stream validity. For go, stdout is a completed scan result only when it parses as a stream of one or more JSON objects AND holds at least one top-level object with a `config` key whose value is an object. This holds whether the stream is one object or many. Anything else gives `go_unparseable_output`. A valid stream with no `finding` objects is a clean, completed result. The existing empty-output check (`go_empty_output`) keeps its precedence, and the documented exit statuses (`{0, 3}`) are unchanged.
- **FR10:** fixed_version scoped to the finding's module. A Go finding's fixed version comes only from the `osv.affected` entries whose `package.name` equals the finding's module. Fixed events from other modules' affected entries are not used.

### Non-Functional Requirements
- **NFR1 - Testing:** Tests use the stdlib `unittest` only, run offline (no go, govulncheck or network at test time), and live under the repository-root `tests/` (outside `em-workflow/`, so they are not distributed).
- **NFR2 - Fixture Hygiene:** The capture and its provenance note are text files. Machine-local absolute paths (e.g. the capturing user's home or temp directory) do not appear in them.
- **NFR3 - Output Safety:** Summary notes and skip reasons carry only counts and fixed tokens, never advisory-sourced or path text. Advisory-sourced strings in findings keep passing through `truncate_untrusted`.
- **NFR4 - Security:** The scan still writes nothing inside the reviewed project root. go.mod is only read, and only from the verified bound project directory. govulncheck stream content and go.mod content are untrusted input.
- **NFR5 - Compatibility:** npm, cargo and pip behavior is unchanged.

## Implementation Approach

### Architecture

Per Go scan unit (one bound project directory), the normalization applies
the requirements above in this order of concerns:

```
govulncheck -json stdout
  -> empty-output check (go_empty_output, precedence kept)        [FR9]
  -> stream validity: >=1 JSON object, >=1 top-level config object [FR9, FR7]
       else go_unparseable_output
  -> read go.mod from the bound project dir (go.sum target: sibling go.mod)
       unreadable / non-UTF-8 -> go_direct_manifest_unreadable    [FR3, FR8]
  -> collapse finding objects by (OSV id, module)                 [FR5]
  -> directness: non-indirect require entry, or stdlib/toolchain  [FR3, FR4]
  -> severity: max band over valid CVSS_V3 vectors, severity_map  [FR1]
       no valid vector -> undetermined count (direct only)        [FR2]
  -> fixed_version from affected entries of the finding's module  [FR10]
```

`run_scan` sums the per-unit undetermined counts over the run and appends
the counts-only `go_severity_undetermined` summary note when the sum is
non-zero (FR2).

### Data Flow

```
tests stub (raw capture text) -> run_scan -> normalize_go(project_root, ...)
  -> findings[] / undetermined count / skip reason -> run result
```

### API Design

Not applicable.

### Database Schema

Not applicable.

### Dependencies

**Internal Dependencies:**
- `_cvss_severity_band`: parses CVSS 3.x vectors (FR1).
- Registry `severity_map`: maps the selected band (FR1).
- `_merge_govulncheck_stream`: govulncheck stream merging; docstring updated (FR7).
- Existing project-relative confinement: resolves the go.mod path (FR3).
- `truncate_untrusted`: applied to advisory-sourced strings in findings (NFR3).

**External Dependencies:**
- `golang.org/x/vuln/cmd/govulncheck` at a pinned version: used only to produce the capture (FR6). Not used at test time (NFR1).

### File Structure

```
tests/
├── test_sca_per_project_scan_binding.py   # GO_PAYLOAD and go stubs switch to a real no-vulnerability stream (FR7)
├── <real govulncheck capture, text>        # FR6
└── <provenance note, text>                 # FR6
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/sca-go-govulncheck-real-output/**`
- `test-docs/sca-go-govulncheck-real-output/**`

`feature-docs/sca-go-govulncheck-real-output/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/sca-go-govulncheck-real-output/**` covers `test-docs/sca-go-govulncheck-real-output/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/sca-go-govulncheck-real-output/` directory at all; the declared
`test-docs/sca-go-govulncheck-real-output/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests
- [ ] TS1 (AC1; FR1, FR2, FR3, FR6): The stub prints the raw capture. go.mod requires the vulnerable module directly. Assert findings at high/critical or the `go_severity_undetermined` note with the expected count. skipped false.
- [ ] TS2 (AC2; FR3): Same capture, with the module marked `// indirect`. Assert no finding for it and no undetermined note.
- [ ] TS3 (AC3; FR1): A stream derived from the capture whose OSV `severity[]` holds a CVSS:3.1 high vector plus a critical one, a CVSS_V4 entry, or a malformed vector. Assert the band selection or undetermined.
- [ ] TS4 (AC4; FR4): A stdlib finding with a go.mod lacking any require. Assert it is treated as direct.
- [ ] TS5 (AC5; FR5): Module-, package- and symbol-level objects for one OSV id in one unit give one result. Two bound project units each holding the advisory give two findings.
- [ ] TS6 (AC6; FR7, FR9): Single-object `{vulns}` payload, a stream without config, a config-only clean stream, and empty stdout.
- [ ] TS7 (AC7; FR8): go.mod with invalid UTF-8 bytes in a bound unit, next to a completing npm unit.
- [ ] TS8 (AC8; FR10): An OSV with two affected entries for different modules, each with a different fixed event.
- [ ] TS9 (AC9; FR6): Structural check: the capture file parses as an object stream containing a config object and at least one finding, and neither file contains `/home/` or `/tmp/`-style absolute paths.

### Integration Tests
None beyond the scenarios above.

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases
- [ ] go.sum target: directness uses the sibling go.mod in the same bound directory (FR3).
- [ ] Quoted module paths in require entries are unquoted before comparison (FR3).
- [ ] An advisory whose band is determinable but below high is dropped, not counted as undetermined (FR2).
- [ ] An undetermined advisory that is not direct is neither a finding nor counted (FR2).

### Performance Tests
Not applicable.

## Security Considerations

- **Authentication:** Not applicable.
- **Authorization:** Not applicable.
- **Input Validation:** govulncheck stream content and go.mod content are untrusted input (NFR4). Stream validity per FR9.
- **Data Protection:** Summary notes and skip reasons carry only counts and fixed tokens, never advisory-sourced or path text; advisory-sourced strings in findings pass through `truncate_untrusted` (NFR3). The capture and provenance note contain no machine-local absolute paths (NFR2).
- **Write Containment:** The scan writes nothing inside the reviewed project root; go.mod is only read, and only from the verified bound project directory (NFR4).

## Error Handling

### Error Codes

| Token | Kind | Condition | Effect |
|-------|------|-----------|--------|
| `go_empty_output` | skip reason | Empty stdout (existing check, precedence kept) | Unit not completed |
| `go_unparseable_output` | skip reason | stdout is not a stream of one or more JSON objects with at least one top-level object whose `config` value is an object | Unit not completed |
| `go_direct_manifest_unreadable` | skip reason | Bound project's go.mod cannot be opened, read or UTF-8 decoded | Unit produces no findings; run `skipped: true`; other units' findings kept |
| `go_severity_undetermined` | summary note | Run-wide undetermined count is non-zero | Counts-only note appended; no skip reason added |

### Error Flow

```
Unit not completed -> skip reason recorded -> reasons sorted, de-duplicated, '+'-joined -> run skipped: true
```

## Performance Optimization

Not applicable.

## Assumptions

- A1: A go.mod require entry marked `// indirect` is not a direct dependency.
- A2: For a go.sum target, directness is resolved from the sibling go.mod in the same bound directory.
- A3: Only CVSS 3.0/3.1 vectors are parsed. Other severity types count as undetermined (refined by FR1's max-band rule).
- A5: The capture fixture and provenance note live under the repository-root `tests/` as text.

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] `python3 -m unittest discover -s tests` passes
- [ ] `python3 em-workflow/scripts/check-plugin-invariants.py .` passes

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

None.

## References

- Requirements document: `feature-docs/sca-go-govulncheck-real-output/REQUIREMENTS.md`
