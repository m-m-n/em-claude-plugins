# Verification Document: rm-home-parent-ref-recursive-deny

## Overview
**Feature**: rm-home-parent-ref-recursive-deny / **SPEC.md**: `feature-docs/rm-home-parent-ref-recursive-deny/SPEC.md` / **IMPLEMENTATION.md**: not written (reduced tier, one task, no file shared between tasks) / **THREAT-MODEL.md**: `feature-docs/rm-home-parent-ref-recursive-deny/THREAT-MODEL.md`

## Build Verification
- Command: none. `project.components.main.build_command` is empty, and the Python scripts are not built.
- Expected: not applicable.

## Test Verification
- Command: `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests`
- Expected: exit code 0. The runner prints no FAIL and no TIMEOUT line, and unittest reports OK.
- Coverage target: not measured (no coverage tool is configured). Every scenario below has an automated check.

### Test Scenarios from SPEC.md

TS-1 to TS-15 are SPEC.md's scenarios. Each is a case in
`em-workflow/hooks/tests/destructive-guard-cases.json` that fixes the decision
and the reason ID, and runs without `CLAUDE_BATCH` unless the row says
otherwise. TS-16 to TS-20 are derived from SPEC.md's Acceptance Criteria
(AC6, AC7), FR3, FR4 and NFR1 to NFR4.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | `rm -rf "$HOME/.claude/skills/../../valuable"` | ask / rm-unresolvable; the reason text equals that of the same rm with an unprotected operand that has an expansion | Unit (case table, unittest) |
| TS-2 | `rm -rf $HOME/.claude/skills/../../valuable` (unquoted) | ask / rm-unresolvable | Unit (case table) |
| TS-3 | `rm -rf $HOME/.claude/skills/foo "$HOME/.claude/skills/../../valuable"` (the first operand is genuinely protected) | ask / rm-unresolvable | Unit (case table) |
| TS-4 | TS-1 with `CLAUDE_BATCH` | deny / rm-unresolvable | Unit (case table) |
| TS-5 | TS-3 with `CLAUDE_BATCH` | deny / rm-unresolvable | Unit (case table) |
| TS-6 | `$(printf rm) -rf $HOME/.claude/skills/foo "$HOME/.claude/skills/../../valuable"` (substitution-headed path) | ask / rm-unresolvable | Unit (case table) |
| TS-7 | `rm -rf "$HOME/.claude/skills/../../valuable" > ~/.claude/settings.json` (the same statement also has a self-modification caused by a redirection) | ask / rm-unresolvable | Unit (case table) |
| TS-8 | `rm -rf "${HOME}/.claude/skills/../../valuable"` (no self-modification ask; the rule does not apply) | ask / rm-unresolvable | Unit (case table) |
| TS-9 | `HOME=/tmp/x; rm -rf "$HOME/.claude/skills/../../valuable"`, without and with `CLAUDE_BATCH` | ask / rm-unresolvable; deny / rm-unresolvable | Unit (case table, two cases) |
| TS-10 | `rm "$HOME/.claude/skills/../../valuable"` (not recursive; no rm record) | ask / self-modification | Unit (case table) |
| TS-11 | `rm -rf "$HOME/.claude/skills/../hooks/x"` (stays inside the protected area after folding) | ask / self-modification | Unit (case table) |
| TS-12 | `rm -rf "$HOME/.claude/skills/../../../../tmp/x"` (`$HOME` unresolved, so it is unresolvable before the safe-area exception) | ask / rm-unresolvable | Unit (case table) |
| TS-13 | `rm -rf $HOME/.claude/skills/foo /home/user/valuable "$HOME/.claude/skills/../../valuable"` (the rm deny keeps top priority) | deny / rm-recursive | Unit (case table) |
| TS-14 | `rm -rf tmp/$X > ~/.claude/settings.json` (self-modification from a redirection only; no qualifying operand) | ask / self-modification | Unit (case table) |
| TS-15 | `rm -rf ~/.claude/skills/../../$X` (`~` spelling with an expansion that leaves the protected area) | ask / rm-unresolvable | Unit (case table) |
| TS-16 | Full case table: every earlier case keeps its decision and reason ID and stays byte-identical in place; this feature's 16 cases form one unbroken run after them; every case finishes within the runner's 10-second bound (AC6, AC7, FR5, NFR1, NFR3) | runner exit 0, no FAIL, no TIMEOUT; unittest OK | Integration (runner, unittest) |
| TS-17 | Documentation: the precedence list of `.claude/rules/hook-tests.md` gains exactly the FR4 bullet and keeps every existing bullet; main()'s selection-order and exclusion comments state the exception; the existing comment and rule-document tests pass (FR4) | unittest OK | Unit (unittest) |
| TS-18 | An ask held earlier by another statement keeps its rank: `git commit --amend ; rm -rf "$HOME/.claude/skills/../../valuable"` and `echo x > ~/.claude/settings.json ; rm -rf "$HOME/.claude/skills/../../valuable"` (FR1) | ask / git-amend; ask / self-modification | Unit (unittest) |
| TS-19 | check_rm(), check_self_modification(), rm_protected_operand_numbers(), fold_parent_refs(), normalize_candidate() and decide() are unchanged from the base; the hook's output for each TS-1 to TS-15 command is byte-identical across two runs (FR3, NFR2) | no changed line in those functions; identical output | Diff check, Unit (unittest) |
| TS-20 | Neither `em-workflow/.claude-plugin/plugin.json` nor `.claude-plugin/marketplace.json` is in the feature's change set against `main` (NFR4) | neither path is listed | Diff check |

## Code Quality Verification
- Format: none configured (`project.components.main.format_command` is empty).
- Static analysis: none configured.

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | All functional requirements are implemented and tested | Functional Requirements Coverage below; every listed scenario passes |
| SC-2 | All test scenarios pass | Test command above (TS-1 to TS-20) |
| SC-3 | `python3 em-workflow/hooks/tests/run-destructive-guard.py` passes in full | TS-16 |
| SC-4 | `python3 -m unittest discover -s tests` passes in full | Test command above |
| SC-5 | Existing cases keep their decision and reason ID (AC6) | TS-16, plus TS-10, TS-11, TS-13 and TS-14 |
| AC1 | The TS-1 / TS-2 forms are ask / rm-unresolvable | TS-1, TS-2 |
| AC2 | The form beside a genuinely protected operand is ask / rm-unresolvable | TS-3 |
| AC3 | The substitution-headed form is ask / rm-unresolvable | TS-6 |
| AC4 | The AC1 and AC2 forms with `CLAUDE_BATCH` are deny / rm-unresolvable | TS-4, TS-5 |
| AC5 | `${HOME}` and the `HOME` reassignment form decide as stated | TS-8, TS-9 |
| AC6 | Existing fixed cases keep their decision and reason ID | TS-16 |
| AC7 | Both test commands pass in full | Test command above |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2, TS-3, TS-4, TS-5, TS-7, TS-9, TS-12, TS-15, TS-18 |
| FR2 | task0001 | TS-1 (plain path), TS-6 (substitution-headed path) |
| FR3 | task0001 | TS-8, TS-9, TS-12, TS-19 |
| FR4 | task0001 | TS-17 |
| FR5 | task0001 | TS-1 to TS-15 (each is a case of the run) |
| NFR1 | task0001 | TS-10, TS-11, TS-13, TS-14, TS-16 |
| NFR2 | task0001 | TS-19 |
| NFR3 | task0001 | TS-16 |
| NFR4 | task0001 | TS-20 |

## Manual Testing (E2E Not Possible)
- None. Every scenario is decided by the hook's output or by a diff, and is checked automatically.

## Performance / Security Verification
- NFR3: no case exceeds `GUARD_TIMEOUT_SECONDS` (10 seconds). The runner reports a TIMEOUT line for any case past the bound (TS-16).
- TM-1: in a statement with a qualifying operand, the rm ask (`rm-unresolvable`) replaces that statement's self-modification ask on both paths, and `CLAUDE_BATCH` demotes it to deny with the same reason ID. Checked by TS-1 to TS-7, TS-9, TS-12 and TS-15, and by TS-1's reason-text equality.
- TM-2: the exception never outranks the rm deny, never reorders asks of other statements, and leaves `$HOME` unresolved. Checked by TS-8, TS-9, TS-10, TS-11, TS-13, TS-14, TS-16, TS-18 and TS-19.
- TM-3: the added check reuses the statement's existing records and protected set, with linear work and no file-system access. Checked by TS-16 (every case within the 10-second bound) and by reading the added check in the diff.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios | 20 | 20 | 0 | 0 |
| Success criteria | 12 | 12 | 0 | 0 |
| Performance (NFR3) | 1 | 1 | 0 | 0 |
| Security (TM-1 to TM-3) | 3 | 3 | 0 | 0 |
