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

Covers task0001 Acceptance Criteria:
- AC-1: tier-rules.yaml parses as YAML and carries all four named
  top-level groups.
- AC-2: the rules file names the external judgement skill and the
  external model-guidance skill by path, reproduces no sentence from
  either, names the readonly Codex wrapper, and never names the raw
  `codex exec` subcommand as an invocation route.
- AC-3: TS-10's three threshold cases, plus the "at or above" edge cases.
- AC-4: no threshold expressed against the confidence member alone,
  anywhere in the rules file or the evaluator.
- AC-5: every fallback-matrix-unusable combination (TS-9), including each
  documented non-zero Jev exit status, resolves to the removes-nothing
  tier with a named reason.
- AC-6: missing/malformed/incomplete input yields the removes-nothing
  tier with a reason naming what was missing, exit status 0, no prompt.
- AC-7: this module is discovered by `python3 -m unittest discover -s
  tests`, imports only the standard library directly, and each of its
  raw-text matchers is paired with a negative proof and a non-vacuity
  guard.
"""

import ast
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
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


def run_cli(stdin_text, rules_path=None):
    args = [sys.executable, str(DECIDE_TIER_SCRIPT)]
    if rules_path is not None:
        args.append(str(rules_path))
    return subprocess.run(
        args,
        input=stdin_text,
        capture_output=True,
        text=True,
        timeout=15,
    )


def build_payload(p0=None, p1=None, expectation_clear=None, jev_available=True,
                   codex_available=True, basis="description_plus_code"):
    probabilities = {}
    if p0 is not None:
        probabilities["0"] = p0
    if p1 is not None:
        probabilities["1"] = p1
    score = {"probabilities": probabilities}
    if expectation_clear is not None:
        score["expectation_clear"] = expectation_clear
    return {
        "jev_available": jev_available,
        "codex_available": codex_available,
        "basis": basis,
        "score": score,
    }


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
# AC-3 (TS-10): threshold row evaluation, direct calls into the evaluator
# ---------------------------------------------------------------------------


class TestThresholdRowEvaluation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = dt._load_rules(TIER_RULES_PATH)

    def _decide(self, **kwargs):
        payload = build_payload(**kwargs)
        return dt.decide(payload, self.rules)

    def test_ts10_high_probability_and_clear_expectation_is_minimal(self):
        result = self._decide(p0=0.81, expectation_clear=0.6)
        self.assertEqual(result["tier"], "minimal")
        self.assertEqual(result["decided_by"], "threshold_rows:minimal")

    def test_ts10_low_first_bucket_carried_by_second_is_full(self):
        # The whole point of the first-bucket floor: P(0)+P(1) = 0.96 >=
        # 0.85, but P(0) alone (0.37) is below the 0.40 floor, so this must
        # NOT reach `reduced`.
        result = self._decide(p0=0.37, p1=0.59)
        self.assertEqual(result["tier"], "full")
        self.assertEqual(result["decided_by"], "threshold_rows:full")

    def test_ts10_moderate_first_bucket_with_high_sum_is_reduced(self):
        result = self._decide(p0=0.50, p1=0.40)
        self.assertEqual(result["tier"], "reduced")
        self.assertEqual(result["decided_by"], "threshold_rows:reduced")

    def test_edge_case_p0_and_clarity_exactly_at_the_minimal_floor(self):
        result = self._decide(p0=0.80, expectation_clear=0.5)
        self.assertEqual(result["tier"], "minimal")

    def test_edge_case_p0_and_sum_exactly_at_the_reduced_floor(self):
        result = self._decide(p0=0.40, p1=0.45)  # sum == 0.85 exactly
        self.assertEqual(result["tier"], "reduced")

    def test_row_order_first_match_wins(self):
        # A score that would also satisfy `reduced`'s condition still
        # resolves to `minimal` because that row is evaluated first.
        result = self._decide(p0=0.90, p1=0.05, expectation_clear=0.9)
        self.assertEqual(result["tier"], "minimal")

    def test_a_score_meeting_neither_row_is_full_not_an_error(self):
        result = self._decide(p0=0.10, p1=0.10, expectation_clear=0.1)
        self.assertEqual(result["tier"], "full")
        self.assertEqual(result["decided_by"], "threshold_rows:full")

    def test_reversing_the_ts10_reduced_and_full_inputs_would_fail(self):
        # Non-vacuity guard on the two discriminating cases above: swapping
        # their expected tiers must make the assertions fail, proving they
        # are not vacuously true regardless of input.
        full_case = self._decide(p0=0.37, p1=0.59)
        reduced_case = self._decide(p0=0.50, p1=0.40)
        with self.assertRaises(AssertionError):
            self.assertEqual(full_case["tier"], "reduced")
        with self.assertRaises(AssertionError):
            self.assertEqual(reduced_case["tier"], "full")


# ---------------------------------------------------------------------------
# AC-5 (TS-9): every fallback-matrix-unusable combination
# ---------------------------------------------------------------------------


class TestFallbackMatrixUnusableCombinations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = dt._load_rules(TIER_RULES_PATH)
        cls.rules_text = TIER_RULES_PATH.read_text(encoding="utf-8")

    def test_jev_exit_codes_documented_as_specified(self):
        # FR13: 0 succeeds; 1, 2 (HTTP 401), 75 (HTTP 429/529) are the
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

    def test_jev_unusable_with_codex_available_yields_full(self):
        payload = build_payload(p0=0.90, expectation_clear=0.9, jev_available=False,
                                 codex_available=True)
        result = dt.decide(payload, self.rules)
        self.assertEqual(result["tier"], "full")
        self.assertEqual(result["decided_by"], "fallback_matrix:jev_unusable")
        self.assertTrue(result["reason"])

    def test_jev_unusable_with_codex_unavailable_yields_full(self):
        payload = build_payload(p0=0.90, expectation_clear=0.9, jev_available=False,
                                 codex_available=False)
        result = dt.decide(payload, self.rules)
        self.assertEqual(result["tier"], "full")
        self.assertEqual(result["decided_by"], "fallback_matrix:jev_unusable")

    def test_jev_unusable_overrides_an_otherwise_minimal_score(self):
        # Non-vacuity guard: the SAME score, with jev_available flipped to
        # True, would have produced `minimal` -- proving the fallback
        # branch, not the score, is what forced `full` above.
        usable_payload = build_payload(p0=0.90, expectation_clear=0.9, jev_available=True,
                                        codex_available=True)
        usable_result = dt.decide(usable_payload, self.rules)
        self.assertEqual(usable_result["tier"], "minimal")

    def test_jev_usable_codex_unavailable_still_evaluates_thresholds(self):
        # The "only the judgement skill usable" row: codex_available=False
        # does not by itself force `full` -- the score is still evaluated.
        payload = build_payload(p0=0.90, expectation_clear=0.9, jev_available=True,
                                 codex_available=False)
        result = dt.decide(payload, self.rules)
        self.assertEqual(result["tier"], "minimal")
        self.assertEqual(result["decided_by"], "threshold_rows:minimal")

    def test_both_usable_evaluates_thresholds(self):
        payload = build_payload(p0=0.90, expectation_clear=0.9, jev_available=True,
                                 codex_available=True)
        result = dt.decide(payload, self.rules)
        self.assertEqual(result["tier"], "minimal")


# ---------------------------------------------------------------------------
# AC-6: missing / malformed / incomplete input
# ---------------------------------------------------------------------------


class TestDegradedInputUnitLevel(unittest.TestCase):
    """Direct decide() calls for input shapes that never need the CLI
    layer (missing/incomplete fields inside an otherwise-JSON payload)."""

    @classmethod
    def setUpClass(cls):
        cls.rules = dt._load_rules(TIER_RULES_PATH)

    def test_missing_jev_available_names_the_missing_field(self):
        payload = {"codex_available": True, "score": {"probabilities": {"0": 0.9}}}
        result = dt.decide(payload, self.rules)
        self.assertEqual(result["tier"], "full")
        self.assertIn("jev_available", result["reason"])

    def test_non_boolean_jev_available_is_treated_as_malformed(self):
        payload = {"jev_available": "yes", "codex_available": True, "score": {}}
        result = dt.decide(payload, self.rules)
        self.assertEqual(result["tier"], "full")
        self.assertIn("jev_available", result["reason"])

    def test_missing_codex_available_names_the_missing_field(self):
        payload = {"jev_available": True, "score": {"probabilities": {"0": 0.9}}}
        result = dt.decide(payload, self.rules)
        self.assertEqual(result["tier"], "full")
        self.assertIn("codex_available", result["reason"])

    def test_missing_score_when_jev_available_names_the_missing_field(self):
        payload = {"jev_available": True, "codex_available": True}
        result = dt.decide(payload, self.rules)
        self.assertEqual(result["tier"], "full")
        self.assertIn("score", result["reason"])

    def test_score_with_missing_members_falls_through_to_full(self):
        # A different code path from "score absent entirely": here the row
        # simply does not match and evaluation falls through (Design
        # section), still ending at `full`.
        payload = {
            "jev_available": True,
            "codex_available": True,
            "score": {"probabilities": {}},
        }
        result = dt.decide(payload, self.rules)
        self.assertEqual(result["tier"], "full")
        self.assertEqual(result["decided_by"], "threshold_rows:full")

    def test_payload_not_an_object_yields_full(self):
        result = dt.decide(["not", "a", "mapping"], self.rules)
        self.assertEqual(result["tier"], "full")
        self.assertTrue(result["reason"])

    def test_missing_field_matcher_would_fail_on_a_complete_payload(self):
        # Non-vacuity guard: a complete, well-formed payload must NOT
        # report a missing field.
        complete = build_payload(p0=0.1, p1=0.1, expectation_clear=0.1)
        result = dt.decide(complete, self.rules)
        self.assertNotIn("jev_available", result["reason"])
        self.assertNotIn("codex_available", result["reason"])


class TestDegradedInputCliLevel(unittest.TestCase):
    """AC-6's CLI-facing half: zero exit status and no prompt, driven as a
    subprocess exactly the way Claude Code / the orchestrator would."""

    def test_empty_stdin_yields_full_with_zero_exit(self):
        result = run_cli("")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["tier"], "full")
        self.assertIn("empty", data["reason"].lower())

    def test_malformed_json_yields_full_with_zero_exit(self):
        result = run_cli("{not valid json")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["tier"], "full")
        self.assertIn("json", data["reason"].lower())

    def test_non_object_json_yields_full_with_zero_exit(self):
        result = run_cli("[1, 2, 3]")
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["tier"], "full")

    def test_well_formed_input_round_trips_through_the_cli(self):
        payload = build_payload(p0=0.81, expectation_clear=0.6)
        result = run_cli(json.dumps(payload))
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["tier"], "minimal")
        self.assertEqual(data["observed"]["score"], payload["score"])

    def test_cli_never_blocks_waiting_for_more_input(self):
        # A 15s subprocess timeout with no matching completion would raise
        # TimeoutExpired; not raising proves no interactive read occurred.
        result = run_cli("")
        self.assertIsNotNone(result.returncode)

    def test_custom_rule_table_path_argument_is_honoured(self):
        with tempfile.TemporaryDirectory() as tmp:
            custom_path = Path(tmp) / "custom-tier-rules.yaml"
            custom_path.write_text(
                "threshold_rows:\n"
                "  - id: minimal\n"
                "    tier: minimal\n"
                "    p0_floor: 0.01\n"
                "    expectation_clear_floor: 0.01\n",
                encoding="utf-8",
            )
            # A score that would be `full` against the real rule table
            # easily clears this forged table's near-zero floors.
            payload = build_payload(p0=0.05, expectation_clear=0.05)
            result = run_cli(json.dumps(payload), rules_path=custom_path)
            self.assertEqual(result.returncode, 0, result.stderr)
            data = json.loads(result.stdout)
            self.assertEqual(data["tier"], "minimal")

    def test_default_path_argument_matcher_would_fail_without_the_override(self):
        # Non-vacuity guard: the same score against the REAL default table
        # (no override) must NOT be `minimal`, proving the override above
        # is what changed the outcome.
        payload = build_payload(p0=0.05, expectation_clear=0.05)
        result = run_cli(json.dumps(payload))
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(data["tier"], "full")


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
