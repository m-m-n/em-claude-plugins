"""Tests for task0003 (implement-failed-kind): stop condition 3 branches on
`failed_kind` for the `implement` step's `failed`, with a capped batch
auto-resume.

Covers task0003 Acceptance Criteria
(feature-docs/implement-failed-kind/tasks/task0003.md):

- AC-1 (FR6): Step B contains a block stating that, for the `implement`
  step's `failed`, stop condition 3 fires only when `failed_kind` reads
  the decision-required value, and that the field's definition and
  permitted values live in `references/workflow-schema.md`.
- AC-2 (FR6, FR2, NFR2): the block states the auto-resume write set in
  full -- `implement` back to `pending`, `failed_kind` back to null, the
  count incremented -- as one write set committed once with
  `commit-docs.sh` before the phase is executed, in that order.
- AC-3 (FR7): the block states the auto-resume is capped, that reaching
  the cap makes the failure the decision-required case so stop condition
  3 fires, that the report names the cap, and that no workflow.yaml write
  is made on the at-cap branch. It cites `references/workflow-schema.md`
  for the record's keys and defaults instead of restating them.
- AC-4 (FR7): the block states the performed count is monotonic per
  feature and is never reset.
- AC-5 (FR8): the block states the auto-resume applies to batch runs
  only, and that an interactive run stops on the external-cause value
  exactly as before.
- AC-6: the block states the auto-resume emits no batch terminal line,
  adds no stop reason code, and is not an `--once` phase boundary of its
  own.
- AC-7: the block states stop condition 3's `needs_update` trigger and
  its behaviour for the `review` and `verify` steps are unchanged.
- AC-8 (regression): the existing stop-condition-3 precedence block and
  the existing batch verify-cap exception block are unchanged, and the
  new block states it is independent of both. Asserted as the continued
  presence of their existing statements, including the former's
  exhaustiveness declaration and the latter's four bullets.
- AC-9 (FR6): the stop-condition list item for condition 3 points at the
  new block for the `implement` step's `failed`, while keeping its
  existing pointer to the `needs_update` carve-out.
- AC-10 (NFR1): the document names a `failed_kind` value only inside a
  branch condition, and carries no permitted-set enumeration, no meanings
  gloss and no missing-value read rule. A negative proof shows the
  detector fires against a synthetic copy that does restate them.
- AC-11 (NFR4): `python3 -m unittest discover -s tests` passes with the
  new module present, and the new module imports only the standard
  library.

Test isolation: every assertion below targets only
`em-workflow/skills/develop/SKILL.md` -- the sole file this task owns
(workflow-schema.md, batch-mode.md and batch-terminal-line.md are cited,
never restated or asserted against here).
"""

import ast
import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SKILL_PATH = os.path.join(REPO_ROOT, "em-workflow", "skills", "develop", "SKILL.md")

# --- section boundaries, taken verbatim from skills/develop/SKILL.md ------

STEP_B_HEADING = "## Step B: 自走ループ"
STEP_C_HEADING = (
    "## Step C: 完了処理（全 step completed — design のみ skipped 可 — "
    "か、cap 到達により verify が `failed` のまま残る場合のみ）"
)

STOP_CONDITION_3_START = "3. ある step の status が `failed` / `needs_update`"
STOP_CONDITION_4_START = "4. workflow.yaml の YAML parse エラー"

NEW_BLOCK_ANCHOR = "**batch: implement の failed_kind による自動再開**"
NEW_BLOCK_END = "| step | 実行方法 |"

PRECEDENCE_BLOCK_ANCHOR = "**停止条件 3 との優先関係**"
VERIFY_CAP_EXCEPTION_ANCHOR = "**batch: verify の cap 到達に対する停止条件の例外**"

# The real two-value vocabulary this task must never restate (IMPLEMENTATION.md
# D2's table: the two values the three write paths set).
FAILED_KIND_VALUES = ["infra", "decision"]


def _read(path):
    if not os.path.isfile(path):
        raise AssertionError(f"expected file to exist: {path}")
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _section(text, start_marker, end_marker):
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    return text[start:end]


def _strip_ws(text):
    # This document's Japanese prose hard-wraps without a space at the
    # break point, so markers must be matched after stripping ALL
    # whitespace (never after collapsing to a single space) -- the
    # convention already used by tests/test_failed_items_category.py and
    # tests/test_develop_skill_rewiring.py.
    return re.sub(r"\s+", "", text)


def _contains(haystack, phrase):
    return _strip_ws(phrase) in _strip_ws(haystack)


def _stripped_index(haystack, phrase):
    # Like str.index, but matched on the whitespace-stripped forms -- this
    # document hard-wraps mid-phrase, so a literal substring search (or a
    # literal .count()) can miss a match that spans a line break.
    return _strip_ws(haystack).index(_strip_ws(phrase))


def _stripped_count(haystack, phrase):
    return _strip_ws(haystack).count(_strip_ws(phrase))


# ---------------------------------------------------------------------
# AC-10 matchers (each backed by a negative proof + non-vacuity guard)
# ---------------------------------------------------------------------


def backtick_quoted_values_present(text):
    """Return the subset of FAILED_KIND_VALUES that occur backtick-quoted
    (e.g. `` `decision` ``) in `text` -- the shape a restated two-value
    vocabulary bullet list, table, or gloss would use."""
    return [v for v in FAILED_KIND_VALUES if f"`{v}`" in text]


def states_permitted_set_enumeration(text):
    """True iff BOTH failed_kind values appear backtick-quoted in `text` --
    presenting the two values together as the permitted set (forbidden by
    IMPLEMENTATION.md D7), as distinct from a single value named inside
    its own branch condition (D7 explicitly permits that shape, and AC-1 /
    AC-5 require exactly it)."""
    return len(backtick_quoted_values_present(text)) == 2


def states_meanings_gloss(text):
    """True iff `text` pairs a backtick-quoted failed_kind value with the
    external-cause / decision-required gloss IMPLEMENTATION.md D7 forbids
    a consumer from restating."""
    infra_gloss = _contains(text, "`infra`") and _contains(text, "外部要因")
    decision_gloss = _contains(text, "`decision`") and _contains(text, "要ユーザー判断")
    return infra_gloss or decision_gloss


def states_missing_value_read_rule(text):
    """True iff `text` states what an absent `failed_kind` reads as -- the
    missing-value read rule IMPLEMENTATION.md C1 assigns to
    workflow-schema.md alone."""
    return (
        _contains(text, "absent") or _contains(text, "無い場合")
    ) and _contains(text, "`decision`")


def states_definition_shaped_restatement(text):
    """AC-10: true iff `text` restates the vocabulary as a permitted-set
    enumeration, a meanings gloss, or a missing-value read rule -- the
    three definition-shaped artefacts IMPLEMENTATION.md D7 reserves to
    workflow-schema.md. A lone value named inside its own branch condition
    (D7's permitted shape) must NOT trip this."""
    return (
        states_permitted_set_enumeration(text)
        or states_meanings_gloss(text)
        or states_missing_value_read_rule(text)
    )


SYNTHETIC_RESTATED_DEFINITION = (
    "`failed_kind` の許容値は 2 つ: `infra`（外部要因）と `decision`"
    "（要ユーザー判断）。値が無い場合は `decision` として扱う。"
)

SYNTHETIC_BRANCH_CONDITION_MENTION = (
    "stop condition 3 fires only when the value is `decision`"
)


class SkillDocTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(SKILL_PATH)
        cls.step_b_section = _section(cls.text, STEP_B_HEADING, STEP_C_HEADING)
        cls.stop_condition_3_item = _section(
            cls.text, STOP_CONDITION_3_START, STOP_CONDITION_4_START
        )
        cls.new_block = _section(cls.text, NEW_BLOCK_ANCHOR, NEW_BLOCK_END)


# --- AC-1: narrowed firing condition + citation ----------------------------


class TestAC1NarrowedFiringConditionAndCitation(SkillDocTestCase):
    def test_states_fires_only_on_decision_required_value(self):
        self.assertTrue(
            _contains(
                self.new_block,
                "`implement` step の `status` が `failed` のとき、"
                "停止条件 3 が発火するのは `failed_kind` が要ユーザー判断"
                "の値を示す場合に限る",
            )
        )

    def test_cites_workflow_schema_for_definition(self):
        self.assertIn("references/workflow-schema.md", self.new_block)


# --- AC-2: full write set, ordering (write set, commit, then phase) -------


class TestAC2WriteSetAndOrdering(SkillDocTestCase):
    def test_states_implement_status_reset_to_pending(self):
        self.assertTrue(
            _contains(self.new_block, "`implement` の `status` を `pending` へ戻す")
        )

    def test_states_failed_kind_cleared_to_null(self):
        self.assertTrue(
            _contains(self.new_block, "`failed_kind` を null へ戻す")
        )

    def test_states_count_incremented(self):
        self.assertTrue(_contains(self.new_block, "実行済み回数を 1 増やす"))

    def test_states_single_commit_before_phase_execution(self):
        self.assertTrue(
            _contains(
                self.new_block,
                "この書き込みセットを、フェーズを実行する**前**に "
                "`commit-docs.sh` で 1 回だけコミットする",
            )
        )

    def test_ordering_write_set_then_commit_then_execute(self):
        # Independently assert the ORDER: the write-set + single-commit
        # statement must precede the "then execute the phase" statement --
        # a document that states the cap but not this ordering would still
        # permit an unbounded resume loop (Test Notes).
        write_and_commit_idx = _stripped_index(
            self.new_block,
            "この書き込みセットを、フェーズを実行する**前**に "
            "`commit-docs.sh` で 1 回だけコミットする",
        )
        execute_phase_idx = _stripped_index(
            self.new_block,
            "その後、Step B の通常シーケンスで implement フェーズを実行",
        )
        self.assertLess(write_and_commit_idx, execute_phase_idx)


# --- AC-3: cap, at-cap no-write, citation (not restatement) of defaults ---


class TestAC3CapAndAtCapNoWrite(SkillDocTestCase):
    def test_states_at_cap_treated_as_decision_required(self):
        self.assertTrue(
            _contains(
                self.new_block,
                "実行済み回数が cap に達している場合 → 要ユーザー判断の"
                "場合と同じ扱いとし、停止条件 3 が発火する",
            )
        )

    def test_states_report_names_the_cap(self):
        self.assertTrue(
            _contains(self.new_block, "レポートには cap への到達を理由として明記")
        )

    def test_states_no_write_on_at_cap_branch(self):
        # Independently asserted from the ordering test above (Test Notes):
        # the at-cap no-write statement is the second half of what keeps
        # the resume loop bounded.
        self.assertTrue(
            _contains(
                self.new_block,
                "この分岐では workflow.yaml への書き込みは一切行わない",
            )
        )

    def test_cites_schema_for_record_keys_instead_of_restating_defaults(self):
        self.assertIn("references/workflow-schema.md", self.new_block)
        # No restated default values (workflow-schema.md's job, per C3) --
        # the block never spells out the record's default numerals.
        self.assertNotIn("rounds: 0", self.new_block)
        self.assertNotIn("cap: 2", self.new_block)


# --- AC-4: monotonic, never reset ------------------------------------------


class TestAC4MonotonicNeverReset(SkillDocTestCase):
    def test_states_monotonic_never_reset(self):
        self.assertTrue(
            _contains(
                self.new_block,
                "実行済み回数は feature ごとに単調増加し、リセットされない",
            )
        )

    def test_states_mirrors_existing_rework_counters(self):
        self.assertTrue(_contains(self.new_block, "既存の rework カウンタと同様"))


# --- AC-5: batch-only; interactive unchanged -------------------------------


class TestAC5BatchOnlyInteractiveUnchanged(SkillDocTestCase):
    def test_states_interactive_stops_unchanged(self):
        self.assertTrue(
            _contains(
                self.new_block,
                "値が外部要因を示し、かつ対話実行の場合 → 停止条件 3 が"
                "従来どおり発火する",
            )
        )

    def test_states_fr8_batch_only_non_change(self):
        self.assertTrue(_contains(self.new_block, "FR8"))
        self.assertTrue(
            _contains(self.new_block, "対話実行の挙動はこの変更で一切変わらない")
        )


# --- AC-6: not a stop; no new stop reason code; not an --once boundary ----


class TestAC6NotAStopNotABoundary(SkillDocTestCase):
    def test_states_no_terminal_line_no_new_stop_reason_code(self):
        self.assertTrue(
            _contains(
                self.new_block,
                "自動再開は停止ではない: バッチ終端行を出さず、新しい "
                "stop reason code も追加しない",
            )
        )

    def test_states_not_an_once_boundary(self):
        self.assertTrue(
            _contains(
                self.new_block,
                "自動再開はそれ自体で `--once` のフェーズ境界にはならない",
            )
        )


# --- AC-7: needs_update / review / verify unaffected -----------------------


class TestAC7NeedsUpdateAndReviewVerifyUnaffected(SkillDocTestCase):
    def test_states_needs_update_and_review_verify_unaffected(self):
        self.assertTrue(
            _contains(
                self.new_block,
                "停止条件 3 のもう一方の発火条件（`needs_update`）、"
                "および `review` / `verify` step に対する挙動はこの "
                "block の対象外であり、一切変更しない",
            )
        )
        self.assertTrue(_contains(self.new_block, "SPEC assumption A3"))


# --- AC-8: existing blocks unchanged; independence declared ---------------


class TestAC8ExistingBlocksUnchangedAndIndependenceDeclared(SkillDocTestCase):
    def test_precedence_block_exhaustiveness_declaration_present(self):
        self.assertTrue(
            _contains(
                self.step_b_section,
                "この列挙は、所有 SSOT 自身がフェーズの自動再エントリを"
                "明記している遷移だけが対象という構成上の理由で網羅的で"
                "あり、他の遷移はこの除外の対象外。",
            )
        )

    def test_verify_cap_exception_four_bullets_present(self):
        bullets = [
            "停止条件 3（ある step の status が `failed` なら停止）に対する"
            "例外: この `failed` を停止理由にしない。",
            "停止条件 1（全 step が `completed` でないとターンを終えられ"
            "ない）に対する例外: verify がこの理由で `failed` のままで"
            "あっても、retrospect の完了後に Step C へ進み、走行を完了"
            "させてよい。",
            "非適用: 上記以外の理由による `failed`（implement の失敗、"
            "review の失敗、cap 未到達の verify 失敗）には適用されない。"
            "interactive にも適用されない。",
            "`verify.status` は `failed` のままであり、別 status も "
            "`deferred` も導入しない。",
        ]
        for bullet in bullets:
            self.assertTrue(
                _contains(self.step_b_section, bullet),
                f"expected bullet still present: {bullet!r}",
            )

    def test_new_block_declares_independence_from_both(self):
        self.assertTrue(
            _contains(
                self.new_block,
                "この block は上記「**停止条件 3 との優先関係**」および"
                "「**batch: verify の cap 到達に対する停止条件の例外**」"
                "のいずれとも独立しており、両ブロックの本文を変更しない。",
            )
        )

    def test_verify_cap_exception_own_independence_paragraph_present(self):
        # The verify-cap-exception block's own pre-existing statement that
        # IT is independent of the precedence block -- a different
        # sentence from this task's new independence statement, and one
        # this task must not disturb.
        self.assertTrue(
            _contains(
                self.step_b_section,
                "この例外は上記「**停止条件 3 との優先関係**」ブロックが"
                "定める自動再エントリ carve-out（`needs_update` に対する"
                "例外）とは独立しており、同ブロックの本文・網羅性宣言を"
                "変更しない。",
            )
        )

    def test_anchor_labels_reused_by_the_new_block_are_not_bare_duplicates(self):
        # Both pre-existing anchor labels are cited once more inside the
        # new block's own independence statement, on top of their
        # pre-existing occurrences (heading + existing pointer/citation).
        # Counted on the whitespace-stripped form since this document
        # hard-wraps mid-phrase (Test Notes).
        self.assertGreaterEqual(_stripped_count(self.text, PRECEDENCE_BLOCK_ANCHOR), 4)
        self.assertGreaterEqual(
            _stripped_count(self.text, VERIFY_CAP_EXCEPTION_ANCHOR), 3
        )


# --- AC-9: stop-condition-3 list item points at the new block -------------


class TestAC9StopConditionListPointsAtNewBlock(SkillDocTestCase):
    def test_keeps_existing_needs_update_pointer(self):
        self.assertTrue(
            _contains(
                self.stop_condition_3_item,
                "「**停止条件 3 との優先関係**」参照",
            )
        )

    def test_adds_pointer_to_new_block_for_implement_failed(self):
        self.assertTrue(
            _contains(
                self.stop_condition_3_item,
                "「**batch: implement の failed_kind による自動再開**」参照",
            )
        )

    def test_names_implement_and_failed_kind_in_the_narrowing_pointer(self):
        self.assertIn("`implement`", self.stop_condition_3_item)
        self.assertIn("`failed_kind`", self.stop_condition_3_item)


# --- AC-10: no restated vocabulary; negative proof + tolerance -------------


class TestAC10NoRestatedVocabulary(SkillDocTestCase):
    def test_new_block_has_no_restated_definition(self):
        self.assertFalse(states_definition_shaped_restatement(self.new_block))

    def test_stop_condition_item_has_no_restated_definition(self):
        self.assertFalse(
            states_definition_shaped_restatement(self.stop_condition_3_item)
        )

    def test_new_block_has_no_backtick_quoted_values_at_all(self):
        # This task's chosen shape never names either raw value literally
        # (it uses the descriptive "要ユーザー判断" / "外部要因" glosses in
        # its own branch-condition prose instead), so the stronger,
        # simpler check also holds.
        self.assertEqual(backtick_quoted_values_present(self.new_block), [])


class TestDetectorNegativeProofAndTolerance(unittest.TestCase):
    """Test Notes: the AC-10 detector must fire on a synthetic restatement
    but tolerate the single-value branch-condition mentions AC-1 / AC-5
    require (IMPLEMENTATION.md D7's permitted shape)."""

    def test_negative_proof_fires_on_synthetic_restated_definition(self):
        self.assertTrue(
            states_definition_shaped_restatement(SYNTHETIC_RESTATED_DEFINITION)
        )

    def test_detector_tolerates_single_value_branch_condition_mention(self):
        self.assertFalse(
            states_definition_shaped_restatement(SYNTHETIC_BRANCH_CONDITION_MENTION)
        )

    def test_permitted_set_enumeration_matcher_can_fail_and_pass(self):
        self.assertFalse(states_permitted_set_enumeration("`decision` only"))
        self.assertTrue(states_permitted_set_enumeration("`decision` and `infra`"))

    def test_meanings_gloss_matcher_can_fail_and_pass(self):
        self.assertFalse(states_meanings_gloss("`decision` requires a human"))
        self.assertTrue(states_meanings_gloss("`decision`（要ユーザー判断）"))
        self.assertTrue(states_meanings_gloss("`infra`（外部要因）"))

    def test_missing_value_read_rule_matcher_can_fail_and_pass(self):
        self.assertFalse(states_missing_value_read_rule("`decision` fires stop 3"))
        self.assertTrue(
            states_missing_value_read_rule("absent -> read as `decision`")
        )
        self.assertTrue(
            states_missing_value_read_rule("値が無い場合は `decision` として扱う")
        )


# --- AC-11: whole suite passes (exercised by the runner, not here); this --
# --- module imports the standard library only ------------------------------


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
