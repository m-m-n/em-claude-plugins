# Implementation Plan: task-tier-reduction

## Overview

A pre-run weight assessment (Codex readonly estimate + Jev System One)
selects one of three run tiers — `full` / `reduced` / `minimal` — and the
selected tier removes documents and parallelism from the em-workflow run.
Every artifact of this feature is a plugin document, a plugin registry, a
small plugin script, or a repository-root test module.

## Technology Stack

- **Language**: Python 3.14 for scripts and tests; Markdown / YAML for the
  plugin's protocol documents and registries.
- **Test framework**: standard-library `unittest`, discovered by
  `python3 -m unittest discover -s tests` (NFR7).
- **New dependencies**: none. No library is added, so
  `references/license-compat.md` imposes no constraint here; `project.license`
  is `none` and stays `none`.
- **Existing dependency reused**: the plugin's already-documented YAML parser
  prerequisite (`em-workflow/README.md`) is what the new evaluator script uses
  to read its rule table. Test modules do not import it directly — they load
  the script the way `tests/test_check_plugin_invariants.py` already loads a
  plugin script, which keeps NFR7's "test code imports no third-party package"
  literally true.

## Layer Structure

Four layers, with a one-way dependency direction (each layer may cite the one
above it, never the reverse):

1. **Decision rules** — `references/tier-rules.yaml`: the question set sent to
   Jev, the threshold rows, the Codex output schema, and the availability
   fallback matrix. Declarative only; it references the external skills and
   copies nothing from them (NFR5).
2. **Decision mechanism** — `scripts/decide-tier.py`: a deterministic
   evaluator over observed values. No inference, no network, no repository
   reads beyond its own rule table (NFR1).
3. **State** — `phase-state/{feature}/tier.yaml` before `workflow.yaml`
   exists, then `workflow.yaml`'s `tier` / `tier_decision` once create-spec has
   built it. `workflow.yaml` wins from that point on (FR15).
4. **Consumers** — the develop orchestrator loop, the create-spec /
   create-plan phase protocols, the review phase, and the rework path. A
   consumer reads the tier; no consumer re-derives it.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| `em-workflow/references/tier-rules.yaml` | Single place holding the Jev question set, the three threshold rows, the Codex output schema and the availability fallback matrix | Pre: none. Post: a consumer reads the rows it needs and never restates them in its own document; the file names the external skills by path and reproduces none of their text | task0001 (author), task0003, task0005 |
| `em-workflow/scripts/decide-tier.py` | Deterministic tier evaluation | Pre: one JSON mapping on standard input carrying the two availability booleans, the Jev score object (its probability members and its clarity member) and the basis label; a rule-table path may be supplied as an argument, defaulting to the plugin's own `references/tier-rules.yaml`. Post: one JSON mapping on standard output carrying the decided tier, the rule row or fallback row that decided it, and an echo of the observed values; a missing, malformed or incomplete input yields the safest tier with a reason naming what was missing, never an error exit and never a prompt; exit status is non-zero only when no output could be produced at all | task0001 (author), task0003 (caller) |
| `phase-state/{feature}/tier.yaml` | Holds the tier decision from the moment it is made until create-spec transcribes it | Pre: written immediately after the decision, before `workflow.yaml` exists, and committed by `commit-docs.sh` (which already stages the whole feature-docs tree, so no script change). Post: carries the schema version, the feature slug, the decided tier, and the two decision bases with their observed values and timestamps. A resume reads it; a re-transcription never lowers the tier already recorded in `workflow.yaml` | task0003 (writer), task0006 (reader) |
| `workflow.yaml` `tier` / `tier_decision` | Canonical tier once create-spec has built `workflow.yaml` | Pre: written only by the orchestrator, in the same write that builds `workflow.yaml` (single-writer rule unchanged). Post: `tier` holds one of the three tier labels; `tier_decision` holds exactly four sub-fields — the deciding agent, the confidence record, the decision timestamp, and the list of subtractions applied. Changes are upgrade-only | task0002 (definer), task0003, task0005, task0006 |
| No-work terminal stop | The run ends before any workflow step when the Codex estimate reports that no work remains | Pre: the estimate's no-work member reads false-y. Post: the run emits the structured result with the stopped state, the no-step sentinel, and non-empty resume guidance stating that no resumption is needed; the stop point is named `no-work-required` and its reason code literal lives only in `references/batch-terminal-line.md` (NFR3/AS-6 — neither `skills/develop/SKILL.md` nor `references/batch-mode.md` may carry the code literal) | task0003 (trigger), task0004 (contract) |
| Tier reduction table | Which artifacts each tier subtracts, and what every tier keeps | Pre: none. Post: owned by `skills/develop/SKILL.md`; every other document cites it rather than restating the subtraction list. `reduced` subtracts the requirements document, the implementation plan and the design step; `minimal` additionally subtracts the spec document (replaced by the task document), the task split, the verification document and task-level parallelism. Every tier keeps the full existing test suite, the Step 0 git-setup gate, the security review perspective, and the integration worktree | task0005 (owner), task0006 (citer) |
| `TASK.md` template | The minimal tier's replacement for the spec document | Pre: none. Post: `em-workflow/references/templates/task-document.md` defines exactly two sections — the change being made, and the expected result — and nothing else | task0006 (author), task0005 (citer) |

## Conventions

- **Document SSOT discipline**: every value defined in this feature has
  exactly one owning document. A second document that needs it cites the
  owner by path and does not restate it. This is the existing rule the
  repository already machine-checks for stop reason codes (NFR3), applied to
  the tier vocabulary, the threshold rows and the reduction table as well.
- **Naming of stop points versus reason codes**: a stop point is written with
  hyphens and a reason code with underscores, following the existing
  `verify-rework-cap` / `verify_rework_cap_reached` pair. A document that owns
  the stop point may name the hyphenated form; only the terminal-line contract
  may carry the underscored code literal.
- **Fail-safe, never fail-open**: every unresolved condition on the decision
  path resolves to the tier that removes nothing. Missing tools, non-zero exit
  statuses, malformed output and absent fields are all the same case.
- **No new user-facing gate**: this feature introduces no `gate_id`. The
  decision is mechanical and its failure mode is a safe default, so there is
  nothing to ask (FR23's explicitly permitted branch, and the cheapest way to
  satisfy NFR6). `references/batch-policies.yaml` therefore needs no entry,
  and the bidirectional `gate_id` check keeps passing untouched.
- **Test module convention**: one new module per task under `tests/`, named
  `tests/test_tier_*.py` except where an existing module is being extended.
  Each module opens with a docstring listing the acceptance criteria it
  covers, asserts against raw file text rather than parsed structure where a
  literal's absence matters, and pairs every matcher with a negative proof
  against a forged sample plus a non-vacuity guard — the convention the
  existing document-conformance modules in `tests/` already follow.
- **Error-handling policy on the decision path**: conditions are recorded, not
  raised. The evaluator reports which input was missing; the orchestrator
  records that reason in the decision bases it persists.

## Cross-task Design Decisions

### D1 — The tier decision is evaluated by a deterministic script

NFR1 forbids Claude inference on the decision path, and TS-10 requires a
threshold evaluation that a test can call. Both are satisfied by a small
plugin script that is a pure function of already-collected observations: the
orchestrator performs the two external invocations the spec fixes
(`run_codex_exec.sh` in readonly mode, and the Jev skill with its JSON input
and JSON output switches), then hands the collected values to the evaluator
and records what it returns. The evaluator itself performs no invocation, so
its behaviour is fully testable offline.
Affected tasks: task0001 (author), task0003 (caller).

### D2 — Two persistence stages, `workflow.yaml` authoritative after create-spec

The decision happens in Step A, before `workflow.yaml` exists, and Step A has
a real interrupt-and-resume path. The decision is therefore written to
phase-state immediately and transcribed into `workflow.yaml` when create-spec
builds it. After that point `workflow.yaml` is the only value read, and a
resume that re-runs the transcription may raise the tier but never lower it.
Affected tasks: task0003 (produce), task0006 (consume), task0002 (field
definition), task0005 (upgrade-only rule in the loop).

### D3 — Section ownership inside `skills/develop/SKILL.md`

Two tasks edit that one file in parallel. Their regions are disjoint and this
split is binding:

- **task0003 owns**: Step A (the decision procedure, the two external
  invocations, the fallback matrix application, the phase-state write, and the
  text that triggers the no-work stop), and the retrospect section's new
  decision record.
- **task0005 owns**: the turn-ending conditions list at the top of the file
  (including the amendment for non-design `skipped` and the new entry for the
  no-work stop point), the Step B status discipline and phase table, the
  automatic-re-entry carve-out enumeration, the Step C entry condition and
  its heading, and the `--once` phase-boundary table.

Neither task edits the other's region. Where one needs a fact the other owns,
it takes it from this document's Shared Components table.

### D4 — The reduction table lives in the develop skill, not in `tier-rules.yaml`

`tier-rules.yaml` answers "which tier", the develop skill answers "what that
tier removes". Keeping the subtraction list out of the rules file avoids a
second place to update when a step is added, and keeps FR1's stated contents
(questions, thresholds, Codex schema) exactly as specified.
Affected tasks: task0001, task0005, task0006.

### D5 — One task owns both version manifests

`em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`
are single-line edits that every task would otherwise conflict on. task0008 is
their only writer for this feature. See Resolved Questions for the level of
the bump and for the twenty-two modules it takes with it.

### D6 — The spec perspective's absence rule is extended, not branched

FR17 is implemented by widening the existing "no spec document ⇒ drop the spec
perspective with a skip notice" rule from the standalone route to the
develop-driven route. No tier-conditional branch is added to the review
selection, which is what keeps NFR2 structurally true: the baseline
perspective set — security included — is untouched by anything in this
feature.
Affected tasks: task0007 (owner), task0005 (must not add a review branch).

### D7 — `minimal` keeps one real task entry

Subtracting the task split is not the same as subtracting the task record: the
task entry carries execution status and branch, and task completion is defined
by the merge into the integration branch. `minimal` therefore registers
exactly one task pointing at the task document, with an empty requirement
mapping permitted alongside it.
Affected tasks: task0006 (the phase precondition and the validator scenario),
task0005 (the reduction table's wording).

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Two tasks editing `skills/develop/SKILL.md` collide | High | Medium | D3's binding region split; each task's acceptance criteria name only its own regions |
| The new stop reason code breaks a fixed-cardinality assertion nobody predicted | Medium | High | task0004 owns every known pinned assertion and runs the whole suite; the two dynamically-extracting modules are inside its declared file set so a surprise there is in scope, not a deviation |
| The minor version bump breaks the 22 modules that pin the major/minor pair as a durable invariant | Certain (accepted) | Medium | Resolved Questions takes the minor bump deliberately; all 22 modules are in task0008's file set and are rewritten to assert the property (both manifests equal, strictly increasing) instead of the literal pair |
| SPEC's threshold table and its TS-10 example disagreed | Resolved before implementation | Low | FR4 amended with a first-bucket floor of 0.40 for `reduced`, so TS-10's three cases all hold as written; see Resolved Questions |
| The develop skill's turn-ending conditions list has a pinned cardinality somewhere | Medium | Medium | task0005 searches for one before adding an entry and includes any hit in its own change |

## Resolved Questions

All three were raised during planning and settled by a Codex consultation
before this plan was committed. The chosen option is recorded here; the
artifacts already reflect it.

- [x] **FR4 versus TS-10 disagreed on one example.** FR4's original rows gave
      `reduced` whenever the first two buckets summed to at or above 0.85,
      which made TS-10's second case (first bucket 0.37, second bucket 0.59,
      sum 0.96) yield `reduced` where TS-10 expects `full`. **Resolved: TS-10
      is authoritative and FR4 is amended** with a floor on the first bucket —
      `reduced` now requires the first bucket at or above 0.40 **and** the sum
      at or above 0.85. Basis: the design intent is fail-safe, so a low first
      bucket carried by a high second bucket must not buy a lighter tier;
      0.40 is the smallest floor that separates SPEC's two cited cases and
      leaves (0.50, 0.40) resolving to `reduced`. SPEC.md and REQUIREMENTS.md
      carry the amended rows; task0001 implements them and TS-10 stands
      unchanged.
- [x] **NFR4 asked for a minor bump, and a minor bump failed the suite.** The
      current version is `0.1.86`, and twenty-two existing modules assert the
      major/minor pair as an explicitly named durable invariant, so `0.2.0`
      fails all of them. **Resolved: take the minor bump and rewrite the
      twenty-two modules.** Basis: NFR4 states `minor` explicitly for this
      change, and a literal `(0, 1)` pin is unfit as a durable invariant
      precisely because it blocks every future legitimate minor bump.
      Rewriting those assertions to the property NFR4 cares about — both
      manifests equal, strictly increasing under per-component numeric
      comparison — is more consistent than silently downgrading the bump to a
      patch. The twenty-two modules are in task0008's declared file set, so
      the rewrite is inside the change set rather than beyond it.
- [x] **TS-11's checker attribution.** TS-11 named the invariant checker's
      stale-reference scan, but that scan detects one deleted agent name and
      one retired phrase — it performs no path-existence check, so TS-11 as
      written could never fail. **Resolved: verify the underlying intent and
      leave the shared checker alone.** Basis: adding a generic
      path-existence check to a repository-wide script would scope in
      pre-existing dangling references unrelated to this feature, widening
      the blast radius for no gain in what FR1 needs. SPEC.md and
      REQUIREMENTS.md now word TS-11 as what is actually verified — the rules
      file exists and every reference to it resolves — and the whole checker
      staying green remains AC-13.
