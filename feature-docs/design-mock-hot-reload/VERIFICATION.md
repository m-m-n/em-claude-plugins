# Verification Document: design-mock-hot-reload

## Overview

**Feature**: design-mock-hot-reload / **SPEC.md**: `feature-docs/design-mock-hot-reload/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/design-mock-hot-reload/IMPLEMENTATION.md` / **THREAT-MODEL.md**: `feature-docs/design-mock-hot-reload/THREAT-MODEL.md`

## Build Verification

- Command: none (`project.components.main.build_command` is empty)
- Expected: not applicable

## Test Verification

- Command: `python3 -m unittest discover -s tests`
- Expected: exit code 0, no failures and no errors
- Coverage target: not applicable. The changed files are Markdown documents; every acceptance criterion is covered by a static test, a diff check or the manual check below.

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | The Step 4 section of `em-workflow/skills/design/SKILL.md` holds `run_in_background`, the dev server command example and the local URL guidance (FR1, NFR5) | The static test passes: Step 4 names `run_in_background` and the `bun ./<mock>.html` form, and guides the local URL from the server output's `url` / `Routes` lines; the file holds neither `0.0.0.0` nor a `--host` or `--port` option | Unit (static) |
| TS-2 | The Step 6 section holds `TaskStop`, and the frontmatter `allowed-tools` lists `TaskStop` (FR2) | The static test passes, including the no-server case and the already-ended case in Step 6 | Unit (static) |
| TS-3 | The Mockups item of `em-workflow/agents/designer.md` holds `?state=` and `data-state`, and states that all states are shown when there is no query (FR4) | The static test passes, including the literal-comparison statement and the no-match fallback | Unit (static) |
| TS-4 | The Mockups item still requires self-contained / CSS custom properties / every SPEC state, and design SKILL.md Step 4 still holds the mock-discipline summary (FR6) | Both static tests pass | Unit (static) |
| TS-5 | design SKILL.md states what happens when the command is missing: open directly, reload by hand (FR5) | The static test passes, including the availability check with the Bash tool's timeout parameter | Unit (static) |
| TS-6 | No signal-sending command appears as a word anywhere in design SKILL.md (NFR1) | The static test passes: none of kill, pkill and killall appears as a whole word, compared case-insensitively | Unit (static) |
| TS-7 | Hot reload works in practice: start the server with `run_in_background`, edit a mock, see the browser update, stop it with `TaskStop` (FR3) | The browser updates without a manual reload, and the task is stopped by `TaskStop` | Manual |
| TS-8 | `python3 -m unittest discover -s tests` runs the whole suite, `tests/test_refitted_worker_agents.py` and `tests/test_muse_consent_no_new_questions.py` included (NFR3, FR6) | Exit code 0 | Integration |
| TS-9 | Added by the planner (no SPEC.md scenario): the version files are untouched (NFR2) | The diff between `workflow.implement.base_commit` and the integration HEAD lists neither `em-workflow/.claude-plugin/plugin.json` nor `.claude-plugin/marketplace.json` | Integration (diff) |
| TS-10 | Added by the planner (no SPEC.md scenario): the write boundary of design SKILL.md is unchanged (NFR4) | The 境界 section of design SKILL.md has no diff between `workflow.implement.base_commit` and the integration HEAD | Integration (diff) |

## Code Quality Verification

- Format: none configured (`project.components.main.format_command` is empty) / Static analysis: none configured

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| SC-1 | All functional requirements are implemented and tested | Every row of Functional Requirements Coverage below has its tasks merged and its scenarios passing |
| SC-2 | All test scenarios pass | TS-1 to TS-10 pass |
| SC-3 | SPEC.md AC-1 to AC-8 are met | AC-1: TS-1, AC-2: TS-2, AC-3: TS-7, AC-4: TS-3, AC-5: TS-4, AC-6: TS-5, AC-7: TS-6, AC-8: TS-8 |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1 |
| FR2 | task0001 | TS-2 |
| FR3 | task0001, task0002 | TS-7 |
| FR4 | task0002 | TS-3 |
| FR5 | task0001 | TS-5 |
| FR6 | task0001, task0002 | TS-4, TS-8 |
| NFR1 | task0001 | TS-6 |
| NFR2 | task0001, task0002 | TS-9 |
| NFR3 | task0001 | TS-8 |
| NFR4 | task0001 | TS-10 |
| NFR5 | task0001 | TS-1 |

## Manual Testing (E2E Not Possible)

- [ ] TS-7: With the dev server command available, start the server for a sample mock through Bash with `run_in_background`, open the local URL it prints, edit the mock, and confirm the browser updates without a manual reload. Stop the task with `TaskStop` only. When the command is not available in the verify environment, record TS-7 as not runnable there, not as passed.

## Performance / Security Verification

- TM-1: Step 4 presents the server as local development use, starts it with no fixed port and no option or address that widens where it listens, and guides only the local URL from the server output — checked by TS-1's static assertions and by reading the Step 4 text at review.
- TM-2: the server is stopped only with `TaskStop` on the task `run_in_background` started, and design SKILL.md names no signal-sending command — checked by TS-2 and TS-6.
- TM-3: the Mockups item requires the `state` value to be used only in a literal comparison with `data-state` values, never inserted into the document or used to compose markup, selectors or code, and to hide nothing unless a section matches — checked by TS-3.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios | 10 | 9 | 0 | 1 |
| Code quality | 0 | 0 | 0 | 0 |
| Security (TM-n) | 3 | 3 | 0 | 0 |
| Total | 13 | 12 | 0 | 1 |
