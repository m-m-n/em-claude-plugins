"""Tests for task0011 (task-tier-reduction, review-round-1 rework): the
tier-upgrade procedure's authorization record, the `reduced` -> `full`
branch's re-entry ordering, and the automatic-re-entry carve-out /
`--once` phase-boundary consistency.

Covers task0011 Acceptance Criteria
(feature-docs/task-tier-reduction/tasks/task0011.md):

- AC-1: both upgrade branches write the `phase-state/rework.yaml`
  authorization record -- interruption reason, `origin_kind` / `origin_id`
  taken from the trigger, recorded-at commit, unconsumed, re-planning
  authorized -- and commit it with `commit-docs.sh` before any step status
  is set; the document states that ordering explicitly.
- AC-2: `phase-state.md` names the tier-upgrade procedure as a writer of
  that record alongside rework's spec-change transition, introducing no
  new field and no new vocabulary value, and `workflow-patch.md`'s
  re-planning path names the tier upgrade as a second transition that can
  produce an authorized record.
- AC-3: the `reduced` -> `full` branch re-runs create-spec, design and
  create-plan in that order, and states that create-spec's re-run is what
  produces the requirements document before create-plan re-enters.
- AC-4: no sentence attributes the requirements document's absence to the
  design step's skip; the requirements document is attributed to
  create-spec's subtraction and the implementation plan to create-plan's.
- AC-5: the automatic-re-entry carve-out's tier-upgrade entry covers both
  the create-spec and the create-plan re-entry; the enumeration's stated
  count equals the number of transitions listed; the `--once`
  phase-boundary table's automatic-re-entry row names the same transition.
- AC-6/AC-7: this module is discovered by
  `python3 -m unittest discover -s tests`, imports only standard-library
  modules, and pairs each matcher with a negative proof and a non-vacuity
  guard.

Test isolation: helper functions and constants are redeclared locally
rather than imported from sibling test modules (Cross-module isolation
convention, matching tests/test_tier_reduction_develop_loop.py and
tests/test_tier_decision_step_a.py).

Matcher -> negative-proof inventory (Test Notes: every matcher carries a
negative proof over a forged/synthetic sample plus a non-vacuity guard):

- `_record_precedes_status_writes` (AC-1 ordering): negative proof is
  TestRecordOrderingMatcherCanFail.test_matcher_detects_swapped_order --
  Test Notes: "the test compares the byte offset of the record-writing
  sentence against the offsets of the status-setting sentences within
  each branch, and the negative proof is a forged sample with the two
  swapped."
- `_auth_record_states_required_fields` (AC-1 fields): negative proof is
  TestAuthRecordFieldsMatcherCanFail.test_matcher_detects_a_missing_field.
- `_phase_state_names_tier_upgrade_as_second_writer` /
  `_workflow_patch_names_tier_upgrade_as_re_planning_transition` (AC-2):
  negative proofs are the respective `TestAC2...MatcherCanFail` classes.
- `_reduced_full_orders_create_spec_design_create_plan` (AC-3 ordering):
  negative proof is
  TestReducedFullOrderingMatcherCanFail.test_matcher_detects_swapped_order.
- `_no_sentence_attributes_requirements_absence_to_design_skip` (AC-4):
  negative proof is the pre-task0011 text itself, captured verbatim
  (Test Notes: "AC-4's negative proof is the current text, which
  attributes both documents to the design skip").
- `_carve_out_counts_match` (AC-5 count): negative proof is
  TestCarveOutCountMatcherCanFail.test_matcher_detects_a_count_mismatch --
  Test Notes: "the count assertion extracts the listed transitions and
  the stated count from the same paragraph and compares them, so that a
  future edit adding a transition without touching the count fails."
- `_tier_upgrade_bullet_covers_both_reentries` /
  `_once_table_row_names_tier_upgrade_transition` (AC-5 carve-out /
  once-table consistency): negative proofs are the respective
  `TestAC5...MatcherCanFail` classes.
"""

import re
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "em-workflow"
SKILL_PATH = PLUGIN_ROOT / "skills" / "develop" / "SKILL.md"
PHASE_STATE_PATH = PLUGIN_ROOT / "references" / "phase-state.md"
WORKFLOW_PATCH_PATH = PLUGIN_ROOT / "references" / "workflow-patch.md"

UPGRADE_LABEL = "**アップグレード手順**"
AUTH_RECORD_LABEL = "**認可記録の先行書き込み**"
DOWNGRADE_LABEL = "降格の禁止:"
MINIMAL_LABEL = "`minimal` tier の追加手順:"
REDUCED_LABEL = "`reduced` から `full` への追加手順:"
STEP_TABLE_MARKER = "| step | 実行方法 |"

STEP_B_HEADING = "## Step B: 自走ループ"
STEP_C_HEADING = (
    "## Step C: 完了処理（全 step completed — `skipped` の step（design "
    "自身の skip、または tier による skip）があっても可 — か、cap 到達に"
    "より verify が `failed` のまま残る場合のみ）"
)
STOP_CONDITION_3_LABEL = "**停止条件 3 との優先関係**"
CREATE_PLAN_EXEMPTION_RATIONALE_LABEL = "**create-plan が `in_progress` を経ない理由**"

ONCE_SECTION_HEADING = "## `--once` のフェーズ境界"
STOP_REPORT_HEADING = "## 停止時の報告（停止条件 2-4 のみ）"

SPEC_CHANGE_FIELD_LABEL = "| `spec_change` |"
CLASSIFICATION_FIELD_LABEL = "| `classification` |"

REPLACE_ALL_PERMISSION_LABEL = "### `replace_all` permission conditions"
TASK_ID_ALLOCATION_LABEL = "### Re-planning task-id allocation"


def _read(path):
    if not path.is_file():
        raise AssertionError(f"expected file to exist: {path}")
    return path.read_text(encoding="utf-8")


def _section(text, start_marker, end_marker):
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    return text[start:end]


def _strip_ws(text):
    # This document hard-wraps Japanese prose without a space at the wrap
    # point, so markers are matched after stripping ALL whitespace (never
    # collapsed to a single space) -- the convention already used by
    # tests/test_tier_reduction_develop_loop.py and
    # tests/test_tier_decision_step_a.py.
    return re.sub(r"\s+", "", text)


def _contains(haystack, phrase):
    return _strip_ws(phrase) in _strip_ws(haystack)


class SkillDocTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(SKILL_PATH)
        cls.auth_record_section = _section(
            cls.text, AUTH_RECORD_LABEL, DOWNGRADE_LABEL
        )
        cls.minimal_section = _section(cls.text, MINIMAL_LABEL, REDUCED_LABEL)
        cls.reduced_section = _section(cls.text, REDUCED_LABEL, STEP_TABLE_MARKER)
        step_b_section = _section(cls.text, STEP_B_HEADING, STEP_C_HEADING)
        cls.carve_out_section = _section(
            step_b_section,
            STOP_CONDITION_3_LABEL,
            CREATE_PLAN_EXEMPTION_RATIONALE_LABEL,
        )
        once_section = _section(cls.text, ONCE_SECTION_HEADING, STOP_REPORT_HEADING)
        cls.once_row = next(
            line
            for line in once_section.splitlines()
            if line.startswith("| 自動再エントリ")
        )


# === AC-1: authorization record ordering + required fields ================

RECORD_MARKER = "上記の認可記録を先に書いたのち"
STATUS_CS_MARKER = "create-spec の `status` を `needs_update` に設定"
STATUS_CP_MARKER = "create-plan の `status` を `needs_update` に設定"


def _record_precedes_status_writes(branch_section):
    """AC-1 matcher: True iff, within `branch_section`, the reference to
    the already-written authorization record precedes BOTH the
    create-spec and create-plan status-setting sentences (byte-offset
    comparison on whitespace-stripped text -- SKILL.md hard-wraps
    mid-phrase). False if any of the three markers is missing, or if the
    record marker does not precede both status markers."""
    stripped = _strip_ws(branch_section)
    record = _strip_ws(RECORD_MARKER)
    cs = _strip_ws(STATUS_CS_MARKER)
    cp = _strip_ws(STATUS_CP_MARKER)
    if record not in stripped or cs not in stripped or cp not in stripped:
        return False
    record_idx = stripped.index(record)
    return record_idx < stripped.index(cs) and record_idx < stripped.index(cp)


class TestAC1RecordPrecedesStatusWrites(SkillDocTestCase):
    """AC-1: both upgrade branches reference the already-written
    authorization record before either status-setting sentence."""

    def test_minimal_branch_record_precedes_status_writes(self):
        self.assertTrue(_record_precedes_status_writes(self.minimal_section))

    def test_reduced_branch_record_precedes_status_writes(self):
        self.assertTrue(_record_precedes_status_writes(self.reduced_section))


FORGED_BRANCH_RECORD_AFTER_STATUS = (
    "`minimal` tier の追加手順: 昇格手順は create-spec の `status` を "
    "`needs_update` に設定し、create-plan の `status` を `needs_update` "
    "に設定する。上記の認可記録を先に書いたのち、これを実行する。"
)


class TestRecordOrderingMatcherCanFail(unittest.TestCase):
    """Negative proof + non-vacuity guard for `_record_precedes_status_writes`
    (Test Notes: "the negative proof is a forged sample with the two
    swapped")."""

    def test_forged_sample_contains_all_three_markers(self):
        # Non-vacuity: the forgery is not missing a marker outright --
        # the failure below is attributable solely to the swapped order.
        stripped = _strip_ws(FORGED_BRANCH_RECORD_AFTER_STATUS)
        self.assertIn(_strip_ws(RECORD_MARKER), stripped)
        self.assertIn(_strip_ws(STATUS_CS_MARKER), stripped)
        self.assertIn(_strip_ws(STATUS_CP_MARKER), stripped)

    def test_matcher_detects_swapped_order(self):
        self.assertFalse(
            _record_precedes_status_writes(FORGED_BRANCH_RECORD_AFTER_STATUS)
        )

    def test_real_branches_are_not_the_degenerate_swapped_case(self):
        # Non-vacuity for the real document: prove the real sections are
        # long enough to be genuine prose, not a coincidentally-passing
        # empty/short string.
        self.assertGreater(len(_read(SKILL_PATH)), 10000)


AUTH_RECORD_REQUIRED_FIELDS = (
    "`reason`",
    "`origin_kind`",
    "`origin_id`",
    "`recorded_at_commit`",
    "`consumed` は `false`",
    "`replan_authorized` は `true`",
    "commit-docs.sh",
)


def _auth_record_states_required_fields(section):
    """AC-1 matcher: returns a list of human-readable violation
    descriptions if `section` (the 認可記録の先行書き込み block) is
    missing any required field/value, empty when none is missing."""
    violations = []
    for field in AUTH_RECORD_REQUIRED_FIELDS:
        if not _contains(section, field):
            violations.append(f"required field/value {field!r} missing")
    return violations


class TestAC1AuthRecordFields(SkillDocTestCase):
    """AC-1: the authorization record's fields -- interruption reason,
    origin pair, recorded-at commit, unconsumed, re-planning authorized --
    and the commit-docs.sh commit are all named."""

    def test_no_auth_record_field_violation(self):
        self.assertEqual(
            _auth_record_states_required_fields(self.auth_record_section), []
        )

    def test_origin_pair_sourced_from_trigger(self):
        self.assertTrue(
            _contains(
                self.auth_record_section,
                "review の critical finding なら `review` とその finding の"
                "安定識別子、verify の `failed` なら `verify` とその失敗"
                "項目の識別子",
            )
        )

    def test_same_record_as_rework_spec_change(self):
        self.assertTrue(
            _contains(
                self.auth_record_section,
                "この記録は rework の spec-change 遷移が書くものと同一の記録",
            )
        )


class TestAuthRecordFieldsMatcherCanFail(unittest.TestCase):
    """Negative proof + non-vacuity guard for
    `_auth_record_states_required_fields`."""

    FORGED_RECORD_MISSING_REPLAN_AUTHORIZED = (
        "`reason` にはトリガーとなった中断理由を、`origin_kind` / "
        "`origin_id` にはトリガーの由来を記録し、`recorded_at_commit` "
        "にはこの記録時点の commit を、`consumed` は `false` で書き、"
        "commit-docs.sh でコミットする。"
    )

    def test_forged_record_is_well_formed_and_found(self):
        for field in AUTH_RECORD_REQUIRED_FIELDS[:-1]:
            if field == "`replan_authorized` は `true`":
                continue
            self.assertIn(field, self.FORGED_RECORD_MISSING_REPLAN_AUTHORIZED)
        self.assertNotIn(
            "replan_authorized", self.FORGED_RECORD_MISSING_REPLAN_AUTHORIZED
        )

    def test_matcher_detects_a_missing_field(self):
        violations = _auth_record_states_required_fields(
            self.FORGED_RECORD_MISSING_REPLAN_AUTHORIZED
        )
        self.assertTrue(
            any("replan_authorized" in v for v in violations),
            "expected the matcher to flag the missing replan_authorized value",
        )


# === AC-2: phase-state.md / workflow-patch.md name the tier-upgrade =======
#     procedure as a (second) writer of the spec_change record


def _phase_state_names_tier_upgrade_as_second_writer(text):
    return (
        _contains(text, "skills/develop/SKILL.md")
        and _contains(text, "tier-upgrade procedure")
        and _contains(text, "second writer")
        and _contains(
            text, "introducing no new field and no new vocabulary value"
        )
    )


class TestAC2PhaseStateNamesTierUpgradeWriter(unittest.TestCase):
    def setUp(self):
        text = _read(PHASE_STATE_PATH)
        self.spec_change_row = _section(
            text, SPEC_CHANGE_FIELD_LABEL, CLASSIFICATION_FIELD_LABEL
        )

    def test_names_tier_upgrade_as_second_writer(self):
        self.assertTrue(
            _phase_state_names_tier_upgrade_as_second_writer(self.spec_change_row)
        )

    def test_still_names_rework_spec_change_transition(self):
        self.assertIn("rework's spec-change transition", self.spec_change_row)


class TestAC2PhaseStateMatcherCanFail(unittest.TestCase):
    FORGED_ROW_MISSING_TIER_UPGRADE = (
        "| `spec_change` | `reason`, `origin_kind`, `origin_id`, "
        "`recorded_at_commit`, `consumed`, `replan_authorized` -- written "
        "by rework's spec-change transition. |"
    )

    def test_forged_row_is_well_formed_and_found(self):
        self.assertIn(
            "rework's spec-change transition",
            self.FORGED_ROW_MISSING_TIER_UPGRADE,
        )
        self.assertNotIn(
            "tier-upgrade procedure", self.FORGED_ROW_MISSING_TIER_UPGRADE
        )

    def test_matcher_detects_missing_tier_upgrade_mention(self):
        self.assertFalse(
            _phase_state_names_tier_upgrade_as_second_writer(
                self.FORGED_ROW_MISSING_TIER_UPGRADE
            )
        )


def _workflow_patch_names_tier_upgrade_as_re_planning_transition(text):
    return (
        _contains(text, "tier-upgrade procedure")
        and _contains(text, "SPEC-change")
        and _contains(text, "authorized `spec_change` record")
    )


class TestAC2WorkflowPatchNamesTierUpgradeTransition(unittest.TestCase):
    def setUp(self):
        text = _read(WORKFLOW_PATCH_PATH)
        self.re_planning_section = _section(
            text, REPLACE_ALL_PERMISSION_LABEL, TASK_ID_ALLOCATION_LABEL
        )

    def test_re_planning_path_names_tier_upgrade(self):
        self.assertTrue(
            _workflow_patch_names_tier_upgrade_as_re_planning_transition(
                self.re_planning_section
            )
        )

    def test_still_names_spec_change_transition(self):
        self.assertIn("SPEC-change", self.re_planning_section)


class TestAC2WorkflowPatchMatcherCanFail(unittest.TestCase):
    FORGED_SECTION_MISSING_TIER_UPGRADE = (
        "- **Re-planning path** -- an explicit re-plan (e.g. the "
        "SPEC-change transition): permitted regardless of task status."
    )

    def test_forged_section_is_well_formed_and_found(self):
        self.assertIn("SPEC-change", self.FORGED_SECTION_MISSING_TIER_UPGRADE)
        self.assertNotIn(
            "tier-upgrade procedure", self.FORGED_SECTION_MISSING_TIER_UPGRADE
        )

    def test_matcher_detects_missing_tier_upgrade_mention(self):
        self.assertFalse(
            _workflow_patch_names_tier_upgrade_as_re_planning_transition(
                self.FORGED_SECTION_MISSING_TIER_UPGRADE
            )
        )


# === AC-3: reduced -> full re-entry ordering ===============================

CS_STATUS_STEM = "create-spec の `status` を `needs_update` に設定"
DESIGN_PENDING_STEM = "design の `skipped` の step を `pending` に戻し"
CP_STATUS_STEM = "create-plan の `status` を `needs_update` に設定"


def _reduced_full_orders_create_spec_design_create_plan(section):
    """AC-3 matcher: True iff `section` states create-spec's, then
    design's, then create-plan's re-entry in that byte order (on
    whitespace-stripped text)."""
    stripped = _strip_ws(section)
    cs = _strip_ws(CS_STATUS_STEM)
    design = _strip_ws(DESIGN_PENDING_STEM)
    cp = _strip_ws(CP_STATUS_STEM)
    if cs not in stripped or design not in stripped or cp not in stripped:
        return False
    return stripped.index(cs) < stripped.index(design) < stripped.index(cp)


def _states_create_spec_produces_requirements_before_create_plan(section):
    return _contains(
        section, "create-spec の再実行がまず要件定義書を作成し"
    ) and _contains(section, "その完了後に create-plan が")


class TestAC3ReducedFullOrdering(SkillDocTestCase):
    def test_orders_create_spec_design_create_plan(self):
        self.assertTrue(
            _reduced_full_orders_create_spec_design_create_plan(
                self.reduced_section
            )
        )

    def test_states_create_spec_produces_requirements_first(self):
        self.assertTrue(
            _states_create_spec_produces_requirements_before_create_plan(
                self.reduced_section
            )
        )


FORGED_REDUCED_SECTION_SWAPPED_ORDER = (
    "`reduced` から `full` への追加手順: design の `skipped` の step を "
    "`pending` に戻し、create-plan の `status` を `needs_update` に設定し、"
    "create-spec の `status` を `needs_update` に設定する。"
)


class TestReducedFullOrderingMatcherCanFail(unittest.TestCase):
    def test_forged_section_contains_all_three_markers(self):
        stripped = _strip_ws(FORGED_REDUCED_SECTION_SWAPPED_ORDER)
        self.assertIn(_strip_ws(CS_STATUS_STEM), stripped)
        self.assertIn(_strip_ws(DESIGN_PENDING_STEM), stripped)
        self.assertIn(_strip_ws(CP_STATUS_STEM), stripped)

    def test_matcher_detects_swapped_order(self):
        self.assertFalse(
            _reduced_full_orders_create_spec_design_create_plan(
                FORGED_REDUCED_SECTION_SWAPPED_ORDER
            )
        )


# === AC-4: requirements-document absence attributed to create-spec, not ===
#     to design's skip

OLD_ATTRIBUTION_SENTENCE = (
    "`reduced` tier では create-plan が\n"
    "既に `completed` に達しており、REQUIREMENTS.md と IMPLEMENTATION.md は\n"
    "design step の skip により未作成のままである。"
)


def _no_sentence_attributes_requirements_absence_to_design_skip(text):
    return not _contains(
        text,
        "REQUIREMENTS.md と IMPLEMENTATION.md は design step の skip に"
        "より未作成",
    )


def _attributes_documents_to_their_owning_steps(section):
    return (
        _contains(
            section,
            "create-spec 自身が `reduced` tier でその作成を省いたことにより"
            "未作成の",
        )
        and _contains(
            section,
            "create-plan 自身が `reduced` tier でその作成を省いたことにより"
            "未作成のままである",
        )
        and _contains(
            section, "design step の skip はこのいずれの不在の原因でもない"
        )
    )


class TestAC4AttributionCorrected(SkillDocTestCase):
    def test_no_sentence_attributes_absence_to_design_skip_whole_file(self):
        self.assertTrue(
            _no_sentence_attributes_requirements_absence_to_design_skip(
                self.text
            )
        )

    def test_documents_attributed_to_owning_steps(self):
        self.assertTrue(
            _attributes_documents_to_their_owning_steps(self.reduced_section)
        )


class TestAttributionMatcherCanFail(unittest.TestCase):
    """Negative proof for `_no_sentence_attributes_requirements_absence_to_design_skip`:
    Test Notes -- "AC-4's negative proof is the current text, which
    attributes both documents to the design skip." `OLD_ATTRIBUTION_SENTENCE`
    is that pre-task0011 sentence, captured verbatim."""

    def test_old_sentence_is_well_formed(self):
        self.assertIn("REQUIREMENTS.md", OLD_ATTRIBUTION_SENTENCE)
        self.assertIn("IMPLEMENTATION.md", OLD_ATTRIBUTION_SENTENCE)
        self.assertIn("design step の skip", OLD_ATTRIBUTION_SENTENCE)

    def test_matcher_detects_old_attribution(self):
        self.assertFalse(
            _no_sentence_attributes_requirements_absence_to_design_skip(
                OLD_ATTRIBUTION_SENTENCE
            )
        )

    def test_positive_attribution_matcher_fails_on_forged_copy(self):
        self.assertFalse(
            _attributes_documents_to_their_owning_steps(OLD_ATTRIBUTION_SENTENCE)
        )


# === AC-5: carve-out entry covers both re-entries; count consistency; ====
#     once-table row names the same transition

CARVE_OUT_INTRO_COUNT_PATTERN = re.compile(r"次の\s*(\d+)\s*つで")
CARVE_OUT_EXHAUSTIVENESS_COUNT_PATTERN = re.compile(r"この\s*(\d+)\s*つで網羅的")
CARVE_OUT_BULLET_PATTERN = re.compile(r"^- ", re.MULTILINE)


def _carve_out_counts(section):
    """AC-5: independently reads (a) the enumeration's own bullet count,
    (b) the intro sentence's stated count, and (c) the exhaustiveness
    sentence's stated count from `section`. Returns a 3-tuple of ints, or
    None for any element not found."""

    def _first_int(pattern):
        match = pattern.search(section)
        return int(match.group(1)) if match else None

    bullet_count = len(CARVE_OUT_BULLET_PATTERN.findall(section))
    intro_count = _first_int(CARVE_OUT_INTRO_COUNT_PATTERN)
    exhaustiveness_count = _first_int(CARVE_OUT_EXHAUSTIVENESS_COUNT_PATTERN)
    return (bullet_count, intro_count, exhaustiveness_count)


def _carve_out_counts_match(section, expected):
    counts = _carve_out_counts(section)
    return all(c == expected for c in counts)


def _tier_upgrade_bullet_covers_both_reentries(section):
    start = section.index("- tier 昇格による再エントリ")
    end_candidates = [
        idx
        for idx in (section.find("\n\nこの列挙は", start),)
        if idx != -1
    ]
    end = min(end_candidates) if end_candidates else len(section)
    bullet_text = section[start:end]
    return _contains(bullet_text, "create-spec") and _contains(
        bullet_text, "create-plan"
    )


class TestAC5CarveOutConsistency(SkillDocTestCase):
    def test_three_transitions_independently_counted_and_matching(self):
        self.assertTrue(_carve_out_counts_match(self.carve_out_section, 3))

    def test_tier_upgrade_bullet_covers_both_create_spec_and_create_plan(self):
        self.assertTrue(
            _tier_upgrade_bullet_covers_both_reentries(self.carve_out_section)
        )


class TestCarveOutCountMatcherCanFail(unittest.TestCase):
    """Negative proof + non-vacuity guard for `_carve_out_counts_match`:
    a forged copy whose bullet list has four items (a transition added)
    but whose count sentences still state the OLD count ("3") must be
    rejected -- proving the comparison reads the counts independently
    rather than trusting the stated numbers alone."""

    FORGED_CARVE_OUT_EXTRA_TRANSITION = (
        "該当する遷移は現時点で厳密に次の 3 つで、それぞれ所有ドキュメントを"
        "明記する:\n"
        "- create-plan の route back to planning\n"
        "- rework の spec-change 遷移\n"
        "- tier 昇格による再エントリ\n"
        "- 新たに追加された 4 つ目の遷移\n\n"
        "この列挙は、所有 SSOT 自身がフェーズの自動再エントリを明記している"
        "遷移だけが対象という構成上の理由でこの 3 つで網羅的であり、他の"
        "遷移はこの除外の対象外。"
    )

    def test_forged_carve_out_is_well_formed_and_found(self):
        bullet_count, intro_count, exhaustiveness_count = _carve_out_counts(
            self.FORGED_CARVE_OUT_EXTRA_TRANSITION
        )
        self.assertEqual(bullet_count, 4)
        self.assertEqual(intro_count, 3)
        self.assertEqual(exhaustiveness_count, 3)

    def test_matcher_detects_a_count_mismatch(self):
        self.assertFalse(
            _carve_out_counts_match(self.FORGED_CARVE_OUT_EXTRA_TRANSITION, 3)
        )


class TestTierUpgradeBulletMatcherCanFail(unittest.TestCase):
    FORGED_SECTION_CREATE_SPEC_ONLY = (
        "- tier 昇格による再エントリ — create-spec を `needs_update` に"
        "設定する遷移\n\nこの列挙は網羅的。"
    )

    def test_forged_bullet_is_well_formed_and_found(self):
        self.assertIn("create-spec", self.FORGED_SECTION_CREATE_SPEC_ONLY)
        self.assertNotIn("create-plan", self.FORGED_SECTION_CREATE_SPEC_ONLY)

    def test_matcher_detects_missing_create_plan_coverage(self):
        self.assertFalse(
            _tier_upgrade_bullet_covers_both_reentries(
                self.FORGED_SECTION_CREATE_SPEC_ONLY
            )
        )


def _once_table_row_names_tier_upgrade_transition(row):
    return _contains(
        row,
        "アップグレード手順による `create-spec` → `needs_update` / "
        "`create-plan` → `needs_update`",
    )


class TestAC5OnceTableRow(SkillDocTestCase):
    def test_once_row_names_tier_upgrade_transition(self):
        self.assertTrue(
            _once_table_row_names_tier_upgrade_transition(self.once_row)
        )

    def test_once_row_still_names_the_other_two_transitions(self):
        self.assertIn("implement I.2.c", self.once_row)
        self.assertIn("rework の spec-change 遷移", self.once_row)


class TestOnceTableRowMatcherCanFail(unittest.TestCase):
    FORGED_ROW_MISSING_TIER_UPGRADE = (
        "| 自動再エントリ | ルーティングパッチを適用してコミット済み"
        "（implement I.2.c の `create-plan` → `needs_update`、または "
        "rework の spec-change 遷移による `create-spec` → `needs_update`）"
        " | 再エントリした step |"
    )

    def test_forged_row_is_well_formed_and_found(self):
        self.assertIn("自動再エントリ", self.FORGED_ROW_MISSING_TIER_UPGRADE)
        self.assertNotIn(
            "アップグレード手順", self.FORGED_ROW_MISSING_TIER_UPGRADE
        )

    def test_matcher_detects_missing_tier_upgrade_transition(self):
        self.assertFalse(
            _once_table_row_names_tier_upgrade_transition(
                self.FORGED_ROW_MISSING_TIER_UPGRADE
            )
        )


# === AC-6/AC-7: this module's own standard-library-only import discipline =


class TestOwnModuleStdlibOnly(unittest.TestCase):
    def test_own_imports_are_all_stdlib(self):
        import ast

        source = Path(__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        stdlib_allowed = {"re", "unittest", "pathlib", "ast"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top_level = alias.name.split(".")[0]
                    self.assertIn(top_level, stdlib_allowed)
            elif isinstance(node, ast.ImportFrom):
                if node.module is not None:
                    top_level = node.module.split(".")[0]
                    self.assertIn(top_level, stdlib_allowed)


if __name__ == "__main__":
    unittest.main()
