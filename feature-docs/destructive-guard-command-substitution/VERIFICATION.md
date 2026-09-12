# Verification Document: destructive-guard-command-substitution

## Overview

**Feature**: destructive-guard-command-substitution /
**SPEC.md**: `feature-docs/destructive-guard-command-substitution/SPEC.md` /
**IMPLEMENTATION.md**: `feature-docs/destructive-guard-command-substitution/IMPLEMENTATION.md`

This document covers the INTEGRATED verification of the merged feature. Each
task's own Acceptance Criteria live in its task plan and are verified inside
the task.

## Build Verification

- Command: none — every component in `workflow.yaml` `project.components`
  declares an empty `build_command`; the deliverables are Python scripts and
  JSON manifests executed in place.
- Expected: not applicable.

## Test Verification

- Command (component `main`): `python3 -m unittest discover -s tests`
- Command (component `guard_cases`):
  `python3 em-workflow/hooks/tests/run-destructive-guard.py`
- Command (component `invariants`):
  `python3 em-workflow/scripts/check-plugin-invariants.py .`
- Expected: exit code 0 from each; the case-table runner reports every case
  passing, including the trailing unattended-demotion case.
- Coverage target: the project carries no coverage instrumentation and no
  coverage threshold. Coverage is judged instead by the requirement-to-scenario
  mapping below: every FR/NFR must be reachable from at least one scenario
  that actually runs.

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Case-table driven run of the guard over every entry of `em-workflow/hooks/tests/destructive-guard-cases.json` | Every case matches its expected verdict; the new substitution-only entries in both spellings are present; no pre-existing command string was dropped | Integration |
| TS-2 | Repository-root unit discovery over `tests/`, driving hooks through the subprocess/stdin contract and parsing manifests as JSON | Exit 0; both new modules discovered and green | Unit |
| TS-3 | Recursive delete whose target is a NESTED command substitution | Verdict `deny`; never `allow` | Integration |
| TS-4 | A substitution sitting in a redirect destination rather than a delete-target position | Not counted as a delete target; verdict `allow` | Integration |
| TS-5 | Multiple delete targets: a safe target plus a substitution target, and a dangerous literal path plus a substitution target | The strongest tier is selected in each case (`ask`, then `deny`) | Integration |
| TS-6 | A delete WITHOUT a recursive flag whose target is a substitution | Verdict unchanged from before the feature | Integration |
| TS-7 | A substitution adjacent to real text inside double quotes | Existing `deny` preserved | Integration |
| TS-8 | A delete whose substitution sits inside a `-c` / eval / here-string payload | Reaches the same verdict as the same delete written directly | Integration |
| TS-9 | Parse-failure fallback: a command with unbalanced quoting containing a substitution | No exception; exit 0; fail-open behaviour intact | Unit |
| TS-10 | Regression over the whole `allow` half of the case table (quoted delete string, here-doc body, commit message, `python3 -c`, redirect to the bit bucket, delete under a safe root) | Every one stays `allow` | Integration |
| TS-11 | A recursive delete whose target mixes a path under a scratch root with a command substitution at a quote boundary | Verdict pinned in the case table and unchanged from the merged tree; the reason text makes no claim about the target's position relative to a safe root, states that part of the target comes from a command substitution, and closes with an instruction actionable for that input | Integration + Unit |

## Code Quality Verification

- Format: none — every component declares an empty `format_command`; the
  project runs no formatter.
- Static analysis: no linter is configured. The structural check that stands in
  for it is `python3 em-workflow/scripts/check-plugin-invariants.py .`, which
  must exit 0.
- Manual code-quality gate: the review phase (the guard is a security
  boundary; see the review floor derived from the tasks' domains).

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | All functional requirements FR1-FR8 implemented and tested | The coverage table below has a task and at least one scenario for every ID |
| SC-2 | All test scenarios TS-1 - TS-11 pass | Run the three component commands above; TS-3 … TS-8, TS-10 and the case-table half of TS-11 are entries of the case table exercised by TS-1 |
| SC-3 | `python3 em-workflow/hooks/tests/run-destructive-guard.py` passes in full, including the unattended-demotion case | Command exits 0 and its final line reports every case passing |
| SC-4 | `python3 -m unittest discover -s tests` passes | Command exits 0 |
| SC-5 | Non-functional requirements NFR1-NFR7 satisfied | The coverage table below |
| SC-6 | Both version fields raised to the same value | The version-bump module under TS-2, plus the repository-wide parity check and the invariants script |
| SC-7 | Code review completed | The review phase reaches its exit condition |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001, task0003 | TS-1 (both spellings as case-table entries), TS-2 (reason-text and demotion assertions), TS-3, TS-8 (task0003: the payload evidence now carries a substitution) |
| FR2 | task0001, task0003 | TS-1 (verdict tier), TS-2 (rule id in the reason prefix), TS-5, TS-8 (payload form reaches the same rule id as the direct form) |
| FR3 | task0001, task0003 | TS-1, TS-2 (rendered target is non-empty, not whitespace, identical across spellings), TS-11 (the flagged-target reason text asserts only what holds of its input) |
| FR4 | task0001 | TS-1 (quoted whole-word entry), TS-2 (its rendered target), TS-7 |
| FR5 | task0001, task0003 | TS-1, TS-3, TS-5, TS-6, TS-7, TS-10, TS-11 (the safe-root boundary forms pinned at their current verdict) |
| FR6 | task0001, task0003 | TS-2, TS-4, TS-6, TS-8, TS-9, TS-10 |
| FR7 | task0001, task0003 | TS-1 (the runner consumes the updated table; entry count and retained command strings checked there), TS-11 (case-table half) |
| FR8 | task0002 | TS-2 (the version-bump module, the repository-wide parity check), plus the invariants script |
| NFR1 | task0001, task0003 | TS-1, TS-2 (the same command re-run yields the identical verdict and reason text) |
| NFR2 | task0001, task0003 | TS-2 (source-level check that no filesystem-resolution, stat or subprocess call was introduced) |
| NFR3 | task0001, task0003 | TS-1 (the kilobyte-scale assignment entry completes; the shell-payload expansion cap is untouched by the ordering change) |
| NFR4 | task0001, task0003 | TS-1 (trailing unattended-demotion case), TS-2 (malformed payload fails open, exit 0), TS-9 |
| NFR5 | task0001, task0003 | TS-2 (the reason text keeps the Japanese style and the closing rewrite instruction), TS-11 (the instruction is actionable for the flagged input), plus the manual read below |
| NFR6 | task0001, task0003 | TS-2 (no NUL or other control character anywhere in the emitted output) |
| NFR7 | task0001, task0003 | TS-1 + TS-10 (every pre-existing `allow` entry retained and still `allow`), TS-11 (a verdict this feature moved is pinned rather than left unrecorded) |

## E2E Testing

Not applicable — the project declares no E2E framework and every component's
`e2e_test_command` is empty. The guard's own subprocess contract (JSON on
standard input, a decision on standard output) is exercised end to end by
TS-1 and TS-2.

## Manual Testing (E2E Not Possible)

- [ ] Read the reason text emitted for `rm -rf $(cat list)` as a human and
      confirm it says which delete target is the problem and what to write
      instead — the usability half of NFR5, which the automated assertions can
      only bound structurally.
- [ ] Confirm the completion report tells the user that a Claude Code restart
      is required before the bumped plugin version takes effect
      (`.claude/rules/core-plugin-version-bump.md`).

No mockup comparison applies: the design step is `skipped` and this feature
has no visual surface.

## Performance / Security Verification

- NFR3: satisfied structurally — the added work stays inside string scanning
  and introduces no loop growing non-linearly in input length; the existing cap
  on shell-payload re-expansion is unchanged. Evidenced by the kilobyte-scale
  case in TS-1 completing without timing out.
- Security (the feature's reason for existing): the attack scenario from the
  goal — a recursive delete whose target is assembled by a command
  substitution — must be non-`allow` in both spellings, in attended mode
  (`ask`) and unattended mode (`deny`). Verified by TS-1 and TS-2.
- Security (regression): no decision path gains filesystem access or process
  spawning (NFR2), and the internal sentinel never reaches output (NFR6).

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios (TS-1 - TS-11) | 11 | 11 | 0 | 0 |
| Success criteria (SC-1 - SC-7) | 7 | 5 | 0 | 2 (SC-7 review, plus the reason-text read) |
| Functional requirements (FR1 - FR8) | 8 | 8 | 0 | 0 |
| Non-functional requirements (NFR1 - NFR7) | 7 | 7 | 0 | 1 (NFR5 usability, in addition to its automated bound) |
