# Verification Document: codex-fallback-review-residuals

## Overview

**Feature**: codex-fallback-review-residuals / **SPEC.md**: `feature-docs/codex-fallback-review-residuals/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/codex-fallback-review-residuals/IMPLEMENTATION.md` / **THREAT-MODEL.md**: `feature-docs/codex-fallback-review-residuals/THREAT-MODEL.md`

All commands run from the integration worktree root.

## Build Verification

- Command: none. Both components in workflow.yaml (`repo-tests`, `plugin-invariants`) declare an empty `build_command`.
- Expected: not applicable.

## Test Verification

- Command (`repo-tests`): `python3 -m unittest discover -s tests`
- Command (`plugin-invariants`): `python3 em-workflow/scripts/check-plugin-invariants.py .`
- Expected: both exit 0.
- Coverage target: not measured. The suite is standard-library `unittest` with no coverage tooling (NFR5); completeness is judged by every scenario below passing.

### Test Scenarios from SPEC.md

Scenario IDs are hyphen-less to string-match workflow.yaml's `requirements.*.tests`. TS1-TS7 come from SPEC.md; TS8 is a verification-only inspection added at planning for the change-set constraints NFR1, NFR2, NFR6 and NFR8 state.

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS1 | Read `em-workflow/README.md`'s `--batch` bullet: the old fail-closed clause is absent; the bullet names the relaxed route for security, license and irreversible questions in batch and the interactive abort; it cites `references/question-resolution.md` with "The batch relaxation" / "The surviving aborts"; negative-proof fixture with the old clause is caught | All assertions in `tests/test_readme_batch_relaxed_route.py` pass | Unit |
| TS2 | Slice `question-resolution.md`'s `### Opus escalation` section; extract the dispatch literal and the contract path; the agent file and the contract file exist; agent frontmatter `name` equals the stem, `model: opus`, `effort: xhigh`, `tools` disjoint from {Write, Edit, NotebookEdit}; no `# Task assignment` heading; the README agent table lists `opus-escalation`; a forged frontmatter carrying Write is rejected by the tools matcher | All assertions in `tests/test_opus_escalation_agent_contract.py` and the README-row assertions in `tests/test_readme_batch_relaxed_route.py` pass | Unit |
| TS3 | Read the contract: delimited untrusted-data block and its stated boundary for the input; per-question return contract (an `option_id` from the question's own `options[].option_id` or an explicit no-decision, reasoning in both cases); updated `test_opus_escalation_return_shape` asserts the section cites the contract path and the contract carries the return shape; the other Opus escalation pins still pass on the section | All assertions in `tests/test_opus_escalation_agent_contract.py` and `tests/test_question_resolution_doc.py` pass | Unit |
| TS4 | The section states the non-packet scope: one dispatch per non-packet gate resolution; at most one per distinct literal command string for the per-command approval fallback; a no-decision falls to the minimum-side-effect option. The contract defines how a non-packet gate's choices become one question's `options[]` with `option_id`s and the section cites it. The per-packet sentences are still present | Assertions in `tests/test_opus_escalation_agent_contract.py` pass | Unit |
| TS5 | Slice phase-state.md's `## Batch audit record file`: the general mapping maps the escalation-decided non-packet case to `batch-codex-consultation` under the route-naming reading, including when no Codex turn ran; the Non-packet gates writer's `resolution_note` names whether the escalation ran and its reasoning; a YAML worked example carries a non-packet `question_id`, `packet_id: null`, `source: batch-codex-consultation` and a `resolution_note` saying the escalation ran and Codex was not consulted; the relaxed-route bullet still has exactly one of each source literal | Assertions in `tests/test_batch_quiet_output_audit_record_contract.py` pass | Unit |
| TS6 | With the stub harness of `tests/test_codex_wrapper_single_invocation.py`, run `run_codex_exec.sh readonly --litellm <fictional-model> "prompt"`: exactly one launch; its argv carries `-p`, `litellm`, `-m`, `<fictional-model>` as consecutive elements; the consecutive-sequence matcher rejects a forged argv with a different model value | The new case passes | Integration (subprocess with stubbed CLI) |
| TS7 | Run the full suite and the invariant checker: `tests/test_check_plugin_invariants.py::TestRepositoryLevelInvariant` passes with the new agent present; `tests/test_codex_wrapper_single_invocation.py` (usage-limit passthrough, single launch, provider-fallback module absent) and `tests/test_review_phase_llm_led.py` pass unchanged | Both commands above exit 0 | Integration |
| TS8 | Inspect the feature diff (`workflow.implement.base_commit` to the integration branch head): it touches none of `em-workflow/scripts/run_codex_exec.sh`, `em-workflow/agents/review-evaluator.md`, `em-workflow/references/review-evaluation-contract.md`, `em-workflow/references/batch-policies.yaml`, `em-workflow/references/question-packet-schema.md`, `em-workflow/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`; `tests/test_codex_wrapper_provider_fallback.py` does not exist | No listed path in the diff; the module is absent | Inspection |

SPEC edge cases map onto these scenarios: a no-decision on a non-packet gate falling to the minimum-side-effect option, and the per-command fallback's per-string bound (TS4); the no-harness escalation recording `batch-codex-consultation`, and `batch-safe-default` staying for the minimum-side-effect option (TS5).

## Code Quality Verification

- Format: none declared (`format_command` is empty for both components).
- Static analysis: none declared beyond the invariant checker in TS7.

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | README no longer states that unlisted security, license or irreversible gates abort fail-closed in batch; it states the interactive/batch split and points to `references/question-resolution.md`; a test pins it with a negative proof | TS1 |
| AC2 | The section carries the dispatch literal, the contract path and the Opus/xhigh binding held in frontmatter; agent and contract files exist with the required frontmatter; README lists the agent; the invariant checker exits 0 | TS2, TS7 |
| AC3 | The contract states the delimited untrusted-input boundary and the per-question return contract | TS3 |
| AC4 | The section states the non-packet scope; the presentation rule is defined in one document and cited by the other; per-packet sentences unchanged | TS4 |
| AC5 | phase-state.md's general mapping, Non-packet gates writer note and worked example cover the escalation-decided non-packet case | TS5 |
| AC6 | `test_opus_escalation_return_shape` (or its replacement) asserts the section-to-contract citation and the contract's return shape; no other pin weakened | TS3, TS7 |
| AC7 | `--litellm MODEL` passes verbatim as consecutive `-p litellm -m MODEL` in a single launch, with a non-vacuity proof | TS6 |
| AC8 | The wrapper still launches once and passes usage-limit diagnostics through; the provider-fallback module does not exist | TS7, TS8 |
| AC9 | The full suite passes; no pinned phrase removed except the moved return-shape sentence; `tests/test_review_phase_llm_led.py` passes unchanged | TS7, TS8 |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0002 | TS1 |
| FR2 | task0001 | TS2, TS7 |
| FR3 | task0001, task0002 | TS2, TS3, TS7 |
| FR4 | task0001 | TS4 |
| FR5 | task0003 | TS5 |
| FR6 | task0001, task0002, task0003 | TS1, TS2, TS3, TS4, TS5, TS7 |
| FR7 | task0004 | TS6 |
| NFR1 | task0001, task0003 | TS8 (diff inspection), plus the existing no-new-`gate_id` and closed-vocabulary pins run in TS7 |
| NFR2 | task0004 | TS6, TS7, TS8 |
| NFR3 | task0001, task0002, task0003 | TS3, TS7 |
| NFR4 | task0001, task0002 | TS1, TS3 |
| NFR5 | task0001, task0002, task0003, task0004 | TS7 |
| NFR6 | task0001, task0002, task0003 | TS8 |
| NFR7 | task0001 | TS2, TS7 |
| NFR8 | task0001 | TS7, TS8 |

## Manual Testing (E2E Not Possible)

- [ ] README rendering: in a Markdown preview, the `opus-escalation` row renders inside the agent table, directly after `review-evaluator`, not as stray text.
- [ ] SSOT reading pass (NFR4): reading README's `--batch` bullet, the `### Opus escalation` section, the contract and the agent definition in sequence, no document restates another's conditions or shape; each names its owner instead.
- [ ] Non-packet walkthrough: for a review diff-size gate with no harness available, the section, the contract and phase-state.md alone determine one dispatch, one presented question whose options include the minimum-side-effect option, and an audit record matching the worked example; with a no-decision return, they determine the minimum-side-effect option and `batch-safe-default`.

## Performance / Security Verification

- TM-1: contract-level delimited untrusted-data block with a stated boundary and the dispatcher's closing-delimiter neutralisation; agent treats its whole input as data — checked by the contract and agent-body pins in `tests/test_opus_escalation_agent_contract.py` (TS2, TS3).
- TM-2: agent `tools` limited to Read, Glob, Grep — checked by the frontmatter tools pin and its forged-Write negative proof (TS2).
- TM-3: agent reads limited to the contract and to project-root files named by carried evidence; no writes — checked by the contract read-constraint pin (TS3).
- TM-4: closed per-question return set, invalid entries counted as no-decision, non-packet options including the minimum-side-effect option, orchestrator reading the output as untrusted — checked by the contract return/validity pins, the presentation-rule pin and the retained untrusted-output pins (TS3, TS4).
- TM-5: one dispatch per non-packet gate resolution and at most one per distinct literal command string within a run — checked by the section's non-packet scope pins (TS4).
- TM-6: escalation-decided non-packet gates recorded as `batch-codex-consultation` under the route-naming reading, with `resolution_note` stating whether the escalation ran and its reasoning, plus the worked example — checked by the phase-state.md pins (TS5).

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios (TS1-TS8) | 8 | 7 | 0 | 1 (TS8 inspection) |
| Success criteria (AC1-AC9) | 9 | 9 | 0 | 0 |
| Requirements coverage (FR1-FR7, NFR1-NFR8) | 15 | 15 | 0 | 0 |
| Security mitigations (TM-1-TM-6) | 6 | 6 | 0 | 0 |
| Manual checks | 3 | 0 | 0 | 3 |
