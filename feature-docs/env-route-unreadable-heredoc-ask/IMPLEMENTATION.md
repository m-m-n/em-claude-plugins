# Implementation Plan: env-route-unreadable-heredoc-ask

## Overview

The env route of destructive-guard reads the `bash -c` payload of a command
whose `env` is written as a path or with a lone `-`. When that payload holds a
here-document whose delimiter word the lexer cannot read, and the unread tail
holds the `mcp-bridge` word or `$'`, the reading becomes unrestorable and the
command gets the existing `args-json-unrestorable` ask. The feature has one
task (task0001).

## Technology Stack

- **Language**: Python 3, standard library only (the hook and its tests).
- **Test tools**: the decision-case runner
  `em-workflow/hooks/tests/run-destructive-guard.py`, and `unittest` discovery
  over `tests/`.
- **New dependencies**: none. `project.license` is `none`, and no license is
  recorded because no dependency is added.

## Layer Structure

| Layer | File | Responsibility |
|-------|------|----------------|
| Hook decision logic | `em-workflow/hooks/destructive-guard.py` | The env route's reading of a `bash -c` payload, and the tail rule inside it |
| Decision cases | `em-workflow/hooks/tests/destructive-guard-cases.json` | End-to-end verdicts of whole commands, read by the runner |
| In-process unit tests | `tests/test_destructive_guard_env_route_tail.py` | Facts no hook verdict shows: the tail rule's answers, the reading's flag, the combination of the two readings, the flag restoration |

Dependency direction: the tests depend on the hook (the runner executes it as
a hook; the unit tests load it from its file path). The hook depends on
nothing new.

## Shared Components

None. The feature has a single task (task0001), so no component is built by
one task and used by another. The contract of the tail rule is stated in
`tasks/task0001.md`.

## Conventions

- **Case labels**: every new case label starts with
  `env-route-unreadable-heredoc-ask TS-n:` followed by a Japanese description
  of the body and of why the verdict holds, like the existing labels. New
  cases are appended at the end of the array. Existing cases are neither
  edited nor removed (NFR3, `.claude/rules/hook-tests.md`).
- **Case metadata**: a case that fixes an ask or a deny carries `rule`; a case
  that fixes the batch verdict carries `batch: true` (FR4).
- **Unit test loading**: unit tests load the hook from its file path with
  bytecode writing off, as `tests/test_destructive_guard_env_route.py` does, so
  no `__pycache__` is written next to the hook (everything under
  `em-workflow/` is distributed).
- **Docstring citations**: docstrings and comments cite this feature's
  requirements as `env-route-unreadable-heredoc-ask FRn`, the way the existing
  docstrings cite theirs.

## Cross-task Design Decisions

These decisions bind task0001 and any rework task that the review or verify
phase adds to this feature.

### D1: Confined to the env route

The tail rule is evaluated only inside the env route's body reading. The top
level, a plain `bash -c`, and run()'s handling of unreadable here-document
delimiters and of extglob switching do not change (NFR1).

### D2: The tail is raw text, matched literally

The tail is the raw payload text from the lexer's tail start to the end. No
expansion is evaluated, so a name that becomes `mcp-bridge` only after
expansion does not match (A3). The only normalization is removing line
continuations and then the `'`, `"` and `\` characters, in that order (FR1).
The word also triggers when it appears only as here-document body text in the
tail (A1), and the pair kind and the `BASH_FUNC_` lifting play no part (A2).

### D3: Existing ask, existing combination, existing priority

The rule only sets the reading's Unrestorable flag. The existing path turns the
flag into the `args-json-unrestorable` ask: no new reason id, and the reason
text is unchanged. The two extglob readings are combined by the existing OR
(FR2). Priority stays as it is: a deny outranks every ask, and the scan-budget
ask outranks the `args-json-unrestorable` ask (NFR2).

### D4: Flag isolation is an invariant

The save and restore of `_lex_unreadable_met`, `_lex_extglob_met` and
`_lex_extglob` around the env route's readings (env-route-lex-flag-isolation
FR1, FR2) does not change (FR3, A5). The rule reads the payload's lexer map,
never the module flags.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| A benign env-route body whose unread tail holds `$'` or the word gets a new ask, which is a deny in batch | Low | Medium (an unattended run stops) | The rule needs an unreadable map and condition (a) or (b) on the tail; TS-5, TS-6 and TS-14 pin benign verdicts |
| The added lexer call changes the module flags or the decision to make a second reading | Low | High | It returns the cached map the chunk build already reported; the readings restore the flags; TS-12 |
| A case meant to be red does not reach the env route (its payload word is not static) and passes for the wrong reason | Medium | Medium | Each new failing case is first observed failing on the unmodified hook; the task plan states how to quote the payload |

## Open Questions

- [ ] Observed while planning, outside this SPEC: when the lexer cannot settle
  the payload within its bounds (LexBudgetExceeded, LexUnmatchedSubscript
  included, inside `_args_json_payload_chunk()`), the env route's reading is
  empty and raises no ask. This feature does not examine whether that path can
  hide a notion pair.
