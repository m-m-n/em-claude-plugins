"""Tests for task0002 of spec-change-rework-reentry: Invariant 1 of
`em-workflow/references/rework-task-synthesis.md` does not govern the
SPEC-change transition (recurrence tests for FR7 (d)).

Pins this task's Acceptance Criteria over the one document it owns, and only
over its Section 11 (Section 10 belongs to another task and is not read here):

- AC-1: Invariant 1 states that it does not govern the SPEC-change transition
  of Section 10, that this transition returns `implement` to `pending` while
  registering no task (Invariant 9), and that its re-entry precondition is
  `references/implement-phase.md`'s Step I.0, cited and not restated.
- AC-2: Invariant 1 names none of the `spec_change` record's fields
  `recorded_at_commit`, `replan_authorized`, `consumed` and
  `completed_at_commit`.
- AC-3: Section 11 holds exactly eleven numbered invariants; Invariants 2 to
  11 and every pre-existing line of Invariant 1 are byte-identical to the base
  revision (held below as verbatim constants).
- AC-4: every matcher is backed by a negative proof, and the pre-change
  Invariant 1 (verbatim constant) is rejected by the AC-1 matcher.
- AC-5: the document holds no Notion URL and no absolute path under `/home/`.

Matching of the AC-1 statement is whitespace-normalized; the byte-identity
checks of AC-3 compare raw text so a reflow is caught. Standard library only.
"""

import hashlib
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SSOT_PATH = REPO_ROOT / "em-workflow" / "references" / "rework-task-synthesis.md"

INVARIANTS_HEADING = "## 11. Invariants"
VALIDATION_HEADING = "## 12. Validation"

# --- Literal text of the base revision (verbatim constants, AC-3 / AC-4) ---

PRE_CHANGE_INVARIANT_1 = """\
1. For a rework-derived transition (Section 10), before `implement`
   returns to `pending`, at least one new rework task is registered in
   workflow.yaml. The develop skill's own batch infra auto-resume
   (`skills/develop/SKILL.md`, the auto-resume block) also returns
   `implement` to `pending`, but is not a rework-derived transition and
   registers no task; this invariant does not govern it — its precondition
   is `references/implement-phase.md`'s Step I.0 (cited, not restated
   here).
"""

PRE_CHANGE_INVARIANTS_2_TO_11 = """\
2. Every newly synthesized task's `status` is `pending`.
3. Every rework task plan states objective, test-translatable Acceptance
   Criteria.
4. `files` / `skills` / `domains` / `requirements` are derived from the
   finding's or failed item's meaning; file-overlap inheritance from an
   existing task alone is not sufficient.
5. `workflow[implement].base_commit` is never changed by a rework patch; it
   is always listed in the patch's `preserve` set.
6. Review-sourced tasks carry the finding's `stable_id`, verify-sourced
   tasks carry the failed item's ID, as `provenance`. Named as a pair, this
   is `origin_kind` (`review` | `verify`) and `origin_id`: for
   `origin_kind: review`, `origin_id` is the finding's `stable_id`; for
   `origin_kind: verify`, `origin_id` is the failed item's ID. This
   document is the pair's one definition; every consumer of a
   rework-derived question's origin — `references/question-resolution.md`
   for what origin verification matches against and what set the
   security / license / irreversible check runs over,
   `references/phase-state.md` for what the `spec_change` record stores —
   cites this pair rather than defining its own.
7. Interactive and batch never differ in task synthesis rules; they differ
   only in how a rework round is selected and in the retry/round cap.
8. Patch application and every workflow.yaml write are always performed by
   the orchestrator, never by the synthesizing worker itself.
9. When rework requires a SPEC.md change, no task is created — the
   SPEC-change transition (Section 10) applies instead.
10. Every rework task declares its verification coverage via `rework_index`
    (Section 8).
11. Verify-sourced rework never sets `review.needs_rework` — that field is
    review-specific, and the verify-sourced transition begins directly at
    dispatch (Section 10).

"""

# SHA-256 of the whole base-revision Section 11 block (heading through the
# line before `## 12. Validation`); the two constants above reassemble to it.
PRE_CHANGE_SECTION_11_SHA256 = (
    "b051003f0dae9883889934d4a8dae52552ccebc53e9340bce4fe349f9856e857"
)

# --- AC-1: the statement Invariant 1 gains --------------------------------

SPEC_CHANGE_ANCHOR = "SPEC-change transition"
ANCHOR_ELEMENT = "names the SPEC-change transition"

# (name, pattern over the whitespace-normalized carve-out). The carve-out is
# the text of Invariant 1 from the first mention of the SPEC-change
# transition to the end of the invariant.
CARVE_OUT_ELEMENTS = (
    ("states the exclusion", r"does not govern"),
    ("names Section 10", r"Section 10"),
    ("states the return of implement to pending", r"returns `implement` to `pending`"),
    ("states that no task is registered", r"registers no task"),
    ("cites Invariant 9", r"Invariant 9"),
    (
        "cites Step I.0 of implement-phase.md",
        r"`references/implement-phase\.md`'s Step I\.0",
    ),
    ("states cited, not restated", r"cited, not restated"),
)

# Synthetic wording that satisfies every element: it is NOT the document's
# wording, so a pass proves the matcher does not pin the document's text.
SYNTHETIC_CARVE_OUT = (
    "   The SPEC-change transition of Section 10 also returns `implement` to\n"
    "   `pending` but registers no task (Invariant 9); this invariant does not\n"
    "   govern it. Its re-entry precondition is\n"
    "   `references/implement-phase.md`'s Step I.0 (cited, not restated here).\n"
)

# --- AC-2 ------------------------------------------------------------------

FORBIDDEN_RECORD_TOKENS = (
    "recorded_at_commit",
    "replan_authorized",
    "consumed",
    "completed_at_commit",
)

# --- AC-5 ------------------------------------------------------------------

REDACTION_NEEDLES = ("notion.so", "notion.site", "notion.com", "/home/")


def _read(path):
    if not path.is_file():
        raise AssertionError(f"expected file to exist: {path}")
    return path.read_text(encoding="utf-8")


def _norm(text):
    return re.sub(r"\s+", " ", text).strip()


def _section_11(text):
    start = text.find(INVARIANTS_HEADING)
    if start == -1:
        raise AssertionError(f"missing marker: {INVARIANTS_HEADING!r}")
    end = text.find(VALIDATION_HEADING, start + len(INVARIANTS_HEADING))
    if end == -1:
        raise AssertionError(f"missing marker: {VALIDATION_HEADING!r}")
    return text[start:end]


def _invariant_1(section):
    """Raw text from the line that starts with `1. ` to the line that starts
    with `2. `."""
    match = re.search(r"^1\. .*?(?=^2\. )", section, re.MULTILINE | re.DOTALL)
    if match is None:
        raise AssertionError("Section 11 has no Invariant 1 followed by Invariant 2")
    return match.group(0)


def _invariants_2_to_11(section):
    """Raw text from the line that starts with `2. ` to the end of the
    section."""
    match = re.search(r"^2\. .*\Z", section, re.MULTILINE | re.DOTALL)
    if match is None:
        raise AssertionError("Section 11 has no Invariant 2")
    return match.group(0)


def _count_numbered(section):
    return len(re.findall(r"^\d+\.", section, re.MULTILINE))


def _carve_out(invariant_text):
    normalized = _norm(invariant_text)
    start = normalized.find(SPEC_CHANGE_ANCHOR)
    if start == -1:
        return None
    return normalized[start:]


def _missing_carve_out_elements(invariant_text):
    """Names of the AC-1 elements Invariant 1 lacks; empty when it states the
    carve-out in full."""
    carve_out = _carve_out(invariant_text)
    if carve_out is None:
        return [ANCHOR_ELEMENT] + [name for name, _ in CARVE_OUT_ELEMENTS]
    return [
        name
        for name, pattern in CARVE_OUT_ELEMENTS
        if re.search(pattern, carve_out) is None
    ]


def _forbidden_tokens_in(text):
    lowered = text.lower()
    return [token for token in FORBIDDEN_RECORD_TOKENS if token in lowered]


def _redaction_hits(text):
    lowered = text.lower()
    return [needle for needle in REDACTION_NEEDLES if needle in lowered]


class _DocTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(SSOT_PATH)
        cls.section = _section_11(cls.text)
        cls.invariant_1 = _invariant_1(cls.section)


class TestVerbatimConstants(unittest.TestCase):
    """The base-revision constants are what they claim to be."""

    def test_constants_reassemble_to_the_base_section_11_digest(self):
        base = INVARIANTS_HEADING + "\n\n" + PRE_CHANGE_INVARIANT_1
        base += PRE_CHANGE_INVARIANTS_2_TO_11
        digest = hashlib.sha256(base.encode("utf-8")).hexdigest()
        self.assertEqual(digest, PRE_CHANGE_SECTION_11_SHA256)

    def test_reassembly_digest_would_detect_a_mistyped_constant(self):
        # Non-vacuity proof for the reassembly check above.
        base = INVARIANTS_HEADING + "\n\n" + PRE_CHANGE_INVARIANT_1
        base += PRE_CHANGE_INVARIANTS_2_TO_11
        edited = base.replace("Every newly synthesized", "Each newly synthesized")
        self.assertNotEqual(edited, base)
        self.assertNotEqual(
            hashlib.sha256(edited.encode("utf-8")).hexdigest(),
            PRE_CHANGE_SECTION_11_SHA256,
        )

    def test_pre_change_invariant_1_does_not_mention_the_spec_change_transition(self):
        self.assertNotIn(SPEC_CHANGE_ANCHOR, PRE_CHANGE_INVARIANT_1)


class TestAC1InvariantOneDoesNotGovernTheSpecChangeTransition(_DocTestCase):
    """AC-1."""

    def test_invariant_1_states_the_carve_out(self):
        self.assertEqual(_missing_carve_out_elements(self.invariant_1), [])

    def test_carve_out_is_added_after_the_pre_existing_lines(self):
        # The anchor sits in lines appended after the pre-change text, so the
        # elements above are not satisfied by the auto-resume sentence.
        self.assertTrue(self.invariant_1.startswith(PRE_CHANGE_INVARIANT_1))
        appended = self.invariant_1[len(PRE_CHANGE_INVARIANT_1) :]
        self.assertIn(SPEC_CHANGE_ANCHOR, appended)


class TestAC2InvariantOneNamesNoRecordField(_DocTestCase):
    """AC-2."""

    def test_invariant_1_contains_none_of_the_record_fields(self):
        self.assertEqual(_forbidden_tokens_in(self.invariant_1), [])


class TestAC3PreExistingTextIsByteIdentical(_DocTestCase):
    """AC-3."""

    def test_section_11_has_exactly_eleven_numbered_invariants(self):
        self.assertEqual(_count_numbered(self.section), 11)

    def test_every_pre_existing_line_of_invariant_1_is_kept(self):
        self.assertTrue(self.invariant_1.startswith(PRE_CHANGE_INVARIANT_1))

    def test_invariants_2_to_11_are_byte_identical_to_the_base_revision(self):
        self.assertEqual(_invariants_2_to_11(self.section), PRE_CHANGE_INVARIANTS_2_TO_11)


class TestAC5NoNotionUrlAndNoHomePath(_DocTestCase):
    """AC-5."""

    def test_document_holds_no_notion_url_and_no_home_path(self):
        self.assertEqual(_redaction_hits(self.text), [])


class TestNegativeProofsOfTheAC1Matcher(unittest.TestCase):
    """AC-4: the AC-1 matcher rejects text that lacks the statement."""

    def test_pre_change_invariant_1_is_rejected(self):
        missing = _missing_carve_out_elements(PRE_CHANGE_INVARIANT_1)
        self.assertEqual(
            missing,
            [ANCHOR_ELEMENT] + [name for name, _ in CARVE_OUT_ELEMENTS],
        )

    def test_the_auto_resume_sentence_alone_has_no_carve_out(self):
        # The auto-resume sentence already says "does not govern it",
        # "registers no task" and cites Step I.0; only the SPEC-change
        # transition anchor sets the new statement apart, and the pre-change
        # text has none.
        self.assertIsNone(_carve_out(PRE_CHANGE_INVARIANT_1))
        self.assertIn("does not govern it", _norm(PRE_CHANGE_INVARIANT_1))
        self.assertIn("registers no task", _norm(PRE_CHANGE_INVARIANT_1))

    def test_a_mention_without_the_statement_is_rejected(self):
        # The wording of Invariant 9 names the transition but states none of
        # the carve-out.
        sample = (
            PRE_CHANGE_INVARIANT_1
            + "   When rework requires a SPEC.md change, the SPEC-change\n"
            "   transition applies instead.\n"
        )
        self.assertNotEqual(_missing_carve_out_elements(sample), [])

    def test_synthetic_statement_is_accepted(self):
        # Positive proof: the matcher can pass.
        sample = PRE_CHANGE_INVARIANT_1 + SYNTHETIC_CARVE_OUT
        self.assertEqual(_missing_carve_out_elements(sample), [])

    def test_each_element_is_required_on_its_own(self):
        for name, pattern in CARVE_OUT_ELEMENTS:
            with self.subTest(element=name):
                # The element patterns match whitespace-normalized text, so
                # the element is removed from the normalized synthetic text.
                normalized = _norm(SYNTHETIC_CARVE_OUT)
                broken = re.sub(pattern, "XXX", normalized)
                self.assertNotEqual(broken, normalized)
                sample = PRE_CHANGE_INVARIANT_1 + "   " + broken + "\n"
                self.assertEqual(_missing_carve_out_elements(sample), [name])


class TestNegativeProofsOfTheAC2Matcher(unittest.TestCase):
    """AC-4: the AC-2 matcher flags each forbidden field."""

    def test_clean_text_is_not_flagged(self):
        self.assertEqual(
            _forbidden_tokens_in(PRE_CHANGE_INVARIANT_1 + SYNTHETIC_CARVE_OUT), []
        )

    def test_each_forbidden_field_is_flagged_on_its_own(self):
        for token in FORBIDDEN_RECORD_TOKENS:
            with self.subTest(token=token):
                sample = PRE_CHANGE_INVARIANT_1 + SYNTHETIC_CARVE_OUT + f"   {token}\n"
                self.assertEqual(_forbidden_tokens_in(sample), [token])

    def test_a_capitalized_field_is_flagged(self):
        sample = "1. The record is Consumed once.\n"
        self.assertEqual(_forbidden_tokens_in(sample), ["consumed"])


class TestNegativeProofsOfTheAC3Matchers(unittest.TestCase):
    """AC-4: the AC-3 matchers reject a count change, a reflowed or edited
    pre-existing line, and an edited later invariant."""

    def _base_section(self):
        return INVARIANTS_HEADING + "\n\n" + PRE_CHANGE_INVARIANT_1 + PRE_CHANGE_INVARIANTS_2_TO_11

    def test_base_section_has_eleven_invariants(self):
        # Positive proof for the count matcher.
        self.assertEqual(_count_numbered(self._base_section()), 11)

    def test_a_twelfth_invariant_is_counted(self):
        sample = self._base_section() + "12. A twelfth invariant.\n"
        self.assertEqual(_count_numbered(sample), 12)

    def test_a_missing_invariant_is_counted(self):
        sample = self._base_section().replace(
            "9. When rework requires a SPEC.md change, no task is created — the\n"
            "   SPEC-change transition (Section 10) applies instead.\n",
            "",
        )
        self.assertEqual(_count_numbered(sample), 10)

    def test_a_reflowed_pre_existing_line_breaks_the_prefix_check(self):
        reflowed = PRE_CHANGE_INVARIANT_1.replace(
            "registered in\n   workflow.yaml", "registered in workflow.yaml"
        )
        self.assertNotEqual(reflowed, PRE_CHANGE_INVARIANT_1)
        sample = reflowed + SYNTHETIC_CARVE_OUT
        self.assertFalse(sample.startswith(PRE_CHANGE_INVARIANT_1))

    def test_a_line_inserted_before_the_last_pre_existing_line_breaks_the_prefix_check(
        self,
    ):
        lines = PRE_CHANGE_INVARIANT_1.splitlines(keepends=True)
        sample = "".join(lines[:-1]) + SYNTHETIC_CARVE_OUT + lines[-1]
        self.assertFalse(sample.startswith(PRE_CHANGE_INVARIANT_1))

    def test_appended_lines_keep_the_prefix_check_passing(self):
        # Positive proof for the prefix check.
        sample = PRE_CHANGE_INVARIANT_1 + SYNTHETIC_CARVE_OUT
        self.assertTrue(sample.startswith(PRE_CHANGE_INVARIANT_1))

    def test_an_edited_later_invariant_differs_from_the_pinned_constant(self):
        section = self._base_section().replace("Every newly", "Each newly")
        self.assertNotEqual(section, self._base_section())
        self.assertNotEqual(_invariants_2_to_11(section), PRE_CHANGE_INVARIANTS_2_TO_11)

    def test_a_reflowed_later_invariant_differs_from_the_pinned_constant(self):
        section = self._base_section().replace(
            "Every rework task plan states objective, test-translatable Acceptance\n"
            "   Criteria.",
            "Every rework task plan states objective, test-translatable Acceptance Criteria.",
        )
        self.assertNotEqual(section, self._base_section())
        self.assertNotEqual(_invariants_2_to_11(section), PRE_CHANGE_INVARIANTS_2_TO_11)

    def test_extraction_splits_invariant_1_from_the_later_invariants(self):
        # Positive proof for the two extractors.
        section = self._base_section()
        self.assertEqual(_invariant_1(section), PRE_CHANGE_INVARIANT_1)
        self.assertEqual(_invariants_2_to_11(section), PRE_CHANGE_INVARIANTS_2_TO_11)


class TestNegativeProofsOfTheAC5Matcher(unittest.TestCase):
    """AC-4: the AC-5 matcher flags each kind of leak."""

    def test_clean_text_is_not_flagged(self):
        self.assertEqual(_redaction_hits(PRE_CHANGE_INVARIANT_1), [])

    def test_each_kind_of_leak_is_flagged(self):
        samples = (
            ("see https://www.notion.so/abc", "notion.so"),
            ("see https://example.notion.site/abc", "notion.site"),
            ("see https://www.notion.com/abc", "notion.com"),
            ("under /home/someone/work", "/home/"),
        )
        for sample, needle in samples:
            with self.subTest(needle=needle):
                self.assertEqual(_redaction_hits(sample), [needle])


if __name__ == "__main__":
    unittest.main()
