---
name: sdd.status
description: Shows SDD workflow progress for a feature
disable-model-invocation: true
allowed-tools: Read, Glob, Grep
---

# SDD Status Viewer

Displays the current progress of an SDD workflow by reading sdd.yaml and tasks.yaml.

## Step 1: Locate sdd.yaml

1. If a path is specified in `$ARGUMENTS`, look for `sdd.yaml` in that directory
2. Otherwise, search for `doc/tasks/*/sdd.yaml` with Glob
3. If multiple found, list them and ask: "複数の SDD ワークフローが見つかりました。どれを表示しますか？"
4. If none found:
   - Search for `doc/tasks/*/SPEC.md` to check for legacy projects
   - If legacy artifacts exist: "sdd.yaml が見つかりません。`/em-sdd:sdd.1-create-spec` で新規作成するか、既存の成果物から生成できます。"
   - If nothing exists: "SDD ワークフローが見つかりません。`/em-sdd:sdd.1-create-spec` で開始してください。"
   - Exit

## Step 2: Read sdd.yaml

Read and parse the sdd.yaml file. Extract:
- `feature`: Feature name
- `scale`: optional, legacy field (may be absent in new sdd.yaml)
- `workflow`: Array of step objects
- `requirements`: Requirements mapping (if present)

## Step 3: Read tasks.yaml (if exists)

Check if `tasks.yaml` exists in the same directory as sdd.yaml.
If it exists, read and parse it.

## Step 4: Display Progress

Output the progress report in the following format:

```
## SDD Progress: {feature}

Workflow ({N} steps):
```

For each step in `workflow`, display one line:
```
  {step.id:<15} {artifacts joined by ', ':<30} {status}
```

Status display mapping:
- `completed` → `completed`
- `in_progress` → `in_progress`
- `pending` → `pending`
- `failed` → `FAILED`
- `needs_update` → `needs_update`

If tasks.yaml exists and the `implement` step is `in_progress` or `completed`:

```
Tasks (implement):
```

For each element in `tasks`:
- If the element is a single-item array (serial task):
  ```
    {task.id:<45} {task.status}
  ```
- If the element is a multi-item array (parallel group):
  - First item uses `┣━` prefix
  - Last item uses `┗━` prefix
  - Middle items use `┃ ` prefix
  - Append `parallel` label to the right

Example:
```
  setup-base-structure                         completed
  ┣━ implement-auth-api                        in_progress    ┃
  ┗━ implement-auth-frontend                   pending        ┃ parallel
  integration-tests                            pending
```

## Step 5: Suggest Next Action

Determine the next action based on workflow status:

1. Find the first step with status != `completed`:
   - If `pending`: suggest running the corresponding `/em-sdd:sdd.*` command
   - If `in_progress`: suggest continuing the step
   - If `failed`: suggest retrying
   - If `needs_update`: suggest re-running

2. If all steps are `completed`:
   ```
   SDD workflow complete
   ```

Step-to-command mapping:
| Step ID | Command |
|---------|---------|
| create-spec | /em-sdd:sdd.1-create-spec |
| create-plan | /em-sdd:sdd.2-create-plan |
| verify-plan | /em-sdd:sdd.3-verify-plan |
| implement | /em-sdd:sdd.4-implement |
| check | /em-sdd:sdd.5-check |
| verify | /em-sdd:sdd.6-verify |

## Step 6: Show Requirements Summary (if present)

If `requirements` section exists in sdd.yaml, show a brief summary:

```
Requirements:
  ok: {count}  tbd: {count}  assumed: {count}  excluded: {count}
```

If any `tbd` requirements exist:
```
  TBD items:
  - {FR_ID}: {title} ({tbd_reason})
```

$ARGUMENTS
