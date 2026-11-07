"""Tests for task0006 of plan-feature-docs-route: `feature-docs-entry.py`, the
Step A.6 judgment of the feature-docs correction (IMPLEMENTATION.md D6).

Acceptance Criteria covered (feature-docs/plan-feature-docs-route/tasks/
task0006.md):

- AC-1 (TS-6): `dispatch` with the targets of every unmerged task, in
  workflow order and then file order, a path at the base commit included.
- AC-2 (TS-7): the cases that never `dispatch`.
- AC-3: the output keys, the exit code and `final_path_remaining`.
- AC-4 (TS-9): exit 2 with a one-line message and no traceback for malformed
  input; a malformed `files` value reads as no files.

Every repository is built in a temporary directory with the identity set per
command, and a file with a report artifact name is only ever created at run
time. The tests use the standard library and unittest only (NFR3).
"""

import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "em-workflow" / "scripts"
ENTRY_PATH = SCRIPTS / "feature-docs-entry.py"
VALIDATOR_PATH = SCRIPTS / "validate-worker-output.py"

THREAT_MODEL = "feature-docs/call-end-history/THREAT-MODEL.md"
NOTES = "feature-docs/other/NOTES.md"
THIRD = "feature-docs/third/DESIGN.md"
MATCHING = "test-docs/demo/REPORT.md"

OUTPUT_KEYS = {"entry", "targets", "errors", "final_path_remaining"}
TARGET_KEYS = {"task_id", "path", "failed_journal_line"}


def _git_env():
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    return env


def git(repo, *args):
    cmd = [
        "git", "-C", str(repo),
        "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
        "-c", "commit.gpgsign=false",
        *args,
    ]
    return subprocess.run(cmd, check=True, capture_output=True, text=True, env=_git_env()).stdout.strip()


def make_workflow(*, implement="failed", tasks=None):
    tasks = tasks if tasks is not None else {
        "task0001": {"status": "failed", "files": [THREAT_MODEL, "src/a.py"]},
        "task0002": {"status": "pending", "files": [NOTES, "src/b.py"]},
        "task0003": {"status": "merged", "files": [THIRD, "src/c.py"]},
    }
    return {
        "schema_version": 1,
        "feature": "demo",
        "workflow": [
            {"id": "create-plan", "status": "completed"},
            {"id": "implement", "status": implement, "base_commit": "x"},
        ],
        "tasks": {
            task_id: {"title": task_id, "plan": f"tasks/{task_id}.md", "skills": [], "domains": [],
                      "complexity": "low", "requirements": ["FR1"], "notes": None,
                      "branch": f"em-workflow/demo/{task_id}", **record}
            for task_id, record in tasks.items()
        },
    }


class EntryCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.root = self.tmp / "repo"
        self.root.mkdir()
        git(self.root, "init", "-q")
        (self.root / "src").mkdir()
        (self.root / "src" / "a.py").write_text("a\n", encoding="utf-8")
        self.commit_files({})
        self.workflow_path = self.tmp / "workflow.yaml"
        self.journal_path = self.tmp / "journal.jsonl"

    def commit_files(self, files):
        for rel, content in files.items():
            target = self.root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "--allow-empty", "-m", "base")
        self.base = git(self.root, "rev-parse", "HEAD")

    def write_workflow(self, workflow):
        self.workflow_path.write_text(json.dumps(workflow), encoding="utf-8")

    def write_journal(self, lines):
        self.journal_path.write_text("".join(lines), encoding="utf-8")

    def event(self, task_id, event):
        return json.dumps({"task": task_id, "event": event}) + "\n"

    def arguments(self, **override):
        values = {
            "--workflow": str(self.workflow_path),
            "--journal": str(self.journal_path),
            "--target-repo": str(self.root),
            "--base-commit": self.base,
        }
        values.update(override)
        return values

    def run_entry(self, omit=None, **override):
        args = [sys.executable, str(ENTRY_PATH)]
        for flag, value in self.arguments(**override).items():
            if flag != omit:
                args += [flag, value]
        return subprocess.run(args, capture_output=True, text=True, env=_git_env())

    def judge(self, **override):
        result = self.run_entry(**override)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)

    def listed(self, result):
        return [(t["task_id"], t["path"], t["failed_journal_line"]) for t in result["targets"]]

    def assert_control_dispatches(self):
        """The script exists and judges a well-formed workflow. Without this
        control a missing script would also exit 2 and the checks of exit 2
        would pass for the wrong reason."""
        self.write_workflow(make_workflow())
        self.assertEqual(self.judge()["entry"], "dispatch")

    def assert_execution_error(self, result):
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertTrue(result.stderr.strip(), "a stderr message is required")
        self.assertNotIn("Traceback", result.stderr)
        self.assertNotIn("can't open file", result.stderr)


# ---------------------------------------------------------------------------
# AC-1 (TS-6)
# ---------------------------------------------------------------------------

class TestDispatchTargets(EntryCase):
    def standard_journal(self):
        self.write_journal([
            self.event("task0001", "launched"), self.event("task0001", "failed"),
            self.event("task0003", "launched"), self.event("task0003", "merged"),
        ])

    def test_ac1_targets_cover_every_unmerged_task_and_skip_the_merged_one(self):
        self.write_workflow(make_workflow())
        self.standard_journal()
        result = self.judge()
        self.assertEqual(result["entry"], "dispatch")
        self.assertEqual(result["errors"], [])
        self.assertEqual(self.listed(result), [("task0001", THREAT_MODEL, 2), ("task0002", NOTES, None)])
        self.assertNotIn(THIRD, [t["path"] for t in result["targets"]])

    def test_ac1_a_target_path_present_at_the_base_commit_is_still_listed(self):
        self.commit_files({THREAT_MODEL: "existing\n", NOTES: "existing\n"})
        self.write_workflow(make_workflow())
        self.standard_journal()
        result = self.judge()
        self.assertEqual(result["entry"], "dispatch")
        self.assertEqual(self.listed(result), [("task0001", THREAT_MODEL, 2), ("task0002", NOTES, None)])

    def test_ac1_the_order_is_the_task_mapping_then_the_file_order(self):
        self.write_workflow(make_workflow(tasks={
            "task0001": {"status": "pending", "files": ["feature-docs/b/B.md", "src/a.py", "feature-docs/a/A.md"]},
            "task0002": {"status": "failed", "files": ["src/b.py", THREAT_MODEL]},
            "task0003": {"status": "pending", "files": [NOTES, "src/c.py"]},
        }))
        self.write_journal([self.event("task0002", "failed")])
        result = self.judge()
        self.assertEqual(result["entry"], "dispatch")
        self.assertEqual(
            self.listed(result),
            [
                ("task0001", "feature-docs/b/B.md", None),
                ("task0001", "feature-docs/a/A.md", None),
                ("task0002", THREAT_MODEL, 1),
                ("task0003", NOTES, None),
            ],
        )

    def test_a_repeated_path_in_one_task_is_listed_once(self):
        self.write_workflow(make_workflow(tasks={
            "task0001": {"status": "failed", "files": [THREAT_MODEL, "src/a.py", THREAT_MODEL]},
        }))
        self.assertEqual(self.listed(self.judge()), [("task0001", THREAT_MODEL, None)])

    def test_the_same_path_in_two_tasks_is_one_target_per_task(self):
        self.write_workflow(make_workflow(tasks={
            "task0001": {"status": "failed", "files": [THREAT_MODEL, "src/a.py"]},
            "task0002": {"status": "pending", "files": [THREAT_MODEL, "src/b.py"]},
        }))
        self.assertEqual(
            [(t["task_id"], t["path"]) for t in self.judge()["targets"]],
            [("task0001", THREAT_MODEL), ("task0002", THREAT_MODEL)],
        )

    def test_the_journal_line_is_the_last_failed_event_with_every_line_counted(self):
        self.write_workflow(make_workflow())
        self.write_journal([
            "\n",
            self.event("task0001", "failed"),
            "not json\n",
            json.dumps({"task": "task0001", "event": "mystery"}) + "\n",
            self.event("task0001", "launched"),
            self.event("task0001", "failed"),
        ])
        self.assertEqual(self.judge()["targets"][0]["failed_journal_line"], 6)

    def test_the_journal_line_is_null_without_a_failed_event(self):
        self.write_workflow(make_workflow())
        self.assertFalse(self.journal_path.exists())
        self.assertIsNone(self.judge()["targets"][0]["failed_journal_line"])

    def test_a_task_failed_by_its_journal_alone_counts_as_failed(self):
        self.write_workflow(make_workflow(tasks={"task0001": {"status": "pending", "files": [THREAT_MODEL, "src/a.py"]}}))
        self.write_journal([self.event("task0001", "launched"), self.event("task0001", "failed")])
        result = self.judge()
        self.assertEqual(result["entry"], "dispatch")
        self.assertEqual(self.listed(result), [("task0001", THREAT_MODEL, 2)])

    def test_the_path_predicate_reads_the_first_normalized_segment(self):
        paths = [
            "./feature-docs/dot.md",
            "feature-docs//slash.md",
            "feature-docs\\backslash.md",
            "feature-docs/x/../up.md",
        ]
        self.write_workflow(make_workflow(tasks={"task0001": {"status": "failed", "files": paths + ["src/a.py"]}}))
        self.assertEqual([t["path"] for t in self.judge()["targets"]], paths)

    def test_a_path_that_is_not_under_feature_docs_is_not_a_target(self):
        others = [
            "feature-docs-archive/x.md",
            "src/feature-docs/x.md",
            "Feature-Docs/x.md",
            "feature-docsx/y.md",
            "docs/feature-docs.md",
        ]
        self.write_workflow(make_workflow(tasks={
            "task0001": {"status": "failed", "files": others + [THREAT_MODEL, "src/a.py"]},
        }))
        self.assertEqual([t["path"] for t in self.judge()["targets"]], [THREAT_MODEL])

    def test_only_a_failed_task_with_a_feature_docs_path_starts_the_correction(self):
        # The task that failed holds nothing under feature-docs; another
        # unmerged task does. The failed tasks alone decide `none`.
        self.write_workflow(make_workflow(tasks={
            "task0001": {"status": "failed", "files": ["src/a.py"]},
            "task0002": {"status": "pending", "files": [NOTES, "src/b.py"]},
        }))
        self.assertEqual(self.judge(), {"entry": "none", "targets": [], "errors": [], "final_path_remaining": False})


# ---------------------------------------------------------------------------
# AC-2 (TS-7)
# ---------------------------------------------------------------------------

class TestNeverDispatch(EntryCase):
    NONE = {"entry": "none", "targets": [], "errors": [], "final_path_remaining": False}

    def test_ac2_none_when_implement_is_not_failed(self):
        for status in ("pending", "in_progress", "completed"):
            with self.subTest(status):
                self.write_workflow(make_workflow(implement=status))
                self.write_journal([self.event("task0001", "failed")])
                self.assertEqual(self.judge(), self.NONE)

    def test_ac2_none_without_an_implement_step(self):
        workflow = make_workflow()
        workflow["workflow"] = [{"id": "create-plan", "status": "completed"}]
        self.write_workflow(workflow)
        self.assertEqual(self.judge(), self.NONE)

    def test_ac2_none_when_only_merged_tasks_hold_feature_docs_paths(self):
        self.write_workflow(make_workflow(tasks={
            "task0001": {"status": "failed", "files": ["src/a.py"]},
            "task0002": {"status": "merged", "files": [THIRD]},
        }))
        self.write_journal([self.event("task0001", "failed"), self.event("task0002", "merged")])
        self.assertEqual(self.judge(), self.NONE)

    def test_a_task_whose_last_journal_event_is_failed_but_is_merged_did_not_fail(self):
        self.write_workflow(make_workflow(tasks={"task0001": {"status": "merged", "files": [THIRD]}}))
        self.write_journal([self.event("task0001", "failed")])
        self.assertEqual(self.judge(), self.NONE)

    def assert_blocked(self, code, task_id=None):
        result = self.judge()
        self.assertEqual(result["entry"], "blocked", result)
        matching = [e for e in result["errors"] if e["code"] == code]
        self.assertTrue(matching, result["errors"])
        if task_id is not None:
            self.assertIn(task_id, [e.get("task_id") for e in matching])
            self.assertTrue(any(task_id in e["message"] for e in matching), matching)
        self.assertFalse(result["final_path_remaining"])
        return result

    def test_ac2_blocked_when_a_task_is_in_progress(self):
        self.write_workflow(make_workflow(tasks={
            "task0001": {"status": "failed", "files": [THREAT_MODEL, "src/a.py"]},
            "task0002": {"status": "in_progress", "files": ["src/b.py"]},
        }))
        self.write_journal([self.event("task0001", "failed")])
        result = self.assert_blocked("feature-docs-removal-in-flight", "task0002")
        self.assertEqual(self.listed(result), [("task0001", THREAT_MODEL, 1)])

    def test_ac2_blocked_when_a_last_journal_event_is_launched(self):
        self.write_workflow(make_workflow())
        self.write_journal([self.event("task0001", "failed"), self.event("task0002", "launched")])
        self.assert_blocked("feature-docs-removal-in-flight", "task0002")

    def test_ac2_blocked_naming_the_task_whose_files_would_become_empty(self):
        self.write_workflow(make_workflow(tasks={
            "task0001": {"status": "failed", "files": [THREAT_MODEL, "src/a.py"]},
            "task0002": {"status": "pending", "files": [NOTES, NOTES]},
        }))
        self.write_journal([self.event("task0001", "failed")])
        result = self.assert_blocked("feature-docs-removal-empty-files", "task0002")
        self.assertEqual([e["task_id"] for e in result["errors"] if e["code"] == "feature-docs-removal-empty-files"],
                         ["task0002"])

    def test_ac2_blocked_when_the_failed_task_itself_would_be_empty(self):
        self.write_workflow(make_workflow(tasks={"task0001": {"status": "failed", "files": [THREAT_MODEL]}}))
        self.assert_blocked("feature-docs-removal-empty-files", "task0001")

    def test_ac2_blocked_when_a_target_task_last_journal_event_is_merged(self):
        self.write_workflow(make_workflow())
        self.write_journal([
            self.event("task0001", "failed"),
            self.event("task0002", "launched"), self.event("task0002", "merged"),
        ])
        result = self.assert_blocked("feature-docs-removal-merged", "task0002")
        self.assertEqual(self.listed(result), [("task0001", THREAT_MODEL, 1), ("task0002", NOTES, None)])

    def test_ac2_blocked_when_a_failed_status_task_has_a_merged_last_event(self):
        self.write_workflow(make_workflow())
        self.write_journal([self.event("task0001", "failed"), self.event("task0001", "merged")])
        self.assert_blocked("feature-docs-removal-merged", "task0001")

    def test_every_failed_condition_is_listed(self):
        self.write_workflow(make_workflow(tasks={
            "task0001": {"status": "failed", "files": [THREAT_MODEL]},
            "task0002": {"status": "in_progress", "files": ["src/b.py"]},
        }))
        codes = {e["code"] for e in self.judge()["errors"]}
        self.assertEqual(codes, {"feature-docs-removal-in-flight", "feature-docs-removal-empty-files"})

    def test_blocked_is_exit_0_and_leaves_the_workflow_untouched(self):
        self.write_workflow(make_workflow(tasks={"task0001": {"status": "failed", "files": [THREAT_MODEL]}}))
        before = self.workflow_path.read_bytes()
        result = self.run_entry()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.workflow_path.read_bytes(), before)


# ---------------------------------------------------------------------------
# AC-3
# ---------------------------------------------------------------------------

class TestOutputContract(EntryCase):
    def test_ac3_the_keys_are_exactly_the_contracted_ones_for_every_outcome(self):
        cases = {
            "none": make_workflow(implement="pending"),
            "dispatch": make_workflow(),
            "blocked": make_workflow(tasks={"task0001": {"status": "failed", "files": [THREAT_MODEL]}}),
        }
        for outcome, workflow in cases.items():
            with self.subTest(outcome):
                self.write_workflow(workflow)
                result = self.run_entry()
                self.assertEqual(result.returncode, 0, result.stderr)
                payload = json.loads(result.stdout)
                self.assertEqual(payload["entry"], outcome)
                self.assertEqual(set(payload), OUTPUT_KEYS)
                self.assertIsInstance(payload["final_path_remaining"], bool)
                for target in payload["targets"]:
                    self.assertEqual(set(target), TARGET_KEYS)

    def test_ac3_a_failed_task_with_a_report_name_after_removal_sets_the_flag(self):
        self.write_workflow(make_workflow(tasks={
            "task0001": {"status": "failed", "files": [THREAT_MODEL, MATCHING, "src/a.py"]},
        }))
        result = self.judge()
        self.assertEqual(result["entry"], "dispatch")
        self.assertTrue(result["final_path_remaining"])

    def test_ac3_the_flag_is_false_without_a_report_name_in_a_failed_task(self):
        self.write_workflow(make_workflow())
        result = self.judge()
        self.assertEqual(result["entry"], "dispatch")
        self.assertIs(result["final_path_remaining"], False)

    def test_ac3_a_report_name_inside_feature_docs_is_removed_with_the_path(self):
        self.write_workflow(make_workflow(tasks={
            "task0001": {"status": "failed", "files": ["feature-docs/other/REPORT.md", "src/a.py"]},
        }))
        result = self.judge()
        self.assertEqual(result["entry"], "dispatch")
        self.assertIs(result["final_path_remaining"], False)

    def test_ac3_a_report_name_in_a_task_that_did_not_fail_does_not_set_the_flag(self):
        self.write_workflow(make_workflow(tasks={
            "task0001": {"status": "failed", "files": [THREAT_MODEL, "src/a.py"]},
            "task0002": {"status": "pending", "files": [MATCHING]},
        }))
        result = self.judge()
        self.assertEqual(result["entry"], "dispatch")
        self.assertIs(result["final_path_remaining"], False)

    def test_ac3_a_report_name_that_is_a_regular_file_at_the_base_is_an_update(self):
        self.commit_files({MATCHING: "existing\n"})
        self.write_workflow(make_workflow(tasks={
            "task0001": {"status": "failed", "files": [THREAT_MODEL, MATCHING]},
        }))
        self.assertIs(self.judge()["final_path_remaining"], False)

    def test_ac3_the_flag_is_false_on_blocked_and_on_none(self):
        self.write_workflow(make_workflow(tasks={
            "task0001": {"status": "failed", "files": [THREAT_MODEL, MATCHING]},
            "task0002": {"status": "in_progress", "files": ["src/b.py"]},
        }))
        blocked = self.judge()
        self.assertEqual(blocked["entry"], "blocked")
        self.assertIs(blocked["final_path_remaining"], False)
        self.write_workflow(make_workflow(implement="pending", tasks={
            "task0001": {"status": "failed", "files": [THREAT_MODEL, MATCHING]},
        }))
        none = self.judge()
        self.assertEqual(none["entry"], "none")
        self.assertIs(none["final_path_remaining"], False)

    def test_ac3_the_base_commit_is_needed_only_on_dispatch_with_a_report_name(self):
        unusable = {"--base-commit": "0" * 40}
        # none, blocked, and a dispatch with no report name never read the base.
        self.write_workflow(make_workflow(implement="pending"))
        self.assertEqual(self.judge(**unusable)["entry"], "none")
        self.write_workflow(make_workflow(tasks={
            "task0001": {"status": "failed", "files": [THREAT_MODEL, MATCHING]},
            "task0002": {"status": "in_progress", "files": ["src/b.py"]},
        }))
        self.assertEqual(self.judge(**unusable)["entry"], "blocked")
        self.write_workflow(make_workflow())
        self.assertEqual(self.judge(**unusable)["entry"], "dispatch")
        # A dispatch that has to look a report name up needs a usable base.
        self.write_workflow(make_workflow(tasks={
            "task0001": {"status": "failed", "files": [THREAT_MODEL, MATCHING]},
        }))
        self.assert_execution_error(self.run_entry(**unusable))

    def test_ac3_report_name_entry_is_not_changed_by_this_script(self):
        # The sibling keeps its own key set; this script only reuses it.
        self.write_workflow(make_workflow(tasks={"task0001": {"status": "failed", "files": [MATCHING]}}))
        result = subprocess.run(
            [sys.executable, str(SCRIPTS / "report-name-entry.py"),
             "--workflow", str(self.workflow_path), "--journal", str(self.journal_path),
             "--target-repo", str(self.root), "--base-commit", self.base],
            capture_output=True, text=True, env=_git_env(),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(set(json.loads(result.stdout)), {"entry", "violations", "errors"})


# ---------------------------------------------------------------------------
# AC-4 (TS-9)
# ---------------------------------------------------------------------------

class TestMalformedInput(EntryCase):
    def test_ac4_a_workflow_that_is_invalid_yaml_exits_2(self):
        self.assert_control_dispatches()
        for text in ("tasks: [unclosed\n", "key: : :\n  - [\n", "\t- a\n\tb: ]\n"):
            with self.subTest(text=text):
                self.workflow_path.write_text(text, encoding="utf-8")
                result = self.run_entry()
                self.assert_execution_error(result)
                self.assertEqual(len(result.stderr.strip().splitlines()), 1)

    def test_ac4_a_workflow_that_is_not_a_mapping_exits_2(self):
        self.assert_control_dispatches()
        for text in ("- a\n- b\n", "just a string\n", "42\n", "", "null\n"):
            with self.subTest(text=text):
                self.workflow_path.write_text(text, encoding="utf-8")
                result = self.run_entry()
                self.assert_execution_error(result)
                self.assertEqual(len(result.stderr.strip().splitlines()), 1)

    def test_ac4_a_missing_workflow_file_exits_2(self):
        self.assert_control_dispatches()
        result = self.run_entry(**{"--workflow": str(self.tmp / "absent.yaml")})
        self.assert_execution_error(result)
        self.assertEqual(len(result.stderr.strip().splitlines()), 1)

    def test_ac4_an_unreadable_journal_exits_2(self):
        # A directory in place of the journal cannot be read as a file.
        self.assert_control_dispatches()
        self.journal_path.mkdir()
        result = self.run_entry()
        self.assert_execution_error(result)
        self.assertEqual(len(result.stderr.strip().splitlines()), 1)

    def test_ac4_a_missing_argument_exits_2(self):
        self.assert_control_dispatches()
        for flag in self.arguments():
            with self.subTest(omit=flag):
                result = self.run_entry(omit=flag)
                self.assert_execution_error(result)
                self.assertIn(flag, result.stderr)

    def test_ac4_a_missing_journal_file_reads_as_no_events(self):
        self.write_workflow(make_workflow())
        self.assertFalse(self.journal_path.exists())
        self.assertEqual(self.judge()["entry"], "dispatch")

    def test_ac4_files_that_is_not_a_list_reads_as_no_files(self):
        for files in ("feature-docs/x.md", 5, None, {"a": THREAT_MODEL}, True):
            with self.subTest(files=files):
                self.write_workflow(make_workflow(tasks={
                    "task0001": {"status": "failed", "files": files},
                    "task0002": {"status": "pending", "files": [NOTES, "src/b.py"]},
                }))
                self.assertEqual(
                    self.judge(),
                    {"entry": "none", "targets": [], "errors": [], "final_path_remaining": False},
                )

    def test_ac4_a_task_without_files_does_not_stop_the_others(self):
        workflow = make_workflow(tasks={
            "task0001": {"status": "failed", "files": [THREAT_MODEL, "src/a.py"]},
            "task0002": {"status": "pending"},
        })
        self.write_workflow(workflow)
        result = self.judge()
        self.assertEqual(result["entry"], "dispatch")
        self.assertEqual(self.listed(result), [("task0001", THREAT_MODEL, None)])

    def test_ac4_non_string_elements_of_files_are_skipped(self):
        self.write_workflow(make_workflow(tasks={
            "task0001": {"status": "failed", "files": [5, None, ["feature-docs/x.md"], {"p": 1}, THREAT_MODEL, "src/a.py"]},
        }))
        result = self.judge()
        self.assertEqual(result["entry"], "dispatch")
        self.assertEqual(self.listed(result), [("task0001", THREAT_MODEL, None)])

    def test_ac4_a_malformed_tasks_value_is_no_task(self):
        for tasks in (["task0001"], "task0001", 3, None):
            with self.subTest(tasks=tasks):
                workflow = make_workflow()
                workflow["tasks"] = tasks
                self.write_workflow(workflow)
                self.assertEqual(self.judge()["entry"], "none")

    def test_ac4_a_task_record_that_is_not_a_mapping_is_skipped(self):
        workflow = make_workflow()
        workflow["tasks"]["task0009"] = "oops"
        workflow["tasks"]["task0010"] = ["feature-docs/x.md"]
        self.write_workflow(workflow)
        result = self.judge()
        self.assertEqual(result["entry"], "dispatch")
        self.assertEqual([t["task_id"] for t in result["targets"]], ["task0001", "task0002"])


# ---------------------------------------------------------------------------
# One implementation of the conditions (D6, D7)
# ---------------------------------------------------------------------------

def _load_entry_module():
    spec = importlib.util.spec_from_file_location("feature_docs_entry_under_test", ENTRY_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_validator():
    spec = importlib.util.spec_from_file_location("validate_worker_output_under_test", VALIDATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestSharedPrecondition(EntryCase):
    def test_the_blocking_conditions_come_from_the_validator_function(self):
        entry = _load_entry_module()
        vwo = _load_validator()
        seen = []

        def stub(workflow, removals, last_events):
            seen.append(([dict(r) for r in removals], dict(last_events)))
            return [{"code": "feature-docs-removal-in-flight", "message": "stub", "task_id": "task0001"}]

        vwo.feature_docs_removal_precondition_errors = stub
        entry.load_validator = lambda: vwo
        self.write_workflow(make_workflow())
        self.write_journal([self.event("task0001", "launched"), self.event("task0001", "failed")])
        out = io.StringIO()
        with redirect_stdout(out):
            code = entry.main([
                "--workflow", str(self.workflow_path), "--journal", str(self.journal_path),
                "--target-repo", str(self.root), "--base-commit", self.base,
            ])
        self.assertEqual(code, 0)
        result = json.loads(out.getvalue())
        self.assertEqual(result["entry"], "blocked")
        self.assertEqual([e["message"] for e in result["errors"]], ["stub"])
        self.assertEqual(
            seen[0][0],
            [{"task_id": "task0001", "path": THREAT_MODEL}, {"task_id": "task0002", "path": NOTES}],
        )
        self.assertEqual(seen[0][1]["task0001"][0], "failed")

    def test_the_failed_task_selection_is_the_one_of_report_name_entry(self):
        source = ENTRY_PATH.read_text(encoding="utf-8")
        self.assertIn("report-name-entry.py", source)
        self.assertNotIn("def failed_tasks", source)
        self.assertNotIn("def unmerged_files_by_task", source)


class TestEntryOutputPassesTheValidator(EntryCase):
    """The targets the script lists are exactly what a patch has to remove:
    fed through a patch that removes them all, the validator's dry run reports
    nothing, and a patch that leaves one out is `-incomplete`."""

    DIGEST_SOURCE = {
        "answers_digest": "sha256:" + "2" * 64,
        "digest_inputs": {"feature-docs/demo/SPEC.md": "sha256:" + "1" * 64},
        "mode": "interactive",
        "value_inputs": {"task_description": None},
        "worker": "implementation-planner",
        "workflow_blob": "8f17c04",
        "write_policy_digest": "sha256:" + "3" * 64,
    }

    def patch_of(self, removals):
        vwo = _load_validator()
        return vwo, {
            "schema_version": 1,
            "patch_id": "create-plan-p0001",
            "base_input_digest": vwo.normalize_json_sha256(self.DIGEST_SOURCE),
            "base_workflow_blob": self.DIGEST_SOURCE["workflow_blob"],
            "operation": "replace_planning",
            "tasks_patch": {
                "mode": "replace_all",
                "carried_task_ids": ["task0001", "task0002", "task0003"],
                "entries": {},
                "feature_docs_removals": removals,
            },
            "requirements_patch": None,
            "step_patches": [],
            "preserve": ["workflow.implement.base_commit"],
        }

    def dry_run(self, workflow, removals):
        vwo, patch = self.patch_of(removals)
        journal = self.journal_path
        return vwo.validate_workflow_patch(
            patch, workflow=workflow, digest_source=self.DIGEST_SOURCE, dry_run=True,
            feature_dir=self.tmp, journal=journal,
        )

    def test_the_listed_targets_are_a_complete_patch(self):
        workflow = make_workflow()
        self.write_workflow(workflow)
        self.write_journal([self.event("task0001", "failed"), self.event("task0003", "merged")])
        targets = self.judge()["targets"]
        removals = [{"task_id": t["task_id"], "path": t["path"]} for t in targets]
        self.assertEqual(self.dry_run(workflow, removals), [])

    def test_a_patch_that_leaves_a_target_out_is_incomplete(self):
        workflow = make_workflow()
        self.write_workflow(workflow)
        self.write_journal([self.event("task0001", "failed"), self.event("task0003", "merged")])
        removals = [{"task_id": "task0001", "path": THREAT_MODEL}]
        codes = [e["code"] for e in self.dry_run(workflow, removals)]
        self.assertIn("feature-docs-removal-incomplete", codes)

    def test_the_blocked_conditions_are_the_conditions_the_validator_rejects(self):
        workflow = make_workflow(tasks={
            "task0001": {"status": "failed", "files": [THREAT_MODEL, "src/a.py"]},
            "task0002": {"status": "in_progress", "files": [NOTES, "src/b.py"]},
            "task0003": {"status": "merged", "files": [THIRD, "src/c.py"]},
        })
        self.write_workflow(workflow)
        self.write_journal([self.event("task0001", "failed")])
        result = self.judge()
        self.assertEqual(result["entry"], "blocked")
        removals = [{"task_id": t["task_id"], "path": t["path"]} for t in result["targets"]]
        validator_codes = {e["code"] for e in self.dry_run(workflow, removals)}
        self.assertTrue({e["code"] for e in result["errors"]} <= validator_codes)


if __name__ == "__main__":
    unittest.main()
