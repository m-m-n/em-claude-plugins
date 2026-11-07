"""Tests for task0003 of rework-docs-only-task-routing: the `requirements_patch`
tests replacement (`tests_replace` set key, `tests_contains` expected key) in
em-workflow/references/workflow-patch.md and
em-workflow/scripts/validate-worker-output.py, and the docs-only round fixture
that reproduces the reported failure
(feature-docs/rework-docs-only-task-routing/tasks/task0003.md).

Covers task0003 Acceptance Criteria:

- AC-1: workflow-patch.md documents the tests replacement
  (`TestWorkflowPatchDocumentsTestsReplace`).
- AC-2: the validator's structural check
  (`TestStructuralCheckOfTestsReplace`).
- AC-3: the dry-run expectation check, `expected-mismatch`
  (`TestDryRunExpectationCheck`).
- AC-4: the in-memory application (`TestInMemoryApplication`).
- AC-5: the `valid-docs-only-round` fixture passes `--dry-run-apply` with the
  content the task plan describes (`TestDocsOnlyRoundFixture`).
- AC-6: applying that fixture's patch in memory yields the documents-only
  outcome (`TestDocsOnlyRoundApplied`).
- AC-7: this module reads the validator module and the fixtures directly and
  imports only the standard library (`TestOwnModuleStdlibOnly`); the
  "every existing fixture and test passes unchanged" half is exercised by
  running the whole suite, not by a test here.

The validator module is loaded by file path (the way
tests/test_validate_worker_output.py does) and the tests assert error codes,
not only exit codes. The in-memory application tests call the module's own
`apply_patch`; they never re-implement application logic.
"""

import ast
import copy
import importlib.util
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "em-workflow" / "scripts" / "validate-worker-output.py"
WORKFLOW_PATCH_DOC = REPO_ROOT / "em-workflow" / "references" / "workflow-patch.md"
FIXTURES_ROOT = REPO_ROOT / "em-workflow" / "references" / "fixtures"
MISMATCH_CASE = (
    FIXTURES_ROOT / "workflow-patch" / "append_rework" / "invalid-tests-replace-expected-mismatch"
)
DOCS_ONLY_CASE = FIXTURES_ROOT / "worker-result" / "rework-planner" / "valid-docs-only-round"


def _load_module():
    spec = importlib.util.spec_from_file_location("validate_worker_output", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


VWO = _load_module()


def _read_json(path):
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _codes(errors):
    return {e["code"] for e in errors}


def _run_cli(args):
    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH)] + list(args),
        capture_output=True,
        text=True,
    )


def _patch_with(entries):
    """A minimal, otherwise valid append_rework patch carrying only the given
    requirements_patch entries, so any error reported is about them."""
    return {
        "schema_version": 1,
        "patch_id": "rework-p0001",
        "base_input_digest": "sha256:" + "a" * 64,
        "base_workflow_blob": "8f17c04",
        "operation": "append_rework",
        "tasks_patch": {"mode": "append", "expected_next_task_id": "task0002", "entries": {}},
        "requirements_patch": {"mode": "merge_entries", "entries": entries},
        # Empty tasks_patch.entries make this a docs-only round, which is
        # valid only with exactly one origin-step entry set to pending
        # (rework-docs-only-medium-fixes/task0002, FR3).
        "step_patches": [
            {"expected": {"status": "failed"}, "set": {"status": "pending"}, "step_id": "verify"}
        ],
        "preserve": ["workflow.implement.base_commit"],
    }


def _entry(set_block, expected=None):
    entry = {"set": set_block}
    if expected is not None:
        entry["expected"] = expected
    return entry


def _structural_errors(entries):
    return VWO.validate_workflow_patch(_patch_with(entries))


def _workflow_with_tests(tests):
    return {
        "requirements": {"FR1": {"status": "ok", "tasks": ["task0001"], "tests": list(tests), "title": "x"}},
        "tasks": {},
        "workflow": [{"id": "implement", "status": "completed", "base_commit": "deadbeef"}],
    }


def _applied_tests(tests, set_block):
    patch = {"operation": "append_rework", "requirements_patch": {"entries": {"FR1": {"set": set_block}}}}
    return VWO.apply_patch(_workflow_with_tests(tests), patch)["requirements"]["FR1"]


# ---------------------------------------------------------------------------
# AC-1: workflow-patch.md
# ---------------------------------------------------------------------------

def _flat(text):
    return re.sub(r"\s+", " ", text)


def _section(text, start_heading, end_heading):
    start = text.index(start_heading)
    end = text.index(end_heading, start)
    return text[start:end]


def doc_findings(text):
    """What the workflow-patch.md prose must say about the tests replacement
    (AC-1). Returns the list of missing items; an empty list is a pass."""
    missing = []
    try:
        section = _flat(_section(text, "## `requirements_patch`", "## `step_patches`"))
    except ValueError:
        return ["the requirements_patch section is missing"]
    for token in ("`tests_replace`", "`from`", "`to`", "`tests_contains`", "`expected-mismatch`"):
        if token not in section:
            missing.append(f"requirements_patch section does not mention {token}")
    if not re.search(r"[Ee]very `from`[^.]*`tests_contains`", section):
        missing.append("the binding of every `from` to `tests_contains` is not stated")
    if not re.search(r"`tests_replace` is applied before `tests_append`", section):
        missing.append("the application order (tests_replace before tests_append) is not stated")
    if not re.search(r"(at|in) the same position", section):
        missing.append("the in-place replacement is not stated")
    if not re.search(r"not (be )?duplicate", section):
        missing.append("the no-duplicate rule is not stated")
    if not re.search(r"[Aa]pplication rule 3", section):
        missing.append("the expectation check does not cite Application rule 3")

    m = re.search(r"The only operations permitted under `set`.*?patchable\.", section)
    if m is None:
        missing.append("the sentence listing the operations permitted under `set` is missing")
    else:
        sentence = m.group(0)
        for token in ("`_append`", "`tests_replace`", "`status`", "`tbd_reason`", "`excluded_reason`"):
            if token not in sentence:
                missing.append(f"the permitted-operations sentence does not list {token}")

    try:
        rules = _section(text, "## Application rules", "## Interrupted authorization-spend recovery")
    except ValueError:
        return missing + ["the Application rules section is missing"]
    numbered = re.findall(r"^(\d+)\. ", rules, re.MULTILINE)
    if numbered != [str(n) for n in range(1, 19)]:
        missing.append(f"the numbered application rules are {numbered}, not 1 to 18")
    if "All eighteen rules apply" not in rules:
        missing.append("the 'All eighteen rules apply' statement is gone")
    return missing


class TestWorkflowPatchDocumentsTestsReplace(unittest.TestCase):
    """AC-1."""

    @classmethod
    def setUpClass(cls):
        cls.text = WORKFLOW_PATCH_DOC.read_text(encoding="utf-8")

    def test_document_describes_the_tests_replacement_and_keeps_eighteen_rules(self):
        self.assertEqual(doc_findings(self.text), [])

    def test_detector_fires_on_a_copy_without_the_replacement(self):
        # Non-vacuity: the same detector over a synthetic copy that lacks the
        # tests replacement must report findings.
        stripped = self.text.replace("tests_replace", "tests_other")
        self.assertNotEqual(doc_findings(stripped), [])

    def test_detector_fires_on_a_copy_with_a_nineteenth_rule(self):
        extra = self.text.replace(
            "## Interrupted authorization-spend recovery",
            "19. A nineteenth rule.\n\n## Interrupted authorization-spend recovery",
            1,
        )
        self.assertTrue(any("1 to 18" in f for f in doc_findings(extra)))

    def test_permitted_operations_sentence_keeps_the_append_forms_and_assignments(self):
        section = _flat(_section(self.text, "## `requirements_patch`", "## `step_patches`"))
        sentence = re.search(r"The only operations permitted under `set`.*?patchable\.", section).group(0)
        self.assertIn("`tasks`", sentence)
        self.assertIn("`tests`", sentence)
        self.assertIn("direct assignment of", sentence)


# ---------------------------------------------------------------------------
# AC-2: structural check
# ---------------------------------------------------------------------------

class TestStructuralCheckOfTestsReplace(unittest.TestCase):
    """AC-2 (TM-3)."""

    PAIR = {"from": "TS1", "to": "TS-1"}
    EXPECTED = {"tests_contains": ["TS1"]}

    def assertAccepted(self, entry):
        errors = _structural_errors({"FR1": entry})
        self.assertEqual(errors, [], errors)

    def assertRejected(self, entry):
        errors = _structural_errors({"FR1": entry})
        self.assertTrue(errors, f"expected a requirements_patch error for {entry!r}")
        self.assertEqual(_codes(errors), {"requirements_patch"}, errors)
        self.assertTrue(
            all("FR1" in e["message"] for e in errors),
            f"every error must name the requirement entry: {errors}",
        )

    def test_a_well_formed_replacement_is_accepted(self):
        self.assertAccepted(_entry({"tests_replace": [self.PAIR]}, self.EXPECTED))

    def test_several_pairs_each_listed_in_the_expectation_are_accepted(self):
        pairs = [{"from": "TS1", "to": "TS-1"}, {"from": "TS2", "to": "TS-2"}]
        expected = {"tests_contains": ["TS1", "TS2", "TS5"]}
        self.assertAccepted(_entry({"tests_replace": pairs}, expected))

    def test_replacement_together_with_the_existing_keys_is_accepted(self):
        set_block = {
            "tests_replace": [self.PAIR],
            "tests_append": ["TS-9"],
            "tasks_append": ["task0007"],
            "status": "ok",
        }
        self.assertAccepted(_entry(set_block, self.EXPECTED))

    def test_an_expectation_without_a_replacement_is_accepted(self):
        self.assertAccepted(_entry({"tests_append": ["TS-9"]}, {"tests_contains": ["TS1"]}))

    def test_the_existing_append_forms_are_still_accepted(self):
        self.assertAccepted(_entry({"tasks_append": ["task0007"], "tests_append": ["TS-9"]}, {"tasks_contains": ["task0003"]}))

    def test_other_keys_remain_disallowed(self):
        errors = _structural_errors({"FR1": _entry({"tests_remove": ["TS1"]})})
        self.assertEqual(_codes(errors), {"requirements_patch"})
        self.assertIn("tests_remove", errors[0]["message"])

    def test_a_value_that_is_not_a_list_is_rejected(self):
        for value in ("TS1", {"from": "TS1", "to": "TS-1"}, None, 3, True):
            with self.subTest(value=value):
                self.assertRejected(_entry({"tests_replace": value}, self.EXPECTED))

    def test_an_empty_list_is_rejected(self):
        self.assertRejected(_entry({"tests_replace": []}, self.EXPECTED))

    def test_a_pair_that_is_not_a_mapping_is_rejected(self):
        for pair in ("TS1", ["TS1", "TS-1"], None, 7):
            with self.subTest(pair=pair):
                self.assertRejected(_entry({"tests_replace": [pair]}, self.EXPECTED))

    def test_a_pair_missing_from_or_to_is_rejected(self):
        for pair in ({"from": "TS1"}, {"to": "TS-1"}, {}):
            with self.subTest(pair=pair):
                self.assertRejected(_entry({"tests_replace": [pair]}, self.EXPECTED))

    def test_a_pair_with_an_empty_or_non_string_id_is_rejected(self):
        for pair in (
            {"from": "", "to": "TS-1"},
            {"from": "TS1", "to": ""},
            {"from": 1, "to": "TS-1"},
            {"from": "TS1", "to": None},
            {"from": ["TS1"], "to": "TS-1"},
        ):
            with self.subTest(pair=pair):
                self.assertRejected(_entry({"tests_replace": [pair]}, {"tests_contains": ["TS1", ""]}))

    def test_a_pair_whose_from_equals_its_to_is_rejected(self):
        self.assertRejected(
            _entry({"tests_replace": [{"from": "TS1", "to": "TS1"}]}, self.EXPECTED)
        )

    def test_a_from_repeated_within_one_entry_is_rejected(self):
        pairs = [{"from": "TS1", "to": "TS-1"}, {"from": "TS1", "to": "TS-one"}]
        self.assertRejected(_entry({"tests_replace": pairs}, self.EXPECTED))

    def test_a_from_absent_from_the_expectation_is_rejected(self):
        pairs = [{"from": "TS1", "to": "TS-1"}, {"from": "TS2", "to": "TS-2"}]
        self.assertRejected(_entry({"tests_replace": pairs}, {"tests_contains": ["TS1"]}))

    def test_a_replacement_without_any_expectation_is_rejected(self):
        self.assertRejected(_entry({"tests_replace": [self.PAIR]}))
        self.assertRejected(_entry({"tests_replace": [self.PAIR]}, {}))
        self.assertRejected(_entry({"tests_replace": [self.PAIR]}, {"tasks_contains": ["task0003"]}))

    def test_a_replacement_whose_expectation_is_not_a_list_is_rejected(self):
        for value in ("TS1", {"TS1": 1}, None, 5):
            with self.subTest(value=value):
                self.assertRejected(_entry({"tests_replace": [self.PAIR]}, {"tests_contains": value}))

    def test_an_expectation_that_is_not_a_list_of_strings_is_rejected(self):
        for value in ("TS1", ["TS1", 2], [None], {"a": 1}, None):
            with self.subTest(value=value):
                self.assertRejected(_entry({"tests_append": ["TS-9"]}, {"tests_contains": value}))

    def test_malformed_entries_never_raise(self):
        for rpatch in (
            {"set": "tests_replace"},
            {"set": ["tests_replace"]},
            {"set": None, "expected": ["tests_contains"]},
            {"set": {"tests_replace": [{"from": {}, "to": []}]}, "expected": {"tests_contains": [{}]}},
        ):
            with self.subTest(rpatch=rpatch):
                VWO.validate_workflow_patch(_patch_with({"FR1": rpatch}))


# ---------------------------------------------------------------------------
# AC-3: dry-run expectation check
# ---------------------------------------------------------------------------

class TestDryRunExpectationCheck(unittest.TestCase):
    """AC-3 (TM-3)."""

    @classmethod
    def setUpClass(cls):
        cls.patch = _read_json(MISMATCH_CASE / "input.json")
        cls.workflow = _read_json(MISMATCH_CASE / "workflow.json")
        cls.digest_source = _read_json(MISMATCH_CASE / "digest-source.json")

    def _dry_run(self, patch=None, workflow=None):
        return VWO.validate_workflow_patch(
            self.patch if patch is None else patch,
            workflow=self.workflow if workflow is None else workflow,
            digest_source=self.digest_source,
            dry_run=True,
        )

    def test_fixture_is_rejected_with_expected_mismatch_and_nothing_else(self):
        errors = self._dry_run()
        self.assertEqual(_codes(errors), {"expected-mismatch"}, errors)
        self.assertNotIn("stale-input-digest", _codes(errors))
        self.assertNotIn("stale-workflow-blob", _codes(errors))
        self.assertIn("FR1", errors[0]["message"])
        self.assertIn("tests_contains", errors[0]["message"])

    def test_fixture_exits_1_through_the_cli_with_only_expected_mismatch(self):
        result = _run_cli(
            [
                "--kind", "workflow-patch",
                "--worker", "implementation-planner",
                "--input", str(MISMATCH_CASE / "input.json"),
                "--workflow", str(MISMATCH_CASE / "workflow.json"),
                "--digest-source", str(MISMATCH_CASE / "digest-source.json"),
                "--dry-run-apply",
            ]
        )
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(_codes(json.loads(result.stdout)["errors"]), {"expected-mismatch"})

    def test_fixture_is_discoverable_by_the_data_driven_runner(self):
        self.assertTrue((MISMATCH_CASE / "DRY_RUN_APPLY").exists())
        self.assertTrue(MISMATCH_CASE.name.startswith("invalid-"))

    def test_the_same_patch_passes_when_every_expected_id_is_present(self):
        workflow = copy.deepcopy(self.workflow)
        workflow["requirements"]["FR1"]["tests"] = ["TS1"]
        self.assertEqual(self._dry_run(workflow=workflow), [])

    def test_a_single_absent_id_among_present_ones_is_rejected(self):
        patch = copy.deepcopy(self.patch)
        patch["requirements_patch"]["entries"]["FR1"]["expected"]["tests_contains"] = ["TS-1", "TS-9"]
        patch["requirements_patch"]["entries"]["FR1"]["set"]["tests_replace"] = [
            {"from": "TS-1", "to": "TS-one"},
            {"from": "TS-9", "to": "TS-nine"},
        ]
        errors = self._dry_run(patch=patch)
        self.assertEqual(_codes(errors), {"expected-mismatch"}, errors)

    def test_an_empty_expectation_list_is_satisfied(self):
        patch = copy.deepcopy(self.patch)
        patch["requirements_patch"]["entries"]["FR1"] = _entry(
            {"tests_append": ["TS-9"]}, {"tests_contains": []}
        )
        self.assertEqual(self._dry_run(patch=patch), [])

    def test_the_tasks_contains_expectation_is_unchanged(self):
        patch = copy.deepcopy(self.patch)
        patch["requirements_patch"]["entries"]["FR1"] = _entry(
            {"tests_append": ["TS-9"]}, {"tasks_contains": ["task0099"]}
        )
        self.assertEqual(_codes(self._dry_run(patch=patch)), {"expected-mismatch"})

    def test_a_workflow_requirement_without_tests_does_not_raise(self):
        workflow = copy.deepcopy(self.workflow)
        workflow["requirements"]["FR1"].pop("tests")
        self.assertEqual(_codes(self._dry_run(workflow=workflow)), {"expected-mismatch"})

    def test_a_malformed_workflow_tests_value_does_not_raise(self):
        workflow = copy.deepcopy(self.workflow)
        workflow["requirements"]["FR1"]["tests"] = "TS1"
        self._dry_run(workflow=workflow)


# ---------------------------------------------------------------------------
# AC-4: in-memory application
# ---------------------------------------------------------------------------

class TestInMemoryApplication(unittest.TestCase):
    """AC-4."""

    def test_from_is_replaced_by_to_at_the_same_position(self):
        req = _applied_tests(["TS0", "TS1", "TS2"], {"tests_replace": [{"from": "TS1", "to": "TS-1"}]})
        self.assertEqual(req["tests"], ["TS0", "TS-1", "TS2"])

    def test_several_pairs_replace_each_in_place(self):
        pairs = [{"from": "TS1", "to": "TS-1"}, {"from": "TS3", "to": "TS-3"}]
        req = _applied_tests(["TS1", "TS2", "TS3"], {"tests_replace": pairs})
        self.assertEqual(req["tests"], ["TS-1", "TS2", "TS-3"])

    def test_from_is_removed_without_duplicating_an_existing_to(self):
        req = _applied_tests(["TS1", "TS-1", "TS2"], {"tests_replace": [{"from": "TS1", "to": "TS-1"}]})
        self.assertEqual(req["tests"], ["TS-1", "TS2"])
        req = _applied_tests(["TS-1", "TS2", "TS1"], {"tests_replace": [{"from": "TS1", "to": "TS-1"}]})
        self.assertEqual(req["tests"], ["TS-1", "TS2"])

    def test_tests_replace_is_applied_before_tests_append_whatever_the_key_order(self):
        # Appending the old ID after the replacement keeps it; had the append
        # run first, the replacement would have consumed it.
        for set_block in (
            {"tests_replace": [{"from": "TS1", "to": "TS-1"}], "tests_append": ["TS1", "TS-9"]},
            {"tests_append": ["TS1", "TS-9"], "tests_replace": [{"from": "TS1", "to": "TS-1"}]},
        ):
            with self.subTest(keys=list(set_block)):
                req = _applied_tests(["TS1"], set_block)
                self.assertEqual(req["tests"], ["TS-1", "TS1", "TS-9"])

    def test_an_absent_from_leaves_tests_unchanged(self):
        req = _applied_tests(["TS2"], {"tests_replace": [{"from": "TS1", "to": "TS-1"}]})
        self.assertEqual(req["tests"], ["TS2"])

    def test_the_tests_replace_key_is_not_stored_on_the_requirement(self):
        req = _applied_tests(["TS1"], {"tests_replace": [{"from": "TS1", "to": "TS-1"}]})
        self.assertNotIn("tests_replace", req)

    def test_the_input_workflow_is_not_mutated(self):
        workflow = _workflow_with_tests(["TS1"])
        before = copy.deepcopy(workflow)
        patch = {
            "operation": "append_rework",
            "requirements_patch": {"entries": {"FR1": {"set": {"tests_replace": [{"from": "TS1", "to": "TS-1"}]}}}},
        }
        VWO.apply_patch(workflow, patch)
        self.assertEqual(workflow, before)

    def test_a_requirement_with_only_tests_append_behaves_as_before(self):
        req = _applied_tests(["TS1"], {"tests_append": ["TS-9"]})
        self.assertEqual(req["tests"], ["TS1", "TS-9"])

    def test_tasks_and_direct_assignments_are_unchanged(self):
        req = _applied_tests(
            ["TS1"],
            {
                "tests_replace": [{"from": "TS1", "to": "TS-1"}],
                "tasks_append": ["task0007"],
                "status": "tbd",
                "tbd_reason": "waiting",
                "excluded_reason": None,
            },
        )
        self.assertEqual(req["tests"], ["TS-1"])
        self.assertEqual(req["tasks"], ["task0001", "task0007"])
        self.assertEqual(req["status"], "tbd")
        self.assertEqual(req["tbd_reason"], "waiting")
        self.assertIsNone(req["excluded_reason"])

    def test_other_requirements_are_untouched(self):
        workflow = _workflow_with_tests(["TS1"])
        workflow["requirements"]["FR2"] = {"status": "ok", "tasks": [], "tests": ["TS1"], "title": "y"}
        patch = {
            "operation": "append_rework",
            "requirements_patch": {"entries": {"FR1": {"set": {"tests_replace": [{"from": "TS1", "to": "TS-1"}]}}}},
        }
        applied = VWO.apply_patch(workflow, patch)
        self.assertEqual(applied["requirements"]["FR2"]["tests"], ["TS1"])

    def test_malformed_pairs_do_not_raise(self):
        for value in (None, "TS1", [None], [{"from": 1}], [{"from": {}, "to": []}]):
            with self.subTest(value=value):
                _applied_tests(["TS1"], {"tests_replace": value})


# ---------------------------------------------------------------------------
# AC-5: the valid-docs-only-round fixture
# ---------------------------------------------------------------------------

DOC_ORIGIN_KINDS = {"review", "verify"}


class TestDocsOnlyRoundFixture(unittest.TestCase):
    """AC-5 (TS-1)."""

    @classmethod
    def setUpClass(cls):
        cls.result = _read_json(DOCS_ONLY_CASE / "input.json")
        cls.envelope = _read_json(DOCS_ONLY_CASE / "envelope.json")
        cls.workflow = _read_json(DOCS_ONLY_CASE / "workflow.json")
        cls.digest_source = _read_json(DOCS_ONLY_CASE / "digest-source.json")
        cls.patch = cls.result["workflow_patch"]

    def _validate(self, result=None, envelope=None, workflow=None, digest_source=None):
        return VWO.validate_worker_result(
            self.result if result is None else result,
            "rework-planner",
            envelope=self.envelope if envelope is None else envelope,
            workflow=self.workflow if workflow is None else workflow,
            digest_source=self.digest_source if digest_source is None else digest_source,
            dry_run=True,
        )

    def test_fixture_exits_0_with_dry_run_apply_through_the_cli(self):
        result = _run_cli(
            [
                "--kind", "worker-result",
                "--worker", "rework-planner",
                "--input", str(DOCS_ONLY_CASE / "input.json"),
                "--input-envelope", str(DOCS_ONLY_CASE / "envelope.json"),
                "--workflow", str(DOCS_ONLY_CASE / "workflow.json"),
                "--digest-source", str(DOCS_ONLY_CASE / "digest-source.json"),
                "--dry-run-apply",
            ]
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_validator_reports_no_error(self):
        self.assertEqual(self._validate(), [])

    def test_fixture_is_discoverable_by_the_data_driven_runner(self):
        self.assertTrue((DOCS_ONLY_CASE / "DRY_RUN_APPLY").exists())
        self.assertTrue(DOCS_ONLY_CASE.name.startswith("valid-"))

    def test_the_result_is_a_completed_rework_planner_result(self):
        self.assertEqual(self.result["status"], "completed")
        self.assertEqual(self.result["worker"], "rework-planner")
        self.assertIsNone(self.result["mode_echo"])

    def test_the_patch_is_an_append_with_empty_task_entries(self):
        self.assertEqual(self.patch["operation"], "append_rework")
        tasks_patch = self.patch["tasks_patch"]
        self.assertEqual(tasks_patch["mode"], "append")
        self.assertEqual(tasks_patch["expected_next_task_id"], "task0004")
        self.assertEqual(tasks_patch["expected_next_task_id"], VWO.next_task_id_after(self.workflow))
        self.assertFalse(tasks_patch.get("entries"))

    def test_the_only_step_patch_returns_verify_to_pending(self):
        self.assertEqual(
            self.patch["step_patches"],
            [{"step_id": "verify", "expected": {"status": "failed"}, "set": {"status": "pending"}}],
        )

    def test_the_implement_base_commit_is_preserved(self):
        self.assertIn("workflow.implement.base_commit", self.patch["preserve"])

    def test_every_tests_replace_pair_is_bound_to_its_expectation(self):
        entries = self.patch["requirements_patch"]["entries"]
        self.assertGreaterEqual(len(entries), 2)
        for fr_id, rpatch in entries.items():
            with self.subTest(requirement=fr_id):
                pairs = rpatch["set"]["tests_replace"]
                self.assertTrue(pairs)
                expected = rpatch["expected"]["tests_contains"]
                current = self.workflow["requirements"][fr_id]["tests"]
                for pair in pairs:
                    self.assertIn(pair["from"], expected)
                    self.assertIn(pair["from"], current)
                    self.assertEqual(pair["from"].replace("TS", "TS-", 1), pair["to"])
                    self.assertIsNone(re.match(r"^TS-", pair["from"]))

    def test_the_workflow_is_at_the_failed_verify_with_three_merged_tasks(self):
        steps = {s["id"]: s for s in self.workflow["workflow"]}
        self.assertEqual(steps["implement"]["status"], "completed")
        self.assertEqual(steps["review"]["status"], "completed")
        self.assertEqual(steps["verify"]["status"], "failed")
        self.assertEqual(sorted(self.workflow["tasks"]), ["task0001", "task0002", "task0003"])
        for item in steps["verify"]["failed_items"]:
            self.assertIn(item["category"], VWO.FAILED_ITEM_CATEGORY_VALUES)

    def test_the_base_fields_match_the_digest_source(self):
        self.assertEqual(self.patch["base_workflow_blob"], self.digest_source["workflow_blob"])
        self.assertEqual(self.patch["base_input_digest"], VWO.normalize_json_sha256(self.digest_source))
        self.assertEqual(self.result["input_revision"]["input_digest"], self.envelope["input_revision"]["input_digest"])

    def test_every_written_artifact_is_covered_by_a_replace_own_target(self):
        paths = [a["path"] for a in self.result["written_artifacts"]]
        self.assertEqual(len(paths), 3)
        targets = {t["path"]: t for t in self.envelope["write_policy"]["targets"]}
        for path in paths:
            with self.subTest(path=path):
                self.assertFalse(path.startswith("/"))
                self.assertIn(path, targets)
                self.assertEqual(targets[path]["action"], "replace_own")
                self.assertTrue(targets[path]["expect_digest"])
        self.assertEqual(self.envelope["allowed_write_roots"], ["feature-docs/docs-only-demo/tasks"])

    def test_the_envelope_indexes_the_pre_rename_ids(self):
        index = self.envelope["verification_index"]
        for rpatch in self.patch["requirements_patch"]["entries"].values():
            for pair in rpatch["set"]["tests_replace"]:
                self.assertIn(pair["from"], index)
                self.assertNotIn(pair["to"], index)

    def test_the_payload_declares_the_document_corrections(self):
        payload = self.result["payload"]
        self.assertEqual(payload["rework_index"], {})
        self.assertTrue(payload["shared_contract_rationale"])
        corrections = payload["doc_corrections"]
        self.assertTrue(corrections)
        entry = corrections[0]
        self.assertEqual(entry["origin_kind"], "verify")
        self.assertIn(entry["origin_kind"], DOC_ORIGIN_KINDS)
        verify = next(s for s in self.workflow["workflow"] if s["id"] == "verify")
        self.assertIn(entry["origin_id"], [i["id"] for i in verify["failed_items"]])
        self.assertEqual(
            entry["documents"], ["VERIFICATION.md", "tasks/task0001.md", "tasks/task0003.md"]
        )
        renames = {(p["from"], p["to"]) for p in entry["scenario_renames"]}
        replaced = {
            (p["from"], p["to"])
            for rpatch in self.patch["requirements_patch"]["entries"].values()
            for p in rpatch["set"]["tests_replace"]
        }
        self.assertEqual(renames, replaced)
        written = {a["path"] for a in self.result["written_artifacts"]}
        self.assertEqual(
            written,
            {f"feature-docs/{self.workflow['feature']}/{doc}" for doc in entry["documents"]},
        )

    def test_a_stale_base_input_digest_is_still_caught(self):
        # Non-vacuity: the dry run really inspects this fixture.
        result = copy.deepcopy(self.result)
        result["workflow_patch"]["base_input_digest"] = "sha256:" + "0" * 64
        self.assertIn("stale-input-digest", _codes(self._validate(result=result)))

    def test_an_expectation_that_misses_a_replaced_id_is_still_caught(self):
        result = copy.deepcopy(self.result)
        result["workflow_patch"]["requirements_patch"]["entries"]["FR1"]["expected"]["tests_contains"] = ["TS2"]
        self.assertIn("requirements_patch", _codes(self._validate(result=result)))

    def test_an_uncovered_written_artifact_is_still_caught(self):
        envelope = copy.deepcopy(self.envelope)
        envelope["write_policy"]["targets"] = envelope["write_policy"]["targets"][:2]
        envelope["allowed_write_roots"] = []
        self.assertIn("write_policy", _codes(self._validate(envelope=envelope)))


# ---------------------------------------------------------------------------
# AC-6: the fixture's patch applied in memory
# ---------------------------------------------------------------------------

class TestDocsOnlyRoundApplied(unittest.TestCase):
    """AC-6."""

    @classmethod
    def setUpClass(cls):
        cls.patch = _read_json(DOCS_ONLY_CASE / "input.json")["workflow_patch"]
        cls.before = _read_json(DOCS_ONLY_CASE / "workflow.json")
        cls.after = VWO.apply_patch(cls.before, cls.patch)

    @staticmethod
    def _steps(workflow):
        return {s["id"]: s for s in workflow["workflow"]}

    def test_no_task_is_added(self):
        self.assertEqual(self.after["tasks"], self.before["tasks"])

    def test_implement_stays_completed_and_review_is_unchanged(self):
        before, after = self._steps(self.before), self._steps(self.after)
        self.assertEqual(after["implement"], before["implement"])
        self.assertEqual(after["implement"]["status"], "completed")
        self.assertEqual(after["review"], before["review"])

    def test_verify_is_pending(self):
        self.assertEqual(self._steps(self.after)["verify"]["status"], "pending")

    def test_every_replaced_id_is_gone_and_its_replacement_present(self):
        entries = self.patch["requirements_patch"]["entries"]
        for fr_id, rpatch in entries.items():
            tests = self.after["requirements"][fr_id]["tests"]
            for pair in rpatch["set"]["tests_replace"]:
                with self.subTest(requirement=fr_id, old=pair["from"]):
                    self.assertNotIn(pair["from"], tests)
                    self.assertIn(pair["to"], tests)

    def test_replaced_ids_keep_their_positions(self):
        self.assertEqual(self.after["requirements"]["FR1"]["tests"], ["TS-1", "TS-2"])
        self.assertEqual(self.after["requirements"]["FR2"]["tests"], ["TS-3"])

    def test_the_preserved_base_commit_is_unchanged(self):
        self.assertEqual(
            VWO.get_preserve_value(self.after, "workflow.implement.base_commit"),
            VWO.get_preserve_value(self.before, "workflow.implement.base_commit"),
        )

    def test_the_input_workflow_is_not_mutated(self):
        self.assertEqual(self.before, _read_json(DOCS_ONLY_CASE / "workflow.json"))


# ---------------------------------------------------------------------------
# AC-7: standard library only
# ---------------------------------------------------------------------------

class TestOwnModuleStdlibOnly(unittest.TestCase):
    """AC-7."""

    def test_this_module_imports_only_the_standard_library(self):
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                imported.add((node.module or "").split(".")[0])
        self.assertTrue(imported)
        self.assertEqual(imported - set(sys.stdlib_module_names), set())

    def test_the_detector_would_flag_a_third_party_import(self):
        tree = ast.parse("import yaml\n")
        names = {alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
        self.assertNotEqual(names - set(sys.stdlib_module_names), set())


if __name__ == "__main__":
    unittest.main()
