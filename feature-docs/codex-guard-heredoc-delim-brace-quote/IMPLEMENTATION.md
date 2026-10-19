# Implementation Plan: codex-guard-heredoc-delim-brace-quote

## Overview

codex-hook-interactive-guard registers a `<<` / `<<-` delimiter that contains `${ ... }` the way zsh does (zsh-equivalent close search plus the `_remove_range_quotes` quote-removal rule), and sends delimiter forms whose zsh reading it cannot reproduce to the existing undecidable path. The whole change is carried by one task, task0001.

## Technology Stack

- **Language**: Python 3, standard library only (NFR5)
- **Tests**: standard-library unittest, table-driven through the existing CASES table of the guard's test module
- **New dependencies**: none (no license to record; `project.license` is `none`)

## Layer Structure

The hook's existing structure is kept; no new layer and no new dependency direction.

1. **Command-text reading** — reads words: quoted units, `$`-constructs (`_dollar`), heredoc operators. The change is confined to this layer, at the delimiter position only.
2. **Heredoc tracking** — registers the delimiter, skips the body, applies `<<-` leading-tab stripping. Receives the delimiter string from layer 1 unchanged in shape.
3. **Judgment with checkpoints** — the existing `_Undecidable` rule: judge commands up to the last checkpoint, emit nothing otherwise. Layer 1 reaches it only through the existing undecidable signal.

## Shared Components

None. The feature has a single task, so no component is built by one task and used by another. The existing internals task0001 reuses (`_remove_range_quotes`, `_dollar`, `_Undecidable`) are described in its task plan.

## Conventions

- **Mirrored copies**: the em-workflow and em-review copies of the guard are edited together and stay byte-identical (NFR1).
- **Regression table**: new cases are CASES rows of the form (expected verdict, label, command), verdict `deny` or `silent`; existing rows are never removed and their expected verdicts never change (NFR4).
- **Error policy**: a delimiter form whose zsh reading cannot be reproduced goes to the existing undecidable path. No new outcome kind, no new output shape (FR6).
- **Change set**: the two guard copies and the test module only; plugin manifests and the marketplace file are outside the change set.

## Cross-task Design Decisions

### D1: One task

The change is one reading path in one region of the guard, duplicated byte-for-byte in two copies, plus regression rows that only pass once that reading changes. Putting the rows in a separate task would leave a task whose own tests cannot pass inside its worktree; splitting the `${ ... }` handling (FR1 to FR3) from the outside-`${ ... }` handling (FR4) would put two parallel edits on the same delimiter-reading path and its position flag. Affected task: task0001.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| The delimiter-position close search or quote removal classifies quotes differently from `_remove_range_quotes`, so the registered delimiter drifts from zsh | Medium | High (missed launch) | Share the quote-state handling with `_remove_range_quotes` rather than writing an independent copy; TS1 to TS17 and TS34 pin the outputs |
| The new reading leaks into non-delimiter positions (`<<<`, `<`, ordinary words) | Medium | High (false deny halts unattended runs) | Select the new reading only for the `<<` / `<<-` operand; TS29 to TS33 and every existing CASES row |
| The close search becomes superlinear on nested constructs | Low | Medium (hook stall) | Single forward scan, nested `$( ... )` skipped once; existing length-cap and timing tests (TS38) |
| A docstring edit breaks the docstring marker tests | Medium | Low | Keep every marker string; place new `-> no output` statements inside the checkpoint-rule section (TS39) |
| The two copies diverge | Low | Medium | Byte comparison (TS37) |

## Open Questions

- [ ] None
