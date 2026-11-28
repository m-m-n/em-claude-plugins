"""Unit tests of the command-name evidence reader of
`em-workflow/hooks/destructive-guard.py`
(destructive-guard-resolver-only-evidence task0001).

`read_command_name_evidence(raw_body)` reads the body of a substitution that
stands where a statement's command word is. It returns a command name only
when the body is one of the resolver forms

    which [-a] [--] NAME      (`which` may be a path whose last segment is `which`)
    command -v [--] NAME
    printf NAME

and None ("unreadable") for every other body. These tests call the reader
directly with table-driven inputs. The hook has no package, so the module is
loaded from its file path with bytecode writing off for the load (no
`__pycache__` is written next to the hook). Standard library only.

Layout:

- TestAcceptedShapes: AC-1 (FR1) -- every accepted shape and its variants.
- TestUnreadableShapes: AC-2 (FR2) -- every shape that is not a resolver form.
- TestUnreadableInputs: AC-3 (FR3) -- absent / empty / whitespace-only bodies,
  a NAME that begins with `-`, a NAME whose last path segment is empty.
- TestReaderIsPureStringProcessing: FR3 -- no process, no file system access.
- TestCaseTable, TestCasesAgainstTheHook: AC-5 (FR4, FR5, NFR1) -- the case
  table holds the eleven FR5 cases, and the hook answers each of them (and the
  cases that must keep their verdict) with the tier and reason ID the table
  states. The whole table is run by
  `python3 em-workflow/hooks/tests/run-destructive-guard.py`.
- TestReaderDocstring: AC-6 (FR6) -- the docstring states the new reading flow
  and no longer carries the old "take the last word" step.
"""

import importlib.util
import json
import os
import re
import subprocess
import sys
import unittest
from unittest import mock

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK = os.path.join(ROOT, "em-workflow", "hooks", "destructive-guard.py")
RUNNER = os.path.join(ROOT, "em-workflow", "hooks", "tests", "run-destructive-guard.py")
CASES_JSON = os.path.join(
    ROOT, "em-workflow", "hooks", "tests", "destructive-guard-cases.json"
)


def _load_hook():
    """A hook module of its own, loaded with bytecode writing off so the load
    leaves no `__pycache__` next to the hook; the caller's
    `sys.dont_write_bytecode` is put back on every exit."""
    spec = importlib.util.spec_from_file_location(
        "destructive_guard_resolver_evidence_under_test", HOOK
    )
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def _load_runner():
    """The case runner as a module, loaded as `python3 run-destructive-guard.py
    HOOK` would see it, with bytecode writing off. Its verdict() runs the hook
    as a subprocess over a PreToolUse payload, the same way the case table
    does."""
    spec = importlib.util.spec_from_file_location(
        "destructive_guard_resolver_evidence_runner", RUNNER
    )
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        with mock.patch.object(sys, "argv", [RUNNER, HOOK]):
            spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


H = _load_hook()
RUNNER_MODULE = _load_runner()

# (label, RAW_BODY, expected command name)
ACCEPTED = [
    ("which NAME", "which rm", "rm"),
    ("which -a NAME", "which -a rm", "rm"),
    ("which -- NAME", "which -- rm", "rm"),
    ("which -a -- NAME", "which -a -- rm", "rm"),
    ("path-form which head", "/usr/bin/which rm", "rm"),
    ("relative path-form which head", "./bin/which rm", "rm"),
    ("path-form NAME", "which /usr/bin/rm", "rm"),
    ("command -v NAME", "command -v rm", "rm"),
    ("command -v -- NAME", "command -v -- rm", "rm"),
    ("printf NAME", "printf rm", "rm"),
    ("which and NAME separated by a tab", "which\trm", "rm"),
    ("which and NAME separated by two spaces", "which  rm", "rm"),
    ("a mixed run of spaces and tabs is one separator", "which \t \trm", "rm"),
    ("leading and trailing newline", "\nwhich rm\n", "rm"),
    ("leading and trailing spaces", "  which rm  ", "rm"),
    ("which git", "which git", "git"),
    ("command -v git", "command -v git", "git"),
    ("command -v -- path-form git", "command -v -- /usr/bin/git", "git"),
    ("printf git", "printf git", "git"),
    ("NAME that is neither rm nor git is still read", "which ls", "ls"),
    ("continuation inside NAME", "which r\\\nm", "rm"),
    ("continuation between words", "which \\\nrm", "rm"),
    ("continuation inside the head", "whi\\\nch rm", "rm"),
]

# (label, RAW_BODY)
NOT_RESOLVER_FORMS = [
    ("dirname", "dirname /opt/rm"),
    ("ls -d", "ls -d /usr/bin/rm"),
    ("readlink -f", "readlink -f ./rm"),
    ("basename with two operands", "basename /a/b git"),
    ("echo", "echo rm"),
    ("type", "type rm"),
    ("a lone name", "rm"),
    ("a lone git", "git"),
    ("two operands to which", "which ls rm"),
    ("an option which does not accept", "which -s rm"),
    ("a terminator before an option word", "which -- -a rm"),
    ("-a after the terminator", "which -- -a"),
    ("a repeated -a", "which -a -a rm"),
    ("a repeated terminator", "which -- -- rm"),
    ("command -V", "command -V rm"),
    ("command without -v", "command rm"),
    ("command -v with a second operand", "command -v rm ls"),
    ("command -v -a", "command -v -a rm"),
    ("command -v with the -a option of which", "command -v -a -- rm"),
    ("path-form command head", "/usr/bin/command -v rm"),
    ("path-form printf head", "/usr/bin/printf rm"),
    ("printf with a format and an argument", "printf %s rm"),
    ("printf with two operands", "printf rm ls"),
    ("printf with an option", "printf -v rm"),
    ("which with no operand", "which"),
    ("command -v with no operand", "command -v"),
    ("printf with no operand", "printf"),
    ("which and NAME separated by a newline", "which\nrm"),
    ("a second line after the form", "which rm\nls"),
    ("a first line before the form", "ls\nwhich rm"),
    ("a continuation that is itself escaped leaves the newline", "which a\\\\\nm"),
    ("a head that only ends with which", "xwhich rm"),
    ("a head path whose last segment is not which", "/usr/bin/which/ rm"),
    ("an upper-case head", "WHICH rm"),
    ("a non-breaking space is not a separator", "which rm"),
    ("a carriage return is not a separator", "which\rrm"),
    ("a form feed is not a separator", "which\x0crm"),
    ("a separator operator after the form", "which rm; ls"),
    ("a pipe after the form", "which rm | cat"),
    ("a quoted resolver word", "'which' rm"),
]

# (label, RAW_BODY)
UNREADABLE_NAMES = [
    ("which with an option-like NAME", "which -rm"),
    ("which -a with an option-like NAME", "which -a -rm"),
    ("which -- with an option-like NAME", "which -- -rm"),
    ("command -v -- with an option-like NAME", "command -v -- -rm"),
    ("command -v with an option-like NAME", "command -v -rm"),
    ("printf with an option-like NAME", "printf -rm"),
    ("which with a path-form option-like NAME", "which -/usr/bin/rm"),
    ("which with NAME ending in a separator", "which /usr/bin/"),
    ("command -v with NAME ending in a separator", "command -v rm/"),
    ("printf with NAME that is a bare separator", "printf /"),
]

UNREADABLE_BODIES = [
    ("an absent body", None),
    ("an empty body", ""),
    ("a space-only body", "   "),
    ("a tab-only body", "\t"),
    ("a newline-only body", "\n"),
    ("a mixed whitespace-only body", " \t\n \r\n"),
    ("a body of continuation pairs only", "\\\n\\\n"),
]


class TestAcceptedShapes(unittest.TestCase):
    """AC-1 (FR1, TM-1)."""

    def test_the_reader_returns_the_command_name_of_every_resolver_form(self):
        for label, body, want in ACCEPTED:
            with self.subTest(label=label, body=body):
                self.assertEqual(H.read_command_name_evidence(body), want)

    def test_the_named_forms_of_the_criterion_return_rm_or_git(self):
        for body in (
            "which rm",
            "which -a rm",
            "which -- rm",
            "which -a -- rm",
            "/usr/bin/which rm",
            "which /usr/bin/rm",
            "command -v rm",
            "command -v -- rm",
            "printf rm",
            "which\trm",
            "which  rm",
            "\nwhich rm\n",
        ):
            with self.subTest(body=body):
                self.assertEqual(H.read_command_name_evidence(body), "rm")
        for body in ("which git", "command -v git"):
            with self.subTest(body=body):
                self.assertEqual(H.read_command_name_evidence(body), "git")


class TestUnreadableShapes(unittest.TestCase):
    """AC-2 (FR2): a body that is not a resolver form is unreadable."""

    def test_a_body_that_is_not_a_resolver_form_is_unreadable(self):
        for label, body in NOT_RESOLVER_FORMS:
            with self.subTest(label=label, body=body):
                self.assertIsNone(H.read_command_name_evidence(body))


class TestUnreadableInputs(unittest.TestCase):
    """AC-3 (FR3): the reading rules that are kept."""

    def test_an_absent_empty_or_whitespace_only_body_is_unreadable(self):
        for label, body in UNREADABLE_BODIES:
            with self.subTest(label=label, body=body):
                self.assertIsNone(H.read_command_name_evidence(body))

    def test_a_name_that_cannot_be_a_command_name_is_unreadable(self):
        for label, body in UNREADABLE_NAMES:
            with self.subTest(label=label, body=body):
                self.assertIsNone(H.read_command_name_evidence(body))


class TestReaderIsPureStringProcessing(unittest.TestCase):
    """FR3: the reader evaluates no substitution, starts no process and reads
    nothing from the file system."""

    def test_no_process_and_no_file_system_access(self):
        bodies = [body for _l, body, _w in ACCEPTED]
        bodies += [body for _l, body in NOT_RESOLVER_FORMS]
        bodies += [body for _l, body in UNREADABLE_NAMES]
        expected = [H.read_command_name_evidence(body) for body in bodies]

        def refuse(*_a, **_k):
            raise AssertionError("the reader touched a process or the file system")

        with mock.patch.object(subprocess, "Popen", refuse), mock.patch.object(
            os, "stat", refuse
        ), mock.patch.object(os, "lstat", refuse), mock.patch.object(
            os, "listdir", refuse
        ), mock.patch.object(os, "scandir", refuse), mock.patch.object(
            os, "system", refuse
        ), mock.patch(
            "builtins.open", refuse
        ):
            got = [H.read_command_name_evidence(body) for body in bodies]
        self.assertEqual(got, expected)

    def test_a_substitution_written_in_the_body_is_not_evaluated(self):
        for body in ("which $(rm)", "which `rm`", "which $RM", "which ${RM}"):
            with self.subTest(body=body):
                name = H.read_command_name_evidence(body)
                self.assertNotEqual(name, "rm")


# (tier, reason ID or None, command). The eleven cases of SPEC FR5.
FR5_CASES = [
    ("allow", None, "$(dirname /opt/rm) -rf /home/user/valuable"),
    ("allow", None, "$(ls -d /usr/bin/rm) -rf /home/user/valuable"),
    ("allow", None, "$(readlink -f ./rm) -rf /home/user/valuable"),
    ("allow", None, "$(basename /a/b git) clean -fd"),
    ("allow", None, "$(which ls rm) -rf /home/user/valuable"),
    ("allow", None, "$(rm) -rf /home/user/valuable"),
    ("deny", "rm-recursive", "$(command -v rm) -rf /home/user/valuable"),
    ("deny", "rm-recursive", "$(which -a rm) -rf /home/user/valuable"),
    ("deny", "rm-recursive", "$(/usr/bin/which rm) -rf /home/user/valuable"),
    ("deny", "rm-recursive", "$(command -v -- rm) -rf /home/user/valuable"),
    ("deny", "git-reset-hard", "$(command -v git) reset --hard HEAD"),
]

# Cases that keep their verdict: the resolver forms the table already held
# (TS-9) and the plain route of a statement whose substitution is not evidence
# (TS-10).
KEPT_CASES = [
    ("deny", "rm-recursive", "$(which rm) -rf /home/user/valuable"),
    ("deny", "rm-recursive", "`which rm` -rf /home/user/valuable"),
    ("deny", "git-reset-hard", "$(which git) reset --hard HEAD"),
    ("deny", "git-clean", "$(which git) clean -fd"),
    ("deny", "rm-recursive", "$(printf rm) -rf /home/user/valuable"),
    ("deny", "rm-recursive", "$(true) rm -rf /home/user/valuable"),
]


class TestCaseTable(unittest.TestCase):
    """AC-5 (FR5): the case table holds the FR5 cases."""

    @classmethod
    def setUpClass(cls):
        with open(CASES_JSON, encoding="utf-8") as f:
            cls.cases = json.load(f)

    def test_the_case_table_holds_the_fr5_cases(self):
        for tier, rule, command in FR5_CASES:
            with self.subTest(command=command):
                holders = [c for c in self.cases if c[2] == command and c[0] == tier]
                self.assertTrue(holders, "no %s case for %r" % (tier, command))
                if rule is not None:
                    self.assertTrue(
                        any(len(c) > 3 and c[3].get("rule") == rule for c in holders),
                        "no case for %r fixes the reason ID %r" % (command, rule),
                    )

    def test_each_fr5_command_has_one_expected_verdict(self):
        for _tier, _rule, command in FR5_CASES:
            with self.subTest(command=command):
                self.assertEqual(
                    len({c[0] for c in self.cases if c[2] == command}), 1
                )


class TestCasesAgainstTheHook(unittest.TestCase):
    """AC-5 (FR4, FR5, NFR1): the hook gives the tier and reason ID the table
    states -- unreadable evidence allows, never asks."""

    def assert_cases(self, cases):
        for tier, rule, command in cases:
            with self.subTest(command=command):
                got, reason = RUNNER_MODULE.verdict(command)
                self.assertEqual(got, tier, reason)
                if rule is not None:
                    self.assertEqual(RUNNER_MODULE.reason_id(reason), rule, reason)

    def test_the_fr5_cases_get_the_table_verdict(self):
        self.assert_cases(FR5_CASES)

    def test_the_resolver_forms_and_the_plain_route_keep_their_verdict(self):
        self.assert_cases(KEPT_CASES)

    def test_an_unreadable_body_is_allowed_and_never_asked(self):
        for tier, _rule, command in FR5_CASES:
            if tier != "allow":
                continue
            with self.subTest(command=command):
                got, reason = RUNNER_MODULE.verdict(command)
                self.assertNotEqual(got, "ask", reason)
                self.assertEqual(got, "allow", reason)


def _normalized(text):
    return re.sub(r"\s+", " ", text or "")


class TestReaderDocstring(unittest.TestCase):
    """AC-6 (FR6): the docstring describes the resolver-only reading flow."""

    def docstring(self, name):
        return _normalized(getattr(H, name).__doc__)

    def test_the_old_last_word_step_is_gone(self):
        text = self.docstring("read_command_name_evidence")
        self.assertTrue(text)
        self.assertNotIn("LAST word", text)

    def test_the_docstring_states_the_resolver_forms_and_the_unreadable_rules(self):
        text = self.docstring("read_command_name_evidence")
        for phrase in (
            "which",
            "command -v",
            "printf",
            "-a",
            "--",
            "unreadable",
            "NAME",
        ):
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, text)
        self.assertRegex(text, r"continuation|backslash-newline")
        self.assertRegex(text, r"spaces? and tabs?")

    def test_the_routing_docstring_keeps_the_phrases_the_tests_pin(self):
        text = self.docstring("route_substitution_headed_statement")
        self.assertIn("held", text)
        self.assertIn("one ordinal", text)


if __name__ == "__main__":
    unittest.main()
