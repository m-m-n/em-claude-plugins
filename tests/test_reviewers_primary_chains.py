"""Tests for em-workflow/references/reviewers.yaml and
em-workflow/references/review-rules.yaml (task0003, llm-led-review).

task0003 turns the reviewer registry into a primary-reviewer registry: every
selected perspective gets ONE non-Claude reviewer chain (`primary_chain`,
replacing the old `cross_validation` key) that the review phase dispatches
from the front of, and the registries' prose stops describing the retired
Claude + cross-model parallel comparison.

- AC-1: `reviewers.yaml` still defines exactly the six current perspectives
  with unchanged `claude_skill` / `requires_spec` values, and no longer
  contains the key `cross_validation`.
- AC-2: every perspective has a non-empty `primary_chain`; each entry is
  either a codex entry with no `model`, or a litellm entry whose `model` is
  one of the litellm model names the header documents.
- AC-3: every perspective's chain is exactly the two-entry chain pinned
  below, in that order.
- AC-4: the `reviewers.yaml` header keeps the responsibility-split statement
  and the verbatim-`model` statement, states that ONE reviewer per selected
  perspective is dispatched from the front of the chain, and contains no
  surviving text about launching a Claude reviewer per perspective, about a
  cross-model reviewer running beside it, or about agreement scoring.
- AC-5: the `reviewers.yaml` header cites references/review-phase.md for the
  no-available-entry Claude fallback and for the retryable chain walk
  without restating either rule's mechanics.
- AC-6: `review-rules.yaml` keeps `baseline`, `rules`, `spec_review` and
  `cross_validation` semantically unchanged, keeps its `domains vocabulary`
  header comment intact, and its header no longer describes a claude +
  cross-model double run.

Per Test Notes: this repository's test code uses the Python standard library
only (no PyYAML) -- the registries are read as text and parsed with a
hand-rolled, restricted-subset parser, the way tests/test_batch_policies.py
reads batch-policies.yaml. Nothing here asserts anything about
references/review-phase.md or the reviewer agents (out of this task's scope,
and not present with this feature's changes in this worktree).
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REVIEWERS_PATH = os.path.join(REPO_ROOT, "em-workflow", "references", "reviewers.yaml")
REVIEW_RULES_PATH = os.path.join(REPO_ROOT, "em-workflow", "references", "review-rules.yaml")

LITELLM_MODEL_NAMES = {"muse-spark"}

# Pinned per IMPLEMENTATION.md Shared Components ("Registry chain key" /
# "Primary chains" rows) and this task's own plan table. `claude_skill` and
# `requires_spec` are the pre-existing values -- AC-1 requires them
# unchanged.
EXPECTED_CLAUDE_SKILLS = {
    "security": "review-security",
    "performance": "review-performance",
    "architecture": "review-architecture",
    "spec": "review-spec",
    "comprehensive": "review-comprehensive",
    "license": "review-license",
}

EXPECTED_REQUIRES_SPEC = {
    "security": "false",
    "performance": "false",
    "architecture": "false",
    "spec": "true",
    "comprehensive": "false",
    "license": "false",
}

# Every chain is two entries -- codex and muse-spark -- differing only in
# which one leads. No Vertex model is assigned any more.
EXPECTED_CHAINS = {
    "security": [
        {"harness": "codex"},
        {"harness": "litellm", "model": "muse-spark"},
    ],
    "performance": [
        {"harness": "litellm", "model": "muse-spark"},
        {"harness": "codex"},
    ],
    "architecture": [
        {"harness": "litellm", "model": "muse-spark"},
        {"harness": "codex"},
    ],
    "spec": [
        {"harness": "litellm", "model": "muse-spark"},
        {"harness": "codex"},
    ],
    "comprehensive": [
        {"harness": "codex"},
        {"harness": "litellm", "model": "muse-spark"},
    ],
    "license": [
        {"harness": "codex"},
        {"harness": "litellm", "model": "muse-spark"},
    ],
}


def parse_reviewers_yaml(text):
    """Restricted-subset parser for reviewers.yaml's `perspectives:` list
    (module docstring: hand-rolled, no PyYAML). Returns a list of
    per-perspective dicts carrying `perspective`, `claude_skill`,
    `requires_spec`, `chain_key` (the literal YAML key introducing the
    ordered chain -- `primary_chain` post-migration, `cross_validation`
    pre-migration, so this parser reads either shape without raising) and
    `chain` (list of {harness[, model]} dicts, possibly empty).

    Raises ValueError if no top-level `perspectives:` key is found or a line
    inside the block violates the expected nesting -- this is what backs a
    "parses as expected" assertion without needing PyYAML.
    """
    lines = text.splitlines()
    perspectives = []
    in_block = False
    saw_block = False
    current = None
    in_chain = False

    CHAIN_KEYS = ("primary_chain", "cross_validation")

    for raw in lines:
        line = raw.split("#", 1)[0].rstrip()
        if not in_block:
            if line == "perspectives:":
                in_block = True
                saw_block = True
            continue
        if not line.strip():
            continue

        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()

        if indent == 0:
            break  # dedent back to column 0: the perspectives block ended

        if indent == 2:
            if not stripped.startswith("- perspective:"):
                raise ValueError(f"expected a perspective list item, got: {raw!r}")
            current = {
                "perspective": stripped[len("- perspective:"):].strip(),
                "claude_skill": None,
                "requires_spec": None,
                "chain_key": None,
                "chain": [],
            }
            perspectives.append(current)
            in_chain = False
            continue

        if current is None:
            raise ValueError(f"attribute line before any perspective: {raw!r}")

        if indent == 4:
            in_chain = False
            key, sep, value = stripped.partition(":")
            key = key.strip()
            value = value.strip()
            if not sep:
                raise ValueError(f"unexpected line in perspective block: {raw!r}")
            if key in CHAIN_KEYS:
                current["chain_key"] = key
                if value == "[]":
                    current["chain"] = []
                elif value == "":
                    in_chain = True
                else:
                    raise ValueError(f"unexpected chain-key value: {raw!r}")
                continue
            current[key] = value
        elif indent == 6:
            if not in_chain:
                raise ValueError(f"chain entry outside a chain block: {raw!r}")
            match = re.match(r"^-\s*\{(.*)\}$", stripped)
            if not match:
                raise ValueError(f"malformed chain entry: {raw!r}")
            entry = {}
            body = match.group(1).strip()
            if body:
                for part in body.split(","):
                    k, _, v = part.partition(":")
                    entry[k.strip()] = v.strip()
            current["chain"].append(entry)
        else:
            raise ValueError(f"unexpected indentation: {raw!r}")

    if not saw_block:
        raise ValueError("no top-level `perspectives:` key found")
    return perspectives


def norm_yaml_comment_block(block):
    """Strip the leading `# ` marker per line, then collapse whitespace --
    matches tests/test_batch_policies.py's `_norm_yaml_comment_header`, so a
    sentence wrapped across several comment lines is still one contiguous,
    matchable phrase."""
    stripped_lines = [re.sub(r"^#\s?", "", line) for line in block.splitlines()]
    return re.sub(r"\s+", " ", " ".join(stripped_lines)).strip()


class TestReviewersYamlPerspectiveStructure(unittest.TestCase):
    """AC-1, AC-2, AC-3: the structured per-perspective facts."""

    @classmethod
    def setUpClass(cls):
        with open(REVIEWERS_PATH, encoding="utf-8") as fh:
            cls.text = fh.read()
        cls.perspectives = parse_reviewers_yaml(cls.text)
        cls.by_name = {p["perspective"]: p for p in cls.perspectives}

    def test_parses_without_error(self):
        self.assertIsInstance(self.perspectives, list)
        self.assertGreater(len(self.perspectives), 0)

    def test_exactly_six_expected_perspectives(self):
        # AC-1: exactly the six current perspectives, no more, no fewer.
        self.assertEqual(set(self.by_name.keys()), set(EXPECTED_CLAUDE_SKILLS.keys()))

    def test_claude_skill_and_requires_spec_unchanged(self):
        # AC-1
        for name, expected_skill in EXPECTED_CLAUDE_SKILLS.items():
            with self.subTest(perspective=name):
                p = self.by_name[name]
                self.assertEqual(p["claude_skill"], expected_skill)
                self.assertEqual(p["requires_spec"], EXPECTED_REQUIRES_SPEC[name])

    def test_chain_key_is_primary_chain_for_every_perspective(self):
        # AC-1: the per-perspective key is `primary_chain`, not
        # `cross_validation`.
        for name, p in self.by_name.items():
            with self.subTest(perspective=name):
                self.assertEqual(p["chain_key"], "primary_chain")

    def test_cross_validation_key_absent_from_whole_file(self):
        # AC-1, belt-and-suspenders over the whole file text (not just the
        # parsed structure): the string never appears at all.
        self.assertNotIn("cross_validation", self.text)

    def test_every_chain_non_empty(self):
        # AC-2: an empty chain is no longer a legal registry state.
        for name, p in self.by_name.items():
            with self.subTest(perspective=name):
                self.assertTrue(p["chain"], f"{name} has an empty primary_chain")

    def test_chain_entries_well_formed(self):
        # AC-2: each entry is a codex entry with no model, or a litellm
        # entry whose model is one of the documented litellm model names.
        for name, p in self.by_name.items():
            for entry in p["chain"]:
                with self.subTest(perspective=name, entry=entry):
                    self.assertIn(entry.get("harness"), ("codex", "litellm"))
                    if entry["harness"] == "codex":
                        self.assertNotIn("model", entry)
                    else:
                        self.assertIn("model", entry)
                        self.assertIn(entry["model"], LITELLM_MODEL_NAMES)

    def test_chains_match_pinned_contract(self):
        # AC-3: comprehensive and license get exactly the new three-entry
        # chains, and the four pre-existing chains are unchanged in order
        # and content.
        for name, expected_chain in EXPECTED_CHAINS.items():
            with self.subTest(perspective=name):
                self.assertEqual(self.by_name[name]["chain"], expected_chain)


class TestReviewersYamlHeaderProse(unittest.TestCase):
    """AC-4, AC-5: the header comment block."""

    @classmethod
    def setUpClass(cls):
        with open(REVIEWERS_PATH, encoding="utf-8") as fh:
            cls.text = fh.read()
        # Everything before the `version:` line is the header comment block.
        cls.header = cls.text.split("\nversion:", 1)[0]
        cls.norm = norm_yaml_comment_block(cls.header)
        cls.norm_lower = cls.norm.lower()

    def test_keeps_responsibility_split_statement(self):
        self.assertIn("the harness plugin owns which models exist", self.norm_lower)
        self.assertIn(
            "this registry owns which model each perspective gets", self.norm_lower
        )

    def test_keeps_verbatim_model_statement(self):
        self.assertIn("handed to the reviewer verbatim", self.norm)

    def test_lists_valid_litellm_model_names(self):
        for name in LITELLM_MODEL_NAMES:
            self.assertIn(name, self.header)

    def test_states_one_reviewer_dispatched_from_chain_front(self):
        # AC-4: ONE reviewer per selected perspective, from the front of the
        # chain.
        self.assertIn("dispatches exactly one reviewer", self.norm_lower)
        self.assertIn("front of that perspective's `primary_chain`", self.norm)

    def test_cites_review_phase_for_fallback_and_chain_walk(self):
        # AC-5
        self.assertIn("references/review-phase.md", self.norm)
        self.assertIn("claude-reviewer fallback", self.norm_lower)
        self.assertIn("no chain entry is available", self.norm_lower)
        self.assertIn("retryable chain walk", self.norm_lower)

    def test_does_not_restate_chain_walk_mechanics(self):
        # AC-5: cites the retryable chain walk, never restates its per-skip
        # advance semantics (owned by review-phase.md Phase R2b).
        for leaked_term in ("rate_limited", "budget_exhausted", "harness_unavailable"):
            with self.subTest(term=leaked_term):
                self.assertNotIn(leaked_term, self.header)

    def test_no_surviving_claude_per_perspective_launch_text(self):
        # AC-4
        self.assertNotIn("claude generic reviewer agent", self.norm_lower)
        self.assertNotIn("em-workflow:reviewer", self.header)

    def test_no_surviving_cross_model_beside_text(self):
        # AC-4
        self.assertNotIn("cross-model reviewer", self.norm_lower)
        self.assertNotIn("cross_validation", self.header)

    def test_no_surviving_agreement_scoring_text(self):
        # AC-4
        self.assertNotIn("agreement scoring", self.norm_lower)

    def test_non_vacuity_of_stale_phrase_checks(self):
        # Proves the assertions above are meaningful: a synthetic string
        # carrying the retired phrases really does trip them.
        synthetic_lower = (
            self.norm_lower
            + " em-workflow uses a claude generic reviewer agent "
            "(em-workflow:reviewer) plus one cross-model reviewer per "
            "harness, scored for agreement scoring."
        )
        self.assertIn("claude generic reviewer agent", synthetic_lower)
        self.assertIn("cross-model reviewer", synthetic_lower)
        self.assertIn("agreement scoring", synthetic_lower)


# review-rules.yaml matchers (task0005, repo-suite-pinned-test-drift).
#
# Matcher / loader separation (IMPLEMENTATION.md Conventions): each matcher
# below takes already-loaded text (or a block already sliced out of it) and
# returns True/False. The live tests in TestReviewRulesDataUnchanged /
# TestReviewRulesHeaderProse load review-rules.yaml's real text and pass it
# in; TestReviewRulesMatchersRejectForgedInput passes forged in-memory text
# built with the same textual shape (module docstring: no YAML library, so
# extraction is `str.index` slicing, and forged input keeps the surrounding
# markers that slicing depends on -- Test Notes, task0005 plan).

CURRENT_BASELINE_LINE = "baseline: [comprehensive, security]"

CURRENT_RULES_BLOCK = (
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

CURRENT_WHEN_ANY_BLOCK = (
    "cross_validation:\n"
    "  when_any:\n"
    "    - complexity: high"
)

CURRENT_COMPUTATION_PHRASE = "Layer 1 settles the value and Layer 2 cannot change it"


def baseline_matches_current(text):
    """AC-1 matcher: True iff the current baseline line (exactly
    [comprehensive, security]) appears verbatim in `text`."""
    return CURRENT_BASELINE_LINE in text


def extract_rules_block(text):
    """Loader: slice the `rules:` block out of `text`, from the `rules:`
    line up to (not including) the blank line before `spec_review:`."""
    start = text.index("rules:\n")
    end = text.index("\n\nspec_review:", start)
    return text[start:end]


def rules_block_matches_current(block):
    """AC-2 matcher: True iff `block` equals the current four-rule contract
    exactly, in content and order."""
    return block == CURRENT_RULES_BLOCK


def extract_when_any_block(text):
    """Loader: slice the `cross_validation:` block out of `text`, from its
    start to the end of `text` (it is the file's last block)."""
    start = text.index("cross_validation:\n  when_any:")
    return text[start:].rstrip("\n")


def when_any_matches_current(block):
    """AC-3 matcher: True iff `block` equals the current single-condition
    when_any (complexity: high only) exactly."""
    return block == CURRENT_WHEN_ANY_BLOCK


def prose_has_current_computation_phrase(text):
    """AC-4 matcher: True iff the current computation-semantics phrase is
    present in `text` after normalization (norm_yaml_comment_block),
    tolerant of the phrase wrapping across comment lines (D4)."""
    return CURRENT_COMPUTATION_PHRASE in norm_yaml_comment_block(text)


class TestReviewRulesDataUnchanged(unittest.TestCase):
    """AC-6, data half: baseline / rules / spec_review / cross_validation
    match review-rules.yaml's current definitions; the domains vocabulary
    comment block stays intact.

    task0005: baseline, rules and cross_validation.when_any are checked
    against the file's current values -- baseline: [comprehensive,
    security], the four current rules in file order, and when_any holding
    only complexity: high -- each via a matcher/loader pair above, which
    also backs the forged-input negative proofs in
    TestReviewRulesMatchersRejectForgedInput.
    """

    @classmethod
    def setUpClass(cls):
        with open(REVIEW_RULES_PATH, encoding="utf-8") as fh:
            cls.text = fh.read()

    def test_baseline_unchanged(self):
        # AC-1: baseline is exactly [comprehensive, security].
        self.assertTrue(
            baseline_matches_current(self.text),
            f"expected {CURRENT_BASELINE_LINE!r} in the file text",
        )

    def test_rules_block_unchanged(self):
        # AC-2: exactly the four current rules, in content and in order.
        block = extract_rules_block(self.text)
        self.assertTrue(
            rules_block_matches_current(block),
            f"rules block did not match the current contract:\n{block}",
        )

    def test_spec_review_unchanged(self):
        self.assertIn("spec_review: always", self.text)

    def test_cross_validation_data_block_unchanged(self):
        # AC-3: when_any holds exactly one condition: complexity high.
        block = extract_when_any_block(self.text)
        self.assertTrue(
            when_any_matches_current(block),
            f"cross_validation block did not match the current contract:\n{block}",
        )

    def test_domains_vocabulary_header_intact(self):
        expected_lines = [
            "# domains vocabulary (fixed, 8 values — planner assigns from these only):",
            "#   auth / input-handling / data-persistence / external-io / concurrency /",
            "#   api-contract / ui / config-infra",
            "# complexity vocabulary: low / medium / high",
        ]
        for line in expected_lines:
            with self.subTest(line=line):
                self.assertIn(line, self.text)


class TestReviewRulesHeaderProse(unittest.TestCase):
    """AC-6, prose half: the header no longer describes a claude +
    cross-model double run.

    task0005: test_computation_semantics_preserved_in_prose requires the
    current phrase "Layer 1 settles the value and Layer 2 cannot change
    it" (tolerant of its comment-line wrap after "cannot"), and no longer
    requires the retired "re-evaluates it after Layer 2" wording.
    """

    @classmethod
    def setUpClass(cls):
        with open(REVIEW_RULES_PATH, encoding="utf-8") as fh:
            cls.text = fh.read()
        # Everything before the `baseline:` line is the header comment
        # block.
        cls.header = cls.text.split("\nbaseline:", 1)[0]
        cls.norm = norm_yaml_comment_block(cls.header)
        cls.norm_lower = cls.norm.lower()

    def test_no_longer_describes_claude_plus_cross_model_double_run(self):
        self.assertNotIn("claude + that entry's model", self.norm_lower)
        self.assertNotIn("double-run", self.norm_lower)
        self.assertNotIn("agreement scoring", self.norm_lower)

    def test_states_no_second_dispatch_because_primary_reviewer_runs(self):
        self.assertIn("no longer adds a second reviewer dispatch", self.norm_lower)
        self.assertIn("already runs a non-claude primary reviewer", self.norm_lower)

    def test_computation_semantics_preserved_in_prose(self):
        # D2: the flag stays computed exactly as before -- only its
        # consequence changed.
        self.assertIn(
            "fires when ANY task has complexity: high", self.norm
        )
        # task0005 AC-4: the current phrase replaces the retired
        # "re-evaluates it after Layer 2" wording; tolerant of the phrase's
        # comment-line wrap (D4).
        self.assertTrue(
            prose_has_current_computation_phrase(self.header),
            f"expected {CURRENT_COMPUTATION_PHRASE!r} in the normalized header",
        )

    def test_non_vacuity_of_double_run_check(self):
        synthetic_lower = (
            self.norm_lower
            + " double-run (claude + that entry's model) for agreement scoring."
        )
        self.assertIn("double-run", synthetic_lower)
        self.assertIn("claude + that entry's model", synthetic_lower)
        self.assertIn("agreement scoring", synthetic_lower)


class TestReviewRulesMatchersRejectForgedInput(unittest.TestCase):
    """AC-5 (task0005): negative proofs for the four review-rules.yaml
    matchers above. Every case here uses forged in-memory text built with
    the same textual shape review-rules.yaml has (module docstring: no YAML
    library, so extraction is `str.index` slicing) -- nothing is read from
    or written to disk (NFR3, hermetic negative proofs)."""

    # -- baseline (AC-1) -----------------------------------------------

    def test_baseline_rejects_prior_value_without_security(self):
        forged = "baseline: [comprehensive]\n"
        self.assertFalse(baseline_matches_current(forged))

    def test_baseline_rejects_value_lacking_security(self):
        forged = "baseline: [comprehensive, performance]\n"
        self.assertFalse(baseline_matches_current(forged))

    # -- rules (AC-2) ----------------------------------------------------

    def test_rules_block_rejects_prior_five_rule_set(self):
        forged = (
            "rules:\n"
            "  - if_domains: [auth, input-handling]\n"
            "    require: [security]\n"
            "  - if_domains: [data-persistence]\n"
            "    require: [security, performance]\n"
            "  - if_domains: [concurrency, external-io]\n"
            "    require: [performance]\n"
            "  - if_domains: [api-contract]\n"
            "    require: [architecture]\n"
            "  - if_complexity: high\n"
            "    require: [architecture, comprehensive]"
            "\n\nspec_review: always\n"
        )
        block = extract_rules_block(forged)
        self.assertFalse(rules_block_matches_current(block))

    def test_rules_block_rejects_missing_rule(self):
        forged = (
            "rules:\n"
            "  - if_domains: [data-persistence]\n"
            "    require: [performance]\n"
            "  - if_domains: [concurrency, external-io]\n"
            "    require: [performance]\n"
            "  - if_complexity: high\n"
            "    require: [architecture, comprehensive]"
            "\n\nspec_review: always\n"
        )
        block = extract_rules_block(forged)
        self.assertFalse(rules_block_matches_current(block))

    def test_rules_block_rejects_extra_rule(self):
        forged = (
            CURRENT_RULES_BLOCK
            + "\n  - if_domains: [ui]\n"
            "    require: [comprehensive]"
            "\n\nspec_review: always\n"
        )
        block = extract_rules_block(forged)
        self.assertFalse(rules_block_matches_current(block))

    # -- cross_validation.when_any (AC-3) --------------------------------

    def test_when_any_rejects_prior_dual_condition_value(self):
        forged = (
            "cross_validation:\n"
            "  when_any:\n"
            "    - complexity: high\n"
            "    - selected_perspective: security\n"
        )
        block = extract_when_any_block(forged)
        self.assertFalse(when_any_matches_current(block))

    def test_when_any_rejects_condition_other_than_complexity_high(self):
        forged = (
            "cross_validation:\n"
            "  when_any:\n"
            "    - selected_perspective: security\n"
        )
        block = extract_when_any_block(forged)
        self.assertFalse(when_any_matches_current(block))

    # -- computation-semantics prose (AC-4) ------------------------------

    def test_prose_rejects_text_with_only_the_retired_phrase(self):
        forged = (
            "# tasks metadata alone, so Layer 1 re-evaluates it after Layer\n"
            "# 2's discretionary additions.\n"
        )
        self.assertFalse(prose_has_current_computation_phrase(forged))

    def test_prose_accepts_current_phrase_wrapped_at_a_different_word(self):
        # Wraps after "settles" -- a different word than the real file's
        # wrap point (after "cannot") -- and still normalizes to one
        # contiguous phrase.
        forged = (
            "# tasks metadata alone, so Layer 1 settles\n"
            "# the value and Layer 2 cannot change it. More text follows.\n"
        )
        self.assertTrue(prose_has_current_computation_phrase(forged))

    def test_prose_rejects_current_phrase_with_one_word_altered(self):
        forged = (
            "# tasks metadata alone, so Layer 1 settles the value and\n"
            "# Layer 2 cannot alter it. More text follows.\n"
        )
        self.assertFalse(prose_has_current_computation_phrase(forged))


if __name__ == "__main__":
    unittest.main()
