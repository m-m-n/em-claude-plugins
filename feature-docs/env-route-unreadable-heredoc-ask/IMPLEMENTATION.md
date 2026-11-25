# Implementation Plan: env-route-unreadable-heredoc-ask

## Overview

The env route of destructive-guard reads the `bash -c` payload of a command
whose `env` is written as a path or with a lone `-`. When that payload holds a
here-document whose delimiter word the lexer cannot read, and the unread tail
holds the `mcp-bridge` word, `$'` or `$"`, the reading becomes unrestorable and
the command gets the existing `args-json-unrestorable` ask.

The feature has two tasks. task0001 (merged) built the tail rule, its use in
the env body reading, and the first cases and unit tests. task0002 brings the
merged result to the current FR1: condition (b) is matched on the tail without
its line continuations and covers `$"` (AC-3, AC-4, TS-4 (d) to (f)), and the
rule's answer is kept when the payload's map was obtained but a later step of
the chunk build fails.

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
| In-process unit tests | `tests/test_destructive_guard_env_route_tail.py` | Facts no hook verdict shows: the tail rule's answers, the reading's flag, the failures of the map and of the chunk build, the combination of the two readings, the flag restoration |

Dependency direction: the tests depend on the hook (the runner executes it as
a hook; the unit tests load it from its file path). The hook depends on
nothing new.

## Shared Components

Both tasks declare the three files of the Layer Structure. task0001 is merged,
so task0002 starts from files that already hold its result.

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| `_args_json_env_tail_unrestorable(payload, lex_map) -> bool` in the hook | The tail rule (FR1) | Pre: LEX_MAP is the map the lexer returned for PAYLOAD in shell mode under the extglob setting in force. Post: true exactly when `LEX_MAP.unreadable` is set and TAIL meets (a) or (b). TAIL is the raw text of PAYLOAD from `LEX_MAP.tail_start` to its end; an absent tail start reads as the start of PAYLOAD. JOINED is TAIL with every backslash-newline pair removed. (a) JOINED with every `'`, `"` and `\` removed contains `mcp-bridge`. (b) JOINED contains `$'` or `$"`. It lexes nothing, reads no module state and raises no flag; its cost is linear in the length of TAIL | task0001 (built; its (b) looked for `$'` in TAIL itself), task0002 (changes (b)) |
| `_args_json_env_body_reading(payload, marked)` in the hook | One reading of the payload under the extglob setting in force | Post, by what could be obtained: map not obtained: the empty reading (no entries, no Overrun, no Unrestorable), the rule not asked. Map obtained, chunk not built: no entries, no Overrun, Unrestorable is the rule's answer on the map. Map and chunk obtained: as built by task0001 (the rule's answer is the starting value of Unrestorable, the statements' Unrestorable is ORed in, entries and Overrun come from the statements). No failure of the map or of the chunk build leaves it as an exception; one raised by the statement loop propagates unchanged | task0001 (built; gave the empty reading whenever the chunk was not built), task0002 (changes the middle row) |
| `_args_json_payload_chunk(payload, outer_marked)` in the hook | The derived chunk of a payload, or None | Unchanged: two arguments, None when the payload cannot be lexed within the lexer's bounds at any of its steps | task0001, task0002 (callers only) |
| The case array in `em-workflow/hooks/tests/destructive-guard-cases.json` | Decision cases of this feature | Append-only: a task adds its cases at the end and edits or removes no existing case; the only change to an existing line is the closing comma of the previous last case | task0001, task0002 |
| `tests/test_destructive_guard_env_route_tail.py` | Unit tests of the tail rule and the env body reading | task0002 adds payload data and tests and edits exactly one existing test, the one its plan names | task0001 (built), task0002 (extends) |

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

These decisions bind task0001, task0002 and any rework task that the review or
verify phase adds to this feature.

### D1: Confined to the env route

The tail rule is evaluated only inside the env route's body reading. The top
level, a plain `bash -c`, and run()'s handling of unreadable here-document
delimiters and of extglob switching do not change (NFR1).

### D2: The tail is raw text, matched literally

The tail is the raw payload text from the lexer's tail start to the end. No
expansion is evaluated, so a name that becomes `mcp-bridge` only after
expansion does not match (A3). There are two normalizations, in a fixed order
(FR1): the line continuations are removed first, giving JOINED; then, for
condition (a) only, the `'`, `"` and `\` characters are removed from JOINED.
Condition (b) is matched on JOINED itself, for `$'` and for `$"`.
The word also triggers when it appears only as here-document body text in the
tail (A1), and the pair kind and the `BASH_FUNC_` lifting play no part (A2).

Removing line continuations never separates a `$` from a quote character that
directly follows it, so every tail the earlier condition (b) matched is still
matched.

### D3: Existing ask, existing combination, existing priority

The rule only sets the reading's Unrestorable flag. The existing path turns the
flag into the `args-json-unrestorable` ask: no new reason id, and the reason
text is unchanged. The two extglob readings are combined by the existing OR
(FR2), a reading whose chunk was not built included. Priority stays as it is: a
deny outranks every ask, and the scan-budget ask outranks the
`args-json-unrestorable` ask (NFR2).

### D4: Flag isolation is an invariant

The save and restore of `_lex_unreadable_met`, `_lex_extglob_met` and
`_lex_extglob` around the env route's readings (env-route-lex-flag-isolation
FR1, FR2) does not change (FR3, A5), on every exit of a reading: normal, map
not obtained, chunk not built, exception of the statement loop. The rule reads
the payload's lexer map, never the module flags.

### D5: The map decides whether the rule is evaluated

FR1 evaluates the rule on the payload's map. A failure of a step after the map
(LexBudgetExceeded, LexUnmatchedSubscript included) does not discard the
answer. When the map itself cannot be obtained, the reading is empty as before
and the verdict stays what it was: that payload is out of scope, and it goes to
a separate follow-up task (gate `rework.spec-change`, question
`rework.spec-change.payload-lex-failure`, answer `keep_spec`; review round 1,
stable_id ec07fad74d99fe6b). The change adds no ask for a payload whose tail
meets neither (a) nor (b), and it propagates no exception that was caught
before. `tests/test_destructive_guard_env_route.py` passes unedited.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| A benign env-route body whose unread tail holds `$'`, `$"` or the word gets a new ask, which is a deny in batch | Low | Medium (an unattended run stops) | The rule needs an unreadable map and condition (a) or (b) on the tail; TS-5, TS-6 and TS-14 pin benign verdicts, TS-17 pins the near misses of (b), TS-19 and TS-20 pin the empty readings |
| The lexer call of the reading changes the module flags or the decision to make a second reading | Low | High | It is the call the chunk build makes, with the same text, mode and setting; the readings restore the flags; TS-12, TS-19, TS-20 |
| Keeping the answer drops the early return or lets an exception out, as the reverted auto-fix of review round 1 did to ten subtests | Medium | High (an env-route command gets a new ask or a crash) | Only the map's lexer call and the chunk build are guarded, each as a failure that ends the reading without an exception; TS-20; `tests/test_destructive_guard_env_route.py` unedited |
| A case meant to be red does not reach the env route (its payload word is not static) and passes for the wrong reason | Medium | Medium | Each new failing case is first observed failing on the unmodified hook; the task plan states how to quote the payload |
| Condition (b) is matched on the raw tail, or after the backslashes are removed, instead of on JOINED | Low | High (a split form escapes, or `$\"` gets an ask) | The contract above fixes the text each condition is matched on; TS-17 holds one form for each mistake |

## Open Questions

None.
