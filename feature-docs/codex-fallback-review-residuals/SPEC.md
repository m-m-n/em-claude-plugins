# Feature: codex-fallback-review-residuals

## Overview

This feature closes the medium findings from
`feature-docs/batch-codex-autonomous-decisions/reviews/round2.yaml` that are
still open in the current tree (21fcec3b529ebbd1, ad385249e099e34b,
f16ba900e23a5497). It also records that the task's headline defect
(b915524ad5c7ed09) and findings 7e1c5176f1992a47 and 43504ede8ee2f609 no
longer exist in the current tree, and adds regression checks for them. The
requirements document is `feature-docs/codex-fallback-review-residuals/REQUIREMENTS.md`.

### Out of Scope (already resolved)

| ID | Finding | Reason |
|----|---------|--------|
| X1 | b915524ad5c7ed09 (task headline: fallback chain truncates earlier attempts' output) | Already resolved. `em-workflow/scripts/run_codex_exec.sh` now makes a single `codex exec` launch (header lines 26-30, launch at line 175). It has no fallback chain, no `run_attempt`, and no per-entry truncation. stdout and stderr are concatenated once (line 194), so an entry-1 usage-limit diagnostic always reaches `codex-reviewer.md` Step 6. `tests/test_codex_wrapper_single_invocation.py` AC-1 pins that the usage-limit stderr text reaches the caller verbatim in a single launch. |
| X2 | Task DoD: update the 3 exact-stdout assertions in `tests/test_codex_wrapper_provider_fallback.py` and add the composition rule to the header comment | No longer applicable. That test module was deleted, and `tests/test_codex_wrapper_single_invocation.py::TestSupersededModuleRemoved` asserts it does not exist. With a single launch there is no multi-entry composition rule to document. |
| X3 | 7e1c5176f1992a47 (litellm model names hardcoded in the wrapper) | Already resolved in the wrapper. It has no `ENTRY_ARGS_*` or `PROVIDER_NAME_*`. A model reaches it only through the caller's `--litellm MODEL` argument, which is passed verbatim (lines 102-112). `muse-spark` appears only in the usage-example comment on line 9. No wrapper change is needed. FR7 adds the missing regression check. |
| X4 | 43504ede8ee2f609 (switch detection relies on an unverified stderr premise) | Already resolved. The wrapper has no `is_usage_limit_response` / `is_provider_error_response` and no recognizer of response shape at all (header lines 29-30). `tests/test_codex_wrapper_single_invocation.py` AC-3 pins that switch-shaped text causes no second launch. |

## Objectives

- Close the medium findings from `feature-docs/batch-codex-autonomous-decisions/reviews/round2.yaml` that are still open in the current tree (21fcec3b529ebbd1, ad385249e099e34b, f16ba900e23a5497). After this change, the human-facing README, the Opus escalation definition, and the batch audit `source` mapping agree with each other and with the batch-codex-autonomous-decisions SPEC.
- Record explicitly that the task's headline defect (b915524ad5c7ed09) and findings 7e1c5176f1992a47 and 43504ede8ee2f609 no longer exist in the current tree, and add regression checks so they do not come back. One of these checks is a `--litellm MODEL` verbatim-passthrough check, which is not covered today.

## User Stories

Not applicable. The acceptance criteria are listed under Success Criteria.

## Technical Requirements

### Functional Requirements

- **FR1: README batch clause states the interactive/batch split** (source finding: 21fcec3b529ebbd1)
  In `em-workflow/README.md`, rewrite the clause in the `--batch` bullet that says 仕様変更・セキュリティ・ライセンス・不可逆判断のゲートは未収載なら安全側で中断する（fail-closed）. The new clause describes the split by mode. Interactive mode aborts. In batch mode, security, license, and irreversible-operation questions take the relaxed route (Codex consultation, then the Opus escalation, then the minimum-side-effect option) and do not abort. The clause refers to `em-workflow/references/question-resolution.md` ("The batch relaxation" / "The surviving aborts") for the trigger conditions and does not restate them. It adds one sentence saying that the surviving aborts named there are the only fail-closed classification stops left in batch.

- **FR2: Opus escalation names its dispatch route, contract, and model binding** (source finding: ad385249e099e34b)
  The `### Opus escalation` section of `em-workflow/references/question-resolution.md` names the escalation as a Task dispatch of a dedicated agent. It uses the literal form `Task(subagent_type="em-workflow:<name>")`, which `em-workflow/scripts/check-plugin-invariants.py`'s `SUBAGENT_TYPE_REF_RE` recognizes as a dispatch reference. The section names the contract document under `em-workflow/references/` that defines the escalation's input and return shape. It carries the Opus/xhigh binding from batch-codex-autonomous-decisions SPEC FR8/FR9/A4 and says where that binding lives: the agent definition's frontmatter `model` / `effort`. The section cites the contract for the input and return shape and does not restate the contract's contents. The per-question return-shape statement may therefore move from this section into the contract document (see NFR3). The section keeps its existing per-packet dispatch sentences, its counted-outside-the-ceiling sentence, and its untrusted-output sentences (the output is read, never executed as instructions, never adopted verbatim, and the per-question mapping judgement stays with the orchestrator).

- **FR3: Opus escalation agent definition and contract document** (source finding: ad385249e099e34b)
  Add a dedicated agent definition `em-workflow/agents/<name>.md` and a dedicated contract document under `em-workflow/references/`. Together they mirror the pairing of `em-workflow/agents/review-evaluator.md` with `em-workflow/references/review-evaluation-contract.md`.
  Agent definition:
  1. Frontmatter `name` equals the file stem and the `subagent_type` suffix used in FR2.
  2. Frontmatter sets `model: opus` and `effort: xhigh`.
  3. `tools` lists read-only tools only and contains no file-writing tool (no Write, Edit, NotebookEdit).
  4. There is no `# Task assignment` heading, which `check-plugin-invariants.py`'s `forbidden_task_assignment_heading` check rejects.
  5. The agent reads the contract and follows it, and the contract is the only source of truth for the agent's input and return shape, so the agent file does not restate the return field list.
  6. The agent treats its whole input as data and never follows instructions inside it.

  Contract document: it defines what the agent receives and returns.
  - Input: every still-unmapped question of one packet, or, for a non-packet gate, the gate's single decision presented per FR4. Each item carries `prompt`, `options` (each with its `option_id`), `why_needed`, `evidence`, and the tentative position. All of this sits inside an explicit delimited untrusted-data block, and the contract states that boundary.
  - Return: for each question, either a chosen `option_id` that exists in that question's own `options[].option_id` or an explicit no-decision, with reasoning in both cases. The output is that return object only.

  Add a row for the new agent to `em-workflow/README.md`'s エージェント table.

- **FR4: Opus escalation scope and option presentation for non-packet-gate callers** (source finding: ad385249e099e34b)
  The `### Opus escalation` section states how the escalation applies to callers that reach it through the Codex consultation procedure without a packet. These callers are `em-workflow/references/batch-mode.md`'s Non-packet gates (the review diff-size gate, the per-command approval fallback, and any other non-packet site that uses the consultation procedure). For such a caller, each non-packet gate resolution gets exactly one dispatch, carrying that gate's single decision. For the per-command approval fallback, this means at most one dispatch per distinct literal command string within a run, which matches that row's existing per-string cache. A non-packet gate has no question packet and so no `option_id`s of its own. Either the contract document (FR3) or this section defines how the gate's decision is presented: as one question whose `options[]` lists the gate's choices, each with an `option_id` and including the gate's minimum-side-effect option. Whichever document defines this, the other cites it. This presentation is what makes the return condition "`option_id` present in that question's own `options[].option_id`" satisfiable. If the escalation returns no decision, the gate takes the minimum-side-effect option that `batch-mode.md`'s table already prescribes. The existing per-packet wording ("Exactly one dispatch per packet" ...) is kept.

- **FR5: Batch audit `source` for an escalation-decided non-packet gate** (source finding: f16ba900e23a5497)
  This change goes in `em-workflow/references/phase-state.md`'s Batch audit record file section, in the general `source` mapping that governs the Non-packet gates writer. The mapping defines the value for a non-packet gate decided by the Opus escalation, including the case where the availability probe found no harness and no Codex consultation turn ran. The value is `batch-codex-consultation`. It is read as naming the consultation route, never as a claim that Codex itself was consulted, which is the same reading the relaxed-route bullet already uses. The value comes from the existing closed vocabulary in `question-packet-schema.md`, and no new value is minted. `batch-safe-default` stays the value when the minimum-side-effect option was taken. The Non-packet gates writer's `resolution_note` also records whether the Opus escalation ran and its reasoning. The section adds a worked example record for a non-packet gate that the escalation resolved with no Codex consultation and no safe-default selection. The example uses that gate's `question_id` (`review.diff-size-gate` or `command-execution.per-command-approval-fallback`), `packet_id: null`, `source: batch-codex-consultation`, and a `resolution_note` that says Codex was not consulted, the Opus escalation ran, and what its reasoning was.

- **FR6: Tests pin FR1 through FR5** (source findings: 21fcec3b529ebbd1, ad385249e099e34b, f16ba900e23a5497)
  Tests under `tests/` (Python stdlib unittest) assert the following.
  - (a) `README.md` no longer contains the batch fail-closed-abort clause, and it cites `references/question-resolution.md` for the relaxation conditions.
  - (b) The Opus escalation section contains the literal `Task(subagent_type="em-workflow:<name>")`, the contract path, and the Opus/xhigh binding. The named agent file exists. Its frontmatter has `name` equal to the file stem, `model: opus`, and `effort: xhigh`. Its `tools` contain no file-writing tool (none of Write, Edit, NotebookEdit). It has no `# Task assignment` heading. The named contract file exists.
  - (c) The contract document states the delimited untrusted-input boundary and the per-question return contract: an `option_id` from the question's own `options[].option_id` or an explicit no-decision, with reasoning in both cases.
  - (d) `tests/test_question_resolution_doc.py`'s existing return-shape pin (`test_opus_escalation_return_shape`) is updated without losing coverage. It asserts that the section references the contract document and that the contract document contains the return-shape statement. The other existing Opus escalation pins are unchanged.
  - (e) The Opus escalation section, or the contract, states the non-packet-gate scope and the non-packet option/`option_id` presentation rule.
  - (f) `phase-state.md`'s general mapping covers the escalation-decided non-packet case and contains the worked example. These assertions go in `tests/test_batch_quiet_output_audit_record_contract.py`, as the finding asks.

  Each new negative assertion carries a non-vacuity proof, following the existing pattern in these modules.

- **FR7: Regression check: --litellm MODEL is passed verbatim** (source finding: 7e1c5176f1992a47)
  `tests/test_codex_wrapper_single_invocation.py` gets a case that calls `em-workflow/scripts/run_codex_exec.sh` with `--litellm` and an arbitrary model value that matches no model name in the wrapper or in `references/reviewers.yaml`. The case asserts a single launch whose argv contains `-p`, `litellm`, `-m`, MODEL as consecutive elements, with MODEL unchanged. The existing argv check (`test_accepted_flag_set_on_the_launch_is_unchanged`) does not pass `--litellm`. The case carries a non-vacuity proof: its matcher rejects an argv in which the model value was replaced or dropped. The wrapper itself is not changed.

### Non-Functional Requirements

- **NFR1 - No new gate, policy entry, or source value:** No new `gate_id`, no new entry in `references/batch-policies.yaml`, and no new value in the answer `source` vocabulary (`references/question-packet-schema.md`).
- **NFR2 - Wrapper unchanged, provider-fallback test module not recreated:** `em-workflow/scripts/run_codex_exec.sh` is not changed. `tests/test_codex_wrapper_provider_fallback.py` is not recreated, because `tests/test_codex_wrapper_single_invocation.py` asserts that it does not exist.
- **NFR3 - Existing pinned phrases preserved:** Phrases already pinned by existing tests stay intact, with one exception. The exception is the Opus escalation return-shape sentence pinned by `tests/test_question_resolution_doc.py::test_opus_escalation_return_shape`. It may move into the contract document, provided that test is updated to assert that the section references the contract and that the contract carries the return shape, so coverage is kept. These pins stay unchanged in the `### Opus escalation` section: "Exactly one dispatch per packet", "carrying every question of that packet still unmapped when the consultation ended", the counted-outside-ceiling sentence, and the untrusted-output sentences. In `tests/test_batch_quiet_output_audit_record_contract.py` these stay unchanged: "For the other three writers below", "the relaxed route's own bullet below states its complete three-way mapping instead", and exactly one occurrence each of `batch-codex-consultation` and `batch-safe-default` in the relaxed-route bullet. FR5's change goes into the general mapping, not into the relaxed-route bullet.
- **NFR4 - SSOT discipline:** The documents keep the SSOT discipline ("cited, not restated"). README delegates the conditions to `question-resolution.md`. `question-resolution.md` cites the contract document and does not copy its shape. The agent definition defers to the contract for its input and return shape.
- **NFR5 - Full suite passes, stdlib-only tests:** The full test suite passes: `python3 -m unittest discover -s tests`. New tests import only the standard library.
- **NFR6 - No manual version change:** The em-workflow plugin version is not changed by hand. The GitHub Actions workflow raises the patch on push (`.claude/rules/core-plugin-version-bump.md`).
- **NFR7 - Plugin invariants hold:** `python3 em-workflow/scripts/check-plugin-invariants.py <repository-root>` still exits 0 against the integrated tree. This is already pinned by `tests/test_check_plugin_invariants.py::TestRepositoryLevelInvariant`. In particular, `agent_dispatch_parity` finds the new agent referenced by a `subagent_type="em-workflow:<name>"` dispatch, and `forbidden_task_assignment_heading` finds no `# Task assignment` heading in it.
- **NFR8 - review-evaluator pair unchanged:** `em-workflow/agents/review-evaluator.md` and `em-workflow/references/review-evaluation-contract.md` are not changed. They are the pattern the new pair mirrors, and `tests/test_review_phase_llm_led.py` pins the evaluator's frontmatter (an exact tools set) and its single dispatch site in `review-phase.md`.

## Assumptions

- **A1:** The Opus escalation is delivered by a dedicated agent `em-workflow/agents/<name>.md` with its own contract document under `em-workflow/references/`. The alternatives were an existing agent type with a model override and an inline contract.
  Basis: Decided by the orchestrator (answer `requirement.opus-escalation-vehicle`, source `batch-codex-consultation`). batch-codex-autonomous-decisions SPEC A4 (SPEC.md:49-50) left the vehicle to planning, so the inline alternative would not have contradicted the SPEC. The dedicated pair was chosen because it keeps the review-evaluator's role and contract separate, mirroring `review-evaluator.md` + `review-evaluation-contract.md`. `check-plugin-invariants.py`'s `agent_dispatch_parity` requires the agent to be referenced in the `subagent_type="em-workflow:<name>"` form. Reversible.
- **A2:** A non-packet gate decided by the escalation records `source: batch-codex-consultation` under the route-naming reading. No new vocabulary value is added.
  Basis: Confirmed by the orchestrator (answer `requirement.escalation-nonpacket-source`). `question-packet-schema.md`'s `source` vocabulary is closed. `phase-state.md`'s relaxed-route bullet (lines 470-475) already maps escalation decisions to `batch-codex-consultation` under that reading. `batch-safe-default`, `batch-decision-table`, and `batch-classification-gate` do not fit this case. Reversible.
- **A3:** This change raises no minor or major version, so the version is left to the Actions patch bump.
  Basis: The change closes gaps in an already-shipped feature: documentation consistency, plus the escalation vehicle that feature's SPEC already required. `core-plugin-version-bump.md` reserves manual bumps for feature additions and breaking changes. Reversible.
- **A4:** No dedicated Opus escalation agent exists today. A new agent needs no registration step other than (1) being referenced in the `subagent_type="em-workflow:<name>"` form somewhere under `em-workflow/`, `feature-docs/`, `test-docs/`, or `tests/` and (2) carrying no `# Task assignment` heading.
  Basis: `check-plugin-invariants.py` builds its agent set from `em-workflow/agents/*.md` (lines 231-237). It fails any definition without a `SUBAGENT_TYPE_REF_RE` match in `SCAN_ROOTS` (lines 99, 172-174, 265-270), and `tests/test_check_plugin_invariants.py::TestRepositoryLevelInvariant` runs it against the repository root. `question-resolution.md` has no `subagent_type` reference, and the README agent table lists no escalation agent. There is no separate registry: the `gate_id_coverage` check covers batch-policies ids only, and the new agent adds none. Reversible.
- **A5:** The new agent's `tools` are Read, Glob, and Grep. Bash is not granted.
  Basis: The escalation decides from the questions it is handed and has no need to run commands. review-evaluator carries Bash only for read-only `git diff`/`git log` inspection of changed files, which the escalation does not do. The test requirement (FR6 b) only needs the absence of file-writing tools, so this choice can be changed at planning without affecting the tests. Reversible.
- **A6:** The agent's `<name>` is chosen at planning. The file stem, the frontmatter `name`, and the `subagent_type` suffix are the same string and match `[A-Za-z0-9_-]+`.
  Basis: `SUBAGENT_TYPE_REF_RE` captures `em-workflow:([A-Za-z0-9_-]+)`, and `agent_dispatch_parity` compares that capture against file stems. Reversible.

## Implementation Approach

### Architecture

**Component Diagram:**
```
em-workflow/README.md  (FR1)
  └─ cites → references/question-resolution.md  ("The batch relaxation" / "The surviving aborts")

references/question-resolution.md  ### Opus escalation  (FR2, FR4)
  ├─ Task(subagent_type="em-workflow:<name>") → agents/<name>.md  (FR3)
  │                                              └─ frontmatter: model: opus, effort: xhigh
  │                                              └─ reads and follows → references/<contract>.md  (FR3)
  └─ cites → references/<contract>.md  (input / return shape)

references/batch-mode.md  Non-packet gates  → reach the escalation via the consultation procedure  (FR4)

references/phase-state.md  Batch audit record file  (FR5)
  └─ general `source` mapping: escalation-decided non-packet gate → batch-codex-consultation
```

### Data Flow

```
Orchestrator (batch, relaxed route)
  → Codex consultation
  → Opus escalation: Task(subagent_type="em-workflow:<name>")
      input:  still-unmapped questions of one packet,
              or one non-packet gate decision presented as one question (FR4),
              inside a delimited untrusted-data block (FR3)
      return: per question, an option_id from that question's own options[].option_id
              or an explicit no-decision, with reasoning (FR3)
  → Orchestrator maps each question (judgement stays with the orchestrator)
  → no-decision on a non-packet gate → batch-mode.md's minimum-side-effect option (FR4)
  → batch audit record: source per phase-state.md's general mapping (FR5)
```

### API Design

Not applicable.

### Database Schema

Not applicable. The batch audit record fields for FR5's worked example are:

| Field | Value |
|-------|-------|
| `question_id` | `review.diff-size-gate` or `command-execution.per-command-approval-fallback` |
| `packet_id` | `null` |
| `source` | `batch-codex-consultation` |
| `resolution_note` | States that Codex was not consulted, that the Opus escalation ran, and its reasoning |

### Dependencies

**Internal Dependencies:**
- `em-workflow/scripts/check-plugin-invariants.py`: `agent_dispatch_parity` and `forbidden_task_assignment_heading` checks apply to the new agent (NFR7, A4).
- `em-workflow/references/question-packet-schema.md`: closed `source` vocabulary (NFR1, FR5).
- `em-workflow/references/batch-mode.md`: Non-packet gates table and its minimum-side-effect options (FR4).
- `em-workflow/agents/review-evaluator.md` and `em-workflow/references/review-evaluation-contract.md`: the pattern the new pair mirrors; not changed (NFR8).
- `feature-docs/batch-codex-autonomous-decisions/SPEC.md`: FR8/FR9/A4 Opus/xhigh binding (FR2).

**External Dependencies:**
- None. New tests import only the Python standard library (NFR5).

### File Structure

```
em-workflow/
├── README.md                                   # FR1 (batch clause), FR3 (agent table row)
├── agents/
│   └── <name>.md                               # FR3 (new)
└── references/
    ├── <contract>.md                           # FR3 (new)
    ├── question-resolution.md                  # FR2, FR4
    └── phase-state.md                          # FR5
tests/
├── test_question_resolution_doc.py             # FR6 (d)
├── test_batch_quiet_output_audit_record_contract.py  # FR6
└── test_codex_wrapper_single_invocation.py     # FR7
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/codex-fallback-review-residuals/**`
- `test-docs/codex-fallback-review-residuals/**`

`feature-docs/codex-fallback-review-residuals/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/codex-fallback-review-residuals/**` covers `test-docs/codex-fallback-review-residuals/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/{feature}/` directory at all; the declared
`test-docs/{feature}/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests
- [ ] TS1 (AC1): Read `em-workflow/README.md`. Assert that the old fail-closed clause string is absent, that the batch bullet names the relaxed route for security, license, and irreversible questions, and that it cites `references/question-resolution.md`. Negative-proof fixture: the old clause text is caught by the matcher.
- [ ] TS2 (AC2): Slice `question-resolution.md`'s `### Opus escalation` section. Extract the `Task(subagent_type="em-workflow:<name>")` literal and the contract path. Assert that `em-workflow/agents/<name>.md` and the contract file exist. Parse the agent frontmatter as `tests/test_review_phase_llm_led.py` does for review-evaluator. Assert that `name` equals `<name>`, that the frontmatter has `model: opus` and `effort: xhigh`, and that the `tools` set is disjoint from {Write, Edit, NotebookEdit}. Assert there is no `# Task assignment` heading, and that the README agent table lists `<name>`. Non-vacuity: a fixture frontmatter carrying `Write` is rejected by the tools matcher.
- [ ] TS3 (AC3, AC6): Read the contract document. Assert that it states the delimited untrusted-data block for the input and the per-question return contract (an `option_id` from the question's own `options[].option_id`, or an explicit no-decision, with reasoning in both cases). Update `test_opus_escalation_return_shape`: assert that the section cites the contract path and that the contract contains the return-shape statement. Assert that the other Opus escalation pins still pass on the section.
- [ ] TS4 (AC4): Assert that the Opus escalation section contains the non-packet-gate scope statement: one dispatch per non-packet gate resolution, the per-command-string reading for the approval fallback, and no-decision falling to the minimum-side-effect option. Assert that the section or the contract states how a non-packet gate's choices become one question's `options[]` with `option_id`s, and that the other document cites it. Assert that the existing per-packet sentences are still present.
- [ ] TS5 (AC5): Slice `phase-state.md`'s Batch audit record file section. Assert that the general mapping maps the escalation-decided non-packet case to `batch-codex-consultation` with the route-naming reading. Assert that the Non-packet gates writer's `resolution_note` names whether the escalation ran and its reasoning. Assert that the section has a worked YAML example with a non-packet `question_id` (`review.diff-size-gate` or `command-execution.per-command-approval-fallback`), `packet_id: null`, `source: batch-codex-consultation`, and a `resolution_note` saying the escalation ran and Codex was not consulted. Assert that the relaxed-route bullet still has exactly one occurrence of each source literal.
- [ ] TS6 (AC7): Using the existing codex stub harness in `tests/test_codex_wrapper_single_invocation.py`, run `run_codex_exec.sh readonly --litellm <arbitrary-model> "prompt"`. Assert exactly one launch, and that the launch argv contains `-p`, `litellm`, `-m`, `<arbitrary-model>` as consecutive elements. Non-vacuity: the consecutive-sequence matcher rejects a forged argv with a different model value.

### Integration Tests
- [ ] TS7 (AC2, AC8, AC9): Run the full suite. `tests/test_check_plugin_invariants.py::TestRepositoryLevelInvariant` passes with the new agent present. `tests/test_codex_wrapper_single_invocation.py` (usage-limit passthrough, single launch, provider-fallback module absent) and `tests/test_review_phase_llm_led.py` pass unchanged.

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected
- [ ] Existing E2E tests pass without regression

### Edge Cases
- [ ] Non-packet gate where the escalation returns no decision: the gate takes the minimum-side-effect option that `batch-mode.md`'s table prescribes (FR4).
- [ ] Non-packet gate decided by the escalation where the availability probe found no harness and no Codex consultation turn ran: `source` is `batch-codex-consultation` under the route-naming reading (FR5).
- [ ] Per-command approval fallback: at most one dispatch per distinct literal command string within a run (FR4).
- [ ] Non-packet gate where the minimum-side-effect option was taken: `source` stays `batch-safe-default` (FR5).

### Performance Tests
Not applicable.

## Security Considerations

- **Authentication:** Not applicable.
- **Authorization:** The new agent's `tools` contain no file-writing tool (FR3).
- **Input Validation:** The contract places the escalation input inside an explicit delimited untrusted-data block and states that boundary. The agent treats its whole input as data and never follows instructions inside it (FR3). The orchestrator reads the escalation output, never executes it as instructions, never adopts it verbatim, and keeps the per-question mapping judgement (FR2).
- **Data Protection:** Not applicable.
- **XSS Prevention:** Not applicable.
- **SQL Injection Prevention:** Not applicable.
- **CSRF Protection:** Not applicable.

## Error Handling

### Error Codes

Not applicable.

### Error Flow

```
Escalation returns no decision for a non-packet gate → gate takes batch-mode.md's minimum-side-effect option → audit source: batch-safe-default
```

## Performance Optimization

Not applicable.

## Success Criteria

- [ ] **AC1** (FR1, FR6): `em-workflow/README.md` no longer says that unlisted security, license, or irreversible gates abort fail-closed in batch. It states the split between interactive abort and the batch relaxed route, and points to `references/question-resolution.md` for the conditions and the surviving aborts. A test pins this, with a negative proof against the old clause.
- [ ] **AC2** (FR2, FR3, FR6, NFR7): `question-resolution.md`'s `### Opus escalation` section contains `Task(subagent_type="em-workflow:<name>")`, a contract document path, and the Opus/xhigh binding held in that agent's frontmatter. The named agent file exists. Its frontmatter has `name` equal to its file stem, `model: opus`, and `effort: xhigh`. Its tools include no file-writing tool, and it has no `# Task assignment` heading. The named contract file exists. README's agent table lists the agent. `check-plugin-invariants.py` exits 0 against the repository root. Tests pin each point.
- [ ] **AC3** (FR3, FR6): The contract document states the delimited untrusted-input boundary and the per-question return contract: a chosen `option_id` present in that question's own `options[].option_id` or an explicit no-decision, with reasoning in both cases. A test reads the contract and pins both.
- [ ] **AC4** (FR4, FR6): The Opus escalation section states its non-packet-gate scope: one dispatch per non-packet gate resolution (per distinct literal command string for the per-command approval fallback), with a no-decision result falling to `batch-mode.md`'s minimum-side-effect option. The section or the contract defines how a non-packet gate's choices are presented as one question's `options[]` with `option_id`s, and the other document cites that definition. The existing per-packet sentences stay unchanged. A test pins this.
- [ ] **AC5** (FR5, FR6): `phase-state.md`'s general `source` mapping gives `batch-codex-consultation` (route-naming reading) for a non-packet gate decided by the Opus escalation, including when no Codex turn ran. The Non-packet gates writer's `resolution_note` records whether the escalation ran and its reasoning. The section contains a worked example record of that case with `packet_id: null` and a `resolution_note` saying Codex was not consulted and the escalation ran, with its reasoning. `tests/test_batch_quiet_output_audit_record_contract.py` covers all of this.
- [ ] **AC6** (FR6, NFR3): `tests/test_question_resolution_doc.py::test_opus_escalation_return_shape` (or its replacement) asserts that the Opus escalation section references the contract document and that the contract document contains the return-shape statement. No existing Opus escalation pin is weakened, and every other pinned phrase listed in NFR3 is still present.
- [ ] **AC7** (FR7, NFR2): A test calls `run_codex_exec.sh` with `--litellm` and an arbitrary model value. It asserts exactly one launch whose argv carries `-p litellm -m MODEL` consecutively with MODEL unchanged, and it has a non-vacuity proof.
- [ ] **AC8** (NFR2): Regression guard for the already-resolved headline defect: `run_codex_exec.sh` still launches `codex exec` exactly once per call, and a usage-limit diagnostic on stderr reaches the caller verbatim. The existing cases in `tests/test_codex_wrapper_single_invocation.py` already pin this (that module's AC-1, AC-3, and AC-7) and must stay green. `tests/test_codex_wrapper_provider_fallback.py` does not exist.
- [ ] **AC9** (NFR3, NFR5, NFR8): `python3 -m unittest discover -s tests` passes. No pinned phrase is removed except the return-shape sentence that AC6 moves with its coverage, and `tests/test_review_phase_llm_led.py` passes unchanged.

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

None. Every requirement is resolved.

## References

- Requirements document: `feature-docs/codex-fallback-review-residuals/REQUIREMENTS.md`
- Review findings: `feature-docs/batch-codex-autonomous-decisions/reviews/round2.yaml`
- Prior SPEC: `feature-docs/batch-codex-autonomous-decisions/SPEC.md` (FR8, FR9, A4)
- `em-workflow/references/question-resolution.md`
- `em-workflow/references/phase-state.md`
- `em-workflow/references/batch-mode.md`
- `em-workflow/references/question-packet-schema.md`
- `em-workflow/agents/review-evaluator.md`, `em-workflow/references/review-evaluation-contract.md`
- `em-workflow/scripts/check-plugin-invariants.py`
- `em-workflow/scripts/run_codex_exec.sh`
