#!/usr/bin/env python3
"""Review input measurement, shard split and dispatch cap (em-workflow plugin,
task0002 of feature-docs/large-diff-review-coverage; FR5, FR6, FR7, FR18,
NFR1, NFR3, NFR4, NFR6).

The review phase runs this script before it dispatches reviewers. It measures
the review input of every changed file in characters, splits the input into
file-level shards when the total exceeds 200,000 characters, and applies the
per-perspective shard cap. It returns only paths, character counts and shard
composition: diff text is counted and never printed.

CLI contract:
    python3 review-shards.py INPUT_DOCUMENT
  Exactly one argument: the path of the input document. The script defines
  no options: the argument is a file name even when it begins with `-`. Any
  other argument count is a usage error.

Input document: one UTF-8 JSON object with exactly these five members.
  project_root       absolute path of an existing directory (the reviewed
                     tree)
  review_mode        `diff` or `whole-codebase`
  diff_base          in diff mode `HEAD` or a commit id of 40 lowercase hex
                     digits; null in whole-codebase mode
  changed_files      a list of project-relative, `/`-separated path strings
                     without duplicates. A path that is empty, absolute,
                     has an empty, `.` or `..` segment, holds NUL, CR or LF,
                     or starts with `-` is invalid. Each path, checked
                     without following symlinks, must be a regular file, and
                     its real path must be inside project_root. Every path
                     is checked before any file is read and before `git`
                     runs, so a FIFO is never opened.
  perspective_count  an integer from 1 to 24 (the number of perspectives the
                     review phase dispatches through Task this round)

Measurement, per file in path (code point) order:
  whole-codebase    the character count of the file content; `git` is not
                    run.
  diff              the character count of `git diff` text for that one
                    file against diff_base. When that text is empty (an
                    untracked file, or no textual change) the file content is
                    counted instead. When diff_base is `HEAD` and the
                    repository has no commit yet, the file content is
                    counted. Any other `git` failure is a failure of the
                    script.
  Characters are counted after decoding bytes as UTF-8 with invalid bytes
  replaced. `git` runs on project_root with an argument list and no shell,
  `--` before the path, literal pathspecs, and external diff, text
  conversion, color, rename detection and the filesystem monitor turned off,
  and with fixed prefix, index-line and context options, so the count does
  not depend on the user's diff configuration.

Split and cap:
  A total of 200,000 characters or less is not split: one shard (index 1)
  holds every path. Above 200,000, files in path order are filled next-fit
  into shards of at most 200,000 characters; a file over 200,000 characters
  forms a shard of its own. Shard indexes start at 1.
  shard_cap is floor(24 / perspective_count). dispatched_shards are the
  indexes 1 to shard_cap (the existing ones), excess_shards are the rest.

Output:
  stdout carries one JSON object on one line, UTF-8 encoded whatever the
  locale, non-ASCII characters unescaped, followed by a newline, with
  exactly these members in this order:
    limit              200000
    total_chars        the sum of the per-file counts
    split              true when the total exceeds the limit
    files              [{"path", "chars"}] in path order
    shards             [{"index", "paths", "chars"}] in index order, the
                       paths of a shard in path order
    shard_cap          floor(24 / perspective_count)
    dispatched_shards  shard indexes, ascending
    excess_shards      shard indexes, ascending
  Paths are project-relative. The output depends only on the set of paths,
  not on their order in changed_files.

Exit codes:
    0   success
    2   usage error, invalid input, an input document that cannot be read or
        parsed, a path that cannot be measured, a `git` failure, or an
        unexpected failure; a message on stderr and nothing on stdout

Isolation: standard library only. The script reads its input document, the
files named in it and, in diff mode, runs `git rev-parse`, `git symbolic-ref`
and `git diff` on project_root with every GIT_* variable removed from the
environment. It writes no file and changes no file, object, ref or setting of
the repository (git may refresh the stat data cached in its index, as for any
`git diff`). No message names diff text or file content.
"""

import codecs
import json
import os
import re
import stat
import subprocess
import sys
import threading

PROGRAM = "review-shards"

USAGE = (
    "usage: python3 review-shards.py INPUT_DOCUMENT\n"
    "  INPUT_DOCUMENT is the path of one UTF-8 JSON object with the members\n"
    "  project_root, review_mode, diff_base, changed_files, perspective_count.\n"
    "  Prints one JSON object with limit, total_chars, split, files, shards,\n"
    "  shard_cap, dispatched_shards, excess_shards.\n"
    "  Exit codes: 0 success, 2 usage error, invalid input or failure.\n"
)

# Fixed values of the review phase (review-phase.md states them as the values
# this script applies).
SHARD_LIMIT = 200_000
DISPATCH_CAP = 24

MEMBERS = (
    "project_root",
    "review_mode",
    "diff_base",
    "changed_files",
    "perspective_count",
)
REVIEW_MODES = ("diff", "whole-codebase")
COMMIT_ID = re.compile(r"[0-9a-f]{40}")

READ_CHUNK_BYTES = 65536
GIT_TIMEOUT_SECONDS = 300

# `git` is run with this argument prefix. The global options come before the
# subcommand; `core.fsmonitor` is turned off so a configured monitor hook is
# never run.
GIT_PREFIX = (
    "git",
    "--no-pager",
    "--literal-pathspecs",
    "-c",
    "core.quotepath=false",
    "-c",
    "core.fsmonitor=false",
)
GIT_DIFF_OPTIONS = (
    "--no-ext-diff",
    "--no-textconv",
    "--no-color",
    "--no-renames",
    "--src-prefix=a/",
    "--dst-prefix=b/",
    "--full-index",
    "--unified=3",
    "--inter-hunk-context=0",
)


class InputError(ValueError):
    """The input is not acceptable or a measurement failed: reported on
    stderr, exit 2."""


# ------------------------------------------------------------ validation ----


def _show(value, limit=80):
    """A single-line, ASCII-only rendering of a value for a message."""
    text = json.dumps(value, ensure_ascii=True)
    if len(text) > limit:
        text = text[: limit - 3] + "..."
    return text


def _describe(value):
    return type(value).__name__ if value is not None else "null"


def _reject_constant(name):
    raise ValueError(f"the constant {name} is not valid JSON")


def _reject_duplicate_keys(pairs):
    keys = [key for key, _ in pairs]
    if len(set(keys)) != len(keys):
        raise ValueError("an object holds a duplicate key")
    return dict(pairs)


def _read_document(path):
    try:
        with open(path, "rb") as handle:
            raw = handle.read()
    except (OSError, ValueError) as exc:
        raise InputError(
            f"cannot read the input document: {type(exc).__name__}"
        ) from None
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise InputError("the input document is not valid UTF-8") from None
    try:
        document = json.loads(
            text,
            parse_constant=_reject_constant,
            object_pairs_hook=_reject_duplicate_keys,
        )
    except (ValueError, RecursionError) as exc:
        raise InputError(f"the input document is not valid JSON: {exc}") from None
    if not isinstance(document, dict):
        raise InputError("the input document must be a JSON object")
    return document


def _is_utf8_encodable(text):
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def _check_project_root(value):
    if not isinstance(value, str):
        raise InputError(f"project_root must be a string, got {_describe(value)}")
    if (
        not value.startswith("/")
        or "\x00" in value
        or not _is_utf8_encodable(value)
    ):
        raise InputError(
            f"project_root must be an absolute path, got {_show(value)}"
        )
    if not os.path.isdir(value):
        raise InputError(
            f"project_root must be an existing directory, got {_show(value)}"
        )
    return value


def _check_review_mode(value):
    if not isinstance(value, str) or value not in REVIEW_MODES:
        raise InputError(
            f"review_mode must be one of {list(REVIEW_MODES)}, got {_show(value)}"
        )
    return value


def _check_diff_base(value, review_mode):
    if review_mode == "diff":
        if not isinstance(value, str) or not (
            value == "HEAD" or COMMIT_ID.fullmatch(value)
        ):
            raise InputError(
                "diff_base must be HEAD or 40 lowercase hex digits in diff "
                f"mode, got {_show(value)}"
            )
    elif value is not None:
        raise InputError(
            f"diff_base must be null in whole-codebase mode, got {_show(value)}"
        )
    return value


def _path_problem(path):
    """The reason a path string is not acceptable, or None."""
    if not path:
        return "is empty"
    if path.startswith("/"):
        return "is absolute"
    if any(char in path for char in "\x00\r\n"):
        return "holds NUL, CR or LF"
    if path.startswith("-"):
        return "starts with -"
    segments = path.split("/")
    if ".." in segments:
        return "has a .. segment"
    if "" in segments or "." in segments:
        return "has an empty or . segment"
    if not _is_utf8_encodable(path):
        return "is not valid Unicode text"
    return None


def _check_changed_files(value):
    if not isinstance(value, list):
        raise InputError(f"changed_files must be a list, got {_describe(value)}")
    seen = set()
    for path in value:
        if not isinstance(path, str):
            raise InputError(
                f"changed_files must hold strings, got {_describe(path)}"
            )
        problem = _path_problem(path)
        if problem is not None:
            raise InputError(f"changed_files path {_show(path)} {problem}")
        if path in seen:
            raise InputError(f"changed_files holds a duplicate: {_show(path)}")
        seen.add(path)
    return value


def _check_perspective_count(value):
    if isinstance(value, bool) or not isinstance(value, int):
        raise InputError(
            f"perspective_count must be an integer, got {_describe(value)}"
        )
    if not 1 <= value <= DISPATCH_CAP:
        raise InputError(
            f"perspective_count must be from 1 to {DISPATCH_CAP}, got {value}"
        )
    return value


def _inside(real_path, real_root):
    return real_path != real_root and os.path.commonpath(
        [real_path, real_root]
    ) == real_root


def _check_files_on_disk(project_root, paths):
    """Every path, checked without following symlinks, is a regular file and
    its real path is inside project_root. Nothing is opened."""
    real_root = os.path.realpath(project_root)
    for path in paths:
        full = os.path.join(project_root, path)
        try:
            mode = os.lstat(full).st_mode
        except OSError:
            raise InputError(
                f"changed_files path {_show(path)} cannot be examined"
            ) from None
        if not stat.S_ISREG(mode):
            raise InputError(
                f"changed_files path {_show(path)} is not a regular file"
            )
        if not _inside(os.path.realpath(full), real_root):
            raise InputError(
                f"changed_files path {_show(path)} is not inside project_root"
            )


def _validate_document(document):
    """Check the whole document and every path before any read or `git` run;
    returns the five members."""
    for name in MEMBERS:
        if name not in document:
            raise InputError(f"the member {name} is missing")
    for name in document:
        if name not in MEMBERS:
            raise InputError(f"the member {name} is not accepted")
    project_root = _check_project_root(document["project_root"])
    review_mode = _check_review_mode(document["review_mode"])
    diff_base = _check_diff_base(document["diff_base"], review_mode)
    changed_files = _check_changed_files(document["changed_files"])
    perspective_count = _check_perspective_count(document["perspective_count"])
    _check_files_on_disk(project_root, changed_files)
    return project_root, review_mode, diff_base, changed_files, perspective_count


# ----------------------------------------------------------- measurement ----


def _count_chunks(chunks):
    """Characters in a sequence of byte chunks decoded as UTF-8 with invalid
    bytes replaced; equals the length of decoding the whole text at once."""
    decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
    total = 0
    for chunk in chunks:
        total += len(decoder.decode(chunk))
    return total + len(decoder.decode(b"", final=True))


def _read_chunks(handle):
    while True:
        chunk = handle.read(READ_CHUNK_BYTES)
        if not chunk:
            return
        yield chunk


def count_content(project_root, path):
    """The character count of a file's content. The file is opened without
    following a symlink and without blocking, and must still be a regular
    file once it is open."""
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    full = os.path.join(project_root, path)
    try:
        descriptor = os.open(full, flags)
    except OSError:
        raise InputError(f"cannot read {_show(path)}") from None
    try:
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise InputError(f"{_show(path)} is not a regular file")
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            try:
                return _count_chunks(_read_chunks(handle))
            except OSError:
                raise InputError(f"cannot read {_show(path)}") from None
    finally:
        os.close(descriptor)


def _git_environment():
    """The environment of every `git` run: no GIT_* variable, since none may
    steer the repository, the index, the diff options or an external
    program."""
    return {
        key: value for key, value in os.environ.items() if not key.startswith("GIT_")
    }


def _run_git(project_root, arguments, consume):
    """Run `git` with an argument list and no shell on project_root. The
    output goes through `consume(chunks)`; stderr is discarded. Returns
    (exit code, consume result). A run that exceeds the time limit fails."""
    try:
        process = subprocess.Popen(
            list(GIT_PREFIX) + list(arguments),
            cwd=project_root,
            env=_git_environment(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            shell=False,
        )
    except OSError as exc:
        raise InputError(f"cannot run git: {type(exc).__name__}") from None
    timed_out = threading.Event()

    def _expire():
        timed_out.set()
        process.kill()

    timer = threading.Timer(GIT_TIMEOUT_SECONDS, _expire)
    timer.start()
    try:
        result = consume(_read_chunks(process.stdout))
    except OSError:
        process.kill()
        result = None
    finally:
        timer.cancel()
        process.stdout.close()
        code = process.wait()
    if timed_out.is_set():
        raise InputError("git did not finish in time")
    return code, result


def _repository_has_no_commit(project_root):
    """True for an existing repository whose HEAD points at a branch that has
    no commit yet; false when HEAD resolves. Anything else is a failure."""
    code, _ = _run_git(
        project_root, ["rev-parse", "--verify", "--quiet", "HEAD"], _count_chunks
    )
    if code == 0:
        return False
    if code == 1:
        branch_code, _ = _run_git(
            project_root, ["symbolic-ref", "--quiet", "HEAD"], _count_chunks
        )
        if branch_code == 0:
            return True
    raise InputError("git cannot resolve HEAD in project_root")


def count_diff(project_root, diff_base, path):
    """The character count of the diff text of one file against diff_base."""
    arguments = ["diff"] + list(GIT_DIFF_OPTIONS) + [diff_base, "--", path]
    code, count = _run_git(project_root, arguments, _count_chunks)
    if code != 0 or count is None:
        raise InputError(f"git diff failed for {_show(path)} (exit {code})")
    return count


def measure(project_root, review_mode, diff_base, paths):
    """The character count of every path, as a list of (path, chars) in
    path order."""
    ordered = sorted(paths)
    no_commit = None
    counts = []
    for path in ordered:
        if review_mode == "whole-codebase":
            chars = count_content(project_root, path)
        else:
            if no_commit is None:
                no_commit = diff_base == "HEAD" and _repository_has_no_commit(
                    project_root
                )
            if no_commit:
                chars = count_content(project_root, path)
            else:
                chars = count_diff(project_root, diff_base, path)
                if chars == 0:
                    chars = count_content(project_root, path)
        counts.append((path, chars))
    return counts


# ------------------------------------------------------- split and cap ----


def split_shards(counts, limit=SHARD_LIMIT):
    """Next-fit shards over (path, chars) pairs already in path order, as a
    list of (paths, chars). A pair over the limit forms a shard of its own."""
    shards = []
    current_paths = []
    current_chars = 0
    for path, chars in counts:
        # A file over the limit never fits after another file, and no later
        # file fits after it, so it ends up alone in its shard.
        if current_paths and current_chars + chars > limit:
            shards.append((current_paths, current_chars))
            current_paths, current_chars = [], 0
        current_paths.append(path)
        current_chars += chars
    if current_paths:
        shards.append((current_paths, current_chars))
    return shards


def build_result(counts, perspective_count, limit=SHARD_LIMIT):
    """The output object for (path, chars) pairs in path order."""
    total = sum(chars for _, chars in counts)
    split = total > limit
    if split:
        shard_paths = split_shards(counts, limit)
    else:
        shard_paths = [([path for path, _ in counts], total)]
    shards = [
        {"index": index, "paths": paths, "chars": chars}
        for index, (paths, chars) in enumerate(shard_paths, start=1)
    ]
    shard_cap = DISPATCH_CAP // perspective_count
    indexes = [shard["index"] for shard in shards]
    return {
        "limit": limit,
        "total_chars": total,
        "split": split,
        "files": [{"path": path, "chars": chars} for path, chars in counts],
        "shards": shards,
        "shard_cap": shard_cap,
        "dispatched_shards": [index for index in indexes if index <= shard_cap],
        "excess_shards": [index for index in indexes if index > shard_cap],
    }


# -------------------------------------------------------------------- CLI ----


def _fail(message, usage=False):
    sys.stderr.write(f"{PROGRAM}: {message}\n")
    if usage:
        sys.stderr.write(USAGE)
    sys.stderr.flush()


def main(argv=None):
    """Run the CLI; `argv` excludes the program name. Returns the exit code."""
    if argv is None:
        argv = sys.argv[1:]
    try:
        if len(argv) != 1:
            _fail(
                f"expected exactly one argument, got {len(argv)}", usage=True
            )
            return 2
        document = _read_document(argv[0])
        (
            project_root,
            review_mode,
            diff_base,
            changed_files,
            perspective_count,
        ) = _validate_document(document)
        counts = measure(project_root, review_mode, diff_base, changed_files)
        result = build_result(counts, perspective_count)
        output = (
            json.dumps(
                result,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")
        sys.stdout.buffer.write(output)
        sys.stdout.buffer.flush()
        return 0
    except InputError as exc:
        _fail(str(exc))
        return 2
    except Exception as exc:  # noqa: BLE001 -- last-resort exit-2 safety net
        _fail(f"unexpected failure: {type(exc).__name__}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
