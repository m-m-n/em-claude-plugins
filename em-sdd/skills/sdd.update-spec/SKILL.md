---
name: sdd.update-spec
description: Updates SPEC.md and cascades changes to IMPLEMENTATION.md and VERIFICATION.md
disable-model-invocation: true
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, AskUserQuestion
---

## SDD Workflow Guard

Before executing this skill:

1. Determine the feature directory:
   - If `$ARGUMENTS` contains a path, use it
   - Otherwise, search `doc/tasks/*/sdd.yaml` with Glob
   - If multiple found, ask user to select
   - If none found: Report "SDD ワークフローが見つかりません。`/em-sdd:sdd.1-create-spec` で開始してください。" and exit

2. Read `doc/tasks/{feature}/sdd.yaml`
   - If YAML parse error: Report error, offer `git restore` or regeneration, and exit

3. Verify `create-spec` status is "completed"
   - If not: Report "仕様書がまだ作成されていません。先に `/em-sdd:sdd.1-create-spec` を実行してください。" and exit

## Main Execution

**Agent**: Read `${CLAUDE_PLUGIN_ROOT}/agents/spec-updater.md` and follow its instructions.

### Workflow

1. Receive change description from user
2. Read sdd.yaml
3. Read current SPEC.md
4. Git safety check:
   - Run: `git status` on SPEC.md
   - If uncommitted changes exist:
     Report "SPEC.md に未コミットの変更があります。先にコミットしてください。" and exit
5. Impact analysis (using sdd.yaml requirements):
   - Identify target FR/NFR IDs
   - List affected implementation tasks from `requirements.{ID}.tasks`
   - List affected tests from `requirements.{ID}.tests`
   - Warn if any completed tasks in tasks.yaml are affected
6. Present impact report to user
7. After user approval, update SPEC.md
8. Cascade updates to downstream artifacts (IMPLEMENTATION.md, VERIFICATION.md)
9. Update sdd.yaml + tasks.yaml:
   - sdd.yaml `requirements.{ID}`: Update title (if changed), tasks, tests
   - tasks.yaml: Set affected task statuses to "needs_update"
   - sdd.yaml workflow: Set affected downstream step statuses to "needs_update"
10. Consistency check:
    - Verify each task name in `requirements.{ID}.tasks` exists in tasks.yaml
    - Warn about orphaned task references, offer deletion or update
11. Output change summary

## SDD Workflow Completion

This skill does NOT advance workflow steps. Instead, it marks affected downstream steps as "needs_update" to trigger re-execution.

Display:
```
仕様変更を適用しました。

影響を受けたステップ:
  {step_id} <- needs_update (再実行が必要)
  ...

次のステップ: 影響を受けたステップを順番に再実行してください。
```

$ARGUMENTS
