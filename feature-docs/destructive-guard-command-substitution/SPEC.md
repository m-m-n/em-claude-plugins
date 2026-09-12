# Feature: destructive-guard-command-substitution

## Overview

`em-workflow/hooks/destructive-guard.py` currently returns `allow` for a
recursive delete whose target word consists entirely of a command
substitution (`$( )` or backtick form): the substitution is blanked to a
single space, the word disappears at lexing, and `check_rm()` returns early
with zero targets. This feature closes that path so such a target reaches
the decision, merges it into the existing `rm-unresolvable` (`ask`) branch,
and brings the `rm-unresolvable` reason text in line with what the hook
actually handles.

Requirements source: `feature-docs/destructive-guard-command-substitution/REQUIREMENTS.md`.

## Objectives

- Close the `allow` hole where a recursive delete's target is built solely
  from a command substitution (`$(...)` / backticks), so an unrecoverable
  delete does not slip through an unattended run.
- Align the `rm-unresolvable` reason text with the hook's actual processing
  range, so a human or agent reading the hook output does not draw false
  assurance from it.
- Make the fix while keeping both the existing `allow` cases (the
  false-positive side) and the existing `deny` / `ask` cases (the detection
  side).

## User Stories

### US1: A substitution-only delete target is judged, not waved through
As an em-workflow user whose Bash calls pass through this PreToolUse hook,
I want `rm -rf $(...)` to be judged rather than allowed outright, so that an
unattended run cannot execute an unrecoverable delete whose blast radius was
never resolved.

**Acceptance Criteria:**
- [ ] AC-1: `rm -rf $(printf /home/sakura/valuable)` is judged `ask` instead
      of `allow` (`deny` when `CLAUDE_BATCH` is set).
- [ ] AC-2: The same content written in backtick form gets the same verdict
      as AC-1.
- [ ] AC-3: `rm -rf $(mktemp -d)` and `rm -rf $(cat list)` are no longer
      `allow`.

### US2: The reason text names the offending target
As an agent running unattended, I want the hook's reason text to describe
what it actually handles and to name the offending delete target, so that I
can rewrite the command into a statically resolvable form and continue.

**Acceptance Criteria:**
- [ ] AC-4: `rm -rf "$(cat list)"` stays `deny` or `ask`, and the delete
      target shown in the reason text is not whitespace only.
- [ ] AC-6: The `rm-unresolvable` reason text matches the processing that
      actually handles command substitutions.

### US3: Detection strength and false-positive cost both hold
As the maintainer of this hook, I want the existing verdicts and the case
table to stay intact, so that neither the detection half nor the
false-positive half regresses.

**Acceptance Criteria:**
- [ ] AC-5: Existing `deny` / `ask` cases (including the forms listed under
      FR5) keep their verdicts.
- [ ] AC-7: `em-workflow/hooks/tests/destructive-guard-cases.json` contains
      new cases for both the `$( )` form and the backtick form.
- [ ] AC-8: `python3 em-workflow/hooks/tests/run-destructive-guard.py`
      passes in full, including the unattended-demotion case.
- [ ] AC-9: `python3 -m unittest discover -s tests` passes.
- [ ] AC-10: The `version` in `em-workflow/.claude-plugin/plugin.json` and
      in the em-workflow entry of `.claude-plugin/marketplace.json` are
      raised to the same value.

## Technical Requirements

### Functional Requirements

- **FR1 — Put a whole-word command-substitution delete target on the
  decision path:** For a delete carrying a recursive flag (`-r` / `-R` /
  `--recursive`) whose target word consists entirely of a command
  substitution (both the `$( )` form and the backtick form; observed
  examples: `rm -rf $(printf /home/sakura/valuable)` and the equivalent with
  that `printf` wrapped in backticks), close the current path where blanking
  the substitution makes the token vanish and `check_rm()` returns early
  with zero targets, so that the target reaches the decision. Treat both
  forms identically.
- **FR2 — Merge the verdict into the existing `rm-unresolvable` (`ask`):**
  Route FR1's targets into the `rm-unresolvable` branch where variable
  expansions already land, returning `ask` (demoted to `deny` under
  `CLAUDE_BATCH` by the existing demotion logic). `deny` would also satisfy
  the completion condition, but matching the treatment of variable
  expansion — the other "statically unresolvable delete target" — takes
  priority.
- **FR3 — The reason text matches the actual processing range:** The
  `rm-unresolvable` reason text (currently "再帰削除の対象 `{t}` が
  変数/コマンド置換で、影響範囲を静的に確定できない。") must be consistent
  with command substitutions actually being handled on that path. The target
  shown in the reason text must not be empty or whitespace only, and must be
  rendered so that the reader can tell which delete target is the problem.
- **FR4 — A quoted command substitution's reason target is not whitespace
  either:** A recursive delete whose only target is a double-quoted command
  substitution (`rm -rf "$(cat list)"`) is currently `deny` under
  `rm-recursive`, but the target in its reason text renders as a single
  space. After the FR1/FR3 change this form stays `deny` or `ask`, and its
  reason-text target rendering must not be whitespace only.
- **FR5 — Existing `deny` / `ask` verdicts are unchanged:** Preserve the
  `deny` for a substitution followed by real text in the same word
  (`rm -rf $(pwd)/build`, `rm -rf $(pwd)/../tmp/scratch`,
  `rm -rf tmp/scratch$(pwd)`, and the backtick equivalents); the `deny`
  reached by re-scanning the substitution body
  (`echo $(rm -rf /home/sakura/x)`); the `ask` for variable expansion
  (`X=$(mktemp -d); rm -rf $X`); and the `allow` from the safe-root
  exception (`rm -rf /tmp/x`, `rm -rf node_modules`, `rm -rf ./build`,
  `rm -rf dist/*`).
- **FR6 — No false positive on non-`rm` commands containing a
  substitution:** Because changes to `_mark_substitutions()` /
  `_strip_unresolved_marks()` affect the token stream of every command,
  harmless commands containing a substitution (build invocations, commit
  messages, `python3 -c`, here-doc bodies, redirect-only statements) must
  keep returning `allow`. The command word `head()` returns, the redirect
  classification in `split_redirects()`, and the destination extraction for
  `cp` / `ln` / `rsync` must not break under the changed handling of words
  containing a substitution.
- **FR7 — Case-table update:** Rewrite the two entries pinned to `allow` as
  known holes in `em-workflow/hooks/tests/destructive-guard-cases.json`
  (`rm -rf $(mktemp -d)` / `rm -rf $(cat list)`, currently lines 96 and 129)
  to the new verdicts, and drop the "既知の穴(未修正)" wording from their
  labels. Additionally add cases where the delete target is a substitution
  only, for both the `$( )` form and the backtick form. Do not delete any
  existing `deny` / `ask` case.
- **FR8 — Plugin version bumped in the same change:** Because files under
  `em-workflow/` change, raise the `version` in
  `em-workflow/.claude-plugin/plugin.json` and in the em-workflow entry of
  the repository-root `.claude-plugin/marketplace.json` to the same value
  within the same change (both are currently 0.1.74; a behaviour fix, so a
  patch step).

### Non-Functional Requirements

- **NFR1 - Determinism:** The verdict is deterministic — the same command
  string always yields the same verdict (the promise in
  destructive-guard.py's module docstring).
- **NFR2 - No filesystem access:** The decision never consults the
  filesystem. Do not newly introduce `os.path.realpath`, `stat`, or
  `subprocess` (preserving `normalize_candidate()`'s constraint).
- **NFR3 - Performance:** The hook runs synchronously on every PreToolUse
  call, so added processing stays within string scanning and introduces no
  loop that grows non-linearly with input length. Existing bounding
  mechanisms such as `MAX_SHELL_PAYLOAD_EXPANSIONS` are not broken.
- **NFR4 - Failure behaviour preserved:** The fail-open (`exit 0`) behaviour
  on a malformed payload, and the `ask` → `deny` demotion in an unattended
  run, are unchanged.
- **NFR5 - Reason-text usability:** The reason text keeps the existing
  Japanese style and contains a concrete instruction an agent can read and
  use to rewrite the command into a safe form.
- **NFR6 - Sentinel containment:** The internal sentinel
  (`UNRESOLVED_MARK` = NUL) never leaks into the reason text or anywhere in
  stdout.
- **NFR7 - False-positive cost parity:** One false positive costs the same
  order of magnitude as one miss (`.claude/rules/hook-tests.md`). Not a
  single `allow`-side case is dropped.

## Implementation Approach

### Architecture

**System Architecture:**
```
┌─────────────────────────────────────────────────┐
│ Claude Code — PreToolUse(Bash)                  │
│   stdin: {"tool_name","tool_input":{"command"}} │
├─────────────────────────────────────────────────┤
│ destructive-guard.py                            │
│   statements()                                  │
│     strip_heredocs()                            │
│     _mark_substitutions()   <- changed          │
│     lex_segments()                              │
│     _strip_unresolved_marks()  <- changed       │
├─────────────────────────────────────────────────┤
│   check_rm()                 <- reason text     │
│   strongest_rm_decision()                       │
├─────────────────────────────────────────────────┤
│   decide()  → stdout permission decision, exit 0│
└─────────────────────────────────────────────────┘
```

**Component Diagram:**
```
_mark_substitutions()   replaces each SUBSTITUTION match; the whole-word
                        case is the branch FR1 changes
_strip_unresolved_marks() turns marker residue into a token's `.unresolved`
                        flag; the whole-marker token is where the target is
                        currently dropped
check_rm()              per-target tiering; `rm-unresolvable` is the branch
                        FR2 merges into and FR3/FR4 rewrite the text of
strongest_rm_decision() picks the strongest tier across targets/segments
decide()                emits, applying the unattended ask→deny demotion
```

### Data Flow

```
command string → strip_heredocs → _mark_substitutions → lex_segments
               → _strip_unresolved_marks → check_rm (per target)
               → strongest_rm_decision → decide → stdout
```

### API Design

No network or HTTP API. The hook's only external interface is the Claude
Code PreToolUse contract, unchanged by this feature:

**Request (stdin):**
```json
{"tool_name": "Bash", "tool_input": {"command": "rm -rf $(cat list)"}}
```

**Response (stdout, exit 0):**
```json
{
  "hookSpecificOutput": {
    "hookEventName": "PreToolUse",
    "permissionDecision": "ask",
    "permissionDecisionReason": "[destructive-guard/rm-unresolvable] ..."
  }
}
```

**Malformed payload:** fail-open — no decision is emitted and the process
exits 0 (NFR4).

### Database Schema

Not applicable; the hook holds no persistent data.

### Dependencies

**Internal Dependencies:**
- `em-workflow/hooks/destructive-guard.py`: the decision logic being changed.
- `em-workflow/hooks/tests/destructive-guard-cases.json`: the case table
  updated by FR7.
- `em-workflow/hooks/tests/run-destructive-guard.py`: the runner that drives
  the case table.
- `em-workflow/.claude-plugin/plugin.json` and
  `.claude-plugin/marketplace.json`: the two version fields FR8 raises.

**External Dependencies:**
- Python standard library only (`json`, `os`, `re`, `shlex`, `shutil`,
  `sys`). No third-party package is added.

### File Structure

```
em-workflow/
├── .claude-plugin/
│   └── plugin.json                       # version (FR8)
└── hooks/
    ├── destructive-guard.py              # FR1-FR6
    └── tests/
        ├── destructive-guard-cases.json  # FR7
        └── run-destructive-guard.py      # runner (unchanged)
.claude-plugin/
└── marketplace.json                      # version (FR8)
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/destructive-guard-command-substitution/**`
- `test-docs/destructive-guard-command-substitution/**`

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
- [ ] **TS-2** (FR1, FR2, FR6): Repository-root unit tests —
      `python3 -m unittest discover -s tests` (per `test/README.md`; hooks
      are tested through the subprocess contract that passes JSON on stdin).

### Integration Tests
- [ ] **TS-1** (FR1, FR2, FR3, FR4, FR5, FR7): Case-table driven —
      `python3 em-workflow/hooks/tests/run-destructive-guard.py`, which runs
      the hook as a subprocess for each 3-element JSON entry (expected
      verdict, label, command) and compares the result.

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected
- [ ] Existing E2E tests pass without regression

### Edge Cases
- [ ] **TS-3** (FR1, FR5): A recursive delete targeting a nested
      substitution — the `SUBSTITUTION` regex matches only the innermost
      form, so the current verdict is `deny`; it must not regress to
      `allow`.
- [ ] **TS-4** (FR6): A substitution sitting somewhere other than a delete
      target (a redirect destination) is not counted as a delete target.
- [ ] **TS-5** (FR2, FR5): Multiple targets (a safe target mixed with a
      substitution target; an unmistakably dangerous path mixed with a
      substitution target) still select the strongest verdict correctly.
- [ ] **TS-6** (FR5, FR6): A delete without a recursive flag behaves exactly
      as before.
- [ ] **TS-7** (FR4, FR5): A substitution adjacent to real text inside
      double quotes keeps its existing `deny`.
- [ ] **TS-8** (FR1, FR6): A delete whose substitution sits inside a
      `bash -c` / `eval` / here-string payload reaches the same verdict
      through `statements()`'s re-scan path.
- [ ] **TS-9** (FR6): On the parse-failure fallback path (unbalanced
      quoting), a command containing a substitution raises no exception.
- [ ] **TS-10** (FR5, FR6): Regression — the `allow` half of the case table
      (a delete string inside quotes, a here-doc body, a commit message,
      `python3 -c`, a redirect to `/dev/null`, a delete under a safe root)
      stays `allow` in full.

### Performance Tests
Not applicable as a separate measurement; NFR3 is satisfied structurally by
keeping added work within string scanning and leaving
`MAX_SHELL_PAYLOAD_EXPANSIONS` intact, and is exercised by the
kilobyte-scale assignment case already in the case table (TS-1).

## Security Considerations

- **Authentication:** Not applicable — the hook is invoked locally by Claude
  Code and authenticates nothing.
- **Authorization:** The hook emits a PreToolUse permission decision; the
  `ask` → `deny` demotion under `CLAUDE_BATCH` is unchanged (NFR4).
- **Input Validation:** The command string is analysed statically; a
  malformed payload fails open with `exit 0` (NFR4). No filesystem access is
  introduced (NFR2).
- **Data Protection:** The internal sentinel (`UNRESOLVED_MARK` = NUL) must
  not leak into the reason text or stdout (NFR6).
- **XSS Prevention:** Not applicable — no UI surface.
- **SQL Injection Prevention:** Not applicable — no database.
- **CSRF Protection:** Not applicable — no HTTP surface.

## Error Handling

### Error Codes

The hook has no error-code table; it emits verdicts identified by a rule id
in the reason prefix.

| Rule id | Tier | Meaning |
|---------|------|---------|
| `rm-unresolvable` | `ask` | The recursive-delete target cannot be statically resolved; FR1's targets merge here per FR2 |
| `rm-recursive` | `deny` | The recursive-delete target lies outside every safe root |
| `rm-root` | `deny` | The target matches the root/home shape |

### Error Flow

```
Malformed payload → no decision emitted → exit 0 (fail open)
ask verdict + CLAUDE_BATCH set → demoted to deny with the demotion note
```

## Performance Optimization

### Performance Goals
- Added processing stays within string scanning, with no loop growing
  non-linearly in input length (NFR3).

### Optimization Strategies
- Preserve the existing `MAX_SHELL_PAYLOAD_EXPANSIONS` bound rather than
  adding a new one (NFR3).

### Caching Strategy
None. Verdicts are computed fresh and deterministically per call (NFR1).

## Success Criteria

- [ ] All functional requirements (FR1-FR8) are implemented and tested
- [ ] All test scenarios (TS-1 - TS-10) pass
- [ ] `python3 em-workflow/hooks/tests/run-destructive-guard.py` passes in
      full, including the unattended-demotion case (AC-8)
- [ ] `python3 -m unittest discover -s tests` passes (AC-9)
- [ ] Non-functional requirements (NFR1-NFR7) are satisfied
- [ ] Both version fields are raised to the same value (AC-10)
- [ ] Code review is completed

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

None. Every FR and NFR is resolved.

## Implementation Phases (if applicable)

Not split into phases; the change is a single behaviour fix to one hook plus
its case table and the plugin version fields.

## References

- Requirements document: `feature-docs/destructive-guard-command-substitution/REQUIREMENTS.md`
- Hook under change: `em-workflow/hooks/destructive-guard.py`
- Case table: `em-workflow/hooks/tests/destructive-guard-cases.json`
- Case-table runner: `em-workflow/hooks/tests/run-destructive-guard.py`
- Hook test rules: `.claude/rules/hook-tests.md`
- Plugin version-bump rule: `.claude/rules/core-plugin-version-bump.md`
- Unit test instructions: `test/README.md`
