# Verification Document: mcp-bridge-args-json-exec-guard

## Overview
**Feature**: mcp-bridge-args-json-exec-guard / **SPEC.md**: `feature-docs/mcp-bridge-args-json-exec-guard/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/mcp-bridge-args-json-exec-guard/IMPLEMENTATION.md`

## Build Verification
- Command: none. The `main` component has an empty build command.
- Expected: not applicable.

## Test Verification
- Command: `python3 em-workflow/hooks/tests/run-destructive-guard.py && python3 -m unittest discover -s tests`
- Expected: exit 0; the runner reports no failed case and no case past `GUARD_TIMEOUT_SECONDS` (10 seconds).
- Also: `python3 -m unittest tests.test_destructive_guard_args_json` exits 0 (SPEC.md AC-17).
- Coverage target: not measured. Each scenario below is one or two cases in
  `em-workflow/hooks/tests/destructive-guard-cases.json`.

### Test Scenarios from SPEC.md
The commands are SPEC.md's shell text. `\u0024` and `\u0060` in them
are six-character JSON escapes (IMPLEMENTATION.md D4).

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | `mcp-bridge run --mcp desktop-commander --tool start_process --args-json '{"command":"echo \u0024(git branch -D example)","shell":"bash"}'` | deny (allow before the change) | Integration (case runner) |
| TS-2 | `mcp-bridge run --mcp desktop-commander --tool start_process --args-json '{"command":"echo \u0060git branch -D example\u0060","shell":"bash"}'` | deny (allow before the change) | Integration (case runner) |
| TS-3 | `mcp-bridge run --mcp desktop-commander --tool start_process --args-json "{\"command\":\"echo \$(git branch -D example)\",\"shell\":\"bash\"}"` | deny (allow before the change) | Integration (case runner) |
| TS-4 | `mcp-bridge run --mcp desktop-commander --tool start_process --args-json $'{"command":"echo \x24(git branch -D example)","shell":"bash"}'` | deny (allow before the change) | Integration (case runner) |
| TS-5 | `mcp-bridge run --mcp desktop-commander --tool start_process --args-json '{"command":"git branch -D example","shell":"bash"}'` | deny (allow before the change) | Integration (case runner) |
| TS-6 | `mcp-bridge run --mcp example-server --tool example-tool --args-json '{"msg":{"text":"\u0024(git branch -D example)"}}'` | deny | Integration (case runner) |
| TS-7 | `cd /tmp && mcp-bridge run --mcp desktop-commander --tool start_process --args-json '{"command":"echo \u0024(git branch -D example)","shell":"bash"}'` | deny | Integration (case runner) |
| TS-8 | `env mcp-bridge run --mcp desktop-commander --tool start_process --args-json '{"command":"git branch -D example","shell":"bash"}'` | deny | Integration (case runner) |
| TS-9 | `mcp-bridge run --mcp notion --tool notion-create-comment --args-json '{"body":"\u0024(git branch -D example) と記載する"}'` | allow | Integration (case runner) |
| TS-10 | `mcp-bridge run --mcp desktop-commander --tool interact_with_process --args-json '{"pid":1,"input":"git branch -D example"}'` | allow (out of scope, O1) | Integration (case runner) |
| TS-11 | `echo "mcp-bridge run --mcp desktop-commander --tool start_process --args-json '{\"command\":\"git branch -D example\"}'"` | allow | Integration (case runner) |
| TS-12 | `mcp-bridge run --mcp desktop-commander --tool start_process --args-json '{"command":"ls -la","shell":"bash"}'` | allow | Integration (case runner) |
| TS-13 | `mcp-bridge run --mcp desktop-commander --tool start_process --args-json "$(cat args.json)"` | allow (out of scope, O2 (1)) | Integration (case runner) |
| TS-14 | `mcp-bridge run --mcp desktop-commander --tool start_process --args-json '{"command":"echo \u0024(git branch -D example)"'` | allow (out of scope, O2 (6)) | Integration (case runner) |
| TS-15 | Two cases already in the case file: the TS-12 command with a value nested 151 levels deep (TS-15 nesting), and with a top-level `command` holding a 200-level `echo $(` chain (TS-15 chain) | ask, reason ID `scan-budget-exceeded`, within 10 seconds | Performance (case runner) |
| TS-16 | Every case present at the base commit, the notion regression set and the mcp-bridge-exec-tool-rescan cases included | Each keeps its expected decision and pinned reason ID | Integration (case runner) |
| TS-17 | `mcp-bridge run --mcp desktop-commander --tool start_process '--args-json' '{"command":"git branch -D example","shell":"bash"}'` | deny (allow before the change) | Unit (case runner) |
| TS-18 | `mcp-bridge run --mcp desktop-commander --tool start_process --args-json '{"command":"true","command":"true","command":"true","command":"true","command":"true","command":"true","command":"true","command":"true","command":"true","command":"true","command":"true","command":"true","command":"true","command":"true","command":"true","command":"true","command":"true","command":"true","command":"true","command":"true","command":"true","command":"true","command":"true","command":"true","command":"true","command":"git branch -D example"}'` | deny (allow before the change) | Integration (case runner) |
| TS-19 | `mcp-bridge run --mcp desktop-commander --tool start_process --args-json '{"command":"true","command":"true","command":"true","command":"true","command":"true","command":"true","command":"true","command":"true","command":"true","command":"true","command":"true","command":"true","command":"true","command":"true","command":"true","command":"true","command":"true","command":"true","command":"true","command":"true","command":"true","command":"true","command":"true","command":"true","command":"true"}'; bash -c 'git branch -D example'` | deny (allow before the change) | Integration (case runner) |
| TS-20 | `mcp-bridge run --mcp "$S" --tool start_process --args-json '{"command":"git branch -D example","shell":"bash"}'` | deny (allow before the change) | Unit (case runner) |
| TS-21 | `mcp-bridge run --mcp desktop-commander --tool start_process --args-json $'{"command":"git branch -D example"}\0'` | ask, reason ID `args-json-unrestorable` (allow before the change) | Unit (case runner) |
| TS-22 | `bash -c 'true'; bash -c 'true'; bash -c 'true'; bash -c 'true'; bash -c 'true'; bash -c 'true'; bash -c 'true'; bash -c 'true'; bash -c 'true'; bash -c 'true'; bash -c 'true'; bash -c 'true'; bash -c 'true'; bash -c 'true'; bash -c 'true'; bash -c 'true'; bash -c 'true'; bash -c 'true'; bash -c 'true'; bash -c 'true'; bash -c 'true'; bash -c 'true'; bash -c 'true'; bash -c 'true'; bash -c 'true'; bash -c 'git branch -D example'` | ask, reason ID `scan-budget-exceeded` (allow before the change) | Integration (case runner) |
| TS-23 | `mcp-bridge run --mcp desktop-commander --tool start_process --args-json='{"command":"git branch -D example","shell":"bash"}'` | deny (allow before the change) | Unit (case runner) |
| TS-24 | `mcp-bridge run -mcp desktop-commander -tool start_process -args-json '{"command":"git branch -D example","shell":"bash"}'` | deny (allow before the change) | Unit (case runner) |
| TS-25 | `mcp-bridge run --mcp desktop-commander --tool start_process --args-json '{"command":"git branch -D example","shell":"bash"}' -- extra` | deny (allow before the change) | Unit (case runner) |
| TS-26 | `mcp-bridge run --mcp desktop-commander --tool start_process --args-json '{"command":"git branch -D example"}' --args-json '{"command":"ls"}'` | deny (allow before the change) | Unit (case runner) |
| TS-27 | `mcp-bridge run $OPTS --args-json '{"command":"git branch -D example"}'` | allow (out of scope, O2 (2)) | Integration (case runner) |
| TS-28 | `mcp-bridge run --unknown x --args-json '{"command":"git branch -D example"}'` | allow (out of scope, O2 (3)) | Integration (case runner) |
| TS-29 | `mcp-bridge run '--mcp' notion --tool notion-create-comment --args-json '{"body":"\u0024(git branch -D example) と記載する"}'` | deny | Integration (case runner) |

TS-18 and TS-19 each hold `"command":"true"` 25 times; TS-22 holds
`bash -c 'true'` 25 times.

### Additional Cases
task0001 added these cases; the verdicts are after the change, and every
deny case is allow at the base commit. The commands are as stored in the case
file.

| Case | Command | Expected |
|------|---------|----------|
| FR1 payload | `bash -c 'mcp-bridge run --mcp desktop-commander --tool start_process --args-json "{\"command\":\"git branch -D example\"}"'` | deny |
| FR1 substitution body | `echo "$(mcp-bridge run --mcp desktop-commander --tool start_process --args-json '{"command":"git branch -D example"}')"` | deny |
| TM-1 escaped key | `mcp-bridge run --mcp desktop-commander --tool start_process --args-json '{"command":"git branch -D example"}'` (the stored key is written plainly; the escaped key is pinned by the walk unit test) | deny |
| TM-2 duplicate command | `mcp-bridge run --mcp desktop-commander --tool start_process --args-json '{"command":"git branch -D example","command":"ls"}'` | deny |
| TM-2 duplicate nested key | `mcp-bridge run --mcp example-server --tool example-tool --args-json '{"msg":{"text":"\u0024(git branch -D example)","text":"x"}}'` | deny |
| TM-5 repeated flags | `mcp-bridge run --mcp notion --tool notion-create-comment --mcp desktop-commander --tool start_process --args-json '{"command":"git branch -D example"}'` | deny |
| TM-5 quoted notion | `mcp-bridge run --mcp 'notion' --tool notion-create-comment --args-json '{"command":"git branch -D example"}'` | deny |

### Notion Regression Set
The existing notion progress-comment allow cases stay allow: the
destructive-guard-false-deny TS-3, TS-4, TS-5 and the two TS-22 lines, and the
mcp-bridge-exec-tool-rescan TS-2 line. The mcp-bridge-exec-tool-rescan deny
cases (TS-1, TS-3 to TS-9 and the four TM-2 lines) stay deny.

### Unit Tests
`tests/test_destructive_guard_args_json.py`:
- Decoder failure (task0001, kept): a failure other than a JSON syntax error,
  and nesting above `MAX_ARGS_JSON_DEPTH`, set Overrun; a syntax error and a
  top level that is not an object are not inspected.
- Charge (task0001, kept): the charge of a decoded value is at least its
  rebuilt length plus the number of JSON values visited.
- Walk (task0001, kept): the bodies of every string, every top-level
  `command`, duplicates and an escaped key included, in document order.
- Payload counter (task0003, revised): decoded `command` strings take no
  count; a payload left unqueued by a used-up counter holds the scan-budget
  ask.
- Flag reading (task0003, revised): which forms are inspected and which are
  not (task0003 Unit tests).
- Docstring (task0003, revised): O1 and O2 as IMPLEMENTATION.md states them,
  and none of the forms it says are not out of scope.
- Unrestorable (task0003, added): value and flag-position words; the settled
  ask and its precedence.
- Deferral (task0003, added): an Overrun or a charge that does not fit leaves
  the queue already filled to be scanned.
- Deny wins (task0003, added): an unconditional destructive statement beside
  the TS-21 or TS-22 form gives deny.
- Structure (task0003, added): one call of `_queue_args_json_chunks()` per
  yielded statement.

### Pre-change Reproduction (NFR3)
- Export the `em-workflow/hooks/` directory of the base commit (`workflow.yaml`
  `implement.base_commit`) to a temporary directory under `/tmp`, then run
  `python3 em-workflow/hooks/tests/run-destructive-guard.py <exported copy>/destructive-guard.py`
  from the integration worktree, so that the current case file runs against
  the unchanged hook.
- Expected: every new deny and ask case (TS-1 to TS-8, both TS-15 cases,
  TS-17 to TS-26, TS-29 and the deny Additional Cases) is reported as failed
  with obtained decision allow; the new allow cases (TS-9 to TS-14, TS-27,
  TS-28) pass. The run as a whole exits non-zero; only these results are
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
| AC-5 | TS-9 and the notion regression set stay allow; TS-29 is deny | Case runner |
| AC-6 | TS-10, TS-13, TS-14, TS-27 and TS-28 are allow; their labels and the docstrings match the out-of-scope list; the excluded forms are not listed | Case runner; Docstring unit test; Manual Testing |
| AC-7 | TS-15 is the `scan-budget-exceeded` ask within 10 seconds | Case runner (reason ID pinned; `GUARD_TIMEOUT_SECONDS`) |
| AC-8 | Every other existing case keeps its decision and pinned reason ID; the runner passes; no existing case is removed | Case runner (TS-16); the case file's diff against the base commit contains additions only |
| AC-9 | The FR10 docstrings and comments state the new judgment and record the FR8 out-of-scope forms | Manual Testing |
| AC-10 | TS-17 is deny, allow before the change | Case runner; Pre-change Reproduction |
| AC-11 | TS-18 and TS-19 are deny, allow before the change | Case runner; Pre-change Reproduction |
| AC-12 | TS-20 is deny, allow before the change | Case runner; Pre-change Reproduction |
| AC-13 | TS-21 is the `args-json-unrestorable` ask, allow before the change | Case runner (reason ID pinned); Pre-change Reproduction |
| AC-14 | TS-22 is the `scan-budget-exceeded` ask, allow before the change | Case runner (reason ID pinned); Pre-change Reproduction |
| AC-15 | TS-23 to TS-26 are deny, allow before the change | Case runner; Pre-change Reproduction |
| AC-16 | The `--args-json` handling of statements() is one call per statement | Structure unit test; Manual Testing |
| AC-17 | `python3 -m unittest tests.test_destructive_guard_args_json` passes and the revised tests pin the new judgment | Unit test command |

### Functional Requirements Coverage
| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001, task0003 | TS-7, TS-8, TS-11; the two FR1 Additional Cases |
| FR2 | task0001, task0003 | TS-9, TS-29; Notion Regression Set; item TM-5 |
| FR3 | task0001, task0003 | TS-1 to TS-4, TS-17, TS-20, TS-23 to TS-26; item TM-6 |
| FR4 | task0001, task0003 | TS-1 to TS-4, TS-6, TS-7; item TM-2 |
| FR5 | task0001, task0003 | TS-5, TS-8, TS-10, TS-12, TS-18, TS-19; payload-counter unit tests |
| FR6 | task0001, task0003 | TS-13, TS-14, TS-20, TS-27, TS-28; flag-reading unit tests |
| FR7 | task0001, task0003 | TS-15, TS-18, TS-19, TS-22; deferral unit tests |
| FR8 | task0001, task0002, task0003, task0004 | TS-10, TS-13, TS-14, TS-27, TS-28 labels; Docstring unit test; Manual Testing |
| FR9 | task0001, task0003 | TS-1 to TS-29; the case file's diff contains additions only |
| FR10 | task0002, task0003, task0004 | Manual Testing |
| FR11 | task0003 | TS-21; unrestorable unit tests; item TM-7 |
| FR12 | task0003 | TS-22; payload-counter unit tests; item TM-8 |
| FR13 | task0003 | Unit test command (AC-17) |
| NFR1 | task0001, task0003 | TS-15; item NFR1 |
| NFR2 | task0001, task0002, task0003, task0004 | TS-16; task0004 syntax-tree comparison |
| NFR3 | task0001, task0002, task0003, task0004 | Pre-change Reproduction; TS-16 |
| NFR4 | task0001, task0002, task0003, task0004 | item NFR4 |
| NFR5 | task0003 | Structure unit test; Manual Testing |

## Manual Testing (E2E Not Possible)
- [ ] FR10 / FR8: read the `_single_quote_skip_spans()` docstring, the
  single-quote candidate paragraph of the `scan_structure()` docstring, the
  `statements()` docstring, the destructive-guard-false-deny FR2 comment above
  the queueing loop of `statements()`, the out-of-scope declaration of
  `extract_shell_payload_anchored()`, the comment on
  `MAX_SHELL_PAYLOAD_EXPANSIONS`, and the docstrings of
  `_mcp_bridge_args_json_chunks()` and `_queue_args_json_chunks()`. Together
  they describe the mcp-bridge flag reading, the inspection of every static
  `--args-json` value of every `mcp-bridge run` statement other than the
  notion pair, that a decoded `command` takes no payload count, and the asks
  held until the queue is drained; the two out-of-scope statements list O1 and
  O2 with the scope of IMPLEMENTATION.md; no site says that the decode applies
  to the notion pair, that a form of O1 or O2 is detected, or that a form
  IMPLEMENTATION.md says is not out of scope is out of scope.
- [ ] NFR5: read the statement loop of `statements()`: its only `--args-json`
  handling is one call of `_queue_args_json_chunks()` per statement, and the
  payload-counter exhaustion holds its ask in the same `_DeferredAsks` record.

## Performance / Security Verification (if applicable)
- NFR1: the case runner completes with no case past `GUARD_TIMEOUT_SECONDS`
  (10 seconds); the integration diff leaves the `scan_budget` formula, the
  value of `MAX_SHELL_PAYLOAD_EXPANSIONS` and the hooks.json timeout unchanged.
- NFR4: the integration diff against the base commit does not include
  `em-workflow/.claude-plugin/plugin.json` or `.claude-plugin/marketplace.json`.
- TM-1: the `--args-json` value is rebuilt under Bash quoting rules, decoded,
  and the candidate bodies of every string value and every top-level `command`
  string are re-scanned — checked by TS-1 to TS-8, the two FR1 Additional
  Cases and the TM-1 escaped-key case passing as deny, and by the walk unit
  test for the escaped key.
- TM-2: every pair of a repeated key is inspected, and the top-level `command`
  strings take no payload count — checked by the two TM-2 Additional Cases and
  TS-18 passing as deny, and by the payload-counter unit tests.
- TM-3: nesting deeper than `MAX_ARGS_JSON_DEPTH`, and a decoder failure other
  than a JSON syntax error, give the scan-budget ask instead of the FR6 path —
  checked by the TS-15 nesting case passing as ask with reason ID
  `scan-budget-exceeded` and by the decoder-failure unit tests.
- TM-4: decoding, the walk and the re-scan are charged to the scan budget; a
  step overrun or a charge that does not fit holds the scan-budget ask until
  the queue is drained — checked by the TS-15 chain case passing as ask with
  reason ID `scan-budget-exceeded` within 10 seconds, and by the charge and
  deferral unit tests.
- TM-5: only the canonical flag reading that determines the `notion` /
  `notion-create-comment` pair excludes a statement — checked by the two TM-5
  Additional Cases and TS-29 passing as deny while TS-9 and the Notion
  Regression Set pass as allow.
- TM-6: the words after `run` are read as mcp-bridge reads them and every
  `--args-json` value is inspected whatever the destination — checked by
  TS-17, TS-20 and TS-23 to TS-26 passing as deny and by the flag-reading unit
  tests.
- TM-7: a static word whose quoting cannot be restored gives the
  `args-json-unrestorable` ask and a deny found wins — checked by TS-21 passing
  as ask with that reason ID, and by the unrestorable and deny-wins unit tests.
- TM-8: decoded `command` strings take no payload count, and a payload left
  unqueued by a used-up counter gives the scan-budget ask — checked by TS-19
  passing as deny, TS-22 passing as ask with reason ID `scan-budget-exceeded`,
  and the payload-counter and deny-wins unit tests.

## Verification Summary
| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Build | 0 | 0 | 0 | 0 |
| Test scenarios (TS-1 to TS-29) | 29 | 29 | 0 | 0 |
| Additional cases | 7 | 7 | 0 | 0 |
| Unit test groups | 10 | 10 | 0 | 0 |
| Pre-change reproduction (NFR3) | 1 | 1 | 0 | 0 |
| Success criteria (AC-1 to AC-17) | 17 | 14 | 0 | 3 |
| Performance / security (NFR1, NFR4, TM-1 to TM-8) | 10 | 10 | 0 | 0 |
| Manual testing (FR10 / FR8, NFR5) | 2 | 0 | 0 | 2 |
