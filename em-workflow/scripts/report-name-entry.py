#!/usr/bin/env python3
"""report-name-entry.py -- the FR6 judgment of subagent-report-write-block,
as aligned with the validator by FR4 of final-path-correction-medium-fixes:
at the start of a develop re-run that names the feature, decide whether the
final-path correction procedure (references/workflow-patch.md,
"Final-path correction") is entered from `implement: failed`.

Usage:
  report-name-entry.py --workflow PATH --journal PATH --target-repo PATH \\
      --base-commit FULL_COMMIT_ID

Prints one JSON object on stdout:

  {"entry": "none" | "dispatch" | "blocked",
   "violations": [{"task_id": ..., "path": ..., "failed_journal_line": N | null}],
   "errors": [...]}

- `none`: `implement` is not failed, or no failed task's files hold a
  violation (a name matching the report artifact rule that is not a regular
  file at the base commit).
- `dispatch`: violations exist and FR5 conditions 1 to 3 hold for each of
  them.
- `blocked`: violations exist and one of conditions 1 to 3 fails; `errors`
  carries the validator's error for each failing condition.

The targets are decided in two steps (FR4):

1. The `none` decision looks at the violations of the failed tasks alone. No
   violation there is `none`, whatever the other tasks hold.
2. Otherwise `violations` is recomputed over every task whose status is not
   `merged`, in the order of the workflow's task mapping and then file order,
   and conditions 1 to 3 are judged on that whole list. A task that has not
   failed is listed with the failed ones.

Exit codes: 0 for all three outcomes, 2 for an execution error (a missing
argument, an unreadable workflow or journal, a base commit that does not
resolve when a matching name makes the base necessary). The messages of an
execution error go to stderr.

The matching rule (FR2), the violation judgment (FR3), the journal replay
and conditions 1 to 3 (FR5) are the ones of `validate-worker-output.py`,
loaded here as this file's sibling, so each has one implementation.
`failed_journal_line` is the 1-based physical line of the task's last
`failed` journal event (the value `routeback_failed_journal_line` records),
or null when the task has none; an element for a task with no failed journal
event (an unstarted task, for one) carries null.
"""

import argparse
import importlib.util
import json
import sys
from pathlib import Path

VALIDATOR_FILE_NAME = "validate-worker-output.py"


def load_validator():
    path = Path(__file__).resolve().with_name(VALIDATOR_FILE_NAME)
    spec = importlib.util.spec_from_file_location("validate_worker_output", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {VALIDATOR_FILE_NAME} next to this script")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def build_arg_parser():
    parser = argparse.ArgumentParser(
        prog="report-name-entry.py",
        description="Judge whether the final-path correction is entered from a failed implement.",
    )
    parser.add_argument("--workflow", required=True, type=Path)
    parser.add_argument("--journal", required=True, type=Path)
    parser.add_argument("--target-repo", required=True, type=Path, dest="target_repo")
    parser.add_argument("--base-commit", required=True, dest="base_commit")
    return parser


def load_workflow(vwo, path):
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise vwo.ExecutionError(f"cannot read --workflow file: {exc.__class__.__name__}")
    workflow, parse_error = vwo.parse_yaml_text(text)
    if parse_error:
        raise vwo.ExecutionError("--workflow file is not valid YAML")
    if not isinstance(workflow, dict):
        raise vwo.ExecutionError("--workflow file must hold a mapping")
    return workflow


def failed_tasks(workflow, last_events):
    """Task ids a failed implement leaves behind: status `failed`, or a last
    journal event `failed` on a task whose status is not `merged`."""
    tasks = workflow.get("tasks")
    if not isinstance(tasks, dict):
        return {}
    found = {}
    for task_id, record in tasks.items():
        if not isinstance(task_id, str) or not isinstance(record, dict):
            continue
        status = record.get("status")
        last_event = last_events.get(task_id, (None, None))[0]
        if status == "failed" or (last_event == "failed" and status != "merged"):
            found[task_id] = record
    return found


def unmerged_files_by_task(workflow):
    """{task_id: files} for every task whose status is not `merged`, in the
    order of the workflow's task mapping. A `files` value that is not a list
    reads as no files."""
    tasks = workflow.get("tasks")
    if not isinstance(tasks, dict):
        return {}
    files_by_task = {}
    for task_id, record in tasks.items():
        if not isinstance(task_id, str) or not isinstance(record, dict):
            continue
        if record.get("status") == "merged":
            continue
        files = record.get("files")
        files_by_task[task_id] = files if isinstance(files, list) else []
    return files_by_task


def judge(vwo, workflow, journal, target_repo, base_commit):
    result = {"entry": "none", "violations": [], "errors": []}
    implement = vwo.workflow_find_step(workflow, "implement")
    if not isinstance(implement, dict) or implement.get("status") != "failed":
        return result

    last_events, last_failed_lines = vwo.read_journal_events(journal)
    failed_files_by_task = {}
    for task_id, record in failed_tasks(workflow, last_events).items():
        files = record.get("files")
        failed_files_by_task[task_id] = files if isinstance(files, list) else []

    # Step 1 (FR4): the `none` decision is the failed tasks' violations alone.
    if not vwo.find_report_name_violations(failed_files_by_task, target_repo, base_commit):
        return result

    # Step 2 (FR4): the targets are the violations of every task that is not
    # merged, the failed ones included, so a patch that corrects them all
    # leaves no carried task with a violation.
    violations = vwo.find_report_name_violations(
        unmerged_files_by_task(workflow), target_repo, base_commit
    )
    result["violations"] = [
        {
            "task_id": task_id,
            "path": path,
            "failed_journal_line": last_failed_lines.get(task_id),
        }
        for task_id, path in violations
    ]
    corrections = [{"task_id": task_id, "old_path": path} for task_id, path in violations]
    errors = vwo.path_correction_precondition_errors(
        workflow, corrections, last_events, target_repo, base_commit
    )
    if errors:
        result["entry"] = "blocked"
        result["errors"] = errors
    else:
        result["entry"] = "dispatch"
    return result


def main(argv=None):
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        vwo = load_validator()
        if vwo.yaml is None:
            raise vwo.ExecutionError("PyYAML is required (import yaml failed)")
        workflow = load_workflow(vwo, args.workflow)
        result = judge(vwo, workflow, args.journal, args.target_repo, args.base_commit)
    except Exception as exc:  # noqa: BLE001 -- every failure here is an execution error (exit 2)
        print(f"execution error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
