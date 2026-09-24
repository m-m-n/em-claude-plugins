# Implementation Plan: routeback-residual-connections

## Overview

Close the three connections left unproven in `em-workflow/references/implement-phase.md`
Step I.2.a / Step I.2.c after PR #7 (PR #7 verify items MANUAL-1 / MANUAL-2 / MANUAL-3),
pin each connection with document-contract tests, and bump em-workflow from 0.2.0 to
0.2.1. Documentation and tests only: no runtime behaviour changes (NFR1). One task
(task0001) carries the whole change. The decisions below also bind any later rework
task that touches the same files.

## Technology Stack

- **Protocol text**: Markdown, `em-workflow/references/implement-phase.md`. This is the
  implement phase's SSOT for the route-back path.
- **Tests**: Python 3 standard library `unittest`, discovered by
  `python3 -m unittest discover -s tests` from the repository root (NFR9).
- **Manifests**: JSON, `em-workflow/.claude-plugin/plugin.json` and
  `.claude-plugin/marketplace.json`. Only the version field changes.
- **New dependencies**: none. No license to record (`project.license: none`).

## Layer Structure

| Layer | Content | May depend on |
|-------|---------|---------------|
| L1 Protocol text | `implement-phase.md` Step I.2.a / Step I.2.c prose | Other SSOTs by citation only: Step I.2.b step 1 / step 3, `references/workflow-patch.md` `replace_all` permission conditions, `em-workflow/scripts/merge-task.sh` journal-write behaviour |
| L2 Document-contract tests | `tests/*.py` modules that read L1 (or L3) as data | L1, L3. Never the reverse, and never another test module's constants |
| L3 Distribution manifests | em-workflow version in both manifests | None |

L1 cites an owning rule and never restates it (NFR8).

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| Pinned-literal registry | The existing literal, ordering and count assertions that three test modules make over `implement-phase.md`: `tests/test_recycled_task_id_consistency.py`, `tests/test_implement_routeback_gate.py`, and the pre-existing part of `tests/test_routeback_reset_scope_consistency.py` | Pre: all pass on the integration base. Post: all still pass after any L1 edit, with the first two modules byte-identical (edit-forbidden, NFR2) and no pre-existing assertion of the third module changed (NFR3). An L1 edit that would need one of these assertions changed is a plan deviation to report. It is never a license to edit the assertion. | task0001 |
| Section slicing | Tests locate sections by heading text. I.2.a runs from the heading "### I.2.a: Launch phase" to "### I.2.b: Wake phase". I.2.c runs from "### I.2.c: Failed handling" to "### Supporting cast". | Headings stay byte-identical. New prose never adds a second occurrence of any heading. | task0001 |
| Normalized vs raw comparison | Content assertions run on a whitespace-normalized copy of a section (every whitespace run collapses to one space). Byte-identity and line-wrap-survival assertions run on raw text. | A new assertion states which form it uses, and the two forms are never mixed in one assertion. | task0001 |

## Conventions

- **C1. Text-identified sites.** Edit sites and test anchors are found by text, never by
  line number (SPEC A-6).
- **C2. Cite, do not restate (NFR8).** A new sentence names its owning rule (Step I.2.b
  step 3, `references/workflow-patch.md`'s `replace_all` permission conditions,
  merge-task.sh's journal-write behaviour) and adds only the content the requirement
  itself demands.
- **C3. Forbidden substrings in normalized I.2.c (NFR4).** Neither "append" nor "rework"
  may appear. This rules out "journal append", "appended", "reworked", and merge-task.sh's
  journal-writing function name, which contains "append".
- **C4. Direction words.** From I.2.a, Step I.2.b and Step I.2.c are "below", never
  "above". Inside I.2.c, the route-back gate is "above" the write set and the cleanup.
- **C5. Line layout.** Protected raw line-wrap literals are never reflowed. Only lines
  that are actually edited are re-wrapped, at the surrounding width and continuation
  indent. After stripping indentation and backticks, no line of `implement-phase.md` may
  start with `git ` and contain `commit` or `add -A` (NFR7). Prose naming
  `git update-ref` keeps it in mid-line.
- **C6. Matcher discipline (the existing module's D8 style).**
  - Every literal that asserts new wording is one module-level constant, read by both its
    positive assertion and its negative proof.
  - Every negative proof runs against a pre-change excerpt copied verbatim from a named
    git revision, with its raw line breaks kept.
  - Every excerpt has a non-vacuity guard. The guard asserts a retained anchor that
    appears in both the excerpt and the live document and that no other test module
    asserts absent.
  - The module docstring lists every new matcher with its proof and records the capture
    revision.
- **C7. Additive test edits.** In `tests/test_routeback_reset_scope_consistency.py`,
  existing constants, test methods and classes stay byte-identical. New material goes in
  as new constants, new classes, and an appended docstring section.
- **C8. Version bump coupling.** Both manifests carry the identical em-workflow version.
  The bump lands in the same commit as the `implement-phase.md` edit, per
  `.claude/rules/core-plugin-version-bump.md`. A local commit guard may enforce this per
  commit, so every change under `em-workflow/` plus `.claude-plugin/marketplace.json` is
  staged into one commit. Files under `tests/` may be committed separately.

## Cross-task Design Decisions

### D1. One task

The `implement-phase.md` edit and the version bump have to share a commit (C8). All new
document-contract assertions go into one existing module (SPEC A-5). Two tasks would
either split the bump from the edit it versions, or edit the same module's docstring and
constant region at the same time. Affected: task0001.

### D2. MANUAL-2 is closed by documenting the residual

The window where a merge landed but its journal event did not is recorded in the text as
a known residual. No per-candidate ancestor check is added before cleanup (SPEC A-1). No
runtime behaviour changes (NFR1). Affected: task0001.

### D3. FR1 is a pin, not an edit

The I.2.a premise already reads `below` and names the I.2.c conjunct that blocks on a
journal `merged` (SPEC A-2). The premise sentence is not re-edited. The FR1 negative
proof reuses the module's existing pre-change sample that carries
"(the widened I.2.c gate above)", captured at `b3d8824da4182071c2a5d7490925fee1aba951e1`.
At the FR2–FR5 capture revision below, the FR1 wording already holds, so that revision
cannot supply the proof. Affected: task0001.

### D4. Capture revision for FR2–FR5

The FR2–FR5 negative proofs run against excerpts of `implement-phase.md` copied verbatim
from revision `9f9502487a8da29220aece87f253058becda432e`. They come from the git object
store, not from the working tree, and are never paraphrased. If that revision cannot be
read, report a deviation and do not substitute another revision. Affected: task0001.

### D5. Version test placement

TS-5 goes in a new module, `tests/test_routeback_residual_connections_version_bump.py`.
Keeping it out of the document-contract module keeps that module reading only
`implement-phase.md`. The new module follows the repository's durable version-test form:

- the version is strictly greater than a pre-task baseline, by per-component numeric
  comparison;
- the two manifests hold equal versions;
- no literal version is pinned.

Affected: task0001.

### D6. Version value

em-workflow goes from 0.2.0 to 0.2.1 (patch: a documentation fix that clarifies
behaviour). No other plugin's version moves. This supersedes the "no further version
bump" item of routeback-reset-scope-consistency D9 (SPEC A-4). Affected: task0001.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| A new sentence breaks an anchor held by an edit-forbidden module. Examples: a second "Because " or " so " inside the I.2.a single-causal span; an earlier `tasks.{T}.status` in I.2.c; a second `git branch -D`. | Medium | High: the suite goes red, and the forbidden module cannot be adjusted | The task plan lists every anchor. Run the full suite before each commit. |
| Natural wording brings in "append" or "rework" (for example "appended", or the merge-task.sh function name) | Medium | High | C3 |
| A new claim overstates what the path verifies, repeating the MANUAL-2 defect | Medium | Medium | Limit the claim to the two sources. Manual check MANUAL-2 in VERIFICATION.md. |
| The FR2 sentence reads as contradicting the I.2.c `in_progress` half's "with the recycled-task-id carve-out that step already defines" | Medium | Medium | Phrase FR2 in terms of the carve-out's domain: it acts only on `failed` last events, so its outcome cannot change a `merged` or in-flight classification. |
| Revision `9f95024` cannot be read in the task worktree | Low | Medium | D4: report a deviation, never substitute. |
| Version-bump modules outside the scan set assume a different shape (SPEC A-8) | Low | Medium | The full-suite run in TS-6 catches it. |

## Open Questions

- [ ] EC-3: Step I.2.c's cleanup does not say how its worktree / branch removal behaves
  for a reset task that has no worktree or branch. Such a task enters the reset set only
  through workflow.yaml `status: failed`. A runtime change is out of scope (NFR1), so
  this is recorded and no action is taken in this feature.
