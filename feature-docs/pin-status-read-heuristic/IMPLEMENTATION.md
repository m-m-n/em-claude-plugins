# Implementation Plan: pin-status-read-heuristic

## Overview

Replace the identifier-name heuristic in the hook classification pin's per-task-status observer (`reads_per_task_status` in `tests/test_hook_classification_pin.py`) with a name-independent substring co-occurrence rule, remove the heuristic, rewrite the explanatory text, and add regression tests that pin the new rule. The whole feature is one task (task0001).

## Technology Stack

- **Language**: Python 3 (repository-root test suite)
- **Framework**: standard-library unit test framework, run with `python3 -m unittest discover -s tests`
- **Key libraries**: standard library only (NFR1). No new dependency is introduced, so no dependency license entry applies (`project.license: none`).

## Layer Structure

The change stays inside one test module. Its parts and the allowed dependency direction (top may use bottom, never the reverse):

| Part | Responsibility | May depend on |
|------|----------------|---------------|
| Test classes (`TestHookClassificationPin`, `TestPinIsNotAVacuousCheck`, `TestObserveHookSource`, new regression tests) | Pin the documented-vs-observed classification and the observer's behaviour | every part below |
| Comparator (`compare_table_to_sources`) | Compares each documented classification row against the observed classification and returns the mismatches | parser rows, source observer |
| Source observer (`reads_per_task_status`) | Decides from one hook source file whether it reads per-task status | docstring/comment stripper |
| Docstring/comment stripper (`_strip_docstrings`) | Produces the executable text of a source file (docstrings and comments removed) | — |
| Classification table parser (`parse_classification_table`) | Turns the Hook classification table documented in `em-workflow/references/implement-phase.md` into rows | — |

Nothing in the module writes under `em-workflow/`; it only reads hook sources and the classification table (NFR2, NFR4).

## Shared Components

Only one task exists, so no component is shared between tasks. The rows below pin the module surface that an existing sibling test module consumes and that the comparator relies on; they must stay stable.

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| `parse_classification_table`, `compare_table_to_sources`, `READS_STATUS`, `DOES_NOT_READ_STATUS` | Existing public surface of the pin module | Names and signatures unchanged (FR3). `compare_table_to_sources` keeps returning one (path, documented classification, observed classification) tuple per mismatching row. | task0001 (owner; behaviour kept). Existing importer: `tests/test_recycled_task_id_consistency.py` (not modified) |
| `reads_per_task_status(hook_path)` returning a boolean | Per-task-status observation for one hook source | Pre: `hook_path` names an existing file; otherwise `ClassificationTableError` is raised. Post: True if and only if the executable text (docstrings and comments stripped by `_strip_docstrings`; identifiers and string literals included) contains both the substring "workflow.yaml" and the case-sensitive substring "status". Function names, call relations and reachability play no part. Signature unchanged. | task0001 (owner); consumed by `compare_table_to_sources` |

## Conventions

- Test code imports standard-library modules only (NFR1).
- Synthetic hook sources exist only as temporary files created through the standard-library temporary-file facility and are removed by test cleanup. No test writes under `em-workflow/` (NFR2).
- Changes are confined to `tests/`. No plugin version (plugin.json / marketplace.json) is bumped (NFR4).
- One observation rule applies uniformly to every classification row. No per-hook branch, allow-list or exception is introduced (NFR3).
- Expected outcomes of pre-existing tests are not changed. Only comments and docstrings that describe the removed name/call rule are rewritten (FR9).

## Cross-task Design Decisions

### D1: The feature is a single task

- **Decision**: all requirements (FR1-FR9, NFR1-NFR4) are implemented by task0001.
- **Rationale**: every change lands in the same test module, and the regression tests for FR4, FR6 and FR8 can only pass against the new rule from FR1. Splitting would make parallel worktrees edit the same functions and duplicate the rule.
- **Affected tasks**: task0001.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| The new rule flips the observation of one of the five real hooks (queue_stop_guard / queue_launch_guard / queue_failure_net / queue_taskstop_net / bash_guard) | Low (SPEC A1 checked the executable text of all five) | High (pin red on the base branch) | task0001 AC-6 and verification TS-6 run the unchanged pin test and the real-hook observation tests |
| A pre-existing synthetic source in the module flips under the new rule | Low (SPEC A2) | Medium | Expected outcomes of existing tests must not be edited; a flip is reported as a plan deviation instead |
| `tests/test_recycled_task_id_consistency.py` imports a removed name | Low (SPEC A8; that file was not scanned) | Medium | Removal is limited to `_TASK_STATUS_NAME_RE`, `task_status_fn_names`, `called_names` and the import they alone used; the full suite runs in task0001 AC-6 and verification |
| A regression test is vacuous (would also have passed under the removed rule) | Medium | Medium | task0001 fixes the synthetic helper names so none matches the removed name pattern, and the uppercase-only test asserts its own precondition |

## Open Questions

None.
