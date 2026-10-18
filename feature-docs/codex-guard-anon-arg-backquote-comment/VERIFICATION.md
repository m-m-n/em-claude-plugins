# Verification Document: codex-guard-anon-arg-backquote-comment

## Overview
**Feature**: codex-guard-anon-arg-backquote-comment / **SPEC.md**: `feature-docs/codex-guard-anon-arg-backquote-comment/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/codex-guard-anon-arg-backquote-comment/IMPLEMENTATION.md` / **THREAT-MODEL.md**: `feature-docs/codex-guard-anon-arg-backquote-comment/THREAT-MODEL.md`

Scenario IDs here use the hyphenated form. Scenario TS-k corresponds to
SPEC.md's unit scenario with the same number for k from 1 to 7; TS-8
corresponds to SPEC.md's integration scenario; TS-9 to TS-13 are SPEC.md's
Edge Cases that no existing CASES row covers; TS-14 checks NFR3's version
clause.

Two copies are under test: `em-workflow/scripts/codex-hook-interactive-guard.py`
and `em-review/scripts/codex-hook-interactive-guard.py`. Every check marked
"both copies" passes only when it passes on each copy.

**Direct invocation** (used by TS-9 to TS-13): feed each copy, on standard
input, the same JSON shape the CASES runner in
`tests/test_codex_hook_interactive_guard.py` builds, with
`tool_input.command` set to the scenario's command. deny means the output
carries `permissionDecision: deny`; silent means exit code 0 with empty
output. The command itself is never executed.

## Build Verification
- Command: none — `build_command` is empty in workflow.yaml `project.components.main`
- Expected: not applicable

## Test Verification
- Command (project test command, verbatim): `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests`
- Command (guard suite): `python3 -m unittest tests.test_codex_hook_interactive_guard`
- Expected: exit code 0, no failures or errors
- Coverage target: not measured (no coverage tool is configured); completeness is judged by the scenario table below

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Reproduction command (command list below) as a CASES row, both copies | deny | Unit (CASES) |
| TS-2 | Reproduction followed by a newline and python3 -i, as a CASES row, both copies | deny | Unit (CASES) |
| TS-3 | Nested group inside the argument range, as a CASES row, both copies | deny (the inner group inherits the exception) | Unit (CASES) |
| TS-4 | Scan stops early at a closing parenthesis inside the backquote, then a direct semicolon, as a CASES row, both copies | deny (the semicolon clears the exception; the hash starts a comment; the group is rescued; the trailing python3 -i is judged) | Unit (CASES) |
| TS-5 | Every pre-existing CASES row, unchanged, both copies — including the rescue rows containing a hash before the closing parenthesis (among them the separator-triggered form with python3 -i and a comment inside the range), the backquote rows (among them the unclosed-backquote rows) and the comment-outside-a-group rows | each row keeps its expected decision and passes; no row removed | Unit (CASES) |
| TS-6 | TestCopies and TestGuardDocumentation, with the new docstring markers added | pass on both copies; every existing marker still passes; no stale sentence present | Unit |
| TS-7 | Existing performance tests (nested backquote ranges, and the prior feature's rescue-form case) and the recursion-check test, both copies | respond within the existing time limits; recursion check passes | Unit (performance) |
| TS-8 | Guard suite command, then the project test command | both exit 0 | Integration |
| TS-9 | Mid-word hash after a backquote, both copies | deny (unchanged from today) | Direct invocation |
| TS-10 | Single pipe inside an exception group before a word-start hash, both copies | deny (the pipe does not clear the exception) | Direct invocation |
| TS-11 | Double pipe inside an exception group before a word-start hash, both copies | deny (the double pipe does not clear the exception) | Direct invocation |
| TS-12 | Exception group closed by its parenthesis, followed by an input redirection, body without -i, both copies | deny (known false-deny class, same treatment as the prior feature's redirection row) | Direct invocation |
| TS-13 | Argument range holding both a semicolon and a backquote, both copies | same output as the copy at the feature's base commit (the exception does not apply because the range is separated) | Direct invocation (differential) |
| TS-14 | Integrated diff from the base commit | no change to any version field in a plugin's plugin.json or in the root marketplace.json | Inspection (git diff) |

Commands, verbatim as hook input. `<newline>` stands for one literal LF
character in the command string; the `'"'"'` sequence in TS-4 is part of the
string.

- TS-1: ``zsh -c 'setopt nonomatch nobareglobqual; function { python3 -i; } foo(`echo x` #)'``
- TS-2: ``zsh -c 'setopt nonomatch nobareglobqual; function { python3 -i; } foo(`echo x` #)<newline>python3 -i'``
- TS-3: ``zsh -c 'setopt nonomatch nobareglobqual; function { python3 -i; } foo(`echo x` (a #))'``
- TS-4: ``zsh -c 'setopt nonomatch nobareglobqual nobadpattern; function { python3 -i; } foo(`case x in x) echo x;; esac`; # '"'"' ignored<newline>python3 -i'``
- TS-9: ``zsh -c 'setopt nonomatch nobareglobqual; function { python3 -i; } foo(`x`#)'``
- TS-10: ``zsh -c 'setopt nonomatch nobareglobqual; function { python3 -i; } foo(`echo x` | #)'``
- TS-11: ``zsh -c 'setopt nonomatch nobareglobqual; function { python3 -i; } foo(`echo x` || #)'``
- TS-12: ``zsh -c 'setopt nonomatch nobareglobqual; function { python3; } foo(`echo x` #) < /dev/null'``
- TS-13: ``zsh -c 'setopt nonomatch nobareglobqual; function { python3 -i; } foo(`echo x`; #)'``

## Code Quality Verification
- Format: none configured (`format_command` is empty)
- Static analysis: none configured; the static constraints (standard library only, no file, network or child-process access) are checked by `TestStaticConstraints`, part of TS-8

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | All functional requirements are implemented and tested | Functional Requirements Coverage table below: every row has a task and at least one passing scenario |
| SC-2 | All test scenarios pass | TS-1 to TS-14 pass |
| SC-3 | Performance meets specified goals | TS-7 |
| SC-4 | Security requirements are satisfied | TS-5, TS-8 (`TestStaticConstraints`), TM-1 to TM-3 below |
| SC-5 | Documentation is complete | TS-6 (docstring markers in the four places FR8 names, both copies) |
| SC-6 | Code review is completed | workflow.yaml `review.status` is `completed` with `residual_critical_high` 0 |
| SC-7 | The two copies are byte-identical | TS-6 (`TestCopies.test_the_two_copies_are_byte_identical`) |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-8 |
| FR2 | task0001 | TS-1, TS-2, TS-9, TS-12 |
| FR3 | task0001 | TS-3 |
| FR4 | task0001 | TS-4, TS-10, TS-11 |
| FR5 | task0001 | TS-5, TS-12, TS-13 |
| FR6 | task0001 | TS-6 |
| FR7 | task0001 | TS-1, TS-2, TS-3, TS-4 |
| FR8 | task0001 | TS-6 |
| NFR1 | task0001 | TS-7 |
| NFR2 | task0001 | TS-5, TS-8 |
| NFR3 | task0001 | TS-5, TS-14 |

## Manual Testing (E2E Not Possible)
- None required. SPEC A4 (zsh's own reading of the argument range) is an accepted assumption and is not checked against a real zsh.

## Performance / Security Verification (if applicable)
- NFR1: parsing stays linear and non-recursive — TS-7 (existing performance tests and recursion check, both copies)
- NFR2: standard library only, no file, network or child-process access, no existing deny row turned silent — TS-8 (`TestStaticConstraints`) and TS-5
- TM-1: a word-start unquoted hash inside a backquote-triggered argument group, or a group nested in it, is a word character, applied to both copies byte-identically — checked by TS-1, TS-2, TS-3 (deny on both copies) and TS-6 (byte identity)
- TM-2: the exception is cleared by the five direct separators only and every other reading is unchanged — checked by TS-4 (deny), TS-10 and TS-11 (deny), TS-13 (output equal to the base copy) and TS-5 (every existing row unchanged)
- TM-3: the per-group state costs constant time per group open and per read, with no recursion — checked by TS-7 on both copies

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS-1 to TS-14) | 14 | 14 | 0 | 0 |
| Success criteria (SC-1 to SC-7) | 7 | 7 | 0 | 0 |
| Requirements coverage (FR1 to FR8, NFR1 to NFR3) | 11 | 11 | 0 | 0 |
| Performance / security requirements (NFR1, NFR2) | 2 | 2 | 0 | 0 |
| Threat mitigations (TM-1 to TM-3) | 3 | 3 | 0 | 0 |
| Manual | 0 | 0 | 0 | 0 |
