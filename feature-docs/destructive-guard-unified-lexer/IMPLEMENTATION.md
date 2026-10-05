# Implementation Plan: destructive-guard-unified-lexer

## Overview

Replace the hook's separate quote / comment / expansion readers (_OperatorContext, _blank_comments(), scan_structure()'s own quote and comment rules, and the raw comment handling of tokens()) with one single-pass shell lexer inside `em-workflow/hooks/destructive-guard.py`, so that `$'...'`, `$"..."`, `${...}`, `$((...))`, `((...))` and `$[...]` are read the way bash reads them. shlex (_TrackingLexer) stays as the tokenizer and receives only a position-preserving rewrite of the text (create-spec answer `requirement.lexer-scope`: shared_state_lexer).

## Technology Stack

- **Language**: Python 3 (the repository's test framework targets Python 3.14, per test/README.md)
- **Key libraries**: Python standard library only (NFR2) — shlex (tokenization, retained), unittest (tests)
- **New dependencies**: none. License record: this feature introduces no new dependency (project.license: none).

## Layer Structure

Each command chunk that statements() pops passes through these layers. A layer may read any earlier layer's result; no layer re-derives an earlier layer's judgment from raw text.

1. **Lexical layer** — the unified lexer (new). Reads a text once and is the sole owner of every quote, comment, expansion, substitution-range, real-heredoc-operator and heredoc-body judgment (FR6).
2. **Layout layer** — heredoc stripping (strip_heredocs()), the position map, and substitution marking. Consumes layer 1; classifies no character itself.
3. **Structure layer** — scan_structure() in all of its modes and callers. Produces its existing return values from layer 1's regions; keeps only span bookkeeping and the honor_single_quotes=False search policy of its own.
4. **Token layer** — _lex_layout() / lex_segments() / tokens(). _TrackingLexer tokenizes the masked view built from layer 1; token values and provenance flags are restored from the original text.
5. **Check layer** — the existing per-statement checks (check_rm(), check_git(), ...). Unchanged; they read Tok values and flags only.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| Unified lexer — `lex_shell(text, mode)` | Single forward pass deciding every context range in a text | See "Unified lexer contract" below | task0001 (hook layers 2-4, agreement test) |
| Position map | Translates positions between the original chunk, the body-stripped chunk and the marker-inserted text | See "Position map contract" below | task0001 (hook layers 2-4, agreement test) |
| Masked view and value restoration | Builds the text _TrackingLexer reads and restores each token's value and flags from the original text | See "Masked view and value restoration contract" below | task0001 (hook layer 4, agreement test) |

The hook module and the agreement test (`tests/test_destructive_guard_lexer_agreement.py`) both program against these contracts; any later rework task does too.

### Unified lexer contract

- **Signature**: `lex_shell(text, mode)`; MODE is `shell` (default) or `heredoc-body`. In `heredoc-body` mode, quote characters and `#` outside any substitution are literal text; inside a substitution, shell rules apply (the same split scan_structure() documents today).
- **Precondition**: TEXT is any string, including one with unbalanced quotes or unclosed openers.
- **Output (the lexical map)**:
  - Regions: an ordered list; each region has a kind, a start offset, an end offset (exclusive) in TEXT, and its immediately enclosing region (or none). Kind vocabulary: single-quote, double-quote, ansi-c-quote (`$'...'`), locale-quote (`$"..."`), comment, parameter-expansion (`${...}`), arithmetic-expansion (`$((...))`), arithmetic-command (`((...))` at command position), bracket-arithmetic (`$[...]`), command-substitution (`$(...)`), backtick-substitution, here-string-operator (`<<<`).
  - Real heredoc operators: for each, the offset of its `<<` / `<<-`, the end of its delimiter word, the delimiter word, whether the delimiter was quoted, and the line range of its body (none when the delimiter line never appears).
  - Unopened openers: offsets of the `${`, `$((`, `$[`, `((` and `$'` openers that were read as not opened (P4).
- **Postconditions**:
  - P1 (FR1): `$'` opens an ansi-c-quote only outside quotes (inside a parameter-expansion included). Inside it, a backslash escapes the next character; the first unescaped `'` closes it. Inside double quotes, `$'` opens nothing. A `'` directly after the special parameter `$$` (and after any other special parameter such as `$?`) is an ordinary single quote. A backslash-escaped `$` opens nothing.
  - P2 (FR2): `${` opens a parameter-expansion closed by its matching `}`. Inside it, quotes are tracked (a `}` inside quotes does not close it), `#` starts no comment, `<<` is no operator, `(` is not counted as group nesting, and nested `${...}`, `$(...)`, backticks and `$'...'` are recognized.
  - P3 (FR3): `$((`, `$[` (nested `[ ]` counted) and `((` at command position open arithmetic regions. Inside them `<<` is no operator, `;` is no separator and `#` starts no comment; nested `$(...)`, backticks and `${...}` are recognized. Command position is: the start of the text, after a statement separator or newline, after a group opener `(` or `{`, after a reserved word (`if`, `then`, `elif`, `else`, `do`, `while`, `until`, `!`, `time`), and the `((` following `for`. It is never after a redirection operator or a process-substitution opener (`<(`, `>(`).
  - P4 (FR5, SPEC A3): an opener among `${`, `$((`, `$[`, `((` and `$'` whose closer does not appear before the end of TEXT is not a region, and the characters after it are read as if it had not opened. A `((` or `$((` whose matching close is not an adjacent `))` is read as two parentheses (`(` `(` / `$(` `(`).
  - P5: in `shell` mode, a `#` starts a comment only at the start of a word and outside every quote, expansion and arithmetic region; the comment ends before its newline.
  - P6 (FR8): a `<<` / `<<-` is a real heredoc operator only outside quote, comment, parameter-expansion and arithmetic regions; inside a command substitution it is real, even when that substitution sits inside double quotes. `<<<` is never one. The body lines of a real operator, through its delimiter line, change no lexer state.
  - P7 (NFR1, NFR3): the same TEXT and MODE always give the same map; the lexer reads no file and evaluates nothing; total work is linear in the length of TEXT, including the work of settling openers that never close.

### Position map contract

- **Coordinates**: O = the original chunk; S = the chunk with real heredoc bodies removed (what strip_heredocs() returns); M = S with top-level substitutions replaced by marker residue (what _lex_layout() tokenizes).
- **Postconditions**: S to O is total and strictly increasing; O to S is total except inside removed body lines, which map to their HeredocRecord; S to M maps a position inside a marked substitution to that substitution's marker; M to S is total and strictly increasing. Construction is linear in the chunk length.

### Masked view and value restoration contract

- **Masked view**: a text with the same length as M. Every character inside a region whose content shlex would read differently from bash (at least: ansi-c-quote, parameter-expansion, the three arithmetic kinds, and comments) is replaced by a mask character; comment text becomes blank up to, not including, its newline. Characters outside those regions are unchanged. Substitution marker residue is never masked, so the existing marker mechanism still yields the same unresolved / substitution_only flags. The mask character is one shlex treats as an ordinary word character (not whitespace, a quote, an escape, a punctuation character or a commenter) and differs from every substitution marker character the hook already uses.
- **Value restoration (FR7)**: each token's inspection value is computed from the original characters of its span through the position map, never by searching the text for mask characters. No value handed to the check layer contains a mask character. A token whose original span contains no masked region gets exactly the value shlex gives that original span.
- **Provenance (FR7)**: is_operator is true only for bare operator syntax outside every region. quoted is true exactly when the token's original span contains a quote region or quote delimiter of any kind (single, double, ANSI-C, locale), including one nested in an expansion. unresolved, substitution_only and raw_substitution_body keep coming from the existing marker mechanism.

## Conventions

- **Fail closed (SPEC A3)**: when the lexer cannot settle bash's reading, it takes the reading that keeps later text inspected: no heredoc body capture, no comment removal, no swallowed separator.
- **Docstrings**: every new or changed function states its contract in the file's existing docstring style and names this feature and the FR IDs it implements.
- **Removal**: _OperatorContext, _blank_comments() and the private constants only they use are deleted outright; no compatibility shim remains.
- **Placement (NFR4)**: the lexer lives in destructive-guard.py; the only new file is the agreement test.
- **Cases file**: new cases are appended after every existing entry; existing entries keep their position and content.

## Cross-task Design Decisions

### D1: One implementation task
FR11 requires the cases to land before the fix, FR10's agreement test exercises the new lexer directly, and FR1-FR9 replace readers inside the one hook file. Tasks run fully in parallel, so no split leaves each task's tests passable on its own. The feature is one task (task0001, complexity high).

### D2: shlex stays as the tokenizer
Per the create-spec answer `requirement.lexer-scope` (shared_state_lexer), shlex keeps operator fusion and token building; it only ever reads the masked view.

### D3: Static-value classification of expansion words is unchanged
A word containing `${...}`, `$((...))` or `$[...]` keeps the unresolved / substitution_only classification the pre-change hook gave it, and every `$(...)` / backtick nested inside such an expansion is still extracted and scanned (FR4). This feature changes where separators, comments and heredoc operators are recognized, not whether a word's value counts as statically known.

### D4: Settling unclosed openers stays linear
Deciding that an opener never closes (P4) must not cost one rescan of the remaining text per opener. When the lexer cannot settle within its linear bound, the hook issues the existing scan-budget "ask" decision that statements() already uses, never allow.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| A benign existing case turns into ask / deny (the round-2 precedent) | Medium | High | Cases appended only; full case runner plus the agreement test over every cases.json command |
| Words with expansions change unresolved classification, shifting verdicts | Medium | High | D3 invariant; existing cases containing expansions must keep their verdicts |
| Settling unclosed openers becomes super-linear | Medium | High | D4; adversarial unclosed-opener input timed in the agreement test |
| Heredoc ranges agree but the body is attributed to the wrong host statement | Medium | High | Verdict-level cases (SPEC AC-1 form 1, AC-2) and the agreement check on heredoc operator positions |
| Command-position detection reads a process substitution `<((...))` as arithmetic and hides its command | Low | High | P3 excludes positions after redirections and process-substitution openers; a deny control in the agreement test |
| The mask character collides with input or marker characters | Low | Medium | Restoration by position, never by character search; mask distinct from marker characters |

## Open Questions

- None.
