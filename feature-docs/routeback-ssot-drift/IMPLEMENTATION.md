# Implementation Plan: routeback-ssot-drift

## Overview

Aligns the agent index (`agents.jsonl`) paragraph of
`em-workflow/references/workflow-schema.md` and the module docstring of
`em-workflow/hooks/queue_agent_index.py` with
`em-workflow/references/implement-phase.md` (readers, purpose, behavior when
absent, the two "ambiguous" conditions), pins the already-defined I.2.b step 1
partial-artifact and third-case Residual outcomes, and raises the version
lockstep baseline to (0, 2, 10) together with the em-workflow bump to 0.2.11.
No runtime behavior changes (NFR3).

## Technology Stack

- **Language / Framework**: Python 3 standard library `unittest` (tests),
  Markdown (protocol documents), JSON (plugin / marketplace manifests)
- **Test command**: `python3 -m unittest discover -s tests`, run from the
  worktree root
- **New dependencies**: none. `project.license` is `none`; no license record
  is required because no dependency is introduced.

## Layer Structure

Not applicable. The feature edits documentation, one module docstring, tests
and version manifests only. Document ownership, which both tasks rely on:

- `implement-phase.md` owns the rules (I.2.b step 1 Recovery / Residual block,
  the Supporting cast Agent index writer bullet and its Orchestrator-side
  read, the SubagentStop failure net and stop-tool recorder bullets).
- `workflow-schema.md` and the `queue_agent_index.py` docstring describe the
  agent index by citing those owners, never by restating their rules.

## Shared Components

The two tasks share no code and no test helper; their file sets are
disjoint. The only shared element is a read-only document anchor.

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| `em-workflow/references/implement-phase.md` (read-only anchor) | Owns the I.2.b step 1 Recovery / Residual block, the Orchestrator-side read, and the Supporting cast hook bullets that the schema paragraph cites and the retention tests pin | Pre: text as at the task's base commit. Post: byte-identical at the end of the feature; no task modifies it (D2). Section boundaries used by tests: the I.2.b section runs from the heading `### I.2.b: Wake phase` up to the heading `### I.2.c: Failed handling`; the Supporting cast section runs from the heading starting `### Supporting cast` up to the heading `## Step I.3: Phase completion` | task0001 (cites it from workflow-schema.md and the docstring), task0002 (pins its I.2.b sentences) |

## Conventions

- **Test modules**: standard library only; discovered by the test command
  above; each task creates its own new module named after the feature slug
  and never imports another task's module. Each module locates files
  relative to the repository root derived from its own location, as the
  existing modules under `tests/` do.
- **Text normalization**: document assertions compare against a copy in
  which every whitespace run (including line-wrap newlines) is collapsed to
  one space, so line wrapping never breaks an assertion.
- **Assertion scope**: presence assertions are scoped to the paragraph or
  section they are about (so a phrase appearing elsewhere in the file cannot
  satisfy them); absence assertions for removed phrases run over the whole
  file.
- **Negative proofs** (repository convention for document-contract tests):
  - every absence assertion is paired with a proof that its matcher flags a
    verbatim excerpt of the pre-change text, plus a non-vacuity guard showing
    the excerpt really contains the removed phrase;
  - every presence assertion for new wording is shown to fail against the
    same pre-change excerpt;
  - every retention assertion (text that already exists and must stay) is
    shown to fail against a copy of its section with the pinned sentence
    removed.
  Pre-change excerpts are copied verbatim from the file as it stands at the
  task's base commit, before the task edits anything. Each new module's
  docstring lists its matcher → negative-proof inventory.
- **Pinned literals**: each pinned phrase is defined once as a module-level
  constant and referenced by name; it is never spelled twice.
- **Citation over restatement**: new prose cites the owning document and
  section by name. The only definitional text allowed outside the owner is
  what SPEC FR4 requires (the two one-line "ambiguous" definitions).

## Cross-task Design Decisions

### D1: One task owns every `em-workflow/` edit and the version bump

- **Decision**: task0001 carries the `workflow-schema.md` paragraph, the
  `queue_agent_index.py` docstring, both version manifests and the lockstep
  baseline in `tests/test_implement_routeback_gate.py`. task0002 creates one
  new module under `tests/` and touches nothing under `em-workflow/`.
- **Rationale**: the repository rule requires any change under
  `em-workflow/` to bump `em-workflow/.claude-plugin/plugin.json` and the
  em-workflow entry of `.claude-plugin/marketplace.json` in the same change,
  and a commit guard enforces it at commit time. The raised baseline
  (strictly greater than (0, 2, 10)) is only green once both manifests read
  0.2.11. Tasks run fully in parallel, so splitting any of these across tasks
  would leave one task either red or unbumped.
- **Affected tasks**: task0001 (owner), task0002 (stays outside
  `em-workflow/` and outside both manifests).

### D2: `implement-phase.md` is frozen for this feature

- **Decision**: no task edits `implement-phase.md`. FR4 requires its
  orchestrator-side "ambiguous" wording unchanged, and FR6 / FR7 are already
  defined at the base revision (SPEC A1): they are pinned, not rewritten. A
  task that finds it must edit this file reports a plan deviation instead.
- **Affected tasks**: task0001, task0002.

### D3: Disjoint test files

- **Decision**: task0001 creates `tests/test_routeback_ssot_drift_agent_index.py`
  and edits only the `TestPluginVersionBumpedInLockstep` class of
  `tests/test_implement_routeback_gate.py`; task0002 creates
  `tests/test_routeback_ssot_drift_i2b_retention.py`. No test file is touched
  by both tasks. `tests/test_routeback_residual_connections_version_bump.py`
  is touched by neither (its (0, 2, 0) baseline stays, FR8).
- **Affected tasks**: task0001, task0002.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Rewording the agents.jsonl paragraph drops a phrase that existing tests pin (NFR2) | Medium | High (suite red) | task0001 keeps every NFR2 phrase verbatim (listed in its plan) and runs the full suite before merging |
| The token `stale-agent-entry` is introduced into `workflow-schema.md` while describing orphan recovery | Low | Medium (an existing test asserts its absence there) | task0001 describes only the no-entry case with `no-agent-entry`; its plan states the prohibition |
| A test module not read during planning pins a removed phrase or the old docstring sentence | Low | Medium | Full suite run in each task; a newly failing pin of a removed phrase is reported as a plan deviation |
| An `em-workflow/` commit without a version bump is rejected by the commit guard, stalling an unattended run | Low (after D1) | High | D1 |
| A retention test that passes on any text (vacuous) | Low | Medium | Non-vacuity proofs per Conventions |

## Open Questions

- None.
