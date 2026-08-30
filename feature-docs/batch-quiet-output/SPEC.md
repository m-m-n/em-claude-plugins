# Feature: batch-quiet-output

## Overview

`/em-workflow:develop --batch` is launched headlessly (`claude -p`,
`claude-batch`), so the only output surfaces its caller actually reads are the
last assistant message of each turn and the Step C final report. This feature
narrows the batch run's main-context output to exactly those surfaces:
mid-run narration and interim summaries are suppressed, a non-terminal turn is
reduced to a single fixed-format marker line, and the Step C final report,
stop/abort reports and the terminal line stay unchanged.

Requirements source: `feature-docs/batch-quiet-output/REQUIREMENTS.md`. That
document is authoritative for the requirement text; this specification renders
the same requirements for implementation.

## Objectives

- Narrow `/em-workflow:develop --batch`'s main-context output to the surfaces
  a headless caller (`claude -p` / `claude-batch`) actually reads.
- Keep normal completion, stop and wait mechanically distinguishable from the
  output alone, even after mid-run narration and interim summaries are
  suppressed.
- Keep auditability, after suppression, on committed artifacts and the Step C
  final report.

## User Stories

### US1: A headless caller reads a run's outcome from the output alone
As a headless caller (`claude -p` / `claude-batch`), I want each batch turn to
end with either a terminal line or a single non-terminal marker line, so that I
can classify the run's state without parsing narration.

**Acceptance Criteria:**
- [ ] A `--batch` run's non-terminal turn (stop condition 5's wait, implement's
      launch / wake) ends its final assistant message with exactly one
      fixed-format marker line and nothing else.
- [ ] That marker line's prefix does not equal `EM_WORKFLOW_TERMINAL:` and is
      not picked up as a terminal line by the terminal-line parser.
- [ ] A `--batch --once` turn that ends at a phase boundary outputs no phase
      narration and does include the terminal line
      (`state=phase_done reason=none`).

### US2: A human evaluator audits a finished run from the final report
As the human who evaluates the finished product, I want the Step C final report
to stay complete, so that I can audit the run even though nothing was narrated
mid-run.

**Acceptance Criteria:**
- [ ] A normally completed `--batch` turn's output contains every audit item
      required by batch-mode.md "Reporting" and, as its last line, the terminal
      line (`state=completed step=retrospect reason=none`).
- [ ] A `--batch` run stopped by stop condition 2/3/4/6, a gate abort, a Step C
      abort, a Step A resolution failure, a second `commit-docs.sh` exit 4, a
      second implement task failure, or the verify rework cap outputs the cause,
      the affected paths, the recovery hints, and the terminal line.
- [ ] The review phase's Phase R6 report body is not emitted into a `--batch`
      run's main context, while that round's `reviews/roundN.yaml` stays
      equivalent to the pre-change content.

### US3: An interactive user sees no change
As a user running develop without `--batch`, I want output, stop behaviour and
report wording to be untouched, so that this feature is invisible to me.

**Acceptance Criteria:**
- [ ] A launch without `--batch` produces output, reports and stop behaviour
      identical to the pre-change behaviour.
- [ ] Across every turn of a `--batch` run, the committed content of
      workflow.yaml, phase-state, `feature-docs/` entries, reviews and
      `retrospect.yaml` is equivalent to the pre-change content.
- [ ] The suppression discipline is defined only in
      `em-workflow/references/batch-mode.md`; every other document references
      it.
- [ ] `em-workflow/.claude-plugin/plugin.json` and
      `.claude-plugin/marketplace.json` carry the same updated version value.

## Technical Requirements

### Functional Requirements

- **FR1 - Activation condition:** Output suppression is active only when the
  current invocation's arguments contain `--batch`. The `batch` block in
  workflow.yaml never activates it. A launch without `--batch` (interactive
  mode) has its output unchanged by this feature.
- **FR2 - Non-terminal turns carry only a marker line:** When a batch turn ends
  without reaching a terminal state as defined by
  `references/batch-terminal-line.md`, that turn's final assistant message
  consists of a single fixed-format marker line and nothing else. The turns in
  scope include at least stop condition 5's wait turn and the implement phase's
  launch turn and wake turn.
- **FR3 - Marker format and distinguishability from the terminal line:** The
  marker line is one physical line made of a fixed prefix plus fixed fields, and
  uses a prefix different from `batch-terminal-line.md`'s terminal-line prefix
  (`EM_WORKFLOW_TERMINAL:`). It must satisfy both: the terminal-line parser does
  not read the marker as a terminal line, and the terminal-line contract's
  "absence of the line means an abnormal outcome" signal is not broken. The
  marker's values carry no confidential information beyond paths.
- **FR4 - Scope of the suppressed interim output:** During a batch run the
  following phase-progress output is not emitted into the main context: phase
  start / completion narration; forwarding of sub-agent reports (implementer /
  reviewer / each worker) into the main context; per-step interim summaries; the
  review phase's Phase R6 Japanese report body; the reconcile results the
  implement wake turn enumerates; the verify result-summary body; design-step
  progress; and the running presentation of Step A.5's command-approval results.
- **FR5 - The Step C final report stays complete:** Step C's (completion
  processing) batch final report is emitted in full as it is today. It includes
  the audit items `references/batch-mode.md` "Reporting" requires — every
  auto-approved command string, every recorded assumption, the auto-rework
  counts consumed by review / verify, deferred findings with their stable_ids,
  every unlisted-gate fallback resolution, and the kept integration branch name
  with its take-over guidance — plus the `/em-workflow:gen-license` guidance line
  when `project.license` is `none`. The terminal line is appended after it as one
  line.
- **FR6 - Stop and abort turns are exceptions to suppression:** A turn that ends
  in a stop or abort is outside the scope of suppression and emits the cause,
  the affected paths and the recovery hints as it does today. In scope: stop
  condition 2 (stuck), 3 (failed / needs_update), 4 (YAML parse error), 6
  (git-setup abort), an in-phase gate abort, an abort inside Step C, Step A's
  feature-resolution failure, a phase abort from a second `commit-docs.sh`
  exit 4, and the implement / verify phases' terminal stops. batch-mode.md's
  principle that batch removes phase confirmations but never hides failures is
  unchanged.
- **FR7 - The terminal-line contract is unchanged:** The terminal line's prefix,
  field grammar, `state` / `step` / `reason` / `detail` value domains, and its
  mapping to stop points remain solely owned by
  `references/batch-terminal-line.md` and are not changed by this feature. The
  conditions under which the terminal line is emitted are unchanged as well.
- **FR8 - Output of a `--once` phase-boundary turn:** A `--batch --once` turn
  that reaches a phase boundary (`state=phase_done`) emits the terminal line,
  and withholds all other phase narration and interim summaries per FR4. Because
  it is neither Step C completion processing nor a stop, it does not fall under
  FR5's or FR6's full-output exceptions.
- **FR9 - Writes to file artifacts are unchanged:** Output suppression targets
  main-context assistant text only. The content, frequency and timing of writes
  and commits to workflow.yaml, `phase-state/*.yaml`, every document under
  `feature-docs/{feature}/`, `reviews/roundN.yaml`, `retrospect.yaml`,
  `journal.jsonl` and `test-docs/` are not changed at all.
- **FR10 - Gate resolution and state transitions are unchanged:** This feature
  changes output only. Batch gate resolution
  (`references/question-resolution.md`, `references/batch-policies.yaml`, and
  batch-mode.md's Non-packet gates table), the auto-rework caps, stop-condition
  evaluation, and workflow.yaml's status-transition discipline are all
  unchanged.
- **FR11 - Audit items are sourced from artifacts:** The audit items FR5
  requires are assembled from committed artifacts and persisted state — not from
  earlier turns' main-context output: workflow.yaml, `phase-state/*.yaml`'s
  `answers` and `resolution_note`, `reviews/roundN.yaml`'s `resolution` /
  `stable_id`, and the `batch` block's counters. If any audit item has no
  persisted source, that source is newly defined.
- **FR12 - Where the discipline is defined:** The batch output-suppression
  discipline (activation condition, suppression scope, exceptions, marker-line
  format) is defined solely in `references/batch-mode.md`;
  `skills/develop/SKILL.md`, `references/review-phase.md`,
  `references/implement-phase.md` and `references/phases/*.md` reference it only
  and never restate the format or the scope.
- **FR13 - Plugin version bump:** Because files under `em-workflow/` change, the
  same change raises the `version` in `em-workflow/.claude-plugin/plugin.json`
  and in the root `.claude-plugin/marketplace.json`'s em-workflow entry to the
  same value (a patch bump, as a behavioural fix).

### Non-Functional Requirements

- **NFR1 - No regression in interactive mode:** For a launch without `--batch`,
  the output, the stop conditions and the report wording are exactly identical
  to the current behaviour.
- **NFR2 - Compatibility with existing consumers:** An existing external
  consumer that parses the terminal line can still make its "terminal line
  present = terminal state / terminal line absent = in-flight or abnormal"
  determination against the post-change output. The marker line must not make
  that determination ambiguous.
- **NFR3 - Diagnosability at a stop:** From a stop turn's output alone, the
  cause, the affected paths and the next human action are identifiable.
  Suppressing interim output must not reduce the information available at a
  stop.
- **NFR4 - A single SSOT:** The output-suppression discipline is not duplicated
  across documents, and introduces no contradiction under
  `scripts/check-plugin-invariants.py`'s criteria.
- **NFR5 - Voice:** The output that remains for humans (the Step C final report
  and stop reports) keeps its current voice: Japanese, casual form, first person
  「私」, no noun-ending sentences. The marker line and the terminal line are
  machine-readable fixed formats and are outside that voice rule.

## Implementation Approach

### Architecture

This feature has no runtime components. It changes protocol documents inside the
em-workflow plugin and the orchestrator's output discipline that those documents
govern (assumption A-005 — no new executable code is expected).

```
┌──────────────────────────────────────────────────────────────┐
│ references/batch-mode.md                                     │
│   sole definition of the output-suppression discipline:      │
│   activation condition / suppressed scope / exceptions /     │
│   marker-line format                          (FR12, NFR4)   │
└──────────────────────────────────────────────────────────────┘
        ▲ reference only (no restatement)
        │
┌───────┴───────────┬──────────────────────┬───────────────────┐
│ skills/develop/   │ references/          │ references/       │
│   SKILL.md        │   implement-phase.md │   review-phase.md │
│                   │                      │   phases/*.md     │
└───────────────────┴──────────────────────┴───────────────────┘

┌──────────────────────────────────────────────────────────────┐
│ references/batch-terminal-line.md                            │
│   sole owner of the terminal line — unchanged     (FR7)      │
└──────────────────────────────────────────────────────────────┘
```

### Data Flow

Per-turn decision on what the final assistant message contains:

```
develop launch
  └─ arguments contain --batch ?                                    (FR1)
       ├─ no  → current interactive output, unchanged        (FR1, NFR1)
       └─ yes → the turn's ending kind
            ├─ stop / abort            → full report + terminal line (FR6, FR7)
            ├─ Step C completion       → full final report + terminal line
            │                                              (FR5, FR11, FR7)
            ├─ --once phase boundary   → terminal line only     (FR8, FR4)
            └─ non-terminal (stop condition 5 wait,
               implement launch / wake) → one marker line only  (FR2, FR3)

In every --batch branch, phase-progress narration and interim summaries are
withheld from the main context.                                        (FR4)
File writes and commits follow the same path as before.                (FR9)
Gate resolution and status transitions follow the same path as before. (FR10)
```

### Output-Line Contract

Two machine-readable line shapes exist on a batch turn's final assistant
message. They must never be confused with each other.

| Line | When | Owner | Changed by this feature |
|---|---|---|---|
| Terminal line (`EM_WORKFLOW_TERMINAL:` prefix) | The turn reaches a terminal state (`completed` / `stopped` / `phase_done`) | `references/batch-terminal-line.md` | No (FR7) |
| Non-terminal marker line | The turn ends without reaching a terminal state | `references/batch-mode.md` | Yes — newly defined (FR2, FR3, FR12) |

Constraints the marker line must satisfy (FR3):

| Aspect | Constraint |
|---|---|
| Prefix | A fixed prefix that differs from `EM_WORKFLOW_TERMINAL:`, such that the terminal-line parser does not read the marker as a terminal line |
| Shape | Exactly one physical line: fixed prefix plus fixed fields |
| Signal preservation | The terminal-line contract's "no line means an abnormal outcome" signal remains intact (NFR2) |
| Confidentiality | Values carry no confidential information beyond paths |

The concrete prefix string and field set are chosen during implementation
subject to the constraints above; the requirements fix the constraints, not the
literal.

### Audit-Item Sourcing

Every audit item FR5 requires must resolve to a persisted source (FR11):

| Persisted source | Supplies |
|---|---|
| workflow.yaml (including the `batch` block's counters) | Auto-rework rounds consumed by review / verify |
| `phase-state/*.yaml` — `answers`, `resolution_note` | Recorded assumptions; unlisted-gate fallback resolutions; auto-approved command strings |
| `reviews/roundN.yaml` — `resolution`, `stable_id` | Deferred findings with their stable_ids |

An audit item found to have no persisted source gets a source newly defined as
part of this change (FR11).

### Database Schema

Not applicable — this feature introduces no data store and changes no file
artifact's content (FR9).

### Dependencies

**Internal Dependencies:**
- `em-workflow/references/batch-mode.md`: the sole definition site of the
  suppression discipline (FR12).
- `em-workflow/references/batch-terminal-line.md`: the terminal-line contract
  the marker line must not collide with (FR3, FR7).
- `em-workflow/skills/develop/SKILL.md`: hosts stop conditions 2-6, Step A,
  Step C and the verify gate; references the discipline (FR6, FR12).
- `em-workflow/references/implement-phase.md`: defines the launch and wake turns
  covered by FR2, and the second-failure stop covered by FR6.
- `em-workflow/references/review-phase.md`: defines the Phase R6 report body
  covered by FR4.
- `em-workflow/references/question-resolution.md`,
  `em-workflow/references/batch-policies.yaml`,
  `em-workflow/references/phase-state.md`: behaviour left unchanged (FR10,
  FR11).

**External Dependencies:**
- None.

### File Structure

```
em-workflow/
├── references/
│   ├── batch-mode.md            # suppression discipline defined here (FR12)
│   ├── batch-terminal-line.md   # unchanged contract, referenced (FR7)
│   ├── implement-phase.md       # references the discipline (FR2, FR6)
│   ├── review-phase.md          # references the discipline (FR4)
│   └── phases/*.md              # reference only, no restatement (FR12)
├── skills/develop/SKILL.md      # references the discipline (FR1, FR5, FR6)
└── .claude-plugin/plugin.json   # version bump (FR13)
.claude-plugin/marketplace.json  # em-workflow entry version bump (FR13)
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/batch-quiet-output/**`
- `test-docs/batch-quiet-output/**`

`feature-docs/batch-quiet-output/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/batch-quiet-output/**` covers
`test-docs/batch-quiet-output/{T}.tests.yaml`, the per-task test record. It is
generated and owned by `implement-phase.md`; this section cites it and restates
none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/batch-quiet-output/` directory at all; the declared
`test-docs/batch-quiet-output/**` entry is still correct in that case — a
declared path that never materializes is not a violation.

## Test Scenarios

### Document-Consistency Tests

- [ ] **TS-1** (FR1, NFR1) — Interactive-mode non-regression: confirm, through
      the agreement between SKILL.md and batch-mode.md, that a develop launch
      whose argument list contains no `--batch` never enters the
      output-suppression branch.
- [ ] **TS-2** (FR2, FR4) — Non-terminal turn markers: for each non-terminal
      point (stop condition 5, implement launch, implement wake), confirm that
      batch-mode.md carries the rule to emit only the marker line and that the
      corresponding sites in SKILL.md reference it.
- [ ] **TS-3** (FR3, FR7, NFR2) — Marker / terminal-line non-collision: confirm
      from both SSOT documents that the marker line's prefix is not a prefix
      match of `EM_WORKFLOW_TERMINAL:`.
- [ ] **TS-4** (FR5, FR6, FR8, NFR3) — Terminal turns keep full output: for all
      11 rows of batch-terminal-line.md's stop-point table, confirm that
      batch-mode.md's exception rule covers the corresponding turn as an
      exception to suppression.
- [ ] **TS-5** (FR11, FR9) — Audit-item provenance: confirm that each audit item
      in batch-mode.md "Reporting" traces one-to-one to a committed artifact or
      to a specific phase-state field.
- [ ] **TS-7** (FR12, NFR4, NFR5) — Plugin invariants and SSOT singularity:
      confirm, under `em-workflow/scripts/check-plugin-invariants.py`'s
      criteria, that the added text contradicts no existing SSOT.

### Regression Suite

- [ ] **TS-6** (FR10, FR13) — Existing suites pass:
      `python3 -m unittest discover -s tests` and
      `python3 em-workflow/hooks/tests/run-destructive-guard.py`.

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

## Security Considerations

- **Confidentiality of emitted lines:** The marker line's values carry no
  confidential information beyond paths (FR3), matching the terminal line's
  existing `detail` constraint (FR7).
- **Authentication / Authorization / Input validation / Data protection:** Not
  applicable — this feature adds no interface, no data store and no external
  integration.

## Error Handling

No new error codes are introduced. The terminal line's closed set of eleven stop
reason codes and their mapping to stop points stay owned by
`references/batch-terminal-line.md` and unchanged (FR7). Stop and abort turns
keep emitting cause, affected paths and recovery hints (FR6, NFR3).

```
Stop / abort occurs → full stop report (cause / paths / recovery hints)
                    → terminal line as the last line
```

## Performance Optimization

Not applicable — no performance requirement is defined for this feature.

## Success Criteria

- [ ] All functional requirements (FR1-FR13) are implemented.
- [ ] All non-functional requirements (NFR1-NFR5) are satisfied.
- [ ] All test scenarios (TS-1 - TS-7) pass.
- [ ] Every acceptance criterion in REQUIREMENTS.md section 11.1 is met.
- [ ] The suppression discipline exists in exactly one definition site
      (`references/batch-mode.md`).
- [ ] Code review is completed.

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

None — every requirement has `status: ok`.

## References

- Requirements document: `feature-docs/batch-quiet-output/REQUIREMENTS.md`
- Batch mode protocol: `em-workflow/references/batch-mode.md`
- Terminal line contract: `em-workflow/references/batch-terminal-line.md`
- Develop skill: `em-workflow/skills/develop/SKILL.md`
- Implement phase: `em-workflow/references/implement-phase.md`
- Review phase: `em-workflow/references/review-phase.md`
- Question resolution: `em-workflow/references/question-resolution.md`
- Batch policies: `em-workflow/references/batch-policies.yaml`
- Phase state: `em-workflow/references/phase-state.md`
