"""Regression tests for feature "destructive-guard-mixed-rm-precedence"
(feature-docs/destructive-guard-mixed-rm-precedence/tasks/task0001.md): in a
compound command, a recursive delete that the hook denies on its own wins over
a non-rm `ask` that sits beside it, whichever comes first. The non-rm asks are
held until the scan ends and are compared with the pooled rm decisions before
any CLAUDE_BATCH demotion. The case runner gains an optional `rule` key, so a
case can pin the reason id as well as the decision.

The exhaustive scenario table lives in
em-workflow/hooks/tests/destructive-guard-cases.json (the cases that carry a
`rule` in their fourth element) and runs through run-destructive-guard.py.
This module checks what the table cannot:

- AC-3 / AC-5: the reason text of a winning rm `deny`, with and without
  CLAUDE_BATCH, and the designation of the rm that is not excluded.
- AC-6: the case table keeps its existing cases and only appends; the output
  is byte-identical across runs.
- AC-7: the runner's `rule` key, against a stub guard and a temporary case
  file, and against the real hook.
- AC-8: the hook's comments and docstrings no longer carry the statements the
  held asks made stale. The hook's text is read; it is not imported there.
- FR4: a lexer budget overrun raised out of the statement iteration ends the
  scan without losing an rm `deny` that was already read.

The hook runs as a subprocess with PreToolUse JSON on standard input. HOME and
PATH are always supplied by the test whenever reason text is compared. Only
the standard library is used.
"""

import ast
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOKS_DIR = REPO_ROOT / "em-workflow" / "hooks"
GUARD_PATH = HOOKS_DIR / "destructive-guard.py"
TESTS_DIR = HOOKS_DIR / "tests"
RUNNER_PATH = TESTS_DIR / "run-destructive-guard.py"
CASES_PATH = TESTS_DIR / "destructive-guard-cases.json"

FEATURE = "destructive-guard-mixed-rm-precedence"

# Test-controlled, never the real environment's. The empty PATH leaves no
# `gio` to find, so the deletion alternative in an rm reason is the same
# wherever the suite runs.
FIXED_HOME = "/home/mixed-rm-test-home"
NO_GIO_PATH = ""

RM = "rm -rf /home/user/valuable"
IAM = (
    "gcloud projects add-iam-policy-binding p "
    "--member=user:a@example.com --role=roles/owner"
)
NEST = "${ " * 80
MV_TEMPLATE = "mv -- <対象> /tmp/"
AMEND_SENTENCE = "`--amend` は既存コミットを書き換える"
DEMOTION_SENTENCE = "`ask` を `deny` に降格した"

# The cases of the table that existed before this feature: their number and
# the digest of their JSON form. Every one of them is still there, unchanged,
# and the new cases come after them.
PRE_EXISTING_CASE_COUNT = 1208
PRE_EXISTING_CASES_DIGEST = (
    "b7f82ca8a26095709b4d934f1301d2fe4691bbe1c95ee9ce192a2f7d702689ec"
)


def run_guard(command, batch=False, home=FIXED_HOME, path=NO_GIO_PATH):
    """The hook as a subprocess, fed one PreToolUse payload."""
    env = {"HOME": home, "PATH": path, "PYTHONDONTWRITEBYTECODE": "1"}
    if batch:
        env["CLAUDE_BATCH"] = "1"
    payload = {"tool_name": "Bash", "tool_input": {"command": command}}
    return subprocess.run(
        [sys.executable, str(GUARD_PATH)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )


def decision(command, batch=False):
    """(decision, reason id, reason text) of the hook for COMMAND."""
    proc = run_guard(command, batch=batch)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip(), "the hook gave no decision"
    out = json.loads(proc.stdout)["hookSpecificOutput"]
    reason = out["permissionDecisionReason"]
    match = re.match(r"\[destructive-guard/([\w-]+)\]", reason)
    return out["permissionDecision"], match.group(1) if match else None, reason


def load_runner(argv):
    """The runner as a module, loaded as `python3 run-destructive-guard.py
    *ARGV[1:]` would see it, without leaving a bytecode cache behind."""
    spec = importlib.util.spec_from_file_location(
        "run_destructive_guard_mixed_rm_under_test", RUNNER_PATH
    )
    module = importlib.util.module_from_spec(spec)
    with mock.patch.object(sys, "argv", argv), mock.patch.object(
        sys, "dont_write_bytecode", True
    ):
        spec.loader.exec_module(module)
    return module


def load_hook():
    """A hook module of its own, loaded with bytecode writing off."""
    spec = importlib.util.spec_from_file_location(
        "destructive_guard_mixed_rm_under_test", GUARD_PATH
    )
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def normalized(text):
    return re.sub(r"\s+", " ", text or "")


def feature_case_positions(cases):
    """The 0-based positions in CASES of this feature's cases: the cases whose
    label (second element) begins with the feature name and one space. A label
    of another feature whose name merely begins with FEATURE is not one."""
    prefix = FEATURE + " "
    return [i for i, case in enumerate(cases) if case[1].startswith(prefix)]


# --- AC-3: the reason of a winning rm deny is the rm reason ----------------


class TestRmDenyReasonText(unittest.TestCase):
    """AC-3 (FR3, NFR2). The command that holds a recursive delete and a
    git-amend `ask` gets the reason the recursive delete alone gets, with and
    without CLAUDE_BATCH."""

    MIXED = RM + " ; git commit --amend"

    def test_the_reason_equals_the_reason_of_the_rm_alone(self):
        for batch in (False, True):
            with self.subTest(batch=batch):
                tier, rule, reason = decision(self.MIXED, batch=batch)
                alone = decision(RM, batch=batch)
                self.assertEqual((tier, rule), ("deny", "rm-recursive"))
                self.assertEqual(reason, alone[2])

    def test_the_reason_designates_the_rm_and_offers_the_deletion_alternative(self):
        for batch in (False, True):
            with self.subTest(batch=batch):
                reason = decision(self.MIXED, batch=batch)[2]
                self.assertIn("1番目のrmの1番目の対象", reason)
                self.assertIn(MV_TEMPLATE, reason)

    def test_the_reason_carries_no_text_of_the_non_rm_check_or_the_demotion(self):
        for batch in (False, True):
            with self.subTest(batch=batch):
                reason = decision(self.MIXED, batch=batch)[2]
                self.assertNotIn(AMEND_SENTENCE, reason)
                self.assertNotIn(DEMOTION_SENTENCE, reason)
                self.assertNotIn("git-amend", reason)

    def test_the_segment_order_does_not_change_the_reason(self):
        for batch in (False, True):
            with self.subTest(batch=batch):
                first = decision(self.MIXED, batch=batch)
                last = decision("git commit --amend ; " + RM, batch=batch)
                self.assertEqual(first, last)

    def test_root_wins_over_a_held_ask_with_the_root_rule(self):
        for batch in (False, True):
            with self.subTest(batch=batch):
                tier, rule, _ = decision("rm -rf ~ ; git commit --amend", batch=batch)
                self.assertEqual((tier, rule), ("deny", "rm-root"))

    def test_a_non_rm_deny_still_ends_the_scan_at_once(self):
        # Precedence between two denies is out of scope: the non-rm deny that
        # is reached keeps its immediate exit.
        for command in (
            RM + " ; git push --force",
            "git push --force ; " + RM,
        ):
            with self.subTest(command=command):
                tier, rule, _ = decision(command)
                self.assertEqual(tier, "deny")
        self.assertEqual(decision("git push --force ; " + RM)[1], "git-force-push")


# --- AC-4 / AC-6: no-deny commands keep the reason id they had -------------


class TestNoDenyCommandsKeepTheirVerdict(unittest.TestCase):
    """AC-4, AC-6 (NFR2, NFR3). Every expected value below was recorded from
    the hook BEFORE it was edited for this task."""

    PINNED = [
        ("rm -rf tmp/$X ; git commit --amend", "ask", "git-amend"),
        ("git commit --amend ; rm -rf tmp/$X", "ask", "git-amend"),
        ("git commit --amend ; chmod -R 777 /etc", "ask", "git-amend"),
        ("chmod -R 777 /etc ; git commit --amend", "ask", "chmod-broad"),
        ("git commit --amend\n" + NEST, "ask", "git-amend"),
        ("echo x\n" + NEST, "ask", "scan-budget-exceeded"),
        ("rm -rf $A $B", "ask", "rm-unresolvable"),
        ("rm -rf ~/.claude/skills/foo", "ask", "self-modification"),
    ]

    def test_decision_and_reason_id_equal_the_recorded_values(self):
        for command, tier, rule in self.PINNED:
            with self.subTest(command=command[:60]):
                got = decision(command)
                self.assertEqual(got[:2], (tier, rule))

    def test_an_unattended_run_demotes_the_ask_that_is_emitted(self):
        for command, tier, rule in self.PINNED:
            with self.subTest(command=command[:60]):
                got = decision(command, batch=True)
                self.assertEqual(got[:2], ("deny" if tier == "ask" else tier, rule))

    def test_the_scan_budget_ask_does_not_hide_an_rm_deny_read_before_it(self):
        tier, rule, reason = decision(RM + "\n" + NEST)
        self.assertEqual((tier, rule), ("deny", "rm-recursive"))
        self.assertEqual(reason, decision(RM)[2])
        tier, rule, _ = decision(RM + "\n" + NEST, batch=True)
        self.assertEqual((tier, rule), ("deny", "rm-recursive"))


# --- AC-5: the FR8 exclusion -------------------------------------------------


class TestProtectedSelfConfigExclusion(unittest.TestCase):
    """AC-5 (FR8, TM-3). In a statement whose own rm deletion operand is a
    protected self-config path, the self-modification `ask` competes as an
    ordinary held `ask` and that statement's rm records are left out."""

    PROTECTED = "~/.claude/skills/foo"

    def test_the_other_rm_is_designated_by_its_place_in_the_command(self):
        for batch in (False, True):
            with self.subTest(batch=batch):
                tier, rule, reason = decision(
                    f"rm -rf {self.PROTECTED} ; {RM}", batch=batch
                )
                self.assertEqual((tier, rule), ("deny", "rm-recursive"))
                self.assertIn("2番目のrmの1番目の対象", reason)
                self.assertNotIn("1番目のrmの1番目の対象", reason)

    def test_the_other_rm_before_the_excluded_one_is_the_first(self):
        tier, rule, reason = decision(f"{RM} ; rm -rf {self.PROTECTED}")
        self.assertEqual((tier, rule), ("deny", "rm-recursive"))
        self.assertIn("1番目のrmの1番目の対象", reason)
        self.assertNotIn("2番目のrm", reason)

    def test_a_protected_and_an_unprotected_target_in_one_rm_stay_an_ask(self):
        self.assertEqual(
            decision(f"rm -rf {self.PROTECTED} /home/user/valuable")[:2],
            ("ask", "self-modification"),
        )

    def test_the_excluded_statement_alone_is_the_self_modification_ask(self):
        self.assertEqual(
            decision(f"rm -rf {self.PROTECTED}")[:2], ("ask", "self-modification")
        )
        self.assertEqual(
            decision(f"rm -rf {self.PROTECTED}", batch=True)[:2],
            ("deny", "self-modification"),
        )

    def test_a_redirect_target_alone_excludes_nothing(self):
        for command in (
            f"{RM} > ~/.claude/settings.json",
            f"{RM} >> ~/.claude/settings.json",
        ):
            with self.subTest(command=command):
                self.assertEqual(decision(command)[:2], ("deny", "rm-recursive"))

    def test_a_protected_path_in_another_statement_excludes_nothing(self):
        for command in (
            f"{RM} ; echo x > ~/.claude/settings.json",
            f"echo x > ~/.claude/settings.json ; {RM}",
            f"{RM} ; cp a {self.PROTECTED}",
            f"{RM} ; tee {self.PROTECTED}",
        ):
            with self.subTest(command=command):
                self.assertEqual(decision(command)[:2], ("deny", "rm-recursive"))

    def test_a_protected_path_in_a_derived_chunk_excludes_nothing(self):
        for command in (
            f"{RM} ; echo \"$(cp a {self.PROTECTED})\"",
            f"{RM} ; bash -c 'cp a {self.PROTECTED}'",
            f"{RM} ; eval 'cp a {self.PROTECTED}'",
            f"{RM} ; cat <<EOF\n$(cp a {self.PROTECTED})\nEOF",
        ):
            with self.subTest(command=command):
                self.assertEqual(decision(command)[:2], ("deny", "rm-recursive"))

    def test_on_the_parse_failure_fallback_the_operand_test_decides(self):
        # An unclosed quote sends the statement through the fallback, where the
        # self-modification check matches the whole segment. That match is not
        # enough to exclude the rm: a deletion operand has to match as well.
        self.assertEqual(
            decision(f"{RM} > ~/.claude/settings.json 'x")[:2],
            ("deny", "rm-recursive"),
        )
        self.assertEqual(
            decision(f"rm -rf {self.PROTECTED} \"x")[:2],
            ("ask", "self-modification"),
        )

    def test_the_spelling_of_the_protected_operand_does_not_matter(self):
        for operand in (
            "~/.claude/skills/foo",
            "$HOME/.claude/skills/foo",
            "~/.claude/../.claude/skills/foo",
            "'~/.claude/skills/foo'",
        ):
            with self.subTest(operand=operand):
                self.assertEqual(
                    decision(f"rm -rf {operand} ; {RM}")[:2], ("deny", "rm-recursive")
                )
                self.assertEqual(
                    decision(f"rm -rf {operand}")[:2], ("ask", "self-modification")
                )

    def test_the_protected_operand_of_the_substitution_headed_route_is_excluded(self):
        # The statement's rm invocation comes from the substitution route: its
        # operands are the remainder. The protected operand excludes it; the
        # other statement's rm decides.
        tier, rule, reason = decision(f"$(printf rm) -rf {self.PROTECTED} ; {RM}")
        self.assertEqual((tier, rule), ("deny", "rm-recursive"))
        self.assertIn("2番目のrmの1番目の対象", reason)


# --- AC-6: determinism and the case table ------------------------------------


class TestDeterminism(unittest.TestCase):
    """AC-6 (NFR2, NFR5). The same command always gives the same bytes."""

    def test_the_output_is_byte_identical_across_runs(self):
        for command, batch in (
            (RM + " ; git commit --amend", False),
            (RM + " ; git commit --amend", True),
            ("git commit --amend ; " + RM, False),
            (RM + "\n" + NEST, False),
        ):
            with self.subTest(command=command[:40], batch=batch):
                first = run_guard(command, batch=batch)
                second = run_guard(command, batch=batch)
                self.assertEqual(first.returncode, 0, first.stderr)
                self.assertEqual(first.stderr, "")
                self.assertEqual(first.stdout, second.stdout)


class TestCaseTable(unittest.TestCase):
    """AC-1, AC-2, AC-5, AC-6 (FR6, NFR1). The cases of the scenarios are in
    the table, rule-pinned, after every existing case."""

    @classmethod
    def setUpClass(cls):
        with open(CASES_PATH, encoding="utf-8") as f:
            cls.cases = json.load(f)
        cls.positions = feature_case_positions(cls.cases)
        cls.new = [cls.cases[i] for i in cls.positions]

    def test_the_feature_cases_form_one_run_right_after_the_existing_cases(self):
        positions = self.positions
        self.assertTrue(positions, "condition 1 failed: no case is selected")
        self.assertEqual(
            positions[0],
            PRE_EXISTING_CASE_COUNT,
            "condition 2 failed: the first selected case is at position "
            f"{positions[0]}, not right after the existing cases",
        )
        for before, after in zip(positions, positions[1:]):
            self.assertEqual(
                after,
                before + 1,
                f"condition 3 failed: the selected case at position {after} "
                f"does not follow the one at position {before}",
            )

    def test_every_existing_case_is_present_unchanged_and_first(self):
        existing = self.cases[:PRE_EXISTING_CASE_COUNT]
        self.assertEqual(len(existing), PRE_EXISTING_CASE_COUNT)
        digest = hashlib.sha256(json.dumps(existing, ensure_ascii=False).encode("utf-8"))
        self.assertEqual(digest.hexdigest(), PRE_EXISTING_CASES_DIGEST)

    def test_every_new_case_is_rule_pinned_and_named_after_the_feature(self):
        self.assertTrue(self.new)
        for case in self.new:
            with self.subTest(label=case[1]):
                self.assertEqual(len(case), 4)
                self.assertIsInstance(case[3].get("rule"), str)
                self.assertTrue(case[3]["rule"])
                self.assertTrue(case[1].startswith(FEATURE + " TS-"), case[1])
                self.assertLessEqual(set(case[3]), {"rule", "batch"})

    def test_the_new_cases_name_no_machine_specific_path(self):
        for case in self.new:
            with self.subTest(label=case[1]):
                self.assertNotRegex(case[2], r"/(?:Users|root)/|/home/(?!user/)")

    def test_each_scenario_has_its_case(self):
        rm_ask_forms = [
            "git commit --amend",
            "chmod -R 777 /etc",
            "terraform destroy",
            "kubectl delete pod x",
            IAM,
        ]
        expected = [
            # (decision, command, rule, batch)
            ("deny", RM + " ; git commit --amend", "rm-recursive", False),  # TS-1
            ("deny", "git commit --amend ; " + RM, "rm-recursive", False),  # TS-2
            ("deny", RM + " ; chmod -R 777 /etc", "rm-recursive", False),  # TS-3
            ("deny", "chmod -R 777 /etc ; " + RM, "rm-recursive", False),
            ("deny", RM + " && terraform destroy", "rm-recursive", False),  # TS-4
            ("deny", "terraform destroy && " + RM, "rm-recursive", False),
            ("deny", RM + " ; kubectl delete pod x", "rm-recursive", False),  # TS-5
            ("deny", "kubectl delete pod x ; " + RM, "rm-recursive", False),
            ("deny", RM + " ; " + IAM, "rm-recursive", False),  # TS-6
            ("deny", IAM + " ; " + RM, "rm-recursive", False),
            ("deny", RM + " ; git commit --amend", "rm-recursive", True),  # TS-7
            ("deny", "rm -rf ~ ; git commit --amend", "rm-root", False),  # TS-8
            ("deny", RM + " ; echo x > ~/.claude/settings.json", "rm-recursive", False),  # TS-9
            ("ask", "rm -rf tmp/$X ; git commit --amend", "git-amend", False),  # TS-10
            ("deny", RM + "\n" + NEST, "rm-recursive", False),  # TS-11
            ("ask", "rm -rf ~/.claude/skills/foo", "self-modification", False),  # TS-12
            ("deny", "rm -rf ~/.claude/skills/foo ; " + RM, "rm-recursive", False),  # TS-13
            ("deny", RM + " ; rm -rf ~/.claude/skills/foo", "rm-recursive", False),  # TS-14
            ("ask", "rm -rf ~/.claude/skills/foo /home/user/valuable", "self-modification", False),  # TS-15
            ("deny", "rm -rf ~/.claude/skills/foo", "self-modification", True),  # TS-16
            ("deny", RM + " && git commit --amend", "rm-recursive", False),  # TS-18
            ("deny", RM + " || git commit --amend", "rm-recursive", False),
            ("deny", RM + "\ngit commit --amend", "rm-recursive", False),
            ("deny", RM + " ; chown -R user /srv/x", "rm-recursive", False),  # TS-19
            ("deny", RM + " ; aws s3 rm s3://bucket/key", "rm-recursive", False),
            ("deny", RM + " ; systemctl stop example.service", "rm-recursive", False),
            ("deny", RM + " ; ssh host ls", "rm-recursive", False),
            ("deny", RM + " ; gh pr merge 42", "rm-recursive", False),
            ("deny", RM + " ; tar -xo -f a.tar", "rm-recursive", False),
            ("deny", RM + " > ~/.claude/settings.json", "rm-recursive", False),  # TS-20
            ("ask", "git commit --amend ; chmod -R 777 /etc", "git-amend", False),  # TS-21
            ("ask", "chmod -R 777 /etc ; git commit --amend", "chmod-broad", False),
            ("ask", "git commit --amend\n" + NEST, "git-amend", False),  # TS-22
        ]
        have = {
            (case[0], case[2], case[3].get("rule"), bool(case[3].get("batch")))
            for case in self.new
        }
        self.assertEqual(len(rm_ask_forms), 5)
        for item in expected:
            with self.subTest(command=item[1][:70], batch=item[3]):
                self.assertIn(item, have)

    def test_the_scenario_ids_are_all_named(self):
        labels = " ".join(case[1] for case in self.new)
        for number in list(range(1, 17)) + list(range(18, 23)):
            with self.subTest(scenario=number):
                self.assertRegex(labels, rf"\bTS-{number}\b")


def scenario_number(case):
    """The N of the `TS-N` a case's label names."""
    return int(re.search(r"\bTS-(\d+)\b", case[1]).group(1))


class TestScenarioCasesPassAgainstTheHook(unittest.TestCase):
    """AC-1 to AC-6 (FR1 to FR4, FR6, FR8, NFR1 to NFR4). Each case of the
    scenarios is judged the way run-destructive-guard.py judges it -- the hook
    as a subprocess, CLAUDE_BATCH cleared unless the case sets it, the
    decision and the pinned reason id both compared -- with one subtest per
    case, so a failure names the case."""

    @classmethod
    def setUpClass(cls):
        cls.runner = load_runner([str(RUNNER_PATH), str(GUARD_PATH)])
        with open(CASES_PATH, encoding="utf-8") as f:
            cases = json.load(f)
        cls.new = [cases[i] for i in feature_case_positions(cases)]

    def scenarios(self, numbers, rm_first=None):
        found = [case for case in self.new if scenario_number(case) in numbers]
        if rm_first is not None:
            found = [case for case in found if case[2].startswith(RM) == rm_first]
        return found

    def assert_pass(self, cases, count):
        self.assertEqual(len(cases), count)
        for case in cases:
            want, label, command = case[:3]
            cwd, batch, rule = self.runner.case_options(case)
            with self.subTest(label=label):
                got, reason = self.runner.verdict(command, batch=batch, cwd=cwd)
                self.assertEqual(got, want, reason[:200])
                self.assertEqual(self.runner.reason_id(reason), rule, reason[:200])

    def test_ac1_the_rm_first_forms_deny_with_rm_recursive(self):
        # TS-1, the rm-first forms of TS-3 to TS-6, TS-18 (three) and TS-19 (six).
        cases = self.scenarios({1, 3, 4, 5, 6, 18, 19}, rm_first=True)
        self.assert_pass(cases, 14)
        for case in cases:
            self.assertEqual((case[0], case[3]["rule"]), ("deny", "rm-recursive"))

    def test_ac2_the_non_rm_first_forms_deny_with_rm_recursive(self):
        # TS-2 and the reversed forms of TS-3 to TS-6.
        cases = self.scenarios({2, 3, 4, 5, 6}, rm_first=False)
        self.assert_pass(cases, 5)
        for case in cases:
            self.assertEqual((case[0], case[3]["rule"]), ("deny", "rm-recursive"))

    def test_ac3_batch_and_root_forms(self):
        cases = self.scenarios({7, 8})
        self.assert_pass(cases, 2)
        self.assertEqual({case[3]["rule"] for case in cases}, {"rm-recursive", "rm-root"})

    def test_ac4_the_scan_budget_early_stop(self):
        cases = self.scenarios({11, 22})
        self.assert_pass(cases, 2)
        self.assertEqual(
            sorted((case[0], case[3]["rule"]) for case in cases),
            [("ask", "git-amend"), ("deny", "rm-recursive")],
        )

    def test_ac5_the_protected_self_config_exclusion(self):
        self.assert_pass(self.scenarios({9, 12, 13, 14, 15, 16, 20}), 7)

    def test_ac6_the_no_deny_commands_keep_their_reason_ids(self):
        cases = self.scenarios({10, 21})
        self.assert_pass(cases, 3)
        self.assertEqual(
            sorted(case[3]["rule"] for case in cases),
            ["chmod-broad", "git-amend", "git-amend"],
        )


# --- AC-7: the runner's rule key -------------------------------------------


# The command is "<decision> <reason id>": the stub answers with that decision
# and a reason that starts with `[destructive-guard/<reason id>]`. A reason id
# of "-" gives the prefix without a rule, "!" a reason with no prefix at all.
# The runner's closing check (the unattended demotion) sends its own command;
# the stub answers it as the real hook does, with a `deny`.
STUB_GUARD = textwrap.dedent(
    """\
    import json, sys
    payload = json.load(sys.stdin)
    command = payload["tool_input"]["command"]
    if command.startswith("echo x > "):
        command = "deny settings"
    decision, _, rule = command.partition(" ")
    if rule == "!":
        reason = "stub reason with no prefix"
    elif rule in ("", "-"):
        reason = "[destructive-guard] stub reason"
    else:
        reason = "[destructive-guard/%s] stub reason" % rule
    json.dump({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": decision,
        "permissionDecisionReason": reason,
    }}, sys.stdout)
    """
)


class TestRunnerRuleKey(unittest.TestCase):
    """AC-7 (FR5). The runner compares the reason id of a case that pins one."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.stub = os.path.join(self.tmp.name, "stub-guard.py")
        with open(self.stub, "w", encoding="utf-8") as f:
            f.write(STUB_GUARD)
        self.runner = load_runner([str(RUNNER_PATH), self.stub])

    def run_cases(self, cases, runner=None):
        runner = runner or self.runner
        path = os.path.join(self.tmp.name, "cases.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(cases, f)
        out = io.StringIO()
        with mock.patch.object(runner, "CASES", path), contextlib.redirect_stdout(out):
            code = runner.main()
        return code, out.getvalue()

    def test_a_case_whose_decision_and_rule_both_match_passes(self):
        code, out = self.run_cases(
            [["deny", "both", "deny rm-recursive", {"rule": "rm-recursive"}]]
        )
        self.assertEqual(code, 0, out)
        self.assertIn("2/2 passed", out)

    def test_a_rule_pinned_case_may_also_carry_batch_and_cwd(self):
        code, out = self.run_cases(
            [["ask", "all keys", "ask git-amend", {"rule": "git-amend", "batch": True, "cwd": "/x"}]]
        )
        self.assertEqual(code, 0, out)

    def test_a_matching_decision_with_another_rule_fails_and_shows_the_obtained_id(self):
        code, out = self.run_cases(
            [["deny", "wrong rule", "deny git-amend", {"rule": "rm-recursive"}]]
        )
        self.assertEqual(code, 1, out)
        self.assertIn("FAIL", out)
        fail_lines = [ln for ln in out.splitlines() if "git-amend" in ln]
        self.assertTrue(fail_lines, out)

    def test_the_fail_line_still_shows_what_it_showed_before(self):
        code, out = self.run_cases(
            [["deny", "wrong decision", "ask rm-recursive", {"rule": "rm-recursive"}]]
        )
        self.assertEqual(code, 1, out)
        self.assertIn("FAIL deny  wrong decision", out)
        self.assertIn("got=ask", out)
        self.assertIn("stub reason", out)

    def test_a_pinned_rule_against_a_reason_with_no_reason_id_fails(self):
        for command in ("deny -", "deny !"):
            with self.subTest(command=command):
                code, out = self.run_cases(
                    [["deny", "no id", command, {"rule": "rm-recursive"}]]
                )
                self.assertEqual(code, 1, out)

    def test_a_case_without_rule_is_judged_on_the_decision_only(self):
        code, out = self.run_cases(
            [
                ["deny", "no fourth element", "deny anything"],
                ["deny", "options without rule", "deny anything", {"batch": True}],
                ["deny", "empty options", "deny -", {}],
                ["ask", "reason without id", "ask !"],
            ]
        )
        self.assertEqual(code, 0, out)
        self.assertIn("5/5 passed", out)

    def test_a_malformed_rule_or_key_ends_the_run(self):
        for options in (
            {"rule": 5},
            {"rule": ""},
            {"rule": None},
            {"rule": ["rm-recursive"]},
            {"rule": "rm-recursive", "unknown": 1},
            {"rules": "rm-recursive"},
        ):
            with self.subTest(options=options):
                with self.assertRaises(SystemExit) as ctx:
                    self.run_cases([["deny", "x", "deny rm-recursive", options]])
                self.assertIn("rule", str(ctx.exception.code))

    def test_a_malformed_case_ends_the_run_before_it_is_judged(self):
        with self.assertRaises(SystemExit):
            self.run_cases([["deny", "x", "deny rm-recursive", {"rule": 5}]])

    def test_against_the_real_hook_a_wrong_rule_pin_fails(self):
        real = load_runner([str(RUNNER_PATH), str(GUARD_PATH)])
        code, out = self.run_cases(
            [["deny", "wrong pin", RM + " ; git commit --amend", {"rule": "git-amend"}]],
            runner=real,
        )
        self.assertEqual(code, 1, out)
        self.assertIn("FAIL", out)

    def test_against_the_real_hook_the_right_pin_passes(self):
        real = load_runner([str(RUNNER_PATH), str(GUARD_PATH)])
        code, out = self.run_cases(
            [
                ["deny", "right pin", RM + " ; git commit --amend", {"rule": "rm-recursive"}],
                ["deny", "right pin batch", RM + " ; git commit --amend",
                 {"rule": "rm-recursive", "batch": True}],
            ],
            runner=real,
        )
        self.assertEqual(code, 0, out)

    def test_the_runner_text_names_the_rule_key(self):
        source = RUNNER_PATH.read_text(encoding="utf-8")
        docstring = normalized(ast.get_docstring(ast.parse(source)))
        self.assertIn('"rule"', docstring)
        self.assertIn("reason id", docstring)
        with self.assertRaises(SystemExit) as ctx:
            self.runner.case_options(["deny", "x", "y", {"unknown": 1}])
        self.assertIn("rule", str(ctx.exception.code))


# --- FR4: a lexer budget overrun raised out of the iteration ----------------


class TestLexerOverrunRaisedOutOfTheIteration(unittest.TestCase):
    """FR4 (Part 3.2). A chunk derived from the command whose lexing runs past
    the lexer's work bound ends the scan; what was read before it still
    decides."""

    BODY = "echo x"

    def judged(self, command, batch=False):
        hook = load_hook()
        real = hook.lex_shell

        def lex_shell(text, *args, **kwargs):
            if text.strip() == self.BODY:
                raise hook.LexBudgetExceeded()
            return real(text, *args, **kwargs)

        env = {"CLAUDE_BATCH": "1" if batch else ""}
        with mock.patch.dict(os.environ, env), mock.patch.object(
            hook, "lex_shell", lex_shell
        ):
            out = hook._judge_under(
                {"tool_name": "Bash", "tool_input": {"command": command}}, False
            )
        self.assertIsNotNone(out)
        result = out["hookSpecificOutput"]
        match = re.match(r"\[destructive-guard/([\w-]+)\]", result["permissionDecisionReason"])
        return result["permissionDecision"], match.group(1) if match else None

    def test_an_rm_deny_read_before_the_overrun_still_decides(self):
        self.assertEqual(
            self.judged(f"{RM} ; echo $({self.BODY})"), ("deny", "rm-recursive")
        )
        self.assertEqual(
            self.judged(f"{RM} ; echo $({self.BODY})", batch=True),
            ("deny", "rm-recursive"),
        )

    def test_a_held_ask_read_before_the_overrun_comes_first(self):
        self.assertEqual(
            self.judged(f"git commit --amend ; echo $({self.BODY})"),
            ("ask", "git-amend"),
        )

    def test_with_nothing_else_the_overrun_is_the_scan_budget_ask(self):
        self.assertEqual(
            self.judged(f"echo $({self.BODY})"), ("ask", "scan-budget-exceeded")
        )
        self.assertEqual(
            self.judged(f"echo $({self.BODY})", batch=True),
            ("deny", "scan-budget-exceeded"),
        )


# --- AC-8: comments and docstrings describe the held asks -----------------


class TestDescriptionsAreCurrent(unittest.TestCase):
    """AC-8 (FR7). The hook's source text is read, never imported."""

    @classmethod
    def setUpClass(cls):
        cls.source = GUARD_PATH.read_text(encoding="utf-8")
        cls.lines = cls.source.splitlines()
        tree = ast.parse(cls.source)
        cls.functions = {
            node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)
        }

    def docstring(self, name):
        self.assertIn(name, self.functions)
        return normalized(ast.get_docstring(self.functions[name]))

    def body_text(self, name):
        """The whole text of the function NAME, comments included."""
        node = self.functions[name]
        return normalized(" ".join(self.lines[node.lineno - 1 : node.end_lineno]))

    def comments(self, name):
        """The comment lines inside the function NAME, as one string."""
        node = self.functions[name]
        lines = self.lines[node.lineno - 1 : node.end_lineno]
        found = [ln.strip()[1:].strip() for ln in lines if ln.strip().startswith("#")]
        return normalized(" ".join(found))

    def comment_before_emission(self):
        """The comment block just above the line where main() picks the
        strongest rm decision."""
        node = self.functions["main"]
        lines = self.lines[node.lineno - 1 : node.end_lineno]
        index = next(
            i for i, ln in enumerate(lines) if "strongest_rm_decision(" in ln
        )
        block = []
        i = index - 1
        while i >= 0 and lines[i].strip().startswith("#"):
            block.append(lines[i].strip()[1:].strip())
            i -= 1
        return normalized(" ".join(reversed(block)))

    def test_the_comment_before_the_emission_describes_the_held_asks(self):
        text = self.comment_before_emission()
        self.assertTrue(text, "no comment block above the emission")
        self.assertIn("held ask", text)
        self.assertIn("resolution step", text)
        self.assertIn("self-modification", text)
        self.assertIn("left out", text)

    def test_the_comment_before_the_emission_is_not_the_old_one(self):
        text = self.comment_before_emission()
        self.assertNotRegex(text, r"reaching it means no other check decided first")
        self.assertNotRegex(text, r"already exited the process before this line")

    def test_the_comment_at_the_start_of_the_loop_is_not_the_old_one(self):
        text = self.comments("main")
        self.assertNotRegex(
            text, r"so this loop only collects, and the strongest decision found "
            r"is emitted once, after every segment has been examined",
        )
        self.assertNotRegex(text, r"an `ask` on an early target must not end the scan")

    def test_statements_does_not_say_a_deny_has_been_given(self):
        text = self.body_text("statements")
        self.assertNotRegex(text, r"a deny among them has been given")
        self.assertNotRegex(text, r"answer now, after the statements of this chunk")

    def test_the_substitution_route_docstring_says_an_ask_is_held(self):
        text = self.docstring("route_substitution_headed_statement")
        self.assertNotRegex(text, r"which decide\(\)s and exits directly")
        self.assertIn("held", text)

    def test_the_emission_routine_and_the_scan_budget_ask_say_how_they_are_reached(self):
        decide = self.docstring("decide")
        self.assertIn("resolution", decide)
        budget = self.docstring("ask_scan_budget_exceeded")
        self.assertNotRegex(budget, r"^Emit the scan-budget `ask` decision and stop")
        self.assertIn("early stop", budget)

    def test_the_phrases_the_numbering_tests_pin_are_kept(self):
        main = self.comments("main")
        self.assertRegex(main, r"after the whole command (?:has been|is) scanned")
        self.assertIn("original command string", main)
        self.assertIn("substitution token", main)
        self.assertIn("one ordinal", main)
        self.assertIn("`--`", self.docstring("check_rm"))
        self.assertIn("`--`", self.docstring("rm_target_designation"))
        self.assertIn("origin position", self.docstring("statements"))
        self.assertIn("template", self.docstring("strongest_rm_decision"))
        self.assertRegex(self.docstring("strongest_rm_decision"), r"plain rm-recursive")
        self.assertIn("one ordinal", self.docstring("route_substitution_headed_statement"))


if __name__ == "__main__":
    unittest.main()
