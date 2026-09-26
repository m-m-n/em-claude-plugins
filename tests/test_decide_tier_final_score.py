"""Tests for task0001 (feature-docs/tier-decision-staged-jev): the
final-score evaluator and its threshold/fallback rules.

Loads em-workflow/scripts/decide-tier.py via importlib.util and calls its
functions directly for unit-level assertions -- the same technique
tests/test_check_plugin_invariants.py already uses for
check-plugin-invariants.py -- rather than importing PyYAML in this test
module (NFR7: test code imports no third-party package; decide-tier.py's
own `import yaml` is a runtime dependency of the plugin, not a test
dependency). CLI-contract tests drive the script as a subprocess, matching
test/README.md's convention for hook/script contract tests.

Rule-table variants used by the rule-table-defect tests (AC-6) are built as
in-memory dicts (or, for the custom-rule-table-path test, a temporary YAML
file) and passed directly to `dt.decide()` / the CLI's optional rules-path
argument -- the real `em-workflow/references/tier-rules.yaml` is never
modified by a test (task plan Test Notes).

Each raw-text matcher below is paired with a negative proof (a forged
sample that must trip the same matcher) and a non-vacuity guard (the real
text was read and is non-empty), per IMPLEMENTATION.md's test convention.

Covers task0001 Acceptance Criteria
(feature-docs/tier-decision-staged-jev/tasks/task0001.md):

- AC-1 (FR4; TS-1..TS-4): threshold rows evaluated over the final bucket
  probabilities alone, top-down, first match wins; `expectation_clear`
  never influences the decision; the two written boundary cases match
  inclusively.
- AC-2 (FR3, NFR1; TS-5): a missing bucket, a non-finite bucket, an
  out-of-range bucket, and an out-of-tolerance sum each give full with the
  offending bucket or the sum named in the reason; the CLI always exits 0
  and always emits strict JSON.
- AC-3 (FR5; TS-6): the legacy `readings` input is rejected as invalid;
  `readings_disagree` appears in neither `decide-tier.py` nor
  `tier-rules.yaml`; `fallback_matrix` has no row keyed on disagreement.
- AC-4 (FR8; TS-7): `codex_available=false` forces full via
  `fallback_matrix:jev_only_usable`, never a `threshold_rows:` value, even
  for a score that would otherwise be minimal; the rule table's
  `jev_only_usable` row action is full.
- AC-5 (FR9; TS-8): `jev_available=false` forces full via
  `fallback_matrix:jev_unusable` regardless of `codex_available`;
  `jev_exit_codes` classifies exit codes 1, 2 and 75 as unusable.
- AC-6 (NFR1, NFR2; TS-13): the rule table holds exactly the three
  threshold rows in order with the specified floors, declares
  `probability_sum_tolerance` as 0.02, and has no row on `confidence` or
  `expectation_clear`; a rule table lacking the tolerance or a row's lower
  bound gives full with a reason naming the missing member; the evaluator
  source has no process-spawning, network or model facility.
- AC-7 (NFR3): this module is discovered by
  `python3 -m unittest discover -s tests`, imports only the standard
  library directly, and pairs every raw-text matcher with a negative proof
  and a non-vacuity guard.

Input-shape and CLI-degraded-input coverage that is not tied to a single
numbered AC (missing/non-boolean `jev_available`/`codex_available`, a
non-object payload, empty/malformed stdin) is kept here too: it is the same
evaluator contract this task rewrites, and the equivalent pre-existing
coverage was removed from tests/test_tier_rules.py as part of this task's
rewrite (see this task's reported deviations).
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
TIER_RULES_PATH = REPO_ROOT / "em-workflow" / "references" / "tier-rules.yaml"
DECIDE_TIER_SCRIPT = REPO_ROOT / "em-workflow" / "scripts" / "decide-tier.py"
THIS_TEST_FILE = Path(__file__).resolve()

# Facility tokens the evaluator source must never contain (AC-6: "no
# process-spawning, network or model facility").
FORBIDDEN_FACILITY_TOKENS = (
    "import subprocess",
    "import socket",
    "import urllib",
    "import requests",
    "import http.client",
    "os.system(",
    "os.popen(",
    "Popen(",
)


def load_decide_tier_module():
    spec = importlib.util.spec_from_file_location(
        "_decide_tier_under_test_final_score", DECIDE_TIER_SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


dt = load_decide_tier_module()


def run_cli(stdin_text, rules_path=None):
    args = [sys.executable, str(DECIDE_TIER_SCRIPT)]
    if rules_path is not None:
        args.append(str(rules_path))
    return subprocess.run(
        args,
        input=stdin_text,
        capture_output=True,
        text=True,
        timeout=15,
    )


def _strict_json_loads(text):
    def _reject(token):
        raise ValueError(f"non-finite JSON token encountered: {token}")

    return json.loads(text, parse_constant=_reject)


def build_final_score(p0=None, p1=None, p2=None, p3=None, expectation_clear=None,
                       confidence=None):
    probabilities = {}
    for key, value in (("0", p0), ("1", p1), ("2", p2), ("3", p3)):
        if value is not None:
            probabilities[key] = value
    score = {"probabilities": probabilities}
    if expectation_clear is not None:
        score["expectation_clear"] = expectation_clear
    if confidence is not None:
        score["confidence"] = confidence
    return score


def build_payload(p0=None, p1=None, p2=None, p3=None, expectation_clear=None,
                   jev_available=True, codex_available=True):
    return {
        "jev_available": jev_available,
        "codex_available": codex_available,
        "final_score": build_final_score(
            p0=p0, p1=p1, p2=p2, p3=p3, expectation_clear=expectation_clear
        ),
    }


# ---------------------------------------------------------------------------
# AC-1: threshold rows over the final bucket probabilities alone.
# ---------------------------------------------------------------------------


class TestAC1ThresholdRowsOverFinalBucketProbabilities(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = dt._load_rules(TIER_RULES_PATH)

    def _decide(self, **kwargs):
        return dt.decide(build_payload(**kwargs), self.rules)

    def test_ts1_low_first_bucket_high_second_bucket_is_reduced(self):
        result = self._decide(p0=0.09, p1=0.90, p2=0.01, p3=0.00)
        self.assertEqual(result["tier"], "reduced")
        self.assertEqual(result["decided_by"], "threshold_rows:reduced")

    def test_ts2_moderate_first_bucket_with_high_sum_is_reduced(self):
        # Under the old rule table this was forced to full by a P(0) floor
        # on the reduced row; that floor is removed (task plan Design).
        result = self._decide(p0=0.37, p1=0.59, p2=0.03, p3=0.01)
        self.assertEqual(result["tier"], "reduced")
        self.assertEqual(result["decided_by"], "threshold_rows:reduced")

    def test_ts3_high_first_bucket_is_minimal_with_expectation_clear(self):
        result = self._decide(p0=0.85, p1=0.10, p2=0.05, p3=0.00, expectation_clear=0.1)
        self.assertEqual(result["tier"], "minimal")
        self.assertEqual(result["decided_by"], "threshold_rows:minimal")

    def test_ts3_high_first_bucket_is_minimal_without_expectation_clear(self):
        result = self._decide(p0=0.85, p1=0.10, p2=0.05, p3=0.00)
        self.assertEqual(result["tier"], "minimal")
        self.assertEqual(result["decided_by"], "threshold_rows:minimal")

    def test_ts4_low_probabilities_is_full(self):
        result = self._decide(p0=0.50, p1=0.30, p2=0.15, p3=0.05)
        self.assertEqual(result["tier"], "full")
        self.assertEqual(result["decided_by"], "threshold_rows:full")

    def test_boundary_bucket0_exactly_at_minimal_floor_is_minimal(self):
        result = self._decide(p0=0.80, p1=0.10, p2=0.05, p3=0.05)
        self.assertEqual(result["tier"], "minimal")

    def test_boundary_bucket_sum_exactly_at_reduced_floor_is_reduced(self):
        result = self._decide(p0=0.50, p1=0.35, p2=0.10, p3=0.05)
        self.assertEqual(result["tier"], "reduced")

    def test_row_order_first_match_wins_minimal_over_reduced(self):
        # bucket0=0.90 alone satisfies minimal; bucket0+1 also clears
        # reduced's floor -- minimal must win because it is evaluated first.
        result = self._decide(p0=0.90, p1=0.05, p2=0.03, p3=0.02)
        self.assertEqual(result["tier"], "minimal")

    def test_non_vacuity_reversing_the_reduced_and_full_expectations_would_fail(self):
        full_case = self._decide(p0=0.50, p1=0.30, p2=0.15, p3=0.05)
        reduced_case = self._decide(p0=0.09, p1=0.90, p2=0.01, p3=0.00)
        with self.assertRaises(AssertionError):
            self.assertEqual(full_case["tier"], "reduced")
        with self.assertRaises(AssertionError):
            self.assertEqual(reduced_case["tier"], "full")


# ---------------------------------------------------------------------------
# AC-2: probability validation before any threshold row is evaluated.
# ---------------------------------------------------------------------------


class TestAC2ProbabilityValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = dt._load_rules(TIER_RULES_PATH)

    def _decide(self, **kwargs):
        return dt.decide(build_payload(**kwargs), self.rules)

    def test_missing_bucket_three_gives_full_naming_bucket(self):
        payload = build_payload(p0=0.5, p1=0.3, p2=0.2)  # bucket "3" omitted
        result = dt.decide(payload, self.rules)
        self.assertEqual(result["tier"], "full")
        self.assertIn("'3'", result["reason"])
        self.assertFalse(result["decided_by"].startswith("threshold_rows:"))

    def test_nan_bucket_two_gives_full_naming_bucket(self):
        result = self._decide(p0=0.1, p1=0.1, p2=float("nan"), p3=0.1)
        self.assertEqual(result["tier"], "full")
        self.assertIn("'2'", result["reason"])

    def test_out_of_range_bucket_one_gives_full_naming_bucket(self):
        result = self._decide(p0=0.1, p1=1.2, p2=0.1, p3=0.1)
        self.assertEqual(result["tier"], "full")
        self.assertIn("'1'", result["reason"])

    def test_sum_out_of_tolerance_gives_full_naming_sum(self):
        result = self._decide(p0=0.85, p1=0.10, p2=0.10, p3=0.05)  # sums to 1.10
        self.assertEqual(result["tier"], "full")
        self.assertIn("1.1", result["reason"])
        self.assertIn("sum", result["reason"].lower())

    def test_extra_bucket_key_gives_full_naming_bucket(self):
        # Design section: "a key outside that set is invalid."
        payload = build_payload(p0=0.5, p1=0.3, p2=0.1, p3=0.1)
        payload["final_score"]["probabilities"]["4"] = 0.0
        result = dt.decide(payload, self.rules)
        self.assertEqual(result["tier"], "full")
        self.assertIn("'4'", result["reason"])

    def test_all_four_malformed_cases_exit_zero_with_strict_json_stdout(self):
        cases = [
            (build_payload(p0=0.5, p1=0.3, p2=0.2), "'3'"),
            (build_payload(p0=0.1, p1=0.1, p2=float("nan"), p3=0.1), "'2'"),
            (build_payload(p0=0.1, p1=1.2, p2=0.1, p3=0.1), "'1'"),
            (build_payload(p0=0.85, p1=0.10, p2=0.10, p3=0.05), "1.1"),
        ]
        for index, (payload, needle) in enumerate(cases):
            with self.subTest(case=index):
                stdin_text = json.dumps(payload)
                result = run_cli(stdin_text)
                self.assertEqual(result.returncode, 0, result.stderr)
                data = _strict_json_loads(result.stdout)
                self.assertEqual(data["tier"], "full")
                self.assertIn(needle, data["reason"])

    def test_non_vacuity_a_valid_four_bucket_score_is_not_full(self):
        result = self._decide(p0=0.85, p1=0.05, p2=0.05, p3=0.05)
        self.assertNotEqual(result["decided_by"], "fallback_matrix:malformed_input")
        self.assertEqual(result["tier"], "minimal")


# ---------------------------------------------------------------------------
# AC-3: legacy two-reading input rejected; disagreement rule removed.
# ---------------------------------------------------------------------------


class TestAC3LegacyReadingsRejected(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = dt._load_rules(TIER_RULES_PATH)

    def test_legacy_readings_payload_gives_full_as_invalid_input(self):
        payload = {
            "jev_available": True,
            "codex_available": True,
            "readings": [
                {"basis": "description_only",
                 "score": {"probabilities": {"0": 0.1, "1": 0.1, "2": 0.4, "3": 0.4}}},
                {"basis": "description_plus_code",
                 "score": {"probabilities": {"0": 0.85, "1": 0.1, "2": 0.03, "3": 0.02}}},
            ],
        }
        result = dt.decide(payload, self.rules)
        self.assertEqual(result["tier"], "full")
        self.assertEqual(result["decided_by"], "fallback_matrix:malformed_input")

    def test_legacy_readings_present_alongside_a_valid_final_score_still_rejected(self):
        payload = build_payload(p0=0.90, p1=0.05, p2=0.03, p3=0.02)
        payload["readings"] = [{"basis": "description_only", "score": {}}]
        result = dt.decide(payload, self.rules)
        self.assertEqual(result["tier"], "full")
        self.assertEqual(result["decided_by"], "fallback_matrix:malformed_input")

    def test_non_vacuity_the_same_final_score_without_readings_reaches_minimal(self):
        payload = build_payload(p0=0.90, p1=0.05, p2=0.03, p3=0.02)
        result = dt.decide(payload, self.rules)
        self.assertEqual(result["tier"], "minimal")

    def test_readings_disagree_absent_from_evaluator_source(self):
        text = DECIDE_TIER_SCRIPT.read_text(encoding="utf-8")
        self.assertGreater(len(text), 0)
        self.assertNotIn("readings_disagree", text)

    def test_readings_disagree_matcher_fires_on_a_forged_evaluator_copy(self):
        text = DECIDE_TIER_SCRIPT.read_text(encoding="utf-8")
        forged = text + '\n# forged: "fallback_matrix:readings_disagree"\n'
        self.assertIn("readings_disagree", forged)
        self.assertNotIn("readings_disagree", text)

    def test_readings_disagree_absent_from_rules_file(self):
        text = TIER_RULES_PATH.read_text(encoding="utf-8")
        self.assertGreater(len(text), 0)
        self.assertNotIn("readings_disagree", text)

    def test_readings_disagree_matcher_fires_on_a_forged_rules_copy(self):
        text = TIER_RULES_PATH.read_text(encoding="utf-8")
        forged = text + "\nforged_row: readings_disagree\n"
        self.assertIn("readings_disagree", forged)
        self.assertNotIn("readings_disagree", text)

    def test_fallback_matrix_has_no_row_keyed_on_disagreement(self):
        fallback_matrix = self.rules.get("fallback_matrix")
        self.assertIsInstance(fallback_matrix, list)
        self.assertGreater(len(fallback_matrix), 0)
        for row in fallback_matrix:
            with self.subTest(row=row.get("id")):
                blob = json.dumps(row)
                self.assertNotIn("disagree", blob.lower())

    def test_non_vacuity_disagreement_matcher_would_catch_a_forged_row(self):
        forged_row = {"id": "forged", "note": "resolves on readings disagreement"}
        self.assertIn("disagree", json.dumps(forged_row).lower())


# ---------------------------------------------------------------------------
# AC-4: codex_available=false forces full via jev_only_usable.
# ---------------------------------------------------------------------------


class TestAC4CodexUnavailableForcesFull(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = dt._load_rules(TIER_RULES_PATH)

    def test_codex_unavailable_with_would_be_minimal_score_gives_full(self):
        payload = build_payload(p0=0.95, p1=0.03, p2=0.01, p3=0.01, codex_available=False)
        result = dt.decide(payload, self.rules)
        self.assertEqual(result["tier"], "full")
        self.assertEqual(result["decided_by"], "fallback_matrix:jev_only_usable")
        self.assertFalse(result["decided_by"].startswith("threshold_rows:"))

    def test_non_vacuity_same_score_with_codex_available_reaches_minimal(self):
        payload = build_payload(p0=0.95, p1=0.03, p2=0.01, p3=0.01, codex_available=True)
        result = dt.decide(payload, self.rules)
        self.assertEqual(result["tier"], "minimal")
        self.assertEqual(result["decided_by"], "threshold_rows:minimal")

    def test_rules_jev_only_usable_row_action_is_full(self):
        fallback_matrix = self.rules.get("fallback_matrix")
        row = next(r for r in fallback_matrix if r.get("id") == "jev_only_usable")
        self.assertEqual(row.get("action"), "full")

    def test_non_vacuity_forged_row_action_would_be_detected_as_different(self):
        forged_row = {"id": "jev_only_usable", "action": "evaluate_threshold_rows"}
        self.assertNotEqual(forged_row.get("action"), "full")


# ---------------------------------------------------------------------------
# AC-5: jev_available=false forces full via jev_unusable, regardless of
# codex_available; jev_exit_codes classification.
# ---------------------------------------------------------------------------


class TestAC5JevUnavailableForcesFull(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = dt._load_rules(TIER_RULES_PATH)

    def test_jev_unavailable_with_codex_available_gives_full(self):
        payload = build_payload(p0=0.95, p1=0.03, p2=0.01, p3=0.01,
                                 jev_available=False, codex_available=True)
        result = dt.decide(payload, self.rules)
        self.assertEqual(result["tier"], "full")
        self.assertEqual(result["decided_by"], "fallback_matrix:jev_unusable")

    def test_jev_unavailable_with_codex_unavailable_gives_full(self):
        payload = build_payload(p0=0.95, p1=0.03, p2=0.01, p3=0.01,
                                 jev_available=False, codex_available=False)
        result = dt.decide(payload, self.rules)
        self.assertEqual(result["tier"], "full")
        self.assertEqual(result["decided_by"], "fallback_matrix:jev_unusable")

    def test_non_vacuity_jev_available_true_with_same_score_reaches_minimal(self):
        payload = build_payload(p0=0.95, p1=0.03, p2=0.01, p3=0.01,
                                 jev_available=True, codex_available=True)
        result = dt.decide(payload, self.rules)
        self.assertEqual(result["tier"], "minimal")

    def test_jev_exit_codes_classifies_1_2_75_as_unusable(self):
        exit_codes = self.rules.get("jev_exit_codes")
        self.assertIsInstance(exit_codes, dict)
        self.assertEqual(exit_codes.get(0), "usable")
        for code in (1, 2, 75):
            with self.subTest(code=code):
                self.assertEqual(exit_codes.get(code), "unusable")

    def test_non_vacuity_forged_usable_code_would_be_detected(self):
        exit_codes = dict(self.rules.get("jev_exit_codes") or {})
        exit_codes[1] = "usable"
        self.assertNotEqual(exit_codes.get(1), "unusable")
        self.assertEqual(self.rules.get("jev_exit_codes", {}).get(1), "unusable")


# ---------------------------------------------------------------------------
# AC-6: rule table shape, tolerance, and defect handling.
# ---------------------------------------------------------------------------


class TestAC6RuleTableShapeAndDefects(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = dt._load_rules(TIER_RULES_PATH)

    def _declared_members(self, row):
        return {k: v for k, v in row.items() if k not in dt.ROW_METADATA_KEYS}

    def test_exactly_three_threshold_rows_minimal_reduced_full_in_order(self):
        rows = self.rules.get("threshold_rows")
        self.assertEqual(len(rows), 3)
        self.assertEqual([row.get("id") for row in rows], ["minimal", "reduced", "full"])

        minimal_members = self._declared_members(rows[0])
        reduced_members = self._declared_members(rows[1])
        full_members = self._declared_members(rows[2])

        self.assertEqual(len(minimal_members), 1)
        self.assertEqual(list(minimal_members.values())[0], 0.80)
        self.assertEqual(len(reduced_members), 1)
        self.assertEqual(list(reduced_members.values())[0], 0.85)
        self.assertEqual(full_members, {})

    def test_probability_sum_tolerance_declared_as_0_02(self):
        self.assertEqual(self.rules.get("probability_sum_tolerance"), 0.02)

    def test_no_threshold_row_declares_confidence_or_expectation_clear(self):
        for row in self.rules.get("threshold_rows"):
            for key in row:
                with self.subTest(row=row.get("id"), key=key):
                    self.assertNotIn("confidence", key.lower())
                    self.assertNotIn("expectation_clear", key.lower())

    def test_non_vacuity_forged_row_key_would_be_detected(self):
        forged_row = {"id": "minimal", "expectation_clear_floor": 0.5}
        offending = [key for key in forged_row if "expectation_clear" in key.lower()]
        self.assertTrue(offending)

    def test_missing_tolerance_in_rule_table_gives_full_naming_it(self):
        broken_rules = {
            key: value for key, value in self.rules.items()
            if key != "probability_sum_tolerance"
        }
        payload = build_payload(p0=0.90, p1=0.05, p2=0.03, p3=0.02)
        result = dt.decide(payload, broken_rules)
        self.assertEqual(result["tier"], "full")
        self.assertIn("probability_sum_tolerance", result["reason"])
        self.assertNotEqual(result["decided_by"], "threshold_rows:minimal")

    def test_non_vacuity_same_score_against_the_real_rules_reaches_minimal(self):
        payload = build_payload(p0=0.90, p1=0.05, p2=0.03, p3=0.02)
        result = dt.decide(payload, self.rules)
        self.assertEqual(result["tier"], "minimal")

    def test_missing_threshold_row_lower_bound_gives_full_naming_it(self):
        broken_rules = copy.deepcopy(self.rules)
        member_key = None
        for row in broken_rules["threshold_rows"]:
            if row.get("id") == "minimal":
                member_key = next(
                    key for key in row if key not in dt.ROW_METADATA_KEYS
                )
                row[member_key] = None
        self.assertIsNotNone(member_key, "fixture must locate the minimal row")

        payload = build_payload(p0=0.95, p1=0.02, p2=0.02, p3=0.01)
        result = dt.decide(payload, broken_rules)
        self.assertEqual(result["tier"], "full")
        self.assertIn(member_key, result["reason"])
        self.assertNotEqual(result["decided_by"], "threshold_rows:minimal")

    def test_non_vacuity_the_unmodified_row_still_matches_minimal(self):
        payload = build_payload(p0=0.95, p1=0.02, p2=0.02, p3=0.01)
        result = dt.decide(payload, self.rules)
        self.assertEqual(result["tier"], "minimal")


class TestEvaluatorHasNoProcessNetworkOrModelFacility(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = DECIDE_TIER_SCRIPT.read_text(encoding="utf-8")

    def test_source_is_non_empty(self):
        self.assertGreater(len(self.source), 0)

    def test_no_forbidden_facility_token_present(self):
        for token in FORBIDDEN_FACILITY_TOKENS:
            with self.subTest(token=token):
                self.assertNotIn(token, self.source)

    def test_forbidden_facility_matcher_fires_on_a_forged_copy(self):
        for token in FORBIDDEN_FACILITY_TOKENS:
            with self.subTest(token=token):
                forged = self.source + f"\n{token}\n"
                self.assertIn(token, forged)
                self.assertNotIn(token, self.source)


# ---------------------------------------------------------------------------
# Input-shape / degraded-input coverage (SC-1 step 0), not tied to a single
# numbered AC -- kept here after removal from tests/test_tier_rules.py.
# ---------------------------------------------------------------------------


class TestInputShapeValidation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = dt._load_rules(TIER_RULES_PATH)

    def test_missing_jev_available_names_the_missing_field(self):
        payload = {
            "codex_available": True,
            "final_score": build_final_score(p0=0.9, p1=0.05, p2=0.03, p3=0.02),
        }
        result = dt.decide(payload, self.rules)
        self.assertEqual(result["tier"], "full")
        self.assertIn("jev_available", result["reason"])

    def test_non_boolean_jev_available_is_malformed(self):
        payload = {"jev_available": "yes", "codex_available": True, "final_score": {}}
        result = dt.decide(payload, self.rules)
        self.assertEqual(result["tier"], "full")
        self.assertIn("jev_available", result["reason"])

    def test_missing_codex_available_names_the_missing_field(self):
        payload = {
            "jev_available": True,
            "final_score": build_final_score(p0=0.9, p1=0.05, p2=0.03, p3=0.02),
        }
        result = dt.decide(payload, self.rules)
        self.assertEqual(result["tier"], "full")
        self.assertIn("codex_available", result["reason"])

    def test_payload_not_an_object_yields_full(self):
        result = dt.decide(["not", "a", "mapping"], self.rules)
        self.assertEqual(result["tier"], "full")
        self.assertTrue(result["reason"])

    def test_missing_final_score_when_both_available_names_it(self):
        payload = {"jev_available": True, "codex_available": True}
        result = dt.decide(payload, self.rules)
        self.assertEqual(result["tier"], "full")
        self.assertIn("final_score", result["reason"])

    def test_non_vacuity_a_complete_payload_does_not_report_a_missing_field(self):
        payload = build_payload(p0=0.1, p1=0.1, p2=0.1, p3=0.1)
        result = dt.decide(payload, self.rules)
        self.assertNotIn("jev_available", result["reason"])
        self.assertNotIn("codex_available", result["reason"])


class TestCliDegradedInput(unittest.TestCase):
    def test_empty_stdin_yields_full_with_zero_exit(self):
        result = run_cli("")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["tier"], "full")
        self.assertIn("empty", data["reason"].lower())

    def test_malformed_json_yields_full_with_zero_exit(self):
        result = run_cli("{not valid json")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["tier"], "full")

    def test_non_object_json_yields_full_with_zero_exit(self):
        result = run_cli("[1, 2, 3]")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["tier"], "full")

    def test_well_formed_input_round_trips_through_the_cli(self):
        payload = build_payload(p0=0.85, p1=0.05, p2=0.05, p3=0.05)
        result = run_cli(json.dumps(payload))
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["tier"], "minimal")
        self.assertEqual(data["observed"]["final_score"], payload["final_score"])

    def test_cli_never_blocks_waiting_for_more_input(self):
        # A 15s subprocess timeout with no matching completion would raise
        # TimeoutExpired; not raising proves no interactive read occurred.
        result = run_cli("")
        self.assertIsNotNone(result.returncode)

    def test_custom_rule_table_path_argument_is_honoured(self):
        with tempfile.TemporaryDirectory() as tmp:
            custom_path = Path(tmp) / "custom-tier-rules.yaml"
            custom_path.write_text(
                "threshold_rows:\n"
                "  - id: minimal\n"
                "    tier: minimal\n"
                "    bucket0_floor: 0.01\n"
                "  - id: full\n"
                "    tier: full\n"
                "probability_sum_tolerance: 0.02\n",
                encoding="utf-8",
            )
            payload = build_payload(p0=0.05, p1=0.05, p2=0.05, p3=0.85)
            result = run_cli(json.dumps(payload), rules_path=custom_path)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            self.assertEqual(data["tier"], "minimal")

    def test_non_vacuity_the_same_score_against_the_real_default_table_is_full(self):
        payload = build_payload(p0=0.05, p1=0.05, p2=0.05, p3=0.85)
        result = run_cli(json.dumps(payload))
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["tier"], "full")


# ---------------------------------------------------------------------------
# AC-7: this module is stdlib-only.
# ---------------------------------------------------------------------------


class TestThisModuleImportsOnlyTheStandardLibrary(unittest.TestCase):
    def test_only_standard_library_imports(self):
        source = THIS_TEST_FILE.read_text(encoding="utf-8")
        tree = ast.parse(source)
        stdlib = sys.stdlib_module_names
        modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    modules.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    modules.add(node.module.split(".")[0])
        non_stdlib = sorted(module for module in modules if module not in stdlib)
        self.assertEqual(non_stdlib, [])


if __name__ == "__main__":
    unittest.main()
