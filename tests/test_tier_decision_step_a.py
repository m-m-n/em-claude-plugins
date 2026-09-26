"""Tests for task0003 (task-tier-reduction): Step A's tier-decision
procedure, its persistence into `phase-state/{feature}/tier.yaml`, the
no-work terminal stop it triggers, and the retrospect decision record.

Covers task0003 Acceptance Criteria
(feature-docs/task-tier-reduction/tasks/task0003.md):

- AC-1 (TS-13): the tier-decision procedure sits in Step A, placed after the
  fail-closed identifier gate and before `workflow.yaml` construction, and
  is reachable from both Step A routes (the new-feature route and the
  resumed-feature route whose bootstrap check finds no `workflow.yaml`
  yet). It names the readonly Codex wrapper (`run_codex_exec.sh readonly`)
  and the judgement skill (`~/.claude/skills/jev`) with its two JSON
  switches (`--json-input` / `--json-output`), never names the raw `codex
  exec` subcommand as an invocation route, consults the judgement skill on
  the task description alone and again with the pre-survey estimate merged
  into its state, and records both readings as decision bases.
- AC-2: availability is resolved by citing `tier-rules.yaml`; no threshold
  value is restated; no sentence is reproduced from either external skill;
  every unresolved condition -- including a non-zero judgement-skill exit
  status -- yields the tier that removes nothing.
- AC-3 (TS-8): the decision is written to
  `feature-docs/{feature}/phase-state/tier.yaml` and committed via the
  existing `commit-docs.sh`; `references/phase-state.md` lists the file in
  its file-layout listing, defines its fields, places it under the existing
  not-owned-by-one-phase exemption, and states that a resume reuses it
  instead of re-deciding.
- AC-4: when the pre-survey reports no work remaining, Step A ends the run
  before any workflow step; the result carries the stopped state, the
  no-step sentinel, non-empty resume guidance saying no resumption is
  needed, and the pre-survey rationale in the recovery text; the
  underscored reason-code literal `no_work_required` appears nowhere in
  `em-workflow/skills/develop/SKILL.md`.
- AC-5 (TS-17): the retrospect section's collected signals include the
  decided tier, the rationale, the observed probability values and the
  pre-survey estimate, and state that threshold tuning is out of scope.
- AC-6 (TS-20, TS-18, TS-22): the procedure states that the standalone route
  follows the same rules with no service-presence branch, and neither the
  decision path nor the stop path introduces a gate identifier or a user
  question.
- AC-7: this module asserts AC-1 through AC-6 against raw document text, is
  discovered by `python3 -m unittest discover -s tests`, imports only
  standard-library modules, and pairs each matcher with a negative proof
  and a non-vacuity guard.

This is a documentation-conformance task (Test Notes: unit-level assertions
over raw file text, no runtime behaviour to integration-test), following the
pattern established by tests/test_batch_stop_contract_skill_wiring.py and
tests/test_phase_state_doc.py: helper matcher functions independent of any
other test module (no cross-module import), `_strip_ws` normalization for
phrases that may be hard-wrapped across lines in the source, and a
`TestXMatcherCanFail` class per matcher proving it fires on a forged sample.

D3 region-ownership note: this task owns only Step A (the tier-decision
procedure, the phase-state write, the no-work stop trigger) and the
retrospect section's new decision record inside
`em-workflow/skills/develop/SKILL.md`. It does not touch the turn-ending
conditions list, the Step B status discipline or phase table, the
automatic-re-entry carve-out enumeration, the Step C entry condition, or the
`--once` phase-boundary table -- those are task0005's regions. A dedicated
regression class below pins anchor sentences from each of those regions as
unchanged by this task's diff.
"""

import ast
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"
SKILL_PATH = PLUGIN_ROOT / "skills" / "develop" / "SKILL.md"
PHASE_STATE_PATH = PLUGIN_ROOT / "references" / "phase-state.md"

TIER_SECTION_START = "### tier 決定"
STEP_A5_START = "## Step A.5"
STEP_A_START = "## Step A: feature の決定"
RETROSPECT_START = "### retrospect フェーズ"
STEP_C_START = (
    "## Step C: 完了処理（全 step completed — `skipped` の step（design "
    "自身の skip、または tier による skip）があっても可 — か、cap 到達に"
    "より verify が `failed` のまま残る場合のみ）"
)

TIER_DECISION_PERSISTENCE_START = "## tier decision persistence"
LEGACY_COMPAT_START = "## Legacy feature compatibility"
FILE_LAYOUT_START = "## File layout"
SCHEMA_START = "## Schema"

# The reason-code literal task0004 alone may write (batch-terminal-line.md).
# This task's SKILL.md diff must never carry it.
FORBIDDEN_REASON_CODE = "no_work_required"
STOP_POINT_HYPHENATED = "no-work-required"


def _read(path):
    if not path.is_file():
        raise AssertionError(f"expected file to exist: {path}")
    return path.read_text(encoding="utf-8")


def _strip_ws(text):
    # Strip ALL whitespace (not collapse to one space): Japanese prose in
    # these documents is hard-wrapped without a space at the break point,
    # so a phrase spanning a wrap needs every whitespace character removed
    # to match reliably (same convention as
    # tests/test_batch_stop_contract_skill_wiring.py's helper of the same
    # name).
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
PHASE_STATE_TEXT = _read(PHASE_STATE_PATH)

TIER_SECTION = _section(SKILL_TEXT, TIER_SECTION_START, STEP_A5_START)
STEP_A_TEXT = _section(SKILL_TEXT, STEP_A_START, STEP_A5_START)
RETROSPECT_SECTION = _section(SKILL_TEXT, RETROSPECT_START, STEP_C_START)
TIER_PERSISTENCE_SECTION = _section(
    PHASE_STATE_TEXT, TIER_DECISION_PERSISTENCE_START, LEGACY_COMPAT_START
)
FILE_LAYOUT_SECTION = _section(PHASE_STATE_TEXT, FILE_LAYOUT_START, SCHEMA_START)


# ---------------------------------------------------------------------------
# AC-1: placement, reachability from both routes, the two named invocations,
# never naming the raw `codex exec` subcommand, the two decision bases.
# ---------------------------------------------------------------------------


def _states_placement_after_gate_before_construction(text):
    return _contains(text, "識別子ゲートを通過した直後") and _contains(
        text, "`workflow.yaml` が構築される前に"
    )


def _names_readonly_codex_wrapper(text):
    return _contains(text, "run_codex_exec.sh readonly")


def _never_names_raw_codex_subcommand(text):
    """AC-1: the raw `codex exec` subcommand is never named as an
    invocation route. Checked as a bare substring (case-sensitive) since
    the real section never has legitimate reason to mention it at all."""
    return "codex exec" not in text


def _names_judgement_skill_with_json_switches(text):
    return (
        "~/.claude/skills/jev" in text
        and "--json-input" in text
        and "--json-output" in text
    )


def _consults_twice_and_records_both_bases(text):
    # Updated by task0003 (tier-decision-staged-jev): the two-reading
    # comparison this originally checked ("1 回目はタスク記述のみを基準に" /
    # "その state に合流させて" / "決定の根拠として記録する") no longer
    # exists -- the final call's input now folds in the first call's full
    # JSON result plus the Codex pre-survey JSON, and the persisted record's
    # `bases` presence rules (not a blanket "always record both") replace
    # the old unconditional recording claim.
    return (
        _contains(text, "decision-basis `description_only`")
        and _contains(text, "decision-basis `description_plus_code`")
        and _contains(text, "2. が返した JSON 結果全体")
    )


class TestAC1PlacementAndInvocations(unittest.TestCase):
    def test_tier_section_exists(self):
        self.assertIn(TIER_SECTION_START, SKILL_TEXT)

    def test_placed_after_identifier_gate_before_workflow_construction(self):
        self.assertTrue(_states_placement_after_gate_before_construction(TIER_SECTION))

    def test_reachable_from_new_feature_route(self):
        self.assertTrue(
            _contains(
                STEP_A_TEXT,
                "タスク記述を確定したら、create-spec を実際に起動する前に",
            )
        )
        self.assertTrue(_contains(STEP_A_TEXT, "「### tier 決定」の手順を実行する"))

    def test_reachable_from_resumed_no_workflow_route(self):
        self.assertTrue(
            _contains(STEP_A_TEXT, "存在しない")
            and _contains(
                STEP_A_TEXT, "create-spec フェーズへ実際に再突入する前に"
            )
        )

    def test_names_readonly_codex_wrapper(self):
        self.assertTrue(_names_readonly_codex_wrapper(TIER_SECTION))

    def test_never_names_raw_codex_subcommand_as_invocation_route(self):
        self.assertTrue(_never_names_raw_codex_subcommand(TIER_SECTION))

    def test_names_judgement_skill_with_json_switches(self):
        self.assertTrue(_names_judgement_skill_with_json_switches(TIER_SECTION))

    def test_consults_twice_and_records_both_bases(self):
        self.assertTrue(_consults_twice_and_records_both_bases(TIER_SECTION))


FORGED_TIER_SECTION_MISSING_EVERYTHING = """### tier 決定

このプレースホルダには手順が一切書かれていない。
"""

FORGED_TIER_SECTION_WITH_RAW_CODEX = (
    TIER_SECTION + "\n念のため `codex exec` を直接呼んでもよい。\n"
)


class TestAC1MatchersCanFail(unittest.TestCase):
    """Negative proofs: each AC-1 matcher fails on a forged sample lacking
    (or, for the raw-subcommand check, adding) the property it asserts --
    proving the matcher is not vacuously true."""

    def test_placement_matcher_fails_on_forged_copy(self):
        self.assertFalse(
            _states_placement_after_gate_before_construction(
                FORGED_TIER_SECTION_MISSING_EVERYTHING
            )
        )

    def test_codex_wrapper_matcher_fails_on_forged_copy(self):
        self.assertFalse(
            _names_readonly_codex_wrapper(FORGED_TIER_SECTION_MISSING_EVERYTHING)
        )

    def test_raw_codex_subcommand_matcher_fires_on_forged_copy(self):
        self.assertFalse(
            _never_names_raw_codex_subcommand(FORGED_TIER_SECTION_WITH_RAW_CODEX)
        )

    def test_judgement_skill_matcher_fails_on_forged_copy(self):
        self.assertFalse(
            _names_judgement_skill_with_json_switches(
                FORGED_TIER_SECTION_MISSING_EVERYTHING
            )
        )

    def test_two_bases_matcher_fails_on_forged_copy(self):
        self.assertFalse(
            _consults_twice_and_records_both_bases(
                FORGED_TIER_SECTION_MISSING_EVERYTHING
            )
        )

    def test_real_section_never_mentions_raw_codex_subcommand(self):
        # Non-vacuity companion for the raw-subcommand check: prove the
        # *real* section is genuinely non-trivial (long enough, mentions
        # the wrapper) so passing the absence check is not a fluke of an
        # empty section.
        self.assertGreater(len(TIER_SECTION), 500)
        self.assertIn("run_codex_exec.sh", TIER_SECTION)


# ---------------------------------------------------------------------------
# AC-2: availability resolved by citation, no threshold value restated, no
# external-skill sentence reproduced, unresolved conditions -> full.
# ---------------------------------------------------------------------------

FORBIDDEN_THRESHOLD_TOKENS = (
    "0.80",
    "0.40",
    "0.85",
    ">= 0.5",
    "P(0)",
    "expectation_clear",
)


def _cites_rules_file_for_availability(text):
    # Updated by task0003 (tier-decision-staged-jev): the fallback table is
    # no longer applied directly by this section's own prose ("フォールバック
    # 表をそのまま適用して解決する" is gone) -- resolution is now delegated
    # to the evaluator's input contract, with tier-rules.yaml still cited
    # for question_set / codex_output_schema.
    return _contains(text, "tier-rules.yaml") and _contains(text, "評価器の入力契約")


def _find_threshold_violations(text):
    return [token for token in FORBIDDEN_THRESHOLD_TOKENS if token in text]


class TestAC2AvailabilityAndThresholds(unittest.TestCase):
    def test_cites_rules_file_for_availability(self):
        self.assertTrue(_cites_rules_file_for_availability(TIER_SECTION))

    def test_no_threshold_value_restated(self):
        self.assertEqual(_find_threshold_violations(TIER_SECTION), [])

    def test_unresolved_conditions_give_removes_nothing_tier(self):
        # Updated by task0003 (tier-decision-staged-jev): the two-reading
        # disagreement phrasing ("判定結果が割れた場合" /
        # "フォールバック表が解決しないその他の条件") is gone -- there is no
        # second reading to disagree with. The remaining unresolved
        # conditions (either judgement-skill call unusable, pre-survey
        # unusable) still resolve to the tier that removes nothing.
        self.assertTrue(
            _contains(TIER_SECTION, "いずれかが使用不可のときは")
        )
        self.assertTrue(_contains(TIER_SECTION, "何も引かない tier"))
        # Non-zero judgement-skill exit status is explicitly one of the
        # unresolved conditions, not a separate unstated case.
        self.assertTrue(_contains(TIER_SECTION, "終了ステータスが非 0 の場合"))

    def test_named_external_skills_by_path_structurally(self):
        # Structural half (unconditional, per task0001's decidable form):
        # the two external references this procedure actually invokes are
        # named by path.
        self.assertIn("~/.claude/skills/jev", TIER_SECTION)
        self.assertIn("run_codex_exec.sh", TIER_SECTION)

    def test_no_external_skill_sentence_reproduced_text_overlap(self):
        # Text-overlap half: best-effort, skipped with a recorded reason
        # when the external documents are not readable in the run
        # environment (Test Notes: same decidable form as task0001's).
        candidates = [
            Path.home() / ".claude" / "skills" / "jev" / "SKILL.md",
        ]
        checked_any = False
        for candidate in candidates:
            if not candidate.is_file():
                continue
            checked_any = True
            external_text = candidate.read_text(encoding="utf-8")
            for line in external_text.splitlines():
                stripped = line.strip()
                if len(stripped) < 40:
                    continue
                self.assertNotIn(
                    stripped,
                    TIER_SECTION,
                    f"a long line from {candidate} was reproduced verbatim",
                )
        if not checked_any:
            self.skipTest(
                "no external skill document was readable in this run "
                "environment; structural half above still applies"
            )


class TestAC2MatchersCanFail(unittest.TestCase):
    def test_availability_citation_matcher_fails_on_forged_copy(self):
        self.assertFalse(
            _cites_rules_file_for_availability("何も参照していないテキスト")
        )

    def test_threshold_absence_matcher_fires_on_forged_copy(self):
        forged = TIER_SECTION + "\n`P(0) >= 0.80` かつ `expectation_clear >= 0.5`。\n"
        self.assertNotEqual(_find_threshold_violations(forged), [])

    def test_real_section_has_no_threshold_violations_nonvacuously(self):
        # Non-vacuity: prove the token list itself is non-empty and that at
        # least one token would be detected if present (shown above), so
        # the real section's clean pass is not a vacuous "empty list vs.
        # empty list" comparison against zero candidate tokens.
        self.assertGreater(len(FORBIDDEN_THRESHOLD_TOKENS), 0)


# ---------------------------------------------------------------------------
# AC-3 (TS-8): persistence to phase-state/tier.yaml, commit via
# commit-docs.sh, phase-state.md layout/fields/exemption/resume-reuse.
# ---------------------------------------------------------------------------


def _skill_writes_and_commits_tier_file(text):
    return _contains(text, "phase-state/tier.yaml") and _contains(
        text, "commit-docs.sh"
    )


PHASE_STATE_EXPECTED_FIELDS = (
    "schema_version",
    "feature",
    "tier",
    "bases",
    "pre_survey_estimate",
    "decided_at",
)


class TestAC3Persistence(unittest.TestCase):
    def test_skill_writes_tier_file_and_commits_via_commit_docs(self):
        self.assertTrue(_skill_writes_and_commits_tier_file(TIER_SECTION))

    def test_skill_states_write_happens_before_anything_else(self):
        self.assertTrue(_contains(TIER_SECTION, "決定した直後、他の何よりも先に"))

    def test_phase_state_lists_file_in_layout(self):
        self.assertIn("tier.yaml", FILE_LAYOUT_SECTION)

    def test_phase_state_defines_every_field(self):
        for field in PHASE_STATE_EXPECTED_FIELDS:
            self.assertIn(
                f"`{field}`",
                TIER_PERSISTENCE_SECTION,
                f"field {field!r} not documented in tier decision persistence section",
            )

    def test_phase_state_places_file_under_not_owned_by_one_phase_exemption(self):
        self.assertIn(
            "not-owned-by-one-phase exemption", TIER_PERSISTENCE_SECTION
        )

    def test_phase_state_states_resume_reuses_it(self):
        self.assertTrue(
            _contains(
                TIER_PERSISTENCE_SECTION,
                "A resume that finds this file present reads it and reuses "
                "the recorded decision rather than re-running the "
                "tier-decision procedure.",
            )
        )

    def test_no_script_change_required(self):
        self.assertIn("no script change needed", TIER_PERSISTENCE_SECTION)


class TestAC3MatchersCanFail(unittest.TestCase):
    def test_write_and_commit_matcher_fails_on_forged_copy(self):
        self.assertFalse(_skill_writes_and_commits_tier_file("何も書いていない"))

    def test_field_matcher_fails_on_forged_copy_missing_a_field(self):
        forged = TIER_PERSISTENCE_SECTION.replace("`pre_survey_estimate`", "")
        self.assertNotIn("`pre_survey_estimate`", forged)

    def test_exemption_matcher_fails_on_forged_copy(self):
        forged = TIER_PERSISTENCE_SECTION.replace(
            "not-owned-by-one-phase exemption", ""
        )
        self.assertNotIn("not-owned-by-one-phase exemption", forged)


# ---------------------------------------------------------------------------
# AC-4: the no-work terminal stop.
# ---------------------------------------------------------------------------


def _states_no_work_stop_before_any_workflow_step(text):
    return _contains(text, "いかなる workflow step も実行せずに") and _contains(
        text, "ここで走行を終える"
    )


def _states_stopped_state_and_no_step_sentinel(text):
    # The doc itself must never restate the literal `no-step` token (a
    # whole-file SSOT guard enforced elsewhere -- see
    # tests/test_batch_quiet_output_skill_wiring.py's
    # `_find_forbidden_literal_violations` / SENTINEL_VALUE), so this
    # checks that the CONCEPT (a stopped result whose step sentinel shows
    # no workflow.yaml step is in effect, per batch-terminal-line.md) is
    # stated, not the literal.
    return (
        _contains(text, "結果は停止状態を持ち")
        and _contains(text, "1 つも有効になっていないことを示す")
        and _contains(text, "センチネル値を持ち")
    )


def _states_nonempty_resume_guidance_says_no_resumption_needed(text):
    return _contains(text, "再開ガイダンスは空にせず") and _contains(
        text, "「再開は不要」である旨を明文で述べる"
    )


def _states_presurvey_rationale_in_recovery_text(text):
    return _contains(text, "Codex 事前調査の根拠は同ガイダンスに含める")


class TestAC4NoWorkStop(unittest.TestCase):
    def test_ends_run_before_any_workflow_step(self):
        self.assertTrue(_states_no_work_stop_before_any_workflow_step(TIER_SECTION))

    def test_result_carries_stopped_state_and_no_step_sentinel(self):
        self.assertTrue(_states_stopped_state_and_no_step_sentinel(TIER_SECTION))

    def test_resume_guidance_nonempty_says_no_resumption_needed(self):
        self.assertTrue(
            _states_nonempty_resume_guidance_says_no_resumption_needed(TIER_SECTION)
        )

    def test_presurvey_rationale_carried_in_recovery_text(self):
        self.assertTrue(_states_presurvey_rationale_in_recovery_text(TIER_SECTION))

    def test_hyphenated_stop_point_name_present(self):
        self.assertIn(STOP_POINT_HYPHENATED, TIER_SECTION)

    def test_underscored_reason_code_absent_from_whole_skill_file(self):
        self.assertNotIn(FORBIDDEN_REASON_CODE, SKILL_TEXT)

    def test_literal_no_step_sentinel_token_never_restated(self):
        # The bare `no-step` token is a batch-terminal-line.md contract
        # literal that SKILL.md must never restate anywhere (an existing
        # whole-file guard enforces this repo-wide, e.g.
        # tests/test_batch_quiet_output_skill_wiring.py's
        # `_find_forbidden_literal_violations`). `no-work-required` (the
        # stop point's own hyphenated name) legitimately contains the
        # substring "-required", not "no-step", so this check does not
        # collide with the hyphenated-name presence check above.
        self.assertNotIn("no-step", SKILL_TEXT)


FORGED_SKILL_TEXT_WITH_REASON_CODE = (
    SKILL_TEXT + "\n<!-- reason: no_work_required -->\n"
)


class TestAC4MatchersCanFail(unittest.TestCase):
    def test_no_work_stop_matcher_fails_on_forged_copy(self):
        self.assertFalse(
            _states_no_work_stop_before_any_workflow_step("何も書いていない")
        )

    def test_stopped_state_matcher_fails_on_forged_copy(self):
        self.assertFalse(_states_stopped_state_and_no_step_sentinel("何も書いていない"))

    def test_resume_guidance_matcher_fails_on_forged_copy(self):
        self.assertFalse(
            _states_nonempty_resume_guidance_says_no_resumption_needed(
                "何も書いていない"
            )
        )

    def test_rationale_matcher_fails_on_forged_copy(self):
        self.assertFalse(_states_presurvey_rationale_in_recovery_text("何も書いていない"))

    def test_reason_code_absence_matcher_fires_on_forged_copy(self):
        self.assertIn(FORBIDDEN_REASON_CODE, FORGED_SKILL_TEXT_WITH_REASON_CODE)

    def test_hyphen_underscore_pair_is_distinguished(self):
        # The hyphenated stop-point name and the underscored reason code
        # must not collapse into the same check: proving one present and
        # the other absent, independently, guards against a future rename
        # silently breaking one half while satisfying the other.
        self.assertIn(STOP_POINT_HYPHENATED, SKILL_TEXT)
        self.assertNotIn(FORBIDDEN_REASON_CODE, SKILL_TEXT)
        self.assertNotEqual(STOP_POINT_HYPHENATED, FORBIDDEN_REASON_CODE)


# ---------------------------------------------------------------------------
# AC-5 (TS-17): retrospect signals.
# ---------------------------------------------------------------------------


def _retrospect_yaml_has_tier_decision_signal(text):
    return _contains(text, "tier_decision:") and _contains(
        text, "Step A「tier 決定」が記録した内容"
    )


def _retrospect_states_fields(text):
    return (
        "tier:" in text
        and "rationale:" in text
        and "bases:" in text
        and "pre_survey_estimate:" in text
    )


def _retrospect_states_threshold_tuning_out_of_scope(text):
    return _contains(text, "閾値のチューニング") and _contains(text, "スコープ外")


class TestAC5RetrospectSignals(unittest.TestCase):
    def test_retrospect_section_exists(self):
        self.assertIn(RETROSPECT_START, SKILL_TEXT)

    def test_retrospect_yaml_gains_tier_decision_key(self):
        self.assertTrue(_retrospect_yaml_has_tier_decision_signal(RETROSPECT_SECTION))

    def test_retrospect_includes_tier_rationale_bases_and_presurvey_estimate(self):
        self.assertTrue(_retrospect_states_fields(RETROSPECT_SECTION))

    def test_retrospect_explanatory_prose_names_the_source_file(self):
        self.assertTrue(
            _contains(RETROSPECT_SECTION, "phase-state/tier.yaml")
        )

    def test_retrospect_states_threshold_tuning_out_of_scope(self):
        self.assertTrue(
            _retrospect_states_threshold_tuning_out_of_scope(RETROSPECT_SECTION)
        )


class TestAC5MatchersCanFail(unittest.TestCase):
    def test_tier_decision_signal_matcher_fails_on_forged_copy(self):
        self.assertFalse(
            _retrospect_yaml_has_tier_decision_signal("収集は自動・承認不要")
        )

    def test_fields_matcher_fails_on_forged_copy(self):
        self.assertFalse(_retrospect_states_fields("tier: reduced のみ"))

    def test_out_of_scope_matcher_fails_on_forged_copy(self):
        self.assertFalse(
            _retrospect_states_threshold_tuning_out_of_scope("何も書いていない")
        )

    def test_real_retrospect_section_predates_this_change_too(self):
        # Non-vacuity: prove the pre-existing verification_failures signal
        # this task did not touch is still present, so the section text
        # captured above is the real, non-empty retrospect block and not an
        # accidental empty slice.
        self.assertIn("verification_failures", RETROSPECT_SECTION)


# ---------------------------------------------------------------------------
# AC-6 (TS-20, TS-18, TS-22): standalone parity, no gate_id / question.
# ---------------------------------------------------------------------------


def _states_standalone_parity_with_no_service_branch(text):
    return _contains(text, "スタンドアロン経路") and _contains(
        text, "サービスの有無で分岐する条件はどこにもない"
    )


def _introduces_no_gate_or_question(text):
    return "AskUserQuestion" not in text and _contains(
        text, "新しい `gate_id` もユーザーへの質問も一切導入しない"
    )


class TestAC6StandaloneParityAndNoGate(unittest.TestCase):
    def test_states_standalone_parity_with_no_service_branch(self):
        self.assertTrue(_states_standalone_parity_with_no_service_branch(TIER_SECTION))

    def test_introduces_no_gate_id_or_user_question(self):
        self.assertTrue(_introduces_no_gate_or_question(TIER_SECTION))

    def test_no_bare_gate_id_value_definition(self):
        # No gate_id VALUE is minted anywhere in this section (the one
        # mention of the literal token "gate_id" is the disclaimer
        # sentence itself, asserted above -- never a "gate_id: ..."
        # definition, which this regex would catch).
        self.assertIsNone(re.search(r"gate_id:\s*\S", TIER_SECTION))


class TestAC6MatchersCanFail(unittest.TestCase):
    def test_standalone_parity_matcher_fails_on_forged_copy(self):
        self.assertFalse(
            _states_standalone_parity_with_no_service_branch("何も書いていない")
        )

    def test_no_gate_matcher_fails_on_forged_copy_missing_disclaimer(self):
        self.assertFalse(_introduces_no_gate_or_question("何も書いていない"))

    def test_no_gate_matcher_fires_on_forged_copy_with_askuserquestion(self):
        forged = TIER_SECTION + "\nAskUserQuestion で確認する。\n"
        self.assertFalse(_introduces_no_gate_or_question(forged))

    def test_gate_id_value_regex_fires_on_forged_copy(self):
        forged = TIER_SECTION + "\ngate_id: tier.no-work\n"
        self.assertIsNotNone(re.search(r"gate_id:\s*\S", forged))


# ---------------------------------------------------------------------------
# Region-ownership regression (Test Notes): the sections task0005 owns must
# be untouched by this task's diff. Pinned by anchor sentence, not by
# whole-section byte-identity, so an unrelated future edit to those regions
# by task0005 itself does not spuriously fail this module once merged.
# ---------------------------------------------------------------------------

TURN_ENDING_CONDITIONS_ANCHOR = (
    "1. `workflow` 配列の全 step が `completed`、ただし `skipped` の step が\n"
    "   あっても可（design 自身の判断による skip、または tier によるスキップの\n"
    "   いずれも該当。完了処理まで済ませた後）"
)
STEP_B_PHASE_TABLE_ANCHOR = "| create-spec | `${CLAUDE_PLUGIN_ROOT}/references/phases/create-spec-phase.md` に従う"
CARVEOUT_ANCHOR = "該当する遷移は現時点で厳密に次の 3 つで"
STEP_C_HEADING = (
    "## Step C: 完了処理（全 step completed — `skipped` の step（design "
    "自身の skip、または tier による skip）があっても可 — か、cap 到達に"
    "より verify が `failed` のまま残る場合のみ）"
)


class TestRegionOwnershipRegression(unittest.TestCase):
    """This task (task0003) owns only Step A and the retrospect section's
    new decision record (IMPLEMENTATION.md D3). It must not touch the
    turn-ending conditions list, the Step B phase table, the automatic
    re-entry carve-out enumeration, or the Step C heading -- task0005's
    regions. Each anchor below is verbatim pre-existing text this task's
    diff never edited."""

    def test_turn_ending_conditions_list_unchanged(self):
        self.assertIn(TURN_ENDING_CONDITIONS_ANCHOR, SKILL_TEXT)

    def test_step_b_phase_table_unchanged(self):
        self.assertIn(STEP_B_PHASE_TABLE_ANCHOR, SKILL_TEXT)

    def test_carveout_enumeration_still_reads_three_transitions(self):
        # This task's own diff must leave the enumeration's own count
        # (owned by task0005 / task0011, not this task) untouched at its
        # current value.
        self.assertIn(CARVEOUT_ANCHOR, SKILL_TEXT)

    def test_step_c_heading_unchanged(self):
        self.assertIn(STEP_C_HEADING, SKILL_TEXT)

    def test_tier_section_is_outside_step_b_and_step_c(self):
        # Structural check: the tier-decision section sits strictly between
        # Step A's numbered list and Step A.5 -- never inside Step B or
        # Step C, whose regions belong to task0005.
        tier_index = SKILL_TEXT.index(TIER_SECTION_START)
        step_a5_index = SKILL_TEXT.index(STEP_A5_START)
        step_b_index = SKILL_TEXT.index("## Step B: 自走ループ")
        self.assertLess(tier_index, step_a5_index)
        self.assertLess(step_a5_index, step_b_index)


class TestRegionOwnershipMatchersCanFail(unittest.TestCase):
    def test_anchor_checks_fail_on_a_document_missing_them(self):
        forged = "この文書には何も含まれていない。"
        self.assertNotIn(TURN_ENDING_CONDITIONS_ANCHOR, forged)
        self.assertNotIn(STEP_B_PHASE_TABLE_ANCHOR, forged)
        self.assertNotIn(CARVEOUT_ANCHOR, forged)
        self.assertNotIn(STEP_C_HEADING, forged)


# ---------------------------------------------------------------------------
# AC-7: this module's own hygiene.
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
