"""Document assertions for self-write-exclusivity-window/task0002: the end
point of the exclusivity assumption's interval in the two documents that
state it.

Covers task0002 Acceptance Criteria
(feature-docs/self-write-exclusivity-window/tasks/task0002.md):

- AC-1 (FR3, TM-2): worker-envelope.md, section "Exclusivity assumption
  during dispatch", states the interval from the start of the dispatch's scope
  snapshot capture through the completion of the phase-state write that
  records the run's `artifacts` and `self_write_set`, and no longer ends it at
  the end of that dispatch's scope verification.
- AC-2 (FR3, TM-2): the same section states both variants: a run whose
  `written_artifacts` is empty runs through the write that records its
  returned `status` and `self_write_set`; a result judged stale runs through
  that judgment.
- AC-3 (FR3): the same section keeps the five-worker restriction, the "not a
  standing constraint on the plugin as a whole" clause, the review phase's
  wave-parallel auto-fix loop exception citing `references/review-phase.md`,
  and the quoted assumption text.
- AC-4 (FR4, TM-2): create-spec-phase.md's `**Scope of applicability**`
  paragraph states the same end point and the same two variants, keeps the
  five-worker restriction and the "not a standing constraint" clause, and no
  longer ends at "the end of verification".
- AC-5 (FR3, FR4): one shared extractor reads the end-point elements
  (phase-state write, `artifacts`, `self_write_set`, `status` for the empty
  case, stale judgment) from both slices; both documents carry the same
  element set.
- AC-6 (FR8, NFR1, NFR2, NFR3, NFR5): this file uses only the standard
  library, follows the test/README.md naming rules, slices by heading and
  normalizes whitespace, and pairs every probe with a forged-text control;
  worker-envelope.md carries no `expect_digest` token.

Every assertion runs on a heading-sliced, whitespace-normalized text; none
depends on line-break positions and none compares a whole document. Each
probe is a module-level function returning a list of violations (empty when
the text conforms). Each probe has a forged-text control in
TestProbesFireOnForgedText showing that it fires on the pre-change wording or
on text missing the element, and TestProbesAcceptConformingText shows it stays
quiet on conforming text.

Standard library only; no import of a sibling test module.
"""

import ast
import inspect
import re
import sys
import textwrap
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"
ENVELOPE_PATH = PLUGIN_ROOT / "references" / "contracts" / "worker-envelope.md"
CREATE_SPEC_PATH = PLUGIN_ROOT / "references" / "phases" / "create-spec-phase.md"
THIS_FILE = Path(__file__).resolve()

EM_DASH = "—"

# ---------------------------------------------------------------------------
# Pinned text
# ---------------------------------------------------------------------------

ENVELOPE_HEADING_TITLE_PREFIX = "Exclusivity assumption during dispatch"
CREATE_SPEC_SUBSECTION_TITLE_PREFIX = "Exclusivity assumption (normative)"
CREATE_SPEC_PARAGRAPH_MARKER = "**Scope of applicability**"

# Interval start, as each document words it.
ENVELOPE_START = "from the start of the dispatch's scope snapshot capture"
CREATE_SPEC_START = "from taking the scope snapshot"

# The five elements the two documents share (AC-5).
ELEMENT_PHASE_STATE_WRITE = "phase-state write"
ELEMENT_ARTIFACTS = "artifacts"
ELEMENT_SELF_WRITE_SET = "self_write_set"
ELEMENT_STATUS = "status"
ELEMENT_STALE_JUDGMENT = "stale judgment"
ALL_ELEMENTS = frozenset(
    {
        ELEMENT_PHASE_STATE_WRITE,
        ELEMENT_ARTIFACTS,
        ELEMENT_SELF_WRITE_SET,
        ELEMENT_STATUS,
        ELEMENT_STALE_JUDGMENT,
    }
)

# The fields the empty-written_artifacts variant must record.
EMPTY_CASE_TOKENS = frozenset({"status", "self_write_set"})

# The pre-change endings (forged controls use these exact phrases).
OLD_ENDING_ENVELOPE = "through the end of that dispatch's scope verification"
OLD_ENDING_CREATE_SPEC = "through the end of verification"
OLD_ENDING_RE = re.compile(r"\bend of (?:that dispatch's )?(?:scope )?verification\b")

# The end point clauses. `fields` runs to the next period, semicolon or dash.
_FIELDS = r"(?P<fields>[^.;—]*)"
MAIN_CLAUSE_RE = re.compile(
    r"through the completion of the phase-state write that records " + _FIELDS
)
EMPTY_CLAUSE_RE = re.compile(
    r"`written_artifacts` is empty[^.]*?\bthrough the write that records " + _FIELDS
)
STALE_CLAUSE_RE = re.compile(r"judged stale[^.]*?\bthrough that judgment\b")

ENVELOPE_KEPT_PHRASES = {
    "five-worker restriction": "only to the five workers in the 2.3 applicability table",
    "not a standing constraint": (
        "it is not a standing constraint on the plugin as a whole"
    ),
    "review exception": (
        "The review phase's wave-parallel auto-fix loop "
        "(`references/review-phase.md`) is an explicit exception governed by "
        "its own per-wave verification rules, not by this assumption."
    ),
}
ENVELOPE_QUOTED_ASSUMPTION = (
    "During a worker's dispatch, only the orchestrator and the dispatched "
    "worker may create, modify, or delete files in the integration worktree. "
    "Other processes may advance the integration branch's ref, but must never "
    "touch the worktree's files directly."
)

CREATE_SPEC_KEPT_PHRASES = {
    "five-worker restriction": "only to the five workers in design-input.md 2.3",
    "not a standing constraint": (
        "it is not a standing constraint on the plugin as a whole"
    ),
}
CREATE_SPEC_QUOTED_ASSUMPTION = (
    "While a worker is dispatched, only the orchestrator and that worker may "
    "create, modify, or delete files directly in the integration worktree. "
    "Other processes may advance the integration branch's ref, but must never "
    "touch the worktree's files directly."
)
CREATE_SPEC_SUBSECTION_KEPT_PHRASES = {
    "review-phase exception": (
        "That is an explicit exception governed by `review-phase.md`'s own "
        "per-wave verification rules"
    ),
    "why the assumption holds": "**Why the assumption holds**",
    "not enforced by a lock or a hook": (
        "**This exclusivity is not enforced by a lock or a hook.**"
    ),
}


# ---------------------------------------------------------------------------
# Slicing and normalization
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
    """The raw text of the first level-`level` heading whose title satisfies
    `title_matches`, from its heading line to the next heading of the same or
    a higher level. Headings inside fenced code are ignored. AssertionError
    when the heading is absent."""
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


def _paragraph_starting(text, marker):
    """The raw text of the first blank-line-delimited paragraph that starts
    with `marker`. AssertionError when absent."""
    for block in re.split(r"\n[ \t]*\n", text.replace("\r\n", "\n")):
        if block.lstrip().startswith(marker):
            return block
    raise AssertionError(f"paragraph starting with {marker!r} not found")


def envelope_section(document_text):
    return _section(
        document_text, 2, lambda title: title.startswith(ENVELOPE_HEADING_TITLE_PREFIX)
    )


def create_spec_subsection(document_text):
    return _section(
        document_text,
        3,
        lambda title: title.startswith(CREATE_SPEC_SUBSECTION_TITLE_PREFIX),
    )


def create_spec_scope_paragraph(document_text):
    return _paragraph_starting(
        create_spec_subsection(document_text), CREATE_SPEC_PARAGRAPH_MARKER
    )


def _quoted_text(raw_section):
    """The whitespace-normalized text of the `>` quote lines of a section."""
    lines = [
        re.sub(r"^\s*>\s?", "", line)
        for line in raw_section.splitlines()
        if line.lstrip().startswith(">")
    ]
    return _normalize_ws(" ".join(lines))


# ---------------------------------------------------------------------------
# The end-point extractor (shared by AC-1, AC-2, AC-4 and AC-5)
# ---------------------------------------------------------------------------


def _tokens(fields):
    return frozenset(re.findall(r"`([^`]+)`", fields))


def end_point_elements(raw_text):
    """The set of end-point elements a slice states."""
    text = _normalize_ws(raw_text)
    elements = set()
    main = MAIN_CLAUSE_RE.search(text)
    if main:
        elements.add(ELEMENT_PHASE_STATE_WRITE)
        tokens = _tokens(main.group("fields"))
        if ELEMENT_ARTIFACTS in tokens:
            elements.add(ELEMENT_ARTIFACTS)
        if ELEMENT_SELF_WRITE_SET in tokens:
            elements.add(ELEMENT_SELF_WRITE_SET)
    empty = EMPTY_CLAUSE_RE.search(text)
    if empty and ELEMENT_STATUS in _tokens(empty.group("fields")):
        elements.add(ELEMENT_STATUS)
    if STALE_CLAUSE_RE.search(text):
        elements.add(ELEMENT_STALE_JUDGMENT)
    return frozenset(elements)


# ---------------------------------------------------------------------------
# Probes: each returns a list of violations, empty when the text conforms
# ---------------------------------------------------------------------------


def _old_ending_violations(raw_text):
    """The pre-change ending ("the end of ... verification") still present."""
    text = _normalize_ws(raw_text)
    return [match.group(0) for match in OLD_ENDING_RE.finditer(text)]


def _interval_violations(raw_text, start):
    """The interval does not run from `start` through the completion of the
    phase-state write that records the run's `artifacts` and `self_write_set`."""
    text = _normalize_ws(raw_text)
    pattern = re.compile(
        re.escape(start)
        + r" through the completion of the phase-state write that records "
        + _FIELDS
    )
    match = pattern.search(text)
    if not match:
        return [
            f"no interval {start!r} through the completion of the phase-state "
            "write that records ..."
        ]
    tokens = _tokens(match.group("fields"))
    return [
        f"the recording write does not name `{name}`"
        for name in (ELEMENT_ARTIFACTS, ELEMENT_SELF_WRITE_SET)
        if name not in tokens
    ]


def _variant_violations(raw_text):
    """Either variant missing: the empty-`written_artifacts` run through the
    write that records `status` and `self_write_set`; the stale result through
    that judgment."""
    text = _normalize_ws(raw_text)
    violations = []
    empty = EMPTY_CLAUSE_RE.search(text)
    if not empty:
        violations.append(
            "no variant for a run whose `written_artifacts` is empty "
            "(through the write that records ...)"
        )
    else:
        tokens = _tokens(empty.group("fields"))
        violations.extend(
            f"the empty-`written_artifacts` variant does not name `{name}`"
            for name in sorted(EMPTY_CASE_TOKENS - tokens)
        )
    if not STALE_CLAUSE_RE.search(text):
        violations.append("no variant for a result judged stale (through that judgment)")
    return violations


def _kept_phrase_violations(raw_text, kept_phrases):
    text = _normalize_ws(raw_text)
    return [
        f"{label}: {phrase!r} is missing"
        for label, phrase in kept_phrases.items()
        if phrase not in text
    ]


def _quoted_assumption_violations(raw_section, expected):
    actual = _quoted_text(raw_section)
    if actual != expected:
        return [f"quoted assumption is {actual!r}, expected {expected!r}"]
    return []


def _envelope_violations(raw_section):
    """Everything AC-1, AC-2 and AC-3 pin on the worker-envelope.md section."""
    return (
        _old_ending_violations(raw_section)
        + _interval_violations(raw_section, ENVELOPE_START)
        + _variant_violations(raw_section)
        + _kept_phrase_violations(raw_section, ENVELOPE_KEPT_PHRASES)
        + _quoted_assumption_violations(raw_section, ENVELOPE_QUOTED_ASSUMPTION)
    )


def _create_spec_paragraph_violations(raw_paragraph):
    """Everything AC-4 pins on the `**Scope of applicability**` paragraph."""
    return (
        _old_ending_violations(raw_paragraph)
        + _interval_violations(raw_paragraph, CREATE_SPEC_START)
        + _variant_violations(raw_paragraph)
        + _kept_phrase_violations(raw_paragraph, CREATE_SPEC_KEPT_PHRASES)
    )


def _create_spec_subsection_violations(raw_subsection):
    """What AC-4 keeps unchanged around the paragraph."""
    return _kept_phrase_violations(
        raw_subsection, CREATE_SPEC_SUBSECTION_KEPT_PHRASES
    ) + _quoted_assumption_violations(raw_subsection, CREATE_SPEC_QUOTED_ASSUMPTION)


def _cross_document_mismatches(envelope_slice, create_spec_slice):
    """The two slices must carry the same end-point element set, and that set
    must be the full one (two documents lacking the same element do not agree
    on the end point either)."""
    envelope_elements = end_point_elements(envelope_slice)
    create_spec_elements = end_point_elements(create_spec_slice)
    mismatches = []
    for element in sorted(envelope_elements ^ create_spec_elements):
        holder = "worker-envelope.md" if element in envelope_elements else "create-spec-phase.md"
        mismatches.append(f"{element!r} is stated only in {holder}")
    for element in sorted(ALL_ELEMENTS - (envelope_elements & create_spec_elements)):
        if element in envelope_elements or element in create_spec_elements:
            continue
        mismatches.append(f"{element!r} is stated in neither document")
    return mismatches


def _import_violations(source):
    """Top-level modules this source imports that are not in the standard
    library."""
    violations = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names = [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names = [node.module or ""] if node.level == 0 else ["." * node.level]
        else:
            continue
        for name in names:
            top = name.split(".")[0]
            if top not in sys.stdlib_module_names:
                violations.append(name)
    return violations


TEST_METHOD_SHAPE_RE = re.compile(r"^test_[a-z0-9]+(?:_[a-z0-9]+)+$")


def _naming_violations(test_classes):
    """Test classes must be `Test<Behavior>` and methods
    `test_<condition>_<expected_result>` (test/README.md)."""
    violations = []
    for cls in test_classes:
        if not re.match(r"^Test[A-Z][A-Za-z0-9]*$", cls.__name__):
            violations.append(f"class {cls.__name__}")
        for name, member in inspect.getmembers(cls, predicate=inspect.isfunction):
            if name in unittest.TestCase.__dict__ or name.startswith("_"):
                continue
            if cls.__dict__.get(name) is not member:
                continue
            if not TEST_METHOD_SHAPE_RE.match(name):
                violations.append(f"{cls.__name__}.{name}")
    return violations


PROBE_NAME_RE = re.compile(r"^_[a-z_]+_(?:violations|mismatches)$")


def _uncontrolled_probe_violations(probe_names, control_source):
    """Probes whose name never appears in the forged-text control source."""
    return [name for name in sorted(probe_names) if name not in control_source]


# ---------------------------------------------------------------------------
# Builders for forged and conforming text
# ---------------------------------------------------------------------------

_ENV_QUOTE = (
    "> During a worker's dispatch, only the orchestrator and the dispatched\n"
    "> worker may create, modify, or delete files in the integration worktree.\n"
    "> Other processes may advance the integration branch's ref, but must never\n"
    "> touch the worktree's files directly.\n"
)
_ENV_RESTRICTION = (
    "This assumption applies only to the five workers in the 2.3 applicability "
    "table, and only for the interval"
)
_MAIN_END = (
    "through the completion of the phase-state write that records the run's "
    "`artifacts` and `self_write_set`"
)
_NOT_STANDING = (
    f" {EM_DASH} it is not a standing constraint on the plugin as a whole."
)
_EMPTY_VARIANT = (
    "For a run whose `written_artifacts` is empty, the interval runs through the "
    "write that records its returned `status` and `self_write_set`;"
)
_STALE_VARIANT = "when the result is judged stale, it runs through that judgment."
_ENV_EXCEPTION = ENVELOPE_KEPT_PHRASES["review exception"]


def build_envelope_section(
    *,
    quote=_ENV_QUOTE,
    restriction=_ENV_RESTRICTION,
    start=ENVELOPE_START,
    end=_MAIN_END,
    not_standing=_NOT_STANDING,
    empty_variant=_EMPTY_VARIANT,
    stale_variant=_STALE_VARIANT,
    exception=_ENV_EXCEPTION,
    wrap=72,
    following="## Cross-references\n\n- Question packet and answer structure.\n",
):
    """A worker-envelope.md section; every piece is overridable so a forged
    control changes exactly one element of an otherwise conforming section."""
    paragraph = " ".join(
        part
        for part in (
            f"{restriction} {start} {end}{not_standing}",
            empty_variant,
            stale_variant,
            exception,
        )
        if part
    )
    return (
        "## Exclusivity assumption during dispatch (design-input.md 5.11.3)\n\n"
        + quote
        + "\n"
        + textwrap.fill(paragraph, width=wrap, break_long_words=False, break_on_hyphens=False)
        + "\n\n"
        + following
    )


_CS_QUOTE = (
    "> While a worker is dispatched, only the orchestrator and that worker may\n"
    "> create, modify, or delete files directly in the integration worktree.\n"
    "> Other processes may advance the integration branch's ref, but must never\n"
    "> touch the worktree's files directly.\n"
)
_CS_RESTRICTION = (
    "**Scope of applicability**: this assumption applies only to the five "
    "workers in design-input.md 2.3, for the interval"
)
_CS_AFTER = (
    "The review phase's auto-fix loop runs multiple `review-editor` workers "
    "concurrently against different files in the same integration worktree, in "
    "its wave-parallel mode (`references/review-phase.md`). That is an explicit "
    "exception governed by `review-phase.md`'s own per-wave verification rules; "
    "this design does not change how the review phase verifies (design-input.md "
    "2.2).\n\n"
    "**Why the assumption holds** (verified against the scripts as written):\n\n"
    "- `merge-task.sh` builds its tree in the task worktree.\n\n"
    "**This exclusivity is not enforced by a lock or a hook.** When it is\n"
    "violated, the outcome is not always fail-closed:\n"
)


def build_create_spec_paragraph(
    *,
    restriction=_CS_RESTRICTION,
    start=CREATE_SPEC_START,
    end=_MAIN_END,
    not_standing=_NOT_STANDING,
    empty_variant=_EMPTY_VARIANT,
    stale_variant=_STALE_VARIANT,
    wrap=72,
):
    paragraph = " ".join(
        part
        for part in (
            f"{restriction} {start} {end}{not_standing}",
            empty_variant,
            stale_variant,
        )
        if part
    )
    return textwrap.fill(paragraph, width=wrap, break_long_words=False, break_on_hyphens=False)


def build_create_spec_subsection(
    *,
    quote=_CS_QUOTE,
    paragraph=None,
    after=_CS_AFTER,
    following="### Pre-dispatch containment validation\n\nBefore dispatching a worker.\n",
):
    return (
        "### Exclusivity assumption (normative)\n\n"
        "A snapshot-based approach cannot, by itself, distinguish the dispatched\n"
        "worker from some other process. This is stated as an explicit assumption:\n\n"
        + quote
        + "\n"
        + (build_create_spec_paragraph() if paragraph is None else paragraph)
        + "\n\n"
        + after
        + "\n"
        + following
    )


def pre_change_envelope_section():
    """The section as it read before this change: the interval ends at the end
    of that dispatch's scope verification and no variant is stated."""
    return build_envelope_section(
        end=OLD_ENDING_ENVELOPE, empty_variant="", stale_variant=""
    )


def pre_change_create_spec_paragraph():
    return build_create_spec_paragraph(
        end=OLD_ENDING_CREATE_SPEC, empty_variant="", stale_variant=""
    )


# ---------------------------------------------------------------------------
# AC-1, AC-2, AC-3: worker-envelope.md
# ---------------------------------------------------------------------------


class TestEnvelopeExclusivityInterval(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.section = envelope_section(_read(ENVELOPE_PATH))

    def test_ac1_interval_runs_from_snapshot_start_through_the_recording_write(self):
        self.assertEqual(_interval_violations(self.section, ENVELOPE_START), [])

    def test_ac1_interval_no_longer_ends_at_the_scope_verification(self):
        self.assertEqual(_old_ending_violations(self.section), [])

    def test_ac2_empty_written_artifacts_and_stale_variants_are_both_stated(self):
        self.assertEqual(_variant_violations(self.section), [])

    def test_ac3_section_keeps_the_restriction_clauses_and_the_quoted_assumption(self):
        self.assertEqual(
            _kept_phrase_violations(self.section, ENVELOPE_KEPT_PHRASES), []
        )
        self.assertEqual(
            _quoted_assumption_violations(self.section, ENVELOPE_QUOTED_ASSUMPTION),
            [],
        )

    def test_ac3_section_keeps_its_heading_after_the_known_limit_label(self):
        self.assertTrue(
            self.section.startswith(
                "## Exclusivity assumption during dispatch (design-input.md 5.11.3)"
            )
        )

    def test_ac1_ac2_ac3_every_envelope_probe_is_quiet_on_the_real_section(self):
        self.assertEqual(_envelope_violations(self.section), [])


# ---------------------------------------------------------------------------
# AC-4: create-spec-phase.md
# ---------------------------------------------------------------------------


class TestCreateSpecExclusivityInterval(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        text = _read(CREATE_SPEC_PATH)
        cls.subsection = create_spec_subsection(text)
        cls.paragraph = create_spec_scope_paragraph(text)

    def test_ac4_interval_runs_from_snapshot_start_through_the_recording_write(self):
        self.assertEqual(_interval_violations(self.paragraph, CREATE_SPEC_START), [])

    def test_ac4_interval_no_longer_ends_at_the_end_of_verification(self):
        self.assertEqual(_old_ending_violations(self.paragraph), [])

    def test_ac4_both_variants_are_stated(self):
        self.assertEqual(_variant_violations(self.paragraph), [])

    def test_ac4_paragraph_keeps_the_restriction_and_the_not_standing_clause(self):
        self.assertEqual(
            _kept_phrase_violations(self.paragraph, CREATE_SPEC_KEPT_PHRASES), []
        )

    def test_ac4_subsection_keeps_the_quote_the_exception_and_the_enforcement_note(self):
        self.assertEqual(_create_spec_subsection_violations(self.subsection), [])

    def test_ac4_every_create_spec_probe_is_quiet_on_the_real_paragraph(self):
        self.assertEqual(_create_spec_paragraph_violations(self.paragraph), [])


# ---------------------------------------------------------------------------
# AC-5: the two documents state the same end point
# ---------------------------------------------------------------------------


class TestEndPointAgreesAcrossDocuments(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.envelope = envelope_section(_read(ENVELOPE_PATH))
        cls.paragraph = create_spec_scope_paragraph(_read(CREATE_SPEC_PATH))

    def test_ac5_both_slices_carry_every_end_point_element(self):
        self.assertEqual(end_point_elements(self.envelope), ALL_ELEMENTS)
        self.assertEqual(end_point_elements(self.paragraph), ALL_ELEMENTS)

    def test_ac5_both_slices_carry_the_same_element_set(self):
        self.assertEqual(
            end_point_elements(self.envelope), end_point_elements(self.paragraph)
        )
        self.assertEqual(_cross_document_mismatches(self.envelope, self.paragraph), [])


# ---------------------------------------------------------------------------
# Conforming text keeps every probe quiet (the probes are not always-firing)
# ---------------------------------------------------------------------------


class TestProbesAcceptConformingText(unittest.TestCase):
    def test_conforming_envelope_section_is_accepted_at_any_wrap_width(self):
        for wrap in (30, 72, 400):
            with self.subTest(wrap=wrap):
                section = envelope_section(build_envelope_section(wrap=wrap))
                self.assertEqual(_envelope_violations(section), [])
                self.assertEqual(end_point_elements(section), ALL_ELEMENTS)

    def test_conforming_create_spec_paragraph_is_accepted_at_any_wrap_width(self):
        for wrap in (30, 72, 400):
            with self.subTest(wrap=wrap):
                subsection = build_create_spec_subsection(
                    paragraph=build_create_spec_paragraph(wrap=wrap)
                )
                paragraph = create_spec_scope_paragraph(subsection)
                self.assertEqual(_create_spec_paragraph_violations(paragraph), [])
                self.assertEqual(
                    _create_spec_subsection_violations(
                        create_spec_subsection(subsection)
                    ),
                    [],
                )
                self.assertEqual(end_point_elements(paragraph), ALL_ELEMENTS)

    def test_conforming_pair_with_different_sentence_shape_agrees(self):
        envelope = build_envelope_section()
        reshaped = build_create_spec_paragraph(
            empty_variant=(
                "A run whose `written_artifacts` is empty ends instead at the write, "
                "reached through the write that records its returned `status` and "
                "`self_write_set`;"
            ),
            stale_variant="a result judged stale ends through that judgment.",
        )
        self.assertEqual(_cross_document_mismatches(envelope, reshaped), [])


class TestSlicingByHeading(unittest.TestCase):
    def test_envelope_slice_stops_at_the_next_level_two_heading(self):
        section = envelope_section(build_envelope_section())
        self.assertTrue(section.startswith("## Exclusivity assumption during dispatch"))
        self.assertNotIn("## Cross-references", section)
        self.assertNotIn("Question packet", section)

    def test_create_spec_slice_stops_at_the_next_heading_of_its_level(self):
        subsection = create_spec_subsection(build_create_spec_subsection())
        self.assertTrue(subsection.startswith("### Exclusivity assumption (normative)"))
        self.assertNotIn("### Pre-dispatch containment validation", subsection)

    def test_create_spec_paragraph_is_cut_at_the_blank_line(self):
        paragraph = create_spec_scope_paragraph(build_create_spec_subsection())
        self.assertTrue(paragraph.startswith("**Scope of applicability**"))
        self.assertNotIn("The review phase's auto-fix loop", paragraph)

    def test_a_heading_inside_a_code_fence_does_not_end_the_slice(self):
        text = (
            "## Exclusivity assumption during dispatch\n\n"
            "```\n## not a heading\n```\n\nbody text\n\n## Next\n"
        )
        section = envelope_section(text)
        self.assertIn("body text", section)
        self.assertNotIn("## Next", section)

    def test_a_missing_heading_raises_instead_of_returning_an_empty_slice(self):
        with self.assertRaises(AssertionError):
            envelope_section("## Something else\n\ntext\n")
        with self.assertRaises(AssertionError):
            create_spec_scope_paragraph("### Exclusivity assumption (normative)\n\ntext\n")


# ---------------------------------------------------------------------------
# Forged-text controls: every probe fires on text it must reject
# ---------------------------------------------------------------------------


class TestProbesFireOnForgedText(unittest.TestCase):
    """One forged control per probe, built from the pre-change wording or from
    a conforming text missing exactly one element."""

    # _old_ending_violations
    def test_old_ending_probe_fires_on_the_pre_change_envelope_sentence(self):
        forged = envelope_section(pre_change_envelope_section())
        self.assertEqual(
            _old_ending_violations(forged),
            ["end of that dispatch's scope verification"],
        )

    def test_old_ending_probe_fires_on_the_pre_change_create_spec_sentence(self):
        forged = pre_change_create_spec_paragraph()
        self.assertEqual(_old_ending_violations(forged), ["end of verification"])

    def test_old_ending_probe_fires_on_the_shortened_scope_verification_ending(self):
        forged = build_envelope_section(end="through the end of scope verification")
        self.assertEqual(
            _old_ending_violations(forged), ["end of scope verification"]
        )

    # _interval_violations
    def test_interval_probe_fires_on_the_pre_change_envelope_section(self):
        forged = envelope_section(pre_change_envelope_section())
        self.assertNotEqual(_interval_violations(forged, ENVELOPE_START), [])

    def test_interval_probe_fires_on_the_pre_change_create_spec_paragraph(self):
        forged = pre_change_create_spec_paragraph()
        self.assertNotEqual(_interval_violations(forged, CREATE_SPEC_START), [])

    def test_interval_probe_fires_when_the_recording_write_omits_artifacts(self):
        forged = build_envelope_section(
            end=(
                "through the completion of the phase-state write that records "
                "the run's `self_write_set`"
            )
        )
        self.assertEqual(
            _interval_violations(forged, ENVELOPE_START),
            ["the recording write does not name `artifacts`"],
        )

    def test_interval_probe_fires_when_the_recording_write_omits_self_write_set(self):
        forged = build_envelope_section(
            end=(
                "through the completion of the phase-state write that records "
                "the run's `artifacts`"
            )
        )
        self.assertEqual(
            _interval_violations(forged, ENVELOPE_START),
            ["the recording write does not name `self_write_set`"],
        )

    def test_interval_probe_fires_when_the_write_is_not_the_phase_state_write(self):
        forged = build_envelope_section(
            end=(
                "through the completion of the write that records the run's "
                "`artifacts` and `self_write_set`"
            )
        )
        self.assertEqual(len(_interval_violations(forged, ENVELOPE_START)), 1)

    def test_interval_probe_fires_when_the_interval_does_not_start_at_the_snapshot(self):
        forged = build_envelope_section(start="from the start of the dispatch")
        self.assertEqual(len(_interval_violations(forged, ENVELOPE_START)), 1)

    # _variant_violations
    def test_variant_probe_fires_when_both_variants_are_missing(self):
        forged = envelope_section(pre_change_envelope_section())
        self.assertEqual(len(_variant_violations(forged)), 2)

    def test_variant_probe_fires_when_the_empty_variant_is_missing(self):
        forged = build_envelope_section(empty_variant="")
        violations = _variant_violations(forged)
        self.assertEqual(len(violations), 1)
        self.assertIn("`written_artifacts` is empty", violations[0])

    def test_variant_probe_fires_when_the_empty_variant_omits_status(self):
        forged = build_envelope_section(
            empty_variant=(
                "For a run whose `written_artifacts` is empty, the interval runs "
                "through the write that records its `self_write_set`;"
            )
        )
        self.assertEqual(
            _variant_violations(forged),
            ["the empty-`written_artifacts` variant does not name `status`"],
        )

    def test_variant_probe_fires_when_the_empty_variant_omits_self_write_set(self):
        forged = build_envelope_section(
            empty_variant=(
                "For a run whose `written_artifacts` is empty, the interval runs "
                "through the write that records its returned `status`;"
            )
        )
        self.assertEqual(
            _variant_violations(forged),
            ["the empty-`written_artifacts` variant does not name `self_write_set`"],
        )

    def test_variant_probe_fires_when_status_appears_only_in_the_main_clause(self):
        forged = build_envelope_section(
            end=(
                "through the completion of the phase-state write that records "
                "the run's `artifacts`, `status` and `self_write_set`"
            ),
            empty_variant="",
        )
        self.assertEqual(len(_variant_violations(forged)), 1)

    def test_variant_probe_fires_when_the_stale_variant_is_missing(self):
        forged = build_envelope_section(stale_variant="")
        violations = _variant_violations(forged)
        self.assertEqual(len(violations), 1)
        self.assertIn("judged stale", violations[0])

    def test_variant_probe_fires_when_the_stale_variant_ends_elsewhere(self):
        forged = build_envelope_section(
            stale_variant="when the result is judged stale, it is discarded."
        )
        self.assertEqual(len(_variant_violations(forged)), 1)

    # _kept_phrase_violations
    def test_kept_phrase_probe_fires_without_the_five_worker_restriction(self):
        forged = build_envelope_section(
            restriction="This assumption applies to every worker, and for the interval"
        )
        violations = _kept_phrase_violations(forged, ENVELOPE_KEPT_PHRASES)
        self.assertEqual(len(violations), 1)
        self.assertIn("five-worker restriction", violations[0])

    def test_kept_phrase_probe_fires_without_the_not_standing_constraint_clause(self):
        forged = build_envelope_section(not_standing=".")
        violations = _kept_phrase_violations(forged, ENVELOPE_KEPT_PHRASES)
        self.assertEqual(len(violations), 1)
        self.assertIn("not a standing constraint", violations[0])

    def test_kept_phrase_probe_fires_without_the_review_exception(self):
        forged = build_envelope_section(exception="")
        violations = _kept_phrase_violations(forged, ENVELOPE_KEPT_PHRASES)
        self.assertEqual(len(violations), 1)
        self.assertIn("review exception", violations[0])

    def test_kept_phrase_probe_fires_on_a_review_exception_without_its_citation(self):
        forged = build_envelope_section(
            exception=(
                "The review phase's wave-parallel auto-fix loop is an explicit "
                "exception governed by its own per-wave verification rules, not by "
                "this assumption."
            )
        )
        violations = _kept_phrase_violations(forged, ENVELOPE_KEPT_PHRASES)
        self.assertEqual(len(violations), 1)

    def test_kept_phrase_probe_fires_on_a_create_spec_paragraph_without_the_restriction(self):
        forged = build_create_spec_paragraph(
            restriction=(
                "**Scope of applicability**: this assumption applies to every "
                "worker, for the interval"
            )
        )
        violations = _kept_phrase_violations(forged, CREATE_SPEC_KEPT_PHRASES)
        self.assertEqual(len(violations), 1)
        self.assertIn("five-worker restriction", violations[0])

    def test_kept_phrase_probe_fires_on_a_create_spec_subsection_missing_a_kept_paragraph(self):
        forged = build_create_spec_subsection(
            after="**Why the assumption holds** (verified against the scripts as written):\n"
        )
        violations = _kept_phrase_violations(
            forged, CREATE_SPEC_SUBSECTION_KEPT_PHRASES
        )
        self.assertEqual(len(violations), 2)

    # _quoted_assumption_violations
    def test_quote_probe_fires_on_an_altered_quoted_assumption(self):
        forged = build_envelope_section(
            quote=_ENV_QUOTE.replace("may create, modify, or delete", "may create")
        )
        self.assertEqual(
            len(_quoted_assumption_violations(forged, ENVELOPE_QUOTED_ASSUMPTION)), 1
        )

    def test_quote_probe_fires_when_the_quote_is_gone(self):
        forged = build_envelope_section(quote="")
        self.assertEqual(
            len(_quoted_assumption_violations(forged, ENVELOPE_QUOTED_ASSUMPTION)), 1
        )

    def test_quote_probe_fires_on_an_altered_create_spec_quote(self):
        forged = build_create_spec_subsection(
            quote=_CS_QUOTE.replace("only the orchestrator", "only a process")
        )
        self.assertEqual(
            len(_quoted_assumption_violations(forged, CREATE_SPEC_QUOTED_ASSUMPTION)),
            1,
        )

    # _envelope_violations / _create_spec_paragraph_violations /
    # _create_spec_subsection_violations
    def test_envelope_probe_fires_on_the_pre_change_section(self):
        forged = envelope_section(pre_change_envelope_section())
        violations = _envelope_violations(forged)
        self.assertGreaterEqual(len(violations), 4)
        self.assertIn("end of that dispatch's scope verification", violations)

    def test_create_spec_paragraph_probe_fires_on_the_pre_change_paragraph(self):
        forged = pre_change_create_spec_paragraph()
        violations = _create_spec_paragraph_violations(forged)
        self.assertGreaterEqual(len(violations), 4)
        self.assertIn("end of verification", violations)

    def test_create_spec_subsection_probe_fires_on_a_subsection_without_its_quote(self):
        forged = build_create_spec_subsection(quote="")
        self.assertNotEqual(_create_spec_subsection_violations(forged), [])

    # _cross_document_mismatches
    def test_cross_document_probe_fires_when_the_two_pre_change_slices_agree_on_nothing(self):
        mismatches = _cross_document_mismatches(
            envelope_section(pre_change_envelope_section()),
            pre_change_create_spec_paragraph(),
        )
        self.assertEqual(len(mismatches), len(ALL_ELEMENTS))

    def test_cross_document_probe_fires_when_one_document_lacks_the_stale_judgment(self):
        mismatches = _cross_document_mismatches(
            build_envelope_section(),
            build_create_spec_paragraph(stale_variant=""),
        )
        self.assertEqual(
            mismatches, ["'stale judgment' is stated only in worker-envelope.md"]
        )

    def test_cross_document_probe_fires_when_one_document_lacks_the_empty_case_status(self):
        mismatches = _cross_document_mismatches(
            build_envelope_section(empty_variant=""),
            build_create_spec_paragraph(),
        )
        self.assertEqual(
            mismatches, ["'status' is stated only in create-spec-phase.md"]
        )

    def test_cross_document_probe_fires_when_one_document_lacks_the_phase_state_write(self):
        mismatches = _cross_document_mismatches(
            build_envelope_section(),
            build_create_spec_paragraph(end=OLD_ENDING_CREATE_SPEC),
        )
        self.assertEqual(
            sorted(mismatches),
            [
                "'artifacts' is stated only in worker-envelope.md",
                "'phase-state write' is stated only in worker-envelope.md",
                "'self_write_set' is stated only in worker-envelope.md",
            ],
        )

    def test_cross_document_probe_fires_when_both_documents_lack_the_same_element(self):
        mismatches = _cross_document_mismatches(
            build_envelope_section(stale_variant=""),
            build_create_spec_paragraph(stale_variant=""),
        )
        self.assertEqual(mismatches, ["'stale judgment' is stated in neither document"])

    # _import_violations
    def test_import_probe_fires_on_a_third_party_import(self):
        self.assertEqual(_import_violations("import yaml\n"), ["yaml"])

    def test_import_probe_fires_on_a_from_import_of_a_third_party_module(self):
        self.assertEqual(_import_violations("from yaml import safe_load\n"), ["yaml"])

    def test_import_probe_fires_on_an_import_of_a_sibling_test_module(self):
        self.assertEqual(
            _import_violations("from test_self_write_digest_docs import _read\n"),
            ["test_self_write_digest_docs"],
        )

    def test_import_probe_fires_on_a_relative_import(self):
        self.assertEqual(_import_violations("from . import helpers\n"), ["."])

    # _naming_violations
    def test_naming_probe_fires_on_a_misnamed_class_and_method(self):
        class Checks(unittest.TestCase):
            def test_x(self):
                pass

            def verifies_something(self):
                pass

        violations = _naming_violations([Checks])
        self.assertIn("class Checks", violations)
        self.assertIn("Checks.test_x", violations)
        self.assertIn("Checks.verifies_something", violations)

    # _uncontrolled_probe_violations
    def test_uncontrolled_probe_check_fires_on_a_probe_without_a_control(self):
        self.assertEqual(
            _uncontrolled_probe_violations(
                {"_alpha_violations", "_beta_violations"},
                "assertEqual(_alpha_violations(x), [])",
            ),
            ["_beta_violations"],
        )


# ---------------------------------------------------------------------------
# AC-6: properties of this test file and of worker-envelope.md
# ---------------------------------------------------------------------------


def _own_test_classes():
    module = sys.modules[__name__]
    return [
        cls
        for _, cls in inspect.getmembers(module, predicate=inspect.isclass)
        if issubclass(cls, unittest.TestCase) and cls.__module__ == __name__
    ]


def _own_probe_names():
    module = sys.modules[__name__]
    return {
        name
        for name, member in inspect.getmembers(module, predicate=inspect.isfunction)
        if PROBE_NAME_RE.match(name) and member.__module__ == __name__
    }


class TestThisFileFollowsTheTestConventions(unittest.TestCase):
    def test_ac6_the_file_imports_only_standard_library_modules(self):
        self.assertEqual(_import_violations(THIS_FILE.read_text(encoding="utf-8")), [])

    def test_ac6_the_file_is_named_per_the_test_readme(self):
        self.assertRegex(THIS_FILE.name, r"^test_[a-z0-9_]+\.py$")
        self.assertEqual(THIS_FILE.parent.name, "tests")

    def test_ac6_classes_and_methods_follow_the_naming_rules(self):
        self.assertEqual(_naming_violations(_own_test_classes()), [])

    def test_ac6_every_probe_is_named_in_the_forged_text_controls(self):
        probe_names = _own_probe_names()
        self.assertGreaterEqual(len(probe_names), 9)
        control_source = inspect.getsource(TestProbesFireOnForgedText)
        self.assertEqual(
            _uncontrolled_probe_violations(probe_names, control_source), []
        )


class TestEnvelopeCarriesNoExpectDigestToken(unittest.TestCase):
    def test_ac6_worker_envelope_has_no_expect_digest_token(self):
        self.assertIsNone(
            re.search(r"\bexpect_digest\b", _read(ENVELOPE_PATH)),
            "worker-envelope.md must not gain an expect_digest token (NFR5)",
        )

    def test_ac6_the_no_expect_digest_probe_fires_on_a_forged_token(self):
        forged = "The worker passes expect_digest to the script.\n"
        self.assertIsNotNone(re.search(r"\bexpect_digest\b", forged))


if __name__ == "__main__":
    unittest.main()
