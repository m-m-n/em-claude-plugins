# Implementation Plan: mcp-bridge-function-shadow

## Overview
The notion-pair exclusion of the `mcp-bridge run --args-json` decision in
`em-workflow/hooks/destructive-guard.py` is lifted when an override or
shell-state construct stands in the statement's chunk or in its enclosing
chain. task0001 builds the lift; task0002 (review round 1 rework) extends the
readings through which a notion statement reaches it. Both tasks declare the
same three files, so this document pins the contracts and conventions they
share.

## Technology Stack
- **Language**: Python 3, standard library only (the hook's existing runtime)
- **New dependencies**: none

## Layer Structure
All layers live in the one hook file.

1. **`--args-json` decision** — `_mcp_bridge_args_json_chunks()` and its
   notion-path readers (the lifted-notion statement reading and the env
   reading of a child shell payload).
2. **Lift** — the chain decision over the per-chunk scan.
3. **Reading helpers (existing)** — the chunk lexing, substitution marking
   and statement shaping that `statements()` applies, and the word-restoring
   helpers of the `--args-json` step.

Allowed directions: the decision asks the lift; the decision and the lift
both use the reading helpers. The lift never asks the decision.
`statements()` references no name that holds `args_json` (pinned by
`TestStructure`), and the lift reads statements only through the same
shaping helpers `statements()` uses.

## Shared Components
| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| `_args_json_notion_lifted(marked)` | Chain decision: whether the notion-pair exclusion is lifted for a statement lexed from one chunk | Pre: MARKED is the marked text of the statement's chunk, registered with its derivation link; None is allowed. Post: true when MARKED or a chunk of its enclosing chain, up to the command's own chunk, holds a construct per `_args_json_shadow_scan()`; None, or a derived chunk without a link, gives true; the chain is walked in a loop, never by recursion; the answer is kept on every chunk the walk visits, so the scan runs at most once per chunk in one `statements()` run; the nameref answer and its cache are neither read nor written | task0001 (builds), task0002 (asks it for a statically restored command word and for the statements of an env-reached `bash -c` payload) |
| `_args_json_shadow_scan(marked)` | Per-chunk scan for the constructs of FR1 to FR3 | Pre: MARKED is one chunk's marked text. Post: reads only that chunk's own text, never its enclosing chunks and never the bodies of its substitutions; true when an FR1 construct stands at command position as `_overrides_command_name()` reads it, when an FR2 statement or current-shell substitution is present, or when a word holds an FR3 word or `BASH_CMDS` as a substring; true on the fail-safe conditions (no lexer regions, a parse-failure fallback statement); false otherwise | task0001 (builds), task0002 (adds the static-run match of the substring check) |
| `_args_json_notion_pair()` (existing, unchanged) | Canonical notion-pair predicate | Asked before the lift for every candidate statement; the lift is never asked for a statement the predicate rejects | task0001, task0002 |
| Chunk derivation link (the outer chunk a derived chunk records) | The chain the lift walks | Every derived chunk the `--args-json` decision reads records the chunk it was derived from; a payload chunk built by the notion-path env reading records the statement's own chunk, so the chain reaches the words around the payload | task0001 (walks it), task0002 (sets it on the payload chunk) |
| `_ARGS_JSON_SHADOW_ENVIRONMENT_WORDS` | The FR3 words `BASH_FUNC_` and `BASH_ALIASES` | Read only by the per-chunk scan; never added to `OVERRIDE_BUILTINS`, `OVERRIDE_VARIABLE_NAME`, `STOP_COMMAND_WORDS` or `STOP_VARIABLE_NAMES` | task0001 (defines), task0002 (matches it on static runs) |

## Conventions
- **Fail-safe direction**: a lift reading that cannot be completed answers
  "lifted". A notion-path reading that cannot restore a word answers "not
  this statement" and sets no Unrestorable flag, so no command gets a new
  `args-json-unrestorable` ask.
- **Notion path only (FR7)**: every reading the feature adds is reached only
  where `_args_json_notion_pair()` answers true. `head()`,
  `_skip_assignments_and_wrappers()`, `_deferral_head()`, the shell-payload
  extraction, `override_seen`, the heredoc data decision, the masking stop
  and the shared vocabularies keep their behaviour.
- **Descriptive text (FR8)**: each function the feature adds or changes
  states its contract and the requirement IDs it serves in its docstring;
  `TestDocstring` pins the phrases.
- **Runner case table**: the diff of
  `em-workflow/hooks/tests/destructive-guard-cases.json` adds lines only; each
  form of a scenario is one case; labels start with
  `mcp-bridge-function-shadow TS-n`, followed by a Japanese description.
- **Unit-test module**: tests are added as new classes or new last methods of
  `TestDocstring` in `tests/test_destructive_guard_args_json.py`; existing
  methods stay unchanged.
- **NFR1 baseline**: base_branch at the integration base (the `base_commit` of
  the `implement` step in `workflow.yaml`) is the reference for the unittest
  suite, compared as VERIFICATION.md TS-16 states. No task edits a test file,
  or any file outside the feature's declared change set, to make a test that
  already fails on that baseline pass (SPEC.md Assumptions).

## Cross-task Design Decisions

### D1: The lift is asked after the pair predicate
- **Decision**: the chain decision is asked only for a statement the
  notion-pair predicate accepts.
- **Rationale**: the chain is never walked for any other pair, so the decision
  for other pairs cannot change (FR7) and the scan cost stays bounded to
  notion statements (NFR2).
- **Affected tasks**: task0001, task0002.

### D2: The chain follows the derivation link, not the enclosing text
- **Decision**: the enclosing chain is the sequence of chunks reached by each
  chunk's recorded derivation link, and each chunk is scanned on its own text.
- **Rationale**: a sibling chunk is on no chain (SPEC.md Assumptions), each
  answer can be kept per chunk, and the walk needs no recursion (FR4, NFR2).
- **Affected tasks**: task0001 (builds the walk), task0002 (links the payload
  chunk it builds).

### D3: Readings that undo quoting stay on the notion path
- **Decision**: the statically restored command word, the env reading of a
  child shell payload and the static-run match are used only by the notion
  path and the lift.
- **Rationale**: FR7 keeps the decision for other pairs and every other check
  unchanged; the follow-ups for other checks are listed in task0002's Out of
  Scope.
- **Affected tasks**: task0002 (adds the readings), task0001 (owns the scan
  the static-run match extends).

### D4: NFR1 is judged against the integration-base baseline
- **Decision**: a unittest failure or error counts against NFR1 only when the
  same test passes on base_branch at the integration base, or when its test
  file is in this feature's diff.
- **Rationale**: SPEC.md NFR1, AC9 and TS-16 as revised.
- **Affected tasks**: task0001, task0002 (their NFR1 criteria are verified
  under this baseline in VERIFICATION.md).

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| A change to statement shaping in `statements()` is not followed by the per-chunk scan, so a construct at command position is missed | Low | High (the bypass returns) | The scan reads statements through the same shaping helpers as `statements()`; runner cases TS-1 to TS-9 and TS-17 pin the deny verdicts |
| The lift is applied too widely, turning legitimate notion comments into deny or ask | Low | Medium (unattended runs stop) | Fail-safe only on unreadable input; TS-11 to TS-15, TS-25 and TS-27 pin the allow verdicts |
| A unittest failure unrelated to this feature, already present on the baseline, is read as a regression of this feature | Medium | Medium (verify fails without a defect in the feature) | TS-16 compares the failing / erroring test ids with base_branch at the integration base |

## Open Questions
- None.
