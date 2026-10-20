# Artifact Digest Protocol (em-workflow SSOT)

This document is the single owner of the artifact digest: its definition,
the means that calculates it, the orchestrator's pre-dispatch verification of
`expect_digest`, the layer-5 recording of `written_artifacts` digests, the
rule for records made by the earlier method, and the list of dispatch sites
that apply all of it. It applies at every dispatch of a worker that carries a
`write_policy`.

The orchestrator does all of this, never the worker. The worker-side stance
is owned by `references/contracts/worker-envelope.md` ("`written_artifacts`
reporting") and `references/contracts/spec-writer-contract.md` ("Who
verifies `expect_digest`"); this document does not restate it.

Other documents cite this one by the path `references/artifact-digest.md`
and a section name from the headings below. They never re-word a definition
or a procedure stated here.

## Digest definition

An artifact digest is the sha256 of a file's raw bytes, written `sha256:`
followed by 64 lowercase hexadecimal digits. One definition covers all three
uses:

- `expect_digest` in a `write_policy.targets` entry;
- `artifacts[].sha256` in a phase-state file (`references/phase-state.md`);
- the layer-5 digest of artifact validation (`references/contracts/worker-envelope.md`,
  "Validation layers").

It is not any of the following, and none of them changes:

- the git blob id that the post-dispatch comparison of scope verification
  uses (`references/phases/create-spec-phase.md`, "Scope verification"). A
  git blob id and an artifact digest are different values, even for the same
  file;
- `input_digest`, the sha256 of the normalized JSON of rule R1
  (`references/contracts/worker-envelope.md`);
- `workflow_blob` and `base_workflow_blob`, which keep their current
  definitions (`references/contracts/worker-envelope.md` and
  `references/workflow-patch.md`).

## Calculation

The orchestrator calculates every artifact digest with one script, called
from the integration worktree, with the target paths as arguments:

```text
python3 "${CLAUDE_PLUGIN_ROOT}/scripts/artifact-digest.py" 'feature-docs/example/SPEC.md' 'feature-docs/example/REQUIREMENTS.md'
```

Quoting rule: the script path is double-quoted, because it contains
`${CLAUDE_PLUGIN_ROOT}`. Each target path is one single-quoted word. A path
containing a single quote, a line break or NUL is never put into a command:
before dispatch it counts as a mismatch (`Pre-dispatch verification`), and at
layer 5 it is an artifact-validation failure (`Layer 5 recording`). The
script defines no options, so a path beginning with `-` is still a path.

Reading the result: standard output is one JSON array with one element per
argument, in argument order, duplicates kept. An element's position is what
ties it to its argument; its `path` echoes the argument as given. A success
element carries `path` and `sha256`. A failure element carries `path`,
`sha256: null` and an `error` token:

- `missing` — no filesystem entry at the path;
- `not_a_regular_file` — a directory, symlink, FIFO, device or socket;
- `unreadable` — a regular file whose reading failed.

Exit codes:

- `0` — every element has a `sha256` digest;
- `1` — at least one element has an `error`; every other element is still
  hashed and reported;
- `2` — no argument was given, an argument was not valid UTF-8, or the script
  failed unexpectedly; standard output carries no array.

This call is not a `workflow.yaml` command, so the Bash guard hook
(`hooks/bash_guard.py`) gives no verdict on it and the normal permission flow
applies.

## Pre-dispatch verification

When: after the clean-worktree precondition and the pre-dispatch snapshot
(`references/phases/create-spec-phase.md`, "Scope verification"),
immediately before the dispatch. Nothing else runs between the verification
and the dispatch.

Targets: every `write_policy.targets` entry whose action requires
`expect_digest` (`references/contracts/spec-writer-contract.md`, "The six
`write_policy` actions"). The `expect_digest` values themselves come from the
same calculation, run at action-decision time ("How the orchestrator chooses
each target's action before dispatch" in the same contract).

The orchestrator runs `Calculation` over those targets and compares each
element's `sha256` with that target's `expect_digest`.

Outcome: any element whose `sha256` differs from its `expect_digest` is a
mismatch, and so is a target whose element carries an `error`, a target path
that the quoting rule keeps out of a command, and an exit code of `2`. On a
mismatch there is no dispatch. The input is stale, and the orchestrator
returns to the action decision. A `replace_authorized` mismatch re-requests
approval, because the approval covers only the content the user was shown.

The worker never repeats this verification. From it to the worker's write,
the exclusivity assumption (`references/contracts/worker-envelope.md`)
protects the targets, and the post-dispatch scope comparison detects any
change made in that window.

## Layer 5 recording

When: after layer 4 (scope verification) passes for the dispatch's
`completed` result.

How: one `Calculation` call over every `written_artifacts` path. The
orchestrator records one `{path, sha256, produced_by}` entry per path into
`artifacts` of the dispatching phase's phase-state file: `create-spec.yaml`,
`design.yaml`, `create-plan.yaml` or `rework.yaml` under
`feature-docs/{feature}/phase-state/`, following the "ID uniqueness and
idempotency" rules of `references/phase-state.md`.

- A `sha256` the worker put in an entry is never read, compared or recorded;
  only digests the orchestrator calculated are recorded.
- `preserve` targets are never written by a worker, so they are not in
  `written_artifacts` and are not recorded.
- When `tokens.yaml` and `tokens.html` are both written, both are recorded.
- Any error element, an exit code of `2`, or a path the quoting rule keeps
  out of a command fails layer 5 as an artifact-validation failure.

## Legacy records

Earlier, a recorded `sha256` was the git blob id of the file. A recorded
value that differs from the file's new digest is therefore compared with the
file's legacy value, which is its git blob id computed with
`git hash-object --` (the target path follows the same quoting rule as
`Calculation`; a path that rule keeps out of a command is not a match).

Equality is the only test. The orchestrator drops an optional `sha256:`
prefix from the recorded value and compares what remains with the git blob
id. Length or format never decides: a git repository that uses SHA-256 has
blob ids of 64 hexadecimal digits too, so a 64-digit value says nothing about
which method made it.

- Equal: the record counts as a match, as if the digest had matched. The new
  digest recorded by `Layer 5 recording` at that dispatch supersedes the
  legacy value.
- Not equal: the digest-mismatch branch applies, the
  `{phase}.artifact-overwrite` gate in interactive mode and the
  `references/batch-policies.yaml` decision in batch mode.

This applies wherever an action decision compares a recorded digest:
create-spec, the design step and create-plan. Rework's action choice is
unchanged.

## Dispatch sites

Each row names a section of a document that dispatches a worker carrying a
`write_policy`, that worker, and the sections of this document the site
section cites. `scripts/check-plugin-invariants.py` (`dispatch_digest_wiring`)
reads this table: a site section that loses its citation fails the check.
Every worker listed here is covered for both `Pre-dispatch verification` and
`Layer 5 recording` across its rows. A new site is registered by adding rows.

| Document | Section | Worker | Covers |
|---|---|---|---|
| `references/phases/create-spec-phase.md` | `9. Spec writer dispatch` | `spec-writer` | `Pre-dispatch verification` |
| `references/phases/create-spec-phase.md` | `10. Artifact validation` | `spec-writer` | `Layer 5 recording` |
| `skills/develop/SKILL.md` | `design ステップ分岐` | `designer` | `Pre-dispatch verification`, `Layer 5 recording` |
| `references/phases/create-plan-phase.md` | `4. Planner dispatch` | `implementation-planner` | `Pre-dispatch verification` |
| `references/phases/create-plan-phase.md` | `8. Validation` | `implementation-planner` | `Layer 5 recording` |
| `references/rework-task-synthesis.md` | `10. Workflow state transition` | `rework-planner` | `Pre-dispatch verification`, `Layer 5 recording` |

- Every create-spec re-entry, rework's spec-change transition and the tier
  upgrade included, goes through the create-spec site above.
- Plan-patch permissions, re-planning authorization and rework's action
  choice are not changed by this document.
