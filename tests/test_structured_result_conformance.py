"""Tests for task0004 (batch-structured-result-output): conformance of the
structured result's document shape (SC1) and escaping rule (SC3) against a
real YAML parser.

Covers task0004 Acceptance Criteria
(feature-docs/batch-structured-result-output/tasks/task0004.md):

- AC-1 (TS1): for each `state` value, an assembled representative document
  loads under a strict YAML load to exactly one mapping whose keys equal
  SC1's set, whose written key order equals SC1's order, whose eight values
  are all strings, and which is exactly eight physical lines with nothing
  before or after it.
- AC-2 (TS2): all 14 adversarial source values round-trip to values equal to
  the source, in every one of the eight key positions; the case list is
  asserted to hold exactly 14 members.
- AC-3: a reference applier that emits a literal newline instead of its
  escape fails the round-trip assertion.
- AC-4 (TS3): a `detail` source containing CR / LF / TAB and space runs
  yields an emitted value with no newline escape and no repeated space; an
  empty normalized `detail` yields the fixed non-empty placeholder.
- AC-5 (TS3): a `resume_conditions` source containing newlines, indentation
  and trailing spaces yields an emitted value carrying newline escapes, and
  round-trips with its indentation and trailing spaces intact.
- AC-7 (partial): this module is discovered by
  `python3 -m unittest discover -s tests`, runs with zero skipped tests when
  PyYAML is installed, and imports no third-party module other than PyYAML
  (IMPLEMENTATION.md D6 -- the single named exception to NFR4).

Per IMPLEMENTATION.md D5, this module declares SC1 independently as a
canonical constant below. Its escaping copy (`_DIRECT_ESCAPES` /
`_needs_unicode_escape`, derived from `_RESIDUAL_RANGES`) and its
`state`/`step`/`reason` samples are bound to the SSOT instead of declared
independently: SC12
(feature-docs/batch-structured-result-output/tasks/task0009.md) is a
named, scoped exception to D5, admissible only because task0008's plan
fixes `## Escaping` and `## Result format` as byte-identical across this
round, and leaves `## Stop reason codes` and the `state`/`step`/`reason`
bullets of `## Field values` unrewritten (task0009's AC-5) -- so no
concurrent task's unmerged edit can affect what is read here. This module
reads exactly those sections of
`em-workflow/references/batch-terminal-line.md` and no other. The escaping
rule (`escape_value`) is written directly from the SSOT-bound table and
residual ranges, with no reliance on any language-provided string-escaping
helper, so the conformance below is never vacuous against Python's own
quoting rules.

Matcher -> negative-proof / non-vacuity inventory (NFR4):

- `_assert_escaping_copy_bound_to_ssot` (SC12): negative proofs are
  `test_forged_copy_missing_a_direct_escape_row_is_rejected` and
  `test_forged_copy_missing_a_residual_range_is_rejected`; non-vacuity is
  `test_direct_escapes_and_residual_ranges_match_ssot`.
- `_assert_sample_conforms_to_ssot_domains` (SC12): negative proof is
  `test_forged_sample_with_out_of_domain_reason_is_rejected`; non-vacuity is
  `test_each_representative_sample_conforms_to_ssot_domains`.
- the banned-reason-literal self-check (AC-1) is a pure absence check with
  no separate negative-proof case; `TestBannedReasonLiteralAbsent` is its
  own module-source non-vacuity guard.

- `escape_value` / the round-trip assertion: negative proof is
  `TestRoundTripIsNotVacuous.test_broken_lf_escaping_fails_the_round_trip`
  (AC-3); its non-vacuity companion is
  `test_correct_escaping_of_the_same_source_does_round_trip`.
- `_well_formed_violations` (SC1 shape checker): negative proofs are
  `test_a_leading_blank_line_is_flagged`,
  `test_an_extra_trailing_key_is_flagged` and
  `test_a_reordered_key_pair_is_flagged`; its non-vacuity companion is
  `test_a_real_assembled_document_has_no_violations`.
- `normalize_detail`: non-vacuity is
  `test_normalization_is_not_vacuous_against_an_identity_function`.
- the stdlib-plus-yaml import checker: negative proof is
  `test_checker_rejects_a_forged_extra_third_party_import`; non-vacuity is
  `test_checker_accepts_a_forged_stdlib_and_yaml_only_source`.
- the 14-case adversarial list: non-vacuity is
  `test_exactly_fourteen_adversarial_cases_are_declared` (a silently dropped
  case shrinks this count instead of failing loudly elsewhere).
"""

import ast
import re
import sys
import unittest
from pathlib import Path

try:
    import yaml
except ImportError:  # pragma: no cover -- exercised only without PyYAML
    yaml = None


_SKIP_REASON = (
    "PyYAML is not installed; the conformance suite cannot verify NFR3 "
    "against a real parser. IMPLEMENTATION.md D6: a skip here is a FAILED "
    "verification item, not a pass."
)


# --- SC1 canonical constant (IMPLEMENTATION.md "Shared Components").
# Declared independently per D5. -------------------------------------------

KEYS = (
    "state",
    "step",
    "reason",
    "detail",
    "feature",
    "branch",
    "pr_url",
    "resume_conditions",
)

STATE_VALUES = ("completed", "stopped", "phase_done")  # SPEC.md FR13

_DIRECT_ESCAPES = {
    "\\": "\\\\",
    '"': '\\"',
    "\r": "\\r",
    "\n": "\\n",
    "\t": "\\t",
}

# The residual code-point ranges SC3's rule sends to a `\uXXXX` escape, as
# (lo, hi) tuples -- single code points are (x, x). Bound to the SSOT's
# residual-range sentence below (SC12); `_needs_unicode_escape` is derived
# from this tuple rather than restating the ranges a second time.
_RESIDUAL_RANGES = (
    (0x0000, 0x001F),
    (0x007F, 0x009F),
    (0x2028, 0x2028),
    (0x2029, 0x2029),
    (0xFFFE, 0xFFFE),
    (0xFFFF, 0xFFFF),
)


def _needs_unicode_escape(code_point):
    return any(lo <= code_point <= hi for lo, hi in _RESIDUAL_RANGES)


# --- SC12: reads `em-workflow/references/batch-terminal-line.md` to bind
# this module's escaping copy and its `state`/`step`/`reason` samples to
# the SSOT. Scoped exception to D5 (see module docstring); reads exactly
# `## Escaping`, `## Stop reason codes` and the `state`/`step`/`reason`
# bullets of `## Field values`, and no other section. ----------------------

_SSOT_PATH = (
    Path(__file__).resolve().parent.parent
    / "em-workflow"
    / "references"
    / "batch-terminal-line.md"
)

_HEADING_RE = re.compile(r"^## (.+?)\s*$", re.MULTILINE)


def _ssot_text():
    return _SSOT_PATH.read_text(encoding="utf-8")


def _normalize(text):
    """Collapses whitespace runs (including line wraps) to a single space --
    used only for the prose-bullet extractors below, never for table
    extraction, which depends on newlines as row delimiters."""
    return re.sub(r"\s+", " ", text)


def _ssot_sections(text):
    """Splits `text` into a dict keyed by level-2 heading text, each value
    the body up to the next level-2 heading (or end of text)."""
    matches = list(_HEADING_RE.finditer(text))
    sections = {}
    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[match.group(1)] = text[start:end]
    return sections


def _table_rows(section_text):
    """Yields each data row of a Markdown table in `section_text` as a list
    of cell strings, skipping the header row and the `---` separator row."""
    raw_rows = []
    for line in section_text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if all(c and set(c) <= {"-", " ", ":"} for c in cells):
            continue  # separator row, e.g. |---|---|---|
        raw_rows.append(cells)
    return raw_rows[1:] if raw_rows else []


_BACKTICK_SINGLE_CHAR_RE = re.compile(r"^`(.)`$")
_NAMED_CODEPOINT_RE = re.compile(r"^[A-Z]+ \(U\+([0-9A-Fa-f]{4,6})\)$")


def _parse_escaping_source_cell(cell):
    """Parses `## Escaping`'s first-column cell into the literal source
    character it names -- either a single backticked character or a named
    "NAME (U+XXXX)" form. Returns None for a cell of neither shape."""
    backtick_match = _BACKTICK_SINGLE_CHAR_RE.match(cell)
    if backtick_match is not None:
        return backtick_match.group(1)
    named_match = _NAMED_CODEPOINT_RE.match(cell)
    if named_match is not None:
        return chr(int(named_match.group(1), 16))
    return None


def _parse_escaping_emitted_cell(cell):
    """Parses `## Escaping`'s second-column cell (always backticked) into
    the literal emitted string. Returns None if not backtick-wrapped."""
    if len(cell) >= 2 and cell.startswith("`") and cell.endswith("`"):
        return cell[1:-1]
    return None


def _extract_direct_escapes_from_ssot(escaping_section_text):
    """Extracts `## Escaping`'s table into a {source_char: emitted_str}
    dict. Returns (mapping, malformed_rows) -- a non-empty malformed_rows
    means a row's cells did not parse, so a caller can fail loudly instead
    of silently dropping a row."""
    mapping = {}
    malformed = []
    for row in _table_rows(escaping_section_text):
        source_char = _parse_escaping_source_cell(row[0])
        emitted_str = _parse_escaping_emitted_cell(row[1])
        if source_char is None or emitted_str is None:
            malformed.append(tuple(row))
        else:
            mapping[source_char] = emitted_str
    return mapping, malformed


_RESIDUAL_RANGE_SENTENCE_RE = re.compile(
    r"falls in (.+?) becomes a backslash", re.DOTALL
)
_RESIDUAL_RANGE_TOKEN_RE = re.compile(
    r"U\+([0-9A-Fa-f]{4,6})(?:-U\+([0-9A-Fa-f]{4,6}))?"
)


def _extract_residual_ranges_from_ssot(escaping_section_text):
    """Extracts the ordered (lo, hi) code-point range tuples named in the
    residual-range sentence following `## Escaping`'s table. Returns None
    when the sentence is not found."""
    sentence_match = _RESIDUAL_RANGE_SENTENCE_RE.search(escaping_section_text)
    if sentence_match is None:
        return None
    ranges = []
    for token_match in _RESIDUAL_RANGE_TOKEN_RE.finditer(sentence_match.group(1)):
        lo = int(token_match.group(1), 16)
        hi = int(token_match.group(2), 16) if token_match.group(2) else lo
        ranges.append((lo, hi))
    return ranges


def _assert_escaping_copy_bound_to_ssot(test, direct_escapes, residual_ranges):
    """AC-4/SC12: binds this module's executable escaping copy to the
    SSOT's `## Escaping` table and residual-range sentence. Fails loudly
    (never a vacuous pass) if either extraction comes back empty or
    unparsed."""
    escaping_section = _ssot_sections(_ssot_text())["Escaping"]

    extracted_pairs, malformed_rows = _extract_direct_escapes_from_ssot(
        escaping_section
    )
    test.assertEqual(
        malformed_rows, [], f"unparsed `## Escaping` row(s): {malformed_rows}"
    )
    test.assertGreater(len(extracted_pairs), 0)
    test.assertEqual(direct_escapes, extracted_pairs)

    extracted_ranges = _extract_residual_ranges_from_ssot(escaping_section)
    test.assertIsNotNone(
        extracted_ranges, "residual-range sentence not found in `## Escaping`"
    )
    test.assertGreater(len(extracted_ranges), 0)
    test.assertEqual(list(residual_ranges), extracted_ranges)


_BACKTICK_CELL_RE = re.compile(r"^`([^`]+)`$")
_BACKTICK_TOKEN_RE = re.compile(r"`([a-zA-Z0-9_-]+)`")
_STATE_DOMAIN_RE = re.compile(r"`state` [—-]+ the run's terminal outcome: (.+?)\.")
_STEP_IDS_RE = re.compile(r"the seven `workflow\.yaml` step ids \(([^)]*)\)")
_STEP_SENTINEL_RE = re.compile(r"single sentinel `([a-z-]+)`")
_COMPLETED_STEP_RE = re.compile(
    r"When `state` is `completed` the value is always `([a-z-]+)`"
)


def _extract_reason_codes_from_ssot(stop_reason_codes_section_text):
    """Extracts `## Stop reason codes`'s table into the ordered list of
    reason codes. Returns (codes, malformed_cells)."""
    codes = []
    malformed = []
    for row in _table_rows(stop_reason_codes_section_text):
        match = _BACKTICK_CELL_RE.match(row[0])
        if match is None:
            malformed.append(row[0])
        else:
            codes.append(match.group(1))
    return codes, malformed


def _ssot_domains():
    """Reads `## Stop reason codes` and the `state`/`step`/`reason`
    bullets of `## Field values` into the closed domains AC-1/AC-2/AC-3
    bind samples against, plus FR13's `completed` -> `retrospect` value."""
    sections = _ssot_sections(_ssot_text())
    field_values = _normalize(sections["Field values"])
    reason_codes, malformed = _extract_reason_codes_from_ssot(
        sections["Stop reason codes"]
    )
    state_match = _STATE_DOMAIN_RE.search(field_values)
    step_ids_match = _STEP_IDS_RE.search(field_values)
    step_sentinel_match = _STEP_SENTINEL_RE.search(field_values)
    completed_step_match = _COMPLETED_STEP_RE.search(field_values)
    step_domain = None
    if step_ids_match is not None and step_sentinel_match is not None:
        step_domain = _BACKTICK_TOKEN_RE.findall(step_ids_match.group(1)) + [
            step_sentinel_match.group(1)
        ]
    return {
        "state_domain": (
            _BACKTICK_TOKEN_RE.findall(state_match.group(1))
            if state_match is not None
            else None
        ),
        "step_domain": step_domain,
        "reason_codes": reason_codes,
        "reason_codes_malformed": malformed,
        "completed_step": (
            completed_step_match.group(1) if completed_step_match is not None else None
        ),
    }


def _assert_sample_conforms_to_ssot_domains(test, values):
    """AC-1/AC-2/AC-3/SC12: `values['state']`, `values['step']` and
    `values['reason']` are members of the SSOT's closed domains -- `reason`
    additionally restricted to the reserved `none` only for a `state` that
    permits it (never `stopped`) -- and, when `state` is `completed`,
    `step` equals the SSOT's `completed` -> `retrospect` rule (FR13). All
    domains are read from the SSOT rather than declared as fixed literals
    here."""
    domains = _ssot_domains()
    test.assertEqual(domains["reason_codes_malformed"], [])
    test.assertGreater(len(domains["reason_codes"]), 0)
    test.assertIsNotNone(domains["state_domain"])
    test.assertGreater(len(domains["state_domain"]), 0)
    test.assertIsNotNone(domains["step_domain"])
    test.assertGreater(len(domains["step_domain"]), 0)
    test.assertIsNotNone(domains["completed_step"])

    test.assertIn(values["state"], domains["state_domain"])
    test.assertIn(values["step"], domains["step_domain"])
    allowed_reasons = set(domains["reason_codes"]) | {"none"}
    test.assertIn(values["reason"], allowed_reasons)
    if values["state"] == "stopped":
        test.assertNotEqual(values["reason"], "none")
    if values["state"] == "completed":
        test.assertEqual(values["step"], domains["completed_step"])


def escape_value(source):
    """SC3's canonical escaping rule: applied character by character, left
    to right, never re-processing a character the rule has just generated.
    Every character not covered by `_DIRECT_ESCAPES` or the residual ranges
    is emitted unchanged, including non-BMP characters."""
    out = []
    for char in source:
        direct = _DIRECT_ESCAPES.get(char)
        if direct is not None:
            out.append(direct)
            continue
        code_point = ord(char)
        if _needs_unicode_escape(code_point):
            out.append("\\u%04x" % code_point)
        else:
            out.append(char)
    return "".join(out)


def assemble(values):
    """SC1's eight-line document: each of the eight keys, in order, each
    once, at line start, each value a double-quoted scalar escaped per
    SC3."""
    lines = [f'{key}: "{escape_value(values[key])}"' for key in KEYS]
    return "\n".join(lines) + "\n"


# --- SC1 shape checker (raw text, independent of any parser) -------------

_LINE_RE = re.compile(r'^([a-z_]+): "(.*)"$')


def _well_formed_violations(text):
    """Returns the list of SC1 shape violations found in `text` (empty list
    means well-formed). Checked over the raw text, independent of YAML
    parsing, so it also catches a key-order violation a parser's dict could
    hide."""
    violations = []
    if text.startswith("\n") or text.startswith(" "):
        violations.append("leading-blank-or-space")
    if not text.endswith("\n"):
        violations.append("missing-trailing-newline")
    parts = text.split("\n")
    if parts and parts[-1] == "":
        parts = parts[:-1]
    else:
        violations.append("no-final-newline-terminated-line")
    if len(parts) != len(KEYS):
        violations.append(f"expected-{len(KEYS)}-physical-lines-got-{len(parts)}")
    written_keys = []
    for line in parts:
        match = _LINE_RE.match(line)
        if match is None:
            violations.append(f"malformed-line:{line!r}")
        else:
            written_keys.append(match.group(1))
    if written_keys != list(KEYS):
        violations.append(f"key-order-mismatch:{written_keys}")
    return violations


def _representative_values(state):
    if state == "completed":
        return {
            "state": "completed",
            "step": "retrospect",
            "reason": "none",
            "detail": "Completed the run without incident.",
            "feature": "sample-feature",
            "branch": "em-workflow/sample-feature/integration",
            "pr_url": "",
            "resume_conditions": "",
        }
    if state == "phase_done":
        return {
            "state": "phase_done",
            "step": "verify",
            "reason": "none",
            "detail": "Finished the current phase.",
            "feature": "sample-feature",
            "branch": "",
            "pr_url": "",
            "resume_conditions": "",
        }
    if state == "stopped":
        return {
            "state": "stopped",
            "step": "implement",
            "reason": "step_stuck",
            "detail": "Stopped pending a required decision.",
            "feature": "sample-feature",
            "branch": "",
            "pr_url": "",
            "resume_conditions": "Resolve the pending question, then resume.",
        }
    raise ValueError(f"unrepresented state: {state!r}")


class TestDocumentShapePerState(unittest.TestCase):
    """AC-1 / TS1 (FR2, FR3, FR4, FR6): a representative document per
    `state` value loads to exactly one well-formed eight-key mapping."""

    @unittest.skipUnless(yaml is not None, _SKIP_REASON)
    def test_each_state_produces_a_single_eight_key_string_mapping(self):
        for state in STATE_VALUES:
            with self.subTest(state=state):
                doc = assemble(_representative_values(state))
                self.assertEqual(_well_formed_violations(doc), [])
                documents = list(yaml.safe_load_all(doc))
                self.assertEqual(len(documents), 1)
                loaded = documents[0]
                self.assertIsInstance(loaded, dict)
                self.assertEqual(set(loaded.keys()), set(KEYS))
                self.assertEqual(list(loaded.keys()), list(KEYS))
                for key in KEYS:
                    with self.subTest(key=key):
                        self.assertIsInstance(loaded[key], str)

    def test_state_values_enumerated_are_exactly_the_three_domain_members(self):
        # Non-vacuity: guards against silently losing a state from the loop
        # above (SPEC.md FR13).
        self.assertEqual(
            set(STATE_VALUES), {"completed", "stopped", "phase_done"}
        )


class TestWellFormedDocumentChecker(unittest.TestCase):
    """Negative proof + non-vacuity for `_well_formed_violations` (NFR4).
    Exercised without needing the YAML parser, so it always runs."""

    def test_a_real_assembled_document_has_no_violations(self):
        doc = assemble(_representative_values("completed"))
        self.assertEqual(_well_formed_violations(doc), [])

    def test_a_leading_blank_line_is_flagged(self):
        doc = "\n" + assemble(_representative_values("completed"))
        self.assertIn("leading-blank-or-space", _well_formed_violations(doc))

    def test_an_extra_trailing_key_is_flagged(self):
        doc = assemble(_representative_values("completed"))
        forged = doc + 'extra: "unexpected"\n'
        violations = _well_formed_violations(forged)
        self.assertTrue(any("physical-lines" in v for v in violations))
        self.assertTrue(any("key-order-mismatch" in v for v in violations))

    def test_a_reordered_key_pair_is_flagged(self):
        values = _representative_values("completed")
        lines = [f'{key}: "{escape_value(values[key])}"' for key in KEYS]
        lines[0], lines[1] = lines[1], lines[0]  # swap state/step
        forged = "\n".join(lines) + "\n"
        violations = _well_formed_violations(forged)
        self.assertTrue(any("key-order-mismatch" in v for v in violations))


class TestEscapingCopyBoundToSSOT(unittest.TestCase):
    """AC-4 (SC12): this module's executable escaping copy (`_DIRECT_ESCAPES`
    / `_RESIDUAL_RANGES`, the source `_needs_unicode_escape` is derived
    from) is bound to the SSOT's `## Escaping` table and residual-range
    sentence -- both the direct-escape pairs and the residual ranges."""

    def test_direct_escapes_and_residual_ranges_match_ssot(self):
        _assert_escaping_copy_bound_to_ssot(self, _DIRECT_ESCAPES, _RESIDUAL_RANGES)

    def test_forged_copy_missing_a_direct_escape_row_is_rejected(self):
        forged = dict(_DIRECT_ESCAPES)
        del forged["\n"]
        with self.assertRaises(AssertionError):
            _assert_escaping_copy_bound_to_ssot(self, forged, _RESIDUAL_RANGES)

    def test_forged_copy_missing_a_residual_range_is_rejected(self):
        forged = _RESIDUAL_RANGES[:-1]  # drops the U+FFFF row
        with self.assertRaises(AssertionError):
            _assert_escaping_copy_bound_to_ssot(self, _DIRECT_ESCAPES, forged)


# AC-1: neither this module nor test_structured_result_consumer_constraints.py
# may contain, as contiguous source text, the specific out-of-domain `reason`
# literal review round 1 found in the old samples -- it names no code the
# SSOT's `## Stop reason codes` table lists. Built from two fragments so this
# check does not itself reintroduce the exact banned contiguous text.
_BANNED_REASON_LITERAL = "awaiting_user" + "_input"


class TestBannedReasonLiteralAbsent(unittest.TestCase):
    """AC-1: the specific out-of-domain `reason` literal review round 1
    found is absent from this module's own source."""

    def test_banned_reason_literal_is_absent_from_this_module(self):
        source = Path(__file__).read_text(encoding="utf-8")
        self.assertNotIn(_BANNED_REASON_LITERAL, source)


class TestRepresentativeSamplesConformToSSOTDomains(unittest.TestCase):
    """AC-1 / AC-3 (SC12): each state's representative sample draws
    `state`/`step`/`reason` from the SSOT's closed domains, checked as
    properties read from the SSOT rather than as fixed literals here."""

    def test_each_representative_sample_conforms_to_ssot_domains(self):
        for state in STATE_VALUES:
            with self.subTest(state=state):
                _assert_sample_conforms_to_ssot_domains(
                    self, _representative_values(state)
                )

    def test_forged_sample_with_out_of_domain_reason_is_rejected(self):
        baseline = _representative_values("stopped")
        forged = dict(baseline)
        forged["reason"] = "made_up_reason_not_in_domain"
        with self.assertRaises(AssertionError):
            _assert_sample_conforms_to_ssot_domains(self, forged)
        # Non-vacuity: the forged sample differs from the otherwise-valid
        # representative sample in `reason` only.
        unchanged = {k: v for k, v in forged.items() if k != "reason"}
        baseline_without_reason = {k: v for k, v in baseline.items() if k != "reason"}
        self.assertEqual(unchanged, baseline_without_reason)


# --- TS2: the 14 adversarial cases ----------------------------------------

ADVERSARIAL_CASES = (
    ("empty_string", ""),
    ("literal_null", "null"),
    ("literal_true", "true"),
    ("literal_zero", "0"),
    ("leading_colon_space", ": leading colon space"),
    ("leading_hyphen_space", "- leading hyphen space"),
    ("leading_hash", "#leading hash comment look-alike"),
    ("colon_space_hash_sequence", "value with : # sequence inside"),
    ("embedded_lf", "first line\nsecond line"),
    ("embedded_crlf", "first line\r\nsecond line"),
    ("embedded_tab", "left\tright"),
    ("embedded_quotes_and_backslashes", 'say "hi" then \\ backslash'),
    ("non_bmp_emoji", "before \U0001F600 after"),
    (
        "c0_c1_line_separator_noncharacter_mix",
        "\x00\x01\x1b\x7f\x80\x9f  ￾￿",
    ),
)

ALREADY_ESCAPED_CASE = "literal backslash-n stays put: \\n end"


def _values_with_case_at(key, value):
    values = {k: "baseline-value" for k in KEYS}
    values[key] = value
    return values


@unittest.skipUnless(yaml is not None, _SKIP_REASON)
class TestAdversarialEscapingRoundTrip(unittest.TestCase):
    """AC-2 / TS2 (FR5, NFR3): all 14 adversarial values round-trip through
    SC3's escaping rule and a real YAML parser, in every key position."""

    def test_exactly_fourteen_adversarial_cases_are_declared(self):
        self.assertEqual(len(ADVERSARIAL_CASES), 14)

    def test_case_names_are_unique(self):
        names = [name for name, _ in ADVERSARIAL_CASES]
        self.assertEqual(len(names), len(set(names)))

    def test_each_case_round_trips_in_every_key_position(self):
        for name, value in ADVERSARIAL_CASES:
            for key in KEYS:
                with self.subTest(case=name, key=key):
                    doc = assemble(_values_with_case_at(key, value))
                    loaded = yaml.safe_load(doc)
                    self.assertEqual(loaded[key], value)

    def test_control_and_noncharacter_mix_round_trips_by_code_point(self):
        # Edge case: assert code-point equality, not visual equality, so a
        # parser that silently normalized a noncharacter would be caught.
        value = dict(ADVERSARIAL_CASES)["c0_c1_line_separator_noncharacter_mix"]
        loaded = yaml.safe_load(assemble(_values_with_case_at("detail", value)))
        self.assertEqual(
            [ord(c) for c in loaded["detail"]], [ord(c) for c in value]
        )


@unittest.skipUnless(yaml is not None, _SKIP_REASON)
class TestAlreadyEscapedSequenceIsNeverReprocessed(unittest.TestCase):
    """Test Notes edge case: a source value that is already an escape
    sequence in text form must emit a doubled backslash and survive the
    round trip unchanged -- the "never re-process a generated escape"
    rule."""

    def test_round_trips_unchanged(self):
        doc = assemble(_values_with_case_at("detail", ALREADY_ESCAPED_CASE))
        loaded = yaml.safe_load(doc)
        self.assertEqual(loaded["detail"], ALREADY_ESCAPED_CASE)

    def test_emitted_text_carries_a_doubled_backslash(self):
        doc = assemble(_values_with_case_at("detail", ALREADY_ESCAPED_CASE))
        line = next(l for l in doc.splitlines() if l.startswith("detail:"))
        self.assertIn("\\\\n", line)


# --- AC-3: the round-trip assertion is not vacuous ------------------------


def _broken_escape_value_missing_lf_escape(source):
    """Deliberately buggy variant of `escape_value` that forgets to escape
    LF, used only as AC-3's non-vacuity proof for the round-trip check."""
    out = []
    for char in source:
        if char == "\\":
            out.append("\\\\")
        elif char == '"':
            out.append('\\"')
        elif char == "\r":
            out.append("\\r")
        elif char == "\n":
            out.append(char)  # BUG: should escape to "\\n"
        elif char == "\t":
            out.append("\\t")
        else:
            code_point = ord(char)
            if _needs_unicode_escape(code_point):
                out.append("\\u%04x" % code_point)
            else:
                out.append(char)
    return "".join(out)


def _assemble_with_escaper(values, escaper):
    lines = [f'{key}: "{escaper(values[key])}"' for key in KEYS]
    return "\n".join(lines) + "\n"


@unittest.skipUnless(yaml is not None, _SKIP_REASON)
class TestRoundTripIsNotVacuous(unittest.TestCase):
    """AC-3: a reference applier that emits a literal newline instead of its
    escape fails the round-trip assertion -- proving the round trip is doing
    work rather than passing trivially."""

    def test_broken_lf_escaping_fails_the_round_trip(self):
        source = "first line\nsecond line"
        values = _values_with_case_at("detail", source)
        broken_doc = _assemble_with_escaper(
            values, _broken_escape_value_missing_lf_escape
        )
        loaded = yaml.safe_load(broken_doc)
        self.assertNotEqual(loaded["detail"], source)

    def test_correct_escaping_of_the_same_source_does_round_trip(self):
        # Non-vacuity: the same source, correctly escaped, must succeed --
        # otherwise the negative proof above could be failing for an
        # unrelated reason.
        source = "first line\nsecond line"
        doc = assemble(_values_with_case_at("detail", source))
        loaded = yaml.safe_load(doc)
        self.assertEqual(loaded["detail"], source)


# --- TS3: detail normalizes then escapes; resume_conditions escapes only -

_DETAIL_EMPTY_PLACEHOLDER = "(no detail recorded)"


def normalize_detail(source):
    """FR7's normalization: CR/LF/TAB collapse to a single space, runs of
    spaces collapse, the result is trimmed, and a fixed non-empty
    placeholder is substituted when that leaves nothing. Applied BEFORE
    escaping, never after (FR7's ordering). `_DETAIL_EMPTY_PLACEHOLDER` is a
    test-local stand-in for the real placeholder text, which is
    task0001/SSOT territory (D5) -- only the normalize-then-escape mechanism
    is under test here, not the literal wording."""
    translated = source.translate({0x0D: " ", 0x0A: " ", 0x09: " "})
    collapsed = re.sub(" +", " ", translated)
    trimmed = collapsed.strip()
    return trimmed if trimmed else _DETAIL_EMPTY_PLACEHOLDER


class TestDetailNormalizationThenEscaping(unittest.TestCase):
    """AC-4 / TS3 (FR7): detail normalizes before it escapes, so no
    newline/tab escape and no repeated space ever reach the emitted
    value."""

    def test_cr_lf_tab_and_space_runs_collapse_to_single_spaces(self):
        source = "line one\r\nline two\ttabbed   multiple   spaces  "
        normalized = normalize_detail(source)
        self.assertNotIn("\r", normalized)
        self.assertNotIn("\n", normalized)
        self.assertNotIn("\t", normalized)
        self.assertNotIn("  ", normalized)  # no repeated space

    @unittest.skipUnless(yaml is not None, _SKIP_REASON)
    def test_emitted_detail_carries_no_newline_escape(self):
        source = "line one\r\nline two\ttabbed   multiple   spaces  "
        values = _values_with_case_at("detail", normalize_detail(source))
        doc = assemble(values)
        line = next(l for l in doc.splitlines() if l.startswith("detail:"))
        self.assertNotIn("\\n", line)
        self.assertNotIn("\\r", line)
        self.assertNotIn("\\t", line)

    def test_whitespace_only_source_normalizes_to_the_fixed_placeholder(self):
        self.assertEqual(
            normalize_detail("\r\n\t   "), _DETAIL_EMPTY_PLACEHOLDER
        )
        self.assertNotEqual(_DETAIL_EMPTY_PLACEHOLDER, "")

    def test_normalization_is_not_vacuous_against_an_identity_function(self):
        # Non-vacuity: an identity "normalizer" (the bug this rule guards
        # against) would leave the newline/tab intact -- proving the
        # assertions above are actually exercising normalize_detail.
        source = "line one\r\nline two\ttabbed"
        self.assertIn("\n", source)
        self.assertNotIn("\n", normalize_detail(source))


@unittest.skipUnless(yaml is not None, _SKIP_REASON)
class TestResumeConditionsEscapingOnly(unittest.TestCase):
    """AC-5 / TS3 (FR8): resume_conditions is never detail-normalized; its
    newlines, indentation and trailing spaces all survive as escapes."""

    def test_emitted_value_carries_newline_escapes(self):
        source = "  - resolve the pending question\n  - re-run develop\n"
        values = _values_with_case_at("resume_conditions", source)
        doc = assemble(values)
        line = next(
            l for l in doc.splitlines() if l.startswith("resume_conditions:")
        )
        self.assertIn("\\n", line)

    def test_round_trips_with_indentation_and_trailing_spaces_intact(self):
        source = "  - resolve the pending question   \n  - re-run develop\n"
        values = _values_with_case_at("resume_conditions", source)
        loaded = yaml.safe_load(assemble(values))
        self.assertEqual(loaded["resume_conditions"], source)


# --- AC-7: stdlib-plus-yaml-only self-check (D6's single exception) ------

_STDLIB_MODULES = set(sys.stdlib_module_names) | set(sys.builtin_module_names)
_ALLOWED_NON_STDLIB = {"yaml"}


def _imported_top_level_modules(source):
    tree = ast.parse(source)
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                modules.add(node.module.split(".")[0])
    return modules


def _non_stdlib_non_yaml_imports(source):
    return (
        _imported_top_level_modules(source) - _STDLIB_MODULES - _ALLOWED_NON_STDLIB
    )


class TestStdlibOnlySelfCheckExceptYaml(unittest.TestCase):
    """AC-7 (D6): this module imports the Python standard library and
    exactly one exception, PyYAML -- no other third-party module."""

    def test_this_modules_own_source_has_no_disallowed_import(self):
        source = Path(__file__).read_text(encoding="utf-8")
        self.assertEqual(_non_stdlib_non_yaml_imports(source), set())

    def test_checker_accepts_a_forged_stdlib_and_yaml_only_source(self):
        forged = (
            "import re\nimport unittest\nfrom pathlib import Path\nimport yaml\n"
        )
        self.assertEqual(_non_stdlib_non_yaml_imports(forged), set())

    def test_checker_rejects_a_forged_extra_third_party_import(self):
        forged = "import yaml\nimport numpy\n"
        self.assertEqual(_non_stdlib_non_yaml_imports(forged), {"numpy"})


if __name__ == "__main__":
    unittest.main()
