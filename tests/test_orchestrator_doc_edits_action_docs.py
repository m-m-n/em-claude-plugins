"""Document tests for orchestrator-spec-edit-overwrite task0001.

The create-spec action decision of
`em-workflow/references/contracts/spec-writer-contract.md`, section "How the
orchestrator chooses each target's action before dispatch", gives an existing
create-spec target `replace_own` when its current digest equals the last
create-spec output for the path or the last `orchestrator_doc_edits` entry for
the path. Every other existing target takes the digest-mismatch branch. The
`replace_own` row of the action table and section 9 of
`em-workflow/references/phases/create-spec-phase.md` cite that rule and do not
restate it.

Covers task0001's Acceptance Criteria
(feature-docs/orchestrator-spec-edit-overwrite/tasks/task0001.md):

- AC-1 (FR3): the create-spec block, its match rule and its verification.
- AC-2 (FR3, FR5): the no-match routing and "no other condition".
- AC-3 (FR4): the read conditions, the five no-record cases, recorded values.
- AC-4 (FR5): the create-plan part of the owner section stays free of the
  record and keeps its pinned sentences.
- AC-5 (FR6, NFR1): the `replace_own` row of "The `write_policy` actions".
- AC-6 (FR6, NFR2, NFR4): section 9 of create-spec-phase.md cites the owner.
- AC-7 (FR7, NFR3): every presence check fails on a forged copy without its
  token, every absence check fires on a forged copy that carries its token.

Method (the task plan's Test Notes): cut a place out by its heading, paragraph
or bullet, whitespace-normalize, then assert that key tokens are present or
absent. Never a whole-document comparison and never a line-break position.
Standard library only; the helpers are this module's own.
"""

import ast
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"

CONTRACT_PATH = (
    PLUGIN_ROOT / "references" / "contracts" / "spec-writer-contract.md"
)
CREATE_SPEC_PATH = PLUGIN_ROOT / "references" / "phases" / "create-spec-phase.md"

ACTION_CHOICE_TITLE = (
    "How the orchestrator chooses each target's action before dispatch"
)
WRITE_POLICY_ACTIONS_TITLE = "The `write_policy` actions"
SECTION_9_TITLE = "9. Spec writer dispatch"
CONTRACT_CITATION = "references/contracts/spec-writer-contract.md"
DIGEST_OWNER_CITATION = "references/artifact-digest.md"
PRE_DISPATCH_NAME = "Pre-dispatch verification"
CITATION_WINDOW = 200

CREATE_PLAN_LEAD = "For an implementation-planner dispatch of create-plan"
CREATE_SPEC_LEAD = "For a spec-writer dispatch of create-spec"
OLD_SECTION_9_PHRASE = "matches the immediately preceding same-phase output"
OLD_THREE_BULLETS_SENTENCE = (
    "For create-spec and the design step the three bullets apply as written"
)

CREATE_SPEC_PHASE_LEVEL_2_HEADINGS = [
    "1. Purpose and ownership",
    "2. Inputs and preconditions",
    "3. Bootstrap and durable-state boundary",
    "4. Reconcile on entry",
    "5. Analyst dispatch loop",
    "6. Question normalization",
    "7. Interactive answer handling",
    "8. Batch answer handling",
    "9. Spec writer dispatch",
    "10. Artifact validation",
    "11. workflow.yaml construction",
    "11a. Design-system determination",
    "12. Command approval gate",
    "13. Completion",
    "Termination conditions",
    "Loop-stop conditions (progress fingerprint)",
    "Scope verification",
    "Gate option vocabulary",
]

_FENCE_RE = re.compile(r"^\s*(```|~~~)")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")

# Slice labels.
S_BLOCK = "the create-spec block of the owner section"
S_PLAN_PART = "the create-plan part of the owner section"
S_ROW = "the replace_own row of the write_policy actions table"
S_BULLET_9 = "the write_policy bullet of create-spec-phase.md section 9"
S_SECTION_9 = "create-spec-phase.md section 9"

# ---------------------------------------------------------------------------
# Helpers (document slicing and matchers)
# ---------------------------------------------------------------------------


def _read(path):
    return path.read_text(encoding="utf-8")


def _norm(text):
    """Whitespace-normalize: any run of whitespace becomes one space."""
    return " ".join(text.split())


def _headings(text):
    """[(line_index, level, title)] for every ATX heading outside a fenced
    code block."""
    found = []
    in_fence = False
    for idx, line in enumerate(text.splitlines()):
        if _FENCE_RE.match(line):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = _HEADING_RE.match(line)
        if match:
            found.append((idx, len(match.group(1)), match.group(2)))
    return found


def _section(text, title, level=None):
    """The body of the one heading whose title equals `title`, up to the next
    heading of the same or a higher level. Exactly one heading must match."""
    lines = text.splitlines()
    heads = _headings(text)
    hits = [
        (i, h) for i, h in enumerate(heads)
        if h[2] == title and (level is None or h[1] == level)
    ]
    if len(hits) != 1:
        raise AssertionError(
            f"expected exactly one heading {title!r}, found {len(hits)}"
        )
    pos, (start, lvl, _title) = hits[0]
    end = len(lines)
    for nxt_line, nxt_lvl, _nxt in heads[pos + 1:]:
        if nxt_lvl <= lvl:
            end = nxt_line
            break
    return "\n".join(lines[start + 1:end])


def _level_2_titles(text):
    return [title for _idx, level, title in _headings(text) if level == 2]


def _blocks(text):
    """Blank-line-delimited, non-empty blocks of `text`."""
    return [b for b in re.split(r"\n\s*\n", text) if b.strip()]


def _bullet(text, starts_with):
    """A top-level `- ` bullet beginning with `starts_with`, through its
    continuation lines (up to the next bullet or blank line)."""
    lines = text.splitlines()
    for i, line in enumerate(lines):
        if line.startswith("- " + starts_with):
            collected = [line]
            for follower in lines[i + 1:]:
                if not follower.strip() or follower.startswith("- "):
                    break
                collected.append(follower)
            return "\n".join(collected)
    raise AssertionError(f"no bullet starts with {starts_with!r}")


def _last_bullet_starts_with(block, starts_with):
    """True when the last top-level `- ` bullet of `block` begins with
    `starts_with`."""
    bullet_lines = [ln for ln in block.splitlines() if ln.startswith("- ")]
    return bool(bullet_lines) and bullet_lines[-1].startswith("- " + starts_with)


def _table_row(text, starts_with):
    for line in text.splitlines():
        if line.startswith(starts_with):
            return line
    raise AssertionError(f"no table row starts with {starts_with!r}")


def _row_cells(row):
    return [cell.strip() for cell in row.strip().strip("|").split("|")]


_ACTION_ROW_RE = re.compile(r"^\| `[a-z_]+` \|", re.MULTILINE)


def _action_table_rows(section_text):
    return len(_ACTION_ROW_RE.findall(section_text))


def _owner_slices(contract_text):
    """The owner section cut into its create-plan part and its create-spec
    block.

    The create-spec block runs from the one paragraph that begins with the
    create-spec lead to the end of the owner section. The create-plan part
    runs from the one paragraph that begins with the create-plan lead up to
    that block. Each lead must occur exactly once in the section, and the
    create-plan lead must come first."""
    owner = _section(contract_text, ACTION_CHOICE_TITLE, level=2)
    flat = _norm(owner)
    for lead in (CREATE_PLAN_LEAD, CREATE_SPEC_LEAD):
        count = flat.count(lead)
        if count != 1:
            raise AssertionError(
                f"expected the words {lead!r} exactly once in the owner "
                f"section, found {count}"
            )
    paragraphs = _blocks(owner)
    starts = {}
    for lead in (CREATE_PLAN_LEAD, CREATE_SPEC_LEAD):
        hits = [i for i, p in enumerate(paragraphs) if _norm(p).startswith(lead)]
        if len(hits) != 1:
            raise AssertionError(f"no paragraph begins with {lead!r}")
        starts[lead] = hits[0]
    plan_at, spec_at = starts[CREATE_PLAN_LEAD], starts[CREATE_SPEC_LEAD]
    if plan_at >= spec_at:
        raise AssertionError("the create-spec block must follow the create-plan part")
    return {
        "owner": owner,
        "plan_part": "\n\n".join(paragraphs[plan_at:spec_at]),
        "block": "\n\n".join(paragraphs[spec_at:]),
        "before_block": paragraphs[spec_at - 1],
    }


def _owner_slice_map(contract_text):
    """{label: raw text} for the two places cut out of the owner section."""
    parts = _owner_slices(contract_text)
    return {S_BLOCK: parts["block"], S_PLAN_PART: parts["plan_part"]}


def _row_slice_map(contract_text):
    """{label: raw text} for the replace_own row of the action table."""
    return {
        S_ROW: _table_row(
            _section(contract_text, WRITE_POLICY_ACTIONS_TITLE, level=3),
            "| `replace_own` |",
        ),
    }


def _section_9_slice_map(create_spec_text):
    """{label: raw text} for section 9 of create-spec-phase.md."""
    section_9 = _section(create_spec_text, SECTION_9_TITLE, level=2)
    return {
        S_BULLET_9: _bullet(section_9, "`write_policy` is built per"),
        S_SECTION_9: section_9,
    }


def _slices(contract_text, create_spec_text):
    """{label: raw text} for the five places this task's statements read."""
    found = {}
    found.update(_owner_slice_map(contract_text))
    found.update(_row_slice_map(contract_text))
    found.update(_section_9_slice_map(create_spec_text))
    return found


def _load_slices():
    return _slices(_read(CONTRACT_PATH), _read(CREATE_SPEC_PATH))


def _cites_contract_owner(text):
    """True when the (whitespace-normalized) text names the contract path and,
    within a citation's reach after it, the owner section's name."""
    flat = _norm(text)
    start = flat.find(CONTRACT_CITATION)
    while start != -1:
        reach = flat[start:start + len(CONTRACT_CITATION) + CITATION_WINDOW]
        if ACTION_CHOICE_TITLE in reach:
            return True
        start = flat.find(CONTRACT_CITATION, start + 1)
    return False


def _cites_digest_owner(text, section_name):
    """True when the text names the digest owner path and, within a
    citation's reach after it, the owner section's name."""
    flat = _norm(text)
    start = flat.find(DIGEST_OWNER_CITATION)
    while start != -1:
        reach = flat[start:start + len(DIGEST_OWNER_CITATION) + CITATION_WINDOW]
        if section_name in reach:
            return True
        start = flat.find(DIGEST_OWNER_CITATION, start + 1)
    return False


# Wording that belongs to the digest owner's definition or procedure. A
# citing place that carries any of it restates the owner (NFR4).
_RESTATEMENT_MARKERS = (
    "raw bytes",
    "raw-byte",
    "lowercase hex",
    "hexadecimal",
    "生バイト",
    "16 進",
    "artifact-digest.py",
    "not_a_regular_file",
    "single-quoted",
    "single quote",
)


def _restatement_markers_in(text):
    flat = _norm(text).lower()
    return [m for m in _RESTATEMENT_MARKERS if m.lower() in flat]


_LAST_ENTRY_RE = re.compile(
    r"\blast(?: `[^`]*`)? entr(?:y|ies)\b|\bcomes last\b", re.IGNORECASE
)
_HAS_ACTION_RE = re.compile(r"\bhas action\b", re.IGNORECASE)
_DIGEST_TERM_RE = re.compile(r"\bdigests?\b|expect_digest|sha256", re.IGNORECASE)
_ARTIFACTS_FOR_CREATE_PLAN_RE = re.compile(
    r"last `artifacts` entry for that path in `phase-state/create-plan\.yaml`",
    re.IGNORECASE,
)


def _names_orchestrator_doc_edits(text):
    return "orchestrator_doc_edits" in text


def _names_phase_state_path(text):
    return "phase-state/" in text


def _names_create_plan_yaml(text):
    return "phase-state/create-plan.yaml" in text


def _names_git_hash_object(text):
    return "git hash-object" in text


def _names_last_entry_rule(text):
    return bool(_LAST_ENTRY_RE.search(_norm(text)))


def _names_has_action_wording(text):
    return bool(_HAS_ACTION_RE.search(_norm(text)))


def _names_a_restatement_marker(text):
    return bool(_restatement_markers_in(text))


def _carries_old_section_9_phrase(text):
    return OLD_SECTION_9_PHRASE in _norm(text)


def _carries_old_three_bullets_sentence(text):
    return OLD_THREE_BULLETS_SENTENCE in _norm(text)


def _names_artifacts_entry_of_create_plan_yaml(text):
    return bool(_ARTIFACTS_FOR_CREATE_PLAN_RE.search(_norm(text)))


def _has_a_pipe_beyond_the_cell_separators(row):
    """True when the row does not split into exactly three cells."""
    return len(_row_cells(row)) != 3


def _adds_a_heading(text):
    return bool(_headings(text))


def _digest_sentences_without_the_orchestrator(text):
    """Sentences that speak of a digest and do not name the orchestrator."""
    flat = _norm(text)
    return [
        sentence
        for sentence in re.split(r"(?<=\.)\s+|;\s*", flat)
        if _DIGEST_TERM_RE.search(sentence)
        and "orchestrator" not in sentence.lower()
    ]


# ---------------------------------------------------------------------------
# Presence statements: (slice, AC, label, pattern, token)
#
# `pattern` is matched against the whitespace-normalized slice,
# case-insensitively. `token` is a text whose removal from the slice, everywhere
# it occurs, must make the pattern fail (the forged copy).
# ---------------------------------------------------------------------------

STATEMENTS = (
    # --- AC-1: the match rule, its two entries, the citation, verification
    (
        S_BLOCK, "AC-1", "the existing create-spec target gets replace_own",
        r"existing create-spec target the action `replace_own`",
        "existing create-spec target the action",
    ),
    (
        S_BLOCK, "AC-1", "replace_own is given when the current digest equals",
        r"`replace_own` when the path's current digest equals either",
        "current digest equals either",
    ),
    (
        S_BLOCK, "AC-1", "(a) the last artifacts entry in create-spec.yaml",
        r"\(a\) the last `artifacts` entry for that path in "
        r"`phase-state/create-spec\.yaml`",
        "phase-state/create-spec.yaml",
    ),
    (
        S_BLOCK, "AC-1", "(a) is an artifacts entry",
        r"\(a\) the last `artifacts` entry for that path in "
        r"`phase-state/create-spec\.yaml`",
        "last `artifacts` entry for that path",
    ),
    (
        S_BLOCK, "AC-1", "(b) names the orchestrator_doc_edits record",
        r"\(b\) the last entry for that path in the `orchestrator_doc_edits` "
        r"record of `phase-state/create-plan\.yaml`",
        "`orchestrator_doc_edits`",
    ),
    (
        S_BLOCK, "AC-1", "(b) is held by phase-state/create-plan.yaml",
        r"\(b\) the last entry for that path in the `orchestrator_doc_edits` "
        r"record of `phase-state/create-plan\.yaml`",
        "`phase-state/create-plan.yaml`",
    ),
    (
        S_BLOCK, "AC-1", "(b) is the last entry for the path",
        r"\(b\) the last entry for that path in the `orchestrator_doc_edits` "
        r"record",
        "last entry for that path",
    ),
    (
        S_BLOCK, "AC-1", "the record is the one phase-state.md defines",
        r"the record `references/phase-state\.md` defines",
        "`references/phase-state.md`",
    ),
    (
        S_BLOCK, "AC-1", "the last entry of a path comes last in its list",
        r"entry for that path that comes last in that list",
        "comes last in that list",
    ),
    (
        S_BLOCK, "AC-1", "only those two and only their last entries count",
        r"counts only those two and only their last entries",
        "only their last entries",
    ),
    (
        S_BLOCK, "AC-1", "earlier entries for the same path do not count",
        r"earlier entries for the same path",
        "earlier entries for the same path",
    ),
    (
        S_BLOCK, "AC-1", "entries for other paths do not count",
        r"entries for other paths",
        "entries for other paths",
    ),
    (
        S_BLOCK, "AC-1", "other phase-state files do not count",
        r"other phase-state files do not count",
        "other phase-state files do not count",
    ),
    (
        S_BLOCK, "AC-1", "either match carries expect_digest",
        r"`replace_own` by either match carries `expect_digest`",
        "by either match",
    ),
    (
        S_BLOCK, "AC-1", "the orchestrator verifies by Pre-dispatch verification",
        r"the orchestrator verifies it by `references/artifact-digest\.md` "
        r"\"Pre-dispatch verification\"",
        "\"Pre-dispatch verification\"",
    ),
    (
        S_BLOCK, "AC-1", "the verification cites the digest owner",
        r"the orchestrator verifies it by `references/artifact-digest\.md` "
        r"\"Pre-dispatch verification\"",
        "`references/artifact-digest.md`",
    ),
    # --- AC-2: no match, the gate, the batch policy, no other condition
    (
        S_BLOCK, "AC-2", "no match: a digest that equals neither entry",
        r"existing create-spec target whose current digest equals neither of "
        r"those two entries",
        "equals neither",
    ),
    (
        S_BLOCK, "AC-2", "no match: the digest-mismatch branch above",
        r"takes the digest-mismatch branch above",
        "digest-mismatch branch above",
    ),
    (
        S_BLOCK, "AC-2", "no match: the create-spec.artifact-overwrite gate",
        r"`create-spec\.artifact-overwrite` gate in interactive mode",
        "`create-spec.artifact-overwrite`",
    ),
    (
        S_BLOCK, "AC-2", "no match: the gate is for interactive mode",
        r"`create-spec\.artifact-overwrite` gate in interactive mode",
        "in interactive mode",
    ),
    (
        S_BLOCK, "AC-2", "no match: the batch-policies.yaml decision",
        r"`references/batch-policies\.yaml` decision in batch mode",
        "`references/batch-policies.yaml`",
    ),
    (
        S_BLOCK, "AC-2", "no match: the decision is for batch mode",
        r"`references/batch-policies\.yaml` decision in batch mode",
        "in batch mode",
    ),
    (
        S_BLOCK, "AC-2", "no other condition gives replace_own",
        r"no other condition gives `replace_own`",
        "other condition gives",
    ),
    (
        S_BLOCK, "AC-2", "a re-planning authorization does not give replace_own",
        r"a spec-change record or a re-planning authorization does not",
        "re-planning authorization",
    ),
    (
        S_BLOCK, "AC-2", "a spec-change record does not give replace_own",
        r"a spec-change record or a re-planning authorization does not",
        "a spec-change record or",
    ),
    # --- AC-3: read conditions, five no-record cases, recorded values
    (
        S_BLOCK, "AC-3", "the record counts only for phase create-plan",
        r"phase `create-plan` and a feature equal to the workflow's feature",
        "phase `create-plan`",
    ),
    (
        S_BLOCK, "AC-3", "the record counts only for the workflow's feature",
        r"phase `create-plan` and a feature equal to the workflow's feature",
        "feature equal to the workflow's feature",
    ),
    (
        S_BLOCK, "AC-3", "no record: an absent file",
        r"\ban absent file\b",
        "absent file",
    ),
    (
        S_BLOCK, "AC-3", "no record: an unreadable file",
        r"\ban unreadable file\b",
        "unreadable file",
    ),
    (
        S_BLOCK, "AC-3", "no record: a malformed file",
        r"\ba malformed file\b",
        "malformed file",
    ),
    (
        S_BLOCK, "AC-3", "no record: a mismatched phase or feature",
        r"\ba mismatched phase or feature\b",
        "mismatched phase or feature",
    ),
    (
        S_BLOCK, "AC-3", "no record: no orchestrator_doc_edits entry for the path",
        r"\bno `orchestrator_doc_edits` entry for the path\b",
        "no `orchestrator_doc_edits` entry for the path",
    ),
    (
        S_BLOCK, "AC-3", "each of the five cases counts as no (b) record",
        r"each count as no \(b\) record",
        "each count as no",
    ),
    (
        S_BLOCK, "AC-3", "the decision then rests on create-spec.yaml alone",
        r"rests on the `phase-state/create-spec\.yaml` comparison alone",
        "comparison alone",
    ),
    (
        S_BLOCK, "AC-3", "(b) recorded values follow Legacy records",
        r"orchestrator compares a \(b\) recorded value.{0,150}"
        r"`references/artifact-digest\.md` \"Legacy records\"",
        "\"Legacy records\"",
    ),
    (
        S_BLOCK, "AC-3", "the orchestrator is the one that compares recorded values",
        r"orchestrator compares a \(b\) recorded value.{0,150}"
        r"`references/artifact-digest\.md` \"Legacy records\"",
        "orchestrator compares",
    ),
    (
        S_BLOCK, "AC-3", "recorded values are compared the same way as create-spec.yaml",
        r"the same way as a `phase-state/create-spec\.yaml` recorded value",
        "the same way as a",
    ),
    # --- AC-4: the create-plan part keeps its statements and points ahead
    (
        S_PLAN_PART, "AC-4", "the design step applies the three bullets as written",
        r"For the design step the three bullets apply as written to every "
        r"existing target whose action is not fixed individually",
        "apply as written",
    ),
    (
        S_PLAN_PART, "AC-4", "create-spec points to the create-spec rule below",
        r"For create-spec, .{0,80}create-spec rule below",
        "create-spec rule below",
    ),
    (
        S_PLAN_PART, "AC-4", "the rule below says which recorded outputs count",
        r"which recorded outputs count as the immediately preceding "
        r"same-phase output",
        "which recorded outputs count",
    ),
    (
        S_PLAN_PART, "AC-4", "token file action sentence: tokens.yaml and tokens.html",
        r"`design-system/tokens\.yaml` \(`extend_only`\) and existing "
        r"`design-system/tokens\.html` \(`regenerate`\) keep the actions "
        r"fixed by this contract's table",
        "keep the actions fixed by this contract's table",
    ),
    (
        S_PLAN_PART, "AC-4", "token file action sentence: a missing tokens file",
        r"A tokens file that does not exist takes the action "
        r"`designer-contract\.md`'s existence table gives \(`create`\)",
        "takes the action",
    ),
    (
        S_PLAN_PART, "AC-4", "no other condition gives replace_own",
        r"No other condition gives `replace_own`",
        "other condition gives `replace_own`",
    ),
    (
        S_PLAN_PART, "AC-4", "other phase-state files do not count",
        r"other phase-state files do not count",
        "other phase-state files do not count",
    ),
    # --- AC-5: the replace_own row
    (
        S_ROW, "AC-5", "the row keeps its first sentence",
        r"Overwrites the same-phase output the worker itself produced earlier\.",
        "Overwrites the same-phase output the worker itself produced earlier.",
    ),
    (
        S_ROW, "AC-5", "the row keeps its create-plan sentence",
        r"For an implementation-planner dispatch of create-plan, this output "
        r"also covers a planning artifact to which the orchestrator gave "
        r"`replace_own`",
        "implementation-planner dispatch of create-plan",
    ),
    (
        S_ROW, "AC-5", "the row keeps rework-planner's recorded output",
        r"rework-planner's recorded output included",
        "rework-planner's recorded output included",
    ),
    (
        S_ROW, "AC-5", "the row names a spec-writer dispatch of create-spec",
        r"For a spec-writer dispatch of create-spec, the same-phase output "
        r"also covers a target to which the orchestrator gave `replace_own`",
        "spec-writer dispatch of create-spec",
    ),
    (
        S_ROW, "AC-5", "the row covers a target the orchestrator gave replace_own",
        r"the same-phase output also covers a target to which the "
        r"orchestrator gave `replace_own`",
        "also covers a target to which",
    ),
    (
        S_ROW, "AC-5", "the row names the version recorded during create-plan",
        r"the version the orchestrator recorded during create-plan",
        "recorded during create-plan",
    ),
    (
        S_ROW, "AC-5", "the row cites the action decision after the create-spec sentence",
        r"spec-writer dispatch of create-spec.{0,300}\"How the orchestrator "
        r"chooses each target's action before dispatch\"",
        ACTION_CHOICE_TITLE,
    ),
    # --- AC-6: section 9 cites the owner and states no match target
    (
        S_BULLET_9, "AC-6", "the bullet keeps the create case",
        r"does not yet exist gets `action: create`",
        "`action: create`",
    ),
    (
        S_BULLET_9, "AC-6", "the replace_own clause refers to the cited section",
        r"matches a recorded output that the cited section counts gets "
        r"`replace_own`",
        "the cited section counts",
    ),
    (
        S_BULLET_9, "AC-6", "the bullet keeps the interactive gate routing",
        r"`create-spec\.artifact-overwrite` gate \(interactive\)",
        "`create-spec.artifact-overwrite`",
    ),
    (
        S_BULLET_9, "AC-6", "the bullet keeps the batch policy routing",
        r"`references/batch-policies\.yaml` \(batch\)",
        "`references/batch-policies.yaml`",
    ),
)

ABSENCE_MATCHERS = {
    # (matcher true on a violation, text that makes it fire)
    "orchestrator_doc_edits": (
        _names_orchestrator_doc_edits,
        " It reads the `orchestrator_doc_edits` record.",
    ),
    "a phase-state/ path": (
        _names_phase_state_path,
        " It reads `phase-state/create-plan.yaml`.",
    ),
    "phase-state/create-plan.yaml": (
        _names_create_plan_yaml,
        " It reads `phase-state/create-plan.yaml`.",
    ),
    "git hash-object": (
        _names_git_hash_object,
        " Compare it with `git hash-object --` first.",
    ),
    "the last-entry rule": (
        _names_last_entry_rule,
        " The last entry for that path counts.",
    ),
    "has-action wording": (
        _names_has_action_wording,
        " On this dispatch the target has action `replace_own`.",
    ),
    "a restatement marker": (
        _names_a_restatement_marker,
        " It hashes the file's raw bytes.",
    ),
    "the old section 9 phrase": (
        _carries_old_section_9_phrase,
        " One whose digest matches the immediately preceding same-phase "
        "output gets `replace_own`.",
    ),
    "the old three-bullets sentence": (
        _carries_old_three_bullets_sentence,
        " For create-spec and the design step the three bullets apply as "
        "written to every existing target.",
    ),
    "a last artifacts entry of create-plan.yaml as (b)": (
        _names_artifacts_entry_of_create_plan_yaml,
        " The last `artifacts` entry for that path in "
        "`phase-state/create-plan.yaml` counts.",
    ),
    "a heading": (
        _adds_a_heading,
        "\n\n### A new subsection\n\ntext\n",
    ),
}

# Which absence matchers each slice must pass (AC in the comment).
ABSENCE_BY_SLICE = {
    S_PLAN_PART: (  # AC-4
        "orchestrator_doc_edits",
        "the old three-bullets sentence",
    ),
    S_BLOCK: (  # AC-1, AC-3
        "git hash-object",
        "a last artifacts entry of create-plan.yaml as (b)",
        "a heading",
    ),
    S_ROW: (  # AC-5
        "a phase-state/ path",
        "orchestrator_doc_edits",
        "the last-entry rule",
        "git hash-object",
        "has-action wording",
        "a restatement marker",
    ),
    S_BULLET_9: (  # AC-6
        "phase-state/create-plan.yaml",
        "orchestrator_doc_edits",
        "the last-entry rule",
        "git hash-object",
        "a restatement marker",
        "the old section 9 phrase",
    ),
    S_SECTION_9: (  # AC-6
        "phase-state/create-plan.yaml",
        "orchestrator_doc_edits",
        "the last-entry rule",
        "git hash-object",
        "a restatement marker",
        "the old section 9 phrase",
    ),
}


def _statement_gaps(slices, statements=STATEMENTS):
    """(slice, label) of the statements whose pattern does not match."""
    return [
        (slice_label, label)
        for slice_label, _ac, label, pattern, _token in statements
        if not re.search(pattern, _norm(slices[slice_label]), re.IGNORECASE)
    ]


def _without_token(text, token):
    return re.sub(re.escape(token), "", _norm(text), flags=re.IGNORECASE)


def _statements_for(ac):
    return [entry for entry in STATEMENTS if entry[1] == ac]


# ---------------------------------------------------------------------------
# Forged documents for the slicer self-tests
# ---------------------------------------------------------------------------

_FORGED_BLOCK = (
    f"{CREATE_SPEC_LEAD}, the orchestrator decides by the rule below.\n\n"
    "- Match. The orchestrator gives it `replace_own`.\n"
)
_FORGED_PLAN_PART = (
    f"{CREATE_PLAN_LEAD}, the orchestrator tells the cases by the rule.\n\n"
    "- Match. one.\n- No match. two.\n- Recorded values. three.\n"
)


def _forged_contract(plan_part=_FORGED_PLAN_PART, block=_FORGED_BLOCK, tail=""):
    return (
        f"## {ACTION_CHOICE_TITLE}\n\nThe introductory paragraph.\n\n"
        + plan_part + "\n" + block + "\n" + tail
        + "## `completed` payload\n\nlater text\n"
    )


# ---------------------------------------------------------------------------
# Slicer and matcher self-tests (each slicer and absence matcher is proved on
# forged text)
# ---------------------------------------------------------------------------


class TestSlicersAreNotVacuous(unittest.TestCase):
    def test_section_slicer_is_fence_aware_and_level_aware(self):
        text = (
            "## A\nbody a\n```\n## not a heading\n```\n### A.1\nsub\n"
            "## B\nbody b\n"
        )
        body = _section(text, "A")
        self.assertIn("body a", body)
        self.assertIn("## not a heading", body)
        self.assertIn("sub", body)
        self.assertNotIn("body b", body)

    def test_section_slicer_rejects_missing_and_duplicate_headings(self):
        with self.assertRaises(AssertionError):
            _section("## A\nx\n", "B")
        with self.assertRaises(AssertionError):
            _section("## A\nx\n## A\ny\n", "A")

    def test_section_slicer_rejects_a_heading_of_another_level(self):
        with self.assertRaises(AssertionError):
            _section("### A\nx\n", "A", level=2)

    def test_owner_slices_cut_the_plan_part_and_the_block_apart(self):
        parts = _owner_slices(_forged_contract())
        self.assertIn(CREATE_PLAN_LEAD, _norm(parts["plan_part"]))
        self.assertNotIn(CREATE_SPEC_LEAD, _norm(parts["plan_part"]))
        self.assertTrue(_norm(parts["block"]).startswith(CREATE_SPEC_LEAD))
        self.assertNotIn(CREATE_PLAN_LEAD, _norm(parts["block"]))
        self.assertNotIn("later text", parts["block"])
        self.assertTrue(
            _last_bullet_starts_with(parts["before_block"], "Recorded values.")
        )

    def test_owner_slices_cut_the_block_at_a_wrapped_lead(self):
        wrapped = _FORGED_BLOCK.replace(
            "For a spec-writer dispatch", "For a\nspec-writer dispatch"
        )
        parts = _owner_slices(_forged_contract(block=wrapped))
        self.assertTrue(_norm(parts["block"]).startswith(CREATE_SPEC_LEAD))

    def test_owner_slices_reject_a_missing_create_spec_lead(self):
        with self.assertRaises(AssertionError):
            _owner_slices(_forged_contract(block="- Match. only a bullet.\n"))

    def test_owner_slices_reject_a_missing_create_plan_lead(self):
        with self.assertRaises(AssertionError):
            _owner_slices(_forged_contract(plan_part="- Match. only a bullet.\n"))

    def test_owner_slices_reject_a_duplicated_create_spec_lead(self):
        twice = _FORGED_BLOCK + "\n" + _FORGED_BLOCK
        with self.assertRaises(AssertionError):
            _owner_slices(_forged_contract(block=twice))

    def test_owner_slices_reject_a_lead_that_is_not_a_paragraph_start(self):
        inside = "Some words first. " + _FORGED_BLOCK
        with self.assertRaises(AssertionError):
            _owner_slices(_forged_contract(block=inside))

    def test_owner_slices_reject_the_block_before_the_plan_part(self):
        swapped = (
            f"## {ACTION_CHOICE_TITLE}\n\n{_FORGED_BLOCK}\n{_FORGED_PLAN_PART}\n"
            "## `completed` payload\n\nlater text\n"
        )
        with self.assertRaises(AssertionError):
            _owner_slices(swapped)

    def test_a_block_placed_in_another_section_is_not_found(self):
        # The block sits under the next heading instead of the owner section:
        # the slice by heading must not find it.
        forged = (
            f"## {ACTION_CHOICE_TITLE}\n\nintro.\n\n{_FORGED_PLAN_PART}\n"
            f"## `completed` payload\n\n{_FORGED_BLOCK}\n"
        )
        with self.assertRaises(AssertionError):
            _owner_slices(forged)

    def test_the_block_is_the_tail_so_a_statement_before_it_is_not_in_it(self):
        plan = _FORGED_PLAN_PART + "\nThe `orchestrator_doc_edits` record is read.\n"
        parts = _owner_slices(_forged_contract(plan_part=plan))
        self.assertTrue(_names_orchestrator_doc_edits(parts["plan_part"]))
        self.assertFalse(_names_orchestrator_doc_edits(parts["block"]))

    def test_the_block_must_follow_the_recorded_values_bullet(self):
        plan = _FORGED_PLAN_PART + "\nA closing paragraph.\n"
        parts = _owner_slices(_forged_contract(plan_part=plan))
        self.assertFalse(
            _last_bullet_starts_with(parts["before_block"], "Recorded values.")
        )
        self.assertFalse(_last_bullet_starts_with("no bullets here", "Recorded"))

    def test_bullet_slicer_takes_one_bullet_through_its_continuation_lines(self):
        text = "- one\n  more one\n- two\n\n- three\n"
        self.assertEqual(_bullet(text, "one"), "- one\n  more one")
        with self.assertRaises(AssertionError):
            _bullet(text, "four")

    def test_table_row_slicer_takes_the_row_by_its_leading_cell(self):
        text = "| `a` | x | y |\n| `replace_own` | req | text |\n"
        self.assertEqual(
            _table_row(text, "| `replace_own` |"), "| `replace_own` | req | text |"
        )
        with self.assertRaises(AssertionError):
            _table_row(text, "| `preserve` |")

    def test_slices_reject_a_row_or_bullet_placed_in_the_wrong_section(self):
        contract = (
            f"## {ACTION_CHOICE_TITLE}\n\nintro.\n\n{_FORGED_PLAN_PART}\n"
            f"{_FORGED_BLOCK}\n"
            "### Another heading\n\n| `replace_own` | required | text. |\n"
        )
        with self.assertRaises(AssertionError):
            _slices(contract, "## 9. Spec writer dispatch\n\n- text\n")
        create_spec = (
            "## 9. Spec writer dispatch\n\ntext\n\n"
            "## 10. Artifact validation\n\n"
            "- `write_policy` is built per the procedure.\n"
        )
        contract_ok = (
            _forged_contract()
            + f"### {WRITE_POLICY_ACTIONS_TITLE}\n\n| `replace_own` | r | t |\n"
        )
        with self.assertRaises(AssertionError):
            _slices(contract_ok, create_spec)

    def test_action_table_row_counter_detects_forged_tables(self):
        section = (
            "| action | `expect_digest` | worker behaviour |\n|---|---|---|\n"
            "| `create` | null | a. |\n| `replace_own` | required | b. |\n"
        )
        self.assertEqual(_action_table_rows(section), 2)
        self.assertEqual(
            _action_table_rows(section + "| `extra_action` | required | x. |\n"), 3
        )

    def test_level_2_titles_ignore_fenced_headings_and_other_levels(self):
        text = "## One\n```\n## Not\n```\n### Sub\n## Two\n"
        self.assertEqual(_level_2_titles(text), ["One", "Two"])


class TestMatchersFireOnForgedText(unittest.TestCase):
    """Each absence matcher fires on a forged copy that carries its token and
    stays quiet on the copy without it."""

    def test_every_absence_matcher_fires_on_its_forged_copy(self):
        base = "The orchestrator gives the target `replace_own`."
        for label, (matcher, injection) in ABSENCE_MATCHERS.items():
            with self.subTest(matcher=label):
                self.assertFalse(matcher(base))
                self.assertTrue(matcher(base + injection))

    def test_pipe_matcher_fires_on_a_row_with_a_fourth_cell(self):
        row = "| `replace_own` | required | text. |"
        self.assertFalse(_has_a_pipe_beyond_the_cell_separators(row))
        self.assertTrue(
            _has_a_pipe_beyond_the_cell_separators("| `replace_own` | a | b | c |")
        )
        self.assertTrue(
            _has_a_pipe_beyond_the_cell_separators(
                "| `replace_own` | required | text with a | pipe. |"
            )
        )

    def test_last_entry_matcher_fires_on_its_wordings_only(self):
        for forged in (
            "the last entry for that path",
            "the last `artifacts` entry for that path",
            "the entries that comes last in that list",
            "the last entries",
        ):
            with self.subTest(forged=forged):
                self.assertTrue(_names_last_entry_rule(forged))
        self.assertFalse(_names_last_entry_rule("the immediately preceding output"))

    def test_restatement_matcher_fires(self):
        for forged in (
            "the sha256 of the file's raw bytes",
            "`sha256:` plus 64 lowercase hex digits",
            "run \"${CLAUDE_PLUGIN_ROOT}/scripts/artifact-digest.py\"",
            "an `not_a_regular_file` element",
            "each path as one single-quoted word",
        ):
            with self.subTest(forged=forged):
                self.assertTrue(_names_a_restatement_marker(forged))
        self.assertFalse(
            _names_a_restatement_marker("cites the owner and verifies the targets")
        )

    def test_citation_matchers_accept_the_citation_and_reject_forged_copies(self):
        good = _norm(
            "see `references/contracts/spec-writer-contract.md`,\n"
            "\"How the orchestrator chooses each\ntarget's action before "
            "dispatch\""
        )
        self.assertTrue(_cites_contract_owner(good))
        self.assertTrue(
            _cites_contract_owner(
                "see `references/contracts/spec-writer-contract.md`,\n"
                "\"How the orchestrator chooses each\ntarget's action before "
                "dispatch\""
            )
        )
        self.assertFalse(_cites_contract_owner(good.replace(CONTRACT_CITATION, "")))
        self.assertFalse(_cites_contract_owner(good.replace(ACTION_CHOICE_TITLE, "")))
        self.assertFalse(_cites_contract_owner(""))
        far = (
            f"`{CONTRACT_CITATION}` " + "x " * (CITATION_WINDOW // 2 + 50)
            + ACTION_CHOICE_TITLE
        )
        self.assertFalse(_cites_contract_owner(far))

        digest = (
            "see `references/artifact-digest.md`\n(`Pre-dispatch verification`)"
        )
        self.assertTrue(_cites_digest_owner(digest, PRE_DISPATCH_NAME))
        self.assertFalse(
            _cites_digest_owner(digest.replace(DIGEST_OWNER_CITATION, ""), PRE_DISPATCH_NAME)
        )
        self.assertFalse(_cites_digest_owner(digest, "Layer 5 recording"))

    def test_digest_sentence_matcher_fires_without_the_orchestrator(self):
        good = "The orchestrator compares the current digest with the entry."
        self.assertEqual(_digest_sentences_without_the_orchestrator(good), [])
        bad = good + " The worker compares the digest of the target."
        self.assertEqual(
            _digest_sentences_without_the_orchestrator(bad),
            ["The worker compares the digest of the target."],
        )
        self.assertTrue(
            _digest_sentences_without_the_orchestrator("It keeps `expect_digest`.")
        )

    def test_statement_gap_finder_reports_a_missing_statement(self):
        slices = {label: "" for label in (
            S_BLOCK, S_PLAN_PART, S_ROW, S_BULLET_9, S_SECTION_9)}
        self.assertEqual(len(_statement_gaps(slices)), len(STATEMENTS))


class TestPresenceStatementsFailOnForgedCopies(unittest.TestCase):
    """Each presence statement fails on a copy of its slice without its token."""

    @classmethod
    def setUpClass(cls):
        cls.slices = _load_slices()

    def test_each_statement_matches_its_slice_and_fails_without_its_token(self):
        for slice_label, _ac, label, pattern, token in STATEMENTS:
            with self.subTest(slice=slice_label, statement=label):
                flat = _norm(self.slices[slice_label])
                self.assertIsNotNone(
                    re.search(pattern, flat, re.IGNORECASE),
                    "the statement is missing from the real slice",
                )
                self.assertIn(
                    token.lower(), flat.lower(),
                    "the forged copy would equal the slice; the token must "
                    "be in the slice for this check to mean anything",
                )
                forged = _without_token(self.slices[slice_label], token)
                self.assertIsNone(
                    re.search(pattern, forged, re.IGNORECASE),
                    f"statement still matches without {token!r}",
                )

    def test_a_statement_placed_in_another_slice_does_not_satisfy_the_check(self):
        # The block's text and the plan part's text change places: a statement
        # that only one of them makes is not satisfied by the other slot.
        swapped = dict(self.slices)
        swapped[S_PLAN_PART] = self.slices[S_BLOCK]
        swapped[S_BLOCK] = self.slices[S_PLAN_PART]
        gap_labels = {label for _slice, label in _statement_gaps(swapped)}
        for label in (
            "(b) names the orchestrator_doc_edits record",
            "(a) the last artifacts entry in create-spec.yaml",
            "the design step applies the three bullets as written",
            "token file action sentence: tokens.yaml and tokens.html",
        ):
            with self.subTest(statement=label):
                self.assertIn(label, gap_labels)

    def test_every_statement_names_a_known_slice_and_ac(self):
        for slice_label, ac, label, _pattern, _token in STATEMENTS:
            with self.subTest(statement=label):
                self.assertIn(slice_label, self.slices)
                self.assertIn(ac, {f"AC-{n}" for n in range(1, 7)})

    def test_no_statement_is_left_unchecked(self):
        self.assertEqual(_statement_gaps(self.slices), [])


# ---------------------------------------------------------------------------
# AC-1 to AC-6 against the real documents
# ---------------------------------------------------------------------------


class _LiveDocumentTest(unittest.TestCase):
    """Loads only the places a test class reads, so that a failure names the
    place that is wrong and not a place the class does not read."""

    LOADS = ()  # any of "owner", "row", "section9"

    @classmethod
    def setUpClass(cls):
        cls.contract = _read(CONTRACT_PATH)
        cls.create_spec = _read(CREATE_SPEC_PATH)
        cls.slices = {}
        if "owner" in cls.LOADS:
            cls.parts = _owner_slices(cls.contract)
            cls.slices.update(_owner_slice_map(cls.contract))
        if "row" in cls.LOADS:
            cls.slices.update(_row_slice_map(cls.contract))
        if "section9" in cls.LOADS:
            cls.slices.update(_section_9_slice_map(cls.create_spec))

    def _assert_statements(self, ac, slice_label=None):
        statements = [
            e for e in _statements_for(ac)
            if slice_label is None or e[0] == slice_label
        ]
        self.assertTrue(statements, ac)
        for entry_slice, _ac, label, pattern, _token in statements:
            with self.subTest(statement=label):
                self.assertRegex(
                    _norm(self.slices[entry_slice]), f"(?i){pattern}"
                )

    def _assert_absent(self, slice_label):
        for label in ABSENCE_BY_SLICE[slice_label]:
            matcher = ABSENCE_MATCHERS[label][0]
            with self.subTest(slice=slice_label, absent=label):
                self.assertFalse(
                    matcher(self.slices[slice_label]),
                    f"{slice_label} must not carry: {label}",
                )


class TestAC1CreateSpecBlockMatchRule(_LiveDocumentTest):
    """AC-1 (FR3): the create-spec block gives replace_own on either of two
    last entries, cites phase-state.md and states the verification."""

    LOADS = ("owner",)

    def test_the_create_spec_lead_occurs_once_and_opens_a_paragraph(self):
        self.assertEqual(_norm(self.parts["owner"]).count(CREATE_SPEC_LEAD), 1)
        self.assertTrue(_norm(self.parts["block"]).startswith(CREATE_SPEC_LEAD))

    def test_the_block_sits_after_the_recorded_values_bullet(self):
        self.assertTrue(
            _last_bullet_starts_with(self.parts["before_block"], "Recorded values.")
        )
        self.assertTrue(
            _norm(_bullet(self.parts["before_block"], "Recorded values.")).startswith(
                "- Recorded values."
            )
        )

    def test_the_block_states_the_match_rule_with_both_entries(self):
        self._assert_statements("AC-1")

    def test_the_block_adds_no_heading(self):
        self.assertFalse(_adds_a_heading(self.parts["block"]))

    def test_the_heading_text_and_level_of_the_owner_section_are_unchanged(self):
        titles = [
            (level, title)
            for _i, level, title in _headings(self.contract)
            if title == ACTION_CHOICE_TITLE
        ]
        self.assertEqual(titles, [(2, ACTION_CHOICE_TITLE)])
        self.assertEqual(_headings(self.parts["owner"]), [])

    def test_every_digest_sentence_of_the_block_names_the_orchestrator(self):
        self.assertEqual(
            _digest_sentences_without_the_orchestrator(self.parts["block"]), []
        )

    def test_the_block_never_writes_b_as_an_artifacts_entry_of_create_plan(self):
        self.assertFalse(
            _names_artifacts_entry_of_create_plan_yaml(self.slices[S_BLOCK])
        )


class TestAC2CreateSpecBlockNoMatchRouting(_LiveDocumentTest):
    """AC-2 (FR3, FR5): any other target goes to the gate or the batch
    policy; no other condition gives replace_own."""

    LOADS = ("owner",)

    def test_the_block_routes_a_non_matching_target_and_names_no_other_condition(self):
        self._assert_statements("AC-2")


class TestAC3CreateSpecBlockReadConditions(_LiveDocumentTest):
    """AC-3 (FR4): read conditions, five no-record cases, recorded values."""

    LOADS = ("owner",)

    def test_the_block_states_the_read_conditions_and_the_no_record_cases(self):
        self._assert_statements("AC-3")

    def test_the_owner_section_does_not_name_git_hash_object(self):
        self.assertFalse(_names_git_hash_object(self.parts["owner"]))
        self.assertFalse(_names_git_hash_object(self.slices[S_BLOCK]))


class TestAC4CreatePlanPartStaysFreeOfTheRecord(_LiveDocumentTest):
    """AC-4 (FR5): the text from the create-plan paragraph up to the block
    does not name the record and keeps its pinned sentences."""

    LOADS = ("owner",)

    def test_the_create_plan_part_names_no_orchestrator_doc_edits(self):
        self._assert_absent(S_PLAN_PART)

    def test_the_create_plan_part_keeps_its_pinned_sentences(self):
        self._assert_statements("AC-4")

    def test_the_create_plan_part_starts_at_its_lead(self):
        self.assertTrue(_norm(self.parts["plan_part"]).startswith(CREATE_PLAN_LEAD))


class TestAC4OldSentenceIsReplaced(_LiveDocumentTest):
    """AC-4 (FR5): the sentence that applied the three bullets to create-spec
    as written is gone from the owner section. Reads the owner section only, so
    it does not depend on the create-spec block being present."""

    LOADS = ()

    def test_the_old_three_bullets_sentence_is_gone_from_the_owner_section(self):
        owner = _section(self.contract, ACTION_CHOICE_TITLE, level=2)
        self.assertFalse(_carries_old_three_bullets_sentence(owner))

    def test_the_design_step_sentence_is_still_in_the_owner_section(self):
        owner = _norm(_section(self.contract, ACTION_CHOICE_TITLE, level=2))
        self.assertIn(
            "For the design step the three bullets apply as written to every "
            "existing target whose action is not fixed individually",
            owner,
        )


class TestAC5ReplaceOwnRow(_LiveDocumentTest):
    """AC-5 (FR6, NFR1): the replace_own row keeps its two sentences and adds
    one that points at the owner section."""

    LOADS = ("row",)

    def test_the_row_keeps_its_sentences_and_adds_the_create_spec_sentence(self):
        self._assert_statements("AC-5")

    def test_the_row_carries_none_of_the_rule(self):
        self._assert_absent(S_ROW)

    def test_the_row_has_three_cells_and_no_other_pipe(self):
        row = self.slices[S_ROW]
        self.assertFalse(_has_a_pipe_beyond_the_cell_separators(row))
        self.assertEqual(len(_row_cells(row)), 3)
        self.assertEqual(row.count("|"), 4)

    def test_the_row_stays_one_line(self):
        self.assertNotIn("\n", self.slices[S_ROW])

    def test_the_action_table_still_has_seven_rows(self):
        section = _section(self.contract, WRITE_POLICY_ACTIONS_TITLE, level=3)
        self.assertEqual(_action_table_rows(section), 7)


class TestAC6CreateSpecPhaseSection9(_LiveDocumentTest):
    """AC-6 (FR6, NFR2, NFR4): section 9 cites the owner and states no rule
    of its own."""

    LOADS = ("section9",)

    def test_the_write_policy_bullet_cites_the_contract_and_the_owner_section(self):
        self.assertTrue(_cites_contract_owner(self.slices[S_BULLET_9]))

    def test_the_write_policy_bullet_keeps_its_cases_and_cites_the_match(self):
        self._assert_statements("AC-6", S_BULLET_9)

    def test_section_9_no_longer_carries_the_old_match_phrase(self):
        self._assert_absent(S_SECTION_9)

    def test_the_write_policy_bullet_states_none_of_the_rule(self):
        self._assert_absent(S_BULLET_9)

    def test_section_9_still_cites_pre_dispatch_verification(self):
        self.assertTrue(
            _cites_digest_owner(self.slices[S_SECTION_9], PRE_DISPATCH_NAME)
        )

    def test_the_level_2_headings_of_the_document_are_unchanged(self):
        self.assertEqual(
            _level_2_titles(self.create_spec), CREATE_SPEC_PHASE_LEVEL_2_HEADINGS
        )

    def test_the_other_bullets_of_section_9_are_still_there(self):
        section_9 = _norm(self.slices[S_SECTION_9])
        for token in (
            "- At the `reduced` tier, spec-writer is dispatched to produce "
            "SPEC.md only",
            "- At the `minimal` tier, spec-writer is not dispatched at all.",
            "- At the `full` tier, both REQUIREMENTS.md and SPEC.md are "
            "produced",
            "- `Task(subagent_type=\"em-workflow:spec-writer\")`",
            "- The orchestrator verifies each target's `expect_digest` itself "
            "before dispatch",
        ):
            with self.subTest(token=token):
                self.assertIn(token, section_9)


class TestAbsenceChecksFailOnForgedLiveSlices(_LiveDocumentTest):
    """AC-7 (NFR3): each absence check of the live tests above fires when its
    token is added to the real slice."""

    LOADS = ("owner", "row", "section9")

    def test_every_live_absence_check_fires_on_the_slice_with_its_token(self):
        for slice_label, labels in ABSENCE_BY_SLICE.items():
            for label in labels:
                matcher, injection = ABSENCE_MATCHERS[label]
                with self.subTest(slice=slice_label, absent=label):
                    self.assertFalse(matcher(self.slices[slice_label]))
                    self.assertTrue(matcher(self.slices[slice_label] + injection))

    def test_the_citation_check_fails_on_the_bullet_without_the_citation(self):
        flat = _norm(self.slices[S_BULLET_9])
        self.assertTrue(_cites_contract_owner(flat))
        self.assertFalse(_cites_contract_owner(flat.replace(CONTRACT_CITATION, "")))
        self.assertFalse(_cites_contract_owner(flat.replace(ACTION_CHOICE_TITLE, "")))

    def test_the_pre_dispatch_citation_check_fails_without_the_citation(self):
        flat = _norm(self.slices[S_SECTION_9])
        self.assertTrue(_cites_digest_owner(flat, PRE_DISPATCH_NAME))
        self.assertFalse(
            _cites_digest_owner(flat.replace(DIGEST_OWNER_CITATION, ""), PRE_DISPATCH_NAME)
        )
        self.assertFalse(
            _cites_digest_owner(flat.replace(PRE_DISPATCH_NAME, ""), PRE_DISPATCH_NAME)
        )

    def test_the_heading_list_check_fails_on_a_changed_heading_list(self):
        forged = self.create_spec.replace(
            "## 9. Spec writer dispatch", "## 9. Spec writer dispatch (changed)"
        )
        self.assertNotEqual(
            _level_2_titles(forged), CREATE_SPEC_PHASE_LEVEL_2_HEADINGS
        )
        self.assertEqual(
            _level_2_titles(self.create_spec), CREATE_SPEC_PHASE_LEVEL_2_HEADINGS
        )

    def test_the_row_cell_check_fails_on_a_row_with_a_forged_pipe(self):
        forged = self.slices[S_ROW].replace(
            "same-phase output also", "same-phase | output also"
        )
        self.assertNotEqual(forged, self.slices[S_ROW])
        self.assertTrue(_has_a_pipe_beyond_the_cell_separators(forged))

    def test_the_seven_row_check_fails_on_a_forged_table(self):
        section = _section(self.contract, WRITE_POLICY_ACTIONS_TITLE, level=3)
        forged = section + "| `extra_action` | required | x. |\n"
        self.assertEqual(_action_table_rows(section), 7)
        self.assertEqual(_action_table_rows(forged), 8)


class TestModuleHygiene(unittest.TestCase):
    def test_only_stdlib_top_level_imports(self):
        stdlib_names = set(sys.stdlib_module_names)
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imported.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imported.add(node.module.split(".")[0])
        self.assertEqual(imported - stdlib_names, set())


if __name__ == "__main__":
    unittest.main()
