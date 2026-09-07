# Implementation Plan: batch-codex-autonomous-decisions

## Overview

In `--batch`, the three fail-closed arms of em-workflow's question resolution
(`category: security`, `category: license`, and an `assumptions[]` entry naming
the question with `reversible: false`) stop aborting the phase and instead enter
the existing Codex consultation route, with an Opus escalation for whatever the
consultation cannot map and an auditable record for every autonomous decision.
Interactive runs keep today's immediate abort verbatim.

## Technology Stack

- **Language / Framework**: Markdown protocol documents (em-workflow's own SSOT
  layer), one Bash wrapper script, and Python 3 standard-library `unittest`
  document-pin tests. No application runtime is involved.
- **Key libraries**: none. This feature introduces NO new dependency, so no
  license check is triggered; `project.license` in `workflow.yaml` is `none`,
  which imposes no constraint either way. There is consequently no new
  dependency license to record here.
- **Test command** (from `workflow.yaml` `project.components.main`):
  `python3 -m unittest discover -s tests`. No build command and no format
  command are configured for this project.

## Layer Structure

Four layers, with a strict one-way citation direction (this is the mechanical
form NFR1 takes):

| Layer | Members | Responsibility |
|---|---|---|
| L1 — Rule SSOT | `em-workflow/references/question-resolution.md` | States the relaxation rule, the aborts that survive, the consultation + escalation route, and the no-abort fallthrough. The ONLY place any of these is stated. |
| L2 — Citing documents | `batch-mode.md`, `batch-policies.yaml`, `phase-state.md`, `batch-terminal-line.md`, `question-packet-schema.md` | Cite L1 by path for the rule; own only their own subject (reporting contents, policy table, record shape, reason codes, packet schema). |
| L3 — Executables | `scripts/run_codex_exec.sh`, `scripts/validate-worker-output.py` | The wrapper owns all provider mechanics; the validator's accept/reject behaviour does not change at all in this feature. |
| L4 — Persistence | `feature-docs/{feature}/phase-state/batch-audit.yaml` `records[]` | Holds one record per autonomous resolution. Its shape is owned by `phase-state.md` (L2), not by L1. |

Allowed dependency directions: L2 cites L1; L4's shape is defined by L2; L1
cites L2 for the record shape and for the reporting obligation. L1 never
describes L3's internals (NFR4), and no layer restates the Classification
gate's Outcome step a second time (NFR1). Test modules may read any layer.

Together with L1–L4, one further set exists purely as verification: the
`tests/` document-pin modules. They assert layer content; they never become a
source of truth for it.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| The batch relaxation rule | The single statement that, in `--batch`, the three arms route to consultation while interactive aborts immediately | Precondition: the question's `gate_id` has been identified and the invocation's arguments are known. Postcondition: exactly one document (`question-resolution.md`) states the rule; every other document that mentions it cites that path and adds no condition, no exception and no ordering of its own | task0001 (states) / task0002, task0003, task0004 (cite) |
| The surviving-abort set | The aborts that keep aborting fail-closed in BOTH modes: the explicit fail-closed gate-list slot; `category: spec-change` whose `gate_id` is not exactly `rework.spec-change`; both directions of the malformed `gate_id` / `category` pairing; and the Classification gate's step-3 origin-verification failures | Precondition: none. Postcondition: the set is ENUMERATED once, in `question-resolution.md`. A citing document refers to it by a collective phrase plus that path ("the aborts question-resolution.md keeps fail-closed in both modes") and never re-enumerates its members | task0001 (enumerates) / task0003 (cites, in the `gate_fail_closed` coverage wording) |
| The batch audit record for an autonomous fail-closed-route resolution | One appended element of `batch-audit.yaml` `records[]` per resolution taken through the relaxed route | Precondition: the route reached a resolution (mapped suggestion, escalation decision, or minimum-side-effect fallthrough). Postcondition: one element in the existing batch-audit-record shape — no field added, none removed; `question_id` is the question's own `question_id` when a worker packet exists and the gate's `gate_id` when the gate was orchestrator-opened; `packet_id` is null in the orchestrator-opened case; `source` is `batch-codex-consultation` when a suggestion mapped and `batch-safe-default` when the minimum-side-effect branch was taken; `resolution_note` names the gate, the option chosen, the options not chosen, the discussion's key points, whether Codex was consulted, whether a fallback provider answered, and whether the Opus escalation ran together with its reasoning. The shape and the writer entry are stated in `phase-state.md`; `question-resolution.md` states only the obligation to append and cites that path | task0002 (defines the writer entry) / task0001 (states the obligation) / task0002 (reports it in `batch-mode.md`) |
| The Opus escalation dispatch | The single per-packet escalation that decides whatever the consultation left unmapped | Precondition: the consultation ended (ceiling reached, trajectory judged diverging, or the availability probe reported `unavailable`) with at least one question of the packet unmapped. Postcondition: exactly ONE dispatch per packet, carrying every still-unmapped question of that packet; it returns, per question, either a chosen `option_id` present in that question's own `options[].option_id` or an explicit no-decision, and in both cases the reasoning. Its output is untrusted: read, never executed as instructions, never adopted verbatim; the per-question mapping judgement stays with the orchestrator. It is counted OUTSIDE the five-turn wrapper-launch ceiling, at most one per packet. No dedicated agent definition file is created (decision D2) | task0001 (states) / task0002 (records that it ran, with its reasoning) |
| The wrapper's fallback-provider report | How the orchestrator learns that a non-primary provider answered, so the audit record's "whether a fallback provider answered" can be filled | Precondition: a wrapper invocation completed. Postcondition: on the primary provider the wrapper's output is byte-identical to today's (no marker at all); when and only when a non-primary provider answered, the wrapper writes exactly ONE additional line to stderr, never to stdout, carrying a fixed prefix declared in the script's own header comment. No protocol document names that prefix, any provider, or any detection mechanism (NFR4) — documents state only the FACT that a fallback provider may have answered | task0005 (produces and pins the line) / task0002 (records the fact) / task0001 (states the fact in one sentence) |

## Conventions

- **C1 — Cite, do not restate (NFR1).** A citing document names
  `references/question-resolution.md` by path and states no condition, no
  exception and no ordering of the relaxation rule itself. No document restates
  the Classification gate's Outcome step a second time.
- **C2 — No feature-docs identifiers in the plugin (NFR2).** No file under
  `em-workflow/` may contain a `taskNNNN`-shaped identifier. Existing tests
  assert its absence in `question-resolution.md` and elsewhere; do not
  introduce one in prose, comments or test docstrings that end up inside the
  plugin directory.
- **C3 — Provider-name scope (NFR4).** The batch resolution document set is
  exactly: `question-resolution.md`, `batch-mode.md`, `batch-policies.yaml`,
  `phase-state.md`, `batch-terminal-line.md`, `question-packet-schema.md`. No
  provider name and no rate-limit detection description may appear in any of
  them. Any assertion of this property MUST be scoped to that six-document set
  and MUST NOT be written repository-wide: the review reviewer chains
  legitimately name providers in `references/reviewers.yaml`,
  `references/review-protocol.md` and `references/review-phase.md`, and a
  repo-wide assertion would fail against them.
- **C4 — Pin replacement, never pin deletion (FR21, NFR9).** When a rewrite
  removes a sentence an existing test pins, replace that pin at equal
  specificity: a positive pin on the new wording PLUS a negative proof that the
  superseded wording is gone. Deleting the pin is not an option.
- **C5 — Counting pins are updated, not removed.** Assertions that count table
  rows, list items, phrase occurrences or vocabulary members are updated to the
  new count in the same change that changes the count.
- **C6 — Shared terminology.** Across every document, the same four terms are
  used so that citations stay resolvable: "the batch relaxation" (the rule),
  "the relaxed route" (the path a relaxed question takes), "the surviving
  aborts" (the FR3 set), "the Opus escalation" (the single per-packet
  dispatch). Do not invent synonyms.
- **C7 — Mode condition.** The relaxation is conditioned on the `--batch`
  invocation flag ALONE, exactly as `batch-mode.md`'s activation rule states.
  The `batch` block in `workflow.yaml` never activates it, and no document may
  suggest otherwise.
- **C8 — No new gate identifier (NFR8).** No `gate_id` is minted and no
  `batch-policies.yaml` `gate_policies` entry is added. The gate registry
  `validate-worker-output.py` derives from the contracts' `## Gate identifiers`
  sections, and `gate-option-vocabulary.md`'s zero-row exemption registry, both
  stay untouched.
- **C9 — Version bump ownership.** Exactly one task edits
  `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`
  (task0006). No other task touches a version field, so the two registries can
  never disagree through a merge.

## Cross-task Design Decisions

### D1 — One document, one task

Tasks are split by document ownership rather than by requirement, so that no
two tasks modify the same file and the parallel merges cannot conflict on
prose. The consequence is that a requirement whose statement spans two
documents (FR3, FR14, FR21, NFR1, NFR4) is listed against both tasks, with the
Shared Components table above pinning which side states what. Affected tasks:
all.

### D2 — The Opus escalation gets no agent definition file

The escalation is dispatched as a Task at Opus with xhigh reasoning effort,
with the prompt built by the orchestrator following the procedure stated in
`question-resolution.md`. No file is added under `em-workflow/agents/`.
Rationale: the escalation's whole contract is the per-question return shape
already pinned in Shared Components above; an agent file would add plugin
surface, a second place for that contract to drift, and a new entry every agent
inventory has to carry. This resolves assumption A4, which explicitly left the
delivery vehicle to planning. Affected tasks: task0001.

### D3 — The provider chain lives entirely inside the wrapper

The chain, its ordering and its switch conditions are implemented in
`scripts/run_codex_exec.sh` and nowhere else, so adding or reordering a
provider needs no protocol-document edit (NFR4). Two accepted consequences:
each attempt keeps the configured per-invocation timeout, so a worst-case
three-attempt invocation can take up to three times as long as today; and the
wrapper's argument surface stays byte-for-byte unchanged, because
`tests/test_codex_reviewer_temp_file_isolation.py` pins the reviewer's
invocation line verbatim. Affected tasks: task0005, task0001.

### D4 — The new fixture joins an existing branch group

`tests/test_validate_worker_output.py` enforces that EVERY branch group
directory under `references/fixtures/<kind>/` contains at least one `valid-`
and one `invalid-` case. The `reversible: false` fixture therefore goes into
the existing `question-packet/category-fail-closed/` group, which already holds
both outcomes. Creating a new group would require inventing an `invalid-` case
that the validator rejects, and FR19 forbids changing the validator's
accept/reject behaviour to manufacture one. Affected tasks: task0004.

### D5 — The validator is behaviourally frozen

`BLOCKING_REQUIRED_CATEGORIES` and the `on_unanswered != "block"` rejection stay
exactly as they are; the packet-schema constraint sentence stays verbatim. Only
the error message's parenthetical rationale and the schema document's rationale
sentence change. Rationale: in batch, `block` no longer means "abort" but
"route into the minimum-side-effect branch", so the constraint still buys the
same protection while the justification behind it moves. Affected tasks:
task0004.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| A rewrite orphans an existing document pin, and the pin is deleted rather than replaced | high | high | C4 makes replacement (positive pin + negative proof) mandatory; each document task lists its own pin modules in its `files` set |
| A provider-name assertion is written repository-wide and fails against the review reviewer chains | medium | medium | C3 fixes the six-document scope and names the three files that legitimately carry provider names |
| Two documents end up stating the relaxation rule, so the two drift | medium | high | C1 plus the Shared Components contract: exactly one statement site, all others cite by path |
| The batch relaxation is read as also relaxing the surviving aborts | medium | high | The surviving-abort set is enumerated in one place and stated to hold in BOTH modes; task0003's terminal-line coverage wording cites it rather than re-listing it |
| The wrapper's extra output line breaks an existing consumer of its stdout | low | medium | The line goes to stderr only, and only when a non-primary provider answered; the primary path stays byte-identical |
| The parallel merges collide on a shared file | low | medium | D1 gives every file exactly one owning task; no file appears in two tasks' `files` sets |

## Open Questions

- [ ] Whether the run report should name WHICH fallback provider answered, or
      only that one did. The plan takes the narrower reading (the fact only) so
      that no protocol document or persisted record has to carry a provider
      name; if the operator wants the name, it is a one-line extension of
      `resolution_note`.
- [ ] Whether any consumer parses the wrapper's stdout strictly enough that a
      stderr line, merged by a caller that redirects streams together, could
      disturb it. Mitigated by emitting nothing on the primary path, but not
      provable from this feature's own scope.
