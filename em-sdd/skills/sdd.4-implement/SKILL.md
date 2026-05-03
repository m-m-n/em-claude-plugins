---
name: sdd.4-implement
description: Implements based on the implementation plan (TDD-compatible, Go/other languages)
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, Task, AskUserQuestion
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

3. Find `implement` in workflow array

4. Status checks:
   - If status is "completed": Ask "再実行する / スキップする"
   - If status is "needs_update": Ask "再実行する / スキップする"
   - If status is "in_progress": Ask "最初からやり直す / 続行する"
   - If status is "failed": Ask "再試行する / 最初からやり直す"

5. Dependency check: Find the step immediately before `implement` in workflow (could be `create-plan` or `verify-plan`)
   - Verify its status is "completed"
   - If not: Report "{previous_step} が未完了です" and exit

6. Set `implement` status to "in_progress" and write sdd.yaml

## Main Execution

**CRITICAL**: After the SDD Workflow Guard sets `implement` status to `in_progress`, you MUST proceed to execute the implementation in the same turn. Do NOT end the turn after writing the status — that leaves the workflow stuck. Always continue to invoke the implementation-executor below.

**Step 1**: Launch the implementation-executor agent via the Task tool.

```
Task(
  subagent_type: "implementation-executor",
  description: "Execute implementation per IMPLEMENTATION.md",
  prompt: "Feature directory: {feature_directory}\n\nRead doc/tasks/{feature}/IMPLEMENTATION.md and tasks.yaml, then execute TDD implementation. Update tasks.yaml as each task completes. Run formatter/linter at the end."
)
```

**Step 2**: Wait for the agent to complete, then proceed to "SDD Workflow Completion".

The implementation-executor agent will:
- Read and analyze the implementation plan
- Read tasks.yaml for task ordering and parallelization
- Execute each phase with TDD (test-first -> implementation)
- Run code quality checks (formatter/linter)
- Update tasks.yaml status as each task completes

## SDD Workflow Completion

After this skill completes successfully:

1. Read `doc/tasks/{feature}/sdd.yaml`
2. Set `implement` status to "completed"
3. Set `implement` completed_at_commit to current `git rev-parse HEAD`
4. Write updated sdd.yaml

$ARGUMENTS
