# Implementation Plan: task-id-allocation-ssot

## Overview

Make the 'Re-planning task-id allocation' section of `em-workflow/references/workflow-patch.md` the only place that defines task-id allocation. Remove the id-recycling / renumbering premise from `em-workflow/references/implement-phase.md` I.2.c, and re-ground the three existing recycled-task-id countermeasures on "a task's own id owns its own journal terminal events". No runtime behaviour changes.

## Technology Stack

- **Markdown reference documents**: the plugin's normative SSOTs. This is the primary change surface.
- **Python 3**: one hook module docstring and one validator comment. No executable-code change.
- **Python standard-library unittest**: test runner (`python3 -m unittest discover -s tests`).
- **New dependencies**: none. `project.license` is `none`, so no license constraint applies and there is no dependency license to record.

## Layer Structure

| Layer | Members | Responsibility |
|-------|---------|----------------|
| Owning SSOT | `em-workflow/references/workflow-patch.md`, section 'Re-planning task-id allocation' | The only definition of the allocation rule: ids are never re-issued, new ids are numbered above the high-water mark, and registered ids are carried verbatim through `tasks_patch.carried_task_ids`. This feature does not change it. |
| Citing documents | `em-workflow/references/implement-phase.md` (I.2.a, I.2.c), `em-workflow/agents/implementation-planner.md`, `em-workflow/references/contracts/planner-contract.md`, `em-workflow/references/phases/create-plan-phase.md` | Name the owning section and state only the consequences they need. They never restate the rule. This feature edits only I.2.c. |
| Code-side explanations | module docstring of `em-workflow/hooks/queue_stop_guard.py`; the re-planning allocation comment in `em-workflow/scripts/validate-worker-output.py` | Explain the mechanism the adjacent code implements, in terms consistent with the owning rule. Executable code is out of scope. |
| Tests | `tests/` | Pin the new wording, each pin paired with a negative proof, and pin the version bump. |

Dependency direction: citing documents and code-side explanations point at the owning SSOT. The owning SSOT never points back to them for the rule's content.

## Shared Components

No task declares a file that another task also declares. No task consumes a component that another task builds. There is therefore no component contract to pin. The only thing the tasks share is the vocabulary under Conventions, which each task writes into its own files.

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| (none) | — | — | — |

## Conventions

### C1: Citation, not restatement (NFR4)

- A citation names both the document (`references/workflow-patch.md`) and the section heading 'Re-planning task-id allocation', verbatim.
- Outside the owning section, no text restates:
  - the high-water-mark expression
  - the field list of a carried record
  - the rejection conditions
- A citing text may state the consequence it needs, for example "task ids are never re-issued" or "the id is carried verbatim". It must attribute that consequence to the cited section.

### C2: Own-id terminal-event vocabulary (shared by both tasks)

- The premise that replaces recycling:
  - A task id is never re-issued (by citation of C1).
  - Therefore no task carries another task's journal terminal event.
  - Every terminal event a task has is its own.
- The failed+pending exception is always described as follows: the task's own id, returned from `failed` to `pending` by route-back, and carried unchanged by the re-planning pass.
- No text states or implies that `replace_all` recycles, renumbers, reuses or re-issues an id.

### C3: Premise wording to remove (matched after whitespace normalization)

- In implement-phase.md I.2.c:
  - 'recycles every id'
  - 'renumbered task id'
  - 'leaves a recycled id launchable'
  - 'no recycled id can ever inherit'
  - the sentence 'The planner re-scopes the failed task (split it, change the approach)'
- In the module docstring of queue_stop_guard.py: 'a recycled task id left behind by a route-back re-plan'.
- In the re-planning allocation comment of validate-worker-output.py: any claim that a re-planning `replace_all`'s `entries` re-declares every registered id.

### C4: Label retention (FR6)

- The reference labels 'recycled-task-id carve-out' and 'recycled-task-id rule' stay byte-identical wherever they occur today.
- Only the explanation around a label changes. A label is never renamed and never removed.

### C5: Behaviour invariance (NFR2)

- In the hook and validator Python files, only docstring and comment lines change.
- Parsing each file with its docstrings removed must give the same syntax tree before and after the change.
- The following files are not touched at all: `queue_launch_guard.py`, `queue_failure_net.py`, `queue_taskstop_net.py`.

### C6: Test conventions (NFR3)

- Tests use the Python standard library only and follow `test/README.md`.
- New test modules are named `tests/test_task_id_allocation_ssot_*.py`.
- Every wording matcher, whether positive or negative, is paired with a negative proof. The proof runs against a pre-change sample embedded as a literal in the test module, captured verbatim from the file BEFORE editing.
  - For an absence matcher, the proof shows the matcher fires on the pre-change sample.
  - For a presence matcher, the proof shows the matcher does not fire on the pre-change sample.
- Live text and samples go through the same whitespace normalization: runs of whitespace collapse to one space.
- Section-scoped checks slice from the section heading to the next heading of the same or higher level.
- An existing test module that SPEC.md says passes "unchanged" is not edited.

### C7: Version fields

Exactly one task edits version fields: the task whose plan declares `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`. No other task touches them.

## Cross-task Design Decisions

### D1: The owning SSOT stays as written

- **Decision**: 'Re-planning task-id allocation' in `references/workflow-patch.md` owns the allocation rule, and its content does not change. The planner, planner contract and create-plan phase documents already cite it and are left as they are.
- **Rationale**: this decision is recorded as confirmed in REQUIREMENTS.md 14.1.
- **Verification**: these existing test modules must pass without modification:
  - `tests/test_workflow_patch_doc.py`
  - `tests/test_replanning_producer_alignment.py`
- **Affected tasks**:
  - the I.2.c rewrite task cites the section;
  - the code-comment task's validator comment describes `carried_task_ids` in a way consistent with the section.

### D2: Countermeasures kept; rationale re-grounded on the task's own id

- **Decision**: under the owning rule, recycled-id inheritance cannot occur. Each of the three countermeasures is still necessary, for a reason that does not depend on id reuse:
  - **Route-back gate third conjunct**: suppose a task's own last journal event is `merged` and the ancestry check fails. Without this conjunct, the task would be reset to `pending`, and the launch guard would then deny its relaunch.
  - **failed+pending carve-out**: route-back returns the task's own `failed` status to `pending`, and the re-planning `replace_all` carries that id verbatim.
  - **`deny_already_merged`**: prevents a second launch of a task's own merged id. It is unrelated to id reuse.
- **Where it is recorded**:
  - The I.2.c rewrite task records this re-judgment in I.2.c.
  - The code-comment task aligns the stop-guard docstring's description of the carve-out with the second item.
- **Constraint**: neither task changes a gate condition, the carve-out condition, or launch-guard behaviour.

### D3: Single owner for the version bump

- **Decision**: exactly one task (C7) applies the em-workflow patch bump, to both manifests, with the same value.
- **Rationale**: two parallel tasks each bumping the version would produce a two-step bump, which violates SPEC AC-9 ("patch 1 段上がっている").

### D4: Code-invariance is verified at feature level

- **Decision**: each task's evidence is that the existing behaviour suites pass without modification. The byte-level "code unchanged except docstrings/comments" claim (SPEC AC-6, AC-8, NFR2) is checked once, in the verify phase: a syntax-tree comparison against `workflow.implement.base_commit` (VERIFICATION.md, Code Quality Verification).
- **Rationale**: a persisted unit test would need the pre-change file contents, and those stop being meaningful after merge.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| A test module other than `tests/test_implement_routeback_gate.py` pins one of the removed I.2.c sentences | Medium | The suite fails after the rewrite | The I.2.c task declares the three retention-test modules in its files. It updates only a literal that pins a removed premise sentence, adding a negative proof. Label-retention literals stay untouched (C4). |
| The rewrite narrows the route-back gate's third conjunct | Low | A merged task whose ancestry check fails gets stuck, because the launch guard denies it | The existing THIRD_CONJUNCT opening / source / independence / never-narrowed anchors must keep matching unchanged |
| The re-scope rewrite widens planner behaviour, for example by implying the planner may edit a carried task's plan | Medium | Contradicts the owning section's verbatim carry | The replacement adds work only as new ids above the high-water mark, keeps the SPEC.md update path, and grants no new action |
| A version bump from another feature lands on main at the same time | Low | Duplicate version, or a merge conflict in the manifests | The bump test asserts a version strictly greater than every existing baseline. A conflict is resolved at merge. |
| The pre-change sample is captured after editing | Low | The negative proof becomes vacuous | C6: capture before editing. Each negative proof asserts its expected outcome against the sample. |
| A docstring or comment edit alters executable code | Low | Runtime behaviour change (NFR2) | Behaviour suites run unmodified, plus the verify-phase syntax-tree comparison (D4) |

## Open Questions

- None.
