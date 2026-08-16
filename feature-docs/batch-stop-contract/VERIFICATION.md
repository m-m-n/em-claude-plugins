# Verification Document: batch-stop-contract

## Overview

**Feature**: batch-stop-contract
**SPEC.md**: `feature-docs/batch-stop-contract/SPEC.md`
**IMPLEMENTATION.md**: `feature-docs/batch-stop-contract/IMPLEMENTATION.md`

This document covers the INTEGRATED verification run after every task has
merged. Per-task acceptance criteria live in the task plans.

## Build Verification

- Command: none. `project.components.main.build_command` is empty — the
  change surface is Markdown / YAML documents, Python test modules and two
  JSON manifests, none of which is compiled.
- Expected: not applicable.

## Test Verification

- Command: `python3 -m unittest discover -s tests` (run from the repository
  root)
- Expected: exit code 0, no failures, no errors.
- Coverage target: not measured — the project has no coverage tooling.
  Coverage is expressed instead as the requirement-to-TS mapping below; every
  FR/NFR must map to at least one passing scenario.
- Additional expectation (NFR2): `git status` shows no modification to any
  test module that existed before this feature.

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS1 | The contract SSOT defines the terminal line's prefix, its field composition, and that a line of the same format is emitted on both completion and stop | The contract document's `## Line format` and `## Field values` sections carry the prefix literal, the fixed four-field order and both terminal states; emission requires no external tool | Unit (documentation contract) |
| TS2 | The contract SSOT enumerates a closed set of stop reason codes, each accompanied by a step field and a `detail` field | The extracted code set equals the set fixed in IMPLEMENTATION.md, has no duplicate and no empty member, and the section documents the step and `detail` fields plus the reserved completion value | Unit (documentation contract) |
| TS3 | Every stop point enumerated by FR5 is bound to a reason code, checked bidirectionally against the code set | All nine stop-point keys appear exactly once, each bound code is a member of the code set, and every stop code is used by at least one row | Unit (documentation contract) |
| TS4 | The contract states "no terminal line on a wait turn" and defines a sentinel step value for step-less stops | The `## No line on a wait turn` section states the exclusion; `## Field values` defines the single sentinel and its applicability condition | Unit (documentation contract) |
| TS5 | Regression guard on the Step C completion report | `skills/develop/SKILL.md` still carries the `em-workflow 完了: {feature}` headline, the retained-branch guidance, the PR URL guidance, the `license none` single line and the batch audit items | Unit (documentation contract) |
| TS6 | The contract states that em-workflow performs no status operation against the external task-management service | The `## Responsibility boundary` section states the boundary and the no-confidential-information rule for `detail` | Unit (documentation contract) |
| TS7 | Both manifests parse as JSON, carry a `0.1`-line version with patch greater than 39, and match as strings; each matcher has a negative proof and a non-vacuity guard | Both assertions pass; the forged pre-bump version and the forged mismatched pair are both rejected, and both forged samples parse as well-formed versions | Unit (documentation contract) |
| TS8 | Added modules import the standard library only, the whole suite passes with existing modules unmodified, and the terminal-line prefix appears nowhere incidentally | No third-party import in any added module; suite exit code 0; the prefix literal occurs under `em-workflow/` only inside the contract document's fenced example blocks | Unit (documentation contract) |

### Integrated invariant check

Beyond the unittest suite, the merged tree must satisfy the plugin invariant
checker, which the suite itself executes against the repository root:

- `python3 em-workflow/scripts/check-plugin-invariants.py .` exits 0.
- In particular the `gate_id_coverage`, `stale_references` and
  `agent_dispatch_parity` checks report no offender — the constraints
  IMPLEMENTATION.md D7 imposes on the edits exist to keep this true.

## Code Quality Verification

- Format: none. `project.components.main.format_command` is empty.
- Static analysis: none configured. The plugin invariant checker above is the
  closest equivalent and is covered by the test suite.

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | A terminal line machine-readably distinguishing completion from a stop is defined (single fixed-prefix line, identical format for both) | TS1 |
| SC-2 | The stop terminal line carries the stopping step and the stop reason (closed enum + free-form `detail`) | TS2 |
| SC-3 | The reason-code set is enumerated in the contract document and every FR5 stop point maps to one of them | TS2, TS3 |
| SC-4 | The output contract is stated in `references/batch-mode.md` or the SSOT it points to | TS1 (contract document exists and is pointed at from `batch-mode.md`) |
| SC-5 | The existing success output keeps its format | TS5 |
| SC-6 | The contract explicitly states that no terminal line is emitted on a wait turn | TS4 |
| SC-7 | A fixed sentinel step value is defined for step-less stops | TS4 |
| SC-8 | The documentation contract test is added under `tests/` | TS8 (module discovery) |
| SC-9 | `python3 -m unittest discover -s tests` passes | Test Verification command |
| SC-10 | Both manifests carry the same bumped version | TS7 |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001, task0002 | TS1 |
| FR2 | task0001 | TS2 |
| FR3 | task0001 | TS1 |
| FR4 | task0002 | TS5 |
| FR5 | task0001, task0002 | TS3 |
| FR6 | task0001, task0002 | TS4 |
| FR7 | task0001 | TS6 |
| FR8 | task0001, task0002, task0003 | TS8 |
| FR9 | task0003 | TS7 |
| NFR1 | task0001, task0002, task0003 | TS8 |
| NFR2 | task0001, task0002, task0003 | TS8 |
| NFR3 | task0001 | TS1 |
| NFR4 | task0001, task0002, task0003 | TS7 |
| NFR5 | task0001 | TS8 |
| NFR6 | task0001 | TS2 |
| NFR7 | task0001 | TS2 |

## E2E Testing

The project has no E2E framework and `project.components.main.e2e_test_command`
is empty. No E2E scenario is defined for this feature.

## Manual Testing (E2E Not Possible)

The terminal line's real emission happens inside a live unattended run, which
no automated check in this repository can produce. The following are
human-judgment items:

- [ ] Run `/em-workflow:develop --batch` on a small throwaway feature to
      normal completion; confirm the final assistant message's last line
      carries the terminal line with terminal state `completed`, and that the
      pre-existing completion report lines above it are unchanged (FR1, FR4).
- [ ] Force a terminating stop (e.g. leave a step `failed`); confirm the final
      message's last line carries terminal state `stopped`, a step value and a
      reason code drawn from the contract's closed set, plus a human-readable
      detail (FR2, FR5).
- [ ] Confirm a turn that ends waiting for an implementer notification emits
      no terminal line, and that the run resumes normally afterwards (FR6).
- [ ] Read the emitted `detail` values and confirm they carry nothing
      confidential beyond paths, since the line reaches a human reviewer
      through an external service (NFR6).
- [ ] Search a real unattended-run log for the prefix and confirm it matches
      only the emitted terminal line — no incidental prose match (NFR5).

No mockup comparison item applies: the `design` step is `skipped` and the
feature has no visual surface.

## Performance / Security Verification

- NFR6 (`detail` carries no confidential information): verified by the
  contract statement (TS6) and by the manual detail-review item above.
- FR7 (external-service boundary): verified by TS6 — the contract states that
  em-workflow performs no status operation against the external service, and
  no task in this feature adds one.
- No performance requirement applies; the feature adds one line of text
  output and no external tool invocation (NFR3).

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios (TS1-TS8) | 8 | 8 | 0 | 0 |
| Success criteria (SC-1..SC-10) | 10 | 10 | 0 | 0 |
| Integrated invariant check | 1 | 1 | 0 | 0 |
| Manual verification items | 5 | 0 | 0 | 5 |
| **Total** | **24** | **19** | **0** | **5** |
