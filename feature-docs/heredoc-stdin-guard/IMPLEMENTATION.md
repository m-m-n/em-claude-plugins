# Implementation Plan: heredoc-stdin-guard

## Overview

Add a PreToolUse guard to the em-workflow plugin that prepends a stdin cut-off
to a Bash command containing a heredoc, so that a stdin-reading CLI in the same
call cannot block forever on the Claude Code socket. The feature is delivered as
exactly ONE task (task0001): the guard program, its contract tests, its
registration, the plugin version bump that makes the change reach an installed
cache, and the version-bump regression module that detects a forgotten bump.

## Technology Stack

- **Language**: Python 3 — the guard program and its tests.
- **Test framework**: the Python standard library's unit-test framework, which
  is already this repository's whole suite (`python3 -m unittest discover -s tests`).
- **Configuration formats**: JSON for the hook registration file and for both
  plugin manifests.
- **New dependencies**: none. Nothing outside the Python 3 standard library is
  imported, by the guard or by either test module (NFR1).
- **License note**: no new dependency is introduced, so there is no third-party
  license to record and no compatibility question to resolve. `project.license`
  is `none` in workflow.yaml, so no project-side license constraint applies to
  this feature either.

## Layer Structure

| Layer | Element | Responsibility | Allowed dependency direction |
|---|---|---|---|
| Guard program | the new hook script under the plugin's hooks directory | Decide, from the event payload alone, whether to rewrite; emit the rewrite or nothing | Depends on nothing else in the repository |
| Registration | the plugin's hook registration file | Name the guard program, its interpreter, its timeout and its position in the PreToolUse Bash array | References the guard program **by path only** |
| Manifest | the plugin manifest and the marketplace manifest | Carry the version that makes the two layers above reach an installed plugin cache | Depends on neither layer above |
| Test | the repository-root test directory | Exercise the guard through its process boundary, pin the registration shape, and pin the version baseline | Reads the three layers above by path; never imports the guard as a module |

No layer imports another. All coupling is by file path and by the stdin/stdout
event contract. Because the feature is a single task, this table is a review and
verification reference rather than a parallelism boundary.

## Shared Components

With one task, this table pins the contracts that are read from OUTSIDE the task
plan as well — by VERIFICATION.md, by the review perspectives and by the verify
phase. They are stated once here and are not restated in the task plan.

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|---|---|---|---|
| Guard invocation form | How the registration names the guard program | **Pre**: the guard program exists at the plugin's hooks directory under the file name fixed by FR1. **Post**: the registration entry invokes it with the Python 3 interpreter through the plugin-root variable, in the same form the neighbouring Python guards use, with a timeout of 10 seconds and a Japanese status message in the existing style | task0001 |
| PreToolUse decision contract | The stdin/stdout shape the guard honours | **Pre**: standard input carries at most one event object; the guard is given no arguments and no environment it depends on. **Post**: standard output is either empty or exactly one object whose only member is the hook-specific output carrying the updated input mapping; a permission decision field is never emitted; the exit status is 0 in every path, including every failure path | task0001 |
| Rewritten-command shape | What a rewrite produces | **Pre**: the command is a rewrite target per FR2. **Post**: the returned command is the stdin cut-off token `exec < /dev/null`, then a newline, then the original command text byte-for-byte; every other field of the original input mapping is reproduced with its original value and type | task0001 |
| Plugin version value | The single version string both manifests carry | **Pre**: both manifests currently read `0.1.72`. **Post**: both read `0.1.73`; no other plugin's version in the marketplace manifest moves, and no other field of either file changes | task0001 |
| Version baseline assertion | How the bump is made regression-detectable | **Pre**: the repository's existing parity check pins a floor of `0.1.50` and the newest per-feature module pins patch > 71, so an un-bumped `0.1.72` tree is green under both. **Post**: a new per-feature module asserts, for BOTH manifests, that the em-workflow version is of the form `0.1.<patch>` with patch strictly greater than 72, and that the two values are identical — making the module red on the un-bumped tree and green only after the bump | task0001 |
| Change-set boundary | Which files the feature may touch | **Post**: nothing outside the em-workflow plugin directory, the repository-root marketplace manifest and the repository-root test directory is modified; the user's global hooks directory is never touched (NFR6) | task0001 |

## Conventions

- **Naming**: the guard program takes the hyphenated file name fixed by FR1,
  matching the hyphenated naming already used by the neighbouring guards in the
  same directory. The version-bump test module takes the repository's established
  per-feature name shape: the feature name in underscore form with a
  `_version_bump` suffix, under the repository-root test directory.
- **Registration style**: timeouts are expressed in seconds; the new entry uses
  10, matching the guards around it. A short Japanese status message describing
  what is being checked follows the existing entries' style.
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

## Cross-task Design Decisions

### D1: The guard program, its tests and its registration land in one task

A worktree that registered a hook file it did not contain would present a
registration pointing at a missing script, which this repository's own invariant
checks and registration tests are entitled to reject. Keeping program, tests and
registration together in task0001 makes the worktree self-consistent at all
times. Affected: task0001.

### D2: The version bump is folded into task0001, not split into a second task

FR9 (both manifests, `0.1.72` → `0.1.73`) is part of task0001 rather than a
task of its own. Three reasons:

1. The repository rule `.claude/rules/core-plugin-version-bump.md` requires the
   bump to land in the same change as the plugin content it version-stamps. A
   separate parallel task leaves a window in which the integration branch carries
   a bumped version with no hook behind it — exactly the inconsistency the rule
   exists to prevent.
2. The two file sets are disjoint (the manifests are touched by nothing else in
   this feature), so folding adds no merge-conflict risk relative to splitting.
3. A two-line manifest change plus one small assertion module adds negligible
   load to task0001, whose acceptance criteria stay within one implementer
   session.

Consequence: this feature has exactly one task. There is no task0002.
Affected: task0001.

### D3: Tail position in the PreToolUse Bash array

The guard is appended after the existing six entries so that every other guard
still evaluates the original, un-rewritten command text (NFR4). Inserting it
earlier would feed a modified command to the destructive-command and kill
guards, silently changing the input their verdicts are computed from — the one
thing this feature must not do. Affected: task0001.

### D4: Rewrite, never deny

The guard's only two outcomes are "one updated-input object" and "nothing". It
never emits a permission decision, so a misdetection can never stop an
unattended run (NFR5); the worst case of a false positive is a command that runs
with its standard input closed. This is what makes an imperfect static reading
of shell text an acceptable basis for the decision. Affected: task0001.

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
guard scripts — updating that expectation to the new seven-entry shape is part
of task0001, not a deviation and not a separate task. Those candidate files are
declared in task0001's file set with an explicit "only if it pins the array"
condition, so leaving an untouched file untouched is equally correct.

### D7: The real-environment confirmation is a verify-phase item, not a task criterion

Confirming that the updated input is actually applied by the running Claude Code
build (SPEC AC1 / AC2) requires the guard to be served from the installed plugin
cache, which in turn requires the bumped version and a restart. Neither is
reachable from inside a task worktree. The confirmation is therefore scheduled
as a manual verification item in VERIFICATION.md, together with the fallback
SPEC A4 already allows (adjust the output shape or the array position) should it
fail. Affected: task0001, verify phase.

### D8: A per-feature version-bump test module raises the version baseline

The bump gets its own regression module, `tests/test_heredoc_stdin_guard_version_bump.py`,
following this repository's established per-feature convention — sixteen such
modules already exist. The reason a new module is needed rather than relying on
the existing checks:

- The repository-wide parity check pins a floor of `0.1.50`, and the newest
  per-feature module pins patch > 71. An un-bumped `0.1.72` tree is green under
  both, so nothing in the current suite detects a forgotten bump for this
  feature.
- The plugin-invariant script carries no version check at all.

The new module therefore raises the baseline to patch > 72 for BOTH manifests
and additionally asserts the two values are identical — the contract pinned under
Shared Components. It is red on the un-bumped tree and green only after the bump,
which is what makes the bump a test-enforced part of "task complete".

**Note on the declared change set**: SPEC.md's File Structure section lists only
`tests/test_heredoc_stdin_guard.py` under the test directory. Adding a second
test module is nevertheless admissible, and is recorded here explicitly rather
than added silently: the Declared Change Set is a SUPERSET guard derived at
create-plan from every task's `files` entries in `workflow.yaml`, not from the
SPEC's prose file listing. The new module is declared in task0001's file set, so
it is inside the declared set by construction. Affected: task0001.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| The running Claude Code build does not apply the returned updated input | Medium | High | Manual verification item in VERIFICATION.md; SPEC A4's fallback (adjust output shape or array position) is pre-authorised, so a negative result routes to rework rather than to an unplanned redesign |
| Static reading of shell text misjudges quoting, a here-string, or a heredoc body, and over-detects | Medium | Low | D4 bounds the blast radius to a closed standard input; the test corpus covers the here-string form, operators inside quoted text, and commands with no heredoc at all |
| Static reading under-detects and the original hang survives | Low | High | The detection condition is deliberately permissive (any unquoted heredoc operator), and the manual verification item exercises the original reproduction procedure end to end |
| An existing test pins the six-entry Bash array and breaks on the seventh entry | Medium | Low | D6; the candidate files are declared in task0001's file set |
| The installed plugin cache keeps serving the pre-change version, so the guard never runs | Medium | High | The version bump is inside task0001 (D2); the completion report states that a Claude Code restart is required for the change to take effect |
| The bump is forgotten, or lands in only one of the two manifests | Low | High | D8's version-bump module is red on the un-bumped tree and asserts both manifests carry an identical, past-baseline value |
| A command that legitimately consumes the tool call's standard input is rewritten | Low | Low | No such consumer exists in this workflow: the tool call's standard input is the Claude Code socket, which nothing in a Bash command is meant to read |

## Open Questions

- [ ] The manual confirmation of SPEC AC1 / AC2 needs an environment where the
      codex CLI is available (SPEC A7) and where the plugin cache has been
      refreshed to the bumped version. If that environment is not available at
      verify time, the item stays open rather than being marked passed.
