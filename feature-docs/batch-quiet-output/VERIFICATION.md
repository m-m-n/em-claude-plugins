# Verification Document: batch-quiet-output

## Overview

**Feature**: batch-quiet-output /
**SPEC.md**: `feature-docs/batch-quiet-output/SPEC.md` /
**IMPLEMENTATION.md**: `feature-docs/batch-quiet-output/IMPLEMENTATION.md`

This feature changes protocol documents and two plugin manifests; it adds no
runtime component. Integrated verification is therefore the repository's two
test suites (which include document-contract modules and the plugin-invariant
checker) plus a small set of human-judgment checks. Every command below runs
from the integration worktree root.

## Build Verification

- Command: none — `project.components` declares no build command for either
  component (`main`: markdown, `hooks`: python).
- Expected: not applicable; nothing is compiled or bundled.

## Test Verification

- Command: `python3 -m unittest discover -s tests`
- Expected: exit code 0, no failures and no errors. This suite carries the
  four modules this feature adds
  (`test_batch_quiet_output_discipline.py`,
  `test_batch_quiet_output_skill_wiring.py`,
  `test_batch_quiet_output_phase_wiring.py`,
  `test_batch_quiet_output_version_bump.py`) alongside every pre-existing
  module, including `test_batch_stop_contract.py`,
  `test_batch_stop_contract_skill_wiring.py`, `test_batch_policies.py`,
  `test_plugin_version_parity.py` and `test_check_plugin_invariants.py`
  (the last of which runs the plugin-invariant checker against the real
  repository root).
- Command: `python3 em-workflow/hooks/tests/run-destructive-guard.py`
- Expected: exit code 0. This feature touches no hook, so this suite is a
  pure non-regression check.
- Coverage target: not applicable — the suites are document-contract and
  guard-behaviour assertions, not line-coverage-measured code.

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Interactive-mode non-regression: SKILL.md and batch-mode.md agree that a launch whose arguments contain no `--batch` never enters the suppression branch | The activation statement in batch-mode.md's discipline section and SKILL.md's `--batch` site both bind suppression to the flag's presence; no interactive-path wording changed | Unit (document contract) |
| TS-2 | Non-terminal turn markers: for stop condition 5, implement launch and implement wake, batch-mode.md carries the marker-only rule and SKILL.md / implement-phase.md reference it | All three sites present; suppressed-scope list complete; no pointer document restates the format or the scope | Unit (document contract) |
| TS-3 | Marker / terminal-line non-collision, confirmed from both SSOT documents | batch-mode.md defines the marker prefix, batch-terminal-line.md defines the terminal prefix, neither is a prefix of the other, and neither document contains the other's prefix literal | Unit (document contract, cross-document) |
| TS-4 | Terminal turns keep full output: every one of the eleven rows of batch-terminal-line.md's stop-point coverage table is covered by the suppression exception | The exception is stated as a set-level rule over that table (IMPLEMENTATION.md D7); the test reads the table's stop-point keys and confirms coverage; Step C and the `--once` boundary exceptions present | Unit (document contract, cross-document) |
| TS-5 | Audit-item provenance: each audit item batch-mode.md "Reporting" requires traces one-to-one to a committed artifact or a specific phase-state field | The audit-item source map has one row per item, each naming a persisted source; Step A.5's newly defined phase-state source and the wake-commit decline channel are both present | Unit (document contract) |
| TS-6 | Existing suites pass, including the version bump | `python3 -m unittest discover -s tests` and `python3 em-workflow/hooks/tests/run-destructive-guard.py` both exit 0; both registries carry the same raised version | Integration (regression) |
| TS-7 | Plugin invariants and SSOT singularity: the added text contradicts no existing SSOT under `em-workflow/scripts/check-plugin-invariants.py`'s criteria | `tests/test_check_plugin_invariants.py` passes (it runs the checker against the real repository root); the discipline exists in exactly one definition site | Integration (invariant checker) + Manual |

## Code Quality Verification

- Format: none — `project.components` declares no format command.
- Static analysis: `em-workflow/scripts/check-plugin-invariants.py`, invoked
  through `tests/test_check_plugin_invariants.py` as part of the unittest
  suite (agent/dispatch parity, stale references, gate-ID coverage, domains
  vocabulary parity, fixture coverage, `input_digest` reproducibility).
  Expected: every check passes.

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | All functional requirements (FR1-FR13) implemented | The coverage table below; every FR maps to ≥ 1 task and ≥ 1 passing scenario |
| SC-2 | All non-functional requirements (NFR1-NFR5) satisfied | TS-1 (NFR1), TS-3 (NFR2), TS-4 (NFR3), TS-7 (NFR4, NFR5) plus manual item M-2 |
| SC-3 | All test scenarios (TS-1 - TS-7) pass | Run both suites; every scenario's owning assertions green |
| SC-4 | Every acceptance criterion in REQUIREMENTS.md 11.1 is met | Walk REQUIREMENTS.md 11.1 against the task Acceptance Criteria and the suite result |
| SC-5 | The suppression discipline exists in exactly one definition site (`references/batch-mode.md`) | TS-7 plus manual item M-1: grep the plugin tree for a second statement of the marker format or the suppressed-scope list |
| SC-6 | Code review completed | The review phase's round record shows no residual critical/high finding |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001, task0002 | TS-1 |
| FR2 | task0001, task0002, task0003 | TS-2 |
| FR3 | task0001 | TS-3 |
| FR4 | task0001, task0002, task0003 | TS-2 |
| FR5 | task0001, task0002 | TS-4 |
| FR6 | task0001, task0002, task0003 | TS-4 |
| FR7 | task0001, task0002 | TS-3 |
| FR8 | task0001, task0002 | TS-4 |
| FR9 | task0001, task0002, task0003 | TS-5 |
| FR10 | task0001, task0002, task0003 | TS-6 |
| FR11 | task0001, task0002, task0003 | TS-5 |
| FR12 | task0001, task0002, task0003 | TS-7 |
| FR13 | task0004 | TS-6 |
| NFR1 | task0001, task0002, task0003 | TS-1 |
| NFR2 | task0001, task0002 | TS-3 |
| NFR3 | task0001, task0002, task0003 | TS-4 |
| NFR4 | task0001, task0002, task0003 | TS-7 |
| NFR5 | task0001, task0002 | TS-7 |

## E2E Testing

The project declares no E2E command (`e2e_test_command` is empty for both
components) and this feature adds no runnable surface, so there is no E2E
scenario to automate.

## Manual Testing (E2E Not Possible)

- [ ] M-1 (SC-5, NFR4): search the plugin tree for a second definition of the
      marker format or of the suppressed-scope list outside
      `references/batch-mode.md`; confirm every other occurrence is a
      reference.
- [ ] M-2 (NFR5): read the Japanese output that survives suppression — Step C's
      final report and the stop reports in `skills/develop/SKILL.md` — and
      confirm the voice is unchanged (タメ語・一人称「私」・体言止めなし), and
      that the marker line and terminal line are stated as machine formats
      outside that rule.
- [ ] M-3 (NFR2): read the marker-line definition and the terminal-line
      contract side by side and confirm that a consumer matching the
      terminal-line prefix cannot match a marker line, and that "no line at
      the end of a run" still reads as an abnormal outcome.
- [ ] M-4 (FR9, FR10): review the integrated diff and confirm no file-artifact
      write rule, gate resolution rule, cap, counter or status-transition rule
      was altered anywhere in the change set.

## Performance / Security Verification

- Performance: no performance requirement is defined for this feature.
- Security (SPEC "Security Considerations"): confirm the marker line's two
  fields carry only a workflow step id and a closed-vocabulary point value —
  no free text, no path, no confidential information — matching the terminal
  line's existing `detail` constraint.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios (TS-1 - TS-7) | 7 | 7 | 0 | 1 (TS-7 also has a manual half) |
| Success criteria (SC-1 - SC-6) | 6 | 4 | 0 | 2 |
| Manual checks (M-1 - M-4) | 4 | 0 | 0 | 4 |
| Security checks | 1 | 0 | 0 | 1 |
