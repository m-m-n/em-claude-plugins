# Implementation Plan: codex-guard-reserved-word-funcdef

## Overview
The guard's function-name recognition removes a leading run of shell reserved words before it decides whether the words before `(` name a function. A definition written right after `then`, `do`, `else`, `!`, `time` and the like becomes silent again. A group after an array assignment, or after any other non-definition head, is still judged.

## Technology Stack
- **Language**: Python 3, standard library only (NFR2)
- **Test framework**: unittest (standard library), driving each hook copy as a separate process
- **New dependencies**: none. `project.license` is `none`; no dependency license needs recording

## Layer Structure
- **Hook script** (two byte-identical copies, one per plugin): reads stdin, parses the command string into simple commands and groups, and judges each simple command. The parser owns function-definition recognition; the judging step consumes only the parser's output.
- **Contract test table**: one table of cases that drives both copies as separate processes. The tests never import the hook module.

Dependency direction: tests -> hook process (through stdin/stdout only). The hook depends on nothing outside the standard library.

## Shared Components
| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| None across tasks | The feature has a single task (task0001), which owns both hook copies and the test file. No component is built by one task and consumed by another | — | task0001 |

## Conventions
- **Byte-identical copies**: `em-workflow/scripts/codex-hook-interactive-guard.py` and `em-review/scripts/codex-hook-interactive-guard.py` change together in the same commit and stay byte-identical (FR9, NFR1).
- **Case table format**: every new case goes into the existing `CASES` table as an (expected verdict, label, command) triple. The expected verdict is `deny` or `silent`, and labels follow the table's existing Japanese labelling. Commands are unique across the table, and no existing entry is removed or has its expected verdict changed (FR8, NFR5).
- **Fail-open**: input the guard cannot decide produces no output, exit status 0 and empty standard error (NFR3). The change adds no new error path.
- **No recursion**: groups stay tracked on the existing explicit stack, and the new removal step is a single forward pass over the words (NFR4, TM-2).
- **Test command for this hook**: `python3 -m unittest tests.test_codex_hook_interactive_guard`, run in the same change (project rule for this hook).

## Cross-task Design Decisions

### Single-task decomposition
- **Decision**: one task covers both hook copies, the docstrings and the test table.
- **Rationale**: the two copies must change in the same commit and stay byte-identical. The new test cases are the TDD contract for the parser change, so splitting code from tests or one copy from the other would leave a task that cannot pass its own tests alone.
- **Affected tasks**: task0001

### Plugin version handling
- **Decision**: no task changes any plugin version (NFR6). This repository bumps plugin versions through its own push-time automation.
- **Affected tasks**: task0001

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Widened recognition makes an executed group read as a function body (missed detection) | Medium | High | Removal limited to the leading run of reserved words, with the unstripped fallback and the unchanged name conditions. Deny cases pin every non-definition shape (THREAT-MODEL.md TM-1) |
| The removal step slows down on a pathological run of reserved words | Low | Medium | Single forward pass, and a long-run case is answered within the deep-input time limit (THREAT-MODEL.md TM-2) |
| The two copies drift apart | Low | Medium | The existing byte-identity test, and both copies edited in the same change |
| A docstring rewrite breaks an existing documentation marker | Medium | Low | The existing marker sentence is kept verbatim, and the documentation test runs every marker against both copies |

## Open Questions
- None
