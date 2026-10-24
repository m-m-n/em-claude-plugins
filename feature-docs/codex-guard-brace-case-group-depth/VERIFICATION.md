# Verification Document: codex-guard-brace-case-group-depth

## Overview
**Feature**: codex-guard-brace-case-group-depth / **SPEC.md**: `feature-docs/codex-guard-brace-case-group-depth/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/codex-guard-brace-case-group-depth/IMPLEMENTATION.md`

The scenario inputs are the ones SPEC.md "Test Scenarios" gives. This
document cites them by ID and does not copy them.

## Build Verification
- Command: none (`project.components.main.build_command` is empty; the guard
  is a Python script with no build step)
- Expected: not applicable

## Test Verification
- Command: `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests`
- Focused command for this guard: `python3 -m unittest tests.test_codex_hook_interactive_guard`
- Expected: exit code 0, no failures or errors
- Coverage target: no coverage tool is configured. The target is scenario
  coverage: every TS-1 to TS-18 below is present and passes on both copies.

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Reproduction 2: `zsh -c` string with `{ : }` in a brace-form item body, launch after the substitution | deny on both copies | Unit (`CASES` row) |
| TS-2 | Contrast: the same with `{ :; }` | deny on both copies | Unit (`CASES` row) |
| TS-3 | Reproduction 3: `always` group in the item body, launch inside quoted text of a later item | silent on both copies | Unit (`CASES` row) |
| TS-4 | Reproduction 4: `function a b { :; }` in the item body, launch inside quoted text of a later item | silent on both copies | Unit (`CASES` row) |
| TS-5 | `always` group, launch after the substitution | deny on both copies | Unit (`CASES` row) |
| TS-6 | `always` right after an argument-position `}`, launch after the substitution | deny on both copies | Unit (`CASES` row) |
| TS-7 | Multi-name `function`, launch after the substitution | deny on both copies | Unit (`CASES` row) |
| TS-8 | Multi-name `function` with an empty `()`, launch after the substitution | deny on both copies | Unit (`CASES` row) |
| TS-9 | Argument-position `}` at depth 0 closes the statement; the substitution closes at `)` | deny on both copies | Unit (`CASES` row) |
| TS-10 | Nested groups closed by argument-position `}` | deny on both copies | Unit (`CASES` row) |
| TS-11 | Quoted `}` is not counted; open group at `;;` | silent on both copies | Unit (`CASES` row) |
| TS-12 | Escaped `}` is not counted | silent on both copies | Unit (`CASES` row) |
| TS-13 | Non-standalone `}` (`a}`) is not counted | silent on both copies | Unit (`CASES` row) |
| TS-14 | The existing row labelled TS-16 by the earlier feature, relabelled to the new reading | deny on both copies; label states that an argument-position `}` closes at depth 0 | Unit (`CASES` row) |
| TS-15 | Existing anonymous-function row (`function { :; }`) | deny on both copies | Unit (`CASES` row) |
| TS-16 | DEPTH nested `{ }` groups closed by argument-position `}` | deny on both copies within the deep-input timeout | Performance |
| TS-17 | `function` followed by DEPTH names | deny on both copies within the deep-input timeout | Performance |
| TS-18 | `_skip_substitution` docstring states the FR5 reading and no longer holds the two old sentences | marker checks pass on both copies | Integration (docstring test) |

The SPEC.md edge cases without a TS ID are verified by the boundary rows
task0001 adds (task0001 AC-2 to AC-5). They are part of the Test Verification
command above.

## Code Quality Verification
- Format: none configured (`format_command` is empty)
- Static analysis: none configured
- Copy identity: `test_the_two_copies_are_byte_identical` passes (NFR2)
- Structure: the existing no-recursion and call-structure tests pass
  (`TestNoRecursion`, `TestSubstitutionSkipCallStructure`)
- Version files: the integration diff against `workflow.implement.base_commit`
  touches neither `em-workflow/.claude-plugin/plugin.json`,
  `em-review/.claude-plugin/plugin.json` nor `.claude-plugin/marketplace.json`
  (NFR3)

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | Reproduction 2 is denied, and the `{ :; }` form stays denied | TS-1, TS-2 |
| AC-2 | Reproduction 3 gives no output | TS-3 |
| AC-3 | Reproduction 4 gives no output | TS-4 |
| AC-4 | Quoted / escaped / non-standalone `}`, `}` in nested lists and in in-form bodies keep the depth and the previous verdict | TS-11, TS-12, TS-13 and the task0001 AC-2 boundary rows; existing rows unchanged |
| AC-5 | `CASES` holds the reproductions and boundary rows; all rows pass on both copies; the old TS-16 row is relabelled | Test Verification command; TS-14 |
| AC-6 | The docstring states FR5 and the marker tests pass | TS-18 |
| AC-7 | The two copies are byte-identical | `test_the_two_copies_are_byte_identical` |
| AC-8 | The full test command passes | Test Verification command |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-6, TS-9, TS-10 |
| FR2 | task0001 | TS-3, TS-5, TS-6 |
| FR3 | task0001 | TS-4, TS-7, TS-8 |
| FR4 | task0001 | TS-15 |
| FR5 | task0001 | TS-18 |
| FR6 | task0001 | TS-14; the Test Verification command over the whole `CASES` table |
| NFR1 | task0001 | TS-16, TS-17 |
| NFR2 | task0001 | Success Criteria AC-7 (byte-identity test) |
| NFR3 | task0001 | Code Quality Verification, version files check |
| NFR4 | task0001 | Manual check of the new tests (standard-library `unittest`, hook run as a subprocess with JSON on standard input) |
| NFR5 | task0001 | Existing `CASES` rows for the reading outside substitutions keep passing; manual review of the guard diff |

## Manual Testing (E2E Not Possible)
- [ ] NFR5: every changed hunk of the guard lies inside the substitution
      reader (`_skip_substitution`, its helpers, their docstrings and
      comments, the comment of the head-state constants). The top-level
      command reading is untouched.
- [ ] NFR4: the tests added by this feature import nothing outside the
      standard library and call the hook only as a subprocess with the JSON
      payload on standard input.

## Performance / Security Verification (if applicable)
- NFR1: TS-16 and TS-17 finish within the deep-input class timeout (60 s) on
  both copies, at the deep-input class depth.
- TM-1: an argument-position `}` in the brace-form item body list itself
  closes the group or the statement, so the launch after the substitution is
  judged. Checked by TS-1, TS-6, TS-9 and TS-10 giving deny on both copies.
- TM-2: the new readings apply only under the FR1 to FR4 conditions.
  - Checked on both copies by:
    - TS-5 to TS-8: deny;
    - TS-11 to TS-13: silent;
    - the task0001 boundary rows, each with the verdict of the intended
      reading: `always` after a separator, `always` after the statement's
      `}`, quoted, escaped and longer `always`, continuation pairs before
      `always`, a quoted extra name, and `}a`;
    - every pre-existing `CASES` row keeping its verdict.
- TM-3: the added state is constant per list and restored by the arithmetic
  re-read. Checked by TS-16 and TS-17 within the timeout, by the task0001
  re-read row, and by the structural tests passing.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS-1 to TS-18) | 18 | 18 | 0 | 0 |
| Success criteria (AC-1 to AC-8) | 8 | 8 | 0 | 0 |
| Code quality / change set | 3 | 3 | 0 | 0 |
| Manual checks (NFR4, NFR5) | 2 | 0 | 0 | 2 |
| Performance / Security (NFR1, TM-1 to TM-3) | 4 | 4 | 0 | 0 |
| **Total** | 35 | 33 | 0 | 2 |
