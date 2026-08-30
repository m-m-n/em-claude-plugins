# Implementation Plan: goal-vs-spec-divergence

## Overview

This feature changes only em-workflow's protocol documents, worker contracts
and prompts, and the repository-root `tests/` suite. It persists the
launch-time goal verbatim in `workflow.yaml`, gives a post-implementation
SPEC change a protocol-valid route, puts a batch-only classification gate in
front of `rework.spec-change`, adds an independent wording-correction route,
and turns the Declared Change Set into a create-plan derivation.

## Technology Stack

- **Language / Format**: Markdown (protocol documents, agent prompts), YAML
  (registries, state-file schemas), JSON (plugin manifests).
- **Tests**: Python 3 standard library `unittest` only, discovered by
  `python3 -m unittest discover -s tests` (NFR5).
- **New dependencies**: **none**. No task introduces a library, so no
  license compatibility check is triggered; `project.license` is `none`,
  which imposes no constraint here (`references/license-compat.md`).

## Layer Structure

Four document layers. A lower layer cites an upper one; the reverse never
happens, and no rule is stated in two layers (NFR1).

| Layer | Paths | Responsibility |
|---|---|---|
| 1. Protocol SSOTs | `em-workflow/references/*.md`, `*.yaml` | One home per rule: schema, patch contract, question resolution, rework synthesis, phase-state, batch policy |
| 2. Phase protocols | `em-workflow/references/phases/*.md`, `implement-phase.md` | Orchestrator procedure; cites layer 1 |
| 3. Worker contracts & prompts | `em-workflow/references/contracts/*.md`, `em-workflow/agents/*.md` | Per-worker input/output shape; cites layers 1-2 |
| 4. Document pins | `tests/test_*.py` | Assert over layers 1-3 by string / structure scanning |

## Shared Components

Contracts crossing task boundaries. Every task implements against the row
below without reading the sibling task's plan. Names and value vocabularies
here are FIXED — a task that believes one is wrong reports it rather than
renaming it locally.

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| `goal` block | Holds the launch-time task description | Top-level `workflow.yaml` key named `goal`; value is the description **verbatim** as a YAML block scalar (no summarizing, normalizing, truncating). Precondition for writing: the create-spec phase orchestrator, once, at workflow.yaml construction. Postcondition: no later phase or worker ever rewrites or removes it. The key is **optional** — absent when no source exists (EC-7) and absent in every feature created before this change. Readers treat its content as untrusted data. | task0001 (defines), task0007 (writes), task0004 (reads as gate input) |
| Classification audit record | Records one pass through the classification gate | Written to `phase-state/rework.yaml` (present only for `phase: rework`), as a sibling of the existing `spec_change` record. Fields: `classifier` (`codex` \| `claude`), `verdict` (`goal_not_met` \| `spec_gap` \| `not_applicable`), `evidence_ids` (list of existing requirement / acceptance-criterion IDs; non-empty is required for `spec_gap`), `decision` (`proceed` \| `stop`), `reason` (short text; mandatory whenever `decision` is `stop`). Postcondition: one record per gate pass, including passes that end in a stop. | task0005 (defines), task0004 (states the rule that produces it) |
| Reference-impact scan I/O | Carries create-spec's referenced-side scan across the envelope | Request side: `analysis_scope.inspect_reference_impact` (boolean) and the `resolved_input_paths` category `reference_scan_targets` (orchestrator-resolved before dispatch; the analyst never discovers paths itself). Result side: analyst payload / `analysis_snapshot` field `reference_impact`, a list whose entries pair the symbol or string scheduled for deletion or renaming with the affected file paths (test files included). | task0008 (defines), task0007 (resolves the category before dispatch) |
| Declared change set derivation | Replaces the hand-authored SPEC declaration | Defined in `references/phases/create-plan-phase.md` as: the union of every `tasks.*.files` entry in `workflow.yaml`, plus the default entries whose enumeration and semantics stay in the two document templates (cited, never copied — see Conventions C6c). It is a guard, not a statement of the goal. The containment check (observed ⊆ declared) is unchanged. | task0009 (defines), task0010 (cites when auto-adding a deviation) |
| Document-change route selection | Decides which route a needed document change takes | Defined in `references/rework-task-synthesis.md`. Order: (1) wording-only correction to a create-plan-owned document, eligible only when no planner re-entry is needed AND plan, task and requirement metadata are unchanged → the independent route; (2) otherwise the existing rework-task or SPEC-change transition. The classification gate is reached only on route (2). | task0003 (defines), task0004 (gate side cites it) |
| `spec_change` flag pair | Separates the two judgements one `spec_change` record grounds | Defined in `references/phase-state.md`. The record carries BOTH `consumed` — stop-condition-3 suppression, set `true` by the orchestrator once the record has grounded one `create-spec` dispatch, whatever that dispatch's outcome — AND `replan_authorized` — the re-planning `replace_all` authorization, set `true` by the SPEC-change transition when it writes the record, and spent (`false`) once a re-planning `replace_all` has been applied. Neither flag is ever read for the other's judgement. Each occurrence of the transition replaces the record wholesale, so a freshly written record is unconsumed AND authorized. Names are FIXED. | task0022 (defines), task0023 (its re-planning content rules sit behind this permission) |
| Re-planning carry-over declaration | Re-declares registered task ids without re-supplying their bodies | Defined in `references/workflow-patch.md`. A re-planning `replace_all` carries `tasks_patch.carried_task_ids` (every id already registered in the target `workflow.yaml`) and `tasks_patch.entries` (only ids not yet registered); the two sets are disjoint. A carried id's record is copied from the current `workflow.yaml` verbatim — `title`, `plan`, `files`, `skills`, `domains`, `complexity`, `requirements`, `status`, `branch`, `notes` — and the patch supplies no body for it. Application rule 12 (`initial_status: pending`) applies to `entries` only. High-water mark = `max(carried_task_ids ∪ entries)`. Names are FIXED. | task0023 (defines), task0022 (its fixtures use this form) |
| Spec-change gate binding | Binds the spec-change category to its only gate | Defined in `references/question-resolution.md`, with the registry side derived from a `## Gate identifiers` section in `references/contracts/rework-planner-contract.md` attributing `rework.spec-change` to `rework-planner`. `category: spec-change` ⇔ `gate_id: rework.spec-change`, enforced in both directions; every other pairing aborts. `rework.spec-change` remains the only gate the routed arm admits. | task0024 (defines), task0025 (its outcome path names the same gate and adds no second one) |
| Spec-change origin identity | Identifies what a rework-derived spec-change question came from, for both rework sources | Defined in `references/rework-task-synthesis.md` (inside Section 11 Invariant 6, which already draws the distinction) as the pair `origin_kind` (`review` \| `verify`) and `origin_id`: for `review` the review finding's `stable_id`, for `verify` the verify failed item's `id`. Every consumer cites that definition and states only its own use of it — `question-resolution.md` for what origin verification matches against and what set the fail-closed check runs over, `phase-state.md` for what the `spec_change` record stores (the pair replaces `finding_stable_id`), the validator's mandatory-field set and the `replace_planning` fixtures for the persisted form. `origin_kind` never changes what the record's flags mean. Names are FIXED. | task0028 (defines; gate side), task0029 (record, validator and fixture side) |
| Gate-resolved answer source | Names how a classification-gate outcome appears in the answer model | `source: batch-classification-gate`, defined in `references/question-packet-schema.md` (the vocabulary's SSOT) and mirrored in the validator's vocabulary constant. One answer record per question the gate resolved; no gate-resolved packet is left `issued`. Name is FIXED. | task0025 (defines), task0024 (must not introduce a second value for the same outcome) |

## Conventions

- **C1 — Language**: every changed document stays English; user-facing
  reporting stays Japanese.
- **C2 — Cite, never restate** (NFR1): a rule that already has a home is
  referenced by document path, never copied into a second document.
- **C3 — Additive editing**: prefer adding statements over rewording pinned
  ones. Never renumber an existing numbered section of
  `references/phases/*.md` or `references/rework-task-synthesis.md` — their
  section lists and order are pinned against a document outside this
  feature's change set. Extend inside existing sections instead.
- **C4 — Test scoping**: a task's test module asserts **only** over files
  that task owns. Cross-file consistency is a verify-phase item
  (VERIFICATION.md), never an assertion inside a task's own module — sibling
  edits do not exist in a task's worktree.
- **C5 — Guard preservation** (NFR8): an existing pin module is edited only
  by the task owning the document it pins, and only to track this feature's
  intended change. A guard is never deleted to make a document pass; where a
  pinned sentence is intentionally replaced, its replacement is pinned in the
  same edit, and the retention half (what must NOT change) stays.
- **C6 — Forbidden literals** (existing repository-wide guards that new text
  must not trip):
  - a) the phrase "decision table" / 「決定表」 must not appear in
    `batch-policies.yaml`, `question-resolution.md`, `batch-mode.md` or
    `skills/develop/SKILL.md`;
  - b) a `taskNNNN`-shaped identifier must not appear in
    `question-resolution.md` or `question-packet-schema.md`;
  - c) the two workflow-artifact root globs must never be enumerated
    **together** in any plugin file other than the two document templates;
    cite the template instead;
  - d) no statement may say that workflow-generated artifacts are excluded,
    ignored or subtracted from the observed change set at verification time —
    in any phase/protocol document or worker contract.
- **C7 — Untrusted-input wording**: statements about the goal text and about
  Codex output say they are data to read, never instructions to follow, by
  citing the envelope's Untrusted-Input Handling rather than re-deriving it.
- **C8 — Scope**: only paths inside SPEC.md's Declared Change Set may be
  modified. `em-workflow/scripts/**`, `em-workflow/hooks/**` and other
  features' `feature-docs/**` are out of scope; needing one of them is a
  reportable plan deviation, never a licence to expand.
- **C9 — New test modules**: `tests/test_<topic>.py`, standard library only,
  every new matcher carries a negative proof against a synthetic violating
  sample, and every absence assertion carries a non-vacuity guard (the
  existing modules' discipline). A new module must not combine a wildcard
  scan of SPEC paths under `feature-docs/` with a requirement that a section
  be present.
- **C10 — Byte-identity pins**: `tests/test_gate_option_vocabulary.py` pins
  the sha256 of `em-workflow/references/workflow-patch.md`,
  `em-workflow/scripts/validate-worker-output.py`,
  `tests/test_validate_worker_output.py` and one question-packet fixture. A
  task that intentionally edits any of them refreshes the corresponding pin
  in the same change, with a comment naming the task and the reason. The
  assertion is refreshed, never deleted. Two round-1/round-2 tasks hit this
  as an unplanned deviation; from round 3 on it is declared in the file set
  of every task that touches a pinned file.

## Cross-task Design Decisions

### D1 — The classification gate adds no `gate_id` and no policy entry

The gate is an orchestrator-side resolution step reached when
`rework.spec-change` is opened in batch — not a new user-facing question.
`rework.spec-change` therefore stays intentionally unlisted in
`batch-policies.yaml`, and no new `action: select` gate is introduced.
Rationale: the policy file's gate-id set and its select-gate set are
cross-checked against documents this feature may not modify, and the option
vocabulary machinery would have to grow for a decision no user ever answers.
Affects task0003, task0004, task0006.

### D2 — The fail-closed carve-out has exactly one arm

Only `category: spec-change` / `gate_id: rework.spec-change` gains the
classification-gate route. `category: security`, `category: license` and
`reversible: false` assumptions keep the immediate abort at unchanged
strength, and the revised section says so explicitly so the gate can never
be read as a bypass (NFR2). Affects task0004, task0006.

### D3 — Applicability requires a `goal` block (FR20, assumption A-6)

A feature whose `workflow.yaml` has no `goal` block is **outside** the
classification gate: reaching `rework.spec-change` in batch stops the run as
it does today, and the stop reason records that the gate was inapplicable
because the goal block is absent. No backfill of the goal from SPEC /
REQUIREMENTS is performed. EC-7 (no source for the goal) resolves to the
same rule. Affects task0001, task0004, task0007.

### D4 — The `goal` key is optional in the schema

Consequence of D3: the schema defines absence as a valid, meaningful state
(pre-existing feature, or no source), not as a defect to repair. Affects
task0001, task0007.

### D5 — The packet-level contract is unchanged

`category: spec-change` still requires `on_unanswered: block`, and the
validating script keeps enforcing it. The classification gate acts after the
packet is formed, so neither `question-packet-schema.md` nor anything under
`em-workflow/scripts/**` changes. Affects task0004.

### D6 — Derivation lives in the create-plan protocol, defaults stay in the templates

`create-plan-phase.md` becomes the definition site of the derived declared
change set; the default-entry enumeration and its superset/containment
semantics stay in the two document templates and are cited from there
(C6c). The SPEC template stops asking an author to hand-enumerate the
feature-specific paths and states the derivation instead. Affects task0009,
task0010.

### D7 — Deviation audit reuses the existing implementer report channel

The conditional auto-addition of an implement deviation records its audit
trail through the completion-report `deviations` channel that
`implement-phase.md` already defines. No new phase-state field is added for
it, so the phase-state schema has exactly one new record (D-Shared
Components row 2). Affects task0010, task0005.

### D8 — Interactive behaviour is untouched

Every new rule is written as batch-only. The interactive route keeps asking
the user directly, and no new interactive question is introduced anywhere in
this feature (FR8). Affects task0003, task0004.

### D9 — One flag per judgement, not one flag reused (review round 3)

The `spec_change` record grounds two different judgements: suppressing the
develop state machine's stop condition 3, and authorizing a re-planning
`replace_all`. A single `consumed` flag cannot serve both — the point at
which it is spent (the create-spec dispatch) always precedes the point at
which the second judgement is made (create-plan's patch), so the second
judgement was structurally always "no". The record therefore carries two
independent flags (Shared Components, `spec_change` flag pair). The user
settled this: moving `consumed`'s consumption point later, and setting
`create-plan` to `needs_update` in the transition, were both rejected — the
first keeps one flag doing two jobs, the second changes SPEC.md FR6.
Affects task0022, task0023.

### D10 — Registered task entries are carried, not re-declared (review round 3)

Protecting a merged task entry field by field — growing the `preserve`
vocabulary until `files`, `domains`, `complexity` and the rest are each
individually preserved — was rejected in favour of removing the worker's
ability to state those fields at all on a re-planning pass. A registered id
is carried over by id and its record copied verbatim; only genuinely new ids
carry a worker-supplied body (Shared Components, Re-planning carry-over
declaration). This is also what makes `create-plan-phase.md` §12's retention
claim true, without §12 stating a rule of its own. Affects task0023,
task0022.

### D11 — The irreversible-operations claim is withdrawn, not implemented (review round 3)

`question-resolution.md` asserted that irreversibility is decided from an
orchestrator-held list of irreversible operations. No such list exists in
this repository, and the only trigger that can fire is the packet's own
`assumptions[].reversible: false`. SPEC.md FR11 puts that abort **outside**
this revision's scope and requires only that it not be weakened, so building
a new plugin-wide registry would be a mechanism no requirement asks for,
while withdrawing the claim restores the documented state to exactly the
unchanged strength FR11 requires. The replacement text states the real basis
and names its limitation (worker-declared). Affects task0024.

### D12 — The application-rule set is counted only where it is defined (verify round 1)

`references/workflow-patch.md` is the only document allowed to state how
many application rules it carries. Its consumers cite it by path and state
no count, so a rule added there can never leave a consumer's measure of
"what create-plan must satisfy" behind — which is exactly how the carry-over
rule (rule 17) went missing from two documents at once. task0027 removes the
two restatements; task0029, if stating the authorization-consumption
procedure requires a new rule in `workflow-patch.md`, updates that
document's own count in the same edit. Affects task0027, task0029.

### D13 — A verify-sourced spec change is admitted, not excluded (verify round 1)

The alternative on the table was to declare verify-sourced rework outside
the classification gate's scope and say so in SPEC.md. It was rejected: FR7
requires every case reaching `gate_id: rework.spec-change` in batch to pass
through the gate, so excluding a whole rework source is a requirement
change, not an implementation of the requirement. The origin vocabulary is
widened instead (Shared Components, Spec-change origin identity), which
leaves FR7 as written and needs no SPEC change. Affects task0028, task0029.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| An edit trips an existing repository-wide guard (carrier scan, exclusion-rule scan, forbidden literals) | High | Task fails late, in another task's module | C6 lists every known guard as a hard convention; each task re-runs the full suite before finishing |
| A pinned sentence a task must change is asserted in a module owned by another task | Medium | Cross-task test conflict at merge | Test-module ownership is one-to-one with document ownership (C4/C5); no module appears in two tasks' file sets |
| A rule needs a document outside the declared change set (validator script, design input) | Medium | Scope violation or a broken guard | C8: report as a plan deviation instead of editing; D1/D5 were chosen specifically to avoid the two known cases |
| Two tasks pick different names for a shared field (`goal`, audit fields, scan category) | Medium | Integration mismatch found only at review | Shared Components fixes every name and value vocabulary before implementation starts |
| The wording-correction route implies a new worker output field | Medium | Contract drift between synthesis SSOT and worker contract | task0003 owns the synthesis document, the rework-planner contract and its prompt together, so the decision is settled inside one task |
| Full-suite regressions accumulate across parallel worktrees | Medium | Verify-phase failure | VERIFICATION.md runs the whole suite on the integrated branch; TS-10 is a dedicated scenario |

## Open Questions

- [ ] FR20 is resolved as an **assumption** (A-6, decision D3), not as an
      investigated fact: no pre-existing feature was surveyed for how often a
      batch run actually reaches `rework.spec-change` without a goal block.
- [ ] Whether the requirements-document template's declared-change-set
      section must change together with the SPEC template (task0009 decides
      inside its own scope; both files are in that task's set).
- [ ] Whether the wording-correction route needs a dedicated field in the
      rework-planner result shape, or fits the existing zero-task branch
      (task0003 decides inside its own scope).
