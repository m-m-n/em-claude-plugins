# Verification Document: subagentstop-failed-event

## Overview

**Feature**: subagentstop-failed-event / **SPEC.md**: `feature-docs/subagentstop-failed-event/SPEC.md` / **IMPLEMENTATION.md**: `feature-docs/subagentstop-failed-event/IMPLEMENTATION.md`

## Build Verification

- Command: none (`project.components.main.build_command` is empty; the Python sources need no build step)
- Expected: not applicable

## Test Verification

- Command: `python3 -m unittest discover -s tests` (from the repository root)
- Expected: exit code 0, with no failure or error that was not already failing on the base revision
- Coverage target: not measured (no coverage tool is configured; the project uses the standard library only). Every requirement maps to at least one scenario below.

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS-1 | Implementer stop for a task whose last event is `launched`, with agent_type `implementer`, `em-workflow:implementer`, or absent; separately agent_type `Explore` with a valid block | Exactly one `failed` line for the task in each implementer case; journal unchanged for `Explore` | Unit (subprocess) |
| TS-2 | Transcript whose first user message has no header and whose second user message carries the block; an inline field without a header present | Exactly one `failed` line for the second message's task; an inline field with a block takes precedence over the transcript | Unit (subprocess) |
| TS-3 | No inline prompt, transcript path missing or unreadable or block-less, `cwd` inside a worktrees root, agents.jsonl entry matching the payload `agent_id`; plus ambiguous, stale, uncontained, oversized-candidate-list and unmatched fixtures | Exactly one `failed` line when resolvable; no append for every refusal fixture; the same journal change as `queue_taskstop_net.py` on an identical fixture | Unit and Integration (subprocess) |
| TS-4 | `task_id: task0099` line before the `# Task assignment` header, real task after it; parser parity fixture set of at least eight prompts | `failed` recorded for the post-header task only; the failure net's parser returns exactly what `queue_launch_guard.py`'s parser returns for every fixture; the launch guard targets the same task | Unit and Integration |
| TS-5 | Several rounds of concurrently started `queue_failure_net.py` and `queue_taskstop_net.py` subprocesses (at least five of each) for the same `launched` task; journal path replaced by a symlink | Exactly one `failed` line per round and every journal line parses; the symlink target is never written and the exit code is 0 | Integration (subprocess, threads) |
| TS-6 | Failure net appends `failed` for a `launched` task, then `queue_launch_guard.py` relaunches the same task | Exit 0, no deny output, a new `launched` line is the journal's last line | Integration (subprocess) |
| TS-7 | Diagnostics log: one fixture per outcome code (all nine); `cwd` without a worktrees root but a validated worktree path under one; neither yielding a root; log path as a symlink or a directory; sentinel string in the prompt; concurrent invocations | One line per invocation with the SC2 keys and the matching outcome, source and task id presence; line lands in the worktree path's root when `cwd` yields none; no file anywhere when neither yields a root; exit 0 and an identical journal when the log is obstructed; symlink target unwritten; sentinel absent from the log; journal never contains a diagnostics line; every log line parses | Unit (subprocess) |
| TS-8 | Regression and invariants: pre-existing merged, failed, Explore, missing-journal-directory, malformed-input and edge-stdin cases; `FAILED_REASON` form; `hooks.json` SubagentStop registration; import sets | Pre-existing test cases pass with their assertions intact; `FAILED_REASON` value unchanged and still parsed by `tests/test_queue_taskstop_net.py`; registration is one group, no matcher, the unchanged command, timeout 15; hook and test modules import only the standard library | Unit |
| TS-9 | Documentation contract: the SubagentStop failure net bullet and the Stale-`launched` caveat in `implement-phase.md`; the hook's module docstring | Bullet states identification order, atomic compare-and-append, diagnostics path, nine outcome codes, missing-line meaning, not-a-journal; caveat states the no-SubagentStop case is covered by the extended same-session branch without adding a writer; phrases pinned by `tests/test_stale_launched_doc_contract.py` and its writer-set check still pass; docstring names the nine codes, the log file name and the three sources | Unit (document text) |
| TS-10 | Version metadata in `em-workflow/.claude-plugin/plugin.json` and the em-workflow entry of `.claude-plugin/marketplace.json` | Identical version strings, strictly greater than 0.2.3 by numeric comparison; the written value is 0.2.4 | Unit (metadata) |
| TS-11 | Full suite | `python3 -m unittest discover -s tests` exits 0 | Suite |

## Code Quality Verification

- Format: not configured (`format_command` is empty)
- Static analysis: not configured
- Standard-library-only import checks run inside the test suite (TS-8, TS-9, TS-10)

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC-1 | `failed` appended exactly once for each listed implementer-stop case | TS-1, TS-2, TS-3 |
| AC-2 | Relaunch allowed by the launch guard after the net appends `failed` | TS-6 |
| AC-3 | Concurrent failure net and stop-tool recorder leave exactly one `failed` line, all lines parse | TS-5 |
| AC-4 | Failure net and launch guard resolve the same post-header task id | TS-4 |
| AC-5 | One diagnostics line per identification outcome; none without a worktrees root; log failures change neither exit code nor journal | TS-7 |
| AC-6 | Existing behavior kept (merged / failed / Explore / missing journal directory) | TS-1, TS-8 |
| AC-7 | `implement-phase.md` updated per FR8; version 0.2.4 in both files | TS-9, TS-10, and diff review of the two version values |
| AC-8 | Full suite passes | TS-11 |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS-1, TS-8 |
| FR2 | task0001 | TS-2 |
| FR3 | task0001 | TS-3 |
| FR4 | task0001 | TS-4 |
| FR5 | task0001 | TS-5, TS-8 |
| FR6 | task0001 | TS-7 |
| FR7 | task0001 | TS-6 |
| FR8 | task0001, task0002 | TS-9 |
| FR9 | task0003 | TS-10 |
| NFR1 | task0001 | TS-7, TS-8 |
| NFR2 | task0001, task0002, task0003 | TS-8, TS-9, TS-10 |
| NFR3 | task0001, task0002 | TS-7, TS-9 |
| NFR4 | task0001 | TS-8 |
| NFR5 | task0001 | TS-8 |
| NFR6 | task0001 | TS-5, TS-7 |
| NFR7 | task0001, task0002, task0003 | TS-11 |

## Manual Testing (E2E Not Possible)

The first two checks (A-2 agent_id match, A-4 SubagentStop delivery and the retry after `failed`) are required before the integration branch is merged; they cannot be proven by the automated suite.

- [ ] In a real em-workflow implement run, every implementer stop leaves one line in `.claude/worktrees/em-workflow/subagent-stop-diagnostics.jsonl`; for each line, check whether the recorded `agent_id` equals one of the identifier candidates of that task's agents.jsonl entry (A-2).
- [ ] In a real run, an implementer that stops without merging leaves one `failed` line, and the `implement.failed-task` retry (fresh implementer into the kept worktree) passes the launch guard.
- [ ] Diff review: in `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`, the only change is the em-workflow version from 0.2.3 to 0.2.4.
- [ ] After the merge and a Claude Code restart, the installed em-workflow plugin cache is the 0.2.4 version.

## Performance / Security Verification

- Symlink refusal at the journal path and the diagnostics log path: TS-5, TS-7.
- Prompt text never written to the diagnostics log: TS-7.
- Agent-index containment, ambiguity and staleness refusal: TS-3.
- Performance: not applicable; every hook invocation in the suite completes within its subprocess timeout.

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios | 11 | 11 | 0 | 0 |
| Success criteria | 8 | 8 | 0 | 1 (AC-7 version diff review) |
| Manual checks | 4 | 0 | 0 | 4 |
