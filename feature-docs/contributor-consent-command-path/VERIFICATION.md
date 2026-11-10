# Verification Document: contributor-consent-command-path

## Overview
**Feature**: contributor-consent-command-path / **SPEC.md**: `feature-docs/contributor-consent-command-path/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/contributor-consent-command-path/IMPLEMENTATION.md`

## Build Verification
- Command: none. `build_command` is empty in workflow.yaml, and the change is a Python test module plus, conditionally, the two skill documents.
- Expected: not applicable.

## Test Verification
- Command: `python3 -m unittest discover -s tests`
- Expected: exit code 0, no failures or errors.
- Coverage target: not measured, because no coverage tool is configured. The scenario table below is the completeness criterion.

### Test Scenarios from SPEC.md

SPEC.md defines TS-1 to TS-9. The plan derives TS-10 to TS-13 from FR3, FR5,
NFR3, NFR4 and NFR5, which need a verifying scenario that the SPEC list does not
hold.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Both skill copies: bind step 5's answer branches to the commands the skill runs | The consent branch is bound to exactly one `--record` command with `hooks/muse_guard.py` and `--project-dir`. The revoke branch is bound to exactly one `--remove` command. Holds for both copies | Unit |
| TS-2 | Both skill copies: the decline and keep branches, and step 6 | The decline and keep branches are bound to no command. Step 6 holds no guard invocation and outputs the no-write line. Holds for both copies | Unit |
| TS-3 | Both skill copies: classify every fenced block and every user-facing literal into two kinds | Every element is classified. User-visible text holds no `${NAME}` or `$NAME` reference. The commands of step 2 and step 5 are classified as skill-executed | Unit |
| TS-4 | Both skill copies: step 5 | Step 5 states that the skill runs the commands and holds no instruction to run them in the user's terminal | Unit |
| TS-5 | Synthetic text through the variable check | Text with `${CLAUDE_PLUGIN_ROOT}` or `$HOME` is flagged. Text with only `$(pwd)`, or with no reference, is not | Unit |
| TS-6 | Synthetic body with step 5's `--record` or `--remove` command removed | The binding check fails | Unit |
| TS-7 | Synthetic body with an added fenced block of unknown kind | The classification check fails | Unit |
| TS-8 | Static check of `tests/test_contributor_consent_skill.py` | No wording lock of the commands. A text search finds neither removed constant name, neither the quoted plugin-root form `"${CLAUDE_PLUGIN_ROOT}"` nor the argument form `--project-dir "$(pwd)"`, and neither "presented to the user" nor "never executed" (case-insensitive). Review finds no passage describing the guard commands as presented to the user | Static (text search and review) |
| TS-9 | Full suite run | All tests pass: the existing checks of the skill test module (task0002 AC-1 to AC-6; task0009 AC-2, AC-3 and AC-5, including the cross-copy equality check), and `tests/test_muse_consent_no_new_questions.py` | Integration |
| TS-10 | Synthetic step 5 that tells the user to paste or run a command in their own terminal, and one whose command-bound branch no longer states that the command is run (derived from FR5 and NFR4) | The run-statement check fails for each | Unit |
| TS-11 | Synthetic body with a guard command bound to the decline or keep branch, and one with a guard invocation in step 6 (derived from FR3 and NFR4) | The binding check fails for each | Unit |
| TS-12 | Rewrap variants of each real skill copy: prose paragraphs joined into one line, and split at a narrower column (derived from NFR3) | The classification, binding and run-statement checks all pass | Unit |
| TS-13 | Static check of the files the feature changes (derived from NFR5) | No Notion URL and no absolute path under a home directory | Static (text search) |

## Code Quality Verification
- Format: none configured (`format_command` is empty in workflow.yaml).
- Static analysis: none configured.
- Imports: the changed test module imports only the standard library (review, SPEC AC-9).

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SPEC AC-1 | The test module holds neither the presented-command constants nor an assertion matching a whole command string or the quoted plugin-root path | TS-8 |
| SPEC AC-2 | The consent and revoke branches of step 5 are each bound to exactly one skill-executed command, for both copies | TS-1 |
| SPEC AC-3 | The decline and keep branches run nothing, and step 6 calls no CLI and outputs the no-write line, for both copies | TS-2 |
| SPEC AC-4 | All fenced blocks and user-facing literals are classified, and user-visible text holds no variable reference, for both copies | TS-3 |
| SPEC AC-5 | Step 5 says the skill runs the commands and gives no user-terminal instruction, for both copies | TS-4 |
| SPEC AC-6 | Non-vacuity of the variable, binding and classification checks | TS-5, TS-6, TS-7 |
| SPEC AC-7 | The task0009 names, comments and docstring describe the skill-executed design | TS-8 |
| SPEC AC-8 | The existing checks still hold | TS-9 |
| SPEC AC-9 | The suite passes, and the changed module imports only the standard library | TS-9 and the import review above |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-4, TS-9 |
| FR2 | task0001 | TS-8 |
| FR3 | task0001 | TS-1, TS-2, TS-6, TS-11 |
| FR4 | task0001 | TS-3, TS-5, TS-7 |
| FR5 | task0001 | TS-4, TS-10 |
| FR6 | task0001 | TS-8 |
| FR7 | task0001 | TS-9 |
| NFR1 | task0001 | TS-9 |
| NFR2 | task0001 | TS-9 |
| NFR3 | task0001 | TS-8, TS-12 |
| NFR4 | task0001 | TS-5, TS-6, TS-7, TS-10, TS-11 |
| NFR5 | task0001 | TS-13 |

## Manual Testing (E2E Not Possible)

This check is optional. It needs an interactive session in which the LiteLLM
harness is available, and it changes the consent store, then restores it.

- [ ] Run the contributor-consent skill of each plugin and answer the consent option.
  - [ ] The skill runs the record command itself and reports the result in one line.
  - [ ] No shown line asks the user to paste or run a command in their own terminal.
  - [ ] Run the skill again and answer the revoke option to restore the store.

## Performance / Security Verification
- TM-1: a mutating guard command can be reached only from the explicit consent answer or the explicit revoke answer. Checked in two ways:
  - TS-1, TS-2 and TS-3 pass on both real copies.
  - The synthetic cases TS-6, TS-7 and TS-11 make the binding and classification checks fail.
- NFR5: the files the feature changes contain no Notion URL and no absolute path under a home directory. Checked by TS-13.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Unit scenarios (TS-1 to TS-7, TS-10 to TS-12) | 10 | 10 | 0 | 0 |
| Integration scenario (TS-9) | 1 | 1 | 0 | 0 |
| Static scenarios (TS-8, TS-13) | 2 | 2 | 0 | 1 |
| Security items (TM-1, NFR5) | 2 | 2 | 0 | 0 |
| Optional interactive check | 1 | 0 | 0 | 1 |
