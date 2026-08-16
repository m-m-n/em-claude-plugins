# Implementation Plan: batch-stop-contract

## Overview

A new SSOT document owns a machine-readable terminal line that an em-workflow
batch run emits at the end of the run, and the existing batch-mode and
develop documents gain pointers to it. Three parallel tasks split the work by
file ownership: the contract document (+ its pointer in `batch-mode.md`), the
develop-skill wiring, and the plugin version bump — each with its own
documentation contract test module.

## Technology Stack

- **Language / Framework**: Markdown + YAML SSOT documents under
  `em-workflow/`; Python 3 standard-library `unittest` documentation contract
  tests under `tests/`; two JSON manifests.
- **Key libraries**: none. No new runtime or test dependency is introduced
  (NFR1, NFR3), so there is no new dependency license to record.
  `project.license` is `none`, which imposes no compatibility constraint on
  this feature.

## Layer Structure

| Layer | Files | Responsibility |
|---|---|---|
| Contract (SSOT) | `em-workflow/references/batch-terminal-line.md` | Sole owner of the terminal-line prefix, field grammar, reason-code set and stop-point mapping |
| Pointer | `em-workflow/references/batch-mode.md`, `em-workflow/skills/develop/SKILL.md` | Name the contract document and state WHEN emission happens; never restate WHAT the line looks like |
| Verification | `tests/test_batch_stop_contract.py`, `tests/test_batch_stop_contract_skill_wiring.py`, `tests/test_batch_stop_contract_version_bump.py` | Read the layers above as data and pin their invariants |
| Registry | `em-workflow/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` | Plugin version |

Allowed dependency direction: pointer → contract, verification → contract and
pointer, registry → nothing. The contract document never depends on a pointer
document's wording, so the pointer documents can be reworded without
invalidating the contract.

## Shared Components

Every row below is a cross-task agreement. Tasks run fully in parallel, so
these values are fixed here and are not renegotiated inside a task.

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|---|---|---|---|
| Contract document path | Holds the whole output contract | Exactly `em-workflow/references/batch-terminal-line.md`. Postcondition: the file exists after task0001 and is the only plugin file that carries the prefix literal. The name must NOT end in `-phase.md` (see D7) | task0001, task0002, task0003 |
| Terminal-line prefix | Uniquely marks the terminal line in unattended-run logs | The exact literal `EM_WORKFLOW_TERMINAL:` followed by one ASCII space. Uppercase, underscore-separated, no dot — so it can never be read as a gate identifier. Precondition for any consumer: the line is the last line of the final assistant message of a batch turn | task0001, task0002, task0003 |
| Terminal-line field grammar | Machine-parseable payload | After the prefix, exactly four `key=value` fields in this fixed order: `state`, `step`, `reason`, `detail`. Single space between fields, no space around `=`. `detail` is last and its value runs to end of line, so it may contain spaces. Postcondition: one physical line, never wrapped | task0001, task0002 |
| `state` value domain | Distinguishes completion from a stop | Closed set of two: `completed`, `stopped`. Same prefix and same four fields in both cases (FR1), so absence of the line is the only abnormal-outcome signal | task0001, task0002 |
| `step` value domain | Locates the stop | A `workflow.yaml` step id (`create-spec`, `design`, `create-plan`, `implement`, `review`, `verify`, `retrospect`) or the single sentinel `no-step`. `no-step` applies whenever no `workflow.yaml` step is in effect at the stop point (Step 0 git-setup abort, Step A feature-resolution failure, Step C completion processing). On `state=completed` the value is `retrospect` — the final workflow step, which a completed run has always reached | task0001, task0002 |
| Stop reason-code set | The closed enum of FR2/NFR7 | Exactly ELEVEN stop codes: `step_stuck`, `step_needs_intervention`, `workflow_yaml_unparseable`, `git_setup_aborted`, `gate_fail_closed`, `gate_option_unavailable`, `implement_task_failed`, `verify_rework_cap_reached`, `completion_aborted`, plus (rework round 1, D9) `feature_resolution_aborted` and `docs_commit_conflict_aborted`. Plus the reserved value `none`, used only when `state=completed`. All lowercase snake_case, no dots | task0001, task0002 (first nine); task0004, task0005 (the two additions) |
| Stop-point key set | The FR5 enumeration, in machine-comparable form | Exactly ELEVEN keys: `stop-condition-2`, `stop-condition-3`, `stop-condition-4`, `stop-condition-6`, `fail-closed-abort`, `policy-option-unavailable`, `implement-second-failure`, `verify-rework-cap`, `step-c-abort`, plus (rework round 1, D9) `step-a-abort` and `docs-commit-conflict`. Lowercase, hyphen-separated, no dots | task0001, task0002 (first nine); task0004 (the two additions) |
| Contract-document heading set | Section anchors the contract test slices on | Exactly these seven level-2 headings, in this order: `## Purpose`, `## Line format`, `## Field values`, `## Stop reason codes`, `## Stop point coverage`, `## No line on a wait turn`, `## Responsibility boundary`. Postcondition: a test may locate a section by its heading string alone | task0001 |
| Reason-code table shape | Lets a test extract the closed set mechanically | Under `## Stop reason codes`: a Markdown table whose first column is a single backticked reason code and which also states, per row, the meaning and which `state` it applies to. Precondition for extraction: one code per row, no code repeated | task0001 |
| Coverage table shape | Lets a test check FR5 bidirectionally | Under `## Stop point coverage`: a Markdown table whose first column is a single backticked stop-point key, whose second column is a single backticked reason code, and whose third column names the owning source document. Postcondition: every stop-point key appears exactly once, and every stop reason code of the set above is used by at least one row | task0001, task0004 |
| Plugin version | Single version identity for the plugin | `0.1.40` — a patch bump from the current `0.1.39` — written identically as a string into `em-workflow/.claude-plugin/plugin.json` and the `em-workflow` entry of `.claude-plugin/marketplace.json`. Exactly one task performs it | task0003 |

## Conventions

### Naming

- New contract test modules are named `tests/test_batch_stop_contract*.py`,
  matching the `tests/test_*.py` discovery pattern.
- Reason codes are lowercase snake_case; stop-point keys are lowercase
  hyphen-separated. Neither may contain a dot, so neither can be mistaken for
  a `gate_id` by the plugin invariant checker.

### SSOT partition (FR3)

A pointer document names the contract document and states WHEN the line is
emitted. It never restates the prefix literal, the field list, a reason code,
or the sentinel value. Any statement that would duplicate contract content is
replaced by a reference to `references/batch-terminal-line.md`.

### Test authoring (NFR4)

Follow the convention of `tests/test_routeback_reset_scope_version_bump.py`:
assertions are durable invariants rather than fixed literals wherever a
literal would go stale; every matcher has a negative proof (a forged sample
the matcher must reject) plus a non-vacuity guard (the forged sample is itself
well-formed, so the proof exercises the comparison and not a parse failure).
Pure regression guards over retained pre-change wording are exempt from the
negative-proof requirement. Test code imports the Python standard library
only (NFR1).

### Error-handling policy

There is no runtime code in this feature. The terminal line IS the
error-reporting surface: a terminating stop reports through `reason` +
`detail`, and a run producing no line at all — outside a wait turn — is read
by the consumer as a crash or a truncated turn.

## Cross-task Design Decisions

### D1 — The contract lives in a new SSOT document, not inside `batch-mode.md`

FR3 permits either. A separate document is chosen because `batch-mode.md` is
pinned by an existing test module in ways the contract text would collide
with: that module asserts `batch-mode.md` does NOT contain the literal
`rework.spec-change` nor `failed_items`, and the FR5 enumeration must be free
to name the fail-closed abort path without tripping either. `batch-mode.md`
keeps a pointer only. Affected: task0001, task0002.

### D2 — Same four fields on completion and on stop

FR1 requires the same format for both terminal states. Rather than making
`reason`/`detail` conditional, all four fields are always present, with
`reason=none` reserved for `state=completed`. A consumer therefore parses one
grammar, and the "absent line = abnormal" rule (b2) has no second shape to
account for. Affected: task0001, task0002.

### D3 — One sentinel, defined by "no step in effect"

FR6 asks for a fixed sentinel for step-less stops and names Step 0 and Step A.
The sentinel `no-step` is defined by the more general property "no
`workflow.yaml` step is in effect at the stop point", which additionally
covers a Step C abort — where every step is completed and the stop happens
outside any of them. This avoids a second sentinel. Affected: task0001,
task0002.

### D4 — Stop-point keys are first-class identifiers

FR5's nine stop points are given stable keys rather than prose labels, so the
coverage check (TS-3) is a set comparison instead of a substring search over
sentences that can be reworded. Affected: task0001.

### D5 — Emission is batch-only

FR1 scopes the line to a batch-mode run. An interactive run emits nothing, so
existing interactive report wording is untouched and FR4's non-regression
surface stays confined to the batch branch of the Step C report. Affected:
task0001, task0002.

### D6 — Prefix uniqueness is expressed as a single-file property

NFR5 asks that the prefix not collide with ordinary prose or with example
lines inside contract documents. The operational form of that guarantee: the
prefix literal appears under `em-workflow/` in exactly one file
(`references/batch-terminal-line.md`), and inside that file only within
fenced example blocks. A log consumer reads run output rather than documents,
so no further disambiguation is required. Affected: task0001, task0002,
task0003.

### D7 — Existing-suite compatibility constraints (NFR2)

The whole suite must pass with no existing test module modified. The
following are therefore hard constraints on the edits, derived from
assertions the existing modules and `em-workflow/scripts/check-plugin-invariants.py`
already make (that checker is executed against the repository root by the
test suite itself):

1. The strings `decision table` (any case) and `決定表` must not appear in
   `batch-policies.yaml`, `batch-mode.md`, `question-resolution.md` or
   `skills/develop/SKILL.md`.
2. The strings `rework.spec-change` and `failed_items` must not appear in
   `batch-mode.md`.
3. The string `requirements-spec-creator` must not appear anywhere under
   `em-workflow/`.
4. The phrase `Read してインラインで従う` must not appear under `em-workflow/`.
5. No row may be added to or removed from `batch-mode.md`'s Non-packet gates
   table — its catch-all paragraph is pinned to the phrase `ten rows above`.
   The catch-all paragraph, the diff-size gate row and the per-command
   approval row keep their current wording.
6. In `skills/develop/SKILL.md`, no new backticked `namespace.name`-shaped
   token may be introduced within roughly 120 characters after a `gate_id` /
   `gate ID` mention unless that token is a key of
   `references/batch-policies.yaml`.
7. The new contract document's filename must not end in `-phase.md` and it
   must not be placed under `references/phases/`, both of which would put it
   into the invariant checker's gate-identifier scan scope.
8. Existing headings and anchor sentences in `skills/develop/SKILL.md` are
   not reworded; edits are additive.

Affected: task0001, task0002, task0003.

### D8 — Version-bump baseline

The version test asserts the `0.1` line with patch strictly greater than 39
(the current committed `0.1.39`), rather than equality with `0.1.40`, so it
stays green across later unrelated bumps while still going red on the
un-bumped tree. Affected: task0003.

### D9 — Rework round 1: the closed sets grow by two, and the split that keeps the two rework tasks independent

Review round 1 found that the closed sets fixed above are not total: Step A's
feature-resolution failure (already named in `## Field values` as a `no-step`
stop) and the phase abort taken when `commit-docs.sh` returns exit 4 a second
time are terminating stops with no reason code and no coverage row. Closing the
sets is a NEW cross-task agreement, because two rework tasks in separate
worktrees both depend on the same names:

| Stop | Stop-point key | Reason code | Owner document named in the coverage table | `step` value |
|---|---|---|---|---|
| Step A abort (fail-closed feature-identifier gate; batch run with no task description) | `step-a-abort` | `feature_resolution_aborted` | `skills/develop/SKILL.md` | the `no-step` sentinel |
| Phase abort on a second `commit-docs.sh` exit 4 | `docs-commit-conflict` | `docs_commit_conflict_aborted` | `references/phase-state.md` | the id of the step whose phase aborted |

Ownership split (file sets are disjoint, so both rework tasks are mergeable
from independent worktrees and each leaves the suite green on its own):

- **task0004** owns `references/batch-terminal-line.md` and
  `tests/test_batch_stop_contract.py`: the two new codes and rows, the
  precedence rule that makes an overlapping stop resolve to exactly one code
  (a phase-specific stop point wins over the generic `stop-condition-N` rows),
  the `detail` normalization rule, the generalized no-line rule, and the
  weakened Source-column claim plus its path-resolvability check.
- **task0005** owns `skills/develop/SKILL.md`, `references/batch-mode.md` and
  `tests/test_batch_stop_contract_skill_wiring.py`: the completed stop
  enumeration, the no-line rule generalized over every non-terminal turn end,
  and the instruction to Read the contract SSOT before emitting the line.

Two consequences that must hold in EITHER merge order: a pointer document still
restates no literal, so `batch-mode.md` and `SKILL.md` stay clean against both
the nine-code and the eleven-code absence lists; and the eleven-member tuple in
the skill-wiring module is used for absence checks only, so it is green
regardless of whether the contract document already carries the two new codes.

Affected: task0004, task0005.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| An edit to `batch-mode.md` or `SKILL.md` breaks a pinned string in an existing test module | Medium | High (NFR2 violated, suite red) | D7's explicit constraint list; edits are strictly additive; each task runs the whole suite before completing |
| The three tasks disagree on the prefix, field order or code set | Medium | High (integration mismatch found only at verify) | Shared Components fixes every literal; pointer documents are forbidden from restating them (SSOT partition), so only one file can define them |
| `check-plugin-invariants.py` fails on the new document via its gate-identifier scan | Low | High (suite red) | D7 items 6 and 7: no dotted identifiers near gate mentions, and the document is outside the scan scope by filename |
| The reason-code set is later found incomplete for a stop point not listed in FR5 | Low | Medium | The coverage table is the single place to extend; the contract test's bidirectional check makes an unmapped key fail loudly |
| Version bump landed twice (both manifests diverge, or two tasks bump) | Low | Medium | Exactly one task owns both manifests; the equality matcher compares the two as strings |

## Open Questions

- [ ] None. Every FR/NFR in workflow.yaml is `ok`; SPEC.md records no open
      question.
