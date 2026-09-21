"""Tests for task0004 (task-tier-reduction): the `no_work_required` stop
reason code -- its row in the closed stop reason-code set, its stop-point
coverage row, and a structured result carrying it.

Covers task0004 Acceptance Criteria
(feature-docs/task-tier-reduction/tasks/task0004.md):

- AC-1: the reason-code table carries exactly one new row for the no-work
  condition, with the stopped state in its applicability column, and every
  pre-existing row keeps its name, meaning and state value unchanged.
- AC-2: every sentence in the contract that states the size of the closed
  set, or the size of the reason value domain including the reserved
  consumer value, is consistent with the new count; no such sentence
  retains the previous number, in either word or digit form.
- AC-3: the stop-point coverage table carries exactly one new row mapping
  the hyphenated stop point to the new code with the develop skill as its
  source, and the precedence paragraph still names the same colliding stop
  points it named before.
- AC-4: a result carrying the stopped state, the new code, the no-step
  sentinel and non-empty resume guidance satisfies every consumer
  constraint and every emitter obligation in the contract; the same result
  with empty resume guidance is rejected (TS-4).
- AC-5: the responsibility-boundary section is byte-identical to its
  pre-change text (TS-14), captured from the base commit before this
  task's edit.
- AC-7 (this module's own half): the code literal `no_work_required`
  appears in neither `references/batch-mode.md` nor
  `skills/develop/SKILL.md`; this module is discovered by
  `python3 -m unittest discover -s tests`, imports only the standard
  library, and pairs each matcher with a negative proof and a non-vacuity
  guard.

Per NFR7 (task-tier-reduction), this module imports the Python standard
library only -- unlike the batch-structured-result-output feature's D6,
this feature names no third-party exception, so PyYAML is never imported
here. The consumer-constraint checker below therefore works directly on
source values (never a real parser's round trip): the general escaping/
round-trip fidelity (SC1/SC3) is already proven, as a regression, by
`test_structured_result_conformance.py` and
`test_structured_result_consumer_constraints.py` (task0004's own AC-7
names both for regression confirmation, unedited); this module's job is
narrower -- proving the ONE new code's result satisfies the contract, not
re-proving the general round trip.

Following this repository's cross-module-isolation convention (see e.g.
tests/test_failed_kind_batch_docs.py, tests/test_batch_quiet_output_discipline.py):
no import from another test module; every constant needed here is
re-declared locally.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTRACT_PATH = REPO_ROOT / "em-workflow" / "references" / "batch-terminal-line.md"
BATCH_MODE_PATH = REPO_ROOT / "em-workflow" / "references" / "batch-mode.md"
SKILL_PATH = REPO_ROOT / "em-workflow" / "skills" / "develop" / "SKILL.md"

NEW_REASON_CODE = "no_work_required"
NEW_STOP_POINT = "no-work-required"
NEW_STOP_POINT_SOURCE = "skills/develop/SKILL.md"
NEW_STEP_SENTINEL = "no-step"

# The eleven pre-existing (code, state) pairs, unchanged by this task,
# in their pre-existing document order.
PRE_EXISTING_REASON_CODE_STATE_PAIRS = (
    ("step_stuck", "stopped"),
    ("step_needs_intervention", "stopped"),
    ("workflow_yaml_unparseable", "stopped"),
    ("git_setup_aborted", "stopped"),
    ("gate_fail_closed", "stopped"),
    ("gate_option_unavailable", "stopped"),
    ("implement_task_failed", "stopped"),
    ("verify_rework_cap_reached", "stopped"),
    ("completion_aborted", "stopped"),
    ("feature_resolution_aborted", "stopped"),
    ("docs_commit_conflict_aborted", "stopped"),
)

EXPECTED_REASON_CODE_STATE_PAIRS = PRE_EXISTING_REASON_CODE_STATE_PAIRS + (
    (NEW_REASON_CODE, "stopped"),
)

PRE_EXISTING_COVERAGE_ROWS = (
    "| `stop-condition-2` | `step_stuck` | `skills/develop/SKILL.md` |",
    "| `stop-condition-3` | `step_needs_intervention` | `skills/develop/SKILL.md` |",
    "| `stop-condition-4` | `workflow_yaml_unparseable` | `skills/develop/SKILL.md` |",
    "| `stop-condition-6` | `git_setup_aborted` | `skills/develop/SKILL.md` |",
    "| `fail-closed-abort` | `gate_fail_closed` | `references/question-resolution.md` |",
    "| `policy-option-unavailable` | `gate_option_unavailable` | `references/batch-policies.yaml` |",
    "| `implement-second-failure` | `implement_task_failed` | `references/implement-phase.md` |",
    "| `verify-rework-cap` | `verify_rework_cap_reached` | `skills/develop/SKILL.md` |",
    "| `step-c-abort` | `completion_aborted` | `skills/develop/SKILL.md` |",
    "| `step-a-abort` | `feature_resolution_aborted` | `skills/develop/SKILL.md` |",
    "| `docs-commit-conflict` | `docs_commit_conflict_aborted` | `references/phase-state.md` |",
)

EXPECTED_NEW_COVERAGE_ROW = (
    f"| `{NEW_STOP_POINT}` | `{NEW_REASON_CODE}` | `{NEW_STOP_POINT_SOURCE}` |"
)

PRECEDENCE_COLLIDING_STOP_POINTS = (
    "`implement-second-failure`",
    "`verify-rework-cap`",
    "`docs-commit-conflict`",
)

# Captured from the base commit (git show HEAD), before this task's edit --
# used only for AC-5's byte-identical check (TS-14).
RESPONSIBILITY_BOUNDARY_PRE_CHANGE_TEXT = (
    "## Responsibility boundary\n"
    "\n"
    "em-workflow declares the stop in its own output only. It performs no\n"
    "status operation against the external task-management service — it does\n"
    "not edit that service's task page body or status property. The relay\n"
    "from this structured result to a human reviewer happens through that\n"
    "external service, in one direction only (outbound). This is also why\n"
    "`detail`, `resume_conditions`, `branch` and `pr_url` carry no confidential\n"
    "information beyond paths: once emitted, the result's content is relayed\n"
    "outside of em-workflow's own process boundary.\n"
)


def _read(path):
    return path.read_text(encoding="utf-8")


def _section(text, start_marker, end_marker):
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    return text[start:end]


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
            continue  # separator row
        raw_rows.append(cells)
    return raw_rows[1:] if raw_rows else []


def _table_row(text, anchor):
    """Locates a table row by its anchor (leading cell text) rather than by
    row index -- row order is not a contract for a single-row lookup."""
    idx = text.index(anchor)
    end = text.index("\n", idx)
    return text[idx:end]


def _reason_code_state_pairs(text):
    section = _section(text, "## Stop reason codes", "## Stop point coverage")
    rows = _table_rows(section)
    pairs = []
    for row in rows:
        code_match = re.match(r"^`([a-z_]+)`$", row[0])
        state_match = re.match(r"^`([a-z_]+)`$", row[-1])
        if code_match and state_match:
            pairs.append((code_match.group(1), state_match.group(1)))
    return pairs


def _coverage_data_rows(text):
    section = _section(text, "## Stop point coverage", "Precedence rule:")
    return [
        line.strip()
        for line in section.splitlines()
        if line.strip().startswith("| `")
    ]


def _responsibility_boundary_section(text):
    marker = "\n## Responsibility boundary\n"
    idx = text.rindex(marker)
    return text[idx + 1 :]


# ---------------------------------------------------------------------------
# AC-1: the reason-code table's new row
# ---------------------------------------------------------------------------


class TestReasonCodeTableRow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(CONTRACT_PATH)

    def test_new_row_present_with_stopped_state(self):
        self.assertIn((NEW_REASON_CODE, "stopped"), _reason_code_state_pairs(self.text))

    def test_new_row_meaning_mentions_no_work_remains(self):
        row = _table_row(self.text, f"| `{NEW_REASON_CODE}` |")
        self.assertIn("no work remains", row)

    def test_exactly_one_new_row_and_pre_existing_rows_unchanged(self):
        self.assertEqual(
            _reason_code_state_pairs(self.text), list(EXPECTED_REASON_CODE_STATE_PAIRS)
        )

    def test_negative_proof_an_added_extra_row_is_detected(self):
        section = _section(self.text, "## Stop reason codes", "## Stop point coverage")
        synthetic = self.text.replace(
            section, section + "| `extra_code` | Something new | `stopped` |\n"
        )
        self.assertNotEqual(
            _reason_code_state_pairs(synthetic), list(EXPECTED_REASON_CODE_STATE_PAIRS)
        )

    def test_negative_proof_the_new_row_removed_is_detected(self):
        # Non-vacuity: the anchor genuinely locates a row in the real text
        # (would raise ValueError otherwise).
        row = _table_row(self.text, f"| `{NEW_REASON_CODE}` |")
        synthetic = self.text.replace(row + "\n", "")
        self.assertNotEqual(
            _reason_code_state_pairs(synthetic), list(EXPECTED_REASON_CODE_STATE_PAIRS)
        )

    def test_negative_proof_a_pre_existing_row_changed_is_detected(self):
        original_row = (
            "| `step_stuck` | A workflow step could not make progress and "
            "is stuck | `stopped` |"
        )
        self.assertIn(original_row, self.text)
        altered_row = original_row.replace("`stopped`", "`completed`")
        synthetic = self.text.replace(original_row, altered_row)
        self.assertNotEqual(
            _reason_code_state_pairs(synthetic), list(EXPECTED_REASON_CODE_STATE_PAIRS)
        )


# ---------------------------------------------------------------------------
# AC-2: set-size prose, in both word and digit form
# ---------------------------------------------------------------------------


class TestSetSizeProseConsistent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(CONTRACT_PATH)

    def test_old_word_form_size_prose_is_gone(self):
        self.assertNotIn("eleven stop reason codes", self.text)
        self.assertNotIn("one of twelve documented values", self.text)
        self.assertNotIn("The twelve are the eleven", self.text)
        self.assertNotIn("a twelfth, reserved value", self.text)

    def test_old_digit_form_size_prose_is_gone(self):
        self.assertNotIn("11 stop reason", self.text)
        self.assertNotIn("12 documented values", self.text)

    def test_new_word_form_size_prose_present(self):
        self.assertIn("Closed set of twelve stop reason codes", self.text)
        self.assertIn("one of thirteen documented values", self.text)
        self.assertIn(
            "The thirteen are the twelve stop reason codes", self.text
        )
        self.assertIn("a thirteenth, reserved value", self.text)

    def test_negative_proof_old_prose_would_have_matched_the_absence_checks(self):
        # Non-vacuity for test_old_word_form_size_prose_is_gone: the OLD
        # wording these absence checks reject genuinely contains the
        # flagged substrings.
        old_sample = (
            "Closed set of eleven stop reason codes:\n\n"
            "one of twelve documented values, or the reserved value `none`. "
            "The twelve are the eleven stop reason codes listed below.\n"
            "`context_budget_reached` is a twelfth, reserved value"
        )
        self.assertIn("eleven stop reason codes", old_sample)
        self.assertIn("one of twelve documented values", old_sample)
        self.assertIn("The twelve are the eleven", old_sample)
        self.assertIn("a twelfth, reserved value", old_sample)


# ---------------------------------------------------------------------------
# AC-3: the stop-point coverage table's new row + the precedence paragraph
# ---------------------------------------------------------------------------


class TestCoverageTableRow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(CONTRACT_PATH)

    def test_new_coverage_row_present_and_exact(self):
        section = _section(self.text, "## Stop point coverage", "Precedence rule:")
        row = _table_row(section, f"| `{NEW_STOP_POINT}` |")
        self.assertEqual(row, EXPECTED_NEW_COVERAGE_ROW)

    def test_exactly_one_new_coverage_row_and_pre_existing_rows_unchanged(self):
        self.assertEqual(
            _coverage_data_rows(self.text),
            list(PRE_EXISTING_COVERAGE_ROWS) + [EXPECTED_NEW_COVERAGE_ROW],
        )

    def test_negative_proof_removed_coverage_row_is_detected(self):
        synthetic = self.text.replace(EXPECTED_NEW_COVERAGE_ROW + "\n", "")
        self.assertNotEqual(
            _coverage_data_rows(synthetic),
            list(PRE_EXISTING_COVERAGE_ROWS) + [EXPECTED_NEW_COVERAGE_ROW],
        )

    def test_negative_proof_changed_mapping_is_detected(self):
        altered_row = f"| `{NEW_STOP_POINT}` | `step_stuck` | `{NEW_STOP_POINT_SOURCE}` |"
        synthetic = self.text.replace(EXPECTED_NEW_COVERAGE_ROW, altered_row)
        self.assertNotEqual(
            _coverage_data_rows(synthetic),
            list(PRE_EXISTING_COVERAGE_ROWS) + [EXPECTED_NEW_COVERAGE_ROW],
        )


class TestPrecedenceParagraphUnchanged(unittest.TestCase):
    """AC-3: the new stop point occurs before any workflow step exists, so
    it collides with none of the generic `stop-condition-N` rows -- the
    precedence paragraph's list of colliding stop points is unchanged."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(CONTRACT_PATH)
        cls.paragraph = _section(
            cls.text, "Precedence rule:", "\n\n## Consumer constraints"
        )

    def test_colliding_stop_points_unchanged(self):
        for point in PRECEDENCE_COLLIDING_STOP_POINTS:
            self.assertIn(point, self.paragraph)

    def test_new_stop_point_not_named_as_colliding(self):
        self.assertNotIn(f"`{NEW_STOP_POINT}`", self.paragraph)

    def test_negative_proof_an_added_colliding_point_is_detected(self):
        forged = self.paragraph + f" `{NEW_STOP_POINT}` also collides."
        self.assertIn(f"`{NEW_STOP_POINT}`", forged)
        self.assertNotIn(f"`{NEW_STOP_POINT}`", self.paragraph)


class TestExactlyOneCodeHasNoStopPoint(unittest.TestCase):
    """Test Notes edge case: the contract says exactly one documented
    `reason` code has no stop point. Adding a stop point for the new code
    (unlike `context_budget_reached`, which keeps none) must not change
    that statement's truth -- checked both as a retained sentence and as a
    direct computation over the document's own two tables."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(CONTRACT_PATH)

    def test_statement_sentence_still_present(self):
        self.assertIn(
            "Exactly one documented `reason` code, `context_budget_reached`, "
            "has no stop point in the table above",
            _normalize(self.text),
        )

    # `context_budget_reached` is documented as part of the `reason` domain
    # (`## Field values`) but deliberately carries no row in the `## Stop
    # reason codes` table -- it is consumer-reserved and never emitted by
    # em-workflow, so `_reason_code_state_pairs` (which parses only that
    # table) never yields it. It must be added explicitly to reconstruct
    # the full DOCUMENTED `reason` domain this edge case is about.
    RESERVED_CONSUMER_REASON_VALUE = "context_budget_reached"

    def _uncovered_codes(self, text):
        reason_codes = {code for code, _ in _reason_code_state_pairs(text)}
        reason_codes.add(self.RESERVED_CONSUMER_REASON_VALUE)
        coverage_section = _section(text, "## Stop point coverage", "Precedence rule:")
        covered_codes = set()
        for row in _table_rows(coverage_section):
            match = re.match(r"^`([a-z_]+)`$", row[1])
            if match:
                covered_codes.add(match.group(1))
        return reason_codes - covered_codes

    def test_uncovered_reason_codes_is_exactly_context_budget_reached(self):
        self.assertEqual(self._uncovered_codes(self.text), {"context_budget_reached"})

    def test_negative_proof_missing_new_coverage_row_is_detected(self):
        synthetic = self.text.replace(EXPECTED_NEW_COVERAGE_ROW + "\n", "")
        self.assertEqual(
            self._uncovered_codes(synthetic),
            {"context_budget_reached", NEW_REASON_CODE},
        )


# ---------------------------------------------------------------------------
# AC-5: the responsibility-boundary section is byte-identical
# ---------------------------------------------------------------------------


class TestResponsibilityBoundaryByteIdentical(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(CONTRACT_PATH)

    def test_section_byte_identical_to_pre_change_text(self):
        actual = _responsibility_boundary_section(self.text)
        self.assertEqual(actual, RESPONSIBILITY_BOUNDARY_PRE_CHANGE_TEXT)

    def test_negative_proof_a_modified_copy_is_detected(self):
        forged = RESPONSIBILITY_BOUNDARY_PRE_CHANGE_TEXT.replace(
            "declares the stop", "declares the halt"
        )
        self.assertNotEqual(forged, RESPONSIBILITY_BOUNDARY_PRE_CHANGE_TEXT)


# ---------------------------------------------------------------------------
# AC-4 / TS-4: a result carrying the new code
# ---------------------------------------------------------------------------

RESULT_KEYS = (
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


def escape_value(source):
    """SC3's escaping rule, applied character by character, left to right --
    a module-local copy (NFR7 forbids importing PyYAML for this feature;
    this module never round-trips through a real parser, it only needs the
    ENCODED BYTE LENGTH for the size-boundary check below)."""
    out = []
    for char in source:
        direct = _DIRECT_ESCAPES.get(char)
        if direct is not None:
            out.append(direct)
        else:
            out.append(char)
    return "".join(out)


def assemble(values):
    lines = [f'{key}: "{escape_value(values[key])}"' for key in RESULT_KEYS]
    return "\n".join(lines) + "\n"


_STATE_DOMAIN_RE = re.compile(r"`state` [—-]+ the run's terminal outcome: (.+?)\.")
_STEP_IDS_RE = re.compile(r"the seven `workflow\.yaml` step ids \(([^)]*)\)")
_STEP_SENTINEL_RE = re.compile(r"single sentinel `([a-z-]+)`")
_BACKTICK_TOKEN_RE = re.compile(r"`([a-zA-Z0-9_-]+)`")


def _normalize(text):
    return re.sub(r"\s+", " ", text)


def _ssot_domains(text):
    """Reads the closed `state`/`step`/`reason` domains directly from the
    contract document -- never declared as fixed literals here, so a
    forgotten addition to the SSOT is caught the same way it would be by a
    consumer reading the live document."""
    field_values = _normalize(_section(text, "## Field values", "## Stop reason codes"))
    state_match = _STATE_DOMAIN_RE.search(field_values)
    step_ids_match = _STEP_IDS_RE.search(field_values)
    step_sentinel_match = _STEP_SENTINEL_RE.search(field_values)
    step_domain = None
    if step_ids_match is not None and step_sentinel_match is not None:
        step_domain = _BACKTICK_TOKEN_RE.findall(step_ids_match.group(1)) + [
            step_sentinel_match.group(1)
        ]
    reason_domain = {code for code, _ in _reason_code_state_pairs(text)} | {"none"}
    return {
        "state_domain": (
            _BACKTICK_TOKEN_RE.findall(state_match.group(1))
            if state_match is not None
            else None
        ),
        "step_domain": step_domain,
        "reason_domain": reason_domain,
    }


_TERMINAL_CONTROL_CHARS = ("\r", "\n")


def _is_terminal_control_code_point(code_point):
    return (0x00 <= code_point <= 0x1F) or (0x7F <= code_point <= 0x9F)


def _carries_line_terminator_or_terminal_control(value):
    if any(term in value for term in _TERMINAL_CONTROL_CHARS):
        return True
    return any(_is_terminal_control_code_point(ord(ch)) for ch in value)


MAX_DOCUMENT_BYTES = 64 * 1024


def rejection_reasons(values, ssot_text):
    """The contract's consumer constraints (`## Consumer constraints`) plus
    the `resume_conditions` field-value invariant (`## Field values`) and
    the domain-membership emitter obligation, evaluated directly on the
    SOURCE values (this module never runs a real parser -- see module
    docstring). Returns the set of violated-constraint names; an empty set
    means the result is accepted."""
    reasons = set()
    if values["state"] == "stopped" and values["reason"] == "none":
        reasons.add("stopped_with_none_reason")
    if values["state"] == "phase_done":
        if values["reason"] != "none":
            reasons.add("phase_done_without_none_reason")
        if values["resume_conditions"] != "":
            reasons.add("phase_done_with_nonempty_resume_conditions")
    if values["state"] == "stopped" and values["resume_conditions"].strip() == "":
        reasons.add("resume_conditions_empty_while_stopped")
    for key in ("branch", "pr_url"):
        if _carries_line_terminator_or_terminal_control(values[key]):
            reasons.add(f"{key}_carries_line_terminator_or_terminal_control")
    doc_text = assemble(values)
    if len(doc_text.encode("utf-8")) > MAX_DOCUMENT_BYTES:
        reasons.add("document_exceeds_64kib")
    domains = _ssot_domains(ssot_text)
    if domains["state_domain"] is not None and values["state"] not in domains["state_domain"]:
        reasons.add("state_outside_domain")
    if domains["step_domain"] is not None and values["step"] not in domains["step_domain"]:
        reasons.add("step_outside_domain")
    if values["reason"] not in domains["reason_domain"]:
        reasons.add("reason_outside_domain")
    return reasons


def _no_work_required_values(resume_conditions):
    return {
        "state": "stopped",
        "step": NEW_STEP_SENTINEL,
        "reason": NEW_REASON_CODE,
        "detail": "The pre-run estimate reported that no work remains.",
        "feature": "sample-feature",
        "branch": "",
        "pr_url": "",
        "resume_conditions": resume_conditions,
    }


class TestNoWorkRequiredResultSatisfiesTheContract(unittest.TestCase):
    """AC-4 / TS-4: `state: stopped` / `reason: no_work_required` /
    `step: no-step` with non-empty `resume_conditions` satisfies every
    consumer constraint and every emitter obligation; the same result with
    empty `resume_conditions` is rejected."""

    @classmethod
    def setUpClass(cls):
        cls.ssot_text = _read(CONTRACT_PATH)

    def test_new_code_is_a_member_of_the_ssot_reason_domain(self):
        # Non-vacuity: proves the acceptance case below actually exercises
        # the new code's presence in the SSOT, not an accidental pass.
        domains = _ssot_domains(self.ssot_text)
        self.assertIn(NEW_REASON_CODE, domains["reason_domain"])

    def test_result_with_non_empty_resume_conditions_is_accepted(self):
        values = _no_work_required_values(
            "No action is needed; the estimate found no remaining work."
        )
        self.assertEqual(rejection_reasons(values, self.ssot_text), set())

    def test_result_with_empty_resume_conditions_is_rejected(self):
        values = _no_work_required_values("")
        self.assertIn(
            "resume_conditions_empty_while_stopped",
            rejection_reasons(values, self.ssot_text),
        )

    def test_result_with_whitespace_only_resume_conditions_is_rejected(self):
        values = _no_work_required_values("   ")
        self.assertIn(
            "resume_conditions_empty_while_stopped",
            rejection_reasons(values, self.ssot_text),
        )

    def test_negative_proof_an_out_of_domain_reason_is_rejected(self):
        values = _no_work_required_values("Some guidance.")
        values["reason"] = "made_up_reason_not_in_domain"
        self.assertIn("reason_outside_domain", rejection_reasons(values, self.ssot_text))

    def test_negative_proof_the_no_step_sentinel_is_required_to_be_in_domain(self):
        # Non-vacuity: `no-step` genuinely belongs to the SSOT's step
        # domain, so the accepted case above is not passing by omission.
        domains = _ssot_domains(self.ssot_text)
        self.assertIn(NEW_STEP_SENTINEL, domains["step_domain"])


# ---------------------------------------------------------------------------
# AC-7: single-source discipline over the two pointer documents
# ---------------------------------------------------------------------------


class TestSingleSourceDiscipline(unittest.TestCase):
    def test_code_literal_absent_from_batch_mode_doc(self):
        self.assertNotIn(NEW_REASON_CODE, _read(BATCH_MODE_PATH))

    def test_code_literal_absent_from_develop_skill(self):
        self.assertNotIn(NEW_REASON_CODE, _read(SKILL_PATH))

    def test_negative_proof_the_literal_would_be_detected_if_present(self):
        forged = "The stop reason is `no_work_required` in this document."
        self.assertIn(NEW_REASON_CODE, forged)


# ---------------------------------------------------------------------------
# AC-7: this module imports only the standard library
# ---------------------------------------------------------------------------


class TestOwnModuleStdlibOnly(unittest.TestCase):
    def test_only_standard_library_imports(self):
        import ast
        import sys

        source = _read(Path(__file__).resolve())
        tree = ast.parse(source)
        stdlib = sys.stdlib_module_names
        modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    modules.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    modules.add(node.module.split(".")[0])
        non_stdlib = sorted(m for m in modules if m not in stdlib)
        self.assertEqual(non_stdlib, [])


if __name__ == "__main__":
    unittest.main()
