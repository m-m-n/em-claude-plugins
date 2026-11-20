# Implementation Plan: args-json-quoting-bypass

## Overview
Four parallel tasks change the `mcp-bridge run --args-json` step of
`em-workflow/hooks/destructive-guard.py`, each owning a disjoint set of
functions in that one module, and add their own runner cases and unit tests.
This document pins only what the four tasks share: function ownership, the
contracts of the functions one task changes and another task's code calls, and
where each task places its additions in the two shared test files.

## Technology Stack
- **Language**: Python 3, standard library only (the hook and both test
  suites already are).
- **New dependencies**: none. No license to record.

## Layer Structure
One module, unchanged in structure. Within the `--args-json` step the call
direction stays:

1. Word readers: `_read_double_quoted()`, `_read_static_word()`,
   `_read_word_as_written()` (masking-stop reading), `_flag_equals_prefix_name()`.
2. Decision: `_mcp_bridge_args_json_chunks()`, which calls the notion-pair
   predicate `_args_json_notion_pair()` and the readers.
3. Collaborator: `_queue_args_json_chunks()`, the only caller of the decision.
4. `statements()`: calls the collaborator once per yielded statement and holds
   no other `--args-json` logic (NFR6). No task edits `statements()`.

No task adds a call from a lower layer to a higher one, and no task adds a new
caller of the decision.

## Shared Components

All four tasks declare `em-workflow/hooks/destructive-guard.py`; tasks 1 to 3
also declare `em-workflow/hooks/tests/destructive-guard-cases.json`; all four
declare `tests/test_destructive_guard_args_json.py`.

### Function ownership in destructive-guard.py

Each task edits only the code, docstrings and comments it owns. Anything not
listed stays byte-identical, including the `def` lines of owned functions
(signatures do not change).

| Owner | Owned regions |
|-------|---------------|
| task0001 | `_args_json_notion_pair()` (body and docstring); the new single-word-certain helper, placed directly after `_args_json_notion_pair()`; the comment above `_MCP_RUN_VALUE_FLAGS`; step 2 of the `_mcp_bridge_args_json_chunks()` docstring; the O2 list in the `_mcp_bridge_args_json_chunks()` docstring; the O2 list in the `extract_shell_payload_anchored()` docstring |
| task0002 | `_flag_equals_prefix_name()` (body and docstring) |
| task0003 | `_read_double_quoted()`, `_read_static_word()`, the docstring of `_read_word_as_written()`, any new private predicate the two readers share (placed directly before `_read_double_quoted()`); step 4 of the `_mcp_bridge_args_json_chunks()` docstring; the comment above `ARGS_JSON_UNRESTORABLE_ASK` |
| task0004 | `_queue_args_json_chunks()` (body and docstring); `_args_json_word_index()` |

Steps 1, 3 and 5 to 8 of the `_mcp_bridge_args_json_chunks()` docstring and
its body are owned by no task and do not change.

### Contracts relied on across tasks

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| `_read_static_word(marked, tok)` | Reads one word of the `--args-json` step | Signature and the three outcome values (`WORD_STATIC` with the restored text, `WORD_NOT_STATIC`, `WORD_UNRESTORABLE`) unchanged. task0003 moves two inputs between outcomes (FR3 form to Unrestorable, `$` plus non-ASCII to Static); every other word keeps its outcome. Not-static still wins over Unrestorable when a word holds both. | Changed by task0003; its existing call sites in the decision are relied on unchanged by task0001 and task0002 |
| `_flag_equals_prefix_name(marked, tok)` | Name part of a non-static `=`-form flag word | Signature unchanged; returns the flag name without dashes, or nothing. task0002 adds the unquoted backslash-escaped `=` as a name-part end; every other word keeps its result. | Changed by task0002; called by the decision's flag reading, unchanged |
| `_args_json_notion_pair(marked, words)` | Decides the notion-pair exclusion | Signature unchanged; true only in a subset of the cases where it is true at base (task0001 narrows it, never widens it). Called only from the decision. | Changed by task0001 |
| Single-word-certain helper (new) | Whether Bash always passes one word as exactly one argument (FR1) | Takes the marked text and one word; true only for a word that is single-word-certain under FR1; false for anything it cannot settle (no span, no marked text, marker residue, a region the word does not hold whole). Reads the word's as-written characters and the lexer's top-level region kinds itself; it does NOT call `_read_double_quoted()`, `_read_static_word()` or `_read_word_as_written()`, whose behaviour task0003 changes. Called only from `_args_json_notion_pair()`. | Built and used by task0001 only |
| `_read_double_quoted(body)` | Restores a double-quoted body | Owned by task0003, which may change its result shape; its callers are all inside task0003's regions. No other task adds a call to it. | task0003 only |
| `_queue_args_json_chunks(...)` | Queues the decision's chunks | Signature unchanged; queued entries and their origin positions (anchor, statement index, token index, ordinal) identical to base for every input. | Changed by task0004; called by `statements()`, unchanged |
| `ArgsJsonResult`, `ArgsJsonValue`, `WORD_*` constants, `ARGS_JSON_UNRESTORABLE_ASK` value | Shared result and ask shapes | Unchanged by every task (only the comment above the ask constant changes, in task0003). The reason id `args-json-unrestorable` and its text stay as they are. | All |
| Chunk derivation link (task0006) | The link from a derived chunk's marked text to the chunk it was derived from, which `_args_json_nameref_declared()` (task0005) walks, and the "may hold a nameref" result of a chunk whose unquoted heredoc body holds a current-shell substitution | Set by code outside `statements()`, which stays byte-identical to the implement base commit. The link fields of `_MarkedText` (`_is_derived`, `_outer_marked`, `_nameref_declared_cache`) and the chain walk keep their meaning; the link is in place before the notion-pair predicate is first asked about the chunk. When `_queue_args_json_chunks()` sets it, the collaborator gains that registration step only: its signature, its queued entries and their origin positions stay as task0004's row above states. | Built by task0006; read by the task0005 chain walk |

## Conventions

- **Runner cases** (`em-workflow/hooks/tests/destructive-guard-cases.json`):
  - Each new case is one line, `[verdict, label, command]` plus the fourth
    element `{"rule": "args-json-unrestorable"}` on the ask cases, following
    `.claude/rules/hook-tests.md`.
  - The label is Japanese and starts with `args-json-quoting-bypass TS-n`
    (n is the SPEC scenario number), and names the finding ID, or O2 (8) for
    TS-12.
  - Each task inserts its cases as one contiguous block directly after a
    distinct existing case, so the three tasks' insertions never touch the
    same or adjacent lines:
    - task0001: after the case whose label starts with
      `mcp-bridge-args-json-exec-guard TS-9:`.
    - task0002: after the case whose label starts with
      `mcp-bridge-args-json-exec-guard TS-23:`.
    - task0003: after the case whose label starts with
      `mcp-bridge-args-json-exec-guard TS-29:`.
  - No case is deleted and no existing case's elements change (NFR2, FR8).
    An inserted block placed between two existing cases leaves every
    existing line unchanged, its trailing comma included, and each inserted
    line ends with a comma. When cases are appended after the file's last
    case, that formerly-last line gains the trailing comma the JSON list
    needs and nothing else on it changes; the new last line has no trailing
    comma.
- **Unit tests** (`tests/test_destructive_guard_args_json.py`):
  - No task edits the module docstring, the imports or the module-level
    helpers; the existing imports suffice. Helpers a task needs live inside
    its own test class.
  - Each new test class or method carries a docstring naming this feature and
    the TS-n it covers.
  - Insertion points, one per task:
    - task0001: TS-17 directly after
      `test_an_excluded_statement_sets_no_unrestorable_flag` in
      `TestFlagReading`; the O2 (8) pin as the last method of `TestDocstring`.
    - task0002: TS-18 directly after `test_the_equals_form_is_inspected` in
      `TestFlagReading`.
    - task0003: one new class directly before `class TestDeferral`.
    - task0004: one new class directly before `class TestDenyWins`.
  - No existing test is edited (FR9); the one exception FR11 allows is
    stated in task0002's plan.
- **Test procedure** (NFR3): before merging, each task runs the runner,
  `python3 -m unittest tests.test_destructive_guard_args_json` and
  `python3 -m unittest discover -s tests`, all from the repository root.
- **No load-based testing** (NFR4): tests show behaviour by structure (spies,
  mocks, counts), never by wall-clock timing or by loading the CPU.
- **Docstrings** are English. Inside the "Out of scope" part of the
  `_mcp_bridge_args_json_chunks()` docstring no task writes any phrase that
  `TestDocstring.test_no_form_that_is_not_out_of_scope_is_listed` forbids.

## Cross-task Design Decisions

### D1: Split by function ownership
The SPEC's change set is one module plus two test files. The four tasks follow
the SPEC's function-to-requirement table: notion pair and O2 (8) (task0001),
`=`-form name reading (task0002), `$` reading in the word readers
(task0003), anchor lookup (task0004). Ownership keeps each task's code edits
apart; the insertion points keep the test-file edits apart. Affected: all.

### D2: The single-word-certain helper is independent of the word readers
task0003 changes how the readers treat `$`; task0001's helper must not depend
on that change, so it reads regions itself (Shared Components). On the safe
side, the helper treats an unquoted `$` that is not the opener of an ANSI-C or
locale quote as making the word not single-word-certain. Affected: task0001,
task0003.

### D3: FR11 rides with the `=`-form task
The subtest FR11 confirms exercises the `=`-form flag reading, so task0002
runs it and changes it only if it fails. Affected: task0002.

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Merge conflict in a shared file | Medium | Low | Ownership table and fixed insertion points; on conflict the implementer's parent-side adoption protocol re-applies its own regions |
| A legitimate notion call turns into deny (the earlier regression) | Medium | High | task0001 keeps the existing notion allow cases and adds TS-5 / TS-17 allow-side checks (TM-2) |
| A docstring edit breaks a TestDocstring pin | Low | Medium | Pinned O1 / O2 phrases kept verbatim; forbidden-phrase list stated in task0001 |
| The FR3 / FR4 reader change alters a word without a line continuation after `$` | Low | High | task0003 requires all existing reader tests and runner cases to pass unchanged |

## Open Questions
- [ ] SPEC TS-17 lists `--args-json` among the flags whose non-certain value
  forms give KIND_INSPECTED. A non-static `--args-json` value word is skipped
  by the flag reading (O2 (1)), so the decision result is KIND_NOTHING for
  those forms whether or not the pair is excluded. task0001 asserts those
  forms at the notion-pair predicate (it is false) and asserts KIND_INSPECTED
  for the `--format` / `--session` forms.
