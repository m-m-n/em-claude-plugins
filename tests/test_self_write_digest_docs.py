"""Document assertions for worker-self-write-digest/task0002: Rule R1's
self-write rule, the three contracts' citations of it, workflow-patch.md
application rule 1, and phase-state.md's two persisted run fields.

Covers task0002 Acceptance Criteria
(feature-docs/worker-self-write-digest/tasks/task0002.md):

- AC-1 (FR1, FR2, FR3, FR4, FR8, FR9; TS-9; TM-1, TM-2, TM-3): worker-envelope.md
  Rule R1, "Recomputation and comparison timing", states once the overlap
  condition, the membership rule (observed change set, covering action's
  permission, `written_artifacts` never decides), every row of the membership
  matrix, the substitution, the stale remainder, the return-time order, the
  orchestrator-side use of the script, and the persistence / resume pointer.
- AC-2 (FR9, NFR6; TS-9, TS-15): the designer, planner and rework-planner
  contracts each cite R1 in one paragraph of their `digest_inputs` section,
  name exactly their overlapping paths, and restate neither the matrix nor the
  substitution.
- AC-3 (FR5; TS-9): workflow-patch.md application rule 1 keeps its rejection
  meaning and cites R1's self-write rule; all eighteen rules still apply in
  order.
- AC-4 (FR6, FR7; TS-8, TS-12; TM-4): phase-state.md shows both fields in the
  schema block and the `worker_runs` row with their write timing, widens the
  idempotency exception to `status` plus the one-time `self_write_set`
  addition, and applies R1's substitution at the Resume decision table's read
  input 4 while read input 5 keeps comparing artifact bodies with their
  recorded digests.
- AC-5 (NFR2; TS-10): `worker_digest_stance` passes on the real repository;
  the stance sentence stays; `worker-envelope.md` carries no `expect_digest`
  token; every added sentence that mentions a digest names the orchestrator or
  is negated.
- AC-6 (NFR1, NFR4; TS-10, TS-13): R1's normalization paragraph and the seven
  structural keys of the `digest_source` example are unchanged, and the
  headings pinned by IMPLEMENTATION.md still exist.

All assertions run on whitespace-normalized, section-sliced text; none depends
on line-break positions and none compares a whole document. Each absence probe
has a forged-text control showing that the probe fires. The script
`em-workflow/scripts/self-write-digest.py` is built in another worktree: these
tests read documents only and never assert that the script file exists.

Standard library only.
"""

import importlib.util
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"
REFERENCES = PLUGIN_ROOT / "references"
CONTRACTS = REFERENCES / "contracts"

ENVELOPE_PATH = CONTRACTS / "worker-envelope.md"
DESIGNER_PATH = CONTRACTS / "designer-contract.md"
PLANNER_PATH = CONTRACTS / "planner-contract.md"
REWORK_PATH = CONTRACTS / "rework-planner-contract.md"
WORKFLOW_PATCH_PATH = REFERENCES / "workflow-patch.md"
PHASE_STATE_PATH = REFERENCES / "phase-state.md"
CHECKER_PATH = PLUGIN_ROOT / "scripts" / "check-plugin-invariants.py"

ENVELOPE_CITATION = "references/contracts/worker-envelope.md"
R1_NAME = "Rule R1"
TIMING_NAME = "Recomputation and comparison timing"

R1_LABELS = (
    "Condition",
    "Self-write set",
    "Substitution",
    "Order",
    "Means",
    "Persistence and resume",
    "Known limit",
)

# IMPLEMENTATION.md "Self-write membership matrix": covering entry -> the
# cell for each change kind (created, modified, deleted).
NOT_MEMBER = "not a member"
MATRIX = {
    "target `create`": ("member", NOT_MEMBER, NOT_MEMBER),
    "target `replace_own`": (NOT_MEMBER, "member", NOT_MEMBER),
    "target `replace_authorized`": (NOT_MEMBER, "member", NOT_MEMBER),
    "target `extend_only`": (NOT_MEMBER, "member", NOT_MEMBER),
    "target `regenerate`": (
        NOT_MEMBER,
        "member only when its `source` is a member",
        NOT_MEMBER,
    ),
    "target `preserve`": (NOT_MEMBER, NOT_MEMBER, NOT_MEMBER),
    "not a target, inside an `allowed_write_roots` entry": (
        "member",
        NOT_MEMBER,
        NOT_MEMBER,
    ),
    "neither": (NOT_MEMBER, NOT_MEMBER, NOT_MEMBER),
}

# Overlapping paths each contract names (task plan "Contract citations").
OVERLAP_PATHS = {
    "designer": {"design-system/tokens.yaml", "design-system/tokens.html"},
    "planner": {"IMPLEMENTATION.md", "VERIFICATION.md", "THREAT-MODEL.md", "tasks/"},
    "rework-planner": {"IMPLEMENTATION.md", "VERIFICATION.md", "tasks/"},
}
CONTRACT_FILES = {
    "designer": DESIGNER_PATH,
    "planner": PLANNER_PATH,
    "rework-planner": REWORK_PATH,
}

# IMPLEMENTATION.md "Pinned headings": (document, heading line).
PINNED_HEADINGS = (
    (PHASE_STATE_PATH, "## ID uniqueness and idempotency"),
    (PHASE_STATE_PATH, "### worker_runs[].status transitions"),
    (PHASE_STATE_PATH, "## Resume decision table"),
    (REFERENCES / "phases" / "create-plan-phase.md", "## 3. Reconcile on entry"),
    (REFERENCES / "phases" / "create-plan-phase.md", "## 4. Planner dispatch"),
    (REFERENCES / "phases" / "create-plan-phase.md", "## 8. Validation"),
    (PLUGIN_ROOT / "skills" / "develop" / "SKILL.md", "### design ステップ分岐"),
    (REFERENCES / "rework-task-synthesis.md", "## 10. Workflow state transition"),
)

NORMALIZATION_PARAGRAPH = (
    "**Normalization procedure**: sort every object's keys in ascending order, "
    'serialize to JSON using separators `(",", ":")`, leave non-ASCII characters '
    "unescaped, then take the sha256 of the resulting bytes."
)
DIGEST_SOURCE_KEYS = (
    "worker",
    "mode",
    "workflow_blob",
    "digest_inputs",
    "value_inputs",
    "answers_digest",
    "write_policy_digest",
)
TIMING_EXISTING_SENTENCES = (
    "the orchestrator computes `input_digest` once, before dispatch, and places it "
    "in the input envelope's `input_revision.input_digest`",
    "The worker copies that value verbatim into its output's "
    "`input_revision.input_digest` (an echo, never a recomputation)",
    "a mismatch means a tracked input changed during the dispatch window and the "
    "result is treated as stale",
    "both follow the identical normalization procedure above",
)


def _load_checker():
    spec = importlib.util.spec_from_file_location(
        "_check_plugin_invariants_for_self_write_docs", CHECKER_PATH
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


cpi = _load_checker()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _read(path):
    return path.read_text(encoding="utf-8")


def _normalize_ws(text):
    return re.sub(r"\s+", " ", text).strip()


def _heading_of(line):
    match = re.match(r"^(#{1,6})[ \t]+(.*?)[ \t]*$", line)
    if not match:
        return None
    return len(match.group(1)), match.group(2)


def _section_lines(text, level, title_matches):
    """Lines (raw text) of the first level-`level` heading whose title
    satisfies `title_matches`, up to the next heading of the same or a higher
    level. Headings inside fenced code are ignored. AssertionError when absent."""
    collected = []
    in_section = False
    in_fence = False
    for line in text.splitlines():
        if line.lstrip().startswith("```"):
            in_fence = not in_fence
        heading = None if in_fence else _heading_of(line)
        if in_section and heading and heading[0] <= level:
            break
        if not in_section and heading and heading[0] == level and title_matches(heading[1]):
            in_section = True
        if in_section:
            collected.append(line)
    if not in_section:
        raise AssertionError("section heading not found")
    return collected


def _section(text, level, title_matches):
    return "\n".join(_section_lines(text, level, title_matches)) + "\n"


def _r1_section(text):
    return _section(text, 2, lambda title: title.startswith("Rule R1"))


def _r1_blocks(envelope_text):
    """{label: raw block text} for the labelled blocks of R1's self-write
    rule. A block runs from its `**Label.**` line to the next label, or to the
    `(Provenance:` paragraph, or to the end of the R1 section. AssertionError
    unless every label appears exactly once."""
    r1 = _r1_section(envelope_text)
    label_re = re.compile(r"^\*\*(%s)\.\*\*" % "|".join(re.escape(l) for l in R1_LABELS), re.M)
    matches = list(label_re.finditer(r1))
    found = [m.group(1) for m in matches]
    for label in R1_LABELS:
        if found.count(label) != 1:
            raise AssertionError(
                f"R1 must hold the block label **{label}.** exactly once (found {found.count(label)})"
            )
    stop = re.search(r"^\(Provenance:", r1, re.M)
    end_of_region = stop.start() if stop else len(r1)
    blocks = {}
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else end_of_region
        blocks[match.group(1)] = r1[match.start():end]
    return blocks


def _r1_region(envelope_text):
    """The self-write rule's whole region: first label to the Provenance
    paragraph."""
    blocks = _r1_blocks(envelope_text)
    return "\n".join(blocks[label] for label in R1_LABELS)


def _table_rows(block_text):
    """List of cell lists for the markdown table lines of `block_text`
    (separator rows dropped)."""
    rows = []
    for line in block_text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|"):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if all(re.fullmatch(r":?-+:?", cell) for cell in cells):
            continue
        rows.append(cells)
    return rows


def _paragraphs(text):
    blocks = re.split(r"\n[ \t]*\n", text.replace("\r\n", "\n"))
    return [_normalize_ws(block) for block in blocks if block.strip()]


def _digest_inputs_section(contract_text):
    return _section(
        contract_text, 2, lambda title: title.replace("`", "").strip() == "digest_inputs"
    )


def _citation_paragraphs(section_text):
    return [
        para
        for para in _paragraphs(section_text)
        if ENVELOPE_CITATION in para and R1_NAME in para and TIMING_NAME in para
    ]


def _path_like_spans(paragraph):
    spans = re.findall(r"`([^`]+)`", paragraph)
    return {span for span in spans if "/" in span or "." in span}


_ACTION_NAMES_RE = re.compile(
    r"\b(?:replace_own|replace_authorized|extend_only|regenerate|preserve)\b|`create`"
)
_CHANGE_KINDS_RE = re.compile(r"\b(?:created|modified|deleted)\b")
_SUBSTITUTION_RE = re.compile(
    r"\babsent\b|dispatch-time value|\bsubstitut\w*|\bmember\b|self-write set",
    re.IGNORECASE,
)


def _restates_matrix_or_substitution(text):
    """True when `text` words out the action-by-kind matrix or the
    substitution (owned by Rule R1) instead of citing them."""
    flat = _normalize_ws(text)
    return bool(
        _ACTION_NAMES_RE.search(flat)
        or _CHANGE_KINDS_RE.search(flat)
        or _SUBSTITUTION_RE.search(flat)
    )


def _digest_sentence_violations(text):
    """Sentences of `text` that mention a digest, neither name the
    orchestrator nor are negated -- the convention for every added digest
    sentence."""
    return [
        sentence
        for sentence in cpi._sentences(text)
        if cpi.DIGEST_TERM_RE.search(sentence)
        and not cpi.ORCHESTRATOR_RE.search(sentence)
        and not cpi.NEGATION_RE.search(sentence)
    ]


def _numbered_item(section_text, number):
    """Text of list item `number.` up to the next list item of the following
    number (or the next blank line followed by a non-indented line)."""
    lines = section_text.splitlines()
    start = next(
        (i for i, line in enumerate(lines) if line.startswith(f"{number}. ")), None
    )
    if start is None:
        raise AssertionError(f"list item {number}. not found")
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if re.match(r"^\d+\. ", lines[i]) or not lines[i].strip():
            end = i
            break
    return _normalize_ws(" ".join(lines[start:end]))


def _bullet(section_text, start_prefix):
    """Text of the top-level bullet that starts with `start_prefix`, up to the
    next top-level bullet."""
    lines = section_text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith(start_prefix)), None)
    if start is None:
        raise AssertionError(f"bullet {start_prefix!r} not found")
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if lines[i].startswith("- ") or lines[i].startswith("#"):
            end = i
            break
    return _normalize_ws(" ".join(lines[start:end]))


# ---------------------------------------------------------------------------
# AC-1: Rule R1 states the self-write rule once
# ---------------------------------------------------------------------------


class TestRuleR1SelfWriteRule(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(ENVELOPE_PATH)
        cls.blocks = _r1_blocks(cls.text)
        cls.flat = {label: _normalize_ws(block) for label, block in cls.blocks.items()}

    def test_ac1_every_block_label_appears_exactly_once_in_the_document(self):
        for label in R1_LABELS:
            with self.subTest(label=label):
                self.assertEqual(self.text.count(f"**{label}.**"), 1)

    def test_ac1_blocks_sit_inside_the_r1_section_after_the_timing_paragraph(self):
        r1 = _r1_section(self.text)
        timing_at = r1.index("**Recomputation and comparison timing**")
        for label in R1_LABELS:
            with self.subTest(label=label):
                self.assertGreater(r1.index(f"**{label}.**"), timing_at)

    def test_ac1_condition_names_the_overlap_and_the_no_op_for_other_workers(self):
        block = self.flat["Condition"]
        self.assertRegex(block, r"`digest_inputs` overlap the paths its `write_policy`")
        self.assertIn("`allowed_write_roots`", block)
        self.assertRegex(block, r"(?i)for any other worker .{0,80}changes nothing")

    def test_ac1_condition_has_the_orchestrator_as_the_actor(self):
        self.assertRegex(self.flat["Condition"], r"^\*\*Condition\.\*\* The orchestrator")

    def test_ac1_membership_needs_the_observed_change_set_and_the_covering_action(self):
        block = self.flat["Self-write set"]
        self.assertIn("change set the orchestrator observed", block)
        self.assertIn('`references/phases/create-spec-phase.md`, "Scope verification"', block)
        self.assertRegex(block, r"action of the `write_policy` entry covering it permits")

    def test_ac1_written_artifacts_never_decides_membership_tm1(self):
        block = self.flat["Self-write set"]
        self.assertIn("`written_artifacts` never decides membership", block)
        self.assertIn("plain intersection", block)

    def test_ac1_actions_meaning_is_cited_not_restated(self):
        block = self.flat["Self-write set"]
        self.assertIn(
            '`references/contracts/spec-writer-contract.md` ("The six `write_policy` actions")',
            block,
        )

    def test_ac1_change_kinds_follow_the_scope_verification(self):
        block = self.flat["Self-write set"]
        for kind in ("created", "modified", "deleted"):
            with self.subTest(kind=kind):
                self.assertIn(f"`{kind}`", block)

    def test_ac1_membership_matrix_header_and_row_set(self):
        rows = _table_rows(self.blocks["Self-write set"])
        self.assertEqual(rows[0], ["Covering entry", "`created`", "`modified`", "`deleted`"])
        self.assertEqual([row[0] for row in rows[1:]], list(MATRIX))

    def test_ac1_membership_matrix_every_row_tm2(self):
        rows = {row[0]: tuple(row[1:]) for row in _table_rows(self.blocks["Self-write set"])[1:]}
        for entry, expected in MATRIX.items():
            with self.subTest(entry=entry):
                self.assertEqual(rows.get(entry), expected)

    def test_ac1_deletion_is_never_admitted_tm2(self):
        rows = _table_rows(self.blocks["Self-write set"])[1:]
        self.assertTrue(rows)
        self.assertEqual({row[3] for row in rows}, {NOT_MEMBER})

    def test_ac1_allowed_write_roots_admit_creation_only_tm2(self):
        rows = {row[0]: row[1:] for row in _table_rows(self.blocks["Self-write set"])[1:]}
        self.assertEqual(
            rows["not a target, inside an `allowed_write_roots` entry"],
            ["member", NOT_MEMBER, NOT_MEMBER],
        )

    def test_ac1_preserve_is_never_admitted_tm2(self):
        rows = {row[0]: row[1:] for row in _table_rows(self.blocks["Self-write set"])[1:]}
        self.assertEqual(rows["target `preserve`"], [NOT_MEMBER] * 3)

    def test_ac1_regenerate_is_admitted_only_with_its_source_tm2(self):
        rows = {row[0]: row[1:] for row in _table_rows(self.blocks["Self-write set"])[1:]}
        self.assertEqual(rows["target `regenerate`"][1], "member only when its `source` is a member")

    def test_ac1_matrix_is_written_out_exactly_once_in_the_document(self):
        self.assertEqual(self.text.count("| Covering entry |"), 1)
        for entry in MATRIX:
            with self.subTest(entry=entry):
                self.assertEqual(self.text.count(f"| {entry} |"), 1)

    def test_ac1_matrix_notes_target_precedence_segments_and_unsafe_paths(self):
        block = self.flat["Self-write set"]
        self.assertRegex(block, r"listed in `targets` is judged by its target even when .{0,60}allowed write root")
        self.assertRegex(block, r"compares path segments, never string prefixes")
        self.assertRegex(block, r"absolute path, or a path with a `\.\.` segment, is never a member")
        self.assertRegex(block, r"`regenerate` target is decided after every other path")

    def test_ac1_substitution_takes_the_dispatch_time_value_or_an_absent_key(self):
        block = self.flat["Substitution"]
        self.assertRegex(block, r"each path of the self-write set .{0,80}dispatch-time value")
        self.assertRegex(block, r"no key for the path, the key stays absent")

    def test_ac1_substitution_keeps_everything_else_current(self):
        block = self.flat["Substitution"]
        for name in ("value_inputs", "answers_digest", "write_policy_digest", "workflow_blob"):
            with self.subTest(name=name):
                self.assertIn(f"`{name}`", block)
        self.assertRegex(block, r"taken from the current state")

    def test_ac1_other_changes_stay_stale_and_the_aggregate_comparison_is_kept(self):
        block = self.flat["Substitution"]
        self.assertIn("aggregate comparison is kept", block)
        self.assertRegex(block, r"outside the self-write set.{0,200}still makes the result stale")

    def test_ac1_substitution_names_the_orchestrator_as_the_actor(self):
        self.assertRegex(self.flat["Substitution"], r"^\*\*Substitution\.\*\* The orchestrator")

    def test_ac1_recomputation_follows_the_scope_verification_fr8(self):
        block = self.flat["Order"]
        self.assertRegex(block, r"only after the scope verification has produced the observed change set")

    def test_ac1_order_lists_the_four_steps_in_sequence(self):
        block = self.flat["Order"]
        anchors = [
            "scope verification yields the observed change set",
            "recomputes the current `digest_source`",
            "runs the self-write script",
            "compares the substituted `digest_source`",
        ]
        positions = [block.find(anchor) for anchor in anchors]
        self.assertNotIn(-1, positions, positions)
        self.assertEqual(positions, sorted(positions))
        self.assertRegex(block, r"mismatch, or a script exit other than `0`, makes the result stale")

    def test_ac1_orchestrator_runs_the_script_with_one_json_document_tm3(self):
        block = self.flat["Means"]
        self.assertIn("`scripts/self-write-digest.py`", block)
        self.assertRegex(block, r"exactly one argument, the path of its input document")
        self.assertIn("one JSON input document", block)
        self.assertIn("file-writing tool", block)
        self.assertIn("outside the integration worktree", block)

    def test_ac1_document_is_never_assembled_through_shell_interpolation_tm3(self):
        block = self.flat["Means"]
        self.assertRegex(block, r"never assembles it through shell interpolation")
        self.assertRegex(block, r"no path taken from the document appears on the command line")

    def test_ac1_a_non_zero_exit_makes_the_result_stale_tm3(self):
        self.assertRegex(
            self.flat["Means"], r"exit code other than `0` makes the result stale"
        )

    def test_ac1_script_computes_no_digest_and_hashing_stays_with_the_orchestrator(self):
        block = self.flat["Means"]
        self.assertRegex(block, r"script computes no digest")
        self.assertRegex(block, r"hashing stays with the orchestrator")

    def test_ac1_persistence_and_resume_point_at_phase_state(self):
        block = self.flat["Persistence and resume"]
        self.assertIn("`references/phase-state.md`", block)
        self.assertIn("dispatch-time `digest_inputs` map", block)
        self.assertRegex(block, r"resumed run takes both from there instead of identifying")

    def test_ac1_known_limit_rests_on_the_exclusivity_assumption(self):
        block = self.flat["Known limit"]
        self.assertRegex(block, r"worker and another actor change the same permitted path")
        self.assertRegex(block, r"cannot be told apart")
        self.assertIn("exclusivity assumption", block)
        exclusivity_heading = self.text.index("## Exclusivity assumption during dispatch")
        self.assertGreater(exclusivity_heading, self.text.index("**Known limit.**"))


# ---------------------------------------------------------------------------
# AC-2: the three contracts cite R1 and name their overlapping paths
# ---------------------------------------------------------------------------


class TestContractCitations(unittest.TestCase):
    def test_ac2_each_contract_has_one_citing_paragraph_in_its_digest_inputs_section(self):
        for worker, path in CONTRACT_FILES.items():
            with self.subTest(contract=worker):
                section = _digest_inputs_section(_read(path))
                self.assertEqual(len(_citation_paragraphs(section)), 1)

    def test_ac2_citation_paragraph_names_exactly_the_overlapping_paths(self):
        for worker, path in CONTRACT_FILES.items():
            with self.subTest(contract=worker):
                paragraph = _citation_paragraphs(_digest_inputs_section(_read(path)))[0]
                named = _path_like_spans(paragraph) - {ENVELOPE_CITATION}
                self.assertEqual(named, OVERLAP_PATHS[worker])

    def test_ac2_citation_paragraph_has_the_orchestrator_as_the_actor(self):
        for worker, path in CONTRACT_FILES.items():
            with self.subTest(contract=worker):
                paragraph = _citation_paragraphs(_digest_inputs_section(_read(path)))[0]
                self.assertRegex(paragraph, r"^The orchestrator")

    def test_ac2_citation_paragraph_restates_neither_matrix_nor_substitution(self):
        for worker, path in CONTRACT_FILES.items():
            with self.subTest(contract=worker):
                paragraph = _citation_paragraphs(_digest_inputs_section(_read(path)))[0]
                self.assertFalse(
                    _restates_matrix_or_substitution(paragraph),
                    f"{worker} paragraph words out the matrix or the substitution: {paragraph!r}",
                )

    def test_ac2_no_contract_carries_the_membership_matrix(self):
        for worker, path in CONTRACT_FILES.items():
            with self.subTest(contract=worker):
                flat = _normalize_ws(_read(path))
                self.assertNotIn("Covering entry", flat)
                self.assertNotIn("member only when", flat)
                self.assertNotIn(NOT_MEMBER, flat)

    def test_ac2_designer_project_native_exclusion_is_kept(self):
        section = _normalize_ws(_digest_inputs_section(_read(DESIGNER_PATH)))
        self.assertIn("**`project_native` exclusion**", section)


# ---------------------------------------------------------------------------
# AC-3: workflow-patch.md application rule 1
# ---------------------------------------------------------------------------


def _rule_text(application_rules_text, number):
    lines = application_rules_text.splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith(f"{number}. ")), None)
    if start is None:
        raise AssertionError(f"application rule {number} not found")
    end = len(lines)
    for i in range(start + 1, len(lines)):
        if re.match(r"^\d+\. ", lines[i]):
            end = i
            break
    return _normalize_ws(" ".join(lines[start:end]))


class TestWorkflowPatchRule1(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.section = _section(
            _read(WORKFLOW_PATCH_PATH), 2, lambda title: title.startswith("Application rules")
        )
        cls.rule1 = _rule_text(cls.section, 1)

    def test_ac3_rule_1_still_rejects_on_a_base_input_digest_mismatch(self):
        self.assertIn(
            "Reject unless `base_input_digest` matches the digest recomputed from the current input",
            self.rule1,
        )

    def test_ac3_rule_1_states_the_recomputed_source_is_built_under_the_self_write_rule(self):
        self.assertRegex(
            self.rule1, r"recomputed `digest_source` under the self-write rule of"
        )

    def test_ac3_rule_1_cites_r1_by_path_and_name(self):
        self.assertIn(ENVELOPE_CITATION, self.rule1)
        self.assertIn(R1_NAME, self.rule1)

    def test_ac3_rule_1_has_the_orchestrator_as_the_actor_of_the_added_sentence(self):
        added = [s for s in re.split(r"(?<=[.!?])\s+", self.rule1) if "self-write" in s]
        self.assertEqual(len(added), 1, added)
        self.assertIn("orchestrator", added[0])

    def test_ac3_rule_1_cites_rather_than_restates(self):
        self.assertFalse(_restates_matrix_or_substitution(self.rule1.replace("self-write rule", "")))

    def test_ac3_all_eighteen_rules_still_apply_in_order(self):
        self.assertIn("All eighteen rules apply, in order, to every patch:", _normalize_ws(self.section))
        for number in range(1, 19):
            with self.subTest(rule=number):
                self.assertTrue(
                    any(line.startswith(f"{number}. ") for line in self.section.splitlines())
                )
        self.assertFalse(any(line.startswith("19. ") for line in self.section.splitlines()))


# ---------------------------------------------------------------------------
# AC-4: phase-state.md fields, timing, idempotency exception, resume
# ---------------------------------------------------------------------------


class TestPhaseStateRunFields(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(PHASE_STATE_PATH)
        cls.schema = _section(cls.text, 2, lambda title: title == "Schema")
        cls.idempotency = _section(
            cls.text, 2, lambda title: title == "ID uniqueness and idempotency"
        )
        cls.resume = _section(cls.text, 2, lambda title: title == "Resume decision table")

    def _schema_block(self):
        match = re.search(r"```yaml\n(.*?)\n```", self.schema, re.S)
        self.assertIsNotNone(match, "schema block not found")
        return match.group(1)

    def _worker_runs_example(self):
        block = self._schema_block()
        start = block.index("worker_runs:")
        end = block.index("\nartifacts:", start)
        return block[start:end]

    def _worker_runs_row(self):
        rows = [line for line in self.schema.splitlines() if line.startswith("| `worker_runs` |")]
        self.assertEqual(len(rows), 1)
        return _normalize_ws(rows[0])

    def test_ac4_schema_block_example_entry_shows_both_fields(self):
        entry = self._worker_runs_example()
        self.assertIn("dispatch_digest_inputs:", entry)
        self.assertIn("self_write_set:", entry)

    def test_ac4_field_table_row_names_both_fields(self):
        row = self._worker_runs_row()
        self.assertIn("`dispatch_digest_inputs`", row)
        self.assertIn("`self_write_set`", row)

    def test_ac4_dispatch_map_is_written_with_the_entry_at_dispatch(self):
        row = self._worker_runs_row()
        self.assertRegex(
            row, r"`dispatch_digest_inputs`.{0,200}written with the entry .{0,80}at dispatch"
        )
        self.assertRegex(row, r"`dispatch_digest_inputs`.{0,400}never changed afterwards")

    def test_ac4_self_write_set_is_written_once_with_the_layer_5_artifacts_entries_tm4(self):
        row = self._worker_runs_row()
        self.assertRegex(
            row,
            r"`self_write_set`.{0,300}written once in the same phase-state write as the "
            r"run's layer-5 `artifacts` entries",
        )
        self.assertRegex(row, r"run with no written artifacts, the write that records its returned `status`")

    def test_ac4_entries_without_the_fields_stay_valid(self):
        self.assertRegex(self._worker_runs_row(), r"carries neither .{0,40}stays valid")

    def test_ac4_idempotency_exception_allows_status_plus_the_one_time_addition(self):
        bullet = _bullet(self.idempotency, "- `worker_runs` follows the same rule")
        self.assertIn("`status`", bullet)
        self.assertIn("`self_write_set`", bullet)
        self.assertIn("one-time addition", bullet)
        self.assertIn("protocol error", bullet)

    def test_ac4_idempotency_exception_no_longer_says_status_alone(self):
        bullet = _bullet(self.idempotency, "- `worker_runs` follows the same rule")
        self.assertNotIn("`status` field alone", bullet)
        self.assertNotIn("`dispatch_digest_inputs`", bullet)

    def test_ac4_resume_read_input_4_applies_r1_substitution_with_the_selected_entry(self):
        item = _numbered_item(self.resume, 4)
        self.assertIn("`input_digest`", item)
        self.assertIn("`last_input_digest`", item)
        self.assertIn(ENVELOPE_CITATION, item)
        self.assertIn(R1_NAME, item)
        self.assertIn("substitution", item)
        self.assertRegex(
            item,
            r"last `worker_runs` entry whose `input_digest` equals `last_input_digest`",
        )
        self.assertIn("`dispatch_digest_inputs`", item)
        self.assertIn("`self_write_set`", item)

    def test_ac4_resume_substitutes_nothing_when_a_field_is_missing(self):
        item = _numbered_item(self.resume, 4)
        self.assertRegex(
            item, r"lacks either .{0,80}no substitution|no substitution .{0,120}lacks either"
        )

    def test_ac4_resume_read_input_5_still_compares_artifact_bodies_tm4(self):
        item = _numbered_item(self.resume, 5)
        self.assertEqual(item, "5. artifact bodies vs. their recorded digest")

    def test_ac4_resume_states_a_post_record_edit_is_still_detected_tm4(self):
        item = _numbered_item(self.resume, 4)
        self.assertRegex(
            item,
            r"orchestrator still detects an edit .{0,40}self-written artifact .{0,40}"
            r"after its digest was recorded",
        )

    def test_ac4_sentences_that_mention_a_digest_name_the_orchestrator_or_are_negated(self):
        row = self._worker_runs_row()
        self.assertIn("two optional fields", row)
        added = [
            row.split("two optional fields", 1)[1],
            _bullet(self.idempotency, "- `worker_runs` follows the same rule"),
            _numbered_item(self.resume, 4),
        ]
        for text in added:
            with self.subTest(text=text[:60]):
                self.assertEqual(_digest_sentence_violations(text), [])


# ---------------------------------------------------------------------------
# AC-5: worker_digest_stance and the orchestrator-as-subject convention
# ---------------------------------------------------------------------------


class TestDigestStanceInvariants(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.envelope = _read(ENVELOPE_PATH)

    def test_ac5_worker_digest_stance_passes_on_the_real_repository(self):
        result = cpi.check_worker_digest_stance(str(REPO_ROOT))
        self.assertEqual(result.name, "worker_digest_stance")
        self.assertTrue(result.passed, result.offenders)

    def test_ac5_written_artifacts_reporting_keeps_the_stance_sentence(self):
        section = _section(
            self.envelope, 2, lambda title: title == "`written_artifacts` reporting"
        )
        self.assertIn("The worker does not compute digests", _normalize_ws(section))

    def test_ac5_envelope_contains_no_expect_digest_token(self):
        self.assertIsNone(re.search(r"\bexpect_digest\b", self.envelope))

    def test_ac5_every_digest_sentence_of_the_self_write_rule_names_the_orchestrator_or_is_negated(self):
        self.assertEqual(_digest_sentence_violations(_r1_region(self.envelope)), [])

    def test_ac5_self_write_rule_carries_no_worker_directed_digest_instruction(self):
        self.assertEqual(
            cpi.find_worker_directed_digest_instructions(_r1_region(self.envelope), ()), []
        )

    def test_ac5_contract_paragraphs_carry_no_worker_directed_digest_instruction(self):
        for worker, path in CONTRACT_FILES.items():
            with self.subTest(contract=worker):
                paragraph = _citation_paragraphs(_digest_inputs_section(_read(path)))[0]
                self.assertEqual(
                    cpi.find_worker_directed_digest_instructions(paragraph, (worker,)), []
                )
                self.assertEqual(_digest_sentence_violations(paragraph), [])


# ---------------------------------------------------------------------------
# AC-6: unchanged structure and pinned headings
# ---------------------------------------------------------------------------


class TestUnchangedStructure(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r1 = _normalize_ws(_r1_section(_read(ENVELOPE_PATH)))
        cls.r1_raw = _r1_section(_read(ENVELOPE_PATH))

    def test_ac6_normalization_paragraph_is_unchanged(self):
        self.assertIn(_normalize_ws(NORMALIZATION_PARAGRAPH), self.r1)

    def test_ac6_digest_source_example_keeps_its_seven_structural_keys(self):
        block = re.search(r"```yaml\ndigest_source:\n(.*?)\n```", self.r1_raw, re.S)
        self.assertIsNotNone(block)
        keys = re.findall(r"^  ([A-Za-z_]+):", block.group(1), re.M)
        self.assertEqual(keys, list(DIGEST_SOURCE_KEYS))

    def test_ac6_timing_paragraph_keeps_its_existing_sentences(self):
        for sentence in TIMING_EXISTING_SENTENCES:
            with self.subTest(sentence=sentence[:50]):
                self.assertIn(sentence, self.r1)

    def test_ac6_pinned_headings_still_exist(self):
        for path, heading in PINNED_HEADINGS:
            with self.subTest(document=path.name, heading=heading):
                lines = _read(path).splitlines()
                self.assertIn(heading, lines)

    def test_ac6_opening_sentence_about_write_policy_structure_is_kept(self):
        text = _normalize_ws(_read(ENVELOPE_PATH))
        self.assertIn(
            "This document does not restate `write_policy`'s internal structure (its six actions, "
            "its per-target digest-expectation requirement, or the split between existing-file "
            "protection and new-file `allowed_write_roots`) — that is owned by design-input.md "
            "5.4.2 and the per-worker contracts.",
            text,
        )

    def test_ac6_r1_names_the_actions_only_to_say_which_kinds_count(self):
        text = _normalize_ws(_read(ENVELOPE_PATH))
        self.assertRegex(
            text,
            r"Rule R1's self-write rule \(below\) names `write_policy`'s six actions only to "
            r"say which observed change kinds make a path a self-write",
        )


# ---------------------------------------------------------------------------
# Probe controls: each absence probe fires on forged text
# ---------------------------------------------------------------------------


class TestProbeControls(unittest.TestCase):
    def test_restatement_probe_fires_on_a_forged_action_by_kind_sentence(self):
        forged = (
            "The orchestrator treats a `create` target that was created as a self-write, "
            "never a deleted one."
        )
        self.assertTrue(_restates_matrix_or_substitution(forged))

    def test_restatement_probe_fires_on_a_forged_preserve_sentence(self):
        self.assertTrue(_restates_matrix_or_substitution("A `preserve` target is never written."))

    def test_restatement_probe_fires_on_a_forged_absent_key_sentence(self):
        self.assertTrue(
            _restates_matrix_or_substitution("A path missing at dispatch stays an absent key.")
        )

    def test_restatement_probe_fires_on_a_forged_substitution_sentence(self):
        self.assertTrue(
            _restates_matrix_or_substitution(
                "The orchestrator substitutes the dispatch-time value for the current one."
            )
        )

    def test_restatement_probe_stays_quiet_on_a_citation_only_paragraph(self):
        clean = (
            'The orchestrator applies `references/contracts/worker-envelope.md`, Rule R1, '
            '"Recomputation and comparison timing", on this worker\'s return. The `digest_inputs` '
            "paths this worker's `write_policy` lets it write are `tasks/`."
        )
        self.assertFalse(_restates_matrix_or_substitution(clean))

    def test_digest_sentence_probe_fires_on_a_forged_worker_directed_sentence(self):
        forged = "Compute the digest of every written path before returning."
        self.assertEqual(_digest_sentence_violations(forged), [forged])

    def test_digest_sentence_probe_accepts_orchestrator_and_negated_sentences(self):
        self.assertEqual(
            _digest_sentence_violations(
                "The orchestrator computes the digest of each path. The worker does not compute digests."
            ),
            [],
        )

    def test_matrix_row_parser_reads_a_forged_table(self):
        forged = (
            "| Covering entry | `created` | `modified` | `deleted` |\n"
            "|---|---|---|---|\n"
            "| target `create` | member | not a member | not a member |\n"
        )
        self.assertEqual(
            _table_rows(forged),
            [
                ["Covering entry", "`created`", "`modified`", "`deleted`"],
                ["target `create`", "member", NOT_MEMBER, NOT_MEMBER],
            ],
        )

    def test_matrix_row_check_fires_when_a_forged_row_admits_deletion(self):
        forged = (
            "| Covering entry | `created` | `modified` | `deleted` |\n"
            "|---|---|---|---|\n"
            "| target `create` | member | not a member | member |\n"
        )
        rows = {row[0]: tuple(row[1:]) for row in _table_rows(forged)[1:]}
        self.assertNotEqual(rows["target `create`"], MATRIX["target `create`"])

    def test_label_slicer_rejects_a_document_without_the_labels(self):
        forged = "# Doc\n\n## Rule R1: x\n\nbody\n\n## Next\n"
        with self.assertRaises(AssertionError):
            _r1_blocks(forged)

    def test_label_slicer_rejects_a_duplicated_label(self):
        labels = "\n\n".join(f"**{label}.** text" for label in R1_LABELS)
        forged = f"## Rule R1: x\n\n{labels}\n\n**Order.** again\n\n## Next\n"
        with self.assertRaises(AssertionError):
            _r1_blocks(forged)

    def test_citation_paragraph_finder_needs_all_three_tokens_in_one_paragraph(self):
        split = (
            f"`{ENVELOPE_CITATION}` only.\n\n{R1_NAME} here.\n\n\"{TIMING_NAME}\" there.\n"
        )
        self.assertEqual(_citation_paragraphs(split), [])
        joined = f'`{ENVELOPE_CITATION}`, {R1_NAME}, "{TIMING_NAME}".\n'
        self.assertEqual(len(_citation_paragraphs(joined)), 1)

    def test_path_span_reader_ignores_non_path_spans(self):
        paragraph = "`input_digest` and `write_policy` and `tasks/` and `IMPLEMENTATION.md`"
        self.assertEqual(_path_like_spans(paragraph), {"tasks/", "IMPLEMENTATION.md"})


if __name__ == "__main__":
    unittest.main()
