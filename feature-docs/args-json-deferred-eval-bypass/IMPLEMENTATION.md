# Implementation Plan: args-json-deferred-eval-bypass

## Overview

The per-chunk nameref answer behind the notion-pair exclusion of
`em-workflow/hooks/destructive-guard.py` gains two readings: an
expansion-level reading of constructs that re-evaluate a value as code in the
current shell (task0001), and a command-level reading that classifies command
names by an allowlist and reads the command-level evaluation triggers
(task0002). Either reading marks the chunk as shell-state-uncertain; nothing
else in the hook changes. The review round 1 rework (task0003) adds two
readings of the per-chunk scan that judge syntax from a token's source text:
subscripted fd-variable redirection words and the brackets of a `[[ ]]`
conditional.

## Technology Stack

- **Language**: Python 3, standard library only (NFR3)
- **Judged syntax**: Bash
- **Tests**: the case-table runner `em-workflow/hooks/tests/run-destructive-guard.py`
  and `unittest` (`tests/test_destructive_guard_args_json.py`)
- **New dependencies**: none (no license to record; `project.license` is `none`)

## Layer Structure

| Layer | Responsibility | May depend on |
|---|---|---|
| Hook judgment (`em-workflow/hooks/destructive-guard.py`) | Lexes the command, decides each chunk's nameref answer, applies the notion-pair exclusion | nothing new |
| Case table (`em-workflow/hooks/tests/destructive-guard-cases.json`) | Pins the whole-hook decision of each command | the hook, through the runner |
| Unit tests (`tests/test_destructive_guard_args_json.py`) | Pin the per-chunk answer and the statement kinds | the hook module, loaded from its path |

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| `_args_json_nameref_scan(marked)` | The per-chunk answer: may the chunk's own text declare a nameref or leave the shell state uncertain | Pre: the marked text of one chunk, or none. Post: true when there is no chunk or it carries no top regions (unchanged), when the round-3 literal / brace substitution check holds (FR4, unchanged), when the expansion-level reading holds (task0001), when the lexer cannot read the chunk as statements (unchanged), when any simple command of the chunk is uncertain under `_args_json_declares_nameref()`, when a `{name[subscript]}` word directly followed by a `<` / `>` redirection operator has a subscript that is not digits only, `@` or `*` (task0003), or when a `[[ ]]` conditional, its opener and closer judged from the token's source text (a backslash-escaped or quoted bracket is neither), is opened by a quoted or escaped `[[` command word, is left without a closer, or meets a `;` or a lone `&` while open (task0003); false otherwise. It reads the chunk's own text only, executes nothing and lets no lexer exception escape. task0001 owns its body and docstring; task0002 does not edit it; task0003 adds its two readings to the body and the docstring. | task0001, task0002, task0003 |
| `_args_json_declares_nameref(marked, toks)` | Command-level classification of one simple command | Pre: the tokens of one simple command between two command boundaries. Signature unchanged. Post: true when the command may declare a nameref or leave the state uncertain; false for a command with no command name; false for a command whose name is `mcp-bridge` or `echo`, whatever its argument words hold (double-quoted expansions, substitutions, redirections, here-documents, here-strings). task0002 owns its body and docstring; task0001 only relies on the false cases stated here. | task0001, task0002 |
| `_args_json_nameref_declared(marked)` | Walks from a chunk to its enclosing chunks and caches the answer per chunk | Unchanged by both tasks: computed once per chunk, walked without recursion (NFR2). Everything either task adds runs inside `_args_json_nameref_scan()` and is therefore cached with it. | task0001, task0002 |

## Conventions

- **No new rule (FR8)**: uncertainty reaches the decision only through the
  existing per-chunk answer. No task adds a call to the decision function, a
  reason ID or an ask / deny rule.
- **Fail-safe**: a form either reading cannot settle is uncertain, never
  certain.
- **Case table entries (FR5)**: every added entry's label starts with
  `args-json-deferred-eval-bypass`, followed by the TS-n it pins. A deny entry
  places its form before `A=(json --mcp desktop-commander --tool start_process)`'s
  notion call `mcp-bridge run --mcp notion --tool notion-create-comment --format "$r" --args-json '{"command":"git branch -D example"}'`
  (`--session "$r"` may replace `--format "$r"`) and carries the fourth
  element `{"rule": "git-branch-force-delete"}`, the existing reason ID of the
  decoded command (TS-10). An allow entry uses `--session "$SID"` in the same
  call.
- **Placement, to keep the two tasks' edits apart**:
  - `destructive-guard.py`: new constants and helpers sit next to the function
    that uses them, never at the top of the module. task0001 places its
    helpers between `_args_json_has_brace_substitution()` and
    `_args_json_nameref_scan()`; task0002 places its sets and helpers between
    `_args_json_declares_nameref()` and `_args_json_strip_redirections()`;
    task0003 places its helpers directly before `_args_json_nameref_scan()`.
  - Case table: task0001 and task0003 append their entries at the end of the array;
    task0002 inserts its entries directly before the first existing entry
    whose label starts with `args-json-quoting-bypass review round 3`.
  - Unit tests: task0002 edits `TestNamerefDeclarations` (FR7) and adds its
    new test class directly after it; task0001 and task0003 each add a new
    test class directly before the module's main guard. No task edits the
    module docstring.
- **Docstring ownership**: task0001 owns the docstrings of
  `_args_json_nameref_scan()`, the heredoc-body predicate, the stripped-text
  marker type and `_ChunkLinks.register()`; task0002 owns those of
  `_args_json_declares_nameref()` and `_args_json_declaration_word()`;
  task0003 adds its two readings to `_args_json_nameref_scan()`'s docstring.
  `_args_json_nameref_scan()`'s docstring names no command; it refers to
  `_args_json_declares_nameref()` for the command-name rules.
- **Hook tests (NFR5)**: every task runs
  `python3 em-workflow/hooks/tests/run-destructive-guard.py` and
  `python3 -m unittest discover -s tests` in its own change.
- **Plugin files**: no task's files hold a `.claude-plugin/` path (NFR4).

## Cross-task Design Decisions

### D1: The split follows the reading level

The expansion level (task0001) reads the lexer's regions: arithmetic and
bracket-arithmetic expansions, array subscripts, parameter expansions. The
command level (task0002) reads simple commands: the command name, its option
and assignment words. The arithmetic command `((...))` belongs to the command
level: its word is the command-position word, FR2 changes how that word is
read, and the unit subtest FR7 moves pins it. Keeping FR2, FR3 and FR7 in one
task leaves that subtest with one owner, since either the allowlist or a
region-level count of the arithmetic command would change its kind.

Affected tasks: task0001, task0002.

### D2: A subshell body is not part of an enclosing chunk's reading

A construct that stands only inside a command substitution, a backtick
substitution or a process substitution changes the subshell, not the caller
(TS-9). The expansion level skips every region that has such a region around
it; the command level reads only the chunk's own statements, as today. A
Bash 5.3 current-shell substitution (`${ cmd; }`, `${| cmd; }`) is not a
subshell: its contents are read, and the literal check already marks it.

Affected tasks: task0001, task0002.

### D3: Data positions and harmless subscripts (A3, A4)

Text inside single quotes, ANSI-C quotes, comments and the body of a
quoted-delimiter heredoc is data for both readings. Neither reading newly
marks a subscript made of digits only, an `@` / `*` subscript of a parameter
expansion, or a compound assignment without subscripts. The existing reading
that an assignment word holding an array-subscript region cannot be restored
(and so is uncertain at command level) stays as it is.

Affected tasks: task0001, task0002.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| Wider uncertainty drops the exclusion for a legitimate notion comment whose body quotes a destructive command, and the hook denies it | Medium | Medium (stops an unattended run) | FR6 allow cases and the new allow-side scenarios (TS-9, TS-11, TS-12) pin the kept forms; `mcp-bridge` and `echo` are certain whatever their arguments |
| A construct that re-evaluates a value and is not enumerated in FR1 remains | Medium | High | The expansion level also counts substring offsets / lengths and assigning parameter expansions (task0001); the remainder is an open question |
| Reading unquoted heredoc bodies in the stripping step, which serves every command, raises or slows unrelated judgments | Low | High | A body that cannot be read is marked, never raised (TM-4) |
| The two tasks conflict in the same three files | High | Low | Placement and docstring ownership above; the parent-side adoption protocol resolves what remains |

## Open Questions

- [ ] A function defined in the chunk under an allowlisted name keeps the
      exclusion (SPEC.md Edge Case Notes). A function named `mcp-bridge` can
      hand the notion call's arguments to another MCP tool. This bypass exists
      before this feature and lies outside FR1-FR8; it is a candidate for a
      follow-up feature.
- [ ] task0001 counts two forms FR1 does not enumerate: a substring offset or
      length that is not a digit string, and an assigning parameter expansion
      (`=` / `:=`). Both re-evaluate a value as arithmetic, or assign one that
      may be an integer-attribute variable or `PS4`.
- [ ] task0003 counts the subscript of a `{name[subscript]}` fd-variable
      redirection word, a subscript position FR1's parenthetical list does not
      name. Bash evaluates it as arithmetic when it assigns the descriptor.
- [ ] task0002 reads `test` / `[` with a word that cannot be restored, and
      `printf` with an option or format word that cannot be restored, as
      uncertain (such a word may expand to `-v` or to a `%n` format). This is
      the fail-safe reading of SPEC.md's "uncertain only when it has `-v`".
