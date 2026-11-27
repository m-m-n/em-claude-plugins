#!/usr/bin/env python3
"""cleanup-task.py -- remove one merged task's worktree and branch, without force.

Usage (long options only, each exactly once, nothing else on the command line):

  cleanup-task.py --integration-worktree PATH --feature FEATURE --task TASK

  --integration-worktree  Absolute path of the feature's integration worktree,
                          <project root>/.claude/worktrees/em-workflow/<feature>/integration
  --feature               Feature name, whole-string match of [a-z0-9][a-z0-9-]*
  --task                  Task ID, whole-string match of task[0-9]+

Targets: the task worktree (the directory named after the task, next to the
integration worktree) and the task branch em-workflow/<feature>/<task>.

Output (exit 0 only): one line holding one JSON object

  {"feature": ..., "task": ...,
   "worktree": {"result": removed|absent|kept, "reason": null|text},
   "branch":   {"name": ..., "result": removed|absent|kept|skipped,
                "reason": null|text}}

  removed  removed by this run
  absent   already gone: the worktree is not in git's worktree registration
           list, or the exact ref refs/heads/<branch> does not resolve
  kept     the non-forced removal or deletion was refused and the target
           remains; `reason` is git's own message
  skipped  branch only: the worktree removal was refused, so the branch
           deletion was not attempted; `reason` is fixed text

`branch.result` is `skipped` exactly when `worktree.result` is `kept`.

Exit status: 0 when a result was produced (kept and skipped included); 2 for
invalid input, before any git command ran, with empty standard output; 1 for an
internal error (for example the worktree listing failing), with empty standard
output. Diagnostics go to standard error only.

git: every git child process runs with the integration worktree as its
repository location, so neither the caller's working directory nor its branch
affects the outcome. The only git operations are the worktree registration
list, a non-forced worktree removal, exact ref resolution, a read-only
ancestry check (`merge-base --is-ancestor`) of the task branch against the
integration branch, and a non-forced `branch -d`. The script never forces a removal or a deletion, never prunes
worktree records, never retries, and reads no file other than what git itself
reads.
"""

import json
import os
import re
import signal
import subprocess
import sys
import unicodedata

FEATURE_RE = re.compile(r"[a-z0-9][a-z0-9-]*")
TASK_RE = re.compile(r"task[0-9]+")

OPTIONS = ("--integration-worktree", "--feature", "--task")

# The last five segments of the integration worktree path.
WORKTREE_TAIL = (".claude", "worktrees", "em-workflow")
INTEGRATION_SEGMENT = "integration"

# Environment variables that would redirect git to a repository other than the
# one the integration worktree belongs to (the set merge-git.py drops).
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

# Time limits of the git child processes, in seconds.
LIST_TIMEOUT = 60.0
REMOVE_TIMEOUT = 300.0
REF_TIMEOUT = 60.0
DELETE_TIMEOUT = 60.0

SKIPPED_REASON = "the branch deletion was not attempted because the worktree removal was refused"


class InvalidInput(Exception):
    """The command line or one of its values broke the input rules."""


class InternalError(Exception):
    """An unexpected git failure (anything other than a reported refusal)."""


# --------------------------------------------------------------------------
# Input validation
# --------------------------------------------------------------------------


def parse_options(argv):
    """Map each of the three long options to its value; each exactly once."""
    values = {}
    i = 0
    while i < len(argv):
        name, equals, attached = argv[i].partition("=")
        if name not in OPTIONS:
            raise InvalidInput("unknown option or positional argument")
        if name in values:
            raise InvalidInput("repeated option %s" % name)
        if equals:
            value = attached
            i += 1
        else:
            if i + 1 >= len(argv):
                raise InvalidInput("option %s has no value" % name)
            value = argv[i + 1]
            i += 2
        if value.startswith("-"):
            raise InvalidInput("the value of %s starts with a hyphen" % name)
        values[name] = value
    for name in OPTIONS:
        if name not in values:
            raise InvalidInput("missing option %s" % name)
    return values


def has_control_character(text):
    return any(unicodedata.category(ch) == "Cc" for ch in text)


def validate_integration_worktree(path, feature):
    """Shape check of the integration worktree path; it must be an existing directory."""
    if not path.startswith("/"):
        raise InvalidInput("--integration-worktree is not an absolute path")
    if has_control_character(path):
        raise InvalidInput("--integration-worktree holds a control character")
    segments = path.split("/")[1:]
    if any(segment in ("", ".", "..") for segment in segments):
        raise InvalidInput("--integration-worktree has an empty, '.' or '..' segment")
    expected = WORKTREE_TAIL + (feature, INTEGRATION_SEGMENT)
    if tuple(segments[-len(expected):]) != expected:
        raise InvalidInput("--integration-worktree does not end in the integration worktree location of the feature")
    if not os.path.isdir(path):
        raise InvalidInput("--integration-worktree is not an existing directory")


def validate(argv):
    """Return (integration worktree, feature, task); raise InvalidInput."""
    values = parse_options(argv)
    feature = values["--feature"]
    task = values["--task"]
    if FEATURE_RE.fullmatch(feature) is None:
        raise InvalidInput("--feature is not a feature name")
    if TASK_RE.fullmatch(task) is None:
        raise InvalidInput("--task is not a task ID")
    integration_worktree = values["--integration-worktree"]
    validate_integration_worktree(integration_worktree, feature)
    return integration_worktree, feature, task


# --------------------------------------------------------------------------
# git runner
# --------------------------------------------------------------------------


class Git:
    """Runs git with the integration worktree as its repository location."""

    def __init__(self, integration_worktree):
        self.location = integration_worktree
        self.env = {
            key: value
            for key, value in os.environ.items()
            if key not in REPO_LOCATION_VARS
        }
        self.env["GIT_TERMINAL_PROMPT"] = "0"
        self.env["LC_ALL"] = "C"

    def run(self, args, timeout):
        """Return (returncode, stdout, stderr); raise InternalError on a start failure or a timeout."""
        command = ["git", "-C", self.location] + list(args)
        try:
            proc = subprocess.Popen(
                command,
                cwd=self.location,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=self.env,
                start_new_session=True,
            )
        except OSError:
            raise InternalError("git could not be started")
        try:
            out, err = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except OSError:
                pass
            try:
                proc.communicate(timeout=10)
            except Exception:
                pass
            raise InternalError("git %s timed out" % args[0])
        return (
            proc.returncode,
            out.decode("utf-8", errors="replace"),
            err.decode("utf-8", errors="replace"),
        )


def refusal_text(operation, returncode, stderr):
    """git's own message, trimmed; the failed operation and its status when git said nothing."""
    text = stderr.strip()
    if text:
        return text
    return "%s failed with exit status %d" % (operation, returncode)


# --------------------------------------------------------------------------
# Cleanup
# --------------------------------------------------------------------------


def registered_worktree_paths(git):
    """Paths of every entry of git's worktree registration list."""
    rc, out, err = git.run(["worktree", "list", "--porcelain"], LIST_TIMEOUT)
    if rc != 0:
        raise InternalError(refusal_text("git worktree list", rc, err))
    return [
        line[len("worktree "):]
        for line in out.split("\n")
        if line.startswith("worktree ")
    ]


def is_registered(git, worktree_path):
    """True when the registration list holds the path (symbolic links resolved on both sides).

    An entry whose directory no longer exists still matches by its registered
    path.
    """
    wanted = normalize_leaf(worktree_path)
    return any(normalize_leaf(path) == wanted for path in registered_worktree_paths(git))


def normalize_leaf(path):
    """Resolve symbolic links in the parent directory only; the last name is kept as is."""
    parent, name = os.path.split(os.path.abspath(path))
    return os.path.join(os.path.realpath(parent), name)


def branch_exists(git, ref):
    """True when the exact ref resolves (a full ref name is looked up as that name only)."""
    rc, _, err = git.run(["show-ref", "--verify", "--quiet", "--", ref], REF_TIMEOUT)
    if rc == 0:
        return True
    if rc == 1:
        return False
    raise InternalError(refusal_text("git show-ref", rc, err))


def cleanup(integration_worktree, feature, task):
    git = Git(integration_worktree)
    task_worktree = os.path.join(os.path.dirname(integration_worktree), task)
    branch = "em-workflow/%s/%s" % (feature, task)
    ref = "refs/heads/%s" % branch

    worktree = {"result": "absent", "reason": None}
    branch_result = {"name": branch, "result": "absent", "reason": None}

    task_worktree = normalize_leaf(task_worktree)
    if os.path.islink(task_worktree):
        worktree = {
            "result": "kept",
            "reason": "the task worktree path is a symbolic link",
        }
        branch_result = {"name": branch, "result": "skipped", "reason": SKIPPED_REASON}
        return result_object(feature, task, worktree, branch_result)

    if is_registered(git, task_worktree):
        rc, _, err = git.run(["worktree", "remove", task_worktree], REMOVE_TIMEOUT)
        if rc == 0:
            worktree = {"result": "removed", "reason": None}
        else:
            worktree = {
                "result": "kept",
                "reason": refusal_text("git worktree remove", rc, err),
            }
            branch_result = {"name": branch, "result": "skipped", "reason": SKIPPED_REASON}
            return result_object(feature, task, worktree, branch_result)

    if branch_exists(git, ref):
        integration_ref = "refs/heads/em-workflow/%s/integration" % feature
        rc, out, err = git.run(["rev-parse", "--verify", ref], REF_TIMEOUT)
        if rc != 0:
            raise InternalError(refusal_text("git rev-parse", rc, err))
        checked_tip = out.strip()
        rc, _, err = git.run(
            ["merge-base", "--is-ancestor", checked_tip, integration_ref], REF_TIMEOUT
        )
        if rc == 1:
            branch_result = {
                "name": branch,
                "result": "kept",
                "reason": "the task branch is not merged into the integration branch",
            }
            return result_object(feature, task, worktree, branch_result)
        if rc != 0:
            raise InternalError(refusal_text("git merge-base", rc, err))
        rc, out, err = git.run(["rev-parse", "--verify", ref], REF_TIMEOUT)
        if rc != 0 or out.strip() != checked_tip:
            branch_result = {
                "name": branch,
                "result": "kept",
                "reason": "the task branch changed after the merge check",
            }
            return result_object(feature, task, worktree, branch_result)
        rc, _, err = git.run(["branch", "-d", branch], DELETE_TIMEOUT)
        if rc == 0:
            branch_result = {"name": branch, "result": "removed", "reason": None}
        else:
            branch_result = {
                "name": branch,
                "result": "kept",
                "reason": refusal_text("git branch -d", rc, err),
            }
    return result_object(feature, task, worktree, branch_result)


def result_object(feature, task, worktree, branch):
    return {"feature": feature, "task": task, "worktree": worktree, "branch": branch}


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------


def main(argv):
    try:
        integration_worktree, feature, task = validate(argv)
    except InvalidInput as exc:
        print("cleanup-task: invalid input: %s" % exc, file=sys.stderr)
        return 2
    try:
        result = cleanup(integration_worktree, feature, task)
    except InternalError as exc:
        print("cleanup-task: internal error: %s" % exc, file=sys.stderr)
        return 1
    except Exception as exc:
        print("cleanup-task: internal error: %s" % type(exc).__name__, file=sys.stderr)
        return 1
    sys.stdout.write(json.dumps(result) + "\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
