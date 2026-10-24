#!/usr/bin/env python3
"""PreToolUse(Write|Edit|MultiEdit) guard against committing identifiers of
the user's machine or of external task trackers into workflow docs.

The rule lives in references/doc-redaction.md. This hook enforces the part
of it that a file write can show: a Notion URL, or an absolute path under the
user's home directory, in new content written under `feature-docs/` or
`test-docs/`.

Decision flow:

  1. Read stdin, parse as one JSON object. Any failure -> no output.
  2. tool_name must be Write, Edit, or MultiEdit, and tool_input.file_path a
     non-empty string with a `feature-docs` or `test-docs` path component.
     Otherwise -> no output.
  3. Collect the new content: Write `content`, Edit `new_string`, MultiEdit
     `edits[].new_string`. Text the edit leaves in place is not inspected.
  4. A Notion URL, or the home directory path followed by a path boundary,
     in that content -> deny. Anything else -> no output.

The guard only ever denies, never asks, so an unattended run gets the reason
back as a tool result and can rewrite the content.

Output: a PreToolUse permission decision on stdout; exit 0 either way.
"""

import json
import os
import re
import sys

HOOK_EVENT_NAME = "PreToolUse"
TOOLS = {"Write", "Edit", "MultiEdit"}
DOC_DIRS = {"feature-docs", "test-docs"}

NOTION_URL = re.compile(
    r"https?://(?:[A-Za-z0-9-]+\.)*notion\.(?:so|site|com)(?![A-Za-z0-9-])",
    re.IGNORECASE,
)

# A home directory shallower than this reveals no user name ("/", "/root").
MIN_HOME_DEPTH = 2


def home_pattern():
    home = os.path.normpath(os.environ.get("HOME", "") or "/")
    if len([p for p in home.split("/") if p]) < MIN_HOME_DEPTH:
        return None
    return re.compile(re.escape(home) + r"(?![A-Za-z0-9._-])")


def in_doc_dir(file_path):
    parts = file_path.replace("\\", "/").split("/")
    return any(p in DOC_DIRS for p in parts[:-1])


def new_content(tool_name, tool_input):
    if tool_name == "Write":
        texts = [tool_input.get("content")]
    elif tool_name == "Edit":
        texts = [tool_input.get("new_string")]
    else:
        edits = tool_input.get("edits")
        if not isinstance(edits, list):
            return ""
        texts = [e.get("new_string") for e in edits if isinstance(e, dict)]
    return "\n".join(t for t in texts if isinstance(t, str))


def findings(content):
    found = []
    if NOTION_URL.search(content):
        found.append("Notion の URL（`<notion-url>` に置き換えるか削る）")
    pattern = home_pattern()
    if pattern is not None and pattern.search(content):
        found.append(
            "ホームディレクトリの絶対パス（リポジトリルートからの相対パス、"
            "リポジトリの外なら `~/...` にする）"
        )
    return found


def emit_deny(file_path, found):
    reason = (
        "[doc-redaction-guard] "
        + file_path
        + " に書く内容に、コミットしてはいけないものが含まれています: "
        + " / ".join(found)
        + "。置き換えて書き直してください。規則は "
        "references/doc-redaction.md。"
    )
    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": HOOK_EVENT_NAME,
                "permissionDecision": "deny",
                "permissionDecisionReason": reason,
            }
        },
        sys.stdout,
        ensure_ascii=False,
    )


def main():
    try:
        payload = json.load(sys.stdin)
    except Exception:
        return
    if not isinstance(payload, dict) or payload.get("tool_name") not in TOOLS:
        return
    tool_input = payload.get("tool_input")
    if not isinstance(tool_input, dict):
        return
    file_path = tool_input.get("file_path")
    if not isinstance(file_path, str) or not file_path or not in_doc_dir(file_path):
        return
    found = findings(new_content(payload["tool_name"], tool_input))
    if found:
        emit_deny(file_path, found)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
