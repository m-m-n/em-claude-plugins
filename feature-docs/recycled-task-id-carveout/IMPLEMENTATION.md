# Implementation Plan: recycled-task-id-carveout

## Overview

Rewrite the self-contradictory scope statement in `em-workflow/references/implement-phase.md` I.2.a into a single rule, scope its citing Supporting-cast bullet to the carve-out, and replace the filename-presence pin with separated wording claims plus a two-layer pin (static hook-source scan + behavioral stop-guard observation) joining the documentation to the hook implementations.

## Technology Stack

- **Language**: Python 3 (test code only) and Markdown/JSON (documents and registries).
- **Test framework**: standard-library `unittest`, run by `python3 -m unittest discover -s tests` from the repository root.
- **Key libraries**: none. No new dependency is introduced by this feature, so there is no new license to record (`project.license: none`; nothing to check against `references/license-compat.md`).
- **Build / format**: none exist for this repository (`workflow.yaml` `project.components.main` declares empty `build_command` and `format_command`).

## Layer Structure

| Layer | Members | Allowed direction |
|---|---|---|
| SSOT prose | `implement-phase.md` I.2.a | normative; cites nothing below it |
| Citing consumers | Supporting-cast Stop-hook bullet, I.2.b step 1 citation | cite I.2.a; never restate its rule in independently-driftable form |
| Pin layer | `tests/` modules | read prose and hook sources, observe hook behavior; never modify either |
| Implementation | the four `em-workflow/hooks/queue_*.py` files | READ-ONLY for this feature (NFR4) |

No layer below the pin layer is written by any task in this feature. Every task that touches `tests/` reads its targets by repository-relative path; there is no installable package and no import between test modules.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|---|---|---|---|
| Hook classification contract | The one classification both the prose and the pin must express | Precondition: the four hook sources are unchanged. Postcondition: `queue_stop_guard.py` is the single hook applying the recycled-task-id carve-out (journal last event `failed` + that task's own workflow.yaml status exactly `pending` → treated as unlaunched); `queue_launch_guard.py`, `queue_failure_net.py`, `queue_taskstop_net.py` derive a task's state from the journal's last event alone and never consult `tasks.{T}.status`. Any statement of this classification — prose sentence, wording matcher, or source scan — must be a rendering of exactly this table row set, never a superset or a reordering. | task0001 (states it in prose and pins the wording), task0002 (pins it against the sources and against observed behavior) |
| Test-module ownership map | Prevents two tasks from editing one test module | Precondition: each module below has exactly one owning task. Postcondition: a task modifies only the modules it owns. `tests/test_recycled_task_id_consistency.py` → task0001. `tests/test_queue_hook_status_read_pin.py` (new) → task0002. `tests/test_recycled_task_id_carveout_version_bump.py` (new) → task0003. Every other module under `tests/` is read-only for every task in this feature. | task0001, task0002, task0003 |
| `implement-phase.md` section anchors | Stable slice boundaries three unmodified test modules depend on | Precondition: the headings `### I.2.a: Launch phase`, `### I.2.b: Wake phase`, `### I.2.c: Failed handling`, `### Supporting cast` exist byte-identically and in that order. Postcondition: unchanged by this feature — no heading text, level or ordering change, and no content moved across a heading boundary. | task0001 (must preserve), task0002 / task0003 (must not touch the file at all) |

## Conventions

- **Test placement / naming**: all test code stays in the repository-root `tests/` directory; new modules are `test_<target>.py`, classes `Test<Behavior>`, methods `test_<condition>_<expected_result>`; discovery is automatic, with no registration step (NFR2, `test/README.md`).
- **Dependency floor**: test code imports only the standard library and never assumes a third-party package is installed (NFR1).
- **No cross-test-module imports**: a module that needs a literal or a fixture shape defined in another test module reproduces it locally with a provenance comment naming the source and the commit it was captured at. This is the module's established precedent (`tests/test_recycled_task_id_consistency.py` copies TS-9's byte-identity literal rather than importing it) and it keeps every module independently runnable and independently owned.
- **Prose assertions are whitespace-normalized**: assertions over `implement-phase.md` prose compare against a whitespace-normalized copy of the relevant section so a reflow never makes them brittle. The byte-identity and raw line-wrap guards are the deliberate exception and keep comparing raw text (NFR3).
- **Non-vacuity discipline** (the module's four contracts, applied by every task that adds a matcher):
  1. each new-wording matcher keeps its literal in ONE module-level constant, read by both its positive test and its negative-proof test;
  2. each negative proof runs against a captured pre-change sample (verbatim excerpt, not a paraphrase, with a provenance comment naming the source file and the base commit);
  3. a matcher asserting retention of pre-existing wording needs no negative proof;
  4. each sample carries a positively-asserted RETAINED anchor in a class named `TestPreChangeSampleGuards`, so a negative proof cannot degrade into a tautology against an emptied sample.
- **Error handling**: the only failure channel in this feature is an assertion failure surfacing as a non-zero exit from the test command. No runtime error path is added, and the hooks' fail-open convention is observed, never altered.
- **Hook sources and `hooks.json` are read-only**: no task changes hook behavior, registration, or byte content (NFR4).

## Cross-task Design Decisions

### D1: The document edit and the assertions that pin it live in the SAME task

`tests/test_recycled_task_id_consistency.py` asserts literals of `implement-phase.md`. Tasks run fully in parallel in isolated worktrees, so splitting the prose rewrite from the assertion rewrite would leave each worktree with a half-updated pair and a red suite — which would break the "tests passing = task done" contract for both sides. Therefore FR1/FR2/FR6 (prose) and FR3/FR5-prose (assertions) are one task (task0001). Affected: task0001.

### D2: The two-layer hook pin is a NEW, self-contained module

FR4's two layers read hook sources and observe `queue_stop_guard.py`'s behavior. Neither depends on the revised prose, so they can be developed and verified independently of task0001. Putting them in a new module (`tests/test_queue_hook_status_read_pin.py`) instead of extending `tests/test_recycled_task_id_consistency.py` keeps the ownership map single-writer, keeps the new module green in its own worktree against the pre-change document, and avoids a second task editing task0001's file. Consequence for FR5: the new module carries its OWN non-vacuity classes, including its own class NAMED `TestPreChangeSampleGuards`, so FR5's discipline is satisfied per-module rather than by a shared class. Affected: task0002 (and, as a non-dependency, task0001).

### D3: Layer 2 deliberately re-derives coverage that `tests/test_queue_stop_guard.py` already has

`tests/test_queue_stop_guard.py` already contains behavioral coverage of the carve-out discriminator. It stays unmodified and is NOT imported. The new Layer 2 test exists for a different purpose — it is the pin joining the DOCUMENTED classification to observable behavior, and must fail if the hook's carve-out behavior ever diverges from what I.2.a claims — so the duplication is accepted and recorded rather than removed. Affected: task0002.

### D4: Protected-literal inventory for `implement-phase.md`

Thirteen test modules read `implement-phase.md`; twelve of them are read-only for this feature and must stay green. The rewrite of I.2.a and of the Supporting-cast bullet must therefore preserve, verbatim, at least the following (non-exhaustive — the full suite is the authority, and running it is an acceptance criterion of task0001):

| Protected item | Pinned by (unmodified module) |
|---|---|
| The raw line-wrap literal joining `` `tasks.*.status`. Select `` to the following `unlaunched tasks (no journal event yet and ...` line | `test_recycled_task_id_consistency.py` (TS-7), `test_routeback_reset_scope_consistency.py` |
| `This carve-out is deliberately scoped to ` + `failed` + ` only` | `test_routeback_reset_scope_consistency.py` |
| The in-flight sentence `A task whose journal last event is ...launched... is always in-flight, regardless of workflow.yaml ...status...` | both modules above |
| The unreachability sentence opening `Given I.2.c's route-back precondition`, its terminator `can never arise.`, and the tokens `replace_all` / `launched` / `pending` inside that slice | `test_routeback_reset_scope_consistency.py` |
| The recursion-invariant sentence `no retired task id can leave a ...merged... last event behind for a renumbered task to inherit`, positioned AFTER `can never arise.` | `test_routeback_reset_scope_consistency.py` |
| The normative opening `Recycled task id: workflow.yaml's status wins over a stale journal event here` | `test_recycled_task_id_consistency.py` (retention matcher) |
| The I.2.b step 1 citation `the recycled-task-id rule in I.2.a above` | `test_recycled_task_id_consistency.py` (NFR6) |
| The whole-file absence of any line that, after stripping indentation and backticks, begins with `git ` and contains `commit` or `add -A` | `test_recycled_task_id_version_bump.py`, `test_routeback_reset_scope_consistency.py` |
| The four section headings of the anchors contract above | `test_implement_routeback_gate.py`, `test_routeback_reset_scope_consistency.py`, `test_recycled_task_id_consistency.py` |

The edit is therefore surgical: only the closing scope sentence of the I.2.a recycled-task-id paragraph is replaced (plus the appended divergence statement), and only the equivalence clause of the Supporting-cast Stop-hook bullet is rescoped. Affected: task0001.

### D5: Exactly one task owns both version-carrying files, and no test pins the literal

`em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` (the `em-workflow` entry) are modified by task0003 only, so the two values can never disagree through a partial merge. Following the repository's established precedent, the automated assertion is DURABLE — the two values are equal, of the form `0.1.Z`, and `Z` is strictly greater than the pre-change baseline `44` — rather than an equality against the literal `0.1.45`, which would go red on the next unrelated bump. The literal `0.1.45` itself is confirmed at verify time by direct file read (VERIFICATION.md success criteria). Every pre-existing version-bump module already asserts `patch > <its own older baseline>`, so the bump keeps them green. Affected: task0003 (and, by exclusion, task0001 / task0002, which must not touch either file).

### D6: The static scan keys on identifiers, never on the bare substring `workflow.yaml`

Layer 1 proves a negative claim over source text. Its matcher keys on the identifiers that CONSTITUTE a per-task status read in this codebase — the `task_statuses_from_workflow` helper name and the `TASK_STATUS_RE` / `TASKS_SECTION_RE` line-scan regex names used by `queue_stop_guard.py` — and never on the bare substring `workflow.yaml`, because `queue_taskstop_net.py`'s module docstring contains that substring while reading nothing. The accepted boundary (recorded in SPEC.md's assumptions): a hook reading a task status by an entirely novel mechanism, e.g. via a YAML library, is not caught by a source-text pin. Affected: task0002.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| The I.2.a rewrite breaks a literal pinned by one of the twelve unmodified modules that read `implement-phase.md` | High | High (red suite at merge, rework round) | D4's inventory + task0001 acceptance criterion requiring the WHOLE suite green in its own worktree, not just its own module |
| The Layer 1 matcher false-positives on `queue_taskstop_net.py`'s docstring mention of `workflow.yaml` | Medium | Medium (permanently red or, if "fixed" by weakening, a vacuous scan) | D6's identifier-only matcher + a paired sample containing ONLY the bare substring, asserted NOT to be a violation |
| The Layer 2 fixture fails to resolve an enumeration root, so the hook exits 0 for the wrong reason and the "exit 0" case passes vacuously | Medium | High (a test that can never fail) | The exit-2 case and the exit-0 case share ONE fixture builder and differ only in the task's workflow.yaml status value, so a broken fixture makes the exit-2 case fail loudly |
| A revised matcher ends up satisfiable by mere filename presence again | Medium | High (reproduces the very defect this feature closes) | FR3's two separated claims, each with its own negative proof against a captured pre-change sample, plus the retained-anchor guard |
| A concurrent feature bumps the same version files | Low | Medium (merge conflict) | Single-owner rule (D5) + durable `patch > baseline` assertions that survive any higher value |
| Layer 2 duplicates existing stop-guard coverage and is later deleted as redundant | Low | Medium (loses the documentation-to-behavior join) | D3 records the intent explicitly, and the new module's docstring states why the duplication exists |

## Open Questions

- [ ] FR5 names `TestPreChangeSampleGuards` as the guard location. This plan interprets that as a per-module class NAME (D2), so task0002's new module carries its own class of that name rather than appending to task0001's. Confirm at review that the per-module reading is intended.
- [ ] SPEC.md's Test Scenarios list TS-1..TS-11 while `tests/test_recycled_task_id_consistency.py` already uses TS-1..TS-10 internally for the PREVIOUS feature's scenarios. SPEC.md notes these are separate namespaces; confirm at review that no in-module renumbering is expected (this plan assumes none).
