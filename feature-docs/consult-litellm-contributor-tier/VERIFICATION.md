# Verification Document: consult-litellm-contributor-tier

## Overview
**Feature**: consult-litellm-contributor-tier / **SPEC.md**: `feature-docs/consult-litellm-contributor-tier/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/consult-litellm-contributor-tier/IMPLEMENTATION.md`

## Build Verification
- Command: none (project.components.main.build_command is empty)
- Expected: not applicable

## Test Verification
- Command: `python3 -m unittest discover -s tests`
- Coverage target: not applicable. These are document-invariant tests, and
  no coverage tool is configured.

### Test Scenarios from SPEC.md
TS-1 to TS-6 come from SPEC.md. TS-7 and TS-8 are verification-only
change-set checks added by the planner for NFR2 and NFR4, which SPEC.md
gives no scenario.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | In question-resolution.md's Codex consultation procedure, the step 1 range (from `1. **Availability probe.**` to `2. **Wrapper invocation.**`, whitespace-normalized) contains `contributor_consented` and the muse_guard.py --list consent-check command (AC-1 / FR1) | The new TestConsultationProcedureChain case passes | Unit |
| TS-2 | The step 2 range (from `2. **Wrapper invocation.**` to `3. **One turn per call.**`) contains `contributor_consented`, `--litellm muse-spark-contributor`, and `--litellm muse-spark` as a standalone flag value (AC-2 / FR2) | The new case passes. Its standard-form check does not pass on the contributor form alone | Unit |
| TS-3 | Step 1 or step 2 states that every litellm turn of the consultation uses the value and that it is not re-determined per turn (AC-3 / FR4) | The new case passes | Unit |
| TS-4 | Preserved text and existing pins: test_contributor_read_mapping_is_cited_not_restated, test_probe_states_two_entries_in_order, test_wrapper_invocation_carries_the_litellm_flag, TestRegistriesAssignOnlyMuseSpark, TestAC5ChainImmutability (AC-4 / FR3) | All pass, with their assertions unchanged from the base revision | Unit |
| TS-5 | Run the new cases against the pre-fix question-resolution.md (SPEC.md names base revision cca44706). For example, use a temporary checkout of that revision outside the integration worktree that carries the revised test file (AC-5 / FR5) | Every new case fails there and passes at HEAD | Unit (regression detection) |
| TS-6 | Run the full suite (AC-6 / NFR1, NFR3) | `python3 -m unittest discover -s tests` exits 0 | Unit |
| TS-7 | Planner-added (NFR2): list the feature's changed paths from the implement base commit 68686d3a to HEAD | No changed path ends in .claude-plugin/plugin.json or .claude-plugin/marketplace.json | Change-set check |
| TS-8 | Planner-added (NFR4): the same changed-path list | No changed path has the final segment run_codex_exec.sh, muse_guard.py, reviewers.yaml or review-phase.md | Change-set check |

## Code Quality Verification
- Format: none configured (format_command is empty) / Static analysis: none configured
- Import check (NFR1): the cases added to tests/test_consultation_harness_chain.py import only Python standard-library modules

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | SPEC.md AC-1 to AC-6 are all met | TS-1 to TS-6, plus the manual reading items below for the wording parts of AC-1 and AC-3 |
| SC-2 | TS-1 to TS-6 all pass | The Test Verification command, plus the TS-5 procedure |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1 |
| FR2 | task0001 | TS-2 |
| FR3 | task0001 | TS-4 |
| FR4 | task0001 | TS-3 |
| FR5 | task0001 | TS-5 |
| NFR1 | task0001 | TS-6, import check |
| NFR2 | task0001 | TS-7 |
| NFR3 | task0001 | TS-6 |
| NFR4 | task0001 | TS-8 |

## E2E Testing
Omitted. No E2E framework exists, and SPEC.md A-1 excludes an automated
reproduction of a real batch run.

## Manual Testing (E2E Not Possible)
- [ ] Read the revised steps 1 and 2 the way the orchestrator follows them,
  literally. Step 2 offers the litellm invocation only through the
  `contributor_consented` condition, and no single fixed model name remains
  as the only example. This covers SPEC.md's completion item that the
  reproduction steps no longer show the defect (A-1).
- [ ] Follow the procedure for a consultation that starts on codex and moves
  to litellm partway through. The step-1 value is reused, and the check is
  not run again (FR4 edge case).
- [ ] Confirm that step 1 says the check runs only when the litellm entry is
  available and before the first turn, and states both the true case and
  the false case (AC-1 wording).

## Performance / Security Verification
- TM-1: the contributor tier is used only after a successful one-line
  consent check. Empty output or any failure (failure takes precedence over
  the one-line rule) yields the standard tier, so the procedure fails
  closed. How it is checked: the new TestConsultationProcedureChain case
  asserts the failure-precedence statement in the step 1 range (it runs as
  part of TS-6). The first manual reading item confirms that step 2 offers
  the contributor-tier invocation only when `contributor_consented` is true.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS-1 to TS-8) | 8 | 8 | 0 | 0 |
| Code quality (import check) | 1 | 0 | 0 | 1 |
| Manual testing | 3 | 0 | 0 | 3 |
| Security (TM-1) | 1 | 1 | 0 | 0 |
| Total | 13 | 9 | 0 | 4 |
