# Implementation Plan: subagentstop-failed-event

## Overview

The SubagentStop failure net (`em-workflow/hooks/queue_failure_net.py`) is reworked so that an implementer stop that never reached merge leaves exactly one `failed` journal event, and every hook invocation leaves one diagnostics line. `em-workflow/references/implement-phase.md` documents the new behavior, and em-workflow moves from 0.2.3 to 0.2.4.

## Technology Stack

- **Language**: Python 3, standard library only, in hooks and tests (NFR2).
- **Test framework**: `unittest`, run from the repository root as `python3 -m unittest discover -s tests`.
- **New dependencies**: none. `project.license` is `none`; there is no dependency license to record.

## Layer Structure

| Layer | Paths | Responsibility | Allowed dependencies |
|---|---|---|---|
| Hooks | `em-workflow/hooks/` | Standalone scripts the harness runs with a JSON payload on stdin; fail-open | Standard library only. A hook never imports another hook or any shared module. |
| Protocol documentation | `em-workflow/references/implement-phase.md` | Normative description of the queue hooks | none |
| Plugin metadata | `em-workflow/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` | Plugin version | none |
| Tests | `tests/` | Subprocess-driven hook tests, documentation-contract tests, metadata tests | Hooks as subprocess targets, or loaded by file path without running their entry point; documents and metadata read as text. A test module never imports another test module. |

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|---|---|---|---|
| SC1: failure-net identification and outcome flow | Decides, per SubagentStop invocation, which task (if any) the stop belongs to, whether `failed` is appended, and which single outcome code describes the invocation | Pre: one SubagentStop payload on stdin. Post: at most one `failed` line appended, for at most one task; exactly one outcome code selected by the flow below; exit code 0. | task0001 (implements), task0002 (documents) |
| SC2: diagnostics log record | One JSON line per invocation, in a file separate from `journal.jsonl` | Pre: an SC1 outcome and a worktrees root resolvable by the rules below. Post: exactly one line appended, or nothing when no root is found or the write fails; the exit code and the journal are never affected. | task0001 (writes), task0002 (documents) |
| SC3: journal `failed` line (unchanged) | The event the failure net appends | Keys `event`, `task`, `at`, `reason`. `reason` is the unchanged `FAILED_REASON` value, which stays a single-line double-quoted module constant (NFR4). | task0001 (writes), task0002 (documents) |

### SC1: identification and outcome flow

1. Stdin is not parsable JSON, or is not a mapping: end. No journal write, no diagnostics line.
2. `agent_type` is a string that is non-empty after trimming and is neither `em-workflow:implementer` nor `implementer`: outcome `not-implementer-type`, source `none`. A missing, empty or non-string `agent_type` continues to step 3.
3. Inline prompt fields, checked in the order `prompt`, `initial_prompt`, `agent_prompt`: the first string value containing an assignment header line (the `# Task assignment` line, matched exactly as `queue_launch_guard.py` matches it) is used; source `inline`; go to step 6. An inline field without a header line does not stop the search.
4. Transcript at `agent_transcript_path`: the first user-role message whose text contains an assignment header line is used; source `transcript`; go to step 6. A missing path, an unreadable file and malformed lines yield no text; none of them is an error.
5. No block found:
   - When the payload carries a non-empty string `agent_id`, the agent-index fallback runs with the resolution rules of `queue_taskstop_net.py`'s `find_task_identity`: nearest worktrees root above the payload `cwd`, candidate-list cap, containment in the feature directory, refusal when the identifier is ambiguous across tasks, refusal when a later launch of the same task exists. A resolved entry: source `agent-index`; go to step 7. Nothing resolved: outcome `index-unresolved`, source `none`.
   - When there is no usable `agent_id`: outcome `no-assignment-block` if any prompt text was available (a non-empty inline field, or at least one user-role message text in the transcript), otherwise `no-prompt-text`. Source `none`.
6. Parse the block: `task_id` and `worktree_path` are taken only from the text after the first header line, with the same logic and line patterns as `queue_launch_guard.py`'s `extract_task_assignment` (FR4).
7. Validate: `task_id` is `task` followed by digits; `worktree_path` is non-empty, absolute and has no `..` segment. Either invalid: outcome `invalid-identity` (source kept).
8. Journal directory = parent of the normalized `worktree_path`. Absent: outcome `journal-dir-missing`; nothing is created.
9. Inside ONE exclusive-lock critical section on the journal file (FR5): replay the journal; when the task's last event is `merged` or `failed`, outcome `already-terminal`; otherwise append one `failed` line (SC3), flush it to disk, outcome `appended`.
10. Any unexpected exception during steps 2 to 9: outcome `error`, recording the exception class name. The source and the validated task id determined before the failure are kept.
11. After the journal lock is released, write the diagnostics line (SC2). Exit 0 in every case.

The outcome code set is closed: `not-implementer-type`, `no-prompt-text`, `no-assignment-block`, `invalid-identity`, `index-unresolved`, `journal-dir-missing`, `already-terminal`, `appended`, `error`.

### SC2: diagnostics log record

- **Location**: the file `subagent-stop-diagnostics.jsonl` directly inside the worktrees root, which is the `.claude/worktrees/em-workflow` directory itself.
- **Root resolution**: walk up from the payload `cwd` (the directory itself first, then each ancestor) to the first directory that contains `.claude/worktrees/em-workflow`, the same walk `queue_taskstop_net.py` uses. When `cwd` yields no root, repeat the walk from the validated `worktree_path` (only when SC1 step 7 passed). A `cwd` that is missing, not a string, or not an absolute path yields no root. The hook process's own working directory is never consulted. No root: no line.
- **Keys of one line**:

| Key | Value | Presence |
|---|---|---|
| `at` | RFC 3339 timestamp with the local offset, seconds precision (same form as the journal's `at`) | always |
| `hook_event_name` | payload value; empty string when absent or not a string | always |
| `agent_id` | payload value; empty string when absent or not a string | always |
| `agent_type` | payload value; empty string when absent or not a string | always |
| `source` | `inline`, `transcript`, `agent-index` or `none` | always |
| `task_id` | the validated task id | only when a valid task id was resolved |
| `outcome` | one code from the SC1 set | always |
| `error_class` | exception class name | only when `outcome` is `error` |

- **Never written**: prompt text, transcript content, `worktree_path`, an invalid parsed task id.
- **Write discipline**: an append-only open that creates the file with mode 0644 when absent and refuses a symlink at the log path (NFR6); an exclusive lock on the log file around one single write of the whole line; directories are never created. Any failure skips the line silently.
- **Semantics**: not a journal and not a journal writer (NFR3); carries no task-status meaning; nothing in the workflow reads it; not committed; no rotation. A missing line alone does not distinguish a hook that did not run from a hook that ran but could not write the log (the write is skipped silently on failure).

## Conventions

- **Fail-open**: the failure net always exits 0 (NFR1). Its catch-all covers the whole invocation, including the diagnostics write.
- **Filesystem safety**: every file the hook opens for writing refuses a symlink at its own path. The hook never creates a directory.
- **Timestamps**: RFC 3339 with the local offset, as the journal already uses.
- **Tests**: standard library only. Each new test module carries its own standard-library-only self-check, as the existing modules do. Every payload `cwd`, worktree path, transcript and agent index used by a test lives inside that test's own temporary directory, so no test writes a diagnostics line into the real repository's `.claude/worktrees/em-workflow`.
- **Documentation-contract and metadata tests** follow the pattern of `tests/test_stale_launched_doc_contract.py` and `tests/test_stale_launched_version_bump.py`: files read from the repository root computed from the module's own path, one module-level constant per pinned literal, whitespace-normalized matching for prose, and a negative proof per matcher.

## Cross-task Design Decisions

### D1: the whole hook change is one task

FR1 to FR6 all change the single entry flow of `queue_failure_net.py`, and every outcome code depends on the identification steps. Splitting it would put parallel edits on the same function and make one task's tests depend on another task's code. task0001 owns the hook, its module docstring and all of its tests; task0002 owns only `implement-phase.md` and its contract test; task0003 owns only the version. The three tasks share no file.

Affected: task0001, task0002, task0003.

### D2: outcome codes, sources and log keys are fixed here

SC1 and SC2 fix the outcome-selection order, the source values and the JSON key names, so the hook (task0001) and the documentation (task0002) state the same contract without either reading the other.

Affected: task0001, task0002.

### D3: journal writer set unchanged

The failure net stays the journal writer it already is; the diagnostics log adds no writer. The writer enumeration in `workflow-schema.md`, pinned by `tests/test_stale_launched_doc_contract.py`, is not edited by any task.

Affected: task0001, task0002.

### D4: version value

The feature's version is 0.2.4, in both `em-workflow/.claude-plugin/plugin.json` and the em-workflow entry of `.claude-plugin/marketplace.json`. Only task0003 edits these two files.

Affected: task0003.

### D5: other hooks are reference sources only

`queue_launch_guard.py`, `queue_taskstop_net.py`, `queue_agent_index.py` and `hooks.json` are reference sources and test targets; no task modifies them.

Affected: task0001.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| A pre-existing test pins wording inside the two `implement-phase.md` passages task0002 edits | Medium | Suite failure | task0002 extends the passages, keeps existing sentences verbatim where possible, and runs the full suite before and after editing. |
| A pre-existing test pins the exact prior version 0.2.3 | Low | Suite failure after task0003 | task0003 runs the full suite; a failure in a file outside its set is reported as a plan deviation. |
| A commit guard requires the version bump in the same commit as a plugin-file change and rejects a task0001 or task0002 commit | Low | Implementer blocked | The previous feature used the same split with a dedicated version-bump task (`tests/test_stale_launched_version_bump.py`). A rejected commit is reported as a blocker; the version files are not edited outside task0003. |
| The concurrency test depends on timing | Medium | Flaky test | The assertion (exactly one `failed` line, every line parses) holds under every interleaving; use several rounds and generous timeouts instead of timing assumptions. |
| The live payload `agent_id` matches no agents.jsonl candidate (A-2) | Medium | The fallback never fires | The fallback is a no-op in that case; the diagnostics line records `agent_id` for a later check (manual verification item). |
| SubagentStop is not delivered for some stops (A-4) | Medium | No `failed` from the net | Out of scope; the existing extended same-session branch covers it; the missing diagnostics line makes it observable. |
| A large transcript without any block is scanned to the end | Low | Slower hook, still within the 15-second timeout | The scan reads line by line and stops at the first matching message. |
| The diagnostics log grows without bound (A-5) | Low | Disk use | Accepted by SPEC (no rotation). |

## Open Questions

- None blocking. A-2 and A-4 cannot be verified inside the repository; they are manual verification items in VERIFICATION.md.
