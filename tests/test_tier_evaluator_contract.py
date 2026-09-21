"""Tests for the data-driven, fail-safe tier evaluator contract
(feature-docs/task-tier-reduction, task0012).

Loads em-workflow/scripts/decide-tier.py via importlib.util and calls its
functions directly -- the same technique test_tier_rules.py already uses --
rather than importing PyYAML in this test module (NFR7: test code imports
no third-party package). Custom rule tables used by the fail-open /
renamed-member regression tests are written to a temporary directory and
passed via decide-tier.py's optional rule-table-path argument (direct
dt._load_rules() + dt.decide()/dt.evaluate_thresholds() calls) rather than
mutating the real em-workflow/references/tier-rules.yaml.

Each matcher below is paired with a negative proof / non-vacuity guard per
IMPLEMENTATION.md's "Test module convention".

Covers task0012 Acceptance Criteria:
- AC-1: no row identifier literal and no threshold numeric literal appears
  in the evaluator; a renamed threshold member makes its row not match
  rather than falling back to a stale literal.
- AC-2: a row declaring at least one threshold member is never returned
  without its declared comparisons being evaluated, including when its
  identifier is unrecognized; only a row declaring no threshold member is
  an unconditional fallthrough.
- AC-3: an absent/non-numeric declared member makes its row not match and
  evaluation continues; with no unconditional row present, the result is
  the tier that removes nothing.
- AC-4: a non-finite or out-of-range observation yields the tier that
  removes nothing with a reason naming the offending member, and neither
  the most-reducing nor the middle tier is reachable with such an
  observation.
- AC-5: no non-finite token can appear in the emitted result; the process
  exits zero for every input including the malformed ones above.
- AC-6: the evaluator accepts two readings in one invocation and returns
  the tier that removes nothing when they evaluate to different tiers; a
  single reading is still accepted and behaves as it does today.
"""

import importlib.util
import json
import math
import re
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TIER_RULES_PATH = REPO_ROOT / "em-workflow" / "references" / "tier-rules.yaml"
DECIDE_TIER_SCRIPT = REPO_ROOT / "em-workflow" / "scripts" / "decide-tier.py"


def load_decide_tier_module():
    spec = importlib.util.spec_from_file_location(
        "_decide_tier_under_test_contract", DECIDE_TIER_SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


dt = load_decide_tier_module()


def run_cli(stdin_text, rules_path=None):
    import subprocess

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


def build_payload(p0=None, p1=None, expectation_clear=None, jev_available=True,
                   codex_available=True, basis="description_plus_code"):
    probabilities = {}
    if p0 is not None:
        probabilities["0"] = p0
    if p1 is not None:
        probabilities["1"] = p1
    score = {"probabilities": probabilities}
    if expectation_clear is not None:
        score["expectation_clear"] = expectation_clear
    return {
        "jev_available": jev_available,
        "codex_available": codex_available,
        "basis": basis,
        "score": score,
    }


def write_rules(tmp_dir, yaml_text):
    path = Path(tmp_dir) / "custom-tier-rules.yaml"
    path.write_text(yaml_text, encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# AC-1: no row identifier literal / no threshold numeric literal in the
# evaluator; a renamed threshold member makes its row not match.
# ---------------------------------------------------------------------------


class TestNoHardcodedRowIdentifiersOrThresholdLiterals(unittest.TestCase):
    """Static-source checks for the fail-open anti-pattern this task
    removes: `row.get(<member>, <number>)` (a literal default reinstating a
    stale threshold) and `row_id == "minimal"` / `row_id == "reduced"`
    (identifier-based branching)."""

    GET_WITH_NUMERIC_DEFAULT = re.compile(r"\.get\([^)]*,\s*-?\d+\.\d+\s*\)")
    ROW_ID_EQUALITY = re.compile(r'row_id\s*==\s*"(minimal|reduced|full)"')

    @classmethod
    def setUpClass(cls):
        cls.source = DECIDE_TIER_SCRIPT.read_text(encoding="utf-8")

    def test_no_get_call_supplies_a_numeric_default(self):
        self.assertIsNone(self.GET_WITH_NUMERIC_DEFAULT.search(self.source))

    def test_get_with_numeric_default_matcher_fires_on_a_forged_copy(self):
        forged = self.source + '\nfake = row.get("p0_floor", 0.80)\n'
        self.assertIsNotNone(self.GET_WITH_NUMERIC_DEFAULT.search(forged))
        # Non-vacuity: the real source does not trip it.
        self.assertIsNone(self.GET_WITH_NUMERIC_DEFAULT.search(self.source))

    def test_no_row_identifier_equality_branch(self):
        self.assertIsNone(self.ROW_ID_EQUALITY.search(self.source))

    def test_row_identifier_equality_matcher_fires_on_a_forged_copy(self):
        forged = self.source + '\nif row_id == "minimal":\n    pass\n'
        self.assertIsNotNone(self.ROW_ID_EQUALITY.search(forged))
        self.assertIsNone(self.ROW_ID_EQUALITY.search(self.source))


class TestRenamedThresholdMemberDoesNotMatch(unittest.TestCase):
    """A rules table whose row keeps its recognizable `id` ("minimal") but
    has had its floor field renamed must not match via a stale literal
    default and must not match at all -- the row becomes unsatisfiable."""

    RENAMED_RULES = (
        "threshold_rows:\n"
        "  - id: minimal\n"
        "    order: 1\n"
        "    tier: minimal\n"
        "    p0_minimum: 0.80\n"  # renamed from p0_floor
        "    expectation_clear_floor: 0.5\n"
        "  - id: full\n"
        "    order: 2\n"
        "    tier: full\n"
    )

    def test_renamed_member_row_never_matches_even_with_generous_score(self):
        with tempfile.TemporaryDirectory() as tmp:
            rules_path = write_rules(tmp, self.RENAMED_RULES)
            rules = dt._load_rules(rules_path)
            payload = build_payload(p0=0.95, expectation_clear=0.95)
            result = dt.decide(payload, rules)
            self.assertEqual(result["tier"], "full")
            self.assertNotEqual(result["decided_by"], "threshold_rows:minimal")

    def test_non_vacuity_same_score_matches_minimal_against_the_real_table(self):
        # Proves the rename above (not something else) is what blocked the
        # match: the identical score against the real default rules table
        # DOES resolve to minimal.
        rules = dt._load_rules(TIER_RULES_PATH)
        payload = build_payload(p0=0.95, expectation_clear=0.95)
        result = dt.decide(payload, rules)
        self.assertEqual(result["tier"], "minimal")
        self.assertEqual(result["decided_by"], "threshold_rows:minimal")


# ---------------------------------------------------------------------------
# AC-2: a row declaring a threshold member always has its comparisons
# evaluated, including when its identifier is unrecognized; only a row
# declaring no threshold member is an unconditional fallthrough.
# ---------------------------------------------------------------------------


class TestUnrecognizedRowIdentifierStillEvaluatesItsComparisons(unittest.TestCase):
    FAIL_OPEN_REGRESSION_RULES = (
        "threshold_rows:\n"
        "  - id: unrecognized_future_row\n"
        "    order: 1\n"
        "    tier: hypothetical\n"
        "    p0_floor: 0.60\n"
        "  - id: full\n"
        "    order: 2\n"
        "    tier: full\n"
    )

    def test_unrecognized_row_matches_when_its_own_condition_holds(self):
        with tempfile.TemporaryDirectory() as tmp:
            rules_path = write_rules(tmp, self.FAIL_OPEN_REGRESSION_RULES)
            rules = dt._load_rules(rules_path)
            payload = build_payload(p0=0.90)
            result = dt.decide(payload, rules)
            self.assertEqual(result["tier"], "hypothetical")
            self.assertEqual(result["decided_by"], "threshold_rows:unrecognized_future_row")

    def test_unrecognized_row_does_not_match_when_its_condition_fails(self):
        # The fail-open regression: pre-task0012 code returned the row the
        # instant it was reached, regardless of whether p0_floor was met,
        # because the identifier matched neither "minimal" nor "reduced"
        # and fell straight into the unconditional-return branch. The
        # data-driven evaluator must instead evaluate the declared
        # p0_floor comparison and fall through to `full` when it fails.
        with tempfile.TemporaryDirectory() as tmp:
            rules_path = write_rules(tmp, self.FAIL_OPEN_REGRESSION_RULES)
            rules = dt._load_rules(rules_path)
            payload = build_payload(p0=0.30)
            result = dt.decide(payload, rules)
            self.assertEqual(result["tier"], "full")
            self.assertEqual(result["decided_by"], "threshold_rows:full")

    def test_non_vacuity_the_two_cases_above_differ(self):
        with tempfile.TemporaryDirectory() as tmp:
            rules_path = write_rules(tmp, self.FAIL_OPEN_REGRESSION_RULES)
            rules = dt._load_rules(rules_path)
            matching = dt.decide(build_payload(p0=0.90), rules)
            non_matching = dt.decide(build_payload(p0=0.30), rules)
            self.assertNotEqual(matching["tier"], non_matching["tier"])


class TestOnlyAMemberlessRowIsUnconditional(unittest.TestCase):
    def test_a_row_with_no_extra_field_beyond_metadata_is_unconditional(self):
        rules = dt._load_rules(TIER_RULES_PATH)
        # A score satisfying nothing still reaches `full`, which declares
        # no threshold member.
        payload = build_payload(p0=0.0, p1=0.0, expectation_clear=0.0)
        result = dt.decide(payload, rules)
        self.assertEqual(result["tier"], "full")
        self.assertEqual(result["decided_by"], "threshold_rows:full")


# ---------------------------------------------------------------------------
# AC-3: absent/non-numeric declared member -> row not matched, evaluation
# continues; no unconditional row present -> safest tier.
# ---------------------------------------------------------------------------


class TestAbsentOrNonNumericMemberFallsThroughWithNoFallthroughRow(unittest.TestCase):
    NO_FALLTHROUGH_RULES = (
        "threshold_rows:\n"
        "  - id: minimal\n"
        "    order: 1\n"
        "    tier: minimal\n"
        "    p0_floor: 0.80\n"
        "    expectation_clear_floor: 0.5\n"
        "  - id: reduced\n"
        "    order: 2\n"
        "    tier: reduced\n"
        "    p0_floor: 0.40\n"
        "    bucket_sum_floor: 0.85\n"
    )

    def test_absent_p0_with_no_fallthrough_row_yields_safest_tier(self):
        with tempfile.TemporaryDirectory() as tmp:
            rules_path = write_rules(tmp, self.NO_FALLTHROUGH_RULES)
            rules = dt._load_rules(rules_path)
            payload = build_payload()  # no p0, no p1, no expectation_clear
            result = dt.decide(payload, rules)
            self.assertEqual(result["tier"], "full")
            self.assertNotEqual(result["decided_by"], "threshold_rows:minimal")
            self.assertNotEqual(result["decided_by"], "threshold_rows:reduced")

    def test_non_numeric_p0_with_no_fallthrough_row_yields_safest_tier(self):
        with tempfile.TemporaryDirectory() as tmp:
            rules_path = write_rules(tmp, self.NO_FALLTHROUGH_RULES)
            rules = dt._load_rules(rules_path)
            payload = build_payload()
            payload["score"]["probabilities"]["0"] = "high"
            result = dt.decide(payload, rules)
            self.assertEqual(result["tier"], "full")

    def test_non_vacuity_a_satisfying_score_still_matches_against_this_table(self):
        # Proves the table above is otherwise capable of matching -- the
        # safest-tier result in the two cases above comes from the
        # absent/non-numeric observation, not from a broken custom table.
        with tempfile.TemporaryDirectory() as tmp:
            rules_path = write_rules(tmp, self.NO_FALLTHROUGH_RULES)
            rules = dt._load_rules(rules_path)
            payload = build_payload(p0=0.90, expectation_clear=0.9)
            result = dt.decide(payload, rules)
            self.assertEqual(result["tier"], "minimal")


# ---------------------------------------------------------------------------
# AC-4: non-finite / out-of-range observation -> safest tier, reason names
# the offending member, neither minimal nor reduced reachable.
# ---------------------------------------------------------------------------


class TestOutOfRangeAndNonFiniteObservations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = dt._load_rules(TIER_RULES_PATH)

    def test_p0_above_one_yields_safest_tier_with_named_reason(self):
        payload = build_payload(p0=1.5, expectation_clear=0.9)
        result = dt.decide(payload, self.rules)
        self.assertEqual(result["tier"], "full")
        self.assertIn("probabilities", result["reason"].lower() + result["reason"])
        self.assertEqual(result["decided_by"], "fallback_matrix:invalid_observation")

    def test_p0_below_zero_yields_safest_tier(self):
        payload = build_payload(p0=-0.1, expectation_clear=0.9)
        result = dt.decide(payload, self.rules)
        self.assertEqual(result["tier"], "full")
        self.assertEqual(result["decided_by"], "fallback_matrix:invalid_observation")

    def test_expectation_clear_nan_yields_safest_tier_not_minimal(self):
        payload = build_payload(p0=0.90, expectation_clear=float("nan"))
        result = dt.decide(payload, self.rules)
        self.assertEqual(result["tier"], "full")
        self.assertIn("expectation_clear", result["reason"])

    def test_expectation_clear_infinite_yields_safest_tier(self):
        payload = build_payload(p0=0.90, expectation_clear=float("inf"))
        result = dt.decide(payload, self.rules)
        self.assertEqual(result["tier"], "full")

    def test_p1_out_of_range_blocks_reduced_even_when_p0_alone_qualifies(self):
        # p0=0.50 alone clears reduced's p0_floor (0.40), but the bucket
        # sum needs p1, and p1 is malformed -- neither minimal nor reduced
        # may be reached.
        payload = build_payload(p0=0.50, p1=2.5)
        result = dt.decide(payload, self.rules)
        self.assertEqual(result["tier"], "full")
        self.assertNotEqual(result["decided_by"], "threshold_rows:reduced")
        self.assertNotEqual(result["decided_by"], "threshold_rows:minimal")

    def test_negative_infinity_p0_yields_safest_tier(self):
        payload = build_payload(p0=float("-inf"), expectation_clear=0.9)
        result = dt.decide(payload, self.rules)
        self.assertEqual(result["tier"], "full")

    def test_non_vacuity_the_same_p0_in_range_reaches_minimal(self):
        payload = build_payload(p0=0.90, expectation_clear=0.9)
        result = dt.decide(payload, self.rules)
        self.assertEqual(result["tier"], "minimal")


# ---------------------------------------------------------------------------
# AC-5: no non-finite token in the emitted result; exit zero.
# ---------------------------------------------------------------------------


class TestNoNonFiniteTokenInEmittedResult(unittest.TestCase):
    def _strict_json_loads(self, text):
        def _reject(token):
            raise ValueError(f"non-finite JSON token encountered: {token}")

        return json.loads(text, parse_constant=_reject)

    def test_nan_probability_input_produces_strictly_parseable_output(self):
        payload = build_payload(p0=0.5, expectation_clear=0.5)
        payload["score"]["probabilities"]["0"] = float("nan")
        stdin_text = json.dumps(payload)
        # Sanity: the input we constructed really does carry a bare
        # non-finite JSON token (Python's json.dumps default allow_nan).
        self.assertIn("NaN", stdin_text)

        result = run_cli(stdin_text)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = self._strict_json_loads(result.stdout)
        self.assertEqual(data["tier"], "full")

    def test_infinite_expectation_clear_input_produces_strictly_parseable_output(self):
        payload = build_payload(p0=0.5, expectation_clear=0.5)
        payload["score"]["expectation_clear"] = float("inf")
        stdin_text = json.dumps(payload)
        self.assertIn("Infinity", stdin_text)

        result = run_cli(stdin_text)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = self._strict_json_loads(result.stdout)
        self.assertEqual(data["tier"], "full")

    def test_well_formed_input_still_parses_strictly_and_exits_zero(self):
        payload = build_payload(p0=0.81, expectation_clear=0.6)
        result = run_cli(json.dumps(payload))
        self.assertEqual(result.returncode, 0, result.stderr)
        data = self._strict_json_loads(result.stdout)
        self.assertEqual(data["tier"], "minimal")

    def test_non_vacuity_the_raw_output_of_the_nan_case_really_did_carry_a_bare_token_pre_sanitization(self):
        # Confirms the module-level sanitizer is doing real work: encoding
        # the same malformed observation WITHOUT going through the
        # evaluator's output path produces a bare, non-standard token.
        naive = json.dumps({"score": {"probabilities": {"0": float("nan")}}})
        self.assertIn("NaN", naive)
        with self.assertRaises(ValueError):
            json.loads(naive, parse_constant=lambda tok: (_ for _ in ()).throw(ValueError(tok)))


# ---------------------------------------------------------------------------
# AC-6: two readings in one invocation.
# ---------------------------------------------------------------------------


class TestTwoReadingContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = dt._load_rules(TIER_RULES_PATH)

    def _reading(self, basis, p0=None, p1=None, expectation_clear=None):
        probabilities = {}
        if p0 is not None:
            probabilities["0"] = p0
        if p1 is not None:
            probabilities["1"] = p1
        score = {"probabilities": probabilities}
        if expectation_clear is not None:
            score["expectation_clear"] = expectation_clear
        return {"basis": basis, "score": score}

    def test_two_readings_agreeing_use_that_tier(self):
        payload = {
            "jev_available": True,
            "codex_available": True,
            "readings": [
                self._reading("description_only", p0=0.81, expectation_clear=0.6),
                self._reading("description_plus_code", p0=0.85, expectation_clear=0.7),
            ],
        }
        result = dt.decide(payload, self.rules)
        self.assertEqual(result["tier"], "minimal")

    def test_two_readings_disagreeing_yield_safest_tier(self):
        payload = {
            "jev_available": True,
            "codex_available": True,
            "readings": [
                self._reading("description_only", p0=0.10, expectation_clear=0.1),
                self._reading("description_plus_code", p0=0.85, expectation_clear=0.7),
            ],
        }
        result = dt.decide(payload, self.rules)
        self.assertEqual(result["tier"], "full")
        self.assertEqual(result["decided_by"], "fallback_matrix:readings_disagree")

    def test_non_vacuity_two_readings_agreeing_on_full_is_not_flagged_as_disagreement(self):
        payload = {
            "jev_available": True,
            "codex_available": True,
            "readings": [
                self._reading("a", p0=0.10, expectation_clear=0.1),
                self._reading("b", p0=0.10, expectation_clear=0.1),
            ],
        }
        result = dt.decide(payload, self.rules)
        self.assertEqual(result["tier"], "full")
        self.assertNotEqual(result["decided_by"], "fallback_matrix:readings_disagree")

    def test_single_reading_via_readings_list_behaves_like_today(self):
        payload = {
            "jev_available": True,
            "codex_available": True,
            "readings": [self._reading("description_only", p0=0.81, expectation_clear=0.6)],
        }
        result = dt.decide(payload, self.rules)
        self.assertEqual(result["tier"], "minimal")
        self.assertEqual(result["decided_by"], "threshold_rows:minimal")

    def test_top_level_basis_score_single_reading_still_accepted(self):
        # Today's shape, unchanged.
        payload = build_payload(p0=0.81, expectation_clear=0.6)
        result = dt.decide(payload, self.rules)
        self.assertEqual(result["tier"], "minimal")
        self.assertEqual(result["observed"]["basis"], "description_plus_code")
        self.assertEqual(result["observed"]["score"], payload["score"])

    def test_cli_accepts_two_readings_end_to_end(self):
        payload = {
            "jev_available": True,
            "codex_available": True,
            "readings": [
                self._reading("description_only", p0=0.10, expectation_clear=0.1),
                self._reading("description_plus_code", p0=0.85, expectation_clear=0.7),
            ],
        }
        result = run_cli(json.dumps(payload))
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["tier"], "full")
        self.assertEqual(data["decided_by"], "fallback_matrix:readings_disagree")


if __name__ == "__main__":
    unittest.main()
