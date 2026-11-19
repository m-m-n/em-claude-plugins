# Implementation Plan: mcp-bridge-args-json-exec-guard

## Overview
destructive-guard gains a statement-level step that rebuilds the `--args-json`
value of every `mcp-bridge run` statement other than the notion pair, decodes
it as JSON, and queues the substitution candidates of every decoded string and
every top-level `command` string for the ordinary re-scan. task0001 builds and
wires the step and pins it with cases; task0002 updates the existing in-code
explanations that describe how `--args-json` is handled.

## Technology Stack
- **Language**: Python 3 (the existing hook script, its case runner and the
  unit tests under `tests/`).
- **Key libraries**: the language's standard library only. JSON decoding uses
  the standard library's JSON decoder. No new dependency is introduced, so no
  dependency license is recorded (`project.license`: none).

## Layer Structure
- **Hook**: `em-workflow/hooks/destructive-guard.py`. The new step sits in the
  statement loop of `statements()`, after a statement is yielded, next to the
  existing `-c` / `eval` / here-string payload extraction. It only adds chunks
  to `pending`; the raw-string scan before it is unchanged.
- **Case suite**: `em-workflow/hooks/tests/destructive-guard-cases.json`, read
  by `em-workflow/hooks/tests/run-destructive-guard.py`.
- **Unit tests**: `tests/`, run by `python3 -m unittest discover -s tests`.
- Dependency direction: case suite and unit tests to hook only.

## Shared Components
| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| `_mcp_bridge_args_json_chunks()` (new function in `em-workflow/hooks/destructive-guard.py`) | For one statement, decide whether it is an inspected `mcp-bridge run` statement (FR1, FR2, FR6) and, when it is, produce what `statements()` queues (FR3 to FR5) | Pre: a statement that `statements()` yielded from a lexed segment, given as its shaped words and the chunk's marked text. Post: the result is exactly one of three kinds. (1) Not inspected: the statement is not a target (FR1), its options determine the notion pair (FR2), or it is one of the FR6 forms. (2) Inspected: the scan charge of the rebuild, the decode and the walk; the candidate bodies found in every decoded string value (FR4); the top-level `command` string values (FR5); each list in document order; and the `--args-json` value word they are anchored at. (3) Overrun: the JSON nesting is deeper than `MAX_ARGS_JSON_DEPTH`, or the decoder failed for a reason other than a JSON syntax error. It evaluates, executes and reads nothing, and changes no token, no marked text and no state of `statements()`. Internal helpers are the building task's choice | task0001 (builds it and calls it from `statements()`), task0002 (names it in the explanations) |
| `MAX_ARGS_JSON_DEPTH` (new module constant, value 100) | The deepest JSON nesting the step decodes (decision D3) | A value nested deeper gives the Overrun result before the decoder runs | task0001 (defines and uses it), task0002 (may name it) |

## Conventions
- **Fail-closed (NFR2)**: the step only adds chunks to `pending`. It removes
  no chunk the existing scan queues, and it never turns an existing deny or ask
  into allow.
- **Case format**: `.claude/rules/hook-tests.md`. New cases carry no fourth
  element, except the two TS-15 cases, which pin the reason ID (A6).
- **Existing cases**: none is removed or edited (FR9).
- **Explanation ownership**: the docstrings and comments that FR10 names
  (`_single_quote_skip_spans()`, the single-quote candidate paragraph of
  `scan_structure()`, the `statements()` docstring and the comment in its
  queueing loop, the out-of-scope declaration of
  `extract_shell_payload_anchored()`) are changed by task0002 only. task0001
  writes the docstring of the new component and a short call-site comment, and
  edits none of the FR10 sites.
- **Language**: docstrings and comments in English; case labels in Japanese,
  like the existing labels, each naming this feature and the case ID.
- **Change set**: no plugin manifest and no marketplace entry is part of either
  task's files (NFR4).

## Cross-task Design Decisions

### D1: The step is additive and runs at every statement
- **Decision**: the step runs for every statement that `statements()` yields
  from a lexed segment, in every chunk (top level, `&&` / `;` / `|` chains,
  behind wrappers, substitution bodies, payloads). The raw-string
  single-quote skip of `_single_quote_skip_spans()` keeps its present
  conditions (W1 to W4, C1, S1, S2, top-level chunk only).
- **Basis**: FR1, FR2, NFR2.
- **Affected tasks**: task0001 implements it; task0002 describes it.

### D2: Which statements are inspected
- **Decision**: the command word that `head()` returns over the statement's
  shaped words is exactly `mcp-bridge` and is not a substitution, and the next
  word is exactly `run`. The words after `run` are read with the canonical flag
  reading of mcp-bridge-exec-tool-rescan (its IMPLEMENTATION.md decision D1):
  a word in flag position is one of `--mcp`, `--tool`, `--args-json`,
  `--format`, `--session` (each takes the next word as its value) or
  `--dry-run`, written as one unquoted run. FR2 excludes the statement only
  when that reading also determines the pair: `--mcp`, `--tool` and
  `--args-json` each once, the `--mcp` value `notion` and the `--tool` value
  `notion-create-comment`, each written as one unquoted run. Otherwise the
  statement is decoded when `--args-json` appears exactly once and every
  `--mcp` and `--tool` value word present is static. A missing or repeated
  `--mcp` / `--tool` does not stop the decode.
- **Basis**: FR1 to FR3, FR6 ("宛先が静的に決まらない形" is read as a non-static
  value word), NFR2. A missing or repeated `--mcp` / `--tool` leaves no
  determined pair, so decoding it is the fail-closed reading.
- **Affected tasks**: task0001 implements it; task0002 describes it.

### D3: Decoder failures and the nesting bound
- **Decision**: a value that the decoder rejects with a JSON syntax error is an
  FR6 form (not inspected). Every other decoder failure, and nesting deeper
  than `MAX_ARGS_JSON_DEPTH`, is the Overrun result, which `statements()`
  turns into the same scan-budget early stop as its own budget overrun
  (`scan-budget-exceeded` ask; deny under batch). The nesting is measured
  before decoding, outside JSON strings. The walk over the decoded value is
  iterative.
- **Basis**: FR7, NFR1. A value that only the guard's decoder fails on, while
  mcp-bridge or the MCP server decodes it, must not fall to the FR6 path, which
  keeps today's verdict (THREAT-MODEL.md TM-3).
- **Affected tasks**: task0001 implements it; task0002 describes it.

### D4: Scenario commands use the escape forms the SPEC text lost
- **Decision**: SPEC.md TS-1, TS-2, TS-6, TS-7, TS-9 and TS-14 are written
  with the JSON escapes for `$` and the backtick, `$` and ```. The
  SPEC.md text shows a bare `$(` or backtick at those places.
- **Basis**: with a bare `$(` inside single quotes, TS-1 is the existing
  mcp-bridge-exec-tool-rescan TS-1 case, which is deny before this change, and
  TS-14 is deny under today's verdict. SPEC.md calls these forms "JSON のエスケープ"
  and expects allow before the change (AC-1) and allow for TS-14. Both hold only
  with the escape form. The source review finding of this feature also names
  the `$(` form. SPEC.md is not rewritten in this run.
- **Affected tasks**: task0001 (cases); VERIFICATION.md uses the same
  commands.

### Out-of-scope forms (FR8)
The forms below are stated with the same scope in the docstring of
`_mcp_bridge_args_json_chunks()` (task0001), in the out-of-scope declaration
of `extract_shell_payload_anchored()` (task0002), and in the labels of TS-10,
TS-13 and TS-14 (task0001).
- **O1**: a command written as plain text, without a substitution, in a key
  other than the top-level `command` (for example the `input` of
  desktop-commander's `interact_with_process`), or in a `command` key below
  the top level. Only the FR4 candidate search applies there (TS-10).
- **O2**: the FR6 forms, which keep the raw-string verdict:
  - a value word set by a substitution or a variable expansion, or otherwise
    not static (a substitution Bash itself runs is still re-scanned) (TS-13);
  - a destination whose `--mcp` or `--tool` value word is not static;
  - a value that does not decode as JSON (TS-14);
  - `--args-json` missing, repeated, or written in the `=` form;
  - words after `run` that do not read as the canonical flag sequence;
  - a decoded value whose top level is not an object.

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| The decode path turns an existing allow case into deny or ask (a false deny stops an unattended run) | Low | Medium | Only the notion cases among the existing allow cases use `mcp-bridge run --args-json`, and FR2 excludes them; the full case suite runs in both tasks and in verify |
| A parser difference between the guard and mcp-bridge (duplicate keys, nesting) hides a destructive value | Medium | High | D3 and the all-pairs walk; THREAT-MODEL.md TM-2 and TM-3 |
| An FR6 form that mcp-bridge still reads (single-dash flag, `=` form, `--` or a positional word after the value, repeated `--args-json`, an ANSI-C escape `_decode_ansi_c()` does not decode) keeps today's verdict, allow | Medium | High | Accepted by SPEC.md FR6 / FR8; recorded in THREAT-MODEL.md Rationale and in Open Questions |
| task0001 and task0002 edit the same file in parallel | Medium | Low | Disjoint regions by the explanation-ownership convention; task0002 names only the component pinned above |
| The JSON escapes in a case command are decoded once too often when the case file is written | Medium | Medium | task0001 checks each stored command against the shell text of its scenario; the pre-change run shows the new deny cases as allow |

## Open Questions
- [ ] SPEC.md lost the JSON escapes in its Overview and in TS-1, TS-2, TS-6,
  TS-7, TS-9 and TS-14 (D4). The plan uses the escape forms; whether SPEC.md is
  corrected later is open.
- [ ] The FR6 forms that mcp-bridge reads anyway (single-dash flags, the `=`
  form, `--` or a positional word after the value, a repeated `--args-json`,
  ANSI-C escapes outside `_decode_ansi_c()`) keep today's verdict, which is
  allow when the raw text shows no substitution. Sending them to ask is a
  candidate for a later feature, weighed against the false-deny cost under
  batch.
