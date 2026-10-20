"""Document tests for worker-digest-ownership task0002.

`em-workflow/references/artifact-digest.md` is the single owner of the
artifact digest definition, the calculation means, the pre-dispatch
`expect_digest` verification, layer-5 recording, the legacy-record rule and
the list of dispatch sites. Every `write_policy` dispatch site cites it.

Covers task0002's Acceptance Criteria
(feature-docs/worker-digest-ownership/tasks/task0002.md):

- AC-1 (FR2, FR7, TM-1): the owner's `Digest definition` and `Calculation`.
- AC-2 (FR3, TM-2, TM-5): `Pre-dispatch verification` and
  `Layer 5 recording`.
- AC-3 (FR8, TM-3): `Legacy records`.
- AC-4 (FR2, FR3, TS3): create-spec-phase.md's snapshot row, section 9 and
  section 10.
- AC-5 (FR3, NFR2, TS11): create-plan-phase.md, rework-task-synthesis.md
  and the develop skill cite the owner; the `Dispatch sites` registry rows.
- AC-6 (FR4, TM-4, TS12): the develop skill's design step branch.

Method (the task plan's Test Notes): slice by heading, whitespace-normalize,
assert presence or absence of tokens and phrases. Never full-document
equality and never a line-break position. Every absence assertion is paired
with a forged-text case proving its matcher would fire. Standard library
only (NFR3).
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"

OWNER_PATH = PLUGIN_ROOT / "references" / "artifact-digest.md"
OWNER_CITATION = "references/artifact-digest.md"
CREATE_SPEC_PATH = PLUGIN_ROOT / "references" / "phases" / "create-spec-phase.md"
CREATE_PLAN_PATH = PLUGIN_ROOT / "references" / "phases" / "create-plan-phase.md"
REWORK_SYNTHESIS_PATH = PLUGIN_ROOT / "references" / "rework-task-synthesis.md"
DEVELOP_SKILL_PATH = PLUGIN_ROOT / "skills" / "develop" / "SKILL.md"

OWNER_SECTIONS = (
    "Digest definition",
    "Calculation",
    "Pre-dispatch verification",
    "Layer 5 recording",
    "Legacy records",
    "Dispatch sites",
)

# The four dispatch sites the SPEC names, as the six registry rows the task
# plan fixes (a create-spec site and a create-plan site each take two rows:
# one per owner section that site cites).
EXPECTED_REGISTRY = {
    ("references/phases/create-spec-phase.md", "9. Spec writer dispatch"):
        {"Pre-dispatch verification"},
    ("references/phases/create-spec-phase.md", "10. Artifact validation"):
        {"Layer 5 recording"},
    ("skills/develop/SKILL.md", "design ステップ分岐"):
        {"Pre-dispatch verification", "Layer 5 recording"},
    ("references/phases/create-plan-phase.md", "4. Planner dispatch"):
        {"Pre-dispatch verification"},
    ("references/phases/create-plan-phase.md", "8. Validation"):
        {"Layer 5 recording"},
    ("references/rework-task-synthesis.md", "10. Workflow state transition"):
        {"Pre-dispatch verification", "Layer 5 recording"},
}

GIT_HASH_OBJECT = "git hash-object"

_FENCE_RE = re.compile(r"^\s*(```|~~~)")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_BACKTICK_RE = re.compile(r"`([^`]+)`")


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


def _paragraph(text, marker):
    """The blank-line-delimited block whose whitespace-normalized text
    contains `marker`."""
    for block in re.split(r"\n\s*\n", text):
        if marker in _norm(block):
            return block
    raise AssertionError(f"no paragraph contains {marker!r}")


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


def _table_row(text, starts_with):
    for line in text.splitlines():
        if line.startswith(starts_with):
            return line
    raise AssertionError(f"no table row starts with {starts_with!r}")


def _names_git_hash_object(text):
    return GIT_HASH_OBJECT in text


def _cites_owner(text, section_name):
    """True when the (whitespace-normalized) text names the owner path and
    the owner section name."""
    flat = _norm(text)
    return OWNER_CITATION in flat and section_name in flat


# Wording that belongs to the owner's definition or procedure. A site
# section that carries any of it restates the owner instead of citing it
# (NFR2).
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


def _parse_registry(owner_text):
    """{(document, section): (worker, {covers})} read from the owner's
    `Dispatch sites` table. Independent of the invariant checker's parser."""
    body = _section(owner_text, "Dispatch sites", level=2)
    rows = {}
    for line in body.splitlines():
        if not line.lstrip().startswith("|"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 4:
            continue
        tokens = [_BACKTICK_RE.findall(c) for c in cells]
        if not all(tokens):
            continue  # header and separator rows carry no backticked token
        document, section, worker = (t[0] for t in tokens[:3])
        rows[(document, section)] = (worker, set(tokens[3]))
    return rows


# ---------------------------------------------------------------------------
# Matcher self-tests (each absence assertion has a forged-text case)
# ---------------------------------------------------------------------------


class TestMatchersFireOnForgedText(unittest.TestCase):
    def test_git_hash_object_matcher_fires(self):
        self.assertTrue(
            _names_git_hash_object("hash it with `git hash-object --` first")
        )
        self.assertFalse(_names_git_hash_object("hash it with the script"))

    def test_citation_matcher_requires_path_and_section_name(self):
        good = "see `references/artifact-digest.md`,\n`Pre-dispatch\nverification`"
        self.assertTrue(_cites_owner(good, "Pre-dispatch verification"))
        self.assertFalse(
            _cites_owner("see `Pre-dispatch verification`", "Pre-dispatch verification")
        )
        self.assertFalse(
            _cites_owner("see `references/artifact-digest.md`", "Layer 5 recording")
        )

    def test_restatement_matcher_fires(self):
        for forged in (
            "the sha256 of the file's raw bytes",
            "`sha256:` plus 64 lowercase hex digits",
            "run python3 \"${CLAUDE_PLUGIN_ROOT}/scripts/artifact-digest.py\"",
            "an `not_a_regular_file` element",
            "each path as one single-quoted word",
            "ファイルの生バイト列の sha256",
        ):
            self.assertTrue(_restatement_markers_in(forged), forged)
        self.assertFalse(
            _restatement_markers_in("cites the owner and verifies the targets")
        )

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

    def test_registry_parser_reads_backticked_cells(self):
        text = (
            "## Dispatch sites\n\n"
            "| Document | Section | Worker | Covers |\n|---|---|---|---|\n"
            "| `d.md` | `1. S` | `w` | `Pre-dispatch verification`, "
            "`Layer 5 recording` |\n"
        )
        self.assertEqual(
            _parse_registry(text),
            {("d.md", "1. S"): ("w", {"Pre-dispatch verification", "Layer 5 recording"})},
        )


# ---------------------------------------------------------------------------
# AC-1: Digest definition and Calculation
# ---------------------------------------------------------------------------


class TestOwnerDocumentStructure(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(OWNER_PATH)

    def test_owner_document_has_exactly_the_six_level_2_sections(self):
        level2 = [t for _i, lvl, t in _headings(self.text) if lvl == 2]
        self.assertEqual(level2, list(OWNER_SECTIONS))


class TestDigestDefinition(unittest.TestCase):
    """AC-1 (first half)."""

    @classmethod
    def setUpClass(cls):
        cls.section = _norm(_section(_read(OWNER_PATH), "Digest definition", level=2))

    def test_gives_one_definition_for_the_three_uses(self):
        self.assertIn("raw bytes", self.section)
        self.assertIn("`sha256:`", self.section)
        self.assertIn("64 lowercase hexadecimal digits", self.section)
        for use in ("`expect_digest`", "`artifacts[].sha256`", "layer-5"):
            self.assertIn(use, self.section)

    def test_distinguishes_the_digest_from_the_git_blob_id(self):
        self.assertIn("git blob id", self.section)
        self.assertRegex(self.section, r"not (?:any of|the|a)\b")

    def test_distinguishes_the_digest_from_input_digest(self):
        self.assertIn("`input_digest`", self.section)
        self.assertIn("rule R1", self.section)
        self.assertIn("references/contracts/worker-envelope.md", self.section)

    def test_leaves_the_workflow_blob_definitions_unchanged(self):
        self.assertIn("`workflow_blob`", self.section)
        self.assertIn("`base_workflow_blob`", self.section)
        self.assertRegex(self.section, r"current definitions?")

    def test_does_not_name_the_git_command_as_a_means(self):
        # `git hash-object` lives only in the post-dispatch comparison and in
        # the owner's `Legacy records`.
        self.assertFalse(_names_git_hash_object(self.section))


class TestCalculation(unittest.TestCase):
    """AC-1 (second half): invocation, result reading, exit codes, TM-1."""

    @classmethod
    def setUpClass(cls):
        cls.raw = _section(_read(OWNER_PATH), "Calculation", level=2)
        cls.section = _norm(cls.raw)

    def test_names_the_python3_invocation_with_a_double_quoted_script_path(self):
        self.assertRegex(
            self.section,
            r'python3 "\$\{CLAUDE_PLUGIN_ROOT\}/scripts/artifact-digest\.py"',
        )

    def test_invocation_is_followed_by_single_quoted_target_paths(self):
        self.assertRegex(
            self.section,
            r'artifact-digest\.py" \'[^\']+\'',
        )

    def test_states_the_quoting_rule_tm1(self):
        self.assertIn("single-quoted", self.section)
        self.assertIn("one", self.section)
        self.assertRegex(
            self.section,
            r"single quote, a line break or NUL is never put into a command",
        )

    def test_quoting_rule_covers_both_failure_sites(self):
        self.assertRegex(self.section, r"before dispatch .{0,40}mismatch")
        self.assertRegex(self.section, r"layer 5 .{0,60}(?:validation )?failure")

    def test_states_how_the_result_is_read(self):
        self.assertIn("one JSON array", self.section)
        self.assertIn("argument order", self.section)
        self.assertIn("duplicates", self.section)
        self.assertIn("`path`", self.section)
        self.assertIn("`sha256`", self.section)

    def test_names_every_error_token(self):
        for token in ("`missing`", "`not_a_regular_file`", "`unreadable`"):
            self.assertIn(token, self.section)

    def test_states_the_meaning_of_each_exit_code(self):
        self.assertRegex(self.section, r"`0`[^.]*every element has a (?:`sha256`|digest)")
        self.assertRegex(self.section, r"`1`[^.]*(?:at least one|any) element")
        self.assertRegex(self.section, r"`2`[^.]*no argument")

    def test_states_that_the_call_is_not_a_workflow_yaml_command(self):
        self.assertIn("not a `workflow.yaml` command", self.section)
        self.assertIn("hooks/bash_guard.py", self.section)

    def test_does_not_name_the_git_command_as_a_means(self):
        self.assertFalse(_names_git_hash_object(self.section))


# ---------------------------------------------------------------------------
# AC-2: Pre-dispatch verification and Layer 5 recording
# ---------------------------------------------------------------------------


class TestPreDispatchVerification(unittest.TestCase):
    """AC-2 (first half), TM-5."""

    @classmethod
    def setUpClass(cls):
        cls.section = _norm(
            _section(_read(OWNER_PATH), "Pre-dispatch verification", level=2)
        )

    def test_states_the_timing_after_snapshot_immediately_before_dispatch(self):
        self.assertIn("clean-worktree precondition", self.section)
        self.assertIn("pre-dispatch snapshot", self.section)
        self.assertIn("references/phases/create-spec-phase.md", self.section)
        self.assertIn("immediately before the dispatch", self.section)

    def test_states_the_target_set(self):
        self.assertIn("every `write_policy.targets` entry", self.section)
        self.assertIn("requires `expect_digest`", self.section)
        self.assertIn("references/contracts/spec-writer-contract.md", self.section)

    def test_states_the_source_of_expect_digest(self):
        self.assertRegex(
            self.section, r"`expect_digest` values .{0,80}same calculation"
        )
        self.assertIn("action-decision time", self.section)

    def test_states_the_mismatch_outcome(self):
        self.assertRegex(self.section, r"no dispatch")
        self.assertIn("stale", self.section)
        self.assertIn("action decision", self.section)

    def test_an_error_element_counts_as_a_mismatch(self):
        self.assertRegex(self.section, r"(?:mismatch|differs).{0,120}`error`|`error`.{0,120}mismatch")

    def test_replace_authorized_mismatch_re_requests_approval(self):
        self.assertRegex(
            self.section, r"`replace_authorized`.{0,80}re-requests? approval"
        )

    def test_the_worker_never_repeats_the_verification(self):
        self.assertRegex(self.section, r"worker never repeats")
        self.assertIn("exclusivity assumption", self.section)
        self.assertIn("post-dispatch scope comparison", self.section)


class TestLayer5Recording(unittest.TestCase):
    """AC-2 (second half), TM-2."""

    @classmethod
    def setUpClass(cls):
        cls.section = _norm(_section(_read(OWNER_PATH), "Layer 5 recording", level=2))

    def test_runs_after_layer_4_passes(self):
        self.assertRegex(self.section, r"after layer 4 .{0,40}passes")

    def test_one_calculation_over_every_written_artifacts_path(self):
        self.assertIn("one `Calculation` call", self.section)
        self.assertIn("every `written_artifacts` path", self.section)

    def test_records_path_sha256_and_produced_by(self):
        self.assertIn("`{path, sha256, produced_by}`", self.section)

    def test_records_into_the_dispatching_phases_phase_state_file(self):
        for name in (
            "`create-spec.yaml`",
            "`design.yaml`",
            "`create-plan.yaml`",
            "`rework.yaml`",
        ):
            self.assertIn(name, self.section)
        self.assertIn("references/phase-state.md", self.section)
        self.assertIn("idempotency", self.section)

    def test_never_uses_a_worker_supplied_sha256_tm2(self):
        self.assertRegex(
            self.section,
            r"`sha256` the worker put in an entry is never (?:read|used)",
        )

    def test_preserve_targets_are_not_recorded(self):
        self.assertRegex(self.section, r"`preserve` targets? .{0,80}not recorded")

    def test_both_token_files_are_recorded_when_both_are_written(self):
        self.assertRegex(
            self.section,
            r"`tokens\.yaml` and `tokens\.html` are both written, both are recorded",
        )

    def test_an_error_element_fails_layer_5(self):
        self.assertRegex(self.section, r"error element\b.{0,120}fails layer 5")


# ---------------------------------------------------------------------------
# AC-3: Legacy records
# ---------------------------------------------------------------------------


class TestLegacyRecords(unittest.TestCase):
    """AC-3 (FR8, TM-3)."""

    @classmethod
    def setUpClass(cls):
        cls.section = _norm(_section(_read(OWNER_PATH), "Legacy records", level=2))

    def test_computes_the_legacy_digest_as_the_git_blob_id(self):
        self.assertIn("`git hash-object --`", self.section)
        self.assertIn("git blob id", self.section)

    def test_equality_after_dropping_an_optional_prefix_is_the_only_test(self):
        self.assertRegex(self.section, r"optional `sha256:` prefix")
        self.assertRegex(self.section, r"equal(?:ity)?")
        self.assertRegex(self.section, r"only test")

    def test_length_or_format_never_decides_tm3(self):
        self.assertRegex(self.section, r"[Ll]ength or format never decides")
        self.assertIn("64", self.section)  # a SHA-256 repository's blob ids

    def test_a_match_is_superseded_by_the_new_digest_at_layer_5(self):
        self.assertRegex(self.section, r"(?i)new digest.{0,120}supersedes|supersedes.{0,80}new digest")
        self.assertIn("Layer 5 recording", self.section)

    def test_a_non_match_goes_to_the_overwrite_gate_or_batch_policy(self):
        self.assertIn("`{phase}.artifact-overwrite`", self.section)
        self.assertIn("references/batch-policies.yaml", self.section)

    def test_applies_to_three_phases_and_leaves_rework_unchanged(self):
        for phase in ("create-spec", "design", "create-plan"):
            self.assertIn(phase, self.section)
        self.assertRegex(self.section, r"(?i)rework.{0,40}action choice is unchanged")

    def test_the_legacy_call_follows_the_quoting_rule(self):
        self.assertRegex(self.section, r"same (?:single-)?quot\w+ rule|quoting rule")


# ---------------------------------------------------------------------------
# AC-4: create-spec-phase.md (TS3)
# ---------------------------------------------------------------------------


class TestCreateSpecPhaseWiring(unittest.TestCase):
    """AC-4 (FR2, FR3, TS3)."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(CREATE_SPEC_PATH)
        cls.snapshot = _section(cls.text, "Pre-dispatch snapshot", level=3)
        cls.row = _table_row(cls.snapshot, "| `write_policy.targets` digests")
        cls.sec9 = _section(cls.text, "9. Spec writer dispatch", level=2)
        cls.sec10 = _section(cls.text, "10. Artifact validation", level=2)
        cls.digest_bullet = _bullet(cls.sec10, "Artifact digests (layer 5)")

    def test_snapshot_row_does_not_name_git_hash_object(self):
        self.assertFalse(_names_git_hash_object(self.row))

    def test_snapshot_row_cites_the_owner_calculation(self):
        self.assertTrue(_cites_owner(self.row, "Calculation"), self.row)

    def test_section_10_artifact_digests_item_does_not_name_git_hash_object(self):
        self.assertFalse(_names_git_hash_object(self.digest_bullet))

    def test_section_10_artifact_digests_item_cites_layer_5_recording(self):
        self.assertTrue(
            _cites_owner(self.digest_bullet, "Layer 5 recording"), self.digest_bullet
        )
        self.assertIn("phase-state/create-spec.yaml", _norm(self.digest_bullet))

    def test_section_9_cites_pre_dispatch_verification(self):
        self.assertTrue(_cites_owner(self.sec9, "Pre-dispatch verification"))

    def test_sections_9_and_10_do_not_name_git_hash_object(self):
        self.assertFalse(_names_git_hash_object(self.sec9))
        self.assertFalse(_names_git_hash_object(self.sec10))

    def test_snapshot_paragraph_states_the_targets_digest_is_not_a_git_blob_id(self):
        paragraph = _norm(_paragraph(self.snapshot, "The one pre-dispatch exception"))
        self.assertIn("not a git blob id", paragraph)
        self.assertIn("references/artifact-digest.md", paragraph)

    def test_snapshot_paragraph_keeps_blob_lookup_and_hashing_post_dispatch(self):
        paragraph = _norm(_paragraph(self.snapshot, "Both blob-ID/mode"))
        self.assertIn(
            "lookup and content hashing (`git hash-object --`) happen only in the "
            "post-dispatch comparison below",
            paragraph,
        )

    def test_post_dispatch_content_hashing_sentence_is_still_present(self):
        self.assertIn(
            "Content hashing with `git hash-object --` is applied only to the",
            self.text,
        )

    def test_post_dispatch_comparison_still_names_git_hash_object(self):
        post = _section(self.text, "Post-dispatch comparison (in this order)", level=3)
        self.assertTrue(_names_git_hash_object(post))


# ---------------------------------------------------------------------------
# AC-5: the other citing sites and the registry (TS11)
# ---------------------------------------------------------------------------


def _site_text(document, section):
    path = PLUGIN_ROOT / document
    text = _read(path)
    heads = {t: lvl for _i, lvl, t in _headings(text)}
    return _section(text, section, level=heads[section])


class TestDispatchSitesRegistry(unittest.TestCase):
    """AC-5, registry half."""

    @classmethod
    def setUpClass(cls):
        cls.rows = _parse_registry(_read(OWNER_PATH))

    def test_registry_lists_the_six_rows_with_their_covers(self):
        actual = {key: covers for key, (_worker, covers) in self.rows.items()}
        self.assertEqual(actual, EXPECTED_REGISTRY)

    def test_every_row_names_one_worker_with_an_agent_definition(self):
        for (document, section), (worker, _covers) in self.rows.items():
            agent = PLUGIN_ROOT / "agents" / f"{worker}.md"
            self.assertTrue(agent.is_file(), f"{document} / {section}: {worker}")

    def test_registry_names_four_distinct_dispatch_workers(self):
        self.assertEqual(len({worker for worker, _c in self.rows.values()}), 4)

    def test_every_registry_row_resolves_to_a_real_section(self):
        for (document, section) in self.rows:
            self.assertTrue((PLUGIN_ROOT / document).is_file(), document)
            _site_text(document, section)  # raises when absent or duplicated

    def test_every_worker_is_covered_for_both_owner_procedures(self):
        by_worker = {}
        for (_doc, _sec), (worker, covers) in self.rows.items():
            by_worker.setdefault(worker, set()).update(covers)
        for worker, covers in by_worker.items():
            self.assertEqual(
                covers,
                {"Pre-dispatch verification", "Layer 5 recording"},
                worker,
            )


class TestEverySiteCitesTheOwner(unittest.TestCase):
    """AC-5, citation half: each registry row's section names the owner path
    and every owner section its `Covers` lists; none restates the owner or
    names the git command."""

    @classmethod
    def setUpClass(cls):
        cls.rows = _parse_registry(_read(OWNER_PATH))

    def test_each_site_section_cites_its_covered_owner_sections(self):
        for (document, section), (_worker, covers) in self.rows.items():
            text = _site_text(document, section)
            for owner_section in covers:
                self.assertTrue(
                    _cites_owner(text, owner_section),
                    f"{document} / {section} lacks a citation of {owner_section}",
                )

    def test_no_site_section_names_git_hash_object(self):
        for (document, section) in self.rows:
            self.assertFalse(
                _names_git_hash_object(_site_text(document, section)),
                f"{document} / {section}",
            )

    def test_no_site_section_restates_the_digest_format_or_procedure(self):
        for (document, section) in self.rows:
            self.assertEqual(
                _restatement_markers_in(_site_text(document, section)),
                [],
                f"{document} / {section}",
            )

    def test_create_plan_phase_never_names_git_hash_object(self):
        self.assertFalse(_names_git_hash_object(_read(CREATE_PLAN_PATH)))

    def test_create_plan_sections_4_and_8_state_the_wiring_and_the_phase_state_file(self):
        sec4 = _norm(_site_text("references/phases/create-plan-phase.md", "4. Planner dispatch"))
        sec8 = _norm(_site_text("references/phases/create-plan-phase.md", "8. Validation"))
        self.assertIn("`write_policy.targets`", sec4)
        self.assertRegex(sec4, r"(?i)before the (?:`Task`|Task) dispatch|before dispatch")
        self.assertIn("phase-state/create-plan.yaml", sec8)
        self.assertIn("layer 5", sec8)

    def test_rework_dispatch_input_paragraph_records_into_rework_yaml(self):
        text = _read(REWORK_SYNTHESIS_PATH)
        sec = _site_text("references/rework-task-synthesis.md", "10. Workflow state transition")
        paragraph = _norm(_paragraph(sec, "Dispatch input (step 2, all four routes)"))
        self.assertIn(OWNER_CITATION, paragraph)
        self.assertIn("phase-state/rework.yaml", paragraph)
        self.assertRegex(paragraph, r"action choice is unchanged")
        self.assertIn("Dispatch input (step 2, all four routes)", text)

    def test_rework_existing_plugin_versioning_sentences_are_intact(self):
        paragraph = _norm(
            _paragraph(
                _site_text("references/rework-task-synthesis.md", "10. Workflow state transition"),
                "Dispatch input (step 2, all four routes)",
            )
        )
        self.assertIn(
            "this document restates neither the field's definition nor its resolution rules",
            paragraph,
        )


# ---------------------------------------------------------------------------
# AC-6: the develop skill's design step branch (TS12)
# ---------------------------------------------------------------------------


class TestDesignStepBranchDigestWiring(unittest.TestCase):
    """AC-6 (FR4, TM-4, TS12)."""

    @classmethod
    def setUpClass(cls):
        text = _read(DEVELOP_SKILL_PATH)
        cls.raw = _section(text, "design ステップ分岐", level=3)
        cls.section = _norm(cls.raw)

    def test_replace_own_is_decided_against_phase_state_design_yaml(self):
        self.assertRegex(
            self.section,
            r"`replace_own`.{0,160}`phase-state/design\.yaml`.{0,160}一致",
        )

    def test_the_comparison_follows_the_owner_including_legacy_records(self):
        self.assertTrue(_cites_owner(self.section, "Legacy records"))

    def test_absent_design_yaml_routes_existing_outputs_to_the_overwrite_gate(self):
        self.assertRegex(
            self.section,
            r"`phase-state/design\.yaml` が無.{0,200}(?:DESIGN\.md|mockup).{0,200}`design\.artifact-overwrite`",
        )
        self.assertIn("references/batch-policies.yaml", self.section)

    def test_the_absent_route_mirrors_legacy_feature_compatibility(self):
        self.assertIn("Legacy feature compatibility", self.section)
        self.assertIn("references/phase-state.md", self.section)

    def test_token_file_actions_stay_with_the_designer_contract(self):
        self.assertRegex(
            self.section,
            r"`tokens\.yaml` / `tokens\.html`.{0,80}designer-contract\.md",
        )

    def test_pre_dispatch_verification_precedes_the_designer_dispatch(self):
        verify_idx = self.section.index("Pre-dispatch verification")
        dispatch_idx = self.section.index("em-workflow:designer")
        self.assertLess(verify_idx, dispatch_idx)

    def test_a_mismatch_means_no_dispatch_stale_and_back_to_step_3(self):
        self.assertRegex(
            self.section,
            r"不一致.{0,60}dispatch しない.{0,100}stale.{0,100}3 に戻",
        )

    def test_layer_4_and_layer_5_recording_into_design_yaml(self):
        self.assertIn("layer 4", self.section)
        self.assertRegex(self.section, r"Scope verification")
        self.assertTrue(_cites_owner(self.section, "Layer 5 recording"))
        self.assertRegex(
            self.section,
            r"`phase-state/design\.yaml`.{0,80}`phase: design`",
        )

    def test_both_token_files_are_recorded_when_written(self):
        self.assertRegex(
            self.section,
            r"`tokens\.yaml` と `tokens\.html`.{0,40}両方.{0,40}記録",
        )

    def test_a_skipped_design_step_dispatches_nothing_and_creates_no_design_yaml(self):
        self.assertRegex(
            self.section,
            r"`skipped`.{0,120}dispatch しない.{0,80}`phase-state/design\.yaml`.{0,40}作らない",
        )

    def test_the_section_does_not_name_git_hash_object_or_restate_the_owner(self):
        self.assertFalse(_names_git_hash_object(self.section))
        self.assertEqual(_restatement_markers_in(self.section), [])

    def test_existing_pinned_phrases_are_intact(self):
        for phrase in (
            "em-workflow:designer",
            "事前条件から再開する",
            "status は 変更しない",
            "`kind: em_workflow` かつ yaml が無く html だけ実在する場合",
            "`designer-contract.md` の対応表どおりに",
        ):
            self.assertIn(phrase, self.section)
        # The raw, line-wrapped form an existing test pins byte-for-byte.
        self.assertIn("status は\n     変更しない", self.raw)
        ordering = [
            self.section.index("`kind: none`"),
            self.section.index("`kind: em_workflow` かつ yaml が無く html だけ実在する場合"),
            self.section.index("`designer-contract.md` の対応表どおりに"),
        ]
        self.assertEqual(ordering, sorted(ordering))


if __name__ == "__main__":
    unittest.main()
