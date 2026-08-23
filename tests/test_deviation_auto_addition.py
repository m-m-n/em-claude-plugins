"""Tests for task0010 (goal-vs-spec-divergence): the conditional
auto-addition rule for an implement-phase deviation, pinned in
`em-workflow/references/implement-phase.md` (the only file this task edits;
C4 -- assertions cover only that document, never the sibling create-plan
derivation task0009 owns).

Covers task0010 Acceptance Criteria
(feature-docs/goal-vs-spec-divergence/tasks/task0010.md):

- AC-1 (FR19): the document states that an implement deviation is
  auto-added to the declaration only when accompanied by evidence that an
  existing acceptance criterion would otherwise be dropped.
- AC-2 (FR19): a deviation without that evidence is not auto-added,
  implementer convenience named as an example that does not qualify.
- AC-3 (FR19): the containment check remains and unjustified scope
  expansion is still stopped.
- AC-4 (FR19, NFR3): an auto-addition leaves an audit record carrying what
  was added and the evidence; a rejected one leaves its reason.
- AC-5 (D7): no new phase-state field is introduced; the audit trail reuses
  the completion-report `deviations` channel already defined in this
  document.
- AC-6 (NFR1, C6c/C6d): the declared set is referenced by path to the
  create-plan derivation, the two workflow-artifact root globs are never
  enumerated together, and no exclusion of workflow-generated artefacts from
  the observed change set is stated.
- AC-7 (NFR8): the repository-wide exclusion-rule guard
  (test_declared_change_set_invariants.py) still reports no offender for
  this document -- exercised by running the full suite, not re-asserted
  here (C4: that module's ownership is a different task).

Matcher -> negative-proof inventory (every matcher this module adds):

- `_states_evidence_gated_auto_addition` ->
  `TestMatchersFlagSyntheticSamples.
  test_conditional_auto_addition_matcher_requires_evidence_and_addition_together`
  and its unconditional-auto-addition counter-sample (Test Notes' named
  edge case).
- `_states_convenience_is_not_auto_added` ->
  `TestMatchersFlagSyntheticSamples.
  test_not_auto_added_matcher_requires_convenience_example_too`.
- `_states_containment_check_retained` ->
  `TestMatchersFlagSyntheticSamples.
  test_containment_retained_matcher_requires_both_clauses`.
- `_states_audit_record_rule` ->
  `TestMatchersFlagSyntheticSamples.
  test_audit_record_matcher_requires_all_three_clauses`.
- `_states_no_new_phase_state_field` ->
  `TestMatchersFlagSyntheticSamples.
  test_no_new_field_matcher_requires_channel_reference_too`.
- `_carries_default_membership_enumeration` (Contract MK shape, reused from
  the repository-wide guard per Test Notes' "same method" instruction) ->
  `TestMatchersFlagSyntheticSamples.
  test_carrier_matcher_requires_both_literals_not_just_one`.
- `_has_verify_side_exclusion_rule` (reused verbatim shape from the
  repository-wide guard, `tests/test_declared_change_set_invariants.py`,
  per Test Notes' "same method" instruction) ->
  `TestMatchersFlagSyntheticSamples.
  test_exclusion_matcher_requires_artifact_root_and_change_set_tokens_too`.

Every absence assertion's non-vacuity guard: the deviation-handling region
is asserted located and non-empty (`TestDeviationRegionIsLocated`); the
whole-document exclusion scan asserts the document was read and is
non-empty (`TestNoExclusionRuleStated.test_document_was_read`).

Round-1 rework (task0015, source_ids `45cc2053b58d2a24`) extends this
module with create-plan-phase.md-side assertions only (C4: task0015 owns
`references/phases/create-plan-phase.md`, never `implement-phase.md`,
which stays task0013's this round) -- pinning that §12's derivation cites
this document's auto-addition rule by path, without restating its evidence
condition, so the rule and its derivation target stay pinned together:

- `TestCreatePlanPhaseCitesAutoAdditionRule` -> task0015 AC-1 (FR19).
- `TestCreatePlanPhaseCitationMatchersFlagSyntheticSamples` -> negative
  proof for the two matchers this extension adds.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
IMPLEMENT_PHASE_PATH = (
    REPO_ROOT / "em-workflow" / "references" / "implement-phase.md"
)

# --- Region extraction: the deviation-handling paragraph this task adds,
# inside Step I.2.b point 3 (where implementer deviations are already
# collected), bounded by its own start marker and the next step's start.

REGION_START_ANCHOR = "**Deviation auto-addition rule**"
REGION_END_ANCHOR = "4. **Clean up**"

CREATE_PLAN_PHASE_PATH_LITERAL = "references/phases/create-plan-phase.md"

ROOT_LITERAL_FEATURE_DOCS = "feature-docs/{feature}/**"
ROOT_LITERAL_TEST_DOCS = "test-docs/{feature}/**"

# --- task0015 rework: create-plan-phase.md-side assertions only (C4). The
# file this task owns, read by literal path -- never implement-phase.md
# again (that stays this module's pre-existing, unmodified assertions).
CREATE_PLAN_PHASE_PATH = (
    REPO_ROOT / "em-workflow" / "references" / "phases" / "create-plan-phase.md"
)
DERIVATION_SECTION_HEADING = "## 12. Declared change set derivation"
IMPLEMENT_PHASE_PATH_LITERAL = "references/implement-phase.md"


def _derivation_section_of_create_plan_phase(text):
    start = text.index(DERIVATION_SECTION_HEADING)
    return text[start:]

# --- Reused verbatim from tests/test_declared_change_set_invariants.py
# (Test Notes: "reuse the existing repository-wide guard's matcher shape...
# so this task's own module fails for the same reason the shared guard
# would" -- TS-8's "same method" requirement). Kept as an independent copy
# rather than an import: this task owns only implement-phase.md and its own
# test module (C4), and the shared guard module belongs to a different,
# already-merged feature.
EXCLUSION_WORD_RE = re.compile(r"exclud\w*|subtract\w*|ignor\w*|除外", re.IGNORECASE)
ARTIFACT_ROOT_RE = re.compile(r"feature-docs/|test-docs/")
CHANGE_SET_TOKEN_RE = re.compile(
    r"change set|変更集合|containment|verification", re.IGNORECASE
)
EXCLUSION_PROXIMITY_WINDOW = 400


def _normalize_ws(text):
    """Collapse all whitespace runs (including line-wrap newlines) to a
    single space, so a phrase assertion survives this document's hard
    line-wrap column instead of depending on exactly where a wrap falls."""
    return re.sub(r"\s+", " ", text)


def _has_verify_side_exclusion_rule(text):
    text = _normalize_ws(text)
    for match in EXCLUSION_WORD_RE.finditer(text):
        start = max(0, match.start() - EXCLUSION_PROXIMITY_WINDOW)
        end = min(len(text), match.end() + EXCLUSION_PROXIMITY_WINDOW)
        window = text[start:end]
        if ARTIFACT_ROOT_RE.search(window) and CHANGE_SET_TOKEN_RE.search(window):
            return True
    return False


def _carries_default_membership_enumeration(text):
    """Contract MK shape (C6c): a document is a carrier only when BOTH root
    literals are enumerated together -- a single literal alone must not
    trip this."""
    return ROOT_LITERAL_FEATURE_DOCS in text and ROOT_LITERAL_TEST_DOCS in text


def _slice_region(text):
    start = text.index(REGION_START_ANCHOR)
    end = text.index(REGION_END_ANCHOR, start)
    return text[start:end]


# --- AC-1: evidence-gated auto-addition, stated as a named condition.

AUTO_ADD_WORD_RE = re.compile(r"auto-add\w*", re.IGNORECASE)
EVIDENCE_RE = re.compile(r"evidence", re.IGNORECASE)
CRITERION_DROPPED_RE = re.compile(
    r"acceptance criterion\w* would otherwise be dropped", re.IGNORECASE
)
GATING_RE = re.compile(r"only when", re.IGNORECASE)


def _states_evidence_gated_auto_addition(text):
    text = _normalize_ws(text)
    return bool(
        AUTO_ADD_WORD_RE.search(text)
        and EVIDENCE_RE.search(text)
        and CRITERION_DROPPED_RE.search(text)
        and GATING_RE.search(text)
    )


# --- AC-2: absent that evidence, not auto-added; convenience named.

NOT_AUTO_ADDED_RE = re.compile(r"not\s+auto-add\w*", re.IGNORECASE)
CONVENIENCE_RE = re.compile(r"implementer convenience", re.IGNORECASE)


def _states_convenience_is_not_auto_added(text):
    text = _normalize_ws(text)
    return bool(NOT_AUTO_ADDED_RE.search(text) and CONVENIENCE_RE.search(text))


# --- AC-3: containment check retained, scope expansion still stopped.

CONTAINMENT_RE = re.compile(r"containment check", re.IGNORECASE)
SCOPE_EXPANSION_RE = re.compile(
    r"unjustified scope expansion is still stopped", re.IGNORECASE
)


def _states_containment_check_retained(text):
    text = _normalize_ws(text)
    return bool(CONTAINMENT_RE.search(text) and SCOPE_EXPANSION_RE.search(text))


# --- AC-4: audit record carries what was added + evidence; rejection
# carries its reason.

AUDIT_RECORD_RE = re.compile(r"audit record", re.IGNORECASE)
REASON_RE = re.compile(r"reason", re.IGNORECASE)


def _states_audit_record_rule(text):
    text = _normalize_ws(text)
    return bool(
        AUDIT_RECORD_RE.search(text)
        and EVIDENCE_RE.search(text)
        and REASON_RE.search(text)
    )


# --- AC-5: no new phase-state field; reuses the completion-report channel.

NO_NEW_FIELD_RE = re.compile(r"no new phase-state field", re.IGNORECASE)
DEVIATIONS_CHANNEL_RE = re.compile(r"`deviations`\s+channel", re.IGNORECASE)


def _states_no_new_phase_state_field(text):
    text = _normalize_ws(text)
    return bool(NO_NEW_FIELD_RE.search(text) and DEVIATIONS_CHANNEL_RE.search(text))


class TestDeviationRegionIsLocated(unittest.TestCase):
    """Non-vacuity guard: the region every other test in this module scopes
    to actually exists and is non-empty."""

    @classmethod
    def setUpClass(cls):
        cls.full_text = IMPLEMENT_PHASE_PATH.read_text(encoding="utf-8")
        cls.region = _slice_region(cls.full_text)

    def test_document_exists_and_was_read(self):
        self.assertTrue(IMPLEMENT_PHASE_PATH.is_file())
        self.assertGreater(len(self.full_text), 0)

    def test_region_was_located_and_is_non_empty(self):
        self.assertGreater(len(self.region), 0)

    def test_region_is_inside_step_i_2_b_where_deviations_are_collected(self):
        # The deviations field this rule governs is already collected in
        # this same numbered step -- confirm the anchor really sits after
        # that collection point, not somewhere unrelated.
        collect_point = self.full_text.index('"deviations": [...]')
        region_start = self.full_text.index(REGION_START_ANCHOR)
        self.assertLess(collect_point, region_start)


class TestAC1EvidenceGatedAutoAddition(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.region = _slice_region(
            IMPLEMENT_PHASE_PATH.read_text(encoding="utf-8")
        )

    def test_states_evidence_gated_auto_addition(self):
        self.assertTrue(_states_evidence_gated_auto_addition(self.region))


class TestAC2ConvenienceDoesNotQualify(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.region = _slice_region(
            IMPLEMENT_PHASE_PATH.read_text(encoding="utf-8")
        )

    def test_states_convenience_is_not_auto_added(self):
        self.assertTrue(_states_convenience_is_not_auto_added(self.region))


class TestAC3ContainmentCheckRetained(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.region = _slice_region(
            IMPLEMENT_PHASE_PATH.read_text(encoding="utf-8")
        )

    def test_states_containment_check_retained(self):
        self.assertTrue(_states_containment_check_retained(self.region))


class TestAC4AuditRecordRule(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.region = _slice_region(
            IMPLEMENT_PHASE_PATH.read_text(encoding="utf-8")
        )

    def test_states_audit_record_rule(self):
        self.assertTrue(_states_audit_record_rule(self.region))


class TestAC5NoNewPhaseStateField(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.region = _slice_region(
            IMPLEMENT_PHASE_PATH.read_text(encoding="utf-8")
        )

    def test_states_no_new_phase_state_field(self):
        self.assertTrue(_states_no_new_phase_state_field(self.region))


class TestAC6DerivationCitationAndNoGlobEnumeration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.full_text = IMPLEMENT_PHASE_PATH.read_text(encoding="utf-8")
        cls.region = _slice_region(cls.full_text)

    def test_region_cites_the_create_plan_derivation_by_path(self):
        self.assertIn(CREATE_PLAN_PHASE_PATH_LITERAL, self.region)

    def test_derivation_is_not_restated_only_cited(self):
        # C2/C6c: the derivation's own enumeration (the two root globs)
        # must not be copied into this document.
        self.assertFalse(
            _carries_default_membership_enumeration(self.full_text)
        )

    def test_whole_document_never_enumerates_both_root_globs_together(self):
        self.assertFalse(
            _carries_default_membership_enumeration(self.full_text)
        )


class TestNoExclusionRuleStated(unittest.TestCase):
    """AC-6 / C6d: no statement that workflow-generated artefacts are
    excluded, ignored or subtracted from the observed change set at
    verification time. Scanned over the WHOLE document (not just the new
    region), matching the repository-wide guard's own scope."""

    @classmethod
    def setUpClass(cls):
        cls.full_text = IMPLEMENT_PHASE_PATH.read_text(encoding="utf-8")

    def test_document_was_read(self):
        self.assertGreater(len(self.full_text), 0)

    def test_no_verify_side_exclusion_rule_found(self):
        self.assertFalse(_has_verify_side_exclusion_rule(self.full_text))


class TestAC7FullSuiteOwnershipNote(unittest.TestCase):
    """AC-7's repository-wide guard is owned by a different, already-merged
    feature (tests/test_declared_change_set_invariants.py); C4 forbids this
    task's module from asserting over a file it does not own. This test
    only confirms that guard module exists and already scans
    implement-phase.md, so AC-7's claim is exercisable by the full suite
    run rather than silently unverifiable."""

    def test_shared_guard_module_exists_and_scans_this_document(self):
        guard_path = REPO_ROOT / "tests" / "test_declared_change_set_invariants.py"
        self.assertTrue(guard_path.is_file())
        guard_source = guard_path.read_text(encoding="utf-8")
        self.assertIn('"implement-phase.md"', guard_source)


class TestCreatePlanPhaseCitesAutoAdditionRule(unittest.TestCase):
    """task0015 AC-1 (FR19): create-plan-phase.md's §12 derivation section
    (task0009's/task0015's file) cites this document's auto-addition rule
    by path, without restating its evidence condition -- so the rule and
    its derivation target stay pinned together. C4: this class asserts only
    over create-plan-phase.md, the file task0015 owns; it does not touch
    this module's other, pre-existing implement-phase.md assertions."""

    @classmethod
    def setUpClass(cls):
        cls.full_text = CREATE_PLAN_PHASE_PATH.read_text(encoding="utf-8")
        cls.section = _derivation_section_of_create_plan_phase(cls.full_text)

    def test_document_exists_and_section_is_located_and_non_empty(self):
        self.assertTrue(CREATE_PLAN_PHASE_PATH.is_file())
        self.assertIn(DERIVATION_SECTION_HEADING, self.full_text)
        self.assertGreater(len(self.section), 0)

    def test_derivation_section_cites_this_document_by_path(self):
        self.assertIn(IMPLEMENT_PHASE_PATH_LITERAL, self.section)

    def test_derivation_section_does_not_restate_the_evidence_condition(self):
        self.assertFalse(CRITERION_DROPPED_RE.search(self.section))


class TestCreatePlanPhaseCitationMatchersFlagSyntheticSamples(unittest.TestCase):
    """Negative proof for the two matchers
    `TestCreatePlanPhaseCitesAutoAdditionRule` adds."""

    def test_citation_matcher_flags_absence_of_the_path_literal(self):
        sample = "## 12. Declared change set derivation\n\nNo citation here."
        self.assertNotIn(IMPLEMENT_PHASE_PATH_LITERAL, sample)

    def test_evidence_restatement_matcher_flags_a_synthetic_violation(self):
        bad_sample = (
            "## 12. Declared change set derivation\n\n"
            "admitted only when accompanied by evidence that an existing "
            "acceptance criterion would otherwise be dropped."
        )
        self.assertTrue(CRITERION_DROPPED_RE.search(bad_sample))


class TestMatchersFlagSyntheticSamples(unittest.TestCase):
    """Negative-proof tests, one per new matcher this module adds (module
    docstring inventory), each against a synthetic sample rather than the
    repository."""

    def test_conditional_auto_addition_matcher_requires_evidence_and_addition_together(
        self,
    ):
        gated_sample = (
            "a deviation is auto-added to the declaration only when it is "
            "accompanied by evidence that an existing acceptance criterion "
            "would otherwise be dropped."
        )
        self.assertTrue(_states_evidence_gated_auto_addition(gated_sample))

        # Test Notes' named edge case: unconditional auto-addition (the
        # addition word, with no evidence/gating clause) must NOT pass.
        unconditional_sample = (
            "every reported deviation is auto-added to the declared change "
            "set."
        )
        self.assertFalse(
            _states_evidence_gated_auto_addition(unconditional_sample)
        )

    def test_not_auto_added_matcher_requires_convenience_example_too(self):
        full_sample = (
            "a deviation lacking that evidence -- implementer convenience, "
            "a nicer structure -- is not auto-added."
        )
        self.assertTrue(_states_convenience_is_not_auto_added(full_sample))

        # "not auto-added" alone, no convenience example named, must fail.
        partial_sample = "some deviations are not auto-added to the set."
        self.assertFalse(
            _states_convenience_is_not_auto_added(partial_sample)
        )

    def test_containment_retained_matcher_requires_both_clauses(self):
        full_sample = (
            "the containment check is unchanged; unjustified scope "
            "expansion is still stopped exactly as before."
        )
        self.assertTrue(_states_containment_check_retained(full_sample))

        partial_sample = "the containment check still applies to every task."
        self.assertFalse(_states_containment_check_retained(partial_sample))

    def test_audit_record_matcher_requires_all_three_clauses(self):
        full_sample = (
            "an auto-addition leaves an audit record carrying the evidence "
            "that justified it; a rejected one leaves its reason."
        )
        self.assertTrue(_states_audit_record_rule(full_sample))

        partial_sample = "an audit record is kept for every deviation."
        self.assertFalse(_states_audit_record_rule(partial_sample))

    def test_no_new_field_matcher_requires_channel_reference_too(self):
        full_sample = (
            "no new phase-state field is introduced; the record reuses the "
            "completion-report `deviations` channel already defined above."
        )
        self.assertTrue(_states_no_new_phase_state_field(full_sample))

        partial_sample = "no new phase-state field is ever needed here."
        self.assertFalse(_states_no_new_phase_state_field(partial_sample))

    def test_carrier_matcher_requires_both_literals_not_just_one(self):
        both = (
            "default membership includes `feature-docs/{feature}/**` and "
            "`test-docs/{feature}/**`."
        )
        self.assertTrue(_carries_default_membership_enumeration(both))

        one_only = "see `feature-docs/{feature}/**` for the scope."
        self.assertFalse(_carries_default_membership_enumeration(one_only))

    def test_exclusion_matcher_requires_artifact_root_and_change_set_tokens_too(
        self,
    ):
        violating_sample = (
            "every workflow-generated artifact under `feature-docs/{feature}/**` "
            "is excluded from the observed change set at verification time."
        )
        self.assertTrue(_has_verify_side_exclusion_rule(violating_sample))

        bare_exclusion_word = (
            "unrelated data is ignored elsewhere in this paragraph, for a "
            "reason that has nothing to do with any artifact root."
        )
        self.assertFalse(_has_verify_side_exclusion_rule(bare_exclusion_word))


class TestModuleIsDiscoverableAndImportsStdlibOnly(unittest.TestCase):
    def test_module_filename(self):
        self.assertEqual(Path(__file__).name, "test_deviation_auto_addition.py")

    def test_this_module_only_imports_standard_library_modules(self):
        own_source = Path(__file__).read_text(encoding="utf-8")
        allowed_top_level_modules = {"re", "unittest", "pathlib"}
        imported = set(
            re.findall(
                r"^(?:import|from)\s+([a-zA-Z_][a-zA-Z0-9_]*)",
                own_source,
                re.MULTILINE,
            )
        )
        offenders = imported - allowed_top_level_modules
        self.assertEqual(offenders, set(), f"non-stdlib import(s): {offenders}")


if __name__ == "__main__":
    unittest.main()
