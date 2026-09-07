"""Tests for review-sca-axis/task0004: R4/R5 triage timing -- no
auto-apply, once per phase.

Covers task0004 Acceptance Criteria
(feature-docs/review-sca-axis/tasks/task0004.md):

- AC-1: Phase R4 states that a `vulnerability` finding is never classified
  auto-applicable and always falls to the needs-judgment side, and that no
  dependency update is auto-applied. (TS-15)
- AC-2: the document states that triage filing runs exactly once per review
  phase, immediately before the final round's R5, and not per round. (TS-9)
- AC-3: the document names the deterministic final-round signal (the
  round's closing disposition), the inputs it is computed from, and the
  point at which it is computed. (TS-9)
- AC-4: the document states explicitly that neither a filing dropped after
  an abnormal termination nor a filing in a non-final round can arise, and
  names the mechanism for each. (TS-9)
- AC-5: Phase R5's round-record shape carries the triage receipt field
  (executed flag, branch taken, filed / appended / suppressed packages,
  report path), documented as present-and-empty when filing did not run,
  and stated to introduce no new gate identifier and not to affect the
  completion gate. (TS-9)
- AC-6: the filing / report branch is stated to be decided mechanically
  from R0's probe result, with no user question in either mode. (TS-9)
- AC-7: in this task's worktree, `python3 -m unittest discover -s tests`
  exits 0 and `python3 em-workflow/scripts/check-plugin-invariants.py
  <repo-root>` exits 0 -- verified by actually running both commands
  (recorded in the implementer report; a suite cannot assert its own full
  outcome).

This is a documentation task (task0004.md Test Notes): verification is by
structural/textual assertion over review-phase.md's raw text, anchored on
the literal "Phase R4" / "Phase R5" headings so a statement landing outside
its phase fails, following the pattern of
tests/test_review_phase_llm_led.py. Whitespace is normalized before phrase
matching, matching that module's convention. Per Test Notes, AC-4 gets both
a positive assertion and a negative control (a forged section missing one
of the two sentences fails).
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"
REVIEW_PHASE_PATH = PLUGIN_ROOT / "references" / "review-phase.md"

R4_HEADING = "## Phase R4: Bounded auto-fix (≤ 3 loops, ON by default)"
R5_HEADING = "## Phase R5: Persist the round record"
R6_HEADING = "## Phase R6: Report (Japanese)"
TRIAGE_FILING_HEADING = (
    "### Triage filing: once per review phase, immediately before the "
    "final round's R5 (FR11, FR24)"
)


def _read(path):
    return path.read_text(encoding="utf-8")


def _slice(text, start_heading, end_heading=None):
    start = text.index(start_heading)
    if end_heading is None:
        return text[start:]
    end = text.index(end_heading, start + len(start_heading))
    return text[start:end]


def _norm(text):
    return re.sub(r"\s+", " ", text).strip()


class DocumentFixture:
    """Reads review-phase.md once and slices out R4/R5 -- the only two
    phases this task's plan authorizes touching (task0004.md Scope)."""

    _text = None

    @classmethod
    def text(cls):
        if cls._text is None:
            cls._text = _read(REVIEW_PHASE_PATH)
        return cls._text

    @classmethod
    def r4(cls):
        return _slice(cls.text(), R4_HEADING, R5_HEADING)

    @classmethod
    def r5(cls):
        return _slice(cls.text(), R5_HEADING, R6_HEADING)


# ---------------------------------------------------------------------------
# AC-1: `vulnerability` is never auto-applicable
# ---------------------------------------------------------------------------


def _states_vulnerability_never_auto_applicable(r4_norm):
    """The three things AC-1 requires: never-auto-applicable (regardless of
    shape), the two independent reasons (protocol forbids it; D4's prose-only
    contract routed through the existing shape probe), and the no-auto-apply
    statement about dependency updates themselves."""
    required = [
        "A `vulnerability` finding is never classified auto-applicable",
        "the needs-judgment side",
        "the protocol forbids it",
        "IMPLEMENTATION.md D4",
        "the shape probe above already classifies it `prose`",
        "No dependency update, lockfile edit or package installation is "
        "ever auto-applied",
    ]
    return all(s in r4_norm for s in required)


class TestAC1VulnerabilityNeverAutoApplicable(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r4 = DocumentFixture.r4()
        cls.r4_norm = _norm(cls.r4)

    def test_r4_heading_present(self):
        self.assertIn(R4_HEADING, DocumentFixture.text())

    def test_never_classified_auto_applicable_regardless_of_shape(self):
        self.assertIn(
            "A `vulnerability` finding is never classified auto-applicable",
            self.r4_norm,
        )
        self.assertIn("regardless of `shape`", self.r4_norm)
        self.assertIn("the needs-judgment side", self.r4_norm)

    def test_two_independent_reasons_stated(self):
        self.assertIn("neither alone load-bearing", self.r4_norm)
        self.assertIn("the protocol forbids it", self.r4_norm)
        self.assertIn(
            "axis 2's `suggestion` field is prose only by contract "
            "(IMPLEMENTATION.md D4)",
            self.r4_norm,
        )
        self.assertIn(
            "the shape probe above already classifies it `prose`",
            self.r4_norm,
        )

    def test_no_dependency_update_ever_auto_applied(self):
        self.assertIn(
            "No dependency update, lockfile edit or package installation "
            "is ever auto-applied",
            self.r4_norm,
        )

    def test_statement_lands_inside_r4_not_r5(self):
        self.assertNotIn(
            "A `vulnerability` finding is never classified auto-applicable",
            _norm(DocumentFixture.r5()),
        )

    def test_matcher_holds_on_the_real_document(self):
        self.assertTrue(_states_vulnerability_never_auto_applicable(self.r4_norm))


class TestAC1RegressionMatcherCanFail(unittest.TestCase):
    """tdd-testing discipline: prove the AC-1 matcher actually discriminates
    by forging text where one required element is dropped."""

    def test_matcher_rejects_text_missing_the_never_auto_applicable_clause(self):
        forged = _norm(
            "the protocol forbids it, and axis 2's `suggestion` field is "
            "prose only by contract (IMPLEMENTATION.md D4); the shape probe "
            "above already classifies it `prose`. No dependency update, "
            "lockfile edit or package installation is ever auto-applied."
        )
        self.assertFalse(_states_vulnerability_never_auto_applicable(forged))

    def test_matcher_rejects_text_missing_the_no_auto_apply_clause(self):
        forged = _norm(
            "A `vulnerability` finding is never classified auto-applicable "
            "and always falls to the needs-judgment side; neither alone "
            "load-bearing: the protocol forbids it, and axis 2's "
            "`suggestion` field is prose only by contract "
            "(IMPLEMENTATION.md D4); the shape probe above already "
            "classifies it `prose`."
        )
        self.assertFalse(_states_vulnerability_never_auto_applicable(forged))

    def test_matcher_accepts_a_well_formed_fragment(self):
        forged = _norm(
            "A `vulnerability` finding is never classified auto-applicable "
            "regardless of `shape` and always falls to the needs-judgment "
            "side; neither alone load-bearing: the protocol forbids it, "
            "and axis 2's `suggestion` field is prose only by contract "
            "(IMPLEMENTATION.md D4), so the shape probe above already "
            "classifies it `prose`. No dependency update, lockfile edit or "
            "package installation is ever auto-applied."
        )
        self.assertTrue(_states_vulnerability_never_auto_applicable(forged))


# ---------------------------------------------------------------------------
# AC-2 / AC-3: triage filing timing + the deterministic final-round signal
# ---------------------------------------------------------------------------


class TestAC2TriageFilingTimingOncePerPhase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r4 = DocumentFixture.r4()
        cls.r4_norm = _norm(cls.r4)

    def test_triage_filing_subsection_present_in_r4(self):
        self.assertIn(TRIAGE_FILING_HEADING, self.r4)

    def test_runs_exactly_once_per_review_phase(self):
        self.assertIn("exactly once per review phase", self.r4_norm)

    def test_runs_immediately_before_the_final_rounds_r5(self):
        self.assertIn(
            "immediately before the final round's R5", self.r4_norm
        )

    def test_states_not_per_round(self):
        self.assertIn("never per round", self.r4_norm)

    def test_subsection_lands_in_r4_not_r5(self):
        self.assertNotIn(TRIAGE_FILING_HEADING, DocumentFixture.r5())


class TestAC3DeterministicFinalRoundSignal(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r4_norm = _norm(DocumentFixture.r4())

    def test_names_the_signal_as_closing_disposition(self):
        self.assertIn("closing disposition", self.r4_norm)
        self.assertIn("IMPLEMENTATION.md D3", self.r4_norm)

    def test_names_the_computation_point(self):
        self.assertIn(
            "computed after Phase R4's loop termination and before the "
            "round record is written",
            self.r4_norm,
        )

    def test_names_every_input(self):
        for phrase in [
            "the residual critical/high count",
            "the `--report-only` flag",
            "the loop termination reason",
            "the batch rework counter",
        ]:
            self.assertIn(phrase, self.r4_norm)

    def test_names_the_disposition_value_vocabulary(self):
        self.assertIn("`another-round`", self.r4_norm)
        self.assertIn("`complete`", self.r4_norm)
        self.assertIn("`rework`", self.r4_norm)
        self.assertIn("`defer`", self.r4_norm)

    def test_filing_runs_iff_not_another_round(self):
        self.assertIn(
            "Filing runs iff the disposition is NOT `another-round`",
            self.r4_norm,
        )


# ---------------------------------------------------------------------------
# AC-4: neither failure mode can arise, mechanism named for each
# ---------------------------------------------------------------------------


def _states_both_failure_modes_closed(r4_norm):
    non_final_round_closed = (
        "a non-final round always yields the `another-round` disposition"
        in r4_norm
        and "filing cannot fire early" in r4_norm
    )
    abnormal_termination_closed = (
        "run that dies before R5 wrote no round record" in r4_norm
        and "recomputes the same disposition" in r4_norm
        and "idempotent under its own package-name duplicate detection"
        in r4_norm
    )
    return non_final_round_closed and abnormal_termination_closed


class TestAC4BothFailureModesClosed(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r4_norm = _norm(DocumentFixture.r4())

    def test_non_final_round_filing_impossible(self):
        self.assertIn(
            "a non-final round always yields the `another-round` "
            "disposition",
            self.r4_norm,
        )
        self.assertIn("filing cannot fire early", self.r4_norm)

    def test_abnormal_termination_cannot_drop_filing(self):
        self.assertIn(
            "run that dies before R5 wrote no round record", self.r4_norm
        )
        self.assertIn("recomputes the same disposition", self.r4_norm)
        self.assertIn(
            "idempotent under its own package-name duplicate detection",
            self.r4_norm,
        )

    def test_matcher_holds_on_the_real_document(self):
        self.assertTrue(_states_both_failure_modes_closed(self.r4_norm))


class TestAC4RegressionMatcherCanFail(unittest.TestCase):
    """Test Notes: AC-4 deserves a negative control because it is the
    criterion whose absence would be hardest to notice later -- a forged
    section missing one of the two sentences must fail."""

    def test_forged_section_missing_abnormal_termination_sentence_fails(self):
        forged = _norm(
            "a non-final round always yields the `another-round` "
            "disposition, so filing cannot fire early."
        )
        self.assertFalse(_states_both_failure_modes_closed(forged))

    def test_forged_section_missing_non_final_round_sentence_fails(self):
        forged = _norm(
            "a run that dies before R5 wrote no round record, so the "
            "resumed review recomputes the same disposition, filing then, "
            "safely, because the filing path is idempotent under its own "
            "package-name duplicate detection."
        )
        self.assertFalse(_states_both_failure_modes_closed(forged))

    def test_matcher_accepts_a_well_formed_fragment(self):
        forged = _norm(
            "a non-final round always yields the `another-round` "
            "disposition, so filing cannot fire early. a run that dies "
            "before R5 wrote no round record, so the resumed review "
            "recomputes the same disposition, filing then -- safely, "
            "because the filing path is idempotent under its own "
            "package-name duplicate detection."
        )
        self.assertTrue(_states_both_failure_modes_closed(forged))


# ---------------------------------------------------------------------------
# AC-5: Phase R5's round-record shape carries the triage receipt field
# ---------------------------------------------------------------------------


class TestAC5RoundRecordReceiptField(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r5 = DocumentFixture.r5()
        cls.r5_norm = _norm(cls.r5)

    def test_receipt_field_present_in_the_round_record_shape(self):
        self.assertIn("triage_filing:", self.r5)

    def test_receipt_field_carries_executed_flag(self):
        self.assertIn("executed:", self.r5)

    def test_receipt_field_carries_branch_taken(self):
        self.assertIn("branch:", self.r5)
        self.assertIn("ntd", self.r5)
        self.assertIn("report", self.r5)

    def test_receipt_field_carries_filed_appended_suppressed_packages(self):
        self.assertIn("filed:", self.r5)
        self.assertIn("appended:", self.r5)
        self.assertIn("duplicates_suppressed:", self.r5)

    def test_receipt_field_carries_report_path(self):
        self.assertIn("report_path:", self.r5)

    def test_receipt_field_present_and_empty_when_filing_did_not_run(self):
        self.assertIn(
            "empty when this round's disposition was `another-round`",
            self.r5_norm,
        )

    def test_receipt_introduces_no_new_gate_identifier(self):
        self.assertIn(
            "introduces no new gate identifier", self.r5_norm
        )

    def test_receipt_never_affects_the_completion_gate(self):
        self.assertIn(
            "never affects the completion gate", self.r5_norm
        )

    def test_receipt_field_lands_after_rework_required_in_the_shape(self):
        rework_idx = self.r5.index("rework_required: false")
        triage_idx = self.r5.index("triage_filing:")
        self.assertLess(rework_idx, triage_idx)


# ---------------------------------------------------------------------------
# AC-6: the filing / report branch is decided mechanically, no user question
# ---------------------------------------------------------------------------


class TestAC6BranchDecidedMechanically(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r4_norm = _norm(DocumentFixture.r4())

    def test_branch_decided_mechanically_from_r0_probe(self):
        self.assertIn(
            "decided mechanically from R0's probe result", self.r4_norm
        )

    def test_no_question_put_to_the_user_in_either_mode(self):
        self.assertIn(
            "no question is put to the user", self.r4_norm
        )
        self.assertIn("interactive or batch mode", self.r4_norm)

    def test_no_askuserquestion_dispatch_introduced_for_this(self):
        idx = self.r4_norm.index("decided mechanically from R0's probe result")
        window = self.r4_norm[max(0, idx - 200) : idx + 200]
        self.assertNotIn("AskUserQuestion(", window)


# ---------------------------------------------------------------------------
# Out-of-scope guard: R0-R3b (task0003) untouched by this module's assertions
# ---------------------------------------------------------------------------


class TestOutOfScopeUntouched(unittest.TestCase):
    """task0004.md Out of Scope: this task never asserts on R0-R3b content,
    and never asserts on the filing script's own behaviour or on
    batch-policies.yaml / batch-mode.md / the gate vocabulary (NFR5)."""

    def test_no_gate_id_declaration_introduced_by_this_tasks_additions(self):
        self.assertNotIn("gate_id:", DocumentFixture.r4())
        self.assertNotIn("gate_id:", DocumentFixture.r5())


# ---------------------------------------------------------------------------
# AC-7 / test ownership convention: standard-library-only imports (TS-22).
# ---------------------------------------------------------------------------


class TestOwnModuleStdlibOnly(unittest.TestCase):
    def test_only_standard_library_imports(self):
        import ast
        import sys

        source = Path(__file__).read_text(encoding="utf-8")
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
        non_stdlib = sorted(m for m in modules if m not in stdlib)
        self.assertEqual(non_stdlib, [])


if __name__ == "__main__":
    unittest.main()
