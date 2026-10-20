# Verification Document: codex-guard-redirect-only-list-pending

## Overview
**Feature**: codex-guard-redirect-only-list-pending / **SPEC.md**: `feature-docs/codex-guard-redirect-only-list-pending/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/codex-guard-redirect-only-list-pending/IMPLEMENTATION.md` / **THREAT-MODEL.md**: `feature-docs/codex-guard-redirect-only-list-pending/THREAT-MODEL.md`

All commands run from the repository root of the integration worktree. In the
scenario commands, `\n` stands for a newline.

## Build Verification
- Command: none (`project.components.main.build_command` is empty; the hook is a script run by the interpreter).
- Expected: not applicable. Do not byte-compile the plugin scripts by hand: a bytecode cache left in a plugin directory fails the bytecode-cache test in TestCopies and would ship to users.

## Test Verification
- Command (project-wide, from workflow.yaml): `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests`
- Command (this hook, from `.claude/rules/hook-tests.md`): `python3 -m unittest tests.test_codex_hook_interactive_guard`
- Expected: exit code 0, no failures or errors.
- Coverage target: not measured (no coverage tool is configured for this project). Every scenario below maps to a case-table row or an existing test.

### Test Scenarios from SPEC.md
TS1 to TS15 are SPEC.md's scenarios; TS16 to TS21 verify SPEC.md's success
criteria and non-functional requirements that have no scenario of their own.
Rows marked "case table" are rows of the case table in
`tests/test_codex_hook_interactive_guard.py`, run against both copies by
TestCasesTable.test_cases_run_against_both_copies.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS1 | `python3 -i &&\n< /dev/null\necho '` | deny (both copies) | Unit (case table) |
| TS2 | `python3 -i && > /dev/null\necho '` | deny (both copies) | Unit (case table) |
| TS3 | `python3 -i \|\| > /dev/null\necho '` | deny (both copies) | Unit (case table) |
| TS4 | `python3 -i && > /dev/null;\necho '` | deny (both copies) | Unit (case table) |
| TS5 | `python3 -i &&\n<<EOF\nx\nEOF\necho '` | deny (both copies) | Unit (case table) |
| TS6 | Each command of TS1 to TS5 as the operand of `bash -c`, quoted for a shell as the existing nested rows are | deny (both copies), five rows | Unit (case table) |
| TS7 | `python3 -i &&\n# c\necho '` | silent (both copies) | Unit (case table) |
| TS8 | `python3 -i &&\necho '` / `python3 -i \|\|\necho '` / `python3 -i &&\n\necho '` (existing rows) | silent (both copies), unchanged | Unit (case table) |
| TS9 | `(python3 -i && < /dev/null)\necho '` | deny (both copies) | Unit (case table) |
| TS10 | `(python3 -i \|\| < /dev/null)\necho '` | deny (both copies) | Unit (case table) |
| TS11 | `(function { :; } foo(a; python3 -i && < /dev/null)\necho '` | deny (both copies), through the rescue path | Unit (case table) |
| TS12 | `(python3 -i && < /dev/null);\necho '` | deny (both copies) | Unit (case table) |
| TS13 | `(python3 -i && < /dev/null) &\necho '` | deny (both copies) | Unit (case table) |
| TS14 | `(python3 -i &&)\necho '` | silent (both copies) | Unit (case table) |
| TS15 | `(function { :; } foo(a; python3 -i &&)\necho '` | silent (both copies) | Unit (case table) |
| TS16 | Documentation: TestGuardDocumentation on both copies; review of the `_Parser` list continuation paragraph, the list continuation field comment and the `_close_paren` / `_close_paren_after_rescue` docstrings against the FR1 / FR6 clearing conditions | all documentation tests pass; module docstring step 9 and the checkpoint sentences unchanged; `_close_paren` still names the case mark and the inherited value; no case-mark permanence phrase anywhere; the four texts state the new clearing conditions | Unit + review |
| TS17 | TestCopies (byte identity of the two copies, and no bytecode cache left in a plugin directory) | pass | Unit |
| TS18 | TestStaticConstraints | pass: both copies use the standard library only and stay within the static constraints | Unit |
| TS19 | TestMalformedAndDeepInput (the scale tests), plus review of the diff | all pass within their time bounds; the diff adds no parser attribute, no walk over groups or commands and no list copy at a newline or a `)` | Unit + review |
| TS20 | `git diff <workflow.implement.base_commit>..HEAD -- '*/.claude-plugin/plugin.json' .claude-plugin/marketplace.json` | empty output: the feature changes no plugin version field | Manual (command) |
| TS21 | TestCasesTable.test_cases_are_unique, plus review of the case-table diff | uniqueness test passes; the case-table diff only adds rows (no pre-existing row removed and no verdict changed) | Unit + review |

## Code Quality Verification
- Format: none configured (`project.components.main.format_command` is empty).
- Static analysis: TestStaticConstraints and TestNoRecursion, run by the test command above.

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | FR2's five commands deny in both copies | TS1 to TS5 |
| AC2 | FR2's commands inside `bash -c` deny in both copies | TS6 |
| AC3 | The existing silent rows stay silent; the new comment-line row is silent | TS7, TS8, TS21 |
| AC4 | The two copies are byte-identical | TS17 |
| AC5 | `python3 -m unittest tests.test_codex_hook_interactive_guard` passes from the repository root, documentation tests included | Test Verification command; TS16 |
| AC6 | The five `(`-group commands deny in both copies | TS9 to TS13 |
| AC7 | `(python3 -i &&)\necho '` and `(function { :; } foo(a; python3 -i &&)\necho '` stay silent in both copies | TS14, TS15 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS1 to TS8, TS12, TS13 (case table) |
| FR2 | task0001 | TS1 to TS6 (case table) |
| FR3 | task0001 | TS16 (documentation tests + review) |
| FR4 | task0001 | TS17 (byte-identity test) |
| FR5 | task0001 | TS1 to TS7, TS9 to TS15 (the new rows), TS21 (uniqueness, additions only) |
| FR6 | task0001 | TS9 to TS15 (case table) |
| NFR1 | task0001 | TS19 (scale tests + diff review) |
| NFR2 | task0001 | TS18 (static-constraint test) |
| NFR3 | task0001 | TS20 (version-field diff check) |
| NFR4 | task0001 | TS8, TS21 (existing rows unchanged) |
| NFR5 | task0001 | TS16 (documentation tests) |

## E2E Testing
Not applicable: the project has no E2E framework (`e2e_test_command` is empty).
The reproduction steps of the original report (feeding the command to the hook
on standard input) are what the case-table run does, so TS1 and TS2 cover them
automatically.

## Manual Testing (E2E Not Possible)
- [ ] TS20: run the version-field diff check and confirm it prints nothing.

## Performance / Security Verification (if applicable)
- NFR1: per-newline and per-`)` work stays constant — TS19.
- TM-1: the list continuation ends at a non-newline separator, at a separator that ends a simple command holding a redirection, and at a `)` closing a `(` group whose ended simple command holds a redirection, in both copies — checked by the deny rows TS1 to TS6 and TS9 to TS13 run against both copies.
- TM-2: a blank line, a comment-only line, a heredoc body and a `)` with no redirection before it keep the continuation, and no existing verdict changes — checked by the silent rows TS7, TS8, TS14, TS15 and by TS21.
- TM-3: the new clearing adds no state, no walk and no list copy — checked by TS19 (scale tests and diff review).

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Case-table scenarios (TS1 to TS15) | 15 | 15 | 0 | 0 |
| Documentation (TS16) | 1 | 1 (plus review) | 0 | 0 |
| Copies, static constraints, scale (TS17 to TS19) | 3 | 3 (TS19 plus review) | 0 | 0 |
| Version-field check (TS20) | 1 | 0 | 0 | 1 |
| Table integrity (TS21) | 1 | 1 (plus review) | 0 | 0 |
| Security mitigations (TM-1 to TM-3) | 3 | 3 | 0 | 0 |
| Success criteria (AC1 to AC7) | 7 | 7 | 0 | 0 |
