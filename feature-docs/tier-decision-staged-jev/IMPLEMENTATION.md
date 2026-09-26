# Implementation Plan: tier-decision-staged-jev

## Overview

The em-workflow tier decision becomes three calls: Jev on the task description
alone, a read-only Codex fact survey, and a final Jev call that sees the
description plus both JSON results. The tier is decided from the final call's
bucket 0-3 probabilities alone, the two-reading disagreement fallback is
removed, the Codex survey reports seven more facts, and the persisted decision
record moves to schema_version 2.

## Technology Stack

- **Language**: Python 3 for the evaluator (`em-workflow/scripts/decide-tier.py`);
  Markdown and YAML for the procedure, schema documents and rule table.
- **Tests**: standard-library `unittest` only, under `tests/`, run by
  `python3 -m unittest discover -s tests` (NFR3).
- **New dependencies**: none. YAML reading in the evaluator and in tests uses
  the mechanism the repository already uses today; no package is added.
  License record: no new dependency, so there is nothing to check against
  `project.license: none`.

## Layer Structure

| Layer | Artifact | Responsibility | May depend on |
|-------|----------|----------------|---------------|
| Rule table (SSOT) | `em-workflow/references/tier-rules.yaml` | Threshold rows, probability-sum tolerance, bucket descriptions (`question_set`), Codex fact schema (`codex_output_schema`), `fallback_matrix`, `jev_exit_codes` | nothing |
| Evaluator | `em-workflow/scripts/decide-tier.py` | Deterministic tier decision from one final score plus availability flags | rule table only |
| Procedure | `em-workflow/skills/develop/SKILL.md`, Step A tier-decision section | Runs the three calls, derives the availability flags, invokes the evaluator, writes the record | evaluator contract (SC-1), rule table by citation, record schema (SC-4) |
| Record schema | `em-workflow/references/phase-state.md`, tier-decision persistence section | Defines `feature-docs/{feature}/phase-state/tier.yaml` schema_version 2 | score object (SC-2) |
| Projections | `em-workflow/references/phases/create-spec-phase.md` mapping table; `em-workflow/references/workflow-schema.md` tier section; SKILL.md retrospect `signals.tier_decision` block | Transcribe the record into workflow.yaml `tier` / `tier_decision` and into the retrospect tier signal | record schema |

Dependency direction is top to bottom only. Documents cite the rule table for
every numeric bound and never restate it (NFR2).

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| SC-1 Evaluator input/output | Decide the tier | Detailed below | task0001 (implements), task0003 (invokes) |
| SC-2 Score object | One Jev call's result | Detailed below | task0001, task0003, task0004 |
| SC-3 `decided_by` vocabulary | Say how the tier was decided | Detailed below | task0001, task0003, task0004 |
| SC-4 tier.yaml schema_version 2 | Persisted decision record | Detailed below | task0003 (writes), task0004 (defines and projects) |
| SC-5 tier-rules.yaml section ownership | Non-overlapping edits to one file | Detailed below | task0001, task0002 (task0003 cites sections by name only) |
| SC-6 SKILL.md section ownership | Non-overlapping edits to one file | Detailed below | task0003, task0004 |
| SC-7 Plugin version target | NFR5 | Detailed below | task0005 (sole owner) |

### SC-1 Evaluator input/output (`em-workflow/scripts/decide-tier.py`)

- Invocation channel and rule-table location stay as they are today; only
  the input payload shape and the decision logic change.
- Input: one JSON object whose decision-relevant members are exactly:
  - `final_score`: the score object (SC-2) of the final Jev call. Required
    when both flags are true; may be absent or null otherwise, and is then
    ignored.
  - `codex_available`: boolean; false when the Codex pre-survey was not run
    or was unusable.
  - `jev_available`: boolean; false when any Jev call that was made was
    unusable (the first call or the final call).
- Precondition: none. Every input, including a missing, malformed or
  legacy-shaped one, is accepted and answered.
- Postconditions:
  - The process always exits 0 and writes exactly one strict-JSON object:
    no NaN or Infinity token anywhere, including in echoed input values.
  - The output keeps today's shape (the tier, `decided_by`, and the reason
    text); only the set of `decided_by` values changes (SC-3).
  - An input carrying the legacy `readings` member (the two-reading payload)
    is rejected as invalid input: tier full, whatever else it carries.
  - The first (description-only) reading, `expectation_clear` and
    `confidence` never influence the decision.
  - Decision order: (0) input shape: not an object, legacy `readings`
    present, or a flag missing or not a boolean gives full as invalid input;
    (1) `jev_available` false gives full via the `jev_unusable` fallback row;
    (2) `codex_available` false gives full via the `jev_only_usable` fallback
    row; (3) validation of `final_score`: buckets `"0"` to `"3"` all present,
    no other bucket key, each value a finite real number in [0, 1], and the
    absolute difference between the four-bucket sum and 1 at most the rule
    table's tolerance; failure gives full with the offending bucket or the
    sum in the reason; (4) threshold rows evaluated top-down, first match
    wins.
  - Every threshold lower bound and the tolerance come from the rule table;
    a missing or malformed one gives full with a reason naming it. The
    evaluator holds no numeric default for any of them (NFR1).

### SC-2 Score object

- The JSON object a Jev call returns with `--json-output`, kept verbatim.
- Bucket probabilities are its `probabilities` member: a mapping from the
  bucket keys `"0"`, `"1"`, `"2"`, `"3"` to numbers.
- `expectation_clear` and `confidence` may be present; they are recorded and
  never used as a threshold member.
- A Jev call is unusable when it exits non-zero (classified by
  `jev_exit_codes`) or when its zero-exit output is not a JSON object.

### SC-3 `decided_by` vocabulary

- Decided by a threshold row: `threshold_rows:minimal`,
  `threshold_rows:reduced`, `threshold_rows:full`.
- Fallbacks: `fallback_matrix:jev_unusable`,
  `fallback_matrix:jev_only_usable`, and the evaluator's current
  malformed-input value (kept unchanged) for invalid input, legacy input,
  rule-table defects and failed probability validation.
- `fallback_matrix:readings_disagree` no longer exists.
- Consumers rely on one distinction only: a value starting with
  `threshold_rows:` means the final reading decided the tier; any other
  value is a fallback. No consumer depends on the exact text of the
  malformed-input value.

### SC-4 tier.yaml schema_version 2 (`feature-docs/{feature}/phase-state/tier.yaml`)

| Member | Presence | Content |
|--------|----------|---------|
| `schema_version` | always | `2` |
| `feature` | always | feature slug |
| `tier` | always | `minimal` / `reduced` / `full` |
| `bases` | always (may be empty) | Ordered list with one entry per Jev call that was made and usable: the `description_only` entry first, then the `description_plus_code` entry. Entry members: `basis`, `score` (SC-2, verbatim), `observed_at` |
| `pre_survey_estimate` | only when the Codex pre-survey was usable | the Codex JSON, verbatim |
| `decided_at` | always | decision timestamp, same format as today (explicit UTC offset) |
| `fallback_reason` | only when `decided_by` does not start with `threshold_rows:` | the evaluator's `decided_by` value together with its reason text |

- A final Jev call that exited zero but whose probabilities fail validation
  keeps its `bases` entry; `fallback_reason` carries the rejection reason.
- An existing schema_version 1 record is reused as-is on resume: it is
  neither rewritten nor re-decided (A12).

### SC-5 tier-rules.yaml section ownership

| Section | Owner | Change |
|---------|-------|--------|
| Threshold rows | task0001 | Redefined over buckets 0-3 |
| `probability_sum_tolerance` (new member, initial value 0.02) | task0001 | Added |
| `fallback_matrix` | task0001 | Disagreement row removed; `jev_only_usable` action becomes full |
| Any member that exists only for the two-reading comparison | task0001 | Removed |
| `jev_exit_codes` | task0001 (read-only) | Unchanged |
| Decision-basis values `description_only` / `description_plus_code` | task0001 (read-only) | Unchanged (A11) |
| `question_set` | task0002 | Bucket 0-3 descriptions and the section comment |
| `codex_output_schema` | task0002 | Seven fact fields added; existing fields kept |

A task never edits a section it does not own. Sections not listed stay
untouched.

### SC-6 SKILL.md section ownership (`em-workflow/skills/develop/SKILL.md`)

| Section | Owner |
|---------|-------|
| Step A tier-decision section, including step 6, the no-work-required stop and the resume reuse of an existing tier.yaml | task0003 |
| Retrospect `signals.tier_decision` block | task0004 |

Every other part of SKILL.md stays untouched.

### SC-7 Plugin version target

- The em-workflow version becomes `0.2.10` in
  `em-workflow/.claude-plugin/plugin.json` and in the em-workflow entry of
  `.claude-plugin/marketplace.json`. task0005 owns both files.
- If a commit guard forces another task to change the version in its own
  commit, that task sets exactly `0.2.10` in both files (identical edits
  merge cleanly) and reports it as a plan deviation.

## Conventions

- Every threshold, lower bound and tolerance is cited from `tier-rules.yaml`.
  The SKILL.md tier-decision section and the workflow-schema.md tier section
  contain no decimal threshold literal, no `P(0)` and no `expectation_clear`.
  No rule anywhere sets a threshold on confidence alone (NFR2).
- The tier-decision path introduces no gate_id and no user question, in
  interactive and batch mode alike (NFR4).
- Each document is edited in its existing language and style, and cites the
  SSOT document that owns a rule instead of restating it.
- Tests use `unittest` only, under `tests/`. Every raw-text matcher is paired
  with (a) a negative proof: the same matcher run on a forged sample that
  breaks the rule must fail, and (b) a non-vacuity guard: the section it
  inspects was located and is non-empty (NFR3).
- Evaluator failure policy: fail safe to full with a reason; never raise,
  never exit non-zero (NFR1).
- No task edits `em-workflow/references/review-phase.md` or
  `em-workflow/references/review-rules.yaml` (NFR6).

## Cross-task Design Decisions

### D1: The final reading alone decides the tier

The threshold rows see only the final call's bucket probabilities. The first
(description-only) reading is recorded, and it is part of the final call's
input, but it is never evaluated against a row. Affected: task0001, task0003,
task0004.

### D2: The evaluator is the single decision point, fallbacks included

The procedure always invokes the evaluator, also when a call was skipped or
unusable, passing the availability flags; the evaluator's fallback rows
produce full. SKILL.md step 6, `fallback_matrix` and the evaluator therefore
describe one behavior. Affected: task0001, task0003.

### D3: Call-skipping rules

- First Jev call unusable: the Codex pre-survey still runs (so the
  no-work-required stop stays reachable), the final Jev call is skipped, and
  `jev_available` is false.
- Codex pre-survey unusable (non-zero exit, output not parseable as JSON, or
  a required field missing): the final Jev call is skipped and
  `codex_available` is false.
- Codex pre-survey usable and reporting no remaining work: the existing
  no-work-required stop ends the run before the final Jev call and before
  any workflow step.

Affected: task0003 (procedure), task0001 (flag semantics), task0004 (absent
record entries and `fallback_reason`).

### D4: Legacy input is invalid, not translated

The evaluator does not convert a two-reading `readings` payload; it rejects
it (tier full). No compatibility shim is added. Affected: task0001, task0003.

### D5: Where the absence of `readings_disagree` is checked

Each task removes the string from the files or sections it owns and asserts
its absence only there, because sibling-owned sections still carry it inside
an isolated task worktree. The whole-tree check over `em-workflow/` runs at
the verify phase (VERIFICATION.md TS-6). Affected: task0001, task0003,
task0004.

### D6: Pre-existing tests

A pre-existing test that asserts behavior this feature replaces (the
two-reading input, the bucket-0 floor on the reduced row, the disagreement
fallback, the schema_version 1 record shape) is updated by the task that owns
the replaced file or section, inside that task. If that test file is not in
the task's declared files, the implementer still updates it and reports the
deviation. A pre-existing test that fails in an isolated worktree only
because a sibling-owned section is still in its old state is not fixed by
editing the sibling-owned section; it is reported as a deviation and settles
at integration. Affected: all tasks.

### D7: Resume compatibility

A schema_version 1 tier.yaml found on resume is reused without any call and
without rewriting it. The procedure (task0003) states the reuse; the record
schema (task0004) states that version 1 records remain valid input for
resume and transcription.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Pre-existing tests not named in SPEC.md assert the two-reading input, the bucket-0 floor, the disagreement fallback or the v1 record shape | High | Medium | D6; every task runs the full suite before completion |
| Merge conflicts in tier-rules.yaml or SKILL.md between parallel tasks | Medium | Low | SC-5 / SC-6 section ownership; parent-side adoption at merge |
| A commit guard requires a version change in every commit that touches `em-workflow/` | Medium | Medium | SC-7 identical-value fallback |
| A two-bucket sum written in decimal as exactly the lower bound evaluates below it in binary floating point | Medium | Medium | task0001 boundary cases (TS-4); no numeric epsilon constant may be added (NFR1) |
| The Jev result names its bucket map differently from `probabilities` | Low | High | SC-2 pins the member; the manual run in VERIFICATION.md confirms it |
| The jev / typesafe-ai skill documents are absent on a test machine | Medium | Low | The copy check reports a visible skip, never a silent pass |
| Files under `em-workflow/` other than the four named in FR5 still carry `readings_disagree` | Low | Low | Whole-tree scan at verify (TS-6); a hit becomes a rework task |

## Open Questions

- [ ] (non-blocking) Whether a permanent whole-tree regression test for the
      absence of `readings_disagree` should be added after integration; no
      single parallel task can own it (D5), so this plan verifies it at the
      verify phase only.
