# Implementation Plan: env-route-lex-flag-isolation

## Overview

destructive-guard's env route (the reading of a `bash -c` body reached through `/usr/bin/env` and similar forms, done for the notion-pair check) stops leaking the lexer's module-level flags into the rest of the decision, and keeps finding a notion pair that only one extglob reading shows. The feature is one task, task0001.

## Technology Stack

- **Language**: Python 3, standard library only — the existing hook `em-workflow/hooks/destructive-guard.py`
- **Decision cases**: `em-workflow/hooks/tests/destructive-guard-cases.json`, run by `em-workflow/hooks/tests/run-destructive-guard.py`
- **Unit tests**: the repository's `tests/` directory, run by unittest discovery
- **New dependencies**: none (nothing to record against `project.license`)

## Layer Structure

| Layer | Responsibility | May depend on |
|-------|----------------|---------------|
| Hook decision logic (`destructive-guard.py`) | Lexes the command and returns allow / ask / deny; the env-route body reading is the only region changed | — |
| Decision cases (`destructive-guard-cases.json`) | Pin the hook's decision and reason ID for whole commands | Hook, through the runner only |
| Unit tests (`tests/`) | Pin internal state properties that no hook decision exposes (flag and extglob-setting restoration, de-duplication, extglob unit record) | Hook module, loaded in-process |

## Shared Components

None. The feature has one task, so no component built by one task is used by another.

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| — | — | — | — |

## Conventions

- Decision cases follow `.claude/rules/hook-tests.md`: three elements, plus a fourth element only for the keys `batch` / `rule` / `cwd`; no machine-specific or home-directory path in a case.
- Existing cases are neither removed nor edited (NFR3); new cases are appended.
- A case that pins an ask or deny carries `rule`; a case that pins the batch decision carries `"batch": true` (FR5).
- Changing `destructive-guard.py` is followed, in the same change, by running the runner and the unittest discovery (the project test command).
- The change leaves `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json` untouched (NFR4).

## Cross-task Design Decisions

### D1: One task

FR1 to FR4 all change the same region of one function (`_args_json_env_payload_values()`'s body reading), and FR3 fixes the order between the second reading and FR1's restoration. TS-6 must be shown to fail against an FR1-only implementation, which needs the cases and the fix in the same worktree. Splitting would make parallel tasks edit one function. Affected tasks: task0001.

### D2: Internal-state requirements are verified by unit tests

FR2 (restoration on an exception exit), FR4 (one return and one charge for a value both readings find; overrun / unrestorable from either reading) and NFR2 (no extglob unit recorded from the env route) do not show in a hook decision. They are verified by in-process unit tests under `tests/` (VERIFICATION.md TS-8, TS-9, TS-10), which the project test command already runs. NFR4 is verified by a diff check (TS-11). Affected tasks: task0001.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Flags restored to a fixed false value clear a flag raised outside the env route | Medium | High | THREAT-MODEL.md TM-1; TS-4 with a check that a restore-to-false variant fails it |
| Confining the flags removes the incidental whole-command extglob re-read that catches an extglob-only notion pair | Medium | High | THREAT-MODEL.md TM-2 (FR3); TS-6 with a check that an FR1-only variant fails it |
| The extglob setting switched for the second reading stays switched | Low | High | THREAT-MODEL.md TM-3; TS-8 |
| The second reading adds lexing work on bodies with extended-pattern parentheses | Low | Low | The second reading runs only when the first meets an extended-pattern parenthesis, and goes through the same lexer calls, so the existing scan budget covers it |
| Unit tests reach module-level names of the hook and break on a rename | Medium | Low | Tests use only the names SPEC.md itself names |

## Open Questions

- [ ] None blocking.
