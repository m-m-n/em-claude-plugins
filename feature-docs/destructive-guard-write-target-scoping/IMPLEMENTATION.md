# Implementation Plan: destructive-guard write-target scoping

## Overview

The self-modification judgment of the PreToolUse(Bash) guard is narrowed from
a regex search over the whole command segment to a match against an assembled
set of write-target paths, with the false-positive cases added to the
expectation suite first. A separate task raises the plugin version so the
installed cache picks the fix up.

## Technology Stack

- **Language**: Python 3 — the hook, its case table and its runner are all
  plain standard-library Python; the case table is JSON data.
- **Key libraries**: none. The hook stays on the standard library it already
  imports, and the expectation suite stays dependency-free.
- **New dependencies**: none introduced by this feature. `project.license` is
  `none`, so no license compatibility constraint applies and no dependency
  license needs recording.

## Layer Structure

| Layer | Artifact | Responsibility | Depends on |
|---|---|---|---|
| Judgment | the guard hook | Turns a command string into allow / ask / deny by static analysis only | nothing in this feature |
| Expectation data | the case table | Declares the expected judgment for each command, one entry per case | the judgment layer's vocabulary |
| Expectation runner | the suite runner | Feeds every case to the judgment layer, compares against the expectation, and holds the trailing unattended-demotion case | both layers above |
| Packaging | the two plugin manifests | Carry the version the installed cache keys on | nothing |

Allowed dependency direction is downward only: the expectation layers read the
judgment layer, never the reverse. The packaging layer is independent of all
three and is touched by exactly one task.

## Shared Components

The two tasks have disjoint file sets and share no runtime component. What
crosses the task boundary is the following pair of contracts, pinned here so
each task can be implemented against them without reading the other's plan.

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|---|---|---|---|
| Judgment vocabulary | The single set of outcomes the guard may emit | Precondition: a command string reached the hook. Postcondition: exactly one of allow / ask / deny is emitted per rule match; a segment matching no rule is allowed; ask is demoted to deny only under unattended execution. This feature changes WHICH commands match, never the vocabulary or the demotion rule. | task0001 (implements), task0002 (unaffected) |
| Plugin version field pair | The version value the installed plugin cache keys freshness on | Precondition: both manifest fields currently hold the same value. Postcondition: both hold the identical next patch value; no other plugin's version moves. Exactly one task writes these fields. | task0002 (sole writer), task0001 (must not touch) |

## Conventions

- **Judgment vocabulary**: allow / ask / deny as above. Reason strings stay in
  the existing style — a short rule identifier plus a sentence explaining why
  the user's intent is being confirmed.
- **Append-only expectation data**: an existing deny or ask case is never
  deleted or edited. New cases are appended. A false positive gets its case
  before the fix that removes it.
- **Static analysis only**: the guard never executes, stats or otherwise
  touches the paths it inspects, and returns the same judgment for the same
  command string every time.
- **Standard library only**: neither the hook nor anything under its test
  directory may acquire a third-party import.
- **Error-handling policy**: the guard must not raise on any segment it is
  handed. An empty write-target set, a token that is not a path, and a target
  that cannot be resolved statically are ordinary outcomes handled by the
  judgment flow, never exceptional ones.
- **Logging policy**: unchanged — the hook's only output channel is its
  judgment result.

## Cross-task Design Decisions

### D1: the case addition and the judgment rewrite are one task, not two

The project rule requires the false-positive cases to exist, and the suite to
be observed red, before the fix lands. Tasks in this workflow run fully in
parallel in separate worktrees, so a red-then-green ordering cannot be
expressed between two tasks — a case-only task would deliver a permanently
red suite, and a fix-only task would have nothing to turn green. The ordering
is therefore internal to one implementer session's test-first cycle.
Affected: task0001.

### D2: the version bump is isolated in its own task and has a single owner

The two manifest fields are disjoint from the hook and its suite, so the bump
parallelizes safely. Making one task the sole writer of both fields is what
keeps them identical; a second writer would risk two different values. The
value is the next patch level above the current one, because this feature is a
behaviour fix. Affected: task0002 owns the fields; task0001 must not touch
them.

### D3: detection strength is a floor, not a target

The change narrows the surface the two detection patterns are matched against.
It never narrows the case table and never relaxes a rule. Any command that is
ask or deny today and becomes allow after the change — other than the newly
added allow cases — is a defect, not an improvement. Reviewers and the verify
phase apply this as the acceptance floor. Affected: task0001, and the verify
phase.

### D4: the trash-correction proposal in the feature goal is out of scope

The goal text recorded in workflow.yaml carries a later appendix proposing a
separate change (redirecting deletions through the desktop trash, a rules
revision, and a service-unit example in the plugin README). Neither
REQUIREMENTS.md nor SPEC.md carries it, and no requirement ID covers it. It is
a different feature and must not be implemented here. Affected: both tasks.

### D5: only the repository copy of the hook is changed

Two other copies of the same script exist on a developer machine — the
installed plugin cache and a user-level hooks directory. Neither is edited by
this feature; the cache is refreshed by the version bump instead. Affected:
both tasks.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| A write source is missed when assembling the target set, silently creating a detection gap (an unmatched command is allowed outright) | Medium | High | The three extraction sources are fixed by the requirement and enumerated in the task plan; the existing deny / ask cases must all still pass, and the completeness of the extraction is an explicit review item |
| A flag is mistaken for a target argument, or a destination position is read wrongly, losing an existing ask | Medium | High | Target arguments are non-flag arguments only, with the destination-is-last rule stated per command family; the affected commands are already in the case table |
| The fix is written before the cases, so the red state is never observed and the suite silently proves nothing | Low | Medium | D1 keeps both in one session and the red observation is an acceptance criterion |
| The version stays put and the installed cache keeps serving the old judgment | Low | Medium | D2 makes the bump its own task with its own acceptance criteria |
| Scope creep into the deletion-correction proposal carried in the goal text | Medium | Medium | D4 states the boundary; both task plans repeat it as an explicit non-goal |

## Open Questions

- [ ] The optional installed-cache freshness check (TS-3) can only run where
      the plugin is actually installed and has been refreshed after the bump.
      It is recorded as optional in VERIFICATION.md rather than as a gating
      item.
