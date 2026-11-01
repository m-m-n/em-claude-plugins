# Implementation Plan: control-char-abort-stop-reason

## Overview
A one-paragraph fix to the batch terminal-line contract
(`em-workflow/references/batch-terminal-line.md`, "Precedence rule:"
paragraph) plus a new document test that pins it. The whole feature is one
task, task0001.

## Technology Stack
- **Document**: Markdown reference document of the em-workflow plugin (English).
- **Test**: Python 3 standard library `unittest`, run by
  `python3 -m unittest discover -s tests`.
- **New dependencies**: none, so no license is recorded.

## Layer Structure
| Layer | Artifact | Responsibility | May depend on |
|-------|----------|----------------|---------------|
| Contract | `em-workflow/references/batch-terminal-line.md` | Binds every batch-terminating stop to exactly one reason code | Cites `references/implement-phase.md` by path and step; never restates it |
| Document test | `tests/test_control_char_abort_stop_reason.py` | Pins the binding and the preserved exclusion | Reads the contract document only |

`em-workflow/references/implement-phase.md` is a cited source only. It is not
edited (SPEC A1).

## Shared Components
None. The feature has a single task, and no component crosses a task
boundary.

## Conventions
- **Document citation**: the contract names a stop by its owning document,
  step and check name, and does not restate the owning document's rules.
- **Document-test convention** (`test/README.md` and the existing modules
  that slice this paragraph): standard-library `unittest` only. Read the
  document relative to the test module. Slice the owned region from its label
  to the next blank line. Normalize whitespace before phrase matching. Assert
  distinctive phrases, not whole sentences. Give every new matcher a negative
  proof and a non-vacuity guard.
- **Existing pinned test modules** are run and never rewritten or retargeted
  (SPEC A4). If an existing pin goes red, the document text is fixed. The pin
  is not changed.

## Cross-task Design Decisions

### D1: One task for the edit and its pinning test
- **Decision**: the paragraph edit and the new test module form a single
  task.
- **Rationale**: the test's matchers key on phrases that only the new text
  contains. Splitting the work would mean freezing the paragraph's wording
  here as a cross-task contract, for an edit of one paragraph.
- **Affected tasks**: task0001.

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| The appended text breaks an existing pin of the paragraph: a blank line, the order of the exclusion anchor before "`failed_kind` reads `decision`", a retired phrase, or `no-work-required` | Medium | Medium: suite red | Append at the end of the paragraph with no blank line and no existing line changed; run the full suite (VERIFICATION.md TS-5) |
| A new matcher is vacuous because its token already occurs in the pre-change paragraph (`stop-condition-3`, `step_needs_intervention`, "Step I.2.a", `implement: failed`, "exception") | Medium | Medium: a regression goes undetected | Key matchers on phrases only the new text contains; negative proof against the verbatim pre-change paragraph (TS-3) |
| The exception reads as a general rule for current-run `implement: failed` writes, or as overriding the exit-4 binding | Low | Medium: other stops' reason changes | Name the Step I.2.a stop and confine the exception to it; leave the exit-4 sentence unchanged (SPEC A2, A3) |

## Open Questions
None.
