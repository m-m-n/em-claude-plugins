"""Tests for task0002 of subagent-report-write-block: the validator side of
the final-path correction (FR5), the FR3 check on carried tasks, and the
scenario-ID scan exception (IMPLEMENTATION.md D2, D3, D8).

Acceptance Criteria covered (feature-docs/subagent-report-write-block/tasks/
task0002.md):

- AC-1: permission states of `path_corrections` (TS-22, TM-6).
- AC-2: the FR3 judgment on carried non-merged tasks, after corrections
  (TS-9).
- AC-3: conditions 1 to 4 (TS-10, TM-4).
- AC-4: condition 5, the normalization comparison (TS-10, TM-5).
- AC-5: the in-memory application and the Files-section agreement
  (TS-10, TS-11).
- AC-7: literal treatment of old_path / new_path, the scenario-ID scan
  exception and the two fixtures (TS-19, TM-1).

Every repository is built in a temporary directory with the identity set per
command, and the documents are committed before they are edited in the
working tree to play the planner's corrected output. A file with an FR2 name
is only ever created at run time, inside such a repository.
"""

import copy
import importlib.util
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "em-workflow" / "scripts" / "validate-worker-output.py"
FIXTURES_ROOT = REPO_ROOT / "em-workflow" / "references" / "fixtures"
PATCH_FIXTURES = FIXTURES_ROOT / "workflow-patch" / "replace_planning"


def _load_module():
    spec = importlib.util.spec_from_file_location("validate_worker_output", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VWO = _load_module()

OLD_PATH = "test-docs/demo/REPORT.md"
NEW_PATH = "test-docs/demo/audit-report.md"
OLD_NAME = "REPORT.md"
NEW_NAME = "audit-report.md"

DIGEST_SOURCE = {
    "answers_digest": "sha256:" + "2" * 64,
    "digest_inputs": {"feature-docs/demo/SPEC.md": "sha256:" + "1" * 64},
    "mode": "interactive",
    "value_inputs": {"task_description": None},
    "worker": "implementation-planner",
    "workflow_blob": "8f17c04",
    "write_policy_digest": "sha256:" + "3" * 64,
}

IMPLEMENTATION_MD = (
    "# Implementation Plan: demo\n"
    "\n"
    "The report is `test-docs/demo/REPORT.md`. REPORT.md is written by task0001 only.\n"
    "\n"
    "## Shared Components\n"
    "\n"
    "None.\n"
)
VERIFICATION_MD = (
    "# Verification Document: demo\n"
    "\n"
    "### Test Scenarios from SPEC.md\n"
    "| ID | Scenario | Expected Result |\n"
    "|----|----------|-----------------|\n"
    "| TS-1 | Read `test-docs/demo/REPORT.md` | It holds one finding |\n"
)
TASK0001_MD = (
    "# Task Plan: task0001 - report\n"
    "\n"
    "## Scope\n"
    "\n"
    "### Files to Create\n"
    "- `test-docs/demo/REPORT.md` - the report\n"
    "- `src/a.py` - code\n"
    "\n"
    "### Files to Modify\n"
    "- `src/b.py` - change\n"
    "\n"
    "## Design\n"
    "\n"
    "Write `test-docs/demo/REPORT.md` with one finding.\n"
    "\n"
    "## Acceptance Criteria (MANDATORY)\n"
    "\n"
    "- [ ] AC-1: `test-docs/demo/REPORT.md` lists one finding (TS-1).\n"
    "\n"
    "## Test Notes\n"
    "\n"
    "None.\n"
)
TASK0002_MD = (
    "# Task Plan: task0002 - code\n"
    "\n"
    "## Scope\n"
    "\n"
    "### Files to Create\n"
    "- `src/c.py` - code\n"
    "\n"
    "## Acceptance Criteria (MANDATORY)\n"
    "\n"
    "- [ ] AC-1: it works.\n"
)


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


class DemoRepo:
    """A disposable repository holding feature-docs/demo, committed."""

    def __init__(self, tmp, *, with_verification=True, extra_files=None):
        self.root = Path(tmp) / "repo"
        self.root.mkdir()
        git(self.root, "init", "-q")
        self.feature_dir = self.root / "feature-docs" / "demo"
        self.write("IMPLEMENTATION.md", IMPLEMENTATION_MD)
        if with_verification:
            self.write("VERIFICATION.md", VERIFICATION_MD)
        self.write("tasks/task0001.md", TASK0001_MD)
        self.write("tasks/task0002.md", TASK0002_MD)
        for rel, content in (extra_files or {}).items():
            target = self.root / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "base")
        self.base = git(self.root, "rev-parse", "HEAD")
        self.journal = Path(tmp) / "journal.jsonl"

    def write(self, rel, text):
        target = self.feature_dir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def read(self, rel):
        return (self.feature_dir / rel).read_text(encoding="utf-8")

    def correct_documents(self, old_path=OLD_PATH, new_path=NEW_PATH, old_name=OLD_NAME, new_name=NEW_NAME):
        """Plays the planner: one pass replaces the path, and the bare name
        where no path stands, in every document."""
        pattern = re.compile("|".join(re.escape(t) for t in (old_path, old_name)))
        mapping = {old_path: new_path, old_name: new_name}
        for rel in ("IMPLEMENTATION.md", "VERIFICATION.md", "tasks/task0001.md"):
            if (self.feature_dir / rel).exists():
                self.write(rel, pattern.sub(lambda m: mapping[m.group(0)], self.read(rel)))

    def write_journal(self, events):
        self.journal.write_text(
            "".join(json.dumps({"task": t, "event": e}) + "\n" for t, e in events), encoding="utf-8"
        )


def make_workflow(base_commit, *, create_plan="completed", implement="failed", statuses=None, files=None):
    statuses = statuses or {"task0001": "failed", "task0002": "merged"}
    files = files or {"task0001": [OLD_PATH, "src/a.py", "src/b.py"], "task0002": ["src/c.py"]}

    def record(task_id):
        return {
            "title": f"title of {task_id}",
            "plan": f"tasks/{task_id}.md",
            "files": list(files[task_id]),
            "skills": ["backend-impl"],
            "domains": ["input-handling"],
            "complexity": "low",
            "requirements": ["FR1"],
            "status": statuses[task_id],
            "notes": "report-name-write-rejected: kept for the test" if statuses[task_id] == "failed" else None,
            "branch": f"em-workflow/demo/{task_id}",
            "routeback_failed_journal_line": 7,
        }

    return {
        "schema_version": 1,
        "feature": "demo",
        "project": {"license": "MIT"},
        "requirements": {"FR1": {"status": "ok", "tasks": [], "tests": [], "title": "x"}},
        "workflow": [
            {"id": "create-spec", "status": "completed", "completed_at_commit": "aaa"},
            {"id": "design", "status": "skipped", "skipped_reason": "no UI"},
            {"id": "create-plan", "status": create_plan},
            {"id": "implement", "status": implement, "base_commit": base_commit},
            {"id": "review", "status": "pending"},
            {"id": "verify", "status": "pending"},
            {"id": "retrospect", "status": "pending"},
        ],
        "tasks": {task_id: record(task_id) for task_id in statuses},
    }


def make_patch(corrections, *, carried=("task0001", "task0002"), entries=None, step_patches=None,
               preserve=("workflow.implement.base_commit",)):
    tasks_patch = {"mode": "replace_all", "carried_task_ids": list(carried), "entries": entries or {}}
    if corrections is not None:
        tasks_patch["path_corrections"] = corrections
    return {
        "schema_version": 1,
        "patch_id": "create-plan-p0001",
        "base_input_digest": VWO.normalize_json_sha256(DIGEST_SOURCE),
        "base_workflow_blob": DIGEST_SOURCE["workflow_blob"],
        "operation": "replace_planning",
        "tasks_patch": tasks_patch,
        "requirements_patch": None,
        "step_patches": step_patches or [],
        "preserve": list(preserve),
    }


def correction(task_id="task0001", old_path=OLD_PATH, new_path=NEW_PATH):
    return {"task_id": task_id, "old_path": old_path, "new_path": new_path}


def validate(patch, workflow, repo, *, dry_run=True, phase_state=None, journal="default", base="default"):
    kwargs = {}
    if dry_run:
        # The base and journal inputs matter only under --dry-run-apply.
        kwargs = dict(
            digest_source=DIGEST_SOURCE,
            phase_state=phase_state,
            dry_run=True,
            feature_dir=repo.feature_dir,
            target_repo=repo.root,
            base_commit=repo.base if base == "default" else base,
            journal=repo.journal if journal == "default" else journal,
        )
    return VWO.validate_workflow_patch(patch, workflow=workflow, **kwargs)


def codes(errors):
    return [e["code"] for e in errors]


class RepoTestCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = tmp.name
        self.repo = DemoRepo(self.tmp)
        self.repo.write_journal([("task0001", "launched"), ("task0001", "failed"),
                                 ("task0002", "launched"), ("task0002", "merged")])
        self.workflow = make_workflow(self.repo.base)

    def good_patch(self):
        return make_patch([correction()])


# ---------------------------------------------------------------------------
# Shape (AC-1, structural, with and without --dry-run-apply)
# ---------------------------------------------------------------------------

class TestPathCorrectionShape(RepoTestCase):
    def shape_codes(self, patch, **kwargs):
        return [c for c in codes(validate(patch, self.workflow, self.repo, **kwargs)) if c.startswith("path-correction")]

    def test_a_well_formed_field_passes_the_structural_check_without_dry_run(self):
        self.assertEqual(validate(self.good_patch(), None, self.repo, dry_run=False), [])

    def test_absent_and_null_are_the_same(self):
        for patch in (make_patch(None), make_patch(None)):
            patch["tasks_patch"]["path_corrections"] = None
            self.assertEqual(validate(patch, None, self.repo, dry_run=False), [])

    def test_malformed_fields_are_path_correction_shape(self):
        cases = {
            "not a list": "oops",
            "empty list": [],
            "item not a mapping": ["x"],
            "extra key": [dict(correction(), note="x")],
            "missing key": [{"task_id": "task0001", "old_path": OLD_PATH}],
            "empty string": [correction(new_path="")],
            "non-string": [correction(old_path=3)],
            "same old and new": [correction(new_path=OLD_PATH)],
            "task not carried": [correction(task_id="task0009")],
            "repeated pair": [correction(), correction(new_path="test-docs/demo/other.md")],
            "one old path to two new paths": [correction(), correction(task_id="task0002", new_path="x/y.md")],
        }
        for label, field in cases.items():
            with self.subTest(label):
                patch = make_patch(field)
                errors = validate(patch, None, self.repo, dry_run=False)
                self.assertIn("path-correction-shape", codes(errors), errors)

    def test_not_permitted_on_append_rework(self):
        patch = {
            "schema_version": 1, "patch_id": "rework-p0001",
            "base_input_digest": "sha256:x", "base_workflow_blob": "8f17c04",
            "operation": "append_rework",
            "tasks_patch": {"mode": "append", "expected_next_task_id": "task0003", "entries": {},
                            "path_corrections": [correction()]},
            "step_patches": [], "preserve": ["workflow.implement.base_commit"],
        }
        errors = validate(patch, None, self.repo, dry_run=False)
        self.assertIn("path-correction-shape", codes(errors))

    def test_shape_errors_do_not_hide_in_the_dry_run(self):
        patch = make_patch([correction(new_path=OLD_PATH)])
        self.assertIn("path-correction-shape", self.shape_codes(patch))


# ---------------------------------------------------------------------------
# Required inputs (exit 2)
# ---------------------------------------------------------------------------

class TestRequiredInputs(RepoTestCase):
    def test_a_missing_input_is_an_execution_error(self):
        self.repo.correct_documents()
        base_kwargs = dict(
            workflow=self.workflow, digest_source=DIGEST_SOURCE, dry_run=True,
            feature_dir=self.repo.feature_dir, target_repo=self.repo.root,
            base_commit=self.repo.base, journal=self.repo.journal,
        )
        self.assertEqual(VWO.validate_workflow_patch(self.good_patch(), **base_kwargs), [])
        for name in ("workflow", "feature_dir", "target_repo", "base_commit", "journal"):
            with self.subTest(name):
                kwargs = dict(base_kwargs, **{name: None})
                with self.assertRaises(VWO.ExecutionError):
                    VWO.validate_workflow_patch(self.good_patch(), **kwargs)

    def test_an_unresolvable_base_is_an_execution_error(self):
        self.repo.correct_documents()
        for base in ("0" * 40, "HEAD", self.repo.base[:12], self.repo.base.upper(), "x" * 40):
            with self.subTest(base=base):
                with self.assertRaises(VWO.ExecutionError):
                    validate(self.good_patch(), self.workflow, self.repo, base=base)

    def test_a_feature_directory_outside_the_repository_is_an_execution_error(self):
        self.repo.correct_documents()
        outside = Path(self.tmp) / "elsewhere"
        outside.mkdir()
        with self.assertRaises(VWO.ExecutionError):
            VWO.validate_workflow_patch(
                self.good_patch(), workflow=self.workflow, digest_source=DIGEST_SOURCE, dry_run=True,
                feature_dir=outside, target_repo=self.repo.root, base_commit=self.repo.base,
                journal=self.repo.journal,
            )

    def test_a_missing_journal_file_reads_as_no_events(self):
        self.repo.correct_documents()
        self.repo.journal.unlink()
        self.assertEqual(validate(self.good_patch(), self.workflow, self.repo), [])

    def test_cli_exits_2_for_a_missing_input_and_0_for_a_complete_call(self):
        self.repo.correct_documents()
        patch_path = Path(self.tmp) / "patch.json"
        workflow_path = Path(self.tmp) / "workflow.json"
        digest_path = Path(self.tmp) / "digest-source.json"
        patch_path.write_text(json.dumps(self.good_patch()), encoding="utf-8")
        workflow_path.write_text(json.dumps(self.workflow), encoding="utf-8")
        digest_path.write_text(json.dumps(DIGEST_SOURCE), encoding="utf-8")
        flags = {
            "--workflow": str(workflow_path),
            "--feature-dir": str(self.repo.feature_dir),
            "--target-repo": str(self.repo.root),
            "--base-commit": self.repo.base,
            "--journal": str(self.repo.journal),
        }

        def run(omit=None, **override):
            args = [sys.executable, str(SCRIPT_PATH), "--kind", "workflow-patch",
                    "--worker", "implementation-planner", "--input", str(patch_path),
                    "--digest-source", str(digest_path), "--dry-run-apply"]
            for flag, value in dict(flags, **override).items():
                if flag != omit:
                    args += [flag, value]
            return subprocess.run(args, capture_output=True, text=True, env=_git_env())

        complete = run()
        self.assertEqual(complete.returncode, 0, complete.stdout + complete.stderr)
        for flag in flags:
            with self.subTest(flag):
                self.assertEqual(run(omit=flag).returncode, 2)
        self.assertEqual(run(**{"--base-commit": "0" * 40}).returncode, 2)


# ---------------------------------------------------------------------------
# Permission (AC-1)
# ---------------------------------------------------------------------------

class TestPermission(RepoTestCase):
    def setUp(self):
        super().setUp()
        self.repo.correct_documents()

    def spec_change_phase_state(self):
        return {
            "phase": "rework", "feature": "demo",
            "spec_change": {"reason": "r", "origin_kind": "review", "origin_id": "x",
                            "recorded_at_commit": "abc", "replan_authorized": True},
        }

    def test_the_correction_entry_admits_a_failed_task(self):
        self.assertEqual(validate(self.good_patch(), self.workflow, self.repo), [])

    def test_the_correction_entry_keeps_an_in_progress_task_rejected(self):
        workflow = make_workflow(self.repo.base, statuses={"task0001": "failed", "task0002": "in_progress"})
        errors = validate(self.good_patch(), workflow, self.repo)
        self.assertIn("replace-all-not-permitted", codes(errors))

    def test_the_correction_entry_requires_empty_step_patches(self):
        patch = make_patch([correction()], step_patches=[{"step_id": "implement", "set": {"status": "pending"}}])
        errors = validate(patch, self.workflow, self.repo)
        self.assertIn("path-correction-step-patches", codes(errors))

    def test_the_same_patch_without_corrections_is_rejected_as_before(self):
        errors = validate(make_patch(None), self.workflow, self.repo)
        self.assertEqual(codes(errors).count("replace-all-not-permitted"), 1)
        self.assertNotIn("path-correction-not-permitted", codes(errors))

    def test_other_states_do_not_admit_the_field(self):
        for create_plan, implement in (("completed", "in_progress"), ("completed", "completed"),
                                       ("in_progress", "failed")):
            with self.subTest(create_plan=create_plan, implement=implement):
                workflow = make_workflow(self.repo.base, create_plan=create_plan, implement=implement)
                errors = validate(self.good_patch(), workflow, self.repo)
                self.assertIn("path-correction-not-permitted", codes(errors))

    def test_the_initial_planning_path_rejects_the_field(self):
        workflow = make_workflow(self.repo.base, create_plan="pending", implement="pending",
                                 statuses={"task0001": "pending", "task0002": "pending"})
        errors = validate(self.good_patch(), workflow, self.repo)
        self.assertIn("path-correction-not-permitted", codes(errors))

    def test_the_replanning_path_admits_the_field(self):
        workflow = make_workflow(self.repo.base, create_plan="needs_update", implement="pending",
                                 statuses={"task0001": "pending", "task0002": "merged"})
        self.assertEqual(validate(self.good_patch(), workflow, self.repo), [])

    def test_route_back_replanning_admits_the_field(self):
        workflow = make_workflow(self.repo.base, create_plan="pending", implement="pending",
                                 statuses={"task0001": "pending", "task0002": "merged"})
        errors = validate(self.good_patch(), workflow, self.repo, phase_state=self.spec_change_phase_state())
        self.assertEqual(errors, [])

    def test_the_replanning_path_keeps_its_own_rules(self):
        workflow = make_workflow(self.repo.base, create_plan="needs_update", implement="pending")
        errors = validate(self.good_patch(), workflow, self.repo)
        self.assertIn("replace-all-not-permitted", codes(errors))
        self.assertNotIn("path-correction-not-permitted", codes(errors))

    def test_the_correction_entry_keeps_the_replanning_obligations(self):
        patch = make_patch([correction()], carried=("task0001",))
        errors = validate(patch, self.workflow, self.repo)
        self.assertIn("replace-all-drops-task", codes(errors))
        patch = make_patch([correction()], preserve=())
        errors = validate(patch, self.workflow, self.repo)
        self.assertIn("preserve", codes(errors))


# ---------------------------------------------------------------------------
# Conditions 1 to 4 (AC-3)
# ---------------------------------------------------------------------------

class TestConditions(RepoTestCase):
    def setUp(self):
        super().setUp()
        self.repo.correct_documents()

    def run_case(self, workflow=None, patch=None):
        return validate(patch or self.good_patch(), workflow or self.workflow, self.repo)

    def test_a_correction_meeting_every_condition_passes(self):
        self.assertEqual(self.run_case(), [])

    def test_condition_1_an_in_progress_task(self):
        workflow = make_workflow(self.repo.base, statuses={"task0001": "failed", "task0002": "in_progress"})
        errors = self.run_case(workflow)
        self.assertEqual(codes(errors).count("path-correction-in-flight"), 1)
        flagged = [e for e in errors if e["code"] == "path-correction-in-flight"][0]
        self.assertEqual(flagged["task_ids"], ["task0002"])

    def test_condition_1_a_launched_last_event(self):
        self.repo.write_journal([("task0001", "failed"), ("task0002", "launched")])
        errors = self.run_case()
        self.assertIn("path-correction-in-flight", codes(errors))

    def test_condition_1_the_last_event_decides(self):
        self.repo.write_journal([("task0002", "launched"), ("task0002", "failed")])
        self.assertNotIn("path-correction-in-flight", codes(self.run_case()))

    def test_condition_2_the_target_status_is_merged(self):
        workflow = make_workflow(self.repo.base, statuses={"task0001": "merged", "task0002": "merged"})
        errors = self.run_case(workflow)
        self.assertIn("path-correction-merged", codes(errors))
        merged = [e for e in errors if e["code"] == "path-correction-merged"][0]
        self.assertEqual((merged["task_id"], merged["path"]), ("task0001", OLD_PATH))

    def test_condition_2_the_target_last_event_is_merged(self):
        self.repo.write_journal([("task0001", "launched"), ("task0001", "merged")])
        self.assertIn("path-correction-merged", codes(self.run_case()))

    def test_condition_2_only_the_target_counts(self):
        # task0002 is merged and carried; only task0001 is corrected.
        self.assertNotIn("path-correction-merged", codes(self.run_case()))

    def test_condition_3_old_path_not_in_files(self):
        workflow = make_workflow(self.repo.base, files={"task0001": ["src/a.py"], "task0002": ["src/c.py"]})
        errors = self.run_case(workflow)
        self.assertIn("path-correction-old-path", codes(errors))

    def test_condition_3_old_path_does_not_match_fr2(self):
        old, new = "docs/notes.md", "docs/notes-2.md"
        workflow = make_workflow(self.repo.base, files={"task0001": [old], "task0002": ["src/c.py"]})
        errors = self.run_case(workflow, make_patch([correction(old_path=old, new_path=new)]))
        self.assertIn("path-correction-old-path", codes(errors))

    def test_condition_3_old_path_exists_at_the_base_commit(self):
        for kind, files in (("a regular file", {OLD_PATH: "x\n"}), ("a directory", {OLD_PATH + "/inner.txt": "x\n"})):
            with self.subTest(kind):
                with tempfile.TemporaryDirectory() as tmp:
                    repo = DemoRepo(tmp, extra_files=files)
                    repo.correct_documents()
                    repo.write_journal([("task0001", "failed")])
                    workflow = make_workflow(repo.base)
                    errors = validate(make_patch([correction()]), workflow, repo)
                    self.assertIn("path-correction-old-path", codes(errors))

    def test_condition_4_new_path_matches_fr2(self):
        for new in ("test-docs/demo/summary.md", "test-docs/demo/Analysis-2.MD", "findings.md"):
            with self.subTest(new):
                errors = self.run_case(patch=make_patch([correction(new_path=new)]))
                self.assertIn("path-correction-new-path", codes(errors))

    def test_condition_4_new_path_is_not_safe(self):
        for new in ("../outside/audit.md", "/abs/audit.md"):
            with self.subTest(new):
                errors = self.run_case(patch=make_patch([correction(new_path=new)]))
                self.assertIn("path-correction-new-path", codes(errors))

    def test_condition_4_new_path_exists_at_the_base_commit(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = DemoRepo(tmp, extra_files={NEW_PATH: "x\n"})
            repo.correct_documents()
            repo.write_journal([("task0001", "failed")])
            errors = validate(make_patch([correction()]), make_workflow(repo.base), repo)
            self.assertIn("path-correction-new-path", codes(errors))

    def test_each_breaking_correction_reports_only_its_condition(self):
        # TS-10: the corrections that break one condition each are rejected
        # with that condition's code and no other FR5 condition code.
        cases = {
            "path-correction-in-flight": (
                make_workflow(self.repo.base, statuses={"task0001": "failed", "task0002": "in_progress"}),
                self.good_patch()),
            "path-correction-merged": (
                make_workflow(self.repo.base, statuses={"task0001": "merged", "task0002": "merged"}),
                self.good_patch()),
            "path-correction-old-path": (
                make_workflow(self.repo.base, files={"task0001": ["src/a.py"], "task0002": ["src/c.py"]}),
                self.good_patch()),
            "path-correction-new-path": (self.workflow, make_patch([correction(new_path="summary.md")])),
        }
        fr5 = {"path-correction-in-flight", "path-correction-merged", "path-correction-old-path",
               "path-correction-new-path", "path-correction-content"}
        for expected, (workflow, patch) in cases.items():
            with self.subTest(expected):
                found = fr5 & set(codes(self.run_case(workflow, patch)))
                self.assertIn(expected, found)
                self.assertEqual(found - {"path-correction-content"}, {expected})

    def test_errors_follow_the_order_of_the_conditions(self):
        workflow = make_workflow(self.repo.base, statuses={"task0001": "merged", "task0002": "in_progress"},
                                 files={"task0001": ["src/a.py"], "task0002": ["src/c.py"]})
        self.repo.write("IMPLEMENTATION.md", "changed\n")
        order = ["path-correction-in-flight", "path-correction-merged", "path-correction-old-path",
                 "path-correction-new-path", "path-correction-content"]
        found = [c for c in codes(self.run_case(workflow, make_patch([correction(new_path="summary.md")])))
                 if c in order]
        self.assertEqual(set(found), set(order))
        positions = [order.index(c) for c in found]
        self.assertEqual(positions, sorted(positions))

    def test_paths_are_literal_text(self):
        # TS-19, TM-1: a leading '-' or pathspec magic is part of the name.
        # new_path ':(top)README.md' names no entry at the base commit even
        # though README.md exists there, so it is absent; read as pathspec
        # magic it would be README.md and rejected.
        with tempfile.TemporaryDirectory() as tmp:
            repo = DemoRepo(tmp, extra_files={"README.md": "x\n", "-dash.md": "x\n"})
            self.assertEqual(VWO.base_tree_entry(repo.root, repo.base, ":(top)README.md"), "absent")
            self.assertEqual(VWO.base_tree_entry(repo.root, repo.base, "README.md"), "regular")
            self.assertEqual(VWO.base_tree_entry(repo.root, repo.base, "-dash.md"), "regular")
            self.assertEqual(VWO.base_tree_entry(repo.root, repo.base, "-absent.md"), "absent")
            self.assertEqual(VWO.base_tree_entry(repo.root, repo.base, ":(glob)*.md"), "absent")
            self.assertEqual(VWO.base_tree_entry(repo.root, repo.base, "HEAD:README.md"), "absent")
            self.assertEqual(VWO.base_tree_entry(repo.root, repo.base, "feature-docs"), "other")
            self.assertEqual(VWO.base_tree_entry(repo.root, repo.base, "README.md/inner"), "absent")
            repo.correct_documents(new_path=":(top)README.md")
            repo.write_journal([("task0001", "failed")])
            errors = validate(make_patch([correction(new_path=":(top)README.md")]), make_workflow(repo.base), repo)
            self.assertNotIn("path-correction-new-path", codes(errors))
            # An old path read literally is absent, so a magic-looking old
            # path passes condition 3's absence test only through its name.
            self.assertEqual(VWO.base_tree_entry(repo.root, repo.base, "-REPORT.md"), "absent")

    def test_base_tree_entry_classifies_symlinks_and_submodule_like_entries(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = DemoRepo(tmp, extra_files={"data/real.txt": "x\n"})
            os.symlink("real.txt", repo.root / "data" / "link.txt")
            git(repo.root, "add", "-A")
            git(repo.root, "commit", "-q", "-m", "link")
            base = git(repo.root, "rev-parse", "HEAD")
            self.assertEqual(VWO.base_tree_entry(repo.root, base, "data/link.txt"), "other")
            self.assertEqual(VWO.base_tree_entry(repo.root, base, "data/link.txt/x"), "absent")
            self.assertEqual(VWO.base_tree_entry(repo.root, base, "data"), "other")
            self.assertEqual(VWO.base_tree_entry(repo.root, base, "data/real.txt"), "regular")


# ---------------------------------------------------------------------------
# Condition 5 (AC-4)
# ---------------------------------------------------------------------------

class TestContentCondition(RepoTestCase):
    def content_errors(self, patch=None, workflow=None):
        errors = validate(patch or self.good_patch(), workflow or self.workflow, self.repo)
        return [e for e in errors if e["code"] == "path-correction-content"]

    def test_the_normalization_alone_passes(self):
        self.repo.correct_documents()
        self.assertEqual(self.content_errors(), [])

    def test_an_untouched_document_set_leaves_the_old_path(self):
        errors = self.content_errors()
        self.assertTrue(errors)
        self.assertTrue(any("old path" in e["message"] for e in errors))

    def test_a_change_beyond_the_normalization_is_rejected(self):
        self.repo.correct_documents()
        text = self.repo.read("tasks/task0001.md")
        self.repo.write("tasks/task0001.md", text.replace("lists one finding", "lists two findings"))
        errors = self.content_errors()
        self.assertEqual([e["document"] for e in errors], ["tasks/task0001.md"])

    def test_each_compared_document_is_checked(self):
        for rel in ("IMPLEMENTATION.md", "VERIFICATION.md", "tasks/task0001.md"):
            with self.subTest(rel):
                self.setUp()
                self.repo.correct_documents()
                self.repo.write(rel, self.repo.read(rel) + "\nAn added sentence.\n")
                self.assertEqual([e["document"] for e in self.content_errors()], [rel])

    def test_an_old_path_left_in_one_document_is_rejected(self):
        self.repo.correct_documents()
        self.repo.write("VERIFICATION.md", self.repo.read("VERIFICATION.md").replace(NEW_PATH, OLD_PATH))
        errors = self.content_errors()
        self.assertEqual([e["document"] for e in errors], ["VERIFICATION.md"])
        self.assertIn("old path", errors[0]["message"])

    def test_a_bare_old_file_name_is_replaced_and_passes(self):
        self.repo.correct_documents()
        self.assertIn(NEW_NAME, self.repo.read("IMPLEMENTATION.md").split("`")[2])
        self.assertEqual(self.content_errors(), [])

    def test_a_bare_old_file_name_left_in_place_is_equal_after_normalization(self):
        # Only an old PATH left behind is rejected; a bare name is normalized.
        self.repo.correct_documents()
        text = self.repo.read("IMPLEMENTATION.md").replace(NEW_NAME + " is written", OLD_NAME + " is written")
        self.repo.write("IMPLEMENTATION.md", text)
        self.assertEqual(self.content_errors(), [])

    def test_a_new_name_containing_the_old_name_is_not_replaced_again(self):
        new_path = "test-docs/demo/release-REPORT.md"
        self.repo.correct_documents(new_path=new_path, new_name="release-REPORT.md")
        patch = make_patch([correction(new_path=new_path)])
        self.assertEqual(self.content_errors(patch), [])

    def test_a_new_path_containing_the_old_path_is_not_an_old_path(self):
        new_path = "nested/" + OLD_PATH.replace("REPORT", "Report")
        self.repo.correct_documents(new_path=new_path, new_name="Report.md")
        patch = make_patch([correction(new_path=new_path)])
        self.assertEqual(self.content_errors(patch), [])

    def test_a_document_absent_at_the_base_commit_is_outside_the_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = DemoRepo(tmp, with_verification=False)
            repo.correct_documents()
            repo.write("VERIFICATION.md", "# New\n\nTS-1 is new and says nothing about the path.\n")
            repo.write_journal([("task0001", "failed")])
            errors = validate(make_patch([correction()]), make_workflow(repo.base), repo)
            self.assertEqual(errors, [])

    def test_a_document_missing_now_is_rejected(self):
        self.repo.correct_documents()
        (self.repo.feature_dir / "VERIFICATION.md").unlink()
        errors = self.content_errors()
        self.assertEqual([e["document"] for e in errors], ["VERIFICATION.md"])

    def test_only_the_target_tasks_plan_is_compared(self):
        self.repo.correct_documents()
        self.repo.write("tasks/task0002.md", self.repo.read("tasks/task0002.md") + "\nUnrelated edit.\n")
        self.assertEqual(self.content_errors(), [])

    def test_new_task_plans_under_entries_are_outside_the_set(self):
        self.repo.correct_documents()
        self.repo.write("tasks/task0003.md", TASK0002_MD.replace("task0002", "task0003").replace("src/c.py", "src/d.py"))
        entry = {
            "title": "new", "plan": "tasks/task0003.md", "files": ["src/d.py"], "skills": [],
            "domains": [], "complexity": "low", "requirements": ["FR1"], "initial_status": "pending",
        }
        patch = make_patch([correction()], entries={"task0003": entry})
        self.assertEqual(validate(patch, self.workflow, self.repo), [])

    def test_the_normalization_is_deterministic_on_a_shared_bare_name(self):
        corrections = [
            correction(old_path="a/REPORT.md", new_path="a/one.md"),
            correction(task_id="task0002", old_path="b/REPORT.md", new_path="b/two.md"),
        ]
        normalizer = VWO._correction_normalizer(corrections)
        text, left = VWO._normalize_path_strings("see a/REPORT.md, b/REPORT.md and REPORT.md", normalizer)
        self.assertEqual(text, "see a/one.md, b/two.md and REPORT.md")
        self.assertEqual(sorted(left), ["a/REPORT.md", "b/REPORT.md"])


# ---------------------------------------------------------------------------
# Application and plan agreement (AC-5)
# ---------------------------------------------------------------------------

class TestApplication(RepoTestCase):
    def test_a_corrected_record_has_the_path_replaced_in_position_and_notes_null(self):
        patch = self.good_patch()
        new = VWO.apply_patch(self.workflow, patch)
        before, after = self.workflow["tasks"]["task0001"], new["tasks"]["task0001"]
        self.assertEqual(after["files"], [NEW_PATH, "src/a.py", "src/b.py"])
        self.assertIsNone(after["notes"])
        for key in before:
            if key not in ("files", "notes"):
                self.assertEqual(after[key], before[key], key)
        self.assertEqual(set(after), set(before))

    def test_other_carried_records_stay_verbatim(self):
        new = VWO.apply_patch(self.workflow, self.good_patch())
        self.assertEqual(new["tasks"]["task0002"], self.workflow["tasks"]["task0002"])

    def test_the_input_workflow_is_not_changed(self):
        snapshot = copy.deepcopy(self.workflow)
        VWO.apply_patch(self.workflow, self.good_patch())
        self.assertEqual(self.workflow, snapshot)

    def test_a_patch_without_corrections_copies_carried_records_verbatim(self):
        new = VWO.apply_patch(self.workflow, make_patch(None))
        self.assertEqual(new["tasks"]["task0001"], self.workflow["tasks"]["task0001"])

    def test_a_malformed_field_applies_nothing(self):
        new = VWO.apply_patch(self.workflow, make_patch([correction(new_path=OLD_PATH)]))
        self.assertEqual(new["tasks"]["task0001"], self.workflow["tasks"]["task0001"])

    def test_the_position_is_kept_when_the_path_is_not_first(self):
        workflow = make_workflow(self.repo.base, files={"task0001": ["src/a.py", OLD_PATH, "src/b.py"],
                                                         "task0002": ["src/c.py"]})
        new = VWO.apply_patch(workflow, self.good_patch())
        self.assertEqual(new["tasks"]["task0001"]["files"], ["src/a.py", NEW_PATH, "src/b.py"])

    def test_a_files_section_that_disagrees_with_files_is_task_plan_files_mismatch(self):
        self.repo.correct_documents()
        patch = self.good_patch()
        self.assertEqual(VWO._validate_task_plans_against_patch(patch, self.repo.feature_dir, workflow=self.workflow), [])
        text = self.repo.read("tasks/task0001.md").replace(NEW_PATH + "` - the report", "test-docs/demo/other.md` - the report")
        self.repo.write("tasks/task0001.md", text)
        errors = VWO._validate_task_plans_against_patch(patch, self.repo.feature_dir, workflow=self.workflow)
        self.assertEqual(codes(errors), ["task-plan-files-mismatch"])
        self.assertIn("task0001", errors[0]["message"])

    def test_an_uncorrected_files_section_disagrees_after_the_correction(self):
        # The plan still lists the old path while files now holds the new one.
        errors = VWO._validate_task_plans_against_patch(self.good_patch(), self.repo.feature_dir, workflow=self.workflow)
        self.assertEqual(codes(errors), ["task-plan-files-mismatch"])

    def test_the_agreement_check_needs_the_workflow_and_a_correction(self):
        self.assertEqual(VWO._validate_task_plans_against_patch(self.good_patch(), self.repo.feature_dir), [])
        self.assertEqual(
            VWO._validate_task_plans_against_patch(make_patch(None), self.repo.feature_dir, workflow=self.workflow), [])

    def test_the_worker_result_path_reports_the_mismatch(self):
        self.repo.correct_documents()
        text = self.repo.read("tasks/task0001.md").replace("- `src/b.py` - change\n", "")
        self.repo.write("tasks/task0001.md", text)
        result = {
            "schema_version": 1, "worker": "implementation-planner", "request_id": "req-1",
            "status": "completed", "input_revision": {"input_digest": "sha256:x"}, "mode_echo": None,
            "payload": {"task_index": {}}, "workflow_patch": self.good_patch(),
            "written_artifacts": [], "question_packet": None, "blocking_reason": None,
        }
        errors = VWO.validate_worker_result(
            result, "implementation-planner", workflow=self.workflow, digest_source=DIGEST_SOURCE,
            dry_run=True, feature_dir=self.repo.feature_dir, target_repo=self.repo.root,
            base_commit=self.repo.base, journal=self.repo.journal,
        )
        self.assertIn("task-plan-files-mismatch", codes(errors))
        # Repair the plan: nothing is left.
        self.repo.write("tasks/task0001.md", text.replace("### Files to Modify\n", "### Files to Modify\n- `src/b.py` - change\n"))
        errors = VWO.validate_worker_result(
            result, "implementation-planner", workflow=self.workflow, digest_source=DIGEST_SOURCE,
            dry_run=True, feature_dir=self.repo.feature_dir, target_repo=self.repo.root,
            base_commit=self.repo.base, journal=self.repo.journal,
        )
        self.assertEqual(errors, [])


# ---------------------------------------------------------------------------
# FR3 on carried tasks (AC-2)
# ---------------------------------------------------------------------------

class TestCarriedCheck(RepoTestCase):
    def carried_workflow(self, files, statuses=None):
        return make_workflow(
            self.repo.base, create_plan="needs_update", implement="pending",
            statuses=statuses or {"task0001": "pending", "task0002": "merged"}, files=files,
        )

    def test_a_carried_non_merged_task_with_a_new_matching_name_is_rejected(self):
        workflow = self.carried_workflow({"task0001": [OLD_PATH], "task0002": ["src/c.py"]})
        errors = validate(make_patch(None), workflow, self.repo)
        found = [e for e in errors if e["code"] == "report-name-new-file"]
        self.assertEqual([(e["task_id"], e["path"]) for e in found], [("task0001", OLD_PATH)])

    def test_a_carried_merged_task_is_not_judged(self):
        workflow = self.carried_workflow({"task0001": ["src/a.py"], "task0002": ["test-docs/demo/SUMMARY.md"]})
        errors = validate(make_patch(None), workflow, self.repo)
        self.assertNotIn("report-name-new-file", codes(errors))

    def test_only_the_non_merged_task_is_rejected_when_both_hold_a_name(self):
        workflow = self.carried_workflow({"task0001": [OLD_PATH], "task0002": ["test-docs/demo/SUMMARY.md"]})
        errors = validate(make_patch(None), workflow, self.repo)
        found = [(e["task_id"], e["path"]) for e in errors if e["code"] == "report-name-new-file"]
        self.assertEqual(found, [("task0001", OLD_PATH)])

    def test_a_corrected_path_is_judged_after_the_correction(self):
        workflow = self.carried_workflow({"task0001": [OLD_PATH], "task0002": ["src/c.py"]})
        self.repo.correct_documents()
        errors = validate(make_patch([correction()]), workflow, self.repo)
        self.assertNotIn("report-name-new-file", codes(errors))
        # A correction to a name that still matches leaves the violation.
        errors = validate(make_patch([correction(new_path="test-docs/demo/summary.md")]), workflow, self.repo)
        self.assertIn("report-name-new-file", codes(errors))

    def test_a_matching_name_that_is_a_regular_file_at_the_base_commit_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = DemoRepo(tmp, extra_files={OLD_PATH: "existing\n"})
            workflow = make_workflow(repo.base, create_plan="needs_update", implement="pending",
                                     statuses={"task0001": "pending", "task0002": "merged"})
            errors = validate(make_patch(None), workflow, repo)
            self.assertNotIn("report-name-new-file", codes(errors))

    def test_a_matching_name_that_is_a_directory_at_the_base_commit_is_new(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = DemoRepo(tmp, extra_files={OLD_PATH + "/inner.txt": "x\n"})
            workflow = make_workflow(repo.base, create_plan="needs_update", implement="pending",
                                     statuses={"task0001": "pending", "task0002": "merged"})
            errors = validate(make_patch(None), workflow, repo)
            self.assertIn("report-name-new-file", codes(errors))

    def test_missing_base_inputs_with_a_matching_name_exit_2(self):
        workflow = self.carried_workflow({"task0001": [OLD_PATH], "task0002": ["src/c.py"]})
        for kwargs in ({"target_repo": None}, {"base_commit": None}, {"base_commit": "0" * 40}):
            with self.subTest(kwargs):
                call = dict(workflow=workflow, digest_source=DIGEST_SOURCE, dry_run=True,
                            feature_dir=self.repo.feature_dir, target_repo=self.repo.root,
                            base_commit=self.repo.base, journal=self.repo.journal)
                call.update(kwargs)
                with self.assertRaises(VWO.ExecutionError):
                    VWO.validate_workflow_patch(make_patch(None), **call)

    def test_no_matching_name_needs_no_base_inputs(self):
        workflow = self.carried_workflow({"task0001": ["src/a.py"], "task0002": ["src/c.py"]})
        errors = VWO.validate_workflow_patch(
            make_patch(None), workflow=workflow, digest_source=DIGEST_SOURCE, dry_run=True,
            feature_dir=self.repo.feature_dir)
        self.assertEqual(errors, [])

    def test_without_a_dry_run_the_carried_files_are_not_read(self):
        workflow = self.carried_workflow({"task0001": [OLD_PATH], "task0002": ["src/c.py"]})
        self.assertEqual(validate(make_patch(None), workflow, self.repo, dry_run=False), [])


# ---------------------------------------------------------------------------
# Scenario-ID scan (AC-7, D8)
# ---------------------------------------------------------------------------

class TestScenarioIdScan(RepoTestCase):
    def setUp(self):
        super().setUp()
        self.repo.write("VERIFICATION.md", self.repo.read("VERIFICATION.md") + "\nSee TS3 for the old form.\n")

    def new_entry_patch(self, corrections):
        entry = {
            "title": "new", "plan": "tasks/task0003.md", "files": ["src/d.py"], "skills": [],
            "domains": [], "complexity": "low", "requirements": ["FR1"], "initial_status": "pending",
        }
        return make_patch(corrections, entries={"task0003": entry})

    def test_a_correction_patch_skips_the_verification_target_only(self):
        patch = self.new_entry_patch([correction()])
        self.repo.write("tasks/task0003.md", "# Task\n\nUses TS7 which is hyphen-less.\n")
        errors = VWO._validate_scenario_id_form(patch, self.repo.feature_dir)
        self.assertEqual(len(errors), 1)
        self.assertIn("task0003", errors[0]["message"])
        self.assertIn("TS7", errors[0]["message"])
        self.assertNotIn("VERIFICATION.md contains", errors[0]["message"])

    def test_a_patch_without_corrections_still_scans_verification(self):
        errors = VWO._validate_scenario_id_form(make_patch(None), self.repo.feature_dir)
        self.assertEqual([e["code"] for e in errors], ["scenario-id-form"])
        self.assertIn("VERIFICATION.md", errors[0]["message"])
        self.assertIn("TS3", errors[0]["message"])

    def test_an_empty_or_malformed_field_does_not_skip_the_scan(self):
        for field in ([], "oops", None):
            with self.subTest(field=field):
                patch = make_patch(None)
                patch["tasks_patch"]["path_corrections"] = field
                errors = VWO._validate_scenario_id_form(patch, self.repo.feature_dir)
                self.assertEqual([e["code"] for e in errors], ["scenario-id-form"])


# ---------------------------------------------------------------------------
# Fixtures (AC-7)
# ---------------------------------------------------------------------------

class TestFixtures(unittest.TestCase):
    def run_fixture(self, name):
        input_path = PATCH_FIXTURES / name / "input.json"
        args = [sys.executable, str(SCRIPT_PATH), "--kind", "workflow-patch",
                "--worker", "implementation-planner", "--input", str(input_path)]
        return subprocess.run(args, capture_output=True, text=True)

    def test_the_well_formed_field_passes_without_a_dry_run(self):
        result = self.run_fixture("valid-path-correction-shape")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads((PATCH_FIXTURES / "valid-path-correction-shape" / "input.json").read_text(encoding="utf-8"))
        self.assertTrue(data["tasks_patch"]["path_corrections"])
        self.assertFalse((PATCH_FIXTURES / "valid-path-correction-shape" / "DRY_RUN_APPLY").exists())

    def test_the_malformed_field_is_path_correction_shape_without_a_dry_run(self):
        result = self.run_fixture("invalid-path-correction-shape")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("path-correction-shape", [e["code"] for e in json.loads(result.stdout)["errors"]])
        self.assertFalse((PATCH_FIXTURES / "invalid-path-correction-shape" / "DRY_RUN_APPLY").exists())

    def test_neither_fixture_holds_a_report_artifact_name(self):
        for name in ("valid-path-correction-shape", "invalid-path-correction-shape"):
            for path in (PATCH_FIXTURES / name).rglob("*"):
                self.assertFalse(VWO.is_report_artifact_name(path.name), path)


if __name__ == "__main__":
    unittest.main()
