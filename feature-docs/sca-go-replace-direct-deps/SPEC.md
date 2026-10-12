# Feature: sca-go-replace-direct-deps

## Overview

The Go SCA directness check is changed so that go.mod `replace` directives
contribute to the direct set. When a direct require is replaced by another
module, the replacement module is also direct, so its advisories become
findings or are counted under `go_severity_undetermined`. This feature
supplements FR3 of sca-go-govulncheck-real-output.

Requirements document: `feature-docs/sca-go-replace-direct-deps/REQUIREMENTS.md`

## Objectives

- Go SCA no longer drops a vulnerability on the replacement module when go.mod replaces a direct require with another module. Such an advisory becomes a finding, or is counted under `go_severity_undetermined` when its severity cannot be determined.
- A regression test covers both the single-line and the block form of replace.

## User Stories

None. Acceptance criteria are listed below.

## Acceptance Criteria

- [ ] AC1 (FR1, FR2, FR4): go.mod has `require example.org/text v0.3.6` and the single-line `replace example.org/text => golang.org/x/text v0.3.6`. A govulncheck stream advisory on golang.org/x/text with a CVSS v3 critical/high vector yields one finding whose package is golang.org/x/text. The same advisory with no CVSS v3 vector is counted in the `go_severity_undetermined` note. skipped is false.
- [ ] AC2 (FR1, FR2): The same as AC1 with the replace written inside a `replace ( ... )` block.
- [ ] AC3 (FR3): A direct require replaced by a local directory (`=> ./text`, `=> ../text`, `=> /abs/text`, `=> .\text`, `=> C:\text`, `=> .`) or by a directory path with a version adds nothing. An advisory on the replacement path is neither a finding nor counted.
- [ ] AC4 (FR5): A replace whose source require is marked `// indirect`, or whose source has no require entry, adds nothing.
- [ ] AC5 (FR2, FR3, FR5): A versioned replace applies only when its version equals the require version. When it matches, it wins over an unversioned replace of the same module. When the winning replace is local, nothing is added, with no fallback to the unversioned replace.
- [ ] AC6 (FR4): After a module replacement, the original require path is still direct.
- [ ] AC7 (NFR2): The existing test suite passes unchanged.

## Technical Requirements

### Functional Requirements
- **FR1:** Replace directives are parsed. go.mod `replace` directives are read in the single-line form (`replace old [v] => new [v]`) and in the `replace ( ... )` block form, with the same comment splitting, double- and back-quote stripping and CRLF handling as require entries. A replace entry is the source path, an optional source version, `=>`, the replacement path and an optional replacement version, all as separate tokens. Any line that does not have this shape contributes nothing. Malformed content never makes the go.mod unreadable.
- **FR2:** Replacement of a non-indirect require is direct. For each require entry that is not marked indirect, the applicable replace is chosen like this. A replace whose source has a version applies only when that version string exactly equals the require entry's version. A replace whose source has no version applies to any version. When a matching versioned replace exists, it wins over the unversioned one. When the applicable replace is a module replacement (FR3), its replacement path is added to the direct set. The result does not depend on where the replace and require directives appear in the file.
- **FR3:** Only module replacements contribute. A replacement counts as a module replacement only when it is exactly a path followed by a version, and the path is not in Go directory-path form. Directory-path form means: equal to `.` or `..`; starting with `./`, `../`, `.\`, `..\`, `/` or `\`; or starting with an ASCII letter followed by `:`. A replacement without a version (a local directory) and a directory-path replacement with a version contribute nothing. When the winning versioned replace (FR2) is not a module replacement, nothing is added, with no fallback to an unversioned replace of the same module.
- **FR4:** Original require path stays direct. The direct set is the union of the non-indirect require paths and the replacement paths added by FR2. Applying a replace never removes the original require path.
- **FR5:** Non-matching replaces contribute nothing. These contribute nothing: a replace whose source matches no require entry; a replace whose source matches only an indirect require entry; a versioned replace whose version differs from the require version; and the replacement of a replacement, because replacements are not chained.
- **FR6:** Supplements prior FR3. This feature supplements FR3 of sca-go-govulncheck-real-output. That FR3 says replace contributes nothing; replace now contributes as described in FR1-FR5. The rest of the prior FR3 is unchanged: exact match, the indirect-marker rule, quoted paths, a go.sum target using the sibling go.mod, and stdlib/toolchain being direct (prior FR4). The prior feature's documents are not edited. The Go normalization section comment, the `_go_mod_direct_modules` docstring and the `normalize_go` docstring in `em-workflow/scripts/scan-dependencies.py` are updated to describe the new behaviour.

### Non-Functional Requirements
- **NFR1 - Testing:** Tests use only stdlib `unittest` and replay offline through the existing govulncheck stub harness. They run under `python3 -m unittest discover -s tests`. They cover both the single-line and the block replace form.
- **NFR2 - Compatibility:** Every existing test keeps passing unchanged, including the replace cases in `tests/test_sca_go_govulncheck_real_output.py` at :709-712 (`DIRECT_GO_MODS`), :737-741 (`NOT_DIRECT_GO_MODS`) and the parser exact-set test at :792-809.
- **NFR3 - Output Safety and Security:** No new skip reason or summary note is added. Notes stay counts-only and carry no advisory or path text. go.mod and the govulncheck stream remain untrusted input. go.mod is only read, through the existing project-relative confinement, and nothing is written inside the reviewed project.

## Implementation Approach

### Architecture

The direct set of one Go scan unit is computed from its go.mod as follows:

```
go.mod (read via existing project-relative confinement)          [NFR3]
  -> tokenize with existing comment splitting / unquoting / CRLF  [FR1]
  -> require entries (single-line and block)                       (prior FR3)
  -> replace entries (single-line and block);
       lines not shaped `old [v] => new [v]` contribute nothing    [FR1]
  -> direct set := non-indirect require paths                      [FR4]
  -> for each non-indirect require entry:
       pick applicable replace:
         versioned source == require version  (wins)               [FR2]
         else unversioned source                                   [FR2]
       if the pick is a module replacement (path + version,
         path not in directory-path form):
           add replacement path to direct set                      [FR2, FR3]
       else: add nothing, no fallback                              [FR3]
  -> replaces matching no / only indirect require, version
       mismatches and chained replacements add nothing             [FR5]
```

Directness of a finding then follows prior FR3 / FR4 against this direct
set. Severity, undetermined counting and the `go_severity_undetermined`
note are unchanged.

### Data Flow

```
tests stub (govulncheck stream) -> run_scan -> normalize_go(project_root, ...)
  -> _go_mod_direct_modules(go.mod) -> direct set (require + replacement paths)
  -> findings[] / undetermined count -> run result
```

### API Design

Not applicable.

### Database Schema

Not applicable.

### Dependencies

**Internal Dependencies:**
- Existing go.mod tokenizer, comment splitting and unquoting: reused for replace parsing (FR1).
- `_go_mod_direct_modules`: computes the direct set; docstring updated (FR4, FR6).
- `normalize_go`: docstring updated (FR6).
- Existing project-relative confinement: resolves the go.mod path (NFR3).
- Existing govulncheck stub harness: replays streams offline in tests (NFR1).

**External Dependencies:**
- None.

### File Structure

```
em-workflow/scripts/
└── scan-dependencies.py   # replace parsing and direct set (FR1-FR5); Go normalization section comment,
                           # _go_mod_direct_modules and normalize_go docstrings (FR6)
tests/
└── <replace regression tests>   # FR1-FR5, NFR1
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/sca-go-replace-direct-deps/**`
- `test-docs/sca-go-replace-direct-deps/**`

`feature-docs/sca-go-replace-direct-deps/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/sca-go-replace-direct-deps/**` covers `test-docs/sca-go-replace-direct-deps/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/sca-go-replace-direct-deps/` directory at all; the declared
`test-docs/sca-go-replace-direct-deps/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests
- [ ] TS1 (AC1; FR1, FR2, FR4): The stub prints a stream whose advisory is on golang.org/x/text. go.mod has `require example.org/text v0.3.6` and the single-line unversioned replace to golang.org/x/text v0.3.6. Assert a high/critical finding with package golang.org/x/text when the advisory has a CVSS v3 vector, and the `go_severity_undetermined` count when it has none.
- [ ] TS2 (AC2; FR1, FR2): The same as TS1 with the replace in a block, including a block holding other entries and comments.
- [ ] TS3 (AC3; FR3): Local and directory-form replacements (`./x`, `../x`, `/x`, `.\x`, `..\x`, `\x`, `C:\x`, `.`, `..`, and `./x v1.0.0`) add nothing. Assert a completed clean result.
- [ ] TS4 (AC4; FR5): The source require is `// indirect`, or there is no require of the source. Assert nothing is added.
- [ ] TS5 (AC5; FR2, FR3, FR5): Versioned source matching the require version adds the replacement; a non-matching version adds nothing; versioned and unversioned replaces of the same module both present -> only the versioned replacement is added; a matching versioned replace that is local and an unversioned module replace both present -> nothing added.
- [ ] TS6 (AC6; FR4): A parser-level assertion that the direct set holds both the original path and the replacement path.
- [ ] TS7 (FR1, FR2): Edge forms: replace before require, quoted paths on both sides, trailing comments, CRLF line endings, `=>` glued to the paths (contributes nothing), malformed replace (missing right side, extra tokens; contributes nothing), and a chained A=>B, B=>C (only B added).
- [ ] TS8 (AC7; NFR2): The full `python3 -m unittest discover -s tests` run passes, including the existing replace cases.

### Integration Tests
None beyond the scenarios above.

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases
- [ ] A replace written before its require is applied the same way (FR2).
- [ ] `=>` glued to the paths is not a separate token, so the line contributes nothing (FR1).
- [ ] A malformed replace contributes nothing and adds no skip reason or note (FR1, NFR3).
- [ ] Chained replacements A=>B, B=>C add only B for a direct require of A (FR5).

### Performance Tests
Not applicable.

## Security Considerations

- **Authentication:** Not applicable.
- **Authorization:** Not applicable.
- **Input Validation:** go.mod and the govulncheck stream remain untrusted input. Malformed replace content contributes nothing and never makes the go.mod unreadable (FR1, NFR3).
- **Data Protection:** No new skip reason or summary note is added. Notes stay counts-only and carry no advisory or path text (NFR3).
- **Write Containment:** go.mod is only read, through the existing project-relative confinement, and nothing is written inside the reviewed project (NFR3).

## Error Handling

### Error Codes

No new skip reason or summary note token is added (NFR3). Malformed replace
content contributes nothing to the direct set and is not an error (FR1).

### Error Flow

```
replace line not shaped `old [v] => new [v]` -> ignored -> direct set unchanged
```

## Performance Optimization

Not applicable.

## Assumptions

- A1: Local-path rule: a replacement contributes only when it is a path plus a version and the path is not in Go IsDirectoryPath form (`.` or `..`; a `./`, `../`, `.\`, `..\`, `/` or `\` prefix; a drive letter). An unversioned replacement or a directory path with a version adds nothing.
- A2: Versioned-source matching: a versioned source applies only when the require version string matches exactly, and an unversioned source applies to any version. A matching versioned replace wins over the unversioned one. If the winning replacement is local, nothing is added and there is no fallback to the unversioned replace. Known limitation: the require version is a minimum, so when the build selects a different version, an exact-version match can still misjudge.
- A3: The direct set is the union of the original require path and the applied replacement path; the original stays direct.
- A4: The prior feature docs (sca-go-govulncheck-real-output `SPEC.md`, `REQUIREMENTS.md` and `tasks/task0001.md`) stay unedited as historical record. This SPEC states that it supplements prior FR3. The docstrings and comments in `scan-dependencies.py` are updated.
- A5: Replacements are applied once and are not chained (A=>B, B=>C adds only B for a direct require of A).
- A6: Replace parsing reuses the existing go.mod tokenizer, comment splitting and unquoting. Malformed replace content contributes nothing and adds no skip reason or note.
- A7: Every existing test in `tests/test_sca_go_govulncheck_real_output.py` keeps passing unchanged, including the replace cases at :709-712, :737-741 and :792-809.

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] `python3 -m unittest discover -s tests` passes

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

None.

## References

- Requirements document: `feature-docs/sca-go-replace-direct-deps/REQUIREMENTS.md`
- Supplemented feature: `feature-docs/sca-go-govulncheck-real-output/SPEC.md` (FR3)
