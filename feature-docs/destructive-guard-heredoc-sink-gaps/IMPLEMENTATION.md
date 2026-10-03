# Implementation Plan: destructive-guard-heredoc-sink-gaps

## Overview

Close the six review-round-2 deferrals in `em-workflow/hooks/destructive-guard.py`
(critical cdb8382d4bbb0b1d; high 73a1d7b31734dd22, 26ab9a3d83649eff,
18b99bd71e74c8dc, 511cd470522973d8, b8fd289ca7750a04) and bound every runner
evaluation at 10 seconds. Four tasks, split by responsibility area inside the
guard; all four share the guard file and the case file.

## Technology Stack

- **Language**: Python 3, standard library only (NFR2).
- **New dependencies**: none. No license entry is required (`project.license: none`).
- **Test suite**: the case table `em-workflow/hooks/tests/destructive-guard-cases.json`
  run by `em-workflow/hooks/tests/run-destructive-guard.py`; the repository-level
  `python3 -m unittest discover -s tests` must keep passing.

## Layer Structure

Logical processing stages of the guard, as named in SPEC.md's Component
Diagram. A later stage consumes earlier stages' results; no stage re-scans
the whole input once per item it handles (NFR3).

| Stage | Responsibility | Owning task(s) in this feature |
|-------|----------------|--------------------------------|
| S1 Lexical scan | quote / escape / comment state, statement separators (lex_segments()), structure scan (scan_structure()), single-quoted substitution scan (honor_single_quotes=False) | task0001 (single-quoted `$(` matching), task0002 (escaped quotes in scan_structure()), task0003 (operator context, cross-line state) |
| S2 Heredoc recognition and host statement | which `<<` / `<<-` are real operators, their bodies, and the host statement of each | task0002 (host statement), task0003 (real vs fake operators) |
| S3 Destination classification | per heredoc: shell sink / data / undetermined, via the host statement's command word and the words skipped before it | task0002 (own-operator check), task0004 (skipped-word sinks, override constructs) |
| S4 Fallback and verdict | existing fallback for undetermined bodies; final allow / ask / deny | unchanged by every task |

The test runner is outside these stages; task0001 owns its time limit.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| C1 Heredoc destination outcome and the existing fallback | Three outcomes per heredoc: shell sink (body scanned as commands), data (body not scanned), undetermined (body handed to the existing fallback, which rescans the body only when its chunk contains a SHELL_SINK word) | Pre: a heredoc has been recognized and a host statement selected. Post: FR2, FR6 and FR7 may only turn a would-be data result into undetermined. No task adds a fourth outcome, changes a shell-sink result, or changes the fallback's own behavior. | task0002, task0004 |
| C2 Shared lexical quoting rule | Single rule every quote-tracking code path in scan_structure() follows | Outside quotes, a backslash-escaped single or double quote is a literal character, never a quote start (FR3). Inside single quotes everything up to the next single quote is literal. Inside double quotes an escaped double quote is literal. A comment starts only at the start of a word outside quotes and ends at the end of the line. The quoting of a heredoc delimiter word is part of the operator, not a quote start. | task0002, task0003 |
| C3 Heredoc recognition result | Per recognized heredoc: operator position, delimiter, body line range | Shape and meaning stay as they are. task0003 changes only which operators appear in it (fake operators no longer do); task0002 reads the operator position for the own-operator check and does not change the shape. | task0002, task0003 |
| C4 Host statement passed to command-word resolution | The statement text from which S3 resolves the command word | task0002 postcondition: the statement is the lex_segments() statement that contains the heredoc's own operator, or the heredoc is already undetermined. task0004 precondition: receives a statement text and resolves its command word and skipped words without depending on how its boundaries were computed. | task0002, task0004 |
| C5 Single-quoted substitution matching (honor_single_quotes=False) | Finds the closing parenthesis of a `$(` inside single quotes | Post: for every input, the spans found are identical to the current implementation's (FR4); only the running time changes. No other task changes this matching. | task0001 (owner); task0002, task0003, task0004 rely on its results being unchanged |
| C6 `destructive-guard-cases.json` | Shared test data | Format: `[expected verdict, label, command]`. Append-only: no task edits, reorders or removes an existing entry, so the array before this feature stays an exact prefix and the case numbers cited in SPEC.md Edge Cases stay valid. Each task appends its own entries as one contiguous block at the end. A merge conflict in this file is resolved by keeping every entry from both sides; the result must be valid JSON that the runner loads. | task0001, task0002, task0003, task0004 |
| C7 `run-destructive-guard.py` interface | Runs every case and reports PASS / FAIL | Invocation stays the same: same command, same optional argument naming the guard file to test. task0001 adds the 10-second limit per evaluation and a timeout marker on FAIL lines; output for cases that finish within the limit is otherwise unchanged. | task0001 (owner); task0002, task0003, task0004 run it |

## Conventions

- **Tests first (FR8)**: each task appends its cases to C6 and runs the
  runner before changing the guard, and records in its test record which
  new cases FAIL and which PASS at that point.
- **Case labels**: a new label starts with the stable_id of the finding the
  case reproduces (for the SPEC TS-9 regression forms, 46923ffe262f20b1),
  then the REQUIREMENTS.md 11.1 form reference (for example `AC-1.3`) or the
  task plan's AC label for cases a task adds beyond FR8's list, then a short
  description in the same language as the surrounding labels.
- **Target placeholder**: REQUIREMENTS.md's `<対象>` is replaced with a target
  that the current guard denies when the destructive command is written as a
  plain standalone command, so the expected deny depends only on detection.
- **Fail-safe direction**: when a changed code path cannot decide, it moves
  the result toward undetermined (C1), never toward data. No change may stop
  scanning a body that is scanned today.
- **Static only (NFR1)**: no file system access, no evaluation of commands or
  substitutions, deterministic output for the same input.
- **Linear (NFR3)**: every added or changed pass is one forward pass over the
  input or over a bounded local structure; nothing restarts a scan from the
  beginning for each `$(`, quote, heredoc or word.
- **Change scope (NFR4)**: only the three files above change. hooks.json and
  the plugin version fields are not touched.
- **Done gate per task**: the runner and the repository test command both
  pass in the task worktree.

## Cross-task Design Decisions

### D1: Four tasks split by responsibility area

- Decision: task0001 = single-quoted `$(` matching + runner time limit
  (26ab9a3d83649eff); task0002 = host statement + escaped quotes
  (cdb8382d4bbb0b1d, 73a1d7b31734dd22); task0003 = fake heredoc operators
  (18b99bd71e74c8dc); task0004 = skipped-word sinks + command-name overrides
  (511cd470522973d8, b8fd289ca7750a04).
- Rationale: tasks run fully in parallel with no ordering. Each task changes
  a different part of the guard, so overlapping edits stay small. C2-C5 pin
  the points where two tasks touch the same data.
- Affected tasks: all.

### D2: Undetermined is the only fail-safe outcome

- Decision: FR2, FR6 and FR7 all use the existing undetermined outcome and the
  existing fallback (C1). No new outcome and no change to the fallback.
- Rationale: SPEC.md routes all three to the existing fallback. The fallback
  rescans only when a sink word is present, which keeps the existing allow
  cases (4, 36, 416-419, 468, 469) allow.
- Affected tasks: task0002, task0004.

### D3: One quoting rule for scan_structure()

- Decision: the escaped-quote change (task0002) and the cross-line quote and
  comment tracking (task0003) both follow C2.
- Rationale: both tasks edit quote handling in scan_structure(); one rule
  keeps the two edits consistent when merged.
- Affected tasks: task0002, task0003.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Merge conflicts: all four tasks edit the guard and append to the case file | High | Medium | Different stages per task (Layer Structure); C6 append-only, union resolution |
| A fix turns legitimate commands into ask, demoted to deny under batch | Medium | High | C1 (data to undetermined only); allow cases from FR8; every existing case kept and passing (FR9) |
| task0002 and task0003 apply different quote rules in scan_structure() | Medium | High | C2, D3 |
| The linear rewrite of single-quoted `$(` matching changes which spans are found | Low | High | C5; SPEC TS-9 regression cases; all existing cases pass |
| Timing checks are noisy | Medium | Low | 10-second limit is far above normal run time; scaling check uses a ratio threshold with margin |
| Residual risk A6 (override target path without a sink name) | Accepted | Medium | Recorded in SPEC.md Security Considerations; no mitigation in scope |

## Open Questions

- None.
