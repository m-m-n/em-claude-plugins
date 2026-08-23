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
