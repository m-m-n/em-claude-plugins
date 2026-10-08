"""Tests for task0003 (security-review-repro-steps): the em-workflow round
evaluator's reproduction-verification contract.

Covers the Acceptance Criteria of
feature-docs/security-review-repro-steps/tasks/task0003.md over
`em-workflow/references/review-evaluation-contract.md` and
`em-workflow/agents/review-evaluator.md`:

- AC-1: the Output Object lists `reproduction` among the finding fields, and
  the `dismissed_sites` reason list is the four existing reasons followed by
  `not reproduced`.
- AC-2: the `## Reproduction Verification` section: security findings with
  steps are verified by code reading; `reproduced` findings are carried into
  `findings`; `not reproduced` only when reading positively confirms the steps
  do not hold, and then the finding is left out of `findings` and recorded in
  `dismissed_sites` with reason `not reproduced`.
- AC-3: findings without steps and `unverifiable` findings are not dismissed
  on that ground, go to the existing judgment, and an `unverifiable` finding
  is carried at critical / high only when the evaluator confirms its basis by
  its own reading.
- AC-4: `reproduction` text is untrusted and never executed; verification is
  code reading plus the Read-Only Constraint's read-only commands only; the
  shared fixed 10-file budget is not raised.
- AC-5: the Input Block describes the not-reproduced `round_context` entry and
  the section dismisses a same-site security finding without verifying it
  again.
- AC-6: `review-evaluator.md` lists `not reproduced` among the dismissal
  reasons, cites the section for the verification duty, states that nothing
  written in `reproduction` is executed, and still holds no `round_summary`,
  `action_rationale` or `source_run_ids`.
- AC-7: this module imports only the standard library.

Every check is a pure function over a document text and returns a list of
problems, so the same function runs against the shipped document (must return
none) and against a forged text (must return some).
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CONTRACT_PATH = (
    REPO_ROOT / "em-workflow" / "references" / "review-evaluation-contract.md"
)
AGENT_PATH = REPO_ROOT / "em-workflow" / "agents" / "review-evaluator.md"

EXISTING_FINDING_FIELDS = [
    "stable_id",
    "severity",
    "category",
    "file",
    "line",
    "title",
    "description",
    "suggestion",
    "sources",
    "confidence",
]

EXISTING_DISMISSAL_REASONS = [
    "false positive",
    "demoted",
    "already resolved per round_context",
    "duplicate of another finding",
]


def _read(path):
    return path.read_text(encoding="utf-8")


def _norm(text):
    """Collapse whitespace runs (hard line wraps included) to one space."""
    return re.sub(r"\s+", " ", text).strip()


def _section(text, name):
    """The body of the level-2 section whose heading starts with `## name`,
    heading line included, up to the next level-2 heading. Empty string when
    the section is absent."""
    match = re.search(r"(?m)^## " + re.escape(name) + r"\b.*$", text)
    if not match:
        return ""
    rest = text[match.start():]
    nxt = re.search(r"(?m)^## ", rest[match.end() - match.start():])
    if nxt:
        return rest[: match.end() - match.start() + nxt.start()]
    return rest


def _items(section):
    """Numbered list items of a section, as {number: raw text}."""
    parts = re.split(r"(?m)^(\d+)\. ", section)
    return {int(parts[i]): parts[i + 1] for i in range(1, len(parts) - 1, 2)}


def _bullets(raw):
    """Normalized text of each `- ` bullet inside `raw` (the text before the
    first bullet is dropped)."""
    return [_norm(b) for b in re.split(r"(?m)^[ \t]*- ", raw)[1:]]


def _outcome_bullets(section):
    """The bullets of the numbered item that lists the verification outcomes."""
    for raw in _items(section).values():
        if "**Outcomes and effect.**" in raw:
            return _bullets(raw)
    return []


def _has_token(text, token):
    return re.search(r"`" + re.escape(token) + r"`", text) is not None


def _in_order(text, phrases):
    """True iff every phrase occurs and the first occurrences are in order."""
    last = -1
    for phrase in phrases:
        idx = text.find(phrase, last + 1)
        if idx == -1:
            return False
        last = idx
    return True


def _mutate(text, old, new):
    """Replace the first occurrence of `old` with `new`, treating any run of
    whitespace in `old` as matching any whitespace run in the document (the
    documents hard-wrap their prose). Fails loudly when `old` is absent, so a
    forged-text test can never silently test an unchanged document."""
    pattern = r"\s+".join(re.escape(word) for word in old.split())
    forged, count = re.subn(pattern, lambda _m: new, text, count=1)
    assert count == 1, f"cannot forge: {old!r} not found in the document"
    return forged


# ---------------------------------------------------------------------------
# AC-1: Output Object
# ---------------------------------------------------------------------------


def output_object_problems(text):
    problems = []
    section = _section(text, "Output Object")
    if not section:
        return ["no Output Object section"]
    norm = _norm(section)

    clause = re.search(r"Each entry of `findings` carries:(.*?)\.(?:\s|$)", norm)
    if not clause:
        problems.append("finding field list not found")
    else:
        fields = re.findall(r"`([a-z_]+)`", clause.group(1))
        if fields != EXISTING_FINDING_FIELDS + ["reproduction"]:
            problems.append(f"finding fields are {fields!r}")

    reasons_clause = re.search(
        r"Each entry of `dismissed_sites` carries:.*?\band `reason` — one of "
        r"(.*?)\.(?:\s|$)",
        norm,
    )
    if not reasons_clause:
        problems.append("dismissed_sites reason list not found")
    else:
        reasons = [
            r.replace("`", "").strip() for r in reasons_clause.group(1).split(" / ")
        ]
        if reasons != EXISTING_DISMISSAL_REASONS + ["not reproduced"]:
            problems.append(f"dismissed_sites reasons are {reasons!r}")
        if not _has_token(reasons_clause.group(1), "not reproduced"):
            problems.append("`not reproduced` is not written as an exact literal")

    carry = re.search(r"`reproduction` is carried from the reviewer finding[^.]*\.", norm)
    if not carry:
        problems.append("no statement that `reproduction` is carried from the reviewer finding")
    else:
        if "null" not in carry.group(0):
            problems.append("carry rule does not mention null")
        if "non-security" not in carry.group(0):
            problems.append("carry rule does not name non-security findings")
    if "evaluator originates" not in norm:
        problems.append("no rule for a finding the evaluator originates")
    return problems


# ---------------------------------------------------------------------------
# AC-2 / AC-3 / AC-5 (section half): ## Reproduction Verification
# ---------------------------------------------------------------------------

SECTION_HEADING_RE = r"(?m)^## Reproduction Verification$"


def verification_problems(text):
    problems = []
    if len(re.findall(SECTION_HEADING_RE, text)) != 1:
        return ["no single `## Reproduction Verification` heading"]
    section = _section(text, "Reproduction Verification")
    norm = _norm(section)
    bullets = _outcome_bullets(section)

    if "`security` perspective" not in norm:
        problems.append("scope (security perspective) not stated")
    if not re.search(r"by reading code under `project_root`", norm):
        problems.append("verification by code reading under project_root not stated")

    def outcome(token):
        found = [b for b in bullets if b.startswith(f"`{token}` —")]
        return found[0] if found else ""

    reproduced = outcome("reproduced")
    if not reproduced:
        problems.append("no `reproduced` outcome")
    else:
        if "carried into `findings`" not in reproduced:
            problems.append("`reproduced` is not carried into `findings`")
        if "dismissed_sites" in reproduced:
            problems.append("`reproduced` must not touch dismissed_sites")

    not_reproduced = outcome("not reproduced")
    if not not_reproduced:
        problems.append("no `not reproduced` outcome")
    else:
        for needed in (
            "reading positively confirms",
            "do not hold",
            "not carried into `findings`",
            "recorded in `dismissed_sites`",
            "`reason` exactly `not reproduced`",
        ):
            if needed not in not_reproduced:
                problems.append(f"`not reproduced` outcome lacks {needed!r}")
        if "failure to confirm the steps is never `not reproduced`" not in (
            not_reproduced.lower()
        ):
            problems.append("failure to confirm is not ruled out as `not reproduced`")

    if not outcome("unverifiable"):
        problems.append("no `unverifiable` outcome")
    return problems


def judgment_problems(text):
    problems = []
    section = _section(text, "Reproduction Verification")
    if not section:
        return ["no Reproduction Verification section"]
    items = _items(section)
    bullets = _outcome_bullets(section)

    no_steps = [
        _norm(i) for i in items.values() if "null, empty or whitespace-only" in i
    ]
    if not no_steps:
        problems.append("no-steps rule (null, empty or whitespace-only) not stated")
    else:
        for needed in (
            "No verification is attempted",
            "existing judgment",
            "not dismissed on that ground",
        ):
            if needed not in no_steps[0]:
                problems.append(f"no-steps rule lacks {needed!r}")

    unverifiable = [b for b in bullets if b.startswith("`unverifiable` —")]
    if not unverifiable:
        problems.append("no `unverifiable` outcome")
    else:
        u = unverifiable[0]
        for needed in (
            "the read budget is exhausted",
            "cannot be traced with read-only means",
            "truncated",
            "4096 bytes",
            "never dismissed on that ground alone",
            "the existing judgment decides",
            "carried at critical / high only when the evaluator confirms its basis "
            "by its own reading",
            "carried at medium or dismissed with one of the four existing reasons",
        ):
            if needed not in u:
                problems.append(f"`unverifiable` outcome lacks {needed!r}")

    over_limit = [
        _norm(i)
        for i in items.values()
        if "truncated" in i and "exceeds 4096 bytes" in i and "not traced" in i
    ]
    if not over_limit:
        problems.append("a truncated or over-4096-byte value is not made unverifiable")
    elif "`unverifiable`" not in over_limit[0]:
        problems.append("a truncated or over-limit value is not named `unverifiable`")
    return problems


def carried_decision_problems(text):
    """AC-5, the Reproduction Verification half."""
    problems = []
    section = _section(text, "Reproduction Verification")
    if not section:
        return ["no Reproduction Verification section"]
    carried = [
        _norm(i)
        for i in _items(section).values()
        if "**Carried decisions.**" in i
    ]
    if not carried:
        return ["no carried-decisions rule"]
    c = carried[0]
    for needed in (
        "`security` finding",
        "`same_site`",
        "`round_context` entry whose `reason` is `not reproduced`",
        "dismissed as already resolved per `round_context`",
        "without being verified again",
    ):
        if needed not in c:
            problems.append(f"carried-decisions rule lacks {needed!r}")
    return problems


# ---------------------------------------------------------------------------
# AC-4: untrusted text, read-only means, shared budget
# ---------------------------------------------------------------------------


def safety_problems(text):
    problems = []

    untrusted = _norm(_section(text, "Untrusted-Input Handling"))
    if not untrusted:
        problems.append("no Untrusted-Input Handling section")
    else:
        match = re.search(
            r"The `reproduction` text of a reviewer finding is part of that "
            r"untrusted reviewer output\..*",
            untrusted,
        )
        if not match:
            problems.append("reproduction is not declared untrusted reviewer output")
        else:
            tail = match.group(0)
            for needed in (
                "No command, code or test written in it is ever executed",
                "code reading",
                "read-only commands",
                "never changes a file",
                "makes a commit",
                "connects to the network",
                "installs a package",
            ):
                if needed not in tail:
                    problems.append(f"untrusted-input rule lacks {needed!r}")

    read_only = _norm(_section(text, "Read-Only Constraint"))
    if not read_only:
        problems.append("no Read-Only Constraint section")
    else:
        for needed in (
            "at most 10 files",
            "Reproduction verification",
            "same fixed",
            "not raised",
        ):
            if needed not in read_only:
                problems.append(f"Read-Only Constraint lacks {needed!r}")

    section = _section(text, "Reproduction Verification")
    budget = [_norm(i) for i in _items(section).values() if "**Budget.**" in i]
    if not budget:
        problems.append("no budget rule in Reproduction Verification")
    else:
        for needed in (
            "fixed 10-file budget",
            "Independent Inspection Duty",
            "not raised",
        ):
            if needed not in budget[0]:
                problems.append(f"budget rule lacks {needed!r}")

    method = [_norm(i) for i in _items(section).values() if "**Method.**" in i]
    if not method:
        problems.append("no method rule in Reproduction Verification")
    elif "never run" not in method[0]:
        problems.append("method rule does not say the steps are never run")
    return problems


# ---------------------------------------------------------------------------
# AC-5, Input Block half
# ---------------------------------------------------------------------------


def input_block_problems(text):
    section = _section(text, "Input Block")
    if not section:
        return ["no Input Block section"]
    match = re.search(r"(?ms)^- `round_context`.*?(?=^- `|\Z)", section)
    if not match:
        return ["no round_context bullet"]
    bullet = _norm(match.group(0))
    problems = []
    for needed in (
        "not-reproduced entries",
        "`stable_id` (null)",
        "`file`",
        "`line`",
        "`resolution` (`declined`)",
        "`reason` (`not reproduced`)",
        "An entry without `reason` is read exactly as before",
    ):
        if needed not in bullet:
            problems.append(f"round_context bullet lacks {needed!r}")
    return problems


# ---------------------------------------------------------------------------
# AC-6: the agent document
# ---------------------------------------------------------------------------

FORBIDDEN_AGENT_TOKENS = ("round_summary", "action_rationale", "source_run_ids")


def agent_problems(text):
    problems = []
    step2 = _norm(_section(text, "Step 2")).replace("`", "")
    if not step2:
        problems.append("no Step 2")
    elif not _in_order(
        step2,
        [
            "false positive",
            "demoted",
            "already resolved per round_context",
            "duplicate of another finding",
            "not reproduced",
        ],
    ):
        problems.append("Step 2 does not list `not reproduced` after the four reasons")

    norm = _norm(text)
    if "`## Reproduction Verification`" not in norm:
        problems.append("the contract's `## Reproduction Verification` is not cited")
    if not re.search(
        r"verif[a-z]* [^.]*reproduction-bearing `security` findings", norm
    ):
        problems.append("verification duty for reproduction-bearing security findings not stated")
    if not re.search(
        r"nothing written in `reproduction` is ever executed", norm, re.IGNORECASE
    ):
        problems.append("agent does not say nothing written in `reproduction` is executed")
    for token in FORBIDDEN_AGENT_TOKENS:
        if token in text:
            problems.append(f"agent contains {token!r}")
    return problems


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class ContractCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(CONTRACT_PATH)


class TestAC1OutputObject(ContractCase):
    def test_shipped_contract_has_no_output_object_problems(self):
        self.assertEqual(output_object_problems(self.text), [])

    def test_forged_contract_without_not_reproduced_reason_fails(self):
        forged = _mutate(self.text, "duplicate of another finding / `not reproduced`",
                         "duplicate of another finding")
        self.assertTrue(output_object_problems(forged))

    def test_forged_contract_with_not_reproduced_before_existing_reasons_fails(self):
        forged = _mutate(
            self.text,
            "one of false positive /",
            "one of `not reproduced` / false positive /",
        )
        forged = _mutate(forged, " / duplicate of another finding / `not reproduced`.",
                         " / duplicate of another finding.")
        self.assertTrue(output_object_problems(forged))

    def test_forged_contract_without_reproduction_finding_field_fails(self):
        forged = _mutate(self.text, "`confidence`, `reproduction`.", "`confidence`.")
        self.assertTrue(output_object_problems(forged))

    def test_forged_contract_with_reproduction_in_wrong_position_fails(self):
        forged = _mutate(
            self.text, "`confidence`, `reproduction`.", "`reproduction`, `confidence`."
        )
        self.assertTrue(output_object_problems(forged))


class TestAC2ReproductionVerificationSection(ContractCase):
    def test_section_heading_is_exactly_one_level_two_heading(self):
        self.assertEqual(len(re.findall(SECTION_HEADING_RE, self.text)), 1)

    def test_shipped_contract_has_no_verification_problems(self):
        self.assertEqual(verification_problems(self.text), [])

    def test_missing_section_is_a_problem(self):
        forged = _mutate(
            self.text, "## Reproduction Verification", "## Reproduction Checks"
        )
        self.assertTrue(verification_problems(forged))

    def test_forged_not_reproduced_that_stays_in_findings_fails(self):
        forged = _mutate(
            self.text,
            "The finding is not carried into `findings`; it is recorded in "
            "`dismissed_sites`",
            "The finding is carried into `findings`; it is not recorded in "
            "`dismissed_sites`",
        )
        self.assertTrue(verification_problems(forged))

    def test_forged_not_reproduced_on_failure_to_confirm_fails(self):
        forged = _mutate(
            self.text,
            "reading positively confirms",
            "reading fails to confirm",
        )
        self.assertTrue(verification_problems(forged))

    def test_forged_reproduced_that_is_dismissed_fails(self):
        forged = _mutate(
            self.text,
            "The finding is carried into `findings`.",
            "The finding is recorded in dismissed_sites.",
        )
        self.assertTrue(verification_problems(forged))


class TestAC3NoStepsAndUnverifiable(ContractCase):
    def test_shipped_contract_has_no_judgment_problems(self):
        self.assertEqual(judgment_problems(self.text), [])

    def test_forged_no_steps_dismissal_fails(self):
        forged = _mutate(
            self.text, "not dismissed on that ground", "dismissed on that ground"
        )
        self.assertTrue(judgment_problems(forged))

    def test_forged_unverifiable_carried_at_high_without_own_reading_fails(self):
        forged = _mutate(
            self.text,
            "carried at critical / high only when the evaluator confirms its "
            "basis by its own reading",
            "carried at critical / high",
        )
        self.assertTrue(judgment_problems(forged))

    def test_forged_unverifiable_dismissed_on_that_ground_fails(self):
        forged = _mutate(
            self.text,
            "never dismissed on that ground alone",
            "dismissed on that ground",
        )
        self.assertTrue(judgment_problems(forged))

    def test_forged_without_read_budget_exhaustion_fails(self):
        forged = _mutate(self.text, "the read budget is exhausted", "the read is slow")
        self.assertTrue(judgment_problems(forged))


class TestAC4UntrustedReproductionAndSharedBudget(ContractCase):
    def test_shipped_contract_has_no_safety_problems(self):
        self.assertEqual(safety_problems(self.text), [])

    def test_forged_contract_that_executes_reproduction_fails(self):
        forged = _mutate(
            self.text,
            "No command, code or test written in it is ever executed",
            "A command written in it may be executed",
        )
        self.assertTrue(safety_problems(forged))

    def test_forged_contract_without_network_and_package_rule_fails(self):
        forged = _mutate(
            self.text,
            "connects to the network or installs a package",
            "reads files",
        )
        self.assertTrue(safety_problems(forged))

    def test_forged_contract_with_raised_budget_fails(self):
        forged = _mutate(
            self.text,
            "draws from this same fixed budget",
            "draws from its own budget",
        )
        self.assertTrue(safety_problems(forged))

    def test_budget_wording_pinned_by_the_existing_suite_is_kept(self):
        section = self.text[self.text.index("## Read-Only Constraint"):]
        window = section[:600]
        self.assertRegex(window, r"\bat most 10 files\b")
        self.assertIn("not raised", window)

    def test_dismissed_site_reason_window_pinned_by_the_existing_suite_is_kept(self):
        idx = self.text.index("Each entry of `dismissed_sites` carries")
        window = self.text[idx: idx + 400].lower()
        for needle in ("false positive", "demoted", "round_context", "duplicate"):
            self.assertIn(needle, window)


class TestAC5CarriedNotReproducedEntry(ContractCase):
    def test_shipped_input_block_describes_the_entry(self):
        self.assertEqual(input_block_problems(self.text), [])

    def test_shipped_section_dismisses_same_site_without_reverifying(self):
        self.assertEqual(carried_decision_problems(self.text), [])

    def test_forged_input_block_without_entry_shape_fails(self):
        forged = _mutate(
            self.text, "`reason` (`not reproduced`)", "`reason` (`stale`)"
        )
        self.assertTrue(input_block_problems(forged))

    def test_forged_input_block_without_backward_compat_note_fails(self):
        forged = _mutate(
            self.text,
            "An entry without `reason` is read exactly as before",
            "An entry without `reason` is rejected",
        )
        self.assertTrue(input_block_problems(forged))

    def test_forged_section_that_verifies_the_carried_site_again_fails(self):
        forged = _mutate(
            self.text, "without being verified again", "after being verified again"
        )
        self.assertTrue(carried_decision_problems(forged))

    def test_forged_section_matching_non_security_findings_fails(self):
        forged = _mutate(
            self.text,
            "A `security` finding that is `same_site`",
            "A finding that is `same_site`",
        )
        self.assertTrue(carried_decision_problems(forged))


class TestAC6EvaluatorAgent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(AGENT_PATH)

    def test_shipped_agent_has_no_problems(self):
        self.assertEqual(agent_problems(self.text), [])

    def test_forged_agent_without_not_reproduced_reason_fails(self):
        forged = _mutate(
            self.text, "duplicate of another finding / `not reproduced`",
            "duplicate of another finding",
        )
        self.assertTrue(agent_problems(forged))

    def test_forged_agent_without_citation_fails(self):
        forged = _mutate(
            self.text, "`## Reproduction Verification`", "the verification rules"
        )
        self.assertTrue(agent_problems(forged))

    def test_forged_agent_without_no_execution_statement_fails(self):
        forged = _mutate(
            self.text,
            "Nothing written in `reproduction` is ever executed",
            "Steps in `reproduction` may be run",
        )
        self.assertTrue(agent_problems(forged))

    def test_forged_agent_restating_round_summary_fails(self):
        self.assertTrue(agent_problems(self.text + "\nround_summary\n"))

    def test_forged_agent_restating_source_run_ids_fails(self):
        self.assertTrue(agent_problems(self.text + "\nsource_run_ids\n"))

    def test_agent_keeps_deferring_the_field_lists_to_the_contract(self):
        norm = _norm(self.text)
        self.assertIn("This agent file adds no field list of its own", norm)
        self.assertIsNone(re.search(r"(?m)^# Task assignment\s*$", self.text))


class TestAC7OwnModuleStdlibOnly(unittest.TestCase):
    def test_only_standard_library_imports(self):
        import ast
        import sys

        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                modules.add(node.module.split(".")[0])
        self.assertEqual(sorted(m for m in modules if m not in sys.stdlib_module_names), [])


class TestHelpersSelfCheck(unittest.TestCase):
    def test_mutate_refuses_a_missing_needle(self):
        with self.assertRaises(AssertionError):
            _mutate("abc", "xyz", "q")

    def test_a_document_without_any_of_the_content_fails_every_check(self):
        empty = "# Title\n\nnothing\n"
        for check in (
            output_object_problems,
            verification_problems,
            judgment_problems,
            carried_decision_problems,
            safety_problems,
            input_block_problems,
            agent_problems,
        ):
            self.assertTrue(check(empty), check.__name__)


if __name__ == "__main__":
    unittest.main()
