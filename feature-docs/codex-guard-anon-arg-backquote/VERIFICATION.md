# Verification Document: codex-guard-anon-arg-backquote

## Overview
**Feature**: codex-guard-anon-arg-backquote / **SPEC.md**: `feature-docs/codex-guard-anon-arg-backquote/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/codex-guard-anon-arg-backquote/IMPLEMENTATION.md`

## Build Verification
- Command: none. `build_command` is empty for component `main` in workflow.yaml; the guard is an interpreted script.
- Expected: not applicable.

## Test Verification
- Command (component `main`, from the repository root): `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests`
- Focused command: `python3 -m unittest tests.test_codex_hook_interactive_guard`
- Expected: exit code 0 for both.
- Coverage target: no coverage tool is configured for this component. Coverage is judged by the tables below: every FR/NFR maps to at least one scenario.

### Test Scenarios from SPEC.md
`CASES` rows are (verdict, label, command) and run against both guard copies. Every command is hook input only and is never executed.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS1 | Reproduction: ``zsh -c 'setopt nonomatch nobareglobqual; function { python3 -i; } foo(`case x in x) echo x;; esac`)'`` | deny from both copies | Unit (CASES) |
| TS2 | Backquote inside double quotes: ``zsh -c 'setopt nonomatch nobareglobqual; function { python3 -i; } foo("`echo "x)"`")'`` | deny from both copies | Unit (CASES) |
| TS3 | Balanced backquotes inside double quotes, then a stdin redirect: ``zsh -c 'setopt nonomatch nobareglobqual; function { python3; } foo("`echo x`") < /dev/null'`` | deny from both copies | Unit (CASES) |
| TS4 | Balanced backquotes, then a stdin redirect (known false deny): ``zsh -c 'setopt nonomatch nobareglobqual; function { python3; } foo(`echo x`) < /dev/null'`` | deny from both copies | Unit (CASES) |
| TS5 | Backquotes after a backslash inside double quotes: ``zsh -c 'setopt nonomatch nobareglobqual; function { python3; } foo("\`x\`") < /dev/null'`` | no output from either copy | Unit (CASES) |
| TS6 | Backquotes after a backslash outside quotes: ``zsh -c 'setopt nonomatch nobareglobqual; function { python3; } foo(\`x\`) < /dev/null'`` | no output from either copy | Unit (CASES) |
| TS7 | Backquotes inside single quotes: the `-c` operand zsh receives is ``setopt nonomatch nobareglobqual; function { python3; } foo('`x`') < /dev/null`` | no output from either copy | Unit (CASES) |
| TS8 | Unclosed backquote: ``zsh -c 'setopt nonomatch nobareglobqual; function { python3 -i; } foo(`echo x)'`` | no output from either copy | Unit (CASES) |
| TS9 | Unclosed backquote inside double quotes: ``zsh -c 'setopt nonomatch nobareglobqual; function { python3 -i; } foo("`echo x")'`` | no output from either copy | Unit (CASES) |
| TS10 | Every `CASES` row that existed before the feature, unchanged: the `foo(x) < /dev/null` silent row, the `;` `&` newline deny rows, the rescue rows, and the rows that hold `$(` | each row's verdict holds for both copies | Unit (CASES) |
| TS11 | `TestGuardDocumentation` with the backquote-rule markers for the module docstring step 4, `_Parser`, `_scan_parens` and `_read_argument_parens`, plus the byte-identity test `TestCopies` | pass | Unit (documentation / copies) |
| TS12 | Performance: `depth` repetitions of ``function { :; } x(`:` `` followed by `depth` closing parentheses, added to the nested-argument-range performance test | both copies answer this and every existing shape within the existing time limit | Unit (performance) |
| TS13 | SPEC.md Edge Cases (assumption A1), a backquote only after the range's closing `)`: ``zsh -c 'setopt nonomatch nobareglobqual; function { python3; } foo(x) < /dev/null; echo `echo y`'`` | no output from either copy | Unit (CASES) |
| TS14 | NFR3, change-set check: the diff between the feature's base and the integration branch | it lists neither `em-workflow/.claude-plugin/plugin.json`, `em-review/.claude-plugin/plugin.json` nor `.claude-plugin/marketplace.json` | Change-set check |

### Integration Tests from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| IT1 | The focused command and the component command, from the repository root | both exit 0 | Integration |

## Code Quality Verification
- Format: none configured (`format_command` is empty).
- Static analysis: `TestStaticConstraints` (standard library only; no file, network or child-process access) and `TestNoRecursion` (no recursion) in the focused module. Both run as part of the test commands above.

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | All functional requirements are implemented and tested | Functional Requirements Coverage below; TS1-TS13 pass |
| SC-2 | All test scenarios pass | The component command exits 0 (IT1) |
| SC-3 | Performance meets the specified goals | TS12; `TestNoRecursion` |
| SC-4 | Security requirements are satisfied | TM-1 and TM-2 items below; `TestStaticConstraints` |
| SC-5 | Documentation is complete | TS11 |
| SC-6 | Code review is completed | The review phase finishes with no open finding |
| SC-7 | The two copies are byte-identical | TS11 (`TestCopies`) |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS1 |
| FR2 | task0001 | TS2 |
| FR3 | task0001 | TS5, TS6, TS7 |
| FR4 | task0001 | TS3, TS4 |
| FR5 | task0001 | TS10, TS13 |
| FR6 | task0001 | TS8, TS9 |
| FR7 | task0001 | TS11 |
| FR8 | task0001 | TS11 |
| FR9 | task0001 | TS1-TS9, IT1 |
| NFR1 | task0001 | TS12 |
| NFR2 | task0001 | IT1 (`TestStaticConstraints`) |
| NFR3 | task0001 | TS14 |

## Manual Testing (E2E Not Possible)
- [ ] Run the reported reproduction by hand against each copy. Pipe a PreToolUse JSON whose `tool_input.command` is the TS1 command into the guard's stdin; the command itself is never executed. Confirm that the guard exits 0 and prints exactly one object with `permissionDecision: deny`. TS1 automates the same check; this item confirms the feature goal's done-definition, which says the reported steps no longer reproduce.

## Performance / Security Verification
- NFR1: the TS12 shape and every existing shape are answered by both copies within the existing time limit, and `TestNoRecursion` passes.
- TM-1: an argument range that holds a backquote that is neither single-quoted nor right after a backslash makes its `(` open a provisional group, so the anonymous body's explicit `python3 -i` is denied. Checked by TS1 and TS2 (deny) and by TS3 and TS4 (balanced backquotes also fall back to the group reading).
- TM-2: noticing the backquote costs constant work per scanned character, and every range scan stays charged to the existing work cap. Checked by TS12 and `TestNoRecursion`.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Unit (CASES) | 11 (TS1-TS10, TS13) | 11 | 0 | 0 |
| Unit (documentation / copies) | 1 (TS11) | 1 | 0 | 0 |
| Performance | 1 (TS12) | 1 | 0 | 0 |
| Change-set check | 1 (TS14) | 1 | 0 | 0 |
| Integration | 1 (IT1) | 1 | 0 | 0 |
| Security (TM-n) | 2 (TM-1, TM-2) | 2 | 0 | 0 |
| Manual | 1 | 0 | 0 | 1 |
| **Total** | 18 | 17 | 0 | 1 |
