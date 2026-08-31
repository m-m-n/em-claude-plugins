# Implementation Plan: destructive-guard-var-resolution

## Overview

The destructive-guard PreToolUse hook gains a static resolution stage that
turns plain literal `VAR=value` assignments found in the command string into
substituted target tokens, so a delete or write reached through such a
variable is judged exactly as the literal path would be. The work splits into
two tasks along file ownership: the hook and its expectation-case list
(task0001), and the two plugin version manifests (task0002).

## Technology Stack

- **Language**: Python 3, standard library only — the hook is one executable
  script and stays that way (NFR5).
- **Data files**: JSON — the expectation-case list read by the hook test
  runner, and the two plugin version manifests.
- **Key libraries**: none added. This feature introduces **0 new
  dependencies**, so no dependency license has to be recorded;
  `project.license` is `none`, so no license compatibility constraint applies
  to this feature at all.

## Layer Structure

The hook's judgment pipeline, stated as layers. Only layer 3 is new; every
other layer keeps its present responsibility (NFR6).

1. **Input decoding** — read the tool payload, extract the command string,
   decide whether this hook answers for the command at all.
2. **Lexing / statement enumeration** — split the command string into
   statements, honouring quoting, and re-queue the script-bearing payloads
   (shell `-c` payloads, command-substitution bodies, here-doc bodies aimed at
   a shell).
3. **Resolution (NEW)** — collect plain assignments from the statements layer 2
   produced, build the name-to-value map, and substitute mapped references into
   a target token before any target-path judgment reads that token.
4. **Target-path judgments** — the recursive-delete judgment (root/home test,
   scratch-area allowance, recursive-delete denial with a replacement-command
   suggestion) and the write-target judgment (Claude Code config test, session
   transcript test).
5. **Verdict emission** — one decision plus a Japanese reason string carrying
   the rule identifier.

Allowed dependency direction: layer 3 reads only layer 2's output and feeds
layer 4. Layer 4 never calls back into layer 3's collection logic, and layer 3
reaches neither the filesystem, a subprocess, nor a shell (NFR1).

## Shared Components

| Component | Responsibility | Contract (pre/postcondition) | Used by tasks |
|-----------|----------------|------------------------------|---------------|
| Hook source tree (`em-workflow/hooks/**`) | All resolution behaviour and every expectation case for it | Pre: exactly one task writes any file under this root. Post: the two hook-test commands exit 0 and no pre-existing expectation entry was deleted or altered | task0001 (sole writer); task0002 must not touch it |
| Plugin version value | Cache-freshness signal for the changed hook | Pre: both manifests read `0.1.56` at the base revision. Post: both read the identical string `0.1.57`; the marketplace entry is located by its plugin name, never by array position; no other plugin's version key is added or changed | task0002 (sole writer); task0001 must not touch either manifest |

These two rows are the whole cross-task surface. The tasks share no code and
no runtime contract — they share only the rule that neither writes into the
other's files, which is what keeps them mergeable in any order.

## Conventions

- **Rule identifiers**: no new rule identifier is introduced. The existing
  five (`rm-root`, `rm-recursive`, `rm-unresolvable`, `self-modification`,
  `transcript-write`) are reused unchanged, and the rule identifier remains
  observable in the emitted reason string.
- **Reason text**: Japanese, matching the surrounding reasons in tone and
  length; a reason states what was judged and what rewrite makes the command
  pass.
- **Error handling / fail-closed policy**: a situation the resolver cannot
  settle statically is an ordinary "not resolved" outcome, never an error and
  never a new exception path. Not-resolved means the pre-change judgment path
  runs on the original token text and produces the pre-change verdict (NFR2).
- **Static-only discipline**: no filesystem access, stat, path realization,
  subprocess or shell invocation is added anywhere on the resolution path
  (NFR1).
- **Expectation-case discipline**: additions only. Every pre-existing entry
  (58 at the base revision) stays present, unedited, with its recorded
  expectation (FR8, and the project's hook-test rule).
- **Verification commands** (from workflow.yaml `project.components`), both of
  which must exit 0 for either task:
  - hooks component: `python3 em-workflow/hooks/tests/run-destructive-guard.py`
  - main component: `python3 -m unittest discover -s tests`

## Cross-task Design Decisions

### D1: Two tasks, split strictly by file ownership

Everything FR1-FR8 asks for lives in one Python file plus its expectation-case
list, so a second task editing that file would buy no parallelism and would
guarantee a merge conflict. FR9 touches two JSON manifests the hook change
never opens. That boundary is the only split with zero file overlap, so it is
the split taken. Affected: task0001, task0002.

### D2: The version bump does not wait for the hook change

Tasks run fully in parallel with no ordering mechanism. The bump is correct
independently of whether the hook change has landed on the same integration
branch, because the version value is a cache-freshness signal rather than a
description of content. Neither task needs a placeholder for the other, and no
integration wiring is left unowned. Affected: task0002.

### D3: Rule identifier and reason content are verified outside the case list

The expectation-case format fixed by the project's hook-test rule carries only
the expected verdict, and the runner compares only that. Scenarios that assert
a rule identifier or a reason substring are therefore verified by invoking the
hook directly with a tool payload and reading the emitted reason (which begins
with the bracketed rule identifier). No new test module is added and the
runner is not modified — the same handling the previous change to this hook
used. Affected: task0001, and VERIFICATION.md's manual section.

### D4: Judgment parity is the definition of correctness

A resolved token is judged by the same path, on the same text, as the same
literal written directly in the command — no extra normalization, expansion or
lookup is introduced on the resolved path, and the replacement-command
suggestion in a denial reason is built from the resolved text. Parity is what
makes "resolution never weakens detection" checkable: for every scenario, the
expected verdict is whatever the literal spelling produces today. Affected:
task0001.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| A partially substituted token is treated as resolved, and its remaining dynamic part hides a wider blast radius | Low | High | Resolution is defined by the FINAL token text: any remaining glob metacharacter, command substitution or unmapped reference means not resolved, so the pre-change verdict stands |
| A command-prefix assignment is resolved, contradicting the shell's own word-expansion order | Medium | High | Excluded explicitly (FR5) and pinned by a scenario; the exclusion is stated as a property of the assignment's own statement shape, not of the variable name |
| Scope tracking misjudges a boundary and lets an assignment cross a nesting level | Medium | High | Any uncertainty resolves to "different scope", i.e. no resolution; two boundary shapes are pinned by scenarios and the remaining boundary kinds are enumerated in the task plan |
| Resolution surfaces targets the previous code never inspected, turning a former allow into a deny | Low | Medium | This is the intended direction — detection only grows; the retained case list proves no recorded verdict moved the other way |
| Parity inherits the existing prefix-only matching of the scratch-area allowance (a value starting inside a scratch root but climbing out with parent references) | Low | Medium | Parity with the literal spelling is the specified contract (FR2/FR4), and the allowance pattern is explicitly out of scope (NFR6); recorded as an open question rather than silently tightened |
| The two tasks land separately in a partial merge, leaving a changed hook at the old version | Low | Low | Both tasks merge before the verify phase, which reads both manifests and runs both suites |

## Open Questions

- [ ] The scratch-area allowance matches on prefix only. A resolved value that
      begins with a scratch root and then climbs out of it with parent
      references is allowed — exactly as the identical literal string is
      allowed today. This feature preserves that parity deliberately (NFR6);
      tightening the allowance would be a separate change with its own
      false-positive budget.
- [ ] NFR4 (bounded cost) has no automated scenario: SPEC.md states it is met
      structurally rather than measured. It is carried as a code-inspection
      item in VERIFICATION.md instead of a test.
