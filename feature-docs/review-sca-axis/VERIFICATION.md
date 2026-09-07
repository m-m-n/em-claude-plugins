# Verification Document: review-sca-axis

## Overview

**Feature**: review-sca-axis (deterministic SCA axis in the review phase) /
**SPEC.md**: `feature-docs/review-sca-axis/SPEC.md` /
**IMPLEMENTATION.md**: `feature-docs/review-sca-axis/IMPLEMENTATION.md`

This document covers the INTEGRATED verification run after every task has
merged. Per-task acceptance criteria live in `tasks/taskNNNN.md`.

## Build Verification

- Command: none — `project.components.main.build_command` is empty. The
  deliverables are Python scripts, Markdown / YAML / JSON references and
  tests; there is no compilation step.
- Substitute gate (syntax): the test command below imports every new script,
  so a syntax error in `scan-dependencies.py` fails the suite.

## Test Verification

- Command: `python3 -m unittest discover -s tests`
- Expected: exit code 0, no errors, no skips introduced by this feature that
  are not an explicit environment guard.
- Coverage target: no numeric coverage gate exists in this repository. The
  binding target is criterion-level: every acceptance criterion of every task
  maps to at least one test, and every TS row below has at least one
  asserting test module.

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Ecosystem and command selection from a changed-file list containing package.json / Cargo.toml / pyproject.toml / requirements.txt / go.mod | The expected ecosystem and the registry-defined command are selected for each | Unit |
| TS-2 | Normalization of representative machine-readable output samples from each of the four tools | The result object conforms to review-output-schema.json (source `tool`, category `vulnerability`, no extra properties) | Unit |
| TS-3 | Threshold at normalization time | Transitive dependencies and below-high advisories never appear in `findings` | Unit |
| TS-4 | The ecosystem's tool is not resolvable on PATH | `skipped: true` + machine-stable `skip_reason`, `findings` empty, exit 0, no LLM fallback | Unit |
| TS-5 | Duplicate-detection key function | The expected key for a given package / advisory pair; no call site composes a key itself | Unit |
| TS-6 | Report destination from a porcelain worktree listing, including an ordering where the integration worktree is not first, confirmed against a real disposable repository | The FIRST entry's root is used; destination is `tmp/` under it; the top-level-resolution command is absent from the script | Integration |
| TS-7 | Duplicate detection over a mixed listing (incomplete / complete / discarded) | Incomplete match ⇒ append entries, no new task; only complete/discarded ⇒ new task; one task per package with multiple 参照 lines | Integration |
| TS-8 | review-phase.md pins: R0 probe, R1 Mandatory Layer-2 `vulnerability`, R2/R2b tool-run exclusion | All three statements present in their own phase sections | Unit (document) |
| TS-9 | review-phase.md pins: triage execution point, final-round signal, both failure modes closed, round-record receipt, mechanical branch | All five statements present in R4/R5 | Unit (document) |
| TS-10 | review-output-schema.json enums and invariance; FROZEN_SOURCE_ENUM pin | `tool` and `vulnerability` present; `required`, `additionalProperties`, `severity` unchanged; the pin is the four-value list | Unit |
| TS-11 | reviewers.yaml registry pin | Exactly six perspectives, none of them `vulnerability` | Unit |
| TS-12 | review-security/SKILL.md pin | "What NOT to flag" carries the axis-2 delegation statement; the rest of the skill is unchanged | Unit |
| TS-13 | Version parity and increase | plugin.json and marketplace.json agree; the value exceeds 0.1.65 by semantic-version comparison | Unit |
| TS-14 | E2E | Not applicable — this repository has no E2E foundation | — |
| TS-15 | review-phase.md pins: axis-2 run row, its path through R3a / R3b step 3 / the accountability floor, and R4's no-auto-apply statement | Present and followable in the document | Unit (document) |
| TS-16 | review-protocol.md Read-only Constraint invariance | The section's content is byte-identical to its pre-change bytes | Unit (document) |
| TS-17 | Gate-identifier invariance | batch-policies.yaml and batch-mode.md's Non-packet gates table carry no new gate identifier | Unit (document) |
| TS-18 | Filing branch, 参照 field content and priority initial value | External-system branch invoked with the security type argument; report branch when absent; severity recorded as fact; priority 「高」 | Integration |
| TS-19 | Read-only discipline and determinism of the scan path | Repeated runs are byte-identical; the project root's file state is unchanged by a scan | Unit |
| TS-20 | Untrusted-text truncation | Fields over 4096 bytes are truncated with a visible marker; no `suggestion` carries diff hunk markers | Unit |
| TS-21 | Plugin invariants | `check-plugin-invariants.py` exits 0 with all seven checks PASS | Integration |
| TS-22 | Test-dependency discipline | Every `tests/test_sca_*.py` module imports only standard-library modules in its own import statements | Unit |

## Code Quality Verification

- Format: none — `project.components.main.format_command` is empty. Follow
  the surrounding files' existing style instead (the repository's scripts and
  references are hand-formatted).
- Static analysis: `python3 em-workflow/scripts/check-plugin-invariants.py
  <repo-root>` — all seven checks PASS, exit 0 (NFR6). This also covers the
  gate-identifier coverage invariant NFR5 depends on.

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | scan-dependencies.py exists and determines npm / cargo / pip / go from changed_files, assembling the command | TS-1 |
| AC-2 | Each tool's output normalizes into a schema-valid object (source tool / category vulnerability) | TS-2 |
| AC-3 | Tool absent ⇒ findings empty, `skipped: true`, machine-stable `skip_reason`, no LLM fallback | TS-4 |
| AC-4 | vuln-scanners.yaml holds manifest / command / severity map / threshold | TS-1, TS-3 |
| AC-5 | Schema `source` gains `tool`, `category` gains `vulnerability`; required / additionalProperties / severity unchanged | TS-10 |
| AC-6 | R0 carries the notion-task-dispatch probe with no hard-coded marketplace name and newest-version selection | TS-8 |
| AC-7 | R1's Mandatory Layer-2 check adds `vulnerability` alongside `license` | TS-8 |
| AC-8 | No Task dispatch / model call in axis 2's description; reachability is the R3a evaluator's; reviewers.yaml stays at six perspectives | TS-11, TS-15 |
| AC-9 | The R2-peer → R3a → R3b → R4 path is followable, with category cross-check and accountability floor applying to `vulnerability` | TS-15 |
| AC-10 | R2's fallback / chain-walk / unreviewed_perspectives accounting excludes `source: tool` | TS-8 |
| AC-11 | R4 never makes `vulnerability` auto-applicable | TS-15 |
| AC-12 | Task creation runs once per review phase immediately before the final round's R5, with the determining signal stated | TS-9 |
| AC-13 | Branch implemented: security-type filing when detected, `tmp/` report when not | TS-18 |
| AC-14 | Report destination from the first porcelain worktree entry; top-level resolution not used | TS-6 |
| AC-15 | One task per package; multiple advisories as multiple 参照 lines | TS-7 |
| AC-16 | Two-stage duplicate detection (package name / advisory id) | TS-5, TS-7 |
| AC-17 | Incomplete tasks only; complete/discarded ⇒ new task filed | TS-7 |
| AC-18 | Key construction confined to one function | TS-5 |
| AC-19 | severity as fact in 参照; priority initial value 「高」 | TS-18 |
| AC-20 | review-security SKILL.md carries the axis-2 delegation statement | TS-12 |
| AC-21 | plugin.json and marketplace.json agree, above 0.1.65 | TS-13 |
| AC-22 | `python3 -m unittest discover -s tests` exits 0, including the updated source-enum pin | Test Verification command above |
| AC-23 | `check-plugin-invariants.py` exits 0 | TS-21 |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1 |
| FR2 | task0001 | TS-2, TS-3 |
| FR3 | task0001 | TS-4 |
| FR4 | task0001 | TS-1, TS-3 |
| FR5 | task0001 | TS-10, TS-2 |
| FR6 | task0003 | TS-8 |
| FR7 | task0003 | TS-8 |
| FR8 | task0003 | TS-11, TS-15 |
| FR9 | task0003 | TS-15 |
| FR10 | task0004 | TS-15 |
| FR11 | task0004 | TS-9 |
| FR12 | task0005 | TS-18 |
| FR13 | task0005 | TS-6 |
| FR14 | task0005 | TS-7 |
| FR15 | task0005 | TS-5, TS-7 |
| FR16 | task0005 | TS-7 |
| FR17 | task0005 | TS-5 |
| FR18 | task0005 | TS-18 |
| FR19 | task0006 | TS-12 |
| FR20 | task0006 | TS-13 |
| FR21 | task0001 | TS-10 |
| FR22 | task0001, task0003, task0004, task0005, task0006 | TS-22 |
| FR23 | task0003 | TS-8 |
| FR24 | task0004 | TS-9 |
| NFR1 | task0003 | TS-16 |
| NFR2 | task0001, task0005 | TS-19, TS-18 |
| NFR3 | task0001 | TS-19 |
| NFR4 | task0001, task0005 | TS-20 |
| NFR5 | task0003 | TS-17 |
| NFR6 | task0003, task0006 | TS-21 |
| NFR7 | task0001, task0005, task0006 | TS-22 |

## E2E Testing

Not applicable. This repository has no E2E framework and
`project.components.main.e2e_test_command` is empty (TS-14).

## Manual Testing (E2E Not Possible)

The following cannot be automated inside this repository, because they need
real SCA tools, a real vulnerable dependency, or the separately-installed
task-dispatch plugin. Each is a one-time confirmation on the integrated
branch, not a gate the suite can hold.

- [ ] Run the scan subcommand by hand in a scratch project that has a real
      lockfile with at least one high-severity direct advisory, with the
      corresponding tool installed. Confirm the emitted object is
      schema-valid, findings carry the pinned title form, and the working
      tree is untouched afterwards (`git status` clean).
- [ ] Run the same scan with the tool uninstalled and confirm the skip shape
      and exit code, and that nothing tried to install anything.
- [ ] With the task-dispatch plugin actually installed, run the filing
      subcommand once against a small findings file and confirm: one task per
      package, the security type argument reached the tool, 参照 carries one
      line per advisory with its severity, and the priority property came out
      as 「高」. Then run it a second time and confirm nothing new is filed.
- [ ] With the plugin absent, confirm the report lands under the MAIN working
      tree's `tmp/` (not the integration worktree's) and is not picked up by
      `git status`.
- [ ] Read the merged Phase R2 / R4 / R5 text end to end once and confirm a
      reader can follow the axis-2 run from selection to the round record
      without consulting IMPLEMENTATION.md.

No mockup comparison applies — the design step is `skipped` and this feature
has no visual artifact.

## Security Verification

- **NFR1**: `review-protocol.md`'s Read-only Constraint is byte-unchanged
  (TS-16). Axis 2 is documented as a separate non-LLM stage, never as an
  exception to that constraint.
- **NFR4**: every advisory-sourced string is truncated at 4096 bytes and is
  passed only inside structured fields, never spliced into prompt prose
  (TS-20).
- **FR9 accountability**: a tool-reported critical/high site cannot be
  silently suppressed by the evaluator — R3b step 3's category cross-check
  and the accountability floor apply to `vulnerability` (TS-15).
- **FR10 remediation policy**: no dependency update is auto-applied; the
  prose-only `suggestion` contract makes the R4 shape probe route every
  vulnerability finding to needs-judgment (TS-15, TS-20).
- **NFR2**: the scan path performs no installation, no lockfile rewrite and
  no formatter run (TS-19).

## Performance Verification

Not applicable — the resolved requirements state no performance target.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Script behaviour (scan) | 6 | 6 | 0 | 2 |
| Script behaviour (filing) | 5 | 5 | 0 | 2 |
| Schema / registry pins | 3 | 3 | 0 | 0 |
| Protocol document pins | 5 | 5 | 0 | 1 |
| Skill / version pins | 2 | 2 | 0 | 0 |
| Repository invariants | 2 | 2 | 0 | 0 |
| **Total** | **23** | **23** | **0** | **5** |
