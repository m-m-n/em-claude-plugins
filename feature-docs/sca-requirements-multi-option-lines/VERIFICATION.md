# Verification Document: sca-requirements-multi-option-lines

## Overview
**Feature**: sca-requirements-multi-option-lines / **SPEC.md**: `feature-docs/sca-requirements-multi-option-lines/SPEC.md` / **IMPLEMENTATION.md**: not produced (tier `reduced`, single task — no cross-task decisions) / **THREAT-MODEL.md**: `feature-docs/sca-requirements-multi-option-lines/THREAT-MODEL.md`

Scenario IDs keep SPEC.md's TSn form so that TS1–TS9 string-match SPEC.md's Test Scenarios; TS10–TS13 are extracted from SPEC.md's Edge Cases, FR1, NFR4, NFR5 and NFR6.

## Build Verification
- Command: none. Both components (`repo-tests`, `plugin-invariants`) are Python with an empty `build_command`.
- Expected: not applicable.

## Test Verification
- Command (repo-tests): `python3 -m unittest discover -s tests`
- Command (plugin-invariants): `python3 em-workflow/scripts/check-plugin-invariants.py .`
- Expected: both exit with code 0.
- Coverage target: not measured (no coverage tool is configured). Every Acceptance Criterion of task0001 maps to at least one scenario below.

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS1 | requirements.txt is only `-c constraints.txt -r deps.txt`; deps.txt declares vuln-pkg, which has a high advisory (SPEC AC1) | Resolver: names {vuln-pkg}, complete=True; the open recorder shows constraints.txt never opened; full scan through the pip-audit substitute: exactly 1 finding, no `pip_directness_undetermined` note | Unit + Integration |
| TS2 | Same as TS1 with `--index-url https://x/simple -r deps.txt` (SPEC AC2) | Same results as TS1; the network guard records no connection attempt | Unit + Integration |
| TS3 | One line with `-r a.txt -r b.txt`; and the forms `-c c.txt --requirement=b.txt`, `-c c.txt -rb.txt`, `--index-url URL --requirement b.txt`, as subTests (SPEC AC3) | Names from both a.txt and b.txt; b.txt followed in every form; c.txt never opened | Unit |
| TS4 | Unsplittable option lines: unclosed quote (`-c a -r "deps.txt`), trailing escape (SPEC AC4) | complete=False; an undeclared high advisory counted exactly once as pip undetermined; no exception; other lines and files still read | Unit + Integration |
| TS5 | Includes without a value: `--index-url URL -r`, a trailing `--requirement`, an empty `--requirement=` (SPEC AC5, FR4 edge cases) | complete=False in each case | Unit |
| TS6 | Mid-line includes using `..`, an absolute path, and a URL (`-c a -r ../outside/x.txt`, `--index-url URL -r https://...`) (SPEC AC6) | The open recorder shows no file opened outside the root; the network guard shows no access; complete=False | Unit |
| TS7 | Non-leading `-e` / `-eX` / `--editable X` / `--editable=X`, each with a value yielding no name and a value yielding a name; and a leading `-e` (SPEC AC7) | Named value: the name is a direct name; nameless or missing value: complete=False; a leading `-e` takes only the next token as its value | Unit |
| TS8 | Abbreviations of `--requirement` and `--editable`, space-separated and with `=` (`--requirem deps.txt`, `--requirem=deps.txt`, `-c a --editab ./pkg`), and ambiguous prefixes `--re`, `--e` (SPEC AC8) | complete=False; the referenced file is never opened | Unit |
| TS9 | Full existing suite and plugin invariants check (SPEC AC9) | `python3 -m unittest discover -s tests` and `python3 em-workflow/scripts/check-plugin-invariants.py .` both pass, including the standard-library-only test and every existing test in `tests/test_scan_dependencies_pip_directness.py` | Integration |
| TS10 | Option lines containing only `--index-url URL`, `--hash=...`, unknown option tokens, or a lone `--` (SPEC Edge Cases, FR6, FR7) | Ignored; completeness unchanged (complete=True when nothing else is incomplete); nothing opened | Unit |
| TS11 | The same include target named twice on one line (`-r deps.txt -r deps.txt`), and a two-file cycle formed by mid-line includes (FR1 at-most-once rule) | Each file opened at most once (open recorder); resolution terminates; names collected; no exception | Unit |
| TS12 | Summary text for the TS4 unsplittable line and the TS6 outside-root include (NFR4, FR8) | The summary carries the `pip_directness_undetermined` token with its count, and contains no splitter error text, no requirements line content, no path name; no new note token exists | Integration |
| TS13 | Diff of the integration branch against the base branch (NFR5, NFR6) | `tests/test_scan_dependencies_pip_directness.py` has additions only (no existing line removed or changed); the version fields of `em-workflow/.claude-plugin/plugin.json` and of `.claude-plugin/marketplace.json` are unchanged | Integration (diff check) |

## Code Quality Verification
- Format: none configured (`format_command` is empty for both components).
- Static analysis: none configured.
- Standard library only: covered by the standard-library-only test inside TS9 (NFR1).

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC1 | FR1–FR8 are implemented and tested | Functional Requirements Coverage table below: every FR has a passing scenario |
| SC2 | NFR1–NFR6 are met | TS4 (NFR2), TS6 / TS8 (NFR3), TS9 (NFR1, NFR5), TS12 (NFR4), TS13 (NFR5, NFR6) |
| SC3 | TS1–TS9 all pass | Run the two Test Verification commands |
| SC4 | SPEC AC1–AC9 are all met | AC1→TS1, AC2→TS2, AC3→TS3, AC4→TS4, AC5→TS5, AC6→TS6, AC7→TS7, AC8→TS8, AC9→TS9 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS1, TS2, TS3, TS6, TS11 |
| FR2 | task0001 | TS1, TS3 |
| FR3 | task0001 | TS4 |
| FR4 | task0001 | TS5 |
| FR5 | task0001 | TS7 |
| FR6 | task0001 | TS8, TS10 |
| FR7 | task0001 | TS2, TS10 |
| FR8 | task0001 | TS1, TS4, TS12 |
| NFR1 | task0001 | TS9 |
| NFR2 | task0001 | TS4, TS11 |
| NFR3 | task0001 | TS2, TS6, TS8 |
| NFR4 | task0001 | TS12 |
| NFR5 | task0001 | TS9, TS13 |
| NFR6 | task0001 | TS13 |

## Manual Testing (E2E Not Possible)
- None. The reproduction steps in the feature goal are automated by TS1 and TS2 (pip-audit substitute, network guard), so no live pip-audit run is required.

## Performance / Security Verification (if applicable)
- TM-1: outside-root include targets at any token position are not opened, and abbreviated long-option tokens are never resolved to a file — checked by TS6 and TS8 (open recorder shows no such open; complete=False).
- TM-2: URL include targets at any token position are never fetched, and editable URL values are never fetched — checked by TS2, TS6 and TS7 (network guard records no connection attempt).
- TM-3: uninterpretable option lines fail closed (no names, complete=False, undeclared advisories counted under `pip_directness_undetermined`) — checked by TS4, TS5, TS7 and TS8.
- TM-4: split failures do not escape the resolver and repeated or cyclic includes terminate with each file opened at most once — checked by TS4 (no exception) and TS11 (open recorder counts, termination).
- TM-5: includes and editables are followed regardless of their position on the line, and constraint targets are never opened — checked by TS1, TS2, TS3 and TS7.
- TM-6: the summary reports an incomplete set only by the existing note token and a count, with no splitter error text, line content or path name — checked by TS12.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS1–TS13) | 13 | 13 | 0 | 0 |
| Code quality | 1 | 1 | 0 | 0 |
| Success criteria | 4 | 4 | 0 | 0 |
| Requirements coverage | 14 | 14 | 0 | 0 |
| Security (TM-1–TM-6) | 6 | 6 | 0 | 0 |
| Manual | 0 | 0 | 0 | 0 |
