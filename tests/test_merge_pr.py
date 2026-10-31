"""Tests for em-workflow/scripts/merge-pr.py (task0004 of
feature-docs/unattended-merge: GitHub repository and PR decisions).

Self-contained, per IMPLEMENTATION.md "Tests (NFR5)": every test builds its
own temporary git repository, replaces gh with a stub placed first on PATH
(answering from per-test fixture files and logging every invocation), and
wraps git in a logging shim that delegates to the real git.  Nothing touches
the network or the real ~/.claude.  The script is run as a child process, so
no bytecode cache is written under em-workflow/.

Every test is also an AC-6 test: after each test the gh invocation log, the
git invocation log and the repository's refs are checked against the
operation boundary (read-only gh, explicit repository, no git ref change).
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "em-workflow" / "scripts" / "merge-pr.py"
REAL_GIT = shutil.which("git")

FEATURE = "feat"
BASE = "main"
BRANCH = "em-workflow/%s/integration" % FEATURE
REPO = "acme/widgets"
GITHUB_URL = "https://github.com/acme/widgets.git"
NON_GITHUB_URL = "https://git.example.invalid/acme/widgets.git"

SHA_HEAD = "a" * 40
SHA_OTHER = "b" * 40
SHA_MERGE = "c" * 40

STUB_GH = """#!%(python)s
import json, os, sys, time
d = os.environ["GH_STUB_DIR"]
args = sys.argv[1:]
with open(os.path.join(d, "gh-log.jsonl"), "a") as f:
    f.write(json.dumps(args) + "\\n")


def load(name):
    path = os.path.join(d, name)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return json.load(f)


def emit(fixture):
    if fixture is None:
        sys.stderr.write("stub gh: no fixture for this call\\n")
        sys.exit(1)
    time.sleep(fixture.get("sleep", 0))
    sys.stdout.write(fixture.get("stdout", ""))
    sys.stderr.write(fixture.get("stderr", ""))
    sys.exit(fixture.get("rc", 0))


if args[:2] == ["repo", "view"]:
    rest = args[2:]
    if rest == ["--json", "nameWithOwner"]:
        emit(load("fixture-repo-view-default.json"))
    if len(rest) == 3 and rest[1:] == ["--json", "nameWithOwner"]:
        raw = load("fixture-repo-view-url.json")
        if raw is not None:
            emit(raw)
        mapping = load("urls.json") or {}
        if rest[0] in mapping:
            emit({"stdout": json.dumps({"nameWithOwner": mapping[rest[0]]})})
        sys.stderr.write("stub gh: could not resolve to a GitHub repository\\n")
        sys.exit(1)
elif args[:2] == ["pr", "list"]:
    emit(load("fixture-pr-list.json"))
elif args[:2] == ["pr", "view"]:
    emit(load("fixture-pr-view.json"))
sys.stderr.write("stub gh: unexpected invocation\\n")
sys.exit(99)
"""

SHIM_GIT = """#!%(python)s
import json, os, sys
d = os.environ["GH_STUB_DIR"]
with open(os.path.join(d, "git-log.jsonl"), "a") as f:
    f.write(json.dumps(sys.argv[1:]) + "\\n")
os.execv(%(real_git)r, [%(real_git)r] + sys.argv[1:])
"""

GH_OPTIONS_ALLOWED = {"--repo", "--head", "--base", "--state", "--limit", "--json"}


def pr_entry(
    number=12,
    state="OPEN",
    draft=False,
    head_ref=BRANCH,
    base_ref=BASE,
    head_sha=SHA_HEAD,
    cross=False,
    merge_commit=None,
    url=None,
):
    """One element of `gh pr list --json ...` output."""
    if state == "MERGED" and merge_commit is None:
        merge_commit = SHA_MERGE
    return {
        "number": number,
        "url": url or "https://github.com/%s/pull/%d" % (REPO, number),
        "state": state,
        "isDraft": draft,
        "headRefName": head_ref,
        "baseRefName": base_ref,
        "headRefOid": head_sha,
        "isCrossRepository": cross,
        "mergeCommit": {"oid": merge_commit} if merge_commit else None,
    }


def view_entry(
    number=12,
    state="OPEN",
    draft=False,
    mergeable="MERGEABLE",
    head_sha=SHA_HEAD,
    merge_commit=None,
    url=None,
):
    """The document `gh pr view --json ...` prints."""
    if state == "MERGED" and merge_commit is None:
        merge_commit = SHA_MERGE
    return {
        "number": number,
        "url": url or "https://github.com/%s/pull/%d" % (REPO, number),
        "state": state,
        "isDraft": draft,
        "mergeable": mergeable,
        "headRefOid": head_sha,
        "mergeCommit": {"oid": merge_commit} if merge_commit else None,
    }


def assert_gh_call_is_read_only(testcase, args):
    """AC-6: the only gh shapes the script may use."""
    if args[:2] == ["repo", "view"]:
        rest = args[2:]
        ok = rest == ["--json", "nameWithOwner"] or (
            len(rest) == 3
            and rest[1:] == ["--json", "nameWithOwner"]
            and not rest[0].startswith("-")
        )
        testcase.assertTrue(ok, "unexpected gh repo view shape: %r" % (args,))
        return
    testcase.assertIn(args[:2], (["pr", "list"], ["pr", "view"]), "gh call %r" % (args,))
    options = [a for a in args[2:] if a.startswith("--")]
    for option in options:
        testcase.assertIn(option, GH_OPTIONS_ALLOWED, "gh option in %r" % (args,))
    testcase.assertIn("--repo", args, "gh call without explicit repository: %r" % (args,))
    value = args[args.index("--repo") + 1]
    testcase.assertRegex(value, r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")


def assert_git_call_is_read_only(testcase, args):
    rest = list(args)
    if rest[:1] == ["-C"]:
        rest = rest[2:]
    testcase.assertEqual(rest[:2], ["remote", "get-url"], "git call %r" % (args,))
    testcase.assertEqual(len(rest), 3, "git call %r" % (args,))


class MergePrTestCase(unittest.TestCase):
    """A temporary repository with remotes, a stub gh and a logging git shim."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name).resolve()
        self.stub_dir = self.tmp / "stub"
        self.bin_dir = self.tmp / "bin"
        self.root = self.tmp / "project"
        for d in (self.stub_dir, self.bin_dir, self.root, self.tmp / "home"):
            d.mkdir()

        for name, text in (
            ("gh", STUB_GH % {"python": sys.executable}),
            ("git", SHIM_GIT % {"python": sys.executable, "real_git": REAL_GIT}),
        ):
            path = self.bin_dir / name
            path.write_text(text)
            path.chmod(0o755)

        self.env = dict(os.environ)
        for key in ("GH_REPO", "GH_TOKEN", "GITHUB_TOKEN", "EM_WORKFLOW_MERGE_PR_GH_TIMEOUT"):
            self.env.pop(key, None)
        self.env.update(
            {
                "PATH": str(self.bin_dir) + os.pathsep + os.environ.get("PATH", ""),
                "HOME": str(self.tmp / "home"),
                "GIT_CONFIG_NOSYSTEM": "1",
                "GH_STUB_DIR": str(self.stub_dir),
                "PYTHONDONTWRITEBYTECODE": "1",
            }
        )
        # The real git, used only to build and inspect the fixture repository.
        self.real_env = dict(self.env)
        self.real_env["PATH"] = os.environ.get("PATH", "")

        self.git("init", "-q", "-b", BASE)
        self.git("config", "user.name", "Test")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "commit.gpgsign", "false")
        self.git("commit", "-q", "--allow-empty", "-m", "initial")
        self.git("remote", "add", "origin", GITHUB_URL)
        self.set_url_mapping({GITHUB_URL: REPO})
        self.set_fixture("repo-view-default", stdout={"nameWithOwner": REPO})
        # Taken right before the first script run, after the test has set up
        # its remotes, so that only the script's own effects are compared.
        self.before = None
        self.addCleanup(self.assert_operation_boundary)

    # -- fixture plumbing ------------------------------------------------------

    def git(self, *args):
        proc = subprocess.run(
            [REAL_GIT, "-C", str(self.root)] + list(args),
            env=self.real_env,
            capture_output=True,
            text=True,
            check=True,
        )
        return proc.stdout

    def set_fixture(self, key, stdout="", rc=0, sleep=0, stderr=""):
        if not isinstance(stdout, str):
            stdout = json.dumps(stdout)
        doc = {"stdout": stdout, "rc": rc, "sleep": sleep, "stderr": stderr}
        (self.stub_dir / ("fixture-%s.json" % key)).write_text(json.dumps(doc))

    def clear_fixture(self, key):
        (self.stub_dir / ("fixture-%s.json" % key)).unlink()

    def set_url_mapping(self, mapping):
        (self.stub_dir / "urls.json").write_text(json.dumps(mapping))

    def add_remote(self, name, url):
        self.git("remote", "add", name, url)

    def repo_snapshot(self):
        return {
            "refs": self.git("for-each-ref", "--format=%(refname) %(objectname)"),
            "head": self.git("rev-parse", "HEAD"),
            "branch": self.git("symbolic-ref", "HEAD"),
            "config": self.git("config", "--local", "--list"),
            "status": self.git("status", "--porcelain"),
        }

    def log(self, name):
        path = self.stub_dir / name
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text().splitlines()]

    def gh_log(self):
        return self.log("gh-log.jsonl")

    # -- running the script ------------------------------------------------------

    def run_script(self, *args, env_extra=None, timeout=60):
        if self.before is None:
            self.before = self.repo_snapshot()
        env = dict(self.env)
        env.update(env_extra or {})
        proc = subprocess.run(
            [sys.executable, str(SCRIPT)] + [str(a) for a in args],
            env=env,
            cwd=str(self.tmp),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return proc.returncode, proc.stdout, proc.stderr

    def decide(self, *args, **kwargs):
        rc, out, err = self.run_script(*args, **kwargs)
        self.assertEqual(rc, 0, "exit %d, stderr: %s" % (rc, err))
        self.assertEqual(len(out.splitlines()), 1, "stdout: %r" % out)
        doc = json.loads(out)
        self.assertIsInstance(doc, dict)
        for key in ("outcome", "reason", "detail"):
            self.assertIn(key, doc)
        self.assertIsInstance(doc["detail"], str)
        return doc

    def assert_internal_failure(self, *args, **kwargs):
        rc, out, err = self.run_script(*args, **kwargs)
        self.assertNotIn(rc, (0, 2), "exit %d, stderr: %s" % (rc, err))
        self.assertEqual(out, "", "an internal failure must not emit an outcome")

    def assert_stop(self, doc, reason):
        self.assertEqual(doc["outcome"], "stop", doc)
        self.assertEqual(doc["reason"], reason, doc)

    def repo_cmd(self, remote="origin"):
        return ("repo", "--project-root", self.root, "--remote", remote)

    def resolve_cmd(self, feature=FEATURE, base=BASE, repo=REPO):
        return (
            "resolve", "--project-root", self.root, "--repo", repo,
            "--feature", feature, "--base", base,
        )

    def state_cmd(self, pr=12, head=SHA_HEAD, repo=REPO):
        return (
            "state", "--project-root", self.root, "--repo", repo,
            "--pr", pr, "--head", head,
        )

    # -- AC-6, applied after every test ---------------------------------------------

    def assert_operation_boundary(self):
        for args in self.gh_log():
            assert_gh_call_is_read_only(self, args)
        for args in self.log("git-log.jsonl"):
            assert_git_call_is_read_only(self, args)
        if self.before is not None:
            self.assertEqual(self.repo_snapshot(), self.before, "repository state changed")


# ---------------------------------------------------------------------------------
# AC-1, AC-2: repo
# ---------------------------------------------------------------------------------


class TestRepo(MergePrTestCase):
    def test_ac1_github_remote_returns_github_with_the_name_gh_reports(self):
        doc = self.decide(*self.repo_cmd())
        self.assertEqual(doc["outcome"], "github")
        self.assertEqual(doc["repo"], REPO)
        self.assertIsNone(doc["reason"])
        self.assertEqual(doc["detail"], "")

    def test_ac1_the_remotes_url_is_what_gh_is_asked_to_resolve(self):
        self.decide(*self.repo_cmd())
        self.assertIn(["repo", "view", GITHUB_URL, "--json", "nameWithOwner"], self.gh_log())

    def test_ac1_repo_name_comes_from_gh_not_from_the_url(self):
        old = "https://github.com/old-owner/old-name.git"
        self.git("remote", "set-url", "origin", old)
        self.set_url_mapping({old: REPO})
        self.assertEqual(self.decide(*self.repo_cmd())["repo"], REPO)

    def test_ac1_ssh_style_remote_is_resolved(self):
        url = "git@github.com:acme/widgets.git"
        self.git("remote", "set-url", "origin", url)
        self.set_url_mapping({url: REPO})
        doc = self.decide(*self.repo_cmd())
        self.assertEqual((doc["outcome"], doc["repo"]), ("github", REPO))

    def test_ac1_non_github_remote_stops_remote_not_github(self):
        self.add_remote("elsewhere", NON_GITHUB_URL)
        doc = self.decide(*self.repo_cmd("elsewhere"))
        self.assert_stop(doc, "remote_not_github")
        self.assertNotIn("repo", doc)

    def test_ac1_local_path_remote_is_not_github_and_not_offered_to_gh(self):
        path = str(self.tmp / "bare" / "widgets")
        self.add_remote("local", path)
        self.assert_stop(self.decide(*self.repo_cmd("local")), "remote_not_github")
        self.assertEqual(self.gh_log(), [])

    def test_ac1_file_scheme_remote_is_not_github_and_not_offered_to_gh(self):
        self.add_remote("filer", "file:///srv/git/acme/widgets.git")
        self.assert_stop(self.decide(*self.repo_cmd("filer")), "remote_not_github")
        self.assertEqual(self.gh_log(), [])

    def test_ac1_credentials_in_the_remote_url_never_reach_gh_or_stdout(self):
        self.git("remote", "set-url", "origin", "https://user:s3cret-token@github.com/acme/widgets.git")
        rc, out, _ = self.run_script(*self.repo_cmd())
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out)["outcome"], "github")
        self.assertNotIn("s3cret-token", json.dumps(self.gh_log()))
        self.assertNotIn("s3cret-token", out)

    def test_ac1_a_remote_that_does_not_exist_stops_remote_unresolved(self):
        self.assert_stop(self.decide(*self.repo_cmd("nonexistent")), "remote_unresolved")
        self.assertEqual(self.gh_log(), [])

    def test_ac2_default_repository_that_differs_stops_remote_unresolved_naming_both(self):
        self.set_fixture("repo-view-default", stdout={"nameWithOwner": "fork-owner/widgets"})
        doc = self.decide(*self.repo_cmd())
        self.assert_stop(doc, "remote_unresolved")
        self.assertIn("fork-owner/widgets", doc["detail"])
        self.assertIn(REPO, doc["detail"])
        self.assertNotIn("repo", doc)

    def test_ac2_default_repository_that_cannot_be_determined_stops_remote_unresolved(self):
        self.set_fixture("repo-view-default", rc=1, stderr="no default repository")
        doc = self.decide(*self.repo_cmd())
        self.assert_stop(doc, "remote_unresolved")
        self.assertIn(REPO, doc["detail"])

    def test_ac2_default_repository_missing_from_the_stub_stops_remote_unresolved(self):
        self.clear_fixture("repo-view-default")
        self.assert_stop(self.decide(*self.repo_cmd()), "remote_unresolved")

    def test_ac2_default_repository_comparison_ignores_letter_case(self):
        self.set_fixture("repo-view-default", stdout={"nameWithOwner": "Acme/Widgets"})
        doc = self.decide(*self.repo_cmd())
        self.assertEqual((doc["outcome"], doc["repo"]), ("github", REPO))

    def test_ac2_default_repository_query_names_no_repository(self):
        self.decide(*self.repo_cmd())
        self.assertEqual(self.gh_log().count(["repo", "view", "--json", "nameWithOwner"]), 1)

    def test_ac2_remote_that_gh_cannot_resolve_is_decided_before_the_default_is_compared(self):
        self.add_remote("elsewhere", NON_GITHUB_URL)
        self.set_fixture("repo-view-default", stdout={"nameWithOwner": "fork-owner/widgets"})
        self.assert_stop(self.decide(*self.repo_cmd("elsewhere")), "remote_not_github")


# ---------------------------------------------------------------------------------
# AC-3: resolve
# ---------------------------------------------------------------------------------


class TestResolve(MergePrTestCase):
    def listing(self, *entries):
        self.set_fixture("pr-list", stdout=list(entries))

    def test_ac3_merged_pr_returns_merged_with_number_url_and_merge_commit(self):
        self.listing(pr_entry(number=7, state="MERGED", merge_commit=SHA_MERGE))
        doc = self.decide(*self.resolve_cmd())
        self.assertEqual(doc["outcome"], "merged")
        self.assertIsNone(doc["reason"])
        self.assertEqual(doc["pr_number"], 7)
        self.assertEqual(doc["pr_url"], "https://github.com/%s/pull/7" % REPO)
        self.assertEqual(doc["merge_commit"], SHA_MERGE)

    def test_ac3_a_merged_pr_wins_over_an_open_one(self):
        self.listing(pr_entry(number=9), pr_entry(number=7, state="MERGED"))
        self.assertEqual(self.decide(*self.resolve_cmd())["outcome"], "merged")

    def test_ac3_open_non_draft_pr_returns_open_with_number_url_and_head(self):
        self.listing(pr_entry(number=12, head_sha=SHA_OTHER))
        doc = self.decide(*self.resolve_cmd())
        self.assertEqual(doc["outcome"], "open")
        self.assertIsNone(doc["reason"])
        self.assertEqual(doc["pr_number"], 12)
        self.assertEqual(doc["pr_url"], "https://github.com/%s/pull/12" % REPO)
        self.assertEqual(doc["head"], SHA_OTHER)

    def test_ac3_an_open_non_draft_pr_wins_over_a_draft_and_a_closed_one(self):
        self.listing(
            pr_entry(number=3, state="CLOSED"),
            pr_entry(number=4, draft=True),
            pr_entry(number=5),
        )
        doc = self.decide(*self.resolve_cmd())
        self.assertEqual((doc["outcome"], doc["pr_number"]), ("open", 5))

    def test_ac3_no_pr_returns_none_with_the_create_head_and_base(self):
        self.listing()
        doc = self.decide(*self.resolve_cmd(feature="my-feature", base="release/1.x"))
        self.assertEqual(doc["outcome"], "none")
        self.assertIsNone(doc["reason"])
        self.assertEqual(doc["create_head"], "em-workflow/my-feature/integration")
        self.assertEqual(doc["create_base"], "release/1.x")

    def test_ac3_closed_only_stops_pr_closed(self):
        self.listing(pr_entry(number=3, state="CLOSED"), pr_entry(number=4, state="CLOSED"))
        self.assert_stop(self.decide(*self.resolve_cmd()), "pr_closed")

    def test_ac3_open_draft_stops_pr_draft(self):
        self.listing(pr_entry(number=4, draft=True))
        self.assert_stop(self.decide(*self.resolve_cmd()), "pr_draft")

    def test_ac3_a_draft_stops_even_when_a_closed_pr_also_exists(self):
        self.listing(pr_entry(number=3, state="CLOSED"), pr_entry(number=4, draft=True))
        self.assert_stop(self.decide(*self.resolve_cmd()), "pr_draft")

    def test_ac3_prs_for_another_head_or_base_are_ignored(self):
        self.listing(
            pr_entry(number=3, head_ref="em-workflow/other/integration"),
            pr_entry(number=4, base_ref="develop"),
        )
        self.assertEqual(self.decide(*self.resolve_cmd())["outcome"], "none")

    def test_ac3_a_cross_repository_pr_with_the_same_head_name_is_ignored(self):
        self.listing(pr_entry(number=3, state="MERGED", cross=True))
        self.assertEqual(self.decide(*self.resolve_cmd())["outcome"], "none")

    def test_ac3_the_list_is_requested_for_every_state_of_the_explicit_repository(self):
        self.listing()
        self.decide(*self.resolve_cmd())
        (call,) = self.gh_log()
        self.assertEqual(call[:2], ["pr", "list"])
        for option, value in (
            ("--repo", REPO), ("--head", BRANCH), ("--base", BASE), ("--state", "all"),
        ):
            self.assertEqual(call[call.index(option) + 1], value, option)


# ---------------------------------------------------------------------------------
# AC-4: state
# ---------------------------------------------------------------------------------


class TestState(MergePrTestCase):
    def view(self, **kwargs):
        self.set_fixture("pr-view", stdout=view_entry(**kwargs))

    def test_ac4_open_mergeable_pr_with_the_expected_head_is_ready(self):
        self.view(mergeable="MERGEABLE")
        doc = self.decide(*self.state_cmd())
        self.assertEqual(doc["outcome"], "ready")
        self.assertIsNone(doc["reason"])
        self.assertEqual(doc["pr_url"], "https://github.com/%s/pull/12" % REPO)

    def test_ac4_unknown_mergeability_counts_as_not_conflicting(self):
        self.view(mergeable="UNKNOWN")
        self.assertEqual(self.decide(*self.state_cmd())["outcome"], "ready")

    def test_ac4_closed_pr_stops_pr_closed(self):
        self.view(state="CLOSED")
        self.assert_stop(self.decide(*self.state_cmd()), "pr_closed")

    def test_ac4_merged_pr_returns_merged_with_url_and_merge_commit(self):
        self.view(state="MERGED", merge_commit=SHA_MERGE)
        doc = self.decide(*self.state_cmd())
        self.assertEqual(doc["outcome"], "merged")
        self.assertIsNone(doc["reason"])
        self.assertEqual(doc["pr_url"], "https://github.com/%s/pull/12" % REPO)
        self.assertEqual(doc["merge_commit"], SHA_MERGE)

    def test_ac4_merged_wins_even_when_the_head_differs(self):
        self.view(state="MERGED", head_sha=SHA_OTHER, mergeable="CONFLICTING")
        self.assertEqual(self.decide(*self.state_cmd())["outcome"], "merged")

    def test_ac4_draft_pr_stops_pr_draft(self):
        self.view(draft=True)
        self.assert_stop(self.decide(*self.state_cmd()), "pr_draft")

    def test_ac4_conflicting_pr_stops_pr_conflicting(self):
        self.view(mergeable="CONFLICTING")
        self.assert_stop(self.decide(*self.state_cmd()), "pr_conflicting")

    def test_ac4_head_different_from_the_expected_one_stops_pr_head_moved(self):
        self.view(head_sha=SHA_OTHER)
        doc = self.decide(*self.state_cmd(head=SHA_HEAD))
        self.assert_stop(doc, "pr_head_moved")
        self.assertIn(SHA_OTHER, doc["detail"])
        self.assertIn(SHA_HEAD, doc["detail"])

    def test_ac4_closed_is_decided_before_draft_conflict_and_head(self):
        self.view(state="CLOSED", draft=True, mergeable="CONFLICTING", head_sha=SHA_OTHER)
        self.assert_stop(self.decide(*self.state_cmd()), "pr_closed")

    def test_ac4_draft_is_decided_before_conflict_and_head(self):
        self.view(draft=True, mergeable="CONFLICTING", head_sha=SHA_OTHER)
        self.assert_stop(self.decide(*self.state_cmd()), "pr_draft")

    def test_ac4_conflict_is_decided_before_head(self):
        self.view(mergeable="CONFLICTING", head_sha=SHA_OTHER)
        self.assert_stop(self.decide(*self.state_cmd()), "pr_conflicting")

    def test_ac4_the_pr_is_read_with_the_explicit_repository(self):
        self.view()
        self.decide(*self.state_cmd(pr=12))
        (call,) = self.gh_log()
        self.assertEqual(call[:3], ["pr", "view", "12"])
        self.assertEqual(call[call.index("--repo") + 1], REPO)

    def test_ac4_a_different_pr_number_in_the_answer_is_an_internal_failure(self):
        self.view(number=13)
        self.assert_internal_failure(*self.state_cmd(pr=12))


# ---------------------------------------------------------------------------------
# AC-5: malformed gh output and time limits
# ---------------------------------------------------------------------------------


class TestMalformedOutput(MergePrTestCase):
    def check_cases(self, fixture_key, command, cases):
        for label, stdout in cases:
            with self.subTest(label):
                self.set_fixture(fixture_key, stdout=stdout)
                self.assert_internal_failure(*command)

    def test_ac5_resolve_rejects_malformed_pr_lists(self):
        def bad(**override):
            entry = pr_entry()
            entry.update(override)
            return [entry]

        self.check_cases(
            "pr-list",
            self.resolve_cmd(),
            [
                ("not json", "this is not json"),
                ("empty output", ""),
                ("object instead of array", {"number": 1}),
                ("entry is not an object", [42]),
                ("string PR number", bad(number="abc")),
                ("numeric string PR number", bad(number="12")),
                ("zero PR number", bad(number=0)),
                ("negative PR number", bad(number=-3)),
                ("boolean PR number", bad(number=True)),
                ("fractional PR number", bad(number=1.5)),
                ("short head SHA", bad(headRefOid="abc1234")),
                ("uppercase head SHA", bad(headRefOid="A" * 40)),
                ("http URL", bad(url="http://github.com/acme/widgets/pull/12")),
                ("URL with a command suffix", bad(url="https://github.com/acme/widgets/pull/12; rm -rf x")),
                ("missing URL", bad(url=None)),
                ("unknown state", bad(state="WEIRD")),
                ("string draft flag", bad(isDraft="false")),
                ("string cross-repository flag", bad(isCrossRepository="no")),
                ("short merge commit", bad(state="MERGED", mergeCommit={"oid": "abc123"})),
                ("merged without merge commit", bad(state="MERGED", mergeCommit=None)),
                ("malformed entry after a valid one", [pr_entry(), {"number": "x"}]),
            ],
        )

    def test_ac5_resolve_rejects_a_malformed_entry_even_when_it_would_not_be_chosen(self):
        entries = [pr_entry(number=5), pr_entry(number=4, state="CLOSED", head_sha="short")]
        self.set_fixture("pr-list", stdout=entries)
        self.assert_internal_failure(*self.resolve_cmd())

    def test_ac5_resolve_exiting_non_zero_is_an_internal_failure(self):
        self.set_fixture("pr-list", rc=1, stderr="HTTP 502")
        self.assert_internal_failure(*self.resolve_cmd())

    def test_ac5_state_rejects_malformed_pr_documents(self):
        def bad(**override):
            doc = view_entry()
            doc.update(override)
            return doc

        self.check_cases(
            "pr-view",
            self.state_cmd(),
            [
                ("not json", "<html>"),
                ("empty output", ""),
                ("array instead of object", [view_entry()]),
                ("string PR number", bad(number="abc")),
                ("zero PR number", bad(number=0)),
                ("short head SHA", bad(headRefOid="deadbeef")),
                ("http URL", bad(url="http://github.com/acme/widgets/pull/12")),
                ("ftp URL", bad(url="ftp://github.com/acme/widgets/pull/12")),
                ("unknown state", bad(state="open")),
                ("unknown mergeability", bad(mergeable="MAYBE")),
                ("missing mergeability", bad(mergeable=None)),
                ("string draft flag", bad(isDraft=0)),
                ("short merge commit", bad(state="MERGED", mergeCommit={"oid": "cafe"})),
                ("merged without merge commit", bad(state="MERGED", mergeCommit=None)),
            ],
        )

    def test_ac5_state_exiting_non_zero_is_an_internal_failure(self):
        self.set_fixture("pr-view", rc=1, stderr="could not resolve to a PullRequest")
        self.assert_internal_failure(*self.state_cmd())

    def test_ac5_repo_rejects_malformed_repository_answers(self):
        for label, stdout in [
            ("not json", "acme/widgets"),
            ("empty output", ""),
            ("array", ["acme/widgets"]),
            ("missing name", {"other": 1}),
            ("no slash", {"nameWithOwner": "widgets"}),
            ("too many parts", {"nameWithOwner": "a/b/c"}),
            ("whitespace", {"nameWithOwner": "acme/wid gets"}),
            ("shell metacharacters", {"nameWithOwner": "acme/widgets;id"}),
            ("leading dash", {"nameWithOwner": "acme/-widgets"}),
            ("dot dot", {"nameWithOwner": "acme/.."}),
            ("not a string", {"nameWithOwner": 5}),
        ]:
            with self.subTest("remote answer: " + label):
                self.set_fixture("repo-view-url", stdout=stdout)
                self.assert_internal_failure(*self.repo_cmd())
        self.clear_fixture("repo-view-url")
        for label, stdout in [
            ("not json", "acme/widgets"),
            ("no slash", {"nameWithOwner": "widgets"}),
            ("trailing newline in name", {"nameWithOwner": "acme/widgets\n"}),
        ]:
            with self.subTest("default answer: " + label):
                self.set_fixture("repo-view-default", stdout=stdout)
                self.assert_internal_failure(*self.repo_cmd())

    def test_ac5_a_gh_that_never_answers_ends_within_the_time_limit(self):
        self.set_fixture("pr-list", stdout=[], sleep=60)
        started = time.monotonic()
        rc, out, _ = self.run_script(
            *self.resolve_cmd(),
            env_extra={"EM_WORKFLOW_MERGE_PR_GH_TIMEOUT": "1"},
            timeout=30,
        )
        elapsed = time.monotonic() - started
        self.assertNotIn(rc, (0, 2))
        self.assertEqual(out, "")
        self.assertLess(elapsed, 15, "the call outlived its time limit")

    def test_ac5_the_time_limit_covers_the_state_and_repo_calls_too(self):
        self.set_fixture("pr-view", stdout=view_entry(), sleep=60)
        self.set_fixture("repo-view-default", stdout={"nameWithOwner": REPO}, sleep=60)
        env = {"EM_WORKFLOW_MERGE_PR_GH_TIMEOUT": "1"}
        for command in (self.state_cmd(), self.repo_cmd()):
            started = time.monotonic()
            rc, out, _ = self.run_script(*command, env_extra=env, timeout=30)
            self.assertNotIn(rc, (0, 2), command[0])
            self.assertEqual(out, "", command[0])
            self.assertLess(time.monotonic() - started, 15, command[0])


# ---------------------------------------------------------------------------------
# Argument handling (C1: exit 2 for missing or malformed arguments)
# ---------------------------------------------------------------------------------


class TestArguments(MergePrTestCase):
    def assert_usage_error(self, *args):
        rc, out, err = self.run_script(*args)
        self.assertEqual(rc, 2, args)
        self.assertIn("usage: merge-pr.py", err, "exit 2 must come from argument parsing")
        self.assertEqual(out, "")
        self.assertEqual(self.gh_log(), [])

    def test_no_subcommand_and_unknown_subcommand_are_usage_errors(self):
        self.assert_usage_error()
        self.assert_usage_error("merge", "--project-root", self.root)

    def test_missing_options_are_usage_errors(self):
        self.assert_usage_error("repo", "--project-root", self.root)
        self.assert_usage_error("resolve", "--project-root", self.root, "--repo", REPO)
        self.assert_usage_error("state", "--project-root", self.root, "--repo", REPO, "--pr", 1)

    def test_malformed_values_are_usage_errors(self):
        good = self.resolve_cmd()
        for label, command in [
            ("feature uppercase", self.resolve_cmd(feature="Feat")),
            ("feature leading dash", self.resolve_cmd(feature="-feat")),
            ("feature with slash", self.resolve_cmd(feature="a/b")),
            ("base leading dash", self.resolve_cmd(base="-x")),
            ("base with space", self.resolve_cmd(base="a b")),
            ("base with dot dot", self.resolve_cmd(base="a..b")),
            ("base ending .lock", self.resolve_cmd(base="main.lock")),
            ("repo without owner", self.resolve_cmd(repo="widgets")),
            ("repo with shell characters", self.resolve_cmd(repo="acme/w;id")),
            ("pr zero", self.state_cmd(pr=0)),
            ("pr negative", self.state_cmd(pr="-4")),
            ("pr leading zero", self.state_cmd(pr="012")),
            ("pr not a number", self.state_cmd(pr="abc")),
            ("pr fractional", self.state_cmd(pr="1.5")),
            ("head short", self.state_cmd(head="abc1234")),
            ("head uppercase", self.state_cmd(head="A" * 40)),
            ("remote leading dash", self.repo_cmd(remote="-o")),
            ("remote with space", self.repo_cmd(remote="a b")),
            ("project root missing", ("repo", "--project-root", self.tmp / "nope", "--remote", "origin")),
        ]:
            with self.subTest(label):
                self.assert_usage_error(*command)
        self.assertEqual(good[0], "resolve")


# ---------------------------------------------------------------------------------
# AC-6: operation boundary
# ---------------------------------------------------------------------------------


class TestOperationBoundary(MergePrTestCase):
    def test_ac6_all_subcommands_use_only_read_operations_with_an_explicit_repository(self):
        self.set_fixture("pr-list", stdout=[pr_entry()])
        self.set_fixture("pr-view", stdout=view_entry())
        self.assertEqual(self.decide(*self.repo_cmd())["outcome"], "github")
        self.assertEqual(self.decide(*self.resolve_cmd())["outcome"], "open")
        self.assertEqual(self.decide(*self.state_cmd())["outcome"], "ready")
        log = self.gh_log()
        self.assertEqual(
            [call[:2] for call in log],
            [["repo", "view"], ["repo", "view"], ["pr", "list"], ["pr", "view"]],
        )
        for call in log:
            assert_gh_call_is_read_only(self, call)
        explicit = [call for call in log if call[:2] != ["repo", "view"]]
        self.assertEqual(len(explicit), 2)
        for call in explicit:
            self.assertEqual(call[call.index("--repo") + 1], REPO)
        # Only the default-repository query names no repository at all.
        self.assertEqual(sum(1 for c in log if c == ["repo", "view", "--json", "nameWithOwner"]), 1)

    def test_ac6_git_is_used_only_to_read_the_remote_url(self):
        self.decide(*self.repo_cmd())
        git_calls = self.log("git-log.jsonl")
        self.assertEqual(len(git_calls), 1)
        assert_git_call_is_read_only(self, git_calls[0])

    def test_ac6_resolve_and_state_do_not_use_git_at_all(self):
        self.set_fixture("pr-list", stdout=[])
        self.set_fixture("pr-view", stdout=view_entry())
        self.decide(*self.resolve_cmd())
        self.decide(*self.state_cmd())
        self.assertEqual(self.log("git-log.jsonl"), [])

    def test_ac6_the_boundary_check_itself_rejects_write_shaped_calls(self):
        for args in (
            ["pr", "create", "--repo", REPO],
            ["pr", "merge", "12", "--repo", REPO],
            ["pr", "view", "12"],
            ["pr", "list", "--repo", REPO, "--web"],
            ["pr", "view", "12", "--repo", REPO, "--method", "POST"],
            ["api", "-X", "POST", "repos/acme/widgets/pulls"],
            ["repo", "view", "--web"],
            ["repo", "edit", "--repo", REPO],
        ):
            with self.subTest(args), self.assertRaises(AssertionError):
                assert_gh_call_is_read_only(self, args)
        for args in (
            ["push", "origin", "main"],
            ["-C", "/x", "fetch"],
            ["-C", "/x", "remote", "add", "o", "u"],
            ["update-ref", "refs/heads/x", "HEAD"],
        ):
            with self.subTest(args), self.assertRaises(AssertionError):
                assert_git_call_is_read_only(self, args)

    def test_ac6_the_script_source_names_no_gh_write_verb(self):
        source = SCRIPT.read_text()
        for needle in ('"create"', '"merge"', '"edit"', '"close"', '"comment"', '"api"', "--method"):
            self.assertNotIn(needle, source)


if __name__ == "__main__":
    unittest.main()
