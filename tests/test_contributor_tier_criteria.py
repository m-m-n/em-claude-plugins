"""Tests for the contributor-tier read-mapping: a plain `muse-spark` chain
entry is dispatched as `muse-spark-contributor` exactly when consent for
the project is recorded in the consent store, with no other condition,
while every perspective's primary/cross_validation chain stays
byte-identical.

- Consent-only rule: each of the four documents states that recorded
  consent is the only condition and that no per-dispatch judgment is added.
- Removed conditions: none of the four documents carries the former
  per-dispatch "do not use" item or the "outside the scope of consent"
  conditions (secrets, third-party work, private repository / license).
- Mechanical check: each review-phase.md probes `contributor_consented` in
  Phase R0 with `muse_guard.py --list`, and the R2 exception defers to that
  value; each registry names the same command.
- No comparison against a value recorded at consent time.
- AC-5: every perspective's chain in both registries stays byte-identical
  to the base revision (literal pin, not recomputed from the same file);
  every chain stays non-empty; no chain entry names the contributor tier;
  the em-workflow registry still contains no `cross_validation` literal.

Per Test Notes: standard library only, hand-rolled restricted parsing
(no PyYAML), the same convention tests/test_reviewers_primary_chains.py
uses. That module already pins em-workflow's `primary_chain` values
literally, so this module does not repeat that pin -- it adds the literal
pin for em-review's `cross_validation` values (AC-5's "both registries"),
which no existing test module covers.
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

EM_WORKFLOW_REVIEWERS = os.path.join(
    REPO_ROOT, "em-workflow", "references", "reviewers.yaml"
)
EM_REVIEW_REVIEWERS = os.path.join(
    REPO_ROOT, "em-review", "references", "reviewers.yaml"
)
EM_WORKFLOW_REVIEW_PHASE = os.path.join(
    REPO_ROOT, "em-workflow", "references", "review-phase.md"
)
EM_REVIEW_REVIEW_PHASE = os.path.join(
    REPO_ROOT, "em-review", "references", "review-phase.md"
)

ALL_FOUR_DOCS = {
    "em-workflow/reviewers.yaml": EM_WORKFLOW_REVIEWERS,
    "em-review/reviewers.yaml": EM_REVIEW_REVIEWERS,
    "em-workflow/review-phase.md": EM_WORKFLOW_REVIEW_PHASE,
    "em-review/review-phase.md": EM_REVIEW_REVIEW_PHASE,
}

REVIEW_PHASE_DOCS = {
    "em-workflow/review-phase.md": EM_WORKFLOW_REVIEW_PHASE,
    "em-review/review-phase.md": EM_REVIEW_REVIEW_PHASE,
}

REGISTRY_DOCS = {
    "em-workflow/reviewers.yaml": EM_WORKFLOW_REVIEWERS,
    "em-review/reviewers.yaml": EM_REVIEW_REVIEWERS,
}

CONSENT_CHECK_COMMAND = (
    'python3 "${CLAUDE_PLUGIN_ROOT}/hooks/muse_guard.py" --list '
    '--project-dir "{project_root}"'
)

# The exception sentence's fixed opening, used both as a presence check and
# as an anchor for the before/after ordering check against the
# substitution-prohibition clause it sits next to.
EXCEPTION_ANCHOR = "Exception to the prohibition above"
SUBSTITUTION_PROHIBITION = "never substitute a model of your own choosing"

# Conditions that no longer gate the contributor tier. Lower-cased,
# matched against whitespace-normalized text.
REMOVED_CONDITION_PHRASES = [
    "per-dispatch: do not use",
    "outside the scope of consent",
    "unpublished idea",
    "secrets present in the diff",
    "third-party work",
    "currently private",
    "the consent was reasonable under",
    "two checks both pass",
    "a per-dispatch judgment made by the dispatching llm",
]

# Forbidden comparison-against-recorded-value phrasing. The consent store
# holds only `updated_at`; a comparison against "when consent was
# given/recorded" would be unimplementable.
FORBIDDEN_RECORDED_VALUE_COMPARISONS = [
    "when consent was given",
    "when consent was recorded",
    "since consent was given",
    "since consent was recorded",
    "at the time consent was",
    "compared to when consent",
    "updated_at",
]


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _norm(text):
    """Strip a leading comment marker (`#`, one optional following space)
    from every line, then collapse all whitespace runs to a single space.
    A no-op on lines that do not start with `#` (ordinary markdown prose),
    so this one function is reused for both the YAML-comment documents and
    the markdown documents -- matching
    tests/test_reviewers_primary_chains.py's `norm_yaml_comment_block`
    convention, generalized to plain text too."""
    lines = [re.sub(r"^#\s?", "", line) for line in text.splitlines()]
    return re.sub(r"\s+", " ", " ".join(lines)).strip()


# ---------------------------------------------------------------------------
# Consent-only rule, all four documents.
# ---------------------------------------------------------------------------


class TestConsentOnlyRuleInAllFourDocuments(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.norm_lower = {
            name: _norm(_read(path)).lower() for name, path in ALL_FOUR_DOCS.items()
        }

    def test_states_muse_spark_selected_entry_trigger(self):
        for name, t in self.norm_lower.items():
            with self.subTest(doc=name):
                self.assertIn(
                    "when `muse-spark` is the chain entry the registry "
                    "selected, dispatch it as the contributor tier",
                    t,
                )

    def test_consent_is_the_only_condition(self):
        for name, t in self.norm_lower.items():
            with self.subTest(doc=name):
                self.assertIn("recorded consent is the only condition", t)
                self.assertIn(
                    "no per-dispatch judgment is added on top of it", t
                )

    def test_falls_back_to_standard_tier_without_consent(self):
        for name, t in self.norm_lower.items():
            with self.subTest(doc=name):
                self.assertIn("and as `muse-spark` otherwise", t)

    def test_states_chain_never_edited_and_single_reading(self):
        for name, t in self.norm_lower.items():
            with self.subTest(doc=name):
                self.assertIn(
                    "is never edited to reach the contributor tier", t
                )
                self.assertIn("exactly one permitted reading", t)

    def test_removed_conditions_are_absent(self):
        for name, t in self.norm_lower.items():
            for phrase in REMOVED_CONDITION_PHRASES:
                with self.subTest(doc=name, phrase=phrase):
                    self.assertNotIn(phrase, t)

    def test_no_comparison_against_a_recorded_value(self):
        for name, t in self.norm_lower.items():
            for phrase in FORBIDDEN_RECORDED_VALUE_COMPARISONS:
                with self.subTest(doc=name, phrase=phrase):
                    self.assertNotIn(phrase, t)


# ---------------------------------------------------------------------------
# Mechanical consent check.
# ---------------------------------------------------------------------------


class TestMechanicalConsentCheck(unittest.TestCase):
    def test_review_phase_probes_consent_in_r0(self):
        for name, path in REVIEW_PHASE_DOCS.items():
            text = _read(path)
            with self.subTest(doc=name):
                r0 = text[text.index("## Phase R0"):text.index("## Phase R1")]
                self.assertIn("`contributor_consented`", r0)
                self.assertIn(CONSENT_CHECK_COMMAND, r0)

    def test_registry_names_the_consent_command(self):
        for name, path in REGISTRY_DOCS.items():
            with self.subTest(doc=name):
                self.assertIn(CONSENT_CHECK_COMMAND, _read(path))

    def test_criteria_defer_to_the_r0_probe(self):
        for name, path in REVIEW_PHASE_DOCS.items():
            t = _norm(_read(path))
            with self.subTest(doc=name):
                self.assertIn(
                    "exactly when `contributor_consented` (Phase R0) is true", t
                )


# ---------------------------------------------------------------------------
# The substitution-prohibition exception, in both review-phase.md
# documents only.
# ---------------------------------------------------------------------------


class TestSubstitutionExceptionInReviewPhaseDocs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = {name: _read(path) for name, path in REVIEW_PHASE_DOCS.items()}
        cls.norm = {name: _norm(t) for name, t in cls.text.items()}

    def test_exception_recorded_next_to_prohibition(self):
        for name, t in self.text.items():
            with self.subTest(doc=name):
                self.assertIn(SUBSTITUTION_PROHIBITION, t)
                self.assertIn(EXCEPTION_ANCHOR, t)
                prohibition_idx = t.index(SUBSTITUTION_PROHIBITION)
                exception_idx = t.index(EXCEPTION_ANCHOR)
                self.assertLess(
                    exception_idx - prohibition_idx,
                    600,
                    "exception text is not adjacent to the prohibition clause",
                )

    def test_exception_points_at_read_mapping_rule(self):
        for name, t in self.norm.items():
            with self.subTest(doc=name):
                self.assertIn(
                    "contributor-tier pre-dispatch criteria",
                    t.lower(),
                )

    def test_exception_states_single_permitted_reading_not_free_choice(self):
        for name, t in self.norm.items():
            with self.subTest(doc=name):
                self.assertIn("never a free choice of model", t)

    def test_exception_uses_the_r0_consent_value(self):
        for name, t in self.norm.items():
            with self.subTest(doc=name):
                lowered = t.lower()
                self.assertIn(
                    "only on the `contributor_consented` value phase r0 "
                    "settled before this dispatch step is reached",
                    lowered,
                )
                self.assertIn("never decided inside the reviewer", lowered)
                self.assertIn(
                    "never after a hop has already been spent", lowered
                )


# ---------------------------------------------------------------------------
# AC-5: chain immutability across both registries.
# ---------------------------------------------------------------------------

# Literal pin of em-review's `cross_validation` chains. Not recomputed
# from the same file -- a self-referential comparison would pass no matter
# what changed.
EM_REVIEW_EXPECTED_CHAINS = {
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
    "comprehensive": [],
}


def parse_perspective_chains(text, chain_key):
    """Minimal restricted parser: returns {perspective: [ {harness[,
    model]}, ... ]} for the given literal chain key (`primary_chain` or
    `cross_validation`). Raises ValueError on unexpected structure -- this
    intentionally does not tolerate a shape it was not told to expect,
    matching tests/test_reviewers_primary_chains.py's parser discipline."""
    lines = text.splitlines()
    chains = {}
    in_block = False
    current = None
    in_chain = False
    for raw in lines:
        line = raw.split("#", 1)[0].rstrip()
        if not in_block:
            if line == "perspectives:":
                in_block = True
            continue
        if not line.strip():
            continue
        indent = len(line) - len(line.lstrip(" "))
        stripped = line.strip()
        if indent == 0:
            break
        if indent == 2:
            if not stripped.startswith("- perspective:"):
                raise ValueError(f"expected perspective item: {raw!r}")
            current = stripped[len("- perspective:"):].strip()
            chains[current] = []
            in_chain = False
            continue
        if current is None:
            raise ValueError(f"attribute before perspective: {raw!r}")
        if indent == 4:
            in_chain = False
            key, sep, value = stripped.partition(":")
            key = key.strip()
            value = value.strip()
            if key == chain_key:
                if value == "[]":
                    chains[current] = []
                elif value == "":
                    in_chain = True
                else:
                    raise ValueError(f"unexpected chain value: {raw!r}")
            continue
        if indent == 6:
            if not in_chain:
                raise ValueError(f"chain entry outside chain block: {raw!r}")
            match = re.match(r"^-\s*\{(.*)\}$", stripped)
            if not match:
                raise ValueError(f"malformed chain entry: {raw!r}")
            entry = {}
            body = match.group(1).strip()
            if body:
                for part in body.split(","):
                    k, _, v = part.partition(":")
                    entry[k.strip()] = v.strip()
            chains[current].append(entry)
            continue
        raise ValueError(f"unexpected indentation: {raw!r}")
    return chains


class TestAC5ChainImmutability(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.em_workflow_text = _read(EM_WORKFLOW_REVIEWERS)
        cls.em_review_text = _read(EM_REVIEW_REVIEWERS)

    def test_em_review_chains_match_literal_pin(self):
        # AC-5, "both registries": test_reviewers_primary_chains.py already
        # literally pins em-workflow's `primary_chain`; em-review's
        # `cross_validation` has no existing literal pin, so this is what
        # this module adds.
        chains = parse_perspective_chains(self.em_review_text, "cross_validation")
        self.assertEqual(chains, EM_REVIEW_EXPECTED_CHAINS)

    def test_em_review_every_chain_non_empty_or_deliberately_empty(self):
        # `comprehensive` is deliberately empty by design (Claude-only);
        # every OTHER perspective must be non-empty.
        chains = parse_perspective_chains(self.em_review_text, "cross_validation")
        for name, chain in chains.items():
            if name == "comprehensive":
                continue
            with self.subTest(perspective=name):
                self.assertTrue(chain, f"{name} has an empty cross_validation chain")

    def test_no_chain_entry_names_the_contributor_tier(self):
        for label, text, key in (
            ("em-workflow", self.em_workflow_text, "primary_chain"),
            ("em-review", self.em_review_text, "cross_validation"),
        ):
            with self.subTest(plugin=label):
                chains = parse_perspective_chains(text, key)
                for perspective, chain in chains.items():
                    for entry in chain:
                        with self.subTest(perspective=perspective, entry=entry):
                            self.assertNotIn("contributor", entry.get("model", ""))
                            self.assertNotIn("contributor", entry.get("harness", ""))

    def test_em_workflow_registry_still_has_no_cross_validation_literal(self):
        self.assertNotIn("cross_validation", self.em_workflow_text)


if __name__ == "__main__":
    unittest.main()
