"""Document-content tests for task0004 (scenario-id-ts-hyphen): the
planner-side documents describe the TS-n requirement and its check.

Covers task0004 Acceptance Criteria
(feature-docs/scenario-id-ts-hyphen/tasks/task0004.md):

- AC-1: `em-workflow/references/phases/create-plan-phase.md` section 9's
  validator-implemented list has a bullet naming VERIFICATION.md,
  `tasks_patch.entries[].plan`, the `TASK.md` exclusion, the `completed`
  status, fenced code blocks and HTML comments as skipped regions, and
  `scenario-id-form`; the bullet says rework-planner output is not checked.
- AC-2: section 9's `--feature-dir` paragraph names the scenario-ID form
  check among the checks skipped together when `--feature-dir` is dropped
  (the sentence's count matches the list); the section's heading, its
  not-implemented list and its canonical invocation block are unchanged
  (pinned by sha256 of the base revision).
- AC-3: `em-workflow/agents/implementation-planner.md`'s step 5 section states
  that a new VERIFICATION.md and task plans use the TS-n form only, cites the
  plan-writing skill's scenario ID rule, and says a hyphen-less ID is
  rejected by the validator.
- AC-4: that file's `## Gate option vocabulary` section is byte-identical
  (sha256 pin) and its `###` step headings are unchanged.
- AC-5: `em-workflow/references/contracts/planner-contract.md` has a `##`
  section before `## Gate option vocabulary` stating the TS-n-only
  requirement, the rejection with code `scenario-id-form` for `completed`
  results validated with `--feature-dir`, and that rework-planner output is
  outside the check; the gate_id set and the Gate option vocabulary table are
  unchanged.
- AC-6: none of the three documents contains a hyphen-less scenario ID, found
  by the Hyphen-less ID detection rule (IMPLEMENTATION.md Shared Components)
  applied to the whole file. This module applies the rule itself and does not
  import the validator script.
- AC-7: this module asserts AC-1 to AC-6 with a negative proof per matcher
  against a pre-change excerpt (or, where the pre-change files hold no
  violation, against a forged sample), and imports the standard library only.

Per the repository convention that no test module imports another, the small
extraction helpers are duplicated here. Files are located relative to this
module's path, headings are anchored literally, and phrase assertions compare
whitespace-normalized text so a line wrap does not break them.

The pins below were computed from the base revision (before task0004).
"""

import ast
import hashlib
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"
PHASE_PATH = PLUGIN_ROOT / "references" / "phases" / "create-plan-phase.md"
PLANNER_PATH = PLUGIN_ROOT / "agents" / "implementation-planner.md"
CONTRACT_PATH = PLUGIN_ROOT / "references" / "contracts" / "planner-contract.md"

SEC9_MARKER = "## 9. Planning invariants"
SEC9_HEADING_LINE = (
    "## 9. Planning invariants — the validator-implemented subset, and human "
    "review for the rest"
)
SEC10_MARKER = "## 10. Atomic patch application"
IMPLEMENTED_LIST_INTRO = "mechanically implements only the"
NOT_IMPLEMENTED_MARKER = (
    "The following are named as planning invariants but are **not implemented"
)
CANONICAL_MARKER = "**Canonical validator invocation**"
DIGEST_SOURCE_MARKER = "The `--digest-source` file holds"

STEP5_MARKER = "### 5. VERIFICATION.md"
STEP6_MARKER = "### 6. Populate requirements mapping"
GATE_VOCAB_MARKER = "## Gate option vocabulary"

# sha256 pins, computed from the base revision.
PHASE_NOT_IMPLEMENTED_SHA256 = (
    "e67e13bba925f41d466fcffebfbae6a0db0483b933beaa5a60fbfa4ef05eaa1c"
)
PHASE_CANONICAL_INVOCATION_SHA256 = (
    "dc78a4e1ba2488e8dff4af9a8112aa9b0d8d5dff2cb3fa76a4fc7b6e1964f4dc"
)
# task0004 of subagent-report-write-block adds exactly these two lines to the
# canonical invocation (the base inputs of the validator). The pin above is
# still the base revision's block: the test removes these two lines from the
# live block before comparing, so everything else stays pinned.
PHASE_CANONICAL_INVOCATION_ADDED_LINES = (
    "    --target-repo {integration worktree} \\\n",
    "    --base-commit {integration tip} \\\n",
)
PLANNER_GATE_VOCAB_SHA256 = (
    "ab908c0af5220c9436b225077c4ca2ddec3ecacb5ca52f5553ef228ec3da7ef8"
)
CONTRACT_GATE_VOCAB_SHA256 = (
    "707f129ea95b74d61b9f6b375721e82d06f179ca2301b016a072c56e9575caf9"
)

PLANNER_STEP_HEADINGS = [
    "### 1. Analyze SPEC.md",
    "### 2. TBD requirement detection (MANDATORY)",
    "### 2a. Threat modeling (MANDATORY)",
    "### 3. Cross-task design decisions → IMPLEMENTATION.md",
    "### 4. Task decomposition → tasks/taskNNNN.md + workflow patch",
    "### 5. VERIFICATION.md (feature-wide, this agent OWNS it)",
    "### 6. Populate requirements mapping (MANDATORY)",
    "### 7. Handle existing files",
    "### 8. Save and report",
]

# The contract's headings before this task, in order. The one section this
# task adds is the only heading allowed on top of these.
# Refreshed by plan-feature-docs-route/task0002: the contract gained the H2
# `## Other-feature documents` (after `## Scope & concurrency assumption`) and
# the H3 `### feature_docs_correction (dispatch-resolved value)` (after the
# `path_correction` subsection). The earlier headings and their order are kept.
CONTRACT_H2_BASE = [
    "## Responsibility",
    "## Additional input: `planning_inputs`",
    "## Question packet bundling rule",
    "## digest_inputs",
    "## `completed` payload",
    "## Prohibited fields",
    "## Task decomposition, complexity and domains vocabulary",
    "## Scope & concurrency assumption",
    "## Other-feature documents",
    "## Gate option vocabulary",
]
CONTRACT_H3_BASE = [
    "### Minimal-tier `TASK.md` append (SC-3)",
    "### plugin_versioning (dispatch-resolved value)",
    "### path_correction (dispatch-resolved value)",
    "### feature_docs_correction (dispatch-resolved value)",
]
CONTRACT_GATE_IDS = frozenset(
    {
        "create-plan.tbd-resolution",
        "create-plan.license-conflict",
        "create-plan.existing-files",
    }
)

# ---------------------------------------------------------------------------
# Pre-change excerpts (verbatim from the base revision) used as the input of
# the negative proofs.
# ---------------------------------------------------------------------------

PRE_CHANGE_PHASE_SEC9_IMPLEMENTED_LIST = """\
Of the invariants a planning result could in principle be checked against,
`scripts/validate-worker-output.py` mechanically implements only the
following. This list is restricted to what the script actually does, not
to every invariant that would be desirable:

- Every task plan has a non-empty Acceptance Criteria section.
- A task's `files` and its task plan's Files section agree as a union.
- `skills` / `domains` / `complexity` match their registered vocabularies —
  **only when `--registries` is supplied**; the check silently does not run
  if it is omitted, it does not fail.
- A task's declared `requirements` already exist in `workflow.yaml` —
  **only when `--workflow` is supplied**; likewise silently skipped, not
  failed, when omitted.
- Shared contracts between parallel tasks are documented in
  IMPLEMENTATION.md, checked as: whenever more than one task declares the
  same file in `files`, IMPLEMENTATION.md must contain a `## Shared
  Components` section. This is a deliberate approximation of "a shared
  contract exists where one is needed" (same-file overlap is neither
  necessary nor sufficient for that), not a defect to fix in this task.

"""

PRE_CHANGE_PHASE_FEATURE_DIR_PARAGRAPH = """\
`--input-envelope` is mandatory for `--kind worker-result` — the script
exits 2 without it. `--workflow`, `--registries`, `--feature-dir` and
`--phase-state` are optional in the script's own argument parser, but each
one that is omitted here silently narrows validation rather than failing loudly:
dropping `--workflow` skips the requirement-existence check, dropping
`--registries` skips the vocabulary check, dropping `--feature-dir` skips
the Acceptance-Criteria, files-union and Shared-Components checks together
(all three are read from the task plan and IMPLEMENTATION.md files under
`--feature-dir`), and dropping `--phase-state` skips the
duplicate-patch-identifier idempotency check. Running anything less than the
invocation above is a coverage regression, not a smaller valid invocation.
"""

PRE_CHANGE_PLANNER_STEP5 = """\
### 5. VERIFICATION.md (feature-wide, this agent OWNS it)

Write `feature-docs/{feature}/VERIFICATION.md` from the plan-writing skill's
template: build/test/format commands (from workflow.yaml
project.components), test scenarios extracted from SPEC.md (TS-n IDs),
success criteria, functional-requirements coverage, E2E / manual sections.
This documents the INTEGRATED verification run by the verify phase — task-
level acceptance criteria live in the task plans.

When THREAT-MODEL.md's verdict is `threats-identified`, add one item per
TM-n to the Performance / Security Verification section, keyed by the
TM-n and stating how it is checked, and count each in the Verification
Summary.

"""

PRE_CHANGE_CONTRACT_TAIL = """\
## Scope & concurrency assumption

During dispatch, only the orchestrator and the dispatched worker may create,
modify or delete files in the integration worktree (design-input.md
5.11.3); this assumption applies for the interval from scope-snapshot
capture through scope verification, and is not a permanent constraint on
the plugin as a whole.

## Gate option vocabulary

The option vocabulary a batch-policies.yaml `option_id` is checked against.

| gate_id | option_id | meaning |
|---|---|---|
| `create-plan.tbd-resolution` | `assume` | placeholder row. |
"""


# ---------------------------------------------------------------------------
# Helpers.
# ---------------------------------------------------------------------------

_FENCE_RE = re.compile(r"```.*?```", re.DOTALL)
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)
_SCENARIO_ID_RE = re.compile(r"TS-?\d+")
_ASCII_ALNUM_RE = re.compile(r"[A-Za-z0-9]")

_COUNT_WORDS = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6}


def _read(path):
    return path.read_text(encoding="utf-8")


def _norm(text):
    """Collapse whitespace runs (including line-wrap newlines) to one space."""
    return re.sub(r"\s+", " ", text).strip()


def _sha256(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _between(text, start_marker, end_marker):
    start = text.index(start_marker)
    end = text.index(end_marker, start + len(start_marker))
    return text[start:end]


def _require(condition, message):
    if not condition:
        raise AssertionError(message)


def _strip_noise(text):
    """Remove fenced code blocks, then HTML comments (the validator's
    noise-stripping step)."""
    text = _FENCE_RE.sub("", text)
    return _HTML_COMMENT_RE.sub("", text)


def hyphenless_ids(text):
    """The Hyphen-less ID detection rule (IMPLEMENTATION.md Shared
    Components): after noise stripping, the matches of `TS-?\\d+` that
    contain no hyphen and whose immediately preceding character is not an
    ASCII letter or digit. A match at the very start counts; inline code
    spans are not removed; a non-ASCII preceding character does not stop a
    match from counting."""
    stripped = _strip_noise(text)
    found = set()
    for match in _SCENARIO_ID_RE.finditer(stripped):
        if "-" in match.group(0):
            continue
        if match.start() > 0 and _ASCII_ALNUM_RE.match(stripped[match.start() - 1]):
            continue
        found.add(match.group(0))
    return found


def _headings(text, prefix):
    """Heading lines starting with `prefix`, outside fenced code blocks."""
    return [
        line
        for line in _FENCE_RE.sub("", text).splitlines()
        if line.startswith(prefix)
    ]


def _bullets(block):
    """Top-level `- ` bullets of `block`, each joined and
    whitespace-normalized. A bullet ends at a blank line or the next
    bullet."""
    bullets = []
    current = None
    for line in block.splitlines():
        if line.startswith("- "):
            if current is not None:
                bullets.append(current)
            current = [line[2:]]
        elif not line.strip():
            if current is not None:
                bullets.append(current)
                current = None
        elif current is not None:
            current.append(line)
    if current is not None:
        bullets.append(current)
    return [_norm(" ".join(parts)) for parts in bullets]


def _paragraphs(text):
    return [p for p in re.split(r"\n\s*\n", text) if p.strip()]


def _split_h2(text):
    """[(heading line, body text)] for every `## ` heading outside fenced
    code blocks, in document order."""
    fence_spans = [m.span() for m in _FENCE_RE.finditer(text)]

    def in_fence(pos):
        return any(start <= pos < end for start, end in fence_spans)

    positions = [
        m for m in re.finditer(r"^## .*$", text, re.MULTILINE) if not in_fence(m.start())
    ]
    sections = []
    for i, match in enumerate(positions):
        end = positions[i + 1].start() if i + 1 < len(positions) else len(text)
        sections.append((match.group(0), text[match.end() : end]))
    return sections


# ---------------------------------------------------------------------------
# AC-1: the validator-implemented list gains the scenario-ID form bullet.
# ---------------------------------------------------------------------------


def _implemented_list_block(text):
    sec9 = _between(text, SEC9_MARKER, SEC10_MARKER)
    return _between(sec9, IMPLEMENTED_LIST_INTRO, NOT_IMPLEMENTED_MARKER)


def _check_ac1_bullet(list_block):
    bullets = _bullets(list_block)
    hits = [b for b in bullets if "scenario-id-form" in b]
    _require(
        len(hits) == 1,
        "expected exactly one validator-implemented bullet naming "
        "`scenario-id-form`, found %d" % len(hits),
    )
    bullet = hits[0]
    for needle in (
        "`scenario-id-form`",
        "VERIFICATION.md",
        "`tasks_patch.entries[].plan`",
        "`TASK.md`",
        "final path segment",
        "`completed`",
        "`--feature-dir`",
        "fenced code blocks",
        "HTML comments",
        "hyphen-less scenario ID",
        "`rework-planner` output is not checked",
    ):
        _require(needle in bullet, "bullet lacks %r" % needle)
    return bullet


class TestAC1ImplementedListBullet(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(PHASE_PATH)
        cls.block = _implemented_list_block(cls.text)

    def test_list_block_found_non_vacuous(self):
        self.assertGreaterEqual(len(_bullets(self.block)), 5)

    def test_bullet_names_every_required_element(self):
        _check_ac1_bullet(self.block)

    def test_bullet_precedes_the_not_implemented_list(self):
        self.assertLess(
            self.text.index("`scenario-id-form`"),
            self.text.index(NOT_IMPLEMENTED_MARKER),
        )

    def test_not_implemented_list_does_not_hold_the_check(self):
        sec9 = _between(self.text, SEC9_MARKER, SEC10_MARKER)
        not_implemented = _between(sec9, NOT_IMPLEMENTED_MARKER, CANONICAL_MARKER)
        self.assertNotIn("scenario-id-form", not_implemented)

    # -- negative proofs ------------------------------------------------

    def test_matcher_rejects_pre_change_list(self):
        block = PRE_CHANGE_PHASE_SEC9_IMPLEMENTED_LIST
        self.assertGreaterEqual(len(_bullets(block)), 5)
        with self.assertRaises(AssertionError):
            _check_ac1_bullet(block)

    def test_matcher_rejects_bullet_missing_task_md_exclusion(self):
        forged = PRE_CHANGE_PHASE_SEC9_IMPLEMENTED_LIST + (
            "- For a `completed` result with `--feature-dir`, VERIFICATION.md\n"
            "  and every `tasks_patch.entries[].plan` contain no hyphen-less\n"
            "  scenario ID outside fenced code blocks and HTML comments\n"
            "  (`scenario-id-form`). `rework-planner` output is not checked.\n"
        )
        with self.assertRaises(AssertionError):
            _check_ac1_bullet(forged)

    def test_matcher_rejects_bullet_missing_rework_planner_statement(self):
        forged = PRE_CHANGE_PHASE_SEC9_IMPLEMENTED_LIST + (
            "- For a `completed` result with `--feature-dir`, VERIFICATION.md\n"
            "  and every `tasks_patch.entries[].plan` (except a plan whose\n"
            "  final path segment is `TASK.md`) contain no hyphen-less\n"
            "  scenario ID outside fenced code blocks and HTML comments\n"
            "  (`scenario-id-form`).\n"
        )
        with self.assertRaises(AssertionError):
            _check_ac1_bullet(forged)

    def test_matcher_accepts_a_complete_forged_bullet(self):
        forged = PRE_CHANGE_PHASE_SEC9_IMPLEMENTED_LIST + (
            "- For a `completed` result with `--feature-dir`, VERIFICATION.md\n"
            "  and every `tasks_patch.entries[].plan` (except a plan whose\n"
            "  final path segment is `TASK.md`) contain no hyphen-less\n"
            "  scenario ID outside fenced code blocks and HTML comments\n"
            "  (`scenario-id-form`). `rework-planner` output is not checked.\n"
        )
        _check_ac1_bullet(forged)


# ---------------------------------------------------------------------------
# AC-2: the --feature-dir paragraph; the unchanged parts of section 9.
# ---------------------------------------------------------------------------

_FEATURE_DIR_CLAUSE_RE = re.compile(
    r"dropping `--feature-dir` skips (?P<items>.+?) checks together "
    r"\(all (?P<count>\w+) are read from"
)


def _check_ac2_clause(sec9_text):
    match = _FEATURE_DIR_CLAUSE_RE.search(_norm(sec9_text))
    _require(match is not None, "no `--feature-dir` skip clause found")
    items_text = re.sub(r"^the\s+", "", match.group("items"))
    items = [i.strip() for i in re.split(r",\s*|\s+and\s+", items_text) if i.strip()]
    count = _COUNT_WORDS.get(match.group("count"))
    _require(count is not None, "count word %r not recognised" % match.group("count"))
    _require(
        len(items) == count,
        "the clause says 'all %s' but lists %d checks: %r"
        % (match.group("count"), len(items), items),
    )
    _require(
        "scenario-ID form" in items,
        "the skipped checks do not include the scenario-ID form check: %r" % items,
    )
    return items


class TestAC2FeatureDirParagraphAndUnchangedParts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(PHASE_PATH)
        cls.sec9 = _between(cls.text, SEC9_MARKER, SEC10_MARKER)

    def test_feature_dir_clause_lists_the_check_with_a_matching_count(self):
        items = _check_ac2_clause(self.sec9)
        self.assertIn("Acceptance-Criteria", items)
        self.assertIn("files-union", items)
        self.assertIn("Shared-Components", items)

    def test_section_heading_line_unchanged(self):
        self.assertEqual(self.sec9.splitlines()[0], SEC9_HEADING_LINE)

    def test_not_implemented_list_unchanged(self):
        block = _between(self.sec9, NOT_IMPLEMENTED_MARKER, CANONICAL_MARKER)
        self.assertEqual(_sha256(block), PHASE_NOT_IMPLEMENTED_SHA256)

    def test_canonical_invocation_block_unchanged(self):
        block = _between(self.sec9, CANONICAL_MARKER, DIGEST_SOURCE_MARKER)
        for added in PHASE_CANONICAL_INVOCATION_ADDED_LINES:
            self.assertEqual(block.count(added), 1, added)
            block = block.replace(added, "")
        self.assertEqual(_sha256(block), PHASE_CANONICAL_INVOCATION_SHA256)

    # -- negative proofs ------------------------------------------------

    def test_clause_matcher_rejects_pre_change_paragraph(self):
        self.assertIn("--feature-dir", PRE_CHANGE_PHASE_FEATURE_DIR_PARAGRAPH)
        with self.assertRaises(AssertionError):
            _check_ac2_clause(PRE_CHANGE_PHASE_FEATURE_DIR_PARAGRAPH)

    def test_clause_matcher_rejects_a_count_that_does_not_match_the_list(self):
        forged = PRE_CHANGE_PHASE_FEATURE_DIR_PARAGRAPH.replace(
            "files-union and Shared-Components checks together",
            "files-union, Shared-Components and scenario-ID form checks together",
        )
        self.assertIn("all three are read", forged)
        with self.assertRaises(AssertionError):
            _check_ac2_clause(forged)

    def test_clause_matcher_accepts_a_matching_forged_paragraph(self):
        forged = PRE_CHANGE_PHASE_FEATURE_DIR_PARAGRAPH.replace(
            "files-union and Shared-Components checks together",
            "files-union, Shared-Components and scenario-ID form checks together",
        ).replace("all three are read", "all four are read")
        self.assertEqual(
            _check_ac2_clause(forged),
            [
                "Acceptance-Criteria",
                "files-union",
                "Shared-Components",
                "scenario-ID form",
            ],
        )

    def test_pin_digest_detects_a_mutated_block(self):
        block = _between(self.sec9, NOT_IMPLEMENTED_MARKER, CANONICAL_MARKER)
        self.assertNotEqual(
            _sha256(block + "- extra bullet.\n"), PHASE_NOT_IMPLEMENTED_SHA256
        )


# ---------------------------------------------------------------------------
# AC-3: implementation-planner.md step 5.
# ---------------------------------------------------------------------------


def _check_ac3_step5(step5_text):
    paragraphs = [p for p in _paragraphs(step5_text) if "scenario ID rule" in p]
    _require(
        len(paragraphs) == 1,
        "expected exactly one step 5 paragraph citing the scenario ID rule, "
        "found %d" % len(paragraphs),
    )
    paragraph = _norm(paragraphs[0])
    for needle in (
        "VERIFICATION.md",
        "task plan",
        "TS-n",
        "form only",
        "skills/plan-writing/SKILL.md",
        "scenario ID rule",
        "hyphen-less",
        "rejected by",
        "`scenario-id-form`",
    ):
        _require(needle in paragraph, "step 5 statement lacks %r" % needle)
    return paragraph


class TestAC3PlannerStep5Statement(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(PLANNER_PATH)
        cls.step5 = _between(cls.text, STEP5_MARKER, STEP6_MARKER)

    def test_step5_section_found_non_vacuous(self):
        self.assertIn("VERIFICATION.md", self.step5)

    def test_step5_states_ts_n_only_cites_rule_and_rejection(self):
        _check_ac3_step5(self.step5)

    def test_statement_names_the_validator(self):
        paragraph = _check_ac3_step5(self.step5)
        self.assertIn("scripts/validate-worker-output.py", paragraph)

    # -- negative proofs ------------------------------------------------

    def test_matcher_rejects_pre_change_step5(self):
        self.assertIn("TS-n IDs", PRE_CHANGE_PLANNER_STEP5)
        with self.assertRaises(AssertionError):
            _check_ac3_step5(PRE_CHANGE_PLANNER_STEP5)

    def test_matcher_rejects_statement_without_rejection(self):
        forged = PRE_CHANGE_PLANNER_STEP5 + (
            "A new VERIFICATION.md and every task plan use the TS-n scenario\n"
            "ID form only, following the scenario ID rule in\n"
            "`skills/plan-writing/SKILL.md`.\n"
        )
        with self.assertRaises(AssertionError):
            _check_ac3_step5(forged)

    def test_matcher_accepts_a_complete_forged_statement(self):
        forged = PRE_CHANGE_PLANNER_STEP5 + (
            "A new VERIFICATION.md and every task plan use the TS-n scenario\n"
            "ID form only, following the scenario ID rule in\n"
            "`skills/plan-writing/SKILL.md`. A hyphen-less scenario ID in\n"
            "either is rejected by the validator (`scenario-id-form`).\n"
        )
        _check_ac3_step5(forged)


# ---------------------------------------------------------------------------
# AC-4: implementation-planner.md pinned surfaces.
# ---------------------------------------------------------------------------


class TestAC4PlannerPinnedSurfaces(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(PLANNER_PATH)

    def test_gate_option_vocabulary_section_byte_identical(self):
        section = self.text[self.text.index(GATE_VOCAB_MARKER) :]
        self.assertEqual(_sha256(section), PLANNER_GATE_VOCAB_SHA256)

    def test_step_headings_unchanged(self):
        self.assertEqual(_headings(self.text, "### "), PLANNER_STEP_HEADINGS)

    def test_new_text_sits_before_the_gate_option_vocabulary(self):
        self.assertLess(
            self.text.index("scenario ID rule"), self.text.index(GATE_VOCAB_MARKER)
        )

    # -- negative proofs ------------------------------------------------

    def test_digest_pin_detects_a_mutated_vocabulary_section(self):
        section = self.text[self.text.index(GATE_VOCAB_MARKER) :]
        self.assertNotEqual(_sha256(section + "\n"), PLANNER_GATE_VOCAB_SHA256)
        self.assertNotEqual(
            _sha256(section.replace("assume", "assumed", 1)),
            PLANNER_GATE_VOCAB_SHA256,
        )

    def test_heading_pin_detects_a_renamed_or_removed_heading(self):
        renamed = self.text.replace(
            "### 5. VERIFICATION.md (feature-wide, this agent OWNS it)",
            "### 5. VERIFICATION.md",
        )
        self.assertNotEqual(_headings(renamed, "### "), PLANNER_STEP_HEADINGS)
        removed = self.text.replace("### 6. Populate requirements mapping (MANDATORY)", "")
        self.assertNotEqual(_headings(removed, "### "), PLANNER_STEP_HEADINGS)


# ---------------------------------------------------------------------------
# AC-5: planner-contract.md gains a section before the Gate option vocabulary.
# ---------------------------------------------------------------------------


def _check_ac5_section(contract_text):
    sections = _split_h2(contract_text)
    headings = [h for h, _ in sections]
    _require(GATE_VOCAB_MARKER in headings, "no Gate option vocabulary heading")
    vocab_index = headings.index(GATE_VOCAB_MARKER)
    hits = [i for i, (_, body) in enumerate(sections) if "scenario-id-form" in body]
    _require(
        len(hits) == 1,
        "expected exactly one `##` section naming `scenario-id-form`, found %d"
        % len(hits),
    )
    _require(hits[0] < vocab_index, "the section is not before the vocabulary")
    heading, body = sections[hits[0]]
    normalized = _norm(body)
    for needle in (
        "TS-n",
        "form only",
        "scripts/validate-worker-output.py",
        "`completed`",
        "`--feature-dir`",
        "hyphen-less scenario ID",
        "fenced code blocks",
        "HTML comments",
        "`scenario-id-form`",
        "`rework-planner` output is outside this check",
        "skills/plan-writing/SKILL.md",
        "does not restate",
    ):
        _require(needle in normalized, "section %r lacks %r" % (heading, needle))
    return heading


class TestAC5ContractSection(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(CONTRACT_PATH)

    def test_section_states_requirement_rejection_and_scope(self):
        _check_ac5_section(self.text)

    def test_existing_headings_unchanged_apart_from_the_new_section(self):
        new_heading = _check_ac5_section(self.text)
        h2 = [h for h in _headings(self.text, "## ") if h != new_heading]
        self.assertEqual(h2, CONTRACT_H2_BASE)
        self.assertEqual(_headings(self.text, "### "), CONTRACT_H3_BASE)

    def test_gate_option_vocabulary_section_byte_identical(self):
        section = self.text[self.text.index(GATE_VOCAB_MARKER) :]
        self.assertEqual(_sha256(section), CONTRACT_GATE_VOCAB_SHA256)

    def test_gate_id_set_unchanged(self):
        section = self.text[self.text.index(GATE_VOCAB_MARKER) :]
        gate_ids = set(re.findall(r"`(create-plan\.[a-z-]+)`", section))
        self.assertEqual(gate_ids, set(CONTRACT_GATE_IDS))

    # -- negative proofs ------------------------------------------------

    def test_matcher_rejects_pre_change_contract_excerpt(self):
        self.assertIn(GATE_VOCAB_MARKER, PRE_CHANGE_CONTRACT_TAIL)
        with self.assertRaises(AssertionError):
            _check_ac5_section(PRE_CHANGE_CONTRACT_TAIL)

    def test_matcher_rejects_section_placed_after_the_vocabulary(self):
        forged = PRE_CHANGE_CONTRACT_TAIL + (
            "\n## Scenario ID form\n\n"
            "New files use the TS-n form only; `scenario-id-form`.\n"
        )
        with self.assertRaises(AssertionError):
            _check_ac5_section(forged)

    def test_matcher_rejects_section_without_rework_planner_scope(self):
        forged = PRE_CHANGE_CONTRACT_TAIL.replace(
            "## Gate option vocabulary",
            "## Scenario ID form\n\n"
            "New VERIFICATION.md files and task plans use the TS-n scenario ID\n"
            "form only. `scripts/validate-worker-output.py` rejects a\n"
            "`completed` result validated with `--feature-dir` that holds a\n"
            "hyphen-less scenario ID outside fenced code blocks and HTML\n"
            "comments (`scenario-id-form`). The rule text is owned by\n"
            "`skills/plan-writing/SKILL.md`; this contract does not restate it.\n\n"
            "## Gate option vocabulary",
        )
        with self.assertRaises(AssertionError):
            _check_ac5_section(forged)

    def test_matcher_accepts_a_complete_forged_section(self):
        forged = PRE_CHANGE_CONTRACT_TAIL.replace(
            "## Gate option vocabulary",
            "## Scenario ID form\n\n"
            "New VERIFICATION.md files and task plans use the TS-n scenario ID\n"
            "form only. `scripts/validate-worker-output.py` rejects a\n"
            "`completed` result validated with `--feature-dir` that holds a\n"
            "hyphen-less scenario ID outside fenced code blocks and HTML\n"
            "comments (`scenario-id-form`). `rework-planner` output is outside\n"
            "this check. The rule text is owned by\n"
            "`skills/plan-writing/SKILL.md`; this contract does not restate it.\n\n"
            "## Gate option vocabulary",
        )
        self.assertEqual(_check_ac5_section(forged), "## Scenario ID form")

    def test_digest_pin_detects_a_mutated_vocabulary_section(self):
        section = self.text[self.text.index(GATE_VOCAB_MARKER) :]
        self.assertNotEqual(_sha256(section + "\n"), CONTRACT_GATE_VOCAB_SHA256)


# ---------------------------------------------------------------------------
# AC-6: no hyphen-less scenario ID in any of the three documents.
# ---------------------------------------------------------------------------


class TestAC6NoHyphenlessIdInTheDocuments(unittest.TestCase):
    def test_phase_document_has_none(self):
        self.assertEqual(hyphenless_ids(_read(PHASE_PATH)), set())

    def test_planner_agent_has_none(self):
        self.assertEqual(hyphenless_ids(_read(PLANNER_PATH)), set())

    def test_planner_contract_has_none(self):
        self.assertEqual(hyphenless_ids(_read(CONTRACT_PATH)), set())

    # -- negative proofs: the base revision holds no violation, so the
    # detection rule is shown firing on forged samples instead. -----------

    @staticmethod
    def _id(digits):
        # Built from parts so this module's own source holds no hyphen-less ID.
        return "TS" + digits

    def test_rule_fires_on_a_plain_hyphenless_id(self):
        forged = "see %s here" % self._id("13")
        self.assertEqual(hyphenless_ids(forged), {self._id("13")})

    def test_rule_fires_at_the_very_start_of_the_text(self):
        forged = "%s is listed first" % self._id("1")
        self.assertEqual(hyphenless_ids(forged), {self._id("1")})

    def test_rule_fires_inside_an_inline_code_span(self):
        forged = "the id `%s` is wrapped" % self._id("7")
        self.assertEqual(hyphenless_ids(forged), {self._id("7")})

    def test_rule_fires_after_a_non_ascii_character(self):
        forged = "対象は%sです" % self._id("5")
        self.assertEqual(hyphenless_ids(forged), {self._id("5")})

    def test_rule_does_not_fire_on_the_hyphenated_form(self):
        self.assertEqual(hyphenless_ids("see TS-13 and TS-2"), set())

    def test_rule_does_not_fire_after_an_ascii_letter_or_digit(self):
        forged = "X%s and 9%s" % (self._id("4"), self._id("6"))
        self.assertEqual(hyphenless_ids(forged), set())

    def test_rule_skips_fenced_code_blocks_and_html_comments(self):
        forged = "```\n%s\n```\n<!-- %s -->\nclean line\n" % (
            self._id("3"),
            self._id("8"),
        )
        self.assertEqual(hyphenless_ids(forged), set())

    def test_rule_reports_each_id_once(self):
        forged = "%s then %s then %s" % (self._id("2"), self._id("2"), self._id("10"))
        self.assertEqual(hyphenless_ids(forged), {self._id("2"), self._id("10")})

    def test_rule_flags_the_pre_change_phase_excerpt_with_an_injected_id(self):
        forged = PRE_CHANGE_PHASE_FEATURE_DIR_PARAGRAPH + "\nSee " + self._id("11") + ".\n"
        self.assertEqual(hyphenless_ids(PRE_CHANGE_PHASE_FEATURE_DIR_PARAGRAPH), set())
        self.assertEqual(hyphenless_ids(forged), {self._id("11")})


# ---------------------------------------------------------------------------
# AC-7: module hygiene.
# ---------------------------------------------------------------------------


class TestAC7ModuleHygiene(unittest.TestCase):
    def test_module_imports_the_standard_library_only(self):
        tree = ast.parse(_read(Path(__file__).resolve()))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                self.assertEqual(node.level, 0, "relative import")
                imported.add((node.module or "").split(".")[0])
        stdlib = set(sys.stdlib_module_names)
        self.assertTrue(imported)
        self.assertEqual(imported - stdlib, set())

    def test_all_three_documents_exist_and_are_non_empty(self):
        for path in (PHASE_PATH, PLANNER_PATH, CONTRACT_PATH):
            with self.subTest(path=path.name):
                self.assertTrue(_read(path).strip())


if __name__ == "__main__":
    unittest.main()
