# Implementation Plan: env-route-partial-overrun-check

## Overview
When exactly one of the env route's two extglob readings overruns, destructive-guard rescans the bodies and commands decoded by the in-limit reading, so a destructive command among them is denied, and keeps the overrun's scan-budget ask. The feature is one task (task0001); this document holds the decisions that bind any task touching this route, rework tasks included.

## Technology Stack
- **Language**: Python 3, standard library only (NFR1).
- **Key libraries**: none added. No new dependency, so no license is recorded (`project.license` is `none`).

## Layer Structure
The decision pipeline for one Bash command, as far as this feature relies on it:

1. **Statement analysis** — finds notion / mcp-bridge calls, including a call lifted from an environment assignment (the env route).
2. **Env-route reading** — reads the payload values once per extglob reading (one or two readings). Each reading reports its own items (candidate bodies and command strings), its own overrun and its own unrestorable.
3. **Combine** — merges the readings of one statement into one result.
4. **Queue step** — step 3 of the `--args-json` queue helper: turns the combined result into rescan items bound to payload words, charges the scan budget, and holds deferred asks.
5. **Rescan and settle** — queued items are analysed as ordinary commands; held asks are settled after the queue drains; a deny wins over every held ask.

Each layer consumes only the result of the layer before it. The change is confined to layers 3 and 4; layers 1, 2 and 5 keep their contracts.

## Shared Components
| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| Env-route combine (`_args_json_env_combine()`) | Merge the per-reading results of one env-route statement | Pre: one or two reading results, each with items, overrun and unrestorable. Post: overrun is reported raised when any reading overran (meaning unchanged). Unrestorable is reported as before. When exactly one of two readings overran, the result also carries the in-limit reading's items and their charge, computed by the existing de-duplication and charge rule over that reading alone; when every returned reading overran, it carries no items to queue. When no reading overran, the result is as before. The three lexer states are back at their entry values on return. | task0001 |
| Queue step (`_queue_args_json_chunks()`, step 3) | Queue rescan items for one statement and hold its deferred asks | Pre: a combined result. Post: no overrun gives the existing behaviour. An env-route overrun that carries in-limit items queues them, each bound to its payload word, when their charge fits the scan budget, holds the scan-budget ask either way, and stops the `--args-json` steps for the rest of the run. Any other overrun (no in-limit items, or a route other than env) queues nothing, holds the scan-budget ask and stops the `--args-json` steps, as before. | task0001 |
| Deferred asks (`_DeferredAsks`) | Hold asks until the queue drains | Unchanged. Stopping the `--args-json` steps lasts for the rest of the run. Settling picks a deny over every held ask. | task0001 |

## Conventions
- **Reason IDs**: no new reason ID. The feature uses `scan-budget-exceeded`, `args-json-unrestorable` and each destructive command's existing ID.
- **Whole-hook cases**: a case in `em-workflow/hooks/tests/destructive-guard-cases.json` that pins a decision of this route carries `rule` and does not set `batch` (`.claude/rules/hook-tests.md`).
- **Existing cases and tests**: none is removed (NFR2).
- **Version**: this feature does not change any plugin version (NFR4).

## Cross-task Design Decisions

### D1: The in-limit unit is the reading
A reading that overran contributes nothing, including values that individually fit the limit. Overrun inside one reading on routes other than env keeps its current handling. Rationale: REQUIREMENTS.md 14.1 fixes this unit; under it the two fix proposals in the goal give the same behaviour. Affected: task0001.

### D2: Deny precedence uses the existing settle mechanism
No new priority rule. Items queued from the in-limit reading are rescanned like any queued item, and a deny they produce wins over the held scan-budget ask when the held asks are settled. Rationale: REQUIREMENTS.md 14.1. Affected: task0001.

### D3: Overrun keeps its meaning; in-limit items are carried beside it
The one-sided case is signalled by the in-limit items the combine result carries, not by clearing or redefining overrun. Every existing consumer of overrun (the scan-budget ask, the `--args-json` stop, tests that assert overrun is reported) keeps working. Affected: task0001.

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| The SPEC.md TS-1 body does not make exactly one reading overrun through the whole hook (REQUIREMENTS.md 10.1) | Medium | High | task0001 pins the one-sided overrun of the case body with a unit test on the real readings and adjusts the body's shape until it holds |
| The reverse direction (only the extglob-off reading overruns) cannot be built through the whole hook | Medium | Low | Covered by the per-combination unit tests (TS-3) |
| Two existing tests pin the combine's result shape | High | Low | Only their expected values change; their assertions that overrun is reported stay |
| Queuing under overrun spreads to routes other than env | Low | High | The queue step queues under overrun only for an env-route result that carries in-limit items; the existing cases for the other routes (TS-6) stay green |

## Open Questions
- [x] None.
