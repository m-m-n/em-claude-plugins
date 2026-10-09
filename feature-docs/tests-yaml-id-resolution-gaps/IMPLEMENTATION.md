# Implementation Plan: tests-yaml-id-resolution-gaps

## Overview

Close the six remaining holes in the record checker
`tests/test_tests_yaml_id_resolution.py` (SPEC FR1-FR5), realign the
non-execution guarantee in `test/README.md` and the module docstring with the
actual behavior (FR6), add recurrence tests (FR7), and update the tests and the
record that pin the old behavior (FR8).

## Technology Stack

- **Language**: Python 3, standard library only (NFR1) — applies to
  `tests/test_tests_yaml_id_resolution.py` and
  `tests/test_tests_yaml_id_rules_docs.py`.
- **Test runner**: the standard unittest discovery run,
  `python3 -m unittest discover -s tests` (NFR2).
- **New dependencies**: none. No license entry is recorded
  (`project.license: none`; nothing is added).

## Layer Structure

The checker module is a pipeline of stages. Every stage has exactly one
owning task in this feature; a task edits only the stages it owns (plus the
fixture tests for them).

| Stage | Module element (base names) | Owning task |
|-------|-----------------------------|-------------|
| Enumeration | the scan of `test-docs/` (enumerate_records) and the module-level generation of per-record test classes | task0004 |
| Extraction | extract_text and the per-AC loop of check_record | task0003 |
| Syntax gate | canonical_id_failure | task0001 |
| Structural resolution | the structural step of resolve_id | task0002 |
| Loader confirmation | _loader_failure and its recursive suite walk | task0002 |
| Reporting | per-record tests and zero-record guard (unchanged); scan-error test (new) | task0004 (scan-error test only) |
| Module documentation | module docstring and the resolver-section comment | task0002 (see D3) |
| Function documentation | docstrings / section comments adjacent to a stage's code | the owning task of that stage |
| Project documentation | `test/README.md` and `tests/test_tests_yaml_id_rules_docs.py` | task0005 |

Call direction (unchanged from base): check_record calls resolve_id per ID;
resolve_id runs Syntax gate, then Structural resolution, then Loader
confirmation. check_record never calls a later stage directly.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| Checker entry points: canonical_id_failure, resolve_id, check_record, extract_text, enumerate_records | Stage entry points called by every task's fixture tests and by one another | Names, parameters and return shapes stay exactly as at base. A task changes only which inputs fail and the failure reasons, never a shape. enumerate_records keeps its return shape (SPEC A3). | task0001, task0002, task0003, task0004 |
| resolve_id (per-ID judgment) | Judge one ID through Syntax gate, Structural resolution, Loader confirmation | Pre: one candidate ID string (and the base's other parameters). Post: returns the base's "no failure" value or a failure reason; **never raises for any ID** — an exception from the loader or from walking its result becomes that ID's reason (FR4). The module search path and the module cache are equal before and after the call on every exit path. Syntax-gate reasons start with `not a canonical ID` (FR1); a dunder last segment of a method ID gives `not a test method` (FR5). | task0003 (check_record relies on "never raises"), task0001 and task0002 (fixture tests) |
| check_record (per-record judgment) | Turn one record into its list of error lines | Pre: one record (base parameters). Post: returns every extraction error and every resolution error of the record together (FR2); ID errors are reported under their AC key's name; judging continues after any ID failure (FR4, guaranteed by resolve_id's "never raises"). Its loop is owned by task0003; task0002 delivers FR4 inside resolve_id and does not edit check_record. | task0001, task0002, task0003 (fixture tests); task0003 (implementation) |

## Conventions

- **Placement of new tests in the shared file**: new fixture tests go into,
  or immediately after, the existing test class for the same stage —
  Syntax gate next to TestSyntaxGate, extraction next to
  TestExtractionErrors, structural/loader next to
  TestResolutionWithoutExecution, scan next to the existing
  enumeration/record tests. Never append new tests at the end of the file.
  This keeps the hunks of parallel tasks apart.
- **Edit only owned regions**: no reformatting, reordering or renaming outside
  the stages a task owns (Layer Structure).
- **Fixtures**: use the module's existing fixture-package pattern. No new
  fixture relies on the bare `tests` ID being accepted (FR1) or on a dunder
  method ID being accepted (FR5), so fixtures stay valid after all tasks merge.
- **Failure reasons**: every error line names the offending ID or element and
  its reason, in the base's existing line format.
- **Discovery**: new tests are TestCase classes inside the two existing test
  modules, so the discovery run collects them without registration (NFR2).
- **Files no task modifies**: `tests/test_exit4_ac2_test_id_drift.py` (NFR3);
  `feature-docs/tests-yaml-test-id-resolution/SPEC.md` and its
  `reviews/round1.yaml` (SPEC A5); the Test Docs Records section of
  `test/README.md` (SPEC A4); any file under the plugin directories
  `em-workflow/`, `em-review/`, `plugin-dev/` or under `.claude-plugin/`
  (NFR4).

## Cross-task Design Decisions

### D1: Non-execution guarantee — one canonical statement

`test/README.md` (task0005) and the module docstring / resolver-section
comment (task0002) state the same range. Canonical statement, used verbatim
in the README:

> Test method bodies are never executed. Loader confirmation, like ordinary
> test collection, instantiates the test classes (including any custom
> `__init__`) and runs `load_tests` hooks.

The Syntax gate is described with the phrase "two or more dot-separated
segments". No document may still claim that resolved objects are never
called or instantiated.

- Rationale: SPEC FR6 requires the same range in both places.
- Affected tasks: task0002, task0005.

### D2: FR4 is fixed inside Loader confirmation only

A non-suite loader result and any exception raised while walking the
returned suite become the ID's failure reason inside resolve_id ("never
raises" contract above). check_record gains no exception handling for FR4.

- Rationale: one owner per stage; check_record's loop belongs to task0003.
- Affected tasks: task0002 (implements), task0003 (relies on the contract).

### D3: Module docstring has a single owner

Only task0002 edits the module docstring. It describes the behaviors of
SPEC FR1-FR5 as specified (two or more segments; dunder method IDs
rejected; loader non-suite result and walk exceptions fail the ID; readable
IDs in an AC with extraction errors are still resolved; `test-docs/` scan
errors are reported as a test failure) plus D1. Other tasks edit only the
function docstrings and section comments next to their own code.

- Rationale: the module docstring is one block; one editor avoids conflicts.
- Affected tasks: task0001, task0002, task0003, task0004.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Merge conflicts: four tasks edit `tests/test_tests_yaml_id_resolution.py` | High | Medium | Stage ownership (Layer Structure), placement convention, D3; parent-side adoption at merge |
| Post-merge interaction between stages (e.g. task0003 now resolves IDs that task0001's stricter gate rejects) | Medium | Medium | Fixture convention (no reliance on bare `tests` or dunder IDs); TS-7 runs on the integrated tree |
| README and docstring wording drift apart | Low | Low | D1 canonical statement; the doc-contract test pins the README |

## Open Questions

- None.
