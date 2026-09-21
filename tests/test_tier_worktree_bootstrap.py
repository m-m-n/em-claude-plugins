"""Tests for task0009 (task-tier-reduction): securing the integration
branch/worktree inside the tier-decision procedure before the tier record is
persisted, and the single-creator statement across the two documents that
can create that worktree.

Covers task0009 Acceptance Criteria
(feature-docs/task-tier-reduction/tasks/task0009.md):

- AC-1: in `skills/develop/SKILL.md`, the integration branch/worktree is
  secured (reachable from both the new-feature route and the
  bootstrap-incomplete route, since both converge into the shared
  tier-decision procedure) before the procedure's persistence step, and the
  persistence step's write target and its `commit-docs.sh` argument are that
  worktree's absolute path.
- AC-2: the securing step runs after the no-work stop check, and the
  document states that a no-work stop creates neither a branch nor a
  worktree.
- AC-3: `references/phases/create-spec-phase.md` section 3 states the
  integration worktree is already secured by Step A and that this phase
  reuses it, naming the single case in which the phase creates one itself
  (a caller that did not come through Step A).
- AC-4: no sentence in either document claims unconditional creation of the
  integration worktree at a point that contradicts AC-1's ordering.
- AC-5: this module asserts AC-1 through AC-4 against the raw text of both
  documents; every matcher is paired with a negative proof against a forged
  sample carrying the pre-change ordering, plus a non-vacuity guard.
- AC-6 (not unit-testable in this module): `python3 -m unittest discover -s
  tests` reporting no failure beyond the integration branch's base commit is
  a whole-suite property verified by running the suite, not a text
  assertion this module can encode.

Test Notes: all criteria are document-conformance assertions over raw file
text, following the pattern established by
`tests/test_tier_decision_step_a.py` (helper matcher functions independent
of any other test module, `_strip_ws` normalization for hard-wrapped
Japanese prose, a `Test*MatchersCanFail` class per matcher proving it fires
on a forged sample). The ordering assertion is positional: it compares the
byte offset (in the whitespace-stripped text, which preserves relative
character order) of the securing step's own numbered-heading marker against
the offsets of the no-work-stop and persistence steps' markers -- never by
checking for keyword presence alone, which would pass vacuously on a
document that mentions all three concepts in the wrong order. The module
imports standard-library modules only (NFR7).

D3a region-ownership note: this task owns, inside `skills/develop/SKILL.md`,
only Step A's worktree-securing step and its ordering relative to the
no-work stop and the persistence step; and inside
`references/phases/create-spec-phase.md`, only section 3's bootstrap
worktree ordering. It does not touch the tier-decision procedure's
two-reading/evaluation steps (task0013's region) or the create-spec
transcription section (also task0013's region) -- a region-ownership
regression class below pins anchor text from those regions as unchanged by
this task's diff.
"""

import ast
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"
SKILL_PATH = PLUGIN_ROOT / "skills" / "develop" / "SKILL.md"
CREATE_SPEC_PHASE_PATH = PLUGIN_ROOT / "references" / "phases" / "create-spec-phase.md"

TIER_SECTION_START = "### tier 決定"
STEP_A5_START = "## Step A.5"

SECTION3_START = "## 3. Bootstrap and durable-state boundary"
SECTION4_START = "## 4. Reconcile on entry"


def _read(path):
    if not path.is_file():
        raise AssertionError(f"expected file to exist: {path}")
    return path.read_text(encoding="utf-8")


def _strip_ws(text):
    # Strip ALL whitespace (not collapse to one space): Japanese prose in
    # these documents is hard-wrapped without a space at the break point, so
    # a phrase spanning a wrap needs every whitespace character removed to
    # match reliably (same convention as tests/test_tier_decision_step_a.py's
    # helper of the same name).
    return re.sub(r"\s+", "", text)


def _contains(text, phrase):
    """True iff `phrase` occurs in `text` once both are whitespace-stripped
    -- safe against the source's hard-wrapping of Japanese prose and against
    a code span split across a line break."""
    return _strip_ws(phrase) in _strip_ws(text)


def _section(text, start_marker, end_marker):
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    return text[start:end]


SKILL_TEXT = _read(SKILL_PATH)
CREATE_SPEC_PHASE_TEXT = _read(CREATE_SPEC_PHASE_PATH)

TIER_SECTION = _section(SKILL_TEXT, TIER_SECTION_START, STEP_A5_START)
BOOTSTRAP_SECTION = _section(CREATE_SPEC_PHASE_TEXT, SECTION3_START, SECTION4_START)


# ---------------------------------------------------------------------------
# AC-1 / AC-2: positional ordering of the securing step relative to the
# no-work stop and the persistence step, inside the tier-decision procedure.
# ---------------------------------------------------------------------------

NO_WORK_STEP_MARKER = "3. **no-work 停止**"
SECURING_STEP_MARKER = "7. **統合 branch/worktree の確保**"
PERSISTENCE_STEP_MARKER = "8. **永続化**"


def _ordering_offsets(text):
    """Byte offsets (in whitespace-stripped text) of the three step
    markers, or None for any marker that is absent -- absence must never be
    silently treated as "order satisfied"."""
    stripped = _strip_ws(text)
    offsets = []
    for marker in (NO_WORK_STEP_MARKER, SECURING_STEP_MARKER, PERSISTENCE_STEP_MARKER):
        idx = stripped.find(_strip_ws(marker))
        if idx == -1:
            return None
        offsets.append(idx)
    return tuple(offsets)


def _securing_step_after_no_work_and_before_persistence(text):
    offsets = _ordering_offsets(text)
    if offsets is None:
        return False
    no_work_idx, securing_idx, persistence_idx = offsets
    return no_work_idx < securing_idx < persistence_idx


def _no_work_stop_states_no_branch_or_worktree_created(text):
    return _contains(
        text,
        "no-work 停止はブランチも worktree も作らずに走行を終える",
    )


def _routes_converge_into_shared_procedure(text):
    # Pre-existing sentence (unchanged by this task): both the new-feature
    # route and the bootstrap-incomplete ("存在しない") route converge into
    # this one shared tier-decision procedure, so a single securing step
    # placed inside it covers both routes at once.
    return _contains(
        text,
        "「ブートストラップ状態の判定」の「存在しない」\n   分岐（create-spec への再突入直前）の両方からここに合流する。",
    ) or _contains(
        text,
        "ブートストラップ状態の判定」の「存在しない」分岐（create-spec への再突入直前）の両方からここに合流する。",
    )


ABS_WORKTREE_PATH = (
    "$PROJECT_ROOT/.claude/worktrees/em-workflow/{feature}/integration"
)


def _persistence_step_targets_worktree_absolute_path(text):
    offsets = _ordering_offsets(text)
    if offsets is None:
        return False
    persistence_idx_stripped = offsets[2]
    stripped = _strip_ws(text)
    persistence_block = stripped[persistence_idx_stripped:]
    return (
        _strip_ws(ABS_WORKTREE_PATH) in persistence_block
        and _strip_ws("feature-docs/{feature}/phase-state/tier.yaml") in persistence_block
        and _strip_ws("commit-docs.sh") in persistence_block
        and _strip_ws("同じ worktree の絶対パスを対象にした") in persistence_block
    )


class TestAC1Ordering(unittest.TestCase):
    def test_tier_section_exists(self):
        self.assertIn(TIER_SECTION_START, SKILL_TEXT)

    def test_securing_step_present(self):
        self.assertTrue(_contains(TIER_SECTION, SECURING_STEP_MARKER))

    def test_securing_step_between_no_work_stop_and_persistence(self):
        self.assertTrue(
            _securing_step_after_no_work_and_before_persistence(TIER_SECTION)
        )

    def test_both_routes_converge_into_the_shared_procedure(self):
        self.assertTrue(_routes_converge_into_shared_procedure(TIER_SECTION))

    def test_persistence_step_targets_worktree_absolute_path(self):
        self.assertTrue(
            _persistence_step_targets_worktree_absolute_path(TIER_SECTION)
        )


class TestAC2NoWorkStopCreatesNothing(unittest.TestCase):
    def test_securing_step_runs_after_no_work_stop(self):
        offsets = _ordering_offsets(TIER_SECTION)
        self.assertIsNotNone(offsets)
        no_work_idx, securing_idx, _ = offsets
        self.assertLess(no_work_idx, securing_idx)

    def test_no_work_stop_states_no_branch_or_worktree_created(self):
        self.assertTrue(
            _no_work_stop_states_no_branch_or_worktree_created(TIER_SECTION)
        )


# ---------------------------------------------------------------------------
# Negative proofs: (a) the actual pre-change text (this task's defect, where
# the securing step did not exist at all), and two forged reorderings of the
# CURRENT text -- one with the securing step spliced in after the
# persistence step, one with it spliced in before the no-work stop.
# ---------------------------------------------------------------------------

# The tier-decision procedure's steps 3-7 exactly as they read before this
# task's change (no securing step existed anywhere in the procedure).
PRE_CHANGE_TIER_STEPS = """3. **no-work 停止**: 2. の Codex 事前調査が「作業が残っていない」旨を
   報告した場合、判定を先へ進めず、いかなる workflow step も実行せずに
   ここで走行を終える。結果は停止状態を持ち、workflow.yaml の step が
   1 つも有効になっていないことを示す `references/batch-terminal-line.md`
   定義のセンチネル値を持ち、再開ガイダンスは空にせず「再開は不要」で
   ある旨を明文で述べる。Codex 事前調査の根拠は同ガイダンスに含める。
   この停止点の名は `no-work-required`（ハイフン区切り）とする。対応する
   reason code の文字列は `references/batch-terminal-line.md` の所有物で
   あり、このファイルには一切書かない。
4. **2 本の判定根拠**: 作業が残っている場合、判定スキルを同じ質問セットに
   対して 2 回呼ぶ — 1 回目はタスク記述のみを基準に、2 回目は 2. の
   Codex 見積もりをその state に合流させて。両方の読み取り結果を、それぞれの
   観測値とともに決定の根拠として記録する。
5. **評価**: 集めた値を評価器（IMPLEMENTATION.md Shared Components
   `scripts/decide-tier.py` 参照）へ渡し、返された tier を採用する。
6. **可用性フォールバック**: 可用性は `tier-rules.yaml` のフォールバック表を
   そのまま適用して解決する（閾値の値・表の行はここに書き写さない）。判定
   スキルの終了ステータスが非 0 の場合はすべて「判定スキル使用不可」として
   扱う。判定スキルが使用不可、または Codex 事前調査が使用不可で 2 本の
   判定結果が割れた場合、あるいはフォールバック表が解決しないその他の条件は
   すべて、何も引かない tier（`full`）を採用する。
7. **永続化**: 決定した直後、他の何よりも先に、
   `feature-docs/{feature}/phase-state/tier.yaml` へ記録し、既存の
   `commit-docs.sh` でコミットする（スクリプト変更は不要 —
   `commit-docs.sh` は既に feature-docs ツリー全体をステージする）。
   フィールドの定義は `references/phase-state.md` の tier decision
   persistence 節参照。
"""


def _split_current_steps(text):
    """Split the CURRENT (post-change) tier-decision procedure text into its
    step-3 (no-work stop), step-7 (securing) and step-8 (persistence, to end
    of section) blocks, plus everything before step 3 -- used to build
    reordered forgeries out of the real current content rather than
    hand-written placeholder text."""
    step4_marker = "4. **2 本の判定根拠**"
    before_step3 = text[: text.index(NO_WORK_STEP_MARKER)]
    step3_block = text[text.index(NO_WORK_STEP_MARKER) : text.index(step4_marker)]
    middle_4_to_6 = text[text.index(step4_marker) : text.index(SECURING_STEP_MARKER)]
    step7_block = text[text.index(SECURING_STEP_MARKER) : text.index(PERSISTENCE_STEP_MARKER)]
    step8_block = text[text.index(PERSISTENCE_STEP_MARKER) :]
    return before_step3, step3_block, middle_4_to_6, step7_block, step8_block


(
    _BEFORE_STEP3,
    _STEP3_BLOCK,
    _MIDDLE_4_TO_6,
    _STEP7_BLOCK,
    _STEP8_BLOCK,
) = _split_current_steps(TIER_SECTION)

# Forgery 1: securing step (7) spliced in AFTER the persistence step (8) --
# violates "before the persistence step" (AC-1).
FORGED_SECURING_AFTER_PERSISTENCE = (
    _BEFORE_STEP3 + _STEP3_BLOCK + _MIDDLE_4_TO_6 + _STEP8_BLOCK + _STEP7_BLOCK
)

# Forgery 2: securing step (7) spliced in BEFORE the no-work stop (3) --
# violates "after the no-work stop check" (AC-2).
FORGED_SECURING_BEFORE_NO_WORK = (
    _BEFORE_STEP3 + _STEP7_BLOCK + _STEP3_BLOCK + _MIDDLE_4_TO_6 + _STEP8_BLOCK
)


class TestAC1AC2MatchersCanFail(unittest.TestCase):
    """Negative proofs: the ordering matcher fails on (a) the actual
    pre-change text, where the securing step is entirely absent, and on two
    forged reorderings of the current text."""

    def test_ordering_matcher_fails_on_pre_change_text(self):
        self.assertFalse(
            _securing_step_after_no_work_and_before_persistence(
                PRE_CHANGE_TIER_STEPS
            )
        )

    def test_no_work_stop_disclaimer_absent_from_pre_change_text(self):
        self.assertFalse(
            _no_work_stop_states_no_branch_or_worktree_created(
                PRE_CHANGE_TIER_STEPS
            )
        )

    def test_ordering_matcher_fails_on_securing_after_persistence_forgery(self):
        self.assertFalse(
            _securing_step_after_no_work_and_before_persistence(
                FORGED_SECURING_AFTER_PERSISTENCE
            )
        )

    def test_ordering_matcher_fails_on_securing_before_no_work_forgery(self):
        self.assertFalse(
            _securing_step_after_no_work_and_before_persistence(
                FORGED_SECURING_BEFORE_NO_WORK
            )
        )

    def test_securing_after_no_work_check_alone_also_fails_on_before_forgery(self):
        offsets = _ordering_offsets(FORGED_SECURING_BEFORE_NO_WORK)
        self.assertIsNotNone(offsets)
        no_work_idx, securing_idx, _ = offsets
        self.assertGreater(securing_idx, -1)
        self.assertFalse(no_work_idx < securing_idx)

    def test_real_current_text_is_nonvacuously_different_from_both_forgeries(self):
        # Non-vacuity: the real (current) text must actually differ from
        # each forgery -- otherwise a pass above would prove nothing.
        self.assertNotEqual(TIER_SECTION, FORGED_SECURING_AFTER_PERSISTENCE)
        self.assertNotEqual(TIER_SECTION, FORGED_SECURING_BEFORE_NO_WORK)
        self.assertNotEqual(TIER_SECTION, PRE_CHANGE_TIER_STEPS)
        # And the real text passes where the forgeries fail.
        self.assertTrue(
            _securing_step_after_no_work_and_before_persistence(TIER_SECTION)
        )


class TestAC1AC2RoutesAndPathMatchersCanFail(unittest.TestCase):
    def test_routes_converge_matcher_fails_on_forged_copy(self):
        self.assertFalse(
            _routes_converge_into_shared_procedure("何も書いていない")
        )

    def test_persistence_target_matcher_fails_on_forged_copy(self):
        self.assertFalse(
            _persistence_step_targets_worktree_absolute_path(
                PRE_CHANGE_TIER_STEPS
            )
        )

    def test_persistence_target_matcher_fails_when_path_missing(self):
        forged = TIER_SECTION.replace(
            "$PROJECT_ROOT/.claude/worktrees/em-workflow/{feature}/integration",
            "",
        )
        self.assertFalse(_persistence_step_targets_worktree_absolute_path(forged))


# ---------------------------------------------------------------------------
# AC-3: create-spec-phase.md section 3 -- reuse, and the single case in
# which the phase creates the worktree itself.
# ---------------------------------------------------------------------------


def _states_worktree_already_secured_by_step_a(text):
    return _contains(text, "already secured") and _contains(
        text, "Step A of `skills/develop/SKILL.md`"
    )


def _states_phase_reuses_it(text):
    return _contains(text, "This phase **reuses** that branch/worktree")


def _names_single_creation_case(text):
    return _contains(
        text, "a caller that did not come through Step A"
    )


class TestAC3BootstrapReuse(unittest.TestCase):
    def test_section3_exists(self):
        self.assertIn(SECTION3_START, CREATE_SPEC_PHASE_TEXT)

    def test_states_worktree_already_secured_by_step_a(self):
        self.assertTrue(
            _states_worktree_already_secured_by_step_a(BOOTSTRAP_SECTION)
        )

    def test_states_phase_reuses_it(self):
        self.assertTrue(_states_phase_reuses_it(BOOTSTRAP_SECTION))

    def test_names_single_creation_case(self):
        self.assertTrue(_names_single_creation_case(BOOTSTRAP_SECTION))

    def test_no_second_differently_worded_creation_case_exists(self):
        # "the single case" (AC-3): the not-through-Step-A phrasing may be
        # restated for clarity (intro paragraph + numbered step), but no
        # OTHER, differently-worded case for the phase creating the
        # worktree itself may appear anywhere in the section.
        self.assertGreaterEqual(
            _strip_ws(BOOTSTRAP_SECTION).count(
                _strip_ws("a caller that did not come through Step A")
            ),
            1,
        )
        self.assertNotIn("gate_id: create-spec.worktree", BOOTSTRAP_SECTION)
        self.assertEqual(BOOTSTRAP_SECTION.count("creates one"), 1)


class TestAC3MatchersCanFail(unittest.TestCase):
    def test_secured_by_step_a_matcher_fails_on_forged_copy(self):
        self.assertFalse(
            _states_worktree_already_secured_by_step_a("何も書いていない")
        )

    def test_reuse_matcher_fails_on_forged_copy(self):
        self.assertFalse(_states_phase_reuses_it("何も書いていない"))

    def test_single_case_matcher_fails_on_forged_copy(self):
        self.assertFalse(_names_single_creation_case("nothing written here"))

    def test_matchers_fail_on_the_actual_pre_change_section3(self):
        pre_change_section3 = (
            "1. If the feature name is already unambiguous from the input, "
            "validate it\n   and secure the integration branch/worktree.\n"
            "2. If the feature name itself is undetermined, the orchestrator "
            "asks that\n   alone first, before anything else.\n"
            "3. **Immediately after the feature name is fixed**, create the "
            "integration\n   worktree and initialize "
            "`feature-docs/{feature}/phase-state/create-spec.yaml`.\n"
        )
        self.assertFalse(
            _states_worktree_already_secured_by_step_a(pre_change_section3)
        )
        self.assertFalse(_states_phase_reuses_it(pre_change_section3))
        self.assertFalse(_names_single_creation_case(pre_change_section3))


# ---------------------------------------------------------------------------
# AC-4: no sentence in either document claims unconditional creation of the
# integration worktree at a point that contradicts AC-1's ordering.
# ---------------------------------------------------------------------------

# The exact pre-change sentences this task removed -- an unconditional
# "validate it and secure ..." claim, and an unconditional "create the
# integration worktree" claim, both from the old section 3.
OLD_UNCONDITIONAL_SECURE_PHRASE = (
    "validate it and secure the integration branch/worktree."
)
OLD_UNCONDITIONAL_CREATE_PHRASE = "create the integration\n   worktree and initialize"


def _no_unconditional_creation_claim_remains(text):
    return not _contains(text, OLD_UNCONDITIONAL_SECURE_PHRASE) and not _contains(
        text, OLD_UNCONDITIONAL_CREATE_PHRASE
    )


class TestAC4SingleOrdering(unittest.TestCase):
    def test_bootstrap_section_no_longer_claims_unconditional_creation(self):
        self.assertTrue(
            _no_unconditional_creation_claim_remains(BOOTSTRAP_SECTION)
        )

    def test_tier_section_no_longer_claims_unconditional_creation_at_wrong_point(
        self,
    ):
        # AC-1's ordering (securing after no-work stop, before persistence)
        # already proves there is exactly one place the tier-decision
        # procedure secures the worktree; this asserts no second,
        # unconditional creation claim exists anywhere else in the section.
        occurrences = _strip_ws(TIER_SECTION).count(_strip_ws(SECURING_STEP_MARKER))
        self.assertEqual(occurrences, 1)


class TestAC4MatchersCanFail(unittest.TestCase):
    def test_unconditional_claim_matcher_fires_on_the_actual_pre_change_text(self):
        pre_change_section3 = (
            "1. If the feature name is already unambiguous from the input, "
            "validate it and secure the integration branch/worktree.\n"
            "3. **Immediately after the feature name is fixed**, create the "
            "integration\n   worktree and initialize something.\n"
        )
        self.assertFalse(
            _no_unconditional_creation_claim_remains(pre_change_section3)
        )

    def test_real_bootstrap_section_is_nonvacuously_nonempty(self):
        self.assertGreater(len(BOOTSTRAP_SECTION), 200)


# ---------------------------------------------------------------------------
# Region-ownership regression (D3a): the tier-decision procedure's
# two-reading/evaluation steps and the create-spec transcription section
# belong to task0013, not this task. Pinned by anchor text so an unrelated
# future edit by task0013 to those regions does not spuriously fail this
# module once merged, while still proving this task's own diff left them
# untouched.
# ---------------------------------------------------------------------------

TWO_READINGS_ANCHOR = (
    "4. **2 本の判定根拠**: 作業が残っている場合、判定スキルを同じ質問セットに\n"
    "   対して 2 回呼ぶ — 1 回目は decision-basis `description_only`\n"
    "   （タスク記述のみを基準に）、2 回目は decision-basis\n"
    "   `description_plus_code`（2. の Codex 見積もりをその state に合流させ\n"
    "   て）。この 2 つの識別子は `tier-rules.yaml` の `decision_basis` 値で\n"
    "   あり、ここでは新しい識別子を作らない。両方の読み取り結果を、それぞれの\n"
    "   basis ラベルと観測値とともに決定の根拠として記録する。"
)
EVALUATION_ANCHOR = (
    "5. **評価**: 集めた 2 本の読みを 1 回の呼び出しで評価器\n"
    "   （IMPLEMENTATION.md Shared Components `scripts/decide-tier.py` 参照）へ\n"
    "   渡す。評価器は各読みがそれぞれ決定する tier を比較し、両者が異なる\n"
    "   tier に評価された場合は何も引かない tier（`full`）を返す — この\n"
    "   不一致解決規則は評価器の入力契約が持ち、ここでは繰り返さない。返された\n"
    "   tier を採用する。"
)
TRANSCRIPTION_ANCHOR = (
    "**Tier transcription**: Step A of `skills/develop/SKILL.md` makes the tier\n"
    "decision immediately after the feature name is fixed (section 3) and\n"
    "persists it to `feature-docs/{feature}/phase-state/tier.yaml`"
)


class TestRegionOwnershipRegression(unittest.TestCase):
    def test_two_readings_step_unchanged(self):
        self.assertIn(TWO_READINGS_ANCHOR, SKILL_TEXT)

    def test_evaluation_step_unchanged(self):
        self.assertIn(EVALUATION_ANCHOR, SKILL_TEXT)

    def test_transcription_section_unchanged(self):
        self.assertIn(TRANSCRIPTION_ANCHOR, CREATE_SPEC_PHASE_TEXT)


class TestRegionOwnershipMatchersCanFail(unittest.TestCase):
    def test_anchor_checks_fail_on_a_document_missing_them(self):
        forged = "この文書には何も含まれていない。"
        self.assertNotIn(TWO_READINGS_ANCHOR, forged)
        self.assertNotIn(EVALUATION_ANCHOR, forged)
        self.assertNotIn(TRANSCRIPTION_ANCHOR, forged)


# ---------------------------------------------------------------------------
# AC-5: this module's own hygiene (stdlib-only imports).
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
