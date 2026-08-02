#!/usr/bin/env python3
"""Repository invariant checker for the em-workflow plugin (task0014).

Renders design-input.md 9.1 (automated verification table) and
IMPLEMENTATION.md D4: seven independent checks assert properties that only
hold once the fully integrated repository exists (agent/dispatch parity,
stale references, gate-ID coverage, `domains` vocabulary parity, the
forbidden `# Task assignment` heading, fixture branch coverage, and
`input_digest` reproducibility). No task worktree contains that integrated
state, which is exactly why every check below is a pure function of an
explicit root path: the unit tests exercise them against small synthetic
trees built in temporary directories (tests/test_check_plugin_invariants.py),
and the authoritative run against the real repository happens once, at the
verify phase (recorded in VERIFICATION.md) -- not here.

CLI contract (IMPLEMENTATION.md "Script exit codes"):
    check-plugin-invariants.py <repository-root>
  0 = every check passed
  1 = at least one check failed (machine-readable detail on stdout)
  2 = execution error (missing/invalid root argument, or an unexpected
      exception while running the checks)

PyYAML is a runtime dependency of the em-workflow plugin (IMPLEMENTATION.md
Technology Stack), used here to parse `batch-policies.yaml`'s structured
`gate_policies:` mapping. It is NOT a test dependency -- tests only ever
invoke the check functions or the CLI, never `import yaml` themselves.
"""

import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, field
from typing import List

import yaml


@dataclass
class CheckResult:
    """One check's outcome. `offenders` is always a list of human-readable
    strings naming the specific offending items (AC-3) -- never a bare
    boolean -- and is empty exactly when `passed` is True."""

    name: str
    passed: bool
    offenders: List[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Shared plumbing
# ---------------------------------------------------------------------------

# Noise directories skipped everywhere a check walks the tree. `.claude`
# covers `.claude/worktrees/...` -- nested sibling-task checkouts that would
# otherwise multiply every match when this script is eventually run for real
# against the integration branch (out of scope for this task, but the
# exclusion costs nothing here and avoids that trap).
EXCLUDED_DIR_NAMES = {".git", ".claude", "node_modules", "__pycache__"}

# This script's own source, and its own test file, necessarily contain the
# literal strings check_stale_references() searches for (they are the
# detection targets, spelled out as constants / test fixtures below). Both
# are excluded from that scan so the checker never flags itself.
SELF_EXCLUDED_RELATIVE_PATHS = {
    os.path.join("em-workflow", "scripts", "check-plugin-invariants.py"),
    os.path.join("tests", "test_check_plugin_invariants.py"),
}


def iter_repo_files(root, exclude_paths=frozenset()):
    """Yield (absolute_path, path_relative_to_root) for every file under
    root, skipping EXCLUDED_DIR_NAMES directories and exclude_paths."""
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIR_NAMES]
        for filename in filenames:
            path = os.path.join(dirpath, filename)
            rel = os.path.relpath(path, root)
            if rel in exclude_paths:
                continue
            yield path, rel


def read_text(path):
    """Best-effort UTF-8 text read. Returns None for anything unreadable or
    non-text (binary fixture files, permission errors) -- a check simply
    skips a file it cannot read rather than treating that as an error."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except (UnicodeDecodeError, OSError):
        return None


# ---------------------------------------------------------------------------
# Check 1: agent / dispatch parity (design-input.md 9.1 row 3, AC-4)
# ---------------------------------------------------------------------------

# Matches `subagent_type="em-workflow:implementer"`, `subagent_type:
# em-workflow:implementer` (YAML), single-quoted, etc. Applied to raw file
# text with no fenced-code-block stripping, so a reference written inside a
# ``` example still counts (Test Notes edge case).
SUBAGENT_TYPE_REF_RE = re.compile(
    r'subagent_type\s*[:=]\s*["\']?em-workflow:([A-Za-z0-9_-]+)'
)


def check_agent_dispatch_parity(root):
    name = "agent_dispatch_parity"
    agents_dir = os.path.join(root, "em-workflow", "agents")
    if not os.path.isdir(agents_dir):
        return CheckResult(name, False, [f"agents directory not found: {agents_dir}"])

    definitions = {
        os.path.splitext(fname)[0]
        for fname in os.listdir(agents_dir)
        if fname.endswith(".md")
    }

    referenced = set()
    for path, _rel in iter_repo_files(root, exclude_paths=SELF_EXCLUDED_RELATIVE_PATHS):
        text = read_text(path)
        if text is None:
            continue
        for match in SUBAGENT_TYPE_REF_RE.finditer(text):
            referenced.add(match.group(1))

    undispatched = sorted(definitions - referenced)
    dangling = sorted(referenced - definitions)

    offenders = [f"undispatched definition: {n}" for n in undispatched]
    offenders += [f"dispatch of missing definition: {n}" for n in dangling]
    return CheckResult(name, not offenders, offenders)


# ---------------------------------------------------------------------------
# Check 2: stale references (design-input.md 9.1 row 4)
# ---------------------------------------------------------------------------

STALE_AGENT_NAME = "requirements-spec-creator"
# design-input.md 9.1's own grep pattern for the inline-execution phrase
# this feature replaces with Task-dispatch (skills/develop/SKILL.md today).
STALE_INLINE_PHRASE = "Read してインラインで従う"

# This feature's own design and planning documents legitimately quote both
# terms historically (e.g. describing the problem being fixed, or D6's
# transitional-inconsistency note) -- task0014.md Design section.
STALE_REFERENCES_ALLOWED_PREFIX = os.path.join("feature-docs", "agent-separation")


def check_stale_references(root):
    name = "stale_references"
    offenders = []
    for path, rel in iter_repo_files(root, exclude_paths=SELF_EXCLUDED_RELATIVE_PATHS):
        if rel == STALE_REFERENCES_ALLOWED_PREFIX or rel.startswith(
            STALE_REFERENCES_ALLOWED_PREFIX + os.sep
        ):
            continue
        text = read_text(path)
        if text is None:
            continue
        if STALE_AGENT_NAME in text:
            offenders.append(f"{rel}: contains {STALE_AGENT_NAME!r}")
        if STALE_INLINE_PHRASE in text:
            offenders.append(f"{rel}: contains stale inline-execution phrase")
    return CheckResult(name, not offenders, offenders)


# ---------------------------------------------------------------------------
# Check 3: gate identifier coverage (design-input.md 5.9, 9.1 row 5, AC-5)
# ---------------------------------------------------------------------------

# A gate ID has the shape `<namespace>.<name>` (e.g. `create-spec.
# feature-identity`, `design-system.reclassify`). Extraction is restricted
# to backtick-quoted spans, matching this repository's existing convention
# for citing a gate ID in prose (`` `create-spec.design-system` `` or the
# whole `` `gate_id: rework.spec-change` `` form).
GATE_ID_SHAPE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_-]*\.[A-Za-z][A-Za-z0-9_-]*$")
# Excludes shapes that are really a filename (`workflow.yaml`, `batch-
# policies.yaml`) from being mistaken for a gate ID of the same dotted form.
NON_GATE_ID_SUFFIXES = {
    "yaml", "yml", "json", "md", "py", "js", "ts", "html", "css", "txt", "sh",
}
BACKTICK_SPAN_RE = re.compile(r"`([^`]+)`")
# How far back (characters) a bare `` `namespace.name` `` span is allowed to
# look for a preceding "gate ID" / "gate_id" mention (see PROXIMITY_WINDOW
# rationale below).
PROXIMITY_WINDOW = 120
GATE_MENTION_RE = re.compile(r"gate[_ ]id", re.IGNORECASE)

# design-input.md 5.4.4/5.9: `rework.spec-change` is deliberately never
# given a batch-policies.yaml entry so the unlisted-gate fallback aborts it.
# Excluded from both directions of the comparison (AC-5).
INTENTIONALLY_UNLISTED_GATE_IDS = {"rework.spec-change"}


def extract_gate_ids_from_text(text):
    """A dotted backtick span counts as a gate-ID reference in one of two
    forms, both observed in the existing corpus:

    1. `` `gate_id: <id>` `` -- the whole `gate_id: ...` phrase is inside
       the backticks (rework-task-synthesis.md, contracts).
    2. a bare `` `<id>` `` span shortly after a "gate ID" / "gate_id"
       mention in the surrounding prose (phase-state.md: "present the
       candidates under gate ID\\n   `create-spec.design-system`").

    Without form 2's proximity requirement, ANY dotted-and-hyphenated
    backtick span (`go.mod`, `project.components`, `review.plan` -- package
    manifests and workflow.yaml field paths that happen to share the same
    textual shape) would be misread as a gate ID -- this is what actually
    happens when scanning review-phase.md, and is why the requirement
    exists rather than being extraction with GATE_ID_SHAPE_RE alone."""
    ids = set()
    for match in BACKTICK_SPAN_RE.finditer(text):
        span = match.group(1).strip()
        if span.lower().startswith("gate_id:"):
            candidate = span.split(":", 1)[1].strip()
        elif GATE_ID_SHAPE_RE.match(span):
            preceding = text[max(0, match.start() - PROXIMITY_WINDOW) : match.start()]
            if not GATE_MENTION_RE.search(preceding):
                continue
            candidate = span
        else:
            continue
        if not GATE_ID_SHAPE_RE.match(candidate):
            continue
        suffix = candidate.rsplit(".", 1)[-1].lower()
        if suffix in NON_GATE_ID_SUFFIXES:
            continue
        ids.add(candidate)
    return ids


def find_gate_scan_files(root):
    """The phase protocols and the develop skill (design-input.md 9.1 row
    5's stated scan scope). Covers both the future `references/phases/*.md`
    layout (IMPLEMENTATION.md Layer Structure) and the current individual
    `references/*-phase.md` files, so this stays meaningful under either."""
    paths = []
    phases_dir = os.path.join(root, "em-workflow", "references", "phases")
    if os.path.isdir(phases_dir):
        for fname in sorted(os.listdir(phases_dir)):
            if fname.endswith(".md"):
                paths.append(os.path.join(phases_dir, fname))

    references_dir = os.path.join(root, "em-workflow", "references")
    if os.path.isdir(references_dir):
        for fname in sorted(os.listdir(references_dir)):
            if fname.endswith("-phase.md"):
                paths.append(os.path.join(references_dir, fname))

    develop_skill = os.path.join(root, "em-workflow", "skills", "develop", "SKILL.md")
    if os.path.isfile(develop_skill):
        paths.append(develop_skill)

    return paths


def check_gate_id_coverage(root):
    name = "gate_id_coverage"
    policy_path = os.path.join(root, "em-workflow", "references", "batch-policies.yaml")
    if not os.path.isfile(policy_path):
        return CheckResult(name, False, [f"batch-policies.yaml not found: {policy_path}"])

    policy_text = read_text(policy_path)
    if policy_text is None:
        return CheckResult(name, False, [f"batch-policies.yaml unreadable: {policy_path}"])

    try:
        policy_data = yaml.safe_load(policy_text) or {}
    except yaml.YAMLError as exc:
        return CheckResult(name, False, [f"batch-policies.yaml is not valid YAML: {exc}"])

    if not isinstance(policy_data, dict) or "gate_policies" not in policy_data:
        return CheckResult(
            name, False, ["batch-policies.yaml has no top-level `gate_policies` key"]
        )
    gate_policies = policy_data["gate_policies"]
    if gate_policies is None:
        # A `gate_policies:` key with no children parses as None (legal
        # YAML for "empty mapping") -- zero policy entries, not malformed.
        gate_policies = {}
    if not isinstance(gate_policies, dict):
        return CheckResult(
            name, False, ["batch-policies.yaml's `gate_policies` key is not a mapping"]
        )
    policy_ids = set(gate_policies.keys())

    scanned_ids = set()
    for path in find_gate_scan_files(root):
        text = read_text(path)
        if text is None:
            continue
        scanned_ids |= extract_gate_ids_from_text(text)

    policy_ids -= INTENTIONALLY_UNLISTED_GATE_IDS
    scanned_ids -= INTENTIONALLY_UNLISTED_GATE_IDS

    missing_from_policy = sorted(scanned_ids - policy_ids)
    unused_in_policy = sorted(policy_ids - scanned_ids)

    offenders = [
        f"referenced but missing from batch-policies.yaml: {gid}" for gid in missing_from_policy
    ]
    offenders += [
        f"in batch-policies.yaml but never referenced: {gid}" for gid in unused_in_policy
    ]
    return CheckResult(name, not offenders, offenders)


# ---------------------------------------------------------------------------
# Check 4: domains vocabulary parity (design-input.md 5.5.6, 9.1 row 6)
# ---------------------------------------------------------------------------

DOMAINS_MARKER_RE = re.compile(r"^#\s*domains vocabulary\b", re.IGNORECASE)
DOMAINS_HEADING_RE = re.compile(r"^##\s*domains criteria\b", re.IGNORECASE)
LIST_ITEM_TOKEN_RE = re.compile(r"^-\s*`([^`]+)`")


def extract_domains_from_review_rules(text):
    """The `# domains vocabulary (...):` comment block in review-rules.yaml
    (a YAML comment, so it must be read as text -- `yaml.safe_load` drops
    comments entirely). Collection stops at the next `... vocabulary` marker
    line (e.g. `# complexity vocabulary: ...`), which ends the block."""
    tokens = []
    collecting = False
    for line in text.splitlines():
        stripped = line.strip()
        if not collecting:
            if DOMAINS_MARKER_RE.match(stripped):
                collecting = True
            continue
        if not stripped.startswith("#"):
            break
        content = stripped.lstrip("#").strip()
        if not content:
            break
        if "vocabulary" in content.lower():
            break
        tokens.extend(tok.strip() for tok in content.split("/") if tok.strip())
    return set(tokens)


def extract_domains_from_plan_writing(text):
    """The `- \\`value\\` — description.` bullet list under the
    `## domains criteria` heading in skills/plan-writing/SKILL.md."""
    tokens = []
    collecting = False
    for line in text.splitlines():
        stripped = line.strip()
        if not collecting:
            if DOMAINS_HEADING_RE.match(stripped):
                collecting = True
            continue
        if stripped.startswith("##"):
            break
        match = LIST_ITEM_TOKEN_RE.match(stripped)
        if match:
            tokens.append(match.group(1))
    return set(tokens)


def check_domains_vocabulary_parity(root):
    name = "domains_vocabulary_parity"
    review_rules_path = os.path.join(root, "em-workflow", "references", "review-rules.yaml")
    plan_writing_path = os.path.join(
        root, "em-workflow", "skills", "plan-writing", "SKILL.md"
    )

    review_rules_text = read_text(review_rules_path)
    plan_writing_text = read_text(plan_writing_path)

    offenders = []
    if review_rules_text is None:
        offenders.append(f"review-rules.yaml not found or unreadable: {review_rules_path}")
    if plan_writing_text is None:
        offenders.append(
            f"plan-writing/SKILL.md not found or unreadable: {plan_writing_path}"
        )
    if offenders:
        return CheckResult(name, False, offenders)

    review_rules_domains = extract_domains_from_review_rules(review_rules_text)
    plan_writing_domains = extract_domains_from_plan_writing(plan_writing_text)

    only_in_review_rules = sorted(review_rules_domains - plan_writing_domains)
    only_in_plan_writing = sorted(plan_writing_domains - review_rules_domains)

    offenders += [f"in review-rules.yaml only: {d}" for d in only_in_review_rules]
    offenders += [f"in plan-writing/SKILL.md only: {d}" for d in only_in_plan_writing]
    return CheckResult(name, not offenders, offenders)


# ---------------------------------------------------------------------------
# Check 5: forbidden `# Task assignment` heading (NFR7, 9.1 row implicit)
# ---------------------------------------------------------------------------

# Byte-identical to queue_launch_guard.py / queue_agent_index.py /
# queue_failure_net.py's ASSIGNMENT_HEADER_RE: the exact fallback heading
# those hooks accept when `subagent_type` is absent (NFR7).
TASK_ASSIGNMENT_HEADING_RE = re.compile(r"(?m)^# Task assignment\s*$")


def check_forbidden_task_assignment_heading(root):
    name = "forbidden_task_assignment_heading"
    agents_dir = os.path.join(root, "em-workflow", "agents")
    if not os.path.isdir(agents_dir):
        return CheckResult(name, False, [f"agents directory not found: {agents_dir}"])

    offenders = []
    for fname in sorted(os.listdir(agents_dir)):
        if not fname.endswith(".md"):
            continue
        text = read_text(os.path.join(agents_dir, fname))
        if text is None:
            continue
        if TASK_ASSIGNMENT_HEADING_RE.search(text):
            offenders.append(fname)
    return CheckResult(name, not offenders, offenders)


# ---------------------------------------------------------------------------
# Check 6: fixture branch coverage (design-input.md 5.11.5, 9.1 row 2)
# ---------------------------------------------------------------------------

# The distinctive header cell of design-input.md 5.11.5's coverage table
# (`| kind | 網羅すべき分岐 |`) -- anchoring on this phrase rather than a
# section number keeps the parser independent of the document's numbering.
FIXTURE_TABLE_HEADER_MARKER = "網羅すべき分岐"
TABLE_ROW_FIRST_COLUMN_RE = re.compile(r"^\|\s*`([^`]+)`\s*\|")


def extract_fixture_kinds_from_design(text):
    """The `kind` column values out of design-input.md 5.11.5's fixture
    coverage table -- the five `--kind` values validate-worker-output.py
    (task0008) accepts, each of which the fixture corpus must cover."""
    kinds = []
    in_table = False
    for line in text.splitlines():
        if not in_table:
            if FIXTURE_TABLE_HEADER_MARKER in line:
                in_table = True
            continue
        stripped = line.strip()
        if not stripped.startswith("|"):
            break
        body = stripped.replace("|", "").strip()
        if body and set(body) <= {"-", " "}:
            continue  # header separator row
        match = TABLE_ROW_FIRST_COLUMN_RE.match(stripped)
        if match:
            kinds.append(match.group(1))
    return kinds


def fixture_kind_for_path(rel_path, kind):
    """Whether a fixture path (relative to references/fixtures/) belongs to
    `kind`, either by living under a same-named subdirectory or by its
    filename being prefixed with `kind` followed by `.`, `-`, or `_`. A file
    matching neither carries no recognizable kind marker at all and counts
    toward no kind (Test Notes edge case: a non-conventional filename)."""
    parts = rel_path.split(os.sep)
    if parts[0] == kind:
        return True
    filename = parts[-1]
    return any(filename.startswith(kind + sep) for sep in (".", "-", "_"))


def check_fixture_branch_coverage(root):
    name = "fixture_branch_coverage"
    design_path = os.path.join(root, "feature-docs", "agent-separation", "design-input.md")
    text = read_text(design_path)
    if text is None:
        return CheckResult(name, False, [f"design-input.md not found or unreadable: {design_path}"])

    kinds = extract_fixture_kinds_from_design(text)
    if not kinds:
        return CheckResult(
            name,
            False,
            ["no fixture coverage table found in design-input.md (5.11.5 marker missing)"],
        )

    fixtures_dir = os.path.join(root, "em-workflow", "references", "fixtures")
    existing_files = []
    if os.path.isdir(fixtures_dir):
        for dirpath, _dirnames, filenames in os.walk(fixtures_dir):
            for fname in filenames:
                rel = os.path.relpath(os.path.join(dirpath, fname), fixtures_dir)
                existing_files.append(rel)

    missing = [
        k for k in kinds if not any(fixture_kind_for_path(f, k) for f in existing_files)
    ]
    return CheckResult(name, not missing, sorted(missing))


# ---------------------------------------------------------------------------
# Check 7: input_digest reproducibility (design-input.md 5.0 R1, 9.1 row 8)
# ---------------------------------------------------------------------------


def compute_input_digest(digest_source):
    """design-input.md 5.0 R1's normalization rule: sort keys ascending,
    separators `(",", ":")`, non-ASCII not escaped, then sha256 the UTF-8
    bytes. Reused verbatim by the orchestrator and by workers -- this is the
    one place the rule is expressed in code for this check to exercise."""
    normalized = json.dumps(
        digest_source, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def check_digest_reproducibility():
    """Builds its own small input set rather than depending on a live
    feature (task0014.md Design/Test Notes -- TDD-awkward area): proves
    recomputation over the identical input is stable, AND that the
    normalization is insensitive to construction-order-only differences
    (the actual point of `sort_keys=True` in R1's rule)."""
    name = "digest_reproducibility"

    source_a = {
        "worker": "implementation-planner",
        "mode": "interactive",
        "digest_inputs": {
            "feature-docs/example/SPEC.md": "sha256:aaaaaaaa",
            "feature-docs/example/REQUIREMENTS.md": "sha256:bbbbbbbb",
        },
        "value_inputs": {"task_description": None},
        "answers_digest": "sha256:cccccccc",
        "write_policy_digest": "sha256:dddddddd",
    }
    # Same logical content as source_a, keys inserted in a different order
    # and via a different construction path -- proving the *normalization*,
    # not mere object identity, is what is reproducible.
    source_b = {
        "write_policy_digest": "sha256:dddddddd",
        "answers_digest": "sha256:cccccccc",
        "value_inputs": {"task_description": None},
        "digest_inputs": {
            "feature-docs/example/REQUIREMENTS.md": "sha256:bbbbbbbb",
            "feature-docs/example/SPEC.md": "sha256:aaaaaaaa",
        },
        "mode": "interactive",
        "worker": "implementation-planner",
    }

    digest_a1 = compute_input_digest(source_a)
    digest_a2 = compute_input_digest(source_a)
    digest_b = compute_input_digest(source_b)

    offenders = []
    if digest_a1 != digest_a2:
        offenders.append("recomputation over the same input changed the digest")
    if digest_a1 != digest_b:
        offenders.append("key-order-only variation changed the digest")
    return CheckResult(name, not offenders, offenders)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def run_all_checks(root):
    return [
        check_agent_dispatch_parity(root),
        check_stale_references(root),
        check_gate_id_coverage(root),
        check_domains_vocabulary_parity(root),
        check_forbidden_task_assignment_heading(root),
        check_fixture_branch_coverage(root),
        check_digest_reproducibility(),
    ]


def format_report(results):
    """Human-readable report (the verify-phase reader is a person, per
    task0014.md Design section)."""
    lines = []
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        lines.append(f"[{status}] {result.name}")
        for offender in result.offenders:
            lines.append(f"    - {offender}")
    return "\n".join(lines)


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if len(argv) != 1:
        print("usage: check-plugin-invariants.py <repository-root>", file=sys.stderr)
        return 2

    root = argv[0]
    if not os.path.isdir(root):
        print(f"ERROR: repository root does not exist or is not a directory: {root}", file=sys.stderr)
        return 2

    try:
        results = run_all_checks(root)
    except Exception as exc:  # noqa: BLE001 -- deliberately broad: anything
        # unexpected here is an execution error (exit 2), not a check
        # failure (exit 1); a check failure is always reported via a
        # CheckResult, never via a raised exception.
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    print(format_report(results))
    return 0 if all(result.passed for result in results) else 1


if __name__ == "__main__":
    sys.exit(main())
