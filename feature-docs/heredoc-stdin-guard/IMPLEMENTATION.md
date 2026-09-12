# Implementation Plan: heredoc-stdin-guard

## Overview

Add a PreToolUse guard to the em-workflow plugin that prepends a stdin cut-off
to a Bash command containing a heredoc, so that a stdin-reading CLI in the same
call cannot block forever on the Claude Code socket. The feature is delivered in
two tasks: **task0001** (merged) landed the guard program, its contract tests,
its registration, the plugin version bump and the version-bump regression
module; **task0002** corrects the one thing task0001 got wrong — the shape of
the object the guard places on standard output — together with the test
assertions that had locked the wrong shape in, the schema-conformance coverage
that would have caught it, and the further version bump the correction requires.

## Technology Stack

- **Language**: Python 3 — the guard program and its tests.
- **Test framework**: the Python standard library's unit-test framework, which
  is already this repository's whole suite (`python3 -m unittest discover -s tests`).
- **Configuration formats**: JSON for the hook registration file and for both
  plugin manifests.
- **New dependencies**: none. Nothing outside the Python 3 standard library is
  imported, by the guard or by either test module (NFR1). This holds for
  task0002 as well: the correction introduces no import that task0001 did not
  already have.
- **License note**: no new dependency is introduced by either task, so there is
  no third-party license to record and no compatibility question to resolve.
  `project.license` is `none` in workflow.yaml, so no project-side license
  constraint applies to this feature either.

## Layer Structure

| Layer | Element | Responsibility | Allowed dependency direction |
|---|---|---|---|
| Guard program | the new hook script under the plugin's hooks directory | Decide, from the event payload alone, whether to rewrite; emit the rewrite in the shape the runtime accepts, or nothing | Depends on nothing else in the repository |
| Registration | the plugin's hook registration file | Name the guard program, its interpreter, its timeout and its position in the PreToolUse Bash array | References the guard program **by path only** |
| Manifest | the plugin manifest and the marketplace manifest | Carry the version that makes the two layers above reach an installed plugin cache | Depends on neither layer above |
| Test | the repository-root test directory | Exercise the guard through its process boundary, check its output against the in-repo hook-output schema fixture, pin the registration shape, and pin the version baseline | Reads the three layers above by path; never imports the guard as a module |

No layer imports another. All coupling is by file path and by the stdin/stdout
event contract. This table is a review and verification reference rather than a
parallelism boundary — see D9 for why this feature never runs two tasks at once.

## Shared Components

These contracts are read from OUTSIDE the task plans as well — by
VERIFICATION.md, by the review perspectives and by the verify phase. They are
stated once here and are not restated in the task plans.

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|---|---|---|---|
| Guard invocation form | How the registration names the guard program | **Pre**: the guard program exists at the plugin's hooks directory under the file name fixed by FR1. **Post**: the registration entry invokes it with the Python 3 interpreter through the plugin-root variable, in the same form the neighbouring Python guards use, with a timeout of 10 seconds and a Japanese status message in the existing style | task0001 |
| PreToolUse decision contract | The stdin/stdout shape the guard honours | **Pre**: standard input carries at most one event object; the guard is given no arguments and no environment it depends on. **Post**: standard output is either empty, or exactly one object whose only top-level member is the hook-specific output; that hook-specific output object carries exactly two members — the event-name member, whose value is the PreToolUse event name, and the updated-input member carrying the updated input mapping. A permission-decision member is never emitted. The exit status is 0 in every path, including every failure path | task0001, task0002 |
| Hook-output schema fixture | The in-repo statement of the shape the runtime requires | **Pre**: none — the fixture is a literal declaration held in the test layer, derived from the runtime's documented PreToolUse hook-output schema and from the A/B measurement recorded in SPEC AC2. It is NEVER read from an installed Claude Code build, so the check runs anywhere. **Post**: the fixture states (a) the required top-level member, (b) the exact required member set of the hook-specific output object, (c) the required value of the event-name member, (d) that the updated-input member is present and carries the expected command. A guard output is conformant only when it satisfies all four | task0002 |
| Rewritten-command shape | What a rewrite produces | **Pre**: the command is a rewrite target per FR2. **Post**: the returned command is the stdin cut-off token `exec < /dev/null`, then a newline, then the original command text byte-for-byte; every other field of the original input mapping is reproduced with its original value and type | task0001, task0002 |
| Plugin version value | The single version string both manifests carry | **Pre**: both manifests read `0.1.73` (the value task0001 left). **Post**: both read `0.1.74`; no other plugin's version in the marketplace manifest moves, and no other field of either file changes | task0002 |
| Version baseline assertion | How the bump is made regression-detectable | **Pre**: the per-feature version-bump module currently pins patch > 72, which the tree already satisfies at `0.1.73`, so nothing in the suite would detect a forgotten second bump. **Post**: the same module pins patch strictly greater than 73 for BOTH manifests and still requires the two values to be identical; its forged pre-bump sample is re-anchored to the value the module must now reject — making the module red on a tree that skipped the second bump and green only after it | task0002 |
| Change-set boundary | Which files the feature may touch | **Post**: nothing outside the em-workflow plugin directory, the repository-root marketplace manifest and the repository-root test directory is modified; the user's global hooks directory is never touched (NFR6) | task0001, task0002 |

## Conventions

- **Naming**: the guard program takes the hyphenated file name fixed by FR1,
  matching the hyphenated naming already used by the neighbouring guards in the
  same directory. The version-bump test module takes the repository's established
  per-feature name shape: the feature name in underscore form with a
  `_version_bump` suffix, under the repository-root test directory.
- **Registration style**: timeouts are expressed in seconds; the entry uses 10,
  matching the guards around it. A short Japanese status message describing what
  is being checked follows the existing entries' style.
- **Output shape policy (feature-wide)**: every object this feature's guard
  places on standard output carries the event-name member inside the
  hook-specific output. The plugin's six pre-existing Bash guards all do this;
  the guard added by this feature is not an exception to the house form. An
  output missing that member is discarded by the runtime, which makes the guard a
  silent no-op rather than a visible failure — so this convention is load-bearing,
  not cosmetic.
- **Error-handling policy (feature-wide): fail open.** Every condition the guard
  cannot resolve — unreadable input, an unexpected payload shape, a command
  string whose structure cannot be settled by static reading, or any unexpected
  internal failure — ends the same way: nothing on standard output, exit status
  0. No failure path exists that stops or delays a tool call, and no failure is
  reported by a non-zero exit status.
- **Logging policy**: none. The guard persists nothing, writes no file, opens no
  network connection, starts no other process, and writes nothing to standard
  error. Its entire observable effect is the single object it may place on
  standard output (NFR2).
- **Test style**: contract tests drive the guard through its process boundary —
  launch it, feed it an event payload, assert on its standard output and exit
  status. No test imports the guard as a module, so the tested surface stays
  identical to the surface Claude Code uses. Manifest assertions parse the JSON
  documents; they never pattern-match the raw file text.
- **Assertion-strictness policy**: an exact member-set assertion over the guard's
  output is kept — it is what pins "no permission decision is ever emitted" — but
  the set it asserts must be the set the runtime requires, and the test layer
  must state that set in one place (the schema fixture) rather than repeating a
  hand-written member list at each call site. An exact-set assertion built from a
  hand-written list is how the original defect stayed green.

## Cross-task Design Decisions

### D1: The guard program, its tests and its registration land in one task

A worktree that registered a hook file it did not contain would present a
registration pointing at a missing script, which this repository's own invariant
checks and registration tests are entitled to reject. Keeping program, tests and
registration together in task0001 made the worktree self-consistent at all
times. Affected: task0001.

### D2: The version bump is folded into the task that changes the plugin

FR9 is part of the task that changes the plugin's content, not a task of its
own. Three reasons:

1. The repository rule `.claude/rules/core-plugin-version-bump.md` requires the
   bump to land in the same change as the plugin content it version-stamps. A
   separate parallel task leaves a window in which the integration branch carries
   a bumped version with no matching content behind it — exactly the
   inconsistency the rule exists to prevent.
2. The manifest file set is disjoint from the rest of the feature's file set, so
   folding adds no merge-conflict risk relative to splitting.
3. A two-line manifest change plus one small assertion adjustment adds negligible
   load, leaving the owning task's acceptance criteria within one implementer
   session.

Applied to task0001 for the first bump, and to task0002 for the second (D12).
Affected: task0001, task0002.

### D3: Tail position in the PreToolUse Bash array

The guard is appended after the existing six entries so that every other guard
still evaluates the original, un-rewritten command text (NFR4). Inserting it
earlier would feed a modified command to the destructive-command and kill
guards, silently changing the input their verdicts are computed from — the one
thing this feature must not do. task0002 does not move it: the position is not
the cause of the defect it corrects. Affected: task0001.

### D4: Rewrite, never deny

The guard's only two outcomes are "one updated-input object" and "nothing". It
never emits a permission decision, so a misdetection can never stop an
unattended run (NFR5); the worst case of a false positive is a command that runs
with its standard input closed. This is what makes an imperfect static reading
of shell text an acceptable basis for the decision. Adding the event-name member
(D10) does not weaken this: the member names the event, it does not grant a
verdict. Affected: task0001, task0002.

### D5: Idempotency is decided from the command text alone

The guard keeps no state between invocations, so "this command was already
rewritten" must be recognisable from the command text itself. The recognition
signal is a stdin redirection standing at the head of the command — which
includes, as one case, the exact cut-off token this guard inserts. That single
rule covers both a previously rewritten command and a command the caller already
wrote with its stdin closed (FR4). Affected: task0001.

### D6: Existing tests that pin the hook array belong to task0001

Where a test already in the repository mechanically encodes the current
PreToolUse Bash entries — their count, their order, or the set of registered
guard scripts — updating that expectation to the seven-entry shape was part of
task0001. task0002 changes neither the array nor its count, so no such file is
in its scope.

### D7: The real-environment confirmation is a verify-phase item, not a task criterion

Confirming that the updated input is actually applied by the running Claude Code
build (SPEC AC1 / AC2, TS-8) requires the guard to be served from the installed
plugin cache, which in turn requires the bumped version and a restart. Neither
is reachable from inside a task worktree. The confirmation is therefore
scheduled as a manual verification item in VERIFICATION.md. D11 draws the
boundary between what this item covers and what is automated. Affected:
task0001, task0002, verify phase.

### D8: A per-feature version-bump module carries the version baseline

The bump has its own regression module,
`tests/test_heredoc_stdin_guard_version_bump.py`, following this repository's
established per-feature convention. A new module rather than reliance on the
existing checks, because the repository-wide parity check pins only a floor far
below the feature's working range and the plugin-invariant script carries no
version check at all. The module asserts the baseline for BOTH manifests and
additionally that the two values are identical — the contract pinned under
Shared Components. It is red on an un-bumped tree and green only after the bump,
which is what makes the bump a test-enforced part of "task complete". D12 states
how task0002 re-anchors its baseline.

**Note on the declared change set**: SPEC.md's File Structure section lists only
the guard contract-test module under the test directory. The version-bump module
is nevertheless admissible, and is recorded here explicitly rather than added
silently: the Declared Change Set is a SUPERSET guard derived at create-plan
from every task's `files` entries in `workflow.yaml`, not from the SPEC's prose
file listing. The module is declared in task0001's file set, so it is inside the
declared set by construction. Affected: task0001, task0002.

### D9: The whole correction is ONE new task, not two or four

The correction has four moving parts — the object the guard emits, the test
assertion that currently pins the wrong member set, the schema-conformance
coverage that was missing, and the version bump that carries all of it into an
installed cache. They land as a single task, task0002. The reasoning, and why
splitting is actively worse here:

1. **Guaranteed merge conflict.** Any split puts the guard contract-test module
   in more than one task's `files`. This plugin's implement phase runs one task
   per worktree per branch, in parallel, with an automatic merge; two tasks
   editing the same module conflict for certain, and the resolution protocol
   (parent-side adoption plus re-implementation) costs far more than the split
   could ever save.
2. **The split has an order dependency the mechanism cannot express.** A
   separate "add schema-conformance coverage" task would depend on the output
   correction having landed first, and task execution order is not guaranteed.
   Run first, that task would be written against the still-broken output — it
   would either be written to pass against the wrong shape, or land red.
3. **There is no parallelism to buy.** The four parts are one coupled unit:
   correct the shape, then verify the corrected shape. Splitting a coupled unit
   across worktrees adds merge risk and ordering risk in exchange for nothing.

Consequence: this feature has exactly two tasks, and they are sequential in
history (task0001 merged, then task0002), never concurrent. Affected: task0002.

### D10: The emitted hook-specific output carries the event-name member

The object the guard places on standard output carries the event-name member
alongside the updated-input member, with the PreToolUse event name as its value
(FR3). This is not a stylistic alignment with the sibling guards — it is what
makes the guard's single externally observable effect survive:

- The runtime's hook-output validator rejects a hook-specific output that omits
  the event-name member, and its sanitizer discards the whole hook-specific
  output when that member's value is not the event name of the event being
  handled. A rejected or discarded output means the updated input is never
  applied, so the guard silently does nothing while every unit test still passes.
- No permission-decision member is added alongside it. Emitting an allow verdict
  would auto-approve every command containing a heredoc and would override the
  verdicts of the guards ahead of it in the array (D3, D4) — a far worse outcome
  than the defect being corrected.

Affected: task0002.

### D11: Schema conformance is automated; runtime acceptance stays manual

The failure this feature just suffered lives exactly on the boundary between
"the script printed this object" and "the runtime accepted this object". Every
test that existed stopped on the near side of that boundary. The boundary is
therefore split deliberately rather than left implicit:

- **Automated (task0002)**: the guard's parsed standard output is checked
  against the in-repo hook-output schema fixture pinned under Shared Components.
  This is deterministic, runs in any worktree, and is where a future regression
  of exactly this kind gets caught.
- **Manual (verify phase, VERIFICATION.md TS-8)**: that the running Claude Code
  build actually applies the updated input. The guard runs on a code path the
  runtime itself drives; reproducing that path from a test process is not
  tractable, so this stays a human-run scenario with a recorded observation.

The corollary is a constraint on the automated half: **the schema fixture must
not be read from an installed Claude Code build.** Deriving the expected shape
by inspecting a binary would make the test depend on a specific installed
version, on that version being present at all, and on a private file layout —
all three of which make the check non-deterministic and non-portable. The
fixture is a literal in-repo declaration, and the runtime's actual behaviour is
confirmed once, by hand, through TS-8. Affected: task0002, verify phase.

### D12: The version baseline is re-anchored to 73, and the tree moves to 0.1.74

task0001 moved both manifests to `0.1.73` and set the per-feature module's
baseline so that anything at or below `0.1.72` fails. task0002 changes plugin
content again — the guard program itself — so
`.claude/rules/core-plugin-version-bump.md` requires another bump in the same
change, and an installed cache that keeps serving `0.1.73` would keep serving
the broken guard. Therefore:

- Both manifests move to `0.1.74`, together, as the single value pinned under
  Shared Components.
- The per-feature version-bump module's baseline is raised so that anything at
  or below `0.1.73` fails, and its forged pre-bump sample is re-anchored to the
  value the module must now reject. Left at the old baseline, the module would be
  green on a tree that skipped the second bump — which is precisely the failure
  the module exists to prevent. Only the baseline and the forged sample move; the
  module's structure, its equality matcher, its negative proofs and its
  non-vacuity guards are kept as they are.

**Deviation from SPEC FR9, recorded rather than silent**: FR9 and SPEC AC10 name
the concrete pair `0.1.72 → 0.1.73`. That literal described the single bump the
feature was expected to need when it was written; a second corrective change to
the same plugin makes a second bump mandatory under the repository rule. FR9's
requirement — both manifests carry the same, newly bumped em-workflow version,
one patch step past the value the tree held before the change — is satisfied by
`0.1.74`; only the literal in the SPEC is stale. This is carried as an open
question below rather than being treated as settled.

**Note on task0001's historical plan**: task0001 is merged and its plan file is
kept verbatim as the record of what was implemented, so its acceptance criteria
still name `0.1.73` and the old baseline. Those criteria were true at task0001's
merge point; task0002 re-anchors them. The current expected values are the ones
in this document's Shared Components table and in VERIFICATION.md, not the ones
in the merged task's historical plan. Affected: task0002.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| The running Claude Code build still does not apply the returned updated input after the shape correction | Low | High | The corrected shape was confirmed by an A/B measurement against the running build (SPEC AC2); TS-8 re-runs that confirmation end to end, and a negative result routes to rework rather than to an unplanned redesign |
| A future change re-introduces an output shape the runtime rejects | Medium | High | D11's automated schema-conformance check, plus the assertion-strictness convention that forbids a hand-written member list at the call site |
| **Now that the rewrite is actually applied, the permission layer and the auto-mode classifier see the rewritten command text, so an allow rule keyed on the original command prefix no longer matches** | Medium | High | Newly live risk: until the correction, the rewrite was discarded, so nothing downstream ever saw a rewritten command. A prefix-keyed allow rule that stops matching falls through to a confirmation, and in an unattended run a confirmation nobody can answer re-introduces the same class of stall this feature exists to remove. Verified as a manual observation item (VERIFICATION.md TS-16) during the same real-environment run as TS-8; a positive finding is reported as a new issue rather than absorbed into this feature |
| Static reading of shell text misjudges quoting, a here-string, or a heredoc body, and over-detects | Medium | Low | D4 bounds the blast radius to a closed standard input; the test corpus covers the here-string form, operators inside quoted text, and commands with no heredoc at all |
| Static reading under-detects and the original hang survives | Low | High | The detection condition is deliberately permissive (any unquoted heredoc operator), and the manual verification item exercises the original reproduction procedure end to end |
| The installed plugin cache keeps serving the pre-correction version, so the corrected guard never runs | Medium | High | The second version bump is inside task0002 (D2, D12); the completion report states that a Claude Code restart is required for the change to take effect |
| The second bump is forgotten, or lands in only one of the two manifests | Low | High | D12's re-anchored baseline is red on a tree that skipped it and asserts both manifests carry an identical, past-baseline value |
| The corrected assertion is written loosely (membership instead of exact set) and stops pinning "never denies" | Low | Medium | The assertion-strictness convention keeps an exact member-set assertion; the set comes from the schema fixture, and the explicit "no permission-decision member" assertion is kept alongside it |
| A command that legitimately consumes the tool call's standard input is rewritten | Low | Low | No such consumer exists in this workflow: the tool call's standard input is the Claude Code socket, which nothing in a Bash command is meant to read |

## Open Questions

- [ ] SPEC FR9 and AC10 name the literal pair `0.1.72 → 0.1.73`, while the
      correction requires `0.1.73 → 0.1.74` (D12). The requirement's substance is
      met; the SPEC's literal is stale. Whether to correct the SPEC literal is
      left to the verify/retrospect phase rather than being decided here.
- [ ] The manual confirmation of SPEC AC1 / AC2 (TS-8) needs an environment where
      the stdin-reading CLI named in the SPEC is available (SPEC A7) and where the
      plugin cache has been refreshed to the bumped version. If that environment
      is not available at verify time, the item stays open rather than being
      marked passed.
- [ ] The downstream permission-matching effect (TS-16) is an observation item,
      not a planned change. If the observation is positive, the remedy is out of
      this feature's declared scope and belongs to a separate issue.
