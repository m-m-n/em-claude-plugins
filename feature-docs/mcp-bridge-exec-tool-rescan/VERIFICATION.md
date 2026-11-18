# Verification Document: mcp-bridge-exec-tool-rescan

## Overview
**Feature**: mcp-bridge-exec-tool-rescan / **SPEC.md**: `feature-docs/mcp-bridge-exec-tool-rescan/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/mcp-bridge-exec-tool-rescan/IMPLEMENTATION.md`

## Build Verification
- Command: none. Both components (`main`, `destructive-guard`) have an empty
  build command.
- Expected: not applicable.

## Test Verification
- Command (destructive-guard): `python3 em-workflow/hooks/tests/run-destructive-guard.py`
- Command (main): `python3 -m unittest discover -s tests`
- Expected: both exit 0; the runner reports no failed case.
- Coverage target: not measured. Each scenario below is one case in
  `em-workflow/hooks/tests/destructive-guard-cases.json`.

### Test Scenarios from SPEC.md
| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | `mcp-bridge run --mcp desktop-commander --tool start_process --args-json '{"command":"echo $(git branch -D example)","shell":"bash"}'` | deny (the base-commit hook gives allow) | Integration (case runner) |
| TS-2 | `mcp-bridge run --tool notion-create-comment --args-json '{"body":"$(git branch -D example) と記載する"}' --mcp notion` | allow | Integration (case runner) |
| TS-3 | `mcp-bridge run --mcp notion --tool notion-update-page --args-json '{"body":"$(git branch -D example)"}'` | deny | Integration (case runner) |
| TS-4 | `mcp-bridge run --mcp desktop-commander --tool notion-create-comment --args-json '{"body":"$(git branch -D example)"}'` | deny | Integration (case runner) |
| TS-5 | `mcp-bridge run --args-json '{"body":"$(git branch -D example)"}'` | deny | Integration (case runner) |
| TS-6 | `mcp-bridge run --mcp notion --tool notion-create-comment --mcp desktop-commander --args-json '{"body":"$(git branch -D example)"}'` | deny | Integration (case runner) |
| TS-7 | `mcp-bridge run --mcp 'notion' --tool notion-create-comment --args-json '{"body":"$(git branch -D example)"}'` | deny | Integration (case runner) |
| TS-8 | `mcp-bridge run --mcp=notion --tool=notion-create-comment --args-json '{"body":"$(git branch -D example)"}'` | deny | Integration (case runner) |
| TS-9 | `mcp-bridge run --mcp notion --args-json '{"body":"$(git branch -D example)"}'` | deny | Integration (case runner) |
| TS-10 | Existing notion progress-comment allow cases (regression set, identified below) | allow, unchanged | Integration (case runner) |

### Regression Set Identification
TS-10 covers the existing allow cases of the notion progress-comment form
that the destructive-guard-false-deny feature added for its scenarios TS-3,
TS-4, TS-5 and the two TS-22 lines.

### Pre-change Reproduction (NFR3)
- Export the `em-workflow/hooks/` directory of the base commit (`workflow.yaml`
  `implement.base_commit`) to a temporary directory under `/tmp`, then run
  `python3 em-workflow/hooks/tests/run-destructive-guard.py <exported copy>/destructive-guard.py`
  from the integration worktree, so the current case file runs against the
  unchanged hook.
- Expected: the TS-1 case is reported as failed with obtained decision allow.
  The run as a whole exits non-zero; only the TS-1 result is checked.

## Code Quality Verification
- Format: none configured (empty format command).
- Static analysis: none configured.

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | TS-1 is deny after the change and allow before it | Case runner (TS-1); Pre-change Reproduction |
| AC-2 | TS-3 to TS-9 are all deny | Case runner |
| AC-3 | The TS-10 regression set stays allow; TS-2 is allow | Case runner |
| AC-4 | Every other existing case keeps its expected decision (and pinned reason ID); the runner passes; no existing case is removed | Case runner; the case file's diff against the base commit contains additions only |
| AC-5 | The four explanation sites state the pair condition, none says the skip applies to any static `mcp-bridge run --args-json` | Manual inspection |
| AC-6 | This feature's SPEC.md and THREAT-MODEL.md state the allowed pair and its premise; `feature-docs/destructive-guard-false-deny` is unchanged | Manual inspection |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1 to TS-10; item TM-2 |
| FR2 | task0001 | TS-10; diff inspection: W1 to W4, C1, S2, the top-level restriction and ANSI-C handling unchanged |
| FR3 | task0001 | TS-1, TS-10; full case suite; diff inspection: candidate marking unchanged |
| FR4 | task0001 | TS-1 to TS-9; case-file diff contains additions only |
| FR5 | task0001 | Manual inspection (Success Criteria AC-5) |
| FR6 | none (planner documents) | Manual inspection (Success Criteria AC-6) |
| NFR1 | task0001 | Performance / Security Verification, item NFR1 |
| NFR2 | task0001 | TS-6, TS-7, TS-8; item TM-2 |
| NFR3 | task0001 | TS-1; Pre-change Reproduction |
| NFR4 | task0001 | Performance / Security Verification, item NFR4 |

## Manual Testing (E2E Not Possible)
- [ ] FR5: read the docstring of `_single_quote_skip_spans()` (S1 part), the
  single-quote candidate paragraph of the `scan_structure()` docstring, the
  `statements()` docstring and the FR2-labelled comment in the queueing loop
  of `statements()`; each states the pair condition, and none says the skip
  applies to any static `mcp-bridge run --args-json`.
- [ ] FR6: SPEC.md Security Considerations and THREAT-MODEL.md state the
  allowed pair and premise A1; the integration diff against the base commit
  lists no path under `feature-docs/destructive-guard-false-deny/`.

## Performance / Security Verification (if applicable)
- NFR1: the case runner completes with no case exceeding `GUARD_TIMEOUT_SECONDS`
  (10 seconds); the integration diff leaves the values of `scan_budget` and
  `MAX_SHELL_PAYLOAD_EXPANSIONS` and the hooks.json timeout unchanged.
- NFR4: the integration diff against the base commit does not include
  `em-workflow/.claude-plugin/plugin.json` or `.claude-plugin/marketplace.json`.
- TM-1: S1 returns its data word only when both sides of the
  `notion` / `notion-create-comment` pair hold — checked by TS-1, TS-3, TS-4,
  TS-5 and TS-9 passing as deny in the case runner.
- TM-2: every form outside the complete flag sequence of IMPLEMENTATION.md
  decision D1 (a repeated flag, a quoted flag word or value, an `=` form, a
  single-dash flag, a `--` terminator, a positional word) leaves the pair
  undeterminable and is re-scanned — checked by TS-6, TS-7 and TS-8 and by
  these five cases passing as deny in the case runner, while TS-2 and the
  TS-10 regression set pass as allow:
  - `mcp-bridge run '--mcp' desktop-commander --mcp notion --tool notion-create-comment --args-json '{"body":"$(git branch -D example)"}'`
  - `mcp-bridge run --mcp notion --tool=start_process --tool notion-create-comment --args-json '{"body":"$(git branch -D example)"}'`
  - `mcp-bridge run --mcp notion --tool notion-create-comment -mcp desktop-commander -tool start_process --args-json '{"command":"echo $(git branch -D example)","shell":"bash"}'`
  - `mcp-bridge run -mcp desktop-commander -tool start_process --args-json '{"command":"echo $(git branch -D example)","shell":"bash"}' -- --mcp notion --tool notion-create-comment`
  - `mcp-bridge run -mcp desktop-commander -tool start_process --args-json '{"command":"echo $(git branch -D example)","shell":"bash"}' note --mcp notion --tool notion-create-comment`

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS-1 to TS-10) | 10 | 10 | 0 | 0 |
| Pre-change reproduction (NFR3) | 1 | 1 | 0 | 0 |
| Success criteria (AC-1 to AC-6) | 6 | 4 | 0 | 2 |
| Performance / security (NFR1, NFR4, TM-1, TM-2) | 4 | 4 | 0 | 0 |
| Manual testing (FR5, FR6) | 2 | 0 | 0 | 2 |
