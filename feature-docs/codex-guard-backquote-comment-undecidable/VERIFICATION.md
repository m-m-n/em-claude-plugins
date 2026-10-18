# Verification Document: codex-guard-backquote-comment-undecidable

## Overview
**Feature**: codex-guard-backquote-comment-undecidable / **SPEC.md**: `feature-docs/codex-guard-backquote-comment-undecidable/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/codex-guard-backquote-comment-undecidable/IMPLEMENTATION.md`

Scenario IDs in this document use the TS-n form. They map one-to-one onto SPEC.md as follows:

| This document | SPEC.md |
|---|---|
| TS-1 to TS-7 | TS1 to TS7 |
| TS-8 | IT1 |

## Build Verification
- Command: none. `project.components.main.build_command` is empty, because the guard is a Python
  script with no build step. The test run below loads both copies.
- Expected: not applicable.

## Test Verification
- Command (project test command): `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests`
- Command (guard suite, `.claude/rules/hook-tests.md`): `python3 -m unittest tests.test_codex_hook_interactive_guard`
- Expected: both commands exit with status 0.
- Coverage target: not measured, because the project configures no coverage tool. Every scenario
  below maps to automated tests that run against both copies.

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | The FR1 reproduction row: a nested `bash -c` string whose first line is `python3 -B -S -i`, followed by an anonymous-function line that becomes undecidable | permissionDecision deny from both copies | Unit (CASES row, run as a child process) |
| TS-2 | The six FR4 deny rows: top-level `-i` before an unbalanced quote; a launch with no program before an unbalanced quote; a nested `-c` string with `-i` before an unbalanced quote; a closed group before the checkpoint; a `-c` string on a line before the checkpoint; a launch after a fully read heredoc | deny from both copies | Unit (CASES rows) |
| TS-3 | The two FR4 rows accepted as false denies: a `zsh -c` string with a later syntax error, and a line inside `if` (labels start with 既知の誤拒否) | deny from both copies | Unit (CASES rows) |
| TS-4 | The eleven FR4 silent rows: same-line launch; `\|`, `\|&`, `&&` and `\|\|` continuations; blank line after `&&`; open group; unterminated heredoc body; connected group; function-definition body; right side of a pipe | no output from both copies | Unit (CASES rows) |
| TS-5 | All CASES rows that existed before, unchanged, plus the SPEC.md edge cases: the anonymous-function argument whose backquote span holds `)` with the real `)` after `#` stays deny; an unterminated heredoc on the launch line stays silent; `cat <<EOF` followed by `python3 -i` stays silent; an error other than `_Undecidable` still skips the string | every row keeps its expected verdict; no row removed; TestNestedReadLimit (including test_a_string_that_proves_undecidable_still_counts) and TestFailOpen pass | Unit |
| TS-6 | TestCopies, TestGuardDocumentation (including the added checkpoint markers) and TestNestedParseErrorContainment, plus TestStaticConstraints | all pass for both copies | Unit (syntax-tree and file checks) |
| TS-7 | The existing performance tests (TestMalformedAndDeepInput), the recursion check (TestNoRecursion), and the new deep-input shape for the checkpoint path | all pass for both copies within the class time limit | Unit (timed child-process runs) |
| TS-8 | The whole suite: `python3 -m unittest tests.test_codex_hook_interactive_guard && python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests` | exit status 0 | Integration |

## Code Quality Verification
- Format: none (`project.components.main.format_command` is empty).
- Static analysis: these checks run as part of the guard suite, on the syntax tree of each copy:
  - TestStaticConstraints: standard library only; no file writes, network or child processes.
  - TestNoRecursion: no self-call and no call cycle.
  - TestNestedParseErrorContainment: one try around the nested parse call, catching
    `_Undecidable` and the general exception class, whose handler neither returns nor raises.

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | SPEC AC1: the FR1 reproduction JSON yields deny from both copies | TS-1 |
| SC-2 | SPEC AC2: every row added for FR4 has its expected verdict in both copies | TS-2, TS-3, TS-4 |
| SC-3 | SPEC AC3: existing CASES rows and TestNestedReadLimit pass unchanged, including test_a_string_that_proves_undecidable_still_counts | TS-5 |
| SC-4 | SPEC AC4: TestCopies.test_the_two_copies_are_byte_identical passes | TS-6 |
| SC-5 | SPEC AC5: the documentation tests pass, including the added wording | TS-6 |
| SC-6 | SPEC AC6: both test commands pass | TS-8 |
| SC-7 | NFR3: plugin version fields and the deny reason text are unchanged | The diff of the integration branch against its base shows no change to any `plugin.json` or to `.claude-plugin/marketplace.json`; TestDenyOutput passes |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1 |
| FR2 | task0001 | TS-2, TS-3, TS-4 |
| FR3 | task0001 | TS-5 |
| FR4 | task0001 | TS-1, TS-2, TS-3, TS-4 |
| FR5 | task0001 | TS-6 |
| FR6 | task0001 | TS-6 |
| NFR1 | task0001 | TS-7, TS-8 |
| NFR2 | task0001 | TS-6, TS-8 |
| NFR3 | task0001 | TS-8, SC-7 |

## Manual Testing (E2E Not Possible)
- [ ] Read the rewritten passages in the module docstring (steps 3, 4, 7 and 9, and the paragraph
      that begins "Everything the guard cannot positively identify passes"), the _scan docstring
      and the _Parser docstring. Check that the retained "no output" sentences and the added
      checkpoint sentences read as one consistent rule. The marker tests check that the sentences
      are present, not that they agree with each other.

## Performance / Security Verification (if applicable)
- NFR1: reading stays linear in the length of the string, and nothing recurses. Checked by TS-7:
  the existing deep-input tests and the new checkpoint-path shape answer within
  TestMalformedAndDeepInput's time limit, and TestNoRecursion passes.
- NFR2: the guard stays standard-library only and side-effect free, and errors on the nested parse
  are contained. Checked by TS-6 (TestStaticConstraints, TestNestedParseErrorContainment).
- TM-1: when reading stops at `_Undecidable`, the guard judges the commands settled up to the last
  checkpoint, at the top level and in every nested `-c` string. Checked by the TS-1, TS-2 and TS-3
  CASES rows: each must be a deny from both copies.
- TM-2: the checkpoint path costs constant time per newline and visits each group once in
  settlement, with no recursion. An undecidable nested string counts at full length toward
  NESTED_READ_LIMIT. Checked by TS-7 (the new deep-input shape with many checkpoints and deeply
  nested closed groups before an unbalanced quote answers in time, with a deny) and by TS-5
  (test_a_string_that_proves_undecidable_still_counts) and TS-6 (TestNestedParseErrorContainment).
- TM-3: a checkpoint requires all four FR2 conditions, and connection and skip use the full-read
  rule. Checked by the TS-4 silent rows (continuations, open group, unterminated heredoc,
  connected group, function body, pipe right side) and by TS-5 (all existing rows unchanged).

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios (TS-1 to TS-8) | 8 | 8 | 0 | 0 |
| Success criteria (SC-1 to SC-7) | 7 | 7 | 0 | 0 |
| Performance / security (NFR1, NFR2, TM-1, TM-2, TM-3) | 5 | 5 | 0 | 0 |
| Manual review | 1 | 0 | 0 | 1 |
| **Total** | 21 | 20 | 0 | 1 |
