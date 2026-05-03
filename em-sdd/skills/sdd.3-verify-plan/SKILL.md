---
name: sdd.3-verify-plan
description: Performs consistency verification and design review of specifications and plans
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, AskUserQuestion
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

3. Find `verify-plan` in workflow array

4. Status checks:
   - If status is "completed": Ask "再実行する / スキップする"
   - If status is "needs_update": Ask "再実行する / スキップする"
   - If status is "in_progress": Ask "最初からやり直す / 続行する"
   - If status is "failed": Ask "再試行する / 最初からやり直す"

5. Dependency check: Verify `create-plan` status is "completed"
   - If not: Report "create-plan が未完了です。先に /em-sdd:sdd.2-create-plan を実行してください。" and exit

6. Set `verify-plan` status to "in_progress" and write sdd.yaml

## Main Execution

**Agent**: Read `${CLAUDE_PLUGIN_ROOT}/agents/plan-consistency-verifier.md` and follow its instructions.

Verify consistency between specifications and plans, and conduct a design review.

- Check consistency between SPEC.md and IMPLEMENTATION.md
- Detect gaps and contradictions, and apply fixes

## SDD Workflow Completion

After this skill completes successfully:

1. Read `doc/tasks/{feature}/sdd.yaml`
2. Set `verify-plan` status to "completed"
3. Set `verify-plan` completed_at_commit to current `git rev-parse HEAD`
4. Write updated sdd.yaml

$ARGUMENTS
