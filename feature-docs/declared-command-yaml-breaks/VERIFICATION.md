# Verification Document: declared-command-yaml-breaks

## Overview
**Feature**: declared-command-yaml-breaks / **SPEC.md**: `feature-docs/declared-command-yaml-breaks/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/declared-command-yaml-breaks/IMPLEMENTATION.md`

Scenario IDs use the TS-n form. TS-1 to TS-4 correspond, number for number, to SPEC.md's TS1 to TS4. TS-5 and TS-6 are added here for FR4 and NFR6, which SPEC.md's test scenarios do not cover.

## Build Verification
- Command: none (`project.components.main.build_command` is empty; Python, no build step)
- Expected: not applicable

## Test Verification
- Command: `python3 -m unittest discover -s tests`
- Expected: exit code 0, no failures or errors
- Focused runs (same expectation): `python3 -m unittest tests.test_bash_guard_declared_yaml_breaks`, `python3 -m unittest tests.test_bash_guard_unicode_whitespace`, `python3 -m unittest tests.test_bash_guard_store_unicode_whitespace`, `python3 -m unittest tests.test_hook_classification_pin`
- Coverage: not measured (standard library `unittest` only). Every task Acceptance Criterion maps to at least one test or check below.

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | New module `tests/test_bash_guard_declared_yaml_breaks.py` with its own fixture: a repository with declarations, a repository without declarations, a store holding only `/usr/bin/true`. For each character (U+0085, U+2028, U+2029) × position (leading, trailing) × command form (raw, YAML-parsed, end-stripped), run the hook as a subprocess. Also run `./unapproved` padded at either end, `/usr/bin/true` padded with each of the three characters, and bare `/usr/bin/true`. | Every raw, YAML-parsed and end-stripped form is denied with a reason containing 未承認. No padded or end-stripped form is allowed. Padded `/usr/bin/true` is denied where declared and gets no verdict without declarations. Bare `/usr/bin/true` is allowed by exact match. The existing test file's `declared_lines` is unchanged. | Integration |
| TS-2 | U+00A0 form: a direct call to `declared_commands` (module loaded without writing bytecode) with `test_command:` followed by U+00A0 + `make lint`. Also run the existing assertions at lines 418 and 422 of `tests/test_bash_guard_unicode_whitespace.py`. | The set contains U+00A0 + `make lint` and not `make lint`. The existing assertions pass with those lines unchanged. | Unit |
| TS-3 | Edge cases: a single-quoted and an unquoted declaration with one of the three characters at an end. A double-quoted value that is only U+0085. | The end-stripped form is in the declared set for the single-quoted and unquoted declarations. The value that is empty after end-stripping contributes no form (b) entry, and its `trim_blanks` form is still in the set. | Unit |
| TS-4 | Full suite `python3 -m unittest discover -s tests`, including the pinned checks: standard-library-only imports, no `status` substring, helpers defined once and in order, `trim_blanks` removing spaces and tabs only, pinned docstring phrases, no raw U+0085 / U+2028 / U+2029 in `bash_guard.py`, and the new test module using only standard library with escaped non-ASCII and no PyYAML. | Exit code 0. | Integration |
| TS-5 | Documentation appendix: diff of `feature-docs/approval-unicode-whitespace/SPEC.md` and `feature-docs/approval-unicode-whitespace/THREAT-MODEL.md` against the base, plus a read of the appended text. | FR8 and TM-5 each carry both FR4 points, naming U+0020, U+0009, U+0085, U+2028 and U+2029. Removing the appended text gives back the base content byte for byte. No new heading, `TB-n` or `TM-n`. `reviews/round1.yaml` and `em-workflow/references/command-execution-protocol.md` are unchanged. | Manual |
| TS-6 | Version fields: list the files changed by the feature against the base. | `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` are not in the list. | Diff check |

## Code Quality Verification
- Format: none (`project.components.main.format_command` is empty)
- Static analysis: none configured. The source constraints (NFR1 to NFR5) are checked by the tests in TS-4.

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | FR1 to FR5 are implemented and tested | TS-1, TS-2, TS-3, TS-5 pass |
| SC-2 | SPEC TS1 to TS4 all pass | TS-1 to TS-4 pass |
| SC-3 | The allow scope has not widened, per FR3 | TS-1's allow assertions and TM-2 below |
| SC-4 | The FR4 documentation appendix is done | TS-5 |
| SC-5 | Code review is completed | Review phase result for this feature |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-3 |
| FR2 | task0001 | TS-2 |
| FR3 | task0001 | TS-1 |
| FR4 | task0002 | TS-5 |
| FR5 | task0001 | TS-1 |
| NFR1 | task0001 | TS-4 |
| NFR2 | task0001 | TS-4 |
| NFR3 | task0001 | TS-4 |
| NFR4 | task0001 | TS-4 |
| NFR5 | task0001 | TS-4 |
| NFR6 | task0001 | TS-6 |

## Manual Testing (E2E Not Possible)
- [ ] TS-5: read the text appended to approval-unicode-whitespace's SPEC.md FR8 and THREAT-MODEL.md TM-5. Confirm both FR4 points are stated, and confirm from the diff that only insertions occurred.

## Performance / Security Verification (if applicable)
- TM-1: the declared set also holds each value with leading and trailing U+0020, U+0009, U+0085, U+2028 and U+2029 removed. Checked by TS-1 (every raw, YAML-parsed and end-stripped form is denied as unapproved for each character and position) and TS-3 (single-quoted and unquoted declarations, values that become empty).
- TM-2: allow stays limited to the exact match and the cd-prefix form, and never consults the declared set. Checked by TS-1 (no padded or end-stripped form is allowed; padded `/usr/bin/true` is denied or gets no verdict; bare `/usr/bin/true` keeps its exact-match allow) and TS-4 (existing allow and `trim_blanks` tests still pass).

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS-1 to TS-4) | 4 | 4 | 0 | 0 |
| Documentation (TS-5) | 1 | 0 | 0 | 1 |
| Change-set check (TS-6) | 1 | 1 | 0 | 0 |
| Security (TM-1, TM-2) | 2 | 2 | 0 | 0 |
| Total | 8 | 7 | 0 | 1 |
