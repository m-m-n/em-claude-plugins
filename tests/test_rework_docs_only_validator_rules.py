"""Unit tests for the three rework-docs-only rules of
em-workflow/scripts/validate-worker-output.py
(rework-docs-only-task-routing, task0004).

Rules pinned here (their contract prose is owned elsewhere; this module
asserts only the validator's rendering of them):

- feature-docs files rule (FR3, TM-1): in `append` mode (the mode bound to
  `append_rework`) a task entry any of whose `files` has `feature-docs` as
  its first normalized path segment is reported with code
  `rework-task-feature-docs`. `replace_planning` entries are checked by a
  separate rule (code `plan-task-feature-docs`, plan-feature-docs-route
  task0004), never by this one.
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
- rename coverage backed by the document diff (rework-docs-only-medium-fixes,
  task0001; FR1, FR2, NFR1): with `--feature-dir` / `--baseline-dir` (the
  post-change and baseline VERIFICATION.md) a declared rename is accepted only
  when both documents confirm it; without the diff no rename is accepted; the
  old ID of a rename is never accepted; with the diff every covered ID must
  exist in the post-change VERIFICATION.md. TestRenameCoverageDiff and
  TestRenameDiffFixtures pin it.
- VERIFICATION.md read as a bounded regular file
  (verification-md-regular-file-read, task0001; FR1-FR4): the scenario-ID
  loader gives the unreadable state, without blocking or loading the file in
  full, for a FIFO, any symlink, a directory, a file over
  `MAX_PLAN_READ_BYTES` and bytes that are not UTF-8; the CLI then ends with
  exit 1 and one `rework-index` error. TestLoadScenarioIdsFileKinds and
  TestVerificationMdNotRegularCli pin it; the cases that give a FIFO or a
  /dev/zero link run in a child process with a timeout and a memory cap.
- tests_replace overlap (rework-docs-only-medium-fixes, task0003; FR4, TM-4):
  a `requirements_patch` entry whose `set.tests_replace` has a `from` set and
  a `to` set that share an ID (a chain TS-1->TS-2, TS-2->TS-3 or a swap
  TS-1->TS-2, TS-2->TS-1) is reported with code `requirements_patch`, at the
  structural layer (with and without `--dry-run-apply`, through both
  `--kind workflow-patch` and `--kind worker-result`). Pairs that only share
  a `to` are not rejected by this check. Malformed shapes never raise.
  TestTestsReplaceOverlap pins it.

Standard-library imports only. The module reads the validator script and the
fixtures under references/fixtures/worker-result/rework-planner/ that these
tasks own.
"""

import ast
import copy
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import tracemalloc
import unittest
from pathlib import Path

try:
    import resource
except ImportError:  # a platform without resource limits
    resource = None

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "em-workflow" / "scripts" / "validate-worker-output.py"
FIXTURE_GROUP_DIR = (
    REPO_ROOT / "em-workflow" / "references" / "fixtures" / "worker-result" / "rework-planner"
)


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

FEATURE_DOCS_CODE = "rework-task-feature-docs"
PLAN_FEATURE_DOCS_CODE = "plan-task-feature-docs"
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

    # Expectation inverted by plan-feature-docs-route/task0004 (FR2): a
    # replace_planning entry whose `files` reach feature-docs/** is now
    # rejected with its own code, `plan-task-feature-docs`, once per path.
    # The rework rule above stays append-only (its code never appears here).
    # The test keeps its original name: the plan-feature-docs-route SPEC and
    # earlier test records refer to it by that name.
    def test_ac1_replace_planning_entries_are_not_checked(self):
        errors = self._errors(["feature-docs/example/SPEC.md"], mode="replace_all")
        self.assertEqual(_codes(errors), [PLAN_FEATURE_DOCS_CODE])
        patch = _replace_planning_patch({"task0007": _entry(["feature-docs/example/SPEC.md"])})
        self.assertEqual(_codes(VWO.validate_workflow_patch(patch)), [PLAN_FEATURE_DOCS_CODE])

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


def _build_base_repo(tree, repo_dir):
    """The disposable repository a fixture's `base-tree.json` describes (a
    mapping from repository-relative path to file text); returns its commit
    ID. Identity is set per command; no git configuration is read."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env["GIT_CONFIG_NOSYSTEM"] = "1"

    def git(*args):
        return subprocess.run(
            ["git", "-c", "user.name=Fixture", "-c", "user.email=fixture@example.invalid",
             "-c", "commit.gpgsign=false", "-C", str(repo_dir), *args],
            check=True, capture_output=True, text=True, env=env,
        )

    repo_dir.mkdir(parents=True, exist_ok=True)
    git("init", "-q")
    for rel_path, content in tree.items():
        target = repo_dir / rel_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "--allow-empty", "-m", "fixture base")
    return git("rev-parse", "HEAD").stdout.strip()


def _fixture_cli_args(kind, group, case_dir, scratch_dir=None):
    """The CLI arguments for one fixture case directory, wired the way the
    fixture runner of tests/test_validate_worker_output.py wires them. A case
    holding `base-tree.json` also needs `scratch_dir`, under which its
    repository is built (`--target-repo` / `--base-commit`)."""
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
    base_tree = _companion_file(case_dir, "base-tree")
    if base_tree is not None:
        assert scratch_dir is not None, f"{case_dir} holds a base tree: pass scratch_dir"
        repo_dir = Path(scratch_dir) / "base-repo"
        base_commit = _build_base_repo(json.loads(base_tree.read_text(encoding="utf-8")), repo_dir)
        args += ["--target-repo", str(repo_dir), "--base-commit", base_commit]
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
                    with self.subTest(fixture=f"{kind}/{group_dir.name}/{case_dir.name}"), \
                            tempfile.TemporaryDirectory() as scratch_dir:
                        completed = run_cli(
                            _fixture_cli_args(kind, group_dir.name, case_dir, scratch_dir=scratch_dir)
                        )
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

    # rework-docs-only-medium-fixes/task0001 (D2): a declared rename is accepted
    # only when the baseline and post-change VERIFICATION.md confirm it, so the
    # tests below that expect an accepted rename pass the confirming pair of
    # directories (baseline defines TS3, post-change defines TS-3 and not TS3).
    # The tests that expect a rejection need no directories: without the diff no
    # rename is accepted either. The diff itself is pinned by
    # TestRenameCoverageDiff.
    def _confirming_diff(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        tmp_path = Path(tmp.name)
        _write_verification_md(tmp_path / "feature-dir", ["TS-3"])
        _write_verification_md(tmp_path / "baseline-dir", ["TS3"])
        plans = tmp_path / "feature-dir" / "tasks"
        plans.mkdir()
        (plans / "task0007.md").write_text(TASK_PLAN_TEXT, encoding="utf-8")
        return {"feature_dir": tmp_path / "feature-dir", "baseline_dir": tmp_path / "baseline-dir"}

    def test_ac4_declared_rename_makes_the_renamed_id_covered(self):
        result = _rework_result(doc_corrections=[_correction(_rename("TS3", "TS-3"))])
        self.assertEqual(
            _validate_result(result, self.PRE_RENAME_INDEX, **self._confirming_diff()), []
        )

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
        self.assertEqual(
            _validate_result(result, self.PRE_RENAME_INDEX, **self._confirming_diff()), []
        )

    def test_ac4_id_that_is_a_verification_index_key_passes_without_any_declaration(self):
        self.assertEqual(_validate_result(_rework_result(), {"TS-3": ["FR1"]}), [])

    def test_ac4_only_the_renamed_id_is_excused(self):
        result = _rework_result(
            covered=("TS-3", "TS-7"), doc_corrections=[_correction(_rename("TS3", "TS-3"))]
        )
        errors = _validate_result(result, self.PRE_RENAME_INDEX, **self._confirming_diff())
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
        self.assertEqual(
            _validate_result(result, self.PRE_RENAME_INDEX, **self._confirming_diff()), []
        )

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


def fixture_cli_args(case):
    """The validator CLI arguments for one rework-planner fixture directory.
    A `feature-dir/` and a `baseline-dir/` subdirectory, each independently
    when it exists, become `--feature-dir` / `--baseline-dir`: they hold the
    post-change and the baseline VERIFICATION.md. A fixture with neither runs
    with the input and the envelope only."""
    case_dir = FIXTURE_GROUP_DIR / case
    args = [
        "--kind", "worker-result",
        "--worker", "rework-planner",
        "--input", str(case_dir / "input.json"),
        "--input-envelope", str(case_dir / "envelope.json"),
    ]
    for flag, dirname in (("--feature-dir", "feature-dir"), ("--baseline-dir", "baseline-dir")):
        if (case_dir / dirname).is_dir():
            args += [flag, str(case_dir / dirname)]
    return args


class TestFixtures(unittest.TestCase):
    def _run(self, case):
        # passes feature-dir/ and baseline-dir/ when the fixture has them
        return run_cli(fixture_cli_args(case))

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
# Rename-aware coverage backed by the document diff
# (rework-docs-only-medium-fixes, task0001; rule: D2 -- FR1, FR2, NFR1)
#
# A covered_by_existing ID reached through a declared scenario rename is
# accepted only when the baseline and post-change VERIFICATION.md confirm the
# rename; the old ID of a rename is never accepted; with the diff available
# every covered ID must exist in the post-change VERIFICATION.md.
# ---------------------------------------------------------------------------

# Each message of the rework-index rule carries a phrase no other message
# carries, so a test can tell the rejections apart.
MSG_NO_DECLARATION = "no declared rename"                                        # (a)
MSG_DIFF_UNAVAILABLE = "document diff is unavailable"                            # (b)
MSG_NOT_CONFIRMED = "is not confirmed by the VERIFICATION.md diff"               # (c)
MSG_OLD_ID = "is the old ID of declared rename"                                  # (d)
MSG_MISSING_FROM_POST = (
    "is a verification_index key but is missing from the post-change VERIFICATION.md"
)                                                                                # (e)
MSG_UNREADABLE = "cannot be read as text"                                        # (f)

ALL_MESSAGE_PHRASES = (
    MSG_NO_DECLARATION,
    MSG_DIFF_UNAVAILABLE,
    MSG_NOT_CONFIRMED,
    MSG_OLD_ID,
    MSG_MISSING_FROM_POST,
    MSG_UNREADABLE,
)

NO_FILE = object()  # the directory exists but holds no VERIFICATION.md
KEEP = object()     # the test already put something into the directory

TASK_PLAN_TEXT = """# Task Plan: task0007 -- Fix auth bypass

## Goal

Fix the auth bypass.

## Requirements

FR1

## Scope

### Files to Create

### Files to Modify
- `src/auth.go` -- the fix

## Design

Small change.

## Acceptance Criteria (MANDATORY)

- [ ] AC-1: the bypass is closed

## Test Notes

None.

## Out of Scope

None.
"""


def _write_verification_md(dir_path, scenario_ids):
    dir_path.mkdir(parents=True, exist_ok=True)
    lines = [
        "## Test Verification",
        "",
        "### Test Scenarios from SPEC.md",
        "",
        "| ID | Scenario | Expected | Layer |",
        "|---|---|---|---|",
    ]
    lines.extend(f"| {tid} | scenario | outcome | Unit |" for tid in scenario_ids)
    (dir_path / "VERIFICATION.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _messages(errors):
    return [e["message"] for e in errors]


class TestRenameCoverageDiff(unittest.TestCase):
    PRE_INDEX = {"TS3": ["FR1"]}

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.feature_dir = self.tmp / "feature-dir"
        self.baseline_dir = self.tmp / "baseline-dir"

    # -- builders -----------------------------------------------------------

    def _make_dir(self, path, ids):
        """Builds the directory afresh (sub-cases share one temporary
        directory). None: the directory is not made (the option is not given).
        NO_FILE: the directory exists without a VERIFICATION.md. KEEP: the
        directory is left as the test made it. A list: the IDs the
        VERIFICATION.md defines."""
        if ids is KEEP:
            return path
        shutil.rmtree(path, ignore_errors=True)
        if ids is None:
            return None
        path.mkdir(parents=True)
        if ids is not NO_FILE:
            _write_verification_md(path, ids)
        return path

    def _errors(
        self,
        *,
        covered=("TS-3",),
        renames=(("TS3", "TS-3"),),
        index=None,
        post=("TS-3",),
        baseline=("TS3",),
    ):
        index = self.PRE_INDEX if index is None else index
        doc_corrections = (
            _ABSENT if renames is None else [_correction(*[_rename(f, t) for f, t in renames])]
        )
        result = _rework_result(covered=covered, doc_corrections=doc_corrections)
        return VWO._validate_rework_index(
            result["payload"]["rework_index"],
            result["workflow_patch"],
            _rework_envelope(index),
            self._make_dir(self.feature_dir, post),
            self._make_dir(self.baseline_dir, baseline),
            payload=result["payload"],
        )

    def _assert_one_rejection(self, errors, *phrases):
        self.assertEqual(_codes(errors), [REWORK_INDEX_CODE], errors)
        for phrase in phrases:
            self.assertIn(phrase, errors[0]["message"])

    def _assert_only_phrase(self, errors, phrase):
        """The one message carries `phrase` and none of the other messages' phrases."""
        message = errors[0]["message"]
        self.assertIn(phrase, message)
        for other in ALL_MESSAGE_PHRASES:
            if other != phrase:
                self.assertNotIn(other, message)

    # -- AC-1: the four conditions (TS-1, TS-2, TS-3, TS-6) -----------------

    def test_ac1_ts6_rename_confirmed_by_both_documents_is_accepted(self):
        self.assertEqual(self._errors(), [])

    def test_ac1_ts1_to_absent_from_the_post_change_document_is_rejected(self):
        errors = self._errors(post=["TS-4"])
        self._assert_one_rejection(
            errors, "'TS3'", "'TS-3'", "'TS-3' is absent from the post-change VERIFICATION.md"
        )
        self._assert_only_phrase(errors, MSG_NOT_CONFIRMED)

    def test_ac1_ts2_from_still_in_the_post_change_document_is_rejected(self):
        errors = self._errors(post=["TS3", "TS-3"])
        self._assert_one_rejection(
            errors, "'TS3'", "'TS-3'", "'TS3' is still defined in the post-change VERIFICATION.md"
        )
        self._assert_only_phrase(errors, MSG_NOT_CONFIRMED)

    def test_ac1_ts3_from_absent_from_the_baseline_document_is_rejected(self):
        for label, baseline in (("empty baseline", []), ("no baseline VERIFICATION.md", NO_FILE)):
            with self.subTest(case=label):
                errors = self._errors(baseline=baseline)
                self._assert_one_rejection(
                    errors, "'TS3'", "'TS-3'", "'TS3' is absent from the baseline VERIFICATION.md"
                )
                self._assert_only_phrase(errors, MSG_NOT_CONFIRMED)

    def test_ac1_from_that_is_not_a_verification_index_key_is_rejected(self):
        errors = self._errors(renames=(("TS9", "TS-3"),), post=["TS-3"], baseline=["TS9"])
        self._assert_one_rejection(
            errors, "'TS9'", "'TS-3'", "'TS9' is not a verification_index key"
        )
        self._assert_only_phrase(errors, MSG_NOT_CONFIRMED)

    def test_ac1_every_declared_pair_with_the_same_to_must_be_confirmed(self):
        index = {"TS3": ["FR1"], "TS4": ["FR1"]}
        renames = (("TS3", "TS-3"), ("TS4", "TS-3"))
        errors = self._errors(renames=renames, index=index, baseline=["TS3"])
        self._assert_one_rejection(errors, "'TS4'", "'TS-3'", "'TS4' is absent from the baseline")
        self.assertEqual(
            self._errors(renames=renames, index=index, baseline=["TS3", "TS4"]), []
        )

    def test_ac1_the_first_failed_condition_is_the_one_named(self):
        # from is not a key AND to is absent from the post set: the key
        # condition comes first.
        errors = self._errors(renames=(("TS9", "TS-3"),), post=["TS-4"], baseline=["TS9"])
        self._assert_one_rejection(errors, "'TS9' is not a verification_index key")
        self.assertNotIn("absent from the post-change", errors[0]["message"])

    def test_ac1_rename_is_judged_per_covered_id(self):
        errors = self._errors(covered=("TS-3", "TS-7"), post=["TS-3"])
        self.assertEqual(_codes(errors), [REWORK_INDEX_CODE])
        self.assertIn("'TS-7'", errors[0]["message"])
        self._assert_only_phrase(errors, MSG_NO_DECLARATION)

    # -- AC-2: the diff is unavailable (TS-4, TS-5) -------------------------

    def test_ac2_ts4_missing_option_means_no_rename_is_accepted_and_the_message_names_it(self):
        cases = (
            ("neither option", None, None, ("--feature-dir", "--baseline-dir")),
            ("no --baseline-dir", ["TS-3"], None, ("--baseline-dir",)),
            ("no --feature-dir", None, ["TS3"], ("--feature-dir",)),
        )
        for label, post, baseline, named in cases:
            with self.subTest(case=label):
                errors = self._errors(post=post, baseline=baseline)
                self._assert_one_rejection(errors, "'TS-3'", *named)
                self._assert_only_phrase(errors, MSG_DIFF_UNAVAILABLE)
                for flag in ("--feature-dir", "--baseline-dir"):
                    if flag not in named:
                        self.assertNotIn(flag, errors[0]["message"])

    def test_ac2_ts5_feature_dir_without_a_verification_md_is_unavailable(self):
        errors = self._errors(post=NO_FILE, baseline=["TS3"])
        self._assert_one_rejection(errors, "'TS-3'", "feature-dir's VERIFICATION.md")
        self._assert_only_phrase(errors, MSG_DIFF_UNAVAILABLE)
        self.assertNotIn("--baseline-dir", errors[0]["message"])

    def test_ac2_diff_unavailable_message_differs_from_the_no_declaration_message(self):
        unavailable = self._errors(post=None, baseline=None)
        undeclared = self._errors(renames=None, post=None, baseline=None)
        self._assert_only_phrase(unavailable, MSG_DIFF_UNAVAILABLE)
        self._assert_only_phrase(undeclared, MSG_NO_DECLARATION)
        self.assertNotEqual(unavailable[0]["message"], undeclared[0]["message"])

    def test_ac2_no_declaration_message_keeps_its_wording(self):
        errors = self._errors(renames=None, post=["TS-3"], baseline=["TS3"])
        self.assertEqual(
            errors[0]["message"],
            "task0007: covered_by_existing 'TS-3' not in verification_index, and no "
            "declared rename maps it to the verification index "
            "(payload.doc_corrections[].scenario_renames)",
        )

    # -- AC-3: the old ID of a rename (TS-7) --------------------------------

    def test_ac3_ts7_from_of_a_declared_pair_is_rejected_with_the_diff(self):
        errors = self._errors(covered=("TS3",), post=["TS-3"], baseline=["TS3"])
        self._assert_one_rejection(errors, "'TS3'", "'TS-3'")
        self._assert_only_phrase(errors, MSG_OLD_ID)

    def test_ac3_ts7_from_of_a_declared_pair_is_rejected_without_the_diff(self):
        errors = self._errors(covered=("TS3",), post=None, baseline=None)
        self._assert_one_rejection(errors, "'TS3'", "'TS-3'")
        self._assert_only_phrase(errors, MSG_OLD_ID)

    def test_ac3_from_is_rejected_even_when_the_to_is_confirmed(self):
        errors = self._errors(covered=("TS-3", "TS3"))
        self._assert_one_rejection(errors, "'TS3'")
        self._assert_only_phrase(errors, MSG_OLD_ID)

    def test_ac3_from_is_rejected_when_the_diff_cannot_confirm_the_rename(self):
        errors = self._errors(covered=("TS3",), post=["TS3", "TS-3"], baseline=["TS3"])
        self._assert_one_rejection(errors)
        self._assert_only_phrase(errors, MSG_OLD_ID)

    # -- AC-4: every covered ID must exist after the change (TS-8, TS-9) -----

    def test_ac4_ts8_verification_index_key_absent_from_the_post_set_is_rejected(self):
        errors = self._errors(
            covered=("TS-8",), renames=None, index={"TS-8": ["FR1"]}, post=["TS-1"], baseline=["TS-8"]
        )
        self._assert_one_rejection(errors, "'TS-8'")
        self._assert_only_phrase(errors, MSG_MISSING_FROM_POST)

    def test_ac4_unrelated_key_is_rejected_next_to_a_confirmed_rename(self):
        errors = self._errors(
            covered=("TS-3", "TS-8"),
            index={"TS3": ["FR1"], "TS-8": ["FR1"]},
            post=["TS-3"],
        )
        self._assert_one_rejection(errors, "'TS-8'")
        self._assert_only_phrase(errors, MSG_MISSING_FROM_POST)

    def test_ac4_verification_index_key_present_in_the_post_set_is_accepted(self):
        errors = self._errors(
            covered=("TS-8",), renames=None, index={"TS-8": ["FR1"]}, post=["TS-8"], baseline=["TS-8"]
        )
        self.assertEqual(errors, [])

    def test_ac4_ts9_without_the_directories_a_key_is_accepted_as_before(self):
        for label, post, baseline in (
            ("neither option", None, None),
            ("only --feature-dir", ["TS-1"], None),
            ("only --baseline-dir", None, ["TS-8"]),
            ("feature-dir without VERIFICATION.md", NO_FILE, ["TS-8"]),
        ):
            with self.subTest(case=label):
                errors = self._errors(
                    covered=("TS-8",),
                    renames=None,
                    index={"TS-8": ["FR1"]},
                    post=post,
                    baseline=baseline,
                )
                self.assertEqual(errors, [])

    # -- AC-7: malformed input ends in an error, never an exception ----------

    def test_ac7_non_string_covered_entries_are_reported_and_never_raise(self):
        for label, post, baseline in (("with the diff", ["TS-3"], ["TS3"]), ("without", None, None)):
            for bad in (3, None, ["TS-3"], {"id": "TS-3"}, True, 1.5):
                with self.subTest(case=label, entry=repr(bad)):
                    errors = self._errors(covered=(bad,), post=post, baseline=baseline)
                    self._assert_one_rejection(errors, "not a string")

    def test_ac7_a_non_string_entry_does_not_hide_the_judgement_of_the_others(self):
        errors = self._errors(covered=(["TS-3"], "TS-3", "TS-7"))
        self.assertEqual(_codes(errors), [REWORK_INDEX_CODE, REWORK_INDEX_CODE])
        self.assertIn("not a string", errors[0]["message"])
        self.assertIn("'TS-7'", errors[1]["message"])

    def test_ac7_covered_by_existing_that_is_not_a_list_is_reported(self):
        result = _rework_result(covered=())
        result["payload"]["rework_index"]["task0007"]["covered_by_existing"] = "TS-3"
        errors = VWO._validate_rework_index(
            result["payload"]["rework_index"],
            result["workflow_patch"],
            _rework_envelope({"TS-3": ["FR1"]}),
            None,
            None,
            payload=result["payload"],
        )
        self.assertEqual(_codes(errors), [REWORK_INDEX_CODE])
        self.assertIn("covered_by_existing", errors[0]["message"])

    def test_ac7_unreadable_verification_md_is_one_error_naming_the_file(self):
        # Both rename (row 3) and key (row 2) need the post set; one error
        # names the unreadable file and nothing is accepted on its strength.
        self.feature_dir.mkdir()
        (self.feature_dir / "VERIFICATION.md").mkdir()
        errors = self._errors(
            covered=("TS-3", "TS-8"),
            index={"TS3": ["FR1"], "TS-8": ["FR1"]},
            post=KEEP,
            baseline=["TS3"],
        )
        self.assertEqual(_codes(errors), [REWORK_INDEX_CODE], errors)
        self._assert_only_phrase(errors, MSG_UNREADABLE)
        self.assertIn(str(self.feature_dir / "VERIFICATION.md"), errors[0]["message"])

    def test_ac7_undecodable_post_change_verification_md_is_one_error_naming_the_file(self):
        self.feature_dir.mkdir()
        (self.feature_dir / "VERIFICATION.md").write_bytes(b"### Test Scenarios from SPEC.md\n\xff\xfe\x80 TS-3\n")
        errors = self._errors(post=KEEP, baseline=["TS3"])
        self.assertEqual(_codes(errors), [REWORK_INDEX_CODE], errors)
        self._assert_only_phrase(errors, MSG_UNREADABLE)
        self.assertIn(str(self.feature_dir / "VERIFICATION.md"), errors[0]["message"])

    def test_ac7_undecodable_baseline_verification_md_is_one_error_naming_the_file(self):
        self.baseline_dir.mkdir()
        (self.baseline_dir / "VERIFICATION.md").write_bytes(b"\xff\xfe\x80\x81")
        errors = self._errors(post=["TS-3"], baseline=KEEP)
        self.assertEqual(_codes(errors), [REWORK_INDEX_CODE], errors)
        self._assert_only_phrase(errors, MSG_UNREADABLE)
        self.assertIn(str(self.baseline_dir / "VERIFICATION.md"), errors[0]["message"])

    def test_ac7_an_unreadable_baseline_is_not_reported_when_no_id_needs_it(self):
        # A verification_index key is judged against the post set only.
        self.baseline_dir.mkdir()
        (self.baseline_dir / "VERIFICATION.md").write_bytes(b"\xff\xfe\x80\x81")
        errors = self._errors(
            covered=("TS-8",), renames=None, index={"TS-8": ["FR1"]}, post=["TS-8"], baseline=KEEP
        )
        self.assertEqual(errors, [])

    def test_ac7_an_unreadable_file_is_reported_for_new_scenarios_too(self):
        self.feature_dir.mkdir()
        (self.feature_dir / "VERIFICATION.md").write_bytes(b"\xff\xfe\x80\x81")
        result = _rework_result(covered=())
        result["payload"]["rework_index"]["task0007"]["new_scenarios"] = ["TS-9"]
        result["workflow_patch"]["requirements_patch"] = {
            "mode": "merge_entries",
            "entries": {"FR1": {"expected": {}, "set": {"tests_append": ["TS-9"]}}},
        }
        errors = VWO._validate_rework_index(
            result["payload"]["rework_index"],
            result["workflow_patch"],
            _rework_envelope({}),
            self._make_dir(self.feature_dir, KEEP),
            self._make_dir(self.baseline_dir, []),
            payload=result["payload"],
        )
        self.assertEqual(_codes(errors), [REWORK_INDEX_CODE], errors)
        self._assert_only_phrase(errors, MSG_UNREADABLE)

    # -- AC-7 through the CLI: exit 1 with JSON error details, never exit 2 --

    def _run_cli(self, result, index, *, post=("TS-3",), baseline=("TS3",), runner=run_cli):
        feature_dir = self._make_dir(self.feature_dir, post)
        baseline_dir = self._make_dir(self.baseline_dir, baseline)
        if feature_dir is not None:
            (feature_dir / "tasks").mkdir(parents=True, exist_ok=True)
            (feature_dir / "tasks" / "task0007.md").write_text(TASK_PLAN_TEXT, encoding="utf-8")
        (self.tmp / "input.json").write_text(json.dumps(result), encoding="utf-8")
        (self.tmp / "envelope.json").write_text(
            json.dumps(_rework_envelope(index)), encoding="utf-8"
        )
        args = [
            "--kind", "worker-result",
            "--worker", "rework-planner",
            "--input", str(self.tmp / "input.json"),
            "--input-envelope", str(self.tmp / "envelope.json"),
        ]
        if feature_dir is not None:
            args += ["--feature-dir", str(feature_dir)]
        if baseline_dir is not None:
            args += ["--baseline-dir", str(baseline_dir)]
        return runner(args)

    def _assert_rejected_with_json(self, completed, *phrases):
        self.assertEqual(completed.returncode, 1, completed.stdout + completed.stderr)
        errors = json.loads(completed.stdout)["errors"]
        self.assertEqual(_codes(errors), [REWORK_INDEX_CODE] * len(errors))
        self.assertTrue(errors)
        for phrase in phrases:
            self.assertTrue(any(phrase in m for m in _messages(errors)), (phrase, errors))
        return errors

    def test_ac7_cli_baseline_the_valid_rename_is_accepted_with_both_documents(self):
        completed = self._run_cli(
            _rework_result(doc_corrections=[_correction(_rename("TS3", "TS-3"))]), self.PRE_INDEX
        )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_ac7_cli_malformed_rename_declarations_exit_1_with_the_diff_available(self):
        valid_pair = _rename("TS3", "TS-3")
        malformed = {
            "scenario_renames is a string": [{"scenario_renames": "TS3->TS-3"}],
            "scenario_renames is a mapping": [{"scenario_renames": valid_pair}],
            "scenario_renames is null": [{"scenario_renames": None}],
            "pair is a string": [_correction("TS3->TS-3")],
            "pair is null": [_correction(None)],
            "pair is a list": [_correction(["TS3", "TS-3"])],
            "pair lacks from": [_correction({"to": "TS-3"})],
            "pair lacks to": [_correction({"from": "TS3"})],
            "from is not a string": [_correction(_rename(3, "TS-3"))],
            "to is not a string": [_correction(_rename("TS3", ["TS-3"]))],
            "from is a list": [_correction(_rename(["TS3"], "TS-3"))],
        }
        for label, doc_corrections in malformed.items():
            with self.subTest(case=label):
                completed = self._run_cli(
                    _rework_result(doc_corrections=doc_corrections), self.PRE_INDEX
                )
                self._assert_rejected_with_json(completed, MSG_NO_DECLARATION)

    def test_ac7_cli_non_string_covered_entry_exits_1_with_and_without_the_diff(self):
        for label, post, baseline in (("with the diff", ("TS-3",), ("TS3",)), ("without", None, None)):
            for bad in (3, None, ["TS-3"], {"id": "TS-3"}):
                with self.subTest(case=label, entry=repr(bad)):
                    result = _rework_result(covered=(bad,))
                    completed = self._run_cli(result, self.PRE_INDEX, post=post, baseline=baseline)
                    self._assert_rejected_with_json(completed, "not a string")

    def test_ac7_cli_verification_md_that_is_a_directory_exits_1(self):
        feature_dir = self._make_dir(self.feature_dir, NO_FILE)
        (feature_dir / "VERIFICATION.md").mkdir()
        result = _rework_result(doc_corrections=[_correction(_rename("TS3", "TS-3"))])
        completed = self._run_cli(result, self.PRE_INDEX, post=KEEP, baseline=("TS3",))
        errors = self._assert_rejected_with_json(completed, MSG_UNREADABLE)
        self.assertEqual(len(errors), 1, errors)

    def test_ac7_cli_undecodable_verification_md_exits_1(self):
        for which in ("feature", "baseline"):
            with self.subTest(which=which):
                bad_dir = self.feature_dir if which == "feature" else self.baseline_dir
                bad_dir.mkdir(parents=True, exist_ok=True)
                (bad_dir / "VERIFICATION.md").write_bytes(b"### Test Scenarios from SPEC.md\n\xff\xfe\x80\n")
                result = _rework_result(doc_corrections=[_correction(_rename("TS3", "TS-3"))])
                completed = self._run_cli(
                    result,
                    self.PRE_INDEX,
                    post=KEEP if which == "feature" else ("TS-3",),
                    baseline=KEEP if which == "baseline" else ("TS3",),
                )
                errors = self._assert_rejected_with_json(completed, MSG_UNREADABLE)
                self.assertEqual(len(errors), 1, errors)

    def test_ac7_cli_new_scenarios_with_an_undecodable_verification_md_exits_1(self):
        result = _rework_result(covered=())
        result["payload"]["rework_index"]["task0007"]["new_scenarios"] = ["TS-9"]
        result["workflow_patch"]["requirements_patch"] = {
            "mode": "merge_entries",
            "entries": {"FR1": {"expected": {}, "set": {"tests_append": ["TS-9"]}}},
        }
        self.feature_dir.mkdir()
        (self.feature_dir / "VERIFICATION.md").write_bytes(b"\xff\xfe\x80\x81")
        completed = self._run_cli(result, {}, post=KEEP, baseline=())
        self._assert_rejected_with_json(completed, MSG_UNREADABLE)


# ---------------------------------------------------------------------------
# AC-5 / AC-6: the new fixtures and the runner that wires feature-dir /
# baseline-dir (rework-docs-only-medium-fixes, task0001)
# ---------------------------------------------------------------------------

DECLARED_FIXTURE = "valid-mixed-round-renamed-scenario-declared"
UNDECLARED_FIXTURE = "invalid-mixed-round-renamed-scenario-undeclared"

# Fixtures that join the rework-planner group for FR1 / FR2. They stay out of
# FIXTURE_EXPECTED_CODES, the set that test_ac6_no_fixture_uses_tests_replace
# and the six-fixture count pin, and none of them contains tests_replace.
RENAME_DIFF_FIXTURE_EXPECTED = {
    "invalid-mixed-round-rename-to-missing": MSG_NOT_CONFIRMED,
    "invalid-mixed-round-rename-without-diff": MSG_DIFF_UNAVAILABLE,
    "invalid-mixed-round-rename-from-covered": MSG_OLD_ID,
}


def _fixture_json(case, name):
    return json.loads((FIXTURE_GROUP_DIR / case / name).read_text(encoding="utf-8"))


class TestRenameDiffFixtures(unittest.TestCase):
    def test_ac5_the_three_fixtures_exist_with_input_and_envelope(self):
        for case in RENAME_DIFF_FIXTURE_EXPECTED:
            for name in ("input.json", "envelope.json"):
                with self.subTest(case=case, file=name):
                    self.assertTrue((FIXTURE_GROUP_DIR / case / name).is_file())

    def test_ac5_each_fixture_is_rejected_with_exit_1_and_rework_index(self):
        for case, phrase in RENAME_DIFF_FIXTURE_EXPECTED.items():
            with self.subTest(case=case):
                completed = run_cli(fixture_cli_args(case))
                self.assertEqual(completed.returncode, 1, completed.stdout + completed.stderr)
                errors = json.loads(completed.stdout)["errors"]
                self.assertEqual(_codes(errors), [REWORK_INDEX_CODE], errors)
                self.assertIn(phrase, errors[0]["message"])

    def test_ac5_no_new_fixture_uses_tests_replace(self):
        for case in RENAME_DIFF_FIXTURE_EXPECTED:
            self.assertNotIn(case, FIXTURE_EXPECTED_CODES)
            for path in (FIXTURE_GROUP_DIR / case).rglob("*"):
                if path.is_file():
                    with self.subTest(path=str(path.relative_to(FIXTURE_GROUP_DIR))):
                        self.assertNotIn("tests_replace", path.read_text(encoding="utf-8"))

    def test_ac5_valid_fixture_carries_the_post_change_and_baseline_documents(self):
        case_dir = FIXTURE_GROUP_DIR / DECLARED_FIXTURE
        post = VWO.extract_verification_scenario_ids(
            (case_dir / "feature-dir" / "VERIFICATION.md").read_text(encoding="utf-8")
        )
        baseline = VWO.extract_verification_scenario_ids(
            (case_dir / "baseline-dir" / "VERIFICATION.md").read_text(encoding="utf-8")
        )
        self.assertIn("TS-3", post)
        self.assertNotIn("TS3", post)
        self.assertIn("TS3", baseline)

    def test_ac5_to_missing_defines_every_other_id_but_not_the_renamed_to(self):
        case_dir = FIXTURE_GROUP_DIR / "invalid-mixed-round-rename-to-missing"
        declared = _fixture_json("invalid-mixed-round-rename-to-missing", "input.json")
        pair = declared["payload"]["doc_corrections"][0]["scenario_renames"][0]
        covered = declared["payload"]["rework_index"]["task0007"]["covered_by_existing"]
        self.assertEqual(covered, [pair["to"]])
        post = VWO.extract_verification_scenario_ids(
            (case_dir / "feature-dir" / "VERIFICATION.md").read_text(encoding="utf-8")
        )
        baseline = VWO.extract_verification_scenario_ids(
            (case_dir / "baseline-dir" / "VERIFICATION.md").read_text(encoding="utf-8")
        )
        self.assertNotIn(pair["to"], post)
        self.assertNotIn(pair["from"], post)
        self.assertIn(pair["from"], baseline)
        self.assertIn(pair["from"], _fixture_json("invalid-mixed-round-rename-to-missing", "envelope.json")["verification_index"])

    def test_ac5_without_diff_has_neither_directory(self):
        case_dir = FIXTURE_GROUP_DIR / "invalid-mixed-round-rename-without-diff"
        self.assertFalse((case_dir / "feature-dir").exists())
        self.assertFalse((case_dir / "baseline-dir").exists())
        self.assertEqual(
            _fixture_json("invalid-mixed-round-rename-without-diff", "input.json"),
            _fixture_json(DECLARED_FIXTURE, "input.json"),
        )
        self.assertEqual(
            _fixture_json("invalid-mixed-round-rename-without-diff", "envelope.json"),
            _fixture_json(DECLARED_FIXTURE, "envelope.json"),
        )

    def test_ac5_from_covered_differs_from_the_valid_fixture_only_by_the_from_id(self):
        valid = _fixture_json(DECLARED_FIXTURE, "input.json")
        derived = _fixture_json("invalid-mixed-round-rename-from-covered", "input.json")
        covered = derived["payload"]["rework_index"]["task0007"]["covered_by_existing"]
        self.assertEqual(
            covered,
            valid["payload"]["rework_index"]["task0007"]["covered_by_existing"] + ["TS3"],
        )
        valid["payload"]["rework_index"]["task0007"]["covered_by_existing"] = covered
        self.assertEqual(valid, derived)
        for dirname in ("feature-dir", "baseline-dir"):
            self.assertTrue(
                (FIXTURE_GROUP_DIR / "invalid-mixed-round-rename-from-covered" / dirname / "VERIFICATION.md").is_file()
            )

    def test_ac2_the_two_messages_of_the_pair_of_fixtures_differ_and_name_what_is_missing(self):
        undeclared = json.loads(run_cli(fixture_cli_args(UNDECLARED_FIXTURE)).stdout)["errors"]
        without_diff = json.loads(
            run_cli(fixture_cli_args("invalid-mixed-round-rename-without-diff")).stdout
        )["errors"]
        self.assertEqual(_codes(undeclared), [REWORK_INDEX_CODE])
        self.assertEqual(_codes(without_diff), [REWORK_INDEX_CODE])
        self.assertNotEqual(undeclared[0]["message"], without_diff[0]["message"])
        self.assertIn(MSG_NO_DECLARATION, undeclared[0]["message"])
        self.assertIn(MSG_DIFF_UNAVAILABLE, without_diff[0]["message"])
        self.assertNotIn(MSG_NO_DECLARATION, without_diff[0]["message"])
        self.assertIn("--feature-dir", without_diff[0]["message"])
        self.assertIn("--baseline-dir", without_diff[0]["message"])

    def test_ac6_the_runner_passes_each_directory_that_exists_independently(self):
        def flags(case):
            args = fixture_cli_args(case)
            return [a for a in args if a in ("--feature-dir", "--baseline-dir")]

        self.assertEqual(flags(DECLARED_FIXTURE), ["--feature-dir", "--baseline-dir"])
        self.assertEqual(flags(UNDECLARED_FIXTURE), [])
        args = fixture_cli_args(DECLARED_FIXTURE)
        self.assertEqual(
            args[args.index("--feature-dir") + 1],
            str(FIXTURE_GROUP_DIR / DECLARED_FIXTURE / "feature-dir"),
        )
        self.assertEqual(
            args[args.index("--baseline-dir") + 1],
            str(FIXTURE_GROUP_DIR / DECLARED_FIXTURE / "baseline-dir"),
        )

    def test_ac6_every_valid_rework_planner_fixture_is_accepted_with_exit_0(self):
        cases = sorted(
            p.name for p in FIXTURE_GROUP_DIR.iterdir() if p.is_dir() and p.name.startswith("valid-")
        )
        self.assertIn(DECLARED_FIXTURE, cases)
        for case in cases:
            with self.subTest(case=case):
                completed = run_cli(fixture_cli_args(case))
                self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)


# ---------------------------------------------------------------------------
# VERIFICATION.md that is not a bounded regular file
# (verification-md-regular-file-read, task0001; FR1-FR4, NFR1, NFR2)
#
# The scenario-ID loader reads VERIFICATION.md only when it is a regular file
# of at most MAX_PLAN_READ_BYTES: a FIFO, a symlink (to /dev/zero, to a regular
# file or to nothing), a directory, an over-limit file and bytes that are not
# UTF-8 all give the unreadable state. A case that hands the loader or the CLI
# a FIFO or a /dev/zero link runs in a child process with a short timeout and,
# where the platform supports one, a memory cap, so that a reverted fix fails
# the case instead of hanging or exhausting the test runner.
# ---------------------------------------------------------------------------

CHILD_TIMEOUT_SECONDS = 15
CHILD_MEMORY_CAP_BYTES = 512 * 1024 * 1024
DEV_ZERO = Path("/dev/zero")
OVER_LIMIT_FACTOR = 50  # the sparse file is this many times MAX_PLAN_READ_BYTES

# Calls `_load_scenario_ids` once on the path in argv[2] and reports the
# returned (state, value) as JSON.
LOADER_CHILD_SOURCE = """
import importlib.util, json, pathlib, sys
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("validate_worker_output", sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
state, value = module._load_scenario_ids(pathlib.Path(sys.argv[2]))
if state == "ok":
    value = sorted(value)
json.dump([state, value], sys.stdout)
"""


def _cap_child_memory():
    """Runs in the child before it starts executing: caps its address space."""
    try:
        resource.setrlimit(resource.RLIMIT_AS, (CHILD_MEMORY_CAP_BYTES, CHILD_MEMORY_CAP_BYTES))
    except (ValueError, OSError):
        pass  # the platform does not enforce it; the timeout alone applies


def run_limited(cmd):
    """Runs `cmd` in a child with a timeout of seconds and a memory cap (where
    the platform supports one). A timeout fails the calling test."""
    kwargs = {}
    if resource is not None and os.name == "posix":
        kwargs["preexec_fn"] = _cap_child_memory
    try:
        return subprocess.run(
            cmd, capture_output=True, text=True, timeout=CHILD_TIMEOUT_SECONDS, **kwargs
        )
    except subprocess.TimeoutExpired as exc:
        raise AssertionError(
            f"the child did not finish within {CHILD_TIMEOUT_SECONDS} seconds: {cmd[-1]}"
        ) from exc


def run_cli_limited(args):
    """`run_cli` with a timeout and a memory cap."""
    return run_limited([sys.executable, str(SCRIPT_PATH)] + list(args))


def load_scenario_ids_in_child(path):
    """`_load_scenario_ids(path)` called once in a limited child process, as
    (state, value). The runner itself never touches a FIFO or a /dev/zero link."""
    completed = run_limited(
        [sys.executable, "-B", "-c", LOADER_CHILD_SOURCE, str(SCRIPT_PATH), str(path)]
    )
    if completed.returncode != 0:
        raise AssertionError(
            f"the loader child exited {completed.returncode}: {completed.stdout}{completed.stderr}"
        )
    state, value = json.loads(completed.stdout)
    return state, value


def make_fifo(path):
    if not hasattr(os, "mkfifo"):
        raise unittest.SkipTest("os.mkfifo is not available on this platform")
    try:
        os.mkfifo(path)
    except OSError as exc:
        raise unittest.SkipTest(f"a FIFO cannot be created here: {exc}")


def make_dev_zero_link(path):
    if not DEV_ZERO.exists():
        raise unittest.SkipTest("/dev/zero does not exist on this platform")
    try:
        os.symlink(DEV_ZERO, path)
    except (OSError, NotImplementedError) as exc:
        raise unittest.SkipTest(f"a symlink cannot be created here: {exc}")


def _sized_verification_md(scenario_ids, size):
    """UTF-8 bytes of exactly `size` bytes: a VERIFICATION.md defining
    `scenario_ids`, padded with spaces."""
    head = "".join(
        [
            "## Test Verification\n\n### Test Scenarios from SPEC.md\n\n",
            "| ID | Scenario | Expected | Layer |\n|---|---|---|---|\n",
        ]
        + [f"| {tid} | scenario | outcome | Unit |\n" for tid in scenario_ids]
    ).encode("utf-8")
    assert len(head) <= size, (len(head), size)
    return head + b" " * (size - len(head))


class TestLoadScenarioIdsFileKinds(unittest.TestCase):
    """The loader contract per kind of directory entry. `_load_scenario_ids`
    returns (state, value) and never raises."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        self.path = self.tmp / "VERIFICATION.md"

    def _assert_unreadable(self, result):
        state, reason = result
        self.assertEqual(state, "unreadable", result)
        self.assertIsInstance(reason, str, result)
        self.assertTrue(reason, result)

    # -- AC-1 (TS-4): entries that are not regular files ---------------------

    def test_ac1_fifo_with_no_writer_is_unreadable_and_returns(self):
        make_fifo(self.path)
        self._assert_unreadable(load_scenario_ids_in_child(self.path))

    def test_ac1_symlink_to_dev_zero_is_unreadable_and_returns(self):
        make_dev_zero_link(self.path)
        self._assert_unreadable(load_scenario_ids_in_child(self.path))

    def test_ac1_symlink_to_a_regular_file_with_valid_ids_is_unreadable(self):
        _write_verification_md(self.tmp / "real", ["TS-1", "TS-2"])
        try:
            os.symlink(self.tmp / "real" / "VERIFICATION.md", self.path)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"a symlink cannot be created here: {exc}")
        self._assert_unreadable(VWO._load_scenario_ids(self.path))

    def test_ac1_dangling_symlink_is_unreadable_not_absent(self):
        try:
            os.symlink(self.tmp / "nowhere", self.path)
        except (OSError, NotImplementedError) as exc:
            self.skipTest(f"a symlink cannot be created here: {exc}")
        self._assert_unreadable(VWO._load_scenario_ids(self.path))

    # -- AC-2 (TS-5): the byte limit ------------------------------------------

    def test_ac2_file_one_byte_over_the_limit_is_unreadable(self):
        self.path.write_bytes(_sized_verification_md(["TS-1"], VWO.MAX_PLAN_READ_BYTES + 1))
        self._assert_unreadable(VWO._load_scenario_ids(self.path))

    def test_ac2_file_of_exactly_the_limit_with_valid_ids_is_ok(self):
        self.path.write_bytes(_sized_verification_md(["TS-1", "TS-2"], VWO.MAX_PLAN_READ_BYTES))
        self.assertEqual(self.path.stat().st_size, VWO.MAX_PLAN_READ_BYTES)
        self.assertEqual(VWO._load_scenario_ids(self.path), ("ok", {"TS-1", "TS-2"}))

    def test_ac2_sparse_file_many_times_the_limit_is_unreadable_and_not_loaded_in_full(self):
        with open(self.path, "wb") as handle:
            handle.truncate(OVER_LIMIT_FACTOR * VWO.MAX_PLAN_READ_BYTES)
        tracemalloc.start()
        try:
            result = VWO._load_scenario_ids(self.path)
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
        self._assert_unreadable(result)
        self.assertLess(peak, 2 * VWO.MAX_PLAN_READ_BYTES)

    # -- AC-3 (TS-6): the behavior that stays ---------------------------------

    def test_ac3_missing_file_is_absent(self):
        self.assertEqual(VWO._load_scenario_ids(self.path), ("absent", None))

    def test_ac3_a_parent_that_is_not_a_directory_is_absent(self):
        (self.tmp / "file").write_text("x", encoding="utf-8")
        self.assertEqual(
            VWO._load_scenario_ids(self.tmp / "file" / "VERIFICATION.md"), ("absent", None)
        )

    def test_ac3_directory_is_unreadable(self):
        self.path.mkdir()
        self._assert_unreadable(VWO._load_scenario_ids(self.path))

    def test_ac3_bytes_that_are_not_utf8_are_unreadable(self):
        self.path.write_bytes(b"### Test Scenarios from SPEC.md\n\xff\xfe\x80 TS-3\n")
        self._assert_unreadable(VWO._load_scenario_ids(self.path))

    def test_ac3_regular_file_gives_the_ids_the_shared_derivation_gives(self):
        _write_verification_md(self.tmp, ["TS-1", "TS2", "TS-3"])
        text = self.path.read_text(encoding="utf-8")
        expected = VWO.extract_verification_scenario_ids(text)
        self.assertEqual(expected, {"TS-1", "TS2", "TS-3"})
        self.assertEqual(VWO._load_scenario_ids(self.path), ("ok", expected))

    def test_ac3_a_path_python_refuses_is_unreadable_and_never_raises(self):
        self._assert_unreadable(VWO._load_scenario_ids(self.tmp / "bad\0name" / "VERIFICATION.md"))


class TestVerificationMdNotRegularCli(unittest.TestCase):
    """The CLI validates a rework-planner result whose coverage judgement
    needs the VERIFICATION.md set of one side, with that file replaced by a
    FIFO or a /dev/zero link: exit 1 with exactly one rework-index error that
    names the file, before the timeout. The fixture builder is the one of
    TestRenameCoverageDiff."""

    setUp = TestRenameCoverageDiff.setUp
    PRE_INDEX = TestRenameCoverageDiff.PRE_INDEX
    _make_dir = TestRenameCoverageDiff._make_dir
    _run_cli = TestRenameCoverageDiff._run_cli
    _assert_rejected_with_json = TestRenameCoverageDiff._assert_rejected_with_json

    def _assert_one_unreadable_error(self, completed, path):
        errors = self._assert_rejected_with_json(completed, MSG_UNREADABLE, str(path))
        self.assertEqual(len(errors), 1, errors)
        self.assertIn(str(path), errors[0]["message"])
        self.assertIn(MSG_UNREADABLE, errors[0]["message"])

    def _run_with_feature_entry(self, make_entry):
        """The feature-dir VERIFICATION.md is replaced; the judgement of a
        declared rename needs the post-change set."""
        feature_dir = self._make_dir(self.feature_dir, NO_FILE)
        path = feature_dir / "VERIFICATION.md"
        make_entry(path)
        result = _rework_result(doc_corrections=[_correction(_rename("TS3", "TS-3"))])
        completed = self._run_cli(
            result, self.PRE_INDEX, post=KEEP, baseline=("TS3",), runner=run_cli_limited
        )
        return completed, path

    def _run_with_baseline_entry(self, make_entry):
        """The baseline-dir VERIFICATION.md is replaced; the judgement of a
        declared rename needs the baseline set."""
        baseline_dir = self._make_dir(self.baseline_dir, NO_FILE)
        path = baseline_dir / "VERIFICATION.md"
        make_entry(path)
        result = _rework_result(doc_corrections=[_correction(_rename("TS3", "TS-3"))])
        completed = self._run_cli(
            result, self.PRE_INDEX, post=("TS-3",), baseline=KEEP, runner=run_cli_limited
        )
        return completed, path

    def test_ac4_ts1_feature_dir_verification_md_that_is_a_fifo_exits_1(self):
        completed, path = self._run_with_feature_entry(make_fifo)
        self._assert_one_unreadable_error(completed, path)

    def test_ac5_ts2_feature_dir_verification_md_that_links_dev_zero_exits_1(self):
        completed, path = self._run_with_feature_entry(make_dev_zero_link)
        self._assert_one_unreadable_error(completed, path)

    def test_ac6_ts3_baseline_dir_verification_md_that_is_a_fifo_exits_1(self):
        completed, path = self._run_with_baseline_entry(make_fifo)
        self._assert_one_unreadable_error(completed, path)

    def test_ac6_ts3_baseline_dir_verification_md_that_links_dev_zero_exits_1(self):
        completed, path = self._run_with_baseline_entry(make_dev_zero_link)
        self._assert_one_unreadable_error(completed, path)


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


def _tests_replace_entry(pairs, contains=_ABSENT):
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


def _tests_replace_patch(entries):
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
        return VWO.validate_workflow_patch(_tests_replace_patch({"FR1": _tests_replace_entry(pairs, **kwargs)}))

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
            completed = _cli_via(Path(tmp), "workflow-patch", False, _tests_replace_patch({"FR1": _tests_replace_entry(CHAIN)}))
            self.assertEqual(completed.returncode, 1, completed.stdout + completed.stderr)
            self.assertEqual(_codes(json.loads(completed.stdout)["errors"]), [REQUIREMENTS_PATCH_CODE])

    def test_ac1_only_the_overlapping_entry_is_named(self):
        patch = _tests_replace_patch(
            {"FR1": _tests_replace_entry(DISJOINT), "FR2": _tests_replace_entry(CHAIN)}
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
            completed = _cli_via(Path(tmp), "workflow-patch", False, _tests_replace_patch({"FR1": _tests_replace_entry(SWAP)}))
            self.assertEqual(completed.returncode, 1, completed.stdout + completed.stderr)
            self.assertEqual(_codes(json.loads(completed.stdout)["errors"]), [REQUIREMENTS_PATCH_CODE])

    # AC-3 -----------------------------------------------------------------

    def test_ac3_chain_and_swap_are_rejected_on_all_four_routes_in_process(self):
        for label, pairs, overlap in (("chain", CHAIN, ["TS-2"]), ("swap", SWAP, ["TS-1", "TS-2"])):
            patch = _tests_replace_patch({"FR1": _tests_replace_entry(pairs)})
            for route, dry_run in ROUTES:
                with self.subTest(pairs=label, route=route, dry_run=dry_run):
                    errors = _errors_via(route, dry_run, patch)
                    self._assert_overlap_rejection(errors, overlap)
                    if route == "worker-result":
                        self.assertIn("workflow_patch", errors[0]["message"])

    def test_ac3_chain_and_swap_exit_1_on_all_four_routes_through_the_cli(self):
        for label, pairs in (("chain", CHAIN), ("swap", SWAP)):
            patch = _tests_replace_patch({"FR1": _tests_replace_entry(pairs)})
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
            patch = _fixture_json(case, "input.json")["workflow_patch"]
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
            result = _fixture_json(case, "input.json")
            envelope = _fixture_json(case, "envelope.json")
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
        patch = _tests_replace_patch({"FR1": _tests_replace_entry(DISJOINT)})
        for route, dry_run in ROUTES:
            with self.subTest(route=route, dry_run=dry_run):
                self.assertEqual(_errors_via(route, dry_run, patch), [])

    def test_ac4_valid_docs_only_round_fixture_is_accepted(self):
        completed = run_cli(fixture_cli_args(OVERLAP_SOURCE_FIXTURE))
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_ac4_pairs_sharing_a_to_are_not_rejected_by_this_check(self):
        patch = _tests_replace_patch({"FR1": _tests_replace_entry(SHARED_TO)})
        for route, dry_run in ROUTES:
            with self.subTest(route=route, dry_run=dry_run):
                self.assertEqual(_errors_via(route, dry_run, patch), [])

    def test_ac4_overlap_is_judged_per_entry(self):
        patch = _tests_replace_patch(
            {
                "FR1": _tests_replace_entry([_rename("TS-1", "TS-2")]),
                "FR2": _tests_replace_entry([_rename("TS-2", "TS-3")]),
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
                completed = run_cli(fixture_cli_args(case))
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
        source = _fixture_json(OVERLAP_SOURCE_FIXTURE, "input.json")
        source_envelope = _fixture_json(OVERLAP_SOURCE_FIXTURE, "envelope.json")
        for case, (pairs, _) in OVERLAP_FIXTURES.items():
            with self.subTest(case=case):
                derived = _fixture_json(case, "input.json")
                self.assertEqual(_fixture_json(case, "envelope.json"), source_envelope)
                derived_entries = derived["workflow_patch"]["requirements_patch"]["entries"]
                self.assertEqual(derived_entries["FR1"], _tests_replace_entry(pairs))
                source_entries = source["workflow_patch"]["requirements_patch"]["entries"]
                derived_entries["FR1"] = source_entries["FR1"]
                self.assertEqual(derived, source)

    # AC-6 -----------------------------------------------------------------

    def test_ac6_malformed_tests_replace_is_reported_never_raised_on_all_four_routes(self):
        for label, value in MALFORMED_TESTS_REPLACE.items():
            entry = {"expected": {"tests_contains": ["TS-1"]}, "set": {"tests_replace": value}}
            patch = _tests_replace_patch({"FR1": entry})
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
            patch = _tests_replace_patch({"FR1": entry})
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
