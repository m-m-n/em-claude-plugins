# Implementation Plan: first-entry-timestamp-scan

## Overview

Adds two regression tests that pin D2 form 2 (marker-based current-session
resolution, `feature-docs/orphaned-implementer-recovery/IMPLEMENTATION.md`
D2) against transcripts whose leading records carry no `timestamp`: one
drives the whole orphan recovery through the command-line entry point (FR1),
one checks the resolution function's result directly (FR2). No production
code changes (FR3).

## Technology Stack

- **Language**: Python 3, standard library only (NFR1).
- **Test framework**: `unittest` from the standard library, collected by
  `python3 -m unittest discover -s tests` run from the repository root
  (NFR2).
- **New dependencies**: none. No package manifest is touched, so no license
  compatibility question arises; `project.license` is `none`.

## Layer Structure

| Layer | Component | Role in this feature | Changed |
|---|---|---|---|
| Test | `tests/test_recover_orphaned_task.py` | Hosts both new regression tests | Yes — additions only |
| Decision (under test) | `em-workflow/scripts/recover-orphaned-task.py` | Exercised through its command-line entry point (FR1) and its current-session resolution function (FR2) | No (FR3) |
| Journal-write (under test) | `em-workflow/scripts/journal-append-failed.py` | Reached in FR1 through the decision layer's default sibling-helper wiring | No |

Dependency direction: the tests depend on the scripts; nothing depends on
the tests.

## Shared Components

None. The feature has a single task. The two scripts under test are consumed
through their existing, unchanged contracts —
`feature-docs/orphaned-implementer-recovery/IMPLEMENTATION.md` SC2 (journal
helper), SC3 (decision entry point), SC5 (session identity rule), D2
(current-session resolution) and D7 (agent index binding) — which this
document cites rather than restates.

## Conventions

- **Test isolation (NFR1)**: every journal, agent index and transcripts
  directory handed to the script lies inside a per-test temporary directory.
  The transcripts directory is always given explicitly — `--transcripts-dir`
  on the command line, the directory argument at function level — so the
  default derivation under the real `~/.claude` is never reached, and real
  `~/.claude` state is never read or written.
- **Frozen files (FR3, NFR3)**: no task of this feature, including any later
  rework task, modifies `em-workflow/scripts/recover-orphaned-task.py`,
  `feature-docs/orphaned-implementer-recovery/IMPLEMENTATION.md` (D2) or
  `feature-docs/orphaned-implementer-recovery/VERIFICATION.md` (TS-14). A new
  test that fails against the unchanged script is a test defect or a finding
  to report, never a license to change the script.
- **Plugin versions (NFR4)**: no task edits
  `em-workflow/.claude-plugin/plugin.json` or
  `.claude-plugin/marketplace.json`.
- **Existing tests**: no existing test in the module is removed or altered;
  the new tests are pure additions.

## Cross-task Design Decisions

### D1 — Extend the existing test module instead of adding a new one

Both tests go into `tests/test_recover_orphaned_task.py`: FR1's beside the
existing command-line entry point tests, FR2's beside the existing
current-session resolution tests. The module already loads the script under
test, already provides the fixture writers and the child-process runner
these tests need, and is where D2 form 2 is already covered; a new module
would have to duplicate those helpers. The module's header docstring maps
each test to the acceptance criterion it covers, grouped by feature and
task; the new tests are listed there under this feature's name, following
that convention.

Any later rework task that adds a test for this feature uses the same
placement. Affects task0001.

### D2 — Regression pins against already-correct behaviour

The script already derives the form 2 start as the earliest parseable
timestamp of the committed transcript. Both tests are therefore expected to
pass on their first run against the unchanged script. Their value lies in
the fixture shape: each fixture is one on which the regressed derivations
named in SPEC.md — reading only the first line (unresolved) and taking the
positionally-first timestamp (15:00) — give an answer different from the
correct one. The script is never altered to obtain a failing run; the
discriminating power of each fixture is established by the shape its task's
acceptance criteria pin. Affects task0001.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| A later edit simplifies a fixture (e.g. gives the leading record a `timestamp`) and removes its discriminating shape | Low | The regression it guards goes undetected | The task's acceptance criteria pin the shape; the module docstring names what each test guards |
| The FR1 fixture violates the real journal helper's preconditions (journal file must already exist, must not be a symbolic link) | Medium | The run exits non-zero instead of reporting `recovered` | Stated in the task plan's Test Notes |
| The real transcript layout drifts beyond the fixtures' shape | Medium | Automated tests pass while real resolution fails | TS-4 manual check against a real session |
| A test reaches the default transcripts-directory derivation | Low | The suite depends on, or touches, real user state | Test isolation convention above; checked under TS-3 |

## Open Questions

None.
