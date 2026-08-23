#!/usr/bin/env python3
"""Repository invariant checker for the em-workflow plugin (task0014,
enforcement fixed by task0021).

Renders design-input.md 9.1 (automated verification table) and
IMPLEMENTATION.md D4: seven independent checks assert properties that only
hold once the fully integrated repository exists (agent/dispatch parity,
stale references, gate-ID coverage, `domains` vocabulary parity, the
forbidden `# Task assignment` heading, fixture branch coverage, and
`input_digest` reproducibility). No task worktree contains that integrated
state, which is exactly why every check below is a pure function of an
explicit root path: the unit tests exercise them against small synthetic
trees built in temporary directories (tests/test_check_plugin_invariants.py)
AND, since task0021, against the real repository root once every other task
has merged (reviews/round1.yaml finding as2) -- that repository-level case is
the run this docstring used to defer entirely to the verify phase; it now
runs here too, in addition to the verify-phase run recorded in
VERIFICATION.md.

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
# against the integration branch. `fixtures` is this feature's own generated
# fixture corpus (references/fixtures/, ~190 files as of this task) -- data
# for validate-worker-output.py's tests, never a dispatch reference or a
# stale-name mention (as22: reading it twice, once per text check, was pure
# waste). `vendor`/`dist`/`build` are the usual dependency/build directories
# named by design (none exist in this repository today; excluded so a future
# one never gets swept for free).
EXCLUDED_DIR_NAMES = {
    ".git",
    ".claude",
    "node_modules",
    "__pycache__",
    "fixtures",
    "vendor",
    "dist",
    "build",
}

# This script's own source contains the literal strings check_stale_
# references() searches for (they are the detection targets, spelled out as
# constants below) -- excluded so the checker never flags itself. The test
# file is additionally listed for the same reason it always was: it is
# scanned for agent_dispatch_parity's `subagent_type=...` extraction too
# (SCAN_ROOTS covers "tests"), and its fixture literals name fictional
# agents ("orphan", "ghost", ...) that must never be read as real dispatch
# references against this repository's actual em-workflow/agents/.
SELF_EXCLUDED_RELATIVE_PATHS = {
    os.path.join("em-workflow", "scripts", "check-plugin-invariants.py"),
    os.path.join("tests", "test_check_plugin_invariants.py"),
}

# Roots (relative to the repository root) that agent_dispatch_parity and
# stale_references ever need to read (as22): the plugin itself, plus this
# feature's own historical/process records, whose full rationale sits next
# to STALE_REFERENCES_ALLOWED_ROOTS below. Nothing outside these four names
# (other plugins, the marketplace root, the singular `test/` directory) has
# ever matched either check's patterns.
SCAN_ROOTS = ("em-workflow", "feature-docs", "test-docs", "tests")

# Extensions either check's patterns can ever match against -- prose and
# code, never the generated JSON fixtures or other binary/asset formats
# (as22).
SCAN_EXTENSIONS = (".md", ".py", ".yaml", ".yml")

# Bound on an individual file read (as22 "bound individual reads"). No
# legitimate target of either check -- hand-authored prose, code, or YAML --
# approaches this size; a file that does is skipped outright (treated as
# "unreadable") rather than decoded partially, which could otherwise cut a
# multi-byte UTF-8 sequence at the boundary or silently miss a match past
# the cutoff.
MAX_READ_BYTES = 2_000_000


def _first_path_segment(rel):
    """The top-level directory name of a root-relative path, e.g.
    "feature-docs" out of "feature-docs/agent-separation/design-input.md"."""
    return rel.split(os.sep, 1)[0]


def iter_repo_files(root, scan_roots=None, extensions=None, exclude_paths=frozenset()):
    """Yield (absolute_path, path_relative_to_root) for every file under
    root, skipping EXCLUDED_DIR_NAMES directories and exclude_paths.

    scan_roots, if given, restricts the walk to those top-level directories
    (relative to root) instead of the whole tree -- e.g. SCAN_ROOTS -- so a
    directory neither check can ever match against (another plugin, a
    generated fixture corpus, ...) is never walked at all (as22).

    extensions, if given, restricts yielded files to those whose name ends
    in one of the given suffixes -- skips binary and irrelevant text formats
    no check here ever needs to read.
    """
    walk_roots = [root] if scan_roots is None else [os.path.join(root, r) for r in scan_roots]
    for walk_root in walk_roots:
        if not os.path.isdir(walk_root):
            continue
        for dirpath, dirnames, filenames in os.walk(walk_root):
            dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIR_NAMES]
            for filename in filenames:
                if extensions is not None and not filename.endswith(tuple(extensions)):
                    continue
                path = os.path.join(dirpath, filename)
                rel = os.path.relpath(path, root)
                if rel in exclude_paths:
                    continue
                yield path, rel


def read_text(path):
    """Best-effort UTF-8 text read. Returns None for anything unreadable,
    non-text (binary fixture files, permission errors), or larger than
    MAX_READ_BYTES (as22) -- a check simply skips a file it cannot or need
    not read rather than treating that as an error."""
    try:
        if os.path.getsize(path) > MAX_READ_BYTES:
            return None
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
    agent_result, _stale_result = _agent_dispatch_and_stale_reference_scan(root)
    return agent_result


# ---------------------------------------------------------------------------
# Check 2: stale references (design-input.md 9.1 row 4)
# ---------------------------------------------------------------------------

STALE_AGENT_NAME = "requirements-spec-creator"
# design-input.md 9.1's own grep pattern for the inline-execution phrase
# this feature replaces with Task-dispatch (skills/develop/SKILL.md today).
STALE_INLINE_PHRASE = "Read してインラインで従う"

# Top-level directories (relative to the repository root) that legitimately
# still name the deleted agent or the stale inline-execution phrase, and
# must therefore never be excused wholesale -- narrowed instead to exactly
# these two categories (task0021, reviews/round1.yaml finding as2):
#
# - "feature-docs": every feature's planning/design/review record, past or
#   present, is history by construction -- not just this feature's own
#   (design-input.md, task plans, retrospectives quoting the name they
#   describe replacing), but ANY other completed feature's records too
#   (e.g. feature-docs/integration-worktree-orchestration/**), which is
#   exactly what the previous single-feature prefix missed.
# - "test-docs" / "tests": a test (or its recorded test-run evidence) that
#   asserts the deleted name's absence must contain that name as a literal
#   to search for -- that is the whole point of the assertion.
#
# Deliberately NOT included: "em-workflow" (the plugin directory itself --
# the one thing this check exists to police) and anything else at the
# repository root (another plugin, the marketplace root, `test/`) that has
# never had a legitimate reason to mention either string.
STALE_REFERENCES_ALLOWED_ROOTS = frozenset({"feature-docs", "test-docs", "tests"})


def check_stale_references(root):
    _agent_result, stale_result = _agent_dispatch_and_stale_reference_scan(root)
    return stale_result


def _agent_dispatch_and_stale_reference_scan(root):
    """Computes agent_dispatch_parity and stale_references together from a
    single tree traversal (task0021, reviews/round1.yaml finding as22: the
    two checks previously walked and read the repository independently,
    doubling both costs). Each check function above still calls this and
    discards the half it does not need, so both remain independently
    callable with correct results on their own (task0014's AC-2) -- the
    single-traversal win applies when both are needed together, which is
    exactly what run_all_checks() does below instead of calling the two
    check functions separately."""
    agent_name = "agent_dispatch_parity"
    stale_name = "stale_references"

    agents_dir = os.path.join(root, "em-workflow", "agents")
    if os.path.isdir(agents_dir):
        definitions = {
            os.path.splitext(fname)[0]
            for fname in os.listdir(agents_dir)
            if fname.endswith(".md")
        }
        agent_result = None
    else:
        definitions = None
        agent_result = CheckResult(agent_name, False, [f"agents directory not found: {agents_dir}"])

    referenced = set()
    stale_offenders = []
    for path, rel in iter_repo_files(
        root,
        scan_roots=SCAN_ROOTS,
        extensions=SCAN_EXTENSIONS,
        exclude_paths=SELF_EXCLUDED_RELATIVE_PATHS,
    ):
        text = read_text(path)
        if text is None:
            continue

        for match in SUBAGENT_TYPE_REF_RE.finditer(text):
            referenced.add(match.group(1))

        if _first_path_segment(rel) in STALE_REFERENCES_ALLOWED_ROOTS:
            continue
        if STALE_AGENT_NAME in text:
            stale_offenders.append(f"{rel}: contains {STALE_AGENT_NAME!r}")
        if STALE_INLINE_PHRASE in text:
            stale_offenders.append(f"{rel}: contains stale inline-execution phrase")

    if agent_result is None:
        undispatched = sorted(definitions - referenced)
        dangling = sorted(referenced - definitions)
        offenders = [f"undispatched definition: {n}" for n in undispatched]
        offenders += [f"dispatch of missing definition: {n}" for n in dangling]
        agent_result = CheckResult(agent_name, not offenders, offenders)

    stale_result = CheckResult(stale_name, not stale_offenders, stale_offenders)
    return agent_result, stale_result


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
# given a batch-policies.yaml entry -- in batch it is routed through the
# classification gate (question-resolution.md), not the unlisted-gate
# fallback. Excluded from both directions of the comparison (AC-5).
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


def _iter_plugin_files(root, exclude_paths=frozenset()):
    """Every file under the plugin directory (em-workflow/), skipping the
    usual noise directories, and never yielding a path in `exclude_paths`
    (paths relative to `root`, matching iter_repo_files's exclude_paths
    convention). Used by check_gate_id_coverage's vocabulary scan (task0021
    AC-6): wider than find_gate_scan_files()'s phase-protocol-only scope,
    because a real gate ID can legitimately be declared in a contract, an
    agent prompt, or references/batch-mode.md -- none of which that
    narrower scope visits."""
    plugin_dir = os.path.join(root, "em-workflow")
    if not os.path.isdir(plugin_dir):
        return
    for dirpath, dirnames, filenames in os.walk(plugin_dir):
        dirnames[:] = [d for d in dirnames if d not in EXCLUDED_DIR_NAMES]
        for filename in filenames:
            path = os.path.join(dirpath, filename)
            rel = os.path.relpath(path, root)
            if rel in exclude_paths:
                continue
            yield path


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

    # Direction 1 (AC-6): a policy id counts as referenced wherever its
    # exact string occurs anywhere under the plugin directory, except
    # inside the policy file itself -- being a key in its own policy is not
    # a reference to itself -- and except inside this checker's own source
    # (SELF_EXCLUDED_RELATIVE_PATHS, the same self-exclusion set
    # check_stale_references already maintains, reviews/round2.yaml finding
    # bs11): this script's own comments name gate IDs as examples
    # (`create-spec.design-system`, `design-system.reclassify`), and without
    # this exclusion those two would be reported as referenced even if every
    # other document dropped them. This replaces the "gate ID" / "gate_id"
    # proximity heuristic below for known vocabulary, since that heuristic
    # is exactly what missed six real, unproximate mentions (analyst
    # contract and prompt, batch-mode table, planner prompt, and a
    # create-spec-phase.md table row with no "gate ID" phrase nearby).
    referenced_vocab_ids = set()
    if policy_ids:
        policy_rel = os.path.relpath(policy_path, root)
        exclude_paths = SELF_EXCLUDED_RELATIVE_PATHS | {policy_rel}
        plugin_texts = []
        for path in _iter_plugin_files(root, exclude_paths=exclude_paths):
            text = read_text(path)
            if text is not None:
                plugin_texts.append(text)
        for gid in policy_ids:
            if any(gid in text for text in plugin_texts):
                referenced_vocab_ids.add(gid)

    # Direction 2: an identifier extracted from the narrower phase-protocol
    # scan scope that is not (yet) a policy key at all -- these can only be
    # recognized by shape plus disambiguation (the explicit `gate_id: <id>`
    # form, or bare-span proximity to a "gate ID" mention), since nothing
    # declares them as vocabulary the way a policy key does.
    extracted_ids = set()
    for path in find_gate_scan_files(root):
        text = read_text(path)
        if text is None:
            continue
        extracted_ids |= extract_gate_ids_from_text(text)

    scanned_ids = extracted_ids | referenced_vocab_ids

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
    # agent_dispatch_parity and stale_references come from one shared scan
    # (as22) rather than each check function being invoked separately, which
    # would repeat the identical tree walk and file reads.
    agent_result, stale_result = _agent_dispatch_and_stale_reference_scan(root)
    return [
        agent_result,
        stale_result,
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
