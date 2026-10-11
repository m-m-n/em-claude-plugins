# Implementation Plan: codex-guard-anon-brace-forms

## Overview

Extend the command-string parser of `codex-hook-interactive-guard.py` (the
em-workflow and em-review copies) so that the bodies of the three zsh
anonymous-function forms are judged, the words after an anonymous body's
closing brace are read as its arguments, and a pipe connection on the
anonymous-function head reaches its body. The feature is one task
(task0001); this document holds only the rules that apply to the whole
change set.

## Technology Stack

- **Language**: Python 3, standard library only (NFR2)
- **Tests**: `unittest`; the existing contract test module runs each hook copy
  as a separate process and never imports it
- **New dependencies**: none. `project.license` is `none`, so no license
  constraint applies and no dependency license needs recording.

## Layer Structure

The hook has three layers. Dependencies point downward only.

1. **Reader / parser** - splits one command string into simple commands and
   groups in one forward pass, then settles each group's connection and
   function-body status in one post-pass. Raises the undecidable signal on
   input it cannot read.
2. **Scan / judge** - walks the simple commands, and the literal shell `-c`
   strings nested in them through an explicit work list, and judges each
   simple command against the interpreter families.
3. **Entry point / output** - reads the hook JSON from stdin and writes one
   deny object or nothing.

This feature changes layer 1 and the documentation that describes it. The
contract layer 1 hands to layer 2 (ordered simple commands, each with its
words, stdin flag, after-pipe flag and innermost group; each group with its
settled connection and function-body status) keeps its shape. Layers 2 and
3, the deny object shape and the deny reason text do not change.

## Shared Components

None across tasks: the feature is a single task, so no component is built by
one task and used by another.

## Conventions

- **Two byte-identical copies**: `em-workflow/scripts/codex-hook-interactive-guard.py`
  and `em-review/scripts/codex-hook-interactive-guard.py` receive the same
  change in the same commit and stay byte-identical (FR6). The existing copy
  identity test pins this.
- **Fail-open policy**: anything the parser cannot positively read stays
  silent (no output). A new reading never turns an unreadable string into a
  deny.
- **No recursion, one forward pass**: no function calls itself and no
  functions form a cycle; nesting stays on explicit stacks (NFR2). The
  existing no-recursion and static-constraint tests pin this.
- **Documentation language**: docstrings and code comments are English;
  cases-table labels are Japanese, following the existing table.
- **Cases table format**: `(expected verdict, label, command)` with the
  verdict `deny` or `silent`, per `.claude/rules/hook-tests.md`. Existing
  entries are never removed or changed (NFR1).
- **Plugin versions**: this repository raises plugin versions automatically
  on push to main. No task edits a `plugin.json` or the marketplace file
  (NFR5).

## Cross-task Design Decisions

### Single-task decomposition

**Decision**: One task owns the parser change in both copies, the
documentation, and the regression tests.

**Rationale**: Every requirement lands in the same few parser functions of
two copies that must stay byte-identical, and the cases table that verifies
them lives in one test module. Splitting would put parallel tasks on the same
functions with no ordering between them, and the documentation would describe
behavior another task builds.

**Affected tasks**: task0001.

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| The argument span after an anonymous body swallows a later command, hiding a launch | Medium | High (fail-open) | The span ends at the next separator or the close of an enclosing group; deny cases with a launch after `;` (THREAT-MODEL TM-2) |
| The pipe connection handed to the anonymous body leaks to later commands | Medium | High (fail-open) | The connection is set on the body group only; deny case with a program-less launch after the body (TM-2) |
| The parenless-form check re-reads the words at every `{` and turns quadratic | Medium | Medium (hook answers late) | Constant-time decision per `{`; adversarial linearity input in the existing timeout test (TM-3) |
| An existing reading changes (named definitions, quoted `function`, ordinary brace groups) | Low | High | Existing cases table kept intact plus the FR4 silent cases |
| The two copies drift apart | Low | Medium | Existing byte-identity test |

## Open Questions

- None.
