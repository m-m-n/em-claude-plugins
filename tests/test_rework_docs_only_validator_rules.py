"""Unit tests for the three rework-docs-only rules of
em-workflow/scripts/validate-worker-output.py
(rework-docs-only-task-routing, task0004).

Rules pinned here (their contract prose is owned elsewhere; this module
asserts only the validator's rendering of them):

- feature-docs files rule (FR3, TM-1): in `append` mode (the mode bound to
  `append_rework`) a task entry any of whose `files` has `feature-docs` as
  its first normalized path segment is reported with code
  `rework-task-feature-docs`. `replace_planning` entries are not checked.
- no implement reset on a docs-only round (FR5, TM-2): an `append_rework`
  patch with absent or empty `tasks_patch.entries` that sets `implement`
  to `pending` is reported with code `docs-only-implement-reset`, at the
  structural layer (with and without `--dry-run-apply`, through both
  `--kind workflow-patch` and `--kind worker-result`).
- rename-aware coverage (FR6, FR7, TM-5): a `covered_by_existing` ID absent
  from `verification_index` passes only when a declared
  `payload.doc_corrections[].scenario_renames` pair maps a
  `verification_index` key (`from`) to it (`to`); otherwise code
  `rework-index`. Malformed declarations contribute no pair and never raise.

- tests_replace overlap (FR4, TM-4, rework-docs-only-medium-fixes task0003):
  a `requirements_patch` entry whose `set.tests_replace` has a `from` set and
  a `to` set that share an ID (a chain TS-1->TS-2, TS-2->TS-3 or a swap
  TS-1->TS-2, TS-2->TS-1) is reported with code `requirements_patch`, at the
  structural layer (with and without `--dry-run-apply`, through both
  `--kind workflow-patch` and `--kind worker-result`). Pairs that only share
  a `to` are not rejected by this check. Malformed shapes never raise.

Standard-library imports only. The module reads the validator script and the
fixtures under references/fixtures/worker-result/rework-planner/ that its
tasks own.
"""

import ast
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
FIXTURE_GROUP_DIR = (
    REPO_ROOT / "em-workflow" / "references" / "fixtures" / "worker-result" / "rework-planner"
)


def _load_module():
    spec = importlib.util.spec_from_file_location("validate_worker_output", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VWO = _load_module()

FEATURE_DOCS_CODE = "rework-task-feature-docs"
IMPLEMENT_RESET_CODE = "docs-only-implement-reset"
REWORK_INDEX_CODE = "rework-index"

DIGEST = "sha256:" + "a" * 64


def run_cli(args):
    cmd = [sys.executable, str(SCRIPT_PATH)] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True)


def _codes(errors):
    return [e["code"] for e in errors]


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def _entry(files):
    return {
        "complexity": "medium",
        "domains": ["auth"],
        "files": list(files),
        "initial_status": "pending",
        "plan": "tasks/task0007.md",
        "provenance": {"review_round": 2, "source": "review", "source_ids": ["abc123"]},
        "requirements": ["FR1"],
        "skills": ["backend-impl"],
        "title": "Fix auth bypass",
    }


IMPLEMENT_PENDING = {
    "expected": {"status": "completed"},
    "set": {"status": "pending"},
    "step_id": "implement",
}
REVIEW_PENDING = {
    "expected": {"status": "in_progress"},
    "set": {"status": "pending"},
    "step_id": "review",
}
VERIFY_PENDING = {
    "expected": {"status": "completed"},
    "set": {"status": "pending"},
    "step_id": "verify",
}

_ABSENT = object()


def _append_patch(entries=_ABSENT, step_patches=(IMPLEMENT_PENDING,)):
    tasks_patch = {"expected_next_task_id": "task0002", "mode": "append"}
    if entries is not _ABSENT:
        tasks_patch["entries"] = entries
    return {
        "base_input_digest": DIGEST,
        "base_workflow_blob": "8f17c04",
        "operation": "append_rework",
        "patch_id": "rework-p0001",
        "preserve": ["workflow.implement.base_commit"],
        "requirements_patch": None,
        "schema_version": 1,
        "step_patches": copy.deepcopy(list(step_patches)),
        "tasks_patch": tasks_patch,
    }


def _replace_planning_patch(entries, step_patches=()):
    return {
        "base_input_digest": DIGEST,
        "base_workflow_blob": "8f17c04",
        "operation": "replace_planning",
        "patch_id": "plan-p0001",
        "preserve": [],
        "requirements_patch": None,
        "schema_version": 1,
        "step_patches": copy.deepcopy(list(step_patches)),
        "tasks_patch": {"entries": entries, "mode": "replace_all"},
    }


def _dry_run_context(patch):
    """A small in-memory workflow.yaml and digest source, plus `patch` with
    its digest fields bound to them, so dry-run-apply is exercised without
    reading any fixture. The next free task id is task0002."""
    digest_source = {
        "answers_digest": "sha256:" + "2" * 64,
        "digest_inputs": {"feature-docs/example/SPEC.md": "sha256:" + "1" * 64},
        "mode": "interactive",
        "value_inputs": {"task_description": None},
        "worker": "rework-planner",
        "workflow_blob": "8f17c04",
        "write_policy_digest": "sha256:" + "3" * 64,
    }
    workflow = {
        "feature": "example",
        "project": {"license": "MIT"},
        "requirements": {"FR1": {"status": "ok", "tasks": [], "tests": [], "title": "x"}},
        "schema_version": 1,
        "tasks": {
            "task0001": {
                "branch": "em-workflow/example/task0001",
                "complexity": "low",
                "domains": [],
                "files": ["x.go"],
                "notes": None,
                "plan": "tasks/task0001.md",
                "requirements": ["FR1"],
                "skills": [],
                "status": "merged",
                "title": "existing",
            }
        },
        "workflow": [
            {"completed_at_commit": "aaa", "id": "create-spec", "status": "completed"},
            {"id": "design", "skipped_reason": "no UI", "status": "skipped"},
            {"id": "create-plan", "status": "pending"},
            {"base_commit": "deadbeef", "id": "implement", "status": "completed"},
            {"id": "review", "status": "in_progress"},
            {"id": "verify", "status": "completed"},
            {"id": "retrospect", "status": "pending"},
        ],
    }
    bound = copy.deepcopy(patch)
    bound["base_input_digest"] = VWO.normalize_json_sha256(digest_source)
    bound["base_workflow_blob"] = digest_source["workflow_blob"]
    return bound, workflow, digest_source


def _rework_envelope(verification_index):
    return {
        "allowed_write_roots": [],
        "input_revision": {"input_digest": DIGEST, "workflow_blob": "8f17c04"},
        "mode": "interactive",
        "phase": "create-plan",
        "request_id": "env-run-0001",
        "resolved_input_paths": {},
        "schema_version": 1,
        "verification_index": verification_index,
        "write_policy": {"targets": []},
    }


def _rework_result(
    *,
    files=("src/auth.go",),
    covered=("TS-3",),
    doc_corrections=_ABSENT,
    entries=_ABSENT,
    rework_index=_ABSENT,
    step_patches=(IMPLEMENT_PENDING,),
):
    if entries is _ABSENT:
        entries = {"task0007": _entry(files)}
    if rework_index is _ABSENT:
        rework_index = {
            "task0007": {
                "covered_by_existing": list(covered),
                "new_scenarios": [],
                "rationale": "covered by an existing scenario",
            }
        }
    payload = {
        "rework_index": rework_index,
        "shared_contract_rationale": "No new shared contract.",
    }
    if doc_corrections is not _ABSENT:
        payload["doc_corrections"] = doc_corrections
    patch = _append_patch(entries, step_patches)
    patch["tasks_patch"]["expected_next_task_id"] = "task0007"
    return {
        "blocking_reason": None,
        "input_revision": {"input_digest": DIGEST, "workflow_blob": "8f17c04"},
        "mode_echo": None,
        "payload": payload,
        "question_packet": None,
        "report": "done",
        "request_id": "run-0001",
        "schema_version": 1,
        "status": "completed",
        "warnings": [],
        "worker": "rework-planner",
        "workflow_patch": patch,
        "written_artifacts": [],
    }


def _validate_result(result, verification_index, **kwargs):
    return VWO.validate_worker_result(
        result,
        "rework-planner",
        envelope=_rework_envelope(verification_index),
        **kwargs,
    )


def _rename(frm, to):
    return {"from": frm, "to": to}


def _correction(*renames):
    return {
        "documents": ["VERIFICATION.md"],
        "origin_id": "abc123",
        "origin_kind": "review",
        "scenario_renames": list(renames),
    }


# ---------------------------------------------------------------------------
# AC-1 / AC-2: feature-docs files rule
# ---------------------------------------------------------------------------

class TestFeatureDocsFilesRule(unittest.TestCase):
    def _errors(self, files, mode="append"):
        return VWO.validate_task_entry("task0007", _entry(files), mode, None, None)

    def test_ac1_all_planning_documents_are_rejected(self):
        files = ["feature-docs/example/VERIFICATION.md", "feature-docs/example/tasks/task0003.md"]
        errors = self._errors(files)
        self.assertEqual(_codes(errors), [FEATURE_DOCS_CODE, FEATURE_DOCS_CODE])
        for path, error in zip(files, errors):
            self.assertIn("task0007", error["message"])
            self.assertIn(path, error["message"])

    def test_ac1_code_and_planning_documents_mixed_are_rejected(self):
        errors = self._errors(["src/auth.go", "feature-docs/example/IMPLEMENTATION.md"])
        self.assertEqual(_codes(errors), [FEATURE_DOCS_CODE])
        self.assertIn("feature-docs/example/IMPLEMENTATION.md", errors[0]["message"])
        self.assertNotIn("src/auth.go", errors[0]["message"])

    def test_ac1_leading_dot_slash_and_separator_forms_are_rejected(self):
        for path in (
            "./feature-docs/example/SPEC.md",
            "feature-docs\\example\\SPEC.md",
            ".\\feature-docs\\example\\SPEC.md",
            "feature-docs//example/SPEC.md",
            "./feature-docs",
            "feature-docs",
        ):
            with self.subTest(path=path):
                errors = self._errors([path])
                self.assertEqual(_codes(errors), [FEATURE_DOCS_CODE])
                self.assertIn(repr(path), errors[0]["message"])

    def test_ac1_rejected_through_an_append_rework_patch(self):
        patch = _append_patch({"task0007": _entry(["feature-docs/example/VERIFICATION.md"])})
        self.assertEqual(_codes(VWO.validate_workflow_patch(patch)), [FEATURE_DOCS_CODE])

    def test_ac1_replace_planning_entries_are_not_checked(self):
        self.assertEqual(self._errors(["feature-docs/example/SPEC.md"], mode="replace_all"), [])
        patch = _replace_planning_patch({"task0007": _entry(["feature-docs/example/SPEC.md"])})
        self.assertEqual(VWO.validate_workflow_patch(patch), [])

    def test_ac2_code_only_task_is_accepted(self):
        self.assertEqual(self._errors(["src/auth.go", "tests/auth_test.go"]), [])
        patch = _append_patch({"task0007": _entry(["src/auth.go"])})
        self.assertEqual(VWO.validate_workflow_patch(patch), [])

    def test_ac2_lookalike_paths_do_not_trigger_the_rule(self):
        for path in (
            "feature-docs-archive/x",
            "src/feature-docs/x",
            "feature-docs.md",
            "Feature-Docs/x",
            "docs/feature-docs",
        ):
            with self.subTest(path=path):
                self.assertEqual(self._errors([path]), [])


# ---------------------------------------------------------------------------
# AC-3: no implement reset on a docs-only round
# ---------------------------------------------------------------------------

class TestDocsOnlyImplementReset(unittest.TestCase):
    def test_ac3_empty_or_absent_entries_with_implement_pending_is_rejected(self):
        for label, entries in (("absent", _ABSENT), ("none", None), ("empty", {})):
            with self.subTest(entries=label):
                patch = _append_patch(entries)
                self.assertEqual(
                    _codes(VWO.validate_workflow_patch(patch)), [IMPLEMENT_RESET_CODE]
                )

    def test_ac3_rejection_names_the_offending_step_patch(self):
        patch = _append_patch({}, [REVIEW_PENDING, IMPLEMENT_PENDING])
        errors = VWO.validate_workflow_patch(patch)
        self.assertEqual(_codes(errors), [IMPLEMENT_RESET_CODE])
        self.assertIn("step_patches[1]", errors[0]["message"])

    def test_ac3_rejected_with_dry_run_apply(self):
        patch, workflow, digest_source = _dry_run_context(_append_patch({}))
        errors = VWO.validate_workflow_patch(
            patch, workflow=workflow, digest_source=digest_source, dry_run=True
        )
        self.assertEqual(_codes(errors), [IMPLEMENT_RESET_CODE])

    def test_ac3_rejected_through_worker_result_with_and_without_dry_run(self):
        result = _rework_result(entries={}, rework_index={})
        errors = _validate_result(result, {"TS-3": ["FR1"]})
        self.assertEqual(_codes(errors), [IMPLEMENT_RESET_CODE])
        self.assertIn("workflow_patch", errors[0]["message"])

        bound_patch, workflow, digest_source = _dry_run_context(result["workflow_patch"])
        bound_patch["tasks_patch"]["expected_next_task_id"] = "task0002"
        result["workflow_patch"] = bound_patch
        errors = _validate_result(
            result,
            {"TS-3": ["FR1"]},
            workflow=workflow,
            digest_source=digest_source,
            dry_run=True,
        )
        self.assertEqual(_codes(errors), [IMPLEMENT_RESET_CODE])

    def test_ac3_cli_workflow_patch_exits_1_with_the_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "input.json"
            input_path.write_text(json.dumps(_append_patch({})), encoding="utf-8")
            result = run_cli(
                ["--kind", "workflow-patch", "--worker", "rework-planner", "--input", str(input_path)]
            )
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertEqual(_codes(json.loads(result.stdout)["errors"]), [IMPLEMENT_RESET_CODE])

            bound, workflow, digest_source = _dry_run_context(_append_patch({}))
            input_path.write_text(json.dumps(bound), encoding="utf-8")
            (tmp_path / "workflow.json").write_text(json.dumps(workflow), encoding="utf-8")
            (tmp_path / "digest-source.json").write_text(json.dumps(digest_source), encoding="utf-8")
            result = run_cli(
                [
                    "--kind", "workflow-patch",
                    "--worker", "rework-planner",
                    "--input", str(input_path),
                    "--workflow", str(tmp_path / "workflow.json"),
                    "--digest-source", str(tmp_path / "digest-source.json"),
                    "--dry-run-apply",
                ]
            )
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertEqual(_codes(json.loads(result.stdout)["errors"]), [IMPLEMENT_RESET_CODE])

    def test_ac3_patch_with_entries_returning_implement_is_accepted(self):
        patch = _append_patch({"task0007": _entry(["src/auth.go"])})
        self.assertEqual(VWO.validate_workflow_patch(patch), [])
        bound, workflow, digest_source = _dry_run_context(
            _append_patch({"task0002": _entry(["src/auth.go"])})
        )
        self.assertEqual(
            VWO.validate_workflow_patch(
                bound, workflow=workflow, digest_source=digest_source, dry_run=True
            ),
            [],
        )

    def test_ac3_empty_entries_returning_only_the_origin_step_is_accepted(self):
        for label, step in (("verify", VERIFY_PENDING), ("review", REVIEW_PENDING)):
            with self.subTest(step=label):
                patch = _append_patch({}, [step])
                self.assertEqual(VWO.validate_workflow_patch(patch), [])
                bound, workflow, digest_source = _dry_run_context(patch)
                self.assertEqual(
                    VWO.validate_workflow_patch(
                        bound, workflow=workflow, digest_source=digest_source, dry_run=True
                    ),
                    [],
                )

    def test_ac3_empty_entries_with_implement_not_set_to_pending_is_accepted(self):
        step = {"expected": {}, "set": {"status": "completed"}, "step_id": "implement"}
        self.assertEqual(VWO.validate_workflow_patch(_append_patch({}, [step])), [])

    def test_ac3_rule_is_limited_to_append_rework(self):
        patch = _replace_planning_patch({}, [IMPLEMENT_PENDING])
        self.assertNotIn(IMPLEMENT_RESET_CODE, _codes(VWO.validate_workflow_patch(patch)))


# ---------------------------------------------------------------------------
# AC-4 / AC-5: rename-aware coverage
# ---------------------------------------------------------------------------

class TestRenameAwareCoverage(unittest.TestCase):
    PRE_RENAME_INDEX = {"TS3": ["FR1"]}

    def test_ac4_declared_rename_makes_the_renamed_id_covered(self):
        result = _rework_result(doc_corrections=[_correction(_rename("TS3", "TS-3"))])
        self.assertEqual(_validate_result(result, self.PRE_RENAME_INDEX), [])

    def test_ac4_undeclared_rename_is_rejected_with_a_message_naming_the_missing_declaration(self):
        for label, kwargs in (
            ("no doc_corrections", {}),
            ("empty doc_corrections", {"doc_corrections": []}),
            ("no scenario_renames", {"doc_corrections": [_correction()]}),
        ):
            with self.subTest(case=label):
                errors = _validate_result(_rework_result(**kwargs), self.PRE_RENAME_INDEX)
                self.assertEqual(_codes(errors), [REWORK_INDEX_CODE])
                self.assertIn("'TS-3'", errors[0]["message"])
                self.assertIn("no declared rename", errors[0]["message"])
                self.assertIn("verification index", errors[0]["message"])

    def test_ac4_declared_from_missing_from_verification_index_is_rejected(self):
        result = _rework_result(doc_corrections=[_correction(_rename("TS9", "TS-3"))])
        errors = _validate_result(result, self.PRE_RENAME_INDEX)
        self.assertEqual(_codes(errors), [REWORK_INDEX_CODE])

    def test_ac4_declared_to_that_differs_from_the_covered_id_is_rejected(self):
        result = _rework_result(doc_corrections=[_correction(_rename("TS3", "TS-4"))])
        errors = _validate_result(result, self.PRE_RENAME_INDEX)
        self.assertEqual(_codes(errors), [REWORK_INDEX_CODE])

    def test_ac4_reversed_pair_does_not_count(self):
        result = _rework_result(doc_corrections=[_correction(_rename("TS-3", "TS3"))])
        errors = _validate_result(result, self.PRE_RENAME_INDEX)
        self.assertEqual(_codes(errors), [REWORK_INDEX_CODE])

    def test_ac4_pair_found_in_any_doc_corrections_entry_counts(self):
        result = _rework_result(
            doc_corrections=[_correction(_rename("TS8", "TS-8")), _correction(_rename("TS3", "TS-3"))]
        )
        self.assertEqual(_validate_result(result, self.PRE_RENAME_INDEX), [])

    def test_ac4_id_that_is_a_verification_index_key_passes_without_any_declaration(self):
        self.assertEqual(_validate_result(_rework_result(), {"TS-3": ["FR1"]}), [])

    def test_ac4_only_the_renamed_id_is_excused(self):
        result = _rework_result(
            covered=("TS-3", "TS-7"), doc_corrections=[_correction(_rename("TS3", "TS-3"))]
        )
        errors = _validate_result(result, self.PRE_RENAME_INDEX)
        self.assertEqual(_codes(errors), [REWORK_INDEX_CODE])
        self.assertIn("'TS-7'", errors[0]["message"])

    def test_ac5_malformed_doc_corrections_shapes_are_judged_as_no_rename_declared(self):
        valid_pair = _rename("TS3", "TS-3")
        malformed = {
            "doc_corrections is a string": "TS3->TS-3",
            "doc_corrections is a number": 5,
            "doc_corrections is a mapping": {"scenario_renames": [valid_pair]},
            "entry is a string": ["TS3->TS-3"],
            "entry is null": [None],
            "entry is a list": [[valid_pair]],
            "scenario_renames is a string": [{"scenario_renames": "TS3->TS-3"}],
            "scenario_renames is a mapping": [{"scenario_renames": valid_pair}],
            "scenario_renames is null": [{"scenario_renames": None}],
            "pair is a string": [_correction("TS3->TS-3")],
            "pair is null": [_correction(None)],
            "pair is a list": [_correction(["TS3", "TS-3"])],
            "pair lacks from": [_correction({"to": "TS-3"})],
            "pair lacks to": [_correction({"from": "TS3"})],
            "from is empty": [_correction(_rename("", "TS-3"))],
            "to is empty": [_correction(_rename("TS3", ""))],
            "from is blank": [_correction(_rename("   ", "TS-3"))],
            "to is blank": [_correction(_rename("TS3", "  "))],
            "from is not a string": [_correction(_rename(3, "TS-3"))],
            "to is not a string": [_correction(_rename("TS3", ["TS-3"]))],
        }
        for label, doc_corrections in malformed.items():
            with self.subTest(case=label):
                result = _rework_result(doc_corrections=doc_corrections)
                errors = _validate_result(result, self.PRE_RENAME_INDEX)
                self.assertEqual(_codes(errors), [REWORK_INDEX_CODE])
                self.assertIn("no declared rename", errors[0]["message"])

    def test_ac5_a_malformed_declaration_does_not_hide_a_well_formed_pair(self):
        result = _rework_result(
            doc_corrections=[
                None,
                "junk",
                {"scenario_renames": "junk"},
                _correction("junk", {"from": "TS3"}, _rename("TS3", "TS-3")),
            ]
        )
        self.assertEqual(_validate_result(result, self.PRE_RENAME_INDEX), [])

    def test_ac5_malformed_shapes_through_the_cli_exit_1_not_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            result = _rework_result(doc_corrections="junk")
            (tmp_path / "input.json").write_text(json.dumps(result), encoding="utf-8")
            (tmp_path / "envelope.json").write_text(
                json.dumps(_rework_envelope(self.PRE_RENAME_INDEX)), encoding="utf-8"
            )
            completed = run_cli(
                [
                    "--kind", "worker-result",
                    "--worker", "rework-planner",
                    "--input", str(tmp_path / "input.json"),
                    "--input-envelope", str(tmp_path / "envelope.json"),
                ]
            )
            self.assertEqual(completed.returncode, 1, completed.stdout + completed.stderr)
            self.assertEqual(_codes(json.loads(completed.stdout)["errors"]), [REWORK_INDEX_CODE])


# ---------------------------------------------------------------------------
# AC-6: the six fixtures
# ---------------------------------------------------------------------------

# fixture case -> codes the validator must report for it (empty = passes)
FIXTURE_EXPECTED_CODES = {
    "invalid-task-files-feature-docs-only": [FEATURE_DOCS_CODE, FEATURE_DOCS_CODE],
    "invalid-task-files-code-and-feature-docs": [FEATURE_DOCS_CODE],
    "valid-task-files-code-only": [],
    "invalid-docs-only-round-resets-implement": [IMPLEMENT_RESET_CODE],
    "valid-mixed-round-renamed-scenario-declared": [],
    "invalid-mixed-round-renamed-scenario-undeclared": [REWORK_INDEX_CODE],
}


class TestFixtures(unittest.TestCase):
    def _run(self, case):
        case_dir = FIXTURE_GROUP_DIR / case
        return run_cli(
            [
                "--kind", "worker-result",
                "--worker", "rework-planner",
                "--input", str(case_dir / "input.json"),
                "--input-envelope", str(case_dir / "envelope.json"),
            ]
        )

    def test_ac6_the_six_fixtures_exist_with_input_and_envelope(self):
        self.assertEqual(len(FIXTURE_EXPECTED_CODES), 6)
        for case in FIXTURE_EXPECTED_CODES:
            for name in ("input.json", "envelope.json"):
                with self.subTest(case=case, file=name):
                    self.assertTrue((FIXTURE_GROUP_DIR / case / name).is_file())

    def test_ac6_prefix_matches_the_exit_code_and_the_reported_codes(self):
        for case, expected_codes in FIXTURE_EXPECTED_CODES.items():
            with self.subTest(case=case):
                completed = self._run(case)
                if case.startswith("valid-"):
                    self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
                else:
                    self.assertEqual(completed.returncode, 1, completed.stdout + completed.stderr)
                    self.assertEqual(
                        _codes(json.loads(completed.stdout)["errors"]), expected_codes
                    )

    def test_ac6_no_fixture_uses_tests_replace(self):
        for case in FIXTURE_EXPECTED_CODES:
            for name in ("input.json", "envelope.json"):
                with self.subTest(case=case, file=name):
                    text = (FIXTURE_GROUP_DIR / case / name).read_text(encoding="utf-8")
                    self.assertNotIn("tests_replace", text)

    def test_ac6_mixed_round_pair_differs_only_in_the_rename_declaration(self):
        declared = json.loads(
            (FIXTURE_GROUP_DIR / "valid-mixed-round-renamed-scenario-declared" / "input.json").read_text(
                encoding="utf-8"
            )
        )
        undeclared = json.loads(
            (
                FIXTURE_GROUP_DIR / "invalid-mixed-round-renamed-scenario-undeclared" / "input.json"
            ).read_text(encoding="utf-8")
        )
        self.assertTrue(declared["payload"]["doc_corrections"][0]["scenario_renames"])
        for entry in undeclared["payload"]["doc_corrections"]:
            self.assertFalse(entry.get("scenario_renames"))
        declared["payload"].pop("doc_corrections")
        undeclared["payload"].pop("doc_corrections")
        self.assertEqual(declared, undeclared)
        for case in (
            "valid-mixed-round-renamed-scenario-declared",
            "invalid-mixed-round-renamed-scenario-undeclared",
        ):
            envelope = json.loads(
                (FIXTURE_GROUP_DIR / case / "envelope.json").read_text(encoding="utf-8")
            )
            self.assertIn("TS3", envelope["verification_index"])
            self.assertNotIn("TS-3", envelope["verification_index"])


# ---------------------------------------------------------------------------
# tests_replace overlap (FR4): TestTestsReplaceOverlap
# ---------------------------------------------------------------------------

REQUIREMENTS_PATCH_CODE = "requirements_patch"
FIXTURES_ROOT = REPO_ROOT / "em-workflow" / "references" / "fixtures"

CHAIN = [_rename("TS-1", "TS-2"), _rename("TS-2", "TS-3")]
SWAP = [_rename("TS-1", "TS-2"), _rename("TS-2", "TS-1")]
DISJOINT = [_rename("TS1", "TS-1"), _rename("TS2", "TS-2")]
SHARED_TO = [_rename("TS1", "X"), _rename("TS2", "X")]

# new fixture -> (its tests_replace pairs, the IDs both sets share)
OVERLAP_FIXTURES = {
    "invalid-docs-only-round-tests-replace-chain": (CHAIN, ["TS-2"]),
    "invalid-docs-only-round-tests-replace-swap": (SWAP, ["TS-1", "TS-2"]),
}
OVERLAP_SOURCE_FIXTURE = "valid-docs-only-round"

# (route, dry_run): the four ways the structural layer is reached
ROUTES = [
    (route, dry_run)
    for route in ("workflow-patch", "worker-result")
    for dry_run in (False, True)
]

OVERLAP_INDEX = {"TS-1": ["FR1"], "TS-2": ["FR1"], "TS-3": ["FR1"]}


def _messages(errors):
    return [e["message"] for e in errors]


def _replace_entry(pairs, contains=_ABSENT):
    """One requirements_patch entry replacing tests by `pairs`. `contains`
    defaults to every string `from`, so the expectation is never the defect."""
    if contains is _ABSENT:
        contains = [
            p["from"] for p in pairs if isinstance(p, dict) and isinstance(p.get("from"), str)
        ]
    return {
        "expected": {"tests_contains": copy.deepcopy(contains)},
        "set": {"tests_replace": copy.deepcopy(pairs)},
    }


def _replace_patch(entries):
    """A docs-only-round append_rework patch (verify back to pending) that
    carries `entries` as its requirements_patch."""
    patch = _append_patch({}, [VERIFY_PENDING])
    patch["requirements_patch"] = {"entries": copy.deepcopy(entries), "mode": "merge_entries"}
    return patch


def _dry_run_inputs(patch):
    """`_dry_run_context` for `patch`, with a workflow.yaml that already
    satisfies every `expected` of the patch (step statuses, the requirement's
    current tests, the registered task ids below expected_next_task_id), so
    the only thing --dry-run-apply can add is a finding about the patch
    itself."""
    bound, workflow, digest_source = _dry_run_context(patch)
    step_patches = bound.get("step_patches")
    for sp in step_patches if isinstance(step_patches, list) else []:
        status = (sp.get("expected") or {}).get("status")
        for step in workflow["workflow"]:
            if status is not None and step["id"] == sp.get("step_id"):
                step["status"] = status
    entries = (bound.get("requirements_patch") or {}).get("entries") or {}
    for fr_id, rpatch in entries.items():
        contains = (rpatch.get("expected") or {}).get("tests_contains")
        if isinstance(contains, list):
            req = workflow["requirements"].setdefault(
                fr_id, {"status": "ok", "tasks": [], "tests": [], "title": "x"}
            )
            req["tests"] = [c for c in contains if isinstance(c, str)]
    next_id = int(bound["tasks_patch"]["expected_next_task_id"][len("task"):])
    for n in range(2, next_id):
        workflow["tasks"][f"task{n:04d}"] = copy.deepcopy(workflow["tasks"]["task0001"])
    return bound, workflow, digest_source


def _worker_result_with(patch):
    result = _rework_result(entries={}, rework_index={}, step_patches=(VERIFY_PENDING,))
    result["workflow_patch"] = copy.deepcopy(patch)
    return result


def _errors_via(route, dry_run, patch):
    """In-process findings for `patch` on one of the four routes."""
    if route == "workflow-patch":
        if dry_run:
            bound, workflow, digest_source = _dry_run_inputs(patch)
            return VWO.validate_workflow_patch(
                bound, workflow=workflow, digest_source=digest_source, dry_run=True
            )
        return VWO.validate_workflow_patch(copy.deepcopy(patch))
    result = _worker_result_with(patch)
    if dry_run:
        bound, workflow, digest_source = _dry_run_inputs(patch)
        result["workflow_patch"] = bound
        return _validate_result(
            result, OVERLAP_INDEX, workflow=workflow, digest_source=digest_source, dry_run=True
        )
    return _validate_result(result, OVERLAP_INDEX)


def _cli_via(tmp_path, route, dry_run, document, envelope=None):
    """Runs the validator CLI on `document` (a workflow patch for
    `workflow-patch`, a worker result for `worker-result`)."""
    document = copy.deepcopy(document)
    args = ["--kind", route, "--worker", "rework-planner"]
    if dry_run:
        patch = document["workflow_patch"] if route == "worker-result" else document
        bound, workflow, digest_source = _dry_run_inputs(patch)
        if route == "worker-result":
            document["workflow_patch"] = bound
        else:
            document = bound
        (tmp_path / "workflow.json").write_text(json.dumps(workflow), encoding="utf-8")
        (tmp_path / "digest-source.json").write_text(json.dumps(digest_source), encoding="utf-8")
    (tmp_path / "input.json").write_text(json.dumps(document), encoding="utf-8")
    args += ["--input", str(tmp_path / "input.json")]
    if route == "worker-result":
        envelope = _rework_envelope(OVERLAP_INDEX) if envelope is None else envelope
        (tmp_path / "envelope.json").write_text(json.dumps(envelope), encoding="utf-8")
        args += ["--input-envelope", str(tmp_path / "envelope.json")]
    if dry_run:
        args += [
            "--workflow", str(tmp_path / "workflow.json"),
            "--digest-source", str(tmp_path / "digest-source.json"),
            "--dry-run-apply",
        ]
    return run_cli(args)


def _read_fixture(case, name):
    return json.loads((FIXTURE_GROUP_DIR / case / name).read_text(encoding="utf-8"))


def _overlap_of(rpatch):
    """The IDs a requirements_patch entry's tests_replace from set and to set
    share, computed independently of the validator (string values of mapping
    pairs only)."""
    pairs = ((rpatch.get("set") or {}).get("tests_replace")) if isinstance(rpatch, dict) else None
    pairs = [p for p in pairs if isinstance(p, dict)] if isinstance(pairs, list) else []
    return {p["from"] for p in pairs if isinstance(p.get("from"), str)} & {
        p["to"] for p in pairs if isinstance(p.get("to"), str)
    }


# tests_replace values (AC-6) that are not a well-formed list of pairs; each
# must end as a requirements_patch finding, never as an exception
MALFORMED_TESTS_REPLACE = {
    "not a list: string": "TS-1",
    "not a list: mapping": {"from": "TS-1", "to": "TS-2"},
    "not a list: null": None,
    "not a list: number": 3,
    "not a list: bool": True,
    "empty list": [],
    "pair is a string": ["TS-1"],
    "pair is null": [None],
    "pair is a list": [["TS-1", "TS-2"]],
    "pair is a number": [7],
    "pair lacks from": [{"to": "TS-2"}],
    "pair lacks to": [{"from": "TS-1"}],
    "pair is empty": [{}],
    "from is a number": [{"from": 1, "to": "TS-2"}],
    "to is null": [{"from": "TS-1", "to": None}],
    "from is a list (unhashable)": [{"from": ["TS-1"], "to": "TS-2"}],
    "from is a mapping (unhashable)": [{"from": {"a": 1}, "to": "TS-2"}],
    "to is a list (unhashable)": [{"from": "TS-1", "to": ["TS-2"]}],
    "to is a mapping (unhashable)": [{"from": "TS-1", "to": {"a": 1}}],
    "from and to are both unhashable": [{"from": ["TS-1"], "to": {"a": 1}}],
    "a valid pair beside an unhashable one": [_rename("TS-1", "TS-2"), {"from": ["TS-2"], "to": "TS-3"}],
}


class TestTestsReplaceOverlap(unittest.TestCase):
    def _entry_errors(self, pairs, **kwargs):
        return VWO.validate_workflow_patch(_replace_patch({"FR1": _replace_entry(pairs, **kwargs)}))

    def _assert_overlap_rejection(self, errors, overlap):
        self.assertEqual(_codes(errors), [REQUIREMENTS_PATCH_CODE], errors)
        self.assertIn("FR1", errors[0]["message"])
        for test_id in overlap:
            self.assertIn(test_id, errors[0]["message"])

    # AC-1 -----------------------------------------------------------------

    def test_ac1_chain_is_rejected_with_requirements_patch(self):
        self._assert_overlap_rejection(self._entry_errors(CHAIN), ["TS-2"])

    def test_ac1_chain_exits_1_with_the_code_through_the_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            completed = _cli_via(Path(tmp), "workflow-patch", False, _replace_patch({"FR1": _replace_entry(CHAIN)}))
            self.assertEqual(completed.returncode, 1, completed.stdout + completed.stderr)
            self.assertEqual(_codes(json.loads(completed.stdout)["errors"]), [REQUIREMENTS_PATCH_CODE])

    def test_ac1_only_the_overlapping_entry_is_named(self):
        patch = _replace_patch(
            {"FR1": _replace_entry(DISJOINT), "FR2": _replace_entry(CHAIN)}
        )
        errors = VWO.validate_workflow_patch(patch)
        self.assertEqual(_codes(errors), [REQUIREMENTS_PATCH_CODE])
        self.assertIn("entries[FR2]", errors[0]["message"])
        self.assertNotIn("FR1", errors[0]["message"])

    def test_ac1_only_the_shared_ids_are_named_among_several_pairs(self):
        pairs = [_rename("TS1", "TS-1"), _rename("TS-1", "TS-9"), _rename("TS7", "TS-7")]
        errors = self._entry_errors(pairs)
        self._assert_overlap_rejection(errors, ["TS-1"])
        for other in ("TS1", "TS-9", "TS7", "TS-7"):
            self.assertNotIn(repr(other), errors[0]["message"])

    # AC-2 -----------------------------------------------------------------

    def test_ac2_swap_is_rejected_with_requirements_patch(self):
        self._assert_overlap_rejection(self._entry_errors(SWAP), ["TS-1", "TS-2"])

    def test_ac2_swap_exits_1_with_the_code_through_the_cli(self):
        with tempfile.TemporaryDirectory() as tmp:
            completed = _cli_via(Path(tmp), "workflow-patch", False, _replace_patch({"FR1": _replace_entry(SWAP)}))
            self.assertEqual(completed.returncode, 1, completed.stdout + completed.stderr)
            self.assertEqual(_codes(json.loads(completed.stdout)["errors"]), [REQUIREMENTS_PATCH_CODE])

    # AC-3 -----------------------------------------------------------------

    def test_ac3_chain_and_swap_are_rejected_on_all_four_routes_in_process(self):
        for label, pairs, overlap in (("chain", CHAIN, ["TS-2"]), ("swap", SWAP, ["TS-1", "TS-2"])):
            patch = _replace_patch({"FR1": _replace_entry(pairs)})
            for route, dry_run in ROUTES:
                with self.subTest(pairs=label, route=route, dry_run=dry_run):
                    errors = _errors_via(route, dry_run, patch)
                    self._assert_overlap_rejection(errors, overlap)
                    if route == "worker-result":
                        self.assertIn("workflow_patch", errors[0]["message"])

    def test_ac3_chain_and_swap_exit_1_on_all_four_routes_through_the_cli(self):
        for label, pairs in (("chain", CHAIN), ("swap", SWAP)):
            patch = _replace_patch({"FR1": _replace_entry(pairs)})
            for route, dry_run in ROUTES:
                with self.subTest(pairs=label, route=route, dry_run=dry_run):
                    document = patch if route == "workflow-patch" else _worker_result_with(patch)
                    with tempfile.TemporaryDirectory() as tmp:
                        completed = _cli_via(Path(tmp), route, dry_run, document)
                    self.assertEqual(completed.returncode, 1, completed.stdout + completed.stderr)
                    self.assertEqual(
                        _codes(json.loads(completed.stdout)["errors"]), [REQUIREMENTS_PATCH_CODE]
                    )

    def test_ac3_each_fixtures_own_workflow_patch_is_rejected_with_and_without_dry_run(self):
        for case in OVERLAP_FIXTURES:
            patch = _read_fixture(case, "input.json")["workflow_patch"]
            for dry_run in (False, True):
                with self.subTest(case=case, dry_run=dry_run):
                    with tempfile.TemporaryDirectory() as tmp:
                        completed = _cli_via(Path(tmp), "workflow-patch", dry_run, patch)
                    self.assertEqual(completed.returncode, 1, completed.stdout + completed.stderr)
                    self.assertEqual(
                        _codes(json.loads(completed.stdout)["errors"]), [REQUIREMENTS_PATCH_CODE]
                    )

    def test_ac3_each_fixture_as_a_worker_result_is_rejected_with_and_without_dry_run(self):
        for case in OVERLAP_FIXTURES:
            result = _read_fixture(case, "input.json")
            envelope = _read_fixture(case, "envelope.json")
            for dry_run in (False, True):
                with self.subTest(case=case, dry_run=dry_run):
                    with tempfile.TemporaryDirectory() as tmp:
                        completed = _cli_via(Path(tmp), "worker-result", dry_run, result, envelope)
                    self.assertEqual(completed.returncode, 1, completed.stdout + completed.stderr)
                    self.assertEqual(
                        _codes(json.loads(completed.stdout)["errors"]), [REQUIREMENTS_PATCH_CODE]
                    )

    # AC-4 -----------------------------------------------------------------

    def test_ac4_pairs_without_overlap_are_accepted_on_all_four_routes(self):
        patch = _replace_patch({"FR1": _replace_entry(DISJOINT)})
        for route, dry_run in ROUTES:
            with self.subTest(route=route, dry_run=dry_run):
                self.assertEqual(_errors_via(route, dry_run, patch), [])

    def test_ac4_valid_docs_only_round_fixture_is_accepted(self):
        completed = run_cli(
            [
                "--kind", "worker-result",
                "--worker", "rework-planner",
                "--input", str(FIXTURE_GROUP_DIR / OVERLAP_SOURCE_FIXTURE / "input.json"),
                "--input-envelope", str(FIXTURE_GROUP_DIR / OVERLAP_SOURCE_FIXTURE / "envelope.json"),
            ]
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_ac4_pairs_sharing_a_to_are_not_rejected_by_this_check(self):
        patch = _replace_patch({"FR1": _replace_entry(SHARED_TO)})
        for route, dry_run in ROUTES:
            with self.subTest(route=route, dry_run=dry_run):
                self.assertEqual(_errors_via(route, dry_run, patch), [])

    def test_ac4_overlap_is_judged_per_entry(self):
        patch = _replace_patch(
            {
                "FR1": _replace_entry([_rename("TS-1", "TS-2")]),
                "FR2": _replace_entry([_rename("TS-2", "TS-3")]),
            }
        )
        self.assertEqual(VWO.validate_workflow_patch(patch), [])

    def test_ac4_no_existing_valid_fixture_has_overlapping_tests_replace(self):
        seen_tests_replace = 0
        for input_path in sorted(FIXTURES_ROOT.glob("*/*/valid-*/input.json")):
            data = json.loads(input_path.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                continue
            patch = data.get("workflow_patch") if isinstance(data.get("workflow_patch"), dict) else data
            requirements_patch = patch.get("requirements_patch")
            entries = requirements_patch.get("entries") if isinstance(requirements_patch, dict) else None
            for fr_id, rpatch in (entries.items() if isinstance(entries, dict) else ()):
                if isinstance(rpatch, dict) and "tests_replace" in (rpatch.get("set") or {}):
                    seen_tests_replace += 1
                with self.subTest(fixture=str(input_path.relative_to(FIXTURES_ROOT)), entry=fr_id):
                    self.assertEqual(_overlap_of(rpatch), set())
        self.assertGreater(seen_tests_replace, 0, "the scan found no valid fixture with tests_replace")

    # AC-5 -----------------------------------------------------------------

    def test_ac5_the_two_fixtures_exist_with_input_and_envelope(self):
        self.assertEqual(len(OVERLAP_FIXTURES), 2)
        for case in OVERLAP_FIXTURES:
            self.assertTrue(case.startswith("invalid-"))
            for name in ("input.json", "envelope.json"):
                with self.subTest(case=case, file=name):
                    self.assertTrue((FIXTURE_GROUP_DIR / case / name).is_file())

    def test_ac5_the_fixtures_are_rejected_with_exit_1_and_only_requirements_patch(self):
        for case, (_, overlap) in OVERLAP_FIXTURES.items():
            with self.subTest(case=case):
                completed = run_cli(
                    [
                        "--kind", "worker-result",
                        "--worker", "rework-planner",
                        "--input", str(FIXTURE_GROUP_DIR / case / "input.json"),
                        "--input-envelope", str(FIXTURE_GROUP_DIR / case / "envelope.json"),
                    ]
                )
                self.assertEqual(completed.returncode, 1, completed.stdout + completed.stderr)
                errors = json.loads(completed.stdout)["errors"]
                self.assertEqual(_codes(errors), [REQUIREMENTS_PATCH_CODE])
                self.assertIn("FR1", errors[0]["message"])
                for test_id in overlap:
                    self.assertIn(test_id, errors[0]["message"])

    def test_ac5_the_fixtures_stay_outside_the_set_that_forbids_tests_replace(self):
        for case in OVERLAP_FIXTURES:
            self.assertNotIn(case, FIXTURE_EXPECTED_CODES)

    def test_ac5_each_fixture_differs_from_valid_docs_only_round_only_in_the_overlap(self):
        source = _read_fixture(OVERLAP_SOURCE_FIXTURE, "input.json")
        source_envelope = _read_fixture(OVERLAP_SOURCE_FIXTURE, "envelope.json")
        for case, (pairs, _) in OVERLAP_FIXTURES.items():
            with self.subTest(case=case):
                derived = _read_fixture(case, "input.json")
                self.assertEqual(_read_fixture(case, "envelope.json"), source_envelope)
                derived_entries = derived["workflow_patch"]["requirements_patch"]["entries"]
                self.assertEqual(derived_entries["FR1"], _replace_entry(pairs))
                source_entries = source["workflow_patch"]["requirements_patch"]["entries"]
                derived_entries["FR1"] = source_entries["FR1"]
                self.assertEqual(derived, source)

    # AC-6 -----------------------------------------------------------------

    def test_ac6_malformed_tests_replace_is_reported_never_raised_on_all_four_routes(self):
        for label, value in MALFORMED_TESTS_REPLACE.items():
            entry = {"expected": {"tests_contains": ["TS-1"]}, "set": {"tests_replace": value}}
            patch = _replace_patch({"FR1": entry})
            for route, dry_run in ROUTES:
                with self.subTest(case=label, route=route, dry_run=dry_run):
                    errors = _errors_via(route, dry_run, patch)
                    self.assertTrue(errors, "a malformed tests_replace must be reported")
                    self.assertEqual(set(_codes(errors)), {REQUIREMENTS_PATCH_CODE}, errors)

    def test_ac6_malformed_tests_replace_exits_1_with_json_details_never_2(self):
        for label in (
            "not a list: string",
            "pair is a list",
            "pair lacks from",
            "from is a list (unhashable)",
            "from is a mapping (unhashable)",
            "to is a list (unhashable)",
            "from and to are both unhashable",
        ):
            entry = {
                "expected": {"tests_contains": ["TS-1"]},
                "set": {"tests_replace": MALFORMED_TESTS_REPLACE[label]},
            }
            patch = _replace_patch({"FR1": entry})
            for route, dry_run in ROUTES:
                with self.subTest(case=label, route=route, dry_run=dry_run):
                    document = patch if route == "workflow-patch" else _worker_result_with(patch)
                    with tempfile.TemporaryDirectory() as tmp:
                        completed = _cli_via(Path(tmp), route, dry_run, document)
                    self.assertEqual(completed.returncode, 1, completed.stdout + completed.stderr)
                    errors = json.loads(completed.stdout)["errors"]
                    self.assertEqual(set(_codes(errors)), {REQUIREMENTS_PATCH_CODE}, errors)

    def test_ac6_a_malformed_pair_does_not_hide_an_overlap_nor_make_the_check_raise(self):
        overlap_only = self._entry_errors(CHAIN)
        self.assertEqual(_codes(overlap_only), [REQUIREMENTS_PATCH_CODE])
        malformed = {"from": ["TS-9"], "to": {"a": 1}}
        for extra in (malformed, None, "TS-9", {"from": "TS-9"}):
            with self.subTest(extra=extra):
                errors = self._entry_errors(CHAIN + [extra], contains=["TS-1", "TS-2"])
                self.assertEqual(set(_codes(errors)), {REQUIREMENTS_PATCH_CODE})
                self.assertIn(_messages(overlap_only)[0], _messages(errors))
                self.assertGreater(len(errors), 1)


# ---------------------------------------------------------------------------
# AC-7: standard library only
# ---------------------------------------------------------------------------

class TestStandardLibraryOnly(unittest.TestCase):
    def test_ac7_this_module_imports_only_standard_library_modules(self):
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                self.assertEqual(node.level, 0, "relative imports are not allowed")
                imported.add((node.module or "").split(".")[0])
        self.assertTrue(imported)
        self.assertEqual(imported - set(sys.stdlib_module_names), set())


if __name__ == "__main__":
    unittest.main()
