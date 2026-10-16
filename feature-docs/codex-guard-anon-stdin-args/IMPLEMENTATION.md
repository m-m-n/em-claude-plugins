# Implementation Plan: codex-guard-anon-stdin-args

## Overview

Parser fix in codex-hook-interactive-guard (two byte-identical copies) so a
zsh anonymous function's body is connected by a stdin redirect read in the
head or placed after an argument word containing `(`, plus regression cases.
The feature is one task (task0001).

## Technology Stack

- **Language**: Python 3, standard library only (NFR3)
- **Tests**: unittest — `tests/test_codex_hook_interactive_guard.py`
- **New dependencies**: none

## Layer Structure

The hook is a single module with three stages: hook input reading → zsh
command-string parser (`_Parser`, `_Group`) → verdict output. This feature
changes the parser stage and the docstrings only; input reading and the
verdict output shape are unchanged. The test module loads each copy by path
and runs the same case table against both.

## Shared Components

None. The feature has one task, so no component is built by one task and used
by another.

## Conventions

- **Byte-identical copies (FR5)**: `em-workflow/scripts/codex-hook-interactive-guard.py`
  and `em-review/scripts/codex-hook-interactive-guard.py` change in the same
  commit and stay byte-identical; `TestCopies` is the check.
- **Case table format**: each `CASES` entry is (expected verdict, label,
  command); the expected verdict is `deny` or `silent`; labels follow the
  file's existing style; the same table runs against both copies.
- **Pinned docstring wording (NFR4)**: every marker `TestGuardDocumentation`
  pins stays verbatim.
- **Hook constraints (NFR3)**: standard library only, no recursion, no file,
  network or subprocess access (`TestNoRecursion`, `TestStaticConstraints`).
- **Undecidable input**: stays silent, as today.
- **Existing cases (NFR1)**: no existing `CASES` entry is removed or has its
  expected verdict changed.
- **Plugin metadata (NFR5)**: no task edits `em-workflow/.claude-plugin/plugin.json`,
  `em-review/.claude-plugin/plugin.json` or `.claude-plugin/marketplace.json`.
- **Test commands**: `python3 -m unittest tests.test_codex_hook_interactive_guard`
  after each change to either copy (repository rule); the project test
  command `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests`
  before completion.

## Cross-task Design Decisions

### D1: One task

- **Decision**: FR1–FR6 and NFR1–NFR5 are implemented by task0001 alone.
- **Rationale**: FR1–FR4 change the same parser region and module docstring
  in both copies, FR5 requires both copies to change in the same commit, and
  FR6 adds to one case table. Separate parallel tasks would edit the same
  lines.
- **Affected tasks**: task0001

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| The widened silent reading lets an interactive launch through | Medium | High | THREAT-MODEL.md TM-2; deny cases TS7–TS9, TS14–TS18; all existing `CASES` verdicts kept |
| The argument range scan makes parsing quadratic | Medium | High | THREAT-MODEL.md TM-1; TS20 input-size test |
| A docstring edit drops a pinned marker | Low | Medium | `TestGuardDocumentation` (TS21) |
| The two copies drift apart | Low | Medium | `TestCopies` (TS22) |

## Open Questions

None.
