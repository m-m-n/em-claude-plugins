# Verification Document: failed-run-cleanup-guard

## Overview

**Feature**: failed-run-cleanup-guard /
**SPEC.md**: `feature-docs/failed-run-cleanup-guard/SPEC.md` /
**IMPLEMENTATION.md**: `feature-docs/failed-run-cleanup-guard/IMPLEMENTATION.md`

This document covers the INTEGRATED verification run after every task has
merged. Task-level acceptance criteria live in the task plans.

## Build Verification

- Command: none — both components in `workflow.yaml` declare an empty build
  command; the deliverables are interpreted scripts and manifests.
- Substitute check (must hold instead): every changed JSON manifest parses,
  which the test suite below asserts directly for the hook manifest and for
  both version registries.
- Expected: exit code 0, no errors.

## Test Verification

- Command (main component): `python3 -m unittest discover -s tests`
- Command (hooks component): `python3 em-workflow/hooks/tests/run-destructive-guard.py`
- Coverage target: line-coverage measurement is not configured in this
  repository and no coverage tool is a permitted dependency for test code.
  The coverage criterion is therefore scenario-based: every scenario below
  passes, and every functional requirement has at least one passing scenario.

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Drive the new guard as a subprocess with a JSON payload on stdin against a temporary integration-worktree fixture whose workflow document has a failed step | Exit code 0; stdout carries a deny decision whose Japanese reason names the feature and the failed step and tells the caller to report and stop; the fixture tree is byte-identical afterwards | Unit |
| TS-2 | Edge and boundary matrix: failed step present; all steps completed with design skipped; only needs_update / pending steps; healthy feature whose free-text goal quotes the failure phrase; workflow document missing; workflow document unparsable; malformed payload; variable-expanded target; non-em-workflow worktree path; target command text inside quotes | Only the failed-step case decides; every other case produces empty stdout and exit code 0 | Unit |
| TS-3 | Pull-request creation with the payload working directory set inside, and then outside, the integration worktree, the outside case additionally carrying a head argument naming the integration branch | Inside resolves the feature and decides; outside produces no decision, proving the resolution never consults command arguments | Unit |
| TS-4 | The same statically unresolvable target run twice, with the unattended-run environment variable unset and then set | Unset yields ask; set yields deny; both reasons instruct rewriting the command into a statically determinable form | Unit |
| TS-5 | The destructive-guard expectation suite after its deferral rows are added: real invocations of the three target shapes, quoted mentions of them, near-miss commands of the same families, and the pre-existing rows | Real invocations produce no output (blanket allow withheld); quoted mentions and near misses still receive the blanket allow; every pre-existing deny/ask/allow row keeps its verdict and none is removed | Integration |
| TS-6 | Manifest-driven registration checks over the edited hook manifest: declared order of the Bash matcher group, command form, interpreter/extension pairing, per-script timeout, referenced script existence, no duplicate registration | The group declares the five guards in the pinned order with the blanket-allow guard last; the new entry is well-formed with the standard timeout and its script exists | Unit |
| TS-7 | Version parity across the plugin manifest and the marketplace entry, the latter looked up by plugin name | Both carry the identical value, strictly greater than the recorded baseline under component-wise numeric comparison; the other plugin's entry is untouched | Unit |

TS-1 through TS-5 are SPEC.md's own scenarios. TS-6 and TS-7 are added here
for two SPEC.md Success Criteria that its scenario list does not number
(registration in the hook manifest, and the paired version bump); both are
satisfied by existing repository test modules once the tasks land.

## Code Quality Verification

- Format: none — both components declare an empty format command.
- Static analysis: `python3 em-workflow/scripts/check-plugin-invariants.py .`
  from the repository root; expected exit code 0.

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | All functional requirements are implemented and tested | The requirement coverage table below has no empty cell |
| SC-2 | All test scenarios pass | TS-1 through TS-7 all pass in the integrated tree |
| SC-3 | The destructive-guard expectation suite passes in full, and a case proves the new guard's deny is not cancelled by the blanket allow | Run the hooks-component command; confirm the added deferral rows are present and green (TS-5) |
| SC-4 | The repository-root unit test command passes in full, including the new tests | Run the main-component command (TS-1 through TS-4, TS-6, TS-7) |
| SC-5 | The new guard is registered in the Bash matcher of the hook manifest | TS-6 |
| SC-6 | Both registries carry the same raised version | TS-7 |
| SC-7 | Security requirements are satisfied | The guard emits no allow, starts no process, writes nothing, and treats the workflow document as inert data — TS-1 (unchanged tree), TS-2 (untrusted content and broken input), TS-4 (demotion) |
| SC-8 | Documentation is complete | The plugin README names the new guard and states the five-guard chain order (manual item M-1) |
| SC-9 | Code review is completed | The review phase's own record |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001, task0002 | TS-1, TS-6 |
| FR2 | task0001 | TS-2 |
| FR3 | task0001 | TS-2 |
| FR4 | task0001 | TS-3 |
| FR5 | task0001 | TS-1, TS-2 |
| FR6 | task0001 | TS-1 |
| FR7 | task0001 | TS-4 |
| FR8 | task0003 | TS-5 |
| FR9 | task0001 | TS-1, TS-2 |
| FR10 | task0001 | TS-2 |
| FR11 | task0002 | TS-7 |
| NFR1 | task0001, task0003 | TS-2, TS-5 |
| NFR2 | task0001 | TS-1 |
| NFR3 | task0001, task0002 | TS-1, TS-6 |
| NFR4 | task0001 | TS-2 |
| NFR5 | task0001 | TS-2 |
| NFR6 | task0001, task0003 | TS-1, TS-5 |

## E2E Testing

No E2E framework exists in this repository and none is detected in
`workflow.yaml`; both components declare an empty E2E command. Nothing to
run, and nothing regressed by omission.

## Manual Testing (E2E Not Possible)

- [ ] M-1: Read the plugin README and confirm the new guard's row and the
      five-guard order sentence describe the shipped behaviour (documentation
      accuracy is a human judgment, not a string match).
- [ ] M-2: In a live Claude Code session with the plugin cache refreshed for
      the new version, attempt a worktree removal against a feature whose
      workflow document has a failed step and confirm the denial reason
      reaches the agent as tool feedback in readable Japanese. This is the
      only check that exercises the real hook chain end to end; the automated
      scenarios drive the scripts directly.
- [ ] M-3: In the same session, perform an ordinary cleanup for a healthy
      feature and confirm it is not interrupted — the false-positive cost
      NFR1 weighs most heavily.

## Performance / Security Verification

- NFR3 (execution cost): the registration declares a 15 second timeout,
  inside the existing 10-15 second band (TS-6), and at most one workflow
  document is read per evaluated command (TS-1, TS-2).
- NFR2 (static evaluation only): no external process is started and no state
  is mutated — the fixture tree is asserted unchanged after a run (TS-1).
- NFR5 (untrusted input): a workflow document carrying instruction-shaped
  natural language does not change the decision (TS-2).
- NFR4 (fail-open): malformed payloads and unparsable documents produce no
  decision and exit 0 (TS-2).

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios | 7 | 7 | 0 | 0 |
| Success criteria | 9 | 7 | 0 | 1 (SC-8; SC-9 is the review phase's own record) |
| Functional requirements | 11 | 11 | 0 | 0 |
| Non-functional requirements | 6 | 6 | 0 | 0 |
| Manual checks | 3 | 0 | 0 | 3 |
