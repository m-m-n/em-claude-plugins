"""Tests for task0007 (task-tier-reduction): the spec perspective's absence
rule on the develop-driven review route.

Covers task0007 Acceptance Criteria
(feature-docs/task-tier-reduction/tasks/task0007.md):

- AC-1: review-phase.md's Phase R0 spec-location step (item 4, "Locate
  SPEC.md") states that an absent spec document on the develop-driven route
  sets `spec_available = false`, and keeps both existing constraints --
  the integration-worktree copy stays canonical, and the main tree is never
  resolved from.
- AC-2: Phase R1's Layer 1 floor description states that the spec
  perspective is dropped with a skip notice when `spec_available` is false,
  on the develop-driven route as well as the standalone one (TS-7); the
  fan-out step's own skip-rendering phrase (Phase R2) is not duplicated
  anywhere else in the document.
- AC-3: review-rules.yaml's header comment no longer claims the
  specification-driven flow guarantees the spec document exists, and no
  longer scopes the drop-with-a-skip-notice behaviour to the standalone
  command alone.
- AC-4: the `baseline` perspective list is byte-identical to its pre-change
  value and still contains `security`; the `rules:` rows are unchanged in
  content and order (NFR2).
- AC-5: evaluating the floor (union semantics, per review-rules.yaml's own
  header) with `spec_available = False` still yields `security` and
  `comprehensive` and never `spec` (TS-7). No script performs this
  evaluation, so it is implemented locally in this module (task0007.md Test
  Notes).
- AC-6: neither review-phase.md nor review-rules.yaml gains a condition that
  reads the tier -- an absence check over both files (including comments)
  that searches for the tier vocabulary rather than a single spelling, with
  a negative proof over a forged copy carrying one.
- AC-7: this module, asserting AC-1 through AC-6, is discovered by
  `python3 -m unittest discover -s tests`, imports only standard-library
  modules, and pairs each positive matcher with a negative proof and a
  non-vacuity guard.

Document assertions are made against raw file text (repository convention:
tests/test_sca_axis_review_phase_r0_r3.py, tests/test_review_phase_llm_led.py)
-- sections are sliced on literal headings and phrases are matched against
whitespace-normalized text, so a statement landing in the wrong phase/route
fails. review-rules.yaml's `baseline` / `rules:` rows (AC-4) and the floor
evaluator (AC-5) are read with a hand-rolled restricted-subset parser local
to this module (repository convention: tests/test_batch_policies.py,
tests/test_reviewers_primary_chains.py, tests/test_sca_axis_review_phase_r0_r3.py).
PyYAML is a runtime dependency of the em-workflow plugin, never a test
dependency (IMPLEMENTATION.md Technology Stack) -- this module imports the
standard library only.

Out of scope (task0007.md): tier-conditional perspective selection -- AC-6's
absence check is the only place this module looks for tier vocabulary, and
it asserts the vocabulary is NOT there.
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLUGIN_ROOT = os.path.join(REPO_ROOT, "em-workflow")
REVIEW_PHASE_PATH = os.path.join(PLUGIN_ROOT, "references", "review-phase.md")
REVIEW_RULES_PATH = os.path.join(PLUGIN_ROOT, "references", "review-rules.yaml")

R0_HEADING = "## Phase R0: Resolve SSOT & review target"
R1_HEADING = "## Phase R1: Perspective selection (two layers)"
R2_HEADING = "## Phase R2: Fan-out (ONE message, N Task calls)"
LAYER1_HEADING = "### Layer 1 — mechanical floor (deterministic, no diff input)"
LAYER2_HEADING = "### Layer 2 — discretionary additions (add-only)"

# The fan-out step's own literal skip-rendering phrase (Phase R2). AC-2's
# non-duplication requirement is checked against this exact string.
FAN_OUT_SKIP_PHRASE = (
    "skip `requires_spec` ones when `spec_available == false` — render as "
    "SKIPPED"
)


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _slice(text, start_heading, end_heading=None):
    start = text.index(start_heading)
    if end_heading is None:
        return text[start:]
    end = text.index(end_heading, start + len(start_heading))
    return text[start:end]


def _norm(text):
    return re.sub(r"\s+", " ", text).strip()


def _strip_comment_markers(text):
    """Strip a leading YAML `#` comment marker (and one following space)
    from every line, so cross-line prose in a comment block can be matched
    by whitespace-normalized substring search without embedded `#` noise
    at each 79-column reflow point."""
    stripped_lines = []
    for line in text.splitlines():
        lstripped = line.lstrip()
        if lstripped.startswith("#"):
            rest = lstripped[1:]
            if rest.startswith(" "):
                rest = rest[1:]
            stripped_lines.append(rest)
        else:
            stripped_lines.append(line)
    return "\n".join(stripped_lines)


class DocumentFixture:
    """Reads review-phase.md once and slices out the sections this module
    needs (task0007 touches R0 item 4 and R1's Layer 1 only)."""

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
    def r1(cls):
        return _slice(cls.text(), R1_HEADING, R2_HEADING)

    @classmethod
    def layer1(cls):
        return _slice(cls.r1(), LAYER1_HEADING, LAYER2_HEADING)


# ---------------------------------------------------------------------------
# AC-1: R0 item 4 ("Locate SPEC.md") states the develop-driven absence rule.
# ---------------------------------------------------------------------------


class TestAC1SpecLocationStepAvailabilityFlag(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        step4 = _slice(DocumentFixture.r0(), "4. Locate SPEC.md", "5. Probe codex")
        cls.step4 = step4
        cls.develop_clause = step4[: step4.index("Standalone →")]
        cls.develop_norm = _norm(cls.develop_clause)

    def test_absent_spec_sets_availability_flag_false_on_develop_route(self):
        self.assertIn("absent ⇒ `spec_available = false`", self.develop_norm)

    def test_integration_worktree_copy_stays_canonical(self):
        self.assertIn(
            "the committed copy inside the integration worktree is the "
            "canonical review input",
            self.develop_norm,
        )

    def test_main_tree_never_resolved_from(self):
        self.assertIn(
            "Do NOT resolve the spec from the main tree", self.develop_norm
        )

    def test_old_must_exist_sdd_guarantee_claim_is_gone(self):
        lowered = self.develop_norm.lower()
        self.assertNotIn("must exist", lowered)
        self.assertNotIn("sdd guarantees", lowered)
        self.assertNotIn("sdd flow guarantees", lowered)

    def test_non_vacuity_slice_is_the_develop_clause_not_the_whole_step(self):
        # Proves the "Standalone →" split actually shortened the text --
        # otherwise the assertions above could be trivially vacuous.
        self.assertLess(len(self.develop_clause), len(self.step4))
        self.assertIn("Locate SPEC.md", self.step4)

    def test_negative_proof_old_wording_fails_the_new_checks(self):
        old_step4 = (
            "4. Locate SPEC.md: develop-駆動 → "
            "`{project_root}/feature-docs/{feature}/SPEC.md`\n"
            "   — the committed copy inside the integration worktree is the "
            "canonical\n"
            "   review input (must exist; SDD guarantees it). Do NOT "
            "resolve the spec from\n"
            "   the main tree: the containment check below is "
            "project_root-based and the\n"
            "   integration copy is what the reviewed code was built "
            "against. Standalone →\n"
        )
        old_develop_clause = old_step4[: old_step4.index("Standalone →")]
        old_norm = _norm(old_develop_clause)
        self.assertNotIn("absent ⇒ `spec_available = false`", old_norm)
        self.assertIn("must exist", old_norm.lower())
        # The two constraints this task must preserve were already present
        # in the old wording -- proving the new checks above discriminate
        # only on the flag statement, not on these.
        self.assertIn(
            "the committed copy inside the integration worktree is the "
            "canonical review input",
            old_norm,
        )
        self.assertIn("Do NOT resolve the spec from the main tree", old_norm)


# ---------------------------------------------------------------------------
# AC-2: R1 Layer 1 floor description widens the drop-with-skip-notice rule.
# ---------------------------------------------------------------------------


class TestAC2FloorDescriptionDropsSpecOnBothRoutes(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.layer1 = DocumentFixture.layer1()
        cls.norm = _norm(cls.layer1)

    def test_states_drop_with_skip_notice_when_unavailable(self):
        self.assertIn("dropped with a skip notice", self.norm)

    def test_applies_explicitly_to_the_develop_driven_route(self):
        self.assertIn("On the develop-駆動 route too", self.norm)

    def test_standalone_case_still_stated_unchanged(self):
        self.assertIn(
            "Standalone with no workflow.yaml: the floor is `baseline` + "
            "(`spec` if spec_available) only",
            self.norm,
        )

    def test_non_vacuity_layer1_slice_excludes_layer2_body(self):
        # Proves the heading-bounded slice actually stopped before Layer 2
        # -- otherwise "applies to develop route" could be satisfied by text
        # belonging to a different section entirely.
        self.assertNotIn("Mandatory Layer-2 check", self.layer1)

    def test_negative_proof_old_wording_lacked_the_develop_route_rule(self):
        old_layer1 = (
            LAYER1_HEADING + "\n\n"
            "Input: ONLY the declared task metadata. develop-駆動: the "
            "`domains` /\n"
            "`complexity` of the tasks in THIS feature's workflow.yaml. "
            "Standalone with no\n"
            "workflow.yaml: the floor is `baseline` + (`spec` if "
            "spec_available) only.\n"
        )
        old_norm = _norm(old_layer1)
        self.assertNotIn("dropped with a skip notice", old_norm)
        # The standalone clause was already present -- proving the new
        # check discriminates on the added develop-route rule, not on text
        # that was already there.
        self.assertIn(
            "Standalone with no workflow.yaml: the floor is `baseline` + "
            "(`spec` if spec_available) only",
            old_norm,
        )


class TestAC2FanOutSkipPhraseNotDuplicated(unittest.TestCase):
    """The phrase reflows across a line break in the raw markdown (`(skip` /
    `` `requires_spec` ``), so this checks the whitespace-normalized whole
    document -- same normalization discipline as every other assertion in
    this module."""

    def test_fan_out_skip_phrase_appears_exactly_once(self):
        norm = _norm(DocumentFixture.text())
        self.assertEqual(norm.count(FAN_OUT_SKIP_PHRASE), 1)

    def test_non_vacuity_phrase_is_actually_present(self):
        self.assertIn(FAN_OUT_SKIP_PHRASE, _norm(DocumentFixture.text()))

    def test_negative_proof_a_duplicate_would_be_caught(self):
        norm = _norm(DocumentFixture.text())
        forged = norm + " " + FAN_OUT_SKIP_PHRASE
        self.assertEqual(forged.count(FAN_OUT_SKIP_PHRASE), 2)


# ---------------------------------------------------------------------------
# AC-3: review-rules.yaml header no longer over-claims / under-scopes.
# ---------------------------------------------------------------------------


class TestAC3ReviewRulesHeaderWidenedSymmetrically(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(REVIEW_RULES_PATH)
        cls.header = cls.text.split("\nbaseline:", 1)[0]
        cls.norm = _norm(_strip_comment_markers(cls.header))

    def test_no_longer_claims_unconditional_inclusion(self):
        self.assertNotIn("unconditionally included", self.norm)

    def test_no_longer_claims_sdd_flow_guarantees_spec_exists(self):
        lowered = self.norm.lower()
        self.assertNotIn("sdd flow guarantees", lowered)
        self.assertNotIn("guarantees spec.md exists", lowered)

    def test_no_longer_scopes_drop_behaviour_to_standalone_command_alone(self):
        self.assertNotIn(
            "In standalone /em-workflow:review without a SPEC.md, spec is "
            "dropped",
            self.norm,
        )

    def test_new_symmetric_availability_wording_present(self):
        self.assertIn(
            "the spec perspective is included whenever the spec document "
            "is available",
            self.norm,
        )
        self.assertIn(
            "on the develop-driven route the same as on the standalone one",
            self.norm,
        )

    def test_skip_notice_behaviour_still_named(self):
        self.assertIn("dropped with a skip notice", self.norm)

    def test_non_vacuity_header_still_describes_baseline_and_layer_rules(self):
        self.assertIn("baseline perspectives are always included", self.norm)
        self.assertIn("require lists are unioned", self.norm)

    def test_negative_proof_old_wording_trips_the_removed_claim_checks(self):
        old_header_fragment = (
            "# - spec_review: always → the spec perspective is "
            "unconditionally included\n"
            "#   (the SDD flow guarantees SPEC.md exists). In standalone "
            "/em-workflow:review\n"
            "#   without a SPEC.md, spec is dropped with a skip notice "
            "instead.\n"
        )
        old_norm = _norm(_strip_comment_markers(old_header_fragment))
        self.assertIn("unconditionally included", old_norm)
        self.assertIn("the sdd flow guarantees", old_norm.lower())
        self.assertIn(
            "In standalone /em-workflow:review without a SPEC.md, spec is "
            "dropped",
            old_norm,
        )


# ---------------------------------------------------------------------------
# AC-4: baseline / rule rows byte-identical to their pre-change value.
# ---------------------------------------------------------------------------

# Captured by direct inspection of review-rules.yaml at task start (this
# task never edits the `baseline:` line or the `rules:` block -- NFR2 -- so
# this is also its expected content afterward; repository convention:
# tests/test_sca_axis_review_phase_r0_r3.py's PINNED_READ_ONLY_CONSTRAINT).
PINNED_BASELINE_LINE = "baseline: [comprehensive, security]"
PINNED_RULES_BLOCK = (
    "rules:\n"
    "  - if_domains: [data-persistence]\n"
    "    require: [performance]\n"
    "  - if_domains: [concurrency, external-io]\n"
    "    require: [performance]\n"
    "  - if_domains: [api-contract]\n"
    "    require: [architecture]\n"
    "  - if_complexity: high\n"
    "    require: [architecture, comprehensive]"
)


class TestAC4BaselineAndRuleRowsUnchanged(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(REVIEW_RULES_PATH)

    def test_baseline_line_byte_identical_to_pre_change_value(self):
        line = next(
            line for line in self.text.splitlines() if line.startswith("baseline:")
        )
        self.assertEqual(line, PINNED_BASELINE_LINE)

    def test_baseline_still_contains_security(self):
        self.assertIn("security", PINNED_BASELINE_LINE)

    def test_rules_block_byte_identical_to_pre_change_value(self):
        start = self.text.index("rules:\n")
        end = self.text.index("\n\nspec_review:", start)
        block = self.text[start:end]
        self.assertEqual(block, PINNED_RULES_BLOCK)

    def test_non_vacuity_pin_actually_has_four_rule_rows(self):
        self.assertEqual(
            len(re.findall(r"^  - if_", PINNED_RULES_BLOCK, re.MULTILINE)), 4
        )

    def test_negative_proof_security_removed_from_baseline_is_detected(self):
        forged = "baseline: [comprehensive]"
        self.assertNotEqual(forged, PINNED_BASELINE_LINE)

    def test_negative_proof_reordered_rules_are_detected(self):
        forged_block = (
            "rules:\n"
            "  - if_complexity: high\n"
            "    require: [architecture, comprehensive]\n"
            "  - if_domains: [data-persistence]\n"
            "    require: [performance]\n"
            "  - if_domains: [concurrency, external-io]\n"
            "    require: [performance]\n"
            "  - if_domains: [api-contract]\n"
            "    require: [architecture]"
        )
        self.assertNotEqual(forged_block, PINNED_RULES_BLOCK)


# ---------------------------------------------------------------------------
# AC-5: floor evaluation (union semantics) with spec_available = False.
# ---------------------------------------------------------------------------


def _parse_inline_list(value):
    value = value.strip()
    if not (value.startswith("[") and value.endswith("]")):
        raise ValueError(f"not an inline YAML list: {value!r}")
    inner = value[1:-1].strip()
    if not inner:
        return []
    return [item.strip() for item in inner.split(",")]


def parse_review_rules(text):
    """Restricted-subset parser (repository convention -- no PyYAML):
    returns {"baseline": [...], "rules": [{"if_domains"?, "if_complexity"?,
    "require": [...]}], "spec_review": "always"}."""
    lines = text.splitlines()
    baseline = None
    spec_review = None
    rules = []
    i = 0
    n = len(lines)
    while i < n:
        raw = lines[i].split("#", 1)[0].rstrip()
        stripped = raw.strip()
        if stripped.startswith("baseline:"):
            baseline = _parse_inline_list(stripped[len("baseline:"):])
            i += 1
            continue
        if stripped == "rules:":
            i += 1
            while i < n:
                rline = lines[i].split("#", 1)[0].rstrip()
                if not rline.strip():
                    i += 1
                    continue
                indent = len(rline) - len(rline.lstrip(" "))
                if indent == 0:
                    break
                item = rline.strip()
                if item.startswith("- if_domains:"):
                    rule = {"if_domains": _parse_inline_list(item[len("- if_domains:"):])}
                elif item.startswith("- if_complexity:"):
                    rule = {"if_complexity": item[len("- if_complexity:"):].strip()}
                else:
                    raise ValueError(f"unexpected rule line: {rline!r}")
                i += 1
                req_line = lines[i].split("#", 1)[0].strip()
                if not req_line.startswith("require:"):
                    raise ValueError(f"expected require: line, got {req_line!r}")
                rule["require"] = _parse_inline_list(req_line[len("require:"):])
                rules.append(rule)
                i += 1
            continue
        if stripped.startswith("spec_review:"):
            spec_review = stripped[len("spec_review:"):].strip()
        i += 1
    if baseline is None:
        raise ValueError("no `baseline:` key found")
    if spec_review is None:
        raise ValueError("no `spec_review:` key found")
    return {"baseline": baseline, "rules": rules, "spec_review": spec_review}


def evaluate_floor(rules_doc, tasks, spec_available):
    """Union semantics per review-rules.yaml's own header: baseline always
    included; a rule fires when ANY if_domains value is in the union of all
    tasks' domains, or if_complexity matches ANY task's complexity; require
    lists are unioned. `spec` enters the floor only when spec_review ==
    "always" AND spec_available (task0007's widened rule)."""
    domains_union = set()
    complexities = set()
    for task in tasks:
        domains_union.update(task.get("domains", []))
        if "complexity" in task:
            complexities.add(task["complexity"])
    floor = list(rules_doc["baseline"])
    for rule in rules_doc["rules"]:
        fired = False
        if "if_domains" in rule and domains_union.intersection(rule["if_domains"]):
            fired = True
        if "if_complexity" in rule and rule["if_complexity"] in complexities:
            fired = True
        if fired:
            for perspective in rule["require"]:
                if perspective not in floor:
                    floor.append(perspective)
    if rules_doc["spec_review"] == "always" and spec_available and "spec" not in floor:
        floor.append("spec")
    return floor


class TestAC5FloorExcludesSpecWhenUnavailable(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules_doc = parse_review_rules(_read(REVIEW_RULES_PATH))

    def test_floor_keeps_security_and_comprehensive_and_drops_spec(self):
        tasks = [{"domains": ["api-contract"], "complexity": "medium"}]
        floor = evaluate_floor(self.rules_doc, tasks, spec_available=False)
        self.assertIn("security", floor)
        self.assertIn("comprehensive", floor)
        self.assertNotIn("spec", floor)

    def test_holds_even_with_no_task_metadata_at_all(self):
        floor = evaluate_floor(self.rules_doc, tasks=[], spec_available=False)
        self.assertIn("security", floor)
        self.assertIn("comprehensive", floor)
        self.assertNotIn("spec", floor)

    def test_negative_proof_spec_available_true_adds_spec_back(self):
        tasks = [{"domains": ["api-contract"], "complexity": "medium"}]
        floor = evaluate_floor(self.rules_doc, tasks, spec_available=True)
        self.assertIn("spec", floor)

    def test_non_vacuity_evaluator_actually_fires_a_domain_rule(self):
        # Proves the evaluator does more than echo the baseline: an
        # api-contract task must pull in `architecture` via the rule table.
        tasks = [{"domains": ["api-contract"], "complexity": "low"}]
        floor = evaluate_floor(self.rules_doc, tasks, spec_available=False)
        self.assertIn("architecture", floor)


# ---------------------------------------------------------------------------
# AC-6: neither file gains a tier-reading condition.
# ---------------------------------------------------------------------------

# The pre-existing, unrelated "contributor tier" / "Contributor-tier"
# phrasing (muse-spark read-mapping, Phase R2) is the one legitimate
# occurrence of the word "tier" in review-phase.md and must not itself trip
# the absence check below.
_CONTRIBUTOR_TIER_RE = re.compile(r"[Cc]ontributor-tier|[Cc]ontributor tier")
_TIER_WORD_RE = re.compile(r"\btier\b", re.IGNORECASE)
_TIER_CODE_SPAN_TOKENS = ("`full`", "`reduced`", "`minimal`", "`tier_decision`")
_TIER_NAME_TOKENS = ("tier-rules.yaml", "decide-tier.py", "tier.yaml", "tier_decision")


def find_tier_vocabulary(text):
    """True iff `text` carries this feature's run-tier vocabulary -- the
    bare word "tier" outside the pre-existing "contributor tier" /
    "Contributor-tier" phrasing, one of the three tier labels as an
    inline-code span, or a reference to the tier decision artifacts."""
    stripped = _CONTRIBUTOR_TIER_RE.sub("", text)
    if _TIER_WORD_RE.search(stripped):
        return True
    return any(token in text for token in _TIER_CODE_SPAN_TOKENS + _TIER_NAME_TOKENS)


class TestAC6NoTierConditionInEitherFile(unittest.TestCase):
    def test_review_phase_carries_no_tier_vocabulary(self):
        self.assertFalse(find_tier_vocabulary(DocumentFixture.text()))

    def test_review_rules_carries_no_tier_vocabulary(self):
        self.assertFalse(find_tier_vocabulary(_read(REVIEW_RULES_PATH)))

    def test_non_vacuity_existing_contributor_tier_wording_survives_untouched(self):
        text = DocumentFixture.text()
        self.assertIn("contributor tier", text)
        self.assertIn("Contributor-tier", text)

    def test_negative_proof_fires_on_a_forged_bare_tier_condition(self):
        forged = (
            DocumentFixture.text()
            + "\nSkip the spec perspective when `tier` is `minimal`.\n"
        )
        self.assertTrue(find_tier_vocabulary(forged))

    def test_negative_proof_fires_on_a_forged_tier_label_reference(self):
        forged = "the floor drops a perspective on the `reduced` tier."
        self.assertTrue(find_tier_vocabulary(forged))

    def test_negative_proof_fires_on_a_forged_tier_decision_reference(self):
        forged = "read workflow.yaml's `tier_decision` before selecting."
        self.assertTrue(find_tier_vocabulary(forged))


# ---------------------------------------------------------------------------
# AC-7 / test ownership convention: standard-library-only imports.
# ---------------------------------------------------------------------------


class TestOwnModuleStdlibOnly(unittest.TestCase):
    def test_only_standard_library_imports(self):
        import ast
        import sys

        with open(__file__, encoding="utf-8") as fh:
            source = fh.read()
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
