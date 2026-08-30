# Implementation Plan: rework-contract-drift

## Overview

Close four producer/consumer contract breaks left by the goal-vs-spec-divergence
verify-origin rework, replace every drifted restatement with a citation of its owning
SSOT, and add coverage that fails against the pre-change tree. The change surface is
Markdown SSOT documents, one agent prompt, one Python validator, fixtures, and
stdlib `unittest` tests.

## Technology Stack

- **Language**: Python 3.14 — stdlib `unittest` only for test code (NFR5, A7). No new
  third-party dependency is introduced by any task.
- **Documents**: Markdown SSOT documents under `em-workflow/references/`, one agent
  prompt, one skill document.
- **Runtime dependency (unchanged)**: `scripts/validate-worker-output.py` keeps using
  PyYAML, a plugin runtime dependency and not a test dependency (A7).
- **License**: `project.license` is `none`, so no license compatibility constraint
  applies. No task adds a dependency, so no new license enters the project.

## Layer Structure

Four artifact classes, with a strict one-way dependency direction. Nothing lower may
redefine something higher; it may only cite it.

| Layer | Members | May depend on |
|---|---|---|
| Definition (SSOT) | `workflow-patch.md`, `workflow-schema.md`, `phase-state.md`, `question-packet-schema.md`, `rework-task-synthesis.md` | nothing in this feature |
| Procedure | `question-resolution.md`, `skills/develop/SKILL.md` | Definition layer, by citation only |
| Contract / prompt | `contracts/planner-contract.md`, `contracts/rework-planner-contract.md`, `agents/implementation-planner.md` | Definition and Procedure layers, by citation only |
| Enforcement | `scripts/validate-worker-output.py`, `references/fixtures/`, repository-root `tests/` | all of the above |

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| `failed_items[].category` vocabulary | The single closed value set for a verify-step failure's category | Exactly seven values: `comprehensive`, `spec`, `security`, `performance`, `architecture`, `license`, `unknown`. Required and non-empty on every entry. Defined once in `references/workflow-schema.md` (task0003); every other site cites that definition and restates neither the field nor the vocabulary. Post: a consumer presented with a missing, empty, unreadable or out-of-vocabulary value resolves to abort/reject, never to a default | task0003 (defines), task0004 (cites in the gate; enforces in the validator) |
| Origin identity pair | The `origin_kind` / `origin_id` pair naming a spec-change record's origin | Defined once by `references/rework-task-synthesis.md` Invariant 6. `origin_kind` is closed to `review` and `verify`; `origin_id` is a non-empty string. Every citing site names the pair and defers the definition. The retired single-field name is not used anywhere outside the exclusions in D3 | task0002 (authorization condition), task0004 (packet schema, gate, validator), task0005 (phase-state record) |
| Synthetic spec-change record shape in tests | The record shape any test builds when it needs a spec-change phase-state | Every synthetic `spec_change` record a test constructs carries a valid `origin_kind` (one of the two values above), a non-empty `origin_id`, a non-empty `reason`, a non-empty `recorded_at_commit`, and a boolean `replan_authorized` — unless the test exists precisely to prove one of those is rejected. This keeps tests written by one task valid under the vocabulary enforcement added by another | task0001, task0004, task0005 |
| Byte-identity digest pins | The pinned digests in `tests/test_gate_option_vocabulary.py` guarding incidental edits | Each pinned file has exactly ONE owning task (D2). A task that changes a pinned file refreshes that file's pin, and only that pin, in the same change, leaving every other pinned constant untouched. Post: after integration each pin equals the digest of the file its owner delivered | task0002 (the workflow-patch document pin), task0004 (the validator, validator-test and fixture pins) |
| Retired-identifier absence scan | Owner-scoped scans proving the retired origin field name is gone | Each scan reads live files, covers a stated closed path set its owning task fully controls, and builds its search term at run time rather than carrying it as a contiguous literal in its own source, so the scan never matches itself. The scans' path sets are disjoint and their union is the surface named in D3 | task0002, task0004, task0005 |
| Plugin version value | The single raised version carried by both plugin manifests | Exactly one task writes `em-workflow/.claude-plugin/plugin.json` and the matching entry in the root `.claude-plugin/marketplace.json`, to the same value, a patch-level increment over the current one. No other task touches either manifest | task0006 only |

## Conventions

- **Citation over restatement (NFR2).** A rule is written out in exactly one document.
  Every other mention names the owning document by repository-relative path and says
  the rule is not restated there. A fix never corrects a copy in place; it deletes the
  copy and cites the owner.
- **Live reads only (NFR4).** Every added assertion reads the document, script or
  fixture from the working tree. No assertion is satisfied by a frozen revision of a
  file, because a frozen read is how the re-planning authorization drift survived the
  existing suite.
- **Test placement and shape (NFR5, A6).** Test files live in the repository-root
  `tests/` directory, named `test_*.py`; classes are named for the behavior under test
  and methods name the condition and the expected result. Standard library only. The
  suite is run with the project's own runner. Nothing test-related is added under
  `em-workflow/`, which ships to users' plugin caches.
- **Negative proof.** Every absence assertion is paired with a check that the same
  matcher fires against a synthetic violating sample, so an absence can never pass
  vacuously. This mirrors the convention already used throughout the suite.
- **One module per owned section.** A test module asserts only over the documents its
  owning task changes. A module that pins a document another task changes is that
  other task's to edit.
- **Abort wording.** Every newly written abort arm states that it is final and
  non-overridable, matching the wording the existing membership check uses, and records
  its reason and the evidence considered. No new arm raises, in an unattended run, a
  confirmation nobody can answer.

## Cross-task Design Decisions

### D1 — Ownership map is the SPEC's, applied verbatim

The rule-to-owner assignment is the one SPEC.md states in its Ownership map; this plan
does not re-derive or extend it. Each task's plan names the owner it must cite and is
forbidden from writing the owning text itself.

### D2 — Single-owner rule for every digest-pinned or cross-cutting file

`tests/test_gate_option_vocabulary.py` holds byte-identity pins over
`em-workflow/references/workflow-patch.md`, `em-workflow/scripts/validate-worker-output.py`,
`tests/test_validate_worker_output.py` and one fixture file. A pinned file that two
tasks changed in parallel would leave at least one pin wrong after integration, so each
pinned file has exactly one owning task:

| Pinned file | Owning task |
|---|---|
| `em-workflow/references/workflow-patch.md` | task0002 |
| `em-workflow/scripts/validate-worker-output.py` | task0004 |
| `tests/test_validate_worker_output.py` | task0004 |
| `em-workflow/references/fixtures/` | task0004 |

This is why the validator half of the required-category work sits in task0004 rather
than with the definition in task0003: the definition and its enforcement are bound
only by the vocabulary contract in Shared Components, which both sides implement
independently. task0002 and task0004 both edit
`tests/test_gate_option_vocabulary.py`, each refreshing only its own constant; the
edits are to disjoint constants, so a correct merge keeps both.

### D3 — Retired-identifier elimination is partitioned by document ownership

The retired origin field name must be gone from the normative documents, the validator,
the fixtures and the tests. Its occurrences are partitioned so that no two tasks touch
the same occurrence and none is orphaned:

| Site | Owning task |
|---|---|
| `em-workflow/references/workflow-patch.md`, `tests/test_workflow_patch_doc.py` | task0002 |
| `em-workflow/references/question-packet-schema.md`, `question-resolution.md`, `contracts/rework-planner-contract.md`, `scripts/validate-worker-output.py`, `references/fixtures/` | task0004 |
| `tests/test_classification_gate.py`, `test_worker_contract_docs.py`, `test_rework_synthesis_contract.py`, `test_question_resolution_doc.py`, `test_validate_worker_output.py`, `test_gate_option_vocabulary.py`, `test_spec_change_origin_binding.py`, `test_spec_change_replan_authorization.py`, `test_replanning_carry_over.py` | task0004 |
| `tests/test_phase_state_doc.py` | task0005 |

**Stated exclusions.** The name legitimately survives in this feature's own
`feature-docs/rework-contract-drift/REQUIREMENTS.md` and `SPEC.md` (which name the
retired field in order to require its removal), in the completed
`feature-docs/goal-vs-spec-divergence/` and `test-docs/` records of the previous
feature (rewriting a delivered record would falsify history), and in git history. No
task edits any of these. Every scan states this exclusion set explicitly rather than
silently skipping it.

### D4 — The repository-wide absence check is split across owners, and re-observed at verify

No single task owns every occurrence in D3, so a single repository-wide scan could not
be green inside any one task's worktree — full parallelism means a task never sees
another task's change. The scan is therefore realized as owner-scoped scans (Shared
Components), whose path sets are disjoint and whose union is the surface in D3 minus
the stated exclusions. The union is observed together for the first time in the verify
phase, which VERIFICATION.md covers as its own scenario. This is the only form of the
requirement compatible with "all tests green inside the task's own worktree".

### D5 — The phase-state format version resolution is a stated compatibility rule

The SPEC requires exactly one of a migration rule, a compatibility rule, or a justified
version transition, and forbids leaving an in-flight on-disk rework record silently
non-re-enterable. **The chosen resolution is a stated compatibility rule: the format
version stays at its current value.** Its content, which task0005 writes into
`references/phase-state.md`, is that a record written before the shape change remains
readable as that same version; its pre-change spec-change shape is refused at the point
of use by the fail-closed conditions that already require the origin pair, with a named
diagnostic and a named remedy; and the remedy is that the spec-change transition
rewrites the record wholesale on its next occurrence, which the document already
guarantees, so re-entry is restored by re-recording rather than by accepting an
unverifiable origin.

Rationale, and why the other two were rejected:

- A version transition would force `scripts/validate-worker-output.py`, every
  phase-state fixture and their tests to move as well. Those files are owned by
  task0004 under D2, so the transition would either break the single-owner rule or
  merge two unrelated large changes. Its only benefit — an older plugin refusing a
  newer record — is not reachable within one repository checkout.
- A migration rule would have to synthesize an `origin_kind` that was never recorded.
  Inventing an origin that the membership check then "verifies" weakens fail-closed
  strength, which NFR1 forbids outright.
- The compatibility rule adds no new arm that can resolve to anything but refusal on
  absent evidence, so it cannot regress NFR1.

This choice was made by the planner because SPEC.md states the obligation without
naming which of the three to take; it is reversible and is raised as an open question.

### D6 — Section boundaries inside the two shared documents

`em-workflow/skills/develop/SKILL.md` is edited by two tasks in disjoint sections:
task0002 changes only the instruction that records the interruption reason and the
record's origin; task0003 changes only the verify step that records failing items.
Neither task touches the other's section. Likewise, within
`references/question-resolution.md` all of this feature's changes fall inside the
classification gate's origin-verification step and are owned by task0004 alone.

### D7 — Where the required-category fail-closed abort lives

The abort belongs to the classification gate, never to the verify phase. The verify
phase assigns the sentinel value and lets the case reach the gate; aborting earlier
would recreate the gate-passage violation the previous feature's specification forbids.
task0003 writes the assignment side, task0004 writes the gate side, and each states the
other side's existence by citation only.

### D8 — Rule-18 recovery lives in the patch contract, not in phase-state

The recovery and idempotency rule for the interrupted authorization consumption is
written in `references/workflow-patch.md` (task0002), which owns the application rules;
`references/phase-state.md`'s idempotency section (task0005) gains only the replay rule
for the append-type classification record. Neither document restates the other's rule.

### D9 — Rework round 1: the pin module and every pinned file have a single owner

D2 assigned each digest-pinned file an owning task and allowed two tasks to edit
`tests/test_gate_option_vocabulary.py` concurrently on disjoint constants. Round
1 delivery showed the cost of that allowance: the concurrent edits produced a
cross-worktree incident and a deviation on the neighbouring count-sentence pin.
For the rework round the rule is tightened rather than repeated — **task0008 is
the sole owner of `tests/test_gate_option_vocabulary.py` and of every file it
pins**, and no other rework task changes a pinned file:

| Pinned file | Owning task (rework round 1) |
|---|---|
| `em-workflow/references/workflow-patch.md` | task0008 |
| `em-workflow/scripts/validate-worker-output.py` | task0008 |
| `tests/test_validate_worker_output.py` | task0008 |
| `em-workflow/references/fixtures/` (the pinned case) | unchanged this round |

The count-sentence pin over the patch contract document in
`tests/test_spec_change_replan_authorization.py` follows the same rule and is
task0008's this round. This supersedes D2's owner rows for the duration of the
rework round; D2's rationale (a pinned file changed by two tasks in parallel
leaves at least one pin wrong after integration) is unchanged — only the
allowance for a shared module is withdrawn.

### D10 — The patch contract may cite the phase-state document within the Definition layer

The Layer Structure table gives the Definition layer no dependencies inside this
feature. The rework round adds exactly one, in citation form only: the patch
contract's interrupted-spend recovery procedure defers its already-applied
determination to `references/phase-state.md`, which already owns that
determination and the per-patch record it reads. The dependency direction is
one-way (the phase-state document neither cites nor restates the recovery
procedure), no new field is introduced on either side, and D8 still holds — the
recovery rule's own text lives in the patch contract, not in phase-state. A
Definition-layer document citing another Definition-layer document is permitted
under this decision; restating one in the other is not.

### D11 — The failing-item category contract distinguishes definition, reach and point of use

The Shared Components row for the failing-item category vocabulary states that a
consumer presented with a missing, empty, unreadable or out-of-vocabulary value
resolves to abort or reject, never to a default. That postcondition is kept and
refined by a scope clause: **the patch validator's rejection surface is what the
patch reaches** — a failing item the patch supplies, or the entries of a verify
step the patch targets — while a pre-existing entry that the patch neither
supplies nor targets is not rejected there, because the party receiving the
rejection cannot repair it (the workflow record is orchestrator-owned and a step
patch may set only a status). The fail-closed treatment of such an entry happens
at its point of use, the classification gate, which is unchanged. The rule
itself is owned by `references/workflow-schema.md` as a pre-change compatibility
rule alongside the field's definition — the same shape the phase-state document
takes for its own destructive shape change (D5) — and the validator cites it.
This refines the row for task0008 without changing the field's required-ness or
its seven values, so task0003's and task0004's delivered halves stay valid.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| A byte-identity pin is left stale after integration, turning the suite red | Medium | High | D2's single-owner rule; each owner refreshes only its own pin; VERIFICATION.md re-runs the full suite after integration |
| Two tasks conflict textually inside `tests/test_gate_option_vocabulary.py` | Medium | Low | Disjoint constants; a conflict is textual only and both edits survive a correct resolution |
| A test module keeps the retired identifier as a literal because its own absence assertion needs it | High | Medium | The Shared Components contract requires the search term to be built at run time so the scan never matches itself |
| The chosen format-version resolution (D5) is not the one the user would have chosen | Medium | Medium | Raised as an open question; the change is confined to one document plus its tests, so reversing it is cheap |
| The definition of the required category and its enforcement drift apart because they sit in different tasks | Medium | High | The vocabulary is pinned once in Shared Components; both sides implement against it, and the integrated verify run exercises definition and enforcement together |
| task0004 is at the upper bound of a single implementer session | High | Medium | Its scope is fixed by the atomicity requirement forbidding a split; it is rated high complexity so the strongest review applies |
| A rejected finding (the alleged fixture migration gap, the performance findings) is reintroduced | Low | Medium | Named in every task's Out of Scope and covered by its own verification scenario |

## Open Questions

- [ ] D5's resolution of the phase-state format version is a planner-made choice: SPEC.md
      requires exactly one of three named resolutions but does not select one. The
      compatibility rule was chosen for the reasons in D5. Confirm before task0005 is
      implemented, or overturn it — the alternatives are listed there.
- [ ] The requirement that the retired identifier appear nowhere in the repository is
      applied to the surface in D3 with the stated exclusions, because this feature's own
      SPEC.md and REQUIREMENTS.md name the retired field in order to require its removal
      and cannot be rewritten by an implement task. Confirm the exclusion set.
- [ ] The requirement that the two rejected findings stay out is a feature-wide negative
      constraint with no natural implementing task; it is attached to task0004, where the
      rejected fixture claim would otherwise have landed, and is verified feature-wide.
