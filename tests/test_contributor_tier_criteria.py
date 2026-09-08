"""Tests for task0003 (muse-spark-contributor-consent): the written,
pre-dispatch criteria a dispatching LLM applies before using the
`muse-spark-contributor` tier as the contributor-tier reading of a plain
`muse-spark` chain entry, while every perspective's primary/cross_validation
chain stays byte-identical.

Covers task0003 Acceptance Criteria
(feature-docs/muse-spark-contributor-consent/tasks/task0003.md):

- AC-1: each of the four documents states the consent precondition and the
  two-check read-mapping rule, naming the mechanical check (the consent
  store) and the per-dispatch judgment (the dispatching LLM) as distinct
  checks.
- AC-2: each plugin's review-phase.md records the exception to the
  model-substitution prohibition, points it at the read-mapping rule, and
  states the judgment is made before dispatch.
- AC-3: in each of the four documents the single per-dispatch "do not use"
  item and the three out-of-scope conditions appear under two distinct
  headings with exactly one and exactly three bullets, never merged and
  never interleaved.
- AC-4: the visibility/license condition is a present-state check at
  dispatch time, never a comparison against a value recorded at consent
  time.
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

HEADING_DO_NOT_USE_MD = "**Per-dispatch: do not use**"
HEADING_OUTSIDE_SCOPE_MD = "**Outside the scope of consent**"
HEADING_DO_NOT_USE_YAML = "# Per-dispatch: do not use"
HEADING_OUTSIDE_SCOPE_YAML = "# Outside the scope of consent"

# The exception sentence's fixed opening, used both as a presence check and
# as an anchor for the before/after ordering check against the
# substitution-prohibition clause it sits next to.
EXCEPTION_ANCHOR = "Exception to the prohibition above"
SUBSTITUTION_PROHIBITION = "never substitute a model of your own choosing"

# Forbidden comparison-against-recorded-value phrasing (AC-4 negative half).
# The consent store holds only `updated_at`; a comparison against "when
# consent was given/recorded" would be unimplementable as well as wrong.
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


def extract_markdown_bullets(text, heading):
    """Return the top-level `- ...` bullet texts introduced by `heading`.
    The bullet block is bounded structurally, not by a caller-supplied stop
    marker: it starts at the first `- ` line after `heading` (skipping any
    blank lines in between) and ends at the first blank line reached once
    at least one bullet has been collected -- which is where a markdown
    list always ends. Continuation lines (wrapped bullet text that does not
    start a new `- `) are folded into the preceding bullet, not counted."""
    lines = text[text.index(heading) + len(heading):].splitlines()
    bullets = []
    for line in lines:
        stripped = line.strip()
        if stripped == "":
            if bullets:
                break
            continue
        if stripped.startswith("- "):
            bullets.append(stripped[2:].strip())
        # else: either pre-list text (bullets still empty) or a
        # continuation line of the current bullet -- neither counted.
    return bullets


def extract_yaml_comment_bullets(text, heading):
    """Same shape as `extract_markdown_bullets`, but for a YAML comment
    block: bullets are comment lines whose content (after stripping the
    leading `#`) starts with `- `. The block ends at the first line that
    is not a `#` comment at all (falling out of the header into YAML data)
    or at the first blank comment line reached once at least one bullet has
    been collected."""
    lines = text[text.index(heading) + len(heading):].splitlines()
    bullets = []
    for raw in lines:
        stripped = raw.strip()
        # The heading's own line leaves an empty leftover entry (the slice
        # starts right after the heading text, before its newline) --
        # treat any blank line as blank BEFORE checking the `#` prefix, or
        # that leftover would wrongly look like "fell out of the comment
        # block" and end extraction before it starts.
        if stripped == "":
            if bullets:
                break
            continue
        if not stripped.startswith("#"):
            break
        content = stripped[1:].strip()
        if content == "":
            # A lone `#` line: a blank line WITHIN the comment block. Ends
            # the bullet list the same way a truly blank line does.
            if bullets:
                break
            continue
        if content.startswith("- "):
            bullets.append(content[2:].strip())
        # else: pre-list comment text or a continuation line -- not counted.
    return bullets


# ---------------------------------------------------------------------------
# AC-1: the consent precondition and the two-check read-mapping rule.
# ---------------------------------------------------------------------------


class TestAC1ReadMappingRulePresentInAllFourDocuments(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.norm = {name: _norm(_read(path)) for name, path in ALL_FOUR_DOCS.items()}
        cls.norm_lower = {name: t.lower() for name, t in cls.norm.items()}

    def test_states_muse_spark_selected_entry_trigger(self):
        # Case-insensitive: this clause opens a fresh sentence in the
        # markdown documents ("When `muse-spark` is...") but continues a
        # colon-introduced sentence in the YAML comment documents ("...
        # read-mapping): when `muse-spark` is..."); the casing difference
        # is not semantically meaningful.
        for name, t in self.norm_lower.items():
            with self.subTest(doc=name):
                self.assertIn(
                    "when `muse-spark` is the chain entry the registry "
                    "selected, reading it as the contributor tier is "
                    "permitted only after two checks both pass",
                    t,
                )

    def test_names_mechanical_check_distinctly(self):
        for name, t in self.norm.items():
            with self.subTest(doc=name):
                self.assertIn("consent for this project is recorded", t)
                self.assertIn("decided by the consent store", t)

    def test_names_per_dispatch_judgment_distinctly(self):
        for name, t in self.norm_lower.items():
            with self.subTest(doc=name):
                self.assertIn("this particular dispatch may use it", t)
                self.assertIn(
                    "a per-dispatch judgment made by the dispatching llm", t
                )

    def test_states_chain_never_edited_and_single_reading(self):
        for name, t in self.norm.items():
            with self.subTest(doc=name):
                self.assertIn(
                    "is never edited to reach the contributor tier", t
                )
                self.assertIn("exactly one permitted reading", t)

    def test_mechanical_and_per_dispatch_checks_are_textually_distinct(self):
        # Non-vacuity: the two check phrases are not the same substring, so
        # the presence assertions above are not trivially satisfied by one
        # sentence doing double duty.
        for name, t in self.norm.items():
            with self.subTest(doc=name):
                mech = "consent for this project is recorded"
                per_dispatch = "this particular dispatch may use it"
                self.assertNotEqual(mech, per_dispatch)
                self.assertIn(mech, t)
                self.assertIn(per_dispatch, t)


# ---------------------------------------------------------------------------
# AC-2: the substitution-prohibition exception, in both review-phase.md
# documents only.
# ---------------------------------------------------------------------------


class TestAC2SubstitutionExceptionInReviewPhaseDocs(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = {name: _read(path) for name, path in REVIEW_PHASE_DOCS.items()}
        cls.norm = {name: _norm(t) for name, t in cls.text.items()}

    def test_exception_recorded_next_to_prohibition(self):
        for name, t in self.text.items():
            with self.subTest(doc=name):
                self.assertIn(SUBSTITUTION_PROHIBITION, t)
                self.assertIn(EXCEPTION_ANCHOR, t)
                # The exception must read as qualifying the prohibition
                # clause it sits next to, not as an unrelated passage
                # elsewhere in the document.
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
                    "contributor-tier pre-dispatch criteria".lower(),
                    t.lower(),
                )

    def test_exception_states_single_permitted_reading_not_free_choice(self):
        for name, t in self.norm.items():
            with self.subTest(doc=name):
                self.assertIn("never a free choice of model", t)

    def test_exception_states_judgment_made_before_dispatch(self):
        for name, t in self.norm.items():
            with self.subTest(doc=name):
                lowered = t.lower()
                self.assertIn("before this dispatch step is reached", lowered)
                self.assertIn("never decided inside the reviewer", lowered)
                self.assertIn(
                    "never after a hop has already been spent", lowered
                )


# ---------------------------------------------------------------------------
# AC-3: one-versus-three structure, all four documents.
# ---------------------------------------------------------------------------


class TestAC3OneVersusThreeStructure(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = {name: _read(path) for name, path in ALL_FOUR_DOCS.items()}

    def _bullets(self, name, text):
        if name.endswith("reviewers.yaml"):
            do_not_use = extract_yaml_comment_bullets(text, HEADING_DO_NOT_USE_YAML)
            outside_scope = extract_yaml_comment_bullets(
                text, HEADING_OUTSIDE_SCOPE_YAML
            )
        else:
            do_not_use = extract_markdown_bullets(text, HEADING_DO_NOT_USE_MD)
            outside_scope = extract_markdown_bullets(text, HEADING_OUTSIDE_SCOPE_MD)
        return do_not_use, outside_scope

    def test_headings_are_distinct_and_ordered(self):
        for name, text in self.text.items():
            with self.subTest(doc=name):
                if name.endswith("reviewers.yaml"):
                    first, second = HEADING_DO_NOT_USE_YAML, HEADING_OUTSIDE_SCOPE_YAML
                else:
                    first, second = HEADING_DO_NOT_USE_MD, HEADING_OUTSIDE_SCOPE_MD
                self.assertNotEqual(first, second)
                self.assertLess(text.index(first), text.index(second))

    def test_exactly_one_do_not_use_bullet(self):
        for name, text in self.text.items():
            with self.subTest(doc=name):
                do_not_use, _ = self._bullets(name, text)
                self.assertEqual(
                    len(do_not_use),
                    1,
                    f"{name}: expected exactly 1 bullet, got {do_not_use}",
                )

    def test_exactly_three_outside_scope_bullets(self):
        for name, text in self.text.items():
            with self.subTest(doc=name):
                _, outside_scope = self._bullets(name, text)
                self.assertEqual(
                    len(outside_scope),
                    3,
                    f"{name}: expected exactly 3 bullets, got {outside_scope}",
                )

    def test_never_merged_or_interleaved(self):
        # The single do-not-use bullet must not itself be one of the three
        # out-of-scope bullets, and vice versa -- proven by disjointness of
        # the two extracted sets, which the windowed extraction above
        # already enforces structurally; this test asserts that windowing
        # actually excludes the other heading's content rather than
        # silently including it.
        for name, text in self.text.items():
            with self.subTest(doc=name):
                do_not_use, outside_scope = self._bullets(name, text)
                self.assertTrue(
                    set(do_not_use).isdisjoint(set(outside_scope))
                )


# ---------------------------------------------------------------------------
# AC-4: present-state check at dispatch time, never a recorded-value
# comparison.
# ---------------------------------------------------------------------------


class TestAC4PresentStateVisibilityLicenseCheck(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = {name: _read(path) for name, path in ALL_FOUR_DOCS.items()}
        cls.norm_lower = {name: _norm(t).lower() for name, t in cls.text.items()}

    def test_present_state_dispatch_time_phrasing_positive(self):
        for name, t in self.norm_lower.items():
            with self.subTest(doc=name):
                self.assertIn(
                    "if the repository is currently private, or its "
                    "license is not the one the consent was reasonable "
                    "under, do not use the contributor tier",
                    t,
                )

    def test_no_comparison_against_a_recorded_value(self):
        for name, t in self.norm_lower.items():
            for phrase in FORBIDDEN_RECORDED_VALUE_COMPARISONS:
                with self.subTest(doc=name, phrase=phrase):
                    self.assertNotIn(phrase, t)


# ---------------------------------------------------------------------------
# AC-5: chain immutability across both registries.
# ---------------------------------------------------------------------------

# Literal pin of em-review's `cross_validation` chains, taken from the base
# revision (this feature's task0003 never edits a chain). Not recomputed
# from the same file -- a self-referential comparison would pass no matter
# what changed.
EM_REVIEW_EXPECTED_CHAINS = {
    "security": [
        {"harness": "codex"},
        {"harness": "litellm", "model": "muse-spark"},
    ],
    "performance": [
        {"harness": "litellm", "model": "muse-spark"},
        {"harness": "litellm", "model": "vertex-glm-5.2"},
        {"harness": "codex"},
    ],
    "architecture": [
        {"harness": "litellm", "model": "vertex-glm-5.2"},
        {"harness": "litellm", "model": "muse-spark"},
        {"harness": "codex"},
    ],
    "spec": [
        {"harness": "litellm", "model": "muse-spark"},
        {"harness": "litellm", "model": "vertex-glm-5.2"},
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
