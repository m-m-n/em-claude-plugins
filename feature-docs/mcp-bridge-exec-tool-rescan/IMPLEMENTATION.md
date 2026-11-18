# Implementation Plan: mcp-bridge-exec-tool-rescan

## Overview
Narrow condition S1 of destructive-guard's single-quote skip so that the
`--args-json` data word of a static `mcp-bridge run` command is skipped only
when the command's options determine the `--mcp notion` /
`--tool notion-create-comment` pair, and pin the behaviour with new cases.
One task, task0001, carries the whole change.

## Technology Stack
- **Language**: Python 3 (the existing hook script and its case runner).
- **Key libraries**: none added. No new dependency is introduced, so no
  dependency license is recorded (`project.license`: none).

## Layer Structure
- **Hook**: `em-workflow/hooks/destructive-guard.py` - PreToolUse static
  analysis. S1 belongs to the single-quote skip-span step, which decides
  which marked candidates are queued for re-scan.
- **Case suite**: `em-workflow/hooks/tests/destructive-guard-cases.json`, read
  by `em-workflow/hooks/tests/run-destructive-guard.py`.
- Dependency direction: case suite to hook only.

## Shared Components
None. The feature has a single task; no component is built by one task and
used by another.

## Conventions
- **Fail-closed (NFR2)**: a form whose pair cannot be determined is treated as
  having no pair. Decision D1 below fixes which forms count as determined.
  The change never turns an existing deny or ask into allow.
- **Case format**: `.claude/rules/hook-tests.md`. New cases are three-element
  cases with no fourth element (A4).
- **Existing cases**: none is removed or edited (FR4).
- **Change set**: limited to the two files of task0001; no plugin manifest is
  part of it (NFR4).

## Cross-task Design Decisions
No decision spans two tasks (single task). One feature-level decision is
recorded here because it reads FR1 and NFR2 more narrowly than the wording of
SPEC.md. The rule that implements it is specified in `tasks/task0001.md`.

### D1: A pair is determined only from a complete flag sequence in the canonical form
- **Decision**: the pair counts as determined only when the words after `run`
  read as a complete sequence of the known `run` flags: `--mcp`, `--tool`,
  `--args-json`, `--format` and `--session`, each followed by its value word,
  and `--dry-run` alone. Every flag name is written in the exact double-dash
  form as one unquoted word. `--mcp`, `--tool` and `--args-json` each appear
  exactly once. There is no `--`, no positional word, and no single-dash or
  `=` form of any flag. Every other form is undeterminable: S1 returns the
  empty set and every candidate is re-scanned. This is the plan's reading of
  FR1's undeterminable clause and of NFR2.
- **Basis**: mcp-bridge `run` parses its options with the Go standard
  library's flag parsing. It accepts each flag in single-dash and double-dash
  form, with the value as the next word or after `=`. A repeated flag takes
  the value of its last occurrence. Option parsing stops at `--` or at the
  first word that is not an option, and the later words are positional
  arguments. No abbreviated option name is accepted. Under FR1's wording
  alone, three forms let mcp-bridge receive another server or tool than the
  words `--mcp notion` / `--tool notion-create-comment` suggest:
  1. the notion pair followed by single-dash `-mcp` / `-tool` options that
     name another server and tool (the last occurrence wins);
  2. another server and tool given before `--`, with the notion pair after it;
  3. the same with a positional word in place of `--`.
- **Wider undeterminable set**: SPEC.md (assumption A2, Data Flow) lists a
  repeated `--mcp` / `--tool` word, a quoted value and the `--opt=value` form.
  D1 widens the set to every form outside the complete sequence: in addition,
  single-dash forms, quoted flag words, `--`, positional words, unknown or
  abbreviated option names, and a value-taking flag with no value word.
  SPEC.md is not rewritten in this run; this document and THREAT-MODEL.md
  (TM-2) record the wider set.
- **Accepted cost**: some forms whose effective pair is the notion pair are
  re-scanned, for example a trailing positional word or a single-dash
  `-mcp notion`. No existing allow case uses such a form; TS-2 and the TS-10
  regression set use the canonical form and stay allow.
- **Affected task**: task0001.

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| An existing allow case of the notion progress-comment form becomes deny under the stricter pair rule | Low | Medium (a false deny stops an unattended run) | TS-2, TS-10 and the full case suite run in task0001 and in verify |
| Assumption A1 (`notion-create-comment` does not run its arguments) stops holding | Low | High | Recorded in THREAT-MODEL.md as the dependency of the one allowed pair (FR6) |
| mcp-bridge's option parsing changes from the behaviour recorded in D1 | Low | High | D1 accepts only the canonical double-dash form with no terminator and no positional word; the dependency is recorded in THREAT-MODEL.md with TM-2 |

## Open Questions
None. The earlier question on abbreviated option names is resolved by D1:
mcp-bridge accepts no abbreviated name, and an abbreviated name is not a
known flag word, so a form that uses one is undeterminable.
