# Implementation Plan: resolve-findings-parent-symlink

## Overview
`em-workflow/scripts/resolve-verified-findings.py` stops following symbolic links at the feature
directory's final element, at `reviews` and at the round record, and makes every check, read and
write after opening `reviews` relative to that one held directory handle (SPEC FR1-FR8). The work
is a single task (task0001).

## Technology Stack
- **Language**: Python 3 (POSIX: Linux / macOS, NFR2)
- **Key libraries**: Python standard library - handle-relative file operations; PyYAML - existing
  safe load / safe dump, unchanged (NFR1)
- **New dependencies**: none. No license is added to the project.

## Layer Structure
One CLI script with four stages, unchanged in order:

1. Argument parsing (command line unchanged, FR4).
2. Input reading: feature directory and `workflow.yaml`, then the mapping file, then `reviews` and
   the latest round record.
3. Eligibility and rewrite of findings (unchanged).
4. Replacement of the round record.

This feature changes stages 2 and 4 only. The order in which inputs are checked, and therefore
which error code is reported when several inputs are broken at once, stays as it is today.

## Shared Components
| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| (none) | The feature has one task; no component is built by one task and used by another | - | - |

## Conventions
- **Error codes**: no new error code (FR4). A feature-directory problem is `invalid-workflow`; a
  link at `reviews`, and any record that is not a regular file or cannot be opened or read, is
  `invalid-round-record`; an absent `reviews`, or one that is neither a directory nor a link, is
  `missing-round-record` as today.
- **Output**: on failure stdout is empty and stderr is exactly one line holding the code; no path,
  link target or operating-system error text is printed (NFR4, THREAT-MODEL.md TM-6).
- **Fail closed**: every failure happens before the first write, or removes the temporary file and
  leaves the record unchanged.
- **Tests**: standard-library unittest only; anything that needs PyYAML runs in a child process
  (NFR1). Race tests reproduce the swap deterministically from a wrapper hook and never use CPU load
  (NFR3).

## Cross-task Design Decisions

### D1: one task
The handle chain (feature directory, then `reviews`, then record and temporary file) runs through
the same few functions of one script, and each requirement depends on the handle opened by the
previous one. Parallel tasks on that chain would edit the same functions and could not be tested
on their own, so the feature is one task even though its acceptance criteria number more than
seven. Affected: task0001.

### D2: handle-relative access instead of a resolved-path containment check
The fix opens entries without following links and works relative to the opened handles; it does
not resolve paths and compare them against the worktree (SPEC Assumptions). Ancestors of the
feature directory are not checked (FR5). Affected: task0001.

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| The error number returned for a no-follow open of a link differs between POSIX systems, so a code chosen from it is wrong on one of them | Medium | `reviews` links reported with the wrong code on macOS or Linux | task0001 chooses the code from a no-follow status query of the entry, never from the error number |
| A FIFO placed in a test fixture blocks the test suite's own tree snapshot helper, which reads every file | High | The suite hangs instead of failing | task0001 makes the helper record special files by kind without opening them, and runs the FIFO case with a child-process timeout |
| A race test that depends on timing passes or fails at random | Medium | Unreliable verification of FR3 / FR8 | Swaps are triggered from wrapper hooks at fixed calls (NFR3), never by load or sleeps |

## Open Questions
- None.
