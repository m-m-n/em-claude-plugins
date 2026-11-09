#!/usr/bin/env python3
"""validate-worker-output.py -- worker output / packet / answer / patch /
phase-state validator for the em-workflow agent-separation feature.

Normative source: feature-docs/agent-separation/design-input.md 5.11.1,
5.11.2 and 5.11.5. This script implements the structural, revision and
cross-artifact validation layers (5.11.2 layers 1, 2, 3 and 6). Scope
verification, artifact verification and state-machine postconditions
(layers 4, 5, 7) are the orchestrator's responsibility (Bash) and are
deliberately NOT implemented here.

Deliberate non-goal: this is NOT a JSON Schema evaluator. The rules below are
written directly against the structures design-input.md defines, because a
partial JSON Schema implementation would diverge subtly on $ref resolution,
combinator semantics, formats and defaults (design-input.md 5.11.1).

Each `references/contracts/*.md` document renders the same rules in
human/LLM-readable form; the two are independent renderings of one rule set,
and `references/fixtures/` is what keeps them from drifting apart
(design-input.md 10.5). When you change a rule here, change the matching
contract prose too.

Exit codes: 0 = pass, 1 = validation failure (JSON detail on stdout),
2 = execution error (missing dependency, unreadable input, unknown --kind
or --worker, missing mandatory auxiliary input).
"""

import argparse
import copy
import hashlib
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    yaml = None


# ---------------------------------------------------------------------------
# Constants (design-input.md vocabularies)
# ---------------------------------------------------------------------------

WORKERS = (
    "requirements-analyst",
    "spec-writer",
    "implementation-planner",
    "rework-planner",
    "designer",
)

KINDS = (
    "worker-result",
    "question-packet",
    "answers",
    "workflow-patch",
    "phase-state",
)

STATUS_VALUES = {
    "needs_user_input",
    "completed",
    "blocked",
    "invalid_input",
    "stale_input",
    "failed",
}

WORKER_RUN_STATUS_VALUES = STATUS_VALUES | {"dispatched", "discarded_stale"}

PATCH_STATUS_VALUES = {"proposed", "validated", "applied", "rejected"}

PACKET_STATUS_VALUES = {"issued", "answered", "obsolete"}

PHASE_STATE_STATUS_VALUES = {
    "initialized",
    "dispatching",
    "awaiting_answers",
    "applying_patch",
    "completed",
    "failed",
}

# worker-digest-ownership/task0003: `design` is a registered phase -- the
# design step records its digests in phase-state/design.yaml
# (references/phase-state.md). The same vocabulary also backs the gate-ID
# phase prefix helper, which attributes a phase only to gates a worker
# contract's "Gate identifiers" section owns; none names a `design.` gate,
# so the gate registry is unchanged.
PHASE_VALUES = {"create-spec", "design", "create-plan", "review", "verify", "rework"}

# goal-vs-spec-divergence/task0029: the classification audit record's field
# vocabularies (references/phase-state.md's `classification` list entry;
# field set unchanged from task0005 -- only the record's shape and
# lifetime changed this round).
CLASSIFIER_VALUES = {"codex", "claude"}

CLASSIFICATION_VERDICT_VALUES = {"goal_not_met", "spec_gap", "not_applicable"}

CLASSIFICATION_DECISION_VALUES = {"proceed", "stop"}

CATEGORY_VALUES = {
    "feature-identity",
    "business-objective",
    "functional-requirement",
    "acceptance-criteria",
    "user-experience",
    "technical-requirement",
    "edge-case",
    "security",
    "dependency",
    "license",
    "testing",
    "design-step",
    "tbd-resolution",
    "existing-files",
    "artifact-overwrite",
    "rework",
    "spec-change",
    "completion",
    "other",
}

PRIORITY_VALUES = {"critical", "high", "normal", "low"}

ANSWER_MODE_VALUES = {"single_select", "multi_select", "freeform", "select_or_freeform"}

ON_UNANSWERED_VALUES = {"block", "record_tbd", "use_batch_policy"}

#  as8 (validator half): categories where NFR4 requires batch mode to abort
# rather than guess. A worker must not be able to disable that abort by
# choosing record_tbd / use_batch_policy for one of these categories.
BLOCKING_REQUIRED_CATEGORIES = {"spec-change", "security", "license"}

# rework-contract-drift/task0004 (FR6): the origin-identity pair's
# `origin_kind` half (references/rework-task-synthesis.md Invariant 6) is
# closed to these two values. Enforced wherever a `spec_change` record's
# `origin_kind` is read, mirroring the vocabulary enforcement `classifier`/
# `verdict`/`decision` already have below.
ORIGIN_KIND_VALUES = {"review", "verify"}

# rework-contract-drift/task0004 (FR3 validator half): the single closed
# value set for a verify-step failed_items[] entry's `category`
# (IMPLEMENTATION.md Shared Components "failed_items[].category
# vocabulary"; the field itself is defined once by references/
# workflow-schema.md, cited here, never restated in prose). Required and
# non-empty on every entry; a missing, empty or out-of-vocabulary value is
# rejected.
FAILED_ITEM_CATEGORY_VALUES = {
    "comprehensive",
    "spec",
    "security",
    "performance",
    "architecture",
    "license",
    "unknown",
}

ANSWER_SOURCE_VALUES = {
    "user",
    "batch-decision-table",
    "batch-codex-consultation",
    "batch-safe-default",
    # goal-vs-spec-divergence/task0025: the batch-only classification
    # gate's proceed outcome (references/question-resolution.md's
    # Classification gate, Outcome step; vocabulary SSOT is
    # references/question-packet-schema.md's `source` vocabulary).
    "batch-classification-gate",
}

IMPACT_VALUES = {"low", "medium", "high"}

OPERATION_VALUES = {"replace_planning", "append_rework"}

OPERATION_TASKS_PATCH_MODE = {
    "replace_planning": "replace_all",
    "append_rework": "append",
}

# plan-feature-docs-route/task0005 (FR4): `amend_other_feature` is the action
# that lets the implementation-planner modify one existing document of
# another feature (IMPLEMENTATION.md D2). Its admission rules and the other
# checks of the other-feature document route are implemented in the
# "Other-feature documents" section below.
AMEND_OTHER_FEATURE_ACTION = "amend_other_feature"

WRITE_POLICY_ACTIONS = {
    "create",
    "replace_own",
    "replace_authorized",
    "preserve",
    "extend_only",
    "regenerate",
    AMEND_OTHER_FEATURE_ACTION,
}

COMPLEXITY_VALUES = {"low", "medium", "high"}

# The route-back reset confirmation record
# (references/workflow-schema.md, "## `routeback_failed_journal_line`").
# Only the orchestrator writes it, in Step I.2.c's route-back write set; a
# worker's tasks_patch.entries entry may never carry the key, whatever its
# value (null included). The error code is the field name itself.
ROUTEBACK_RECORD_FIELD = "routeback_failed_journal_line"

REQUIREMENTS_PATCH_SET_KEYS = {
    "tasks_append",
    "tests_append",
    "tests_replace",
    "status",
    "tbd_reason",
    "excluded_reason",
}

PACKET_ID_RE = re.compile(r"^[a-z][a-z0-9-]*-q[0-9]{4}$")
QUESTION_ID_RE = re.compile(r"^[a-z][a-z0-9._-]*$")
PATCH_ID_RE = re.compile(r"^[a-z][a-z0-9-]*-p[0-9]{4}$")
TASK_ID_RE = re.compile(r"^task[0-9]+$")
REQUIREMENT_ID_RE = re.compile(r"^(FR|NFR)[1-9][0-9]*$")

PRESERVE_EXACT = {"workflow.implement.base_commit", "project.license"}
PRESERVE_PATTERNS = (
    re.compile(r"^workflow\.[a-z][a-z0-9_-]*\.completed_at_commit$"),
    re.compile(r"^tasks\.task[0-9]+\.status$"),
    re.compile(r"^tasks\.task[0-9]+\.branch$"),
)

REQUIRED_PRESERVE_BY_OPERATION = {
    "append_rework": {"workflow.implement.base_commit"},
    "replace_planning": set(),
}

# ---------------------------------------------------------------------------
# Worker capability table (design-input.md 5.3, 5.4.1-5.4.5)
# ---------------------------------------------------------------------------

WORKER_CAPABILITIES = {
    "requirements-analyst": {
        "full": dict(
            allowed_statuses=set(STATUS_VALUES),
            required_payload={"resolved_requirements", "project_detection", "design_system_candidates"},
            forbidden_payload=set(),
            has_workflow_patch=False,
        ),
        "design_system_detection": dict(
            allowed_statuses={"completed", "blocked", "failed"},
            required_payload={"design_system_candidates"},
            forbidden_payload={"resolved_requirements", "project_detection"},
            has_workflow_patch=False,
        ),
    },
    "spec-writer": {
        "_default": dict(
            allowed_statuses={"completed", "blocked", "invalid_input", "stale_input", "failed"},
            required_payload={"spec_index", "assumptions_written"},
            forbidden_payload=set(),
            has_workflow_patch=False,
        ),
    },
    "implementation-planner": {
        "_default": dict(
            allowed_statuses=set(STATUS_VALUES),
            required_payload={"task_index"},
            forbidden_payload=set(),
            has_workflow_patch=True,
        ),
    },
    "rework-planner": {
        "_default": dict(
            allowed_statuses=set(STATUS_VALUES),
            # shared_contract_rationale: rework-planner-contract.md:126 /
            # design-input.md 5.4.4 -- IMPLEMENTATION.md update-or-not is
            # not machine-judgeable, so the judgement rationale is always
            # required as a human-readable audit trail (as5).
            required_payload={"rework_index", "shared_contract_rationale"},
            forbidden_payload=set(),
            has_workflow_patch=True,
        ),
    },
    "designer": {
        "_default": dict(
            allowed_statuses={"completed", "blocked", "invalid_input", "stale_input", "failed"},
            required_payload={"design_summary"},
            forbidden_payload=set(),
            has_workflow_patch=False,
        ),
    },
}


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------

def err(code, message, **extra):
    d = {"code": code, "message": message}
    d.update(extra)
    return d


def prefix_errors(errors, prefix):
    out = []
    for e in errors:
        e = dict(e)
        e["message"] = f"{prefix}: {e['message']}"
        out.append(e)
    return out


class ExecutionError(Exception):
    """Raised for exit-code-2 conditions (not validation failures)."""


def load_yaml_or_json(path, what):
    """Read and parse a file as YAML (a superset of JSON). Missing/unreadable
    files are execution errors (exit 2); parse failures are reported to the
    caller so they can be surfaced as a layer-1 syntax validation failure
    (exit 1) instead."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ExecutionError(f"cannot read {what} file {path}: {exc}")
    return text


def parse_yaml_text(text):
    """Returns (obj, error_or_None). A parse failure is a syntax validation
    error, not an execution error."""
    try:
        return yaml.safe_load(text), None
    except yaml.YAMLError as exc:
        return None, str(exc)


def normalize_json_sha256(obj):
    """design-input.md 5.0 R1 normalization: sort keys, compact separators,
    do not escape non-ASCII, then sha256 the UTF-8 bytes."""
    text = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"


def is_safe_relative_path(path):
    """5.5.5 rule 7: files are project-relative; absolute paths, `..`
    segments and NUL bytes are rejected."""
    if not isinstance(path, str) or not path:
        return False
    if "\x00" in path:
        return False
    if path.startswith("/"):
        return False
    parts = path.replace("\\", "/").split("/")
    if any(p == ".." for p in parts):
        return False
    return True


def is_preserve_path_allowed(path):
    if path in PRESERVE_EXACT:
        return True
    return any(p.match(path) for p in PRESERVE_PATTERNS)


def path_segments(path):
    """Normalized posix-style segments for an already-safe relative path
    (see is_safe_relative_path). Empty and `.` segments (e.g. from a
    trailing slash) are dropped so they never participate in containment
    comparison."""
    return [p for p in path.replace("\\", "/").split("/") if p not in ("", ".")]


def path_is_contained_in_root(path, root):
    """5.11.3 / as6: `path` is contained in directory `root` only when
    root's segments are a STRICT prefix of path's segments. This is
    deliberately never a string-prefix comparison (`path.startswith(root)`),
    which wrongly admits a sibling directory whose name extends the root's
    name as a substring (`feature-docs/example2` is not contained in
    `feature-docs/example`; `feature-docs/example/design/mockups-evil` is
    not contained in `.../mockups`). Absolute paths, `..` segments, NUL
    bytes and non-string inputs are rejected on either side."""
    if not is_safe_relative_path(path) or not is_safe_relative_path(root):
        return False
    path_parts = path_segments(path)
    root_parts = path_segments(root)
    if not root_parts:
        return True
    return path_parts[: len(root_parts)] == root_parts and len(path_parts) > len(root_parts)


# ---------------------------------------------------------------------------
# Report artifact names (subagent-report-write-block/task0001, FR2 / FR3 / FR4)
#
# Claude Code rejects a subagent's Write by file name alone. A plan whose task
# `files` hold a NEW file with such a name stops the implementation, so the
# validator rejects it first. The pattern is implemented once, here. The
# rule's prose (FR1, with the regex literal) is owned by
# skills/plan-writing/SKILL.md, section "Report Artifact Names"; a test
# compares that literal with REPORT_ARTIFACT_NAME_RE, and no other document
# restates the regex.
#
# The base inputs (--target-repo, --base-commit) are read only after a
# matching name is found. A path from `files` is untrusted: it never reaches
# git as an argument. base_tree_entry walks the base commit's trees one level
# at a time with `git ls-tree` on object IDs git itself printed, and compares
# each name literally, so a path can neither act as an option, as pathspec
# magic (`:(top)`, `*`) nor as a revision expression (`^{tree}`, `~1`, `@{0}`).
# ---------------------------------------------------------------------------

REPORT_ARTIFACT_NAME_RE = re.compile(r"^(REPORT|SUMMARY|FINDINGS|ANALYSIS).*\.md$", re.IGNORECASE)
REPORT_NAME_ERROR_CODE = "report-name-new-file"

# A full object ID of a SHA-1 (40) or SHA-256 (64) repository, lowercase.
_FULL_HEX_ID_RE = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")

# Environment variables that select which repository, work tree, index or
# object store git reads. They are dropped so `git -C <target repo>` can only
# ever read the repository it was given.
_GIT_REPOSITORY_ENV_VARS = (
    "GIT_DIR",
    "GIT_WORK_TREE",
    "GIT_INDEX_FILE",
    "GIT_OBJECT_DIRECTORY",
    "GIT_ALTERNATE_OBJECT_DIRECTORIES",
    "GIT_COMMON_DIR",
    "GIT_NAMESPACE",
    "GIT_PREFIX",
    "GIT_QUARANTINE_PATH",
    "GIT_CEILING_DIRECTORIES",
    "GIT_DISCOVERY_ACROSS_FILESYSTEM",
    "GIT_REPLACE_REF_BASE",
    "GIT_NO_REPLACE_OBJECTS",
    "GIT_GRAFT_FILE",
    "GIT_SHALLOW_FILE",
)

_GIT_TIMEOUT_SECONDS = 120


def is_report_artifact_name(path):
    """FR2: True only for a string whose last normalized path segment
    (path_segments: `\\` as `/`, empty and `.` segments dropped) is a report
    artifact name. Only that segment is judged -- directory names never are --
    and the whole segment must match: a trailing line break is not part of a
    name the Write check sees. Any non-string input is False."""
    if not isinstance(path, str):
        return False
    segments = path_segments(path)
    if not segments:
        return False
    return REPORT_ARTIFACT_NAME_RE.fullmatch(segments[-1]) is not None


def _git_environment():
    return {k: v for k, v in os.environ.items() if k not in _GIT_REPOSITORY_ENV_VARS}


def _run_git(target_repo, *args):
    """Runs `git -C <target_repo> <args>` without a shell and returns the
    completed process (bytes). A git that cannot be run is an execution
    error, never a pass."""
    try:
        return subprocess.run(
            ["git", "-C", str(target_repo), *args],
            capture_output=True,
            env=_git_environment(),
            timeout=_GIT_TIMEOUT_SECONDS,
            check=False,
        )
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        raise ExecutionError(f"cannot run git for the report-name base check: {exc}")


def require_report_name_base(target_repo, base_commit):
    """FR4 input check. Called only after a report artifact name was found.
    Raises ExecutionError (exit 2) when a value is missing, the commit is not
    a full lowercase hexadecimal ID (40 or 64 digits -- never a revision
    expression, abbreviation or option), the repository is unusable, or the
    commit does not resolve to a commit object in it. Returns nothing."""
    if target_repo is None or str(target_repo) == "":
        raise ExecutionError(
            "--target-repo is required when a task's files hold a report artifact name "
            "(skills/plan-writing/SKILL.md, Report Artifact Names)"
        )
    if base_commit is None or base_commit == "":
        raise ExecutionError(
            "--base-commit is required when a task's files hold a report artifact name "
            "(skills/plan-writing/SKILL.md, Report Artifact Names)"
        )
    if not isinstance(base_commit, str) or _FULL_HEX_ID_RE.fullmatch(base_commit) is None:
        raise ExecutionError(
            "--base-commit must be a full lowercase hexadecimal commit ID (40 or 64 digits); "
            "a branch name, abbreviation or revision expression is not accepted"
        )
    repo = Path(str(target_repo))
    if not repo.is_dir():
        raise ExecutionError(f"--target-repo {repo} is not a directory")
    proc = _run_git(repo, "cat-file", "-t", base_commit)
    if proc.returncode != 0 or proc.stdout.strip() != b"commit":
        raise ExecutionError(
            f"--base-commit {base_commit} does not resolve to a commit in --target-repo {repo}"
        )


def _list_git_tree(target_repo, tree_id):
    """The entries of one tree object: {name (bytes): (mode, type, id)}.
    `tree_id` is the verified base commit or an object ID git printed itself,
    never text from a patch."""
    if _FULL_HEX_ID_RE.fullmatch(tree_id) is None:
        raise ExecutionError(f"refusing to list a tree that is not a full object ID: {tree_id!r}")
    proc = _run_git(target_repo, "ls-tree", "-z", tree_id)
    if proc.returncode != 0:
        raise ExecutionError(f"git ls-tree failed for {tree_id} in --target-repo {target_repo}")
    entries = {}
    for record in proc.stdout.split(b"\0"):
        if not record:
            continue
        meta, separator, name = record.partition(b"\t")
        fields = meta.split(b" ")
        if not separator or len(fields) != 3:
            raise ExecutionError(f"unreadable git ls-tree record for {tree_id}")
        entries[name] = (fields[0], fields[1], fields[2].decode("ascii", "replace"))
    return entries


def base_tree_entry(target_repo, base_commit, path):
    """What `path` is at the base commit: "regular" (a non-symlink file),
    "other" (a directory, symlink or submodule) or "absent".

    Pre: the base passed require_report_name_base and the path passed
    is_safe_relative_path (a path that did not is "absent"). The path is
    normalized with path_segments and compared as literal text against the
    names git lists; it is never passed to git (see the section comment
    above). An intermediate entry that is not a directory, a symlink included,
    makes the path absent."""
    if not is_safe_relative_path(path):
        return "absent"
    segments = path_segments(path)
    if not segments:
        return "absent"
    tree_id = base_commit
    last = len(segments) - 1
    for depth, segment in enumerate(segments):
        try:
            wanted = segment.encode("utf-8", "surrogateescape")
        except UnicodeEncodeError:
            return "absent"  # not representable as a git tree entry name
        entry = _list_git_tree(target_repo, tree_id).get(wanted)
        if entry is None:
            return "absent"
        mode, entry_type, entry_id = entry
        if depth == last:
            if entry_type == b"blob" and mode != b"120000":
                return "regular"
            return "other"
        if entry_type != b"tree":
            return "absent"
        tree_id = entry_id
    return "absent"  # pragma: no cover - the loop always returns


def find_report_name_violations(files_by_task, target_repo, base_commit):
    """FR3 judgment over a task-to-files mapping. Returns [(task_id, path)]
    in task then file order, one pair per distinct violation.

    Entries that are not strings, or are not safe relative paths, are skipped:
    the entry validation reports them. The base inputs are read only when a
    report artifact name is present. A matching name is a violation unless it
    is a regular file at the base commit (an update, not a new file)."""
    candidates = []
    seen = set()
    for task_id, files in files_by_task.items():
        if not isinstance(files, (list, tuple)):
            continue
        for path in files:
            if not isinstance(path, str) or not is_safe_relative_path(path):
                continue
            if not is_report_artifact_name(path):
                continue
            if (task_id, path) in seen:
                continue
            seen.add((task_id, path))
            candidates.append((task_id, path))
    if not candidates:
        return []
    require_report_name_base(target_repo, base_commit)
    return [
        (task_id, path)
        for task_id, path in candidates
        if base_tree_entry(target_repo, base_commit, path) != "regular"
    ]


def _report_name_errors(entries, target_repo, base_commit):
    files_by_task = {
        task_id: entry.get("files") for task_id, entry in entries.items() if isinstance(entry, dict)
    }
    return [
        err(
            REPORT_NAME_ERROR_CODE,
            f"tasks_patch.entries[{task_id}].files entry {path!r} has a report artifact name and "
            "is not a regular file at the base commit; a new file with such a name is rejected "
            "by Claude Code's Write (skills/plan-writing/SKILL.md, Report Artifact Names)",
            task_id=task_id,
            path=path,
        )
        for task_id, path in find_report_name_violations(files_by_task, target_repo, base_commit)
    ]


# ---------------------------------------------------------------------------
# Markdown structural parsing (design-input.md 5.11.1 "Markdown 解析の範囲")
#
# Limited to the four existing template markers; no new markers are
# introduced and free-form prose is never semantically parsed.
# ---------------------------------------------------------------------------

_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_BACKTICK_RE = re.compile(r"`([^`]+)`")
_BULLET_RE = re.compile(r"^[ \t]*-\s+(.*)$", re.MULTILINE)
# Scenario ID grammar: the TS-n form (TS, one hyphen, digits) and the TSn form
# (TS immediately followed by digits). All consecutive digits are consumed.
# IDs are literal strings; neither form is normalized into the other.
_TS_ID_RE = re.compile(r"TS-?\d+")


def _strip_noise(text):
    """Removes fenced code blocks and HTML comments before structural
    parsing, per 5.11.1 ("HTML コメントと fenced code block 内は解析対象外")."""
    text = _FENCE_RE.sub("", text)
    text = _HTML_COMMENT_RE.sub("", text)
    return text


def extract_markdown_section(text, heading, next_headings):
    """Returns the substring from `heading` (exclusive of the heading line)
    up to whichever of `next_headings` occurs first after it, or end of
    text. Returns None if `heading` is absent."""
    idx = text.find(heading)
    if idx == -1:
        return None
    start = idx + len(heading)
    end = len(text)
    for nh in next_headings:
        nidx = text.find(nh, start)
        if nidx != -1:
            end = min(end, nidx)
    return text[start:end]


def extract_task_plan_files(markdown_text):
    """Files to Create / Files to Modify bullets, per
    references/templates/task-plan.md. Each bullet must carry exactly one
    backtick-quoted path; zero or 2+ is a validation error. Returns
    (paths: set[str], errors: list[str])."""
    text = _strip_noise(markdown_text)
    paths = set()
    errors = []
    for heading, stop_headings in (
        ("### Files to Create", ("### Files to Modify", "## Design", "## Scope")),
        ("### Files to Modify", ("## Design", "## Acceptance Criteria", "## Scope")),
    ):
        section = extract_markdown_section(text, heading, stop_headings)
        if section is None:
            continue
        for bullet in _BULLET_RE.findall(section):
            tokens = _BACKTICK_RE.findall(bullet)
            if len(tokens) == 0:
                errors.append(f"bullet without a backtick-quoted path: {bullet.strip()!r}")
            elif len(tokens) > 1:
                errors.append(f"bullet with multiple backtick-quoted paths: {bullet.strip()!r}")
            else:
                paths.add(tokens[0])
    return paths, errors


def task_plan_has_acceptance_criteria(markdown_text):
    text = _strip_noise(markdown_text)
    section = extract_markdown_section(
        text, "## Acceptance Criteria (MANDATORY)", ("## Test Notes", "## Out of Scope")
    )
    if section is None:
        return False
    return bool(_BULLET_RE.search(section))


def implementation_md_has_shared_components(markdown_text):
    text = _strip_noise(markdown_text)
    return "## Shared Components" in text


def extract_verification_scenario_ids(markdown_text):
    """### Test Scenarios from SPEC.md under ## Test Verification ->
    scenario IDs in either accepted form: TS-<n> (hyphenated) or TS<n>
    (hyphen-less). IDs are literal strings; the two forms are not
    normalized into one another, so TS13 and TS-13 are distinct IDs."""
    text = _strip_noise(markdown_text)
    section = extract_markdown_section(
        text, "### Test Scenarios from SPEC.md", ("## ", "### ")
    )
    if section is None:
        # Section may run to end of file / no further heading.
        idx = text.find("### Test Scenarios from SPEC.md")
        if idx == -1:
            return set()
        section = text[idx:]
    return set(_TS_ID_RE.findall(section))


# ---------------------------------------------------------------------------
# Gate registry (bs2, round 2, validator half): binds a question's `gate_id`
# to the worker, phase, category and option identifiers permitted for it, so
# a worker cannot launder a sensitive question through a permissive gate_id
# borrowed from an unrelated decision point. Two independent derivations
# combine, neither one restating a table this script does not own (AC-2):
#
# 1. category -- a gate_id's suffix (the part after its first '.') is
#    checked against CATEGORY_VALUES, this script's own vocabulary constant.
#    When the suffix names an existing category exactly, that is the only
#    category a question carrying this gate_id may declare. This needs no
#    document parsing.
# 2. worker + phase + required option_id -- derived ONLY for gate_ids that a
#    contract's own "## Gate identifiers" section attributes to that
#    worker (currently analyst-contract.md's two entries). A gate_id
#    without such an attribution stays worker/phase-unconstrained: most
#    gate_policies entries in batch-policies.yaml are raised by the
#    ORCHESTRATOR rather than any worker's own question_packet
#    (spec-writer-contract.md's `{phase}.artifact-overwrite`,
#    designer-contract.md's `design-system.reclassify`), so binding them to
#    a specific worker here would be a guess this script cannot verify, not
#    a derivation. batch-policies.yaml's `option_id` (present when a gate's
#    action is `select`) is likewise only enforced for worker-attributed
#    gates -- the wider fixture corpus reuses other gate_ids as a generic
#    placeholder across many option vocabularies unrelated to the real
#    policy, so enforcing it universally would reject those, not the
#    laundering this registry exists to catch.
# ---------------------------------------------------------------------------

CONTRACT_FILE_TO_WORKER = {
    "analyst-contract.md": "requirements-analyst",
    "spec-writer-contract.md": "spec-writer",
    "planner-contract.md": "implementation-planner",
    "rework-planner-contract.md": "rework-planner",
    "designer-contract.md": "designer",
}

GATE_ID_SHAPE_RE = re.compile(r"^[a-z][a-z0-9-]*\.[a-z][a-z0-9-]*$")


def _category_for_gate_id(gate_id):
    if not isinstance(gate_id, str) or "." not in gate_id:
        return None
    suffix = gate_id.split(".", 1)[1]
    return suffix if suffix in CATEGORY_VALUES else None


def _phase_for_gate_id(gate_id):
    if not isinstance(gate_id, str) or "." not in gate_id:
        return None
    prefix = gate_id.split(".", 1)[0]
    return prefix if prefix in PHASE_VALUES else None


def _worker_gate_ids_from_contracts(contracts_dir):
    """Parses each contract's own "## Gate identifiers" section (currently
    only analyst-contract.md has one) for gate_id-shaped backtick tokens,
    attributing each to that file's worker via CONTRACT_FILE_TO_WORKER.
    Missing contracts_dir / files are tolerated (returns {}) -- this is a
    best-effort enrichment on top of the category-only binding above, not a
    hard dependency."""
    result = {}
    if contracts_dir is None or not contracts_dir.is_dir():
        return result
    for path in sorted(contracts_dir.glob("*.md")):
        worker = CONTRACT_FILE_TO_WORKER.get(path.name)
        if worker is None:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            continue
        section = extract_markdown_section(_strip_noise(text), "## Gate identifiers", ("## ",))
        if section is None:
            continue
        for token in _BACKTICK_RE.findall(section):
            if GATE_ID_SHAPE_RE.match(token):
                result[token] = worker
    return result


def _gate_option_ids_from_policies(references_dir):
    """references/batch-policies.yaml's gate_policies -- when a gate's
    action is `select` and it names an option_id, question-resolution.md
    rule 4 requires that option_id to actually be among the question's own
    options[].option_id. Returns {gate_id: option_id}."""
    result = {}
    if references_dir is None:
        return result
    path = references_dir / "batch-policies.yaml"
    if not path.is_file():
        return result
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return result
    data, parse_err = parse_yaml_text(text)
    if parse_err or not isinstance(data, dict):
        return result
    for gate_id, policy in (data.get("gate_policies") or {}).items():
        if isinstance(policy, dict) and policy.get("action") == "select" and policy.get("option_id"):
            result[gate_id] = policy["option_id"]
    return result


def build_gate_registry(references_dir):
    """Combines the two derivations above into one gate_id -> constraint
    mapping. `references_dir` is the plugin's own `em-workflow/references/`
    directory (contains `batch-policies.yaml` and `contracts/`). Returns {}
    when references_dir is None or does not exist -- callers degrade to no
    gate-registry enforcement rather than erroring, since this is a
    defense-in-depth check layered on top of the existing structural rules."""
    if references_dir is None:
        return {}
    option_ids = _gate_option_ids_from_policies(references_dir)
    worker_by_gate = _worker_gate_ids_from_contracts(references_dir / "contracts")

    gate_ids = set(option_ids) | set(worker_by_gate)
    policies_path = references_dir / "batch-policies.yaml"
    if policies_path.is_file():
        try:
            data, parse_err = parse_yaml_text(policies_path.read_text(encoding="utf-8"))
        except OSError:
            data, parse_err = None, "unreadable"
        if not parse_err and isinstance(data, dict):
            gate_ids |= set((data.get("gate_policies") or {}).keys())

    registry = {}
    for gate_id in gate_ids:
        worker = worker_by_gate.get(gate_id)
        registry[gate_id] = dict(
            worker=worker,
            phase=_phase_for_gate_id(gate_id) if worker else None,
            category=_category_for_gate_id(gate_id),
            required_option_id=option_ids.get(gate_id) if worker else None,
        )
    return registry


def _gate_ids_for_category(gate_registry, category):
    """goal-vs-spec-divergence/task0024 (AC-4/AC-5): the reverse of
    `_category_for_gate_id` -- every gate_id in `gate_registry` a contract's
    own "## Gate identifiers" section attributes to a worker (never an
    orchestrator-opened, worker-unattributed gate_id -- see
    `_worker_gate_ids_from_contracts`'s docstring for why that distinction
    matters) AND whose suffix derives exactly `category`. `rework.spec-change`
    lands here once `rework-planner-contract.md`'s own section attributes it
    (this is what AC-4 requires: the registry entry, not a restated
    sentence). Returns an empty set for a `category` with no such
    worker-attributed gate_id -- callers must treat that as "no
    category -> gate_id constraint today", never as "reject every gate_id",
    so an as-yet-unattributed category stays unconstrained rather than
    universally rejected."""
    if not category:
        return set()
    return {
        gate_id
        for gate_id, entry in (gate_registry or {}).items()
        if entry.get("worker") is not None and entry.get("category") == category
    }


# ---------------------------------------------------------------------------
# extend_only comparability (design-input.md 5.4.2)
#
# The worker itself is the one that performs the extend_only key-preservation
# comparison and returns `blocked` when it is uncomparable -- this script has
# no CLI channel that carries the actual before/after file content for an
# arbitrary write_policy target (the auxiliary-argument list in 5.11.1 has no
# "current project root" argument), so validate-worker-output.py cannot
# independently re-run that comparison against real files. This helper
# implements the SAME "comparable?" test as a reusable, independently unit
# testable primitive, for the worker/contract side of this rule to share --
# see the Test Notes edge case in feature-docs/agent-separation/tasks/
# task0008.md ("an extend_only target whose YAML contains an alias or merge
# key ... reported as uncomparable rather than silently accepted").
# ---------------------------------------------------------------------------

def yaml_extend_only_comparable(text):
    """Returns True if `text` parses as YAML into a mapping with no alias or
    merge-key node anywhere in the document (safe to key-compare). Returns
    False ("uncomparable") for non-mapping documents, alias reuse, or an
    explicit merge key (`<<`).

    PyYAML's `compose()` resolves anchors/aliases by reusing the SAME Node
    object at every point an alias refers back to it (there is no distinct
    "AliasNode" surviving into the composed tree) -- so alias detection here
    is "this exact node object was already visited elsewhere in the tree",
    tracked by python object id() across the recursive walk.
    """
    if yaml is None:
        raise ExecutionError("PyYAML is required")
    try:
        node = yaml.compose(text)
    except yaml.YAMLError:
        return False
    if node is None or not isinstance(node, yaml.MappingNode):
        return False
    return _subtree_alias_free(node, set())


def _subtree_alias_free(node, seen_ids):
    if id(node) in seen_ids:
        return False  # same node object reached twice => alias reuse
    seen_ids.add(id(node))
    if isinstance(node, yaml.MappingNode):
        for key_node, value_node in node.value:
            if isinstance(key_node, yaml.ScalarNode) and key_node.value == "<<":
                return False
            if not _subtree_alias_free(key_node, seen_ids):
                return False
            if not _subtree_alias_free(value_node, seen_ids):
                return False
        return True
    if isinstance(node, yaml.SequenceNode):
        return all(_subtree_alias_free(item, seen_ids) for item in node.value)
    return True


# ---------------------------------------------------------------------------
# Registries (design-input.md 5.5.5 rules 8-9)
# ---------------------------------------------------------------------------

def load_skills_vocabulary(registries_dir):
    path = registries_dir / "impl-skills.yaml"
    text = load_yaml_or_json(path, "registries/impl-skills.yaml")
    data, parse_err = parse_yaml_text(text)
    if parse_err:
        raise ExecutionError(f"cannot parse {path}: {parse_err}")
    skills = (data or {}).get("skills") or []
    return {s.get("name") for s in skills if isinstance(s, dict) and s.get("name")}


def load_domains_vocabulary(registries_dir):
    """references/review-rules.yaml is the domains SSOT (5.5.6), but the
    vocabulary itself lives only in a header comment there (no task in this
    feature adds a machine-readable `domains:` key to that file -- see
    IMPLEMENTATION.md 6.2). Parse the comment block rather than duplicating
    the list as a script-side constant, so this stays a single SSOT.

    as15: the block must terminate the SAME way
    check-plugin-invariants.py's extract_domains_from_review_rules() does --
    on the next `... vocabulary` marker line (e.g. `# complexity
    vocabulary: ...`) -- otherwise this parser keeps consuming past the
    domains block and absorbs complexity values ('low' / 'medium' / 'high')
    into the domain vocabulary."""
    path = registries_dir / "review-rules.yaml"
    text = load_yaml_or_json(path, "registries/review-rules.yaml")
    tokens = []
    in_block = False
    for line in text.splitlines():
        stripped = line.strip()
        if not in_block:
            if "domains vocabulary" in stripped.lower():
                in_block = True
            continue
        if not stripped.startswith("#"):
            break
        content = stripped.lstrip("#").strip()
        if not content:
            break
        if "vocabulary" in content.lower():
            break
        tokens.extend(t.strip() for t in content.split("/") if t.strip())
    return {t for t in tokens if re.fullmatch(r"[a-z][a-z-]*", t)}


# ---------------------------------------------------------------------------
# workflow.yaml access helpers (read-only; used for cross-reference and
# --dry-run-apply checks against a caller-supplied workflow.yaml)
# ---------------------------------------------------------------------------

def workflow_step_ids(workflow):
    return {s.get("id") for s in (workflow or {}).get("workflow", []) if isinstance(s, dict)}


def workflow_find_step(workflow, step_id):
    for s in (workflow or {}).get("workflow", []):
        if isinstance(s, dict) and s.get("id") == step_id:
            return s
    return None


# AC-1/AC-2 (task0017, review round 2 rework); wording updated task0022
# (review round 3, consumed-flag-split): the mandatory fields references/
# phase-state.md defines for a `spec_change` record eligible for
# re-planning. `replan_authorized` is checked separately below (its own
# boolean-type + True check) -- it is the flag that carries the
# re-planning authorization judgement. `consumed` is never consulted here
# (references/phase-state.md's `spec_change` flag pair).
#
# goal-vs-spec-divergence/task0029: `origin_kind` / `origin_id` replace
# the retired single-field origin identifier -- the origin pair defined in
# references/rework-task-synthesis.md (Spec-change origin identity). Presence/
# non-emptiness is all this check requires; a `verify`-sourced record
# (`origin_kind: verify`) satisfies it on the same terms as a
# `review`-sourced one (D13) -- neither value is special-cased here.
SPEC_CHANGE_MANDATORY_FIELDS = ("reason", "origin_kind", "origin_id", "recorded_at_commit")


def _load_rework_phase_state_from_dir(feature_dir):
    """Loads `{feature_dir}/phase-state/rework.yaml` -- one of the two
    equally valid sources for the re-planning path's re-entry signal
    (workflow-patch.md's `replace_all` permission conditions, second case).
    This is the form create-plan-phase.md's canonical invocation actually
    produces: `--phase-state` there points at `phase-state/create-plan.yaml`
    (the create-plan phase's own state), never at rework.yaml directly, so
    the signal has to be read from this path instead. Tolerates a missing
    `feature_dir`, a missing file, an unreadable file, or a parse failure by
    returning None (fail-closed -- never a widening; this auxiliary read has
    no channel to report a syntax error through, so it degrades exactly
    like "signal absent")."""
    if feature_dir is None:
        return None
    path = Path(feature_dir) / "phase-state" / "rework.yaml"
    if not path.is_file():
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    data, parse_err = parse_yaml_text(text)
    if parse_err or not isinstance(data, dict):
        return None
    return data


def resolve_rework_phase_state(phase_state, feature_dir):
    """Resolves the rework-phase state mapping the re-planning path's second
    case reads its re-entry signal from -- one of two equally valid sources:

    1. `--phase-state`, when its own `phase` is `rework` (a caller that
       already has that file open is not forced to re-supply it).
    2. `{feature_dir}/phase-state/rework.yaml` -- the form the canonical
       invocation actually produces (see _load_rework_phase_state_from_dir).

    Returns None when neither source is available or qualifies -- fail
    closed: the caller must then treat the patch as the initial-planning
    path."""
    if isinstance(phase_state, dict) and phase_state.get("phase") == "rework":
        return phase_state
    return _load_rework_phase_state_from_dir(feature_dir)


def workflow_replace_all_spec_change_reentry(workflow, phase_state, feature_dir=None):
    """workflow-patch.md's re-planning path has a second entry form: `create-
    plan` reads `pending` not because this is the first planning pass but
    because the SPEC-change transition re-entered it. That form is
    recognizable only from a rework-phase phase-state mapping (resolved by
    resolve_rework_phase_state -- never from workflow.yaml alone), and ALL
    of the following must hold:

    1. A rework-phase state mapping is available (see
       resolve_rework_phase_state above).
    2. Its `feature` matches `workflow`'s own `feature`.
    3. It carries a `spec_change` record shaped as `references/
       phase-state.md` defines: `reason`, `origin_kind`, `origin_id` and
       `recorded_at_commit` present and non-empty, and `replan_authorized`
       present as a boolean.
    4. `replan_authorized` is `True` -- an authorization already spent
       (`False`) is not a standing permission. `consumed` is never
       consulted for this judgement: `references/phase-state.md`'s
       `spec_change` flag pair keeps the two flags independent, and this
       helper's re-planning-authorization check does not read `consumed`
       (task0022, review round 3, consumed-flag-split).
    5. `workflow.implement.base_commit` is already set (implementation has
       actually started at least once before).

    Fails closed on every one of these: a missing signal, a phase or feature
    mismatch, a malformed record, or a `replan_authorized` that is absent,
    non-boolean or spent is NOT this form -- the caller must fall back to
    treating the patch as the initial-planning path. A narrower invocation
    must never widen what replace_all permits."""
    rework_state = resolve_rework_phase_state(phase_state, feature_dir)
    if rework_state is None:
        return False
    if rework_state.get("feature") != (workflow or {}).get("feature"):
        return False
    spec_change = rework_state.get("spec_change")
    if not isinstance(spec_change, dict) or not spec_change:
        return False
    if not all(spec_change.get(f) for f in SPEC_CHANGE_MANDATORY_FIELDS):
        return False
    # rework-contract-drift/task0004 (FR6): `origin_kind`'s closed
    # vocabulary is enforced here, removing the asymmetry with
    # `classification`'s classifier/verdict/decision vocabularies below --
    # presence alone (the mandatory-fields check above) is not enough.
    if spec_change.get("origin_kind") not in ORIGIN_KIND_VALUES:
        return False
    replan_authorized = spec_change.get("replan_authorized")
    if not isinstance(replan_authorized, bool):
        return False
    if replan_authorized is not True:
        return False
    implement_step = workflow_find_step(workflow, "implement")
    base_commit = implement_step.get("base_commit") if implement_step else None
    return bool(base_commit)


def workflow_requirement_ids(workflow):
    return set((workflow or {}).get("requirements", {}) or {})


def workflow_task_ids(workflow):
    return set((workflow or {}).get("tasks", {}) or {})


def get_preserve_value(workflow, path):
    parts = path.split(".")
    if parts[0] == "workflow" and len(parts) == 3:
        step = workflow_find_step(workflow, parts[1])
        return step.get(parts[2]) if step else None
    if parts[0] == "tasks" and len(parts) == 3:
        task = (workflow or {}).get("tasks", {}).get(parts[1])
        return task.get(parts[2]) if isinstance(task, dict) else None
    if path == "project.license":
        return (workflow or {}).get("project", {}).get("license")
    return None


def next_task_id_after(workflow):
    ids = workflow_task_ids(workflow)
    max_n = 0
    for tid in ids:
        m = TASK_ID_RE.match(tid)
        if m:
            max_n = max(max_n, int(tid[len("task"):]))
    return f"task{max_n + 1:04d}"


# ---------------------------------------------------------------------------
# --kind question-packet
# ---------------------------------------------------------------------------

def validate_question(q, index, *, gate_registry=None, packet_phase=None, packet_worker=None):
    errors = []
    p = f"questions[{index}]"
    qid = q.get("question_id")
    if not isinstance(qid, str) or not QUESTION_ID_RE.match(qid):
        errors.append(err("question_id", f"{p}.question_id must match {QUESTION_ID_RE.pattern}"))
    gate_id = q.get("gate_id")
    if not gate_id:
        errors.append(err("gate_id", f"{p}.gate_id is required"))
    elif gate_registry:
        # bs2 (round 2): gate_id was previously checked for non-emptiness
        # only, so any question could carry ANY listed gate_id regardless
        # of who actually raises it, in what phase, for what category, or
        # with what options -- laundering a sensitive question through a
        # permissive gate. Reject a mismatch on any bound dimension.
        entry = gate_registry.get(gate_id)
        if entry is not None:
            if entry["worker"] is not None and packet_worker is not None and packet_worker != entry["worker"]:
                errors.append(
                    err(
                        "gate_id",
                        f"{p}.gate_id {gate_id!r} is registered to worker {entry['worker']!r}, "
                        f"not {packet_worker!r}",
                    )
                )
            if entry["phase"] is not None and packet_phase is not None and packet_phase != entry["phase"]:
                errors.append(
                    err(
                        "gate_id",
                        f"{p}.gate_id {gate_id!r} is registered to phase {entry['phase']!r}, "
                        f"not {packet_phase!r}",
                    )
                )
            if entry["category"] is not None and q.get("category") != entry["category"]:
                errors.append(
                    err(
                        "gate_id",
                        f"{p}.gate_id {gate_id!r} requires category {entry['category']!r}, "
                        f"got {q.get('category')!r}",
                    )
                )
            if entry["required_option_id"] is not None:
                option_ids = {o.get("option_id") for o in (q.get("options") or []) if isinstance(o, dict)}
                if entry["required_option_id"] not in option_ids:
                    errors.append(
                        err(
                            "gate_id",
                            f"{p}.gate_id {gate_id!r} requires option_id "
                            f"{entry['required_option_id']!r} to be offered among options",
                        )
                    )
        # goal-vs-spec-divergence/task0024 (AC-5): the check above only
        # constrains gate_id -> category, and only when gate_id is itself
        # a registered entry -- a category: spec-change question paired
        # with an unregistered, or worker-attributed-but-uncategorized,
        # gate_id passed through with no error. Close the missing
        # direction: category -> gate_id, derived the same way (never a
        # hardcoded gate_id literal here) from the same registry, via
        # whichever worker-attributed gate_id(s) that category's suffix
        # binds to.
        required_gate_ids = _gate_ids_for_category(gate_registry, q.get("category"))
        if required_gate_ids and gate_id not in required_gate_ids:
            errors.append(
                err(
                    "category",
                    f"{p}.category {q.get('category')!r} requires gate_id to be one of "
                    f"{sorted(required_gate_ids)}, got {gate_id!r}",
                )
            )
    # rework-contract-drift/task0004 (FR4): the packet's own origin-naming
    # obligation (references/question-packet-schema.md's evidence[].
    # origin_id row; references/question-resolution.md's Classification
    # gate, Origin verification) -- a `rework.spec-change` question with no
    # `evidence[]` entry carrying a non-empty `origin_id` can never pass
    # origin verification, so it is rejected here too.
    if gate_id == "rework.spec-change":
        evidence_entries = q.get("evidence") or []
        if not any(isinstance(e, dict) and e.get("origin_id") for e in evidence_entries):
            errors.append(
                err(
                    "evidence",
                    f"{p}.evidence must carry at least one entry with a non-empty "
                    "origin_id when gate_id is 'rework.spec-change'",
                )
            )
    if q.get("category") not in CATEGORY_VALUES:
        errors.append(err("category", f"{p}.category must be one of the fixed vocabulary"))
    if q.get("priority") not in PRIORITY_VALUES:
        errors.append(err("priority", f"{p}.priority must be one of {sorted(PRIORITY_VALUES)}"))
    if not isinstance(q.get("blocking"), bool):
        errors.append(err("blocking", f"{p}.blocking must be a boolean"))
    if not q.get("prompt"):
        errors.append(err("prompt", f"{p}.prompt is required"))
    header = q.get("header")
    if not isinstance(header, str) or len(header) > 12:
        errors.append(err("header", f"{p}.header must be <= 12 characters"))
    answer_mode = q.get("answer_mode")
    if answer_mode not in ANSWER_MODE_VALUES:
        errors.append(err("answer_mode", f"{p}.answer_mode must be one of {sorted(ANSWER_MODE_VALUES)}"))
    options = q.get("options") or []
    if answer_mode == "freeform":
        if options:
            errors.append(err("options", f"{p}.options must be empty for answer_mode freeform"))
    elif answer_mode in ("single_select", "multi_select", "select_or_freeform"):
        if not (2 <= len(options) <= 4):
            errors.append(err("options", f"{p}.options must have 2-4 entries for answer_mode {answer_mode}"))
    for oi, opt in enumerate(options):
        if not opt.get("option_id"):
            errors.append(err("option_id", f"{p}.options[{oi}].option_id is required"))
        if not opt.get("label"):
            errors.append(err("label", f"{p}.options[{oi}].label is required"))
    if not q.get("why_needed"):
        errors.append(err("why_needed", f"{p}.why_needed is required"))
    on_unanswered = q.get("on_unanswered")
    if on_unanswered not in ON_UNANSWERED_VALUES:
        errors.append(err("on_unanswered", f"{p}.on_unanswered must be one of {sorted(ON_UNANSWERED_VALUES)}"))
    category = q.get("category")
    if category in BLOCKING_REQUIRED_CATEGORIES and on_unanswered != "block":
        errors.append(
            err(
                "on_unanswered",
                f"{p}.on_unanswered must be 'block' when category is {category!r} "
                "(NFR4 fail-closed: a worker cannot choose the non-blocking "
                "handling for spec-change / security / license questions)",
            )
        )
    for did in q.get("depends_on") or []:
        if not isinstance(did, str):
            errors.append(err("depends_on", f"{p}.depends_on entries must be strings"))
    for sid in q.get("supersedes") or []:
        if not isinstance(sid, str):
            errors.append(err("supersedes", f"{p}.supersedes entries must be strings"))
    return errors


def validate_question_packet(data, *, gate_registry=None):
    if not isinstance(data, dict):
        return [err("structure", "question packet must be a mapping")]
    errors = []
    if data.get("schema_version") != 1:
        errors.append(err("schema_version", "schema_version must be 1"))
    packet_id = data.get("packet_id")
    if not isinstance(packet_id, str) or not PACKET_ID_RE.match(packet_id):
        errors.append(err("packet_id", f"packet_id must match {PACKET_ID_RE.pattern}"))
    if data.get("phase") not in PHASE_VALUES:
        errors.append(err("phase", f"phase must be one of {sorted(PHASE_VALUES)}"))
    if data.get("worker") not in WORKERS:
        errors.append(err("worker", f"worker must be one of {WORKERS}"))
    iteration = data.get("iteration")
    if not isinstance(iteration, int) or iteration < 1:
        errors.append(err("iteration", "iteration must be an integer >= 1"))
    input_revision = data.get("input_revision") or {}
    if "input_digest" not in input_revision:
        errors.append(err("input_revision", "input_revision.input_digest is required"))
    summary = data.get("summary")
    if summary is not None and len(summary) > 2000:
        errors.append(err("summary", "summary must be <= 2000 characters"))
    for i, fact in enumerate(data.get("confirmed_facts") or []):
        if not fact.get("fact_id") or not fact.get("statement"):
            errors.append(err("confirmed_facts", f"confirmed_facts[{i}] requires fact_id and statement"))
    for i, a in enumerate(data.get("assumptions") or []):
        if a.get("impact") not in IMPACT_VALUES:
            errors.append(err("assumptions", f"assumptions[{i}].impact must be one of {sorted(IMPACT_VALUES)}"))
        if not isinstance(a.get("reversible"), bool):
            errors.append(err("assumptions", f"assumptions[{i}].reversible must be a boolean"))
    questions = data.get("questions") or []
    if not (1 <= len(questions) <= 32):
        errors.append(err("questions", "questions must have 1-32 entries"))
    packet_phase = data.get("phase")
    packet_worker = data.get("worker")
    seen_ids = set()
    for i, q in enumerate(questions):
        errors.extend(
            validate_question(
                q, i, gate_registry=gate_registry, packet_phase=packet_phase, packet_worker=packet_worker
            )
        )
        qid = q.get("question_id")
        if qid in seen_ids:
            errors.append(err("question_id", f"duplicate question_id {qid!r} within packet"))
        seen_ids.add(qid)
    for i, q in enumerate(questions):
        qid = q.get("question_id")
        # depends_on orders questions bundled in the SAME packet/dispatch, so
        # its target must be resolvable within this packet.
        for did in q.get("depends_on") or []:
            if did == qid:
                errors.append(err("depends_on", f"questions[{i}].depends_on cannot reference its own question_id"))
            elif did not in seen_ids:
                errors.append(err("depends_on", f"questions[{i}].depends_on references unknown question_id {did!r}"))
        # supersedes typically points at a question from an earlier packet
        # (already resolved/obsoleted), so it is not required to exist in
        # THIS packet -- only self-reference is structurally invalid.
        for sid in q.get("supersedes") or []:
            if sid == qid:
                errors.append(err("supersedes", f"questions[{i}].supersedes cannot reference its own question_id"))
    return errors


# ---------------------------------------------------------------------------
# --kind answers (5.2)
# ---------------------------------------------------------------------------

def validate_answer(a, question=None):
    errors = []
    if not a.get("question_id"):
        errors.append(err("question_id", "question_id is required"))
    if not a.get("packet_id"):
        errors.append(err("packet_id", "packet_id is required"))
    if a.get("source") not in ANSWER_SOURCE_VALUES:
        errors.append(err("source", f"source must be one of {sorted(ANSWER_SOURCE_VALUES)}"))
    answer_mode = a.get("answer_mode")
    if answer_mode not in ANSWER_MODE_VALUES:
        errors.append(err("answer_mode", f"answer_mode must be one of {sorted(ANSWER_MODE_VALUES)}"))
    selected = a.get("selected_option_ids") or []
    freeform = a.get("freeform")

    # 5.2 rules 1-4
    if answer_mode == "single_select":
        if len(selected) != 1 or freeform is not None:
            errors.append(err("answer_mode", "single_select requires exactly 1 selected_option_ids and null freeform"))
    elif answer_mode == "multi_select":
        if len(selected) < 1:
            errors.append(err("answer_mode", "multi_select requires at least 1 selected_option_ids"))
    elif answer_mode == "freeform":
        if selected or not freeform:
            errors.append(err("answer_mode", "freeform requires empty selected_option_ids and non-empty freeform"))
    elif answer_mode == "select_or_freeform":
        if not selected and not freeform:
            errors.append(err("answer_mode", "select_or_freeform requires selected_option_ids or freeform"))

    # rule 5 + cross-reference against the corresponding question
    if question is not None:
        option_ids = {o.get("option_id") for o in (question.get("options") or [])}
        for oid in selected:
            if oid not in option_ids:
                errors.append(err("selected_option_ids", f"{oid!r} is not one of the question's options[].option_id"))
        if question.get("answer_mode") is not None and question.get("answer_mode") != answer_mode:
            errors.append(err("answer_mode", "answer_mode does not match the corresponding question's answer_mode"))
    return errors


def find_question(packet, question_id):
    if not packet:
        return None
    for q in packet.get("questions") or []:
        if q.get("question_id") == question_id:
            return q
    return None


def validate_answers_list(data, packet=None):
    if isinstance(data, dict):
        # Also accept a question_id-keyed map (phase-state.answers shape).
        items = list(data.values())
    elif isinstance(data, list):
        items = data
    else:
        return [err("structure", "answers input must be a list or a question_id-keyed mapping")]
    errors = []
    for i, a in enumerate(items):
        if not isinstance(a, dict):
            errors.append(err("structure", f"answers[{i}] must be a mapping"))
            continue
        question = find_question(packet, a.get("question_id")) if packet else None
        errors.extend(prefix_errors(validate_answer(a, question), f"answers[{i}]"))
    return errors


# ---------------------------------------------------------------------------
# Final-path correction (subagent-report-write-block, FR5 / FR6;
# final-path-correction-medium-fixes, FR1 to FR3, FR5 to FR7 and FR9)
#
# `tasks_patch.path_corrections` is the one exception to the verbatim copy of
# a carried task's record (references/workflow-patch.md, "Final-path
# correction", owns the contract; IMPLEMENTATION.md D1 to D3 and D8 of
# subagent-report-write-block and D2 to D7 of
# final-path-correction-medium-fixes own the bindings). A correction changes
# paths and nothing else, so the validation passes no other change:
#
# - The structural shape is checked with and without --dry-run-apply.
# - Under --dry-run-apply a patch with corrections is in one path state
#   (`correction_path_state`): the correction entry, the Re-planning path, or
#   any other state, which is rejected as `path-correction-not-permitted` and
#   judged by condition 5 in its strictest form.
# - Conditions 1 to 5 run in every state. Condition 4 includes the form check
#   of `new_path` (FR2). Condition 5 compares positionally on the correction
#   entry and covers every plan of workflow.yaml (FR3, FR6, FR9); on the
#   Re-planning path only its left-behind check runs (FR5). A bare old file
#   name left behind is rejected (FR7); the scanner is the only definition of
#   an occurrence.
# - On the correction entry only, `tasks_patch.entries` and `requirements_patch`
#   are limited (FR1), after condition 5 and outside the five numbered
#   conditions.
# - The in-memory application and the plan Files-section agreement follow.
# ---------------------------------------------------------------------------

JOURNAL_KNOWN_EVENTS = ("launched", "merged", "failed")

PATH_CORRECTION_KEYS = frozenset({"task_id", "old_path", "new_path"})

# The documents condition 5 compares besides the plans of workflow.yaml.
PATH_CORRECTION_DOCUMENTS = ("IMPLEMENTATION.md", "VERIFICATION.md")

# The path states of a patch with corrections (IMPLEMENTATION.md D2).
PATH_STATE_CORRECTION_ENTRY = "correction-entry"
PATH_STATE_REPLANNING = "replanning"
PATH_STATE_OTHER = "other"

PATH_CORRECTION_ENTRIES_CODE = "path-correction-entries"
PATH_CORRECTION_REQUIREMENTS_CODE = "path-correction-requirements"


def read_journal_events(journal_path):
    """Replays the journal and returns (last_events, last_failed_lines):
    {task_id: (event, line)} for each task's last event, and {task_id: line}
    for each task's last `failed` event. A missing file reads as no events; an
    unreadable one raises ExecutionError. Lines are delimited by LF only (a CR
    never starts a line) and a final non-empty segment without a terminating
    LF is one more line, the counting rule of the `routeback_failed_journal_line`
    section of references/workflow-schema.md; blank, malformed, unknown-event
    and invalid-task-id lines are skipped but counted."""
    try:
        with open(journal_path, "rb") as handle:
            raw = handle.read()
    except FileNotFoundError:
        return {}, {}
    except OSError as exc:
        raise ExecutionError(f"cannot read --journal file: {exc.__class__.__name__}")
    segments = raw.split(b"\n")
    if segments and segments[-1] == b"":
        segments.pop()  # the last LF terminates a line, it adds none
    last_events = {}
    last_failed_lines = {}
    for line_number, segment in enumerate(segments, start=1):
        line = segment.decode("utf-8", errors="replace").strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except (ValueError, RecursionError):
            continue
        if not isinstance(record, dict):
            continue
        task_id = record.get("task")
        event = record.get("event")
        if not isinstance(task_id, str) or not TASK_ID_RE.match(task_id):
            continue
        if event not in JOURNAL_KNOWN_EVENTS:
            continue
        last_events[task_id] = (event, line_number)
        if event == "failed":
            last_failed_lines[task_id] = line_number
    return last_events, last_failed_lines


def journal_last_events(journal_path):
    """{task_id: (event, line)} for the last event of each task; see
    `read_journal_events` for the reading rules."""
    return read_journal_events(journal_path)[0]


def _tasks_of(workflow):
    tasks = (workflow or {}).get("tasks") if isinstance(workflow, dict) else None
    return tasks if isinstance(tasks, dict) else {}


def _path_corrections_field(patch):
    tasks_patch = patch.get("tasks_patch") if isinstance(patch, dict) else None
    return tasks_patch.get("path_corrections") if isinstance(tasks_patch, dict) else None


def _on_correction_entry(workflow, patch):
    """True when `patch` carries a non-empty `tasks_patch.path_corrections`
    and `workflow` is on the correction entry (IMPLEMENTATION.md D2):
    create-plan `completed` and implement `failed`. False without a workflow
    mapping."""
    if not isinstance(workflow, dict) or not patch_has_path_corrections(patch):
        return False
    return _workflow_on_correction_entry(workflow)


def correction_path_state(workflow, patch, phase_state=None, feature_dir=None):
    """The path state of a patch (IMPLEMENTATION.md D2), decided from
    workflow.yaml and the phase state whatever `tasks_patch.mode` holds: None
    for a patch without corrections; otherwise exactly one of
    `PATH_STATE_CORRECTION_ENTRY` (create-plan `completed` and implement
    `failed`), `PATH_STATE_REPLANNING` (create-plan `needs_update`, or
    `pending` on a SPEC-change re-entry) and `PATH_STATE_OTHER`. The last is
    rejected as `path-correction-not-permitted`; condition 5 judges it as the
    correction entry, the strictest form, and the FR1 limits do not run."""
    if not patch_has_path_corrections(patch):
        return None
    if _on_correction_entry(workflow, patch):
        return PATH_STATE_CORRECTION_ENTRY
    create_plan = workflow_find_step(workflow, "create-plan")
    status = create_plan.get("status") if create_plan else None
    if status == "needs_update" or (
        status == "pending" and workflow_replace_all_spec_change_reentry(workflow, phase_state, feature_dir)
    ):
        return PATH_STATE_REPLANNING
    return PATH_STATE_OTHER


def patch_has_path_corrections(patch):
    """True when the patch carries a non-empty list in
    `tasks_patch.path_corrections`, whatever its elements hold."""
    field = _path_corrections_field(patch)
    return isinstance(field, list) and bool(field)


def path_correction_shape_errors(patch):
    """The structural check of `tasks_patch.path_corrections` (error code
    `path-correction-shape`), the same with and without --dry-run-apply: when
    present it is a non-empty list of mappings with exactly `task_id`,
    `old_path` and `new_path` (non-empty strings), on `replace_planning`
    only; every `task_id` is in the patch's own `carried_task_ids`; each
    (task_id, old_path) appears once; `new_path` differs from `old_path`; one
    old path never moves to two new paths. Absent and null are the same."""
    field = _path_corrections_field(patch)
    if field is None:
        return []
    label = "tasks_patch.path_corrections"
    errors = []

    def bad(message):
        errors.append(err("path-correction-shape", f"{label}{message}"))

    if patch.get("operation") != "replace_planning":
        bad(" is permitted on replace_planning only")
        return errors
    if not isinstance(field, list) or not field:
        bad(" must be a non-empty list of mappings")
        return errors
    carried_raw = patch["tasks_patch"].get("carried_task_ids")
    carried = {c for c in carried_raw if isinstance(c, str)} if isinstance(carried_raw, list) else set()
    seen = set()
    new_for_old = {}
    for i, item in enumerate(field):
        if not isinstance(item, dict):
            bad(f"[{i}] must be a mapping")
            continue
        if set(item) != PATH_CORRECTION_KEYS:
            bad(f"[{i}] must hold exactly task_id, old_path and new_path")
            continue
        task_id, old_path, new_path = item["task_id"], item["old_path"], item["new_path"]
        if not all(isinstance(v, str) and v for v in (task_id, old_path, new_path)):
            bad(f"[{i}] task_id, old_path and new_path must be non-empty strings")
            continue
        if task_id not in carried:
            bad(f"[{i}].task_id {task_id!r} is not in tasks_patch.carried_task_ids")
        if old_path == new_path:
            bad(f"[{i}].new_path must differ from old_path")
        if (task_id, old_path) in seen:
            bad(f"[{i}] repeats the correction of {old_path!r} on {task_id}")
        seen.add((task_id, old_path))
        if new_for_old.setdefault(old_path, new_path) != new_path:
            bad(f"[{i}] moves {old_path!r} to a second new path")
    return errors


def _well_formed_path_corrections(patch):
    """The list of corrections (mappings with the three strings) when the
    field passes `path_correction_shape_errors`, else []."""
    if not patch_has_path_corrections(patch) or path_correction_shape_errors(patch):
        return []
    return [dict(item) for item in _path_corrections_field(patch)]


def _apply_path_corrections(tasks, corrections):
    """In-memory application on a {task_id: record} mapping the caller owns
    (a copy): a corrected record has `old_path` replaced by `new_path` at the
    same list position and `notes` set to null; every other field stays
    verbatim. A correction naming a task that is not in `tasks` is skipped."""
    for correction in corrections:
        record = tasks.get(correction.get("task_id"))
        if not isinstance(record, dict):
            continue
        files = record.get("files")
        if isinstance(files, list):
            record["files"] = [
                correction["new_path"] if f == correction["old_path"] else f for f in files
            ]
        record["notes"] = None


def _require_path_correction_inputs(patch, *, workflow, journal, feature_dir, target_repo, base_commit):
    """Under --dry-run-apply a non-empty `path_corrections` needs --workflow,
    --journal, --feature-dir, --target-repo and --base-commit, and a base
    that resolves: a missing one or an unresolvable base is an execution
    error (exit 2), never a pass."""
    if not patch_has_path_corrections(patch):
        return
    missing = [
        flag
        for flag, value in (
            ("--workflow", workflow),
            ("--journal", journal),
            ("--feature-dir", feature_dir),
            ("--target-repo", target_repo),
            ("--base-commit", base_commit),
        )
        if value is None
    ]
    if missing:
        raise ExecutionError(
            "--dry-run-apply of a patch with path_corrections requires " + ", ".join(missing)
        )
    require_report_name_base(target_repo, base_commit)


def path_correction_precondition_errors(workflow, corrections, last_events, target_repo, base_commit):
    """FR5 conditions 1 to 3 (one error code each, in that order). A
    correction is a mapping with `task_id` and `old_path`; the entry script
    supplies them from its violations. `last_events` is `journal_last_events`.

    1. `path-correction-in-flight`: once, when any task is `in_progress` or
       any task's journal last event is `launched`.
    2. `path-correction-merged`: the target's status or journal last event is
       `merged`.
    3. `path-correction-old-path`: `old_path` is not in the target's `files`,
       does not match FR2, or is not `absent` at the base commit.

    The base inputs are read only when condition 3 reaches a lookup."""
    errors = []
    tasks = _tasks_of(workflow)
    last_events = last_events or {}

    in_flight = {
        task_id
        for task_id, record in tasks.items()
        if isinstance(record, dict) and record.get("status") == "in_progress"
    }
    in_flight |= {task_id for task_id, (event, _) in last_events.items() if event == "launched"}
    if in_flight:
        errors.append(
            err(
                "path-correction-in-flight",
                f"a final-path correction requires no task in flight; in flight: {sorted(in_flight)}",
                task_ids=sorted(in_flight),
            )
        )

    for correction in corrections:
        task_id, old_path = correction.get("task_id"), correction.get("old_path")
        record = tasks.get(task_id)
        status = record.get("status") if isinstance(record, dict) else None
        last_event = last_events.get(task_id, (None, None))[0]
        if status == "merged" or last_event == "merged":
            errors.append(
                err(
                    "path-correction-merged",
                    f"{task_id}: the target task is merged (status {status!r}, last journal event {last_event!r}); "
                    "its record cannot be corrected",
                    task_id=task_id,
                    path=old_path,
                )
            )

    base_checked = False
    for correction in corrections:
        task_id, old_path = correction.get("task_id"), correction.get("old_path")
        record = tasks.get(task_id)
        files = record.get("files") if isinstance(record, dict) else None
        reason = None
        if not isinstance(files, list) or old_path not in files:
            reason = "is not in the target task's files"
        elif not is_report_artifact_name(old_path):
            reason = "does not have a name that matches the report artifact rule"
        else:
            if not base_checked:
                require_report_name_base(target_repo, base_commit)
                base_checked = True
            entry = base_tree_entry(target_repo, base_commit, old_path)
            if entry != "absent":
                reason = f"is not absent at the base commit ({entry})"
        if reason is not None:
            errors.append(
                err(
                    "path-correction-old-path",
                    f"{task_id}: old_path {old_path!r} {reason}",
                    task_id=task_id,
                    path=old_path,
                )
            )
    return errors


# The form of a new_path (FR2): Unicode word characters, `.`, `/` and `-`.
_CORRECTION_PATH_FORM_RE = re.compile(r"[\w./-]+")


def path_correction_form_ok(path):
    """FR2, the form check of a path that a correction writes into
    workflow.yaml or a plan: True only when all three clauses hold. The whole
    string matches `[\\w./-]+` (so a trailing line break fails); it equals its
    normalized form `'/'.join(path_segments(path))` (so `.`, `./`, `a//b.md`,
    `a/./b.md` and a trailing `/` fail); and its first segment does not start
    with `-`. Pure: a non-string is False."""
    if not isinstance(path, str) or _CORRECTION_PATH_FORM_RE.fullmatch(path) is None:
        return False
    segments = path_segments(path)
    return bool(segments) and "/".join(segments) == path and not segments[0].startswith("-")


def _path_correction_new_path_errors(corrections, target_repo, base_commit):
    """FR5 condition 4 (`path-correction-new-path`): `new_path` does not match
    FR2, passes `is_safe_relative_path`, passes the form check
    `path_correction_form_ok` (FR2 of final-path-correction-medium-fixes, after
    the safe-path check and before the base lookup), and is `absent` at the
    base commit."""
    errors = []
    base_checked = False
    for correction in corrections:
        task_id, new_path = correction["task_id"], correction["new_path"]
        if is_report_artifact_name(new_path):
            reason = "has a name that still matches the report artifact rule"
        elif not is_safe_relative_path(new_path):
            reason = "is not a safe project-relative path"
        elif not path_correction_form_ok(new_path):
            reason = (
                "does not have the path form (Unicode word characters, '.', '/' and '-' only, "
                "equal to its normalized form, first segment not starting with '-')"
            )
        else:
            if not base_checked:
                require_report_name_base(target_repo, base_commit)
                base_checked = True
            entry = base_tree_entry(target_repo, base_commit, new_path)
            reason = None if entry == "absent" else f"is not absent at the base commit ({entry})"
        if reason is not None:
            errors.append(
                err(
                    "path-correction-new-path",
                    f"{task_id}: new_path {new_path!r} {reason}",
                    task_id=task_id,
                    path=new_path,
                )
            )
    return errors


# ---------------------------------------------------------------------------
# Reference occurrences (IMPLEMENTATION.md D3, FR7) and the positional
# comparison (D4, FR6)
# ---------------------------------------------------------------------------

# FR7: a bare old file name is not preceded by an ASCII letter, digit, `_`,
# `-`, `.`, `/` or `\`, and not followed by an ASCII letter, digit, `_`, `-`,
# `/` or `\`, or by `.` plus one of letter, digit, `_`, `-`. An old path of
# several segments keeps the same boundary, except that a preceding `./`
# lifts the one before the token.
_NOT_PRECEDED_BY_NAME_CHAR = r"(?<![A-Za-z0-9_\-./\\])"
_PRECEDED_BY_DOT_SLASH = r"(?<=\./)"
_NOT_FOLLOWED_BY_NAME_CHAR = r"(?![A-Za-z0-9_\-/\\]|\.[A-Za-z0-9_\-])"


def _correction_file_name(path):
    segments = path_segments(path)
    return segments[-1] if segments else ""


def _scan_references(text, corrections):
    """The reference occurrences of IMPLEMENTATION.md D3 in `text`: a list of
    `(start, end, token, kind)` in text order, never overlapping. `kind` is
    "path" for an old path of several segments and "bare" for a bare old file
    name; a one-segment old path, judged after `path_segments`, is matched
    only as a bare name. The scan runs left to right and at one position the
    longer token wins. This is the only definition of an occurrence: the
    comparison, the left-behind check and the entries limit all use it, and
    none of them searches for substrings. Pure."""
    path_tokens, bare_names = set(), set()
    for correction in corrections:
        segments = path_segments(correction["old_path"])
        if not segments:
            continue
        bare_names.add(segments[-1])
        if len(segments) > 1:
            path_tokens.add(correction["old_path"])
    alternatives = []
    for token in sorted(path_tokens | bare_names, key=lambda t: (-len(t), t)):
        before = (
            f"(?:{_NOT_PRECEDED_BY_NAME_CHAR}|{_PRECEDED_BY_DOT_SLASH})"
            if token in path_tokens
            else _NOT_PRECEDED_BY_NAME_CHAR
        )
        alternatives.append(f"{before}{re.escape(token)}{_NOT_FOLLOWED_BY_NAME_CHAR}")
    if not alternatives:
        return []
    pattern = re.compile("|".join(alternatives))
    return [
        (m.start(), m.end(), m.group(0), "path" if m.group(0) in path_tokens else "bare")
        for m in pattern.finditer(text)
    ]


def _replacement_texts(token, kind, corrections, preferred):
    """The permitted replacements of one occurrence (IMPLEMENTATION.md D4),
    without the old text, which the comparison always permits. An old path of
    several segments permits only its own `new_path`. A bare old file name
    permits the new file names of the corrections of `preferred` (the
    corrections of the target tasks using the document) that hold it, and when
    there are none those of all corrections of the patch that hold it; for a
    one-segment old path the `new_path` of each selected correction whose old
    path is that one segment is added, because a plan's Files section holds
    the full `new_path`."""
    if kind == "path":
        return {c["new_path"] for c in corrections if c["old_path"] == token}
    holders = [c for c in preferred if _correction_file_name(c["old_path"]) == token] or [
        c for c in corrections if _correction_file_name(c["old_path"]) == token
    ]
    texts = set()
    for c in holders:
        new_name = _correction_file_name(c["new_path"])
        if new_name:
            texts.add(new_name)
        if len(path_segments(c["old_path"])) == 1:
            texts.add(c["new_path"])
    return texts


def _positional_match(base_text, current_text, occurrences, permitted):
    """True when `current_text` can be read as the literal runs of `base_text`
    in order, each occurrence holding one member of its permitted set (the old
    text itself always among them), consuming the whole current text.
    `occurrences` are the `_scan_references` tuples of the base text and
    `permitted[i]` is the set of replacement texts of occurrence i.
    Replacements are literal and the current text is never rescanned. Permitted
    texts may be prefixes of each other, so the search keeps, per occurrence,
    the set of current positions it can have reached: a pair (occurrence index,
    position) is visited once, and the cost is bounded by the number of such
    pairs, never exponential."""
    literals = []
    position = 0
    for start, end, _token, _kind in occurrences:
        literals.append(base_text[position:start])
        position = end
    literals.append(base_text[position:])
    if not current_text.startswith(literals[0]):
        return False
    reachable = {len(literals[0])}
    for index, (start, end, _token, _kind) in enumerate(occurrences):
        candidates = set(permitted[index])
        candidates.add(base_text[start:end])
        following = literals[index + 1]
        advanced = set()
        for here in reachable:
            for text in candidates:
                if current_text.startswith(text, here):
                    after = here + len(text)
                    if current_text.startswith(following, after):
                        advanced.add(after + len(following))
        if not advanced:
            return False
        reachable = advanced
    return len(current_text) in reachable


def _left_behind_references(text, corrections):
    """(old paths, bare old file names) that occur in `text`, each sorted and
    without repeats, by the occurrences of `_scan_references`."""
    paths, names = set(), set()
    for _start, _end, token, kind in _scan_references(text, corrections):
        (paths if kind == "path" else names).add(token)
    return sorted(paths), sorted(names)


def _regular_blob_id(target_repo, base_commit, path):
    """The object ID of `path` at the base commit, for a path that
    base_tree_entry classified as "regular". The walk is the one base_tree_entry
    makes: one tree at a time with `git ls-tree` on object IDs git printed,
    each segment compared as literal text, so the path is never given to git."""
    tree_id = base_commit
    segments = path_segments(path)
    for depth, segment in enumerate(segments):
        entry = _list_git_tree(target_repo, tree_id).get(segment.encode("utf-8", "surrogateescape"))
        if entry is None:
            raise ExecutionError("the base commit's tree changed while a document was read")
        _mode, entry_type, entry_id = entry
        if depth == len(segments) - 1:
            if entry_type != b"blob":
                raise ExecutionError("the base commit's tree changed while a document was read")
            return entry_id
        tree_id = entry_id
    raise ExecutionError("the base commit's tree changed while a document was read")


def _read_base_document(target_repo, base_commit, path):
    """(text, None) for a regular file at the base commit, else
    (None, reason) with reason one of the `_SCAN_*` constants. The kind comes
    from base_tree_entry; a git read that fails is an ExecutionError."""
    kind = base_tree_entry(target_repo, base_commit, path)
    if kind == "absent":
        return None, _SCAN_ABSENT
    if kind != "regular":
        return None, _SCAN_NOT_REGULAR
    object_id = _regular_blob_id(target_repo, base_commit, path)
    size_proc = _run_git(target_repo, "cat-file", "-s", object_id)
    try:
        size = int(size_proc.stdout.strip()) if size_proc.returncode == 0 else None
    except ValueError:
        size = None
    if size is None:
        raise ExecutionError(f"git could not read the size of a document in --target-repo {target_repo}")
    if size > MAX_PLAN_READ_BYTES:
        return None, _SCAN_TOO_LARGE
    blob_proc = _run_git(target_repo, "cat-file", "blob", object_id)
    if blob_proc.returncode != 0:
        raise ExecutionError(f"git could not read a document in --target-repo {target_repo}")
    try:
        return blob_proc.stdout.decode("utf-8"), None
    except UnicodeDecodeError:
        return None, _SCAN_NOT_UTF8


def _feature_dir_in_repository(feature_dir, target_repo):
    """The segments of the feature directory's path relative to the
    repository, or an ExecutionError when it lies outside it."""
    try:
        relative = Path(feature_dir).resolve().relative_to(Path(target_repo).resolve())
    except (ValueError, OSError):
        raise ExecutionError("--feature-dir is not inside --target-repo")
    return list(relative.parts)


def _read_current_document(feature_dir, document):
    """Reads one document of the feature directory for condition 5 and the
    plan check of an entry: (text, None, None) for a readable regular file,
    (None, True, None) for a file that does not exist, and
    (None, False, message) for anything that cannot be read or compared (an
    unsafe path, a symlink segment, a file that is not regular, over the
    read limit or not UTF-8)."""
    current_path, path_error = _resolve_contained_relative_path(feature_dir, document)
    if path_error is not None:
        return None, False, f"cannot be read: {path_error}"
    text, reason = _read_document_for_scenario_scan(current_path)
    if reason is None:
        return text, False, None
    if reason == _SCAN_ABSENT:
        return None, True, None
    return None, False, f"cannot be compared with the base commit: {_scenario_scan_reason_text(reason)}"


def _task_is_merged(tasks, last_events, task_id):
    record = tasks.get(task_id)
    status = record.get("status") if isinstance(record, dict) else None
    return status == "merged" or (last_events.get(task_id) or (None,))[0] == "merged"


def _path_correction_content_errors(
    workflow, corrections, feature_dir, target_repo, base_commit, path_state, last_events
):
    """FR5 condition 5 (`path-correction-content`) with the refinements of
    final-path-correction-medium-fixes (FR3, FR5 to FR7, FR9), IMPLEMENTATION.md
    D3 to D5. `path_state` is `correction_path_state`'s result and
    `last_events` the journal's `journal_last_events`.

    On the correction entry (and in any other state, judged as the strictest
    form) the documents are IMPLEMENTATION.md, VERIFICATION.md and the plan of
    every task of workflow.yaml, keyed by their normalized path so that a
    document used by several tasks is checked once. A document takes the first
    class that fits:

    - merged plan (a user task's status or last journal event is `merged`):
      byte-equal to the base commit, no left-behind check; this holds for a
      plan shared with a target and takes precedence over its replacement;
    - target plan (a user is a target of the patch): positional comparison
      (FR6) and the left-behind check (FR7);
    - shared document (IMPLEMENTATION.md, VERIFICATION.md): as a target plan;
    - non-target plan: positional comparison, an old reference may remain.

    For every class: no entry at the base commit and present now is rejected
    (FR9); no entry at the base commit and absent now is not an error; an
    entry at the base commit and absent now is rejected; a document that is
    not regular at the base commit or cannot be read now is rejected. A new
    task's plan under `tasks_patch.entries` is in none of the classes unless
    its normalized path equals one of those documents.

    On the Re-planning path (FR5) only IMPLEMENTATION.md, VERIFICATION.md and
    the target plans are read, the base commit is not compared, only the
    left-behind check runs, and a document that does not exist now is not an
    error.

    The left-behind check rejects an old path (message "old path") and a bare
    old file name (message "bare old file name") in the current text, by the
    occurrences of `_scan_references`; a comparison failure is a separate
    error on the same document."""
    errors = []
    feature_dir = Path(feature_dir)
    feature_segments = _feature_dir_in_repository(feature_dir, target_repo)
    replanning = path_state == PATH_STATE_REPLANNING
    tasks = _tasks_of(workflow)
    last_events = last_events or {}
    target_ids = {correction["task_id"] for correction in corrections}

    documents = {}  # normalized path -> {"name": spelling, "users": [task ids]}

    def add_document(spelling, task_id=None):
        entry = documents.setdefault("/".join(path_segments(spelling)), {"name": spelling, "users": []})
        if task_id is not None:
            entry["users"].append(task_id)

    for shared_document in PATH_CORRECTION_DOCUMENTS:
        add_document(shared_document)
    for task_id, record in tasks.items():
        if replanning and task_id not in target_ids:
            continue
        plan = record.get("plan") if isinstance(record, dict) else None
        if isinstance(plan, str) and plan:
            add_document(plan, task_id)

    def content_error(document, message):
        errors.append(
            err("path-correction-content", f"{document}: {message}", document=document)
        )

    def left_behind_errors(document, text):
        paths, names = _left_behind_references(text, corrections)
        if paths:
            content_error(document, f"still contains the old path {paths}")
        if names:
            content_error(document, f"still contains the bare old file name {names}")

    for key, info in documents.items():
        document, users = info["name"], info["users"]
        target_users = [task_id for task_id in users if task_id in target_ids]
        shared = key in PATH_CORRECTION_DOCUMENTS
        if not is_safe_relative_path(document):
            content_error(document, "is not a safe project-relative path")
            continue

        if replanning:
            current_text, absent, problem = _read_current_document(feature_dir, document)
            if problem is not None:
                content_error(document, problem)
            elif not absent:
                left_behind_errors(document, current_text)
            continue

        if any(_task_is_merged(tasks, last_events, task_id) for task_id in users):
            document_class = "merged"
        elif target_users:
            document_class = "target"
        elif shared:
            document_class = "shared"
        else:
            document_class = "non-target"

        base_path = "/".join(feature_segments + path_segments(document))
        base_text, base_reason = _read_base_document(target_repo, base_commit, base_path)
        if base_reason is not None and base_reason != _SCAN_ABSENT:
            content_error(document, f"cannot be compared with the base commit: {_scenario_scan_reason_text(base_reason)}")
            continue
        current_text, absent, problem = _read_current_document(feature_dir, document)
        if base_reason == _SCAN_ABSENT:
            if problem is not None:
                content_error(document, problem)
            elif not absent:
                content_error(
                    document,
                    "has no entry at the base commit but exists now; a plan document is not created "
                    "on the correction entry",
                )
            continue
        if absent:
            content_error(document, "exists at the base commit but is missing now")
            continue
        if problem is not None:
            content_error(document, problem)
            continue

        if document_class == "merged":
            if current_text != base_text:
                content_error(
                    document,
                    "is the plan of a merged task and differs from the base commit; it must stay byte-equal",
                )
            continue
        occurrences = _scan_references(base_text, corrections)
        preferred = [c for c in corrections if c["task_id"] in target_users]
        permitted = [_replacement_texts(token, kind, corrections, preferred) for _s, _e, token, kind in occurrences]
        if not _positional_match(base_text, current_text, occurrences, permitted):
            content_error(document, "differs from the base commit by more than the path replacement")
        if document_class in ("target", "shared"):
            left_behind_errors(document, current_text)
    return errors


def _entry_file_reason_text(reason):
    if reason == _SCAN_ABSENT:
        return "it is absent at the base commit"
    return _scenario_scan_reason_text(reason)


def canonical_correction_plan(task_id, files, corrections):
    """The canonical plan text of a new task that corrects references
    (IMPLEMENTATION.md D6, FR1 (d)): UTF-8 with LF line ends and a final LF.
    A title, the Files section with one bullet per file in `files` order, and
    one acceptance criterion per element of `corrections` (the corrections
    with an occurrence in those files at the base commit, in `path_corrections`
    order) stating that the old reference is replaced by the new one. This is
    the one function that renders it. Pre: every rendered string passed
    `path_correction_form_ok`. Post: the exact text of D6."""
    lines = [
        f"# Task Plan: {task_id} - correct path references",
        "",
        "## Scope",
        "",
        "### Files to Modify",
    ]
    lines.extend(f"- `{file}` - correct the old references" for file in files)
    lines.extend(["", "## Acceptance Criteria (MANDATORY)", ""])
    for number, correction in enumerate(corrections, start=1):
        old_name = _correction_file_name(correction["old_path"])
        new_name = _correction_file_name(correction["new_path"])
        lines.append(
            f"- [ ] AC-{number}: `{correction['old_path']}` is replaced by `{correction['new_path']}`, "
            f"and the bare `{old_name}` by `{new_name}`."
        )
    return "\n".join(lines) + "\n"


def _correction_requirements_errors(workflow, patch):
    """FR1 (a): `requirements_patch` on the correction entry is rejected with
    `path-correction-requirements` unless it is null or has no entries, or
    every item names a requirement already in workflow.yaml and its `set`
    holds only `tasks_append` whose values are all ids under
    `tasks_patch.entries`. A malformed item is a rejection, not a pass."""
    requirements_patch = patch.get("requirements_patch")
    if requirements_patch is None:
        return []

    def reject(message):
        return err(PATH_CORRECTION_REQUIREMENTS_CODE, f"requirements_patch: {message}")

    if not isinstance(requirements_patch, dict):
        return [reject("must be a mapping")]
    items = requirements_patch.get("entries")
    if not items:
        return []
    if not isinstance(items, dict):
        return [reject("entries must be a mapping")]
    entries = (patch.get("tasks_patch") or {}).get("entries")
    entry_ids = set(entries) if isinstance(entries, dict) else set()
    known = workflow_requirement_ids(workflow)
    errors = []
    for fr_id, item in items.items():
        if fr_id not in known:
            errors.append(reject(f"{fr_id!r} is not a requirement already in workflow.yaml"))
            continue
        set_block = item.get("set") if isinstance(item, dict) else None
        if not isinstance(set_block, dict) or set(set_block) != {"tasks_append"}:
            errors.append(reject(f"entries[{fr_id}] may hold only a set with tasks_append"))
            continue
        values = set_block["tasks_append"]
        if not isinstance(values, list) or any(not isinstance(v, str) or v not in entry_ids for v in values):
            errors.append(reject(f"entries[{fr_id}].set.tasks_append may name only ids under tasks_patch.entries"))
    return errors


def _correction_entries_errors(corrections, patch, feature_dir, target_repo, base_commit):
    """FR1 (b) to (d): each item of `tasks_patch.entries` on the correction
    entry is rejected with `path-correction-entries`, one error per rejected
    reason naming the task and the file, unless

    - its `files` is non-empty and every file passes the FR2 form check
      (`path_correction_form_ok`, applied before anything is read or
      rendered), is a regular text file at the base commit within the read
      limit (read only through `_read_base_document`), and holds an
      occurrence of an old path or a bare old file name of the patch's
      corrections (`_scan_references`);
    - every old_path and new_path rendered into its plan passes the form
      check; and
    - its plan, read as a current document of condition 5 is, is byte-equal to
      `canonical_correction_plan` of the task id, its files and the
      corrections that have an occurrence in those files. This holds for a
      TASK.md plan too.

    The plan check runs only once every file passed."""
    entries = (patch.get("tasks_patch") or {}).get("entries") or {}
    if not entries:
        return []
    errors = []

    def reject(task_id, message, path=None):
        extra = {"task_id": task_id}
        if path is not None:
            extra["path"] = path
        errors.append(err(PATH_CORRECTION_ENTRIES_CODE, f"tasks_patch.entries[{task_id}]: {message}", **extra))

    if not isinstance(entries, dict):
        errors.append(err(PATH_CORRECTION_ENTRIES_CODE, "tasks_patch.entries must be a mapping"))
        return errors
    for task_id, entry in entries.items():
        if not isinstance(entry, dict):
            reject(task_id, "must be a mapping")
            continue
        files = entry.get("files")
        if not isinstance(files, list) or not files:
            reject(task_id, "files must be a non-empty list of the files that hold an old reference")
            continue
        files_ok = True
        found_paths, found_names = set(), set()
        for file in files:
            if not isinstance(file, str) or not is_safe_relative_path(file) or not path_correction_form_ok(file):
                reject(
                    task_id,
                    f"file {file!r} does not have the file form (Unicode word characters, '.', '/' and '-' "
                    "only, equal to its normalized form, first segment not starting with '-')",
                    file if isinstance(file, str) else None,
                )
                files_ok = False
                continue
            text, reason = _read_base_document(target_repo, base_commit, file)
            if reason is not None:
                reject(task_id, f"file {file!r} is not a regular text file at the base commit: "
                       f"{_entry_file_reason_text(reason)}", file)
                files_ok = False
                continue
            occurrences = _scan_references(text, corrections)
            if not occurrences:
                reject(task_id, f"file {file!r} holds no old path and no bare old file name", file)
                files_ok = False
                continue
            for _start, _end, token, kind in occurrences:
                (found_paths if kind == "path" else found_names).add(token)
        if not files_ok:
            continue

        rendered = [
            c for c in corrections
            if (len(path_segments(c["old_path"])) > 1 and c["old_path"] in found_paths)
            or _correction_file_name(c["old_path"]) in found_names
        ]
        renderable = True
        for c in rendered:
            for key in ("old_path", "new_path"):
                if not path_correction_form_ok(c[key]):
                    reject(task_id, f"the {key} {c[key]!r} of a correction cannot be rendered into the "
                           "plan: it does not have the path form")
                    renderable = False
        if not renderable:
            continue

        plan = entry.get("plan")
        if not isinstance(plan, str) or not plan:
            reject(task_id, "plan must be a non-empty path")
            continue
        text, absent, problem = _read_current_document(Path(feature_dir), plan)
        if absent:
            reject(task_id, f"plan {plan!r} does not exist", plan)
        elif problem is not None:
            reject(task_id, f"plan {plan!r} {problem}", plan)
        elif text != canonical_correction_plan(task_id, files, rendered):
            reject(task_id, f"plan {plan!r} differs from the canonical correction plan", plan)
    return errors


def _correction_entry_limit_errors(workflow, corrections, patch, feature_dir, target_repo, base_commit):
    """The FR1 limits, run on the correction entry only (the Re-planning path
    and every other state are not limited), after condition 5 and outside the
    five numbered conditions: `path-correction-requirements` for
    `requirements_patch` and `path-correction-entries` for
    `tasks_patch.entries`."""
    return _correction_requirements_errors(workflow, patch) + _correction_entries_errors(
        corrections, patch, feature_dir, target_repo, base_commit
    )


def _carried_report_name_errors(workflow, new_workflow, patch, target_repo, base_commit):
    """FR3 on the files, after corrections, of every id in `carried_task_ids`
    whose status in `workflow` is not `merged`: `report-name-new-file`, the
    same code and the same exit 2 rule as for an entry."""
    carried_raw = (patch.get("tasks_patch") or {}).get("carried_task_ids")
    if not isinstance(carried_raw, list):
        return []
    before, after = _tasks_of(workflow), _tasks_of(new_workflow)
    files_by_task = {}
    for task_id in carried_raw:
        if not isinstance(task_id, str) or task_id in files_by_task:
            continue
        record, new_record = before.get(task_id), after.get(task_id)
        if not isinstance(record, dict) or not isinstance(new_record, dict):
            continue
        if record.get("status") == "merged":
            continue
        files_by_task[task_id] = new_record.get("files")
    return [
        err(
            REPORT_NAME_ERROR_CODE,
            f"tasks.{task_id}.files entry {path!r} of a carried task has a report artifact name and "
            "is not a regular file at the base commit; a new file with such a name is rejected "
            "by Claude Code's Write (skills/plan-writing/SKILL.md, Report Artifact Names)",
            task_id=task_id,
            path=path,
        )
        for task_id, path in find_report_name_violations(files_by_task, target_repo, base_commit)
    ]


# ---------------------------------------------------------------------------
# Feature-docs correction (plan-feature-docs-route/task0006, FR8 and FR9)
#
# `tasks_patch.feature_docs_removals` removes feature-docs paths from carried
# task records on the correction entry (create-plan `completed`, implement
# `failed`). IMPLEMENTATION.md D7 owns the bindings and references/
# workflow-patch.md, "Feature-docs correction", owns the contract text. Like
# the final-path correction it is the exception to the verbatim copy of a
# carried record, and it changes `files` and `notes` and nothing else:
#
# - The structural shape is checked with and without --dry-run-apply.
# - Under --dry-run-apply the permission comes first: only the correction
#   entry admits the field. On it, `feature_docs_removal_precondition_errors`
#   (the one function the entry script `scripts/feature-docs-entry.py` calls
#   too) judges the in-flight, merged, path and empty-files conditions, then
#   the limits follow, the in-memory application runs and the
#   `-incomplete` check judges its result.
# - The plan agreement (`task-plan-files-mismatch`) is shared with the
#   final-path correction (`_validate_corrected_task_plans`).
# - A feature-docs path is expressed as the append check of
#   `validate_task_entry` expresses it: the first segment after
#   `path_segments` is exactly `feature-docs`.
# ---------------------------------------------------------------------------

FEATURE_DOCS_REMOVAL_KEYS = frozenset({"task_id", "path"})


def _feature_docs_removals_field(patch):
    tasks_patch = patch.get("tasks_patch") if isinstance(patch, dict) else None
    return tasks_patch.get("feature_docs_removals") if isinstance(tasks_patch, dict) else None


def patch_has_feature_docs_removals(patch):
    """True when the patch carries a non-empty list in
    `tasks_patch.feature_docs_removals`, whatever its elements hold."""
    field = _feature_docs_removals_field(patch)
    return isinstance(field, list) and bool(field)


def feature_docs_removal_shape_errors(patch):
    """The structural check of `tasks_patch.feature_docs_removals` (error code
    `feature-docs-removal-shape`), the same with and without --dry-run-apply:
    when present it is a non-empty list of mappings with exactly `task_id` and
    `path` (non-empty strings), on `replace_planning` only; every `task_id` is
    in the patch's own `carried_task_ids`; each (task_id, path) pair appears
    once; `path_corrections` is absent. Absent and null are the same. A
    malformed value is an error of this code and the rest of the check is
    skipped for it; nothing raises."""
    field = _feature_docs_removals_field(patch)
    if field is None:
        return []
    label = "tasks_patch.feature_docs_removals"
    errors = []

    def bad(message):
        errors.append(err("feature-docs-removal-shape", f"{label}{message}"))

    if patch.get("operation") != "replace_planning":
        bad(" is permitted on replace_planning only")
        return errors
    if not isinstance(field, list) or not field:
        bad(" must be a non-empty list of mappings")
        return errors
    tasks_patch = patch["tasks_patch"]
    if tasks_patch.get("path_corrections") is not None:
        bad(" must not be used together with tasks_patch.path_corrections")
    carried_raw = tasks_patch.get("carried_task_ids")
    carried = {c for c in carried_raw if isinstance(c, str)} if isinstance(carried_raw, list) else set()
    seen = set()
    for i, item in enumerate(field):
        if not isinstance(item, dict):
            bad(f"[{i}] must be a mapping")
            continue
        if set(item) != FEATURE_DOCS_REMOVAL_KEYS:
            bad(f"[{i}] must hold exactly task_id and path")
            continue
        task_id, path = item["task_id"], item["path"]
        if not all(isinstance(v, str) and v for v in (task_id, path)):
            bad(f"[{i}] task_id and path must be non-empty strings")
            continue
        if task_id not in carried:
            bad(f"[{i}].task_id {task_id!r} is not in tasks_patch.carried_task_ids")
        if (task_id, path) in seen:
            bad(f"[{i}] repeats the removal of {path!r} from {task_id}")
        seen.add((task_id, path))
    return errors


def _well_formed_feature_docs_removals(patch):
    """The list of removals (mappings with the two strings) when the field
    passes `feature_docs_removal_shape_errors`, else []."""
    if not patch_has_feature_docs_removals(patch) or feature_docs_removal_shape_errors(patch):
        return []
    return [dict(item) for item in _feature_docs_removals_field(patch)]


def _apply_feature_docs_removals(tasks, removals):
    """In-memory application on a {task_id: record} mapping the caller owns
    (a copy): every occurrence of `path` leaves the target's `files` and
    `notes` is set to null; every other field stays verbatim. A removal naming
    a task that is not in `tasks` is skipped."""
    for removal in removals:
        record = tasks.get(removal.get("task_id"))
        if not isinstance(record, dict):
            continue
        files = record.get("files")
        if isinstance(files, list):
            record["files"] = [f for f in files if f != removal["path"]]
        record["notes"] = None


def _require_feature_docs_removal_inputs(patch, *, workflow, journal, feature_dir):
    """Under --dry-run-apply a non-empty `feature_docs_removals` needs
    --workflow, --journal and --feature-dir: a missing one is an execution
    error (exit 2), never a pass."""
    if not patch_has_feature_docs_removals(patch):
        return
    missing = [
        flag
        for flag, value in (("--workflow", workflow), ("--journal", journal), ("--feature-dir", feature_dir))
        if value is None
    ]
    if missing:
        raise ExecutionError(
            "--dry-run-apply of a patch with feature_docs_removals requires " + ", ".join(missing)
        )


def _workflow_on_correction_entry(workflow):
    """True when `workflow` is on the correction entry: create-plan
    `completed` and implement `failed`. False without a workflow mapping."""
    if not isinstance(workflow, dict):
        return False
    create_plan = workflow_find_step(workflow, "create-plan")
    implement = workflow_find_step(workflow, "implement")
    return (
        (create_plan.get("status") if create_plan else None) == "completed"
        and (implement.get("status") if implement else None) == "failed"
    )


def _last_event_name(value):
    """The event of a `journal_last_events` value `(event, line)`; None for a
    value of any other shape."""
    return value[0] if isinstance(value, (tuple, list)) and value else None


def feature_docs_removal_precondition_errors(workflow, removals, last_events):
    """The conditions of a feature-docs correction that the workflow and the
    journal decide, one error code each, in this order. A removal is a mapping
    with `task_id` and `path`; the entry script supplies them from its
    targets. `last_events` is `journal_last_events`.

    1. `feature-docs-removal-in-flight`: one error per task whose status is
       `in_progress` or whose journal last event is `launched` (any task, not
       only a target).
    2. `feature-docs-removal-merged`: one error per target task whose status or
       journal last event is `merged`.
    3. `feature-docs-removal-path`: one error per removal whose `path` is not a
       feature-docs path or is not in the target's `files`.
    4. `feature-docs-removal-empty-files`: one error per target task whose
       `files` would be empty once every feature-docs path named for it is
       removed.

    A malformed input (a record that is not a mapping, a removal that is not a
    mapping) is skipped or judged by condition 3; nothing raises."""
    errors = []
    tasks = _tasks_of(workflow)
    last_events = last_events if isinstance(last_events, dict) else {}
    removals = [r for r in removals if isinstance(r, dict)] if isinstance(removals, (list, tuple)) else []

    in_flight = {
        task_id
        for task_id, record in tasks.items()
        if isinstance(record, dict) and record.get("status") == "in_progress"
    }
    in_flight |= {task_id for task_id, value in last_events.items() if _last_event_name(value) == "launched"}
    for task_id in sorted(in_flight, key=str):
        errors.append(
            err(
                "feature-docs-removal-in-flight",
                f"{task_id}: a feature-docs correction requires no task in flight "
                "(status in_progress or last journal event launched)",
                task_id=task_id,
            )
        )

    targets = []  # distinct target task ids, in removal order
    for removal in removals:
        task_id = removal.get("task_id")
        if isinstance(task_id, str) and task_id not in targets:
            targets.append(task_id)
    for task_id in targets:
        record = tasks.get(task_id)
        status = record.get("status") if isinstance(record, dict) else None
        last_event = _last_event_name(last_events.get(task_id))
        if status == "merged" or last_event == "merged":
            errors.append(
                err(
                    "feature-docs-removal-merged",
                    f"{task_id}: the target task is merged (status {status!r}, last journal event "
                    f"{last_event!r}); its record cannot be corrected",
                    task_id=task_id,
                )
            )

    named = {}  # task_id -> the feature-docs paths named for it
    for removal in removals:
        task_id, path = removal.get("task_id"), removal.get("path")
        record = tasks.get(task_id) if isinstance(task_id, str) else None
        files = record.get("files") if isinstance(record, dict) else None
        if not (isinstance(path, str) and path_segments(path)[:1] == ["feature-docs"]):
            reason = "is not a feature-docs path"
        elif not isinstance(files, list) or path not in files:
            reason = "is not in the target task's files"
        else:
            named.setdefault(task_id, set()).add(path)
            continue
        errors.append(
            err(
                "feature-docs-removal-path",
                f"{task_id}: path {path!r} {reason}",
                task_id=task_id,
                path=path,
            )
        )

    for task_id, paths in named.items():
        files = tasks[task_id]["files"]
        remaining = [f for f in files if not (isinstance(f, str) and f in paths)]
        if not remaining:
            errors.append(
                err(
                    "feature-docs-removal-empty-files",
                    f"{task_id}: files would be empty once {sorted(paths)} are removed; "
                    "a task with no file cannot be corrected",
                    task_id=task_id,
                )
            )
    return errors


def _feature_docs_removal_limit_errors(patch):
    """`feature-docs-removal-limits`: on the correction entry `step_patches`
    and `tasks_patch.entries` are empty and `requirements_patch` is null or
    holds no entries. One error per breach."""
    errors = []

    def reject(message):
        errors.append(err("feature-docs-removal-limits", message))

    if patch.get("step_patches"):
        reject("a feature-docs correction requires step_patches to be empty")
    tasks_patch = patch.get("tasks_patch")
    if isinstance(tasks_patch, dict) and tasks_patch.get("entries"):
        reject("a feature-docs correction requires tasks_patch.entries to be empty")
    requirements_patch = patch.get("requirements_patch")
    if isinstance(requirements_patch, dict) and requirements_patch.get("entries"):
        reject("a feature-docs correction requires requirements_patch to be null or to hold no entries")
    return errors


def _feature_docs_removal_incomplete_errors(new_workflow):
    """`feature-docs-removal-incomplete`: one error per task of the patched
    workflow whose status is not `merged` and whose `files` still hold a
    feature-docs path."""
    errors = []
    for task_id, record in _tasks_of(new_workflow).items():
        if not isinstance(record, dict) or record.get("status") == "merged":
            continue
        files = record.get("files")
        remaining = (
            [f for f in files if isinstance(f, str) and path_segments(f)[:1] == ["feature-docs"]]
            if isinstance(files, list)
            else []
        )
        if remaining:
            errors.append(
                err(
                    "feature-docs-removal-incomplete",
                    f"{task_id}: files still hold feature-docs paths after the patch: {remaining}",
                    task_id=task_id,
                    paths=remaining,
                )
            )
    return errors


# ---------------------------------------------------------------------------
# --kind workflow-patch (5.5)
# ---------------------------------------------------------------------------

def _verify_step_targeted_by_patch(patch):
    """rework-contract-drift/task0008 (FR3, NFR1, NFR2, D11): True when
    `patch`'s `step_patches` names `step_id` `verify` -- the only channel a
    worker patch has for reaching the verify step at all (a `step_patches`
    entry's `set` may touch only `status`; workflow-patch.md's
    `step_patches` contract, cited not restated). None/absent
    `step_patches`, a non-list, or `step_patches` naming other steps only,
    is not targeting."""
    if not isinstance(patch, dict):
        return False
    step_patches = patch.get("step_patches")
    if not isinstance(step_patches, list):
        return False
    return any(
        isinstance(sp, dict) and sp.get("step_id") == "verify"
        for sp in step_patches
    )


def _validate_verify_failed_items_categories(workflow, patch):
    """rework-contract-drift/task0004 (FR3 validator half, FR6), scoped by
    rework-contract-drift/task0008 (FR3 rework, NFR1, NFR2, D11): every
    entry of `workflow.yaml`'s `verify` step `failed_items[]` that `patch`
    REACHES carries a REQUIRED, non-empty `category` drawn from
    FAILED_ITEM_CATEGORY_VALUES (references/workflow-schema.md owns the
    field's definition, vocabulary and the pre-change compatibility rule
    this scoping implements; this function enforces it, never restates the
    vocabulary in prose elsewhere). `patch` reaches the verify step's
    entries only when it targets that step via `step_patches` (see
    `_verify_step_targeted_by_patch`) -- a pre-existing entry a patch
    neither supplies nor targets contributes no error here, because the
    party that would receive the rejection (a worker's step patch) has no
    way to repair it. Runs on the invocation path that already reads
    `--workflow` (validate_workflow_patch), unconditional on
    --dry-run-apply. Tolerates a missing/absent verify step or
    failed_items list (nothing to check yet) and a non-mapping entry
    (reported elsewhere, not this function's job) rather than crashing."""
    errors = []
    if not _verify_step_targeted_by_patch(patch):
        return errors
    verify_step = workflow_find_step(workflow, "verify")
    if not isinstance(verify_step, dict):
        return errors
    failed_items = verify_step.get("failed_items")
    if not isinstance(failed_items, list):
        return errors
    for i, item in enumerate(failed_items):
        if not isinstance(item, dict):
            continue
        if item.get("category") not in FAILED_ITEM_CATEGORY_VALUES:
            errors.append(
                err(
                    "category",
                    f"workflow.yaml verify.failed_items[{i}].category must "
                    f"be one of {sorted(FAILED_ITEM_CATEGORY_VALUES)} "
                    "(missing, empty, or out of vocabulary)",
                )
            )
    return errors


def _as_checked_list(container, key, p, field_label, errors):
    """bs9 (round 2): returns `container.get(key)` coerced to a list for
    iteration, appending a machine-readable error (instead of raising) when
    the value is present but not actually a list -- e.g. a bare string,
    which would otherwise be iterated silently per-character."""
    value = container.get(key)
    if value is None:
        return []
    if not isinstance(value, list):
        errors.append(err(field_label, f"{p}.{field_label} must be a list"))
        return []
    return value


def validate_task_entry(task_id, entry, mode, registries, workflow):
    errors = []
    p = f"tasks_patch.entries[{task_id}]"
    if not isinstance(entry, dict):
        return [err("tasks_patch.entries", f"{p} must be a mapping")]
    if not TASK_ID_RE.match(task_id):
        errors.append(err("task_id", f"{task_id!r} must match {TASK_ID_RE.pattern}"))
    files = _as_checked_list(entry, "files", p, "files", errors)
    for f in files:
        if not is_safe_relative_path(f):
            errors.append(err("files", f"{p}.files entry {f!r} is not a safe project-relative path"))
    skills = _as_checked_list(entry, "skills", p, "skills", errors)
    if registries is not None:
        allowed_skills = registries.get("skills")
        if allowed_skills is not None:
            for s in skills:
                if s not in allowed_skills:
                    errors.append(err("skills", f"{p}.skills entry {s!r} is not registered in impl-skills.yaml"))
    domains = _as_checked_list(entry, "domains", p, "domains", errors)
    if registries is not None:
        allowed_domains = registries.get("domains")
        if allowed_domains is not None:
            for d in domains:
                if d not in allowed_domains:
                    errors.append(err("domains", f"{p}.domains entry {d!r} is not in review-rules.yaml vocabulary"))
    if entry.get("complexity") not in COMPLEXITY_VALUES:
        errors.append(err("complexity", f"{p}.complexity must be one of {sorted(COMPLEXITY_VALUES)}"))
    requirements = _as_checked_list(entry, "requirements", p, "requirements", errors)
    if workflow is not None:
        known = workflow_requirement_ids(workflow)
        for r in requirements:
            if r not in known:
                errors.append(err("requirements", f"{p}.requirements entry {r!r} does not exist in workflow.yaml"))
    if entry.get("initial_status") != "pending":
        errors.append(err("initial_status", f"{p}.initial_status must be 'pending'"))
    if ROUTEBACK_RECORD_FIELD in entry:
        errors.append(
            err(
                ROUTEBACK_RECORD_FIELD,
                f"{p}.{ROUTEBACK_RECORD_FIELD} must not be set by a worker "
                "(orchestrator-only route-back record; see "
                "references/workflow-schema.md)",
            )
        )
    if mode == "append":
        provenance = entry.get("provenance")
        if not provenance:
            errors.append(err("provenance", f"{p}.provenance is required for append"))
        elif not isinstance(provenance, dict):
            errors.append(err("provenance", f"{p}.provenance must be a mapping"))
        elif provenance.get("source") not in ("review", "verify"):
            errors.append(err("provenance", f"{p}.provenance.source must be 'review' or 'verify'"))
        # rework-docs-only-task-routing/task0004 (FR3, TM-1): `append` is the
        # mode bound to `append_rework`, so this is the rework-synthesized
        # task entry; the `replace_all` mode (`replace_planning`) has its own
        # check and code below (plan-feature-docs-route/task0004). A path
        # is a planning document when its first normalized segment
        # (path_segments: `\` as `/`, empty and `.` dropped) is exactly
        # `feature-docs` -- exact segment equality, so `feature-docs-archive/x`
        # and `src/feature-docs/x` pass. The rule's prose is owned by
        # references/rework-task-synthesis.md, cited not restated.
        for f in files:
            if isinstance(f, str) and path_segments(f)[:1] == ["feature-docs"]:
                errors.append(
                    err(
                        "rework-task-feature-docs",
                        f"{p}.files entry {f!r} is a feature-docs planning document; "
                        "a rework-synthesized task's files must not reach feature-docs/**",
                    )
                )
    elif mode == "replace_all":
        # plan-feature-docs-route/task0004 (FR2, NFR2; IMPLEMENTATION.md D1):
        # a planned task's `files` must not reach `feature-docs/**`. One
        # `plan-task-feature-docs` error per offending path, the message
        # holding the task id and the path as given. The predicate is the
        # append check's own (path_segments, first segment exactly
        # `feature-docs`); a non-string element and a non-list `files` are
        # already reported by the `files` code above and are skipped here, so
        # this never raises. Only `tasks_patch.entries` pass through this
        # function: carried tasks (`carried_task_ids`) are copied verbatim and
        # never checked. The rule's prose is owned by
        # skills/plan-writing/SKILL.md `## Feature-docs Files`, cited not
        # restated.
        for f in files:
            if isinstance(f, str) and path_segments(f)[:1] == ["feature-docs"]:
                errors.append(
                    err(
                        "plan-task-feature-docs",
                        f"{p}.files entry {f!r} is a feature-docs path; "
                        "a planned task's files must not reach feature-docs/** "
                        "(skills/plan-writing/SKILL.md, ## Feature-docs Files)",
                    )
                )
    return errors


def _validate_tests_replace_entry(fr_id, rpatch):
    """rework-docs-only-task-routing/task0003 (FR2, FR4): the structural
    half of the `requirements_patch` tests replacement
    (references/workflow-patch.md, `requirements_patch` section, owns the
    operation; IMPLEMENTATION.md D3 owns the binding). For one requirement
    entry: `set.tests_replace`, when present, is a non-empty list of
    mappings with non-empty string `from` and `to`, `from` different from
    `to`, no `from` repeated, and every `from` listed in the entry's
    `expected.tests_contains`; `expected.tests_contains`, when present, is
    a list of strings (also without any replacement beside it).
    rework-docs-only-medium-fixes/task0003 (FR4, IMPLEMENTATION.md D4): the
    entry's `from` set (the string `from` values of its mapping pairs) and
    `to` set (the string `to` values) must not share an ID, so a sequential
    application can never lose a scenario reference (a chain TS-1->TS-2,
    TS-2->TS-3 and a swap TS-1->TS-2, TS-2->TS-1 both share one); pairs that
    only share a `to` do not overlap. Every
    finding carries the code `requirements_patch`. Malformed input is a
    finding, never an exception: nothing here is hashed or indexed before
    it is known to be a string, and a non-mapping `set` / `expected` is
    left to the checks that already report it."""
    errors = []
    p = f"requirements_patch.entries[{fr_id}]"
    expected = rpatch.get("expected")
    if not isinstance(expected, dict):
        expected = {}
    listed = []
    contains_malformed = False
    if "tests_contains" in expected:
        value = expected["tests_contains"]
        if isinstance(value, list) and all(isinstance(i, str) for i in value):
            listed = value
        else:
            contains_malformed = True
            errors.append(err("requirements_patch", f"{p}.expected.tests_contains must be a list of strings"))
    set_block = rpatch.get("set")
    if not isinstance(set_block, dict) or "tests_replace" not in set_block:
        return errors
    pairs = set_block["tests_replace"]
    if not isinstance(pairs, list) or not pairs:
        errors.append(err("requirements_patch", f"{p}.set.tests_replace must be a non-empty list of from/to pairs"))
        return errors
    seen_from = set()
    for i, pair in enumerate(pairs):
        q = f"{p}.set.tests_replace[{i}]"
        if not isinstance(pair, dict):
            errors.append(err("requirements_patch", f"{q} must be a mapping with 'from' and 'to'"))
            continue
        old, new = pair.get("from"), pair.get("to")
        if not (isinstance(old, str) and old and isinstance(new, str) and new):
            errors.append(err("requirements_patch", f"{q} 'from' and 'to' must be non-empty strings"))
            continue
        if old == new:
            errors.append(err("requirements_patch", f"{q} 'from' and 'to' must differ ({old!r})"))
        if old in seen_from:
            errors.append(err("requirements_patch", f"{q} repeats 'from' {old!r} within one entry"))
        seen_from.add(old)
        if not contains_malformed and old not in listed:
            errors.append(err("requirements_patch", f"{q} 'from' {old!r} must be listed in {p}.expected.tests_contains"))
    # FR4 / D4: only string values of mapping pairs enter the two sets, so a
    # malformed pair (a non-string, unhashable `from` / `to`, a missing key)
    # is never hashed here and stays with the shape findings above.
    mapping_pairs = [pair for pair in pairs if isinstance(pair, dict)]
    from_ids = {pair["from"] for pair in mapping_pairs if isinstance(pair.get("from"), str)}
    to_ids = {pair["to"] for pair in mapping_pairs if isinstance(pair.get("to"), str)}
    overlap = sorted(from_ids & to_ids)
    if overlap:
        errors.append(
            err(
                "requirements_patch",
                f"{p}.set.tests_replace 'from' and 'to' share {overlap!r}: a sequential "
                "application would lose a scenario reference (no ID may be both replaced "
                "and a replacement within one entry)",
            )
        )
    return errors


# rework-docs-only-medium-fixes/task0002 (FR3, IMPLEMENTATION.md D3): the two
# steps a docs-only round may return to `pending` -- the origin of the rework,
# which is the `type` of the input envelope's `rework_source` (`review` or
# `verify`).
DOCS_ONLY_ORIGIN_STEPS = ("verify", "review")


def _docs_only_origin_steps(envelope):
    """rework-docs-only-medium-fixes/task0002 (FR3, NFR1, D3): the step ids
    that a docs-only round's single step patch may target. Taken from the
    run's input envelope when the validator holds one:

    - `rework_source` is a mapping whose `type` is exactly the string
      `review` or `verify`: that one step.
    - no envelope (or one that is not a mapping), no `rework_source` key, or
      a `rework_source` mapping without a `type` key: either of
      DOCS_ONLY_ORIGIN_STEPS.
    - `rework_source` present but not a mapping, or `type` present with any
      other value (null, a non-string, another string): the empty tuple --
      no origin step, so no step patch can match it (fail-closed).

    Never raises: nothing here is hashed or indexed before it is known to be
    a string."""
    if not isinstance(envelope, dict) or "rework_source" not in envelope:
        return DOCS_ONLY_ORIGIN_STEPS
    rework_source = envelope["rework_source"]
    if not isinstance(rework_source, dict):
        return ()
    if "type" not in rework_source:
        return DOCS_ONLY_ORIGIN_STEPS
    source_type = rework_source["type"]
    if isinstance(source_type, str) and source_type in DOCS_ONLY_ORIGIN_STEPS:
        return (source_type,)
    return ()


def _docs_only_step_patches_violation(step_patches, origin_steps):
    """rework-docs-only-medium-fixes/task0002 (FR3, NFR1, D3): None when
    `step_patches` (the patch's raw value) is a list of exactly one mapping
    whose `step_id` is one of `origin_steps` and whose `set.status` is the
    string `pending`; otherwise the message naming the first violated
    condition -- the count, the step_id against the origin, or the status.
    Never raises on a malformed shape; a malformed shape is a violation."""
    if not isinstance(step_patches, list):
        return (
            "step_patches must be a list holding exactly one entry, for the origin step "
            "(a docs-only round)"
        )
    if len(step_patches) != 1:
        return (
            f"step_patches holds {len(step_patches)} entries; a docs-only round "
            "(append_rework with no tasks_patch.entries) requires exactly one, for the origin step"
        )
    entry = step_patches[0]
    if not isinstance(entry, dict):
        return "step_patches[0] must be a mapping (a docs-only round requires exactly one entry, for the origin step)"
    step_id = entry.get("step_id")
    if not isinstance(step_id, str) or step_id not in origin_steps:
        if origin_steps:
            wanted = " or ".join(repr(step) for step in origin_steps)
            return f"step_patches[0].step_id {step_id!r} is not the origin step ({wanted})"
        return (
            f"step_patches[0].step_id {step_id!r} cannot match an origin step: the input "
            "envelope's rework_source is not a mapping whose type is 'review' or 'verify'"
        )
    set_block = entry.get("set")
    status = set_block.get("status") if isinstance(set_block, dict) else None
    if status != "pending":
        return f"step_patches[0].set.status must be 'pending', got {status!r}"
    return None


def validate_workflow_patch(
    data,
    *,
    workflow=None,
    registries=None,
    digest_source=None,
    phase_state=None,
    dry_run=False,
    feature_dir=None,
    envelope=None,
    target_repo=None,
    base_commit=None,
    journal=None,
):
    if not isinstance(data, dict):
        return [err("structure", "workflow patch must be a mapping")]
    errors = []
    if workflow is not None:
        # FR3 validator half / FR6, scoped by task0008 (FR3 rework, D11):
        # this is the invocation path that already reads --workflow
        # (workflow_requirement_ids below); the verify-step
        # failed_items[].category vocabulary is enforced here too,
        # unconditional on --dry-run-apply, scoped to what `data` (this
        # patch) reaches -- see _validate_verify_failed_items_categories.
        errors.extend(_validate_verify_failed_items_categories(workflow, data))
    if data.get("schema_version") != 1:
        errors.append(err("schema_version", "schema_version must be 1"))
    patch_id = data.get("patch_id")
    if not isinstance(patch_id, str) or not PATCH_ID_RE.match(patch_id):
        errors.append(err("patch_id", f"patch_id must match {PATCH_ID_RE.pattern}"))
    if not data.get("base_input_digest"):
        errors.append(err("base_input_digest", "base_input_digest is required"))
    if not data.get("base_workflow_blob"):
        errors.append(err("base_workflow_blob", "base_workflow_blob is required"))
    operation = data.get("operation")
    if operation not in OPERATION_VALUES:
        errors.append(err("operation", f"operation must be one of {sorted(OPERATION_VALUES)}"))
        return errors  # nothing further can be checked safely

    tasks_patch = data.get("tasks_patch") or {}
    mode = tasks_patch.get("mode")
    expected_mode = OPERATION_TASKS_PATCH_MODE[operation]
    if mode != expected_mode:
        errors.append(err("tasks_patch.mode", f"operation {operation} requires tasks_patch.mode {expected_mode!r}, got {mode!r}"))
    if mode == "append" and not tasks_patch.get("expected_next_task_id"):
        errors.append(err("tasks_patch", "expected_next_task_id is required when mode is append"))

    entries = tasks_patch.get("entries") or {}
    if not isinstance(entries, dict):
        errors.append(err("tasks_patch.entries", "tasks_patch.entries must be a mapping"))
        entries = {}
    for task_id, entry in entries.items():
        errors.extend(validate_task_entry(task_id, entry, mode, registries, workflow))

    # Report artifact names (subagent-report-write-block/task0001, FR3):
    # a new file with a matching name in any entry is rejected, for both
    # operations, with and without --dry-run-apply, whatever the entry's plan
    # (a TASK.md plan included). --target-repo / --base-commit are read only
    # when a matching name is present (FR4); a failure to use them raises
    # ExecutionError, which main() turns into exit 2.
    errors.extend(_report_name_errors(entries, target_repo, base_commit))

    # Re-planning carry-over declaration (workflow-patch.md "Re-planning
    # task-id allocation"): tasks_patch.carried_task_ids -- structural shape
    # only (each entry is a taskNNNN-shaped string). The semantic checks
    # (every registered id carried, no unregistered id carried, no
    # registered id re-entered under entries) need workflow.yaml and the
    # re-planning/initial-planning distinction, so they live in
    # _validate_dry_run_apply instead, alongside the other replace_all
    # permission checks that already depend on the same distinction.
    carried_task_ids = tasks_patch.get("carried_task_ids")
    if carried_task_ids is not None:
        if not isinstance(carried_task_ids, list):
            errors.append(err("tasks_patch.carried_task_ids", "tasks_patch.carried_task_ids must be a list"))
        else:
            for cid in carried_task_ids:
                if not isinstance(cid, str) or not TASK_ID_RE.match(cid):
                    errors.append(
                        err(
                            "tasks_patch.carried_task_ids",
                            f"tasks_patch.carried_task_ids entry {cid!r} must match {TASK_ID_RE.pattern}",
                        )
                    )

    # Final-path correction (workflow-patch.md "Final-path correction"):
    # the structural shape of tasks_patch.path_corrections, with and without
    # --dry-run-apply. The permission state, the conditions and the
    # application need workflow.yaml and live in _validate_dry_run_apply.
    errors.extend(path_correction_shape_errors(data))

    # Feature-docs correction (workflow-patch.md "Feature-docs correction"):
    # the structural shape of tasks_patch.feature_docs_removals, with and
    # without --dry-run-apply. The permission, the conditions and the
    # application need workflow.yaml and live in _validate_dry_run_apply.
    errors.extend(feature_docs_removal_shape_errors(data))

    requirements_patch = data.get("requirements_patch")
    if requirements_patch is not None:
        if not isinstance(requirements_patch, dict):
            errors.append(err("requirements_patch", "requirements_patch must be a mapping"))
            requirements_patch = {}
        if requirements_patch and requirements_patch.get("mode") != "merge_entries":
            errors.append(err("requirements_patch", "requirements_patch.mode must be 'merge_entries'"))
        rp_entries = requirements_patch.get("entries") or {}
        if not isinstance(rp_entries, dict):
            errors.append(err("requirements_patch", "requirements_patch.entries must be a mapping"))
            rp_entries = {}
        for fr_id, rpatch in rp_entries.items():
            if not REQUIREMENT_ID_RE.match(fr_id):
                errors.append(err("requirements_patch", f"{fr_id!r} must match {REQUIREMENT_ID_RE.pattern}"))
            if not isinstance(rpatch, dict):
                errors.append(err("requirements_patch", f"requirements_patch.entries[{fr_id}] must be a mapping"))
                continue
            set_block = rpatch.get("set") or {}
            for k in set_block:
                if k not in REQUIREMENTS_PATCH_SET_KEYS:
                    errors.append(err("requirements_patch", f"requirements_patch.entries[{fr_id}].set has disallowed key {k!r}"))
            errors.extend(_validate_tests_replace_entry(fr_id, rpatch))

    step_patches = data.get("step_patches")
    if step_patches is None:
        errors.append(err("step_patches", "step_patches is required (an empty list is permitted when no step transition is proposed)"))
        step_patches = []
    elif not isinstance(step_patches, list):
        errors.append(err("step_patches", "step_patches must be a list"))
        step_patches = []
    for i, sp in enumerate(step_patches):
        if not isinstance(sp, dict):
            errors.append(err("step_patches", f"step_patches[{i}] must be a mapping"))
            continue
        step_id = sp.get("step_id")
        if not step_id:
            errors.append(err("step_patches", f"step_patches[{i}].step_id is required"))
        elif not isinstance(step_id, str):
            errors.append(err("step_patches", f"step_patches[{i}].step_id must be a string"))
        set_block = sp.get("set") or {}
        if not isinstance(set_block, dict):
            errors.append(err("step_patches", f"step_patches[{i}].set must be a mapping"))
        elif set(set_block) - {"status"}:
            errors.append(err("step_patches", f"step_patches[{i}].set may only contain 'status'"))
        # A non-string step_id was reported above and is never looked up
        # (it may not even be hashable).
        step_id_is_lookupable = step_id is None or isinstance(step_id, str)
        if workflow is not None and step_id_is_lookupable and step_id not in workflow_step_ids(workflow):
            errors.append(err("step_patches", f"step_patches[{i}].step_id {step_id!r} does not exist in workflow.yaml"))

    # A docs-only round is recognized by empty task entries (no new patch
    # field marks it): an `append_rework` patch whose `tasks_patch.entries`
    # is absent or empty. "Empty" follows this function's own reading of
    # `entries` above (`tasks_patch.get("entries") or {}`). Structural layer:
    # runs with and without --dry-run-apply, and on both routes that
    # validate a patch. The rule's prose is owned by
    # references/rework-task-synthesis.md ("Docs-only correction route"),
    # cited not restated. Two independent checks, either or both of which
    # may report on one patch:
    #
    # - rework-docs-only-task-routing/task0004 (FR5, TM-2), widened by
    #   rework-docs-only-medium-fixes/task0002 (FR3): every step patch that
    #   targets `implement` is `docs-only-implement-reset`, whatever its
    #   set.status is -- implement stays completed.
    # - rework-docs-only-medium-fixes/task0002 (FR3, D3):
    #   `docs-only-step-patches`, once per patch, unless step_patches is
    #   exactly one entry for the origin step with set.status `pending`. The
    #   origin step comes from the input envelope's rework_source
    #   (`_docs_only_origin_steps`).
    if operation == "append_rework" and not tasks_patch.get("entries"):
        for i, sp in enumerate(step_patches):
            if isinstance(sp, dict) and sp.get("step_id") == "implement":
                errors.append(
                    err(
                        "docs-only-implement-reset",
                        f"step_patches[{i}] targets implement on an append_rework patch "
                        "with no tasks_patch.entries (a docs-only round); implement must stay completed",
                    )
                )
        violation = _docs_only_step_patches_violation(
            data.get("step_patches"), _docs_only_origin_steps(envelope)
        )
        if violation is not None:
            errors.append(err("docs-only-step-patches", violation))

    preserve = data.get("preserve")
    if preserve is None:
        errors.append(err("preserve", "preserve is required"))
        preserve = []
    elif not isinstance(preserve, list):
        errors.append(err("preserve", "preserve must be a list"))
        preserve = []
    preserve_strs = []
    for p in preserve:
        if not isinstance(p, str):
            errors.append(err("preserve", f"preserve entry {p!r} must be a string"))
            continue
        preserve_strs.append(p)
        if not is_preserve_path_allowed(p):
            errors.append(err("preserve", f"preserve path {p!r} is not in the permitted vocabulary"))
    required_preserve = REQUIRED_PRESERVE_BY_OPERATION.get(operation, set())
    missing_preserve = required_preserve - set(preserve_strs)
    if missing_preserve:
        errors.append(err("preserve", f"operation {operation} requires preserve to include {sorted(missing_preserve)}"))

    if dry_run:
        errors.extend(
            _validate_dry_run_apply(
                data,
                workflow=workflow,
                digest_source=digest_source,
                phase_state=phase_state,
                feature_dir=feature_dir,
                target_repo=target_repo,
                base_commit=base_commit,
                journal=journal,
            )
        )

    return errors


def _validate_dry_run_apply(
    data,
    *,
    workflow,
    digest_source,
    phase_state,
    feature_dir=None,
    target_repo=None,
    base_commit=None,
    journal=None,
):
    errors = []
    operation = data.get("operation")
    tasks_patch = data.get("tasks_patch") or {}
    mode = tasks_patch.get("mode")

    # Final-path correction inputs: a missing one or an unresolvable base is
    # an execution error (exit 2), decided before any other check.
    _require_path_correction_inputs(
        data,
        workflow=workflow,
        journal=journal,
        feature_dir=feature_dir,
        target_repo=target_repo,
        base_commit=base_commit,
    )
    corrections = _well_formed_path_corrections(data)
    # Feature-docs correction inputs (D7): a missing one is an execution
    # error (exit 2) as well, decided before any other check.
    _require_feature_docs_removal_inputs(data, workflow=workflow, journal=journal, feature_dir=feature_dir)
    removals = _well_formed_feature_docs_removals(data)

    if digest_source is None:
        errors.append(err("dry-run-apply", "--digest-source is required for --dry-run-apply"))
    else:
        expected_digest = normalize_json_sha256(digest_source)
        if data.get("base_input_digest") != expected_digest:
            errors.append(err("stale-input-digest", "base_input_digest does not match the recomputed digest_source digest (stale)"))
        if data.get("base_workflow_blob") != digest_source.get("workflow_blob"):
            errors.append(err("stale-workflow-blob", "base_workflow_blob does not match digest_source.workflow_blob (stale)"))

    if workflow is None:
        errors.append(err("dry-run-apply", "--workflow is required for --dry-run-apply"))
        return errors

    # Final-path correction (IMPLEMENTATION.md D2): the path state is decided
    # here, before the replace_all branch, so the corrections block below can
    # read it whatever `tasks_patch.mode` holds.
    path_state = correction_path_state(workflow, data, phase_state, feature_dir)
    # Feature-docs correction (IMPLEMENTATION.md D7): the field is admitted on
    # the correction entry only, where the replace_all below is permitted the
    # same way a final-path correction is.
    has_removals = patch_has_feature_docs_removals(data)
    removal_entry = has_removals and _workflow_on_correction_entry(workflow)

    # Rule 3: all `expected` values must match current state. A step_patches
    # that is not a list, or an element that is not a mapping, is reported by
    # the structural layer and has no `expected` to compare here.
    step_patches = data.get("step_patches")
    for i, sp in enumerate(step_patches if isinstance(step_patches, list) else []):
        if not isinstance(sp, dict):
            continue
        expected = sp.get("expected") or {}
        if "status" in expected:
            step = workflow_find_step(workflow, sp.get("step_id"))
            current_status = step.get("status") if step else None
            if current_status != expected["status"]:
                errors.append(err("expected-mismatch", f"step_patches[{i}] expected.status {expected['status']!r} does not match current {current_status!r}"))
    requirements_patch = data.get("requirements_patch") or {}
    for fr_id, rpatch in (requirements_patch.get("entries") or {}).items():
        expected = rpatch.get("expected") or {}
        tasks_contains = expected.get("tasks_contains")
        if tasks_contains is not None:
            current_tasks = (workflow.get("requirements", {}).get(fr_id) or {}).get("tasks") or []
            if not set(tasks_contains).issubset(current_tasks):
                errors.append(err("expected-mismatch", f"requirements_patch.entries[{fr_id}].expected.tasks_contains not satisfied by current workflow.yaml"))
        # rework-docs-only-task-routing/task0003 (FR4): the tests
        # replacement's expectation (workflow-patch.md, `requirements_patch`
        # section) -- every listed ID must be in the requirement's current
        # `tests`. A malformed `tests_contains` is reported by the
        # structural layer; it contributes nothing here.
        tests_contains = expected.get("tests_contains")
        if isinstance(tests_contains, list):
            current_reqs = workflow.get("requirements")
            current_req = current_reqs.get(fr_id) if isinstance(current_reqs, dict) else None
            current_tests = current_req.get("tests") if isinstance(current_req, dict) else None
            if not isinstance(current_tests, list):
                current_tests = []
            absent = [i for i in tests_contains if i not in current_tests]
            if absent:
                errors.append(err("expected-mismatch", f"requirements_patch.entries[{fr_id}].expected.tests_contains {absent!r} not satisfied by current workflow.yaml"))

    # Rule 5 / 5.5.1: replace_all permission conditions. Two permitted
    # paths (workflow-patch.md "replace_all permission conditions"):
    # initial-planning (create-plan: pending, no re-entry signal) and
    # re-planning (create-plan: needs_update, OR create-plan: pending on a
    # SPEC-change re-entry -- workflow_replace_all_spec_change_reentry).
    # Rule 3, common to both: any in_progress/failed task is a protocol
    # error regardless of path.
    #
    # task0017 (review round 2 rework): the re-planning path carries two
    # further, path-dependent obligations that can only be checked here --
    # neither is knowable without the workflow.yaml this dry-run-apply
    # already has in hand:
    #
    # - Mandatory `preserve` per operation (workflow-patch.md's table row):
    #   `workflow.implement.base_commit` is mandatory on the re-planning
    #   path, not mandatory at all on the initial-planning path.
    # - Re-planning task-id allocation (workflow-patch.md "Re-planning
    #   task-id allocation"): ids already registered in `workflow.yaml`
    #   are carried via `tasks_patch.carried_task_ids` and are not
    #   re-declared under `tasks_patch.entries`; `entries` names only ids
    #   not yet registered; the two id sets are disjoint.
    if mode == "replace_all":
        tasks = workflow.get("tasks", {}) or {}
        create_plan_step = workflow_find_step(workflow, "create-plan")
        current_status = create_plan_step.get("status") if create_plan_step else None
        # Final-path correction (IMPLEMENTATION.md D2): path_corrections is
        # admitted on the correction entry (create-plan completed and
        # implement failed) and on the re-planning path, and rejected on
        # the initial-planning path and in every other state. On the
        # correction entry a `failed` task is permitted (an `in_progress`
        # one is not) and step_patches must be empty.
        implement_step = workflow_find_step(workflow, "implement")
        implement_status = implement_step.get("status") if implement_step else None
        has_corrections = path_state is not None
        correction_entry = path_state == PATH_STATE_CORRECTION_ENTRY
        if has_corrections:
            if path_state == PATH_STATE_OTHER:
                errors.append(
                    err(
                        "path-correction-not-permitted",
                        "tasks_patch.path_corrections is admitted only on the correction entry "
                        "(create-plan completed and implement failed) and on the re-planning path, "
                        f"not with create-plan {current_status!r} and implement {implement_status!r}",
                    )
                )
            if correction_entry and step_patches:
                errors.append(
                    err(
                        "path-correction-step-patches",
                        "a correction on the correction entry requires step_patches to be empty",
                    )
                )
        on_correction_entry = correction_entry or removal_entry
        blocked_task_statuses = ("in_progress",) if on_correction_entry else ("in_progress", "failed")
        if current_status not in ("pending", "needs_update") and not on_correction_entry:
            errors.append(err("replace-all-not-permitted", f"replace_all requires create-plan step to be pending or needs_update, got {current_status!r}"))
        else:
            if tasks and any((t or {}).get("status") in blocked_task_statuses for t in tasks.values()):
                if on_correction_entry:
                    errors.append(err("replace-all-not-permitted", "replace_all on the correction entry requires no task to be in_progress (implementation is in flight)"))
                else:
                    errors.append(err("replace-all-not-permitted", "replace_all requires no task to be in_progress or failed (implementation has started)"))
            else:
                is_replanning = (
                    on_correction_entry
                    or current_status == "needs_update"
                    or workflow_replace_all_spec_change_reentry(workflow, phase_state, feature_dir)
                )
                if not is_replanning and tasks and any((t or {}).get("status") != "pending" for t in tasks.values()):
                    errors.append(err("replace-all-not-permitted", "replace_all requires tasks to be empty or all pending (implementation has started)"))
                elif is_replanning:
                    preserve_strs = [p for p in (data.get("preserve") or []) if isinstance(p, str)]
                    if "workflow.implement.base_commit" not in preserve_strs:
                        errors.append(
                            err(
                                "preserve",
                                "replace_all on the re-planning path requires preserve to "
                                "include 'workflow.implement.base_commit'",
                            )
                        )
                    # Re-planning carry-over declaration
                    # (workflow-patch.md "Re-planning task-id allocation"):
                    # `entries` may name only ids not yet registered; every
                    # already-registered id must instead appear in
                    # `carried_task_ids`, whose record is copied from
                    # `workflow.yaml` verbatim (apply_patch's
                    # `replace_planning` arm) -- three independently
                    # reported rejections so a fixture proving one never
                    # rides along with the other two.
                    replanning_entries = (data.get("tasks_patch") or {}).get("entries") or {}
                    entry_ids = set(replanning_entries) if isinstance(replanning_entries, dict) else set()
                    carried_raw = (data.get("tasks_patch") or {}).get("carried_task_ids")
                    carried_ids = {c for c in carried_raw if isinstance(c, str)} if isinstance(carried_raw, list) else set()
                    existing_ids = set(tasks)

                    registered_in_entries = sorted(entry_ids & existing_ids)
                    if registered_in_entries:
                        errors.append(
                            err(
                                "replace-all-entry-for-registered-id",
                                "a re-planning replace_all's tasks_patch.entries must name "
                                f"only ids not yet registered; {registered_in_entries} are "
                                "already registered in workflow.yaml (carry them in "
                                "tasks_patch.carried_task_ids instead)",
                            )
                        )
                    dropped_ids = existing_ids - carried_ids
                    if dropped_ids:
                        errors.append(
                            err(
                                "replace-all-drops-task",
                                "a re-planning replace_all must carry every task id already "
                                "registered in workflow.yaml in tasks_patch.carried_task_ids; "
                                f"missing {sorted(dropped_ids)}",
                            )
                        )
                    unregistered_carried = sorted(carried_ids - existing_ids)
                    if unregistered_carried:
                        errors.append(
                            err(
                                "replace-all-carried-id-unregistered",
                                "tasks_patch.carried_task_ids names ids not registered in "
                                f"workflow.yaml: {unregistered_carried}",
                            )
                        )
                    max_existing_id = 0
                    for tid in existing_ids:
                        m = TASK_ID_RE.match(tid)
                        if m:
                            max_existing_id = max(max_existing_id, int(tid[len("task"):]))
                    for tid in sorted(entry_ids - existing_ids):
                        m = TASK_ID_RE.match(tid)
                        if m and int(tid[len("task"):]) <= max_existing_id:
                            errors.append(
                                err(
                                    "replace-all-task-id-reused",
                                    f"new task id {tid!r} must be allocated above the highest "
                                    f"registered id (task{max_existing_id:04d})",
                                )
                            )

    # Final-path correction conditions 1 to 5 (FR5), one error code each, in
    # that order. The inputs were checked above; every read of the journal,
    # the base commit and the documents happens here, without a shell.
    # Condition 5 reads the path state; the FR1 limits on tasks_patch.entries
    # and requirements_patch follow it, outside the numbered conditions, on
    # the correction entry only.
    if corrections:
        last_events = journal_last_events(journal)
        errors.extend(
            path_correction_precondition_errors(workflow, corrections, last_events, target_repo, base_commit)
        )
        errors.extend(_path_correction_new_path_errors(corrections, target_repo, base_commit))
        errors.extend(
            _path_correction_content_errors(
                workflow, corrections, feature_dir, target_repo, base_commit, path_state, last_events
            )
        )
        if path_state == PATH_STATE_CORRECTION_ENTRY:
            errors.extend(
                _correction_entry_limit_errors(workflow, corrections, data, feature_dir, target_repo, base_commit)
            )

    # Feature-docs correction (IMPLEMENTATION.md D7): the permission comes
    # first. Any state but the correction entry is rejected; on it the
    # precondition function (shared with scripts/feature-docs-entry.py) and
    # then the limits are judged. The in-memory application and the
    # `-incomplete` check follow below.
    if has_removals and not removal_entry:
        create_plan_now = workflow_find_step(workflow, "create-plan")
        implement_now = workflow_find_step(workflow, "implement")
        errors.append(
            err(
                "feature-docs-removal-not-permitted",
                "tasks_patch.feature_docs_removals is admitted only on the correction entry "
                "(create-plan completed and implement failed), "
                f"not with create-plan {(create_plan_now or {}).get('status')!r} and "
                f"implement {(implement_now or {}).get('status')!r}",
            )
        )
    elif removals:
        errors.extend(feature_docs_removal_precondition_errors(workflow, removals, journal_last_events(journal)))
        errors.extend(_feature_docs_removal_limit_errors(data))

    # Rule 4: append must not overwrite existing task IDs, and
    # expected_next_task_id must match the actual next id.
    if mode == "append":
        existing = workflow_task_ids(workflow)
        entries = (data.get("tasks_patch") or {}).get("entries") or {}
        for task_id in entries:
            if task_id in existing:
                errors.append(err("append-overwrite", f"append must not overwrite existing task_id {task_id}"))
        expected_next = (data.get("tasks_patch") or {}).get("expected_next_task_id")
        actual_next = next_task_id_after(workflow)
        if expected_next != actual_next:
            errors.append(err("expected-next-task-id-mismatch", f"expected_next_task_id {expected_next!r} does not match actual next id {actual_next!r}"))

    # Duplicate patch_id (5.6.1 idempotency).
    if phase_state is not None:
        patch_id = data.get("patch_id")
        for existing_patch in phase_state.get("patches", []) or []:
            if not isinstance(existing_patch, dict):
                continue
            if existing_patch.get("patch_id") == patch_id:
                same = (
                    existing_patch.get("base_input_digest") == data.get("base_input_digest")
                    and existing_patch.get("base_workflow_blob") == data.get("base_workflow_blob")
                )
                if not same:
                    errors.append(err("duplicate-patch-id", f"patch_id {patch_id!r} already exists in phase-state with different content"))

    # Post-application structural sanity + preserve invariance.
    try:
        new_workflow = apply_patch(workflow, data)
    except Exception as exc:  # noqa: BLE001 - surfaced as a validation error
        errors.append(err("apply-failed", f"could not apply patch in-memory: {exc}"))
        return errors

    for p in data.get("preserve") or []:
        if not isinstance(p, str):
            continue  # already reported by the structural preserve-list check above
        before = get_preserve_value(workflow, p)
        after = get_preserve_value(new_workflow, p)
        if before != after:
            errors.append(err("preserve-violated", f"preserve path {p!r} changed from {before!r} to {after!r}"))

    for task_id, task in (new_workflow.get("tasks") or {}).items():
        for field in ("files", "skills", "domains", "complexity", "requirements"):
            if field not in task:
                errors.append(err("post-apply-structure", f"applied workflow.yaml tasks.{task_id} is missing required field {field!r}"))

    # Feature-docs correction: `-incomplete` judges the in-memory result.
    permitted_removals = bool(removals) and removal_entry
    if permitted_removals:
        errors.extend(_feature_docs_removal_incomplete_errors(new_workflow))

    # FR3 on the carried tasks that are not merged, judged on their files
    # after corrections (same code and same exit 2 rule as for an entry).
    # A permitted feature-docs correction is outside it: the patch only
    # removes paths, so it introduces no report artifact name, and a name a
    # failed task still holds is the final-path judgment's to correct on the
    # next evaluation of Step A.6 (SPEC A4: neither judgment stops the other).
    if operation == "replace_planning" and not permitted_removals:
        errors.extend(_carried_report_name_errors(workflow, new_workflow, data, target_repo, base_commit))

    return errors


def _apply_tests_replace(tests, pairs):
    """rework-docs-only-task-routing/task0003 (FR4): the in-memory
    application of a requirement entry's `set.tests_replace`
    (workflow-patch.md, `requirements_patch` section). Pairs are applied in
    their listed order. Each `from` found in `tests` is replaced by its `to`
    at the same position; when `to` is already present, `from` is removed
    and `to` is not duplicated; a `from` that is absent leaves `tests`
    unchanged. Returns a new list. A malformed `tests` or pair is skipped,
    never raised on (the structural layer reports it)."""
    current = list(tests) if isinstance(tests, list) else []
    for pair in pairs if isinstance(pairs, list) else []:
        if not isinstance(pair, dict):
            continue
        old, new = pair.get("from"), pair.get("to")
        if not (isinstance(old, str) and isinstance(new, str)) or old == new or old not in current:
            continue
        if new in current:
            current = [t for t in current if t != old]
        else:
            position = current.index(old)
            current = current[:position] + [new] + [t for t in current[position + 1:] if t != old]
    return current


def apply_patch(workflow, patch):
    """A minimal, in-memory simulation of 5.5.5's application rules, used
    only to check post-application structure and preserve invariance under
    --dry-run-apply. This is NOT the orchestrator's real apply step."""
    new_wf = copy.deepcopy(workflow)
    operation = patch.get("operation")
    tasks_patch = patch.get("tasks_patch") or {}
    entries = tasks_patch.get("entries") or {}

    if operation == "replace_planning":
        # Re-planning carry-over declaration (workflow-patch.md
        # "Re-planning task-id allocation"): a carried id's record is
        # copied from the ORIGINAL workflow verbatim -- not re-derived from
        # any patch-supplied body, because the patch supplies none.
        carried_ids = tasks_patch.get("carried_task_ids")
        carried_ids = carried_ids if isinstance(carried_ids, list) else []
        existing_tasks = (workflow or {}).get("tasks", {}) or {}
        new_tasks = {}
        for task_id in carried_ids:
            if isinstance(task_id, str) and isinstance(existing_tasks.get(task_id), dict):
                new_tasks[task_id] = copy.deepcopy(existing_tasks[task_id])
        # The one exception to the verbatim copy: a final-path correction
        # (workflow-patch.md "Final-path correction") replaces old_path by
        # new_path in place and clears `notes`; every other field stays.
        _apply_path_corrections(new_tasks, _well_formed_path_corrections(patch))
        # Likewise a feature-docs correction (workflow-patch.md "Feature-docs
        # correction") removes the named paths from `files` and clears
        # `notes`; applied after the verbatim copy, as path corrections are.
        _apply_feature_docs_removals(new_tasks, _well_formed_feature_docs_removals(patch))
        for task_id, entry in entries.items():
            new_entry = dict(entry)
            new_entry["status"] = new_entry.pop("initial_status", "pending")
            new_entry.setdefault("notes", None)
            new_entry.setdefault("branch", None)
            new_tasks[task_id] = new_entry
        new_wf["tasks"] = new_tasks
    elif operation == "append_rework":
        tasks = new_wf.setdefault("tasks", {})
        for task_id, entry in entries.items():
            new_entry = dict(entry)
            new_entry["status"] = new_entry.pop("initial_status", "pending")
            new_entry.setdefault("notes", None)
            new_entry.setdefault("branch", None)
            tasks[task_id] = new_entry

    requirements_patch = patch.get("requirements_patch") or {}
    requirements = new_wf.setdefault("requirements", {})
    for fr_id, rpatch in (requirements_patch.get("entries") or {}).items():
        req = requirements.setdefault(fr_id, {})
        set_block = rpatch.get("set") or {}
        # tests_replace is applied before tests_append within one entry
        # (workflow-patch.md, `requirements_patch` section), whatever the
        # order of the keys in the entry.
        if "tests_replace" in set_block:
            req["tests"] = _apply_tests_replace(req.get("tests"), set_block["tests_replace"])
        for key, value in set_block.items():
            if key == "tests_replace":
                continue
            if key == "tasks_append":
                req["tasks"] = list(req.get("tasks") or []) + list(value)
            elif key == "tests_append":
                req["tests"] = list(req.get("tests") or []) + list(value)
            else:
                req[key] = value

    for sp in patch.get("step_patches") or []:
        step = None
        for s in new_wf.get("workflow", []):
            if isinstance(s, dict) and s.get("id") == sp.get("step_id"):
                step = s
                break
        if step is not None:
            set_block = sp.get("set") or {}
            if "status" in set_block:
                step["status"] = set_block["status"]

    return new_wf


# ---------------------------------------------------------------------------
# Other-feature documents (plan-feature-docs-route/task0005; FR3 to FR7)
#
# The implementation-planner may amend an existing document of ANOTHER
# feature during create-plan, in two stages (IMPLEMENTATION.md D3): stage 1
# returns a request result and writes nothing; the orchestrator grants one
# `amend_other_feature` write_policy target per requested path; stage 2 amends
# the granted documents and declares each amendment in
# `payload.other_feature_doc_fixes`. This section is the mechanical side of
# that route. The rule text is owned by planner-contract.md
# (`## Other-feature documents`) and spec-writer-contract.md (the action
# table); this section only implements it.
#
# Every check reports a malformed value as an error of its own code and skips
# the rest of its check for that value; none raises (NFR2).
# ---------------------------------------------------------------------------

OTHER_FEATURE_DOC_SCOPE_CODE = "other-feature-doc-scope"
OTHER_FEATURE_DOC_REQUEST_CODE = "other-feature-doc-request"
OTHER_FEATURE_DOC_FIX_CODE = "other-feature-doc-fix"

OTHER_FEATURE_DOC_REQUESTS_KEY = "other_feature_doc_requests"
OTHER_FEATURE_DOC_FIXES_KEY = "other_feature_doc_fixes"

OTHER_FEATURE_DOC_REQUEST_FIELDS = ("path", "reason")
OTHER_FEATURE_DOC_FIX_FIELDS = ("path", "change", "reason")
OTHER_FEATURE_DOC_RECORD_FIELDS = ("path", "change", "reason", "produced_by")

# The create-plan worker that may hold the action, and the phase it holds it in.
AMEND_OTHER_FEATURE_WORKER = "implementation-planner"
AMEND_OTHER_FEATURE_PHASE = "create-plan"


def other_feature_doc_in_scope(path, own_feature):
    """D4: whether `path` may be requested, granted and amended as a document
    of another feature than `own_feature`. All of these hold:

    1. `path` is a string that passes `is_safe_relative_path`;
    2. its normalized segments (`path_segments`) number at least three, the
       first is exactly `feature-docs` and the second is not `own_feature`;
    3. its last segment ends with `.md` (case-sensitive);
    4. it is not inside `feature-docs/{x}/phase-state/`,
       `feature-docs/{x}/tasks/` or `feature-docs/{x}/design/mockups/`,
       compared by segments.

    Existence as a regular file is the orchestrator's check at grant time;
    nothing here reads the file system. `own_feature` that is not a non-empty
    string is judged as no feature: only the other conditions apply. Never
    raises."""
    if not is_safe_relative_path(path):
        return False
    segments = path_segments(path)
    if len(segments) < 3 or segments[0] != "feature-docs":
        return False
    if isinstance(own_feature, str) and own_feature and segments[1] == own_feature:
        return False
    if not segments[-1].endswith(".md"):
        return False
    inside = segments[2:]
    if inside[0] in ("phase-state", "tasks") and len(inside) > 1:
        return False
    if inside[:2] == ["design", "mockups"] and len(inside) > 2:
        return False
    return True


def _dispatch_feature(envelope, workflow):
    """The own feature of the dispatch: the envelope's `feature`, else the
    workflow's. None when neither is a non-empty string."""
    for source in (envelope, workflow):
        if isinstance(source, dict):
            feature = source.get("feature")
            if isinstance(feature, str) and feature:
                return feature
    return None


def _is_non_empty_string(value):
    return isinstance(value, str) and bool(value.strip())


def _path_identity(path):
    """Key under which two spellings of one path collide: the normalized
    segments of a safe relative path, the string itself otherwise."""
    if is_safe_relative_path(path):
        return tuple(path_segments(path))
    return path


def _write_policy_targets(envelope):
    """The mapping items of the input envelope's `write_policy.targets`, and
    the structural errors of everything else there (code `write_policy`).
    A missing `write_policy` or `targets` is an empty list. Never raises."""
    if not isinstance(envelope, dict):
        return [], []
    write_policy = envelope.get("write_policy") or {}
    if not isinstance(write_policy, dict):
        return [], [err("write_policy", "input envelope write_policy must be a mapping")]
    raw = write_policy.get("targets", [])
    if not isinstance(raw, list):
        return [], [err("write_policy", "input envelope write_policy.targets must be a list")]
    targets = []
    errors = []
    for i, target in enumerate(raw):
        if not isinstance(target, dict):
            errors.append(err("write_policy", f"input envelope write_policy.targets[{i}] must be a mapping"))
            continue
        path = target.get("path")
        if not isinstance(path, str) and target.get("action") != AMEND_OTHER_FEATURE_ACTION:
            # an amend_other_feature target with such a path is the scope
            # rule's error (_amend_other_feature_target_errors), not this one
            errors.append(err("write_policy", f"input envelope write_policy.targets[{i}].path must be a string"))
            continue
        targets.append(target)
    return targets, errors


def _amend_other_feature_target_errors(targets, worker, envelope, own_feature):
    """D2 / D3: an `amend_other_feature` target is valid only on an
    implementation-planner create-plan dispatch, with a non-null
    `expect_digest` and an in-scope path. Each breach is one
    `other-feature-doc-scope` error naming the path."""
    errors = []
    phase = envelope.get("phase") if isinstance(envelope, dict) else None
    for target in targets:
        if target.get("action") != AMEND_OTHER_FEATURE_ACTION:
            continue
        path = target.get("path")
        if worker != AMEND_OTHER_FEATURE_WORKER or phase != AMEND_OTHER_FEATURE_PHASE:
            errors.append(err(
                OTHER_FEATURE_DOC_SCOPE_CODE,
                f"write_policy target {path!r} has action {AMEND_OTHER_FEATURE_ACTION!r}, which is valid only on an "
                f"{AMEND_OTHER_FEATURE_WORKER} {AMEND_OTHER_FEATURE_PHASE} dispatch",
            ))
        if not _is_non_empty_string(target.get("expect_digest")):
            errors.append(err(
                OTHER_FEATURE_DOC_SCOPE_CODE,
                f"write_policy target {path!r} has action {AMEND_OTHER_FEATURE_ACTION!r} and requires a non-null expect_digest",
            ))
        if not other_feature_doc_in_scope(path, own_feature):
            errors.append(err(
                OTHER_FEATURE_DOC_SCOPE_CODE,
                f"write_policy target {path!r} has action {AMEND_OTHER_FEATURE_ACTION!r} but is not a document that "
                "may be amended in another feature (out of scope)",
            ))
    return errors


def _is_other_feature_request_result(worker, status, payload):
    """Whether a result takes the stage-1 request shape's place: a completed
    implementation-planner result whose payload carries the requests key."""
    return (
        worker == AMEND_OTHER_FEATURE_WORKER
        and status == "completed"
        and isinstance(payload, dict)
        and OTHER_FEATURE_DOC_REQUESTS_KEY in payload
    )


def _other_feature_request_errors(payload, written_artifacts_raw, workflow_patch, has_grants, own_feature):
    """D3 stage 1: the shape of the request result and its admission.

    Shape and admission errors are `other-feature-doc-request`; a requested
    path out of scope is `other-feature-doc-scope`. The result is admitted
    only on a dispatch with no `amend_other_feature` target (`has_grants`)."""
    errors = []

    def request_error(message):
        errors.append(err(OTHER_FEATURE_DOC_REQUEST_CODE, message))

    if has_grants:
        request_error(
            f"a request result is admitted only on a dispatch without {AMEND_OTHER_FEATURE_ACTION!r} targets; "
            "this dispatch already carries grants"
        )
    for key in sorted((k for k in payload if k != OTHER_FEATURE_DOC_REQUESTS_KEY), key=str):
        request_error(f"a request result payload holds only {OTHER_FEATURE_DOC_REQUESTS_KEY!r}; it also carries {key!r}")
    if written_artifacts_raw:
        request_error("a request result writes nothing; written_artifacts must be empty")
    if workflow_patch is not None:
        request_error("a request result carries no patch; workflow_patch must be null")

    requests = payload[OTHER_FEATURE_DOC_REQUESTS_KEY]
    if not isinstance(requests, list):
        request_error(f"{OTHER_FEATURE_DOC_REQUESTS_KEY} must be a list")
        return errors
    if not requests:
        request_error(f"{OTHER_FEATURE_DOC_REQUESTS_KEY} must not be empty")
        return errors
    seen = set()
    for i, item in enumerate(requests):
        label = f"{OTHER_FEATURE_DOC_REQUESTS_KEY}[{i}]"
        if not isinstance(item, dict):
            request_error(f"{label} must be a mapping with exactly 'path' and 'reason'")
            continue
        missing = [f for f in OTHER_FEATURE_DOC_REQUEST_FIELDS if f not in item]
        unknown = sorted((k for k in item if k not in OTHER_FEATURE_DOC_REQUEST_FIELDS), key=str)
        if missing or unknown:
            request_error(f"{label} must hold exactly 'path' and 'reason' (missing {missing}, unknown {unknown})")
        for field in OTHER_FEATURE_DOC_REQUEST_FIELDS:
            if field in item and not _is_non_empty_string(item[field]):
                request_error(f"{label}.{field} must be a non-empty string")
        path = item.get("path")
        if not _is_non_empty_string(path):
            continue
        identity = _path_identity(path)
        if identity in seen:
            request_error(f"{label}.path {path!r} repeats an earlier request")
        seen.add(identity)
        if not other_feature_doc_in_scope(path, own_feature):
            errors.append(err(
                OTHER_FEATURE_DOC_SCOPE_CODE,
                f"{label}.path {path!r} is not a document that may be amended in another feature (out of scope)",
            ))
    return errors


def _other_feature_fix_errors(payload, amend_paths, written_paths, own_feature):
    """D3 stage 2: `payload.other_feature_doc_fixes` against the written
    grants. `amend_paths` is the set of `amend_other_feature` target paths of
    the dispatch; `written_paths` the usable `written_artifacts` paths.

    The set of declared paths must equal the set of target paths that are
    written. Each item holds exactly non-empty `path`, `change` and `reason`;
    a fix on a dispatch without grants, a fix for a path that is not a target,
    a written target without a fix, a declared target that is not written and
    a repeated path are each `other-feature-doc-fix`. A declared path out of
    scope is also `other-feature-doc-scope`."""
    errors = []

    def fix_error(message):
        errors.append(err(OTHER_FEATURE_DOC_FIX_CODE, message))

    written_grants = {p for p in written_paths if p in amend_paths}
    declared = set()
    if OTHER_FEATURE_DOC_FIXES_KEY in payload:
        fixes = payload[OTHER_FEATURE_DOC_FIXES_KEY]
        if not isinstance(fixes, list):
            fix_error(f"{OTHER_FEATURE_DOC_FIXES_KEY} must be a list")
            return errors
        seen = set()
        for i, item in enumerate(fixes):
            label = f"{OTHER_FEATURE_DOC_FIXES_KEY}[{i}]"
            if not isinstance(item, dict):
                fix_error(f"{label} must be a mapping with exactly 'path', 'change' and 'reason'")
                continue
            missing = [f for f in OTHER_FEATURE_DOC_FIX_FIELDS if f not in item]
            unknown = sorted((k for k in item if k not in OTHER_FEATURE_DOC_FIX_FIELDS), key=str)
            if missing or unknown:
                fix_error(f"{label} must hold exactly 'path', 'change' and 'reason' (missing {missing}, unknown {unknown})")
            for field in OTHER_FEATURE_DOC_FIX_FIELDS:
                if field in item and not _is_non_empty_string(item[field]):
                    fix_error(f"{label}.{field} must be a non-empty string")
            path = item.get("path")
            if not _is_non_empty_string(path):
                continue
            identity = _path_identity(path)
            if identity in seen:
                fix_error(f"{label}.path {path!r} repeats an earlier fix")
            seen.add(identity)
            declared.add(path)
            if not other_feature_doc_in_scope(path, own_feature):
                errors.append(err(
                    OTHER_FEATURE_DOC_SCOPE_CODE,
                    f"{label}.path {path!r} is not a document that may be amended in another feature (out of scope)",
                ))
            if path not in amend_paths:
                if amend_paths:
                    fix_error(f"{label}.path {path!r} is not an {AMEND_OTHER_FEATURE_ACTION!r} target of this dispatch")
                else:
                    fix_error(
                        f"{label}.path {path!r} is declared on a dispatch without {AMEND_OTHER_FEATURE_ACTION!r} targets"
                    )
    for path in sorted(written_grants - declared):
        fix_error(f"granted document {path!r} is in written_artifacts but has no entry in {OTHER_FEATURE_DOC_FIXES_KEY}")
    for path in sorted((declared & amend_paths) - written_grants):
        fix_error(f"{OTHER_FEATURE_DOC_FIXES_KEY} declares {path!r}, which is not in written_artifacts")
    return errors


def other_feature_doc_fix_record_errors(value):
    """D5: the shape of a create-plan phase-state's `other_feature_doc_fixes`
    list. A list of mappings, each with non-empty string `path`, `change`,
    `reason` and `produced_by`, every `path` passing the safe-relative check.
    Each breach is `other-feature-doc-fix`. Never raises."""
    if not isinstance(value, list):
        return [err(OTHER_FEATURE_DOC_FIX_CODE, f"{OTHER_FEATURE_DOC_FIXES_KEY} must be a list")]
    errors = []
    for i, item in enumerate(value):
        label = f"{OTHER_FEATURE_DOC_FIXES_KEY}[{i}]"
        if not isinstance(item, dict):
            errors.append(err(OTHER_FEATURE_DOC_FIX_CODE, f"{label} must be a mapping"))
            continue
        for field in OTHER_FEATURE_DOC_RECORD_FIELDS:
            if not _is_non_empty_string(item.get(field)):
                errors.append(err(OTHER_FEATURE_DOC_FIX_CODE, f"{label}.{field} must be a non-empty string"))
        path = item.get("path")
        if _is_non_empty_string(path) and not is_safe_relative_path(path):
            errors.append(err(
                OTHER_FEATURE_DOC_FIX_CODE,
                f"{label}.path {path!r} must be a relative path without '..' segments or NUL bytes",
            ))
    return errors


# ---------------------------------------------------------------------------
# --kind phase-state (5.6)
# ---------------------------------------------------------------------------

def validate_phase_state(data):
    if not isinstance(data, dict):
        return [err("structure", "phase-state must be a mapping")]
    errors = []
    if data.get("schema_version") != 1:
        errors.append(err("schema_version", "schema_version must be 1 (unknown schema_version is a plugin-version mismatch)"))
    if not data.get("feature"):
        errors.append(err("feature", "feature is required"))
    if data.get("phase") not in PHASE_VALUES:
        errors.append(err("phase", f"phase must be one of {sorted(PHASE_VALUES)}"))
    if data.get("status") not in PHASE_STATE_STATUS_VALUES:
        errors.append(err("status", f"status must be one of {sorted(PHASE_STATE_STATUS_VALUES)}"))
    if not isinstance(data.get("generation"), int):
        errors.append(err("generation", "generation must be an integer"))

    worker_runs = data.get("worker_runs") or []
    if not isinstance(worker_runs, list):
        errors.append(err("worker_runs", "worker_runs must be a list"))
        worker_runs = []
    seen_request_ids = {}
    for i, run in enumerate(worker_runs):
        if not isinstance(run, dict):
            errors.append(err("worker_runs", f"worker_runs[{i}] must be a mapping"))
            continue
        rid = run.get("request_id")
        if not rid:
            errors.append(err("worker_runs", f"worker_runs[{i}].request_id is required"))
        if run.get("status") not in WORKER_RUN_STATUS_VALUES:
            errors.append(err("worker_runs", f"worker_runs[{i}].status must be one of {sorted(WORKER_RUN_STATUS_VALUES)}"))
        if rid in seen_request_ids:
            errors.append(err("worker_runs", f"duplicate request_id {rid!r} in worker_runs"))
        seen_request_ids[rid] = run

    patches = data.get("patches") or []
    if not isinstance(patches, list):
        errors.append(err("patches", "patches must be a list"))
        patches = []
    for i, p in enumerate(patches):
        if not isinstance(p, dict):
            errors.append(err("patches", f"patches[{i}] must be a mapping"))
            continue
        pid = p.get("patch_id")
        if not isinstance(pid, str) or not PATCH_ID_RE.match(pid):
            errors.append(err("patches", f"patches[{i}].patch_id must match {PATCH_ID_RE.pattern}"))
        if p.get("status") not in PATCH_STATUS_VALUES:
            errors.append(err("patches", f"patches[{i}].status must be one of {sorted(PATCH_STATUS_VALUES)}"))

    packets = data.get("packets") or {}
    if not isinstance(packets, dict):
        errors.append(err("packets", "packets must be a mapping"))
        packets = {}
    for packet_id, packet in packets.items():
        if not isinstance(packet_id, str) or not PACKET_ID_RE.match(packet_id):
            errors.append(err("packets", f"packets key {packet_id!r} must match {PACKET_ID_RE.pattern}"))
        if not isinstance(packet, dict):
            errors.append(err("packets", f"packets[{packet_id}] must be a mapping"))
            continue
        if packet.get("status") not in PACKET_STATUS_VALUES:
            errors.append(err("packets", f"packets[{packet_id}].status must be one of {sorted(PACKET_STATUS_VALUES)}"))

    answers = data.get("answers") or {}
    if not isinstance(answers, dict):
        errors.append(err("answers", "answers must be a mapping"))
        answers = {}
    for question_id, answer in answers.items():
        if not isinstance(answer, dict):
            errors.append(err("answers", f"answers[{question_id}] must be a mapping"))
            continue
        errors.extend(prefix_errors(validate_answer(answer), f"answers[{question_id}]"))

    resolved_cache = data.get("resolved_input_cache")
    if resolved_cache is not None:
        if not isinstance(resolved_cache, dict):
            errors.append(err("resolved_input_cache", "resolved_input_cache must be a mapping"))
            resolved_cache = {}
        generation = data.get("generation")
        for category, cache in resolved_cache.items():
            if not isinstance(cache, dict):
                errors.append(err("resolved_input_cache", f"resolved_input_cache[{category}] must be a mapping"))
                continue
            for field in ("generation_digest", "resolved_at_generation", "paths", "digests", "truncated"):
                if field not in cache:
                    errors.append(err("resolved_input_cache", f"resolved_input_cache[{category}] is missing {field!r}"))
            if isinstance(generation, int) and isinstance(cache.get("resolved_at_generation"), int):
                if cache["resolved_at_generation"] > generation:
                    errors.append(err("resolved_input_cache", f"resolved_input_cache[{category}].resolved_at_generation exceeds current generation"))

    stale_count = data.get("stale_redispatch_count", 0)
    if not isinstance(stale_count, int) or stale_count < 0:
        errors.append(err("stale_redispatch_count", "stale_redispatch_count must be a non-negative integer"))

    # goal-vs-spec-divergence/task0029: `classification` is an append-type
    # list (references/phase-state.md) -- one entry per gate pass, never
    # rewritten or removed. A mapping here (what a wholesale-replace would
    # leave behind, the pre-task0029 shape) is a structural violation, not
    # a degraded-but-valid document.
    classification = data.get("classification")
    if classification is not None:
        if not isinstance(classification, list):
            errors.append(err(
                "classification",
                "classification must be a list -- one entry appended per "
                "gate pass, never replaced wholesale (references/"
                "phase-state.md)",
            ))
        else:
            for i, entry in enumerate(classification):
                if not isinstance(entry, dict):
                    errors.append(err("classification", f"classification[{i}] must be a mapping"))
                    continue
                if entry.get("classifier") not in CLASSIFIER_VALUES:
                    errors.append(err("classification", f"classification[{i}].classifier must be one of {sorted(CLASSIFIER_VALUES)}"))
                if entry.get("verdict") not in CLASSIFICATION_VERDICT_VALUES:
                    errors.append(err("classification", f"classification[{i}].verdict must be one of {sorted(CLASSIFICATION_VERDICT_VALUES)}"))
                if entry.get("decision") not in CLASSIFICATION_DECISION_VALUES:
                    errors.append(err("classification", f"classification[{i}].decision must be one of {sorted(CLASSIFICATION_DECISION_VALUES)}"))
                if entry.get("verdict") == "spec_gap" and not entry.get("evidence_ids"):
                    errors.append(err("classification", f"classification[{i}].evidence_ids is required (non-empty) when verdict is spec_gap"))
                if entry.get("decision") == "stop" and not entry.get("reason"):
                    errors.append(err("classification", f"classification[{i}].reason is required when decision is stop"))

    # plan-feature-docs-route/task0005 (FR7, D5): a create-plan phase-state
    # may carry the append-only `other_feature_doc_fixes` list. Its absence is
    # valid, and so is any other top-level key (unknown keys stay tolerated).
    if data.get("phase") == "create-plan" and OTHER_FEATURE_DOC_FIXES_KEY in data:
        errors.extend(other_feature_doc_fix_record_errors(data[OTHER_FEATURE_DOC_FIXES_KEY]))

    return errors


# ---------------------------------------------------------------------------
# --kind worker-result (5.3, 5.4)
# ---------------------------------------------------------------------------

def _normalize_written_artifacts(raw):
    """Type-checks `written_artifacts` and each entry's `path` (as6): a
    written_artifacts value that is not a list is a validation error rather
    than being silently iterated per-character (a bare string passed as the
    whole value), and an entry that is not a mapping/string, or a mapping
    missing a usable string `path`, is a validation error rather than a
    traceback (the previous code called `.startswith` on a `None` path).
    Returns (list[str] of usable paths, list[error])."""
    if raw is None:
        return [], []
    if not isinstance(raw, list):
        return [], [err("written_artifacts", "written_artifacts must be a list")]
    errors = []
    paths = []
    for i, artifact in enumerate(raw):
        if isinstance(artifact, dict):
            path = artifact.get("path")
        elif isinstance(artifact, str):
            path = artifact
        else:
            errors.append(err("written_artifacts", f"written_artifacts[{i}] must be a mapping with a 'path' key"))
            continue
        if not isinstance(path, str) or not path:
            errors.append(err("written_artifacts", f"written_artifacts[{i}] is missing a usable 'path'"))
            continue
        paths.append(path)
    return paths, errors


def validate_worker_result(
    data,
    worker,
    *,
    envelope=None,
    packet=None,
    answers=None,
    workflow=None,
    registries=None,
    phase_state=None,
    digest_source=None,
    feature_dir=None,
    baseline_dir=None,
    dry_run=False,
    gate_registry=None,
    target_repo=None,
    base_commit=None,
    journal=None,
):
    if not isinstance(data, dict):
        return [err("structure", "worker result must be a mapping")]
    errors = []

    if data.get("schema_version") != 1:
        errors.append(err("schema_version", "schema_version must be 1"))
    if data.get("worker") != worker:
        errors.append(err("worker", f"--worker {worker!r} does not match input worker field {data.get('worker')!r}"))
    if not data.get("request_id"):
        errors.append(err("request_id", "request_id is required"))

    status = data.get("status")
    if status not in STATUS_VALUES:
        errors.append(err("status", f"status must be one of {sorted(STATUS_VALUES)}"))
        return errors

    input_revision = data.get("input_revision") or {}
    if "input_digest" not in input_revision:
        errors.append(err("input_revision", "input_revision.input_digest is required"))

    question_packet = data.get("question_packet")
    blocking_reason = data.get("blocking_reason")
    written_artifacts_raw = data.get("written_artifacts")
    written_artifacts, written_artifacts_errors = _normalize_written_artifacts(written_artifacts_raw)
    errors.extend(written_artifacts_errors)
    workflow_patch = data.get("workflow_patch")
    mode_echo = data.get("mode_echo")
    payload = data.get("payload") or {}
    if status == "completed" and not isinstance(payload, dict):
        # every check below reads the payload as a mapping
        errors.append(err("payload", "payload must be a mapping"))
        payload = {}
    # plan-feature-docs-route/task0005 (D3): the stage-1 request result takes
    # the place of the planner's ordinary result shape (workflow_patch and
    # payload.task_index); its own checks are made below.
    is_request_result = _is_other_feature_request_result(worker, status, payload)

    # --- status exclusivity (5.3) ---
    if status == "needs_user_input":
        if not question_packet:
            errors.append(err("exclusivity", "needs_user_input requires question_packet"))
        else:
            errors.extend(
                prefix_errors(
                    validate_question_packet(question_packet, gate_registry=gate_registry), "question_packet"
                )
            )
        if written_artifacts_raw:
            errors.append(err("exclusivity", "needs_user_input forbids written_artifacts"))
        if workflow_patch:
            errors.append(err("exclusivity", "needs_user_input forbids workflow_patch"))
        if blocking_reason:
            errors.append(err("exclusivity", "needs_user_input forbids blocking_reason"))
    else:
        if question_packet:
            errors.append(err("exclusivity", f"status {status!r} forbids question_packet"))

    # as21 / worker-envelope.md: `completed` is the only status that
    # REQUIRES a payload. bs1 (round 2): the envelope's status table forbids
    # `artifacts`, a `patch` and `blocking_reason` on `needs_user_input` --
    # it does NOT forbid `payload`, and the analyst contract requires
    # `needs_user_input` to carry `payload.analysis_snapshot` (its interim
    # findings survive into the next clarification round). So
    # `needs_user_input` is exempt from the forbids-payload rule below; the
    # other four non-completed statuses (`blocked`, `invalid_input`,
    # `stale_input`, `failed`) still forbid a non-empty payload.
    if status == "completed":
        if not payload:
            errors.append(err("payload", "completed requires a non-empty payload"))
    elif status != "needs_user_input" and payload:
        errors.append(err("payload", f"status {status!r} forbids a non-empty payload"))
    if status in ("blocked", "invalid_input", "failed"):
        if not blocking_reason:
            errors.append(err("blocking_reason", f"status {status!r} requires blocking_reason"))

    # --- mode_echo (5.3, 5.4.1) ---
    mode_key = None
    if worker == "requirements-analyst":
        input_mode = (envelope or {}).get("analysis_mode")
        if mode_echo not in ("full", "design_system_detection"):
            errors.append(err("mode_echo", "mode_echo is missing or not one of 'full'/'design_system_detection'"))
        elif input_mode is not None and mode_echo != input_mode:
            errors.append(err("mode_echo", f"mode_echo {mode_echo!r} does not match input envelope analysis_mode {input_mode!r}"))
            mode_key = mode_echo
        else:
            mode_key = mode_echo
    else:
        if mode_echo is not None:
            errors.append(err("mode_echo", f"{worker} must return mode_echo: null"))
        mode_key = "_default"

    if mode_key is not None:
        caps = WORKER_CAPABILITIES[worker][mode_key]
        if status not in caps["allowed_statuses"]:
            errors.append(err("status-not-allowed", f"{worker} ({mode_key}) cannot return status {status!r}"))
        if not caps["has_workflow_patch"] and workflow_patch:
            errors.append(err("workflow_patch", f"{worker} must not return workflow_patch"))
        if caps["has_workflow_patch"] and status == "completed" and not workflow_patch and not is_request_result:
            errors.append(err("workflow_patch", f"{worker} completed result must include workflow_patch"))
        if status == "completed":
            missing = caps["required_payload"] - set(payload.keys())
            if missing and not is_request_result:
                errors.append(err("payload-missing", f"payload is missing required keys: {sorted(missing)}"))
            forbidden_present = caps["forbidden_payload"] & set(payload.keys())
            if forbidden_present:
                errors.append(err("payload-forbidden", f"payload contains keys forbidden for this mode: {sorted(forbidden_present)}"))

    # --- input_revision copy-check + write_policy consistency (5.3) ---
    # plan-feature-docs-route/task0005: the targets are read once, with their
    # structural errors, because the other-feature document checks below need
    # them too (an absent envelope has no grants).
    policy_targets, policy_errors = _write_policy_targets(envelope)
    own_feature = _dispatch_feature(envelope, workflow)
    if envelope is not None:
        envelope_digest = (envelope.get("input_revision") or {}).get("input_digest")
        if envelope_digest is not None and input_revision.get("input_digest") != envelope_digest:
            errors.append(err("input_revision", "input_revision.input_digest was not copied verbatim from the input envelope"))
        errors.extend(policy_errors)
        targets_by_path = {t.get("path"): t for t in policy_targets if isinstance(t.get("path"), str)}
        for path, target in targets_by_path.items():
            action = target.get("action")
            if not (isinstance(action, str) and action in WRITE_POLICY_ACTIONS):
                errors.append(err("write_policy", f"input envelope write_policy.targets[{path!r}].action is not one of {sorted(WRITE_POLICY_ACTIONS)}"))
        errors.extend(_amend_other_feature_target_errors(policy_targets, worker, envelope, own_feature))
        allowed_roots = envelope.get("allowed_write_roots") or []
        for path in written_artifacts:
            if path in targets_by_path:
                continue
            if any(path_is_contained_in_root(path, root) for root in allowed_roots):
                continue
            errors.append(err("write_policy", f"written_artifacts path {path!r} is covered by neither write_policy.targets nor allowed_write_roots"))
        # regenerate co-occurrence (5.4.2)
        artifact_paths = set(written_artifacts)
        for target in policy_targets:
            if target.get("action") == "regenerate" and target.get("path") in artifact_paths:
                source = target.get("source")
                if not isinstance(source, str) or source not in artifact_paths:
                    errors.append(err("regenerate", f"written_artifacts includes regenerate target {target.get('path')!r} without its source {source!r}"))

    # --- other-feature documents (plan-feature-docs-route/task0005) ---
    # Stage 1 (D3): the request result's shape and admission. Stage 2: the
    # declared fixes against the written grants. Both read the dispatch's
    # `amend_other_feature` targets; an absent envelope has none.
    amend_targets = [t for t in policy_targets if t.get("action") == AMEND_OTHER_FEATURE_ACTION]
    amend_paths = {t["path"] for t in amend_targets if isinstance(t.get("path"), str)}
    if is_request_result:
        errors.extend(
            _other_feature_request_errors(
                payload, written_artifacts_raw, workflow_patch, bool(amend_targets), own_feature
            )
        )
    if status == "completed":
        errors.extend(_other_feature_fix_errors(payload, amend_paths, written_artifacts, own_feature))

    # --- tokens.yaml / tokens.html co-occurrence (5.4.5), unconditional ---
    artifact_paths = set(written_artifacts)
    has_yaml = any(p and p.endswith("design-system/tokens.yaml") for p in artifact_paths)
    has_html = any(p and p.endswith("design-system/tokens.html") for p in artifact_paths)
    if has_yaml != has_html:
        errors.append(err("tokens-cooccurrence", "written_artifacts must include both design-system/tokens.yaml and design-system/tokens.html, or neither"))

    # --- workflow_patch structural + cross-artifact validation ---
    if workflow_patch:
        errors.extend(
            prefix_errors(
                validate_workflow_patch(
                    workflow_patch,
                    workflow=workflow,
                    registries=registries,
                    digest_source=digest_source,
                    phase_state=phase_state,
                    dry_run=dry_run,
                    feature_dir=feature_dir,
                    envelope=envelope,
                    target_repo=target_repo,
                    base_commit=base_commit,
                    journal=journal,
                ),
                "workflow_patch",
            )
        )
        if feature_dir is not None:
            errors.extend(_validate_task_plans_against_patch(workflow_patch, feature_dir, workflow=workflow))

    # --- scenario-ID form (scenario-id-ts-hyphen/task0001, FR3) ---
    # Only a completed implementation-planner result with a feature directory
    # is checked (IMPLEMENTATION.md D1); rework-planner output and every other
    # status or worker are left alone.
    # A stage-1 request result (plan-feature-docs-route/task0005) writes no
    # document and carries no patch, so there is nothing of its own to scan.
    if (
        worker == "implementation-planner"
        and status == "completed"
        and feature_dir is not None
        and not is_request_result
    ):
        errors.extend(_validate_scenario_id_form(workflow_patch, feature_dir, workflow))

    # --- rework_index coverage (5.4.4) ---
    if worker == "rework-planner" and status == "completed":
        errors.extend(
            _validate_rework_index(
                payload.get("rework_index") or {},
                workflow_patch,
                envelope,
                feature_dir,
                baseline_dir,
                payload=payload,
            )
        )

    return errors


# as16: task-plan reads exceeding this size are rejected before the content
# is loaded into memory. Task plans are short prose documents (the template
# is a handful of KB); this bound is generous headroom, not a tight fit.
MAX_PLAN_READ_BYTES = 1_000_000


def _resolve_contained_relative_path(base_dir, rel_path):
    """Resolves an untrusted, patch-supplied relative path under `base_dir`
    (as16: the `plan` field arrives in the workflow patch, which is worker
    output). Rejects absolute paths and `..` segments lexically, rejects a
    symlink at ANY path segment -- including the final component -- BEFORE
    the target is ever opened (`is_file`/`read_text` themselves follow
    symlinks), and independently re-checks that the resolved real path
    still sits inside `base_dir`'s resolved real path as defense in depth
    beyond the lexical check. Returns (Path, None) on success, or
    (None, message) on rejection."""
    if not is_safe_relative_path(rel_path):
        return None, f"{rel_path!r} is not a safe project-relative path (must be relative, no '..')"
    segments = path_segments(rel_path)
    if not segments:
        return None, f"{rel_path!r} does not name a file"
    current = base_dir
    for segment in segments:
        current = current / segment
        if current.is_symlink():
            return None, f"path segment {current} is a symlink"
    try:
        base_real = base_dir.resolve(strict=False)
        target_real = current.resolve(strict=False)
    except OSError as exc:
        return None, f"cannot resolve path {current}: {exc}"
    try:
        target_real.relative_to(base_real)
    except ValueError:
        return None, f"resolved path {target_real} escapes {base_real}"
    return current, None


# task-tier-reduction/task0010 (AC-4): the task document's file name
# (`references/templates/task-document.md`), matched by itself -- never a
# tier value, which this call site has no channel to receive.
TASK_DOCUMENT_FILE_NAME = "TASK.md"


def _task_entry_plan_is_task_document(plan_rel):
    """task-tier-reduction/task0010 (AC-1, AC-4, section 2a of
    create-plan-phase.md, worded identically there): the exemption's
    trigger is the plan value's final path segment equals the task
    document's file name -- not the full path, so this decision uses only
    data the phase document already fixes. Evaluated on the raw,
    not-yet-validated `plan_rel` string; callers must reach this only AFTER
    the path-safety, symlink and containment checks have already passed
    (see `_validate_task_plans_against_patch`), so a patch-supplied path
    can never use this exemption to skip containment."""
    segments = path_segments(plan_rel)
    return bool(segments) and segments[-1] == TASK_DOCUMENT_FILE_NAME


def _task_plan_document_errors(task_id, plan_rel, files_declared, feature_dir, *, require_acceptance_criteria):
    """The checks of one task plan document against the files its task
    declares: path safety, symlink and containment, existence, size, then
    (unless the plan is the task document) the Files sections against
    `files_declared` and, when `require_acceptance_criteria`, the Acceptance
    Criteria section. Shared by the entries check and the check on the tasks
    a final-path correction corrects."""
    errors = []
    plan_path, path_error = _resolve_contained_relative_path(feature_dir, plan_rel)
    if path_error is not None:
        errors.append(err("task-plan-path", f"{task_id}: {path_error}"))
        return errors
    if not plan_path.is_file():
        errors.append(err("task-plan-missing", f"{task_id}: plan file {plan_path} not found"))
        return errors
    try:
        plan_size = plan_path.stat().st_size
    except OSError as exc:
        errors.append(err("task-plan-missing", f"{task_id}: cannot stat plan file {plan_path}: {exc}"))
        return errors
    if plan_size > MAX_PLAN_READ_BYTES:
        errors.append(
            err(
                "task-plan-too-large",
                f"{task_id}: plan file {plan_path} is {plan_size} bytes, exceeding the {MAX_PLAN_READ_BYTES} byte limit",
            )
        )
        return errors
    if _task_entry_plan_is_task_document(plan_rel):
        # task-tier-reduction/task0010 (AC-1, AC-3): the task document
        # carries only `## Change` and `## Expected Result` -- neither
        # content check below applies to it. Every check above this
        # point (path safety, symlink rejection, containment,
        # existence, size) still ran unconditionally.
        return errors
    plan_text = plan_path.read_text(encoding="utf-8")
    plan_files, parse_errors = extract_task_plan_files(plan_text)
    for pe in parse_errors:
        errors.append(err("task-plan-files", f"{task_id}: {pe}"))
    if plan_files != files_declared:
        errors.append(
            err(
                "task-plan-files-mismatch",
                f"{task_id}: files {sorted(files_declared)} does not match task plan Files sections {sorted(plan_files)}",
            )
        )
    if require_acceptance_criteria and not task_plan_has_acceptance_criteria(plan_text):
        errors.append(err("task-plan-acceptance-criteria", f"{task_id}: plan lacks a non-empty Acceptance Criteria (MANDATORY) section"))
    return errors


def _validate_corrected_task_plans(workflow_patch, feature_dir, workflow):
    """FR5 plan agreement: for each plan used by a task a final-path
    correction or a feature-docs correction corrects, the plan's Files
    sections against the files of those tasks after the correction, as for an
    entry (`task-plan-files-mismatch`).
    The target tasks are grouped by normalized plan and each plan is checked
    once, against the union of its tasks' files (FR6); a plan used by one
    target behaves as for that task alone. Needs the current workflow.yaml
    (the carried record is not in the patch) and the feature directory."""
    errors = []
    corrections = _well_formed_path_corrections(workflow_patch)
    removals = _well_formed_feature_docs_removals(workflow_patch)
    if not (corrections or removals) or not isinstance(workflow, dict):
        return errors
    existing = _tasks_of(workflow)
    corrected = {}
    for correction in corrections + removals:
        record = existing.get(correction["task_id"])
        if isinstance(record, dict):
            corrected[correction["task_id"]] = copy.deepcopy(record)
    _apply_path_corrections(corrected, corrections)
    _apply_feature_docs_removals(corrected, removals)
    plans = {}  # normalized plan path -> {"plan": spelling, "task_ids": [...], "files": set}
    for task_id, record in corrected.items():
        plan_rel = record.get("plan")
        if not plan_rel or not isinstance(plan_rel, str):
            continue
        group = plans.setdefault(
            "/".join(path_segments(plan_rel)), {"plan": plan_rel, "task_ids": [], "files": set()}
        )
        group["task_ids"].append(task_id)
        files = record.get("files")
        if isinstance(files, list):
            group["files"] |= {f for f in files if isinstance(f, str)}
    for group in plans.values():
        errors.extend(
            _task_plan_document_errors(
                ", ".join(group["task_ids"]), group["plan"], group["files"], feature_dir,
                require_acceptance_criteria=False,
            )
        )
    return errors


def _validate_task_plans_against_patch(workflow_patch, feature_dir, workflow=None):
    errors = []
    entries = (workflow_patch.get("tasks_patch") or {}).get("entries") or {}
    files_by_task = {}
    for task_id, entry in entries.items():
        files_declared = set(entry.get("files") or [])
        files_by_task[task_id] = files_declared
        plan_rel = entry.get("plan")
        if not plan_rel:
            continue
        errors.extend(
            _task_plan_document_errors(
                task_id, plan_rel, files_declared, feature_dir, require_acceptance_criteria=True
            )
        )

    errors.extend(_validate_corrected_task_plans(workflow_patch, feature_dir, workflow))

    file_owner_count = {}
    for fset in files_by_task.values():
        for f in fset:
            file_owner_count[f] = file_owner_count.get(f, 0) + 1
    if any(c > 1 for c in file_owner_count.values()):
        impl_path = feature_dir / "IMPLEMENTATION.md"
        if not impl_path.is_file() or not implementation_md_has_shared_components(impl_path.read_text(encoding="utf-8")):
            errors.append(
                err(
                    "shared-components-missing",
                    "multiple tasks declare the same file but IMPLEMENTATION.md lacks a ## Shared Components section",
                )
            )
    return errors


# ---------------------------------------------------------------------------
# Scenario-ID form check (scenario-id-ts-hyphen/task0001, FR3)
#
# The TS-n form is the only scenario ID form an implementation-planner result
# may newly write into VERIFICATION.md or a task plan. This check reports the
# hyphen-less (TSn) IDs it finds in those two kinds of document. It runs only
# for a `completed` implementation-planner result with a feature directory
# (IMPLEMENTATION.md D1) and reads nothing but VERIFICATION.md and the task
# plans the patch names. The read side -- `_TS_ID_RE`,
# `extract_verification_scenario_ids`, `_strip_noise` -- is not touched: both
# forms stay readable (FR4).
#
# scenario-id-fence-scope/task0001: the check leaves out line-start fenced
# blocks (backtick or tilde) and HTML comments, not what `_strip_noise` removes.
# So an ID in a tilde block is read but not reported, and an ID between inline
# triple backticks is reported but not read (SPEC A7).
# ---------------------------------------------------------------------------

SCENARIO_ID_FORM_ERROR_CODE = "scenario-id-form"
VERIFICATION_DOCUMENT_FILE_NAME = "VERIFICATION.md"

# Reasons `_read_document_for_scenario_scan` gives for not returning text.
_SCAN_ABSENT = "absent"
_SCAN_SYMLINK = "symlink"
_SCAN_NOT_REGULAR = "not-regular"
_SCAN_TOO_LARGE = "too-large"
_SCAN_NOT_UTF8 = "not-utf8"
_SCAN_UNREADABLE = "unreadable"


# A line that opens a fenced block: optional leading spaces and tabs, then a
# run of three or more backticks or tildes (the whole run is the opening
# length). What follows the run is checked by `_drop_fenced_blocks`.
_BLOCK_OPENING_LINE_RE = re.compile(r"[ \t]*(`{3,}|~{3,})(.*)\Z", re.DOTALL)


def _is_block_closing_line(line, fence_char, fence_length):
    """True when `line` closes a block opened by a run of `fence_length`
    `fence_char`: optional leading spaces and tabs, a run of `fence_char` at
    least that long, then only spaces and tabs."""
    body = line.lstrip(" \t")
    run = len(body) - len(body.lstrip(fence_char))
    return run >= fence_length and not body[run:].strip(" \t")


def _drop_fenced_blocks(text):
    """Removes the line-start fenced blocks of `text`, each as whole lines
    from its opening line through its closing line (an unclosed block runs to
    the end of the text), and returns the kept lines joined by line feeds.
    Lines are split on the line feed only; a trailing carriage return is part
    of the line end when a line is judged. A backtick opening line holds no
    backtick after its run; a tilde opening line has no such limit."""
    kept = []
    fence_char = None
    fence_length = 0
    for raw_line in text.split("\n"):
        line = raw_line[:-1] if raw_line.endswith("\r") else raw_line
        if fence_char is not None:
            if _is_block_closing_line(line, fence_char, fence_length):
                fence_char = None
            continue
        opening = _BLOCK_OPENING_LINE_RE.match(line)
        if opening is not None:
            run, rest = opening.group(1), opening.group(2)
            if run[0] == "~" or "`" not in rest:
                fence_char = run[0]
                fence_length = len(run)
                continue
        kept.append(raw_line)
    return "\n".join(kept)


def find_hyphenless_scenario_ids(text):
    """Hyphen-less ID detection rule (IMPLEMENTATION.md Shared Components,
    scenario-id-fence-scope SPEC FR1 to FR5). The text that is scanned is what
    remains of `text` after the line-start fenced blocks (backtick or tilde,
    see `_drop_fenced_blocks`) and then the HTML comments are removed, in that
    order, as `_strip_noise` does. `_strip_noise` itself is not called, so
    the range differs from the read side: a tilde block is excluded here, and
    triple backticks inside a line are not a block, so an ID between them is
    scanned, as is an inline code span with single backticks. Of the matches
    of the read grammar `_TS_ID_RE`, the ones counted are those that contain
    no hyphen and whose immediately preceding character is not an ASCII
    letter or an ASCII digit (so `XTS1` and `UTS46` are not scenario IDs). A
    match at the very start of the text has no preceding character and
    counts; a non-ASCII preceding character, such as Japanese text, does not
    stop a match from counting. Returns the set of matched literal strings.
    Pure: no file access, and no exception for any string."""
    stripped = _HTML_COMMENT_RE.sub("", _drop_fenced_blocks(text))
    found = set()
    for match in _TS_ID_RE.finditer(stripped):
        token = match.group(0)
        if "-" in token:
            continue
        start = match.start()
        if start > 0:
            preceding = stripped[start - 1]
            if preceding.isascii() and preceding.isalnum():
                continue
        found.add(token)
    return found


def _read_document_for_scenario_scan(path):
    """Reads `path` as UTF-8 text for the scenario-ID scan and never raises.
    Returns (text, None), or (None, reason) with reason one of the `_SCAN_*`
    constants. The file is classified by `lstat` first, so a symlink, a
    directory or a special file (a FIFO would block a read) is never opened;
    it is then opened without following a symlink and without blocking, the
    opened descriptor is checked to still be a regular file, and at most
    `MAX_PLAN_READ_BYTES` + 1 bytes are read, so an oversized file is never
    loaded in full."""
    try:
        info = os.lstat(path)
    except (FileNotFoundError, NotADirectoryError):
        return None, _SCAN_ABSENT
    except OSError:
        return None, _SCAN_UNREADABLE
    if stat.S_ISLNK(info.st_mode):
        return None, _SCAN_SYMLINK
    if not stat.S_ISREG(info.st_mode):
        return None, _SCAN_NOT_REGULAR
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        fd = os.open(path, flags)
    except OSError:
        return None, _SCAN_UNREADABLE
    try:
        handle = os.fdopen(fd, "rb")
    except OSError:
        os.close(fd)
        return None, _SCAN_UNREADABLE
    try:
        with handle:
            if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                return None, _SCAN_NOT_REGULAR
            data = handle.read(MAX_PLAN_READ_BYTES + 1)
    except OSError:
        return None, _SCAN_UNREADABLE
    if len(data) > MAX_PLAN_READ_BYTES:
        return None, _SCAN_TOO_LARGE
    try:
        return data.decode("utf-8"), None
    except UnicodeDecodeError:
        return None, _SCAN_NOT_UTF8


def _scenario_scan_reason_text(reason):
    return {
        _SCAN_SYMLINK: "it is a symlink",
        _SCAN_NOT_REGULAR: "it is not a regular file",
        _SCAN_TOO_LARGE: f"it is too large (over {MAX_PLAN_READ_BYTES} bytes)",
        _SCAN_NOT_UTF8: "it is not UTF-8",
    }.get(reason, "it could not be read")


def _hyphenless_ids_message(subject, ids):
    return (
        f"{subject} contains hyphen-less scenario IDs: {', '.join(sorted(ids))} "
        "(write a hyphen between TS and the number)"
    )


def _validate_scenario_id_form(workflow_patch, feature_dir, workflow=None):
    """The scenario-ID form check for one `completed` implementation-planner
    result (Shared Components, "Scenario-ID form check contract"). Returns a
    list of `scenario-id-form` errors, possibly empty, and never raises for
    any file content or file state. The caller decides whether the check
    applies (worker, status, feature directory).

    Target (a): VERIFICATION.md directly under `feature_dir` -- absent is not
    an error (the minimal tier writes none); a symlink, a non-regular file, a
    file over `MAX_PLAN_READ_BYTES` or a file that is not UTF-8 gives one
    error naming the reason and is not scanned. This target is skipped only
    when `workflow` is given and the patch is on the correction entry
    (non-empty `tasks_patch.path_corrections`, create-plan `completed`,
    implement `failed`; subagent-report-write-block IMPLEMENTATION.md D8 and
    final-path-correction-medium-fixes FR5): the correction may change
    nothing but path strings there, so the document is not re-scanned. A
    correction patch on the Re-planning path, one in any other state, and one
    validated without a workflow (`workflow` None, the two-argument call)
    scan it.

    Target (b): the plan of every `tasks_patch.entries` item whose final path
    segment is not `TASK.md`. A plan is read only when it passes the checks
    `_validate_task_plans_against_patch` applies to the same value (safe
    path, no symlink segment, containment, regular file, size limit); one
    that fails them is skipped, because those failures are reported there."""
    errors = []
    feature_dir = Path(feature_dir)

    if workflow is not None and _on_correction_entry(workflow, workflow_patch):
        text, reason = None, _SCAN_ABSENT  # D8, FR5: the VERIFICATION.md target is skipped
    else:
        text, reason = _read_document_for_scenario_scan(feature_dir / VERIFICATION_DOCUMENT_FILE_NAME)
    if reason is None:
        found = find_hyphenless_scenario_ids(text)
        if found:
            errors.append(
                err(SCENARIO_ID_FORM_ERROR_CODE, _hyphenless_ids_message(VERIFICATION_DOCUMENT_FILE_NAME, found))
            )
    elif reason != _SCAN_ABSENT:
        errors.append(
            err(
                SCENARIO_ID_FORM_ERROR_CODE,
                f"{VERIFICATION_DOCUMENT_FILE_NAME} was not scanned for hyphen-less scenario IDs: "
                f"{_scenario_scan_reason_text(reason)}",
            )
        )

    if not isinstance(workflow_patch, dict):
        return errors
    tasks_patch = workflow_patch.get("tasks_patch")
    entries = tasks_patch.get("entries") if isinstance(tasks_patch, dict) else None
    if not isinstance(entries, dict):
        return errors
    for task_id, entry in entries.items():
        plan_rel = entry.get("plan") if isinstance(entry, dict) else None
        if not plan_rel:
            continue
        plan_path, path_error = _resolve_contained_relative_path(feature_dir, plan_rel)
        if path_error is not None or _task_entry_plan_is_task_document(plan_rel):
            continue
        plan_text, plan_reason = _read_document_for_scenario_scan(plan_path)
        if plan_reason is not None:
            continue
        found = find_hyphenless_scenario_ids(plan_text)
        if found:
            errors.append(
                err(
                    SCENARIO_ID_FORM_ERROR_CODE,
                    _hyphenless_ids_message(f"{task_id}: plan {plan_rel}", found),
                )
            )
    return errors


def _declared_scenario_renames(payload):
    """rework-docs-only-task-routing/task0004 (FR6, FR7, TM-5): the rename
    relation the rework-planner declared in
    `payload.doc_corrections[].scenario_renames`, as a set of
    `(from, to)` pairs. The validator consumes only `scenario_renames`
    (`doc_corrections` itself stays optional); a malformed declaration
    contributes no pair and never raises -- `doc_corrections` not a list,
    an entry not a mapping, `scenario_renames` not a list, a pair not a
    mapping, or a pair whose `from` / `to` is not a non-blank string."""
    pairs = set()
    doc_corrections = payload.get("doc_corrections") if isinstance(payload, dict) else None
    if not isinstance(doc_corrections, list):
        return pairs
    for correction in doc_corrections:
        if not isinstance(correction, dict):
            continue
        renames = correction.get("scenario_renames")
        if not isinstance(renames, list):
            continue
        for pair in renames:
            if not isinstance(pair, dict):
                continue
            old_id, new_id = pair.get("from"), pair.get("to")
            if isinstance(old_id, str) and old_id.strip() and isinstance(new_id, str) and new_id.strip():
                pairs.add((old_id, new_id))
    return pairs


# Phrases that tell the rename-aware coverage messages apart (the
# no-declaration message of row 4 carries its own, "no declared rename").
_MSG_OLD_ID = "is the old ID of declared rename"
_MSG_DIFF_UNAVAILABLE = "document diff is unavailable"
_MSG_NOT_CONFIRMED = "is not confirmed by the VERIFICATION.md diff"


def _load_scenario_ids(path):
    """rework-docs-only-medium-fixes/task0001: the scenario-ID set a
    VERIFICATION.md defines, as `(state, value)`.

    - `("ok", ids)`: the file was read as text; `ids` come from
      `extract_verification_scenario_ids` (the one derivation every
      cross-artifact check shares).
    - `("absent", None)`: the path has no directory entry (not found, or a
      parent component is not a directory).
    - `("unreadable", reason)`: the path exists but cannot be read as text.
      `reason` is a short human-readable string. That covers a symlink
      (whether it points to a regular file, to a device or nowhere), a
      directory, a FIFO or a device file, a file over `MAX_PLAN_READ_BYTES`,
      bytes that do not decode as UTF-8, a permission failure and a path that
      cannot be examined (such as one with a NUL character).

    Only a regular file that is not a symlink is read, and at most
    `MAX_PLAN_READ_BYTES` + 1 bytes of it: the reading is delegated to
    `_read_document_for_scenario_scan`, which opens the entry without
    following a symlink and without blocking, so a FIFO never makes the
    loader wait and a file such as /dev/zero behind a symlink is never read.
    Never raises."""
    try:
        text, reason = _read_document_for_scenario_scan(path)
    except (OSError, ValueError) as exc:
        return "unreadable", type(exc).__name__
    if reason == _SCAN_ABSENT:
        return "absent", None
    if reason is not None:
        return "unreadable", _scenario_scan_reason_text(reason)
    return "ok", extract_verification_scenario_ids(text)


class _VerificationDiff:
    """rework-docs-only-medium-fixes/task0001 (D2): the document diff the
    rename-aware coverage rule leans on.

    The diff is *available* when `--feature-dir` and `--baseline-dir` are both
    given and feature-dir contains VERIFICATION.md. `post` is the scenario-ID
    set of `{feature-dir}/VERIFICATION.md`; `baseline` is that of
    `{baseline-dir}/VERIFICATION.md`, empty when the file is absent. `missing`
    names what keeps the diff unavailable. A VERIFICATION.md that exists but
    cannot be read as text is recorded in `unreadable` (label -> (path,
    reason)); its set stays None. `need_*` records that a judgement used a
    set, so `unreadable_errors` reports one `rework-index` error per
    unreadable file that was actually needed -- never one per covered ID."""

    def __init__(self, feature_dir, baseline_dir):
        self.post = None
        self.baseline = None
        self.available = False
        self.missing = []
        self.unreadable = {}
        self._needed = set()
        if feature_dir is None:
            self.missing.append("--feature-dir")
        if baseline_dir is None:
            self.missing.append("--baseline-dir")
        post_state = None
        if feature_dir is not None:
            post_path = Path(feature_dir) / "VERIFICATION.md"
            post_state, post_value = _load_scenario_ids(post_path)
            if post_state == "absent":
                self.missing.append("feature-dir's VERIFICATION.md")
            elif post_state == "ok":
                self.post = post_value
            else:
                self.unreadable["post"] = (post_path, post_value)
        if feature_dir is None or baseline_dir is None or post_state == "absent":
            return
        self.available = True
        baseline_path = Path(baseline_dir) / "VERIFICATION.md"
        baseline_state, baseline_value = _load_scenario_ids(baseline_path)
        if baseline_state == "ok":
            self.baseline = baseline_value
        elif baseline_state == "absent":
            self.baseline = set()
        else:
            self.unreadable["baseline"] = (baseline_path, baseline_value)

    @property
    def usable(self):
        """The diff is available and both sets could be built."""
        return self.available and not self.unreadable

    def need_post(self):
        self._needed.add("post")
        return "post" not in self.unreadable

    def need_both(self):
        self._needed.update(("post", "baseline"))
        return not self.unreadable

    def unreadable_errors(self):
        errors = []
        for label in ("post", "baseline"):
            if label in self.unreadable and label in self._needed:
                path, reason = self.unreadable[label]
                errors.append(
                    err(
                        "rework-index",
                        f"{path} {'(post-change)' if label == 'post' else '(baseline)'} "
                        f"cannot be read as text ({reason}); no covered_by_existing or "
                        "new_scenarios ID is accepted on the strength of it",
                    )
                )
        return errors


class _RenameAwareCoverage:
    """rework-docs-only-medium-fixes/task0001 (D2, FR1, FR2): judges one
    `covered_by_existing` ID at a time. The first matching row decides:

    1. the `from` of a declared pair -> rejected, with or without the diff;
    2. a verification_index key -> with the diff, accepted only when it is in
       the post set; without the diff, accepted (unchanged behavior);
    3. the `to` of declared pair(s) -> with the diff, accepted only when every
       pair with this `to` meets all four conditions (from is a
       verification_index key, to is in the post set, from is in the baseline
       set, from is not in the post set); without the diff, rejected;
    4. anything else -> rejected with the no-declaration message.

    Every rejection is a `rework-index` error. `judge` returns the errors for
    the ID; an ID whose judgement needs a set that cannot be read gets none,
    because the one error of `_VerificationDiff.unreadable_errors` covers it."""

    def __init__(self, declared_pairs, verification_index, diff):
        self.verification_index = verification_index
        self.diff = diff
        self.froms = {}
        self.tos = {}
        for old_id, new_id in sorted(declared_pairs):
            self.froms.setdefault(old_id, []).append(new_id)
            self.tos.setdefault(new_id, []).append(old_id)

    def _failed_condition(self, old_id, new_id):
        """The first of the four conditions the pair fails, or None."""
        if old_id not in self.verification_index:
            return f"{old_id!r} is not a verification_index key"
        if new_id not in self.diff.post:
            return f"{new_id!r} is absent from the post-change VERIFICATION.md"
        if old_id not in self.diff.baseline:
            return f"{old_id!r} is absent from the baseline VERIFICATION.md"
        if old_id in self.diff.post:
            return f"{old_id!r} is still defined in the post-change VERIFICATION.md"
        return None

    def judge(self, task_id, cid):
        diff = self.diff
        if cid in self.froms:  # row 1
            targets = ", ".join(repr(t) for t in self.froms[cid])
            return [
                err(
                    "rework-index",
                    f"{task_id}: covered_by_existing {cid!r} {_MSG_OLD_ID} "
                    f"{cid!r} -> {targets}; a renamed-away ID is never covered "
                    "(payload.doc_corrections[].scenario_renames)",
                )
            ]
        if cid in self.verification_index:  # row 2
            if not diff.available:
                return []
            if not diff.need_post() or cid in diff.post:
                return []
            return [
                err(
                    "rework-index",
                    f"{task_id}: covered_by_existing {cid!r} is a verification_index key but "
                    "is missing from the post-change VERIFICATION.md",
                )
            ]
        if cid in self.tos:  # row 3
            if not diff.available:
                return [
                    err(
                        "rework-index",
                        f"{task_id}: covered_by_existing {cid!r} is the target of a declared "
                        f"rename, but the rename cannot be confirmed because the {_MSG_DIFF_UNAVAILABLE} "
                        f"(missing: {', '.join(diff.missing)})",
                    )
                ]
            if not diff.need_both():
                return []
            for old_id in self.tos[cid]:
                failed = self._failed_condition(old_id, cid)
                if failed is not None:
                    return [
                        err(
                            "rework-index",
                            f"{task_id}: covered_by_existing {cid!r}: declared rename "
                            f"{old_id!r} -> {cid!r} {_MSG_NOT_CONFIRMED}: {failed}",
                        )
                    ]
            return []
        return [  # row 4 -- wording is fixed by earlier features; do not reword
            err(
                "rework-index",
                f"{task_id}: covered_by_existing {cid!r} not in verification_index, and no "
                "declared rename maps it to the verification index "
                "(payload.doc_corrections[].scenario_renames)",
            )
        ]


def _validate_rework_index(rework_index, workflow_patch, envelope, feature_dir, baseline_dir, payload=None):
    errors = []
    verification_index = (envelope or {}).get("verification_index") or {}
    # Rename-aware coverage rule (rework-docs-only-task-routing/task0004,
    # tightened by rework-docs-only-medium-fixes/task0001): a
    # `covered_by_existing` ID reached through a declared pair (`from` ->
    # `to`) is accepted only when the baseline and post-change VERIFICATION.md
    # confirm the rename, and the old ID of a rename is never accepted.
    # `payload` is the result's payload; None (a caller that has no payload)
    # declares nothing. See `_RenameAwareCoverage` for the decision order.
    diff = _VerificationDiff(feature_dir, baseline_dir)
    coverage = _RenameAwareCoverage(_declared_scenario_renames(payload), verification_index, diff)

    # bs10 (round 2, validator half): without a baseline directory there is
    # nothing to diff VERIFICATION.md against, so "new" cannot be verified --
    # the previous fallback ("the identifier exists in the current document")
    # degrades to trusting the rework-planner's own claim, since the planner
    # is the one that just wrote that document. `new_ids_in_doc` is therefore
    # only ever computed when a baseline IS supplied; the per-task loop below
    # turns a declared `new_scenarios` with no baseline into a hard error
    # instead of silently accepting it.
    #
    # task-tier-reduction/task0008 (AC-3, TS-19): a THIRD situation exists
    # alongside "no baseline supplied" and "baseline supplied, document
    # present" -- the most-reducing tier never produces VERIFICATION.md at
    # all (references/rework-task-synthesis.md Section 8a), so the feature
    # directory's own VERIFICATION.md can be absent even when a baseline
    # directory WAS supplied. That absence must not fall through into
    # `new_ids_in_doc` staying None and therefore silently skipping the
    # check below (the pre-task0008 gap) -- `verification_doc_absent`
    # records it explicitly so the per-task loop gives it its own outcome.
    #
    # rework-docs-only-medium-fixes/task0001: both sets come from
    # `_VerificationDiff`, the one reader the rename-aware coverage rule
    # shares, so the two checks agree and a VERIFICATION.md that cannot be
    # read as text is an error rather than an exception.
    new_ids_in_doc = diff.post - diff.baseline if diff.usable else None
    verification_doc_absent = feature_dir is not None and baseline_dir is not None and not diff.available

    tests_append_all = set()
    if workflow_patch is not None:
        req_patch = workflow_patch.get("requirements_patch") or {}
        for rpatch in (req_patch.get("entries") or {}).values():
            tests_append_all.update((rpatch.get("set") or {}).get("tests_append") or [])

    # as5: rework_index completeness must be verified in BOTH directions
    # against the tasks the patch actually creates -- an empty (or merely
    # incomplete) rework_index previously passed unnoticed because nothing
    # ever compared its keys to tasks_patch.entries.
    created_task_ids = set(((workflow_patch or {}).get("tasks_patch") or {}).get("entries") or {})
    index_task_ids = set(rework_index)
    for task_id in sorted(created_task_ids - index_task_ids):
        errors.append(err("rework-index", f"{task_id}: created by tasks_patch but missing from rework_index"))
    for task_id in sorted(index_task_ids - created_task_ids):
        errors.append(err("rework-index", f"{task_id}: present in rework_index but not created by tasks_patch"))

    for task_id, ri in rework_index.items():
        if not isinstance(ri, dict):
            errors.append(err("rework-index", f"{task_id}: rework_index entry must be a mapping"))
            continue
        covered = ri.get("covered_by_existing") or []
        new_sc = ri.get("new_scenarios") or []
        if not covered and not new_sc:
            errors.append(err("rework-index", f"{task_id}: covered_by_existing and new_scenarios are both empty"))
        if not isinstance(covered, list):
            errors.append(err("rework-index", f"{task_id}: covered_by_existing must be a list of scenario IDs"))
            covered = []
        for cid in covered:
            if not isinstance(cid, str):
                # Non-string values never take part in set or membership
                # computations: they are excluded and reported (NFR1).
                errors.append(
                    err("rework-index", f"{task_id}: covered_by_existing entry {cid!r} is not a string")
                )
                continue
            errors.extend(coverage.judge(task_id, cid))
        if new_sc and baseline_dir is None:
            errors.append(
                err(
                    "rework-index",
                    f"{task_id}: new_scenarios is declared but no --baseline-dir was supplied; "
                    "the claim that these scenarios are new (rather than pre-existing) cannot be "
                    "verified against a VERIFICATION.md diff",
                )
            )
        elif new_sc and verification_doc_absent:
            # task-tier-reduction/task0008 (AC-3, TS-19): distinct from the
            # no-baseline-directory case above -- a baseline WAS supplied,
            # but there is no VERIFICATION.md in the feature directory to
            # diff it against at all (the most-reducing tier never produces
            # one; references/rework-task-synthesis.md Section 8a). Fail
            # closed, the same as the no-baseline case, but name the case
            # distinctly so the two are never confused when triaging a
            # rejection.
            errors.append(
                err(
                    "rework-index",
                    f"{task_id}: new_scenarios is declared but no VERIFICATION.md exists in "
                    "the feature directory to diff (the most-reducing tier never produces one "
                    "until the tier is upgraded); the claim that these scenarios are new cannot "
                    "be verified",
                )
            )
        elif diff.available and new_sc:
            # An unreadable set is reported once, after the loop.
            if diff.need_both():
                for nid in new_sc:
                    if nid not in new_ids_in_doc:
                        errors.append(err("rework-index", f"{task_id}: new_scenarios {nid!r} is not a new VERIFICATION.md scenario"))
        if new_sc and not set(new_sc).issubset(tests_append_all):
            errors.append(err("rework-index", f"{task_id}: new_scenarios must also appear in requirements_patch tests_append"))
    errors.extend(diff.unreadable_errors())
    return errors


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_arg_parser():
    parser = argparse.ArgumentParser(
        prog="validate-worker-output.py",
        description="Validate em-workflow worker output / question packets / "
        "answers / workflow patches / phase-state (design-input.md 5.11.1).",
    )
    parser.add_argument("--kind", required=True, choices=KINDS)
    parser.add_argument("--worker", required=True, choices=WORKERS)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--packet", type=Path)
    parser.add_argument("--answers", type=Path)
    parser.add_argument("--workflow", type=Path)
    parser.add_argument("--registries", type=Path)
    parser.add_argument("--phase-state", type=Path, dest="phase_state")
    parser.add_argument("--input-envelope", type=Path, dest="input_envelope")
    parser.add_argument("--digest-source", type=Path, dest="digest_source")
    parser.add_argument("--feature-dir", type=Path, dest="feature_dir")
    parser.add_argument("--baseline-dir", type=Path, dest="baseline_dir")
    parser.add_argument("--dry-run-apply", action="store_true", dest="dry_run_apply")
    # Report artifact names (FR4): the integration worktree and the full
    # commit ID of the integration tip. Both are optional to the parser and
    # read only when a task's files hold a report artifact name. Plain
    # strings, so an empty value stays visible as empty rather than becoming
    # the current directory.
    parser.add_argument("--target-repo", dest="target_repo", default=None)
    parser.add_argument("--base-commit", dest="base_commit", default=None)
    # Final-path correction (FR5) and feature-docs correction (D7): the
    # append-only journal of the run, read only when the patch carries
    # `tasks_patch.path_corrections` or `tasks_patch.feature_docs_removals`.
    parser.add_argument("--journal", type=Path, dest="journal")
    return parser


def _load_optional(path, what):
    if path is None:
        return None
    text = load_yaml_or_json(path, what)
    data, parse_err = parse_yaml_text(text)
    if parse_err:
        raise ExecutionError(f"cannot parse {what} file {path}: {parse_err}")
    return data


def _load_registries(registries_dir):
    if registries_dir is None:
        return None
    return {
        "skills": load_skills_vocabulary(registries_dir),
        "domains": load_domains_vocabulary(registries_dir),
    }


def main(argv=None):
    if yaml is None:
        print("execution error: PyYAML is required (import yaml failed)", file=sys.stderr)
        return 2

    parser = build_arg_parser()
    args = parser.parse_args(argv)

    if args.kind == "worker-result" and args.input_envelope is None:
        print(
            "execution error: --input-envelope is required for --kind worker-result "
            f"(worker {args.worker!r})",
            file=sys.stderr,
        )
        return 2

    try:
        input_text = load_yaml_or_json(args.input, "--input")
        envelope = _load_optional(args.input_envelope, "--input-envelope")
        packet = _load_optional(args.packet, "--packet")
        answers = _load_optional(args.answers, "--answers")
        workflow = _load_optional(args.workflow, "--workflow")
        phase_state = _load_optional(args.phase_state, "--phase-state")
        digest_source = _load_optional(args.digest_source, "--digest-source")
        registries = _load_registries(args.registries)
    except ExecutionError as exc:
        print(f"execution error: {exc}", file=sys.stderr)
        return 2

    data, parse_err = parse_yaml_text(input_text)
    if parse_err:
        result = {"kind": args.kind, "errors": [err("syntax", f"--input is not valid YAML/JSON: {parse_err}")]}
        print(json.dumps(result, indent=2, sort_keys=True))
        return 1

    feature_dir = args.feature_dir
    baseline_dir = args.baseline_dir
    gate_registry = build_gate_registry(Path(__file__).resolve().parent.parent / "references")

    # bs9 (round 2): every structural guard above catches the malformed-input
    # shapes design-input.md names explicitly. This wrapper is the safety
    # net for whatever it does NOT name: an unexpected exception here is an
    # execution error (exit 2, message on stderr), never exit 1 with an
    # empty stdout -- exit 1 must always carry the JSON error detail the
    # contract promises.
    try:
        if args.kind == "worker-result":
            errors = validate_worker_result(
                data,
                args.worker,
                envelope=envelope,
                packet=packet,
                answers=answers,
                workflow=workflow,
                registries=registries,
                phase_state=phase_state,
                digest_source=digest_source,
                feature_dir=feature_dir,
                baseline_dir=baseline_dir,
                dry_run=args.dry_run_apply,
                gate_registry=gate_registry,
                target_repo=args.target_repo,
                base_commit=args.base_commit,
                journal=args.journal,
            )
        elif args.kind == "question-packet":
            errors = validate_question_packet(data, gate_registry=gate_registry)
        elif args.kind == "answers":
            errors = validate_answers_list(data, packet=packet)
        elif args.kind == "workflow-patch":
            errors = validate_workflow_patch(
                data,
                workflow=workflow,
                registries=registries,
                digest_source=digest_source,
                phase_state=phase_state,
                dry_run=args.dry_run_apply,
                feature_dir=feature_dir,
                envelope=envelope,
                target_repo=args.target_repo,
                base_commit=args.base_commit,
                journal=args.journal,
            )
        elif args.kind == "phase-state":
            errors = validate_phase_state(data)
        else:  # pragma: no cover - argparse `choices` already prevents this
            print(f"execution error: unknown --kind {args.kind!r}", file=sys.stderr)
            return 2
    except ExecutionError as exc:
        # A declared execution error raised below the parser (for example the
        # report-name base inputs): exit 2 with the message itself.
        print(f"execution error: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # noqa: BLE001 -- last-resort exit-2 safety net
        print(f"execution error: unexpected exception during --kind {args.kind!r} validation: {exc}", file=sys.stderr)
        return 2

    if errors:
        result = {"kind": args.kind, "worker": args.worker, "errors": errors}
        print(json.dumps(result, indent=2, sort_keys=True))
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
