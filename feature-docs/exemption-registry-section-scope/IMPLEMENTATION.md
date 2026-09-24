# Implementation Plan: exemption-registry-section-scope

## Overview

Only the table rows of the `## Exemption registry` section of
`em-workflow/references/gate-option-vocabulary.md` may exempt a gate from the
gate-option correspondence sweep. The section extractor, row parser, row
validator and exemption loader move into one non-test helper module under
`tests/`, and both gate-vocabulary test modules consume it.

## Technology Stack

- **Language**: Python 3, standard library only (NFR1).
- **Test framework**: `unittest` (standard library), run as
  `python3 -m unittest discover -s tests` (workflow.yaml
  `project.components.main.test_command`).
- **New dependencies**: none. `project.license` is `none`; no license line
  to record.

## Layer Structure

| Layer | Members | Responsibility |
|-------|---------|----------------|
| Input documents (read-only) | `em-workflow/references/gate-option-vocabulary.md`, `em-workflow/references/batch-policies.yaml` | Source of the registry rows and of the `action: select` gate-id set. Never edited by this feature (FR8, NFR2). |
| Shared helper | `tests/_gate_vocabulary.py` | Registry section extraction, row parsing, row validation, exemption loading. Holds no test cases. |
| Test modules | `tests/test_gate_option_vocabulary_doc.py` (doc side), `tests/test_gate_option_vocabulary.py` (consumer side, correspondence sweep) | Assertions about the document and about the correspondence decision. |

Allowed dependency directions:

1. Test module → shared helper: allowed (import by the helper's top-level
   module name).
2. Shared helper → any test module: forbidden.
3. Test module → another test module: forbidden (NFR5).
4. Shared helper → standard library only (NFR1).

## Shared Components

The helper's four callables are the contract between the helper and both
test modules, and any later rework task builds against the same contract.

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| Section extractor — `extract_exemption_registry_section(text)` | Isolate the registry section of a registry document (FR1) | Pre: `text` is the full document text. Post: returns the section body — the text after the FIRST line that consists exactly of the heading `## Exemption registry` (trailing whitespace allowed), up to but not including the next line that begins with `## `, or to end of text. A line beginning with `### ` does not end the section. A `### Exemption registry` line, or `## Exemption registry` appearing anywhere other than at the start of its own line, is not a section start. Returns a no-section result (null) when no qualifying heading line exists. Does not raise for string input. | task0001 (doc side and consumer side) |
| Row parser — `parse_exemption_table_rows(section_text)` | Turn the section's pipe table into rows (FR2) | Pre: `section_text` is a non-null extractor result. Post: a pipe-table line is a line whose content, after surrounding whitespace is removed, begins with a pipe character. The first two pipe-table lines (header row, separator row) are skipped. Returns a list with one 3-tuple of whitespace-stripped cell texts per remaining line, in document order. Raises `ValueError` when the section holds no pipe-table line at all, and when a data line does not split into exactly 3 cells (the message quotes the offending line). | task0001 (doc side and consumer side) |
| Row validator — `validate_exemption_rows(rows, select_ids)` | Check parsed rows (FR3) | Pre: `rows` is a parser result; `select_ids` is a set of gate-id strings. Post: returns a list of violation strings, empty when every row is valid. For each row: the gate_id (see gate_id derivation below) not in `select_ids` yields a violation containing ``not an `action: select` entry``; an empty reason cell yields one containing `missing a reason`; an empty compensating-guarantee cell yields one containing `missing a compensating guarantee`. Does not raise. | task0001 (doc side and consumer side) |
| Exemption loader — `load_exempt_gate_ids(registry_path, select_ids)` | Produce the exempt gate-id set for the correspondence sweep (FR5) | Pre: `registry_path` is a filesystem path; `select_ids` is REQUIRED (no default) and is the `action: select` gate-id set. Post, in order: (1) path is not a regular file → empty set; (2) reading fails with an OS-level error → empty set; (3) extractor returns no-section → empty set; (4) otherwise the parser runs and its `ValueError` propagates unchanged; (5) the validator runs and, when it returns any violation, the loader raises `ValueError` whose message contains every violation string; (6) otherwise returns the set of gate_ids of the parsed rows. | task0001 (consumer side) |

**gate_id derivation (shared rule)**: a row's gate_id is its first cell with
every leading and trailing backtick character removed, then leading and
trailing whitespace removed. The validator and the loader use this one rule,
so a gate_id the validator accepted is exactly the gate_id the loader
returns.

## Conventions

- **Error-handling policy — loud failure, fail-safe degrade.** A malformed
  registry row, a registry section without a table, or an invalid exemption
  raises `ValueError`, and nothing in the helper or in either test module
  catches and suppresses it. Exactly three conditions degrade to zero
  exemptions: absent file, unreadable file, absent section. All three are
  fail-safe, because zero exemptions means every select gate stays checked.
- **Helper naming.** The helper's file name begins with an underscore and
  does not match `test*.py`, so `unittest discover` never collects it as a
  test module. It defines no `TestCase` subclass.
- **Import resolution.** Test modules import the helper by its top-level
  module name. Both the canonical discover invocation (which puts `tests/`
  on the module search path) and direct execution of a test module as a
  script (whose own directory is on the search path) must resolve it.
- **Read-only inputs.** No file under `em-workflow/` changes, so no plugin
  version bump applies: `em-workflow/.claude-plugin/plugin.json` and
  `.claude-plugin/marketplace.json` stay at 0.2.1 (NFR2).
- **Pinned data stays where it is.** `ISSUING_SITE_MAP` stays in
  `tests/test_gate_option_vocabulary.py` (NFR3), and the
  `TestFrozenMachineReadSurface` digest constants are not edited (NFR4).

## Cross-task Design Decisions

### D1: One task for the helper and both consumers

The helper and its two consumer modules form one change. Tasks run fully in
parallel, each in its own worktree, so a consumer-side task could not run its
tests without the helper already present in its own worktree; a split would
force two tasks to create the same helper file. The feature is therefore one
task (task0001). Any later rework task reads this document for the contract
above.

### D2: Section boundaries

The section starts at the first line-anchored `## Exemption registry`
heading and ends at the next line-start `## ` heading or end of text
(SPEC A-1, A-2). The doc side's registry-section lookup and the consumer
side's loader both go through the one extractor, so both sides use the same
anchor. For the current document the result equals the old
`## Exemption registry` … `## Scope` slice, because `## Scope` is the next
level-2 heading. Fenced code blocks are not treated specially (SPEC A-7).

### D3: The select gate-id set is a loader parameter

The loader does not read `batch-policies.yaml` itself (SPEC A-4). The real
call site in the correspondence sweep passes the set derived from the policy
the consumer module has already parsed. Hermetic tests pass an explicit set.

### D4: Out-of-scope neighbours stay untouched

The `## Gate option vocabulary` block parser in the consumer module, the two
duplicated restricted-subset `gate_policies:` parsers, and the doc side's
generic section slicer used for other sections are not part of the shared
surface and are not changed beyond what the import switch requires.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| The stricter loader raises on the real document and turns the suite red | Low | High | The real registry holds a header row and a separator row with zero data rows, which parses to zero rows and validates clean; the real-repository test asserts an empty set. |
| The helper import fails under some invocation | Low | Medium | Discover and direct script execution both put `tests/` on the search path; the task checks both (SPEC A-6). |
| A hermetic regression fixture is vacuous (the unrelated table never sat outside the registry section) | Medium | Medium | The regression tests assert a non-vacuity precondition on their own fixture (see task0001 Test Notes). |
| Docstring edits break a wording pin | Low | Low | Only test-module docstrings change; the wording pins read `gate-option-vocabulary.md`, which is not edited. |

## Open Questions

- None.
