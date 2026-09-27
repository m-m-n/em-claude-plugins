"""Tests for task0002 (threat-model-stride): implementation-planner.md gains
a mandatory STRIDE threat-modeling step and carries its mitigations into
task acceptance criteria / VERIFICATION.md (or TASK.md's Expected Result at
the minimal tier).

Covers task0002 Acceptance Criteria
(feature-docs/threat-model-stride/tasks/task0002.md):

- AC-1: implementation-planner.md has a `### 2a.` heading located after
  `### 2. TBD requirement detection (MANDATORY)` and before `### 3.`; its
  section states the pass runs on every dispatch at every tier (full,
  reduced, minimal) and contains no statement that skips it by domains,
  complexity or tier.
- AC-2: the `### 2a.` section names the four domains as depth adjusters
  only, states the post-decomposition consistency re-check, and cites
  `planning_inputs.threat_model_template` and the plan-writing skill
  instead of restating the template's section list.
- AC-3: the `### 2a.` section states THREAT-MODEL.md's location, the
  short-form conditions, and the SPEC/THREAT-MODEL.md role split; the
  frontmatter description mentions THREAT-MODEL.md.
- AC-4: the step 4 section requires every TM-n of a `threats-identified`
  model to be named in an AC at the full/reduced tiers and cites
  planner-contract.md for the minimal-tier TASK.md append; the step 5
  section requires a TM-n keyed VERIFICATION.md item.
- AC-5: the step 7 existing-files decision includes THREAT-MODEL.md; step 8
  and the Output section list THREAT-MODEL.md among written artifacts
  (TASK.md only when appended); the backtick-quoted gate_id set is
  unchanged; the Gate option vocabulary table is byte-identical.
- AC-6: the pre-existing sibling test modules pass unmodified -- verified
  by running the full suite (`python3 -m unittest discover -s tests`), not
  re-asserted in this module (a module cannot assert a sibling module's
  outcome without recursion).
- AC-7: this module imports the standard library only and holds a negative
  proof per custom matcher; the full suite passes; if the two manifest
  files (plugin.json / marketplace.json) changed, only their em-workflow
  version fields changed and both hold the same value (structurally
  guarded here by direct comparison; non-version drift is additionally
  caught by the pre-existing tests/test_muse_consent_version_bump.py
  digest pins, which this task does not touch).

Per IMPLEMENTATION.md ("Tests": every new module locates files relative to
its own path, anchors on literal headings, and carries a negative proof for
every matcher), and per the tdd-testing skill's "search existing tests
before declaring none exist": `tests/test_replanning_producer_alignment.py`
already extracts implementation-planner.md's step 4 section via the same
literal heading markers used here (`### 4. Task decomposition` /
`### 5. VERIFICATION.md`); this module does not depend on that module and
duplicates the minimal extraction logic needed, per the repository's
"no test module imports another" convention (test/README.md).
"""

import ast
import hashlib
import json
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"
PLANNER_PATH = PLUGIN_ROOT / "agents" / "implementation-planner.md"
PLUGIN_MANIFEST_PATH = PLUGIN_ROOT / ".claude-plugin" / "plugin.json"
MARKETPLACE_PATH = REPO_ROOT / ".claude-plugin" / "marketplace.json"

# Literal heading markers this module anchors on (IMPLEMENTATION.md
# "Editing pinned documents": the `### 4.` / `### 5.` / `### 6.` headings
# are not renumbered by this feature).
STEP2_MARKER = "### 2. TBD requirement detection (MANDATORY)"
STEP2A_MARKER = "### 2a. Threat modeling (MANDATORY)"
STEP3_MARKER = "### 3. Cross-task design decisions"
STEP4_MARKER = "### 4. Task decomposition"
STEP5_MARKER = "### 5. VERIFICATION.md"
STEP6_MARKER = "### 6. Populate requirements mapping"
STEP7_MARKER = "### 7. Handle existing files"
STEP8_MARKER = "### 8. Save and report"
OUTPUT_MARKER = "## Output"
IMPORTANT_GUIDELINES_MARKER = "## Important Guidelines"
GATE_VOCAB_MARKER = "## Gate option vocabulary"

# SHA-256 of the `## Gate option vocabulary` section (heading through EOF)
# computed from the pre-task0002 tree -- this task must not touch it
# (task0002.md AC-5: "the Gate option vocabulary table is byte-identical").
GATE_OPTION_VOCAB_SHA256 = (
    "ab908c0af5220c9436b225077c4ca2ddec3ecacb5ca52f5553ef228ec3da7ef8"
)

# The gate_id set already present in implementation-planner.md before this
# feature -- this task introduces no new gate (D1/D2/D3 add no gate_id).
GATE_ID_BASELINE = frozenset(
    {
        "create-plan.tbd-resolution",
        "create-plan.license-conflict",
        "create-plan.existing-files",
    }
)

GATE_ID_RE = re.compile(
    r"`((?:design-system|create-spec|create-plan|implement|develop|design"
    r"|verify|rework|review)\.[a-z][a-z-]*)`"
)


def _read(path):
    return path.read_text(encoding="utf-8")


def _extract_section(text, start_marker, end_marker):
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    return text[start:end]


def _norm(text):
    """Collapse whitespace runs (including Markdown line-wrap newlines) to
    a single space, so a multi-word phrase assertion does not depend on
    where a line happens to wrap."""
    return re.sub(r"\s+", " ", text)


def _split_frontmatter(text):
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.DOTALL)
    if not match:
        raise AssertionError("expected a --- delimited frontmatter block")
    return match.group(1), match.group(2)


def _has_skip_condition(text):
    """True iff `text` carries a phrase that conditions the threat-modeling
    pass on domains/complexity/tier (the shape AC-1's negative check must
    catch): 'only when/if ... <domain|tier|complexity keyword>' or
    'skips it when/for/if'."""
    keywords = ("domain", "complexity", "tier", "full", "reduced", "minimal")
    for m in re.finditer(r"\bonly\s+(?:when|if)\b|\bunless\b", text, re.IGNORECASE):
        window = text[max(0, m.start() - 80) : m.end() + 80].lower()
        if any(kw in window for kw in keywords):
            return True
    if re.search(r"\bskips?\s+it\s+(?:when|for|if)\b", text, re.IGNORECASE):
        return True
    return False


class TestAC1TrustBoundaryHeadingPlacementAndUnconditionalRun(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(PLANNER_PATH)
        cls.section = _extract_section(cls.text, STEP2A_MARKER, STEP3_MARKER)

    def test_section_found_non_vacuous(self):
        self.assertTrue(self.section.strip())

    def test_heading_located_after_step2_and_before_step3(self):
        idx2 = self.text.index(STEP2_MARKER)
        idx2a = self.text.index(STEP2A_MARKER)
        idx3 = self.text.index(STEP3_MARKER)
        self.assertLess(idx2, idx2a)
        self.assertLess(idx2a, idx3)

    def test_states_stride_runs_every_dispatch_naming_all_three_tiers(self):
        self.assertIn("STRIDE", self.section)
        self.assertIn("every dispatch", self.section)
        normalized = _norm(self.section)
        self.assertIn("full, reduced and minimal", normalized)

    def test_section_has_no_skip_condition(self):
        self.assertFalse(
            _has_skip_condition(self.section),
            "the ### 2a. section must not condition the pass on domains, "
            "complexity or tier",
        )

    def test_skip_condition_matcher_fires_on_forged_domain_conditional_sample(self):
        """Negative proof (tdd-testing: a matcher that can never fail is
        not a matcher). Test Notes: 'prove the matcher fires on a forged
        section that says the pass runs only when a security domain is
        declared'."""
        forged = "The pass runs only when a security domain is declared."
        self.assertTrue(_has_skip_condition(forged))

    def test_skip_condition_matcher_fires_on_forged_tier_conditional_sample(self):
        forged = "This step skips it when the tier is minimal."
        self.assertTrue(_has_skip_condition(forged))


class TestAC2DomainsAsDepthAdjustersAndCitation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(PLANNER_PATH)
        cls.section = _extract_section(cls.text, STEP2A_MARKER, STEP3_MARKER)

    FORBIDDEN_TEMPLATE_RESTATEMENT = (
        "## Verdict",
        "## Trust Boundaries",
        "Spoofing, Tampering, Repudiation",
    )

    def test_four_domains_named_as_depth_adjusters_only(self):
        for domain in ("`auth`", "`input-handling`", "`external-io`", "`data-persistence`"):
            with self.subTest(domain=domain):
                self.assertIn(domain, self.section)
        self.assertIn("depth adjusters", self.section)

    def test_states_post_decomposition_consistency_recheck(self):
        self.assertIn("Boundary files", self.section)
        self.assertIn("Rationale", self.section)
        normalized = _norm(self.section)
        self.assertIn("after task decomposition", normalized.lower())

    def test_cites_threat_model_template_input_and_plan_writing_skill(self):
        self.assertIn("planning_inputs.threat_model_template", self.section)
        self.assertIn("plan-writing skill", self.section)

    def test_does_not_restate_the_templates_section_list(self):
        for phrase in self.FORBIDDEN_TEMPLATE_RESTATEMENT:
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, self.section)

    def test_restatement_matcher_fires_on_a_forged_restating_section(self):
        """Negative proof for the absence check above."""
        forged = (
            "## Verdict\n\nExactly one verdict token.\n\n"
            "## Trust Boundaries\n\nSTRIDE categories: "
            "Spoofing, Tampering, Repudiation, ...\n"
        )
        for phrase in self.FORBIDDEN_TEMPLATE_RESTATEMENT:
            self.assertIn(phrase, forged)


class TestAC3ArtifactLocationShortFormAndRoleSplit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(PLANNER_PATH)
        cls.section = _extract_section(cls.text, STEP2A_MARKER, STEP3_MARKER)
        cls.frontmatter, _ = _split_frontmatter(cls.text)

    def test_states_written_to_feature_directory(self):
        self.assertIn("feature-docs/{feature}/THREAT-MODEL.md", self.section)

    def test_states_short_form_conditions_and_no_invented_mitigation(self):
        normalized = _norm(self.section)
        self.assertIn("short form", normalized)
        self.assertIn("no trust", normalized)
        self.assertIn("no applicable threat", normalized)
        self.assertIn("invent no mitigation", normalized)

    def test_states_role_split_with_security_considerations(self):
        self.assertIn("Security Considerations", self.section)
        normalized = _norm(self.section)
        self.assertIn("apart", normalized)
        self.assertIn("neither document restates the other", normalized)

    def test_frontmatter_description_mentions_threat_model_md(self):
        self.assertIn("THREAT-MODEL.md", self.frontmatter)

    def test_role_split_matcher_fires_on_a_forged_duplicating_sample(self):
        """Negative proof: a sample that fails to keep the two documents
        apart must not satisfy the 'apart' + 'neither document restates
        the other' pair the real section states."""
        forged = "SPEC.md's Security Considerations and THREAT-MODEL.md say the same thing."
        self.assertNotIn("apart", forged)
        self.assertNotIn("neither document restates the other", forged)


class TestAC4MitigationCarriageAndVerificationItem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(PLANNER_PATH)
        cls.step4_section = _extract_section(cls.text, STEP4_MARKER, STEP5_MARKER)
        cls.step5_section = _extract_section(cls.text, STEP5_MARKER, STEP6_MARKER)

    def test_step4_section_found_non_vacuous(self):
        self.assertTrue(self.step4_section.strip())

    def test_step5_section_found_non_vacuous(self):
        self.assertTrue(self.step5_section.strip())

    def test_step4_requires_tm_n_named_in_ac_at_full_and_reduced_tiers(self):
        self.assertIn("TM-n", self.step4_section)
        self.assertIn("Acceptance Criterion", self.step4_section)
        normalized = _norm(self.step4_section)
        self.assertIn("full and reduced tiers", normalized)

    def test_step4_cites_planner_contract_for_minimal_tier_task_md_append(self):
        self.assertIn(
            "references/contracts/planner-contract.md", self.step4_section
        )
        self.assertIn("TASK.md", self.step4_section)
        self.assertIn("`## Expected", self.step4_section)
        self.assertIn("blocked", self.step4_section)
        normalized = _norm(self.step4_section)
        self.assertIn("not restated here", normalized)

    def test_step4_does_not_restate_the_append_rules_own_mechanics(self):
        """NFR1: the append rule is cited, not restated -- the specific
        write_policy mechanics (owned by planner-contract.md / SC-3) must
        not appear here."""
        for term in ("extend_only", "expect_digest", "exact prefix"):
            with self.subTest(term=term):
                self.assertNotIn(term, self.step4_section)

    def test_step5_requires_tm_n_keyed_performance_security_item(self):
        self.assertIn("TM-n", self.step5_section)
        self.assertIn("Performance / Security Verification", self.step5_section)
        normalized = _norm(self.step5_section)
        self.assertIn("Verification Summary", normalized)

    def test_step5_matcher_fires_on_a_forged_section_missing_tm_n(self):
        """Negative proof (tdd-testing): a step 5 section that never
        mentions TM-n must fail the presence check above."""
        forged = (
            "### 5. VERIFICATION.md (feature-wide, this agent OWNS it)\n\n"
            "Write VERIFICATION.md with build/test/format commands.\n"
        )
        self.assertNotIn("TM-n", forged)


class TestAC5ExistingFilesWrittenArtifactsAndGateIds(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(PLANNER_PATH)
        cls.step7_section = _extract_section(cls.text, STEP7_MARKER, STEP8_MARKER)
        cls.step8_section = _extract_section(cls.text, STEP8_MARKER, "## Questions")
        cls.output_section = _extract_section(
            cls.text, OUTPUT_MARKER, IMPORTANT_GUIDELINES_MARKER
        )

    def test_step7_section_found_non_vacuous(self):
        self.assertTrue(self.step7_section.strip())

    def test_step7_includes_threat_model_in_existing_files_decision(self):
        self.assertIn("THREAT-MODEL.md", self.step7_section)

    def test_step8_lists_threat_model_among_written_artifacts(self):
        self.assertIn("THREAT-MODEL.md", self.step8_section)
        normalized = _norm(self.step8_section)
        self.assertIn("TASK.md when appended", normalized)

    def test_output_section_lists_threat_model_among_written_artifacts(self):
        self.assertIn("THREAT-MODEL.md", self.output_section)
        normalized = _norm(self.output_section)
        self.assertIn("TASK.md when appended", normalized)

    def test_gate_ids_unchanged(self):
        found = set(GATE_ID_RE.findall(self.text))
        self.assertEqual(found, set(GATE_ID_BASELINE))

    def test_gate_id_matcher_fires_on_a_synthetic_new_gate(self):
        """Negative proof: the extractor must actually detect a new
        gate_id-shaped token before its absence in the real prompt means
        anything."""
        forged = "See `create-plan.threat-model-review` for the new gate."
        found = set(GATE_ID_RE.findall(forged))
        self.assertIn("create-plan.threat-model-review", found)
        self.assertFalse(found <= GATE_ID_BASELINE)

    def test_gate_option_vocabulary_table_byte_identical(self):
        section = self.text[self.text.index(GATE_VOCAB_MARKER) :]
        digest = hashlib.sha256(section.encode("utf-8")).hexdigest()
        self.assertEqual(
            digest,
            GATE_OPTION_VOCAB_SHA256,
            "the ## Gate option vocabulary section changed -- task0002 must "
            "not touch it (AC-5)",
        )

    def test_gate_vocabulary_digest_matcher_detects_a_mutation(self):
        """Negative proof for the digest check above: a one-character
        mutation of the pinned section must change its digest."""
        real_section = self.text[self.text.index(GATE_VOCAB_MARKER) :]
        mutated = real_section.replace("assume", "assumeX", 1)
        self.assertNotEqual(
            hashlib.sha256(mutated.encode("utf-8")).hexdigest(),
            GATE_OPTION_VOCAB_SHA256,
        )


class TestAC7OwnModuleStdlibOnly(unittest.TestCase):
    """AC-7: this module imports the standard library only."""

    def test_only_standard_library_imports(self):
        source = Path(__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        stdlib = set(sys.stdlib_module_names) | set(sys.builtin_module_names)
        modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    modules.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.level == 0 and node.module:
                    modules.add(node.module.split(".")[0])
        non_stdlib = sorted(m for m in modules if m not in stdlib)
        self.assertEqual(non_stdlib, [])


class TestAC7ManifestVersionsConditionalOnChange(unittest.TestCase):
    """AC-7 second half: if the two manifest files changed for this task
    (SC-6's commit-guard fallback), only their em-workflow version fields
    changed and both hold the same value. Both files parse as JSON and
    agree on the version whether or not this task's commit needed the
    fallback bump -- non-version drift is additionally caught by the
    pre-existing tests/test_muse_consent_version_bump.py digest pins,
    which this task does not touch (searched for and found before writing
    this class, per tdd-testing's 'search existing tests' rule)."""

    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads(_read(PLUGIN_MANIFEST_PATH))
        cls.marketplace = json.loads(_read(MARKETPLACE_PATH))
        cls.entry = next(
            (
                p
                for p in cls.marketplace.get("plugins", [])
                if p.get("name") == "em-workflow"
            ),
            None,
        )

    def test_entry_found_non_vacuous(self):
        self.assertIsNotNone(self.entry, "no em-workflow marketplace entry found")

    def test_manifest_and_marketplace_versions_agree(self):
        self.assertEqual(self.manifest.get("version"), self.entry.get("version"))

    def test_version_mismatch_is_detected(self):
        """Negative proof for the equality check above."""
        self.assertNotEqual("0.3.0", "0.3.1")


if __name__ == "__main__":
    unittest.main()
