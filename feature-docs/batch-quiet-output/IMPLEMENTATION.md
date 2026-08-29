# Implementation Plan: batch-quiet-output

## Overview

Narrow `/em-workflow:develop --batch`'s main-context output to the two
surfaces a headless caller reads, by defining one new output-suppression
discipline inside `em-workflow/references/batch-mode.md` and having every
other affected document point at it. There is no runtime component: the
change set is protocol documents, the two plugin manifests, and one new
document-contract test module per task.

## Technology Stack

- **Format**: Markdown protocol documents under `em-workflow/`; JSON plugin
  manifests (`em-workflow/.claude-plugin/plugin.json`,
  `.claude-plugin/marketplace.json`).
- **Tests**: Python standard-library `unittest` modules under `tests/`,
  discovered by `python3 -m unittest discover -s tests`. This repository's
  established form for a documentation/protocol change is a test module that
  asserts document text (see `tests/test_batch_stop_contract.py`,
  `tests/test_batch_stop_contract_skill_wiring.py`).
- **New dependencies**: none. No library is added, so no license check is
  triggered; `project.license` is `none` and stays `none`.

## Layer Structure

Four layers, one permitted dependency direction — pointer → SSOT. A pointer
document never points at another pointer document for this discipline, and
the SSOT never depends on a pointer document.

| Layer | Files | Responsibility |
|---|---|---|
| Discipline SSOT | `em-workflow/references/batch-mode.md` | The ONLY definition of the batch output-suppression discipline: activation condition, suppressed scope, exceptions, the non-terminal marker line, the audit-item source map (FR12, NFR4) |
| Pointer layer | `em-workflow/skills/develop/SKILL.md`, `em-workflow/references/implement-phase.md`, `em-workflow/references/review-phase.md`, `em-workflow/references/phases/create-spec-phase.md`, `em-workflow/references/phases/create-plan-phase.md` | Apply the discipline at their own sites BY REFERENCE; never restate the marker format or the suppressed scope |
| Frozen contract | `em-workflow/references/batch-terminal-line.md` | The terminal line. Its prefix, field grammar, value domains, reason codes, stop-point table and emission conditions are unchanged (FR7). A single non-normative cross-reference sentence is the only permitted edit |
| Packaging | `em-workflow/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` | Version parity (FR13) |

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|---|---|---|---|
| Non-terminal marker line (D1) | The single line a non-terminal batch turn emits | Defined ONLY in batch-mode.md. Prefix literal `EM_WORKFLOW_PROGRESS:` followed by one ASCII space, then exactly two `key=value` fields in fixed order: `phase`, then `point`. `phase`'s value is the `workflow.yaml` step id in effect for that turn (domain owned by `references/workflow-schema.md`); `point`'s value is one of the closed set `wait` / `launch` / `wake`. No space around `=`; a single ASCII space separates the two fields; always exactly one physical line. Precondition: the turn ended without the run reaching any terminal state the terminal-line contract defines. Postcondition: the turn's final assistant message consists of this line and nothing else | task0001 (defines), task0002 / task0003 (emit sites, by reference; must NOT contain the prefix literal) |
| Marker / terminal non-collision (D2) | Keeps the terminal-line contract's "no line = abnormal outcome" signal intact | Neither prefix is a prefix of the other, so a consumer matching the terminal-line prefix never matches a marker line. batch-mode.md states this property by naming `references/batch-terminal-line.md`, never by reproducing that document's prefix literal (see D6) | task0001, task0002, task0003 |
| Pointer convention (D3) | How a pointer document applies the discipline | A pointer site names `references/batch-mode.md` (SKILL.md uses its own `${CLAUDE_PLUGIN_ROOT}/references/batch-mode.md` convention) and states only WHERE the rule applies — never the marker prefix, never its fields, never the suppressed-scope list, never an exception list | task0002, task0003 |
| Audit-item source map (D4) | Every audit item batch-mode.md "Reporting" requires resolves to a persisted source, so Step C's report survives suppression | Auto-rework counts consumed ← `workflow.yaml`'s `batch` block. Recorded assumptions and unlisted-gate fallback resolutions ← `feature-docs/{feature}/phase-state/*.yaml` `answers` / resolution notes. Deferred findings with `stable_id` ← `feature-docs/{feature}/reviews/roundN.yaml` `resolution` / `stable_id`. Auto-approved command strings ← the phase-state record of the `create-spec.command-approval` gate resolution, which Step A.5's batch branch writes when it auto-records (this is FR11's "newly defined source"; it uses the existing `answers` entry shape, so `references/phase-state.md` needs no schema change and is NOT in any task's file set). Kept integration branch name ← `workflow.yaml` `parent_branch` plus the feature name | task0001 (defines the map), task0002 (Step A.5 write site + Step C assembly) |
| Declined-deviation audit channel (D5) | implement-phase.md's wake-phase obligation to list an admitted/declined `files` deviation stays satisfiable once the wake turn emits only the marker line | The admission's audit record is unchanged (the appended `files` entry plus the wake commit). A DECLINE's record moves from the wake turn's main-context report to the wake commit's message, from which Step C's batch report assembles it. No file artifact's content changes, so FR9 holds. **Superseded by D9** (rework round 1, finding `9d1f4e6a2c8b0537`): the decline's record moves to D9's persisted file instead of the commit message; the admission's record and the interactive behaviour are unaffected | task0003 (records it), task0002 (Step C reads it), task0005 (moves it to D9) |
| Batch audit record file (D9) | The one persisted home for the batch audit records no per-phase phase-state file owns | `feature-docs/{feature}/phase-state/batch-audit.yaml`, one per feature, not owned by a single phase — the same exemption `references/phase-state.md` already grants `backfill.yaml`. Holds: an `answers`-shaped entry per non-packet unlisted-gate fallback resolution (gate site / options / choice / Codex consulted or not, in `resolution_note`), and one entry per declined `files` deviation (`task_id` + which of the three evidence parts failed). Reuses the existing `answers` entry shape, so no per-phase schema field changes. Append-only. Written at resolution time; committed by an existing `commit-docs.sh` call (the wake commit for a decline) and never the cause of an additional commit. Read by Step C through batch-mode.md's source map and implement-phase.md's decline pointer | task0005 (defines it in `phase-state.md`, points batch-mode.md's source map and the two Non-packet gates rows at it, writes it from implement-phase.md's wake step); task0002's Step C assembly reaches it unchanged, through the pointers it already follows |
| Existing-guard constraints (D6) | The pre-existing test modules that already pin these files must stay green | (a) `EM_WORKFLOW_TERMINAL:` must not appear in `batch-mode.md` or `SKILL.md` (whole-file absence guards). (b) The terminal-line contract's eleven reason codes, the `no-step` sentinel, the four field names as a backticked group, any `state={value}` shape and the bare `phase_done` literal must not appear anywhere in those two files. (c) batch-terminal-line.md's seven level-2 headings and their order are pinned by exact equality — no heading may be added, removed, renamed or reordered. (d) batch-mode.md's Non-packet gates table must keep exactly ten data rows and its catch-all wording; `## Terminal line` and `## Reporting` must keep their headings and relative order | task0001, task0002, task0003 |

## Conventions

- **Test module per task**: each task adds exactly one new module named
  `tests/test_batch_quiet_output_{aspect}.py`. No task edits another task's
  module or any pre-existing module — that is what keeps four parallel
  worktrees conflict-free. Standard library only; no cross-module import
  (a module re-declares any constant it needs locally, matching this
  repository's existing convention).
- **Matcher discipline**: every NEW matcher a test module introduces carries
  a negative proof (a forged sample it rejects) plus a non-vacuity guard
  (the forged sample is well-formed and actually found). Pure regression
  guards over retained pre-change wording are exempt.
- **Document language**: each edited file keeps its own language —
  `references/*.md` is English, `skills/develop/SKILL.md` is Japanese
  (タメ語・一人称「私」・体言止めなし, NFR5). The marker line and the
  terminal line are machine formats and sit outside the voice rule.
- **No new gate**: this feature introduces no `gate_id`, no policy entry and
  no AskUserQuestion site. A pointer edit must not add a `gate_id` mention.
- **Reference-only edits**: an edit that exists solely to point at the
  discipline adds sentences; it never rewrites, reorders or deletes an
  existing rule, table row or heading.

## Cross-task Design Decisions

### D1 — Marker prefix and fields are fixed by this plan

The SPEC fixes the constraints and leaves the literal to implementation.
Three tasks need the same literal at the same time (one to define it, two to
assert its absence from their pointer documents), so it is fixed here
instead: prefix `EM_WORKFLOW_PROGRESS:`, fields `phase` then `point`, values
as in Shared Components. Rationale: it shares the `EM_WORKFLOW_` namespace so
a consumer can filter em-workflow lines, while neither prefix is a prefix of
the other (D2). Two closed-vocabulary fields carry no free text at all, which
satisfies FR3's confidentiality constraint by construction. Affects
task0001, task0002, task0003.

### D2 — Non-collision is stated by reference, not by literal

FR3 requires the marker prefix to be distinguishable from the terminal-line
prefix, but a pre-existing whole-file guard forbids the terminal prefix
literal from appearing in `batch-mode.md`. The discipline therefore states
the property relationally ("the marker's prefix is not the prefix
`references/batch-terminal-line.md` defines, and neither is a prefix of the
other"). TS-3's "confirm from both SSOT documents" is realized in task0001's
test module — a test module, not a protocol document, may hold both
literals. Affects task0001.

### D3 — New section placement in batch-mode.md

The discipline goes into ONE new level-2 section, added as the document's
LAST level-2 section (after `## Reporting`). Rationale: a pre-existing test
slices `## Terminal line` → `## Reporting`; appending at the end leaves every
existing slice, the ten-row gates table and the Terminal line section
untouched. `## Reporting` gains one pointer sentence to the new section's
audit-item source map, and its audit-item list is otherwise unchanged (FR5).
Affects task0001, and task0002/task0003 which point at that section.

### D4 — Audit items are sourced from persisted state

See Shared Components. The one item without a persisted source today is the
set of auto-approved command strings, because Step A.5 runs outside any
phase dispatch and only presented them in the running output — exactly what
FR4 now suppresses. FR11's "the source is newly defined" is satisfied by
having Step A.5's batch branch record the gate resolution into the feature's
phase-state using the existing `answers` entry shape, so no phase-state
schema change is needed and `references/phase-state.md` stays out of the
change set. Affects task0001 (map) and task0002 (write site + assembly).

Amended by D9 (rework round 1): the auto-approved command strings were not
the only item lacking a persisted source — the non-packet unlisted-gate
fallback resolutions lacked one too, and D9 supplies it. This row's mapping
of that item to `phase-state/*.yaml`'s `answers` / resolution notes is
unchanged and is what D9 makes true; `references/phase-state.md` enters the
change set with D9's file definition (task0005).

### D5 — Declined-deviation records move to the wake commit message

`implement-phase.md`'s wake phase currently records a DECLINED `files`
deviation only in that wake turn's own report. Once the wake turn emits only
the marker line, that record would vanish, contradicting the same document's
requirement that a batch run also list it in the run report (NFR4 forbids
leaving that contradiction). The record moves to the wake commit's message —
a committed, persisted channel that changes no file artifact's content,
frequency or timing, so FR9 holds. Affects task0003 (writes it) and task0002
(Step C's report assembles from it).

### D6 — Existing test modules are the compatibility floor

Every pre-existing module under `tests/` must stay green with its assertions
unmodified; a task that finds itself wanting to weaken one has mis-scoped its
edit. The specific pins are listed in Shared Components (D6). Affects
task0001, task0002, task0003.

### D7 — Stop/abort exceptions are stated as a set-level rule

FR6's stop and abort turns coincide exactly with the stop points
`batch-terminal-line.md`'s stop-point coverage table binds to a reason code.
The discipline states the exception once, over that table as a set, instead
of enumerating stop points or reason codes — enumerating reason codes would
also break D6(b). TS-4's eleven-row coverage is then a property of the
set-level rule. The pointer documents refer to that same single rule rather
than repeating any part of the enumeration. Affects task0001, task0002,
task0003.

### D8 — The version bump is triggered by the other three tasks

task0001, task0002 and task0003 all change files under `em-workflow/`, which
is exactly what obliges this change set to raise the plugin version (project
rule `core-plugin-version-bump`); the bump is separated into task0004 only so
that the two manifests have a single owning worktree. Both registries
currently read `0.1.51`, and this is a behavioural fix, so both move to the
SAME next patch value on the `0.1.x` line. task0004's test module pins the
baseline (`patch > 51`, `(major, minor) == (0, 1)`, both registries equal as
strings) rather than a fixed literal, matching
`tests/test_batch_stop_contract_version_bump.py`. If task0001-0003 all ended
up merging without touching `em-workflow/`, the bump would be unnecessary —
that is the only condition under which task0004 is void, and it cannot occur
given their file sets.

### D9 — Both unowned batch audit records share one persisted file

Added by rework round 1 (findings `1cd0e6ab9dba1fef`, `48ac1e2b5f7d90c3`,
`b0f4c7d2e819a635`, `2a6b8f0c3d5e7192`, `9d1f4e6a2c8b0537`,
`7e3a95c14b0d82ff`). Two audit records had no phase-state file to live in —
the non-packet unlisted-gate fallback resolutions (the review diff-size gate
and the per-command approval fallback carry no `gate_id`, so no `answers`
entry is raised for them) and the wake phase's declined `files` deviations.
D4's original text routed the first to an unsuppressed output line and D5
routed the second to a batch-only commit message; both are volatile or
mode-divergent channels, contradicting FR11 (audit items come from committed
artifacts and persisted state), FR4/FR2 (a non-terminal turn emits one marker
line and nothing else) and FR9 (commits are unchanged between modes).

One file resolves both, because both are the same kind of record: a batch
decision that no phase owns. `phase-state/batch-audit.yaml` sits inside
FR11's own named source (`phase-state/*.yaml`'s `answers` /
`resolution_note`) and inside `commit-docs.sh`'s existing `ARTIFACT_PATHS`,
so it needs no script change and no per-phase schema change — it is exactly
FR11's "if any audit item has no persisted source, that source is newly
defined", taking `backfill.yaml`'s existing not-owned-by-one-phase shape as
its precedent. The fourth suppression exception and the batch-only wake
commit-message construction are removed with it, since each existed only to
carry one of these two records. Affects task0005; D4's unlisted-gate row and
D5 are amended accordingly.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| A new sentence in `batch-mode.md` / `SKILL.md` trips a pre-existing whole-file literal guard | Medium | High (suite red on merge) | D6 lists every pinned literal; each task's own module re-checks the whole-file guard for the files it owns |
| An external consumer misreads the marker as a terminal line | Low | High (a run reported as finished when in flight) | D1/D2 prefix choice + task0001's non-collision assertion over both documents (TS-3) |
| The discipline gets restated in a pointer document, breaking single-SSOT (NFR4) | Medium | Medium | D3 pointer convention; each pointer task's module asserts the marker literal and the scope list are absent from its own files |
| Suppression silently removes an audit item Step C needs (FR5/FR11) | Medium | High (a finished run becomes un-auditable) | D4 source map is written into the SSOT and asserted item-by-item (TS-5); D5 closes the implement-phase decline gap |
| Adding a heading to `batch-terminal-line.md` breaks its exact heading-list pin | Low | Medium | D6(c): the only permitted edit there is one sentence inside `## No line on a wait turn` |
| Two tasks edit the same document section and conflict at merge | Low | Medium | Each protocol file has exactly one owning task; test modules are one-per-task and new |

## Open Questions

- [x] D5 reads FR9 as constraining file-artifact content only, so a commit
      MESSAGE may carry the declined-deviation record. If review reads FR9 as
      covering commit messages too, the channel has to move (the only other
      candidate without a phase-state schema change is leaving the decline
      unreported in batch, which contradicts implement-phase.md).
      **Resolved by rework round 1** (finding `9d1f4e6a2c8b0537`): review read
      FR9 as covering the commit itself, so the channel moves to D9's
      persisted file — a third candidate this question had not considered,
      which needs no per-phase schema change either.
- [ ] D4 assumes Step A.5's batch auto-record can write the feature's
      phase-state at that point in the run (workflow.yaml exists by then, so
      the feature directory does). If it cannot, task0002 must report a plan
      deviation rather than invent a second source.
- [ ] FR2's "turns in scope include at least" leaves the list open. This plan
      fixes the scope at exactly the three named non-terminal turns (stop
      condition 5's wait, implement launch, implement wake); a fourth found
      during implementation is a plan deviation, not a silent addition.
