# Verification Document: destructive-guard-heredoc-sink-gaps

## Overview
**Feature**: destructive-guard-heredoc-sink-gaps / **SPEC.md**: `feature-docs/destructive-guard-heredoc-sink-gaps/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/destructive-guard-heredoc-sink-gaps/IMPLEMENTATION.md`

## Build Verification
- Command: none (`build_command` is empty; Python, no build step)
- Expected: not applicable

## Test Verification
- Command: `python3 -m unittest discover -s tests` (test_command)
- Command: `python3 em-workflow/hooks/tests/run-destructive-guard.py` (e2e_test_command; the case-table suite)
- Expected: both exit 0
- Coverage target: not applicable. The suite is a case table, so no coverage tool is configured. Every case added by this feature must PASS.

"Base guard" below means the copy of `em-workflow/hooks/destructive-guard.py`
at `workflow.implement.base_commit`, placed outside the repository and
passed to the runner's guard-path argument. "Base case file" means
`em-workflow/hooks/tests/destructive-guard-cases.json` at the same commit.
`<対象>` is a target the guard denies when the destructive command is written
on its own.

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | The eleven REQUIREMENTS.md 11.1 AC-1 forms (cdb8382d4bbb0b1d) as deny cases | each PASS (deny) | Unit (case table) |
| TS-2 | The REQUIREMENTS.md 11.1 AC-2 form as an allow case | PASS (allow) | Unit (case table) |
| TS-3 | The three REQUIREMENTS.md 11.1 AC-3 forms (73a1d7b31734dd22) as deny cases | each PASS (deny) | Unit (case table) |
| TS-4 | The ~60KB command: `echo '`, then `$(` 30000 times, then `' ; rm -rf <対象>` (26ab9a3d83649eff) | PASS (deny) within the 10-second limit in every evaluation | Unit (case table, performance) |
| TS-5 | The four REQUIREMENTS.md 11.1 AC-5 forms (18b99bd71e74c8dc) as deny cases | each PASS (deny) | Unit (case table) |
| TS-6 | The REQUIREMENTS.md 11.1 AC-6 form as an allow case | PASS (allow) | Unit (case table) |
| TS-7 | The five REQUIREMENTS.md 11.1 AC-7 forms (511cd470522973d8) as deny cases | each PASS (deny) | Unit (case table) |
| TS-8 | The five REQUIREMENTS.md 11.1 AC-8 forms (b8fd289ca7750a04) as deny cases | each PASS (deny) | Unit (case table) |
| TS-9 | The three 46923ffe262f20b1 forms from SPEC.md TS-9 as deny cases | each PASS (deny) | Unit (case table) |
| TS-10 | Full runner run on the integrated tree | every case PASSes and the runner exits 0. Includes the existing cases named in SPEC.md Edge Cases (4, 36, 416-419, 428, 434, 435, 455, 456, 457, 468, 469) at their existing verdicts | Integration |
| TS-11 | FR8 red check: the integrated runner and case file run against the base guard | for each of the six findings, at least one added reproduction case FAILs. The report lists every added deny case that already PASSes against the base guard | Integration (scripted) |
| TS-12 | FR9 preservation: compare the base case file with the integrated one | the base array is an exact prefix of the integrated array, so every pre-existing entry is unchanged in verdict, label and command | Integration (scripted) |
| TS-13 | FR10 runner behavior, from the TS-11 run | the TS-4 case is reported as FAIL with a timeout marker, and each of its evaluations stops after about 10 seconds. The runner evaluates every remaining case, prints its summary, and ends without a traceback | Integration (scripted) |
| TS-14 | NFR3 scaling: time the integrated guard directly on (a) the TS-4 shape with 30000 and with 60000 repetitions, and (b) a ~60KB command and a ~120KB command made by repeating the TS-1, TS-3, TS-5, TS-7 and TS-8 shapes | the larger input takes less than 3 times as long as the smaller one, in both (a) and (b). Every run finishes within 10 seconds | Performance (scripted) |
| TS-15 | FR5 cross-line edges (task0003 AC-4), each followed by a destructive line: real heredocs with single- and double-quoted delimiters; a comment holding an unpaired quote; a real heredoc body holding an unpaired quote | each PASS (deny) | Unit (case table) |
| TS-16 | FR6 variants (task0004 AC-2): env split-string spellings not in TS-7 (separate, attached, `=`-joined, inside a short-option cluster); a quoted sink as an assignment value and as a git global option value; a sink as a skipped wrapper option value | each PASS (deny) | Unit (case table) |
| TS-17 | FR7 constructs not in TS-8 (task0004 AC-5): `function NAME` with and without `()`, a brace-body definition, `enable`, a standalone PATH assignment, `export` with PATH. Also the allow case of task0004 AC-3: a script written through a data heredoc whose body defines a function | constructs PASS (deny); the script-writing case PASSes (allow) | Unit (case table) |
| TS-18 | NFR1, NFR2, NFR4 static review of the base..integrated diff | outside `feature-docs/` and `test-docs/`, only the three files in NFR4 change. hooks.json and both plugin version fields are unchanged. No import outside the Python standard library is added. No added guard code accesses the file system or evaluates commands or substitutions | Manual |

## Code Quality Verification
- Format: none configured (`format_command` is empty)
- Static analysis: none configured

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | All functional requirements are implemented and tested | Functional Requirements Coverage below; TS-1 to TS-17 pass |
| SC-2 | All test scenarios pass | TS-1 to TS-18 |
| SC-3 | Performance meets the specified goals | TS-4, TS-13, TS-14 |
| SC-4 | Security requirements are satisfied | Performance / Security Verification below (TM-1 to TM-7); TS-18 |
| SC-5 | REQUIREMENTS.md 11.1 AC-1 to AC-9 are all met | AC-1: TS-1. AC-2: TS-2. AC-3: TS-3. AC-4: TS-4, TS-13. AC-5: TS-5. AC-6: TS-6. AC-7: TS-7. AC-8: TS-8. AC-9: TS-10, TS-12 |
| SC-6 | Documentation is complete; code review is completed | Review phase result; no further documents are required by SPEC.md |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0002 | TS-1, TS-2 |
| FR2 | task0002 | TS-1, TS-3 |
| FR3 | task0002 | TS-3 |
| FR4 | task0001 | TS-4, TS-9, TS-14 |
| FR5 | task0003 | TS-5, TS-6, TS-15 |
| FR6 | task0004 | TS-7, TS-16 |
| FR7 | task0004 | TS-8, TS-17 |
| FR8 | task0001, task0002, task0003, task0004 | TS-1, TS-2, TS-3, TS-4, TS-5, TS-6, TS-7, TS-8, TS-11 |
| FR9 | task0001, task0002, task0003, task0004 | TS-9, TS-10, TS-12 |
| FR10 | task0001 | TS-4, TS-10, TS-13 |
| NFR1 | task0001, task0002, task0003, task0004 | TS-18 |
| NFR2 | task0001, task0002, task0003, task0004 | TS-18 |
| NFR3 | task0001, task0002, task0003, task0004 | TS-4, TS-10, TS-14 |
| NFR4 | task0001, task0002, task0003, task0004 | TS-18 |

## E2E Testing
- [ ] `python3 em-workflow/hooks/tests/run-destructive-guard.py` (e2e_test_command) passes. This is the same run as TS-10.

## Manual Testing (E2E Not Possible)
- [ ] TS-18: static review of the diff for NFR1, NFR2 and NFR4.

## Performance / Security Verification (if applicable)
- NFR3: every runner evaluation finishes within 10 seconds (TS-10, TS-13), and the scaling ratio stays below 3 (TS-14).
- TM-1: the host statement is taken from lex_segments(), and a host statement without its own operator yields undetermined. Checked by TS-1 PASS; the own-operator contribution is recorded under task0002 AC-4.
- TM-2: escaped quotes are not quote starts in scan_structure(). Checked by TS-3 PASS.
- TM-3: fake heredoc operators capture no body, and cross-line state skips real bodies. Checked by TS-5, TS-6 and TS-15 PASS.
- TM-4: skipped-word sinks and env split-string yield undetermined. Checked by TS-7 and TS-16 PASS.
- TM-5: override constructs make the command's data judgments undetermined. Checked by TS-8 and the deny part of TS-17 PASS.
- TM-6: single-quoted `$(` matching is linear, and the runner bounds every evaluation. Checked by TS-4 PASS, TS-13 and TS-14.
- TM-7: no legitimate command is newly blocked. Checked by TS-2, TS-6, the allow part of TS-17, TS-10 (all pre-existing allow cases) and TS-12.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (case table) | 13 (TS-1 to TS-9, TS-15 to TS-17, plus TS-10) | 13 | 1 (TS-10) | 0 |
| Scripted integration / performance | 4 (TS-11 to TS-14) | 4 | 0 | 0 |
| Static review | 1 (TS-18) | 0 | 0 | 1 |
| Security / performance items | 8 (NFR3, TM-1 to TM-7) | 8 | 0 | 0 |
| Total scenario IDs | 18 | 17 | 1 | 1 |
