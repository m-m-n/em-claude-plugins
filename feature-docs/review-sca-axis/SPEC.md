# Feature: review-sca-axis

## Overview

em-workflow's review phase is composed entirely of LLM reviewer fan-out, which
`review-protocol.md`'s Read-only Constraint holds under a no-network rule. This
feature adds a second, deterministic machine-check axis (axis 2) that detects
known vulnerabilities in dependency packages with SCA tools, without changing
that constraint at all: axis 2 is not a place where an LLM judges, so it is
placed as a separate section rather than as an exception to the constraint. Its
findings merge into the existing R3a evaluation, R3b gate and R4 auto-fix
unchanged, and dependency updates are never auto-applied — they are left in a
human-triageable form.

Requirements document: `feature-docs/review-sca-axis/REQUIREMENTS.md`.

## Objectives

- Place a deterministic machine-check stage (axis 2), separate from the LLM
  fan-out, in em-workflow's review phase and detect known vulnerabilities in
  dependency packages with SCA tools.
- Achieve this without changing `review-protocol.md`'s no-network constraint in
  any way. Axis 2 is not a place where an LLM judges, so there is no reason to
  apply the same constraint to it; it is placed as a separate section on that
  basis.
- Merge the detected findings into the existing R3a evaluation, R3b gate and R4
  auto-fix as they are, rebuilding nothing downstream.
- Never auto-apply dependency updates; leave them in a form a human can triage
  (a notion-task-dispatch task, or a report under the repository root's `tmp/`
  when it is absent).

## User Stories

The resolved requirements carry no user stories: this feature introduces no user
interface and no end-user-facing rendering. Its acceptance criteria are
enumerated under Success Criteria below, each tagged with the requirement it
belongs to.

## Technical Requirements

### Functional Requirements

- **FR1 — New SCA scan script:** Add
  `em-workflow/scripts/scan-dependencies.py`. It determines the ecosystem from
  the review's `changed_files` and runs the corresponding SCA tool
  (`npm audit --json` / `cargo audit --json` / `pip-audit --format json` /
  `govulncheck -json`).

- **FR2 — Normalization of tool output into findings:** Normalize each tool's
  raw output into a review-result object conforming to
  `em-workflow/references/review-output-schema.json` (`findings` / `summary` /
  `skipped` / `skip_reason` / `source`). `source` is `tool` and each finding's
  `category` is `vulnerability`.

- **FR3 — Skip when the tool is absent:** When the corresponding SCA tool is not
  present in the environment, return `skipped: true` together with a
  machine-readable `skip_reason`. No LLM stands in for it (a knowledge cutoff
  would erase axis 2's meaning).

- **FR4 — New `vuln-scanners.yaml`:** Add
  `em-workflow/references/vuln-scanners.yaml` holding manifest → command →
  severity mapping → threshold (direct dependencies only / severity high and
  above). It follows the same SSOT conventions as `reviewers.yaml` (a header
  comment stating the responsibility split, and a `version` key).

- **FR5 — enum extension in `review-output-schema.json`:** Add `tool` to the
  root `source` enum and `vulnerability` to the finding `category` enum. Both
  are currently closed enums, and without the additions R3b rejects the output.
  `required` / `additionalProperties` / the `severity` enum are unchanged.

- **FR6 — notion-task-dispatch probe added to R0:** Add one probe step to
  `review-phase.md` Phase R0, in the same shape as step 5 "Probe codex" and
  step 6 "Probe litellm". The subject is the glob
  `~/.claude/plugins/cache/*/notion-task-dispatch/*/scripts/ntd.sh`. It does not
  hard-code the marketplace name, and picks the newest when several versions
  exist. The wording distinguishes it from R0 step 1's SSOT fail-closed
  resolution — this is an availability probe.

- **FR7 — `vulnerability` rides along R1's Layer-2 check:** Ride along the
  dependency-manifest / lockfile determination of `review-phase.md` Phase R1's
  "Mandatory Layer-2 check — license", adding `vulnerability` to the selected
  set on the same trigger. The existing `license` addition behaviour is
  unchanged.

- **FR8 — No LLM in axis 2:** Place no model invocation anywhere in axis 2.
  Judgement about reachability and attack scenarios is carried by the R3a
  evaluator (Opus). `vulnerability` is not added to `reviewers.yaml`'s
  `perspectives` (it has no LLM reviewer).

- **FR9 — Runs as an R2 peer and merges downstream:** Axis 2 runs as one entry
  of Phase R2's fan-out set, as a script execution by the orchestrator rather
  than as a Task. That run enters the set R2 builds as
  `perspectives_dispatched` / `reviewer_outputs`, and its findings pass through
  R3a's evaluation input, R3b's machine gate and R4's auto-fix as they are. R3b
  step 3's category cross-check and the evaluator accountability floor apply to
  `vulnerability` as well, so a critical/high the tool emitted cannot be
  silently suppressed by the evaluator.

- **FR10 — No auto-application of dependency updates:** Dependency updates are
  not auto-applied. R4 leaves `vulnerability` findings on the needs-judgment
  side.

- **FR11 — Task-creation timing and count:** Turning unresolved `vulnerability`
  findings into tasks happens exactly once per review phase. Its execution point
  is immediately before Phase R5 of the final round in which the review phase
  moves toward completion. It does not run per round (that would file up to
  three times, and would leave stale tasks for vulnerabilities R4 had already
  resolved).

- **FR12 — Branching of the filing destination:** When FR6's probe detects
  notion-task-dispatch, file with `--type セキュリティ`. When it does not, write
  a report under the repository root's `tmp/`.

- **FR13 — How the report destination is resolved:** The report destination is
  `tmp/` directly under the root of the first entry of
  `git -C {project_root} worktree list --porcelain` (the main working tree).
  `git rev-parse --show-toplevel` is not used, because it returns the review's
  `project_root` (the integration worktree).

- **FR14 — Task granularity:** One task per package. Multiple CVEs for the same
  package are listed as multiple lines in the "参照" field.

- **FR15 — Two-stage duplicate detection:** Task identity is judged by package
  name; the identity of a vulnerability entry inside a task is judged by
  CVE / GHSA ID.

- **FR16 — Scope of duplicate detection:** Duplicate detection considers
  incomplete tasks only. When only `完了` / `破棄` tasks exist, a new task is
  filed (a new advisory on a discarded package is a separate matter that
  deserves a fresh judgement).

- **FR17 — Localization of the duplicate-detection key:** Confine the
  construction of the duplicate-detection key to a single function inside the
  script; call sites use only that function. A later extension to
  "package name + major version" then requires no change at the call sites.

- **FR18 — Separation of severity from priority:** severity is retained as a
  fact in the "参照" field. The priority property is entered with an initial
  value of 「高」 and moved by a human during triage.

- **FR19 — Duplicate suppression in the review-security skill:** Add
  "既知 CVE の判定は軸 2 が機械的に行う" to the "What NOT to flag" section of
  `em-workflow/skills/review-security/SKILL.md`, reducing duplicate findings.

- **FR20 — Plugin version bump:** Raise the `version` of
  `em-workflow/.claude-plugin/plugin.json` and of the em-workflow entry in the
  root `.claude-plugin/marketplace.json` to the same value (both currently
  0.1.65).

- **FR21 — Existing test follow-up (source enum freeze update):**
  `tests/test_reviewer_roles_protocol.py`'s `FROZEN_SOURCE_ENUM` asserts exact
  equality with `["claude", "codex", "litellm"]` and therefore fails outright
  once FR5 adds `tool`. Update that pin within the same change. (The category
  enum side is `assertIn`-based and does not fail on the `vulnerability`
  addition.)

- **FR22 — New tests:** Following the conventions in `test/README.md`, add
  `test_*.py` under the repository-root `tests/` directory (Python standard
  library `unittest` only; no external dependency including PyYAML is imported).

- **FR23 — Excluding the tool run from LLM chain walking:** Axis 2's run is
  explicitly excluded from the LLM harness's registry chain walking, its
  fallback, and the `unreviewed_perspectives` accounting. That R2's fallback
  determination does not wake an LLM reviewer for a `source: tool` run is stated
  at the relevant place in review-phase.md.

- **FR24 — A deterministic signal for the final-round determination:** To make
  FR11's "once per review phase" hold, state on review-phase.md a signal by
  which the point at which task creation runs can be determined
  deterministically. Neither a path where filing is dropped because the signal
  never rises after an abnormal termination, nor a path where filing runs in a
  round that is not the final one, may arise.

### Non-Functional Requirements

- **NFR1 — Invariance of the no-network constraint:**
  `review-protocol.md`'s Read-only Constraint (no network calls except the
  cross-model harness invocation) is not changed, wording included. Axis 2 is
  not an exception to that constraint; it is organized as a separate section
  that is not an LLM reviewer.

- **NFR2 — The review's read-only discipline:** Axis 2's tool execution does not
  modify the working tree. It performs no automatic package installation, no
  lockfile rewriting and no formatter execution (`npm audit` and its peers are
  invoked in a form that only reads the existing lockfile).

- **NFR3 — Determinism:** No model invocation is placed anywhere on axis 2's
  decision path. The same input yields the same findings.

- **NFR4 — Treating tool output as untrusted:** SCA tool output (advisory titles
  and descriptions) is treated as untrusted text, never concatenated into prompt
  prose, and truncated under the same discipline as R3b step 4's 4096-byte
  limit.

- **NFR5 — No new gate identifier:** The filing / report branch is decided
  mechanically by R0's probe, so no new `gate_id` is introduced.
  `references/batch-policies.yaml` and the Non-packet gates table of
  `references/batch-mode.md` are unchanged (so as not to break
  `check-plugin-invariants.py`'s gate_id_coverage invariant).

- **NFR6 — Preservation of the plugin invariants:**
  `python3 em-workflow/scripts/check-plugin-invariants.py <repo-root>` still
  exits 0 (all 7 checks PASS).

- **NFR7 — Execution environment:** The new script is written in Python 3 and,
  like the existing `scripts/*.py`, may go as far as the plugin's runtime
  dependency (PyYAML). Test code uses the standard library only.

## Implementation Approach

### Architecture

Axis 1 (the LLM reviewer fan-out) and axis 2 (the deterministic tool stage) sit
side by side inside Phase R2, and merge into a single downstream chain:

```
R0  probe codex / probe litellm / probe notion-task-dispatch   <- FR6
R1  perspective selection (Mandatory Layer-2: license + vulnerability)  <- FR7
R2  ├── axis 1: LLM reviewers dispatched as Tasks (fan-out)
    └── axis 2: orchestrator runs scan-dependencies.py         <- FR1, FR9
             (source: tool; excluded from chain walk/fallback) <- FR23
R3a evaluation by the Opus evaluator (reachability judgement)  <- FR8
R3b machine gate (category cross-check + accountability floor) <- FR9
R4  auto-fix classification (vulnerability -> needs-judgment)  <- FR10
    ── final round only, immediately before R5: task creation  <- FR11, FR24
R5  round closure
```

**Component Diagram:**

- `em-workflow/scripts/scan-dependencies.py` — FR1/FR2/FR3's execution and
  normalization, FR13's destination resolution, FR14–FR18's filing and
  duplicate-detection logic, and FR12's branch.
- `em-workflow/references/vuln-scanners.yaml` — FR4's registry: manifest,
  command, severity mapping and threshold. Read by the script; no logic.
- `em-workflow/references/review-output-schema.json` — FR5's enum extension; the
  contract the normalized object is validated against.
- `em-workflow/references/review-phase.md` — FR6/FR7/FR9/FR10/FR11/FR23/FR24's
  protocol text.
- `em-workflow/skills/review-security/SKILL.md` — FR19's duplicate-suppression
  sentence.
- `em-workflow/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` —
  FR20's two registries.
- `tests/` — FR21's pin update and FR22's new modules.

### Data Flow

```
changed_files
  -> ecosystem determination (vuln-scanners.yaml manifest map)        FR1, FR4
  -> SCA tool invocation (read-only against the existing lockfile)    FR1, NFR2
  -> tool absent? -> skipped: true + skip_reason, findings empty      FR3
  -> normalization: threshold applied (direct only / high and above)  FR2, A7
  -> result object { findings, summary, skipped, skip_reason,
                     source: tool }, category: vulnerability          FR2, FR5
  -> recorded as one perspective_runs row with source: tool           A3
  -> R3a evaluation input -> R3b gate -> R4 (needs-judgment)          FR9, FR10
  -> final round, immediately before R5:
       probe hit  -> ntd.sh --type セキュリティ                        FR12
       probe miss -> report under main working tree's tmp/            FR12, FR13
```

### API Design

No API surface is added or changed. The interface between the orchestrator and
axis 2 is the `scan-dependencies.py` invocation and its
`review-output-schema.json`-conforming result object (FR2).

### Database Schema

No data model is added or changed. The shape of the result object axis 2
produces is stated in FR2 and pinned by `review-output-schema.json` (FR5).

### Dependencies

**Internal Dependencies:**

- `em-workflow/references/review-phase.md`: owns Phases R0–R5; the site of FR6,
  FR7, FR9, FR10, FR11, FR23 and FR24.
- `em-workflow/references/review-protocol.md`: owns the Read-only Constraint;
  unchanged (NFR1).
- `em-workflow/references/review-output-schema.json`: the schema the normalized
  object conforms to (FR2, FR5).
- `em-workflow/references/reviewers.yaml`: the SSOT-convention model for FR4;
  its `perspectives` stays at 6 entries (FR8).
- `em-workflow/references/batch-policies.yaml`,
  `em-workflow/references/batch-mode.md`,
  `em-workflow/scripts/check-plugin-invariants.py`: unchanged; the
  gate_id_coverage invariant must stay satisfied (NFR5, NFR6).
- `.claude/rules/core-plugin-version-bump.md`: the two-registry bump rule (FR20).
- `test/README.md`: the placement and dependency conventions for tests (FR22).

**External Dependencies:**

- `npm` / `cargo audit` / `pip-audit` / `govulncheck`: the SCA tools invoked by
  FR1. Each is optional — absence is handled by FR3's skip.
- `notion-task-dispatch`'s `scripts/ntd.sh`: optional, detected by FR6's probe
  and used by FR12's filing branch.
- The new script may depend on PyYAML as the plugin's runtime dependency; test
  code imports the standard library only (NFR7).

### File Structure

```
em-workflow/
├── scripts/
│   └── scan-dependencies.py          # FR1, FR2, FR3, FR12-FR18 (new)
├── references/
│   ├── vuln-scanners.yaml            # FR4 (new)
│   ├── review-output-schema.json     # FR5
│   └── review-phase.md               # FR6, FR7, FR9, FR10, FR11, FR23, FR24
├── skills/review-security/SKILL.md   # FR19
└── .claude-plugin/plugin.json        # FR20
.claude-plugin/marketplace.json       # FR20
tests/                                # FR21, FR22, NFR7
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

The feature-specific paths this SPEC anticipates, stated as a superset:

- `em-workflow/scripts/scan-dependencies.py`
- `em-workflow/references/vuln-scanners.yaml`
- `em-workflow/references/review-output-schema.json`
- `em-workflow/references/review-phase.md`
- `em-workflow/skills/review-security/SKILL.md`
- `em-workflow/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`
- `tests/**`

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/review-sca-axis/**`
- `test-docs/review-sca-axis/**`

`feature-docs/{feature}/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/{feature}/**` covers `test-docs/{feature}/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/{feature}/` directory at all; the declared
`test-docs/{feature}/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests

- [ ] **TS-1** (FR1, FR4): Script unit: for `changed_files` containing
      package.json / Cargo.toml / pyproject.toml / requirements.txt / go.mod,
      the expected ecosystem and command are selected.
- [ ] **TS-2** (FR2, FR5): Script unit: given representative JSON output
      samples (fixtures) from each tool, the normalized result is schema-valid
      against review-output-schema.json.
- [ ] **TS-3** (FR2, FR4): Script unit: the threshold (direct dependencies only
      / severity high and above) is applied at normalization time, so transitive
      dependencies and moderate/low advisories do not appear in findings.
- [ ] **TS-4** (FR3): Script unit: with the tool absent (an environment with an
      emptied PATH), `skipped: true` + `skip_reason` is returned and findings
      is empty.
- [ ] **TS-5** (FR15, FR17): Script unit: the duplicate-detection key function
      produces the expected key for a given package name / CVE, and a change to
      the key composition is confined to that function.
- [ ] **TS-10** (FR5, FR21): Schema pin: review-output-schema.json's source enum
      contains `tool` and the category enum contains `vulnerability`, while the
      severity enum and `required` are unchanged.
- [ ] **TS-11** (FR8): Registry pin: reviewers.yaml's perspectives remain 6
      entries and do not contain `vulnerability`.
- [ ] **TS-12** (FR19): Skill pin: review-security/SKILL.md's "What NOT to flag"
      carries the delegation sentence to axis 2.
- [ ] **TS-13** (FR20): Version bump: plugin.json and marketplace.json agree and
      are greater than 0.1.65.

### Integration Tests

- [ ] **TS-6** (FR13): Script unit: from `git worktree list --porcelain` output
      samples (including one where the integration worktree is not first),
      extract the first entry's path and build the destination under `tmp/`.
      Confirm this against reality by creating a disposable git repository under
      tempfile.
- [ ] **TS-7** (FR14, FR15, FR16): Duplicate detection: when an incomplete task
      for the same package already exists, no new task is filed and an entry is
      appended; when only `完了` / `破棄` tasks exist, a new task is filed.
- [ ] **TS-8** (FR6, FR7, FR23): Document pin: review-phase.md carries the probe
      in R0, `vulnerability` in R1's Mandatory Layer-2 check, and the tool-run
      exclusion in R2's fallback description.
- [ ] **TS-9** (FR11, FR24): Document pin: review-phase.md states the execution
      point of task creation and the final-round determination signal.

### E2E Tests

**Existing E2E tests**: None (this repository has no E2E foundation; TS-14).
**Run command**: Not detected

### Edge Cases

- [ ] Tool absent: no LLM fallback occurs; findings empty with a
      machine-stable `skip_reason` (TS-4, FR3).
- [ ] Threshold boundary: transitive dependencies and moderate/low advisories
      are dropped at normalization time and never reach findings (TS-3, A7).
- [ ] Integration worktree not first in `git worktree list --porcelain`: the
      first entry (the main working tree) is still what resolves the report
      destination (TS-6, FR13).
- [ ] Only `完了` / `破棄` tasks exist for a package: a new task is filed
      rather than suppressed as a duplicate (TS-7, FR16).

### Performance Tests

Not applicable: the resolved requirements state no performance target.

## Security Considerations

- **Input Validation:** SCA tool output (advisory titles and descriptions) is
  treated as untrusted text, is never concatenated into prompt prose, and is
  truncated under the same discipline as R3b step 4's 4096-byte limit (NFR4).
- **Data Protection:** Axis 2's tool execution does not modify the working tree
  — no automatic package installation, no lockfile rewriting, no formatter
  execution (NFR2).
- **Network:** `review-protocol.md`'s Read-only Constraint is unchanged, wording
  included. Axis 2 is organized as a separate section that is not an LLM
  reviewer, not as an exception to that constraint (NFR1).
- **Accountability:** R3b step 3's category cross-check and the evaluator
  accountability floor apply to `vulnerability`, so a critical/high the tool
  emitted cannot be silently suppressed (FR9).
- **Remediation policy:** Dependency updates are never auto-applied; R4 keeps
  `vulnerability` findings on the needs-judgment side and a human triages them
  (FR10, FR18).

## Error Handling

- Tool absent → `skipped: true` with a machine-readable `skip_reason`, findings
  empty; no LLM substitution (FR3).
- notion-task-dispatch absent → the filing branch falls back to writing a report
  under the main working tree's `tmp/` (FR12, FR13).
- No new `gate_id` and no new user-facing question are introduced for either
  branch; both are decided mechanically by R0's probe (NFR5, A9).
- FR24 requires that neither a dropped filing after an abnormal termination nor
  a filing in a non-final round can arise.

## Performance Optimization

Not applicable.

## Success Criteria

- [ ] **AC-1 (FR1):** `em-workflow/scripts/scan-dependencies.py` exists and
      determines the npm / cargo / pip / go ecosystems from changed_files,
      assembling the corresponding command.
- [ ] **AC-2 (FR2, FR5):** Each tool's JSON output is normalized into a result
      object that is schema-valid against review-output-schema.json
      (source: tool / category: vulnerability).
- [ ] **AC-3 (FR3):** When the corresponding tool is not on PATH, findings is
      empty, `skipped: true` and a machine-stable `skip_reason` are returned,
      and no LLM fallback occurs.
- [ ] **AC-4 (FR4):** `em-workflow/references/vuln-scanners.yaml` exists and
      holds manifest / command / severity mapping / threshold (direct
      dependencies only, severity high and above).
- [ ] **AC-5 (FR5):** review-output-schema.json's `source` enum contains `tool`
      and the finding `category` enum contains `vulnerability`; `required` /
      `additionalProperties` / the `severity` enum are as before.
- [ ] **AC-6 (FR6):** review-phase.md Phase R0 carries a notion-task-dispatch
      probe as a step, stating that it does not hard-code the marketplace name
      and picks the newest among multiple versions.
- [ ] **AC-7 (FR7):** review-phase.md Phase R1's Mandatory Layer-2 check states
      that a diff touching a dependency manifest or lockfile adds
      `vulnerability` in addition to `license`.
- [ ] **AC-8 (FR8):** Nowhere in axis 2's description is there a Task dispatch
      or model invocation, and it is stated that the reachability judgement is
      carried by the R3a evaluator. `reviewers.yaml`'s perspectives remain 6
      entries.
- [ ] **AC-9 (FR9):** The path by which axis 2 runs as an R2 peer and its run
      passes R3a's input, R3b's gate and R4's auto-fix is followable on
      review-phase.md (R3b step 3's category cross-check and the accountability
      floor apply to `vulnerability`).
- [ ] **AC-10 (FR23):** review-phase.md states that R2's fallback / chain-walk /
      `unreviewed_perspectives` accounting explicitly excludes `source: tool`
      runs.
- [ ] **AC-11 (FR10):** It is stated that R4's classification does not make
      `vulnerability` findings auto-applicable and drops them on the
      needs-judgment side.
- [ ] **AC-12 (FR11, FR24):** It is stated that task creation runs once per
      review phase, immediately before the final round's R5, and the signal that
      determines that "final round" deterministically is given.
- [ ] **AC-13 (FR12):** The branch is implemented: file with
      `--type セキュリティ` when notion-task-dispatch is detected, write a report
      under the repository root's `tmp/` when it is not.
- [ ] **AC-14 (FR13):** The report destination is resolved from the first entry
      of `git -C {project_root} worktree list --porcelain`, and
      `rev-parse --show-toplevel` is not used.
- [ ] **AC-15 (FR14):** One task per package, with multiple CVEs for the same
      package listed as multiple lines in the "参照" field.
- [ ] **AC-16 (FR15):** Duplicate detection runs in two stages: task identity =
      package name, entry identity = CVE/GHSA ID.
- [ ] **AC-17 (FR16):** Duplicate detection matches against incomplete tasks
      only; when only 完了 / 破棄 exist, a new task is filed.
- [ ] **AC-18 (FR17):** The construction of the duplicate-detection key is
      confined to one function, with no knowledge of the key composition leaking
      to the call sites.
- [ ] **AC-19 (FR18):** In the filed content, severity is recorded as a fact in
      the "参照" field and the priority property is entered with the initial
      value 「高」.
- [ ] **AC-20 (FR19):** review-security/SKILL.md's "What NOT to flag" carries
      the statement that the judgement of known CVEs is made mechanically by
      axis 2.
- [ ] **AC-21 (FR20):** plugin.json's and marketplace.json's em-workflow entries
      carry the same version, greater than 0.1.65.
- [ ] **AC-22 (FR21, FR22, NFR7):** `python3 -m unittest discover -s tests`
      exits 0 (including the source enum pin update in
      `tests/test_reviewer_roles_protocol.py`).
- [ ] **AC-23 (NFR5, NFR6):** `python3 em-workflow/scripts/check-plugin-invariants.py <repo-root>`
      exits 0.

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

None. Every FR is `status: resolved`.

## Assumptions

These assumptions were resolved by requirements-analyst and are carried here
unchanged.

| ID | Assumption | Reversible |
|----|------------|------------|
| A1 | `vulnerability` is added only to review-output-schema.json's category enum, not to reviewers.yaml's perspectives. Axis 2 has no LLM reviewer, and adding it would make R2 fan out an LLM. | true |
| A2 | `tests/test_reviewer_roles_protocol.py`'s `FROZEN_SOURCE_ENUM` is updated to `["claude", "codex", "litellm", "tool"]`. | true |
| A3 | Axis 2's execution result is recorded in the round record's `perspective_runs` as a single `source: tool` row, so that R3b step 3's category cross-check and the accountability floor can reference that run. The concrete form of run_id is decided at design/implementation time. | true |
| A4 | Axis 2 runs as a peer of Phase R2's fan-out set, as a deterministic step in which the orchestrator itself executes `scan-dependencies.py` (no Task dispatch). | true |
| A5 | The report is written under the main working tree's `tmp/`, with a filename containing the feature name and a timestamp. `tmp/` is already in .gitignore, so it is not committed. | true |
| A6 | The version is bumped by one patch: 0.1.65 → 0.1.66. | true |
| A7 | The threshold (direct dependencies only / severity high and above) is applied at normalization time, and advisories below the threshold are not emitted as findings. The tool's critical maps to `critical` and high to `high`; moderate / low are dropped by the threshold. | true |
| A8 | Axis 2 runs under both develop-driven and standalone (`/em-workflow:review`) execution (R0/R1 are the same sections shared by both contexts). The filing / report branch follows the same probe under standalone as well. | true |
| A9 | No new `gate_id` is introduced. The filing / report branch is a mechanical determination by the probe and adds no question to the user. | true |

Their recorded reasons:

- **A1**: From the existing fact that `tests/test_reviewers_primary_chains.py`
  pins perspectives at exactly 6 entries, and from the instruction memo's "no
  LLM in axis 2". The Codex consultation (Q2) reached the same conclusion.
- **A2**: The existing test pins by exact equality; without the update the
  source enum extension turns red immediately.
- **A3**: Mapping the constraint "treating axis 2 as a perspective makes the
  accountability floor apply" onto the existing R3b / R5 machinery leaves no
  path other than recording it as a dispatched run. Confirmed in the Codex
  consultation (Q2).
- **A4**: Compared in the Codex consultation (Q1) against adding an independent
  stage between R1 and R3a; placing it as an R2 peer was judged superior because
  it enters the `perspectives_dispatched` / `reviewer_outputs` that R3a consumes
  as they are.
- **A5**: The repository's .gitignore carries `tmp/`, and this matches the
  temporary-file placement policy.
- **A6**: `core-plugin-version-bump.md` invokes semver while stating that "in
  practice almost everything is a behaviour correction, so patch granularity is
  the baseline", and the repository's record is consistently patch.
- **A7**: review-output-schema.json's severity enum carries only
  critical/high/medium and cannot express below-threshold. R3b accepts medium
  as well, so a downstream filter would not work either. Confirmed in the Codex
  consultation (Q4).
- **A8**: review-phase.md is structured so that one protocol covers two
  execution contexts, and there is no instruction to add a context branch to
  R0/R1.
- **A9**: The instructions carry no mention of a new gate, and
  check-plugin-invariants.py's gate_id_coverage fails in both directions, so a
  casual addition would be an invariant violation.

## Design Step

Skipped. The feature carries no UI and no visual artifact at all. Its subjects
are one Python script, one YAML registry, text edits to an existing JSON schema,
a Markdown protocol and a skill, and a plugin version bump.
`design_system_candidates` is empty, and no design-system candidate exists.

## References

- Requirements document: `feature-docs/review-sca-axis/REQUIREMENTS.md`
- `em-workflow/references/review-phase.md`: the review-phase protocol (R0–R5)
- `em-workflow/references/review-protocol.md`: the Read-only Constraint
- `em-workflow/references/review-output-schema.json`: the review-result schema
- `em-workflow/references/reviewers.yaml`: the reviewer registry and the SSOT
  convention model
- `em-workflow/skills/review-security/SKILL.md`: the security-perspective skill
- `em-workflow/scripts/check-plugin-invariants.py`: the plugin invariant check
- `.claude/rules/core-plugin-version-bump.md`: version-bump granularity
- `test/README.md`: test placement and dependency conventions
