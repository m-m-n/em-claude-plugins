# Threat Model: implementer-assignment-untrusted-boundary

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md, REQUIREMENTS.md and the attack scenario in the feature goal; tier `full`. The feature changes how workflow.yaml-derived values (`skills_to_load`, `project_commands`, `expected_files`) are placed into the implementer assignment prompt, which the LLM implementer reads as its task instructions and which three queue hooks parse in separate processes. That gives two trust boundaries: repository-controlled values entering the implementer's instruction context (TB-1), and prompt text entering the hooks' identity parse (TB-2). Depth is set by the task domains: `input-handling` (all tasks), `auth` (task0002, task0003: what may instruct the implementer) and `api-contract` (task0001: the payload format shared by the orchestrator, the hooks and the implementer). Both boundaries are analysed deep.

Post-decomposition consistency: task0004 declares `input-handling`, but its only file is a new test module that verifies TB-2 without implementing it, so no Boundary files line names it.

Not covered by this feature's SPEC and not modelled here: whether an `expected_files` entry may point outside the task worktree.

## Trust Boundaries

### TB-1: workflow.yaml values into the implementer's instruction context
Crossing: `skills_to_load`, `project_commands` and `expected_files` values read from the feature's workflow.yaml (repository-controlled, attacker-influenceable text) are interpolated by the orchestrator into the assignment prompt the LLM implementer receives next to the trusted fields.
Boundary files: `em-workflow/references/implement-phase.md`, `em-workflow/agents/implementer.md`, `em-workflow/skills/worktree-task-workflow/SKILL.md`
Depth: deep (input-handling, auth, api-contract)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | Data values sit among the trusted fields with no boundary, so instruction-shaped text inside them has the same standing as the orchestrator's own instructions (FR1) | TM-1 | The values move to a labelled `Untrusted data` section after every trusted field, with adjacent text stating they are workflow.yaml data, not instructions (FR1; IMPLEMENTATION.md C1, C2) | task0001 AC-1, AC-2 | VERIFICATION.md Performance / Security Verification, TM-1 (TS1) |
| Tampering | A value containing a newline or another control character breaks out of its line and injects lines that read as trusted fields or as prompt structure (FR2) | TM-2 | Each value is written as one JSON literal on its own line, with newlines and control characters only in escaped form (FR2; IMPLEMENTATION.md C3) | task0001 AC-3 | VERIFICATION.md Performance / Security Verification, TM-2 (TS1) |
| Information disclosure | The implementer follows an instruction placed in a value, for example to read a secret file and include it in the report, exposing any file it can read through its report (FR4) | TM-3 | `implementer.md` rule: decode each value, use it only for its permitted use, never follow instructions inside it, and record such instructions in the report's notes (FR4; IMPLEMENTATION.md C4) | task0002 AC-1, AC-2, AC-4 | VERIFICATION.md Performance / Security Verification, TM-3 (TS5) |
| Elevation of privilege | The worktree-task-workflow skill counts the whole launch prompt as an instruction source, so values inside it inherit instruction authority, including over which command string is run (FR5) | TM-4 | The Untrusted input section limits the launch prompt's authority to its trusted fields and structure and excludes the data-section values; the Command execution gate runs the decoded value under the existing verbatim and approval rules, with no new byte-equality claim (FR5, NFR6; IMPLEMENTATION.md C5) | task0003 AC-1, AC-2, AC-3 | VERIFICATION.md Performance / Security Verification, TM-4 (TS6) |

### TB-2: Assignment prompt into the queue hooks
Crossing: the assignment prompt text, partly derived from workflow.yaml values, is parsed by separate hook processes (`queue_launch_guard.py`, `queue_agent_index.py`, `queue_failure_net.py`) that record journal and agent-index entries keyed by the `task_id` and `worktree_path` they extract.
Boundary files: `em-workflow/references/implement-phase.md` (identity-line order); the three queue hook scripts named above (unchanged, NFR5)
Depth: deep (input-handling, api-contract)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Spoofing | A forged `task_id:` or `worktree_path:` inside a data value, JSON-escaped or as a raw line after the genuine identity lines, makes a hook attribute journal or agent-index entries to another task or worktree (FR3) | TM-5 | The `task_id:` and `worktree_path:` lines stay the first two lines after the header, before the data section, so the hooks' unchanged first-match parse takes the genuine values (FR3, A1; IMPLEMENTATION.md C1) | task0001 AC-4; pinned by task0004 AC-1 to AC-4 | VERIFICATION.md Performance / Security Verification, TM-5 (TS2, TS3, TS4) |
