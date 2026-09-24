# Verification Document: divergence-fail-open-wording

## Overview

**Feature**: divergence-fail-open-wording / **SPEC.md**: `feature-docs/divergence-fail-open-wording/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/divergence-fail-open-wording/IMPLEMENTATION.md`

## Build Verification

- Command: none (`project.components.main.build_command` is empty)
- Expected: not applicable

## Test Verification

- Command: `python3 -m unittest discover -s tests` (run at the repository root)
- Expected: exit code 0, no failures or errors
- Coverage target: not applicable (no coverage tooling is configured in `project.components`)

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Extract the I.2.a section of the current `implement-phase.md` and normalize whitespace; take the divergence span from the start of UNLAUNCHED_SOLELY_FROM_ABSENCE_PHRASE through the end of AUTHORITATIVE_SOURCE_PHRASE | The span contains no "fail-open" substring | Unit |
| TS-2 | Check the I.2.a section for the new DIVERGENCE_REASON_PHRASE (missed-first-launch detection rationale) and for the phrase stating that the false BLOCK is bounded by the consecutive-block cap (3) | Both phrases are present | Unit |
| TS-3 | Check the I.2.a section for the phrases stating that I.2.b step 1's reconcile classifies without consulting status, and that `status != merged` takes effect as I.2.a's selection-time filter | Both phrases are present | Unit |
| TS-4 | Check the I.2.b section for the FR3 note phrase and for "the recycled-task-id rule in I.2.a above" | Both are present | Unit |
| TS-5 | Negative proof against verbatim pre-change samples at base 4999893: the divergence paragraph sample and the I.2.b step 1 sample | The divergence sample contains none of the TS-2 / TS-3 phrases and does contain "the hooks are fail-open nets, not authorities"; the I.2.b step 1 sample does not contain the FR3 note phrase | Unit |
| TS-6 | Existing test_plugin_version_parity with em-workflow at 0.2.8 | Passes; both manifests read 0.2.8 | Unit |
| TS-7 | Full suite `python3 -m unittest discover -s tests` | Passes | Integration |

## Code Quality Verification

- Format: none (`project.components.main.format_command` is empty)
- Static analysis: none configured

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | The I.2.a divergence paragraph contains no "fail-open" string | TS-1 |
| AC-2 | The divergence paragraph states both the missed-first-launch detection rationale and that the false BLOCK is bounded by the consecutive-block cap (3) | TS-2 |
| AC-3 | The divergence paragraph states that I.2.b step 1's reconcile also classifies without consulting status, and that `status != merged` takes effect as I.2.a's selection-time filter | TS-3 |
| AC-4 | I.2.b step 1 carries a note that the no-event classification does not consult status and that the merged exclusion is applied by I.2.a's selection; "the recycled-task-id rule in I.2.a above" remains | TS-4 |
| AC-5 | DIVERGENCE_REASON_PHRASE holds the new wording; its positive assertion passes on the current document; the new negative proof asserts against the base 4999893 divergence paragraph sample that the new phrase is absent and the old phrase is present | TS-2, TS-5 |
| AC-6 | The em-workflow version in `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` is 0.2.8 in both | TS-6 |
| AC-7 | `python3 -m unittest discover -s tests` passes at the repository root | TS-7 |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-2, TS-7 |
| FR2 | task0001 | TS-3, TS-7 |
| FR3 | task0001 | TS-4, TS-7 |
| FR4 | task0001 | TS-2, TS-5, TS-7 |
| FR5 | task0001 | TS-6, TS-7 |
| NFR1 | task0001 | TS-7 (existing pins on the hook classification table, its anchor and the I.2.a Select-line raw literal); manual diff check below |
| NFR2 | task0001 | TS-7 (existing pins on the four divergence-paragraph phrases) |
| NFR3 | task0001 | TS-7; manual import check below |

## Manual Testing (E2E Not Possible)

- [ ] Read the rewritten I.2.a divergence paragraph on its own: it does not read as "the orchestrator always applies `status != merged` at classification time" (FR2).
- [ ] Read I.2.b step 1 on its own: the note makes clear that the no-event classification ignores status and that the merged exclusion happens at I.2.a selection (FR3).
- [ ] In both places, the "does not consult status" wording is limited to the no-journal-event classification and cannot be confused with the failed-and-pending recycled-task-id carve-out (SPEC A7).
- [ ] The feature diff against its base does not touch `em-workflow/hooks/queue_stop_guard.py`, the Supporting cast fail-open definition, the hook classification table or its anchor, or the I.2.a Select line (NFR1).
- [ ] The feature diff does not touch `test-docs/recycled-task-id-contract/task0001.tests.yaml` (SPEC A5).
- [ ] The test module adds no import outside the NFR3 allowance (NFR3).
- [ ] The pre-change sample constants match the text of `em-workflow/references/implement-phase.md` at commit 4999893 verbatim (FR4, SPEC A8).

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Unit tests | 6 (TS-1 to TS-6) | 6 | 0 | 0 |
| Integration tests | 1 (TS-7) | 1 | 0 | 0 |
| Code quality | 0 | 0 | 0 | 0 |
| Manual checks | 7 | 0 | 0 | 7 |
