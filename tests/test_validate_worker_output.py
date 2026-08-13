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
an extend_only target whose YAML contains an alias or merge key
(TestExtendOnlyComparability, direct unit test of the pure helper --
see that function's docstring in the script for why it is not wired to a
--kind path).

task0016 (review round1 rework) added coverage for as5, as6, as8 (validator
half), as15, as16, as17 and as21 -- see feature-docs/agent-separation/
reviews/round1.yaml for the reproductions these classes pin:

- AC-1 / as6: TestWrittenArtifactsContainment, TestPathContainmentHelper --
  segment-wise written_artifacts containment (replaces string-prefix
  matching), malformed entries and a non-list written_artifacts no longer
  crash.
- AC-2 / as5: TestReworkIndexTaskCoverageDirect, TestReworkIndexCoverage --
  rework_index completeness verified against tasks_patch.entries in both
  directions; shared_contract_rationale is a required payload key.
- AC-3 / as15: TestDomainsVocabularyParse -- the domains vocabulary parser
  no longer absorbs the complexity vocabulary comment that follows it.
- AC-4 / as16: TestPlanPathContainment (formerly TestSymlinkedWrittenArtifact
  -- the symlink case now asserts REJECTION instead of successful read,
  per the task's explicit behaviour change) -- absolute paths, `..`
  segments, symlink segments and oversized reads are all rejected before
  the plan file is opened.
- AC-5 / as8 (validator half): TestQuestionCategoryForcesBlockingUnanswered
  -- spec-change/security/license questions must set on_unanswered: block.
- AC-6 / as21: TestStatusPayloadExclusivity -- the five non-completed
  statuses forbid a non-empty payload.
- AC-7 / as21: TestFixtureCoverageDerivedFromCapabilityTable, replacing the
  weak substring check in TestFixtureBranchesDerivedFromDesignInput for
  kind worker-result (see that test's inline comment).

task0003 (feature-docs/create-plan-status-conflict/tasks/task0003.md) adds
TestReplaceAllCreatePlanEntryStatus below, pinning the (frozen,
IMPLEMENTATION.md D1) validator's `replace_all` dry-run-apply permission
check against the create-plan step's entry status:

- AC-3: a new `invalid-replace-all-create-plan-in-progress` fixture makes
  the check reject the patch with the `replace-all-not-permitted`
  identifier, attributed to the create-plan step's `in_progress` status.
- AC-4: the same patch shape passes (exit 0) for both `pending` (the
  existing `valid-dry-run-apply` fixture, asserted here by name rather than
  only via the combined both-operations sweep) and `needs_update` (new
  `valid-replace-all-create-plan-needs-update` fixture).
- AC-5: the `in_progress` rejection carries exactly one error identifier --
  no staleness, vocabulary, or expected-mismatch entry rides along, so the
  regression cannot pass for the wrong reason.
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
            if kind == "worker-result":
                # as21: this substring-anywhere-in-the-kind check is too weak
                # for worker-result -- it is satisfied by ANY worker's
                # fixture mentioning a status token, regardless of which
                # worker actually needs it. Superseded by
                # TestFixtureCoverageDerivedFromCapabilityTable, which reads
                # each fixture's own `status` field and checks it against
                # the worker/mode it actually belongs to.
                continue
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
# as16 / AC-4: the `plan` field in a workflow_patch tasks_patch entry is
# untrusted worker output joined to --feature-dir. Absolute paths, `..`
# segments and symlink segments must be rejected before the file is ever
# opened, and an oversized plan file must be rejected before it is read in
# full. Built in temporary directories at test-run time per the Test
# Notes -- the committed fixture corpus never carries a symlink object.
# ---------------------------------------------------------------------------

class TestPlanPathContainment(unittest.TestCase):
    def _make_feature_dir(self, tmp_path):
        feature_dir = tmp_path / "feature-dir"
        tasks_dir = feature_dir / "tasks"
        tasks_dir.mkdir(parents=True)
        return feature_dir, tasks_dir

    @staticmethod
    def _valid_plan_text():
        return (
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
            "## Out of Scope\n\nNone.\n"
        )

    def _run(self, feature_dir, plan_rel, tmp_path):
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
                            "plan": plan_rel,
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

        return run_cli(
            [
                "--kind", "worker-result",
                "--worker", "implementation-planner",
                "--input", str(input_path),
                "--input-envelope", str(envelope_path),
                "--feature-dir", str(feature_dir),
            ]
        )

    def test_plan_reached_through_a_symlink_segment_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            feature_dir, tasks_dir = self._make_feature_dir(tmp_path)
            real_plan = tasks_dir / "_real_task0001.md"
            real_plan.write_text(self._valid_plan_text(), encoding="utf-8")
            symlink_plan = tasks_dir / "task0001.md"
            os.symlink(real_plan.name, symlink_plan)
            self.assertTrue(symlink_plan.is_symlink())

            result = self._run(feature_dir, "tasks/task0001.md", tmp_path)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("symlink", result.stdout.lower())

    def test_plan_without_a_symlink_is_still_read_correctly(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            feature_dir, tasks_dir = self._make_feature_dir(tmp_path)
            (tasks_dir / "task0001.md").write_text(self._valid_plan_text(), encoding="utf-8")

            result = self._run(feature_dir, "tasks/task0001.md", tmp_path)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_absolute_plan_path_is_rejected(self):
        # Asserts the SPECIFIC "task-plan-path" rejection code, not merely
        # exit 1 -- the pre-fix code also exits 1 for "/etc/passwd" on a
        # system where that file exists, but only by coincidence: pathlib's
        # `/` operator discards the left operand for an absolute right
        # operand, so it reads the real /etc/passwd and fails on a files-
        # mismatch ("task-plan-files-mismatch"), never recognizing the path
        # itself as unsafe.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            feature_dir, tasks_dir = self._make_feature_dir(tmp_path)
            (tasks_dir / "task0001.md").write_text(self._valid_plan_text(), encoding="utf-8")

            result = self._run(feature_dir, "/etc/passwd", tmp_path)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("task-plan-path", result.stdout)

    def test_plan_path_escaping_feature_dir_via_parent_segments_is_rejected(self):
        # Same coincidence risk as the absolute-path case above: the OS
        # resolves `..` when the pre-fix code calls `.is_file()`, so it
        # would also happen to read the outside file and fail on a
        # files-mismatch rather than rejecting the path itself. Assert the
        # specific rejection code to discriminate the real fix.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            feature_dir, tasks_dir = self._make_feature_dir(tmp_path)
            (tasks_dir / "task0001.md").write_text(self._valid_plan_text(), encoding="utf-8")
            (tmp_path / "outside.md").write_text("secret", encoding="utf-8")

            result = self._run(feature_dir, "../outside.md", tmp_path)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("task-plan-path", result.stdout)

    def test_oversized_plan_file_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            feature_dir, tasks_dir = self._make_feature_dir(tmp_path)
            (tasks_dir / "task0001.md").write_text("x" * (VWO.MAX_PLAN_READ_BYTES + 1), encoding="utf-8")

            result = self._run(feature_dir, "tasks/task0001.md", tmp_path)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("task-plan-too-large", result.stdout)


class TestPathContainmentHelper(unittest.TestCase):
    """as6: direct unit tests of the pure segment-comparison helper,
    reproducing both measured escapes without going through the CLI."""

    def test_sibling_directory_is_not_contained(self):
        self.assertFalse(VWO.path_is_contained_in_root("feature-docs/example2/evil.md", "feature-docs/example"))

    def test_substring_name_is_not_contained(self):
        self.assertFalse(
            VWO.path_is_contained_in_root(
                "feature-docs/example/design/mockups-evil/x.html",
                "feature-docs/example/design/mockups",
            )
        )

    def test_nested_path_is_contained(self):
        self.assertTrue(VWO.path_is_contained_in_root("feature-docs/example/tasks/task0001.md", "feature-docs/example"))

    def test_traversal_path_is_rejected(self):
        self.assertFalse(VWO.path_is_contained_in_root("feature-docs/example/../../etc/passwd", "feature-docs/example"))

    def test_trailing_slash_root_still_matches(self):
        self.assertTrue(VWO.path_is_contained_in_root("feature-docs/example/IMPLEMENTATION.md", "feature-docs/example/"))


class TestWrittenArtifactsContainment(unittest.TestCase):
    """as6: fixture-driven end-to-end coverage. Segment-wise containment
    replaces the previous string-prefix comparison that admitted a
    sibling-directory escape and a substring-name escape; malformed
    entries and a non-list written_artifacts must produce a
    machine-readable error instead of a traceback / silent per-character
    iteration."""

    def _run(self, case_name):
        case_dir = FIXTURES_ROOT / "worker-result" / "designer" / case_name
        return run_cli(build_case_args("worker-result", "designer", case_dir))

    def test_sibling_directory_escape_is_rejected(self):
        result = self._run("invalid-written-artifact-sibling-directory-escape")
        self.assertEqual(result.returncode, 1)
        self.assertIn("write_policy", result.stdout)

    def test_traversal_escape_is_rejected(self):
        result = self._run("invalid-written-artifact-traversal")
        self.assertEqual(result.returncode, 1)

    def test_substring_name_escape_is_rejected(self):
        result = self._run("invalid-written-artifact-substring-name-escape")
        self.assertEqual(result.returncode, 1)
        self.assertIn("write_policy", result.stdout)

    def test_entry_missing_path_is_a_validation_error_not_a_traceback(self):
        result = self._run("invalid-written-artifact-missing-path")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "")
        payload = json.loads(result.stdout)
        self.assertTrue(payload["errors"])

    def test_non_list_written_artifacts_is_a_validation_error_not_a_crash(self):
        # Asserts the SPECIFIC "must be a list" error (exactly one), not
        # merely "some error occurred" -- the pre-fix code also exits 1
        # here, but only by coincidence (it silently iterates the string
        # per character, and each single-character "path" happens to fail
        # containment against every allowed root).
        result = self._run("invalid-written-artifacts-not-a-list")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stderr, "")
        payload = json.loads(result.stdout)
        self.assertEqual(len(payload["errors"]), 1)
        self.assertIn("must be a list", payload["errors"][0]["message"])

    def test_contained_path_in_allowed_root_is_accepted(self):
        result = self._run("valid-written-artifact-in-allowed-root")
        self.assertEqual(result.returncode, 0, result.stdout)


# ---------------------------------------------------------------------------
# as15 / AC-3: the domains vocabulary parser must stop at the domains block
# boundary the same way check-plugin-invariants.py does, so it never
# absorbs the complexity vocabulary comment that follows it.
# ---------------------------------------------------------------------------

class TestDomainsVocabularyParse(unittest.TestCase):
    def test_real_review_rules_yaml_yields_exactly_the_eight_documented_domains(self):
        vocab = VWO.load_domains_vocabulary(REPO_ROOT / "em-workflow" / "references")
        self.assertEqual(
            vocab,
            {
                "auth",
                "input-handling",
                "data-persistence",
                "external-io",
                "concurrency",
                "api-contract",
                "ui",
                "config-infra",
            },
        )

    def test_domain_declaring_a_complexity_value_is_rejected(self):
        case_dir = FIXTURES_ROOT / "workflow-patch" / "replace_planning" / "invalid-domain-is-complexity-value"
        result = run_cli(build_case_args("workflow-patch", "replace_planning", case_dir))
        self.assertEqual(result.returncode, 1)
        self.assertIn("domains", result.stdout)


# ---------------------------------------------------------------------------
# as8 (validator half) / AC-5: a question whose category is spec-change,
# security or licensing must carry on_unanswered: block, so a worker cannot
# silently choose record_tbd/use_batch_policy and defeat the batch abort.
# ---------------------------------------------------------------------------

class TestQuestionCategoryForcesBlockingUnanswered(unittest.TestCase):
    def _run(self, case_name):
        case_dir = FIXTURES_ROOT / "question-packet" / "category-fail-closed" / case_name
        return run_cli(build_case_args("question-packet", "category-fail-closed", case_dir))

    def test_security_question_with_non_blocking_unanswered_is_rejected(self):
        result = self._run("invalid-security-record-tbd")
        self.assertEqual(result.returncode, 1)
        self.assertIn("on_unanswered", result.stdout)

    def test_security_question_with_blocking_unanswered_is_accepted(self):
        result = self._run("valid-security-blocking")
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_all_three_fail_closed_categories_are_rejected_directly(self):
        for category in ("spec-change", "security", "license"):
            with self.subTest(category=category):
                q = {
                    "question_id": "q.test",
                    "gate_id": "gate.x",
                    "category": category,
                    "priority": "high",
                    "blocking": True,
                    "prompt": "p",
                    "header": "h",
                    "answer_mode": "freeform",
                    "options": [],
                    "why_needed": "w",
                    "on_unanswered": "record_tbd",
                }
                errors = VWO.validate_question(q, 0)
                messages = " ".join(e["message"] for e in errors)
                self.assertIn("on_unanswered", messages)

    def test_other_categories_do_not_force_blocking(self):
        q = {
            "question_id": "q.test",
            "gate_id": "gate.x",
            "category": "testing",
            "priority": "high",
            "blocking": False,
            "prompt": "p",
            "header": "h",
            "answer_mode": "freeform",
            "options": [],
            "why_needed": "w",
            "on_unanswered": "record_tbd",
        }
        errors = VWO.validate_question(q, 0)
        self.assertEqual(errors, [])


# ---------------------------------------------------------------------------
# as21 / AC-6: worker-envelope.md forbids `payload` on the five non-completed
# statuses; the validator never enforced that.
# ---------------------------------------------------------------------------

class TestStatusPayloadExclusivity(unittest.TestCase):
    def test_blocked_with_nonempty_payload_is_rejected(self):
        case_dir = FIXTURES_ROOT / "worker-result" / "requirements-analyst-full" / "invalid-blocked-with-payload"
        result = run_cli(build_case_args("worker-result", "requirements-analyst-full", case_dir))
        self.assertEqual(result.returncode, 1)
        self.assertIn("payload", result.stdout)

    def test_every_non_completed_status_forbids_payload_directly(self):
        base = dict(
            schema_version=1,
            worker="designer",
            request_id="run-0001",
            input_revision={"input_digest": "sha256:" + "a" * 64},
            question_packet=None,
            workflow_patch=None,
            mode_echo=None,
            written_artifacts=[],
        )
        for status in ("blocked", "invalid_input", "stale_input", "failed"):
            with self.subTest(status=status):
                data = dict(base, status=status, blocking_reason="x", payload={"design_summary": {}})
                errors = VWO.validate_worker_result(data, "designer")
                messages = " ".join(e["message"] for e in errors)
                self.assertIn("payload", messages)

    def test_completed_still_requires_a_non_empty_payload(self):
        data = dict(
            schema_version=1,
            worker="designer",
            request_id="run-0001",
            input_revision={"input_digest": "sha256:" + "a" * 64},
            question_packet=None,
            workflow_patch=None,
            mode_echo=None,
            written_artifacts=[],
            status="completed",
            blocking_reason=None,
            payload={},
        )
        errors = VWO.validate_worker_result(data, "designer")
        messages = " ".join(e["message"] for e in errors)
        self.assertIn("non-empty payload", messages)


# ---------------------------------------------------------------------------
# as21 / AC-7: fixture coverage generated from WORKER_CAPABILITIES (the
# capability table) instead of checking that a status token merely appears
# SOMEWHERE under fixtures/worker-result/ (see
# TestFixtureBranchesDerivedFromDesignInput, which skips worker-result for
# exactly this reason).
# ---------------------------------------------------------------------------

class TestFixtureCoverageDerivedFromCapabilityTable(unittest.TestCase):
    @staticmethod
    def _group_dir_name(worker, mode_key):
        if worker == "requirements-analyst":
            # Fixture directories use kebab-case even though the mode_key
            # itself (WORKER_CAPABILITIES / mode_echo) is snake_case.
            return f"requirements-analyst-{mode_key.replace('_', '-')}"
        return worker

    @staticmethod
    def _valid_fixture_statuses(group_dir):
        """Maps each valid-* case dir under group_dir to the `status` read
        from its OWN input file -- not from the directory name -- so this
        cannot be satisfied by a differently-named worker's fixture."""
        statuses = set()
        if not group_dir.is_dir():
            return statuses
        for case_dir in sorted(group_dir.iterdir()):
            if not case_dir.is_dir() or not case_dir.name.startswith("valid-"):
                continue
            input_path = _companion(case_dir, "input")
            if input_path is None:
                continue
            data, _ = VWO.parse_yaml_text(input_path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                statuses.add(data.get("status"))
        return statuses

    def test_every_worker_and_permitted_status_pair_has_a_valid_fixture(self):
        for worker, modes in VWO.WORKER_CAPABILITIES.items():
            for mode_key, caps in modes.items():
                group = self._group_dir_name(worker, mode_key)
                group_dir = FIXTURES_ROOT / "worker-result" / group
                statuses_present = self._valid_fixture_statuses(group_dir)
                for status in sorted(caps["allowed_statuses"]):
                    with self.subTest(worker=worker, mode=mode_key, status=status):
                        self.assertIn(
                            status,
                            statuses_present,
                            f"no valid-* fixture under {group_dir} declares status {status!r} "
                            f"(worker={worker!r}, mode={mode_key!r})",
                        )


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

def _write_verification_md(dir_path, scenario_ids):
    dir_path.mkdir(parents=True, exist_ok=True)
    lines = ["### Test Scenarios from SPEC.md", ""]
    lines.extend(f"- {tid}: something" for tid in scenario_ids)
    (dir_path / "VERIFICATION.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


class TestReworkIndexNewScenariosRequireTestsAppend(unittest.TestCase):
    # Both cases now declare task0007 in tasks_patch.entries too: as5's
    # coverage fix (TestReworkIndexTaskCoverageDirect below) rejects a
    # rework_index entry naming a task tasks_patch never created, so these
    # workflow_patch fixtures must create the task they index to isolate
    # the tests_append cross-check this class exists to cover.
    def test_new_scenario_missing_from_tests_append_is_rejected(self):
        rework_index = {"task0007": {"covered_by_existing": [], "new_scenarios": ["TS-9"], "rationale": "new case"}}
        workflow_patch = {
            "tasks_patch": {"entries": {"task0007": {}}},
            "requirements_patch": {"mode": "merge_entries", "entries": {"FR1": {"expected": {}, "set": {"tests_append": []}}}},
        }
        # bs10 (round 2): this case now ALSO carries the "no --baseline-dir"
        # error (feature_dir/baseline_dir are both None), but assertIn only
        # requires "tests_append" to appear SOMEWHERE in the combined
        # messages, so the additional error does not affect this assertion.
        errors = VWO._validate_rework_index(rework_index, workflow_patch, envelope=None, feature_dir=None, baseline_dir=None)
        messages = " ".join(e["message"] for e in errors)
        self.assertIn("tests_append", messages)

    def test_new_scenario_present_in_tests_append_is_accepted(self):
        # bs10 (round 2): a real feature_dir/baseline_dir pair is now
        # required to isolate the tests_append cross-check this test exists
        # for -- without one, the baseline-requirement rule (see
        # TestReworkIndexRequiresBaselineForNewScenarios below) would itself
        # reject this case, which is not what this test is about.
        rework_index = {"task0007": {"covered_by_existing": [], "new_scenarios": ["TS-9"], "rationale": "new case"}}
        workflow_patch = {
            "tasks_patch": {"entries": {"task0007": {}}},
            "requirements_patch": {"mode": "merge_entries", "entries": {"FR1": {"expected": {}, "set": {"tests_append": ["TS-9"]}}}},
        }
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            feature_dir = tmp_path / "feature-dir"
            baseline_dir = tmp_path / "baseline-dir"
            _write_verification_md(feature_dir, ["TS-9"])
            _write_verification_md(baseline_dir, [])
            errors = VWO._validate_rework_index(
                rework_index, workflow_patch, envelope=None, feature_dir=feature_dir, baseline_dir=baseline_dir
            )
        self.assertEqual(errors, [])


# ---------------------------------------------------------------------------
# bs10 (round 2, validator half) / AC-5: declaring new_scenarios without a
# --baseline-dir must be an error, not a silent degradation to "the
# identifier exists in the current document" (which the rework-planner
# itself wrote, so it proves nothing).
# ---------------------------------------------------------------------------

class TestReworkIndexRequiresBaselineForNewScenarios(unittest.TestCase):
    def _rework_index_and_patch(self):
        rework_index = {"task0007": {"covered_by_existing": [], "new_scenarios": ["TS-9"], "rationale": "new case"}}
        workflow_patch = {
            "tasks_patch": {"entries": {"task0007": {}}},
            "requirements_patch": {"mode": "merge_entries", "entries": {"FR1": {"expected": {}, "set": {"tests_append": ["TS-9"]}}}},
        }
        return rework_index, workflow_patch

    def test_new_scenarios_without_baseline_dir_is_rejected_even_with_feature_dir(self):
        rework_index, workflow_patch = self._rework_index_and_patch()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            feature_dir = tmp_path / "feature-dir"
            _write_verification_md(feature_dir, ["TS-9"])
            errors = VWO._validate_rework_index(
                rework_index, workflow_patch, envelope=None, feature_dir=feature_dir, baseline_dir=None
            )
        messages = " ".join(e["message"] for e in errors)
        self.assertIn("baseline", messages.lower())

    def test_new_scenarios_without_baseline_dir_is_rejected_with_no_feature_dir_either(self):
        rework_index, workflow_patch = self._rework_index_and_patch()
        errors = VWO._validate_rework_index(
            rework_index, workflow_patch, envelope=None, feature_dir=None, baseline_dir=None
        )
        messages = " ".join(e["message"] for e in errors)
        self.assertIn("baseline", messages.lower())

    def test_new_scenarios_with_baseline_dir_is_not_rejected_for_baseline_reasons(self):
        rework_index, workflow_patch = self._rework_index_and_patch()
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            feature_dir = tmp_path / "feature-dir"
            baseline_dir = tmp_path / "baseline-dir"
            _write_verification_md(feature_dir, ["TS-9"])
            _write_verification_md(baseline_dir, [])
            errors = VWO._validate_rework_index(
                rework_index, workflow_patch, envelope=None, feature_dir=feature_dir, baseline_dir=baseline_dir
            )
        messages = " ".join(e["message"] for e in errors)
        self.assertNotIn("baseline", messages.lower())

    def test_covered_by_existing_only_needs_no_baseline_dir(self):
        # A task that only claims covered_by_existing (no new_scenarios) has
        # nothing to verify against a baseline diff, so this rule must not
        # fire for it.
        rework_index = {"task0007": {"covered_by_existing": ["TS-3"], "new_scenarios": [], "rationale": "x"}}
        workflow_patch = {"tasks_patch": {"entries": {"task0007": {}}}}
        envelope = {"verification_index": {"TS-3": ["FR1"]}}
        errors = VWO._validate_rework_index(
            rework_index, workflow_patch, envelope=envelope, feature_dir=None, baseline_dir=None
        )
        self.assertEqual(errors, [])


# ---------------------------------------------------------------------------
# as5 / AC-2: rework_index completeness against tasks_patch.entries, in both
# directions, plus shared_contract_rationale as a required payload key.
# ---------------------------------------------------------------------------

class TestReworkIndexTaskCoverageDirect(unittest.TestCase):
    """Direct unit tests of the pure coverage-comparison helper: reproduces
    as5's exact measured regression ("replacing the valid-completed
    fixture's rework_index with {} while task0007 remains in tasks_patch
    still exits 0") and its mirror image."""

    def test_task_created_but_absent_from_index_is_rejected(self):
        workflow_patch = {"tasks_patch": {"entries": {"task0007": {}}}}
        errors = VWO._validate_rework_index({}, workflow_patch, envelope=None, feature_dir=None, baseline_dir=None)
        messages = " ".join(e["message"] for e in errors)
        self.assertIn("task0007", messages)
        self.assertIn("missing from rework_index", messages)

    def test_index_names_a_task_not_created_is_rejected(self):
        rework_index = {"task0099": {"covered_by_existing": [], "new_scenarios": [], "rationale": "x"}}
        workflow_patch = {"tasks_patch": {"entries": {}}}
        errors = VWO._validate_rework_index(rework_index, workflow_patch, envelope=None, feature_dir=None, baseline_dir=None)
        messages = " ".join(e["message"] for e in errors)
        self.assertIn("task0099", messages)
        self.assertIn("not created by tasks_patch", messages)

    def test_fully_covered_index_matching_created_tasks_is_accepted(self):
        rework_index = {"task0007": {"covered_by_existing": ["TS-3"], "new_scenarios": [], "rationale": "x"}}
        workflow_patch = {"tasks_patch": {"entries": {"task0007": {}}}}
        envelope = {"verification_index": {"TS-3": ["FR1"]}}
        errors = VWO._validate_rework_index(rework_index, workflow_patch, envelope=envelope, feature_dir=None, baseline_dir=None)
        self.assertEqual(errors, [])


class TestReworkIndexCoverage(unittest.TestCase):
    """Fixture-driven end-to-end coverage for the same rule via the CLI."""

    def _run(self, case_name):
        case_dir = FIXTURES_ROOT / "worker-result" / "rework-planner" / case_name
        return run_cli(build_case_args("worker-result", "rework-planner", case_dir))

    def test_created_task_missing_from_rework_index_is_rejected(self):
        result = self._run("invalid-rework-index-missing-task-entry")
        self.assertEqual(result.returncode, 1)
        self.assertIn("task0007", result.stdout)

    def test_rework_index_naming_an_uncreated_task_is_rejected(self):
        result = self._run("invalid-rework-index-unknown-task")
        self.assertEqual(result.returncode, 1)
        self.assertIn("task0007", result.stdout)

    def test_missing_shared_contract_rationale_is_rejected(self):
        result = self._run("invalid-missing-shared-contract-rationale")
        self.assertEqual(result.returncode, 1)
        self.assertIn("shared_contract_rationale", result.stdout)

    def test_valid_completed_with_full_coverage_and_rationale_passes(self):
        result = self._run("valid-completed")
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_new_scenarios_without_baseline_dir_is_rejected_via_cli(self):
        result = self._run("invalid-new-scenarios-without-baseline")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("baseline", result.stdout.lower())


# ---------------------------------------------------------------------------
# bs2 (round 2, security/comprehensive) / AC-1, AC-2: gate registry binding.
# gate_id was previously checked for non-emptiness only, so any listed gate
# could be attached to any worker/phase/category/option combination. Both
# measured spoofs from feature-docs/agent-separation/reviews/round2.yaml are
# reproduced here (via fixtures run through the real CLI) and must now be
# rejected; a correctly-bound packet must still pass.
# ---------------------------------------------------------------------------

class TestGateRegistryBinding(unittest.TestCase):
    def _run(self, case_name):
        case_dir = FIXTURES_ROOT / "question-packet" / "gate-registry" / case_name
        return run_cli(build_case_args("question-packet", "gate-registry", case_dir))

    def test_worker_phase_and_category_spoof_is_rejected(self):
        # bs2 reproduction 1: "a rework-planner packet with phase rework,
        # category security and gate_id create-spec.design-step" -- measured
        # to exit 0 before this fix.
        result = self._run("invalid-worker-phase-category-spoof")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        messages = " ".join(e["message"] for e in payload["errors"])
        self.assertIn("registered to worker", messages)
        self.assertIn("registered to phase", messages)
        self.assertIn("requires category", messages)

    def test_category_laundered_through_unrelated_gate_is_rejected(self):
        # bs2 reproduction 2: "category spec-change and gate_id
        # create-plan.tbd-resolution" -- measured to exit 0 before this fix.
        result = self._run("invalid-category-mismatch-tbd-resolution")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        messages = " ".join(e["message"] for e in payload["errors"])
        self.assertIn("requires category 'tbd-resolution'", messages)

    def test_correctly_bound_gate_passes(self):
        result = self._run("valid-design-step-correct-binding")
        self.assertEqual(result.returncode, 0, result.stdout)


class TestGateRegistryDerivation(unittest.TestCase):
    """Direct unit tests of the derivation helpers, against the plugin's own
    real references/ directory (same precedent as
    TestDomainsVocabularyParse's real-file test above) -- these are the
    plugin's committed reference documents, not test/case-specific fixtures,
    so reading them directly is not a hermeticity violation."""

    REFERENCES_DIR = REPO_ROOT / "em-workflow" / "references"

    def test_category_derived_from_gate_id_suffix(self):
        self.assertEqual(VWO._category_for_gate_id("create-spec.design-step"), "design-step")
        self.assertEqual(VWO._category_for_gate_id("create-plan.tbd-resolution"), "tbd-resolution")
        # "requirement-clarification" is not a CATEGORY_VALUES member, so no
        # category is derived (the analyst contract states this gate covers
        # many categories, not one).
        self.assertIsNone(VWO._category_for_gate_id("create-spec.requirement-clarification"))
        self.assertIsNone(VWO._category_for_gate_id("not-a-gate-id"))

    def test_phase_derived_from_gate_id_prefix(self):
        self.assertEqual(VWO._phase_for_gate_id("create-spec.design-step"), "create-spec")
        self.assertEqual(VWO._phase_for_gate_id("create-plan.tbd-resolution"), "create-plan")
        # "design-system" is not a PHASE_VALUES member.
        self.assertIsNone(VWO._phase_for_gate_id("design-system.reclassify"))

    def test_analyst_contract_gates_are_worker_and_phase_attributed(self):
        registry = VWO.build_gate_registry(self.REFERENCES_DIR)
        entry = registry.get("create-spec.design-step")
        self.assertIsNotNone(entry, "expected create-spec.design-step in the derived registry")
        self.assertEqual(entry["worker"], "requirements-analyst")
        self.assertEqual(entry["phase"], "create-spec")
        self.assertEqual(entry["category"], "design-step")
        self.assertEqual(entry["required_option_id"], "decide_autonomously")

    def test_gate_with_no_contract_table_attribution_is_worker_unconstrained(self):
        # create-plan.tbd-resolution is listed in batch-policies.yaml but no
        # contract attributes it to a specific worker via a "## Gate
        # identifiers" table, so worker/phase/option stay unconstrained --
        # only its suffix-derived category is bound. This is also what
        # keeps the existing fixture corpus (which reuses this gate_id
        # across several different workers as a generic placeholder) green.
        registry = VWO.build_gate_registry(self.REFERENCES_DIR)
        entry = registry.get("create-plan.tbd-resolution")
        self.assertIsNotNone(entry)
        self.assertIsNone(entry["worker"])
        self.assertIsNone(entry["phase"])
        self.assertIsNone(entry["required_option_id"])
        self.assertEqual(entry["category"], "tbd-resolution")

    def test_missing_references_dir_yields_empty_registry(self):
        self.assertEqual(VWO.build_gate_registry(None), {})
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(VWO.build_gate_registry(Path(tmp) / "does-not-exist"), {})


# ---------------------------------------------------------------------------
# bs9 (round 2, comprehensive) / AC-3: every element of the patch entries,
# step patches, preserve list, worker runs, patches, packets, answers and
# resolved_input_cache must produce a machine-readable error for a malformed
# element, never a traceback. The two reproductions the round record names
# are covered end-to-end via fixtures (TestFixtureCorpusDataDriven already
# runs them); the remaining structures this finding also names are covered
# directly here against the pure validation functions.
# ---------------------------------------------------------------------------

class TestMalformedElementsProduceMachineReadableErrors(unittest.TestCase):
    def test_task_patch_entry_as_string_is_rejected_not_a_crash(self):
        # bs9 reproduction 1 (fixture-driven end-to-end coverage also exists
        # at workflow-patch/replace_planning/invalid-task-entry-not-a-mapping).
        patch = {
            "schema_version": 1,
            "patch_id": "create-plan-p0001",
            "base_input_digest": "sha256:" + "a" * 64,
            "base_workflow_blob": "8f17c04",
            "operation": "replace_planning",
            "tasks_patch": {"mode": "replace_all", "entries": {"task0001": "not-a-mapping"}},
            "requirements_patch": None,
            "step_patches": [],
            "preserve": [],
        }
        errors = VWO.validate_workflow_patch(patch)
        messages = " ".join(e["message"] for e in errors)
        self.assertIn("must be a mapping", messages)

    def test_worker_run_as_string_is_rejected_not_a_crash(self):
        # bs9 reproduction 2 (fixture-driven end-to-end coverage also exists
        # at phase-state/completed/invalid-worker-run-not-a-mapping).
        data = dict(
            schema_version=1, feature="example", phase="create-plan", status="completed",
            generation=1, worker_runs=["not-a-mapping"], patches=[], packets={}, answers={},
            resolved_input_cache={},
        )
        errors = VWO.validate_phase_state(data)
        messages = " ".join(e["message"] for e in errors)
        self.assertIn("must be a mapping", messages)

    def test_step_patches_entry_as_string_is_rejected_not_a_crash(self):
        patch = {
            "schema_version": 1,
            "patch_id": "create-plan-p0001",
            "base_input_digest": "sha256:" + "a" * 64,
            "base_workflow_blob": "8f17c04",
            "operation": "replace_planning",
            "tasks_patch": {"mode": "replace_all", "entries": {}},
            "requirements_patch": None,
            "step_patches": ["not-a-mapping"],
            "preserve": [],
        }
        errors = VWO.validate_workflow_patch(patch)
        messages = " ".join(e["message"] for e in errors)
        self.assertIn("step_patches[0] must be a mapping", messages)

    def test_preserve_entry_as_dict_is_rejected_not_a_crash(self):
        patch = {
            "schema_version": 1,
            "patch_id": "create-plan-p0001",
            "base_input_digest": "sha256:" + "a" * 64,
            "base_workflow_blob": "8f17c04",
            "operation": "replace_planning",
            "tasks_patch": {"mode": "replace_all", "entries": {}},
            "requirements_patch": None,
            "step_patches": [],
            "preserve": [{"not": "a string"}],
        }
        errors = VWO.validate_workflow_patch(patch)
        messages = " ".join(e["message"] for e in errors)
        self.assertIn("preserve entry", messages)
        self.assertIn("must be a string", messages)

    def test_phase_state_patches_entry_as_string_is_rejected_not_a_crash(self):
        data = dict(
            schema_version=1, feature="example", phase="create-plan", status="completed",
            generation=1, worker_runs=[], patches=["not-a-mapping"], packets={}, answers={},
            resolved_input_cache={},
        )
        errors = VWO.validate_phase_state(data)
        messages = " ".join(e["message"] for e in errors)
        self.assertIn("patches[0] must be a mapping", messages)

    def test_phase_state_packet_value_as_string_is_rejected_not_a_crash(self):
        data = dict(
            schema_version=1, feature="example", phase="create-plan", status="completed",
            generation=1, worker_runs=[], patches=[], packets={"create-plan-q0001": "not-a-mapping"},
            answers={}, resolved_input_cache={},
        )
        errors = VWO.validate_phase_state(data)
        messages = " ".join(e["message"] for e in errors)
        self.assertIn("packets[create-plan-q0001] must be a mapping", messages)

    def test_phase_state_answer_value_as_string_is_rejected_not_a_crash(self):
        # bs9: "the answers list already has a guard that the equivalent
        # phase-state loop lacks" -- this is the phase-state loop.
        data = dict(
            schema_version=1, feature="example", phase="create-plan", status="completed",
            generation=1, worker_runs=[], patches=[], packets={},
            answers={"requirement.fr4.tbd-resolution": "not-a-mapping"}, resolved_input_cache={},
        )
        errors = VWO.validate_phase_state(data)
        messages = " ".join(e["message"] for e in errors)
        self.assertIn("answers[requirement.fr4.tbd-resolution] must be a mapping", messages)

    def test_resolved_input_cache_entry_as_string_is_rejected_not_a_crash(self):
        data = dict(
            schema_version=1, feature="example", phase="create-plan", status="completed",
            generation=1, worker_runs=[], patches=[], packets={}, answers={},
            resolved_input_cache={"design_system_candidates": "not-a-mapping"},
        )
        errors = VWO.validate_phase_state(data)
        messages = " ".join(e["message"] for e in errors)
        self.assertIn("resolved_input_cache[design_system_candidates] must be a mapping", messages)


# ---------------------------------------------------------------------------
# bs9 / AC-4: an unexpected exception (one the structural guards above do
# not specifically name) must exit 2 with a message on stderr, never exit 1
# with an empty stdout.
# ---------------------------------------------------------------------------

class TestUnexpectedExceptionExitsTwoWithMessage(unittest.TestCase):
    def test_non_mapping_workflow_during_dry_run_apply_exits_2_not_1_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            patch = {
                "schema_version": 1,
                "patch_id": "create-plan-p0001",
                "base_input_digest": "sha256:" + "a" * 64,
                "base_workflow_blob": "8f17c04",
                "operation": "replace_planning",
                "tasks_patch": {"mode": "replace_all", "entries": {}},
                "requirements_patch": None,
                "step_patches": [],
                "preserve": [],
            }
            input_path = tmp_path / "input.json"
            workflow_path = tmp_path / "workflow.json"
            digest_source_path = tmp_path / "digest-source.json"
            input_path.write_text(json.dumps(patch), encoding="utf-8")
            # A non-mapping workflow.yaml (a bare list) reaches
            # `workflow.get(...)` deep inside the dry-run-apply machinery,
            # which is not one of the structures bs9 explicitly names --
            # this demonstrates the exit-2 safety net catches genuinely
            # unanticipated shapes too, not just the enumerated ones.
            workflow_path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
            digest_source_path.write_text(json.dumps({"workflow_blob": "8f17c04"}), encoding="utf-8")

            result = run_cli(
                [
                    "--kind", "workflow-patch",
                    "--worker", "implementation-planner",
                    "--input", str(input_path),
                    "--workflow", str(workflow_path),
                    "--digest-source", str(digest_source_path),
                    "--dry-run-apply",
                ]
            )
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertTrue(result.stderr.strip(), "expected a message on stderr")


# ---------------------------------------------------------------------------
# bs1 (round 2, comprehensive) / AC-6: the envelope's status table forbids
# `artifacts`, a `patch` and `blocking_reason` on `needs_user_input` -- it
# does NOT forbid `payload`, and the analyst contract requires
# `needs_user_input` to carry `payload.analysis_snapshot`. The payload
# prohibition added last round wrongly extended to this one status; it must
# still hold for the other four non-completed statuses.
# ---------------------------------------------------------------------------

class TestNeedsUserInputPayloadExemption(unittest.TestCase):
    def _base(self, status, payload):
        return dict(
            schema_version=1,
            worker="requirements-analyst",
            request_id="run-0001",
            input_revision={"input_digest": "sha256:" + "a" * 64},
            question_packet={
                "schema_version": 1,
                "packet_id": "create-spec-q0001",
                "phase": "create-spec",
                "worker": "requirements-analyst",
                "iteration": 1,
                "input_revision": {"input_digest": "sha256:" + "a" * 64},
                "questions": [
                    {
                        "question_id": "q.x",
                        "gate_id": "create-spec.requirement-clarification",
                        "category": "other",
                        "priority": "high",
                        "blocking": True,
                        "prompt": "p",
                        "header": "h",
                        "answer_mode": "freeform",
                        "options": [],
                        "why_needed": "w",
                        "on_unanswered": "record_tbd",
                    }
                ],
            },
            workflow_patch=None,
            mode_echo="full",
            written_artifacts=[],
            status=status,
            blocking_reason=None,
            payload=payload,
        )

    def test_needs_user_input_with_non_empty_payload_is_no_longer_rejected_for_payload(self):
        data = self._base("needs_user_input", {"analysis_snapshot": {"feature_name_candidate": "x"}})
        errors = VWO.validate_worker_result(data, "requirements-analyst")
        messages = " ".join(e["message"] for e in errors)
        self.assertNotIn("forbids a non-empty payload", messages)

    def test_other_non_completed_statuses_still_forbid_payload(self):
        for status in ("blocked", "invalid_input", "stale_input", "failed"):
            with self.subTest(status=status):
                data = self._base(status, {"analysis_snapshot": {}})
                data["question_packet"] = None
                data["blocking_reason"] = "x"
                errors = VWO.validate_worker_result(data, "requirements-analyst")
                messages = " ".join(e["message"] for e in errors)
                self.assertIn("forbids a non-empty payload", messages)

    def test_fixture_analyst_needs_user_input_with_analysis_snapshot_passes(self):
        case_dir = (
            FIXTURES_ROOT / "worker-result" / "requirements-analyst-full"
            / "valid-needs-user-input-with-analysis-snapshot"
        )
        result = run_cli(build_case_args("worker-result", "requirements-analyst-full", case_dir))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


# ---------------------------------------------------------------------------
# task0003 (feature-docs/create-plan-status-conflict): pins the frozen
# validate-worker-output.py replace_all/create-plan permission check with
# regression fixtures. AC-3/AC-4/AC-5.
# ---------------------------------------------------------------------------

class TestReplaceAllCreatePlanEntryStatus(unittest.TestCase):
    """The validator's dry-run application (5.5.5 rule 5 /
    _validate_dry_run_apply) rejects replace_all unless the create-plan
    step's entry status is pending or needs_update. This class pins that
    behaviour without touching the validator (IMPLEMENTATION.md D1)."""

    def _run(self, case_name):
        case_dir = FIXTURES_ROOT / "workflow-patch" / "replace_planning" / case_name
        return run_cli(build_case_args("workflow-patch", "replace_planning", case_dir))

    def test_create_plan_in_progress_rejected_with_replace_all_not_permitted(self):
        # AC-3
        result = self._run("invalid-replace-all-create-plan-in-progress")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        codes = {e["code"] for e in payload["errors"]}
        self.assertIn("replace-all-not-permitted", codes)
        messages = " ".join(e["message"] for e in payload["errors"])
        self.assertIn("in_progress", messages)

    def test_create_plan_in_progress_rejected_for_exactly_one_reason(self):
        # AC-5: removing the permission check from consideration, every
        # other validation layer is satisfied -- assert on the set of
        # reported error identifiers, not just their count, so the test
        # cannot pass because the fixture happens to be wrong in two ways.
        result = self._run("invalid-replace-all-create-plan-in-progress")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        codes = {e["code"] for e in payload["errors"]}
        self.assertEqual(codes, {"replace-all-not-permitted"})

    def test_create_plan_needs_update_passes(self):
        # AC-4
        result = self._run("valid-replace-all-create-plan-needs-update")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_create_plan_pending_passes(self):
        # AC-4 (Test Notes): the existing pending case is exercised today
        # only as part of TestDryRunApplyRejections's combined
        # both-operations sweep; this scenario-named assertion means a
        # future change to that combined test cannot silently drop the
        # pending branch.
        result = self._run("valid-dry-run-apply")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
