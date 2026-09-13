# Implementation Plan: codex-wrapper-fallback-removal

## Overview

Remove the provider fallback chain from the em-workflow Codex wrapper so the
wrapper runs `codex exec` exactly once, nest the wrapper's timeout strictly
inside the caller's Bash-tool timeout in both plugins, and realign every
document and test that described the removed in-wrapper chain.

## Technology Stack

- **Bash** — `em-workflow/scripts/run_codex_exec.sh`, the only component that
  launches an external process.
- **YAML** — `references/codex-cli.yaml` in both plugins; supplies the
  wrapper's timeout value and nothing else.
- **Markdown** — agent prompts and protocol documents; they are the plugins'
  executable surface, so their wording is a contract, not commentary.
- **JSON** — plugin manifests and the marketplace registry.
- **Python standard library (`unittest`)** — the existing test harness for
  this repository.

No new dependency is introduced by this feature, so no new license enters the
project. `project.license` is `none`; there is no license constraint to check
and no license conflict to resolve.

## Layer Structure

| Layer | Members | Responsibility |
|---|---|---|
| L1 execution | `em-workflow/scripts/run_codex_exec.sh` | The single point that launches `codex exec` and shapes what the caller receives |
| L2 configuration | `em-workflow/references/codex-cli.yaml`, `em-review/references/codex-cli.yaml` | SSOT for the wrapper's timeout value; read by L1 at run time |
| L3 invocation | `em-workflow/agents/codex-reviewer.md` Step 5, `em-review/agents/codex-reviewer.md` Step 5, `em-workflow/references/question-resolution.md` Codex consultation procedure step 2 | Launch L1 and declare the Bash-tool timeout that bounds it |
| L4 protocol prose | `em-workflow/references/batch-mode.md`, `em-workflow/references/phase-state.md` | Describe what a batch run reports and persists about a consultation |
| L5 verification | `tests/` | Pin L1–L4 and L6 |
| L6 distribution | both `plugin.json`, root `marketplace.json` | Plugin versions |

Allowed dependency directions: L3 → L1 → L2. L5 reads every layer and is read
by none. L6 is independent.

**Forbidden direction (the feature's central claim):** L1 never depends on L3
or L4. The wrapper does not know the shape of the prompt it carries, therefore
it must not choose which harness answers it. Harness selection belongs to the
orchestrator's Phase R2b chain walk over `reviewers.yaml`, which is outside
this feature's change set entirely.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|---|---|---|---|
| Wrapper caller-facing contract | What any caller of `run_codex_exec.sh` may rely on | Pre: a valid mode plus optional working-directory / output-schema selection and a prompt. Post: exactly one `codex exec` process is launched per wrapper run; the launched process's own exit code is the wrapper's exit code, except that exceeding the configured timeout yields exit code 124 together with one stderr line naming the configured timeout in seconds; the combined output is the process's whole stdout followed by its whole stderr; no line beginning with either fallback marker prefix is ever emitted | task0001 (produces), task0002 (reasons about its timing), task0003 (describes it) |
| Timeout nesting contract | Guarantees the wrapper's diagnostic reaches the caller | Pre: the caller states a Bash-tool timeout in milliseconds. Post: wrapper seconds × 1000 < caller milliseconds, with the margin set at 60 seconds (540 / 600000); the wrapper value lives only in L2 and the caller value only in L3 prose | task0002 (sets both sides), task0001 (its tests must not hard-code either) |
| Configured-timeout read rule | Keeps per-task worktrees independent | Any test that exercises the wrapper's timeout path asserts against the value it reads from L2 at test time, or against a reduced value it supplies to an isolated copy of the wrapper — never against a hard-coded number. Only the timeout-alignment task asserts the literal 540 / 600000, and it asserts them as configuration facts, not as wrapper behaviour | task0001, task0002 |
| Removed-phrase vocabulary | Defines exactly what "remove the in-wrapper fallback claim" means | Removed everywhere: the claim that the wrapper's own reply may come from a fallback provider instead of the primary one, and the obligation to record whether a fallback provider answered. Preserved byte-for-byte: every description of the orchestrator's Phase R2b chain walk over `reviewers.yaml`, the `rate_limited` / `budget_exhausted` / `harness_unavailable` routing table, every description of the Opus escalation, the "Unlisted-gate fallback" section name, the Claude-fallback rules, and the schema-path fallback in both reviewer prompts | task0001, task0002, task0003 |
| Version-assertion baseline rule | Keeps version tests from going stale | A test asserting a plugin version compares against a fixed pre-feature baseline in the strictly-greater (or not-below) direction. An equality pin on a version that is current at authoring time is prohibited — it converts the next legitimate bump of that plugin into a false failure | task0004 |
| File ownership map | Prevents two tasks from editing the same region | See the table under D4; every file in the change set has exactly one owning task | all tasks |

## Conventions

- **Test hermeticity**: new and edited test code imports only the Python
  standard library and runs with a stubbed command on `PATH`, an isolated
  `HOME`, no network and no real provider. Both project test commands must
  pass: the unittest discovery run and the destructive-guard runner.
- **Non-vacuity**: every new matcher is accompanied by a negative proof
  against forged input showing the matcher fails when the property is absent,
  following the pattern the existing version-bump and doc-pinning modules
  already use.
- **Vocabulary removal is a reading task, never a string replacement**: the
  word "fallback" is used legitimately in several places that must survive
  (see the Removed-phrase vocabulary row above). Each occurrence is judged in
  place.
- **No provider naming in `em-workflow/references/`**: no provider or model
  identifier, and no description of usage-limit detection, may be introduced
  anywhere under that directory. This feature only shrinks that surface.
- **Byte-identical invocation lines**: the fenced wrapper-invocation command
  inside each reviewer prompt's Step 5 is a pinned byte-level contract. The
  Bash-tool timeout is stated as prose about the tool parameter, outside that
  fence.
- **Deletion over deprecation**: superseded test modules are deleted rather
  than emptied; superseded historical SPEC entries are left untouched rather
  than annotated.

## Cross-task Design Decisions

### D1 — One invocation, no recovery logic inside the wrapper

The wrapper launches the external command once and reports what happened. It
never inspects the response to decide whether to launch again. This removes
the last place where a model-generated stream could influence control flow,
and it is what makes the worst-case wrapper duration equal to the configured
timeout rather than a multiple of it.

Affected: task0001 (implements), task0002 (its timeout arithmetic assumes a
single invocation), VERIFICATION.md (NFR1).

### D2 — Timeout nesting: the wrapper always expires first

The wrapper's configured seconds are set below the caller's declared
milliseconds, with a 60-second margin, so the wrapper survives long enough to
emit its own diagnostic and the caller receives that diagnostic instead of a
bare timeout exit. The margin is a probability improvement, not a guarantee:
the timeout mechanism is used without a kill-after grace period, so a process
slow to respond to termination can still outlive it.

Affected: task0002 (sets both sides at all five locations), task0001 (must not
encode either number).

### D3 — Split capture and JSON-first ordering are preserved behaviour

stdout and stderr are captured separately and concatenated stdout-first. This
is deliberately NOT simplified into a combined-stream form: the external CLI
writes a large banner to stderr on every run, and interleaving it would place
banner text inside the schema-constrained JSON reply. The combined output
still ends with stderr after the JSON, so a consumer that parses the entire
output as one JSON document fails — what makes this safe is the reviewer
prompt's extract-then-parse behaviour, which this feature does not change.

Affected: task0001 (preserves), VERIFICATION.md (FR2 / TS5).

### D4 — One owner per file, and per-task scope for the document sweep

Two independent facts change inside the same paragraph of
`question-resolution.md` (the Bash-tool timeout and the removal of the
fallback-provider claim). Both are assigned to a single task so no two
worktrees edit the same region. The full four-document sweep that SPEC.md
describes as TS8 therefore cannot live in any one task worktree — each task
verifies only the documents it owns, and the union is verified after
integration by VERIFICATION.md.

| File | Owner |
|---|---|
| `em-workflow/scripts/run_codex_exec.sh` | task0001 |
| `tests/test_codex_wrapper_provider_fallback.py` (deleted) | task0001 |
| the replacement wrapper test module | task0001 |
| `em-workflow/references/codex-cli.yaml` | task0002 |
| `em-review/references/codex-cli.yaml` | task0002 |
| `em-workflow/agents/codex-reviewer.md` | task0002 |
| `em-review/agents/codex-reviewer.md` | task0002 |
| `em-workflow/references/question-resolution.md` | task0002 |
| `tests/test_question_resolution_doc.py` | task0002 |
| the timeout-alignment test module | task0002 |
| `em-workflow/references/batch-mode.md` | task0003 |
| `em-workflow/references/phase-state.md` | task0003 |
| `tests/test_batch_quiet_output_discipline.py` | task0003 |
| `tests/test_batch_quiet_output_audit_record_contract.py` | task0003 |
| the doc-realignment test module | task0003 |
| both `plugin.json`, root `marketplace.json` | task0004 |
| the four existing modules that pin the em-review version | task0004 |
| the version-consistency test module | task0004 |
| `tests/test_reviewer_roles_protocol.py` | task0005 |
| the integrated-checks test module | task0005 |

**Derived pins have an owner too (added by task0005).** A file that no task
edits by intention, but that a declared edit mechanically forces to change, is
still a file in the change set and still needs exactly one owning task. The
case in this feature: `tests/test_reviewer_roles_protocol.py` holds a digest
over `em-workflow/agents/codex-reviewer.md` from `## Step 0` to EOF, so
task0002's one-sentence addition to Step 5 of that document forced the digest
to be recomputed. The document belongs to task0002 and the module belongs to
task0005; the coupling between them is declared inside the module itself, as
the set of source documents its digests are derived from, so the next task that
declares one of those documents can see that this module comes with it. The
finer-grained byte-level pin of the Step 5 invocation line stays where it is,
in `tests/test_codex_reviewer_temp_file_isolation.py`, which no task declares
and no task may touch (NFR6, AC14).

### D5 — The em-review version bump has a test ripple

Four existing test modules assert the em-review marketplace version equals a
literal captured before their own feature — the value this feature moves.
Bumping em-review without touching them turns the suite red, so they are part
of the version task's file set. They are repaired by moving each assertion to
the baseline form described in the Version-assertion baseline rule, not by
re-pinning the new literal (re-pinning would recreate the same breakage at the
next em-review bump). The em-workflow side needs no such repair: every
em-workflow version assertion in the suite is already baseline-relative.

### D6 — What "unchanged" is verified by

Two files must remain byte-for-byte identical: the em-review wrapper and the
superseded feature's SPEC. A test cannot prove byte identity against a
baseline it does not hold, so each is covered from two sides: a positive
structural assertion inside the owning task (the property that would be lost
if the file were edited), and a change-set check at verification time against
the integration base commit. Neither side alone is sufficient; both are
required.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| A run that previously succeeded between the old and the new timeout is now cut short | Medium | Low | Accepted: a truncated run that keeps its diagnostic is preferable to one that loses it (SPEC A1) |
| The wrapper outlives the caller's timer because termination is slow | Low | Medium | 60-second margin; accepted as a probability improvement, not a guarantee (SPEC A2) |
| A "fallback" occurrence that must survive is deleted by over-eager editing | Medium | High | Removed-phrase vocabulary contract above; each task asserts the preserved wording positively, not only the removed wording negatively |
| A test edit silently weakens a pin instead of updating it | Medium | Medium | Non-vacuity convention: every matcher keeps a negative proof against forged input |
| The em-review timeout change reaches em-review users who never hit the em-workflow defect | High | Low | Accepted (SPEC A6); release notes come from the version bump |
| A consumer parses the wrapper's whole output as one JSON document | Low | Medium | Unchanged from today (D3); the extract-then-parse behaviour in the reviewer prompt is untouched |

## Open Questions

- [ ] SPEC.md's File Structure section lists neither the four existing test
      modules that pin the em-review version nor the file names of the new
      test modules. The change set derived from the task `files` entries
      below is the authoritative list for this feature.
