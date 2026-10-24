# Verification Document: self-write-exclusivity-window

## Overview
**Feature**: self-write-exclusivity-window / **SPEC.md**: `feature-docs/self-write-exclusivity-window/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/self-write-exclusivity-window/IMPLEMENTATION.md`

## Build Verification
- Command: none (`project.components.main.build_command` is empty)
- Expected: not applicable

## Test Verification
- Command: `python3 -m unittest discover -s tests` (run from the repository root)
- Expected: exit code 0, no failures, no errors
- Coverage target: not applicable — the change is Markdown protocol text pinned by document tests; every new probe has a forged-text control instead of a coverage figure

### Test Scenarios from SPEC.md

TS-1 to TS-8 are SPEC.md's scenarios. TS-9 to TS-12 are derived from SPEC.md's
non-functional requirements and AC-6.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | `worker-envelope.md` "Exclusivity assumption during dispatch": the interval's end names the recording phase-state write (`artifacts`, `self_write_set`), the empty-`written_artifacts` variant and the stale judgment | Probes pass on the document; a forged section ending "through the end of that dispatch's scope verification" makes them fire | Unit |
| TS-2 | `create-spec-phase.md` "Scope of applicability": same as TS-1, and the end-point elements match TS-1's | Probes pass; a forged paragraph ending "through the end of verification" makes them fire | Unit |
| TS-3 | R1 "Order": after the four existing step anchors and before the recording write, the return-time recheck appears with the orchestrator as actor, blob id / mode / kind, the scope verification's observed values, and stale on mismatch or failure | Order and element probes pass; a forged Order block without the recheck makes them fire | Unit |
| TS-4 | Existing Order, Known limit and digest-sentence tests in `tests/test_self_write_digest_docs.py` | Pass unchanged | Unit |
| TS-5 | R1 "Known limit" keeps its three existing phrases and states that a change after the scope verification is detected by the return-time recheck, the remaining window resting on the exclusivity assumption | Probes pass; the pre-change Known limit makes them fire | Unit |
| TS-6 | `artifact-digest.md` "Layer 5 recording" `When:` cites R1, keeps "after layer 4 … passes", and places `Calculation` after the comparison and the recording write after the return-time recheck | Probes pass; the pre-change `When:` paragraph makes them fire | Unit |
| TS-7 | The three dispatch sites: `scripts/self-write-digest.py` → (create-plan: `validate-worker-output.py`; rework: `step 3 validates`) → return-time recheck reference citing R1 → `Layer 5 recording`; no restatement of the recheck | Order, citation and no-restatement probes pass; each pre-change site text makes them fire | Unit |
| TS-8 | Whole suite | `python3 -m unittest discover -s tests` exits 0 | Integration |
| TS-9 | R1 structural invariants: each R1 label appears exactly once with no new label; no `expect_digest` token in `worker-envelope.md`; the normalization paragraph, the seven `digest_source` keys and the timing paragraph's existing sentences unchanged; every digest sentence of the R1 region names the orchestrator or is negated; `worker_digest_stance` passes | Existing tests in `tests/test_self_write_digest_docs.py` (`TestRuleR1SelfWriteRule`, `TestDigestStanceInvariants`, `TestUnchangedStructure`) pass unchanged | Unit |
| TS-10 | Out-of-scope files are unchanged: the feature's diff against `main` touches none of `em-workflow/scripts/self-write-digest.py`, `em-workflow/references/phase-state.md`, `em-workflow/references/contracts/analyst-contract.md`, `em-workflow/references/contracts/spec-writer-contract.md`, `em-workflow/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, and leaves the final paragraph of `artifact-digest.md` "Pre-dispatch verification" as it was | `git diff --name-only main...` on the integration branch lists none of these files; the paragraph's text is identical to `main` | Integration |
| TS-11 | Form of the new document tests: standard library only; `test_<target>.py` / `Test<Behavior>` / `test_<condition>_<expected_result>` naming; heading slicing with whitespace normalization; no line-break or whole-document dependence; a forged-text control for every probe | Reviewer confirms each new test file against these points | Manual |
| TS-12 | Reproduction walkthrough (SPEC AC-6): designer dispatched with `extend_only` on `tokens.yaml`; an external process rewrites an existing key right after the scope verification. Trace the revised R1 "Order" | The trace ends stale at the return-time recheck (blob id mismatch on `tokens.yaml`); no recording write happens, so the rewritten content is not recorded at Layer 5 | Manual |

## Code Quality Verification
- Format: none (`project.components.main.format_command` is empty)
- Static analysis: none configured; the plugin invariant checks this feature depends on (`worker_digest_stance`, `dispatch_digest_wiring`) run inside the test suite (TS-8)

## SPEC.md Compliance

### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | All functional requirements are implemented and tested | Functional Requirements Coverage below; TS-1 to TS-8 pass |
| SC-2 | All test scenarios pass | TS-1 to TS-12 |
| SC-3 | AC-1 to AC-7 of SPEC.md are met | AC-1: TS-3, TS-4; AC-2: TS-1, TS-2; AC-3: TS-4, TS-5; AC-4: TS-6; AC-5: TS-7; AC-6: TS-12; AC-7: TS-8, TS-11 |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-3, TS-4, TS-12 |
| FR2 | task0001 | TS-3, TS-4, TS-12 |
| FR3 | task0002 | TS-1, TS-2 |
| FR4 | task0002 | TS-1, TS-2 |
| FR5 | task0001 | TS-4, TS-5 |
| FR6 | task0003 | TS-6 |
| FR7 | task0004 | TS-7 |
| FR8 | task0001, task0002, task0003, task0004 | TS-8, TS-11 |
| NFR1 | task0001, task0002, task0003, task0004 | TS-8, TS-11 |
| NFR2 | task0001, task0002, task0003, task0004 | TS-11 |
| NFR3 | task0001, task0002, task0003, task0004 | TS-4, TS-8, TS-9 |
| NFR4 | task0001 | TS-9 |
| NFR5 | task0001, task0002 | TS-9 |
| NFR6 | task0001 | TS-3, TS-10 |
| NFR7 | task0001, task0002, task0003, task0004 | TS-10 |

## Manual Testing (E2E Not Possible)
- [ ] TS-11: review each new test file under `tests/` for the listed form points
- [ ] TS-12: walk the reproduction steps through the revised R1 "Order" and confirm the stale outcome with no Layer 5 record

## Performance / Security Verification (if applicable)
- TM-1: return-time recheck before the recording write (R1 "Order", cited by `artifact-digest.md` "Layer 5 recording" and the three dispatch sites) — checked by TS-3 (rule text and order), TS-6 and TS-7 (citations and order), and TS-12 (reproduction ends stale with nothing recorded)
- TM-2: exclusivity interval through the recording write in both documents, and Known limit pointing the remaining window at it — checked by TS-1, TS-2 (same end point in both documents) and TS-5 (Known limit)

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS-n) | 12 | 10 (TS-1 to TS-10) | 0 | 2 (TS-11, TS-12) |
| Code quality | 0 | 0 | 0 | 0 |
| Security (TM-n) | 2 | 2 (TM-1, TM-2) | 0 | 0 |

TM-1 is additionally covered by the manual TS-12; it is counted once, under
Automated.
