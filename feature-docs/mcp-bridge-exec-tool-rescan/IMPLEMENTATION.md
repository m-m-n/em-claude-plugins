# Implementation Plan: mcp-bridge-exec-tool-rescan

## Overview
Narrow condition S1 of destructive-guard's single-quote skip so that the
`--args-json` data word of a static `mcp-bridge run` command is skipped only
for the `--mcp notion` / `--tool notion-create-comment` pair, and pin the
behaviour with new cases. One task, task0001, carries the whole change.

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
  having no pair. The change never turns an existing deny or ask into allow.
- **Case format**: `.claude/rules/hook-tests.md`. New cases are three-element
  cases with no fourth element (A4).
- **Existing cases**: none is removed or edited (FR4).
- **Change set**: limited to the two files of task0001; no plugin manifest is
  part of it (NFR4).

## Cross-task Design Decisions
None (single task). The pair-recognition rule is specified in
`tasks/task0001.md`.

## Risk Assessment
| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|------------|
| An existing allow case of the notion progress-comment form becomes deny under the stricter pair rule | Low | Medium (a false deny stops an unattended run) | TS-10 and the full case suite run in task0001 and in verify |
| Assumption A1 (`notion-create-comment` does not run its arguments) stops holding | Low | High | Recorded in THREAT-MODEL.md as the dependency of the one allowed pair (FR6) |

## Open Questions
- [ ] Whether mcp-bridge accepts abbreviated option names (a shorter prefix of
  `--mcp` or `--tool`). The inputs do not say. The pair rule in task0001 does
  not count such a word as a flag occurrence.
