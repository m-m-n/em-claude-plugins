# Feature: batch-stop-contract

## Overview

em-workflow's batch mode currently has no machine-readable way to express that a run stopped inside the workflow. This feature defines an output contract: a fixed-prefix terminal line emitted at the end of a batch run, carrying the terminal state and — when the run stopped — the stopping step and a stop reason. The contract is written into an SSOT document and pinned by a documentation contract test.

Requirements source: `feature-docs/batch-stop-contract/REQUIREMENTS.md`.

## Objectives

- Emit the fact that an em-workflow batch run stopped inside the workflow in a machine-readable form.
- Make normal completion and stopping structurally distinguishable without depending on the caller process's exit code.
- Include the stopping step and the stop reason in the stop output.
- State that output contract in `em-workflow/references/batch-mode.md` (or the SSOT it points to) and pin it with a documentation contract test.
- Keep em-workflow's responsibility at declaring the stop; do not reach into an external task-management service's status transitions.

## User Stories

### US1: Distinguishing completion from a stop in an unattended run
As the caller process of an unattended batch run, I want to read a single fixed-prefix terminal line from the output, so that I can tell normal completion from a stop — and tell both from a crash or a truncated turn — without relying on the exit code.

**Acceptance Criteria:**
- [ ] A terminal line is defined that is emitted on both normal completion and stop, in the same format (FR1).
- [ ] The absence of the line is itself detectable as an abnormal outcome (crash / truncation) (FR1).
- [ ] The prefix is uniquely identifiable in unattended-run logs and does not collide with ordinary prose or with the example lines inside the contract document (NFR5).

### US2: Locating a stop from the output alone
As a human reviewer receiving the output through an external service, I want the terminal line to name the step that stopped and why, so that I can locate the stop without reading the whole run.

**Acceptance Criteria:**
- [ ] The stop terminal line carries the stopping step identifier and the stop reason (FR2).
- [ ] The stop reason is one of a closed set of stable reason codes, accompanied by a free-form human-facing `detail` (FR2).
- [ ] Every terminating stop point enumerated in FR5 maps to one of those reason codes (FR5).
- [ ] `detail` carries no confidential information, since the line is relayed to a human reviewer through an external service (NFR6).

## Technical Requirements

### Functional Requirements

- **FR1 — Machine-readable terminal state:** At the end of a batch-mode run, emit the terminal state as a single fixed-prefix line inside the final assistant message. Emit a line of the same format both on normal completion and on stop, so that the absence of the line is itself detectable as an abnormal outcome (crash / truncation).
- **FR2 — Stopping step and stop reason carried in the line:** The stop terminal line includes the identifier of the step that stopped and the stop reason. The stop reason is expressed as a closed set (enum) of stable reason codes, accompanied by a free-form human-facing `detail`.
- **FR3 — Output contract stated in the SSOT:** State the output contract in `em-workflow/references/batch-mode.md`, or in an SSOT referenced from it. Follow the existing SSOT-partition discipline: do not restate another document's content, create a pointer to it instead.
- **FR4 — No regression of existing success output:** Do not break the format of the Step C 3. completion report (`em-workflow 完了: {feature}` / the retained branch name and merge-in guidance / the PR URL / the `license none` single line / the batch audit items). The terminal line is defined as an additional line that coexists with them.
- **FR5 — Enumeration of covered stop points:** The contract covers every terminating stop point. Specifically: stop condition 2 (stuck), 3 (`failed` / `needs_update`), 4 (YAML parse error) and 6 (git-setup abort), plus phase abort from `question-resolution.md`'s fail-closed classification, `batch-policies.yaml`'s `on_unavailable: abort`, `implement.failed-task`'s abort phase on a second `failed` for the same task, `verify.failed` reaching the rework cap, and Step C's abort (dirty main working tree / `git worktree remove` failure). Each is enumerated and bound to a reason code of the terminal line.
- **FR6 — Representing wait turns and step-less stops:** A turn that ends at stop condition 5 (waiting for implementer notification) emits no terminal line. A stop where no `workflow.yaml` step is established (Step 0 git-setup abort / Step A feature-resolution failure) is assigned a fixed sentinel step value that is carried in the terminal line.
- **FR7 — No encroachment on external-service responsibility:** em-workflow does not edit an external task-management service's task page body or status property. The contract states explicitly that declaring the stop is where the responsibility ends.
- **FR8 — Documentation contract test:** Add a documentation contract test under `tests/` that pins the output contract, and leave `python3 -m unittest discover -s tests` passing.
- **FR9 — Version bump:** Patch-bump the `version` in `em-workflow/.claude-plugin/plugin.json` and in `.claude-plugin/marketplace.json` to the same value (both are currently `0.1.39`).

### Non-Functional Requirements

- **NFR1 — Dependencies:** Test code uses the Python standard library only. Do not pull runtime dependencies such as PyYAML into the test dependencies.
- **NFR2 — Compatibility:** The whole suite passes without modifying any existing test module.
- **NFR3 — Simplicity:** Producing the terminal line requires no external tool and no additional dependency (a single line of text output only).
- **NFR4 — Test quality:** Contract-test assertions are expressed as durable invariants rather than fixed literals, with a negative proof and a non-vacuity guard per matcher (the existing convention of `tests/test_routeback_reset_scope_version_bump.py`).
- **NFR5 — Observability:** The terminal line's prefix is uniquely identifiable in unattended-run logs and does not collide with ordinary prose or with example lines inside contract documents.
- **NFR6 — Security:** The stop reason's `detail` contains no confidential information. The terminal line is relayed to a human reviewer through an external service.
- **NFR7 — Verifiability:** Stop reason codes are enumerated in the contract document as a closed set, written so that a contract test can inspect the correspondence between that set and the stop points.

## Implementation Approach

### Architecture

This feature changes documents and tests only. Per assumption `a1`, the change surface is limited to the SSOT Markdown / YAML documents, the Python tests under `tests/`, and the two JSON manifests; no runtime code (hooks / scripts) behaviour changes.

```
em-workflow/references/batch-mode.md      ← contract statement (FR3), or a pointer to the SSOT holding it
em-workflow/skills/develop/SKILL.md       ← stop conditions 2-6 and Step C completion report (FR4, FR5, FR6)
tests/                                    ← documentation contract test pinning the contract (FR8)
em-workflow/.claude-plugin/plugin.json    ← version (FR9)
.claude-plugin/marketplace.json           ← version (FR9)
```

### Data Flow

```
batch run ends
  ├─ normal completion → existing Step C 3. report lines (FR4) + terminal line (FR1)
  ├─ terminating stop   → terminal line with step + reason code + detail (FR1, FR2, FR5)
  ├─ stop condition 5 (waiting) → no terminal line (FR6)
  └─ crash / truncation → no terminal line ⇒ detected as abnormal by its absence (FR1)

terminal line → unattended caller process (parse)
             → external task-management service → human reviewer (relay only; FR7, NFR6)
```

### Terminal-line structure

Defined by FR1, FR2 and FR6; the concrete field encoding is settled when the contract text is written.

| Element | Requirement | Notes |
|---|---|---|
| Fixed prefix | FR1, NFR5 | Single line inside the final assistant message; unique in logs |
| Terminal state | FR1 | Same format for completion and for stop |
| Step identifier | FR2, FR6 | Sentinel value when no `workflow.yaml` step is established |
| Stop reason code | FR2, NFR7 | Closed enum, enumerated in the contract document |
| `detail` | FR2, NFR6 | Free-form, human-facing, no confidential information |

### Stop-point coverage (FR5)

Every entry below must bind to a reason code in the contract document.

| Stop point | Source |
|---|---|
| Stop condition 2 (stuck) | `skills/develop/SKILL.md` |
| Stop condition 3 (`failed` / `needs_update`) | `skills/develop/SKILL.md` |
| Stop condition 4 (YAML parse error) | `skills/develop/SKILL.md` |
| Stop condition 6 (git-setup abort) | `skills/develop/SKILL.md` |
| Phase abort by fail-closed classification | `references/question-resolution.md` |
| `on_unavailable: abort` | `references/batch-policies.yaml` |
| Abort phase on a second `failed` for the same task | `implement.failed-task` |
| Rework cap reached | `verify.failed` |
| Step C abort (dirty main working tree / `git worktree remove` failure) | `skills/develop/SKILL.md` |

Stop condition 5 (waiting for implementer notification) is explicitly excluded from terminal-line emission (FR6).

### Dependencies

**Internal Dependencies:**
- `em-workflow/references/batch-mode.md`: the document that states the contract, or points to the SSOT that does (FR3).
- `em-workflow/skills/develop/SKILL.md`: source of the stop conditions and of the Step C completion report guarded by FR4.
- `em-workflow/references/question-resolution.md`, `em-workflow/references/batch-policies.yaml`: sources of two covered stop points (FR5).

**External Dependencies:**
- None. Test code uses the Python standard library only (NFR1), and terminal-line emission needs no external tool (NFR3).

## Test Scenarios

Test command: `python3 -m unittest discover -s tests`. The project has no build, format or E2E command.

### Documentation Contract Tests

- [ ] **TS1** (FR1, FR3): Assert against the contract document body that the SSOT defines the terminal line's prefix, its field composition, and the fact that it is emitted on both completion and stop.
- [ ] **TS2** (FR2, NFR7): Assert that the contract SSOT enumerates a closed set of stop reason codes and that each code is accompanied by a step field and a `detail` field. Extract the set as a set and also check it has no duplicates and no empty members.
- [ ] **TS3** (FR5): Assert that every stop point listed in FR5 (stop conditions 2/3/4/6, fail-closed abort, `on_unavailable: abort`, second `failed` in implement, verify cap reached, Step C abort) is bound to some reason code in the contract document, as a bidirectional coverage check between the stop-point list and the mapping table.
- [ ] **TS4** (FR6): Assert that the contract document states "no terminal line on a stop-condition-5 wait turn", and that a sentinel step value for step-less stops is defined.
- [ ] **TS5** (FR4): Regression guard — assert that the Step C completion report in `skills/develop/SKILL.md` still carries `em-workflow 完了: {feature}`, the branch-name guidance, the PR URL, the `license none` single line and the batch audit items.
- [ ] **TS6** (FR7): Assert that the contract document states that em-workflow performs no status operation against the external task-management service.
- [ ] **TS7** (FR9, NFR4): Assert that `plugin.json` and `marketplace.json` parse as JSON, that `version` is in the `0.1` series with patch > 39, and that the two match as strings. Place a negative proof (rejecting a forged `0.1.39` and a mismatched pair) and a non-vacuity guard (the forged value is well-formed) per matcher.
- [ ] **TS8** (NFR1, NFR2, NFR5): Verify that the added module imports the standard library only, that the whole `python3 -m unittest discover -s tests` suite passes with existing modules unmodified, and that the terminal-line prefix appears only in the contract document's example lines and in the test's expected values — never incidentally in prose.

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

## Security Considerations

- **Data Protection:** The stop reason's `detail` carries no confidential information, because the terminal line is relayed to a human reviewer through an external service (NFR6). Per assumption `a3`, nothing beyond paths is included in `detail`.
- **External-service boundary:** em-workflow does not edit the external task-management service's task page body or status property (FR7); the relay direction is outbound only.
- **Authentication / Authorization / XSS / SQL injection / CSRF:** Not applicable. The change surface is documents, tests and manifests; no request-handling or data-storage code is involved.

## Error Handling

The terminal line is itself the error-reporting surface for a stopped run: each terminating stop point maps to a reason code (FR5), and each stop terminal line carries the step and a `detail` (FR2). A run that produces no terminal line at all — outside the stop-condition-5 wait turn (FR6) — is to be read as a crash or a truncated turn (FR1).

## Success Criteria

- [ ] A terminal line that machine-readably distinguishes normal completion from a stop is defined (single fixed-prefix line, identical format for both).
- [ ] The stop terminal line carries the stopping step and the stop reason (closed enum + free-form `detail`).
- [ ] The set of stop reason codes is enumerated in the contract document, and every stop point listed in FR5 maps to one of them.
- [ ] That output contract is stated in `em-workflow/references/batch-mode.md` (or the SSOT it points to).
- [ ] The existing success output (`em-workflow 完了: {feature}` / the integration branch-name line / the PR URL line / the batch audit items) keeps its format.
- [ ] The contract explicitly states that no terminal line is emitted on a stop-condition-5 wait turn.
- [ ] A fixed sentinel step value is defined for step-less stops (Step 0 / Step A).
- [ ] The corresponding documentation contract test is added under `tests/`.
- [ ] `python3 -m unittest discover -s tests` passes.
- [ ] `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` carry the same bumped `version`.

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

None. Every FR and NFR is `resolved`.

## Recorded Assumptions

Analyst-derived assumptions:

- **a1** (impact medium, reversible): The change surface of this feature is limited to the SSOT Markdown / YAML documents, the Python tests under `tests/`, and the two manifests; no runtime code (hooks / scripts) behaviour change is involved. Reason: the acceptance criteria consist entirely of documents, contract, tests and a version bump, and no implementation artifact is specified.
- **a2** (impact low, reversible): Declaring the stop ends at em-workflow's own output; the external task-management service's status transition is not implemented. Reason: stated in the task description's out-of-scope clause and as a notion-batch-develop convention.
- **a3** (impact low, reversible): The stop reason's `detail` contains no confidential information beyond paths, because the stop output is relayed to a human through an external service. Reason: `batch-mode.md`'s Reporting defines the external service as the sole confirmation surface relaying to a human reviewer.

Batch-resolved assumptions — decided by Codex consultation in batch mode with `record_as_assumption: true`, **not user-confirmed**:

- **b1** (impact high, reversible): The terminal state is emitted as a single fixed-prefix line inside the final assistant message (fenced JSON, `--output-schema` and file output are not adopted). Rationale for the choice: it can be consumed by the same line-parsing approach as the existing integration branch line and PR URL line.
- **b2** (impact high, reversible): A terminal line of the same format is emitted on normal completion as well as on stop, so that the line's absence is itself detectable as abnormal. Rationale: "absent = normal" cannot distinguish a truncated turn from normal completion.
- **b3** (impact medium, reversible): The stop reason is expressed as a closed set of stable reason codes with a free-form human-facing `detail`. Rationale: it gives the contract test something fixed to pin.
- **b4** (impact high, reversible): The contract covers not only SKILL.md's stop conditions 2/3/4/6 but every terminating stop point, including fail-closed abort, `on_unavailable: abort`, a second `failed` in implement, the verify cap being reached, and Step C abort. Rationale: it avoids leaving the same class of omission on other paths.
- **b5** (impact medium, reversible): No terminal line is emitted on a stop-condition-5 wait turn, and a fixed sentinel step value is assigned to step-less stops. Rationale: it prevents an in-flight wait from being misread as a stop.

## Design Step

`skipped`. Reason: the change surface is limited to SSOT Markdown / YAML documents, Python contract tests and two JSON manifests, with no UI, screen or visual element involved; there were also zero design-system candidates. The batch policy `create-spec.design-step` (`decide_autonomously`) adopted the analyst's skip recommendation as-is.

## References

- Requirements document: `feature-docs/batch-stop-contract/REQUIREMENTS.md`
- Contract statement target: `em-workflow/references/batch-mode.md`
- Stop conditions and Step C completion report: `em-workflow/skills/develop/SKILL.md`
- Fail-closed classification: `em-workflow/references/question-resolution.md`
- `on_unavailable: abort`: `em-workflow/references/batch-policies.yaml`
- Existing contract-test convention: `tests/test_routeback_reset_scope_version_bump.py`
- Version bump targets: `em-workflow/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`
- Project license: none (no LICENSE file in the repository)
