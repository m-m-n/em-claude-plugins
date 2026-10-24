"""Document assertions for self-write-exclusivity-window/task0001: Rule R1's
"Order" block states the return-time recheck, and R1's "Known limit" block says
which window the recheck covers.

Covers task0001 Acceptance Criteria
(feature-docs/self-write-exclusivity-window/tasks/task0001.md):

- AC-1 (FR1, TM-1): the `**Order.**` block keeps its intro sentence and its four
  numbered steps with their anchors in sequence, and after step 4 states the
  `return-time recheck` as an orchestrator step that runs after the comparison
  and after Layer 5's `Calculation`, and before the phase-state write that
  records the run's `artifacts` and `self_write_set`.
- AC-2 (FR1, FR2, TM-1): the recheck text names the self-write set's paths, the
  current git blob id, mode and kind (file / symlink / absent), the values the
  same run's scope verification observed as the baseline, and states in a
  negated sentence that no raw-byte sha256 is compared.
- AC-3 (FR1, TM-1): the recheck text states that any mismatch, or a recheck
  that cannot run (read failure included), makes the result stale, cites the
  scope verification's stale handling, states that a stale result reaches no
  recording write, and states that an empty self-write set passes with nothing
  to do.
- AC-4 (FR5, TM-2): the `**Known limit.**` block keeps its existing sentence,
  still precedes `## Exclusivity assumption during dispatch`, and adds that a
  change after the scope verification is detected by the `return-time recheck`
  and that the remaining window rests on the exclusivity assumption.
- AC-5 (NFR3, NFR4, NFR5, NFR6): R1's label set is unchanged, every added
  sentence that mentions a digest, a hash or sha256 names the orchestrator or
  is negated, the document carries no `expect_digest` token, and the
  `**Means.**` block still states that the script computes no digest.
- AC-6 (FR8, NFR1, NFR2): this file uses only the standard library and follows
  the `test/README.md` naming rules.

All assertions run on whitespace-normalized text sliced by heading / R1 label;
none depends on line-break positions or compares a whole document. Every probe
has a forged-text control showing that the probe fires on the pre-change text or
on a single-element deletion of the new text. The recheck's wording is pinned
here, not in `tests/test_self_write_digest_docs.py`, which keeps passing
unchanged.

Standard library only.
"""

import ast
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
ENVELOPE_PATH = (
    REPO_ROOT / "em-workflow" / "references" / "contracts" / "worker-envelope.md"
)

R1_LABELS = (
    "Condition",
    "Self-write set",
    "Substitution",
    "Order",
    "Means",
    "Persistence and resume",
    "Known limit",
)

# The four anchors R1's Order has carried since worker-self-write-digest.
ORDER_ANCHORS = (
    "scope verification yields the observed change set",
    "recomputes the current `digest_source`",
    "runs the self-write script",
    "compares the substituted `digest_source`",
)
ORDER_INTRO = (
    "recomputes `input_digest` on a return only after the scope verification "
    "has produced the observed change set"
)
STEP4_STALE_SENTENCE = "A mismatch, or a script exit other than `0`, makes the result stale."
RECHECK_TERM = "return-time recheck"
RECORDING_WRITE_PHRASE = (
    "phase-state write that records the run's `artifacts` and `self_write_set`"
)

KNOWN_LIMIT_EXISTING_SENTENCE = (
    "When the worker and another actor change the same permitted path, the two "
    "changes cannot be told apart and the path joins the self-write set; this "
    "case rests on the exclusivity assumption stated below."
)
EXCLUSIVITY_HEADING = "## Exclusivity assumption during dispatch"

# R1 "Order" and "Known limit" as they read at this feature's base. Forged
# controls: every probe about the new text must fire on these.
OLD_ORDER_BLOCK = """\
**Order.** The orchestrator recomputes `input_digest` on a return only
after the scope verification has produced the observed change set,
because membership needs it. At rule level:

1. The scope verification yields the observed change set (violations are
   handled there).
2. The orchestrator recomputes the current `digest_source` from the
   current state, exactly as at dispatch.
3. The orchestrator runs the self-write script on it.
4. The orchestrator compares the substituted `digest_source`'s digest
   with the dispatch-time `input_digest`. A mismatch, or a script exit
   other than `0`, makes the result stale.
"""

OLD_KNOWN_LIMIT_BLOCK = """\
**Known limit.** When the worker and another actor change the same
permitted path, the two changes cannot be told apart and the path joins
the self-write set; this case rests on the exclusivity assumption stated
below.
"""

# A reference recheck paragraph and Known limit tail. They are the forged-text
# bases for the single-element deletions; the same probes run on the real
# document.
GOOD_RECHECK = """\
When step 4's comparison has not made the result stale and, if
`written_artifacts` is non-empty, Layer 5's `Calculation`
(`references/artifact-digest.md`) has run, the orchestrator runs the
return-time recheck. For each path of the self-write set, the orchestrator
reads the current git blob id (`git hash-object --`), mode and kind (file,
symlink or absent) and compares them with the values the same run's scope
verification observed for that path after the dispatch
(`references/phases/create-spec-phase.md`, "Scope verification"). The
orchestrator compares no raw-byte sha256 here, neither the artifact digest of
`references/artifact-digest.md` nor a `digest_inputs` value. Any mismatch, or
a recheck that cannot run (a read failure included), makes the result stale,
handled as the stale handling of that scope verification states
(`references/phases/create-spec-phase.md`, "Scope verification", "Stale
handling"). An empty self-write set passes with nothing to do. The
return-time recheck runs before the phase-state write that records the run's
`artifacts` and `self_write_set` (for a run whose `written_artifacts` is
empty, the write that records the returned `status` and `self_write_set`),
and that write follows only a passing recheck: a stale result reaches no such
write.
"""
GOOD_ORDER_BLOCK = OLD_ORDER_BLOCK + "\n" + GOOD_RECHECK

GOOD_KNOWN_LIMIT_BLOCK = (
    OLD_KNOWN_LIMIT_BLOCK.rstrip("\n")
    + """
A change made after the scope verification is detected by the return-time
recheck of "Order" above. The remaining window, from that recheck through the
phase-state write that records the run's `artifacts` and `self_write_set`,
rests on the exclusivity assumption, whose interval the section "Exclusivity
assumption during dispatch" below states.
"""
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read(path):
    return path.read_text(encoding="utf-8")


def _normalize_ws(text):
    return re.sub(r"\s+", " ", text).strip()


def _heading_of(line):
    match = re.match(r"^(#{1,6})[ \t]+(.*?)[ \t]*$", line)
    if not match:
        return None
    return len(match.group(1)), match.group(2)


def _section(text, level, title_matches):
    """Raw text of the first level-`level` heading whose title satisfies
    `title_matches`, up to the next heading of the same or a higher level.
    Headings inside fenced code are ignored. AssertionError when absent."""
    collected = []
    in_section = False
    in_fence = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        heading = None if in_fence else _heading_of(line)
        if in_section and heading and heading[0] <= level:
            break
        if not in_section and heading and heading[0] == level and title_matches(heading[1]):
            in_section = True
        if in_section:
            collected.append(line)
    if not in_section:
        raise AssertionError("section heading not found")
    return "\n".join(collected) + "\n"


def _r1_section(text):
    return _section(text, 2, lambda title: title.startswith("Rule R1"))


_LABEL_RE = re.compile(r"^\*\*([A-Z][A-Za-z -]*)\.\*\*", re.M)


def _r1_labels(r1_text):
    """The `**Label.**` block labels of the R1 section, in document order."""
    return [match.group(1) for match in _LABEL_RE.finditer(r1_text)]


def _r1_blocks(r1_text):
    """{label: raw block text}. A block runs from its `**Label.**` line to the
    next label, or to the `(Provenance:` paragraph, or to the end of the
    section. AssertionError unless every label of R1_LABELS appears exactly
    once."""
    matches = list(_LABEL_RE.finditer(r1_text))
    found = [match.group(1) for match in matches]
    for label in R1_LABELS:
        if found.count(label) != 1:
            raise AssertionError(
                f"R1 must hold the block label **{label}.** exactly once "
                f"(found {found.count(label)})"
            )
    stop = re.search(r"^\(Provenance:", r1_text, re.M)
    end_of_region = stop.start() if stop else len(r1_text)
    blocks = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else end_of_region
        blocks[match.group(1)] = r1_text[match.start():end]
    return blocks


def _block(envelope_text, label):
    return _normalize_ws(_r1_blocks(_r1_section(envelope_text))[label])


def _recheck_text(order_block):
    """The part of a normalized Order block after step 4's own stale sentence,
    so that step 4's wording can never satisfy a recheck probe. Empty when
    step 4's sentence is absent."""
    index = order_block.find(STEP4_STALE_SENTENCE)
    if index == -1:
        return ""
    return order_block[index + len(STEP4_STALE_SENTENCE):].strip()


def _sentences(text):
    """Sentences of normalized `text`: backticks and bold markers dropped,
    split after sentence-ending punctuation and at semicolons."""
    cleaned = _normalize_ws(text).replace("**", "").replace("`", "")
    parts = re.split(r"(?<=[.!?])[\"')\]]*\s+|[;；]\s*", cleaned)
    return [part.strip() for part in parts if part.strip()]


# The digest-sentence convention of tests/test_self_write_digest_docs.py (which
# loads em-workflow/scripts/check-plugin-invariants.py, a PyYAML importer):
# a sentence that mentions a digest, a hash or sha256 names the orchestrator or
# is negated. This file is standard library only, so it keeps its own copy.
_WORD_BEFORE = r"(?<![A-Za-z0-9_])"
_WORD_AFTER = r"(?![A-Za-z0-9_])"
_DIGEST_TERM_RE = re.compile(
    _WORD_BEFORE
    + r"(?:sha-?256(?:sum)?|expect_digest|digests?|hash(?:es|ed|ing)?)"
    + _WORD_AFTER,
    re.IGNORECASE,
)
_NEGATION_RE = re.compile(
    _WORD_BEFORE
    + r"(?:not|never|no|cannot|without|neither|nor)"
    + _WORD_AFTER
    + r"|n['’]t"
    + _WORD_AFTER,
    re.IGNORECASE,
)
_ORCHESTRATOR_RE = re.compile(r"orchestrator", re.IGNORECASE)


def _digest_sentence_violations(text):
    return [
        sentence
        for sentence in _sentences(text)
        if _DIGEST_TERM_RE.search(sentence)
        and not _ORCHESTRATOR_RE.search(sentence)
        and not _NEGATION_RE.search(sentence)
    ]


def _missing(text, elements):
    """Names of the elements whose pattern does not match `text`."""
    return [name for name, pattern, _old, _new in elements if not re.search(pattern, text)]


def _forge(text, old, new):
    """Whitespace-normalized `text` with the first `old` replaced by `new`
    (both normalized, so line breaks never matter). AssertionError when `old`
    is not in `text`, so a control can never pass vacuously."""
    flat, old_flat, new_flat = _normalize_ws(text), _normalize_ws(old), _normalize_ws(new)
    if old_flat not in flat:
        raise AssertionError(f"forge anchor not found: {old_flat!r}")
    return _normalize_ws(flat.replace(old_flat, new_flat, 1))


# ---------------------------------------------------------------------------
# AC-1: the Order block places the return-time recheck after step 4 and before
# the recording write
# ---------------------------------------------------------------------------


def _order_sequence_problems(order_block):
    """Problems with the position sequence: the four anchors, the recheck term,
    the recording-write phrase must each appear and strictly increase in first
    position."""
    sequence = ORDER_ANCHORS + (RECHECK_TERM, RECORDING_WRITE_PHRASE)
    positions = [order_block.find(item) for item in sequence]
    problems = [f"missing: {item}" for item, pos in zip(sequence, positions) if pos == -1]
    if not problems and not all(a < b for a, b in zip(positions, positions[1:])):
        problems.append(f"out of order: {positions}")
    return problems


def _kept_order_problems(order_block):
    """Problems with the kept part of the Order block: the intro sentence and
    step 4's stale sentence."""
    flat = _normalize_ws(order_block)
    problems = []
    if ORDER_INTRO not in flat:
        problems.append("intro sentence missing")
    if STEP4_STALE_SENTENCE not in flat:
        problems.append("step 4 stale sentence missing")
    return problems


# (name, pattern over the recheck text, anchor in GOOD_RECHECK, forged value)
WHEN_ELEMENTS = (
    (
        "runs after step 4's comparison did not make the result stale",
        r"step 4's comparison has not made the result stale",
        "When step 4's comparison has not made the result stale and, if",
        "When, if",
    ),
    (
        "runs after Layer 5's Calculation when written_artifacts is non-empty",
        r"`written_artifacts` is non-empty, Layer 5's `Calculation`",
        "`written_artifacts` is non-empty, Layer 5's `Calculation`\n(`references/artifact-digest.md`) has run,",
        "`written_artifacts` is non-empty,",
    ),
    (
        "the orchestrator is the actor",
        r"the orchestrator runs the return-time recheck",
        "the orchestrator runs the\nreturn-time recheck.",
        "the\nreturn-time recheck runs.",
    ),
    (
        "runs before the recording phase-state write",
        r"return-time recheck runs before the phase-state write that records the run's "
        r"`artifacts` and `self_write_set`",
        "return-time recheck runs before the phase-state write that records the run's\n`artifacts` and `self_write_set`",
        "return-time recheck is part of the return",
    ),
    (
        "the empty written_artifacts variant names the status write",
        r"`written_artifacts` is empty, the write that records the returned `status` and "
        r"`self_write_set`",
        "(for a run whose `written_artifacts` is\nempty, the write that records the returned `status` and `self_write_set`),\nand that write",
        "and that write",
    ),
    (
        "the recording write follows only a passing recheck",
        r"follows only a passing recheck",
        "follows only a passing recheck:",
        "follows:",
    ),
)


class TestOrderRecheckPlacement(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(ENVELOPE_PATH)
        cls.order = _block(cls.text, "Order")
        cls.recheck = _recheck_text(cls.order)

    def test_ac1_order_block_keeps_its_intro_and_step_4_stale_sentence(self):
        self.assertEqual(_kept_order_problems(self.order), [])

    def test_ac1_four_anchors_then_recheck_term_then_recording_write_phrase_in_sequence(self):
        self.assertEqual(_order_sequence_problems(self.order), [])

    def test_ac1_recheck_text_exists_after_step_4(self):
        self.assertTrue(self.recheck, "no text after step 4's stale sentence")
        self.assertIn(RECHECK_TERM, self.recheck)

    def test_ac1_recheck_text_states_when_it_runs_and_who_runs_it(self):
        self.assertEqual(_missing(self.recheck, WHEN_ELEMENTS), [])

    def test_ac1_calculation_is_mentioned_before_the_recheck_term(self):
        calculation_at = self.recheck.find("Layer 5's `Calculation`")
        term_at = self.recheck.find(RECHECK_TERM)
        self.assertNotEqual(calculation_at, -1)
        self.assertNotEqual(term_at, -1)
        self.assertLess(calculation_at, term_at)

    def test_ac1_calculation_is_cited_to_artifact_digest_md(self):
        self.assertIn("`references/artifact-digest.md`", self.recheck)

    # --- forged controls -------------------------------------------------

    def test_ac1_sequence_probe_fires_on_the_pre_change_order_block(self):
        problems = _order_sequence_problems(_normalize_ws(OLD_ORDER_BLOCK))
        self.assertTrue(problems)
        self.assertIn(f"missing: {RECHECK_TERM}", problems)

    def test_ac1_sequence_probe_passes_on_the_reference_order_block(self):
        self.assertEqual(_order_sequence_problems(_normalize_ws(GOOD_ORDER_BLOCK)), [])

    def test_ac1_sequence_probe_fires_when_the_recheck_comes_before_the_four_steps(self):
        forged = _normalize_ws(GOOD_RECHECK + "\n" + OLD_ORDER_BLOCK)
        problems = _order_sequence_problems(forged)
        self.assertTrue(any(p.startswith("out of order") for p in problems), problems)

    def test_ac1_sequence_probe_fires_when_the_recording_write_comes_before_the_recheck(self):
        forged = _normalize_ws(
            OLD_ORDER_BLOCK
            + "\nThe "
            + RECORDING_WRITE_PHRASE
            + " happens first.\n"
            + GOOD_RECHECK
        )
        problems = _order_sequence_problems(forged)
        self.assertTrue(any(p.startswith("out of order") for p in problems), problems)

    def test_ac1_sequence_probe_fires_when_the_recording_write_phrase_is_absent(self):
        forged = _forge(GOOD_ORDER_BLOCK, RECORDING_WRITE_PHRASE, "recording step")
        self.assertNotIn(RECORDING_WRITE_PHRASE, forged)
        self.assertIn(
            f"missing: {RECORDING_WRITE_PHRASE}", _order_sequence_problems(forged)
        )

    def test_ac1_sequence_probe_fires_when_one_step_anchor_is_missing(self):
        for anchor in ORDER_ANCHORS:
            with self.subTest(anchor=anchor):
                forged = _normalize_ws(GOOD_ORDER_BLOCK).replace(anchor, "x")
                self.assertIn(f"missing: {anchor}", _order_sequence_problems(forged))

    def test_ac1_kept_probe_fires_on_a_block_without_the_intro_sentence(self):
        forged = _forge(OLD_ORDER_BLOCK, "only\nafter the scope verification", "after")
        self.assertIn("intro sentence missing", _kept_order_problems(forged))

    def test_ac1_kept_probe_fires_on_a_block_without_step_4_stale_sentence(self):
        forged = _forge(OLD_ORDER_BLOCK, "makes the result stale", "is noted")
        self.assertIn("step 4 stale sentence missing", _kept_order_problems(forged))

    def test_ac1_kept_probe_passes_on_the_pre_change_order_block(self):
        self.assertEqual(_kept_order_problems(OLD_ORDER_BLOCK), [])

    def test_ac1_recheck_text_of_the_pre_change_order_block_is_empty(self):
        self.assertEqual(_recheck_text(_normalize_ws(OLD_ORDER_BLOCK)), "")

    def test_ac1_when_probes_pass_on_the_reference_recheck(self):
        self.assertEqual(_missing(_normalize_ws(GOOD_RECHECK), WHEN_ELEMENTS), [])

    def test_ac1_each_when_probe_fires_when_its_element_is_deleted(self):
        for name, _pattern, old, new in WHEN_ELEMENTS:
            with self.subTest(element=name):
                forged = _normalize_ws(_forge(GOOD_RECHECK, old, new))
                self.assertIn(name, _missing(forged, WHEN_ELEMENTS))

    def test_ac1_when_probes_fire_on_the_pre_change_order_block(self):
        missing = _missing(_recheck_text(_normalize_ws(OLD_ORDER_BLOCK)), WHEN_ELEMENTS)
        self.assertEqual(len(missing), len(WHEN_ELEMENTS))

    def test_ac1_step_4_stale_wording_alone_never_satisfies_a_recheck_probe(self):
        # the recheck text starts after step 4's sentence, so the old block's
        # "makes the result stale" is outside it
        self.assertNotIn("makes the result stale", _recheck_text(_normalize_ws(OLD_ORDER_BLOCK)))


# ---------------------------------------------------------------------------
# AC-2: what the recheck compares, against which baseline, and what it never
# compares
# ---------------------------------------------------------------------------

COMPARE_ELEMENTS = (
    (
        "names the self-write set's paths",
        r"\b(?:each|every) path of the self-write set\b",
        "For each path of the self-write set, the orchestrator\nreads",
        "The orchestrator\nreads",
    ),
    (
        "names the current git blob id",
        r"\bcurrent git blob id\b",
        "the current git blob id (`git hash-object --`), mode",
        "the current (`git hash-object --`), mode",
    ),
    (
        "names the mode",
        r"\bmode\b",
        "(`git hash-object --`), mode and kind",
        "(`git hash-object --`), and kind",
    ),
    (
        "names the kind as file / symlink / absent",
        r"\bkind\b[^.]{0,60}\bfile\b[^.]{0,20}\bsymlink\b[^.]{0,20}\babsent\b",
        "mode and kind (file,\nsymlink or absent)",
        "mode and kind",
    ),
    (
        "takes the same run's scope verification values as the baseline",
        r"values the same run's scope verification observed for that path",
        "the values the same run's scope\nverification observed for that path after the dispatch",
        "the values it holds after the dispatch",
    ),
    (
        "cites the scope verification",
        r"scope verification observed for that path after the dispatch "
        r"\(`references/phases/create-spec-phase\.md`, \"Scope verification\"\)",
        "(`references/phases/create-spec-phase.md`, \"Scope verification\"). The",
        ". The",
    ),
)


NEGATED_SHA256_SENTENCE = (
    "The orchestrator compares no raw-byte sha256 here, neither the artifact "
    "digest of `references/artifact-digest.md` nor a `digest_inputs` value."
)


def _negated_raw_sha256_sentences(text):
    """Sentences that mention a raw-byte sha256 and are negated."""
    return [
        sentence
        for sentence in _sentences(text)
        if re.search(r"raw-byte sha256", sentence) and _NEGATION_RE.search(sentence)
    ]


def _raw_sha256_sentences(text):
    return [s for s in _sentences(text) if re.search(r"raw-byte sha256", s)]


class TestRecheckComparison(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.order = _block(_read(ENVELOPE_PATH), "Order")
        cls.recheck = _recheck_text(cls.order)

    def test_ac2_recheck_text_names_paths_blob_id_mode_kind_and_the_observed_baseline(self):
        self.assertEqual(_missing(self.recheck, COMPARE_ELEMENTS), [])

    def test_ac2_recheck_text_states_in_a_negated_sentence_that_no_raw_sha256_is_compared(self):
        self.assertTrue(_negated_raw_sha256_sentences(self.recheck))

    def test_ac2_every_sentence_naming_a_raw_sha256_is_negated(self):
        self.assertEqual(
            _raw_sha256_sentences(self.recheck), _negated_raw_sha256_sentences(self.recheck)
        )

    def test_ac2_the_negated_sentence_names_the_artifact_digest_and_digest_inputs(self):
        sentence = _negated_raw_sha256_sentences(self.recheck)[0]
        self.assertIn("references/artifact-digest.md", sentence)
        self.assertIn("digest_inputs", sentence)

    def test_ac2_baseline_is_held_within_the_run_and_never_persisted(self):
        # IMPLEMENTATION.md D3: no persistence wording for the observed values
        self.assertNotRegex(self.recheck, r"(?i)\bpersist")

    # --- forged controls -------------------------------------------------

    def test_ac2_compare_probes_pass_on_the_reference_recheck(self):
        self.assertEqual(_missing(_normalize_ws(GOOD_RECHECK), COMPARE_ELEMENTS), [])

    def test_ac2_each_compare_probe_fires_when_its_element_is_deleted(self):
        for name, _pattern, old, new in COMPARE_ELEMENTS:
            with self.subTest(element=name):
                forged = _normalize_ws(_forge(GOOD_RECHECK, old, new))
                self.assertIn(name, _missing(forged, COMPARE_ELEMENTS))

    def test_ac2_compare_probes_fire_on_the_pre_change_order_block(self):
        missing = _missing(_recheck_text(_normalize_ws(OLD_ORDER_BLOCK)), COMPARE_ELEMENTS)
        self.assertEqual(len(missing), len(COMPARE_ELEMENTS))

    def test_ac2_negation_probe_passes_on_the_reference_recheck(self):
        self.assertTrue(_negated_raw_sha256_sentences(GOOD_RECHECK))

    def test_ac2_negation_probe_fires_when_the_negated_sentence_is_deleted(self):
        forged = _forge(GOOD_RECHECK, NEGATED_SHA256_SENTENCE, "")
        self.assertEqual(_negated_raw_sha256_sentences(forged), [])

    def test_ac2_negation_probe_fires_when_the_sentence_compares_a_raw_sha256(self):
        forged = _forge(
            GOOD_RECHECK,
            NEGATED_SHA256_SENTENCE,
            "The orchestrator compares the raw-byte sha256 of each path.",
        )
        self.assertEqual(_negated_raw_sha256_sentences(forged), [])
        self.assertTrue(_raw_sha256_sentences(forged))

    def test_ac2_negation_probe_fires_on_the_pre_change_order_block(self):
        self.assertEqual(_negated_raw_sha256_sentences(OLD_ORDER_BLOCK), [])

    def test_ac2_persistence_probe_fires_on_a_forged_sentence_that_persists_the_baseline(self):
        forged = GOOD_RECHECK + "\nThe orchestrator persists the observed values in phase-state.\n"
        self.assertRegex(_normalize_ws(forged), r"(?i)\bpersist")


# ---------------------------------------------------------------------------
# AC-3: the outcome of the recheck
# ---------------------------------------------------------------------------


def _stale_outcome_problems(recheck):
    """Problems with the sentence that makes the result stale: it must name a
    mismatch and a recheck that cannot run, a read failure included."""
    for sentence in _sentences(recheck):
        if "makes the result stale" in sentence:
            problems = []
            if not re.search(r"\bmismatch\b", sentence):
                problems.append("mismatch missing")
            if not re.search(r"\brecheck that cannot run\b", sentence):
                problems.append("recheck that cannot run missing")
            if not re.search(r"\bread failure\b", sentence):
                problems.append("read failure missing")
            return problems
    return ["no sentence makes the result stale"]


OUTCOME_ELEMENTS = (
    (
        "cites the scope verification's stale handling",
        r"stale handling of that scope verification states "
        r"\(`references/phases/create-spec-phase\.md`, \"Scope verification\", \"Stale handling\"\)",
        "handled as the stale handling of that scope verification states\n"
        "(`references/phases/create-spec-phase.md`, \"Scope verification\", \"Stale\nhandling\")",
        "handled as before",
    ),
    (
        "a stale result reaches no recording write",
        r"stale result reaches no [^.]{0,30}write",
        "a stale result reaches no such\nwrite",
        "nothing more happens",
    ),
    (
        "an empty self-write set passes with nothing to do",
        r"empty self-write set passes with nothing to do",
        "An empty self-write set passes with nothing to do. ",
        "",
    ),
)


class TestRecheckOutcome(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.order = _block(_read(ENVELOPE_PATH), "Order")
        cls.recheck = _recheck_text(cls.order)

    def test_ac3_a_mismatch_or_a_recheck_that_cannot_run_makes_the_result_stale(self):
        self.assertEqual(_stale_outcome_problems(self.recheck), [])

    def test_ac3_recheck_text_cites_the_stale_handling_states_the_empty_set_and_no_write(self):
        self.assertEqual(_missing(self.recheck, OUTCOME_ELEMENTS), [])

    def test_ac3_stale_handling_citation_points_at_create_spec_phase_md(self):
        self.assertIn("`references/phases/create-spec-phase.md`", self.recheck)

    # --- forged controls -------------------------------------------------

    def test_ac3_stale_probe_passes_on_the_reference_recheck(self):
        self.assertEqual(_stale_outcome_problems(_normalize_ws(GOOD_RECHECK)), [])

    def test_ac3_stale_probe_fires_when_the_failure_case_is_missing(self):
        forged = _forge(
            GOOD_RECHECK,
            "or\na recheck that cannot run (a read failure included), makes",
            "makes",
        )
        problems = _stale_outcome_problems(_normalize_ws(forged))
        self.assertIn("recheck that cannot run missing", problems)
        self.assertIn("read failure missing", problems)

    def test_ac3_stale_probe_fires_when_only_the_read_failure_is_missing(self):
        forged = _forge(GOOD_RECHECK, " (a read failure included)", "")
        self.assertEqual(
            _stale_outcome_problems(_normalize_ws(forged)), ["read failure missing"]
        )

    def test_ac3_stale_probe_fires_when_the_mismatch_case_is_missing(self):
        forged = _forge(GOOD_RECHECK, "Any mismatch, or\na recheck", "Only a recheck")
        self.assertIn("mismatch missing", _stale_outcome_problems(_normalize_ws(forged)))

    def test_ac3_stale_probe_fires_on_the_pre_change_order_block_recheck_text(self):
        self.assertEqual(
            _stale_outcome_problems(_recheck_text(_normalize_ws(OLD_ORDER_BLOCK))),
            ["no sentence makes the result stale"],
        )

    def test_ac3_stale_probe_fires_when_step_4_wording_is_the_only_stale_sentence(self):
        # step 4 names a mismatch and a script exit, not a failed recheck
        self.assertNotEqual(_stale_outcome_problems(STEP4_STALE_SENTENCE), [])

    def test_ac3_outcome_probes_pass_on_the_reference_recheck(self):
        self.assertEqual(_missing(_normalize_ws(GOOD_RECHECK), OUTCOME_ELEMENTS), [])

    def test_ac3_each_outcome_probe_fires_when_its_element_is_deleted(self):
        for name, _pattern, old, new in OUTCOME_ELEMENTS:
            with self.subTest(element=name):
                forged = _normalize_ws(_forge(GOOD_RECHECK, old, new))
                self.assertIn(name, _missing(forged, OUTCOME_ELEMENTS))

    def test_ac3_outcome_probes_fire_on_the_pre_change_order_block(self):
        missing = _missing(_recheck_text(_normalize_ws(OLD_ORDER_BLOCK)), OUTCOME_ELEMENTS)
        self.assertEqual(len(missing), len(OUTCOME_ELEMENTS))


# ---------------------------------------------------------------------------
# AC-4: Known limit
# ---------------------------------------------------------------------------

KNOWN_LIMIT_ELEMENTS = (
    (
        "keeps the existing sentence verbatim",
        re.escape(KNOWN_LIMIT_EXISTING_SENTENCE),
        "this case rests on the exclusivity assumption stated\nbelow.",
        "this case is ignored.",
    ),
    (
        "a change after the scope verification is detected by the return-time recheck",
        r"change made after the scope verification is detected by the return-time recheck",
        "A change made after the scope verification is detected by the return-time\nrecheck",
        "A change made after the scope verification is not covered",
    ),
    (
        "the remaining window from the recheck to the recording write rests on the assumption",
        r"remaining window, from (?:that|the) (?:return-time )?recheck (?:to|through) the "
        r"phase-state write that records the run's `artifacts` and `self_write_set`, "
        r"rests on the exclusivity assumption",
        "The remaining window, from that recheck through the\n"
        "phase-state write that records the run's `artifacts` and `self_write_set`,\n"
        "rests on the exclusivity assumption,",
        "The window is not discussed,",
    ),
    (
        "points at the Exclusivity section for the interval",
        r"whose interval the section \"Exclusivity assumption during dispatch\" below states",
        "whose interval the section \"Exclusivity\nassumption during dispatch\" below states.",
        "whose interval is not stated.",
    ),
)

# Interval end-point variants belong to the Exclusivity section, not to Known
# limit ("Point at that section instead of restating the interval's variants").
_INTERVAL_VARIANT_RE = re.compile(
    r"returned `status`|stale judgment|scope snapshot capture|is empty", re.IGNORECASE
)


class TestKnownLimit(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(ENVELOPE_PATH)
        cls.block = _block(cls.text, "Known limit")

    def test_ac4_known_limit_adds_the_recheck_detection_and_the_remaining_window(self):
        self.assertEqual(_missing(self.block, KNOWN_LIMIT_ELEMENTS), [])

    def test_ac4_known_limit_keeps_the_three_existing_phrases(self):
        self.assertRegex(self.block, r"worker and another actor change the same permitted path")
        self.assertRegex(self.block, r"cannot be told apart")
        self.assertIn("exclusivity assumption", self.block)

    def test_ac4_known_limit_precedes_the_exclusivity_heading(self):
        self.assertGreater(
            self.text.index(EXCLUSIVITY_HEADING), self.text.index("**Known limit.**")
        )

    def test_ac4_known_limit_does_not_restate_the_interval_variants(self):
        self.assertIsNone(_INTERVAL_VARIANT_RE.search(self.block))

    def test_ac4_known_limit_precedes_the_provenance_paragraph(self):
        self.assertLess(self.text.index("**Known limit.**"), self.text.index("(Provenance:"))
        self.assertNotIn("(Provenance:", self.block)

    # --- forged controls -------------------------------------------------

    def test_ac4_known_limit_probes_fire_on_the_pre_change_known_limit_text(self):
        missing = _missing(_normalize_ws(OLD_KNOWN_LIMIT_BLOCK), KNOWN_LIMIT_ELEMENTS)
        self.assertEqual(
            missing,
            [name for name, _p, _o, _n in KNOWN_LIMIT_ELEMENTS if not name.startswith("keeps")],
        )

    def test_ac4_known_limit_probes_pass_on_the_reference_known_limit(self):
        self.assertEqual(_missing(_normalize_ws(GOOD_KNOWN_LIMIT_BLOCK), KNOWN_LIMIT_ELEMENTS), [])

    def test_ac4_each_known_limit_probe_fires_when_its_element_is_deleted(self):
        for name, _pattern, old, new in KNOWN_LIMIT_ELEMENTS:
            with self.subTest(element=name):
                forged = _normalize_ws(_forge(GOOD_KNOWN_LIMIT_BLOCK, old, new))
                self.assertIn(name, _missing(forged, KNOWN_LIMIT_ELEMENTS))

    def test_ac4_variant_probe_fires_on_a_known_limit_that_restates_the_interval(self):
        forged = GOOD_KNOWN_LIMIT_BLOCK + (
            "For a run whose `written_artifacts` is empty the interval ends at the write "
            "that records the returned `status`.\n"
        )
        self.assertIsNotNone(_INTERVAL_VARIANT_RE.search(_normalize_ws(forged)))

    def test_ac4_variant_probe_stays_quiet_on_the_reference_known_limit(self):
        self.assertIsNone(_INTERVAL_VARIANT_RE.search(_normalize_ws(GOOD_KNOWN_LIMIT_BLOCK)))

    def test_ac4_heading_order_probe_fires_on_a_document_with_the_heading_first(self):
        forged = EXCLUSIVITY_HEADING + "\n\n" + OLD_KNOWN_LIMIT_BLOCK
        self.assertLess(forged.index(EXCLUSIVITY_HEADING), forged.index("**Known limit.**"))


# ---------------------------------------------------------------------------
# AC-5: R1 invariants the added text must keep
# ---------------------------------------------------------------------------


class TestR1Invariants(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(ENVELOPE_PATH)
        cls.r1 = _r1_section(cls.text)
        cls.order = _block(cls.text, "Order")
        cls.recheck = _recheck_text(cls.order)
        cls.means = _block(cls.text, "Means")
        cls.known_limit = _block(cls.text, "Known limit")

    def test_ac5_r1_label_set_is_unchanged_and_each_label_appears_once(self):
        self.assertEqual(_r1_labels(self.r1), list(R1_LABELS))
        for label in R1_LABELS:
            with self.subTest(label=label):
                self.assertEqual(self.text.count(f"**{label}.**"), 1)

    def test_ac5_every_added_digest_sentence_names_the_orchestrator_or_is_negated(self):
        self.assertEqual(_digest_sentence_violations(self.recheck), [])
        self.assertEqual(_digest_sentence_violations(self.known_limit), [])

    def test_ac5_the_recheck_names_git_hash_object_in_an_orchestrator_sentence(self):
        sentences = [s for s in _sentences(self.recheck) if "git hash-object" in s]
        self.assertTrue(sentences)
        for sentence in sentences:
            with self.subTest(sentence=sentence[:60]):
                self.assertRegex(sentence, r"(?i)orchestrator")

    def test_ac5_the_document_carries_no_expect_digest_token(self):
        self.assertIsNone(re.search(r"\bexpect_digest\b", self.text))

    def test_ac5_means_block_still_states_that_the_script_computes_no_digest(self):
        self.assertIn("The script computes no digest", self.means)
        self.assertIn("hashing stays with the orchestrator", self.means)

    # --- forged controls -------------------------------------------------

    def test_ac5_label_probe_fires_on_an_r1_section_with_a_new_label(self):
        forged = self.r1.replace("**Means.**", "**Return-time recheck.** x\n\n**Means.**", 1)
        self.assertNotEqual(_r1_labels(forged), list(R1_LABELS))

    def test_ac5_label_probe_fires_on_an_r1_section_with_a_duplicated_label(self):
        forged = self.r1 + "\n**Order.** again\n"
        with self.assertRaises(AssertionError):
            _r1_blocks(forged)

    def test_ac5_label_probe_fires_on_an_r1_section_missing_a_label(self):
        forged = self.r1.replace("**Means.**", "Means:", 1)
        with self.assertRaises(AssertionError):
            _r1_blocks(forged)

    def test_ac5_digest_sentence_probe_passes_on_the_reference_text(self):
        self.assertEqual(_digest_sentence_violations(GOOD_RECHECK), [])
        self.assertEqual(_digest_sentence_violations(GOOD_KNOWN_LIMIT_BLOCK), [])

    def test_ac5_digest_sentence_probe_fires_on_a_worker_directed_hash_sentence(self):
        forged = _forge(
            GOOD_RECHECK,
            "For each path of the self-write set, the orchestrator\nreads the current git blob id",
            "For each path of the self-write set, read the current git blob id",
        )
        violations = _digest_sentence_violations(forged)
        self.assertTrue(violations)
        self.assertTrue(any("git hash-object" in v for v in violations))

    def test_ac5_digest_sentence_probe_fires_on_an_unnegated_raw_sha256_sentence(self):
        forged = _forge(
            GOOD_RECHECK,
            NEGATED_SHA256_SENTENCE,
            "The recheck compares the raw-byte sha256 of each path.",
        )
        self.assertTrue(_digest_sentence_violations(forged))

    def test_ac5_digest_sentence_probe_stays_quiet_on_a_negated_sentence_without_the_orchestrator(self):
        self.assertEqual(
            _digest_sentence_violations("This step compares no raw-byte sha256."), []
        )

    def test_ac5_expect_digest_probe_fires_on_a_forged_document(self):
        forged = self.text + "\nThe worker sets `expect_digest` first.\n"
        self.assertIsNotNone(re.search(r"\bexpect_digest\b", forged))

    def test_ac5_means_probe_fires_on_a_means_block_that_computes_a_digest(self):
        forged = _forge(self.means, "The script computes no digest", "The script computes the digest")
        self.assertNotIn("The script computes no digest", forged)


# ---------------------------------------------------------------------------
# Slicers: the helpers behave on forged documents
# ---------------------------------------------------------------------------


class TestSlicers(unittest.TestCase):
    def _forged_r1(self):
        labels = {
            "Condition": "c",
            "Self-write set": "s",
            "Substitution": "u",
            "Order": OLD_ORDER_BLOCK.split(".** ", 1)[1],
            "Means": "m",
            "Persistence and resume": "p",
            "Known limit": OLD_KNOWN_LIMIT_BLOCK.split(".** ", 1)[1],
        }
        body = "\n\n".join(f"**{label}.** {text}" for label, text in labels.items())
        return f"# Doc\n\n## Rule R1: x\n\n{body}\n\n(Provenance: p.)\n\n## Next\n\ntail\n"

    def test_order_block_runs_to_the_means_label(self):
        doc = self._forged_r1()
        order = _block(doc, "Order")
        self.assertTrue(order.startswith("**Order.**"))
        self.assertNotIn("**Means.**", order)
        self.assertIn(STEP4_STALE_SENTENCE, order)

    def test_known_limit_block_stops_before_the_provenance_paragraph(self):
        doc = self._forged_r1()
        block = _block(doc, "Known limit")
        self.assertNotIn("Provenance", block)
        self.assertIn(KNOWN_LIMIT_EXISTING_SENTENCE, block)

    def test_r1_section_stops_at_the_next_level_2_heading(self):
        self.assertNotIn("tail", _r1_section(self._forged_r1()))

    def test_section_slicer_rejects_a_document_without_the_heading(self):
        with self.assertRaises(AssertionError):
            _r1_section("# Doc\n\n## Other\n\ntext\n")

    def test_recheck_slicer_ignores_step_4_wording_in_a_block_with_a_fenced_heading(self):
        doc = "## Rule R1: x\n\n```\n## Not a heading\n```\n\n**Order.** text\n"
        self.assertIn("**Order.** text", _r1_section(doc))

    def test_whitespace_normalization_makes_the_probes_independent_of_line_breaks(self):
        wrapped = GOOD_ORDER_BLOCK
        unwrapped = wrapped.replace("\n", " ")
        self.assertEqual(_normalize_ws(wrapped), _normalize_ws(unwrapped))
        self.assertEqual(_order_sequence_problems(_normalize_ws(unwrapped)), [])


# ---------------------------------------------------------------------------
# AC-6: the form of this file
# ---------------------------------------------------------------------------


def _third_party_imports(source):
    names = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.extend(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.append(node.module.split(".")[0])
    return sorted({name for name in names if name not in sys.stdlib_module_names})


_METHOD_NAME_RE = re.compile(r"^test_[a-z0-9]+(?:_[a-z0-9]+)+$")


def _naming_problems(source):
    problems = []
    for node in ast.parse(source).body:
        if not isinstance(node, ast.ClassDef):
            continue
        bases = [ast.unparse(base) for base in node.bases]
        if node.name.startswith("Test"):
            if "unittest.TestCase" not in bases:
                problems.append(f"{node.name}: does not extend unittest.TestCase")
            for item in node.body:
                if isinstance(item, ast.FunctionDef) and item.name.startswith("test"):
                    if not _METHOD_NAME_RE.match(item.name):
                        problems.append(f"{node.name}.{item.name}: not test_<condition>_<result>")
        elif "unittest.TestCase" in bases:
            problems.append(f"{node.name}: a TestCase class not named Test<Behavior>")
    return problems


class TestTestFileForm(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = _read(Path(__file__).resolve())

    def test_ac6_this_file_imports_only_the_standard_library(self):
        self.assertEqual(_third_party_imports(self.source), [])

    def test_ac6_this_file_follows_the_test_readme_naming_rules(self):
        self.assertEqual(_naming_problems(self.source), [])

    def test_ac6_this_file_is_named_test_target_py(self):
        self.assertRegex(Path(__file__).name, r"^test_[a-z0-9_]+\.py$")

    def test_ac6_import_probe_fires_on_a_forged_third_party_import(self):
        self.assertEqual(_third_party_imports("import os\nimport yaml\nfrom foo.bar import x\n"), ["foo", "yaml"])

    def test_ac6_import_probe_stays_quiet_on_standard_library_imports(self):
        self.assertEqual(_third_party_imports("import os\nfrom pathlib import Path\n"), [])

    def test_ac6_naming_probe_fires_on_a_forged_camel_case_method(self):
        forged = "import unittest\nclass TestX(unittest.TestCase):\n    def testThing(self):\n        pass\n"
        self.assertTrue(_naming_problems(forged))

    def test_ac6_naming_probe_fires_on_a_forged_class_that_is_not_named_test(self):
        forged = "import unittest\nclass Checks(unittest.TestCase):\n    def test_a_b(self):\n        pass\n"
        self.assertTrue(_naming_problems(forged))

    def test_ac6_naming_probe_stays_quiet_on_a_well_named_class(self):
        forged = "import unittest\nclass TestX(unittest.TestCase):\n    def test_a_b(self):\n        pass\n"
        self.assertEqual(_naming_problems(forged), [])


if __name__ == "__main__":
    unittest.main()
