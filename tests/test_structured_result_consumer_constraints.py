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

Per IMPLEMENTATION.md D5, this module declares SC1's key set independently
and never reads `em-workflow/references/batch-terminal-line.md`. Per the
task plan's Design ("Module-local reference applier"), this module carries
its own small copy of the reference applier rather than importing one from
`test_structured_result_conformance.py` -- each conformance module is a
self-contained test fixture, never a shared production component
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
"""

import ast
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
# independently per D5 -- this module never reads batch-terminal-line.md. --

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


def _needs_unicode_escape(code_point):
    return (
        0x0000 <= code_point <= 0x001F
        or 0x007F <= code_point <= 0x009F
        or code_point in (0x2028, 0x2029, 0xFFFE, 0xFFFF)
    )


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
        "step": "no-step",
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
            reason="awaiting_user_input",
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
            state="phase_done", reason="awaiting_user_input", resume_conditions=""
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
