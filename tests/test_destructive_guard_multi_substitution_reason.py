"""Regression tests for feature "destructive-guard-multi-substitution-reason"
(feature-docs/destructive-guard-multi-substitution-reason/tasks/task0001.md):
when one command carries two or more rm targets built entirely from command
substitution, destructive-guard's reason text names each of them by a distinct
positional designation, `N番目のrmのM番目の対象[`$(...)`]`, in the order the
targets are written in the original command string. The stand-in `$(...)` is
the same for every such target, so the position alone tells them apart; no
substitution body text reaches the reason text; and the decision and the reason
id stay what they were.

Every case drives the guard as a subprocess with PreToolUse JSON on standard
input and asserts on `permissionDecision` / `permissionDecisionReason`. No test
imports the guard as a module. The child environment is built explicitly: the
HOME and PATH this module chooses, plus CLAUDE_BATCH only for the one batch
case. Nothing is inherited from the runner's environment, so the result is the
same whether or not the runner itself has CLAUDE_BATCH set (NFR1). Only the
standard library is used.

Covers task0001 Acceptance Criteria:

- AC-1 (NFR1): this module is collected by the project's unittest discovery,
  uses only the standard library, runs the hook as a child process, and gives
  the same results with and without CLAUDE_BATCH in the runner's environment.
- AC-2 (FR1, FR3; TM-1, TM-2): `rm -rf $(cat a) $(cat b)` is ask (deny under
  CLAUDE_BATCH), rm-unresolvable, with both designations in order and no body
  text.
- AC-3 (FR2): two `rm` statements, one substitution target each.
- AC-4 (FR7, FR8, FR9; TM-2): backtick, mixed and process-substitution forms.
- AC-5 (FR10; TM-2): a static target between two substitutions keeps its
  position.
- AC-6 (FR11; TM-1, TM-2): a body that carries a marker string never reaches
  the reason text.
- AC-7 (FR4, FR5, FR6, NFR2): the guard's own case suite and the project's
  unittest discovery both pass; that is the project's test command, not a
  test of this module.
"""

import json
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
GUARD_PATH = REPO_ROOT / "em-workflow" / "hooks" / "destructive-guard.py"

RULE_PATTERN = re.compile(r"\[destructive-guard/([\w-]+)\]")
# Same form as DESIGNATION_PATTERN in test_destructive_guard_rm_reason_positions.py.
DESIGNATION_PATTERN = re.compile(r"\d+番目のrmの\d+番目の対象(?:\[`[^`]*`\])?")

# Test-controlled, never the real environment's. Neither needs to exist: the
# hook never touches the filesystem for these commands. An empty PATH makes
# shutil.which() find nothing, so the result never depends on the machine.
FIXED_HOME = "/home/multi-substitution-reason-test-home"
EMPTY_PATH = ""

STANDIN = "$(...)"


def D(invocation, target):
    """The designation of the TARGETth operand of the INVOCATIONth rm when that
    operand is built entirely from command substitution."""
    return f"{invocation}番目のrmの{target}番目の対象[`{STANDIN}`]"


def run_guard(command, batch=False):
    """Run the guard as a child process with an EXPLICITLY built environment
    -- never `dict(os.environ)` -- so HOME, PATH and CLAUDE_BATCH are exactly
    what this module intends."""
    env = {"HOME": FIXED_HOME, "PATH": EMPTY_PATH}
    if batch:
        env["CLAUDE_BATCH"] = "1"
    return subprocess.run(
        [sys.executable, str(GUARD_PATH)],
        input=json.dumps({"tool_name": "Bash", "tool_input": {"command": command}}),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )


def decision(command, batch=False):
    """Run the guard over COMMAND and return (decision, reason id, reason)."""
    result = run_guard(command, batch=batch)
    assert result.returncode == 0, f"guard exited {result.returncode}: {result.stderr}"
    assert result.stdout.strip(), "guard produced no output (unexpected deferral)"
    out = json.loads(result.stdout)["hookSpecificOutput"]
    reason = out.get("permissionDecisionReason", "")
    rule_match = RULE_PATTERN.search(reason)
    return out["permissionDecision"], (rule_match.group(1) if rule_match else None), reason


def designations(reason):
    """Every designation in REASON, in order of appearance."""
    return DESIGNATION_PATTERN.findall(reason)


class MultiSubstitutionCase(unittest.TestCase):
    """Shared checks. A failure message names the TS."""

    def check(
        self,
        ts,
        command,
        expected_designations,
        decision_expected=None,
        rule_expected=None,
        batch=False,
        absent=(),
    ):
        got_decision, got_rule, reason = decision(command, batch=batch)
        context = f"{ts}: {command!r} batch={batch}\nreason: {reason}"
        # Whole ordered lists: one equality covers order, distinctness and
        # "each exactly once" (NFR4).
        self.assertEqual(designations(reason), expected_designations, context)
        if decision_expected is not None:
            self.assertEqual(got_decision, decision_expected, context)
        if rule_expected is not None:
            self.assertEqual(got_rule, rule_expected, context)
        for text in absent:
            self.assertNotIn(text, reason, context)


# --- AC-2: two substitution targets of one rm -------------------------------


class TestTwoSubstitutionTargetsOfOneRm(MultiSubstitutionCase):
    """AC-2 (FR1, FR3; TM-1, TM-2)."""

    COMMAND = "rm -rf $(cat a) $(cat b)"

    def test_ts1_ask_names_each_target_by_position_and_renders_no_body(self):
        self.check(
            "TS-1",
            self.COMMAND,
            [D(1, 1), D(1, 2)],
            decision_expected="ask",
            rule_expected="rm-unresolvable",
            batch=False,
            absent=("cat a", "cat b"),
        )

    def test_ts3_batch_denies_with_the_same_designations_and_the_same_rule(self):
        self.check(
            "TS-3",
            self.COMMAND,
            [D(1, 1), D(1, 2)],
            decision_expected="deny",
            rule_expected="rm-unresolvable",
            batch=True,
            absent=("cat a", "cat b"),
        )

    def test_the_two_designations_differ(self):
        # Two targets sharing the one stand-in are told apart by position
        # alone: the designations are two entries, never one repeated.
        _, _, reason = decision(self.COMMAND)
        found = designations(reason)
        self.assertEqual(len(found), 2, reason)
        self.assertNotEqual(found[0], found[1], reason)


# --- AC-3: one substitution target in each of two rm statements -------------


class TestOneSubstitutionTargetPerRm(MultiSubstitutionCase):
    """AC-3 (FR2). FR2 pins no decision and no reason id, so neither is
    asserted."""

    def test_ts2_two_rm_statements_get_one_ordinal_each(self):
        self.check(
            "TS-2",
            "rm -rf $(cat a); rm -rf $(cat b)",
            [D(1, 1), D(2, 1)],
        )


# --- AC-4: backtick, mixed and process-substitution forms -------------------


class TestSubstitutionForms(MultiSubstitutionCase):
    """AC-4 (FR7, FR8, FR9; TM-2). A backtick substitution becomes the same
    stand-in as a dollar-paren substitution; in a process substitution the
    opening and closing operators are not counted as targets."""

    def test_ts5_backtick_substitutions(self):
        self.check(
            "TS-5",
            "rm -rf `cat a` `cat b`",
            [D(1, 1), D(1, 2)],
            decision_expected="ask",
            rule_expected="rm-unresolvable",
        )

    def test_ts6_dollar_paren_then_backtick_substitution(self):
        self.check(
            "TS-6",
            "rm -rf $(cat a) `cat b`",
            [D(1, 1), D(1, 2)],
            decision_expected="ask",
            rule_expected="rm-unresolvable",
        )

    def test_ts7_process_substitutions(self):
        self.check(
            "TS-7",
            "rm -rf <(cat a) <(cat b)",
            [D(1, 1), D(1, 2)],
            decision_expected="ask",
            rule_expected="rm-unresolvable",
        )


# --- AC-5: a static target between two substitutions keeps its position -----


class TestStaticTargetBetweenSubstitutions(MultiSubstitutionCase):
    """AC-5 (FR10; TM-2). The static target /tmp/scratch is safe and produces
    no record, yet it still occupies target position 2."""

    def test_ts8_static_target_keeps_its_position(self):
        self.check(
            "TS-8",
            "rm -rf $(cat a) /tmp/scratch $(cat b)",
            [D(1, 1), D(1, 3)],
            decision_expected="ask",
            rule_expected="rm-unresolvable",
            absent=("1番目のrmの2番目の対象",),
        )


# --- AC-6: a body that carries a marker string never reaches the reason -----


class TestBodyTextNeverRendered(MultiSubstitutionCase):
    """AC-6 (FR11; TM-1, TM-2)."""

    def test_ts9_marker_strings_in_the_bodies_are_absent(self):
        self.check(
            "TS-9",
            "rm -rf $(printf MULTISUBBODYALPHA) $(printf MULTISUBBODYBETA)",
            [D(1, 1), D(1, 2)],
            decision_expected="ask",
            rule_expected="rm-unresolvable",
            absent=("MULTISUBBODYALPHA", "MULTISUBBODYBETA"),
        )


# --- AC-1: the result does not depend on the runner's environment -----------


class TestRunnerEnvironmentIsNotInherited(MultiSubstitutionCase):
    """AC-1 (NFR1). The child environment carries CLAUDE_BATCH only in the
    batch case, so a runner that has it set (an unattended run) gets the same
    results as one that does not."""

    def test_runner_with_claude_batch_set_still_gets_ask_for_the_non_batch_case(self):
        with mock.patch.dict(os.environ, {"CLAUDE_BATCH": "1"}):
            self.check(
                "TS-1 under a runner with CLAUDE_BATCH set",
                "rm -rf $(cat a) $(cat b)",
                [D(1, 1), D(1, 2)],
                decision_expected="ask",
                rule_expected="rm-unresolvable",
                batch=False,
            )

    def test_runner_without_claude_batch_still_gets_deny_for_the_batch_case(self):
        env = {k: v for k, v in os.environ.items() if k != "CLAUDE_BATCH"}
        with mock.patch.dict(os.environ, env, clear=True):
            self.check(
                "TS-3 under a runner without CLAUDE_BATCH",
                "rm -rf $(cat a) $(cat b)",
                [D(1, 1), D(1, 2)],
                decision_expected="deny",
                rule_expected="rm-unresolvable",
                batch=True,
            )

    def test_the_child_environment_is_exactly_what_the_module_builds(self):
        with mock.patch.dict(os.environ, {"CLAUDE_BATCH": "1", "SOME_OTHER": "x"}):
            with mock.patch("subprocess.run") as fake_run:
                fake_run.return_value = subprocess.CompletedProcess([], 0, "", "")
                run_guard("rm -rf $(cat a) $(cat b)", batch=False)
                run_guard("rm -rf $(cat a) $(cat b)", batch=True)
        non_batch_env = fake_run.call_args_list[0].kwargs["env"]
        batch_env = fake_run.call_args_list[1].kwargs["env"]
        self.assertEqual(non_batch_env, {"HOME": FIXED_HOME, "PATH": EMPTY_PATH})
        self.assertEqual(
            batch_env, {"HOME": FIXED_HOME, "PATH": EMPTY_PATH, "CLAUDE_BATCH": "1"}
        )


if __name__ == "__main__":
    unittest.main()
