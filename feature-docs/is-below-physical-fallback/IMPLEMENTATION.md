# Implementation Plan: is-below-physical-fallback

## Overview
This feature changes the cd-prefix path check of the em-workflow Bash guard. A path that Bash reaches through its physical-path fallback is judged by its physical path, and the existing protection is kept: a logical destination outside the area is still not allowed. The feature is a single task (task0001), so this document records only feature-level context. The judgment rule, the tests and the wording change are specified in the task plan.

## Technology Stack
- **Language**: Python 3, standard library only (SPEC NFR1)
- **Test framework**: unittest from the standard library, run with the workflow.yaml test command
- **New dependencies**: none, so there is no license to record (project.license: none)

## Layer Structure
- **Hook**: `em-workflow/hooks/bash_guard.py`. This is the PreToolUse decision for Bash calls. The path check is an internal step of the cd-prefix judgment; it is not an exported interface.
- **Protocol documentation**: `em-workflow/references/command-execution-protocol.md`. Its Verbatim execution rule states the path condition in prose.
- **Tests**: `tests/` at the repository root. The tests exercise the hook; the hook never depends on the tests.

No new layer and no new dependency direction is introduced.

## Shared Components
| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| (none) | The feature has a single task, so no component is built by one task and used by another | - | - |

## Conventions
- The existing hook invariants hold for any change to the hook: standard-library imports only, exit code 0 and nothing on stderr, no `status` substring in executable text, and the prefixed path is never given to a child process (SPEC NFR1-NFR4). Existing tests pin them, and task0001 carries them as constraints.
- When a check fails, the result falls to the no-decision side. A path check that fails leaves the command treated as having no cd prefix; it never produces a new deny (SPEC FR6).

## Cross-task Design Decisions

### Single-task decomposition
- **Decision**: the judgment change, its recurrence tests, and the two written statements of the rule (the hook's module docstring and the protocol's Verbatim execution rule) form one task.
- **Rationale**: the rule wording must match the implemented judgment exactly. Splitting the wording into a parallel task would put one rule in two independent implementations. The whole change fits one implementer session.
- **Affected tasks**: task0001.

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| The guard's model of Bash's cd diverges from what Bash actually does, so a command is allowed where Bash lands outside the area | Low | High (auto-approval outside the area) | The logical-path branch is unchanged: both paths must be strictly below the area. The fallback applies only when the logical path is not an existing directory. See THREAT-MODEL.md TM-1 and TM-2. |
| The /proc-dependent reproduction test cannot run in some environments | Medium | Low | That case is skipped when the process root entry under /proc is not a directory. The /proc-independent symbolic-link reproduction covers the same branch. |
| The new resolution step raises on unusual input and aborts the hook before its later decisions | Low | Medium | See THREAT-MODEL.md TM-4. |

## Open Questions
- [ ] Per-process paths (for example the shell's working-directory entry under /proc) are not special-cased (SPEC A3). The fallback branch makes forms that collapse lexically into a non-existent logical path judgeable by their physical path, as resolved in the hook's process. Whether the hook's working directory always equals the shell's is not established by the SPEC. This is accepted as a residual risk and left for review attention.
