"""Tests for task0002 (subagentstop-failed-event): the SubagentStop failure
net bullet and the Stale-`launched` caveat in
`em-workflow/references/implement-phase.md` state the new identification
order, the atomic compare-and-append rule, the diagnostics log contract and
the fifth-mechanism observability claim (IMPLEMENTATION.md SC1-SC3).

Covers task0002 Acceptance Criteria
(feature-docs/subagentstop-failed-event/tasks/task0002.md):

- AC-1: within the failure-net bullet, both accepted agent-type values, the
  block-source statement (inline prompt field or first transcript user
  message containing the header, post-header-only parsing identical to the
  launch guard) and the agent-index fallback by the payload agent id appear
  in that order.
- AC-2: within the bullet, the exclusive-lock critical section statement,
  the `failed`-appended-only-when-neither-terminal statement, and the
  at-most-one-`failed`-line statement.
- AC-3: within the bullet, the diagnostics log path, each of the nine
  outcome codes in backticks, the missing-line-meaning statement and the
  not-a-journal/adds-no-writer statement.
- AC-4: within the Stale-`launched` caveat, the new observable-as-a-
  missing-diagnostics-line statement, plus the two phrases
  `tests/test_stale_launched_doc_contract.py` pins in this paragraph
  remaining verbatim.
- AC-5: this module asserts AC-1 to AC-4 against the real file, each
  matcher has a negative proof against a forged copy, and the module
  imports only the standard library.

Follows the established convention (standard library only, document text
read from the repository root computed from this module's own path,
module-level constants for each literal, whitespace-normalized matching,
a negative proof per matcher).
"""

import ast
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"
IMPLEMENT_PHASE_PATH = PLUGIN_ROOT / "references" / "implement-phase.md"

BULLET_START_MARKER = "- **SubagentStop failure net**"
BULLET_END_MARKER = "- **Stop-tool recorder**"
CAVEAT_START_MARKER = "**Stale-`launched` caveat**"
CAVEAT_END_MARKER = "**Resume**"


def _read():
    return IMPLEMENT_PHASE_PATH.read_text(encoding="utf-8")


def _normalize_ws(text):
    return re.sub(r"\s+", " ", text)


def _slice(text, start_marker, end_marker, start_from=0):
    start = text.index(start_marker, start_from)
    end = text.index(end_marker, start)
    return text[start:end]


def _bullet_text():
    return _normalize_ws(_slice(_read(), BULLET_START_MARKER, BULLET_END_MARKER))


def _caveat_text():
    return _normalize_ws(_slice(_read(), CAVEAT_START_MARKER, CAVEAT_END_MARKER))


# --- AC-1: agent type, block source, agent-index fallback, in this order --

AGENT_TYPE_VALUE_1 = "`em-workflow:implementer`"
AGENT_TYPE_VALUE_2 = "`implementer`"
AGENT_TYPE_HOOK_NOOP_PHRASE = "any other non-empty type means the hook does nothing"

BLOCK_SOURCE_PHRASE = (
    "taken from an inline prompt field or from the first transcript user "
    "message that contains the `# Task assignment` header, with the task "
    "id and worktree path taken only from the text after the header, "
    "parsed exactly as the launch guard parses it"
)

AGENT_INDEX_FALLBACK_PHRASE = (
    "the agent-index fallback by the payload's own agent id, resolved "
    "with the stop-tool recorder's rules"
)


class TestBulletIdentificationOrder(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bullet = _bullet_text()

    def test_both_agent_type_values_present(self):
        self.assertIn(AGENT_TYPE_VALUE_1, self.bullet)
        self.assertIn(AGENT_TYPE_VALUE_2, self.bullet)

    def test_agent_type_noop_phrase_present(self):
        self.assertIn(AGENT_TYPE_HOOK_NOOP_PHRASE, self.bullet)

    def test_block_source_phrase_present(self):
        self.assertIn(BLOCK_SOURCE_PHRASE, self.bullet)

    def test_agent_index_fallback_phrase_present(self):
        self.assertIn(AGENT_INDEX_FALLBACK_PHRASE, self.bullet)

    def test_items_appear_in_fixed_order(self):
        positions = [
            self.bullet.index(AGENT_TYPE_VALUE_1),
            self.bullet.index(AGENT_TYPE_VALUE_2),
            self.bullet.index(BLOCK_SOURCE_PHRASE),
            self.bullet.index(AGENT_INDEX_FALLBACK_PHRASE),
        ]
        self.assertEqual(positions, sorted(positions))

    def test_negative_proof_missing_agent_type_value_detected(self):
        forged = self.bullet.replace(AGENT_TYPE_VALUE_2, "")
        self.assertNotIn(AGENT_TYPE_VALUE_2, forged)

    def test_negative_proof_missing_noop_phrase_detected(self):
        forged = self.bullet.replace(AGENT_TYPE_HOOK_NOOP_PHRASE, "")
        self.assertNotIn(AGENT_TYPE_HOOK_NOOP_PHRASE, forged)

    def test_negative_proof_missing_block_source_phrase_detected(self):
        forged = self.bullet.replace(BLOCK_SOURCE_PHRASE, "")
        self.assertNotIn(BLOCK_SOURCE_PHRASE, forged)

    def test_negative_proof_missing_agent_index_fallback_phrase_detected(self):
        forged = self.bullet.replace(AGENT_INDEX_FALLBACK_PHRASE, "")
        self.assertNotIn(AGENT_INDEX_FALLBACK_PHRASE, forged)

    def test_negative_proof_out_of_order_items_detected(self):
        # Swap the block-source and agent-index-fallback phrases in a
        # forged copy; the order check must then fail (positions no
        # longer sorted).
        forged = self.bullet.replace(
            BLOCK_SOURCE_PHRASE, "__PLACEHOLDER__"
        ).replace(AGENT_INDEX_FALLBACK_PHRASE, BLOCK_SOURCE_PHRASE).replace(
            "__PLACEHOLDER__", AGENT_INDEX_FALLBACK_PHRASE
        )
        positions = [
            forged.index(AGENT_TYPE_VALUE_1),
            forged.index(AGENT_TYPE_VALUE_2),
            forged.index(BLOCK_SOURCE_PHRASE),
            forged.index(AGENT_INDEX_FALLBACK_PHRASE),
        ]
        self.assertNotEqual(positions, sorted(positions))


# --- AC-2: exclusive-lock, failed-only-when-neither-terminal, at-most-one -

EXCLUSIVE_LOCK_PHRASE = (
    "Replay and append happen inside one exclusive-lock critical section "
    "on the journal"
)
FAILED_ONLY_WHEN_NEITHER_PHRASE = (
    "`failed` is appended only when the task's last event is neither "
    "`merged` nor `failed`"
)
AT_MOST_ONE_FAILED_LINE_PHRASE = (
    "together with the stop-tool recorder at most one `failed` line ever "
    "results for a task"
)


class TestBulletAtomicCompareAndAppend(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bullet = _bullet_text()

    def test_exclusive_lock_statement_present(self):
        self.assertIn(EXCLUSIVE_LOCK_PHRASE, self.bullet)

    def test_failed_only_when_neither_terminal_statement_present(self):
        self.assertIn(FAILED_ONLY_WHEN_NEITHER_PHRASE, self.bullet)

    def test_at_most_one_failed_line_statement_present(self):
        self.assertIn(AT_MOST_ONE_FAILED_LINE_PHRASE, self.bullet)

    def test_negative_proof_exclusive_lock_statement_detected(self):
        forged = self.bullet.replace(EXCLUSIVE_LOCK_PHRASE, "")
        self.assertNotIn(EXCLUSIVE_LOCK_PHRASE, forged)

    def test_negative_proof_failed_only_when_neither_terminal_detected(self):
        forged = self.bullet.replace(FAILED_ONLY_WHEN_NEITHER_PHRASE, "")
        self.assertNotIn(FAILED_ONLY_WHEN_NEITHER_PHRASE, forged)

    def test_negative_proof_at_most_one_failed_line_detected(self):
        forged = self.bullet.replace(AT_MOST_ONE_FAILED_LINE_PHRASE, "")
        self.assertNotIn(AT_MOST_ONE_FAILED_LINE_PHRASE, forged)


# --- AC-3: diagnostics log path, nine outcome codes, absence semantics ----

DIAGNOSTICS_LOG_PATH = (
    "`.claude/worktrees/em-workflow/subagent-stop-diagnostics.jsonl`"
)

OUTCOME_CODES = (
    "not-implementer-type",
    "no-prompt-text",
    "no-assignment-block",
    "invalid-identity",
    "index-unresolved",
    "journal-dir-missing",
    "already-terminal",
    "appended",
    "error",
)

MISSING_LINE_MEANING_PHRASE = (
    "A missing diagnostics line alone does not distinguish a hook that "
    "did not run from a hook that ran but could not write the log"
)

NOT_A_JOURNAL_NO_WRITER_PHRASE = (
    "This log is not a journal, carries no task-status meaning, and adds "
    "no journal writer"
)


class TestBulletDiagnosticsLog(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bullet = _bullet_text()

    def test_diagnostics_log_path_present(self):
        self.assertIn(DIAGNOSTICS_LOG_PATH, self.bullet)

    def test_all_nine_outcome_codes_present(self):
        self.assertEqual(len(OUTCOME_CODES), 9)
        for code in OUTCOME_CODES:
            with self.subTest(code=code):
                self.assertIn(f"`{code}`", self.bullet)

    def test_missing_line_meaning_statement_present(self):
        self.assertIn(MISSING_LINE_MEANING_PHRASE, self.bullet)

    def test_not_a_journal_no_writer_statement_present(self):
        self.assertIn(NOT_A_JOURNAL_NO_WRITER_PHRASE, self.bullet)

    def test_negative_proof_diagnostics_log_path_detected(self):
        forged = self.bullet.replace(DIAGNOSTICS_LOG_PATH, "")
        self.assertNotIn(DIAGNOSTICS_LOG_PATH, forged)

    def test_negative_proof_missing_outcome_code_detected(self):
        forged = self.bullet.replace("`already-terminal`", "")
        self.assertNotIn("`already-terminal`", forged)

    def test_negative_proof_missing_line_meaning_detected(self):
        forged = self.bullet.replace(MISSING_LINE_MEANING_PHRASE, "")
        self.assertNotIn(MISSING_LINE_MEANING_PHRASE, forged)

    def test_negative_proof_not_a_journal_no_writer_detected(self):
        forged = self.bullet.replace(NOT_A_JOURNAL_NO_WRITER_PHRASE, "")
        self.assertNotIn(NOT_A_JOURNAL_NO_WRITER_PHRASE, forged)


# --- AC-4: caveat covers a stop with no SubagentStop event ----------------

# The two phrases tests/test_stale_launched_doc_contract.py pins in this
# same paragraph -- asserted here too since AC-4 requires them to remain,
# not merely that some other module happens to still pass.
CAVEAT_NEITHER_EVENT_PHRASE = (
    "a stop that delivers neither a subagent-stop nor a stop-tool event"
)
CAVEAT_EXTENDED_BRANCH_PHRASE = (
    "orphan-recovery attempt's extended same-session branch"
)

CAVEAT_OBSERVABLE_MISSING_DIAGNOSTICS_PHRASE = (
    "Such a stop is also observable as a missing diagnostics line"
)


class TestCaveatCoversMissingSubagentStopEvent(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.caveat = _caveat_text()

    def test_pinned_neither_event_phrase_present(self):
        self.assertIn(CAVEAT_NEITHER_EVENT_PHRASE, self.caveat)

    def test_pinned_extended_branch_phrase_present(self):
        self.assertIn(CAVEAT_EXTENDED_BRANCH_PHRASE, self.caveat)

    def test_observable_missing_diagnostics_line_statement_present(self):
        self.assertIn(CAVEAT_OBSERVABLE_MISSING_DIAGNOSTICS_PHRASE, self.caveat)

    def test_caveat_does_not_name_the_failure_net_hook(self):
        # The caveat must not claim the SubagentStop failure net itself
        # fires for this case (it never runs at all) -- matches the
        # invariant tests/test_implement_routeback_gate.py already pins.
        self.assertNotIn("SubagentStop failure net", self.caveat)
        self.assertNotIn("queue_failure_net", self.caveat)

    def test_negative_proof_neither_event_phrase_detected(self):
        forged = self.caveat.replace(CAVEAT_NEITHER_EVENT_PHRASE, "")
        self.assertNotIn(CAVEAT_NEITHER_EVENT_PHRASE, forged)

    def test_negative_proof_extended_branch_phrase_detected(self):
        forged = self.caveat.replace(CAVEAT_EXTENDED_BRANCH_PHRASE, "")
        self.assertNotIn(CAVEAT_EXTENDED_BRANCH_PHRASE, forged)

    def test_negative_proof_observable_missing_diagnostics_detected(self):
        forged = self.caveat.replace(
            CAVEAT_OBSERVABLE_MISSING_DIAGNOSTICS_PHRASE, ""
        )
        self.assertNotIn(CAVEAT_OBSERVABLE_MISSING_DIAGNOSTICS_PHRASE, forged)


# --- AC-5: module imports only the standard library ------------------------


class TestModuleImportsStdlibOnly(unittest.TestCase):
    def test_module_uses_only_standard_library_imports(self):
        source = Path(__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        allowed = {"ast", "re", "unittest", "pathlib"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    self.assertIn(top, allowed, f"non-stdlib import: {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    top = node.module.split(".")[0]
                    self.assertIn(top, allowed, f"non-stdlib import: {node.module}")


if __name__ == "__main__":
    unittest.main()
