# Verification Document: destructive-guard-quoted-substitution

## Overview

**Feature**: destructive-guard-quoted-substitution /
**SPEC.md**: `feature-docs/destructive-guard-quoted-substitution/SPEC.md` /
**IMPLEMENTATION.md**: `feature-docs/destructive-guard-quoted-substitution/IMPLEMENTATION.md`

### Counting vocabulary used throughout this document

Two distinct numbers describe the expectation suite (IMPLEMENTATION.md C1);
every count below names which one it is.

| Name | Definition | Before | After |
|---|---|---|---|
| **array element count** | records stored in `em-workflow/hooks/tests/destructive-guard-cases.json` | 225 | 227 |
| **suite-reported total** | the `N/N passed` figure `run-destructive-guard.py` prints | 226/226 | 228/228 |

The suite-reported total is the array element count plus one, because the
runner adds one hard-coded case (the unattended `ask` → `deny` demotion) that
is not stored in the array. SPEC.md's `226 + 2 = 228` figures are
suite-reported totals and are correct read that way.

## Build Verification

- Command: none. `project.components.main.build_command` and
  `project.components.repository.build_command` are both empty — the change is
  JSON data and manifest strings, with nothing to compile.
- Expected: N/A (no build step exists for this project).

## Test Verification

- Command (guard suite): `python3 em-workflow/hooks/tests/run-destructive-guard.py`
  - Expected: exit code 0, suite-reported total `228/228 passed`, zero
    failures.
- Command (repository suite): `python3 -m unittest discover -s tests`
  - Expected: exit code 0, and no failure that is absent from the pre-change
    baseline.
- Coverage target: not measured. No coverage tooling is configured in
  `workflow.yaml` `project.components`, and this feature adds no executable
  code to cover.

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Run the ticket's reproduction steps against the current `em-workflow/hooks/destructive-guard.py` (the reproduction command passed as `tool_input.command` on stdin) | The target shown in `permissionDecisionReason` is not a single space; the text is `[destructive-guard/rm-unresolvable]` and states that the target is a variable / command substitution whose blast radius cannot be statically determined; no non-existent `gio trash` path is offered | Integration |
| TS-2 | Search the case file for records whose JSON-decoded command equals the reproduction form (quoted `$()` spelling) | Exactly one such record exists and its first element is `ask` | Unit |
| TS-3 | Search the case file for records whose JSON-decoded command equals the backtick-spelled variant | Exactly one such record exists and its first element is `ask` | Unit |
| TS-4 | Run `python3 em-workflow/hooks/tests/run-destructive-guard.py` over the case file including the two added records | Suite-reported total `228/228 passed`, zero failures; the verdicts of the 225 pre-existing array elements are unchanged (no existing `allow` record turned into a false positive) | Integration |
| TS-5 | Read the em-workflow version string from `em-workflow/.claude-plugin/plugin.json` and from the root `.claude-plugin/marketplace.json`, before and after the change | The two values are equal (`0.1.76`) and the patch has advanced by at least one from the pre-change `0.1.75`; the em-review entry still reads `0.5.9` | Unit |
| TS-6 | Inspect the integration branch's diff for `em-workflow/hooks/destructive-guard.py` | No diff | Integration |

## Code Quality Verification

- Format: none configured (`format_command` is empty for both components).
- Static analysis: none configured.
- JSON well-formedness: `em-workflow/hooks/tests/run-destructive-guard.py`
  loads the case file as JSON before running anything, so TS-4 fails loudly on
  a malformed file; both manifests are additionally re-read to confirm they
  parse after the version edit (TS-5).
- Diff shape: the case-file diff is additive only — two added record lines
  plus the separator comma on the former final record. Any other modified line
  in that file is a defect (IMPLEMENTATION.md C4).

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | The guard suite passes in full including the added records | TS-4 — suite-reported total `228/228` (array element count 227 + 1 hard-coded case) |
| SC-2 | The two added command strings match the ticket's reproduction command and its backtick variant character for character | TS-2 / TS-3, comparing the JSON-decoded strings |
| SC-3 | Both added records expect the verdict `ask` | TS-2 / TS-3 |
| SC-4 | Existing records are unchanged in count and content apart from the additions | TS-4 plus the additive-only diff check under Code Quality; array element count 225 → 227 |
| SC-5 | `em-workflow/hooks/destructive-guard.py` has no diff | TS-6 |
| SC-6 | The reproduction steps yield a reason text whose target is not a single space and which carries `[destructive-guard/rm-unresolvable]` | TS-1 |
| SC-7 | The em-workflow version is equal in both manifests and newer than before | TS-5 |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-2, TS-4 |
| FR2 | task0001 | TS-3, TS-4 |
| FR3 | task0001 | TS-4 (+ additive-only diff check) |
| FR4 | task0001 | TS-5 |
| FR5 | task0001 | TS-1, TS-6 |
| FR6 | task0001 | TS-2, TS-3 |
| FR7 | task0001 | **No TS-n scenario** — manual item M-1 (label readability is a human-judgment property) |
| NFR1 | task0001 | **No TS-n scenario** — manual item M-2 (no test code is added, so the constraint is verified by inspection) |
| NFR2 | task0001 | TS-2, TS-3 |
| NFR3 | task0001 | **No TS-n scenario** — manual item M-3 (diff-mechanical check) |
| NFR4 | task0001 | **No TS-n scenario** — manual item M-4 (human-judgment property) |
| NFR5 | task0001 | TS-4 |

## Manual Testing (E2E Not Possible)

No E2E framework exists for this project (`e2e_test_command` is empty for both
components), so the items below are the human-judgment layer.

- [ ] M-1 (FR7): Read the two added labels. Each is Japanese, each identifies
      the `rm-unresolvable` path, and the two differ from each other in naming
      the quoted-substitution spelling (`$()` vs. backtick). They are
      distinguishable from the existing bare-spelling pair.
- [ ] M-2 (NFR1): Confirm no test code was added — the change to the case file
      is data only, and no new import of any kind exists anywhere in the diff.
- [ ] M-3 (NFR3): Confirm the diff creates no new file. Exactly three files are
      modified: the case file and the two manifests.
- [ ] M-4 (NFR4): Confirm both added records are suitable as distributed
      content — every file under `em-workflow/` is copied into user plugin
      caches. Check the labels for anything that should not ship, and note that
      the command strings are fixture text handed to the guard as data, never
      executed.
- [ ] M-5: Confirm the report and commit message state counts using the
      vocabulary of IMPLEMENTATION.md C1 (array element count vs.
      suite-reported total) and never claim an array count of 228.

## Performance / Security Verification

- Security (false positives, NFR5): a false positive stalls an unattended run
  on the spot, which `.claude/rules/hook-tests.md` weights as heavily as a
  miss. TS-4's full-suite run is the check; a filtered or partial run does not
  satisfy it.
- Security (guard integrity, FR5): TS-6 confirms the guard's decision logic is
  untouched by this feature.
- Performance: no threshold applies. The suite grows from 225 to 227 stored
  records, each a single subprocess invocation.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS-1..TS-6) | 6 | 6 | 0 | 0 |
| Success criteria (SC-1..SC-7) | 7 | 7 | 0 | 0 |
| Manual inspection (M-1..M-5) | 5 | 0 | 0 | 5 |
| **Total** | **18** | **13** | **0** | **5** |
