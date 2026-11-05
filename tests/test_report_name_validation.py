"""subagent-report-write-block/task0001: report artifact names -- the FR2
judgment, the FR3 rejection of a new matching name in a workflow patch, and the
FR4 base inputs.

Acceptance criteria covered (task plan task0001):

- AC-1: `REPORT_ARTIFACT_NAME_RE` / `is_report_artifact_name`, and the regex
  written in plan-writing's `## Report Artifact Names` against the constant
  (TS-15).
- AC-2: `## Report Artifact Names` states each FR1 rule (TS-17, TM-9).
- AC-3: a replace_planning or append_rework patch with a new matching name
  exits 1 with `report-name-new-file`, the task id and the path (TS-1, TS-2,
  TS-3, TS-8).
- AC-4: a matching name that is a regular file at the base commit passes; a
  directory or a symlink is rejected as new (TS-4, TS-5).
- AC-5: missing or unusable base inputs exit 2 when a matching name is present
  and are never read otherwise (TS-6, TS-7, TM-2, TM-3).
- AC-6: paths are judged as literal text (TS-19, TM-1).
- AC-7: the three fixtures under references/fixtures/workflow-patch/ and the
  plan of the reproduction steps (FR9, NFR2, NFR4).

Every repository these tests need is built in a temporary directory with the
identity set per command, and no file in this repository carries a matching
name: such files exist only inside the disposable repositories, created at run
time.
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
PLAN_WRITING_PATH = REPO_ROOT / "em-workflow" / "skills" / "plan-writing" / "SKILL.md"
FIXTURES_ROOT = REPO_ROOT / "em-workflow" / "references" / "fixtures"
REPLACE_PLANNING_FIXTURES = FIXTURES_ROOT / "workflow-patch" / "replace_planning"
APPEND_REWORK_FIXTURES = FIXTURES_ROOT / "workflow-patch" / "append_rework"
WORKER_RESULT_FIXTURE = (
    FIXTURES_ROOT / "worker-result" / "implementation-planner" / "valid-completed"
)

SECTION_HEADING = "## Report Artifact Names"
ERROR_CODE = "report-name-new-file"


def _load_module():
    spec = importlib.util.spec_from_file_location("validate_worker_output", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VWO = _load_module()


# ---------------------------------------------------------------------------
# Disposable repositories
# ---------------------------------------------------------------------------

def _git_env():
    """The environment of every git process these tests start: nothing from
    the caller's repository selection (GIT_DIR and friends) and no user or
    system configuration."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    return env


def _git(repo, *args, check=True):
    # The identity is set on every command; nothing is read from a
    # configuration file.
    cmd = [
        "git",
        "-c", "user.name=Report Name Test",
        "-c", "user.email=report-name-test@example.invalid",
        "-c", "commit.gpgsign=false",
        "-C", str(repo),
        *args,
    ]
    return subprocess.run(cmd, check=check, capture_output=True, text=True, env=_git_env())


def build_repo(repo, files=None, symlinks=None, object_format=None):
    """Creates a repository at `repo` with one commit holding `files` (path ->
    text) and `symlinks` (path -> link target). Returns the commit ID."""
    repo.mkdir(parents=True, exist_ok=True)
    init = ["init", "-q"]
    if object_format:
        init.append(f"--object-format={object_format}")
    _git(repo, *init)
    for rel, content in (files or {}).items():
        target = repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    for rel, link_target in (symlinks or {}).items():
        link = repo / rel
        link.parent.mkdir(parents=True, exist_ok=True)
        os.symlink(link_target, link)
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "--allow-empty", "-m", "base")
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


def commit_more(repo, files):
    for rel, content in files.items():
        target = repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "more")
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


# ---------------------------------------------------------------------------
# Patch and CLI helpers
# ---------------------------------------------------------------------------

def _load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def patch_for(operation, files_by_task, plan_by_task=None):
    """A workflow patch that is valid in every respect but the `files` of its
    entries, built from the committed valid fixture of the operation."""
    if operation == "replace_planning":
        patch = _load_json(REPLACE_PLANNING_FIXTURES / "valid-replace-all" / "input.json")
    else:
        patch = _load_json(APPEND_REWORK_FIXTURES / "valid-append" / "input.json")
    entries = patch["tasks_patch"]["entries"]
    prototype = next(iter(entries.values()))
    new_entries = {}
    for task_id, files in files_by_task.items():
        entry = copy.deepcopy(prototype)
        entry["files"] = list(files)
        entry["plan"] = (plan_by_task or {}).get(task_id, f"tasks/{task_id}.md")
        new_entries[task_id] = entry
    patch["tasks_patch"]["entries"] = new_entries
    if operation == "append_rework":
        patch["tasks_patch"]["expected_next_task_id"] = next(iter(new_entries))
    return patch


def run_cli(args):
    cmd = [sys.executable, str(SCRIPT_PATH)] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True)


class CliCase(unittest.TestCase):
    """Base class: a scratch directory per test and a way to validate a patch
    through the real command line."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.repo = self.tmp / "base-repo"

    def write_json(self, name, data):
        path = self.tmp / name
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def validate_patch(
        self,
        patch,
        *,
        target_repo=None,
        base_commit=None,
        extra_args=(),
        kind="workflow-patch",
    ):
        args = ["--kind", kind]
        if kind == "worker-result":
            args += [
                "--worker", "implementation-planner",
                "--input-envelope", str(WORKER_RESULT_FIXTURE / "envelope.json"),
            ]
        else:
            args += ["--worker", "implementation-planner"]
        args += ["--input", str(self.write_json("input.json", patch))]
        # The `=` form keeps a value that starts with a dash a value for the
        # argument parser instead of an option of its own.
        if target_repo is not None:
            args.append(f"--target-repo={target_repo}")
        if base_commit is not None:
            args.append(f"--base-commit={base_commit}")
        args += list(extra_args)
        return run_cli(args)

    def validate_files(self, operation, files_by_task, **kwargs):
        plan_by_task = kwargs.pop("plan_by_task", None)
        return self.validate_patch(patch_for(operation, files_by_task, plan_by_task), **kwargs)

    def assert_exit(self, result, expected):
        self.assertEqual(
            result.returncode,
            expected,
            f"expected exit {expected}, got {result.returncode}\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}",
        )

    def assert_execution_error(self, result):
        # Exit 2 from the validator's own execution-error path, not from the
        # argument parser (which also exits 2 on an unknown option).
        self.assert_exit(result, 2)
        self.assertIn("execution error", result.stderr)
        self.assertNotIn("unrecognized arguments", result.stderr)
        self.assertEqual(result.stdout, "", "an execution error carries no validation detail")

    @staticmethod
    def errors_of(result):
        return json.loads(result.stdout)["errors"]

    def report_name_errors(self, result):
        return [e for e in self.errors_of(result) if e.get("code") == ERROR_CODE]

    def assert_rejected_as_new(self, result, expected_pairs):
        """Exit 1 and exactly the expected (task_id, path) violations."""
        self.assert_exit(result, 1)
        found = [(e["task_id"], e["path"]) for e in self.report_name_errors(result)]
        self.assertEqual(found, list(expected_pairs))
        self.assertEqual(
            len(self.errors_of(result)),
            len(found),
            "the only errors of the patch are the report-name ones",
        )


OPERATIONS = ("replace_planning", "append_rework")


# ---------------------------------------------------------------------------
# AC-1: the constant and the judgment
# ---------------------------------------------------------------------------

class TestReportArtifactNameConstant(unittest.TestCase):
    def test_ac1_constant_pattern_is_the_fr2_regex(self):
        self.assertEqual(
            VWO.REPORT_ARTIFACT_NAME_RE.pattern,
            r"^(REPORT|SUMMARY|FINDINGS|ANALYSIS).*\.md$",
        )

    def test_ac1_constant_is_compiled_case_insensitively(self):
        self.assertTrue(VWO.REPORT_ARTIFACT_NAME_RE.flags & re.IGNORECASE)

    def test_ac1_plan_writing_regex_equals_the_constant_ts15(self):
        text = PLAN_WRITING_PATH.read_text(encoding="utf-8")
        section = _section_text(text, SECTION_HEADING)
        literals = re.findall(r"`/(.+?)/([a-z]*)`", section)
        self.assertEqual(
            len(literals),
            1,
            f"{SECTION_HEADING} must hold exactly one regex literal, found {literals!r}",
        )
        pattern, flags = literals[0]
        self.assertEqual(pattern, VWO.REPORT_ARTIFACT_NAME_RE.pattern)
        self.assertEqual(
            "i" in flags,
            bool(VWO.REPORT_ARTIFACT_NAME_RE.flags & re.IGNORECASE),
            "the case-insensitive flag of the document and the constant disagree",
        )
        self.assertEqual(
            set(flags) - {"i"},
            set(),
            "the document's literal carries no flag other than i",
        )


class TestIsReportArtifactName(unittest.TestCase):
    MATCHING = (
        "REPORT.md",
        "report.md",
        "Report.Md",
        "Analysis-notes.md",
        "SUMMARY_x.MD",
        "findings.md",
        "FINDINGS.md",
        "REPORTS-2026.md",
        "ANALYSISx.md",
        "test-docs/x/REPORT.md",
        "a/b/c/summary.md",
        "dir\\REPORT.md",
        "dir/REPORT.md/",
        "./REPORT.md",
    )
    NOT_MATCHING = (
        "report.txt",
        "reports/foo.md",
        "audit-report.md",
        "README.md",
        "xREPORT.md",
        "REPORT",
        "REPORT.mdx",
        "REPORT.md.bak",
        "SUMMARY",
        "notes/FINDINGS.txt",
        # Directory names are never judged.
        "REPORT.md/inner.txt",
        "findings.md/sub/other.py",
        "test-docs/ANALYSIS.md/data.json",
        # A name that only holds a matching name after a prefix is another name.
        ":(top)REPORT.md",
        "-REPORT.md",
        "HEAD:REPORT.md",
        "",
        "/",
        ".",
        "./",
        # A trailing line break is not part of a name the Write check sees.
        "report.md\n",
    )

    def test_ac1_matching_names(self):
        for path in self.MATCHING:
            with self.subTest(path=path):
                self.assertIs(VWO.is_report_artifact_name(path), True)

    def test_ac1_non_matching_names(self):
        for path in self.NOT_MATCHING:
            with self.subTest(path=path):
                self.assertIs(VWO.is_report_artifact_name(path), False)

    def test_ac1_any_other_input_is_false(self):
        for value in (None, 5, 1.5, True, b"REPORT.md", ["REPORT.md"], {"path": "REPORT.md"}):
            with self.subTest(value=value):
                self.assertIs(VWO.is_report_artifact_name(value), False)


# ---------------------------------------------------------------------------
# AC-2: the rule text
# ---------------------------------------------------------------------------

def _section_text(text, heading):
    lines = text.splitlines()
    start = None
    for i, line in enumerate(lines):
        if line.strip() == heading:
            start = i + 1
            break
    if start is None:
        return ""
    body = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        body.append(line)
    return "\n".join(body)


class TestReportArtifactNamesSection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = PLAN_WRITING_PATH.read_text(encoding="utf-8")
        cls.section = _section_text(cls.text, SECTION_HEADING)
        cls.flat = " ".join(cls.section.split())

    def test_ac2_the_section_exists_exactly_once(self):
        self.assertEqual(
            [l for l in self.text.splitlines() if l.strip() == SECTION_HEADING],
            [SECTION_HEADING],
        )
        self.assertTrue(self.section.strip(), f"{SECTION_HEADING} is empty")

    def test_ac2_fr2_only_the_final_segment_is_judged_and_case_is_ignored(self):
        self.assertIn("final path segment", self.flat)
        self.assertRegex(self.flat, r"[Cc]ase is ignored")
        self.assertRegex(self.flat, r"[Dd]irectory names are not judged")

    def test_ac2_fr1_a_new_matching_name_is_no_artifact_of_any_plan_part(self):
        self.assertIn("does not exist at the base commit", self.flat)
        for part in ("files", "task body", "acceptance criterion", "VERIFICATION.md"):
            with self.subTest(part=part):
                self.assertIn(part, self.flat)

    def test_ac2_fr1_a_report_artifact_takes_a_name_that_does_not_match(self):
        self.assertIn("A report artifact takes a name that does not match", self.flat)

    def test_ac2_tm9_no_step_writes_under_another_name_and_renames(self):
        self.assertIn("A plan holds no step that writes under another name and then renames", self.flat)

    def test_ac2_fr1_updating_an_existing_file_is_stated_as_made_with_edit(self):
        self.assertRegex(
            self.flat,
            r"exists at the base commit states in its body that the update is made with Edit",
        )

    def test_ac2_the_checklist_cites_the_section(self):
        checklist = _section_text(self.text, "## Pre-Save Self-Verification Checklist (MANDATORY)")
        self.assertIn(SECTION_HEADING, checklist)


# ---------------------------------------------------------------------------
# AC-3: new matching names are rejected
# ---------------------------------------------------------------------------

class TestNewMatchingNameIsRejected(CliCase):
    def setUp(self):
        super().setUp()
        self.base = build_repo(self.repo, files={"src/api/register.go": "package api\n"})

    def test_ac3_each_matching_name_is_rejected_for_both_operations(self):
        names = (
            "test-docs/x/REPORT.md",
            "report.md",
            "Analysis-notes.md",
            "SUMMARY_x.MD",
            "findings.md",
        )
        for operation in OPERATIONS:
            for name in names:
                with self.subTest(operation=operation, name=name):
                    result = self.validate_files(
                        operation,
                        {"task0001": [name, "src/api/register.go"]},
                        target_repo=self.repo,
                        base_commit=self.base,
                    )
                    self.assert_rejected_as_new(result, [("task0001", name)])

    def test_ac3_non_matching_names_pass_for_both_operations(self):
        names = ("report.txt", "reports/foo.md", "audit-report.md", "README.md")
        for operation in OPERATIONS:
            for name in names:
                with self.subTest(operation=operation, name=name):
                    result = self.validate_files(
                        operation,
                        {"task0001": [name]},
                        target_repo=self.repo,
                        base_commit=self.base,
                    )
                    self.assert_exit(result, 0)

    def test_ac3_the_error_names_the_task_and_the_path(self):
        result = self.validate_files(
            "replace_planning",
            {"task0001": ["test-docs/x/REPORT.md"]},
            target_repo=self.repo,
            base_commit=self.base,
        )
        self.assert_exit(result, 1)
        (error,) = self.report_name_errors(result)
        self.assertEqual(error["code"], ERROR_CODE)
        self.assertEqual(error["task_id"], "task0001")
        self.assertEqual(error["path"], "test-docs/x/REPORT.md")
        self.assertIn("task0001", error["message"])
        self.assertIn("test-docs/x/REPORT.md", error["message"])

    def test_ac3_each_violation_is_one_error_in_task_then_file_order(self):
        result = self.validate_files(
            "replace_planning",
            {
                "task0001": ["src/api/register.go", "docs/findings.md", "REPORT.md"],
                "task0002": ["README.md"],
                "task0003": ["out/Summary.md"],
            },
            target_repo=self.repo,
            base_commit=self.base,
        )
        self.assert_rejected_as_new(
            result,
            [
                ("task0001", "docs/findings.md"),
                ("task0001", "REPORT.md"),
                ("task0003", "out/Summary.md"),
            ],
        )

    def test_ac3_a_task_whose_plan_is_task_md_is_judged_like_any_other(self):
        for operation in OPERATIONS:
            with self.subTest(operation=operation):
                result = self.validate_files(
                    operation,
                    {"task0001": ["test-docs/x/REPORT.md"]},
                    plan_by_task={"task0001": "tasks/task0001/TASK.md"},
                    target_repo=self.repo,
                    base_commit=self.base,
                )
                self.assert_rejected_as_new(result, [("task0001", "test-docs/x/REPORT.md")])

    def test_ac3_the_worker_result_kind_rejects_the_same_patch(self):
        result_doc = _load_json(WORKER_RESULT_FIXTURE / "input.json")
        patch = result_doc["workflow_patch"]
        patch["tasks_patch"]["entries"]["task0001"]["files"] = ["test-docs/x/REPORT.md"]
        result = self.validate_patch(
            result_doc,
            kind="worker-result",
            target_repo=self.repo,
            base_commit=self.base,
        )
        self.assert_exit(result, 1)
        (error,) = self.report_name_errors(result)
        self.assertEqual((error["task_id"], error["path"]), ("task0001", "test-docs/x/REPORT.md"))
        self.assertTrue(error["message"].startswith("workflow_patch: "))

    def test_ac3_the_worker_result_kind_passes_when_no_name_matches(self):
        result = self.validate_patch(
            _load_json(WORKER_RESULT_FIXTURE / "input.json"),
            kind="worker-result",
            target_repo=self.repo,
            base_commit=self.base,
        )
        self.assert_exit(result, 0)

    def test_ac3_dry_run_apply_rejects_the_same_patch(self):
        case_dir = REPLACE_PLANNING_FIXTURES / "valid-dry-run-apply"
        patch = _load_json(case_dir / "input.json")
        patch["tasks_patch"]["entries"]["task0001"]["files"] = ["test-docs/x/REPORT.md"]
        dry_run_args = [
            "--dry-run-apply",
            "--workflow", str(case_dir / "workflow.json"),
            "--digest-source", str(case_dir / "digest-source.json"),
        ]
        result = self.validate_patch(
            patch,
            target_repo=self.repo,
            base_commit=self.base,
            extra_args=dry_run_args,
        )
        self.assert_exit(result, 1)
        found = [(e["task_id"], e["path"]) for e in self.report_name_errors(result)]
        self.assertEqual(found, [("task0001", "test-docs/x/REPORT.md")])

    def test_ac3_dry_run_apply_without_a_matching_name_still_passes(self):
        case_dir = REPLACE_PLANNING_FIXTURES / "valid-dry-run-apply"
        result = self.validate_patch(
            _load_json(case_dir / "input.json"),
            target_repo=self.repo,
            base_commit=self.base,
            extra_args=[
                "--dry-run-apply",
                "--workflow", str(case_dir / "workflow.json"),
                "--digest-source", str(case_dir / "digest-source.json"),
            ],
        )
        self.assert_exit(result, 0)


# ---------------------------------------------------------------------------
# AC-4: what exists at the base commit
# ---------------------------------------------------------------------------

class TestBaseCommitTreeEntry(CliCase):
    def test_ac4_a_regular_file_at_the_base_commit_passes_as_an_update(self):
        base = build_repo(
            self.repo,
            files={"test-docs/x/REPORT.md": "# existing\n", "REPORT.md": "# top\n"},
        )
        for operation in OPERATIONS:
            for name in ("test-docs/x/REPORT.md", "REPORT.md"):
                with self.subTest(operation=operation, name=name):
                    result = self.validate_files(
                        operation,
                        {"task0001": [name]},
                        target_repo=self.repo,
                        base_commit=base,
                    )
                    self.assert_exit(result, 0)

    def test_ac4_an_executable_regular_file_passes_too(self):
        (self.repo).mkdir(parents=True)
        script = self.repo / "SUMMARY.md"
        script.write_text("x\n", encoding="utf-8")
        script.chmod(0o755)
        _git(self.repo, "init", "-q")
        _git(self.repo, "add", "-A")
        _git(self.repo, "commit", "-q", "-m", "base")
        base = _git(self.repo, "rev-parse", "HEAD").stdout.strip()
        result = self.validate_files(
            "replace_planning", {"task0001": ["SUMMARY.md"]}, target_repo=self.repo, base_commit=base
        )
        self.assert_exit(result, 0)

    def test_ac4_ts5_a_directory_at_the_base_commit_is_rejected_as_new(self):
        base = build_repo(self.repo, files={"docs/REPORT.md/inner.txt": "x\n"})
        for operation in OPERATIONS:
            with self.subTest(operation=operation):
                result = self.validate_files(
                    operation,
                    {"task0001": ["docs/REPORT.md"]},
                    target_repo=self.repo,
                    base_commit=base,
                )
                self.assert_rejected_as_new(result, [("task0001", "docs/REPORT.md")])

    def test_ac4_a_symlink_at_the_base_commit_is_rejected_as_new(self):
        base = build_repo(
            self.repo,
            files={"docs/real.txt": "x\n"},
            symlinks={"docs/REPORT.md": "real.txt", "findings.md": "docs"},
        )
        for operation in OPERATIONS:
            for name in ("docs/REPORT.md", "findings.md"):
                with self.subTest(operation=operation, name=name):
                    result = self.validate_files(
                        operation,
                        {"task0001": [name]},
                        target_repo=self.repo,
                        base_commit=base,
                    )
                    self.assert_rejected_as_new(result, [("task0001", name)])

    def test_ac4_a_file_below_a_symlinked_directory_is_rejected_as_new(self):
        base = build_repo(
            self.repo,
            files={"real/REPORT.md": "x\n"},
            symlinks={"linked": "real"},
        )
        result = self.validate_files(
            "replace_planning",
            {"task0001": ["linked/REPORT.md"]},
            target_repo=self.repo,
            base_commit=base,
        )
        self.assert_rejected_as_new(result, [("task0001", "linked/REPORT.md")])

    def test_ac4_a_name_that_differs_only_in_case_is_a_different_name(self):
        base = build_repo(self.repo, files={"report.md": "x\n"})
        result = self.validate_files(
            "replace_planning", {"task0001": ["REPORT.md"]}, target_repo=self.repo, base_commit=base
        )
        self.assert_rejected_as_new(result, [("task0001", "REPORT.md")])

    def test_ac4_only_the_base_commit_counts_not_the_working_tree(self):
        base = build_repo(self.repo, files={"src/a.txt": "x\n"})
        (self.repo / "REPORT.md").write_text("untracked\n", encoding="utf-8")
        result = self.validate_files(
            "replace_planning", {"task0001": ["REPORT.md"]}, target_repo=self.repo, base_commit=base
        )
        self.assert_rejected_as_new(result, [("task0001", "REPORT.md")])

    def test_ac4_a_file_added_after_the_base_commit_is_new(self):
        base = build_repo(self.repo, files={"src/a.txt": "x\n"})
        commit_more(self.repo, {"REPORT.md": "later\n"})
        result = self.validate_files(
            "replace_planning", {"task0001": ["REPORT.md"]}, target_repo=self.repo, base_commit=base
        )
        self.assert_rejected_as_new(result, [("task0001", "REPORT.md")])

    def test_ac4_a_file_removed_after_the_base_commit_is_an_update(self):
        base = build_repo(self.repo, files={"REPORT.md": "x\n"})
        _git(self.repo, "rm", "-q", "REPORT.md")
        _git(self.repo, "commit", "-q", "-m", "remove")
        result = self.validate_files(
            "replace_planning", {"task0001": ["REPORT.md"]}, target_repo=self.repo, base_commit=base
        )
        self.assert_exit(result, 0)

    def test_ac4_a_sha256_repository_with_a_full_64_digit_commit_id(self):
        probe = self.tmp / "probe"
        probe.mkdir()
        if _git(probe, "init", "-q", "--object-format=sha256", check=False).returncode != 0:
            self.skipTest("this git cannot create a sha256 repository")
        base = build_repo(self.repo, files={"REPORT.md": "x\n"}, object_format="sha256")
        self.assertEqual(len(base), 64)
        result = self.validate_files(
            "replace_planning", {"task0001": ["REPORT.md"]}, target_repo=self.repo, base_commit=base
        )
        self.assert_exit(result, 0)
        result = self.validate_files(
            "replace_planning", {"task0001": ["findings.md"]}, target_repo=self.repo, base_commit=base
        )
        self.assert_rejected_as_new(result, [("task0001", "findings.md")])


# ---------------------------------------------------------------------------
# AC-5: the base inputs
# ---------------------------------------------------------------------------

class TestBaseInputs(CliCase):
    def setUp(self):
        super().setUp()
        self.base = build_repo(self.repo, files={"REPORT.md": "existing\n", "src/a.go": "x\n"})
        self.matching = {"task0001": ["REPORT.md"]}

    def validate_matching(self, **kwargs):
        return self.validate_files("replace_planning", self.matching, **kwargs)

    def test_ac5_ts6_a_matching_name_without_either_value_exits_2(self):
        for operation in OPERATIONS:
            with self.subTest(operation=operation, given="neither"):
                self.assert_execution_error(
                    self.validate_files(operation, self.matching)
                )
            with self.subTest(operation=operation, given="only the repository"):
                self.assert_execution_error(
                    self.validate_files(operation, self.matching, target_repo=self.repo)
                )
            with self.subTest(operation=operation, given="only the commit"):
                self.assert_execution_error(
                    self.validate_files(operation, self.matching, base_commit=self.base)
                )

    def test_ac5_empty_values_count_as_missing(self):
        for flag_args in (
            ["--target-repo", "", "--base-commit", self.base],
            ["--target-repo", str(self.repo), "--base-commit", ""],
        ):
            with self.subTest(args=flag_args):
                result = self.validate_files(
                    "replace_planning", self.matching, extra_args=flag_args
                )
                self.assert_execution_error(result)

    def test_ac5_tm2_a_base_that_is_not_a_full_hex_id_exits_2(self):
        resolvable_forms = {
            "branch name": "main",
            "HEAD": "HEAD",
            "HEAD~0": "HEAD~0",
            "HEAD^{commit}": "HEAD^{commit}",
            "abbreviated id": self.base[:12],
            "39 digits": self.base[:39],
            "41 digits": self.base + "0",
            "63 digits": self.base[:39] + "0" * 24,
            "upper case": self.base.upper(),
            "id and a line break": self.base + "\n",
            "id and a suffix": self.base + "~0",
            "id and a path": f"{self.base}:REPORT.md",
            "an option": "--help",
            "an option with an id": f"--{self.base}",
            "whitespace around": f" {self.base} ",
        }
        for label, value in resolvable_forms.items():
            with self.subTest(base=label):
                result = self.validate_matching(target_repo=self.repo, base_commit=value)
                self.assert_execution_error(result)

    def test_ac5_a_base_that_does_not_resolve_exits_2(self):
        tree_id = _git(self.repo, "rev-parse", "HEAD^{tree}").stdout.strip()
        blob_id = _git(self.repo, "rev-parse", "HEAD:REPORT.md").stdout.strip()
        unresolvable = {
            "40 zeros": "0" * 40,
            "40 digits of an unknown object": "1234567890abcdef" * 2 + "12345678",
            "64 zeros": "0" * 64,
            "a tree": tree_id,
            "a blob": blob_id,
        }
        for label, value in unresolvable.items():
            with self.subTest(base=label):
                result = self.validate_matching(target_repo=self.repo, base_commit=value)
                self.assert_execution_error(result)

    def test_ac5_a_repository_that_is_unusable_exits_2(self):
        not_a_repo = self.tmp / "plain-directory"
        not_a_repo.mkdir()
        a_file = self.tmp / "a-file"
        a_file.write_text("x", encoding="utf-8")
        for label, value in (
            ("missing directory", self.tmp / "does-not-exist"),
            ("a file", a_file),
            ("a directory that is no repository", not_a_repo),
        ):
            with self.subTest(repository=label):
                result = self.validate_matching(target_repo=value, base_commit=self.base)
                self.assert_execution_error(result)

    def test_ac5_a_commit_of_another_repository_does_not_resolve(self):
        other = self.tmp / "other-repo"
        other_base = build_repo(other, files={"unrelated.txt": "other\n"})
        result = self.validate_matching(target_repo=self.repo, base_commit=other_base)
        self.assert_execution_error(result)

    def test_ac5_ts7_without_a_matching_name_neither_value_is_needed(self):
        for operation in OPERATIONS:
            with self.subTest(operation=operation):
                result = self.validate_files(operation, {"task0001": ["src/a.go", "README.md"]})
                self.assert_exit(result, 0)

    def test_ac5_without_a_matching_name_the_values_are_not_read_even_when_malformed(self):
        for args in (
            ["--base-commit", "HEAD"],
            ["--base-commit", "not a commit"],
            ["--target-repo", str(self.tmp / "does-not-exist")],
            ["--target-repo", "", "--base-commit", ""],
            ["--target-repo", str(self.tmp / "does-not-exist"), "--base-commit", "0" * 40],
        ):
            with self.subTest(args=args):
                result = self.validate_files(
                    "replace_planning", {"task0001": ["src/a.go"]}, extra_args=args
                )
                self.assert_exit(result, 0)

    def test_ac5_a_matching_name_that_is_not_a_task_file_does_not_trigger_the_inputs(self):
        # A non-string or unsafe `files` entry is reported by the entry
        # validation, never judged here, so it does not make the base inputs
        # mandatory either.
        patch = patch_for("replace_planning", {"task0001": ["src/a.go"]})
        patch["tasks_patch"]["entries"]["task0001"]["files"] = ["../REPORT.md", "/abs/REPORT.md", 7]
        result = self.validate_patch(patch)
        self.assert_exit(result, 1)
        self.assertEqual(self.report_name_errors(result), [])


class TestFindViolationsContract(unittest.TestCase):
    """The component contract of IMPLEMENTATION.md, called directly."""

    def test_ac5_the_inputs_are_read_only_when_a_matching_name_is_present(self):
        self.assertEqual(
            VWO.find_report_name_violations({"task0001": ["src/a.go", "README.md"]}, None, None),
            [],
        )
        with self.assertRaises(VWO.ExecutionError):
            VWO.find_report_name_violations({"task0001": ["REPORT.md"]}, None, None)

    def test_ac3_non_string_and_unsafe_entries_are_skipped(self):
        files_by_task = {
            "task0001": [None, 7, ["REPORT.md"], "/abs/REPORT.md", "../REPORT.md", "a/../REPORT.md", "x\x00REPORT.md", ""],
            "task0002": "REPORT.md",
            "task0003": None,
        }
        self.assertEqual(VWO.find_report_name_violations(files_by_task, None, None), [])

    def test_ac5_require_report_name_base_returns_nothing_on_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "r"
            base = build_repo(repo, files={"a.txt": "x\n"})
            self.assertIsNone(VWO.require_report_name_base(str(repo), base))
            self.assertIsNone(VWO.require_report_name_base(repo, base))

    def test_ac5_require_report_name_base_raises_execution_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "r"
            base = build_repo(repo, files={"a.txt": "x\n"})
            for target_repo, base_commit in (
                (None, base),
                (str(repo), None),
                ("", base),
                (str(repo), ""),
                (str(repo), "HEAD"),
                (str(repo), base.upper()),
                (str(repo), "0" * 40),
                (str(Path(tmp) / "missing"), base),
            ):
                with self.subTest(target_repo=target_repo, base_commit=base_commit):
                    with self.assertRaises(VWO.ExecutionError):
                        VWO.require_report_name_base(target_repo, base_commit)

    def test_ac3_the_result_is_a_list_of_task_and_path_pairs(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "r"
            base = build_repo(repo, files={"keep/REPORT.md": "x\n"})
            result = VWO.find_report_name_violations(
                {
                    "task0001": ["keep/REPORT.md", "new/REPORT.md", "new/REPORT.md"],
                    "task0002": ["keep/REPORT.md"],
                },
                str(repo),
                base,
            )
            self.assertEqual(result, [("task0001", "new/REPORT.md")])


# ---------------------------------------------------------------------------
# AC-6: literal text
# ---------------------------------------------------------------------------

class TestPathsAreLiteralText(CliCase):
    def test_ac6_ts19_a_leading_dash_is_not_an_option(self):
        base = build_repo(
            self.repo,
            files={
                "dir/REPORT.md": "x\n",
                "C/REPORT.md": "x\n",
                "-kept/REPORT.md": "literal\n",
            },
        )
        for name in ("-dir/REPORT.md", "--dir/REPORT.md", "-C/REPORT.md", "--/REPORT.md", "-/REPORT.md"):
            with self.subTest(name=name):
                result = self.validate_files(
                    "replace_planning",
                    {"task0001": [name]},
                    target_repo=self.repo,
                    base_commit=base,
                )
                self.assert_rejected_as_new(result, [("task0001", name)])
        # The same shape is an update when that exact path is in the base.
        result = self.validate_files(
            "replace_planning",
            {"task0001": ["-kept/REPORT.md"]},
            target_repo=self.repo,
            base_commit=base,
        )
        self.assert_exit(result, 0)

    def test_ac6_ts19_pathspec_magic_is_not_interpreted(self):
        base = build_repo(
            self.repo,
            files={"REPORT.md": "x\n", "dir/REPORT.md": "x\n", "dir/FINDINGS.md": "x\n"},
        )
        # Each path ends in a matching name, so it is judged; only its
        # leading segment carries the magic.
        magic = (
            ":(top)/REPORT.md",
            ":(top)dir/REPORT.md",
            ":/REPORT.md",
            ":(literal)dir/REPORT.md",
            ":(icase)dir/report.md",
            ":!dir/REPORT.md",
            ":^dir/REPORT.md",
            ":(glob)**/REPORT.md",
            ":(exclude)other/REPORT.md",
            "dir/:(top)/REPORT.md",
            "REPORT*.md",
            "REPORT[.].md",
            "*/REPORT.md",
            "[d]ir/REPORT.md",
            "d*/REPORT.md",
            "dir/FINDINGS?.md",
        )
        for operation in OPERATIONS:
            for name in magic:
                with self.subTest(operation=operation, name=name):
                    result = self.validate_files(
                        operation,
                        {"task0001": [name]},
                        target_repo=self.repo,
                        base_commit=base,
                    )
                    self.assert_rejected_as_new(result, [("task0001", name)])

    def test_ac6_a_revision_expression_in_a_path_is_not_resolved(self):
        base = build_repo(self.repo, files={"dir/REPORT.md": "x\n", "REPORT.md": "x\n"})
        for name in (
            "dir^{tree}/REPORT.md",
            "dir~1/REPORT.md",
            "dir@{0}/REPORT.md",
            "HEAD:dir/REPORT.md",
            "HEAD:/REPORT.md",
        ):
            with self.subTest(name=name):
                result = self.validate_files(
                    "replace_planning",
                    {"task0001": [name]},
                    target_repo=self.repo,
                    base_commit=base,
                )
                self.assert_rejected_as_new(result, [("task0001", name)])

    def test_ac6_the_same_characters_are_an_update_when_that_exact_path_exists(self):
        base = build_repo(
            self.repo,
            files={":(top)/REPORT.md": "literal colon\n", "x*/REPORT.md": "literal star\n"},
        )
        for name in (":(top)/REPORT.md", "x*/REPORT.md"):
            with self.subTest(name=name):
                result = self.validate_files(
                    "replace_planning",
                    {"task0001": [name]},
                    target_repo=self.repo,
                    base_commit=base,
                )
                self.assert_exit(result, 0)

    def test_ac6_base_tree_entry_answers_regular_other_and_absent(self):
        base = build_repo(
            self.repo,
            files={"a/REPORT.md": "x\n", "d/REPORT.md/inner.txt": "x\n"},
            symlinks={"link-to-a": "a"},
        )
        repo = str(self.repo)
        cases = (
            ("a/REPORT.md", "regular"),
            ("a\\REPORT.md", "regular"),
            ("./a/REPORT.md", "regular"),
            ("a//REPORT.md", "regular"),
            ("d/REPORT.md", "other"),
            ("d", "other"),
            ("link-to-a", "other"),
            ("link-to-a/REPORT.md", "absent"),
            ("a/REPORT.md/deeper", "absent"),
            ("a/missing.md", "absent"),
            ("missing/REPORT.md", "absent"),
            (":(top)a/REPORT.md", "absent"),
            ("-a/REPORT.md", "absent"),
            ("a/REPORT*.md", "absent"),
            ("a^{tree}/REPORT.md", "absent"),
        )
        for path, expected in cases:
            with self.subTest(path=path):
                self.assertEqual(VWO.base_tree_entry(repo, base, path), expected)


# ---------------------------------------------------------------------------
# AC-7: fixtures and the reproduction plan
# ---------------------------------------------------------------------------

FIXTURE_CASES = (
    (REPLACE_PLANNING_FIXTURES / "invalid-report-name-new-file", 1),
    (REPLACE_PLANNING_FIXTURES / "valid-report-name-existing-file", 0),
    (APPEND_REWORK_FIXTURES / "invalid-report-name-new-file", 1),
)


class TestFixtures(CliCase):
    def test_ac7_each_fixture_holds_an_input_and_a_base_tree(self):
        for case_dir, _ in FIXTURE_CASES:
            with self.subTest(case=str(case_dir.relative_to(FIXTURES_ROOT))):
                self.assertTrue((case_dir / "input.json").is_file())
                tree = _load_json(case_dir / "base-tree.json")
                self.assertIsInstance(tree, dict)
                for path, content in tree.items():
                    self.assertIsInstance(path, str)
                    self.assertIsInstance(content, str)

    def test_ac7_each_fixture_matches_its_declared_outcome(self):
        for case_dir, expected in FIXTURE_CASES:
            with self.subTest(case=str(case_dir.relative_to(FIXTURES_ROOT))):
                repo = self.tmp / case_dir.parent.name / case_dir.name
                base = build_repo(repo, files=_load_json(case_dir / "base-tree.json"))
                result = run_cli(
                    [
                        "--kind", "workflow-patch",
                        "--worker", "implementation-planner",
                        "--input", str(case_dir / "input.json"),
                        "--target-repo", str(repo),
                        "--base-commit", base,
                    ]
                )
                self.assert_exit(result, expected)
                if expected == 1:
                    self.assertTrue(self.report_name_errors(result))

    def test_ac7_fixture_names_agree_with_their_directories(self):
        self.assertEqual(
            [c.name.split("-")[0] for c, _ in FIXTURE_CASES], ["invalid", "valid", "invalid"]
        )

    def test_ac7_the_existing_file_fixture_is_an_update_of_a_matching_name(self):
        case_dir = REPLACE_PLANNING_FIXTURES / "valid-report-name-existing-file"
        files = [
            f
            for entry in _load_json(case_dir / "input.json")["tasks_patch"]["entries"].values()
            for f in entry["files"]
        ]
        tree = _load_json(case_dir / "base-tree.json")
        matching = [f for f in files if VWO.is_report_artifact_name(f)]
        self.assertTrue(matching)
        for f in matching:
            self.assertIn(f, tree)

    def test_ac7_the_new_file_fixtures_name_a_matching_file_the_base_lacks(self):
        for case_dir in (
            REPLACE_PLANNING_FIXTURES / "invalid-report-name-new-file",
            APPEND_REWORK_FIXTURES / "invalid-report-name-new-file",
        ):
            with self.subTest(case=str(case_dir.relative_to(FIXTURES_ROOT))):
                files = [
                    f
                    for entry in _load_json(case_dir / "input.json")["tasks_patch"]["entries"].values()
                    for f in entry["files"]
                ]
                tree = _load_json(case_dir / "base-tree.json")
                matching = [f for f in files if VWO.is_report_artifact_name(f)]
                self.assertTrue(matching)
                for f in matching:
                    self.assertNotIn(f, tree)

    def test_ac7_the_plan_of_the_reproduction_steps_is_rejected(self):
        # Reproduction steps: a feature whose `tasks.<id>.files` holds
        # `test-docs/<feature>/REPORT.md`, run unattended. The name is joined
        # at run time; no file of this repository carries it.
        feature = "tcp-send-path-fr8-race-audit"
        report = "/".join(["test-docs", feature, "RE" + "PORT.md"])
        base = build_repo(
            self.repo,
            files={"src/send.go": "package send\n", "feature-docs/x/SPEC.md": "spec\n"},
        )
        patch = patch_for(
            "replace_planning",
            {"task0001": ["src/send.go", report], "task0002": ["src/send_test.go"]},
        )
        result = self.validate_patch(patch, target_repo=self.repo, base_commit=base)
        self.assert_rejected_as_new(result, [("task0001", report)])


if __name__ == "__main__":
    unittest.main()
