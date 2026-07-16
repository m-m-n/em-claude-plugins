# Verification Document: Implement Phase Queue

## Overview
**Feature**: implement-phase-queue / **SPEC.md**:
`feature-docs/implement-phase-queue/SPEC.md` / **IMPLEMENTATION.md**:
`feature-docs/implement-phase-queue/IMPLEMENTATION.md`

## Build Verification
- Command: (none — no build step in this repository)
- Expected: n/a

## Test Verification
- Command: `python3 -m unittest discover -s tests`
- Coverage target: every new hook script and the merge-task.sh journal
  append exercised by at least one test (no numeric coverage tooling in
  this stdlib-only setup)

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | merge-task.sh merge success (fast-forward, merge-commit, idempotent) | exactly one well-formed `merged` JSONL line per merge | Integration |
| TS-2 | merge-task.sh conflict / precondition failure | no journal append; exit codes unchanged | Integration |
| TS-3 | Stop hook with free slots + unlaunched tasks | exit 2, stderr names tasks to launch | Unit |
| TS-4 | Stop hook pass-through cases (failed task present / no pending / no free slot / cap of 3 exceeded) | exit 0 (warning on cap path); cap resets on state change | Unit |
| TS-5 | Launch guard decisions (first launch allow+`launched` append / in-flight deny / retry-after-failed allow / merged deny / non-implementer ignore) | per-case decision and journal effect | Unit |
| TS-6 | Concurrent journal appends (parallel merges) | every journal line parses as JSON; no torn lines | Integration |
| TS-7 | Failure net (implementer stop without `merged` → `failed` append; merged/failed/non-implementer stops → no append) | per-case journal effect; always exit 0 | Unit |
| TS-8 | hooks.json registration | valid JSON; Stop / PreToolUse(Task) / SubagentStop + Bash guard entries; referenced scripts exist | Unit |
| TS-9 | Malformed journal line during replay | line skipped; derivation unaffected; no crash | Unit |
| TS-10 | Hook fail-open on broken environment (missing journal/feature-docs, malformed stdin) | exit 0, no crash, in all three hooks | Unit |

## Code Quality Verification
- Format: (none configured) / Static analysis: (none configured)

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | All FRs implemented and tested | TS-1..TS-10 pass + M-1..M-4 checked |
| SC-2 | `python3 -m unittest discover -s tests` passes | run in integration worktree |
| SC-3 | No chunk barriers remain in implement-phase.md Step I.2 | M-1 |
| SC-4 | No new runtime dependencies | M-3 |
| SC-5 | Documentation reflects the journal / workflow.yaml role split | M-2 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0005 | M-1 (queue-loop protocol conformance) |
| FR2 | task0001, task0002, task0003, task0004 | TS-1, TS-5, TS-6, TS-7, TS-9 |
| FR3 | task0001 | TS-1, TS-2 |
| FR4 | task0002 | TS-3, TS-4 |
| FR5 | task0003 | TS-5 |
| FR6 | task0004 | TS-7 |
| FR7 | task0005 | TS-8 |
| FR8 | task0005 | M-2 |
| NFR1 | task0002, task0003, task0004 | M-3 (+ per-task stdlib-only ACs) |
| NFR2 | task0001, task0003, task0004 | TS-6 |
| NFR3 | task0005 | M-4 |
| NFR4 | task0001, task0002, task0003, task0004, task0005 | SC-2 (suite runs and passes) |

## E2E Testing
(no E2E framework in this repository — omitted)

## Manual Testing (E2E Not Possible)
- [ ] M-1: implement-phase.md Step I.2 describes background launch +
  notification-driven refill; no chunk-barrier mechanics remain; unchanged
  invariants (identifier gate, I.1, three-option failure flow,
  trust-but-verify, resume guard) are still present (FR1).
- [ ] M-2: em-workflow/README.md and workflow-schema.md state the role
  split (journal = machine-written raw event log; workflow.yaml =
  LLM-managed summary SSOT) and workflow-schema.md names the journal path
  formula (FR8).
- [ ] M-3: the three new hook scripts import Python stdlib modules only;
  merge-task.sh gained no new external tool dependencies beyond the
  already-required git/flock (NFR1).
- [ ] M-4: the rewritten protocol documents resume/reconcile from
  workflow.yaml + journal + git state, and the stale-`launched` caveat
  with its bounds (NFR3).

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Journal writers (merge-task.sh) | TS-1, TS-2, TS-6 | 3 | 0 | 0 |
| Hooks | TS-3, TS-4, TS-5, TS-7, TS-9, TS-10 | 6 | 0 | 0 |
| Wiring & docs | TS-8, M-1, M-2, M-3, M-4 | 1 | 0 | 4 |
