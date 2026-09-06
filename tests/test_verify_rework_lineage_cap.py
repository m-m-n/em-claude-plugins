"""Tests for task0001 (batch-verify-rework-lineage-cap): the develop
skill's batch verify-rework cap moves from a fixed-count cap
(`batch.verify_rework_count`) to a two-judgment model -- a lineage cap
over failed-item-ID recurrence and a hard cap over rework round count,
evaluated independently -- with the definition body living solely in
`skills/develop/SKILL.md`'s verify フェーズ section (NFR1) and the batch
`workflow.yaml` block restructured to carry the history the judgment
reads (FR8).

Covers task0001 Acceptance Criteria
(feature-docs/batch-verify-rework-lineage-cap/tasks/task0001.md):

- AC-1 (FR1): SKILL.md's verify フェーズ section describes the lineage
  count (cumulative per-failed-item-ID occurrences held in
  `failed_id_counts`, incremented for every ID appearing each round,
  including the first), a lineage cap value of 1, and the "new ID gets a
  fresh budget" consequence; the same content is summarized (no numeral)
  in batch-mode.md's `verify.failed` row.
- AC-2 (FR2): both files state the hard cap (round-count limit) is
  evaluated independently of the lineage cap; the numeral lives only in
  SKILL.md.
- AC-3 (FR3): SKILL.md states that reaching either cap does not stop the
  run -- `verify.status` stays `failed` into the retrospect phase -- the
  old "stay failed and stop with a report" wording is gone from the whole
  file, and no instruction anywhere assigns `deferred` to verify's
  leftover items.
- AC-4 (FR8): workflow-schema.md's `batch` block structure shows
  `review_rework_count` plus `verify_rework.rounds` /
  `verify_rework.failed_id_counts`; the retired `verify_rework_count` key
  is gone from that structure (a historical mention elsewhere in the file
  is permitted); the explanation is updated for a history-carrying
  structure, batch-activation-independence is retained, and the retired
  key's fallback handling is stated.
- AC-5 (NFR1): the cap definition body (numeral + counting rule) lives
  only in SKILL.md -- batch-mode.md and workflow-schema.md carry no
  verify-cap numeral near the lineage/hard-cap vocabulary (review's own
  `cap 1` wording is untouched and out of scope).
- AC-7 (NFR3, NFR4): this module imports the standard library only, and
  each new matcher rejects a forged section carrying the old
  fixed-counter wording (negative proof) while accepting a forged section
  built to satisfy it (non-vacuity guard).

Test isolation (IMPLEMENTATION.md D2): every assertion below targets only
the three files this task owns -- `skills/develop/SKILL.md`,
`references/batch-mode.md`, `references/workflow-schema.md`. Nothing here
asserts content another task's plan assigns elsewhere (Step C wording,
retrospect.yaml's `follow_up_drafts`, the stop-condition exception
clauses, or the terminal line).
"""

import ast
import re
import sys
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "em-workflow"
SKILL_PATH = PLUGIN_ROOT / "skills" / "develop" / "SKILL.md"
BATCH_MODE_PATH = PLUGIN_ROOT / "references" / "batch-mode.md"
SCHEMA_PATH = PLUGIN_ROOT / "references" / "workflow-schema.md"

# Section boundaries, taken verbatim from skills/develop/SKILL.md. Using
# the heading LINES themselves as the cut points (Test Notes) keeps the
# slice stable even if another task rewrites the retrospect section body.
VERIFY_HEADING = "### verify フェーズ"
RETROSPECT_HEADING = "### retrospect フェーズ（収集は自動・承認不要）"

# The pre-existing fixed-counter cap wording this task retires. Its
# continued presence anywhere in SKILL.md is a regression (AC-3).
OLD_STOP_AND_REPORT_WORDING = "`failed` のまま報告して停止"

# Keywords that anchor "this text is talking about verify's rework cap"
# for the NFR1 numeral-absence scan (Test Notes: scope the numeral check
# to this neighborhood so review's own retained `cap 1` wording, which
# lives elsewhere in batch-mode.md, is never mistaken for a violation).
CAP_CONTEXT_KEYWORDS = ("verify_rework", "系譜", "hard cap")
# Digits that would represent an actual cap threshold if they appeared
# near the keywords above (the lineage cap is 1, the hard cap is 3); a
# bare `0` (an initial/unset counter value) is not a threshold and is not
# scanned for.
CAP_THRESHOLD_DIGITS = ("1", "3")


def _read(path):
    if not path.is_file():
        raise AssertionError(f"expected file to exist: {path}")
    return path.read_text(encoding="utf-8")


def _section(text, start_marker, end_marker):
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    return text[start:end]


def _strip_ws(text):
    # Strip ALL whitespace (not collapse to one space): this document
    # hard-wraps Japanese prose without a space at the break point, so a
    # phrase can straddle a line break with no literal space there
    # (matching the convention already used by
    # tests/test_batch_quiet_output_skill_wiring.py and
    # tests/test_develop_skill_rewiring.py's same-named helper).
    return re.sub(r"\s+", "", text)


def _contains(haystack, phrase):
    return _strip_ws(phrase) in _strip_ws(haystack)


def _extract_verify_failed_row(batch_mode_text):
    """Isolates the `verify.failed` table row in batch-mode.md's
    Non-packet gates table, so TS1/TS2's summary checks are scoped to
    that row and never accidentally match review's own row."""
    start = batch_mode_text.index("`verify.failed`")
    end = batch_mode_text.index("\n", start)
    return batch_mode_text[start:end]


def _extract_batch_yaml_block(schema_text):
    """Isolates the `batch:` mapping inside workflow-schema.md's Full
    Structure fenced YAML (from the line opening with the literal
    `batch:` key to the fence's closing ```` ``` ````), so the
    retired-key absence check (TS7) is scoped to the STRUCTURE itself and
    not to any historical mention elsewhere in the file (Test Notes)."""
    match = re.search(r"^batch:.*$", schema_text, re.MULTILINE)
    if match is None:
        raise ValueError("no top-level 'batch:' key found in workflow-schema.md")
    end = schema_text.index("```", match.start())
    return schema_text[match.start():end]


# ---------------------------------------------------------------------
# Matchers (each backed by a negative proof + non-vacuity guard below)
# ---------------------------------------------------------------------


def _states_lineage_counting_rule(section):
    """TS1: true iff `section` describes `failed_id_counts` as holding a
    cumulative per-failed-item-ID occurrence count, states the lineage
    cap's numeral (1), and states that an ID absent from every prior
    round's `failed_items` gets a fresh budget."""
    return (
        _contains(section, "failed_id_counts")
        and _contains(section, "累積出現回数")
        and _contains(section, "系譜 cap")
        and _contains(section, "値 1")
        and _contains(section, "新規予算を得る")
    )


def _states_hard_cap_independent_rule(section):
    """TS2: true iff `section` states a hard cap keyed to
    `batch.verify_rework.rounds`, its numeral (3), and that it is
    evaluated independently of the lineage cap."""
    return (
        _contains(section, "hard cap")
        and _contains(section, "rounds")
        and _contains(section, "値 3")
        and _contains(section, "独立")
    )


def _states_cap_reached_continues_without_stopping(section):
    """TS3: true iff `section` states that `verify.status` stays `failed`
    and the run proceeds into the retrospect phase without stopping."""
    return (
        _contains(section, "`verify.status`")
        and _contains(section, "`failed`")
        and _contains(section, "retrospect フェーズ")
        and (_contains(section, "停止しない") or _contains(section, "停止せず"))
    )


# Any of these appearing in the verify フェーズ section would mean an
# instruction to actually assign `deferred` to a leftover verify item --
# forbidden by AC-3. The negation sentence Design item 2 requires
# ("残った `failed_items` に `deferred` を与えない") is explicitly NOT one
# of these shapes.
FORBIDDEN_DEFERRED_ASSIGNMENTS = (
    "deferred にする",
    "deferred を設定",
    "deferred を与える",
    "status: deferred",
)


def _no_deferred_assignment_for_verify(section):
    """TS3: true iff `section` contains no instruction that actually
    assigns `deferred` to a verify item (the required negation sentence
    stating the opposite is not such an instruction)."""
    return not any(_contains(section, p) for p in FORBIDDEN_DEFERRED_ASSIGNMENTS)


def _row_summarizes_lineage_and_hard_cap_without_numeral(row):
    """TS1/TS2/TS12: true iff batch-mode.md's `verify.failed` row conveys
    the lineage-cap / hard-cap digest (ID recurrence, independent
    round-count cap, stays-failed-into-retrospect outcome) while carrying
    no numeral for either cap."""
    conveys_digest = (
        _contains(row, "verify_rework")
        and ("lineage" in row.lower() or _contains(row, "系譜"))
        and "hard cap" in row.lower()
        and ("independ" in row.lower() or _contains(row, "独立"))
        and _contains(row, "`failed`")
        and _contains(row, "retrospect")
    )
    return conveys_digest and _cap_numeral_absent_near_keywords(row)


def _cap_numeral_absent_near_keywords(text, window=60):
    """NFR1 / TS12: true iff no cap-threshold digit (1 or 3) appears
    within `window` characters of any of CAP_CONTEXT_KEYWORDS -- scoped so
    review's own retained `cap 1` wording elsewhere in the same file is
    never flagged (Test Notes)."""
    lowered = text
    pattern = "|".join(re.escape(k) for k in CAP_CONTEXT_KEYWORDS)
    for match in re.finditer(pattern, lowered, flags=re.IGNORECASE):
        start = max(0, match.start() - window)
        end = min(len(lowered), match.end() + window)
        neighborhood = lowered[start:end]
        for digit_match in re.finditer(r"\d+", neighborhood):
            if digit_match.group(0) in CAP_THRESHOLD_DIGITS:
                return False
    return True


def _batch_block_has_new_structure(block):
    """TS7: true iff the extracted `batch:` YAML block shows
    `review_rework_count` plus a nested `verify_rework` mapping with
    `rounds` and `failed_id_counts`."""
    return (
        "review_rework_count" in block
        and "verify_rework:" in block
        and "rounds" in block
        and "failed_id_counts" in block
    )


def _batch_block_lacks_retired_key_as_active_field(block):
    """TS7: true iff the extracted `batch:` YAML block contains no live
    `verify_rework_count:` mapping entry (a historical mention outside
    this structural block, e.g. in prose describing migration behaviour,
    is a different file location and is not scanned here)."""
    return re.search(r"verify_rework_count\s*:", block) is None


class TestSkillLineageCountingDefinition(unittest.TestCase):
    """AC-1: SKILL.md's verify フェーズ section defines the lineage count
    and its cap."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SKILL_PATH)
        cls.section = _section(cls.text, VERIFY_HEADING, RETROSPECT_HEADING)

    def test_lineage_counting_rule_is_stated(self):
        self.assertTrue(
            _states_lineage_counting_rule(self.section),
            "verify フェーズ section must state the failed_id_counts "
            "cumulative-count rule, lineage cap value 1, and the "
            "new-ID-gets-a-fresh-budget consequence",
        )

    def test_lineage_counter_key_is_the_new_history_field(self):
        self.assertIn("batch.verify_rework.failed_id_counts", self.section)

    def test_old_thin_counter_key_is_gone(self):
        self.assertNotIn("verify_rework_count", self.text)


class TestSkillHardCapDefinition(unittest.TestCase):
    """AC-2: SKILL.md's verify フェーズ section defines the hard cap and
    states its independence from the lineage cap."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SKILL_PATH)
        cls.section = _section(cls.text, VERIFY_HEADING, RETROSPECT_HEADING)

    def test_hard_cap_rule_is_stated(self):
        self.assertTrue(
            _states_hard_cap_independent_rule(self.section),
            "verify フェーズ section must state the hard cap on "
            "batch.verify_rework.rounds, its value 3, and that it is "
            "evaluated independently of the lineage cap",
        )

    def test_hard_cap_counter_key_is_the_new_history_field(self):
        self.assertIn("batch.verify_rework.rounds", self.section)


class TestSkillCapReachedOutcome(unittest.TestCase):
    """AC-3: cap reached does not stop the run; the old wording is gone;
    no instruction gives verify's leftovers `deferred`."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SKILL_PATH)
        cls.section = _section(cls.text, VERIFY_HEADING, RETROSPECT_HEADING)

    def test_cap_reached_continues_to_retrospect(self):
        self.assertTrue(
            _states_cap_reached_continues_without_stopping(self.section),
            "verify フェーズ section must state that verify.status stays "
            "failed and the run proceeds into retrospect without "
            "stopping",
        )

    def test_old_stop_and_report_wording_is_gone_from_whole_file(self):
        self.assertNotIn(OLD_STOP_AND_REPORT_WORDING, self.text)

    def test_no_deferred_assignment_for_verify_leftovers(self):
        self.assertTrue(
            _no_deferred_assignment_for_verify(self.section),
            "no wording may instruct assigning `deferred` to a verify "
            "leftover item",
        )

    def test_deferred_negation_sentence_is_present(self):
        # The required sentence itself: this is what makes the absence
        # check above meaningful rather than the negation simply never
        # having been written at all.
        self.assertIn("deferred", self.section)
        self.assertTrue(
            _contains(self.section, "`deferred` を与えない"),
            "the negation sentence itself must be present",
        )


class TestBatchModeVerifyFailedRowSummary(unittest.TestCase):
    """AC-1, AC-2: batch-mode.md's `verify.failed` row conveys the same
    digest (lineage cap + independent hard cap + stays-failed outcome)
    without restating either cap's numeral."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(BATCH_MODE_PATH)
        cls.row = _extract_verify_failed_row(cls.text)

    def test_row_summarizes_both_caps_without_a_numeral(self):
        self.assertTrue(
            _row_summarizes_lineage_and_hard_cap_without_numeral(self.row),
            f"verify.failed row must summarize the lineage/hard cap "
            f"digest with no numeral; got: {self.row!r}",
        )

    def test_row_still_points_at_full_detail(self):
        self.assertIn("skills/develop/SKILL.md", self.row)


class TestBatchYamlBlockStructure(unittest.TestCase):
    """AC-4: workflow-schema.md's `batch` block structure."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(SCHEMA_PATH)
        cls.block = _extract_batch_yaml_block(cls.text)

    def test_new_structure_is_present(self):
        self.assertTrue(
            _batch_block_has_new_structure(self.block),
            f"batch block must show review_rework_count and a nested "
            f"verify_rework.{{rounds,failed_id_counts}}; got: "
            f"{self.block!r}",
        )

    def test_retired_key_is_gone_from_the_structure(self):
        self.assertTrue(
            _batch_block_lacks_retired_key_as_active_field(self.block),
            "the batch block's YAML structure must not carry the "
            "retired verify_rework_count key as a live mapping entry",
        )

    def test_batch_activation_independence_is_retained(self):
        # The pre-existing "this block never activates batch mode" fact
        # must survive the restructure, regardless of which prose
        # location in the file now carries it.
        self.assertTrue(_contains(self.text, "--batch"))
        self.assertTrue(
            _contains(self.text, "活性")
            or _contains(self.text, "activate")
            or _contains(self.text, "有効化")
        )

    def test_retired_key_fallback_is_documented(self):
        # D7: a workflow.yaml missing the new keys is read as unset
        # (rounds 0, failed_id_counts empty); the old key is ignored. The
        # historical mention of the retired key name is expected OUTSIDE
        # the structural block (Test Notes), so this checks the whole
        # file rather than `self.block`.
        self.assertIn("verify_rework_count", self.text)
        self.assertTrue(
            _contains(self.text, "未計上") or _contains(self.text, "unset"),
            "the retired-key fallback behaviour must be documented",
        )


class TestVerifyCapNumeralIsSkillOnly(unittest.TestCase):
    """AC-5 (NFR1): the cap numerals live only in SKILL.md; batch-mode.md
    and workflow-schema.md carry no verify-cap numeral near the
    lineage/hard-cap vocabulary."""

    @classmethod
    def setUpClass(cls):
        cls.skill_text = _read(SKILL_PATH)
        cls.skill_section = _section(
            cls.skill_text, VERIFY_HEADING, RETROSPECT_HEADING
        )
        cls.batch_mode_text = _read(BATCH_MODE_PATH)
        cls.schema_text = _read(SCHEMA_PATH)

    def test_skill_states_both_numerals(self):
        self.assertTrue(_contains(self.skill_section, "値 1"))
        self.assertTrue(_contains(self.skill_section, "値 3"))

    def test_batch_mode_has_no_verify_cap_numeral(self):
        self.assertTrue(_cap_numeral_absent_near_keywords(self.batch_mode_text))

    def test_workflow_schema_has_no_verify_cap_numeral(self):
        self.assertTrue(_cap_numeral_absent_near_keywords(self.schema_text))


class TestLineageCountingMatcherCanFail(unittest.TestCase):
    """Test Notes: negative proof + non-vacuity guard for
    `_states_lineage_counting_rule` -- a forged section carrying the OLD
    fixed-counter wording must NOT satisfy the new matcher."""

    OLD_WORDING_FORGERY = (
        "（batch: 確認せず自動 rework。`batch.verify_rework_count == 0` なら "
        "interactive と同じ手順で rework-planner を dispatch し、カウンタを "
        "+1、既に 1 以上なら `failed` のまま報告して停止）。"
    )

    FORGED_NEW_WORDING = (
        "系譜 cap（値 1）: `batch.verify_rework.failed_id_counts` が保持する "
        "累積出現回数が 2 に達した時点で到達する。過去ラウンドの "
        "`failed_items` に現れなかった新規 ID は新規予算を得る。"
    )

    def test_old_wording_is_genuinely_the_old_shape(self):
        self.assertIn("batch.verify_rework_count", self.OLD_WORDING_FORGERY)
        self.assertNotIn("failed_id_counts", self.OLD_WORDING_FORGERY)

    def test_matcher_rejects_old_wording(self):
        self.assertFalse(_states_lineage_counting_rule(self.OLD_WORDING_FORGERY))

    def test_matcher_accepts_forged_new_wording(self):
        self.assertTrue(_states_lineage_counting_rule(self.FORGED_NEW_WORDING))


class TestHardCapMatcherCanFail(unittest.TestCase):
    """Test Notes: negative proof + non-vacuity guard for
    `_states_hard_cap_independent_rule`."""

    OLD_WORDING_FORGERY = (
        "`batch.verify_rework_count == 0` なら rework-planner を dispatch "
        "し、カウンタを +1、既に 1 以上なら `failed` のまま報告して停止。"
    )

    FORGED_NEW_WORDING = (
        "hard cap（値 3）: `batch.verify_rework.rounds` が 3 に達した時点で "
        "到達する。系譜 cap とは独立に評価する。"
    )

    def test_matcher_rejects_old_wording(self):
        self.assertFalse(_states_hard_cap_independent_rule(self.OLD_WORDING_FORGERY))

    def test_matcher_accepts_forged_new_wording(self):
        self.assertTrue(_states_hard_cap_independent_rule(self.FORGED_NEW_WORDING))


class TestCapReachedOutcomeMatcherCanFail(unittest.TestCase):
    """Test Notes: negative proof + non-vacuity guard for
    `_states_cap_reached_continues_without_stopping`."""

    OLD_WORDING_FORGERY = (
        "既に 1 以上なら `verify` を `failed` のまま報告して停止する。"
    )

    FORGED_NEW_WORDING = (
        "cap 到達時は走行を停止しない。`verify.status` は `failed` のまま "
        "次のフェーズ（retrospect フェーズ）へ進む。"
    )

    def test_matcher_rejects_old_wording(self):
        self.assertFalse(
            _states_cap_reached_continues_without_stopping(self.OLD_WORDING_FORGERY)
        )

    def test_matcher_accepts_forged_new_wording(self):
        self.assertTrue(
            _states_cap_reached_continues_without_stopping(self.FORGED_NEW_WORDING)
        )


class TestDeferredAssignmentMatcherCanFail(unittest.TestCase):
    """Test Notes: negative proof + non-vacuity guard for
    `_no_deferred_assignment_for_verify` -- a forged section that DOES
    instruct assigning `deferred` must be rejected."""

    FORGED_ASSIGNING_SECTION = (
        "cap 到達時は残った failed_items の status を deferred にする。"
    )

    FORGED_NEGATION_SECTION = (
        "cap 到達時は残った `failed_items` に `deferred` を与えない。"
    )

    def test_matcher_rejects_section_that_assigns_deferred(self):
        self.assertFalse(
            _no_deferred_assignment_for_verify(self.FORGED_ASSIGNING_SECTION)
        )

    def test_matcher_accepts_section_that_only_negates(self):
        self.assertTrue(
            _no_deferred_assignment_for_verify(self.FORGED_NEGATION_SECTION)
        )


class TestRowSummaryMatcherCanFail(unittest.TestCase):
    """Test Notes: negative proof + non-vacuity guard for
    `_row_summarizes_lineage_and_hard_cap_without_numeral`."""

    OLD_ROW_FORGERY = (
        "| `verify.failed` -- ... | Auto-rework once "
        "(`batch.verify_rework_count` cap 1); at cap, stay `failed` and "
        "stop with a report. Full detail: `skills/develop/SKILL.md` |"
    )

    FORGED_NEW_ROW = (
        "| `verify.failed` -- ... | Auto-rework, gated by two "
        "independently-evaluated caps on `batch.verify_rework`: a "
        "lineage cap (per failed-item-ID recurrence) and a hard cap "
        "(round count). At either cap, `verify.status` stays `failed` "
        "and the run proceeds to retrospect without stopping. Full "
        "detail: `skills/develop/SKILL.md` |"
    )

    FORGED_NEW_ROW_WITH_LEAKED_NUMERAL = FORGED_NEW_ROW.replace(
        "a lineage cap (per failed-item-ID recurrence)",
        "a lineage cap of 1 (per failed-item-ID recurrence)",
    )

    def test_matcher_rejects_old_row(self):
        self.assertFalse(
            _row_summarizes_lineage_and_hard_cap_without_numeral(self.OLD_ROW_FORGERY)
        )

    def test_matcher_accepts_forged_new_row(self):
        self.assertTrue(
            _row_summarizes_lineage_and_hard_cap_without_numeral(self.FORGED_NEW_ROW)
        )

    def test_matcher_rejects_new_row_wording_that_leaks_a_numeral(self):
        self.assertFalse(
            _row_summarizes_lineage_and_hard_cap_without_numeral(
                self.FORGED_NEW_ROW_WITH_LEAKED_NUMERAL
            )
        )


class TestCapNumeralNeighborhoodMatcherCanFail(unittest.TestCase):
    """Test Notes: negative proof + non-vacuity guard for
    `_cap_numeral_absent_near_keywords`, including the review-cap
    exemption (a `cap 1` far from any verify keyword must NOT trip it)."""

    def test_matcher_rejects_numeral_near_keyword(self):
        self.assertFalse(
            _cap_numeral_absent_near_keywords(
                "the batch.verify_rework hard cap value is 3 rounds"
            )
        )

    def test_matcher_accepts_text_with_no_numeral_near_keyword(self):
        self.assertTrue(
            _cap_numeral_absent_near_keywords(
                "batch.verify_rework tracks the lineage cap and hard cap "
                "history; " + ("padding " * 40) + "review's own cap 1 "
                "wording lives far away in the same document"
            )
        )

    def test_matcher_ignores_zero_valued_initial_counters(self):
        self.assertTrue(
            _cap_numeral_absent_near_keywords(
                "verify_rework:\n  rounds: 0\n  failed_id_counts: {}"
            )
        )


class TestBatchYamlBlockMatcherCanFail(unittest.TestCase):
    """Test Notes: negative proof + non-vacuity guard for
    `_batch_block_has_new_structure` and
    `_batch_block_lacks_retired_key_as_active_field`."""

    OLD_BLOCK = (
        "batch:\n"
        "  review_rework_count: 0\n"
        "  verify_rework_count: 0\n"
    )

    NEW_BLOCK = (
        "batch:\n"
        "  review_rework_count: 0\n"
        "  verify_rework:\n"
        "    rounds: 0\n"
        "    failed_id_counts: {}\n"
    )

    def test_structure_matcher_rejects_old_block(self):
        self.assertFalse(_batch_block_has_new_structure(self.OLD_BLOCK))

    def test_structure_matcher_accepts_new_block(self):
        self.assertTrue(_batch_block_has_new_structure(self.NEW_BLOCK))

    def test_retired_key_matcher_rejects_old_block(self):
        self.assertFalse(
            _batch_block_lacks_retired_key_as_active_field(self.OLD_BLOCK)
        )

    def test_retired_key_matcher_accepts_new_block(self):
        self.assertTrue(
            _batch_block_lacks_retired_key_as_active_field(self.NEW_BLOCK)
        )


class TestOwnModuleStdlibOnly(unittest.TestCase):
    """NFR3, NFR4: this module imports the standard library only."""

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
