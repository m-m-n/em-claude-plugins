# Implementation Plan: codex-guard-redirect-only-list-pending

## Overview
The guard parser's list continuation also ends after a redirect-only simple
command, at a separator other than a newline, and at a `)` that closes a `(`
group after a redirect-only simple command, so the checkpoint rule denies an
explicit interactive launch on an earlier line. The feature is one task
(task0001) that changes both guard copies and the case table together.

## Technology Stack
- **Language**: Python 3, standard library only (NFR2) — the hook script and its unittest suite.
- **New dependencies**: none. No license entry is needed (`project.license: none`).

## Layer Structure
One layer: the guard script reads the command string into simple commands and
groups, then judges them. The change stays inside the reader's list-continuation
state and the docstrings that describe it. The test module drives each copy as a
separate process through a JSON payload on standard input. No dependency
direction changes.

## Shared Components
None. The feature is a single task, so no component built by one task is
consumed by another.

## Conventions
- The two guard copies (`em-workflow/scripts/` and `em-review/scripts/`) change
  in the same commit and stay byte-identical (FR4, `.claude/rules/hook-tests.md`).
- Case-table rows have three fields — expected verdict (`deny` or `silent`),
  a Japanese label in the style of the neighbouring rows, and the command — and
  every command in the table is unique.
- The repository bumps plugin versions on push (exempt repository); no plan in
  this feature instructs a version change.

## Cross-task Design Decisions

### D1: One task for the parser change and its test rows
- **Decision**: the parser change in both copies, the docstring updates and the
  new case-table rows are one task.
- **Rationale**: tasks run in parallel in separate worktrees. The new deny rows
  fail until the parser change exists, so a test-only task could never satisfy
  "all tests pass = task done", and FR4 requires both copies to change in the
  same commit.
- **Affected tasks**: task0001.

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| The new clearing ends the continuation at a blank line, a comment-only line, a heredoc body or a `)` with no redirection, and an existing silent row turns into a deny | Low | Medium (false deny of a command the shell never runs) | Silent rows TS7, TS8, TS14, TS15 and the full case table (NFR4, THREAT-MODEL.md TM-2) |
| A docstring rewrite removes a sentence a documentation test pins | Medium | Low | Leave module docstring step 9 and the checkpoint sentences as they are; keep the case-mark terms in the `_close_paren` docstring; run the documentation tests (NFR5) |
| The two copies diverge | Low | High (one plugin keeps the fail-open) | Byte-identity test (FR4) |
| Syntax-error forms such as `&& ;` now deny when an undecidable line follows | Low | Low | Accepted by SPEC.md AS1; no rows required |

## Open Questions
None.
