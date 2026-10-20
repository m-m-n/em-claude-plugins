#!/usr/bin/env python3
"""Repository invariant checker for the em-workflow plugin (task0014,
enforcement fixed by task0021).

Renders design-input.md 9.1 (automated verification table) and
IMPLEMENTATION.md D4: seven independent checks assert properties that only
hold once the fully integrated repository exists (agent/dispatch parity,
stale references, gate-ID coverage, `domains` vocabulary parity, the
forbidden `# Task assignment` heading, fixture branch coverage, and
`input_digest` reproducibility). worker-digest-ownership adds two more:
`dispatch_digest_wiring` (every `write_policy` dispatch site registered in
references/artifact-digest.md cites that owner document, and no site names
`git hash-object`) and `worker_digest_stance` (the digest stance of the
prompts and contracts of the envelope workers that write files and have no
Bash). No task worktree contains that integrated
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
# Check 8: worker digest stance (worker-digest-ownership task0004)
# ---------------------------------------------------------------------------
#
# An envelope worker that writes files and has no Bash cannot compute a
# digest, so it must never be told to, and must say in its own prompt that the
# orchestrator owns every digest. Which workers those are is never listed
# here: they are derived from worker-envelope.md's Applicability table and
# from each agent's frontmatter `tools`. Pure function of the root; reads
# fixed paths only (no tree walk, no iter_repo_files).

STANCE_ENVELOPE_PATH = "em-workflow/references/contracts/worker-envelope.md"
STANCE_SPEC_WRITER_CONTRACT_PATH = "em-workflow/references/contracts/spec-writer-contract.md"
STANCE_AGENTS_DIR = "em-workflow/agents"
STANCE_CONTRACTS_DIR = "em-workflow/references/contracts"

# Path tokens and section names a target agent prompt cites (the two owner
# sections of the worker-side stance).
ENVELOPE_CITATION_PATH = "references/contracts/worker-envelope.md"
ENVELOPE_SECTION_NAME = "`written_artifacts` reporting"
SPEC_WRITER_CITATION_PATH = "references/contracts/spec-writer-contract.md"
SPEC_WRITER_SECTION_NAME = "Who verifies `expect_digest`"

# The stance sentence each owner section must keep (whitespace-normalized).
ENVELOPE_OWNER_SENTENCE = "The worker does not compute digests"
SPEC_WRITER_OWNER_SENTENCE = "A worker never returns `blocked` because it cannot compute a digest."

FILE_WRITING_TOOLS = frozenset({"write", "edit", "multiedit", "notebookedit"})
WORKER_NAME_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")
CONTRACT_CITATION_RE = re.compile(
    r"references/contracts/([A-Za-z0-9][A-Za-z0-9_-]*-contract)\.md"
)
BACKTICK_NAME_RE = re.compile(r"`([^`]*)`")
MARKDOWN_HEADING_RE = re.compile(r"^(#{1,6})[ \t]+(.+?)[ \t]*$")
FENCE_RE = re.compile(r"^\s*(?:```|~~~)")
LIST_MARKER_RE = re.compile(r"^\s*(?:[-*+]|\d+[.)])\s+")
TABLE_SEPARATOR_CELL_RE = re.compile(r"^:?-+:?$")


def _normalize_whitespace(text):
    return " ".join(text.split())


def _markdown_section(text, wanted):
    """Body of the first heading whose text satisfies `wanted(heading_text)`,
    up to the next heading of the same or a higher level; None when no such
    heading exists. Heading-looking lines inside fenced code are ignored."""
    in_fence = False
    level = None
    body = []
    for line in text.replace("\r\n", "\n").split("\n"):
        if FENCE_RE.match(line):
            in_fence = not in_fence
            if level is not None:
                body.append(line)
            continue
        match = None if in_fence else MARKDOWN_HEADING_RE.match(line)
        if match:
            heading_level = len(match.group(1))
            if level is not None and heading_level <= level:
                break
            if level is None and wanted(match.group(2)):
                level = heading_level
                continue
        if level is not None:
            body.append(line)
    return "\n".join(body) if level is not None else None


def _split_table_row(line):
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|") and not stripped.endswith("\\|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in re.split(r"(?<!\\)\|", stripped)]


def _is_table_separator_row(cells):
    return bool(cells) and all(TABLE_SEPARATOR_CELL_RE.match(cell) for cell in cells if cell)


def _applicability_worker_names(envelope_text):
    """(names, problems): the first backticked name of every `Applies` cell of
    the Applicability section's first table, with any annotation ("(new)",
    "(revised)") dropped."""
    section = _markdown_section(
        envelope_text, lambda heading: heading.strip().lower().startswith("applicability")
    )
    if section is None:
        return [], ["worker-envelope.md has no Applicability section"]
    rows = []
    for line in section.split("\n"):
        if line.lstrip().startswith("|"):
            rows.append(_split_table_row(line))
        elif rows:
            break
    if not rows:
        return [], ["worker-envelope.md's Applicability section has no table"]
    header = [re.sub(r"[`*_]", "", cell).strip().lower() for cell in rows[0]]
    if "applies" not in header:
        return [], ["worker-envelope.md's Applicability table has no `Applies` column"]
    column = header.index("applies")
    names = []
    problems = []
    for cells in rows[1:]:
        if _is_table_separator_row(cells) or column >= len(cells):
            continue
        match = BACKTICK_NAME_RE.search(cells[column])
        if not match:
            continue
        # A trailing annotation may sit inside or outside the backticks.
        name = re.split(r"[\s(]", match.group(1).strip(), maxsplit=1)[0]
        if WORKER_NAME_RE.fullmatch(name):
            names.append(name)
        else:
            problems.append(
                f"worker-envelope.md's Applies column names {match.group(1)!r}, "
                "which is not a plain worker name"
            )
    return names, problems


def _split_tool_entries(value):
    entries = []
    depth = 0
    current = []
    for char in value:
        if char == "(":
            depth += 1
        elif char == ")":
            depth = max(0, depth - 1)
        if char == "," and depth == 0:
            entries.append("".join(current))
            current = []
        else:
            current.append(char)
    entries.append("".join(current))
    return [entry.strip().strip("'\"") for entry in entries if entry.strip()]


def _frontmatter_tools(agent_text):
    """The frontmatter `tools` entries (comma list, flow list, or block list),
    or None when there is no frontmatter or no `tools` key."""
    lines = agent_text.replace("\r\n", "\n").split("\n")
    if not lines or lines[0].strip() != "---":
        return None
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return None
    frontmatter = lines[1:end]
    for index, line in enumerate(frontmatter):
        match = re.match(r"^tools\s*:\s*(.*?)\s*$", line)
        if not match:
            continue
        value = match.group(1)
        if value:
            return _split_tool_entries(value.strip("[]"))
        entries = []
        for following in frontmatter[index + 1 :]:
            item = re.match(r"^\s*-\s*(.+?)\s*$", following)
            if item:
                entries.append(item.group(1).strip("'\""))
            elif following.strip():
                break
        return entries
    return None


def _tool_name(entry):
    return entry.split("(", 1)[0].strip().lower()


def _derive_digest_stance_targets(root):
    """(workers, problems). `workers` is the sorted target-worker list;
    `problems` are human-readable reasons the derivation is incomplete (no
    envelope document, no Applicability table, an `Applies` name without an
    agent file, ...)."""
    envelope_text = read_text(os.path.join(root, *STANCE_ENVELOPE_PATH.split("/")))
    if envelope_text is None:
        return [], [f"{STANCE_ENVELOPE_PATH}: not found or unreadable"]
    names, problems = _applicability_worker_names(envelope_text)
    workers = set()
    for name in names:
        agent_rel = f"{STANCE_AGENTS_DIR}/{name}.md"
        agent_text = read_text(os.path.join(root, *agent_rel.split("/")))
        if agent_text is None:
            problems.append(
                f"{agent_rel}: not found or unreadable (listed in worker-envelope.md's "
                "Applies column)"
            )
            continue
        tools = _frontmatter_tools(agent_text)
        if tools is None:
            continue
        tool_names = {_tool_name(entry) for entry in tools}
        if tool_names & FILE_WRITING_TOOLS and "bash" not in tool_names:
            workers.add(name)
    return sorted(workers), problems


def derive_digest_stance_workers(root):
    """Sorted names of the envelope workers (worker-envelope.md's Applicability
    table, `Applies` column) whose agent frontmatter `tools` holds a
    file-writing tool and no Bash entry in any form. Nothing is hard-coded."""
    workers, _problems = _derive_digest_stance_targets(root)
    return workers


# --- citations -------------------------------------------------------------


def _paragraphs(text):
    """Blank-line-delimited blocks with whitespace normalized, so a line break
    inside a block never matters."""
    blocks = re.split(r"\n[ \t]*\n", text.replace("\r\n", "\n"))
    return [_normalize_whitespace(block) for block in blocks if block.strip()]


def _paragraph_cites(paragraphs, path_token, section_name):
    return any(path_token in para and section_name in para for para in paragraphs)


# --- worker-directed digest instruction ------------------------------------

_ASCII_WORD_BEFORE = r"(?<![A-Za-z0-9_])"
_ASCII_WORD_AFTER = r"(?![A-Za-z0-9_])"
DIGEST_TERM_RE = re.compile(
    _ASCII_WORD_BEFORE
    + r"(?:sha-?256(?:sum)?|expect_digest|digests?|hash(?:es|ed|ing)?)"
    + _ASCII_WORD_AFTER
    + "|ハッシュ|ダイジェスト",
    re.IGNORECASE,
)
_VERB_BASE = r"(?:re-?)?(?:compute|calculate|hash|verify|compare)"
_VERB_ANY = (
    r"(?:re-?)?(?:comput(?:e|es|ed|ing)|calculat(?:e|es|ed|ing)|hash(?:es|ed|ing)?"
    r"|verif(?:y|ies|ied|ying)|compar(?:e|es|ed|ing))"
)
CHECK_VERB_RE = re.compile(
    _ASCII_WORD_BEFORE + _VERB_ANY + _ASCII_WORD_AFTER + "|計算|照合|比較|検証",
    re.IGNORECASE,
)
NEGATION_RE = re.compile(
    _ASCII_WORD_BEFORE
    + r"(?:not|never|no|cannot|without|neither|nor)"
    + _ASCII_WORD_AFTER
    + r"|n['’]t"
    + _ASCII_WORD_AFTER
    + "|しない|しません|行わない|せず|ならない|禁止|不要",
    re.IGNORECASE,
)
ORCHESTRATOR_RE = re.compile(r"orchestrator|オーケストレーター", re.IGNORECASE)
IMPERATIVE_RE = re.compile(
    r"^(?:(?:always|also|then|first|next|finally|simply|just|please|again)\s+)*"
    + _VERB_BASE
    + _ASCII_WORD_AFTER,
    re.IGNORECASE,
)
JAPANESE_IMPERATIVE_RE = re.compile(
    "(?:計算|照合|比較|検証)(?:すること|せよ|しろ|しなさい|してください|して下さい|すべき|する必要がある)"
)
CLAUSE_BOUNDARY_RE = re.compile(r",\s*|\s+(?:and\s+then|and|then|or)\s+", re.IGNORECASE)
SENTENCE_BOUNDARY_RE = re.compile(
    r"(?<=[.!?])[\"')\]]*\s+|(?<=[。！？])|[;；]\s*"
)
ABBREVIATION_RE = re.compile(r"\b(?:e\.g|i\.e|etc|vs|cf)\.", re.IGNORECASE)
YAML_KEY_PREFIX_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_-]*:\s*")


def _prose_segments(text):
    """Fragments of `text` that never straddle a blank line, heading, list
    item, table cell, frontmatter line or fenced-code line. Line breaks inside
    a fragment are joined with spaces, so the verdict never depends on where a
    paragraph was wrapped."""
    lines = text.replace("\r\n", "\n").split("\n")
    segments = []
    buffer = []

    def flush():
        if buffer:
            segments.append(" ".join(buffer))
            buffer.clear()

    index = 0
    if lines and lines[0].strip() == "---":
        end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
        if end is not None:
            for line in lines[1:end]:
                value = YAML_KEY_PREFIX_RE.sub("", line.strip())
                if value:
                    segments.append(value)
            index = end + 1
    in_fence = False
    for raw in lines[index:]:
        stripped = raw.strip()
        if FENCE_RE.match(raw):
            flush()
            in_fence = not in_fence
            continue
        if not stripped:
            flush()
        elif in_fence:
            flush()
            segments.append(stripped)
        elif MARKDOWN_HEADING_RE.match(stripped):
            flush()
            segments.append(MARKDOWN_HEADING_RE.match(stripped).group(2))
        elif stripped.startswith("|"):
            flush()
            cells = _split_table_row(stripped)
            if not _is_table_separator_row(cells):
                segments.extend(cell for cell in cells if cell)
        elif LIST_MARKER_RE.match(raw):
            flush()
            buffer.append(LIST_MARKER_RE.sub("", raw, count=1).strip())
        else:
            buffer.append(stripped)
    flush()
    return segments


def _sentences(text):
    sentences = []
    for segment in _prose_segments(text):
        cleaned = _normalize_whitespace(segment).replace("**", "").replace("__", "")
        cleaned = cleaned.replace("`", "")
        cleaned = ABBREVIATION_RE.sub(lambda m: m.group(0).replace(".", "․"), cleaned)
        for part in SENTENCE_BOUNDARY_RE.split(cleaned):
            part = part.replace("․", ".").strip()
            if part:
                sentences.append(part)
    return sentences


def _worker_subject_re(worker_names):
    names = sorted({name for name in worker_names if name}, key=len, reverse=True)
    name_alternatives = "".join(f"|{re.escape(name)}" for name in names)
    subject = (
        r"(?:(?:the|this|that|a|an|each|every|any)\s+(?:worker|agent)|you"
        + name_alternatives
        + r")"
    )
    return (
        re.compile(rf"^{subject}(?![A-Za-z0-9_-])", re.IGNORECASE),
        re.compile(
            rf"^(?:この|その)?(?:worker|agent|ワーカー|エージェント{name_alternatives})\s*(?:は|が)",
            re.IGNORECASE,
        ),
    )


def _is_worker_directed_digest_instruction(sentence, worker_subject_res):
    if not DIGEST_TERM_RE.search(sentence) or not CHECK_VERB_RE.search(sentence):
        return False
    if NEGATION_RE.search(sentence) or ORCHESTRATOR_RE.search(sentence):
        return False
    if JAPANESE_IMPERATIVE_RE.search(sentence):
        return True
    # Addressed to the worker: a clause (the sentence itself, or what follows
    # a leading clause that ends in a comma or a coordinator) that opens with
    # an imperative check verb, or with the worker as its subject.
    body = sentence.lstrip("\"'“”‘’([ ")
    starts = [0] + [match.end() for match in CLAUSE_BOUNDARY_RE.finditer(body)]
    for start in starts:
        clause = body[start:].lstrip("\"'“”‘’([ ")
        if IMPERATIVE_RE.match(clause):
            return True
        if any(subject_re.match(clause) for subject_re in worker_subject_res):
            return True
    return False


def find_worker_directed_digest_instructions(text, worker_names=()):
    """Sentences of `text` that tell the worker to compute, hash, verify or
    compare a digest. A sentence qualifies when it carries a digest term, a
    check verb, is addressed to the worker (an imperative clause, or a clause
    whose subject is the worker, "you", or one of `worker_names`), carries no
    negation and does not name the orchestrator."""
    worker_subject_res = _worker_subject_re(worker_names)
    return [
        sentence
        for sentence in _sentences(text)
        if _is_worker_directed_digest_instruction(sentence, worker_subject_res)
    ]


# --- the check -------------------------------------------------------------


def _check_owner_sentence(root, rel_path, heading, sentence, offenders):
    text = read_text(os.path.join(root, *rel_path.split("/")))
    if text is None:
        offenders.append(f"{rel_path}: not found or unreadable (owner of the digest stance)")
        return
    section = _markdown_section(text, lambda h: _normalize_whitespace(h) == heading)
    if section is None:
        offenders.append(f'{rel_path}: section "{heading}" not found')
    elif _normalize_whitespace(sentence) not in _normalize_whitespace(section):
        offenders.append(
            f'{rel_path}: section "{heading}" lacks the stance sentence "{sentence}"'
        )


def check_worker_digest_stance(root):
    name = "worker_digest_stance"
    workers, offenders = _derive_digest_stance_targets(root)
    if not workers:
        offenders.append(
            "no target workers derived: no worker named in the Applies column of "
            f"{STANCE_ENVELOPE_PATH}'s Applicability table has a file-writing tool "
            "and no Bash in its agent frontmatter"
        )

    scanned_contracts = {}
    for worker in workers:
        agent_rel = f"{STANCE_AGENTS_DIR}/{worker}.md"
        prompt = read_text(os.path.join(root, *agent_rel.split("/")))
        if prompt is None:
            offenders.append(f"{worker} ({agent_rel}): not found or unreadable")
            continue
        paragraphs = _paragraphs(prompt)
        if not _paragraph_cites(paragraphs, ENVELOPE_CITATION_PATH, ENVELOPE_SECTION_NAME):
            offenders.append(
                f'{worker} ({agent_rel}): lacks citation (i): {ENVELOPE_CITATION_PATH} and '
                f'"{ENVELOPE_SECTION_NAME}" in one paragraph'
            )
        if not _paragraph_cites(paragraphs, SPEC_WRITER_CITATION_PATH, SPEC_WRITER_SECTION_NAME):
            offenders.append(
                f'{worker} ({agent_rel}): lacks citation (ii): {SPEC_WRITER_CITATION_PATH} and '
                f'"{SPEC_WRITER_SECTION_NAME}" in one paragraph'
            )

        cited = sorted(set(CONTRACT_CITATION_RE.findall(prompt)))
        if not cited:
            offenders.append(
                f"{worker} ({agent_rel}): cites no references/contracts/*-contract.md"
            )
        for contract in cited:
            contract_rel = f"{STANCE_CONTRACTS_DIR}/{contract}.md"
            if contract not in scanned_contracts:
                scanned_contracts[contract] = read_text(os.path.join(root, *contract_rel.split("/")))
            contract_text = scanned_contracts[contract]
            if contract_text is None:
                offenders.append(
                    f"{contract_rel}: not found or unreadable (cited by {worker})"
                )
            elif ENVELOPE_CITATION_PATH not in contract_text:
                offenders.append(
                    f"{contract_rel}: cited by {worker} but does not cite {ENVELOPE_CITATION_PATH}"
                )

        for sentence in find_worker_directed_digest_instructions(prompt, workers):
            offenders.append(
                f"{worker} ({agent_rel}): worker-directed digest instruction: {sentence!r}"
            )

    for contract, contract_text in sorted(scanned_contracts.items()):
        if contract_text is None:
            continue
        subject_names = set(workers) | {contract, contract.rsplit("-contract", 1)[0]}
        for sentence in find_worker_directed_digest_instructions(contract_text, subject_names):
            offenders.append(
                f"{STANCE_CONTRACTS_DIR}/{contract}.md: worker-directed digest instruction: "
                f"{sentence!r}"
            )

    _check_owner_sentence(
        root, STANCE_ENVELOPE_PATH, ENVELOPE_SECTION_NAME, ENVELOPE_OWNER_SENTENCE, offenders
    )
    _check_owner_sentence(
        root,
        STANCE_SPEC_WRITER_CONTRACT_PATH,
        SPEC_WRITER_SECTION_NAME,
        SPEC_WRITER_OWNER_SENTENCE,
        offenders,
    )
    return CheckResult(name, not offenders, offenders)


# ---------------------------------------------------------------------------
# Check: dispatch digest wiring (worker-digest-ownership task0002, FR3 / FR6 / FR7)
# ---------------------------------------------------------------------------

# The owner document of the artifact digest protocol (path relative to the
# plugin directory em-workflow/) and the one citation token every dispatch
# site carries.
DIGEST_OWNER_DOCUMENT = "references/artifact-digest.md"
DIGEST_OWNER_CITATION = "references/artifact-digest.md"
DIGEST_CALCULATION_HEADING = "Calculation"
DIGEST_REGISTRY_HEADING = "Dispatch sites"
# The two owner sections a dispatch site may cover. Every registered worker
# must be covered for both, across the union of its rows.
DIGEST_COVERS_NAMES = ("Pre-dispatch verification", "Layer 5 recording")
DIGEST_REGISTRY_HEADER = ("Document", "Section", "Worker", "Covers")
# The invocation form the owner's `Calculation` section must name: python3,
# then a double-quoted path ending in scripts/artifact-digest.py.
DIGEST_INVOCATION_RE = re.compile(r'python3\s+"[^"\n]*scripts/artifact-digest\.py"')
# Never named inside a dispatch site's section: the git blob id command is
# not the means of any artifact digest (it stays in the post-dispatch scope
# comparison and in the owner's `Legacy records`).
DIGEST_FORBIDDEN_SITE_TOKEN = "git hash-object"

_MD_FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_MD_HEADING_RE = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.+?)(?:[ \t]+#+)?[ \t]*$")
_AGENT_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def _wiring_markdown_headings(text):
    """[(line_index, level, title)] for every ATX heading outside a fenced
    code block."""
    headings = []
    fence = None  # (char, length) of the open fence
    for index, line in enumerate(text.splitlines()):
        fence_match = _MD_FENCE_RE.match(line)
        if fence_match:
            marker = fence_match.group(1)
            if fence is None:
                fence = (marker[0], len(marker))
            elif marker[0] == fence[0] and len(marker) >= fence[1]:
                fence = None
            continue
        if fence is not None:
            continue
        heading = _MD_HEADING_RE.match(line)
        if heading:
            headings.append((index, len(heading.group(1)), heading.group(2)))
    return headings


def _wiring_markdown_section(text, title):
    """(status, body): the body of the heading whose text equals `title`,
    running to the next heading of the same or a higher level. status is
    "ok", "absent", or "ambiguous" (the title heads more than one section,
    so no single body can be named)."""
    headings = _wiring_markdown_headings(text)
    hits = [i for i, (_idx, _lvl, t) in enumerate(headings) if t == title]
    if not hits:
        return "absent", ""
    if len(hits) > 1:
        return "ambiguous", ""
    lines = text.splitlines()
    start, level, _title = headings[hits[0]]
    end = len(lines)
    for next_index, next_level, _next_title in headings[hits[0] + 1 :]:
        if next_level <= level:
            end = next_index
            break
    return "ok", "\n".join(lines[start + 1 : end])


def _parse_dispatch_registry(body):
    """([(document, section, worker, covers)], [problem]) from the markdown
    table in the `Dispatch sites` section. A row is well-formed when its
    Document, Section and Worker cells each hold exactly one backticked
    token and its Covers cell holds at least one. The header and separator
    rows are skipped; any other row that is not well-formed is a problem."""
    rows = []
    problems = []
    for line in body.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = _split_table_row(line)
        if tuple(cells) == DIGEST_REGISTRY_HEADER:
            continue
        if _is_table_separator_row(cells):
            continue
        tokens = [BACKTICK_SPAN_RE.findall(c) for c in cells]
        if (
            len(cells) != 4
            or any(len(t) != 1 for t in tokens[:3])
            or not tokens[3]
        ):
            problems.append(f"malformed registry row: {line.strip()}")
            continue
        rows.append(
            (
                tokens[0][0].strip(),
                tokens[1][0].strip(),
                tokens[2][0].strip(),
                [t.strip() for t in tokens[3]],
            )
        )
    return rows, problems


def check_dispatch_digest_wiring(root):
    """Every `write_policy` dispatch site cites the digest owner document.

    A pure function of `root` that reads the owner document and the
    documents its `Dispatch sites` registry names, and nothing else (it
    never walks the repository). Flow:

    1. the owner document exists;
    2. its `Calculation` section names a python3 invocation of a
       double-quoted path ending in scripts/artifact-digest.py;
    3. its `Dispatch sites` section holds a registry with at least one row,
       and every owner section a row can cover exists in the owner;
    4. for each row, the named document exists under em-workflow/, a heading
       equal to `Section` exists exactly once, and that section (to the next
       heading of the same or a higher level, whitespace-normalized) holds
       the owner path and every owner section name in `Covers` and does not
       hold `git hash-object`;
    5. for each worker named in the registry, its agent definition exists and
       the union of `Covers` over its rows holds both owner section names.
    """
    name = "dispatch_digest_wiring"
    plugin_dir = os.path.join(root, "em-workflow")
    owner_path = os.path.join(plugin_dir, *DIGEST_OWNER_DOCUMENT.split("/"))
    owner_label = f"em-workflow/{DIGEST_OWNER_DOCUMENT}"

    if not os.path.isfile(owner_path):
        return CheckResult(name, False, [f"owner document not found: {owner_label}"])
    owner_text = read_text(owner_path)
    if owner_text is None:
        return CheckResult(name, False, [f"owner document unreadable: {owner_label}"])

    offenders = []

    # 2. the invocation inside `Calculation`.
    status, calculation = _wiring_markdown_section(owner_text, DIGEST_CALCULATION_HEADING)
    if status != "ok":
        offenders.append(
            f"owner document has no single '{DIGEST_CALCULATION_HEADING}' section ({status})"
        )
    elif not DIGEST_INVOCATION_RE.search(calculation):
        offenders.append(
            f"owner document '{DIGEST_CALCULATION_HEADING}' section names no "
            'python3 "<path>/scripts/artifact-digest.py" invocation'
        )

    # 3. the registry.
    status, registry_body = _wiring_markdown_section(owner_text, DIGEST_REGISTRY_HEADING)
    if status != "ok":
        offenders.append(
            f"owner document has no single '{DIGEST_REGISTRY_HEADING}' section ({status})"
        )
        return CheckResult(name, False, offenders)
    rows, problems = _parse_dispatch_registry(registry_body)
    offenders.extend(problems)
    if not rows:
        offenders.append(
            f"owner document '{DIGEST_REGISTRY_HEADING}' registry has no rows"
        )
        return CheckResult(name, False, offenders)
    for covers_name in DIGEST_COVERS_NAMES:
        covers_status, _body = _wiring_markdown_section(owner_text, covers_name)
        if covers_status != "ok":
            offenders.append(
                f"owner document has no single '{covers_name}' section ({covers_status})"
            )

    # 4. each registry row's site section.
    plugin_real = os.path.realpath(plugin_dir)
    documents = {}  # document token -> text, or None when unusable
    workers = {}  # worker -> union of Covers over its rows
    for document, section, worker, covers in rows:
        label = f"{document} / {section}"
        workers.setdefault(worker, set()).update(covers)

        unknown = [c for c in covers if c not in DIGEST_COVERS_NAMES]
        if unknown:
            offenders.append(f"{label}: Covers names unknown owner section(s) {unknown}")

        if document not in documents:
            documents[document] = None
            try:
                site_path = os.path.realpath(os.path.join(plugin_dir, document))
            except ValueError:  # e.g. an embedded NUL character
                site_path = None
            inside = (
                site_path is not None
                and not os.path.isabs(document)
                and os.path.commonpath([plugin_real, site_path]) == plugin_real
            )
            if not inside:
                offenders.append(f"{label}: document path escapes the plugin directory")
            elif not os.path.isfile(site_path):
                offenders.append(f"{label}: document not found under em-workflow/")
            else:
                text = read_text(site_path)
                if text is None:
                    offenders.append(f"{label}: document unreadable")
                documents[document] = text
        text = documents[document]
        if text is None:
            continue

        status, site_body = _wiring_markdown_section(text, section)
        if status != "ok":
            offenders.append(f"{label}: heading {section!r} is {status} in the document")
            continue
        flat = " ".join(site_body.split())
        if DIGEST_OWNER_CITATION not in flat:
            offenders.append(f"{label}: missing owner citation {DIGEST_OWNER_CITATION!r}")
        for covers_name in covers:
            if covers_name in DIGEST_COVERS_NAMES and covers_name not in flat:
                offenders.append(f"{label}: missing owner section name {covers_name!r}")
        if DIGEST_FORBIDDEN_SITE_TOKEN in flat:
            offenders.append(f"{label}: names {DIGEST_FORBIDDEN_SITE_TOKEN!r}")

    # 5. each registered worker.
    for worker in sorted(workers):
        if not _AGENT_NAME_RE.match(worker):
            offenders.append(f"worker {worker!r}: not a valid agent name")
            continue
        agent_path = os.path.join(plugin_dir, "agents", f"{worker}.md")
        if not os.path.isfile(agent_path):
            offenders.append(
                f"worker {worker!r}: agent definition not found: em-workflow/agents/{worker}.md"
            )
        for covers_name in DIGEST_COVERS_NAMES:
            if covers_name not in workers[worker]:
                offenders.append(
                    f"worker {worker!r}: no registry row covers {covers_name!r}"
                )

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
        check_dispatch_digest_wiring(root),
        check_worker_digest_stance(root),
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
