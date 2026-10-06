# Implementation Plan: destructive-guard-lexer-round2-residuals

## Overview
Fix the four review round 2 residuals in the unified lexer of
`em-workflow/hooks/destructive-guard.py` (command position after a closer
`{` and after `time --`; array subscripts of assignment words; whole-word
here-document delimiters; linear re-reading for non-adjacent `))` closes),
as four tasks that run in parallel and share three files.

## Technology Stack
- **Language**: Python 3, standard library only (NFR5).
- **New dependencies**: none. `project.license` is `none`; no license to
  record.
- **Test entry points**: `python3 em-workflow/hooks/tests/run-destructive-guard.py`
  (case table run through the hook's stdin/stdout contract) and
  `python3 -m unittest tests.test_destructive_guard_lexer_agreement`
  (lexer fixed expectations, stage agreement, linearity, module contract).
  The project suite `python3 -m unittest discover -s tests` also holds the
  other destructive-guard test modules.

## Layer Structure
- **Lexer layer** (`lex_shell()` and its single pass): reads the command
  text once and produces the lexical map (regions, here-document operators,
  single-quote candidates, unopened openers, tail start, work, rounds).
  Every change in this feature lives here.
- **Consumers** (here-document stripping, structure scan, statement table,
  masked view): consume the lexical map only. They change only where a task
  adds a region kind that the masked view must hide (task0002).
- **Decision layer**: turns statements into allow / ask / deny. Unchanged.
- Dependency direction stays consumers → lexer; the lexer depends on
  nothing above it.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| `lex_shell()` and its lexical map | One forward reading of a command text into the lexical map | Pre: any text, mode `shell` or `heredoc-body`. Post: the same (text, mode, bodies) always gives an identical map (NFR4); the map's fields keep their current meaning; the work counted is at most `LEX_WORK_FACTOR` × text length + 1024, otherwise the budget-exceeded condition is raised and the hook answers ask (deny under `CLAUDE_BATCH`), never allow (NFR1, NFR3); the lexer reads no file and evaluates nothing (NFR5). | task0001, task0002, task0003, task0004 |
| Word-level grammar state of a shell-rule frame (command position, after-closer position, `time` option marker, keyword marker), advanced once per word | Decides where reserved words and a bare `((` are recognized | Only task0001 changes which words set or keep the command position / after-closer position: `{` joins the after-closer reserved word set (name unchanged), and `--` directly after `time` or `time -p` keeps the command position and ends `time`'s options. task0002 may add its own tracking of assignment-acceptable positions, but it adds no transition of the command / after-closer state: for every input, where reserved words and `((` are recognized is exactly what base plus task0001 define. | task0001, task0002 |
| Settle channel for unclosed openers (P4) | An opener that never closes is not a region; from the earliest such opener on, no `<<` operator and no comment are read | Post: a pass reports every opener of a settle-eligible kind that it finds cannot close (at the latest, still open at the end of the text), all of them in one pass; the next reading treats every reported opener as literal and reports the earliest as the tail start. task0004 keeps this channel's semantics and its settle-all-at-once behaviour unchanged. task0002 may add its subscript opener to the settle-eligible kinds and must treat a settled subscript opener as literal text. | task0002, task0004 |
| Two-parentheses re-reading (non-adjacent close) | A `((` / `$((` whose first depth-1 close is a lone `)` is read as two parentheses | Owned by task0004. Post: the final map equals the reading in which exactly the openers that close without an adjacent `))` are read as two parentheses (today's whole-text-restart result); total work stays within the linear bound. No other task changes the arithmetic frame's close handling or the re-reading loop in `lex_shell()`. | task0004 (task0001, task0002, task0003 rely on the unchanged meaning) |
| Here-document operator reading (operator registration, delimiter value, quoted flag, close-line index) | Which `<<` / `<<-` is a real operator, its delimiter, and where its body ends | Owned by task0003. Post: the delimiter recorded on a here-document entry is the quote-removed delimiter word; `quoted` is true exactly when the word holds a quote character; an operator whose delimiter word cannot be read takes no body. task0002 keeps a `<<` inside a subscript from registering only by consuming the subscript before the operator reader sees it, without changing the operator reader. task0004 keeps the pending-body / line-start trigger semantics intact across its re-reading. | task0002, task0003, task0004 |
| Case table append protocol (`em-workflow/hooks/tests/destructive-guard-cases.json`) | Holds the regression cases the runner checks | Pre: the 627 entries present at the feature base (indexes 0-626). Post: each task appends its own contiguous block after the last entry; no entry is inserted before, edited, removed or reordered (FR8); every new label begins with the finding's stable_id followed by `round2-residuals` and a requirement tag (e.g. `FR1.1`); the commit that appends a task's cases precedes every commit of that task that changes the hook (FR6). Tests locate new cases by label and command text, never by an absolute index of 627 or above, because the order of the four blocks depends on merge order. | task0001, task0002, task0003, task0004 |
| Lexer agreement test layout (`tests/test_destructive_guard_lexer_agreement.py`) | Where each task adds its tests, so that parallel edits land in distinct places | task0001: extends `COMMAND_POSITION_FORMS` and `COMMAND_POSITION_EXTRA_REGIONS`, adds its two-mode verdict test to `TestFixedVerdicts`, and adds the placement test to `TestModuleContract`. task0002: a new test class placed directly after `TestSubstitutionPolicies`. task0003: a new test class placed directly after `TestHeredocBodies`. task0004: extends `TestUnclosedOpeners` / `TestReworkLinearity` and adds a new test class placed directly after `TestReworkLinearity`. Constants a task needs are defined next to its own class, except task0001's edits to the form lists at the top. | task0001, task0002, task0003, task0004 |

## Conventions
- **Fail-safe direction (NFR6, SPEC A3)**: follow bash 5.3. Where the
  lexer cannot match bash, choose the reading that keeps the following
  lines inspected. Widening a reading is safe only when it can remove a
  here-document operator and cannot open a quote or region that swallows
  later lines.
- **bash confirmation**: when a task confirms a form on bash 5.3, the
  destructive command is replaced by a harmless `echo` in the probe; no
  destructive command is ever executed. When bash 5.3 is not available, the
  form is not added as a case and the task report lists it as unconfirmed.
- **Existing cases are fixed points**: if a change flips the verdict of any
  pre-existing case, the case is not edited; the task stops changing that
  behaviour and reports the conflict as a plan deviation.
- **Commit order after parent-side adoption**: when a conflict forces
  re-implementation on the parent's version, re-append the task's case
  block in a commit before the commit that re-applies the hook change.
- **Test runs**: every hook change is followed by both test entry points in
  the same change (`.claude/rules/hook-tests.md`), and the project suite
  passes before the task merges.
- **File scope**: no task touches a file outside its declared list.

## Cross-task Design Decisions

### D1: Split by finding into four parallel tasks
FR1 and FR2 (both command-position reading) form task0001; FR3 (subscript)
is task0002; FR4 (delimiter word) is task0003; FR5 (re-reading cost) is
task0004. Each task appends only its own cases, so each task branch has a
fully green suite at its end while the cases still precede the fix in that
branch's history (FR6, AC4). Affected: all tasks.

### D2: Ownership of hook code regions
The Shared Components rows above assign each part of the lexer to exactly
one task (grammar-state transitions: task0001; subscript reading:
task0002; operator reading and close-line index: task0003; non-adjacent
re-reading and the `lex_shell()` loop: task0004; settle channel: unchanged
except for task0002 adding a kind). This keeps textual merge conflicts to
the shared tail of the case table and makes semantic overlap explicit.
Affected: all tasks.

### D3: Order-agnostic placement check
task0001 owns one placement test: no label at an index below 627 carries
any of the four round 2 stable_ids (453963d025537b11, 681fab61e1d9ff2c,
9381769d7116fab2, 29bbf9032dd762a0), and the existing position pins for
indexes 574-626 keep passing. Each task additionally checks its own cases
by label and command text. The check passes whichever subset of the four
blocks is present, so it holds on every task branch and after every merge
order. Affected: all tasks (task0001 implements the shared test).

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| All four tasks append at the tail of the case table, so later merges conflict there | High | Low | Parent-side adoption, then re-append the task's own block (commit order convention above); tests identify cases by label, not index |
| Overlapping edits inside the single lexer pass function conflict textually | Medium | Medium | Region ownership (D2); re-implement on the parent's version per the adoption protocol |
| task0004's re-reading interacts with task0002's subscript region or task0003's operator reading (e.g. a pending here-document across a re-read span) | Medium | High | task0004's map-equivalence test runs over every case-table command, so after merge it covers the other tasks' cases; the verify phase runs both suites on the integrated tree |
| A wider reading flips the verdict of an existing case | Low | High | Existing cases are fixed points (Conventions); stop and report |
| bash 5.3 is not available to confirm an edge form | Low | Low | The form is not added and is reported as unconfirmed; the fail-safe direction still governs the code |

## Open Questions
- None.
