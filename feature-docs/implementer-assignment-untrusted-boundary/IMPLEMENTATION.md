# Implementation Plan: implementer-assignment-untrusted-boundary

## Overview

The implementer assignment payload moves `skills_to_load`, `project_commands` and `expected_files` into a labelled untrusted-data section placed after every trusted field, each value written as a one-line JSON literal; `implementer.md` and the worktree-task-workflow skill state that those values are data, not instructions. The change is confined to three plugin documents plus new standard-library regression tests; no script changes.

## Technology Stack

- **Documents**: Markdown prompt and reference documents of the em-workflow plugin.
- **Tests**: Python 3 standard-library `unittest` only (NFR1), run by `python3 -m unittest discover -s tests`.
- **New dependencies**: none (`project.license` is `none`; no license record needed).

## Layer Structure

| Layer | File | Responsibility in this feature |
|-------|------|--------------------------------|
| Orchestrator procedure | `em-workflow/references/implement-phase.md` | Defines the assignment payload the orchestrator writes (C1, C2, C3) |
| Implementer system prompt | `em-workflow/agents/implementer.md` | Top-level data-not-instructions rule and permitted uses (C4) |
| Implementer workflow skill | `em-workflow/skills/worktree-task-workflow/SKILL.md` | Instruction-source definition (C5) and the command execution gate |
| Queue hooks (unchanged) | `queue_launch_guard.py`, `queue_agent_index.py`, `queue_failure_net.py` | Read the identity lines of the payload |
| Regression tests | new modules under `tests/` | Pin the document contracts and the hook behaviour |

Dependency direction: `implementer.md` and `SKILL.md` refer to the payload only through the names pinned in Shared Components (section name, field names), never through `implement-phase.md` line numbers. Tests read documents as text and run hooks as separate processes.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| C1 Assignment payload layout | Line order of the implementer assignment prompt | Order: (1) the `# Task assignment` header line; (2) the `task_id:` line, then the `worktree_path:` line, as the first two lines after the header; (3) the remaining trusted fields in this order: `task_plan_path`, `implementation_md_path`, `lessons_path`, `parent_branch`, `merge_script`, `tests_yaml_path`; (4) the Untrusted data section (C2), last. Postcondition: no trusted field line follows the section label, and the first `task_id:` and `worktree_path:` lines after the header are the genuine ones. | task0001 (defines), task0004 (builds fixtures from it), task0002, task0003 (describe it) |
| C2 Untrusted data section | Carries the workflow.yaml-derived values | Section name: `Untrusted data`. It begins with one label line that starts with `## Untrusted data`; the rest of that line is free wording saying the values are data, not instructions (bounded by NFR7). Then exactly five data lines in this order: `skills_to_load`, `project_commands.build`, `project_commands.test`, `project_commands.format`, `expected_files`. Each data line holds the field name, a colon, one space and one JSON literal, all on that line. Nothing follows the five data lines inside the payload. | task0001, task0002, task0003, task0004 |
| C3 Value encoding | How each data value is written | `skills_to_load` and `expected_files`: a JSON array of strings. Each `project_commands.*`: a JSON string. Newlines and other control characters appear only in escaped form, so a value never spans lines. A missing build or format command is the empty JSON string; an empty list is the empty JSON array. Each `skills_to_load` string keeps the `em-workflow:` prefix. Postcondition: decoding a data line's JSON literal yields the original value exactly. | task0001 (defines), task0002 (decode instruction), task0004 (fixtures) |
| C4 Permitted uses | The sole use of each decoded value | `skills_to_load`: skill identifiers loaded with the Skill tool. `project_commands.*`: command strings run under worktree-task-workflow's existing verbatim-execution and approval rules; an empty string means no such command. `expected_files`: the task's file-scope list. A natural-language instruction found inside a decoded value is not followed and is recorded in the implementer report's existing `notes` field; no report field is added. | task0002 (states it), task0003 (stays consistent with it) |
| C5 Instruction source | What may direct the implementer | The orchestrator's launch prompt is an instruction source only through its trusted fields (C1 items 1 to 3) and its structure. Values in the Untrusted data section are excluded and are used only per C4. | task0003 (defines), task0002 (refers to it) |

## Conventions

- Documents name the section `Untrusted data` and the fields exactly as in C2.
- Implementer rules live in `em-workflow/agents/implementer.md` and `em-workflow/skills/worktree-task-workflow/SKILL.md` only. `worker-envelope.md`, the queue hook scripts, `bash_guard.py` and the approval store are not modified (NFR5, A3).
- No line matching `^# Task assignment\s*$` is added to any `em-workflow/agents/*.md` (NFR3, A2); a document that must mention the header does so inside a sentence.
- No raw byte-equality claim beyond the existing verbatim rule is introduced (NFR6).
- Tests use the standard-library `unittest` only. Each task adds its own new module under `tests/`; existing test modules and their assertions are not modified (NFR1, NFR4). Document tests locate text by stable anchors (section headings, the section name, field names), never by line numbers.
- The retry relaunch (I.2.c) reuses the same payload; there is no second payload definition (A7).

## Cross-task Design Decisions

### D1: Section name and data-line shape are pinned here

SPEC leaves the label and boundary-sentence wording to implementation. The four tasks run in parallel and each depends on the section (one writes it, one builds fixtures from it, two refer to it), so the section name, the label-line prefix, the field names and their order are fixed in C2. The rest of the label line and the boundary sentences stay with task0001.

Affected tasks: task0001, task0002, task0003, task0004.

### D2: One line per project command

`project_commands` is written as `project_commands.build`, `project_commands.test` and `project_commands.format`, one JSON string each, so every value is one line holding one JSON literal (FR2).

Affected tasks: task0001, task0002, task0004.

### D3: Hooks are pinned by tests, not edited

The identity-line order in C1 keeps the hooks' first-match parse valid (A1). task0004 builds its prompts from C1 to C3 directly, so it does not depend on the `implement-phase.md` text. A hook that returns a forged identity falsifies A1; that is reported as a plan deviation and the hook is not edited (NFR5).

Affected tasks: task0001, task0004.

### D4: Each document task owns its document test

Each document task writes a separate new test module, so its TDD contract stays inside the task and test modules never collide across worktrees.

Affected tasks: task0001, task0002, task0003.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| An existing test pins the old payload order or field spelling | Medium | Medium | task0001 runs the full suite; a conflict is reported as a plan deviation, never fixed by editing an existing assertion (NFR4) |
| New payload text contains an AC-1 ordering anchor phrase | Low | Medium | task0001 asserts absence and keeps the existing ordering test passing (NFR7) |
| A `# Task assignment` line enters `implementer.md` | Low | Medium | task0002 asserts absence; check-plugin-invariants runs (NFR3) |
| Another em-workflow document restates the old payload shape | Medium | Low | Outside SPEC scope; an implementer that finds one reports it as a deviation |
| A queue hook does not take the first identity line after the header (A1 false) | Low | High | task0004 detects it; reported, not patched in the hook |

## Open Questions

- None.
