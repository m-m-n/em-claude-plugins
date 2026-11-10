"""Text inspection of Phase R2, Phase R2b and the README for the shard dispatch
of the large-diff-review-coverage feature (task0004).

Acceptance criteria covered:

- AC-1: Phase R2 states the measurement step before the fan-out (input built
  from Phase R0's values, `perspective_count`, abort on a non-zero exit), the
  unsplit dispatch as before, the per-shard dispatch of every non-spec
  perspective limited to `dispatched_shards`, excess shards left undispatched,
  and one procedure for develop-driven, standalone, diff and whole-codebase
  runs.
- AC-2: a shard dispatch carries the unchanged input block with `changed_files`
  set to the shard's paths and `diff_cmd_quoted` built from the Phase R0 step 3
  validated paths; no input field is added.
- AC-3: the run_id paragraph states the whole run_id grammar; no
  `{perspective}#loop{N}` form is left in Phase R2 or Phase R2b.
- AC-4: Phase R2b applies the walk, the two-hop budget, the Claude fallback and
  the last-result replacement per shard.
- AC-5: the Phase R2b table has a fourth row for `review_data_too_large` and
  a fifth, last row for `contributor_consent_missing`; the schema-validity
  paragraph states the litellm exception decided by `classify_results` on the
  recorded harness.
- AC-6: Phase R2b states the spec order and the rescue runs.
- AC-7: the README states per-shard dispatch and the `review_data_too_large`
  route; the reviewer input fields and `review-output-schema.json` are
  unchanged; this module uses only the standard library.

muse-guard-deny-recovery task0003 adds:

- the fifth Phase R2b routing row, `contributor_consent_missing`, advancing to
  the next entry in the chain (FR3);
- the note on that row (consent belongs to the contributor tier, the walk
  resumes after the recorded chain index, no re-judgment and no chain edit, the
  2-hop budget, an exhausted chain takes the Claude fallback) (FR3);
- the precedence statement placed right after the harness-level paragraph
  (FR4);
- the README hop paragraph putting the value in the next-entry group (FR8).

The matchers slice Phase R2 and Phase R2b by their headings and compare
whitespace-normalized phrases. Every matcher gets forged texts it must reject.
"""

import ast
import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"
REVIEW_PHASE_PATH = PLUGIN_ROOT / "references" / "review-phase.md"
README_PATH = PLUGIN_ROOT / "README.md"
SCHEMA_PATH = PLUGIN_ROOT / "references" / "review-output-schema.json"

R2_HEADING = "## Phase R2: Fan-out (ONE message, N Task calls)"
R2B_HEADING = "## Phase R2b: Cross-model fallback (chain walk)"
R3A_HEADING = "## Phase R3a: Evaluation (single Opus evaluator)"


def _read(path):
    return path.read_text(encoding="utf-8")


def _norm(text):
    return re.sub(r"\s+", " ", text).strip()


def _slice(text, start_heading, end_heading):
    start = text.index(start_heading)
    end = text.index(end_heading, start + len(start_heading))
    return text[start:end]


def _paragraph(text, anchor):
    """The blank-line separated paragraph of `text` that contains `anchor`;
    an empty string when no paragraph does."""
    for block in re.split(r"\n\s*\n", text):
        if anchor in _norm(block):
            return block
    return ""


def _forge(text, anchor, old, new=""):
    """`text` with `old` replaced by `new` inside the paragraph holding
    `anchor` (compared whitespace-normalized, so a phrase wrapped over lines
    in the document is still found). Fails loudly when the mutation cannot
    apply, so a forged text is never accidentally identical to the real one."""
    paragraph = _paragraph(text, anchor)
    assert paragraph, f"no paragraph holds {anchor!r}"
    norm_paragraph = _norm(paragraph)
    assert old in norm_paragraph, f"{old!r} not in the paragraph of {anchor!r}"
    return text.replace(paragraph, norm_paragraph.replace(old, new, 1), 1)


def _contains_all(text, phrases):
    norm = _norm(text)
    return all(phrase in norm for phrase in phrases)


class _Doc:
    _text = None

    @classmethod
    def text(cls):
        if cls._text is None:
            cls._text = _read(REVIEW_PHASE_PATH)
        return cls._text

    @classmethod
    def r2(cls):
        return _slice(cls.text(), R2_HEADING, R2B_HEADING)

    @classmethod
    def r2b(cls):
        return _slice(cls.text(), R2B_HEADING, R3A_HEADING)


# ---------------------------------------------------------------------------
# AC-1: the measurement step and the dispatch rules of Phase R2
# ---------------------------------------------------------------------------

MEASURE_ANCHOR = "review-shards.py"

MEASURE_PHRASES = [
    "builds the `review-shards` input from Phase R0's values",
    "`project_root`, `review_mode`, `diff_base` (develop-駆動: "
    "`base_commit`; standalone: `HEAD`; whole-codebase: null)",
    "`changed_files` exactly as Phase R0 step 3 validated them",
    "`perspective_count`",
    "the number of perspectives this phase dispatches through Task this round",
    "`spec` counts when it is dispatched",
    "axis 2 `vulnerability` do not count",
    "with its file-writing tool into the session scratchpad directory, "
    "outside `project_root`",
    "never through shell interpolation",
    'python3 "${CLAUDE_PLUGIN_ROOT}/scripts/review-shards.py"',
    "reads only its JSON output",
    "`limit`, `total_chars`, `split`, `files`, `shards`, `shard_cap`, "
    "`dispatched_shards`, `excess_shards`",
    "never reads diff text to measure size",
    "kept as the pass manifest of loop 0",
    "A non-zero exit aborts the review phase",
    "before any dispatch of this pass",
    "no round record is written",
    "develop-駆動 and standalone runs, diff and whole-codebase modes, "
    "and Phase R4's re-review",
]

SPLIT_ANCHOR = "Dispatch per shard."

SPLIT_PHRASES = [
    "When `split` is false, dispatch exactly as above",
    "the round's full `changed_files` and `diff_cmd_quoted`",
    "run_ids below unchanged",
    "When `split` is true, each non-spec perspective is dispatched once per "
    "index in `dispatched_shards`",
    "Shards listed in `excess_shards` are not dispatched",
    "Phase R5 discloses them",
    "`spec` is dispatched once, on the full diff, in both cases",
]


def measurement_step_ok(r2):
    """AC-1: the measurement paragraph states the input, the script call, the
    output keys and the abort, and sits before the first Task dispatch."""
    paragraph = _paragraph(r2, MEASURE_ANCHOR)
    if not paragraph or not _contains_all(paragraph, MEASURE_PHRASES):
        return False
    norm = _norm(r2)
    first_dispatch = norm.find("Task(subagent_type=")
    return first_dispatch != -1 and norm.index(MEASURE_ANCHOR) < first_dispatch


def split_dispatch_ok(r2):
    """AC-1: unsplit dispatch as before; split dispatch per index of
    `dispatched_shards`; excess shards undispatched; spec once."""
    paragraph = _paragraph(r2, SPLIT_ANCHOR)
    return bool(paragraph) and _contains_all(paragraph, SPLIT_PHRASES)


PINNED_ONE_PRIMARY_PHRASES = [
    "Dispatch exactly ONE primary reviewer for this perspective "
    "(per shard when the round is split)",
    "Exactly one primary reviewer runs per selected perspective "
    "(per shard when the round is split)",
    "All Task calls go in a SINGLE message.",
]


def one_primary_qualified_ok(r2):
    return _contains_all(r2, PINNED_ONE_PRIMARY_PHRASES)


class TestAC1PhaseR2MeasurementAndDispatch(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r2 = _Doc.r2()

    def test_measurement_step_is_stated_before_the_fan_out(self):
        self.assertTrue(measurement_step_ok(self.r2))

    def test_unsplit_and_split_dispatch_are_stated(self):
        self.assertTrue(split_dispatch_ok(self.r2))

    def test_pinned_one_primary_sentences_are_qualified_per_shard(self):
        self.assertTrue(one_primary_qualified_ok(self.r2))

    def test_every_measurement_phrase_is_load_bearing(self):
        for phrase in MEASURE_PHRASES:
            with self.subTest(phrase=phrase):
                mutated = _forge(self.r2, MEASURE_ANCHOR, phrase)
                self.assertFalse(measurement_step_ok(mutated))

    def test_every_split_dispatch_phrase_is_load_bearing(self):
        for phrase in SPLIT_PHRASES:
            with self.subTest(phrase=phrase):
                mutated = _forge(self.r2, SPLIT_ANCHOR, phrase)
                self.assertFalse(split_dispatch_ok(mutated))

    def test_forged_measurement_after_the_first_dispatch_is_rejected(self):
        paragraph = _paragraph(self.r2, MEASURE_ANCHOR)
        self.assertTrue(paragraph)
        moved = self.r2.replace(paragraph, "", 1) + "\n\n" + paragraph
        self.assertTrue(moved != self.r2, "mutation did not apply")
        self.assertFalse(measurement_step_ok(moved))

    def test_forged_measurement_without_abort_is_rejected(self):
        forged = _forge(
            self.r2,
            MEASURE_ANCHOR,
            "A non-zero exit aborts the review phase",
            "A non-zero exit is ignored and the pass dispatches unsplit",
        )
        self.assertFalse(measurement_step_ok(forged))

    def test_forged_dispatch_of_every_shard_is_rejected(self):
        forged = _forge(
            self.r2,
            SPLIT_ANCHOR,
            "once per index in `dispatched_shards`",
            "once per shard of the `shards` list",
        )
        self.assertFalse(split_dispatch_ok(forged))

    def test_forged_unqualified_one_primary_sentence_is_rejected(self):
        forged = self.r2.replace(" (per shard when the round is split)", "")
        self.assertTrue(forged != self.r2, "mutation did not apply")
        self.assertFalse(one_primary_qualified_ok(forged))

    def test_task_calls_still_go_in_one_message_for_split_rounds(self):
        norm = _norm(self.r2)
        self.assertIn("Shard dispatches are Task calls too", norm)

    def test_orchestrator_still_passes_only_paths_never_diff_content(self):
        # The measurement step passes paths and counts only; the Phase R2
        # rule that no diff content enters the orchestrator stays.
        norm = _norm(self.r2)
        self.assertIn("never diff content", norm)


# ---------------------------------------------------------------------------
# AC-2: the shard input block
# ---------------------------------------------------------------------------

SHARD_INPUT_PHRASES = [
    "A shard dispatch carries the same input block",
    "`changed_files` is that shard's paths",
    "normalized to project_root-based absolute paths as above",
    "`diff_cmd_quoted` is built from those same paths",
    "each an element of the Phase R0 step 3 validated set",
    "the same `printf %q` quoting",
    "the same command form Phase R0 step 3 uses",
    "No input field is added",
    "a shard is expressed only through `changed_files` and `diff_cmd_quoted`",
]

# The input block's field list as Phase R2 stated it before this feature: the
# reviewers' inputs do not change (NFR5).
INPUT_BLOCK_FIELDS_SENTENCE = (
    "same review-protocol input block (perspective, perspective_skill = "
    "`em-workflow:` + registry `claude_skill` (e.g. "
    "`em-workflow:review-security`), review_mode, protocol_path, "
    "schema_path, changed_files, diff_cmd_quoted, spec_path when perspective "
    "== spec, project_license when perspective == license (develop-駆動: "
    "workflow.yaml `project.license`; standalone: detect from "
    "`{project_root}/LICENSE*`, `none` when absent), project_root, "
    "round_context, lessons)."
)


def shard_input_block_ok(r2):
    paragraph = _paragraph(r2, SPLIT_ANCHOR)
    if not paragraph or not _contains_all(paragraph, SHARD_INPUT_PHRASES):
        return False
    # The shard sentence must not hand the script's text to the command: it
    # names the validated set as the only source of the paths.
    return not re.search(
        r"re-?join(ed)? from the script output|from the script output text",
        _norm(paragraph),
    )


def input_block_fields_unchanged(r2):
    return INPUT_BLOCK_FIELDS_SENTENCE in _norm(r2)


class TestAC2ShardInputBlock(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r2 = _Doc.r2()

    def test_shard_dispatch_input_block_is_stated(self):
        self.assertTrue(shard_input_block_ok(self.r2))

    def test_reviewer_input_field_list_is_unchanged(self):
        self.assertTrue(input_block_fields_unchanged(self.r2))

    def test_every_shard_input_phrase_is_load_bearing(self):
        for phrase in SHARD_INPUT_PHRASES:
            with self.subTest(phrase=phrase):
                mutated = _forge(self.r2, SPLIT_ANCHOR, phrase)
                self.assertFalse(shard_input_block_ok(mutated))

    def test_forged_cmd_rejoined_from_script_output_is_rejected(self):
        forged = _forge(
            self.r2,
            SPLIT_ANCHOR,
            "each an element of the Phase R0 step 3 validated set",
            "each re-joined from the script output text",
        )
        self.assertFalse(shard_input_block_ok(forged))

    def test_forged_added_shard_field_is_rejected(self):
        forged = _forge(
            self.r2,
            SPLIT_ANCHOR,
            "No input field is added",
            "A `shard_index` input field is added",
        )
        self.assertFalse(shard_input_block_ok(forged))

    def test_forged_field_list_with_a_shard_field_is_rejected(self):
        forged = self.r2.replace(
            "round_context, lessons)", "round_context, lessons, shard_index)", 1
        )
        self.assertTrue(forged != self.r2, "mutation did not apply")
        self.assertFalse(input_block_fields_unchanged(forged))

    def test_review_output_schema_has_no_shard_property(self):
        schema = json.loads(_read(SCHEMA_PATH))
        self.assertNotIn("shard", json.dumps(schema).lower())


# ---------------------------------------------------------------------------
# AC-3: the run_id grammar
# ---------------------------------------------------------------------------

RUN_ID_ANCHOR = "{perspective}[@s{k}]#[loop{N}.]{chain_index|fallback}"

RUN_ID_PHRASES = [
    RUN_ID_ANCHOR,
    "`@s{k}` is present only for a run in a split pass",
    "`k` being the shard index from the review-shards output",
    "`spec` carries it only as a rescue run",
    "`loop{N}.` is present only for Phase R4 loop N",
    "N starting at 1",
    "the chain index (integer, 0 or more) of the dispatched chain entry",
    "or `fallback` for the Claude fallback",
    "An unsplit Phase R2 run keeps `{perspective}#{chain_index}` or "
    "`{perspective}#fallback`",
    "`vulnerability#tool` and `evaluator` are unchanged",
    "`security#0`",
    "`performance@s2#1`",
    "`spec@s1#fallback`",
    "`architecture@s3#loop1.0`",
    "`comprehensive#loop2.fallback`",
]

OLD_LOOP_RUN_ID_FORM = "{perspective}#loop{N}"


def run_id_grammar_ok(r2):
    paragraph = _paragraph(r2, RUN_ID_ANCHOR)
    return bool(paragraph) and _contains_all(paragraph, RUN_ID_PHRASES)


def no_old_loop_form(*sections):
    return all(OLD_LOOP_RUN_ID_FORM not in _norm(s) for s in sections)


class TestAC3RunIdGrammar(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r2 = _Doc.r2()
        cls.r2b = _Doc.r2b()

    def test_whole_grammar_is_stated(self):
        self.assertTrue(run_id_grammar_ok(self.r2))

    def test_old_phase_r4_run_id_form_is_gone_from_r2_and_r2b(self):
        self.assertTrue(no_old_loop_form(self.r2, self.r2b))

    def test_every_run_id_phrase_is_load_bearing(self):
        for phrase in RUN_ID_PHRASES:
            with self.subTest(phrase=phrase):
                mutated = _forge(self.r2, RUN_ID_ANCHOR, phrase)
                self.assertFalse(run_id_grammar_ok(mutated))

    def test_forged_shard_marker_on_every_pass_is_rejected(self):
        forged = _forge(
            self.r2,
            RUN_ID_ANCHOR,
            "`@s{k}` is present only for a run in a split pass",
            "`@s{k}` is present on every run",
        )
        self.assertFalse(run_id_grammar_ok(forged))

    def test_forged_old_loop_form_is_rejected(self):
        forged = self.r2 + "\n\nPhase R4 uses `{perspective}#loop{N}`.\n"
        self.assertFalse(no_old_loop_form(forged, self.r2b))

    def test_forged_old_loop_form_in_r2b_is_rejected(self):
        forged = self.r2b + "\n\nA re-review run is `{perspective}#loop{N}`.\n"
        self.assertFalse(no_old_loop_form(self.r2, forged))


# ---------------------------------------------------------------------------
# AC-4: the per-shard walk of Phase R2b
# ---------------------------------------------------------------------------

R2B_OPENING = (
    "Applies to every perspective whose R2 primary-reviewer dispatch returned"
)
R2B_TABLE_HEADER = "| `skip_reason` | What it means | Advance to |"
PER_SHARD_ANCHOR = "Split passes."

PER_SHARD_PHRASES = [
    "When Phase R2's pass is split, every rule of this section applies per "
    "shard",
    "the unit of the walk is the shard, not the perspective",
    "That covers the walk, the \"At most 2 fallback dispatches per "
    "perspective\" budget, counted per shard, the Claude fallback and the "
    "last-result replacement",
    "A result of one shard never replaces another shard's",
    "All perspectives and shards falling back at the same hop go in ONE "
    "message",
]


def per_shard_walk_ok(r2b):
    """AC-4: the paragraph sits after the opening sentence and before the
    routing table, and applies every walk rule per shard."""
    paragraph = _paragraph(r2b, PER_SHARD_ANCHOR)
    if not paragraph or not _contains_all(paragraph, PER_SHARD_PHRASES):
        return False
    norm = _norm(r2b)
    opening = norm.find(R2B_OPENING)
    anchor = norm.find(PER_SHARD_ANCHOR)
    table = norm.find(R2B_TABLE_HEADER)
    return -1 < opening < anchor < table


# A representative subset of the Phase R2b phrases pinned by
# tests/test_review_phase_llm_led.py, tests/test_sca_axis_review_phase_r0_r3.py
# and tests/test_threat_model_review_phase.py; those modules hold the full
# pins and run in the same suite.
PINNED_R2B_PHRASES = [
    "Applies to every perspective whose R2 primary-reviewer dispatch returned",
    "**At most 2 fallback dispatches per perspective**",
    "all perspectives falling back at the same hop",
    "go in ONE message",
    "the perspective receives exactly ONE Claude fallback",
    "never concurrently with a harness reviewer",
    "dispatched only after every selected",
    "including any chain-exhaustion Claude fallback",
    "This dispatch does NOT consume the 2-hop budget above",
    "every perspective reaching this state in the same round",
    "is dispatched in ONE message (FR9)",
    "has no further reviewer to try",
    "the round continues and degrades rather than aborting",
    "A reviewer that fails at the **harness** level never reaches this table",
    "same `threat_model_path` value",
    "never consumes one of this section's fallback hops",
    "never triggers the Claude fallback dispatch",
    "never appears in Phase R5's `unreviewed_perspectives` list",
    "not a candidate for this section's retryable-`skip_reason` table",
]

UNREVIEWED_LISTING_CLAUSES = [
    "does the perspective end up in Phase R5's `unreviewed_perspectives`",
    "it ends the round unreviewed for this perspective",
]

KEPT_SKIP_PHRASES = [
    "A kept skip leaves that unit without a completed run",
    "Phase R5 discloses it",
]


def pinned_r2b_phrases_ok(r2b):
    return _contains_all(r2b, PINNED_R2B_PHRASES)


def unreviewed_listing_moved_to_coverage_ok(r2b):
    """The two sentences that named `unreviewed_perspectives` now name the
    unit that ends without a completed run and leave the listing to Phase
    R5's coverage computation."""
    norm = _norm(r2b)
    if any(clause in norm for clause in UNREVIEWED_LISTING_CLAUSES):
        return False
    return (
        "Phase R5's coverage computation discloses it" in norm
        and "ends the round without a completed run" in norm
        and _contains_all(r2b, KEPT_SKIP_PHRASES)
    )


class TestAC4PerShardWalk(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r2b = _Doc.r2b()

    def test_walk_rules_apply_per_shard(self):
        self.assertTrue(per_shard_walk_ok(self.r2b))

    def test_existing_pinned_r2b_phrases_are_still_present(self):
        self.assertTrue(pinned_r2b_phrases_ok(self.r2b))

    def test_listing_sentences_name_the_unit_without_a_completed_run(self):
        self.assertTrue(unreviewed_listing_moved_to_coverage_ok(self.r2b))

    def test_every_per_shard_phrase_is_load_bearing(self):
        for phrase in PER_SHARD_PHRASES:
            with self.subTest(phrase=phrase):
                mutated = _forge(self.r2b, PER_SHARD_ANCHOR, phrase)
                self.assertFalse(per_shard_walk_ok(mutated))

    def test_forged_paragraph_after_the_table_is_rejected(self):
        paragraph = _paragraph(self.r2b, PER_SHARD_ANCHOR)
        self.assertTrue(paragraph)
        moved = self.r2b.replace(paragraph, "", 1) + "\n\n" + paragraph
        self.assertTrue(moved != self.r2b, "mutation did not apply")
        self.assertFalse(per_shard_walk_ok(moved))

    def test_forged_shard_result_replacing_another_is_rejected(self):
        forged = _forge(
            self.r2b,
            PER_SHARD_ANCHOR,
            "A result of one shard never replaces another shard's",
            "The last result of any shard replaces the perspective's",
        )
        self.assertFalse(per_shard_walk_ok(forged))

    def test_forged_removal_of_a_pinned_phrase_is_rejected(self):
        forged = self.r2b.replace("go in ONE message", "go in separate messages")
        self.assertTrue(forged != self.r2b, "mutation did not apply")
        self.assertFalse(pinned_r2b_phrases_ok(forged))

    def test_forged_old_unreviewed_listing_sentence_is_rejected(self):
        forged = self.r2b + (
            "\n\nOnly then does the perspective end up in Phase R5's "
            "`unreviewed_perspectives`.\n"
        )
        self.assertFalse(unreviewed_listing_moved_to_coverage_ok(forged))

    def test_axis_2_exclusion_keeps_pins_and_names_task_dispatched_lists(self):
        norm = _norm(self.r2b)
        self.assertIn(
            "those lists hold only Task-dispatched perspectives, and axis 2 "
            "is not one",
            norm,
        )
        self.assertNotIn(
            "that list only ever holds a perspective whose OWN Phase R2b "
            "Claude fallback",
            norm,
        )


# ---------------------------------------------------------------------------
# AC-5: the fourth routing row and the litellm exception
# ---------------------------------------------------------------------------

ORIGINAL_ROW_LINES = [
    "| `rate_limited` | upstream congestion (Codex rate limit, Vertex 429) "
    "| the next entry in the chain |",
    "| `budget_exhausted` | the harness's own budget is spent (LiteLLM's "
    "monthly virtual-key cap) | the next entry of a **different** harness |",
    "| `harness_unavailable` | the harness could not be reached at all "
    "(proxy down, profile broken, wrapper missing) | the next entry of a "
    "**different** harness |",
]
FOURTH_ROW_LINE = (
    "| `review_data_too_large` | the assembled prompt exceeds the model's "
    "context | the next entry of a **different** harness |"
)
FIFTH_ROW_LINE = (
    "| `contributor_consent_missing` | muse_guard denied the contributor "
    "tier because the repository has no recorded consent | the next entry "
    "in the chain |"
)


def _first_table_lines(section):
    lines = section.splitlines()
    start = next(
        (i for i, line in enumerate(lines) if line.startswith(R2B_TABLE_HEADER)),
        None,
    )
    if start is None:
        return []
    table = []
    for line in lines[start:]:
        if not line.startswith("|"):
            break
        table.append(line)
    return table


def routing_table_ok(r2b):
    table = _first_table_lines(r2b)
    if len(table) != 2 + 5:
        return False
    return table[2:] == ORIGINAL_ROW_LINES + [FOURTH_ROW_LINE, FIFTH_ROW_LINE]


LITELLM_ANCHOR = "classify_results"
LITELLM_ANCHOR_PARAGRAPH = "For each schema-valid, non-skipped result"

LITELLM_PHRASES = [
    "For each schema-valid, non-skipped result of a run whose recorded "
    "harness is `litellm`",
    "the harness the orchestrator recorded when it dispatched the run, never "
    "the result's own `source`",
    "runs the `classify_results` operation of "
    "`em-workflow/scripts/review-coverage.py`",
    "one call per hop",
    "A result it returns as `failed`",
    "is recorded `status: failed`",
    "gets no `skip_reason`",
    "takes the malformed-result path above",
    "one Claude fallback",
    "If the script exits non-zero, every result of that call counts as failed",
]


def litellm_exception_ok(r2b):
    paragraph = _paragraph(r2b, "For each schema-valid, non-skipped result")
    if not paragraph or not _contains_all(paragraph, LITELLM_PHRASES):
        return False
    # The key is the recorded harness: the paragraph never makes the
    # result's own `source` the condition.
    return not re.search(
        r"(whose|if the|when the) (result's )?(own )?`source` "
        r"(is|starts|begins|contains|names)",
        _norm(paragraph),
    )


SCHEMA_VALIDITY_ANCHOR = "is a substantive completed"


class TestAC5RoutingTableAndLitellmException(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r2b = _Doc.r2b()

    def test_table_has_four_rows_and_the_three_old_rows_are_unchanged(self):
        # The name is kept so the records that list it keep resolving. The
        # table now has five data rows: the four earlier rows byte-identical,
        # then `contributor_consent_missing` as the last row.
        self.assertTrue(routing_table_ok(self.r2b))

    def test_litellm_exception_is_stated_with_the_recorded_harness(self):
        self.assertTrue(litellm_exception_ok(self.r2b))

    def test_exception_sits_with_the_schema_validity_paragraph(self):
        norm = _norm(self.r2b)
        self.assertLess(
            norm.index(SCHEMA_VALIDITY_ANCHOR),
            norm.index("For each schema-valid, non-skipped result"),
        )
        self.assertLess(
            norm.index("For each schema-valid, non-skipped result"),
            norm.index("Walk rules:"),
        )

    def test_every_litellm_phrase_is_load_bearing(self):
        for phrase in LITELLM_PHRASES:
            with self.subTest(phrase=phrase):
                mutated = _forge(self.r2b, LITELLM_ANCHOR_PARAGRAPH, phrase)
                self.assertFalse(litellm_exception_ok(mutated))

    def test_forged_three_row_table_is_rejected(self):
        forged = self.r2b.replace(FOURTH_ROW_LINE + "\n", "", 1)
        self.assertTrue(forged != self.r2b, "mutation did not apply")
        self.assertFalse(routing_table_ok(forged))

    def test_forged_four_row_table_without_the_fifth_row_is_rejected(self):
        forged = self.r2b.replace(FIFTH_ROW_LINE + "\n", "", 1)
        self.assertTrue(forged != self.r2b, "mutation did not apply")
        self.assertEqual(len(_first_table_lines(forged)), 2 + 4)
        self.assertFalse(routing_table_ok(forged))

    def test_forged_fifth_row_advancing_to_a_different_harness_is_rejected(
        self,
    ):
        forged = self.r2b.replace(
            FIFTH_ROW_LINE,
            FIFTH_ROW_LINE.replace(
                "the next entry in the chain",
                "the next entry of a **different** harness",
            ),
            1,
        )
        self.assertTrue(forged != self.r2b, "mutation did not apply")
        self.assertFalse(routing_table_ok(forged))

    def test_forged_fifth_row_with_a_changed_meaning_is_rejected(self):
        forged = self.r2b.replace(
            "muse_guard denied the contributor tier because the repository "
            "has no recorded consent",
            "muse_guard denied the contributor tier",
            1,
        )
        self.assertTrue(forged != self.r2b, "mutation did not apply")
        self.assertFalse(routing_table_ok(forged))

    def test_forged_fifth_row_ahead_of_the_fourth_is_rejected(self):
        forged = self.r2b.replace(
            FOURTH_ROW_LINE + "\n" + FIFTH_ROW_LINE,
            FIFTH_ROW_LINE + "\n" + FOURTH_ROW_LINE,
            1,
        )
        self.assertTrue(forged != self.r2b, "mutation did not apply")
        self.assertFalse(routing_table_ok(forged))

    def test_forged_changed_old_row_after_the_fifth_row_is_rejected(self):
        forged = self.r2b.replace(
            "| `harness_unavailable` | the harness could not be reached at all "
            "(proxy down, profile broken, wrapper missing) | the next entry of "
            "a **different** harness |",
            "| `harness_unavailable` | the harness could not be reached | the "
            "next entry of a **different** harness |",
            1,
        )
        self.assertTrue(forged != self.r2b, "mutation did not apply")
        self.assertFalse(routing_table_ok(forged))

    def test_forged_fourth_row_advancing_within_the_harness_is_rejected(self):
        forged = self.r2b.replace(
            FOURTH_ROW_LINE,
            FOURTH_ROW_LINE.replace(
                "the next entry of a **different** harness",
                "the next entry in the chain",
            ),
            1,
        )
        self.assertTrue(forged != self.r2b, "mutation did not apply")
        self.assertFalse(routing_table_ok(forged))

    def test_forged_changed_old_row_is_rejected(self):
        forged = self.r2b.replace(
            "| `rate_limited` | upstream congestion (Codex rate limit, Vertex "
            "429) | the next entry in the chain |",
            "| `rate_limited` | upstream congestion | the next entry in the "
            "chain |",
            1,
        )
        self.assertTrue(forged != self.r2b, "mutation did not apply")
        self.assertFalse(routing_table_ok(forged))

    def test_forged_rule_keyed_on_the_result_source_is_rejected(self):
        forged = _forge(
            self.r2b,
            LITELLM_ANCHOR_PARAGRAPH,
            "the harness the orchestrator recorded when it dispatched the "
            "run, never the result's own `source`",
            "the result's own `source`",
        )
        self.assertFalse(litellm_exception_ok(forged))

    def test_forged_rule_whose_source_starts_with_litellm_is_rejected(self):
        forged = _forge(
            self.r2b,
            LITELLM_ANCHOR_PARAGRAPH,
            "whose recorded harness is `litellm`",
            "whose own `source` starts with `litellm:`",
        )
        self.assertFalse(litellm_exception_ok(forged))

    def test_forged_failed_result_with_a_skip_reason_is_rejected(self):
        forged = _forge(
            self.r2b,
            LITELLM_ANCHOR_PARAGRAPH,
            "gets no `skip_reason`",
            "gets a `harness_unavailable` skip_reason",
        )
        self.assertFalse(litellm_exception_ok(forged))

    def test_table_keeps_exactly_four_retryable_rows_by_count(self):
        # The name is kept so the records that list it keep resolving. The
        # section holds five `| the next entry` occurrences: one per data row,
        # none in the prose outside the table.
        self.assertEqual(self.r2b.count("| the next entry"), 5)
        self.assertEqual(len(_first_table_lines(self.r2b)) - 2, 5)


# ---------------------------------------------------------------------------
# muse-guard-deny-recovery task0003: the note on the `contributor_consent_missing`
# row (FR3) and the precedence over the harness-level path (FR4)
# ---------------------------------------------------------------------------

CONSENT_NOTE_ANCHOR = "consent is a property of the contributor tier"
WALK_RULES_MARKER = "Walk rules:"

CONSENT_NOTE_PHRASES = [
    "consent is a property of the contributor tier, not of the harness",
    "so the walk may advance within the same harness",
    "resumes from the entry after the recorded chain index",
    "never re-dispatches the same entry as plain `muse-spark`",
    "Phase R0's `contributor_consented` is not re-judged",
    "the chain is not edited",
    'The hop counts against the "At most 2 fallback dispatches per '
    'perspective" budget',
    "an exhausted chain takes the existing Claude fallback",
]


def contributor_consent_note_ok(r2b):
    """The note sits in prose after the routing table (after its last row,
    before the walk rules), outside the table, and states every point."""
    paragraph = _paragraph(r2b, CONSENT_NOTE_ANCHOR)
    if not paragraph or paragraph.lstrip().startswith("|"):
        return False
    if not _contains_all(paragraph, CONSENT_NOTE_PHRASES):
        return False
    norm = _norm(r2b)
    if norm.count(CONSENT_NOTE_ANCHOR) != 1:
        return False
    last_row = norm.find(FIFTH_ROW_LINE)
    note = norm.find(CONSENT_NOTE_ANCHOR)
    walk_rules = norm.find(WALK_RULES_MARKER)
    return -1 < last_row < note < walk_rules


HARNESS_LEVEL_ANCHOR = (
    "A reviewer that fails at the **harness** level never reaches this table"
)
# The harness-level paragraph, whitespace-normalized, byte-for-byte as it was
# before the precedence statement was added after it.
HARNESS_LEVEL_PARAGRAPH = (
    "A reviewer that fails at the **harness** level never reaches this table: "
    "the Task call itself comes back `is_error`, a permission denial lands in "
    "its output, or the Codex wrapper script never executed, so there is no "
    "`skip_reason` to route on. That is not a chain-walk case, but the "
    "perspective still has no completed run and no further chain entry to "
    "try, so — separately from diagnosing the harness failure — it receives "
    "the same ONE Claude fallback dispatch as the malformed-result and "
    "chain-exhaustion cases above, issued after this determination and never "
    "concurrently with a harness reviewer. Diagnose the harness-level cause "
    "per `references/workflow-failure-recovery.md` (dispatch `workflow-doctor` "
    "over the failed agents' JSONL logs) and include the diagnosis in the R6 "
    "report rather than silently recording the perspective as missing."
)

PRECEDENCE_PHRASES = [
    "a valid `skipped: true` object whose `skip_reason` is "
    "`contributor_consent_missing`",
    "is routed by the table above even when the cause was a hook deny",
    "no valid skip object comes back",
    "the Task call is `is_error`",
    "a permission denial lands in the output without a skip object",
    "the wrapper script never ran",
    "the harness-level path above applies",
    "the one Claude fallback and the `workflow-doctor` diagnosis",
]


def _blocks(text):
    return re.split(r"\n\s*\n", text)


def harness_level_paragraph_unchanged_ok(r2b):
    blocks = _blocks(r2b)
    holders = [b for b in blocks if HARNESS_LEVEL_ANCHOR in _norm(b)]
    return len(holders) == 1 and _norm(holders[0]) == HARNESS_LEVEL_PARAGRAPH


def precedence_statement_ok(r2b):
    """The precedence statement is the paragraph immediately after the
    harness-level paragraph, and states both halves."""
    blocks = _blocks(r2b)
    holders = [
        i for i, b in enumerate(blocks) if HARNESS_LEVEL_ANCHOR in _norm(b)
    ]
    if len(holders) != 1 or holders[0] + 1 >= len(blocks):
        return False
    following = blocks[holders[0] + 1]
    if not following.strip() or following.lstrip().startswith("|"):
        return False
    return _contains_all(following, PRECEDENCE_PHRASES)


class TestContributorConsentMissingNoteAndPrecedence(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r2b = _Doc.r2b()

    # -- non-vacuity: the matchers pass on the real text ------------------

    def test_note_matcher_passes_on_the_real_text(self):
        self.assertTrue(_paragraph(self.r2b, CONSENT_NOTE_ANCHOR))
        self.assertTrue(contributor_consent_note_ok(self.r2b))

    def test_precedence_matcher_passes_on_the_real_text(self):
        self.assertTrue(harness_level_paragraph_unchanged_ok(self.r2b))
        self.assertTrue(precedence_statement_ok(self.r2b))

    def test_harness_level_sentence_is_still_pinned_verbatim(self):
        self.assertIn(HARNESS_LEVEL_ANCHOR, _norm(self.r2b))

    # -- the note (FR3) ----------------------------------------------------

    def test_every_note_phrase_is_load_bearing(self):
        for phrase in CONSENT_NOTE_PHRASES:
            with self.subTest(phrase=phrase):
                mutated = _forge(self.r2b, CONSENT_NOTE_ANCHOR, phrase)
                self.assertFalse(contributor_consent_note_ok(mutated))

    def test_forged_text_without_the_note_is_rejected(self):
        paragraph = _paragraph(self.r2b, CONSENT_NOTE_ANCHOR)
        forged = self.r2b.replace(paragraph, "", 1)
        self.assertTrue(forged != self.r2b, "mutation did not apply")
        self.assertFalse(contributor_consent_note_ok(forged))

    def test_forged_note_that_re_dispatches_as_plain_muse_spark_is_rejected(
        self,
    ):
        forged = _forge(
            self.r2b,
            CONSENT_NOTE_ANCHOR,
            "never re-dispatches the same entry as plain `muse-spark`",
            "re-dispatches the same entry as plain `muse-spark`",
        )
        self.assertFalse(contributor_consent_note_ok(forged))

    def test_forged_note_that_re_judges_consent_is_rejected(self):
        forged = _forge(
            self.r2b,
            CONSENT_NOTE_ANCHOR,
            "Phase R0's `contributor_consented` is not re-judged",
            "Phase R0's `contributor_consented` is judged again",
        )
        self.assertFalse(contributor_consent_note_ok(forged))

    def test_forged_note_moved_before_the_routing_table_is_rejected(self):
        paragraph = _paragraph(self.r2b, CONSENT_NOTE_ANCHOR)
        moved = self.r2b.replace(paragraph, "", 1).replace(
            R2B_TABLE_HEADER, paragraph.strip() + "\n\n" + R2B_TABLE_HEADER, 1
        )
        self.assertTrue(moved != self.r2b, "mutation did not apply")
        self.assertFalse(contributor_consent_note_ok(moved))

    def test_forged_note_moved_after_the_walk_rules_is_rejected(self):
        paragraph = _paragraph(self.r2b, CONSENT_NOTE_ANCHOR)
        moved = self.r2b.replace(paragraph, "", 1) + "\n\n" + paragraph
        self.assertTrue(moved != self.r2b, "mutation did not apply")
        self.assertFalse(contributor_consent_note_ok(moved))

    def test_forged_note_written_as_a_table_row_is_rejected(self):
        paragraph = _paragraph(self.r2b, CONSENT_NOTE_ANCHOR)
        forged = self.r2b.replace(
            paragraph, "| " + _norm(paragraph) + " |\n", 1
        )
        self.assertTrue(forged != self.r2b, "mutation did not apply")
        self.assertFalse(contributor_consent_note_ok(forged))

    def test_note_adds_no_next_entry_cell_outside_the_table(self):
        paragraph = _paragraph(self.r2b, CONSENT_NOTE_ANCHOR)
        self.assertNotIn("| the next entry", _norm(paragraph))

    # -- the precedence over the harness-level path (FR4) -----------------

    def test_every_precedence_phrase_is_load_bearing(self):
        following = self._following_paragraph(self.r2b)
        for phrase in PRECEDENCE_PHRASES:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, _norm(following))
                mutated = self.r2b.replace(
                    following, _norm(following).replace(phrase, "", 1), 1
                )
                self.assertTrue(mutated != self.r2b, "mutation did not apply")
                self.assertFalse(precedence_statement_ok(mutated))

    def test_forged_text_without_the_precedence_statement_is_rejected(self):
        following = self._following_paragraph(self.r2b)
        forged = self.r2b.replace(following, "", 1)
        self.assertTrue(forged != self.r2b, "mutation did not apply")
        self.assertFalse(precedence_statement_ok(forged))

    def test_forged_precedence_statement_before_the_harness_paragraph_is_rejected(
        self,
    ):
        following = self._following_paragraph(self.r2b)
        harness = _paragraph(self.r2b, HARNESS_LEVEL_ANCHOR)
        swapped = self.r2b.replace(
            harness.strip() + "\n\n" + following.strip(),
            following.strip() + "\n\n" + harness.strip(),
            1,
        )
        self.assertTrue(swapped != self.r2b, "mutation did not apply")
        self.assertFalse(precedence_statement_ok(swapped))

    def test_forged_precedence_statement_not_adjacent_is_rejected(self):
        following = self._following_paragraph(self.r2b)
        forged = self.r2b.replace(
            following, "An unrelated sentence.\n\n" + following, 1
        )
        self.assertTrue(forged != self.r2b, "mutation did not apply")
        self.assertFalse(precedence_statement_ok(forged))

    def test_forged_statement_that_drops_the_harness_level_fallback_is_rejected(
        self,
    ):
        following = self._following_paragraph(self.r2b)
        forged = self.r2b.replace(
            following,
            _norm(following).replace(
                "the one Claude fallback and the `workflow-doctor` diagnosis",
                "nothing further",
                1,
            ),
            1,
        )
        self.assertTrue(forged != self.r2b, "mutation did not apply")
        self.assertFalse(precedence_statement_ok(forged))

    def test_forged_harness_level_paragraph_with_a_changed_byte_is_rejected(
        self,
    ):
        forged = _forge(
            self.r2b,
            HARNESS_LEVEL_ANCHOR,
            "a permission denial lands in its output",
            "a permission denial lands in its log",
        )
        self.assertFalse(harness_level_paragraph_unchanged_ok(forged))

    def test_forged_harness_level_sentence_rewritten_is_rejected(self):
        forged = self.r2b.replace(
            HARNESS_LEVEL_ANCHOR,
            "A reviewer that fails at the harness level reaches this table",
            1,
        )
        self.assertTrue(forged != self.r2b, "mutation did not apply")
        self.assertFalse(harness_level_paragraph_unchanged_ok(forged))
        self.assertFalse(precedence_statement_ok(forged))

    @staticmethod
    def _following_paragraph(r2b):
        blocks = _blocks(r2b)
        index = next(
            i
            for i, b in enumerate(blocks)
            if HARNESS_LEVEL_ANCHOR in _norm(b)
        )
        return blocks[index + 1]


# ---------------------------------------------------------------------------
# AC-6: the spec order and the rescue runs
# ---------------------------------------------------------------------------

SPEC_ANCHOR = "spec order and rescue runs."

SPEC_PHRASES = [
    "`spec` is never split",
    "runs its chain on the full diff: the Phase R2 front entry, this "
    "section's walk, then the Claude fallback",
    "Rescue runs happen only when that whole path, Claude fallback included, "
    "ends with no completed run and the pass is split",
    "An unsplit pass never has rescue runs",
    "A rescue run is a `spec` retry, not a primary dispatch",
    "one per dispatched shard, at most `shard_cap`",
    "run_id `spec@s{k}#...`",
    "goes through the per-shard walk",
    "Phase R3a waits until every rescue walk has finished",
]


def spec_order_ok(r2b):
    paragraph = _paragraph(r2b, SPEC_ANCHOR)
    return bool(paragraph) and _contains_all(paragraph, SPEC_PHRASES)


class TestAC6SpecOrderAndRescue(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r2b = _Doc.r2b()

    def test_spec_order_and_rescue_runs_are_stated(self):
        self.assertTrue(spec_order_ok(self.r2b))

    def test_every_spec_phrase_is_load_bearing(self):
        for phrase in SPEC_PHRASES:
            with self.subTest(phrase=phrase):
                mutated = _forge(self.r2b, SPEC_ANCHOR, phrase)
                self.assertFalse(spec_order_ok(mutated))

    def test_forged_rescue_in_an_unsplit_pass_is_rejected(self):
        forged = _forge(
            self.r2b,
            SPEC_ANCHOR,
            "An unsplit pass never has rescue runs",
            "An unsplit pass may also have rescue runs",
        )
        self.assertFalse(spec_order_ok(forged))

    def test_forged_rescue_before_the_claude_fallback_is_rejected(self):
        forged = _forge(
            self.r2b,
            SPEC_ANCHOR,
            "Rescue runs happen only when that whole path, Claude fallback "
            "included, ends with no completed run and the pass is split",
            "Rescue runs happen as soon as the front entry returns no "
            "completed run and the pass is split",
        )
        self.assertFalse(spec_order_ok(forged))

    def test_forged_rescue_beyond_the_cap_is_rejected(self):
        forged = _forge(
            self.r2b,
            SPEC_ANCHOR,
            "one per dispatched shard, at most `shard_cap`",
            "one per shard",
        )
        self.assertFalse(spec_order_ok(forged))

    def test_r2_dispatches_spec_once_on_the_full_diff(self):
        self.assertIn(
            "`spec` is dispatched once, on the full diff, in both cases",
            _norm(_Doc.r2()),
        )

    def test_rescue_runs_are_not_counted_as_primary_dispatches(self):
        self.assertIn(
            "not a primary dispatch", _norm(_paragraph(self.r2b, SPEC_ANCHOR))
        )


# ---------------------------------------------------------------------------
# AC-7: README, unchanged interfaces, module hygiene
# ---------------------------------------------------------------------------

README_PRIMARY_ANCHOR = "選択された各観点には、その観点の `primary_chain`"
README_CHAIN_HEADING = "### primary-reviewer チェーン表"
README_HOP_ANCHOR = "R2b はスキップ理由が retryable なときだけチェーンを進める"

README_PRIMARY_PINS = [
    "1 体だけ起動",
    "チェーンの全エントリが利用不可",
    "Claude 汎用レビュアーにフォールバック",
]
README_PRIMARY_ADDITION = (
    "レビュー入力が大きい（200,000 文字超）ときは、入力をファイル単位の"
    "シャードに分割し、シャードごとに専用のレビュアーを起動する"
)
README_HOP_PHRASES = [
    "`budget_exhausted` / `harness_unavailable` / `review_data_too_large` は"
    "**別ハーネス**の次エントリへ飛ぶ",
    "ホップ数はシャードごとに数える",
]


def readme_primary_paragraph_ok(readme):
    paragraph = _paragraph(readme, README_PRIMARY_ANCHOR)
    if not paragraph:
        return False
    if not all(pin in paragraph for pin in README_PRIMARY_PINS):
        return False
    if README_PRIMARY_ADDITION not in paragraph:
        return False
    # The chain table comes right after; "R2b" is not added before it.
    before_table = readme[: readme.index(README_CHAIN_HEADING)]
    return "R2b" not in before_table


def readme_hop_paragraph_ok(readme):
    paragraph = _paragraph(readme, README_HOP_ANCHOR)
    return bool(paragraph) and all(p in paragraph for p in README_HOP_PHRASES)


# muse-guard-deny-recovery task0003 (FR8): the hop paragraph lists
# `contributor_consent_missing` in the group that advances to the next entry
# (the `rate_limited` group), not in the different-harness group.
README_NEXT_ENTRY_GROUP = (
    "`rate_limited` / `contributor_consent_missing` は次のエントリへ、"
)


def readme_consent_in_next_entry_group_ok(readme):
    paragraph = _paragraph(readme, README_HOP_ANCHOR)
    if not paragraph or README_NEXT_ENTRY_GROUP not in paragraph:
        return False
    other_group = paragraph[paragraph.index("`budget_exhausted`"):]
    return "`contributor_consent_missing`" not in other_group


class TestAC7ReadmeAndUnchangedInterfaces(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.readme = _read(README_PATH)

    def test_primary_reviewer_paragraph_states_per_shard_dispatch(self):
        self.assertTrue(readme_primary_paragraph_ok(self.readme))

    def test_hop_paragraph_names_review_data_too_large_and_per_shard_hops(self):
        self.assertTrue(readme_hop_paragraph_ok(self.readme))

    def test_forged_readme_without_the_shard_sentence_is_rejected(self):
        forged = self.readme.replace(README_PRIMARY_ADDITION, "")
        self.assertTrue(forged != self.readme, "mutation did not apply")
        self.assertFalse(readme_primary_paragraph_ok(forged))

    def test_forged_readme_losing_a_pinned_phrase_is_rejected(self):
        forged = self.readme.replace("チェーンの全エントリが利用不可", "全滅")
        self.assertTrue(forged != self.readme, "mutation did not apply")
        self.assertFalse(readme_primary_paragraph_ok(forged))

    def test_forged_readme_with_r2b_before_the_chain_table_is_rejected(self):
        forged = self.readme.replace(
            README_PRIMARY_ADDITION, "R2b " + README_PRIMARY_ADDITION, 1
        )
        self.assertTrue(forged != self.readme, "mutation did not apply")
        self.assertFalse(readme_primary_paragraph_ok(forged))

    def test_forged_readme_without_the_new_reason_is_rejected(self):
        forged = self.readme.replace(
            " / `review_data_too_large`", "", 1
        )
        self.assertTrue(forged != self.readme, "mutation did not apply")
        self.assertFalse(readme_hop_paragraph_ok(forged))

    def test_hop_paragraph_puts_the_consent_value_in_the_next_entry_group(
        self,
    ):
        self.assertTrue(readme_consent_in_next_entry_group_ok(self.readme))
        # Both pinned phrases stay verbatim next to it.
        self.assertTrue(readme_hop_paragraph_ok(self.readme))

    def test_forged_readme_without_the_consent_value_is_rejected(self):
        forged = self.readme.replace(" / `contributor_consent_missing`", "", 1)
        self.assertTrue(forged != self.readme, "mutation did not apply")
        self.assertFalse(readme_consent_in_next_entry_group_ok(forged))

    def test_forged_readme_with_the_consent_value_in_the_other_group_is_rejected(
        self,
    ):
        forged = self.readme.replace(
            " / `contributor_consent_missing` は次のエントリへ、"
            "`budget_exhausted` / `harness_unavailable` / "
            "`review_data_too_large` は",
            " は次のエントリへ、`budget_exhausted` / `harness_unavailable` / "
            "`review_data_too_large` / `contributor_consent_missing` は",
            1,
        )
        self.assertTrue(forged != self.readme, "mutation did not apply")
        self.assertFalse(readme_consent_in_next_entry_group_ok(forged))

    def test_readme_has_one_slash_listing_ending_in_review_data_too_large(
        self,
    ):
        # An existing forged-text test removes the first such occurrence and
        # expects the hop paragraph to lose it, so none may precede it.
        self.assertEqual(self.readme.count(" / `review_data_too_large`"), 1)
        self.assertIn(
            " / `review_data_too_large`",
            _paragraph(self.readme, README_HOP_ANCHOR),
        )

    def test_forged_readme_without_per_shard_hops_is_rejected(self):
        forged = self.readme.replace("ホップ数はシャードごとに数える", "", 1)
        self.assertTrue(forged != self.readme, "mutation did not apply")
        self.assertFalse(readme_hop_paragraph_ok(forged))

    def test_output_schema_keeps_its_top_level_shape(self):
        schema = json.loads(_read(SCHEMA_PATH))
        self.assertIn("properties", schema)
        self.assertNotIn("shard", json.dumps(schema).lower())

    def test_vertex_reviewer_block_is_still_otherwise_identical(self):
        # The vertex reviewer is dispatched with the same input block plus
        # `model`; sharding adds nothing it would have to understand.
        norm = _norm(_Doc.r2())
        self.assertIn("the block is otherwise identical", norm)
        self.assertIn(
            "that reviewer fetches diff/file data itself exactly like the "
            "codex reviewer",
            norm,
        )


class TestOwnModuleStdlibOnly(unittest.TestCase):
    def test_only_standard_library_imports(self):
        import sys

        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        modules = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                modules.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0:
                modules.add((node.module or "").split(".")[0])
        non_stdlib = sorted(m for m in modules if m not in sys.stdlib_module_names)
        self.assertEqual(non_stdlib, [])


if __name__ == "__main__":
    unittest.main()
