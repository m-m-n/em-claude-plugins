# Implementation Plan: implement-failed-kind

## Overview

Give the `implement` step's `failed` status a reason classification
(`failed_kind`) so an infrastructure-caused failure resumes the run
automatically while a decision-caused failure keeps returning control to a
human. The change is protocol documentation inside the `em-workflow`
plugin plus document-invariant tests; no runtime source changes.

## Technology Stack

- **Language / Framework**: Markdown (em-workflow protocol documents) +
  Python 3 standard library (`unittest`) for document-invariant tests.
- **Key libraries**: none. **No new dependency is introduced by this
  feature**, so no new license is recorded. `project.license` is `none`,
  so no license compatibility constraint applies to this plan.
- **Test runner**: `python3 -m unittest discover -s tests` (workflow.yaml
  `project.components.main.test_command`).

## Layer Structure

Three layers, with a strictly one-directional citation dependency:

| Layer | Files | Responsibility |
|---|---|---|
| Definition (SSOT) | `em-workflow/references/workflow-schema.md` | Sole owner of the `failed_kind` field: its vocabulary, its meanings, its required-ness, its lifecycle, its missing-value read rule, and the `batch` keys that record the infra auto-resume count |
| Consumer (protocol) | `em-workflow/references/implement-phase.md`, `em-workflow/skills/develop/SKILL.md`, `em-workflow/references/batch-mode.md`, `em-workflow/references/batch-terminal-line.md` | Write paths, the stop-condition branch, and the descriptive rows — each **cites** the definition layer by repository-relative path |
| Registry | `em-workflow/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` | Plugin version parity |
| Test | `tests/test_failed_kind_*.py` | One document-invariant module per task, asserting that layer's own statements |

**Allowed direction**: Consumer → Definition (citation only). The
definition layer never cites a consumer for the field's meaning, and no
consumer cites another consumer for it. The registry and test layers
depend on everything and are depended on by nothing.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|---|---|---|---|
| C1 `failed_kind` field definition | Closed two-value vocabulary `infra` / `decision`, their meanings, required-ness on the three write paths, and the missing-value read rule | Pre: none. Post: exactly one document states the vocabulary, the meanings and the missing-value rule; every other document that mentions the field names a value only inside a branch condition or a "this path writes X" statement, and cites the definition by repository-relative path. Detailed rule: D7 below | task0001 owns; task0002 / task0003 / task0004 cite |
| C2 Write-path classification | Which value each of the three terminal write paths sets | Pre: the write path is about to set the `implement` step's `status` to `failed`. Post: the same single write also carries `failed_kind`, valued per the table in D2 below; no additional write and no additional commit is introduced (NFR2) | task0002 owns; task0004 cites the batch row's summary |
| C3 `batch.infra_resume` record | Where the infra auto-resume count and its cap live | Key path `batch.infra_resume`, with member keys `rounds` (resumes already performed for this feature) and `cap` (the permitted maximum). An absent `batch` block, an absent `infra_resume` block, or an absent member key reads as `rounds: 0` and `cap: 2`. `rounds` is monotonic per feature and is never reset. The key definition and the unset-read rule are the definition layer's; the judgment that consumes them (when to increment, when the cap is reached, what happens at cap) is the develop skill's | task0001 owns the keys; task0003 owns the judgment |
| C4 `failed_kind` lifecycle | When the field is set, held and cleared | Set only in the same write that sets the `implement` step to `failed`. Held for exactly as long as that `failed` status. Cleared (set back to null) in the same write set that moves the `implement` step off `failed` — no separate write, no separate commit. Adopted assumption: `clear_on_leaving_failed` (D1) | task0001 owns the rule; task0002 and task0003 each apply it in their own write set |
| C5 Terminal-line contract | The batch terminal line's stop reason codes | Unchanged by this feature: the closed set stays at eleven codes, `stop-condition-3` stays mapped to `step_needs_intervention`, and the precedence rule keeps its current three phase-specific stop points. The infra auto-resume is **not** a stop and emits no terminal line, and is not an `--once` phase boundary of its own | task0004 owns the document; task0003 must not add a code or a boundary |
| C6 Plugin version baseline | Version parity across the two registries | Pre: both registries read `0.1.62`. Post: both read the identical value, on the `0.1.x` line, with the patch component strictly greater than 62; the `em-review` entry stays at `0.5.7` | task0005 only; no other task touches either registry file |

## Conventions

- **Document language**: follow the file being edited. `skills/develop/SKILL.md`
  is written in Japanese; every document under `em-workflow/references/` is
  written in English. Never switch a document's language.
- **Citation form**: reuse the citation form already used by the
  surrounding lines of the file being edited (plugin-relative
  `references/...` inside em-workflow documents). Do not introduce a new
  citation form. In `files` lists and in test modules, paths are
  repository-relative (`em-workflow/references/...`).
- **Editing discipline**: these documents are dense, cross-referenced
  SSOTs. Add the new branch or field to the existing structure; do not
  restructure, re-order or re-word surrounding rules that this feature
  does not change. Every existing carve-out named in FR6 (the
  `needs_update` auto-re-entry carve-out, and the batch verify-cap
  exception) stays byte-identical.
- **Error/edge policy**: every read of `failed_kind` and of the
  `batch.infra_resume` members treats an absent value as its defined
  default (C1, C3) rather than as an error. The defaults are chosen so
  that an unrecognised state falls back to the stopping behaviour
  (`decision`), never to the continuing one.
- **Test module convention** (matches `tests/test_failed_items_category.py`
  and `tests/test_verify_rework_lineage_cap_version_bump.py`): one module
  per task, standard library only, document text read from the repository
  root computed from the module's own path, exact-wording markers held as
  module constants and matched after whitespace normalisation, one
  negative proof per matcher against synthetic text, and a non-vacuity
  guard where a matcher could pass on absent input.
- **Test module naming**: `tests/test_failed_kind_<aspect>.py`, one file
  per task and never shared between tasks, so parallel tasks never edit
  the same test module.

## Cross-task Design Decisions

### D1 — `failed_kind` lifecycle is `clear_on_leaving_failed` (FR2)

Adopted from the answered TBD gate. The field is written only by the write
that sets `implement` to `failed`, and is returned to null by the same
write set that moves `implement` off `failed`. No extra write and no extra
commit are created for the clear, which is what keeps NFR2 intact.

Two write sets move `implement` off `failed` and therefore carry the
clear: the route-back-to-planning write set in the implement phase
(task0002), and the infra auto-resume write set in the develop skill
(task0003). Both are already single, committed-once write sets, so the
clear rides along.

*Affected tasks*: task0001 (states the rule), task0002, task0003.

### D2 — Classification per write path (FR3, FR4, FR5)

The three terminal write paths and the value each one writes:

| Write path | Value written | Rule |
|---|---|---|
| Implement phase I.2.c **abort phase**, reached by the interactive menu selection | `infra` when the task's failure originates from a journal `failed` event whose reason is `orphaned`; `decision` otherwise | FR3 |
| Implement phase I.2.c **abort phase**, reached by the batch `implement.failed-task` policy after a second failure of the same task | `decision`, unconditionally | FR4, adopted assumption `second_always_decision` |
| Implement phase I.2.c **route-back gate rejected** terminal | `decision`, unconditionally | FR5, adopted assumption `always_decision` |

**Precedence**: the two abort-phase entrances share one branch in the
document but not one rule. The batch second-failure entrance writes
`decision` even when the failure originated from an `orphaned` journal
event — the second row overrides the first for that entrance, and the
document must state that explicitly rather than leaving it to be inferred.
This does not change where the run stops: `references/batch-terminal-line.md`
already gives `implement-second-failure` precedence over `stop-condition-3`.

*Affected tasks*: task0002 (writes all three), task0004 (the batch-mode row
summarises the second-failure one and cites the implement phase for detail).

### D3 — Stop condition 3 branches on `failed_kind` (FR6)

For the `implement` step's `failed` status only, stop condition 3 fires
when `failed_kind` reads `decision`, and does not fire when it reads
`infra` and the auto-resume is admissible (D4, D5). Stop condition 3's
other trigger (`needs_update`) and its behaviour for the `review` and
`verify` steps are unchanged — this is SPEC assumption A3 and must be
stated as an explicit non-change, not left implicit.

*Affected tasks*: task0003 owns; task0004 reflects it in the
`step_needs_intervention` meaning row.

### D4 — Auto-resume cap, keys and procedure (FR7)

Adopted from the answered TBD gate: `cap_2`.

Admissibility and procedure, in order:

1. Step B has identified `implement` as the step to execute and reads its
   `status` as `failed`.
2. Read `failed_kind` (absent → `decision`, C1).
3. `decision` → stop condition 3 fires; nothing below runs.
4. `infra` and the run is not batch → stop condition 3 fires (D5).
5. `infra` and the run is batch → read `batch.infra_resume.rounds` and
   `.cap` (C3 defaults apply).
6. `rounds >= cap` → treated as `decision`: stop condition 3 fires, and
   the report names the cap as the reason. No write is made on this
   branch.
7. Otherwise → one workflow.yaml write set: set `implement` `status` to
   `pending`, clear `failed_kind` (D1), and increment
   `batch.infra_resume.rounds` by one. Commit that write set once with
   `commit-docs.sh` **before** executing the implement phase (NFR2). Then
   execute the phase.

The count is monotonic per feature and never reset, mirroring the existing
`review_rework_count` / `verify_rework.rounds` keys. The `batch` block's
creation rule is `references/batch-mode.md`'s and is cited, not restated.

*Affected tasks*: task0001 (defines the keys and the unset-read rule),
task0003 (owns steps 1–7).

### D5 — Auto-resume applies to batch only (FR8)

Adopted from the answered TBD gate: `batch_only`. In interactive mode,
stop condition 3 fires on an `implement` `failed` regardless of the
`failed_kind` value; the field is still written by the three write paths
(D2), it simply has no effect on the interactive stopping behaviour. This
matches the record location: `batch.infra_resume` lives in the `batch`
block, which exists only for a feature a `--batch` run has touched.

*Affected tasks*: task0003 owns; task0004's rows must not imply an
interactive behaviour change.

### D6 — No runtime source change; tests are document-invariant

SPEC assumption A4 (whether Python changes are needed) resolves to **no**:

- `failed_kind` is written by the orchestrator's own direct workflow.yaml
  writes. It never travels through a worker patch — a `step_patches`
  entry's `set` may touch only `status` — so
  `em-workflow/scripts/validate-worker-output.py` needs no change.
- No hook or script reads the `implement` step's status; the queue hooks
  read `tasks.{T}.status`, which this feature does not touch.

Consequence: NFR4's script/hook trigger does not fire. Every task still
ships a document-invariant `unittest` module, because that is this
project's established form for a protocol change and is what makes each
task's Acceptance Criteria test-translatable. NFR4's remaining obligation
— `python3 -m unittest discover -s tests` passing — applies to every task.

*Affected tasks*: all.

### D7 — SSOT citation discipline for a two-valued field (NFR1)

`failed_kind` differs from a field whose consumers never name its values:
every consumer here must name a value to state its own branch condition or
its own write. The discipline is therefore drawn at definition, not at
mention:

- **Permitted in a consumer**: naming a value inside a branch condition
  ("fires only when the value is `decision`"), or inside a statement of
  what that path writes ("this path writes `infra`").
- **Forbidden in a consumer**: presenting both values together as the
  permitted set; restating the values' meanings (the external-cause versus
  implementation-failure gloss); restating the missing-value read rule.
- **Required in a consumer**: a citation of
  `references/workflow-schema.md` at the point the field is first used in
  that document.

Each consuming task's test module asserts the citation's presence and the
absence of a definition-shaped restatement, with a negative proof against
a synthetic copy that does restate it.

*Affected tasks*: task0001 (must be the only definition), task0002,
task0003, task0004.

### D8 — The terminal-line contract is unchanged (FR10, C5)

No new stop reason code is added; the closed set stays at eleven. The
`step_needs_intervention` meaning row and the `stop-condition-3` coverage
row are re-worded to reflect the `failed_kind: decision` restriction for
the `implement` step, and the precedence rule's three phase-specific stop
points are untouched. The infra auto-resume emits no terminal line (it is
not a stop) and is not an `--once` phase boundary of its own — the
boundary stays wherever the implement phase itself puts it.

*Affected tasks*: task0004 owns the document; task0003 must not introduce
a code or a boundary.

### D9 — Version bump has exactly one owner

`em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`
appear in task0005's `files` and in no other task's. Tasks run fully in
parallel, so two tasks bumping the same version would conflict on a value
neither can reconcile mechanically.

*Affected tasks*: task0005 owns; every other task must not touch either file.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| The infra auto-resume loops forever because the cap is read wrong or never incremented | Low | High — reproduces the unattended-run failure this feature exists to fix, in a worse form | The cap defaults (C3) fall back to a finite value on any absent key; the increment is in the same write set as the reset (D4 step 7), so a resume that happens is a resume that was counted |
| A consumer document restates the vocabulary and drifts from the SSOT | Medium | Medium | D7's explicit permitted/forbidden split, asserted per consuming task with a negative proof |
| task0002 and task0004 state the second-failure classification differently | Medium | Medium | D2 pins the value and the precedence; task0004's row is a summary that cites the implement phase for detail rather than restating the rule |
| An edit disturbs an adjacent carve-out in the same paragraph (the `needs_update` auto-re-entry carve-out, the batch verify-cap exception) | Medium | High — silently changes an unrelated stopping behaviour | The Conventions' editing discipline; task0003's Acceptance Criteria pin both carve-outs as unchanged |
| A parallel task bumps the version too, conflicting with task0005 | Low | Low | D9's single-owner rule, restated in every other task's Out of Scope |
| SPEC assumption A2 is wrong and a fourth write path sets `implement` to `failed` | Low | Medium | Recorded as an open question below; a fourth path would be a follow-up task, not a silent widening of this plan |

## Open Questions

- [ ] SPEC A2: `references/batch-terminal-line.md`'s precedence rule lists
      `docs-commit-conflict` among the stop points that leave a step
      `failed`, while its owning document (`references/phase-state.md`)
      states the `failed` it sets is the phase-state file's own status.
      This plan assumes the three paths in D2 are the complete set of
      writers of the `implement` step's `failed`. If that is wrong, a
      fourth path needs a classification (recommended `infra`) as a
      follow-up task.
- [ ] Whether `batch.infra_resume.cap` should ever be authored by a user
      in workflow.yaml, or is effectively a constant recorded for
      readability. This plan treats it as a readable key with a defined
      default (C3) and defines no authoring path for it.
