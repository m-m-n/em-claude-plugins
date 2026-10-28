# Verification Document: cd-prefix-toplevel-operators

## Overview
**Feature**: cd-prefix-toplevel-operators / **SPEC.md**: `feature-docs/cd-prefix-toplevel-operators/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/cd-prefix-toplevel-operators/IMPLEMENTATION.md`

Scenario IDs use the TSn form (TS1 … TS9) so that they match the IDs of
SPEC.md and the `requirements.*.tests` entries of workflow.yaml as literal
strings. TS1–TS7 come from SPEC.md; TS8 and TS9 are added here. Inside the
tables below, a pipe character in a command is written escaped so the table
renders; the command itself holds a plain pipe.

## Build Verification
- Command: none (`project.components.main.build_command` is empty).
- Expected: not applicable.

## Test Verification
- Command: `python3 -m unittest discover -s tests` (from the repository root)
- Expected: exit code 0, no failure and no error.
- Coverage target: not measured (the project has no coverage tool; the
  criterion is that every scenario below has passing cases).

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS1 | Approve `A & B`, `A ; B`, `A \|\| B`, `A &`, `A;` (plus `A &&& B`, a quote-edge `;` and a line feed inside), run the cd prefix form with a path in the worktree area | No decision (no output) | Integration (hook subprocess) |
| TS2 | Approve `make test 2>&1`, `a \|& b`, `a \| b`, `a &> log`, `a &>> log`, `a <&0`, `a && b`, `echo "a;b"`, `echo 'a&b'`, `echo a\;b` (plus the quote-edge and escape cases of task0001 AC-2), run the cd prefix form | `allow` with the cd prefix reason | Integration (hook subprocess) |
| TS3 | Approve one string per FR3 condition (unclosed quote, trailing backslash, `$'x'`, `$"x"`, `#` in several positions including inside quotes, `(` `)` `{` `}` outside quotes, `$(true)`, `${HOME}`, backtick, `$(` / `${` / backtick inside double quotes), run the cd prefix form | No decision | Integration (hook subprocess) |
| TS4 | Bare `A & B` that is approved; a declared, unapproved string; excluded cd prefix forms whose whole string is declared or approved | `allow` (exact match); `deny` (unapproved); `deny`; `allow` | Integration (hook subprocess) |
| TS5 | A refusal-pattern string that also holds `&` (and one with `;`), written to the store directly, run in the cd prefix form | `deny`; the reason names 禁止パターン and the pattern | Integration (hook subprocess) |
| TS6 | The existing cases of `tests/test_bash_guard_cd_prefix.py` | All pass, the module unedited | Integration (regression) |
| TS7 | Document tests: sections sliced by heading, whitespace normalized; the FR6–FR9 statements (exclusion conditions, the implementer does not run such a string and reports it in `notes`) are present in the protocol, README, workflow-schema, implementer.md, SKILL.md and the hook docstring; every absence assertion has a forged-text pair | All pass | Unit (document) |
| TS8 | The integrated diff from `workflow.implement.base_commit` to the integration HEAD, file names only | Contains none of `em-workflow/hooks/queue_launch_guard.py`, `em-workflow/scripts/merge-task.sh`, `em-workflow/hooks/hooks.json`, any `.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` | Inspection (git diff) |
| TS9 | The full suite, including the pinned modules `tests/test_cd_prefix_exception_docs.py`, `tests/test_implementer_cd_chain_docs.py`, `tests/test_worktree_skill_instruction_source.py`, `tests/test_hook_classification_pin.py`, `tests/test_hooks_registration.py` | `python3 -m unittest discover -s tests` exits 0 | Regression (full suite) |

## Code Quality Verification
- Format: none (`format_command` is empty).
- Static analysis: none configured. The standard-library-only checks run
  inside the suite (TS6, TS9).

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC1 | All functional requirements are implemented and tested | Functional Requirements Coverage below; TS1–TS7 pass |
| SC2 | All test scenarios pass | TS1–TS9 |
| SC3 | Security requirements are satisfied | Performance / Security Verification below (TM-1 … TM-5) |
| SC4 | Documentation is complete | TS7 |
| SC5 | Code review is completed | The review phase completes with no open critical / high finding |
| SC6 | `python3 -m unittest discover -s tests` passes (SPEC AC8) | TS9 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS1, TS2, TS6 |
| FR2 | task0001 | TS1, TS2, TS6 |
| FR3 | task0001 | TS1, TS3 |
| FR4 | task0001 | TS1, TS3, TS4 |
| FR5 | task0001 | TS5 |
| FR6 | task0002 | TS7 |
| FR7 | task0003 | TS7 |
| FR8 | task0002 | TS7 |
| FR9 | task0001 | TS7 |
| FR10 | task0001, task0002, task0003 | TS1, TS2, TS3, TS4, TS5, TS7, TS9 |
| NFR1 | task0001 | TS6 (standard-library-only check) |
| NFR2 | task0001 | TS6, TS9 (`status` substring checks) |
| NFR3 | task0001 | TS6, TS8, TS9 |
| NFR4 | task0001, task0002, task0003 | TS8 |
| NFR5 | task0003 | TS6, TS9 (`tests/test_implementer_cd_chain_docs.py`, `tests/test_worktree_skill_instruction_source.py`) |
| NFR6 | task0002, task0003 | TS6, TS9 (`tests/test_cd_prefix_exception_docs.py`, `tests/test_implementer_cd_chain_docs.py`) |
| NFR7 | task0001, task0002, task0003 | TS6, TS9 |

## Manual Testing (E2E Not Possible)
None. Every scenario is automated or a mechanical inspection (TS8).

## Performance / Security Verification (if applicable)
- TM-1: top-level `&`, `;`, `||` and line break exclude the cd prefix form — TS1 cases give no decision and TS2 cases stay allowed.
- TM-2: the safe-side constructs exclude the cd prefix form without nesting being parsed — every TS3 case gives no decision.
- TM-3: refusal patterns still deny a cd prefix form with a top-level operator — TS5 gives `deny` with the pattern named in the reason.
- TM-4: the implementer does not run an excluded approved string and reports it in `notes` — TS7 finds the statement in the protocol Verbatim execution rule, implementer.md Step 3 and the SKILL.md Command execution gate.
- TM-5: redirection and pipe tokens, quoted and escaped characters do not exclude, and no new deny appears — TS2 stays allowed, TS4 gives the pre-change decisions, TS6 passes unedited.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios | 9 (TS1–TS9) | 9 | 0 | 0 |
| Success criteria | 6 (SC1–SC6) | 5 | 0 | 1 (SC5, review outcome) |
| Security (TM-n) | 5 (TM-1–TM-5) | 5 | 0 | 0 |
