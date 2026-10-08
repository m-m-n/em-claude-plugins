# Implementation Plan: tests-yaml-test-id-resolution

## Overview

Rewrite every `acceptance_tests.*.tests` element of `test-docs/**/*.tests.yaml` into a canonical unittest ID (three cleanup tasks over disjoint record ranges), add a standard-library-only record check to `tests/` that fails once per record file on any extraction or resolution error, and add the record-writing rules to `em-workflow/agents/implementer.md` and `test/README.md`.

## Technology Stack

- **Language**: Python 3; every new test module imports the standard library only (NFR1)
- **Test framework**: unittest, run as `python3 -m unittest discover -s tests` from the repository root (NFR2)
- **New dependencies**: none, so no license is recorded (`project.license` is `none`)

## Layer Structure

| Layer | Contents | Written by |
|---|---|---|
| Record data | `test-docs/**/*.tests.yaml`; the ID mapping records under `test-docs/tests-yaml-test-id-resolution/` | task0002, task0003, task0004 |
| Checks | `tests/test_tests_yaml_id_resolution.py` (record check); `tests/test_tests_yaml_id_rules_docs.py` (document-contract test) | task0001, task0005 |
| Documentation | `em-workflow/agents/implementer.md`; `test/README.md` | task0005 |

Allowed dependencies: the checks read record data and documentation as text. The record check reaches test modules only through ID resolution (SC-1) and imports nothing outside the standard library. Record data and documentation depend on nothing in the checks.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|---|---|---|---|
| SC-1 Canonical test ID and resolution criterion | The only accepted form of a `tests` element in this repository, and how acceptance is judged | Pre: an element string and a root directory. Post: accepted only when every SC-1 step passes; nothing resolved is called, no test is run, the module search path is unchanged afterwards | task0001 (enforces), task0002, task0003, task0004 (produce), task0005 (documents) |
| SC-2 Supported record notation | The YAML subset the record check reads | Pre: one record file. Post: either an AC key to ordered ID list mapping, or extraction errors naming file and AC; opaque values never contribute IDs | task0001 (implements), task0002, task0003, task0004 (leave every record inside it), task0005 (documents) |
| SC-3 ID mapping record | Audit trail of every removed or replaced ID | Post: one row per removed old-ID occurrence; the row count equals the diff's removed-occurrence count | task0002, task0003, task0004 (write); verify (TS-3) |
| SC-4 Cleanup partition | Disjoint record ranges for the cleanup | Post: every record outside `test-docs/tests-yaml-test-id-resolution/` belongs to exactly one range | task0002, task0003, task0004 |
| SC-5 red_reason append convention | How FR2 moves a removed element's text into `red_reason` | Post: the parsed pre-existing value is the exact prefix of the parsed new value; no key is added | task0002, task0003, task0004 |
| SC-6 Test module names | Fixed names of the two new test modules | Post: the names below are used verbatim | task0001, task0005 |

### SC-1: Canonical test ID and resolution criterion (FR1, FR6)

Environment: as under the project test command run from the repository root, where the repository root and `tests/` are both on the module search path (A1). The record check additionally puts the repository root (or a fixture root) at the front of the module search path for the duration of each check (FR6).

Steps, in order. The first failing step ends the evaluation of that element; no later step runs for it.

1. **Syntax gate**: the element consists of one or more dot-separated segments, each a valid Python identifier, and the first segment is exactly `tests`. File paths, `path::Class::method` forms, wildcards, abbreviations and free text fail here. No import and no loader call happens for an element that fails this gate.
2. **Structural resolution**: the longest leading part of the element that names an importable module is imported; the remaining segments are looked up as attributes without calling anything. A module that exists but fails while importing is a failure whose reason carries the import error. The final object must be one of:
   - (a) a module;
   - (b) a class derived from the unittest test-case base class, other than the base class itself;
   - (c) a function reached as an attribute of such a class and defined on that class or on one of its ancestors that is neither the unittest test-case base class nor an ancestor of that base class.
   Anything else fails: a missing module or attribute, a class not derived from the base class, a module-level function or any other callable, a method available only through the base class.
3. **Loader confirmation**: the element is passed to the standard unittest loader's load-by-name operation on a fresh loader. It fails when the operation raises, when the loader's error list gains an entry, or when the returned suite, walked recursively without being run, contains a failed-test placeholder.
4. The checker never calls anything it resolved and never runs a returned test.
5. The module search path is restored to its exact prior value after every check, including when a step raises.

Cleanup output (task0002, task0003, task0004) additionally guarantees that the loader result of every element it leaves in a record contains at least one test, because the verify reproduction procedure (TS-2) counts a zero-test result as unresolved. The record check does not add this condition, because FR6 does not include it.

### SC-2: Supported record notation (FR7, FR4, FR8)

A record is read as UTF-8 text, line by line. Indentation uses spaces only.

- **Ignored lines**: blank lines and full-line comments (first non-space character `#`) at every structural level; one optional document start marker `---` before the first top-level key.
- **Keys**: a plain or single-line quoted key followed by a colon. A trailing comment (whitespace, then `#`, outside quotes) is allowed on every key line and every `tests` item line.
- **Top level**: keys at column 0. `acceptance_tests` occurs exactly once and has nothing after its colon except an optional comment.
- **AC level**: the keys one level under `acceptance_tests`, all at one common indentation. Every key name is accepted as an AC key (`AC-n` or any other name, such as `D4-parser-unavailable`). An AC key has nothing after its colon except an optional comment.
- **Field level**: the keys one level under an AC key, all at one common indentation. Exactly one field is `tests`.
- **`tests` value**, one of:
  - a one-line flow sequence on the key line: an opening bracket, zero or more comma-separated single-line scalars, a closing bracket, then an optional comment; `[]` is the empty list;
  - nothing on the key line except an optional comment, followed by one or more block sequence items, all at one indentation that is equal to or deeper than the `tests` key's indentation; each item is a dash, a space, one single-line scalar and an optional comment.
- **Scalars inside `tests`**: plain, single-quoted or double-quoted, each on one line. Inside single quotes, two consecutive single quotes stand for one; inside double quotes, backslash-quote and backslash-backslash are the only escapes.
- **Opaque values**: every top-level key other than `acceptance_tests`, and every field other than `tests`, is opaque. Its value is the rest of its key line plus every following line that is blank or indented deeper than that key. Opaque lines are never interpreted: lines starting with `tests:` or a dash inside them are never IDs. This covers block scalars (`|` and `>`, with or without indicators) such as a multi-line `red_reason`, and `baseline_failures` / `final_failures` in any form; none of them is ever extracted (FR4).
- **Errors**, each naming the record path and the AC key, or a record-level marker when no AC applies:
  - unsupported notation: any structural line outside the rules above, for example a tab in indentation, a `tests` item that is a mapping, a sequence, multi-line or empty, a flow sequence spanning lines, an inline value after `acceptance_tests:` or after an AC key, inconsistent indentation within one level, a second `acceptance_tests`, or a `tests` key with neither a value nor items;
  - duplicate AC key; duplicate `tests` key within one AC; missing `tests` key in an AC; missing `acceptance_tests`;
  - unreadable record: the file cannot be read or cannot be decoded as UTF-8 (FR8).
  An extraction failure is never treated as an empty list (FR8).

### SC-3: ID mapping record (FR3)

- **Location**: one file per cleanup task: `test-docs/tests-yaml-test-id-resolution/id-mapping-range1.md` (task0002), `test-docs/tests-yaml-test-id-resolution/id-mapping-range2.md` (task0003), `test-docs/tests-yaml-test-id-resolution/id-mapping-range3.md` (task0004). These names never end in `.tests.yaml`, so the record check does not read them.
- **Shape**: a level-1 heading naming the range, one sentence stating the SC-4 range rule, then exactly one Markdown table with the columns File, AC, Old ID, New ID, Basis, in that order. No other table.
- **Row unit**: one row per removed old-ID occurrence, meaning an element present in an AC's `tests` list at the base revision and absent from the same AC's list afterwards, counted as a multiset difference. Reordering produces no row.
- **Cells**: File is the repository-relative record path; AC is the AC key's value; Old ID is the removed element's scalar value exactly; New ID is the replacing canonical ID or IDs joined by comma and space (also when the replacement was already present in the AC), or the word `deleted`; Basis is one category token, a colon, a space and short evidence. A pipe character inside a cell is escaped with a backslash.
- **Basis categories**:
  - `normalized`: mechanical conversion (the `tests.` prefix added; a `path::Class::method` or file-path form converted to dot form);
  - `abbreviation`: expanded from its definition inside the same record (evidence: where it is defined);
  - `renamed`: rename or merge found in git history (evidence: the commit id);
  - `wildcard`: expanded to the existing IDs it identifies;
  - `runner-replaced`: FR2, a non-unittest element replaced by the existing unittest that verifies the same target (evidence: that test);
  - `non-unittest-removed`: FR2, removed with its text appended to the AC's `red_reason` per SC-5, or evidence `no red_reason` when the AC has none;
  - `no-counterpart`: FR3 step 4, no counterpart exists (evidence: what was searched).
- **Count invariant** (TS-3): the rows of the three files together equal the removed-occurrence count of the base-to-HEAD diff over every record outside `test-docs/tests-yaml-test-id-resolution/`.

### SC-4: Cleanup partition

- The partition key is the first path segment under `test-docs/` (normally the feature directory name), lowercased; ranges compare its first character by code point.
- range1 (task0002): first character at or before `d`, which includes digits, punctuation and `a` to `d`.
- range2 (task0003): first character `e` through `p`.
- range3 (task0004): first character after `p`, excluding `test-docs/tests-yaml-test-id-resolution/`.
- `test-docs/tests-yaml-test-id-resolution/` holds only this feature's own task records and the SC-3 files. No cleanup task edits a record there; each task writes only its own task record there.
- A cleanup task changes no record outside its range.

### SC-5: red_reason append convention (FR2)

- Applies only when the AC already has `red_reason`. A `red_reason` key is never added.
- Appended text: one English sentence starting with `Removed from tests (not a unittest ID): `, followed by the removed elements' text in their original order, joined by semicolon and space.
- The parsed pre-existing value stays the exact prefix of the parsed new value:
  - single-line quoted value: the sentence is added inside the same quotes on the same line after one space, escaped for that quote style;
  - single-line plain value: the line is rewritten as one double-quoted line holding the old value, one space and the sentence;
  - literal block scalar (`|`): one new body line after the existing body, at the body's indentation;
  - folded block scalar (`>`): one blank line, then one new body line at the body's indentation, so that the old final line break survives folding.
- Never applied to `test-docs/exit4-tip-argument/task0002.tests.yaml` (NFR3).

### SC-6: Test module names

- Record check: `tests/test_tests_yaml_id_resolution.py` (task0001).
- Document-contract test: `tests/test_tests_yaml_id_rules_docs.py` (task0005).
- `test/README.md` names the record check. `em-workflow/agents/implementer.md` names neither module, because FR10 keeps it independent of language and repository.

## Conventions

- Every task's own record (`test-docs/tests-yaml-test-id-resolution/{task}.tests.yaml`) follows SC-1 and SC-2. An AC that no committed test covers uses `tests: []`, with the explanation in `red_reason` (FR8, FR10).
- Scratch scripts used during a task live outside the repository and are never committed.
- Check failure messages are in English. Every error line names the file, the AC (or the record-level marker), the ID when one applies, and the reason.
- No task changes `tests/test_exit4_ac2_test_id_drift.py` (FR5, NFR3).
- No task renames, deletes or adds tests under `tests/` to make a record resolve; records are changed to match the tests.
- No task changes a plugin manifest or `.claude-plugin/marketplace.json` (NFR4).

## Cross-task Design Decisions

### D1: Three range-partitioned cleanup tasks

- **Decision**: task0002, task0003 and task0004 each own one SC-4 range and one SC-3 file.
- **Rationale**: about 1,035 failing IDs over about 133 files (A2) exceed one implementer session; disjoint ranges and separate mapping files leave no record or file shared between them.
- **Affected tasks**: task0002, task0003, task0004.

### D2: Real-repository failures in the record check's own worktree are expected

- **Decision**: task0001 is built and verified against fixtures. Its real-repository per-record tests fail in its own worktree for every record not yet cleaned, because the cleanup runs in parallel. task0001 lists those failures in its `final_failures`, edits no record, and does not relax SC-1 or SC-2 to make them pass. TS-1 is confirmed on the integrated branch in verify.
- **Affected tasks**: task0001, task0002, task0003, task0004.

### D3: Cleanup verification without the record check

- **Decision**: each cleanup task verifies its range with a scratch check outside the repository that implements SC-1 (including the at-least-one-test condition) and SC-2.
- **Rationale**: the record check is not present in the cleanup worktrees.
- **Affected tasks**: task0002, task0003, task0004.

### D4: Opaque values

- **Decision**: SC-2 treats every non-target value as opaque text bounded by indentation.
- **Rationale**: keeps FR4 (failure lists are never read) and FR7 (multi-line bodies are never read as IDs) structural, and keeps existing non-`tests` content readable without rewriting it (AC-4 forbids rewriting it).
- **Affected tasks**: task0001, task0002, task0003, task0004, task0005.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| A real record's structural lines outside `tests` fall outside SC-2, and the cleanup may not rewrite them | Low | Medium: TS-1 fails for that record | task0001 reports the record and the notation as a deviation instead of widening SC-2 silently; resolved by rework after review or verify |
| An ID passes a cleanup scratch check but fails the record check | Medium | Medium | both implement SC-1 as written; TS-1 and TS-2 run on the integrated branch |
| Fixture checks and real-repository checks see each other's `tests` package through the module cache | Medium | High: results depend on test order | task0001 sets aside and restores the module-cache entries of the `tests` package around fixture checks (task0001 AC-6) |
| Resolution imports test modules a second time under `tests.` names, running their import-time code twice | Low | Low | the same run already imports them; the record check limits its own import-time work to record enumeration |
| A run other than the project command from the repository root changes the module search path and the results | Low | Low | `test/README.md` states the invocation; verify uses the project command |
| Mapping rows disagree with the diff when several IDs merge into one | Medium | Medium | SC-3 counts removed occurrences, not added IDs; TS-3 |
| An FR2 removal hits an AC without `red_reason` | Medium | Low | SC-5 adds no key; the SC-3 row carries `no red_reason` and the removed text |

## Open Questions

- [ ] FR2 does not cover an AC that has no `red_reason`. This plan adds no key and keeps the removed text in the SC-3 row (SC-5).
- [ ] FR6 does not count a zero-test loader result as a failure, while the TS-2 reproduction procedure does. The record check follows FR6; the cleanup avoids zero-test IDs (SC-1).
