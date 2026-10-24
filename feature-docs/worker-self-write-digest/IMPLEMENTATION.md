# Implementation Plan: worker-self-write-digest

## Overview

On a worker's return, the orchestrator recomputes `input_digest` with the
dispatch-time digest substituted for every path the worker legitimately wrote
(the self-write set), so permitted self-writes are no longer judged stale while
every other change still is. One standard-library script identifies the set and
performs the substitution; Rule R1 states the rule once; three worker contracts
cite it; the three dispatch sites call the script; phase-state persists what a
resumed run needs.

## Technology Stack

- **Language**: Python 3, standard library only, for the new script; Markdown
  for protocol documents.
- **Test framework**: `unittest`, run as `python3 -m unittest discover -s tests`.
  Tests that run `validate-worker-output.py` depend on PyYAML exactly as the
  existing validator tests already do.
- **New dependencies**: none. `project.license` is `none`; no license line is
  recorded because nothing new is introduced.

## Layer Structure

| Layer | Members | Responsibility |
|---|---|---|
| Rule owner | `em-workflow/references/contracts/worker-envelope.md`, Rule R1, the "Recomputation and comparison timing" paragraph | The only statement of the self-write rule: when it applies, what the self-write set is, the per-action permission, the substitution, the return-time order, how the orchestrator runs the script, and that resume takes the persisted set |
| Schema owner | `em-workflow/references/phase-state.md` | Definition of the two new `worker_runs[]` fields, when they are written, and how the Resume decision table uses them |
| Citing documents | `designer-contract.md`, `planner-contract.md`, `rework-planner-contract.md` (under `em-workflow/references/contracts/`), `em-workflow/references/workflow-patch.md` application rule 1 | Cite R1; each contract names its overlapping paths |
| Orchestrator procedures (dispatch sites) | `em-workflow/skills/develop/SKILL.md` 「design ステップ分岐」, `em-workflow/references/phases/create-plan-phase.md` sections 3, 4, 8, 9, `em-workflow/references/rework-task-synthesis.md` section 10 | Record, run the script, compare and persist, in the order R1 states |
| Script | `em-workflow/scripts/self-write-digest.py` | Self-write identification and substitution; no hashing |
| Tests | `tests/` | Load or run the script, run the validator, read documents |

Allowed directions: procedures cite R1 and `phase-state.md`, and run the script
by its invocation; contracts and `workflow-patch.md` cite R1 only. The script
reads no document and no file other than its own input document. Tests depend
on scripts and documents, never the reverse. Paths in this document are
repository-relative unless written relative to `em-workflow/`.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|---|---|---|---|
| R1 self-write rule | Single statement of the rule (FR1–FR4, FR8, FR9) | Lives in `worker-envelope.md` under the existing heading "## Rule R1: `input_digest` and staleness detection", inside or directly after the bold "Recomputation and comparison timing" paragraph, stated once. A citation is the path token `references/contracts/worker-envelope.md` plus the words "Rule R1" and "Recomputation and comparison timing" in one paragraph. | written by task0002; cited by task0003 and by the script's module docstring (task0001) |
| Self-write script | Identification and substitution (FR10) | "Self-write script CLI contract" below | built by task0001; named in R1 by task0002; invoked by the task0003 procedures |
| Self-write membership matrix | Which observed change counts as a self-write (FR2, FR3) | "Self-write membership matrix" below | implemented by task0001; stated in R1 by task0002 |
| Substitution | How the return-time `digest_source` is built (FR1, FR4, NFR1) | "Substitution contract" below | implemented by task0001; stated in R1 by task0002 |
| Phase-state run fields | Persistence for reproduction after an interruption (FR6, FR7) | "Phase-state run fields" below | defined by task0002; written and read by the task0003 procedures; used by task0001's resume test |
| Return-time sequence | Order at a dispatch site (FR5, FR8) | "Return-time sequence" below | stated in R1 by task0002; applied at each site by task0003 |

### Self-write script CLI contract

- **Path and invocation**: `em-workflow/scripts/self-write-digest.py`, run with
  `python3`, the script path double-quoted (it is written with
  `${CLAUDE_PLUGIN_ROOT}`), then exactly one argument: the path of the input
  document. Any other argument count is a usage error.
- **Input document**: one UTF-8 JSON object whose `operation` member selects
  one of two operations:
  - `identify_and_substitute` — members `dispatch_digest_source`,
    `current_digest_source`, `observed_changes`, `write_policy`,
    `allowed_write_roots`.
  - `substitute_only` — members `current_digest_source`,
    `dispatch_digest_inputs`, `self_write_set`.
  - A missing member, a member not listed for the selected operation, or an
    unknown operation is invalid input.
- **Member shapes**: a digest_source member is a mapping whose `digest_inputs`
  member is a mapping of string path to string digest; its other members are
  carried, never interpreted. `observed_changes` is a list of mappings with
  `path` (non-empty string) and `kind` (`created` | `modified` | `deleted`),
  no path repeated. `write_policy` is the dispatch envelope's `write_policy`
  object; only its `targets` list is read, each entry with `path`, `action`
  (one of the six actions) and `source` (required when the action is
  `regenerate`); a repeated target path is invalid input.
  `allowed_write_roots` is the envelope's top-level list of strings.
  `dispatch_digest_inputs` is a mapping of string to string. `self_write_set`
  is a list of strings.
- **Output**: standard output carries one JSON object followed by a newline,
  UTF-8, non-ASCII unescaped, with two members: `self_write_set` (ascending,
  without duplicates) and `digest_source` (the substituted object). For
  `substitute_only`, `self_write_set` echoes the given set sorted and
  de-duplicated.
- **Exit codes**: `0` success; `2` usage error, invalid input, an input
  document that cannot be read or parsed, or an unexpected failure — a message
  on standard error and nothing on standard output.
- **Isolation**: standard library only; reads only the input document (paths
  inside it need not exist); computes no hash; starts no child process; writes
  no file.
- **Orchestrator side** (stated in R1 by task0002): the orchestrator writes the
  input document with its file-writing tool to a location outside the
  integration worktree, never assembling it through shell interpolation; no
  path taken from the document ever appears on the command line; any exit code
  other than `0` makes the result stale.

### Self-write membership matrix

A path is in the self-write set only when it appears in `observed_changes` and
its change kind is permitted by the entry covering it:

| Covering entry | `created` | `modified` | `deleted` |
|---|---|---|---|
| target `create` | member | not a member | not a member |
| target `replace_own` | not a member | member | not a member |
| target `replace_authorized` | not a member | member | not a member |
| target `extend_only` | not a member | member | not a member |
| target `regenerate` | not a member | member only when its `source` is a member | not a member |
| target `preserve` | not a member | not a member | not a member |
| not a target, inside an `allowed_write_roots` entry | member | not a member | not a member |
| neither | not a member | not a member | not a member |

- A path listed in `targets` is judged by its target even when it also lies
  under an allowed write root.
- Containment in an allowed write root compares path segments, never string
  prefixes (`feature-docs/x2/a.md` is not inside `feature-docs/x`); a root
  written with or without a trailing slash names the same directory; a path
  equal to the root itself is not inside it.
- An absolute path, or a path with a `..` segment, is never a member.
- `regenerate` targets are decided after every other path; a `regenerate`
  target whose `source` is itself a `regenerate` target is not a member.
- Kinds follow the split of `references/phases/create-spec-phase.md`
  ("Scope verification"): `created` = absent at the pre-dispatch snapshot and
  present now; `modified` = present at both (content, mode or file kind
  changed); `deleted` = present at the snapshot and absent now.
- The worker's `written_artifacts` is not an input of the identification.

### Substitution contract

Given the current digest_source C, a dispatch-time map D (the dispatch
digest_source's `digest_inputs`, or the persisted map on resume) and a
self-write set S, the output O satisfies:

- O has exactly C's top-level members; every member other than
  `digest_inputs` equals C's (so `worker`, `mode`, `workflow_blob`,
  `value_inputs`, `answers_digest`, `write_policy_digest` are always current).
- O's `digest_inputs` starts as C's. For each path P in S: when P is a key of
  D, O holds D's value for P; otherwise P is absent from O.
- A path not in S keeps C's value, or C's absence.
- Inputs are never mutated; identical inputs give identical output.
- Consequence: when every in-window change to a digest input is a self-write
  and nothing else changed, the R1-normalized digest of O equals the
  dispatch-time `input_digest`; any other change keeps them different.

### Phase-state run fields

Each `worker_runs[]` entry gains two optional fields, written at the three
dispatch sites that run the script (design step, create-plan, rework):

- `dispatch_digest_inputs` — the per-path `digest_inputs` map of the
  dispatch's digest_source. Written with the entry when it is created at
  dispatch (`status: dispatched`); never changed afterwards.
- `self_write_set` — ascending list of paths, as the script returned it.
  Absent until the return-time sequence completes; written once, in the same
  phase-state write that records the run's layer-5 `artifacts` entries (for a
  run with no written artifacts, the write that records its returned status);
  never changed afterwards. The ID-uniqueness rule's `worker_runs` exception
  widens from "`status` alone" to "`status`, plus this one-time addition".
- **Resume selection**: the last `worker_runs` entry whose `input_digest`
  equals `last_input_digest`. When that entry lacks either field, nothing is
  substituted.
- Entries written before this feature carry neither field and remain valid.

### Return-time sequence

At each of the three dispatch sites, in this order:

1. Layer 4 scope verification (`references/phases/create-spec-phase.md`,
   "Scope verification"), which yields the observed change set with kinds;
   violations are handled there.
2. The orchestrator recomputes the current digest_source from current state,
   exactly as at dispatch (value inputs re-resolved).
3. The script, operation `identify_and_substitute`.
4. The R1 comparison of the substituted digest_source's R1-normalized digest
   with the dispatch-time `input_digest`: at create-plan and rework through
   `validate-worker-output.py --dry-run-apply` with `--digest-source` set to
   the substituted digest_source (application rule 1); at the design step
   directly. A mismatch, or a script exit other than `0`, makes the result
   stale.
5. Layer 5 recording (`references/artifact-digest.md`, "Layer 5 recording")
   and `self_write_set`, in one phase-state write.

On a resumed create-plan run, the orchestrator recomputes the current
digest_source, runs `substitute_only` with the selected entry's
`dispatch_digest_inputs` and `self_write_set`, and compares the result with
`last_input_digest`; the comparison of artifact bodies with their recorded
digests stays as it is.

## Conventions

- **Single statement (NFR6)**: only R1 states the condition, the membership
  matrix, the substitution, the return-time order and the script's
  orchestrator-side use; only `phase-state.md` defines the two fields.
  Everything else cites by path plus section or paragraph name and never
  re-words them.
- **Orchestrator as subject (NFR2)**: every new sentence about digests names
  the orchestrator as the actor or is negated; no worker agent prompt changes;
  `worker-envelope.md` keeps "The worker does not compute digests" in
  "`written_artifacts` reporting" and never contains the token
  `expect_digest`.
- **Dispatch-site sections (NFR3)**: each section registered in
  `references/artifact-digest.md` "Dispatch sites" keeps its citation of
  `references/artifact-digest.md` with its Covers names and never contains
  `git hash-object`.
- **Pinned headings**: existing headings are never renamed — in particular
  `phase-state.md` "## ID uniqueness and idempotency",
  "### worker_runs[].status transitions" and "## Resume decision table";
  `create-plan-phase.md` "## 3. Reconcile on entry", "## 4. Planner dispatch",
  "## 8. Validation"; `SKILL.md` "### design ステップ分岐";
  `rework-task-synthesis.md` "## 10. Workflow state transition".
- **Structure unchanged (NFR1)**: R1's normalization paragraph and the
  `digest_source` example with its seven structural keys stay as written.
- **Tests**: standard-library `unittest`; temporary directories; documents
  asserted on whitespace-normalized, section-sliced text, never by
  full-document equality. A document test asserts citation text only, never
  that the script file exists (tasks run in separate worktrees). The
  hyphenated script is loaded by file path. A new test file never contains
  `subagent_type=` followed by a quote and `em-workflow:`.
- **Gate-ID scan hygiene**: new prose never puts a dotted backtick span within
  120 characters after a "gate id" / "gate_id" mention unless it is a real
  gate ID listed in `batch-policies.yaml`.
- **Language**: protocol documents in English; `SKILL.md` in Japanese, citing
  English section and paragraph names verbatim.
- **Versioning**: no task edits a plugin `version` field (NFR5); the
  repository's Actions workflow owns it.

## Cross-task Design Decisions

### D1: Substitute, never exclude

Self-written paths take their dispatch-time value inside `digest_inputs`
rather than being dropped from the digest, so the aggregate comparison stays
and a re-plan still detects drift in paths it did not write (A1). Affects
task0001, task0002.

### D2: Membership from what the orchestrator observed, judged conservatively

Only the layer-4 observed change set can admit a path; `written_artifacts`
never does (FR2). The matrix admits only what each action permits; deletion is
never a self-write (no in-scope worker holds a tool that deletes files, so a
deletion is never legitimate output), and `replace_own` /
`replace_authorized` / `extend_only` admit modification only. Affects
task0001, task0002.

### D3: One script, one JSON input document, two operations

`identify_and_substitute` serves the return-time recheck; `substitute_only`
serves resume, where the persisted set replaces re-identification. A single
input document keeps worker-chosen file names off the command line (TM-3).
Hashing stays with the orchestrator (A8). Affects task0001, task0002,
task0003.

### D4: `validate-worker-output.py` is unchanged

FR5 is met by what the orchestrator passes as `--digest-source`: the
substituted digest_source. The validator's rule-1 comparison already hashes
whatever digest_source it receives, so no validator code changes and its byte
pin in `tests/test_gate_option_vocabulary.py` is not touched. Affects
task0001 (its tests run the validator), task0002 (rule 1 wording), task0003
(section 9 invocation note).

### D5: Persistence on the run record, written together with layer 5

The two fields sit on the `worker_runs[]` entry the set belongs to.
`self_write_set` is written in the same phase-state write as the run's layer-5
`artifacts` entries, so every substituted path also has a recorded digest that
the resume step "artifact bodies vs. their recorded digest" checks (TM-4).
Affects task0002, task0003, task0001 (resume test).

### D6: Out of scope

`TASK.md` (minimal tier) is not in the planner's `digest_inputs`, so it is not
an overlapping path and nothing about it changes (A5). The designer's
`project_native` case has no overlap and needs no special handling: the
substitution is a no-op there.

### D7: Scenario ID form

VERIFICATION.md uses the hyphenated `TS-n` form so IDs string-match SPEC.md and
the `requirements[].tests` already recorded in workflow.yaml.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Docs and script drift apart on the matrix or the substitution | Medium | High | Both are pinned above; task0001 tests every matrix cell; task0002 asserts R1 states each rule |
| A new sentence in a cited contract trips `worker_digest_stance` | Medium | Medium | Orchestrator-subject convention; the real-repository check is an Acceptance Criterion of task0002 |
| A dispatch-site edit drops an artifact-digest citation or names `git hash-object` | Low | Medium | NFR3 convention; `dispatch_digest_wiring` real-repository pass is an Acceptance Criterion of task0003 |
| An existing wording pin breaks on a document edit | Medium | Medium | Pinned-heading convention; full suite before completion in every task |
| Worker and an external actor change the same permitted path (A6) | Low | Medium | Known limit; relies on the exclusivity assumption, stated in R1 rather than solved |

## Open Questions

- [ ] "再現手順で現象が起きない" with a live designer `extend_only` dispatch and a
      live re-plan is not executable from unit tests; it is a manual
      verification item.
- [ ] A6 (worker and external actor writing the same permitted path) remains a
      known limit of snapshot-based detection.
