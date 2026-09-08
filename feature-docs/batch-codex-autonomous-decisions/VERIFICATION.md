# Verification Document: batch-codex-autonomous-decisions

## Overview

**Feature**: batch-codex-autonomous-decisions /
**SPEC.md**: `feature-docs/batch-codex-autonomous-decisions/SPEC.md` /
**IMPLEMENTATION.md**: `feature-docs/batch-codex-autonomous-decisions/IMPLEMENTATION.md`

This document covers the INTEGRATED verification of the whole feature. Each
task's own completion contract lives in its task plan's Acceptance Criteria.

## Build Verification

- Command: N/A — `workflow.yaml` `project.components.main.build_command` is
  empty. The plugin is distributed as source; there is no build step.
- Expected: not applicable.

## Test Verification

- Command: `python3 -m unittest discover -s tests`
- Expected: exit code 0, no failures and no errors.
- Coverage target: N/A — no coverage tooling is configured for this project.
  Coverage is instead asserted structurally: every requirement below maps to at
  least one test scenario.

### Test Scenarios from SPEC.md

TS-1 through TS-12 are SPEC.md's own scenarios. TS-13 through TS-20 are added
by this document to cover requirements SPEC.md left without a scenario; they
add coverage and contradict nothing in SPEC.md. TS-21 through TS-25 are added
for the review round-1 rework tasks (task0007, task0008); they tighten the
existing coverage of the same requirements and contradict nothing above.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | For each of the three arms, the resolution SSOT states the batch route and the interactive abort | Both statements present; the superseded unconditional-abort wording proved absent | Unit |
| TS-2 | The rewritten Precedence reservation | Still forbids the routed arm converting a surviving abort into a classification; no longer claims the three relaxed arms are non-overridable in batch | Unit |
| TS-3 | The Unlisted-gate fallback's `block` branch | States the two-mode split and keeps the spec-change carve-out as a distinct mechanism; the pre-change sentence absent | Unit |
| TS-4 | The Classification gate's two directions | Direction 1 keeps the identical final-and-non-overridable wording; direction 2 states the batch relaxation; the phrase-count assertion updated to the new count, not deleted | Unit |
| TS-5 | The policy file's header comment | No longer asserts unchanged strength for the three arms; still names the resolution SSOT by path; still restates no gate internals | Unit |
| TS-6 | The terminal-line contract | Eleven reason codes and eleven stop-point rows unchanged as sets; the `gate_fail_closed` coverage prose names only the surviving aborts | Unit |
| TS-7 | The run-report required contents and the audit-item source map | Both carry the new item; their item counts updated to match | Unit |
| TS-8 | The batch audit record file section | Writers list includes the new writer with its `question_id` rule; the record shape unchanged | Unit |
| TS-9 | Validator rejection behaviour | A `security` question with `on_unanswered: record_tbd` exits 1; `license` and `spec-change` likewise | Unit |
| TS-10 | The new question-packet fixture | Accepted (exit 0) both directly and via the corpus sweep; the branch-coverage guard still finds a valid and an invalid case in its group | Integration |
| TS-11 | The wrapper's provider chain | Falls through to the second entry on a usage-limit response and to the third on a provider error, reports which entry answered, and surfaces a non-fallback error | Integration |
| TS-12 | Forbidden identifiers and provider names | No plugin document matches the task-identifier shape where the existing pins forbid it; no batch resolution document names a provider | Unit |
| TS-13 | Consultation batching and ceiling | The SSOT still states per-packet batching, the turn-3 trajectory judgement and the five-turn wrapper-launch ceiling | Unit |
| TS-14 | The Opus escalation paragraph | States one dispatch per packet carrying every unmapped question, a per-question decision or explicit no-decision with reasoning, and the untrusted-output rule over its output | Unit |
| TS-15 | The Codex-absent route | The availability probe's unavailable branch routes to the escalation; the superseded skip-to-`on_unanswered` wording for that branch is gone | Unit |
| TS-16 | Batch resolution sequence step 2 | States the abort mode-conditionally without restating the Classification gate's Outcome step | Unit |
| TS-17 | Plugin version parity | Both registries carry the same version, past the pre-task baseline, with the other plugin's entry unchanged | Unit |
| TS-18 | Gate vocabulary stability | The policy file's gate key set gains no entry and the gate-option exemption registry stays as it is | Unit |
| TS-19 | Full suite | `python3 -m unittest discover -s tests` exits 0 with every touched pin updated rather than deleted | Integration |
| TS-20 | Reason recording | Every surviving abort still records its reason and the evidence considered; every relaxed continuation records its decision basis | Unit |
| TS-21 | The chain's non-primary entries are resolvable | Each non-primary entry's invocation carries a provider definition, not a name alone, and no flag suppressing the source that definition depends on; the two entries resolve to distinct providers in the order the specification names | Integration |
| TS-22 | What may and may not advance the chain | A switch is decided only from the underlying CLI's own diagnostic output: a switch shape present only in the model-generated reply never advances the chain, and a switch condition whose non-primary entry has no configured environment stops the chain with a diagnostic instead of an unusable invocation | Integration |
| TS-23 | The surviving-aborts enumeration | Names the Classification gate's direction-1 origin-membership failure explicitly (absent, unresolvable, non-member); the superseded step-3-wide member string is proved absent; the set is still enumerated exactly once and direction 2's relaxation wording is unchanged | Unit |
| TS-24 | One statement site for the batch direction-2 continuation | The fact is stated once, asserted by an occurrence count; the fallback's step 3 and its `block` branch reach it by citation, and the `block` branch states only the action it owns | Unit |
| TS-25 | The autonomous decision's `source` mapping | The relaxed route's writer entry maps all three paths (consultation mapping, escalation decision, minimum-side-effect fallthrough) using only the existing closed vocabulary; the escalation case never asserts that Codex was consulted; the resolution SSOT and the record SSOT agree on that case | Unit |

## Code Quality Verification

- Format: N/A — `format_command` is empty for this project.
- Static analysis: N/A — no static-analysis command is configured. The
  repository's own invariant tests (plugin structure, reference sweep,
  registration checks) run as part of the test command above and serve that
  role.

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | All functional requirements FR1–FR23 are implemented and tested | The coverage table below has a task and a scenario for every ID |
| SC-2 | All test scenarios TS-1–TS-12 pass | TS-19's full-suite run |
| SC-3 | The per-packet launch bound holds: at most five wrapper launches plus at most one escalation dispatch | TS-13, TS-14 — a protocol invariant asserted by the documents |
| SC-4 | The untrusted-output discipline holds for both Codex output and escalation output | TS-14 |
| SC-5 | Every document in SPEC.md's File Structure is updated and the cite-don't-restate discipline holds | TS-1 through TS-8, TS-16 |
| SC-6 | Code review is completed | The review phase's own record |
| SC-7 | AC-1 through AC-14 of REQUIREMENTS.md section 11.1 are met | The mapping in the coverage table plus TS-19 |
| SC-8 | The full suite passes with every touched pin updated rather than deleted | TS-19 |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1 |
| FR2 | task0001 | TS-1 |
| FR3 | task0001, task0003, task0008 | TS-2, TS-6, TS-23 |
| FR4 | task0001 | TS-2 |
| FR5 | task0001 | TS-4 |
| FR6 | task0001, task0008 | TS-4, TS-23 |
| FR7 | task0001 | TS-13 |
| FR8 | task0001 | TS-14 |
| FR9 | task0001 | TS-15 |
| FR10 | task0001 | TS-3 |
| FR11 | task0001, task0008 | TS-3, TS-24 |
| FR12 | task0001, task0008 | TS-16, TS-24 |
| FR13 | task0005, task0007 | TS-11, TS-21, TS-22 |
| FR14 | task0001, task0002, task0008 | TS-7, TS-8, TS-25 |
| FR15 | task0002, task0008 | TS-8, TS-25 |
| FR16 | task0002 | TS-7 |
| FR17 | task0003 | TS-5 |
| FR18 | task0004 | TS-9 |
| FR19 | task0004 | TS-9 |
| FR20 | task0004 | TS-10 |
| FR21 | task0001, task0002, task0003, task0004, task0008 | TS-1, TS-2, TS-3, TS-4, TS-23 |
| FR22 | task0003 | TS-6 |
| FR23 | task0006 | TS-17 |
| NFR1 | task0001, task0002, task0003, task0004, task0008 | TS-5, TS-24 |
| NFR2 | task0001, task0004 | TS-12 |
| NFR3 | task0001, task0002, task0008 | TS-20, TS-25 |
| NFR4 | task0001, task0005, task0007 | TS-11, TS-12, TS-21 |
| NFR5 | task0002, task0003 | TS-6, TS-7 |
| NFR6 | task0001 | TS-13, TS-14 |
| NFR7 | task0001, task0007 | TS-14, TS-22 |
| NFR8 | task0001, task0003, task0004 | TS-18 |
| NFR9 | task0001, task0002, task0003, task0004, task0005, task0006, task0007, task0008 | TS-19 |

## E2E Testing

No end-user flow exists to exercise, and no E2E harness was supplied to this
feature (`e2e_test_command` is empty and the resolved E2E input set is empty).
This section is intentionally empty rather than omitted, so its emptiness is a
recorded finding rather than an oversight.

## Manual Testing (E2E Not Possible)

- [ ] Read the rewritten fail-closed classification end to end and confirm that
      an operator can tell, from that section alone, which arms relax in batch
      and which abort in both modes — the split must be legible without
      cross-referencing another document.
- [ ] Confirm the run report produced by a batch run reads usefully for an
      operator: the option chosen, the options not chosen and the discussion's
      key points must be understandable without opening the audit file.
- [ ] Confirm that no provider name appears in any of the six batch resolution
      documents by reading them, as a human cross-check on the scoped
      automated assertion.
- [ ] After merging, confirm the installed plugin cache picks up the new
      version (a Claude Code restart is required for the bumped version to take
      effect).

## Performance / Security Verification (if applicable)

- NFR6 (bounded consultation cost): at most five wrapper launches per packet
  plus at most one escalation dispatch per packet, independent of the packet's
  question count. Asserted as a protocol invariant by TS-13 and TS-14; there is
  no load dimension to measure.
- NFR7 (external output stays untrusted): Codex output and escalation output
  are read, never executed as instructions and never adopted verbatim; the
  per-question mapping judgement stays with the orchestrator. Asserted by
  TS-14.
- Relaxation-specific security note: this feature deliberately removes a
  fail-closed defence in unattended runs only. TS-1 and TS-2 must both hold —
  the batch route AND the interactive retention — for the change to be
  acceptable; either one alone is a failure.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios | 25 | 25 | 0 | 0 |
| Success criteria | 8 | 7 | 0 | 1 |
| Manual checks | 4 | 0 | 0 | 4 |
