# Feature: exemption-registry-section-scope

## Overview

Only the table rows inside the `## Exemption registry` section of
`em-workflow/references/gate-option-vocabulary.md` can exempt a gate from the
gate-option correspondence sweep. The section extractor, row parser, row
validator and exemption loader move into one shared non-test helper under
`tests/`, used by both the doc-side tests and the correspondence sweep.
Requirements: `feature-docs/exemption-registry-section-scope/REQUIREMENTS.md`.

## Objectives

- Only rows in the `## Exemption registry` section exempt a gate from the correspondence sweep.
- A table anywhere else in the document never exempts a gate without a signal.

## User Stories

### US1: Section-scoped exemptions
As an em-workflow maintainer, I want the exemption loader to read only the
`## Exemption registry` section, so that a table elsewhere in the document
never exempts a gate.

**Acceptance Criteria:**
- [ ] AC-1: `load_exempt_gate_ids()` collects table rows only from the `## Exemption registry` heading up to the next `## ` heading, using the same shared extractor as the doc-side registry section.
- [ ] AC-4: A hermetic test shows that a synthetic document with an unrelated table plus a zero-row `## Exemption registry` gives `set()`.

### US2: Validated registry rows
As an em-workflow maintainer, I want invalid registry rows to raise, so that
an exemption always carries a select gate, a reason and a compensating
guarantee.

**Acceptance Criteria:**
- [ ] AC-2: Parsed exemption rows are checked the same way as `validate_exemption_rows` (3 cells, non-empty reason, non-empty compensating guarantee, gate_id in the `action: select` set). An invalid row raises an exception.

### US3: One shared implementation
As an em-workflow maintainer, I want the doc side and the consumer side to use
one helper, so that both sides use the same anchor and rules.

**Acceptance Criteria:**
- [ ] AC-3: The shared parser/validator exists in one non-test helper module under `tests/`, and both `tests/test_gate_option_vocabulary_doc.py` and `tests/test_gate_option_vocabulary.py` use it.
- [ ] AC-5: `python3 -m unittest discover -s tests` passes.

## Technical Requirements

### Functional Requirements
- **FR1: Section-scoped extraction** — A shared helper extracts the registry section. It starts at a line-anchored `## Exemption registry` heading and runs up to, but not including, the next line-start `## ` heading, or to EOF. A `### ` subheading does not end the section. Only pipe-table lines inside this section are collected.
- **FR2: Row parsing** — Inside the section, the header row and the separator row are skipped. Every data row must have exactly 3 cells, otherwise `ValueError` is raised. A section that is present but holds no table raises `ValueError`, which is the current behavior of the doc-side `parse_exemption_table_rows`.
- **FR3: Row validation** — Parsed rows get the same checks as `validate_exemption_rows`: gate_id is an `action: select` entry of `batch-policies.yaml`, reason is non-empty, and compensating guarantee is non-empty. `validate_exemption_rows` keeps returning a list of violation strings that contain the existing substrings `missing a reason`, `missing a compensating guarantee` and ``not an `action: select` entry``. The consumer-side loader raises `ValueError` naming the violations when that list is non-empty.
- **FR4: Single shared helper** — The section extractor, row parser, row validator and exemption loader live in exactly one non-test module under `tests/`, for example `tests/_gate_vocabulary.py`. Its name does not match `test*.py`, so `unittest discover` does not collect it. `tests/test_gate_option_vocabulary_doc.py` and `tests/test_gate_option_vocabulary.py` both import from it, and their local duplicates are removed. The doc-side `_registry_section` uses the shared extractor, so both sides use the same anchor.
- **FR5: `load_exempt_gate_ids` behavior** — If the registry file is absent, the result is `set()`; this keeps the existing D3 degrade. If the file is present, the loader does the section-scoped parse (FR1/FR2), then validation (FR3), then returns the set of gate_ids from the registry rows. The loader takes the `action: select` gate-id set as input, and the real call site passes the set derived from `batch-policies.yaml`.
- **FR6: Hermetic regression tests** — Synthetic-document tests are added. (a) An unrelated table whose first cell names a real select gate, such as a `## Gate option vocabulary` example row for `create-spec.feature-identity`, plus a zero-row `## Exemption registry` gives `set()`. (b) An unrelated table after the registry section is not counted. (c) A registry row that is missing its reason, missing its guarantee, names a non-select gate, or has the wrong cell count raises `ValueError`. (d) A valid row that names a select gate gives that gate_id. (e) An absent file gives `set()`.
- **FR7: Existing hermetic tests updated** — The two existing `TestExemptionRegistryDegrade` fixtures use a level-1 `# Exemption registry` heading and the non-select gate `some.gate`, so they are rewritten to the `## Exemption registry` level-2 heading and a real select gate id. `test_present_file_parses_listed_gate_ids` would otherwise return `set()` or raise under FR1/FR3.
- **FR8: Real repository unchanged in outcome** — The real `gate-option-vocabulary.md` (present, zero registry rows) still gives `set()`. The correspondence sweep still covers all eleven select gates. `em-workflow/references/gate-option-vocabulary.md` is not edited.

### Non-Functional Requirements
- **NFR1 - Standard library only:** Test code imports only the Python standard library (`test/README.md`).
- **NFR2 - No em-workflow change:** No file under `em-workflow/` changes, so neither `em-workflow/.claude-plugin/plugin.json` nor `.claude-plugin/marketplace.json` is bumped. Both stay at 0.2.1.
- **NFR3 - ISSUING_SITE_MAP location:** The `ISSUING_SITE_MAP` stays in `tests/test_gate_option_vocabulary.py`. `gate-option-vocabulary.md` cites the map as living in the ``correspondence-check module under `tests/` ``, and `test_gate_option_vocabulary_doc.py:485` pins that wording.
- **NFR4 - Frozen digest pins unaffected:** `TestFrozenMachineReadSurface` digest pins are unaffected (`workflow-patch.md`, `validate-worker-output.py`, `test_validate_worker_output.py`, the design-step fixture). None of those files is touched.
- **NFR5 - No test-to-test imports:** No test module imports another test module. Importing the non-test helper keeps the existing convention stated in the `test_gate_option_vocabulary.py` docstring.

## Implementation Approach

### Architecture

**Component Diagram:**
```
tests/_gate_vocabulary.py  (non-test helper; name does not match test*.py)
  ├── section extractor   (FR1)
  ├── row parser          (FR2)
  ├── row validator       (FR3; validate_exemption_rows)
  └── exemption loader    (FR5; load_exempt_gate_ids)
        ▲                          ▲
        │ import                   │ import
tests/test_gate_option_vocabulary_doc.py   tests/test_gate_option_vocabulary.py
  (_registry_section uses the              (correspondence sweep;
   shared extractor)                        ISSUING_SITE_MAP stays here)
```

### Data Flow

```
gate-option-vocabulary.md
  → absent? ─ yes → set()
  → section extractor (## Exemption registry .. next "## " heading or EOF)
  → row parser (skip header/separator; 3 cells per row; no table → ValueError)
  → row validator (select gate, non-empty reason, non-empty guarantee)
  → violations? ─ yes → ValueError naming the violations
  → set of registry gate_ids → correspondence sweep
```

The loader receives the `action: select` gate-id set as a parameter; the
real call site passes the set derived from `batch-policies.yaml`.

### API Design

Not applicable (no network API). The helper's callable surface is the section
extractor, row parser, `validate_exemption_rows` and `load_exempt_gate_ids`
(FR1–FR5).

### Database Schema

Not applicable.

### Dependencies

**Internal Dependencies:**
- `em-workflow/references/gate-option-vocabulary.md`: read-only input; not edited (FR8).
- `batch-policies.yaml`: source of the `action: select` gate-id set passed to the loader (FR5).

**External Dependencies:**
- None. Python standard library only (NFR1).

### File Structure

```
tests/
├── _gate_vocabulary.py                  # shared helper (example name, FR4)
├── test_gate_option_vocabulary.py       # imports the helper; local duplicates removed
└── test_gate_option_vocabulary_doc.py   # imports the helper; local duplicates removed
```

### Assumptions

- A-1: The section end is the next line-start `## ` heading or EOF, not the fixed `## Scope` marker that the doc-side `_registry_section` uses today. The two are equal for the current document, because `## Scope` is the next level-2 heading. The ticket's DoD states both "next `## ` heading" and "same anchor as `_registry_section`", and switching the doc side to the shared extractor satisfies both.
- A-2: The heading match is line-anchored (`^## Exemption registry\s*$`), not a substring find. A substring find would also match `### Exemption registry` or prose. The first occurrence is used.
- A-3: A present registry file with no `## Exemption registry` section gives `set()`, which is fail-safe because every gate stays checked. An unreadable present file (`OSError`) also gives `set()`, as it does today. A present section that holds no table raises `ValueError`, as the doc side does today.
- A-4: gate_id extraction from the first cell follows the doc-side rule (strip backticks), so the existing doc-side tests keep their behavior. The loader receives the select gate-id set as a parameter rather than reading `batch-policies.yaml` itself.
- A-5: The stale wording in `tests/test_gate_option_vocabulary.py` is updated to say the registry is present with zero rows, and the `== set()` assertion is kept. This covers the module docstring lines 40-43 ("degrading to zero exemptions when the file is absent -- which it is"), the `load_exempt_gate_ids` docstring, and the name and comment of `test_real_repository_registry_is_absent_in_this_worktree`.
- A-6: `import _gate_vocabulary` resolves under `python3 -m unittest discover -s tests` (`tests/` is inserted into `sys.path` as the top-level dir) and under direct `python3 tests/<module>.py` execution. The implementer must confirm that the helper import also works for any other invocation the project uses.
- A-7: Fenced code blocks inside `gate-option-vocabulary.md` are not specially handled. A line starting `## ` inside a fence would still end a section.

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/exemption-registry-section-scope/**`
- `test-docs/exemption-registry-section-scope/**`

`feature-docs/exemption-registry-section-scope/**` covers `REQUIREMENTS.md`,
`SPEC.md`, `IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/exemption-registry-section-scope/**` covers
`test-docs/exemption-registry-section-scope/{T}.tests.yaml`, the per-task
test record. It is generated and owned by `implement-phase.md`; this section
cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/exemption-registry-section-scope/` directory at all; the declared
`test-docs/exemption-registry-section-scope/**` entry is still correct in
that case — a declared path that never materializes is not a violation.

## Test Scenarios

### Unit Tests
- [ ] TS-1 (FR1, FR5, FR6): An unrelated `## Gate option vocabulary`-style table naming `create-spec.feature-identity` placed before a zero-row `## Exemption registry` gives `set()`. This is the ticket's reproduction.
- [ ] TS-2 (FR1, FR5): A table placed in a section after `## Exemption registry` (e.g. `## Scope`) is not read as an exemption.
- [ ] TS-3 (FR1, FR5): A `### ` subheading inside the registry section does not end it.
- [ ] TS-4 (FR2, FR3): Registry rows that are missing a reason, missing a guarantee, name a non-select gate, or have the wrong cell count each make the loader raise `ValueError`.
- [ ] TS-5 (FR2, FR3): A valid registry row naming a select gate gives `{that gate_id}`.

### Integration Tests
- [ ] TS-6 (FR4): Both test modules resolve the extractor/parser/validator from the shared helper, and no local duplicate remains. Checked by the updated modules importing from the helper.
- [ ] TS-7 (FR7, FR8): Absent file gives `set()`. The real repository registry gives `set()`. The existing doc-side AC-3/AC-4 tests and the correspondence sweep stay green in a full `discover` run.

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases
- [ ] A `### ` subheading inside the registry section does not end it (TS-3).
- [ ] A present section with no table raises `ValueError` (FR2).
- [ ] An absent registry file gives `set()` (FR5, TS-7).

### Performance Tests
Not applicable.

## Security Considerations

Not applicable. The change is confined to test code and a test helper under
`tests/`.

## Error Handling

### Error Codes

| Code | Description | Raised by |
|------|-------------|-----------|
| `ValueError` | A data row in the registry section does not have exactly 3 cells | Row parser (FR2) |
| `ValueError` | The registry section is present but holds no table | Row parser (FR2) |
| `ValueError` | `validate_exemption_rows` returned a non-empty violation list; the message names the violations | Exemption loader (FR3) |

### Error Flow

```
Invalid row / empty section → ValueError → test run fails
```

## Performance Optimization

Not applicable.

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] `python3 -m unittest discover -s tests` passes (AC-5)
- [ ] Code review is completed

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

None.

## References

- Requirements: `feature-docs/exemption-registry-section-scope/REQUIREMENTS.md`
- Registry document: `em-workflow/references/gate-option-vocabulary.md`
- Test code rules: `test/README.md`
