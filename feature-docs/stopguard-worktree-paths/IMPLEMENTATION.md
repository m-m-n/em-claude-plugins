# Implementation Plan: stopguard-worktree-paths

## Overview

Rewire the Stop-hook queue guard (`em-workflow/hooks/queue_stop_guard.py`) so
that enumeration and resolution share exactly one derivation of feature
identity under the integration-worktree layout, add a freshness filter that
drops abandoned integration worktrees, and ship the result as a
version-bumped plugin release.

## Technology Stack

- **Language**: Python 3, standard library only (NFR1). No third-party import
  is added.
- **New dependencies**: none. Nothing to check against `project.license`
  (`none`), and no license line to record — the feature adds no library.
- **Runtime shape**: the hook is a standalone script invoked by absolute path
  on the Stop event. The queue hooks are not a package and share no importable
  module; there is no import edge between them.
- **Test framework**: `unittest`, discovered by
  `python3 -m unittest discover -s tests`. Hook tests drive the script as a
  subprocess with Stop-hook JSON on stdin and assert on exit code and stderr.
- **Release metadata**: two JSON manifests — the plugin manifest and the
  marketplace entry.

## Layer Structure

The hook has three stages with a strictly one-way dependency direction. This
feature changes stages 1 and 2 and leaves stage 3's semantics untouched
(NFR5).

1. **Root resolution** — current working directory to enumeration root.
2. **Active-set enumeration** — enumeration root to an ordered list of
   candidate features, filtered by implement-step state and by freshness.
3. **Decision** — one candidate to block / no-block, including the sidecar
   fingerprint and the consecutive-block cap.

Allowed direction: 1 → 2 → 3. Stage 3 never re-enters stage 1 or 2 and never
rebuilds a path from a root plus a feature name. Stage 2 never reads decision
state. Release metadata sits outside these stages and shares with them only
the requirement to land in the same change.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| Enumeration-root resolver | Locate the worktrees root from the hook's current working directory | pre: none. post: yields the `.claude/worktrees/em-workflow` directory belonging to the nearest ancestor of the current directory (the directory itself included) that contains one; yields "no root" when the walk reaches the filesystem root, when the starting value is empty, or when it is not a usable path. Spawns no process. Never raises to the caller. Same semantics as the ancestor walk already in `queue_taskstop_net.py` (`:149`) | task0001 |
| Enumerated-path decomposition | Single derivation of feature identity and journal directory from one matched `workflow.yaml` path | pre: the path was produced by the layout pattern below. post: yields (feature identity, journal directory) where the journal directory is the ancestor of the matched path that directly contains the integration-worktree directory, and the identity is that same ancestor's own last segment. The `feature-docs/<segment>` wildcard is never read as identity. No join of root plus identity is ever used to produce a path that is later opened | task0001 |
| Enumerated-path ownership filter | Decide, from the matched path alone, whether the derived identity owns that path, and refuse ambiguity | pre: the ordered list of paths the layout pattern produced under one enumeration root. post: the subset whose `feature-docs/<segment>` equals the identity the decomposition derived (ownership), minus every identity carried by two or more surviving matches, which is dropped in full (ambiguity refusal, fail-open). Decided from path strings only: opens nothing, stats nothing, spawns nothing. Compares two segments of the matched path; never reconstructs a path from a root plus a name | task0003 |
| Active-set enumerator | Ordered candidate list | pre: an enumeration root. post: candidate (feature identity, `workflow.yaml` path) pairs, ascending and stable by feature identity, restricted to paths the ownership filter admitted, to features whose implement step reads `in_progress`, and that pass the freshness condition | task0001, task0003 |
| Decision stage | Block / no-block for one candidate | pre: a candidate pair from the enumerator. post: reads the given `workflow.yaml` path verbatim; reaches the journal and sidecar through the decomposition above; all downstream semantics (slot arithmetic, failed-task pass-through, recycled-task-id carve-out, fingerprint, three-block cap) unchanged | task0001 |
| Release version parity | Plugin manifest and marketplace entry carry one identical version string | pre: both currently hold the same value. post: both hold the same new value; no other key in either file changes | task0002 |

## Path Contract (feature-wide)

```
enumeration pattern:
  {worktrees_root}/*/integration/feature-docs/*/workflow.yaml
```

| Artifact | Location |
|---|---|
| Enumeration root (`worktrees_root`) | the `.claude/worktrees/em-workflow` directory of the nearest ancestor of the current working directory that has one |
| Enumerated `workflow.yaml` | `{worktrees_root}/{feature}/integration/feature-docs/{feature}/workflow.yaml` |
| `journal.jsonl` | `{worktrees_root}/{feature}/journal.jsonl` |
| `stop-guard-state.json` | `{worktrees_root}/{feature}/stop-guard-state.json` |

The enumeration root is the `.claude/worktrees/em-workflow` directory itself,
not the ancestor that contains it — this matches the value the existing
reference walk returns, and the two rows below it are expressed relative to
that. The journal and sidecar locations are unchanged by this feature
(assumption a1); only the way they are reached changes.

**Ownership (binding on every enumerated path).** The `{feature}` in the two
wildcard positions of the enumerated location is the SAME name — that is what
SPEC.md's Path Contract states, and it is a condition to be enforced, not an
assumption to be trusted. An integration worktree is a full checkout of its
branch, so it also contains every OTHER feature's `feature-docs/` directory;
the pattern's second wildcard therefore matches paths the derived identity
does not own. A matched path is admitted only when its
`feature-docs/<segment>` equals the identity derived from its worktree-side
segment, and an identity carried by more than one admitted path is dropped in
full. Consequences relied on downstream: one identity maps to at most one
`workflow.yaml`, so the journal and the sidecar under
`{worktrees_root}/{feature}/` have exactly one writer per Stop, and the
"first in-progress feature with refillable work wins" selection ranges over
distinct identities only.

## Conventions

- **Fail-open, without exception (NFR2)**: every abnormal condition resolves
  to a silent exit 0. No code path introduced by this feature may exit 2 for a
  condition that previously exited 0. The reverse direction (a condition that
  used to exit 2 now exiting 0) is acceptable only where a requirement
  explicitly asks for it — the freshness exclusion is the only such case.
- **Undecidable falls to the non-blocking side**: when the freshness inputs
  cannot be read at all, the feature leaves the active set rather than being
  admitted.
- **No process spawning on the Stop path**: the hook must not invoke any
  external command. Zero subprocesses is a hard property, asserted statically.
- **Standard library only**: no import outside the standard library, asserted
  statically.
- **Named constants**: the freshness threshold is a single named
  module-level constant, alongside the existing slot and block-cap constants.
- **Scope containment (NFR5)**: `queue_launch_guard.py`, `queue_failure_net.py`
  and `queue_taskstop_net.py` are not modified by any task in this feature.
- **Release coupling**: because files under `em-workflow/` change, the plugin
  version is bumped in the same change; the reader of the shipped hook is the
  plugin cache, not the repository.

## Cross-task Design Decisions

### D1 — Feature identity is derived exactly once (NFR4, review-blocking)

The matched `workflow.yaml` path is decomposed once into identity and journal
directory, and every later read uses the path (or the ancestor of the path)
that was matched. Nothing downstream reassembles a path from an enumeration
root plus a feature name. This is the exact defect that caused the earlier
revert (827d223 → db91387): enumeration took names from one wildcard while
resolution rebuilt a different path, so the file enumerated and the file read
could differ. Affected: task0001. It is stated here rather than only in the
task plan because the review phase treats it as a blocking invariant.

### D2 — The ancestor walk is duplicated, not factored out

The queue hooks are standalone scripts invoked by path, with no shared
importable module and no package on the path at hook time. Introducing one is
out of scope (NFR5) and would change how every hook is loaded. The walk is
therefore reimplemented in the Stop guard with semantics identical to the
existing reference implementation. Affected: task0001.

### D3 — Freshness policy

A candidate is admitted only if fresh. Freshness reads the journal file's
modification time, falling back to the enumerated `workflow.yaml`'s
modification time when the journal file does not exist. A chosen time more
than the threshold (24 hours) older than the current time excludes the
feature. If neither time can be obtained, the feature is excluded. The check
costs one time-stamp read per candidate in the common case, plus the fallback
read only when the journal file is absent; it adds no directory traversal
(NFR3). Affected: task0001.

### D4 — The flat layout is removed outright, and the fixture migrates with it

Only the integration-worktree layout is enumerated; no second enumeration
path remains. The test fixture must move its `workflow.yaml` into that layout,
keeping the journal and sidecar where they already are. Two consequences the
implementer must plan for: (a) after migration no test may still depend on the
flat layout being enumerated, and (b) creating the integration-worktree
directory chain is also what makes the ancestor walk resolvable from a fixture
root, so fixtures that expect any decision at all must create that chain, and
fixtures that expect "no root at all" must not. Affected: task0001.

### D5 — The release bump is a separate task

The two manifests share no file with the hook change and no contract with it
beyond "same change". Keeping the bump separate keeps the hook task's file set
honest and lets the two run in parallel. It is not optional: without it the
plugin cache keeps serving the old hook (NFR6, assumption a4). Affected:
task0002.

### D6 — Ownership is enforced; ambiguity refusal guards the resulting invariant

Enforcing the Path Contract's segment equality (above) is the mechanism that
keeps one feature's Stop decision out of another feature's journal and
sidecar. Refusing an ambiguous identity — dropping it entirely when two
admitted paths carry it, as `queue_taskstop_net.py` already does for its own
identifier resolution — is a guard on the invariant that equality creates,
not a second mechanism for the same defect: with equality enforced, one
identity cannot be carried twice under one enumeration root. Both are kept,
in that order, so the selection over candidates is an explicit contract
rather than an implicit first-wins. Checking two segments of the path that
was matched is an inspection of an enumerated path, not a reconstruction, so
D1 (single derivation) is untouched. Affected: task0003.

Consequence for D1's automated proxy: the divergent-segment probe can no
longer assert a block, because a divergent layout is now excluded. The
replacement discriminator is two `feature-docs` directories inside ONE
integration worktree, only one of which is owned — reading the unowned one is
observable in the BLOCK line's task ids.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Re-derivation creeps back in on the resolution side (the defect behind the earlier revert) | Medium | High | D1 pinned as a contract; review-blocking invariant; task0003's mixed-worktree probe (two `feature-docs` directories in one integration worktree, only the owned one readable) fails if any read path is rebuilt from root plus name or taken from an unowned match |
| An unowned `workflow.yaml` from another feature in the same integration worktree is evaluated under this feature's identity, journal and sidecar | High (observed in review round 1: 16 raw matches collapsing to one identity) | High | D6 ownership enforcement plus ambiguity refusal; task0003 AC-1 to AC-3 and AC-5 |
| Fixture migration silently removes coverage — the suite goes green because nothing is enumerated any more | Medium | High | TS7 requires every existing test class to keep its intent, and TS1/TS2 assert a positive block under the migrated layout, so an enumeration that yields nothing cannot pass |
| Freshness excludes a genuinely active feature | Low | Low | The failure direction is not blocking, which is the fail-open side; boundary values in tests sit well clear of the threshold |
| Clock-dependent flakiness in the freshness tests | Low | Medium | Test times are set to "now" and "now minus 25 hours"; no assertion sits near the 24-hour boundary |
| Version bump forgotten, so the fix never reaches the plugin cache | Medium | High | Dedicated task, AC9, and a release check in VERIFICATION.md |
| A fixture that expects fail-open accidentally creates the worktrees directory chain and starts resolving a root | Medium | Medium | D4(b) is called out in the task plan; the "no root" case is asserted with an explicitly bare temporary directory |

## Open Questions

- [ ] NFR4 (single derivation of feature identity) has no SPEC test scenario.
      It is verified by code review as a blocking invariant, plus TS10 —
      task0003's ownership scenarios, which subsume the divergent-segment
      probe task0001 added and add the mixed-worktree discriminator (D6).
- [ ] NFR6 (matching version bump) has no SPEC test scenario and no automated
      check in the suite. It is verified by the release check recorded in
      VERIFICATION.md. Adding a manifest-parity unit test would widen the
      declared change set and is deliberately not planned.
