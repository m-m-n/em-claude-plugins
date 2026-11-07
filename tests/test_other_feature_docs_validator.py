"""Unit tests for the other-feature document route in
em-workflow/scripts/validate-worker-output.py
(plan-feature-docs-route, task0005; FR3, FR4, FR5, FR6, FR7, NFR2, NFR3).

What is pinned here is the validator's rendering of IMPLEMENTATION.md D2 to D5
of that feature, encoded directly in this module (it reads no planner-contract
or workflow-patch document):

- the scope predicate (D4) and the `other-feature-doc-scope` code on every
  requested, fixed and granted path (AC-1);
- admission of the `amend_other_feature` action (D2): implementation-planner,
  create-plan, in-scope path, non-null `expect_digest` (AC-2);
- the stage-1 request result (D3) and `other-feature-doc-request` (AC-3);
- the stage-2 fix declaration and `other-feature-doc-fix` (AC-4);
- the shape of the `other_feature_doc_fixes` phase-state record (D5, AC-5);
- malformed input is reported, never raised (AC-6);
- the byte-pin refresh comment naming this task (AC-7).

Standard-library imports only.
"""

import copy
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "em-workflow" / "scripts" / "validate-worker-output.py"
GATE_VOCAB_TEST_PATH = REPO_ROOT / "tests" / "test_gate_option_vocabulary.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("validate_worker_output", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VWO = _load_module()

SCOPE = "other-feature-doc-scope"
REQUEST = "other-feature-doc-request"
FIX = "other-feature-doc-fix"
OTHER_CODES = (SCOPE, REQUEST, FIX)

OWN = "self"
DOC_A = "feature-docs/other-a/THREAT-MODEL.md"
DOC_B = "feature-docs/other-b/SPEC.md"
DOC_C = "feature-docs/other-c/NOTE.md"
DIGEST = "sha256:" + "0" * 64


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------

def amend_target(path, digest=DIGEST):
    return {"path": path, "action": "amend_other_feature", "expect_digest": digest}


def make_envelope(targets=(), phase="create-plan", feature=OWN, roots=()):
    envelope = {
        "schema_version": 1,
        "request_id": "req-1",
        "phase": phase,
        "input_revision": {"input_digest": "sha256:x"},
        "write_policy": {"targets": [copy.deepcopy(t) for t in targets]},
        "allowed_write_roots": list(roots),
    }
    if feature is not None:
        envelope["feature"] = feature
    return envelope


def make_result(payload, written=(), patch=None, worker="implementation-planner", status="completed"):
    return {
        "schema_version": 1,
        "worker": worker,
        "request_id": "req-1",
        "status": status,
        "input_revision": {"input_digest": "sha256:x"},
        "mode_echo": None,
        "payload": payload,
        "workflow_patch": patch,
        "written_artifacts": [copy.deepcopy(w) for w in written],
        "question_packet": None,
        "blocking_reason": None,
    }


def validate(result, envelope, worker="implementation-planner", workflow=None):
    return VWO.validate_worker_result(result, worker, envelope=envelope, workflow=workflow)


def request_payload(*items):
    return {"other_feature_doc_requests": list(items)}


def request_item(path, reason="the plan needs it"):
    return {"path": path, "reason": reason}


def fix_item(path, change="added a section", reason="the plan relies on it"):
    return {"path": path, "change": change, "reason": reason}


def stage2_payload(fixes=None):
    payload = {"task_index": {}}
    if fixes is not None:
        payload["other_feature_doc_fixes"] = fixes
    return payload


def codes(errors):
    return [e["code"] for e in errors]


def only(errors, code):
    return [e for e in errors if e["code"] == code]


def other_feature_errors(errors):
    return [e for e in errors if e["code"] in OTHER_CODES]


def fix_run(payload_fixes, written, targets, **kw):
    """A stage-2 planner result and its dispatch. The workflow_patch is a
    placeholder: assertions below look only at the codes this task owns and
    at `write_policy`."""
    result = make_result(stage2_payload(payload_fixes), written=written, patch={"operation": "x"})
    return validate(result, make_envelope(targets, **kw))


def make_phase_state(**extra):
    data = {
        "schema_version": 1,
        "feature": OWN,
        "phase": "create-plan",
        "status": "completed",
        "generation": 1,
    }
    data.update(extra)
    return data


def record_item(path=DOC_A, **over):
    item = {"path": path, "change": "added a section", "reason": "needed", "produced_by": "create-plan-run-0001"}
    item.update(over)
    return item


# ---------------------------------------------------------------------------
# AC-1: the scope predicate
# ---------------------------------------------------------------------------

class TestScopePredicate(unittest.TestCase):
    def in_scope(self, path, own=OWN):
        return VWO.other_feature_doc_in_scope(path, own)

    def test_accepts_a_markdown_document_of_another_feature(self):
        for path in (
            "feature-docs/call-end-history/THREAT-MODEL.md",
            "feature-docs/other/sub/NOTE.md",
        ):
            with self.subTest(path=path):
                self.assertTrue(self.in_scope(path))

    def test_rejects_each_out_of_scope_form(self):
        for path in (
            "feature-docs/self/SPEC.md",
            "feature-docs/LESSONS.md",
            "feature-docs/other/workflow.yaml",
            "feature-docs/other/phase-state/x.md",
            "feature-docs/other/tasks/task0001.md",
            "feature-docs/other/design/mockups/a.md",
            "feature-docs/other/notes.txt",
            "/feature-docs/other/A.md",
            "/abs/feature-docs/other/A.md",
            "feature-docs/other/../self/SPEC.md",
            "feature-docs/../other/A.md",
            "feature-docs/other/A\x00.md",
        ):
            with self.subTest(path=path):
                self.assertFalse(self.in_scope(path))

    def test_rejects_a_path_outside_feature_docs_or_in_the_wrong_case(self):
        for path in (
            "src/feature-docs/other/A.md",
            "feature-docs-archive/other/A.md",
            "Feature-Docs/other/A.md",
            "feature-docs/other/A.MD",
            "feature-docs/other/A.md.txt",
            "other/A.md",
            "",
        ):
            with self.subTest(path=path):
                self.assertFalse(self.in_scope(path))

    def test_rejects_a_non_string(self):
        for value in (None, 5, 1.5, True, [], ["feature-docs/other/A.md"], {}, b"feature-docs/other/A.md"):
            with self.subTest(value=value):
                self.assertFalse(self.in_scope(value))

    def test_judges_the_normalized_segments(self):
        self.assertTrue(self.in_scope("./feature-docs/other/A.md"))
        self.assertTrue(self.in_scope("feature-docs\\other\\A.md"))
        self.assertTrue(self.in_scope("feature-docs//other/./A.md"))
        self.assertFalse(self.in_scope("./feature-docs/self/A.md"))
        self.assertFalse(self.in_scope("feature-docs\\self\\A.md"))
        self.assertFalse(self.in_scope("feature-docs\\other\\phase-state\\x.md"))
        self.assertFalse(self.in_scope("./feature-docs/other/tasks/t.md"))

    def test_the_excluded_directories_are_compared_by_segments(self):
        self.assertTrue(self.in_scope("feature-docs/other/tasks-notes/A.md"))
        self.assertTrue(self.in_scope("feature-docs/other/phase-state.md"))
        self.assertTrue(self.in_scope("feature-docs/other/design/mockups-evil/a.md"))
        self.assertTrue(self.in_scope("feature-docs/other/design/mockups.md"))
        self.assertTrue(self.in_scope("feature-docs/other/design/DESIGN.md"))

    def test_the_own_feature_is_compared_by_segment(self):
        self.assertTrue(self.in_scope("feature-docs/self-2/SPEC.md"))
        self.assertTrue(self.in_scope("feature-docs/elf/SPEC.md"))
        self.assertFalse(self.in_scope("feature-docs/self/sub/A.md"))

    def test_without_an_own_feature_only_the_other_conditions_apply(self):
        for own in (None, "", 5, ["self"]):
            with self.subTest(own=own):
                self.assertTrue(self.in_scope("feature-docs/self/SPEC.md", own))
                self.assertFalse(self.in_scope("feature-docs/LESSONS.md", own))
                self.assertFalse(self.in_scope("feature-docs/other/tasks/t.md", own))

    def test_a_request_a_fix_and_a_target_each_yield_one_scope_error_naming_the_path(self):
        bad = "feature-docs/self/SPEC.md"

        request = validate(make_result(request_payload(request_item(bad))), make_envelope())
        self.assertEqual(len(only(request, SCOPE)), 1, request)
        self.assertIn(bad, only(request, SCOPE)[0]["message"])

        fix = fix_run([fix_item(bad)], [bad], [amend_target(bad)])
        # the target and the fix each name the rejected path once
        self.assertEqual(len(only(fix, SCOPE)), 2, fix)
        for error in only(fix, SCOPE):
            self.assertIn(bad, error["message"])

        target = validate(make_result(request_payload(request_item(DOC_A))), make_envelope([amend_target(bad)]))
        self.assertEqual(len(only(target, SCOPE)), 1, target)
        self.assertIn(bad, only(target, SCOPE)[0]["message"])

    def test_the_own_feature_comes_from_the_workflow_when_the_envelope_has_none(self):
        bad = "feature-docs/self/SPEC.md"
        result = make_result(request_payload(request_item(bad)))
        with_workflow = validate(result, make_envelope(feature=None), workflow={"feature": OWN})
        self.assertEqual(len(only(with_workflow, SCOPE)), 1, with_workflow)
        without_any = validate(result, make_envelope(feature=None))
        self.assertEqual(only(without_any, SCOPE), [])

    def test_the_envelope_feature_wins_over_the_workflow_feature(self):
        result = make_result(request_payload(request_item("feature-docs/self/SPEC.md")))
        errors = validate(result, make_envelope(feature="elsewhere"), workflow={"feature": OWN})
        self.assertEqual(only(errors, SCOPE), [])


# ---------------------------------------------------------------------------
# AC-2: admission of the amend_other_feature action
# ---------------------------------------------------------------------------

class TestActionAdmission(unittest.TestCase):
    def check(self, target, worker="implementation-planner", **env):
        result = make_result(stage2_payload(), patch={"operation": "x"}, worker=worker)
        return validate(result, make_envelope([target], **env), worker=worker)

    def test_the_action_is_in_the_write_policy_vocabulary(self):
        self.assertIn("amend_other_feature", VWO.WRITE_POLICY_ACTIONS)

    def test_accepted_on_a_planner_create_plan_dispatch(self):
        errors = self.check(amend_target(DOC_A))
        self.assertEqual(other_feature_errors(errors), [], errors)
        self.assertEqual(only(errors, "write_policy"), [], errors)

    def test_another_worker_is_rejected(self):
        for worker in ("spec-writer", "rework-planner", "designer", "requirements-analyst"):
            with self.subTest(worker=worker):
                errors = self.check(amend_target(DOC_A), worker=worker)
                self.assertEqual(len(only(errors, SCOPE)), 1, errors)

    def test_another_phase_is_rejected(self):
        for phase in ("rework", "design", "create-spec", "review", "verify", None, 5):
            with self.subTest(phase=phase):
                envelope = make_envelope([amend_target(DOC_A)], phase=phase)
                if phase is None:
                    del envelope["phase"]
                errors = validate(make_result(stage2_payload(), patch={"operation": "x"}), envelope)
                self.assertEqual(len(only(errors, SCOPE)), 1, errors)

    def test_a_null_or_unusable_expect_digest_is_rejected(self):
        for digest in (None, "", 5, ["sha256:x"], {}):
            with self.subTest(digest=digest):
                errors = self.check(amend_target(DOC_A, digest=digest))
                self.assertEqual(len(only(errors, SCOPE)), 1, errors)
        target = {"path": DOC_A, "action": "amend_other_feature"}
        self.assertEqual(len(only(self.check(target), SCOPE)), 1)

    def test_an_out_of_scope_path_is_rejected_naming_the_path(self):
        for path in ("feature-docs/self/SPEC.md", "feature-docs/LESSONS.md", "feature-docs/o/workflow.yaml"):
            with self.subTest(path=path):
                errors = self.check(amend_target(path))
                self.assertEqual(len(only(errors, SCOPE)), 1, errors)
                self.assertIn(path, only(errors, SCOPE)[0]["message"])

    def test_a_target_of_another_action_is_checked_as_today(self):
        # the scope rule does not apply to the other actions
        target = {"path": "feature-docs/self/SPEC.md", "action": "replace_own", "expect_digest": None}
        errors = self.check(target)
        self.assertEqual(other_feature_errors(errors), [], errors)
        self.assertEqual(only(errors, "write_policy"), [], errors)

    def test_an_unknown_action_is_still_rejected(self):
        for action in ("amend_other_feature_x", "amend", "delete", None, 5, ["amend_other_feature"]):
            with self.subTest(action=action):
                target = {"path": DOC_A, "action": action, "expect_digest": DIGEST}
                errors = self.check(target)
                self.assertEqual(len(only(errors, "write_policy")), 1, errors)
                self.assertEqual(other_feature_errors(errors), [], errors)

    def test_a_written_grant_passes_the_coverage_check(self):
        result = make_result(stage2_payload([fix_item(DOC_A)]), written=[DOC_A], patch={"operation": "x"})
        errors = validate(result, make_envelope([amend_target(DOC_A)]))
        self.assertEqual(only(errors, "write_policy"), [], errors)

    def test_an_unlisted_written_path_is_still_a_write_policy_error(self):
        result = make_result(stage2_payload(), written=[DOC_B], patch={"operation": "x"})
        errors = validate(result, make_envelope([amend_target(DOC_A)]))
        self.assertEqual(len(only(errors, "write_policy")), 1, errors)


# ---------------------------------------------------------------------------
# AC-3: the stage-1 request result
# ---------------------------------------------------------------------------

class TestRequestResult(unittest.TestCase):
    def request(self, payload, envelope=None, **kw):
        return validate(make_result(payload, **kw), envelope or make_envelope())

    def test_a_request_result_passes_on_a_dispatch_without_grants(self):
        errors = self.request(request_payload(request_item(DOC_A), request_item(DOC_B)))
        self.assertEqual(errors, [])

    def test_a_request_result_passes_when_other_targets_are_not_grants(self):
        envelope = make_envelope([{"path": "feature-docs/self/IMPLEMENTATION.md", "action": "replace_own",
                                   "expect_digest": None}])
        self.assertEqual(self.request(request_payload(request_item(DOC_A)), envelope), [])

    def test_grants_on_the_dispatch_make_it_a_request_error(self):
        envelope = make_envelope([amend_target(DOC_A)])
        errors = self.request(request_payload(request_item(DOC_B)), envelope)
        self.assertEqual(len(only(errors, REQUEST)), 1, errors)

    def test_task_index_next_to_the_requests_is_a_request_error(self):
        payload = request_payload(request_item(DOC_A))
        payload["task_index"] = {}
        errors = self.request(payload)
        self.assertEqual(len(only(errors, REQUEST)), 1, errors)
        self.assertIn("task_index", only(errors, REQUEST)[0]["message"])
        # the ordinary payload rules are not applied on top of it
        self.assertEqual(only(errors, "payload-missing"), [], errors)

    def test_an_item_without_a_reason_is_a_request_error(self):
        errors = self.request(request_payload({"path": DOC_A}))
        self.assertGreaterEqual(len(only(errors, REQUEST)), 1, errors)

    def test_an_empty_reason_or_path_is_a_request_error(self):
        for item in (request_item(DOC_A, reason=""), request_item(DOC_A, reason="  "),
                     {"path": "", "reason": "r"}, {"path": "  ", "reason": "r"}):
            with self.subTest(item=item):
                errors = self.request(request_payload(item))
                self.assertGreaterEqual(len(only(errors, REQUEST)), 1, errors)

    def test_a_repeated_path_is_a_request_error(self):
        errors = self.request(request_payload(request_item(DOC_A), request_item(DOC_A, "again")))
        self.assertEqual(len(only(errors, REQUEST)), 1, errors)
        errors = self.request(request_payload(request_item(DOC_A), request_item("./" + DOC_A)))
        self.assertEqual(len(only(errors, REQUEST)), 1, errors)

    def test_an_unknown_item_key_is_a_request_error(self):
        item = request_item(DOC_A)
        item["change"] = "x"
        errors = self.request(request_payload(item))
        self.assertGreaterEqual(len(only(errors, REQUEST)), 1, errors)

    def test_an_empty_request_list_is_a_request_error(self):
        errors = self.request({"other_feature_doc_requests": []})
        self.assertEqual(len(only(errors, REQUEST)), 1, errors)

    def test_written_artifacts_or_a_patch_on_a_request_are_request_errors(self):
        errors = self.request(request_payload(request_item(DOC_A)), written=[DOC_A])
        self.assertGreaterEqual(len(only(errors, REQUEST)), 1, errors)
        errors = self.request(request_payload(request_item(DOC_A)), patch={"operation": "x"})
        self.assertGreaterEqual(len(only(errors, REQUEST)), 1, errors)

    def test_an_out_of_scope_requested_path_is_a_scope_error_only(self):
        errors = self.request(request_payload(request_item("feature-docs/LESSONS.md")))
        self.assertEqual(len(only(errors, SCOPE)), 1, errors)
        self.assertEqual(only(errors, REQUEST), [], errors)

    def test_each_out_of_scope_requested_path_is_reported_once(self):
        errors = self.request(request_payload(
            request_item("feature-docs/self/SPEC.md"),
            request_item("feature-docs/x/workflow.yaml"),
            request_item(DOC_A),
        ))
        self.assertEqual(len(only(errors, SCOPE)), 2, errors)

    def test_only_the_implementation_planner_has_the_request_alternative(self):
        result = make_result(request_payload(request_item(DOC_A)), worker="rework-planner")
        errors = VWO.validate_worker_result(result, "rework-planner", envelope=make_envelope())
        self.assertIn("workflow_patch", codes(errors))
        self.assertEqual(only(errors, REQUEST), [], errors)

    def test_the_request_shape_does_not_weaken_the_ordinary_planner_result(self):
        # no requests: a completed result still needs workflow_patch and task_index
        errors = self.request({"unrelated": 1})
        self.assertIn("workflow_patch", codes(errors))
        self.assertIn("payload-missing", codes(errors))
        self.assertEqual(other_feature_errors(errors), [], errors)

    def test_a_blocked_planner_result_is_not_a_request(self):
        result = make_result({}, status="blocked")
        result["blocking_reason"] = "needs feature-docs/other/A.md which is out of scope"
        errors = validate(result, make_envelope())
        self.assertEqual(other_feature_errors(errors), [], errors)


# ---------------------------------------------------------------------------
# AC-4: the fix declaration (stage 2)
# ---------------------------------------------------------------------------

class TestFixDeclaration(unittest.TestCase):
    TARGETS = [amend_target(DOC_A), amend_target(DOC_B)]

    def test_writing_a_grant_and_declaring_its_fix_passes(self):
        errors = fix_run([fix_item(DOC_A)], [DOC_A], self.TARGETS)
        self.assertEqual(other_feature_errors(errors), [], errors)
        self.assertEqual(only(errors, "write_policy"), [], errors)

    def test_writing_both_grants_and_declaring_both_passes(self):
        errors = fix_run([fix_item(DOC_A), fix_item(DOC_B)], [DOC_A, DOC_B], self.TARGETS)
        self.assertEqual(other_feature_errors(errors), [], errors)

    def test_a_granted_target_left_unchanged_is_neither_declared_nor_reported(self):
        self.assertEqual(other_feature_errors(fix_run(None, [], self.TARGETS)), [])
        self.assertEqual(other_feature_errors(fix_run([], [], self.TARGETS)), [])

    def test_writing_a_grant_without_a_fix_fails(self):
        for fixes in (None, [], [fix_item(DOC_B)]):
            with self.subTest(fixes=fixes):
                written = [DOC_A, DOC_B] if fixes else [DOC_A]
                errors = fix_run(fixes, written, self.TARGETS)
                fix_errors = only(errors, FIX)
                self.assertGreaterEqual(len(fix_errors), 1, errors)
                self.assertTrue(any(DOC_A in e["message"] for e in fix_errors), fix_errors)

    def test_declaring_a_grant_that_was_not_written_fails(self):
        errors = fix_run([fix_item(DOC_A), fix_item(DOC_B)], [DOC_A], self.TARGETS)
        fix_errors = only(errors, FIX)
        self.assertEqual(len(fix_errors), 1, errors)
        self.assertIn(DOC_B, fix_errors[0]["message"])

    def test_declaring_a_path_that_is_not_granted_fails(self):
        errors = fix_run([fix_item(DOC_A), fix_item(DOC_C)], [DOC_A], self.TARGETS)
        fix_errors = only(errors, FIX)
        self.assertEqual(len(fix_errors), 1, errors)
        self.assertIn(DOC_C, fix_errors[0]["message"])

    def test_declaring_fixes_on_a_dispatch_without_grants_fails(self):
        errors = fix_run([fix_item(DOC_A)], [], [])
        self.assertGreaterEqual(len(only(errors, FIX)), 1, errors)
        errors = fix_run([fix_item(DOC_A)], [], [{"path": "feature-docs/self/IMPLEMENTATION.md",
                                                   "action": "replace_own", "expect_digest": None}])
        self.assertGreaterEqual(len(only(errors, FIX)), 1, errors)

    def test_a_dispatch_without_grants_and_without_fixes_has_no_fix_error(self):
        self.assertEqual(only(fix_run(None, [], []), FIX), [])
        self.assertEqual(only(fix_run([], [], []), FIX), [])

    def test_a_duplicate_path_fails(self):
        errors = fix_run([fix_item(DOC_A), fix_item(DOC_A, change="again")], [DOC_A], self.TARGETS)
        fix_errors = only(errors, FIX)
        self.assertEqual(len(fix_errors), 1, errors)
        self.assertIn(DOC_A, fix_errors[0]["message"])

    def test_each_field_must_be_a_non_empty_string(self):
        for field in ("path", "change", "reason"):
            for value in ("", "   ", None, 5, ["x"], {}):
                with self.subTest(field=field, value=value):
                    item = fix_item(DOC_A)
                    item[field] = value
                    errors = fix_run([item], [DOC_A], self.TARGETS)
                    self.assertGreaterEqual(len(only(errors, FIX)), 1, errors)
            with self.subTest(field=field, value="<absent>"):
                item = fix_item(DOC_A)
                del item[field]
                errors = fix_run([item], [DOC_A], self.TARGETS)
                self.assertGreaterEqual(len(only(errors, FIX)), 1, errors)

    def test_an_unknown_item_key_fails(self):
        item = fix_item(DOC_A)
        item["produced_by"] = "create-plan-run-0001"
        errors = fix_run([item], [DOC_A], self.TARGETS)
        self.assertGreaterEqual(len(only(errors, FIX)), 1, errors)

    def test_the_fix_check_is_not_applied_to_a_result_that_is_not_completed(self):
        result = make_result({}, status="blocked", written=[DOC_A])
        result["blocking_reason"] = "needs feature-docs/other-c/NOTE.md"
        errors = validate(result, make_envelope(self.TARGETS))
        self.assertEqual(only(errors, FIX), [], errors)

    def test_the_fix_check_applies_to_every_worker(self):
        result = make_result({"other_feature_doc_fixes": [fix_item(DOC_A)]}, worker="spec-writer")
        errors = VWO.validate_worker_result(result, "spec-writer", envelope=make_envelope())
        self.assertGreaterEqual(len(only(errors, FIX)), 1, errors)

    def test_an_absent_envelope_means_no_grants(self):
        result = make_result(stage2_payload([fix_item(DOC_A)]), patch={"operation": "x"})
        errors = VWO.validate_worker_result(result, "implementation-planner")
        self.assertGreaterEqual(len(only(errors, FIX)), 1, errors)


# ---------------------------------------------------------------------------
# AC-5: the phase-state record
# ---------------------------------------------------------------------------

class TestPhaseStateRecord(unittest.TestCase):
    def test_a_phase_state_without_the_key_passes(self):
        self.assertEqual(VWO.validate_phase_state(make_phase_state()), [])

    def test_a_well_formed_list_passes(self):
        data = make_phase_state(other_feature_doc_fixes=[record_item(DOC_A), record_item(DOC_B)])
        self.assertEqual(VWO.validate_phase_state(data), [])

    def test_an_empty_list_passes(self):
        self.assertEqual(VWO.validate_phase_state(make_phase_state(other_feature_doc_fixes=[])), [])

    def test_unknown_top_level_keys_stay_tolerated(self):
        data = make_phase_state(some_future_key={"a": 1}, other_feature_doc_fixes=[record_item()])
        self.assertEqual(VWO.validate_phase_state(data), [])

    def test_a_non_list_value_is_a_fix_error(self):
        for value in ("text", {"path": DOC_A}, 5, None, True):
            with self.subTest(value=value):
                errors = VWO.validate_phase_state(make_phase_state(other_feature_doc_fixes=value))
                self.assertEqual(codes(errors), [FIX], errors)

    def test_a_non_mapping_item_is_a_fix_error(self):
        for item in ("text", 5, None, [DOC_A], [record_item()]):
            with self.subTest(item=item):
                errors = VWO.validate_phase_state(make_phase_state(other_feature_doc_fixes=[item]))
                self.assertEqual(codes(errors), [FIX], errors)

    def test_an_item_missing_produced_by_is_a_fix_error(self):
        item = record_item()
        del item["produced_by"]
        errors = VWO.validate_phase_state(make_phase_state(other_feature_doc_fixes=[item]))
        self.assertEqual(codes(errors), [FIX], errors)
        self.assertIn("produced_by", errors[0]["message"])

    def test_each_field_must_be_a_non_empty_string(self):
        for field in ("path", "change", "reason", "produced_by"):
            for value in ("", "  ", None, 5, ["x"]):
                with self.subTest(field=field, value=value):
                    item = record_item(**{field: value})
                    errors = VWO.validate_phase_state(make_phase_state(other_feature_doc_fixes=[item]))
                    self.assertTrue(errors and set(codes(errors)) == {FIX}, errors)

    def test_the_path_must_pass_the_safe_relative_check(self):
        for path in ("/abs/feature-docs/o/A.md", "feature-docs/../x.md", "feature-docs/o/A\x00.md"):
            with self.subTest(path=path):
                item = record_item(path)
                errors = VWO.validate_phase_state(make_phase_state(other_feature_doc_fixes=[item]))
                self.assertEqual(codes(errors), [FIX], errors)

    def test_every_bad_item_is_reported(self):
        items = [record_item(DOC_A), "text", record_item(DOC_B, reason=""), record_item(DOC_C)]
        errors = VWO.validate_phase_state(make_phase_state(other_feature_doc_fixes=items))
        self.assertEqual(codes(errors), [FIX, FIX], errors)

    def test_the_record_is_read_only_for_a_create_plan_phase_state(self):
        data = make_phase_state(phase="design", other_feature_doc_fixes="whatever")
        self.assertEqual(VWO.validate_phase_state(data), [])


# ---------------------------------------------------------------------------
# AC-6: malformed input is reported, never raised
# ---------------------------------------------------------------------------

GARBAGE = (None, 5, 1.5, True, "text", [], {}, ["a"], [[]], [None], {"path": 1})


class TestMalformedInput(unittest.TestCase):
    def test_a_non_list_request_value_is_a_request_error(self):
        for value in (None, 5, "text", {"path": DOC_A, "reason": "r"}, True):
            with self.subTest(value=value):
                errors = validate(make_result({"other_feature_doc_requests": value}), make_envelope())
                self.assertGreaterEqual(len(only(errors, REQUEST)), 1, errors)

    def test_a_non_mapping_request_item_is_a_request_error(self):
        for item in (None, 5, "text", [DOC_A], True):
            with self.subTest(item=item):
                errors = validate(make_result(request_payload(item)), make_envelope())
                self.assertGreaterEqual(len(only(errors, REQUEST)), 1, errors)

    def test_non_string_request_fields_are_request_errors(self):
        for path, reason in ((5, "r"), (None, "r"), (["x"], "r"), (DOC_A, 5), (DOC_A, None), (DOC_A, ["r"])):
            with self.subTest(path=path, reason=reason):
                errors = validate(make_result(request_payload({"path": path, "reason": reason})), make_envelope())
                self.assertGreaterEqual(len(only(errors, REQUEST)), 1, errors)

    def test_a_non_list_fix_value_is_a_fix_error(self):
        for value in (None, 5, "text", {"path": DOC_A}, True):
            with self.subTest(value=value):
                errors = fix_run(value, [DOC_A], [amend_target(DOC_A)])
                self.assertGreaterEqual(len(only(errors, FIX)), 1, errors)

    def test_a_non_mapping_fix_item_is_a_fix_error(self):
        for item in (None, 5, "text", [DOC_A], True):
            with self.subTest(item=item):
                errors = fix_run([item], [DOC_A], [amend_target(DOC_A)])
                self.assertGreaterEqual(len(only(errors, FIX)), 1, errors)

    def test_non_string_fix_fields_are_fix_errors(self):
        for field in ("path", "change", "reason"):
            for value in (5, None, ["x"], {"a": 1}):
                with self.subTest(field=field, value=value):
                    item = fix_item(DOC_A)
                    item[field] = value
                    errors = fix_run([item], [DOC_A], [amend_target(DOC_A)])
                    self.assertGreaterEqual(len(only(errors, FIX)), 1, errors)

    def test_malformed_targets_are_reported_and_do_not_raise(self):
        for targets in (GARBAGE + (["a", None],)):
            with self.subTest(targets=targets):
                envelope = make_envelope()
                envelope["write_policy"] = {"targets": targets}
                errors = validate(make_result(request_payload(request_item(DOC_A))), envelope)
                self.assertIsInstance(errors, list)
                if targets != []:
                    self.assertGreaterEqual(len(only(errors, "write_policy")), 1, errors)

    def test_a_non_mapping_target_item_is_an_error(self):
        for item in (None, 5, "text", ["path"], True):
            with self.subTest(item=item):
                envelope = make_envelope()
                envelope["write_policy"] = {"targets": [item]}
                errors = validate(make_result(stage2_payload(), patch={"operation": "x"}), envelope)
                self.assertGreaterEqual(len(only(errors, "write_policy")), 1, errors)

    def test_non_string_target_fields_are_errors(self):
        for target in (
            {"path": 5, "action": "amend_other_feature", "expect_digest": DIGEST},
            {"path": None, "action": "amend_other_feature", "expect_digest": DIGEST},
            {"path": ["a"], "action": "amend_other_feature", "expect_digest": DIGEST},
            {"path": DOC_A, "action": "amend_other_feature", "expect_digest": 5},
            {"path": DOC_A, "action": ["amend_other_feature"], "expect_digest": DIGEST},
            {"path": ["a"], "action": "replace_own", "expect_digest": None},
            {"path": ["a"], "action": "regenerate", "source": ["b"]},
            {"path": DOC_A, "action": "regenerate", "source": ["b"]},
        ):
            with self.subTest(target=target):
                envelope = make_envelope([target])
                errors = validate(make_result(stage2_payload(), written=[DOC_A], patch={"operation": "x"}), envelope)
                self.assertTrue(errors, errors)

    def test_an_amend_target_with_a_non_string_path_is_a_scope_error(self):
        for path in (5, None, ["a"], {"a": 1}):
            with self.subTest(path=path):
                errors = validate(
                    make_result(stage2_payload(), patch={"operation": "x"}),
                    make_envelope([{"path": path, "action": "amend_other_feature", "expect_digest": DIGEST}]),
                )
                self.assertEqual(len(only(errors, SCOPE)), 1, errors)

    def test_a_malformed_write_policy_does_not_raise(self):
        for write_policy in (5, "text", ["targets"], {"targets": None}, {"targets": 5}, {"targets": "x"}):
            with self.subTest(write_policy=write_policy):
                envelope = make_envelope()
                envelope["write_policy"] = write_policy
                errors = validate(make_result(request_payload(request_item(DOC_A))), envelope)
                self.assertGreaterEqual(len(only(errors, "write_policy")), 1, errors)

    def test_a_non_mapping_payload_does_not_raise(self):
        for payload in ("text", [1], 5):
            with self.subTest(payload=payload):
                errors = validate(make_result(payload), make_envelope())
                self.assertIn("payload", codes(errors))

    def test_a_non_mapping_workflow_does_not_raise(self):
        for workflow in ("text", [1], 5):
            with self.subTest(workflow=workflow):
                result = make_result(request_payload(request_item(DOC_A)))
                self.assertEqual(validate(result, make_envelope(feature=None), workflow=workflow), [])

    def test_a_non_string_envelope_feature_is_judged_against_no_feature(self):
        for feature in (5, ["self"], {"a": 1}):
            with self.subTest(feature=feature):
                result = make_result(request_payload(request_item("feature-docs/self/SPEC.md")))
                self.assertEqual(only(validate(result, make_envelope(feature=feature)), SCOPE), [])

    def test_non_string_written_artifact_paths_do_not_raise(self):
        for written in ([5], [None], [["x"]], 5, "text"):
            with self.subTest(written=written):
                result = make_result(stage2_payload([fix_item(DOC_A)]), patch={"operation": "x"})
                result["written_artifacts"] = written
                errors = validate(result, make_envelope([amend_target(DOC_A)]))
                self.assertIsInstance(errors, list)

    def test_every_garbage_value_in_every_slot_is_reported_without_raising(self):
        slots = {
            "other_feature_doc_requests": request_payload,
            "other_feature_doc_fixes": lambda *items: stage2_payload(list(items)),
        }
        for key, build in slots.items():
            for value in GARBAGE:
                with self.subTest(slot=key, value=value):
                    payload = {key: value}
                    result = make_result(payload, patch={"operation": "x"})
                    errors = validate(result, make_envelope([amend_target(DOC_A)]))
                    self.assertIsInstance(errors, list)
                with self.subTest(slot=key + "[item]", value=value):
                    errors = validate(make_result(build(value), patch={"operation": "x"}),
                                      make_envelope([amend_target(DOC_A)]))
                    self.assertIsInstance(errors, list)

    def test_every_garbage_record_is_reported_without_raising(self):
        for value in GARBAGE:
            with self.subTest(value=value):
                errors = VWO.validate_phase_state(make_phase_state(other_feature_doc_fixes=value))
                self.assertIsInstance(errors, list)
                errors = VWO.validate_phase_state(make_phase_state(other_feature_doc_fixes=[value]))
                self.assertGreaterEqual(len(only(errors, FIX)), 1, errors)


# ---------------------------------------------------------------------------
# The command-line wiring
# ---------------------------------------------------------------------------

class TestCommandLine(unittest.TestCase):
    def run_validator(self, kind, data, envelope=None):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            input_path = tmp / "input.json"
            input_path.write_text(json.dumps(data), encoding="utf-8")
            args = [sys.executable, str(SCRIPT_PATH), "--kind", kind,
                    "--worker", "implementation-planner", "--input", str(input_path)]
            if envelope is not None:
                envelope_path = tmp / "envelope.json"
                envelope_path.write_text(json.dumps(envelope), encoding="utf-8")
                args += ["--input-envelope", str(envelope_path)]
            return subprocess.run(args, capture_output=True, text=True)

    def test_a_request_result_on_a_dispatch_without_grants_exits_0(self):
        result = self.run_validator(
            "worker-result", make_result(request_payload(request_item(DOC_A))), make_envelope())
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_a_request_result_on_a_dispatch_with_grants_exits_1_with_the_request_code(self):
        result = self.run_validator(
            "worker-result", make_result(request_payload(request_item(DOC_B))),
            make_envelope([amend_target(DOC_A)]))
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(REQUEST, codes(json.loads(result.stdout)["errors"]))

    def test_a_request_for_an_out_of_scope_path_exits_1_with_the_scope_code(self):
        result = self.run_validator(
            "worker-result", make_result(request_payload(request_item("feature-docs/LESSONS.md"))),
            make_envelope())
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertEqual(codes(json.loads(result.stdout)["errors"]), [SCOPE])

    def test_a_grant_written_without_a_fix_exits_1_with_the_fix_code(self):
        result = self.run_validator(
            "worker-result", make_result(stage2_payload(), written=[DOC_A], patch={"operation": "x"}),
            make_envelope([amend_target(DOC_A)]))
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(FIX, codes(json.loads(result.stdout)["errors"]))

    def test_an_amend_target_on_the_wrong_phase_exits_1_with_the_scope_code(self):
        result = self.run_validator(
            "worker-result", make_result(stage2_payload(), patch={"operation": "x"}),
            make_envelope([amend_target(DOC_A)], phase="rework"))
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn(SCOPE, codes(json.loads(result.stdout)["errors"]))

    def test_a_phase_state_record_is_checked_through_the_command_line(self):
        good = self.run_validator("phase-state", make_phase_state(other_feature_doc_fixes=[record_item()]))
        self.assertEqual(good.returncode, 0, good.stdout + good.stderr)
        item = record_item()
        del item["produced_by"]
        bad = self.run_validator("phase-state", make_phase_state(other_feature_doc_fixes=[item]))
        self.assertEqual(bad.returncode, 1, bad.stdout + bad.stderr)
        self.assertEqual(codes(json.loads(bad.stdout)["errors"]), [FIX])


# ---------------------------------------------------------------------------
# AC-7: the byte-pin refresh comment
# ---------------------------------------------------------------------------

class TestBytePinRefreshComment(unittest.TestCase):
    MARKER = "Refreshed again by plan-feature-docs-route/task0005"

    def test_the_validator_pin_carries_a_refresh_comment_naming_this_task(self):
        text = GATE_VOCAB_TEST_PATH.read_text(encoding="utf-8")
        self.assertIn(self.MARKER, text)
        start = text.index(self.MARKER)
        end = text.index("VALIDATE_WORKER_OUTPUT_SHA256 = (", start)
        comment = re.sub(r"\s+", " ", re.sub(r"^\s*#", " ", text[start:end], flags=re.MULTILINE))
        self.assertIn("amend_other_feature", comment)
        self.assertIn("other-feature-doc", comment)

    def test_the_pin_assignment_still_exists(self):
        text = GATE_VOCAB_TEST_PATH.read_text(encoding="utf-8")
        self.assertRegex(text, r"VALIDATE_WORKER_OUTPUT_SHA256 = \(\s*\"[0-9a-f]{64}\"\s*\)")


if __name__ == "__main__":
    unittest.main()
