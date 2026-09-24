# Implementation Plan: recycled-carveout-reader-count-claims

## Overview

Rewrite two lines of `feature-docs/recycled-task-id-carveout/VERIFICATION.md` (the TS-13 row at line 36 and the Manual Testing item at line 89) so that both address only the two constants covered by that feature's SPEC AC-6 (`HOOK_FILENAMES`, `JOURNAL_ONLY_HOOK_FILENAMES`), and confirm without editing that the module docstring of `tests/test_recycled_task_id_consistency.py` holds no reader-count claim. The feature is a single task (task0001).

## Technology Stack

- **Language / Framework**: none added. The change is Markdown text only.
- **Test runner (existing)**: Python standard-library unittest, run as `python3 -m unittest discover -s tests` (workflow.yaml `project.components.main.test_command`).
- **New dependencies**: none. No license record is needed (`project.license: none`; nothing is added).

## Layer Structure

Not applicable. No code layer is created or changed.

## Shared Components

None. The feature has one task; no component is shared across tasks.

## Conventions

- **Reader site** (glossary term used by every artifact of this feature): a code reference to a constant located outside that constant's definition line. References inside comments and docstrings are not counted.
- **TS-13 criterion** (the one wording both rewritten lines apply): each of `HOOK_FILENAMES` and `JOURNAL_ONLY_HOOK_FILENAMES` is either retired together with all of its references (no definition, 0 reader sites) or has 2 or more reader sites.
- **Line preservation**: every rewritten line stays a single physical line, so the line count of the edited file and the numbering of all other lines are unchanged.

## Cross-task Design Decisions

None. A single task owns the whole change.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| An existing test under `tests/` pins the current wording of line 36 or line 89, so the suite fails after the rewrite | Low | Medium | Run the suite before and after the edit. A failure caused by pinned wording is reported as a plan deviation; `tests/` is never edited (FR4, NFR2). |
| A rewrite spills onto an extra line and shifts every following line of the edited file, breaking FR4 byte-identity | Low | Medium | Line preservation convention above; task0001 AC-6 checks the line count and the line-level diff. |
| SPEC measurements (`HOOK_FILENAMES` reader sites at lines 1290, 1291, 1429) were taken at d8e6d30, while the implement base commit is d19dffc | Low | Low | The criterion is count-based (2 or more), not line-based; line numbers are informative only. |

## Open Questions

- [ ] SPEC AC-5 / TS-4 list only `feature-docs/recycled-carveout-reader-count-claims/` as the allowed workflow-generated path, while FR4 ("this feature's own workflow-generated documents") and the SPEC's Declared Change Set also include `test-docs/recycled-carveout-reader-count-claims/**`, which the implement phase writes. VERIFICATION.md TS-4 accepts both roots.
