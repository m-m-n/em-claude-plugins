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
- docs-only round step_patches (rework-docs-only-medium-fixes, task0002,
  FR3): on the same kind of patch every step patch that targets `implement`
  is `docs-only-implement-reset` whatever its status, and `step_patches`
  that is not exactly one entry for the origin step with `set.status`
  `pending` is reported once with code `docs-only-step-patches`. The origin
  step is the input envelope's `rework_source.type`, or `verify` / `review`
  when there is none; a malformed `rework_source` matches no origin step.
  Malformed shapes are reported, never raised.
- rename-aware coverage (FR6, FR7, TM-5): a `covered_by_existing` ID absent
  from `verification_index` passes only when a declared
  `payload.doc_corrections[].scenario_renames` pair maps a
  `verification_index` key (`from`) to it (`to`); otherwise code
  `rework-index`. Malformed declarations contribute no pair and never raise.

Standard-library imports only. The module reads the validator script and the
six fixtures under references/fixtures/worker-result/rework-planner/ that
this task owns.
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
STEP_PATCHES_CODE = "docs-only-step-patches"
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
                    _codes(VWO.validate_workflow_patch(patch)), [IMPLEMENT_RESET_CODE, STEP_PATCHES_CODE]
                )

    def test_ac3_rejection_names_the_offending_step_patch(self):
        patch = _append_patch({}, [REVIEW_PENDING, IMPLEMENT_PENDING])
        errors = VWO.validate_workflow_patch(patch)
        self.assertEqual(_codes(errors), [IMPLEMENT_RESET_CODE, STEP_PATCHES_CODE])
        self.assertIn("step_patches[1]", errors[0]["message"])

    def test_ac3_rejected_with_dry_run_apply(self):
        patch, workflow, digest_source = _dry_run_context(_append_patch({}))
        errors = VWO.validate_workflow_patch(
            patch, workflow=workflow, digest_source=digest_source, dry_run=True
        )
        self.assertEqual(_codes(errors), [IMPLEMENT_RESET_CODE, STEP_PATCHES_CODE])

    def test_ac3_rejected_through_worker_result_with_and_without_dry_run(self):
        result = _rework_result(entries={}, rework_index={})
        errors = _validate_result(result, {"TS-3": ["FR1"]})
        self.assertEqual(_codes(errors), [IMPLEMENT_RESET_CODE, STEP_PATCHES_CODE])
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
        self.assertEqual(_codes(errors), [IMPLEMENT_RESET_CODE, STEP_PATCHES_CODE])

    def test_ac3_cli_workflow_patch_exits_1_with_the_code(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            input_path = tmp_path / "input.json"
            input_path.write_text(json.dumps(_append_patch({})), encoding="utf-8")
            result = run_cli(
                ["--kind", "workflow-patch", "--worker", "rework-planner", "--input", str(input_path)]
            )
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertEqual(_codes(json.loads(result.stdout)["errors"]), [IMPLEMENT_RESET_CODE, STEP_PATCHES_CODE])

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
            self.assertEqual(_codes(json.loads(result.stdout)["errors"]), [IMPLEMENT_RESET_CODE, STEP_PATCHES_CODE])

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

    def test_ac3_empty_entries_with_implement_not_set_to_pending_is_rejected_too(self):
        # rework-docs-only-medium-fixes/task0002 (FR3): the implement check no
        # longer looks at set.status -- any step patch that targets implement
        # on a docs-only round is `docs-only-implement-reset`.
        step = {"expected": {}, "set": {"status": "completed"}, "step_id": "implement"}
        codes = _codes(VWO.validate_workflow_patch(_append_patch({}, [step])))
        self.assertIn(IMPLEMENT_RESET_CODE, codes)

    def test_ac3_rule_is_limited_to_append_rework(self):
        patch = _replace_planning_patch({}, [IMPLEMENT_PENDING])
        self.assertNotIn(IMPLEMENT_RESET_CODE, _codes(VWO.validate_workflow_patch(patch)))


# ---------------------------------------------------------------------------
# rework-docs-only-medium-fixes/task0002 (FR3, FR6, FR7, NFR1): the docs-only
# round's step_patches check. A docs-only round is an `append_rework` patch
# whose tasks_patch.entries is absent or empty. It is accepted only when
# step_patches is exactly one entry for the origin step with set.status
# `pending`; any entry that targets implement is `docs-only-implement-reset`
# whatever its status. The origin step is the input envelope's
# rework_source.type, or verify / review when there is none (IMPLEMENTATION.md
# D3). The rule's prose is owned by the SSOT documents, cited not restated.
# ---------------------------------------------------------------------------

_STEP_EXPECTED_STATUS = {"implement": "completed", "review": "in_progress", "verify": "completed"}


def _step_patch(step_id, status="pending"):
    """A step_patches entry whose `expected.status` matches the in-memory
    workflow of `_dry_run_context`, so dry-run-apply adds no code of its own."""
    entry = {"set": {"status": status}, "step_id": step_id}
    if step_id in _STEP_EXPECTED_STATUS:
        entry["expected"] = {"status": _STEP_EXPECTED_STATUS[step_id]}
    return entry


def _docs_only_patch(step_patches):
    """An `append_rework` patch with empty tasks_patch.entries whose
    step_patches is exactly `step_patches` (any shape)."""
    patch = _append_patch({}, [])
    patch["step_patches"] = copy.deepcopy(step_patches)
    return patch


def _docs_only_result(step_patches):
    result = _rework_result(entries={}, rework_index={}, step_patches=[])
    result["workflow_patch"]["step_patches"] = copy.deepcopy(step_patches)
    return result


def _docs_only_envelope(rework_source=_ABSENT):
    envelope = _rework_envelope({"TS-3": ["FR1"]})
    if rework_source is not _ABSENT:
        envelope["rework_source"] = copy.deepcopy(rework_source)
    return envelope


def _bind_result(result):
    """The result with its workflow_patch bound to the in-memory dry-run
    context, plus that context's workflow and digest source."""
    bound_patch, workflow, digest_source = _dry_run_context(result["workflow_patch"])
    bound_patch["tasks_patch"]["expected_next_task_id"] = "task0002"
    bound = copy.deepcopy(result)
    bound["workflow_patch"] = bound_patch
    return bound, workflow, digest_source


def _validate_docs_only(step_patches, kind, dry_run=False, rework_source=_ABSENT):
    """Runs the validator in-process on the route `kind`: the patch alone
    (`workflow-patch`, which holds no envelope) or a worker result whose
    input envelope carries `rework_source` when it is not _ABSENT."""
    if kind == "workflow-patch":
        patch = _docs_only_patch(step_patches)
        if dry_run:
            patch, workflow, digest_source = _dry_run_context(patch)
            return VWO.validate_workflow_patch(
                patch, workflow=workflow, digest_source=digest_source, dry_run=True
            )
        return VWO.validate_workflow_patch(patch)
    result = _docs_only_result(step_patches)
    envelope = _docs_only_envelope(rework_source)
    if dry_run:
        result, workflow, digest_source = _bind_result(result)
        return VWO.validate_worker_result(
            result,
            "rework-planner",
            envelope=envelope,
            workflow=workflow,
            digest_source=digest_source,
            dry_run=True,
        )
    return VWO.validate_worker_result(result, "rework-planner", envelope=envelope)


def _write_json(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")


def _run_docs_only_cli(step_patches, kind, dry_run=False, rework_source=_ABSENT):
    """Runs the validator CLI on the route `kind`. `--input-envelope` is
    passed for `worker-result` (it is mandatory there) and for
    `workflow-patch` only when `rework_source` is given."""
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp)
        workflow = digest_source = None
        if kind == "workflow-patch":
            document = _docs_only_patch(step_patches)
            if dry_run:
                document, workflow, digest_source = _dry_run_context(document)
        else:
            document = _docs_only_result(step_patches)
            if dry_run:
                document, workflow, digest_source = _bind_result(document)
        _write_json(tmp_path / "input.json", document)
        args = ["--kind", kind, "--worker", "rework-planner", "--input", str(tmp_path / "input.json")]
        if kind == "worker-result" or rework_source is not _ABSENT:
            _write_json(tmp_path / "envelope.json", _docs_only_envelope(rework_source))
            args += ["--input-envelope", str(tmp_path / "envelope.json")]
        if dry_run:
            _write_json(tmp_path / "workflow.json", workflow)
            _write_json(tmp_path / "digest-source.json", digest_source)
            args += [
                "--workflow", str(tmp_path / "workflow.json"),
                "--digest-source", str(tmp_path / "digest-source.json"),
                "--dry-run-apply",
            ]
        return run_cli(args)


def _cli_codes(completed):
    return _codes(json.loads(completed.stdout)["errors"])


_ROUTES = (
    ("workflow-patch", False),
    ("workflow-patch", True),
    ("worker-result", False),
    ("worker-result", True),
)

_IMPLEMENT_AND_SHAPE = {IMPLEMENT_RESET_CODE, STEP_PATCHES_CODE}

# AC-1 / AC-2 cases whose rejection does not depend on the envelope
# (label, step_patches, codes the validator must report)
_ENVELOPE_INDEPENDENT_REJECTIONS = (
    ("implement entry completed", [_step_patch("implement", "completed")], _IMPLEMENT_AND_SHAPE),
    (
        "implement entry pending beside review",
        [_step_patch("implement"), _step_patch("review")],
        _IMPLEMENT_AND_SHAPE,
    ),
    ("empty step_patches", [], {STEP_PATCHES_CODE}),
    ("two entries", [_step_patch("verify"), _step_patch("review")], {STEP_PATCHES_CODE}),
    ("origin entry not pending", [_step_patch("verify", "completed")], {STEP_PATCHES_CODE}),
)

# (label, step_patches, rework_source) -- every one is a malformed shape
_MALFORMED_STEP_PATCH_SHAPES = (
    ("step_patches is a string", "verify", _ABSENT),
    ("step_patches is a mapping", {"step_id": "verify"}, _ABSENT),
    ("step_patches is a number", 5, _ABSENT),
    ("step_patches is null", None, _ABSENT),
    ("element is a string", ["verify"], _ABSENT),
    ("element is null", [None], _ABSENT),
    ("element is a list", [["verify"]], _ABSENT),
    ("element is a number", [5], _ABSENT),
    ("set is a string", [{"step_id": "verify", "set": "pending"}], _ABSENT),
    ("set is a list", [{"step_id": "verify", "set": ["status"]}], _ABSENT),
    ("set is a number", [{"step_id": "verify", "set": 5}], _ABSENT),
    ("set is null", [{"step_id": "verify", "set": None}], _ABSENT),
    ("step_id is a number", [{"step_id": 5, "set": {"status": "pending"}}], _ABSENT),
    ("step_id is a list", [{"step_id": ["verify"], "set": {"status": "pending"}}], _ABSENT),
    ("step_id is a mapping", [{"step_id": {"a": 1}, "set": {"status": "pending"}}], _ABSENT),
    ("step_id is a bool", [{"step_id": True, "set": {"status": "pending"}}], _ABSENT),
    ("status is a number", [{"step_id": "verify", "set": {"status": 5}}], _ABSENT),
    ("status is a list", [{"step_id": "verify", "set": {"status": ["pending"]}}], _ABSENT),
    ("status is a mapping", [{"step_id": "verify", "set": {"status": {"a": 1}}}], _ABSENT),
    ("status is null", [{"step_id": "verify", "set": {"status": None}}], _ABSENT),
    ("status is a bool", [{"step_id": "verify", "set": {"status": True}}], _ABSENT),
    ("rework_source is a string", [_step_patch("verify")], "verify"),
    ("rework_source is a list", [_step_patch("verify")], ["verify"]),
    ("rework_source is a number", [_step_patch("verify")], 5),
    ("rework_source is null", [_step_patch("verify")], None),
    ("type is null", [_step_patch("verify")], {"type": None}),
    ("type is a number", [_step_patch("verify")], {"type": 5}),
    ("type is a list", [_step_patch("verify")], {"type": ["verify"]}),
    ("type is a mapping", [_step_patch("verify")], {"type": {"a": 1}}),
    ("type is a bool", [_step_patch("verify")], {"type": True}),
)

# the malformed shapes that are also run through the dry-run CLI routes
_DRY_RUN_CLI_SHAPES = (
    "step_patches is a string",
    "element is a number",
    "set is a number",
    "step_id is a list",
    "status is a list",
    "rework_source is a list",
    "type is a list",
)

# fixture case -> codes the validator must report for it
STEP_PATCHES_FIXTURE_EXPECTED_CODES = {
    "invalid-docs-only-round-implement-completed": [IMPLEMENT_RESET_CODE, STEP_PATCHES_CODE],
    "invalid-docs-only-round-no-step-patches": [STEP_PATCHES_CODE],
    "invalid-docs-only-round-extra-step": [STEP_PATCHES_CODE],
    "invalid-docs-only-round-origin-not-pending": [STEP_PATCHES_CODE],
    "invalid-docs-only-round-origin-mismatch": [STEP_PATCHES_CODE],
}

_FIXTURES_ROOT = FIXTURE_GROUP_DIR.parent.parent
_GROUP_WORKER = {
    "requirements-analyst-full": "requirements-analyst",
    "requirements-analyst-design-system-detection": "requirements-analyst",
    "spec-writer": "spec-writer",
    "implementation-planner": "implementation-planner",
    "rework-planner": "rework-planner",
    "designer": "designer",
}


def _companion_file(case_dir, stem):
    for ext in (".json", ".yaml", ".yml"):
        candidate = case_dir / f"{stem}{ext}"
        if candidate.is_file():
            return candidate
    return None


def _fixture_cli_args(kind, group, case_dir):
    """The CLI arguments for one fixture case directory, wired the way the
    fixture runner of tests/test_validate_worker_output.py wires them."""
    args = [
        "--kind", kind,
        "--worker", _GROUP_WORKER.get(group, "implementation-planner"),
        "--input", str(_companion_file(case_dir, "input")),
    ]
    for flag, stem in (
        ("--input-envelope", "envelope"),
        ("--packet", "packet"),
        ("--answers", "answers"),
        ("--workflow", "workflow"),
        ("--digest-source", "digest-source"),
        ("--phase-state", "phase-state"),
    ):
        companion = _companion_file(case_dir, stem)
        if companion is not None:
            args += [flag, str(companion)]
    for flag, dirname in (
        ("--registries", "registries"),
        ("--feature-dir", "feature-dir"),
        ("--baseline-dir", "baseline-dir"),
    ):
        if (case_dir / dirname).is_dir():
            args += [flag, str(case_dir / dirname)]
    if (case_dir / "DRY_RUN_APPLY").exists():
        args.append("--dry-run-apply")
    return args


def _read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


class TestDocsOnlyStepPatches(unittest.TestCase):
    # -- AC-1: an entry that targets implement, whatever its status ----------

    def test_ac1_implement_entry_is_rejected_whatever_its_status(self):
        for status in ("pending", "completed", "in_progress", "failed", "skipped"):
            with self.subTest(status=status):
                codes = _codes(
                    VWO.validate_workflow_patch(_docs_only_patch([_step_patch("implement", status)]))
                )
                self.assertIn(IMPLEMENT_RESET_CODE, codes)

    def test_ac1_implement_entry_without_a_status_is_rejected(self):
        for label, entry in (
            ("no set", {"step_id": "implement"}),
            ("set without status", {"step_id": "implement", "set": {}}),
            ("status null", {"step_id": "implement", "set": {"status": None}}),
        ):
            with self.subTest(entry=label):
                codes = _codes(VWO.validate_workflow_patch(_docs_only_patch([entry])))
                self.assertIn(IMPLEMENT_RESET_CODE, codes)

    def test_ac1_each_implement_entry_is_reported_and_named_by_index(self):
        patch = _docs_only_patch(
            [_step_patch("review"), _step_patch("implement", "completed"), _step_patch("implement")]
        )
        errors = VWO.validate_workflow_patch(patch)
        resets = [e for e in errors if e["code"] == IMPLEMENT_RESET_CODE]
        self.assertEqual(len(resets), 2)
        self.assertIn("step_patches[1]", resets[0]["message"])
        self.assertIn("step_patches[2]", resets[1]["message"])

    def test_ac1_a_single_implement_completed_entry_also_fails_the_shape_check(self):
        errors = VWO.validate_workflow_patch(
            _docs_only_patch([_step_patch("implement", "completed")])
        )
        self.assertEqual(_codes(errors), [IMPLEMENT_RESET_CODE, STEP_PATCHES_CODE])

    def test_ac1_implement_entry_on_a_patch_with_task_entries_is_not_checked(self):
        patch = _append_patch({"task0007": _entry(["src/auth.go"])}, [_step_patch("implement", "completed")])
        codes = _codes(VWO.validate_workflow_patch(patch))
        self.assertNotIn(IMPLEMENT_RESET_CODE, codes)
        self.assertNotIn(STEP_PATCHES_CODE, codes)

    # -- AC-2: count and status ----------------------------------------------

    def test_ac2_empty_step_patches_is_rejected(self):
        errors = VWO.validate_workflow_patch(_docs_only_patch([]))
        self.assertEqual(_codes(errors), [STEP_PATCHES_CODE])
        self.assertIn("exactly one", errors[0]["message"])

    def test_ac2_two_or_more_entries_are_rejected(self):
        for label, step_patches in (
            ("verify and review", [_step_patch("verify"), _step_patch("review")]),
            ("review and verify", [_step_patch("review"), _step_patch("verify")]),
            ("verify twice", [_step_patch("verify"), _step_patch("verify")]),
            (
                "three entries",
                [_step_patch("verify"), _step_patch("review"), _step_patch("retrospect")],
            ),
        ):
            with self.subTest(case=label):
                errors = VWO.validate_workflow_patch(_docs_only_patch(step_patches))
                self.assertEqual(_codes(errors), [STEP_PATCHES_CODE])
                self.assertIn("exactly one", errors[0]["message"])

    def test_ac2_single_origin_entry_whose_status_is_not_pending_is_rejected(self):
        for step_id in ("verify", "review"):
            for status in ("completed", "in_progress", "failed", "skipped"):
                with self.subTest(step_id=step_id, status=status):
                    errors = VWO.validate_workflow_patch(
                        _docs_only_patch([_step_patch(step_id, status)])
                    )
                    self.assertEqual(_codes(errors), [STEP_PATCHES_CODE])
                    self.assertIn("'pending'", errors[0]["message"])

    def test_ac2_the_shape_error_is_reported_once_per_patch(self):
        patch = _docs_only_patch(
            [_step_patch("implement"), _step_patch("review", "completed"), {"step_id": 5}]
        )
        codes = _codes(VWO.validate_workflow_patch(patch))
        self.assertEqual(codes.count(STEP_PATCHES_CODE), 1)

    def test_ac2_the_message_names_the_violated_condition(self):
        count = VWO.validate_workflow_patch(_docs_only_patch([]))[0]["message"]
        origin = VWO.validate_workflow_patch(_docs_only_patch([_step_patch("retrospect")]))[0]["message"]
        status = VWO.validate_workflow_patch(
            _docs_only_patch([_step_patch("verify", "completed")])
        )[0]["message"]
        self.assertIn("exactly one", count)
        self.assertIn("origin step", origin)
        self.assertIn("'retrospect'", origin)
        self.assertIn("set.status", status)
        self.assertIn("'completed'", status)
        self.assertEqual(len({count, origin, status}), 3)

    def test_ac2_a_single_pending_origin_entry_is_accepted(self):
        for step_id in ("verify", "review"):
            with self.subTest(step_id=step_id):
                self.assertEqual(
                    VWO.validate_workflow_patch(_docs_only_patch([_step_patch(step_id)])), []
                )

    def test_ac2_rule_is_limited_to_append_rework_with_empty_entries(self):
        patch = _replace_planning_patch({}, [])
        self.assertNotIn(STEP_PATCHES_CODE, _codes(VWO.validate_workflow_patch(patch)))
        patch = _append_patch({"task0007": _entry(["src/auth.go"])}, [])
        self.assertNotIn(STEP_PATCHES_CODE, _codes(VWO.validate_workflow_patch(patch)))

    # -- AC-3: the origin step comes from the envelope -----------------------

    def test_ac3_envelope_type_that_differs_from_the_entry_is_rejected(self):
        for source_type, step_id in (("verify", "review"), ("review", "verify")):
            with self.subTest(rework_source_type=source_type, step_id=step_id):
                errors = _validate_docs_only(
                    [_step_patch(step_id)],
                    "worker-result",
                    rework_source={"type": source_type},
                )
                self.assertEqual(_codes(errors), [STEP_PATCHES_CODE])
                self.assertIn(repr(source_type), errors[0]["message"])
                self.assertIn(repr(step_id), errors[0]["message"])

    def test_ac3_entry_that_equals_the_envelope_type_is_accepted(self):
        for source_type in ("verify", "review"):
            for dry_run in (False, True):
                with self.subTest(rework_source_type=source_type, dry_run=dry_run):
                    errors = _validate_docs_only(
                        [_step_patch(source_type)],
                        "worker-result",
                        dry_run=dry_run,
                        rework_source={"type": source_type},
                    )
                    self.assertEqual(errors, [])

    def test_ac3_envelope_type_is_applied_through_the_cli_for_both_kinds(self):
        for kind in ("worker-result", "workflow-patch"):
            with self.subTest(kind=kind, case="mismatch"):
                completed = _run_docs_only_cli(
                    [_step_patch("review")], kind, rework_source={"type": "verify"}
                )
                self.assertEqual(completed.returncode, 1, completed.stdout + completed.stderr)
                self.assertEqual(_cli_codes(completed), [STEP_PATCHES_CODE])
            with self.subTest(kind=kind, case="match"):
                completed = _run_docs_only_cli(
                    [_step_patch("verify")], kind, rework_source={"type": "verify"}
                )
                self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    # -- AC-4: no usable type -> verify or review; malformed -> fail-closed --

    def test_ac4_without_an_envelope_verify_or_review_with_pending_is_accepted(self):
        for step_id in ("verify", "review"):
            for dry_run in (False, True):
                with self.subTest(step_id=step_id, dry_run=dry_run):
                    self.assertEqual(
                        _validate_docs_only([_step_patch(step_id)], "workflow-patch", dry_run), []
                    )

    def test_ac4_without_an_envelope_any_other_step_id_is_rejected(self):
        for step_id in ("implement", "create-spec", "design", "create-plan", "retrospect", "bogus", ""):
            with self.subTest(step_id=step_id):
                codes = _codes(
                    VWO.validate_workflow_patch(_docs_only_patch([_step_patch(step_id)]))
                )
                self.assertIn(STEP_PATCHES_CODE, codes)

    def test_ac4_envelope_without_a_usable_type_falls_back_to_verify_or_review(self):
        for label, rework_source in (
            ("no rework_source", _ABSENT),
            ("empty rework_source", {}),
            ("rework_source without type", {"review_round": 2, "findings": []}),
        ):
            for step_id in ("verify", "review"):
                with self.subTest(case=label, step_id=step_id):
                    self.assertEqual(
                        _validate_docs_only(
                            [_step_patch(step_id)], "worker-result", rework_source=rework_source
                        ),
                        [],
                    )
            with self.subTest(case=label, step_id="retrospect"):
                codes = _codes(
                    _validate_docs_only(
                        [_step_patch("retrospect")], "worker-result", rework_source=rework_source
                    )
                )
                self.assertIn(STEP_PATCHES_CODE, codes)

    def test_ac4_a_rework_source_that_is_not_a_mapping_is_rejected(self):
        for label, rework_source in (
            ("string", "review"),
            ("list", ["review"]),
            ("number", 5),
            ("null", None),
            ("empty list", []),
            ("empty string", ""),
            ("false", False),
        ):
            for step_id in ("verify", "review"):
                with self.subTest(rework_source=label, step_id=step_id):
                    errors = _validate_docs_only(
                        [_step_patch(step_id)], "worker-result", rework_source=rework_source
                    )
                    self.assertEqual(_codes(errors), [STEP_PATCHES_CODE])
                    self.assertIn("rework_source", errors[0]["message"])

    def test_ac4_a_type_that_is_not_review_or_verify_is_rejected(self):
        for label, source_type in (
            ("null", None),
            ("number", 5),
            ("bool", True),
            ("list", ["verify"]),
            ("mapping", {"a": 1}),
            ("empty string", ""),
            ("another string", "implement"),
            ("capitalized", "Verify"),
            ("trailing space", "verify "),
        ):
            for step_id in ("verify", "review"):
                with self.subTest(type=label, step_id=step_id):
                    errors = _validate_docs_only(
                        [_step_patch(step_id)],
                        "worker-result",
                        rework_source={"type": source_type},
                    )
                    self.assertEqual(_codes(errors), [STEP_PATCHES_CODE])

    # -- AC-5: structural layer, both routes, with and without dry-run -------

    def test_ac5_rejected_on_every_route_in_process(self):
        for label, step_patches, expected_codes in _ENVELOPE_INDEPENDENT_REJECTIONS:
            for kind, dry_run in _ROUTES:
                with self.subTest(case=label, kind=kind, dry_run=dry_run):
                    codes = _codes(_validate_docs_only(step_patches, kind, dry_run))
                    self.assertTrue(expected_codes <= set(codes), codes)

    def test_ac5_rejected_on_every_route_through_the_cli(self):
        for label, step_patches, expected_codes in _ENVELOPE_INDEPENDENT_REJECTIONS:
            for kind, dry_run in _ROUTES:
                with self.subTest(case=label, kind=kind, dry_run=dry_run):
                    completed = _run_docs_only_cli(step_patches, kind, dry_run)
                    self.assertEqual(completed.returncode, 1, completed.stdout + completed.stderr)
                    self.assertTrue(expected_codes <= set(_cli_codes(completed)))

    def test_ac5_worker_result_messages_name_the_workflow_patch(self):
        errors = _validate_docs_only([], "worker-result")
        self.assertEqual(_codes(errors), [STEP_PATCHES_CODE])
        self.assertIn("workflow_patch", errors[0]["message"])

    # -- AC-6: fixtures ------------------------------------------------------

    def test_ac6_the_five_fixtures_exist_next_to_their_source(self):
        self.assertEqual(len(STEP_PATCHES_FIXTURE_EXPECTED_CODES), 5)
        for case in STEP_PATCHES_FIXTURE_EXPECTED_CODES:
            for name in ("input.json", "envelope.json", "workflow.json", "digest-source.json", "DRY_RUN_APPLY"):
                with self.subTest(case=case, file=name):
                    self.assertTrue((FIXTURE_GROUP_DIR / case / name).is_file())
            for name in ("feature-dir", "baseline-dir"):
                with self.subTest(case=case, file=name):
                    self.assertFalse((FIXTURE_GROUP_DIR / case / name).exists())

    def test_ac6_the_five_fixtures_are_rejected_with_their_codes(self):
        for case, expected_codes in STEP_PATCHES_FIXTURE_EXPECTED_CODES.items():
            with self.subTest(case=case):
                completed = run_cli(
                    _fixture_cli_args("worker-result", "rework-planner", FIXTURE_GROUP_DIR / case)
                )
                self.assertEqual(completed.returncode, 1, completed.stdout + completed.stderr)
                self.assertEqual(_cli_codes(completed), expected_codes)

    def test_ac6_each_fixture_differs_from_its_source_only_in_the_targeted_defect(self):
        source_dir = FIXTURE_GROUP_DIR / "valid-docs-only-round"
        source_input = _read_json(source_dir / "input.json")
        source_envelope = _read_json(source_dir / "envelope.json")
        for case in STEP_PATCHES_FIXTURE_EXPECTED_CODES:
            case_dir = FIXTURE_GROUP_DIR / case
            with self.subTest(case=case):
                for name in ("workflow.json", "digest-source.json"):
                    self.assertEqual(_read_json(case_dir / name), _read_json(source_dir / name))
                case_input = _read_json(case_dir / "input.json")
                case_input["workflow_patch"]["step_patches"] = source_input["workflow_patch"]["step_patches"]
                self.assertEqual(case_input, source_input)
                case_envelope = _read_json(case_dir / "envelope.json")
                case_envelope.pop("rework_source", None)
                self.assertEqual(case_envelope, source_envelope)

    def test_ac6_each_fixture_carries_the_step_patches_its_name_states(self):
        def step_patches(case):
            return _read_json(FIXTURE_GROUP_DIR / case / "input.json")["workflow_patch"]["step_patches"]

        implement = step_patches("invalid-docs-only-round-implement-completed")
        self.assertEqual(
            [(sp["step_id"], sp["set"]["status"]) for sp in implement], [("implement", "completed")]
        )
        self.assertEqual(step_patches("invalid-docs-only-round-no-step-patches"), [])
        extra = step_patches("invalid-docs-only-round-extra-step")
        self.assertEqual(
            [(sp["step_id"], sp["set"]["status"]) for sp in extra],
            [("verify", "pending"), ("review", "pending")],
        )
        not_pending = step_patches("invalid-docs-only-round-origin-not-pending")
        self.assertEqual(
            [(sp["step_id"], sp["set"]["status"]) for sp in not_pending], [("verify", "completed")]
        )
        mismatch = step_patches("invalid-docs-only-round-origin-mismatch")
        self.assertEqual(
            [(sp["step_id"], sp["set"]["status"]) for sp in mismatch], [("review", "pending")]
        )
        envelope = _read_json(FIXTURE_GROUP_DIR / "invalid-docs-only-round-origin-mismatch" / "envelope.json")
        self.assertEqual(envelope["rework_source"]["type"], "verify")

    def test_ac6_the_new_fixtures_stay_outside_the_tests_replace_free_set(self):
        for case in STEP_PATCHES_FIXTURE_EXPECTED_CODES:
            self.assertNotIn(case, FIXTURE_EXPECTED_CODES)

    def test_ac6_every_existing_valid_fixture_is_accepted(self):
        checked = 0
        for kind in ("worker-result", "workflow-patch"):
            for group_dir in sorted((_FIXTURES_ROOT / kind).iterdir()):
                if not group_dir.is_dir():
                    continue
                for case_dir in sorted(group_dir.iterdir()):
                    if not (case_dir.is_dir() and case_dir.name.startswith("valid-")):
                        continue
                    checked += 1
                    with self.subTest(fixture=f"{kind}/{group_dir.name}/{case_dir.name}"):
                        completed = run_cli(_fixture_cli_args(kind, group_dir.name, case_dir))
                        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertGreater(checked, 0)
        self.assertTrue((FIXTURE_GROUP_DIR / "valid-docs-only-round").is_dir())

    # -- AC-7: malformed shapes are reported, never raised -------------------

    def test_ac7_malformed_shapes_are_reported_in_process_on_every_route(self):
        for label, step_patches, rework_source in _MALFORMED_STEP_PATCH_SHAPES:
            for kind, dry_run in _ROUTES:
                if rework_source is not _ABSENT and kind == "workflow-patch":
                    continue  # the patch alone holds no envelope
                with self.subTest(case=label, kind=kind, dry_run=dry_run):
                    errors = _validate_docs_only(step_patches, kind, dry_run, rework_source)
                    self.assertIn(STEP_PATCHES_CODE, _codes(errors))

    def test_ac7_malformed_shapes_exit_1_with_json_details_through_the_cli(self):
        for label, step_patches, rework_source in _MALFORMED_STEP_PATCH_SHAPES:
            routes = _ROUTES if label in _DRY_RUN_CLI_SHAPES else [r for r in _ROUTES if not r[1]]
            for kind, dry_run in routes:
                with self.subTest(case=label, kind=kind, dry_run=dry_run):
                    completed = _run_docs_only_cli(step_patches, kind, dry_run, rework_source)
                    self.assertEqual(completed.returncode, 1, completed.stdout + completed.stderr)
                    self.assertIn(STEP_PATCHES_CODE, _cli_codes(completed))

    def test_ac7_malformed_rework_source_reaches_the_workflow_patch_route_through_the_envelope(self):
        for rework_source in ("verify", ["verify"], None, {"type": None}, {"type": 5}):
            with self.subTest(rework_source=rework_source):
                completed = _run_docs_only_cli(
                    [_step_patch("verify")], "workflow-patch", rework_source=rework_source
                )
                self.assertEqual(completed.returncode, 1, completed.stdout + completed.stderr)
                self.assertEqual(_cli_codes(completed), [STEP_PATCHES_CODE])

    def test_ac7_a_malformed_envelope_is_treated_as_holding_no_rework_source(self):
        for envelope in ("junk", ["rework_source"], 5, None):
            with self.subTest(envelope=envelope):
                patch = _docs_only_patch([_step_patch("verify")])
                self.assertEqual(VWO.validate_workflow_patch(patch, envelope=envelope), [])

    def test_ac7_step_patch_shape_checks_do_not_raise_outside_docs_only_rounds(self):
        entries = {"task0007": _entry(["src/auth.go"])}
        workflow = _dry_run_context(_append_patch({}))[1]
        reported = (
            "step_patches is a string",
            "step_patches is a mapping",
            "step_patches is a number",
            "step_patches is null",
            "element is a string",
            "element is null",
            "element is a list",
            "element is a number",
            "set is a string",
            "set is a list",
            "set is a number",
            "step_id is a number",
            "step_id is a list",
            "step_id is a mapping",
            "step_id is a bool",
        )
        for label, step_patches, _ in _MALFORMED_STEP_PATCH_SHAPES:
            if label not in reported:
                continue
            for with_workflow in (False, True):
                with self.subTest(case=label, with_workflow=with_workflow):
                    patch = _append_patch(entries, [])
                    patch["step_patches"] = copy.deepcopy(step_patches)
                    kwargs = {"workflow": workflow} if with_workflow else {}
                    codes = _codes(VWO.validate_workflow_patch(patch, **kwargs))
                    self.assertIn("step_patches", codes)
                    self.assertNotIn(STEP_PATCHES_CODE, codes)


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
    # rework-docs-only-medium-fixes/task0002: the implement entry plus a
    # second entry now also breaks the step_patches shape (count).
    "invalid-docs-only-round-resets-implement": [IMPLEMENT_RESET_CODE, STEP_PATCHES_CODE],
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
