#!/usr/bin/env python3
"""Merge result renderer (em-workflow plugin, task0001 of
feature-docs/unattended-merge; FR21, NFR7, NFR8).

Turns a JSON input document into the one conformant result that ends a
`/em-workflow:merge --batch <feature>` run. The product-level contract -- the
key set and order, the vocabularies, the reason-code table, the value rules,
the confidentiality rule and the fixed fallback result -- is owned by
`references/merge-result.md`; the layout, quoting and escaping are those of
`references/batch-terminal-line.md` (its `## Result format` and `## Escaping`
sections). This module documents only the command line and carries the
constants the contract names.

Command line:
    python3 merge-result.py INPUT_JSON_PATH

Input document: one JSON object with the fields `result`, `feature`, `route`,
`reason`, `pr_url`, `merge_commit`, `worktree_removed` and `detail`, and the
optional `project_root` (used only to make paths repository-relative; never
printed). Any other key is ignored.

Output: stdout carries one result -- eight `key: "value"` lines -- and nothing
else. When the input document cannot be read, is not a JSON object, or breaks
a value rule, the result is `not_merged` / `internal_error` and its `detail`
names the failing field; the invalid value is never echoed.

Exit codes: 0 whenever a result was printed. 1 only when nothing could be
printed; the caller then prints the contract's fallback result verbatim.

The module imports only the standard library and calls nothing else.
"""

import json
import os
import re
import sys

KEYS = (
    "merge_result",
    "feature",
    "route",
    "reason",
    "pr_url",
    "merge_commit",
    "worktree_removed",
    "detail",
)

RESULT_VALUES = ("merged", "already_merged", "not_merged")
ROUTE_VALUES = ("pr", "local", "none")
REASON_CODES = (
    "invalid_arguments",
    "invalid_feature_name",
    "integration_branch_missing",
    "record_unreadable",
    "base_branch_invalid",
    "precondition_unmet",
    "unresolved_findings",
    "commands_unapproved",
    "remote_unresolved",
    "remote_not_github",
    "pr_closed",
    "pr_draft",
    "pr_conflicting",
    "pr_create_failed",
    "lock_busy",
    "lock_lost",
    "worktree_not_clean",
    "conflict_unattributable",
    "verification_failed",
    "push_rejected",
    "ci_failed",
    "ci_timeout",
    "pr_head_moved",
    "base_moving",
    "main_tree_not_ready",
    "merge_failed",
    "git_failed",
    "internal_error",
)

# Maximum length of `detail`, in characters, after normalization.
DETAIL_CAP = 1000
ELLIPSIS = "..."

# The fixed result the caller prints verbatim when this renderer cannot run.
# `references/merge-result.md` carries the same eight lines under
# `## Fallback result`.
FALLBACK_RESULT = "\n".join(
    [
        'merge_result: "not_merged"',
        'feature: ""',
        'route: "none"',
        'reason: "internal_error"',
        'pr_url: ""',
        'merge_commit: ""',
        'worktree_removed: "false"',
        'detail: "the merge result renderer could not run"',
    ]
)

NOTION_PLACEHOLDER = "<notion-url>"

# Input field name for each output key, in output order.
INPUT_FIELDS = (
    "result",
    "feature",
    "route",
    "reason",
    "pr_url",
    "merge_commit",
    "worktree_removed",
    "detail",
)

# What an invalid or missing field is replaced by in an `internal_error`
# result built from a document that broke a value rule.
DEFAULT_VALUES = {
    "feature": "",
    "route": "none",
    "pr_url": "",
    "merge_commit": "",
    "worktree_removed": "false",
}

FEATURE_PATTERN = re.compile(r"[a-z0-9][a-z0-9-]*")
SHA_PATTERN = re.compile(r"[0-9a-f]{40}")
# `https://` followed by characters an RFC 3986 URL may carry; no space, no
# control character, no double quote, no backslash.
PR_URL_PATTERN = re.compile(r"https://[A-Za-z0-9._~:/?#\[\]@!$&'()*+,;=%-]+")

# U+0000-U+001F, U+007F-U+009F, U+2028, U+2029, U+FFFE and U+FFFF are the
# characters `batch-terminal-line.md`'s `## Escaping` turns into `\uXXXX`;
# unpaired surrogates cannot be written as UTF-8 at all. `detail` turns every
# one of them into a space before escaping.
_DETAIL_CONTROL = re.compile("[\x00-\x1f\x7f-\x9f  ￾￿\ud800-\udfff]")
_ESCAPE_TARGET = re.compile('[\\\\"\x00-\x1f\x7f-\x9f  ￾￿]')
_NAMED_ESCAPES = {
    "\\": "\\\\",
    '"': '\\"',
    "\r": "\\r",
    "\n": "\\n",
    "\t": "\\t",
}
_SPACE_RUN = re.compile(" {2,}")

# A URL whose host is notion.so, notion.site, notion.com or a subdomain of
# them, with its port, path, query and fragment.
_NOTION_URL = re.compile(
    r"https?://(?:[A-Za-z0-9-]+\.)*notion\.(?:so|site|com)(?![A-Za-z0-9-])"
    r"(?::\d+)?(?:[/?#][^\s\"'<>\\)\]]*)?",
    re.IGNORECASE,
)

# A home directory shallower than this reveals no user name ("/", "/root").
_MIN_HOME_DEPTH = 2
# A path is only recognised when it does not continue a longer path or URL.
_BEFORE_PATH = r"(?<![A-Za-z0-9_.~-])"
_AFTER_PATH = r"(?![A-Za-z0-9._-])"
# Characters after which "<root>/" stands alone rather than starting a path.
_PATH_END = "\"'`)]}>,;:"

_UNREADABLE_DETAIL = "invalid renderer input: document unreadable or not JSON"
_NOT_OBJECT_DETAIL = "invalid renderer input: document is not a JSON object"
_ARGUMENTS_DETAIL = "invalid renderer input: expected exactly one document path"


def _escape(value):
    """`batch-terminal-line.md`'s `## Escaping`: one left-to-right pass that
    never re-processes a character it generated."""

    def one(match):
        char = match.group(0)
        named = _NAMED_ESCAPES.get(char)
        return named if named is not None else "\\u%04x" % ord(char)

    return _ESCAPE_TARGET.sub(one, value)


def _format(values):
    return "\n".join('%s: "%s"' % (key, _escape(values[key])) for key in KEYS)


def _normalize_directory(path, minimum_depth):
    """The absolute directory in normal form, or None when unusable."""
    if not isinstance(path, str) or not path.startswith("/"):
        return None
    normal = "/" + os.path.normpath(path).lstrip("/")
    parts = [part for part in normal.split("/") if part]
    if len(parts) < minimum_depth:
        return None
    return normal


def _home_directory():
    home = os.environ.get("HOME")
    if not home:
        expanded = os.path.expanduser("~")
        home = "" if expanded.startswith("~") else expanded
    return _normalize_directory(home, _MIN_HOME_DEPTH)


def _path_pattern(directory):
    return re.compile(_BEFORE_PATH + re.escape(directory) + _AFTER_PATH + "(/*)")


def _relative_to_root(match):
    following = match.string[match.end() : match.end() + 1]
    if match.group(1) and following and not following.isspace() and following not in _PATH_END:
        return ""
    return "."


def _redactor(project_root):
    """A function that applies `references/doc-redaction.md`'s replacements to
    one string: Notion URLs, then paths under the project root (repository
    relative), then paths under the home directory (`~/...`)."""
    root = _normalize_directory(project_root, 1)
    home = _home_directory()
    root_pattern = _path_pattern(root) if root else None
    home_pattern = _path_pattern(home) if home else None

    def redact(text):
        text = _NOTION_URL.sub(NOTION_PLACEHOLDER, text)
        if root_pattern is not None:
            text = root_pattern.sub(_relative_to_root, text)
        if home_pattern is not None:
            text = home_pattern.sub(lambda match: "~" + ("/" if match.group(1) else ""), text)
        return text

    return redact


def _normalize_detail(text):
    text = _DETAIL_CONTROL.sub(" ", text)
    text = _SPACE_RUN.sub(" ", text).strip(" ")
    if len(text) > DETAIL_CAP:
        text = text[: DETAIL_CAP - len(ELLIPSIS)] + ELLIPSIS
    return text


def _check_vocabulary(vocabulary):
    return lambda text: text if text in vocabulary else None


def _check_pattern(pattern):
    return lambda text: text if text == "" or pattern.fullmatch(text) else None


def _check_worktree_removed(raw):
    if raw is True or raw == "true":
        return "true"
    if raw is False or raw == "false":
        return "false"
    return None


# Per field: the check that turns a (redacted) string into its output value,
# or returns None when the value breaks the contract.
_CHECKS = {
    "result": _check_vocabulary(RESULT_VALUES),
    "feature": _check_pattern(FEATURE_PATTERN),
    "route": _check_vocabulary(ROUTE_VALUES),
    "reason": lambda text: text if text == "" or text in REASON_CODES else None,
    "pr_url": _check_pattern(PR_URL_PATTERN),
    "merge_commit": _check_pattern(SHA_PATTERN),
    "detail": _normalize_detail,
}

_OUTPUT_KEY = dict(zip(INPUT_FIELDS, KEYS))

_MISSING = object()


def _internal_error(valid, detail):
    values = dict(DEFAULT_VALUES)
    values.update({key: value for key, value in valid.items() if key in DEFAULT_VALUES})
    values["merge_result"] = "not_merged"
    values["reason"] = "internal_error"
    values["detail"] = detail
    return _format(values)


def render_result(data):
    """The result text (eight lines joined by LF, no trailing newline) for
    one input mapping. An input that breaks the contract renders as
    `not_merged` / `internal_error` whose detail names the first offending
    field in output order; no invalid value is ever echoed."""
    if not isinstance(data, dict):
        return _internal_error({}, _NOT_OBJECT_DETAIL)

    redact = _redactor(data.get("project_root"))
    values = {}
    first_problem = None
    for field in INPUT_FIELDS:
        value = _check_field(field, data.get(field, _MISSING), redact)
        if value is None:
            if first_problem is None:
                first_problem = field
        else:
            values[_OUTPUT_KEY[field]] = value

    if first_problem is None:
        has_reason = values["reason"] != ""
        if (values["merge_result"] == "not_merged") != has_reason:
            first_problem = "reason"

    if first_problem is not None:
        return _internal_error(values, "invalid renderer input: field " + first_problem)
    return _format(values)


def _check_field(field, raw, redact):
    if raw is _MISSING:
        return None
    if field == "worktree_removed":
        return _check_worktree_removed(raw)
    if not isinstance(raw, str):
        return None
    return _CHECKS[field](redact(raw))


def _load_document(path):
    """(mapping or other JSON value, None) on success; (None, detail) when
    the document cannot be read or parsed."""
    try:
        with open(path, "rb") as handle:
            raw = handle.read()
        return json.loads(raw.decode("utf-8")), None
    except (OSError, ValueError, RecursionError):
        return None, _UNREADABLE_DETAIL


def main(argv=None):
    args = sys.argv[1:] if argv is None else list(argv)
    try:
        if len(args) != 1:
            text = _internal_error({}, _ARGUMENTS_DETAIL)
        else:
            data, problem = _load_document(args[0])
            text = _internal_error({}, problem) if problem else render_result(data)
        payload = (text + "\n").encode("utf-8")
    except Exception:
        payload = (FALLBACK_RESULT + "\n").encode("utf-8")
    try:
        sys.stdout.buffer.write(payload)
        sys.stdout.buffer.flush()
    except (OSError, ValueError, AttributeError):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
