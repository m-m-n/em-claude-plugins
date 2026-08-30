# Feature: declared-change-set-implementation

## Overview

The Declared Change Set section of both document templates enumerates the members of `feature-docs/{feature}/**`, but omits `IMPLEMENTATION.md`, the mandatory create-plan artifact. This feature adds `IMPLEMENTATION.md` to that enumeration in both templates and to the matching `FEATURE_DOCS_MEMBERS` literal set in the two tests, and bumps the plugin version. Requirement details are in `feature-docs/declared-change-set-implementation/REQUIREMENTS.md`.

## Objectives

- Align the enumerated members of `feature-docs/{feature}/**` with reality, so a SPEC author who narrows the declaration to an explicit enumeration does not drop `IMPLEMENTATION.md` (BO-1).
- Remove the drift between the owning SSOTs (`create-plan-phase.md` / `phase-state.md`) and the template-side enumeration, so both templates and the corresponding tests carry a single literal set (BO-2).

## User Stories

### US1: A SPEC author narrows the declaration to an explicit enumeration
As a SPEC author, I want the template's enumeration of `feature-docs/{feature}/**` to list every member, so that narrowing the declaration to an explicit enumeration does not silently drop `IMPLEMENTATION.md`.

**Acceptance Criteria:**
- [ ] AC1: `em-workflow/references/templates/spec-document.md`'s `## Declared Change Set` section enumerates `IMPLEMENTATION.md`. (verifies FR1)
- [ ] AC2: `em-workflow/references/templates/requirements-document.md`'s `### 9.4 宣言された変更集合` enumerates `IMPLEMENTATION.md`. (verifies FR2)

### US2: The enumeration stays consistent with its tests
As a maintainer, I want the tests to assert the same literal set the templates carry, so that template and test do not drift apart again.

**Acceptance Criteria:**
- [ ] AC3: `tests/test_spec_template_declared_change_set.py` and `tests/test_requirements_template_declared_change_set.py` carry the same literal in `FEATURE_DOCS_MEMBERS`. (verifies FR3)
- [ ] AC4: `python3 -m unittest discover -s tests` passes at the repository root. (verifies FR1, FR2, FR3, NFR2, NFR3)
- [ ] AC5: `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` carry the same bumped version within the same change. (verifies FR4)

## Technical Requirements

### Functional Requirements

- **FR1 — SPEC template enumeration gains IMPLEMENTATION.md:** `em-workflow/references/templates/spec-document.md`'s `## Declared Change Set` section must include `IMPLEMENTATION.md` among the members it enumerates for `feature-docs/{feature}/**`.
- **FR2 — REQUIREMENTS template enumeration gains IMPLEMENTATION.md:** `em-workflow/references/templates/requirements-document.md`'s `### 9.4 宣言された変更集合` must include `IMPLEMENTATION.md` among the members it enumerates for `feature-docs/{feature}/**`.
- **FR3 — Tests carry the same literal in FEATURE_DOCS_MEMBERS:** `tests/test_spec_template_declared_change_set.py` and `tests/test_requirements_template_declared_change_set.py` must include, in `FEATURE_DOCS_MEMBERS`, the same `IMPLEMENTATION.md` literal added by FR1 / FR2.
- **FR4 — Plugin version bump:** because files under the plugin (`em-workflow/references/templates/`) change, `em-workflow/.claude-plugin/plugin.json` and the corresponding entry in `.claude-plugin/marketplace.json` must be bumped to the same value within the same change. The increment is patch, matching a behavioral fix.

### Non-Functional Requirements

- **NFR1 - Enumeration style consistency:** the notation and placement of the added member must match the existing members of each section (`REQUIREMENTS.md` / `SPEC.md` / `workflow.yaml` / `phase-state/` / `tasks/` / `reviews/roundN.yaml` / `VERIFICATION.md` / `retrospect.yaml` / design artifacts). The name used must match the naming in the owning SSOTs, `em-workflow/references/phases/create-plan-phase.md` and `em-workflow/references/phase-state.md`.
- **NFR2 - No third-party test dependencies:** test changes depend only on the Python standard library `unittest` (per `test/README.md`: test code imports no third-party package).
- **NFR3 - Negative-proof samples unchanged:** the `PRE_CHANGE` samples inside the tests do not contain the literal and must not be modified, so the negative proof (detection fails against the pre-change state) is preserved.
- **NFR4 - Bounded change scope:** the change is limited to the two templates, the two test files, and the two version declarations. Adding the enumeration to feature-specific documents (e.g. `design-input.md`) is out of scope.

## Implementation Approach

### Architecture

No runtime architecture is involved. The change touches Markdown templates, Python test literals, and version metadata only.

**Component Diagram:**
```
em-workflow/references/phases/create-plan-phase.md  ─┐  (owning SSOT for member naming)
em-workflow/references/phase-state.md               ─┘
                     │
                     ▼
em-workflow/references/templates/spec-document.md          (FR1)
em-workflow/references/templates/requirements-document.md  (FR2)
                     │
                     ▼
tests/test_spec_template_declared_change_set.py            (FR3)
tests/test_requirements_template_declared_change_set.py    (FR3)
```

### Data Flow

Not applicable — no runtime data flow.

### API Design

Not applicable — no API surface.

### Database Schema

Not applicable — no persistent data.

### Dependencies

**Internal Dependencies:**
- `em-workflow/references/phases/create-plan-phase.md`: owning SSOT for the member naming required by NFR1.
- `em-workflow/references/phase-state.md`: owning SSOT for the member naming required by NFR1.
- PR #9 (`feature: spec-file-set-completeness`): supplies the target sections and the two test files (AS-1).

**External Dependencies:**
- Python standard library `unittest` only (NFR2).

### File Structure

```
.
├── .claude-plugin/
│   └── marketplace.json                                  # version bump (FR4)
├── em-workflow/
│   ├── .claude-plugin/
│   │   └── plugin.json                                   # version bump (FR4)
│   └── references/templates/
│       ├── spec-document.md                              # FR1
│       └── requirements-document.md                      # FR2
└── tests/
    ├── test_spec_template_declared_change_set.py         # FR3
    └── test_requirements_template_declared_change_set.py # FR3
```

## Declared Change Set

Feature-specific paths this feature creates or modifies:

- `em-workflow/references/templates/spec-document.md`
- `em-workflow/references/templates/requirements-document.md`
- `tests/test_spec_template_declared_change_set.py`
- `tests/test_requirements_template_declared_change_set.py`
- `em-workflow/.claude-plugin/plugin.json`
- `.claude-plugin/marketplace.json`

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/{feature}/**`
- `test-docs/{feature}/**`

`feature-docs/{feature}/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/{feature}/**` covers `test-docs/{feature}/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/{feature}/` directory at all; the declared
`test-docs/{feature}/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests
- [ ] TS1 (FR1, FR3): `test_spec_template_declared_change_set.py` asserts that every member of `FEATURE_DOCS_MEMBERS` — including `IMPLEMENTATION.md` — appears in `spec-document.md`'s Declared Change Set section. Command: `python3 -m unittest discover -s tests`
- [ ] TS2 (FR2, FR3): `test_requirements_template_declared_change_set.py` performs the same assertion against section 9.4 of `requirements-document.md`. Command: `python3 -m unittest discover -s tests`

### Integration Tests
- [ ] TS4 (FR1, FR2, FR3, NFR2, NFR3): the whole suite passes without regression. Command: `python3 -m unittest discover -s tests`

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases
- [ ] TS3 (NFR3): the negative proof against the `PRE_CHANGE` samples keeps detecting failure for input that does not contain `IMPLEMENTATION.md`. Command: `python3 -m unittest discover -s tests`

### Performance Tests
Not applicable.

## Security Considerations

Not applicable — the change touches documentation templates, test literals, and version metadata only.

## Error Handling

Not applicable — no runtime error surface.

## Performance Optimization

Not applicable.

## Success Criteria

- [ ] All functional requirements (FR1–FR4) are implemented.
- [ ] All test scenarios (TS1–TS4) pass.
- [ ] `python3 -m unittest discover -s tests` passes at the repository root (AC4).
- [ ] The change scope stays within the two templates, two test files, and two version declarations (NFR4).
- [ ] Code review is completed.

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

None — every requirement is `resolved`.

## Assumptions

- **AS-1**: PR #9 (`feature: spec-file-set-completeness`) is merged, so both templates carry the target sections and the two test files exist. If it is not merged, this feature cannot be started.
- **AS-2**: because the root declaration is a `**` glob, containment itself is not broken; this feature corrects the completeness of the enumeration, not the validity of the declaration.
- **AS-3**: the current content of the target templates and tests was not read during analysis; the requirements were derived from the acceptance conditions the task description stated explicitly.
- **AS-4**: the version bump increment is patch (a behavioral fix). The current version value is determined at implementation time.

## Implementation Phases (if applicable)

Not applicable — single-phase change.

## References

- Requirements document: `feature-docs/declared-change-set-implementation/REQUIREMENTS.md`
- Member-naming SSOT: `em-workflow/references/phases/create-plan-phase.md`
- Member-naming SSOT: `em-workflow/references/phase-state.md`
- Test convention (no third-party imports): `test/README.md`
