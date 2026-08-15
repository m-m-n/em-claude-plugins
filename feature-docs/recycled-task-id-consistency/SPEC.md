# Feature: recycled-task-id-consistency

## Overview

The recycled-task-id rule in `em-workflow/references/implement-phase.md` does not read identically at the four sites that depend on it (Step I.2.a, Step I.2.b step 1, Step I.2.b step 3, Step I.2.c route-back), so a task the reconcile step classifies as unlaunched is written back to `failed` by the same wake phase and thereby made permanently unlaunchable. This feature harmonizes those four sites, gives the combination "workflow.yaml `status: pending` + journal last event `launched`" a defined disposition by preventing it at its only source, states the rule's scope explicitly, and backs the retained rule with requirements, acceptance criteria and test scenarios in this feature's documents. The change is contained to protocol documentation, the plugin version bump and new document-contract tests.

Requirements source: `feature-docs/recycled-task-id-consistency/REQUIREMENTS.md`.

## Objectives

- Make the recycled-task-id rule read identically at Step I.2.a, Step I.2.b step 1, Step I.2.b step 3 and Step I.2.c route-back, so that a task the reconcile step classifies as unlaunched is not written back to `failed` by the same wake phase.
- Give "workflow.yaml `status: pending` + journal last event `launched`" a defined disposition by preventing it at its only source: I.2.c route-back gains a precondition that every task it resets must have a terminal journal last event, and a non-terminal last event becomes a defined terminal outcome (abort with a report) rather than an undefined path.
- State the recycled-task-id rule's scope explicitly, so a reader can tell that it governs only the orchestrator's interpretation of the journal and never changes how the journal-reading hooks classify a task.
- Give the retained rule the requirement / acceptance-criterion / test-scenario coverage it currently lacks, inside this feature's REQUIREMENTS.md and SPEC.md, leaving the completed implement-routeback-gate documents untouched.
- Keep the change contained to protocol documentation, the plugin version bump and new document-contract tests: no hook, script, agent or skill behaviour changes.

## User Stories

### US1: A recycled-id task survives the wake phase
As the orchestrator running the implement phase, I want Step I.2.b step 3's `failed` write-back to key off step 1's reconciled state, so that a recycled-id task step 1 classified as unlaunched is not stranded by I.2.a's "Tasks whose reconciled state is `failed` are NEVER selected here".

**Acceptance Criteria:**
- [ ] AC-1 (FR1): In the `### I.2.b: Wake phase` section, step 3's `failed` write-back condition names step 1's reconciled state (e.g. "for every task whose step-1 reconciled state is `failed`"), and the section no longer contains the journal-only write-back condition "for every task whose last journal event is `failed`". The `merged` half of the sentence and the "report is `failed`/malformed" clause are still present.
- [ ] AC-2 (FR2): I.2.a still contains the normative recycled-task-id statement; I.2.b step 1 still cites "the recycled-task-id rule in I.2.a above"; and no site in I.2.a / I.2.b / I.2.c states a per-task classification condition that contradicts it.

### US2: Route-back never produces an orphaned `pending` + `launched` pair
As the orchestrator handling a failed implement phase, I want route-back to be admissible only when every task it would reset has a terminal journal last event, and a non-terminal last event to end the phase with a report instead of a partial write, so that the "`status: pending` + journal last event `launched`" combination cannot arise.

**Acceptance Criteria:**
- [ ] AC-3 (FR3): The I.2.c route-back bullet states that every task whose status it resets must have a terminal journal last event (`merged` or `failed`), and that statement's position precedes the ordered write set (its normalized index is less than that of "`create-plan` to `needs_update`"). The existing gate "no task has status `merged`" is still present.
- [ ] AC-4 (FR4): The same bullet states that a non-terminal journal last event makes route-back inapplicable, that `implement` stays `failed`, that no `create-plan` `needs_update` write and no worktree/branch cleanup are performed in that case, and that the phase reports (naming the affected task ids and their last journal event) and returns control via develop's stop condition 3 / the same terminal as "abort phase". Neither "rework" nor "`append`" appears anywhere in the I.2.c section.
- [ ] AC-5 (FR5): I.2.a's recycled-task-id paragraph states that id recycling arises only through I.2.c route-back plus the planner's `replace_all` renumbering and that, given AC-3's precondition, `status: pending` with journal last event `launched` cannot arise. The sentence "A task whose journal last event is `launched` is always in-flight, regardless of workflow.yaml `status`" is still present.

### US3: A reader can tell how far the rule reaches
As a reader of `implement-phase.md`, I want the rule's scope stated as orchestrator-only, so that I can tell it never changes how the journal-reading hooks classify a task.

**Acceptance Criteria:**
- [ ] AC-6 (FR6): `implement-phase.md` contains a sentence stating that the recycled-task-id rule governs only the orchestrator's interpretation of the journal, naming `queue_launch_guard.py`, `queue_stop_guard.py`, `queue_failure_net.py` and `queue_taskstop_net.py`, and stating that they judge by the journal's last event alone and never consult `tasks.{T}.status`. The document contains no claim that these hooks never read workflow.yaml.

### US4: The retained rule is backed by documents and a contained change
As the maintainer of this repository, I want the requirements, acceptance criteria and test scenarios for the retained rule to live in this feature's documents and the change to stay inside a declared file set with a matching version bump, so that the completed implement-routeback-gate feature's historical scope stays intact.

**Acceptance Criteria:**
- [ ] AC-7 (FR7): `feature-docs/recycled-task-id-consistency/REQUIREMENTS.md` and `SPEC.md` exist and carry the requirements, acceptance criteria and test scenarios for the retained rule; `git diff --name-only` for the change lists no path under `feature-docs/implement-routeback-gate/`.
- [ ] AC-8 (FR8): `git diff --name-only` for the change is a subset of {`em-workflow/references/implement-phase.md`, `em-workflow/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json`, `feature-docs/recycled-task-id-consistency/**`, `test-docs/recycled-task-id-consistency/**`, the new/extended module(s) under `tests/`}, and contains no path under `em-workflow/hooks/`, `em-workflow/scripts/`, `em-workflow/agents/`, `em-workflow/skills/`.
- [ ] AC-9 (FR9): `em-workflow/.claude-plugin/plugin.json` reads `"version": "0.1.37"`, and the `em-workflow` entry of `.claude-plugin/marketplace.json` reads `"version": "0.1.37"`; the `em-review` entry is unchanged.
- [ ] AC-10 (NFR1): `python3 -m unittest discover -s tests` passes from the repository root with `tests/test_implement_routeback_gate.py`, `tests/test_review_implement_develop_lock_contracts.py`, `tests/test_rework_synthesis_contract.py`, `tests/test_develop_skill_rewiring.py`, `tests/test_batch_policies.py` and `tests/test_check_plugin_invariants.py` unmodified — which is what demonstrates that every anchor NFR1 enumerates survived.
- [ ] AC-11 (NFR1): `implement-phase.md` contains no line that begins with `git ` (ignoring markdown backticks and indentation) and contains `commit` or `add -A`.
- [ ] AC-12 (NFR5): The new test module(s) assert every point of AC-1 through AC-6 and include at least one test proving each new matcher flags the corresponding pre-change wording.

## Technical Requirements

### Functional Requirements

- **FR1 — I.2.b step 3's write-back keys off the step-1 reconciled state:** In `em-workflow/references/implement-phase.md` Step I.2.b step 3, the workflow.yaml write-back condition for `failed` changes from the journal-only phrasing currently in the document — "`= failed` for every task whose last journal event is `failed` or whose report is `failed`/malformed" — to a condition keyed off step 1's reconciled state: `tasks.{T}.status = failed` is written for every task whose STEP-1 RECONCILED STATE is `failed`, or whose completion report is `failed`/malformed. Consequence, which must be readable from the text: a recycled-id task that step 1 classified as unlaunched via the carve-out (journal last event `failed` while workflow.yaml `status` is `pending`) is NOT written back to `failed` in the same wake phase, so the carve-out survives the wake and I.2.a's "Tasks whose reconciled state is `failed` are NEVER selected here" no longer strands it. The `merged` half of the same sentence ("set `tasks.{T}.status = merged` for every task verified merged") is unchanged.
- **FR2 — One normative statement of the recycled-task-id rule, cited by the other three sites:** The recycled-task-id rule keeps exactly one normative statement, in Step I.2.a's recycled-task-id paragraph (the sentences beginning "Recycled task id: workflow.yaml's status wins over a stale journal event here"). The other three sites cite it rather than restating a condition that can drift from it: Step I.2.b step 1 keeps its existing citation "the recycled-task-id rule in I.2.a above"; Step I.2.b step 3 refers to step 1's reconciled state (FR1) instead of re-deriving a classification from the journal; Step I.2.c's route-back precondition (FR3) is expressed in the same vocabulary (journal last event, terminal vs non-terminal) as I.2.a's statement. After the edit, no site states a per-task classification rule that reads differently from I.2.a's.
- **FR3 — I.2.c route-back precondition: every reset task has a terminal journal last event:** The "route back to planning" bullet of `### I.2.c: Failed handling` gains an explicit precondition, stated before its ordered workflow.yaml write set: route-back is admissible only when EVERY task whose `tasks.{T}.status` it would reset to `pending` has a TERMINAL journal last event (`merged` or `failed`). This precondition is checked by replaying the journal, in addition to — not instead of — the existing gate "applies only when no task has status `merged`". The existing gate sentence and its wording are retained.
- **FR4 — A non-terminal last event is a defined terminal outcome, not an undefined path:** The same bullet defines what happens when FR3's precondition fails: route-back is INAPPLICABLE. The orchestrator makes no part of the route-back write set (no `create-plan` = `needs_update`, no `implement` = `pending`, no `tasks.{T}.status` reset), performs no worktree/branch cleanup and no route-back commit; `implement` stays `failed`; the phase ends with a report that names each offending task id and its non-terminal journal last event, and returns control to the user via develop's stop condition 3 — the same terminal as the bullet's existing "abort phase" option. The added text must not introduce the word "rework" or the token "`append`" anywhere inside the I.2.c section, and must not introduce a partial-write path.
- **FR5 — The `pending` + journal `launched` pair is shown to be unreachable:** Step I.2.a's recycled-task-id paragraph states, in one or two sentences, why the combination "workflow.yaml `status: pending` + journal last event `launched`" cannot arise: task-id recycling only ever occurs through I.2.c's route-back (the only writer that resets a task's status to `pending`) followed by the planner's `replace_all` renumbering from `task0001`, and FR3's precondition admits route-back only for tasks whose journal last event is terminal — so a re-numbered task can only ever inherit a retired id's `merged` or `failed` events, never a `launched` one. The existing sentence "A task whose journal last event is `launched` is always in-flight, regardless of workflow.yaml `status` — never reinterpret it as unlaunched, since the launch guard would deny that launch." is RETAINED verbatim; FR5's addition is what removes the orphaned combination it previously left without an exit.
- **FR6 — The rule's scope is stated as orchestrator-only:** `implement-phase.md` states explicitly that the recycled-task-id rule governs ONLY the orchestrator's interpretation of the journal, and that the journal-reading hooks are unaffected: `queue_launch_guard.py`, `queue_stop_guard.py`, `queue_failure_net.py` and `queue_taskstop_net.py` each derive a task's state from the journal's last event ALONE and never consult `tasks.{T}.status`. The statement must be worded so that it stays true of `queue_stop_guard.py`, which does read workflow.yaml for the `implement` step's own status line and for the `tasks:` key list — the claim to make is "never consults `tasks.{T}.status`", never the stronger "never reads workflow.yaml". The sentence sits with I.2.a's normative statement (FR2) and does not restate hook internals already owned by the "Supporting cast: journal, hooks, resume" inventory; it cites that inventory rather than duplicating it.
- **FR7 — Requirements, ACs and test scenarios live in this feature's documents:** The requirements, acceptance criteria and test scenarios that back the retained recycled-task-id rule are written into `feature-docs/recycled-task-id-consistency/REQUIREMENTS.md` and `feature-docs/recycled-task-id-consistency/SPEC.md`. No file under `feature-docs/implement-routeback-gate/` is created, edited or deleted — its REQUIREMENTS.md, SPEC.md, tasks/ and reviews/round1.yaml stay exactly as they are, preserving that completed feature's historical scope and review provenance.
- **FR8 — Change containment:** The change touches only: `em-workflow/references/implement-phase.md`; `em-workflow/.claude-plugin/plugin.json`; `.claude-plugin/marketplace.json`; artifacts under `feature-docs/recycled-task-id-consistency/`; artifacts under `test-docs/recycled-task-id-consistency/` (`em-workflow/references/implement-phase.md` mandates these as per-task required outputs, so the implementation cannot omit them); and the new or extended test module(s) under `tests/`. Explicitly NOT modified: anything under `em-workflow/hooks/`, `em-workflow/scripts/`, `em-workflow/agents/`, `em-workflow/skills/` (including `skills/develop/SKILL.md`), `em-workflow/references/workflow-patch.md`, `em-workflow/references/workflow-schema.md`, `em-workflow/references/rework-task-synthesis.md`, `em-workflow/references/contracts/*`, `feature-docs/implement-routeback-gate/*`, and the existing test modules `tests/test_implement_routeback_gate.py`, `tests/test_review_implement_develop_lock_contracts.py`, `tests/test_rework_synthesis_contract.py`, `tests/test_develop_skill_rewiring.py`, `tests/test_batch_policies.py`, `tests/test_check_plugin_invariants.py`.
- **FR9 — Plugin version bump to 0.1.37 in both registries:** As part of the same change, `em-workflow/.claude-plugin/plugin.json`'s `version` goes from `0.1.36` to `0.1.37` (patch), and the root `.claude-plugin/marketplace.json`'s `plugins[]` entry whose `name` is `em-workflow` carries `"version": "0.1.37"`. That entry currently has no `version` key at all, so this requirement is satisfied by ADDING the key with that value; the `em-review` entry is not touched, and no other field of either file changes.

### Non-Functional Requirements

- **NFR1 — Existing document-contract test anchors survive unchanged:** The edits must not disturb any anchor the existing suites depend on. Line-wrap-sensitive RAW literals (matched against un-normalized text, so a reflow breaks them even when the prose is unchanged): (a) `tests/test_rework_synthesis_contract.py` requires "Select\nunlaunched tasks (no journal event yet and `status != merged`, ascending" and "require at least one task in `tasks` whose\n   `status == pending`", with the latter still positioned earlier in the file than the former; (b) `tests/test_review_implement_develop_lock_contracts.py` requires the I.2.b commit literal '"docs({feature}): implement wake\n   phase reconcile"' with its exact newline and three-space continuation indent, plus the anchors `Refresh the integration worktree FIRST` and `Update workflow.yaml, then commit` in that order, and `phase reconcile" "$RECONCILE_TIP"`. Byte-identity literals: the heading `### I.2.c: Failed handling`, and the batch-mode paragraph that closes the I.2.c section (asserted byte-identical by `tests/test_implement_routeback_gate.py`'s `PRE_CHANGE_BATCH_MODE_PARAGRAPH`, INCLUDING its position as the last text of the section). Whitespace-normalized ordering and proximity constraints inside I.2.c that `tests/test_implement_routeback_gate.py` enforces and that added text must preserve: the FIRST occurrence of `tasks.{T}.status` must still have `pending` within the following 60 normalized characters; `create-plan` to `needs_update`, `implement` step back to `pending`, `tasks.{T}.status` back to `pending` and `tasks.{T}.notes` must all still precede `git worktree remove --force`; `git worktree remove --force` must precede the FIRST `commit-docs.sh`, which must precede `End the phase with a`; the phrase "no task has status `merged`" must remain; the slice from `If any task has already merged` to `- **abort phase**` must contain neither `rework` nor `append`; and the old phrasings "every existing task is still `pending`" and "create-plan exemption owns that precedence" must stay absent. Finally, no line of `implement-phase.md` may begin with `git ` and contain `commit` or `add -A`, so any new commit instruction goes through `commit-docs.sh`.
- **NFR2 — SSOT non-duplication:** `implement-phase.md` keeps exactly one normative statement of the recycled-task-id rule (FR2) and cites, rather than restates, rules owned elsewhere: `references/workflow-patch.md` for `replace_all` / `replace_planning` permission conditions, `skills/develop/SKILL.md` Step B's stop-condition-3 precedence clause for the develop-side precedence, and the file's own "Supporting cast" inventory for hook behaviour. The new precondition and scope sentences add no copy of a rule that another document owns.
- **NFR3 — Documentation-only change:** No executed behaviour changes. No Python hook or script is edited; the hooks keep their fail-open, journal-last-event contract exactly as implemented today. Deliverables are protocol markdown, this feature's feature-docs artifacts, the version bump, and new tests.
- **NFR4 — Local style consistency:** Edited prose in `implement-phase.md` stays in English and matches its surroundings: existing bullet structure, backtick conventions for identifiers and file names, and no rationale beyond what the requirements state. Added sentences are wrapped consistently with the surrounding paragraphs and must not reflow the literals NFR1 protects.
- **NFR5 — Tests are Python unittest document-contract assertions:** New verification is added as Python `unittest` document-contract tests under `tests/`, runnable by `python3 -m unittest discover -s tests` from the repository root (the project defines no build and no format command and has no E2E infrastructure). They follow the pattern of `tests/test_implement_routeback_gate.py`: a module-level `PLUGIN_ROOT` / path constant, section slicing by heading, a `_normalize_ws` helper for prose assertions with raw text used only for byte-identity assertions, and at least one negative-proof test class demonstrating that each new matcher flags the pre-change wording (a test that can never fail is not a test).

## Implementation Approach

### Architecture

**System Architecture:**

The unit of change is a protocol document, not a running system. The affected structure is the section layout of `em-workflow/references/implement-phase.md` and the two registry files that carry the plugin version.

```
em-workflow/references/implement-phase.md
├── ## Step I.2: Task loop
│   ├── ### I.2.a: Launch phase
│   │     └── recycled-task-id paragraph  ← FR2 (sole normative statement)
│   │                                        FR5 (unreachability sentences)
│   │                                        FR6 (orchestrator-only scope sentence)
│   ├── ### I.2.b: Wake phase
│   │     ├── step 1  → cites I.2.a's rule (FR2, unchanged citation)
│   │     └── step 3  → write-back keyed off step-1 reconciled state (FR1)
│   └── ### I.2.c: Failed handling
│         └── "route back to planning" bullet
│               ├── precondition before the ordered write set (FR3)
│               └── inapplicable branch, no partial write (FR4)
└── ### Supporting cast: journal, hooks, resume  ← cited by FR6, not duplicated

em-workflow/.claude-plugin/plugin.json      version 0.1.36 → 0.1.37   (FR9)
.claude-plugin/marketplace.json             em-workflow entry gains
                                            "version": "0.1.37"        (FR9)

feature-docs/recycled-task-id-consistency/  REQUIREMENTS.md, SPEC.md   (FR7)
tests/                                      new/extended unittest
                                            document-contract module(s) (NFR5)
```

**Component Diagram:**

```
Step I.2.a  ──(normative statement)──▶  recycled-task-id rule
   ▲   ▲                                       │
   │   └───(cited by)─── Step I.2.b step 1     │ scope: orchestrator only (FR6)
   │                                           ▼
   │                            journal-reading hooks are UNAFFECTED:
   │                            queue_launch_guard.py, queue_stop_guard.py,
   │                            queue_failure_net.py, queue_taskstop_net.py
   │                            (last journal event alone; never tasks.{T}.status)
   │
   ├───(same vocabulary)─── Step I.2.c route-back precondition (FR3/FR4)
   └───(reconciled state, not re-derived)─── Step I.2.b step 3 (FR1)
```

### Data Flow

Wake phase, per task (FR1):

```
journal ──replay──▶ I.2.b step 1 ──reconciled state──▶ I.2.b step 3 ──▶ workflow.yaml
                    (applies I.2.a's rule)              failed  ⟸ reconciled state == failed
                                                                 OR report failed/malformed
                                                        merged  ⟸ verified merged (unchanged)
```

Failed handling, route-back admissibility (FR3, FR4):

```
journal ──replay──▶ last event per task to be reset
                        │
                        ├── all terminal (merged | failed)
                        │       └──▶ existing gate ("no task has status `merged`")
                        │              └──▶ ordered workflow.yaml write set → cleanup → commit
                        │
                        └── any non-terminal
                                └──▶ route-back INAPPLICABLE
                                     no write set, no cleanup, no route-back commit
                                     implement stays `failed`
                                     report names each offending task id + last event
                                     control returns via develop stop condition 3
```

### API Design

Not applicable. This feature introduces no endpoint; it is a documentation-only change (NFR3) whose deliverables are protocol markdown, this feature's feature-docs artifacts, two JSON version fields and Python unittest modules.

### Database Schema

Not applicable. This feature introduces no persistent data model. The only structured data it edits are two JSON version fields (FR9):

| File | Key | Before | After |
|------|-----|--------|-------|
| `em-workflow/.claude-plugin/plugin.json` | `version` | `0.1.36` | `0.1.37` |
| `.claude-plugin/marketplace.json` | `plugins[name == em-workflow].version` | key absent | `0.1.37` (key added) |

#### Entity Relationship Diagram

Not applicable (no entities).

### Dependencies

**Internal Dependencies:**
- `em-workflow/references/implement-phase.md`: the document under change; owns Steps I.2.a / I.2.b / I.2.c and the "Supporting cast: journal, hooks, resume" inventory that FR6 cites.
- `em-workflow/references/workflow-patch.md`: owns the `replace_all` / `replace_planning` permission conditions; cited, never restated (NFR2). Not modified (FR8).
- `em-workflow/skills/develop/SKILL.md`: owns Step B's stop-condition-3 precedence clause, the terminal FR4 returns control through; cited, never restated (NFR2). Not modified (FR8).
- `tests/test_implement_routeback_gate.py`: supplies the pattern the new module follows (NFR5) and the byte-identity literal reused by TS-9. Not modified (FR8).
- `feature-docs/implement-routeback-gate/`: the completed feature whose documents are left untouched (FR7).

**External Dependencies:**
- Python `unittest` (standard library): the only test framework in the project; the suite runs as `python3 -m unittest discover -s tests` from the repository root. The repository has no package manifest, no build command, no format command and no E2E infrastructure.

### File Structure

```
em-workflow/
├── references/
│   └── implement-phase.md            # FR1-FR6, NFR1, NFR2, NFR4
└── .claude-plugin/
    └── plugin.json                   # FR9: version 0.1.37
.claude-plugin/
└── marketplace.json                  # FR9: em-workflow entry gains version 0.1.37
feature-docs/
└── recycled-task-id-consistency/
    ├── REQUIREMENTS.md               # FR7
    └── SPEC.md                       # FR7
tests/
└── <new or extended module(s)>       # NFR5, TS-1 .. TS-11
```

## Test Scenarios

### Unit Tests

- [ ] TS-1 (normal / unittest document contract, AC-1, FR1): Slice `### I.2.b: Wake phase` .. `### I.2.c: Failed handling`, normalize whitespace, assert the step-1-reconciled-state write-back phrasing is present and assert assertNotIn for the journal-only phrasing "for every task whose last journal event is `failed`". Negative proof: the same matcher applied to the captured pre-change sentence flags it.
- [ ] TS-2 (normal / unittest document contract, AC-2, FR2): Assert I.2.a's normative sentence "Recycled task id: workflow.yaml's status wins over a stale journal event here" is present, and that the I.2.b step-1 parenthetical still contains "the recycled-task-id rule in I.2.a above".
- [ ] TS-3 (normal / unittest document contract, AC-3, FR3): In the normalized I.2.c section, assert the precondition text mentions a terminal journal last event with both `merged` and `failed`, and assert `section.index(<precondition anchor>) < section.index("`create-plan` to `needs_update`")`. Also assert "no task has status `merged`" is still present.
- [ ] TS-6 (normal / unittest document contract, AC-6, FR6): Assert the scope sentence names all four hook filenames, contains `tasks.{T}.status` in a "never consults" construction, and assert the document nowhere states that these hooks "never read workflow.yaml" (an assertNotIn on that exact phrase near the hook names), so a later edit cannot reintroduce the false claim.
- [ ] TS-7 (regression / unittest, AC-10, NFR1): Assert the raw text still contains "Select\nunlaunched tasks (no journal event yet and `status != merged`, ascending" and "require at least one task in `tasks` whose\n   `status == pending`" with the second occurring before the first, so a reflow introduced by the I.2.a edit fails here with a message naming the wrap rather than only inside an unrelated suite.
- [ ] TS-8 (regression / unittest, AC-10, NFR1): Assert the raw text still contains '"docs({feature}): implement wake\n   phase reconcile"' exactly, guarding the I.2.b step-3 edit against reflowing the commit literal.
- [ ] TS-9 (regression / unittest, AC-10 + NFR1): Assert `### I.2.c: Failed handling` is byte-identical and the batch-mode paragraph is still the byte-identical tail of the I.2.c section (reuse `tests/test_implement_routeback_gate.py`'s literal).
- [ ] TS-11 (normal / unittest, AC-9 + AC-11, FR9 + NFR1): Parse `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` as JSON and assert both report version `0.1.37` for em-workflow; and assert `implement-phase.md` has zero lines starting with `git ` that contain `commit` or `add -A`.

### Integration Tests

Not applicable. The change is documentation-only (NFR3) and the only project command is `python3 -m unittest discover -s tests`; every scenario is a document-contract assertion in that suite.

### E2E Tests

**Existing E2E tests**: None (the repository has no E2E infrastructure).
**Run command**: Not detected.
- [ ] AC-10 (NFR1): `python3 -m unittest discover -s tests` passes from the repository root with `tests/test_implement_routeback_gate.py`, `tests/test_review_implement_develop_lock_contracts.py`, `tests/test_rework_synthesis_contract.py`, `tests/test_develop_skill_rewiring.py`, `tests/test_batch_policies.py` and `tests/test_check_plugin_invariants.py` unmodified.

### Edge Cases

- [ ] TS-4 (abnormal path / unittest document contract, AC-4, FR4): In the normalized I.2.c section, assert the inapplicable-route-back branch states `implement` stays `failed` and cites stop condition 3 / "abort phase", and assert `assertNotIn("rework", section)` and `assertNotIn("append", section)` for the whole I.2.c section.
- [ ] TS-5 (boundary / unittest document contract, AC-5, FR5): In the normalized I.2.a slice, assert the unreachability sentence mentions `replace_all` (or the planner renumbering) together with `launched` and `pending`, and assert the retained sentence "A task whose journal last event is `launched` is always in-flight, regardless of workflow.yaml `status`" is still present.
- [ ] TS-10 (boundary / unittest document contract, NFR1): Re-assert the I.2.c intra-section orderings after the edit: first `tasks.{T}.status` occurrence has `pending` within the following 60 normalized characters; the four write tokens precede `git worktree remove --force`; cleanup precedes the first `commit-docs.sh`, which precedes `End the phase with a`.
- [ ] A5 (reachability note for FR3's precondition): the precondition is stated as "terminal journal last event (`merged` / `failed`)", following the recorded answer verbatim. A task carrying NO journal event at all is likewise non-terminal, but that state is unreachable for a task route-back would reset: I.2.b step 3 only writes `failed` for a task whose step-1 reconciled state is `failed` or whose completion report is `failed`/malformed, and both imply at least a `launched` event exists. No separate "no event" branch is therefore required.

### Performance Tests

Not applicable. No executed behaviour changes (NFR3).

## Security Considerations

- **Authentication:** Not applicable — documentation-only change (NFR3); no authentication surface is introduced or modified.
- **Authorization:** Not applicable — no authorization surface is introduced or modified.
- **Input Validation:** Not applicable at runtime. The validation this feature performs is static: the document-contract assertions of TS-1 .. TS-11 over `implement-phase.md` and the two JSON registry files.
- **Data Protection:** Not applicable — no data is stored or transmitted.
- **XSS Prevention:** Not applicable — no UI surface and no rendered output.
- **SQL Injection Prevention:** Not applicable — no database.
- **CSRF Protection:** Not applicable — no HTTP surface.

## Error Handling

### Error Codes

Not applicable — no runtime error codes are introduced. The one error path this feature defines is a protocol-level outcome:

| Condition | Behaviour | Requirement |
|-----------|-----------|-------------|
| A task route-back would reset has a non-terminal journal last event | Route-back is INAPPLICABLE: no part of the write set, no worktree/branch cleanup, no route-back commit; `implement` stays `failed`; the phase reports each offending task id and its non-terminal journal last event and returns control via develop's stop condition 3 | FR4 |
| A task's completion report is `failed` or malformed | `tasks.{T}.status = failed` is written in the wake phase | FR1 |

### Error Flow

```
I.2.c route-back requested
  → replay journal for every task whose status would be reset
    → any non-terminal last event?
       yes → make no write, no cleanup, no commit
             keep implement = failed
             report offending task ids + their last events
             return control via develop stop condition 3 ("abort phase" terminal)
       no  → proceed with the existing gate and ordered write set
```

No partial-write path exists between these two outcomes (FR4).

## Performance Optimization

### Performance Goals

Not applicable — documentation-only change (NFR3); no executed behaviour changes.

### Optimization Strategies

Not applicable.

### Caching Strategy

Not applicable.

## Success Criteria

- [ ] All functional requirements (FR1–FR9) are implemented and covered by AC-1 through AC-12.
- [ ] All test scenarios (TS-1 .. TS-11) pass.
- [ ] `python3 -m unittest discover -s tests` passes from the repository root with the six enumerated existing modules unmodified (AC-10).
- [ ] `git diff --name-only` for the change stays inside FR8's declared file set and lists no path under `feature-docs/implement-routeback-gate/` (AC-7, AC-8).
- [ ] `em-workflow/.claude-plugin/plugin.json` and the `em-workflow` entry of `.claude-plugin/marketplace.json` both read version `0.1.37` (AC-9).
- [ ] Every new matcher has a negative-proof test showing it flags the corresponding pre-change wording (AC-12).
- [ ] `implement-phase.md` keeps exactly one normative statement of the recycled-task-id rule and cites, rather than restates, rules owned elsewhere (NFR2).

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

None. Every requirement in this specification has `status: resolved`.

Recorded as an explicit NON-GOAL rather than an open question (D4): `queue_stop_guard.py`'s silence for the remainder of a feature once any task carries a permanent `failed` journal event (`evaluate_feature` returns None whenever `failed` is non-empty) is a real but separate detection defect. No requirement here addresses it and no hook file is modified; the orchestrator files it as a follow-up task.

## Implementation Phases (if applicable)

### Phase 1: Protocol document edits
**Goals:** Harmonize the recycled-task-id rule across its four sites and define the route-back precondition and its failure outcome.
**Deliverables:**
- `em-workflow/references/implement-phase.md`: FR1 (I.2.b step 3 write-back), FR2 (single normative statement), FR3 (I.2.c precondition), FR4 (inapplicable branch), FR5 (unreachability), FR6 (orchestrator-only scope), observing NFR1, NFR2 and NFR4.

### Phase 2: Version bump and verification
**Goals:** Bump the plugin version in both registries and add the document-contract tests.
**Deliverables:**
- `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`: FR9.
- New or extended `tests/` module(s) implementing TS-1 .. TS-11 with negative-proof tests (NFR5, AC-12).

## References

- Requirements document: `feature-docs/recycled-task-id-consistency/REQUIREMENTS.md`
- Target protocol document: `em-workflow/references/implement-phase.md` (Steps I.2.a, I.2.b, I.2.c and the "Supporting cast: journal, hooks, resume" inventory), in the state after the implement-routeback-gate change (PR #4) landed, including the recycled-task-id paragraph its review auto-fix loop 3 introduced (A3)
- `em-workflow/references/workflow-patch.md`: owns `replace_all` / `replace_planning` permission conditions (NFR2)
- `em-workflow/skills/develop/SKILL.md`: owns Step B's stop-condition-3 precedence clause (NFR2, FR4)
- `tests/test_implement_routeback_gate.py`: test pattern and reused byte-identity literal (NFR5, TS-9)
- `tests/test_review_implement_develop_lock_contracts.py`: I.2.b commit literal and ordering anchors (NFR1)
- `tests/test_rework_synthesis_contract.py`: line-wrap-sensitive RAW literals (NFR1)
- `feature-docs/implement-routeback-gate/`: completed feature's documents, left untouched (FR7)
