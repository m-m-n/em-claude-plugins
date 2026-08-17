# Implementation Plan: abort-phase-terminal

## Overview

Make implement-phase.md Step I.2.c's `- **abort phase**` option (and the
section's batch-mode second-failure abort) prescribe the same explicit
refresh / `implement: failed` write / `commit-docs.sh` / report terminal the
rejected path already prescribes, and synchronize batch-mode.md's
`implement.failed-task` row with it. The work splits into two tasks along a
strict single-writer-per-file line, because the batch-mode paragraph is
pinned byte-identically in three test modules.

## Technology Stack

- **Documents**: Markdown protocol references under `em-workflow/references/`
  (agent-facing SSOT prose — the deliverable itself).
- **Tests**: Python standard-library `unittest` (Python 3.14), run as
  `python3 -m unittest discover -s tests` from the repository root. No
  third-party package is imported by test code (`test/README.md`).
- **Manifests**: JSON plugin/marketplace manifests (version fields only).
- **New dependencies**: none. This feature introduces no library, so there
  is no new license to record; `project.license` is `none` and stays `none`.

## Layer Structure

This feature has no runtime component. The layering is documentary, and the
dependency direction below must not be inverted:

| Layer | Members | May depend on |
|---|---|---|
| Protocol SSOT | `em-workflow/references/implement-phase.md` (owns the abort terminal), `em-workflow/references/batch-mode.md` (restates it for batch and points back for full detail) | batch-mode.md cites implement-phase.md; implement-phase.md never depends on batch-mode.md for the terminal's definition |
| Pin / contract tests | `tests/test_implement_routeback_gate.py`, `tests/test_recycled_task_id_consistency.py`, `tests/test_routeback_reset_scope_consistency.py`, plus one new module for the batch-mode.md row | the documents above (one-way: documents never reference tests) |
| Packaging | `em-workflow/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` | nothing |

**Frozen — no task may create, modify or delete these**:
`em-workflow/skills/develop/SKILL.md`,
`em-workflow/references/workflow-patch.md`,
`em-workflow/scripts/validate-worker-output.py`,
`em-workflow/scripts/commit-docs.sh`, `em-workflow/hooks/**`,
`tests/test_batch_policies.py`, and
`feature-docs/routeback-gate-postcondition/SPEC.md`.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|---|---|---|---|
| **SC-1 Abort terminal** | The single ordered procedure that every abort call site and batch-mode.md's row must describe | **Pre**: a task's reconciled status is `failed` and the abort choice is taken — interactively via the option, or in batch on a second failure of the SAME task. **Post**, in this order: (1) the integration worktree is refreshed to the integration branch (the same `reset --hard em-workflow/{feature}/integration` the rejected path uses), (2) the resulting tip is captured into a variable (mirroring the rejected path's `rev-parse HEAD` capture), (3) the `implement` step's `status` is set to `failed` in workflow.yaml, (4) exactly that write is committed through `commit-docs.sh` with the integration worktree as first argument, a `docs({feature}): …` message as second, and the captured tip as third, (5) the phase reports and stops; control returns via develop's stop condition 3, which fires on the NEXT Step B iteration reading `implement: failed`. **Excluded side effects (exhaustive)**: no `create-plan` `needs_update`, no `tasks.{T}.status` reset, no `tasks.{T}.notes` failure-reason write set, no worktree removal, no branch deletion, no route-back commit — the terminal status write and its own commit are the ONLY side effect. **Failure**: a `commit-docs.sh` exit 4 at this call site takes the Branch & Worktree Model's bounded recovery (refresh, re-capture the tip, re-apply the same transition re-derived from source, retry once; a second exit 4 stops the phase with a report); this call site is NEVER added to the single carve-out, which stays exactly Step I.2.c's route-back commit | task0001 (writes it into implement-phase.md's abort bullet and its batch-mode paragraph), task0002 (restates it in batch-mode.md's `implement.failed-task` row) |
| **SC-2 I.2.c batch-mode paragraph and its byte pins** | The exact bytes of the paragraph that closes the I.2.c section, and the three test literals that mirror it | **Pre**: the paragraph begins with the marker `` Batch mode (`references/batch-mode.md` `` and is the final content of the `### I.2.c: Failed handling` section (nothing follows it before `### Supporting cast`), ending with exactly one blank line before that heading. **Post**: each of the three pin literals equals, byte for byte, the section slice from that marker to the section end — including line wrapping and the trailing blank line. **Ownership**: task0001 exclusively produces both the paragraph and all three literals; no other task modifies implement-phase.md or those three modules, so no cross-task byte agreement has to be negotiated | task0001 (sole writer); task0002 (must not touch) |
| **SC-3 Plugin version 0.1.44** | The lockstep version value | **Pre**: both manifests currently read `0.1.43`. **Post**: `em-workflow/.claude-plugin/plugin.json`'s `version` and the `em-workflow` entry's `version` in root `.claude-plugin/marketplace.json` both read `0.1.44`; the two values never diverge. The existing lockstep assertion (equality; `(major, minor) == (0, 1)`; patch strictly greater than 42) already accepts this value, so no test module needs editing for it | task0002 (sole writer); task0001 (must not touch the manifests) |
| **SC-4 File ownership map** | Which task may write which path | task0001: `em-workflow/references/implement-phase.md`, `tests/test_implement_routeback_gate.py`, `tests/test_recycled_task_id_consistency.py`, `tests/test_routeback_reset_scope_consistency.py`. task0002: `em-workflow/references/batch-mode.md`, `tests/test_abort_phase_terminal_batch_mode.py` (new), `em-workflow/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`. No path appears under two owners; a task that believes it needs a path outside its own list reports a plan deviation instead of writing it | both |

## Conventions

- **Single writer per file**: every path in SC-4 has exactly one owning task.
  Since tasks run fully in parallel and merge into one integration branch,
  this is what keeps the byte pins consistent without cross-task negotiation.
- **Commits only through `commit-docs.sh`**: every commit any new prose
  prescribes goes through that helper. A bare `git commit` or `git add` line
  anywhere in implement-phase.md fails a whole-file scan (NFR3).
- **Forbidden substrings inside the I.2.c section**: the normalized section
  must contain neither `rework` nor `append`, in any inflection. New abort
  wording is written around them (existing tests enforce this).
- **Structural anchors are load-bearing**: `### I.2.c: Failed handling` and
  the option opener `- **abort phase**` are used as slice anchors by test
  modules; they stay byte-identical. Likewise the rejected-path marker
  `When the gate does not hold` and the paragraph beginning
  `There is NO skip option:` stay in place.
- **Terminal wording is restated, not copied, across documents**: batch-mode.md's
  row describes SC-1 in its own row-sized wording. No byte identity is
  required between the two documents — only non-contradiction (NFR6).
- **New test placement**: task0001 adds its assertions to the three modules
  it already owns (their section-slice helpers are already there).
  task0002 adds a new module rather than editing `tests/test_batch_policies.py`,
  which must stay green unmodified.
- **Commit message for the abort commit**: left to implementation, but it
  must be distinguishable in history from the rejected path's
  `docs({feature}): implement route-back gate rejected`. No test pins it.

## Cross-task Design Decisions

### D1 — implement-phase.md and all three byte pins belong to ONE task

The three pin literals must equal the SAME final paragraph text. Tasks run
fully in parallel in separate worktrees, so a decomposition that lets one
task write the paragraph and another write a pin would require the two to
agree on bytes they cannot see. Assigning the paragraph and all three
literals to task0001 removes the coupling entirely instead of managing it.
The same argument extends to the other two edit sites in implement-phase.md
(the abort bullet and the Branch & Worktree Model exit-4 bullet): both go to
task0001, so the file has exactly one writer. Affected: task0001, task0002.

### D2 — batch-mode.md's row is a restatement bound by SC-1, not a copy

task0002 cannot read task0001's plan, so it implements SC-1's contract text
directly. Its row must describe the write-and-commit terminal and retain the
row's gate id `implement.failed-task`, its `Auto-select **retry** once per
task` clause, its `Route-back-to-planning is never taken automatically`
clause, and its `` Full detail: `references/implement-phase.md` Step I.2.c ``
pointer, so the existing batch-policy test's gate-id list and its
(description, keyword) pairing keep matching. Affected: task0001, task0002.

### D3 — the version bump rides with task0002 and needs no test edit

The lockstep assertion lives in a module task0001 owns, and it is already
satisfied by `0.1.44` (equality plus patch > 42), so task0002 changes only
the two manifests. This keeps the manifests off task0001's file list and
keeps the test module off task0002's. Affected: task0001, task0002.

### D4 — task0001 carries more acceptance criteria than the usual guidance

task0001 has eight acceptance criteria, above the ~7 rule of thumb. The
split that would reduce it puts two tasks on one file and one byte-pin set,
which D1 rejects as strictly worse. The criteria are accepted as-is.

### D5 — no dependency, therefore no license decision

No task adds a library, a package manifest, or a vendored file. Nothing is
recorded against `project.license` (`none`), and no license question arises.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| A pin literal drifts from the paragraph by one character (wrap position, trailing blank line, non-ASCII arrow) | Medium | High — the suite goes red and the feature cannot land | SC-2: one task owns the paragraph and all three literals, and re-derives each literal from the final document bytes after the prose is settled, never from memory |
| New abort wording introduces a forbidden substring (`rework` / `append`) into the I.2.c section | Medium | Medium — an existing test goes red | Convention above; task0001's acceptance criteria assert absence explicitly |
| The batch-mode paragraph stops being the section's last content (a new sentence appended after it) | Low | High — all three pins fail at once | SC-2 states the position invariant; task0001 asserts it on the raw slice |
| batch-mode.md's row loses a retained clause and breaks the batch-policy test's pairing | Low | Medium | D2 enumerates the four elements that must survive; task0002 asserts each |
| The two documents end up describing different terminals (NFR6) | Medium | Medium — the feature's whole point is lost | SC-1 is the single contract both tasks implement; verification cross-reads both documents (TS-3, TS-6) |
| Version manifests diverge | Low | Medium | SC-3 plus the existing equality assertion |
| A task edits a frozen path (develop/SKILL.md, the batch-policy test, …) | Low | High — violates FR10 / NFR4 | Frozen list above; each task plan repeats it under Out of Scope; TS-10 checks the working-tree diff |

## Open Questions

- [ ] None. Every requirement in workflow.yaml has `status: ok`; SPEC.md
      carries no open question and no `tbd` requirement.
