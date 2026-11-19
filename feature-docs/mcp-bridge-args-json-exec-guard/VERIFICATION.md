# Verification Document: mcp-bridge-args-json-exec-guard

## Overview
**Feature**: mcp-bridge-args-json-exec-guard / **SPEC.md**: `feature-docs/mcp-bridge-args-json-exec-guard/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/mcp-bridge-args-json-exec-guard/IMPLEMENTATION.md`

## Build Verification
- Command: none. The `main` component has an empty build command.
- Expected: not applicable.

## Test Verification
- Command: `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests`
- Expected: exit 0; the runner reports no failed case and no case past `GUARD_TIMEOUT_SECONDS` (10 seconds).
- Coverage target: not measured. Each scenario below is one or two cases in
  `em-workflow/hooks/tests/destructive-guard-cases.json`.

### Test Scenarios from SPEC.md
`$` and ``` below are the six-character JSON escapes, not `$` or a
backtick (IMPLEMENTATION.md D4).

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | `mcp-bridge run --mcp desktop-commander --tool start_process --args-json '{"command":"echo $(git branch -D example)","shell":"bash"}'` | deny (allow before the change) | Integration (case runner) |
| TS-2 | `mcp-bridge run --mcp desktop-commander --tool start_process --args-json '{"command":"echo `git branch -D example`","shell":"bash"}'` | deny (allow before the change) | Integration (case runner) |
| TS-3 | `mcp-bridge run --mcp desktop-commander --tool start_process --args-json "{\"command\":\"echo \$(git branch -D example)\",\"shell\":\"bash\"}"` | deny (allow before the change) | Integration (case runner) |
| TS-4 | `mcp-bridge run --mcp desktop-commander --tool start_process --args-json $'{"command":"echo \x24(git branch -D example)","shell":"bash"}'` | deny (allow before the change) | Integration (case runner) |
| TS-5 | `mcp-bridge run --mcp desktop-commander --tool start_process --args-json '{"command":"git branch -D example","shell":"bash"}'` | deny (allow before the change) | Integration (case runner) |
| TS-6 | `mcp-bridge run --mcp example-server --tool example-tool --args-json '{"msg":{"text":"$(git branch -D example)"}}'` | deny | Integration (case runner) |
| TS-7 | `cd /tmp && mcp-bridge run --mcp desktop-commander --tool start_process --args-json '{"command":"echo $(git branch -D example)","shell":"bash"}'` | deny | Integration (case runner) |
| TS-8 | `env mcp-bridge run --mcp desktop-commander --tool start_process --args-json '{"command":"git branch -D example","shell":"bash"}'` | deny | Integration (case runner) |
| TS-9 | `mcp-bridge run --mcp notion --tool notion-create-comment --args-json '{"body":"$(git branch -D example) と記載する"}'` | allow | Integration (case runner) |
| TS-10 | `mcp-bridge run --mcp desktop-commander --tool interact_with_process --args-json '{"pid":1,"input":"git branch -D example"}'` | allow (out of scope, O1) | Integration (case runner) |
| TS-11 | `echo "mcp-bridge run --mcp desktop-commander --tool start_process --args-json '{\"command\":\"git branch -D example\"}'"` | allow | Integration (case runner) |
| TS-12 | `mcp-bridge run --mcp desktop-commander --tool start_process --args-json '{"command":"ls -la","shell":"bash"}'` | allow | Integration (case runner) |
| TS-13 | `mcp-bridge run --mcp desktop-commander --tool start_process --args-json "$(cat args.json)"` | allow (out of scope, O2) | Integration (case runner) |
| TS-14 | `mcp-bridge run --mcp desktop-commander --tool start_process --args-json '{"command":"echo $(git branch -D example)"'` | allow (out of scope, O2) | Integration (case runner) |
| TS-15 | Two cases (task0001 New cases): the TS-12 command with a value nested 151 levels deep, and with a top-level `command` holding a 200-level `echo $(` chain | ask, reason ID `scan-budget-exceeded`, within 10 seconds | Performance (case runner) |
| TS-16 | Every case present at the base commit, the notion regression set and the mcp-bridge-exec-tool-rescan deny cases included | Each keeps its expected decision and pinned reason ID | Integration (case runner) |

### Additional Cases
task0001 also adds these cases; the verdicts are after the change, and every
deny case is allow before it.

| Case | Command | Expected |
|------|---------|----------|
| FR1 payload | `bash -c 'mcp-bridge run --mcp desktop-commander --tool start_process --args-json "{\"command\":\"git branch -D example\"}"'` | deny |
| FR1 substitution body | `echo "$(mcp-bridge run --mcp desktop-commander --tool start_process --args-json '{"command":"git branch -D example"}')"` | deny |
| TM-1 escaped key | `mcp-bridge run --mcp desktop-commander --tool start_process --args-json '{"command":"git branch -D example"}'` | deny |
| TM-2 duplicate command | `mcp-bridge run --mcp desktop-commander --tool start_process --args-json '{"command":"git branch -D example","command":"ls"}'` | deny |
| TM-2 duplicate nested key | `mcp-bridge run --mcp example-server --tool example-tool --args-json '{"msg":{"text":"$(git branch -D example)","text":"x"}}'` | deny |
| TM-5 repeated flags | `mcp-bridge run --mcp notion --tool notion-create-comment --mcp desktop-commander --tool start_process --args-json '{"command":"git branch -D example"}'` | deny |
| TM-5 quoted notion | `mcp-bridge run --mcp 'notion' --tool notion-create-comment --args-json '{"command":"git branch -D example"}'` | deny |

### Notion Regression Set
The existing notion progress-comment allow cases stay allow: the
destructive-guard-false-deny TS-3, TS-4, TS-5 and the two TS-22 lines, and the
mcp-bridge-exec-tool-rescan TS-2 line.

### Unit Tests
`tests/test_destructive_guard_args_json.py` (task0001):
- Decoder failure: a failure other than a JSON syntax error gives the Overrun
  result; a syntax error gives Not inspected.
- Charge: the charge of an inspected value is at least the rebuilt value's
  length plus the number of JSON values visited.
- Payload counter: with the `MAX_SHELL_PAYLOAD_EXPANSIONS` counter used up,
  the decoded `command`'s candidate body is still yielded and the command
  string is not; with one count left, both are.

### Pre-change Reproduction (NFR3)
- Export the `em-workflow/hooks/` directory of the base commit (`workflow.yaml`
  `implement.base_commit`) to a temporary directory under `/tmp`, then run
  `python3 em-workflow/hooks/tests/run-destructive-guard.py <exported copy>/destructive-guard.py`
  from the integration worktree, so that the current case file runs against
  the unchanged hook.
- Expected: every new deny case (TS-1 to TS-8 and the Additional Cases) and
  both TS-15 cases are reported as failed with obtained decision allow; the new
  allow cases pass. The run as a whole exits non-zero; only these results are
  checked.

## Code Quality Verification
- Format: none configured (empty format command).
- Static analysis: none configured.

## SPEC.md Compliance
### Success Criteria
| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | TS-1 to TS-4 are deny after the change and allow before it | Case runner; Pre-change Reproduction |
| AC-2 | TS-5 is deny after the change and allow before it | Case runner; Pre-change Reproduction |
| AC-3 | TS-6 is deny | Case runner |
| AC-4 | TS-7 and TS-8 are deny; TS-11 is allow | Case runner |
| AC-5 | TS-9 and the notion regression set stay allow | Case runner |
| AC-6 | TS-10, TS-13 and TS-14 are allow; their labels match SPEC.md's out-of-scope list | Case runner; manual reading of the three labels against SPEC.md 範囲外 and IMPLEMENTATION.md O1 / O2 |
| AC-7 | TS-15 is the `scan-budget-exceeded` ask within 10 seconds | Case runner (reason ID pinned; `GUARD_TIMEOUT_SECONDS`) |
| AC-8 | Every other existing case keeps its decision and pinned reason ID; the runner passes; no existing case is removed | Case runner (TS-16); the case file's diff against the base commit contains additions only |
| AC-9 | The FR10 docstrings and comments state the new judgment and record the FR8 out-of-scope forms | Manual Testing below |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-7, TS-8, TS-11; the two FR1 Additional Cases |
| FR2 | task0001 | TS-9; Notion Regression Set; item TM-5 |
| FR3 | task0001 | TS-1 to TS-4 |
| FR4 | task0001 | TS-1 to TS-4, TS-6, TS-7; item TM-2 |
| FR5 | task0001 | TS-5, TS-8, TS-12; payload-counter unit test |
| FR6 | task0001 | TS-13, TS-14; decoder-failure unit test |
| FR7 | task0001 | TS-15; charge unit test |
| FR8 | task0001, task0002 | TS-10, TS-13, TS-14 labels; Manual Testing |
| FR9 | task0001 | TS-1 to TS-16; the case file's diff contains additions only |
| FR10 | task0002 | Manual Testing |
| NFR1 | task0001 | TS-15; item NFR1 |
| NFR2 | task0001, task0002 | TS-16; task0002 syntax-tree comparison |
| NFR3 | task0001, task0002 | Pre-change Reproduction; TS-16 |
| NFR4 | task0001, task0002 | item NFR4 |

## Manual Testing (E2E Not Possible)
- [ ] FR10 / FR8: read the `_single_quote_skip_spans()` docstring, the
  single-quote candidate paragraph of the `scan_structure()` docstring, the
  `statements()` docstring, the destructive-guard-false-deny FR2 comment above
  the queueing loop of `statements()`, the out-of-scope declaration of
  `extract_shell_payload_anchored()` and the docstring of
  `_mcp_bridge_args_json_chunks()`. Each describes the decode and inspection of
  `--args-json` for every `mcp-bridge run` statement other than the notion
  pair; the last two list the out-of-scope forms O1 and O2 with the same scope
  as IMPLEMENTATION.md; none says that the decode applies to the notion pair or
  that a form of O1 or O2 is detected.

## Performance / Security Verification (if applicable)
- NFR1: the case runner completes with no case past `GUARD_TIMEOUT_SECONDS`
  (10 seconds); the integration diff leaves the `scan_budget` formula, the
  value of `MAX_SHELL_PAYLOAD_EXPANSIONS` and the hooks.json timeout unchanged.
- NFR4: the integration diff against the base commit does not include
  `em-workflow/.claude-plugin/plugin.json` or `.claude-plugin/marketplace.json`.
- TM-1: the `--args-json` value is rebuilt under Bash quoting rules, decoded,
  and the candidate bodies of every string value and every top-level `command`
  string are re-scanned — checked by TS-1 to TS-8, the two FR1 Additional
  Cases and the TM-1 escaped-key case passing as deny.
- TM-2: every pair of a repeated key is inspected — checked by the two TM-2
  Additional Cases passing as deny.
- TM-3: nesting deeper than `MAX_ARGS_JSON_DEPTH`, and a decoder failure other
  than a JSON syntax error, end the scan with the scan-budget ask instead of
  the FR6 path — checked by the TS-15 nesting case passing as ask with reason
  ID `scan-budget-exceeded` and by the decoder-failure unit test.
- TM-4: decoding, the walk and the re-scan are charged to the scan budget and
  an overrun gives the scan-budget ask — checked by the TS-15 chain case
  passing as ask with reason ID `scan-budget-exceeded` within 10 seconds and by
  the charge unit test.
- TM-5: only the canonical flag reading that determines the `notion` /
  `notion-create-comment` pair excludes a statement — checked by the two TM-5
  Additional Cases passing as deny while TS-9 and the Notion Regression Set
  pass as allow.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS-1 to TS-16) | 16 | 16 | 0 | 0 |
| Additional cases | 7 | 7 | 0 | 0 |
| Unit tests | 3 | 3 | 0 | 0 |
| Pre-change reproduction (NFR3) | 1 | 1 | 0 | 0 |
| Success criteria (AC-1 to AC-9) | 9 | 7 | 0 | 2 |
| Performance / security (NFR1, NFR4, TM-1 to TM-5) | 7 | 7 | 0 | 0 |
| Manual testing (FR10 / FR8) | 1 | 0 | 0 | 1 |
