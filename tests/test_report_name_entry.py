"""Tests for task0002 of subagent-report-write-block: `report-name-entry.py`,
the FR6 judgment, and the journal replay it shares with the validator.

Acceptance Criteria covered (feature-docs/subagent-report-write-block/tasks/
task0002.md):

- AC-6: `none`, `dispatch` and `blocked` as contracted, `failed_journal_line`
  on each violation, exit 2 on a missing argument or on a base that does not
  resolve when one is needed (TS-21).
- AC-3 (the journal half of conditions 1 and 2) through the entry script.

Acceptance Criteria covered (feature-docs/final-path-correction-medium-fixes/
tasks/task0002.md), classes TestEntryWidened, TestEntryDocstring and
TestEntryOutputPassesTheValidator:

- AC-1: a failed task and an unstarted task are both listed (TS-7).
- AC-2: no violation in the failed tasks is `none`, whatever others hold.
- AC-3: a merged task is not listed; an unstarted task whose last journal
  event is `merged`, or whose name is a directory at the base, is blocked
  (TS-7).
- AC-4: the output of two targets, corrected in a patch, passes the validator
  (TS-8).
- AC-5: the output keys and the docstring (TS-16).

Every repository is built in a temporary directory with the identity set per
command. A file with an FR2 name is only ever created at run time, inside such
a repository.
"""

import ast
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = REPO_ROOT / "em-workflow" / "scripts"
ENTRY_PATH = SCRIPTS / "report-name-entry.py"
VALIDATOR_PATH = SCRIPTS / "validate-worker-output.py"


def _load_validator():
    spec = importlib.util.spec_from_file_location("validate_worker_output", VALIDATOR_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VWO = _load_validator()

MATCHING = "test-docs/demo/REPORT.md"


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
        "task0001": {"status": "failed", "files": [MATCHING, "src/a.py"]},
        "task0002": {"status": "merged", "files": ["src/b.py"]},
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

    def run_entry(self, omit=None, script=ENTRY_PATH, **override):
        args = [sys.executable, str(script)]
        for flag, value in self.arguments(**override).items():
            if flag != omit:
                args += [flag, value]
        return subprocess.run(args, capture_output=True, text=True, env=_git_env())

    def judge(self, **override):
        result = self.run_entry(**override)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return json.loads(result.stdout)


class TestEntryNone(EntryCase):
    def test_implement_that_is_not_failed_is_none(self):
        for status in ("pending", "in_progress", "completed"):
            with self.subTest(status):
                self.write_workflow(make_workflow(implement=status))
                self.write_journal([self.event("task0001", "failed")])
                self.assertEqual(self.judge(), {"entry": "none", "violations": [], "errors": []})

    def test_a_failed_task_without_a_matching_name_is_none(self):
        workflow = make_workflow(tasks={"task0001": {"status": "failed", "files": ["src/a.py", "docs/reports/x.md"]}})
        self.write_workflow(workflow)
        self.assertEqual(self.judge(), {"entry": "none", "violations": [], "errors": []})

    def test_a_matching_name_that_is_a_regular_file_at_the_base_is_an_update(self):
        self.commit_files({MATCHING: "existing\n"})
        self.write_workflow(make_workflow())
        self.assertEqual(self.judge()["entry"], "none")

    def test_a_matching_name_in_a_task_that_did_not_fail_is_none(self):
        workflow = make_workflow(tasks={
            "task0001": {"status": "failed", "files": ["src/a.py"]},
            "task0002": {"status": "pending", "files": [MATCHING]},
            "task0003": {"status": "merged", "files": ["test-docs/demo/SUMMARY.md"]},
        })
        self.write_workflow(workflow)
        self.assertEqual(self.judge()["entry"], "none")

    def test_a_task_whose_last_journal_event_is_failed_but_is_merged_did_not_fail(self):
        workflow = make_workflow(tasks={"task0001": {"status": "merged", "files": [MATCHING]}})
        self.write_workflow(workflow)
        self.write_journal([self.event("task0001", "failed")])
        self.assertEqual(self.judge()["entry"], "none")

    def test_an_unusable_base_is_not_read_without_a_matching_name(self):
        self.write_workflow(make_workflow(tasks={"task0001": {"status": "failed", "files": ["src/a.py"]}}))
        for base in ("0" * 40, "HEAD", "not-hex"):
            with self.subTest(base=base):
                self.assertEqual(self.judge(**{"--base-commit": base})["entry"], "none")
        self.assertEqual(self.judge(**{"--target-repo": str(self.tmp / "missing")})["entry"], "none")


class TestEntryDispatch(EntryCase):
    def test_a_violation_with_conditions_1_to_3_holding_is_dispatch(self):
        self.write_workflow(make_workflow())
        self.write_journal([
            self.event("task0001", "launched"), self.event("task0001", "failed"),
            self.event("task0002", "launched"), self.event("task0002", "merged"),
        ])
        result = self.judge()
        self.assertEqual(result["entry"], "dispatch")
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["violations"], [{"task_id": "task0001", "path": MATCHING, "failed_journal_line": 2}])

    def test_the_journal_line_is_the_last_failed_event_with_every_line_counted(self):
        self.write_workflow(make_workflow())
        self.write_journal([
            "\n",
            self.event("task0001", "failed"),
            "not json\n",
            json.dumps({"task": "task0001", "event": "mystery"}) + "\n",
            json.dumps({"task": "bad id", "event": "failed"}) + "\n",
            self.event("task0001", "launched"),
            self.event("task0001", "failed"),
            self.event("task0002", "merged"),
        ])
        violation = self.judge()["violations"][0]
        self.assertEqual(violation["failed_journal_line"], 7)

    def test_the_journal_line_is_null_without_a_failed_event(self):
        self.write_workflow(make_workflow())
        for lines in (None, [self.event("task0002", "merged")]):
            with self.subTest(lines=lines):
                if lines is None:
                    self.journal_path.unlink(missing_ok=True)
                else:
                    self.write_journal(lines)
                result = self.judge()
                self.assertEqual(result["entry"], "dispatch")
                self.assertEqual(result["violations"][0]["failed_journal_line"], None)

    def test_a_missing_journal_file_reads_as_no_events(self):
        self.write_workflow(make_workflow())
        self.assertFalse(self.journal_path.exists())
        self.assertEqual(self.judge()["entry"], "dispatch")

    def test_a_task_failed_by_its_journal_alone_counts(self):
        workflow = make_workflow(tasks={"task0001": {"status": "pending", "files": [MATCHING]}})
        self.write_workflow(workflow)
        self.write_journal([self.event("task0001", "launched"), self.event("task0001", "failed")])
        result = self.judge()
        self.assertEqual(result["entry"], "dispatch")
        self.assertEqual(result["violations"][0]["failed_journal_line"], 2)

    def test_every_violation_of_every_failed_task_is_listed(self):
        workflow = make_workflow(tasks={
            "task0001": {"status": "failed", "files": [MATCHING, "docs/Summary-1.md", "src/a.py"]},
            "task0002": {"status": "failed", "files": [MATCHING]},
        })
        self.write_workflow(workflow)
        self.write_journal([self.event("task0001", "failed"), self.event("task0002", "failed")])
        result = self.judge()
        self.assertEqual(result["entry"], "dispatch")
        self.assertEqual(
            [(v["task_id"], v["path"], v["failed_journal_line"]) for v in result["violations"]],
            [("task0001", MATCHING, 1), ("task0001", "docs/Summary-1.md", 1), ("task0002", MATCHING, 2)],
        )

    def test_the_output_carries_exactly_the_contracted_keys(self):
        self.write_workflow(make_workflow())
        result = self.judge()
        self.assertEqual(set(result), {"entry", "violations", "errors"})
        for violation in result["violations"]:
            self.assertEqual(set(violation), {"task_id", "path", "failed_journal_line"})


class TestEntryBlocked(EntryCase):
    def assert_blocked(self, code):
        result = self.judge()
        self.assertEqual(result["entry"], "blocked")
        self.assertIn(code, [e["code"] for e in result["errors"]])
        self.assertTrue(result["violations"])
        return result

    def test_condition_1_a_task_in_progress(self):
        workflow = make_workflow(tasks={
            "task0001": {"status": "failed", "files": [MATCHING]},
            "task0002": {"status": "in_progress", "files": ["src/b.py"]},
        })
        self.write_workflow(workflow)
        self.write_journal([self.event("task0001", "failed")])
        result = self.assert_blocked("path-correction-in-flight")
        self.assertEqual(result["violations"][0]["failed_journal_line"], 1)

    def test_condition_1_a_launched_last_event(self):
        self.write_workflow(make_workflow())
        self.write_journal([self.event("task0001", "failed"), self.event("task0002", "launched")])
        self.assert_blocked("path-correction-in-flight")

    def test_a_blocked_violation_carries_a_null_line_without_a_failed_event(self):
        self.write_workflow(make_workflow())
        self.write_journal([self.event("task0001", "launched")])
        result = self.assert_blocked("path-correction-in-flight")
        self.assertIsNone(result["violations"][0]["failed_journal_line"])

    def test_condition_2_a_merged_last_event_on_a_task_whose_status_is_failed(self):
        self.write_workflow(make_workflow())
        self.write_journal([self.event("task0001", "failed"), self.event("task0001", "merged")])
        result = self.assert_blocked("path-correction-merged")
        self.assertEqual(result["violations"][0]["failed_journal_line"], 1)

    def test_condition_3_a_matching_name_that_is_a_directory_at_the_base(self):
        self.commit_files({MATCHING + "/inner.txt": "x\n"})
        self.write_workflow(make_workflow())
        self.assert_blocked("path-correction-old-path")

    def test_condition_3_a_matching_name_that_is_a_symlink_at_the_base(self):
        os.symlink("a.py", self.root / "src" / "REPORT.md")
        self.commit_files({})
        workflow = make_workflow(tasks={"task0001": {"status": "failed", "files": ["src/REPORT.md"]}})
        self.write_workflow(workflow)
        self.assert_blocked("path-correction-old-path")

    def test_blocked_is_still_exit_0_and_leaves_workflow_untouched(self):
        self.write_workflow(make_workflow())
        self.write_journal([self.event("task0002", "launched")])
        before = self.workflow_path.read_bytes()
        result = self.run_entry()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.workflow_path.read_bytes(), before)


SECOND = "test-docs/demo/SUMMARY.md"


# Recurrence tests for finding 4409a460572aac40 (final-path-correction-medium-fixes, FR4).
class TestEntryWidened(EntryCase):
    """Recurrence tests for finding 4409a460572aac40: once a failed task holds
    a violation, the targets are the violations of every task whose status is
    not `merged`, because the validator rejects a carried non-merged task that
    still holds a new report-artifact name."""

    def listed(self, result):
        return [(v["task_id"], v["path"], v["failed_journal_line"]) for v in result["violations"]]

    def test_a_failed_task_and_an_unstarted_task_are_both_listed(self):
        self.write_workflow(make_workflow(tasks={
            "task0001": {"status": "failed", "files": [MATCHING, "src/a.py"]},
            "task0002": {"status": "pending", "files": [SECOND]},
        }))
        self.write_journal([self.event("task0001", "launched"), self.event("task0001", "failed")])
        result = self.judge()
        self.assertEqual(result["entry"], "dispatch")
        self.assertEqual(result["errors"], [])
        self.assertEqual(self.listed(result), [("task0001", MATCHING, 2), ("task0002", SECOND, None)])

    def test_the_list_follows_the_task_mapping_then_the_file_order(self):
        self.write_workflow(make_workflow(tasks={
            "task0001": {"status": "pending", "files": ["src/a.py", SECOND, "docs/Analysis-1.md"]},
            "task0002": {"status": "failed", "files": [MATCHING, "docs/Summary-1.md"]},
            "task0003": {"status": "pending", "files": ["docs/Findings.md"]},
        }))
        self.write_journal([self.event("task0002", "failed")])
        result = self.judge()
        self.assertEqual(result["entry"], "dispatch")
        self.assertEqual(
            self.listed(result),
            [
                ("task0001", SECOND, None),
                ("task0001", "docs/Analysis-1.md", None),
                ("task0002", MATCHING, 1),
                ("task0002", "docs/Summary-1.md", 1),
                ("task0003", "docs/Findings.md", None),
            ],
        )

    def test_a_task_in_any_status_but_merged_is_listed(self):
        for status in ("pending", "needs_update", "skipped"):
            with self.subTest(status):
                self.write_workflow(make_workflow(tasks={
                    "task0001": {"status": "failed", "files": [MATCHING]},
                    "task0002": {"status": status, "files": [SECOND]},
                }))
                result = self.judge()
                self.assertEqual([v["task_id"] for v in result["violations"]], ["task0001", "task0002"])

    def test_the_output_keys_do_not_change(self):
        self.write_workflow(make_workflow(tasks={
            "task0001": {"status": "failed", "files": [MATCHING]},
            "task0002": {"status": "pending", "files": [SECOND]},
        }))
        result = self.judge()
        self.assertEqual(set(result), {"entry", "violations", "errors"})
        for violation in result["violations"]:
            self.assertEqual(set(violation), {"task_id", "path", "failed_journal_line"})

    def test_a_failed_task_without_a_violation_is_none_whatever_others_hold(self):
        # AC-2: the `none` decision is made on the failed tasks alone.
        self.write_workflow(make_workflow(tasks={
            "task0001": {"status": "failed", "files": ["src/a.py"]},
            "task0002": {"status": "pending", "files": [SECOND]},
        }))
        self.assertEqual(self.judge(), {"entry": "none", "violations": [], "errors": []})

    def test_a_failed_task_whose_name_is_an_update_is_none_whatever_others_hold(self):
        self.commit_files({MATCHING: "existing\n"})
        self.write_workflow(make_workflow(tasks={
            "task0001": {"status": "failed", "files": [MATCHING]},
            "task0002": {"status": "pending", "files": [SECOND]},
        }))
        self.assertEqual(self.judge(), {"entry": "none", "violations": [], "errors": []})

    def test_the_base_is_not_read_for_the_names_of_other_tasks_when_none(self):
        self.write_workflow(make_workflow(tasks={
            "task0001": {"status": "failed", "files": ["src/a.py"]},
            "task0002": {"status": "pending", "files": [SECOND]},
        }))
        for base in ("0" * 40, "HEAD", "not-hex"):
            with self.subTest(base=base):
                self.assertEqual(self.judge(**{"--base-commit": base})["entry"], "none")

    def test_a_merged_task_holding_a_name_is_not_listed(self):
        self.write_workflow(make_workflow(tasks={
            "task0001": {"status": "failed", "files": [MATCHING]},
            "task0002": {"status": "merged", "files": [SECOND]},
        }))
        self.write_journal([self.event("task0001", "failed"), self.event("task0002", "merged")])
        result = self.judge()
        self.assertEqual(result["entry"], "dispatch")
        self.assertEqual(self.listed(result), [("task0001", MATCHING, 1)])

    def test_an_unstarted_task_whose_last_journal_event_is_merged_is_blocked(self):
        self.write_workflow(make_workflow(tasks={
            "task0001": {"status": "failed", "files": [MATCHING]},
            "task0002": {"status": "pending", "files": [SECOND]},
        }))
        self.write_journal([
            self.event("task0001", "failed"),
            self.event("task0002", "launched"),
            self.event("task0002", "merged"),
        ])
        result = self.judge()
        self.assertEqual(result["entry"], "blocked")
        self.assertEqual(
            [(e["code"], e["task_id"]) for e in result["errors"] if e["code"] == "path-correction-merged"],
            [("path-correction-merged", "task0002")],
        )
        self.assertEqual(self.listed(result), [("task0001", MATCHING, 1), ("task0002", SECOND, None)])

    def test_an_unstarted_task_whose_name_is_a_directory_at_the_base_is_blocked(self):
        self.commit_files({SECOND + "/inner.txt": "x\n"})
        self.write_workflow(make_workflow(tasks={
            "task0001": {"status": "failed", "files": [MATCHING]},
            "task0002": {"status": "pending", "files": [SECOND]},
        }))
        result = self.judge()
        self.assertEqual(result["entry"], "blocked")
        self.assertEqual(
            [(e["task_id"], e["path"]) for e in result["errors"] if e["code"] == "path-correction-old-path"],
            [("task0002", SECOND)],
        )
        self.assertEqual(self.listed(result), [("task0001", MATCHING, None), ("task0002", SECOND, None)])

    def test_condition_1_is_judged_on_the_whole_list(self):
        self.write_workflow(make_workflow(tasks={
            "task0001": {"status": "failed", "files": [MATCHING]},
            "task0002": {"status": "pending", "files": [SECOND]},
            "task0003": {"status": "in_progress", "files": ["src/b.py"]},
        }))
        result = self.judge()
        self.assertEqual(result["entry"], "blocked")
        self.assertIn("path-correction-in-flight", [e["code"] for e in result["errors"]])
        self.assertEqual([v["task_id"] for v in result["violations"]], ["task0001", "task0002"])

    def test_the_exit_codes_are_unchanged(self):
        self.write_workflow(make_workflow(tasks={
            "task0001": {"status": "failed", "files": [MATCHING]},
            "task0002": {"status": "pending", "files": [SECOND]},
        }))
        for flag in self.arguments():
            with self.subTest(omit=flag):
                self.assertEqual(self.run_entry(omit=flag).returncode, 2)
        unusable = self.run_entry(**{"--base-commit": "0" * 40})
        self.assertEqual((unusable.returncode, unusable.stdout), (2, ""))
        self.assertEqual(self.run_entry().returncode, 0)


class TestEntryDocstring(unittest.TestCase):
    def test_the_docstring_states_fr4_and_the_two_steps(self):
        tree = ast.parse(ENTRY_PATH.read_text(encoding="utf-8"))
        doc = ast.get_docstring(tree)
        self.assertIsNotNone(doc)
        doc = " ".join(doc.split())  # the docstring wraps lines; compare phrases
        self.assertIn("FR4", doc)
        self.assertIn("final-path-correction-medium-fixes", doc)
        self.assertIn("every task whose status is not `merged`", doc)
        self.assertIn("failed_journal_line", doc)
        self.assertIn("null", doc)


# Recurrence test for finding 4409a460572aac40 (final-path-correction-medium-fixes, FR4).
class TestEntryOutputPassesTheValidator(EntryCase):
    """TS-8: the violations the entry lists are exactly what a patch has to
    correct; fed through a patch that corrects them all, the validator's dry
    run reports nothing. Finding 4409a460572aac40."""

    FEATURE_DIR = "feature-docs/demo"
    OLD_NAMES = {MATCHING: "test-docs/demo/audit-report.md", SECOND: "test-docs/demo/audit-summary.md"}
    DIGEST_SOURCE = {
        "answers_digest": "sha256:" + "2" * 64,
        "digest_inputs": {"feature-docs/demo/SPEC.md": "sha256:" + "1" * 64},
        "mode": "interactive",
        "value_inputs": {"task_description": None},
        "worker": "implementation-planner",
        "workflow_blob": "8f17c04",
        "write_policy_digest": "sha256:" + "3" * 64,
    }
    DOCUMENTS = {
        "IMPLEMENTATION.md": (
            "# Implementation Plan: demo\n"
            "\n"
            "The report is `test-docs/demo/REPORT.md`. REPORT.md is written by task0001 only.\n"
            "The summary is `test-docs/demo/SUMMARY.md`. SUMMARY.md is written by task0003 only.\n"
            "\n"
            "## Shared Components\n"
            "\n"
            "None.\n"
        ),
        "VERIFICATION.md": (
            "# Verification Document: demo\n"
            "\n"
            "### Test Scenarios from SPEC.md\n"
            "| ID | Scenario | Expected Result |\n"
            "|----|----------|-----------------|\n"
            "| TS-1 | Read `test-docs/demo/REPORT.md` | It holds one finding |\n"
            "| TS-2 | Read `test-docs/demo/SUMMARY.md` | It holds one line |\n"
        ),
        "tasks/task0001.md": (
            "# Task Plan: task0001 - report\n"
            "\n"
            "## Scope\n"
            "\n"
            "### Files to Create\n"
            "- `test-docs/demo/REPORT.md` - the report\n"
            "\n"
            "### Files to Modify\n"
            "- `src/a.py` - change\n"
            "\n"
            "## Acceptance Criteria (MANDATORY)\n"
            "\n"
            "- [ ] AC-1: REPORT.md lists one finding (TS-1).\n"
        ),
        "tasks/task0002.md": (
            "# Task Plan: task0002 - code\n"
            "\n"
            "## Scope\n"
            "\n"
            "### Files to Modify\n"
            "- `src/b.py` - change\n"
            "\n"
            "## Acceptance Criteria (MANDATORY)\n"
            "\n"
            "- [ ] AC-1: it works.\n"
        ),
        "tasks/task0003.md": (
            "# Task Plan: task0003 - summary\n"
            "\n"
            "## Scope\n"
            "\n"
            "### Files to Create\n"
            "- `test-docs/demo/SUMMARY.md` - the summary\n"
            "\n"
            "## Acceptance Criteria (MANDATORY)\n"
            "\n"
            "- [ ] AC-1: SUMMARY.md holds one line (TS-2).\n"
        ),
    }

    def setUp(self):
        super().setUp()
        self.feature_dir = self.root / self.FEATURE_DIR
        self.commit_files({f"{self.FEATURE_DIR}/{rel}": text for rel, text in self.DOCUMENTS.items()})
        self.workflow = make_workflow(tasks={
            "task0001": {"status": "failed", "files": [MATCHING, "src/a.py"]},
            "task0002": {"status": "merged", "files": ["src/b.py"]},
            "task0003": {"status": "pending", "files": [SECOND]},
        })
        self.write_workflow(self.workflow)
        self.write_journal([
            self.event("task0001", "launched"), self.event("task0001", "failed"),
            self.event("task0002", "launched"), self.event("task0002", "merged"),
        ])

    def correct_documents(self, corrections):
        """Plays the planner: one left-to-right pass replaces each old path,
        and each bare old file name, by its new one, in every document."""
        mapping = {}
        for c in corrections:
            mapping[c["old_path"]] = c["new_path"]
            mapping[c["old_path"].rsplit("/", 1)[-1]] = c["new_path"].rsplit("/", 1)[-1]
        if not mapping:
            return
        tokens = sorted(mapping, key=lambda token: (-len(token), token))
        pattern = re.compile("|".join(re.escape(token) for token in tokens))
        for rel in self.DOCUMENTS:
            target = self.feature_dir / rel
            target.write_text(
                pattern.sub(lambda m: mapping[m.group(0)], target.read_text(encoding="utf-8")),
                encoding="utf-8",
            )

    def patch_correcting(self, corrections):
        return {
            "schema_version": 1,
            "patch_id": "create-plan-p0001",
            "base_input_digest": VWO.normalize_json_sha256(self.DIGEST_SOURCE),
            "base_workflow_blob": self.DIGEST_SOURCE["workflow_blob"],
            "operation": "replace_planning",
            "tasks_patch": {
                "mode": "replace_all",
                "carried_task_ids": list(self.workflow["tasks"]),
                "entries": {},
                "path_corrections": corrections,
            },
            "requirements_patch": None,
            "step_patches": [],
            "preserve": ["workflow.implement.base_commit"],
        }

    def test_the_entry_output_corrected_in_a_patch_passes_the_dry_run(self):
        result = self.judge()
        self.assertEqual(result["entry"], "dispatch")
        corrections = [
            {"task_id": v["task_id"], "old_path": v["path"], "new_path": self.OLD_NAMES[v["path"]]}
            for v in result["violations"]
        ]
        self.correct_documents(corrections)
        errors = VWO.validate_workflow_patch(
            self.patch_correcting(corrections),
            workflow=self.workflow,
            digest_source=self.DIGEST_SOURCE,
            dry_run=True,
            feature_dir=self.feature_dir,
            target_repo=self.root,
            base_commit=self.base,
            journal=self.journal_path,
        )
        self.assertEqual([e["code"] for e in errors], [], errors)
        self.assertEqual(
            sorted((c["task_id"], c["old_path"]) for c in corrections),
            [("task0001", MATCHING), ("task0003", SECOND)],
        )


class TestEntryExecutionErrors(EntryCase):
    def setUp(self):
        super().setUp()
        self.write_workflow(make_workflow())

    def test_a_missing_argument_exits_2(self):
        for flag in self.arguments():
            with self.subTest(flag):
                self.assertEqual(self.run_entry(omit=flag).returncode, 2)

    def test_a_base_that_does_not_resolve_exits_2_when_a_matching_name_needs_it(self):
        for base in ("0" * 40, "HEAD", self.base[:12], self.base.upper(), "not-hex", ""):
            with self.subTest(base=base):
                result = self.run_entry(**{"--base-commit": base})
                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertEqual(result.stdout, "")

    def test_a_target_repository_that_is_not_a_repository_exits_2(self):
        for target in (str(self.tmp / "missing"), str(self.tmp)):
            with self.subTest(target=target):
                self.assertEqual(self.run_entry(**{"--target-repo": target}).returncode, 2)

    def test_an_unreadable_journal_exits_2(self):
        self.journal_path.mkdir()
        self.assertEqual(self.run_entry().returncode, 2)

    def test_a_broken_workflow_exits_2(self):
        self.assertEqual(self.run_entry(**{"--workflow": str(self.tmp / "missing.yaml")}).returncode, 2)
        self.workflow_path.write_text("- just\n- a list\n", encoding="utf-8")
        self.assertEqual(self.run_entry().returncode, 2)
        self.workflow_path.write_text("key: [unclosed\n", encoding="utf-8")
        self.assertEqual(self.run_entry().returncode, 2)

    def test_the_validator_is_located_as_a_sibling_file(self):
        copy_dir = self.tmp / "copy"
        copy_dir.mkdir()
        shutil.copy(ENTRY_PATH, copy_dir / ENTRY_PATH.name)
        shutil.copy(VALIDATOR_PATH, copy_dir / VALIDATOR_PATH.name)
        # The sibling copy's references directory is absent, so only the
        # entry's own load is exercised; the validator reads it lazily.
        result = self.run_entry(script=copy_dir / ENTRY_PATH.name)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["entry"], "dispatch")
        (copy_dir / VALIDATOR_PATH.name).unlink()
        self.assertEqual(self.run_entry(script=copy_dir / ENTRY_PATH.name).returncode, 2)


class TestJournalReplay(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "journal.jsonl"

    def write(self, data):
        self.path.write_bytes(data if isinstance(data, bytes) else data.encode("utf-8"))

    def test_a_missing_file_reads_as_no_events(self):
        self.assertEqual(VWO.journal_last_events(self.path), {})
        self.assertEqual(VWO.read_journal_events(self.path), ({}, {}))

    def test_an_unreadable_file_raises(self):
        self.path.mkdir()
        with self.assertRaises(VWO.ExecutionError):
            VWO.journal_last_events(self.path)

    def test_the_last_event_of_each_task_and_its_line(self):
        self.write(
            '{"task":"task0001","event":"launched"}\n'
            '{"task":"task0002","event":"launched"}\n'
            '{"task":"task0001","event":"failed"}\n'
        )
        self.assertEqual(
            VWO.journal_last_events(self.path),
            {"task0001": ("failed", 3), "task0002": ("launched", 2)},
        )

    def test_blank_malformed_unknown_and_invalid_lines_are_skipped_but_counted(self):
        self.write(
            "\n"
            "garbage\n"
            "[]\n"
            '{"task":"task0001","event":"mystery"}\n'
            '{"task":"Task1","event":"failed"}\n'
            '{"task":3,"event":"failed"}\n'
            '{"task":"task0001","event":"launched"}\n'
        )
        self.assertEqual(VWO.journal_last_events(self.path), {"task0001": ("launched", 7)})

    def test_a_cr_is_not_a_line_delimiter_and_a_final_segment_without_lf_counts(self):
        self.write(
            b'{"task":"task0001","event":"launched"}\r\n'
            b'{"task":"task0001","event":"failed"}\r\n'
            b'\r\n'
            b'{"task":"task0002","event":"merged"}'
        )
        self.assertEqual(
            VWO.journal_last_events(self.path),
            {"task0001": ("failed", 2), "task0002": ("merged", 4)},
        )

    def test_a_lone_cr_inside_a_line_does_not_split_it(self):
        self.write(b'{"task":"task0001",\r"event":"failed"}\n')
        self.assertEqual(VWO.journal_last_events(self.path), {"task0001": ("failed", 1)})

    def test_the_last_failed_line_survives_a_later_event(self):
        self.write(
            '{"task":"task0001","event":"failed"}\n'
            '{"task":"task0001","event":"launched"}\n'
        )
        last_events, last_failed = VWO.read_journal_events(self.path)
        self.assertEqual(last_events, {"task0001": ("launched", 2)})
        self.assertEqual(last_failed, {"task0001": 1})

    def test_the_line_rule_matches_the_stop_guard_replay(self):
        guard_path = REPO_ROOT / "em-workflow" / "hooks" / "queue_stop_guard.py"
        spec = importlib.util.spec_from_file_location("queue_stop_guard", guard_path)
        guard = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(guard)
        self.write(
            b'\n{"task":"task0001","event":"launched"}\r\n'
            b'garbage\n'
            b'{"task":"task0002","event":"failed"}\n'
            b'{"task":"task0001","event":"merged"}'
        )
        self.assertEqual(VWO.journal_last_events(self.path), guard.read_journal(str(self.path)))


if __name__ == "__main__":
    unittest.main()
