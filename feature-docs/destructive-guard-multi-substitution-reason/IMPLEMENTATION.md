# Implementation Plan: destructive-guard-multi-substitution-reason

## Overview
Regression tests that pin destructive-guard's positional designations when one or
more recursive deletes carry two or more substitution-only targets. The plan has one
task (task0001); the hook changes only when a new test fails on the current hook
(SPEC.md FR6).

## Technology Stack
- **Language**: Python 3, standard library only
- **Test framework**: unittest (standard library), collected by the project's
  `python3 -m unittest discover -s tests` run (NFR1)
- **New dependencies**: none

## Layer Structure
Not applicable: the feature adds one test module that runs the existing hook as a
child process.

## Shared Components
None. The plan has a single task, so no component is used across tasks.

## Conventions
No cross-task conventions: the plan has a single task, and its plan carries the
conventions it follows.

## Cross-task Design Decisions
None.

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| A new test fails on the current hook, so the hook has to change (FR6) | Low: SPEC.md A1 and A6 record that the expected designations were confirmed by running the hook | Medium: the hook is a security guard (THREAT-MODEL.md TM-2) | task0001 changes the hook only after a new test fails, under the constraints its plan states, and both test suites must pass |
| The test outcome depends on the runner's environment (an unattended run sets CLAUDE_BATCH) | Medium | Low: a false failure, not a missed regression | task0001 builds the child environment explicitly (NFR1, its AC-1) |

## Open Questions
- None.
