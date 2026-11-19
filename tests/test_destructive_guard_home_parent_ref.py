"""Regression tests for feature "rm-home-parent-ref-recursive-deny"
(feature-docs/rm-home-parent-ref-recursive-deny/tasks/task0001.md): in a
statement whose own rm has a qualifying operand, the hook gives the rm `ask`
(reason ID `rm-unresolvable`) in place of that statement's self-modification
`ask`. A qualifying operand is a deletion target whose raw form matches the
protected self-config pattern, which is not protected once `..` is folded, and
which `check_rm()` judges `rm-unresolvable` because it holds an expansion.
`$HOME` stays an unresolved expansion: nothing here expands it.

The scenarios are cases in
em-workflow/hooks/tests/destructive-guard-cases.json (labels beginning
`rm-home-parent-ref-recursive-deny TS-`) and run through
run-destructive-guard.py. This module checks what the table cannot:

- the case table: the 16 cases are one unbroken run after every earlier case,
  and the earlier cases are unchanged (pinned by count and digest);
- each case of the table judged the way the runner judges it;
- TS-18 (a held ask of an earlier statement keeps its rank) and TS-1's reason
  text (the rm reason, with no self-modification text);
- the helper that decides whether a qualifying operand exists, called with
  records and protected sets taken from the hook's own functions;
- the structure of main(): the helper is called on both rm paths and nowhere
  else, and the helper has no side effects and no file-system access;
- two-run determinism of the hook's output;
- the FR4 comments of main() and the bullet of `.claude/rules/hook-tests.md`,
  checked by key terms rather than exact sentences.

The hook runs as a subprocess with PreToolUse JSON on standard input, with
HOME and PATH supplied by the test and CLAUDE_BATCH absent unless a test sets
it. Only the standard library is used.
"""

import ast
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOKS_DIR = REPO_ROOT / "em-workflow" / "hooks"
GUARD_PATH = HOOKS_DIR / "destructive-guard.py"
TESTS_DIR = HOOKS_DIR / "tests"
RUNNER_PATH = TESTS_DIR / "run-destructive-guard.py"
CASES_PATH = TESTS_DIR / "destructive-guard-cases.json"
RULE_PATH = REPO_ROOT / ".claude" / "rules" / "hook-tests.md"

FEATURE = "rm-home-parent-ref-recursive-deny"
LABEL_PREFIX = FEATURE + " TS-"

# The cases of the table that existed before this feature: their number and
# the digest of their JSON form. Computed at the task base. Every one of them
# is still there, unchanged and in its place, and the feature's cases come
# after them.
PRE_EXISTING_CASE_COUNT = 1374
PRE_EXISTING_CASES_DIGEST = (
    "6ebe4a950daf897c387f76b0be235123d9768df65f5b6f78af516fab1f49ac1b"
)

# Test-controlled, never the real environment's. The empty PATH leaves no
# `gio` to find, so the reason of an rm is the same wherever the suite runs.
FIXED_HOME = "/home/home-parent-ref-test-home"
NO_GIO_PATH = ""

PLAIN = '"$HOME/.claude/skills/../../valuable"'
PROTECTED = "$HOME/.claude/skills/foo"

# (scenario, decision, command, rule, batch): the 16 cases of the feature, in
# the order the table holds them. TS-9 has two cases.
SCENARIOS = [
    (1, "ask", f"rm -rf {PLAIN}", "rm-unresolvable", False),
    (2, "ask", "rm -rf $HOME/.claude/skills/../../valuable", "rm-unresolvable", False),
    (3, "ask", f"rm -rf {PROTECTED} {PLAIN}", "rm-unresolvable", False),
    (4, "deny", f"rm -rf {PLAIN}", "rm-unresolvable", True),
    (5, "deny", f"rm -rf {PROTECTED} {PLAIN}", "rm-unresolvable", True),
    (6, "ask", f"$(printf rm) -rf {PROTECTED} {PLAIN}", "rm-unresolvable", False),
    (7, "ask", f"rm -rf {PLAIN} > ~/.claude/settings.json", "rm-unresolvable", False),
    (8, "ask", 'rm -rf "${HOME}/.claude/skills/../../valuable"', "rm-unresolvable", False),
    (9, "ask", f"HOME=/tmp/x; rm -rf {PLAIN}", "rm-unresolvable", False),
    (9, "deny", f"HOME=/tmp/x; rm -rf {PLAIN}", "rm-unresolvable", True),
    (10, "ask", f"rm {PLAIN}", "self-modification", False),
    (11, "ask", 'rm -rf "$HOME/.claude/skills/../hooks/x"', "self-modification", False),
    (12, "ask", 'rm -rf "$HOME/.claude/skills/../../../../tmp/x"', "rm-unresolvable", False),
    (
        13,
        "deny",
        f"rm -rf {PROTECTED} /home/user/valuable {PLAIN}",
        "rm-recursive",
        False,
    ),
    (14, "ask", "rm -rf tmp/$X > ~/.claude/settings.json", "self-modification", False),
    (15, "ask", "rm -rf ~/.claude/skills/../../$X", "rm-unresolvable", False),
]

# The commands of scenarios TS-1 to TS-15 with the batch flag they run under.
FORMS = [(command, batch) for _n, _d, command, _r, batch in SCENARIOS]

# TS-18: a held ask of an earlier statement keeps its rank.
TS_18 = [
    (
        f"git commit --amend ; rm -rf {PLAIN}",
        "ask",
        "git-amend",
    ),
    (
        f"echo x > ~/.claude/settings.json ; rm -rf {PLAIN}",
        "ask",
        "self-modification",
    ),
]

REASON_ID = re.compile(r"^\[destructive-guard/([\w-]+)\]")


def run_guard(command, batch=False, home=FIXED_HOME, path=NO_GIO_PATH):
    """The hook as a subprocess, fed one PreToolUse payload. The environment
    is built from scratch, so CLAUDE_BATCH is absent unless BATCH asks."""
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
    match = REASON_ID.match(reason)
    return out["permissionDecision"], match.group(1) if match else None, reason


def load_runner(argv):
    """The runner as a module, loaded as `python3 run-destructive-guard.py
    *ARGV[1:]` would see it, without leaving a bytecode cache behind."""
    spec = importlib.util.spec_from_file_location(
        "run_destructive_guard_home_parent_ref_under_test", RUNNER_PATH
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
        "destructive_guard_home_parent_ref_under_test", GUARD_PATH
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


def scenario_number(case):
    return int(re.match(rf"^{FEATURE} TS-(\d+)", case[1]).group(1))


def feature_positions(cases):
    return [i for i, case in enumerate(cases) if case[1].startswith(LABEL_PREFIX)]


# --- AC-5: the case table -----------------------------------------------------


class TestCaseTable(unittest.TestCase):
    """AC-5 (FR5, NFR1, NFR3, TM-3, TS-16). The feature's 16 cases are one
    unbroken run after every earlier case, and every earlier case is unchanged
    and in its place. What follows the run is not constrained: a later feature
    appends its own cases there."""

    @classmethod
    def setUpClass(cls):
        with open(CASES_PATH, encoding="utf-8") as f:
            cls.cases = json.load(f)
        cls.positions = feature_positions(cls.cases)
        cls.new = [cls.cases[i] for i in cls.positions]

    def test_there_are_16_cases(self):
        self.assertEqual(len(self.new), len(SCENARIOS))
        self.assertEqual(len(self.new), 16)

    def test_the_cases_form_one_unbroken_run_right_after_the_earlier_cases(self):
        self.assertEqual(
            self.positions,
            list(
                range(
                    PRE_EXISTING_CASE_COUNT, PRE_EXISTING_CASE_COUNT + len(SCENARIOS)
                )
            ),
        )

    def test_every_earlier_case_is_present_unchanged_and_in_its_place(self):
        existing = self.cases[:PRE_EXISTING_CASE_COUNT]
        self.assertEqual(len(existing), PRE_EXISTING_CASE_COUNT)
        digest = hashlib.sha256(
            json.dumps(existing, ensure_ascii=False).encode("utf-8")
        )
        self.assertEqual(digest.hexdigest(), PRE_EXISTING_CASES_DIGEST)

    def test_no_earlier_case_carries_the_feature_label(self):
        for case in self.cases[:PRE_EXISTING_CASE_COUNT]:
            self.assertFalse(case[1].startswith(FEATURE), case[1])

    def test_every_case_has_four_elements_and_a_rule(self):
        for case in self.new:
            with self.subTest(label=case[1]):
                self.assertEqual(len(case), 4)
                self.assertIsInstance(case[3].get("rule"), str)
                self.assertTrue(case[3]["rule"])
                self.assertLessEqual(set(case[3]), {"rule", "batch"})

    def test_every_label_starts_with_the_prefix_and_a_japanese_description(self):
        for case in self.new:
            with self.subTest(label=case[1]):
                self.assertRegex(case[1], rf"^{FEATURE} TS-\d+: ")
                self.assertTrue(
                    re.search(r"[぀-ヿ一-鿿]", case[1]),
                    "the label is not in Japanese",
                )

    def test_no_case_names_a_machine_specific_path(self):
        for case in self.new:
            with self.subTest(label=case[1]):
                self.assertNotRegex(
                    case[1] + " " + case[2], r"/(?:Users|root)/|/home/(?!user/)"
                )

    def test_the_batch_key_is_set_on_ts_4_ts_5_and_the_batch_case_of_ts_9_only(self):
        batch = sorted(
            (scenario_number(case), case[0])
            for case in self.new
            if case[3].get("batch")
        )
        self.assertEqual(batch, [(4, "deny"), (5, "deny"), (9, "deny")])
        for case in self.new:
            if "batch" in case[3]:
                self.assertIs(case[3]["batch"], True)

    def test_the_cases_are_exactly_the_scenarios_in_order(self):
        have = [
            (
                scenario_number(case),
                case[0],
                case[2],
                case[3]["rule"],
                bool(case[3].get("batch")),
            )
            for case in self.new
        ]
        self.assertEqual(have, SCENARIOS)


class TestCasesPassAgainstTheHook(unittest.TestCase):
    """AC-1 to AC-5. Each case of the feature is judged the way
    run-destructive-guard.py judges it -- the hook as a subprocess,
    CLAUDE_BATCH cleared unless the case sets it, the decision and the pinned
    reason id both compared -- with one subtest per case."""

    @classmethod
    def setUpClass(cls):
        cls.runner = load_runner([str(RUNNER_PATH), str(GUARD_PATH)])
        with open(CASES_PATH, encoding="utf-8") as f:
            cases = json.load(f)
        cls.new = [case for case in cases if case[1].startswith(LABEL_PREFIX)]

    def test_every_case_of_the_feature_passes(self):
        self.assertEqual(len(self.new), 16)
        for case in self.new:
            want, label, command = case[:3]
            cwd, batch, rule = self.runner.case_options(case)
            with self.subTest(label=label):
                got, reason = self.runner.verdict(command, batch=batch, cwd=cwd)
                self.assertEqual(got, want, reason[:200])
                self.assertEqual(self.runner.reason_id(reason), rule, reason[:200])


class TestVerdictsUnderAFixedHome(unittest.TestCase):
    """AC-1 to AC-4 (FR1 to FR3, NFR1, NFR2). The scenarios once more, with
    HOME and PATH supplied by the test so that the verdict is the same
    wherever the suite runs."""

    def test_the_scenarios_give_their_decision_and_reason_id(self):
        for number, want, command, rule, batch in SCENARIOS:
            with self.subTest(scenario=number, batch=batch):
                got, got_rule, reason = decision(command, batch=batch)
                self.assertEqual((got, got_rule), (want, rule), reason[:200])


class TestForwardRankOfEarlierStatements(unittest.TestCase):
    """AC-4 (FR1, TS-18). The asks held by another statement keep their rank:
    a statement that comes first and holds an ask is not outranked by the rm
    ask of a later statement."""

    def test_an_earlier_git_amend_ask_stays_first(self):
        command, want, rule = TS_18[0]
        got, got_rule, reason = decision(command)
        self.assertEqual((got, got_rule), (want, rule), reason[:200])

    def test_an_earlier_self_modification_ask_of_another_statement_stays_first(self):
        command, want, rule = TS_18[1]
        got, got_rule, reason = decision(command)
        self.assertEqual((got, got_rule), (want, rule), reason[:200])

    def test_a_later_ask_of_another_statement_does_not_outrank_the_rm_ask(self):
        # The statement of the qualifying operand holds the first ask, so its
        # rm ask is the verdict; the asks after it are behind it, as before.
        for command in (
            f"rm -rf {PLAIN} ; git commit --amend",
            f"rm -rf {PLAIN} ; echo x > ~/.claude/settings.json",
        ):
            with self.subTest(command=command):
                got, got_rule, reason = decision(command)
                self.assertEqual((got, got_rule), ("ask", "rm-unresolvable"), reason[:200])

    def test_the_rm_deny_still_wins_over_an_earlier_held_ask(self):
        got, got_rule, _ = decision(
            f"git commit --amend ; rm -rf {PROTECTED} /home/user/valuable"
        )
        self.assertEqual((got, got_rule), ("deny", "rm-recursive"))


class TestSubstitutionHeadedPath(unittest.TestCase):
    """AC-3 (FR2, TM-1). On the substitution-headed path the statement's own
    self-modification `ask` is only held when a redirect target names a
    protected file (the plain TS-6 form holds none and is the rm ask already),
    so the redirect is what makes the check run here. The qualifying operand
    is found with the operand numbers of that path's own basis: the remainder
    after the skipped substitution."""

    REDIRECT = " > ~/.claude/settings.json"
    HEAD = "$(printf rm)"

    def check(self, command, want_decision, want_rule, batch=False):
        with self.subTest(command=command, batch=batch):
            got, rule, reason = decision(command, batch=batch)
            self.assertEqual((got, rule), (want_decision, want_rule), reason[:200])

    def test_a_qualifying_operand_beside_a_protected_one_gives_the_rm_ask(self):
        self.check(
            f"{self.HEAD} -rf {PROTECTED} {PLAIN}{self.REDIRECT}",
            "ask",
            "rm-unresolvable",
        )

    def test_a_qualifying_operand_alone_gives_the_rm_ask(self):
        self.check(
            f"{self.HEAD} -rf {PLAIN}{self.REDIRECT}", "ask", "rm-unresolvable"
        )

    def test_with_claude_batch_the_rm_ask_is_demoted_after_the_choice(self):
        self.check(
            f"{self.HEAD} -rf {PROTECTED} {PLAIN}{self.REDIRECT}",
            "deny",
            "rm-unresolvable",
            batch=True,
        )

    def test_a_protected_operand_alone_keeps_the_self_modification_ask(self):
        self.check(
            f"{self.HEAD} -rf {PROTECTED}{self.REDIRECT}", "ask", "self-modification"
        )

    def test_an_operand_that_matches_no_protected_path_keeps_the_self_modification_ask(
        self,
    ):
        self.check(
            f"{self.HEAD} -rf tmp/$X{self.REDIRECT}", "ask", "self-modification"
        )

    def test_without_a_recursive_flag_the_self_modification_ask_stands(self):
        self.check(f"{self.HEAD} {PLAIN}{self.REDIRECT}", "ask", "self-modification")

    def test_an_rm_deny_of_another_operand_still_wins(self):
        self.check(
            f"{self.HEAD} -rf {PROTECTED} /home/user/valuable {PLAIN}{self.REDIRECT}",
            "deny",
            "rm-recursive",
        )

    def test_the_plain_path_gives_the_same_decisions(self):
        for command, want in (
            (f"rm -rf {PROTECTED} {PLAIN}{self.REDIRECT}", ("ask", "rm-unresolvable")),
            (f"rm -rf {PROTECTED}{self.REDIRECT}", ("ask", "self-modification")),
        ):
            with self.subTest(command=command):
                got, rule, reason = decision(command)
                self.assertEqual((got, rule), want, reason[:200])


class TestReasonText(unittest.TestCase):
    """AC-1 (FR1, A2). The reason of the rm ask is the reason the hook gives
    for an rm whose operand matches no protected path and holds an expansion:
    it holds no text of the self-modification ask."""

    def test_the_reason_equals_the_reason_of_an_unprotected_expansion_operand(self):
        got = decision(f"rm -rf {PLAIN}")
        other = decision('rm -rf "$Y/valuable"')
        self.assertEqual(got[:2], ("ask", "rm-unresolvable"))
        self.assertEqual(other[:2], ("ask", "rm-unresolvable"))
        self.assertEqual(got[2], other[2])

    def test_the_reason_carries_no_self_modification_text(self):
        reason = decision(f"rm -rf {PROTECTED} {PLAIN}")[2]
        self.assertNotIn("自己設定", reason)
        self.assertNotIn("self-modification", reason)

    def test_the_demotion_sentence_is_added_only_under_claude_batch(self):
        attended = decision(f"rm -rf {PLAIN}")[2]
        unattended = decision(f"rm -rf {PLAIN}", batch=True)[2]
        self.assertNotIn("降格", attended)
        self.assertIn("降格", unattended)
        self.assertTrue(unattended.startswith(attended))


# --- the helper that decides whether a qualifying operand exists -------------


class TestQualifyingOperandHelper(unittest.TestCase):
    """AC-1, AC-3 (FR1, FR2). The helper is given an operand basis, the rm
    records for that basis before the protected-operand filtering and the
    protected-operand set. The records and the set come from the hook's own
    check_rm() and rm_protected_operand_numbers(), so the numbers they carry
    are the numbers the helper reads."""

    NAME = "has_qualifying_rm_operand"

    @classmethod
    def setUpClass(cls):
        cls.hook = load_hook()

    def setUp(self):
        patcher = mock.patch.dict("os.environ", {"HOME": FIXED_HOME})
        patcher.start()
        self.addCleanup(patcher.stop)

    def qualifies(self, *args):
        records = self.hook.check_rm(list(args), 0)
        protected = self.hook.rm_protected_operand_numbers(list(args))
        return getattr(self.hook, self.NAME)(list(args), records, protected)

    def test_a_parent_ref_operand_out_of_the_protected_area_qualifies(self):
        self.assertTrue(self.qualifies("-rf", "$HOME/.claude/skills/../../valuable"))

    def test_the_tilde_spelling_qualifies(self):
        self.assertTrue(self.qualifies("-rf", "~/.claude/skills/../../$X"))

    def test_a_protected_operand_alone_does_not_qualify(self):
        self.assertFalse(self.qualifies("-rf", "$HOME/.claude/skills/foo"))

    def test_a_protected_operand_beside_a_qualifying_one_does_not_hide_it(self):
        self.assertTrue(
            self.qualifies(
                "-rf", "$HOME/.claude/skills/foo", "$HOME/.claude/skills/../../valuable"
            )
        )

    def test_an_operand_that_stays_inside_the_area_does_not_qualify(self):
        self.assertFalse(self.qualifies("-rf", "$HOME/.claude/skills/../hooks/x"))

    def test_without_a_recursive_flag_there_is_no_record_and_no_qualifying_operand(self):
        self.assertFalse(self.qualifies("$HOME/.claude/skills/../../valuable"))

    def test_an_operand_whose_raw_form_matches_nothing_does_not_qualify(self):
        self.assertFalse(self.qualifies("-rf", "tmp/$X"))
        self.assertFalse(self.qualifies("-rf", "${HOME}/.claude/skills/../../valuable"))

    def test_an_operand_judged_by_a_deny_record_does_not_qualify(self):
        # Its raw form matches the pattern, but nothing in it is an expansion:
        # check_rm() gives rm-recursive, not rm-unresolvable.
        self.assertFalse(
            self.qualifies("-rf", "/home/user/.claude/skills/../../valuable")
        )

    def test_the_numbers_follow_the_double_dash_rule(self):
        self.assertTrue(
            self.qualifies("-rf", "--", "$HOME/.claude/skills/../../valuable")
        )

    def test_a_record_of_another_operand_number_does_not_qualify(self):
        hook = self.hook
        args = ["-rf", "$HOME/.claude/skills/../../valuable"]
        elsewhere = [
            hook._RmRecord(
                "ask", "rm-unresolvable", 0, 2, hook.RM_FORM_EXPANSION
            )
        ]
        protected = hook.rm_protected_operand_numbers(args)
        self.assertFalse(getattr(hook, self.NAME)(args, elsewhere, protected))

    def test_a_record_with_another_reason_id_does_not_qualify(self):
        hook = self.hook
        args = ["-rf", "$HOME/.claude/skills/../../valuable"]
        other = [
            hook._RmRecord(
                "deny", "rm-recursive", 0, 1, hook.RM_FORM_OUTSIDE_SCRATCH
            )
        ]
        protected = hook.rm_protected_operand_numbers(args)
        self.assertFalse(getattr(hook, self.NAME)(args, other, protected))

    def test_the_same_inputs_always_give_the_same_output_and_are_not_changed(self):
        hook = self.hook
        args = ["-rf", "$HOME/.claude/skills/foo", "$HOME/.claude/skills/../../valuable"]
        records = hook.check_rm(args, 0)
        protected = hook.rm_protected_operand_numbers(args)
        args_before, protected_before = list(args), set(protected)
        numbers_before = [(r.rule, r.number) for r in records]
        first = getattr(hook, self.NAME)(args, records, protected)
        second = getattr(hook, self.NAME)(args, records, protected)
        self.assertEqual(first, second)
        self.assertEqual(args, args_before)
        self.assertEqual(protected, protected_before)
        self.assertEqual([(r.rule, r.number) for r in records], numbers_before)


# --- the structure of main() and the helper ---------------------------------


class TestStructure(unittest.TestCase):
    """AC-3, AC-7 (FR2, FR3, NFR2). The hook's source is parsed, never run."""

    NAME = "has_qualifying_rm_operand"

    @classmethod
    def setUpClass(cls):
        cls.source = GUARD_PATH.read_text(encoding="utf-8")
        tree = ast.parse(cls.source)
        cls.functions = {
            node.name: node for node in tree.body if isinstance(node, ast.FunctionDef)
        }

    def calls_of(self, name):
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

    def test_the_helper_exists(self):
        self.assertIn(self.NAME, self.functions)

    def test_the_helper_is_called_once_per_rm_path_and_only_from_main(self):
        calls = self.calls_of(self.NAME)
        self.assertEqual(len(calls), 2)
        for holder, call in calls:
            with self.subTest(line=call.lineno):
                self.assertEqual(holder, "main")
                self.assertEqual(len(call.args), 3)
                self.assertEqual(call.keywords, [])

    def test_the_protected_operand_function_is_still_called_twice_from_main(self):
        calls = self.calls_of("rm_protected_operand_numbers")
        self.assertEqual([holder for holder, _ in calls], ["main", "main"])

    def test_the_helper_reads_no_filesystem_and_expands_nothing(self):
        node = self.functions[self.NAME]
        names = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
        attributes = {n.attr for n in ast.walk(node) if isinstance(n, ast.Attribute)}
        self.assertFalse(
            names & {"os", "open", "Path", "subprocess", "normalize_candidate"}, names
        )
        self.assertFalse(
            attributes
            & {"expanduser", "expandvars", "realpath", "stat", "exists", "environ", "getenv"},
            attributes,
        )

    def test_the_helper_reuses_the_numbering_helper_and_the_pattern(self):
        node = self.functions[self.NAME]
        names = {n.id for n in ast.walk(node) if isinstance(n, ast.Name)}
        self.assertIn("_number_rm_operands", names)
        self.assertIn("SELF_CONFIG", names)

    def test_the_self_config_pattern_is_not_duplicated(self):
        self.assertEqual(len(re.findall(r"^SELF_CONFIG = ", self.source, re.M)), 1)


# --- AC-7: determinism ------------------------------------------------------


class TestDeterminism(unittest.TestCase):
    """AC-7 (NFR2, TS-19). The hook's output for each command of TS-1 to
    TS-15 is byte-identical across two runs."""

    def test_the_output_is_byte_identical_across_two_runs(self):
        for command, batch in FORMS:
            with self.subTest(command=command, batch=batch):
                first = run_guard(command, batch=batch)
                second = run_guard(command, batch=batch)
                self.assertEqual(first.returncode, 0, first.stderr)
                self.assertTrue(first.stdout.strip())
                self.assertEqual(first.stdout, second.stdout)
                self.assertEqual(first.stderr, second.stderr)


# --- AC-6: the comments of main() and the rule document ----------------------


class TestComments(unittest.TestCase):
    """AC-6 (FR4, TS-17). The selection-order comment and the exclusion
    comment of main() state the exception. The checks are on key terms."""

    @classmethod
    def setUpClass(cls):
        source = GUARD_PATH.read_text(encoding="utf-8")
        cls.lines = source.splitlines()
        tree = ast.parse(source)
        main = next(
            n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "main"
        )
        cls.main_lines = cls.lines[main.lineno - 1 : main.end_lineno]

    def comment_before(self, anchor_text):
        index = next(i for i, ln in enumerate(self.main_lines) if anchor_text in ln)
        block = []
        i = index - 1
        while i >= 0 and self.main_lines[i].strip().startswith("#"):
            block.append(self.main_lines[i].strip()[1:].strip())
            i -= 1
        return normalized(" ".join(reversed(block)))

    def test_the_selection_order_comment_states_the_exception_at_step_2(self):
        text = self.comment_before("strongest_rm_decision(")
        self.assertIn("qualifying operand", text)
        self.assertIn("rm-unresolvable", text)
        self.assertRegex(text, r"yields? to the rm `ask`")
        self.assertIn("self-modification", text)
        # The step it belongs to is still the second one of the list.
        self.assertRegex(text, r"2\. the first held ask")

    def test_the_exclusion_comment_says_a_qualifying_operand_is_not_left_out(self):
        text = self.comment_before("self_modification_asked = any(")
        self.assertIn("qualifying operand", text)
        self.assertRegex(text, r"yields? to the rm `ask`")
        self.assertRegex(text, r"not left out")


class TestRuleDocument(unittest.TestCase):
    """AC-6 (FR4, TS-17). `.claude/rules/hook-tests.md` has one more bullet in
    the precedence list, after the bullet about the same statement's deletion
    targets and before the CLAUDE_BATCH demotion bullet. The document is read
    as text and the bullets are checked by key terms."""

    HEADING = "そのようなケースが固定する優先順位は次のとおり。"

    @classmethod
    def setUpClass(cls):
        text = RULE_PATH.read_text(encoding="utf-8")
        start = text.index(cls.HEADING)
        end = text.index("\n- ", start)
        cls.block = text[start:end]
        # The nested bullets: each is its own line plus its continuation lines.
        bullets = []
        for line in cls.block.splitlines()[1:]:
            if re.match(r"^\s+- ", line):
                bullets.append([line.strip()[2:]])
            elif bullets:
                bullets[-1].append(line.strip())
        cls.bullets = ["".join(lines) for lines in bullets]

    def new_bullets(self):
        return [
            i
            for i, bullet in enumerate(self.bullets)
            if "rm-unresolvable" in bullet
        ]

    def test_there_is_exactly_one_bullet_about_rm_unresolvable(self):
        self.assertEqual(len(self.new_bullets()), 1, self.bullets)

    def test_the_bullet_states_the_exception(self):
        bullet = self.bullets[self.new_bullets()[0]]
        compact = re.sub(r"\s+", "", bullet)
        for term in (
            "同じrmの削除対象",
            "生の形が保護された自己設定パスに一致する",
            "`..`を畳むと保護範囲の外に出て",
            "rm-unresolvable",
            "その文のself-modificationの`ask`",
            "rmの`ask`が先に選ばれる",
        ):
            with self.subTest(term=term):
                self.assertIn(term, compact)
        self.assertTrue(bullet.endswith("。"), bullet)

    def test_the_bullet_does_not_say_a_protected_target_replaces_the_verdict(self):
        bullet = self.bullets[self.new_bullets()[0]]
        compact = re.sub(r"\s+", "", bullet)
        self.assertFalse("自己設定パス" in compact and "代わりに" in compact)

    def test_the_bullet_stands_after_the_same_rm_bullet_and_before_the_demotion(self):
        index = self.new_bullets()[0]
        before = [i for i, b in enumerate(self.bullets) if "他の削除対象の`deny`" in re.sub(r"\s+", "", b)]
        after = [i for i, b in enumerate(self.bullets) if "`CLAUDE_BATCH`" in b]
        self.assertEqual(len(before), 1)
        self.assertEqual(len(after), 1)
        self.assertEqual(index, before[0] + 1)
        self.assertEqual(after[0], index + 1)

    def test_the_existing_bullets_are_still_there(self):
        compact = re.sub(r"\s+", "", "".join(self.bullets))
        for term in (
            "再帰削除の`deny`は、他のcheckの`ask`に、順序に関係なく勝つ",
            "同じ文のrmの削除対象のうち、保護された自己設定パスだけが候補から外れ",
            "その分はself-modificationの`ask`が残る",
            "同じrmの他の削除対象の`deny`は、その`ask`に勝つ",
            "`CLAUDE_BATCH`による降格は、優先順位を決めた後に行う",
        ):
            with self.subTest(term=term):
                self.assertIn(term, compact)


if __name__ == "__main__":
    unittest.main()
