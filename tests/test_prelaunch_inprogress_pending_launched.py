"""Tests for task0002 (prelaunch-inprogress-routeback): the Step I.2.a
selection-rules sentence that claimed workflow.yaml `status: pending`
combined with journal last event `launched` can never arise is rewritten in
`em-workflow/references/implement-phase.md`. The combination does arise --
between a task's launch and Step I.2.a's launch-state commit, and when that
commit is not reached -- and the in-flight rule already stated in I.2.a
governs it.

Covers task0002 Acceptance Criteria
(feature-docs/prelaunch-inprogress-routeback/tasks/task0002.md):

- AC-1 (FR5, TS5): the I.2.a section contains no "can never arise", in
  particular no claim that `status: pending` combined with journal last
  event `launched` can never arise.
- AC-2 (FR5, TS5): the replacement text sits after the in-flight sentence
  and before the sentence opening "Because Step I.2.c's route-back gate
  below"; it states the window between a task's launch and Step I.2.a's
  launch-state commit, and the cases where that commit is not reached (an
  interruption or a second exit 4); it cites the in-flight rule as the
  governing rule; it contains the literal term "launch-state commit".
- AC-3 (FR5, NFR1): the Region P items that stay byte-identical are
  present, unchanged and in their original relative order; the recursion
  invariant follows the replacement text.
- AC-6 (FR6, NFR4, TS5): this module uses only the standard library; each
  new-wording matcher below has a negative proof against a verbatim
  pre-change sample of the old sentence, backed by a non-vacuity guard.

This module reads only `em-workflow/references/implement-phase.md`. It does
not import another test module.

Content assertions compare against a whitespace-normalized copy of the
relevant section, so line-wrap choices never make a prose assertion
brittle; byte-identity assertions compare the raw, un-normalized text. The
two are never mixed in one assertion.

Matcher -> negative-proof inventory (every new-wording matcher):

- test_i2a_has_no_can_never_arise_phrase,
  test_i2a_has_no_never_arise_claim_in_any_inflection -> absence of the old
  claim ->
  test_never_arise_matchers_flag_the_pre_change_sentence
- test_replacement_sits_between_in_flight_sentence_and_next_sentence ->
  new wording (ordered placement) ->
  test_placement_matcher_fails_on_pre_change_sentence
- test_replacement_states_launch_window -> new wording ->
  test_launch_window_matcher_flags_absence_in_pre_change_sentence
- test_replacement_states_commit_not_reached_cases -> new wording ->
  test_commit_not_reached_matcher_flags_absence_in_pre_change_sentence
- test_replacement_cites_in_flight_rule -> new wording ->
  test_in_flight_citation_matcher_flags_absence_in_pre_change_sentence
- test_replacement_states_carve_out_does_not_apply -> new wording ->
  test_replacement_slice_cannot_be_taken_on_pre_change_sentence
- test_replacement_contains_launch_state_commit_term -> new wording ->
  test_launch_state_commit_term_matcher_flags_absence_in_pre_change_sentence
- test_recursion_invariant_follows_replacement_text -> derivative ordering
  check on the replacement's terminal phrase -> same proof as
  test_replacement_slice_cannot_be_taken_on_pre_change_sentence
- TestByteIdenticalItems (other tests) -> RETENTION matchers, no proof
  needed
- TestModuleUsesOnlyStandardLibrary -> structural guard, no proof needed

Every negative proof runs against PRE_CHANGE_I2A_PENDING_LAUNCHED_SAMPLE, a
verbatim excerpt of `em-workflow/references/implement-phase.md` as it reads
at this task's base revision (`ce845cbd9fb831b8c01a32851dab19761f84ab54`),
generated from the file by script and not reconstructed. Its non-vacuity is
guarded in `TestPreChangeSampleGuards`: each anchor the matchers rely on is
asserted present in both the sample and the live document.
"""

import ast
import re
import sys
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "em-workflow"
IMPLEMENT_PHASE_PATH = PLUGIN_ROOT / "references" / "implement-phase.md"

I2A_HEADING = "### I.2.a: Launch phase"
I2B_HEADING = "### I.2.b: Wake phase"
# Region P ends where Region L begins (IMPLEMENTATION.md, Shared Components).
REGION_L_OPENING_ANCHOR = "For each selected task T"

# --- Module-level constants: every literal asserted as new wording is read
# by both its positive test and its negative-proof test.

# Anchors that bracket the replacement text; present before and after the
# edit (non-vacuity anchors for the sample as well).
IN_FLIGHT_SENTENCE = (
    "A task whose journal last event is `launched` is always in-flight, "
    "regardless of workflow.yaml `status`"
)
OPENING_ANCHOR = "Given I.2.c's route-back precondition below"
NEXT_SENTENCE_ANCHOR = "Because Step I.2.c's route-back gate below"

# AC-1: the claim that is gone.
OLD_NEVER_ARISE_PHRASE = "can never arise"
OLD_NEVER_ARISE_TERMINAL = "can never arise."
NEVER_ARISE_RE = re.compile(r"\bnever\s+arises?\b")

# AC-2: the new wording.
LAUNCH_STATE_COMMIT_TERM = "launch-state commit"
LAUNCH_WINDOW_PHRASE = (
    "that combination arises between a task's launch and Step I.2.a's "
    "launch-state commit below"
)
COMMIT_NOT_REACHED_PHRASE = (
    "when that commit is not reached (an interruption, or a second exit 4)"
)
IN_FLIGHT_RULE_CITATION_PHRASE = (
    "The in-flight rule stated just above governs that combination, cited "
    "here and not restated"
)
REPLACEMENT_TERMINAL_PHRASE = (
    "the recycled-task-id carve-out above does not apply to it."
)

# AC-3: Region P items that stay byte-identical (raw text, line wraps
# included), captured from the base revision by script.
CARVE_OUT_SCOPED_SENTENCE = (
    "This carve-out is deliberately scoped to `failed` only"
)
IN_FLIGHT_SENTENCE_RAW = (
    "A task whose journal last event is `launched` is\n"
    "always in-flight, regardless of workflow.yaml `status`"
)
PREMISE_THROUGH_SCOPED_SPAN_RAW = (
    "Because Step I.2.c's route-back gate below blocks route-back\n"
    "whenever any task's journal last event is `merged` — read from the\n"
    "journal directly, independent of the ancestor check — that gate never\n"
    "admits route-back while such an event stands. No retired task id is ever\n"
    "re-issued, so a task whose workflow.yaml `status` is `pending` can never\n"
    "carry an inherited `merged` journal last event; the recycled-task-id\n"
    "carve-out above stays correctly scoped to `failed` only."
)
SELECT_LINEWRAP_LITERAL_RAW = (
    "`tasks.*.status`. Select\n"
    "unlaunched tasks (no journal event yet and `status != merged`, "
    "ascending"
)
INDEPENDENT_OF_ANCESTOR_CHECK_PHRASE = "independent of the ancestor check"
RECURSION_INVARIANT_PHRASE = (
    "No retired task id is ever re-issued, so a task whose workflow.yaml "
    "`status` is `pending` can never carry an inherited `merged` journal "
    "last event"
)
SCOPED_SPAN_TERMINAL_PHRASE = "correctly scoped to `failed` only."

# --- Pre-change sample: a verbatim excerpt of
# em-workflow/references/implement-phase.md at this task's base revision
# ce845cbd9fb831b8c01a32851dab19761f84ab54, from the in-flight sentence
# through the opening words of the sentence that follows the old claim.
# Generated from the file by script, never reconstructed.
PRE_CHANGE_I2A_PENDING_LAUNCHED_SAMPLE = (
    "A task whose journal last event is `launched` is\n"
    "always in-flight, regardless of workflow.yaml `status` — never reinterpret\n"
    "it as unlaunched, since the launch guard would deny that launch. Reason:\n"
    "I.2.c's route back to planning is the only writer that resets a task's\n"
    "status to `pending`, and no re-planning pass ever re-issues a retired task\n"
    "id to a different task — `references/workflow-patch.md`'s re-planning\n"
    "task-id allocation rule (cited here, never restated) allocates every new\n"
    "id above the highest the feature has ever registered, so the `pending` +\n"
    "`failed` combination arises only from I.2.c's own reset of a task's own\n"
    "prior `failed` status, never from a task inheriting a different task's\n"
    "retired id. Given I.2.c's route-back precondition below, which admits only\n"
    "tasks with a terminal journal last event, and the allocation rule's\n"
    "guarantee that a `replace_all` never re-issues a retired id, a task can\n"
    "only ever carry its OWN journal's terminal event — so workflow.yaml\n"
    "`status: pending` combined with journal last event `launched` can never\n"
    "arise. Because Step I.2.c's route-back gate below blocks route-back"
)


def _read():
    return IMPLEMENT_PHASE_PATH.read_text(encoding="utf-8")


def _normalize_ws(text):
    """Collapse all whitespace runs (including line-wrap newlines) to a
    single space."""
    return re.sub(r"\s+", " ", text)


def _i2a_section(text):
    start = text.index(I2A_HEADING)
    end = text.index(I2B_HEADING, start)
    return text[start:end]


def _region_p(text):
    """Step I.2.a's selection rules: from the I.2.a heading up to, not
    including, the paragraph that opens "For each selected task T"."""
    start = text.index(I2A_HEADING)
    end = text.index(REGION_L_OPENING_ANCHOR, start)
    return text[start:end]


def _ordered_spans(text, needles):
    """Locate each needle in order, searching each later needle only after
    the earlier needle's match ends, so a shared substring cannot satisfy the
    order by accident. Raises AssertionError naming the first needle that is
    missing from its allowed range."""
    spans = []
    pos = 0
    for needle in needles:
        idx = text.find(needle, pos)
        if idx == -1:
            raise AssertionError(
                f"{needle!r} not found at or after offset {pos}"
            )
        pos = idx + len(needle)
        spans.append((idx, pos))
    return spans


def _replacement_text(normalized_text):
    """The replacement text: from the kept opening anchor through the
    terminal phrase of the rewritten sentence. Raises ValueError when either
    anchor is missing."""
    start = normalized_text.find(OPENING_ANCHOR)
    if start == -1:
        raise ValueError(f"opening anchor {OPENING_ANCHOR!r} not found")
    terminal = normalized_text.find(REPLACEMENT_TERMINAL_PHRASE, start)
    if terminal == -1:
        raise ValueError(
            f"terminal phrase {REPLACEMENT_TERMINAL_PHRASE!r} not found "
            f"after the opening anchor"
        )
    return normalized_text[start : terminal + len(REPLACEMENT_TERMINAL_PHRASE)]


def _placement_spans(normalized_text):
    """Spans of (in-flight sentence, window phrase, next sentence opening),
    searched in that order."""
    return _ordered_spans(
        normalized_text,
        (IN_FLIGHT_SENTENCE, LAUNCH_WINDOW_PHRASE, NEXT_SENTENCE_ANCHOR),
    )


class TestNeverArisesClaimRemoved(unittest.TestCase):
    """AC-1 (FR5, TS5): the I.2.a section no longer claims the combination
    can never arise."""

    @classmethod
    def setUpClass(cls):
        cls.i2a = _normalize_ws(_i2a_section(_read()))

    def test_i2a_has_no_can_never_arise_phrase(self):
        self.assertFalse(
            OLD_NEVER_ARISE_PHRASE in self.i2a,
            f"I.2.a still contains {OLD_NEVER_ARISE_PHRASE!r}",
        )

    def test_i2a_has_no_never_arise_claim_in_any_inflection(self):
        self.assertIsNone(NEVER_ARISE_RE.search(self.i2a))


class TestReplacementText(unittest.TestCase):
    """AC-2 (FR5, TS5): the replacement text's placement and content."""

    @classmethod
    def setUpClass(cls):
        cls.i2a = _normalize_ws(_i2a_section(_read()))

    def test_replacement_sits_between_in_flight_sentence_and_next_sentence(
        self,
    ):
        in_flight, window, next_sentence = _placement_spans(self.i2a)
        self.assertLess(in_flight[1], window[0])
        self.assertLess(window[1], next_sentence[0])

    def test_replacement_states_launch_window(self):
        self.assertIn(LAUNCH_WINDOW_PHRASE, _replacement_text(self.i2a))

    def test_replacement_states_commit_not_reached_cases(self):
        self.assertIn(COMMIT_NOT_REACHED_PHRASE, _replacement_text(self.i2a))

    def test_replacement_cites_in_flight_rule(self):
        self.assertIn(
            IN_FLIGHT_RULE_CITATION_PHRASE, _replacement_text(self.i2a)
        )

    def test_replacement_states_carve_out_does_not_apply(self):
        replacement = _replacement_text(self.i2a)
        self.assertTrue(replacement.endswith(REPLACEMENT_TERMINAL_PHRASE))

    def test_replacement_contains_launch_state_commit_term(self):
        self.assertIn(LAUNCH_STATE_COMMIT_TERM, _replacement_text(self.i2a))

    def test_replacement_ends_before_next_sentence(self):
        start = self.i2a.index(OPENING_ANCHOR)
        end = start + len(_replacement_text(self.i2a))
        next_idx = self.i2a.index(NEXT_SENTENCE_ANCHOR, end)
        self.assertLessEqual(end, next_idx)
        # Nothing but the single separating space sits between the
        # replacement's terminal and the next sentence's opening.
        self.assertEqual(self.i2a[end:next_idx].strip(), "")


class TestByteIdenticalItems(unittest.TestCase):
    """AC-3 (FR5, NFR1): the Region P items outside the replaced sentence
    are present, byte-identical and in their original relative order; the
    recursion invariant follows the replacement text.

    Byte-identity assertions run on raw text; ordering and counting
    assertions run on whitespace-normalized text."""

    @classmethod
    def setUpClass(cls):
        text = _read()
        cls.region_p_raw = _region_p(text)
        cls.region_p = _normalize_ws(cls.region_p_raw)

    def test_carve_out_scoped_sentence_is_byte_identical(self):
        self.assertEqual(
            self.region_p_raw.count(CARVE_OUT_SCOPED_SENTENCE), 1
        )

    def test_in_flight_sentence_is_byte_identical(self):
        self.assertEqual(self.region_p_raw.count(IN_FLIGHT_SENTENCE_RAW), 1)

    def test_premise_through_scoped_span_is_byte_identical(self):
        self.assertEqual(
            self.region_p_raw.count(PREMISE_THROUGH_SCOPED_SPAN_RAW), 1
        )

    def test_select_linewrap_literal_is_byte_identical(self):
        self.assertEqual(
            self.region_p_raw.count(SELECT_LINEWRAP_LITERAL_RAW), 1
        )

    def test_items_keep_their_original_relative_order(self):
        # Original order in Region P: the Select literal, the failed-only
        # carve-out sentence, the in-flight sentence, then the premise span.
        spans = _ordered_spans(
            self.region_p,
            (
                _normalize_ws(SELECT_LINEWRAP_LITERAL_RAW),
                CARVE_OUT_SCOPED_SENTENCE,
                IN_FLIGHT_SENTENCE,
                _normalize_ws(PREMISE_THROUGH_SCOPED_SPAN_RAW),
            ),
        )
        self.assertEqual(len(spans), 4)

    def test_recursion_invariant_follows_replacement_text(self):
        replacement_end = self.region_p.index(OPENING_ANCHOR) + len(
            _replacement_text(self.region_p)
        )
        invariant_idx = self.region_p.index(
            RECURSION_INVARIANT_PHRASE, replacement_end
        )
        self.assertLess(replacement_end, invariant_idx)

    def test_premise_span_has_exactly_one_because_and_one_so(self):
        # From the premise through "correctly scoped to `failed` only."
        # there is exactly one "Because " and one " so "; the replacement
        # text sits before this span and adds neither word inside it.
        start = self.region_p.index(NEXT_SENTENCE_ANCHOR)
        end = self.region_p.index(SCOPED_SPAN_TERMINAL_PHRASE, start) + len(
            SCOPED_SPAN_TERMINAL_PHRASE
        )
        span = self.region_p[start:end]
        self.assertEqual(span.count("Because "), 1)
        self.assertEqual(span.count(" so "), 1)

    def test_premise_stays_independent_of_ancestor_check(self):
        start = self.region_p.index(NEXT_SENTENCE_ANCHOR)
        self.assertIn(
            INDEPENDENT_OF_ANCESTOR_CHECK_PHRASE, self.region_p[start:]
        )


class TestPreChangeSampleDetection(unittest.TestCase):
    """AC-6 (FR6, NFR4, TS5): every new-wording matcher above fails
    meaningfully against the verbatim pre-change sample. Each proof asserts
    that the matcher's new phrase is absent from (or its anchored slice
    cannot be formed on) the old sentence, which does contain
    "can never arise."."""

    @classmethod
    def setUpClass(cls):
        cls.sample = _normalize_ws(PRE_CHANGE_I2A_PENDING_LAUNCHED_SAMPLE)

    def test_never_arise_matchers_flag_the_pre_change_sentence(self):
        self.assertIn(OLD_NEVER_ARISE_PHRASE, self.sample)
        self.assertIn(OLD_NEVER_ARISE_TERMINAL, self.sample)
        self.assertIsNotNone(NEVER_ARISE_RE.search(self.sample))

    def test_placement_matcher_fails_on_pre_change_sentence(self):
        with self.assertRaises(AssertionError):
            _placement_spans(self.sample)

    def test_launch_window_matcher_flags_absence_in_pre_change_sentence(self):
        self.assertNotIn(LAUNCH_WINDOW_PHRASE, self.sample)

    def test_commit_not_reached_matcher_flags_absence_in_pre_change_sentence(
        self,
    ):
        self.assertNotIn(COMMIT_NOT_REACHED_PHRASE, self.sample)

    def test_in_flight_citation_matcher_flags_absence_in_pre_change_sentence(
        self,
    ):
        self.assertNotIn(IN_FLIGHT_RULE_CITATION_PHRASE, self.sample)

    def test_launch_state_commit_term_matcher_flags_absence_in_pre_change_sentence(
        self,
    ):
        self.assertNotIn(LAUNCH_STATE_COMMIT_TERM, self.sample)

    def test_replacement_slice_cannot_be_taken_on_pre_change_sentence(self):
        # The opening anchor is present in the sample (see the guards
        # below), so the slice fails on its terminal phrase, not on a
        # missing opening.
        with self.assertRaises(ValueError):
            _replacement_text(self.sample)


class TestPreChangeSampleGuards(unittest.TestCase):
    """Non-vacuity guards: each anchor the matchers rely on is present in
    both the pre-change sample and the live document, so a negative proof
    above cannot degrade into a tautology (an absence check passes against
    an empty or truncated sample)."""

    @classmethod
    def setUpClass(cls):
        cls.sample = _normalize_ws(PRE_CHANGE_I2A_PENDING_LAUNCHED_SAMPLE)
        cls.live = _normalize_ws(_i2a_section(_read()))

    def test_in_flight_sentence_is_in_sample_and_live_document(self):
        self.assertIn(IN_FLIGHT_SENTENCE, self.sample)
        self.assertIn(IN_FLIGHT_SENTENCE, self.live)

    def test_opening_anchor_is_in_sample_and_live_document(self):
        self.assertIn(OPENING_ANCHOR, self.sample)
        self.assertIn(OPENING_ANCHOR, self.live)

    def test_next_sentence_anchor_is_in_sample_and_live_document(self):
        self.assertIn(NEXT_SENTENCE_ANCHOR, self.sample)
        self.assertIn(NEXT_SENTENCE_ANCHOR, self.live)

    def test_sample_carries_the_old_claim_the_live_document_dropped(self):
        self.assertIn(OLD_NEVER_ARISE_TERMINAL, self.sample)
        self.assertFalse(
            OLD_NEVER_ARISE_TERMINAL in self.live,
            f"live I.2.a still contains {OLD_NEVER_ARISE_TERMINAL!r}",
        )

    def test_sample_is_ordered_like_the_live_document(self):
        spans = _ordered_spans(
            self.sample,
            (IN_FLIGHT_SENTENCE, OPENING_ANCHOR, NEXT_SENTENCE_ANCHOR),
        )
        self.assertEqual(len(spans), 3)


class TestModuleUsesOnlyStandardLibrary(unittest.TestCase):
    """AC-6 (NFR4): this module imports only the standard library and no
    other test module."""

    def test_imports_are_standard_library_only(self):
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                imported.add((node.module or "").split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                imported.add("<relative import>")
        self.assertTrue(imported)
        self.assertEqual(imported - set(sys.stdlib_module_names), set())


if __name__ == "__main__":
    unittest.main()
