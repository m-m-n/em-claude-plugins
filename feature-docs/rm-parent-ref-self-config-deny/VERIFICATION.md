# Verification Document: rm-parent-ref-self-config-deny

## Overview
**Feature**: rm-parent-ref-self-config-deny / **SPEC.md**: `feature-docs/rm-parent-ref-self-config-deny/SPEC.md` / **IMPLEMENTATION.md**: not written (reduced tier; no file is declared by more than one task) / **THREAT-MODEL.md**: `feature-docs/rm-parent-ref-self-config-deny/THREAT-MODEL.md`

## Build Verification
- Command: none (workflow.yaml `build_command` is empty; the component is Python run directly)
- Expected: not applicable

## Test Verification
- Command: `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests`
- Expected: exit code 0; every case of the case table passes on decision and, where `rule` is set, on reason ID; every unittest passes
- Coverage target: not measured (no coverage tool is configured); completeness is judged by every scenario below having a passing test

### Test Scenarios from SPEC.md
TS-1 to TS-11 come from SPEC.md. TS-12 is added at create-plan for the anchor rule of the folded form (the leading `~` / `$HOME` segment consumed by a `..`).

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | `rm -rf ~/.claude/skills/../../valuable`, no `CLAUDE_BATCH` | deny / rm-recursive | Integration (case table, rule-tagged) |
| TS-2 | `rm -rf ~/.claude/skills/foo ~/.claude/skills/../../valuable`, no `CLAUDE_BATCH` | deny / rm-recursive | Integration (case table, rule-tagged) |
| TS-3 | the TS-2 command with `batch: true` | deny / rm-recursive | Integration (case table, rule-tagged) |
| TS-4 | `rm -rf ~/.claude/skills/../hooks/x` (folded form stays inside the protected area) | ask / self-modification | Integration (case table, rule-tagged) |
| TS-5 | `rm -rf /home/user/.claude/skills/../../valuable` | deny / rm-recursive | Integration (case table, rule-tagged) |
| TS-6 | hook run in a subprocess with HOME outside /home and `CLAUDE_BATCH` unset: `rm -rf ~/.claude/skills/foo` and `rm -rf ~/.claude/skills/../../valuable` | ask / self-modification for the first; deny / rm-recursive for the second | Unit (`tests/` unittest) |
| TS-7 | `$(printf rm) -rf ~/.claude/skills/foo ~/.claude/skills/../../valuable` (command-substitution-led path) | the changed hook's actual decision and reason ID, pinned (expected deny / rm-recursive) | Integration (case table, rule-tagged) |
| TS-8 | `rm ~/.claude/skills/../../valuable` (not recursive) | ask / self-modification (unchanged) | Integration (case table, rule-tagged) |
| TS-9 | `rm -rf ~/.claude/skills/..` | deny / rm-recursive (was ask) | Integration (case table, rule-tagged) |
| TS-10 | `rm -rf ~/.claude/skills/../../../../tmp/x` (folds into a safe deletion area) | ask / self-modification (unchanged) | Integration (case table, rule-tagged) |
| TS-11 | `rm -rf ~/.claude/skills/foo/..` (folded form still protected) | same decision and reason ID as at the base commit (expected ask / self-modification) | Integration (case table, rule-tagged) |
| TS-12 | same subprocess setup as TS-6 (HOME outside /home, last segment not a literal `~`): `rm -rf ~/.claude/skills/../../../~/.claude/hooks/x` | deny / rm-recursive (was ask) | Unit (`tests/` unittest, same module as TS-6) |

## Code Quality Verification
- Format: none configured (workflow.yaml `format_command` is empty) / Static analysis: none configured

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | `rm -rf ~/.claude/skills/foo ~/.claude/skills/../../valuable` without `CLAUDE_BATCH` is deny / rm-recursive | TS-2 passes |
| AC2 | `rm -rf ~/.claude/skills/../../valuable` alone is deny / rm-recursive | TS-1 passes |
| AC3 | the AC1 form with `CLAUDE_BATCH` is deny / rm-recursive | TS-3 passes |
| AC4 | `rm -rf ~/.claude/skills/foo` and the previous feature's cases (mixed-rm-self-config-deny TS-1 to TS-15) keep their decision and reason ID | full case-table run passes; the diff of the case table only appends after the previous last case |
| AC5 | with HOME outside /home, `rm -rf ~/.claude/skills/foo` stays ask / self-modification and `rm -rf ~/.claude/skills/../../valuable` is deny / rm-recursive | TS-6 passes |
| AC6 | both test commands pass in full | the Test Verification command exits 0 |
| NFR4 | the plugin's version fields are not changed | the diff between the base commit and the integration tip lists neither `em-workflow/.claude-plugin/plugin.json` nor `.claude-plugin/marketplace.json` |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2, TS-3, TS-4, TS-5, TS-9, TS-11, TS-12 |
| FR2 | task0001 | TS-4, TS-6, TS-11, TS-12 |
| FR3 | task0001 | TS-2 (plain path), TS-7 (command-substitution-led path); manual check of the call sites |
| FR4 | task0001 | manual check of the docstring (no scenario) |
| FR5 | task0001 | TS-1 and TS-2 present at the end of the case table with `rule` and the label prefix |
| NFR1 | task0001 | TS-4, TS-8, TS-10, TS-11 unchanged; full case-table run passes with no existing case edited |
| NFR2 | task0001 | TS-6 and TS-12 (placeholder HOME that need not exist); manual check that the folded form is lexical only |
| NFR3 | task0001 | every case-table scenario (TS-1 to TS-5, TS-7 to TS-11) completes within GUARD_TIMEOUT_SECONDS |
| NFR4 | task0001 | diff check in Success Criteria (no scenario) |

## Manual Testing (E2E Not Possible)
- [ ] FR3: both callers of `rm_protected_operand_numbers()` (the plain rm path and the command-substitution-led path) call the same function, and the new rule exists only inside it.
- [ ] FR4: the function's docstring no longer says it matches the raw or normalized form like `check_self_modification()`, and states that a raw-form match counts only when the `..`-folded form (`~` / `$HOME` not expanded) also matches, that the folded form does not match once a `..` consumes the leading `~` / `$HOME` anchor, and that a `normalize_candidate()` match counts as before.
- [ ] NFR2: the folded form is computed from the operand string alone; the change adds no filesystem query.

## Performance / Security Verification (if applicable)
- NFR3: no case exceeds GUARD_TIMEOUT_SECONDS (10 s) — the full case-table run passes, and the change adds only a constant amount of lexical folding per operand inside the existing scan budget.
- TM-1: a raw self-config match counts only when the `..`-folded form also matches, the folded form stops matching once a `..` consumes the leading `~` / `$HOME` anchor, and this holds on both rm paths — TS-1, TS-2 and TS-5 (plain path), TS-7 (command-substitution-led path) and TS-12 (anchor rule, HOME outside /home) pass with deny / rm-recursive pinned, while TS-4 and TS-11 keep the self-modification ask for operands that stay inside the protected area.
- TM-2: the batch-mode decision for the escaping form carries reason ID rm-recursive — TS-3 passes with `batch: true` and `rule` rm-recursive.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios, case table (TS-1 to TS-5, TS-7 to TS-11) | 10 | 10 | 0 | 0 |
| Test scenarios, unittest (TS-6, TS-12) | 2 | 2 | 0 | 0 |
| Success criteria (AC1 to AC6, NFR4) | 7 | 7 | 0 | 0 |
| Manual checks (FR3, FR4, NFR2) | 3 | 0 | 0 | 3 |
| Performance (NFR3) | 1 | 1 | 0 | 0 |
| Security (TM-1, TM-2) | 2 | 2 | 0 | 0 |
