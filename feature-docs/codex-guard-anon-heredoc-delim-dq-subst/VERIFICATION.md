# Verification Document: codex-guard-anon-heredoc-delim-dq-subst

## Overview
**Feature**: codex-guard-anon-heredoc-delim-dq-subst / **SPEC.md**: `feature-docs/codex-guard-anon-heredoc-delim-dq-subst/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/codex-guard-anon-heredoc-delim-dq-subst/IMPLEMENTATION.md`

Scenario ID mapping:

- TS-1 to TS-7 are SPEC.md's TS1 to TS7, in the same order.
- TS-3 and TS-6 also carry the SPEC.md Edge Cases that concern them.
- TS-8 is SPEC.md's Integration Tests (SPEC.md AC-6).
- TS-9 is the change-set check for NFR4.

The test file also contains labels such as TS-10 and TS-17 that belong to
earlier features. They are not scenario IDs of this document. The scale
test is referred to by its method name.

Multi-line inputs follow the task plan's convention: one command string,
zsh -c followed by the lines joined with newlines and shell-quoted as one
argument. Every verdict below must hold for both guard copies.

## Build Verification
- Command: none. `build_command` is empty, because the guard is a Python script that runs directly.
- Expected: not applicable.

## Test Verification
- Command (project, from workflow.yaml): `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests`, run at the repository root.
- Command (feature-focused): `python3 -m unittest tests.test_codex_hook_interactive_guard`, run at the repository root.
- Expected: exit code 0 for both.
- Coverage target: not applicable. No coverage tooling is configured, so coverage is scenario-based: every scenario below maps to at least one test or check.

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Miss-side reproduction. Lines: `function { :; } << foo("$(echo "x")")`, `foo("$(echo "x")")`, `foo($(echo "x"))`, `python3 -i` | deny | Unit (CASES) |
| TS-2 | False-deny-side reproduction. Lines: `function { :; } << foo("$(echo "a")")`, `foo($(echo a))`, `python3 -i`, `foo($(echo "a"))` | silent | Unit (CASES) |
| TS-3 | Undecidable inside a delimiter range. (a) A double-quoted substitution whose skip ends beyond the range end: first line `function { :; } << foo("$(echo ")")")`, then a body, then `python3 -i` after the body. (b) A quoted unit that does not close before the range end. (c) A double-quoted substitution that `_skip_substitution` itself cannot read, such as an unclosed substitution. | silent (undecidable), for each of (a) to (c) | Unit (CASES) |
| TS-4 | `$(( ))` inside double quotes is kept verbatim. Lines: `function { :; } << foo("$((1+2))")`, `foo($((1+2)))`, `python3 -i` | deny | Unit (CASES) |
| TS-5 | A nested substitution with inner quotes inside double quotes is kept verbatim. Lines: `function { :; } << foo("$(a "$(b "c")")")`, `foo($(a "$(b "c")"))`, `python3 -i` | deny | Unit (CASES) |
| TS-6 | Word-reader distinctions are kept. (a) `python3 '' -i` and `python3 "" -i`: new rows, which already return silent on the base revision. (b) The existing line-continuation row: `python3`, backslash-newline, `-i`. (c) A backslash at the very end of the input. | (a) silent; (b) deny; (c) silent (undecidable) | Unit (CASES) |
| TS-7 | Pre-existing rows are unchanged: the delimiter-range rows; the row where `$'` inside double quotes is not a trigger; the row where quotes inside a `$( )` outside quotes are not removed | each keeps its current verdict | Unit (CASES) |
| TS-8 | The full guard suite: all CASES, TestCopies, TestNoRecursion, the scale test (test_delimiter_ranges_at_scale_are_read_in_time_and_the_launch_after_them_is_denied), TestGuardDocumentation and TestStaticConstraints | all pass | Integration |
| TS-9 | The change set, as the diff from `workflow.implement.base_commit` to the integration branch | lists none of `em-workflow/.claude-plugin/plugin.json`, `em-review/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` | Integration (diff check) |

## Code Quality Verification
- Format: none configured (`format_command` is empty). Static analysis: none configured.
- Copy identity: TestCopies (TS-8).

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | The miss-side reproduction returns deny | TS-1 |
| AC-2 | The false-deny-side reproduction returns silent | TS-2 |
| AC-3 | Both reproductions are in `CASES` in the (expected verdict, label, command) form | Inspect `CASES`, then run TS-1 and TS-2 |
| AC-4 | A substitution skip beyond the range end returns silent (undecidable) | TS-3 (a) |
| AC-5 | Both sites call the shared reader from their three branches (backslash, single quote, double quote): the parse body and `_remove_range_quotes`. Neither site keeps its own loop for reading inside double quotes. | Manual code inspection (see Manual Testing) |
| AC-6 | `python3 -m unittest tests.test_codex_hook_interactive_guard` passes in full | TS-8 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2, TS-3; manual inspection (AC-5) |
| FR2 | task0001 | TS-1, TS-2, TS-6, TS-7; manual inspection (AC-5) |
| FR3 | task0001 | TS-1, TS-2, TS-4, TS-5 |
| FR4 | task0001 | TS-3 |
| FR5 | task0001 | TS-6, TS-7 |
| FR6 | task0001 | TS-8 (TestCopies) |
| FR7 | task0001 | TS-8 (TestGuardDocumentation) |
| FR8 | task0001 | TS-7 |
| NFR1 | task0001 | TS-8 (scale test) |
| NFR2 | task0001 | TS-8 (TestNoRecursion) |
| NFR3 | task0001 | TS-8 (TestStaticConstraints) |
| NFR4 | task0001 | TS-9 |

## Manual Testing (E2E Not Possible)
- [ ] Code inspection (SPEC.md AC-5; FR1, FR2; TM-4), in both copies:
  - The parse body's backslash, single-quote and double-quote branches call the one shared quoted-unit reader, with the end of the input as the limit.
  - The same three branches of `_remove_range_quotes` call it with the range end as the limit.
  - Neither site keeps its own loop for reading inside double quotes.
  - `_skip_substitution` does not call the shared reader or either reader.

## Performance / Security Verification (if applicable)
- NFR1: the scale test (test_delimiter_ranges_at_scale_are_read_in_time_and_the_launch_after_them_is_denied) passes within its own time bound (TS-8).
- TM-1: the shared reader keeps double-quoted substitutions verbatim in delimiter ranges. Check: TS-1, TS-2, TS-4 and TS-5 return their stated verdicts on both copies.
- TM-2: an overrun skip, a quoted unit that does not close before its limit, and `_skip_substitution`'s own undecidable result each make the verdict undecidable. Check: TS-3 (a) to (c) return silent on both copies.
- TM-3: the word reader's distinctions are kept (dynamic-ness, empty quote starts a word, backslash-newline adds nothing, trailing backslash undecidable). Check: TS-6 and TS-7 return their stated verdicts on both copies.
- TM-4: no recursion or call cycle, and reading stays linear. Check: TestNoRecursion and the scale test pass (TS-8), and the manual inspection confirms that `_skip_substitution` does not call back.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Unit (CASES): TS-1 to TS-7 | 7 | 7 | 0 | 0 |
| Integration: TS-8, TS-9 | 2 | 2 | 0 | 0 |
| Code inspection: SPEC.md AC-5 | 1 | 0 | 0 | 1 |
| Performance: NFR1 | 1 | 1 | 0 | 0 |
| Security: TM-1 to TM-4 | 4 | 4 | 0 | 0 |
| Total | 15 | 14 | 0 | 1 |
