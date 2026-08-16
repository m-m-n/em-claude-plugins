"""Tests for task0004 (spec-file-set-completeness): invariant guards over the
declared change set this feature introduces -- pinned in this module even
though this task edits no production file (IMPLEMENTATION.md D7 / task0004.md
Design). Every scanned document listed below is one FR6 or FR7 forbids this
task from modifying; a failing guard is fixed by narrowing the matcher or by
reporting a genuine finding, never by editing the scanned document.

Covers task0004 Acceptance Criteria
(feature-docs/spec-file-set-completeness/tasks/task0004.md):

- AC-1 (FR6, NFR1) / G1 / TS-8: no verify-side exclusion rule exists in the
  six named phase/protocol documents or under `references/contracts/`; the
  scan is non-vacuous and the known create-spec-phase near miss ("excluding
  the HEAD layer" / "the worker's change set", about scope-snapshot staleness
  detection, not about the observed change set at verification time) is not
  reported.
- AC-2 (FR7) / G2 / TS-9: the already-consistent recycled-task-id-consistency
  feature-docs still enumerate `test-docs/recycled-task-id-consistency/**` in
  SPEC.md's FR8 and AC-8 statements and in REQUIREMENTS.md's FR8 constraint,
  read by explicit literal path (never by wildcard).
- AC-3 (NFR2) / G3 / TS-11: the default-membership enumeration (Contract MK:
  co-occurrence of BOTH root literals, never a single literal) carries in a
  subset of the two template paths across the whole plugin directory;
  `review-phase.md` and `implement-phase.md` are confirmed non-carriers.
- AC-4 (NFR6) / G4 / TS-12: no module under `tests/` combines a wildcard/glob
  scan of SPEC paths under `feature-docs/` with a requirement that the
  Declared Change Set section be present; this module itself reads existing
  feature-docs only by literal path.
- AC-5 (NFR5): this module exists, is discovered by
  `python3 -m unittest discover -s tests`, and imports nothing outside the
  Python standard library.
- AC-6 (NFR5): every matcher other than the TS-9 retention pin carries a
  negative proof against a synthetic violating sample, and every absence
  assertion carries a non-vacuity guard (see the inventory below).
- AC-7 (FR8, NFR1, NFR4): this task creates only this module; every
  pre-existing module under `tests/` is left untouched by construction (no
  other file is written by this task), and the full suite passes.

Matcher -> negative-proof inventory (AC-6; every matcher this module adds):

- `_has_verify_side_exclusion_rule` (G1 / TS-8) ->
  `TestNewMatchersFlagSyntheticViolations.
  test_verify_side_exclusion_matcher_flags_a_synthetic_violation`, plus two
  conjunction-refinement tests proving a partial match (missing one of the
  three required tokens) does not trip it.
- `_carries_default_membership_enumeration` (G3 / TS-11) ->
  `TestNewMatchersFlagSyntheticViolations.
  test_carrier_matcher_flags_a_synthetic_sample_with_both_literals`, plus a
  single-literal refinement test (Contract MK's explicit warning: a single
  literal must never be treated as a carrier).
- `_is_spec_wildcard_section_requirement_offender` (G4 / TS-12) ->
  `TestNewMatchersFlagSyntheticViolations.
  test_wildcard_section_requirement_matcher_flags_a_synthetic_module`, plus
  two refinement tests proving each half alone is insufficient.
- G2's retention pin (`TestRecycledTaskIdRetentionPin`) is EXPLICITLY EXEMPT
  from a negative proof, per IMPLEMENTATION.md's Conventions ("Negative proof
  and non-vacuity"): it is green before and after this feature and asserts
  retention of content this task did not write, so there is no "pre-change
  wording" to construct a violation from.

Every absence assertion's non-vacuity guard: G1's scan asserts every scanned
path exists and was read, and that the `references/contracts/` directory scan
(walked, not hard-coded) is non-empty. G3's scan asserts the plugin-directory
walk visited a non-trivial number of files. G4's scan asserts the `tests/`
walk found at least the pre-existing modules, naming one by path.

Content assertions in this module read raw, un-normalized text throughout:
every scenario here is a substring / regex co-occurrence check over document
or source text, never a byte-identity or line-wrap-sensitive assertion, so no
`_normalize_ws`-style helper is needed (unlike the whitespace-sensitive
line-wrap literals task0001/task0002 pin).
"""

import os
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"
TESTS_DIR = REPO_ROOT / "tests"

# --- G1 (TS-8 / FR6): the six named phase/protocol documents, plus every
# file directly under references/contracts/ (walked, not hard-coded --
# Test Notes edge case: the contracts directory may gain files later).

CREATE_SPEC_PHASE_PATH = PLUGIN_ROOT / "references" / "phases" / "create-spec-phase.md"

G1_NAMED_DOCS = [
    PLUGIN_ROOT / "references" / "implement-phase.md",
    PLUGIN_ROOT / "references" / "review-phase.md",
    PLUGIN_ROOT / "references" / "review-protocol.md",
    CREATE_SPEC_PHASE_PATH,
    PLUGIN_ROOT / "references" / "phases" / "create-plan-phase.md",
    PLUGIN_ROOT / "references" / "rework-task-synthesis.md",
]
CONTRACTS_DIR = PLUGIN_ROOT / "references" / "contracts"

# Matcher tokens (task0004.md G1): all three categories must co-occur within
# one proximity window -- a bare exclusion word, or an exclusion word merely
# sharing a document with an artifact-root literal, is not enough (that
# looser form is exactly what would misfire on the known near miss below).
EXCLUSION_WORD_RE = re.compile(r"exclud\w*|subtract\w*|ignor\w*|除外", re.IGNORECASE)
ARTIFACT_ROOT_RE = re.compile(r"feature-docs/|test-docs/")
CHANGE_SET_TOKEN_RE = re.compile(
    r"change set|変更集合|containment|verification", re.IGNORECASE
)
G1_PROXIMITY_WINDOW = 400  # characters on each side of an exclusion-word hit


def _has_verify_side_exclusion_rule(text):
    """TS-8 / FR6 matcher: flags a statement that removes workflow-generated
    artifacts from the observed change set at verification time. Requires an
    exclusion expression, a workflow-artifact-root token, and a change-set /
    verification token, all within one proximity window of the exclusion
    word -- never a bare exclusion word alone."""
    for match in EXCLUSION_WORD_RE.finditer(text):
        start = max(0, match.start() - G1_PROXIMITY_WINDOW)
        end = min(len(text), match.end() + G1_PROXIMITY_WINDOW)
        window = text[start:end]
        if ARTIFACT_ROOT_RE.search(window) and CHANGE_SET_TOKEN_RE.search(window):
            return True
    return False


# --- G2 (TS-9 / FR7): retention pin. Read by explicit literal path only.

RECYCLED_SPEC_PATH = (
    REPO_ROOT / "feature-docs" / "recycled-task-id-consistency" / "SPEC.md"
)
RECYCLED_REQUIREMENTS_PATH = (
    REPO_ROOT / "feature-docs" / "recycled-task-id-consistency" / "REQUIREMENTS.md"
)

TEST_DOCS_RECYCLED_PATH_LITERAL = "test-docs/recycled-task-id-consistency/"

SPEC_FR8_ANCHOR = "- **FR8 — Change containment:**"
SPEC_FR9_ANCHOR = "- **FR9 —"
SPEC_AC8_ANCHOR = "- [ ] AC-8 (FR8):"
SPEC_AC9_ANCHOR = "- [ ] AC-9 (FR9):"
REQ_FR8_ANCHOR = "#### FR8:"
REQ_FR9_ANCHOR = "#### FR9:"


def _slice(text, start_anchor, end_anchor):
    start = text.index(start_anchor)
    end = text.index(end_anchor, start + len(start_anchor))
    return text[start:end]


# --- G3 (TS-11 / NFR2): Contract MK co-occurrence marker, scoped to the
# plugin directory only (D6: this feature's own SPEC.md legitimately
# contains both root literals, so the scan root is asserted explicitly
# rather than left implicit -- see the dedicated scope test below).

ROOT_LITERAL_FEATURE_DOCS = "feature-docs/{feature}/**"
ROOT_LITERAL_TEST_DOCS = "test-docs/{feature}/**"

TEMPLATE_SPEC_PATH = PLUGIN_ROOT / "references" / "templates" / "spec-document.md"
TEMPLATE_REQUIREMENTS_PATH = (
    PLUGIN_ROOT / "references" / "templates" / "requirements-document.md"
)
ALLOWED_CARRIER_PATHS = {
    TEMPLATE_SPEC_PATH.resolve(),
    TEMPLATE_REQUIREMENTS_PATH.resolve(),
}

REVIEW_PHASE_PATH = PLUGIN_ROOT / "references" / "review-phase.md"
IMPLEMENT_PHASE_PATH = PLUGIN_ROOT / "references" / "implement-phase.md"


def _carries_default_membership_enumeration(text):
    """Contract MK: a file carries the enumeration if and only if it
    contains BOTH root literals. Single-literal matching is wrong and must
    not be used -- review-phase.md already carries the feature-docs literal
    alone, and implement-phase.md already carries a test-docs path without
    the double-star form; neither is a carrier under this definition."""
    return ROOT_LITERAL_FEATURE_DOCS in text and ROOT_LITERAL_TEST_DOCS in text


def _iter_plugin_directory_files():
    # os.walk does not follow symlinked directories by default, so this
    # walk never leaves the plugin directory via a symlink hop (Test Notes
    # edge case).
    for dirpath, _dirnames, filenames in os.walk(PLUGIN_ROOT):
        for filename in filenames:
            yield Path(dirpath) / filename


def _read_text_or_none(path):
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        # Binary or unreadable content is skipped gracefully (Test Notes
        # edge case), never treated as a scan failure.
        return None


# --- G4 (TS-12 / NFR6): no module under tests/ combines a wildcard/glob
# scan of SPEC paths under feature-docs/ with a requirement that the
# Declared Change Set section be present.

DECLARED_CHANGE_SET_SECTION_TOKENS = ("Declared Change Set", "宣言された変更集合")
WILDCARD_INDICATOR_RE = re.compile(r"\*|\.glob\(|\.rglob\(|os\.walk\(")
REQUIREMENT_INDICATOR_RE = re.compile(r"assertIn|assertTrue|self\.assert")
G4_WINDOW = 300

# This module's own docstring and constants legitimately discuss
# "feature-docs", "SPEC.md" and wildcard literals side by side (G2's
# RECYCLED_SPEC_PATH, G3's ROOT_LITERAL_FEATURE_DOCS, and this section's own
# TestNewMatchersFlagSyntheticViolations fixtures, which must contain the
# violating pattern verbatim to prove the matcher fires on it) -- none of it
# is an actual glob/rglob/os.walk call against real feature-docs. Excluded
# from its own G4 scan below, the same way check-plugin-invariants.py's
# self-referencing STALE_AGENT_NAME constant is excluded via
# SELF_EXCLUDED_PLUGIN_FILE in test_reference_sweep.py. G2's
# RECYCLED_SPEC_PATH / RECYCLED_REQUIREMENTS_PATH constants above are this
# module's only actual feature-docs reads, and both are literal Path joins,
# never a glob.
G4_SELF_EXCLUDED_PATH = Path(__file__).resolve()


def _has_spec_wildcard_over_feature_docs(source):
    for match in re.finditer(r"feature-docs", source):
        start = max(0, match.start() - G4_WINDOW)
        end = min(len(source), match.end() + G4_WINDOW)
        window = source[start:end]
        if "SPEC.md" in window and WILDCARD_INDICATOR_RE.search(window):
            return True
    return False


def _requires_declared_change_set_section(source):
    for token in DECLARED_CHANGE_SET_SECTION_TOKENS:
        for match in re.finditer(re.escape(token), source):
            start = max(0, match.start() - G4_WINDOW)
            end = min(len(source), match.end() + G4_WINDOW)
            window = source[start:end]
            if REQUIREMENT_INDICATOR_RE.search(window):
                return True
    return False


def _is_spec_wildcard_section_requirement_offender(source):
    return _has_spec_wildcard_over_feature_docs(
        source
    ) and _requires_declared_change_set_section(source)


class TestNoVerifySideExclusionRule(unittest.TestCase):
    """G1 / TS-8 / AC-1 (FR6, NFR1)."""

    @classmethod
    def setUpClass(cls):
        cls.contracts_files = sorted(p for p in CONTRACTS_DIR.iterdir() if p.is_file())
        cls.scanned_paths = list(G1_NAMED_DOCS) + cls.contracts_files
        cls.texts = {path: path.read_text(encoding="utf-8") for path in cls.scanned_paths}
        cls.offenders = [
            str(path.relative_to(REPO_ROOT))
            for path, text in cls.texts.items()
            if _has_verify_side_exclusion_rule(text)
        ]

    def test_no_offender_found(self):
        self.assertEqual(
            self.offenders,
            [],
            f"verify-side exclusion rule found in: {self.offenders}",
        )

    def test_every_scanned_path_exists_and_was_read(self):
        self.assertTrue(self.scanned_paths)
        for path in self.scanned_paths:
            self.assertTrue(path.is_file(), f"{path} does not exist")
            self.assertGreater(len(self.texts[path]), 0, f"{path} was not read")

    def test_contracts_directory_scan_is_nonempty(self):
        self.assertTrue(
            self.contracts_files, "references/contracts/ walk found no files"
        )

    def test_known_create_spec_near_miss_is_present_but_not_flagged(self):
        # The near miss the task plan names: excluding the HEAD layer from
        # the scope-snapshot computation, in the same document as "the
        # worker's change set" -- about which snapshot layer the scope
        # check reads, not about subtracting artifacts from the observed
        # change set. Confirm the phrase is actually there (so this proves
        # something about the real near miss, not a strawman), then confirm
        # the matcher does not flag the document it lives in.
        text = self.texts[CREATE_SPEC_PHASE_PATH]
        self.assertIn("Excluding the HEAD layer from step 1", text)
        self.assertIn("the worker's change set", text)
        self.assertFalse(_has_verify_side_exclusion_rule(text))


class TestRecycledTaskIdRetentionPin(unittest.TestCase):
    """G2 / TS-9 / AC-2 (FR7). Retention matcher: green before and after
    this feature, no negative proof needed (see module docstring's
    exemption list) -- both files are read by explicit literal path, never
    by wildcard (G4's own concern)."""

    @classmethod
    def setUpClass(cls):
        cls.spec_text = RECYCLED_SPEC_PATH.read_text(encoding="utf-8")
        cls.requirements_text = RECYCLED_REQUIREMENTS_PATH.read_text(encoding="utf-8")

    def test_spec_fr8_still_enumerates_the_test_docs_path(self):
        section = _slice(self.spec_text, SPEC_FR8_ANCHOR, SPEC_FR9_ANCHOR)
        self.assertIn(TEST_DOCS_RECYCLED_PATH_LITERAL, section)

    def test_spec_ac8_still_enumerates_the_test_docs_path(self):
        section = _slice(self.spec_text, SPEC_AC8_ANCHOR, SPEC_AC9_ANCHOR)
        self.assertIn(TEST_DOCS_RECYCLED_PATH_LITERAL, section)

    def test_requirements_fr8_still_enumerates_the_test_docs_path(self):
        section = _slice(self.requirements_text, REQ_FR8_ANCHOR, REQ_FR9_ANCHOR)
        self.assertIn(TEST_DOCS_RECYCLED_PATH_LITERAL, section)


class TestNoThirdRestatementOfDefaultMembership(unittest.TestCase):
    """G3 / TS-11 / AC-3 (NFR2)."""

    @classmethod
    def setUpClass(cls):
        cls.scanned = list(_iter_plugin_directory_files())
        cls.carriers = []
        for path in cls.scanned:
            text = _read_text_or_none(path)
            if text is not None and _carries_default_membership_enumeration(text):
                cls.carriers.append(path.resolve())

    def test_walk_visited_a_nontrivial_number_of_files(self):
        self.assertGreater(len(self.scanned), 100)

    def test_scan_root_is_the_plugin_directory_excluding_feature_docs(self):
        # D6: this feature's own SPEC.md legitimately contains both root
        # literals as prose describing the feature; the scan root is
        # asserted explicitly here so that document is never in scope.
        self.assertEqual(PLUGIN_ROOT, REPO_ROOT / "em-workflow")
        this_feature_spec = (
            REPO_ROOT / "feature-docs" / "spec-file-set-completeness" / "SPEC.md"
        )
        scanned_resolved = {p.resolve() for p in self.scanned}
        self.assertNotIn(this_feature_spec.resolve(), scanned_resolved)

    def test_carrier_set_is_subset_of_the_two_templates(self):
        offenders = [str(p) for p in self.carriers if p not in ALLOWED_CARRIER_PATHS]
        self.assertEqual(offenders, [], f"unexpected carrier(s): {offenders}")

    def test_review_phase_is_not_a_carrier(self):
        self.assertNotIn(REVIEW_PHASE_PATH.resolve(), self.carriers)

    def test_implement_phase_is_not_a_carrier(self):
        self.assertNotIn(IMPLEMENT_PHASE_PATH.resolve(), self.carriers)


class TestNoRetroactiveObligationOnExistingSpecs(unittest.TestCase):
    """G4 / TS-12 / AC-4 (NFR6)."""

    @classmethod
    def setUpClass(cls):
        cls.scanned = sorted(TESTS_DIR.glob("*.py"))
        cls.offenders = []
        for path in cls.scanned:
            if path.resolve() == G4_SELF_EXCLUDED_PATH:
                continue
            text = _read_text_or_none(path)
            if text is not None and _is_spec_wildcard_section_requirement_offender(
                text
            ):
                cls.offenders.append(str(path.relative_to(REPO_ROOT)))

    def test_no_module_combines_a_spec_wildcard_with_the_section_requirement(self):
        self.assertEqual(
            self.offenders,
            [],
            f"wildcard-obligation offender(s) found: {self.offenders}",
        )

    def test_walk_found_at_least_the_existing_modules(self):
        self.assertGreaterEqual(len(self.scanned), 20)
        self.assertIn(
            TESTS_DIR / "test_recycled_task_id_consistency.py", self.scanned
        )

    def test_this_modules_actual_feature_docs_reads_are_literal_paths(self):
        # AC-4's "reads existing feature-docs only by literal path" refers
        # to G2's actual reads (RECYCLED_SPEC_PATH / RECYCLED_REQUIREMENTS_PATH
        # above), not to the demonstration text inside this module's own
        # negative-proof fixtures (see G4_SELF_EXCLUDED_PATH's rationale).
        self.assertIn("recycled-task-id-consistency", str(RECYCLED_SPEC_PATH))
        self.assertIn("recycled-task-id-consistency", str(RECYCLED_REQUIREMENTS_PATH))
        self.assertTrue(RECYCLED_SPEC_PATH.is_file())
        self.assertTrue(RECYCLED_REQUIREMENTS_PATH.is_file())


class TestModuleIsDiscoverableAndImportsStdlibOnly(unittest.TestCase):
    """AC-5 (NFR5)."""

    def test_module_filename_matches_the_contract_mi_inventory(self):
        self.assertEqual(
            Path(__file__).name, "test_declared_change_set_invariants.py"
        )

    def test_this_module_only_imports_standard_library_modules(self):
        own_source = Path(__file__).read_text(encoding="utf-8")
        allowed_top_level_modules = {"os", "re", "unittest", "pathlib"}
        imported = set(
            re.findall(
                r"^(?:import|from)\s+([a-zA-Z_][a-zA-Z0-9_]*)",
                own_source,
                re.MULTILINE,
            )
        )
        offenders = imported - allowed_top_level_modules
        self.assertEqual(offenders, set(), f"non-stdlib import(s): {offenders}")


class TestNewMatchersFlagSyntheticViolations(unittest.TestCase):
    """AC-6: negative-proof tests, one per new matcher this module adds
    (see the module docstring's inventory) -- each demonstrated against a
    synthetic sample rather than the repository, per tdd-testing discipline
    (a guard that has never been seen to fire is not a guard). G2's
    retention pin is the sole exemption (module docstring)."""

    def test_verify_side_exclusion_matcher_flags_a_synthetic_violation(self):
        sample = (
            "Every workflow-generated artifact under `feature-docs/{feature}/**` "
            "and `test-docs/{feature}/**` is excluded from the observed change "
            "set at verification time."
        )
        self.assertTrue(_has_verify_side_exclusion_rule(sample))

    def test_verify_side_exclusion_matcher_requires_the_artifact_root_token(self):
        # "excluded" + a change-set token, but no feature-docs/test-docs
        # literal anywhere -- must not trip the matcher alone.
        sample = (
            "Ignored data is excluded from the containment check at "
            "verification time."
        )
        self.assertFalse(_has_verify_side_exclusion_rule(sample))

    def test_verify_side_exclusion_matcher_requires_the_change_set_token(self):
        # "excluded" + an artifact-root literal, but neither "change set",
        # "containment" nor "verification" anywhere -- the create-spec-phase
        # near miss's shape, restated as a minimal synthetic case.
        sample = (
            "The HEAD layer is excluded from step 1's computation; "
            "`feature-docs/{feature}/**` is mentioned elsewhere in this "
            "same paragraph for an unrelated reason."
        )
        self.assertFalse(_has_verify_side_exclusion_rule(sample))

    def test_carrier_matcher_flags_a_synthetic_sample_with_both_literals(self):
        sample = (
            "Default membership includes `feature-docs/{feature}/**` and "
            "`test-docs/{feature}/**`."
        )
        self.assertTrue(_carries_default_membership_enumeration(sample))

    def test_carrier_matcher_requires_both_literals_not_just_one(self):
        # Contract MK's explicit warning: single-literal matching is wrong.
        feature_docs_only = "See `feature-docs/{feature}/**` for the scope."
        test_docs_only = "See `test-docs/{feature}/**` for the scope."
        self.assertFalse(_carries_default_membership_enumeration(feature_docs_only))
        self.assertFalse(_carries_default_membership_enumeration(test_docs_only))

    def test_wildcard_section_requirement_matcher_flags_a_synthetic_module(self):
        sample = (
            "import glob\n"
            "for path in glob.glob('feature-docs/*/SPEC.md'):\n"
            "    text = open(path).read()\n"
            "    self.assertIn('Declared Change Set', text)\n"
        )
        self.assertTrue(_is_spec_wildcard_section_requirement_offender(sample))

    def test_wildcard_alone_is_not_sufficient(self):
        sample = (
            "import glob\n"
            "for path in glob.glob('feature-docs/*/SPEC.md'):\n"
            "    pass  # never requires the new section\n"
        )
        self.assertFalse(_is_spec_wildcard_section_requirement_offender(sample))

    def test_section_requirement_alone_is_not_sufficient(self):
        sample = (
            "text = Path('feature-docs/example/SPEC.md').read_text()\n"
            "self.assertIn('Declared Change Set', text)\n"
        )
        self.assertFalse(_is_spec_wildcard_section_requirement_offender(sample))


if __name__ == "__main__":
    unittest.main()
