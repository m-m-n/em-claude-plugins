# Threat Model: codex-guard-escaped-hash-brace-case-heredoc

## Verdict
threats-identified

## Rationale

### Inputs inspected

- SPEC.md and REQUIREMENTS.md (tier `full`, design step skipped).
- The substitution reader `_skip_substitution` in both copies of `codex-hook-interactive-guard.py`.
- `tests/test_codex_hook_interactive_guard.py`.

### What crosses the boundary

The hook reads a PreToolUse(Bash) JSON object from standard input. Its `tool_input.command` is written by an agent whose output can be shaped by untrusted text, such as repository content, tool output or a task description. The guard turns that string into one decision: deny an interactive launch, or stay silent.

The feature changes how the reader finds the close of a command substitution. A misread close therefore lets a launch after the substitution go unjudged. Such a launch then waits for input that never comes and stalls an unattended run (REQUIREMENTS.md 1.1 and 2.3).

### Depth and task consistency

- Both tasks declare `input-handling`, so the boundary is analysed at deep depth.
- Both tasks' guard files are the boundary files below.
- The test module is declared by both tasks but implements no part of the boundary. It carries the verification only.

### Categories with no row

- **Spoofing, Repudiation, Elevation of privilege**: no row. The guard authenticates no party, records no actions, and grants no privilege.
- **Information disclosure**: no row. The deny reason does not echo the command, and this feature does not change that.

## Trust Boundaries

### TB-1: Agent-authored command string into the guard's substitution reader
Crossing: the `tool_input.command` string of a PreToolUse(Bash) hook input, authored by an agent and possibly shaped by untrusted text, read by the guard process to decide deny or silent.
Boundary files: `em-workflow/scripts/codex-hook-interactive-guard.py`, `em-review/scripts/codex-hook-interactive-guard.py`
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Denial of service | A substitution holding a `#` after an escaped blank or separator, or after a continuation pair that follows a word character, is read as having a comment there. With no newline before the input ends, the reading is undecidable, so an interactive launch after the substitution is not denied and the unattended run stalls (FR1, NFR3) | TM-1 | The comment-start decision looks past continuation pairs and treats an escaped previous character as a word character. It applies at every site of the substitution reader where a comment can start, in both copies | task0001 AC-1, AC-2, AC-3, AC-4 | VERIFICATION.md Performance / Security Verification, TM-1 |
| Denial of service | A substitution holding zsh's brace-form `case x { ... }` is undecidable ("case without in"), so a launch after it is not denied (FR2, FR3) | TM-2 | The brace form is opened by a standalone `{` after the subject. It is read to its close: a `}` or `esac` at a pattern position, or a `}` at a command position of an item body at depth 0. The list that holds it then continues at a command position | task0002 AC-1, AC-2 | VERIFICATION.md Performance / Security Verification, TM-2 |
| Denial of service | The new brace reading can misplace the close. It may take a `}` of a group in an item body, a quoted or escaped brace, a `}` at an argument position, or a nested statement's closing word as the statement's close, or keep stale state after the rule-9 re-read. The reader then ends the substitution at the wrong place: a launch after it is taken as part of the substitution and not denied, or the substitution's contents are judged against NFR3 (FR3, FR4, FR5, NFR3) | TM-3 | Depth counts only standalone, unquoted braces at command positions of the item body list itself. Nested case statements keep their own state. The re-read restores the brace state to its value at the `((`. Forms whose close is uncertain stay undecidable and are never guessed: a terminator while a group is open, an `esac` at a command position of a brace-form body, a heredoc in any case statement, and an unclosed statement | task0002 AC-2, AC-3, AC-4, AC-5 | VERIFICATION.md Performance / Security Verification, TM-3 |
| Denial of service | A crafted long command makes the added look at the characters before a `#`, or the added per-statement state, cost more than linear time. Examples are long runs of backslashes, of continuation pairs or of `#`, or deeply nested brace-form statements and `{ }` groups. The hook then overruns its time and gives no answer (NFR1) | TM-4 | The `#` decision costs a constant amount of work per character over the whole skip. The brace-form state is of constant size per open statement. The existing re-read budget is unchanged | task0001 AC-7, task0002 AC-7 | VERIFICATION.md Performance / Security Verification, TM-4 |
