# Verification Document: exit4-recovery-scope

## Overview

**Feature**: exit4-recovery-scope /
**SPEC.md**: `feature-docs/exit4-recovery-scope/SPEC.md` /
**IMPLEMENTATION.md**: `feature-docs/exit4-recovery-scope/IMPLEMENTATION.md`

This document covers the INTEGRATED verification of the feature. Task-level
acceptance criteria live in `feature-docs/exit4-recovery-scope/tasks/task0001.md`.

## Build Verification

- Command: none. `project.components.main.build_command` is empty — the change
  set is Markdown, Python test source and two JSON manifests, none of which has a
  build step in this repository.
- Expected: not applicable. Substituted by the JSON-parse check inside TS6 and by
  the test suite importing the modified test module (TS5).

## Test Verification

- Command: `python3 -m unittest discover -s tests`
- Coverage target: no coverage tooling is configured for this repository, so no
  numeric target is set. The coverage obligation is expressed structurally
  instead: the test-method count of `tests/test_implement_routeback_gate.py` must
  be greater after the change than before, and no test may be removed, renamed
  away, or skipped (NFR3).

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS1 | The exit-4 recovery bullet states a universal scope over every `commit-docs.sh` call site in the implement phase | The universal-scope matcher finds the phrasing in the bullet; the assertion fails against the pre-change text | Unit |
| TS2 | Step I.2.a's launch-time write and Step I.3's completion write are named inside the bullet's bound-side enumeration | Both site identifiers are found within the bullet's own text, not merely somewhere in the file | Unit |
| TS3 | The closed-enumeration phrasing is absent, and its matcher is proven to flag the pre-change wording | Absence assertion passes against the new text; the paired regression proof shows the same matcher matches the pre-change wording | Unit |
| TS4 | Existing assertions in the exit-4 enumeration class and the three-SSOT carve-out class run unchanged | All existing assertions pass; the carve-out sentence, unreachability-chain and ref-advancing-paths phrasings and the recovery-procedure fragments are still present; both forbidden phrases still absent | Unit |
| TS5 | Whole-suite run catches any other module pinning the bullet's wording | `python3 -m unittest discover -s tests` exits 0 with no failures, errors or new skips | Integration |
| TS6 | Plugin-invariant / version consistency across the two manifests | Both `em-workflow/.claude-plugin/plugin.json` and the em-workflow entry of `.claude-plugin/marketplace.json` parse as JSON and read `0.1.43` | Integration |

## Code Quality Verification

- Format: none configured (`project.components.main.format_command` is empty).
  The substitute check is that the edit stays inside the exit-4 recovery bullet:
  the whole-file byte-identity test on the batch-mode paragraph and the
  bare-git-command test over the Step I.2.c section both remain green (EC3).
- Static analysis: none configured. The substitute check is that the modified
  test module imports and runs under the suite discovery command above.

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | The bullet's bounded recovery is universally scoped over every `commit-docs.sh` call site in the implement phase, with exactly one carve-out (Step I.2.c's route-back commit) | TS1 plus TS3's absence assertion; carve-out count confirmed by reading the bullet (manual M1) |
| AC2 | Step I.2.a's launch/refill status commit and Step I.3's completion commit are named explicitly on the bound side | TS2 |
| AC3 | The three SSOTs state the same thing about the carved-out site and the universal binding of every other site | TS4's three-SSOT class, plus manual read-through M1 |
| AC4 | Every string the test module currently fixes remains satisfied | TS4 |
| AC5 | The removed closed-enumeration wording has its own absence assertion plus a paired regression proof | TS3 |
| AC6 | `python3 -m unittest discover -s tests` passes | TS5 |
| AC7 | Both version fields read `0.1.43` | TS6 |
| NFR2 | Frozen files untouched | Change-set inspection: neither `em-workflow/references/workflow-patch.md` nor `em-workflow/scripts/validate-worker-output.py` appears in the integrated diff |
| NFR4 | The change set is contained in the expected four-file set plus the declared workflow-generated entries | Change-set inspection against the SPEC's Declared Change Set |
| NFR5 | The Branch & Worktree Model bullet remains the sole owner of the bounded recovery procedure | Manual read-through M2 |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS1, TS3 |
| FR2 | task0001 | TS2 |
| FR3 | task0001 | TS4 |
| FR4 | task0001 | TS4 |
| FR5 | task0001 | TS3, TS4 |
| FR6 | task0001 | TS6 |
| NFR1 | task0001 | TS5 |
| NFR2 | task0001 | TS5 |
| NFR3 | task0001 | TS5 |
| NFR4 | task0001 | TS5 |
| NFR5 | task0001 | TS4 |
| NFR6 | task0001 | TS3 |

## E2E Testing

No E2E framework exists in this repository and no E2E command is configured
(`project.components.main.e2e_test_command` is empty). Nothing in this feature is
E2E-testable — the change has no runtime surface (NFR1).

## Manual Testing (E2E Not Possible)

- [ ] M1 (AC1, AC3, EC1): Read the rewritten exit-4 recovery bullet, then the
      RECOVERY CONTRACT header of `em-workflow/scripts/commit-docs.sh`, then the
      exit-4 paragraph of `em-workflow/skills/develop/SKILL.md`. Confirm all
      three yield the same answer to "which call sites are bound, and which
      single site is carved out", and that the bullet's list reads as examples
      under the universal scope rather than as a closed set. The
      list-reads-as-illustrative judgment is human-only; no string matcher can
      establish it.
- [ ] M2 (NFR5, EC2): Confirm the bullet is still the only place stating the
      bounded-recovery procedure, that the two citing documents remain citations
      rather than second definitions, that rules owned elsewhere (the
      write-then-commit rule, the widened Step I.2.c gate) are cited and not
      restated, and that the unreachability proof's reasoning was not narrowed to
      only the newly enumerated sites.
- [ ] M3 (NFR1, NFR2, NFR4): Inspect the integrated diff. Confirm it touches only
      `em-workflow/references/implement-phase.md`,
      `tests/test_implement_routeback_gate.py`,
      `em-workflow/.claude-plugin/plugin.json` and
      `.claude-plugin/marketplace.json` (plus the declared
      `feature-docs/exit4-recovery-scope/**` and
      `test-docs/exit4-recovery-scope/**` entries), that no executable line of
      any script changed, and that no test was deleted, renamed away, or skipped.

## Performance / Security Verification (if applicable)

Not applicable. Per NFR1 no executable line changes, so there is no runtime
behavior to load-test and no authentication, authorization, input-handling or
data-protection surface is touched.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios | 6 (TS1-TS6) | 6 | 0 | 0 |
| Success criteria | 10 (AC1-AC7, NFR2, NFR4, NFR5) | 7 | 0 | 3 |
| Manual checks | 3 (M1-M3) | 0 | 0 | 3 |
