# Implementation Plan: approval-unicode-whitespace

## Overview

Narrow every approval-match trim in `em-workflow/scripts/merge-preflight.py`
and `em-workflow/hooks/bash_guard.py` to spaces and tabs, and refuse approval,
on every path, for a value that still has another whitespace character at
either end after that trim (SPEC.md FR1-FR9, NFR1-NFR4).

## Technology Stack

- **Language**: Python 3.14, standard library only (NFR1, NFR3).
- **Tests**: standard-library unittest, run as
  `python3 -m unittest discover -s tests`.
- **New dependencies**: none. `project.license` is `none`; no license line is
  recorded because nothing is added.

## Layer Structure

| Layer | Files | Responsibility |
|-------|-------|----------------|
| Approval store and hook | `em-workflow/hooks/bash_guard.py` | Sole owner of the approval store (`approved_for`, `--record`, `--remove`, `--list`) and of the PreToolUse decision (`hook_main`, cd prefix form, declared commands). |
| Merge preflight | `em-workflow/scripts/merge-preflight.py` | Check 7 (verification command approval). Reads the approved set only by running `bash_guard.py --list`. |
| Protocol documentation | `em-workflow/references/command-execution-protocol.md` | States the approval rule the orchestrator and implementers follow. |

Dependency direction is unchanged: merge-preflight.py runs `bash_guard.py
--list` as a child process; neither script imports the other.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| C1: approval trim rule | The single definition of "trim", "empty", "matchable" and "non-matchable" that every approval path applies | See "C1: approval trim rule" below | task0001, task0002 (implement); task0003 (documents) |
| C2: bash_guard.py trim helpers | Two module-level functions in bash_guard.py that implement C1 | See "C2: bash_guard.py trim helpers" below | task0001, task0002 |
| C3: approved set (`approved_for` and `--list`) | The set of approved strings for a project, as the hook and merge-preflight.py see it | See "C3: approved set" below | task0002 (producer); task0001 (consumer through the hook and through merge-preflight.py) |

### C1: approval trim rule

- **Trim**: precondition — the value is a string. Postcondition — the result
  is the value with every leading and trailing space (U+0020) and tab
  (U+0009) removed. No other character is removed or changed: LF, CR, U+000B,
  U+000C, U+00A0, U+0085, U+2000-U+200A, U+3000 and every other character
  stay as they are.
- **Classification of a trimmed value**:
  - *empty* — the trimmed value has length zero;
  - *non-matchable* — the trimmed value is non-empty and its first or its
    last character is a character that Python's string whitespace test
    classifies as whitespace (the definition SPEC.md FR1 fixes);
  - *matchable* — every other trimmed value.
- **Comparison**: only a matchable trimmed value is compared with approved
  strings, by exact string equality. Inner whitespace is never normalized.
- **Per-path consequences** (every path fails closed):

| Path | Empty | Non-matchable | Owner |
|------|-------|---------------|-------|
| merge-preflight.py `collect_commands` / `check_approval` | skipped (not a command) | collected and stops as `commands_unapproved`; the raw-value LF / CR exclusion stays in force | task0001 |
| bash_guard.py hook entry (`hook_main`) | no decision | never allowed: denied as unapproved when declared, otherwise no decision | task0001 |
| cd prefix remainder (`is_cd_prefixed_approved`, `cd_remainder_excluded`) | not a candidate | not a candidate and excluded from the cd prefix allow | task0001 |
| declared commands (`declared_commands`) | not declared (unchanged) | kept in the declared set, so the hook denies it | task0001 |
| stored entries (`approved_for`, `--list`) | dropped (unchanged) | dropped: never approved, never listed | task0002 |
| `--record` / `--remove` stdin lines (after removing exactly one trailing LF) | skipped (unchanged) | the whole input is refused: stderr report, exit code 1, store unchanged | task0002 |

### C2: bash_guard.py trim helpers

- `trim_blanks(value) -> str` — precondition: `value` is a string.
  Postcondition: returns the C1 Trim of `value`. Pure; no I/O.
- `is_matchable(text) -> bool` — precondition: `text` is a result of
  `trim_blanks`. Postcondition: true exactly when `text` is C1-matchable
  (non-empty, and neither its first nor its last character is whitespace by
  the C1 definition). Pure; no I/O.
- **Placement**: module level in bash_guard.py, directly after
  `strip_yaml_quotes` and directly before `declared_commands`. Both task0001
  and task0002 introduce these two functions with exactly these names, this
  contract and this placement (see "D3" below).
- Names and docstrings contain no substring `status` (NFR2).

### C3: approved set

- `approved_for(store, key)` — precondition: `store` is a loaded store
  mapping, `key` a project key. Postcondition: the set of the project's stored
  entries that are strings and C1-matchable after the C1 Trim, each in its
  trimmed form. A non-string, empty or non-matchable entry is not a member.
- `bash_guard.py --list --project-dir DIR` — postcondition: prints each member
  of `approved_for` for the project once, one per line, sorted; exit code 0.
  Unchanged: a failure to run or decode it makes merge-preflight.py stop with
  `commands_unapproved` ("approval cannot be confirmed").
- **Consumer rule**: a consumer never relies on the producer-side filtering
  for its own refusal. merge-preflight.py refuses a non-matchable command
  value itself, and the hook refuses a non-matchable command itself, whatever
  the approved set contains. This keeps task0001 and task0002 independently
  correct in their own worktrees.

## Conventions

- **Fail closed**: a value that is non-matchable is never turned into a
  matchable one by any further trimming or normalization on an approval path.
  Trims unrelated to approval (for example git output) are out of scope and
  unchanged.
- **Hook outputs**: no new decision kind and no new reason text is
  introduced. A non-matchable command reaches only the existing deny
  branches (refusal pattern, unapproved declared command) or no decision.
- **Preflight outputs**: no new stop reason; every refusal in this feature is
  `commands_unapproved`. The `command` in the `proceed` output stays the
  original, untrimmed value.
- **bash_guard.py source**: standard-library imports only (NFR1, pinned by
  `TestAc7StandardLibraryOnly`); no substring `status` anywhere in its
  executed text (NFR2, pinned by `tests/test_hook_classification_pin.py`).
- **Tests**:
  - standard-library unittest only; every test that touches the approval
    store points `EM_WORKFLOW_APPROVALS` at a temporary file (NFR3);
  - the hook is exercised as a child process given a PreToolUse JSON payload,
    the store CLI as a child process given stdin;
  - non-ASCII and control whitespace is written in test source as escape
    sequences, never as raw invisible characters, so a reviewer can see it;
  - the character set is shared across tasks: U+00A0, U+000B and U+000C as
    the primary set, each before, after and on both sides of the value;
    U+0085, U+2000, U+3000 and U+001F as the representative other whitespace
    characters; `make<U+00A0>test` against `make test` for inner whitespace.
- **Test run**: the task-completion check is the full suite. bash_guard.py
  has no dedicated runner in `.claude/rules/hook-tests.md`; none of the hooks
  that file lists is touched by this feature.
- **Versions**: no task edits a `plugin.json` or
  `.claude-plugin/marketplace.json` (NFR4).

## Cross-task Design Decisions

### D1: task split follows the test coupling

The existing agreement test in `tests/test_merge_preflight.py`
(`test_fr4_ac3_preflight_agrees_with_bash_guards_own_approval_decision`) runs
merge-preflight.py and the hook on the same values and asserts that they
agree, so fixing either side alone breaks it. The hook entry trim also decides
the trailing case of the cd prefix remainder and whether a padded declared
value is denied. merge-preflight.py check 7, the hook entry, the cd prefix
remainder and the declared-command extraction therefore form one task
(task0001). The store side (`approved_for`, `--list`, `--record` /
`--remove`) has no test that needs the hook-entry change and is task0002. The
protocol document is task0003. Affected: task0001, task0002, task0003.

### D2: two independent implementations of C1

merge-preflight.py carries its own implementation of C1 (its form is
task0001's choice); it does not import bash_guard.py. The agreement test keeps
the two implementations equal. Affected: task0001.

### D3: one definition of the C2 helpers after integration

task0001 and task0002 both need C2 and run in parallel, so both add it, with
the names, contract and placement fixed above. Identical additions merge
cleanly as one copy; differing additions at the same place surface as a merge
conflict that the second task to merge resolves by parent-side adoption,
keeping the already-merged definition and its own call sites. Placement
elsewhere is a plan deviation, because it would leave two definitions.
Affected: task0001, task0002.

### D4: documentation ownership

- bash_guard.py module docstring (the hook-mode summary and the cd prefix
  "approval" bullet): task0001. task0002 does not edit the module docstring.
- merge-preflight.py module docstring (Approval rule paragraph) and the
  comment in `check_approval`: task0001.
- `em-workflow/references/command-execution-protocol.md`: task0003.

Affected: task0001, task0002, task0003.

### D5: existing tests that pin the old trim

An existing test that pins the old behaviour is updated by the task that
changes the behaviour it pins, and only to the extent SPEC.md requires:
lines 1198-1199 of `tests/test_merge_preflight.py`, the case "surrounding
whitespace on the command" in `tests/test_bash_guard_cd_prefix.py` and
`test_ac2_surrounding_blanks_and_a_trailing_line_feed_allow` in
`tests/test_bash_guard_cd_prefix_operators.py` belong to task0001. Any other
existing test found to pin the old trim is updated in the same task and
reported as a plan deviation. Affected: task0001, task0002.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| C2 helpers end up defined twice in bash_guard.py after both tasks merge | Low | Medium (dead duplicate, reviewer confusion) | Fixed names and placement (D3); VERIFICATION.md manual item checks one definition |
| An approval path keeps a full-whitespace trim that no test reaches | Medium | High (the bypass stays open on that path) | C1 per-path table names every path and its owner; VERIFICATION.md manual item reviews every approval-path trim in the integrated code |
| An existing test outside the plan pins the old stdin or stored-entry trim | Low | Low | D5: update it in the owning task and report the deviation |
| A batch run whose workflow.yaml command carries non-space/tab padding now fails the approval gate (`--record` exit 1) | Low | Low (intended fail-closed stop) | The refusal is reported on stderr in the same manner as a refusal pattern; task0003 documents that such a value is never approved |

## Open Questions

None.
