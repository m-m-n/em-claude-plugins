# Implementation Plan: divergence-fail-open-wording

## Overview

Reword the I.2.a divergence paragraph and add a note to I.2.b step 1 in
`em-workflow/references/implement-phase.md` so that both agree with the
document's own fail-open definition and with each other, re-pin the new
wording in `tests/test_recycled_task_id_consistency.py`, and bump em-workflow
to 0.2.8. The whole change is delivered as a single task (task0001).

## Technology Stack

- **Markdown** - the reference document being reworded (`implement-phase.md`)
- **Python 3 standard library unittest** - the phrase-pinning test module
  (run from the repository root with `python3 -m unittest discover -s tests`)
- **JSON** - the plugin manifests carrying the em-workflow version
  (`em-workflow/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`)
- **New dependencies**: none. `project.license` is `none`; no dependency
  license needs recording.

## Layer Structure

Not applicable in the layered-architecture sense. The three artifact groups
have one dependency direction only:

| Artifact | Depends on | Notes |
|----------|-----------|-------|
| `implement-phase.md` (I.2.a, I.2.b) | nothing | Source of the wording |
| `test_recycled_task_id_consistency.py` | `implement-phase.md` text | Pins phrases of I.2.a / I.2.b and holds pre-change samples |
| `plugin.json` / `marketplace.json` | nothing | Version parity is checked by the existing parity test |

## Shared Components

None. The plan has exactly one task, so no component, file or contract is
shared between tasks.

## Conventions

- **Phrase pinning**: pinned phrases are compared after whitespace
  normalization against a section extracted by heading, following the
  existing pattern of the test module. Pinned phrase constants keep their
  names when only their value changes.
- **Pre-change samples**: a negative proof is run against a verbatim copy of
  the document text at a named commit, never against retyped or reflowed
  text. Every such sample carries a self-check asserting that it contains
  an expected old phrase, so an empty or wrong sample cannot make the
  negative proof pass vacuously.
- **Terminology**: "fail-open" is used only in the sense defined by the
  Supporting cast section of `implement-phase.md` (on an unexpected state a
  hook exits 0 silently). A hook behavior that blocks the turn (exit 2) is
  never described as fail-open.
- **Version bump**: a change under `em-workflow/` raises
  `em-workflow/.claude-plugin/plugin.json` and the em-workflow entry of
  `.claude-plugin/marketplace.json` to the same value in the same change;
  other plugins' versions are not touched.

## Cross-task Design Decisions

### D1: Single task

- **Decision**: FR1 through FR5 (and NFR1 through NFR3) are implemented by one
  task, task0001.
- **Rationale**: the test module pins the exact wording written for FR1-FR3,
  so FR4 cannot be implemented without that wording; splitting into
  parallel tasks would require fixing the prose itself here as a cross-task
  contract. The version bump must land in the same change as the document
  edit.
- **Affected tasks**: task0001.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Renaming the fail-open-named test method breaks the old-name reference in `test-docs/recycled-task-id-contract/task0001.tests.yaml` | Low | Low | That file is not edited; if the full suite fails for that reason alone, the rename is reverted and the old name kept (SPEC A5) |
| A pre-change sample is not a verbatim copy, so a negative proof passes vacuously | Low | Medium | Sample self-check assertions (SPEC A8) |
| The rewrite drops or splits one of the four already-pinned phrases | Medium | Low | Existing pins fail in the full suite (NFR2) |
| New sentences land outside the span checked for "fail-open" | Low | Medium | Task acceptance criteria assert that every new phrase lies inside that span |
| The em-workflow version on the integration branch is no longer 0.2.7 at implementation time | Low | Low | Reported as a plan deviation instead of choosing a different value |

## Open Questions

- None.
