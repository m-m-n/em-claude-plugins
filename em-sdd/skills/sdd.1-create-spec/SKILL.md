---
name: sdd.1-create-spec
description: Interactively creates requirements documents and SPEC.md for feature implementation or modification
disable-model-invocation: true
allowed-tools: Read, Write, Glob, Grep, Bash, AskUserQuestion
---

## SDD Workflow Guard

Before executing this skill:

1. Determine the feature directory:
   - If `$ARGUMENTS` contains a path pointing to an existing `doc/tasks/{feature}/` directory, use it
   - If this is a new feature (no existing directory), skip guard (sdd.yaml will be created by this step)
   - If `doc/tasks/*/sdd.yaml` exists and matches, read it

2. If sdd.yaml exists for this feature:
   - If YAML parse error: Report error, offer `git restore` or regeneration, and exit
   - Find `create-spec` in workflow array
   - If status is "completed": Ask "再実行する / スキップする"
   - If status is "needs_update": Ask "再実行する / スキップする"
   - If status is "in_progress": Ask "最初からやり直す / 続行する"
   - If status is "failed": Ask "再試行する / 最初からやり直す"
   - Set `create-spec` status to "in_progress" and write sdd.yaml

3. If sdd.yaml does not exist: This is normal for the first step. Continue.

## Main Execution

**Agent**: Read `${CLAUDE_PLUGIN_ROOT}/agents/requirements-spec-creator.md` and follow its instructions.

Interactively create requirements documents and technical specifications.

- Clarify requirements through user dialogue
- Generate requirements document and SPEC.md
- Place in doc/tasks/{feature-name}/
- Generate sdd.yaml with workflow template

## SDD Workflow Completion

After this skill completes successfully:

1. Read `doc/tasks/{feature}/sdd.yaml` (created during this step)
2. Set `create-spec` status to "completed"
3. Set `create-spec` completed_at_commit to current `git rev-parse HEAD`
4. Write updated sdd.yaml

$ARGUMENTS
