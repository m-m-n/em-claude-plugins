"""Text tests for task0003 of verify-pass-resolves-deferred-findings: the
round record's `verify_resolution` field in
em-workflow/references/review-phase.md (Phase R5) and the deferred-findings
audit item in em-workflow/references/batch-mode.md (Reporting and the
audit-item source map).

Acceptance criteria covered (feature-docs/verify-pass-resolves-deferred-
findings/tasks/task0003.md):

- AC-1: review-phase.md defines `verify_resolution` with the five keys
  `verify_round`, `verified_commit`, `criteria_ids`, `previous_resolution`
  and `previous_resolution_reason`, gives the fixed-format sentence, names
  `resolve-verified-findings.py` as the writer and the latest round as the
  only round rewritten.
- AC-2: R5's Completion gate paragraph is unchanged and R5 contains neither
  `gate_id:` nor `batch-policies.yaml`.
- AC-3: batch-mode.md's Reporting presents the deferred-findings audit item
  with the fixed-by-verify-pass group apart from the still-deferred group,
  and states that `resolution_reason`, `previous_resolution_reason` and
  finding text are not transcribed.
- AC-4: batch-mode.md's audit-item source map names the latest review round
  record's findings with `resolution: fixed` and a `verify_resolution` as
  the source of the fixed-by-verify-pass group, and keeps the source of the
  still-deferred group.
- AC-5: batch-mode.md places no digit 1 or 3 within 60 characters of
  `verify_rework`, the lineage keyword or `hard cap`.

The tests locate each section by its heading and end it at the next heading
of the same or a higher level. Every check is a pure function of the text it
receives, so a forged text can be fed to it: each group ends with negative
proofs showing the matcher rejects a forged text. The module imports the
standard library only.
"""

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REFERENCES = REPO_ROOT / "em-workflow" / "references"
REVIEW_PHASE_PATH = REFERENCES / "review-phase.md"
BATCH_MODE_PATH = REFERENCES / "batch-mode.md"

R5_HEADING = "## Phase R5: Persist the round record"
REPORTING_HEADING = "## Reporting"
QUIET_OUTPUT_HEADING = "## Batch quiet output"

FIELDS_LEAD = "**Findings fixed by verify pass**"
COMPLETION_LEAD = "**Completion gate**"
DEFERRED_ITEM_LEAD = "The deferred-findings item"
SOURCE_MAP_LEAD = "**Audit-item source map.**"
DEFERRED_ROW_ITEM = "deferred findings"

VERIFY_RESOLUTION_KEYS = (
    "verify_round",
    "verified_commit",
    "criteria_ids",
    "previous_resolution",
    "previous_resolution_reason",
)
KEY_TYPE_PHRASES = {
    "verify_round": ["integer"],
    "verified_commit": ["string"],
    "criteria_ids": ["list of strings"],
    "previous_resolution": ["string", "`deferred`"],
    "previous_resolution_reason": ["null"],
}
REASON_SENTENCE = (
    "resolved by verify round {N}: acceptance criteria {IDs} passed"
)
WRITER_PATH = "`em-workflow/scripts/resolve-verified-findings.py`"

COMPLETION_GATE_TEXT = (
    "**Completion gate**: the review step may be marked `completed` ONLY when "
    "`residual_critical_high == 0`. Otherwise: offer another round / rework / "
    "explicit user acceptance (recorded as `deferred` with reason — this is "
    "the opt-out that keeps committed records free of undisclosed critical "
    "items). Batch mode: same rule, recorded as `deferred` per "
    "`references/batch-mode.md`'s Non-packet gates table (gate "
    "`review.residual-critical-high`) rather than offered interactively."
)

CAP_CONTEXT_KEYWORDS = ("verify_rework", "系譜", "hard cap")
CAP_THRESHOLD_DIGITS = ("1", "3")

HEADING_LINE = re.compile(r"^(#{1,6}) ")


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------


def _read(path):
    return path.read_text(encoding="utf-8")


def _norm(text):
    return re.sub(r"\s+", " ", text).strip()


def missing_phrases(text, phrases):
    """The phrases that do not occur in the whitespace-normalized `text`."""
    norm = _norm(text)
    return [phrase for phrase in phrases if phrase not in norm]


def section(text, heading):
    """The lines from the `heading` line up to the line before the next
    heading of the same or a higher level. Lines inside a fenced code block
    are never taken for headings."""
    level = len(heading) - len(heading.lstrip("#"))
    taken = []
    started = False
    in_fence = False
    for line in text.splitlines(keepends=True):
        bare = line.rstrip("\r\n")
        if bare.lstrip().startswith("```"):
            in_fence = not in_fence
        elif not in_fence:
            match = HEADING_LINE.match(bare)
            if started and match and len(match.group(1)) <= level:
                break
            if not started and bare == heading:
                started = True
        if started:
            taken.append(line)
    if not started:
        raise AssertionError("heading not found: " + heading)
    return "".join(taken)


def paragraph(text, lead):
    """The block that starts at `lead` and runs up to the next blank line."""
    start = text.index(lead)
    end = text.find("\n\n", start + len(lead))
    return text[start:] if end == -1 else text[start:end]


class Docs:
    _cache = {}

    @classmethod
    def _text(cls, path):
        if path not in cls._cache:
            cls._cache[path] = _read(path)
        return cls._cache[path]

    @classmethod
    def r5(cls):
        return section(cls._text(REVIEW_PHASE_PATH), R5_HEADING)

    @classmethod
    def reporting(cls):
        return section(cls._text(BATCH_MODE_PATH), REPORTING_HEADING)

    @classmethod
    def quiet_output(cls):
        return section(cls._text(BATCH_MODE_PATH), QUIET_OUTPUT_HEADING)

    @classmethod
    def batch_mode(cls):
        return cls._text(BATCH_MODE_PATH)


# ---------------------------------------------------------------------------
# AC-1: review-phase.md defines verify_resolution
# ---------------------------------------------------------------------------


def verify_resolution_fields(r5):
    """(key, normalized description) of every bullet of the list that follows
    FIELDS_LEAD, in order."""
    lines = r5[r5.index(FIELDS_LEAD):].splitlines()[1:]
    fields = []
    for line in lines:
        bullet = re.match(r"^- `([A-Za-z_]+)`: ?(.*)$", line)
        if bullet:
            fields.append([bullet.group(1), bullet.group(2)])
        elif line.strip() == "":
            if fields:
                break
        elif fields and line.startswith("  "):
            fields[-1][1] += " " + line.strip()
        elif fields:
            break
    return [(key, _norm(description)) for key, description in fields]


def defines_exactly_the_five_keys(r5):
    keys = [key for key, _ in verify_resolution_fields(r5)]
    return tuple(keys) == VERIFY_RESOLUTION_KEYS


def gives_each_key_its_type(r5):
    described = dict(verify_resolution_fields(r5))
    for key, phrases in KEY_TYPE_PHRASES.items():
        if key not in described:
            return False
        if missing_phrases(described[key], phrases):
            return False
    return True


def gives_the_fixed_format_reason(r5):
    return not missing_phrases(
        r5,
        [
            "its `resolution_reason` is exactly the sentence `"
            + REASON_SENTENCE
            + "`",
            "`{N}` is `verify_resolution.verify_round`",
            "`{IDs}` is `verify_resolution.criteria_ids` joined with a comma "
            "and one space",
        ],
    )


def names_writer_and_latest_round_only(r5):
    return not missing_phrases(
        r5,
        [
            "The writer is " + WRITER_PATH,
            "It rewrites the latest round record only",
        ],
    )


class TestAC1VerifyResolutionDefinition(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r5 = Docs.r5()

    def test_the_field_block_is_in_phase_r5(self):
        self.assertIn(FIELDS_LEAD, self.r5)

    def test_verify_resolution_is_optional_and_only_on_a_fixed_by_verify_finding(
        self,
    ):
        self.assertEqual(
            missing_phrases(
                paragraph(self.r5, FIELDS_LEAD),
                [
                    "`verify_resolution`, an optional field present only on a "
                    "finding fixed by verify pass",
                    "a mapping with exactly these five keys",
                ],
            ),
            [],
        )

    def test_verify_resolution_has_exactly_the_five_keys(self):
        self.assertTrue(defines_exactly_the_five_keys(self.r5))

    def test_each_key_has_its_type_and_meaning(self):
        self.assertTrue(gives_each_key_its_type(self.r5))

    def test_the_resolution_reason_sentence_is_given(self):
        self.assertTrue(gives_the_fixed_format_reason(self.r5))

    def test_a_fixed_finding_has_resolution_fixed(self):
        self.assertEqual(
            missing_phrases(
                self.r5, ["The `resolution` of such a finding is `fixed`"]
            ),
            [],
        )

    def test_the_writer_and_the_only_round_rewritten_are_named(self):
        self.assertTrue(names_writer_and_latest_round_only(self.r5))

    def test_the_conditions_are_cited_from_the_develop_skill_not_restated(self):
        self.assertEqual(
            missing_phrases(
                self.r5, ["`skills/develop/SKILL.md`「verify フェーズ」"]
            ),
            [],
        )
        self.assertNotIn("passed_ids", self.r5)
        self.assertNotIn("--verified-commit", self.r5)

    def test_the_merge_preflight_reads_the_finding_as_resolved_unchanged(self):
        self.assertEqual(
            missing_phrases(
                self.r5,
                [
                    "counts as resolved for the merge preflight because "
                    "its `resolution` is `fixed`",
                    "the preflight's rule is unchanged",
                ],
            ),
            [],
        )

    def test_the_round_record_example_points_at_the_field(self):
        yaml_start = self.r5.index("```yaml")
        yaml_end = self.r5.index("\n```", yaml_start + len("```yaml"))
        comments = [
            line
            for line in self.r5[yaml_start:yaml_end].splitlines()
            if line.lstrip().startswith("#")
        ]
        self.assertTrue(any("verify_resolution" in line for line in comments))

    def test_negative_proof_a_definition_missing_a_key(self):
        forged = re.sub(
            r"(?m)^- `previous_resolution_reason`:.*(?:\n  .*)*\n", "", self.r5
        )
        self.assertNotEqual(forged, self.r5)
        self.assertFalse(defines_exactly_the_five_keys(forged))

    def test_negative_proof_a_definition_with_an_extra_key(self):
        forged = self.r5.replace(
            "\n- `previous_resolution_reason`:",
            "\n- `extra_key`: string; not part of the definition.\n"
            "- `previous_resolution_reason`:",
            1,
        )
        self.assertNotEqual(forged, self.r5)
        self.assertFalse(defines_exactly_the_five_keys(forged))

    def test_negative_proof_a_key_without_its_type(self):
        forged = self.r5.replace("`verify_round`: integer", "`verify_round`: ", 1)
        self.assertNotEqual(forged, self.r5)
        self.assertFalse(gives_each_key_its_type(forged))

    def test_negative_proof_a_different_reason_sentence(self):
        forged = self.r5.replace(REASON_SENTENCE, "resolved by verify")
        self.assertNotEqual(forged, self.r5)
        self.assertFalse(gives_the_fixed_format_reason(forged))

    def test_negative_proof_a_writer_that_rewrites_every_round(self):
        forged = self.r5.replace(
            "It rewrites the latest round record only",
            "It rewrites every round record",
        )
        self.assertNotEqual(forged, self.r5)
        self.assertFalse(names_writer_and_latest_round_only(forged))

    def test_negative_proof_a_different_writer(self):
        forged = self.r5.replace(WRITER_PATH, "`em-workflow/scripts/other.py`")
        self.assertNotEqual(forged, self.r5)
        self.assertFalse(names_writer_and_latest_round_only(forged))


# ---------------------------------------------------------------------------
# AC-2: R5's Completion gate paragraph and pinned absences
# ---------------------------------------------------------------------------


def completion_gate_is_unchanged(r5):
    return _norm(paragraph(r5, COMPLETION_LEAD)) == COMPLETION_GATE_TEXT


def has_gate_id_or_batch_policy_reference(r5):
    return "gate_id:" in r5 or "batch-policies.yaml" in r5


class TestAC2R5WordingStays(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r5 = Docs.r5()

    def test_completion_gate_paragraph_is_unchanged(self):
        self.assertTrue(completion_gate_is_unchanged(self.r5))

    def test_r5_gains_neither_a_gate_id_nor_a_batch_policy_reference(self):
        self.assertFalse(has_gate_id_or_batch_policy_reference(self.r5))

    def test_negative_proof_a_gate_paragraph_with_an_added_condition(self):
        forged = self.r5.replace(
            "`residual_critical_high == 0`. Otherwise",
            "`residual_critical_high == 0` AND `verify_resolution` is set. "
            "Otherwise",
            1,
        )
        self.assertNotEqual(forged, self.r5)
        self.assertFalse(completion_gate_is_unchanged(forged))

    def test_negative_proof_a_gate_identifier_is_detected(self):
        self.assertTrue(
            has_gate_id_or_batch_policy_reference(self.r5 + "\ngate_id: x\n")
        )

    def test_negative_proof_a_batch_policy_reference_is_detected(self):
        self.assertTrue(
            has_gate_id_or_batch_policy_reference(
                self.r5 + "\nsee batch-policies.yaml\n"
            )
        )


# ---------------------------------------------------------------------------
# AC-3: Reporting shows the two groups of the deferred-findings item
# ---------------------------------------------------------------------------


def _groups(item):
    """(group a text, group b text) of the deferred-findings item paragraph,
    or None when either marker is missing or they are out of order."""
    norm = _norm(item)
    a = norm.find("Group (a)")
    b = norm.find("Group (b)")
    if a == -1 or b == -1 or a > b:
        return None
    return norm[a:b], norm[b:]


def shows_two_groups_apart(reporting):
    item = paragraph(reporting, DEFERRED_ITEM_LEAD)
    groups = _groups(item)
    if groups is None:
        return False
    fixed, deferred = groups
    if "two groups" not in _norm(item):
        return False
    if missing_phrases(
        fixed,
        [
            "fixed by verify pass",
            "`stable_id`",
            "verify round (`verify_resolution.verify_round`)",
            "criteria IDs (`verify_resolution.criteria_ids`)",
        ],
    ):
        return False
    return (
        "still deferred" in deferred
        and "`stable_id`" in deferred
        and "verify_resolution" not in deferred
    )


def states_free_text_is_not_transcribed(reporting):
    item = paragraph(reporting, DEFERRED_ITEM_LEAD)
    return not missing_phrases(
        item,
        [
            "The item carries only those structured values",
            "`resolution_reason`, `previous_resolution_reason` and finding "
            "text are not transcribed",
        ],
    )


class TestAC3ReportingDeferredFindingsItem(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.reporting = Docs.reporting()

    def test_reporting_names_the_structured_fields(self):
        norm = _norm(self.reporting)
        for name in (
            "verify_resolution",
            "verify_round",
            "criteria_ids",
            "previous_resolution_reason",
        ):
            with self.subTest(name=name):
                self.assertIn(name, norm)

    def test_the_fixed_by_verify_pass_group_is_shown_apart_from_the_deferred_one(
        self,
    ):
        self.assertTrue(shows_two_groups_apart(self.reporting))

    def test_free_text_is_not_transcribed(self):
        self.assertTrue(states_free_text_is_not_transcribed(self.reporting))

    def test_the_item_is_in_the_reporting_section_before_the_quiet_output(self):
        text = Docs.batch_mode()
        item = text.index(DEFERRED_ITEM_LEAD)
        self.assertGreater(item, text.index("\n" + REPORTING_HEADING + "\n"))
        self.assertLess(item, text.index("\n" + QUIET_OUTPUT_HEADING + "\n"))

    def test_negative_proof_a_report_with_a_single_undivided_group(self):
        forged = self.reporting.replace("Group (b)", "Also")
        self.assertNotEqual(forged, self.reporting)
        self.assertFalse(shows_two_groups_apart(forged))

    def test_negative_proof_groups_in_the_wrong_order(self):
        forged = (
            self.reporting.replace("Group (a)", "Group (X)")
            .replace("Group (b)", "Group (a)")
            .replace("Group (X)", "Group (b)")
        )
        self.assertNotEqual(forged, self.reporting)
        self.assertFalse(shows_two_groups_apart(forged))

    def test_negative_proof_a_fixed_group_without_the_criteria_ids(self):
        forged = self.reporting.replace(
            "`verify_resolution.criteria_ids`", "`criteria`", 1
        )
        self.assertNotEqual(forged, self.reporting)
        self.assertFalse(shows_two_groups_apart(forged))

    def test_negative_proof_a_deferred_group_that_mixes_in_verify_fields(self):
        item = paragraph(self.reporting, DEFERRED_ITEM_LEAD)
        forged = self.reporting.replace(
            item, item + " Group (b) also lists `verify_resolution`."
        )
        self.assertNotEqual(forged, self.reporting)
        self.assertFalse(shows_two_groups_apart(forged))

    def test_negative_proof_a_report_that_transcribes_the_reason(self):
        reporting = _norm(self.reporting)
        forged = reporting.replace(
            "`resolution_reason`, `previous_resolution_reason` and finding "
            "text are not transcribed",
            "`resolution_reason` is transcribed",
        )
        self.assertNotEqual(forged, reporting)
        self.assertFalse(states_free_text_is_not_transcribed(forged))


# ---------------------------------------------------------------------------
# AC-4: audit-item source map
# ---------------------------------------------------------------------------


def source_map_rows(quiet_output):
    """Every data row of the audit-item source map table as a list of
    cells."""
    table = quiet_output[quiet_output.index(SOURCE_MAP_LEAD):]
    rows = []
    for line in table.splitlines():
        stripped = line.strip()
        if not (stripped.startswith("|") and stripped.endswith("|")):
            continue
        cells = [cell.strip() for cell in stripped.strip("|").split("|")]
        if all(cell and set(cell) <= {"-", " ", ":"} for cell in cells):
            continue
        rows.append(cells)
    return rows[1:]


def deferred_row_source(quiet_output):
    for item, source in source_map_rows(quiet_output):
        if DEFERRED_ROW_ITEM in item:
            return source
    return None


def source_names_the_fixed_by_verify_group(source):
    if source is None:
        return False
    return not missing_phrases(
        source,
        [
            "the fixed-by-verify-pass group is the latest review round "
            "record's findings with `resolution: fixed` and a "
            "`verify_resolution`",
            "`verify_resolution.verify_round`",
            "`verify_resolution.criteria_ids`",
        ],
    )


def source_keeps_the_still_deferred_group(source):
    if source is None:
        return False
    return not missing_phrases(
        source,
        [
            "`feature-docs/{feature}/reviews/roundN.yaml` `resolution` / "
            "`stable_id`",
            "the still-deferred group is the findings with resolution "
            "`deferred`",
        ],
    )


class TestAC4AuditItemSourceMap(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.quiet = Docs.quiet_output()
        cls.source = deferred_row_source(cls.quiet)

    def test_the_deferred_findings_row_exists_in_the_source_map(self):
        self.assertIsNotNone(self.source)

    def test_the_fixed_by_verify_pass_group_has_its_source(self):
        self.assertTrue(source_names_the_fixed_by_verify_group(self.source))

    def test_the_still_deferred_group_keeps_its_source(self):
        self.assertTrue(source_keeps_the_still_deferred_group(self.source))

    def test_the_source_map_is_cut_at_the_table_not_at_a_far_row(self):
        items = [item for item, _ in source_map_rows(self.quiet)]
        self.assertEqual(items[-1], "The kept integration branch name")

    def test_negative_proof_a_source_without_the_verify_resolution_group(self):
        forged = self.source.replace("`verify_resolution`", "`other`")
        self.assertNotEqual(forged, self.source)
        self.assertFalse(source_names_the_fixed_by_verify_group(forged))

    def test_negative_proof_a_source_that_reads_every_round(self):
        forged = self.source.replace(
            "latest review round record's", "every review round record's"
        )
        self.assertNotEqual(forged, self.source)
        self.assertFalse(source_names_the_fixed_by_verify_group(forged))

    def test_negative_proof_a_source_that_drops_the_deferred_group(self):
        forged = self.source.replace(
            "the still-deferred group is the findings with resolution "
            "`deferred`",
            "",
        )
        self.assertNotEqual(forged, self.source)
        self.assertFalse(source_keeps_the_still_deferred_group(forged))

    def test_negative_proof_a_map_without_the_deferred_row(self):
        forged = "\n".join(
            line
            for line in self.quiet.splitlines()
            if "deferred findings" not in line
        )
        self.assertNotEqual(forged, self.quiet)
        self.assertIsNone(deferred_row_source(forged))


# ---------------------------------------------------------------------------
# AC-5: no digit 1 or 3 near the verify-cap vocabulary in batch-mode.md
# ---------------------------------------------------------------------------


def cap_numeral_absent_near_keywords(text, window=60):
    """True iff no cap-threshold digit (1 or 3) appears within `window`
    characters of any of CAP_CONTEXT_KEYWORDS."""
    pattern = "|".join(re.escape(keyword) for keyword in CAP_CONTEXT_KEYWORDS)
    for match in re.finditer(pattern, text, flags=re.IGNORECASE):
        start = max(0, match.start() - window)
        end = min(len(text), match.end() + window)
        for number in re.finditer(r"\d+", text[start:end]):
            if number.group(0) in CAP_THRESHOLD_DIGITS:
                return False
    return True


class TestAC5NoCapNumeralInBatchMode(unittest.TestCase):
    def test_batch_mode_places_no_digit_1_or_3_near_the_cap_vocabulary(self):
        self.assertTrue(cap_numeral_absent_near_keywords(Docs.batch_mode()))

    def test_negative_proof_a_digit_near_the_keyword_is_detected(self):
        self.assertFalse(
            cap_numeral_absent_near_keywords(
                "the batch.verify_rework hard cap value is 3 rounds"
            )
        )

    def test_negative_proof_a_digit_near_the_lineage_keyword_is_detected(self):
        self.assertFalse(cap_numeral_absent_near_keywords("系譜 cap は 1 回"))

    def test_non_vacuity_a_digit_far_from_the_keywords_is_accepted(self):
        self.assertTrue(
            cap_numeral_absent_near_keywords(
                "batch.verify_rework tracks the history; "
                + ("padding " * 40)
                + "review's own cap 1 wording lives far away"
            )
        )

    def test_the_new_text_of_this_task_adds_no_such_digit(self):
        new_text = "\n".join(
            [
                paragraph(Docs.reporting(), DEFERRED_ITEM_LEAD),
                str(deferred_row_source(Docs.quiet_output())),
            ]
        )
        self.assertTrue(cap_numeral_absent_near_keywords(new_text))
        self.assertFalse(
            re.search(r"\b[13]\b", new_text),
            "the new batch-mode text carries a bare digit 1 or 3",
        )


if __name__ == "__main__":
    unittest.main()
