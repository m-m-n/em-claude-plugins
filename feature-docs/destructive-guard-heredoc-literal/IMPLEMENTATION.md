# Implementation Plan: destructive-guard-heredoc-literal

## Overview

`em-workflow/hooks/destructive-guard.py` reads the content of closed ordinary
string literals in a Python-program heredoc body as data (task0001, merged).
After the SPEC change, that reading stops for the whole command whenever the
command holds a statement that replaces a command name, changes shell state or
variable attributes, or has a command word that cannot be fixed statically as
a single word, read through any number of nested `builtin` / `command` words
(task0002, FR9 / NFR5). This document holds only what the two tasks share.

## Technology Stack

- **Language**: Python 3, standard library only (NFR1). No new dependency is
  introduced, so no dependency license is recorded (`project.license` is
  `none`).
- **Test**: the expectation suite that
  `em-workflow/hooks/tests/run-destructive-guard.py` runs over
  `em-workflow/hooks/tests/destructive-guard-cases.json`, plus the project
  unittest discovery.

## Layer Structure

One hook script, no new layer. Inside it, one traversal reads the command
chunk by chunk (the command itself, substitution bodies, payloads, queued
heredoc bodies). For each heredoc the destination decision picks sink, data,
undetermined or Python program. For each statement the traversal reads, two
per-statement readings may raise run-wide flags (the FR7 override flag and the
masking-stop flag), and the per-statement rule checks decide allow, ask or
deny. The case file pins the decisions from outside the script.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| Python-program masking path | The "Python program" destination outcome, the literal scan and masking, and the body handling that queues the masked text and parks the original body | Pre: the heredoc meets every eligibility condition (FR2). Post: while the masking-stop flag is down, the masked text is queued in place of the body and the original is parked; when the flag is up at that point, or the literal scan cannot settle the body (FR6), the body is queued whole as a sink body is; a parked original is queued whole once the flag is raised. For an unquoted delimiter, the substitutions of the original body are also extracted and queued (FR5). The path never touches the FR7 override flag or the handling of data heredoc bodies. task0002 adds one mark to what this path queues (the Python-body chunk mark, D4) and changes nothing else in it. | task0001 (built it), task0002 (marks its chunks) |
| Masking-stop flag | One run-wide flag per hook invocation that ends literal masking for the rest of the command | Pre: none. Post: raised by the masking-stop check for any statement the traversal reads, lexed or through the parse-failure fallback, wherever that statement stands relative to the heredoc; raised at most once; raising it queues every parked original whole exactly once and prevents any further masking; raising it never raises the FR7 override flag (D1). | task0001 (introduced it), task0002 (changes what raises it) |
| Override reading (FR7) | The existing per-statement detection of command-name override constructs (a function definition, an override builtin as the command word, also behind one `builtin`, a PATH assignment, the override variable name in any word), in a lexed form and a fallback form for statements that do not lex, that turns data-heredoc judgments undetermined | The words it matches and its one-level `builtin` reading are unchanged by this feature (SPEC A-5). Every statement it flags also raises the masking-stop flag (NFR5). Its vocabulary (the override builtin set and the override variable-name definition) is the base the masking-stop vocabulary is derived from (D2). | task0001 (TM-2), task0002 (derivation) |
| Command-word reading | The existing reading that skips assignments, wrappers (with their options and option values) and mise/asdf exec prefixes to find a statement's command word, and passes over a word built entirely from a command substitution | Unchanged by this feature. Every other check keeps reading it. The FR9 check does not use its result directly; it reads the same skip vocabulary by name (D3). | task0001 (FR2 (a)), task0002 (vocabulary only) |
| Expectation case file | Pins the guard's decisions | Every case has three elements (decision, label, command), no fourth element; existing cases are never removed or rewritten; each new label is a Japanese label that starts with the feature name and the scenario ID (a letter suffix per case where a scenario has several), unique in the file; no command holds a machine-specific path or a home-directory path. | task0001, task0002 |

## Conventions

- **Fail-closed**: a shape a check does not positively recognise keeps the
  decision the guard returned before this feature.
- **Unchanged guard**: "the unchanged guard's decision" means the decision of
  `em-workflow/hooks/destructive-guard.py` at `workflow.implement.base_commit`
  for the same command.
- **Cases first**: new cases are added to the case file before the guard is
  changed (`.claude/rules/hook-tests.md`); the FAIL lines of that first run
  are the red state.
- **Change scope (NFR3)**: only `em-workflow/hooks/destructive-guard.py` and
  `em-workflow/hooks/tests/destructive-guard-cases.json` change;
  `em-workflow/.claude-plugin/plugin.json` and
  `.claude-plugin/marketplace.json` are not edited.
- **No evaluation (NFR1)**: no text of the command is evaluated, executed,
  compiled or imported; restoring a quoted or escaped word is done by the
  guard's own reading of its characters.

## Cross-task Design Decisions

### D1: The masking-stop flag stays separate from the FR7 override flag

- **Decision**: what FR9 adds (nested `builtin` / `command` reading, state
  builtins, statically undeterminable command words, restored words,
  `BASH_ALIASES`) raises only the masking-stop flag. The FR7 override flag
  keeps exactly the constructs it reads today.
- **Rationale**: SPEC A-5 keeps the data-heredoc judgment unchanged; TS-31
  pins that a data heredoc in a command holding `builtin builtin alias` keeps
  its decision.
- **Affected tasks**: task0001 (flag introduced), task0002 (stop check).

### D2: The masking-stop vocabulary is derived from the override vocabulary

- **Decision**: the stop check's command-word vocabulary is the override
  builtin set joined with the FR9 (2) state builtins, and its variable-name
  vocabulary is the override variable-name definition joined with
  `BASH_ALIASES`. Each joined set refers to the override definition by name;
  no word is written in two lists (NFR5).
- **Rationale**: a word later added to the override vocabulary then also stops
  masking, and every statement the override reading flags stops masking
  (NFR5).
- **Affected tasks**: task0001 (override reading, unchanged words), task0002
  (derivation).

### D3: One function removes `builtin` / `command` for the FR9 check

- **Decision**: the FR9 check reads a statement's command word through one
  function that removes, in a loop, assignments, the wrappers of the
  command-word reading (by its vocabulary, referred to by name) and any number
  of `builtin` / `command` words with their options and `--`. That function is
  the only place the FR9 check removes `builtin` / `command`. The command-word
  reading and the override reading's one-level `builtin` reading are not
  replaced by it.
- **Rationale**: NFR5 requires the removal in one function; SPEC A-5 keeps the
  other readings unchanged.
- **Affected tasks**: task0001 (readings left as they are), task0002 (the
  function).

### D4: Python-body chunks are exempt from FR9 (3) only

- **Decision**: a chunk queued from the body of a heredoc whose destination is
  "Python program", and every chunk derived from such a chunk, carries a
  Python-body mark. FR9 (3) (the statically undeterminable command word) is
  not applied to the statements of a marked chunk. Two kinds of chunk are not
  marked: the substitutions the FR5 extraction queues from an unquoted
  delimiter's original body, and the substitution bodies and unclosed command
  forms found in the body chunk of a heredoc whose delimiter is unquoted —
  the shell evaluates these before Python reads the body — together with
  everything derived from them. FR9 (1) and (2), the override reading and
  every other check apply to marked chunks as before.
- **Rationale**: SPEC FR9, last paragraph. The code of a Python program read
  as shell commonly holds `*`, `[...]`, `{...}` and `~` at the command-word
  position (TS-40, TS-43); applying FR9 (3) there would deny the reproduction
  again.
- **Affected tasks**: task0001 (queues the chunks), task0002 (marks them and
  reads the mark).

### D5: Scenario numbering

- **Decision**: SPEC scenarios are TS-1 to TS-16 and TS-28 to TS-40.
  Planner-added scenarios are TS-17 to TS-27 (task0001) and TS-41 to TS-45
  (task0002).
- **Affected tasks**: task0001, task0002.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| The stop condition fires on the statements read from a Python-program body itself, so ordinary bodies lose masking and the reproduction (TS-1, TS-2) is denied again | Medium | High | D4; TS-1 to TS-6, TS-17, TS-18, TS-27, TS-40 and TS-43 stay in the suite as allow cases |
| The exemption of D4 reaches a substitution the shell evaluates, so a state change hidden there keeps another body masked | Low | High | D4 names the unmarked chunks; TS-42 pins it |
| The nested `builtin` / `command` reading leaks into the FR7 override reading and changes data-heredoc decisions | Low | Medium | D1; TS-31 pinned at the unchanged guard's decision; the full suite |
| The lexer answers an extended-glob or brace command word with an `ask` instead of letting the stop check see it, so a SPEC case cannot reach `deny` | Medium | Medium | task0002 reports it as a plan deviation instead of changing the lexer |
| task0002 edits the same two files task0001 changed | Low | Low | task0001 is merged; task0002 starts from the integration branch that holds it, and no other task runs in parallel |

## Open Questions

None.
