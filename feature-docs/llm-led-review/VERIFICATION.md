# Verification Document: llm-led-review

## Overview

**Feature**: llm-led-review / **SPEC.md**: `feature-docs/llm-led-review/SPEC.md` /
**IMPLEMENTATION.md**: `feature-docs/llm-led-review/IMPLEMENTATION.md`

This feature changes plugin documents, agent prompts and registries only, so
verification is (a) structural assertions that the documents state the new
composition, (b) the plugin invariants checker, and (c) the pre-existing
regression modules whose assumptions the change could break.

## Build Verification

- Command: none — this repository has no build step (`project.components`
  records an empty `build_command` for every component).
- Expected: n/a

## Test Verification

- Command (main): `python3 -m unittest discover -s tests`
- Command (plugin invariants): `python3 em-workflow/scripts/check-plugin-invariants.py .`
- Command (guard hook): `python3 em-workflow/hooks/tests/run-destructive-guard.py`
- Expected: exit code 0 for all three.
- Coverage target: not measured — this suite asserts document structure, not
  executable line coverage; the coverage contract is instead "every FR/NFR is
  named by at least one test scenario below".

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS1 | Structural assertions that `review-phase.md`, `reviewers.yaml`, `review-rules.yaml`, `review-protocol.md`, `review-output-schema.json`, the evaluation contract, the three agent definitions, `skills/review/SKILL.md`, `README.md` and both plugin registries state the new composition (one non-Claude primary reviewer per perspective, the Claude fallback, the single Opus evaluator, the orchestrator's mechanical gates, the untrusted-data treatment, the read-only constraint, the round-record extension, the two confidence corrections) and no longer state the replaced one | All modules pass: `tests/test_review_evaluation_contract.py`, `tests/test_review_phase_llm_led.py`, `tests/test_reviewers_primary_chains.py`, `tests/test_reviewer_roles_protocol.py`, `tests/test_llm_led_review_user_docs.py` | Unit |
| TS2 | `agent_dispatch_parity` regression: the new evaluator definition is dispatched from `review-phase.md`, and `agents/reviewer.md` still has a dispatch site | `check-plugin-invariants.py` reports `agent_dispatch_parity` OK (no undispatched definition, no dispatch of a missing definition); `stale_references` also OK | Integration |
| TS3 | `gate_id` coverage regression: no new gate identifier was introduced, and every existing one still resolves against `batch-policies.yaml` | `check-plugin-invariants.py` reports `gate_id_coverage` OK | Integration |
| TS4 | flock contract regression on the review phase's fix-commit block and its commit-message literal | `tests/test_review_implement_develop_lock_contracts.py` passes | Unit |
| TS5 | codex-reviewer scratchpad temp-file isolation regression (more load-bearing now that the agent runs for every perspective in one message) | `tests/test_codex_reviewer_temp_file_isolation.py` passes | Unit |
| TS6 | Version-bump regression: both registries agree on the em-workflow version and it compares strictly greater than the recorded baseline | `tests/test_plugin_version_parity.py` passes | Unit |
| TS7 | Evaluator accountability and output conformance (rework round 1): no coverage-based discard of a whole evaluation; degradation limited to the two structural triggers; `dismissed_sites` declared in the evaluation contract; an unaccounted reviewer critical/high site lifted individually at confidence 60 with the run's identity and the dispatching perspective; `same_site` the only site predicate; the finding field named `sources` with `source_run_ids` gone; the category gate stated as equality with the source run's dispatched perspective and still drop-not-relabel; the per-perspective independent-inspection duty and the read-only bound | `tests/test_review_evaluation_contract.py` and `tests/test_review_phase_llm_led.py` pass, including their absence assertions for the removed text | Unit |
| TS8 | Fallback reachability (rework round 1): a perspective whose chain walk ends with no completed run — exhaustion or malformed result — receives exactly one Claude fallback dispatch after the walk, never concurrently with a harness reviewer and without consuming the 2-hop budget; `unreviewed_perspectives` keeps its name, root position and non-blocking status but is reachable only after that fallback failed, is carried in the Phase R3a input block, and is stated as carried by the committed round record in batch mode; no new `gate_id` and no `batch-policies.yaml` change | `tests/test_review_phase_llm_led.py` and `tests/test_reviewer_roles_protocol.py` pass; `check-plugin-invariants.py` still reports `agent_dispatch_parity` and `gate_id_coverage` OK | Unit |

## Code Quality Verification

- Format: none — `project.components` records an empty `format_command` for
  every component.
- Static analysis: `python3 em-workflow/scripts/check-plugin-invariants.py .`
  (agent/dispatch parity, stale references, gate-id coverage, domains
  vocabulary parity, forbidden agent heading, fixture branch coverage, digest
  reproducibility).

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | FR1–FR15 are implemented and reflected in the affected documents | TS1 + the per-task acceptance criteria |
| SC-2 | TS1–TS6 all pass | Run the three commands above |
| SC-3 | Security requirements FR5 / FR6 / NFR1 / NFR5 are satisfied | TS1's assertions on the untrusted-data treatment, the mechanical gates (drop-not-relabel, source overwrite, size caps), and the read-only constraint |
| SC-4 | Documentation is complete: review-phase.md / review-protocol.md / reviewers.yaml / README.md | TS1 |
| SC-5 | `python3 -m unittest discover -s tests` passes and the invariants checker's `agent_dispatch_parity` / `stale_references` / `gate_id coverage` pass | TS1–TS6 command runs |
| SC-6 | Both plugin registries carry the same, bumped em-workflow version | TS6 |
| SC-7 | No file under `em-review/` is modified | `git diff --name-only {implement base_commit} HEAD` lists no path starting with `em-review/` |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0002, task0004 | TS1 (R2 dispatches one harness reviewer per perspective; protocol role framing), TS5 |
| FR2 | task0003, task0004 | TS1 (every perspective has a non-empty `primary_chain`; the category enum accepts all six) |
| FR3 | task0002, task0003, task0004 | TS1 (fallback-only branch and agent role framing), TS2 |
| FR4 | task0002 | TS1 (R3a dispatch and the evaluator definition), TS2 |
| FR5 | task0001 | TS1 (the contract's untrusted-data treatment of reviewer output) |
| FR6 | task0002 | TS1 (R3b's ordered mechanical gates) |
| FR7 | task0001, task0002 | TS1 (input block / output object field names, `recommended_action` vocabulary) |
| FR8 | task0002 | TS1 (advisory recommendation; writes, commits and gates stay orchestrator-owned) |
| FR9 | task0002 | TS1 (one-message fan-out, chain-walk retention, evaluator after the walk), TS5 |
| FR10 | task0002, task0003 | TS1 (no-harness fallback, no abort) |
| FR11 | task0005 | TS1 (`skills/review/SKILL.md` describes the same composition and keeps delegating to review-phase.md) |
| FR12 | task0002 | TS1 (round-record path, downstream-read fields, additive `perspective_runs`) |
| FR13 | task0002 | TS1 (only the two mechanical corrections remain; the agreement table is removed) |
| FR14 | task0005 | TS6 |
| FR15 | task0002 | TS2, TS3 |
| NFR1 | task0002 | TS1 (drop-not-relabel, orchestrator-owned `sources`) |
| NFR2 | task0004 | TS5, TS1 (codex availability probe and the optional litellm harness unchanged) |
| NFR3 | task0002 | TS1 (no new AskUserQuestion in the new path), TS3 |
| NFR4 | task0004 | TS1 (freeze assertions on input names, skip strings and existing schema members) |
| NFR5 | task0001, task0002 | TS1 (read-only constraint stated for the evaluator and the reviewers) |
| NFR6 | task0002 | TS4 |

### Rework round 1 additions

The two scenarios above cover the rework tasks synthesized from review round
1. They extend, and never replace, the requirement rows in the table above.

| Requirement | Rework task | Verification |
|-------------|-------------|--------------|
| FR4, FR5, FR6, FR7, FR13, NFR1, NFR5 | task0006 | TS7 (plus TS1, whose modules are the ones TS7 extends) |
| FR1, FR3, FR9, FR10, FR12, NFR2, NFR3 | task0007 | TS8 (plus TS1 and TS2 for the retained dispatch parity) |

## E2E Testing

No E2E framework exists in this repository (`resolved_input_paths.e2e` is
empty), and this feature adds no executable surface. Section omitted
intentionally.

## Manual Testing (E2E Not Possible)

- [ ] Run `/em-workflow:review` (or a develop-driven review round) in an
      environment where the codex CLI is available and confirm that each
      perspective produced exactly one harness reviewer run and one evaluator
      run in the resulting round record.
- [ ] Repeat in an environment without the codex CLI and without the
      `vertex-review` plugin, and confirm the phase completes with Claude
      fallback runs recorded and no abort.
- [ ] Read one produced `reviews/roundN.yaml` and confirm a previous feature's
      older round record is still consumable by `round_context` (same field
      names, same meanings).

## Performance / Security Verification

- NFR1 (injection laundering prevention): TS1 asserts that a finding whose
  `category` is not one of the round's dispatched perspectives is dropped and
  never relabelled, that `sources` are rebuilt from orchestrator-assigned run
  ids, and that the 4096-byte caps and the `file` lexical/existence checks
  remain.
- NFR5 (reviews stay read-only): TS1 asserts the read-only constraint text in
  the evaluation contract and the evaluator definition, and that the evaluator
  definition grants no `Write` / `Edit` tool.
- Performance: no threshold is defined for this feature; the fan-out shape (one
  message, one reviewer per perspective, at most two fallback hops) is verified
  structurally by TS1.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios | 8 | 8 | 0 | 0 |
| Success criteria | 7 | 7 | 0 | 0 |
| Requirements (FR + NFR) | 21 | 21 | 0 | 0 |
| Behavioural confirmation | 3 | 0 | 0 | 3 |
