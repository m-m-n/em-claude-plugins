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

D6 rewrite (feature-docs/tier-decision-staged-jev, task0001): this module
predates that feature and asserted the single-reading score shape
(`score.probabilities["0"|"1"]` + `expectation_clear`/`confidence` as
threshold members via `p0_floor`/`expectation_clear_floor`/
`bucket_sum_floor`) and, in `TestTwoReadingContract`, the two-reading
`readings` input the new evaluator rejects outright. task0001 rewrites this
module's fixtures and payload builder to the new `final_score.probabilities`
(buckets `"0"`-`"3"`) shape and the new `bucket0_floor` /
`bucket0_1_sum_floor` member names, and removes what the new dedicated file
`tests/test_decide_tier_final_score.py` now fully supersedes:
`TestOutOfRangeAndNonFiniteObservations` (bucket range/finiteness is now
covered by that file's AC-2 tests), `TestNoNonFiniteTokenInEmittedResult`
(covered by that file's AC-2 strict-JSON tests), and `TestTwoReadingContract`
(the behavior it tested no longer exists; AC-3 there covers the legacy
`readings` rejection). The remaining classes below keep testing the same
generic, still-true invariant (no hardcoded row identifier or threshold
literal; a row's declared comparisons are always evaluated; only a
memberless row is an unconditional fallthrough) against the new score shape.

Covers task0012 Acceptance Criteria:
- AC-1: no row identifier literal and no threshold numeric literal appears
  in the evaluator; a renamed threshold member makes its row not match
  rather than falling back to a stale literal.
- AC-2: a row declaring at least one threshold member is never returned
  without its declared comparisons being evaluated, including when its
  identifier is unrecognized; only a row declaring no threshold member is
  an unconditional fallthrough.
- AC-3: a valid score that satisfies no declared row, against a rule table
  with no unconditional fallthrough row, yields the tier that removes
  nothing.
"""

import importlib.util
import re
import subprocess
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


def build_payload(p0=None, p1=None, p2=None, p3=None, jev_available=True,
                   codex_available=True):
    probabilities = {}
    for key, value in (("0", p0), ("1", p1), ("2", p2), ("3", p3)):
        if value is not None:
            probabilities[key] = value
    return {
        "jev_available": jev_available,
        "codex_available": codex_available,
        "final_score": {"probabilities": probabilities},
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
        forged = self.source + '\nfake = row.get("bucket0_floor", 0.80)\n'
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
        "    bucket0_minimum: 0.80\n"  # renamed from bucket0_floor
        "  - id: full\n"
        "    order: 2\n"
        "    tier: full\n"
        "probability_sum_tolerance: 0.02\n"
    )

    def test_renamed_member_row_never_matches_even_with_generous_score(self):
        with tempfile.TemporaryDirectory() as tmp:
            rules_path = write_rules(tmp, self.RENAMED_RULES)
            rules = dt._load_rules(rules_path)
            payload = build_payload(p0=0.95, p1=0.03, p2=0.01, p3=0.01)
            result = dt.decide(payload, rules)
            self.assertEqual(result["tier"], "full")
            self.assertEqual(result["decided_by"], "threshold_rows:full")
            self.assertNotEqual(result["decided_by"], "threshold_rows:minimal")

    def test_non_vacuity_same_score_matches_minimal_against_the_real_table(self):
        # Proves the rename above (not something else) is what blocked the
        # match: the identical score against the real default rules table
        # DOES resolve to minimal.
        rules = dt._load_rules(TIER_RULES_PATH)
        payload = build_payload(p0=0.95, p1=0.03, p2=0.01, p3=0.01)
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
        "    bucket0_floor: 0.60\n"
        "  - id: full\n"
        "    order: 2\n"
        "    tier: full\n"
        "probability_sum_tolerance: 0.02\n"
    )

    def test_unrecognized_row_matches_when_its_own_condition_holds(self):
        with tempfile.TemporaryDirectory() as tmp:
            rules_path = write_rules(tmp, self.FAIL_OPEN_REGRESSION_RULES)
            rules = dt._load_rules(rules_path)
            payload = build_payload(p0=0.90, p1=0.05, p2=0.03, p3=0.02)
            result = dt.decide(payload, rules)
            self.assertEqual(result["tier"], "hypothetical")
            self.assertEqual(result["decided_by"], "threshold_rows:unrecognized_future_row")

    def test_unrecognized_row_does_not_match_when_its_condition_fails(self):
        # The fail-open regression: pre-task0012 code returned the row the
        # instant it was reached, regardless of whether bucket0_floor was
        # met, because the identifier matched neither "minimal" nor
        # "reduced" and fell straight into the unconditional-return branch.
        # The data-driven evaluator must instead evaluate the declared
        # bucket0_floor comparison and fall through to `full` when it fails.
        with tempfile.TemporaryDirectory() as tmp:
            rules_path = write_rules(tmp, self.FAIL_OPEN_REGRESSION_RULES)
            rules = dt._load_rules(rules_path)
            payload = build_payload(p0=0.30, p1=0.05, p2=0.35, p3=0.30)
            result = dt.decide(payload, rules)
            self.assertEqual(result["tier"], "full")
            self.assertEqual(result["decided_by"], "threshold_rows:full")

    def test_non_vacuity_the_two_cases_above_differ(self):
        with tempfile.TemporaryDirectory() as tmp:
            rules_path = write_rules(tmp, self.FAIL_OPEN_REGRESSION_RULES)
            rules = dt._load_rules(rules_path)
            matching = dt.decide(build_payload(p0=0.90, p1=0.05, p2=0.03, p3=0.02), rules)
            non_matching = dt.decide(
                build_payload(p0=0.30, p1=0.05, p2=0.35, p3=0.30), rules
            )
            self.assertNotEqual(matching["tier"], non_matching["tier"])


class TestOnlyAMemberlessRowIsUnconditional(unittest.TestCase):
    def test_a_row_with_no_extra_field_beyond_metadata_is_unconditional(self):
        rules = dt._load_rules(TIER_RULES_PATH)
        # A valid score satisfying neither minimal nor reduced still reaches
        # `full`, which declares no threshold member.
        payload = build_payload(p0=0.10, p1=0.10, p2=0.40, p3=0.40)
        result = dt.decide(payload, rules)
        self.assertEqual(result["tier"], "full")
        self.assertEqual(result["decided_by"], "threshold_rows:full")


# ---------------------------------------------------------------------------
# AC-3: a valid score matching no declared row, against a table with no
# unconditional fallthrough row, yields the tier that removes nothing.
# ---------------------------------------------------------------------------


class TestNoRowMatchesAndNoFallthroughRowExists(unittest.TestCase):
    """Rewritten from the task0012 fixture of the same intent: under the new
    validate-then-evaluate flow (task0001), an absent or non-numeric bucket
    is caught by probability validation before any row is even reached, so
    the "no fallthrough row" case is now exercised with a VALID score that
    simply satisfies no declared row."""

    NO_FALLTHROUGH_RULES = (
        "threshold_rows:\n"
        "  - id: minimal\n"
        "    order: 1\n"
        "    tier: minimal\n"
        "    bucket0_floor: 0.80\n"
        "  - id: reduced\n"
        "    order: 2\n"
        "    tier: reduced\n"
        "    bucket0_1_sum_floor: 0.85\n"
        "probability_sum_tolerance: 0.02\n"
    )

    def test_valid_score_matching_neither_row_yields_safest_tier_with_no_fallthrough(self):
        with tempfile.TemporaryDirectory() as tmp:
            rules_path = write_rules(tmp, self.NO_FALLTHROUGH_RULES)
            rules = dt._load_rules(rules_path)
            payload = build_payload(p0=0.10, p1=0.10, p2=0.40, p3=0.40)
            result = dt.decide(payload, rules)
            self.assertEqual(result["tier"], "full")
            self.assertNotEqual(result["decided_by"], "threshold_rows:minimal")
            self.assertNotEqual(result["decided_by"], "threshold_rows:reduced")
            self.assertIn("no threshold row matched", result["reason"])

    def test_non_vacuity_a_satisfying_score_still_matches_against_this_table(self):
        # Proves the table above is otherwise capable of matching -- the
        # safest-tier result above comes from no row being satisfied, not
        # from a broken custom table.
        with tempfile.TemporaryDirectory() as tmp:
            rules_path = write_rules(tmp, self.NO_FALLTHROUGH_RULES)
            rules = dt._load_rules(rules_path)
            payload = build_payload(p0=0.90, p1=0.05, p2=0.03, p3=0.02)
            result = dt.decide(payload, rules)
            self.assertEqual(result["tier"], "minimal")


if __name__ == "__main__":
    unittest.main()
