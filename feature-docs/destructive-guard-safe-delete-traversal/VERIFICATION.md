# Verification Document: destructive-guard SAFE_DELETE traversal fix

## Overview

**Feature**: destructive-guard-safe-delete-traversal /
**SPEC.md**: `feature-docs/destructive-guard-safe-delete-traversal/SPEC.md` /
**IMPLEMENTATION.md**: `feature-docs/destructive-guard-safe-delete-traversal/IMPLEMENTATION.md`

This document covers the INTEGRATED verification of the feature. Per-task
acceptance criteria live in `tasks/task0001.md` and `tasks/task0002.md`.

## Build Verification

- Command: none — `project.components.hooks.build_command` is empty (the hook is
  an interpreted script with no build step).
- Expected: n/a. The equivalent smoke check is that both changed JSON manifests
  and the changed Python script load without error, which the test command below
  exercises for the script and TS-9 covers for the manifests.

## Test Verification

- Command: `python3 em-workflow/hooks/tests/run-destructive-guard.py`
- Expected: exit code 0, and the final line reports every case passing
  (`N/N passed`, where N is the case count plus the trailing batch-demotion
  assertion).
- Coverage target: no coverage tool is configured for this component. The
  equivalent measure is case-table completeness: every scenario below is pinned
  by at least one case-table entry, and the count of entries after the change is
  greater than or equal to the count before it (entries are added, never
  removed).

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | (SPEC TS1) Path traversal through an absolute scratch root: recursive delete of `/tmp/../home/sakura/valuable` | `deny` with the recursive-delete reason id, the same reason id as the control `/home/sakura/valuable` | Unit |
| TS-2 | (SPEC TS2) Relative path traversal: recursive delete of `build/../src` | `deny` — normalization leaves a target outside every safe root | Unit |
| TS-3 | (SPEC TS3) Component boundary: recursive delete of `targets`, `build-debug`, `dist-ssr`, `target-old`, `coverage.old`, `build-artifacts`, `dist-newstyle`, `coverage-old`, `node_modules_bak` | `deny` for every one — a leading component that merely starts with a safe name is not a match | Unit |
| TS-4 | (SPEC TS4) Scratch root itself: recursive delete of `/tmp/`, `tmp/`, `.cache/`, `/var/tmp/` | `deny`, identical to the trailing-separator-free spellings, which stay `deny` | Unit |
| TS-5 | (SPEC TS5) Allow-side regression guard: recursive delete of `node_modules` with output discarded, `/tmp/x` with and without redirection, `./build`, `dist/*`, and the two entries whose only target is a command substitution leaving zero targets | `allow` for every one — no new false positive | Unit |
| TS-6 | (SPEC TS6) Deny/ask-side regression guard: the existing root/home entries, the unresolvable entries, and the three entries mixing a parent reference with a variable or a glob | Decisions unchanged from before the change | Unit |
| TS-7 | (SPEC TS7) Unresolved expansion under a safe root: recursive delete of a target placing a variable below a scratch root | `ask` with the unresolvable reason id — the safe exception is not reached | Unit |
| TS-8 | (SPEC TS8) Batch demotion: the runner's trailing assertion, which sets the batch variable | `deny` — `ask` is still demoted under unattended execution | Integration |
| TS-9 | Version consistency: the `em-workflow` version in `em-workflow/.claude-plugin/plugin.json` and in `.claude-plugin/marketplace.json` | Both read the identical raised value `0.1.73`; the `em-review` entry is unchanged; both files parse as JSON | Static |
| TS-10 | Determinism: the changed decision paths introduce no real-path resolution, file-status inspection or subprocess call, and two consecutive suite runs produce identical results | No such call present; identical output on both runs | Static + Integration |
| TS-11 | Self-description: the safe-root constant's comment states the two-class component rule, and the residual symlink-escape constraint is stated in the code | Both statements present in the changed file | Static |
| TS-12 | Substitution residue: recursive delete of a target where a command substitution is adjacent to other text and a parent reference follows it (`$(pwd)/../tmp/scratch`, a `printf`-substitution spelling with `/../../tmp/scratch`, and a backtick spelling of the same shape) | Never `allow` — `ask` or `deny`, with and without the batch environment variable; the counterpart whose only targets are command substitutions still decides `allow` | Unit |
| TS-13 | Unresolvable spellings judged before normalization: recursive delete of `"$@/../build"` after a positional-parameter assignment, of `$1/../build`, of `~+/../build`, `~-/../build` and `~someone/../build` | `ask` with the unresolvable reason id (`deny` under batch demotion); a bare `~` target and a `~/`-leading target keep their current decisions | Unit |
| TS-14 | Decision precedence: recursive delete of `tmp/$X` together with `/home/sakura/valuable`, the target-order-swapped spelling, and a compound command whose first segment is the ask form and whose later segment is destructive | `deny` for all three, with the reason text naming every contributing target; a command whose unresolvable target is its only target still decides `ask` | Unit |

## Code Quality Verification

- Format: none configured (`project.components.hooks.format_command` is empty).
  The equivalent check is that the diff keeps the surrounding file's existing
  style and that both JSON manifests retain their formatting and key order.
- Static analysis: none configured. The static items above (TS-9, TS-10, TS-11)
  are performed by reading the diff.

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | All functional requirements FR1-FR10 are implemented | Requirement coverage table below; every row has at least one task and one scenario |
| SC-2 | All test scenarios TS-1 to TS-8 pass | One suite run reports every case passing |
| SC-3 | `python3 em-workflow/hooks/tests/run-destructive-guard.py` passes on every case | Exit code 0 and the `N/N passed` line |
| SC-4 | The 14 safe-delete-labelled case-table entries carry deny expectations and no "known hole" wording | Read the case table; count the entries mentioning the safe-delete exception and check both properties |
| SC-5 | No existing deny or ask case has been deleted | Diff the case table against the base revision; only additions and expectation flips appear on those lines |
| SC-6 | Both manifests carry the same raised version | TS-9 |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001, task0003 | TS-1, TS-2, TS-4, TS-13 |
| FR2 | task0001, task0003 | TS-1, TS-2, TS-6, TS-12, TS-13, TS-14 |
| FR3 | task0001 | TS-3 |
| FR4 | task0001 | TS-1, TS-4, TS-5 |
| FR5 | task0001 | TS-4, TS-5 |
| FR6 | task0001, task0003 | TS-6, TS-7, TS-12, TS-13, TS-14 |
| FR7 | task0001 | TS-5 |
| FR8 | task0001, task0003 | TS-1, TS-2, TS-3, TS-4, TS-12, TS-13, TS-14 |
| FR9 | task0002 | TS-9 |
| FR10 | task0001, task0003 | TS-8 |
| NFR1 | task0001, task0003 | TS-10 |
| NFR2 | task0001, task0003 | TS-5 |
| NFR3 | task0001, task0003 | TS-10 |
| NFR4 | task0001 | TS-11 |
| NFR5 | task0001 | TS-11 |

## E2E Testing

No E2E framework is configured for this project
(`project.components.hooks.e2e_test_command` is empty), and the guard has no
user-facing surface to drive. The expectation suite is the end-to-end exercise
of the hook: it feeds a real hook payload to the real script through a
subprocess and reads the decision back, so no separate E2E layer is added.

## Manual Testing (E2E Not Possible)

- [ ] Read the case-table diff and confirm each flipped label states why the
      decision is now `deny`, rather than merely dropping the "known hole"
      wording (judgement about wording quality, not mechanically checkable).
- [ ] Confirm the residual symlink-escape note reads as a standing constraint a
      future maintainer can act on, not as a TODO.
- [ ] After merge, confirm the raised version is what the installed plugin cache
      picks up, and report that a Claude Code restart is required for the change
      to take effect.

## Performance / Security Verification

- Security (the point of the feature): the three attack commands recorded in the
  goal — `/tmp/../home/sakura/valuable`, `build/../src`, `targets` — no longer
  decide `allow` (TS-1, TS-2, TS-3), while the control target keeps deciding
  `deny` (TS-1).
- Security (round-1 rework): the forms that reached the safe exception through
  lost or unrecognized unresolvable evidence no longer decide `allow` (TS-12,
  TS-13), and a warranted `deny` is no longer hidden behind an earlier `ask`
  (TS-14), while the `allow` decisions the SPEC pins stay put (TS-5).
- Security (residual): symlink-based escape remains possible by design and is
  documented in the code (TS-11); it is explicitly out of scope per the SPEC.
- Performance: the hook runs synchronously on every Bash invocation, so the
  decision must stay string processing only with no filesystem access (TS-10).
  No latency threshold is defined; the absence of filesystem and subprocess
  calls on the decision path is the check.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios | 14 | 11 (TS-1 to TS-8, TS-12 to TS-14) | 0 | 3 (TS-9, TS-10, TS-11 static/read-back) |
| Success criteria | 6 | 3 (SC-2, SC-3, SC-6) | 0 | 3 (SC-1, SC-4, SC-5 by reading the diff) |
| Requirements | 15 | 15 mapped | 0 | 0 unmapped |
| Manual checks | 3 | 0 | 0 | 3 |
