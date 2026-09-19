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

Per IMPLEMENTATION.md D5, this module declares SC1 and SC3 independently as
canonical constants below and never reads
`em-workflow/references/batch-terminal-line.md` -- task0001 owns the single
binding assertion that the SSOT states the same rule. The escaping rule
(`escape_value`) is written directly from SC3's table and residual ranges,
with no reliance on any language-provided string-escaping helper, so the
conformance below is never vacuous against Python's own quoting rules.

Matcher -> negative-proof / non-vacuity inventory (NFR4):

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


# --- SC1 / SC3 canonical constants (IMPLEMENTATION.md "Shared Components").
# Declared independently per D5: this module never reads
# batch-terminal-line.md -- task0001 owns the binding assertion that the
# real SSOT states the same values. --------------------------------------

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


def _needs_unicode_escape(code_point):
    return (
        0x0000 <= code_point <= 0x001F
        or 0x007F <= code_point <= 0x009F
        or code_point in (0x2028, 0x2029, 0xFFFE, 0xFFFF)
    )


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
            "reason": "awaiting_user_input",
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
