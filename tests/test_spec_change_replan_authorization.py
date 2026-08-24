"""Tests for task0022 (goal-vs-spec-divergence, review round 3, finding
consumed-flag-split; feature-docs/goal-vs-spec-divergence/tasks/
task0022.md): the `spec_change` record carries two independent flags --
`consumed` (stop-condition-3 suppression) and `replan_authorized` (the
re-planning `replace_all` authorization) -- instead of one flag serving
both judgements.

Why this task exists: the re-planning path's real ordering is (1) the
SPEC-change transition writes the record (authorized, unconsumed), (2) the
state machine re-enters `create-spec`, which marks the record `consumed`
at that dispatch, (3) `create-spec` finishes, (4) `create-plan` reads
`pending` with `merged` tasks present and receives a re-planning
`replace_all`. Step 4 always finds the record already `consumed`, so a
single `consumed`-keyed re-entry check always falls back to the
Initial-planning rule and always rejects -- FR6 never held in the flow it
was written for. This module pins the fix (a second, independent flag)
across every document and the validator that state or implement it, so a
future change to any one of them in isolation is caught here.

This is a cross-document module by design (Test Notes / task plan Files to
Create): task0022 owns `references/phase-state.md`, `references/
workflow-patch.md`, `skills/develop/SKILL.md` and `scripts/validate-
worker-output.py` together, so pinning the shared rule across all four in
one module (rather than duplicating it per-document) is in scope.

Acceptance Criteria covered:

- AC-1 (NFR1): TestPhaseStateDefinesBothFlagsInOnePlace -- phase-state.md
  defines both flags in one place (name, writer, judgement, spend point),
  states neither flag is read for the other's judgement, and the
  wholesale-replacement sentence covers both flags.
- AC-2 (FR6): TestWorkflowPatchReadsReplanAuthorizationNotConsumed --
  workflow-patch.md's Re-planning path second case reads
  `replan_authorized`, not `consumed`; mandatory-field list and
  fail-closed fallback updated together. (Direct per-sentence pins for
  workflow-patch.md's own test module additionally live in
  tests/test_workflow_patch_doc.py, which this task also owns.)
- AC-3 (FR4, FR6): TestValidatorReadsReplanAuthorizedNotConsumed -- the
  re-entry helper accepts `consumed: true` with an unspent authorization,
  and rejects a spent / absent / non-boolean authorization, each with its
  own direction.
- AC-4 (FR6): TestReentryOrdering -- the ordering test: record written
  (authorized, unconsumed) -> create-spec dispatched (consumed becomes
  true, performed by the test itself, never baked into the fixture) ->
  create-spec completes -> create-plan reads pending with merged tasks
  present -- and the re-planning replace_all validated at that point is
  accepted (no replace-all-not-permitted). Drives create-plan-phase.md's
  canonical `--kind workflow-patch --dry-run-apply` invocation form
  (the same shape TestCanonicalReentryInvocation in
  test_validate_worker_output.py already established), adding no new
  flag.
- AC-5 (NFR1): TestSkillDevelopStatesTwoConsumptionPointsSeparately --
  Step B's stop-condition-3 exclusion text states the two consumption
  points separately and does not imply one flag grounds both.

AC-6 (FR5, NFR8, fixture-group consistency) and AC-7 (full-suite pass,
byte-identity pin refresh) have no dedicated class here: AC-6 is proven by
the fixture-driven sweep in test_validate_worker_output.py
(TestFixtureCorpusDataDriven, TestReplanningMandatoryPreserveAndTaskId
Allocation) and AC-7 by running the whole suite / test_gate_option_
vocabulary.py, neither of which belongs in this module.
"""

import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"
PHASE_STATE_PATH = PLUGIN_ROOT / "references" / "phase-state.md"
WORKFLOW_PATCH_PATH = PLUGIN_ROOT / "references" / "workflow-patch.md"
DEVELOP_SKILL_PATH = PLUGIN_ROOT / "skills" / "develop" / "SKILL.md"
SCRIPT_PATH = PLUGIN_ROOT / "scripts" / "validate-worker-output.py"


def _read(path):
    return path.read_text(encoding="utf-8")


def _load_validator_module():
    spec = importlib.util.spec_from_file_location(
        "validate_worker_output_flagpair", SCRIPT_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VWO = _load_validator_module()


def run_cli(args):
    cmd = [sys.executable, str(SCRIPT_PATH)] + list(args)
    return subprocess.run(cmd, capture_output=True, text=True)


# ---------------------------------------------------------------------------
# AC-1
# ---------------------------------------------------------------------------


class TestPhaseStateDefinesBothFlagsInOnePlace(unittest.TestCase):
    """phase-state.md defines both flags -- name, writer, the judgement
    each grounds, the point at which each is spent -- in one place, and
    states neither flag is read for the other's judgement."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(PHASE_STATE_PATH)
        idx = cls.text.index("| `spec_change` |")
        end = cls.text.index("\n", idx)
        cls.row = cls.text[idx:end]

        schema_start = cls.text.index("## Schema")
        fence_end = cls.text.index("\n```\n", schema_start)
        schema_block = cls.text[schema_start:fence_end]
        spec_change_idx = schema_block.index("spec_change:")
        cls.schema_record = schema_block[spec_change_idx:]

    def test_both_flag_names_present_in_the_row(self):
        self.assertIn("`consumed`", self.row)
        self.assertIn("`replan_authorized`", self.row)

    def test_both_flags_present_in_the_schema_example(self):
        self.assertIn("consumed:", self.schema_record)
        self.assertIn("replan_authorized:", self.schema_record)

    def test_each_flags_writer_stated(self):
        self.assertIn("written `true` by the orchestrator", self.row)
        self.assertIn(
            "written `true` by rework's spec-change transition", self.row
        )

    def test_each_flags_judgement_and_spend_point_stated(self):
        self.assertIn("grounded one `create-spec` dispatch", self.row)
        self.assertIn(
            "set `false` once a re-planning `replace_all` has been applied",
            self.row,
        )

    def test_neither_flag_read_for_the_others_judgement(self):
        self.assertIn("never read as a re-planning permission", self.row)
        self.assertIn("never read as a stop-condition-3 suppressor", self.row)
        self.assertIn(
            "Neither flag is ever read for the other's judgement.", self.row
        )

    def test_wholesale_replacement_sentence_covers_both_flags(self):
        self.assertIn("replacing", self.row)
        self.assertIn("always unconsumed AND authorized", self.row)

    def test_no_other_document_restates_the_schema(self):
        # Non-vacuity paired with the negative proof below: workflow-
        # patch.md and SKILL.md may CITE the flags by name (they must, for
        # AC-2/AC-5) but must not restate the writer/spend-point schema
        # sentence itself.
        schema_sentence = "written `true` by rework's spec-change transition"
        for path in (WORKFLOW_PATCH_PATH, DEVELOP_SKILL_PATH):
            with self.subTest(path=path.name):
                self.assertNotIn(schema_sentence, _read(path))


class TestPhaseStateDefinesBothFlagsInOnePlaceNegativeProof(unittest.TestCase):
    """Non-vacuity: prove the assertions above can fail against a synthetic
    single-flag row (tdd-testing discipline)."""

    def test_single_flag_row_fails_the_both_names_check(self):
        synthetic_row = (
            "| `spec_change` | `reason`, `finding_stable_id`, "
            "`recorded_at_commit`, `consumed` -- ... |"
        )
        self.assertIn("`consumed`", synthetic_row)
        self.assertNotIn("`replan_authorized`", synthetic_row)

    def test_row_without_neither_flag_sentence_fails(self):
        synthetic_row = "| `spec_change` | `consumed`, `replan_authorized` -- two flags. |"
        self.assertNotIn(
            "Neither flag is ever read for the other's judgement.",
            synthetic_row,
        )


# ---------------------------------------------------------------------------
# AC-2
# ---------------------------------------------------------------------------


class TestWorkflowPatchReadsReplanAuthorizationNotConsumed(unittest.TestCase):
    """workflow-patch.md's Re-planning path second case reads the
    re-planning authorization flag, no longer makes `consumed`'s value
    part of the condition, and states its mandatory-field list and
    fail-closed fallback in the same edit."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(WORKFLOW_PATCH_PATH)
        start = cls.text.index("### `replace_all` permission conditions")
        end = cls.text.index("### `append` requirements", start)
        cls.section = cls.text[start:end]
        cls.normalized = re.sub(r"\s+", " ", cls.section)

    def test_unspent_authorization_phrase_present(self):
        self.assertIn(
            "carrying an **unspent re-planning authorization**",
            self.normalized,
        )

    def test_mandatory_field_list_names_replan_authorized_as_boolean(self):
        self.assertIn(
            "carries `replan_authorized` as a boolean", self.normalized
        )
        self.assertIn("`replan_authorized` is `true`", self.normalized)

    def test_consumed_explicitly_excluded_from_the_decision(self):
        self.assertIn(
            "`consumed`'s value plays no part in this decision",
            self.normalized,
        )

    def test_old_unconsumed_reading_absent(self):
        self.assertNotIn("**unconsumed** `spec_change` record", self.section)
        self.assertNotIn(
            '"Unconsumed" means the record carries', self.section
        )

    def test_fail_closed_fallback_retained(self):
        self.assertIn(
            "the invocation falls back to the Initial-planning path's rule",
            self.normalized,
        )
        self.assertIn(
            "a narrower invocation never widens what `replace_all` permits",
            self.normalized,
        )


# ---------------------------------------------------------------------------
# AC-3
# ---------------------------------------------------------------------------


class TestValidatorReadsReplanAuthorizedNotConsumed(unittest.TestCase):
    """workflow_replace_all_spec_change_reentry reads `replan_authorized`,
    never `consumed`, for the re-planning-authorization judgement -- each
    direction (unspent / spent / absent / non-boolean) proven, and
    `consumed`'s value proven irrelevant either way."""

    FEATURE = "example"

    def _workflow(self, base_commit="deadbeef"):
        return {
            "feature": self.FEATURE,
            "workflow": [
                {"id": "create-plan", "status": "pending"},
                {"id": "implement", "status": "pending", "base_commit": base_commit},
            ],
        }

    def _phase_state(self, **spec_change_overrides):
        spec_change = {
            "reason": "x",
            "finding_stable_id": "abc",
            "recorded_at_commit": "deadbeef",
            "consumed": True,
            "replan_authorized": True,
        }
        spec_change.update(spec_change_overrides)
        return {"phase": "rework", "feature": self.FEATURE, "spec_change": spec_change}

    def test_consumed_true_with_unspent_authorization_is_a_reentry(self):
        # This is exactly the state the real transition sequence always
        # produces by the time create-plan is reached (AC-4's ordering).
        phase_state = self._phase_state()
        self.assertTrue(
            VWO.workflow_replace_all_spec_change_reentry(self._workflow(), phase_state)
        )

    def test_consumed_false_with_unspent_authorization_is_also_a_reentry(self):
        # consumed's value must never change the outcome either way.
        phase_state = self._phase_state(consumed=False)
        self.assertTrue(
            VWO.workflow_replace_all_spec_change_reentry(self._workflow(), phase_state)
        )

    def test_spent_authorization_is_not_a_reentry(self):
        phase_state = self._phase_state(replan_authorized=False)
        self.assertFalse(
            VWO.workflow_replace_all_spec_change_reentry(self._workflow(), phase_state)
        )

    def test_absent_authorization_is_not_a_reentry(self):
        phase_state = self._phase_state()
        del phase_state["spec_change"]["replan_authorized"]
        self.assertFalse(
            VWO.workflow_replace_all_spec_change_reentry(self._workflow(), phase_state)
        )

    def test_non_boolean_authorization_is_not_a_reentry(self):
        for bad_value in ("true", 1, 0, None, []):
            with self.subTest(bad_value=bad_value):
                phase_state = self._phase_state(replan_authorized=bad_value)
                self.assertFalse(
                    VWO.workflow_replace_all_spec_change_reentry(
                        self._workflow(), phase_state
                    )
                )


# ---------------------------------------------------------------------------
# AC-4
# ---------------------------------------------------------------------------


class TestReentryOrdering(unittest.TestCase):
    """The point of this task: reproduce the transition's real sequence and
    assert acceptance despite `consumed: true`, driving the validator
    through create-plan-phase.md's canonical `--kind workflow-patch
    --dry-run-apply` invocation form (the same argument shape
    TestCanonicalReentryInvocation in test_validate_worker_output.py
    already established for this exact check), adding no new flag.

    Per the task's Test Notes: the intermediate `consumed` mark is
    performed by the test itself (a second write to rework.yaml), never
    baked into a fixture -- a fixture that starts pre-consumed would only
    prove the final-state case, not the ordering."""

    FEATURE = "example"

    def _workflow_obj(self):
        return {
            "feature": self.FEATURE,
            "project": {"license": "MIT"},
            "requirements": {
                "FR1": {"status": "ok", "tasks": [], "tests": [], "title": "x"}
            },
            "schema_version": 1,
            "tasks": {
                "task0009": {
                    "branch": "em-workflow/example/task0009",
                    "complexity": "low",
                    "domains": [],
                    "files": ["x.go"],
                    "notes": None,
                    "plan": "tasks/task0009.md",
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
                {"base_commit": "deadbeef", "id": "implement", "status": "pending"},
                {"id": "review", "status": "pending"},
                {"id": "verify", "status": "pending"},
                {"id": "retrospect", "status": "pending"},
            ],
        }

    def _patch_obj(self, base_input_digest):
        return {
            "base_input_digest": base_input_digest,
            "base_workflow_blob": "8f17c04",
            "operation": "replace_planning",
            "patch_id": "create-plan-p0001",
            "preserve": ["workflow.implement.base_commit"],
            "requirements_patch": None,
            "schema_version": 1,
            "step_patches": [],
            "tasks_patch": {
                "entries": {
                    "task0009": {
                        "complexity": "low",
                        "domains": [],
                        "files": ["x.go"],
                        "initial_status": "pending",
                        "plan": "tasks/task0009.md",
                        "requirements": ["FR1"],
                        "skills": [],
                        "title": "existing",
                    },
                },
                "mode": "replace_all",
            },
        }

    def _digest_source_obj(self):
        return {
            "answers_digest": "sha256:" + "2" * 64,
            "digest_inputs": {},
            "mode": "interactive",
            "value_inputs": {"task_description": None},
            "worker": "implementation-planner",
            "workflow_blob": "8f17c04",
            "write_policy_digest": "sha256:" + "3" * 64,
        }

    def _rework_yaml_text(self, *, consumed):
        return (
            "phase: rework\n"
            f"feature: {self.FEATURE}\n"
            "spec_change:\n"
            "  reason: SPEC changed after implementation to add a missed requirement\n"
            "  finding_stable_id: abc123\n"
            "  recorded_at_commit: deadbeef\n"
            f"  consumed: {'true' if consumed else 'false'}\n"
            "  replan_authorized: true\n"
        )

    def test_replace_all_accepted_after_create_spec_dispatch_consumed_the_record(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            feature_dir = tmp_path / "feature-dir"
            phase_state_dir = feature_dir / "phase-state"
            phase_state_dir.mkdir(parents=True)
            rework_yaml = phase_state_dir / "rework.yaml"

            # Step 1: the SPEC-change transition writes the record --
            # authorized, unconsumed.
            rework_yaml.write_text(
                self._rework_yaml_text(consumed=False), encoding="utf-8"
            )

            # Step 2: the state machine re-enters create-spec; the record
            # is marked consumed at that dispatch (skills/develop/SKILL.md
            # Step B's stop-condition-3 exclusion rule). Performed here by
            # the test itself -- never baked into the fixture.
            rework_yaml.write_text(
                self._rework_yaml_text(consumed=True), encoding="utf-8"
            )

            # Step 3: create-spec finishes (no further phase-state.md
            # write this test needs to model for the validator's own
            # decision -- outcome-independent per phase-state.md's
            # `consumed` row).

            # Step 4: create-plan reads `pending`, with a `merged` task
            # present -- workflow.json below, and the canonical
            # `--phase-state` argument points at create-plan's OWN state
            # file, never at rework.yaml directly.
            create_plan_yaml = tmp_path / "create-plan.yaml"
            create_plan_yaml.write_text(
                f"phase: create-plan\nfeature: {self.FEATURE}\n", encoding="utf-8"
            )

            digest_source = self._digest_source_obj()
            base_input_digest = VWO.normalize_json_sha256(digest_source)

            input_path = tmp_path / "input.json"
            workflow_path = tmp_path / "workflow.json"
            digest_source_path = tmp_path / "digest-source.json"
            input_path.write_text(
                json.dumps(self._patch_obj(base_input_digest)), encoding="utf-8"
            )
            workflow_path.write_text(
                json.dumps(self._workflow_obj()), encoding="utf-8"
            )
            digest_source_path.write_text(
                json.dumps(digest_source), encoding="utf-8"
            )

            result = run_cli(
                [
                    "--kind", "workflow-patch",
                    "--worker", "implementation-planner",
                    "--input", str(input_path),
                    "--workflow", str(workflow_path),
                    "--digest-source", str(digest_source_path),
                    "--feature-dir", str(feature_dir),
                    "--phase-state", str(create_plan_yaml),
                    "--dry-run-apply",
                ]
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_same_sequence_without_the_consumed_mark_is_also_accepted(self):
        # Non-vacuity companion: proves the acceptance above is not a
        # coincidence of some OTHER unrelated fixture detail -- the only
        # variable between this test and the one above is whether step 2
        # (the consumed mark) ran, and both must accept.
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            feature_dir = tmp_path / "feature-dir"
            phase_state_dir = feature_dir / "phase-state"
            phase_state_dir.mkdir(parents=True)
            (phase_state_dir / "rework.yaml").write_text(
                self._rework_yaml_text(consumed=False), encoding="utf-8"
            )

            create_plan_yaml = tmp_path / "create-plan.yaml"
            create_plan_yaml.write_text(
                f"phase: create-plan\nfeature: {self.FEATURE}\n", encoding="utf-8"
            )

            digest_source = self._digest_source_obj()
            base_input_digest = VWO.normalize_json_sha256(digest_source)

            input_path = tmp_path / "input.json"
            workflow_path = tmp_path / "workflow.json"
            digest_source_path = tmp_path / "digest-source.json"
            input_path.write_text(
                json.dumps(self._patch_obj(base_input_digest)), encoding="utf-8"
            )
            workflow_path.write_text(
                json.dumps(self._workflow_obj()), encoding="utf-8"
            )
            digest_source_path.write_text(
                json.dumps(digest_source), encoding="utf-8"
            )

            result = run_cli(
                [
                    "--kind", "workflow-patch",
                    "--worker", "implementation-planner",
                    "--input", str(input_path),
                    "--workflow", str(workflow_path),
                    "--digest-source", str(digest_source_path),
                    "--feature-dir", str(feature_dir),
                    "--phase-state", str(create_plan_yaml),
                    "--dry-run-apply",
                ]
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


# ---------------------------------------------------------------------------
# AC-5
# ---------------------------------------------------------------------------


class TestSkillDevelopStatesTwoConsumptionPointsSeparately(unittest.TestCase):
    """skills/develop/SKILL.md Step B states the two consumption points
    separately -- stop-condition 3's exclusion keyed on `consumed`, the
    re-planning authorization spent at re-planning patch application -- and
    no sentence there implies one flag grounds both."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(DEVELOP_SKILL_PATH)

    def test_consumed_spend_point_is_the_create_spec_dispatch(self):
        self.assertIn(
            "根拠に create-spec を 1 度 dispatch した時点で消費される",
            self.text,
        )

    def test_replan_authorized_named_as_a_separate_flag(self):
        self.assertIn("replan_authorized", self.text)

    def test_replan_authorized_spend_point_is_replanning_patch_application(self):
        self.assertIn(
            "消費されるのは再計画 `replace_all` パッチが適用された時点",
            self.text,
        )

    def test_replan_authorized_not_spent_by_create_spec_dispatch(self):
        self.assertIn(
            "この create-spec の dispatch では消費されず",
            self.text,
        )

    def test_forbidden_decision_table_literal_still_absent(self):
        # C6a (IMPLEMENTATION.md Conventions): this task's addition must
        # not accidentally introduce the forbidden literal.
        self.assertNotIn("decision table", self.text)
        self.assertNotIn("決定表", self.text)


if __name__ == "__main__":
    unittest.main()
