# Verification Document: sca-go-replace-direct-deps

## Overview
**Feature**: sca-go-replace-direct-deps / **SPEC.md**: `feature-docs/sca-go-replace-direct-deps/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/sca-go-replace-direct-deps/IMPLEMENTATION.md`

## Build Verification
- Command: none (`build_command` is empty for both components `repo-tests` and `plugin-invariants`)
- Expected: not applicable

## Test Verification
- Command (repo-tests): `python3 -m unittest discover -s tests`
- Command (plugin-invariants): `python3 em-workflow/scripts/check-plugin-invariants.py .`
- Expected: exit code 0 for both
- Coverage target: not measured (no coverage tool in the project components); every scenario below must pass

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS1 | go.mod has `require example.org/text v0.3.6` and the single-line unversioned replace to golang.org/x/text v0.3.6; the stub stream carries an advisory on golang.org/x/text, once with and once without a CVSS v3 vector | With the vector: one high/critical finding whose package is golang.org/x/text. Without it: counted under `go_severity_undetermined`. skipped is false | Unit |
| TS2 | Same as TS1 with the replace inside a `replace ( ... )` block, including a block holding other entries and comments | Same as TS1 | Unit |
| TS3 | Local and directory-form replacements: `./x`, `../x`, `/x`, `.\x`, `..\x`, `\x`, `C:\x`, `.`, `..`, `./x v1.0.0` | Nothing added; an advisory on the replacement path is neither a finding nor counted; completed clean result | Unit |
| TS4 | The source require is `// indirect`, or there is no require of the source | Nothing added | Unit |
| TS5 | Versioned source equal to the require version; non-matching version; versioned and unversioned replaces of the same module; matching versioned local replace plus unversioned module replace | Replacement added; nothing added; only the versioned replacement added; nothing added | Unit |
| TS6 | Parser-level direct set after a module replacement | Holds both the original require path and the replacement path | Unit |
| TS7 | Edge forms: replace before require, quoted paths on both sides, trailing comments, CRLF, `=>` glued to the paths, malformed replace (missing right side, extra tokens), chained A=>B and B=>C | Order-independent; quoting, comments and CRLF handled as for require; glued and malformed lines contribute nothing; chain adds only B | Unit |
| TS8 | Full `python3 -m unittest discover -s tests` run, including the existing replace cases in `tests/test_sca_go_govulncheck_real_output.py` | Passes; no existing test module is changed | Integration |
| TS9 | Inspect the Go normalization section comment, the `_go_mod_direct_modules` docstring and the `normalize_go` docstring in `em-workflow/scripts/scan-dependencies.py`; diff `feature-docs/sca-go-govulncheck-real-output/` between the implement base commit and the integration tip | The three sites describe replace contributing per FR1-FR5 and none says replace contributes nothing; the diff is empty | Inspection |
| TS10 | Inspect the new regression test module and the discover run's test list | Uses only stdlib `unittest` plus existing repository test helpers; replays through the existing govulncheck stub harness with no real govulncheck or network; collected by `python3 -m unittest discover -s tests`; covers both the single-line and the block form | Inspection |
| TS11 | For the malformed and non-contributing go.mod cases (TS3, TS4, TS5 non-matching, TS7 malformed), with a distinctive marker string written into the replace directives on both sides | skipped is false; no skip reason; only pre-existing summary note tokens with counts-only values; the marker string appears nowhere in the serialized run result | Unit |
| TS12 | A direct require is replaced by a local path resolving to an existing directory outside the project root whose own go.mod requires module M; the stream carries advisories on M and on the local path | Neither advisory is a finding or counted; completed clean result | Unit |

## Code Quality Verification
- Format: none (`format_command` is empty)
- Static analysis: `python3 em-workflow/scripts/check-plugin-invariants.py .` (exit code 0)

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | Single-line replace of a direct require makes the replacement's advisory a finding or an undetermined count | TS1 |
| AC2 | Same with the block form | TS2 |
| AC3 | Local and directory-path replacements add nothing | TS3, TS12 |
| AC4 | Indirect source or missing source require adds nothing | TS4 |
| AC5 | Versioned replace selection, precedence and no fallback | TS5 |
| AC6 | The original require path stays direct | TS6 |
| AC7 | Existing test suite passes unchanged | TS8 |
| SC1 | All functional requirements are implemented and tested | Functional Requirements Coverage table below (includes TS9, TS10) |
| SC2 | All test scenarios pass | TS1-TS12 |
| SC3 | `python3 -m unittest discover -s tests` passes | TS8 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS1, TS2, TS7, TS11 |
| FR2 | task0001 | TS1, TS2, TS5, TS7 |
| FR3 | task0001 | TS3, TS5, TS12 |
| FR4 | task0001 | TS1, TS6 |
| FR5 | task0001 | TS4, TS5, TS7 |
| FR6 | task0001 | TS9 |
| NFR1 | task0001 | TS1, TS2, TS10 |
| NFR2 | task0001 | TS8 |
| NFR3 | task0001 | TS11, TS12 |

## Manual Testing (E2E Not Possible)
- [ ] TS9: docstring / section comment content and the empty diff under `feature-docs/sca-go-govulncheck-real-output/`
- [ ] TS10: the new test module's imports and offline replay
- [ ] TM-2 code inspection: no filesystem path is built from, resolved from or opened from a replace directive in `em-workflow/scripts/scan-dependencies.py`

## Performance / Security Verification (if applicable)
- TM-1: malformed replace lines are ignored without raising and the go.mod stays readable — checked by TS7 (malformed and glued forms contribute nothing, require-derived direct set intact) and TS11 (no skip reason)
- TM-2: no file is read from a replace directive's path — checked by TS12 (an outside go.mod reached by a local replacement has no effect) plus the TM-2 code inspection under Manual Testing
- TM-3: no text from replace directives reaches any output field; notes stay counts-only — checked by TS11 (marker string absent from the serialized result; only pre-existing note tokens)

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS1-TS12) | 12 | 10 | 0 | 2 |
| Code quality | 1 | 1 | 0 | 0 |
| Success criteria (AC1-AC7, SC1-SC3) | 10 | 9 | 0 | 1 |
| Security (TM-1, TM-2, TM-3) | 3 | 3 | 0 | 0 |
| Manual testing | 3 | 0 | 0 | 3 |
