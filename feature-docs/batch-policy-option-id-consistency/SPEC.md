# Feature: batch-policy-option-id-consistency

## Overview

`em-workflow/references/batch-policies.yaml` names an `option_id` for every
`action: select` gate, but some of those option_ids are not offered by the site
that issues the gate's option vocabulary. When that happens, a batch run hits
`question-resolution.md`'s step-6 protocol-error abort at a non-blocking
preference gate. This feature reconciles every such gate by extending its
issuing site to declare and offer the option_id the policy names, and adds a
mechanical check so the same drift cannot recur silently.

Requirements source: `feature-docs/batch-policy-option-id-consistency/REQUIREMENTS.md`.

## Objectives

- Make every `action: select` entry in `em-workflow/references/batch-policies.yaml`
  resolvable against the option_ids its gate actually offers, so a batch run never
  hits `question-resolution.md`'s step-6 protocol-error abort at a non-blocking
  preference gate.
- Establish, for every such gate, an identified issuing site whose offered
  option_ids include the option_id the policy names, with `batch-policies.yaml`
  as the authoritative side of that correspondence.
- Make that correspondence machine-checked so the same drift cannot recur
  silently, or document why a given gate cannot be checked and what guarantee it
  has instead.

## User Stories

### US1: A batch run resolves a select gate against the policy

As a batch run (`--batch`), I want the `option_id` recorded in
`batch-policies.yaml` for a gate to be one the gate actually offers, so that I
can resolve a non-blocking preference gate instead of aborting with a protocol
error.

**Acceptance Criteria:**
- [ ] Applying `batch-policies.yaml`'s `create-spec.design-step` policy selects an
      option requirements-analyst genuinely offers, because the analyst's issuing
      site declares `decide_autonomously`; the policy file's option_id is unchanged.
- [ ] `create-spec.design-system`'s `top_candidate_or_none` is declared at its
      issuing site alongside the `project_native` / `em_workflow` / `none`
      vocabulary, so the design-system gate resolves in batch mode.
- [ ] All 11 `batch-policies.yaml` entries with `action: select` + `option_id` have
      an identified issuing site and a holding correspondence.

### US2: A maintainer is told when the correspondence drifts

As an em-workflow maintainer, I want the policy-to-issuing-site correspondence to
be checked by the test suite, so that a drift fails a test rather than surfacing
as a batch-run abort.

**Acceptance Criteria:**
- [ ] A test under `tests/` fails when any of those correspondences is broken; for
      any gate not mechanically checkable, the reason and the alternative guarantee
      are documented in the plugin's documentation.
- [ ] `tests/test_validate_worker_output.py:1269` and the
      `valid-design-step-correct-binding` fixture are byte-identical to their
      pre-change state.
- [ ] `em-workflow/references/workflow-patch.md` and
      `em-workflow/scripts/validate-worker-output.py` are unmodified.
- [ ] `python3 -m unittest discover -s tests` passes.
- [ ] em-workflow's version is bumped in `em-workflow/.claude-plugin/plugin.json`
      and set to the same value in `.claude-plugin/marketplace.json`.

## Technical Requirements

### Functional Requirements

- **FR1 - create-spec.design-step resolves against the policy's option_id:**
  `batch-policies.yaml`'s `create-spec.design-step` entry keeps its option_id
  `decide_autonomously` unchanged, and requirements-analyst's issuing site
  (`em-workflow/references/contracts/analyst-contract.md` together with the
  requirements-analyst agent prompt) declares and offers `decide_autonomously` as
  an option of the `create-spec.design-step` gate, with that option's semantics
  documented at the issuing site. `tests/test_validate_worker_output.py:1269` and
  the `valid-design-step-correct-binding` fixture are left unmodified.

- **FR2 - Identified issuing site per select gate:** For each of the 11
  `batch-policies.yaml` entries carrying `action: select` plus an `option_id`
  (`create-spec.feature-identity`, `create-spec.design-step`,
  `create-spec.design-system`, `design-system.reclassify`, the three
  `*.artifact-overwrite` gates, `create-spec.stalled`,
  `create-plan.tbd-resolution`, `create-plan.license-conflict`,
  `create-plan.existing-files`), the site that issues its option vocabulary is
  identified, and that site's offered option_ids include the option_id the policy
  names.

- **FR3 - create-spec.design-system's second latent mismatch:**
  `create-spec.design-system`'s policy option_id `top_candidate_or_none` stays as
  written, and its issuing site (`create-spec-phase.md` step 11a, which today
  documents only a `project_native` / `em_workflow` / `none` vocabulary for that
  gate) is extended to declare and offer `top_candidate_or_none` with documented
  semantics.

- **FR4 - Option vocabularies that exist only in the policy file:** Every
  option_id that today appears nowhere outside `batch-policies.yaml` —
  `derive_from_task_description`, `top_candidate_or_none`,
  `compatible_alternative`, `merge`, `assume`, and `create-spec.stalled`'s
  `record_tbd` — gains a declared, documented vocabulary entry at its gate's
  issuing site. No such option_id is renamed to fit a site's existing vocabulary.

- **FR5 - Mechanical consistency check:** The repository-root unittest suite gains
  a check that fails when a `batch-policies.yaml` `action: select` entry names an
  option_id that its gate's issuing site does not offer, covering every such entry
  rather than `create-spec.design-step` alone.

- **FR6 - Documented fallback for uncheckable gates:** For any select gate whose
  correspondence cannot be checked mechanically, the reason and the compensating
  guarantee are recorded in the plugin's own documentation rather than left
  implicit.

- **FR7 - Existing structural tests updated in the same change:**
  `tests/test_batch_policies.py`, which pins the policy file's structure and its
  gate-ID set, and any other test asserting on the touched values are updated
  within this change so the suite reflects the new documented vocabularies.

- **FR8 - Plugin version bump:** `em-workflow/.claude-plugin/plugin.json`'s
  `version` is bumped from 0.1.41, and the em-workflow entry in the
  repository-root `.claude-plugin/marketplace.json` is set to that same value.

### Non-Functional Requirements

- **NFR1 - Frozen files:** `em-workflow/references/workflow-patch.md` and
  `em-workflow/scripts/validate-worker-output.py` are not modified by this change.

- **NFR2 - No third-party imports in test code:** The new check imports no
  third-party package (no PyYAML); it reuses or reimplements the restricted-subset
  YAML parser already present in `tests/test_batch_policies.py`, per
  `test/README.md`'s test-scoped no-external-dependencies rule.

- **NFR3 - Whole suite stays green:** `python3 -m unittest discover -s tests`
  passes for the entire suite, not only for the changed test module.

- **NFR4 - SSOT preserved:** `batch-policies.yaml` remains the single source of
  truth for gate_id-carrying gates. The change introduces no second policy table
  and moves no gate into `batch-mode.md`'s Non-packet gates table.

- **NFR5 - Direction of reconciliation is uniform:** Every reconciliation in this
  change moves the issuing site toward the policy file. No `batch-policies.yaml`
  option_id is rewritten to match a drifted worker or protocol vocabulary.

## Implementation Approach

### Architecture

The change spans three kinds of artifact and no runtime code path:

```
em-workflow/references/batch-policies.yaml   (authoritative side; option_ids unchanged)
                 |
                 |  correspondence: policy option_id ∈ issuing site's offered option_ids
                 v
issuing sites:
  - worker contracts     (e.g. references/contracts/analyst-contract.md)   -> FR1
  - phase protocols      (e.g. references/create-spec-phase.md step 11a)   -> FR3
  - agent prompts        (requirements-analyst prompt)                     -> FR1
                 |
                 |  verified by
                 v
tests/  (repository-root unittest suite)                                   -> FR5, FR7
                 |
                 |  exemptions recorded in
                 v
plugin documentation (reason + compensating guarantee)                     -> FR6
```

Reconciliation direction is one-way per NFR5: the issuing site moves toward the
policy file, never the reverse. `batch-policies.yaml` stays the single policy
table per NFR4.

### Data Flow

```
batch run -> gate raised -> issuing site's offered option_ids
                              ^
                              | must contain
batch-policies.yaml entry ----+ option_id  -> resolved selection (no step-6 abort)
```

### Gate inventory (FR2)

| # | gate_id | policy option_id | issuing site |
|---|---------|------------------|--------------|
| 1 | `create-spec.feature-identity` | as recorded in `batch-policies.yaml` | identified by FR2 |
| 2 | `create-spec.design-step` | `decide_autonomously` | `references/contracts/analyst-contract.md` + requirements-analyst prompt (FR1) |
| 3 | `create-spec.design-system` | `top_candidate_or_none` | `references/create-spec-phase.md` step 11a (FR3) |
| 4 | `design-system.reclassify` | as recorded in `batch-policies.yaml` | identified by FR2 |
| 5 | `*.artifact-overwrite` (gate 1 of 3) | as recorded in `batch-policies.yaml` | identified by FR2 |
| 6 | `*.artifact-overwrite` (gate 2 of 3) | as recorded in `batch-policies.yaml` | identified by FR2 |
| 7 | `*.artifact-overwrite` (gate 3 of 3) | as recorded in `batch-policies.yaml` | identified by FR2 |
| 8 | `create-spec.stalled` | `record_tbd` | identified by FR2; `record_tbd` also gains a documented vocabulary entry (FR4) |
| 9 | `create-plan.tbd-resolution` | as recorded in `batch-policies.yaml` | identified by FR2 |
| 10 | `create-plan.license-conflict` | as recorded in `batch-policies.yaml` | identified by FR2 |
| 11 | `create-plan.existing-files` | as recorded in `batch-policies.yaml` | identified by FR2 |

The option_ids that exist only in the policy file today —
`derive_from_task_description`, `top_candidate_or_none`,
`compatible_alternative`, `merge`, `assume`, `record_tbd` — each gain a declared,
documented entry at their gate's issuing site (FR4), and none is renamed.

The count of 11 reflects `batch-policies.yaml` at base revision bb33560; if the
file gains or loses such an entry before implementation, FR2's enumeration
follows the file rather than that number.

### Dependencies

**Internal Dependencies:**
- `em-workflow/references/batch-policies.yaml`: the authoritative policy table.
- `em-workflow/references/question-resolution.md`: defines the step-6
  protocol-error abort this feature prevents reaching.
- `em-workflow/references/contracts/analyst-contract.md` and the
  requirements-analyst agent prompt: the `create-spec.design-step` issuing site.
- `em-workflow/references/create-spec-phase.md` step 11a: the
  `create-spec.design-system` issuing site.
- `em-workflow/references/batch-mode.md`: its Non-packet gates table stays
  unchanged (NFR4).
- `tests/test_batch_policies.py`: pins the policy file's structure and gate-ID
  set; its restricted-subset YAML parser is reused or reimplemented (NFR2).
- `test/README.md`: the test-scoped no-external-dependencies rule.

**External Dependencies:**
- None. The new check imports no third-party package (NFR2).

### File Structure

```
em-workflow/
├── references/
│   ├── batch-policies.yaml            # authoritative; option_ids unchanged
│   ├── create-spec-phase.md           # step 11a gains top_candidate_or_none (FR3)
│   ├── contracts/
│   │   └── analyst-contract.md        # gains decide_autonomously (FR1)
│   ├── workflow-patch.md              # FROZEN (NFR1)
│   └── ...                            # other issuing sites / FR6 documentation
├── agents/                            # agent prompts issuing gate vocabularies
├── scripts/
│   └── validate-worker-output.py      # FROZEN (NFR1)
└── .claude-plugin/plugin.json         # version bump (FR8)
.claude-plugin/marketplace.json        # same version (FR8)
tests/
├── test_batch_policies.py             # updated (FR7)
├── test_validate_worker_output.py     # line 1269 + fixture byte-identical (FR1)
└── <new correspondence check module>  # (FR5)
```

## Declared Change Set

Feature-specific paths:

- `em-workflow/references/batch-policies.yaml`
- `em-workflow/references/contracts/analyst-contract.md`
- `em-workflow/references/create-spec-phase.md`
- `em-workflow/references/**` (the remaining select-gate issuing sites FR2
  identifies — contract and phase-protocol documents — and FR6's documentation
  destination)
- `em-workflow/agents/**` (agent prompts that issue gate option vocabularies)
- `em-workflow/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `tests/**` (FR5's new check module and FR7's update to
  `tests/test_batch_policies.py`)

Every SPEC declares, by default, the following two workflow-generated entries in
addition to the feature-specific paths above:

- `feature-docs/{feature}/**`
- `test-docs/{feature}/**`

`feature-docs/{feature}/**` covers `REQUIREMENTS.md`, `SPEC.md`, `workflow.yaml`,
`phase-state/`, `tasks/`, `reviews/roundN.yaml`, `VERIFICATION.md`,
`retrospect.yaml`, and the design artifacts the design step produces. These are
generated and owned by the phase documents and by `references/phase-state.md`;
this section cites them and restates none of their rules.

`test-docs/{feature}/**` covers `test-docs/{feature}/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`; this
section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC author
explicitly removes them; their absence is never assumed by silence.

This declaration is a SUPERSET assertion: the actual change set observed at
verification time must be CONTAINED IN the declared set, not equal to it. A
declared path that never materializes is not a violation.

**Declared but must not be modified.** `tests/**` is declared, yet
`tests/test_validate_worker_output.py:1269` and the
`valid-design-step-correct-binding` fixture must remain byte-identical to their
pre-change state (FR1). `em-workflow/references/**` is declared, yet
`em-workflow/references/workflow-patch.md` must not be modified, and neither must
`em-workflow/scripts/validate-worker-output.py` (NFR1).

## Test Scenarios

### Unit Tests

- [ ] **TS1** Coverage scenario: a test enumerates every `batch-policies.yaml`
      entry with `action: select` and asserts each one carries an `option_id`, and
      that the set of such gate_ids equals an explicitly pinned expected set of 11
      — so a newly added select gate fails the test until it is deliberately
      registered. (FR2, FR5, FR7)
- [ ] **TS2** Correspondence scenario: for each select gate, the test resolves its
      issuing site (a path plus the section declaring that gate's option
      vocabulary), parses the offered option_ids, and asserts the policy's
      option_id is a member. A deliberately mutated policy option_id in a
      temporary copy makes the assertion fail. (FR2, FR5)
- [ ] **TS3** design-step regression scenario: a test asserts
      `create-spec.design-step`'s policy option_id is exactly
      `decide_autonomously` and that `analyst-contract.md`'s declared design-step
      option vocabulary contains `decide_autonomously`, pinning the answered
      direction. (FR1, FR5)
- [ ] **TS4** design-system regression scenario: a test asserts
      `create-spec.design-system`'s policy option_id is exactly
      `top_candidate_or_none` and that `create-spec-phase.md` step 11a's declared
      vocabulary contains it in addition to `project_native` / `em_workflow` /
      `none`. (FR3, FR4, FR5)
- [ ] **TS7** Non-select scenario: a test asserts
      `create-spec.requirement-clarification` and `create-spec.command-approval`
      carry no `option_id` and are excluded from the correspondence check.
      (FR2, FR5)
- [ ] **TS10** Version-sync scenario: a test asserts
      `em-workflow/.claude-plugin/plugin.json`'s version equals the em-workflow
      entry's version in `.claude-plugin/marketplace.json` and is strictly greater
      than 0.1.41. (FR8)
- [ ] **TS11** Parser-robustness scenario: the restricted-subset YAML parser used
      by the check handles the option vocabularies as they are actually expressed;
      a fixture using the chosen representation parses without raising. (NFR2)

### Integration Tests

- [ ] **TS9** Frozen-file scenario: a test asserts
      `em-workflow/references/workflow-patch.md` and
      `em-workflow/scripts/validate-worker-output.py` are not modified by this
      change. (NFR1)
- [ ] **TS12** Suite scenario: `python3 -m unittest discover -s tests` completes
      with zero failures and zero errors. (NFR3)

### E2E Tests

**Existing E2E tests**: None — the repository has no E2E infrastructure.
**Run command**: None (intentionally empty, not undetected).

### Edge Cases

- [ ] **TS5** `on_unanswered` disambiguation scenario: a test asserts that
      `create-spec.stalled`'s option_id `record_tbd` is validated against its
      gate's offered options only, and that an occurrence of `record_tbd` in an
      `on_unanswered` field alone does not satisfy the correspondence check.
      (FR4, FR5)
- [ ] **TS6** Absence scenario: a test asserts `rework.spec-change` remains absent
      from `batch-policies.yaml` and that the coverage check does not report it as
      a missing entry. (FR2, FR5)
- [ ] **TS8** Uncheckable-gate documentation scenario: for any gate the checker
      cannot verify mechanically, a test asserts the documented reason and
      compensating guarantee exist at the recorded documentation path, so an
      undocumented exemption fails. (FR6)

### Performance Tests

Not applicable. No performance requirement was established for this change.

## Security Considerations

Not applicable. The change is confined to a YAML policy file, Markdown
reference/contract/protocol documents, the Python unittest suite, and two version
fields in JSON manifests; no authentication, authorization, data-handling, or
network surface is introduced.

## Error Handling

The failure mode this feature addresses is `question-resolution.md`'s step-6
protocol-error abort, reached when a batch run applies a policy whose `option_id`
is not among the option_ids the gate offers. After this change, that abort is not
reachable at any of the 11 select gates, because each gate's issuing site offers
the option_id its policy names (FR2). Drift that would restore the failure mode is
surfaced as a test failure instead (FR5), or, where mechanical checking is not
possible, by the documented reason and compensating guarantee (FR6).

## Performance Optimization

Not applicable. No performance goal was established for this change.

## Success Criteria

- [ ] Applying `batch-policies.yaml`'s `create-spec.design-step` policy selects an
      option requirements-analyst genuinely offers, because the analyst's issuing
      site declares `decide_autonomously`; the policy file's option_id is
      unchanged.
- [ ] `create-spec.design-system`'s `top_candidate_or_none` is declared at its
      issuing site alongside the `project_native` / `em_workflow` / `none`
      vocabulary, so the design-system gate resolves in batch mode.
- [ ] All 11 `batch-policies.yaml` entries with `action: select` + `option_id`
      have an identified issuing site and a holding correspondence.
- [ ] A test under `tests/` fails when any of those correspondences is broken; for
      any gate not mechanically checkable, the reason and the alternative guarantee
      are documented in the plugin's documentation.
- [ ] `tests/test_validate_worker_output.py:1269` and the
      `valid-design-step-correct-binding` fixture are byte-identical to their
      pre-change state.
- [ ] `em-workflow/references/workflow-patch.md` and
      `em-workflow/scripts/validate-worker-output.py` are unmodified.
- [ ] `python3 -m unittest discover -s tests` passes.
- [ ] em-workflow's version is bumped in `em-workflow/.claude-plugin/plugin.json`
      and set to the same value in `.claude-plugin/marketplace.json`.

## Assumptions

These are the assumptions requirements-analyst recorded; they are carried here
unchanged.

1. **Reconciliation direction** (recorded under batch policy
   `record_as_assumption: true`): the direction is `pin_worker_vocabulary` —
   `em-workflow/references/batch-policies.yaml` is authoritative for every
   `action: select` gate's option_id, and each gate's issuing site (worker
   contract, agent prompt, or phase protocol) must declare and offer the option_id
   the policy names. No policy option_id is rewritten to match a worker's drifted
   vocabulary. This was resolved by Codex consultation under gate_id
   `create-spec.requirement-clarification` (action: `codex_consultation`) during a
   batch run, not by the user; the user has not confirmed it.
2. **Consequence of that assumption**, likewise unconfirmed by the user:
   requirements-analyst gains `decide_autonomously` in its
   `create-spec.design-step` option vocabulary, and `create-spec-phase.md` step
   11a gains `top_candidate_or_none` in the `create-spec.design-system`
   vocabulary, rather than either policy entry being renamed.
3. The count of 11 `action: select` + `option_id` entries reflects
   `batch-policies.yaml` at base revision bb33560; if the file gains or loses such
   an entry before implementation, FR2's enumeration follows the file rather than
   the number stated here.
4. The repository has no LICENSE file at its root, so the feature inherits no SPDX
   obligation; license detection returned `none` with high confidence.
5. The repository has no build step, no configured formatter, and no E2E
   infrastructure; the corresponding command fields are intentionally empty strings
   rather than undetected values.

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

None. Every requirement (FR1-FR8, NFR1-NFR5) is `status: confirmed`. The
unconfirmed items are the assumptions listed above, not requirements.

## Design Step

Skipped. The change is confined to a YAML policy file, Markdown
reference/contract/protocol documents, the Python unittest suite, and two version
fields in JSON manifests. There is no user interface, no visual surface, and no
design-system candidate anywhere in the repository, so a design step would produce
nothing consumable.

## References

- Requirements document: `feature-docs/batch-policy-option-id-consistency/REQUIREMENTS.md`
- Batch policy SSOT: `em-workflow/references/batch-policies.yaml`
- Step-6 protocol-error abort: `em-workflow/references/question-resolution.md`
- create-spec.design-step issuing site: `em-workflow/references/contracts/analyst-contract.md`
- create-spec.design-system issuing site: `em-workflow/references/create-spec-phase.md` (step 11a)
- Non-packet gates table: `em-workflow/references/batch-mode.md`
- Existing structural test: `tests/test_batch_policies.py`
- Test-scoped dependency rule: `test/README.md`
