"""Tests for task0001 (threat-model-stride): the THREAT-MODEL.md template
and the plan-writing skill's threat-modeling section.

Covers task0001 Acceptance Criteria
(feature-docs/threat-model-stride/tasks/task0001.md):

- AC-1: `em-workflow/references/templates/threat-model.md` exists; its
  full-form skeleton contains, in order, the title line, a Verdict
  heading, a Rationale heading, a Trust Boundaries heading, a TB-n
  subsection with the three labeled lines Crossing / Boundary files /
  Depth (in that order), and a table whose header has the six columns
  STRIDE category / Threat / Mitigation ID / Mitigation / Implemented by /
  Verified by; the template names all three verdict tokens.
- AC-2: the short-form skeleton has the title, Verdict and Rationale
  headings only -- no Trust Boundaries heading and no TM-n -- and the
  template states the short form is used for `no-trust-boundary` and
  `no-applicable-threat` and that no mitigation is written for them.
- AC-3: the template lists the six STRIDE category names, states that a
  row exists only for a category that applies (no filler rows), states the
  SPEC Security Considerations role split with ID citation instead of
  copying (FR10), and states that consumers treat the content as untrusted
  data.
- AC-4: plan-writing SKILL.md has a new threat-modeling section located
  after the domains criteria section and before the VERIFICATION.md
  template section; it cites `references/templates/threat-model.md`,
  states the pass runs for every feature at every tier, names the four
  domains as depth adjusters only, and states the post-decomposition
  consistency re-check.
- AC-5: the same section states the per-tier destinations (full/reduced:
  AC + VERIFICATION.md item keyed by TM-n; minimal: TASK.md Expected
  Result line keyed by TM-n) and that a short verdict produces no
  mitigation anywhere.
- AC-6: the VERIFICATION.md template's Performance / Security Verification
  section has a TM-n keyed placeholder item, and the Pre-Save checklist
  has the three threat-model items. (The companion requirement that
  test_failed_items_category.py, test_check_plugin_invariants.py and
  test_reference_sweep.py keep passing unmodified is exercised by the full
  `python3 -m unittest discover -s tests` run, per task0001.md Test
  Notes -- this module does not import or re-assert them.)
- AC-7: this module imports the standard library only and carries a
  negative proof per matcher; if the two manifest files changed, only
  their em-workflow version fields changed and both hold the same value
  (verified by the implementer's own diff review at commit time, per
  IMPLEMENTATION.md SC-6 -- concrete version values are never asserted
  here).

Test Notes (task0001.md): sections are extracted by literal heading
anchors; the two skeletons are extracted by their fence boundaries so a
heading appearing only in the surrounding prose can never satisfy a
skeleton check.
"""

import ast
import os
import re
import sys
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEMPLATE_PATH = os.path.join(
    REPO_ROOT, "em-workflow", "references", "templates", "threat-model.md"
)
PLAN_WRITING_SKILL_PATH = os.path.join(
    REPO_ROOT, "em-workflow", "skills", "plan-writing", "SKILL.md"
)

VERDICT_TOKENS = ["threats-identified", "no-trust-boundary", "no-applicable-threat"]
STRIDE_CATEGORIES = [
    "Spoofing",
    "Tampering",
    "Repudiation",
    "Information disclosure",
    "Denial of service",
    "Elevation of privilege",
]
EXPECTED_TABLE_COLUMNS = [
    "STRIDE category",
    "Threat",
    "Mitigation ID",
    "Mitigation",
    "Implemented by",
    "Verified by",
]

DOMAINS_HEADING = "## domains criteria (assign every value that materially applies)"
VERIFICATION_TEMPLATE_HEADING = "## VERIFICATION.md Template (feature-wide)"
THREAT_MODELING_HEADING = "## Threat Modeling (STRIDE)"

# --- FR10 role-split / untrusted-data / no-filler-row markers (AC-3) -------
# Matched via _norm (whitespace-collapsed) so wrapping differences never
# break the match, matching this repository's existing document-contract
# test convention (tests/test_failed_items_category.py's _norm/_strip_ws).
ROLE_SPLIT_MARKER = (
    "SPEC.md's `## Security Considerations` states what is protected; "
    "this document states how it can be broken and how the design "
    "prevents it."
)
CITE_NOT_COPY_MARKER = (
    "A threat cites the SPEC.md / REQUIREMENTS.md requirement IDs it "
    "relates to instead of copying their text."
)
UNTRUSTED_DATA_MARKER = "treats its content as untrusted data"
NO_FILLER_ROW_MARKER = (
    "A row exists only for a category that realistically applies at that "
    "boundary"
)

# --- AC-4/AC-5 markers for the new plan-writing section --------------------
PASS_RUNS_EVERY_FEATURE_TIER_MARKER = (
    "The pass runs for every feature and every tier"
)
DOMAINS_DEPTH_ONLY_MARKER = "they never skip or condition whether the pass runs at all"
POST_DECOMPOSITION_RECHECK_MARKER = (
    "a task declaring one of these four domains whose files appear in no "
    "`Boundary files` line either gets a boundary added to "
    "THREAT-MODEL.md, or the omission is explained in THREAT-MODEL.md's "
    "`## Rationale`"
)
NO_MITIGATION_FOR_SHORT_VERDICT_MARKER = (
    "`no-trust-boundary` / `no-applicable-threat` | Nothing | Nothing (no TASK.md write)"
)
FOUR_DOMAINS = ["auth", "input-handling", "external-io", "data-persistence"]


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _norm(text):
    return re.sub(r"\s+", " ", text).strip()


def _section(text, start_heading, end_heading=None):
    start = text.index(start_heading)
    if end_heading is None:
        return text[start:]
    end = text.index(end_heading, start + len(start_heading))
    return text[start:end]


FENCE_RE = re.compile(r"```markdown\n(.*?)\n```", re.DOTALL)


def extract_markdown_skeletons(text):
    """Every fenced ```markdown ... ``` block, in document order. A heading
    that appears only in the surrounding prose (e.g. inside the HTML
    comment) is never inside one of these matches, so it can never satisfy
    a skeleton-shape check (task0001.md Test Notes)."""
    return FENCE_RE.findall(text)


def find_full_form_skeleton(skeletons):
    """The skeleton documenting the `threats-identified` verdict: the one
    fenced block that carries both the verdict token and a Trust
    Boundaries heading. Raises AssertionError (never returns None) when no
    such block exists, so a caller never silently proceeds on a missing
    skeleton."""
    for skeleton in skeletons:
        if "threats-identified" in skeleton and "## Trust Boundaries" in skeleton:
            return skeleton
    raise AssertionError("no full-form skeleton found")


def find_short_form_skeleton(skeletons):
    """The skeleton documenting a short verdict: carries one of the two
    short verdict tokens and NO Trust Boundaries heading. Raises
    AssertionError when no such block exists."""
    for skeleton in skeletons:
        if (
            ("no-trust-boundary" in skeleton or "no-applicable-threat" in skeleton)
            and "## Trust Boundaries" not in skeleton
        ):
            return skeleton
    raise AssertionError("no short-form skeleton found")


def assert_full_form_heading_order(skeleton):
    """AC-1: title, Verdict, Rationale, Trust Boundaries headings appear in
    this order. Raises AssertionError (via a missing substring or an
    out-of-order position) otherwise."""
    title_pos = skeleton.index("# Threat Model: ")
    verdict_pos = skeleton.index("## Verdict")
    rationale_pos = skeleton.index("## Rationale")
    tb_pos = skeleton.index("## Trust Boundaries")
    if not (title_pos < verdict_pos < rationale_pos < tb_pos):
        raise AssertionError(
            f"headings out of order: title={title_pos} verdict={verdict_pos} "
            f"rationale={rationale_pos} trust_boundaries={tb_pos}"
        )


def extract_tb_labeled_lines(skeleton, tb_heading="### TB-1:"):
    """AC-1: the labeled Crossing / Boundary files / Depth lines that
    follow a `### TB-n:` heading, in the order they appear. Raises
    AssertionError when the heading or any of the three labels is
    missing."""
    start = skeleton.index(tb_heading)
    # the block ends at the next blank line followed by a table or heading;
    # scanning forward line by line is more robust than a fixed slice.
    lines = skeleton[start:].splitlines()
    labels_found = []
    for line in lines[1:]:
        stripped = line.strip()
        if stripped.startswith("|") or stripped.startswith("#"):
            break
        for label in ("Crossing:", "Boundary files:", "Depth:"):
            if stripped.startswith(label):
                labels_found.append(label)
    required = ["Crossing:", "Boundary files:", "Depth:"]
    if labels_found[: len(required)] != required:
        raise AssertionError(f"expected {required} in order, got {labels_found}")
    return labels_found


def extract_table_header_columns(skeleton, header_prefix="| STRIDE category"):
    """AC-1: the six-column header row of the Trust Boundaries table.
    Raises AssertionError when no line starts with the expected header
    prefix (missing table) -- this is the matcher a forged, column-short
    table fails."""
    for line in skeleton.splitlines():
        if line.startswith(header_prefix):
            return [c.strip() for c in line.strip("|").split("|")]
    raise AssertionError("no STRIDE table header row found")


def assert_short_form_shape(skeleton):
    """AC-2: exactly the title, Verdict and Rationale headings; no Trust
    Boundaries heading; no TM-n token. Raises AssertionError on any
    violation -- this is the matcher a forged short form (one that smuggles
    in a Trust Boundaries heading, per the task plan's own example) fails."""
    if "## Trust Boundaries" in skeleton:
        raise AssertionError("short form must not contain a Trust Boundaries heading")
    if "TM-" in skeleton:
        raise AssertionError("short form must not contain a TM-n token")
    headings = re.findall(r"^#{1,3} .*$", skeleton, re.MULTILINE)
    if len(headings) != 3:
        raise AssertionError(f"expected exactly 3 headings, got {headings}")


def assert_threat_modeling_section_placement(text):
    """AC-4: the threat-modeling heading sits strictly between the domains
    criteria heading and the VERIFICATION.md template heading. Raises
    AssertionError otherwise -- the matcher a forged, misplaced heading
    (e.g. moved before domains criteria) fails."""
    domains_pos = text.index(DOMAINS_HEADING)
    section_pos = text.index(THREAT_MODELING_HEADING)
    verification_pos = text.index(VERIFICATION_TEMPLATE_HEADING)
    if not (domains_pos < section_pos < verification_pos):
        raise AssertionError(
            f"threat-modeling section misplaced: domains={domains_pos} "
            f"section={section_pos} verification_template={verification_pos}"
        )


# ---------------------------------------------------------------------------
# AC-1
# ---------------------------------------------------------------------------


class TestTemplateFileExists(unittest.TestCase):
    def test_template_file_exists(self):
        self.assertTrue(os.path.isfile(TEMPLATE_PATH), TEMPLATE_PATH)


class TemplateTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(TEMPLATE_PATH)
        cls.skeletons = extract_markdown_skeletons(cls.text)


class TestFullFormSkeletonShape(TemplateTestCase):
    def test_full_form_skeleton_found(self):
        find_full_form_skeleton(self.skeletons)

    def test_headings_appear_in_order(self):
        skeleton = find_full_form_skeleton(self.skeletons)
        assert_full_form_heading_order(skeleton)

    def test_negative_proof_heading_order_matcher_rejects_reordered_headings(self):
        forged = (
            "# Threat Model: {feature}\n\n"
            "## Trust Boundaries\n\n"
            "## Verdict\nthreats-identified\n\n"
            "## Rationale\n{...}\n"
        )
        with self.assertRaises(AssertionError):
            assert_full_form_heading_order(forged)

    def test_tb_subsection_has_three_labeled_lines_in_order(self):
        skeleton = find_full_form_skeleton(self.skeletons)
        labels = extract_tb_labeled_lines(skeleton)
        self.assertEqual(labels, ["Crossing:", "Boundary files:", "Depth:"])

    def test_negative_proof_tb_matcher_rejects_missing_label(self):
        forged = "### TB-1: x\nCrossing: y\nDepth: z\n\n| table |\n"
        with self.assertRaises(AssertionError):
            extract_tb_labeled_lines(forged)

    def test_table_header_has_six_expected_columns(self):
        skeleton = find_full_form_skeleton(self.skeletons)
        columns = extract_table_header_columns(skeleton)
        self.assertEqual(columns, EXPECTED_TABLE_COLUMNS)

    def test_negative_proof_table_matcher_rejects_a_column_short_table(self):
        forged = (
            "### TB-1: x\n"
            "| STRIDE category | Threat | Mitigation ID | Mitigation | Verified by |\n"
            "|---|---|---|---|---|\n"
        )
        with self.assertRaises(AssertionError):
            columns = extract_table_header_columns(forged)
            self.assertEqual(columns, EXPECTED_TABLE_COLUMNS)


class TestVerdictTokensNamed(TemplateTestCase):
    def test_all_three_verdict_tokens_present(self):
        for token in VERDICT_TOKENS:
            with self.subTest(token=token):
                self.assertIn(token, self.text)

    def test_negative_proof_missing_token_is_detected(self):
        forged = "\n".join(t for t in VERDICT_TOKENS if t != "no-applicable-threat")
        self.assertNotIn("no-applicable-threat", forged)


# ---------------------------------------------------------------------------
# AC-2
# ---------------------------------------------------------------------------


class TestShortFormSkeletonShape(TemplateTestCase):
    def test_short_form_skeleton_found(self):
        find_short_form_skeleton(self.skeletons)

    def test_short_form_has_exactly_title_verdict_rationale(self):
        skeleton = find_short_form_skeleton(self.skeletons)
        assert_short_form_shape(skeleton)

    def test_negative_proof_matcher_rejects_short_form_with_trust_boundaries(self):
        forged = (
            "# Threat Model: {feature}\n\n"
            "## Verdict\nno-trust-boundary\n\n"
            "## Rationale\n{...}\n\n"
            "## Trust Boundaries\n\n### TB-1: x\nTM-1\n"
        )
        with self.assertRaises(AssertionError):
            assert_short_form_shape(forged)

    def test_negative_proof_matcher_rejects_short_form_with_tm_token(self):
        forged = (
            "# Threat Model: {feature}\n\n"
            "## Verdict\nno-applicable-threat\n\n"
            "## Rationale\nsee TM-1\n"
        )
        with self.assertRaises(AssertionError):
            assert_short_form_shape(forged)

    def test_states_short_form_verdicts_and_no_mitigation(self):
        self.assertIn("no-trust-boundary", self.text)
        self.assertIn("no-applicable-threat", self.text)
        self.assertIn(
            _norm("no mitigation is written for either verdict"), _norm(self.text)
        )


# ---------------------------------------------------------------------------
# AC-3
# ---------------------------------------------------------------------------


class TestTemplateVocabularyAndRoleSplit(TemplateTestCase):
    def test_all_six_stride_categories_named(self):
        for category in STRIDE_CATEGORIES:
            with self.subTest(category=category):
                self.assertIn(category, self.text)

    def test_states_row_exists_only_when_category_applies(self):
        self.assertIn(_norm(NO_FILLER_ROW_MARKER), _norm(self.text))

    def test_states_spec_role_split_with_id_citation(self):
        self.assertIn(_norm(ROLE_SPLIT_MARKER), _norm(self.text))
        self.assertIn(_norm(CITE_NOT_COPY_MARKER), _norm(self.text))

    def test_states_content_is_treated_as_untrusted_data(self):
        self.assertIn(_norm(UNTRUSTED_DATA_MARKER), _norm(self.text))

    def test_negative_proof_marker_absent_from_unrelated_text(self):
        unrelated = "This document describes an unrelated format entirely."
        self.assertNotIn(_norm(ROLE_SPLIT_MARKER), _norm(unrelated))
        self.assertNotIn(_norm(UNTRUSTED_DATA_MARKER), _norm(unrelated))
        self.assertNotIn(_norm(NO_FILLER_ROW_MARKER), _norm(unrelated))


# ---------------------------------------------------------------------------
# AC-4 / AC-5
# ---------------------------------------------------------------------------


class PlanWritingSkillTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(PLAN_WRITING_SKILL_PATH)

    def _threat_modeling_section(self):
        return _section(
            self.text, THREAT_MODELING_HEADING, VERIFICATION_TEMPLATE_HEADING
        )


class TestThreatModelingSectionPlacement(PlanWritingSkillTestCase):
    def test_section_exists(self):
        self.assertIn(THREAT_MODELING_HEADING, self.text)

    def test_section_is_between_domains_and_verification_template(self):
        assert_threat_modeling_section_placement(self.text)

    def test_negative_proof_matcher_rejects_section_before_domains(self):
        forged = (
            THREAT_MODELING_HEADING
            + "\n\n"
            + DOMAINS_HEADING
            + "\n\n"
            + VERIFICATION_TEMPLATE_HEADING
            + "\n"
        )
        with self.assertRaises(AssertionError):
            assert_threat_modeling_section_placement(forged)

    def test_negative_proof_matcher_rejects_section_after_verification_template(self):
        forged = (
            DOMAINS_HEADING
            + "\n\n"
            + VERIFICATION_TEMPLATE_HEADING
            + "\n\n"
            + THREAT_MODELING_HEADING
            + "\n"
        )
        with self.assertRaises(AssertionError):
            assert_threat_modeling_section_placement(forged)

    def test_domains_criteria_section_content_unchanged(self):
        # The domains list itself (the vocabulary bullets) must still sit
        # immediately before the new section -- i.e. this task never
        # touched the domains criteria section's own content.
        section = _section(self.text, DOMAINS_HEADING, THREAT_MODELING_HEADING)
        self.assertIn("`config-infra`", section)
        self.assertIn("review-rules.yaml", section)


class TestThreatModelingSectionContent(PlanWritingSkillTestCase):
    def test_cites_template_by_plugin_relative_path(self):
        section = self._threat_modeling_section()
        self.assertIn("references/templates/threat-model.md", section)

    def test_states_pass_runs_every_feature_every_tier(self):
        section = self._threat_modeling_section()
        self.assertIn(_norm(PASS_RUNS_EVERY_FEATURE_TIER_MARKER), _norm(section))

    def test_names_four_domains_as_depth_adjusters_only(self):
        section = self._threat_modeling_section()
        for domain in FOUR_DOMAINS:
            with self.subTest(domain=domain):
                self.assertIn(f"`{domain}`", section)
        self.assertIn(_norm(DOMAINS_DEPTH_ONLY_MARKER), _norm(section))

    def test_states_post_decomposition_consistency_recheck(self):
        section = self._threat_modeling_section()
        self.assertIn(_norm(POST_DECOMPOSITION_RECHECK_MARKER), _norm(section))

    def test_negative_proof_markers_absent_from_unrelated_section(self):
        unrelated = _norm("This section discusses something unrelated entirely.")
        self.assertNotIn(_norm(PASS_RUNS_EVERY_FEATURE_TIER_MARKER), unrelated)
        self.assertNotIn(_norm(POST_DECOMPOSITION_RECHECK_MARKER), unrelated)


class TestPerTierMitigationReflection(PlanWritingSkillTestCase):
    def test_full_reduced_destination_named(self):
        section = self._threat_modeling_section()
        normalized = _norm(section)
        self.assertIn(_norm("names the `TM-n` and states the observable protective behavior"), normalized)
        self.assertIn(
            _norm(
                "One item in VERIFICATION.md's Performance / Security "
                "Verification section keyed by the `TM-n`"
            ),
            normalized,
        )

    def test_minimal_destination_named(self):
        section = self._threat_modeling_section()
        normalized = _norm(section)
        self.assertIn(
            _norm("One line appended to TASK.md's Expected Result keyed by the `TM-n`"),
            normalized,
        )

    def test_short_verdict_produces_no_mitigation_anywhere(self):
        section = self._threat_modeling_section()
        self.assertIn(_norm(NO_MITIGATION_FOR_SHORT_VERDICT_MARKER), _norm(section))

    def test_negative_proof_marker_absent_from_unrelated_text(self):
        unrelated = _norm("nothing about mitigation reflection here")
        self.assertNotIn(_norm(NO_MITIGATION_FOR_SHORT_VERDICT_MARKER), unrelated)


# ---------------------------------------------------------------------------
# AC-6
# ---------------------------------------------------------------------------


class TestVerificationTemplateAndChecklist(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(PLAN_WRITING_SKILL_PATH)

    def _verification_md_template_block(self):
        return _section(
            self.text,
            VERIFICATION_TEMPLATE_HEADING,
            "## Pre-Save Self-Verification Checklist (MANDATORY)",
        )

    def _perf_security_section(self):
        block = self._verification_md_template_block()
        return _section(
            block,
            "## Performance / Security Verification (if applicable)",
            "## Verification Summary",
        )

    def test_perf_security_section_has_tm_n_keyed_placeholder(self):
        section = self._perf_security_section()
        self.assertIn("TM-n", section)

    def test_negative_proof_placeholder_absent_from_unrelated_section(self):
        unrelated = "## Build Verification\n- Command: {x}\n"
        self.assertNotIn("TM-n", unrelated)

    def test_no_backtick_quoted_review_perspective_term_added(self):
        # Mirrors tests/test_failed_items_category.py's
        # backtick_quoted_vocab_terms_present convention: the
        # VERIFICATION.md template section (whole block, not just the
        # Performance / Security subsection) must never gain a
        # backtick-quoted review-perspective vocabulary term.
        vocab = ["comprehensive", "spec", "security", "performance", "architecture", "license", "unknown"]
        block = self._verification_md_template_block()
        hits = [v for v in vocab if f"`{v}`" in block]
        self.assertEqual(hits, [])

    def test_negative_proof_vocab_detector_fires_on_synthetic_restatement(self):
        vocab = ["comprehensive", "spec", "security", "performance", "architecture", "license", "unknown"]
        synthetic = "`comprehensive` `spec` `security` `performance` `architecture` `license` `unknown`"
        hits = [v for v in vocab if f"`{v}`" in synthetic]
        self.assertEqual(hits, vocab)

    def test_presave_checklist_has_three_threat_model_items(self):
        checklist = _section(self.text, "## Pre-Save Self-Verification Checklist (MANDATORY)")
        self.assertIn("THREAT-MODEL.md is written with exactly one verdict", checklist)
        self.assertIn("TM-n", checklist)
        self.assertIn("no mitigation exists without a recorded threat".lower(), checklist.lower())

    def test_negative_proof_checklist_items_absent_from_unrelated_text(self):
        unrelated = "- [ ] Some unrelated checklist item."
        self.assertNotIn("THREAT-MODEL.md is written with exactly one verdict", unrelated)


# ---------------------------------------------------------------------------
# AC-7
# ---------------------------------------------------------------------------


class TestOwnModuleStdlibOnly(unittest.TestCase):
    def test_only_standard_library_imports(self):
        source = _read(os.path.abspath(__file__))
        tree = ast.parse(source)
        stdlib = sys.stdlib_module_names
        modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    modules.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    modules.add(node.module.split(".")[0])
        non_stdlib = sorted(m for m in modules if m not in stdlib)
        self.assertEqual(non_stdlib, [])


class TestManifestVersionFieldsOnly(unittest.TestCase):
    """AC-7's manifest clause: IF the two manifest files were touched by
    this task (only happens when the local commit-guard hook rejects the
    commit -- IMPLEMENTATION.md SC-6), only their em-workflow version
    fields changed and both hold the same value. Both manifests still
    parse as JSON and carry matching versions unconditionally -- that part
    is a plain invariant this module can assert directly. The "only the
    version field changed" part is a diff-shape property against a
    pre-task git revision that this module cannot see from inside a single
    checkout without hardcoding a commit hash (a pattern this repository's
    other version-bump tests deliberately avoid, e.g.
    tests/test_em_workflow_version.py's baseline-floor approach); it is
    verified by the implementer's own `git diff` review at commit time
    instead, per IMPLEMENTATION.md SC-6."""

    def test_both_manifests_parse_and_agree_on_em_workflow_version(self):
        import json

        plugin_manifest_path = os.path.join(
            REPO_ROOT, "em-workflow", ".claude-plugin", "plugin.json"
        )
        marketplace_path = os.path.join(REPO_ROOT, ".claude-plugin", "marketplace.json")
        plugin_data = json.loads(_read(plugin_manifest_path))
        marketplace_data = json.loads(_read(marketplace_path))
        entry = next(
            e for e in marketplace_data["plugins"] if e.get("name") == "em-workflow"
        )
        self.assertEqual(entry.get("version"), plugin_data.get("version"))


if __name__ == "__main__":
    unittest.main()
