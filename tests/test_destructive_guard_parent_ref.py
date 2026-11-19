"""Regression tests for feature "rm-parent-ref-self-config-deny"
(feature-docs/rm-parent-ref-self-config-deny/tasks/task0001.md): an rm operand
whose raw form matches the protected self-config pattern but whose
`..`-folded form leaves the protected area is no longer taken out of the
recursive-delete deny pool, so its recursive deletion is decided as
deny / rm-recursive instead of being absorbed by the self-modification ask.

The scenarios whose decision does not depend on HOME are in the case table
(em-workflow/hooks/tests/destructive-guard-cases.json, labels beginning
`rm-parent-ref-self-config-deny TS-`). The case-table runner cannot replace
HOME, so the scenarios that do depend on it are checked here:

- TS-6: with HOME outside /home, `~/.claude/skills/foo` is still a protected
  self-config path (its raw and folded forms match, its normalized form does
  not), and `~/.claude/skills/../../valuable` is not.
- TS-12: the anchor rule. A `..` that consumes the leading `~` leaves the
  protected area whatever follows, so a later literal `~` segment does not
  rebuild a home-anchored form. With HOME outside /home the operand is
  decided as deny / rm-recursive; with HOME under /home its normalized form
  still matches the pattern and the decision stays ask / self-modification.

The hook runs as a subprocess with PreToolUse JSON on standard input, with
HOME and PATH supplied by the test and CLAUDE_BATCH absent. No test imports
the hook as a module; the structural checks (AC-5, AC-6) read its source with
the ast module. Only the standard library is used.
"""

import ast
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GUARD_PATH = REPO_ROOT / "em-workflow" / "hooks" / "destructive-guard.py"

# A HOME that is not under /home, is not inside any area the hook treats as a
# safe deletion target (/tmp, /var/tmp, the relative build / scratch roots), and
# whose last segment is not a literal `~`. It need not exist. A HOME under the
# system temp directory would make every `..` target land in a safe deletion
# area and give no rm-recursive record at all.
HOME_OUTSIDE_HOME = "/opt/parent-ref-test-home"
# The placeholder user the case table already uses for a HOME-style path.
HOME_UNDER_HOME = "/home/user"

REASON_ID = re.compile(r"^\[destructive-guard/([\w-]+)\]")


def decision(command, home):
    """(permissionDecision, reason id) of the hook for COMMAND with HOME set to
    HOME. The environment is built from scratch, so CLAUDE_BATCH is absent
    whatever the environment of the suite is."""
    env = {"HOME": home, "PATH": "", "PYTHONDONTWRITEBYTECODE": "1"}
    payload = {"tool_name": "Bash", "tool_input": {"command": command}}
    proc = subprocess.run(
        [sys.executable, str(GUARD_PATH)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip(), "the hook gave no decision"
    out = json.loads(proc.stdout)["hookSpecificOutput"]
    match = REASON_ID.match(out["permissionDecisionReason"])
    return out["permissionDecision"], match.group(1) if match else None


class TestHomeOutsideHomeChoice(unittest.TestCase):
    """AC-4 (NFR2). The HOME the tests below use meets the conditions the
    scenarios rest on."""

    def test_the_home_is_not_under_home(self):
        self.assertNotRegex(HOME_OUTSIDE_HOME, r"^/home(?:/|$)")

    def test_the_home_is_not_in_a_safe_deletion_area(self):
        for root in ("/tmp", "/var/tmp"):
            self.assertFalse(
                HOME_OUTSIDE_HOME == root or HOME_OUTSIDE_HOME.startswith(root + "/")
            )

    def test_the_last_segment_of_the_home_is_not_a_literal_tilde(self):
        self.assertNotEqual(HOME_OUTSIDE_HOME.rstrip("/").split("/")[-1], "~")

    def test_the_hook_runs_without_claude_batch(self):
        # decision() builds the environment from scratch; CLAUDE_BATCH would
        # turn every `ask` below into a `deny`.
        self.assertEqual(
            decision("rm -rf ~/.claude/skills/foo", HOME_OUTSIDE_HOME)[0], "ask"
        )


class TestParentRefWithHomeOutsideHome(unittest.TestCase):
    """AC-4 (FR1, FR2, NFR2, TM-1). TS-6 and TS-12 with HOME outside /home."""

    def check(self, command, want_decision, want_rule):
        with self.subTest(command=command):
            self.assertEqual(
                decision(command, HOME_OUTSIDE_HOME), (want_decision, want_rule)
            )

    def test_ts6_a_protected_operand_stays_protected(self):
        # Raw and folded forms match, the normalized form does not (HOME is
        # not under /home): the raw-or-normalized structure keeps it protected.
        self.check("rm -rf ~/.claude/skills/foo", "ask", "self-modification")

    def test_ts6_a_parent_ref_out_of_the_protected_area_is_denied(self):
        self.check(
            "rm -rf ~/.claude/skills/../../valuable", "deny", "rm-recursive"
        )

    def test_ts12_a_later_tilde_segment_does_not_rebuild_the_anchor(self):
        # The third `..` consumes the leading `~`; a plain lexical fold would
        # turn the operand back into `~/.claude/hooks/x`, which matches.
        self.check(
            "rm -rf ~/.claude/skills/../../../~/.claude/hooks/x",
            "deny",
            "rm-recursive",
        )


class TestSubstitutionHeadedRoute(unittest.TestCase):
    """AC-5 (FR3). The path where a command substitution leads the statement
    applies the same rule as the plain rm path: the exclusion only happens
    when the statement's own self-modification `ask` was held, which the
    redirect to a protected file provides here (the plain TS-7 command holds
    none, so there every operand stays in the deny pool whatever the rule)."""

    REDIRECT = " > ~/.claude/settings.json"

    def test_a_parent_ref_out_of_the_protected_area_stays_in_the_deny_pool(self):
        command = (
            "$(printf rm) -rf ~/.claude/skills/foo "
            "~/.claude/skills/../../valuable" + self.REDIRECT
        )
        self.assertEqual(
            decision(command, HOME_OUTSIDE_HOME), ("deny", "rm-recursive")
        )

    def test_a_protected_operand_is_still_left_out_of_the_deny_pool(self):
        command = "$(printf rm) -rf ~/.claude/skills/foo" + self.REDIRECT
        self.assertEqual(
            decision(command, HOME_OUTSIDE_HOME), ("ask", "self-modification")
        )

    def test_the_plain_path_gives_the_same_decisions(self):
        for command, want in (
            (
                "rm -rf ~/.claude/skills/foo ~/.claude/skills/../../valuable"
                + self.REDIRECT,
                ("deny", "rm-recursive"),
            ),
            (
                "rm -rf ~/.claude/skills/foo" + self.REDIRECT,
                ("ask", "self-modification"),
            ),
        ):
            with self.subTest(command=command):
                self.assertEqual(decision(command, HOME_OUTSIDE_HOME), want)


class TestAnchorRuleWithHomeUnderHome(unittest.TestCase):
    """AC-4 (FR1, NFR1). The anchor rule only makes operands unprotected; the
    normalized form still protects an operand it matches."""

    def test_ts12_the_normalized_form_still_protects_with_home_under_home(self):
        # `/home/user` + the folded operand is `/home/~/.claude/hooks/x`, which
        # SELF_CONFIG reads as a `/home/<name>/.claude/hooks/` path.
        self.assertEqual(
            decision(
                "rm -rf ~/.claude/skills/../../../~/.claude/hooks/x", HOME_UNDER_HOME
            ),
            ("ask", "self-modification"),
        )

    def test_ts6_the_parent_ref_out_of_the_area_is_denied_with_home_under_home(self):
        self.assertEqual(
            decision("rm -rf ~/.claude/skills/../../valuable", HOME_UNDER_HOME),
            ("deny", "rm-recursive"),
        )


class TestRuleLivesInOneFunction(unittest.TestCase):
    """AC-5, AC-6 (FR3, FR4, NFR2). The new rule is inside
    rm_protected_operand_numbers() alone, both callers call that one function
    the same way, and its docstring states the rule. The hook's source is
    parsed, never imported or run."""

    @classmethod
    def setUpClass(cls):
        cls.tree = ast.parse(GUARD_PATH.read_text(encoding="utf-8"))
        cls.functions = {
            node.name: node
            for node in cls.tree.body
            if isinstance(node, ast.FunctionDef)
        }

    def calls_of(self, name):
        """[(name of the top-level function holding the call, the call)] for
        every call of the module-level function NAME."""
        found = []
        for holder in self.functions.values():
            for node in ast.walk(holder):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == name
                ):
                    found.append((holder.name, node))
        return found

    def docstring(self, name):
        return " ".join((ast.get_docstring(self.functions[name]) or "").split())

    def test_the_fold_is_called_only_from_the_protected_operand_function(self):
        self.assertIn("fold_parent_refs", self.functions)
        holders = {holder for holder, _ in self.calls_of("fold_parent_refs")}
        self.assertEqual(holders, {"rm_protected_operand_numbers"})

    def test_both_call_sites_call_the_one_function_with_the_same_shape(self):
        calls = self.calls_of("rm_protected_operand_numbers")
        self.assertEqual(len(calls), 2)
        for holder, call in calls:
            with self.subTest(holder=holder, line=call.lineno):
                self.assertEqual(holder, "main")
                self.assertEqual(len(call.args), 1)
                self.assertEqual(call.keywords, [])

    def test_the_fold_reads_no_filesystem_and_expands_nothing(self):
        names = {
            node.id
            for node in ast.walk(self.functions["fold_parent_refs"])
            if isinstance(node, ast.Name)
        }
        attributes = {
            node.attr
            for node in ast.walk(self.functions["fold_parent_refs"])
            if isinstance(node, ast.Attribute)
        }
        self.assertFalse(
            names & {"os", "open", "Path", "subprocess", "normalize_candidate"}, names
        )
        self.assertFalse(
            attributes
            & {"expanduser", "realpath", "stat", "exists", "environ", "getenv"},
            attributes,
        )

    def test_the_docstring_states_the_rule_and_not_the_old_one(self):
        text = self.docstring("rm_protected_operand_numbers")
        self.assertNotIn("the way check_self_modification() matches a write target", text)
        self.assertNotIn("the raw operand, or its normalized form", text)
        for phrase in (
            "raw form matches AND its `..`-folded form",
            "`~` and `$HOME` not expanded",
            "consumes the leading `~` / `$HOME` anchor",
            "normalize_candidate()",
            "alone, with no filesystem access",
            "check_self_modification() itself is unchanged",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)

    def test_check_self_modification_still_matches_the_raw_or_normalized_form(self):
        source = ast.get_source_segment(
            GUARD_PATH.read_text(encoding="utf-8"),
            self.functions["check_self_modification"],
        )
        self.assertIn(
            "SELF_CONFIG.search(target) or SELF_CONFIG.search(normalized)", source
        )
        self.assertNotIn("fold_parent_refs", source)


if __name__ == "__main__":
    unittest.main()
