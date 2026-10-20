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


def digest_of_descriptor(fd):
    """sha256 of everything readable from `fd`, in bounded chunks."""
    hasher = hashlib.sha256()
    while True:
        chunk = os.read(fd, CHUNK_SIZE)
        if not chunk:
            break
        hasher.update(chunk)
    return "sha256:" + hasher.hexdigest()


def digest_of_path(path):
    """Return `(digest, None)` or `(None, error_token)` for one raw path.

    The path is inspected without following a symlink, so a FIFO, device or
    symlink is rejected before anything is opened. The open itself refuses a
    symlink and never waits, and the regular-file determination is repeated
    on the opened handle, which is the one that is read.
    """
    try:
        inspected = os.lstat(path)
    except OSError as exc:
        if exc.errno in NO_ENTRY_ERRNOS:
            return None, "missing"
        return None, "unreadable"
    if not stat.S_ISREG(inspected.st_mode):
        return None, "not_a_regular_file"

    try:
        fd = os.open(path, OPEN_FLAGS)
    except OSError as exc:
        if exc.errno in SYMLINK_OPEN_ERRNOS:
            return None, "not_a_regular_file"
        if exc.errno in NO_ENTRY_ERRNOS:
            return None, "missing"
        return None, "unreadable"
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            return None, "not_a_regular_file"
        return digest_of_descriptor(fd), None
    except OSError:
        return None, "unreadable"
    finally:
        os.close(fd)


def build_element(path_text, digest, error):
    if error is None:
        return {"path": path_text, "sha256": digest}
    return {"path": path_text, "sha256": None, "error": error}


def run(argv):
    """Return the exit code; write the array only when it is complete."""
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
