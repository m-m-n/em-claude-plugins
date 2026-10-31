#!/usr/bin/env python3
"""GitHub repository and pull-request decisions for the unattended merge
(em-workflow plugin, task0004 of feature-docs/unattended-merge; FR6, FR7,
FR8, FR9, FR22, NFR3, NFR4, NFR5).

Three read-only subcommands; each prints exactly ONE JSON object on ONE
stdout line.  Common keys: `outcome`, `reason` (a reason code when `outcome`
is `stop`, otherwise null), `detail` (string, empty when there is nothing to
add).  Diagnostics go to stderr only.

  repo     --project-root P --remote R
      Resolve remote R's URL to a GitHub repository through gh, then confirm
      that gh's own default repository for the project is the same one.
      outcome `github` (+ `repo` = owner/name)
      stop `remote_not_github`  gh cannot resolve the remote's URL
      stop `remote_unresolved`  the remote does not exist, or gh's default
                                repository cannot be determined or differs
                                (both names in `detail` when known)

  resolve  --project-root P --repo O/N --feature F --base B
      List the PRs (every state) whose head is `em-workflow/F/integration`
      and whose base is B, ignoring cross-repository (fork) PRs.
      outcome `merged` (+ `pr_number`, `pr_url`, `merge_commit`)   any merged PR
      outcome `open`   (+ `pr_number`, `pr_url`, `head`)           open, non-draft
      outcome `none`   (+ `create_head`, `create_base`)            no PR at all
      stop `pr_draft`   only open draft PRs
      stop `pr_closed`  only closed, unmerged PRs
      Precedence: merged > open non-draft > open draft > closed.  When
      several PRs share a class, the highest PR number is used.  `head` is
      the PR's head commit SHA.

  state    --project-root P --repo O/N --pr N --head SHA
      Read the PR's state right before the merge.
      outcome `merged` (+ `pr_url`, `merge_commit`)
      outcome `ready`  (+ `pr_url`, `head`)
      stop `pr_closed` / `pr_draft` / `pr_conflicting` / `pr_head_moved`
      Checked in that order, after `merged`.  Mergeability MERGEABLE or
      UNKNOWN counts as not conflicting.  `pr_head_moved`: the PR's head SHA
      differs from --head.

Exit codes: 0 when a decision was produced (stop outcomes included); 2 for
missing or malformed arguments; 1 for an internal failure (gh output that is
not parseable or fails validation, a child process that cannot be started or
exceeds its time limit).  An internal failure prints nothing on stdout.

Operation boundary (FR22): this script only READS through gh (`gh repo view`,
`gh pr list`, `gh pr view`) and git (`git remote get-url`).  It never creates,
edits or merges a PR, never calls a write API and never changes a git ref.
Every gh call except the default-repository query names its repository
explicitly (`--repo`, or the remote's URL for the first resolution).

Time limits: every child process is time-limited (gh 60 s, git 30 s).  The
environment variable EM_WORKFLOW_MERGE_PR_GH_TIMEOUT (seconds, a positive
number) can only SHORTEN the gh limit; it exists for tests.
"""

import argparse
import json
import os
import re
import signal
import subprocess
import sys

GH_TIMEOUT_DEFAULT = 60.0
GIT_TIMEOUT = 30.0
GH_TIMEOUT_ENV = "EM_WORKFLOW_MERGE_PR_GH_TIMEOUT"
LIST_LIMIT = "100"

# --- validation -------------------------------------------------------------

FEATURE_RE = re.compile(r"[a-z0-9][a-z0-9-]*")
SHA_RE = re.compile(r"[0-9a-f]{40}")
PR_NUMBER_RE = re.compile(r"[1-9][0-9]{0,8}")
GIT_NAME_CHARS_RE = re.compile(r"[A-Za-z0-9._/-]+")
REPO_RE = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}/(?!\.{1,2}$)[A-Za-z0-9._][A-Za-z0-9._-]{0,99}"
)
HTTPS_URL_RE = re.compile(r"https://[A-Za-z0-9.-]+(?::[0-9]{1,5})?/[A-Za-z0-9._~%/+-]+")
REMOTE_SCHEMES = ("https", "http", "ssh", "git", "git+ssh", "ssh+git")
SCHEME_URL_RE = re.compile(r"([A-Za-z][A-Za-z0-9+.-]*)://([^/@]*@)?(.+)", re.DOTALL)
SCP_URL_RE = re.compile(r"[A-Za-z0-9_.-]+@[A-Za-z0-9.-]+:(?!//)[^\s]+")

PR_STATES = ("OPEN", "CLOSED", "MERGED")
MERGEABLE_VALUES = ("MERGEABLE", "CONFLICTING", "UNKNOWN")


class InternalFailure(Exception):
    """A condition that must never be turned into a guess."""


def valid_git_name(value):
    if not isinstance(value, str) or not value or len(value) > 255:
        return False
    if GIT_NAME_CHARS_RE.fullmatch(value) is None:
        return False
    if value.startswith(("-", "/")) or value.endswith(("/", ".")):
        return False
    if ".." in value or "//" in value:
        return False
    return not any(c.startswith(".") or c.endswith(".lock") for c in value.split("/"))


def valid_sha(value):
    return isinstance(value, str) and SHA_RE.fullmatch(value) is not None


def valid_pr_number(value):
    return isinstance(value, int) and not isinstance(value, bool) and 0 < value < 10**9


def valid_https_url(value):
    return (
        isinstance(value, str)
        and len(value) <= 2048
        and HTTPS_URL_RE.fullmatch(value) is not None
    )


def valid_repo(value):
    return isinstance(value, str) and REPO_RE.fullmatch(value) is not None


# --- argument types (a failure here is exit 2) -------------------------------


def arg_feature(value):
    if FEATURE_RE.fullmatch(value) is None:
        raise argparse.ArgumentTypeError("invalid feature name")
    return value


def arg_branch(value):
    if not valid_git_name(value):
        raise argparse.ArgumentTypeError("invalid branch or remote name")
    return value


def arg_sha(value):
    if not valid_sha(value):
        raise argparse.ArgumentTypeError("not a 40-character lowercase hex SHA")
    return value


def arg_pr(value):
    if PR_NUMBER_RE.fullmatch(value) is None:
        raise argparse.ArgumentTypeError("not a positive decimal integer")
    return int(value)


def arg_repo(value):
    if not valid_repo(value):
        raise argparse.ArgumentTypeError("not an owner/name repository")
    return value


def arg_dir(value):
    if not os.path.isdir(value):
        raise argparse.ArgumentTypeError("not an existing directory")
    return os.path.realpath(value)


def build_parser():
    parser = argparse.ArgumentParser(prog="merge-pr.py", allow_abbrev=False)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("repo", allow_abbrev=False)
    p.add_argument("--project-root", required=True, type=arg_dir)
    p.add_argument("--remote", required=True, type=arg_branch)

    p = sub.add_parser("resolve", allow_abbrev=False)
    p.add_argument("--project-root", required=True, type=arg_dir)
    p.add_argument("--repo", required=True, type=arg_repo)
    p.add_argument("--feature", required=True, type=arg_feature)
    p.add_argument("--base", required=True, type=arg_branch)

    p = sub.add_parser("state", allow_abbrev=False)
    p.add_argument("--project-root", required=True, type=arg_dir)
    p.add_argument("--repo", required=True, type=arg_repo)
    p.add_argument("--pr", required=True, type=arg_pr)
    p.add_argument("--head", required=True, type=arg_sha)
    return parser


# --- child processes -----------------------------------------------------------


def gh_timeout():
    limit = GH_TIMEOUT_DEFAULT
    raw = os.environ.get(GH_TIMEOUT_ENV)
    if raw:
        try:
            shortened = float(raw)
        except ValueError:
            shortened = 0.0
        if 0.0 < shortened < limit:
            limit = shortened
    return limit


def run_child(argv, cwd, timeout):
    """Run a child to completion within `timeout` seconds.

    Returns (returncode, stdout text, stderr text).  A child that cannot be
    started, exceeds the limit or emits undecodable output is an internal
    failure.  The child runs in its own session so a timeout takes down its
    whole process group.
    """
    env = dict(os.environ)
    env["GH_PROMPT_DISABLED"] = "1"
    env["GH_NO_UPDATE_NOTIFIER"] = "1"
    env["GIT_TERMINAL_PROMPT"] = "0"
    try:
        proc = subprocess.Popen(
            argv,
            cwd=cwd,
            env=env,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
    except OSError as exc:
        raise InternalFailure("cannot start %s: %s" % (argv[0], exc.strerror))
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except OSError:
            pass
        try:
            proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        raise InternalFailure("%s timed out after %gs" % (argv[0], timeout))
    try:
        return proc.returncode, out.decode("utf-8"), err.decode("utf-8", "replace")
    except UnicodeDecodeError:
        raise InternalFailure("%s produced undecodable output" % argv[0])


def run_gh(args, cwd):
    return run_child(["gh"] + args, cwd, gh_timeout())


def gh_json(args, cwd):
    """Run gh expecting success and JSON on stdout; anything else that is
    not a plain non-zero exit is an internal failure.  Returns None for a
    non-zero exit (the caller decides what that means)."""
    rc, out, err = run_gh(args, cwd)
    if rc != 0:
        sys.stderr.write("gh exited %d: %s\n" % (rc, err.strip()[:500]))
        return None
    try:
        return json.loads(out)
    except ValueError:
        raise InternalFailure("gh output is not JSON")


def require_json_object(value, what):
    if not isinstance(value, dict):
        raise InternalFailure("%s is not a JSON object" % what)
    return value


def name_with_owner(doc, what):
    doc = require_json_object(doc, what)
    value = doc.get("nameWithOwner")
    if not valid_repo(value):
        raise InternalFailure("%s carries no valid nameWithOwner" % what)
    return value


# --- results -------------------------------------------------------------------


def result(outcome, reason=None, detail="", **extra):
    out = {"outcome": outcome, "reason": reason, "detail": detail}
    out.update(extra)
    return out


def stop(reason, detail="", **extra):
    return result("stop", reason=reason, detail=detail, **extra)


# --- repo --------------------------------------------------------------------


def gh_target_url(raw):
    """The URL handed to gh for resolution, or None when the remote's URL is
    not one gh could treat as a GitHub repository URL.  Credentials embedded
    in the URL are dropped; gh uses its own authentication."""
    if not raw or len(raw) > 2048 or re.search(r"[\s\x00-\x1f\x7f]", raw):
        return None
    m = SCHEME_URL_RE.fullmatch(raw)
    if m:
        if m.group(1).lower() not in REMOTE_SCHEMES:
            return None
        return "%s://%s" % (m.group(1), m.group(3))
    if SCP_URL_RE.fullmatch(raw):
        return raw
    return None


def cmd_repo(args):
    root = args.project_root
    rc, out, err = run_child(
        ["git", "-C", root, "remote", "get-url", args.remote], None, GIT_TIMEOUT
    )
    if rc == 2:
        return stop("remote_unresolved", "remote '%s' does not exist" % args.remote)
    if rc != 0:
        raise InternalFailure("git remote get-url failed: %s" % err.strip()[:500])
    target = gh_target_url(out[:-1] if out.endswith("\n") else out)
    if target is None:
        return stop(
            "remote_not_github",
            "the URL of remote '%s' is not a GitHub repository URL" % args.remote,
        )

    remote_doc = gh_json(["repo", "view", target, "--json", "nameWithOwner"], root)
    if remote_doc is None:
        return stop(
            "remote_not_github",
            "gh cannot resolve remote '%s' to a GitHub repository" % args.remote,
        )
    remote_repo = name_with_owner(remote_doc, "gh repo view (remote)")

    # By design this query names no repository: it asks gh what it would use
    # for `gh pr create` / `gh pr merge` in this project.
    default_doc = gh_json(["repo", "view", "--json", "nameWithOwner"], root)
    if default_doc is None:
        return stop(
            "remote_unresolved",
            "gh default repository cannot be determined (remote repository: %s)"
            % remote_repo,
        )
    default_repo = name_with_owner(default_doc, "gh repo view (default)")
    if default_repo.lower() != remote_repo.lower():
        return stop(
            "remote_unresolved",
            "gh default repository %s differs from remote repository %s"
            % (default_repo, remote_repo),
        )
    return result("github", repo=remote_repo)


# --- PR parsing ----------------------------------------------------------------


def parse_merge_commit(value, required):
    if value is None:
        if required:
            raise InternalFailure("merged PR without a merge commit")
        return None
    if not isinstance(value, dict) or not valid_sha(value.get("oid")):
        raise InternalFailure("PR mergeCommit is not a valid commit")
    return value["oid"]


def parse_pr(raw, with_branches):
    """Validate one PR object from gh and return a normalized dict."""
    raw = require_json_object(raw, "PR entry")

    def need(key, ok, label):
        value = raw.get(key)
        if not ok(value):
            raise InternalFailure("PR field %s is not a valid %s" % (key, label))
        return value

    pr = {
        "number": need("number", valid_pr_number, "PR number"),
        "url": need("url", valid_https_url, "https URL"),
        "state": need("state", lambda v: v in PR_STATES, "PR state"),
        "draft": need("isDraft", lambda v: isinstance(v, bool), "boolean"),
        "head_sha": need("headRefOid", valid_sha, "commit SHA"),
    }
    pr["merge_commit"] = parse_merge_commit(
        raw.get("mergeCommit"), required=pr["state"] == "MERGED"
    )
    if with_branches:
        pr["head_ref"] = need("headRefName", lambda v: isinstance(v, str), "string")
        pr["base_ref"] = need("baseRefName", lambda v: isinstance(v, str), "string")
        pr["cross_repo"] = need(
            "isCrossRepository", lambda v: isinstance(v, bool), "boolean"
        )
    else:
        pr["mergeable"] = need(
            "mergeable", lambda v: v in MERGEABLE_VALUES, "mergeability"
        )
    return pr


PR_LIST_FIELDS = (
    "number,url,state,isDraft,headRefName,baseRefName,headRefOid,"
    "isCrossRepository,mergeCommit"
)
PR_VIEW_FIELDS = "number,url,state,isDraft,mergeable,headRefOid,mergeCommit"


# --- resolve -----------------------------------------------------------------


def cmd_resolve(args):
    branch = "em-workflow/%s/integration" % args.feature
    listed = gh_json(
        [
            "pr", "list",
            "--repo", args.repo,
            "--head", branch,
            "--base", args.base,
            "--state", "all",
            "--limit", LIST_LIMIT,
            "--json", PR_LIST_FIELDS,
        ],
        args.project_root,
    )
    if listed is None:
        raise InternalFailure("gh pr list failed")
    if not isinstance(listed, list):
        raise InternalFailure("gh pr list output is not a JSON array")
    prs = [parse_pr(item, with_branches=True) for item in listed]
    prs = [
        p for p in prs
        if p["head_ref"] == branch and p["base_ref"] == args.base and not p["cross_repo"]
    ]

    def newest(state, draft=None):
        found = [
            p for p in prs
            if p["state"] == state and (draft is None or p["draft"] == draft)
        ]
        return max(found, key=lambda p: p["number"]) if found else None

    merged = newest("MERGED")
    if merged:
        return result(
            "merged",
            pr_number=merged["number"],
            pr_url=merged["url"],
            merge_commit=merged["merge_commit"],
        )
    open_ready = newest("OPEN", draft=False)
    if open_ready:
        return result(
            "open",
            pr_number=open_ready["number"],
            pr_url=open_ready["url"],
            head=open_ready["head_sha"],
        )
    open_draft = newest("OPEN", draft=True)
    if open_draft:
        return stop(
            "pr_draft",
            "PR #%d is a draft" % open_draft["number"],
            pr_number=open_draft["number"],
            pr_url=open_draft["url"],
        )
    closed = newest("CLOSED")
    if closed:
        return stop(
            "pr_closed",
            "PR #%d is closed without being merged" % closed["number"],
            pr_number=closed["number"],
            pr_url=closed["url"],
        )
    return result("none", create_head=branch, create_base=args.base)


# --- state -------------------------------------------------------------------


def cmd_state(args):
    doc = gh_json(
        [
            "pr", "view", str(args.pr),
            "--repo", args.repo,
            "--json", PR_VIEW_FIELDS,
        ],
        args.project_root,
    )
    if doc is None:
        raise InternalFailure("gh pr view failed")
    pr = parse_pr(doc, with_branches=False)
    if pr["number"] != args.pr:
        raise InternalFailure("gh returned a different PR than requested")

    num, url = pr["number"], pr["url"]
    if pr["state"] == "MERGED":
        return result("merged", pr_url=url, merge_commit=pr["merge_commit"])
    if pr["state"] != "OPEN":
        return stop("pr_closed", "PR #%d is not open" % num, pr_url=url)
    if pr["draft"]:
        return stop("pr_draft", "PR #%d is a draft" % num, pr_url=url)
    if pr["mergeable"] == "CONFLICTING":
        return stop("pr_conflicting", "PR #%d has merge conflicts" % num, pr_url=url)
    if pr["head_sha"] != args.head:
        return stop(
            "pr_head_moved",
            "PR #%d head is %s, expected %s" % (num, pr["head_sha"], args.head),
            pr_url=url,
        )
    return result("ready", pr_url=url, head=pr["head_sha"])


HANDLERS = {"repo": cmd_repo, "resolve": cmd_resolve, "state": cmd_state}


def main(argv=None):
    args = build_parser().parse_args(argv)
    try:
        outcome = HANDLERS[args.command](args)
    except InternalFailure as exc:
        sys.stderr.write("merge-pr.py: internal failure: %s\n" % exc)
        return 1
    except Exception as exc:  # never let a crash look like a decision
        sys.stderr.write("merge-pr.py: internal failure: %s\n" % type(exc).__name__)
        return 1
    sys.stdout.write(json.dumps(outcome) + "\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
