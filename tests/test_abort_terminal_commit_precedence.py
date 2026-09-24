"""Tests for abort-docs-commit-precedence/task0001: the "Precedence rule:"
paragraph in `em-workflow/references/batch-terminal-line.md` resolves the
one phase-specific-vs-phase-specific collision -- the batch second-failure
abort's terminal status commit (Step I.2.c abort-phase terminal status
commit) exhausting `commit-docs.sh` exit-4 recovery -- in favour of
`docs-commit-conflict` / `docs_commit_conflict_aborted`.

Covers task0001 Acceptance Criteria
(feature-docs/abort-docs-commit-precedence/tasks/task0001.md):

- AC-1 (FR1, TS-1): the paragraph names both `implement-second-failure` and
  `docs-commit-conflict` as matching the collision stop, states the
  commit-failure-caused-it winner rule, and binds the stop to
  `docs_commit_conflict_aborted`.
- AC-2 (FR2, TS-1): the paragraph states the stop ends the run (so neither
  `implement-second-failure` nor `stop-condition-3` sees a Step B
  evaluation of the uncommitted write in that run), and states the
  retry-success carve-out keeps `implement_task_failed`.
- AC-3 (FR3, TS-1): the existing "aborts without writing any status ...
  the failed status write is itself its stop cause" sentence stays, and
  new text states the written-but-uncommitted distinction plus a pointer
  to implement-phase.md's Branch & Worktree Model.
- AC-4 (FR8, NFR1, TS-1, TS-6): the paragraph confines the new resolution
  to the one collision and restates that the other four implement exit-4
  call sites keep their `docs_commit_conflict_aborted`-alone binding. The
  existing 13-code / 14-row pins in test_batch_stop_contract.py /
  test_failed_kind_batch_docs.py are not touched by this module and pass
  unchanged as part of the full suite run.
- AC-5 (NFR2, TS-1): the paragraph stays one blank-line-free block, every
  NFR2 anchor phrase survives, and `no-work-required` is not named.
- AC-6 (FR1, TS-2): every new matcher above fails against a verbatim
  pre-change sample of the paragraph, captured from the base revision
  (`git show HEAD:em-workflow/references/batch-terminal-line.md` before
  this task's edit) -- proving each assertion is non-vacuous.
- AC-7 (FR10, NFR3, NFR4, TS-7, TS-8): both manifests' em-workflow version
  is well-formed and at least `0.2.2`, and the two agree with each other
  (the existing version-lockstep test in test_plugin_version_parity.py
  only checks its own "past baseline" and "registries agree" columns;
  repo-suite-pinned-test-drift/task0003 replaced this module's `0.2.2`
  literal-equality pin with the same floor + form + agreement shape, so
  the check stays green at any later em-workflow version).

Test authoring follows this repository's doc-contract convention (see
tests/test_batch_stop_contract.py): read the file relative to the test
module, slice the owned region, normalize whitespace before phrase
matching, assert on distinctive phrases rather than whole sentences, and
give every new matcher a negative proof plus a non-vacuity guard.
"""

import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"
CONTRACT_PATH = PLUGIN_ROOT / "references" / "batch-terminal-line.md"
PLUGIN_MANIFEST_PATH = PLUGIN_ROOT / ".claude-plugin" / "plugin.json"
MARKETPLACE_PATH = REPO_ROOT / ".claude-plugin" / "marketplace.json"

# FR6: a floor, not an equality target -- the em-workflow version must be
# at least this value, never exactly this value. See the Version form rule
# / Lower-bound comparison / Registry agreement contracts in
# IMPLEMENTATION.md Shared Components.
FR6_VERSION_FLOOR = "0.2.2"

VERSION_FORM_RE = re.compile(r"^\d+\.\d+\.\d+$")

# The exact call-site phrase this feature's Shared Components table fixes
# for new document text (IMPLEMENTATION.md Shared Components: "Call-site
# name"). Distinct from the pre-existing possessive form
# ("Step I.2.c's abort-phase terminal status commit") that NFR2 keeps
# untouched elsewhere in implement-phase.md -- not asserted by this module,
# which owns only batch-terminal-line.md.
CALL_SITE_PHRASE = "Step I.2.c abort-phase terminal status commit"

# NFR2: anchors that must survive byte-for-byte inside the paragraph.
NFR2_ANCHORS = [
    "phase-specific stop point takes precedence over the generic",
    "through that phase's own abort route",
    "no route of the current run produced",
    "write a step's status",
    "aborts without writing any status",
    "the failed status write is itself its stop cause",
    "`implement-second-failure`",
    "`verify-rework-cap`",
    "`docs-commit-conflict`",
]

# Retired phrases the paragraph must never reintroduce.
RETIRED_PHRASES = [
    "no phase-specific row covers",
    "all three leave a step's status `failed`",
]

# Pre-change paragraph, captured verbatim from the base revision
# (`git show HEAD:em-workflow/references/batch-terminal-line.md`, this
# task's starting commit, before its own edit) -- never paraphrased or
# reconstructed. Used only as TS-2's negative-proof sample.
PRE_CHANGE_PRECEDENCE_PARAGRAPH = (
    "Precedence rule: when a stop matches more than one row above, the\n"
    "phase-specific stop point takes precedence over the generic\n"
    "`stop-condition-N` rows, so exactly one code applies.\n"
    "`implement-second-failure` and `verify-rework-cap` write a step's status\n"
    "`failed`, which is `stop-condition-3`'s own trigger; `docs-commit-conflict`\n"
    "aborts without writing any status, because the failed status write is\n"
    "itself its stop cause. A phase-specific row wins when the current run\n"
    "reaches the stop through that phase's own abort route. This includes\n"
    "`implement-second-failure`, which the same run realizes through its next\n"
    "Step B evaluation when that evaluation reads the `failed` the run wrote.\n"
    "Correspondingly, the `stop-condition-3` row's meaning binds a stop at Step\n"
    "B's entry evaluation that reads a `failed` / `needs_update` status no\n"
    "route of the current run produced — for example, a `failed` left by an\n"
    "earlier run's `implement-second-failure` — and, for the `implement`\n"
    "step's `failed`, further restricted to the cases where `failed_kind`\n"
    "reads `decision`, or where the automatic-resume attempt count has reached\n"
    "its cap per `skills/develop/SKILL.md` (see the `step_needs_intervention`\n"
    "row above)."
)


def _read(path):
    return path.read_text(encoding="utf-8")


# --- FR6 version matchers (form / lower-bound / registry agreement) -------


def _is_version_well_formed(value):
    """Version form rule: a string of exactly three dot-separated
    components, each a non-empty run of ASCII decimal digits."""
    return isinstance(value, str) and VERSION_FORM_RE.match(value) is not None


def _version_parts(value):
    return tuple(int(part) for part in value.split("."))


def _assert_version_well_formed(test, value, label):
    test.assertTrue(
        _is_version_well_formed(value),
        f"{label} version {value!r} is not of the form X.Y.Z",
    )


def _assert_version_at_least(test, value, floor, label):
    """Lower-bound comparison: `value` passes the form rule and its three
    components, compared as integers left to right, are at or above
    `floor`'s. Never a string comparison."""
    _assert_version_well_formed(test, value, label)
    test.assertGreaterEqual(
        _version_parts(value),
        _version_parts(floor),
        f"{label} version {value!r} is below the floor {floor!r}",
    )


def _assert_versions_agree(test, value_a, value_b, label_a, label_b):
    """Registry agreement: both sides pass the form rule and are identical.
    Neither side is compared with a literal."""
    _assert_version_well_formed(test, value_a, label_a)
    _assert_version_well_formed(test, value_b, label_b)
    test.assertEqual(
        value_a,
        value_b,
        f"{label_a} ({value_a!r}) disagrees with {label_b} ({value_b!r})",
    )


def _assert_fr6_pair_valid(test, manifest_version, entry_version, floor=FR6_VERSION_FLOOR):
    """FR6's combined matcher, used by the negative proofs below: each side
    is well-formed and at least `floor`, and the two sides agree."""
    _assert_version_at_least(test, manifest_version, floor, "plugin.json")
    _assert_version_at_least(test, entry_version, floor, "marketplace entry")
    _assert_versions_agree(
        test, entry_version, manifest_version, "marketplace entry", "plugin.json"
    )


def _normalize(text):
    """Collapses whitespace runs (including line wraps) to a single space,
    mirroring tests/test_batch_stop_contract.py's `_normalize` -- a prose
    phrase check must not depend on exactly where the source happens to
    wrap a line."""
    return re.sub(r"\s+", " ", text)


def _extract_precedence_paragraph(text):
    """Slices the "Precedence rule:" paragraph out of the full document
    text, from its label to the next blank line -- the same slicing
    semantics as test_batch_stop_contract.py's
    `_extract_precedence_rule_paragraph` (label unique in the document, so
    no section pre-slice is needed here). Returns "" when the label is
    absent, so a caller's assertion fails cleanly."""
    idx = text.find("Precedence rule:")
    if idx == -1:
        return ""
    end = text.find("\n\n", idx)
    if end == -1:
        end = len(text)
    return text[idx:end]


# --- per-AC matchers (each gets a negative proof in TestNegativeProofs) ----


def _assert_collision_binding_stated(test, paragraph):
    """AC-1: names both matching rows for the collision stop and states the
    winner rule and its binding."""
    normalized = _normalize(paragraph)
    test.assertIn(CALL_SITE_PHRASE, normalized)
    test.assertIn("exit 4 on its first attempt", normalized)
    test.assertIn("single exit-4 retry", normalized)
    test.assertIn("`implement-second-failure`", paragraph)
    test.assertIn("`docs-commit-conflict`", paragraph)
    test.assertIn(
        "row whose commit failure directly caused the stop wins", normalized
    )
    test.assertIn("binds to `docs_commit_conflict_aborted`", normalized)
    test.assertIn("not to `implement_task_failed`", normalized)


def _assert_terminal_stop_and_retry_carveout_stated(test, paragraph):
    """AC-2: the stop ends the run (no Step B evaluation of the uncommitted
    write happens in that run), and the retry-success carve-out keeps
    `implement_task_failed`."""
    normalized = _normalize(paragraph)
    test.assertIn("ends the run", normalized)
    test.assertIn("Step B entry evaluation", normalized)
    test.assertIn("uncommitted `implement: failed`", normalized)
    test.assertIn(
        "neither `implement-second-failure` nor `stop-condition-3` applies",
        normalized,
    )
    test.assertIn("successful retry", normalized)
    test.assertIn("keeps `implement_task_failed`", normalized)


def _assert_written_but_uncommitted_distinction_stated(test, paragraph):
    """AC-3: the existing no-status-written sentence stays, and new text
    states the written-but-uncommitted distinction plus a pointer (never a
    restatement) to implement-phase.md's Branch & Worktree Model."""
    normalized = _normalize(paragraph)
    test.assertIn("aborts without writing any status", normalized)
    test.assertIn("the failed status write is itself its stop cause", normalized)
    test.assertIn("exists in the integration worktree", normalized)
    test.assertIn("uncommitted", normalized)
    test.assertIn("never reaches the branch", normalized)
    test.assertIn("distinct from", normalized)
    test.assertIn("no status written", normalized)
    test.assertIn("abort terminal-commit exception", normalized)
    test.assertIn("implement-phase.md's Branch & Worktree Model", normalized)
    # Shared Components: the terminal status write is named with the pair
    # notation, never the "`failed_kind` reads `decision`" phrase -- an
    # existing anchor elsewhere in this same paragraph, for a different
    # restriction, so this checks adjacency rather than global absence.
    test.assertIn("`implement: failed`", paragraph)
    test.assertIn("`failed_kind: decision`", paragraph)


def _assert_scope_confined_stated(test, paragraph):
    """AC-4: the new resolution is confined to the one collision, and the
    other four implement exit-4 call sites keep their
    `docs_commit_conflict_aborted`-alone binding."""
    normalized = _normalize(paragraph)
    test.assertIn("confined to that one collision", normalized)
    for site in ("Step I.1", "Step I.2.a", "Step I.2.b", "Step I.3"):
        with test.subTest(site=site):
            test.assertIn(site, normalized)
    test.assertIn(
        "exit-4 stops keep their binding to `docs_commit_conflict_aborted` alone",
        normalized,
    )


def _assert_nfr2_anchors_preserved(test, paragraph):
    """AC-5: the paragraph stays one blank-line-free block, every NFR2
    anchor phrase survives, and `no-work-required` is never named. The
    no-blank-line check reads the RAW paragraph (whitespace normalization
    would itself collapse a blank line and defeat the check); every phrase
    check reads the normalized text, since two of the anchors wrap across
    a source line break."""
    test.assertTrue(paragraph, "no 'Precedence rule:' paragraph found")
    test.assertNotIn("\n\n", paragraph)
    normalized = _normalize(paragraph)
    for anchor in NFR2_ANCHORS:
        with test.subTest(anchor=anchor):
            test.assertIn(anchor, normalized)
    test.assertNotIn("no-work-required", normalized)
    for retired in RETIRED_PHRASES:
        with test.subTest(retired=retired):
            test.assertNotIn(retired, normalized)


ALL_MATCHERS = [
    _assert_collision_binding_stated,
    _assert_terminal_stop_and_retry_carveout_stated,
    _assert_written_but_uncommitted_distinction_stated,
    _assert_scope_confined_stated,
    _assert_nfr2_anchors_preserved,
]


class TestDocumentExists(unittest.TestCase):
    def test_document_exists(self):
        self.assertTrue(CONTRACT_PATH.is_file())


class TestPrecedenceParagraphExtraction(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(CONTRACT_PATH)
        cls.paragraph = _extract_precedence_paragraph(cls.text)

    def test_paragraph_is_non_empty(self):
        self.assertTrue(self.paragraph)

    def test_paragraph_has_no_blank_line(self):
        """The design constraint this whole task follows: append within
        the same paragraph, never insert a blank line."""
        self.assertNotIn("\n\n", self.paragraph)


class TestCollisionBindingStated(TestPrecedenceParagraphExtraction):
    """AC-1."""

    def test_collision_binding_stated(self):
        _assert_collision_binding_stated(self, self.paragraph)


class TestTerminalStopAndRetryCarveoutStated(TestPrecedenceParagraphExtraction):
    """AC-2."""

    def test_terminal_stop_and_retry_carveout_stated(self):
        _assert_terminal_stop_and_retry_carveout_stated(self, self.paragraph)


class TestWrittenButUncommittedDistinctionStated(TestPrecedenceParagraphExtraction):
    """AC-3."""

    def test_written_but_uncommitted_distinction_stated(self):
        _assert_written_but_uncommitted_distinction_stated(self, self.paragraph)


class TestScopeConfinedStated(TestPrecedenceParagraphExtraction):
    """AC-4."""

    def test_scope_confined_stated(self):
        _assert_scope_confined_stated(self, self.paragraph)


class TestNfr2AnchorsPreserved(TestPrecedenceParagraphExtraction):
    """AC-5."""

    def test_nfr2_anchors_preserved(self):
        _assert_nfr2_anchors_preserved(self, self.paragraph)


class TestPreChangeSampleIsTheRealParagraph(unittest.TestCase):
    """Non-vacuity guard for TS-2's negative proof below: the captured
    pre-change sample really is the Precedence paragraph (carries an
    existing NFR2 anchor and the three phase-specific stop-point keys),
    not an unrelated or empty string."""

    def test_sample_carries_an_nfr2_anchor(self):
        self.assertIn(
            "phase-specific stop point takes precedence over the generic",
            PRE_CHANGE_PRECEDENCE_PARAGRAPH,
        )

    def test_sample_carries_the_three_phase_specific_stop_points(self):
        for key in (
            "`implement-second-failure`",
            "`verify-rework-cap`",
            "`docs-commit-conflict`",
        ):
            with self.subTest(key=key):
                self.assertIn(key, PRE_CHANGE_PRECEDENCE_PARAGRAPH)

    def test_sample_has_no_blank_line(self):
        """The pre-change paragraph was already blank-line-free -- the
        positive `test_paragraph_has_no_blank_line` test above is not
        vacuously true just because slicing always stops at the first
        blank line regardless of content."""
        self.assertNotIn("\n\n", PRE_CHANGE_PRECEDENCE_PARAGRAPH)

    def test_sample_does_not_yet_state_the_collision_binding(self):
        """Confirms the sample predates this task's edit -- it must not
        already contain the new call-site phrase."""
        self.assertNotIn(CALL_SITE_PHRASE, PRE_CHANGE_PRECEDENCE_PARAGRAPH)


class TestNegativeProofs(unittest.TestCase):
    """AC-6/TS-2: every new matcher above fails against the verbatim
    pre-change paragraph -- proving none of them is satisfiable by the
    "otherwise well formed" pre-change text, i.e. none is vacuous."""

    def test_collision_binding_matcher_rejects_pre_change_paragraph(self):
        with self.assertRaises(AssertionError):
            _assert_collision_binding_stated(self, PRE_CHANGE_PRECEDENCE_PARAGRAPH)

    def test_terminal_stop_carveout_matcher_rejects_pre_change_paragraph(self):
        with self.assertRaises(AssertionError):
            _assert_terminal_stop_and_retry_carveout_stated(
                self, PRE_CHANGE_PRECEDENCE_PARAGRAPH
            )

    def test_written_but_uncommitted_matcher_rejects_pre_change_paragraph(self):
        with self.assertRaises(AssertionError):
            _assert_written_but_uncommitted_distinction_stated(
                self, PRE_CHANGE_PRECEDENCE_PARAGRAPH
            )

    def test_scope_confined_matcher_rejects_pre_change_paragraph(self):
        with self.assertRaises(AssertionError):
            _assert_scope_confined_stated(self, PRE_CHANGE_PRECEDENCE_PARAGRAPH)

    def test_nfr2_anchors_matcher_accepts_pre_change_paragraph(self):
        """The one matcher that is a pure regression guard rather than a
        NEW-statement guard: NFR2_ANCHORS are all pre-existing text, so
        this matcher must ACCEPT the pre-change paragraph (it does not
        assert the new statements at all). Proves
        `_assert_nfr2_anchors_preserved` is not itself vacuous in the
        other direction -- it still requires every anchor and the
        no-blank-line invariant even before this task's edit."""
        _assert_nfr2_anchors_preserved(self, PRE_CHANGE_PRECEDENCE_PARAGRAPH)


class TestVersionBump(unittest.TestCase):
    """AC-7: both manifests' em-workflow version is well-formed and at
    least FR6_VERSION_FLOOR (0.2.2), and the two agree with each other. The
    existing test_plugin_version_parity.py checks its own "past baseline"
    and "registries agree" columns; this module additionally enforces the
    0.2.2 floor this task's plan requires -- never a literal-equality pin,
    so the checks stay green at any later em-workflow version."""

    @classmethod
    def setUpClass(cls):
        cls.manifest_data = json.loads(_read(PLUGIN_MANIFEST_PATH))
        marketplace_data = json.loads(_read(MARKETPLACE_PATH))
        cls.entry = next(
            (p for p in marketplace_data.get("plugins", []) if p.get("name") == "em-workflow"),
            None,
        )

    def test_plugin_manifest_version_is_well_formed_and_at_least_0_2_2(self):
        _assert_version_at_least(
            self, self.manifest_data.get("version"), FR6_VERSION_FLOOR, "plugin.json"
        )

    def test_marketplace_em_workflow_entry_version_is_well_formed_at_least_0_2_2_and_agrees_with_manifest(
        self,
    ):
        self.assertIsNotNone(self.entry, "no marketplace entry named 'em-workflow'")
        _assert_version_at_least(
            self, self.entry.get("version"), FR6_VERSION_FLOOR, "marketplace entry"
        )
        _assert_versions_agree(
            self,
            self.entry.get("version"),
            self.manifest_data.get("version"),
            "marketplace entry",
            "plugin.json",
        )


# Malformed values from every kind the Version form rule rejects: two
# components, a non-digit component, a "v" prefix, a pre-release suffix, an
# empty string, a non-string value.
FR6_MALFORMED_VERSIONS = ["0.2", "0.2.x", "v0.2.4", "0.2.4-rc1", "", None]


class TestFr6VersionMatcherNegativeProofs(unittest.TestCase):
    """AC-2: the FR6 combined matcher's verdicts against forged values --
    hermetic (NFR3), never touches the real manifest files."""

    def test_accepts_a_forged_higher_version_in_both_registries(self):
        _assert_fr6_pair_valid(self, "99.0.0", "99.0.0")  # must not raise

    def test_accepts_a_two_digit_patch_component_via_numeric_comparison(self):
        # Proves the comparison is per-component numeric, not lexicographic:
        # lexicographically "0.2.10" < "0.2.2" (the character '1' < '2').
        _assert_fr6_pair_valid(self, "0.2.10", "0.2.10")  # must not raise

    def test_rejects_a_version_below_the_floor_in_both_registries(self):
        with self.assertRaises(AssertionError):
            _assert_fr6_pair_valid(self, "0.2.1", "0.2.1")

    def test_rejects_a_malformed_value_in_either_registry(self):
        # 5.5.5: an arbitrary well-formed, above-floor companion value --
        # never a current-version literal (NFR2) -- so the malformed side
        # alone is what triggers the rejection.
        for malformed in FR6_MALFORMED_VERSIONS:
            with self.subTest(malformed=malformed, side="manifest"):
                with self.assertRaises(AssertionError):
                    _assert_fr6_pair_valid(self, malformed, "5.5.5")
            with self.subTest(malformed=malformed, side="entry"):
                with self.assertRaises(AssertionError):
                    _assert_fr6_pair_valid(self, "5.5.5", malformed)

    def test_rejects_disagreeing_registries(self):
        with self.assertRaises(AssertionError):
            _assert_fr6_pair_valid(self, "5.5.5", "5.5.6")


if __name__ == "__main__":
    unittest.main()
