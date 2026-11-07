# Feature: large-diff-review-coverage

## Overview

This feature makes the review phase distinguish perspectives that could not be
performed from perspectives that produced no findings, and makes selected
perspectives run even on large diffs. em-workflow gains file-level sharding of
review input, a per-round dispatch cap, and round-record disclosure of unreviewed
and partially reviewed perspectives; em-review adopts only the codex-reviewer
skip handling. The requirements document is
`feature-docs/large-diff-review-coverage/REQUIREMENTS.md`.

## Objectives

- Distinguish perspectives that could not be performed from "no findings"
- Perform the selected perspectives even when the diff is large

## User Stories

No user stories are defined. Acceptance criteria are listed below with the
requirements each one covers.

**Acceptance Criteria:**
- [ ] AC1 (FR1): A Codex run that exits 124 yields skipped:true, skip_reason harness_unavailable, and empty findings, even when its output contains valid JSON.
- [ ] AC2 (FR2, FR3): Codex non-JSON results and litellm results with either of the two fixed summaries do not become completed. If the origin is not litellm, findings is non-empty, or summary does not match, the FR3 handling does not apply.
- [ ] AC3 (FR4): A dispatched perspective that ends with only non-retryable skips appears in unreviewed_perspectives.
- [ ] AC4 (FR5, FR6, NFR4): Input over 200,000 characters always splits into the same composition for the same input, with each file in exactly one shard. Whole-codebase files and untracked files are also measured.
- [ ] AC5 (FR7): With N selected perspectives, the shards per perspective stay at or below floor(24 / N), and the excess is recorded as unreviewed.
- [ ] AC6 (FR8, FR9): run_id values within a round do not collide, and a skip or replacement in one shard does not affect the results of other shards.
- [ ] AC7 (FR6, FR9, FR10): On a diff over 300,000 characters, performance / architecture retain completed runs, and the range that did not complete appears in the record.
- [ ] AC8 (FR11, FR12, FR13): spec executes rescue runs only when every full-diff path has failed, a spec that went through rescue is recorded as partially reviewed, and missing-implementation findings from rescue runs enter neither auto-fix nor residual.
- [ ] AC9 (FR14): When a file that completed before a fix is changed by the fix and the re-review does not complete, that file is recorded as unreviewed.
- [ ] AC10 (FR15, FR16): The completion gate condition is unchanged, and the two fields are present in R6, the batch Reporting section, the source map, and the R3a input.
- [ ] AC11 (FR17): The em-review codex-reviewer returns skipped:true on exit 124 and on non-JSON, and carries no splitting rules.
- [ ] AC12 (NFR1, NFR5): Rounds at or below 200,000 characters are dispatched as a single input, and the reviewer input fields and review-output-schema.json do not change.
- [ ] AC13 (FR18): `python3 -m unittest discover -s tests` and `python3 em-workflow/scripts/check-plugin-invariants.py .` succeed.

## Technical Requirements

### Functional Requirements
- **FR1:** Codex timeout distinction. At the start of Step 6, before JSON parsing and with priority over it, codex-reviewer checks for wrapper exit code 124. On 124 it returns `{"findings": [], "summary": "skipped: codex timed out", "skipped": true, "skip_reason": "harness_unavailable", "source": "codex"}`. Partial findings are not retained. The check uses the exit code only, never the output text.
- **FR2:** Codex non-JSON distinction. When codex-reviewer cannot parse JSON and the case is neither rate-limit nor unsupported-model, it returns `{"findings": [], "summary": "skipped: codex returned non-JSON output", "skipped": true, "skip_reason": "harness_unavailable", "source": "codex"}`.
- **FR3:** litellm empty-result distinction. Phase R2b does not treat as completed a result whose orchestrator-recorded origin is litellm, whose findings is empty, and whose summary exactly matches `litellm model output truncated` or `litellm returned non-JSON output`. That run becomes status: failed, and the existing malformed-result path runs Claude fallback once. All other results keep the schema-conformance-only check.
- **FR4:** Unreviewed disclosure. A dispatched perspective with no completed run is listed in unreviewed_perspectives regardless of whether its last skip_reason is retryable. Perspectives not dispatched because of requires_spec are not listed. Axis 2 runs with source: tool are not listed.
- **FR5:** Review input size measurement. Before the Phase R2 fan-out, the character count of the review input is measured per file. Diff-mode tracked files are measured by that file's diff text; whole-codebase-mode files and standalone untracked files are measured by file content. Input that does not appear in the diff is not omitted from measurement.
- **FR6:** File-level sharding. When the total review input exceeds 200,000 characters, changed_files is split into shards at file granularity. Each shard is at most 200,000 characters. A single file over 200,000 characters forms its own shard. A file belongs to exactly one shard. Each shard builds diff_cmd_quoted from the Phase R0 step 3 validated paths. This applies to all perspectives other than spec and to all harnesses, and the same procedure is used in Phase R2, Phase R4 re-review, develop-driven runs, standalone, diff mode, and whole-codebase mode.
- **FR7:** Dispatch cap. Primary reviewer dispatches per round are limited to 24. Shards per perspective are capped at floor(24 / selected perspective count), and excess shards are deterministically disclosed as unreviewed. Retries and Claude fallback are not counted. Phase R4 re-review applies the same cap separately per loop.
- **FR8:** run_id. run_id identifies the shard, chain entry, and loop. The format is `{perspective}[@s{k}]#[loop{N}.]{chain_index|fallback}`; `@s{k}` is present only when split. Phase R4 runs use `loop{N}.{chain_index|fallback}` so that run_id stays unique when chain walks occur multiple times in one loop.
- **FR9:** Shard-level chain walk. The single Phase R2 reviewer, the up to two Phase R2b fallbacks, the one Claude fallback, and last-result replacement apply per shard rather than per perspective. A result of one shard never replaces a result of another shard.
- **FR10:** review_data_too_large path. Phase R2b in em-workflow adds review_data_too_large to its retry reasons and advances to the next entry on a different harness. When the chain is exhausted, the existing Claude fallback runs.
- **FR11:** spec full-diff priority. The spec perspective is not split and runs the normal chain on the full diff (muse-spark, then Codex self-fetch, then Claude fallback). Only when that entire path fails to complete are shard-level rescue runs executed. A spec that executed rescue runs is disclosed as partially performed even when all shards complete.
- **FR12:** Missing-implementation findings from rescue runs. Missing-implementation findings reported by spec rescue runs are recorded with `resolution: unresolved` and a `resolution_reason` beginning with `unverified`, and are excluded from auto-fix candidates and residual critical/high. The same handling is kept in Phase R4 re-review and on the evaluator-failure path.
- **FR13:** Partial review record. unreviewed_perspectives remains the list of perspectives that were entirely unreviewed. `partially_reviewed_perspectives` is added at the root of the round record and records each perspective where completed runs coexist with an unreviewed range, as a tuple of perspective name, unreviewed files, and reason. It exists as empty when there are none.
- **FR14:** R4 re-review coverage. Each Phase R4 loop rebuilds shards from the current diff. A perspective-file pair counts as reviewed only when a completed run saw that file's final content. A file changed by a fix does not count as reviewed through a pre-fix completed run. A file not changed by a fix keeps its existing completed run.
- **FR15:** Completion and reporting. The completion gate stays residual_critical_high == 0. Phase R6 outputs both unreviewed_perspectives and partially_reviewed_perspectives. The --batch final result also outputs both, and both are added to the `## Reporting` section and the Audit-item source map of batch-mode.md. No new gate is added.
- **FR16:** Evaluator handoff. The Phase R3a input includes unreviewed_perspectives and partially_reviewed_perspectives. Only perspectives in unreviewed_perspectives are exempt from the Independent Inspection Duty. Partially reviewed perspectives remain subject to it.
- **FR17:** em-review alignment. FR1 and FR2 apply to the em-review codex-reviewer, and the skip description in the em-review review-protocol.md is aligned. Splitting, the dispatch cap, and the review_data_too_large path do not apply to em-review.
- **FR18:** Recurrence-detection tests. Size measurement, shard splitting, the dispatch cap, and unreviewed and partial-review determination live in Python scripts under scripts/ and are verified by unit tests in tests/. The rules in agents and references are pinned by text inspection in tests/.

### Non-Functional Requirements
- **NFR1 - Behavior at or below the limit:** In rounds where review input is at or below 200,000 characters, the dispatch count and the meaning of existing round-record fields are the same as today. Only the Phase R4 run_id format follows FR8.
- **NFR2 - vertex-review unchanged:** The feature works without changing the vertex-review plugin.
- **NFR3 - Orchestrator context:** Diff bodies are not placed in the orchestrator's context. Scripts return only paths, character counts, and shard composition.
- **NFR4 - Determinism:** The same input produces the same shards and the same excess shards.
- **NFR5 - Reviewer interface:** The reviewer input fields and review-output-schema.json do not change. A shard is expressed within changed_files and diff_cmd_quoted.
- **NFR6 - Test constraints:** Tests use only the standard library unittest, and shell-related behavior is verified in a disposable git repository in a temporary directory.

## Implementation Approach

### Architecture

**System Architecture:**
```
┌──────────────────────────────────────────────────────────────┐
│ Review phase (R2, R2b, R3a, R4, R6)                          │
│   dispatches per shard, records runs, reports coverage       │
├──────────────────────────────────────────────────────────────┤
│ Python scripts under scripts/ (standard library)             │
│   measurement, splitting, cap, unreviewed/partial decision   │
│   return paths, character counts, shard composition only     │
├──────────────────────────────────────────────────────────────┤
│ Reviewers (input fields and output schema unchanged)         │
│   receive a shard as changed_files and diff_cmd_quoted       │
└──────────────────────────────────────────────────────────────┘
```

**Component Diagram:**
```
Phase R2 ──► scripts (measure, split, cap)
Phase R2 ──► reviewers ──► Phase R2b (per-shard chain walk)
Phase R2b ──► scripts (unreviewed / partial decision) ──► round record
round record ──► Phase R3a input, Phase R6, --batch final result
Phase R4 ──► scripts (rebuild shards from the current diff, per loop)
```

### Data Flow

```
Per-file review input
  → character count per file
  → total ≤ 200,000: single input, as today
  → total > 200,000: file-level shards (spec excluded)
      → cap at floor(24 / selected perspective count) shards per perspective
      → excess shards recorded as unreviewed
      → per-shard reviewer, fallback chain, Claude fallback
  → unreviewed_perspectives / partially_reviewed_perspectives in the round record

spec perspective
  → full-diff chain (muse-spark, Codex self-fetch, Claude fallback)
  → only if the whole path does not complete: shard-level rescue runs
```

### API Design

Not applicable. The reviewer input fields do not change (NFR5).

### Database Schema

Not applicable.

### Round Record

| Field | Required | Description |
|-------|----------|-------------|
| `unreviewed_perspectives` | Yes | List of perspectives that were entirely unreviewed |
| `partially_reviewed_perspectives` | Yes | At the record root. Tuples of perspective name, unreviewed files, and reason. Exists as empty when there are none |

### Dependencies

**Internal Dependencies:**
- Phase R0 step 3: validated paths used to build diff_cmd_quoted for each shard (FR6)
- Phase R2b chain and the existing malformed-result path: reused per shard (FR3, FR9, FR10)
- codex-reviewer in em-workflow and em-review: Step 6 changes (FR1, FR2, FR17)
- em-review review-protocol.md: skip description (FR17)
- batch-mode.md: `## Reporting` and Audit-item source map (FR15)

**External Dependencies:**
- None. Scripts use the Python standard library (A5), and tests use the standard library unittest (NFR6).

### File Structure

Specific paths are derived at create-plan. The locations named by the
requirements are:

```
em-workflow/
├── scripts/      # measurement, splitting, cap, unreviewed/partial decision
tests/            # unit tests and text inspection
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/large-diff-review-coverage/**`
- `test-docs/large-diff-review-coverage/**`

`feature-docs/large-diff-review-coverage/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/large-diff-review-coverage/**` covers `test-docs/large-diff-review-coverage/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/large-diff-review-coverage/` directory at all; the declared
`test-docs/large-diff-review-coverage/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests
- [ ] TS-1: Text-inspect Step 6 of codex-reviewer in both plugins - The exit code 124 check precedes JSON parsing, and the rule to return the specified skip object is present. Covers FR1, FR2, FR17.
- [ ] TS-2: Verify the failed determination for each combination of origin, findings, and summary. Covers FR3.
- [ ] TS-3: In a disposable git repository, verify measurement and splitting for tracked, untracked, whole-codebase, rename, binary, and single-oversized-file inputs. Covers FR5, FR6.
- [ ] TS-4: Verify the shard cap and the determinism of excess shards for selected perspective counts 1 through 6. Covers FR7.
- [ ] TS-5: From combinations of perspective_runs, determine unreviewed, partially reviewed, and post-fix invalidation. Covers FR4, FR13, FR14.
- [ ] TS-6: Verify run_id uniqueness where shards, chains, and loops overlap, and shard-level result replacement. Covers FR8, FR9.
- [ ] TS-7: Text-inspect the R2b table, the spec ordering, rescue-run handling, the completion gate, Reporting, the source map, and the R3a input. Covers FR10, FR11, FR12, FR15, FR16.
- [ ] TS-8: Verify that input at or below the limit forms one shard, and that the schema and Inputs section pins hold. Covers NFR1, NFR5.

### Integration Tests
None.

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases
None beyond the scenarios above.

### Performance Tests
None.

## Security Considerations

No security requirements are defined.

## Error Handling

### Error Codes

| Condition | Result | Requirement |
|-----------|--------|-------------|
| Codex wrapper exit code 124 | Skip object with `skipped: codex timed out`, skip_reason harness_unavailable, empty findings | FR1 |
| Codex output is not parseable JSON, neither rate-limit nor unsupported-model | Skip object with `skipped: codex returned non-JSON output`, skip_reason harness_unavailable, empty findings | FR2 |
| litellm origin, empty findings, and an exact match on one of the two fixed summaries | status: failed; existing malformed-result path runs Claude fallback once | FR3 |
| review_data_too_large in Phase R2b | Advance to the next entry on a different harness; existing Claude fallback when the chain is exhausted | FR10 |

### Error Flow

```
Reviewer result → classified per shard → chain walk within that shard
  → no completed run for the whole perspective: unreviewed_perspectives
  → completed runs and an unreviewed range coexist: partially_reviewed_perspectives
```

## Performance Optimization

### Performance Goals

No performance goals are defined. The 200,000-character limit is an initial
value that does not guarantee completion within 540 seconds (A12).

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] `python3 -m unittest discover -s tests` succeeds
- [ ] `python3 em-workflow/scripts/check-plugin-invariants.py .` succeeds

## Assumptions

- **A1:** The Codex timeout uses the skip_reason harness_unavailable; no new skip_reason is added.
- **A2:** The exit 124 check is placed before JSON parsing and takes priority; the result is skipped:true, harness_unavailable, and empty findings. Partial findings are not retained.
- **A3:** The vertex-review plugin is not changed.
- **A4:** Splitting applies to every path: Phase R2, Phase R4, develop-driven, standalone, diff mode, and whole-codebase mode.
- **A5:** Measurement, splitting, the cap, and unreviewed determination live in Python scripts using the standard library.
- **A6:** review-output-schema.json is not changed.
- **A7:** The version is not bumped by hand.
- **A8:** A missing-implementation finding is one that asserts the implementation corresponding to a requirement is absent from the visible diff, rather than an error at a changed location. The orchestrator makes the determination, and an undeterminable finding is treated as missing-implementation.
- **A9:** FR3 results do not create a skip_reason and take the existing malformed-result path.
- **A10:** The selected perspective count includes Task-dispatched perspectives, spec included, and excludes axis 2 vulnerability. spec rescue runs are capped at floor(24 / selected perspective count).
- **A11:** Excess shards are chosen from the end of the shards ordered by path.
- **A12:** 200,000 characters is an initial value that does not guarantee completion within 540 seconds.
- **A13:** Missing a design issue that spans shards is a known constraint. The shard investigation budget stays at the existing 3 files.

## Open Questions

None.

## References

- Requirements document: `feature-docs/large-diff-review-coverage/REQUIREMENTS.md`
