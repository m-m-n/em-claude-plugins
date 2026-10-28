"""Contract tests for the top-level operator exclusion of the
`cd "<P>" && <approved command>` allowance in `em-workflow/hooks/bash_guard.py`
(feature cd-prefix-toplevel-operators, task0001).

Every hook case drives the hook as a subprocess with PreToolUse JSON on
standard input and reads the decision from standard output. The expected
decision is one of three:

- `allow`  -- a JSON `permissionDecision: allow` on standard output.
- `deny`   -- a JSON `permissionDecision: deny` on standard output.
- `silent` -- no output at all (no decision; the normal permission flow
  applies).

Isolation: the approval store is a temporary file selected through
`EM_WORKFLOW_APPROVALS`, `CLAUDE_PROJECT_DIR` is removed from the hook's
environment, and every repository is a temporary git repository. The real
approval store and the real repository's workflow.yaml are never read. Paths
used for comparison are realpaths. The fixture is built here; it is not
imported from `tests/test_bash_guard_cd_prefix.py`.

Covers task0001 Acceptance Criteria
(feature-docs/cd-prefix-toplevel-operators/tasks/task0001.md):

- AC-1: no decision for an approved string with a top-level operator.
- AC-2: allow, with the cd prefix reason, for the recognized tokens, quoted
  and escaped characters.
- AC-3: no decision for each safe-side exclusion (E5 to E10).
- AC-4: the exclusion only narrows the allow; the unchanged decision table
  judges an excluded form.
- AC-5: the refusal patterns are applied first, with or without an operator.
- AC-6: the module docstring states the conditions.
- AC-7: standard-library-only imports in this module and in the hook.

Standard library only.
"""

import ast
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
GUARD_PATH = REPO_ROOT / "em-workflow" / "hooks" / "bash_guard.py"

ALLOW = "allow"
DENY = "deny"
SILENT = "silent"

PLAIN_COMMAND = "make test"
DECLARED_COMMAND = "make lint"
SUDO_AMPERSAND = "sudo make test & make lint"
SUDO_SEMICOLON = "sudo make test ; make lint"

# Marker words of the three reasons the hook gives (the strings are the
# hook's, compared here by their stable fragments).
CD_PREFIX_MARKER = "cd 前置形"
UNAPPROVED_MARKER = "未承認"
REFUSAL_MARKER = "禁止パターン"

# AC-1: approved strings that must lose the cd prefix allow.
# (label, remainder). A and B are `echo a` and `echo b`.
OPERATOR_CASES = (
    ("lone & between two commands", "echo a & echo b"),
    ("semicolon between two commands", "echo a ; echo b"),
    ("|| between two commands", "echo a || echo b"),
    ("trailing lone &", "echo a &"),
    ("trailing semicolon", "echo a;"),
    ("&& followed by a lone &", "echo a &&& echo b"),
    (
        "single quote closes at the quote after the backslash",
        "echo 'a\\';b",
    ),
    (
        "escaped backslash then closing double quote leaves ; at top level",
        'echo "a\\\\";b',
    ),
    ("escaped backslash leaves ; at top level", "echo \\\\;b"),
    ("lone & after an &>> token", "echo a &>> log & echo b"),
    ("|& does not hide a following ||", "echo a |& b || c"),
)

# Strings the record CLI cannot store (a line break inside) are written to
# the store file directly.
LINE_BREAK_CASES = (
    ("line feed inside the string", "echo a\necho b"),
    ("carriage return inside the string", "echo a\recho b"),
)

# AC-2: approved strings that keep the cd prefix allow.
ALLOW_REMAINDERS = (
    ("redirection 2>&1", "make test 2>&1"),
    ("|& token", "a |& b"),
    ("plain pipe", "a | b"),
    ("&> token", "a &> log"),
    ("&>> token", "a &>> log"),
    ("<& token", "a <&0"),
    (">& token", "a >&2"),
    ("&& token", "a && b"),
    ("; inside double quotes", 'echo "a;b"'),
    ("& inside single quotes", "echo 'a&b'"),
    ("escaped semicolon", "echo a\\;b"),
    ("escaped double quote inside double quotes", 'echo "a\\";b"'),
    ("single quote closed by the quote after the backslash", "echo 'a\\'"),
    ("plain variable reference in double quotes", 'echo "$HOME"'),
    ("escaped parentheses", "echo \\(x\\)"),
    ("backslash before ; inside double quotes is ordinary", 'echo "a\\;b"'),
    ("| inside double quotes", 'echo "a|b"'),
)

# AC-3: approved strings excluded on the safe side.
SAFE_SIDE_CASES = (
    ("E5 unclosed single quote", "echo 'abc"),
    ("E5 unclosed double quote", 'echo "abc'),
    ("E6 trailing backslash", "echo abc\\"),
    ("E7 dollar single quote", "echo $'x'"),
    ("E7 dollar double quote", 'echo $"x"'),
    ("E8 hash at the start", "#echo a"),
    ("E8 hash in the middle", "echo a#b"),
    ("E8 hash at the end", "echo a #"),
    ("E8 hash inside single quotes", "echo '#'"),
    ("E8 hash inside double quotes", 'echo "#"'),
    ("E9 opening parenthesis", "echo a (b"),
    ("E9 closing parenthesis", "echo a )b"),
    ("E9 opening brace", "echo {a"),
    ("E9 closing brace", "echo a}"),
    ("E10 command substitution", "echo $(true)"),
    ("E10 parameter substitution", "echo ${HOME}"),
    ("E10 backtick pair", "echo `true`"),
    ("E10 command substitution inside double quotes", 'echo "$(true)"'),
    ("E10 parameter substitution inside double quotes", 'echo "${HOME}"'),
    ("E10 backtick inside double quotes", 'echo "`true`"'),
    ("E10 command substitution inside single quotes", "echo '$(true)'"),
)


def _clean_env():
    return {
        key: value
        for key, value in os.environ.items()
        if key != "CLAUDE_PROJECT_DIR" and not key.startswith("GIT_")
    }


def _git(cwd, *args):
    env = _clean_env()
    env.update(
        GIT_AUTHOR_NAME="test",
        GIT_AUTHOR_EMAIL="test@example.com",
        GIT_COMMITTER_NAME="test",
        GIT_COMMITTER_EMAIL="test@example.com",
        GIT_CONFIG_NOSYSTEM="1",
        GIT_CONFIG_GLOBAL=os.devnull,
    )
    proc = subprocess.run(
        ["git", "-c", "commit.gpgsign=false", "-C", str(cwd), *args],
        capture_output=True,
        text=True,
        env=env,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {proc.stderr}")
    return proc.stdout.strip()


def _make_repo(path):
    path.mkdir(parents=True)
    _git(path, "init", "-q")
    (path / "README").write_text("fixture\n", encoding="utf-8")
    _git(path, "add", "README")
    _git(path, "commit", "-q", "-m", "init")


class Fixture:
    """Temporary repository, git worktree, approval stores and workflow.yaml."""

    def __init__(self):
        self.root = Path(os.path.realpath(tempfile.mkdtemp(prefix="bash-guard-ops-")))
        self.repo = self.root / "repo1"
        _make_repo(self.repo)
        self.region = self.repo / ".claude" / "worktrees" / "em-workflow"
        # Three distinct directories, so a declared cd form and an approved
        # cd form never collide with the cd forms the other cases use.
        self.inside = self.region / "task0001"
        self.declared_dir = self.region / "task0002"
        self.whole_dir = self.region / "task0003"
        for directory in (self.inside, self.declared_dir, self.whole_dir):
            directory.mkdir(parents=True)
        # A directory whose name holds operators: only the remainder is
        # scanned, never the path.
        self.operator_dir = self.region / "p;q & r || s"
        self.operator_dir.mkdir()

        # A real git worktree below the area, used as the hook's cwd.
        self.worktree = self.region / "wtree"
        _git(self.repo, "worktree", "add", "-q", str(self.worktree), "-b", "wtree")

        self.key = _git(
            self.repo, "rev-parse", "--path-format=absolute", "--git-common-dir"
        )

        # Declared (workflow.yaml) strings; no `#` in any value.
        self.declared_forms = tuple(
            f'cd "{self.declared_dir}" && {remainder}'
            for remainder in (
                "echo a & echo b",
                "echo a ; echo b",
                "echo 'abc",
                PLAIN_COMMAND,
            )
        )
        lines = [f"test_command: {DECLARED_COMMAND}"]
        lines += [f"build_command: {form}" for form in self.declared_forms]
        # The hook reads the workflow.yaml files under the git top level of
        # its cwd, which differs between the main working tree and the git
        # worktree, so both hold the same file.
        for top in (self.repo, self.worktree):
            wf_dir = top / "feature-docs" / "demo"
            wf_dir.mkdir(parents=True)
            (wf_dir / "workflow.yaml").write_text(
                "\n".join(lines) + "\n", encoding="utf-8"
            )

        # Approval stores.
        cli_remainders = [PLAIN_COMMAND]
        cli_remainders += [r for _, r in OPERATOR_CASES]
        cli_remainders += [r for _, r in ALLOW_REMAINDERS]
        cli_remainders += [r for _, r in SAFE_SIDE_CASES]
        direct_remainders = [r for _, r in LINE_BREAK_CASES]
        self.store = self.root / "approvals-main.json"
        self.write_store(self.store, cli_remainders, direct_remainders)

        # AC-4: the whole excluded cd form is itself approved.
        self.whole_form = f'cd "{self.whole_dir}" && echo a & echo b'
        self.store_whole = self.root / "approvals-whole.json"
        self.write_store(
            self.store_whole, ["echo a & echo b", self.whole_form], []
        )

        # AC-5: refusal-pattern strings holding a top-level operator.
        self.store_refusal = self.root / "approvals-refusal.json"
        self.write_store(self.store_refusal, [], [SUDO_AMPERSAND, SUDO_SEMICOLON])

    def env(self, store, extra=None):
        env = _clean_env()
        env["EM_WORKFLOW_APPROVALS"] = str(store)
        env["GIT_CEILING_DIRECTORIES"] = str(self.root)
        if extra:
            env.update(extra)
        return env

    def write_store(self, store, cli_commands, direct_commands):
        """Record cli_commands through the record CLI; add direct_commands to
        the same project entry by writing the store file."""
        if cli_commands:
            proc = subprocess.run(
                [
                    sys.executable,
                    str(GUARD_PATH),
                    "--record",
                    "--project-dir",
                    str(self.repo),
                ],
                input="\n".join(cli_commands) + "\n",
                capture_output=True,
                text=True,
                env=self.env(store),
            )
            if proc.returncode != 0:
                raise RuntimeError(f"--record failed: {proc.stderr}")
        if direct_commands:
            try:
                data = json.loads(store.read_text(encoding="utf-8"))
            except OSError:
                data = {"version": 1, "projects": {}}
            entry = data["projects"].setdefault(self.key, {})
            merged = set(entry.get("approved_commands") or []) | set(direct_commands)
            entry["approved_commands"] = sorted(merged)
            store.write_text(json.dumps(data), encoding="utf-8")

    def tokens(self):
        return {
            "@IN@": str(self.inside),
            "@DECL@": str(self.declared_dir),
            "@WHOLE@": str(self.whole_dir),
            "@OPS@": str(self.operator_dir),
        }

    def expand(self, template):
        for token, value in self.tokens().items():
            template = template.replace(token, value)
        return template

    def run_hook(self, command, cwd, store=None):
        payload = {"tool_name": "Bash", "tool_input": {"command": command}, "cwd": str(cwd)}
        return subprocess.run(
            [sys.executable, str(GUARD_PATH)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            env=self.env(store or self.store),
            cwd=str(cwd),
        )

    def cleanup(self):
        shutil.rmtree(self.root, ignore_errors=True)


FIX = None


def setUpModule():
    global FIX
    FIX = Fixture()


def tearDownModule():
    FIX.cleanup()


def decide(proc):
    """Return (decision, hookSpecificOutput dict or None)."""
    if proc.returncode != 0:
        raise AssertionError(f"hook exited {proc.returncode}: {proc.stderr}")
    if proc.stderr != "":
        raise AssertionError(f"hook wrote to stderr: {proc.stderr}")
    if proc.stdout == "":
        return SILENT, None
    output = json.loads(proc.stdout)["hookSpecificOutput"]
    return output["permissionDecision"], output


def prefixed(remainder, token="@IN@"):
    return 'cd "' + token + '" && ' + remainder


class HookCase(unittest.TestCase):
    def cwds(self):
        return (FIX.repo, FIX.worktree)

    def check_silent(self, cases):
        for cwd in self.cwds():
            for label, remainder in cases:
                with self.subTest(label=label, cwd=cwd.name):
                    command = FIX.expand(prefixed(remainder))
                    decision, output = decide(FIX.run_hook(command, cwd))
                    self.assertEqual((decision, output), (SILENT, None))

    def exact_match_reason(self):
        decision, output = decide(FIX.run_hook(PLAIN_COMMAND, FIX.repo))
        self.assertEqual(decision, ALLOW)
        return output["permissionDecisionReason"]


class TestAc1TopLevelOperatorsAreExcluded(HookCase):
    """AC-1 (FR1, FR2, FR4, TM-1)."""

    def test_ac1_operator_strings_get_no_decision(self):
        self.check_silent(OPERATOR_CASES)

    def test_ac1_line_break_strings_get_no_decision(self):
        self.check_silent(LINE_BREAK_CASES)

    def test_ac1_fixture_holds_the_strings_verbatim(self):
        # Guards the fixture: each excluded string is in the store, so only
        # the exclusion can keep the cd prefix form silent. The bare string
        # is allowed by exact match.
        for label, remainder in OPERATOR_CASES + LINE_BREAK_CASES:
            with self.subTest(label=label):
                decision, output = decide(FIX.run_hook(remainder, FIX.repo))
                self.assertEqual(decision, ALLOW)
                self.assertNotIn(CD_PREFIX_MARKER, output["permissionDecisionReason"])


class TestAc2RecognizedFormsStillAllowed(HookCase):
    """AC-2 (FR1, FR2, TM-1, TM-5)."""

    def check_prefix_allow(self, command, cwd):
        decision, output = decide(FIX.run_hook(command, cwd))
        self.assertEqual(decision, ALLOW)
        reason = output["permissionDecisionReason"]
        self.assertIn(CD_PREFIX_MARKER, reason)
        self.assertNotEqual(reason, self.exact_match_reason())

    def test_ac2_recognized_tokens_and_quoted_characters_allow(self):
        for cwd in self.cwds():
            for label, remainder in ALLOW_REMAINDERS:
                with self.subTest(label=label, cwd=cwd.name):
                    self.check_prefix_allow(FIX.expand(prefixed(remainder)), cwd)

    def test_ac2_surrounding_blanks_and_a_trailing_line_feed_allow(self):
        for cwd in self.cwds():
            with self.subTest(cwd=cwd.name):
                command = "  " + FIX.expand(prefixed("make test 2>&1")) + "  \n"
                self.check_prefix_allow(command, cwd)

    def test_ac2_operators_in_the_path_are_not_scanned(self):
        for cwd in self.cwds():
            with self.subTest(cwd=cwd.name):
                command = FIX.expand(prefixed(PLAIN_COMMAND, "@OPS@"))
                self.check_prefix_allow(command, cwd)


class TestAc3SafeSideExclusions(HookCase):
    """AC-3 (FR3, FR4, TM-2)."""

    def test_ac3_each_safe_side_string_gets_no_decision(self):
        self.check_silent(SAFE_SIDE_CASES)

    def test_ac3_fixture_holds_the_strings_verbatim(self):
        for label, remainder in SAFE_SIDE_CASES:
            with self.subTest(label=label):
                decision, output = decide(FIX.run_hook(remainder, FIX.repo))
                self.assertEqual(decision, ALLOW)
                self.assertNotIn(CD_PREFIX_MARKER, output["permissionDecisionReason"])


class TestAc4DecisionTableUnchanged(HookCase):
    """AC-4 (FR4, TM-5): the exclusion only narrows the cd prefix allow."""

    def test_ac4_bare_approved_string_with_an_operator_is_allowed_by_exact_match(self):
        expected = self.exact_match_reason()
        for cwd in self.cwds():
            with self.subTest(cwd=cwd.name):
                decision, output = decide(FIX.run_hook("echo a & echo b", cwd))
                self.assertEqual(decision, ALLOW)
                self.assertEqual(output["permissionDecisionReason"], expected)

    def test_ac4_bare_declared_unapproved_string_is_denied(self):
        decision, output = decide(FIX.run_hook(DECLARED_COMMAND, FIX.repo))
        self.assertEqual(decision, DENY)
        self.assertIn(UNAPPROVED_MARKER, output["permissionDecisionReason"])

    def test_ac4_excluded_form_whose_whole_string_is_declared_is_denied(self):
        # Each remainder is approved and excluded; the whole cd form is
        # declared in workflow.yaml and not approved.
        excluded = FIX.declared_forms[:3]
        _, guidance = decide(FIX.run_hook(DECLARED_COMMAND, FIX.repo))
        for cwd in self.cwds():
            for form in excluded:
                with self.subTest(form=form, cwd=cwd.name):
                    decision, output = decide(FIX.run_hook(form, cwd))
                    self.assertEqual(decision, DENY)
                    self.assertIn(UNAPPROVED_MARKER, output["permissionDecisionReason"])
                    self.assertEqual(
                        output["additionalContext"], guidance["additionalContext"]
                    )

    def test_ac4_not_excluded_form_whose_whole_string_is_declared_keeps_the_allow(self):
        form = FIX.declared_forms[3]
        for cwd in self.cwds():
            with self.subTest(cwd=cwd.name):
                decision, output = decide(FIX.run_hook(form, cwd))
                self.assertEqual(decision, ALLOW)
                self.assertIn(CD_PREFIX_MARKER, output["permissionDecisionReason"])

    def test_ac4_excluded_form_whose_whole_string_is_approved_is_allowed(self):
        expected = self.exact_match_reason()
        for cwd in self.cwds():
            with self.subTest(cwd=cwd.name):
                decision, output = decide(
                    FIX.run_hook(FIX.whole_form, cwd, FIX.store_whole)
                )
                self.assertEqual(decision, ALLOW)
                self.assertEqual(output["permissionDecisionReason"], expected)

    def test_ac4_excluded_form_neither_approved_nor_declared_gets_no_decision(self):
        command = FIX.expand(prefixed("echo a & echo b", "@WHOLE@"))
        decision, _ = decide(FIX.run_hook(command, FIX.repo))
        self.assertEqual(decision, SILENT)


class TestAc5RefusalPatternsAreAppliedFirst(HookCase):
    """AC-5 (FR5, TM-3)."""

    def test_ac5_refusal_string_with_an_operator_is_denied_in_cd_form(self):
        for cwd in self.cwds():
            for remainder in (SUDO_AMPERSAND, SUDO_SEMICOLON):
                with self.subTest(remainder=remainder, cwd=cwd.name):
                    command = FIX.expand(prefixed(remainder))
                    decision, output = decide(
                        FIX.run_hook(command, cwd, FIX.store_refusal)
                    )
                    self.assertEqual(decision, DENY)
                    reason = output["permissionDecisionReason"]
                    self.assertIn(REFUSAL_MARKER, reason)
                    self.assertIn("sudo", reason)

    def test_ac5_the_store_holds_the_refusal_strings_verbatim(self):
        # Guards the fixture: the bare strings also deny, proving the store
        # entries are what is being matched.
        for remainder in (SUDO_AMPERSAND, SUDO_SEMICOLON):
            with self.subTest(remainder=remainder):
                decision, output = decide(
                    FIX.run_hook(remainder, FIX.repo, FIX.store_refusal)
                )
                self.assertEqual(decision, DENY)
                self.assertIn(REFUSAL_MARKER, output["permissionDecisionReason"])


def _cd_prefix_paragraph():
    source = GUARD_PATH.read_text(encoding="utf-8")
    docstring = ast.get_docstring(ast.parse(source)) or ""
    start = docstring.find("cd prefix:")
    if start < 0:
        return ""
    paragraph = re.split(r"\n\s*\n", docstring[start:], maxsplit=1)[0]
    return " ".join(paragraph.split())


# (label, pattern) -- every statement the "cd prefix:" paragraph must carry.
STATEMENT_PATTERNS = (
    (
        "four top-level operators",
        re.compile(r"no lone `&`, `;`, `\|\|` or line break at the top level of the remainder"),
    ),
    (
        "operators are outside quotes",
        re.compile(r"remainder \(outside quotes and backslash escapes\)"),
    ),
    ("line break counts inside quotes", re.compile(r"a line break counts inside quotes too")),
    ("E5 unclosed quote", re.compile(r"an unclosed quote")),
    ("E6 trailing backslash", re.compile(r"a trailing backslash")),
    ("E7 dollar quote", re.compile(r"`\$'` or `\$\"` anywhere")),
    ("E8 hash", re.compile(r"`#` anywhere, inside quotes too")),
    (
        "E9 grouping characters",
        re.compile(r"`\(`, `\)`, `\{` or `\}` outside quotes and backslash escapes"),
    ),
    (
        "E10 substitutions",
        re.compile(r"`\$\(`, `\$\{` or a backtick anywhere, inside single quotes too"),
    ),
    ("never a new deny", re.compile(r"judged exactly as if it had no cd prefix")),
    (
        "refusal patterns first",
        re.compile(r"refusal patterns are applied to the whole command first"),
    ),
    (
        "refusal check independent of the operator condition",
        re.compile(r"does not depend on the operator conditions"),
    ),
)

RECOGNIZED_TOKEN_GROUP = re.compile(r"recognized tokens \(([^)]*)\)")
RECOGNIZED_TOKENS = ("&&", "|&", ">&", "<&", "&>", "&>>")


def missing_statements(paragraph):
    """Labels of the required statements the paragraph does not carry."""
    missing = [label for label, pattern in STATEMENT_PATTERNS if not pattern.search(paragraph)]
    group = RECOGNIZED_TOKEN_GROUP.search(paragraph)
    listed = set(re.findall(r"`([^`]*)`", group.group(1))) if group else set()
    missing += [f"token {token}" for token in RECOGNIZED_TOKENS if token not in listed]
    return missing


class TestAc6DocstringStatesTheConditions(unittest.TestCase):
    """AC-6 (FR9, FR10)."""

    def test_ac6_the_paragraph_is_found_and_covers_the_existing_conditions(self):
        paragraph = _cd_prefix_paragraph()
        self.assertTrue(paragraph.startswith("cd prefix:"))
        for fragment in ("syntax:", "path:", "approval:"):
            self.assertIn(fragment, paragraph)

    def test_ac6_the_paragraph_states_every_required_condition(self):
        self.assertEqual(missing_statements(_cd_prefix_paragraph()), [])

    def test_ac6_the_paragraph_ends_before_the_approval_store_paragraph(self):
        self.assertNotIn("Approval store:", _cd_prefix_paragraph())

    def test_ac6_the_matcher_fires_on_a_paragraph_missing_a_statement(self):
        # Forged text: remove one statement at a time; the matcher must name it.
        paragraph = _cd_prefix_paragraph()
        for label, pattern in STATEMENT_PATTERNS:
            with self.subTest(label=label):
                forged = pattern.sub("", paragraph)
                self.assertNotEqual(forged, paragraph)
                self.assertIn(label, missing_statements(forged))

    def test_ac6_the_matcher_fires_on_a_paragraph_missing_a_token(self):
        paragraph = _cd_prefix_paragraph()
        for token in RECOGNIZED_TOKENS:
            with self.subTest(token=token):
                group = RECOGNIZED_TOKEN_GROUP.search(paragraph)
                self.assertIsNotNone(group)
                forged_group = group.group(0).replace(f"`{token}`", "")
                self.assertNotEqual(forged_group, group.group(0))
                forged = paragraph.replace(group.group(0), forged_group)
                self.assertIn(f"token {token}", missing_statements(forged))

    def test_ac6_the_matcher_fires_when_the_paragraph_is_absent(self):
        self.assertEqual(
            len(missing_statements("")),
            len(STATEMENT_PATTERNS) + len(RECOGNIZED_TOKENS),
        )


def _imported_top_level_modules(source):
    found = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            found.add(node.module.split(".")[0])
    return found


def _non_standard_imports(source):
    return _imported_top_level_modules(source) - set(sys.stdlib_module_names)


class TestAc7StandardLibraryOnly(unittest.TestCase):
    """AC-7 (NFR1, NFR7)."""

    def test_ac7_the_checker_fires_on_forged_third_party_imports(self):
        self.assertEqual(_non_standard_imports("import requests\n"), {"requests"})
        self.assertEqual(_non_standard_imports("from yaml import safe_load\n"), {"yaml"})
        self.assertEqual(_non_standard_imports("import os\nfrom json import dumps\n"), set())

    def test_ac7_this_test_module_imports_only_standard_library_modules(self):
        source = Path(__file__).read_text(encoding="utf-8")
        self.assertTrue(_imported_top_level_modules(source))
        self.assertEqual(_non_standard_imports(source), set())

    def test_ac7_hook_imports_only_standard_library_modules(self):
        source = GUARD_PATH.read_text(encoding="utf-8")
        self.assertTrue(_imported_top_level_modules(source))
        self.assertEqual(_non_standard_imports(source), set())


if __name__ == "__main__":
    unittest.main()
