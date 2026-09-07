"""Tests for em-workflow/scripts/scan-dependencies.py's `file-tasks`
subcommand (review-sca-axis/task0005).

The script's filename uses a hyphen (CLI-script convention, not an
importable package), so it is loaded via `importlib.util` from its actual
path -- the same technique test_check_plugin_invariants.py already uses.

Acceptance criteria covered (feature-docs/review-sca-axis/tasks/task0005.md):

- AC-1: TestFileTasksBranches -- entry point present => ntd branch; absent
  => report branch; listing failure (entry point present but its
  incomplete-task listing cannot be obtained) => report branch, degraded.
- AC-2: TestReportDestinationResolution -- tmp/ under the FIRST entry of
  the porcelain worktree listing, verified against a real disposable
  repository with an added worktree, and the top-level-resolution command
  never appears in the script's own source.
- AC-3: TestGroupingAndFiling.test_three_advisories_one_package_one_task_*
  and test_two_packages_two_tasks.
- AC-4: TestGroupingAndFiling's incomplete-only duplicate detection cases.
- AC-5: TestBuildDedupKey.
- AC-6: TestSeverityPriorityAndTruncation.
- AC-7: TestModuleCoOwnership.
- AC-8: verified by the implementer's own definition-of-done run, not by a
  test here (it depends on the full suite / check-plugin-invariants.py
  against the real repository).

Test Notes followed: the external task system is never contacted -- every
filing test points `--entry-point` at a stand-in executable
(`_write_standin`) that records the arguments/file contents it received
into a JSON log and replies with a scripted response read from a control
file, so a test can rewrite the control file between two invocations to
simulate persisted state (idempotency). This module's own imports are
standard-library only; the script's transitive imports are not.
"""

import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "em-workflow" / "scripts" / "scan-dependencies.py"


def load_script_module():
    spec = importlib.util.spec_from_file_location("_scan_dependencies_under_test", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


sd = load_script_module()


STANDIN_TEMPLATE = '''#!/usr/bin/env python3
import json
import sys
from pathlib import Path

CONTROL = Path({control!r})
CALLS = Path({calls!r})

argv = sys.argv[1:]
noun = argv[0] if len(argv) > 0 else None
verb = argv[1] if len(argv) > 1 else None
rest = argv[2:]


def read_flag(name):
    if name in rest:
        return rest[rest.index(name) + 1]
    return None


record = {{"noun": noun, "verb": verb, "args": rest}}
for flag in ("--title", "--type", "--priority", "--id", "--format"):
    val = read_flag(flag)
    if val is not None:
        record[flag] = val
for file_flag in ("--references-file", "--append-references-file"):
    path = read_flag(file_flag)
    if path is not None:
        record[file_flag + "-content"] = Path(path).read_text(encoding="utf-8")

calls = json.loads(CALLS.read_text(encoding="utf-8")) if CALLS.exists() else []
calls.append(record)
CALLS.write_text(json.dumps(calls), encoding="utf-8")

control = json.loads(CONTROL.read_text(encoding="utf-8")) if CONTROL.exists() else {{}}
key = f"{{noun}} {{verb}}"
default_stdout = "[]" if key == "task list" else "{{}}"
resp = control.get(key, {{"exit_code": 0, "stdout": default_stdout, "stderr": ""}})
sys.stderr.write(resp.get("stderr", ""))
sys.stdout.write(resp.get("stdout", ""))
sys.exit(resp.get("exit_code", 0))
'''


def _write_standin(tmp_dir):
    """Writes a recording/scripted stand-in executable under `tmp_dir`.
    Returns (standin_path, control_path, calls_path). The control file
    starts out empty ({}); write to it to script a subcommand's response,
    keyed "task list" / "task create" / "task update". The calls file
    starts absent; read it (json list) to inspect every invocation."""
    tmp_dir = Path(tmp_dir)
    control_path = tmp_dir / "control.json"
    calls_path = tmp_dir / "calls.json"
    standin_path = tmp_dir / "standin.py"
    control_path.write_text("{}", encoding="utf-8")
    standin_path.write_text(
        STANDIN_TEMPLATE.format(control=str(control_path), calls=str(calls_path)),
        encoding="utf-8",
    )
    standin_path.chmod(standin_path.stat().st_mode | stat.S_IEXEC | stat.S_IXGRP | stat.S_IXOTH)
    return standin_path, control_path, calls_path


def _set_control(control_path, mapping):
    control_path.write_text(json.dumps(mapping), encoding="utf-8")


def _read_calls(calls_path):
    if not calls_path.exists():
        return []
    return json.loads(calls_path.read_text(encoding="utf-8"))


def _finding(package, advisory_id, severity="high", advisory_title="advisory"):
    return {
        "file": "package.json",
        "line": None,
        "line_end": None,
        "severity": severity,
        "category": "vulnerability",
        "title": f"{package}: {advisory_id} — {advisory_title}",
        "description": "affected range / fixed version / advisory summary",
        "suggestion": "bump the dependency to the fixed version",
    }


def _write_findings(tmp_dir, findings):
    path = Path(tmp_dir) / "findings.json"
    path.write_text(json.dumps(findings), encoding="utf-8")
    return path


def _init_git_repo(path):
    """report_destination() always resolves via `git worktree list
    --porcelain`, even for the plain no-entry-point report branch -- so
    every test that reaches it needs `path` to actually be a git repo (no
    commit required; `git worktree list` works against an empty repo)."""
    env = dict(os.environ)
    env.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0"})
    subprocess.run(
        ["git", "init", "-q", "-b", "main", str(path)],
        env=env, capture_output=True, text=True, check=True,
    )


# ---------------------------------------------------------------------------
# AC-5: the duplicate-detection key
# ---------------------------------------------------------------------------

class TestBuildDedupKey(unittest.TestCase):
    def test_package_only_key_is_the_package_itself(self):
        self.assertEqual(sd.build_dedup_key("lodash"), "lodash")

    def test_package_and_advisory_key_combines_both(self):
        key = sd.build_dedup_key("lodash", "CVE-2024-1")
        self.assertIn("lodash", key)
        self.assertIn("CVE-2024-1", key)
        self.assertNotEqual(key, sd.build_dedup_key("lodash"))

    def test_key_disambiguates_pairs_that_would_collide_under_naive_concatenation(self):
        # A naive `package + advisory_id` string-join would collide here:
        # ("lodash", "X-CVE-1") vs ("lodash-X", "CVE-1"). The real function
        # must not.
        a = sd.build_dedup_key("lodash", "X-CVE-1")
        b = sd.build_dedup_key("lodash-X", "CVE-1")
        self.assertNotEqual(a, b)

    def test_no_call_site_composes_a_key_itself(self):
        """Patching build_dedup_key to a completely different composition
        must not break duplicate detection anywhere in file_tasks -- every
        call site has to re-derive its key from the (patched) function,
        never from a hardcoded composition of its own."""
        with tempfile.TemporaryDirectory() as tmp:
            standin, control, calls = _write_standin(tmp)
            _set_control(
                control,
                {
                    "task list": {
                        "exit_code": 0,
                        "stdout": json.dumps(
                            [
                                {
                                    "id": "task-1",
                                    "package": "lodash",
                                    "status": "incomplete",
                                    "references": "CVE-2024-1 (high)",
                                }
                            ]
                        ),
                    }
                },
            )
            findings = [_finding("lodash", "CVE-2024-1"), _finding("lodash", "CVE-2024-2")]

            def weird_key(package, advisory_id=None):
                if advisory_id is None:
                    return "PKG::" + package
                return "PKG::" + package + "::ADV::" + advisory_id

            with patch.object(sd, "build_dedup_key", side_effect=weird_key):
                result = sd.file_tasks(Path(tmp), "review-sca-axis", findings, str(standin))

            # CVE-2024-1 already recorded => suppressed; CVE-2024-2 is new
            # => appended. If any call site had hardcoded its own key
            # composition instead of calling the (patched) function, this
            # match would fail (either both would look new, or both would
            # look like duplicates).
            self.assertEqual(result["appended_packages"], ["lodash"])
            self.assertEqual(result["suppressed"], [["lodash", "CVE-2024-1"]])


# ---------------------------------------------------------------------------
# Recovery function (Finding text-encoding contract)
# ---------------------------------------------------------------------------

class TestRecoverPackageAdvisory(unittest.TestCase):
    def test_recovers_package_and_advisory_id(self):
        finding = _finding("left-pad", "GHSA-xxxx-yyyy-zzzz", advisory_title="prototype pollution")
        package, advisory_id = sd.recover_package_advisory(finding)
        self.assertEqual(package, "left-pad")
        self.assertEqual(advisory_id, "GHSA-xxxx-yyyy-zzzz")

    def test_recovers_scoped_package_name(self):
        finding = _finding("@scope/pkg", "CVE-2024-9999")
        package, advisory_id = sd.recover_package_advisory(finding)
        self.assertEqual(package, "@scope/pkg")
        self.assertEqual(advisory_id, "CVE-2024-9999")

    def test_malformed_title_raises(self):
        finding = {"title": "this title has no colon-space separator"}
        with self.assertRaises(sd.FindingTitleError):
            sd.recover_package_advisory(finding)

    def test_no_call_site_parses_title_itself(self):
        """group_findings_by_package must route through the recovery
        function -- patching it to a distinguishable stand-in must change
        the grouping result accordingly."""
        findings = [_finding("real-package", "CVE-1")]
        with patch.object(sd, "recover_package_advisory", return_value=("patched-package", "patched-advisory")):
            groups = sd.group_findings_by_package(findings)
        self.assertIn("patched-package", groups)
        self.assertNotIn("real-package", groups)


# ---------------------------------------------------------------------------
# AC-2 / TS-6: report destination resolution
# ---------------------------------------------------------------------------

class TestReportDestinationResolution(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp_path = Path(self._tmp.name)

        git_home = self.tmp_path / "git-home"
        git_home.mkdir()
        self.git_env = dict(os.environ)
        self.git_env.update(
            {
                "HOME": str(git_home),
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_AUTHOR_NAME": "Test",
                "GIT_AUTHOR_EMAIL": "test@example.invalid",
                "GIT_COMMITTER_NAME": "Test",
                "GIT_COMMITTER_EMAIL": "test@example.invalid",
                "GIT_TERMINAL_PROMPT": "0",
            }
        )

        self.main_repo = self.tmp_path / "main-repo"
        self.main_repo.mkdir()
        self._git(self.main_repo, "init", "-q", "-b", "main")
        self._git(self.main_repo, "config", "commit.gpgsign", "false")
        (self.main_repo / "README.md").write_text("base\n")
        self._git(self.main_repo, "add", "README.md")
        self._git(self.main_repo, "commit", "-q", "-m", "initial commit")
        self._git(self.main_repo, "branch", "integration")

        self.linked_wt = self.tmp_path / "linked-worktree"
        self._git(self.main_repo, "worktree", "add", str(self.linked_wt), "integration")

    def _git(self, cwd, *args):
        return subprocess.run(
            ["git", *args], cwd=str(cwd), env=self.git_env, capture_output=True, text=True, check=True,
        )

    def test_resolves_to_main_repo_root_from_main_repo(self):
        root = sd.resolve_main_worktree_root(self.main_repo)
        self.assertEqual(Path(root).resolve(), self.main_repo.resolve())

    def test_resolves_to_main_repo_root_from_linked_worktree(self):
        """The linked ("integration") worktree is NOT first in the
        porcelain listing; invoking the resolution from inside it must
        still yield the main repo's root, not its own path."""
        root = sd.resolve_main_worktree_root(self.linked_wt)
        self.assertEqual(Path(root).resolve(), self.main_repo.resolve())
        self.assertNotEqual(Path(root).resolve(), self.linked_wt.resolve())

    def test_report_destination_is_tmp_under_main_repo_root(self):
        dest = sd.report_destination(self.linked_wt, "review-sca-axis")
        self.assertEqual(dest.parent, self.main_repo.resolve() / "tmp")
        self.assertIn("review-sca-axis", dest.name)

    def test_script_never_uses_the_top_level_resolution_command(self):
        text = SCRIPT_PATH.read_text(encoding="utf-8")
        self.assertNotIn("show-toplevel", text)


# ---------------------------------------------------------------------------
# AC-1: branch selection
# ---------------------------------------------------------------------------

class TestFileTasksBranches(unittest.TestCase):
    def test_no_entry_point_writes_a_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            _init_git_repo(tmp)
            findings = [_finding("pkg-a", "CVE-2024-1")]
            result = sd.file_tasks(Path(tmp), "review-sca-axis", findings, None)
            self.assertEqual(result["branch"], "report")
            self.assertFalse(result["degraded"])
            self.assertIsNone(result["degraded_reason"])
            report_path = Path(result["report_path"])
            self.assertTrue(report_path.is_file())
            content = report_path.read_text(encoding="utf-8")
            self.assertIn("pkg-a", content)
            self.assertIn("CVE-2024-1", content)

    def test_entry_point_present_files_via_ntd(self):
        with tempfile.TemporaryDirectory() as tmp:
            standin, control, calls = _write_standin(tmp)
            _set_control(control, {"task list": {"exit_code": 0, "stdout": "[]"}})
            findings = [_finding("pkg-a", "CVE-2024-1")]
            result = sd.file_tasks(Path(tmp), "review-sca-axis", findings, str(standin))
            self.assertEqual(result["branch"], "ntd")
            self.assertEqual(result["filed_packages"], ["pkg-a"])
            recorded = _read_calls(calls)
            create_calls = [c for c in recorded if c["noun"] == "task" and c["verb"] == "create"]
            self.assertEqual(len(create_calls), 1)
            self.assertEqual(create_calls[0]["--type"], "セキュリティ")

    def test_listing_failure_degrades_to_report_and_states_degradation(self):
        with tempfile.TemporaryDirectory() as tmp:
            _init_git_repo(tmp)
            standin, control, calls = _write_standin(tmp)
            _set_control(control, {"task list": {"exit_code": 1, "stdout": "", "stderr": "boom"}})
            findings = [_finding("pkg-a", "CVE-2024-1")]
            result = sd.file_tasks(Path(tmp), "review-sca-axis", findings, str(standin))
            self.assertEqual(result["branch"], "report")
            self.assertTrue(result["degraded"])
            self.assertEqual(result["degraded_reason"], "task_listing_unavailable")
            content = Path(result["report_path"]).read_text(encoding="utf-8")
            self.assertIn("DEGRADED", content)

    def test_listing_unparsable_output_also_degrades(self):
        with tempfile.TemporaryDirectory() as tmp:
            _init_git_repo(tmp)
            standin, control, calls = _write_standin(tmp)
            _set_control(control, {"task list": {"exit_code": 0, "stdout": "not json"}})
            findings = [_finding("pkg-a", "CVE-2024-1")]
            result = sd.file_tasks(Path(tmp), "review-sca-axis", findings, str(standin))
            self.assertEqual(result["branch"], "report")
            self.assertTrue(result["degraded"])


# ---------------------------------------------------------------------------
# AC-3 / AC-4: grouping, filing, and incomplete-only duplicate detection
# ---------------------------------------------------------------------------

class TestGroupingAndFiling(unittest.TestCase):
    def test_three_advisories_one_package_produce_one_task_with_three_lines(self):
        with tempfile.TemporaryDirectory() as tmp:
            standin, control, calls = _write_standin(tmp)
            _set_control(control, {"task list": {"exit_code": 0, "stdout": "[]"}})
            findings = [
                _finding("pkg-a", "CVE-1", severity="high"),
                _finding("pkg-a", "CVE-2", severity="critical"),
                _finding("pkg-a", "CVE-3", severity="high"),
            ]
            result = sd.file_tasks(Path(tmp), "review-sca-axis", findings, str(standin))
            self.assertEqual(result["filed_packages"], ["pkg-a"])
            recorded = _read_calls(calls)
            create_calls = [c for c in recorded if c["noun"] == "task" and c["verb"] == "create"]
            self.assertEqual(len(create_calls), 1)
            ref_content = create_calls[0]["--references-file-content"]
            lines = [l for l in ref_content.splitlines() if l.strip()]
            self.assertEqual(len(lines), 3)
            self.assertTrue(any("CVE-1" in l and "high" in l for l in lines))
            self.assertTrue(any("CVE-2" in l and "critical" in l for l in lines))
            self.assertTrue(any("CVE-3" in l and "high" in l for l in lines))

    def test_two_packages_produce_two_tasks(self):
        with tempfile.TemporaryDirectory() as tmp:
            standin, control, calls = _write_standin(tmp)
            _set_control(control, {"task list": {"exit_code": 0, "stdout": "[]"}})
            findings = [
                _finding("pkg-a", "CVE-1"),
                _finding("pkg-b", "CVE-2"),
            ]
            result = sd.file_tasks(Path(tmp), "review-sca-axis", findings, str(standin))
            self.assertEqual(sorted(result["filed_packages"]), ["pkg-a", "pkg-b"])
            recorded = _read_calls(calls)
            create_calls = [c for c in recorded if c["noun"] == "task" and c["verb"] == "create"]
            self.assertEqual(len(create_calls), 2)

    def test_incomplete_task_present_appends_only_unrecorded_advisories(self):
        with tempfile.TemporaryDirectory() as tmp:
            standin, control, calls = _write_standin(tmp)
            _set_control(
                control,
                {
                    "task list": {
                        "exit_code": 0,
                        "stdout": json.dumps(
                            [
                                {
                                    "id": "task-existing",
                                    "package": "pkg-a",
                                    "status": "incomplete",
                                    "references": "CVE-1 (high)\nCVE-2 (high)",
                                }
                            ]
                        ),
                    }
                },
            )
            findings = [
                _finding("pkg-a", "CVE-1", severity="high"),
                _finding("pkg-a", "CVE-2", severity="high"),
                _finding("pkg-a", "CVE-3", severity="critical"),
            ]
            result = sd.file_tasks(Path(tmp), "review-sca-axis", findings, str(standin))
            self.assertEqual(result["filed_packages"], [])
            self.assertEqual(result["appended_packages"], ["pkg-a"])
            self.assertEqual(
                sorted(result["suppressed"]),
                sorted([["pkg-a", "CVE-1"], ["pkg-a", "CVE-2"]]),
            )
            recorded = _read_calls(calls)
            update_calls = [c for c in recorded if c["noun"] == "task" and c["verb"] == "update"]
            self.assertEqual(len(update_calls), 1)
            self.assertEqual(update_calls[0]["--id"], "task-existing")
            appended_content = update_calls[0]["--append-references-file-content"]
            appended_lines = [l for l in appended_content.splitlines() if l.strip()]
            self.assertEqual(len(appended_lines), 1)
            self.assertIn("CVE-3", appended_lines[0])
            create_calls = [c for c in recorded if c["noun"] == "task" and c["verb"] == "create"]
            self.assertEqual(len(create_calls), 0)

    def test_only_complete_or_discarded_tasks_still_files_a_new_task(self):
        """Mix of incomplete/complete/discarded across packages in one
        listing (Test Notes AC-4): a package with only complete/discarded
        tasks on file gets a brand-new task, never appended to a closed
        one."""
        with tempfile.TemporaryDirectory() as tmp:
            standin, control, calls = _write_standin(tmp)
            _set_control(
                control,
                {
                    "task list": {
                        "exit_code": 0,
                        "stdout": json.dumps(
                            [
                                {"id": "t-1", "package": "pkg-a", "status": "complete", "references": "CVE-OLD (high)"},
                                {"id": "t-2", "package": "pkg-a", "status": "discarded", "references": "CVE-OLD2 (high)"},
                                {"id": "t-3", "package": "pkg-b", "status": "incomplete", "references": ""},
                            ]
                        ),
                    }
                },
            )
            findings = [
                _finding("pkg-a", "CVE-NEW"),
                _finding("pkg-b", "CVE-NEW-B"),
            ]
            result = sd.file_tasks(Path(tmp), "review-sca-axis", findings, str(standin))
            self.assertEqual(result["filed_packages"], ["pkg-a"])
            self.assertEqual(result["appended_packages"], ["pkg-b"])
            recorded = _read_calls(calls)
            create_calls = [c for c in recorded if c["noun"] == "task" and c["verb"] == "create"]
            self.assertEqual(len(create_calls), 1)
            self.assertEqual(create_calls[0]["--title"], "pkg-a")

    def test_idempotent_second_run_files_nothing_new(self):
        """D3's recovery guarantee: running file-tasks twice over the same
        findings against the same (now-updated) listing state files
        nothing new the second time."""
        with tempfile.TemporaryDirectory() as tmp:
            standin, control, calls = _write_standin(tmp)
            _set_control(control, {"task list": {"exit_code": 0, "stdout": "[]"}})
            findings = [_finding("pkg-a", "CVE-1"), _finding("pkg-a", "CVE-2")]

            first = sd.file_tasks(Path(tmp), "review-sca-axis", findings, str(standin))
            self.assertEqual(first["filed_packages"], ["pkg-a"])

            # Simulate the created task now existing with both advisories
            # already recorded, as the first run's task-create call would
            # have produced against a real task system.
            _set_control(
                control,
                {
                    "task list": {
                        "exit_code": 0,
                        "stdout": json.dumps(
                            [
                                {
                                    "id": "task-1",
                                    "package": "pkg-a",
                                    "status": "incomplete",
                                    "references": "CVE-1 (high)\nCVE-2 (high)",
                                }
                            ]
                        ),
                    }
                },
            )
            second = sd.file_tasks(Path(tmp), "review-sca-axis", findings, str(standin))
            self.assertEqual(second["filed_packages"], [])
            self.assertEqual(second["appended_packages"], [])
            self.assertEqual(sorted(second["suppressed"]), sorted([["pkg-a", "CVE-1"], ["pkg-a", "CVE-2"]]))


# ---------------------------------------------------------------------------
# AC-6: severity as a recorded fact, priority always 高, truncation
# ---------------------------------------------------------------------------

class TestSeverityPriorityAndTruncation(unittest.TestCase):
    def test_priority_is_always_high_regardless_of_severity(self):
        with tempfile.TemporaryDirectory() as tmp:
            standin, control, calls = _write_standin(tmp)
            _set_control(control, {"task list": {"exit_code": 0, "stdout": "[]"}})
            findings = [_finding("pkg-a", "CVE-1", severity="critical")]
            sd.file_tasks(Path(tmp), "review-sca-axis", findings, str(standin))
            recorded = _read_calls(calls)
            create_calls = [c for c in recorded if c["noun"] == "task" and c["verb"] == "create"]
            self.assertEqual(create_calls[0]["--priority"], "高")

    def test_severity_recorded_as_fact_in_reference_line(self):
        line = sd.format_reference_line("CVE-1", "critical")
        self.assertIn("CVE-1", line)
        self.assertIn("critical", line)

    def test_long_advisory_sourced_string_is_truncated_with_visible_marker(self):
        huge_advisory_id = "CVE-" + ("0" * 5000)
        finding = _finding("pkg-a", huge_advisory_id)
        groups = sd.group_findings_by_package([finding])
        (advisory_id, _severity), = groups["pkg-a"]
        self.assertLessEqual(len(advisory_id.encode("utf-8")), sd.UNTRUSTED_TEXT_MAX_BYTES)
        self.assertIn(sd.TRUNCATION_MARKER, advisory_id)
        self.assertLess(len(advisory_id), len(huge_advisory_id))

    def test_truncated_advisory_reaches_the_filed_reference_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            standin, control, calls = _write_standin(tmp)
            _set_control(control, {"task list": {"exit_code": 0, "stdout": "[]"}})
            huge_advisory_id = "CVE-" + ("1" * 5000)
            findings = [_finding("pkg-a", huge_advisory_id)]
            sd.file_tasks(Path(tmp), "review-sca-axis", findings, str(standin))
            recorded = _read_calls(calls)
            create_calls = [c for c in recorded if c["noun"] == "task" and c["verb"] == "create"]
            content = create_calls[0]["--references-file-content"]
            self.assertIn(sd.TRUNCATION_MARKER, content)
            self.assertLessEqual(len(content.encode("utf-8")), sd.UNTRUSTED_TEXT_MAX_BYTES + 64)


class TestTruncateUntrusted(unittest.TestCase):
    def test_short_text_is_unchanged(self):
        self.assertEqual(sd.truncate_untrusted("short"), "short")

    def test_none_passes_through(self):
        self.assertIsNone(sd.truncate_untrusted(None))

    def test_long_text_is_capped_and_marked(self):
        text = "a" * 10000
        out = sd.truncate_untrusted(text)
        self.assertTrue(out.endswith(sd.TRUNCATION_MARKER))
        self.assertLessEqual(len(out.encode("utf-8")), sd.UNTRUSTED_TEXT_MAX_BYTES)

    def test_never_splits_a_multibyte_utf8_sequence(self):
        text = "あ" * 3000  # multi-byte characters throughout
        out = sd.truncate_untrusted(text)
        # Must decode cleanly (already guaranteed by being a str), and the
        # non-marker portion must be composed of whole characters only.
        prefix = out[: -len(sd.TRUNCATION_MARKER)]
        self.assertEqual(prefix, "あ" * (len(prefix)))


# ---------------------------------------------------------------------------
# AC-7: co-ownership skeleton
# ---------------------------------------------------------------------------

class TestModuleCoOwnership(unittest.TestCase):
    def test_both_subcommands_are_registered(self):
        proc = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "--help"], capture_output=True, text=True,
        )
        self.assertIn("scan", proc.stdout)
        self.assertIn("file-tasks", proc.stdout)

    def test_scan_is_a_marked_placeholder(self):
        proc = subprocess.run(
            [sys.executable, str(SCRIPT_PATH), "scan"], capture_output=True, text=True,
        )
        self.assertEqual(proc.returncode, sd.EXIT_EXECUTION_ERROR)
        self.assertIn("implemented by the other task", proc.stderr)

    def test_file_tasks_runs_end_to_end_via_the_real_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            _init_git_repo(tmp)
            findings_path = _write_findings(tmp, [_finding("pkg-a", "CVE-1")])
            proc = subprocess.run(
                [
                    sys.executable, str(SCRIPT_PATH), "file-tasks",
                    "--project-root", tmp,
                    "--feature", "review-sca-axis",
                    "--findings", str(findings_path),
                ],
                capture_output=True, text=True,
            )
            self.assertEqual(proc.returncode, sd.EXIT_OK, proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertEqual(payload["branch"], "report")


if __name__ == "__main__":
    unittest.main()
