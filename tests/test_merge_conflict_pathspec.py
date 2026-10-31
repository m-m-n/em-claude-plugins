"""Tests for task0011 (feature-docs/unattended-merge): the conflict-resolution
step of `em-workflow/skills/merge/SKILL.md` passes a conflicted path to git as
a literal path (FR12, NFR4, TM-6; TS29, TS15).

Quoting and `--` do not disable git's pathspec magic: a file named `:(top)` or
`:(top,glob)*.md` handed to `git add -- "<path>"` selects other files. The
documented forms therefore carry git's `--literal-pathspecs` global option.

Method: the command forms are read out of step 9 of SKILL.md at test time, so
the behavioral tests run the documented text, not a copy of it. Each
behavioral test builds its own temporary git repository, leaves a conflicting
merge in progress on a magic-named file, and runs the documented form with an
argument list (no shell) after replacing only the placeholders. Every
behavioral test has a control that runs the same fixture with the plain form
(no `--literal-pathspecs`) and shows the damage the option prevents, so a
passing result cannot come from a fixture that never could fail.

Covers task0011 Acceptance Criteria
(feature-docs/unattended-merge/tasks/task0011.md):

- AC-1: staging a conflicted `:(top)` stages only that path.
- AC-2: staging a conflicted `:(top,glob)*.md` stages only that path.
- AC-3: resolving a conflict as a deletion of `:(top)` removes only that path.
- AC-4: the attribution log lists only the base-side commits that touched
  `:(top)`.
- AC-5: static check of every `git add` / `git rm` / `git log` form that
  contains `<conflicted_path>`, and of the list of permitted actions.
- AC-6: destructive-guard, run as a hook payload under CLAUDE_BATCH, returns
  no `ask` / `deny` for the three literal forms.

AC-7 (the whole suite passes) is the project's test command itself.

Standard library only; the hook subprocess runs with bytecode writing off, so
nothing is written under `em-workflow/`.
"""

import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"
SKILL_PATH = PLUGIN_ROOT / "skills" / "merge" / "SKILL.md"
GUARD_PATH = PLUGIN_ROOT / "hooks" / "destructive-guard.py"

PLACEHOLDER = "<conflicted_path>"
OPTION = "--literal-pathspecs"
PATH_SUBCOMMANDS = ("add", "rm", "log")

FENCE_RE = re.compile(r"^\s*```")
BASH_FENCE_RE = re.compile(r"^\s*```(?:bash|sh)\s*$")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
INLINE_RE = re.compile(r"`([^`\n]+)`")

GIT_TIMEOUT = 60


# ---------------------------------------------------------------------------
# Reading the command forms out of SKILL.md step 9
# ---------------------------------------------------------------------------


def step9_body(text):
    """Lines of the conflict-resolution section (heading `### 9. ...` up to
    the next heading of the same or a higher level)."""
    lines = text.split("\n")
    in_fence = False
    start = None
    level = None
    for index, line in enumerate(lines):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = HEADING_RE.match(line)
        if not match:
            continue
        if start is None:
            if re.match(r"9\.\s", match.group(2)):
                start = index
                level = len(match.group(1))
        elif len(match.group(1)) <= level:
            return lines[start:index]
    return lines[start:] if start is not None else None


def command_forms(lines):
    """Every line of a Bash fence and every inline code span in `lines`."""
    forms = []
    in_bash = False
    in_other_fence = False
    for line in lines:
        if in_bash or in_other_fence:
            if FENCE_RE.match(line):
                in_bash = in_other_fence = False
            elif in_bash and line.strip():
                forms.append(line.strip())
            continue
        if BASH_FENCE_RE.match(line):
            in_bash = True
            continue
        if FENCE_RE.match(line):
            in_other_fence = True
            continue
        forms.extend(match.group(1).strip() for match in INLINE_RE.finditer(line))
    return forms


def subcommand(tokens):
    """The git subcommand of a tokenised form: the first token after `git`
    that is not an option. None when the form is not a git command."""
    if not tokens or tokens[0] != "git":
        return None
    for token in tokens[1:]:
        if not token.startswith("-"):
            return token
    return None


def tokenize(form):
    try:
        return shlex.split(form)
    except ValueError:
        return []


def path_forms(forms):
    """The forms that hand `<conflicted_path>` to git as a pathspec: git add /
    rm / log carrying the placeholder."""
    found = []
    for form in forms:
        tokens = tokenize(form)
        if PLACEHOLDER in tokens and subcommand(tokens) in PATH_SUBCOMMANDS:
            found.append(form)
    return found


def violations(forms):
    """The path forms whose first token after `git` is not --literal-pathspecs."""
    return [
        form
        for form in path_forms(forms)
        if tokenize(form)[1:2] != [OPTION]
    ]


def read_skill():
    return SKILL_PATH.read_text(encoding="utf-8")


def skill_forms():
    body = step9_body(read_skill())
    if body is None:
        raise AssertionError("SKILL.md has no step 9 heading")
    return command_forms(body)


def form_for(subcmd):
    """The one documented form of `subcmd` (add / rm / log) that carries the
    conflicted-path placeholder."""
    matches = [f for f in path_forms(skill_forms()) if subcommand(tokenize(f)) == subcmd]
    if len(matches) != 1:
        raise AssertionError(
            "expected exactly one step 9 `git %s` form with %s, found %d: %r"
            % (subcmd, PLACEHOLDER, len(matches), matches)
        )
    return matches[0]


def merge_base_form():
    matches = [f for f in skill_forms() if f.startswith("git merge-base ")]
    if len(matches) != 1:
        raise AssertionError("expected exactly one `git merge-base` form: %r" % matches)
    return matches[0]


def argv(form, **placeholders):
    """The form as an argument list, `<name>` placeholders replaced."""
    out = []
    for token in tokenize(form):
        for name, value in placeholders.items():
            token = token.replace("<%s>" % name, value)
        out.append(token)
    return out


# ---------------------------------------------------------------------------
# Fixture: a temporary repository with a conflicting merge left in progress
# ---------------------------------------------------------------------------


def git_env(literal_setup):
    env = dict(os.environ)
    env.update(
        {
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_SYSTEM": os.devnull,
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@example.com",
        }
    )
    env.pop("GIT_LITERAL_PATHSPECS", None)
    if literal_setup:
        # Fixture building handles magic-named files; the documented forms
        # under test are always run without this variable.
        env["GIT_LITERAL_PATHSPECS"] = "1"
    return env


class Repo:
    def __init__(self, root):
        self.root = Path(root)

    def run(self, args, literal_setup=False, check=True):
        proc = subprocess.run(
            args,
            cwd=str(self.root),
            env=git_env(literal_setup),
            capture_output=True,
            text=True,
            timeout=GIT_TIMEOUT,
        )
        if check and proc.returncode != 0:
            raise AssertionError("%r failed: %s%s" % (args, proc.stdout, proc.stderr))
        return proc

    def setup(self, *args, check=True):
        return self.run(["git"] + list(args), literal_setup=True, check=check)

    def write(self, name, content):
        (self.root / name).write_text(content, encoding="utf-8")

    def commit_all(self, message):
        self.setup("add", "-A")
        self.setup("commit", "-q", "-m", message)

    def head(self):
        return self.setup("rev-parse", "HEAD").stdout.strip()

    def cached_names(self):
        out = self.run(["git", "diff", "--cached", "--name-only", "-z"]).stdout
        return sorted(name for name in out.split("\0") if name)

    def index_names(self):
        out = self.run(["git", "ls-files", "-z"]).stdout
        return sorted(name for name in out.split("\0") if name)


def make_repo(base_dir):
    repo = Repo(Path(base_dir) / "repo")
    repo.root.mkdir()
    repo.setup("init", "-q", "-b", "main")
    return repo


def conflict_on_modify(repo, magic_name, base_side_extra=None):
    """A merge of `main` into `feature` left in progress, both sides having
    changed `magic_name`. `base_side_extra` is an optional (file, content)
    committed on the base side as a separate commit after the conflicting
    one. An unrelated tracked file is then modified and left unstaged.
    Returns the base-side commit SHAs (conflicting one first)."""
    repo.write(magic_name, "base\n")
    repo.write("README.md", "readme\n")
    repo.write("notes.txt", "notes\n")
    repo.commit_all("init")
    repo.setup("checkout", "-q", "-b", "feature")
    repo.write(magic_name, "feature side\n")
    repo.commit_all("feature change")
    repo.setup("checkout", "-q", "main")
    repo.write(magic_name, "base side\n")
    repo.commit_all("base change on the conflicted file")
    base_commits = [repo.head()]
    if base_side_extra is not None:
        name, content = base_side_extra
        repo.write(name, content)
        repo.commit_all("base change on another file")
        base_commits.append(repo.head())
    repo.setup("checkout", "-q", "feature")
    merge = repo.setup("merge", "main", check=False)
    if merge.returncode == 0:
        raise AssertionError("the fixture merge did not conflict")
    # An unrelated tracked file, modified and not staged.
    repo.write("README.md", "readme\nlocal edit\n")
    return base_commits


def conflict_on_delete(repo, magic_name):
    """A merge in which the base side deleted `magic_name` and the feature
    side modified it (modify/delete), left in progress."""
    repo.write(magic_name, "base\n")
    repo.write("README.md", "readme\n")
    repo.write("notes.txt", "notes\n")
    repo.commit_all("init")
    repo.setup("checkout", "-q", "-b", "feature")
    repo.write(magic_name, "feature side\n")
    repo.commit_all("feature change")
    repo.setup("checkout", "-q", "main")
    repo.setup("rm", "-q", "--", magic_name)
    repo.setup("commit", "-q", "-m", "base deletes the file")
    repo.setup("checkout", "-q", "feature")
    merge = repo.setup("merge", "main", check=False)
    if merge.returncode == 0:
        raise AssertionError("the fixture merge did not conflict")


PLAIN_FORMS = {
    "add": ["git", "add", "--", PLACEHOLDER],
    "rm": ["git", "rm", "--", PLACEHOLDER],
    "log": ["git", "log", "--format=%H", "<merge_base>..MERGE_HEAD", "--", PLACEHOLDER],
}


class FixtureCase(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="merge-pathspec-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.repo = make_repo(self.tmp)

    def merge_base(self):
        # The documented `git merge-base` form, run as written.
        out = self.repo.run(argv(merge_base_form()))
        return out.stdout.strip()

    def run_documented(self, subcmd, path, **extra):
        form = form_for(subcmd)
        return self.repo.run(argv(form, conflicted_path=path, **extra), check=False)

    def run_plain(self, subcmd, path, **extra):
        args = []
        for token in PLAIN_FORMS[subcmd]:
            for name, value in dict(conflicted_path=path, **extra).items():
                token = token.replace("<%s>" % name, value)
            args.append(token)
        return self.repo.run(args, check=False)


# ---------------------------------------------------------------------------
# AC-1, AC-2: staging
# ---------------------------------------------------------------------------


class TestStagingForm(FixtureCase):
    def test_ac1_staging_a_conflicted_top_named_file_stages_only_it(self):
        conflict_on_modify(self.repo, ":(top)")
        self.repo.write(":(top)", "resolved\n")
        result = self.run_documented("add", ":(top)")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.repo.cached_names(), [":(top)"])

    def test_ac1_control_the_plain_form_stages_the_unrelated_file(self):
        conflict_on_modify(self.repo, ":(top)")
        self.repo.write(":(top)", "resolved\n")
        self.run_plain("add", ":(top)")
        self.assertIn("README.md", self.repo.cached_names())

    def test_ac2_staging_a_conflicted_top_glob_named_file_stages_only_it(self):
        name = ":(top,glob)*.md"
        conflict_on_modify(self.repo, name)
        self.repo.write(name, "resolved\n")
        result = self.run_documented("add", name)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.repo.cached_names(), [name])

    def test_ac2_control_the_plain_form_stages_the_unrelated_markdown_file(self):
        name = ":(top,glob)*.md"
        conflict_on_modify(self.repo, name)
        self.repo.write(name, "resolved\n")
        self.run_plain("add", name)
        self.assertIn("README.md", self.repo.cached_names())


# ---------------------------------------------------------------------------
# AC-3: deletion
# ---------------------------------------------------------------------------


class TestDeletionForm(FixtureCase):
    def test_ac3_a_deletion_resolution_removes_only_the_conflicted_file(self):
        conflict_on_delete(self.repo, ":(top)")
        result = self.run_documented("rm", ":(top)")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.repo.index_names(), ["README.md", "notes.txt"])

    def test_ac3_control_the_plain_form_does_not_resolve_the_conflicted_file(self):
        conflict_on_delete(self.repo, ":(top)")
        self.run_plain("rm", ":(top)")
        # Read as pathspec magic, the plain form does not delete the file that
        # carries the name: it stays in the index.
        self.assertIn(":(top)", self.repo.index_names())


# ---------------------------------------------------------------------------
# AC-4: attribution
# ---------------------------------------------------------------------------


class TestAttributionForm(FixtureCase):
    def test_ac4_attribution_lists_only_base_commits_that_touched_the_path(self):
        base_commits = conflict_on_modify(
            self.repo, ":(top)", base_side_extra=("notes.txt", "notes changed on base\n")
        )
        merge_base = self.merge_base()
        result = self.run_documented("log", ":(top)", merge_base=merge_base)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.split(), [base_commits[0]])

    def test_ac4_control_the_plain_form_also_lists_the_unrelated_commit(self):
        base_commits = conflict_on_modify(
            self.repo, ":(top)", base_side_extra=("notes.txt", "notes changed on base\n")
        )
        merge_base = self.merge_base()
        result = self.run_plain("log", ":(top)", merge_base=merge_base)
        self.assertEqual(sorted(result.stdout.split()), sorted(base_commits))


# ---------------------------------------------------------------------------
# AC-5: static check of the documented text
# ---------------------------------------------------------------------------


class TestStaticForms(unittest.TestCase):
    def test_ac5_step9_has_an_add_an_rm_and_a_log_form_over_the_conflicted_path(self):
        found = {subcommand(tokenize(form)) for form in path_forms(skill_forms())}
        self.assertEqual(found, set(PATH_SUBCOMMANDS))

    def test_ac5_every_form_over_the_conflicted_path_has_the_option_right_after_git(self):
        forms = path_forms(skill_forms())
        self.assertTrue(forms)
        for form in forms:
            self.assertEqual(tokenize(form)[:2], ["git", OPTION], form)
        self.assertEqual(violations(skill_forms()), [])

    def test_ac5_the_matcher_fires_on_forged_forms_without_the_option(self):
        forged = [
            'git add -- "<conflicted_path>"',
            'git rm -- "<conflicted_path>"',
            'git log --format=%H <merge_base>..MERGE_HEAD -- "<conflicted_path>"',
            'git --no-pager add -- "<conflicted_path>"',
            'git add --literal-pathspecs -- "<conflicted_path>"',
        ]
        self.assertEqual(violations(forged), forged)
        good = [
            'git --literal-pathspecs add -- "<conflicted_path>"',
            'git --literal-pathspecs rm -- "<conflicted_path>"',
            'git --literal-pathspecs log --format=%H <merge_base>..MERGE_HEAD -- "<conflicted_path>"',
        ]
        self.assertEqual(violations(good), [])
        self.assertEqual(path_forms(good), good)

    def test_ac5_forms_without_the_placeholder_are_not_judged(self):
        other = [
            "git merge-base HEAD MERGE_HEAD",
            "git log --merges --format=%H%x20%P%x20%s <merge_base>..MERGE_HEAD",
            "git add",
        ]
        self.assertEqual(path_forms(other), [])

    def test_ac5_the_permitted_actions_name_the_literal_forms(self):
        permitted = [
            line for line in step9_body(read_skill()) if "このステップで許すのは次だけ" in line
        ]
        self.assertEqual(len(permitted), 1)
        line = permitted[0]
        self.assertIn("git --literal-pathspecs add", line)
        self.assertIn("git --literal-pathspecs rm", line)
        self.assertNotRegex(line, r"git (add|rm)\b")

    def test_ac5_unattributable_path_conditions_are_unchanged(self):
        body = "\n".join(step9_body(read_skill()))
        self.assertIn("パスに `\"` `$` バッククォート `\\` 改行のどれかが含まれる。", body)
        self.assertIn(
            'git commit -m "Merge <base_branch> into em-workflow/<feature>/integration (resolve conflicts)"',
            body,
        )
        self.assertIn("hook は迂回しない", body)


# ---------------------------------------------------------------------------
# AC-6: destructive-guard under CLAUDE_BATCH
# ---------------------------------------------------------------------------


def guard_decision(command):
    """The permissionDecision destructive-guard gives `command` as a hook
    payload under CLAUDE_BATCH; "silent" when it prints nothing."""
    env = dict(os.environ)
    env["CLAUDE_BATCH"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    payload = {"tool_name": "Bash", "tool_input": {"command": command}}
    proc = subprocess.run(
        [sys.executable, str(GUARD_PATH)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        env=env,
        timeout=30,
    )
    if proc.returncode != 0:
        raise AssertionError("destructive-guard exited %d: %s" % (proc.returncode, proc.stderr))
    if not proc.stdout.strip():
        return "silent"
    return json.loads(proc.stdout)["hookSpecificOutput"]["permissionDecision"]


SAMPLE_PATHS = ("feature-docs/sample/SPEC.md", ":(top)")
SAMPLE_BASE = "0123456789abcdef0123456789abcdef01234567"


class TestGuardUnderBatch(unittest.TestCase):
    def filled(self, form, path):
        # Placeholders replaced in the documented text, quoting kept as written.
        return form.replace("<conflicted_path>", path).replace("<merge_base>", SAMPLE_BASE)

    def test_ac6_the_three_literal_forms_are_neither_asked_nor_denied(self):
        for subcmd in PATH_SUBCOMMANDS:
            form = form_for(subcmd)
            self.assertEqual(tokenize(form)[:2], ["git", OPTION], form)
            for path in SAMPLE_PATHS:
                command = self.filled(form, path)
                self.assertNotIn(guard_decision(command), ("ask", "deny"), command)

    def test_ac6_control_the_guard_judges_a_destructive_command_under_batch(self):
        self.assertIn(guard_decision("git reset --hard HEAD"), ("ask", "deny"))


if __name__ == "__main__":
    unittest.main()
