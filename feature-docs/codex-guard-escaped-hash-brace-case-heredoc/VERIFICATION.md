# Verification Document: codex-guard-escaped-hash-brace-case-heredoc

## Overview
**Feature**: codex-guard-escaped-hash-brace-case-heredoc / **SPEC.md**: `feature-docs/codex-guard-escaped-hash-brace-case-heredoc/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/codex-guard-escaped-hash-brace-case-heredoc/IMPLEMENTATION.md`

Notation in the commands below: shell text, where `\` is one backslash and `<newline>` stands for one newline character. In the CASES table the same commands are written as Python string literals.

## Build Verification
- Command: none (`project.components.main.build_command` is empty). The test run below executes both hook copies.
- Expected: not applicable

## Test Verification
- Command: `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests` (from workflow.yaml)
- Focused command: `python3 -m unittest tests.test_codex_hook_interactive_guard` (`.claude/rules/hook-tests.md`)
- Expected: exit code 0, no failures or errors
- Coverage target: not applicable (no coverage tool is configured). The criterion is that every scenario below passes on both copies.

### Test Scenarios from SPEC.md

Every hook scenario is a CASES row, or a test in the module, that runs against both copies. TS-28 and TS-29 are added here for NFR1 and NFR4, which SPEC.md's scenario list does not number. TS-30 to TS-36 are added by the review round 1 rework (task0003): a `#` at the start of the line after a comment that ends in a backslash.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Reproduction 2, escaped blank before `#` in a word-list process substitution: `zsh -c 'echo "$(for x (<(: \ #x)) { :; })"; python3 -i'` | deny | Unit |
| TS-2 | Reproduction 3, escaped blank before `#` in a plain substitution: `zsh -c 'echo "$(: \ #x)"; python3 -i'` | deny | Unit |
| TS-3 | Reproduction 4, brace-form case in a word-list process substitution: `zsh -c 'echo "$(for x (<(case x { x) :;; })) { :; })"; python3 -i'` | deny | Unit |
| TS-4 | The pre-existing brace-form row, changed to deny: `echo "$(case x { x) :;; })"; python3 -i` | deny | Unit |
| TS-5 | A continuation pair after a word character, then `#`: `echo "$(: a\<newline>#x)"; python3 -i` | deny | Unit |
| TS-6 | A continuation pair after a blank, then `#`; the comment holds the `)` and the launch: `zsh -c 'echo "$(printf x \<newline># )"; python3 -i; echo "<newline>)"'` | silent | Unit |
| TS-7 | Escaped `;` before `#`: `echo "$(: a\;#x)"; python3 -i` | deny | Unit |
| TS-8 | Escaped blank before `#` in an item body: `echo "$(case x in x) : \ #y;; esac)"; python3 -i` | deny | Unit |
| TS-9 | Escaped blank before `#` in a pattern: `echo "$(case x in a\ #b) :;; esac)"; python3 -i` | deny | Unit |
| TS-10 | Escaped blank before `#` in the outermost entry of a word list: `echo "$(for x (a\ #b) { :; })"; python3 -i` | deny | Unit |
| TS-11 | `#` after `>` keeps its reading: `echo "$(: >#x)"; python3 -i` | deny | Unit |
| TS-12 | Brace form closed by a pattern-position `esac`: `zsh -c 'echo "$(case x { x) :;; esac)"; python3 -i'` | deny | Unit |
| TS-13 | Brace form closed by a depth-0 body `}`: `echo "$(case x { x) :; })"; python3 -i` | deny | Unit |
| TS-14 | A `{ }` group in the body is not the close: `echo "$(case x { x) { :; };; })"; python3 -i` | deny | Unit |
| TS-15 | Quoted and escaped braces are not counted: `echo "$(case x { x) echo "}" '{' \{;; })"; python3 -i` | deny | Unit |
| TS-16 | A `}` at an argument position is not the close: `echo "$(case x { x) echo };; })"; python3 -i` | deny | Unit |
| TS-17 | An `in`-form statement inside a brace form: `echo "$(case x { x) case y in y) :;; esac;; })"; python3 -i` | deny | Unit |
| TS-18 | A brace form inside an `in`-form statement: `echo "$(case x in x) case y { y) :;; };; esac)"; python3 -i` | deny | Unit |
| TS-19 | A heredoc in a brace form: `echo "$(case x { x) cat <<E<newline>body<newline>E<newline>;; })"; python3 -i` | silent | Unit |
| TS-20 | An unclosed brace form: `echo "$(case x { x) :;;"; python3 -i` | silent | Unit |
| TS-21 | An `esac` at a command position of a brace-form body: `echo "$(case x { x) :; esac)"; python3 -i` | silent | Unit |
| TS-22 | An item terminator while a group is open: `echo "$(case x { x) { :;; })"; python3 -i` | silent | Unit |
| TS-23 | A quoted `{` does not replace `in`: `echo "$(case x "{" x) :;; })"; python3 -i` | silent | Unit |
| TS-24 | The contents of a brace-form substitution are not judged: `echo "$(case x { x) python3 -i;; })"` | silent | Unit |
| TS-25 | An arithmetic-command re-read inside a brace-form body: `echo "$(case x { x) { ((echo a) ); };; })"; python3 -i` | deny | Unit |
| TS-26 | The docstring marker tests: the undecidable list, the start of a word, the word-list `#` and the new comment-start and brace-form descriptions (`TestSubstitutionSkipDocumentation`) | pass | Unit |
| TS-27 | `python3 -m unittest tests.test_codex_hook_interactive_guard` passes, and `cmp em-workflow/scripts/codex-hook-interactive-guard.py em-review/scripts/codex-hook-interactive-guard.py` reports no difference | pass | Integration |
| TS-28 | NFR1 scale tests in `TestCaseStatementsInASubstitution`, each denied within the class timeout on both copies. The inputs are long runs of escaped blanks before `#`, long runs of continuation pairs between a word character and `#`, long backslash runs of both parities before a blank and `#`, one brace-form statement with DEPTH items, brace-form statements nested DEPTH deep, and DEPTH nested `{ }` groups in one brace-form body | pass | Integration |
| TS-29 | NFR4: `git diff --name-only` from workflow.yaml `implement.base_commit` to the integration HEAD lists neither `em-workflow/.claude-plugin/plugin.json`, `em-review/.claude-plugin/plugin.json` nor `.claude-plugin/marketplace.json` | pass | Integration |
| TS-30 | A comment ending in a backslash, then `#` at the start of the next line: `echo "$(: a #b\<newline># don't<newline>)"; python3 -i` | deny | Unit |
| TS-31 | The same form in an item body: `echo "$(case x in x) : a #b\<newline># don't<newline>;; esac)"; python3 -i` | deny | Unit |
| TS-32 | The same form at the pattern position (phase 4): `echo "$(case x in #b\<newline># don't<newline>x) :;; esac)"; python3 -i` | deny | Unit |
| TS-33 | The same form after the pattern's `)` (phase 7, rule 3): `echo "$(case x in x)#b\<newline># don't<newline>:;; esac)"; python3 -i` | deny | Unit |
| TS-34 | The same form in the outermost entry of a word list: `echo "$(for x (a #b\<newline># don't<newline>) { :; })"; python3 -i` | deny | Unit |
| TS-35 | The line after a backslash-ended comment is a comment that holds the `)` and the launch: `zsh -c 'echo "$(: a #b\<newline># )"; python3 -i; echo "<newline>)"'` | silent | Unit |
| TS-36 | NFR1 scale test in `TestCaseStatementsInASubstitution`: DEPTH repetitions of a comment ending in a backslash, each followed by a line that begins with `#`, in one substitution followed by `; python3 -i`, denied within the class timeout on both copies | pass | Integration |

## Code Quality Verification
- Format: none configured (`format_command` is empty)
- Static analysis: none configured
- Byte identity of the two copies: covered by TS-27

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | Reproduction 2 is denied | TS-1 |
| AC-2 | Reproduction 3 is denied | TS-2 |
| AC-3 | Reproduction 4 is denied | TS-3 |
| AC-4 | `#` after a continuation pair is decided by the character before the pair. `#` after an escaped character is a word character, in patterns, item bodies and the outermost word-list entry too | TS-5, TS-6, TS-7, TS-8, TS-9, TS-10, TS-30, TS-31, TS-32, TS-33, TS-34, TS-35, plus task0001's boundary rows |
| AC-5 | The brace form closes at a pattern-position `}` or `esac`, or a depth-0 body `}`. Body groups, quoted braces, argument `}` and nested statements are not mistaken for the close | TS-4, TS-12, TS-13, TS-14, TS-15, TS-16, TS-17, TS-18, TS-23 |
| AC-6 | A body `esac`, a terminator at depth 1 or more, an unclosed brace form and a heredoc in a brace form are undecidable (silent) | TS-19, TS-20, TS-21, TS-22 |
| AC-7 | The arithmetic-command re-read keeps the brace form readable | TS-25 |
| AC-8 | The pre-existing brace-form row is deny. The pre-existing heredoc rows named in task0002 AC-4 stay silent. Every other pre-existing row keeps its verdict | TS-4, TS-11, TS-24, TS-27 |
| AC-9 | The docstring and comments describe the actual reading, and the marker tests pass | TS-26 |
| AC-10 | The module passes on both copies, and the copies are byte-identical | TS-27 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001, task0003 | TS-1, TS-2, TS-5, TS-6, TS-7, TS-8, TS-9, TS-10, TS-30, TS-31, TS-32, TS-33, TS-34, TS-35 |
| FR2 | task0002 | TS-3, TS-4, TS-12, TS-13, TS-14, TS-15, TS-16, TS-17, TS-18, TS-23 |
| FR3 | task0002 | TS-3, TS-4, TS-12, TS-13, TS-14, TS-15, TS-16, TS-17, TS-18, TS-23 |
| FR4 | task0002 | TS-4, TS-12, TS-13, TS-14, TS-15, TS-16, TS-17, TS-18, TS-19, TS-20, TS-21, TS-22, TS-23 |
| FR5 | task0002 | TS-25 |
| FR6 | task0002 | TS-4, TS-11, TS-19, TS-20, TS-21, TS-22, TS-24 |
| FR7 | task0001, task0002, task0003 | TS-26 |
| FR8 | task0001, task0002, task0003 | TS-4, TS-11, TS-24, TS-26, TS-27 |
| FR9 | task0001, task0002, task0003 | TS-27 |
| NFR1 | task0001, task0002, task0003 | TS-28, TS-36 |
| NFR2 | task0001, task0002, task0003 | TS-4, TS-11, TS-24, TS-27 |
| NFR3 | task0001, task0002, task0003 | TS-6, TS-19, TS-20, TS-21, TS-22, TS-23, TS-24, TS-35 |
| NFR4 | task0001, task0002, task0003 | TS-29 |

## Manual Testing (E2E Not Possible)
- [ ] SPEC.md A3, which is not measured: run zsh in parse-only mode (`zsh -n`) on a brace-form statement whose last item body ends with a depth-0 `}`, and record whether zsh accepts it. This check is for information only and does not change TS-13's expected verdict.

## Performance / Security Verification (if applicable)
- NFR1: TS-28 and TS-36. Every scale input is denied within the deep-input class timeout on both copies.
- TM-1: The comment-start decision looks past continuation pairs and treats an escaped previous character as a word character at every site. The newline that ends a comment is never a continuation pair. Checked by TS-1, TS-2, TS-5, TS-6, TS-7, TS-8, TS-9, TS-10 and TS-30 to TS-35 on both copies.
- TM-2: The brace form is read to its close. Checked by TS-3, TS-4, TS-12 and TS-13 on both copies.
- TM-3: Only command-position braces of the item body list are counted. Nested statements keep their own state, the re-read restores the brace state, and uncertain forms stay undecidable. Checked by TS-14 to TS-25 (deny for TS-14 to TS-18 and TS-25, silent for TS-19 to TS-24) on both copies.
- TM-4: The reading stays linear. Checked by TS-28 and TS-36.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Unit (CASES rows and docstring markers, TS-1 to TS-26, TS-30 to TS-35) | 32 | 32 | 0 | 0 |
| Integration (TS-27 to TS-29, TS-36) | 4 | 4 | 0 | 0 |
| Security (TM-1 to TM-4) | 4 | 4 | 0 | 0 |
| Manual (SPEC.md A3 check) | 1 | 0 | 0 | 1 |
| Total | 41 | 40 | 0 | 1 |
