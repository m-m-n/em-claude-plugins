# Feature: resume-conditions-newline-rejection

## Overview

`em-workflow/references/batch-terminal-line.md` contradicts itself: `## Field values` says `resume_conditions`'s CR / LF / TAB survive as `## Escaping`'s escapes, while the first bullet under the `## Consumer constraints` OWN-rules label rejects a decoded line terminator in both `detail` and `resume_conditions`. This feature splits that shared bullet into per-field rules, so a `state: stopped` result carrying a multi-line recovery procedure — the normal form of a stop result — has a legal representation. The change is documentation-and-test only, plus the plugin version bump the repository's rules require.

Requirements source: `feature-docs/resume-conditions-newline-rejection/REQUIREMENTS.md`.

## Objectives

- Remove the self-contradiction in the batch structured-result SSOT so that the normal form of a stop result (a `state: stopped` result carrying a multi-line recovery procedure) has a legal representation.
- Keep the SSOT's own hardening rules enforceable: an implementation must be able to decide, from the document alone, which decoded code points are rejected per field.

## User Stories

### US1: Decide the rejected code points per field from the document alone

As an implementer reading the SSOT, I want each field's rejection rule stated separately, so that I can decide from the document alone which decoded code points are rejected for `detail` and for `resume_conditions`.

**Acceptance Criteria:**
- [ ] AC1: Reading `## Field values`'s `resume_conditions` bullet and the first OWN-rules bullet in `## Consumer constraints` in sequence yields no contradiction: a `resume_conditions` value carrying Markdown newlines is a legal, normal-form value.
- [ ] AC2: The OWN-rules section states that `resume_conditions` rejects only terminal-control code points other than CR, LF and TAB after decoding.
- [ ] AC3: The OWN-rules section still states, for `detail`, rejection of a line terminator or a terminal-control code point after decoding.
- [ ] AC4: The "Each of the four cannot fire while `## Escaping` is honoured" sentence no longer states a claim contradicted by the rule set below it.

### US2: Represent a stop result whose recovery procedure spans several lines

As the emitter of a stop result, I want a multi-line recovery procedure carried in full inside `resume_conditions` to be legal, so that the normal form of a `state: stopped` result has a representation the SSOT permits.

**Acceptance Criteria:**
- [ ] AC1: A `resume_conditions` value carrying Markdown newlines is a legal, normal-form value.
- [ ] AC7: A new positive test fails against the pre-change document text and passes against the post-change text.
- [ ] AC8: `TestEscapingAndResultFormatByteIdentical` and `test_five_carried_over_constraints_still_present_and_still_five` pass unmodified.

## Technical Requirements

### Functional Requirements

- **FR1:** Split the shared own-rule bullet into a per-field rule. In `em-workflow/references/batch-terminal-line.md`'s `## Consumer constraints`, under the label "em-workflow's OWN emitter obligations and rejection rules", the first bullet is replaced by per-field rules: `detail` rejects a line terminator or a terminal-control code point after decoding (unchanged in substance); `resume_conditions` rejects only terminal-control code points other than CR (U+000D), LF (U+000A) and TAB (U+0009) after decoding.
- **FR2:** State the newline exemption explicitly. The `resume_conditions` rule states explicitly that a decoded CR, LF or TAB inside `resume_conditions` is NOT a violation, because `## Field values` defines those as surviving as `## Escaping`'s escapes rather than being collapsed.
- **FR3:** Preserve `detail`'s rationale. The `detail` rule states its reason: `## Field values` already replaces every CR, LF and TAB in `detail` with a space before escaping, so a surviving one means the normalization was skipped, and rejection is therefore correct.
- **FR4:** Rewrite the "cannot fire" sentence. The sentence "Each of the four cannot fire while `## Escaping` is honoured: they are defense in depth for the case an unescaped newline inside a value is followed by a line that looks like another key." is rewritten so it matches the post-FR1 rule set: the blanket "cannot fire" claim is dropped and the block is introduced simply as em-workflow's own hardening rules, with no count word that goes stale and no claim contradicted by the rules below it.
- **FR5:** Do not disturb the pinned sections. `## Result format` and `## Escaping` stay byte-identical, and the five numbered carried-over consumer constraints stay exactly five and unchanged; the new wording is expressed as bullets under the OWN-rules label.
- **FR6:** Preserve the `## Field values` pinned literals. If the `resume_conditions` bullet in `## Field values` is touched at all, it keeps the literals existing tests pin: "NOT put through `detail`'s normalization", "survive as", "non-whitespace whenever `state` is `stopped`", "never empty and never whitespace-only", "empty for every other `state`", and "carried in full inside `resume_conditions`".
- **FR7:** Update the conformance matcher. `tests/test_batch_stop_contract.py`'s `_assert_own_hardening_rules_stated` expected strings are updated to the new wording, while keeping its existing guarantees: it stays anchored on OWN_RULES_LABEL, still asserts the three shape defenses, and still asserts the "carried-over consumer behaviour" labelling.
- **FR8:** Update the negative-proof sample. `FORGED_OWN_RULES_PARTIAL` is updated so it remains a well-formed-but-partial sample under the new wording: `TestOwnHardeningRulesMatcherNegativeProof.test_forged_partial_rules_is_otherwise_well_formed` still passes and `test_forged_partial_rules_missing_shape_checks_is_rejected` still fails for the missing shape checks, not for the changed control-code-point wording.
- **FR9:** Add a positive case for the newline exemption. A new positive test asserts that the document states a newline-carrying `resume_conditions` is not rejected, backed by a negative proof whose forged sample is the current pre-change wording ("`detail` and `resume_conditions` each reject a line terminator ... after decoding, in the same form as constraints 3 and 4 above") so the new matcher provably rejects the contradictory form.
- **FR10:** Plugin version bump. `em-workflow/.claude-plugin/plugin.json` and the em-workflow entry of `.claude-plugin/marketplace.json` are bumped to the same new patch version in the same change, per `.claude/rules/core-plugin-version-bump.md`.

### Non-Functional Requirements

- **NFR1 - Dependency constraint:** Tests use only the Python standard library `unittest` (no third-party imports), per test/README.md.
- **NFR2 - Maintainability:** New assertions read raw document text (`Path.read_text`) and go through the module's existing `_normalize` / `_sections` helpers, so a literal inside a fenced block is still seen and prose-wrap position does not matter.
- **NFR3 - Test rigour:** Every new matcher carries a negative proof plus a non-vacuity guard, matching the module's stated authoring convention.
- **NFR4 - Scope containment:** The change is documentation-and-test only: no runtime script, hook, or skill behaviour changes, and the document stays in English matching its surrounding prose.
- **NFR5 - Internal consistency:** The document remains internally consistent: after the change, no statement in `## Field values`, `## Escaping`, `## Result format` or `## Consumer constraints` contradicts another for any of the eight values.

## Implementation Approach

### Architecture

**System Architecture:** Not applicable. The change touches a prose SSOT document, a text-conformance test module, and two version manifests; it introduces no runtime layer.

**Component Diagram:**

```
em-workflow/references/batch-terminal-line.md   (prose SSOT: the rules)
        ^
        | read as text and asserted on
        |
tests/test_batch_stop_contract.py               (conformance matchers + negative proofs)

em-workflow/.claude-plugin/plugin.json  ==  .claude-plugin/marketplace.json (em-workflow entry)
        (same version value, bumped in the same change)
```

### Data Flow

```
tests/test_batch_stop_contract.py
  → Path.read_text(batch-terminal-line.md)
  → _normalize / _sections
  → matcher assertions (OWN_RULES_LABEL-anchored)
  → pass / fail
```

### API Design

Not applicable. This feature defines no endpoint and changes no interface.

### Database Schema

Not applicable. This feature has no persistent data and no entity relationships, so no table definition and no ER diagram apply.

### Dependencies

**Internal Dependencies:**
- `em-workflow/references/batch-terminal-line.md`: the document whose `## Consumer constraints` wording changes (FR1-FR4) and whose `## Result format`, `## Escaping` and `## Field values` pins must hold (FR5, FR6).
- `tests/test_batch_stop_contract.py`: the conformance module whose matcher, forged sample and new positive case change (FR7-FR9), and whose `_normalize` / `_sections` helpers the new assertions reuse (NFR2).
- `.claude/rules/core-plugin-version-bump.md`: the rule that requires FR10's paired version bump.
- `em-workflow/references/batch-mode.md` and `em-workflow/skills/develop/SKILL.md`: read-only; assumption A7 records that neither needs an edit.

**External Dependencies:**
- Python standard library `unittest` only; no third-party package (NFR1).

### File Structure

```
em-workflow/
├── references/
│   └── batch-terminal-line.md          # FR1-FR6: OWN-rules wording, pinned sections
└── .claude-plugin/
    └── plugin.json                     # FR10: em-workflow version
tests/
└── test_batch_stop_contract.py         # FR7-FR9: matcher, forged sample, new positive case
.claude-plugin/
└── marketplace.json                    # FR10: em-workflow entry version
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/resume-conditions-newline-rejection/**`
- `test-docs/resume-conditions-newline-rejection/**`

`feature-docs/resume-conditions-newline-rejection/**` covers
`REQUIREMENTS.md`, `SPEC.md`, `IMPLEMENTATION.md`, `workflow.yaml`,
`phase-state/`, `tasks/`, `reviews/roundN.yaml`, `VERIFICATION.md`,
`retrospect.yaml`, and the design artifacts the design step produces. These
are generated and owned by the phase documents and by
`references/phase-state.md`; this section cites them and restates none of
their rules.

`test-docs/resume-conditions-newline-rejection/**` covers
`test-docs/resume-conditions-newline-rejection/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/resume-conditions-newline-rejection/` directory at all; the
declared `test-docs/resume-conditions-newline-rejection/**` entry is still
correct in that case — a declared path that never materializes is not a
violation.

## Test Scenarios

### Unit Tests
- [ ] TS1 (FR1, FR2, FR9): Positive — the OWN-rules text of `## Consumer constraints` states the CR/LF/TAB exemption for `resume_conditions` (new matcher, asserted against the real document).
- [ ] TS2 (FR9, NFR3): Negative proof for TS1 — the pre-change bullet text, used verbatim as a forged sample, is rejected by TS1's matcher.
- [ ] TS3 (FR9, NFR3): Non-vacuity for TS1 — the carried-over numbered constraints alone do not satisfy TS1's matcher (it stays anchored on OWN_RULES_LABEL).
- [ ] TS4 (FR3, FR7): Regression — `_assert_own_hardening_rules_stated` passes against the updated document and still requires all three shape defenses and the "carried-over consumer behaviour" labelling.
- [ ] TS5 (FR8): Regression — `FORGED_OWN_RULES_PARTIAL` is still otherwise well-formed and still rejected for missing shape checks.
- [ ] TS6 (FR5, FR6, NFR5): Regression — `## Result format` and `## Escaping` byte-identity, the five-numbered-constraint count, and the `## Field values` `resume_conditions` pins (normalization-not-applied, presence rule, carried-in-full) all still hold.
- [ ] TS7 (FR10): Regression — the em-workflow version in `plugin.json` equals the version in the marketplace entry and is greater than the base revision's value.

### Integration Tests
- [ ] TS8 (NFR1, NFR2, NFR4): Regression — the whole suite runs with `python3 -m unittest discover -s tests` using only the standard library.

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

Not applicable: the repository has no E2E infrastructure.

### Edge Cases
- [ ] A decoded CR (U+000D), LF (U+000A) or TAB (U+0009) inside `resume_conditions` is not a violation (FR2).
- [ ] A terminal-control code point other than CR, LF and TAB inside `resume_conditions` — including U+2028 / U+2029 and the C0/C1 terminal-control ranges — is still rejected (FR1, assumption A1).
- [ ] A surviving CR, LF or TAB inside `detail` is still rejected, because its normalization must have been skipped (FR3).
- [ ] The pre-change wording used verbatim as a forged sample is rejected by the new matcher (FR9, TS2).

### Performance Tests

Not applicable.

## Security Considerations

- **Authentication:** Not applicable.
- **Authorization:** Not applicable.
- **Input Validation:** The feature restates, per field, which decoded code points a structured-result value rejects: `detail` rejects a line terminator or a terminal-control code point; `resume_conditions` rejects only terminal-control code points other than CR, LF and TAB (FR1). These stay defense-in-depth hardening rules of the document, not new runtime validation.
- **Data Protection:** Not applicable.
- **XSS Prevention:** Not applicable.
- **SQL Injection Prevention:** Not applicable.
- **CSRF Protection:** Not applicable.

## Error Handling

### Error Codes

Not applicable. The change introduces no runtime error path (NFR4).

### Error Flow

Not applicable.

## Performance Optimization

### Performance Goals

Not applicable.

### Optimization Strategies

Not applicable.

### Caching Strategy

Not applicable.

## Success Criteria

- [ ] All functional requirements (FR1-FR10) are implemented and tested.
- [ ] All test scenarios (TS1-TS8) pass.
- [ ] AC5: `python3 -m unittest discover -s tests` passes with no new failures relative to the base revision.
- [ ] AC6: `_assert_own_hardening_rules_stated` and `FORGED_OWN_RULES_PARTIAL` reflect the new wording, and `TestOwnHardeningRulesMatcherNegativeProof`'s three tests all still pass.
- [ ] AC7: A new positive test fails against the pre-change document text and passes against the post-change text.
- [ ] AC8: `TestEscapingAndResultFormatByteIdentical` and `test_five_carried_over_constraints_still_present_and_still_five` pass unmodified.
- [ ] AC9: `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` carry the same bumped em-workflow version.
- [ ] Performance goals: not applicable.
- [ ] Security requirements are satisfied.
- [ ] Documentation is complete.
- [ ] Code review is completed.

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

None. Every requirement (FR1-FR10, NFR1-NFR5) has `status: ok`; no requirement is `tbd`.

## Assumptions

Recorded by requirements-analyst; carried here unchanged.

- **A1** (impact: medium, reversible): The exemption set for `resume_conditions` is exactly CR (U+000D), LF (U+000A) and TAB (U+0009); every other code point the old rule covered - including U+2028 / U+2029 and the C0/C1 terminal-control ranges - stays rejected.
- **A2** (impact: low, reversible): `detail`'s own rejection rule is unchanged in substance; only its presentation changes because the shared bullet is split.
- **A3** (impact: low, reversible): The em-workflow version bump is a patch increment.
- **A4** (impact: medium, reversible): The "positive case" required by the completion definition is a document-wording conformance test, not an executable emitter test.
- **A5** (impact: low, reversible): `## Result format` and `## Escaping` are not edited.
- **A6** (impact: low, reversible): The five numbered carried-over consumer constraints stay exactly five; all new wording is expressed as bullets under the OWN-rules label.
- **A7** (impact: low, reversible): `em-workflow/references/batch-mode.md` and `em-workflow/skills/develop/SKILL.md` need no edit.
- **A8** (impact: low, reversible): The "cannot fire" preamble is resolved by deleting the blanket claim rather than by restating it per rule.

## Implementation Phases (if applicable)

Not applicable. The change is a single documentation-and-test correction plus the paired version bump; no phased delivery.

The design step is skipped: documentation-SSOT wording correction plus text-conformance tests in an existing module. No UI, no new module or interface, no data model, no architectural boundary; the change surface is two known files plus the two version manifests. Design-system candidates: 0.

## References

- Requirements document: `feature-docs/resume-conditions-newline-rejection/REQUIREMENTS.md`
- SSOT under correction: `em-workflow/references/batch-terminal-line.md`
- Conformance tests: `tests/test_batch_stop_contract.py`
- Version bump rule: `.claude/rules/core-plugin-version-bump.md`
- Plugin manifest: `em-workflow/.claude-plugin/plugin.json`
- Marketplace manifest: `.claude-plugin/marketplace.json`
- Test conventions: `test/README.md`
