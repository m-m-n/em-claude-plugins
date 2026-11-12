# Implementation Plan: destructive-guard-multi-substitution-reason

## Overview
Regression tests that pin destructive-guard's positional designations when one or
more recursive deletes carry two or more substitution-only targets (task0001, merged),
and a change to how `tests/test_destructive_guard_mixed_rm_precedence.py` selects its
own cases from the case table, so that the full test suite passes again (task0002,
SPEC.md FR12). The hook changes only when a new test fails on the current hook
(SPEC.md FR6).

## Technology Stack
- **Language**: Python 3, standard library only
- **Test framework**: unittest (standard library), collected by the project's
  `python3 -m unittest discover -s tests` run (NFR1)
- **New dependencies**: none

## Layer Structure
Not applicable: the feature adds one test module that runs the existing hook as a
child process, and changes the case selection of one existing test module.

## Shared Components
None. task0001 and task0002 use no component of each other and declare no common file.

## Conventions
- Pre-existing test files stay unchanged (SPEC.md FR4), with exactly one exception:
  `tests/test_destructive_guard_mixed_rm_precedence.py`, which only task0002 changes,
  and only within FR12's scope.
- No task changes `em-workflow/hooks/tests/destructive-guard-cases.json`.

## Cross-task Design Decisions
None.

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| A mixed-rm-precedence case that task0002's label selection keeps fails against the current hook (a decision change made after that feature merged) | Low: SPEC.md A7 attributes every verify round 1 failure in that module to the cases after its own 33 | Medium: it would be a real guard regression (THREAT-MODEL.md TM-3) | task0002 changes neither the hook nor any expectation; it reports the failing case as a plan deviation, which becomes a new task |
| A check of the mixed-rm-precedence module other than the two selections still fails after the change | Low: SPEC.md A8 records that the head-of-table check passes today | Low | task0002 leaves that check unchanged and reports a plan deviation (FR12 limits the change) |
| A test outcome depends on the runner's environment (an unattended run sets CLAUDE_BATCH) | Medium | Low: a false failure, not a missed regression | task0001 builds the child environment explicitly (NFR1, its AC-1) |

## Open Questions
- None.
