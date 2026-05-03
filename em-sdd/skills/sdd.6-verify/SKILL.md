---
name: sdd.6-verify
description: Comprehensive verification - file structure, SPEC compliance, E2E tests, security, performance
disable-model-invocation: true
allowed-tools: Read, Write, Glob, Grep, Bash, AskUserQuestion
---

## SDD Workflow Guard

Before executing this skill:

1. Determine the feature directory:
   - If `$ARGUMENTS` contains a path, use it
   - Otherwise, search `doc/tasks/*/sdd.yaml` with Glob
   - If multiple found, ask user to select
   - If none found, check for legacy artifacts and offer to generate sdd.yaml

2. Read `doc/tasks/{feature}/sdd.yaml`
   - If YAML parse error: Report error, offer `git restore` or regeneration, and exit

3. Find `verify` in workflow array

4. Status checks:
   - If status is "completed": Ask "再実行する / スキップする"
   - If status is "needs_update": Ask "再実行する / スキップする"
   - If status is "in_progress": Ask "最初からやり直す / 続行する"
   - If status is "failed": Ask "再試行する / 最初からやり直す"

5. Dependency check: Find the step immediately before `verify` in workflow
   - If `check` exists in workflow: Verify `check` status is "completed"
   - Otherwise: Verify `implement` status is "completed"
   - If not: Report "{previous_step} が未完了です" and exit

6. Staleness detection (if `check` exists in workflow):
   - Get `check` step's `completed_at_commit`
   - Compare with current `git rev-parse HEAD`
   - If different:
     - Report "sdd.5 完了後にコード変更が検出されました"
     - Run: build + test (lightweight re-verification using sdd.yaml project commands)
     - If failed: Report and exit (defer to sdd.5)
     - If passed: Continue

7. Set `verify` status to "in_progress" and write sdd.yaml

## Main Execution

**Agent**: Read `${CLAUDE_PLUGIN_ROOT}/agents/verification-executor.md` and follow its instructions.

Comprehensive verification based on VERIFICATION.md:

- File structure verification
- SPEC.md functional requirements compliance check
- E2E tests (Docker, if environment exists)
- Manual test item extraction
- Performance verification (if applicable)
- Security verification (if applicable)

Note: Build, test, format, and static analysis are NOT re-run (already verified by sdd.5-check) unless staleness was detected in the guard.

## SDD Workflow Completion

After this skill completes successfully:

1. Read `doc/tasks/{feature}/sdd.yaml`
2. Set `verify` status to "completed"
3. Set `verify` completed_at_commit to current `git rev-parse HEAD`
4. Write updated sdd.yaml

$ARGUMENTS
