"""Tests for task0028: origin identity, and who chooses what gets checked.

Pins this task's own Acceptance Criteria (AC-1 through AC-5) over the three
documents it owns:

- `em-workflow/references/rework-task-synthesis.md` (AC-1, AC-7): the
  origin-identity pair `origin_kind` / `origin_id` is named once, inside
  Invariant 6, and is the field list Section 10's SPEC-change transition
  now names in place of the retired single-field origin identifier.
- `em-workflow/references/question-resolution.md` (AC-2, AC-3, AC-4): the
  security / license / `reversible: false` check runs over the
  orchestrator-held bound set for the dispatch -- never over the subset an
  untrusted worker named -- and both origin kinds (`review`, `verify`) are
  admissible.
- `em-workflow/references/contracts/rework-planner-contract.md` (AC-5): the
  worker's declared origins are traceability only; the check target is the
  orchestrator's bound set, never `evidence[]`.

Each matcher below is paired with a negative proof against a synthetic
violating sample of the kind the underlying finding named (untrusted-set
selection, review-only admission, single-direction membership), and every
absence assertion carries a non-vacuity guard, per this task's Test Notes
and C9.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SYNTHESIS_PATH = REPO_ROOT / "em-workflow" / "references" / "rework-task-synthesis.md"
RESOLUTION_PATH = REPO_ROOT / "em-workflow" / "references" / "question-resolution.md"
REWORK_CONTRACT_PATH = (
    REPO_ROOT / "em-workflow" / "references" / "contracts" / "rework-planner-contract.md"
)


def _read(path):
    if not path.is_file():
        raise AssertionError(f"expected file to exist: {path}")
    return path.read_text(encoding="utf-8")


def _norm(text):
    return re.sub(r"\s+", " ", text)


# ---------------------------------------------------------------------------
# AC-1 (NFR1): the origin-identity pair is named once, inside Invariant 6.
# ---------------------------------------------------------------------------


class TestAC1OriginIdentityPairDefinedInSynthesisInvariant6(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(SYNTHESIS_PATH)
        cls.norm = _norm(cls.text)
        cls.resolution_text = _read(RESOLUTION_PATH)
        cls.contract_text = _read(REWORK_CONTRACT_PATH)

    def _invariant_6_text(self):
        start = self.text.index("6. Review-sourced tasks carry")
        end = self.text.index("7. Interactive and batch")
        return self.text[start:end]

    def test_invariant_6_names_the_pair(self):
        section = _norm(self._invariant_6_text())
        self.assertIn(
            "`origin_kind` (`review` | `verify`) and `origin_id`", section
        )

    def test_invariant_6_names_which_id_review_carries(self):
        section = _norm(self._invariant_6_text())
        self.assertIn(
            "for `origin_kind: review`, `origin_id` is the finding's "
            "`stable_id`",
            section,
        )

    def test_invariant_6_names_which_id_verify_carries(self):
        section = _norm(self._invariant_6_text())
        self.assertIn(
            "for `origin_kind: verify`, `origin_id` is the failed item's "
            "ID",
            section,
        )

    def test_negative_proof_pair_missing_from_invariant_fails_matcher(self):
        # Synthetic violating sample: the pre-task0028 Invariant 6, which
        # draws the review/verify distinction but never names the pair.
        fake_invariant = (
            "6. Review-sourced tasks carry the finding's `stable_id`, "
            "verify-sourced tasks carry the failed item's ID, as "
            "`provenance`."
        )
        self.assertNotIn(
            "`origin_kind` (`review` | `verify`) and `origin_id`",
            fake_invariant,
        )

    def test_eleven_invariants_still_present_section_not_renumbered(self):
        # Retention + non-vacuity companion: adding the pair inside
        # Invariant 6 must not grow, shrink or renumber the invariant list
        # (C3 -- this document's section list is pinned against a document
        # outside this feature's change set).
        start = self.text.index("## 11. Invariants")
        end = self.text.index("## 12. Validation")
        section = self.text[start:end]
        items = re.findall(r"^\d+\.", section, re.MULTILINE)
        self.assertEqual(len(items), 11)

    def test_thirteen_top_level_sections_still_present_in_order(self):
        indices = []
        for n in range(1, 14):
            marker = f"## {n}. "
            self.assertIn(marker, self.text, f"missing top-level section {n}")
            indices.append(self.text.index(marker))
        self.assertEqual(indices, sorted(indices))

    def test_no_other_document_defines_the_pair(self):
        # AC-1: no other document DEFINES the pair (states which id each
        # origin_kind carries) -- consumers cite this document instead.
        for text, name in (
            (self.resolution_text, "question-resolution.md"),
            (self.contract_text, "rework-planner-contract.md"),
        ):
            self.assertNotIn(
                "for `origin_kind: review`, `origin_id` is the finding's",
                text,
                f"{name} must not redefine the origin-identity pair",
            )
            self.assertNotIn(
                "for `origin_kind: verify`, `origin_id` is the failed "
                "item's",
                text,
                f"{name} must not redefine the origin-identity pair",
            )

    def test_non_vacuity_synthesis_document_actually_contains_definitions(
        self,
    ):
        # Non-vacuity guard: the phrases the absence check above searches
        # for are genuinely present in the owning document, so an absent
        # feature could not trivially pass the absence check too.
        self.assertIn(
            "for `origin_kind: review`, `origin_id` is the finding's",
            self.norm,
        )
        self.assertIn(
            "for `origin_kind: verify`, `origin_id` is the failed item's",
            self.norm,
        )


class TestAC7SpecChangeTransitionFieldListUsesOriginPair(unittest.TestCase):
    """AC-7 (FR7, NFR1): Section 10's SPEC-change transition step 4 names
    the origin pair in place of the retired single-field origin
    identifier; step count and section numbering are unchanged (C3)."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SYNTHESIS_PATH)

    def _section_10(self):
        start = self.text.index("## 10. Workflow state transition")
        end = self.text.index("## 11. Invariants")
        return self.text[start:end]

    def test_step_4_names_origin_pair(self):
        section = _norm(self._section_10())
        self.assertIn(
            "phase-state `rework.yaml` records `reason`, `origin_kind`, "
            "`origin_id`, `recorded_at_commit`, and `replan_authorized: "
            "true`",
            section,
        )

    def test_step_4_no_longer_names_the_retired_field(self):
        # Built at run time (never a contiguous literal) so this needle
        # never trips the retired-identifier absence scan (IMPLEMENTATION.md
        # Shared Components).
        retired_field = "finding" + "_stable_id"
        self.assertNotIn(f"`reason`, `{retired_field}`,", self.text)

    def test_negative_proof_old_field_list_would_be_caught(self):
        retired_field = "finding" + "_stable_id"
        fake_step_4 = (
            "4. phase-state `rework.yaml` records `reason`, "
            f"`{retired_field}`, `recorded_at_commit`, and "
            "`replan_authorized: true`"
        )
        self.assertIn(f"`reason`, `{retired_field}`,", fake_step_4)

    def test_still_defers_field_definitions_to_phase_state(self):
        section = _norm(self._section_10())
        self.assertIn(
            "field definitions owned by `references/phase-state.md`; "
            "this document does not restate them",
            section,
        )

    def test_still_five_numbered_steps_in_spec_change_transition(self):
        marker = "**When rework needs a SPEC.md change**"
        start = self.text.index(marker)
        end = self.text.index("Step 2's `create-plan` re-entry")
        section = self.text[start:end]
        numbered = re.findall(r"^(\d+)\. ", section, re.MULTILINE)
        self.assertEqual(numbered, ["1", "2", "3", "4", "5"])


# ---------------------------------------------------------------------------
# AC-2 (NFR2, FR11): the check runs over the orchestrator-held bound set,
# never over the packet-named subset or any other worker-supplied field.
# ---------------------------------------------------------------------------


class TestAC2CheckRunsOverOrchestratorHeldBoundSet(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(RESOLUTION_PATH)

    def _origin_verification_section(self):
        start = self.text.index("**Origin verification.**")
        end = self.text.index("4. **Question shape.**")
        return self.text[start:end]

    def test_states_check_runs_over_the_whole_bound_set(self):
        section = _norm(self._origin_verification_section()).lower()
        self.assertIn("this check runs over the whole bound set above", section)

    def test_states_bound_set_is_orchestrator_held_for_the_dispatch(self):
        section = _norm(self._origin_verification_section())
        self.assertIn("bound set for this dispatch", section)
        self.assertIn(
            "`origin_kind` is orchestrator-held, never packet-supplied",
            section,
        )

    def test_states_not_derived_from_packet_or_worker_supplied_field(self):
        section = _norm(self._origin_verification_section())
        self.assertIn(
            "never over only the origins the packet named, and never "
            "derived from `evidence[]` or any other worker-supplied field",
            section,
        )

    def test_negative_proof_evidence_scoped_check_target_fails_matcher(self):
        # Synthetic violating sample (per this task's Test Notes / finding
        # e04b7c2915da683f): a document whose check target is the packet's
        # evidence, not the orchestrator's bound set -- the exact defect
        # this task fixes.
        fake_section = (
            "**Origin verification.** The orchestrator reads each origin "
            "named in `evidence[]` and aborts when that origin's category "
            "is `security` or `license`."
        )
        self.assertNotIn(
            "never over only the origins the packet named, and never "
            "derived from `evidence[]` or any other worker-supplied field",
            fake_section,
        )
        self.assertNotIn(
            "this check runs over the whole bound set above",
            fake_section.lower(),
        )

    def test_non_vacuity_bound_set_table_present(self):
        # Non-vacuity guard: the bound set itself is genuinely defined
        # (not merely named in passing) before the absence-style checks
        # above are trusted.
        section = self._origin_verification_section()
        rows = re.findall(r"^\s*\|\s*`(review|verify)`\s*\|", section, re.MULTILINE)
        self.assertEqual(sorted(rows), ["review", "verify"])


# ---------------------------------------------------------------------------
# AC-3 (NFR2): both directions of the membership rule, non-overridable.
# ---------------------------------------------------------------------------


class TestAC3BidirectionalMembershipRuleNonOverridable(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(RESOLUTION_PATH)

    def _origin_verification_section(self):
        start = self.text.index("**Origin verification.**")
        end = self.text.index("4. **Question shape.**")
        return self.text[start:end]

    def test_direction_1_named_origin_outside_bound_set_aborts(self):
        section = _norm(self._origin_verification_section())
        self.assertIn(
            "an origin that is absent, unresolvable, or not a member of "
            "the bound set admits nothing, and the run aborts here",
            section,
        )

    def test_direction_2_bound_set_member_carrying_category_aborts_regardless(
        self,
    ):
        section = _norm(self._origin_verification_section())
        self.assertIn(
            "aborts, regardless of what the packet named, when any "
            "bound-set member's category is `security` or `license`",
            section,
        )

    def test_both_directions_marked_non_overridable(self):
        # Refreshed by rework-contract-drift/task0004 AC-4: direction 2 no
        # longer says "likewise" -- it repeats direction 1's own closing
        # sentence verbatim, so both directions use the IDENTICAL wording.
        section = _norm(self._origin_verification_section()).lower()
        non_overridable_phrase = (
            "this abort is final and non-overridable, exactly as the "
            "fail-closed classification's precedence reservation above "
            "states for its own abort arms"
        )
        self.assertEqual(section.count(non_overridable_phrase), 2)

    def test_negative_proof_single_direction_membership_rule_fails_matcher(
        self,
    ):
        # Synthetic violating sample (AC-6): a membership rule stating only
        # the "named origin must be in the bound set" direction, omitting
        # the "bound-set member carrying a fail-closed category aborts
        # regardless of what the packet named" direction entirely.
        fake_section = (
            "**Origin verification.** Every origin named by the packet "
            "must be a member of the bound set; an origin outside it "
            "aborts."
        )
        self.assertNotIn(
            "aborts, regardless of what the packet named, when any "
            "bound-set member's category is `security` or `license`",
            fake_section,
        )
        self.assertNotIn("non-overridable", fake_section)

    def test_non_vacuity_precedence_reservation_wording_exists_upstream(
        self,
    ):
        # Non-vacuity guard: the "final and non-overridable" phrase this
        # step reuses genuinely exists in the Precedence reservation it
        # cites, so the reuse is a real citation, not an invented match.
        self.assertIn(
            "the abort arm is evaluated first and its abort is final and "
            "non-overridable",
            _norm(self.text).lower(),
        )


# ---------------------------------------------------------------------------
# AC-4 (FR7): both origin_kind values are admissible; neither wording
# requires a review stable_id alone, nor excludes verify-sourced rework.
# ---------------------------------------------------------------------------


class TestAC4BothOriginKindsAcceptedNeitherExclusivelyRequired(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(RESOLUTION_PATH)

    def _origin_verification_section(self):
        start = self.text.index("**Origin verification.**")
        end = self.text.index("4. **Question shape.**")
        return self.text[start:end]

    def test_review_kind_matched_against_review_round_record(self):
        section = _norm(self._origin_verification_section())
        self.assertIn(
            "every finding in the review round record for this feature",
            section,
        )

    def test_verify_kind_matched_against_workflow_yaml_failed_items(self):
        section = _norm(self._origin_verification_section())
        self.assertIn(
            "every entry of `workflow.yaml`'s `verify` step `failed_items`",
            section,
        )

    def test_no_statement_requires_review_stable_id_as_sole_origin(self):
        self.assertNotIn(
            "must name the originating review finding(s) by `stable_id`",
            self.text,
        )

    def test_no_statement_makes_verify_ineligible_for_the_gate(self):
        lowered = self.text.lower()
        self.assertNotIn("verify-sourced rework is not eligible", lowered)
        self.assertNotIn("verify-sourced rework cannot reach", lowered)
        self.assertNotIn(
            "only a review-sourced question may reach classification",
            lowered,
        )

    def test_negative_proof_review_only_admission_fails_matcher(self):
        # Synthetic violating sample (AC-6, finding 112aadaef68d8fd8): a
        # document admitting only review origins, which is exactly what
        # made every verify-sourced spec-change rework abort before
        # classification pre-task0028.
        fake_section = (
            "**Origin verification.** Only an origin whose `origin_kind` "
            "is `review` may reach classification; a `verify`-sourced "
            "origin aborts here unconditionally."
        )
        self.assertNotIn(
            "every entry of `workflow.yaml`'s `verify` step `failed_items`",
            fake_section,
        )

    def test_non_vacuity_both_rows_present_in_the_table(self):
        section = self._origin_verification_section()
        rows = re.findall(r"^\s*\|\s*`(review|verify)`\s*\|", section, re.MULTILINE)
        self.assertEqual(sorted(rows), ["review", "verify"])


# ---------------------------------------------------------------------------
# AC-5 (NFR1): the worker's declared origins are traceability only; no
# abort arm or verification step is restated.
# ---------------------------------------------------------------------------


class TestAC5WorkerDeclarationIsTraceabilityOnly(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(REWORK_CONTRACT_PATH)

    def _transition_section(self):
        start = self.text.index("## Specification-change transition")
        end = self.text.index(
            "## Other conditions under which a question packet may be returned"
        )
        return self.text[start:end]

    def test_states_origins_declared_for_traceability_only(self):
        section = _norm(self._transition_section()).lower()
        self.assertIn("these declared origins are traceability only", section)
        self.assertIn(
            "untrusted, exactly like the rest of the rework-planner's "
            "output",
            section,
        )

    def test_states_check_target_is_orchestrators_bound_set(self):
        section = _norm(self._transition_section())
        self.assertIn(
            "that check target is the orchestrator's own bound set for "
            "this dispatch, never `evidence[]` or any other "
            "worker-supplied field",
            section,
        )

    def test_restates_no_abort_arm_and_no_verification_step(self):
        section = _norm(self._transition_section()).lower()
        self.assertIn(
            "this document restates neither that check's abort arms nor "
            "its verification procedure",
            section,
        )
        self.assertIn(
            "both belong to `references/question-resolution.md`, cited "
            "here and not restated",
            section,
        )

    def test_negative_proof_worker_declaration_treated_as_authoritative_fails_matcher(
        self,
    ):
        # Synthetic violating sample: a document treating the worker's
        # declared origins as the authoritative check target -- the bug
        # this task fixes -- rather than stating them as traceability only.
        fake_section = (
            "## Specification-change transition\n\n"
            "The question packet returned for `gate_id: rework.spec-change` "
            "names the finding(s) to check; the classification gate reads "
            "the security/license category directly from the named "
            "finding(s)."
        )
        self.assertNotIn(
            "these declared origins are traceability only",
            fake_section.lower(),
        )
        self.assertNotIn(
            "the orchestrator's own bound set for this dispatch",
            fake_section.lower(),
        )

    def test_non_vacuity_transition_section_actually_found(self):
        section = self._transition_section()
        self.assertTrue(section.strip())
        self.assertIn("Specification-change transition", self.text)


if __name__ == "__main__":
    unittest.main()
