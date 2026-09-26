"""Tests for task0003 (tier-decision-staged-jev): the staged tier-decision
procedure in `skills/develop/SKILL.md`'s Step A tier-decision section (first
Jev call on the task description alone, a read-only Codex pre-survey, then a
final Jev call that sees the description plus both JSON results), the single
final-score evaluator payload, and the schema_version 2 persisted record.

Covers this task's Acceptance Criteria
(feature-docs/tier-decision-staged-jev/tasks/task0003.md):

- AC-1 (FR1; TS-9): the section describes the three calls in the order first
  Jev call (description only), Codex read-only pre-survey, final Jev call;
  asserted by the relative positions of the three call descriptions.
- AC-2 (FR2, FR6; TS-9): the final Jev call's input is the task description,
  the first Jev call's full JSON result including its confidence, and the
  Codex pre-survey JSON; both Jev calls receive the `question_set` bucket
  descriptions by citation of the rule table.
- AC-3 (FR8, FR9; TS-9): a pre-survey with a non-zero exit, unparseable JSON
  output or a missing required field skips the final Jev call and yields
  tier full; a non-zero exit of either Jev call yields tier full; an
  unusable first Jev call still lets the pre-survey run.
- AC-4 (FR12; TS-9): a pre-survey reporting no remaining work ends the run
  through the no-work-required stop before the final Jev call and before
  any workflow step.
- AC-5 (FR5, FR10; TS-9): the evaluator receives one final score object plus
  `codex_available` and `jev_available` (no two-reading payload); the
  result is recorded as tier.yaml schema_version 2 with the SC-4 presence
  rules; the resume reuse of an existing record is stated; the section
  contains neither `readings_disagree` nor any rule comparing two readings.
- AC-6 (NFR2, NFR4; TS-9): no decimal fraction literal, no `P(0)`, no
  `expectation_clear`, no gate_id value definition and no AskUserQuestion.
- AC-7 (NFR3): each matcher passes on the real section and fails on a forged
  sample that violates it; the section locator asserts a non-empty section
  bounded by its own heading and the next heading of the same or higher
  level; `python3 -m unittest discover -s tests` passes.

Test Notes: locates the section generically (own heading to the next heading
of level <= 3, not a hardcoded sibling heading) so the retrospect block
(owned elsewhere, IMPLEMENTATION.md SC-6) can never affect these tests.
Follows the pattern established by tests/test_tier_decision_step_a.py:
helper matcher functions, `_strip_ws` normalization for hard-wrapped
Japanese prose, and a `Test*MatchersCanFail` class per matcher proving a
negative proof, plus non-vacuity guards.
"""

import ast
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"
SKILL_PATH = PLUGIN_ROOT / "skills" / "develop" / "SKILL.md"

TIER_SECTION_HEADING = "### tier 決定"


def _read(path):
    if not path.is_file():
        raise AssertionError(f"expected file to exist: {path}")
    return path.read_text(encoding="utf-8")


def _strip_ws(text):
    # Strip ALL whitespace (not collapse to one space): Japanese prose in
    # this document is hard-wrapped without a space at the break point, so a
    # phrase spanning a wrap needs every whitespace character removed to
    # match reliably (same convention as tests/test_tier_decision_step_a.py).
    return re.sub(r"\s+", "", text)


def _contains(text, phrase):
    """True iff `phrase` occurs in `text` once both are whitespace-stripped
    -- safe against hard-wrapping and against a code span split across a
    line break."""
    return _strip_ws(phrase) in _strip_ws(text)


def _locate_section(text, heading):
    """AC-7: locate `heading`'s own line, then slice up to the next heading
    of the same or higher level (fewer or equal leading `#`s) -- never a
    hardcoded sibling heading string, so this genuinely exercises "bounded
    by its own heading and the next heading of the same or higher level"
    rather than assuming where that next heading is. Raises if the heading
    is missing or the resulting section is empty."""
    heading_match = re.search(r"(?m)^" + re.escape(heading), text)
    if heading_match is None:
        raise AssertionError(f"heading not found as its own line: {heading!r}")
    own_level = len(heading) - len(heading.lstrip("#"))
    start = heading_match.start()
    search_from = heading_match.end()
    next_heading_re = re.compile(r"(?m)^(#{1,%d})\s" % own_level)
    next_match = next_heading_re.search(text, search_from)
    end = next_match.start() if next_match is not None else len(text)
    section = text[start:end]
    body_after_heading = section[len(heading) :]
    if not body_after_heading.strip():
        raise AssertionError("located section is empty")
    return section


SKILL_TEXT = _read(SKILL_PATH)
TIER_SECTION = _locate_section(SKILL_TEXT, TIER_SECTION_HEADING)


# ---------------------------------------------------------------------------
# AC-7 (part 1): the generic locator itself -- non-vacuity and failure modes.
# ---------------------------------------------------------------------------


class TestSectionLocator(unittest.TestCase):
    def test_locates_a_nonempty_section(self):
        self.assertGreater(len(TIER_SECTION.strip()), 500)

    def test_section_starts_with_its_own_heading(self):
        self.assertTrue(TIER_SECTION.startswith(TIER_SECTION_HEADING))

    def test_section_stops_before_the_next_heading_of_same_or_higher_level(self):
        # The next heading after "### tier 決定" bounded at level <= 3 is
        # "## Step A.5" (level 2, higher than ###) in the real document;
        # this proves the generic locator actually stopped there rather than
        # running to end-of-file or into a deeper (####) heading.
        self.assertNotIn("## Step A.5", TIER_SECTION)
        self.assertIn("## Step A.5", SKILL_TEXT)

    def test_locator_raises_on_missing_heading(self):
        with self.assertRaises(AssertionError):
            _locate_section("何も見出しが無い文書。", TIER_SECTION_HEADING)

    def test_locator_raises_on_empty_section(self):
        forged = TIER_SECTION_HEADING + "\n## 次の見出し\n本文\n"
        with self.assertRaises(AssertionError):
            _locate_section(forged, TIER_SECTION_HEADING)


# ---------------------------------------------------------------------------
# AC-1: the three calls appear, in order: first Jev call (description only),
# Codex read-only pre-survey, final Jev call.
# ---------------------------------------------------------------------------

FIRST_JEV_CALL_MARKER = (
    "2. **1 回目の判定呼び出し（decision-basis `description_only`）**"
)
CODEX_PRESURVEY_MARKER = "3. **Codex 事前調査**"
FINAL_JEV_CALL_MARKER = (
    "5. **2 回目（最終）の判定呼び出し（decision-basis "
    "`description_plus_code`）**"
)


def _call_marker_offsets(text):
    """Byte offsets (in whitespace-stripped text) of the three call
    markers, or None if any is missing -- absence must never be silently
    treated as "order satisfied"."""
    stripped = _strip_ws(text)
    offsets = []
    for marker in (
        FIRST_JEV_CALL_MARKER,
        CODEX_PRESURVEY_MARKER,
        FINAL_JEV_CALL_MARKER,
    ):
        idx = stripped.find(_strip_ws(marker))
        if idx == -1:
            return None
        offsets.append(idx)
    return tuple(offsets)


def _calls_described_in_order(text):
    offsets = _call_marker_offsets(text)
    if offsets is None:
        return False
    first_idx, codex_idx, final_idx = offsets
    return first_idx < codex_idx < final_idx


class TestAC1CallOrder(unittest.TestCase):
    def test_all_three_call_markers_present(self):
        self.assertIsNotNone(_call_marker_offsets(TIER_SECTION))

    def test_calls_described_in_order(self):
        self.assertTrue(_calls_described_in_order(TIER_SECTION))


class TestAC1MatchersCanFail(unittest.TestCase):
    def test_fails_when_reordered(self):
        # Splice the final-call block before the first-call block: a forged
        # reordering built from the real content, not hand-written text.
        first_idx = TIER_SECTION.index(FIRST_JEV_CALL_MARKER)
        codex_idx = TIER_SECTION.index(CODEX_PRESURVEY_MARKER)
        final_idx = TIER_SECTION.index(FINAL_JEV_CALL_MARKER)
        no_work_idx = TIER_SECTION.index("4. **no-work 停止**")
        before_first = TIER_SECTION[:first_idx]
        first_block = TIER_SECTION[first_idx:codex_idx]
        codex_block = TIER_SECTION[codex_idx:no_work_idx]
        no_work_and_rest = TIER_SECTION[no_work_idx:final_idx]
        final_and_rest = TIER_SECTION[final_idx:]
        forged = (
            before_first
            + final_and_rest
            + first_block
            + codex_block
            + no_work_and_rest
        )
        self.assertFalse(_calls_described_in_order(forged))

    def test_fails_when_final_call_missing(self):
        forged = TIER_SECTION.replace(FINAL_JEV_CALL_MARKER, "")
        self.assertFalse(_calls_described_in_order(forged))

    def test_fails_when_codex_call_missing(self):
        forged = TIER_SECTION.replace(CODEX_PRESURVEY_MARKER, "")
        self.assertFalse(_calls_described_in_order(forged))

    def test_fails_when_first_call_missing(self):
        forged = TIER_SECTION.replace(FIRST_JEV_CALL_MARKER, "")
        self.assertFalse(_calls_described_in_order(forged))

    def test_non_vacuity_real_section_passes(self):
        self.assertTrue(_calls_described_in_order(TIER_SECTION))


# ---------------------------------------------------------------------------
# AC-2: final call's input and the question_set citation on both calls.
# ---------------------------------------------------------------------------


def _states_final_call_input_components(text):
    return (
        _contains(text, "入力はタスク記述")
        and _contains(text, "`confidence` を含む")
        and _contains(text, "Codex の JSON")
    )


def _both_calls_cite_question_set_by_name(text):
    return text.count("`question_set`") >= 2


class TestAC2FinalCallInput(unittest.TestCase):
    def test_states_final_call_input_components(self):
        self.assertTrue(_states_final_call_input_components(TIER_SECTION))

    def test_both_jev_calls_cite_question_set(self):
        self.assertTrue(_both_calls_cite_question_set_by_name(TIER_SECTION))

    def test_no_threshold_or_decision_basis_value_restated_outside_citation(self):
        # `question_set` and `codex_output_schema` are cited by name; their
        # content (bucket wording, field list) is never copied here.
        self.assertNotIn("files_expected", TIER_SECTION)
        self.assertNotIn("changed_lines_approx", TIER_SECTION)


class TestAC2MatchersCanFail(unittest.TestCase):
    def test_final_call_input_matcher_fails_on_forged_copy(self):
        self.assertFalse(_states_final_call_input_components("何も書いていない"))

    def test_question_set_matcher_fails_when_cited_only_once(self):
        forged = TIER_SECTION.replace("`question_set`", "`question_set`", 1)
        # Remove every citation but the first to prove the >=2 count matters.
        first_idx = forged.index("`question_set`")
        after_first = first_idx + len("`question_set`")
        forged = forged[:after_first] + forged[after_first:].replace(
            "`question_set`", "question set"
        )
        self.assertFalse(_both_calls_cite_question_set_by_name(forged))

    def test_non_vacuity_real_section_cites_question_set_at_least_twice(self):
        self.assertGreaterEqual(TIER_SECTION.count("`question_set`"), 2)


# ---------------------------------------------------------------------------
# AC-3: usability consequences -- pre-survey unusable skips the final call
# and yields full; a non-zero exit of either Jev call yields full; an
# unusable first Jev call still lets the pre-survey run.
# ---------------------------------------------------------------------------

STEP6_MARKER = "6. **可用性の解決と評価器への委譲**"


def _step6_section(text):
    start = text.index(STEP6_MARKER)
    end = text.index("7. **統合 branch/worktree の確保**", start)
    return text[start:end]


def _presurvey_unusable_skips_final_call_and_yields_full(text):
    return (
        _contains(text, "5. の最終判定呼び出しを行わず")
        and _contains(text, "codex_available")
        and _contains(text, "何も引かない tier（`full`）を採用する")
    )


def _either_jev_call_nonzero_exit_yields_full(text):
    return _contains(text, "2. または 5. のいずれかが使用不可のときは") and _contains(
        text, "jev_available"
    )


def _unusable_first_call_still_lets_presurvey_run(text):
    return _contains(
        text,
        "2. が使用不可であっても、3. の Codex 事前調査はそのまま実行する",
    )


class TestAC3UsabilityConsequences(unittest.TestCase):
    def test_step6_exists_and_nonempty(self):
        section = _step6_section(TIER_SECTION)
        self.assertGreater(len(section.strip()), 100)

    def test_presurvey_unusable_skips_final_call_and_yields_full(self):
        self.assertTrue(
            _presurvey_unusable_skips_final_call_and_yields_full(
                _step6_section(TIER_SECTION)
            )
        )

    def test_either_jev_call_nonzero_exit_yields_full(self):
        self.assertTrue(
            _either_jev_call_nonzero_exit_yields_full(_step6_section(TIER_SECTION))
        )

    def test_unusable_first_call_still_lets_presurvey_run(self):
        self.assertTrue(
            _unusable_first_call_still_lets_presurvey_run(TIER_SECTION)
        )

    def test_codex_usability_criteria_named(self):
        section = _step6_section(TIER_SECTION)
        self.assertTrue(_contains(section, "終了ステータスが非 0"))
        self.assertTrue(_contains(section, "JSON として解釈できない"))
        self.assertTrue(_contains(section, "必須フィールドが欠けている"))


class TestAC3MatchersCanFail(unittest.TestCase):
    def test_presurvey_matcher_fails_on_forged_copy(self):
        self.assertFalse(
            _presurvey_unusable_skips_final_call_and_yields_full("何も書いていない")
        )

    def test_jev_nonzero_matcher_fails_on_forged_copy(self):
        self.assertFalse(_either_jev_call_nonzero_exit_yields_full("何も書いていない"))

    def test_first_call_unusable_matcher_fails_on_forged_copy(self):
        self.assertFalse(
            _unusable_first_call_still_lets_presurvey_run("何も書いていない")
        )

    def test_step6_still_calling_final_jev_is_detected(self):
        # Test Notes forged sample: "a step 6 that still calls the final
        # Jev" -- a step 6 lacking the skip statement must fail the
        # presurvey-unusable matcher.
        forged_step6 = (
            STEP6_MARKER
            + "\nCodex 事前調査が使用不可でも 5. の最終判定呼び出しを行う。\n"
        )
        self.assertFalse(
            _presurvey_unusable_skips_final_call_and_yields_full(forged_step6)
        )

    def test_non_vacuity_real_step6_passes_every_matcher(self):
        section = _step6_section(TIER_SECTION)
        self.assertTrue(_presurvey_unusable_skips_final_call_and_yields_full(section))
        self.assertTrue(_either_jev_call_nonzero_exit_yields_full(section))


# ---------------------------------------------------------------------------
# AC-4: no-work-required stop ends the run before the final Jev call and
# before any workflow step.
# ---------------------------------------------------------------------------


def _no_work_stop_precedes_final_call_and_any_workflow_step(text):
    stripped = _strip_ws(text)
    no_work_idx = stripped.find(_strip_ws("4. **no-work 停止**"))
    final_call_idx = stripped.find(_strip_ws(FINAL_JEV_CALL_MARKER))
    ends_before_workflow_step = _strip_ws(
        "いかなる workflow step も実行せずにここで走行を終える"
    ) in stripped
    if no_work_idx == -1 or final_call_idx == -1:
        return False
    return no_work_idx < final_call_idx and ends_before_workflow_step


class TestAC4NoWorkStop(unittest.TestCase):
    def test_no_work_stop_precedes_final_call_and_any_workflow_step(self):
        self.assertTrue(
            _no_work_stop_precedes_final_call_and_any_workflow_step(TIER_SECTION)
        )

    def test_hyphenated_stop_point_name_present(self):
        self.assertIn("no-work-required", TIER_SECTION)


class TestAC4MatchersCanFail(unittest.TestCase):
    def test_fails_on_forged_copy(self):
        self.assertFalse(
            _no_work_stop_precedes_final_call_and_any_workflow_step("何も書いていない")
        )

    def test_fails_when_final_call_precedes_no_work_stop(self):
        no_work_idx = TIER_SECTION.index("4. **no-work 停止**")
        final_idx = TIER_SECTION.index(FINAL_JEV_CALL_MARKER)
        step6_idx = TIER_SECTION.index(STEP6_MARKER)
        forged = (
            TIER_SECTION[:no_work_idx]
            + TIER_SECTION[final_idx:step6_idx]
            + TIER_SECTION[no_work_idx:final_idx]
            + TIER_SECTION[step6_idx:]
        )
        self.assertFalse(_no_work_stop_precedes_final_call_and_any_workflow_step(forged))


# ---------------------------------------------------------------------------
# AC-5: single final-score evaluator payload, schema_version 2 presence
# rules, resume reuse, no two-reading residue.
# ---------------------------------------------------------------------------


def _evaluator_payload_is_single_final_score_plus_flags(text):
    return (
        _contains(text, "final_score")
        and _contains(text, "codex_available")
        and _contains(text, "jev_available")
        and "readings" not in text
    )


def _records_schema_version_2_with_presence_rules(text):
    return (
        _contains(text, "`schema_version` は常に `2`")
        and _contains(text, "使用可能だった判定呼び出しの分だけ")
        and _contains(text, "使用可能だったときのみ書く")
        and _contains(text, "`threshold_rows:` から始まらないときのみ書く")
    )


def _states_resume_reuse(text):
    return _contains(text, "永続化済み判定の再利用") and _contains(
        text, "判定をやり直さず"
    )


class TestAC5EvaluatorPayloadAndRecord(unittest.TestCase):
    def test_evaluator_payload_is_single_final_score_plus_flags(self):
        self.assertTrue(
            _evaluator_payload_is_single_final_score_plus_flags(TIER_SECTION)
        )

    def test_records_schema_version_2_with_presence_rules(self):
        self.assertTrue(_records_schema_version_2_with_presence_rules(TIER_SECTION))

    def test_states_resume_reuse(self):
        self.assertTrue(_states_resume_reuse(TIER_SECTION))

    def test_no_readings_disagree_string(self):
        self.assertNotIn("readings_disagree", TIER_SECTION)

    def test_no_rule_comparing_two_readings(self):
        self.assertNotIn("評価器は各読みがそれぞれ決定する tier を比較し", TIER_SECTION)


class TestAC5MatchersCanFail(unittest.TestCase):
    def test_evaluator_payload_matcher_fails_on_forged_two_reading_copy(self):
        forged = TIER_SECTION + "\nreadings: [...]\n"
        self.assertFalse(_evaluator_payload_is_single_final_score_plus_flags(forged))

    def test_record_matcher_fails_on_forged_copy(self):
        self.assertFalse(_records_schema_version_2_with_presence_rules("何も書いていない"))

    def test_resume_matcher_fails_on_forged_copy(self):
        self.assertFalse(_states_resume_reuse("何も書いていない"))

    def test_readings_disagree_absence_matcher_fires_on_forged_copy(self):
        forged = TIER_SECTION + "\nfallback_matrix:readings_disagree\n"
        self.assertIn("readings_disagree", forged)

    def test_two_reading_comparison_absence_matcher_fires_on_forged_copy(self):
        forged = TIER_SECTION + "\n評価器は各読みがそれぞれ決定する tier を比較し\n"
        self.assertIn("評価器は各読みがそれぞれ決定する tier を比較し", forged)


# ---------------------------------------------------------------------------
# AC-6: no decimal fraction literal, no P(0), no expectation_clear, no
# gate_id value definition, no AskUserQuestion.
# ---------------------------------------------------------------------------

DECIMAL_LITERAL_RE = re.compile(r"\d+\.\d+")


def _find_ac6_violations(text):
    violations = []
    if DECIMAL_LITERAL_RE.search(text):
        violations.append("decimal_literal")
    if "P(0)" in text:
        violations.append("P(0)")
    if "expectation_clear" in text:
        violations.append("expectation_clear")
    if re.search(r"gate_id:\s*\S", text):
        violations.append("gate_id_value")
    if "AskUserQuestion" in text:
        violations.append("AskUserQuestion")
    return violations


class TestAC6ForbiddenTokens(unittest.TestCase):
    def test_no_violations_in_real_section(self):
        self.assertEqual(_find_ac6_violations(TIER_SECTION), [])

    def test_gate_id_word_in_disclaimer_is_not_a_value_definition(self):
        # The section's own disclaimer sentence legitimately contains the
        # bare word "gate_id" (never a "gate_id: value" definition) -- this
        # proves the real section's clean AC-6 pass is not a fluke of the
        # word being absent altogether.
        self.assertIn("gate_id", TIER_SECTION)
        self.assertIsNone(re.search(r"gate_id:\s*\S", TIER_SECTION))


class TestAC6MatchersCanFail(unittest.TestCase):
    def test_decimal_literal_detected(self):
        self.assertIn("decimal_literal", _find_ac6_violations(TIER_SECTION + "\n0.85\n"))

    def test_p0_detected(self):
        self.assertIn("P(0)", _find_ac6_violations(TIER_SECTION + "\nP(0) が高い\n"))

    def test_expectation_clear_detected(self):
        self.assertIn(
            "expectation_clear",
            _find_ac6_violations(TIER_SECTION + "\nexpectation_clear を見る\n"),
        )

    def test_gate_id_value_detected(self):
        self.assertIn(
            "gate_id_value",
            _find_ac6_violations(TIER_SECTION + "\ngate_id: tier.no-work\n"),
        )

    def test_ask_user_question_detected(self):
        self.assertIn(
            "AskUserQuestion",
            _find_ac6_violations(TIER_SECTION + "\nAskUserQuestion で確認する。\n"),
        )


# ---------------------------------------------------------------------------
# AC-7 (part 2): this module's own hygiene (stdlib-only imports).
# ---------------------------------------------------------------------------


class TestOwnModuleStdlibOnly(unittest.TestCase):
    def test_own_imports_are_all_stdlib(self):
        with open(__file__, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=__file__)

        stdlib_names = set(sys.stdlib_module_names)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])

        self.assertTrue(imported, "expected at least one import in this module")
        non_stdlib = imported - stdlib_names
        self.assertEqual(non_stdlib, set(), f"non-stdlib imports found: {non_stdlib}")


if __name__ == "__main__":
    unittest.main()
