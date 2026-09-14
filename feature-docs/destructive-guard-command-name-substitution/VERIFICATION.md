# Verification Document: destructive-guard-command-name-substitution

## Overview

**Feature**: destructive-guard-command-name-substitution
**SPEC.md**: `feature-docs/destructive-guard-command-name-substitution/SPEC.md`
**IMPLEMENTATION.md**: `feature-docs/destructive-guard-command-name-substitution/IMPLEMENTATION.md`

This document covers the INTEGRATED verification of the feature, run after the
task has merged. Per-task acceptance criteria live in
`feature-docs/destructive-guard-command-name-substitution/tasks/task0001.md`.

## Build Verification

- Command (component `main`): `python3 em-workflow/scripts/check-plugin-invariants.py .`
- Component `hooks` declares no build command; nothing is compiled for it.
- Expected: exit code 0, no errors reported.

## Test Verification

- Command (component `hooks`): `python3 em-workflow/hooks/tests/run-destructive-guard.py`
- Command (component `main`): `python3 -m unittest discover -s tests`
- Expected: both exit 0 with every case/test passing.
- Coverage target: no coverage tooling exists in this repository and none is
  introduced (NFR6). Completeness is measured instead by case-table coverage:
  every scenario below must exist as an entry in
  `em-workflow/hooks/tests/destructive-guard-cases.json`, except the scenarios
  marked Inspection, which are checked by reading the changed files.

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | `$(which rm) -rf /home/sakura/valuable` | `deny`, reason id `rm-recursive` | Unit |
| TS-2 | Backtick spelling of TS-1 (`` `which rm` -rf /home/sakura/valuable ``) | `deny`, reason id `rm-recursive` | Unit |
| TS-3 | `$(which git) reset --hard HEAD` | `deny`, reason id `git-reset-hard` | Unit |
| TS-4 | `$(which git) clean -fd` | `deny`, reason id `git-clean` | Unit |
| TS-5 | `$(which node) script.js` | `allow` | Unit |
| TS-6 | `$(which ls) -la` | `allow` (flag-leading remainder that does not match the rm shape) | Unit |
| TS-7 | `$(which grep) -r pattern src` | `allow` (recursion flag without force flag) | Unit |
| TS-8 | `$(which rm) -rf dist` | `allow` (build-artifact safe-route exception inherited) | Unit |
| TS-9 | `$(which rm) -rf /tmp/scratch/x` | `allow` (scratch-root exception inherited) | Unit |
| TS-10 | `bash -c "$(cat script.sh)" 'rm -rf /home/sakura/valuable'` | `allow`; the pre-existing case is retained with a rewritten label | Unit |
| TS-11 | `eval "$(ssh-agent -s)"`, and the same shape for `eval "$(direnv export bash)"`, `eval "$(mise activate zsh)"`, `bash -c "$(cat script.sh)"` | `allow` for all four | Unit |
| TS-12 | `bash -c "$(echo 'rm -rf /home/sakura/valuable')" 'echo safe'` | `allow`, with the out-of-scope declaration present in the label | Unit |
| TS-13 | Unquoted payload promotion forms: `bash -c $(printf %s) 'rm -rf /home/sakura/valuable'`, its backtick spelling, `sh -c $(true) 'git reset --hard HEAD'`, `bash <<<$(true) 'rm -rf /home/sakura/valuable'` | `deny` for all four (unchanged from pre-change behaviour) | Unit |
| TS-14 | The case table contains every command of TS-1 through TS-13 as three-element entries, and the suite still runs with no new runner and no added dependency | Case table parses; runner unchanged; entries present | Inspection |
| TS-15 | The mirror divergence note covers the newly added branches, and the two mirror scripts have no code change | Note extended; mirror scripts byte-identical to their pre-change content | Inspection |
| TS-16 | The two version manifests hold the same value with the patch component advanced by at least one, and the feature's changed-file set is contained in the four declared files | Values equal and advanced; no fifth source file changed | Inspection |
| TS-17 | The judgement path introduces no filesystem access, no subprocess launch, and no evaluation of a substitution | None present in the changed code | Inspection |
| TS-18 | Every pre-existing case keeps its expected verdict except the single FR6 entry, including the unattended-demotion cases at the end of the runner | Full suite passes; the only changed expectation is the FR6 one | Integration |

## Code Quality Verification

- Format: no format command is declared for either component; nothing to run.
- Static analysis: none declared. The plugin invariants check
  (`python3 em-workflow/scripts/check-plugin-invariants.py .`) serves as the
  structural check for the manifests.

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | `$(which rm) -rf /home/sakura/valuable` is `deny` with reason id `rm-recursive` | TS-1 (and TS-2 for the backtick spelling) |
| AC-2 | `$(which git) reset --hard HEAD` is `deny` with reason id `git-reset-hard` | TS-3 |
| AC-3 | `$(true) echo safe`, `env $(true) echo safe`, `git $(true) status`, `$(which node) script.js`, `$(which ls) -la` are `allow` | TS-5, TS-6 plus the pre-existing entries for the first three commands (TS-18 proves they are unchanged) |
| AC-4 | `$(which rm) -rf dist` and `$(which rm) -rf /tmp/scratch/x` are `allow` | TS-8, TS-9 |
| AC-5 | The FR6 command is `allow` and its case is retained with a rewritten label | TS-10 |
| AC-6 | The four quoted-payload normal-operation commands are `allow` | TS-11 |
| AC-7 | The four unquoted-promotion forms stay `deny` | TS-13 |
| AC-8 | The out-of-scope form is `allow`, and its label and the payload-extraction docstring state the same scope | TS-12 (verdict) + Manual item M-1 (wording agreement) |
| AC-9 | `python3 em-workflow/hooks/tests/run-destructive-guard.py` passes in full | TS-18 / Test Verification |
| AC-10 | `python3 -m unittest discover -s tests` passes in full | Test Verification |
| AC-11 | Both version manifests carry the same value, advanced by at least one patch | TS-16 + Build Verification |
| AC-12 | Commands containing no substitution return the same stage and the same reason text as before the change | TS-18 (the pre-existing substitution-free cases) + Manual item M-2 |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2, TS-6, TS-7, TS-8, TS-9 |
| FR2 | task0001 | TS-3, TS-4 |
| FR3 | task0001 | TS-5, TS-6 |
| FR4 | task0001 | TS-10, TS-11 |
| FR5 | task0001 | TS-13 |
| FR6 | task0001 | TS-10 |
| FR7 | task0001 | TS-12 |
| FR8 | task0001 | TS-14 |
| FR9 | task0001 | TS-15 |
| FR10 | task0001 | TS-16 |
| NFR1 | task0001 | TS-17 |
| NFR2 | task0001 | TS-18 |
| NFR3 | task0001 | TS-18 (allow-side entries TS-5 through TS-9, TS-11 in particular) |
| NFR4 | task0001 | TS-18 (the unattended-demotion cases) |
| NFR5 | task0001 | TS-16 |
| NFR6 | task0001 | TS-14 |

## E2E Testing

No E2E framework exists in this repository and `e2e_test_command` is empty for
both components. No E2E scenario is defined for this feature.

## Manual Testing (E2E Not Possible)

- [ ] M-1 (AC-8, FR7): Read the out-of-scope case label and the
      payload-extraction docstring side by side and confirm they state the same
      scope — that a form whose substitution output becomes the script body is
      outside this hook's static analysis. A difference in scope (not merely in
      phrasing) is a failure.
- [ ] M-2 (AC-12, NFR1): Read the changed judgement path and confirm it consults
      the command string only — no path resolution, no stat, no subprocess, no
      evaluation of a substitution — and that no reason text was reworded for a
      substitution-free command.
- [ ] M-3 (FR9, AS-6): Confirm the mirror divergence note now covers the added
      branches, and that neither mirror script received a code change.
- [ ] M-4 (NFR5, FR10): Confirm the feature's integrated change set is contained
      in the four declared source files plus the workflow-generated
      `feature-docs/` and `test-docs/` entries, and that the version bump appears
      as its own commit rather than being mixed into the behaviour change.

## Performance / Security Verification

- Security (detection scope): a statement whose command word is statically
  unknown reaches a `deny` / `ask` verdict only through an existing destructive
  shape match — verified by TS-1 through TS-4 (positives) together with TS-5
  through TS-9 (negatives).
- Security (unattended behaviour): the `ask`-to-`deny` demotion path is
  unchanged — verified by TS-18's demotion cases.
- Performance: not applicable. No performance requirement is stated and the
  analysis remains a single pass over one command string.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios | 18 | 14 (TS-1 - TS-13, TS-18) | 0 | 4 (TS-14 - TS-17, as inspections) |
| Success criteria | 12 | 10 | 0 | 2 (AC-8, AC-12 partially) |
| Build / quality | 1 | 1 | 0 | 0 |
| Manual items | 4 | 0 | 0 | 4 |
