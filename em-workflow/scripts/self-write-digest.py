#!/usr/bin/env python3
"""Self-write digest identification and substitution (em-workflow plugin,
task0001 of feature-docs/worker-self-write-digest; FR1-FR7, FR10, FR11).

Identifies the paths one worker dispatch legitimately wrote (its self-write
set) from the orchestrator-observed change set, and builds the return-time
`digest_source` in which each of those paths carries its dispatch-time
digest. The orchestrator -- never a worker -- runs this script. The rule it
serves, the orchestrator-side procedure and the comparison that follows are
stated once, in `references/contracts/worker-envelope.md`, Rule R1,
"Recomputation and comparison timing". This module documents only the
command line.

CLI contract:
    python3 self-write-digest.py INPUT_DOCUMENT
  Exactly one argument: the path of the input document. The script defines
  no options: the argument is a file name even when it begins with `-`. Any
  other argument count is a usage error.

Input document: one UTF-8 JSON object whose `operation` member selects one
of two operations. A missing member, a member not listed for the selected
operation, or an unknown operation is invalid input.
  identify_and_substitute   members: dispatch_digest_source,
                            current_digest_source, observed_changes,
                            write_policy, allowed_write_roots
  substitute_only           members: current_digest_source,
                            dispatch_digest_inputs, self_write_set

Member shapes:
  dispatch_digest_source, current_digest_source
                  a mapping whose `digest_inputs` member is a mapping of
                  string path to string digest; its other members are
                  carried, never interpreted.
  observed_changes
                  a list of mappings with `path` (non-empty string) and
                  `kind` (`created`, `modified` or `deleted`); no path is
                  repeated.
  write_policy    the dispatch envelope's `write_policy` object; only its
                  `targets` list is read, each entry with `path`, `action`
                  (`create`, `replace_own`, `replace_authorized`,
                  `extend_only`, `regenerate` or `preserve`) and `source`
                  (required when the action is `regenerate`); no target
                  path is repeated.
  allowed_write_roots
                  the envelope's top-level list of strings. Roots and paths
                  are compared lexically, segment by segment.
  dispatch_digest_inputs
                  a mapping of string to string.
  self_write_set  a list of strings.

Output:
  stdout carries one JSON object, UTF-8 encoded whatever the locale,
  non-ASCII characters unescaped, followed by a newline, with two members:
    self_write_set  ascending, without duplicates; for `substitute_only`
                    the given set, sorted and de-duplicated
    digest_source   the substituted digest_source object

Exit codes:
    0   success
    2   usage error, invalid input, an input document that cannot be read
        or parsed, or an unexpected failure; a message on stderr and
        nothing on stdout

Isolation: standard library only. The script reads only the input document
(the paths named inside it need not exist and are never opened), computes no
hash, starts no child process and writes no file.
"""

import collections
import copy
import json
import sys

PROGRAM = "self-write-digest"

USAGE = (
    "usage: python3 self-write-digest.py INPUT_DOCUMENT\n"
    "  INPUT_DOCUMENT is the path of one UTF-8 JSON object whose `operation`\n"
    "  member is identify_and_substitute or substitute_only.\n"
    "  Prints one JSON object with self_write_set and digest_source.\n"
    "  Exit codes: 0 success, 2 usage error, invalid input or failure.\n"
)

ACTIONS = frozenset(
    {
        "create",
        "replace_own",
        "replace_authorized",
        "extend_only",
        "regenerate",
        "preserve",
    }
)
KINDS = frozenset({"created", "modified", "deleted"})

# Membership matrix: the change kinds each covering target action admits.
# `regenerate` is decided separately (it depends on its source), and a path
# that is not a target is judged against the allowed write roots.
TARGET_ADMITTED_KINDS = {
    "create": frozenset({"created"}),
    "replace_own": frozenset({"modified"}),
    "replace_authorized": frozenset({"modified"}),
    "extend_only": frozenset({"modified"}),
    "preserve": frozenset(),
}
ROOT_ADMITTED_KINDS = frozenset({"created"})

OPERATION_MEMBERS = {
    "identify_and_substitute": (
        "dispatch_digest_source",
        "current_digest_source",
        "observed_changes",
        "write_policy",
        "allowed_write_roots",
    ),
    "substitute_only": (
        "current_digest_source",
        "dispatch_digest_inputs",
        "self_write_set",
    ),
}

Target = collections.namedtuple("Target", ["action", "source"])


class InputError(ValueError):
    """The input is not acceptable: reported on stderr, exit 2."""


# ---------------------------------------------------------------- checks ----


def _describe(value):
    return type(value).__name__ if value is not None else "null"


def _check_str_map(value, where):
    """A mapping of string to string; returns it."""
    if not isinstance(value, dict):
        raise InputError(f"{where} must be a mapping, got {_describe(value)}")
    for key, item in value.items():
        if not isinstance(item, str):
            raise InputError(
                f"{where}[{key!r}] must be a string, got {_describe(item)}"
            )
    return value


def _check_str_list(value, where):
    """A list of strings; returns it."""
    if not isinstance(value, list):
        raise InputError(f"{where} must be a list, got {_describe(value)}")
    for index, item in enumerate(value):
        if not isinstance(item, str):
            raise InputError(
                f"{where}[{index}] must be a string, got {_describe(item)}"
            )
    return value


def _check_digest_source(value, where):
    """A mapping with a string-to-string `digest_inputs` member."""
    if not isinstance(value, dict):
        raise InputError(f"{where} must be a mapping, got {_describe(value)}")
    if "digest_inputs" not in value:
        raise InputError(f"{where} has no digest_inputs member")
    _check_str_map(value["digest_inputs"], f"{where}.digest_inputs")
    return value


def _check_observed_changes(value):
    """A list of {path, kind} mappings, no path repeated; returns
    [(path, kind), ...] in the given order."""
    where = "observed_changes"
    if not isinstance(value, list):
        raise InputError(f"{where} must be a list, got {_describe(value)}")
    changes = []
    seen = set()
    for index, entry in enumerate(value):
        label = f"{where}[{index}]"
        if not isinstance(entry, dict):
            raise InputError(f"{label} must be a mapping, got {_describe(entry)}")
        path = entry.get("path")
        if not isinstance(path, str) or not path:
            raise InputError(f"{label}.path must be a non-empty string")
        kind = entry.get("kind")
        if not isinstance(kind, str) or kind not in KINDS:
            raise InputError(
                f"{label}.kind must be one of {sorted(KINDS)}, got {kind!r}"
            )
        if path in seen:
            raise InputError(f"{where} repeats the path {path!r}")
        seen.add(path)
        changes.append((path, kind))
    return changes


def _check_write_policy(value):
    """`write_policy.targets` as a mapping of path to Target."""
    where = "write_policy"
    if not isinstance(value, dict):
        raise InputError(f"{where} must be a mapping, got {_describe(value)}")
    targets = value.get("targets")
    if not isinstance(targets, list):
        raise InputError(f"{where}.targets must be a list, got {_describe(targets)}")
    result = {}
    for index, entry in enumerate(targets):
        label = f"{where}.targets[{index}]"
        if not isinstance(entry, dict):
            raise InputError(f"{label} must be a mapping, got {_describe(entry)}")
        path = entry.get("path")
        if not isinstance(path, str) or not path:
            raise InputError(f"{label}.path must be a non-empty string")
        action = entry.get("action")
        if not isinstance(action, str) or action not in ACTIONS:
            raise InputError(
                f"{label}.action must be one of {sorted(ACTIONS)}, got {action!r}"
            )
        source = entry.get("source")
        if action == "regenerate":
            if not isinstance(source, str) or not source:
                raise InputError(
                    f"{label}.source is required for a regenerate target"
                )
        if path in result:
            raise InputError(f"{where}.targets repeats the path {path!r}")
        result[path] = Target(action, source if action == "regenerate" else None)
    return result


def _check_allowed_roots(value):
    """The allowed write roots as a list of segment tuples that can contain
    a relative path; a root that cannot (empty, absolute, or holding a `..`
    segment) is kept out and so admits nothing."""
    roots = []
    for root in _check_str_list(value, "allowed_write_roots"):
        if root.startswith("/"):
            continue
        segments = _segments(root)
        if not segments or ".." in segments:
            continue
        roots.append(segments)
    return roots


# ------------------------------------------------------------- operations ----


def _segments(path):
    """The path's segments, empty ones (doubled or trailing slashes) dropped,
    so a trailing slash never changes what a root or a path names."""
    return tuple(part for part in path.split("/") if part)


def _is_relative_and_clean(path):
    """False for an absolute path and for a path with a `..` segment."""
    return not path.startswith("/") and ".." not in path.split("/")


def _inside_a_root(path, roots):
    """Segment-wise containment: strictly inside, never the root itself."""
    parts = _segments(path)
    for root in roots:
        if len(parts) > len(root) and parts[: len(root)] == root:
            return True
    return False


def identify_self_writes(observed_changes, write_policy, allowed_write_roots):
    """The ascending, de-duplicated list of paths the membership matrix
    admits. Reads nothing but its three arguments."""
    changes = _check_observed_changes(observed_changes)
    targets = _check_write_policy(write_policy)
    roots = _check_allowed_roots(allowed_write_roots)

    members = set()
    regenerated = []
    for path, kind in changes:
        if not _is_relative_and_clean(path):
            continue
        covering = targets.get(path)
        if covering is None:
            if kind in ROOT_ADMITTED_KINDS and _inside_a_root(path, roots):
                members.add(path)
        elif covering.action == "regenerate":
            regenerated.append((path, kind, covering.source))
        elif kind in TARGET_ADMITTED_KINDS[covering.action]:
            members.add(path)

    # `regenerate` targets are decided after every other path: only a
    # modification, and only when the source itself was admitted above (so a
    # source that is itself a `regenerate` target never admits anything).
    admitted_sources = frozenset(members)
    for path, kind, source in regenerated:
        if kind == "modified" and source in admitted_sources:
            members.add(path)
    return sorted(members)


def substitute_self_writes(current_digest_source, dispatch_digest_inputs, self_write_set):
    """A new digest_source: the current one with every self-written path
    carrying its dispatch-time value (or absent when it was absent then).
    The inputs are never modified."""
    _check_digest_source(current_digest_source, "current_digest_source")
    _check_str_map(dispatch_digest_inputs, "dispatch_digest_inputs")
    paths = set(_check_str_list(self_write_set, "self_write_set"))

    result = copy.deepcopy(current_digest_source)
    inputs = dict(current_digest_source["digest_inputs"])
    for path in paths:
        if path in dispatch_digest_inputs:
            inputs[path] = dispatch_digest_inputs[path]
        else:
            inputs.pop(path, None)
    result["digest_inputs"] = {path: inputs[path] for path in sorted(inputs)}
    return result


def identify_and_substitute(
    dispatch_digest_source,
    current_digest_source,
    observed_changes,
    write_policy,
    allowed_write_roots,
):
    """Identification, then substitution with the dispatch digest_source's
    `digest_inputs` as the dispatch-time map. Returns
    (self_write_set, digest_source)."""
    _check_digest_source(dispatch_digest_source, "dispatch_digest_source")
    members = identify_self_writes(
        observed_changes, write_policy, allowed_write_roots
    )
    substituted = substitute_self_writes(
        current_digest_source, dispatch_digest_source["digest_inputs"], members
    )
    return members, substituted


# -------------------------------------------------------------------- CLI ----


def _reject_constant(name):
    raise ValueError(f"the constant {name} is not valid JSON")


def _read_document(path):
    try:
        with open(path, "rb") as handle:
            raw = handle.read()
    except OSError as exc:
        raise InputError(f"cannot read the input document: {exc}") from None
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise InputError("the input document is not valid UTF-8") from None
    try:
        document = json.loads(text, parse_constant=_reject_constant)
    except (ValueError, RecursionError) as exc:
        raise InputError(f"the input document is not valid JSON: {exc}") from None
    if not isinstance(document, dict):
        raise InputError("the input document must be a JSON object")
    return document


def _validate_document(document):
    """Check the whole document before any operation runs; returns
    (operation, members)."""
    operation = document.get("operation")
    if not isinstance(operation, str) or operation not in OPERATION_MEMBERS:
        raise InputError(
            f"operation must be one of {sorted(OPERATION_MEMBERS)}, "
            f"got {operation!r}"
        )
    expected = OPERATION_MEMBERS[operation]
    for name in expected:
        if name not in document:
            raise InputError(f"{operation}: the member {name} is missing")
    for name in document:
        if name != "operation" and name not in expected:
            raise InputError(f"{operation}: the member {name} is not accepted")

    if operation == "identify_and_substitute":
        _check_digest_source(document["dispatch_digest_source"], "dispatch_digest_source")
        _check_digest_source(document["current_digest_source"], "current_digest_source")
        _check_observed_changes(document["observed_changes"])
        _check_write_policy(document["write_policy"])
        _check_allowed_roots(document["allowed_write_roots"])
    else:
        _check_digest_source(document["current_digest_source"], "current_digest_source")
        _check_str_map(document["dispatch_digest_inputs"], "dispatch_digest_inputs")
        _check_str_list(document["self_write_set"], "self_write_set")
    return operation, {name: document[name] for name in expected}


def _run(operation, members):
    if operation == "identify_and_substitute":
        self_write_set, digest_source = identify_and_substitute(**members)
    else:
        self_write_set = sorted(set(members["self_write_set"]))
        digest_source = substitute_self_writes(
            members["current_digest_source"],
            members["dispatch_digest_inputs"],
            self_write_set,
        )
    return {"self_write_set": self_write_set, "digest_source": digest_source}


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
        operation, members = _validate_document(document)
        result = _run(operation, members)
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
        _fail(f"unexpected failure: {exc!r}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
