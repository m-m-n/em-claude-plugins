# Implementation Plan: destructive-guard-lexer-round2-deferred

## Overview
Close the eight review round 2 findings that destructive-guard-lexer-round2-residuals
deferred, all in the lexer of `em-workflow/hooks/destructive-guard.py`: openers
after an unreadable delimiter word, one tail gate, a here-document after a
subscript closed on a later line, line continuations inside a name, line and
delimiter boundaries other than `\n`, continuation joining in unquoted bodies,
`\r` as a blank, and bash 5.3 `${ cmd; }` / `${| cmd; }`. Five tasks run in
parallel and share three files.

## Technology Stack
- **Language**: Python 3, standard library only (NFR5).
- **New dependencies**: none. `project.license` is `none`; no license to
  record.
- **Test entry points**: `python3 em-workflow/hooks/tests/run-destructive-guard.py`
  (case table through the hook's stdin / stdout contract, normal mode),
  `python3 -m unittest tests.test_destructive_guard_lexer_agreement` (fixed
  lexical expectations, two-mode verdicts, stage agreement, linearity, module
  contract) and the project suite `python3 -m unittest discover -s tests`.

## Layer Structure
- **Lexer layer**: `lex_shell()`, its single pass (`_lex_pass`), the line
  index (`_LexLines`) and the delimiter reader. Most of every task lives here.
- **Consumers**: here-document stripping (cuts the bodies the lexer reports),
  the structure scan (spans, unmatched openers, here-document body
  extraction), the masked view and its tokenizer, statement shaping. Changed
  only by task0001 (statement-level case shaping honours the tail), task0004
  (tokenizer blanks) and task0005 (downstream handling of the command form of
  `${`).
- **Decision layer**: turns statements into allow / ask / deny. Changed only
  by task0004 (a trailing `\r` on a word is disregarded when matching).
- Dependency direction stays consumers → lexer; the lexer depends on nothing
  above it.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| `lex_shell()` and its lexical map | One forward reading of a command text into the lexical map | Pre: any text, mode `shell` or `heredoc-body`. Post: the same (text, mode, bodies) always gives an identical map (NFR4); the work counted is at most `LEX_WORK_FACTOR` × text length + 1024, otherwise the budget-exceeded condition is raised and the hook answers ask (deny under `CLAUDE_BATCH`), never allow (NFR1, NFR3); nothing is read from disk and nothing is evaluated (NFR5). The map's fields keep their meaning, with three additions: UNOPENED also lists the expansion openers the tail gate refuses (task0001); the regions include the command-form substitution region (task0005); line starts are offset 0 and the offsets right after each `\n`, nothing else (task0003). | task0001, task0002, task0003, task0004, task0005 |
| Tail gate (one decision function of the lexer pass) | Decides, for an opener kind at an offset, whether the opener may open in the current pass state | Owned by task0001. **Tail-start class** (refused from the tail start on: the earliest settled opener, or the first `<<` whose delimiter word cannot be read): comment, here-document operator, assignment-word subscript and array-element subscript, discarded-line trigger (P13). **Tail-source class** (refused once a `<<` whose delimiter word cannot be read has been met): single quote, double quote, `$'`, `$"`, parameter-form `${`, `$((`, `$[`, `((` at a command position, opening a case construct. **Never gated**: `$(`, backtick, process substitution, command-form `${ ` / `${|`. A refused opener is literal text and its offset is listed in UNOPENED. Tasks other than task0001 keep every existing tail check they touch semantically unchanged and add no inline tail check of their own; parent-side adoption turns any such check into a gate call. | task0001 (owner), task0002, task0005 |
| Character classes of the lexer | Which characters are blanks, delimiter metacharacters and line separators | Blanks (end a word, are skipped between words, leave the next character at a word start, end a bound subscript): space and tab only, owned by task0004. Here-document delimiter metacharacters: space, tab, `\n`, `;`, `\|`, `&`, `(`, `)`, `<`, `>`; line separator of the line index and of the operator's-line rule: `\n` only, owned by task0003. Once both merge, `\r`, `\x0b`, `\x0c`, `\x1c`, `\x1d`, `\x1e`, `\x85`, ` ` and ` ` are ordinary word characters everywhere in the lexer. Neither task changes the other's set. | task0003, task0004 |
| Here-document close-line rule | Where a body ends | Owned by task0003. Quoted delimiter: a physical line equal to the delimiter value (under `<<-` once its leading tabs are removed), as today. Unquoted delimiter: a candidate is the body's first line, or a line whose preceding line does not end with an odd number of backslashes; it is compared after being joined with the lines it continues into (each backslash-newline removed) and, under `<<-`, after removing its leading tabs; the close end is the end of the last joined physical line. The index stays one pass per kind, and its existing call shape keeps its present meaning. | task0003 (task0002 relies on the operator reading after a subscript, unchanged) |
| Assignment-word subscript start | Where a `NAME[` subscript opens | Owned by task0002: the `NAME[` test runs on the word's leading characters with every backslash-newline pair removed, at exactly the positions where it runs today; the subscript opens at the original offset of the `[`. The tail-start decision for a subscript compares the word's original start offset (task0001's gate). A `]` that never comes still raises LexUnmatchedSubscript. | task0002 (owner), task0001 |
| `${` dispatch in the lexer's `$` handling | Which reading a `${` starts | task0005 decides first: `${` directly followed by a space, a tab, a newline or `\|` is the command form; any other `${` is the parameter form, which alone is subject to the settle channel (unchanged) and to the tail gate (task0001). This holds wherever the `$` handling runs (shell-rule frames, double quotes, expansions, subscripts, the literal top level of a here-document body). | task0001, task0005 |
| Word-level grammar state of a shell-rule frame | What a word does to command position, case state and frames | task0001: a `case` word met after a tail source opens no case construct (gate). task0002: the `NAME[` detection. task0005: a `}` word at a reserved-word position closes the innermost command-form frame, unless it closes a brace group opened inside that frame. No task changes any other transition (command position, after-closer position, `time` options, `coproc`, `function`, `for` / `select`, conditional command). | task0001, task0002, task0005 |
| Statement-level case shaping | Case-pattern state across the statements of one chunk | Owned by task0001: in `statements()` and in the here-document destination table, a statement that begins at or after the chunk's tail start (from the lexer's map of that chunk, compared in one coordinate system) opens no case construct with `case`; the group-closer mirror of the case state follows the same rule. No other task changes statement shaping. | task0001 |
| Substitution regions downstream | How the structure scan, marking and body extraction treat a substitution region | Owned by task0005: the command-form region is a member of the substitution kinds, so it is a span in the structure scan, marked at the top level, and its inner text (after `${` or `${\|`, before the closing `}`, or to the end of its extent when unclosed) is queued as its own chunk; an unclosed one is still reported with its inner text, in here-document body extraction as well. The openers task0001 refuses need no downstream change: they are neither quote characters nor masked. | task0005 (task0001 relies on it unchanged otherwise) |
| Pass state and resume snapshot | Completeness of the state a non-adjacent-close resume restores | Any field a task adds to `_LexPassState` is classified in `_LexResumeSnapshot` (restored or deliberately not restored); the existing completeness test fails otherwise. No task changes the resume mechanism or the non-adjacent-close re-reading. | task0001, task0002, task0003, task0004, task0005 |
| Lexer internals the agreement test drives directly | Call shapes the test file depends on | `_LexLines(text)` with its close-line index per operator flavour, `_lex_pass(...)` as the whole-text-restart reference and the resume tests call it, `_tokenize_marked(marked, layout)` and `_MarkedText.plain(text)`: every existing call keeps working with its present meaning. A task that extends one does so with an optional addition, or updates every caller in the test file in the same change. | task0001, task0002, task0003, task0004, task0005 |
| Case table append protocol (`em-workflow/hooks/tests/destructive-guard-cases.json`) | Holds the regression cases the runner checks | Pre: 769 entries at the feature base (indexes 0-768). Post: each task appends its own contiguous block after the last entry; no entry is inserted before, edited, removed or reordered (FR10); every new label begins with the finding's stable_id, then `round2-deferred`, then a requirement tag (e.g. `FR2.1`), then a Japanese description like the existing labels; the commit that appends a task's cases precedes every commit of that task that changes the hook (FR9). Tests locate new cases by label and command text, never by an absolute index of 769 or above, because the order of the blocks depends on merge order. | task0001, task0002, task0003, task0004, task0005 |
| Agreement test layout (`tests/test_destructive_guard_lexer_agreement.py`) | Where each task adds tests, so parallel edits land in distinct places | task0001: a new class directly after `TestHeredocFallbackAndCloseLines`, the placement test in `TestModuleContract` after the existing round 2 placement test, and the one in-place rewrite its plan names. task0002: a new class directly after `TestArraySubscriptAndExtglobReadings`. task0003: a new class directly after `TestHeredocDelimiterWords`. task0004: a new class directly after `TestPositionMap`. task0005: a new class and a stage-agreement subclass over its forms directly after `TestUnclosedOpeners`, the in-place rewrites its plan names, and the kind constants at the top of the file if it adds a region kind. Constants a task needs sit next to its own class. | task0001, task0002, task0003, task0004, task0005 |

## Conventions
- **Fail-safe direction (NFR6)**: follow bash 5.3. Where the lexer cannot
  match bash, choose the reading that keeps the following lines inspected.
- **Lexical pin ownership**: a task's fixed expectations assert exactly on
  what the task owns. Where another task's change can alter a region (the
  reading of a `${`, an opener after a tail source, how a `\r` beside the
  form is read), the expectation asserts only presence or absence of the
  region kinds it is about, never the full region list.
- **bash confirmation**: a probe never runs a destructive command; `rm` is
  replaced by a harmless `echo`. Forms listed in SPEC.md are added as written
  (their bash 5.3.9 behaviour was confirmed in review round 2 or is fixed by
  SPEC.md). A form a task adds beyond SPEC.md that claims a bypass (bash runs
  the destructive line) is confirmed on bash 5.3 when it is available;
  otherwise it is pinned in the agreement test only, not in the case table,
  and the task report lists it as unconfirmed. A deny case that only keeps an
  existing conservative verdict needs no confirmation.
- **Existing cases are fixed points**: if a change flips the verdict of any
  pre-existing case, the case is not edited; the task withholds that
  behaviour change and reports the conflict as a plan deviation.
- **Existing agreement-test expectations**: only the rewrites a task plan
  names may change an existing expectation. Another one that the planned
  reading forces is rewritten only if the test's purpose is kept, and the
  task report lists it as a plan deviation.
- **Commit order after parent-side adoption**: when a conflict forces
  re-implementation on the parent's version, re-append the task's case block
  in a commit before the commit that re-applies the hook change.
- **Test runs**: every hook change is followed by both test entry points in
  the same change (`.claude/rules/hook-tests.md`), and the project suite
  passes before the task merges.
- **File scope**: no task touches a file outside its declared list.

## Cross-task Design Decisions

### D1: Five parallel tasks split by code locality
task0001 takes FR2 and FR8 (the same tail checks); task0002 takes FR1 and
FR4 (subscript reading); task0003 takes FR3 and FR5 (the line index and the
close-line rule); task0004 takes FR6 (blanks); task0005 takes FR7 (the
command form of `${`). Each task appends only its own cases and pins only its
own forms, so each branch ends with a green suite while its cases precede its
fix in that branch's history (FR9). Affected: all tasks.

### D2: Ownership of hook code regions
The Shared Components rows assign each part of the lexer and its consumers
to one task: tail gate, the `$((` / `$[` / parameter-form `${` gating, the
`((` at a command position, the `case` transition and statement-level case
shaping (task0001); subscript reading and `NAME[` detection (task0002); line
index, delimiter reader and close-line rule (task0003); blank sets, tokenizer
blanks and trailing-`\r` matching (task0004); the command form of `${`, its
frame, its close, and its downstream handling (task0005). Textual overlap is
limited to the `${` branch of the `$` handling (task0001, task0005), the word
transition (task0001, task0002, task0005) and the tail of the case table.
Affected: all tasks.

### D3: Order-agnostic placement check
task0001 owns one placement test: no label at an index below 769 contains
any of the seven stable_ids that get cases (5753be9288beab27,
52bfa0f59d1ea852, e959ba60bde865a4, e25427e2a8b1dddf, 2b52be5874de85f4,
aa735aa95be36542, 1fcae1f76f2a20f0), and the first 769 entries are unchanged
from the base. Each task additionally finds its own cases by label and
command text at index 769 or later. The check holds whichever subset of the
five blocks is present, on every branch and after every merge order (FR10,
FR11). Affected: all tasks (task0001 implements the shared test).

### D4: The command form of `${` opens after a tail source
SPEC.md FR2 says no `${` opens after a tail source. Read with FR7, that
applies to the parameter form: its content is hidden from inspection. The
command form `${ ` / `${|` runs its content as commands in bash 5.3, exactly
as `$(` does, and SPEC.md's edge case F2 keeps `$(` opening in the tail for
that reason. Keeping the command form literal there would turn its content
into arguments of the preceding command and hide a destructive command bash
runs, against NFR6. So the gate never refuses the command form; only the
parameter form is refused. Affected: task0001, task0005.

### D5: Refused openers are listed in UNOPENED
An expansion opener the tail gate refuses is recorded like a settled opener:
its offset is in the map's UNOPENED and its characters stay literal. The
masked view hides only quote characters among them, as today. Affected:
task0001 (task0005's command form is never refused).

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| All five tasks append at the tail of the case table, so later merges conflict there | High | Low | Parent-side adoption, then re-append the task's own block (commit order convention); tests find cases by label, not index |
| Overlapping edits in the `${` branch, the word transition and the tail checks of the single pass conflict textually | High | Medium | Ownership rows and D2; re-implement on the parent's version per the adoption protocol |
| The tail rule (task0001) and the command form (task0005) disagree on a `${` after a tail source | Medium | High | D4 fixes the reading; lexical pin ownership keeps both branches' tests valid; the verify phase runs TS-2 and TS-18 on the integrated tree |
| Reading `\r` as a word character turns a denied destructive word into an unmatched one (`git reset --hard\r`) | Medium | High | Trailing `\r` disregarded when matching (task0004); deny cases pin both edge forms |
| The `\n`-only line index changes what another reader of the index cuts or anchors | Low | High | task0003 checks every reader; stage agreement runs over every case-table command |
| Continuation joining computed over the whole text misses a body's first line after a backslash-ended line and hides the following lines | Medium | High | First-line rule in the close-line contract; task0003 pins the quoted-then-unquoted form |
| Deeply nested unclosed command forms make the statement layer rescan each level | Medium | Medium | The relative scan budget answers ask (deny in batch); task0005 pins the 60 KB inputs within 10 seconds |
| The gate refactor changes a pre-existing tail decision | Low | High | Pure refactor for existing kinds (task0001 AC); full suites, including the whole-text-restart map equivalence, stay green |
| A change flips the verdict of an existing case | Low | High | Existing cases are fixed points; stop and report |
| bash 5.3 is not available to confirm a form beyond SPEC.md | Low | Low | The form is pinned in the agreement test only and reported as unconfirmed; the fail-safe direction still governs the code |

## Open Questions
- None blocking. D4 records how FR2 and FR7 combine for a `${` after a tail
  source.
