# Implementation Plan: routeback-deferred-findings

## Overview

Resolve the six findings deferred at review round 3 of `routeback-admissibility-exits`
(`12839a507a7df994`, `2da3c75adac32650`, `bc57aa350bb027c7`, `59e58726b1b22211`,
`94de80a315821a55`, `9cc0ce6b64087d2f`): stale `launched` tasks with missing artifacts
join the existing proof chain, a journal-`merged` task that fails the ancestor check
gets an automated exit through a new `failed` reason `merge-unverified`, and the drift
between `em-workflow/references/implement-phase.md` and the SSOT
`em-workflow/references/workflow-schema.md` is removed.

## Technology Stack

- **Language**: Python 3, standard library only (scripts and tests).
- **Documents**: Markdown protocol references under `em-workflow/references/`.
- **Test runner**: `python3 -m unittest discover -s tests`.
- **New dependencies**: none. `project.license` is `none`, and no new library is
  introduced, so there is no dependency license to record.

## Layer Structure

| Layer | Members | Responsibility | May depend on |
|-------|---------|----------------|---------------|
| Protocol owner | `em-workflow/references/implement-phase.md` | Owns the implement-phase protocol (I.2.a / I.2.b / I.2.c / Supporting cast), including every SC6 reason code and every invocation of the scripts below | Cites `workflow-schema.md` and prior features' IMPLEMENTATION.md contracts; never restates them |
| SSOT | `em-workflow/references/workflow-schema.md` | Owns status semantics, the journal writer set and the agent-index role | Cites `implement-phase.md` sections by repository-relative path; never restates them |
| Decision script | `em-workflow/scripts/recover-orphaned-task.py` | Decides, for one candidate, whether termination is proven; never writes the journal | Invokes the journal-write helper as a subprocess |
| Journal-write helper | `em-workflow/scripts/journal-append-failed.py` | The only orchestrator-side writer of terminal `failed` events; closed reason set; replay and append under one exclusive lock | The journal file only |
| Unchanged hooks and scripts | `queue_launch_guard.py`, `merge-task.sh`, the other queue hooks | Not modified by any task (NFR7) | — |
| Tests | `tests/` | Doc-contract modules (read documents) and script tests (subprocess plus function level) | Read documents and scripts; drive scripts and hooks as subprocesses |

Dependency direction: the orchestrator (described by `implement-phase.md`) calls the
decision script for orphan recovery and calls the helper directly only for
`merge-unverified`; the decision script calls the helper; the helper touches only the
journal. No layer calls upward.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| SC-1: journal helper reason `merge-unverified` | Records a terminal `failed` event for a task whose journal says `merged` but whose merge failed ancestor verification | Invocation: `--journal <feature journal path> --task <task id> --reason merge-unverified`, never with `--launch-at`. Pre: the existing journal-path preconditions (file exists, not a symbolic link, never created). Decision is made inside the same exclusive lock as the replay of the task's own final event: final event `merged` → exactly one `failed` line appended with fields in the order event, task, at, reason (reason `merge-unverified`), outcome `appended`; any other final event (`launched`, `failed`, none, any other name) → no write, outcome `noop_terminal`, journal byte-identical. `--launch-at` supplied together with `merge-unverified` → usage error (non-zero exit, empty stdout, journal untouched, decided before the journal is opened). Outcome vocabulary (`appended` \| `noop_terminal` \| `launch_changed`), exit-code contract, and the `orphaned` / `stale-launched` decisions are unchanged. Post: at most one `failed` line per `merged` final event under concurrent invocations | task0001 (builds), task0004 (describes the orchestrator's invocation in I.2.b step 1 and its effect in I.2.a / I.2.c), task0005 (records the reason value in the writer-set paragraph) |
| SC-2: evidence-chain artifact step | Treats the caller's worktree / branch observations as evidence, not as a chain terminator | `--worktree-present` and `--branch-present` each exactly `yes` or `no` (case-sensitive) → accepted as observed evidence and the chain proceeds to its remaining, unchanged steps; `no` never ends the chain by itself. Either input absent, or any other token → residual `task-artifacts-missing`, decided before any agent-index read, path assembly or file open. `--task-worktree` carries the task's expected worktree path (`$WT_ROOT/{T}`) whether or not that path exists, compared as a plain string with the Agent index entry's recorded worktree in the identity-binding step. The closed SC6 set stays exactly sixteen codes with `task-artifacts-missing` at its fixed position; the legacy chain (no evidence input) is unchanged and consults no artifact input | task0002 (builds), task0003 (describes in I.2.b's Same-session extension and invocation contract) |
| SC-3: single helper exception for orchestrator-caused journal writes | Frames every orchestrator-caused journal write as one exception | Exactly one exception exists to "the orchestrator never writes the journal": `em-workflow/scripts/journal-append-failed.py`. Its invocation sites are exactly three, all inside I.2.b step 1: the orphan-recovery attempt's legacy chain (reason `orphaned`, invoked by `recover-orphaned-task.py`), its extended same-session branch (reason `stale-launched`, invoked by `recover-orphaned-task.py` with a launch identity), and the ancestor-check branch (reason `merge-unverified`, invoked by the orchestrator directly, no launch identity). No sentence in either document claims the orphan-recovery attempt is the only orchestrator-caused append. The journal writer enumeration stays exactly five names; `merge-unverified` adds no writer. The Status semantics bullet gains no exception | task0004 (implement-phase.md: orphan block, Journal bullet, Stale-`launched` caveat), task0005 (workflow-schema.md writer-set paragraph) |
| SC-4: citation label for the ancestor-check branch | Gives the new invocation site one stable name | task0004 places the `merge-unverified` invocation inside I.2.b step 1's ancestor-check bullet (the bullet that runs `git merge-base --is-ancestor`). Other documents cite it as "`em-workflow/references/implement-phase.md`'s I.2.b step 1 ancestor-check branch" and never restate its content. The existing label "I.2.b Recovery / Residual block" keeps naming the orphan-recovery attempt | task0004 (creates the site), task0005 (cites it) |
| SC-5: agent index reader set | States who reads `agents.jsonl` and what an absent or stale index costs | Readers: `queue_taskstop_net.py` at stop; `queue_failure_net.py`'s agent-index fallback; the orchestrator's I.2.b step 1 Agent index lookup and Recovery through the Supporting cast "Orchestrator-side read" rule (the rule itself stays in `implement-phase.md`); `recover-orphaned-task.py`. For a stale `launched` task with a missing artifact, the orchestrator's lookup is keyed by task id and needs no worktree. An absent or stale index degrades the stop-tool recorder to a no-op, leaves the failure net's fallback unresolved, and leaves I.2.b step 1's not-live determination unresolved for a stale `launched` task — that consequence is owned by `implement-phase.md` I.2.b and only cited from the schema | task0003 (describes the orchestrator-side lookup for missing-artifact tasks), task0005 (states the reader set in workflow-schema.md) |

## Conventions

1. **Citation, not restatement**: a document names the owning section by
   repository-relative path and does not copy its rule. This applies between
   `implement-phase.md` and `workflow-schema.md`, and between sections of
   `implement-phase.md`.
2. **SC6 placement (NFR4)**: backtick-quoted SC6 residual reason codes appear only in
   I.2.b of `implement-phase.md`; never in `workflow-schema.md` or the README. New
   prose added by this feature names no SC6 code except inside the Same-session
   extension's own evidence steps, so the six codes keep their fixed first-occurrence
   order within I.2.b.
3. **I.2.c constraints (NFR2, NFR3)**: the I.2.c section (from its heading up to the
   Supporting cast heading) contains neither the substring `append` nor `rework`; its
   batch-mode paragraph stays byte-identical; its abort bullet is unchanged.
4. **Test-slicing markers stay unique and unchanged**: existing tests slice the
   documents at the literal strings below. They are not edited, and no new text
   contains any of them:
   - in `implement-phase.md`: `### I.2.b: Wake phase`, `### I.2.c: Failed handling`,
     `### Supporting cast`, `## Step I.3: Phase completion`, `**Resume**`,
     ``Stale-`launched` caveat``, `` Batch mode (`references/batch-mode.md` ``,
     `When the gate does not hold`;
   - in `workflow-schema.md`: `Its writer set is unambiguous`,
     `outside this one exception`.
5. **Minimal-diff editing of shared documents**: edit only the sentences a task owns;
   do not re-wrap, reflow or re-indent untouched lines. This keeps the two tasks that
   edit `implement-phase.md` mergeable without conflicts.
6. **Doc-contract test conventions (FR10, NFR8)**: standard library only;
   whitespace-normalized matching unless byte identity is the point; every literal is
   a module-level constant read by its positive test and by its negative proof; each
   absence assertion is paired with a negative proof run against a verbatim pre-change
   sample captured from the task's own base commit, plus a retained-anchor guard (a
   phrase present in both the sample and the live document) so the proof cannot pass
   vacuously.
7. **Pin-update discipline (FR10)**: a pre-existing assertion that contradicts the
   change is updated in the same task, never deleted without a replacement assertion;
   the test-method count of every modified module does not decrease; no test is
   skipped.
8. **Test-module ownership**: each task creates at most one new test module, with the
   name fixed in its task plan; no two tasks create or modify the same test module.
9. **Never modified**: `em-workflow/hooks/queue_launch_guard.py`,
   `em-workflow/scripts/merge-task.sh`,
   `feature-docs/routeback-admissibility-exits/reviews/round3.yaml`, and that feature's
   SPEC.md / REQUIREMENTS.md.
10. **Fail-safe direction (NFR5)**: doubt never produces a journal write; no
    elapsed-time or idle-interval threshold anywhere; artifact absence and a journal
    `merged` event are never treated as proof that an agent terminated; a recorded
    `session_id` is never a stop target or a match candidate.

## Cross-task Design Decisions

### D1: Missing-artifact stale `launched` tasks join the existing proof chain

A task whose journal last event is `launched`, with at least one of its worktree and
branch absent, and whose `Task()` call is not outstanding in this reconcile step, goes
through the same not-live determination as the both-present candidates, in the order
Agent index lookup → Recovery → Orphan recovery → Same-session extension. Artifact
absence is evidence only. Residual remains only when no proof is obtained. Rationale:
REQUIREMENTS.md 14.1 A1. Affected: task0002 (script), task0003 (protocol text).

### D2: `task-artifacts-missing` keeps its slot with a narrowed meaning

The code is not removed; it now means "artifact observation absent or unrecognized"
(SC-2). The closed sixteen-value set, its fixed order, and the step-order property
(decided before any read) are kept. Rationale: A4. Affected: task0002, task0003.

### D3: `merge-unverified` is a helper reason, not a new writer

The ancestor-check exit is expressed as a third additive value of the existing
`failed` reason field, written by the existing helper, accepted only over a locked
`merged` final event, and reported as `noop_terminal` when nothing is appended — no
new outcome value and no new exit code. Rationale: A2, A5, NFR1. Affected: task0001,
task0004, task0005.

### D4: `--launch-at` with `merge-unverified` is a usage error

The new reason has no launch-identity semantics. Supplying `--launch-at` with it is
rejected before the journal is opened (non-zero exit, empty stdout, journal
untouched), which keeps the fail-safe direction (NFR5) and stays inside the existing
exit-code contract (usage errors already exit non-zero with no write). Affected:
task0001 (behaviour), task0004 (the protocol text invokes the helper without a launch
identity).

### D5: The SSOT stays unconditional

`workflow-schema.md`'s Status semantics ("A `failed` task resolves ONLY by retry or by
routing back to planning") is not edited and gains no exception; after this feature
no protocol text describes an exit outside retry / route back to planning / abort.
Orchestrator-caused journal writes are framed as one helper exception (SC-3).
Affected: task0004, task0005.

### D6: The orchestrator-read rule stays in the Supporting cast

The Agent index "Orchestrator-side read" rule remains in `implement-phase.md`'s
Supporting cast; the schema only names the orchestrator as a reader (SC-5). Rationale:
A6. Affected: task0003, task0005.

### D7: Region ownership inside `implement-phase.md`

- task0003 owns: in I.2.b step 1's first bullet, the block that currently begins "A
  second, independent condition triggers this same recovery"; the Orphan recovery
  paragraph's opening candidate description; the Same-session extension's artifact
  evidence step; the invocation contract's `--task-worktree` description.
- task0004 owns: I.2.a's ancestor-check retry sentences; I.2.b step 1's ancestor-check
  bullet; the Orphan recovery paragraph's "This is the ONLY case ..." sentence; I.2.c's
  ancestor-failure paragraph; the Supporting cast Journal bullet's exception clause;
  the Stale-`launched` caveat's exception sentence; the README journal description.
- Neither task edits the other's regions.

### D8: `bc57aa350bb027c7` is resolved by pinning, not by rewriting

The candidate-set predicate ("whose `Task()` call is not among this reconcile step's
own currently-outstanding calls") is not session-keyed, and the Same-session extension
already reaches a `stale-launched` journal `failed`; the prose is left as is and a new
doc-contract test pins the predicate with a negative proof against the loop-2 wording.
Affected: task0003.

### D9: Version bump in one task

em-workflow goes from 0.2.10 to 0.2.11 in both registries inside task0006 alone.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| task0003 and task0004 conflict when both merge into `implement-phase.md` | Medium | Medium | D7 region ownership; Convention 5 (no re-wrapping); parent-side adoption on conflict |
| New I.2.b prose mentions an SC6 code early and breaks the first-occurrence order pinned by `tests/test_stale_launched_doc_contract.py` | Medium | Low | Convention 2 |
| A rewritten sentence drops a phrase pinned by an existing module (`test_implement_routeback_gate.py`, `test_stale_launched_doc_contract.py`, `test_subagentstop_failure_net_doc_contract.py`) | Medium | Medium | Retained-literal lists in each task plan; full suite run by every implementer |
| The verbatim loop-2 wording needed for the FR3 negative proof cannot be located | Low | Low | task0003 takes it verbatim from commit `0d9d0dc4` |
| The schema's citation label does not match the text task0004 writes | Low | Medium | SC-4 fixes the label; review checks the pair |
| `em-workflow/README.md` claims the orphan-recovery attempt is the only orchestrator-caused journal write | Confirmed | Low | task0004 edits it |

## Open Questions

- [x] `em-workflow/README.md` line 104 states that the orphaned `launched` residue is
      the only case where the orchestrator appends `failed` via the helper; task0004
      edits it.
