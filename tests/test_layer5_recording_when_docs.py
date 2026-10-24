"""Document tests for self-write-exclusivity-window task0003.

`em-workflow/references/artifact-digest.md`, section "Layer 5 recording",
paragraph `When:` says when layer 5 recording happens. After this change the
paragraph keeps its statement that recording follows layer 4 (scope
verification) passing for the dispatch's `completed` result, and adds, by
citation of `references/contracts/worker-envelope.md`, Rule R1,
"Recomputation and comparison timing":

- `Calculation` runs only after R1's return-time comparison has not made the
  result stale;
- the recording write (the `artifacts` entries) happens only after R1's
  `return-time recheck` has not made the result stale.

Covers task0003's Acceptance Criteria
(feature-docs/self-write-exclusivity-window/tasks/task0003.md):

- AC-1 (FR6): the layer 4 statement is kept.
- AC-2 (FR6, TM-1): the R1 citation, the `Calculation` statement and the
  recording-write statement.
- AC-3 (FR6): the order Calculation, recheck, recording write.
- AC-4 (FR6): the paragraph cites the recheck and never restates it.
- AC-5 (NFR3): the added sentences follow the digest-sentence convention; the
  rest of "Layer 5 recording" and the final paragraph of "Pre-dispatch
  verification" are unchanged.
- AC-6 (FR8, NFR1, NFR2): this file's own conventions.

Method: slice the section by heading, take the paragraph that starts with
`When:`, whitespace-normalize, and run named probes on it. Nothing depends on
a line-break position or on whole-document equality. Every probe is paired
with a forged-text control on which it fires (the pre-change paragraph, a
reordered paragraph, a paragraph that restates the recheck, a worker-directed
digest sentence, an altered neighbour paragraph). The tests read the
paragraph's citation text only; they never assert that `worker-envelope.md`
already contains the recheck. Standard library only.
"""

import ast
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OWNER_PATH = REPO_ROOT / "em-workflow" / "references" / "artifact-digest.md"

SECTION_TITLE = "Layer 5 recording"
PRE_DISPATCH_TITLE = "Pre-dispatch verification"

ENVELOPE_CITATION = "references/contracts/worker-envelope.md"
R1_NAME = "Rule R1"
TIMING_NAME = "Recomputation and comparison timing"

_FENCE_RE = re.compile(r"^\s*(```|~~~)")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")


# ---------------------------------------------------------------------------
# Helpers (document slicing)
# ---------------------------------------------------------------------------


def _read(path):
    return path.read_text(encoding="utf-8")


def _norm(text):
    """Whitespace-normalize: any run of whitespace becomes one space."""
    return " ".join(text.split())


def _headings(text):
    """[(line_index, level, title)] for every ATX heading outside a fenced
    code block."""
    found = []
    in_fence = False
    for idx, line in enumerate(text.splitlines()):
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = _HEADING_RE.match(line)
        if match:
            found.append((idx, len(match.group(1)), match.group(2)))
    return found


def _section(text, title, level=2):
    """The body of the one level-`level` heading titled `title`, up to the
    next heading of the same or a higher level. Exactly one heading must
    match."""
    lines = text.splitlines()
    heads = _headings(text)
    hits = [i for i, h in enumerate(heads) if h[2] == title and h[1] == level]
    if len(hits) != 1:
        raise AssertionError(
            f"expected exactly one level-{level} heading {title!r}, found {len(hits)}"
        )
    pos = hits[0]
    start, lvl, _title = heads[pos]
    end = len(lines)
    for nxt_line, nxt_lvl, _nxt in heads[pos + 1:]:
        if nxt_lvl <= lvl:
            end = nxt_line
            break
    return "\n".join(lines[start + 1:end])


def _paragraphs(text):
    """Blank-line-delimited blocks, each whitespace-normalized; empty blocks
    dropped."""
    return [p for p in (_norm(b) for b in re.split(r"\n\s*\n", text)) if p]


def _when_paragraph(section_text):
    """The one paragraph of the section whose text starts with `When:`,
    whitespace-normalized."""
    hits = [p for p in _paragraphs(section_text) if p.startswith("When:")]
    if len(hits) != 1:
        raise AssertionError(
            f"expected exactly one paragraph starting with 'When:', found {len(hits)}"
        )
    return hits[0]


def _sentences(flat):
    return re.split(r"(?<=[.!?])\s+", flat)


def _sentence_with(flat, token):
    for sentence in _sentences(flat):
        if token in sentence:
            return sentence
    return ""


# ---------------------------------------------------------------------------
# Probes. Each takes a paragraph (or section) and returns True when it FIRES,
# that is, when it finds the defect it is named for. Every probe appears in
# PROBE_CONTROLS with forged texts on which it fires and a conforming text on
# which it stays quiet.
# ---------------------------------------------------------------------------

_LAYER_4_RE = re.compile(
    r"\bafter layer 4 \(scope verification\) passes for the dispatch's "
    r"`completed` result\b"
)
_CALCULATION_RE = re.compile(
    r"`Calculation`.*?\bonly after\b.*?\breturn-time comparison\b"
    r".*?\bnot made the result stale\b",
    re.IGNORECASE,
)
_RECORDING_RE = re.compile(
    r"\bonly after\b.*?\breturn-time recheck\b.*?\bnot made the result stale\b"
    r".*?\brecording write\b",
    re.IGNORECASE,
)
_RECHECK_TERM = "return-time recheck"


def probe_layer_4_statement_missing(paragraph):
    return not _LAYER_4_RE.search(_norm(paragraph))


def probe_r1_citation_missing(paragraph):
    """Fires unless one sentence names the owner path, `Rule R1` and the
    rule's timing name together."""
    for sentence in _sentences(_norm(paragraph)):
        if (
            ENVELOPE_CITATION in sentence
            and R1_NAME in sentence
            and TIMING_NAME in sentence
        ):
            return False
    return True


def probe_calculation_statement_missing(paragraph):
    """Fires unless the sentence naming `Calculation` says it runs only after
    R1's return-time comparison has not made the result stale."""
    sentence = _sentence_with(_norm(paragraph), "`Calculation`")
    return not _CALCULATION_RE.search(sentence)


def probe_recording_statement_missing(paragraph):
    """Fires unless one sentence says the recording write happens only after
    the return-time recheck has not made the result stale."""
    return not any(
        _RECORDING_RE.search(sentence) for sentence in _sentences(_norm(paragraph))
    )


def probe_order_violated(paragraph):
    """Fires unless the first `Calculation` mention precedes the first
    `return-time recheck` mention, which precedes the first `recording write`
    mention, and the `Calculation` sentence never names the recheck."""
    flat = _norm(paragraph)
    marks = [flat.find("`Calculation`"), flat.find(_RECHECK_TERM), flat.find("recording write")]
    if any(mark < 0 for mark in marks):
        return True
    if not marks[0] < marks[1] < marks[2]:
        return True
    return _RECHECK_TERM in _sentence_with(flat, "`Calculation`")


# What the recheck compares, how a path joins the self-write set, and the
# substitution are owned by Rule R1: a citing paragraph names none of them.
_RESTATEMENT_PATTERNS = {
    "git hash-object": re.compile(r"git hash-object"),
    "blob id": re.compile(r"\bblob\b", re.IGNORECASE),
    "mode": re.compile(r"\bmodes?\b", re.IGNORECASE),
    "kind": re.compile(r"\bkinds?\b", re.IGNORECASE),
    "file kind name": re.compile(r"\b(?:symlink|absent)\b", re.IGNORECASE),
    "re-read": re.compile(r"\bre-?reads?\b", re.IGNORECASE),
    "self-write set": re.compile(r"self-write[ -]set", re.IGNORECASE),
    "membership": re.compile(r"\bmember(?:s|ship)?\b", re.IGNORECASE),
    "substitution": re.compile(
        r"\bsubstitut\w*|dispatch-time value", re.IGNORECASE
    ),
    "change kind": re.compile(r"\b(?:created|modified|deleted)\b"),
    "write_policy action": re.compile(
        r"\b(?:replace_own|replace_authorized|extend_only|regenerate|preserve)\b"
    ),
}


def restatement_markers(paragraph):
    flat = _norm(paragraph)
    return [name for name, pattern in _RESTATEMENT_PATTERNS.items() if pattern.search(flat)]


def probe_recheck_restated(paragraph):
    return bool(restatement_markers(paragraph))


# The digest-sentence convention (NFR3): a sentence that mentions a digest, a
# hash or sha256 names the orchestrator as its actor or is negated.
_DIGEST_TERM_RE = re.compile(
    r"(?<![A-Za-z0-9_])(?:sha-?256(?:sum)?|expect_digest|digests?|hash(?:es|ed|ing)?)"
    r"(?![A-Za-z0-9_])",
    re.IGNORECASE,
)
_ORCHESTRATOR_RE = re.compile(r"orchestrator", re.IGNORECASE)
_NEGATION_RE = re.compile(
    r"(?<![A-Za-z0-9_])(?:not|never|no|cannot|without|neither|nor)(?![A-Za-z0-9_])"
    r"|n['’]t(?![A-Za-z0-9_])",
    re.IGNORECASE,
)


def digest_sentence_violations(text):
    return [
        sentence
        for sentence in _sentences(_norm(text.replace("`", "")))
        if _DIGEST_TERM_RE.search(sentence)
        and not _ORCHESTRATOR_RE.search(sentence)
        and not _NEGATION_RE.search(sentence)
    ]


def added_sentences(paragraph):
    """The sentences of the `When:` paragraph after its first one, the
    statement that existed before this change."""
    return _sentences(_norm(paragraph))[1:]


def probe_added_digest_sentence_violates_convention(paragraph):
    """Fires when the paragraph adds no sentence at all (the check would pass
    vacuously) or an added sentence mentions a digest without naming the
    orchestrator and without a negation."""
    added = added_sentences(paragraph)
    return not added or bool(digest_sentence_violations(" ".join(added)))


# The neighbours of the `When:` paragraph that this change leaves alone.
LAYER5_NEIGHBOUR_PARAGRAPHS = (
    "Zero artifacts: when the result's `written_artifacts` has zero entries, "
    "`Calculation` is not run and nothing is recorded. Whether an empty "
    "`completed` result is acceptable is not decided here; the rules of the "
    "layer that handles that result decide it. When the result has one or more "
    "entries, the procedure below and every artifact-validation failure "
    "condition apply unchanged.",
    "How: one `Calculation` call over every `written_artifacts` path. The "
    "orchestrator records one `{path, sha256, produced_by}` entry per path into "
    "`artifacts` of the dispatching phase's phase-state file: `create-spec.yaml`, "
    "`design.yaml`, `create-plan.yaml` or `rework.yaml` under "
    "`feature-docs/{feature}/phase-state/`, following the \"ID uniqueness and "
    "idempotency\" rules of `references/phase-state.md`.",
    "- A `sha256` the worker put in an entry is never read, compared or "
    "recorded; only digests the orchestrator calculated are recorded. "
    "- `preserve` targets are never written by a worker, so they are not in "
    "`written_artifacts` and are not recorded. "
    "- When `tokens.yaml` and `tokens.html` are both written, both are recorded. "
    "- Any error element, an exit code of `2`, or a path the quoting rule keeps "
    "out of a command fails layer 5 as an artifact-validation failure.",
)

PRE_DISPATCH_FINAL_PARAGRAPH = (
    "The worker never repeats this verification. From it to the worker's write, "
    "the exclusivity assumption (`references/contracts/worker-envelope.md`) "
    "protects the targets, and the post-dispatch scope comparison detects any "
    "change made in that window."
)


def probe_layer5_rest_changed(section_text):
    """Fires unless the section holds exactly the `When:` paragraph followed by
    the three neighbour blocks, each word for word."""
    rest = [p for p in _paragraphs(section_text) if not p.startswith("When:")]
    return rest != list(LAYER5_NEIGHBOUR_PARAGRAPHS)


def probe_pre_dispatch_final_paragraph_changed(section_text):
    paragraphs = _paragraphs(section_text)
    return not paragraphs or paragraphs[-1] != PRE_DISPATCH_FINAL_PARAGRAPH


# ---------------------------------------------------------------------------
# Forged texts (the controls)
# ---------------------------------------------------------------------------

# The `When:` paragraph as it read before this change.
PRE_CHANGE_WHEN = (
    "When: after layer 4 (scope verification) passes for the dispatch's\n"
    "`completed` result.\n"
)

# A paragraph that conforms to the task plan, wrapped differently from the
# document so that the whitespace normalization is exercised.
CONFORMING_WHEN = (
    "When: after layer 4 (scope verification) passes for the dispatch's\n"
    "`completed` result. The orchestrator runs `Calculation` only after the\n"
    "return-time comparison of `references/contracts/worker-envelope.md`,\n"
    "Rule R1, \"Recomputation and comparison timing\", has not made the result\n"
    "stale. Only after Rule R1's `return-time recheck` has not made the result\n"
    "stale does the orchestrator make the recording write, the `artifacts`\n"
    "entries below.\n"
)

# `Calculation` is mentioned after the recheck.
CALCULATION_AFTER_RECHECK_WHEN = (
    "When: after layer 4 (scope verification) passes for the dispatch's "
    "`completed` result. The orchestrator first requires that the "
    "`return-time recheck` of `references/contracts/worker-envelope.md`, Rule R1, "
    "\"Recomputation and comparison timing\", has not made the result stale. It "
    "then runs `Calculation` only after the return-time comparison has not made "
    "the result stale. Only after the `return-time recheck` has not made the "
    "result stale does the orchestrator make the recording write."
)

# `Calculation` is said to run after the recheck.
CALCULATION_NAMES_RECHECK_WHEN = (
    "When: after layer 4 (scope verification) passes for the dispatch's "
    "`completed` result. The orchestrator runs `Calculation` only after the "
    "return-time comparison and the `return-time recheck` of "
    "`references/contracts/worker-envelope.md`, Rule R1, \"Recomputation and "
    "comparison timing\", have not made the result stale. Only after the "
    "`return-time recheck` has not made the result stale does the orchestrator "
    "make the recording write."
)

# `Calculation` is said to run only after the recheck, with no mention of the
# return-time comparison.
CALCULATION_ONLY_AFTER_RECHECK_WHEN = (
    "When: after layer 4 (scope verification) passes for the dispatch's "
    "`completed` result. The orchestrator runs `Calculation` only after the "
    "`return-time recheck` of `references/contracts/worker-envelope.md`, Rule R1, "
    "\"Recomputation and comparison timing\", has not made the result stale. Only "
    "after the `return-time recheck` has not made the result stale does the "
    "orchestrator make the recording write."
)

# The recording write is mentioned before the recheck.
RECORDING_BEFORE_RECHECK_WHEN = (
    "When: after layer 4 (scope verification) passes for the dispatch's "
    "`completed` result. The orchestrator runs `Calculation` only after the "
    "return-time comparison of `references/contracts/worker-envelope.md`, Rule "
    "R1, \"Recomputation and comparison timing\", has not made the result stale. "
    "The recording write follows. Only after the `return-time recheck` has not "
    "made the result stale does the orchestrator finish."
)

# The citation is spread over two sentences.
SPLIT_CITATION_WHEN = (
    "When: after layer 4 (scope verification) passes for the dispatch's "
    "`completed` result. The orchestrator runs `Calculation` only after the "
    "return-time comparison of `references/contracts/worker-envelope.md` has not "
    "made the result stale. Rule R1, \"Recomputation and comparison timing\", "
    "also applies. Only after the `return-time recheck` has not made the result "
    "stale does the orchestrator make the recording write."
)

# The recheck is restated in its several parts.
RESTATING_WHENS = {
    "blob id, mode and kind": (
        CONFORMING_WHEN.replace(
            "`artifacts`\nentries below.",
            "`artifacts`\nentries below. The recheck compares the current git blob "
            "id, mode and kind of each path.",
        )
    ),
    "git hash-object": (
        CONFORMING_WHEN
        + "The recheck hashes each path with `git hash-object`.\n"
    ),
    "membership": (
        CONFORMING_WHEN
        + "A path is a member of the self-write set when it was created.\n"
    ),
    "substitution": (
        CONFORMING_WHEN
        + "The dispatch-time value is substituted for each such path.\n"
    ),
}

# A worker-directed digest sentence and a digest sentence that names no actor.
WORKER_DIRECTED_DIGEST_WHEN = (
    CONFORMING_WHEN + "Compute the digest of every written path before returning.\n"
)
NO_ACTOR_DIGEST_WHEN = (
    CONFORMING_WHEN + "The digest of each path is recorded in the entry.\n"
)

# The layer-5 section and the pre-dispatch section, as forged neighbours.
FORGED_LAYER5_SECTION_ALTERED_HOW = (
    "\n"
    + CONFORMING_WHEN
    + "\n"
    + LAYER5_NEIGHBOUR_PARAGRAPHS[0]
    + "\n\n"
    + LAYER5_NEIGHBOUR_PARAGRAPHS[1].replace("one `Calculation` call", "two `Calculation` calls")
    + "\n\n"
    + LAYER5_NEIGHBOUR_PARAGRAPHS[2]
    + "\n"
)
FORGED_LAYER5_SECTION_EXTRA_PARAGRAPH = (
    "\n"
    + CONFORMING_WHEN
    + "\n"
    + "\n\n".join(LAYER5_NEIGHBOUR_PARAGRAPHS)
    + "\n\nAn extra paragraph that was not there before.\n"
)
INTACT_LAYER5_SECTION = (
    "\n" + CONFORMING_WHEN + "\n" + "\n\n".join(LAYER5_NEIGHBOUR_PARAGRAPHS) + "\n"
)
FORGED_PRE_DISPATCH_SECTION = (
    "\nWhen: earlier.\n\n"
    + PRE_DISPATCH_FINAL_PARAGRAPH.replace(
        "protects the targets", "protects the targets until the recording write"
    )
    + "\n"
)
INTACT_PRE_DISPATCH_SECTION = "\nWhen: earlier.\n\n" + PRE_DISPATCH_FINAL_PARAGRAPH + "\n"

# probe -> (forged texts on which it fires, conforming text on which it is quiet)
PROBE_CONTROLS = {
    probe_layer_4_statement_missing: (
        [
            "When: after the dispatch returns.",
            "When: after layer 3 (revision validation) passes for the dispatch's "
            "`completed` result.",
            "When: after layer 4 (scope verification) passes.",
        ],
        CONFORMING_WHEN,
    ),
    probe_r1_citation_missing: (
        [PRE_CHANGE_WHEN, SPLIT_CITATION_WHEN],
        CONFORMING_WHEN,
    ),
    probe_calculation_statement_missing: (
        [PRE_CHANGE_WHEN, CALCULATION_ONLY_AFTER_RECHECK_WHEN],
        CONFORMING_WHEN,
    ),
    probe_recording_statement_missing: (
        [PRE_CHANGE_WHEN, RECORDING_BEFORE_RECHECK_WHEN],
        CONFORMING_WHEN,
    ),
    probe_order_violated: (
        [
            PRE_CHANGE_WHEN,
            CALCULATION_AFTER_RECHECK_WHEN,
            CALCULATION_NAMES_RECHECK_WHEN,
            CALCULATION_ONLY_AFTER_RECHECK_WHEN,
            RECORDING_BEFORE_RECHECK_WHEN,
        ],
        CONFORMING_WHEN,
    ),
    probe_recheck_restated: (list(RESTATING_WHENS.values()), CONFORMING_WHEN),
    probe_added_digest_sentence_violates_convention: (
        [PRE_CHANGE_WHEN, WORKER_DIRECTED_DIGEST_WHEN, NO_ACTOR_DIGEST_WHEN],
        CONFORMING_WHEN,
    ),
    probe_layer5_rest_changed: (
        [FORGED_LAYER5_SECTION_ALTERED_HOW, FORGED_LAYER5_SECTION_EXTRA_PARAGRAPH],
        INTACT_LAYER5_SECTION,
    ),
    probe_pre_dispatch_final_paragraph_changed: (
        [FORGED_PRE_DISPATCH_SECTION, "\nNo paragraph survives here.\n\n"],
        INTACT_PRE_DISPATCH_SECTION,
    ),
}


# ---------------------------------------------------------------------------
# Controls: every probe fires on forged text and is quiet on conforming text
# ---------------------------------------------------------------------------


class TestProbesFireOnForgedText(unittest.TestCase):
    def test_every_probe_fires_on_each_of_its_forged_texts(self):
        for probe, (forged_texts, _conforming) in PROBE_CONTROLS.items():
            for index, forged in enumerate(forged_texts):
                with self.subTest(probe=probe.__name__, forged=index):
                    self.assertTrue(probe(forged), forged)

    def test_every_probe_stays_quiet_on_the_conforming_text(self):
        for probe, (_forged, conforming) in PROBE_CONTROLS.items():
            with self.subTest(probe=probe.__name__):
                self.assertFalse(probe(conforming), conforming)

    def test_every_probe_function_has_a_control_entry(self):
        probes_in_module = {
            obj
            for name, obj in globals().items()
            if name.startswith("probe_") and callable(obj)
        }
        self.assertEqual(probes_in_module, set(PROBE_CONTROLS))

    def test_the_pre_change_paragraph_fires_each_probe_for_the_added_statements(self):
        for probe in (
            probe_r1_citation_missing,
            probe_calculation_statement_missing,
            probe_recording_statement_missing,
            probe_order_violated,
            probe_added_digest_sentence_violates_convention,
        ):
            with self.subTest(probe=probe.__name__):
                self.assertTrue(probe(PRE_CHANGE_WHEN))

    def test_the_pre_change_paragraph_keeps_the_layer_4_statement_and_restates_nothing(self):
        self.assertFalse(probe_layer_4_statement_missing(PRE_CHANGE_WHEN))
        self.assertFalse(probe_recheck_restated(PRE_CHANGE_WHEN))

    def test_the_restatement_forgeries_cover_every_restatement_marker_group(self):
        seen = set()
        for forged in RESTATING_WHENS.values():
            seen.update(restatement_markers(forged))
        for group in ("blob id", "mode", "kind", "git hash-object", "membership", "substitution"):
            self.assertIn(group, seen)

    def test_digest_sentence_matcher_accepts_orchestrator_and_negated_sentences(self):
        self.assertEqual(
            digest_sentence_violations(
                "The orchestrator computes the digest of each path. "
                "The worker does not compute digests."
            ),
            [],
        )

    def test_digest_sentence_matcher_flags_a_sentence_that_names_no_actor(self):
        self.assertEqual(
            digest_sentence_violations("The sha256 is kept. Nothing else."),
            ["The sha256 is kept."],
        )

    def test_a_git_hash_object_sentence_counts_as_a_digest_sentence(self):
        self.assertEqual(
            digest_sentence_violations("Run `git hash-object` on each path."),
            ["Run git hash-object on each path."],
        )

    def test_when_slicer_takes_only_the_when_paragraph_of_the_section(self):
        text = (
            "## Other\n\nWhen: elsewhere.\n\n"
            "## Layer 5 recording\n\nWhen: here,\nwrapped.\n\nZero artifacts: x.\n\n"
            "## Next\n\nWhen: after.\n"
        )
        section = _section(text, SECTION_TITLE)
        self.assertEqual(_when_paragraph(section), "When: here, wrapped.")

    def test_when_slicer_rejects_a_missing_or_a_duplicate_paragraph(self):
        with self.assertRaises(AssertionError):
            _when_paragraph("Zero artifacts: x.\n")
        with self.assertRaises(AssertionError):
            _when_paragraph("When: a.\n\nWhen: b.\n")

    def test_section_slicer_is_fence_aware_and_rejects_duplicate_headings(self):
        text = "## A\nbody a\n```\n## not a heading\n```\n## B\nbody b\n"
        self.assertIn("## not a heading", _section(text, "A"))
        self.assertNotIn("body b", _section(text, "A"))
        with self.assertRaises(AssertionError):
            _section("## A\nx\n## A\ny\n", "A")
        with self.assertRaises(AssertionError):
            _section("## A\nx\n", "B")


# ---------------------------------------------------------------------------
# The real document
# ---------------------------------------------------------------------------


class _OwnerDocumentCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(OWNER_PATH)
        cls.layer5_section = _section(cls.text, SECTION_TITLE)
        cls.pre_dispatch_section = _section(cls.text, PRE_DISPATCH_TITLE)
        cls.when = _when_paragraph(cls.layer5_section)


class TestWhenParagraphLayer4(_OwnerDocumentCase):
    """AC-1 (FR6)."""

    def test_ac1_when_paragraph_still_follows_layer_4_passing_for_the_completed_result(self):
        self.assertFalse(probe_layer_4_statement_missing(self.when), self.when)

    def test_ac1_when_paragraph_is_still_the_first_block_of_the_section(self):
        first = _paragraphs(self.layer5_section)[0]
        self.assertEqual(first, self.when)


class TestWhenParagraphR1Citation(_OwnerDocumentCase):
    """AC-2 (FR6, TM-1)."""

    def test_ac2_when_paragraph_cites_the_owner_path_rule_r1_and_the_timing_name_together(self):
        self.assertFalse(probe_r1_citation_missing(self.when), self.when)

    def test_ac2_calculation_runs_only_after_the_return_time_comparison_has_not_made_the_result_stale(self):
        self.assertFalse(probe_calculation_statement_missing(self.when), self.when)

    def test_ac2_recording_write_happens_only_after_the_return_time_recheck_has_not_made_the_result_stale(self):
        self.assertFalse(probe_recording_statement_missing(self.when), self.when)

    def test_ac2_the_orchestrator_is_the_actor_of_both_statements(self):
        for token in ("`Calculation`", "recording write"):
            with self.subTest(token=token):
                self.assertIn("orchestrator", _sentence_with(self.when, token))

    def test_ac2_the_recheck_term_is_written_in_code_format(self):
        self.assertIn("`return-time recheck`", self.when)


class TestWhenParagraphOrder(_OwnerDocumentCase):
    """AC-3 (FR6)."""

    def test_ac3_calculation_mention_precedes_the_recheck_mention_which_precedes_the_recording_write_mention(self):
        self.assertFalse(probe_order_violated(self.when), self.when)

    def test_ac3_the_calculation_sentence_never_implies_calculation_follows_the_recheck(self):
        sentence = _sentence_with(self.when, "`Calculation`")
        self.assertTrue(sentence)
        self.assertNotIn(_RECHECK_TERM, sentence)


class TestWhenParagraphDoesNotRestateTheRecheck(_OwnerDocumentCase):
    """AC-4 (FR6)."""

    def test_ac4_when_paragraph_restates_neither_the_compared_values_nor_membership_nor_substitution(self):
        self.assertEqual(restatement_markers(self.when), [])

    def test_ac4_when_paragraph_never_names_the_hashing_command(self):
        self.assertNotIn("git hash-object", self.when)


class TestAddedSentencesFollowTheDigestConvention(_OwnerDocumentCase):
    """AC-5 (NFR3), first half."""

    def test_ac5_the_paragraph_adds_sentences_and_each_digest_sentence_among_them_complies(self):
        self.assertTrue(added_sentences(self.when))
        self.assertFalse(
            probe_added_digest_sentence_violates_convention(self.when), self.when
        )

    def test_ac5_the_added_sentences_carry_no_instruction_to_a_worker(self):
        for sentence in added_sentences(self.when):
            with self.subTest(sentence=sentence[:60]):
                self.assertNotRegex(sentence, r"(?i)^(?:the |this )?worker\b")
                self.assertNotRegex(sentence, r"(?i)\byou\b")


class TestRestOfTheDocumentIsUnchanged(_OwnerDocumentCase):
    """AC-5 (NFR3), second half: the rest of "Layer 5 recording" and the final
    paragraph of "Pre-dispatch verification" stay as they were."""

    def test_ac5_layer_5_recording_holds_the_when_paragraph_and_the_three_unchanged_blocks(self):
        self.assertFalse(probe_layer5_rest_changed(self.layer5_section))

    def test_ac5_the_final_paragraph_of_pre_dispatch_verification_is_unchanged(self):
        self.assertFalse(
            probe_pre_dispatch_final_paragraph_changed(self.pre_dispatch_section)
        )


# ---------------------------------------------------------------------------
# AC-6: this file's own conventions
# ---------------------------------------------------------------------------


class TestThisFileConventions(unittest.TestCase):
    """AC-6 (FR8, NFR1, NFR2)."""

    @classmethod
    def setUpClass(cls):
        cls.tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))

    def test_ac6_this_file_imports_only_standard_library_modules(self):
        stdlib = set(sys.stdlib_module_names)
        imported = set()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                self.assertEqual(node.level, 0, "no relative import of a sibling test")
                imported.add((node.module or "").split(".")[0])
        self.assertTrue(imported)
        self.assertEqual(imported - stdlib, set())

    def test_ac6_this_file_follows_the_naming_rules_of_the_test_readme(self):
        for node in self.tree.body:
            if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                self.assertTrue(node.name.startswith("Test"), node.name)
                for item in node.body:
                    if isinstance(item, ast.FunctionDef) and item.name.startswith("test"):
                        self.assertRegex(item.name, r"^test_[a-z0-9_]+$")


if __name__ == "__main__":
    unittest.main()
