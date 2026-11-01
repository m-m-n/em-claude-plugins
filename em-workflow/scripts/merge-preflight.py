#!/usr/bin/env python3
"""merge-preflight.py -- decide, from the integration branch tip alone,
whether a feature may proceed to merging.

Contract: feature-docs/unattended-merge/IMPLEMENTATION.md (C1 script
conventions, C2 vocabularies, C4 merge-preflight) and
feature-docs/unattended-merge/tasks/task0002.md.

Usage:
  merge-preflight.py --project-root DIR --feature NAME

`--project-root` is any directory of the repository (the main working tree or
a linked worktree); the script reports the main working tree root.

Output: exactly one JSON object on one stdout line, exit 0 whenever a
decision was produced (stop outcomes included).

  {"outcome": "stop", "reason": <C2 code>, "detail": <text>}
  {"outcome": "proceed", "reason": null, "detail": "", "project_root": ...,
   "worktree_path": ..., "integration_branch": ..., "integration_tip": ...,
   "base_branch": ..., "commands": [{"component", "field", "command"}, ...],
   "review_round": <int or null>}

Exit codes: 0 decision produced; 2 missing or malformed arguments; 1 internal
failure (diagnostic on stderr, nothing on stdout).

Checks run in a fixed order and the first failure decides the stop reason:
  1. feature name pattern             -> invalid_feature_name
  2. integration branch exists        -> integration_branch_missing
  3. workflow.yaml at the branch tip  -> record_unreadable
  4. base_branch                      -> base_branch_invalid
  5. every step completed / skipped,
     verify's result is not fail      -> precondition_unmet
  6. latest review round findings     -> unresolved_findings / record_unreadable
  7. verification command approval    -> commands_unapproved

Boundaries (NFR4): workflow.yaml and the review round records are read from
the committed content of the integration branch tip, never from a working
tree, and parsed with safe YAML loading only. Only structured fields drive a
decision; free text in those files is never echoed and never followed. Every
value that reaches the output is validated first. The script writes nothing
(not the repository, not the approval store), runs git only for read
operations (rev-parse, cat-file, ls-tree) and never runs gh. Approval is read
through `hooks/bash_guard.py --list` of the plugin this script belongs to.

Approval rule (check 7): a verification command is approved when it is
approvable and its `str.strip()` value is a member of the set read through
`bash_guard.py --list`. That is the same trim bash_guard.py applies to stored
and incoming commands, so leading and trailing blanks never decide the verdict
differently from the hook. A command is approvable only when it is a string
with a valid component name and its raw value holds no line break and no CR;
the raw value is judged, so the trim cannot turn a multi line command into an
approved one. Inner whitespace is compared as is. The `command` carried in the
proceed output is the original, untrimmed string.
"""

import json
import os
import re
import subprocess
import sys

sys.dont_write_bytecode = True

PROG = "merge-preflight"

# C1 identifier rules.
FEATURE_RE = re.compile(r"[a-z0-9][a-z0-9-]*")
SHA_RE = re.compile(r"[0-9a-f]{40}")
BRANCH_CHARS_RE = re.compile(r"[A-Za-z0-9._/-]+")
BRANCH_MAX_LENGTH = 200

# Values that may be echoed into `detail`: step ids and statuses, stable ids,
# component names. Anything else is replaced by a fixed placeholder.
TOKEN_RE = re.compile(r"[A-Za-z0-9_.-]{1,64}")
STABLE_ID_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}")
COMPONENT_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}")
INVALID_ID = "<invalid-id>"
INVALID_COMPONENT = "<invalid-component>"

ROUND_FILE_RE = re.compile(r"round([1-9][0-9]*)\.yaml")
KNOWN_SEVERITIES = ("critical", "high", "medium", "low")
BLOCKING_SEVERITIES = ("critical", "high")
RESOLVED = ("fixed", "declined")
PASSING_STEP_STATUSES = ("completed", "skipped")
COMMAND_FIELDS = ("build_command", "test_command", "e2e_test_command")

GIT_TIMEOUT_SECONDS = 30
GUARD_TIMEOUT_SECONDS = 30
MAX_RECORD_BYTES = 8 * 1024 * 1024

# Environment variables that would redirect git away from the repository the
# caller named.
GIT_REDIRECT_VARIABLES = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_COMMON_DIR",
    "GIT_INDEX_FILE",
    "GIT_PREFIX",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_NAMESPACE",
)


class UsageError(Exception):
    """Missing or malformed arguments (exit 2)."""


class InternalFailure(Exception):
    """An unexpected failure (exit 1, diagnostic on stderr)."""


class Stop(Exception):
    """A decision to stop, with a C2 reason code."""

    def __init__(self, reason, detail=""):
        super().__init__(reason)
        self.reason = reason
        self.detail = detail


class ApprovalUnavailable(Exception):
    """The approval list could not be read."""


# -- arguments ----------------------------------------------------------------


def parse_args(argv):
    values = {}
    i = 0
    while i < len(argv):
        name, equals, value = argv[i].partition("=")
        if name not in ("--project-root", "--feature"):
            raise UsageError(f"unexpected argument: {name[:40]!r}")
        if name in values:
            raise UsageError(f"{name} given more than once")
        if equals:
            i += 1
        else:
            if i + 1 >= len(argv):
                raise UsageError(f"{name} needs a value")
            value = argv[i + 1]
            i += 2
        values[name] = value
    for required in ("--project-root", "--feature"):
        if required not in values:
            raise UsageError(f"{required} is required")
    project_root = values["--project-root"]
    if not project_root or not os.path.isabs(project_root):
        raise UsageError("--project-root must be an absolute path")
    return project_root, values["--feature"]


# -- child processes -----------------------------------------------------------


def child_env():
    env = dict(os.environ)
    for name in GIT_REDIRECT_VARIABLES:
        env.pop(name, None)
    env["GIT_OPTIONAL_LOCKS"] = "0"
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def run_git(directory, *args):
    """Run a read-only git command; return (returncode, stdout bytes)."""
    try:
        proc = subprocess.run(
            ["git", "-C", directory, *args],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=GIT_TIMEOUT_SECONDS,
            env=child_env(),
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise InternalFailure(f"git {args[0]} could not run: {type(exc).__name__}")
    return proc.returncode, proc.stdout


def git_text(directory, *args):
    returncode, out = run_git(directory, *args)
    if returncode != 0:
        return None
    try:
        return out.decode("utf-8").strip()
    except UnicodeDecodeError:
        return None


# -- repository ------------------------------------------------------------------


def resolve_integration(project_root_arg, feature):
    """Return (main working tree root, integration branch, tip sha)."""
    branch = f"em-workflow/{feature}/integration"
    tip = git_text(
        project_root_arg, "rev-parse", "--verify", "--quiet", f"refs/heads/{branch}^{{commit}}"
    )
    if tip is None:
        raise Stop(
            "integration_branch_missing",
            f"branch {branch} does not exist or the repository cannot be read",
        )
    if not SHA_RE.fullmatch(tip):
        raise InternalFailure("git returned an unexpected commit id for the integration branch")
    common_dir = git_text(project_root_arg, "rev-parse", "--path-format=absolute", "--git-common-dir")
    if not common_dir or not os.path.isabs(common_dir):
        raise InternalFailure("cannot determine the git common directory")
    if os.path.basename(common_dir) != ".git":
        raise InternalFailure("cannot derive the main working tree root from the git common directory")
    return os.path.dirname(common_dir), branch, tip


def read_record(root, tip, relative_path):
    """Committed content of a file at the tip, or None when absent/unreadable."""
    spec = f"{tip}:{relative_path}"
    returncode, out = run_git(root, "cat-file", "-s", spec)
    if returncode != 0:
        return None
    try:
        size = int(out.decode("ascii").strip())
    except (UnicodeDecodeError, ValueError):
        return None
    if size > MAX_RECORD_BYTES:
        return None
    returncode, data = run_git(root, "cat-file", "blob", spec)
    if returncode != 0:
        return None
    return data


def list_round_numbers(root, tip, feature):
    returncode, out = run_git(
        root, "ls-tree", "-z", "--name-only", "--full-tree", tip, "--", f"feature-docs/{feature}/reviews/"
    )
    if returncode != 0:
        raise InternalFailure("git ls-tree failed while listing review round records")
    numbers = []
    for raw in out.split(b"\0"):
        if not raw:
            continue
        try:
            name = raw.decode("utf-8")
        except UnicodeDecodeError:
            continue
        match = ROUND_FILE_RE.fullmatch(name.rsplit("/", 1)[-1])
        if match:
            numbers.append(int(match.group(1)))
    return numbers


# -- YAML -----------------------------------------------------------------------


def parse_yaml(data, label):
    try:
        import yaml
    except Exception:
        raise Stop("record_unreadable", "the YAML loader is unavailable")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise Stop("record_unreadable", f"{label} is not valid UTF-8")
    try:
        return yaml.safe_load(text)
    except Exception:
        raise Stop("record_unreadable", f"{label} is not parseable YAML")


# -- checks ------------------------------------------------------------------------


def valid_branch_name(value):
    if not isinstance(value, str) or not 0 < len(value) <= BRANCH_MAX_LENGTH:
        return False
    if not BRANCH_CHARS_RE.fullmatch(value):
        return False
    if value.startswith(("-", "/")) or value.endswith(("/", ".")):
        return False
    if "//" in value or ".." in value:
        return False
    return all(
        part and not part.startswith(".") and not part.endswith(".lock")
        for part in value.split("/")
    )


def safe_token(value, placeholder):
    if isinstance(value, str) and TOKEN_RE.fullmatch(value):
        return value
    return placeholder


def read_workflow(root, tip, feature):
    data = read_record(root, tip, f"feature-docs/{feature}/workflow.yaml")
    if data is None:
        raise Stop("record_unreadable", "workflow.yaml is absent or unreadable at the integration tip")
    doc = parse_yaml(data, "workflow.yaml")
    if not isinstance(doc, dict):
        raise Stop("record_unreadable", "workflow.yaml is not a mapping")
    steps = doc.get("workflow")
    if not isinstance(steps, list) or not steps or not all(isinstance(s, dict) for s in steps):
        raise Stop("record_unreadable", "the workflow list is not a non empty list of mappings")
    return doc


def check_base_branch(doc):
    value = doc.get("base_branch")
    if not valid_branch_name(value):
        raise Stop("base_branch_invalid", "base_branch is missing or not a valid branch name")
    return value


def check_precondition(doc):
    failing = []
    for step in doc["workflow"]:
        step_id = safe_token(step.get("id"), "?")
        status = step.get("status")
        if not (isinstance(status, str) and status in PASSING_STEP_STATUSES):
            if status is None:
                label = "missing"
            else:
                label = safe_token(status, "invalid")
            failing.append(f"{step_id}:{label}")
        if step.get("id") == "verify":
            result = step.get("result")
            if result is None or result == "pass":
                continue
            if isinstance(result, str) and result.strip().casefold() == "fail":
                failing.append("verify:result=fail")
            else:
                failing.append("verify:result=invalid")
    if failing:
        raise Stop("precondition_unmet", "steps not completed or skipped: " + ", ".join(failing))


def check_review_findings(root, tip, feature):
    """Judge the latest review round; return its number or None when there is none."""
    numbers = list_round_numbers(root, tip, feature)
    if not numbers:
        return None
    latest = max(numbers)
    data = read_record(root, tip, f"feature-docs/{feature}/reviews/round{latest}.yaml")
    malformed = Stop("record_unreadable", f"review round {latest} record is unreadable or malformed")
    if data is None:
        raise malformed
    record = parse_yaml(data, f"review round {latest} record")
    if not isinstance(record, dict) or not isinstance(record.get("findings"), list):
        raise malformed
    blocking = []
    for finding in record["findings"]:
        if not isinstance(finding, dict):
            raise malformed
        severity = finding.get("severity")
        if not isinstance(severity, str):
            raise malformed
        severity = severity.strip().casefold()
        if severity not in KNOWN_SEVERITIES:
            raise malformed
        if severity not in BLOCKING_SEVERITIES:
            continue
        resolution = finding.get("resolution")
        if isinstance(resolution, str) and resolution in RESOLVED:
            continue
        stable_id = finding.get("stable_id")
        if isinstance(stable_id, str) and STABLE_ID_RE.fullmatch(stable_id):
            label = stable_id
        else:
            label = INVALID_ID
        if label not in blocking:
            blocking.append(label)
    if blocking:
        raise Stop(
            "unresolved_findings",
            f"round{latest} unresolved critical/high findings: " + ", ".join(blocking),
        )
    return latest


def collect_commands(doc):
    """Non-empty verification commands, components in name order, fields in order.

    Each entry is (component label, field, command, approvable); an entry that
    cannot be approved by construction (invalid component name, non string or
    multi line command) is flagged rather than dropped.
    """
    malformed = Stop(
        "commands_unapproved",
        "the project components are malformed, so approval cannot be confirmed",
    )
    project = doc.get("project")
    if project is None:
        return []
    if not isinstance(project, dict):
        raise malformed
    components = project.get("components")
    if components is None:
        return []
    if not isinstance(components, dict):
        raise malformed
    entries = []
    for name, component in sorted(components.items(), key=lambda item: str(item[0])):
        if not isinstance(component, dict):
            raise malformed
        name_ok = isinstance(name, str) and COMPONENT_RE.fullmatch(name) is not None
        label = name if name_ok else INVALID_COMPONENT
        for field in COMMAND_FIELDS:
            command = component.get(field)
            if command is None:
                continue
            if isinstance(command, str):
                if not command.strip():
                    continue
                approvable = name_ok and "\n" not in command and "\r" not in command
            else:
                approvable = False
            entries.append((label, field, command, approvable))
    return entries


def read_approved_commands(project_root):
    guard = os.path.join(
        os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "hooks", "bash_guard.py"
    )
    interpreter = sys.executable or "python3"
    try:
        proc = subprocess.run(
            [interpreter, "-B", guard, "--list", "--project-dir", project_root],
            stdin=subprocess.DEVNULL,
            capture_output=True,
            timeout=GUARD_TIMEOUT_SECONDS,
            env=child_env(),
        )
    except (OSError, subprocess.SubprocessError):
        raise ApprovalUnavailable()
    if proc.returncode != 0:
        raise ApprovalUnavailable()
    try:
        text = proc.stdout.decode("utf-8")
    except UnicodeDecodeError:
        raise ApprovalUnavailable()
    return {line for line in text.split("\n") if line}


def check_approval(root, doc):
    entries = collect_commands(doc)
    if not entries:
        return []
    try:
        approved = read_approved_commands(root)
    except ApprovalUnavailable:
        raise Stop(
            "commands_unapproved", "the approval list could not be read, so approval cannot be confirmed"
        )
    unapproved = []
    for label, field, command, approvable in entries:
        # Compare the trimmed value, as bash_guard.py does for stored and
        # incoming commands. `approvable` already excludes every non string
        # and every raw value with a line break or CR, so the trim never
        # turns such a value into an approved one. Inner whitespace is not
        # normalized, and the emitted command below stays untrimmed.
        if approvable and command.strip() in approved:
            continue
        name = f"{label}.{field}"
        if name not in unapproved:
            unapproved.append(name)
    if unapproved:
        raise Stop("commands_unapproved", "verification commands not approved: " + ", ".join(unapproved))
    return [{"component": label, "field": field, "command": command} for label, field, command, _ in entries]


# -- decision ----------------------------------------------------------------------


def decide(project_root_arg, feature):
    if not FEATURE_RE.fullmatch(feature):
        raise Stop("invalid_feature_name", "the feature name does not match the feature pattern")
    root, branch, tip = resolve_integration(project_root_arg, feature)
    doc = read_workflow(root, tip, feature)
    base_branch = check_base_branch(doc)
    check_precondition(doc)
    review_round = check_review_findings(root, tip, feature)
    commands = check_approval(root, doc)
    return {
        "outcome": "proceed",
        "reason": None,
        "detail": "",
        "project_root": root,
        "worktree_path": os.path.join(
            root, ".claude", "worktrees", "em-workflow", feature, "integration"
        ),
        "integration_branch": branch,
        "integration_tip": tip,
        "base_branch": base_branch,
        "commands": commands,
        "review_round": review_round,
    }


def emit(result):
    sys.stdout.write(json.dumps(result, ensure_ascii=True) + "\n")
    sys.stdout.flush()


def main(argv):
    try:
        project_root, feature = parse_args(argv)
    except UsageError as exc:
        print(f"{PROG}: {exc}", file=sys.stderr)
        print(f"usage: {PROG}.py --project-root DIR --feature NAME", file=sys.stderr)
        return 2
    try:
        result = decide(project_root, feature)
    except Stop as stop:
        result = {"outcome": "stop", "reason": stop.reason, "detail": stop.detail}
    except InternalFailure as exc:
        print(f"{PROG}: internal failure: {exc}", file=sys.stderr)
        return 1
    except Exception as exc:  # fail closed: never print a decision after a crash
        print(f"{PROG}: internal failure: {type(exc).__name__}", file=sys.stderr)
        return 1
    emit(result)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
