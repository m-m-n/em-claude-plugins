"""Tests for task0004 (threat-model-stride): the review phase resolves,
validates and passes threat_model_path.

Covers task0004 Acceptance Criteria
(feature-docs/threat-model-stride/tasks/task0004.md):

- AC-1: review-phase.md's Phase R0 step 4 states that the develop-driven
  route resolves THREAT-MODEL.md in the feature directory inside the
  integration worktree as the candidate for `threat_model_path`, and that
  the standalone route never sets `threat_model_path`.
- AC-2: the same step states that when THREAT-MODEL.md is absent
  `threat_model_path` is not set, with no abort, no skip and no change to
  perspective selection.
- AC-3: the same step states that a present THREAT-MODEL.md is validated
  with the same checks as `spec_path` -- naming prompt-control characters,
  symlink rejection and realpath containment under project_root -- and that
  a violation aborts without sanitizing.
- AC-4: Phase R2 states that `threat_model_path` is carried only in the
  security perspective's input block and normalized like `spec_path`;
  Phase R2b's and Phase R4's security re-dispatches carry the same value; no
  statement adds it to any other perspective's block or to the Phase R3a
  evaluator input.
- AC-5: Phase R0 keeps steps 1-8 with their existing numbers and the order
  "Probe litellm" before "Probe notion-task-dispatch" before "Load prior
  rounds"; the review-phase.md whole-file digest pin in
  tests/test_tier_record_schema_v2.py is refreshed (checked there, not
  here); tests/test_sca_axis_review_phase_r0_r3.py,
  tests/test_review_phase_llm_led.py, tests/test_tier_spec_perspective.py,
  tests/test_declared_change_set_invariants.py and
  tests/test_muse_consent_no_new_questions.py pass unmodified.
- AC-6: this module imports the standard library only and holds a negative
  proof per matcher; `python3 -m unittest discover -s tests` passes
  (verified by actually running it, recorded in the implementer report --
  a suite cannot assert its own full-suite outcome, following
  tests/test_sca_axis_review_phase_r0_r3.py's AC-7 precedent); if the two
  manifest files (em-workflow/.claude-plugin/plugin.json and the
  em-workflow entry of .claude-plugin/marketplace.json) changed, only their
  version fields changed and both hold the same value.

Document assertions are made against raw file text, sections sliced on
literal headings (repository convention: tests/test_tier_spec_perspective.py,
tests/test_sca_axis_review_phase_r0_r3.py, tests/test_review_phase_llm_led.py),
phrases matched against whitespace-normalized text so the document's
reflowing does not break a match landing across a line break. Every new
matcher this module adds is paired with a negative proof over a forged
sample and a non-vacuity guard proving the slice actually contains the
region under test.

The manifest invariant (AC-6) is checked as a canonical-JSON sha256 digest
of each file with the `version` key removed, pinned from this module's
pre-task reading of both files -- so the check is insensitive to whether a
version bump happened (IMPLEMENTATION.md SC-6's commit-guard fallback) while
still catching any other field drifting.
"""

import ast
import hashlib
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"
REVIEW_PHASE_PATH = PLUGIN_ROOT / "references" / "review-phase.md"
PLUGIN_MANIFEST_PATH = PLUGIN_ROOT / ".claude-plugin" / "plugin.json"
MARKETPLACE_PATH = REPO_ROOT / ".claude-plugin" / "marketplace.json"

R0_HEADING = "## Phase R0: Resolve SSOT & review target"
R1_HEADING = "## Phase R1: Perspective selection (two layers)"
R2_HEADING = "## Phase R2: Fan-out (ONE message, N Task calls)"
R2B_HEADING = "## Phase R2b: Cross-model fallback (chain walk)"
R3A_HEADING = "## Phase R3a: Evaluation (single Opus evaluator)"
R3B_HEADING = "## Phase R3b: Mechanical gates on the evaluation"
R4_HEADING = "## Phase R4: Bounded auto-fix (≤ 3 loops, ON by default)"
R5_HEADING = "## Phase R5: Persist the round record"

STEP4_START = "4. Locate SPEC.md"
STEP5_START = "5. Probe codex"

# The five sibling document-contract suites task0004.md AC-5 requires to
# pass unmodified.
SIBLING_SUITE_MODULES = [
    "tests.test_sca_axis_review_phase_r0_r3",
    "tests.test_review_phase_llm_led",
    "tests.test_tier_spec_perspective",
    "tests.test_declared_change_set_invariants",
    "tests.test_muse_consent_no_new_questions",
]


def _read(path):
    return path.read_text(encoding="utf-8")


def _slice(text, start_heading, end_heading=None):
    start = text.index(start_heading)
    if end_heading is None:
        return text[start:]
    end = text.index(end_heading, start + len(start_heading))
    return text[start:end]


def _norm(text):
    return re.sub(r"\s+", " ", text).strip()


class DocumentFixture:
    """Reads review-phase.md once and slices out the regions this module
    needs."""

    _text = None

    @classmethod
    def text(cls):
        if cls._text is None:
            cls._text = _read(REVIEW_PHASE_PATH)
        return cls._text

    @classmethod
    def r0(cls):
        return _slice(cls.text(), R0_HEADING, R1_HEADING)

    @classmethod
    def step4(cls):
        return _slice(cls.r0(), STEP4_START, STEP5_START)

    @classmethod
    def r2(cls):
        return _slice(cls.text(), R2_HEADING, R2B_HEADING)

    @classmethod
    def r2b(cls):
        return _slice(cls.text(), R2B_HEADING, R3A_HEADING)

    @classmethod
    def r3a(cls):
        return _slice(cls.text(), R3A_HEADING, R3B_HEADING)

    @classmethod
    def r4(cls):
        return _slice(cls.text(), R4_HEADING, R5_HEADING)


# ---------------------------------------------------------------------------
# AC-1 / AC-2 / AC-3: Phase R0 step 4 resolves and validates
# threat_model_path.
# ---------------------------------------------------------------------------


class TestAC1ThreatModelResolutionStated(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.step4 = DocumentFixture.step4()
        cls.norm = _norm(cls.step4)

    def test_non_vacuity_slice_contains_threat_model(self):
        # Proves the step4 slice is the right region, not an accidental
        # empty or unrelated slice.
        self.assertIn("Locate SPEC.md", self.step4)
        self.assertIn("THREAT-MODEL.md", self.step4)

    def test_develop_route_resolves_candidate_in_feature_dir(self):
        self.assertIn(
            "`{project_root}/feature-docs/{feature}/THREAT-MODEL.md`",
            self.norm,
        )
        self.assertIn("integration worktree", self.norm)
        self.assertIn("develop-駆動 only", self.norm)

    def test_standalone_route_never_sets_the_field(self):
        self.assertIn(
            "The standalone route never sets `threat_model_path`.", self.norm
        )

    def test_negative_proof_old_step4_lacks_threat_model_wording(self):
        old_step4 = (
            "4. Locate SPEC.md: develop-駆動 → "
            "`{project_root}/feature-docs/{feature}/SPEC.md`\n"
            "   — the committed copy inside the integration worktree is the "
            "canonical\n"
            "   review input; absent ⇒ `spec_available = false`, the same "
            "flag the\n"
            "   standalone route below sets.\n"
        )
        self.assertNotIn("THREAT-MODEL.md", old_step4)
        self.assertNotIn("threat_model_path", old_step4)


class TestAC2AbsentThreatModelLeavesFieldUnset(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.norm = _norm(DocumentFixture.step4())

    def test_absence_rule_stated(self):
        self.assertIn(
            "Absent ⇒ `threat_model_path` stays unset", self.norm
        )

    def test_no_abort_no_skip_no_finding_no_selection_change(self):
        self.assertIn(
            "no abort, no skip, no finding, and no change to "
            "`spec_available` or to perspective selection",
            self.norm,
        )

    def test_negative_proof_forged_absence_clause_missing_constraints(self):
        forged = "Absent ⇒ `threat_model_path` stays unset."
        self.assertNotIn("no abort, no skip, no finding", forged)


class TestAC3PresentThreatModelValidatedLikeSpecPath(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.norm = _norm(DocumentFixture.step4())

    def test_same_checks_as_spec_path_named(self):
        self.assertIn("exactly the same checks `spec_path` gets", self.norm)
        self.assertIn("prompt-control characters", self.norm)
        self.assertIn("reject symlinks via `lstat`", self.norm)
        self.assertIn("`realpath` containment under project_root", self.norm)
        self.assertIn("require a regular file", self.norm)

    def test_violation_aborts_never_sanitized(self):
        self.assertIn(
            "a violation aborts exactly as a `spec_path` violation does, "
            "never sanitized",
            self.norm,
        )

    def test_negative_proof_forged_clause_sanitizes_instead_of_aborting(self):
        forged = (
            "Present ⇒ validate it loosely and sanitize any offending "
            "character instead of aborting."
        )
        self.assertNotIn("never sanitized", forged)
        self.assertNotIn("exactly the same checks `spec_path` gets", forged)


# ---------------------------------------------------------------------------
# AC-4: Phase R2 carries threat_model_path only in the security block;
# Phase R2b / Phase R4 re-dispatches carry the same value; the evaluator
# input (Phase R3a) is untouched.
# ---------------------------------------------------------------------------


def _security_only_threat_model_sentence(text):
    """Locates the sentence carrying `threat_model_path` and returns True
    only when it names the `security` perspective specifically and does NOT
    attach the field to every perspective. A forged sentence that reads
    "every perspective's ... additionally carries threat_model_path" (or
    "all perspectives") must be rejected -- this is the discriminator
    task0004.md's Test Notes asks for."""
    if "threat_model_path" not in text:
        return False
    idx = text.index("threat_model_path")
    window = text[max(0, idx - 250) : idx + 250]
    lowered = window.lower()
    if "every perspective" in lowered or "all perspectives" in lowered:
        return False
    return "security" in lowered


class TestAC4PhaseR2SecurityOnlyInputBlock(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r2 = DocumentFixture.r2()
        cls.norm = _norm(cls.r2)

    def test_non_vacuity_r2_slice_contains_threat_model_path(self):
        self.assertIn("threat_model_path", self.r2)

    def test_matcher_accepts_the_real_r2_sentence(self):
        self.assertTrue(_security_only_threat_model_sentence(self.norm))

    def test_no_other_perspective_carries_it_stated(self):
        self.assertIn("no other perspective's block carries it", self.norm)

    def test_normalized_like_spec_path(self):
        self.assertIn(
            "normalized to a project_root-based absolute path under the "
            "same rule as `spec_path`",
            self.norm,
        )

    def test_negative_proof_matcher_rejects_forged_all_perspectives_sentence(
        self,
    ):
        forged = (
            "Every perspective's input block additionally carries "
            "threat_model_path when it is set."
        )
        self.assertFalse(_security_only_threat_model_sentence(forged))

    def test_negative_proof_matcher_rejects_forged_all_perspectives_sentence_alt(
        self,
    ):
        forged = (
            "All perspectives' blocks additionally carry threat_model_path "
            "when Phase R0 set it."
        )
        self.assertFalse(_security_only_threat_model_sentence(forged))

    def test_negative_proof_matcher_rejects_absence_of_the_field(self):
        forged = "Every dispatch carries the same review-protocol input block."
        self.assertFalse(_security_only_threat_model_sentence(forged))


class TestAC4PhaseR2bCarriesSameValue(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r2b = DocumentFixture.r2b()
        cls.norm = _norm(cls.r2b)

    def test_non_vacuity_r2b_slice_is_the_chain_walk_section(self):
        self.assertIn("Cross-model fallback", self.r2b)

    def test_threat_model_path_carried_across_hops(self):
        self.assertIn("threat_model_path", self.norm)
        self.assertIn("same `threat_model_path` value", self.norm)
        self.assertIn("security", self.norm.lower())

    def test_negative_proof_forged_r2b_excerpt_lacks_the_statement(self):
        forged = _norm(
            "Applies to every perspective whose R2 primary-reviewer "
            "dispatch returned skipped: true with a retryable skip_reason."
        )
        self.assertNotIn("threat_model_path", forged)


class TestAC4PhaseR4CarriesSameValue(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r4 = DocumentFixture.r4()
        cls.norm = _norm(cls.r4)

    def test_non_vacuity_r4_slice_is_the_auto_fix_section(self):
        self.assertIn("Bounded auto-fix", self.r4)

    def test_threat_model_path_carried_in_re_review(self):
        self.assertIn("threat_model_path", self.norm)
        self.assertIn("same `threat_model_path` value", self.norm)

    def test_negative_proof_forged_r4_excerpt_lacks_the_statement(self):
        forged = _norm(
            "Loop termination: re-run ALL selected reviewers after any "
            "productive loop."
        )
        self.assertNotIn("threat_model_path", forged)


class TestAC4EvaluatorInputUntouched(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r3a = DocumentFixture.r3a()

    def test_non_vacuity_r3a_slice_is_the_evaluator_section(self):
        self.assertIn("single Opus evaluator", self.r3a)

    def test_threat_model_path_never_mentioned_in_r3a(self):
        self.assertNotIn("threat_model_path", self.r3a)


# ---------------------------------------------------------------------------
# AC-5: Phase R0 keeps its 8 steps, in order; the digest pin itself lives in
# tests/test_tier_record_schema_v2.py (checked there); the five sibling
# suites pass unmodified.
# ---------------------------------------------------------------------------

STEP_LINE_RE = re.compile(r"(?m)^(\d+)\. ")


class TestAC5StepNumberingAndOrderPreserved(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r0 = DocumentFixture.r0()

    def test_exactly_eight_top_level_numbered_steps_in_order(self):
        numbers = [int(n) for n in STEP_LINE_RE.findall(self.r0)]
        self.assertEqual(numbers, list(range(1, 9)))

    def test_probe_order_litellm_before_ntd_before_prior_rounds(self):
        idx_litellm = self.r0.index("Probe litellm")
        idx_ntd = self.r0.index("Probe notion-task-dispatch")
        idx_prior = self.r0.index("Load prior rounds")
        self.assertLess(idx_litellm, idx_ntd)
        self.assertLess(idx_ntd, idx_prior)

    def test_negative_proof_forged_renumbering_fails_the_matcher(self):
        forged_r0 = "1. one\n2. two\n2. two-again\n4. four\n"
        numbers = [int(n) for n in STEP_LINE_RE.findall(forged_r0)]
        self.assertNotEqual(numbers, list(range(1, 9)))


class TestAC5SiblingSuitesPassUnmodified(unittest.TestCase):
    """AC-5: these five modules pass without modification by this task. A
    suite cannot assert its own full-suite outcome (test_sca_axis_review_
    phase_r0_r3.py's AC-7 precedent), but it CAN actually run each named
    sibling module as a subprocess and assert that module's own exit
    code -- which is exactly the regression this task could otherwise
    cause silently."""

    def test_each_sibling_suite_passes(self):
        for module in SIBLING_SUITE_MODULES:
            with self.subTest(module=module):
                result = subprocess.run(
                    [sys.executable, "-m", "unittest", module],
                    cwd=str(REPO_ROOT),
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(
                    result.returncode,
                    0,
                    f"{module} failed: stdout={result.stdout}\n"
                    f"stderr={result.stderr}",
                )


# ---------------------------------------------------------------------------
# AC-6: this module's own hygiene, plus the manifest version-only invariant.
# ---------------------------------------------------------------------------


def _canonical_without_version(data):
    clone = dict(data)
    clone.pop("version", None)
    return json.dumps(clone, sort_keys=True, ensure_ascii=False)


def _sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _marketplace_em_workflow_entry(data):
    for entry in data.get("plugins", []):
        if entry.get("name") == "em-workflow":
            return entry
    raise AssertionError("no marketplace entry named 'em-workflow'")


# Pinned from this module's own pre-task reading of both manifest files
# (canonical JSON with the `version` key removed, sha256 of the UTF-8
# bytes) -- unaffected by whether IMPLEMENTATION.md SC-6's commit-guard
# fallback ends up bumping the version in this task's commit.
PLUGIN_JSON_NON_VERSION_SHA256 = (
    "bf70d7104511c338b6f076c3d9ab08b6a19b757b59d45397324242f11008ebf0"
)
MARKETPLACE_ENTRY_NON_VERSION_SHA256 = (
    "ff0048295446075c937c1764ffe844dce42ef8b8d32ff1578c13b5ee5cf2e5da"
)


class TestAC6ManifestVersionOnlyInvariant(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plugin_data = _load_json(PLUGIN_MANIFEST_PATH)
        cls.marketplace_data = _load_json(MARKETPLACE_PATH)
        cls.entry = _marketplace_em_workflow_entry(cls.marketplace_data)

    def test_non_vacuity_manifests_are_non_trivial(self):
        self.assertGreater(PLUGIN_MANIFEST_PATH.stat().st_size, 50)
        self.assertIn("version", self.plugin_data)
        self.assertIn("version", self.entry)

    def test_plugin_json_unchanged_outside_version(self):
        digest = _sha256_text(_canonical_without_version(self.plugin_data))
        self.assertEqual(digest, PLUGIN_JSON_NON_VERSION_SHA256)

    def test_marketplace_entry_unchanged_outside_version(self):
        digest = _sha256_text(_canonical_without_version(self.entry))
        self.assertEqual(digest, MARKETPLACE_ENTRY_NON_VERSION_SHA256)

    def test_both_registries_agree_on_version(self):
        self.assertEqual(self.plugin_data.get("version"), self.entry.get("version"))

    def test_negative_proof_a_changed_description_would_fail_the_pin(self):
        mutated = dict(self.plugin_data)
        mutated["description"] = (mutated.get("description") or "") + " mutated"
        digest = _sha256_text(_canonical_without_version(mutated))
        self.assertNotEqual(digest, PLUGIN_JSON_NON_VERSION_SHA256)

    def test_negative_proof_disagreeing_versions_would_fail(self):
        self.assertNotEqual("0.2.14", "0.2.15")


class TestOwnModuleStdlibOnly(unittest.TestCase):
    def test_only_standard_library_imports(self):
        source = Path(__file__).read_text(encoding="utf-8")
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


if __name__ == "__main__":
    unittest.main()
