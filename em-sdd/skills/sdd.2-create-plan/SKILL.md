---
name: sdd.2-create-plan
description: Analyzes specifications and creates implementation plan with VERIFICATION.md
user-invocable: false
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

3. Find `create-plan` in workflow array

4. Status checks:
   - If status is "completed": Ask "再実行する / スキップする"
   - If status is "needs_update": Ask "再実行する / スキップする"
   - If status is "in_progress": Ask "最初からやり直す / 続行する"
   - If status is "failed": Ask "再試行する / 最初からやり直す"

5. Dependency check: Verify `create-spec` status is "completed"
   - If not: Report "create-spec が未完了です。先に /em-sdd:sdd.1-create-spec を実行してください。" and exit

6. Set `create-plan` status to "in_progress" and write sdd.yaml

## Main Execution

**Agent**: Read `${CLAUDE_PLUGIN_ROOT}/agents/implementation-planner.md` and follow its instructions.

Analyze the specification and create an implementation plan.

- Read and analyze SPEC.md
- Generate a plan including implementation order, file structure, and test strategy
- Output IMPLEMENTATION.md and VERIFICATION.md
- Generate tasks.yaml from IMPLEMENTATION.md phase analysis

## SDD Workflow Completion

After this skill completes successfully:

1. Read `doc/tasks/{feature}/sdd.yaml`
2. Set `create-plan` status to "completed"
3. Set `create-plan` completed_at_commit to current `git rev-parse HEAD`
4. Write updated sdd.yaml

$ARGUMENTS
