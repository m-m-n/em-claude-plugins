"""Tests for task0001 of rework-docs-only-task-routing: the docs-only
correction route in `em-workflow/references/rework-task-synthesis.md`.

Covers task0001 Acceptance Criteria
(feature-docs/rework-docs-only-task-routing/tasks/task0001.md):

- AC-1: Section 9 holds `### Docs-only correction route` after the whole
  `### Wording-correction route` subsection and before
  `## 10. Workflow state transition`; the scope is stated (the
  Wording-correction route is ineligible; the change is resolved by
  VERIFICATION.md, IMPLEMENTATION.md, existing `tasks/*.md` and requirement
  test references only); a change needing SPEC.md or REQUIREMENTS.md goes to
  the SPEC-change transition. The Section 9 table gains the matching
  conditions.
- AC-2: the decision order is stated; the Wording-correction route's Guard and
  Ordering name the docs-only route as the next step while keeping their
  pinned strings; the route's introductory paragraph, Applies to, Eligibility
  block and Outcome text are byte-identical to the base revision.
- AC-3: a docs-only round creates no task, the rework-planner corrects the
  documents per the cited contract, requirement test references change
  through the cited tests replacement, only the origin step returns to
  `pending`, and a sentence of its own states that `implement` does not
  return to `pending`; Invariant 1's text is unchanged.
- AC-4: the mixed-round split is stated; `payload.doc_corrections` is cited
  without restating its shape.
- AC-5 (TM-7): every change the route makes keeps the changed document
  consistent with SPEC.md and REQUIREMENTS.md.
- AC-6: Section 7 states the feature-docs files rule; Section 12 lists the
  files rule, the empty-entries rule and the rename-aware coverage rule.
- AC-7: 13 numbered sections in base order, no `## 14.`, exactly 11
  invariants, and no classification-gate verdict literal between
  `### Wording-correction route` and `## 10.`; this module imports only
  standard-library modules.

Every assertion reads only `em-workflow/references/rework-task-synthesis.md`
(and this module's own source for the import check). Wording that may wrap is
compared whitespace-normalized; the byte-identity pins of AC-2 and the
Invariant 1 pin of AC-3 compare raw text so a reflow is caught.
"""

import ast
import hashlib
import re
import sys
import unittest
from pathlib import Path

THIS_FILE = Path(__file__).resolve()
REPO_ROOT = THIS_FILE.parent.parent
SSOT_PATH = REPO_ROOT / "em-workflow" / "references" / "rework-task-synthesis.md"

SECTION_7_HEADING = "## 7. Metadata derivation"
SECTION_8_HEADING = "## 8. Verification coverage rules"
SECTION_9_HEADING = "## 9. Related document updates"
WORDING_HEADING = "### Wording-correction route"
DOCS_ONLY_HEADING = "### Docs-only correction route"
SECTION_10_HEADING = "## 10. Workflow state transition"
SECTION_11_HEADING = "## 11. Invariants"
SECTION_12_HEADING = "## 12. Validation"
SECTION_13_HEADING = "## 13. Execution adapter"

# The thirteen numbered sections of the base revision, in order.
SECTION_HEADINGS = [
    "## 1. Purpose",
    "## 2. Applicable modes",
    "## 3. Inputs",
    "## 4. Grouping rules",
    "## 5. Task ID allocation",
    "## 6. Task plan requirements",
    "## 7. Metadata derivation",
    "## 8. Verification coverage rules",
    "## 9. Related document updates",
    "## 10. Workflow state transition",
    "## 11. Invariants",
    "## 12. Validation",
    "## 13. Execution adapter",
]

# Labels of the Wording-correction route; the new subsection must not reuse
# them (the Wording-correction route's own test module extracts its blocks by
# the first occurrence of these labels).
WORDING_ROUTE_LABELS = (
    "**Eligibility",
    "**Outcome when eligible**",
    "**Guard**",
    "**Ordering**",
)

# Labels of the new subsection.
LABEL_SCOPE = "**Scope**"
LABEL_ORDER = "**Decision order**"
LABEL_RESULT = "**Result of a docs-only round**"
LABEL_MIXED = "**Mixed round**"
LABEL_DECLARATION = "**Declaration**"
LABEL_CONSISTENCY = "**Consistency with the specification**"
NEW_LABELS = (
    LABEL_SCOPE,
    LABEL_ORDER,
    LABEL_RESULT,
    LABEL_MIXED,
    LABEL_DECLARATION,
    LABEL_CONSISTENCY,
)

# Classification-gate verdict literals owned by references/question-resolution.md.
GATE_VERDICTS = ("goal_not_met", "spec_gap", "not_applicable")

# --- Literal text of the base revision (byte-identity pins, AC-2 / AC-3) ---

BASE_WORDING_INTRO = (
    "Before a needed change to `IMPLEMENTATION.md` or `VERIFICATION.md` is routed\n"
    "to rework-task synthesis above or to the SPEC-change transition (Section\n"
    "10), route selection checks first whether it qualifies for this\n"
    "independent route.\n"
)

BASE_WORDING_APPLIES_TO = (
    "**Applies to**: a change confined to the wording of the two create-plan-owned\n"
    "documents — `IMPLEMENTATION.md` and `VERIFICATION.md`.\n"
)

BASE_WORDING_ELIGIBILITY = (
    "**Eligibility (all three, conjunctive — every condition below must hold)**:\n"
    "\n"
    "1. No planner re-entry is needed.\n"
    "2. No plan or task metadata changes: the task set, `files`, `skills`,\n"
    "   `domains`, `complexity`, or plan paths.\n"
    "3. No requirement metadata changes: requirement statements, IDs, `status`,\n"
    "   or the task/test mapping.\n"
)

BASE_WORDING_OUTCOME = (
    "**Outcome when eligible**: the correction is applied through this section's\n"
    "document-update channel with no task synthesized, `create-plan` is NOT set\n"
    "to `needs_update`, and no workflow patch touching planning is produced.\n"
)

BASE_INVARIANT_1 = (
    "1. For a rework-derived transition (Section 10), before `implement`\n"
    "   returns to `pending`, at least one new rework task is registered in\n"
    "   workflow.yaml. The develop skill's own batch infra auto-resume\n"
    "   (`skills/develop/SKILL.md`, the auto-resume block) also returns\n"
    "   `implement` to `pending`, but is not a rework-derived transition and\n"
    "   registers no task; this invariant does not govern it — its precondition\n"
    "   is `references/implement-phase.md`'s Step I.0 (cited, not restated\n"
    "   here).\n"
)

# SHA-256 of the whole Section 11 block (heading through the line before
# `## 12. Validation`) of the base revision: the eleven invariants keep their
# text byte for byte.
BASE_SECTION_11_SHA256 = (
    "b051003f0dae9883889934d4a8dae52552ccebc53e9340bce4fe349f9856e857"
)

BASE_SECTION_2_STATEMENT = (
    "Task synthesis rules (Sections 4-9, 11) are IDENTICAL across all four routes."
)

# The six Section 12 bullets of the base revision, whitespace-normalized.
BASE_SECTION_12_BULLETS = [
    "- Every synthesized task appears as a key in `rework_index`.",
    "- Every ID listed in a task's `covered_by_existing` exists in the input's "
    "`verification_index`.",
    "- Every ID listed in a task's `new_scenarios` exists in the VERIFICATION.md "
    "diff the synthesis produced.",
    "- When `new_scenarios` is non-empty, the same IDs also appear in the "
    "`requirements_patch`'s `tests_append`.",
    "- No task has BOTH `covered_by_existing` and `new_scenarios` empty "
    "(Section 8).",
    "- A `new_scenarios` claim made while no `VERIFICATION.md` exists in the "
    "current feature directory is rejected outright, fail-closed, distinctly "
    "from a claim rejected merely because no baseline directory was supplied "
    "(Section 8a).",
]


def _read(path):
    if not path.is_file():
        raise AssertionError(f"expected file to exist: {path}")
    return path.read_text(encoding="utf-8")


def _norm(text):
    return re.sub(r"\s+", " ", text).strip()


def _slice(text, start_marker, end_marker):
    start = text.find(start_marker)
    if start == -1:
        raise AssertionError(f"missing marker: {start_marker!r}")
    end = text.find(end_marker, start + len(start_marker))
    if end == -1:
        raise AssertionError(f"missing marker after {start_marker!r}: {end_marker!r}")
    return text[start:end]


def _docs_only_subsection(text):
    return _slice(text, DOCS_ONLY_HEADING, SECTION_10_HEADING)


def _wording_through_section_10(text):
    return _slice(text, WORDING_HEADING, SECTION_10_HEADING)


def _labelled_paragraph(block, label):
    """Whitespace-normalized text of the paragraph that starts with `label`
    (up to the next blank line)."""
    start = block.find(label)
    if start == -1:
        raise AssertionError(f"missing label: {label!r}")
    end = block.find("\n\n", start)
    return _norm(block[start : end if end != -1 else None])


def _bullets(block):
    """Whitespace-normalized bullets (`- ` lines plus indented continuation
    lines) of a block."""
    bullets = []
    for line in block.splitlines():
        if line.startswith("- "):
            bullets.append(line)
        elif bullets and line.startswith("  "):
            bullets[-1] += " " + line.strip()
    return [_norm(b) for b in bullets]


def _table_rows(block):
    rows = []
    for line in block.splitlines():
        stripped = line.strip()
        if stripped.startswith("|") and not re.fullmatch(r"[|\-\s]+", stripped):
            rows.append([c.strip() for c in stripped.strip("|").split("|")])
    return rows


IMPLEMENT_SENTENCE_RE = re.compile(
    r"^[^.]*\bdoes not return `implement` to `pending`[^.]*\.$"
)


def _sentences(normalized_paragraph):
    return re.split(r"(?<=\.)\s+", normalized_paragraph)


def _has_standalone_implement_sentence(normalized_paragraph):
    """True when the paragraph holds a sentence of its own that says the route
    does not return `implement` to `pending` (and says nothing about the
    origin step in that same sentence)."""
    for sentence in _sentences(normalized_paragraph):
        if IMPLEMENT_SENTENCE_RE.match(sentence) and "origin step" not in sentence:
            return True
    return False


def _first_index_in_order(text, needles):
    """Indices of `needles` in `text`, each searched after the previous hit;
    raises ValueError when the order does not hold."""
    indices = []
    cursor = 0
    for needle in needles:
        idx = text.index(needle, cursor)
        indices.append(idx)
        cursor = idx + len(needle)
    return indices


class _DocTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(SSOT_PATH)

    @property
    def docs_only(self):
        return _docs_only_subsection(self.text)


class TestDocsOnlySubsectionPlacementAndScope(_DocTestCase):
    """AC-1."""

    def test_heading_present_exactly_once(self):
        self.assertEqual(self.text.count(DOCS_ONLY_HEADING + "\n"), 1)
        self.assertEqual(self.text.count(DOCS_ONLY_HEADING), 1)

    def test_heading_follows_the_whole_wording_route_and_precedes_section_10(self):
        wording_ordering = self.text.find("**Ordering**")
        docs_only = self.text.find(DOCS_ONLY_HEADING)
        section_10 = self.text.find(SECTION_10_HEADING)
        self.assertNotEqual(docs_only, -1, "missing heading")
        self.assertLess(self.text.index(WORDING_HEADING), docs_only)
        self.assertLess(wording_ordering, docs_only)
        self.assertLess(docs_only, section_10)

    def test_heading_sits_inside_section_9(self):
        section_9 = _slice(self.text, SECTION_9_HEADING, SECTION_10_HEADING)
        self.assertIn(DOCS_ONLY_HEADING, section_9)

    def test_new_subsection_uses_its_own_labels_not_the_wording_routes(self):
        for label in NEW_LABELS:
            with self.subTest(label=label):
                self.assertIn(label, self.docs_only)
        for label in WORDING_ROUTE_LABELS:
            with self.subTest(wording_label=label):
                self.assertNotIn(label, self.docs_only)

    def test_scope_names_ineligibility_and_the_four_resolution_targets(self):
        scope = _labelled_paragraph(self.docs_only, LABEL_SCOPE)
        self.assertIn("fails the Wording-correction route's eligibility", scope)
        self.assertIn("`VERIFICATION.md`", scope)
        self.assertIn("`IMPLEMENTATION.md`", scope)
        self.assertIn("existing `tasks/*.md`", scope)
        self.assertIn("requirement test references", scope)
        self.assertIn("`workflow.yaml`", scope)
        self.assertIn("is resolved by changing only", scope)

    def test_scope_sends_spec_or_requirements_changes_to_the_spec_change_transition(
        self,
    ):
        scope = _labelled_paragraph(self.docs_only, LABEL_SCOPE)
        self.assertRegex(
            scope,
            r"needs `SPEC\.md` or `REQUIREMENTS\.md` stays with the SPEC-change "
            r"transition \(Section 10\)",
        )

    def test_scope_matcher_would_reject_a_scope_without_the_spec_change_rule(self):
        # Non-vacuity proof for the matcher above.
        sample = (
            "**Scope**: a needed change that fails the Wording-correction "
            "route's eligibility and is resolved by changing only "
            "`VERIFICATION.md`."
        )
        self.assertNotRegex(
            sample, r"stays with the SPEC-change transition \(Section 10\)"
        )

    def test_section_9_table_adds_the_docs_only_route_to_the_two_planning_documents(
        self,
    ):
        table = _slice(self.text, SECTION_9_HEADING, WORDING_HEADING)
        rows = {row[0]: row for row in _table_rows(table)}
        verification = rows["`VERIFICATION.md`"][1]
        implementation = rows["`IMPLEMENTATION.md`"][1]
        self.assertIn("Per Section 8's coverage rules", verification)
        self.assertIn("the docs-only correction route below", verification)
        self.assertIn("NEW shared contract", implementation)
        self.assertIn("`payload.shared_contract_rationale`", implementation)
        self.assertIn("the docs-only correction route below", implementation)

    def test_section_9_table_has_a_row_for_existing_task_plans(self):
        table = _slice(self.text, SECTION_9_HEADING, WORDING_HEADING)
        rows = _table_rows(table)
        existing = [r for r in rows if "tasks/*.md" in r[0]]
        self.assertEqual(len(existing), 1)
        self.assertIn("Existing", existing[0][0])
        self.assertRegex(existing[0][1], r"(?i)only through the docs-only correction route")

    def test_section_9_table_keeps_the_new_task_plan_and_spec_rows(self):
        table = _slice(self.text, SECTION_9_HEADING, WORDING_HEADING)
        rows = {row[0]: row for row in _table_rows(table)}
        self.assertEqual(
            rows["`tasks/taskNNNN.md`"][1],
            "Always created, one per synthesized task",
        )
        self.assertTrue(
            rows["`SPEC.md` / `REQUIREMENTS.md`"][1].startswith(
                "Never updated by this synthesis"
            )
        )

    def test_section_9_table_matcher_would_reject_an_unchanged_row(self):
        # Non-vacuity proof: the base wording of the VERIFICATION.md row lacks
        # the docs-only route and must fail the check above.
        base_row = "| `VERIFICATION.md` | Per Section 8's coverage rules |"
        rows = _table_rows(base_row)
        self.assertNotIn("the docs-only correction route below", rows[0][1])


class TestDecisionOrderAndWordingRouteEdits(_DocTestCase):
    """AC-2."""

    ORDER_SENTENCE = (
        "Wording-correction route -> Docs-only correction route -> "
        "rework-task synthesis / SPEC-change transition"
    )

    def test_decision_order_is_stated_in_the_new_subsection(self):
        order = _labelled_paragraph(self.docs_only, LABEL_ORDER)
        self.assertIn(self.ORDER_SENTENCE, order)

    def test_decision_order_names_the_routes_in_the_stated_order(self):
        order = _labelled_paragraph(self.docs_only, LABEL_ORDER)
        indices = _first_index_in_order(
            order,
            [
                "Wording-correction route",
                "Docs-only correction route",
                "rework-task synthesis",
                "SPEC-change transition",
            ],
        )
        self.assertEqual(indices, sorted(indices))

    def test_order_matcher_would_reject_a_swapped_order(self):
        # Non-vacuity proof for the order check above.
        swapped = (
            "Docs-only correction route -> Wording-correction route -> "
            "rework-task synthesis / SPEC-change transition"
        )
        with self.assertRaises(ValueError):
            _first_index_in_order(
                swapped,
                [
                    "Wording-correction route",
                    "Docs-only correction route",
                    "rework-task synthesis",
                    "SPEC-change transition",
                ],
            )

    def test_guard_names_the_docs_only_route_and_keeps_its_pinned_strings(self):
        wording = _wording_through_section_10(self.text)
        guard = _slice(wording, "**Guard**", "**Ordering**")
        self.assertIn("Docs-only correction route", _norm(guard))
        for pinned in (
            "rework-task synthesis",
            "SPEC-change transition",
            "concrete",
            "artefact",
        ):
            with self.subTest(pinned=pinned):
                self.assertIn(pinned, guard)

    def test_ordering_names_the_docs_only_route_and_keeps_the_gate_citation(self):
        wording = _wording_through_section_10(self.text)
        ordering_norm = _labelled_paragraph(wording, "**Ordering**")
        self.assertIn("Docs-only correction route", ordering_norm)
        self.assertIn("`references/question-resolution.md`", ordering_norm)
        self.assertIn("classification gate", ordering_norm)

    def test_ordering_matcher_would_reject_the_base_ordering(self):
        # Non-vacuity proof: the base Ordering does not name the new route.
        base_ordering = (
            "**Ordering**: this route is checked first; only a change that "
            "fails it can reach the SPEC-change transition and, through it, "
            "the classification gate (`references/question-resolution.md`)."
        )
        self.assertNotIn("Docs-only correction route", base_ordering)

    def test_introductory_paragraph_is_byte_identical(self):
        self.assertIn(
            WORDING_HEADING + "\n\n" + BASE_WORDING_INTRO + "\n**Applies to**",
            self.text,
        )

    def test_applies_to_is_byte_identical(self):
        self.assertIn(BASE_WORDING_APPLIES_TO + "\n", self.text)

    def test_eligibility_block_is_byte_identical(self):
        self.assertIn(BASE_WORDING_ELIGIBILITY + "\n", self.text)

    def test_eligibility_block_keeps_three_numbered_conditions_and_conjunctive(self):
        wording = _wording_through_section_10(self.text)
        block = _slice(wording, "**Eligibility", "**Outcome when eligible**")
        self.assertEqual(re.findall(r"^(\d+)\. ", block, re.MULTILINE), ["1", "2", "3"])
        self.assertIn("conjunctive", block)

    def test_outcome_is_byte_identical(self):
        self.assertIn(BASE_WORDING_OUTCOME + "\n", self.text)

    def test_byte_identity_matcher_would_catch_a_reflow(self):
        # Non-vacuity proof: the same words wrapped differently are not equal.
        reflowed = BASE_WORDING_OUTCOME.replace("section's\n", "section's ")
        self.assertNotEqual(reflowed, BASE_WORDING_OUTCOME)
        self.assertNotIn(reflowed, self.text)


class TestDocsOnlyRoundResult(_DocTestCase):
    """AC-3."""

    @property
    def result(self):
        return _labelled_paragraph(self.docs_only, LABEL_RESULT)

    def test_states_that_no_task_is_synthesized(self):
        self.assertRegex(self.result, r"no task is synthesized")

    def test_rework_planner_corrects_the_documents_per_the_cited_contract(self):
        self.assertIn("The rework-planner corrects the documents itself", self.result)
        self.assertIn("`references/contracts/rework-planner-contract.md`", self.result)

    def test_requirement_test_references_change_through_the_cited_tests_replacement(
        self,
    ):
        self.assertRegex(
            self.result,
            r"[Rr]equirement test references change through the tests "
            r"replacement of `references/workflow-patch\.md`",
        )

    def test_only_the_origin_step_returns_to_pending(self):
        self.assertIn("returns only the origin step to `pending`", self.result)
        self.assertIn("`verify` for verify-sourced", self.result)
        self.assertIn("`review` for review-sourced", self.result)

    def test_implement_not_returning_to_pending_has_a_sentence_of_its_own(self):
        self.assertTrue(_has_standalone_implement_sentence(self.result))

    def test_matcher_fails_on_a_subsection_that_only_says_origin_step(self):
        # Non-vacuity proof: a result paragraph that only says the origin step
        # returns, and never says `implement` stays put, must fail.
        only_origin = (
            "**Result of a docs-only round**: no task is synthesized. The "
            "patch returns only the origin step to `pending`: `verify` for "
            "verify-sourced rework, `review` for review-sourced rework."
        )
        self.assertFalse(_has_standalone_implement_sentence(_norm(only_origin)))

    def test_matcher_fails_when_the_implement_clause_shares_the_origin_sentence(self):
        # Non-vacuity proof: "a sentence of its own" is enforced.
        merged = (
            "The patch returns only the origin step to `pending` and does not "
            "return `implement` to `pending`."
        )
        self.assertFalse(_has_standalone_implement_sentence(merged))

    def test_matcher_accepts_the_standalone_sentence(self):
        sample = (
            "The patch returns only the origin step to `pending`. This route "
            "does not return `implement` to `pending`."
        )
        self.assertTrue(_has_standalone_implement_sentence(sample))

    def test_invariant_1_is_not_reworded(self):
        self.assertIn(BASE_INVARIANT_1, self.text)

    def test_invariant_1_is_stated_as_not_engaged_by_this_route(self):
        self.assertRegex(
            self.result,
            r"Invariant 1 \(Section 11\)[^.]*is therefore not engaged by this route",
        )

    def test_all_eleven_invariants_keep_their_text(self):
        section_11 = _slice(self.text, SECTION_11_HEADING, SECTION_12_HEADING)
        digest = hashlib.sha256(section_11.encode("utf-8")).hexdigest()
        self.assertEqual(digest, BASE_SECTION_11_SHA256)

    def test_section_11_digest_would_detect_an_edited_invariant(self):
        # Non-vacuity proof for the digest pin above.
        section_11 = _slice(self.text, SECTION_11_HEADING, SECTION_12_HEADING)
        edited = section_11.replace("Every newly synthesized", "Each newly synthesized")
        self.assertNotEqual(edited, section_11)
        self.assertNotEqual(
            hashlib.sha256(edited.encode("utf-8")).hexdigest(),
            BASE_SECTION_11_SHA256,
        )


class TestMixedRoundAndDeclaration(_DocTestCase):
    """AC-4."""

    def test_mixed_round_splits_docs_only_and_code_items(self):
        mixed = _labelled_paragraph(self.docs_only, LABEL_MIXED)
        self.assertIn("Docs-only items are corrected directly by the rework-planner", mixed)
        self.assertIn("code items become tasks under the grouping rules of Section 4", mixed)

    def test_mixed_round_with_a_task_returns_implement_and_the_origin_step(self):
        mixed = _labelled_paragraph(self.docs_only, LABEL_MIXED)
        self.assertRegex(
            mixed,
            r"A round with at least one task returns `implement` and the origin "
            r"step to `pending`, as before",
        )

    def test_origin_step_only_result_is_limited_to_docs_only_rounds(self):
        mixed = _labelled_paragraph(self.docs_only, LABEL_MIXED)
        self.assertRegex(
            mixed,
            r"origin-step-only result[^.]*is limited to docs-only rounds",
        )

    def test_mixed_matcher_would_reject_a_paragraph_without_the_limit(self):
        # Non-vacuity proof for the limit check above.
        sample = (
            "**Mixed round**: docs-only items are corrected directly; code "
            "items become tasks."
        )
        self.assertNotRegex(sample, r"is limited to docs-only rounds")

    def test_declaration_cites_payload_doc_corrections_and_the_contract(self):
        declaration = _labelled_paragraph(self.docs_only, LABEL_DECLARATION)
        self.assertIn("`payload.doc_corrections`", declaration)
        self.assertIn("`references/contracts/rework-planner-contract.md`", declaration)
        self.assertIn("(cited, not restated)", declaration)

    def test_declaration_covers_every_correction_through_this_route(self):
        declaration = _labelled_paragraph(self.docs_only, LABEL_DECLARATION)
        self.assertRegex(declaration, r"[Ee]very correction made through this route")

    def test_declaration_does_not_restate_the_entry_shape(self):
        for field in (
            "scenario_renames",
            "origin_kind",
            "origin_id",
            "`documents`",
            "`from`",
            "`to`",
        ):
            with self.subTest(field=field):
                self.assertNotIn(field, self.docs_only)

    def test_shape_leak_would_be_detected(self):
        # Non-vacuity proof for the absence check above.
        leaking = "`payload.doc_corrections` holds `scenario_renames` pairs."
        self.assertIn("scenario_renames", leaking)


class TestConsistencyWithTheSpecification(_DocTestCase):
    """AC-5 (TM-7)."""

    @property
    def consistency(self):
        return _labelled_paragraph(self.docs_only, LABEL_CONSISTENCY)

    def test_every_change_stays_consistent_with_spec_and_requirements(self):
        self.assertRegex(
            self.consistency,
            r"[Ee]very change this route makes keeps the changed document "
            r"consistent with `SPEC\.md` and `REQUIREMENTS\.md`",
        )

    def test_the_route_never_changes_spec_or_requirements(self):
        self.assertRegex(
            self.consistency, r"which this route never changes"
        )

    def test_a_weakening_correction_is_not_a_docs_only_correction(self):
        self.assertRegex(
            self.consistency,
            r"scenario or acceptance criterion check less than `SPEC\.md` or "
            r"`REQUIREMENTS\.md` require is not a docs-only correction",
        )

    def test_a_weakening_correction_continues_to_synthesis_or_spec_change(self):
        self.assertRegex(
            self.consistency,
            r"continues to rework-task synthesis or the SPEC-change transition",
        )

    def test_matcher_would_reject_a_paragraph_without_the_weakening_rule(self):
        # Non-vacuity proof.
        sample = (
            "**Consistency with the specification**: every change this route "
            "makes keeps the changed document consistent with `SPEC.md`."
        )
        self.assertNotRegex(sample, r"is not a docs-only correction")


class TestFeatureDocsFilesRuleAndSection12(_DocTestCase):
    """AC-6."""

    def setUp(self):
        self.section_7 = _norm(_slice(self.text, SECTION_7_HEADING, SECTION_8_HEADING))
        self.section_12 = _slice(self.text, SECTION_12_HEADING, SECTION_13_HEADING)
        self.bullets = _bullets(self.section_12)

    def test_section_7_states_the_feature_docs_files_rule(self):
        self.assertRegex(
            self.section_7,
            r"(?i)a rework-synthesized task's `files` contain no path whose "
            r"first path segment is exactly `feature-docs`",
        )

    def test_section_7_states_the_segment_normalization(self):
        self.assertIn("`\\` treated as `/`", self.section_7)
        self.assertIn("empty and `.` segments dropped", self.section_7)

    def test_section_7_limits_the_rule_to_append_rework_entries(self):
        self.assertIn("`append_rework`", self.section_7)

    def test_section_7_keeps_its_base_sentences(self):
        self.assertIn(
            "The `files` rule of the section cited in Section 6 applies on top "
            "of the meaning-derived `files`.",
            self.section_7,
        )

    def test_section_7_matcher_would_reject_a_loose_rule(self):
        # Non-vacuity proof: a rule that names the directory without the exact
        # first-segment wording fails the check above.
        loose = "A task's `files` should avoid feature-docs paths."
        self.assertNotIn("first path segment is exactly `feature-docs`", loose)

    def test_section_12_lists_the_files_rule(self):
        matching = [b for b in self.bullets if "first path segment" in b]
        self.assertEqual(len(matching), 1)
        bullet = matching[0]
        self.assertIn("exactly `feature-docs`", bullet)
        self.assertIn("`files`", bullet)
        self.assertIn("`append_rework`", bullet)

    def test_section_12_lists_the_empty_entries_rule(self):
        matching = [b for b in self.bullets if "never returns `implement` to `pending`" in b]
        self.assertEqual(len(matching), 1)
        bullet = matching[0]
        self.assertIn("`append_rework`", bullet)
        self.assertIn("`tasks_patch.entries`", bullet)
        self.assertIn("absent or empty", bullet)

    def test_section_12_lists_the_rename_aware_coverage_rule(self):
        matching = [b for b in self.bullets if "scenario_renames" in b]
        self.assertEqual(len(matching), 1)
        bullet = matching[0]
        for token in (
            "`covered_by_existing`",
            "`verification_index`",
            "`to`",
            "`from`",
            "`rework-index`",
        ):
            with self.subTest(token=token):
                self.assertIn(token, bullet)

    def test_section_12_keeps_its_six_base_bullets_unchanged(self):
        for base in BASE_SECTION_12_BULLETS:
            with self.subTest(bullet=base[:50]):
                self.assertIn(base, self.bullets)

    def test_section_12_has_exactly_three_additional_bullets(self):
        self.assertEqual(len(self.bullets), len(BASE_SECTION_12_BULLETS) + 3)

    def test_section_12_matcher_would_reject_the_base_bullet_list(self):
        # Non-vacuity proof: the six base bullets alone hold none of the three
        # new rules.
        base_block = "\n".join(BASE_SECTION_12_BULLETS)
        bullets = _bullets(base_block)
        self.assertFalse([b for b in bullets if "first path segment" in b])
        self.assertFalse([b for b in bullets if "scenario_renames" in b])


class TestPreservedStructure(_DocTestCase):
    """AC-7."""

    def test_thirteen_numbered_sections_in_base_order(self):
        headings = re.findall(r"^## \d+\. .*$", self.text, re.MULTILINE)
        self.assertEqual(headings, SECTION_HEADINGS)

    def test_no_fourteenth_section(self):
        self.assertNotIn("## 14.", self.text)

    def test_exactly_eleven_invariants(self):
        section = _slice(self.text, SECTION_11_HEADING, SECTION_12_HEADING)
        self.assertEqual(len(re.findall(r"^\d+\.", section, re.MULTILINE)), 11)

    def test_section_2_keeps_the_statement_that_puts_the_subsection_on_all_routes(self):
        self.assertIn(BASE_SECTION_2_STATEMENT, self.text)
        self.assertIn("Sections 4-9, 11", self.text)

    def test_no_classification_gate_verdict_between_wording_route_and_section_10(self):
        block = _wording_through_section_10(self.text)
        for verdict in GATE_VERDICTS:
            with self.subTest(verdict=verdict):
                self.assertNotIn(verdict, block)

    def test_verdict_leak_would_be_detected(self):
        # Non-vacuity proof for the absence check above.
        self.assertIn("goal_not_met", "verdict: goal_not_met")

    def test_wording_route_blocks_still_extract_from_the_first_label_occurrence(self):
        # The Wording-correction route's own test module extracts by the first
        # occurrence of these labels inside the range this subsection joins.
        block = _wording_through_section_10(self.text)
        eligibility = block.index("**Eligibility")
        outcome = block.index("**Outcome when eligible**")
        guard = block.index("**Guard**")
        ordering = block.index("**Ordering**")
        docs_only = block.find(DOCS_ONLY_HEADING)
        self.assertNotEqual(docs_only, -1, "missing heading")
        self.assertLess(eligibility, outcome)
        self.assertLess(guard, ordering)
        self.assertLess(ordering, docs_only)
        for label in WORDING_ROUTE_LABELS:
            with self.subTest(label=label):
                self.assertEqual(block.count(label), 1)


class TestModuleHygiene(unittest.TestCase):
    """AC-7: standard library only; reads only the one document."""

    def test_module_imports_only_the_standard_library(self):
        tree = ast.parse(_read(THIS_FILE))
        modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                modules.add((node.module or "").split(".")[0])
        self.assertTrue(modules)
        self.assertLessEqual(modules, set(sys.stdlib_module_names))

    def test_module_reads_only_the_rework_task_synthesis_document(self):
        self.assertEqual(SSOT_PATH.name, "rework-task-synthesis.md")
        self.assertTrue(SSOT_PATH.is_file())


if __name__ == "__main__":
    unittest.main()
