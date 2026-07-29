# Verification Document: codex-reviewer temp-file isolation

## Overview

**Feature**: codex-reviewer-temp-file-isolation /
**SPEC.md**: `feature-docs/codex-reviewer-temp-file-isolation/SPEC.md` /
**IMPLEMENTATION.md**: `feature-docs/codex-reviewer-temp-file-isolation/IMPLEMENTATION.md`

## Build Verification

No build step — the repository ships Markdown and Python scripts only
(`workflow.yaml` `project.components.main.build_command` is empty).

## Test Verification

- Command: `python3 -m unittest discover -s tests`
- Expected: exit code 0, no failures, no errors
- Coverage target: not tracked (the repository has no coverage tooling)

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | `em-workflow/agents/codex-reviewer.md` is read as text | A temp-file discipline section is present | Unit |
| TS-2 | `em-review/agents/codex-reviewer.md` is read as text | The equivalent section is present | Unit |
| TS-3 | Both sections are scanned for the prescribed mechanism | `mktemp` and an `XXXXXX` template appear in each | Unit |
| TS-4 | Both sections are scanned for the prohibition | Fixed names are forbidden and uniqueness is stated as per-invocation, not per-perspective | Unit |
| TS-5 | Both sections are scanned for the failure route | Allocation failure returns the standard skip object | Unit |
| TS-6 | Both files' Codex execution lines are compared to the pre-change form | The `run_codex_exec.sh` invocation is unchanged; no prompt-file flag exists | Unit |
| TS-7 | The whole suite is run | All pre-existing tests still pass | Unit |
| TS-8 | Both `.claude-plugin/plugin.json` files are read | Each version is patch-bumped relative to the base commit | Manual |

## Code Quality Verification

- Format: no formatter configured for this repository
  (`format_command` is empty)
- Static analysis: none configured

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | All functional requirements implemented | TS-1 – TS-6 pass |
| SC-2 | All test scenarios pass | TS-7 |
| SC-3 | `run_codex_exec.sh` unmodified in both plugins | `git diff` over the integration range touches neither script |
| SC-4 | Both plugin versions patch-bumped | TS-8 |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1 |
| FR2 | task0001 | TS-2 |
| FR3 | task0001 | TS-3 |
| FR4 | task0001 | TS-4 |
| FR5 | task0001 | TS-5 |
| FR6 | task0001 | TS-1, TS-2 |
| FR7 | task0001 | TS-7 |
| NFR1 | task0001 | TS-6 |
| NFR2 | task0001 | TS-6 |
| NFR3 | task0001 | TS-3 |

## E2E Testing

Not applicable — exercising the real collision needs the Codex CLI, which is not
installed in this environment.

## Manual Testing (E2E Not Possible)

- [ ] Read both discipline sections side by side and confirm they state the same
      rule (a reader-level check the structural test cannot make).
- [ ] Confirm `git diff` over the integration range touches only the five files
      listed in task0001's Scope.
- [ ] Confirm both plugin manifest versions are patch-bumped (TS-8).

## Performance / Security Verification

- NFR3: confirm the prescribed template supplies the random component, so no
  predictable fixed path is ever documented as acceptable.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios | 8 | 7 | 0 | 1 |
| Success criteria | 4 | 3 | 0 | 1 |
