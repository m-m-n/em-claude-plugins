# Verification Document: mixed-rm-self-config-deny

## Overview
**Feature**: mixed-rm-self-config-deny / **SPEC.md**: `feature-docs/mixed-rm-self-config-deny/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/mixed-rm-self-config-deny/IMPLEMENTATION.md`

## Build Verification
- Command: none. Both components in workflow.yaml have an empty build command. The test commands below load the hook and fail on a syntax error.
- Expected: not applicable.

## Test Verification
- Command (component destructive-guard): `python3 em-workflow/hooks/tests/run-destructive-guard.py`
- Command (component main): `python3 -m unittest discover -s tests`
- Expected: both exit 0 with every case and every test passing.
- Coverage target: not measured; no coverage tool is configured. Every scenario below maps to a case or a test.

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | `rm -rf ~/.claude/skills/foo /home/user/valuable` | deny / rm-recursive | Integration (case table) |
| TS-2 | `rm -rf /home/user/valuable ~/.claude/skills/foo` | deny / rm-recursive | Integration (case table) |
| TS-3 | TS-1's command with CLAUDE_BATCH set | deny / rm-recursive | Integration (case table) |
| TS-4 | `rm -rf ~/.claude/skills/foo ~` | deny / rm-root | Integration (case table) |
| TS-5 | `rm -rf ~/.claude/skills/foo tmp/$X` | ask / self-modification | Integration (case table) |
| TS-6 | `rm -rf ~/.claude/skills/foo /tmp/x` | ask / self-modification | Integration (case table) |
| TS-7 | `rm -rf ~/.claude/skills/foo ~/.claude/hooks/bar` | ask / self-modification | Integration (case table) |
| TS-8 | `rm ~/.claude/skills/foo /home/user/valuable` (not recursive) | ask / self-modification | Integration (case table) |
| TS-9 | `rm -rf $HOME/.claude/skills/foo /home/user/valuable` | deny / rm-recursive | Integration (case table) |
| TS-10 | `rm -rf -- ~/.claude/skills/foo /home/user/valuable` | deny / rm-recursive | Integration (case table) |
| TS-11 | `rm -rf ~/.claude/skills/foo /home/user/valuable ; git commit --amend` | deny / rm-recursive | Integration (case table) |
| TS-12 | Reason text of AC1 to AC3 through the subprocess output | The reason for TS-1's command names "1番目のrmの2番目の対象", does not name "1番目のrmの1番目の対象", and carries no self-modification text and no demotion sentence. It is byte-identical with and without CLAUDE_BATCH. The reason for TS-2's command names "1番目のrmの1番目の対象" | Unit |
| TS-13 | Substitution-headed route `$(printf rm) -rf ~/.claude/skills/foo /home/user/valuable` | Decision, reason id and reason text equal the pinned actual output | Unit |
| TS-14 | The same protected path written twice: `rm -rf ~/.claude/skills/foo ~/.claude/skills/foo` | ask / self-modification (both occurrences left out) | Integration (case table) |
| TS-15 | Only the redirect target is protected: `rm -rf /home/user/valuable > ~/.claude/settings.json` (old feature's TS-20) | deny / rm-recursive (nothing left out) | Integration (case table) |

TS-16 to TS-19 are verification scenarios that this document adds; SPEC.md has no such IDs.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-16 | The hook's descriptions (FR4) | The protected-operand function returns a set of operand numbers. The exclusion comment in the loop and the comment block above the `strongest_rm_decision(` call describe the target as the unit. That block keeps "held ask", "resolution step", "self-modification" and "left out", and no stale phrase returns | Unit (description tests) |
| TS-17 | Case table integrity and full run (FR5, NFR1, NFR4) | The old TS-15 case is deny with rule rm-recursive, at its old position, and its label still begins with "destructive-guard-mixed-rm-precedence TS-15". Every other existing case is byte-identical, lines 31 and 42 included. This feature's cases are appended, rule-pinned and labelled "mixed-rm-self-config-deny TS-". The runner passes every case within GUARD_TIMEOUT_SECONDS | Integration + git diff |
| TS-18 | Documents (FR7, FR8) | In the destructive-guard-mixed-rm-precedence SPEC.md, the known-impact sentence of FR8, the third sentence of AC9 and the TS-15 line give deny / rm-recursive for `rm -rf ~/.claude/skills/foo /home/user/valuable`; that feature's REQUIREMENTS.md and VERIFICATION.md are unchanged. The precedence bullet in `.claude/rules/hook-tests.md` states the per-target exclusion, and `tests/test_hook_tests_rule_key_doc.py` passes | Unit (rule document) + Manual (git diff) |
| TS-19 | Plugin manifests (NFR5) | The integrated diff changes neither `em-workflow/.claude-plugin/plugin.json` nor `.claude-plugin/marketplace.json` | Manual (git diff) |

## Code Quality Verification
- Format: none configured (the format command is empty for both components).
- Static analysis: none configured.

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | TS-1's command gives deny / rm-recursive and its reason names the second target only | TS-1, TS-12 |
| AC2 | The reversed order gives deny / rm-recursive, naming the first target | TS-2, TS-12 |
| AC3 | With CLAUDE_BATCH, AC1's command gives deny / rm-recursive with the same reason text | TS-3, TS-12 |
| AC4 | `rm -rf ~/.claude/skills/foo ~` gives deny / rm-root | TS-4 |
| AC5 | The five forms without a deny stay ask / self-modification | TS-5, TS-6, TS-7, TS-8; the existing case at line 42 |
| AC6 | The spellings `~/`, `$HOME/` and after `--` give deny / rm-recursive | TS-1, TS-9, TS-10 |
| AC7 | The old TS-12, TS-13, TS-14, TS-16 and TS-20 cases and lines 42 and 31 keep their decisions and reason ids | TS-17 (runner pass + git diff of the case table) |
| AC8 | Both test commands pass in full | Test Verification commands |
| AC9 | The old SPEC.md's FR8, AC9 and TS-15 and the hook-tests.md precedence bullet describe the new behavior; the old REQUIREMENTS.md and VERIFICATION.md are unchanged | TS-18 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2, TS-10, TS-11, TS-13, TS-14 |
| FR2 | task0001 | TS-7, TS-9, TS-10, TS-14 |
| FR3 | task0001 | TS-1, TS-2, TS-3, TS-4, TS-5, TS-6, TS-7, TS-8, TS-12, TS-15 |
| FR4 | task0001 | TS-16 |
| FR5 | task0001 | TS-17 |
| FR6 | task0001 | TS-12, TS-13 |
| FR7 | none (amended by the planner during create-plan) | TS-18 |
| FR8 | task0002 | TS-18 |
| NFR1 | task0001 | TS-15, TS-17 |
| NFR2 | task0001 | TS-5, TS-6, TS-7, TS-8 |
| NFR3 | task0001 | TS-3, TS-12 |
| NFR4 | task0001 | TS-17 |
| NFR5 | task0001 | TS-19 |

## Manual Testing (E2E Not Possible)
- [ ] TS-18, other-feature part: read the three amended statements of `feature-docs/destructive-guard-mixed-rm-precedence/SPEC.md` (the known-impact sentence of FR8, the third sentence of AC9, the TS-15 line) and confirm the git diff of that feature's directory touches nothing else, REQUIREMENTS.md and VERIFICATION.md included.
- [ ] TS-17, diff part: in the git diff of `em-workflow/hooks/tests/destructive-guard-cases.json`, the only changed existing line is the old TS-15 case, and every other change is an appended case.
- [ ] TS-19: the integrated diff contains no change to the plugin manifest or the marketplace file.

## Performance / Security Verification
- NFR4: each case finishes within GUARD_TIMEOUT_SECONDS (10 seconds). The runner stops a case past that limit and counts it as a FAIL, so a full pass of `python3 em-workflow/hooks/tests/run-destructive-guard.py` (TS-17) checks it.
- NFR1: no existing case expectation moves from deny to ask or allow; the only changed expectation is the old TS-15, from ask to deny (TS-17 diff part).
- TM-1: per-target exclusion. The records of the other targets of the same rm join the pool, and their deny wins before any demotion, with a reason built from the winning targets alone. Checked by TS-1, TS-2, TS-3, TS-4, TS-9, TS-10 and TS-11 (deny with the rm reason id) and TS-12 (reason text, identical with and without CLAUDE_BATCH).
- TM-2: the protected set uses the operand basis and numbering of `check_rm()` on both routes. Checked by TS-10 (the `--` rule), TS-14 (a repeated protected operand), TS-13 (the substitution-headed remainder) and TS-2 (order).

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Case-table scenarios (TS-1 to TS-11, TS-14, TS-15) | 13 | 13 | 0 | 0 |
| Unit scenarios (TS-12, TS-13, TS-16) | 3 | 3 | 0 | 0 |
| Case table integrity (TS-17) | 2 | 1 | 0 | 1 |
| Documents (TS-18) | 2 | 1 | 0 | 1 |
| Plugin manifests (TS-19) | 1 | 0 | 0 | 1 |
| Performance (NFR4) | 1 | 1 | 0 | 0 |
| Security (TM-1, TM-2) | 2 | 2 | 0 | 0 |
| Total | 24 | 21 | 0 | 3 |
