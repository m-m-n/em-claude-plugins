# Implementation Plan: destructive-guard-unified-lexer

## Overview

Replace the hook's separate quote / comment / expansion readers (_OperatorContext, _blank_comments(), scan_structure()'s own quote and comment rules, and the raw comment handling of tokens()) with one single-pass shell lexer inside `em-workflow/hooks/destructive-guard.py`, so that `$'...'`, `$"..."`, `${...}`, `$((...))`, `((...))`, `$[...]` and the process substitutions `<(...)` / `>(...)` are read the way bash reads them. shlex (_TrackingLexer) stays as the tokenizer and receives only a position-preserving rewrite of the text (create-spec answer `requirement.lexer-scope`: shared_state_lexer).

## Technology Stack

- **Language**: Python 3 (the repository's test framework targets Python 3.14, per test/README.md)
- **Key libraries**: Python standard library only (NFR2) — shlex (tokenization, retained), unittest (tests)
- **New dependencies**: none. License record: this feature introduces no new dependency (project.license: none).

## Layer Structure

Each command chunk that statements() pops passes through these layers. A layer may read any earlier layer's result; no layer re-derives an earlier layer's judgment from raw text.

1. **Lexical layer** — the unified lexer (new). Reads a text once and is the sole owner of every quote, comment, expansion, substitution-range (command, backtick and process substitution), real-heredoc-operator and heredoc-body judgment, and of the single-quote substitution candidates the broad substitution search reads (FR6, FR9).
2. **Layout layer** — heredoc stripping (strip_heredocs()), the position map, and substitution marking. Consumes layer 1; classifies no character itself.
3. **Structure layer** — scan_structure() in all of its modes and callers. Produces its existing return values from layer 1's output; keeps only span bookkeeping and the choice of which layer-1 output each search policy reads.
4. **Token layer** — _lex_layout() / lex_segments() / tokens(). _TrackingLexer tokenizes the masked view built from layer 1; token values and provenance flags are restored from the original text.
5. **Check layer** — the existing per-statement checks (check_rm(), check_git(), ...). Unchanged; they read Tok values and flags only.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| Unified lexer — `lex_shell(text, mode)` | Single forward pass deciding every context range, substitution range and single-quote substitution candidate in a text | See "Unified lexer contract" below | task0001 (hook layers 2-4, agreement test) |
| Position map | Translates positions between the original chunk, the body-stripped chunk and the marker-inserted text | See "Position map contract" below | task0001 (hook layers 2-4, agreement test) |
| Masked view and value restoration | Builds the text _TrackingLexer reads and restores each token's value and flags from the original text | See "Masked view and value restoration contract" below | task0001 (hook layer 4, agreement test) |

The hook module and the agreement test (`tests/test_destructive_guard_lexer_agreement.py`) both program against these contracts; any later rework task does too.

### Unified lexer contract

- **Signature**: `lex_shell(text, mode)`; MODE is `shell` (default) or `heredoc-body`. In `heredoc-body` mode, outside any substitution, quote characters, `$'`, `$"`, `#`, `<(` / `>(` and a bare `((` are literal text, while the `$` expansions (`${`, `$((`, `$[`, `$(`, backticks) are recognized; inside a substitution, shell rules apply (the split scan_structure() documents today, extended to the new expansion kinds).
- **Precondition**: TEXT is any string, including one with unbalanced quotes or unclosed openers.
- **Output (the lexical map)**:
  - Regions: an ordered list; each region has a kind, a start offset, an end offset (exclusive) in TEXT, and its immediately enclosing region (or none). Kind vocabulary: single-quote, double-quote, ansi-c-quote (`$'...'`), locale-quote (`$"..."`), comment, parameter-expansion (`${...}`), arithmetic-expansion (`$((...))`), arithmetic-command (`((...))` at a command position, and the `((...))` header of an arithmetic for), bracket-arithmetic (`$[...]`), command-substitution (`$(...)`), backtick-substitution, process-substitution (`<(...)`, `>(...)`), here-string-operator (`<<<`).
  - Real heredoc operators: for each, the offset of its `<<` / `<<-`, the end of its delimiter word, the delimiter word, whether the delimiter was quoted, and the line range of its body (none when the delimiter line never appears).
  - Single-quote substitution candidates (P8): for each single-quote and ansi-c-quote region, the candidate ranges inside it and each candidate's enclosing substitution region (or none).
  - Unopened openers (P4): the offsets of the `${`, `$((`, `$[`, `((` and `$'` openers settled as not opened, and the start of the re-read tail (none when no opener was settled that way).
- **Postconditions**:
  - P1 (FR1): `$'` opens an ansi-c-quote only outside quotes (inside a parameter-expansion included). Inside it, a backslash escapes the next character; the first unescaped `'` closes it. Inside double quotes, `$'` opens nothing. A `'` directly after the special parameter `$$` (and after any other special parameter such as `$?`) is an ordinary single quote. A backslash-escaped `$` opens nothing.
  - P2 (FR2): `${` opens a parameter-expansion closed by its matching `}`. Inside it, quotes are tracked (a `}` inside quotes does not close it), `#` starts no comment, `<<` is no operator, `(` is not counted as group nesting, and nested `${...}`, `$(...)`, backticks and `$'...'` are recognized.
  - P3 (FR3; create-plan answer PA4 — arithmetic is decided by grammar state, never by a blanket exclusion):
    - `$((` and `$[` (nested `[ ]` counted) are expansions. Each opens an arithmetic region wherever a `$` expansion is recognized — outside single-quote, ansi-c-quote and comment regions — including inside double quotes, inside a parameter-expansion and in a redirection target.
    - A bare `((` opens an arithmetic-command region only at a real command position: the start of TEXT; after a newline, `;`, `&`, `&&`, `||`, `|` or `|&`; after `!`; after the reserved words `if`, `then`, `elif`, `else`, `do`, `while`, `until`, `time` (also `time -p`) and `coproc`; after the group openers `{` and `(`; after the `)` that closes a case pattern; as the body of a function definition; and at the start of a process-substitution body (P9). The `((` directly after `for` opens the arithmetic-for header.
    - A bare `((` is never arithmetic inside a quote, after a backslash escape, at an argument position, or as a redirection target.
    - Inside every arithmetic region, `<<` is no operator, `;` is no separator and `#` starts no comment; nested `$(...)`, backticks and `${...}` are recognized.
  - P4 (FR5, SPEC A3; create-plan answer Q3-agreement-risk): an opener among `${`, `$((`, `$[`, `((` and `$'` whose matching closer is absent before the end of TEXT is not a region, and its own characters are literal (the `'` of an unclosed `$'` opens no single quote; an unclosed `$((` is settled here, not as an unclosed `$(`). The text from the earliest such opener to the end of TEXT is the re-read tail. It is read by every other rule, except that no `<<` in it is a real heredoc operator and no `#` in it starts a comment; separators in it count as usual. So nothing after an unclosed opener is dropped as a heredoc body or as a comment, and no separator is swallowed. A `((` or `$((` whose matching close exists but is not an adjacent `))` is read as two parentheses (`(` `(` / `$(` `(`); that reading is not an unclosed opener and starts no re-read tail. Unclosed `'`, `"`, `$(`, backticks and process substitutions keep the pre-change handling: a quote runs to the end of TEXT (the token layer then takes its parse-failure path) and a substitution is reported unterminated, running to the end of TEXT.
  - P5: in `shell` mode, a `#` starts a comment only at the start of a word, outside every quote, parameter-expansion and arithmetic region and outside the re-read tail; the same rule applies inside a command or process substitution body. The comment ends before its newline.
  - P6 (FR8): a `<<` / `<<-` is a real heredoc operator only outside quote, comment, parameter-expansion and arithmetic regions and outside the re-read tail. Inside a command substitution (even one inside double quotes) or a process substitution it is real. `<<<` is never one. The body lines of a real operator, through its delimiter line, change no lexer state.
  - P7 (NFR1, NFR3): the same TEXT and MODE always give the same map. The lexer reads no file and evaluates nothing. Total work is linear in the length of TEXT, including settling openers that never close and computing the P8 candidates (also for one quote region holding tens of thousands of `$(`, as the existing ~60KB case does).
  - P8 (FR9; create-plan answer Q3-single-quote-candidates): the candidates reproduce, inside each single-quote and ansi-c-quote region, what the pre-change broad search (scan_structure() with honor_single_quotes=False) finds there. Scanning left to right within the quote region: a `$(` closes at the `)` that balances its own `(` when every `(` and `)` up to the quote's end counts alike; failing that, at the first `)` after it; with none, it is no candidate. A backtick closes at the next backtick before the quote's end; with none, it is no candidate. Scanning resumes after a candidate's end, so an opener inside an earlier candidate is no separate candidate. A candidate never extends past its quote region. Candidates are not regions and change no other judgment of the lexer.
  - P9 (FR3, FR4; create-plan answers PA4, Q3-procsub): in `shell` mode, and inside a substitution in `heredoc-body` mode, `<(` and `>(` outside quote, comment, parameter-expansion and arithmetic regions open a process-substitution region closed by its matching `)`. The opener's two characters are consumed once and the body starts at a new command position: `<((rm ...))` is the opener followed by a subshell `(`, never arithmetic; `<(((1<<2)))` holds an arithmetic-command region. Inside the body, the rules for a command-substitution body apply (quotes, comments, the case-pattern `)`, nested substitutions, real heredoc operators).

### Position map contract

- **Coordinates**: O = the original chunk; S = the chunk with real heredoc bodies removed (what strip_heredocs() returns); M = S with top-level substitutions replaced by marker residue (what _lex_layout() tokenizes).
- **Segments**: each of the two maps (O to S, S to M) is an ordered list of segments. An unchanged segment is a run of characters copied verbatim between the two coordinates. A replaced segment is either a removed heredoc body (its O range has no S counterpart and maps to its HeredocRecord) or a marked substitution (its whole S range corresponds to its whole marker range in M). The two lengths of a marked substitution may differ: the marker carries a run-global index, so a three-character `$()` can become a marker of six characters or more (create-plan answer Q3-position-map).
- **Postconditions**:
  - Positions keep their order across each map.
  - Within an unchanged segment the map is a constant shift; a round trip returns the same position and the same character.
  - A position inside a replaced segment maps to that segment's whole counterpart (its range, or its HeredocRecord), never to a single position inside it; the counterpart maps back to the whole replaced range.
  - No character-level total or strictly increasing correspondence is promised across replaced segments.
  - Construction is linear in the chunk length.

### Masked view and value restoration contract

- **Masked view**: a text with the same length as M. A mask character replaces every character inside a region whose content shlex would read differently from bash (at least: ansi-c-quote, parameter-expansion, the three arithmetic kinds, and comments) and the quote character of an opener settled as not opened (P4), so shlex never opens a quote the lexer did not. Comment text becomes blank up to, not including, its newline. Characters outside those positions are unchanged. Substitution marker residue is never masked, so the existing marker mechanism still yields the same unresolved / substitution_only flags. The mask character is one shlex treats as an ordinary word character (not whitespace, a quote, an escape, a punctuation character or a commenter) and differs from every substitution marker character the hook already uses.
- **Value restoration (FR7)**: each token's inspection value is computed from its span through the position map, never by searching the text for mask characters. Characters in unchanged segments are restored from the original text; marker residue keeps going through the existing marker mechanism. No value handed to the check layer contains a mask character. A token whose original span contains no masked position gets exactly the value shlex gives that original span.
- **Provenance (FR7)**: is_operator is true only for bare operator syntax outside every region. quoted is true exactly when the token's original span contains a quote region or quote delimiter of any kind (single, double, ANSI-C, locale), including one nested in an expansion. unresolved, substitution_only and raw_substitution_body keep coming from the existing marker mechanism.

## Conventions

- **Fail closed (SPEC A3)**: when the lexer cannot settle bash's reading, it takes the reading that keeps later text inspected: no heredoc body capture, no comment removal, no swallowed separator.
- **Docstrings**: every new or changed function states its contract in the file's existing docstring style and names this feature and the FR IDs it implements.
- **Removal**: _OperatorContext, _blank_comments() and the private constants only they use are deleted outright; no compatibility shim remains.
- **Placement (NFR4)**: the lexer lives in destructive-guard.py; the only new file is the agreement test.
- **Cases file**: new cases are appended after every existing entry; existing entries keep their position and content.

## Cross-task Design Decisions

### D1: One implementation task, with a fixed in-task order
FR11 requires the cases to land before the fix, FR10's agreement test exercises the new lexer directly, and FR1-FR9 replace readers inside the one hook file. Splitting would leave the case task holding intentionally failing cases and the fix task unable to check agreement with a lexer it does not own (create-plan answer PA1). The feature is one task (task0001, complexity high), carried out in this order: append the cases, confirm that they fail against the unchanged hook, and commit them; then write and commit the agreement test; then change the hook. The verify phase checks that commit order in the task history.

### D2: shlex stays as the tokenizer
Per the create-spec answer `requirement.lexer-scope` (shared_state_lexer), shlex keeps operator fusion and token building; it only ever reads the masked view.

### D3: Static-value classification of expansion words is unchanged
A word containing `${...}`, `$((...))` or `$[...]` keeps the unresolved / substitution_only classification the pre-change hook gave it, and every `$(...)` / backtick nested inside such an expansion is still extracted and scanned (FR4). This feature changes where separators, comments and heredoc operators are recognized, not whether a word's value counts as statically known.

### D4: Settling unclosed openers stays linear
Deciding that an opener never closes (P4) must not cost one rescan of the remaining text per opener. When the lexer cannot settle within its linear bound, the hook issues the existing scan-budget "ask" decision that statements() already uses, never allow.

### D5: A process substitution is a substitution
A `<(...)` / `>(...)` body is discovered, queued and scanned as its own chunk, and the heredoc operators inside it are attributed, exactly as for a `$(...)` body: scan_structure() reports it among its spans, with parent and containing-span information. The statement holding it keeps the opener evidence that the heredoc destination analysis reads today (has_process_sub), so `tee >(bash) <<'EOF'` keeps its deny. This closes `cat <((rm -rf ...))`, which the pre-change hook allows (create-plan answer Q3-procsub).

### D6: Agreement is anchored to fixed expectations
Layers that all read one lexer map can share one misread and still agree. Every edge form the agreement test adds therefore carries hand-written expected regions (and real heredoc operators where relevant) and an expected hook verdict. Agreement between layers alone never counts as proof of a reading (create-plan answer Q3-agreement-risk).

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| A benign existing case turns into ask / deny (the round-2 precedent) | Medium | High | Cases appended only; full case runner plus the agreement test over every cases.json command |
| Words with expansions change unresolved classification, shifting verdicts | Medium | High | D3 invariant; existing cases containing expansions must keep their verdicts |
| Settling unclosed openers becomes super-linear | Medium | High | D4; adversarial unclosed-opener input timed in the agreement test |
| Heredoc ranges agree but the body is attributed to the wrong host statement | Medium | High | Verdict-level cases (SPEC AC-1 form 1, AC-2) and the agreement check on heredoc operator positions |
| Command-position recognition misses a real position (an arithmetic `<<` is read as a heredoc) or invents one (a subshell or process-substitution body read as arithmetic) | Medium | High | P3 position list and P9 opener consumption; deny cases for less common positions; `cat <((rm -rf ...))` deny and `cat <(((1<<2)))` allow |
| Every layer shares one misread, so the agreement test passes over a wrong reading | Medium | High | D6: hand-written expected regions and verdicts for every added form |
| Text after an unclosed opener is still dropped through a comment or a heredoc body | Low | High | P4 re-read tail; deny forms with `#` and `<<` after unclosed openers |
| The broad search (FR9) loses reach once single-quote state comes from the lexer | Low | High | P8 candidates; agreement property that broad-policy spans equal default spans plus candidates; the ~60KB case |
| Position round trips are assumed exact across markers whose length differs from the substitution | Low | Medium | Segment-based position-map contract; character round trips checked only on unchanged segments |
| Reporting a process substitution as a span removes the opener evidence the heredoc destination analysis reads | Low | Medium | D5 invariant; the existing `tee >(bash) <<'EOF'` case keeps deny |
| The re-read tail rule changes an existing allow case | Low | Medium | Full case runner; a changed verdict is reported as a plan deviation, never fixed by editing the case |
| The mask character collides with input or marker characters | Low | Medium | Restoration by position, never by character search; mask distinct from marker characters |

## Open Questions

- None.
