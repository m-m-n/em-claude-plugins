"""Linked-layout tests for queue_launch_guard.py (canonical-worktree-path-guards, task0001).

In a linked layout one of `.claude`, `.claude/worktrees` or
`.claude/worktrees/em-workflow` is a symlink that resolves inside the main
worktree. The canonical (strict-realpath) `worktree_path` of a task worktree
then lacks the `/.claude/worktrees/em-workflow/` segment, and the launch
guard derives the project root from git's common dir instead.

The module is self-contained: it builds its own launch payload and its own
hook subprocess helper and imports no other test module.

Covers task0001 Acceptance Criteria
(feature-docs/canonical-worktree-path-guards/tasks/task0001.md):

- AC-1: a launch from the main worktree is allowed in every linked layout
  (TestLinkedLayoutMainWorktreeLaunch).
- AC-2: a launch from inside another worktree is denied in every linked
  layout, naming the main worktree, before the journal is touched
  (TestLinkedLayoutOtherWorktreeLaunch).
- AC-3: segment absent and no common dir resolvable -> fail-open
  (TestSegmentAbsentFailOpen).
- AC-4: the fallback call shape (TestFallbackCallShape).
- AC-5: every failure of the fallback call leaves the project root
  undetermined (TestFallbackFailures).
- AC-6: the hook's module docstring (TestHookDocstring).
- AC-7: standard library only, symlink fixtures, no timing
  (TestStdlibAndDeterminism).
"""

import ast
import contextlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HOOK_PATH = os.path.join(REPO_ROOT, "em-workflow", "hooks", "queue_launch_guard.py")
THIS_PATH = os.path.abspath(__file__)

SEGMENT = "/.claude/worktrees/em-workflow/"
FEATURE = "linked-feature"
TASK_ID = "task0001"

GIT_CALL_TIMEOUT_SECONDS = 60
HOOK_CALL_TIMEOUT_SECONDS = 60

# Environment variables that make git act on a repository other than the one
# its working directory names. A suite started from inside a git hook inherits
# them; they are removed from every git call and from the hook subprocess.
REPOSITORY_SELECTING_GIT_VARS = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_COMMON_DIR",
    "GIT_PREFIX",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_NAMESPACE",
    "GIT_QUARANTINE_PATH",
    "GIT_CEILING_DIRECTORIES",
)

# (label, link path below the project root, name of the link's target
# directory below the project root). A target name never recreates the
# `/.claude/worktrees/em-workflow/` segment.
PLACEMENTS = (
    ("claude", ".claude", "store-claude"),
    ("claude-worktrees", ".claude/worktrees", "store-worktrees"),
    ("claude-worktrees-em-workflow", ".claude/worktrees/em-workflow", "store-em-workflow"),
)

# The statement of the hook's module docstring before this task, verbatim from
# the pre-change file (fail-open paragraph).
PRE_CHANGE_FAIL_OPEN_EXCERPT = """\
Fail-open convention: this hook is a net, not an authority. Any unexpected
state — malformed stdin, an invalid task id or worktree path, an unreadable
journal, an uncreatable journal location, a missing cwd, a worktree path
outside the `.claude/worktrees/em-workflow/` layout, a cwd whose git
toplevel cannot be resolved — exits 0 silently rather than
risk blocking (or crashing) the user's session."""
PRE_CHANGE_OUTSIDE_LAYOUT_STATEMENT = (
    "a worktree path outside the `.claude/worktrees/em-workflow/` layout"
)

# What the module docstring states now. Each is searched after whitespace
# normalization.
DOCSTRING_SEGMENT_STATEMENT = (
    "When the worktree path contains the `.claude/worktrees/em-workflow/` "
    "segment, the project root is the prefix before its last occurrence."
)
DOCSTRING_FALLBACK_STATEMENT = (
    "When the segment is absent, the project root is the parent directory of "
    "the git common dir resolved from the worktree path"
)
DOCSTRING_FAIL_OPEN_STATEMENT = (
    "When neither resolves, the project root is undetermined and the cwd "
    "check is skipped (fail-open)."
)


def git_environment(extra=None):
    env = {k: v for k, v in os.environ.items() if k not in REPOSITORY_SELECTING_GIT_VARS}
    env["GIT_CONFIG_NOSYSTEM"] = "1"
    env["GIT_CONFIG_GLOBAL"] = os.devnull
    env.update(extra or {})
    return env


FIXTURE_GIT_ENV = {
    "GIT_AUTHOR_NAME": "Fixture",
    "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
    "GIT_COMMITTER_NAME": "Fixture",
    "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
}


def run_git(args, cwd):
    proc = subprocess.run(
        ["git", "-c", "commit.gpgsign=false", *args],
        cwd=cwd,
        env=git_environment(FIXTURE_GIT_ENV),
        capture_output=True,
        text=True,
        timeout=GIT_CALL_TIMEOUT_SECONDS,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed in {cwd}: {proc.stderr.strip()}")
    return proc.stdout


class LinkedLayout:
    """A temporary git project whose worktree root is reached through a link."""

    def __init__(self, label, link_path, project_root, integration, task, task_via_link):
        self.label = label
        self.link_path = link_path
        self.project_root = project_root
        self.integration = integration  # canonical (strict realpath)
        self.task = task  # canonical (strict realpath) -> the worktree_path
        self.task_via_link = task_via_link  # the path reached through the link


@contextlib.contextmanager
def linked_layout(label, link_relpath, store_name):
    """git project with the link at `link_relpath` -> `store_name`, an
    integration worktree and a task worktree created through the link."""
    with tempfile.TemporaryDirectory() as tmp:
        project_root = os.path.realpath(tmp)
        run_git(["init", "-q", project_root], cwd=project_root)
        with open(os.path.join(project_root, "README.md"), "w", encoding="utf-8") as fh:
            fh.write("fixture\n")
        run_git(["add", "README.md"], cwd=project_root)
        run_git(["commit", "-q", "-m", "initial"], cwd=project_root)

        store = os.path.join(project_root, store_name)
        os.makedirs(store)
        link = os.path.join(project_root, link_relpath)
        os.makedirs(os.path.dirname(link), exist_ok=True)
        os.symlink(store, link)

        feature_via_link = os.path.join(
            project_root, ".claude", "worktrees", "em-workflow", FEATURE
        )
        os.makedirs(feature_via_link)
        integration_via_link = os.path.join(feature_via_link, "integration")
        task_via_link = os.path.join(feature_via_link, TASK_ID)
        run_git(
            ["worktree", "add", "-q", "-b", f"em-workflow/{FEATURE}/integration",
             integration_via_link],
            cwd=project_root,
        )
        run_git(
            ["worktree", "add", "-q", "-b", f"em-workflow/{FEATURE}/{TASK_ID}",
             task_via_link],
            cwd=project_root,
        )
        yield LinkedLayout(
            label,
            link_relpath,
            project_root,
            os.path.realpath(integration_via_link, strict=True),
            os.path.realpath(task_via_link, strict=True),
            task_via_link,
        )


def build_prompt(task_id, worktree_path):
    return (
        "# Task assignment\n"
        f"task_id: {task_id}\n"
        f"worktree_path: {worktree_path}\n"
        f"task_plan_path: /main/feature-docs/f/tasks/{task_id}.md\n"
        "implementation_md_path: /main/feature-docs/f/IMPLEMENTATION.md\n"
        "parent_branch: em-workflow/f/integration\n"
        "merge_script: /main/em-workflow/scripts/merge-task.sh\n"
        "skills_to_load: []\n"
        "project_commands:\n"
        "  build: \"\"\n"
        "  test: \"echo ok\"\n"
        "  format: \"\"\n"
        "expected_files: []\n"
    )


def launch_payload(worktree_path, cwd=None, task_id=TASK_ID):
    payload = {
        "tool_name": "Agent",
        "tool_input": {
            "subagent_type": "em-workflow:implementer",
            "description": f"Implement {task_id}",
            "prompt": build_prompt(task_id, worktree_path),
        },
    }
    if cwd is not None:
        payload["cwd"] = cwd
    return payload


def run_hook(payload, extra_env=None):
    return subprocess.run(
        [sys.executable, HOOK_PATH],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=HOOK_CALL_TIMEOUT_SECONDS,
        env=git_environment(extra_env),
    )


def journal_file_for(worktree_path):
    return os.path.join(os.path.dirname(worktree_path), "journal.jsonl")


def read_journal(worktree_path):
    path = journal_file_for(worktree_path)
    if not os.path.isfile(path):
        return []
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def launched_events(worktree_path, task_id=TASK_ID):
    return [
        e for e in read_journal(worktree_path)
        if e.get("event") == "launched" and e.get("task") == task_id
    ]


def load_hook_module():
    spec = importlib.util.spec_from_file_location(
        "queue_launch_guard_linked_layout_under_test", HOOK_PATH
    )
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


def deny_output(test, proc):
    """The hookSpecificOutput of a deny, failing the test cleanly when the hook
    allowed the launch (no output)."""
    test.assertEqual(proc.returncode, 0, proc.stderr)
    test.assertNotEqual(proc.stdout.strip(), "", "expected a deny decision, got no output")
    return json.loads(proc.stdout)["hookSpecificOutput"]


def completed(stdout, returncode=0):
    return subprocess.CompletedProcess(args=[], returncode=returncode, stdout=stdout, stderr="")


class RecordingRunner:
    """Stand-in for the hook's process runner (`subprocess.run`): records
    every call and answers each git command from a scripted outcome. An
    outcome is a CompletedProcess to return or an exception to raise."""

    COMMON_DIR_FLAG = "--git-common-dir"
    TOPLEVEL_FLAG = "--show-toplevel"

    def __init__(self, common_dir=None, toplevel=None):
        self.outcomes = {self.COMMON_DIR_FLAG: common_dir, self.TOPLEVEL_FLAG: toplevel}
        self.calls = []

    def __call__(self, *args, **kwargs):
        command = list(args[0] if args else kwargs["args"])
        self.calls.append((command, kwargs))
        for flag, outcome in self.outcomes.items():
            if flag in command:
                if isinstance(outcome, BaseException):
                    raise outcome
                if outcome is None:
                    raise AssertionError(f"no outcome scripted for {command}")
                return outcome
        raise AssertionError(f"unexpected process: {command}")

    def common_dir_calls(self):
        return [(c, k) for c, k in self.calls if self.COMMON_DIR_FLAG in c]


def normalized(text):
    return " ".join(text.split())


def contains_normalized(text, needle):
    return normalized(needle) in normalized(text)


def imported_top_level_modules(source):
    tree = ast.parse(source)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imported.add(node.module.split(".")[0])
    return imported


def timing_dependencies(source):
    """Names that signal timing or concurrency in `source`: imports of time /
    threading style modules and any use of a name or attribute `sleep`."""
    tree = ast.parse(source)
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = (
                [a.name for a in node.names]
                if isinstance(node, ast.Import)
                else [node.module or ""]
            )
            for name in names:
                top = name.split(".")[0]
                if top in ("time", "threading", "sched", "asyncio", "multiprocessing"):
                    found.add(top)
        elif isinstance(node, ast.Attribute) and node.attr == "sleep":
            found.add("sleep")
        elif isinstance(node, ast.Name) and node.id == "sleep":
            found.add("sleep")
    return found


class TestLinkedLayoutMainWorktreeLaunch(unittest.TestCase):
    """AC-1: with the project root derived from git's common dir, a launch
    whose cwd is the main worktree is allowed and recorded."""

    def test_launch_from_main_worktree_is_allowed_and_recorded_in_every_placement(self):
        for label, link_relpath, store_name in PLACEMENTS:
            with self.subTest(placement=label), \
                    linked_layout(label, link_relpath, store_name) as layout:
                self.assertNotIn(SEGMENT, layout.task)
                self.assertNotEqual(layout.task, layout.task_via_link)
                self.assertEqual(layout.task, os.path.realpath(layout.task_via_link))

                proc = run_hook(launch_payload(layout.task, cwd=layout.project_root))

                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertEqual(proc.stdout, "")
                self.assertEqual(len(launched_events(layout.task)), 1)


class TestLinkedLayoutOtherWorktreeLaunch(unittest.TestCase):
    """AC-2: a launch whose cwd is inside another worktree of the project is
    denied, naming the main worktree, before the journal is touched."""

    def test_launch_from_integration_worktree_is_denied_naming_the_main_worktree(self):
        for label, link_relpath, store_name in PLACEMENTS:
            with self.subTest(placement=label), \
                    linked_layout(label, link_relpath, store_name) as layout:
                self.assertNotIn(SEGMENT, layout.task)

                proc = run_hook(launch_payload(layout.task, cwd=layout.integration))

                output = deny_output(self, proc)
                self.assertEqual(output["permissionDecision"], "deny")
                self.assertIn(TASK_ID, output["permissionDecisionReason"])
                self.assertIn(layout.project_root, output["permissionDecisionReason"])
                self.assertIn(f'cd "{layout.project_root}"', output["additionalContext"])

    def test_denied_launch_leaves_no_launched_event_and_no_journal(self):
        for label, link_relpath, store_name in PLACEMENTS:
            with self.subTest(placement=label), \
                    linked_layout(label, link_relpath, store_name) as layout:
                proc = run_hook(launch_payload(layout.task, cwd=layout.integration))

                self.assertEqual(deny_output(self, proc)["permissionDecision"], "deny")
                self.assertEqual(launched_events(layout.task), [])
                self.assertFalse(os.path.exists(journal_file_for(layout.task)))

    def test_launch_from_the_task_worktree_itself_is_also_denied(self):
        label, link_relpath, store_name = PLACEMENTS[0]
        with linked_layout(label, link_relpath, store_name) as layout:
            proc = run_hook(launch_payload(layout.task, cwd=layout.task))

            output = deny_output(self, proc)
            self.assertEqual(output["permissionDecision"], "deny")
            self.assertIn(layout.project_root, output["permissionDecisionReason"])


class TestSegmentAbsentFailOpen(unittest.TestCase):
    """AC-3: segment absent and git unable to resolve a common dir -> the
    project root is undetermined, the cwd check is skipped, nothing is denied."""

    @contextlib.contextmanager
    def _non_repository(self, make_worktree_path):
        """Yields (run, worktree_path): `run()` launches from the cwd of an
        unrelated git repository, so a root wrongly derived from the cwd would
        show as a denial. The worktree path lies in a directory that is not
        part of any repository."""
        with tempfile.TemporaryDirectory() as tmp:
            base = os.path.realpath(tmp)
            other_repository = os.path.join(base, "other-repository")
            os.makedirs(other_repository)
            run_git(["init", "-q", other_repository], cwd=other_repository)
            worktree_path = make_worktree_path(os.path.join(base, "not-a-repository"))
            self.assertNotIn(SEGMENT, worktree_path)

            def run():
                # Bound git's repository discovery so a temp dir below a
                # repository cannot be found from the worktree path.
                return run_hook(
                    launch_payload(worktree_path, cwd=other_repository),
                    extra_env={"GIT_CEILING_DIRECTORIES": base},
                )

            yield run, worktree_path

    def test_existing_directory_inside_a_non_repository_fails_open(self):
        def make(non_repository):
            path = os.path.join(non_repository, FEATURE, TASK_ID)
            os.makedirs(path)
            return path

        with self._non_repository(make) as (run, worktree_path):
            proc = run()

            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(proc.stdout, "")
            self.assertEqual(len(launched_events(worktree_path)), 1)

    def test_nonexistent_absolute_path_fails_open(self):
        with self._non_repository(
            lambda non_repository: os.path.join(non_repository, FEATURE, TASK_ID)
        ) as (run, worktree_path):
            self.assertFalse(os.path.exists(worktree_path))

            proc = run()

            self.assertEqual(proc.returncode, 0, proc.stderr)
            self.assertEqual(proc.stdout, "")
            self.assertFalse(os.path.exists(os.path.dirname(worktree_path)))


class TestFallbackCallShape(unittest.TestCase):
    """AC-4: the segment decides; only a path without it runs the one
    git-common-dir call, in the worktree path, bounded by the existing timeout."""

    SEGMENT_PATH = "/proj/.claude/worktrees/em-workflow/f/task0001"
    CANONICAL_PATH = "/proj-store/em-workflow/f/task0001"

    @classmethod
    def setUpClass(cls):
        cls.hook = load_hook_module()

    def _patched(self, runner):
        return mock.patch.object(self.hook.subprocess, "run", runner)

    def test_path_with_the_segment_triggers_no_process_at_all(self):
        runner = RecordingRunner()
        with self._patched(runner):
            root = self.hook.project_root_for(self.SEGMENT_PATH)

        self.assertEqual(root, "/proj")
        self.assertEqual(runner.calls, [])

    def test_path_with_the_segment_triggers_no_git_common_dir_call_in_the_cwd_check(self):
        runner = RecordingRunner(toplevel=completed("/proj\n"))
        with self._patched(runner):
            result = self.hook.cwd_outside_project_root("/proj", self.SEGMENT_PATH)

        self.assertIsNone(result)
        self.assertEqual(runner.common_dir_calls(), [])

    def test_last_occurrence_of_the_segment_gives_the_root(self):
        path = "/a/.claude/worktrees/em-workflow/x/.claude/worktrees/em-workflow/f/task0001"
        runner = RecordingRunner()
        with self._patched(runner):
            root = self.hook.project_root_for(path)

        self.assertEqual(root, "/a/.claude/worktrees/em-workflow/x")
        self.assertEqual(runner.calls, [])

    def test_segment_at_the_start_of_the_path_is_undetermined_without_fallback(self):
        runner = RecordingRunner()
        with self._patched(runner):
            root = self.hook.project_root_for("/.claude/worktrees/em-workflow/f/task0001")

        self.assertIsNone(root)
        self.assertEqual(runner.calls, [])

    def test_path_without_the_segment_triggers_exactly_one_git_common_dir_call(self):
        runner = RecordingRunner(common_dir=completed("/proj/.git\n"))
        with self._patched(runner):
            root = self.hook.project_root_for(self.CANONICAL_PATH)

        self.assertEqual(root, "/proj")
        self.assertEqual(len(runner.calls), 1)
        command, kwargs = runner.calls[0]
        self.assertEqual(
            command, ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"]
        )
        self.assertEqual(kwargs.get("cwd"), self.CANONICAL_PATH)
        self.assertEqual(kwargs.get("timeout"), self.hook.GIT_TIMEOUT_SECONDS)

    def test_the_fallback_timeout_is_the_existing_bounded_constant(self):
        self.assertIsInstance(self.hook.GIT_TIMEOUT_SECONDS, (int, float))
        self.assertGreater(self.hook.GIT_TIMEOUT_SECONDS, 0)

    def test_cwd_check_without_the_segment_makes_one_common_dir_call(self):
        runner = RecordingRunner(
            common_dir=completed("/proj/.git\n"), toplevel=completed("/proj\n")
        )
        with self._patched(runner):
            result = self.hook.cwd_outside_project_root("/proj", self.CANONICAL_PATH)

        self.assertIsNone(result)
        self.assertEqual(len(runner.common_dir_calls()), 1)

    def test_root_is_the_parent_directory_of_the_normalized_output(self):
        for output in ("/proj/.git", "  /proj/.git/\n", "/proj/./sub/../.git"):
            with self.subTest(output=output):
                runner = RecordingRunner(common_dir=completed(output))
                with self._patched(runner):
                    self.assertEqual(self.hook.project_root_for(self.CANONICAL_PATH), "/proj")

    def test_missing_or_non_string_cwd_skips_the_check_before_any_git_call(self):
        for cwd in (None, "", 5, ["/proj"]):
            with self.subTest(cwd=cwd):
                runner = RecordingRunner()
                with self._patched(runner):
                    result = self.hook.cwd_outside_project_root(cwd, self.CANONICAL_PATH)

                self.assertIsNone(result)
                self.assertEqual(runner.calls, [])


class TestFallbackFailures(unittest.TestCase):
    """AC-5 (TM-1): a fallback call that fails to start, times out, exits
    non-zero or prints only whitespace leaves the project root undetermined
    and the cwd check without a denial. No real timeout is waited for."""

    WORKTREE_PATH = "/proj-store/em-workflow/f/task0001"
    OTHER_TOPLEVEL = "/elsewhere/other-worktree"

    @classmethod
    def setUpClass(cls):
        cls.hook = load_hook_module()
        command = ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"]
        cls.failures = (
            ("fails to start", FileNotFoundError("git: no such directory")),
            ("times out", subprocess.TimeoutExpired(command, 5)),
            ("exits non-zero", completed("/proj/.git\n", returncode=128)),
            ("prints only whitespace", completed("  \n\t\n")),
            ("prints nothing", completed("")),
            ("prints a relative path", completed(".git\n")),
            ("is given an invalid value", ValueError("embedded null byte")),
        )

    def _patched(self, runner):
        return mock.patch.object(self.hook.subprocess, "run", runner)

    def test_each_failure_leaves_the_project_root_undetermined(self):
        for label, outcome in self.failures:
            with self.subTest(failure=label):
                runner = RecordingRunner(common_dir=outcome)
                with self._patched(runner):
                    root = self.hook.project_root_for(self.WORKTREE_PATH)

                self.assertIsNone(root)
                self.assertEqual(len(runner.common_dir_calls()), 1)

    def test_each_failure_yields_no_denial_although_the_cwd_toplevel_resolves(self):
        for label, outcome in self.failures:
            with self.subTest(failure=label):
                runner = RecordingRunner(
                    common_dir=outcome, toplevel=completed(self.OTHER_TOPLEVEL + "\n")
                )
                with self._patched(runner):
                    result = self.hook.cwd_outside_project_root(
                        self.OTHER_TOPLEVEL, self.WORKTREE_PATH
                    )

                self.assertIsNone(result)
                self.assertEqual(len(runner.common_dir_calls()), 1)

    def test_a_resolved_common_dir_with_another_toplevel_is_a_denial(self):
        # Control: the absence of a denial above comes from the undetermined
        # root, not from an unresolvable toplevel.
        runner = RecordingRunner(
            common_dir=completed("/proj/.git\n"),
            toplevel=completed(self.OTHER_TOPLEVEL + "\n"),
        )
        with self._patched(runner):
            result = self.hook.cwd_outside_project_root(self.OTHER_TOPLEVEL, self.WORKTREE_PATH)

        self.assertEqual(result, "/proj")

    def test_the_hook_exits_zero_with_no_output_and_records_the_launch(self):
        for label, outcome in self.failures:
            with self.subTest(failure=label), tempfile.TemporaryDirectory() as tmp:
                worktree_path = os.path.join(os.path.realpath(tmp), TASK_ID)
                runner = RecordingRunner(
                    common_dir=outcome, toplevel=completed(self.OTHER_TOPLEVEL + "\n")
                )
                stdout = io.StringIO()
                stdin = io.StringIO(
                    json.dumps(launch_payload(worktree_path, cwd=self.OTHER_TOPLEVEL))
                )
                with self._patched(runner), \
                        mock.patch.object(sys, "stdin", stdin), \
                        contextlib.redirect_stdout(stdout):
                    code = self.hook.hook_main()

                self.assertEqual(code, 0)
                self.assertEqual(stdout.getvalue(), "")
                self.assertEqual(len(runner.common_dir_calls()), 1)
                self.assertEqual(len(launched_events(worktree_path)), 1)


class TestHookDocstring(unittest.TestCase):
    """AC-6: the module docstring states the segment derivation, the
    git-common-dir fallback and fail-open, and no longer states the old
    outside-layout skip. Every presence and absence assertion is paired with
    a forged-text proof that the search can tell the two outcomes apart."""

    @classmethod
    def setUpClass(cls):
        with open(HOOK_PATH, encoding="utf-8") as fh:
            tree = ast.parse(fh.read(), filename=HOOK_PATH)
        cls.docstring = ast.get_docstring(tree, clean=False)

    def test_the_docstring_was_read_from_the_hook_file(self):
        self.assertIsInstance(self.docstring, str)
        self.assertIn("queue launch guard", self.docstring)

    def test_each_current_statement_is_present(self):
        for statement in (
            DOCSTRING_SEGMENT_STATEMENT,
            DOCSTRING_FALLBACK_STATEMENT,
            DOCSTRING_FAIL_OPEN_STATEMENT,
        ):
            with self.subTest(statement=statement):
                self.assertTrue(contains_normalized(self.docstring, statement))

    def test_each_presence_search_rejects_a_forged_text_without_the_statement(self):
        for statement in (
            DOCSTRING_SEGMENT_STATEMENT,
            DOCSTRING_FALLBACK_STATEMENT,
            DOCSTRING_FAIL_OPEN_STATEMENT,
        ):
            with self.subTest(statement=statement):
                forged = normalized(self.docstring).replace(normalized(statement), "")
                self.assertNotEqual(forged, normalized(self.docstring))
                self.assertFalse(contains_normalized(forged, statement))

    def test_the_presence_search_is_not_defeated_by_line_wrapping(self):
        wrapped = DOCSTRING_FALLBACK_STATEMENT.replace(" the git ", "\n    the git ")
        self.assertNotEqual(wrapped, DOCSTRING_FALLBACK_STATEMENT)
        self.assertTrue(contains_normalized(wrapped, DOCSTRING_FALLBACK_STATEMENT))

    def test_the_outside_layout_skip_statement_is_absent(self):
        self.assertFalse(
            contains_normalized(self.docstring, PRE_CHANGE_OUTSIDE_LAYOUT_STATEMENT)
        )

    def test_the_absence_search_finds_the_statement_in_the_pre_change_excerpt(self):
        self.assertTrue(
            contains_normalized(
                PRE_CHANGE_FAIL_OPEN_EXCERPT, PRE_CHANGE_OUTSIDE_LAYOUT_STATEMENT
            )
        )

    def test_the_absence_search_finds_the_statement_in_a_forged_docstring(self):
        forged = self.docstring + "\n" + PRE_CHANGE_FAIL_OPEN_EXCERPT
        self.assertTrue(contains_normalized(forged, PRE_CHANGE_OUTSIDE_LAYOUT_STATEMENT))


class TestStdlibAndDeterminism(unittest.TestCase):
    """AC-7: only the standard library, symlink fixtures, no timing."""

    def _read(self, path):
        with open(path, encoding="utf-8") as fh:
            return fh.read()

    def test_the_hook_imports_only_standard_library_modules(self):
        imported = imported_top_level_modules(self._read(HOOK_PATH))

        self.assertTrue(imported)
        self.assertEqual(imported - set(sys.stdlib_module_names), set())

    def test_this_module_imports_only_standard_library_modules(self):
        imported = imported_top_level_modules(self._read(THIS_PATH))

        self.assertTrue(imported)
        self.assertEqual(imported - set(sys.stdlib_module_names), set())

    def test_the_import_check_flags_a_third_party_import(self):
        forged = "import json\nimport requests\nfrom yaml import safe_load\n"
        self.assertEqual(
            imported_top_level_modules(forged) - set(sys.stdlib_module_names),
            {"requests", "yaml"},
        )

    def test_this_module_imports_no_other_test_module(self):
        local = {
            name for name in imported_top_level_modules(self._read(THIS_PATH))
            if os.path.exists(os.path.join(os.path.dirname(THIS_PATH), name + ".py"))
        }
        self.assertEqual(local, set())

    def test_this_module_neither_sleeps_nor_imports_a_timing_module(self):
        self.assertEqual(timing_dependencies(self._read(THIS_PATH)), set())

    def test_the_timing_check_flags_a_sleeping_source(self):
        self.assertEqual(
            timing_dependencies("import time\ntime.sleep(1)\n"), {"time", "sleep"}
        )

    def test_each_placement_is_a_symlink_to_a_directory_inside_the_project(self):
        for label, link_relpath, store_name in PLACEMENTS:
            with self.subTest(placement=label), \
                    linked_layout(label, link_relpath, store_name) as layout:
                link = os.path.join(layout.project_root, link_relpath)
                self.assertTrue(os.path.islink(link))
                target = os.path.realpath(link, strict=True)
                self.assertTrue(os.path.isdir(target))
                self.assertTrue(target.startswith(layout.project_root + os.sep))
                self.assertNotIn(SEGMENT, target + "/")
                self.assertNotIn(SEGMENT, layout.task)
                self.assertNotIn(SEGMENT, layout.integration)

    def test_the_fixture_environment_drops_the_repository_selecting_variables(self):
        with mock.patch.dict(os.environ, {"GIT_DIR": "/nonexistent", "GIT_INDEX_FILE": "/x"}):
            env = git_environment()

        for name in REPOSITORY_SELECTING_GIT_VARS:
            self.assertNotIn(name, env)


if __name__ == "__main__":
    unittest.main()
