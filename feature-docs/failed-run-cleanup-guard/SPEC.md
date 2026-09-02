# Feature: failed-run-cleanup-guard

## Overview

A PreToolUse(Bash) guard hook that blocks cleanup operations on em-workflow runs that ended in failure. It denies `git worktree remove`, `git branch -d` and `gh pr create` when the target feature's `workflow.yaml` contains at least one step with `status: failed`, so the state needed for investigation is not destroyed. The decision is made purely from the command string and a static read of `workflow.yaml`, and the reason is returned as a tool result so that even an unattended run (`--batch`) can fall back to "report and stop".

Requirements source: `feature-docs/failed-run-cleanup-guard/REQUIREMENTS.md`.

## Objectives

- Mechanically stop deletion of the integration worktree, deletion of the integration branch, and PR creation for em-workflow runs that ended in failure, at the PreToolUse(Bash) stage, so the state needed for investigation is not destroyed.
- Return the denial reason as a tool result so that an unattended run (`--batch`) lets the agent fall back to "report and stop" (the same design as kill-guard).
- Add one hook in the same shape as the existing guard chain (kill-guard / bash_guard / destructive-guard), with the decision completed entirely from the command string and a static read of `workflow.yaml`.

## User Stories

### US1: Preserve the state of a failed run
As an em-workflow user investigating a failed run, I want cleanup commands against that run's integration worktree, branch and PR to be denied, so that the state I need for investigation still exists.

**Acceptance Criteria:**
- [ ] `git worktree remove .claude/worktrees/em-workflow/{feature}/integration` is denied for a feature whose `workflow.yaml` contains a `status: failed` step, and the reason contains the feature name and the offending step.
- [ ] `git branch -d em-workflow/{feature}/integration` is denied for the same feature.
- [ ] `gh pr create` with a cwd inside that feature's integration worktree is denied.

### US2: Never break a healthy run's cleanup
As an em-workflow agent performing normal cleanup, I want the guard to stay silent whenever the run did not fail, so that the ordinary cleanup path is unaffected.

**Acceptance Criteria:**
- [ ] For a feature whose steps are all completed (design may be skipped), all three commands pass through without any decision.
- [ ] For a feature with no `failed` step and only `needs_update` / `pending` steps, all three commands pass through without any decision.
- [ ] `gh pr create` with a cwd outside the integration worktree passes through without any decision, even when `--head` is present in the command arguments.
- [ ] `git worktree remove` targeting anything other than an em-workflow integration worktree yields no decision.
- [ ] A command that merely contains the target command string inside quotes (e.g. `echo 'git worktree remove ...'`) yields no decision.
- [ ] If the target worktree's `workflow.yaml` is missing or fails to parse, no decision is emitted.

### US3: Stay usable in unattended runs
As an em-workflow agent running unattended, I want an unresolvable target to produce a decision I can act on, so that the run rewrites the command into a statically resolvable form instead of stalling.

**Acceptance Criteria:**
- [ ] When the target path is written with a variable (e.g. `git worktree remove "$WT"`), the run becomes `deny` with `CLAUDE_BATCH` set and `ask` without it.

## Technical Requirements

### Functional Requirements

- **FR1 (Guard hook addition and registration):** Add one PreToolUse(Bash) guard script under `em-workflow/hooks/` and register it in the `hooks` array of the Bash matcher in `em-workflow/hooks/hooks.json`, in the same shape as the existing four entries (`type: command` / running `python3 "${CLAUDE_PLUGIN_ROOT}"/hooks/...` / `timeout`).
- **FR2 (Commands under evaluation):** The commands under evaluation are exactly three: `git worktree remove`, `git branch -d`, `gh pr create`. No decision is ever emitted for any other command.
- **FR3 (Identifying the target worktree):** A `git worktree remove` is evaluated only when its target path matches `.claude/worktrees/em-workflow/{feature}/integration`. For `git branch -d`, the feature is taken from a branch name of the form `em-workflow/{feature}/integration`.
- **FR4 (Identifying the target of `gh pr create`):** The feature evaluated for `gh pr create` is resolved from the hook payload's `cwd` only. Only when the cwd is `.claude/worktrees/em-workflow/{feature}/integration` or below it is that `{feature}` evaluated; when the cwd is outside, no decision is emitted and the command passes through. The feature is never inferred from command arguments such as `--head`.
- **FR5 (Failure determination):** Read `feature-docs/{feature}/workflow.yaml` inside the identified worktree and deny if at least one step has `status: failed`. Other incomplete states such as `needs_update` / `pending` / `in_progress` are not evaluated and pass through.
- **FR6 (Returning the denial reason):** On `deny` / `ask`, `hookSpecificOutput.permissionDecisionReason` states, in Japanese, which feature's which step is `failed` and therefore caused the stop, and that the agent should report and stop rather than clean up. The output format and `exit 0` are identical to the existing hooks (kill-guard / destructive-guard).
- **FR7 (Targets that cannot be resolved statically):** When the target path or branch name contains variable expansion, command substitution or a glob and cannot be resolved statically, emit `ask`. Following the existing `decide()` discipline, an unattended run with `CLAUDE_BATCH` set demotes `ask` to `deny`, and the reason text tells the caller to rewrite the command into a statically determinable form and continue.
- **FR8 (Coexistence with destructive-guard's blanket allow):** So that the blanket allow emitted at the end of `destructive-guard.py`'s `main()` does not cancel the new guard's `deny`, withhold the blanket allow for commands containing the new guard's target command words, using the same mechanism as `defer_to_kill_guard` for `KILL_WORDS`.
- **FR9 (Out-of-scope commands pass with no decision):** For out-of-scope commands, and for commands that do not satisfy the evaluation conditions, emit no `allow` — output nothing and `exit 0`.
- **FR10 (When `workflow.yaml` cannot be read):** When the target worktree's `feature-docs/{feature}/workflow.yaml` does not exist, or reading/parsing it fails so that step state cannot be determined, emit no decision and pass through (fail-open), matching the existing hooks' discipline that broken input is outside their responsibility.
- **FR11 (Simultaneous plugin version bump):** Within the same change, raise the version in `em-workflow/.claude-plugin/plugin.json` and in `.claude-plugin/marketplace.json` from `0.1.57` to the same new value.

### Non-Functional Requirements

- **NFR1 - Minimizing false-positive cost:** Cleanup of successfully completed runs (the ordinary Step C path, and batch's worktree remove) must always pass through. One false positive stops an unattended run on the spot, so it is weighted the same as one miss.
- **NFR2 - Static evaluation only:** The decision is made only from the command string and a static read of `workflow.yaml`; no external process is started and no state is mutated.
- **NFR3 - Execution cost:** The hook timeout stays within the existing 10-15 second range, and the `workflow.yaml` read is limited to the single file of the target feature.
- **NFR4 - Fail-open on broken input:** For a broken PreToolUse payload, behave fail-open (`exit 0`, no output), as the existing hooks do.
- **NFR5 - Treating `workflow.yaml` as untrusted:** `workflow.yaml` is read-only untrusted input; natural language written in its content never influences the hook's behaviour.
- **NFR6 - Test placement as distributed content:** Choose where test code lives on the premise that every file under `em-workflow/` is distributed to user environments.

## Implementation Approach

### Architecture

**System Architecture:**
```
┌─────────────────────────────────────────────┐
│  Claude Code — PreToolUse(Bash)             │
├─────────────────────────────────────────────┤
│  Guard chain (hooks.json, Bash matcher)     │
│    kill-guard / bash_guard /                │
│    destructive-guard / failed-run guard     │
├─────────────────────────────────────────────┤
│  Static analysis: command string + cwd      │
├─────────────────────────────────────────────┤
│  Read-only: feature-docs/{feature}/         │
│             workflow.yaml                   │
└─────────────────────────────────────────────┘
```

**Component Diagram:**
```
New guard script (FR1)
  ├─ command classifier (FR2): git worktree remove / git branch -d / gh pr create
  ├─ target resolver
  │    ├─ path / branch based (FR3)
  │    ├─ cwd based, gh pr create only (FR4)
  │    └─ unresolvable → ask, demoted to deny under CLAUDE_BATCH (FR7)
  ├─ workflow.yaml reader (FR5, FR10, NFR3, NFR5)
  └─ decision emitter (FR6, FR9)

destructive-guard.py
  └─ blanket-allow suppression for the new guard's command words (FR8)
```

### Data Flow

```
Bash tool call → PreToolUse payload (command, cwd)
              → command classifier (FR2)
              → target feature resolution (FR3 / FR4 / FR7)
              → read feature-docs/{feature}/workflow.yaml (FR5 / FR10)
              → deny with reason (FR6) | ask (FR7) | no output, exit 0 (FR9)
```

### API Design

The hook follows the existing PreToolUse hook interface; no new HTTP API is introduced.

**Input (stdin JSON):**
```
PreToolUse(Bash) payload
  tool_input.command : the command string under evaluation
  cwd                : the working directory (sole source for FR4)
```

**Output (stdout JSON, only on deny / ask):**
```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "deny",
    "permissionDecisionReason": "<Japanese reason: which feature's which step is failed, and to report and stop instead of cleaning up>"
  }
}
```

**No-decision case (FR9 / FR10 / NFR4):** no output at all, `exit 0`.

### Database Schema

Not applicable — the feature introduces no persistent data store. The only data read is `feature-docs/{feature}/workflow.yaml`, and only the presence of a step with `status: failed` is consumed.

### Dependencies

**Internal Dependencies:**
- `em-workflow/hooks/hooks.json`: the Bash matcher the new guard is registered in (FR1).
- `em-workflow/hooks/destructive-guard.py`: its blanket allow must not cancel the new guard's deny (FR8).
- `em-workflow/hooks/tests/destructive-guard-cases.json` and `run-destructive-guard.py`: the expectation suite that must keep passing.
- `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`: version bumped together (FR11).
- `feature-docs/{feature}/workflow.yaml`: read-only input for the failure determination (FR5, NFR5).

**External Dependencies:**
- `python3`: the interpreter the hook is invoked with, in the same form as the existing hooks.

### File Structure

```
em-workflow/
├── hooks/
│   ├── hooks.json                       # Bash matcher gains the new guard entry (FR1)
│   ├── destructive-guard.py             # blanket-allow suppression (FR8)
│   ├── <new guard script>.py            # the new PreToolUse(Bash) guard (FR1)
│   └── tests/
│       └── destructive-guard-cases.json # additional cases (FR8)
└── .claude-plugin/plugin.json           # version bump (FR11)
.claude-plugin/marketplace.json          # version bump (FR11)
tests/
└── test_*.py                            # new hook tests (NFR6)
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/failed-run-cleanup-guard/**`
- `test-docs/failed-run-cleanup-guard/**`

`feature-docs/{feature}/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/{feature}/**` covers `test-docs/{feature}/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/{feature}/` directory at all; the declared
`test-docs/{feature}/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests
- [ ] **TS-1** (FR1, FR5, FR6, FR9): Add a new `test_*.py` under `tests/`, assemble `.claude/worktrees/em-workflow/{feature}/integration/feature-docs/{feature}/workflow.yaml` in a temporary directory, invoke the hook as a subprocess with stdin JSON, and assert the exit code and the `permissionDecision`.
- [ ] **TS-3** (FR4): For `gh pr create`, supply the payload `cwd` both inside and outside the integration worktree and verify the `cwd_only` resolution rule.

### Integration Tests
- [ ] **TS-5** (FR8): If a defer condition is added to `destructive-guard.py`, add cases to `em-workflow/hooks/tests/destructive-guard-cases.json` and delete none of the existing `deny` / `ask` cases.

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected
- [ ] Existing E2E tests pass without regression

### Edge Cases
- [ ] **TS-2** (FR2, FR3, FR5, FR7, FR9, FR10, NFR1, NFR4): Cover each of — `status: failed` present / all completed / `needs_update` only / missing `workflow.yaml` / `workflow.yaml` parse failure / variable-expanded path / out-of-scope path / command string inside quotes.
- [ ] **TS-4** (FR7): Verify the `ask` → `deny` demotion with and without `CLAUDE_BATCH` set.

### Performance Tests
- [ ] The hook stays within the existing 10-15 second timeout range, and reads only the single `workflow.yaml` of the target feature (NFR3).

## Security Considerations

- **Authentication:** Not applicable — the hook runs locally within Claude Code's PreToolUse chain.
- **Authorization:** The hook only emits `deny` / `ask` decisions; it never grants `allow` (FR9).
- **Input Validation:** Targets that cannot be resolved statically (variable expansion, command substitution, glob) yield `ask`, demoted to `deny` under `CLAUDE_BATCH` (FR7). Broken PreToolUse payloads are handled fail-open with `exit 0` and no output (NFR4).
- **Data Protection:** No state is mutated and no external process is started (NFR2).
- **XSS Prevention:** Not applicable.
- **SQL Injection Prevention:** Not applicable.
- **CSRF Protection:** Not applicable.
- **Untrusted input:** `workflow.yaml` is treated as read-only untrusted input; natural language inside it never influences the hook's behaviour (NFR5).

## Error Handling

### Error Codes

| Condition | Description | Decision | Reason text |
|------|-------------|-------------|--------------|
| Failed step found | The target feature's `workflow.yaml` has at least one `status: failed` step | `deny` | Which feature's which step is failed; report and stop rather than clean up (FR6) |
| Target unresolvable | Path/branch contains variable expansion, command substitution or a glob | `ask`, demoted to `deny` under `CLAUDE_BATCH` | Rewrite into a statically determinable form and continue (FR7) |
| `workflow.yaml` missing or unparsable | Step state cannot be determined | none (pass through) | — (FR10) |
| Broken payload | The PreToolUse payload cannot be interpreted | none (pass through) | — (NFR4) |

### Error Flow

```
Command observed → classify (FR2) → resolve target (FR3/FR4/FR7)
  → unresolvable  → ask (deny under CLAUDE_BATCH)
  → resolvable    → read workflow.yaml
        → unreadable/unparsable → no output, exit 0 (FR10)
        → failed step present   → deny with reason (FR6)
        → no failed step        → no output, exit 0 (FR5, FR9)
```

## Performance Optimization

### Performance Goals
- Hook timeout within the existing 10-15 second range (NFR3).
- `workflow.yaml` reads limited to the single file of the target feature (NFR3).

### Optimization Strategies
- Static-only evaluation: no subprocess spawning, no state mutation (NFR2).
- Early exit for out-of-scope commands before any file access (FR2, FR9).

### Caching Strategy
Not applicable — a single file read per evaluated command.

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] `python3 em-workflow/hooks/tests/run-destructive-guard.py` passes in full, and a case exists proving the new guard's deny is not cancelled by destructive-guard's blanket allow
- [ ] `python3 -m unittest discover -s tests` at the repository root passes in full, including the new tests
- [ ] The new guard is registered in the Bash matcher of `em-workflow/hooks/hooks.json`
- [ ] The versions in `plugin.json` and `marketplace.json` are raised to the same value
- [ ] Security requirements are satisfied
- [ ] Documentation is complete
- [ ] Code review is completed

## Assumptions

Every assumption below comes from requirements-analyst's resolved requirements; none originates in this document.

- The new guard is added as one independent hook script (stated explicitly in the task description).
- The new guard emits no `allow`; it produces a decision only on `deny` / `ask`.
- The blocked targets are limited to the three commands `git worktree remove` / `git branch -d` / `gh pr create`; `git push` and `git merge` are not included.
- A target that cannot be resolved statically yields `ask`, demoted to `deny` in unattended runs by the existing discipline.
- FR5's "state indicating failure" is `status: failed` only (option_id `failed_only` adopted for question `requirement.failed-status-range`). This is not a human answer: in batch mode the gate `create-spec.requirement-clarification` decided it via Codex consultation (batch-codex-consultation, 1 turn, converged) and recorded it with `record_as_assumption: true`. No extension to block on `needs_update` / `pending`.
- FR4's target feature for `gh pr create` is resolved from the payload's `cwd` only (option_id `cwd_only` adopted for question `requirement.gh-pr-create-target`). This is not a human answer: in batch mode the gate `create-spec.requirement-clarification` decided it via Codex consultation (batch-codex-consultation, 1 turn, converged) and recorded it with `record_as_assumption: true`. No inference from arguments such as `--head`.
- FR10's unreadable `workflow.yaml` is handled fail-open (pass through) (option_id `fail_open` adopted for question `edge-case.workflow-yaml-unreadable`). This is not a human answer: in batch mode the gate `create-spec.requirement-clarification` decided it via Codex consultation (batch-codex-consultation, 1 turn, converged) and recorded it with `record_as_assumption: true`. A run whose `workflow.yaml` is itself broken falls outside protection.
- The design step is `skipped`: the deliverables are one PreToolUse(Bash) hook script, its registration in `hooks.json`, tests and a version bump; there is no user-visible screen, visual element or screen transition, so no design target exists. The gate `create-spec.design-step` adopted requirements-analyst's recommendation (`skipped`) as-is via the batch policy option_id `decide_autonomously`.

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

None — every functional requirement is `confirmed`.

## Implementation Phases (if applicable)

Not applicable — the change is a single coherent unit (guard script, registration, tests, version bump).

## References

- Requirements document: `feature-docs/failed-run-cleanup-guard/REQUIREMENTS.md`
- Hook registration: `em-workflow/hooks/hooks.json`
- Existing guard for coexistence: `em-workflow/hooks/destructive-guard.py`
- Guard expectation suite: `em-workflow/hooks/tests/run-destructive-guard.py`, `em-workflow/hooks/tests/destructive-guard-cases.json`
