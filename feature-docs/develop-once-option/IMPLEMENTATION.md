# Implementation Plan: develop-once-option

## Overview

`--once` is a per-invocation flag for the `develop` skill that ends the turn
after exactly one phase. The change is documentation-only (NFR2): prompt and
reference Markdown, their structural test modules, and two JSON `version`
fields. This document records only the decisions that span more than one
task; everything task-local lives in `tasks/taskNNNN.md`.

## Technology Stack

- **Prompt / reference documents**: Markdown under `em-workflow/`
  (`skills/develop/SKILL.md`, `references/batch-mode.md`,
  `references/batch-terminal-line.md`).
- **Manifests**: JSON (`em-workflow/.claude-plugin/plugin.json`,
  `.claude-plugin/marketplace.json`).
- **Verification**: Python 3 standard-library `unittest`, repository-root
  `tests/`, discovered by `python3 -m unittest discover -s tests`
  (`test/README.md`).
- **New dependencies**: none. Test code imports the standard library only.
  `project.license` is `none`, so no license constraint applies to this
  feature; no dependency license needs recording.

## Layer Structure

Three documentation layers plus one enforcement layer. The partition between
them is itself a requirement (NFR1, FR9) — information flows downward only:

| Layer | File | Owns |
|---|---|---|
| Prompt | `em-workflow/skills/develop/SKILL.md` | argument handling, phase-boundary definition, stop conditions, WHEN the terminal line is emitted, the interactive closing line |
| Pointer | `em-workflow/references/batch-mode.md` | naming the contract document, WHEN the line is emitted |
| Contract SSOT | `em-workflow/references/batch-terminal-line.md` | prefix, field grammar, every value domain (`state` / `step` / `reason` / `detail`) |
| Enforcement | `tests/` modules | structural/textual assertions over the three documents and the two manifests |

Allowed dependency direction: Prompt and Pointer may NAME the Contract SSOT
and instruct reading it; neither may restate any literal it owns. The
Contract SSOT never depends on the other two. The enforcement layer reads
all of them.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|---|---|---|---|
| Terminal-line `state` domain | The closed set of terminal-line `state` values | Domain is exactly `completed`, `stopped`, and the `--once` phase-boundary value `phase_done` (D1). Precondition for emitting `phase_done`: the batch turn ended at a `--once` phase boundary (D5). Postconditions: `reason` is `none`, `detail` is a non-empty single physical line, prefix and the four fields and their order are the existing ones, and the consumer re-launches the same feature. Defined in `em-workflow/references/batch-terminal-line.md`; every other document refers to the set without naming a member | task0002 (absence checks only), task0003 (defines) |
| Contract-literal guard rule, `state`-value scope | The rule both pointer guards implement to enforce FR9 mechanically | For each value of the `state` domain, the contract-specific shape `state={value}` (bare, backticked or quoted) must be absent; additionally the `--once` boundary value's bare literal must be absent. Bare `completed` / `stopped` / `skipped` are NEVER flagged — both pointer documents use them as ordinary `workflow.yaml` step-status vocabulary. Scope: the whole file, for both `SKILL.md` and `batch-mode.md`. The pre-existing checks (prefix literal, four field-name tokens as a group, reason codes, sentinel) keep their current scope and semantics (D2) | task0002 (`tests/test_batch_stop_contract_skill_wiring.py`), task0003 (`tests/test_batch_stop_contract.py`) |
| SKILL.md region ownership | Which task edits which region of the one file two tasks share | task0001 owns the frontmatter, 「引数処理」, 「ターンを終わらせていい唯一の条件」 and the new `--once` section; task0002 owns the body of 「## バッチ終端行」 and nothing else. Placement invariants in D3 hold after both merges | task0001, task0002 |
| Terminal-state cardinality rule | Keeps every count-bearing sentence true after a third value exists | No document states how many terminal states exist. The Contract SSOT enumerates the set; every other document refers to "the terminal states the SSOT defines" without a count and without naming a member (D4) | task0002, task0003 |
| Phase-boundary set and `step` semantics | The shared meaning of "one phase" | Four boundary kinds (D5), each ending the turn only after the state change is committed. The terminal line's `step` always names the step EXECUTED in that turn — `verify` at the verify-fail rework boundary — never the step the next launch resumes at | task0001 (defines the boundaries), task0003 (states the `step` rule) |
| Test-module ownership map | One owner per test module, so no two tasks edit the same module | D6's table. A task that must change a module it does not own reports a plan deviation instead of editing it silently | all tasks |

## Conventions

- **Naming**: prose in the `em-workflow/` documents keeps each file's
  existing language — Japanese in `skills/develop/SKILL.md`, English in
  `references/batch-mode.md` and `references/batch-terminal-line.md`.
- **SSOT partition**: a pointer document names the contract document and
  instructs reading it immediately before emitting; it states only WHEN the
  line is emitted. It never carries the prefix, a field grammar, a reason
  code, the sentinel, or a `state` value.
- **Test conventions** (NFR3): new modules live in the repository-root
  `tests/` as `test_*.py`, import the standard library only, and carry a
  `TestOwnModuleStdlibOnly`-style self-check when they are new. Every new
  MATCHER (a helper function encoding a judgment) carries a negative proof
  plus a non-vacuity guard. Plain presence/absence assertions over retained
  wording are pure regression guards and are exempt, per the convention the
  existing modules record.
- **Whitespace handling in assertions**: the Japanese documents hard-wrap
  without a space at the break, so multi-token phrase assertions strip all
  whitespace from both sides (the existing `_strip_ws` convention) rather
  than collapsing runs to one space.
- **Error handling policy**: no error codes are introduced. Every failure
  mode in scope is a test failure over document text.
- **Cross-module isolation**: test modules never import each other. A shared
  constant (the `state` domain, the reason codes) is re-declared locally in
  each module and used for absence checks only; a module asserts that a
  document DEFINES a value only when it owns that document. This preserves
  green-between-merges behaviour while tasks run in parallel.

## Cross-task Design Decisions

### D1 — The third `state` value literal is `phase_done`

Fixed by this plan, not renegotiated per task, because three tasks need the
same literal at the same time: `tests/test_batch_stop_contract.py` asserts
the contract document defines it, and the two pointer guards assert its
absence. `em-workflow/references/batch-terminal-line.md` remains its only
definition site. Affected: task0002, task0003.

### D2 — Guard shape for `state` values

`completed`, `stopped` and `skipped` are ordinary step-status vocabulary in
both pointer documents, so a bare-word check would false-positive (FR10,
AC7). The guard therefore checks a contract-specific SHAPE, the same way the
four field names are already checked as a group:

1. For every value of the `state` domain: the `state={value}` form must not
   appear, in bare, backticked or quoted spelling.
2. For the `--once` boundary value only: the bare literal must not appear
   either. It is contract-only vocabulary that occurs nowhere else, so this
   adds no false-positive surface, and without it a pointer document could
   restate the value while dodging rule 1.

Scope is the whole file for both `SKILL.md` and `batch-mode.md`, matching
AC6's whole-file phrasing and the existing whole-file prefix check. The
pre-existing subsection-scoped checks are unchanged. Both guards implement
this rule independently, with their own negative proof, non-vacuity guard
and false-positive proof over the real files. Affected: task0002, task0003.

### D3 — SKILL.md placement invariants

Two tasks edit `em-workflow/skills/develop/SKILL.md` in disjoint regions.
The following hold after both merges, and each task verifies them on its own
worktree:

1. All new content sits BEFORE the 「## 停止時の報告（停止条件 2-4 のみ）」
   heading, except the batch-emission wording, which stays inside the
   existing 「## バッチ終端行」 section.
2. No level-2 heading is introduced between 「## 停止時の報告」 and
   「## バッチ終端行」 (a level-3 heading there is permitted).
3. Nothing is appended after the 「## バッチ終端行」 section. The region from
   that heading to the file's `$ARGUMENTS` marker is the guard's slice and
   stays free of contract literals and of any `gate_id` / "gate ID" mention.
4. 「ターンを終わらせていい唯一の条件」 keeps items 1-6 verbatim, appends item
   7, and keeps its closing anchor sentence 「これらに該当しない限り…」 after
   the list.
5. SKILL.md names no terminal-line `state` value anywhere in the file. The
   state is described by role (the turn that ended at a `--once` phase
   boundary), with the value left to the SSOT.
6. New content introduces no `gate_id` / "gate ID" mention, so the plugin
   invariant checker's proximity heuristic cannot newly fire.

Affected: task0001, task0002.

### D4 — Terminal-state cardinality

FR11's targets are three sentences that pin the count at two: the contract's
`state` bullet, the contract's 「No line on a wait turn」 sentence, and
SKILL.md's 「同 SSOT が定める 2 つの終端状態のいずれか」. Rule: no document
states a count. The contract enumerates its own domain; every other document
refers to the set. The assertion in `tests/test_batch_stop_contract.py` that
pins the count-bearing wording is updated by the same task that rewrites the
sentence (task0003), so the suite is never red between merges. Affected:
task0002 (SKILL.md side), task0003 (contract side).

### D5 — The four phase-boundary kinds

One phase ends only after the resulting state change is COMMITTED. The four
kinds, and the `step` value the terminal line carries for each:

| Boundary | Turn ends when | Terminal-line `step` | Next launch resumes at |
|---|---|---|---|
| Ordinary step | the step's `status` is `completed` (`skipped` for `design` only) and committed | the executed step | the following step |
| `retrospect` | `retrospect` reaches `completed`; Step C (完了処理) is its own phase | `retrospect` | Step C |
| verify-fail rework | the rework patch is applied, `implement` and `verify` are back to `pending`, and that change is committed | `verify` | `implement` |
| automatic re-entry | the routing patch is applied and committed (`create-plan` → `needs_update` from implement I.2.c, or `create-spec` → `needs_update` from the rework spec-change transition) | the executed step | the re-entered step |

Non-boundaries: stop condition 5's wait turns and implement's launch and
wake turns. They are non-terminal, end no run, and emit no terminal line —
`--once` never ends the turn inside the implement phase, because in-flight
background implementers are lost on process exit. Affected: task0001
(defines them in SKILL.md), task0003 (states the `step` rule in the
contract).

### D6 — Test-module ownership

| Module | Owner | Pins |
|---|---|---|
| `tests/test_develop_once_option.py` (new) | task0001 | SKILL.md's `--once` semantics: argument handling, phase boundaries, stop condition 7, interactive closing line, non-boundaries |
| `tests/test_batch_stop_contract_skill_wiring.py` | task0002 | SKILL.md's 「バッチ終端行」 subsection and `batch-mode.md`'s `## Terminal line`; the SKILL.md-side literal guard |
| `tests/test_batch_stop_contract.py` | task0003 | `batch-terminal-line.md`'s structure and value domains; the `batch-mode.md` pointer literal-absence guard; the prefix-uniqueness sweep |
| `tests/test_plugin_version_parity.py` (new) | task0004 | the two manifests' `version` agreement |
| `tests/test_develop_skill_rewiring.py` | nobody | pre-existing SKILL.md wording that must survive this feature unchanged |

A task that finds it must modify a module outside its own row reports that
as a plan deviation rather than editing it silently — that signal is how an
unintended wording regression surfaces.

### D7 — Version bump ownership

The bump to `0.1.51` (from the confirmed current `0.1.50`) is a single task
touching both manifests together, per
`.claude/rules/core-plugin-version-bump.md`. In
`.claude-plugin/marketplace.json` the em-workflow entry is selected by its
`name`, since the em-review entry carries no `version` key at all. Affected:
task0004.

### D8 — Emission occasion in the pointer documents

`batch-mode.md`'s `## Terminal line` currently enumerates the occasions as
"normal completion and every terminating stop", which stops being exhaustive
once a `--once` phase boundary can also end a run's turn. The occasion list
is therefore extended in both pointer documents to include the `--once`
phase boundary, stated as an occasion only — no value literal, no field
grammar (FR9, NFR1). This is a planner decision: no FR mandates the
`batch-mode.md` sentence change, but leaving it as-is would make the pointer
document state something false. Affected: task0002.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Two tasks edit `SKILL.md` and collide | Medium | Medium | D3's disjoint region ownership; conflicts resolved by the implementer's parent-side-adoption protocol |
| The extended guard false-positives on step-status prose (`completed` / `skipped` / `stopped`) | Medium | High (blocks every later change to the pointer documents) | D2's shape-scoped rule plus a mandatory false-positive proof over the real files in both guard modules |
| A pointer document silently gains the new `state` literal | Medium | High (SSOT partition collapses) | Whole-file guard scope in both modules (D2), plus the unchanged prefix-uniqueness sweep |
| A count-bearing sentence about terminal states becomes false | High if unmanaged | Medium | D4, with the pinning assertion updated by the same task that rewrites the sentence |
| New SKILL.md content lands inside the guard's slice (after 「## バッチ終端行」) and trips the literal or `gate_id` checks | Low | Medium | D3 items 3 and 6 |
| An implementer edits a pre-existing module it does not own to make its own change pass | Low | High (silently erases a wording guarantee) | D6's ownership map; such an edit is a reportable plan deviation |
| `--once` described in a way that permits ending the turn mid-implement | Low | High (in-flight implementers lost) | D5's explicit non-boundary list, pinned by a dedicated test scenario (TS14) |

## Open Questions

- [ ] D1 pins the third `state` value as `phase_done`, taken from the
      feature's originating plan. SPEC.md deliberately leaves the literal to
      the contract document; if review prefers a different spelling, exactly
      one definition site and three absence-check constants change.
- [ ] D8's `batch-mode.md` sentence extension is a planner decision, not an
      FR. Confirm it is wanted rather than leaving the pointer document's
      occasion list stale.
