"""Tests for task0003 (spec-change-rework-reentry): implement Step I.0 admits
the SPEC-change re-entry, so a feature that went through rework's SPEC-change
transition (`em-workflow/references/rework-task-synthesis.md` Section 10)
reaches review without the protocol-error ABORT, and every other non-fresh
entry with nothing to do still ABORTs immediately. This module is the
recurrence test for FR7 (b) and (c) and for the TM-1 to TM-3 statements of
the threat model.

Covers task0003 Acceptance Criteria
(feature-docs/spec-change-rework-reentry/tasks/task0003.md):

- AC-1: Step I.0 item 5 names the SPEC-change re-entry among four entry
  routes, defines it by citing Section 10 of the rework synthesis reference
  and the create-spec -> create-plan re-run, and states that on this route
  an entry with no `pending` task and no task whose reconciled state is
  `failed` does not ABORT.
- AC-2 (TM-2, TM-3): the five identification conditions are all required,
  read from committed facts only, with the `spec_change` record's fields
  cited to `references/phase-state.md`; neither session memory nor worker
  natural-language output is used; a resume from `in_progress` written by
  the same re-entry's Step I.1 is admitted.
- AC-3: with no `pending` task the route runs Step I.1, skips Step I.2
  (no implementer, no turn ended on an empty queue) and completes through
  Step I.3 in the same turn; one or more `pending` tasks registered by the
  re-plan proceed through Step I.2 as usual.
- AC-4 (TM-2): the immediate ABORT remains for a non-fresh entry that is not
  a SPEC-change re-entry; an entry failing any identification condition
  falls to it; "with nothing to launch" is kept and the Step A.6
  restoration paragraph still follows it.
- AC-5 (TM-1): each commit value read from `workflow.yaml` or the
  `spec_change` record is checked against the full hexadecimal commit
  object-id shape before it appears in any git command; a non-matching
  value means the route is not identified and is never sanitised.
- AC-6: the fresh-first-pass sentence, the rework re-entry paragraph (byte
  for byte), the auto-resume paragraph with its citation and the Step A.6
  restoration paragraph are unchanged; the document holds no Notion URL and
  no absolute path under the home directory; Step I.0 gains no fenced
  command block.
- AC-7: every matcher is backed by a negative proof, and the pre-change
  item 5, held below as a verbatim constant, is rejected by the AC-1 and
  AC-3 matchers (and by the others), so this module demonstrably fails
  against the pre-change wording (SPEC AC7).

Follows this suite's established convention: standard library only, the
document read from the repository root computed from this module's own path,
exact-wording markers held as module constants, matching done after
whitespace normalisation except where a raw pin is intended (the rework
route's condition sentence and the paragraphs AC-6 keeps unchanged are
compared as raw text, line breaks included).
"""

import os
import re
import unittest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
IMPLEMENT_PHASE_PATH = os.path.join(
    REPO_ROOT, "em-workflow", "references", "implement-phase.md"
)

STEP_I0_HEADING = "## Step I.0: Preconditions"
STEP_I1_HEADING = "## Step I.1: Confirm the integration worktree"


# ---------------------------------------------------------------------
# The pre-change item 5 (verbatim) and the parts AC-6 keeps unchanged
# ---------------------------------------------------------------------

FRESH_FIRST_PASS_SENTENCE = (
    "A fresh first pass carries no further condition here."
)

REWORK_PARAGRAPH_RAW = (
    "   Rework re-entry: when this phase is entered because\n"
    "   review or verify sent `implement` back to `pending` (rework, not a fresh\n"
    "   first pass), require at least one task in `tasks` whose\n"
    "   `status == pending` — this is Invariant 1 of\n"
    "   `references/rework-task-synthesis.md`: the synthesis step that flips\n"
    "   `implement` to `pending` never does so without registering a pending\n"
    "   rework task alongside it.\n"
)

AUTO_RESUME_PARAGRAPH_RAW = (
    "   Batch infra auto-resume re-entry: when instead this phase is entered via\n"
    "   the auto-resume route above, require at least one task whose Step\n"
    "   I.2.b step 1's reconciled state is `failed` — that is what the resumed\n"
    "   phase has work to do about; no `pending` task is required on this\n"
    "   route, since the auto-resume's write set registers no task.\n"
)

STEP_A6_PARAGRAPH_RAW = (
    "   The failed-entry restoration of `skills/develop/SKILL.md` Step A.6\n"
    "   (`## Step A.6: failed からの入口`) sets `implement` and the target task's\n"
    "   `status` back to `pending`. That restoration meets the rework re-entry's\n"
    "   condition above — at least one task whose `status == pending` — and is\n"
    "   treated as that route here, not as a fresh first pass.\n"
)

AUTO_RESUME_CITATION = (
    "(`skills/develop/SKILL.md`, the auto-resume block; its own precondition "
    "and write set are stated there, not restated here)"
)

PRE_CHANGE_ITEM_5 = (
    "5. **Re-entry precondition**: Step I.0 recognises three entry routes into\n"
    "   `implement: pending` — a fresh first pass, a rework re-entry, and the\n"
    "   develop skill's batch infra auto-resume (`skills/develop/SKILL.md`, the\n"
    "   auto-resume block; its own precondition and write set are stated there,\n"
    "   not restated here). A fresh first pass carries no further condition\n"
    "   here.\n"
    "\n"
    + REWORK_PARAGRAPH_RAW
    + "\n"
    + AUTO_RESUME_PARAGRAPH_RAW
    + "\n"
    "   A non-fresh entry satisfying neither condition — every task `merged`\n"
    "   (or otherwise none `pending`), and no task whose reconciled state is\n"
    "   `failed` — is therefore a protocol error, not a fresh idle state to\n"
    "   wait out: ABORT the phase immediately with a clear report naming the\n"
    "   offending workflow.yaml state, rather than looping through Step I.2\n"
    "   with nothing to launch.\n"
    "\n"
    + STEP_A6_PARAGRAPH_RAW
)

# Markers used to order the paragraphs of the new item 5.
SPEC_CHANGE_DEFINITION_MARKER = (
    "SPEC-change re-entry: the entry into `implement` after the SPEC-change "
    "transition"
)
ABORT_MARKER = "A non-fresh entry that is not a SPEC-change re-entry"
STEP_A6_MARKER = "The failed-entry restoration of `skills/develop/SKILL.md` Step A.6"
OUTCOME_MARKER = (
    "On this route an entry with no `pending` task and no task whose "
    "reconciled state is `failed`"
)


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------


def _read(path):
    if not os.path.isfile(path):
        raise AssertionError(f"expected file to exist: {path}")
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _normalize(text):
    return re.sub(r"\s+", " ", text).strip()


def _step_i0(text):
    start = text.index(STEP_I0_HEADING)
    end = text.index(STEP_I1_HEADING, start)
    return text[start:end]


def _quiet_in(test, needle, haystack):
    """assertTrue(needle in haystack) with a short failure message (the
    haystack is a whole document section and is never dumped)."""
    test.assertTrue(needle in haystack, f"missing text: {needle[:80]!r}")


def _index_of(label, norm, marker):
    needle = _normalize(marker)
    if needle not in norm:
        raise AssertionError(f"{label}: missing marker: {marker!r}")
    return norm.index(needle)


def _require(label, norm, phrases):
    """Raise AssertionError naming the first phrase absent from the
    whitespace-normalised text `norm`."""
    for phrase in phrases:
        if _normalize(phrase) not in norm:
            raise AssertionError(f"{label}: missing statement: {phrase!r}")


def _require_order(label, norm, markers):
    """Raise AssertionError unless every marker is present and the markers
    appear in the given order."""
    positions = [_index_of(label, norm, marker) for marker in markers]
    if positions != sorted(positions) or len(set(positions)) != len(positions):
        raise AssertionError(f"{label}: markers out of order: {markers!r}")


# ---------------------------------------------------------------------
# AC-1: four entry routes, definition, no ABORT on the new route
# ---------------------------------------------------------------------


def check_ac1_names_route_and_no_abort(step_i0):
    norm = _normalize(step_i0)
    _require(
        "AC-1",
        norm,
        [
            "Step I.0 recognises four entry routes into `implement: pending` — "
            "a fresh first pass, a rework re-entry, the SPEC-change re-entry, "
            "and the develop skill's batch infra auto-resume",
            SPEC_CHANGE_DEFINITION_MARKER,
            "(`references/rework-task-synthesis.md` Section 10, the "
            "`**When rework needs a SPEC.md change**` block, cited here, not "
            "restated)",
            "and the create-spec → create-plan re-run that follows it",
            OUTCOME_MARKER + " is not a protocol error and does not ABORT",
        ],
    )


# ---------------------------------------------------------------------
# AC-2 (TM-2, TM-3): identification from committed facts only
# ---------------------------------------------------------------------


def check_ac2_identification(step_i0):
    norm = _normalize(step_i0)
    _require(
        "AC-2",
        norm,
        [
            # all five conditions are required, from committed facts only
            "only when ALL of the following hold",
            "each read from committed facts only",
            "`workflow.yaml`",
            "the `spec_change` record of `phase-state/rework.yaml`",
            "the integration branch's commit history",
            "no timestamp is compared",
            # 1
            "`create-spec` and `create-plan` are `completed`, and `implement` "
            "holds a `base_commit` and a prior `completed_at_commit`",
            # 2, with the field meanings cited and not restated
            "a `spec_change` record with `consumed: true` and "
            "`replan_authorized: false`",
            "defined by `references/phase-state.md`, cited here, not restated",
            # 3
            "The prior `completed_at_commit` is a proper ancestor of the "
            "record's `recorded_at_commit`, and `recorded_at_commit` is an "
            "ancestor of the current integration tip",
            # 4
            "The commit history shows that the SPEC-change transition that "
            "wrote this record returned `implement` to `pending`",
            "the tier-upgrade procedure writes the same record without doing "
            "so, so the flags alone do not suffice",
            # 5
            "`tasks` is non-empty and every task is `merged`",
            # TM-3: the inputs the identification never uses
            "The identification uses no session memory and no worker "
            "natural-language output",
            # resume from the same re-entry's own Step I.1
            "A resume of the same re-entry",
            "`implement` reads `in_progress`, written by that re-entry's own "
            "Step I.1",
            "is admitted on the same facts",
        ],
    )


# ---------------------------------------------------------------------
# AC-3: zero-task path through Step I.3, new tasks through Step I.2
# ---------------------------------------------------------------------


def check_ac3_zero_task_path(step_i0):
    norm = _normalize(step_i0)
    _require(
        "AC-3",
        norm,
        [
            "With no `pending` task, Step I.1 runs as usual (the gitignore "
            "guard, `base_commit` preserved, the `implement` → `in_progress` "
            "commit)",
            "Step I.2 is skipped",
            "no implementer is launched",
            "the turn does not end waiting on an empty queue",
            "the phase proceeds in the same turn to Step I.3",
            "capture → refresh → write → commit sets `completed_at_commit` "
            "even though no task ran",
            "keeps the same `spec_change` record from grounding a later "
            "re-entry",
            "When the re-plan registered one or more new `pending` tasks, the "
            "entry meets the rework re-entry's condition above and proceeds "
            "through Step I.2 as usual",
        ],
    )


# ---------------------------------------------------------------------
# AC-4 (TM-2): the immediate ABORT stays for every other non-fresh entry
# ---------------------------------------------------------------------


def check_ac4_abort_remains(step_i0):
    norm = _normalize(step_i0)
    _require(
        "AC-4",
        norm,
        [
            ABORT_MARKER + " and satisfies neither the rework nor the "
            "auto-resume condition",
            "every task `merged` (or otherwise none `pending`), and no task "
            "whose reconciled state is `failed`",
            "is therefore a protocol error",
            "ABORT the phase immediately",
            "with nothing to launch",
            "An entry for which any identification condition above does not "
            "hold is not a SPEC-change re-entry and falls here",
        ],
    )
    _require_order(
        "AC-4 order",
        norm,
        [
            SPEC_CHANGE_DEFINITION_MARKER,
            OUTCOME_MARKER,
            ABORT_MARKER,
            "with nothing to launch",
            STEP_A6_MARKER,
        ],
    )


# ---------------------------------------------------------------------
# AC-5 (TM-1): commit-value shape check before any git command
# ---------------------------------------------------------------------


def check_ac5_commit_value_shape_check(step_i0):
    norm = _normalize(step_i0)
    _require(
        "AC-5",
        norm,
        [
            "before a commit value read from `workflow.yaml` or from the "
            "`spec_change` record appears in any git command, it is checked "
            "against the shape of a full hexadecimal commit object id",
            "A value that does not match means the entry is not a SPEC-change "
            "re-entry, and the value is never sanitised",
        ],
    )


# ---------------------------------------------------------------------
# AC-6: what stays unchanged
# ---------------------------------------------------------------------


def check_ac6_unchanged_parts(step_i0):
    norm = _normalize(step_i0)
    _require(
        "AC-6",
        norm,
        [FRESH_FIRST_PASS_SENTENCE, AUTO_RESUME_CITATION],
    )
    for label, raw in (
        ("rework re-entry paragraph", REWORK_PARAGRAPH_RAW),
        ("auto-resume paragraph", AUTO_RESUME_PARAGRAPH_RAW),
        ("Step A.6 restoration paragraph", STEP_A6_PARAGRAPH_RAW),
    ):
        if raw not in step_i0:
            raise AssertionError(f"AC-6: {label} is not byte-identical")


def check_ac6_no_fenced_block_added(step_i0):
    if "```" in step_i0:
        raise AssertionError("AC-6: Step I.0 gained a fenced block")


# ---------------------------------------------------------------------
# Live document
# ---------------------------------------------------------------------


class ImplementPhaseCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = _read(IMPLEMENT_PHASE_PATH)
        cls.step_i0 = _step_i0(cls.text)


class TestAC1NamesTheRoute(ImplementPhaseCase):
    def test_step_i0_names_four_routes_and_does_not_abort_on_the_new_one(self):
        check_ac1_names_route_and_no_abort(self.step_i0)


class TestAC2Identification(ImplementPhaseCase):
    def test_five_conditions_committed_facts_inputs_and_resume_are_stated(self):
        check_ac2_identification(self.step_i0)

    def test_section_10_is_cited_for_the_definition_not_restated(self):
        norm = _normalize(self.step_i0)
        _quiet_in(
            self, "`references/rework-task-synthesis.md` Section 10", norm
        )
        # the five transition steps are Section 10's; Step I.0 names none.
        self.assertFalse("`create-spec` step → `needs_update`" in norm)
        self.assertFalse(
            "`workflow[implement].base_commit` is preserved" in norm
        )

    def test_record_fields_are_cited_to_phase_state_not_defined(self):
        norm = _normalize(self.step_i0)
        # the record's other fields are never listed in Step I.0.
        for field in ("origin_kind", "origin_id", "reason:"):
            with self.subTest(field=field):
                self.assertFalse(field in norm, f"restated field: {field}")


class TestAC3ZeroTaskPath(ImplementPhaseCase):
    def test_zero_task_route_runs_i1_skips_i2_and_completes_through_i3(self):
        check_ac3_zero_task_path(self.step_i0)


class TestAC4AbortRemains(ImplementPhaseCase):
    def test_abort_remains_for_every_other_non_fresh_entry_in_order(self):
        check_ac4_abort_remains(self.step_i0)


class TestAC5CommitValueShapeCheck(ImplementPhaseCase):
    def test_commit_values_are_shape_checked_before_any_git_command(self):
        check_ac5_commit_value_shape_check(self.step_i0)


class TestAC6UnchangedParts(ImplementPhaseCase):
    def test_unchanged_sentence_and_paragraphs_are_intact(self):
        check_ac6_unchanged_parts(self.step_i0)

    def test_no_fenced_command_block_is_added_to_step_i0(self):
        check_ac6_no_fenced_block_added(self.step_i0)

    def test_document_holds_no_notion_url_and_no_home_path(self):
        for needle in ("notion.so", "notion.site", "notion.com", "/home/"):
            with self.subTest(needle=needle):
                self.assertFalse(needle in self.text, f"found: {needle}")

    def test_pre_change_constant_is_what_the_kept_parts_are_cut_from(self):
        # Consistency of the verbatim constant with the kept parts: each is
        # a substring of the pre-change item 5.
        for raw in (
            REWORK_PARAGRAPH_RAW,
            AUTO_RESUME_PARAGRAPH_RAW,
            STEP_A6_PARAGRAPH_RAW,
        ):
            self.assertIn(raw, PRE_CHANGE_ITEM_5)
        self.assertIn(
            FRESH_FIRST_PASS_SENTENCE, _normalize(PRE_CHANGE_ITEM_5)
        )
        self.assertIn(AUTO_RESUME_CITATION, _normalize(PRE_CHANGE_ITEM_5))


# ---------------------------------------------------------------------
# AC-7: negative proofs
# ---------------------------------------------------------------------


class TestAC7PreChangeItem5IsRejected(unittest.TestCase):
    """FR7 (b), SPEC AC7: the pre-change wording fails the new matchers."""

    def _must_fail(self, matcher, sample):
        with self.assertRaises(AssertionError):
            matcher(sample)

    def test_ac1_matcher_rejects_the_pre_change_item_5(self):
        self._must_fail(check_ac1_names_route_and_no_abort, PRE_CHANGE_ITEM_5)

    def test_ac3_matcher_rejects_the_pre_change_item_5(self):
        self._must_fail(check_ac3_zero_task_path, PRE_CHANGE_ITEM_5)

    def test_ac2_matcher_rejects_the_pre_change_item_5(self):
        self._must_fail(check_ac2_identification, PRE_CHANGE_ITEM_5)

    def test_ac4_matcher_rejects_the_pre_change_item_5(self):
        self._must_fail(check_ac4_abort_remains, PRE_CHANGE_ITEM_5)

    def test_ac5_matcher_rejects_the_pre_change_item_5(self):
        self._must_fail(check_ac5_commit_value_shape_check, PRE_CHANGE_ITEM_5)


class TestAC1NegativeProofs(unittest.TestCase):
    def test_four_routes_without_the_no_abort_statement_is_rejected(self):
        sample = (
            "5. **Re-entry precondition**: Step I.0 recognises four entry "
            "routes into `implement: pending` — a fresh first pass, a rework "
            "re-entry, the SPEC-change re-entry, and the develop skill's "
            "batch infra auto-resume. "
            + SPEC_CHANGE_DEFINITION_MARKER
            + " (`references/rework-task-synthesis.md` Section 10, the "
            "`**When rework needs a SPEC.md change**` block, cited here, not "
            "restated) and the create-spec → create-plan re-run that follows "
            "it."
        )
        with self.assertRaises(AssertionError):
            check_ac1_names_route_and_no_abort(sample)

    def test_definition_without_the_section_10_citation_is_rejected(self):
        sample = (
            "Step I.0 recognises four entry routes into `implement: pending` "
            "— a fresh first pass, a rework re-entry, the SPEC-change "
            "re-entry, and the develop skill's batch infra auto-resume. "
            + SPEC_CHANGE_DEFINITION_MARKER
            + " and the create-spec → create-plan re-run that follows it. "
            + OUTCOME_MARKER
            + " is not a protocol error and does not ABORT."
        )
        with self.assertRaises(AssertionError):
            check_ac1_names_route_and_no_abort(sample)


class TestAC2NegativeProofs(unittest.TestCase):
    def test_record_fields_listed_without_the_phase_state_citation_are_rejected(
        self,
    ):
        # The conditions are all present, but the record's fields are named
        # without citing `references/phase-state.md`.
        sample = (
            "only when ALL of the following hold, each read from committed "
            "facts only — `workflow.yaml`, the `spec_change` record of "
            "`phase-state/rework.yaml`, and the integration branch's commit "
            "history; no timestamp is compared: `create-spec` and "
            "`create-plan` are `completed`, and `implement` holds a "
            "`base_commit` and a prior `completed_at_commit`. "
            "`phase-state/rework.yaml` holds a `spec_change` record with "
            "`consumed: true` and `replan_authorized: false`. "
            "The prior `completed_at_commit` is a proper ancestor of the "
            "record's `recorded_at_commit`, and `recorded_at_commit` is an "
            "ancestor of the current integration tip. The commit history "
            "shows that the SPEC-change transition that wrote this record "
            "returned `implement` to `pending` — the tier-upgrade procedure "
            "writes the same record without doing so, so the flags alone do "
            "not suffice. `tasks` is non-empty and every task is `merged`. "
            "The identification uses no session memory and no worker "
            "natural-language output. A resume of the same re-entry — "
            "`implement` reads `in_progress`, written by that re-entry's own "
            "Step I.1 — is admitted on the same facts."
        )
        with self.assertRaises(AssertionError) as ctx:
            check_ac2_identification(sample)
        self.assertIn("references/phase-state.md", str(ctx.exception))

    def test_identification_without_the_inputs_statement_is_rejected(self):
        sample = (
            "only when ALL of the following hold, each read from committed "
            "facts only — `workflow.yaml`. A resume of the same re-entry is "
            "admitted on the same facts."
        )
        with self.assertRaises(AssertionError):
            check_ac2_identification(sample)

    def test_identification_without_the_tier_upgrade_evidence_is_rejected(self):
        # Flags and ancestry alone: the commit-history evidence that the
        # transition returned `implement` to `pending` is missing (TM-2).
        live = _step_i0(_read(IMPLEMENT_PHASE_PATH))
        norm = _normalize(live)
        needle = _normalize(
            "The commit history shows that the SPEC-change transition that "
            "wrote this record returned `implement` to `pending`"
        )
        _quiet_in(self, needle, norm)
        with self.assertRaises(AssertionError):
            check_ac2_identification(norm.replace(needle, ""))

    def test_identification_without_the_non_empty_all_merged_condition_is_rejected(
        self,
    ):
        live = _normalize(_step_i0(_read(IMPLEMENT_PHASE_PATH)))
        needle = "`tasks` is non-empty and every task is `merged`"
        _quiet_in(self, needle, live)
        with self.assertRaises(AssertionError):
            check_ac2_identification(live.replace(needle, ""))


class TestAC3NegativeProofs(unittest.TestCase):
    def test_route_that_still_launches_through_step_i2_is_rejected(self):
        sample = (
            "On this route Step I.1 runs as usual and the phase continues "
            "through Step I.2, which launches an implementer, before "
            "Step I.3."
        )
        with self.assertRaises(AssertionError):
            check_ac3_zero_task_path(sample)

    def test_zero_task_path_without_the_new_task_branch_is_rejected(self):
        live = _normalize(_step_i0(_read(IMPLEMENT_PHASE_PATH)))
        needle = _normalize(
            "When the re-plan registered one or more new `pending` tasks, "
            "the entry meets the rework re-entry's condition above and "
            "proceeds through Step I.2 as usual"
        )
        _quiet_in(self, needle, live)
        with self.assertRaises(AssertionError):
            check_ac3_zero_task_path(live.replace(needle, ""))


class TestAC4NegativeProofs(unittest.TestCase):
    def test_synthetic_step_i0_naming_the_route_without_an_abort_is_rejected(
        self,
    ):
        # (c) negative proof: the SPEC-change route is named, but no ABORT
        # paragraph remains.
        sample = (
            "5. **Re-entry precondition**: Step I.0 recognises four entry "
            "routes into `implement: pending`. "
            + SPEC_CHANGE_DEFINITION_MARKER
            + " (`references/rework-task-synthesis.md` Section 10). "
            + OUTCOME_MARKER
            + " is not a protocol error and does not ABORT. "
            + STEP_A6_MARKER
            + " sets `implement` back to `pending`."
        )
        with self.assertRaises(AssertionError):
            check_ac4_abort_remains(sample)

    def test_abort_without_the_not_a_spec_change_carve_out_is_rejected(self):
        sample = (
            "A non-fresh entry satisfying neither condition — every task "
            "`merged` (or otherwise none `pending`), and no task whose "
            "reconciled state is `failed` — is therefore a protocol error: "
            "ABORT the phase immediately, rather than looping through Step "
            "I.2 with nothing to launch."
        )
        with self.assertRaises(AssertionError):
            check_ac4_abort_remains(sample)

    def test_abort_placed_before_the_spec_change_paragraph_is_rejected(self):
        live = _normalize(_step_i0(_read(IMPLEMENT_PHASE_PATH)))
        outcome_at = _index_of("probe", live, OUTCOME_MARKER)
        abort_at = _index_of("probe", live, ABORT_MARKER)
        a6_at = _index_of("probe", live, STEP_A6_MARKER)
        self.assertLess(outcome_at, abort_at)
        self.assertLess(abort_at, a6_at)
        # Swap the SPEC-change outcome sentence group and the ABORT group.
        swapped = (
            live[:outcome_at]
            + live[abort_at:a6_at]
            + live[outcome_at:abort_at]
            + live[a6_at:]
        )
        with self.assertRaises(AssertionError):
            check_ac4_abort_remains(swapped)

    def test_abort_placed_after_the_step_a6_paragraph_is_rejected(self):
        live = _normalize(_step_i0(_read(IMPLEMENT_PHASE_PATH)))
        abort_at = _index_of("probe", live, ABORT_MARKER)
        a6_at = _index_of("probe", live, STEP_A6_MARKER)
        swapped = live[:abort_at] + live[a6_at:] + " " + live[abort_at:a6_at]
        with self.assertRaises(AssertionError):
            check_ac4_abort_remains(swapped)


class TestAC5NegativeProofs(unittest.TestCase):
    def test_ancestry_check_named_without_any_shape_check_is_rejected(self):
        sample = (
            "The prior `completed_at_commit` is a proper ancestor of the "
            "record's `recorded_at_commit`, and `recorded_at_commit` is an "
            "ancestor of the current integration tip; the ancestry checks "
            "run on the integration branch's history."
        )
        with self.assertRaises(AssertionError):
            check_ac5_commit_value_shape_check(sample)

    def test_shape_check_without_the_fail_closed_consequence_is_rejected(self):
        sample = (
            "Before a commit value read from `workflow.yaml` or from the "
            "`spec_change` record appears in any git command, it is checked "
            "against the shape of a full hexadecimal commit object id."
        )
        with self.assertRaises(AssertionError):
            check_ac5_commit_value_shape_check(sample)

    def test_sanitising_instead_of_rejecting_is_rejected(self):
        sample = (
            "before a commit value read from `workflow.yaml` or from the "
            "`spec_change` record appears in any git command, it is checked "
            "against the shape of a full hexadecimal commit object id; a "
            "value that does not match is stripped of its offending "
            "characters and used."
        )
        with self.assertRaises(AssertionError):
            check_ac5_commit_value_shape_check(sample)


class TestAC6NegativeProofs(unittest.TestCase):
    def test_reflowed_rework_paragraph_is_rejected(self):
        reflowed = _normalize(PRE_CHANGE_ITEM_5)
        with self.assertRaises(AssertionError):
            check_ac6_unchanged_parts(reflowed)

    def test_dropped_step_a6_paragraph_is_rejected(self):
        sample = PRE_CHANGE_ITEM_5.replace(STEP_A6_PARAGRAPH_RAW, "")
        with self.assertRaises(AssertionError):
            check_ac6_unchanged_parts(sample)

    def test_a_fenced_block_in_step_i0_is_rejected(self):
        sample = PRE_CHANGE_ITEM_5 + "\n```bash\ngit merge-base a b\n```\n"
        with self.assertRaises(AssertionError):
            check_ac6_no_fenced_block_added(sample)

    def test_pre_change_item_5_satisfies_the_unchanged_parts_matcher(self):
        # The matcher can PASS, not just fail: the pre-change text holds
        # every part AC-6 says stays unchanged.
        check_ac6_unchanged_parts(PRE_CHANGE_ITEM_5)
        check_ac6_no_fenced_block_added(PRE_CHANGE_ITEM_5)


class TestExtractionIsNotVacuous(unittest.TestCase):
    def test_step_i0_region_is_located_and_holds_item_5(self):
        step_i0 = _step_i0(_read(IMPLEMENT_PHASE_PATH))
        _quiet_in(self, "5. **Re-entry precondition**", step_i0)
        self.assertFalse("## Step I.1" in step_i0)

    def test_ordering_matcher_rejects_a_missing_marker(self):
        with self.assertRaises(AssertionError):
            _require_order("probe", "alpha beta", ["alpha", "gamma"])


if __name__ == "__main__":
    unittest.main()
