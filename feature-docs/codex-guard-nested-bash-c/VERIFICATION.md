# Verification Document: codex-guard-nested-bash-c

## Overview
**Feature**: codex-guard-nested-bash-c / **SPEC.md**: `feature-docs/codex-guard-nested-bash-c/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/codex-guard-nested-bash-c/IMPLEMENTATION.md`

## Build Verification
- Command: none. Both components (`repo-tests`, `plugin-invariants`) have an empty `build_command` in workflow.yaml.
- Expected: not applicable.

## Test Verification
- Command (feature module, NFR4): `python3 -m unittest tests.test_codex_hook_interactive_guard`
- Command (`repo-tests` component): `python3 -m unittest discover -s tests`
- Command (`plugin-invariants` component): `python3 em-workflow/scripts/check-plugin-invariants.py .`
- Expected: exit code 0 for each, run from the repository root.
- Coverage target: not measured (standard library only, no coverage tool). Behaviour coverage is by the scenarios below.

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Nested deny rows in `CASES`: the three changed rows (`bash -c "bash -c 'python3 -i'"`, `sh -c 'bash -lc "python3 -i"'`, `bash -cx "bash -c 'python3 -i'"`), a second-level program-less launch, the task's extglob example, a three-level string, inner `zsh -c` / `bash -lc` / `env FOO=1 bash -c`, and a second-level `cd x && python3 -i` | Both copies print exactly one deny object | Integration (hook run as a process) |
| TS-2 | Nested silent rows in `CASES`: pipe and stdin redirect reaching the second level, a pipe inside the second level, a dynamic second-level operand, a harmless second-level string, an unbalanced quote in the second-level string, an inner function body | Both copies print nothing | Integration |
| TS-3 | Deep nesting by repeated shell-quoting (the depth the limit admits, and one deeper) and many sibling second-level strings totalling over the limit | Within 60 s: exit status 0, empty standard error, standard output empty or exactly one deny object; the depth the limit admits is denied | Integration |
| TS-4 | Limit behaviour: total exactly at the limit is read (deny); one character over is not (silent); later second-level strings pass once the limit is reached, even in another first-level string; a second-level launch before the limit is denied; first-level and level-0 launches are denied whatever the total | Verdicts as stated, on both copies | Integration |
| TS-5 | `TestGuardDocumentation` markers for every-level judgment, the explicit stack and the limit; the two replaced step-7 sentences are absent | Both copies' docstrings hold the markers and lack the stale sentences | Static (docstring) |
| TS-6 | The feature module suite, including `TestCopies` (byte identity) and `TestStaticConstraints` (standard library only, no network, process or write) | `python3 -m unittest tests.test_codex_hook_interactive_guard` exits 0 | Unit / Integration |
| TS-7 | Judgment order and recursion absence (derived from FR2): a nested launch before a later launch decides the reason; a static check finds no self-call and no cycle among module-level functions | The reason names the nested launch; the static check passes on both copies and flags its own samples | Integration + Static |
| TS-8 | Version fields untouched (derived from NFR5) | The integrated diff against the base commit lists none of `em-workflow/.claude-plugin/plugin.json`, `em-review/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` | Diff check |

## Code Quality Verification
- Format: none configured (`format_command` is empty in workflow.yaml).
- Static analysis: `TestStaticConstraints` (part of TS-6) and the recursion-absence check (TS-7).
- Byte identity of the two copies: `TestCopies` (part of TS-6).

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | SPEC.md records the every-level decision and its reasons | Manual check (below) |
| AC2 | `CASES` holds nested deny rows, including the extglob example | TS-1 |
| AC3 | The three changed rows expect deny, and SPEC.md gives a reason for each | TS-1, plus manual check (below) |
| AC4 | Inner levels keep the first-level rules; listed inputs stay silent | TS-2 |
| AC5 | `_scan` walks nested strings with an explicit stack; second-level-and-deeper re-reads are capped; strings past the cap pass | TS-4, TS-7 |
| AC6 | Deep and many nested inputs are answered in time with exit 0 and empty standard error | TS-3 |
| AC7 | Docstring step 7 describes every-level judgment, the explicit stack and the limit in both copies | TS-5 |
| AC8 | The two copies are byte-identical and the module suite passes | TS-6 |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2 |
| FR2 | task0001 | TS-3, TS-7 |
| FR3 | task0001 | TS-3, TS-4 |
| FR4 | task0001 | TS-1 |
| FR5 | task0001 | TS-1, TS-2 |
| FR6 | task0002 | TS-5 |
| FR7 | task0001, task0002 | TS-6 |
| NFR1 | task0001 | TS-6 |
| NFR2 | task0001 | TS-2, TS-4 |
| NFR3 | task0001 | TS-3 |
| NFR4 | task0001, task0002 | TS-6 |
| NFR5 | task0001, task0002 | TS-8 |

## Manual Testing (E2E Not Possible)
- [ ] SPEC.md "判断記録" states that `-c` strings are judged at every level and why, and "既存 CASES の期待の変更" gives a reason for each of the three changed rows (AC1, AC3).
- [ ] Step 7 of the module docstring (either copy) agrees with the merged traversal: every level with the same rules, explicit stack and order, the 1,000,000-character limit over second-level-and-deeper strings, first-level strings not counted, strings past the limit passing, the limit never a deny reason.

## Performance / Security Verification
- NFR3: deep and many nested inputs are answered within 60 s with exit status 0 and empty standard error (TS-3).
- TM-1: every-level judgment of literal shell `-c` strings — checked by the TS-1 deny rows (three-level string and extglob example included) and the TS-7 order tests passing on both copies.
- TM-2: explicit work list and the 1,000,000-character re-read cap — checked by the TS-7 recursion-absence check, the TS-4 limit cases and the TS-3 time-bounded answers passing on both copies.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios (TS-1 to TS-8) | 8 | 8 | 0 | 0 |
| Manual checks | 2 | 0 | 0 | 2 |
| Performance / security items (NFR3, TM-1, TM-2) | 3 | 3 | 0 | 0 |
| Total | 13 | 11 | 0 | 2 |
