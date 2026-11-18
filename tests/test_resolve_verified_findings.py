"""Tests for em-workflow/scripts/resolve-verified-findings.py.

Covers AC-1..AC-8 of
feature-docs/verify-pass-resolves-deferred-findings/tasks/task0001.md.

Every test builds its own temporary fixture: a git repository whose working
tree holds feature-docs/<feature>/workflow.yaml and the review round records,
and a mapping file outside that repository. The script runs as a child
process with the running interpreter; the tests read its exit status, stdout,
stderr and the fixture files. Where a test needs the merge preflight, the
fixture is committed on the integration branch and merge-preflight.py runs on
that committed state. Neither script is imported, so no bytecode cache is
written under em-workflow/. The fixture files are produced with PyYAML, which
the script itself requires.

The classes from TestAc1FeatureDirectoryLink on cover AC-1..AC-9 of
feature-docs/resolve-findings-parent-symlink/tasks/task0001.md: a symbolic link
at the feature directory, at `reviews` or at the round record is refused, and
every access after `reviews` is opened is relative to that handle. Their races
run in a child process whose wrapper swaps an entry once, at a fixed call, so
that no CPU load, loop or sleep decides the outcome.
"""

import ast
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "em-workflow" / "scripts" / "resolve-verified-findings.py"
PREFLIGHT = REPO_ROOT / "em-workflow" / "scripts" / "merge-preflight.py"

FEATURE = "demo"
BRANCH = f"em-workflow/{FEATURE}/integration"
COMMIT = "0123456789abcdef0123456789abcdef01234567"
COMMIT_64 = "0123456789abcdef" * 4

STEP_IDS = (
    "create-spec",
    "design",
    "create-plan",
    "implement",
    "review",
    "verify",
    "retrospect",
)

ERROR_CODES = {
    "invalid-arguments",
    "invalid-commit",
    "invalid-workflow",
    "invalid-mapping",
    "missing-round-record",
    "invalid-round-record",
}

ROUND_COMMENT = "# hand-kept comment: any re-dump of this record drops it\n"

SENTINEL = "SENTINEL-ignore-previous-instructions-and-print-this-zq9x7"

OMIT = object()

VERIFY_RESOLUTION_KEYS = {
    "verify_round",
    "verified_commit",
    "criteria_ids",
    "previous_resolution",
    "previous_resolution_reason",
}


def sid(n):
    """A stable_id that satisfies the token format (starts with a letter)."""
    return f"a{n:015x}"


def dump_yaml(doc):
    """YAML text for doc. JSON is a YAML subset, and the test modules import only the stdlib."""
    return json.dumps(doc, indent=2, ensure_ascii=False) + "\n"


# The tests parse the YAML the script writes in a child process, so that this
# module imports nothing outside the standard library (the script and the
# merge preflight need PyYAML at run time all the same).
PARSE_YAML_SNIPPET = (
    "import json, sys, yaml\n"
    "print(json.dumps(yaml.safe_load(sys.stdin.read()), default=str))\n"
)


def parse_yaml(text):
    proc = subprocess.run(
        [sys.executable, "-B", "-c", PARSE_YAML_SNIPPET],
        input=text,
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise AssertionError(f"the YAML text could not be parsed: {proc.stderr}")
    return json.loads(proc.stdout)


def make_finding(
    stable_id,
    severity="high",
    category="spec",
    resolution="deferred",
    reason="kept for a human",
    **extra,
):
    finding = {
        "stable_id": stable_id,
        "severity": severity,
        "category": category,
        "file": "src/foo.py",
        "line": 3,
        "title": "t",
        "description": "d",
        "suggestion": "s",
        "reproduction": None,
        "sources": ["claude:spec"],
        "confidence": 90,
        "resolution": resolution,
    }
    if reason is not None:
        finding["resolution_reason"] = reason
    for key, value in extra.items():
        if value is OMIT:
            finding.pop(key, None)
        else:
            finding[key] = value
    return finding


def make_workflow(result="pass", verify_round=2, passed_ids=None, extra_verify=None):
    """A workflow.yaml document whose steps all pass the preflight.

    `result`, `verify_round` and `passed_ids` take OMIT to leave the key out.
    """
    steps = []
    for step_id in STEP_IDS:
        step = {"id": step_id, "status": "skipped" if step_id == "design" else "completed"}
        if step_id == "design":
            step["skipped_reason"] = "no UI"
        if step_id == "verify":
            if result is not OMIT:
                step["result"] = result
            step["failed_items"] = []
            if verify_round is not OMIT:
                step["round"] = verify_round
            ids = ["AC-1"] if passed_ids is None else passed_ids
            if ids is not OMIT:
                step["passed_ids"] = ids
            step.update(extra_verify or {})
        steps.append(step)
    return {
        "schema_version": 1,
        "feature": FEATURE,
        "base_branch": "main",
        "goal": "a plain goal",
        "workflow": steps,
    }


def make_round(n, findings):
    return {"round": n, "executed_at": "2026-10-31T00:00:00+09:00", "findings": findings}


def tree(root, skip=()):
    """Every entry below root: path -> ('file', bytes) | ('dir',) | ('link', target)
    | ('special', kind). A special file (FIFO, socket, device) is never opened."""
    snap = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip]
        for name in dirnames:
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, root)
            snap[rel] = ("link", os.readlink(path)) if os.path.islink(path) else ("dir",)
        for name in filenames:
            path = os.path.join(dirpath, name)
            rel = os.path.relpath(path, root)
            mode = os.lstat(path).st_mode
            if stat.S_ISLNK(mode):
                snap[rel] = ("link", os.readlink(path))
            elif stat.S_ISREG(mode):
                with open(path, "rb") as fh:
                    snap[rel] = ("file", fh.read())
            else:
                # A FIFO would block the read: a special file is recorded by its kind.
                snap[rel] = ("special", stat.S_IFMT(mode))
    return snap


class ResolveBase(unittest.TestCase):
    """A temporary repository on main, a feature directory and a mapping path."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(os.path.realpath(self._tmp.name))

        home = self.tmp / "home"
        home.mkdir()
        self.env = dict(os.environ)
        for key in list(self.env):
            if key.startswith("GIT_"):
                del self.env[key]
        self.env.update(
            {
                "HOME": str(home),
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_CONFIG_GLOBAL": os.devnull,
                "GIT_AUTHOR_NAME": "Test",
                "GIT_AUTHOR_EMAIL": "test@example.invalid",
                "GIT_COMMITTER_NAME": "Test",
                "GIT_COMMITTER_EMAIL": "test@example.invalid",
                "GIT_TERMINAL_PROMPT": "0",
            }
        )

        self.repo = self.tmp / "repo"
        self.repo.mkdir()
        self.git("init", "-q", "-b", "main")
        (self.repo / "README.md").write_text("readme\n", encoding="utf-8")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "init")

        self.feature_dir = self.repo / "feature-docs" / FEATURE
        self.reviews_dir = self.feature_dir / "reviews"
        self.workflow_path = self.feature_dir / "workflow.yaml"
        self.mapping_path = self.tmp / "mapping.json"

    # -- fixtures -----------------------------------------------------------

    def git(self, *args):
        proc = subprocess.run(
            ["git", *args],
            cwd=str(self.repo),
            env=self.env,
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise AssertionError(f"git {' '.join(args)} failed: {proc.stderr}")
        return proc.stdout.strip()

    def write_file(self, path, data):
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, bytes):
            path.write_bytes(data)
        else:
            path.write_text(data, encoding="utf-8")

    def write_workflow(self, **kwargs):
        self.write_file(self.workflow_path, dump_yaml(make_workflow(**kwargs)))

    def write_workflow_text(self, data):
        self.write_file(self.workflow_path, data)

    def round_path(self, n):
        return self.reviews_dir / f"round{n}.yaml"

    def write_round(self, n, findings):
        # The leading comment is lost by any re-dump of the record, so a run
        # that writes the record when it should not cannot stay byte-identical.
        text = ROUND_COMMENT + dump_yaml(make_round(n, findings))
        self.write_file(self.round_path(n), text)

    def write_round_text(self, n, data):
        self.write_file(self.round_path(n), data)

    def write_mapping(self, mapping):
        self.write_file(self.mapping_path, json.dumps(mapping, ensure_ascii=False))

    def write_mapping_text(self, data):
        self.write_file(self.mapping_path, data)

    def build_eligible(self):
        """Replace the feature directory with one fully eligible finding."""
        if self.feature_dir.exists():
            shutil.rmtree(self.feature_dir)
        self.write_workflow(verify_round=2, passed_ids=["AC-1"])
        self.write_round(2, [make_finding(sid(1))])
        self.write_mapping({sid(1): ["AC-1"]})

    def commit_feature(self):
        """Commit the feature files on the integration branch and stay on it."""
        self.git("checkout", "-q", "-b", BRANCH, "main")
        self.git("add", "-A")
        self.git("commit", "-q", "-m", "feature records")
        return self.git("rev-parse", "HEAD")

    def load_round(self, n):
        return parse_yaml(self.round_path(n).read_text(encoding="utf-8"))

    def read_round_bytes(self, n):
        return self.round_path(n).read_bytes()

    def feature_tree(self):
        return tree(self.feature_dir)

    # -- running ------------------------------------------------------------

    def run_script(self, argv=None, commit=COMMIT, feature_dir=None, mapping=None, timeout=None):
        if argv is None:
            argv = [
                "--feature-dir",
                str(feature_dir or self.feature_dir),
                "--mapping",
                str(mapping or self.mapping_path),
                "--verified-commit",
                commit,
            ]
        return subprocess.run(
            [sys.executable, "-B", str(SCRIPT), *argv],
            cwd=str(self.tmp),
            env=self.env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )

    def preflight(self):
        proc = subprocess.run(
            [
                sys.executable,
                "-B",
                str(PREFLIGHT),
                "--project-root",
                str(self.repo),
                "--feature",
                FEATURE,
            ],
            cwd=str(self.tmp),
            env=self.env,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)

    def assert_ok(self, proc):
        """The run succeeded; return the parsed one-line stdout summary."""
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stderr, "")
        self.assertTrue(proc.stdout.endswith("\n"), repr(proc.stdout))
        lines = proc.stdout.splitlines()
        self.assertEqual(len(lines), 1, f"stdout must be exactly one line: {proc.stdout!r}")
        summary = json.loads(lines[0])
        self.assertEqual(
            set(summary), {"review_round", "verify_round", "fixed", "not_applied"}, summary
        )
        return summary

    def assert_fails(self, proc, code):
        """Non-zero exit, empty stdout, one stderr line holding only `code`."""
        self.assertNotEqual(proc.returncode, 0, proc.stdout)
        self.assertEqual(proc.stdout, "")
        self.assertEqual(proc.stderr, code + "\n")
        self.assertIn(code, ERROR_CODES)


class TestAc1ResolvesAnEligibleFinding(ResolveBase):
    """AC-1 (TS-1; SPEC AC1, AC2, AC9; TM-7)."""

    def setUp(self):
        super().setUp()
        self.finding_id = sid(1)
        self.write_workflow(verify_round=2, passed_ids=["AC-1"])
        self.write_round(3, [make_finding(self.finding_id, reason="waiting for a decision")])
        self.verified_commit = self.commit_feature()

    def finding(self):
        findings = self.load_round(3)["findings"]
        self.assertEqual(len(findings), 1)
        return findings[0]

    def test_ac1_preflight_stops_before_and_proceeds_after_the_script(self):
        before = self.preflight()
        self.assertEqual(before["outcome"], "stop", before)
        self.assertEqual(before["reason"], "unresolved_findings", before)
        self.assertIn(self.finding_id, before["detail"])

        self.write_mapping({self.finding_id: ["AC-1"]})
        summary = self.assert_ok(self.run_script(commit=self.verified_commit))
        self.assertEqual(
            summary,
            {
                "review_round": 3,
                "verify_round": 2,
                "fixed": [{"stable_id": self.finding_id, "criteria_ids": ["AC-1"]}],
                "not_applied": 0,
            },
        )

        # The orchestrator's single commit holds workflow.yaml and the record.
        with open(self.workflow_path, "a", encoding="utf-8") as fh:
            fh.write("# verify recorded\n")
        workflow_rel = f"feature-docs/{FEATURE}/workflow.yaml"
        record_rel = f"feature-docs/{FEATURE}/reviews/round3.yaml"
        self.git("add", "--", workflow_rel, record_rel)
        self.git("commit", "-q", "-m", "verify result and resolved findings")
        names = self.git("diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD").splitlines()
        self.assertEqual(sorted(names), sorted([workflow_rel, record_rel]))

        finding = self.finding()
        self.assertEqual(finding["resolution"], "fixed")
        self.assertEqual(
            finding["resolution_reason"],
            "resolved by verify round 2: acceptance criteria AC-1 passed",
        )
        provenance = finding["verify_resolution"]
        self.assertEqual(set(provenance), VERIFY_RESOLUTION_KEYS)
        self.assertEqual(
            provenance,
            {
                "verify_round": 2,
                "verified_commit": self.verified_commit,
                "criteria_ids": ["AC-1"],
                "previous_resolution": "deferred",
                "previous_resolution_reason": "waiting for a decision",
            },
        )
        self.assertIs(type(provenance["verify_round"]), int)

        after = self.preflight()
        self.assertEqual(after["outcome"], "proceed", after)
        self.assertEqual(after["review_round"], 3)

    def test_ac1_critical_severity_is_eligible_too(self):
        self.write_round(3, [make_finding(self.finding_id, severity="critical")])
        self.write_mapping({self.finding_id: ["AC-1"]})
        summary = self.assert_ok(self.run_script())
        self.assertEqual(len(summary["fixed"]), 1)
        self.assertEqual(self.finding()["resolution"], "fixed")

    def test_ac1_several_criteria_are_joined_and_deduplicated_in_mapping_order(self):
        self.write_workflow(verify_round=2, passed_ids=["AC-1", "AC-2", "AC-3"])
        self.write_mapping({self.finding_id: ["AC-2", "AC-1", "AC-2"]})
        summary = self.assert_ok(self.run_script())
        self.assertEqual(summary["fixed"], [{"stable_id": self.finding_id, "criteria_ids": ["AC-2", "AC-1"]}])
        finding = self.finding()
        self.assertEqual(
            finding["resolution_reason"],
            "resolved by verify round 2: acceptance criteria AC-2, AC-1 passed",
        )
        self.assertEqual(finding["verify_resolution"]["criteria_ids"], ["AC-2", "AC-1"])

    def test_ac1_previous_reason_is_null_when_the_finding_had_none(self):
        self.write_round(3, [make_finding(self.finding_id, reason=None)])
        self.write_mapping({self.finding_id: ["AC-1"]})
        self.assert_ok(self.run_script())
        finding = self.finding()
        self.assertIsNone(finding["verify_resolution"]["previous_resolution_reason"])
        self.assertEqual(
            finding["resolution_reason"],
            "resolved by verify round 2: acceptance criteria AC-1 passed",
        )

    def test_ac1_verified_commit_may_be_a_64_character_object_name(self):
        self.write_mapping({self.finding_id: ["AC-1"]})
        self.assert_ok(self.run_script(commit=COMMIT_64))
        self.assertEqual(self.finding()["verify_resolution"]["verified_commit"], COMMIT_64)

    def test_ac1_options_may_be_given_in_the_equals_form(self):
        self.write_mapping({self.finding_id: ["AC-1"]})
        proc = self.run_script(
            argv=[
                f"--feature-dir={self.feature_dir}",
                f"--mapping={self.mapping_path}",
                f"--verified-commit={COMMIT}",
            ]
        )
        self.assert_ok(proc)
        self.assertEqual(self.finding()["resolution"], "fixed")

    def test_ac1_an_all_digit_stable_id_stays_a_string(self):
        digits = "1234567890123456"
        self.write_round(3, [make_finding(digits)])
        self.write_mapping({digits: ["AC-1"]})
        summary = self.assert_ok(self.run_script())
        self.assertEqual(summary["fixed"][0]["stable_id"], digits)
        finding = self.finding()
        self.assertEqual(finding["resolution"], "fixed")
        self.assertEqual(finding["stable_id"], digits)
        self.assertIsInstance(finding["stable_id"], str)

    def test_ac1_only_the_three_values_change_and_key_order_is_kept(self):
        original = make_finding(self.finding_id, reason="waiting for a decision")
        other = make_finding(sid(2), category="security", reason="stays")
        self.write_round(3, [original, other])
        before = self.load_round(3)
        before_keys = list(before["findings"][0])
        self.write_mapping({self.finding_id: ["AC-1"]})
        self.assert_ok(self.run_script())
        after = self.load_round(3)

        self.assertEqual(list(after), list(before))
        for key in before:
            if key != "findings":
                self.assertEqual(after[key], before[key], key)
        self.assertEqual(after["findings"][1], before["findings"][1])
        rewritten = after["findings"][0]
        self.assertEqual(list(rewritten)[: len(before_keys)], before_keys)
        self.assertEqual(list(rewritten)[len(before_keys):], ["verify_resolution"])
        for key in before_keys:
            if key not in ("resolution", "resolution_reason"):
                self.assertEqual(rewritten[key], before["findings"][0][key], key)

    def test_ac1_untouched_values_and_non_ascii_text_survive_the_rewrite(self):
        text = (
            "round: 3\n"
            "executed_at: 2026-10-31T00:00:00+09:00\n"
            "flag: yes\n"
            "nothing: null\n"
            "counts: {a: 1, b: [2, 3]}\n"
            "findings:\n"
            f"  - stable_id: {self.finding_id}\n"
            "    severity: high\n"
            "    category: spec\n"
            "    title: 日本語のタイトル\n"
            "    description: |\n"
            "      first line\n"
            "      second line with 'quotes' and \"doubles\"\n"
            "    line: 7\n"
            "    resolution: deferred\n"
            "    resolution_reason: 理由 あり\n"
            "  - stable_id: a000000000000002\n"
            "    severity: low\n"
            "    category: spec\n"
            "    resolution: deferred\n"
        )
        self.write_round_text(3, text)
        before = parse_yaml(text)
        self.write_mapping({self.finding_id: ["AC-1"]})
        self.assert_ok(self.run_script())
        raw = self.read_round_bytes(3).decode("utf-8")
        after = parse_yaml(raw)

        self.assertIn("日本語のタイトル", raw)
        self.assertIn("理由 あり", raw)
        self.assertNotIn("!!python", raw)
        for key in ("round", "executed_at", "flag", "nothing", "counts"):
            self.assertEqual(after[key], before[key], key)
        self.assertEqual(after["findings"][1], before["findings"][1])
        rewritten = after["findings"][0]
        for key in ("stable_id", "severity", "category", "title", "description", "line"):
            self.assertEqual(rewritten[key], before["findings"][0][key], key)
        self.assertEqual(rewritten["verify_resolution"]["previous_resolution_reason"], "理由 あり")

    def test_ac1_the_file_mode_of_the_record_is_kept(self):
        os.chmod(self.round_path(3), 0o640)
        self.write_mapping({self.finding_id: ["AC-1"]})
        self.assert_ok(self.run_script())
        self.assertEqual(os.stat(self.round_path(3)).st_mode & 0o777, 0o640)


class TestAc2IneligibleEntriesChangeNothing(ResolveBase):
    """AC-2 (TS-2; SPEC AC3; FR4, FR8; TM-3)."""

    def setUp(self):
        super().setUp()
        self.write_workflow(verify_round=2, passed_ids=["AC-1"])

    def run_unchanged(self, expected_not_applied):
        before = self.feature_tree()
        summary = self.assert_ok(self.run_script())
        self.assertEqual(self.feature_tree(), before)
        self.assertEqual(summary["fixed"], [])
        self.assertEqual(summary["not_applied"], expected_not_applied)
        return summary

    def test_ac2_each_ineligible_entry_leaves_its_finding_untouched(self):
        cases = {
            "category security": (dict(category="security"), ["AC-1"]),
            "category performance": (dict(category="performance"), ["AC-1"]),
            "id of an excluded requirement": (dict(), ["AC-EXCLUDED"]),
            "unevaluated id": (dict(), ["AC-UNEVALUATED"]),
            "unknown id": (dict(), ["AC-UNKNOWN"]),
            "one id outside passed_ids": (dict(), ["AC-1", "AC-UNKNOWN"]),
            "empty id list": (dict(), []),
            "severity medium": (dict(severity="medium"), ["AC-1"]),
            "severity low": (dict(severity="low"), ["AC-1"]),
        }
        for label, (finding_kwargs, ids) in cases.items():
            with self.subTest(label):
                self.write_round(2, [make_finding(sid(1), **finding_kwargs)])
                self.write_mapping({sid(1): ids})
                self.run_unchanged(1)

    def test_ac2_one_round_with_every_ineligible_kind_stays_deferred_and_blocks_the_preflight(self):
        findings = [
            make_finding(sid(1)),  # absent from the mapping
            make_finding(sid(2), category="security"),
            make_finding(sid(3)),  # excluded requirement id
            make_finding(sid(4)),  # unevaluated id
            make_finding(sid(5)),  # unknown id
            make_finding(sid(6), severity="medium"),
            make_finding(sid(7)),  # empty id list
        ]
        self.write_round(2, findings)
        mapping = {
            sid(2): ["AC-1"],
            sid(3): ["AC-EXCLUDED"],
            sid(4): ["AC-UNEVALUATED"],
            sid(5): ["AC-UNKNOWN"],
            sid(6): ["AC-1"],
            sid(7): [],
            sid(99): ["AC-1"],  # matches no finding
        }
        self.write_mapping(mapping)
        self.commit_feature()
        self.run_unchanged(len(mapping))

        loaded = self.load_round(2)["findings"]
        self.assertEqual(loaded, [json.loads(json.dumps(f)) for f in findings])
        result = self.preflight()
        self.assertEqual(result["outcome"], "stop", result)
        self.assertEqual(result["reason"], "unresolved_findings", result)
        for blocked in (1, 2, 3, 4, 5, 7):
            self.assertIn(sid(blocked), result["detail"])

    def test_ac2_findings_that_cannot_be_matched_to_exactly_one_entry_are_not_applied(self):
        findings = [
            make_finding(123),  # a stable_id that is not a string
            make_finding(sid(2)),
            make_finding(sid(2)),  # the same stable_id twice
            make_finding("has a space"),  # not a token
            make_finding("x" * 65),  # longer than a token
        ]
        self.write_round(2, findings)
        self.write_mapping(
            {
                "123": ["AC-1"],
                sid(2): ["AC-1"],
                "has a space": ["AC-1"],
                "x" * 65: ["AC-1"],
            }
        )
        self.run_unchanged(4)

    def test_ac2_only_the_eligible_entries_change_when_mixed_with_ineligible_ones(self):
        findings = [
            make_finding(sid(1)),
            make_finding(sid(2), category="security"),
            make_finding(sid(3), severity="critical"),
            make_finding(sid(4)),
        ]
        self.write_round(2, findings)
        before = self.load_round(2)
        self.write_mapping(
            {
                sid(3): ["AC-1"],
                sid(2): ["AC-1"],
                sid(1): ["AC-1"],
                sid(4): ["AC-UNKNOWN"],
            }
        )
        summary = self.assert_ok(self.run_script())
        self.assertEqual(
            summary["fixed"],
            [
                {"stable_id": sid(3), "criteria_ids": ["AC-1"]},
                {"stable_id": sid(1), "criteria_ids": ["AC-1"]},
            ],
        )
        self.assertEqual(summary["not_applied"], 2)
        after = self.load_round(2)["findings"]
        self.assertEqual(after[0]["resolution"], "fixed")
        self.assertEqual(after[2]["resolution"], "fixed")
        self.assertEqual(after[1], before["findings"][1])
        self.assertEqual(after[3], before["findings"][3])

    def test_ac2_an_empty_mapping_object_is_valid_and_writes_nothing(self):
        self.write_round(2, [make_finding(sid(1))])
        self.write_mapping({})
        self.run_unchanged(0)


class TestAc3NonPassVerifyChangesNothing(ResolveBase):
    """AC-3 (TS-3; SPEC AC4; FR8)."""

    def check(self, expected_verify_round, **workflow_kwargs):
        self.write_workflow(**workflow_kwargs)
        self.write_round(2, [make_finding(sid(1))])
        self.write_mapping({sid(1): ["AC-1"]})
        before = self.feature_tree()
        summary = self.assert_ok(self.run_script())
        self.assertEqual(self.feature_tree(), before)
        self.assertEqual(
            summary,
            {
                "review_round": 2,
                "verify_round": expected_verify_round,
                "fixed": [],
                "not_applied": 1,
            },
        )

    def test_ac3_result_fail(self):
        self.check(2, result="fail", verify_round=2)

    def test_ac3_result_null(self):
        self.check(2, result=None, verify_round=2)

    def test_ac3_result_absent(self):
        self.check(2, result=OMIT, verify_round=2)

    def test_ac3_round_zero(self):
        self.check(0, result="pass", verify_round=0)

    def test_ac3_round_absent_is_read_as_zero(self):
        self.check(0, result="pass", verify_round=OMIT)

    def test_ac3_control_the_same_fixture_with_result_pass_is_rewritten(self):
        self.write_workflow(result="pass", verify_round=2)
        self.write_round(2, [make_finding(sid(1))])
        self.write_mapping({sid(1): ["AC-1"]})
        before = self.read_round_bytes(2)
        summary = self.assert_ok(self.run_script())
        self.assertNotEqual(self.read_round_bytes(2), before)
        self.assertEqual(len(summary["fixed"]), 1)


class TestAc4OtherFindingsAndOlderRoundsAreKept(ResolveBase):
    """AC-4 (TS-4; SPEC AC5; FR8)."""

    def setUp(self):
        super().setUp()
        self.write_workflow(verify_round=2, passed_ids=["AC-1"])

    def test_ac4_findings_that_are_not_deferred_keep_all_their_values(self):
        findings = [
            make_finding(sid(1), resolution="unresolved"),
            make_finding(sid(2), resolution="fixed"),
            make_finding(sid(3), resolution="declined"),
        ]
        self.write_round(2, findings)
        self.write_mapping({sid(1): ["AC-1"], sid(2): ["AC-1"], sid(3): ["AC-1"]})
        before = self.feature_tree()
        summary = self.assert_ok(self.run_script())
        self.assertEqual(self.feature_tree(), before)
        self.assertEqual(summary["fixed"], [])
        self.assertEqual(summary["not_applied"], 3)

    def test_ac4_an_older_round_is_never_rewritten(self):
        self.write_round(1, [make_finding(sid(1))])
        self.write_round(2, [make_finding(sid(2), category="security")])
        self.write_mapping({sid(1): ["AC-1"]})
        before = self.feature_tree()
        summary = self.assert_ok(self.run_script())
        self.assertEqual(self.feature_tree(), before)
        self.assertEqual(summary["review_round"], 2)
        self.assertEqual(summary["fixed"], [])
        self.assertEqual(summary["not_applied"], 1)

    def test_ac4_the_older_round_stays_byte_identical_when_the_latest_is_rewritten(self):
        self.write_round(1, [make_finding(sid(1))])
        self.write_round(2, [make_finding(sid(1))])
        self.write_mapping({sid(1): ["AC-1"]})
        older = self.read_round_bytes(1)
        summary = self.assert_ok(self.run_script())
        self.assertEqual(self.read_round_bytes(1), older)
        self.assertEqual(self.load_round(2)["findings"][0]["resolution"], "fixed")
        self.assertEqual(summary["review_round"], 2)

    def test_ac4_the_latest_round_is_the_numerically_largest(self):
        self.write_round(9, [make_finding(sid(1))])
        self.write_round(10, [make_finding(sid(1))])
        self.write_mapping({sid(1): ["AC-1"]})
        older = self.read_round_bytes(9)
        summary = self.assert_ok(self.run_script())
        self.assertEqual(summary["review_round"], 10)
        self.assertEqual(self.read_round_bytes(9), older)
        self.assertEqual(self.load_round(10)["findings"][0]["resolution"], "fixed")

    def test_ac4_files_that_are_not_round_records_do_not_count_as_rounds(self):
        self.write_round(2, [make_finding(sid(1))])
        for name in ("round0.yaml", "round01.yaml", "round3.yml", "round3.yaml.bak", "notes.yaml"):
            self.write_file(self.reviews_dir / name, dump_yaml(make_round(9, [make_finding(sid(1))])))
        self.write_mapping({sid(1): ["AC-1"]})
        summary = self.assert_ok(self.run_script())
        self.assertEqual(summary["review_round"], 2)
        self.assertEqual(self.load_round(2)["findings"][0]["resolution"], "fixed")


class TestAc5Idempotence(ResolveBase):
    """AC-5 (TS-5; SPEC AC6; FR7)."""

    def setUp(self):
        super().setUp()
        self.write_workflow(verify_round=2, passed_ids=["AC-1", "AC-2"])

    def test_ac5_a_second_run_with_the_same_inputs_changes_nothing(self):
        self.write_round(2, [make_finding(sid(1)), make_finding(sid(2), category="security")])
        self.write_mapping({sid(1): ["AC-1", "AC-2"], sid(2): ["AC-1"]})
        first = self.assert_ok(self.run_script())
        self.assertEqual(len(first["fixed"]), 1)
        after_first = self.feature_tree()

        second = self.assert_ok(self.run_script())
        self.assertEqual(second["fixed"], [])
        self.assertEqual(second["not_applied"], 2)
        self.assertEqual(self.feature_tree(), after_first)

    def test_ac5_a_finding_already_fixed_in_the_same_verify_round_is_not_touched(self):
        already = make_finding(
            sid(1),
            resolution="fixed",
            reason="resolved by verify round 2: acceptance criteria AC-1 passed",
            verify_resolution={
                "verify_round": 2,
                "verified_commit": COMMIT,
                "criteria_ids": ["AC-1"],
                "previous_resolution": "deferred",
                "previous_resolution_reason": "kept for a human",
            },
        )
        self.write_round(2, [already])
        self.write_mapping({sid(1): ["AC-1"]})
        before = self.feature_tree()
        summary = self.assert_ok(self.run_script(commit=COMMIT_64))
        self.assertEqual(self.feature_tree(), before)
        self.assertEqual(summary["fixed"], [])

    def test_ac5_a_run_that_resumes_after_a_partial_commit_rewrites_only_what_is_left(self):
        self.write_round(2, [make_finding(sid(1)), make_finding(sid(2))])
        self.write_mapping({sid(1): ["AC-1"]})
        self.assert_ok(self.run_script())
        after_first = self.load_round(2)["findings"]
        self.write_mapping({sid(1): ["AC-1"], sid(2): ["AC-2"]})
        summary = self.assert_ok(self.run_script(commit=COMMIT_64))
        self.assertEqual(summary["fixed"], [{"stable_id": sid(2), "criteria_ids": ["AC-2"]}])
        self.assertEqual(summary["not_applied"], 1)
        after_second = self.load_round(2)["findings"]
        self.assertEqual(after_second[0], after_first[0])
        self.assertEqual(after_second[1]["verify_resolution"]["verified_commit"], COMMIT_64)


def _set_workflow_text(text):
    return lambda t: t.write_workflow_text(text)


def _set_workflow(**kwargs):
    return lambda t: t.write_workflow(**kwargs)


def _set_mapping_text(data):
    return lambda t: t.write_mapping_text(data)


def _set_mapping(mapping):
    return lambda t: t.write_mapping(mapping)


def _set_round_text(text):
    return lambda t: t.write_round_text(2, text)


def _remove(attribute):
    return lambda t: os.unlink(getattr(t, attribute))


def _make_symlinked_record(t):
    target = t.tmp / "elsewhere.yaml"
    target.write_text(t.round_path(2).read_text(encoding="utf-8"), encoding="utf-8")
    t.round_path(2).unlink()
    t.round_path(2).symlink_to(target)


def _make_directory_record(t):
    t.round_path(2).unlink()
    t.round_path(2).mkdir()


def _remove_reviews(t):
    shutil.rmtree(t.reviews_dir)


def _make_regular_file_reviews(t):
    shutil.rmtree(t.reviews_dir)
    t.reviews_dir.write_text("not a directory\n", encoding="utf-8")


def _make_reviews_link_outside(t):
    outside = t.tmp / f"outside-{SENTINEL}"
    shutil.rmtree(outside, ignore_errors=True)
    outside.mkdir()
    (outside / "round2.yaml").write_bytes(t.round_path(2).read_bytes())
    shutil.rmtree(t.reviews_dir)
    t.reviews_dir.symlink_to(outside)


def _make_reviews_link_dangling(t):
    shutil.rmtree(t.reviews_dir)
    t.reviews_dir.symlink_to(t.tmp / f"missing-{SENTINEL}")


def _only_unrelated_files(t):
    t.round_path(2).unlink()
    for name in ("round0.yaml", "round01.yaml", "round2.yml", "round2.yaml.bak", "notes.yaml"):
        t.write_file(t.reviews_dir / name, "findings: []\n")


def _two_verify_steps(t):
    doc = make_workflow()
    doc["workflow"].append(dict(doc["workflow"][5]))
    t.write_workflow_text(dump_yaml(doc))


def _no_verify_step(t):
    doc = make_workflow()
    doc["workflow"] = [s for s in doc["workflow"] if s["id"] != "verify"]
    t.write_workflow_text(dump_yaml(doc))


def _workflow_not_a_list(t):
    doc = make_workflow()
    doc["workflow"] = {"verify": {"id": "verify"}}
    t.write_workflow_text(dump_yaml(doc))


def _workflow_key_absent(t):
    doc = make_workflow()
    del doc["workflow"]
    t.write_workflow_text(dump_yaml(doc))


BROKEN_INPUTS = {
    # -- mapping --
    "mapping is not JSON": ("invalid-mapping", _set_mapping_text("{not json")),
    "mapping is empty": ("invalid-mapping", _set_mapping_text("")),
    "mapping is not UTF-8": ("invalid-mapping", _set_mapping_text(b"\xff\xfe{}")),
    "mapping top level is an array": ("invalid-mapping", _set_mapping_text('["a"]')),
    "mapping top level is a string": ("invalid-mapping", _set_mapping_text('"a"')),
    "mapping top level is null": ("invalid-mapping", _set_mapping_text("null")),
    "mapping value is a string": ("invalid-mapping", _set_mapping({sid(1): "AC-1"})),
    "mapping value is an object": ("invalid-mapping", _set_mapping({sid(1): {"a": "AC-1"}})),
    "mapping value is null": ("invalid-mapping", _set_mapping({sid(1): None})),
    "mapping element is a number": ("invalid-mapping", _set_mapping({sid(1): [1]})),
    "mapping element is null": ("invalid-mapping", _set_mapping({sid(1): [None]})),
    "mapping element is an array": ("invalid-mapping", _set_mapping({sid(1): [["AC-1"]]})),
    "one bad entry among good ones": (
        "invalid-mapping",
        _set_mapping({sid(1): ["AC-1"], sid(2): [3]}),
    ),
    "mapping file is missing": ("invalid-mapping", _remove("mapping_path")),
    # -- round record --
    "round record is not YAML": ("invalid-round-record", _set_round_text("findings: [unclosed\n")),
    "round record is empty": ("invalid-round-record", _set_round_text("")),
    "round record top level is a list": ("invalid-round-record", _set_round_text("- a\n- b\n")),
    "findings value is a mapping": (
        "invalid-round-record",
        _set_round_text("round: 2\nfindings:\n  a: 1\n"),
    ),
    "findings value is a string": (
        "invalid-round-record",
        _set_round_text("round: 2\nfindings: none\n"),
    ),
    "findings value is null": ("invalid-round-record", _set_round_text("round: 2\nfindings:\n")),
    "findings key is absent": ("invalid-round-record", _set_round_text("round: 2\n")),
    "findings element is a string": (
        "invalid-round-record",
        _set_round_text("round: 2\nfindings:\n  - just text\n"),
    ),
    "findings element is a list": (
        "invalid-round-record",
        _set_round_text("round: 2\nfindings:\n  - [a, b]\n"),
    ),
    "one bad finding among good ones": (
        "invalid-round-record",
        _set_round_text(
            "round: 2\nfindings:\n"
            f"  - stable_id: {sid(1)}\n    severity: high\n    category: spec\n"
            "    resolution: deferred\n"
            "  - 3\n"
        ),
    ),
    "round record is a symbolic link": ("invalid-round-record", _make_symlinked_record),
    "round record is a directory": ("invalid-round-record", _make_directory_record),
    # -- workflow.yaml --
    "workflow.yaml is not YAML": ("invalid-workflow", _set_workflow_text("workflow: [unclosed\n")),
    "workflow.yaml is empty": ("invalid-workflow", _set_workflow_text("")),
    "workflow.yaml top level is a list": ("invalid-workflow", _set_workflow_text("- a\n- b\n")),
    "workflow.yaml is missing": ("invalid-workflow", _remove("workflow_path")),
    "workflow key is absent": ("invalid-workflow", _workflow_key_absent),
    "workflow value is not a list": ("invalid-workflow", _workflow_not_a_list),
    "no verify step": ("invalid-workflow", _no_verify_step),
    "two verify steps": ("invalid-workflow", _two_verify_steps),
    "result is an unknown word": ("invalid-workflow", _set_workflow(result="maybe")),
    "result is a number": ("invalid-workflow", _set_workflow(result=1)),
    "round is a string": ("invalid-workflow", _set_workflow(verify_round="2")),
    "round is negative": ("invalid-workflow", _set_workflow(verify_round=-1)),
    "round is a boolean": ("invalid-workflow", _set_workflow(verify_round=True)),
    "round is a float": ("invalid-workflow", _set_workflow(verify_round=2.0)),
    "round is null": ("invalid-workflow", _set_workflow(verify_round=None)),
    "passed_ids is a string": ("invalid-workflow", _set_workflow(passed_ids="AC-1")),
    "passed_ids is a mapping": ("invalid-workflow", _set_workflow(passed_ids={"AC-1": 1})),
    "passed_ids is null": ("invalid-workflow", _set_workflow(passed_ids=None, extra_verify={"passed_ids": None})),
    "passed_ids element has a space": (
        "invalid-workflow",
        _set_workflow(passed_ids=["AC-1", "bad id"]),
    ),
    "passed_ids element is empty": ("invalid-workflow", _set_workflow(passed_ids=["AC-1", ""])),
    "passed_ids element starts with a hyphen": (
        "invalid-workflow",
        _set_workflow(passed_ids=["AC-1", "-lead"]),
    ),
    "passed_ids element is 65 characters": (
        "invalid-workflow",
        _set_workflow(passed_ids=["AC-1", "x" * 65]),
    ),
    "passed_ids element is a number": ("invalid-workflow", _set_workflow(passed_ids=["AC-1", 3])),
    "passed_ids element is null": ("invalid-workflow", _set_workflow(passed_ids=["AC-1", None])),
    "passed_ids element is non-ASCII": (
        "invalid-workflow",
        _set_workflow(passed_ids=["AC-1", "é"]),
    ),
    # -- no round record --
    "reviews directory is absent": ("missing-round-record", _remove_reviews),
    "reviews is a regular file": ("missing-round-record", _make_regular_file_reviews),
    "reviews is a symbolic link to a directory outside the repository": (
        "invalid-round-record",
        _make_reviews_link_outside,
    ),
    "reviews is a dangling symbolic link": ("invalid-round-record", _make_reviews_link_dangling),
    "only unrelated files in reviews": ("missing-round-record", _only_unrelated_files),
}

BROKEN_COMMITS = {
    "too short": "abc",
    "39 characters": "a" * 39,
    "41 characters": "a" * 41,
    "63 characters": "a" * 63,
    "65 characters": "a" * 65,
    "upper case": "A" * 40,
    "not hexadecimal": "g" * 40,
    "empty": "",
    "trailing newline": "a" * 40 + "\n",
    "leading space": " " + "a" * 39,
    "a revision name": "HEAD",
}


class TestAc6StructuralErrorsWriteNothing(ResolveBase):
    """AC-6 (TS-6; SPEC AC7; TM-5)."""

    def snapshot(self):
        return self.feature_tree(), self.mapping_path.read_bytes() if self.mapping_path.exists() else None

    def test_ac6_control_the_unbroken_fixture_is_rewritten(self):
        self.build_eligible()
        before = self.read_round_bytes(2)
        summary = self.assert_ok(self.run_script())
        self.assertNotEqual(self.read_round_bytes(2), before)
        self.assertEqual(len(summary["fixed"]), 1)

    def test_ac6_each_broken_input_fails_with_its_code_and_writes_nothing(self):
        for label, (code, mutate) in BROKEN_INPUTS.items():
            with self.subTest(label):
                self.build_eligible()
                mutate(self)
                before = self.snapshot()
                self.assert_fails(self.run_script(), code)
                self.assertEqual(self.snapshot(), before)

    def test_ac6_a_malformed_verified_commit_fails_and_writes_nothing(self):
        self.build_eligible()
        for label, commit in BROKEN_COMMITS.items():
            with self.subTest(label):
                before = self.snapshot()
                self.assert_fails(self.run_script(commit=commit), "invalid-commit")
                self.assertEqual(self.snapshot(), before)

    def test_ac6_missing_or_malformed_arguments_fail_and_write_nothing(self):
        self.build_eligible()
        feature = str(self.feature_dir)
        mapping = str(self.mapping_path)
        cases = {
            "no arguments": [],
            "no feature dir": ["--mapping", mapping, "--verified-commit", COMMIT],
            "no mapping": ["--feature-dir", feature, "--verified-commit", COMMIT],
            "no verified commit": ["--feature-dir", feature, "--mapping", mapping],
            "option without a value": ["--feature-dir", feature, "--mapping", mapping, "--verified-commit"],
            "duplicate option": [
                "--feature-dir", feature, "--feature-dir", feature,
                "--mapping", mapping, "--verified-commit", COMMIT,
            ],
            "unknown option": [
                "--feature-dir", feature, "--mapping", mapping,
                "--verified-commit", COMMIT, "--force", "1",
            ],
            "positional argument": [
                "--feature-dir", feature, "--mapping", mapping,
                "--verified-commit", COMMIT, "extra",
            ],
            "empty feature dir": ["--feature-dir", "", "--mapping", mapping, "--verified-commit", COMMIT],
            "empty mapping": ["--feature-dir", feature, "--mapping", "", "--verified-commit", COMMIT],
        }
        for label, argv in cases.items():
            with self.subTest(label):
                before = self.snapshot()
                self.assert_fails(self.run_script(argv=argv), "invalid-arguments")
                self.assertEqual(self.snapshot(), before)

    def test_ac6_a_feature_directory_that_does_not_exist_fails(self):
        self.build_eligible()
        before = self.snapshot()
        proc = self.run_script(feature_dir=self.tmp / "no-such-directory")
        self.assert_fails(proc, "invalid-workflow")
        self.assertEqual(self.snapshot(), before)
        self.assertFalse((self.tmp / "no-such-directory").exists())

    @unittest.skipIf(os.geteuid() == 0, "a read-only directory does not stop root")
    def test_ac6_a_record_that_cannot_be_replaced_is_left_as_it_was(self):
        self.build_eligible()
        before = self.snapshot()
        os.chmod(self.reviews_dir, 0o555)
        self.addCleanup(os.chmod, self.reviews_dir, 0o755)
        self.assert_fails(self.run_script(), "invalid-round-record")
        self.assertEqual(self.snapshot(), before)

    def test_ac6_a_symbolic_link_record_target_is_left_alone(self):
        self.build_eligible()
        _make_symlinked_record(self)
        target = self.tmp / "elsewhere.yaml"
        target_bytes = target.read_bytes()
        self.assert_fails(self.run_script(), "invalid-round-record")
        self.assertEqual(target.read_bytes(), target_bytes)
        self.assertTrue(self.round_path(2).is_symlink())


class TestAc7UnsafeInputAndOutputDiscipline(ResolveBase):
    """AC-7 (TS-10; NFR1, NFR6; TM-4, TM-5, TM-6)."""

    TAGS = (
        "!!python/object/apply:os.mkdir",
        "!!python/object/apply:os.makedirs",
    )

    def marker(self):
        return self.tmp / "pwned"

    def tagged(self, tag):
        return f"{tag} [{json.dumps(str(self.marker()))}]"

    def test_ac7a_a_round_record_with_a_python_tag_is_refused(self):
        for tag in self.TAGS:
            with self.subTest(tag):
                self.build_eligible()
                self.write_round_text(
                    2,
                    "round: 2\nfindings:\n"
                    f"  - stable_id: {sid(1)}\n    severity: high\n    category: spec\n"
                    "    resolution: deferred\n"
                    f"    description: {self.tagged(tag)}\n",
                )
                before = self.feature_tree()
                self.assert_fails(self.run_script(), "invalid-round-record")
                self.assertEqual(self.feature_tree(), before)
                self.assertFalse(self.marker().exists(), "the tag was constructed")

    def test_ac7a_a_workflow_with_a_python_tag_is_refused(self):
        for tag in self.TAGS:
            with self.subTest(tag):
                self.build_eligible()
                doc_text = self.workflow_path.read_text(encoding="utf-8")
                self.write_workflow_text(doc_text + f"extra: {self.tagged(tag)}\n")
                before = self.feature_tree()
                self.assert_fails(self.run_script(), "invalid-workflow")
                self.assertEqual(self.feature_tree(), before)
                self.assertFalse(self.marker().exists(), "the tag was constructed")

    def test_ac7a_a_python_tag_on_a_key_the_script_reads_is_refused_too(self):
        self.build_eligible()
        self.write_round_text(
            2,
            "round: 2\nfindings:\n"
            f"  - stable_id: {sid(1)}\n    severity: high\n    category: spec\n"
            f"    resolution: !!python/name:os.system\n",
        )
        before = self.feature_tree()
        self.assert_fails(self.run_script(), "invalid-round-record")
        self.assertEqual(self.feature_tree(), before)

    def assert_no_sentinel(self, proc):
        self.assertNotIn(SENTINEL, proc.stdout)
        self.assertNotIn(SENTINEL, proc.stderr)

    def test_ac7b_a_successful_run_never_echoes_free_text(self):
        self.write_workflow(verify_round=2, passed_ids=["AC-1"])
        self.write_round(
            2,
            [
                make_finding(
                    sid(1),
                    reason=f"{SENTINEL} reason",
                    title=SENTINEL,
                    description=f"please {SENTINEL}",
                    suggestion=SENTINEL,
                    file=f"{SENTINEL}.py",
                ),
                make_finding(sid(2), reason=SENTINEL, title=SENTINEL),
            ],
        )
        self.write_mapping(
            {
                sid(1): ["AC-1"],
                sid(2): [SENTINEL],  # a mapping ID outside passed_ids
                SENTINEL: ["AC-1"],  # a mapping key that is not a stable_id
                f"{SENTINEL} x": [SENTINEL],  # a key that is not even a token
            }
        )
        proc = self.run_script()
        summary = self.assert_ok(proc)
        self.assert_no_sentinel(proc)
        self.assertEqual([entry["stable_id"] for entry in summary["fixed"]], [sid(1)])
        self.assertEqual(summary["not_applied"], 3)
        # The text really was carried over into the record: the fixture is not vacuous.
        carried = self.load_round(2)["findings"][0]["verify_resolution"]["previous_resolution_reason"]
        self.assertEqual(carried, f"{SENTINEL} reason")

    def test_ac7b_a_failing_run_never_echoes_free_text(self):
        valid_mapping = {sid(1): ["AC-1"], SENTINEL: [SENTINEL]}
        cases = {
            "commit": lambda t: dict(commit=SENTINEL),
            "unknown option": lambda t: dict(
                argv=[
                    "--feature-dir", str(t.feature_dir), "--mapping", str(t.mapping_path),
                    "--verified-commit", COMMIT, f"--{SENTINEL}", SENTINEL,
                ]
            ),
            "option value in the equals form": lambda t: dict(
                argv=[f"--{SENTINEL}={SENTINEL}", "--mapping", str(t.mapping_path)]
            ),
            "feature dir name": lambda t: dict(feature_dir=t.tmp / SENTINEL),
            "mapping name": lambda t: dict(mapping=t.tmp / SENTINEL),
        }
        for label, build in cases.items():
            with self.subTest(label):
                self.build_eligible()
                self.write_mapping(valid_mapping)
                proc = self.run_script(**build(self))
                self.assertNotEqual(proc.returncode, 0)
                self.assertEqual(proc.stdout, "")
                self.assertIn(proc.stderr.rstrip("\n"), ERROR_CODES)
                self.assert_no_sentinel(proc)

        inputs = {
            "mapping not JSON": ("mapping", f'{{"{SENTINEL}": [{SENTINEL}'),
            "mapping element not a string": ("mapping", json.dumps({SENTINEL: [SENTINEL, 1]})),
            "mapping value not an array": ("mapping", json.dumps({SENTINEL: SENTINEL})),
            "round record not YAML": ("round", f"findings: [{SENTINEL}\n"),
            "round record element not a mapping": ("round", f'findings: ["{SENTINEL}"]\n'),
            "round record findings not a list": ("round", f"findings: {SENTINEL}\n"),
            "workflow not YAML": ("workflow", f"workflow: [{SENTINEL}\n"),
            "workflow result unknown": (
                "workflow",
                dump_yaml(make_workflow(result=SENTINEL)),
            ),
            "workflow passed_ids element breaks the token format": (
                "workflow",
                dump_yaml(make_workflow(passed_ids=["AC-1", f"{SENTINEL} !"])),
            ),
            "workflow round is free text": (
                "workflow",
                dump_yaml(make_workflow(verify_round=SENTINEL)),
            ),
        }
        for label, (kind, text) in inputs.items():
            with self.subTest(label):
                self.build_eligible()
                self.write_mapping({sid(1): ["AC-1"], SENTINEL: [SENTINEL]})
                writers = {
                    "mapping": self.write_mapping_text,
                    "round": lambda data: self.write_round_text(2, data),
                    "workflow": self.write_workflow_text,
                }
                writers[kind](text)
                proc = self.run_script()
                self.assertNotEqual(proc.returncode, 0)
                self.assertEqual(proc.stdout, "")
                self.assertIn(proc.stderr.rstrip("\n"), ERROR_CODES)
                self.assert_no_sentinel(proc)

    def test_ac7c_only_the_latest_round_record_changes_and_no_file_is_added(self):
        self.write_workflow(verify_round=2, passed_ids=["AC-1"])
        self.write_round(1, [make_finding(sid(1))])
        self.write_round(2, [make_finding(sid(1)), make_finding(sid(2), category="security")])
        self.write_mapping({sid(1): ["AC-1"], sid(2): ["AC-1"]})
        self.write_file(self.feature_dir / "SPEC.md", "spec text\n")
        self.write_file(self.feature_dir / "VERIFICATION.md", "verification text\n")
        self.commit_feature()

        before = tree(self.repo, skip=(".git",))
        mapping_before = self.mapping_path.read_bytes()
        proc = self.run_script()
        self.assert_ok(proc)
        after = tree(self.repo, skip=(".git",))

        self.assertEqual(set(after), set(before), "a file was added or removed")
        changed = sorted(path for path in before if before[path] != after[path])
        self.assertEqual(changed, [f"feature-docs/{FEATURE}/reviews/round2.yaml"])
        self.assertEqual(self.mapping_path.read_bytes(), mapping_before)
        self.assertEqual(self.git("status", "--porcelain"), f"M feature-docs/{FEATURE}/reviews/round2.yaml")
        leftovers = [p.name for p in self.reviews_dir.iterdir()]
        self.assertEqual(sorted(leftovers), ["round1.yaml", "round2.yaml"])


class TestAc8PreflightIsUnchanged(ResolveBase):
    """AC-8 (TS-8, TS-12; SPEC AC10; FR11, NFR3).

    The change-set half of the criterion (neither merge-preflight.py nor
    tests/test_merge_preflight.py is touched) is checked with git diff against
    the base commit by the task's verification, not inside the suite: a test
    that diffs against a moving base would fail for unrelated later changes.
    What this class pins is the property the unchanged preflight must keep:
    it reads only `resolution`, so a deferred critical/high finding blocks it
    until the script has rewritten that finding, and a deferred non-blocking
    one never blocks it.
    """

    def test_ac8_a_deferred_blocking_finding_stops_the_unchanged_preflight(self):
        self.write_workflow(verify_round=2, passed_ids=["AC-1"])
        self.write_round(1, [make_finding(sid(1))])
        self.commit_feature()
        result = self.preflight()
        self.assertEqual(result["reason"], "unresolved_findings", result)

    def test_ac8_a_deferred_medium_finding_does_not_stop_the_preflight(self):
        self.write_workflow(verify_round=2, passed_ids=["AC-1"])
        self.write_round(1, [make_finding(sid(1), severity="medium")])
        self.commit_feature()
        result = self.preflight()
        self.assertEqual(result["outcome"], "proceed", result)



# -- links at the feature directory, `reviews` and the round record ----------------
#
# Covers AC-1..AC-9 of
# feature-docs/resolve-findings-parent-symlink/tasks/task0001.md.

CURRENT = "current"

# The child program of the race tests. It runs with the running interpreter in
# no-bytecode mode: it installs one wrapper, sets the script's arguments as its
# command line and runs the script file as the main module. The wrapper swaps
# exactly once, at a fixed call (never by load, loops or sleeps), and then calls
# the original. Nothing is written to stdout or stderr here, so the script's own
# output stays the only output of the run.
RACE_CHILD = r"""
import builtins, json, os, runpy, sys

spec = json.loads(sys.argv[1])
state = {"fired": False}

if spec["mode"] == "serializer":
    import yaml

    original_dump = yaml.safe_dump

    def dump_wrapper(*args, **kwargs):
        if not state["fired"]:
            state["fired"] = True
            os.rename(spec["current_reviews"], spec["aside"])
            os.symlink(spec["other_reviews"], spec["current_reviews"])
        return original_dump(*args, **kwargs)

    yaml.safe_dump = dump_wrapper
else:
    original_os_open = os.open
    original_open = builtins.open

    def swap_if_record(path):
        if state["fired"] or not isinstance(path, (str, bytes, os.PathLike)):
            return
        if os.path.basename(os.fsdecode(path)) != spec["record_name"]:
            return
        state["fired"] = True
        os.rename(spec["record"], spec["aside"])
        if spec["mode"] == "record-to-link":
            os.symlink(spec["other_record"], spec["record"])
        else:
            os.mkfifo(spec["record"])

    def os_open_wrapper(path, flags, *args, **kwargs):
        swap_if_record(path)
        return original_os_open(path, flags, *args, **kwargs)

    def open_wrapper(file, *args, **kwargs):
        swap_if_record(file)
        return original_open(file, *args, **kwargs)

    os.open = os_open_wrapper
    builtins.open = open_wrapper

script = spec["script"]
sys.argv = [script] + spec["argv"]
runpy.run_path(script, run_name="__main__")
"""

# A run takes a fraction of a second; this is only the bound after which a
# script that waits (for a FIFO writer) counts as failed.
CHILD_TIMEOUT = 30


def assert_clean_failure(test, proc, code):
    """`assert_fails`, and the sentinel string appears nowhere in the output."""
    test.assert_fails(proc, code)
    test.assertNotIn(SENTINEL, proc.stdout)
    test.assertNotIn(SENTINEL, proc.stderr)


def leftover_temporaries(directory):
    return [name for name in os.listdir(directory) if name.startswith(".resolve-")]


class LinkBase(ResolveBase):
    """Two features in one fixture.

    `demo` (the default feature of ResolveBase) is the victim, "other": the
    existing preflight helper checks it unchanged. `current` is the feature the
    script is pointed at.
    """

    def setUp(self):
        super().setUp()
        self.other_dir = self.feature_dir
        self.other_reviews = self.other_dir / "reviews"
        self.current_dir = self.repo / "feature-docs" / CURRENT
        self.current_reviews = self.current_dir / "reviews"
        self.outside_dir = self.tmp / f"outside-{SENTINEL}"

    def build_other(self, round_number=2):
        """The victim: a valid workflow.yaml and one eligible deferred finding."""
        self.write_workflow(verify_round=2, passed_ids=["AC-1"])
        self.write_round(round_number, [make_finding(sid(1))])
        self.write_mapping({sid(1): ["AC-1"]})

    def write_current_workflow(self):
        self.write_file(
            self.current_dir / "workflow.yaml",
            dump_yaml(make_workflow(verify_round=2, passed_ids=["AC-1"])),
        )

    def write_current_round(self, n=2):
        self.write_file(
            self.current_reviews / f"round{n}.yaml",
            ROUND_COMMENT + dump_yaml(make_round(n, [make_finding(sid(1))])),
        )

    def build_current(self):
        """A real `current` feature with its own eligible round record."""
        self.write_current_workflow()
        self.write_current_round()

    def current_arg(self, suffix=""):
        return str(self.current_dir) + suffix

    def run_child(self, spec, timeout=CHILD_TIMEOUT):
        spec = dict(
            spec,
            script=str(SCRIPT),
            argv=[
                "--feature-dir",
                self.current_arg(),
                "--mapping",
                str(self.mapping_path),
                "--verified-commit",
                COMMIT,
            ],
        )
        try:
            return subprocess.run(
                [sys.executable, "-B", "-c", RACE_CHILD, json.dumps(spec)],
                cwd=str(self.tmp),
                env=self.env,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            self.fail(f"the script waited for more than {timeout} seconds")


class TestAc1FeatureDirectoryLink(LinkBase):
    """AC-1 (TS-3, TS-8; FR2, FR7; TM-2)."""

    def setUp(self):
        super().setUp()
        self.build_other()
        os.symlink(FEATURE, self.current_dir)  # feature-docs/current -> demo

    def test_ac1_a_link_as_the_final_element_is_refused_with_every_trailing_spelling(self):
        for label, suffix in (("plain", ""), ("one slash", "/"), ("two slashes", "//")):
            with self.subTest(label):
                before = self.feature_tree()
                proc = self.run_script(feature_dir=self.current_arg(suffix))
                assert_clean_failure(self, proc, "invalid-workflow")
                self.assertEqual(self.feature_tree(), before)

    def test_ac1_the_refusal_comes_before_workflow_yaml_and_the_mapping_are_read(self):
        # With workflow.yaml read first, the broken mapping would be reported instead.
        self.write_mapping_text("{not json")
        before = self.feature_tree()
        proc = self.run_script(feature_dir=self.current_arg())
        assert_clean_failure(self, proc, "invalid-workflow")
        self.assertEqual(self.feature_tree(), before)

    def test_ac1_a_link_whose_name_and_target_carry_the_sentinel_is_not_echoed(self):
        target = self.tmp / f"target-{SENTINEL}"
        shutil.copytree(self.other_dir, target, symlinks=True)
        named = self.repo / "feature-docs" / f"link-{SENTINEL}"
        os.symlink(target, named)
        before = tree(target)
        proc = self.run_script(feature_dir=str(named) + "/")
        assert_clean_failure(self, proc, "invalid-workflow")
        self.assertEqual(tree(target), before)


class TestAc2ReviewsLink(LinkBase):
    """AC-2 (TS-1, TS-2; FR1; TM-1)."""

    def setUp(self):
        super().setUp()
        self.write_current_workflow()

    def test_ac2_a_link_to_another_features_reviews_is_refused_and_preflight_still_stops(self):
        self.build_other(round_number=1)
        os.symlink(os.path.join("..", FEATURE, "reviews"), self.current_reviews)
        self.commit_feature()
        stopped = self.preflight()
        self.assertEqual(stopped["reason"], "unresolved_findings", stopped)

        other_before = self.feature_tree()
        current_before = tree(self.current_dir)
        proc = self.run_script(feature_dir=self.current_arg())
        assert_clean_failure(self, proc, "invalid-round-record")
        self.assertEqual(self.feature_tree(), other_before)
        self.assertEqual(tree(self.current_dir), current_before)

        # The orchestrator commits whatever the script left on disk. A run that
        # had rewritten the other feature's record would let the preflight through.
        self.git("add", "-A")
        self.git("commit", "-q", "--allow-empty", "-m", "after the script")
        after = self.preflight()
        self.assertEqual(after["outcome"], "stop", after)
        self.assertEqual(after["reason"], "unresolved_findings", after)
        self.assertIn(sid(1), after["detail"])

    def test_ac2_a_link_to_a_directory_outside_the_repository_is_refused(self):
        self.build_other()
        for n in (1, 2):
            self.write_file(
                self.outside_dir / f"round{n}.yaml",
                ROUND_COMMENT + dump_yaml(make_round(n, [make_finding(sid(1))])),
            )
        os.symlink(self.outside_dir, self.current_reviews)
        feature_before = tree(self.current_dir)
        outside_before = tree(self.outside_dir)
        proc = self.run_script(feature_dir=self.current_arg())
        assert_clean_failure(self, proc, "invalid-round-record")
        self.assertEqual(tree(self.current_dir), feature_before)
        self.assertEqual(tree(self.outside_dir), outside_before)

    def test_ac2_a_dangling_link_is_refused(self):
        self.build_other()
        missing = self.tmp / f"missing-{SENTINEL}"
        os.symlink(missing, self.current_reviews)
        before = tree(self.current_dir)
        proc = self.run_script(feature_dir=self.current_arg())
        assert_clean_failure(self, proc, "invalid-round-record")
        self.assertEqual(tree(self.current_dir), before)
        self.assertFalse(os.path.lexists(missing), "the link target was created")

    def test_ac2_a_link_to_a_regular_file_is_refused_as_a_link_not_as_a_missing_record(self):
        self.build_other()
        target = self.tmp / f"file-{SENTINEL}"
        target.write_text("not a directory\n", encoding="utf-8")
        os.symlink(target, self.current_reviews)
        before = tree(self.current_dir)
        proc = self.run_script(feature_dir=self.current_arg())
        assert_clean_failure(self, proc, "invalid-round-record")
        self.assertEqual(tree(self.current_dir), before)
        self.assertEqual(target.read_text(encoding="utf-8"), "not a directory\n")

    def test_ac2_a_link_at_reviews_still_gives_way_to_the_earlier_checks(self):
        # The mapping and workflow.yaml are read before `reviews` is opened.
        self.build_other()
        os.symlink(os.path.join("..", FEATURE, "reviews"), self.current_reviews)
        self.write_mapping_text("{not json")
        assert_clean_failure(self, self.run_script(feature_dir=self.current_arg()), "invalid-mapping")
        self.write_mapping({sid(1): ["AC-1"]})
        (self.current_dir / "workflow.yaml").write_text("workflow: [unclosed\n", encoding="utf-8")
        assert_clean_failure(self, self.run_script(feature_dir=self.current_arg()), "invalid-workflow")


class TestAc3ReviewsSwappedBeforeTheWrite(LinkBase):
    """AC-3 (TS-4; FR3; TM-3)."""

    def setUp(self):
        super().setUp()
        self.build_other()  # the victim's round2.yaml has the name the script writes
        self.build_current()
        self.aside = self.current_dir / "reviews-moved-aside"

    def test_ac3_a_swap_at_the_serializer_never_reaches_the_other_features_reviews(self):
        other_before = self.feature_tree()
        proc = self.run_child(
            {
                "mode": "serializer",
                "current_reviews": str(self.current_reviews),
                "aside": str(self.aside),
                "other_reviews": str(self.other_reviews),
            }
        )

        # The wrapper really swapped; the exit status of the run is not fixed.
        self.assertTrue(os.path.islink(self.current_reviews), "the wrapper did not swap `reviews`")
        self.assertTrue(self.aside.is_dir())
        self.assertEqual(self.feature_tree(), other_before)
        self.assertEqual(leftover_temporaries(self.other_reviews), [])
        self.assertEqual(leftover_temporaries(self.aside), [])
        self.assertNotIn(SENTINEL, proc.stdout + proc.stderr)

    def test_ac3_control_the_same_run_without_a_swap_rewrites_the_current_record(self):
        summary = self.assert_ok(self.run_script(feature_dir=self.current_arg()))
        self.assertEqual(len(summary["fixed"]), 1)
        record = parse_yaml((self.current_reviews / "round2.yaml").read_text(encoding="utf-8"))
        self.assertEqual(record["findings"][0]["resolution"], "fixed")


class TestAc4RecordSwappedBeforeTheOpen(LinkBase):
    """AC-4 (TS-10; FR8; TM-4)."""

    def setUp(self):
        super().setUp()
        self.build_other()
        self.build_current()
        self.record = self.current_reviews / "round2.yaml"
        self.aside = self.current_reviews / "record-moved-aside"

    def test_ac4_a_record_swapped_for_a_link_after_the_check_is_refused(self):
        other_before = self.feature_tree()
        proc = self.run_child(
            {
                "mode": "record-to-link",
                "record_name": "round2.yaml",
                "record": str(self.record),
                "aside": str(self.aside),
                "other_record": str(self.round_path(2)),
            }
        )
        self.assertTrue(self.aside.is_file(), "the wrapper did not swap the record")
        assert_clean_failure(self, proc, "invalid-round-record")
        self.assertEqual(self.feature_tree(), other_before)
        self.assertEqual(leftover_temporaries(self.current_reviews), [])


class TestAc5FifoRecord(LinkBase):
    """AC-5 (TS-11; FR8; TM-5)."""

    def setUp(self):
        super().setUp()
        self.build_other()
        self.build_current()
        self.record = self.current_reviews / "round2.yaml"

    def test_ac5_a_fifo_record_fails_without_waiting_for_a_writer(self):
        os.unlink(self.record)
        os.mkfifo(self.record)
        before = tree(self.current_dir)
        self.assertEqual(before["reviews/round2.yaml"][0], "special")
        try:
            proc = self.run_script(feature_dir=self.current_arg(), timeout=CHILD_TIMEOUT)
        except subprocess.TimeoutExpired:
            self.fail("the script waited for a writer on the FIFO")
        assert_clean_failure(self, proc, "invalid-round-record")
        self.assertEqual(tree(self.current_dir), before)

    def test_ac5_a_record_swapped_for_a_fifo_after_the_check_fails_without_waiting(self):
        proc = self.run_child(
            {
                "mode": "record-to-fifo",
                "record_name": "round2.yaml",
                "record": str(self.record),
                "aside": str(self.current_reviews / "record-moved-aside"),
            }
        )
        self.assertTrue(stat.S_ISFIFO(os.lstat(self.record).st_mode), "the wrapper did not swap the record")
        assert_clean_failure(self, proc, "invalid-round-record")
        self.assertEqual(leftover_temporaries(self.current_reviews), [])


class TestAc6LegitimatePathsAreStillRewritten(LinkBase):
    """AC-6 (TS-5, TS-9; FR5, FR7)."""

    def finding_after(self):
        record = parse_yaml(self.round_path(2).read_text(encoding="utf-8"))
        self.assertEqual(len(record["findings"]), 1)
        return record["findings"][0]

    def test_ac6_a_link_among_the_ancestors_is_not_checked(self):
        self.build_eligible()
        alias = self.tmp / "alias-of-the-repository"
        os.symlink(self.repo, alias)
        proc = self.run_script(feature_dir=str(alias / "feature-docs" / FEATURE))
        self.assertEqual(len(self.assert_ok(proc)["fixed"]), 1)
        self.assertEqual(self.finding_after()["resolution"], "fixed")

    def test_ac6_a_link_followed_by_dot_names_dot_as_the_final_element(self):
        self.build_eligible()
        os.symlink(FEATURE, self.current_dir)  # feature-docs/current -> demo
        proc = self.run_script(feature_dir=self.current_arg("/."))
        self.assertEqual(len(self.assert_ok(proc)["fixed"]), 1)
        self.assertEqual(self.finding_after()["resolution"], "fixed")

    def test_ac6_trailing_separators_on_a_real_directory_give_the_result_of_the_plain_path(self):
        summaries = {}
        for label, suffix in (("plain", ""), ("one slash", "/"), ("two slashes", "//")):
            with self.subTest(label):
                self.build_eligible()
                proc = self.run_script(feature_dir=str(self.feature_dir) + suffix)
                summaries[label] = self.assert_ok(proc)
                self.assertEqual(len(summaries[label]["fixed"]), 1)
                self.assertEqual(self.finding_after()["resolution"], "fixed")
        self.assertEqual(summaries["one slash"], summaries["plain"])
        self.assertEqual(summaries["two slashes"], summaries["plain"])

    def test_ac6_the_equals_form_accepts_a_trailing_separator_too(self):
        self.build_eligible()
        proc = self.run_script(
            argv=[
                f"--feature-dir={self.feature_dir}/",
                f"--mapping={self.mapping_path}",
                f"--verified-commit={COMMIT}",
            ]
        )
        self.assertEqual(len(self.assert_ok(proc)["fixed"]), 1)


class TestAc7UnchangedContract(ResolveBase):
    """AC-7 (FR4, NFR4; TM-6): behaviour that must not move."""

    def test_ac7_reviews_that_is_a_regular_file_is_a_missing_record(self):
        self.build_eligible()
        shutil.rmtree(self.reviews_dir)
        self.reviews_dir.write_text("not a directory\n", encoding="utf-8")
        before = self.feature_tree()
        assert_clean_failure(self, self.run_script(), "missing-round-record")
        self.assertEqual(self.feature_tree(), before)

    @unittest.skipIf(os.geteuid() == 0, "a mode-0 directory does not stop root")
    def test_ac7_reviews_that_cannot_be_opened_is_a_missing_record(self):
        self.build_eligible()
        os.chmod(self.reviews_dir, 0)
        self.addCleanup(os.chmod, self.reviews_dir, 0o755)
        assert_clean_failure(self, self.run_script(), "missing-round-record")

    def test_ac7_a_feature_directory_that_is_a_regular_file_fails_with_invalid_workflow(self):
        self.build_eligible()
        plain = self.tmp / "not-a-directory"
        plain.write_text("x\n", encoding="utf-8")
        assert_clean_failure(self, self.run_script(feature_dir=str(plain)), "invalid-workflow")
        assert_clean_failure(self, self.run_script(feature_dir=str(plain) + "/"), "invalid-workflow")

    def test_ac7_a_link_at_workflow_yaml_itself_is_still_followed(self):
        self.build_eligible()
        elsewhere = self.tmp / "workflow-elsewhere.yaml"
        elsewhere.write_bytes(self.workflow_path.read_bytes())
        self.workflow_path.unlink()
        os.symlink(elsewhere, self.workflow_path)
        self.assertEqual(len(self.assert_ok(self.run_script())["fixed"]), 1)
        self.assertTrue(self.workflow_path.is_symlink())

    def test_ac7_the_record_keeps_its_mode_and_no_temporary_file_is_left(self):
        self.build_eligible()
        os.chmod(self.round_path(2), 0o600)
        self.assert_ok(self.run_script(feature_dir=str(self.feature_dir) + "/"))
        self.assertEqual(os.stat(self.round_path(2)).st_mode & 0o777, 0o600)
        self.assertEqual(sorted(os.listdir(self.reviews_dir)), ["round2.yaml"])


def imported_modules(path):
    modules = set()
    for node in ast.walk(ast.parse(Path(path).read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            modules.add(node.module.split(".")[0])
    return modules


class TestAc8Docstring(unittest.TestCase):
    """AC-8 (FR6): the Boundaries section of the module docstring."""

    def boundaries(self):
        docstring = ast.get_docstring(ast.parse(SCRIPT.read_text(encoding="utf-8")))
        self.assertIn("Boundaries:", docstring)
        return " ".join(docstring.split("Boundaries:", 1)[1].split())

    def test_ac8_the_three_refused_links_and_their_codes_are_named(self):
        section = self.boundaries()
        self.assertIn("symbolic link", section)
        self.assertRegex(section, r"symbolic link[^;]*--feature-dir[^;]*one or more[^;]*invalid-workflow")
        self.assertRegex(section, r";[^;]*`reviews`[^;]*invalid-round-record")
        self.assertRegex(section, r";[^;]*round record[^;]*invalid-round-record")

    def test_ac8_every_read_and_write_is_stated_to_be_relative_to_the_directory_handle(self):
        self.assertRegex(self.boundaries(), r"relative to (that|the) directory handle")


class TestAc9Constraints(unittest.TestCase):
    """AC-9 (NFR1, NFR3, NFR5): what a test can pin about the change itself.

    The races above are triggered from wrapper hooks at fixed calls, with no
    load, loops or sleeps. That neither SKILL.md, merge-preflight.py nor
    tests/test_merge_preflight.py changed is a diff against the base commit made
    during verification, not a test in the suite.
    """

    def stdlib(self):
        names = getattr(sys, "stdlib_module_names", None)
        if names is None:
            self.skipTest("sys.stdlib_module_names is not available")
        return set(names)

    def test_ac9_the_script_imports_the_standard_library_and_pyyaml_only(self):
        self.assertEqual(imported_modules(SCRIPT) - self.stdlib(), {"yaml"})

    def test_ac9_this_module_imports_the_standard_library_only(self):
        self.assertEqual(imported_modules(__file__) - self.stdlib(), set())


if __name__ == "__main__":
    unittest.main()
