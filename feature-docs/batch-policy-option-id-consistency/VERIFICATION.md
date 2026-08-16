# Verification Document: batch-policy-option-id-consistency

## Overview

**Feature**: batch-policy-option-id-consistency
**SPEC.md**: `feature-docs/batch-policy-option-id-consistency/SPEC.md`
**IMPLEMENTATION.md**: `feature-docs/batch-policy-option-id-consistency/IMPLEMENTATION.md`

Scenario identifiers below (`TS1` … `TS12`) match SPEC.md's Test Scenarios
verbatim, and requirement identifiers (`FR1` … `NFR5`) match SPEC.md and
`workflow.yaml`'s `requirements` keys verbatim.

## Build Verification

- Command: none. `workflow.yaml`'s `project.components.main.build_command` is
  an intentionally empty string — the repository is a Claude Code plugin
  marketplace with no build step. Absence here is a recorded fact, not an
  undetected command.
- Expected: not applicable.

## Test Verification

- Command: `python3 -m unittest discover -s tests`
- Expected: exit code 0, zero failures and zero errors across the whole suite.
- Coverage target: no numeric coverage threshold is configured for this
  repository. The coverage obligation for this feature is scenario coverage:
  every requirement below maps to at least one scenario, and every new matcher
  has a negative proof (a synthetic case in which it reports failure).

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS1 | Every `action: select` entry in `em-workflow/references/batch-policies.yaml` carries an `option_id`, and the set of such gate_ids equals an explicitly pinned expected set of 11 | Both assertions pass; a newly added select gate fails until deliberately registered | Unit (policy-structure module) |
| TS2 | For each select gate, its issuing site (path plus the section declaring that gate's option vocabulary) is resolved, its offered option_ids parsed, and the policy's option_id asserted to be a member; a mutated policy option_id in a temporary copy makes it fail | Real-repository sweep passes; the mutated synthetic copy fails | Integration (correspondence module) + Unit (synthetic) |
| TS3 | `create-spec.design-step`'s policy option_id is exactly `decide_autonomously`, and the analyst contract's declared design-step vocabulary contains it | Both assertions pass | Unit (correspondence module) |
| TS4 | `create-spec.design-system`'s policy option_id is exactly `top_candidate_or_none`, and step 11a's declared vocabulary contains it in addition to the three `kind` values | Both assertions pass | Unit (correspondence module) |
| TS5 | `create-spec.stalled`'s option_id `record_tbd` is validated against that gate's offered options only; an occurrence in an `on_unanswered`-style field alone does not satisfy the check | The real gate passes; the synthetic on_unanswered-only document fails | Unit (correspondence module, synthetic) |
| TS6 | `rework.spec-change` remains absent from the policy file and the coverage check does not report it as a missing entry | Both assertions pass | Unit (policy-structure module) |
| TS7 | `create-spec.requirement-clarification` and `create-spec.command-approval` carry no `option_id` and are excluded from the correspondence check | Both assertions pass | Unit (policy-structure module) |
| TS8 | For any gate the checker cannot verify mechanically, the documented reason and compensating guarantee exist at the recorded documentation path; an undocumented or incomplete exemption fails | Registry assertions pass on the current empty registry, and the synthetic incomplete-row cases fail | Unit (documentation module) |
| TS9 | `em-workflow/references/workflow-patch.md` and `em-workflow/scripts/validate-worker-output.py` are unmodified by this change, as are `tests/test_validate_worker_output.py` and the `valid-design-step-correct-binding` fixture | Recorded digests and the pinned line still match | Integration (correspondence module) + Manual (git diff at verify) |
| TS10 | `em-workflow/.claude-plugin/plugin.json`'s version equals the em-workflow entry's version in `.claude-plugin/marketplace.json` and is strictly greater than 0.1.41 | Both assertions pass | Unit (version module) |
| TS11 | The parser used by the check handles the option vocabularies as they are actually expressed, and the restricted-subset YAML parsing of the policy file raises nothing; a fixture using the chosen representation parses cleanly | No exception; parsed content matches the fixture's declared options | Unit (correspondence module, synthetic) |
| TS12 | `python3 -m unittest discover -s tests` completes with zero failures and zero errors | Exit code 0 | Integration (whole suite) |

## Code Quality Verification

- Format: none. `workflow.yaml`'s `format_command` is an intentionally empty
  string — the repository configures no formatter. Style is verified by review
  reading against the conventions in IMPLEMENTATION.md.
- Static analysis: none configured. The plugin invariant checker
  (`em-workflow/scripts/check-plugin-invariants.py`) is exercised against the
  real repository by the existing suite, so it runs as part of the test
  command above rather than as a separate step.

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | Applying the design-step policy selects an option requirements-analyst genuinely offers, because its issuing site declares `decide_autonomously`; the policy file's option_id is unchanged | TS3 |
| SC-2 | `create-spec.design-system`'s `top_candidate_or_none` is declared at its issuing site alongside the three `kind` values | TS4 |
| SC-3 | All 11 select entries have an identified issuing site and a holding correspondence | TS1, TS2 |
| SC-4 | A test fails when any correspondence breaks; any non-checkable gate has a documented reason and alternative guarantee | TS2, TS5, TS8 |
| SC-5 | `tests/test_validate_worker_output.py:1269` and the `valid-design-step-correct-binding` fixture are byte-identical to their pre-change state | TS9 |
| SC-6 | `em-workflow/references/workflow-patch.md` and `em-workflow/scripts/validate-worker-output.py` are unmodified | TS9 |
| SC-7 | `python3 -m unittest discover -s tests` passes | TS12 |
| SC-8 | The version is bumped in the plugin manifest and set to the same value in the marketplace manifest | TS10 |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS3 |
| FR2 | task0001 | TS1, TS2, TS6, TS7 |
| FR3 | task0001 | TS4 |
| FR4 | task0001 | TS4, TS5 |
| FR5 | task0001 | TS1, TS2, TS3, TS4, TS5, TS6, TS7 |
| FR6 | task0001, task0002 | TS8 |
| FR7 | task0001 | TS1 |
| FR8 | task0003 | TS10 |
| NFR1 | task0001 | TS9 |
| NFR2 | task0001 | TS11 |
| NFR3 | task0001, task0002, task0003 | TS12 |
| NFR4 | task0002 | TS1 |
| NFR5 | task0001 | TS3, TS4 |

## E2E Testing

Not applicable. `workflow.yaml`'s `e2e_test_command` is an intentionally empty
string and the repository has no E2E infrastructure; no E2E scenario is
claimed for this feature.

## Manual Testing (E2E Not Possible)

- [ ] Change containment: the diff from the implement base commit to the
      integration tip is contained in SPEC.md's Declared Change Set, and
      contains no path under `em-workflow/references/workflow-patch.md`,
      `em-workflow/scripts/`, or `tests/test_validate_worker_output.py`.
- [ ] Read each new `## Gate option vocabulary` section and confirm the stated
      meaning of every option matches the behaviour the surrounding document
      already describes — a row whose identifier is right but whose meaning is
      invented is not detectable by any assertion.
- [ ] Confirm no contract document gained a `## Gate identifiers` section it
      did not previously have, and that the analyst contract's existing one is
      unchanged.
- [ ] Confirm the documentation introduces no second policy table and no
      option vocabulary of its own (NFR4), and that reconciliation moved only
      issuing sites, never a policy option_id (NFR5).
- [ ] Restart-required note: the version bump takes effect for an installed
      plugin only after Claude Code is restarted; confirm this is stated when
      the feature is reported.

No mockup comparison item applies — the design step is `skipped` for this
feature and no visual artifact exists.

## Performance / Security Verification

Not applicable. SPEC.md establishes no performance requirement, and the change
touches no authentication, authorization, data-handling or network surface.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios | 12 | 12 | 0 | 1 (TS9 also confirmed by git diff) |
| Success criteria | 8 | 8 | 0 | 2 (SC-5, SC-6 also confirmed by git diff) |
| Requirements | 13 | 13 | 0 | 2 (NFR4, NFR5 also read at review) |
| Manual-only checks | 5 | 0 | 0 | 5 |
