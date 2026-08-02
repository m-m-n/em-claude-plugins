"""Tests for task0008: em-workflow/scripts/validate-worker-output.py and its
fixture corpus (em-workflow/references/fixtures/).

Covers task0008 Acceptance Criteria (feature-docs/agent-separation/
tasks/task0008.md):

- AC-1: TestCLIInterface -- five --kind values, mandatory --worker/--input,
  every auxiliary argument from design-input.md 5.11.1; unknown --kind is an
  execution error.
- AC-2: TestExitCodes -- 0 / 1 (JSON on stdout) / 2, and the PyYAML-missing
  message.
- AC-3: TestInputEnvelopeMandatoryForWorkerResult -- omitting
  --input-envelope with --kind worker-result exits 2 for every worker.
- AC-4: TestModeEchoAndAnalystModeExclusivity -- mode_echo missing/mismatch,
  and design_system_detection payload containing full-mode-only keys.
- AC-5: TestDryRunApplyRejections -- stale digest/blob anchor, expected
  mismatch, duplicate patch identifier, replace_all after implementation
  started, append_rework missing the mandatory preserve path.
- AC-6: TestFixtureCoverageValidAndInvalidPerBranch -- every branch group has
  at least one valid and one invalid fixture, including the two analyst
  modes separately.
- AC-7: TestFixtureCorpusDataDriven -- every fixture under
  em-workflow/references/fixtures/ is run and asserted against the exit
  code its directory name (valid-/invalid-) declares.

TestFixtureBranchesDerivedFromDesignInput is the Test Notes' coverage test:
it parses the branch table from design-input.md 5.11.5 (and, for
phase-state, the reconcile table in 5.6.3 that row points at) rather than
hardcoding the expected vocabulary, so a branch added to the design later
has no fixture until one is added (NFR6 applies to tests too; mirrors the
pattern in test_workflow_patch_doc.py).

Edge cases (Test Notes): a task-plan Files bullet with zero/two
backtick-quoted paths (fixtures under worker-result/implementation-planner);
a symlink-valued written_artifacts path (TestSymlinkedWrittenArtifact, built
at test time -- not committed as a fixture, see that class's docstring); an
extend_only target whose YAML contains an alias or merge key
(TestExtendOnlyComparability, direct unit test of the pure helper --
see that function's docstring in the script for why it is not wired to a
--kind path).
"""

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
DESIGN_INPUT_PATH = REPO_ROOT / "feature-docs" / "agent-separation" / "design-input.md"


def _load_module():
    spec = importlib.util.spec_from_file_location("validate_worker_output", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VWO = _load_module()


def run_cli(args, env=None):
    cmd = [sys.executable, str(SCRIPT_PATH)] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True, env=env)


def _companion(case_dir, stem):
    for ext in (".json", ".yaml", ".yml"):
        p = case_dir / f"{stem}{ext}"
        if p.is_file():
            return p
    return None


# Fixture directory group -> --worker value, for kinds whose CLI worker
# argument matters (worker-result). Other kinds pass a fixed, arbitrary
# valid worker name since --worker is mandatory but not cross-checked there.
WORKER_FOR_GROUP = {
    "requirements-analyst-full": "requirements-analyst",
    "requirements-analyst-design-system-detection": "requirements-analyst",
    "spec-writer": "spec-writer",
    "implementation-planner": "implementation-planner",
    "rework-planner": "rework-planner",
    "designer": "designer",
}


def build_case_args(kind, group, case_dir):
    """Builds the CLI argv for one fixture case directory, wiring every
    companion file/dir present by its fixed role name (see the fixtures
    directory docstring-equivalent in this module: input/envelope/packet/
    answers/workflow/digest-source/phase-state/registries/feature-dir/
    baseline-dir/DRY_RUN_APPLY)."""
    input_path = _companion(case_dir, "input")
    assert input_path is not None, f"{case_dir} has no input.* file"
    worker = WORKER_FOR_GROUP.get(group, "implementation-planner")
    args = ["--kind", kind, "--worker", worker, "--input", str(input_path)]

    for flag, stem in (
        ("--input-envelope", "envelope"),
        ("--packet", "packet"),
        ("--answers", "answers"),
        ("--workflow", "workflow"),
        ("--digest-source", "digest-source"),
        ("--phase-state", "phase-state"),
    ):
        companion = _companion(case_dir, stem)
        if companion is not None:
            args += [flag, str(companion)]

    for flag, dirname in (
        ("--registries", "registries"),
        ("--feature-dir", "feature-dir"),
        ("--baseline-dir", "baseline-dir"),
    ):
        d = case_dir / dirname
        if d.is_dir():
            args += [flag, str(d)]

    if (case_dir / "DRY_RUN_APPLY").exists():
        args.append("--dry-run-apply")

    return args


def discover_fixture_cases():
    """Yields (kind, group, case_dir) for every leaf fixture case directory
    under em-workflow/references/fixtures/. No manifest file is read -- the
    kind/group/outcome are the directory names themselves (Design section:
    "Fixture files carry enough naming structure ... without a separate
    manifest")."""
    if not FIXTURES_ROOT.is_dir():
        return
    for kind_dir in sorted(FIXTURES_ROOT.iterdir()):
        if not kind_dir.is_dir():
            continue
        for group_dir in sorted(kind_dir.iterdir()):
            if not group_dir.is_dir():
                continue
            for case_dir in sorted(group_dir.iterdir()):
                if not case_dir.is_dir():
                    continue
                yield kind_dir.name, group_dir.name, case_dir


def expected_exit_code(case_dir):
    name = case_dir.name
    if name.startswith("valid-"):
        return 0
    if name.startswith("invalid-"):
        return 1
    raise AssertionError(f"fixture case dir {case_dir} must start with valid- or invalid-")


# ---------------------------------------------------------------------------
# AC-1
# ---------------------------------------------------------------------------

class TestCLIInterface(unittest.TestCase):
    def test_all_five_kind_values_are_declared(self):
        parser = VWO.build_arg_parser()
        kind_action = next(a for a in parser._actions if a.dest == "kind")
        self.assertEqual(set(kind_action.choices), set(VWO.KINDS))
        self.assertEqual(len(VWO.KINDS), 5)

    def test_worker_and_input_are_mandatory(self):
        parser = VWO.build_arg_parser()
        required_dests = {a.dest for a in parser._actions if getattr(a, "required", False)}
        self.assertIn("worker", required_dests)
        self.assertIn("input", required_dests)

    def test_all_auxiliary_arguments_declared(self):
        parser = VWO.build_arg_parser()
        dests = {a.dest for a in parser._actions}
        for expected in (
            "packet",
            "answers",
            "workflow",
            "registries",
            "phase_state",
            "input_envelope",
            "digest_source",
            "feature_dir",
            "baseline_dir",
            "dry_run_apply",
        ):
            self.assertIn(expected, dests, f"missing auxiliary argument {expected!r}")

    def test_unknown_kind_is_an_execution_error(self):
        result = run_cli(["--kind", "not-a-real-kind", "--worker", "designer", "--input", "/nonexistent"])
        self.assertEqual(result.returncode, 2)

    def test_unknown_worker_is_an_execution_error(self):
        result = run_cli(["--kind", "phase-state", "--worker", "not-a-real-worker", "--input", "/nonexistent"])
        self.assertEqual(result.returncode, 2)


# ---------------------------------------------------------------------------
# AC-2
# ---------------------------------------------------------------------------

class TestExitCodes(unittest.TestCase):
    def test_valid_input_exits_0(self):
        case_dir = FIXTURES_ROOT / "worker-result" / "designer" / "valid-completed"
        result = run_cli(build_case_args("worker-result", "designer", case_dir))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "")

    def test_validation_failure_exits_1_with_json_detail_on_stdout(self):
        case_dir = FIXTURES_ROOT / "worker-result" / "spec-writer" / "invalid-missing-payload"
        result = run_cli(build_case_args("worker-result", "spec-writer", case_dir))
        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        self.assertIn("errors", payload)
        self.assertTrue(payload["errors"])

    def test_pyyaml_missing_exits_2_naming_pyyaml(self):
        with tempfile.TemporaryDirectory() as stub_dir:
            stub_path = Path(stub_dir) / "yaml.py"
            stub_path.write_text("raise ImportError(\"No module named 'yaml'\")\n", encoding="utf-8")
            env = dict(os.environ)
            env["PYTHONPATH"] = stub_dir + os.pathsep + env.get("PYTHONPATH", "")
            result = run_cli(
                ["--kind", "phase-state", "--worker", "designer", "--input", "/nonexistent"], env=env
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("PyYAML", result.stderr)


# ---------------------------------------------------------------------------
# AC-3
# ---------------------------------------------------------------------------

class TestInputEnvelopeMandatoryForWorkerResult(unittest.TestCase):
    def test_missing_input_envelope_exits_2_for_every_worker(self):
        for worker in VWO.WORKERS:
            with self.subTest(worker=worker):
                result = run_cli(
                    ["--kind", "worker-result", "--worker", worker, "--input", "/nonexistent"]
                )
                self.assertEqual(result.returncode, 2)
                self.assertIn("input-envelope", result.stderr)


# ---------------------------------------------------------------------------
# AC-4
# ---------------------------------------------------------------------------

class TestModeEchoAndAnalystModeExclusivity(unittest.TestCase):
    def _run(self, group, case_name):
        case_dir = FIXTURES_ROOT / "worker-result" / group / case_name
        return run_cli(build_case_args("worker-result", group, case_dir))

    def test_missing_mode_echo_fails_validation(self):
        result = self._run("requirements-analyst-full", "invalid-mode-echo-missing")
        self.assertEqual(result.returncode, 1)
        self.assertIn("mode_echo", result.stdout)

    def test_mismatched_mode_echo_fails_validation(self):
        result = self._run("requirements-analyst-full", "invalid-mode-echo-mismatch")
        self.assertEqual(result.returncode, 1)
        self.assertIn("mode_echo", result.stdout)

    def test_design_system_detection_with_full_mode_payload_keys_fails_validation(self):
        result = self._run("requirements-analyst-design-system-detection", "invalid-full-mode-payload-keys")
        self.assertEqual(result.returncode, 1)
        payload = json.loads(result.stdout)
        messages = " ".join(e["message"] for e in payload["errors"])
        self.assertIn("resolved_requirements", messages)

    def test_valid_full_mode_completed_passes(self):
        result = self._run("requirements-analyst-full", "valid-completed")
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_valid_design_system_detection_completed_passes(self):
        result = self._run("requirements-analyst-design-system-detection", "valid-completed")
        self.assertEqual(result.returncode, 0, result.stdout)


# ---------------------------------------------------------------------------
# AC-5
# ---------------------------------------------------------------------------

class TestDryRunApplyRejections(unittest.TestCase):
    """Test Notes: the dry-run application needs a workflow.yaml to apply
    against; each of these fixtures carries a small synthetic workflow.json
    built in em-workflow/references/fixtures/ rather than depending on this
    feature's own workflow.yaml."""

    def _run(self, group, case_name):
        case_dir = FIXTURES_ROOT / "workflow-patch" / group / case_name
        return run_cli(build_case_args("workflow-patch", group, case_dir))

    def test_stale_input_digest_rejected(self):
        result = self._run("replace_planning", "invalid-stale-input-digest")
        self.assertEqual(result.returncode, 1)
        self.assertIn("stale", result.stdout.lower())

    def test_stale_workflow_blob_rejected(self):
        result = self._run("replace_planning", "invalid-stale-workflow-blob")
        self.assertEqual(result.returncode, 1)
        self.assertIn("stale", result.stdout.lower())

    def test_expected_mismatch_rejected(self):
        result = self._run("append_rework", "invalid-expected-status-mismatch")
        self.assertEqual(result.returncode, 1)
        self.assertIn("expected", result.stdout.lower())

    def test_duplicate_patch_id_with_differing_content_rejected(self):
        result = self._run("replace_planning", "invalid-duplicate-patch-id-differing-content")
        self.assertEqual(result.returncode, 1)
        self.assertIn("duplicate", result.stdout.lower())

    def test_replace_all_after_implementation_started_rejected(self):
        result = self._run("replace_planning", "invalid-replace-all-after-implementation-started")
        self.assertEqual(result.returncode, 1)
        self.assertIn("replace_all", result.stdout)

    def test_append_rework_missing_mandatory_preserve_path_rejected(self):
        result = self._run("append_rework", "invalid-missing-base-commit-preserve")
        self.assertEqual(result.returncode, 1)
        self.assertIn("workflow.implement.base_commit", result.stdout)

    def test_valid_dry_run_apply_passes_for_both_operations(self):
        for group, case in (
            ("replace_planning", "valid-dry-run-apply"),
            ("append_rework", "valid-dry-run-apply"),
        ):
            with self.subTest(group=group):
                result = self._run(group, case)
                self.assertEqual(result.returncode, 0, result.stdout)


# ---------------------------------------------------------------------------
# AC-6
# ---------------------------------------------------------------------------

class TestFixtureCoverageValidAndInvalidPerBranch(unittest.TestCase):
    """Every branch-group directory under references/fixtures/<kind>/ must
    contain at least one valid-* and one invalid-* case directory."""

    def test_every_group_has_a_valid_and_an_invalid_case(self):
        groups = {}
        for kind, group, case_dir in discover_fixture_cases():
            groups.setdefault((kind, group), set()).add(
                "valid" if case_dir.name.startswith("valid-") else "invalid"
            )
        self.assertTrue(groups, "expected at least one fixture group to exist")
        for (kind, group), outcomes in sorted(groups.items()):
            with self.subTest(kind=kind, group=group):
                self.assertIn("valid", outcomes, f"{kind}/{group} has no valid-* fixture")
                self.assertIn("invalid", outcomes, f"{kind}/{group} has no invalid-* fixture")

    def test_the_two_analyst_modes_are_covered_separately(self):
        worker_result_groups = {
            group for kind, group, _ in discover_fixture_cases() if kind == "worker-result"
        }
        self.assertIn("requirements-analyst-full", worker_result_groups)
        self.assertIn("requirements-analyst-design-system-detection", worker_result_groups)


# ---------------------------------------------------------------------------
# AC-7 + data-driven fixture corpus runner
# ---------------------------------------------------------------------------

class TestFixtureCorpusDataDriven(unittest.TestCase):
    def test_every_fixture_matches_its_declared_exit_code(self):
        cases = list(discover_fixture_cases())
        self.assertTrue(cases, "expected the fixture corpus to be non-empty")
        for kind, group, case_dir in cases:
            with self.subTest(kind=kind, group=group, case=case_dir.name):
                expected = expected_exit_code(case_dir)
                args = build_case_args(kind, group, case_dir)
                result = run_cli(args)
                self.assertEqual(
                    result.returncode,
                    expected,
                    f"{case_dir}: expected exit {expected}, got {result.returncode}\n"
                    f"stdout: {result.stdout}\nstderr: {result.stderr}",
                )


# ---------------------------------------------------------------------------
# Test Notes: coverage test derived from design-input.md, not hardcoded
# ---------------------------------------------------------------------------

def _read(path):
    return path.read_text(encoding="utf-8")


def _extract_section(text, start_heading, end_heading):
    start = text.index(start_heading)
    end = text.index(end_heading, start)
    return text[start:end]


def _normalize(token):
    return token.replace("_", "").replace("-", "").lower()


class DesignInputBranchFixture:
    """Derives, per --kind, the set of branch tokens the fixture corpus must
    cover from design-input.md 5.11.5's table (and, for phase-state, the
    5.6.3 reconcile table that row points at instead of enumerating
    inline) -- mirrors test_workflow_patch_doc.py's pattern of parsing the
    design document rather than hardcoding its content a second time."""

    # answer_mode is a field name in the 5.11.5 row, not a branch value by
    # itself; its actual branches are its four enum values (pulled from the
    # script's own constant, not duplicated here).
    TOKEN_EXPANSIONS = {"answer_mode": VWO.ANSWER_MODE_VALUES}

    def __init__(self):
        self.text = _read(DESIGN_INPUT_PATH)
        self.fixture_section = _extract_section(
            self.text, "#### 5.11.5 fixture", "### 5.12 既存 feature の互換性"
        )

    def branch_tokens_for_kind(self, kind):
        if kind == "phase-state":
            return self._phase_state_statuses()
        row_match = re.search(
            r"^\| `%s` \| (.+) \|$" % re.escape(kind), self.fixture_section, re.MULTILINE
        )
        assert row_match, f"expected a 5.11.5 table row for kind {kind!r}"
        raw_tokens = re.findall(r"`([^`]+)`", row_match.group(1))
        assert raw_tokens, f"expected at least one backtick-quoted token in the {kind!r} row"
        tokens = set()
        for t in raw_tokens:
            tokens.update(self.TOKEN_EXPANSIONS.get(t, {t}))
        return tokens

    def _phase_state_statuses(self):
        section = _extract_section(self.text, "#### 5.6.3 再開判定", "#### 5.6.4 サイズ管理")
        statuses = re.findall(r"^\| `([a-z_]+)`", section, re.MULTILINE)
        assert statuses, "expected the 5.6.3 phase-state status table rows"
        return set(statuses)


class TestFixtureBranchesDerivedFromDesignInput(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = DesignInputBranchFixture()

    def test_every_parsed_branch_token_has_at_least_one_fixture(self):
        for kind in VWO.KINDS:
            branch_tokens = self.fixture.branch_tokens_for_kind(kind)
            kind_dir = FIXTURES_ROOT / kind
            all_paths_normalized = [
                _normalize(str(case_dir.relative_to(kind_dir)))
                for _, _, case_dir in discover_fixture_cases()
                if case_dir.is_relative_to(kind_dir)
            ]
            for token in sorted(branch_tokens):
                with self.subTest(kind=kind, token=token):
                    needle = _normalize(token)
                    self.assertTrue(
                        any(needle in path for path in all_paths_normalized),
                        f"design-input.md 5.11.5 lists branch {token!r} for kind {kind!r}, "
                        "but no fixture path under references/fixtures/ mentions it -- "
                        "add a fixture (this is the 'fails until a fixture exists' guard)",
                    )


# ---------------------------------------------------------------------------
# Edge case: extend_only YAML with an alias or merge key is uncomparable
# ---------------------------------------------------------------------------

class TestExtendOnlyComparability(unittest.TestCase):
    """design-input.md 5.4.2: an extend_only target whose YAML contains an
    alias or merge key must be reported as uncomparable rather than silently
    accepted. The validator itself has no CLI channel carrying the actual
    current file content for an arbitrary write_policy target (confirmed
    against the exhaustive auxiliary-argument list in the Design section),
    so this rule is exercised directly against the pure helper function --
    see its docstring in validate-worker-output.py."""

    def test_plain_mapping_is_comparable(self):
        self.assertTrue(VWO.yaml_extend_only_comparable("a: 1\nb: 2\n"))

    def test_alias_is_uncomparable(self):
        text = "base: &b\n  x: 1\nderived: *b\n"
        self.assertFalse(VWO.yaml_extend_only_comparable(text))

    def test_merge_key_is_uncomparable(self):
        text = "base: &b\n  x: 1\nderived:\n  <<: *b\n  y: 2\n"
        self.assertFalse(VWO.yaml_extend_only_comparable(text))

    def test_non_mapping_document_is_uncomparable(self):
        self.assertFalse(VWO.yaml_extend_only_comparable("- a\n- b\n"))


# ---------------------------------------------------------------------------
# Edge case: a symlink-valued path in written_artifacts
# ---------------------------------------------------------------------------

class TestSymlinkedWrittenArtifact(unittest.TestCase):
    """Test Notes: "a symlink-valued path in written_artifacts". Built in a
    temporary directory at test-run time rather than committed as a static
    fixture, so the repository's fixture corpus never carries an actual
    symlink object (portability / binary-files-in-git concern)."""

    def test_task_plan_reached_through_a_symlink_is_read_correctly(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            feature_dir = tmp_path / "feature-dir"
            tasks_dir = feature_dir / "tasks"
            tasks_dir.mkdir(parents=True)
            real_plan = tasks_dir / "_real_task0001.md"
            real_plan.write_text(
                "# Task Plan: task0001 -- Something\n\n"
                "## Goal\n\nDeliver something.\n\n"
                "## Requirements\n\nFR1\n\n"
                "## Scope\n\n"
                "### Files to Create\n"
                "- `src/a.go` -- main file\n\n"
                "### Files to Modify\n\n"
                "## Design\n\nNotes.\n\n"
                "## Acceptance Criteria (MANDATORY)\n\n"
                "- [ ] AC-1: something is delivered\n\n"
                "## Test Notes\n\nNotes.\n\n"
                "## Out of Scope\n\nNone.\n",
                encoding="utf-8",
            )
            symlink_plan = tasks_dir / "task0001.md"
            os.symlink(real_plan.name, symlink_plan)
            self.assertTrue(symlink_plan.is_symlink())

            result_obj = {
                "schema_version": 1,
                "request_id": "run-0001",
                "worker": "implementation-planner",
                "status": "completed",
                "input_revision": {"workflow_blob": "8f17c04", "input_digest": "sha256:" + "a" * 64},
                "question_packet": None,
                "blocking_reason": None,
                "written_artifacts": [
                    {"path": "feature-docs/example/tasks/task0001.md", "sha256": "sha256:" + "e" * 64},
                ],
                "workflow_patch": {
                    "schema_version": 1,
                    "patch_id": "create-plan-p0001",
                    "base_input_digest": "sha256:" + "a" * 64,
                    "base_workflow_blob": "8f17c04",
                    "operation": "replace_planning",
                    "tasks_patch": {
                        "mode": "replace_all",
                        "entries": {
                            "task0001": {
                                "title": "Something",
                                "plan": "tasks/task0001.md",
                                "files": ["src/a.go"],
                                "skills": ["backend-impl"],
                                "domains": ["api-contract"],
                                "complexity": "medium",
                                "requirements": ["FR1"],
                                "initial_status": "pending",
                            }
                        },
                    },
                    "requirements_patch": None,
                    "step_patches": [],
                    "preserve": [],
                },
                "mode_echo": None,
                "payload": {"task_index": {"task0001": {"title": "Something"}}},
                "warnings": [],
                "report": "done",
            }
            envelope_obj = {
                "schema_version": 1,
                "request_id": "env-run-0001",
                "phase": "create-plan",
                "mode": "interactive",
                "input_revision": {"workflow_blob": "8f17c04", "input_digest": "sha256:" + "a" * 64},
                "write_policy": {"targets": []},
                "allowed_write_roots": ["feature-docs/example/"],
                "resolved_input_paths": {},
            }
            input_path = tmp_path / "input.json"
            envelope_path = tmp_path / "envelope.json"
            input_path.write_text(json.dumps(result_obj), encoding="utf-8")
            envelope_path.write_text(json.dumps(envelope_obj), encoding="utf-8")

            result = run_cli(
                [
                    "--kind", "worker-result",
                    "--worker", "implementation-planner",
                    "--input", str(input_path),
                    "--input-envelope", str(envelope_path),
                    "--feature-dir", str(feature_dir),
                ]
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


# ---------------------------------------------------------------------------
# Edge case: a task-plan Files bullet with zero or two backtick-quoted paths
# ---------------------------------------------------------------------------

class TestTaskPlanFilesBulletBacktickEdgeCases(unittest.TestCase):
    def test_zero_backtick_tokens_in_a_bullet_is_rejected(self):
        case_dir = (
            FIXTURES_ROOT
            / "worker-result"
            / "implementation-planner"
            / "invalid-task-plan-bullet-zero-backticks"
        )
        result = run_cli(build_case_args("worker-result", "implementation-planner", case_dir))
        self.assertEqual(result.returncode, 1)
        self.assertIn("backtick", result.stdout)

    def test_two_backtick_tokens_in_a_bullet_is_rejected(self):
        case_dir = (
            FIXTURES_ROOT
            / "worker-result"
            / "implementation-planner"
            / "invalid-task-plan-bullet-two-backticks"
        )
        result = run_cli(build_case_args("worker-result", "implementation-planner", case_dir))
        self.assertEqual(result.returncode, 1)
        self.assertIn("backtick", result.stdout)


# ---------------------------------------------------------------------------
# rework_index / requirements_patch.tests_append cross-check (5.4.4)
#
# Direct unit test of the internal helper: the fixture corpus's rework-planner
# cases only exercise covered_by_existing (no new_scenarios), so this closes
# the gap for the "new_scenarios must also appear in requirements_patch
# tests_append" rule without adding more committed fixtures for one internal
# helper's branch.
# ---------------------------------------------------------------------------

class TestReworkIndexNewScenariosRequireTestsAppend(unittest.TestCase):
    def test_new_scenario_missing_from_tests_append_is_rejected(self):
        rework_index = {"task0007": {"covered_by_existing": [], "new_scenarios": ["TS-9"], "rationale": "new case"}}
        workflow_patch = {"requirements_patch": {"mode": "merge_entries", "entries": {"FR1": {"expected": {}, "set": {"tests_append": []}}}}}
        errors = VWO._validate_rework_index(rework_index, workflow_patch, envelope=None, feature_dir=None, baseline_dir=None)
        messages = " ".join(e["message"] for e in errors)
        self.assertIn("tests_append", messages)

    def test_new_scenario_present_in_tests_append_is_accepted(self):
        rework_index = {"task0007": {"covered_by_existing": [], "new_scenarios": ["TS-9"], "rationale": "new case"}}
        workflow_patch = {"requirements_patch": {"mode": "merge_entries", "entries": {"FR1": {"expected": {}, "set": {"tests_append": ["TS-9"]}}}}}
        errors = VWO._validate_rework_index(rework_index, workflow_patch, envelope=None, feature_dir=None, baseline_dir=None)
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
