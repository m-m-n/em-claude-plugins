# Implementation Plan: declared-command-edge-fold

## Overview
`hook_main` in `em-workflow/hooks/bash_guard.py` also matches the received command with six characters stripped from both ends against the declared set. The YAML-parsed form of a declaration whose ends mix or repeat U+0085, U+2028 and U+2029 is then denied as unapproved, and what the hook allows is unchanged. One implementation task (task0001) carries the code, the docstring and comments, and the tests. The planner made the appends to four documents of other features during create-plan.

## Technology Stack
- **Language**: Python 3.14, standard library only (NFR1)
- **Tests**: standard-library unittest, run by `python3 -m unittest discover -s tests` (NFR6)
- **New dependencies**: none. No license to record.

## Layer Structure
- PreToolUse hook script: `em-workflow/hooks/bash_guard.py`. Its allow / deny / no-decision outcome is the approval gate.
- Tests: `tests/`. They run the hook as a subprocess and load the module directly without writing bytecode.

Tests depend on the hook; the hook depends on nothing in `tests/`.

## Shared Components
None. The feature has one implementation task, so no component is built by one task and used by another.

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|

## Conventions
The terms below are used with the same meaning in task0001, VERIFICATION.md, THREAT-MODEL.md, and the four amended documents of other features.

- **Six characters**: U+0020, U+0009, LF (U+000A), U+0085, U+2028, U+2029. They are named by code point in prose. They are never written raw in `bash_guard.py` or in test source (NFR4, NFR6).
- **End-stripped form**: the received command with every leading and trailing occurrence of the six characters removed from both ends. It is distinct from the five-character `DECLARED_END_STRIP` form that `declared_commands` adds to the declared set.
- **No decision**: the hook returns neither allow nor deny, so the normal permission prompt follows. Tests expect it as silent.

## Cross-task Design Decisions

### D1: Other-feature documents are amended by the planner
FR5 asks for appends to four documents: approval-unicode-whitespace's SPEC.md (FR8) and THREAT-MODEL.md (TM-5), and declared-command-yaml-breaks' SPEC.md (FR1) and THREAT-MODEL.md (TM-1). The planner made these appends during create-plan through the other-feature document route, so no task lists those paths.
- Each append is inserted next to the item it extends. No existing line is changed.
- The appends cover the three points of FR5: the end-stripped declared match, the widened deny of FR3, and the out-of-scope cases.
- `feature-docs/*/reviews/round1.yaml` and `em-workflow/references/command-execution-protocol.md` stay unchanged.

Affected: VERIFICATION.md TS-9 checks these appends.

### D2: Plugin version
The repository bumps plugin versions through its own automation. No task edits `plugin.json` or `.claude-plugin/marketplace.json` (NFR7).

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| An existing test beyond the one SPEC.md names expects no decision for a form that the end-stripped match now denies | Low | Medium | task0001 reports it as a plan deviation instead of editing the test, and the expectation is decided in review |
| The widened deny (FR3) blocks an approved command padded at an end with LF, U+0085, U+2028 or U+2029 in a repository that declares it | Low | Low | Accepted by SPEC.md A2. Recorded in the four amended documents and pinned by TS-3 |

## Open Questions
- None.
