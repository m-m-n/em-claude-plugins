# Implementation Plan: self-write-exclusivity-window

## Overview

Add a return-time recheck to Rule R1's "Order" (orchestrator re-reads every
self-write-set path after the comparison and before the recording
phase-state write), extend the exclusivity assumption's interval to that
recording write, and align the citing documents and document tests. Only
Markdown protocol text and `tests/` change.

## Technology Stack

- **Documents**: Markdown protocol documents under `em-workflow/` (English;
  `em-workflow/skills/develop/SKILL.md` is Japanese)
- **Tests**: Python 3 standard library `unittest` only, run by
  `python3 -m unittest discover -s tests`
- **New dependencies**: none (no license to record)

## Layer Structure

| Layer | Documents | Responsibility | May depend on |
|-------|-----------|----------------|---------------|
| Rule owner (SSOT) | `em-workflow/references/contracts/worker-envelope.md` Rule R1 "Order" / "Known limit" | States the return-time recheck once | — |
| Assumption statements | `worker-envelope.md` "Exclusivity assumption during dispatch"; `em-workflow/references/phases/create-spec-phase.md` "Exclusivity assumption (normative)" → "Scope of applicability" | State the interval the exclusivity assumption covers | the recording-write term below |
| Citing documents | `em-workflow/references/artifact-digest.md` "Layer 5 recording"; `em-workflow/skills/develop/SKILL.md` design step 5; `em-workflow/references/phases/create-plan-phase.md` section 8; `em-workflow/references/rework-task-synthesis.md` section 10 | Point at the recheck by citation, never restate it | Rule owner (by citation only) |
| Document tests | new `tests/test_*_docs.py` files, one per task | Pin each task's own document text with forged-text controls | the documents they read |

Dependency direction is one-way: citing documents and assumption statements
cite Rule R1; Rule R1 cites `create-spec-phase.md` only for the scope
verification and its stale handling (as it already does).

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| Return-time recheck (defined in worker-envelope.md Rule R1, inside the existing `**Order.**` block, after its step 4) | Detect an external change to a self-write-set path made after the scope verification, before anything is recorded | Name: the literal term `return-time recheck` (used verbatim by every citing document, including the Japanese develop SKILL.md, where it may be accompanied by 再確認). Actor: the orchestrator. Pre: step 4's comparison did not make the result stale; when `written_artifacts` is non-empty, Layer 5's `Calculation` has run. Action: for each self-write-set path, the current git blob id, mode and kind (file / symlink / absent) are re-read and compared with the values the same run's scope verification observed for that path. Post: all equal → the recording write may proceed; any mismatch, or a recheck that cannot run (read failure included) → the result is stale and handled by the scope verification's stale handling (`references/phases/create-spec-phase.md`), and no recording write happens; an empty self-write set passes with nothing to do. | task0001 (defines), task0003, task0004 (cite) |
| Recording write | The single point every task places the recheck before and the interval ends at | The phase-state write that records the run's layer-5 `artifacts` entries together with its `self_write_set`; for a run whose `written_artifacts` is empty, the write that records its returned `status` and `self_write_set`. Documents name it by those fields (`artifacts`, `self_write_set`, and `status` for the empty case), not by a new label. | task0001, task0002, task0003, task0004 |
| Exclusivity interval end point | The interval both assumption statements state | Start unchanged (the dispatch's scope snapshot capture). End: completion of the recording write; when the result is judged stale, that stale judgment. Both `worker-envelope.md` and `create-spec-phase.md` state this same end point with both variants. | task0002 (defines), task0001 (Known limit refers to it) |
| R1 citation form | How citing documents reference the rule | Path `references/contracts/worker-envelope.md` + `Rule R1` + `"Recomputation and comparison timing"` (the form the existing sites already use), plus the term `return-time recheck` | task0003, task0004 |

## Conventions

- **Cite, never restate**: citing documents (task0003, task0004) name the
  recheck and cite R1; they never enumerate the compared values (blob id /
  mode / kind), never name `git hash-object`, and never word out the
  membership matrix or the substitution.
- **Insert, do not rewrite**: every task adds text into existing sections and
  keeps the existing sentences and anchor phrases those sections already
  carry. When an inserted phrase breaks an existing test assertion, the
  inserted text is changed — existing tests are not edited.
- **Digest-sentence convention (NFR3)**: every added sentence that mentions a
  digest, a hash or sha256 (a sentence naming `git hash-object` counts) names
  the orchestrator as its actor or is negated. No added text gives a worker a
  digest instruction. `worker-envelope.md` never gains an `expect_digest`
  token (NFR5).
- **Value kinds stay apart (FR2)**: the recheck compares git blob id / mode /
  kind with the scope verification's values of the same kind; no document
  mixes these with a raw-byte sha256 (artifact digest, `digest_inputs`).
- **Tests**: each task adds exactly one new test file of its own under
  `tests/`, standard library only, self-contained (no import of a sibling
  test module), named per `test/README.md` (`test_<target>.py`,
  `Test<Behavior>`, `test_<condition>_<expected_result>`). Assertions run on
  heading-sliced, whitespace-normalized text; none depends on line-break
  position or whole-document equality. Every probe has a forged-text control
  built from the pre-change wording, on which the probe fires. A test of a
  citing document never asserts that Rule R1 already contains the recheck
  (that text lands in another worktree).
- **Plugin version**: no task edits `em-workflow/.claude-plugin/plugin.json`
  or `.claude-plugin/marketplace.json` (NFR7).

## Cross-task Design Decisions

### D1: The recheck lives inside the existing `**Order.**` block

The recheck is added as the step that follows step 4 inside the existing
Order block, not as a new labelled R1 block. R1's label set therefore stays
as it is, and `R1_LABELS` in `tests/test_self_write_digest_docs.py` needs no
change (NFR4). Affected: task0001; task0003 and task0004 cite "Rule R1" and
the term, not a new label.

### D2: Calculation before the recheck, recording write after it

R1 places Layer 5's `Calculation` between the comparison and the recheck,
and the recording write after the recheck. No citing document may state or
imply that `Calculation` runs after the recheck; citing documents place the
recheck after the comparison (or the `validate-worker-output.py` validation)
and before the recording write. Affected: task0001, task0003, task0004.

### D3: Observed values are held within the run only

The scope verification's observed values that the recheck compares against
are held within the run and are not persisted; `references/phase-state.md`
and its schema do not change (SPEC A3). Affected: task0001 (no persistence
wording), all tasks (phase-state.md untouched).

### D4: The assumption stays unenforced

The extended interval is still an assumption, not a lock or hook (SPEC A5).
The quoted assumption text, the five-worker restriction, the "not a standing
constraint" clause and the review wave-parallel exception remain in both
documents. The headings `## Exclusivity assumption during dispatch` and
`### Exclusivity assumption (normative)` stay as they are (existing tests
locate them). Affected: task0002, task0001 (Known limit).

### D5: Out-of-scope documents stay untouched

`em-workflow/scripts/self-write-digest.py`, `em-workflow/references/phase-state.md`,
`em-workflow/references/contracts/analyst-contract.md` (its exclusivity
section), `em-workflow/references/contracts/spec-writer-contract.md`, and the
final paragraph of `artifact-digest.md` "Pre-dispatch verification" are not
modified (SPEC A1, A2, NFR6).

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| An inserted sentence at a dispatch site shifts the first position of a token an existing order assertion uses (`self_write_set`, `Layer 5 recording`, `成果物`) | Medium | Medium | task0004's plan lists the constraining assertions; existing tests run unchanged (TS-4, TS-8) |
| An R1 sentence naming `git hash-object` trips the digest-sentence convention | Medium | Low | Convention above; `test_ac5_every_digest_sentence_of_the_self_write_rule_names_the_orchestrator_or_is_negated` runs unchanged |
| task0001 and task0002 both edit `worker-envelope.md` | Low | Low | Different sections (R1 vs Exclusivity); merges are resolved by the parent-side adoption protocol |
| The designer / planner / rework-planner contracts' "Scope & concurrency assumption" sections still state the old interval end | High | Medium | Outside the SPEC's file set; raised as an open question below |
| In rework, section 10's step 3 both validates and applies the patch, so the recheck may follow the patch application | Medium | Medium | Outside the SPEC (FR7 keeps each site's existing order); raised as an open question below |

## Open Questions

- [ ] `em-workflow/references/contracts/designer-contract.md`,
      `planner-contract.md` and `rework-planner-contract.md` each state, in
      their "Scope & concurrency assumption" section, an interval "from
      scope-snapshot capture through scope verification". After this feature
      they disagree with `worker-envelope.md`. The SPEC does not list them as
      targets.
- [ ] `rework-task-synthesis.md` section 10 step 3 validates and applies
      rework-planner's patch in one step. If the patch is applied before the
      return-time recheck, a recheck mismatch is judged stale after
      `workflow.yaml` was already patched. The SPEC fixes only the textual
      order (step 3 validates → recheck → recording).
