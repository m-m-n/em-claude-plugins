# Implementation Plan: failed-run-cleanup-guard

## Overview

One new PreToolUse(Bash) guard script denies cleanup commands aimed at
em-workflow runs that ended in failure, is registered into the plugin's
existing Bash guard chain, and is protected from being overridden by
destructive-guard's blanket allow. Only cross-task decisions live here;
per-task detail lives in `tasks/taskNNNN.md`.

## Technology Stack

- **Language**: Python 3, standard library, matching every existing hook in
  `em-workflow/hooks/`.
- **YAML parsing**: PyYAML, used through its safe loading entry point. This
  is NOT a new dependency — it is already a runtime dependency of this
  plugin (`em-workflow/scripts/check-plugin-invariants.py` and
  `em-workflow/scripts/validate-worker-output.py` both require it), so no
  new third-party package enters the project with this feature.
- **License**: no new dependency is introduced, therefore no new license
  obligation arises. `project.license` is `none`, so no compatibility
  constraint applies to this feature; recorded here for the license review
  perspective.
- **Tests**: `unittest` from the standard library only (test code never
  imports a third-party package), driving hook scripts as subprocesses with
  a JSON payload on stdin.

## Layer Structure

| Layer | Responsibility | Depends on |
|---|---|---|
| Registration (`em-workflow/hooks/hooks.json`) | Declares which scripts run for which tool event, and in which order — array order IS execution order within one matcher group | the guard scripts (by filename) |
| Guard scripts (`em-workflow/hooks/*.py`) | Reach one permission decision from the payload plus static, read-only inspection | nothing inside this repository |
| Test layer (`tests/`, `em-workflow/hooks/tests/`) | Drives the scripts as subprocesses and pins registration invariants | registration + guard scripts |

Allowed dependency direction is downward only. Guard scripts never import
each other: `em-workflow/hooks/` has no shared module today, and the
established pattern in this repository is that a small primitive needed by
several hooks is duplicated per hook and pinned by a test that compares the
copies (see the task-assignment header regex shared by three queue hooks).
This feature introduces no shared module either.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| Bash guard chain order | Fixes the execution order of the PreToolUse Bash matcher group | After this feature the group declares exactly, in this order: gitleaks-precommit.sh, kill-guard.py, bash_guard.py, failed-run-cleanup-guard.py, destructive-guard.py. Precondition: one single matcher group for Bash. Postcondition: destructive-guard.py remains last, and the new guard runs after bash_guard.py and before destructive-guard.py | task0001 (declares it in the manifest and in the order-pinning test), task0002 (documents it) |
| New guard identity | The one filename and registration form every other artifact refers to | Script path is `em-workflow/hooks/failed-run-cleanup-guard.py`; its registration entry is of type command, invokes the script with the `python3` interpreter through the plugin-root-relative form the other Python hooks use, and declares a timeout of 15 seconds (the repository's standard hook timeout, inside the 10-15 second band NFR3 requires). Postcondition: the registration passes the repository's manifest-shape checks without adding an exception entry to the per-script timeout table | task0001 (creates + registers), task0002 (names it in the plugin README) |
| Target invocation shapes (S1/S2/S3) | The single vocabulary of command shapes this feature reasons about | S1: a `git` invocation whose subcommand is `worktree` with the `remove` operation. S2: a `git` invocation whose subcommand is `branch` carrying a non-force delete flag (short `-d` or long `--delete`; the force spelling is already denied by destructive-guard's own branch rule). S3: a `gh` invocation with the `pr create` subcommand pair. Postcondition (INVARIANT): the set of commands for which destructive-guard withholds its blanket allow is a SUPERSET of the set of commands on which the new guard can emit a decision | task0001 (classifier), task0003 (deferral) |
| Decision output contract | The wire shape every decision this feature emits uses | On deny/ask: a single JSON object on stdout carrying the PreToolUse hook-specific output block (event name, permission decision, permission decision reason), then exit 0. On no decision: nothing on stdout, exit 0. The reason string is Japanese prose prefixed with a bracketed hook tag in the existing style used by kill-guard and destructive-guard. An `ask` is demoted to `deny` when the unattended-run environment variable is set to anything other than its "off" spellings (empty, `0`, `false`, `no`) | task0001 |
| Plugin version value | The single value both registries carry after this feature | `0.1.58` (patch step from `0.1.57`), written identically to the plugin manifest and to the em-workflow entry of the marketplace manifest, the latter selected by entry name and never by array position | task0002 |
| Guard parity vocabulary | The two lists both guards must interpret identically, so the superset invariant above cannot drift | Grouping constructs: subshell, brace group, a function body defined and invoked within the same command, command substitution, and an inline interpreter string — in each, the invocation one level in is the statement's real head, not the grouping token. Unresolvable markers: the one character set that makes an operand statically unresolvable, identical on both sides, glob spellings included. Postcondition: the pairing is asserted by an executable check over a fixed command corpus (D7), never by a comment | task0001 (its classifier defines the vocabulary), task0003 (its deferral consumed it), task0004 (restores the pairing and pins it) |

## Conventions

- **Naming**: the guard script is named for what it protects, hyphenated,
  matching the neighbouring `kill-guard.py` / `destructive-guard.py`
  spelling. Its unit-test module is `tests/test_failed_run_cleanup_guard.py`
  (underscored, per the test directory's own naming rule).
- **Decision discipline**: this feature's new guard NEVER emits `allow`.
  Every path that is not a deny or an ask produces no output and exit 0.
- **Error-handling policy — fail-open everywhere**: a payload that cannot be
  interpreted, a missing or unparsable `workflow.yaml`, an unavailable YAML
  parser, or any unexpected internal error all resolve to "no decision, exit
  0". Blocking on broken input is out of the hooks' responsibility, matching
  the existing hooks' discipline.
- **Reason language**: decision reason text is Japanese; source comments and
  docstrings are English, as in the surrounding hook sources.
- **Untrusted input**: `workflow.yaml` is read-only data. Only structured
  field values are consumed; no natural-language content in it ever selects
  a behaviour, and no value from it is ever executed or interpolated into a
  command.
- **Test placement (NFR6)**: every file under `em-workflow/` is distributed
  to user environments, so NEW test code lives in the repository-root
  `tests/` directory. The pre-existing expectation suite under
  `em-workflow/hooks/tests/` is extended with case DATA rows only; no new
  test program is added there.
- **Existing expectation rows are never deleted**: the destructive-guard
  case list only grows.

## Cross-task Design Decisions

### D1 — The new guard is registered between bash_guard and destructive-guard

destructive-guard emits a blanket allow for anything its blocklist does not
match, and an allow ends the permission decision for that call, which is why
it must stay last in the group. The new guard is therefore inserted as the
fourth of five entries. The order is not merely a convention: it is asserted
verbatim by an existing repository test, so the task that edits the manifest
also updates that test's expected order list in the same change.

Affected tasks: task0001 (manifest + order test), task0002 (README order
sentence and guard table).

### D2 — destructive-guard withholds its blanket allow for S1/S2/S3

The existing mechanism for "another hook owns this verdict" is the kill-word
deferral: the destructive checks still run, but the trailing blanket allow is
suppressed so the other hook's deny survives. The same mechanism is extended
to the three shapes above.

Two properties are required of the deferral, and they pull in opposite
directions:

1. **Superset** — every command the new guard could decide on must suppress
   the blanket allow, or the deny it produces can be cancelled.
2. **Narrowness** — a suppressed allow does not deny anything; it hands the
   command back to Claude Code's auto mode classifier, whose false-positive
   rate is the very cost this plugin's blanket allow exists to avoid
   (NFR1). Every command needlessly suppressed is a small tax on unattended
   runs.

Resolution: the deferral fires on REAL invocations of S1/S2/S3, judged on
the same quote-aware statement/token decomposition destructive-guard already
performs for its own checks — not on a raw substring scan of the command
text. A mention inside quotes, a here-document body, or a commit message
therefore keeps its blanket allow, exactly as the new guard itself stays
silent for those. The superset property still holds because the new guard
only ever decides on real invocations.

Affected tasks: task0003 (implements the deferral and its expectation rows),
task0001 (its classifier must not decide on anything outside S1/S2/S3).

### D3 — Failure determination parses structure, never scans text

The determination is "does the target feature's `workflow.yaml` contain at
least one entry of the top-level workflow step sequence whose status value is
`failed`". Two constraints follow, and both are mandatory:

- **Structured parsing only.** A substring scan for the literal phrase is
  forbidden. The `goal` block of a `workflow.yaml` carries free user text and
  legitimately quotes that very phrase — this feature's own `workflow.yaml`
  does — so a text scan would deny cleanup of a perfectly healthy run. That
  is precisely the false positive NFR1 weighs as heavily as a miss.
- **Only the top-level step sequence counts.** Per-task status values (which
  have their own `failed` spelling) are out of scope for this feature; so are
  `needs_update`, `pending` and `in_progress` at any level.

Affected tasks: task0001 (implements it), task0003 (its added expectation
rows must not depend on any parsing behaviour of the new guard).

### D4 — Fail-open when the parser is unavailable

If the YAML parser cannot be imported at all, the guard emits no decision.
The consequence is explicit and accepted: on a machine without that parser
the protection is silently absent rather than blocking every cleanup. This
follows the same "broken input is not this hook's problem" rule as FR10, and
keeps a missing dependency from freezing an unattended run.

Affected tasks: task0001.

### D5 — Version step

Both registries move from `0.1.57` to `0.1.58`. A patch step is what every
comparable hook addition in this repository has used, and the repository's
version-parity test only requires the two registries to agree and to compare
strictly greater than the recorded baseline.

Affected tasks: task0002.

### D6 — Static-only evaluation

The guard starts no external process, writes nothing, and mutates no state.
Its only file access is: bounded, read-only path/existence checks needed to
locate the target worktree, plus at most ONE `workflow.yaml` read per
evaluated command.

Affected tasks: task0001.

### D7 — The superset invariant is pinned by a parity check, not by prose

D2's superset property is a relation between two independently written
scripts, and the layer structure above deliberately keeps them from sharing
code. A relation stated only in prose drifts the first time one side is
narrowed without the other: that is exactly what the first review round
found, in both directions at once.

The relation is therefore given one executable owner: a check that feeds one
fixed corpus of command strings to BOTH guards and asserts, per member,
that whenever the new guard emits a decision the destructive guard emits no
allow — plus the narrowness converse, that a mention or a near miss keeps its
blanket allow. The corpus is data, so a newly discovered shape is added as a
row rather than as new assertion code, and it lives in the repository-root
test directory per the NFR6 convention above.

Two consequences bind future changes to either script:

- The Guard parity vocabulary row above is the shared contract. A grouping
  construct or an unresolvable marker recognized by one guard is recognized
  by the other; neither list is extended on one side alone.
- The relation is a SUPERSET, not an equality. A form on which the
  destructive guard withholds its allow while the new guard stays silent is
  permitted — it costs one classifier round trip (the NFR1 tax) and denies
  nothing. Only the opposite direction is a defect.

Affected tasks: task0004 (owns the check and the alignment), task0001 and
task0003 (their scripts are the two sides the check compares).

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| A text-scan style failure check denies cleanup of a healthy run whose goal text quotes the failure phrase | High if unguarded | High (an unattended run stops on the spot) | D3 mandates structured parsing of the step sequence only; an explicit expectation case covers a healthy feature whose goal text contains the phrase |
| The new guard's deny is cancelled by destructive-guard's blanket allow | Certain if unaddressed | High (feature silently does nothing) | D2 deferral, plus expectation rows proving destructive-guard emits no decision for S1/S2/S3 |
| The deferral is too wide and taxes ordinary commands with classifier round-trips | Medium | Medium | D2 restricts it to real S1/S2/S3 invocations, quote-aware |
| Adding a fifth entry breaks the existing verbatim order assertion | Certain if unaddressed | Medium (red suite) | task0001 owns both the manifest edit and the order-list update |
| The YAML parser is absent in a user environment | Low | Medium (protection silently off) | D4 fail-open, documented as an accepted gap |
| Branch-form targets carry no path, so the worktree must be located indirectly | Medium | Medium (missed protection) | task0001 pins a bounded, static ancestor search and falls through to "no decision" when it does not resolve |

## Open Questions

- [ ] None blocking. Two consequences are deliberately accepted rather than
      open: protection is absent when the YAML parser cannot be imported
      (D4), and a run whose own `workflow.yaml` is unreadable falls outside
      protection (FR10, already an assumption recorded in SPEC.md).
