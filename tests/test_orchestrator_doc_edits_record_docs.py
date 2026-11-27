"""Document contract tests for orchestrator-spec-edit-overwrite/task0002: the
`orchestrator_doc_edits` record of `phase-state/create-plan.yaml` (its schema)
and the develop skill's Step B procedure that appends to it.

Covers the Acceptance Criteria of
feature-docs/orchestrator-spec-edit-overwrite/tasks/task0002.md:

- AC-1 (`TestAC1SchemaExample`): the `## Schema` yaml example of
  `em-workflow/references/phase-state.md` carries one top-level
  `orchestrator_doc_edits:` key with one entry of `path`, `sha256` and
  `reason`, placed between `other_feature_doc_fixes` and `patches`.
- AC-2 (`TestAC2FieldTableRow`): the top-level field table carries exactly
  one `orchestrator_doc_edits` row directly after the
  `other_feature_doc_fixes` row, and the row cites its owners.
- AC-3 (`TestAC3WriterParagraph`): `em-workflow/skills/develop/SKILL.md` Step B
  carries the `**create-plan 中の自 feature 文書修正の記録**` paragraph between
  the `**exit-4 リカバリ**` paragraph and the
  `**batch: verify の cap 到達に対する停止条件の例外**` paragraph, and states
  when and what the orchestrator appends, and that it is the same commit.
- AC-4 (`TestAC4FailureAndExit4`): the same paragraph states that no entry is
  written when the digest calculation fails, and what an exit 4 of the commit
  does.
- AC-5 (`TestAC5Absences`, `TestAC5UnchangedNeighbours`): the new paragraph
  carries none of the forbidden tokens or commands; the create-plan exemption
  block, the commit-discipline paragraph and the `**exit-4 リカバリ**`
  paragraph of Step B keep their pinned digests. (The new row's absences are
  checked under AC-2.)
- AC-6 (`TestAC6OwnModule`): this module reads the documents without writing
  them and imports the standard library only. Every presence check has a test
  on a forged sample without its token, and every absence check has a test on a
  forged sample carrying its token (the `*Proof*` tests of each class).

Convention: standard library `unittest` only. Every assertion reads the place
it concerns on whitespace-normalized text, so no line-break position is
pinned. Every matcher has a negative proof against an in-test sample, so a
proof never depends on the live documents. This module never writes a file.
"""

import ast
import hashlib
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"
PHASE_STATE_PATH = PLUGIN_ROOT / "references" / "phase-state.md"
SKILL_PATH = PLUGIN_ROOT / "skills" / "develop" / "SKILL.md"

RECORD_FIELD = "orchestrator_doc_edits"
PREVIOUS_FIELD = "other_feature_doc_fixes"
NEXT_FIELD = "patches"
ENTRY_KEYS = ("path", "sha256", "reason")

TABLE_MARKER = "Every top-level field:"

STEP_B_HEADING = "## Step B: 自走ループ"
NEW_LABEL = "**create-plan 中の自 feature 文書修正の記録**"
EXIT4_LABEL = "**exit-4 リカバリ**"
EXIT4_END = "しない）。"
NEXT_LABEL = "**batch: verify の cap 到達に対する停止条件の例外**"

EXEMPTION_START = "**例外: create-plan は先に `in_progress` を経ない**"
EXEMPTION_END = "`needs_update` のまま dispatch する。"
COMMIT_DISCIPLINE_START = (
    "workflow.yaml か feature-docs/ 配下のドキュメントを Write/Edit するたび"
)

# sha256 of the three Step B blocks that stay byte-identical, computed from the
# base revision of this task. The exemption block is the two paragraphs from
# its bold label to `のまま dispatch する。`; the other two are one paragraph
# each, from their first words to the blank line that follows.
EXEMPTION_SHA256 = "ea23d4fc2e4083ee9452680cc47b7cde1a5f57406b1ba14d45fa8a0030afdecd"
COMMIT_DISCIPLINE_SHA256 = (
    "154b5421a5dc0e9a9e9424de1cc4aec927e8c236bd295d6db949d637fd1e0638"
)
EXIT4_PARAGRAPH_SHA256 = (
    "aff5e3908801fe6077ce5f0af45391b6e6c580d863b71d95c3e7ce41e551e287"
)

# Wording that belongs to the digest owner's definition or procedure
# (`references/artifact-digest.md`); a citing place that carries any of it
# restates the owner instead of citing it.
RESTATEMENT_MARKERS = (
    "raw bytes",
    "raw-byte",
    "lowercase hex",
    "hexadecimal",
    "artifact-digest.py",
    "not_a_regular_file",
    "unreadable",
    "single-quoted",
    "single quote",
    "生のバイト",
    "16 進",
    "16進",
    "シングルクォート",
    "単一引用符",
)
LAST_ENTRY_WORDING = (
    "last entry",
    "last-entry",
    "最後のエントリ",
    "最後の 1 件",
    "末尾のエントリ",
)


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------


def _read(path):
    return path.read_text(encoding="utf-8")


def _flat(text):
    """Collapse every whitespace run to one space."""
    return re.sub(r"\s+", " ", text).strip()


def _norm(text):
    """Whitespace-normalized text with the whitespace next to any non-ASCII
    character dropped, so a needle survives the documents' hard line wrapping
    inside Japanese text."""
    return re.sub(r"\s*([^\x00-\x7f])\s*", r"\1", _flat(text))


def _require(condition, message):
    if not condition:
        raise AssertionError(message)


def _only(candidates, what):
    _require(
        len(candidates) == 1,
        "expected exactly one %s, found %d" % (what, len(candidates)),
    )
    return candidates[0]


def _holds_all(text, needles, what):
    flat = _norm(text)
    for needle in needles:
        _require(_norm(needle) in flat, "%s lacks %r" % (what, needle))
    return flat


def _holds_none(text, tokens, what):
    flat = _norm(text)
    lowered = flat.lower()
    for token in tokens:
        _require(
            _norm(token).lower() not in lowered,
            "%s carries the forbidden token %r" % (what, token),
        )
    return flat


def _without(sample, needle):
    """`sample` with every occurrence of `needle` removed, matching the
    needle across any whitespace or line wrapping. Fails when the needle is
    absent, so a proof cannot pass because its edit missed."""
    pattern = r"\s*".join(re.escape(char) for char in needle if not char.isspace())
    forged, count = re.subn(pattern, "", sample)
    if count < 1:
        raise AssertionError("proof edit missed: %r" % needle)
    return forged


def _headings(text):
    """(line_index, level, line) for every Markdown heading outside a fenced
    code block."""
    in_fence = False
    found = []
    for index, line in enumerate(text.split("\n")):
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        match = re.match(r"^(#{1,6}) \S", line)
        if match:
            found.append((index, len(match.group(1)), line))
    return found


def _h2_section(text, heading):
    """Body of the one H2 section whose heading line is `heading` (heading
    line excluded), up to the next H2. Raises AssertionError unless exactly
    one such heading exists outside a fenced block."""
    lines = text.split("\n")
    h2 = [(i, line) for i, level, line in _headings(text) if level == 2]
    starts = [i for i, line in h2 if line == heading]
    _require(len(starts) == 1, "expected exactly one %r heading" % heading)
    start = starts[0]
    end = next((i for i, _line in h2 if i > start), len(lines))
    return "\n".join(lines[start + 1 : end])


def _paragraphs(text):
    """Raw paragraphs (blank-line separated, surrounding line breaks
    removed)."""
    return [
        block.strip("\n")
        for block in re.split(r"\n\s*\n", text)
        if block.strip()
    ]


def _sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# phase-state.md: the schema example (AC-1).
# ---------------------------------------------------------------------------

EXISTING_EXAMPLE_LINES = (
    "schema_version: 1",
    "worker_runs:",
    "artifacts:",
    "other_feature_doc_fixes:",
    "patches:",
    "classification:",
)


def schema_example_block(text):
    """The first fenced yaml block under the `## Schema` heading."""
    section = _h2_section(text, "## Schema")
    match = re.search(r"```yaml\n(.*?)\n```", section, re.DOTALL)
    _require(match is not None, "no yaml block under ## Schema")
    return match.group(1)


def _top_level_keys(block):
    """(line_index, key) for every column-0 mapping key of a yaml block."""
    found = []
    for index, line in enumerate(block.split("\n")):
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*):", line)
        if match:
            found.append((index, match.group(1)))
    return found


def record_block(block):
    """(first line, entry lines) of the one top-level `orchestrator_doc_edits`
    key: the key line, then every line up to the next column-0 line."""
    lines = block.split("\n")
    starts = [
        i for i, line in enumerate(lines) if line.startswith(RECORD_FIELD + ":")
    ]
    _require(
        len(starts) == 1,
        "expected one top-level %s: line, found %d" % (RECORD_FIELD, len(starts)),
    )
    body = []
    for line in lines[starts[0] + 1 :]:
        if line and not line.startswith(" "):
            break
        body.append(line)
    return lines[starts[0]], body


def check_example_position(block):
    """The key sits after `other_feature_doc_fixes` and before `patches`, with
    no other top-level key between them."""
    keys = [key for _index, key in _top_level_keys(block)]
    _require(
        keys.count(RECORD_FIELD) == 1,
        "expected one top-level %s key" % RECORD_FIELD,
    )
    _require(keys.count(PREVIOUS_FIELD) == 1, "expected one top-level previous key")
    _require(keys.count(NEXT_FIELD) == 1, "expected one top-level next key")
    at = keys.index(RECORD_FIELD)
    _require(
        at > 0 and keys[at - 1] == PREVIOUS_FIELD,
        "the key does not directly follow %s" % PREVIOUS_FIELD,
    )
    _require(
        at + 1 < len(keys) and keys[at + 1] == NEXT_FIELD,
        "the key is not directly followed by %s" % NEXT_FIELD,
    )


def check_example_record(block):
    """One top-level key, its trailing comment, exactly one entry carrying
    exactly `path`, `sha256` and `reason`."""
    first, body = record_block(block)
    comment = first.partition("#")[2]
    _require("#" in first, "the key line carries no comment")
    _require("`phase: create-plan` only" in comment, "the comment lacks the phase")
    _require("append-only" in comment, "the comment lacks append-only")
    entries = [line for line in body if line.startswith("  - ")]
    _require(len(entries) == 1, "the example holds %d entries, expected 1" % len(entries))
    keys = []
    values = {}
    for line in body:
        match = re.match(r"^(?:  - |    )([A-Za-z0-9_]+): (\S.*)$", line)
        if match:
            keys.append(match.group(1))
            values[match.group(1)] = match.group(2)
    _require(
        sorted(keys) == sorted(ENTRY_KEYS),
        "the example entry holds keys %r, expected %r" % (sorted(keys), sorted(ENTRY_KEYS)),
    )
    _require(
        re.match(r"^feature-docs/[^/\s]+/(SPEC|REQUIREMENTS)\.md$", values["path"]),
        "the example path %r is not an own-feature SPEC.md or REQUIREMENTS.md path"
        % values["path"],
    )
    return entries


def check_existing_example_lines(block):
    top_level = [line for line in block.split("\n") if line and not line.startswith(" ")]
    for needle in EXISTING_EXAMPLE_LINES:
        _require(
            any(line.startswith(needle) for line in top_level),
            "the example lost the top-level line %r" % needle,
        )


def check_schema_example(block):
    check_example_record(block)
    check_example_position(block)
    check_existing_example_lines(block)


RECORD_BLOCK = """\
orchestrator_doc_edits:        # `phase: create-plan` only; append-only
  - path: feature-docs/example/SPEC.md
    sha256: sha256:...
    reason: "..."
"""
EXAMPLE_HEAD = """\
schema_version: 1
feature: example-feature
worker_runs:
  - request_id: create-plan-run-0001
    status: completed
artifacts:
  - path: feature-docs/example/IMPLEMENTATION.md
    sha256: sha256:...
    produced_by: create-plan-run-0001
other_feature_doc_fixes:       # `phase: create-plan` only; append-only
  - path: feature-docs/other-feature/SPEC.md
    change: "..."
    reason: "..."
    produced_by: create-plan-run-0002
"""
EXAMPLE_TAIL = """\
patches:
  - patch_id: create-plan-p0001
    status: proposed
classification:                # `phase: rework` only
  - classifier: codex
"""
GOOD_EXAMPLE = EXAMPLE_HEAD + RECORD_BLOCK + EXAMPLE_TAIL


# ---------------------------------------------------------------------------
# phase-state.md: the field table row (AC-2).
# ---------------------------------------------------------------------------

ROW_NEEDLES = (
    "`phase: create-plan` only",
    "append-only",
    "the feature's own SPEC.md or REQUIREMENTS.md",
    "during create-plan",
    "`path`, `sha256` and `reason`",
    "`references/artifact-digest.md`",
    '"Digest definition"',
    "never rewritten or cleared",
    "a phase restart (`generation` increases) included",
    "`skills/develop/SKILL.md`, Step B",
    "in the same commit as the document change",
    "`references/contracts/spec-writer-contract.md`",
    "\"How the orchestrator chooses each target's action before dispatch\"",
    "A file written before the field existed lacks it and stays valid.",
)
ROW_ABSENT_TOKENS = (
    ("git hash-object",)
    + RESTATEMENT_MARKERS
    + LAST_ENTRY_WORDING
    + ("replace_own", "malformed")
)
GOOD_ROW = (
    "| `orchestrator_doc_edits` | `phase: create-plan` only. An append-only "
    "list of the changes the orchestrator itself made to the feature's own "
    "SPEC.md or REQUIREMENTS.md during create-plan and committed. Each entry: "
    "`path`, `sha256` and `reason`. `sha256` is the digest "
    '`references/artifact-digest.md` "Digest definition" defines. The writer '
    "is `skills/develop/SKILL.md`, Step B; it commits the entry in the same "
    "commit as the document change. The reader is "
    "`references/contracts/spec-writer-contract.md`, \"How the orchestrator "
    "chooses each target's action before dispatch\". The list is never "
    "rewritten or cleared, a phase restart (`generation` increases) included. "
    "A file written before the field existed lacks it and stays valid. |"
)
GOOD_TABLE_ROWS = [
    "| `schema_version` | Format version. |",
    "| `other_feature_doc_fixes` | `phase: create-plan` only. A list. |",
    GOOD_ROW,
    "| `patches` | List. |",
]


def top_level_table_rows(text):
    """The contiguous Markdown table lines that follow the one
    `Every top-level field:` marker."""
    _require(text.count(TABLE_MARKER) == 1, "expected one %r marker" % TABLE_MARKER)
    after = text[text.index(TABLE_MARKER) + len(TABLE_MARKER) :]
    rows = []
    for line in after.split("\n"):
        if line.startswith("|"):
            rows.append(line)
        elif rows:
            break
    _require(rows, "no table follows the marker")
    return rows


def _row_name(row):
    match = re.match(r"^\| `([^`]+)` \|", row)
    return match.group(1) if match else None


def field_table_row(rows):
    return _only(
        [row for row in rows if _row_name(row) == RECORD_FIELD],
        "field table row for %s" % RECORD_FIELD,
    )


def check_row_position(rows):
    """The one row sits directly after the `other_feature_doc_fixes` row."""
    names = [_row_name(row) for row in rows]
    _require(names.count(RECORD_FIELD) == 1, "expected one %s row" % RECORD_FIELD)
    _require(names.count(PREVIOUS_FIELD) == 1, "expected one previous row")
    _require(
        names.index(RECORD_FIELD) == names.index(PREVIOUS_FIELD) + 1,
        "the row does not directly follow the %s row" % PREVIOUS_FIELD,
    )


def check_row_wording(row):
    _holds_all(row, ROW_NEEDLES, "the %s row" % RECORD_FIELD)


def check_row_absences(row):
    _holds_none(row, ROW_ABSENT_TOKENS, "the %s row" % RECORD_FIELD)


# ---------------------------------------------------------------------------
# SKILL.md: the Step B paragraph (AC-3, AC-4, AC-5).
# ---------------------------------------------------------------------------

WHEN_AND_WHAT_NEEDLES = (
    "create-plan の間に",
    "オーケストレーター自身が",
    "feature 自身の SPEC.md または REQUIREMENTS.md を変更してコミットしたとき",
    "`phase-state/create-plan.yaml`",
    "`orchestrator_doc_edits`",
    "エントリを 1 件追記する",
    "変更したドキュメントの path",
    "その時点のそのドキュメントの digest",
    "`references/artifact-digest.md` の `Calculation` で計算する",
    "変更の理由",
    "エントリの形は `references/phase-state.md` の `## Schema` を引く",
)
SAME_COMMIT_NEEDLES = (
    "ドキュメントの変更と同じ `commit-docs.sh` のコミットに含める",
    "`references/phase-state.md` の「Update, commit, and exit-4 recovery」を引く",
)
READER_CITATION_NEEDLES = (
    "`references/contracts/spec-writer-contract.md`",
    "How the orchestrator chooses each target's action before dispatch",
)
CALCULATION_FAILURE_NEEDLES = (
    "digest の計算が失敗したときは、エントリを書かない",
)
EXIT4_NEEDLES = (
    "そのコミットが exit 4 を返したときは",
    "上記の「**exit-4 リカバリ**」に従い",
    "最新ツリーの上で修正を作り直し",
    "作り直した本文から digest を計算し直し",
    "読み直した `phase-state/create-plan.yaml` にエントリを追記して",
    "エントリを同じコミットに含めて再試行する",
)

# Substrings that must never appear (case-insensitive) in the paragraph.
PARAGRAPH_ABSENT_TOKENS = (
    ("git hash-object", "phase-state/create-spec.yaml", "sha256:")
    + RESTATEMENT_MARKERS
    + LAST_ENTRY_WORDING
)
# Patterns for the git commands and script invocations the paragraph must not
# write, each with a sample text that carries one.
PARAGRAPH_ABSENT_PATTERNS = (
    (re.compile(r"```"), "A fenced block:\n```\nstatus\n```\n"),
    (re.compile(r"`\s*git\b"), "Run `git status` here."),
    (re.compile(r"(?m)^\s*(?:\$ )?git\s"), "\ngit status\n"),
    (re.compile(r"`\s*python3?\s"), "Run `python3 script.py` here."),
    (re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}"), "Run ${CLAUDE_PLUGIN_ROOT}/scripts/x here."),
)

GOOD_PARAGRAPH = """\
**create-plan 中の自 feature 文書修正の記録**: create-plan の間に、
オーケストレーター自身がその feature 自身の SPEC.md または REQUIREMENTS.md を
変更してコミットしたときは、`phase-state/create-plan.yaml` の
`orchestrator_doc_edits` にエントリを 1 件追記する。エントリには、変更した
ドキュメントの path、その時点のそのドキュメントの digest
（`references/artifact-digest.md` の `Calculation` で計算する）、変更の理由を
入れる。エントリの形は `references/phase-state.md` の `## Schema` を引く。
エントリは、ドキュメントの変更と同じ `commit-docs.sh` のコミットに含める
（phase-state の書き込みが取るコミットの形は `references/phase-state.md` の
「Update, commit, and exit-4 recovery」を引く）。digest の計算が失敗したときは、
エントリを書かない。そのコミットが exit 4 を返したときは、上記の
「**exit-4 リカバリ**」に従い、最新ツリーの上で修正を作り直し、作り直した本文から
digest を計算し直し、読み直した `phase-state/create-plan.yaml` にエントリを追記
して、エントリを同じコミットに含めて再試行する。このエントリを読むのは、
`references/contracts/spec-writer-contract.md` の「How the orchestrator chooses
each target's action before dispatch」が定める create-spec の action 決定である。
"""
GOOD_EXIT4_PARAGRAPH = """\
**exit-4 リカバリ**（commit-docs.sh の全呼び出し箇所で共通）: 戻り値 4 を受け
たら refresh して再試行する。2 回目も exit 4 ならそこでフェーズを中断し、状況を
ユーザーに報告する（無限リトライ
しない）。
"""
GOOD_NEXT_PARAGRAPH = """\
**batch: verify の cap 到達に対する停止条件の例外**（FR7）: 次の条件が
揃ったときにのみ適用される。
"""
GOOD_STEP_B = "\n".join(
    (
        "Intro paragraph.",
        "",
        GOOD_EXIT4_PARAGRAPH,
        GOOD_PARAGRAPH,
        GOOD_NEXT_PARAGRAPH,
    )
)


def step_b_section(skill_text):
    return _h2_section(skill_text, STEP_B_HEADING)


def _paragraph_starting(paragraphs, label):
    return _only(
        [i for i, p in enumerate(paragraphs) if p.startswith(label)],
        "paragraph starting with %r" % label,
    )


def check_placement(step_b):
    """The new paragraph is one paragraph of its own, the paragraph directly
    after the `**exit-4 リカバリ**` paragraph and directly before the
    `**batch: verify の cap 到達に対する停止条件の例外**` paragraph. Returns
    the new paragraph."""
    paragraphs = _paragraphs(step_b)
    at = _paragraph_starting(paragraphs, NEW_LABEL)
    exit4 = _paragraph_starting(paragraphs, EXIT4_LABEL)
    _require(
        exit4 == at - 1,
        "the paragraph directly before the new one is not the exit-4 paragraph",
    )
    _require(
        paragraphs[exit4].rstrip().endswith(EXIT4_END),
        "the exit-4 paragraph does not end with %r" % EXIT4_END,
    )
    _require(
        at + 1 < len(paragraphs) and paragraphs[at + 1].startswith(NEXT_LABEL),
        "the paragraph directly after the new one is not the batch exception",
    )
    return paragraphs[at]


def check_when_and_what(paragraph):
    _holds_all(paragraph, WHEN_AND_WHAT_NEEDLES, "the new paragraph")


def check_same_commit(paragraph):
    _holds_all(paragraph, SAME_COMMIT_NEEDLES, "the new paragraph")


def check_reader_citation(paragraph):
    _holds_all(paragraph, READER_CITATION_NEEDLES, "the new paragraph")


def check_calculation_failure(paragraph):
    _holds_all(paragraph, CALCULATION_FAILURE_NEEDLES, "the new paragraph")


def check_exit4(paragraph):
    _holds_all(paragraph, EXIT4_NEEDLES, "the new paragraph")


def check_paragraph_absences(paragraph):
    _holds_none(paragraph, PARAGRAPH_ABSENT_TOKENS, "the new paragraph")
    for pattern, _sample in PARAGRAPH_ABSENT_PATTERNS:
        _require(
            not pattern.search(paragraph),
            "the new paragraph matches the forbidden pattern %r" % pattern.pattern,
        )


def check_digest(block, expected, what):
    _require(_sha256(block) == expected, "%s changed (sha256 mismatch)" % what)


def _block(text, start_marker, end_marker, include_end):
    _require(text.count(start_marker) == 1, "expected one %r" % start_marker)
    start = text.index(start_marker)
    _require(end_marker in text[start:], "end marker %r not found" % end_marker)
    end = text.index(end_marker, start)
    return text[start : end + (len(end_marker) if include_end else 0)]


def exemption_block(step_b):
    return _block(step_b, EXEMPTION_START, EXEMPTION_END, True)


def commit_discipline_paragraph(step_b):
    _require(
        step_b.count(COMMIT_DISCIPLINE_START) == 1,
        "expected one commit-discipline paragraph",
    )
    return _paragraphs(step_b[step_b.index(COMMIT_DISCIPLINE_START) :])[0]


def exit4_paragraph(step_b):
    paragraphs = _paragraphs(step_b)
    return paragraphs[_paragraph_starting(paragraphs, EXIT4_LABEL)]


# ---------------------------------------------------------------------------
# AC-1: the schema example.
# ---------------------------------------------------------------------------


class TestAC1SchemaExample(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(PHASE_STATE_PATH)
        cls.block = schema_example_block(cls.text)

    def test_ac1_the_example_holds_one_record_with_one_complete_entry(self):
        self.assertEqual(len(check_example_record(self.block)), 1)

    def test_ac1_the_record_sits_after_the_previous_record_and_before_patches(self):
        check_example_position(self.block)

    def test_ac1_the_existing_example_lines_are_kept(self):
        check_existing_example_lines(self.block)

    def test_ac1_the_whole_example_passes(self):
        check_schema_example(self.block)

    # -- negative proofs ------------------------------------------------

    def test_ac1_proof_the_good_sample_passes(self):
        check_schema_example(GOOD_EXAMPLE)

    def test_ac1_proof_a_missing_record_fails(self):
        forged = GOOD_EXAMPLE.replace(RECORD_BLOCK, "")
        self.assertNotEqual(forged, GOOD_EXAMPLE)
        with self.assertRaises(AssertionError):
            check_schema_example(forged)

    def test_ac1_proof_a_second_top_level_line_fails(self):
        forged = GOOD_EXAMPLE.replace(RECORD_BLOCK, RECORD_BLOCK + RECORD_BLOCK)
        with self.assertRaises(AssertionError):
            check_schema_example(forged)

    def test_ac1_proof_no_entry_fails(self):
        forged = GOOD_EXAMPLE.replace(
            RECORD_BLOCK, "orchestrator_doc_edits: []   # `phase: create-plan` only; append-only\n"
        )
        with self.assertRaises(AssertionError):
            check_schema_example(forged)

    def test_ac1_proof_two_entries_fail(self):
        entry = RECORD_BLOCK.split("\n", 1)[1]
        forged = GOOD_EXAMPLE.replace(RECORD_BLOCK, RECORD_BLOCK + entry)
        self.assertNotEqual(forged, GOOD_EXAMPLE)
        with self.assertRaises(AssertionError):
            check_schema_example(forged)

    def test_ac1_proof_each_removed_key_fails(self):
        for key in ENTRY_KEYS:
            forged_block = re.sub(
                r"^(  - |    )%s: .*\n" % key, "", RECORD_BLOCK, flags=re.MULTILINE
            )
            self.assertNotEqual(forged_block, RECORD_BLOCK, key)
            forged = GOOD_EXAMPLE.replace(RECORD_BLOCK, forged_block)
            with self.assertRaises(AssertionError, msg=key):
                check_schema_example(forged)

    def test_ac1_proof_an_extra_key_fails(self):
        forged = GOOD_EXAMPLE.replace(
            RECORD_BLOCK, RECORD_BLOCK + "    produced_by: create-plan-run-0002\n"
        )
        with self.assertRaises(AssertionError):
            check_schema_example(forged)

    def test_ac1_proof_a_comment_without_the_phase_or_append_only_fails(self):
        for needle in ("`phase: create-plan` only", "append-only"):
            forged_block = RECORD_BLOCK.replace(needle, "")
            self.assertNotEqual(forged_block, RECORD_BLOCK, needle)
            with self.assertRaises(AssertionError, msg=needle):
                check_schema_example(GOOD_EXAMPLE.replace(RECORD_BLOCK, forged_block))
        no_comment = RECORD_BLOCK.replace(
            "        # `phase: create-plan` only; append-only", ""
        )
        self.assertNotEqual(no_comment, RECORD_BLOCK)
        with self.assertRaises(AssertionError):
            check_schema_example(GOOD_EXAMPLE.replace(RECORD_BLOCK, no_comment))

    def test_ac1_proof_a_path_outside_the_own_documents_fails(self):
        forged_block = RECORD_BLOCK.replace(
            "feature-docs/example/SPEC.md", "feature-docs/example/TASK.md"
        )
        self.assertNotEqual(forged_block, RECORD_BLOCK)
        with self.assertRaises(AssertionError):
            check_schema_example(GOOD_EXAMPLE.replace(RECORD_BLOCK, forged_block))

    def test_ac1_proof_the_wrong_position_fails(self):
        before = EXAMPLE_HEAD.replace("artifacts:", RECORD_BLOCK + "artifacts:", 1)
        with self.assertRaises(AssertionError):
            check_schema_example(before + EXAMPLE_TAIL)
        after = EXAMPLE_HEAD + EXAMPLE_TAIL + RECORD_BLOCK
        with self.assertRaises(AssertionError):
            check_schema_example(after)

    def test_ac1_proof_each_lost_existing_line_fails(self):
        for needle in EXISTING_EXAMPLE_LINES:
            forged = "\n".join(
                line for line in GOOD_EXAMPLE.split("\n") if not line.startswith(needle)
            )
            self.assertNotEqual(forged, GOOD_EXAMPLE, needle)
            with self.assertRaises(AssertionError, msg=needle):
                check_existing_example_lines(forged)

    def test_ac1_proof_the_block_finder_rejects_a_document_without_a_block(self):
        with self.assertRaises(AssertionError):
            schema_example_block("\n## Schema\n\nNo block here.\n")
        with self.assertRaises(AssertionError):
            schema_example_block("# Title\n\n```yaml\na: 1\n```\n")


# ---------------------------------------------------------------------------
# AC-2: the field table row.
# ---------------------------------------------------------------------------


class TestAC2FieldTableRow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(PHASE_STATE_PATH)
        cls.rows = top_level_table_rows(cls.text)

    def test_ac2_exactly_one_row_sits_directly_after_the_previous_record_row(self):
        check_row_position(self.rows)

    def test_ac2_the_row_states_its_shape_owners_and_lifetime(self):
        check_row_wording(field_table_row(self.rows))

    def test_ac2_the_row_carries_no_forbidden_token(self):
        check_row_absences(field_table_row(self.rows))

    def test_ac2_the_table_keeps_its_existing_rows(self):
        names = [_row_name(row) for row in self.rows]
        for field in (
            "schema_version",
            "artifacts",
            PREVIOUS_FIELD,
            "patches",
            "worker_runs",
            "classification",
            "last_error",
        ):
            self.assertIn(field, names)

    # -- negative proofs ------------------------------------------------

    def test_ac2_proof_the_good_sample_passes(self):
        check_row_position(GOOD_TABLE_ROWS)
        check_row_wording(field_table_row(GOOD_TABLE_ROWS))
        check_row_absences(field_table_row(GOOD_TABLE_ROWS))

    def test_ac2_proof_each_missing_wording_element_fails(self):
        check_row_wording(GOOD_ROW)
        for needle in ROW_NEEDLES:
            forged = _without(GOOD_ROW, needle)
            with self.assertRaises(AssertionError, msg=needle):
                check_row_wording(forged)

    def test_ac2_proof_each_forbidden_token_fails(self):
        check_row_absences(GOOD_ROW)
        for token in ROW_ABSENT_TOKENS:
            forged = GOOD_ROW + " " + token
            with self.assertRaises(AssertionError, msg=token):
                check_row_absences(forged)

    def test_ac2_proof_a_missing_row_fails(self):
        rows = [row for row in GOOD_TABLE_ROWS if _row_name(row) != RECORD_FIELD]
        with self.assertRaises(AssertionError):
            check_row_position(rows)
        with self.assertRaises(AssertionError):
            field_table_row(rows)

    def test_ac2_proof_a_second_row_fails(self):
        rows = GOOD_TABLE_ROWS[:3] + [GOOD_ROW] + GOOD_TABLE_ROWS[3:]
        with self.assertRaises(AssertionError):
            check_row_position(rows)
        with self.assertRaises(AssertionError):
            field_table_row(rows)

    def test_ac2_proof_a_row_in_another_place_fails(self):
        moved = [GOOD_TABLE_ROWS[2]] + GOOD_TABLE_ROWS[:2] + GOOD_TABLE_ROWS[3:]
        with self.assertRaises(AssertionError):
            check_row_position(moved)
        later = GOOD_TABLE_ROWS[:2] + [GOOD_TABLE_ROWS[3], GOOD_ROW]
        with self.assertRaises(AssertionError):
            check_row_position(later)

    def test_ac2_proof_the_table_finder_rejects_a_missing_or_repeated_marker(self):
        with self.assertRaises(AssertionError):
            top_level_table_rows("No marker here.\n| `a` | b |\n")
        with self.assertRaises(AssertionError):
            top_level_table_rows(
                "%s\n\n| `a` | b |\n\n%s\n\n| `c` | d |\n" % (TABLE_MARKER, TABLE_MARKER)
            )
        with self.assertRaises(AssertionError):
            top_level_table_rows("%s\n\nNo table follows.\n" % TABLE_MARKER)


# ---------------------------------------------------------------------------
# AC-3: the writer paragraph, its place, its trigger and its same-commit rule.
# ---------------------------------------------------------------------------


class TestAC3WriterParagraph(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(SKILL_PATH)
        cls.step_b = step_b_section(cls.text)
        cls.paragraph = check_placement(cls.step_b)

    def test_ac3_the_paragraph_sits_between_the_exit4_paragraph_and_the_batch_exception(self):
        check_placement(self.step_b)

    def test_ac3_the_paragraph_states_when_and_what_the_orchestrator_appends(self):
        check_when_and_what(self.paragraph)

    def test_ac3_the_paragraph_states_the_entry_is_in_the_same_commit(self):
        check_same_commit(self.paragraph)

    def test_ac3_the_paragraph_cites_the_reader(self):
        check_reader_citation(self.paragraph)

    # -- negative proofs ------------------------------------------------

    def test_ac3_proof_the_good_sample_passes(self):
        paragraph = check_placement(GOOD_STEP_B)
        check_when_and_what(paragraph)
        check_same_commit(paragraph)
        check_reader_citation(paragraph)

    def test_ac3_proof_each_missing_when_and_what_element_fails(self):
        for needle in WHEN_AND_WHAT_NEEDLES:
            forged = _without(GOOD_PARAGRAPH, needle)
            with self.assertRaises(AssertionError, msg=needle):
                check_when_and_what(forged)

    def test_ac3_proof_each_missing_same_commit_element_fails(self):
        for needle in SAME_COMMIT_NEEDLES:
            forged = _without(GOOD_PARAGRAPH, needle)
            with self.assertRaises(AssertionError, msg=needle):
                check_same_commit(forged)

    def test_ac3_proof_each_missing_reader_citation_element_fails(self):
        for needle in READER_CITATION_NEEDLES:
            forged = _without(GOOD_PARAGRAPH, needle)
            with self.assertRaises(AssertionError, msg=needle):
                check_reader_citation(forged)

    def test_ac3_proof_a_missing_paragraph_fails(self):
        forged = GOOD_STEP_B.replace(GOOD_PARAGRAPH, "")
        self.assertNotEqual(forged, GOOD_STEP_B)
        with self.assertRaises(AssertionError):
            check_placement(forged)

    def test_ac3_proof_a_paragraph_before_the_exit4_paragraph_fails(self):
        forged = "\n".join(
            ("Intro paragraph.", "", GOOD_PARAGRAPH, GOOD_EXIT4_PARAGRAPH, GOOD_NEXT_PARAGRAPH)
        )
        with self.assertRaises(AssertionError):
            check_placement(forged)

    def test_ac3_proof_a_paragraph_after_the_batch_exception_fails(self):
        forged = "\n".join(
            ("Intro paragraph.", "", GOOD_EXIT4_PARAGRAPH, GOOD_NEXT_PARAGRAPH, GOOD_PARAGRAPH)
        )
        with self.assertRaises(AssertionError):
            check_placement(forged)

    def test_ac3_proof_a_paragraph_separated_from_the_exit4_paragraph_fails(self):
        forged = GOOD_STEP_B.replace(
            GOOD_PARAGRAPH, "Another paragraph in between.\n\n" + GOOD_PARAGRAPH
        )
        with self.assertRaises(AssertionError):
            check_placement(forged)

    def test_ac3_proof_a_paragraph_split_in_two_before_the_batch_exception_fails(self):
        forged = GOOD_STEP_B.replace(
            GOOD_NEXT_PARAGRAPH, "A second paragraph.\n\n" + GOOD_NEXT_PARAGRAPH
        )
        with self.assertRaises(AssertionError):
            check_placement(forged)

    def test_ac3_proof_a_repeated_label_fails(self):
        forged = GOOD_STEP_B + "\n" + NEW_LABEL + " again.\n"
        with self.assertRaises(AssertionError):
            check_placement(forged)

    def test_ac3_proof_the_step_b_finder_rejects_a_document_without_the_heading(self):
        with self.assertRaises(AssertionError):
            step_b_section("# Skill\n\n## Step A: x\n\ntext\n")
        with self.assertRaises(AssertionError):
            step_b_section("# Skill\n\n```\n%s\n```\n" % STEP_B_HEADING)


# ---------------------------------------------------------------------------
# AC-4: the failure and exit-4 statements.
# ---------------------------------------------------------------------------


class TestAC4FailureAndExit4(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.paragraph = check_placement(step_b_section(_read(SKILL_PATH)))

    def test_ac4_no_entry_is_written_when_the_digest_calculation_fails(self):
        check_calculation_failure(self.paragraph)

    def test_ac4_an_exit4_follows_the_recovery_and_retries_with_the_entry(self):
        check_exit4(self.paragraph)

    # -- negative proofs ------------------------------------------------

    def test_ac4_proof_the_good_sample_passes(self):
        check_calculation_failure(GOOD_PARAGRAPH)
        check_exit4(GOOD_PARAGRAPH)

    def test_ac4_proof_each_missing_calculation_failure_element_fails(self):
        for needle in CALCULATION_FAILURE_NEEDLES:
            forged = _without(GOOD_PARAGRAPH, needle)
            with self.assertRaises(AssertionError, msg=needle):
                check_calculation_failure(forged)

    def test_ac4_proof_each_missing_exit4_element_fails(self):
        for needle in EXIT4_NEEDLES:
            forged = _without(GOOD_PARAGRAPH, needle)
            with self.assertRaises(AssertionError, msg=needle):
                check_exit4(forged)


# ---------------------------------------------------------------------------
# AC-5: absences and unchanged neighbours.
# ---------------------------------------------------------------------------


class TestAC5Absences(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.paragraph = check_placement(step_b_section(_read(SKILL_PATH)))

    def test_ac5_the_paragraph_carries_no_forbidden_token_or_command(self):
        check_paragraph_absences(self.paragraph)

    # -- negative proofs ------------------------------------------------

    def test_ac5_proof_the_good_sample_passes(self):
        check_paragraph_absences(GOOD_PARAGRAPH)

    def test_ac5_proof_each_forbidden_token_fires(self):
        for token in PARAGRAPH_ABSENT_TOKENS:
            forged = GOOD_PARAGRAPH + token + "\n"
            with self.assertRaises(AssertionError, msg=token):
                check_paragraph_absences(forged)

    def test_ac5_proof_each_forbidden_command_pattern_fires(self):
        for pattern, sample in PARAGRAPH_ABSENT_PATTERNS:
            self.assertTrue(pattern.search(sample), pattern.pattern)
            forged = GOOD_PARAGRAPH + sample
            with self.assertRaises(AssertionError, msg=pattern.pattern):
                check_paragraph_absences(forged)


class TestAC5UnchangedNeighbours(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.step_b = step_b_section(_read(SKILL_PATH))

    def test_ac5_the_create_plan_exemption_block_is_unchanged(self):
        check_digest(exemption_block(self.step_b), EXEMPTION_SHA256, "the exemption block")

    def test_ac5_the_commit_discipline_paragraph_is_unchanged(self):
        check_digest(
            commit_discipline_paragraph(self.step_b),
            COMMIT_DISCIPLINE_SHA256,
            "the commit-discipline paragraph",
        )

    def test_ac5_the_exit4_paragraph_is_unchanged(self):
        check_digest(
            exit4_paragraph(self.step_b), EXIT4_PARAGRAPH_SHA256, "the exit-4 paragraph"
        )

    # -- negative proofs ------------------------------------------------

    def test_ac5_proof_an_edited_block_fails_its_digest_check(self):
        for block, expected in (
            (exemption_block(self.step_b), EXEMPTION_SHA256),
            (commit_discipline_paragraph(self.step_b), COMMIT_DISCIPLINE_SHA256),
            (exit4_paragraph(self.step_b), EXIT4_PARAGRAPH_SHA256),
        ):
            check_digest(block, expected, "the live block")
            with self.assertRaises(AssertionError):
                check_digest(block + " ", expected, "the edited block")
            with self.assertRaises(AssertionError):
                check_digest(block[:-1], expected, "the shortened block")

    def test_ac5_proof_the_block_finders_reject_a_document_without_the_block(self):
        with self.assertRaises(AssertionError):
            exemption_block("No exemption here.")
        with self.assertRaises(AssertionError):
            commit_discipline_paragraph("No paragraph here.")
        with self.assertRaises(AssertionError):
            commit_discipline_paragraph(
                COMMIT_DISCIPLINE_START + "\n\n" + COMMIT_DISCIPLINE_START + "\n"
            )
        with self.assertRaises(AssertionError):
            exit4_paragraph("No paragraph here.")


# ---------------------------------------------------------------------------
# AC-6: this module.
# ---------------------------------------------------------------------------


class TestAC6OwnModule(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))

    def test_ac6_imports_are_all_standard_library(self):
        imported = set()
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                imported.add((node.module or "").split(".")[0])
        self.assertEqual(sorted(imported - set(sys.stdlib_module_names)), [])

    def test_ac6_the_module_never_writes_a_file(self):
        writers = {"write_text", "write_bytes", "write", "writelines", "mkdir", "unlink"}
        calls = []
        for node in ast.walk(self.tree):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute) and node.func.attr in writers:
                    calls.append(node.func.attr)
                if isinstance(node.func, ast.Name) and node.func.id == "open":
                    calls.append("open")
        self.assertEqual(calls, [])

    def test_ac6_the_documents_exist_and_are_read_from_the_working_tree(self):
        self.assertTrue(PHASE_STATE_PATH.is_file())
        self.assertTrue(SKILL_PATH.is_file())
        self.assertEqual(PHASE_STATE_PATH.parent.name, "references")
        self.assertEqual(SKILL_PATH.parent.name, "develop")


if __name__ == "__main__":
    unittest.main()
