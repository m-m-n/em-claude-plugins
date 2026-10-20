# Threat Model: worker-digest-ownership

## Verdict
threats-identified

## Rationale

Inspected: REQUIREMENTS.md, SPEC.md (FR1–FR8, NFR1–NFR3), workflow.yaml, and
the protocol documents the feature edits at the dispatch sites
(create-spec-phase.md, create-plan-phase.md, rework-task-synthesis.md, the
develop skill's 「design ステップ分岐」, phase-state.md, worker-envelope.md,
spec-writer-contract.md). Tier `full`; the design step is `skipped`, so no
DESIGN.md was an input.

The feature moves digest computation to the orchestrator: the orchestrator
now runs a command over file paths that partly come from a worker's result,
and it decides whether a worker may overwrite an existing file by comparing
digests of on-disk content with digests persisted in phase-state records.
Both are trust boundaries with realistic threats, so the verdict is
`threats-identified`.

Depth is `deep` for both boundaries: task0001 declares `input-handling` and
`external-io`; task0002 declares `data-persistence` and `input-handling`;
task0003 declares `data-persistence`. task0004 declares none of the four
depth domains (`api-contract`, `config-infra`): it only adds citations of
existing stance text to agent prompts and adds an invariant check.

Post-decomposition consistency: every task declaring one of the four depth
domains has at least one file on a `Boundary files` line. Files of those
tasks that are on no such line, and why:

- `em-workflow/scripts/check-plugin-invariants.py` (task0002, task0004) reads
  repository documents at fixed paths and reports pass/fail; it takes no
  worker output and authorizes nothing.
- `em-workflow/scripts/validate-worker-output.py` (task0003) gains one
  allowed `phase` value; how it treats worker results is unchanged.
- The test modules run against temporary directories they create
  themselves.

SPEC.md's Security Considerations records no protected asset (該当なし);
this document states how the digest protocol can be broken and how the
design prevents it, citing requirement IDs only.

## Trust Boundaries

### TB-1: Worker-reported paths and digests to orchestrator commands
Crossing: path strings and optional `sha256` values in a worker's
`written_artifacts` (an LLM subagent whose inputs include untrusted content)
cross into the orchestrator, which places paths into a Bash command line for
the digest script (and, for legacy records, `git hash-object --`) and
records digests into phase-state files.
Boundary files: em-workflow/references/artifact-digest.md,
em-workflow/scripts/artifact-digest.py,
em-workflow/references/contracts/worker-envelope.md,
em-workflow/references/phases/create-spec-phase.md,
em-workflow/references/phases/create-plan-phase.md,
em-workflow/references/rework-task-synthesis.md,
em-workflow/skills/develop/SKILL.md
Depth: deep (input-handling, external-io)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | A worker-reported path carrying shell metacharacters (a single quote, a command substitution, a line break) is interpolated into the digest command line (FR7, FR3) and runs arbitrary commands with the orchestrator's permissions | TM-1 | Each target path is passed as one single-quoted word; a path containing a single quote, line break or NUL is never put into a command (the owner document's `Calculation`, applied also to the legacy `git hash-object --` call) | task0002 AC-1 | VERIFICATION.md Performance / Security Verification, TM-1 |
| Tampering | A worker puts a `sha256` into a `written_artifacts` entry that does not match the written file; if recorded, a later `replace_own` decision treats a user-edited file as the worker's own output and authorizes overwriting it (FR1, FR2) | TM-2 | Layer 5 never reads a worker-supplied `sha256`; it records only digests the orchestrator computed with the script after layer 4 passes | task0002 AC-2 | VERIFICATION.md Performance / Security Verification, TM-2 |

### TB-2: On-disk content and persisted digest records to overwrite authorization
Crossing: file content in the integration worktree and digests persisted in
`phase-state/*.yaml` — both editable by the user or another process between
runs — cross into the orchestrator's decision whether a worker may overwrite
an existing artifact (`replace_own` / `replace_authorized`).
Boundary files: em-workflow/references/artifact-digest.md,
em-workflow/scripts/artifact-digest.py,
em-workflow/references/phase-state.md,
em-workflow/references/contracts/spec-writer-contract.md,
em-workflow/skills/develop/SKILL.md
Depth: deep (data-persistence, external-io)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Tampering | A record written by the earlier git-blob method is judged a match by its length or format (a SHA-256 git repository's blob ids are 64 hex digits too), so a user-edited file is silently overwritten (FR8) | TM-3 | A legacy record counts as a match only by equality with the current file's git blob id after dropping an optional `sha256:` prefix; length or format never decides; a non-match goes to the `{phase}.artifact-overwrite` gate / batch-policies decision | task0002 AC-3 | VERIFICATION.md Performance / Security Verification, TM-3 |
| Tampering | On a feature without `phase-state/design.yaml`, existing DESIGN.md or mockups are treated as the designer's own output and overwritten without any record proving it (FR4) | TM-4 | With `phase-state/design.yaml` absent and such outputs present, they go to the `design.artifact-overwrite` gate (batch: batch-policies.yaml), never to `replace_own` | task0002 AC-6 | VERIFICATION.md Performance / Security Verification, TM-4 |
| Tampering | A target file changes between the action decision (when `expect_digest` was computed) and the dispatch, and the stale `replace_own` / `replace_authorized` overwrites the newer content (FR3) | TM-5 | Pre-dispatch verification runs after the pre-dispatch snapshot and immediately before every dispatch; any mismatch or error means no dispatch and a fresh action decision (`replace_authorized` re-requests approval) | task0002 AC-2 | VERIFICATION.md Performance / Security Verification, TM-5 |
| Denial of service | A target path that is a FIFO, device or symlink makes the digest calculation block indefinitely or read a file outside the worktree, stalling an unattended run or yielding a digest for the wrong content (FR7) | TM-6 | The script reads only regular files, confirms the type on the handle it reads, follows no symlink and never waits on a FIFO or device; such entries yield `not_a_regular_file` | task0001 AC-6 | VERIFICATION.md Performance / Security Verification, TM-6 |
