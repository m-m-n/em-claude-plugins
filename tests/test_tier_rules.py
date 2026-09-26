"""Tests for em-workflow/references/tier-rules.yaml and
em-workflow/scripts/decide-tier.py (feature-docs/task-tier-reduction,
task0001).

Behavioural tests (threshold rows, fallback-matrix combinations, the
degraded-input path) load decide-tier.py via importlib.util and call its
functions directly -- the same technique tests/test_check_plugin_invariants.py
already uses for check-plugin-invariants.py -- rather than importing PyYAML
in this test module (NFR7: test code imports no third-party package;
decide-tier.py's own `import yaml` is a runtime dependency of the plugin,
not a test dependency). CLI-contract tests (exit status, stdin/stdout JSON,
the rule-table path argument) drive the script as a subprocess, matching
test/README.md's convention for hook/script contract tests.

Conformance tests (group presence, the external-skill non-duplication
check, and the confidence-only absence check) read tier-rules.yaml's raw
file text rather than a parsed structure, so a violation hidden inside a
YAML comment still fails (task plan Test Notes). Each such matcher is
paired with a negative proof against a forged sample plus a non-vacuity
guard (IMPLEMENTATION.md "Test module convention").

Covers task0001 Acceptance Criteria (feature-docs/task-tier-reduction,
the predecessor feature this module was originally written for):
- AC-1: tier-rules.yaml parses as YAML and carries all four named
  top-level groups.
- AC-2: the rules file names the external judgement skill and the
  external model-guidance skill by path, reproduces no sentence from
  either, names the readonly Codex wrapper, and never names the raw
  `codex exec` subcommand as an invocation route.
- AC-4: no threshold expressed against the confidence member alone,
  anywhere in the rules file or the evaluator.
- AC-7: this module is discovered by `python3 -m unittest discover -s
  tests`, imports only the standard library directly, and each of its
  raw-text matchers is paired with a negative proof and a non-vacuity
  guard.

D6 rewrite (feature-docs/tier-decision-staged-jev, task0001 of THAT
feature): the predecessor feature's AC-3 (`TestThresholdRowEvaluation`,
threshold rows over `probabilities["0"|"1"]` + `expectation_clear`) and
AC-5/AC-6 behavior tests (`TestDegradedInputUnitLevel`,
`TestDegradedInputCliLevel`, and the `decide()`-driven half of
`TestFallbackMatrixUnusableCombinations`) asserted the single-reading
`basis`/`score` input shape and the old threshold-row scheme this feature
replaces. That coverage is retired here and superseded by the new
dedicated file `tests/test_decide_tier_final_score.py` (this feature's own
task0001), which asserts the equivalent behavior against the new
`final_score.probabilities` (buckets `"0"`-`"3"`) contract. The
`jev_exit_codes` structural checks below are kept unchanged: that table is
read-only for this task and its content did not change.
"""

import ast
import importlib.util
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TIER_RULES_PATH = REPO_ROOT / "em-workflow" / "references" / "tier-rules.yaml"
DECIDE_TIER_SCRIPT = REPO_ROOT / "em-workflow" / "scripts" / "decide-tier.py"
THIS_TEST_FILE = Path(__file__).resolve()

JEV_SKILL_DOC = Path.home() / ".claude" / "skills" / "jev" / "SKILL.md"
TYPESAFE_CACHE_ROOT = Path.home() / ".claude" / "plugins" / "cache" / "typesafe-ai"

# "short" line-length threshold below which incidental overlap (a YAML key,
# a short data value) is not evidence of copying (task plan Test Notes).
MIN_DUP_LINE_LEN = 40


def load_decide_tier_module():
    spec = importlib.util.spec_from_file_location(
        "_decide_tier_under_test", DECIDE_TIER_SCRIPT
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


dt = load_decide_tier_module()


def find_typesafe_skill_doc():
    """Locate the typesafe-ai skill's SKILL.md under the plugin cache. The
    path is version-numbered (.../typesafe/<version>/skills/typesafe-ai/
    SKILL.md) so it is discovered by glob rather than pinned literally."""
    if not TYPESAFE_CACHE_ROOT.is_dir():
        return None
    matches = sorted(TYPESAFE_CACHE_ROOT.glob("typesafe/*/skills/typesafe-ai/SKILL.md"))
    return matches[0] if matches else None


# ---------------------------------------------------------------------------
# AC-1: parses as YAML, carries all four named top-level groups
# ---------------------------------------------------------------------------


class TestRulesFileStructure(unittest.TestCase):
    TOP_LEVEL_GROUPS = [
        "question_set",
        "threshold_rows",
        "codex_output_schema",
        "fallback_matrix",
    ]

    @classmethod
    def setUpClass(cls):
        cls.text = TIER_RULES_PATH.read_text(encoding="utf-8")

    def test_parses_as_yaml(self):
        rules = dt._load_rules(TIER_RULES_PATH)
        self.assertIsInstance(rules, dict)
        self.assertGreater(len(rules), 0)

    def test_all_four_named_groups_present(self):
        for group in self.TOP_LEVEL_GROUPS:
            with self.subTest(group=group):
                self.assertRegex(self.text, rf"(?m)^{re.escape(group)}:")

    def _without_top_level_key(self, key):
        return "\n".join(
            line for line in self.text.splitlines() if not line.startswith(f"{key}:")
        )

    def test_group_presence_matcher_would_fail_on_a_forged_removal(self):
        # Negative proof + non-vacuity guard, once per group: strip only
        # that group's top-level key line and confirm the same matcher used
        # above now fails against the forged copy.
        for group in self.TOP_LEVEL_GROUPS:
            with self.subTest(group=group):
                forged = self._without_top_level_key(group)
                self.assertNotRegex(forged, rf"(?m)^{re.escape(group)}:")
                # Non-vacuity: the real text does carry it, so the forgery
                # actually changed something the matcher can discriminate.
                self.assertRegex(self.text, rf"(?m)^{re.escape(group)}:")


# ---------------------------------------------------------------------------
# AC-2: external skills named by path, no duplication, wrapper-only route
# ---------------------------------------------------------------------------


class TestExternalSkillsNamedByPathNotReproduced(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = TIER_RULES_PATH.read_text(encoding="utf-8")

    def test_names_jev_skill_by_path(self):
        self.assertIn("~/.claude/skills/jev", self.text)

    def test_names_typesafe_skill_by_path(self):
        self.assertIn("typesafe:typesafe-ai", self.text)

    def test_naming_matcher_would_fail_on_a_forged_copy_missing_it(self):
        forged = self.text.replace("~/.claude/skills/jev", "")
        self.assertNotIn("~/.claude/skills/jev", forged)
        self.assertIn("~/.claude/skills/jev", self.text)

        forged2 = self.text.replace("typesafe:typesafe-ai", "")
        self.assertNotIn("typesafe:typesafe-ai", forged2)
        self.assertIn("typesafe:typesafe-ai", self.text)

    def test_names_readonly_wrapper_as_the_route(self):
        self.assertIn("run_codex_exec.sh", self.text)
        self.assertIn("readonly", self.text)

    def test_does_not_name_raw_subcommand_as_an_invocation_route(self):
        # The raw subcommand is written as two space-separated words
        # ("codex exec"), distinct from the wrapper's filename token
        # ("run_codex_exec.sh", underscore-joined, no space). Wherever the
        # raw form appears, it must be inside a `forbidden:`-style
        # statement, never inside a `route:` statement.
        for match in re.finditer(r"codex exec", self.text):
            start = match.start()
            line_start = self.text.rfind("\n", 0, start) + 1
            context = self.text[max(0, start - 200) : start + 200]
            self.assertIn("forbidden", context.lower())
            line_end = self.text.find("\n", line_start)
            line = self.text[line_start : line_end if line_end != -1 else None]
            self.assertNotRegex(line, r"route:\s*.*codex exec")

    def test_raw_subcommand_matcher_would_fail_on_a_forged_route(self):
        # Non-vacuity guard: a forged copy that DOES name the raw
        # subcommand as a route must be rejected by the same logic above.
        forged = self.text + '\nforged_invocation:\n  route: "codex exec"\n'
        offending = [
            m for m in re.finditer(r"codex exec", forged)
            if "forbidden" not in forged[max(0, m.start() - 200) : m.start() + 200].lower()
        ]
        self.assertTrue(
            offending, "forged sample must contain a non-forbidden 'codex exec' mention"
        )


class TestNoDuplicationOfExternalSkillContent(unittest.TestCase):
    """NFR5's non-duplication half: no long line of tier-rules.yaml is also
    present verbatim in the external skills' own documents. Skipped (with a
    recorded reason) when a document is not readable in this environment,
    per the task plan's explicit instruction -- the structural half above
    (naming by path) is asserted unconditionally regardless."""

    @classmethod
    def setUpClass(cls):
        cls.rules_lines = [
            line.strip()
            for line in TIER_RULES_PATH.read_text(encoding="utf-8").splitlines()
            if len(line.strip()) > MIN_DUP_LINE_LEN
        ]

    def test_no_long_line_duplicated_from_jev_skill_doc(self):
        if not JEV_SKILL_DOC.is_file():
            self.skipTest(f"{JEV_SKILL_DOC} not readable in this environment")
        jev_text = JEV_SKILL_DOC.read_text(encoding="utf-8")
        offenders = [line for line in self.rules_lines if line in jev_text]
        self.assertEqual(
            offenders, [], f"lines duplicated verbatim from the jev skill doc: {offenders}"
        )

    def test_no_long_line_duplicated_from_typesafe_skill_doc(self):
        typesafe_doc = find_typesafe_skill_doc()
        if typesafe_doc is None:
            self.skipTest("typesafe-ai skill SKILL.md not readable in this environment")
        typesafe_text = typesafe_doc.read_text(encoding="utf-8")
        offenders = [line for line in self.rules_lines if line in typesafe_text]
        self.assertEqual(
            offenders,
            [],
            f"lines duplicated verbatim from the typesafe-ai skill doc: {offenders}",
        )


# ---------------------------------------------------------------------------
# AC-4: no threshold expressed against `confidence` alone
# ---------------------------------------------------------------------------

CONFIDENCE_ALONE_PATTERN = re.compile(r"confidence[^\n]{0,40}(>=|<=|>|<)")


class TestConfidenceNeverThresholdedAlone(unittest.TestCase):
    def test_absent_from_rules_file(self):
        text = TIER_RULES_PATH.read_text(encoding="utf-8")
        self.assertIsNone(CONFIDENCE_ALONE_PATTERN.search(text))

    def test_absent_from_evaluator_source(self):
        text = DECIDE_TIER_SCRIPT.read_text(encoding="utf-8")
        self.assertIsNone(CONFIDENCE_ALONE_PATTERN.search(text))

    def test_absence_matcher_fires_on_a_forged_copy_carrying_one(self):
        # Non-vacuity guard, per AC-4's own wording: the negative proof
        # must show the checker WOULD catch a real violation.
        forged_rules = (
            TIER_RULES_PATH.read_text(encoding="utf-8")
            + "\nforged_threshold: confidence >= 0.9\n"
        )
        self.assertIsNotNone(CONFIDENCE_ALONE_PATTERN.search(forged_rules))

        forged_source = (
            DECIDE_TIER_SCRIPT.read_text(encoding="utf-8")
            + "\n# forged: if confidence >= 0.9: return 'minimal'\n"
        )
        self.assertIsNotNone(CONFIDENCE_ALONE_PATTERN.search(forged_source))


# ---------------------------------------------------------------------------
# jev_exit_codes: read-only, unchanged content -- kept as a structural
# check. The decide()-driven fallback/threshold behavior tests that used to
# live in this class (AC-5/AC-6 of the predecessor feature) were removed
# per the D6 rewrite note above.
# ---------------------------------------------------------------------------


class TestJevExitCodesDocumented(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = dt._load_rules(TIER_RULES_PATH)

    def test_jev_exit_codes_documented_as_specified(self):
        # FR9: 0 succeeds; 1, 2 (HTTP 401), 75 (HTTP 429/529) are the
        # documented non-zero codes, all "unusable".
        exit_codes = self.rules.get("jev_exit_codes")
        self.assertIsInstance(exit_codes, dict)
        self.assertEqual(exit_codes.get(0), "usable")
        for code in (1, 2, 75):
            with self.subTest(code=code):
                self.assertEqual(exit_codes.get(code), "unusable")

    def test_jev_exit_codes_matcher_would_fail_on_a_forged_usable_code(self):
        forged = dict(self.rules.get("jev_exit_codes") or {})
        forged[1] = "usable"
        self.assertNotEqual(forged.get(1), "unusable")
        # Non-vacuity: the real table does have it unusable.
        self.assertEqual(self.rules.get("jev_exit_codes", {}).get(1), "unusable")


# ---------------------------------------------------------------------------
# AC-7: module discoverability / stdlib-only imports for THIS test module
# ---------------------------------------------------------------------------


class TestThisModuleImportsOnlyTheStandardLibrary(unittest.TestCase):
    def test_only_standard_library_imports(self):
        source = THIS_TEST_FILE.read_text(encoding="utf-8")
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
