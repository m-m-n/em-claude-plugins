# Implementation Plan: cd-prefix-toplevel-operators

## Overview

`em-workflow/hooks/bash_guard.py` stops allowing the cd prefix form
`cd "{worktree_path}" && <approved string>` when the approved string could
run partly outside the worktree (a lone `&`, `;`, `||` or a line break at its
top level, or a construct the hook does not parse). The documents and tests
are aligned with the hook in the same change. This file holds only the
decisions the three tasks share. Inside tables, a pipe character of a shell
token is written escaped so the table renders; the token itself is a plain
pipe.

## Technology Stack

- **Language**: Python 3, standard library only (NFR1) — the hook and every
  test module.
- **Test framework**: standard-library unittest, run as
  `python3 -m unittest discover -s tests` from the repository root (NFR7).
- **Documents**: Markdown. English for `command-execution-protocol.md`,
  `workflow-schema.md`, `implementer.md`, the worktree-task-workflow
  `SKILL.md` and the hook docstring; Japanese for `em-workflow/README.md`
  (each document keeps its current language).
- **New dependencies**: none. No license record is needed.

## Layer Structure

| Layer | Members | Responsibility |
|-------|---------|----------------|
| Enforcement | `em-workflow/hooks/bash_guard.py` (task0001) | Decides allow / deny / no decision deterministically |
| Contract statement (SSOT for the condition list) | `em-workflow/references/command-execution-protocol.md`, Verbatim execution rule (task0002) | States every condition of the cd prefix allowance in full |
| Summaries | README 実行時強制 item, workflow-schema Command approval store (task0002); implementer.md Step 3, SKILL.md Command execution gate (task0003); hook module docstring (task0001) | Summarize the condition and cite the protocol |
| Tests | one new module per task under `tests/` | Pin the behavior and the wording |

Dependency direction: summaries cite the protocol; the protocol and the hook
docstring both state rule C1 below; nothing cites a summary as its source.

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| C1: cd prefix exclusion rule | Decides whether the remainder of a cd prefix form is excluded from the cd prefix allow | Pre: R is the remainder (everything after the first `&&` of the cd prefix form) with surrounding whitespace removed — the same string that is compared with the approval store. Post: "excluded" when any rule E1–E10 below fires, otherwise "not excluded". Pure: no file read, no child process, no LLM; the same R always gives the same answer | task0001 (implements, docstring), task0002 (states in full in the protocol; summarizes in README and schema), task0003 (summarizes) |
| C2: hook decision order | Orders the hook's checks so that the exclusion only narrows the cd prefix allow | Pre: the whole command, already stripped. Post: the decision of steps 1–8 below; no command gets a deny that the hook before this change would not give it | task0001 (implements), task0002 (the protocol's decision table keeps its rows and order) |
| C3: document anchors | Headings other tasks and existing tests locate text by | Post: none of these headings is renamed, removed or re-levelled: protocol "Verbatim execution rule" and "Runtime enforcement (hook decision table)"; workflow-schema "Command approval store (outside the repository)"; README numbered item containing 実行時強制; implementer.md "Step 3: Verify the worktree"; SKILL.md "Command execution gate (workflow.yaml strings)". No new heading is added inside these sections | task0002, task0003 |
| C4: shared wording | Keeps the summaries consistent with the protocol | Post: every summary names the four top-level operators — `&`, `;`, `\|\|` and the line break — with the words "top level" (English) or トップレベル (Japanese), and cites `references/command-execution-protocol.md` for the full list. The implementer handling is stated in English as: the implementer does not run such an approved string, and reports it in `notes`. The two implementer instruction sources (implementer.md Step 3, SKILL.md Command execution gate) also state the report value when that string is the test command (`project_commands.test`): `tests: "fail"`, with `notes` saying the test command was not run because the cd prefix form does not cover it. Summaries do not restate rules E5–E10 | task0002, task0003 |

### C1 detail: scan model

One left-to-right pass over R with three quoting states:

| State | Behavior |
|-------|----------|
| Unquoted | `'` enters single-quoted; `"` enters double-quoted; a backslash escapes the next character, and an escaped character is never counted by any rule |
| Single-quoted | Every character is ordinary, a backslash included; only `'` returns to unquoted |
| Double-quoted | A backslash followed by `$`, a backtick, `"`, a backslash or a line break escapes that character; any other backslash is an ordinary character; an unescaped `"` returns to unquoted |

Token recognition in the unquoted state, longest match first: `&>>`, then
the two-character tokens `&&`, `&>`, `|&`, `>&`, `<&`, `||`. A token is
consumed as one unit; the `&` inside `&&`, `|&`, `>&`, `<&`, `&>` and `&>>`
is not counted. A `|` that starts none of these tokens is a pipe and is not
counted. So `&&&` is `&&` followed by a lone `&`.

### C1 detail: exclusion rules

| ID | R is excluded when | Where the rule looks | Source |
|----|--------------------|----------------------|--------|
| E1 | a lone `&` appears (an `&` that is not part of a recognized token) | unquoted, unescaped | FR2 |
| E2 | a `;` appears | unquoted, unescaped | FR2 |
| E3 | the token `\|\|` appears | unquoted, unescaped | FR2 |
| E4 | a line break (LF or CR) appears | anywhere, inside quotes included | FR2, FR3 |
| E5 | the scan ends inside a single- or double-quoted state (unclosed quote) | end of scan | FR3 |
| E6 | the scan ends on a backslash that has no following character (trailing backslash) | end of scan, outside single quotes | FR3 |
| E7 | the two-character sequence `$'` or `$"` appears | anywhere | FR3 |
| E8 | `#` appears | anywhere, inside quotes included | FR3 |
| E9 | `(`, `)`, `{` or `}` appears | unquoted, unescaped | FR3 |
| E10 | `$(`, `${` or a backtick appears | anywhere — unquoted, inside double quotes, and on the safe side inside single quotes too | FR3 |

Nesting is never parsed (FR3): one hit of any rule is enough.

### C2 detail: decision order

1. The hook strips the whole command (unchanged).
2. The command is workflow-relevant when the whole command is declared in a
   workflow.yaml, OR the whole command is approved, OR it is a cd prefix
   candidate: it meets the existing syntax condition, its trimmed remainder is
   approved, and its path meets the existing path condition. C1 plays no part
   in this step.
3. Not workflow-relevant → no decision.
4. A refusal pattern matches the whole command → deny (FR5, unchanged reason
   and guidance).
5. The whole command is approved → allow (exact-match reason, unchanged).
6. It is a cd prefix candidate AND C1 says "not excluded" → allow (cd prefix
   reason, unchanged).
7. The whole command is declared → deny (unapproved reason, the
   unapproved-deny guidance unchanged — SPEC A6).
8. Otherwise → no decision. Only an excluded cd prefix candidate whose whole
   string is neither approved nor declared reaches this step (FR4, A3).

## Conventions

- **Standard library only** in the hook and in every new test module (NFR1,
  NFR7).
- **Test module ownership**: each task creates exactly one new module under
  `tests/` and edits no existing test module. The existing modules —
  notably `tests/test_bash_guard_cd_prefix.py`,
  `tests/test_cd_prefix_exception_docs.py`,
  `tests/test_implementer_cd_chain_docs.py`,
  `tests/test_worktree_skill_instruction_source.py` and
  `tests/test_hook_classification_pin.py` — stay as they are and keep passing
  (NFR2, NFR5, NFR6).
- **Hook-test method** (FR10): run the hook as a subprocess with PreToolUse
  JSON on standard input; select a temporary approval store through
  `EM_WORKFLOW_APPROVALS`; remove `CLAUDE_PROJECT_DIR` from the environment;
  use temporary git repositories; compare realpaths. Approved strings that
  the record CLI cannot store (a line break inside, or a refusal pattern) are
  written to the store file directly.
- **Document-test method** (FR10): slice the text by heading, normalize
  whitespace, assert stable phrases, never line numbers. Every absence
  assertion is paired with a forged-text case that proves its matcher fires.
- **Untouched files**: `em-workflow/hooks/queue_launch_guard.py`,
  `em-workflow/scripts/merge-task.sh` and `em-workflow/hooks/hooks.json` are
  not edited by any task (NFR3). No task edits a plugin version field (NFR4).
- **Doc redaction**: no absolute home-directory path and no Notion URL in
  any document or test.

## Cross-task Design Decisions

### D1: Exclude, do not change the execution form

The execution form `cd "{worktree_path}" && <approved string>` stays as it is
(SPEC A1). A string that cannot run entirely in the worktree under that form
loses the cd prefix allow instead. Affects all tasks: the documents describe
an exclusion, not a new form.

### D2: Safe-side rules are position-independent where FR3 gives no position

FR3 names `$'`, `$"`, `$(...)`, `${...}` and the backtick without a quoting
position, and states `#` and the line break regardless of position. C1
applies E4, E7, E8 and E10 anywhere in R. Excluding too much costs only a
fall back to the unchanged decision table (never a new deny); excluding too
little lets part of a string run in the main working tree. Affects task0001
(implements) and task0002 (the protocol states the same positions).

### D3: Relevance is unchanged; only the allow is narrowed

If the exclusion also removed a candidate from the workflow-relevant set, an
approved refusal-pattern string with a top-level `&` would fall from deny to
no decision. C2 keeps step 2 as before and applies C1 only in step 6, and
step 7 now checks the declared set explicitly so that an excluded candidate
reaches no decision rather than the unapproved deny. Affects task0001; the
protocol's decision table (task0002) needs no row change because its
cd prefix row says "meeting the conditions above".

### D4: Backslash escapes count as quoting for every unquoted-state rule

FR2 does not count escaped characters; C1 applies the same to E9 (an escaped
parenthesis or brace is a literal character in Bash). Affects task0001 and
task0002.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| The scan follows quoting differently from Bash and lets a string with a real top-level operator through | Low | High | C1 scan model; quote-edge cases in task0001's Acceptance Criteria; THREAT-MODEL.md TM-1, TM-2 |
| The scan counts the `&` of a redirection or a quoted `;`, so common approved strings lose the allow | Medium | Medium | Token recognition in C1; the allow list in task0001 AC-2; THREAT-MODEL.md TM-5 |
| Edited documents break pinned sentences in existing doc tests | Medium | Low | C3 anchors; the per-task constraint lists; the full suite in every task's Acceptance Criteria |
| Hook, docstring and protocol drift apart | Low | Medium | C1 is the one statement; the docstring test (task0001) and the protocol test (task0002) check the same C1 conditions |
| A `status` substring enters the hook's executable text | Low | Medium | task0001 AC-7 runs the existing classification pin |

## Open Questions

- [x] The value of the implementer's `tests` field when the approved test
      command is excluded from the cd prefix form: `"fail"`, with `notes`
      stating that the test command was not run because the cd prefix form
      does not cover it (answer to
      `create-plan.fr7-excluded-test-command-tests-value`). Carried by C4 and
      task0003.
