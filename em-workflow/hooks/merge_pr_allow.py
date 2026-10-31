"""The one `gh pr merge` that destructive-guard.py lets through.

This module is not a hook. destructive-guard.py loads it from the directory it
runs from and consults it while it judges a command; a PreToolUse hook is
registered in hooks.json, and this file is not.

em-workflow's unattended merge skill (IMPLEMENTATION.md C9) merges a pull
request with exactly this command, run from the feature's integration worktree:

    gh pr merge <PR number> --merge --match-head-commit <40-hex SHA>

The head-commit pin makes GitHub refuse the merge if the PR moved after it was
verified. destructive-guard.py asks about every other `gh pr merge` (`deny` in an
unattended run), including the same words with one more token, an environment
prefix, or from any other directory.

The exception holds only when all of these are true:

  - the statement is exactly the seven tokens above (is_canonical_merge());
  - the working directory is a registered integration worktree of this project,
    or a directory below one (is_integration_worktree_cwd());
  - the merge is the whole command: no other statement shares it, and none of
    them changes the directory or the environment (keeps_exception()).

destructive-guard.py calls two functions and nothing else here:

  allows_statement(toks, lexed, cwd)
      for one statement: does the exception apply to it?
  keeps_exception(statement_count, context_changed)
      after the whole command was read, with an exception applied to one of
      its statements: does the exception still stand?

Everything specific to the merge lives in this file: the form, the path shape,
the on-disk registration check and the sole-statement policy. destructive-guard.py
holds no pattern, path or ref name of it.
"""

import os
import re

MERGE_PR_NUMBER = re.compile(r"[1-9][0-9]*")
MERGE_HEAD_SHA = re.compile(r"[0-9a-f]{40}")
MERGE_FEATURE = re.compile(r"[a-z0-9][a-z0-9-]*")
MERGE_WORKTREE_PREFIX = (".claude", "worktrees", "em-workflow")


def allows_statement(toks, lexed, cwd):
    """Whether the exception applies to one statement: it is the canonical
    merge command and CWD is a registered integration worktree (or below
    one). TOKS and LEXED are the statement's tokens and whether its chunk
    lexed; CWD is the payload's working directory."""
    return is_canonical_merge(toks, lexed) and is_integration_worktree_cwd(cwd)


def keeps_exception(statement_count, context_changed):
    """Whether the exception stands for a command in which one statement got
    it. The merge must be the only statement: any other one, harmless or not,
    ends the exception. So does a statement that changed the directory or the
    environment the merge would run in (CONTEXT_CHANGED); such a statement is
    one of the others, which STATEMENT_COUNT already counts."""
    return statement_count <= 1 and not context_changed


def is_canonical_merge(toks, lexed):
    """Whether one statement is exactly the canonical merge command and
    nothing else: TOKS is the statement's whole token list, so a redirect, an
    environment prefix, a wrapper, a grouping token or any extra word makes
    it differ. A token built from a command substitution (its text is not
    the value bash passes), or carrying a trailing carriage return, never
    matches. A statement of a chunk that would not lex (LEXED false) has no
    token provenance and is not matched."""
    if not lexed or len(toks) != 7:
        return False
    if any(
        getattr(t, "is_operator", False)
        or getattr(t, "unresolved", False)
        or getattr(t, "substitution_only", False)
        or getattr(t, "trailing_cr", "")
        for t in toks
    ):
        return False
    gh, pr, merge, number, merge_flag, pin, sha = toks
    return (
        (gh, pr, merge, merge_flag, pin)
        == ("gh", "pr", "merge", "--merge", "--match-head-commit")
        and MERGE_PR_NUMBER.fullmatch(number) is not None
        and MERGE_HEAD_SHA.fullmatch(sha) is not None
    )


def is_integration_worktree_cwd(cwd):
    """Whether CWD is a registered em-workflow integration worktree or
    somewhere below it: an absolute path holding `.claude/worktrees/em-workflow/
    <feature>/integration` (<feature> a valid feature name, the next segment
    exactly `integration`) with nothing after it that climbs out again, and
    whose directory is registered on disk (_is_registered_integration_worktree).

    `.` segments are dropped. A `..` before the end of the shape means the
    path only reaches it by way of the climb, and one after it that leaves
    the worktree means the directory is somewhere else: neither counts. A
    `..` after the shape that stays inside the worktree does. The path string
    decides the shape; the disk is read only for the registration and for the
    directories below the worktree root.
    """
    if not isinstance(cwd, str) or not cwd.startswith("/"):
        return False
    segs = [s for s in cwd.split("/") if s not in ("", ".")]
    for i in range(len(segs) - 4):
        if tuple(segs[i : i + 3]) != MERGE_WORKTREE_PREFIX:
            continue
        if MERGE_FEATURE.fullmatch(segs[i + 3]) is None or segs[i + 4] != "integration":
            continue
        if ".." in segs[:i]:
            continue
        depth = 0
        for seg in segs[i + 5 :]:
            depth += -1 if seg == ".." else 1
            if depth < 0:
                break
        else:
            root = "/" + "/".join(segs[: i + 5])
            project = "/" + "/".join(segs[:i])
            # Below the root, any directory with its own `.git` (nested clone,
            # submodule) or any symlink is a different repository: no exception.
            rest = []
            for seg in segs[i + 5 :]:
                if seg == "..":
                    rest.pop()
                else:
                    rest.append(seg)
            cur = root
            try:
                for seg in rest:
                    cur = os.path.join(cur, seg)
                    if os.path.islink(cur) or os.path.lexists(os.path.join(cur, ".git")):
                        return False
            except Exception:
                return False
            return _is_registered_integration_worktree(root, project, segs[i + 3])
    return False


def _is_registered_integration_worktree(root, project, feature):
    """On-disk check behind is_integration_worktree_cwd(): ROOT's `.git` is a
    regular file (not a symlink) whose `gitdir:` resolves to a direct child of
    PROJECT's `.git/worktrees/`, and that gitdir's HEAD is the feature's
    integration branch. Any failure or exception means False (ask)."""
    try:
        git_file = os.path.join(root, ".git")
        if os.path.islink(git_file) or not os.path.isfile(git_file):
            return False
        with open(git_file, "r", encoding="utf-8") as f:
            content = f.read(4096)
        line = content.strip()
        if "\n" in line or not line.startswith("gitdir:"):
            return False
        gitdir = line[len("gitdir:"):].strip()
        if not gitdir:
            return False
        if not os.path.isabs(gitdir):
            gitdir = os.path.join(root, gitdir)
        gitdir = os.path.realpath(gitdir)
        worktrees = os.path.realpath(os.path.join(project, ".git", "worktrees"))
        if os.path.dirname(gitdir) != worktrees or not os.path.isdir(gitdir):
            return False
        head_path = os.path.join(gitdir, "HEAD")
        if os.path.islink(head_path) or not os.path.isfile(head_path):
            return False
        with open(head_path, "r", encoding="utf-8") as f:
            head = f.read(4096).strip()
        return head == f"ref: refs/heads/em-workflow/{feature}/integration"
    except Exception:
        return False
