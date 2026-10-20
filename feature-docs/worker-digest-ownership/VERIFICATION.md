# Verification Document: worker-digest-ownership

## Overview

**Feature**: worker-digest-ownership / **SPEC.md**:
`feature-docs/worker-digest-ownership/SPEC.md` / **IMPLEMENTATION.md**:
`feature-docs/worker-digest-ownership/IMPLEMENTATION.md`

Scenario IDs use the `TSn` form so they string-match SPEC.md and
workflow.yaml (IMPLEMENTATION.md D7). TS1–TS8 come from SPEC.md; TS9–TS12
are added here for SPEC.md's integration test, NFR2, NFR3 and FR4's
document content.

## Build Verification

- Command: none (`project.components.main.build_command` is empty; the
  feature is Python scripts and Markdown).
- Expected: not applicable.

## Test Verification

- Command: `python3 -m unittest discover -s tests`
- Expected: exit code 0, every test passing (skips only with a stated reason,
  e.g. a permission case under root).
- Coverage target: not measured (the project has no coverage tool); every
  Acceptance Criterion maps to at least one test.
- The repository-level invariant run (`check-plugin-invariants.py` against
  the repository root, including the two new checks) is part of this suite
  (`tests/test_check_plugin_invariants.py`), so no separate command is run.

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS1 | `worker_digest_stance` derives the target workers from worker-envelope.md's Applicability table and the agents' frontmatter tools, and checks each target's prompt and cited contracts (FR1, FR6) | Passes on the real repository; fails on synthetic trees where a target's citation is missing, a cited contract lacks the envelope citation, an owner stance sentence is removed, or a worker-directed digest instruction appears | Unit |
| TS2 | `dispatch_digest_wiring` checks that every registered dispatch site cites the owner document's procedures, that the owner names the `artifact-digest.py` invocation, and that no site names `git hash-object` (FR3, FR4, FR7) | Passes on the real repository; fails on synthetic trees with a citation removed, owner missing, invocation missing, empty registry, missing heading, `git hash-object` in a site, or a worker lacking a layer-5 row; create-plan-phase.md has no `git hash-object` | Unit |
| TS3 | create-spec-phase.md's Pre-dispatch snapshot row and §10 Artifact digests cite the owner and do not name `git hash-object`; the post-dispatch blob-id sentence remains; the owner document's `Legacy records` holds the FR8 rule (FR2, FR8) | All assertions hold | Unit |
| TS4 | `validate-worker-output.py --kind phase-state` with `phase: design` and with an unknown phase; worker-envelope.md and phase-state.md list `design` (FR5) | `design` accepted (exit 0); unknown phase rejected (exit 1); both documents list `design` | Unit |
| TS5 | `validate-worker-output.py --kind worker-result` on each derived worker's completed fixture with `written_artifacts[].sha256` null and omitted (FR1, FR6) | Both variants accepted (exit 0) for every derived worker; derived set non-empty; control variant rejected | Unit |
| TS6 | `artifact-digest.py` on known contents, several paths, hyphen-leading paths, paths with spaces and Japanese characters (FR7) | Known test-vector digests as `sha256:` + 64 lowercase hex; one element per argument in order; hyphen paths hashed as files; non-ASCII paths echoed unescaped | Unit |
| TS7 | `artifact-digest.py` on a missing path, an unreadable file and non-regular entries (FR7) | `missing` / `unreadable` / `not_a_regular_file` elements, exit 1, other elements still hashed, no blocking | Unit |
| TS8 | `worker_digest_stance` on synthetic trees with zero target workers (FR6) | The check fails | Unit |
| TS9 | The whole test suite, including the existing wording and byte pins listed in SPEC.md NFR1 (NFR1) | Exit code 0 | Integration |
| TS10 | The digest script and the new or extended test modules import only standard-library modules; the script starts no external command (NFR3) | Script: asserted by `tests/test_artifact_digest_script.py`; test modules: their import lines name only standard-library modules | Unit + Integration review |
| TS11 | Dispatch sites, phase-state.md and worker-envelope.md cite `references/artifact-digest.md` and do not restate its definition or procedures; spec-writer-contract.md names every dispatch site through it (NFR2, FR3) | Citations present; no restatement | Unit |
| TS12 | develop SKILL.md 「design ステップ分岐」 states pre-dispatch verification, layer 4 + layer-5 recording into `phase-state/design.yaml`, the `replace_own` decision against design.yaml, the design.yaml-absent route to `design.artifact-overwrite`, and the skipped case (FR4) | All statements present; existing pinned phrases intact | Unit |

## Code Quality Verification

- Format: none configured (`format_command` is empty).
- Static analysis: none configured.

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC1 | All functional requirements are implemented and tested | Functional Requirements Coverage below; TS1–TS8, TS11, TS12 |
| SC2 | All test scenarios pass | TS9 |
| SC3 | Documentation is complete | TS3, TS11, TS12; the owner document's six sections exist (TS2) |
| SC4 | Code review is completed | Review phase result |
| SC5 | `python3 -m unittest discover -s tests` passes in full (NFR1) | TS9 |
| AC1 | create-spec re-entry: spec-writer with `replace_own` does not return `blocked` for digests and returns path-only `written_artifacts` | TS1, TS5 (automated); Manual Testing item 1 |
| AC2 | designer with existing outputs does not block on digests; the orchestrator verifies, validates and records into `phase-state/design.yaml` | TS1, TS5, TS12 |
| AC3 | Every dispatch site skips dispatch on an `expect_digest` mismatch | TS2, TS11 |
| AC4 | One digest definition and one calculation script for all three uses; create-spec-phase.md no longer names `git hash-object` for them; other identifiers unchanged | TS3, TS6 |
| AC5 | New checks pass on the repository and fail on negative trees; validator and script tests exist; suite passes | TS1, TS2, TS5, TS8, TS9 |
| AC6 | Script outputs and exit codes for all defined cases | TS6, TS7 |
| AC7 | Legacy records: confirmed matches are matches, others go to `{phase}.artifact-overwrite` | TS3 |
| AC8 | design.yaml-absent handling written in 「design ステップ分岐」 | TS12 |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0004 | TS1, TS5 |
| FR2 | task0002, task0003 | TS3 |
| FR3 | task0002, task0003 | TS2, TS11 |
| FR4 | task0002 | TS2, TS12 |
| FR5 | task0003 | TS4 |
| FR6 | task0001, task0002, task0003, task0004 | TS1, TS2, TS4, TS5, TS6, TS7, TS8 |
| FR7 | task0001, task0002 | TS2, TS6, TS7 |
| FR8 | task0002, task0003 | TS3 |
| NFR1 | task0001, task0002, task0003, task0004 | TS9 |
| NFR2 | task0002, task0003, task0004 | TS11 |
| NFR3 | task0001, task0002, task0003, task0004 | TS10 |

## Manual Testing (E2E Not Possible)

Agent runtime behaviour is not executed from unit tests (SPEC.md A5).

- [ ] 1. Reproduction (完了の定義): on a feature whose create-spec has
      completed, re-enter create-spec with REQUIREMENTS.md / SPEC.md as
      `replace_own` targets; spec-writer writes both and returns `completed`
      with path-only `written_artifacts`, and the orchestrator records both
      digests in `phase-state/create-spec.yaml` via `artifact-digest.py`.
- [ ] 2. The workers named in the owner document's `Dispatch sites` registry
      include every worker the `worker_digest_stance` derivation returns for
      the repository (IMPLEMENTATION.md D5, Open Questions).
- [ ] 3. Read-through: following any dispatch site's citation reaches
      `references/artifact-digest.md` and, from its `Calculation` section,
      the `scripts/artifact-digest.py` path that the script tests execute.

## Performance / Security Verification

- TM-1: each target path is passed as one single-quoted word and a path with
  a single quote, line break or NUL is never put into a command — asserted on
  the owner document's `Calculation` section by
  `tests/test_artifact_digest_docs.py`.
- TM-2: layer 5 never uses a worker-supplied `sha256` and records only
  script-computed digests — asserted on `Layer 5 recording` by
  `tests/test_artifact_digest_docs.py`.
- TM-3: a legacy record counts as a match only by equality with the current
  file's git blob id, never by length or format — asserted on
  `Legacy records` by `tests/test_artifact_digest_docs.py`.
- TM-4: with `phase-state/design.yaml` absent, existing DESIGN.md / mockups
  go to `design.artifact-overwrite` (batch: batch-policies.yaml) — asserted on
  「design ステップ分岐」 by `tests/test_artifact_digest_docs.py`.
- TM-5: pre-dispatch verification runs after the snapshot and immediately
  before dispatch at every site — asserted on `Pre-dispatch verification`
  by `tests/test_artifact_digest_docs.py`, and the sites' citations by
  `dispatch_digest_wiring` (TS2).
- TM-6: the script reads only regular files, follows no symlink and never
  blocks — `tests/test_artifact_digest_script.py` (directory, symlink,
  dangling symlink, FIFO under a timeout).
- Performance: not applicable (SPEC.md); the script reads in bounded chunks.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS1–TS12) | 12 | 12 | 0 | 0 |
| Success criteria (SC1–SC5, AC1–AC8) | 13 | 11 | 0 | 2 (SC4 by the review phase, AC1's reproduction) |
| Requirements coverage | 11 | 11 | 0 | 0 |
| Manual items | 3 | 0 | 0 | 3 |
| Security (TM-1–TM-6) | 6 | 6 | 0 | 0 |
