# Implementation Plan: validator-scenario-id-format

## Overview

The worker-output validator recognizes VERIFICATION.md scenario IDs in both
the hyphenated and the hyphen-less form, and `plan-writing/SKILL.md` states
the same two forms as the scenario ID rule.

## Technology Stack

- **Language**: Python 3 (existing `em-workflow/scripts/validate-worker-output.py`
  and `tests/test_validate_worker_output.py`)
- **Test framework**: standard-library `unittest` (NFR1)
- **New dependencies**: none

## Layer Structure

Not applicable. The change touches one validator script, its test module and
one skill document.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| Scenario ID grammar | Defines which tokens are VERIFICATION.md scenario IDs | Exactly two forms are scenario IDs: the TS-n form (the letters `TS`, one hyphen, one or more decimal digits) and the TSn form (the letters `TS` immediately followed by one or more decimal digits). A recognized ID includes all consecutive digits that follow. IDs are compared as literal strings; neither form is normalized into the other, so `TS13` and `TS-13` are distinct IDs. Every ID the hyphenated-only rule recognizes today is still recognized, with the same literal value. | task0001 (the validator implements it), task0002 (`plan-writing/SKILL.md` states it) |

## Conventions

- New VERIFICATION.md files use the TS-n form for scenario IDs; the TSn form
  remains a valid scenario ID (Shared Components).
- Plugin version fields (`plugin.json`, `.claude-plugin/marketplace.json`)
  are outside every task's file set.

## Cross-task Design Decisions

### D1: One grammar, literal comparison

The validator (task0001) and the skill rule (task0002) name the same two
forms, and both treat scenario IDs as literal strings with no normalization
between forms (SPEC.md assumption a1). Affected tasks: task0001, task0002.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| The baseline and current VERIFICATION.md are read with different rules, so an already-existing ID passes the rework_index novelty check | Low | Medium | One extraction rule for both documents; THREAT-MODEL.md TM-1 (task0001 AC-4) |
| The widened rule changes results for hyphenated IDs | Low | Medium | Existing hyphenated-ID tests and the fixture corpus pass unmodified (task0001 AC-7) |

## Open Questions

None.
