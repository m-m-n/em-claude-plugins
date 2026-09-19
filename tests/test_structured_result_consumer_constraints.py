"""Tests for task0004 (batch-structured-result-output): the consumer's
rejected combinations (FR14) -- TS5.

Covers task0004 Acceptance Criteria
(feature-docs/batch-structured-result-output/tasks/task0004.md):

- AC-6: each of FR14's five constraints has both an accepting case and a
  rejecting case, with the `branch` / `pr_url` rejection applied to the
  PARSED value rather than to the emitted text.
- AC-7 (partial): this module is discovered by
  `python3 -m unittest discover -s tests`, runs with zero skipped tests when
  PyYAML is installed, and imports no third-party module other than PyYAML
  (IMPLEMENTATION.md D6).

Per IMPLEMENTATION.md D5, this module declares SC1's key set independently.
Its escaping copy (`_DIRECT_ESCAPES` / `_needs_unicode_escape`, derived from
`_RESIDUAL_RANGES`) and its baseline's `state`/`step`/`reason` values are
bound to the SSOT instead of declared independently: SC12
(feature-docs/batch-structured-result-output/tasks/task0009.md) is a named,
scoped exception to D5, admissible only because task0008's plan fixes
`## Escaping` and `## Result format` as byte-identical across this round,
and leaves `## Stop reason codes` and the `state`/`step`/`reason` bullets of
`## Field values` unrewritten (task0009's AC-5) -- so no concurrent task's
unmerged edit can affect what is read here. This module reads exactly those
sections of `em-workflow/references/batch-terminal-line.md` and no other.
Per the task plan's Design ("Module-local reference applier"), this module
carries its own small copy of the reference applier rather than importing
one from `test_structured_result_conformance.py` -- each conformance module
is a self-contained test fixture, never a shared production component
(NFR7 forbids shipping it under `em-workflow/` at all).

FR14's five constraints and their tests:

1. `state: "stopped"` with `reason: "none"` is rejected --
   `TestStoppedWithNoneReasonRejected`.
2. `state: "phase_done"` requires `reason: "none"` --
   `TestPhaseDoneRequiresNoneReason`.
3. `state: "phase_done"` requires `resume_conditions: ""` --
   `TestPhaseDoneRequiresEmptyResumeConditions`.
4. `branch` / `pr_url` must carry no line terminator and no terminal-control
   code point, checked on the PARSED value -- escaping does not rescue it --
   `TestBranchAndPrUrlCharacterConstraint`.
5. The whole document is at most 64 KiB encoded UTF-8, constructed in bytes
   -- `TestDocumentSizeBoundary`.

Each constraint's rejecting test uses an otherwise-valid baseline (a forged
"conforming-looking" sample, per the task plan's Non-vacuity note) so only
the one field under test can be responsible for the rejection.

task0009 additions (SC12) and their negative proofs (NFR4):

- `_assert_escaping_copy_bound_to_ssot` (AC-4): negative proofs are
  `test_forged_copy_missing_a_direct_escape_row_is_rejected` and
  `test_forged_copy_missing_a_residual_range_is_rejected`; non-vacuity is
  `test_direct_escapes_and_residual_ranges_match_ssot`.
- `_assert_sample_conforms_to_ssot_domains` (AC-2/AC-3), applied to
  `_baseline_source_values()`: negative proofs are
  `test_forged_baseline_with_out_of_domain_reason_is_rejected` and
  `test_forged_baseline_with_completed_state_and_wrong_step_is_rejected`;
  non-vacuity is `test_baseline_conforms_to_ssot_domains`.
- the banned-reason-literal self-check (AC-1) is a pure absence check with
  no separate negative-proof case; `TestBannedReasonLiteralAbsent` is its
  own module-source non-vacuity guard.
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
    "PyYAML is not installed; the consumer-constraints suite cannot verify "
    "the PARSED-value rejection against a real parser. IMPLEMENTATION.md "
    "D6: a skip here is a FAILED verification item, not a pass."
)


# --- SC1 canonical constants + a minimal reference applier, declared
# independently per D5. SC12 below is the scoped exception that reads
# batch-terminal-line.md for the escaping copy and the baseline's domain
# values only (see module docstring). ---------------------------------

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
# this module's escaping copy and its baseline's `state`/`step`/`reason`
# values to the SSOT. Scoped exception to D5 (see module docstring); reads
# exactly `## Escaping`, `## Stop reason codes` and the `state`/`step`/
# `reason` bullets of `## Field values`, and no other section. ------------

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
    bullets of `## Field values` into the closed domains AC-2/AC-3 bind
    the baseline against, plus FR13's `completed` -> `retrospect` value."""
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
    """AC-2/AC-3/SC12: `values['state']`, `values['step']` and
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
    """SC3's canonical escaping rule (see
    test_structured_result_conformance.py's copy for the full derivation
    commentary)."""
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
    """SC1's eight-line document."""
    lines = [f'{key}: "{escape_value(values[key])}"' for key in KEYS]
    return "\n".join(lines) + "\n"


REASON_NONE = "none"
MAX_DOCUMENT_BYTES = 64 * 1024  # FR14: 64 KiB

_LINE_TERMINATORS = ("\r", "\n", " ", " ")


def _is_terminal_control_code_point(code_point):
    return (0x00 <= code_point <= 0x1F) or (0x7F <= code_point <= 0x9F)


def _carries_line_terminator_or_terminal_control(value):
    if any(term in value for term in _LINE_TERMINATORS):
        return True
    return any(_is_terminal_control_code_point(ord(ch)) for ch in value)


def rejection_reasons(parsed, doc_text):
    """FR14's five constraints. `parsed` is the consumer's decoded mapping
    (as `yaml.safe_load` would return it); `doc_text` is the raw emitted
    document (the wire bytes). The four field-level constraints are decided
    on `parsed` -- never on the raw escaped text, per AC-6; the size
    constraint is decided on `doc_text`'s encoded byte length, per the task
    plan's Test Notes. Returns the set of violated-constraint names (empty
    set = accepted)."""
    reasons = set()
    if parsed["state"] == "stopped" and parsed["reason"] == REASON_NONE:
        reasons.add("stopped_with_none_reason")
    if parsed["state"] == "phase_done":
        if parsed["reason"] != REASON_NONE:
            reasons.add("phase_done_without_none_reason")
        if parsed["resume_conditions"] != "":
            reasons.add("phase_done_with_nonempty_resume_conditions")
    for key in ("branch", "pr_url"):
        if _carries_line_terminator_or_terminal_control(parsed[key]):
            reasons.add(f"{key}_carries_line_terminator_or_terminal_control")
    if len(doc_text.encode("utf-8")) > MAX_DOCUMENT_BYTES:
        reasons.add("document_exceeds_64kib")
    return reasons


def _baseline_source_values():
    return {
        "state": "completed",
        "step": "retrospect",  # FR13: `state: "completed"` forces `step: "retrospect"`
        "reason": REASON_NONE,
        "detail": "Completed the run without incident.",
        "feature": "sample-feature",
        "branch": "em-workflow/sample-feature/integration",
        "pr_url": "",
        "resume_conditions": "",
    }


def _build(source_values):
    """Assembles, then parses back -- returns (parsed, doc_text) exactly as
    a consumer would receive them."""
    doc_text = assemble(source_values)
    parsed = yaml.safe_load(doc_text)
    return parsed, doc_text


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


# AC-1: neither this module nor test_structured_result_conformance.py may
# contain, as contiguous source text, the specific out-of-domain `reason`
# literal review round 1 found in the old samples -- it names no code the
# SSOT's `## Stop reason codes` table lists. Built from two fragments so
# this check does not itself reintroduce the exact banned contiguous text.
_BANNED_REASON_LITERAL = "awaiting_user" + "_input"


class TestBannedReasonLiteralAbsent(unittest.TestCase):
    """AC-1: the specific out-of-domain `reason` literal review round 1
    found is absent from this module's own source."""

    def test_banned_reason_literal_is_absent_from_this_module(self):
        source = Path(__file__).read_text(encoding="utf-8")
        self.assertNotIn(_BANNED_REASON_LITERAL, source)


class TestBaselineConformsToSSOTDomains(unittest.TestCase):
    """AC-2 / AC-3 (SC12): `_baseline_source_values()` draws `state`/`step`/
    `reason` from the SSOT's closed domains, and its `step` satisfies
    FR13's `completed` -> `retrospect` rule -- checked as properties read
    from the SSOT rather than as fixed literals here."""

    def test_baseline_conforms_to_ssot_domains(self):
        _assert_sample_conforms_to_ssot_domains(self, _baseline_source_values())

    def test_forged_baseline_with_out_of_domain_reason_is_rejected(self):
        baseline = _baseline_source_values()
        forged = dict(baseline)
        forged["reason"] = "made_up_reason_not_in_domain"
        with self.assertRaises(AssertionError):
            _assert_sample_conforms_to_ssot_domains(self, forged)
        # Non-vacuity: the forged baseline differs from the otherwise-valid
        # baseline in `reason` only.
        unchanged = {k: v for k, v in forged.items() if k != "reason"}
        baseline_without_reason = {k: v for k, v in baseline.items() if k != "reason"}
        self.assertEqual(unchanged, baseline_without_reason)

    def test_forged_baseline_with_completed_state_and_wrong_step_is_rejected(self):
        baseline = _baseline_source_values()
        forged = dict(baseline)
        forged["step"] = "no-step"
        with self.assertRaises(AssertionError):
            _assert_sample_conforms_to_ssot_domains(self, forged)
        # Non-vacuity: the forged baseline differs from the otherwise-valid
        # baseline in `step` only.
        unchanged = {k: v for k, v in forged.items() if k != "step"}
        baseline_without_step = {k: v for k, v in baseline.items() if k != "step"}
        self.assertEqual(unchanged, baseline_without_step)


@unittest.skipUnless(yaml is not None, _SKIP_REASON)
class TestStoppedWithNoneReasonRejected(unittest.TestCase):
    """AC-6 / TS5 (FR14, constraint 1)."""

    def test_stopped_with_none_reason_is_rejected(self):
        values = dict(_baseline_source_values())
        values.update(
            state="stopped", reason=REASON_NONE, resume_conditions="Resume guidance."
        )
        parsed, doc_text = _build(values)
        self.assertIn(
            "stopped_with_none_reason", rejection_reasons(parsed, doc_text)
        )

    def test_stopped_with_a_non_none_reason_is_accepted(self):
        values = dict(_baseline_source_values())
        values.update(
            state="stopped",
            reason="step_stuck",
            resume_conditions="Resume guidance.",
        )
        parsed, doc_text = _build(values)
        self.assertEqual(rejection_reasons(parsed, doc_text), set())


@unittest.skipUnless(yaml is not None, _SKIP_REASON)
class TestPhaseDoneRequiresNoneReason(unittest.TestCase):
    """AC-6 / TS5 (FR14, constraint 2)."""

    def test_phase_done_with_a_non_none_reason_is_rejected(self):
        values = dict(_baseline_source_values())
        values.update(
            state="phase_done", reason="step_stuck", resume_conditions=""
        )
        parsed, doc_text = _build(values)
        self.assertIn(
            "phase_done_without_none_reason", rejection_reasons(parsed, doc_text)
        )

    def test_phase_done_with_none_reason_is_accepted(self):
        values = dict(_baseline_source_values())
        values.update(state="phase_done", reason=REASON_NONE, resume_conditions="")
        parsed, doc_text = _build(values)
        self.assertEqual(rejection_reasons(parsed, doc_text), set())


@unittest.skipUnless(yaml is not None, _SKIP_REASON)
class TestPhaseDoneRequiresEmptyResumeConditions(unittest.TestCase):
    """AC-6 / TS5 (FR14, constraint 3)."""

    def test_phase_done_with_nonempty_resume_conditions_is_rejected(self):
        values = dict(_baseline_source_values())
        values.update(
            state="phase_done",
            reason=REASON_NONE,
            resume_conditions="Unexpected guidance.",
        )
        parsed, doc_text = _build(values)
        self.assertIn(
            "phase_done_with_nonempty_resume_conditions",
            rejection_reasons(parsed, doc_text),
        )

    def test_phase_done_with_empty_resume_conditions_is_accepted(self):
        values = dict(_baseline_source_values())
        values.update(state="phase_done", reason=REASON_NONE, resume_conditions="")
        parsed, doc_text = _build(values)
        self.assertEqual(rejection_reasons(parsed, doc_text), set())


@unittest.skipUnless(yaml is not None, _SKIP_REASON)
class TestBranchAndPrUrlCharacterConstraint(unittest.TestCase):
    """AC-6 / TS5 (FR14, constraint 4): rejection is decided on the PARSED
    value, not on the emitted (escaped) text -- escaping never rescues a
    forbidden character."""

    def test_clean_branch_and_pr_url_are_accepted(self):
        values = dict(_baseline_source_values())
        values.update(
            branch="em-workflow/sample-feature/integration",
            pr_url="https://example.invalid/pulls/1",
        )
        parsed, doc_text = _build(values)
        self.assertEqual(rejection_reasons(parsed, doc_text), set())

    def test_a_terminal_control_code_point_is_rejected_after_parsing(self):
        for key in ("branch", "pr_url"):
            with self.subTest(key=key):
                values = dict(_baseline_source_values())
                values[key] = "em-workflow/sample\x1bfeature/integration"
                parsed, doc_text = _build(values)
                # Escaping hides the raw control byte from the wire text ...
                line = next(
                    l for l in doc_text.splitlines() if l.startswith(f"{key}:")
                )
                self.assertNotIn("\x1b", line)
                # ... but the PARSED value still carries it, and is rejected.
                self.assertIn("\x1b", parsed[key])
                self.assertIn(
                    f"{key}_carries_line_terminator_or_terminal_control",
                    rejection_reasons(parsed, doc_text),
                )

    def test_a_line_terminator_is_rejected_after_parsing(self):
        for key in ("branch", "pr_url"):
            with self.subTest(key=key):
                values = dict(_baseline_source_values())
                values[key] = "em-workflow/sample\nfeature/integration"
                parsed, doc_text = _build(values)
                line = next(
                    l for l in doc_text.splitlines() if l.startswith(f"{key}:")
                )
                self.assertNotIn("\n", line)
                self.assertIn("\n", parsed[key])
                self.assertIn(
                    f"{key}_carries_line_terminator_or_terminal_control",
                    rejection_reasons(parsed, doc_text),
                )


def _values_padded_to(target_bytes):
    """Pads `detail` with single-byte ASCII filler so the assembled
    document's ENCODED UTF-8 byte length is exactly `target_bytes` -- the
    task plan's Test Notes require the boundary to be constructed in bytes,
    not in character count."""
    values = dict(_baseline_source_values())
    values["detail"] = ""
    base_size = len(assemble(values).encode("utf-8"))
    filler_length = target_bytes - base_size
    if filler_length < 0:
        raise ValueError(f"target {target_bytes} smaller than base size {base_size}")
    values["detail"] = "x" * filler_length
    return values


@unittest.skipUnless(yaml is not None, _SKIP_REASON)
class TestDocumentSizeBoundary(unittest.TestCase):
    """AC-6 / TS5 (FR14, constraint 5): the 64 KiB bound is on the ENCODED
    UTF-8 byte length of the whole emitted document."""

    def test_exactly_at_the_bound_is_accepted(self):
        values = _values_padded_to(MAX_DOCUMENT_BYTES)
        parsed, doc_text = _build(values)
        self.assertEqual(len(doc_text.encode("utf-8")), MAX_DOCUMENT_BYTES)
        self.assertEqual(rejection_reasons(parsed, doc_text), set())

    def test_just_below_the_bound_is_accepted(self):
        values = _values_padded_to(MAX_DOCUMENT_BYTES - 1)
        parsed, doc_text = _build(values)
        self.assertEqual(len(doc_text.encode("utf-8")), MAX_DOCUMENT_BYTES - 1)
        self.assertEqual(rejection_reasons(parsed, doc_text), set())

    def test_just_above_the_bound_is_rejected(self):
        values = _values_padded_to(MAX_DOCUMENT_BYTES + 1)
        parsed, doc_text = _build(values)
        self.assertEqual(len(doc_text.encode("utf-8")), MAX_DOCUMENT_BYTES + 1)
        self.assertIn(
            "document_exceeds_64kib", rejection_reasons(parsed, doc_text)
        )


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
        forged = "import re\nimport unittest\nfrom pathlib import Path\nimport yaml\n"
        self.assertEqual(_non_stdlib_non_yaml_imports(forged), set())

    def test_checker_rejects_a_forged_extra_third_party_import(self):
        forged = "import yaml\nimport numpy\n"
        self.assertEqual(_non_stdlib_non_yaml_imports(forged), {"numpy"})


if __name__ == "__main__":
    unittest.main()
