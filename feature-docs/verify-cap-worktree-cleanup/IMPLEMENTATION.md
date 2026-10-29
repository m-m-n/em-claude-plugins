# Implementation Plan: verify-cap-worktree-cleanup

## Overview

Align `em-workflow/hooks/failed-run-cleanup-guard.py` with develop's Step C: for a
feature whose workflow.yaml is in the excluded state (verify failed at the batch
rework cap after a completed retrospect), the hook emits no decision for S1 and
S3. S2, and every failed state that is not the excluded state, keep today's
behavior. The hook's module docstring and the README hook-list row describe the
same judgment model.

## Technology Stack

- **Language**: Python 3 (standard library) — the existing hook script.
- **Key libraries**: PyYAML — already used by the hook; when it is unavailable
  the hook emits no decision (unchanged, NFR4).
- **Tests**: standard-library unittest with tempfile fixtures (NFR6).
- **New dependencies**: none. `project.license` is `none`; no license to record.

## Layer Structure

One hook script with a single judgment pipeline. Steps 1, 2 and 5 exist today and
keep their behavior; step 3 gains the excluded-state classification and step 4
gains the per-shape outcome.

1. Payload parsing — identify command shape (S1 / S2 / S3) and resolve the target
   feature(s) (existing).
2. workflow.yaml loading — at most one read per target (existing, NFR2).
3. Classification of one feature — healthy / failed and excluded / failed and not
   excluded.
4. Per-shape outcome — see "Judgment model" below.
5. Output — no stdout for "no decision"; deny or ask otherwise, with the
   CLAUDE_BATCH ask-to-deny demotion (existing).

Dependency direction: each step uses only the output of earlier steps. The
classification step consults only the structured fields listed under the
judgment model; it never reads raw text.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| Judgment model of failed-run-cleanup-guard | The one description of what the hook decides. The hook implements it. The module docstring and the README hook-list row describe it. | Pre: none. Post: the hook's behavior, its module docstring, and the README row all state the same excluded-state conditions and the same per-shape outcomes (Cross-task Design Decisions, D1). Neither text adds a condition or outcome that the other lacks. The README row may summarize; the docstring is the full statement. | task0001, task0002 |

## Conventions

- **Terms**: "excluded state", "lineage cap", "hard cap", "S1" (`git worktree
  remove`), "S2" (`git branch -d` / `--delete`), "S3" (`gh pr create`). Use these
  terms with the same meaning in the docstring, the README row and test names.
- **No allow**: exclusion means no decision: empty stdout and exit code 0. The
  hook never emits an allow decision (NFR1).
- **Unchanged wording**: deny and ask reasons for failed states that are not the
  excluded state stay byte-identical to today's wording (FR6).
- **Language**: each file keeps its existing language (docstring, README).
- **Version**: the plugin version is not touched by any task (NFR7).

## Cross-task Design Decisions

### D1: Judgment model (canonical statement)

**Excluded state.** A feature's workflow.yaml is in the excluded state when all
of the following hold:

- (a) The only top-level step with status `failed` is the step with id `verify`.
- (b) A step with id `retrospect` exists and its status is `completed`.
- (c) Every other top-level step has status `completed` or `skipped`.
- (d) `batch.verify_rework` shows that a cap was reached. The lineage cap is
  reached when any `failed_id_counts` value is 2 or more. The hard cap is reached
  when `rounds` is 3 or more. These thresholds are the values of
  `em-workflow/skills/develop/SKILL.md`'s lineage-cap definition (NFR5).

**Cap-record reading.** These rules apply to (d):

- If `batch` or `batch.verify_rework` is absent or is not a mapping, the
  feature is not excluded.
- An absent `rounds` member reads as 0. An absent `failed_id_counts` member
  reads as an empty mapping.
- If a member is present with an invalid type, the whole cap record is invalid
  and the feature is not excluded. The invalid types are: `rounds` is not an
  integer (a boolean counts as not an integer); `failed_id_counts` is not a
  mapping; a `failed_id_counts` value is not an integer (a boolean counts as not
  an integer).
- The obsolete `verify_rework_count` key is ignored. A `batch` block that merely
  exists is not evidence of a batch run.

**Per-shape outcome for a feature with a failed step:**

| Shape | Excluded state | Failed, not excluded |
|-------|----------------|----------------------|
| S1 | no decision | deny (unchanged) |
| S2 | deny (unchanged) | deny (unchanged) |
| S3 | no decision | deny (unchanged) |

**Unresolvable targets** (the any-failed-worktree aggregate):

- S1 counts an excluded-state worktree as healthy.
- S2 counts an excluded-state worktree as failed, as it does today.
- The aggregate is computed separately for each shape. A result computed for one
  shape is never reused for another shape.
- When no worktree can be enumerated, the hook still asks, as it does today. The
  CLAUDE_BATCH ask-to-deny demotion is unchanged.

**Unchanged:**

- Healthy features.
- Fail-open on a missing or unparseable workflow.yaml, on missing PyYAML, and on
  an internal error (NFR4).
- destructive-guard's deferral to this hook through its target-shape matching.

Affected tasks: task0001 implements this model and states it in the docstring.
task0002 summarizes it in the README row.

### D2: Align on the hook side

`em-workflow/skills/develop/SKILL.md` is not changed. This covers Step C 2.'s
worktree removal, the detail wording for a cap-reached run, and the lineage-cap
definition. The hook is changed to agree with the skill (FR1). Affected tasks:
task0001, task0002.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| The new classification raises on an unexpected value shape, and the hook's fail-open path silences a deny that a failed run, not in the excluded state, gets today | Medium | High | The classification never raises: on any shape it cannot classify, it returns "not excluded" (THREAT-MODEL.md TM-3) |
| Memoization shares an aggregate between S1 and S2, so S2 gets no decision for an excluded feature | Low | High | The aggregate is kept separately for each shape (D1; THREAT-MODEL.md TM-4) |
| An existing test fixture already satisfies the excluded state while expecting a deny | Low | Medium | Only `tests/test_failed_run_cleanup_guard.py` may change. The other listed suites must pass unmodified |
| The docstring and the README row diverge | Low | Low | Both describe D1 |

## Open Questions

- None.
