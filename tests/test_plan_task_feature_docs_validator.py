"""Unit tests for the `plan-task-feature-docs` check of
em-workflow/scripts/validate-worker-output.py
(plan-feature-docs-route, task0004; FR2, NFR2, NFR3).

Rule pinned here (its prose is owned by skills/plan-writing/SKILL.md,
`## Feature-docs Files`; this module asserts only the validator's rendering
of it):

- In the replace_all mode (the mode bound to `replace_planning`), every
  element of a `tasks_patch.entries` item's `files` that is a string whose
  first normalized path segment (`path_segments`: `\\` read as `/`, empty
  and `.` segments dropped) is exactly `feature-docs` is reported with code
  `plan-task-feature-docs`: one error per offending path, the message
  holding the task id and the path as given.
- The append mode keeps its own code `rework-task-feature-docs` and message;
  an append entry never gets the new code.
- Carried tasks (`carried_task_ids`) never pass through entry validation, so
  their feature-docs paths are not checked, with and without
  `--dry-run-apply`.
- A malformed `files` value (not a list, a non-string element) is left to
  the existing structural codes; the new check skips it and never raises.

Acceptance criteria covered (feature-docs/plan-feature-docs-route/tasks/
task0004.md): AC-1 (TS-1), AC-2 (TS-2), AC-3 (TS-3), AC-4 (TS-4),
AC-6 (TS-9, part). AC-5 lives in
tests/test_rework_docs_only_validator_rules.py, AC-7 is the whole suite plus
the byte pin in tests/test_gate_option_vocabulary.py.

Convention: standard library `unittest` only; patches and workflows are built
in memory; the command-line cases write only into a temporary directory that
the test framework's cleanup removes.
"""

import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "em-workflow" / "scripts" / "validate-worker-output.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("validate_worker_output", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VWO = _load_module()

PLAN_CODE = "plan-task-feature-docs"
APPEND_CODE = "rework-task-feature-docs"

DIGEST = "sha256:" + "a" * 64
THREAT_MODEL_PATH = "feature-docs/call-end-history/THREAT-MODEL.md"


def run_cli(args):
    cmd = [sys.executable, str(SCRIPT_PATH)] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True)


def _codes(errors):
    return [e["code"] for e in errors]


def _only(errors, code):
    return [e for e in errors if e["code"] == code]


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------


def _entry(files, task_number="0007", **extra):
    entry = {
        "complexity": "medium",
        "domains": ["auth"],
        "files": files,
        "initial_status": "pending",
        "plan": f"tasks/task{task_number}.md",
        "requirements": ["FR1"],
        "skills": ["backend-impl"],
        "title": "Plan entry",
    }
    entry.update(extra)
    return entry


def _replace_planning_patch(entries, carried_task_ids=None, preserve=()):
    tasks_patch = {"entries": entries, "mode": "replace_all"}
    if carried_task_ids is not None:
        tasks_patch["carried_task_ids"] = carried_task_ids
    return {
        "base_input_digest": DIGEST,
        "base_workflow_blob": "8f17c04",
        "operation": "replace_planning",
        "patch_id": "plan-p0001",
        "preserve": list(preserve),
        "requirements_patch": None,
        "schema_version": 1,
        "step_patches": [],
        "tasks_patch": tasks_patch,
    }


def _append_patch(entries):
    return {
        "base_input_digest": DIGEST,
        "base_workflow_blob": "8f17c04",
        "operation": "append_rework",
        "patch_id": "rework-p0001",
        "preserve": ["workflow.implement.base_commit"],
        "requirements_patch": None,
        "schema_version": 1,
        "step_patches": [
            {
                "expected": {"status": "completed"},
                "set": {"status": "pending"},
                "step_id": "implement",
            }
        ],
        "tasks_patch": {
            "entries": entries,
            "expected_next_task_id": "task0007",
            "mode": "append",
        },
    }


def _append_entry(files):
    return _entry(
        files,
        provenance={"review_round": 2, "source": "review", "source_ids": ["abc123"]},
    )


def _append_message(path):
    # The pre-existing append message of task entry validation, pinned
    # verbatim so AC-3 notices any change to it.
    return (
        f"tasks_patch.entries[task0007].files entry {path!r} is a feature-docs "
        "planning document; a rework-synthesized task's files must not reach "
        "feature-docs/**"
    )


# ---------------------------------------------------------------------------
# AC-1 (TS-1): a replace_planning entry holding a feature-docs path
# ---------------------------------------------------------------------------


class TestReplacePlanningEntryFeatureDocsPath(unittest.TestCase):
    def _entry_errors(self, files, task_id="task0007"):
        return VWO.validate_task_entry(task_id, _entry(files), "replace_all", None, None)

    def test_ac1_one_error_with_the_new_code_naming_the_task_and_the_path(self):
        errors = self._entry_errors([THREAT_MODEL_PATH])
        self.assertEqual(_codes(errors), [PLAN_CODE])
        self.assertIn("task0007", errors[0]["message"])
        self.assertIn(THREAT_MODEL_PATH, errors[0]["message"])

    def test_ac1_the_message_states_the_rule_and_cites_its_owner(self):
        message = self._entry_errors([THREAT_MODEL_PATH])[0]["message"]
        self.assertIn("feature-docs/**", message)
        self.assertIn("skills/plan-writing/SKILL.md", message)
        self.assertIn("## Feature-docs Files", message)

    def test_ac1_the_message_holds_the_path_as_given(self):
        path = "feature-docs\\call-end-history\\THREAT-MODEL.md"
        errors = self._entry_errors([path])
        self.assertEqual(_codes(errors), [PLAN_CODE])
        self.assertIn(repr(path), errors[0]["message"])

    def test_ac1_the_error_is_reported_through_a_replace_planning_patch(self):
        patch = _replace_planning_patch({"task0007": _entry([THREAT_MODEL_PATH])})
        errors = VWO.validate_workflow_patch(patch)
        self.assertEqual(_codes(errors), [PLAN_CODE])
        self.assertIn("task0007", errors[0]["message"])
        self.assertIn(THREAT_MODEL_PATH, errors[0]["message"])

    def test_ac1_a_code_path_next_to_the_feature_docs_path_is_not_reported(self):
        errors = self._entry_errors(["src/auth.go", THREAT_MODEL_PATH, "tests/auth_test.go"])
        self.assertEqual(_codes(errors), [PLAN_CODE])
        self.assertNotIn("src/auth.go", errors[0]["message"])
        self.assertNotIn("tests/auth_test.go", errors[0]["message"])

    def test_ac1_an_entry_without_a_feature_docs_path_is_accepted(self):
        self.assertEqual(self._entry_errors(["src/auth.go", "tests/auth_test.go"]), [])
        patch = _replace_planning_patch({"task0007": _entry(["src/auth.go"])})
        self.assertEqual(VWO.validate_workflow_patch(patch), [])

    def test_ac1_each_entry_of_the_patch_is_checked_under_its_own_task_id(self):
        patch = _replace_planning_patch(
            {
                "task0007": _entry(["src/auth.go"], "0007"),
                "task0008": _entry([THREAT_MODEL_PATH], "0008"),
            }
        )
        errors = VWO.validate_workflow_patch(patch)
        self.assertEqual(_codes(errors), [PLAN_CODE])
        self.assertIn("task0008", errors[0]["message"])
        self.assertNotIn("task0007", errors[0]["message"])


# ---------------------------------------------------------------------------
# AC-2 (TS-2): path forms, look-alikes, several paths
# ---------------------------------------------------------------------------


class TestFeatureDocsPathForms(unittest.TestCase):
    def _entry_errors(self, files):
        return VWO.validate_task_entry("task0007", _entry(files), "replace_all", None, None)

    def test_ac2_each_spelling_of_a_feature_docs_path_yields_one_error(self):
        for path in (
            "./feature-docs/x",
            "feature-docs\\x\\y.md",
            "feature-docs//x",
            ".\\feature-docs\\example\\SPEC-notes.md",
            "feature-docs",
            "./feature-docs",
        ):
            with self.subTest(path=path):
                errors = self._entry_errors([path])
                self.assertEqual(_codes(errors), [PLAN_CODE])
                self.assertIn(repr(path), errors[0]["message"])

    def test_ac2_look_alike_paths_yield_no_error(self):
        for path in (
            "feature-docs-archive/x",
            "src/feature-docs/x",
            "feature-docs.md",
            "Feature-Docs/x",
            "docs/feature-docs",
        ):
            with self.subTest(path=path):
                self.assertEqual(self._entry_errors([path]), [])

    def test_ac2_two_feature_docs_paths_yield_two_errors_one_per_path(self):
        first = "feature-docs/alpha/LESSONS.md"
        second = "./feature-docs/beta/tasks/task0001.md"
        errors = self._entry_errors([first, "src/auth.go", second])
        self.assertEqual(_codes(errors), [PLAN_CODE, PLAN_CODE])
        self.assertIn(repr(first), errors[0]["message"])
        self.assertNotIn(second, errors[0]["message"])
        self.assertIn(repr(second), errors[1]["message"])
        self.assertNotIn(first, errors[1]["message"])

    def test_ac2_the_same_path_listed_twice_is_reported_once_per_occurrence(self):
        errors = self._entry_errors([THREAT_MODEL_PATH, THREAT_MODEL_PATH])
        self.assertEqual(_codes(errors), [PLAN_CODE, PLAN_CODE])

    def test_ac2_forms_and_look_alikes_through_a_replace_planning_patch(self):
        patch = _replace_planning_patch(
            {
                "task0007": _entry(
                    ["./feature-docs/x", "feature-docs-archive/x", "src/feature-docs/x"]
                )
            }
        )
        errors = VWO.validate_workflow_patch(patch)
        self.assertEqual(_codes(errors), [PLAN_CODE])
        self.assertIn("'./feature-docs/x'", errors[0]["message"])


# ---------------------------------------------------------------------------
# AC-3 (TS-3): the append rule is unchanged
# ---------------------------------------------------------------------------


class TestAppendRuleUnchanged(unittest.TestCase):
    def test_ac3_an_append_entry_gets_only_the_append_code_and_message(self):
        paths = [THREAT_MODEL_PATH, "./feature-docs/x", "feature-docs\\x\\y.md"]
        errors = VWO.validate_task_entry(
            "task0007", _append_entry(paths), "append", None, None
        )
        self.assertEqual(_codes(errors), [APPEND_CODE] * 3)
        for path, error in zip(paths, errors):
            self.assertEqual(error["message"], _append_message(path))
        self.assertNotIn(PLAN_CODE, _codes(errors))

    def test_ac3_an_append_rework_patch_gets_only_the_append_code(self):
        patch = _append_patch({"task0007": _append_entry([THREAT_MODEL_PATH])})
        errors = VWO.validate_workflow_patch(patch)
        self.assertEqual(_codes(errors), [APPEND_CODE])
        self.assertEqual(errors[0]["message"], _append_message(THREAT_MODEL_PATH))

    def test_ac3_look_alike_paths_stay_accepted_on_the_append_side(self):
        for path in ("feature-docs-archive/x", "src/feature-docs/x"):
            with self.subTest(path=path):
                patch = _append_patch({"task0007": _append_entry([path])})
                self.assertEqual(VWO.validate_workflow_patch(patch), [])

    def test_ac3_the_two_modes_use_different_codes_for_the_same_path(self):
        replace_errors = VWO.validate_task_entry(
            "task0007", _entry([THREAT_MODEL_PATH]), "replace_all", None, None
        )
        append_errors = VWO.validate_task_entry(
            "task0007", _append_entry([THREAT_MODEL_PATH]), "append", None, None
        )
        self.assertEqual(_codes(replace_errors), [PLAN_CODE])
        self.assertEqual(_codes(append_errors), [APPEND_CODE])


# ---------------------------------------------------------------------------
# AC-4 (TS-4): carried tasks are not checked
# ---------------------------------------------------------------------------


def _workflow_with_carried_task(carried_files):
    return {
        "feature": "example",
        "project": {"license": "MIT"},
        "requirements": {"FR1": {"status": "ok", "tasks": ["task0001"], "tests": [], "title": "x"}},
        "schema_version": 1,
        "tasks": {
            "task0001": {
                "branch": "em-workflow/example/task0001",
                "complexity": "low",
                "domains": [],
                "files": list(carried_files),
                "notes": None,
                "plan": "tasks/task0001.md",
                "requirements": ["FR1"],
                "skills": [],
                "status": "pending",
                "title": "carried",
            }
        },
        "workflow": [
            {"completed_at_commit": "aaa", "id": "create-spec", "status": "completed"},
            {"id": "design", "skipped_reason": "no UI", "status": "skipped"},
            {"id": "create-plan", "status": "needs_update"},
            {"base_commit": "deadbeef", "id": "implement", "status": "pending"},
            {"id": "review", "status": "pending"},
            {"id": "verify", "status": "pending"},
            {"id": "retrospect", "status": "pending"},
        ],
    }


def _digest_source():
    return {
        "answers_digest": "sha256:" + "2" * 64,
        "digest_inputs": {},
        "mode": "interactive",
        "value_inputs": {"task_description": None},
        "worker": "implementation-planner",
        "workflow_blob": "8f17c04",
        "write_policy_digest": "sha256:" + "3" * 64,
    }


def _replanning_patch(entries):
    patch = _replace_planning_patch(
        entries,
        carried_task_ids=["task0001"],
        preserve=["workflow.implement.base_commit"],
    )
    patch["base_input_digest"] = VWO.normalize_json_sha256(_digest_source())
    return patch


class TestCarriedTasksAreNotChecked(unittest.TestCase):
    CARRIED_FILES = ["feature-docs/example/NOTES.md", "src/carried.go"]

    def test_ac4_a_carried_id_without_a_dry_run_gets_no_new_error(self):
        patch = _replanning_patch({})
        self.assertEqual(VWO.validate_workflow_patch(patch), [])

    def test_ac4_a_carried_task_with_a_feature_docs_path_gets_no_new_error_in_process(self):
        workflow = _workflow_with_carried_task(self.CARRIED_FILES)
        for dry_run in (False, True):
            with self.subTest(dry_run=dry_run):
                errors = VWO.validate_workflow_patch(
                    _replanning_patch({}),
                    workflow=workflow,
                    digest_source=_digest_source(),
                    dry_run=dry_run,
                )
                self.assertNotIn(PLAN_CODE, _codes(errors))
                self.assertEqual(errors, [])

    def test_ac4_the_new_entry_next_to_a_carried_task_is_still_checked(self):
        workflow = _workflow_with_carried_task(self.CARRIED_FILES)
        patch = _replanning_patch({"task0002": _entry([THREAT_MODEL_PATH], "0002")})
        errors = VWO.validate_workflow_patch(
            patch, workflow=workflow, digest_source=_digest_source(), dry_run=True
        )
        found = _only(errors, PLAN_CODE)
        self.assertEqual(len(found), 1)
        self.assertIn("task0002", found[0]["message"])
        self.assertNotIn("task0001", found[0]["message"])

    def test_ac4_the_command_line_validator_with_and_without_dry_run_apply(self):
        workflow = _workflow_with_carried_task(self.CARRIED_FILES)
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            patch_path = tmp_path / "input.json"
            workflow_path = tmp_path / "workflow.json"
            digest_path = tmp_path / "digest-source.json"
            patch_path.write_text(json.dumps(_replanning_patch({})), encoding="utf-8")
            workflow_path.write_text(json.dumps(workflow), encoding="utf-8")
            digest_path.write_text(json.dumps(_digest_source()), encoding="utf-8")
            base = [
                "--kind", "workflow-patch",
                "--worker", "implementation-planner",
                "--input", str(patch_path),
            ]
            runs = {
                "plain": base,
                "dry-run-apply": base
                + [
                    "--dry-run-apply",
                    "--workflow", str(workflow_path),
                    "--digest-source", str(digest_path),
                ],
            }
            for label, args in runs.items():
                with self.subTest(run=label):
                    completed = run_cli(args)
                    self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
                    self.assertNotIn(PLAN_CODE, completed.stdout + completed.stderr)

    def test_ac4_the_command_line_validator_reports_the_new_code_for_an_entry(self):
        workflow = _workflow_with_carried_task(self.CARRIED_FILES)
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            patch_path = tmp_path / "input.json"
            workflow_path = tmp_path / "workflow.json"
            digest_path = tmp_path / "digest-source.json"
            patch = _replanning_patch({"task0002": _entry([THREAT_MODEL_PATH], "0002")})
            patch_path.write_text(json.dumps(patch), encoding="utf-8")
            workflow_path.write_text(json.dumps(workflow), encoding="utf-8")
            digest_path.write_text(json.dumps(_digest_source()), encoding="utf-8")
            completed = run_cli(
                [
                    "--kind", "workflow-patch",
                    "--worker", "implementation-planner",
                    "--input", str(patch_path),
                    "--dry-run-apply",
                    "--workflow", str(workflow_path),
                    "--digest-source", str(digest_path),
                ]
            )
            self.assertEqual(completed.returncode, 1, completed.stdout + completed.stderr)
            found = _only(json.loads(completed.stdout)["errors"], PLAN_CODE)
            self.assertEqual(len(found), 1, completed.stdout)
            self.assertIn("task0002", found[0]["message"])
            self.assertNotIn("task0001", found[0]["message"])


# ---------------------------------------------------------------------------
# AC-6 (TS-9, part): malformed values are errors, never exceptions
# ---------------------------------------------------------------------------


class TestMalformedFilesNeverRaise(unittest.TestCase):
    def _entry_errors(self, files):
        return VWO.validate_task_entry("task0007", _entry(files), "replace_all", None, None)

    def test_ac6_a_files_value_that_is_not_a_list_is_reported_not_raised(self):
        for value in ("feature-docs/x", {"feature-docs/x": 1}, 5, True):
            with self.subTest(value=value):
                errors = self._entry_errors(value)
                self.assertEqual(_codes(errors), ["files"])
                self.assertNotIn(PLAN_CODE, _codes(errors))

    def test_ac6_a_non_string_element_next_to_a_feature_docs_path(self):
        for bad in (5, None, 1.5, True, ["feature-docs/x"], {"path": "feature-docs/x"}):
            with self.subTest(element=bad):
                errors = self._entry_errors([bad, THREAT_MODEL_PATH])
                self.assertEqual(sorted(_codes(errors)), ["files", PLAN_CODE])
                plan_errors = _only(errors, PLAN_CODE)
                self.assertEqual(len(plan_errors), 1)
                self.assertIn(THREAT_MODEL_PATH, plan_errors[0]["message"])

    def test_ac6_a_non_string_element_alone_gets_only_the_structural_code(self):
        errors = self._entry_errors([5])
        self.assertEqual(_codes(errors), ["files"])

    def test_ac6_an_empty_string_element_is_not_a_feature_docs_path(self):
        errors = self._entry_errors([""])
        self.assertEqual(_codes(errors), ["files"])

    def test_ac6_malformed_files_through_a_replace_planning_patch(self):
        patch = _replace_planning_patch(
            {
                "task0007": _entry([None, 5, THREAT_MODEL_PATH]),
                "task0008": _entry("feature-docs/x", "0008"),
            }
        )
        errors = VWO.validate_workflow_patch(patch)
        self.assertEqual(len(_only(errors, PLAN_CODE)), 1)
        self.assertIn("task0007", _only(errors, PLAN_CODE)[0]["message"])
        self.assertEqual(len(_only(errors, "files")), 3)

    def test_ac6_malformed_files_through_the_command_line_exit_1_without_a_traceback(self):
        patch = _replace_planning_patch(
            {"task0007": _entry([{"a": 1}, THREAT_MODEL_PATH])}
        )
        with tempfile.TemporaryDirectory() as tmp:
            patch_path = Path(tmp) / "input.json"
            patch_path.write_text(json.dumps(patch), encoding="utf-8")
            completed = run_cli(
                [
                    "--kind", "workflow-patch",
                    "--worker", "implementation-planner",
                    "--input", str(patch_path),
                ]
            )
        self.assertEqual(completed.returncode, 1, completed.stdout + completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)
        self.assertIn(PLAN_CODE, completed.stdout)
        self.assertIn("files", completed.stdout)

    def test_ac6_validation_does_not_mutate_the_entry(self):
        entry = _entry([5, THREAT_MODEL_PATH])
        before = copy.deepcopy(entry)
        VWO.validate_task_entry("task0007", entry, "replace_all", None, None)
        self.assertEqual(entry, before)


# ---------------------------------------------------------------------------
# AC-7: the validator byte pin is refreshed in place with a comment naming
# this task
# ---------------------------------------------------------------------------


class TestValidatorBytePinRefreshComment(unittest.TestCase):
    PIN_MODULE_PATH = REPO_ROOT / "tests" / "test_gate_option_vocabulary.py"
    MARKER = "Refreshed again by plan-feature-docs-route/task0004"
    PIN_ASSIGNMENT = "VALIDATE_WORKER_OUTPUT_SHA256 = ("

    def test_ac7_the_pin_is_preceded_by_a_refresh_comment_naming_this_task(self):
        text = self.PIN_MODULE_PATH.read_text(encoding="utf-8")
        self.assertEqual(text.count(self.MARKER), 1)
        start = text.rfind("\n", 0, text.index(self.MARKER)) + 1
        pin = text.index(self.PIN_ASSIGNMENT, start)
        comment = text[start:pin]
        self.assertIn("plan-task-feature-docs", comment)
        self.assertTrue(
            all(line.lstrip().startswith("#") or not line.strip() for line in comment.splitlines()[:-1]),
            "the refresh comment must sit directly above the pin assignment",
        )

    def test_ac7_the_pin_assignment_still_exists(self):
        text = self.PIN_MODULE_PATH.read_text(encoding="utf-8")
        self.assertRegex(text, r"VALIDATE_WORKER_OUTPUT_SHA256 = \(\s*\"[0-9a-f]{64}\"\s*\)")


if __name__ == "__main__":
    unittest.main()
