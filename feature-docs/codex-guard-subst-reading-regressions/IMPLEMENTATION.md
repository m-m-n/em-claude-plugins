# Implementation Plan: codex-guard-subst-reading-regressions

## Overview
Remove the three fail-open regressions of the substitution reader `_skip_substitution` in codex-hook-interactive-guard, one task per defect (task0001: the zsh `for` word list; task0002: the empty `()` check; task0003: coproc and repeat by shell kind, with one re-read). All three tasks edit the same two byte-identical script copies and the same test module in parallel, so this document fixes which part of each file each task owns.

## Technology Stack
- **Language**: Python 3, standard library only (NFR3)
- **Tests**: unittest, `tests/test_codex_hook_interactive_guard.py`; the hook copies run as child processes, structure and documentation are checked on the syntax tree
- **New dependencies**: none (no license to record; `project.license` is `none`)

## Layer Structure
The guard is one module kept as two byte-identical copies: `em-workflow/scripts/codex-hook-interactive-guard.py` and `em-review/scripts/codex-hook-interactive-guard.py`.

| Layer | Members | Responsibility |
|---|---|---|
| Reader | `_Parser` (with `_skip_substitution`, `_read_command_word`, `_keyword_end`, `_empty_parens_end`), the module-level `parse` | Split one string into simple commands; on a string it cannot read to its end, raise `_Undecidable` carrying the commands settled up to the last checkpoint |
| Judgment | `_judge` and the option readers | Judge one simple command; hand back a literal shell `-c` string |
| Walk | `_scan`, `find_deny`, `main` | Walk nested strings with a work list; the first launch to deny decides |

Dependencies point from Walk to Judgment and from Walk to Reader only. Nothing reachable from `_skip_substitution` reaches `_skip_substitution` itself, `_read_quoted_unit`, `parse` or `_remove_range_quotes`, and no function calls itself (NFR2).

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| The two guard copies | The guard itself | Pre: byte-identical when a task starts. Post: byte-identical after every commit of every task (FR7, TestCopies); every edit lands in both files. | task0001, task0002, task0003 |
| Context stack of `_skip_substitution` | Nesting of the contexts inside one substitution chunk | Each stack entry has exactly one parallel `saved` entry holding the same four values as today (at command position, open `[[`, head state, whether the close gives the enclosing list a command position); no task adds or removes a value. A new context is a new stack character distinct from the existing ones (p, a, d, b, k, K, g and the case phases 1 to 8). Shell-dependent rules are parser-wide switches fixed when the parser is built, never per-entry state. `$((` keeps opening context a with its present reading. | task0001 (adds the word-list context), task0003 (reads the parser-wide switches at head words) |
| `_empty_parens_end(j)` | Decide the empty `()` of a function head | Pre: `j` is the index of a `(` read in a head state (after the first word of a simple command, after `function`, or after a function name). Post: the index just after the `)` when only spaces, tabs and continuation pairs (a backslash directly followed by a newline) lie between; otherwise the not-found value, including when the input ends first and when a backslash is followed by anything other than a newline. Raises nothing, keeps no state, calls no method; each character it skips is read at most once more by its caller. The word-list context never reaches it (no head state there). | task0002 (owner), task0001 (edits the `(` branch that calls it; the call stays as is) |
| CASES table | Row-driven verdicts run against both copies | Rows are (expected, label, command) with expected `deny` or `silent`; commands stay unique; pre-existing rows are neither removed nor changed (A4); each task puts its rows in its own commented block at the anchor listed under Conventions. | task0001, task0002, task0003 |
| `TestCaseStatementsInASubstitution` | Timing scenarios TS25 to TS27 | Each new method uses the class DEPTH and TIMEOUT and the class's every-copy-deny helper; each task adds one method at its anchor. | task0001, task0002, task0003 |
| Documentation-marker tests | Pin docstring sentences (`TestSubstitutionSkipDocumentation`, `TestGuardDocumentation`) | Every pinned marker and passage anchor stays verbatim in the docstrings. The only entries that may change are the loop and coproc head rule entries of RULE_MARKERS, changed by task0003 alone, in the same change as the docstring, and only where the sentence's meaning changes (FR8). | task0001, task0002, task0003 |

## Conventions

- **Both copies.** Every commit leaves the two script copies byte-identical. While working, run `python3 -m unittest tests.test_codex_hook_interactive_guard` (`.claude/rules/hook-tests.md`); before finishing, run the project's full test command.
- **CASES labels.** A new row's label starts with `置換読み` and the scenario ID (for example `置換読み TS5`), followed by a Japanese description. Commands follow SPEC.md notation: `<NL>` is a newline character, `\<NL>` a backslash followed by a newline; `wrap_bash(s)` and `wrap_zsh(s)` are the shell name, `-c`, a space and `s` shell-quoted the way the existing `zsh -c` rows quote it. Rows that wrap the earlier feature's commands (TS13, TS15, TS16, TS17) repeat that command text literally inside the wrapper.
- **Anchors.** Each task inserts at its own place, so the three parallel edits touch separate hunks.

| Task | CASES block (a comment line naming this feature and the scenarios, then the rows) | Timing method in `TestCaseStatementsInASubstitution` | Other test edits |
|---|---|---|---|
| task0001 | Directly after the row labelled `case 読み TS59`, before the comment that introduces the TS61 rows of codex-guard-case-reading-fixes | Directly after `test_ts60_loop_heads_nested_deeply_are_read_in_time` (the end of the class) | none |
| task0002 | Directly after the last row labelled `case 読み TS61`, before the comment that introduces the codex-guard-heredoc-delim-brace-quote rows | Directly after `test_ts42_function_heads_nested_deeply_are_read_in_time` | none |
| task0003 | At the end of CASES, after the last existing row and before the closing bracket | Directly after `test_ts22_a_long_run_of_argument_reserved_words_is_read_in_time` | TS32 at the end of `TestNestedReadLimit`; TS33 as a new test placed directly after `TestNestedParseErrorContainment`; the RULE_MARKERS entries named above |

- **Docstring ownership.** Each task edits only the text that describes its own rule and does not re-wrap neighbouring sentences; no task adds new documentation-marker tests (docstring content is checked by review).

| Task | Owned docstring and comment text |
|---|---|
| task0001 | `_skip_substitution`: the Contexts on the stack passage (context a becomes arithmetic only; the word-list context is added). The rule 6 sentence on `for name (words)` stays as written. |
| task0002 | `_empty_parens_end` docstring; in rule 6 of `_skip_substitution`, the sentences on what lies between the parentheses of an empty `()` and how emptiness is decided |
| task0003 | Comments on `HEAD_*` and `HEAD_AFTER_WORD`; in `_skip_substitution`, the coproc and repeat sentences of rule 6 and the head-state list of rule 7; the `_read_command_word`, `_Parser`, module-level `parse`, `_judge` and `_scan` docstrings; module docstring steps 7 and 9 |

- **Version.** The repository is exempt from manual version bumps (the bump workflow exists at its root). No task changes a version in any plugin's `plugin.json` or in `.claude-plugin/marketplace.json` (NFR4).
- **Constraints every task keeps.** Linear reading time with constant-size state (NFR1); no recursion and the call-reachability limits of the substitution skip (NFR2); standard library only, no file writes, no process or network use (NFR3); `find_deny(command)` keeps its one parameter and `_scan` keeps its one try around `parse` with the `_Undecidable` and `Exception` handlers (NFR5).
- **Earlier documents.** The earlier feature's SPEC is not edited (A5).

## Cross-task Design Decisions

### D1: One task per defect, with ownership of file regions
Each defect is a separate reading rule with its own reproduction, its own review finding and its own scenarios, so it is one task. All three tasks edit the same three files in parallel; the anchors and docstring ownership above keep their hunks apart, and a conflict that still occurs is resolved by the parent-side adoption protocol of `em-workflow/skills/worktree-task-workflow/SKILL.md`. Affected: task0001, task0002, task0003.

### D2: The word-list reading is documented in the Contexts on the stack passage
FR8 names the Contexts on the stack description of `a` as the text to change for FR1, and the rule 6 sentence on `for name (words)` stays accurate. Keeping task0001's text out of rule 6 leaves rule 6 to task0002 (the empty `()`) and task0003 (coproc and repeat), whose sentences sit next to the word-list sentence. Affected: task0001, task0003.

### D3: Scenario IDs beyond SPEC.md
VERIFICATION.md keeps SPEC.md's TS1 to TS27 and adds TS28 to TS33 (rows that pin clauses of FR1, FR2, FR3 and FR6 that no SPEC scenario isolates) and TS34 to TS40 (the integration checks of SPEC.md's Integration Tests and Success Criteria). Task plans and CASES labels use these IDs. Affected: task0001, task0002, task0003.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| The three parallel tasks conflict when merged: same function, same docstring, same tables, two copies each | Medium | Low | Anchors and docstring ownership (Conventions); parent-side adoption protocol; TestCopies after every merge |
| A merge leaves the two copies different | Low | High | TestCopies runs in every task and in verify (TS34) |
| A docstring edit drops a pinned marker or passage anchor | Medium | Low | The documentation-marker tests run in every task; only task0003 may touch RULE_MARKERS |
| Timing tests run slower under load, now that some top-level strings are read twice | Low | Low | The class TIMEOUT (60 s) and DEPTH stay; every reading is linear and a string is read at most twice |
| FR6 residual: when the re-read of an unknown-kind string reads to the end, its commands replace the first read's, so a string whose earlier `coproc WORD` or `repeat` substitution reads to the end under both readings with different extents, followed by a part only the first reading finds undecidable, can lose a launch the first read settled before its last checkpoint | Low (the string has to be shaped for it) | Medium (a missed detection: the REPL can stall an unattended run) | None beyond FR6 as specified; recorded in THREAT-MODEL.md Rationale and left for review to decide whether SPEC should change |

## Open Questions
- [ ] FR6 residual (Risk Assessment, last row): implemented as SPEC.md specifies; review decides whether a SPEC change is wanted.
