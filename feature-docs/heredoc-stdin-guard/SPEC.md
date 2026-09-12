# Feature: heredoc-stdin-guard

## Overview

A Bash tool call whose command contains a heredoc is not given `/dev/null` on
stdin, so a child process that reads stdin (`codex exec`) blocks forever on the
Unix socket to Claude Code. This feature adds a PreToolUse hook to the
em-workflow plugin that detects such commands and rewrites them through
`hookSpecificOutput.updatedInput`, prepending `exec < /dev/null` to the command.
The hook never denies a call: when it cannot decide, it emits nothing and exits
0.

Requirements source: `feature-docs/heredoc-stdin-guard/REQUIREMENTS.md`.

## Objectives

- Ensure that a single Bash call containing a heredoc does not leave the
  following commands' stdin attached to the Unix socket to Claude Code, closing
  the path by which a stdin-reading CLI (`codex exec` and the like) blocks
  forever waiting for EOF. (BO1)
- Keep `/em-workflow:develop --batch` unattended runs from hanging indefinitely
  through this path. (BO2)
- Keep the remedy inside the em-workflow plugin, with no dependency on the
  undocumented feature flag `CLAUDE_CODE_THRIFTY_SONIC`. (BO3)

## User Stories

### US1: Unattended batch runs do not hang on heredoc stdin
As an em-workflow user running `/em-workflow:develop --batch` unattended, I want
a Bash call that contains a heredoc followed by a stdin-reading CLI to complete,
so that the run does not stall with the child process at zero CPU time.

**Acceptance Criteria:**
- [ ] AC1: Running the reproduction procedure from the task description (create a
      prompt file under /tmp with a heredoc, then run
      `codex exec --sandbox read-only "$(cat ...)"` in the same Bash call) as a
      real Bash call with the existing hooks active, `codex exec` completes
      instead of waiting on stdin.
- [ ] AC2: In the AC1 run, the codex process does not stall with CPU time at
      `00:00:00` (`updatedInput` is observably applied in the real environment).
      If it is not applied, the hook's output shape (whether `permissionDecision`
      is emitted alongside) or its position in the matcher array is adjusted in
      the implementation phase.

### US2: The hook never blocks a tool call it cannot classify
As an em-workflow user, I want the hook to stay out of the way for commands it
does not target and for malformed payloads, so that it never stops a tool call.

**Acceptance Criteria:**
- [ ] AC5: A command without a heredoc, a command whose stdin is already
      redirected at the head, and a payload whose `tool_name` is not Bash each
      produce empty stdout and exit code 0.
- [ ] AC6: Malformed JSON, a missing `command` key, and an empty `command` on
      stdin each leave the hook exiting non-zero-free (exit 0) with nothing on
      stdout.

### US3: The rewrite is faithful and idempotent
As an em-workflow maintainer, I want the rewrite to preserve the rest of
`tool_input` and never double-apply, so that the hook's effect is limited to
closing stdin.

**Acceptance Criteria:**
- [ ] AC3: Given a command containing a heredoc and no stdin redirection, the
      hook writes JSON whose `hookSpecificOutput.updatedInput.command` starts
      with `exec < /dev/null` to stdout and exits 0.
- [ ] AC4: Executing the rewritten command in a real shell writes the heredoc
      body without losing a single byte (content, newlines and terminator
      intact).
- [ ] AC7: Every `tool_input` field other than `command` comes back in
      `updatedInput` with the same value as the input.

## Technical Requirements

### Functional Requirements

- **FR1 — heredoc-stdin-guard hook (new file):** Add
  `em-workflow/hooks/heredoc-stdin-guard.py`. It is a Python script operating
  under the same contract as the existing hooks: it reads the PreToolUse event
  JSON from stdin, writes its decision to stdout, and exits 0.
- **FR2 — Rewrite detection condition:** A payload is a rewrite target when
  `tool_name` is `Bash`, `tool_input.command` contains a heredoc operator
  (`<<` / `<<-`, excluding the here-string `<<<`), and stdin is not already
  redirected at the head of the command.
- **FR3 — stdin cut-off inserted at the head of the command via updatedInput:**
  For a rewrite target, return a command with `exec < /dev/null` inserted at the
  head via `hookSpecificOutput.updatedInput`. `permissionDecision: "deny"` is
  never returned.
- **FR4 — Idempotency:** When stdin is already redirected to `/dev/null` (or
  equivalent) at the head of the command — including the result of a previous
  rewrite — perform no rewrite and emit nothing. `exec < /dev/null` is never
  inserted twice into the same command.
- **FR5 — Preservation of the other tool_input fields:** When returning
  `updatedInput`, every `tool_input` field other than `command` (description,
  timeout, run_in_background, and so on) keeps its original value.
- **FR6 — Fail open:** Unparseable stdin JSON, a `tool_name` other than Bash, a
  `command` that is not a string or is empty, a command string that cannot be
  fully resolved by static analysis, and any other internal exception all lead to
  the same outcome: emit nothing, exit 0 (no decision). The hook never stops a
  tool call.
- **FR7 — Registration position in hooks.json:** Register
  `python3 "${CLAUDE_PLUGIN_ROOT}"/hooks/heredoc-stdin-guard.py` at the tail of
  the `hooks` array under PreToolUse / matcher `Bash` in
  `em-workflow/hooks/hooks.json` — after the existing six, as the seventh. The
  order and content of the existing six are not changed.
- **FR8 — Test placement and form:** Tests live at the repository root as
  `tests/test_heredoc_stdin_guard.py`, written with the Python standard library's
  `unittest`. They take the contract-test form: launch the hook as a subprocess,
  feed PreToolUse JSON on stdin, and assert on the `updatedInput` in stdout and
  on the exit code. Both the detection-condition tests and the execution test
  that the heredoc body survives the rewrite live in that same file. The
  case-table harness under `em-workflow/hooks/tests/` is not used.
- **FR9 — Plugin version bump:** Update the version in
  `em-workflow/.claude-plugin/plugin.json` and in the em-workflow entry of the
  repository-root `.claude-plugin/marketplace.json` to the same value, one patch
  step (0.1.72 → 0.1.73).

### Non-Functional Requirements

- **NFR1 - Dependencies:** No external dependencies. Only the Python 3 standard
  library is imported (beyond the `test/README.md` rule that tests import no
  third-party package, the hook itself needs no PyYAML or similar).
- **NFR2 - Security:** Decide by static analysis only. Start no external process,
  reach no network, write no file.
- **NFR3 - Performance:** The decision completes with ample margin against the
  timeout registered in hooks.json (10 seconds, matching the existing hooks).
- **NFR4 - Compatibility:** Do not change the verdicts of the existing six hooks.
  Placing this hook seventh (at the tail) means the other guards see the original,
  pre-rewrite command.
- **NFR5 - Availability:** A false positive never denies; it only adds a stdin
  cut-off at the head of the command (it does not stop an unattended batch run).
- **NFR6 - Scope containment:** The remedy stays inside the em-workflow plugin.
  The global hooks under `~/.claude/hooks/` are not changed. There is no
  dependency on the environment variable `CLAUDE_CODE_THRIFTY_SONIC`.

## Implementation Approach

### Architecture

**System Architecture:**

```
┌─────────────────────────────────────────────┐
│ Claude Code — Bash tool call                │
├─────────────────────────────────────────────┤
│ PreToolUse / matcher "Bash" (hooks.json)    │
│   1..6  existing guards  (see the original  │
│         command; verdicts unchanged, NFR4)  │
│   7     heredoc-stdin-guard.py  (FR7)       │
├─────────────────────────────────────────────┤
│ hookSpecificOutput.updatedInput  (FR3/FR5)  │
├─────────────────────────────────────────────┤
│ Shell executing the rewritten command       │
└─────────────────────────────────────────────┘
```

**Component Diagram:**

```
em-workflow/hooks/heredoc-stdin-guard.py
  - stdin  : PreToolUse event JSON
  - decide : tool_name == Bash?  (FR2/FR6)
             command is a non-empty string?  (FR2/FR6)
             heredoc operator present, here-string excluded?  (FR2)
             stdin already redirected at the head?  (FR2/FR4)
  - stdout : hookSpecificOutput.updatedInput, or nothing  (FR3/FR6)
  - exit   : always 0  (FR1/FR6)

em-workflow/hooks/hooks.json
  - PreToolUse / matcher "Bash" / hooks[7]  (FR7)

tests/test_heredoc_stdin_guard.py
  - subprocess-based contract tests  (FR8)
```

### Data Flow

```
Bash tool call
  → PreToolUse JSON on the hook's stdin
  → static analysis of tool_input.command      (NFR2)
  → rewrite target?  no  → nothing on stdout, exit 0      (FR4/FR6)
                     yes → updatedInput on stdout, exit 0 (FR3/FR5)
  → shell runs the command with stdin at /dev/null
```

### API Design

The hook's interface is the PreToolUse stdin/stdout contract, not an HTTP API.

**Input (stdin):**

```json
{
  "tool_name": "Bash",
  "tool_input": {
    "command": "cat > /tmp/f.txt <<'EOF'\n...\nEOF\n",
    "description": "...",
    "timeout": 120000
  }
}
```

**Output (stdout) when the command is a rewrite target (FR3, FR5):**

```json
{
  "hookSpecificOutput": {
    "updatedInput": {
      "command": "exec < /dev/null\ncat > /tmp/f.txt <<'EOF'\n...\nEOF\n",
      "description": "...",
      "timeout": 120000
    }
  }
}
```

**Output when not a target, or on any failure to decide (FR4, FR6):** empty
stdout, exit code 0. `permissionDecision: "deny"` is never emitted (FR3).

### Database Schema

Not applicable. The hook persists no data and writes no file (NFR2).

### Dependencies

**Internal Dependencies:**

- `em-workflow/hooks/hooks.json`: registers the hook as the seventh entry under
  PreToolUse / matcher `Bash`, after the existing six (FR7, NFR4).
- `em-workflow/.claude-plugin/plugin.json` and `.claude-plugin/marketplace.json`:
  carry the em-workflow version that must move together (FR9).

**External Dependencies:**

- Python 3 standard library only (NFR1).
- `codex` CLI: required only to run the real-environment check behind AC1 / AC2
  (assumption A7).

### File Structure

```
em-workflow/
├── hooks/
│   ├── hooks.json                       # PreToolUse / matcher "Bash": 7th entry (FR7)
│   └── heredoc-stdin-guard.py           # new hook (FR1)
├── .claude-plugin/
│   └── plugin.json                      # version 0.1.72 → 0.1.73 (FR9)
.claude-plugin/
└── marketplace.json                     # em-workflow version 0.1.72 → 0.1.73 (FR9)
tests/
└── test_heredoc_stdin_guard.py          # unittest contract tests (FR8)
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/heredoc-stdin-guard/**`
- `test-docs/heredoc-stdin-guard/**`

`feature-docs/{feature}/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/{feature}/**` covers `test-docs/{feature}/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/{feature}/` directory at all; the declared
`test-docs/{feature}/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests

- [ ] TS1 (FR2, FR3): Pass a command containing `cat > /tmp/f.txt <<'EOF'` … `EOF`
      as PreToolUse JSON and assert that `updatedInput.command` has
      `exec < /dev/null` inserted.
- [ ] TS2 (FR2, FR3): A command where a heredoc and a following stdin-reading
      command coexist (a `cat`-style placeholder standing in for `codex exec …`)
      is rewritten the same way.
- [ ] TS3 (FR2): A command with no heredoc (`ls -l`, `git status`) produces empty
      stdout.
- [ ] TS4 (FR2): A command containing only a here-string `<<<` is not mistaken for
      a heredoc.
- [ ] TS5 (FR4): A command already starting with `exec < /dev/null`, and a command
      of the form `cmd < /dev/null` whose stdin is closed from the head, both
      produce empty stdout (idempotency).
- [ ] TS6 (FR6): Malformed JSON, missing `command`, empty `command`, and a
      `tool_name` other than Bash — all four patterns exit 0 with empty stdout
      (fail open).

### Integration Tests

- [ ] TS7 (FR3): Actually run the rewritten command through `subprocess` and
      assert that the file written by the heredoc matches the original body
      exactly (using a temporary directory, never touching real project state).

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

- [ ] TS8 (FR1, FR2, FR3, FR7): With the existing hooks active in the real
      environment, run the reproduction procedure's Bash call once and confirm
      `codex exec` completes instead of waiting on stdin (AC1 / AC2).

### Edge Cases

- [ ] Here-string `<<<` only: not treated as a heredoc; no rewrite (TS4, FR2).
- [ ] Stdin already closed at the head of the command: no rewrite, no double
      insertion (TS5, FR4).
- [ ] Command string not fully resolvable by static analysis: emit nothing, exit 0
      (FR6).

### Regression Tests

- [ ] TS9 (FR7, FR8): `python3 -m unittest discover -s tests` in full, and
      `python3 em-workflow/hooks/tests/run-destructive-guard.py`, both still pass
      after the hooks.json change.

### Performance Tests

- [ ] The decision completes well within the 10-second hooks.json timeout (NFR3).

## Security Considerations

- **Authentication:** Not applicable — the hook is invoked locally by Claude Code
  over stdin/stdout.
- **Authorization:** Not applicable.
- **Input Validation:** The PreToolUse payload is validated defensively:
  `tool_name` must be `Bash` and `tool_input.command` must be a non-empty string;
  anything else, including unparseable JSON, results in no output and exit 0
  (FR2, FR6).
- **Data Protection:** The hook writes no file and persists nothing (NFR2).
- **Process and network isolation:** The decision is static analysis only — no
  external process is started and no network is reached (NFR2).
- **Blast radius of a false positive:** A misdetection never denies; it only adds
  a stdin cut-off at the head of the command (NFR5).

## Error Handling

### Error Cases

| Case | Condition | Handling |
|------|-----------|----------|
| Unparseable JSON | stdin is not valid JSON | No output, exit 0 (FR6) |
| Not a Bash call | `tool_name` is not `Bash` | No output, exit 0 (FR6) |
| Missing command | `tool_input.command` absent | No output, exit 0 (FR6) |
| Empty command | `tool_input.command` is `""` | No output, exit 0 (FR6) |
| Command not a string | type mismatch | No output, exit 0 (FR6) |
| Static analysis incomplete | the command string cannot be fully resolved | No output, exit 0 (FR6) |
| Any other internal exception | unexpected failure | No output, exit 0 (FR6) |

### Error Flow

```
Any failure to decide → emit nothing → exit 0 → the tool call proceeds unchanged
```

The hook has no error output path that stops a tool call: `permissionDecision:
"deny"` is never returned (FR3).

## Performance Optimization

### Performance Goals

- Decision time: well within the 10-second hooks.json timeout (NFR3).

### Optimization Strategies

- Static analysis of the command string only; no subprocess, no network, no file
  I/O (NFR2).

### Caching Strategy

None. The hook holds no state between invocations.

## Success Criteria

- [ ] All functional requirements (FR1–FR9) are implemented and tested
- [ ] All test scenarios (TS1–TS9) pass
- [ ] AC1 / AC2 confirm in the real environment that `updatedInput` is applied and
      `codex exec` completes
- [ ] AC9: the PreToolUse / matcher `Bash` hooks array has 7 elements, the 7th is
      heredoc-stdin-guard.py, and the first 6 match their pre-change content
- [ ] AC10: `em-workflow/.claude-plugin/plugin.json` and
      `.claude-plugin/marketplace.json` both carry em-workflow version 0.1.73
- [ ] AC8: `python3 -m unittest discover -s tests` passes in full and includes
      `tests/test_heredoc_stdin_guard.py`
- [ ] Non-functional requirements NFR1–NFR6 are satisfied
- [ ] Code review is completed

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

None. Every functional requirement (FR1–FR9) is `resolved`; no requirement
carries `status: tbd`.

The following assumptions are recorded as reversible and are re-checked during
implementation:

- A1: Claude Code 2.1.263's PreToolUse hook output schema has `updatedInput` and
  it can be returned inside `hookSpecificOutput`. Whether it is actually applied
  is secured by the AC1 / AC2 real-environment check.
- A2: A heredoc inside a string passed with `-c` is read from the script source,
  so prepending `exec < /dev/null` does not break the heredoc body. Re-confirmed
  by TS7 / AC4.
- A3: PreToolUse / matcher `Bash` in hooks.json currently holds six hooks (the
  task description's "five" does not match the actual content). The new one
  becomes the seventh.
- A4: Even when destructive-guard.py in the same matcher array returns `allow`
  for a non-destructive command, the `updatedInput` returned by the tail hook is
  applied — this premise has no precedent in the repository, so if AC2 is not
  met, the output shape or the position in the array is adjusted in the
  implementation phase.
- A5: The version is bumped one patch step as a behavioural fix (0.1.72 →
  0.1.73).
- A6: There is no LICENSE at the project root, so the SPDX identifier recorded in
  workflow.yaml stays undetected.
- A7: The AC1 / AC2 real-environment check runs in an environment where the codex
  CLI is available.

## Implementation Phases (if applicable)

### Phase 1: Hook and tests
**Goals:** Land the hook with its contract tests green.
**Deliverables:**
- `em-workflow/hooks/heredoc-stdin-guard.py` (FR1–FR6)
- `tests/test_heredoc_stdin_guard.py` (FR8; TS1–TS7)

### Phase 2: Registration, real-environment confirmation, version bump
**Goals:** Register the hook, confirm `updatedInput` takes effect, and bump the
plugin version.
**Deliverables:**
- `em-workflow/hooks/hooks.json` seventh entry (FR7, AC9)
- AC1 / AC2 real-environment confirmation (TS8); output shape or array position
  adjusted if not met (A4)
- Version 0.1.73 in both plugin.json and marketplace.json (FR9, AC10)
- TS9 regression run

## References

- Requirements document: `feature-docs/heredoc-stdin-guard/REQUIREMENTS.md`
- Hook registration: `em-workflow/hooks/hooks.json`
- Hook test conventions: `.claude/rules/hook-tests.md`
- Plugin version bump rule: `.claude/rules/core-plugin-version-bump.md`
- Plugin layout and structure: `.claude/rules/core-plugin-structure.md`
