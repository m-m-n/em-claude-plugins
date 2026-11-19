# Implementation Plan: mcp-bridge-args-json-exec-guard

## Overview
destructive-guard decodes the `--args-json` value of every `mcp-bridge run`
statement other than the notion pair and queues the substitution candidates of
every decoded string and every top-level `command` string for the ordinary
re-scan. task0001 and task0002 (merged) built that step and its explanations.
This re-plan follows the SPEC change of review round 1: task0003 reads the
words after `run` the way mcp-bridge reads them, asks instead of skipping
silently when a bound leaves something unscanned or a static word cannot be
restored, moves the step's bookkeeping out of statements(), and pins the new
cases and the revised unit tests; task0004 updates the in-code explanations.
Review round 2 (finding ca547a9f716957df) adds task0005: a flag-position word
whose restored text is shorter than two characters (a lone `-`) ends the flag
sequence as a positional word (D2 step 2).

Verify round 1 found that TS-19 is deny at the base commit as well. The SPEC
change of that round records it: TS-19 is deny before and after the change
(SPEC.md AC-11), and it is outside the pre-change reproduction set (SPEC.md
NFR3). The merged code and cases already meet the revised SPEC, so this
re-plan corrects the plan documents only and adds no task. The merged task0003
plan, whose red-run criterion expects every new deny and ask case to be allow
before the change, is not edited; VERIFICATION.md's Pre-change Reproduction
states the current expectation.

## Technology Stack
- **Language**: Python 3 (the existing hook script, its case runner and the
  unit tests under `tests/`).
- **Key libraries**: the language's standard library only. JSON decoding uses
  the standard library's JSON decoder. No new dependency is introduced, so no
  dependency license is recorded (`project.license`: none).

## Layer Structure
- **Hook**: `em-workflow/hooks/destructive-guard.py`. The step's decision
  (`_mcp_bridge_args_json_chunks()`) and its bookkeeping collaborator
  (`_queue_args_json_chunks()`) sit outside statements(). statements() calls the
  collaborator once per statement it yields, next to the `-c` / `eval` /
  here-string payload extraction, and settles its deferred asks once its queue
  is drained. The raw-string scan before the step is unchanged.
- **Case suite**: `em-workflow/hooks/tests/destructive-guard-cases.json`, read
  by `em-workflow/hooks/tests/run-destructive-guard.py`.
- **Unit tests**: `tests/`, run by `python3 -m unittest discover -s tests`.
- Dependency direction: case suite and unit tests to hook only.

## Shared Components
| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| `_mcp_bridge_args_json_chunks()` (existing function in `em-workflow/hooks/destructive-guard.py`; name kept) | The decision for one statement: whether it is an inspected `mcp-bridge run` statement, and what its `--args-json` values yield (FR1 to FR6, FR11) | Pre: the shaped words of a statement that statements() yielded, and the marked text it was lexed from. Post: nothing is evaluated, executed or read, and no token, marked text or state of statements() changes. The result is either "nothing to do" (not a target, the notion pair, or a statement-level FR6 form) or: for each `--args-json` value, in order, that is static and decodes to an object, its anchor word, its candidate bodies and its top-level `command` strings (each in document order); the total scan charge of the rebuilds, the nesting passes, the decodes and the walks; an Overrun flag (some value nests deeper than `MAX_ARGS_JSON_DEPTH` or fails the decoder for a reason other than a JSON syntax error); and an Unrestorable flag (FR11, D5). Flow: D2, D3, D5. The representation is the building task's choice | task0003 (revises it), task0004 (names it), task0005 (revises the flag reading of D2 step 2) |
| `_queue_args_json_chunks()` (new function in the same file) | The step's bookkeeping, outside statements() (NFR5): it calls the decision once and does everything statements() did inline for it | Pre: called by statements() once for each statement it yields, with that statement's shaped words, marked text, lexed flag and origin step, the chunk's anchor and derived Python-body mark, and the run's pending queue, scan state (scanned total and budget) and `_DeferredAsks` record. Post: (1) for a statement from the parse-failure fallback, or once this step has already held the scan-budget ask in the run, it does nothing; (2) on Overrun, or when the charge would take the scanned total past the budget, it leaves the scanned total unchanged, queues nothing for the statement and holds the scan-budget ask; (3) otherwise it adds the charge to the scanned total and queues every body like a substitution body and every `command` string like a `-c` payload, taking no count from `MAX_SHELL_PAYLOAD_EXPANSIONS`, each anchored at its value's word in the payload anchor form; (4) on Unrestorable it holds the `args-json-unrestorable` ask, whatever (2) or (3) did. It never emits a decision and never ends the scan (D3, D6, D7) | task0003 (builds it and calls it), task0004 (names it) |
| `_DeferredAsks` (new class in the same file) | The run-local record of the asks statements() holds until its queue is drained (NFR5) | Pre: one record per statements() run. Post: it holds at most the two asks of D6 (scan-budget, `args-json-unrestorable`); it is settled once, after the queue is drained: with an early-stop list the strongest held ask is appended to it, with none that ask is emitted through decide(); an empty record does nothing. An ordinary scan-budget overrun that ends the scan early keeps its present behaviour, and the record is then not settled (D6) | task0003 (builds it; the collaborator and the payload extraction hold asks in it), task0004 (names it) |
| `ARGS_JSON_UNRESTORABLE_ASK` (new module constant) | The (reason id, reason text) pair of the FR11 ask | Reason id `args-json-unrestorable`; the reason text is Japanese and says, in the sense of FR11, that the quoting of an `mcp-bridge run` `--args-json` value or flag word cannot be restored statically, so a confirmation is asked on the safe side. Same shape as `SCAN_BUDGET_ASK` | task0003 (defines it), task0004 (names it) |
| `MAX_ARGS_JSON_DEPTH` (existing module constant, value 100) | The deepest JSON nesting the step decodes (D3) | Unchanged | task0003 (uses it), task0004 (may name it) |

## Conventions
- **Fail-closed (NFR2)**: the step only adds chunks to `pending` and holds asks.
  It removes no chunk the existing scan queues and never turns an existing deny
  or ask into allow. A change from allow to ask happens only for the FR11 and
  FR12 forms.
- **Case format**: `.claude/rules/hook-tests.md`. New cases carry no fourth
  element, except TS-21 and TS-22, whose fourth element holds only the reason
  ID (A6). The two TS-15 cases already pin theirs.
- **Existing cases**: none is removed or edited (FR9).
- **Explanation ownership**: task0003 owns the docstrings and comments of the
  code it writes, revises or moves: `_mcp_bridge_args_json_chunks()` (an FR8 /
  FR10 site), `_queue_args_json_chunks()`, `_DeferredAsks`,
  `ARGS_JSON_UNRESTORABLE_ASK`, the word reader of D5, `_read_word_as_written()`,
  the module comment above `MAX_ARGS_JSON_DEPTH`, and the comments inside the
  part of the statements() body it changes. task0004 owns the other FR10 sites:
  the `_single_quote_skip_spans()` docstring, the single-quote candidate
  paragraph of the `scan_structure()` docstring, the statements() docstring,
  the destructive-guard-false-deny FR2 comment above the queueing loop of
  statements(), the out-of-scope declaration of
  `extract_shell_payload_anchored()`, and the comment on
  `MAX_SHELL_PAYLOAD_EXPANSIONS`. Neither task edits the other's sites.
- **Language**: docstrings and comments in English; case labels in Japanese,
  like the existing labels, each naming this feature and the case ID.
- **Change set**: no plugin manifest and no marketplace entry is part of any
  task's files (NFR4).

## Cross-task Design Decisions

### D1: The step is additive and runs at every statement
- **Decision**: the step runs for every statement that statements() yields
  from a lexed segment, in every chunk (top level, `&&` / `;` / `|` chains,
  behind wrappers, substitution bodies, payloads, queued `command` strings).
  The raw-string single-quote skip of `_single_quote_skip_spans()` keeps its
  present conditions (W1 to W4, C1, S1, S2, top-level chunk only).
- **Basis**: FR1, FR2, NFR2.
- **Affected tasks**: task0001 built it; task0003 keeps it through the
  collaborator; task0002 and task0004 describe it.

### D2: Which statements are inspected, and how the words after `run` are read (revised)
- **Target (FR1)**: the command word that `head()` returns over the shaped
  words is exactly `mcp-bridge` and is not a substitution, and the next word is
  exactly `run`. Unchanged.
- **Notion pair (FR2, A9)**: the canonical reading of task0001 decides it and
  is not widened: every word in flag position is exactly one of `--mcp`,
  `--tool`, `--args-json`, `--format`, `--session` (each takes the next word as
  its value) or `--dry-run`, written as one unquoted run; `--mcp`, `--tool` and
  `--args-json` each appear exactly once; the `--mcp` value is `notion` and the
  `--tool` value is `notion-create-comment`, each as one unquoted run. Such a
  statement gets neither FR3 to FR5 nor FR11.
- **Every other target statement (FR3)** is read left to right with the
  reading of mcp-bridge-exec-tool-rescan IMPLEMENTATION.md D1 (A11); the first
  word after `run` is in flag position:
  1. A word in flag position is classified (D5). Not static: the statement is
     not inspected (FR6 (2)). Unrestorable: the step holds the
     `args-json-unrestorable` ask, the reading ends, and no value of the
     statement is inspected (FR11). Otherwise its restored text is used, so a
     quoted or backslashed flag word reads as the plain one (FR3 (a)).
  2. Restored text exactly `--` ends the flag sequence; restored text that does
     not begin with `-`, or that is shorter than two characters (the empty
     text, a lone `-`), is a positional word and ends it too (FR3 (d)). The
     `--args-json` values read before the end are inspected; the words after
     it are not read as flags. The word shorter than two characters follows
     Go's standard flag parsing, which ends the flags at such a word; review
     round 2 finding ca547a9f716957df reads mcp-bridge-exec-tool-rescan D1
     (A11) as recording that `mcp-bridge run` uses that parsing.
  3. Otherwise one or two leading dashes are removed (FR3 (b)), and the rest is
     split at its first `=` into a name and an inline value (FR3 (c)).
  4. Name `mcp`, `tool`, `args-json`, `format` or `session`: the value is the
     inline value, or else the next word, whatever it holds; with neither, the
     statement is not inspected (FR6 (4)). The word after a value word is in
     flag position. Name `dry-run`: no value, inline or not. Any other name:
     the statement is not inspected (FR6 (3)).
- **Values (FR3 (e), (g))**: every `--args-json` value is handled on its own,
  in order. The values of `--mcp`, `--tool`, `--format` and `--session` are not
  examined, so a non-static destination does not stop the inspection (A8). No
  `--args-json` at all: the statement is not inspected (FR6 (5)).
- **Per value**: a value word of its own is classified (D5): not static, that
  value is skipped (FR6 (1)); unrestorable, the step holds the
  `args-json-unrestorable` ask and skips that value (FR11); otherwise its
  restored text is the value (FR3 (f)). An inline value is the text after the
  first `=` of its restored flag word, and its anchor word is the flag word.
- **Basis**: FR1 to FR3, FR6, FR11, A8, A9, A11; review round 1 findings
  65c5a71c6af6cb06 and e0e4df99e5cded9d; review round 2 finding
  ca547a9f716957df (step 2, the word shorter than two characters).
- **Affected tasks**: task0003 implements it; task0004 describes it; task0005
  implements step 2's word shorter than two characters and updates the
  flag-reading step of the `_mcp_bridge_args_json_chunks()` docstring.

### D3: Decoder failures, the nesting bound and the step's charge (revised)
- **Decision**: a value the decoder rejects with a JSON syntax error, and a
  decoded value whose top level is not an object, are skipped (FR6 (6), (7)).
  Nesting deeper than `MAX_ARGS_JSON_DEPTH`, measured before decoding outside
  JSON strings, and every other decoder failure, set Overrun. On Overrun, and
  when the step's charge would take the scanned total past the budget, the
  collaborator adds nothing to the scanned total, queues nothing for the
  statement and holds the scan-budget ask; from then on the step does nothing
  for the rest of the run. The queue already filled is therefore processed
  within the bounds as they stand, and the ask is settled after it is drained
  (D6). The walk over a decoded value stays iterative.
- **Charged when popped**: a queued body or `command` string is charged when it
  is popped, as every chunk is. An overrun at that point is the ordinary
  overrun of statements() and ends the scan as it does today.
- **Basis**: FR7, NFR1; review round 1 findings 2a7b7391eec63ca0 and
  3be0fecc1174dfe2. A value only the guard's decoder fails on must not fall to
  the FR6 path (THREAT-MODEL.md TM-3).
- **Affected tasks**: task0003 implements it; task0004 describes it.

### D4: Scenario commands with JSON escapes
- **Decision**: the commands of the case suite and VERIFICATION.md are the
  shell text of SPEC.md's Test Scenarios, verbatim. `\u0024` and
  `\u0060` in them are six-character JSON escapes (a backslash, `u` and
  four hex digits) that must reach the hook unchanged.
- **Basis**: SPEC.md now writes the escapes; the first plan had to restore them
  (its D4). An editing tool can decode such an escape on the way into a file,
  which is how the first plan's documents lost them.
- **Affected tasks**: task0001 (merged cases), task0003 (new cases).

### D5: Classifying a word the step reads (new)
- **Decision**: the step reads a flag-position word and an `--args-json` value
  word with a reader of its own that gives one of three outcomes.
  - **Not static** (FR6 (1), (2)): the word holds an element of FR6 (1): a
    region of a kind other than a single-quote, double-quote, ANSI-C or locale
    quote (a substitution, a parameter or arithmetic expansion, an array
    subscript); an unescaped `$` or backtick inside a double-quote or
    locale-quote region; an unquoted `$` or backtick; the unquoted glob,
    brace, tilde and extended-glob forms that `_read_word_as_written()`
    rejects; residue of a real substitution; a word that is a substitution as a
    whole. A word with no as-written reading (no span, no marked text) is not
    static too, as today.
  - **Unrestorable** (FR11): the word holds none of those, and its quoting
    still cannot be restored: an ANSI-C quote that `_decode_ansi_c()` gives no
    result for (a NUL, a character outside ASCII, an escape it does not
    handle), a locale quote, or any other failure of the restoration.
  - **Restored text**: otherwise, the characters Bash passes on. The marker
    residue the marking left for a single-quote candidate inside a single-quote
    or ANSI-C-quote region of the word does not count against it: the
    candidate's characters are the literal text Bash passes on (as task0001).
- **Reader placement**: the three-outcome reader is not a mode flag of
  `_read_word_as_written()`. That function keeps only the masking-stop reading
  (the quote-residue mode task0001 added to it is removed), and its result for
  the masking-stop caller does not change. Helpers both readers share are
  allowed.
- **Basis**: FR6, FR11; review round 1 finding c7437c587af92da4.
- **Affected tasks**: task0003.

### D6: Deferred asks (new)
- **Decision**: one `_DeferredAsks` record per statements() run holds two asks:
  - the scan-budget ask (`SCAN_BUDGET_ASK`), held by the collaborator on
    Overrun or on a charge that does not fit (D3), and by the payload
    extraction of statements() when the payload counter is used up (D7);
  - the `args-json-unrestorable` ask (`ARGS_JSON_UNRESTORABLE_ASK`), held by the
    collaborator (D2, D5).
  After the queue is drained the record is settled once. The strongest held
  ask is the scan-budget ask, then the `args-json-unrestorable` ask; exactly
  that one is appended to an early-stop list, or emitted through decide() when
  statements() has none. main()'s resolution is unchanged: a deny found
  anywhere wins over every ask, and decide() demotes an ask to deny under
  batch. When an ordinary overrun ends the scan early (at a pop, or on the
  unclosed command forms of a chunk), statements() returns as it does today
  with the scan-budget ask, and the record is not settled.
- **Basis**: FR7, FR11, FR12, NFR5; SPEC.md Error Handling (deny, then
  `scan-budget-exceeded`, then `args-json-unrestorable`).
- **Affected tasks**: task0003 implements it; task0004 describes it.

### D7: The payload counter (new)
- **Decision**: `MAX_SHELL_PAYLOAD_EXPANSIONS` (25, unchanged) counts the
  `-c` / `eval` / here-string payloads only. A decoded top-level `command`
  string takes no count; it is bounded by the scan budget only (FR5, D3). The
  payload extraction runs for every lexed statement whatever the counter
  holds: a payload that is not blank is queued while the counter is above zero
  and takes one, and with the counter at zero it is not queued and the
  scan-budget ask is held (FR12). This holds in every chunk: the top level,
  substitution bodies, payloads and queued `command` strings.
- **Basis**: FR5, FR12, A4; review round 1 findings 32aa9e6e947c325d and
  934ab7486f2cfbfb.
- **Affected tasks**: task0003 implements it; task0004 describes it.

### Out-of-scope forms (FR8)
The forms below are stated with the same scope in the docstring of
`_mcp_bridge_args_json_chunks()` (task0003), in the out-of-scope declaration
of `extract_shell_payload_anchored()` (task0004), and in the labels of the
cases that pin them (TS-10, TS-13, TS-14 from task0001; TS-27, TS-28 from
task0003). Neither form is sent to ask; each keeps the verdict it has without
the step.
- **O1**: a command written as plain text, without a substitution, in a key
  other than the top-level `command` (for example the `input` of
  desktop-commander's `interact_with_process`), or in a `command` key below
  the top level. Only the candidate search applies there (TS-10).
- **O2**: the FR6 forms, which keep the raw-string verdict:
  1. an `--args-json` value word that is not static, set by a substitution, a
     variable expansion or the like (a substitution Bash itself runs is still
     re-scanned) (TS-13);
  2. a word in flag position that is not static in the same sense (TS-27);
  3. an unknown flag (TS-28);
  4. a value-taking flag with no value word;
  5. no `--args-json`;
  6. a value that does not decode as JSON (TS-14);
  7. a decoded value whose top level is not an object.

None of these is out of scope, and no out-of-scope statement lists them: a
destination that is not static, an ANSI-C escape the guard cannot restore, a
quoted flag name, the `=` form, a single-dash flag, a value before `--` or a
positional word (a lone `-` included), a repeated `--args-json`.

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| FR12 turns an existing allow case that holds 26 or more payloads into ask (a false deny under batch) | Low | Medium | task0003 looks for such cases before the change and in the red run; FR9: it stops and reports without editing the case |
| The wider flag reading turns an existing allow case into deny or ask | Low | Medium | The existing allow cases that hold `mcp-bridge run --args-json` are the notion cases, whose canonical exclusion is unchanged, and task0001's TS-10 to TS-14, each either not a target statement or written in the canonical flag sequence, which the wider reading reads as before; the full suite runs in every task and in verify |
| Removing the quote-residue mode of `_read_word_as_written()` changes the masking-stop reading | Low | High | Its result for the masking-stop caller is an acceptance criterion of task0003; the full case suite and the existing unit tests run |
| FR11 asks on a legitimate command and stops a batch run | Low | Medium | Only a word with no FR6 (1) element whose quoting cannot be restored is affected (A10) |
| A parser difference between the guard and mcp-bridge (duplicate keys, nesting) hides a destructive value | Medium | High | D3 and the all-pairs walk; THREAT-MODEL.md TM-2 and TM-3 |
| task0003 and task0004 edit the same file in parallel | Medium | Low | Disjoint regions by the explanation-ownership convention; task0004 names only the components pinned above |
| A long repeated case command (TS-18, TS-19, TS-22) is written with the wrong count, or a JSON escape is decoded on the way into the case file (D4) | Medium | Medium | task0003 reads each stored command back, compares it with the shell text and counts the repetitions; the red run shows each new deny and ask case as allow, except TS-19, which is deny before the change as well (SPEC.md AC-11, NFR3), so the read-back alone checks its count |

## Open Questions
- [ ] The case labelled "TM-1 escaped key" that task0001 added holds the key
  `command` written plainly, not with a JSON escape; the escaped key is pinned
  only by the unit test of the walk. FR9 forbids editing the case in this run.
