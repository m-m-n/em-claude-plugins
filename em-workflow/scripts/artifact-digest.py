#!/usr/bin/env python3
"""Artifact digest calculation (em-workflow plugin, task0001 of
feature-docs/worker-digest-ownership; FR6, FR7, NFR1, NFR3).

The one standard-library calculation of the artifact digest: sha256 over a
file's raw bytes, rendered `sha256:` followed by 64 lowercase hexadecimal
digits. The orchestrator -- never a worker -- runs this script and records
the result; `references/artifact-digest.md` is the protocol-side description
of how the orchestrator uses it (the digest definition, the pre-dispatch
verification procedure, layer-5 recording). This module documents only the
command line.

This digest is not `input_digest` (rule R1) and it is not a git blob id.

CLI contract:
    python3 artifact-digest.py PATH [PATH ...]
  The script defines no options: every argument is a target path taken
  verbatim, including arguments that begin with `-` (`-`, `--` and `--help`
  are file names). A relative path resolves against the current directory.
  An empty argument is reported as `missing`.

Output:
  stdout carries one JSON array, UTF-8 encoded whatever the locale,
  non-ASCII characters unescaped, followed by a newline. There is exactly
  one element per argument, in argument order, duplicates kept.
    success element:  {"path": <argument as given>, "sha256": "sha256:<hex>"}
    failure element:  {"path": <argument as given>, "sha256": null,
                       "error": <token>}
  Error tokens:
    missing             no filesystem entry at the path
    not_a_regular_file  the entry is a directory, a symlink (dangling or
                        not), a FIFO, a device or a socket
    unreadable          the entry is a regular file whose reading failed
                        (permission denied, I/O error); an entry whose
                        existence cannot be determined because of a
                        permission or I/O error is reported the same way

Exit codes:
    0   every element carries a digest
    1   at least one element carries an error; every other element is still
        hashed
    2   no argument (usage on stderr), an argument that is not valid UTF-8,
        or an unexpected internal failure; stdout carries no array

Entry kinds: only a regular file is hashed. The final path component is
never resolved through a symlink and nothing waits on a FIFO or a device.
The regular-file determination is confirmed on the handle actually read, so
an entry replaced between inspection and reading can neither redirect the
read through a symlink nor block it. Arguments are handled as raw bytes, so
the result does not depend on the locale or the interpreter's text
encodings. The file is read in fixed-size chunks; memory use does not grow
with file size. The script starts no child process and calls no external
command.
"""

import errno
import hashlib
import json
import os
import stat
import sys

CHUNK_SIZE = 64 * 1024

USAGE = (
    "usage: python3 artifact-digest.py PATH [PATH ...]\n"
    "  Prints one JSON array with one element per PATH (in argument order)\n"
    "  holding the path and its sha256 digest, or an error token.\n"
    "  Every argument is a path; there are no options.\n"
    "  Exit codes: 0 all digests, 1 at least one error element,\n"
    "  2 usage or internal failure.\n"
)

# Open flags that make the read safe whatever the entry has become by the
# time it is opened: never follow a symlink in the final component, never
# wait on a FIFO or device, never leak the descriptor into a child. A flag
# the platform lacks is simply absent (0).
OPEN_FLAGS = (
    os.O_RDONLY
    | getattr(os, "O_NOFOLLOW", 0)
    | getattr(os, "O_NONBLOCK", 0)
    | getattr(os, "O_CLOEXEC", 0)
    | getattr(os, "O_BINARY", 0)
)

# errno values meaning that no filesystem entry can exist at the path.
NO_ENTRY_ERRNOS = frozenset(
    {errno.ENOENT, errno.ENOTDIR, errno.ELOOP, errno.ENAMETOOLONG}
)

# errno values meaning "the final component is a symlink" when the path is
# opened with O_NOFOLLOW (ELOOP on Linux and macOS, EMLINK on FreeBSD).
SYMLINK_OPEN_ERRNOS = frozenset(
    code
    for code in (errno.ELOOP, getattr(errno, "EMLINK", None))
    if code is not None
)

# Open flags for every directory the walk steps into, the last directory
# included when the path ends in `/`: only a directory is accepted, a symlink
# is never followed, nothing waits on a FIFO or device, and the descriptor
# never leaks into a child. A flag the platform lacks is simply absent (0)
# here, so loading the script never fails; run() refuses to start before any
# argument is processed when a flag the walk depends on is missing.
DIRECTORY_OPEN_FLAGS = (
    os.O_RDONLY
    | getattr(os, "O_DIRECTORY", 0)
    | getattr(os, "O_NOFOLLOW", 0)
    | getattr(os, "O_NONBLOCK", 0)
    | getattr(os, "O_CLOEXEC", 0)
)

# errno values with which a directory-only, no-follow open refuses a
# component that is not a directory. A symlink gives ENOTDIR on Linux and
# ELOOP (EMLINK on FreeBSD) elsewhere, so the kind of the component has to be
# inspected before the failure becomes an error token.
DIRECTORY_REFUSED_ERRNOS = frozenset({errno.ENOTDIR}) | SYMLINK_OPEN_ERRNOS


def digest_of_descriptor(fd):
    """sha256 of everything readable from `fd`, in bounded chunks."""
    hasher = hashlib.sha256()
    while True:
        chunk = os.read(fd, CHUNK_SIZE)
        if not chunk:
            break
        hasher.update(chunk)
    return "sha256:" + hasher.hexdigest()


def close_descriptor(fd):
    """Close a read-only descriptor; a failing close cannot change a result."""
    try:
        os.close(fd)
    except OSError:
        pass


def missing_capabilities():
    """Names of the platform capabilities the path walk needs but lacks.

    Looked up on every call (never cached at import time), so the answer
    always reflects the `os` module as it is when the script runs.
    """
    absent = []
    if os.open not in getattr(os, "supports_dir_fd", ()):
        absent.append(
            "descriptor-relative open (os.open with dir_fd, "
            "os.supports_dir_fd)"
        )
    if not hasattr(os, "O_NOFOLLOW"):
        absent.append("no-follow open flag (os.O_NOFOLLOW)")
    if not hasattr(os, "O_DIRECTORY"):
        absent.append("directory-only open flag (os.O_DIRECTORY)")
    return absent


def failure_token(exc):
    """The error token for an OSError that is not a symlink refusal."""
    if exc.errno in NO_ENTRY_ERRNOS:
        return "missing"
    return "unreadable"


def directory_refusal_token(parent_fd, name):
    """Error token for a component that a directory-only open refused.

    The component's kind is inspected relative to the same parent descriptor
    and without following a symlink. A symlink of any kind (to a directory,
    to a file, dangling, looping) is `not_a_regular_file`; something that
    exists but is neither a directory nor a symlink, or nothing at all, is
    `missing`. A directory here means the component was swapped after the
    open failed, and an inspection that fails itself is mapped like any other
    failure; neither case may ever produce a digest.
    """
    try:
        kind = os.lstat(name, dir_fd=parent_fd).st_mode
    except OSError as exc:
        return failure_token(exc)
    if stat.S_ISLNK(kind):
        return "not_a_regular_file"
    if stat.S_ISDIR(kind):
        return "unreadable"
    return "missing"


def digest_of_entry(parent_fd, name):
    """Return `(digest, None)` or `(None, error_token)` for the final
    component `name` of a path, found in the directory open as `parent_fd`.

    The entry is inspected without following a symlink, so a FIFO, device,
    socket or symlink is rejected before anything is opened. The open itself
    refuses a symlink and never waits, and the regular-file determination is
    repeated on the opened handle, which is the one that is read.
    """
    try:
        inspected = os.lstat(name, dir_fd=parent_fd)
    except OSError as exc:
        return None, failure_token(exc)
    if not stat.S_ISREG(inspected.st_mode):
        return None, "not_a_regular_file"

    try:
        fd = os.open(name, OPEN_FLAGS, dir_fd=parent_fd)
    except OSError as exc:
        if exc.errno in SYMLINK_OPEN_ERRNOS:
            return None, "not_a_regular_file"
        return None, failure_token(exc)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return None, "not_a_regular_file"
        return digest_of_descriptor(fd), None
    except OSError:
        return None, "unreadable"
    finally:
        close_descriptor(fd)


def split_components(raw):
    """Split a raw path into `(components, directory_required)`.

    Empty components and `.` are dropped. A trailing `/` or a final `.`
    requires the last remaining component to be a directory. `..` stays a
    component and is opened like any other directory.
    """
    parts = raw.split(b"/")
    components = [part for part in parts if part not in (b"", b".")]
    directory_required = parts[-1] in (b"", b".")
    return components, directory_required


def digest_of_path(raw):
    """Return `(digest, None)` or `(None, error_token)` for one raw path.

    The path is walked one component at a time from `/` (absolute argument)
    or the current directory (relative argument). Every directory on the way
    is opened relative to the previous directory's descriptor, directory-only
    and without following a symlink, so a symlink at any component stops the
    walk. The path is never resolved as one string. Each argument fails
    closed: any failure becomes that argument's error token. Every directory
    descriptor opened here is closed before this function returns.
    """
    if not raw:
        return None, "missing"
    components, directory_required = split_components(raw)

    try:
        current = os.open(
            b"/" if raw.startswith(b"/") else b".", DIRECTORY_OPEN_FLAGS
        )
    except OSError as exc:
        return None, failure_token(exc)
    try:
        for position, name in enumerate(components):
            is_last = position == len(components) - 1
            if is_last and not directory_required:
                return digest_of_entry(current, name)
            try:
                child = os.open(name, DIRECTORY_OPEN_FLAGS, dir_fd=current)
            except OSError as exc:
                if exc.errno in DIRECTORY_REFUSED_ERRNOS:
                    return None, directory_refusal_token(current, name)
                return None, failure_token(exc)
            previous, current = current, child
            close_descriptor(previous)
        # Every component was a directory (or none was left): the argument
        # names a directory, never a regular file.
        return None, "not_a_regular_file"
    finally:
        close_descriptor(current)


def build_element(path_text, digest, error):
    if error is None:
        return {"path": path_text, "sha256": digest}
    return {"path": path_text, "sha256": None, "error": error}


def run(argv):
    """Return the exit code; write the array only when it is complete."""
    absent = missing_capabilities()
    if absent:
        sys.stderr.write(
            "artifact-digest.py: error: this platform lacks a capability "
            "the path walk needs; no argument was processed\n"
            + "".join(f"  missing: {name}\n" for name in absent)
        )
        return 2

    if not argv:
        sys.stderr.write(USAGE)
        return 2

    # Handle every argument as the raw bytes it arrived as, so the result
    # does not depend on the locale or on the interpreter's text encodings.
    raw_paths = [os.fsencode(argument) for argument in argv]
    texts = []
    for position, raw in enumerate(raw_paths, start=1):
        try:
            texts.append(raw.decode("utf-8"))
        except UnicodeDecodeError:
            sys.stderr.write(
                f"artifact-digest.py: error: argument {position} is not "
                "valid UTF-8 and cannot be written to the JSON output\n"
            )
            return 2

    elements = []
    for text, raw in zip(texts, raw_paths):
        digest, error = digest_of_path(raw)
        elements.append(build_element(text, digest, error))

    payload = json.dumps(elements, ensure_ascii=False) + "\n"
    sys.stdout.buffer.write(payload.encode("utf-8"))
    sys.stdout.buffer.flush()
    return 1 if any("error" in element for element in elements) else 0


def main():
    try:
        return run(sys.argv[1:])
    except Exception as exc:  # unexpected: no array, exit 2
        sys.stderr.write(
            f"artifact-digest.py: internal error: "
            f"{type(exc).__name__}: {exc}\n"
        )
        return 2


if __name__ == "__main__":
    sys.exit(main())
