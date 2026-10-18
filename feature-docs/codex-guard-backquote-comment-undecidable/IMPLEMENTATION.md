# Implementation Plan: codex-guard-backquote-comment-undecidable

## Overview
When reading a string stops at `_Undecidable`, codex-hook-interactive-guard judges the commands
settled up to the last checkpoint instead of judging nothing. The feature is a single task,
task0001: every change lands in the same three files, and the two guard copies must stay
byte-identical (FR5).

## Technology Stack
- **Language**: Python 3, standard library only (NFR2)
- **Test framework**: unittest. The suite is `tests/test_codex_hook_interactive_guard.py`, and it
  runs each copy as a child process.
- **New dependencies**: none. `project.license` is `none`, so there is no license to record.

## Layer Structure
The guard is one module. It has three layers, and each layer depends only on the layers below it:

1. **Entry** (main, find_deny): reads the hook JSON, starts the walk at the hook command, and
   prints one deny object or nothing.
2. **Walk** (_scan, _judge): walks the simple commands of the hook command and of every nested
   literal shell `-c` string with an explicit work list, and judges each simple command.
3. **Reader** (_Parser, parse): turns one string into simple commands with their group context.
   Raises `_Undecidable` when the string cannot be read.

The feature changes only the contract between the Reader and its two callers: the top-level call
in find_deny and the nested call in _scan. It adds no layer and no module.

## Shared Components
| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| (none) | - | The feature has one task, so no task builds a component that another task uses. | - |

## Conventions
These rules apply to every task that touches the guard or its tests, including rework tasks added
later:

- **Two copies**: change `em-workflow/scripts/codex-hook-interactive-guard.py` and
  `em-review/scripts/codex-hook-interactive-guard.py` in the same task and the same commit, and
  keep them byte-identical (FR5, `.claude/rules/hook-tests.md`).
- **Symbols**: no existing symbol is removed or renamed (A3). New private helpers and attributes
  are allowed.
- **Constraints**: standard library only; no file, network or child-process access; the decision
  depends on the command string alone (NFR2). No recursion; reading stays linear in the length of
  the string (NFR1).
- **Output**: the deny reason text and the output shape stay unchanged (NFR3). No task changes a
  plugin version field (NFR3).
- **Test table**: test cases are CASES rows of (expected verdict, label, command), and the same
  table runs against both copies. Expected verdicts are `deny` or `silent`. Every row accepted as
  a known false deny has a label that starts with 既知の誤拒否 (A2). Existing rows are never removed
  and their expected values never change (FR3).

## Cross-task Design Decisions
The feature has one task. The decision below binds task0001 and any rework task added later.

### D1: Error-handling policy of the guard
- **Decision**:
  - `_Undecidable` is the one outcome that keeps partial results. The guard judges the commands
    settled before the last checkpoint, and it judges nothing when there is no checkpoint.
  - Any other exception keeps today's handling. In a nested string it skips that string and the
    walk goes on. At the top level the hook gives no output.
  - The range of the comment exception, `_scan_parens`, `_read_argument_parens`, the rescue rules,
    and the reading of separators, groups and heredocs do not change.
- **Rationale**: FR2 and FR3. This is approach (a), adopted at create-spec. Approach (b), which
  narrows the comment exception, is not taken.
- **Affected tasks**: task0001.

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| A checkpoint in the wrong place turns an existing silent row, or a connected or skipped command, into a false deny | Medium | High | Implement only the four FR2 conditions; settle connection and skip with the full-read rule; run the whole CASES table plus the eleven new silent rows |
| The docstring rewrite drops an existing marker sentence or brings back a stale one | Medium | Medium | Existing documentation tests stay unchanged; new checkpoint markers are added; the stale sentence lists are checked |
| The two copies drift apart | Low | High | Byte-identity test; both copies are edited in one task |
| The new path makes reading superlinear on crafted input | Low | Medium | Checkpoints record counts only; settlement visits each group once; a deep-input test for the checkpoint path |
| Accepted false denies: a zsh `-c` string with a later syntax error, and a line inside `if` / `while` / `for` / `case` | Accepted (A2) | Low | Rows labelled 既知の誤拒否 pin the accepted behaviour |

## Open Questions
- None.
