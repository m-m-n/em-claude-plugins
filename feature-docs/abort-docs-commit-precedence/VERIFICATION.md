# Verification Document: abort-docs-commit-precedence

## Overview

- **Feature**: abort-docs-commit-precedence
- **SPEC.md**: `feature-docs/abort-docs-commit-precedence/SPEC.md`
- **IMPLEMENTATION.md**: `feature-docs/abort-docs-commit-precedence/IMPLEMENTATION.md`

This document covers the integrated verification run by the verify phase.
Task-level acceptance criteria live in `tasks/task0001.md` and `tasks/task0002.md`.
The TS-N scenario IDs below correspond to SPEC.md's TS1-TS8. TS-9 and TS-10 are
added here because SPEC.md lists no scenario for FR9 or NFR4.

## Build Verification

- Command: none configured (`project.components.main.build_command` is empty).
- Manifest well-formedness, in place of a build: both `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` parse as JSON with the Python 3 standard-library JSON tool.
- Expected: exit code 0 for both files.

## Test Verification

- Command: `python3 -m unittest discover -s tests`, run from the repository root.
- Expected: the set of failing test IDs equals the set of failing test IDs on the base commit (`workflow.implement.base_commit`). SPEC NFR3 states that main has 9 pre-existing failures. Compare IDs, not just counts: no new failure, and no baseline failure replaced by a different one.
- Coverage target: not applicable (doc-contract tests over prose; no coverage tooling is configured).

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Slice batch-terminal-line.md's 'Precedence rule:' paragraph from its label to the next blank line and check its statements | The paragraph states the phase-specific-vs-phase-specific rule with `docs_commit_conflict_aborted` as the winner for the Step I.2.c abort-phase terminal status commit's double exit 4. It states the terminal-stop / no-Step-B statement, the retry-success carve-out (`implement_task_failed`) and the written-but-uncommitted distinction, the last with the existing "aborts without writing any status" sentence kept. It confines the rule to that collision, with the I.1 / I.2.a / I.2.b / I.3 exit-4 stops binding to `docs_commit_conflict_aborted` alone. All NFR2 anchors are present, and `no-work-required` is absent. | Unit |
| TS-2 | Run the new Precedence-paragraph matchers against a verbatim pre-change paragraph sample | Every new matcher rejects the pre-change text | Unit |
| TS-3 | Slice implement-phase.md's Branch & Worktree Model section; run the existing I.2.c byte-identity pins | The section names the abort terminal-commit exception. The exception defines the uncommitted `implement: failed` / `failed_kind: decision` write at the second exit 4 and scopes the exception to the "never carries uncommitted state across turns" claim for exactly this stop. It points to develop/SKILL.md Step A. The I.2.c batch-mode paragraph through the end of I.2.c is byte-identical, and the exit-4 bullet phrases are intact. | Unit |
| TS-4 | Slice develop/SKILL.md Step A's existing-workflow.yaml resume branch | It contains the `reset --hard em-workflow/{feature}/integration` refresh of the integration worktree before the Step A.5 hand-off in text order, and states that the refresh runs for batch and interactive resumes before Step B reads workflow.yaml | Unit |
| TS-5 | Check the re-derivation and terminal-line content in the abort terminal-commit exception | It names the committed task status, the retry-consumed marker in `tasks.{T}.notes` and the journal, and states that no additional automatic retry is granted. It requires `detail` to name the call site, the failing task(s) and the uncommitted write, and requires `resume_conditions` to name the resume-entry discard and re-derivation from committed facts. | Unit |
| TS-6 | Run the existing code-set and row-set pins (test_batch_stop_contract.py, test_failed_kind_batch_docs.py) | They pass unchanged: 13 reason codes and 14 Stop point coverage rows, with key/code pairs and order unchanged | Unit |
| TS-7 | Run the existing version-lockstep test (test_implement_routeback_gate.py) and read both manifests | The test passes, and both manifests read `0.2.2` for em-workflow | Unit |
| TS-8 | Run the full `python3 -m unittest discover -s tests` | The failing-test-ID set equals the base commit's baseline set (SPEC: 9 failures on main) | Integration |
| TS-9 | Slice commit-docs.sh's RECOVERY CONTRACT comment block | The unqualified "never carries uncommitted state across turns" justification is gone, and the block names the exception or defers to implement-phase.md. The five FR9 pinned phrases and the byte-pinned carve-out sentence are intact. | Unit |
| TS-10 | Inspect the integrated diff against the base commit for `em-workflow/scripts/` and `em-workflow/hooks/`; run the existing commit-docs.sh executable-body pin | Only commit-docs.sh appears, it has comment-line changes only, and the executable-body pin passes | Integration |

## Code Quality Verification

- Format: none configured (`format_command` is empty).
- Static analysis / repository invariants: `python3 em-workflow/scripts/check-plugin-invariants.py .` from the repository root. Expected: exit code 0.

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | Precedence paragraph names both keys for the abort-terminal-commit stop, and `docs_commit_conflict_aborted` wins | TS-1, TS-2 |
| AC2 | Stop ends the run, with no Step B evaluation of the uncommitted `implement: failed`; retry-success keeps `implement_task_failed` | TS-1 |
| AC3 | Written-but-uncommitted is distinguished from "aborts without writing any status", and the existing sentence is kept | TS-1 |
| AC4 | implement-phase.md Branch & Worktree Model defines the uncommitted write and the named exception | TS-3 |
| AC5 | develop/SKILL.md Step A resume branch refreshes before Step A.5 | TS-4 |
| AC6 | Re-derivation from committed facts with no extra retry; `detail` / `resume_conditions` content stated | TS-5 |
| AC7 | 13 codes and 14 rows are unchanged; other exit-4 call sites bind only to `docs_commit_conflict_aborted` | TS-1, TS-6 |
| AC8 | No new failures versus the baseline; I.2.c byte pins pass | TS-3, TS-8 |
| AC9 | plugin.json and marketplace.json both read 0.2.2 | TS-7 |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2 |
| FR2 | task0001 | TS-1 |
| FR3 | task0001 | TS-1 |
| FR4 | task0002 | TS-3 |
| FR5 | task0002 | TS-4 |
| FR6 | task0002 | TS-5 |
| FR7 | task0002 | TS-5 |
| FR8 | task0001, task0002 | TS-1, TS-3, TS-6 |
| FR9 | task0002 | TS-9 |
| FR10 | task0001, task0002 | TS-7 |
| NFR1 | task0001 | TS-6 |
| NFR2 | task0001, task0002 | TS-1, TS-3, TS-4, TS-8, TS-9 |
| NFR3 | task0001, task0002 | TS-8 |
| NFR4 | task0001, task0002 | TS-9, TS-10 |

## Manual Testing (E2E Not Possible)

- [ ] Read batch-terminal-line.md's Stop point coverage section as a first-time reader. Confirm that exactly one reason code can be derived in each of these three cases:
  - the abort terminal status commit's exit 4 followed by exit 4 on retry;
  - the same commit's exit 4 followed by a successful retry;
  - exit 4 at Step I.1, I.2.a, I.2.b or I.3.
- [ ] Read implement-phase.md's abort terminal-commit exception and develop/SKILL.md Step A together. Confirm that the leftover write's state, its discard point and the next run's re-derivation are determinate, with no path that grants an extra automatic retry, and that no document restates another document's rule.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build (manifest well-formedness) | 2 | 2 | 0 | 0 |
| Unit (doc-contract) | 8 (TS-1 to TS-7, TS-9) | 8 | 0 | 0 |
| Integration | 2 (TS-8, TS-10) | 2 | 0 | 0 |
| Code quality (invariants) | 1 | 1 | 0 | 0 |
| Manual reading checks | 2 | 0 | 0 | 2 |
