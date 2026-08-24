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
import re
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

PHASE_VALUES = {"create-spec", "create-plan", "review", "verify", "rework"}

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

WRITE_POLICY_ACTIONS = {
    "create",
    "replace_own",
    "replace_authorized",
    "preserve",
    "extend_only",
    "regenerate",
}

COMPLEXITY_VALUES = {"low", "medium", "high"}

REQUIREMENTS_PATCH_SET_KEYS = {
    "tasks_append",
    "tests_append",
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
# Markdown structural parsing (design-input.md 5.11.1 "Markdown 解析の範囲")
#
# Limited to the four existing template markers; no new markers are
# introduced and free-form prose is never semantically parsed.
# ---------------------------------------------------------------------------

_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_BACKTICK_RE = re.compile(r"`([^`]+)`")
_BULLET_RE = re.compile(r"^[ \t]*-\s+(.*)$", re.MULTILINE)
_TS_ID_RE = re.compile(r"TS-\d+")


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
    TS-<n> identifiers (plan-writing/SKILL.md 131-139)."""
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
                "(NFR4 fail-closed: a worker cannot disable the batch abort for "
                "spec-change / security / license questions)",
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
# --kind workflow-patch (5.5)
# ---------------------------------------------------------------------------

def _validate_verify_failed_items_categories(workflow):
    """rework-contract-drift/task0004 (FR3 validator half, FR6): every
    entry of `workflow.yaml`'s `verify` step `failed_items[]` carries a
    REQUIRED, non-empty `category` drawn from FAILED_ITEM_CATEGORY_VALUES
    (references/workflow-schema.md owns the field's definition and
    vocabulary; this function enforces it, never restates the vocabulary
    in prose elsewhere). Runs on the invocation path that already reads
    `--workflow` (validate_workflow_patch), unconditional on
    --dry-run-apply. Tolerates a missing/absent verify step or
    failed_items list (nothing to check yet) and a non-mapping entry
    (reported elsewhere, not this function's job) rather than crashing."""
    errors = []
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
    if mode == "append":
        provenance = entry.get("provenance")
        if not provenance:
            errors.append(err("provenance", f"{p}.provenance is required for append"))
        elif not isinstance(provenance, dict):
            errors.append(err("provenance", f"{p}.provenance must be a mapping"))
        elif provenance.get("source") not in ("review", "verify"):
            errors.append(err("provenance", f"{p}.provenance.source must be 'review' or 'verify'"))
    return errors


def validate_workflow_patch(
    data,
    *,
    workflow=None,
    registries=None,
    digest_source=None,
    phase_state=None,
    dry_run=False,
    feature_dir=None,
):
    if not isinstance(data, dict):
        return [err("structure", "workflow patch must be a mapping")]
    errors = []
    if workflow is not None:
        # FR3 validator half / FR6: this is the invocation path that
        # already reads --workflow (workflow_requirement_ids below); the
        # verify-step failed_items[].category vocabulary is enforced here
        # too, unconditional on --dry-run-apply.
        errors.extend(_validate_verify_failed_items_categories(workflow))
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
        if not sp.get("step_id"):
            errors.append(err("step_patches", f"step_patches[{i}].step_id is required"))
        set_block = sp.get("set") or {}
        if set(set_block) - {"status"}:
            errors.append(err("step_patches", f"step_patches[{i}].set may only contain 'status'"))
        if workflow is not None and sp.get("step_id") not in workflow_step_ids(workflow):
            errors.append(err("step_patches", f"step_patches[{i}].step_id {sp.get('step_id')!r} does not exist in workflow.yaml"))

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
            )
        )

    return errors


def _validate_dry_run_apply(data, *, workflow, digest_source, phase_state, feature_dir=None):
    errors = []
    operation = data.get("operation")
    tasks_patch = data.get("tasks_patch") or {}
    mode = tasks_patch.get("mode")

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

    # Rule 3: all `expected` values must match current state.
    for i, sp in enumerate((data.get("step_patches") or [])):
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
    # - Re-planning task-id allocation: `entries` must re-declare every
    #   task id already registered in `workflow.yaml` (never drop one), and
    #   any genuinely new id must be allocated above the highest registered
    #   id -- the high-water mark is `max(registered ids)`, read directly
    #   from `workflow`, never a number the validator has to store itself.
    if mode == "replace_all":
        tasks = workflow.get("tasks", {}) or {}
        create_plan_step = workflow_find_step(workflow, "create-plan")
        current_status = create_plan_step.get("status") if create_plan_step else None
        if current_status not in ("pending", "needs_update"):
            errors.append(err("replace-all-not-permitted", f"replace_all requires create-plan step to be pending or needs_update, got {current_status!r}"))
        else:
            if tasks and any((t or {}).get("status") in ("in_progress", "failed") for t in tasks.values()):
                errors.append(err("replace-all-not-permitted", "replace_all requires no task to be in_progress or failed (implementation has started)"))
            else:
                is_replanning = current_status == "needs_update" or workflow_replace_all_spec_change_reentry(
                    workflow, phase_state, feature_dir
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

    return errors


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
        for key, value in set_block.items():
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
        if caps["has_workflow_patch"] and status == "completed" and not workflow_patch:
            errors.append(err("workflow_patch", f"{worker} completed result must include workflow_patch"))
        if status == "completed":
            missing = caps["required_payload"] - set(payload.keys())
            if missing:
                errors.append(err("payload-missing", f"payload is missing required keys: {sorted(missing)}"))
            forbidden_present = caps["forbidden_payload"] & set(payload.keys())
            if forbidden_present:
                errors.append(err("payload-forbidden", f"payload contains keys forbidden for this mode: {sorted(forbidden_present)}"))

    # --- input_revision copy-check + write_policy consistency (5.3) ---
    if envelope is not None:
        envelope_digest = (envelope.get("input_revision") or {}).get("input_digest")
        if envelope_digest is not None and input_revision.get("input_digest") != envelope_digest:
            errors.append(err("input_revision", "input_revision.input_digest was not copied verbatim from the input envelope"))
        write_policy = envelope.get("write_policy") or {}
        targets_by_path = {t.get("path"): t for t in write_policy.get("targets", [])}
        for path, target in targets_by_path.items():
            if target.get("action") not in WRITE_POLICY_ACTIONS:
                errors.append(err("write_policy", f"input envelope write_policy.targets[{path!r}].action is not one of {sorted(WRITE_POLICY_ACTIONS)}"))
        allowed_roots = envelope.get("allowed_write_roots") or []
        for path in written_artifacts:
            if path in targets_by_path:
                continue
            if any(path_is_contained_in_root(path, root) for root in allowed_roots):
                continue
            errors.append(err("write_policy", f"written_artifacts path {path!r} is covered by neither write_policy.targets nor allowed_write_roots"))
        # regenerate co-occurrence (5.4.2)
        artifact_paths = set(written_artifacts)
        for target in write_policy.get("targets", []):
            if target.get("action") == "regenerate" and target.get("path") in artifact_paths:
                source = target.get("source")
                if source not in artifact_paths:
                    errors.append(err("regenerate", f"written_artifacts includes regenerate target {target.get('path')!r} without its source {source!r}"))

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
                ),
                "workflow_patch",
            )
        )
        if feature_dir is not None:
            errors.extend(_validate_task_plans_against_patch(workflow_patch, feature_dir))

    # --- rework_index coverage (5.4.4) ---
    if worker == "rework-planner" and status == "completed":
        errors.extend(
            _validate_rework_index(payload.get("rework_index") or {}, workflow_patch, envelope, feature_dir, baseline_dir)
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


def _validate_task_plans_against_patch(workflow_patch, feature_dir):
    errors = []
    entries = (workflow_patch.get("tasks_patch") or {}).get("entries") or {}
    files_by_task = {}
    for task_id, entry in entries.items():
        files_declared = set(entry.get("files") or [])
        files_by_task[task_id] = files_declared
        plan_rel = entry.get("plan")
        if not plan_rel:
            continue
        plan_path, path_error = _resolve_contained_relative_path(feature_dir, plan_rel)
        if path_error is not None:
            errors.append(err("task-plan-path", f"{task_id}: {path_error}"))
            continue
        if not plan_path.is_file():
            errors.append(err("task-plan-missing", f"{task_id}: plan file {plan_path} not found"))
            continue
        try:
            plan_size = plan_path.stat().st_size
        except OSError as exc:
            errors.append(err("task-plan-missing", f"{task_id}: cannot stat plan file {plan_path}: {exc}"))
            continue
        if plan_size > MAX_PLAN_READ_BYTES:
            errors.append(
                err(
                    "task-plan-too-large",
                    f"{task_id}: plan file {plan_path} is {plan_size} bytes, exceeding the {MAX_PLAN_READ_BYTES} byte limit",
                )
            )
            continue
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
        if not task_plan_has_acceptance_criteria(plan_text):
            errors.append(err("task-plan-acceptance-criteria", f"{task_id}: plan lacks a non-empty Acceptance Criteria (MANDATORY) section"))

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


def _validate_rework_index(rework_index, workflow_patch, envelope, feature_dir, baseline_dir):
    errors = []
    verification_index = (envelope or {}).get("verification_index") or {}

    # bs10 (round 2, validator half): without a baseline directory there is
    # nothing to diff VERIFICATION.md against, so "new" cannot be verified --
    # the previous fallback ("the identifier exists in the current document")
    # degrades to trusting the rework-planner's own claim, since the planner
    # is the one that just wrote that document. `new_ids_in_doc` is therefore
    # only ever computed when a baseline IS supplied; the per-task loop below
    # turns a declared `new_scenarios` with no baseline into a hard error
    # instead of silently accepting it.
    new_ids_in_doc = None
    if feature_dir is not None and baseline_dir is not None:
        vpath = feature_dir / "VERIFICATION.md"
        if vpath.is_file():
            after_ids = extract_verification_scenario_ids(vpath.read_text(encoding="utf-8"))
            bpath = baseline_dir / "VERIFICATION.md"
            before_ids = extract_verification_scenario_ids(bpath.read_text(encoding="utf-8")) if bpath.is_file() else set()
            new_ids_in_doc = after_ids - before_ids

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
        covered = ri.get("covered_by_existing") or []
        new_sc = ri.get("new_scenarios") or []
        if not covered and not new_sc:
            errors.append(err("rework-index", f"{task_id}: covered_by_existing and new_scenarios are both empty"))
        for cid in covered:
            if cid not in verification_index:
                errors.append(err("rework-index", f"{task_id}: covered_by_existing {cid!r} not in verification_index"))
        if new_sc and baseline_dir is None:
            errors.append(
                err(
                    "rework-index",
                    f"{task_id}: new_scenarios is declared but no --baseline-dir was supplied; "
                    "the claim that these scenarios are new (rather than pre-existing) cannot be "
                    "verified against a VERIFICATION.md diff",
                )
            )
        elif new_ids_in_doc is not None:
            for nid in new_sc:
                if nid not in new_ids_in_doc:
                    errors.append(err("rework-index", f"{task_id}: new_scenarios {nid!r} is not a new VERIFICATION.md scenario"))
        if new_sc and not set(new_sc).issubset(tests_append_all):
            errors.append(err("rework-index", f"{task_id}: new_scenarios must also appear in requirements_patch tests_append"))
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
            )
        elif args.kind == "phase-state":
            errors = validate_phase_state(data)
        else:  # pragma: no cover - argparse `choices` already prevents this
            print(f"execution error: unknown --kind {args.kind!r}", file=sys.stderr)
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
