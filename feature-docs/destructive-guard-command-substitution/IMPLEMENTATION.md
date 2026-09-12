# Implementation Plan: destructive-guard-command-substitution

## Overview

Close the `allow` path in the PreToolUse destructive guard where a recursive
delete whose target word is built solely from a command substitution loses
that target at the lexing boundary, and raise the em-workflow plugin version
so the fixed hook actually reaches installed caches. Two tasks, disjoint file
sets, fully parallel.

## Technology Stack

- **Language**: Python 3, standard library only. The hook already imports
  `json` / `os` / `re` / `shlex` / `shutil` / `sys`; nothing outside the
  standard library is added.
- **Test framework**: `unittest` from the standard library, run through
  `python3 -m unittest discover -s tests` (`test/README.md`), plus the
  feature-local expectation runner over the guard's case table.
- **New dependencies**: none. No third-party package enters the project, so
  no new license enters it either. `project.license` is `none`, so no
  compatibility constraint applies and nothing in this feature changes it;
  the LICENSE file is not touched.

## Layer Structure

The guard is a one-way pipeline; no stage re-enters an earlier one, and this
feature adds no stage and reorders none.

1. **Payload intake** — read the PreToolUse JSON on standard input; a
   malformed payload fails open (no decision, exit 0).
2. **Statement extraction (the lexing boundary)** — strip here-doc bodies,
   mark command substitutions, tokenize into statements, then convert marker
   residue into per-token flags. This is the only stage task0001 changes on
   the input side.
3. **Per-command checks** — recursive delete, git, file destruction,
   self-modification, external/irreversible operations, bypass flags,
   permissions. Task0001 changes only the recursive-delete check and the text
   it produces.
4. **Cross-target/cross-segment selection** — the strongest tier across every
   target of every statement wins; unchanged.
5. **Emission** — one decision on standard output, `ask` demoted to `deny`
   in an unattended run, exit 0; unchanged.

Alongside the pipeline sits the **distribution layer**: the two plugin
manifests whose version value gates whether an installed cache picks up the
changed hook at all. Task0002 owns that layer and touches no pipeline stage.

## Shared Components

No source-code component is shared between the two tasks — their file sets
are disjoint. The two surfaces below are the only cross-task contracts, and
both are pinned here rather than in either task plan.

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| Repository-root unit-test suite (`tests/`) | Holds every repository-level regression module for this feature | Pre: each task adds its own module, named for this feature (`test_destructive_guard_command_substitution.py`, `test_destructive_guard_command_substitution_version_bump.py`); a module imports no third-party package, imports no sibling test module, and never touches real `~/.claude` state; a hook is exercised through its external contract (subprocess, PreToolUse JSON on standard input), a manifest is parsed as JSON rather than pattern-matched. Post: one `python3 -m unittest discover -s tests` run discovers both modules and is green with both present. | task0001, task0002 |
| em-workflow plugin version (one value, two manifests) | Identifies the release that carries this fix | Pre: both manifests read the same pre-change value. Post: both read one identical string of the form `0.1.<patch>` with patch strictly greater than the pre-change patch (74), no other plugin's version moves, and every other field of both files is byte-identical. Task0002 is the ONLY writer of either manifest; task0001 must not edit them. | task0001 (boundary only), task0002 |

## Conventions

- **Verdict vocabulary**: tiers are `deny` / `ask` / `allow`; `ask` is demoted
  to `deny` in an unattended run by the existing demotion. This feature
  introduces no new rule id — every verdict it produces carries an existing
  one.
- **Reason text**: Japanese, the existing sentence style, prefixed with the
  rule id, and always ending in a concrete instruction the reading agent can
  act on to rewrite the command (NFR5). The offending delete target is named
  in the text and is never empty or whitespace only.
- **Sentinel containment**: the internal marker used inside the lexing
  boundary never appears in the reason text or anywhere else on standard
  output (NFR6).
- **Filesystem-free decision**: no path resolution against the real
  filesystem, no process spawning, is added to the decision path (NFR2); the
  verdict stays deterministic for a given command string (NFR1).
- **Case-table discipline** (`.claude/rules/hook-tests.md`): entries are
  `[expected verdict, label, command]`; the detection half and the
  false-positive half carry equal weight; no existing entry is ever deleted,
  and an expectation is changed only where this document records the decision
  to change it.
- **Version bump** (`.claude/rules/core-plugin-version-bump.md`): a change
  under `em-workflow/` raises the version in both manifests to the same value
  in the same change; a behaviour fix is a patch step. Report to the user
  that a Claude Code restart is required for the new version to take effect.

## Cross-task Design Decisions

### D1: Task split — behaviour vs distribution

The feature splits into exactly two tasks along the pipeline/distribution
line: task0001 owns the guard source, its case table and its regression
module; task0002 owns the two manifests and the version-bump module. Their
`files` sets do not intersect, so both run fully in parallel with no ordering
and no merge conflict. The split is deliberate rather than incidental — the
version bump is a mechanical, low-complexity edit whose own regression module
must be able to go red on its own, independent of whether the behaviour fix
landed.

### D2: Version value and ownership

The target value is the next patch above what both manifests currently read
(`0.1.74`), i.e. `0.1.75`. The version-bump module's baseline is expressed as
"strictly greater than patch 74" rather than as a fixed literal, so an
unrelated bump landing first does not make it stale, while a tree that skipped
this bump still fails. Only task0002 writes either manifest.

### D3: No new dependency, no license movement

Every requirement is satisfied within the standard library already imported by
the hook and by the test runner. No dependency is added, so no license
compatibility question arises; `project.license` stays `none` and is listed in
the workflow patch's preserve set.

### D4: Feature-level behavioural contract (implemented by task0001, asserted by VERIFICATION.md)

Recorded here because the verification plan and both test suites are written
against it, not because two tasks implement it.

- A recursive delete whose target word consists ENTIRELY of a command
  substitution reaches the decision as a target and is judged `ask` under the
  existing `rm-unresolvable` rule id — the same treatment the other
  statically-unresolvable delete target, a variable expansion, already gets
  (FR2). In an unattended run the existing demotion turns that into `deny`, so
  the attack scenario is closed in both modes.
- The `$( )` spelling and the backtick spelling are indistinguishable in the
  outcome: same tier, same rule id, same rendered target (FR1).
- The double-quoted whole-word form (`rm -rf "$(cat list)"`) is the same shape
  once quoting is resolved and therefore takes the same route, moving from
  today's `deny` to `ask`. FR4 sanctions either tier for it and requires only
  that its rendered target stop being whitespace; treating it identically to
  the bare form is chosen over a quoted/unquoted special case because the
  distinction has no bearing on how resolvable the target is. Its case-table
  entry is retained with an updated expectation and a rewritten label — it is
  not removed. Protection in unattended runs is unchanged, since `ask` demotes
  to `deny` there.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| The lexing-boundary change affects the token stream of EVERY command, not just deletes, producing false positives that stall unattended runs | Medium | High | The whole `allow` half of the case table is retained unchanged and re-run; task0001's regression module covers the non-delete positions a substitution can occupy (command word, redirect destination, copy/link/sync destination, here-doc body, quoted data, shell payload) |
| An attended session loses today's `deny` on the quoted whole-word form | High (it is the planned outcome, D4) | Medium | The tier still blocks execution without a human answer, and demotes to `deny` unattended; the case-table entry is kept with the new expectation so the change is visible rather than silent |
| The stand-in text for a lost target leaks the internal sentinel, or is shaped like a real path, flag or redirect operator | Low | High | Task0001 pins the required properties of that rendering and asserts on the complete standard-output text |
| A nested substitution silently regresses from `deny` to `allow` | Low | High | Pinned as an edge-case scenario (TS-3) with its own case-table entry |
| The version bump is skipped, so installed caches keep serving the vulnerable hook | Medium | High | Task0002's module fails on any tree that still reads the pre-change patch, and runs in the same discovery pass as everything else |

## Open Questions

- [ ] The concrete version string assumes both manifests still read `0.1.74`
      when task0002 runs. If an unrelated bump lands first, task0002 takes the
      next patch above whatever both manifests then read; the "strictly
      greater than 74" baseline stays correct either way.
