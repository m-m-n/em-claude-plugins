# Implementation Plan: review-sca-axis

## Overview

Adds a deterministic machine-check stage (axis 2) to em-workflow's review
phase: one new script and one new registry, an additive enum extension to the
review-result schema, protocol text placing the axis inside Phase R2 and its
findings in the existing R3a / R3b / R4 chain, plus a duplicate-suppression
note in the security skill and the mandatory plugin version bump.

## Technology Stack

- **Language**: Python 3 (script), Markdown / YAML / JSON (references,
  registry, schema), `unittest` (tests).
- **Runtime dependency**: PyYAML — ALREADY the plugin's runtime dependency
  (`em-workflow/scripts/validate-worker-output.py` uses it). This feature
  introduces **no new third-party dependency**, so no license check is
  triggered; `project.license` is `none` and stays `none`.
- **External programs** (invoked, never vendored, never installed by this
  feature — each optional): `npm`, `cargo audit`, `pip-audit`,
  `govulncheck`, and notion-task-dispatch's `ntd.sh`. They are environment
  facts, not project dependencies; absence is a first-class handled state.
- **Test dependency**: standard library only (NFR7). A test module may load
  the script under test by file path; the script's own PyYAML import is
  transitive and does not breach NFR7 (existing precedent:
  `tests/test_validate_worker_output.py`).

## Layer Structure

Four layers; dependencies point downward only.

| Layer | Member | Responsibility |
|---|---|---|
| Protocol | `em-workflow/references/review-phase.md` | States WHEN the orchestrator runs axis 2 and HOW its run joins R2 / R3a / R3b / R4 / R5. Contains no logic the script owns. |
| Contract | `em-workflow/references/review-output-schema.json` | The shape axis 2's output is validated against. |
| Script | `em-workflow/scripts/scan-dependencies.py` | The only executable component: ecosystem detection, tool execution, normalization, triage filing / report. Never decides its own execution point. |
| Registry | `em-workflow/references/vuln-scanners.yaml` | Data only (manifest → command → severity map → threshold). No logic, no conditionals. |

The script is invoked by the orchestrator, never by a Task-dispatched agent,
and never invokes a model (FR8, NFR3).

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|---|---|---|---|
| **`scan` subcommand** | Run axis 2's detection pass | **Pre**: caller supplies the project root, the review's changed-file list, and an optional registry-path override (default: the registry file in the plugin's own `references/` directory). **Post**: exactly one JSON object conforming to `review-output-schema.json` on stdout, with `source: "tool"`; process exit 0 whenever a result object was produced (including `skipped: true`); a distinct non-zero exit only for an execution error (unreadable/absent registry, missing PyYAML), with the failure named on stderr and NO object on stdout. Never writes inside the project root (NFR2). | task0001, task0003 |
| **`file-tasks` subcommand** | Turn unresolved vulnerability findings into human-triageable artifacts | **Pre**: caller supplies the project root, the feature name, a path to a JSON file holding an array of already-gated findings (each `category: "vulnerability"`, each unresolved — the SELECTION of which findings qualify is the orchestrator's, never the script's), and the notion-task-dispatch entry-point path when R0's probe found one (absent ⇒ report branch). **Post**: one JSON summary object on stdout naming the branch taken (`ntd` / `report`), the packages filed, the packages appended to, the duplicates suppressed, and the report path when the report branch ran; exit 0 on success. Idempotent for the same input: a second run against the same unresolved set files nothing new. | task0005, task0004 |
| **Module co-ownership skeleton** | Keep one file implementable by two parallel tasks | `scan-dependencies.py` is created by BOTH task0001 and task0005. Both register BOTH subcommand names in the same subcommand-style CLI dispatch. Each task implements its own subcommand fully and supplies the other subcommand as a clearly-marked placeholder that exits with the execution-error code and a one-line "implemented by the other task" message. **Merge duty (symmetric, both tasks)**: when the integration branch already carries the other subcommand's real implementation, the merging implementer adopts the parent side and re-applies only its own half — a placeholder MUST NEVER overwrite a real implementation. After the second merge the file exposes both subcommands and both tasks' tests pass. | task0001, task0005 |
| **Normalized result object** | Axis 2's single output shape | `findings` (array; empty when nothing crosses the threshold), `summary` (one line of prose, no untrusted text spliced in), `skipped` (true only when the ecosystem's tool is not resolvable on PATH), `skip_reason` (machine-stable identifier string, `null` when `skipped` is false), `source: "tool"`. Every finding carries `category: "vulnerability"` and `severity` in {`critical`, `high`} only. No property outside the schema (the schema forbids additional properties). The two enum values this shape depends on are added to the schema by task0001, which owns that file. | task0001, task0003 |
| **Finding text-encoding contract** | Carry package identity and advisory identity through a schema that forbids extra fields | `file` = the project-relative dependency manifest that declares the package (must exist under the project root, so R3b step 1's existence check passes). `line` = the manifest line when known, else null. `title` = a single line of the fixed form `{package}: {advisory_id} — {advisory short title}` — package name first, then `": "`, then the advisory identifier (CVE / GHSA / RUSTSEC / PYSEC / GO- form), then `" — "`, then the (truncated) advisory title. `description` = affected range, fixed version, and the advisory summary, all truncated per the truncation discipline below. `suggestion` = prose only (see D4). Recovery of `(package, advisory_id)` from a finding is done through ONE function in the script; no call site parses `title` itself. | task0001, task0005 |
| **Untrusted-text truncation** | One discipline for every attacker-influenced string | Advisory titles, descriptions and any other tool- or advisory-sourced text is treated as untrusted: never concatenated into prompt prose, never interpreted as instructions, and truncated to at most 4096 bytes per field with a visible truncation marker — the same limit R3b step 4 applies. Implemented as ONE helper in the script and used by every producer of a `title` / `description` / `suggestion` / filed-task field. | task0001, task0005 |
| **Axis-2 run identity** | Make R3b's category cross-check and accountability floor apply to axis 2 | The orchestrator records axis 2's execution as ONE `perspective_runs` row: `run_id: "vulnerability#tool"`, `perspective: vulnerability`, `role: tool` (a new value alongside `primary` / `fallback` / `evaluator`), `source: tool`, `status` one of `completed` / `skipped` (with `skip_reason`) / `failed`. That row is what `perspectives_dispatched` carries into R3a and what R3b step 3 resolves a `vulnerability` finding's source against. | task0003, task0001, task0004 |

## Conventions

- **Naming**: new test modules are `tests/test_sca_*.py`; each locates repo
  files relative to its own resolved path (two parents up), following the
  existing modules' pattern.
- **Test dependencies**: stdlib only in a test module's own imports. YAML
  content asserted by tests is read with a hand-rolled restricted-subset
  parser local to the test module — the established repository convention
  (`tests/test_batch_policies.py`, `tests/test_reviewers_primary_chains.py`).
- **Script error policy**: a produced result object is exit 0 even when it
  reports a skip; execution errors (missing PyYAML, unreadable registry,
  malformed inputs) use a distinct non-zero exit code and print the reason
  to stderr, never a partial object to stdout. Existing precedent:
  `em-workflow/scripts/validate-worker-output.py`.
- **Working-tree discipline**: nothing on axis 2's scan path writes inside
  the review's project root — no install, no lockfile rewrite, no formatter
  run (NFR2). The filing path writes only outside it (main working tree
  `tmp/`) or to the external task system.
- **Protocol edits are additive**: several existing test modules pin
  `review-phase.md`'s text. Add steps, rows and sentences; do not reflow or
  reword sentences that are already pinned.
- **Definition of done, every task**: `python3 -m unittest discover -s tests`
  exits 0 AND `python3 em-workflow/scripts/check-plugin-invariants.py
  <repo-root>` exits 0, in the task's own worktree, before it is complete.
- **Registry style**: `vuln-scanners.yaml` follows `reviewers.yaml`'s SSOT
  conventions — a header comment stating the responsibility split (registry
  owns WHICH tool and WHICH threshold; the script owns HOW to run and
  normalize) and a top-level `version` key.

## Cross-task Design Decisions

### D1 — Axis 2 is recorded as a dispatched run, not as a reviewer

Axis 2 produces one `perspective_runs` row (see Shared Components, "Axis-2
run identity") whose `perspective` is `vulnerability`, even though
`reviewers.yaml` has no such perspective. This is what makes R3b step 3's
category cross-check resolve a `vulnerability` finding to a real dispatched
run, and what puts axis 2's critical/high sites under the evaluator
accountability floor (FR9). Affected: task0003 (protocol prose), task0001
(emits `source: tool`), task0004 (the round record carries the row).

### D2 — `vulnerability` is a selected-set member with no registry entry

R1's Mandatory Layer-2 check adds `vulnerability` on the same
manifest/lockfile trigger that already adds `license` (FR7). Because
`reviewers.yaml` deliberately keeps six perspectives (FR8), R2's fan-out
must state that `vulnerability` is served by axis 2's script execution and
is never looked up in the registry, never chain-walked, never counted in the
R2b fallback budget, and never listed in `unreviewed_perspectives` (FR23).
Without this statement R2 would either fail a registry lookup or wake an LLM
reviewer for a `source: tool` run. Affected: task0003.

### D3 — The final-round signal is the round's closing disposition

Task creation runs exactly once per review phase, immediately before the
final round's R5 (FR11). The deterministic signal (FR24) is the round's
**closing disposition**, computed after R4's loop termination and BEFORE the
round record is written, from inputs the orchestrator has already computed
mechanically (residual critical/high count, `--report-only`, the loop
termination reason, the batch rework counter): the disposition is
`another-round` or one of `complete` / `rework` / `defer`. Task creation runs
iff the disposition is NOT `another-round` — that is, iff this round closes
the review step.

Two failure modes are closed explicitly:

- **Filing in a non-final round**: impossible, because `another-round`
  suppresses it and the disposition is computed from the same values that
  decide whether another round runs.
- **Filing dropped after abnormal termination**: a run that dies before R5
  wrote no round record, so the resumed review re-runs the round and
  recomputes the same disposition. Re-filing is safe because the filing path
  is idempotent under its own duplicate detection (FR15/FR16).

The round record carries the receipt: a root field recording whether triage
filing ran this round, the branch taken, and the packages filed / appended /
suppressed (present and empty when the disposition was `another-round`).
Affected: task0004 (protocol prose and record shape), task0005 (idempotency
is the recovery guarantee this decision leans on).

### D4 — A vulnerability finding's `suggestion` is always prose

R4 classifies a candidate as auto-applicable only when its `suggestion` has
unified-diff shape. Emitting remediation as prose — never as a diff, never
containing diff hunk markers — is therefore the MECHANICAL reason a
dependency update can never be auto-applied (FR10), in addition to the
protocol statement. Affected: task0001 (produces the field), task0004
(states the R4 consequence).

### D5 — The threshold is applied at normalization time

Direct dependencies only, severity high and above. The tool's `critical`
maps to `critical`, `high` maps to `high`; anything lower, and anything
reached only transitively, is dropped before a finding object exists (A7).
This is forced by the schema: its `severity` enum cannot express a
below-threshold value, and R3b accepts `medium`, so a downstream filter
would not hold the line. Affected: task0001 (drop logic), task0003 (the
protocol states the threshold lives in the registry, not in the protocol).

### D6 — Task-system listing failure degrades to the report branch

Duplicate detection (FR15/FR16) can only run against the external task
system's list of incomplete tasks. When the notion-task-dispatch entry point
was probed successfully but its listing cannot be obtained (non-zero exit,
unparseable output), the filing path does NOT file blind: it falls back to
the report branch and states the degradation in the report. Filing without
duplicate detection would spam the task system on every review round;
silently dropping the findings would lose them. Affected: task0005.

### D7 — Exactly two files are written by more than one task

- `em-workflow/scripts/scan-dependencies.py` — task0001 + task0005, ONE
  file created by both. Absorbed by the co-ownership skeleton and the
  symmetric merge duty in Shared Components above, restated in both plans.
- `em-workflow/references/review-phase.md` — task0003 + task0004, DISJOINT
  regions: task0003 edits R0 / R1 / R2 / R2b / R3a / R3b, task0004 edits
  R4 / R5 only. Neither task touches the other's region, so the two branches
  produce non-overlapping hunks in a long document.

Every other file in this feature has exactly one writing task. In particular
`review-output-schema.json` and `tests/test_reviewer_roles_protocol.py` are
task0001's alone: it owns the enum extension AND the frozen-pin update in the
same change, so no second writer and no cross-branch agreement rule exists
for them.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Two parallel tasks create `scan-dependencies.py` independently and the second merge clobbers the first half | Medium | High | Co-ownership skeleton + symmetric merge duty in both plans; both subcommands registered in both branches; post-merge criterion that both halves' tests pass |
| Editing `review-phase.md` breaks an existing document-pin test (several modules assert its text) | Medium | Medium | Every task's definition of done runs the full suite; the additive-edit convention above; the two document tasks own disjoint regions (D7) |
| The schema enum edit turns the existing `FROZEN_SOURCE_ENUM` pin red | High | Medium | Both halves are task0001's, in one change: the task cannot land the schema edit without the pin update, and its own definition of done runs the full suite |
| `vulnerability` reaching R2's registry lookup as an ordinary perspective would wake an LLM reviewer | Medium | High | D2's explicit exclusion statement, plus TS-11 pinning `reviewers.yaml` at six perspectives |
| The external task system's CLI surface is not pinned by SPEC and is unavailable in the implementer's environment | High | Medium | The entry-point path is an INPUT to the script (never discovered inside it), so tests substitute a stand-in executable; D6 defines the degraded path |
| Filing runs twice across a resume | Low | Medium | D3's disposition signal plus the filing path's own idempotency (package-name identity) |
| Report written into the wrong tree (integration worktree instead of the main one) | Medium | Medium | Destination resolved only from the first entry of the porcelain worktree listing; the top-level-resolution command is explicitly banned (FR13) and covered by TS-6 against a real temporary repository |

## Open Questions

- [ ] The notion-task-dispatch listing/creation CLI surface (how incomplete
      tasks are enumerated, how the 「参照」 field and the priority property
      are set) is not pinned by SPEC and is owned by a separate repository.
      task0005 resolves it from the installed plugin at implementation time;
      if the installed surface cannot support incomplete-task enumeration,
      D6's report branch is the standing fallback and the mismatch is a
      reportable plan deviation.
- [ ] D3 adds a receipt field to the round record's shape. If a future
      round-record consumer validates that record against a closed schema,
      this field has to be added there too — no such consumer exists today.
