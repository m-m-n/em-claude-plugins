#!/usr/bin/env python3
"""merge-git.py -- git-side decisions of an unattended merge run.

Subcommands (long options only; one JSON object on one stdout line):

  route          --project-root --base
  merged         --project-root --feature --base
  worktree-state --project-root --feature
  integrate      --project-root --feature --base [--remote]
  base-check     --project-root --base [--remote] --integrated-base
                 --redo-count
  main-tree      --project-root --base

Output: `outcome`, `reason` (a closed reason code when `outcome` is `stop`,
otherwise null) and `detail` (fixed text, empty when there is nothing to add),
plus the subcommand-specific keys:

  route          remote
  worktree-state worktree_path
  integrate      integrated_base, head, conflicted_paths
  base-check     current_base

Exit codes: 0 when a decision was produced (stop outcomes included), 2 for
missing or malformed arguments, 1 for an internal failure.

Side effects: only `integrate` (fetch, then merge inside the integration
worktree) and `base-check` (fetch) write anything. The script never pushes,
rebases, resets, force-updates, adds or removes a worktree, bypasses a hook,
or changes the main working tree. Values that come from the repository are
emitted only after validation; free text appears only in `detail`, and
`detail` is fixed text that carries no absolute path.
"""

import argparse
import json
import os
import re
import signal
import subprocess
import sys
import time

FEATURE_RE = re.compile(r"[a-z0-9][a-z0-9-]*")
SHA_RE = re.compile(r"[0-9a-f]{40}")
NAME_CHARS_RE = re.compile(r"[A-Za-z0-9._/-]+")

# One invocation finishes within 600 s; every child process has its own limit
# that is also clamped to what is left of this overall budget.
TOTAL_BUDGET = 570.0
DEFAULT_TIMEOUT = 60.0
FETCH_TIMEOUT = 180.0
MERGE_TIMEOUT = 240.0

WORKTREE_ROOT = os.path.join(".claude", "worktrees", "em-workflow")
GITIGNORE_LINE = ".claude/worktrees/"

# Environment variables that would redirect git to a repository other than the
# one named by --project-root.
REPO_LOCATION_VARS = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_COMMON_DIR",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_PREFIX",
    "GIT_NAMESPACE",
)

# Markers (git-path names) of an operation in progress, other than a merge.
OTHER_OPERATION_MARKERS = (
    ("rebase-merge", "rebase"),
    ("rebase-apply", "rebase"),
    ("CHERRY_PICK_HEAD", "cherry-pick"),
    ("REVERT_HEAD", "revert"),
    ("BISECT_LOG", "bisect"),
    ("sequencer", "sequencer operation"),
)


class Stop(Exception):
    """A decision to stop the run with a closed reason code."""

    def __init__(self, reason, detail):
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


class GitFailure(Exception):
    """An unexpected git failure; reported as the stop reason git_failed."""

    def __init__(self, detail):
        super().__init__(detail)
        self.detail = detail


# --------------------------------------------------------------------------
# Identifier validation
# --------------------------------------------------------------------------


def valid_name(name):
    """A git branch / remote name made only of letters, digits, . _ - /."""
    if not isinstance(name, str) or not name or len(name) > 200:
        return False
    if not NAME_CHARS_RE.fullmatch(name):
        return False
    if name.startswith(("-", "/")) or name.endswith(("/", ".")):
        return False
    if ".." in name or "//" in name:
        return False
    for segment in name.split("/"):
        if segment.startswith(".") or segment.endswith(".lock"):
            return False
    return True


def valid_feature(feature):
    return isinstance(feature, str) and FEATURE_RE.fullmatch(feature) is not None


def valid_sha(sha):
    return isinstance(sha, str) and SHA_RE.fullmatch(sha) is not None


def valid_repo_path(path):
    """A repository-relative path that is safe to report."""
    if not path or path.startswith("/"):
        return False
    if any(ord(ch) < 32 or ord(ch) == 127 for ch in path):
        return False
    return all(part not in ("", ".", "..") for part in path.split("/"))


# --------------------------------------------------------------------------
# git runner
# --------------------------------------------------------------------------


class Git:
    """Runs git child processes with time limits and a scrubbed environment."""

    def __init__(self):
        self.deadline = time.monotonic() + TOTAL_BUDGET
        self.env = {
            key: value
            for key, value in os.environ.items()
            if key not in REPO_LOCATION_VARS
        }
        self.env["GIT_TERMINAL_PROMPT"] = "0"
        self.env["GIT_OPTIONAL_LOCKS"] = "0"
        self.env["LC_ALL"] = "C"

    def run(self, args, cwd, timeout=DEFAULT_TIMEOUT):
        """Return (returncode, stdout, stderr); raise GitFailure on timeout."""
        remaining = self.deadline - time.monotonic()
        if remaining <= 1.0:
            raise GitFailure("the time budget of the script is exhausted")
        command = [
            "git",
            "-c",
            "gc.auto=0",
            "-c",
            "maintenance.auto=false",
            "-C",
            cwd,
        ] + list(args)
        try:
            proc = subprocess.Popen(
                command,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=self.env,
                start_new_session=True,
            )
        except OSError:
            raise GitFailure("git could not be started")
        try:
            out, err = proc.communicate(timeout=min(timeout, remaining))
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except OSError:
                pass
            try:
                proc.communicate(timeout=10)
            except Exception:
                pass
            raise GitFailure("git %s timed out" % (args[0] if args else ""))
        stdout = out.decode("utf-8", errors="replace")
        stderr = err.decode("utf-8", errors="replace")
        if stderr.strip():
            first = stderr.strip().splitlines()[0][:200]
            print("merge-git: git %s: %s" % (args[0] if args else "", first), file=sys.stderr)
        return proc.returncode, stdout, stderr

    def lines(self, args, cwd, timeout=DEFAULT_TIMEOUT):
        rc, out, _ = self.run(args, cwd, timeout)
        if rc != 0:
            raise GitFailure("git %s failed" % args[0])
        return [line for line in out.split("\n") if line]

    def resolve(self, ref, cwd):
        """Commit SHA of `ref`, or None when it does not resolve to a commit."""
        rc, out, _ = self.run(
            ["rev-parse", "--verify", "--quiet", ref + "^{commit}"], cwd
        )
        if rc == 1:
            return None
        if rc != 0:
            raise GitFailure("git rev-parse failed")
        sha = out.strip()
        if not valid_sha(sha):
            raise GitFailure("git rev-parse returned an unexpected value")
        return sha

    def is_ancestor(self, ancestor, descendant, cwd):
        rc, _, _ = self.run(["merge-base", "--is-ancestor", ancestor, descendant], cwd)
        if rc == 0:
            return True
        if rc == 1:
            return False
        raise GitFailure("git merge-base failed")


# --------------------------------------------------------------------------
# Shared helpers
# --------------------------------------------------------------------------


def integration_branch(feature):
    return "em-workflow/%s/integration" % feature


def expected_worktree_path(project_root, feature):
    return os.path.join(
        os.path.abspath(project_root), WORKTREE_ROOT, feature, "integration"
    )


def same_path(left, right):
    return os.path.realpath(left) == os.path.realpath(right)


def list_worktrees(git, project_root):
    rc, out, _ = git.run(["worktree", "list", "--porcelain"], project_root)
    if rc != 0:
        raise GitFailure("git worktree list failed")
    entries = []
    current = None
    for line in out.split("\n"):
        if line.startswith("worktree "):
            current = {"path": line[len("worktree "):]}
            entries.append(current)
        elif line == "":
            current = None
        elif current is None:
            continue
        elif line.startswith("HEAD "):
            current["head"] = line[len("HEAD "):]
        elif line.startswith("branch "):
            current["branch"] = line[len("branch "):]
        elif line == "detached":
            current["detached"] = True
        elif line == "bare":
            current["bare"] = True
    return entries


def git_path(git, cwd, names):
    """Absolute paths of git-path `names` for the repository at `cwd`."""
    args = ["rev-parse"]
    for name in names:
        args += ["--git-path", name]
    rc, out, _ = git.run(args, cwd)
    paths = [line for line in out.split("\n") if line]
    if rc != 0 or len(paths) != len(names):
        raise GitFailure("git rev-parse --git-path failed")
    return [p if os.path.isabs(p) else os.path.join(cwd, p) for p in paths]


def other_operation(git, cwd):
    """Name of an in-progress operation other than a merge, or None."""
    paths = git_path(git, cwd, [marker for marker, _ in OTHER_OPERATION_MARKERS])
    for path, (_, label) in zip(paths, OTHER_OPERATION_MARKERS):
        if os.path.lexists(path):
            return label
    return None


def merge_in_progress(git, cwd):
    return os.path.lexists(git_path(git, cwd, ["MERGE_HEAD"])[0])


def branch_label(ref):
    """`refs/heads/<name>` reduced to the name when it is a safe name."""
    if isinstance(ref, str) and ref.startswith("refs/heads/"):
        name = ref[len("refs/heads/"):]
        if valid_name(name):
            return name
    return None


# --------------------------------------------------------------------------
# route (FR6)
# --------------------------------------------------------------------------


def cmd_route(git, args, result):
    root = args.project_root
    base = args.base
    if not valid_name(base):
        raise Stop("base_branch_invalid", "the base branch name is not a safe branch name")
    remotes = git.lines(["remote"], root)
    if not remotes:
        if git.resolve("refs/heads/" + base, root) is None:
            raise Stop(
                "base_branch_invalid",
                "no remote exists and the base branch is absent locally",
            )
        result["outcome"] = "local"
        return
    chosen = None
    rc, out, _ = git.run(["config", "--get", "branch.%s.remote" % base], root)
    if rc not in (0, 1):
        raise GitFailure("git config failed")
    upstream = out.strip() if rc == 0 else ""
    if upstream and upstream != "." and upstream in remotes:
        chosen = upstream
    elif len(remotes) == 1:
        chosen = remotes[0]
    if chosen is None:
        raise Stop(
            "remote_unresolved",
            "several remotes exist and the base branch has no upstream remote",
        )
    if not valid_name(chosen):
        raise Stop("remote_unresolved", "the chosen remote name is not a safe name")
    result["outcome"] = "remote"
    result["remote"] = chosen


# --------------------------------------------------------------------------
# merged (FR7, local route)
# --------------------------------------------------------------------------


def cmd_merged(git, args, result):
    root = args.project_root
    base_tip = git.resolve("refs/heads/" + args.base, root)
    if base_tip is None:
        raise Stop("base_branch_invalid", "the base branch is absent locally")
    branch = integration_branch(args.feature)
    tip = git.resolve("refs/heads/" + branch, root)
    if tip is None:
        raise Stop("integration_branch_missing", "the integration branch does not exist")
    result["outcome"] = "merged" if git.is_ancestor(tip, base_tip, root) else "not_merged"


# --------------------------------------------------------------------------
# worktree-state (FR3, D4)
# --------------------------------------------------------------------------


def worktree_state(git, project_root, feature):
    """Return the state token; raise Stop(worktree_not_clean) otherwise."""
    branch_ref = "refs/heads/" + integration_branch(feature)
    path = expected_worktree_path(project_root, feature)
    entries = list_worktrees(git, project_root)
    matches = [e for e in entries if same_path(e["path"], path)]
    exists = os.path.lexists(path)

    if not matches:
        if exists:
            raise Stop(
                "worktree_not_clean",
                "the integration worktree path exists but is not a registered worktree",
            )
        if any(e.get("branch") == branch_ref for e in entries):
            raise Stop(
                "worktree_not_clean",
                "the integration branch is checked out in another worktree",
            )
        return "absent"

    entry = matches[0]
    if os.path.islink(path) or not os.path.isdir(path):
        raise Stop(
            "worktree_not_clean",
            "the integration worktree is registered but its directory is missing",
        )
    if entry.get("bare"):
        raise Stop("worktree_not_clean", "the integration worktree entry is a bare repository")
    if entry.get("detached"):
        raise Stop("worktree_not_clean", "the integration worktree has a detached HEAD")
    if entry.get("branch") != branch_ref:
        label = branch_label(entry.get("branch"))
        suffix = " (%s)" % label if label else ""
        raise Stop(
            "worktree_not_clean",
            "the integration worktree has another branch checked out" + suffix,
        )
    # Never run git inside a directory that is not the registered worktree
    # itself: from there git would silently report the enclosing repository.
    rc, out, _ = git.run(["rev-parse", "--show-toplevel"], path)
    if rc != 0 or not same_path(out.strip(), path):
        raise Stop(
            "worktree_not_clean",
            "the integration worktree directory is not the registered worktree",
        )
    operation = other_operation(git, path)
    if operation is not None:
        raise Stop(
            "worktree_not_clean",
            "the integration worktree has a %s in progress" % operation,
        )
    if merge_in_progress(git, path):
        return "merge_in_progress"
    rc, out, _ = git.run(["status", "--porcelain=v1", "--untracked-files=no"], path)
    if rc != 0:
        raise GitFailure("git status failed")
    if out.strip():
        raise Stop(
            "worktree_not_clean",
            "the integration worktree has uncommitted changes to tracked files",
        )
    return "clean"


def cmd_worktree_state(git, args, result):
    result["worktree_path"] = expected_worktree_path(args.project_root, args.feature)
    result["outcome"] = worktree_state(git, args.project_root, args.feature)


# --------------------------------------------------------------------------
# integrate (FR11)
# --------------------------------------------------------------------------


def fetch_base(git, cwd, remote, base):
    """Fetch base_branch from `remote` and return the fetched tip."""
    destination = "refs/remotes/%s/%s" % (remote, base)
    rc, _, _ = git.run(
        [
            "fetch",
            "--no-tags",
            "--no-recurse-submodules",
            remote,
            "refs/heads/%s:%s" % (base, destination),
        ],
        cwd,
        FETCH_TIMEOUT,
    )
    if rc != 0:
        raise GitFailure("the fetch of the base branch from the remote failed")
    tip = git.resolve(destination, cwd)
    if tip is None:
        raise GitFailure("the fetched base branch tip cannot be resolved")
    return tip


def unmerged_paths(git, cwd):
    rc, out, _ = git.run(["diff", "--name-only", "--diff-filter=U", "-z"], cwd)
    if rc != 0:
        raise GitFailure("git diff failed")
    return sorted({p for p in out.split("\0") if p})


def cmd_integrate(git, args, result):
    root = args.project_root
    state = worktree_state(git, root, args.feature)
    if state != "clean":
        raise Stop(
            "git_failed",
            "the integration worktree state is %s, expected clean" % state,
        )
    worktree = expected_worktree_path(root, args.feature)
    branch = integration_branch(args.feature)
    old_tip = git.resolve("HEAD", worktree)
    if old_tip is None or old_tip != git.resolve("refs/heads/" + branch, worktree):
        raise GitFailure("the integration worktree HEAD is not the integration branch tip")
    result["head"] = old_tip

    if args.remote:
        base_tip = fetch_base(git, worktree, args.remote, args.base)
    else:
        base_tip = git.resolve("refs/heads/" + args.base, worktree)
        if base_tip is None:
            raise GitFailure("the base branch is absent locally")
    result["integrated_base"] = base_tip

    if git.is_ancestor(base_tip, old_tip, worktree):
        result["outcome"] = "up_to_date"
        return

    message = "Merge base branch %s into %s" % (args.base, branch)
    rc, _, _ = git.run(
        ["merge", "--no-ff", "--no-edit", "-m", message, base_tip],
        worktree,
        MERGE_TIMEOUT,
    )
    if rc == 0:
        new_tip = git.resolve("HEAD", worktree)
        if new_tip is None:
            raise GitFailure("the merge result cannot be resolved")
        if new_tip == old_tip:
            result["outcome"] = "up_to_date"
            return
        rc, out, _ = git.run(["rev-list", "--parents", "-n", "1", new_tip], worktree)
        parents = out.split()
        if rc != 0 or parents != [new_tip, old_tip, base_tip]:
            raise GitFailure("the merge result does not have the expected parents")
        result["head"] = new_tip
        result["outcome"] = "merged_clean"
        return

    paths = unmerged_paths(git, worktree)
    in_progress = merge_in_progress(git, worktree)
    if paths and in_progress:
        safe = [p for p in paths if valid_repo_path(p)]
        result["conflicted_paths"] = safe
        if git.resolve("HEAD", worktree) != old_tip:
            raise GitFailure("the integration branch tip changed during a conflicting merge")
        result["outcome"] = "conflict"
        if len(safe) != len(paths):
            result["detail"] = "%d conflicted path(s) with unsafe names are not listed" % (
                len(paths) - len(safe)
            )
        return
    suffix = "; a merge is left in progress" if in_progress else ""
    raise GitFailure("the merge failed without a conflict" + suffix)


# --------------------------------------------------------------------------
# base-check (FR16, D7)
# --------------------------------------------------------------------------


def cmd_base_check(git, args, result):
    root = args.project_root
    if args.remote:
        tip = fetch_base(git, root, args.remote, args.base)
    else:
        tip = git.resolve("refs/heads/" + args.base, root)
        if tip is None:
            raise GitFailure("the base branch is absent locally")
    result["current_base"] = tip
    if tip == args.integrated_base:
        result["outcome"] = "unchanged"
        return
    if args.redo_count >= 3:
        raise Stop("base_moving", "the base branch moved again after 3 redos")
    result["outcome"] = "redo"


# --------------------------------------------------------------------------
# main-tree (FR18)
# --------------------------------------------------------------------------


def gitignore_exception_applies(git, root, xy):
    """True when the uncommitted .gitignore change is only the worktrees line."""
    if any(ch not in " MA?" for ch in xy):
        return False
    path = os.path.join(root, ".gitignore")
    if os.path.islink(path) or not os.path.isfile(path):
        return False
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            current = handle.read().splitlines()
    except OSError:
        return False
    rc, out, _ = git.run(["ls-tree", "HEAD", "--", ".gitignore"], root)
    if rc != 0:
        raise GitFailure("git ls-tree failed")
    committed = []
    if out.strip():
        rc, blob, _ = git.run(["cat-file", "blob", "HEAD:.gitignore"], root)
        if rc != 0:
            raise GitFailure("git cat-file failed")
        committed = blob.splitlines()
    if GITIGNORE_LINE in committed:
        return False
    for index, line in enumerate(current):
        if line == GITIGNORE_LINE and current[:index] + current[index + 1:] == committed:
            return True
    return False


def status_entries(out):
    """Parse `status --porcelain=v1 -z` into (xy, path) pairs."""
    tokens = out.split("\0")
    entries = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        index += 1
        if len(token) < 4:
            continue
        xy, path = token[:2], token[3:]
        if "R" in xy or "C" in xy:
            index += 1  # the original path of a rename / copy
        entries.append((xy, path))
    return entries


def cmd_main_tree(git, args, result):
    root = args.project_root
    entries = list_worktrees(git, root)
    if not entries or not same_path(entries[0]["path"], root) or entries[0].get("bare"):
        raise Stop(
            "main_tree_not_ready",
            "the project root is not the main working tree",
        )
    rc, out, _ = git.run(["symbolic-ref", "-q", "HEAD"], root)
    if rc == 1:
        raise Stop("main_tree_not_ready", "the main working tree has a detached HEAD")
    if rc != 0:
        raise GitFailure("git symbolic-ref failed")
    if out.strip() != "refs/heads/" + args.base:
        raise Stop(
            "main_tree_not_ready",
            "the main working tree is on a branch other than the base branch",
        )
    if git.resolve("HEAD", root) is None:
        raise Stop("main_tree_not_ready", "the base branch has no commits")
    operation = other_operation(git, root)
    if operation is None and merge_in_progress(git, root):
        operation = "merge"
    if operation is not None:
        raise Stop(
            "main_tree_not_ready",
            "the main working tree has a %s in progress" % operation,
        )
    rc, out, _ = git.run(["status", "--porcelain=v1", "-z", "--untracked-files=all"], root)
    if rc != 0:
        raise GitFailure("git status failed")
    tracked = untracked = False
    for xy, path in status_entries(out):
        if path == ".gitignore" and gitignore_exception_applies(git, root, xy):
            continue
        if xy == "??":
            untracked = True
        else:
            tracked = True
    if tracked:
        raise Stop(
            "main_tree_not_ready",
            "the main working tree has uncommitted changes to tracked files",
        )
    if untracked:
        raise Stop("main_tree_not_ready", "the main working tree has untracked files")
    result["outcome"] = "ready"


# --------------------------------------------------------------------------
# Command line
# --------------------------------------------------------------------------

HANDLERS = {
    "route": cmd_route,
    "merged": cmd_merged,
    "worktree-state": cmd_worktree_state,
    "integrate": cmd_integrate,
    "base-check": cmd_base_check,
    "main-tree": cmd_main_tree,
}

EXTRA_DEFAULTS = {
    "route": {"remote": None},
    "merged": {},
    "worktree-state": {"worktree_path": None},
    "integrate": {"integrated_base": None, "head": None, "conflicted_paths": []},
    "base-check": {"current_base": None},
    "main-tree": {},
}


def build_parser():
    parser = argparse.ArgumentParser(prog="merge-git.py", allow_abbrev=False)
    sub = parser.add_subparsers(dest="command", required=True)

    def add(name, feature=False, base=False, remote=False, check=False):
        p = sub.add_parser(name, allow_abbrev=False)
        p.add_argument("--project-root", required=True)
        if feature:
            p.add_argument("--feature", required=True)
        if base:
            p.add_argument("--base", required=True)
        if remote:
            p.add_argument("--remote")
        if check:
            p.add_argument("--integrated-base", required=True)
            p.add_argument("--redo-count", required=True, type=int)
        return p

    add("route", base=True)
    add("merged", feature=True, base=True)
    add("worktree-state", feature=True)
    add("integrate", feature=True, base=True, remote=True)
    add("base-check", base=True, remote=True, check=True)
    add("main-tree", base=True)
    return parser


def validate_arguments(parser, args):
    if not os.path.isdir(args.project_root):
        parser.error("--project-root is not a directory")
    if hasattr(args, "feature") and not valid_feature(args.feature):
        parser.error("--feature is not a valid feature name")
    # route reports an unsafe base as a stop; every other subcommand rejects it.
    if hasattr(args, "base") and args.command != "route" and not valid_name(args.base):
        parser.error("--base is not a valid branch name")
    if getattr(args, "remote", None) is not None and not valid_name(args.remote):
        parser.error("--remote is not a valid remote name")
    if hasattr(args, "integrated_base") and not valid_sha(args.integrated_base):
        parser.error("--integrated-base is not a 40-character lowercase hexadecimal SHA")
    if hasattr(args, "redo_count") and args.redo_count not in (0, 1, 2, 3):
        parser.error("--redo-count must be 0, 1, 2 or 3")


def main(argv=None):
    parser = build_parser()
    args = parser.parse_args(argv)
    validate_arguments(parser, args)
    args.project_root = os.path.abspath(args.project_root)

    result = {"outcome": None, "reason": None, "detail": ""}
    result.update(EXTRA_DEFAULTS[args.command])
    git = Git()
    try:
        HANDLERS[args.command](git, args, result)
    except Stop as stop:
        result["outcome"] = "stop"
        result["reason"] = stop.reason
        result["detail"] = stop.detail
    except GitFailure as failure:
        result["outcome"] = "stop"
        result["reason"] = "git_failed"
        result["detail"] = failure.detail
    sys.stdout.write(json.dumps(result) + "\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except BaseException as error:  # internal failure: no decision was produced
        print("merge-git: internal error: %s" % type(error).__name__, file=sys.stderr)
        sys.exit(1)
