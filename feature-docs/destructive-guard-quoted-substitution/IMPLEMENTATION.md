# Implementation Plan: destructive-guard-quoted-substitution

## Overview

Pin the already-correct `rm-unresolvable` handling of a quoted command
substitution with two permanent expectation cases, and raise the em-workflow
plugin version so the change reaches installed plugin caches. The guard hook
itself is not touched.

## Technology Stack

- **Language**: Python 3, standard library only — the guard hook and its
  expectation runner already run on the standard library, and this feature
  adds no executable code at all.
- **Data formats**: JSON — the expectation-case array, the plugin manifest,
  and the marketplace manifest are all JSON documents edited by hand.
- **New dependencies**: none. No library is added, so no license check is
  triggered; `project.license` is `none`, which imposes no constraint either
  way. Nothing to record beyond this line.

## Layer Structure

Three artifact layers are in play. Only two of them are writable in this
feature.

| Layer | Artifact | Writable here | Responsibility |
|---|---|---|---|
| Expectation data | `em-workflow/hooks/tests/destructive-guard-cases.json` | yes | Declarative `[expected verdict, label, command]` records; carries no logic |
| Guard logic | `em-workflow/hooks/destructive-guard.py` | **no** (FR5) | Produces the verdict the expectation data asserts against |
| Distribution metadata | `em-workflow/.claude-plugin/plugin.json`, `.claude-plugin/marketplace.json` | yes | Cache-freshness key for installed plugin copies |

Allowed dependency direction: the expectation-data layer depends on the
observable verdicts of the guard-logic layer, never the reverse. A change is
never propagated from the data layer back into the guard. The
distribution-metadata layer depends on neither; it is bumped because any edit
below `em-workflow/` changes what is distributed.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| (none) | — | — | — |

The feature is delivered by exactly one task (decision D1 below), so no
component contract crosses a task boundary. The conventions below are still
binding, because they are shared between this document, VERIFICATION.md, the
task plan, and the commit messages the task produces.

## Conventions

### C1: Counting vocabulary (MANDATORY)

Two different numbers describe this test suite, and they never coincide.
Every count stated in this feature's documents, commit messages, task reports
and review responses names which of the two it is.

| Name | Definition | Before this feature | After this feature |
|---|---|---|---|
| **array element count** | Number of `[expected verdict, label, command]` records stored in `em-workflow/hooks/tests/destructive-guard-cases.json` | **225** | **227** |
| **suite-reported total** | The `N/N passed` figure `em-workflow/hooks/tests/run-destructive-guard.py` prints | **226/226** | **228/228** |

The suite-reported total is always the array element count **plus one**: the
runner computes its total as the number of loaded cases plus one, because it
executes one additional hard-coded case that is not stored in the array (the
unattended `ask` → `deny` demotion check, which sets `CLAUDE_BATCH` back on
for that one run).

Consequence: "the array holds 228 entries" is always wrong, and so is "the
suite reports 227". SPEC.md's and REQUIREMENTS.md's `226 + 2 = 228` figures
are **suite-reported totals**, and are correct read that way; those two
documents are read-only for this phase and are not edited.

### C2: Expectation-case format

Every record is the 3-element form `[expected verdict, label, command]`
(`.claude/rules/hook-tests.md`). The file's own layout conventions — one
record per line, two-space indent, related records grouped and groups
separated by a blank line — are followed by any new record.

### C3: Label convention

Labels are Japanese. A new label carries the `動的目標(rm-unresolvable):`
family prefix already used by the neighbouring records on the same verdict
path, and its remaining text identifies which quoted command-substitution
spelling the record pins (`$()` form vs. backtick form) so the two new
records are distinguishable from each other and from the existing bare-form
pair.

### C4: Additive-only editing

Existing records keep their content, their verdicts and their order. The only
edit permitted to pre-existing text in the case file is the separator comma
that JSON grammar requires after what is currently the final record.

### C5: Version convention

Both version strings move together, by exactly one patch step, to the same
value: `0.1.75` → `0.1.76`. No other plugin's version is touched (the
em-review entry stays at `0.5.9`).

## Cross-task Design Decisions

### D1: One task, not two

The expectation-case append and the version bump are delivered as a single
task. `.claude/rules/core-plugin-version-bump.md` requires the version bump to
be part of the same change as any edit below `<plugin>/`; splitting them would
place a rule-violating intermediate state on the integration branch.
Affected: task0001.

### D2: Expected verdict of the new records is `ask`

The guard classifies an unresolvable recursive-delete target as `ask` with
reason id `rm-unresolvable`. The `deny` observed when running the ticket's
reproduction steps is the unattended demotion of that same `ask` (the guard
demotes `ask` to `deny` when it sees `CLAUDE_BATCH`). The expectation runner
clears `CLAUDE_BATCH` for every stored case, so `ask` is the value the records
must carry — matching the existing records on the same path.
Affected: task0001 (FR6).

### D3: The guard body is read-only

The cause was fixed by the sibling ticket and is already merged; the
reproduction command is already stopped as `rm-unresolvable`. This feature
adds regression coverage and bumps the version, and produces no diff in
`em-workflow/hooks/destructive-guard.py`.
Affected: task0001 (FR5).

### D4: No license action

No dependency is added, and `project.license` is `none`. No license
compatibility check applies and no LICENSE work is in scope.
Affected: task0001.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| The two counts are conflated in a later document, commit or review reply | high | medium | Convention C1 states both numbers and their relationship; VERIFICATION.md restates them at every point a count appears |
| A new record drags an existing `allow` record into a false positive | low | high (a false positive stalls an unattended run on the spot) | Full expectation-suite run is an acceptance criterion (TS-4), not an afterthought |
| A repository-level test pins the case count or the case file's content | low | medium | The repository test suite is run as well as the expectation suite (VERIFICATION.md, Test Verification) |
| JSON escaping error makes the decoded command differ from the ticket form | medium | medium | The criterion is stated on the JSON-**decoded** string, and TS-2 / TS-3 compare decoded values |
| Only one of the two manifests is bumped | low | high (installed caches keep serving stale files) | TS-5 compares both manifests and asserts equality |

## Open Questions

- [ ] FR7 (label readability) has no TS-n scenario; it is verified by the
      manual inspection item M-1 in VERIFICATION.md.
- [ ] NFR1 (standard library only) has no TS-n scenario; no test code is
      written by this feature, so it is verified by inspection item M-2.
- [ ] NFR3 (no new files) has no TS-n scenario; verified by the diff
      inspection item M-3.
- [ ] NFR4 (suitability as distributed content) has no TS-n scenario; it is a
      human-judgment property, verified by inspection item M-4.
