# Verification Document: codex-guard-case-in-substitution

## Overview
**Feature**: codex-guard-case-in-substitution / **SPEC.md**: `feature-docs/codex-guard-case-in-substitution/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/codex-guard-case-in-substitution/IMPLEMENTATION.md`

IMPLEMENTATION.md D1 supersedes SPEC.md FR3's "right after an item terminator": that position is verified as a pattern position.

## Build Verification
- Command: none (`project.components.main.build_command` is empty; the hook is a Python script with no build step)
- Expected: not applicable

## Test Verification
- Command (project test command, from the repository root): `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests`
- Focused command for this hook (from the repository root): `python3 -m unittest tests.test_codex_hook_interactive_guard`
- Expected: exit code 0, no failures or errors
- Coverage target: not measured (no coverage tool is configured); every scenario below is an explicit test, run against both hook copies

### Test Scenarios from SPEC.md
Scenarios TS18-TS21 are added by the plan (not in SPEC.md) to verify FR9, NFR2, NFR4 and IMPLEMENTATION.md D3.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS1 | FR5 (a): `zsh -c` followed by the shell-quoted three-line inner text (anonymous-function heredoc whose delimiter range holds `"$(case x in x) echo foo;; esac)"`, the closing line, then `python3 -i`) | deny on both copies (the delimiter is registered as `foo($(case x in x) echo foo;; esac))`, line 2 ends the body, line 3 is judged) | Unit (CASES row) |
| TS2 | FR5 (b): `zsh -c` followed by the shell-quoted `echo "$(case x in x) :;; esac)"; python3 -i` | deny on both copies | Unit (CASES row) |
| TS3 | Pattern with the optional leading `(`: `echo "$(case x in (x) :;; esac)"; python3 -i` | deny on both copies | Unit (CASES row) |
| TS4 | Alternatives and zsh terminators inside `zsh -c`: `echo "$(case x in a\|b) :;& x) :;\| *) :;; esac)"; python3 -i` | deny on both copies | Unit (CASES row) |
| TS5 | bash terminator inside `bash -c`: `echo "$(case x in x) :;;& *) :;; esac)"; python3 -i` | deny on both copies | Unit (CASES row) |
| TS6 | Last item closed by `esac` without a terminator: `echo "$(case x in x) :; esac)"; python3 -i`, and the same with a newline instead of `;` (two rows) | deny on both copies, both rows | Unit (CASES rows) |
| TS7 | Nested statement right after the pattern's `)`: `echo "$(case x in x) case y in y) :;; esac;; esac)"; python3 -i` | deny on both copies | Unit (CASES row) |
| TS8 | Quoted `)` in a pattern and a subshell in the body: `echo "$(case x in ')') (:);; x) :;; esac)"; python3 -i` | deny on both copies | Unit (CASES row) |
| TS9 | Statement inside a nested substitution in a body: `echo "$(case x in x) echo "$(case y in y) :;; esac)";; esac)"; python3 -i` | deny on both copies | Unit (CASES row) |
| TS10 | An argument `esac` and a comment `esac` close nothing: `echo "$(case x in x) echo esac;; esac)"; python3 -i`, and a body holding `: # esac` and a newline (two rows) | deny on both copies, both rows | Unit (CASES rows) |
| TS11 | Contents of the substitution are not judged: `echo "$(case x in x) python3 -i;; esac)"` | silent on both copies | Unit (CASES row) |
| TS12 | No closing `esac`: `echo "$(case x in x) :;;"; python3 -i` | silent on both copies | Unit (CASES row) |
| TS13 | Heredoc in an item body: first line `echo "$(case x in x) cat <<E`, then a body line, `E`, and `;; esac)"; python3 -i` | silent on both copies | Unit (CASES row) |
| TS14 | zsh brace form: `echo "$(case x { x) :;; })"; python3 -i` | silent on both copies | Unit (CASES row) |
| TS15 | TS1 shape with several items in the range: the substitution in the range is `$(case x in a) :;; x) echo foo;; esac)` | deny on both copies | Unit (CASES row) |
| TS16 | Many items and deep nesting (each nested statement opened as the first word of the enclosing body) inside a double-quoted substitution, followed by `; python3 -i`; item count and depth each at least the deep-input class's depth | deny on both copies within the deep-input class's timeout | Performance (test method) |
| TS17 | Existing suite: every existing CASES row (the backquote rows holding `case` included), `TestNoRecursion`, `TestSharedQuotedUnitReader`, `TestStaticConstraints`, `TestGuardDocumentation`, `TestCopies` | pass unchanged | Regression (existing tests) |
| TS18 | (Plan-added) Documentation test: `_skip_substitution`'s docstring no longer holds "a heredoc or a `case` inside it", states that case statements are read and names each undecidable form; the module docstring still holds "A chunk that is not closed, or whose close cannot be located with certainty -> no output" | pass on both copies | Unit (documentation test) |
| TS19 | (Plan-added) Call-structure test: no `_Parser` method reachable from `_skip_substitution` through `self.` calls is `_skip_substitution` again, `_read_quoted_unit`, `parse` or `_remove_range_quotes` | pass on both copies | Unit (structural test) |
| TS20 | (Plan-added) Version files untouched: the feature's diff against the base revision lists no `plugin.json` and no `.claude-plugin/marketplace.json` | no such path in the diff | Diff check |
| TS21 | (Plan-added, D3) Forms zsh accepts are read, not made undecidable, each inside `zsh -c` followed by `; python3 -i` after the substitution (five rows): an empty leading alternative `case x in \|x) :;; esac`; the same after the optional parenthesis `case x in (\|x) :;; esac`; parentheses in the subject `case x(a\|b) in *) :;; esac`; a numeric range as the subject `case <1-2> in *) :;; esac`; a process substitution as the subject `case <(:) in *) :;; esac` — each statement inside `echo "$( ... )"` | deny on both copies, all five rows | Unit (CASES rows) |

## Code Quality Verification
- Format: none configured / Static analysis: none configured. `TestStaticConstraints` (standard library only; no file writes, network or child processes) runs as part of the test command.

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | FR5 (a) reproduction is denied on both copies | TS1 row passes |
| AC-2 | FR5 (b) reproduction is denied on both copies | TS2 row passes |
| AC-3 | The AC-1 and AC-2 inputs are `CASES` rows in the form (expected verdict, label, command) | Inspect `CASES`; TS1 and TS2 rows present |
| AC-4 | TS3-TS15 rows are in `CASES` and give the expected verdict on both copies | TS3-TS15 rows pass |
| AC-5 | The two copies are byte-identical | `TestCopies.test_the_two_copies_are_byte_identical` passes |
| AC-6 | The focused command and the project test command both pass from the repository root | Run both commands; exit code 0 (TS17 included) |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS1-TS6, TS10, TS15, TS21 |
| FR2 | task0001 | TS3, TS8, TS21 |
| FR3 | task0001 | TS7-TS10 (with "right after an item terminator" read per IMPLEMENTATION.md D1) |
| FR4 | task0001 | TS12-TS14 |
| FR5 | task0001 | TS1, TS2, TS15 |
| FR6 | task0001 | TS11, TS17 |
| FR7 | task0001 | TS1-TS15 and TS21 present as CASES rows; `TestCasesTable` (uniqueness, both copies) in the test command |
| FR8 | task0001 | TS17 (`TestCopies`) |
| FR9 | task0001 | TS18 |
| NFR1 | task0001 | TS16 |
| NFR2 | task0001 | TS17, TS19 |
| NFR3 | task0001 | TS17 (`TestStaticConstraints`) |
| NFR4 | task0001 | TS20 |

## Manual Testing (E2E Not Possible)
- [ ] TS20: list the files changed between the feature's base revision and the integration branch head; confirm that no `plugin.json` and no `.claude-plugin/marketplace.json` appears.
- [ ] Optional confirmation of FR5: pipe the PreToolUse JSON for TS1 and TS2 into each copy and observe one deny object on standard output (the CASES rows automate the same check).

## Performance / Security Verification
- NFR1: TS16, item count and nesting depth each at least the deep-input class's depth; deny within that class's timeout on both copies.
- TM-1: the case statement is read so the launch after the substitution is judged, including the forms zsh accepts (D3) — checked by the deny rows TS1-TS10, TS15 and TS21 on both copies.
- TM-2: the substitution closes only after its case statements close, its contents are never judged, and unlocatable forms stay undecidable — checked by the silent rows TS11-TS14 and by the deny rows TS8-TS10 (close found after a quoted `)`, a nested substitution, and an argument or comment `esac`).
- TM-3: linear reading on the explicit stack with no recursion or call cycle — checked by TS16, TS17 (`TestNoRecursion`) and TS19.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Behaviour scenarios (TS1-TS15, TS21; 22 CASES rows) | 16 | 16 | 0 | 0 |
| Performance (TS16) | 1 | 1 | 0 | 0 |
| Regression (TS17) | 1 | 1 | 0 | 0 |
| Documentation and call structure (TS18, TS19) | 2 | 2 | 0 | 0 |
| Diff check (TS20) | 1 | 0 | 0 | 1 |
| Success criteria (AC-1 to AC-6) | 6 | 6 | 0 | 0 |
| Security (TM-1 to TM-3) | 3 | 3 | 0 | 0 |
| Optional FR5 confirmation | 1 | 0 | 0 | 1 |
