#!/usr/bin/env python3
"""feature-docs-entry.py -- the Step A.6 judgment of the feature-docs
correction (plan-feature-docs-route, FR8 and FR9; IMPLEMENTATION.md D6): at
the start of a develop re-run, decide whether a failed implement is corrected
by removing feature-docs paths from the plan (references/workflow-patch.md,
"Feature-docs correction").

Usage:
  feature-docs-entry.py --workflow PATH --journal PATH --target-repo PATH \\
      --base-commit FULL_COMMIT_ID

The arguments are the four of `report-name-entry.py`. Prints one JSON object
on stdout with exactly these keys:

  {"entry": "none" | "dispatch" | "blocked",
   "targets": [{"task_id": ..., "path": ..., "failed_journal_line": N | null}],
   "errors": [...],
   "final_path_remaining": true | false}

- `none`: `implement` is not failed, or no failed task holds a feature-docs
  path in its `files`.
- `dispatch`: a failed task holds a feature-docs path and no blocking
  condition holds.
- `blocked`: a failed task holds a feature-docs path and a blocking condition
  holds; `errors` carries the validator's error for each failed condition
  (a task in flight, a target whose last journal event is `merged`, a target
  whose `files` would be empty once its feature-docs paths are removed).

`targets` is every distinct (task, path) pair over every task whose status is
not `merged`, in the order of the workflow's task mapping and then file order,
whose path is a feature-docs path (the first segment after `path_segments` is
exactly `feature-docs`). A task that has not failed is listed with the failed
ones, and no base-commit check applies to a target.

`final_path_remaining` is true only on `dispatch`, when some failed task, with
its feature-docs paths removed, still holds a report-name violation (the
validator's finder, which reads `--target-repo` and `--base-commit`); it is
false in every other case, so the base commit is needed only then.

Exit codes: 0 for all three outcomes, 2 for an execution error (a missing
argument, an unreadable or malformed workflow or journal, a base commit that
does not resolve when a report artifact name makes the base necessary). An
execution error prints one line on stderr and no traceback.

The failed-task and unmerged-task selection is `report-name-entry.py`'s, and
the journal replay, the blocking conditions
(`feature_docs_removal_precondition_errors`) and the report-name violation
finder are the ones of `validate-worker-output.py`; both are loaded here as
this file's siblings, so each has one implementation.
`failed_journal_line` is the 1-based physical line of the task's last `failed`
journal event (the value `routeback_failed_journal_line` records), or null
when the task has none. A `files` value that is not a list reads as no files,
and an element that is not a string is skipped.
"""

import argparse
import importlib.util
import json
import sys
from pathlib import Path

VALIDATOR_FILE_NAME = "validate-worker-output.py"
REPORT_NAME_ENTRY_FILE_NAME = "report-name-entry.py"


def _load_sibling(file_name, module_name):
    path = Path(__file__).resolve().with_name(file_name)
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {file_name} next to this script")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_validator():
    return _load_sibling(VALIDATOR_FILE_NAME, "validate_worker_output")


def load_report_name_entry():
    return _load_sibling(REPORT_NAME_ENTRY_FILE_NAME, "report_name_entry")


def build_arg_parser():
    parser = argparse.ArgumentParser(
        prog="feature-docs-entry.py",
        description="Judge whether the feature-docs correction is entered from a failed implement.",
    )
    parser.add_argument("--workflow", required=True, type=Path)
    parser.add_argument("--journal", required=True, type=Path)
    parser.add_argument("--target-repo", required=True, type=Path, dest="target_repo")
    parser.add_argument("--base-commit", required=True, dest="base_commit")
    return parser


def is_feature_docs_path(vwo, path):
    """True only for a string whose first segment, after the validator's
    `path_segments` normalization, is exactly `feature-docs`."""
    return isinstance(path, str) and vwo.path_segments(path)[:1] == ["feature-docs"]


def judge(vwo, rne, workflow, journal, target_repo, base_commit):
    result = {"entry": "none", "targets": [], "errors": [], "final_path_remaining": False}
    implement = vwo.workflow_find_step(workflow, "implement")
    if not isinstance(implement, dict) or implement.get("status") != "failed":
        return result

    last_events, last_failed_lines = vwo.read_journal_events(journal)
    failed = rne.failed_tasks(workflow, last_events)

    # The `none` decision looks at the failed tasks alone: whatever the other
    # tasks hold, no feature-docs path in a failed task is `none`.
    failed_files = {}
    for task_id, record in failed.items():
        files = record.get("files")
        failed_files[task_id] = files if isinstance(files, list) else []
    if not any(is_feature_docs_path(vwo, f) for files in failed_files.values() for f in files):
        return result

    # The targets are the feature-docs paths of every task that is not merged,
    # the failed ones included, so a patch that removes them all leaves no
    # carried task with a feature-docs path.
    removals = []
    seen = set()
    for task_id, files in rne.unmerged_files_by_task(workflow).items():
        for path in files:
            if is_feature_docs_path(vwo, path) and (task_id, path) not in seen:
                seen.add((task_id, path))
                removals.append({"task_id": task_id, "path": path})
    result["targets"] = [
        {
            "task_id": removal["task_id"],
            "path": removal["path"],
            "failed_journal_line": last_failed_lines.get(removal["task_id"]),
        }
        for removal in removals
    ]

    errors = vwo.feature_docs_removal_precondition_errors(workflow, removals, last_events)
    if errors:
        result["entry"] = "blocked"
        result["errors"] = errors
        return result

    result["entry"] = "dispatch"
    # A failed task that still holds a report-name violation once its
    # feature-docs paths are gone is corrected by the final-path judgment.
    remaining_files = {
        task_id: [f for f in files if not is_feature_docs_path(vwo, f)]
        for task_id, files in failed_files.items()
    }
    result["final_path_remaining"] = bool(
        vwo.find_report_name_violations(remaining_files, target_repo, base_commit)
    )
    return result


def main(argv=None):
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    try:
        vwo = load_validator()
        rne = load_report_name_entry()
        if vwo.yaml is None:
            raise vwo.ExecutionError("PyYAML is required (import yaml failed)")
        workflow = rne.load_workflow(vwo, args.workflow)
        result = judge(vwo, rne, workflow, args.journal, args.target_repo, args.base_commit)
    except Exception as exc:  # noqa: BLE001 -- every failure here is an execution error (exit 2)
        message = " ".join(str(exc).split()) or exc.__class__.__name__
        print(f"execution error: {message}", file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
