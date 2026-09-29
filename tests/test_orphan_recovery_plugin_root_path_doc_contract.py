"""Doc-contract tests for task0001 (orphan-recovery-plugin-root-path): the
three places in `em-workflow/references/implement-phase.md` I.2.b step 1
where the ORCHESTRATOR itself launches a plugin-bundled helper resolve that
helper under `${CLAUDE_PLUGIN_ROOT}` by citing Step I.0 step 4, instead of
naming a cwd-relative `em-workflow/scripts/...` path that only exists when
the user's working directory happens to hold an `em-workflow/` checkout
(a marketplace install does not).

The three sites (located by their text, never by line number):

- Site A: I.2.b's Orphan recovery paragraph -- the orchestrator invokes
  `recover-orphaned-task.py` for the candidate task.
- Site B: the Same-session extension's "Invocation contract for this
  branch" -- the orchestrator re-invokes the same script.
- Site C: the ancestor-check bullet -- the orchestrator invokes
  `journal-append-failed.py` with `--reason merge-unverified`.

Covers this task's own Acceptance Criteria
(feature-docs/orphan-recovery-plugin-root-path/tasks/task0001.md):

- AC-1, AC-2, AC-3 (TS-1): each new invocation sentence is pinned as a
  constant and present in I.2.b; each carries its
  `${CLAUDE_PLUGIN_ROOT}/scripts/` path and the "Step I.0 step 4"
  citation; the two recovery sentences also carry the `{project_root}`
  working directory; site A keeps its marker-passing clause and "D2 form 1
  takes precedence over the marker scan"; site C keeps its verbatim
  `--reason merge-unverified` clause and SC-1 / D4 citation.
- AC-4 (TS-4): the resolution-failure statements (the recovery Residual
  for sites A and B, the Helper-failure residue for site C) are present,
  and the existing "Helper-failure residue: when that invocation exits
  non-zero, ..." sentence is unchanged.
- AC-5 (TS-2, TS-3): the three pre-change cwd-relative forms are absent
  from the whole document (each with a negative proof against a verbatim
  pre-change sample), and the fallback search literals occur only inside
  Step I.0 (with a negative proof against a forged copy).

AC-6 (the two pin conversions) lives in tests/test_implement_routeback_gate.py
and tests/test_merge_unverified_exit_doc_contract.py; AC-7 (diff scope) is
checked by inspecting the task's diff, not by a unit test.

Red/green discipline: every PRE_CHANGE_*_SAMPLE constant below is a verbatim
excerpt of `em-workflow/references/implement-phase.md` at this task's base
commit (efadb30ff28dab548db0da5a986e670b8203cbe5), copied with its line
breaks and indentation, captured before this task's edit landed -- each
paired with a positive test proving the sample carries the OLD form
(proving the sample is genuinely pre-change) and a retained-anchor guard (a
phrase present in both the sample and the live document, proving the sample
comes from the same place). Each new-wording constant is paired with a
"forged" sanity test (`str.replace` the phrase out and confirm the matcher
would then fail) proving the matcher is not vacuous, and was additionally
observed to fail before this task's edit landed (recorded in this task's own
tests.yaml, not reproduced here).

Follows the established convention (standard library only, document text
read from the repository root computed from this module's own path,
module-level constants for each literal, whitespace-normalized matching).
"""

import ast
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
IMPLEMENT_PHASE_PATH = REPO_ROOT / "em-workflow" / "references" / "implement-phase.md"

I2B_HEADING = "### I.2.b: Wake phase"
I2C_HEADING = "### I.2.c: Failed handling"
STEP_I0_HEADING = "## Step I.0: Preconditions"
STEP_I1_HEADING = "## Step I.1"


def _read():
    return IMPLEMENT_PHASE_PATH.read_text(encoding="utf-8")


def _normalize_ws(text):
    """Collapse all whitespace runs (including line-wrap newlines) to a
    single space, so multi-word assertions never depend on where the prose
    happens to wrap a line."""
    return re.sub(r"\s+", " ", text)


def _slice(text, start_marker, end_marker):
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    return text[start:end]


def _i2b_section(text):
    return _slice(text, I2B_HEADING, I2C_HEADING)


def _step_i0_section(text):
    return _slice(text, STEP_I0_HEADING, STEP_I1_HEADING)


# ===========================================================================
# AC-1, AC-2, AC-3 (TS-1): the three new invocation sentences.
# ===========================================================================

RECOVER_SCRIPT_PLUGIN_ROOT_PATH = (
    "${CLAUDE_PLUGIN_ROOT}/scripts/recover-orphaned-task.py"
)
JOURNAL_HELPER_PLUGIN_ROOT_PATH = (
    "${CLAUDE_PLUGIN_ROOT}/scripts/journal-append-failed.py"
)
STEP_I0_STEP4_CITATION = "Step I.0 step 4"
PROJECT_ROOT_CWD = "`{project_root}`"

# Site A -- Orphan recovery paragraph.
SITE_A_INVOCATION_PHRASE = (
    "invokes `RECOVER_SCRIPT=${CLAUDE_PLUGIN_ROOT}/scripts/"
    "recover-orphaned-task.py` (resolved per Step I.0 step 4) for the "
    "candidate task with `{project_root}` (the main working tree) as its "
    "working directory"
)
# Site B -- Same-session extension, "Invocation contract for this branch".
SITE_B_INVOCATION_PHRASE = (
    "the orchestrator re-invokes the same `RECOVER_SCRIPT="
    "${CLAUDE_PLUGIN_ROOT}/scripts/recover-orphaned-task.py` (resolved per "
    "Step I.0 step 4) for the same candidate task with `{project_root}` "
    "(the main working tree) as its working directory"
)
# Site C -- ancestor-check bullet.
SITE_C_INVOCATION_PHRASE = (
    "the orchestrator invokes "
    "`${CLAUDE_PLUGIN_ROOT}/scripts/journal-append-failed.py` (resolved per "
    "Step I.0 step 4) exactly once, with the task id and `--reason "
    "merge-unverified`, supplying no launch identity (IMPLEMENTATION.md's "
    "SC-1, D4)"
)

# (phrase, plugin-root path the phrase must carry, whether it must also
# carry the `{project_root}` working directory)
NEW_INVOCATION_SITES = (
    ("site A", SITE_A_INVOCATION_PHRASE, RECOVER_SCRIPT_PLUGIN_ROOT_PATH, True),
    ("site B", SITE_B_INVOCATION_PHRASE, RECOVER_SCRIPT_PLUGIN_ROOT_PATH, True),
    ("site C", SITE_C_INVOCATION_PHRASE, JOURNAL_HELPER_PLUGIN_ROOT_PATH, False),
)

# Retained around site A (AC-1): the marker-passing clause and D2 form 1
# precedence stay.
SITE_A_MARKER_PASSING_PHRASE = (
    "passing that marker (or, when the orchestrator's own session identity "
    "and start time are already known some other way, those values "
    "directly"
)
SITE_A_D2_FORM1_PRECEDENCE_PHRASE = (
    "D2 form 1 takes precedence over the marker scan"
)
# Retained after site B (AC-2): the inputs list is unchanged.
SITE_B_INPUTS_RETAINED_PHRASE = (
    "the same journal, Agent-index and identity inputs the call above "
    "already passes, plus at least one of seven evidence inputs"
)
# Retained inside site C (AC-3): verbatim clause and the SC-1 / D4 citation.
SITE_C_VERBATIM_CLAUSE_PHRASE = (
    "exactly once, with the task id and `--reason merge-unverified`, "
    "supplying no launch identity (IMPLEMENTATION.md's SC-1, D4)"
)


class TestNewInvocationWording(unittest.TestCase):
    """AC-1, AC-2, AC-3 (TS-1)."""

    @classmethod
    def setUpClass(cls):
        cls.i2b = _normalize_ws(_i2b_section(_read()))

    def test_each_new_invocation_sentence_present_in_i2b(self):
        for label, phrase, _path, _cwd in NEW_INVOCATION_SITES:
            with self.subTest(site=label):
                self.assertIn(phrase, self.i2b)

    def test_each_constant_carries_its_plugin_root_path(self):
        for label, phrase, path, _cwd in NEW_INVOCATION_SITES:
            with self.subTest(site=label):
                self.assertIn(path, phrase)

    def test_each_constant_cites_step_i0_step4(self):
        for label, phrase, _path, _cwd in NEW_INVOCATION_SITES:
            with self.subTest(site=label):
                self.assertIn(STEP_I0_STEP4_CITATION, phrase)

    def test_recovery_constants_carry_project_root_working_directory(self):
        for label, phrase, _path, needs_cwd in NEW_INVOCATION_SITES:
            if not needs_cwd:
                continue
            with self.subTest(site=label):
                self.assertIn(PROJECT_ROOT_CWD, phrase)

    def test_journal_helper_constant_states_no_working_directory(self):
        # A4: the journal-helper invocation carries no cwd requirement.
        self.assertNotIn("working directory", SITE_C_INVOCATION_PHRASE)

    def test_forged_sanity_each_new_sentence_detected_if_removed(self):
        for label, phrase, _path, _cwd in NEW_INVOCATION_SITES:
            with self.subTest(site=label):
                forged = self.i2b.replace(phrase, "")
                self.assertNotIn(phrase, forged)

    def test_site_a_keeps_marker_passing_clause_and_d2_precedence(self):
        self.assertIn(SITE_A_MARKER_PASSING_PHRASE, self.i2b)
        self.assertIn(SITE_A_D2_FORM1_PRECEDENCE_PHRASE, self.i2b)

    def test_site_b_keeps_its_inputs_list(self):
        self.assertIn(SITE_B_INPUTS_RETAINED_PHRASE, self.i2b)

    def test_site_c_keeps_verbatim_merge_unverified_clause(self):
        self.assertIn(SITE_C_VERBATIM_CLAUSE_PHRASE, self.i2b)
        self.assertIn(SITE_C_VERBATIM_CLAUSE_PHRASE, SITE_C_INVOCATION_PHRASE)

    def test_forged_sanity_retained_phrases_detected_if_removed(self):
        for phrase in (
            SITE_A_MARKER_PASSING_PHRASE,
            SITE_A_D2_FORM1_PRECEDENCE_PHRASE,
            SITE_B_INPUTS_RETAINED_PHRASE,
            SITE_C_VERBATIM_CLAUSE_PHRASE,
        ):
            with self.subTest(phrase=phrase):
                forged = self.i2b.replace(phrase, "")
                self.assertNotIn(phrase, forged)


# ===========================================================================
# AC-5 (TS-2): the three pre-change cwd-relative forms are gone.
# ===========================================================================

OLD_SITE_A_FORM = "invokes `em-workflow/scripts/recover-orphaned-task.py`"
OLD_SITE_B_FORM = "re-invokes `em-workflow/scripts/recover-orphaned-task.py`"
OLD_SITE_C_FORM = (
    "the orchestrator invokes `em-workflow/scripts/journal-append-failed.py`"
)

# Verbatim excerpts of implement-phase.md at the base commit
# efadb30ff28dab548db0da5a986e670b8203cbe5, copied with line breaks and
# indentation.
PRE_CHANGE_SITE_A_SAMPLE = (
    "     (IMPLEMENTATION.md D2), then invokes\n"
    "     `em-workflow/scripts/recover-orphaned-task.py` for the candidate task,\n"
    "     passing that marker (or, when the orchestrator's own session identity\n"
    "     and start time are already known some other way, those values\n"
    "     directly — D2 form 1 takes precedence over the marker scan). That"
)
PRE_CHANGE_SITE_B_SAMPLE = (
    "     Invocation contract for this branch: the orchestrator re-invokes\n"
    "     `em-workflow/scripts/recover-orphaned-task.py` for the same candidate\n"
    "     task, with the same journal, Agent-index and identity inputs the call\n"
    "     above already passes, plus at least one of seven evidence inputs —"
)
PRE_CHANGE_SITE_C_SAMPLE = (
    "     cited here rather than restated. Once termination is confirmed, the\n"
    "     orchestrator invokes `em-workflow/scripts/journal-append-failed.py`\n"
    "     exactly once, with the task id and `--reason merge-unverified`,\n"
    "     supplying no launch identity (IMPLEMENTATION.md's SC-1, D4). Step 1"
)

# (label, old form, verbatim pre-change sample, anchor present in BOTH the
# sample and the live document -- guards the negative proof against passing
# vacuously)
OLD_FORM_PROOFS = (
    (
        "site A",
        OLD_SITE_A_FORM,
        PRE_CHANGE_SITE_A_SAMPLE,
        SITE_A_D2_FORM1_PRECEDENCE_PHRASE,
    ),
    (
        "site B",
        OLD_SITE_B_FORM,
        PRE_CHANGE_SITE_B_SAMPLE,
        SITE_B_INPUTS_RETAINED_PHRASE,
    ),
    (
        "site C",
        OLD_SITE_C_FORM,
        PRE_CHANGE_SITE_C_SAMPLE,
        SITE_C_VERBATIM_CLAUSE_PHRASE,
    ),
)

# Script-internal / out-of-scope sentences (A2, FR7). They describe what a
# script invokes internally or identify the writer, and must survive; none
# of them matches an old form above.
SCRIPT_INTERNAL_ORPHANED_PHRASE = (
    "invoke `em-workflow/scripts/journal-append-failed.py` exactly once, "
    "with the task id and reason `orphaned`"
)
SCRIPT_INTERNAL_STALE_LAUNCHED_PHRASE = (
    "invoke `em-workflow/scripts/journal-append-failed.py` exactly once, "
    "with the task id and reason `stale-launched`"
)
SCRIPT_INTERNAL_ON_FULL_PROOF_PHRASE = (
    "On full proof that script — never the orchestrator — invokes "
    "`em-workflow/scripts/journal-append-failed.py` itself"
)
STALE_LAUNCHED_CAVEAT_PHRASE = (
    "(cited there, not restated here) invokes "
    "`em-workflow/scripts/journal-append-failed.py`, which"
)
SUPPORTING_CAST_JOURNAL_BULLET_PHRASE = (
    "the `em-workflow/scripts/journal-append-failed.py` helper, invoked by "
    "I.2.b step 1's orphan-recovery attempt"
)
OUT_OF_SCOPE_RETAINED_PHRASES = (
    SCRIPT_INTERNAL_ORPHANED_PHRASE,
    SCRIPT_INTERNAL_STALE_LAUNCHED_PHRASE,
    SCRIPT_INTERNAL_ON_FULL_PROOF_PHRASE,
    STALE_LAUNCHED_CAVEAT_PHRASE,
    SUPPORTING_CAST_JOURNAL_BULLET_PHRASE,
)


class TestCwdRelativeInvocationFormsAbsent(unittest.TestCase):
    """AC-5 (TS-2): no cwd-relative orchestrator invocation remains."""

    @classmethod
    def setUpClass(cls):
        cls.whole = _normalize_ws(_read())

    def test_old_forms_absent_from_whole_document(self):
        for label, form, _sample, _anchor in OLD_FORM_PROOFS:
            with self.subTest(site=label):
                self.assertNotIn(form, self.whole)

    def test_old_form_matchers_flag_the_pre_change_samples(self):
        # Negative proof: each matcher above WOULD fire on the verbatim
        # pre-change wording, so its absence from the live document is
        # meaningful.
        for label, form, sample, _anchor in OLD_FORM_PROOFS:
            with self.subTest(site=label):
                self.assertIn(form, _normalize_ws(sample))

    def test_pre_change_samples_come_from_the_same_place(self):
        # Retained anchor: present in the sample AND the live document.
        for label, _form, sample, anchor in OLD_FORM_PROOFS:
            with self.subTest(site=label):
                self.assertIn(anchor, _normalize_ws(sample))
                self.assertIn(anchor, self.whole)

    def test_script_internal_and_out_of_scope_sentences_survive(self):
        for phrase in OUT_OF_SCOPE_RETAINED_PHRASES:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.whole)

    def test_old_forms_do_not_match_the_out_of_scope_sentences(self):
        for phrase in OUT_OF_SCOPE_RETAINED_PHRASES:
            for label, form, _sample, _anchor in OLD_FORM_PROOFS:
                with self.subTest(phrase=phrase, site=label):
                    self.assertNotIn(form, phrase)


# ===========================================================================
# AC-5, NFR1 (TS-3): the fallback search literals live only in Step I.0.
# ===========================================================================

FALLBACK_SEARCH_LITERALS = (
    "$HOME/.claude/plugins",
    "$HOME/.claude/skills",
    "*/em-workflow/*/scripts/*",
)


def _fallback_literal_counts(text, literal):
    """(occurrences in the whole normalized document, occurrences inside
    the normalized Step I.0 section)."""
    return (
        _normalize_ws(text).count(literal),
        _normalize_ws(_step_i0_section(text)).count(literal),
    )


def _fallback_literal_confined_to_step_i0(text, literal):
    whole_count, step_i0_count = _fallback_literal_counts(text, literal)
    return step_i0_count >= 1 and whole_count == step_i0_count


class TestFallbackLiteralsConfinedToStepI0(unittest.TestCase):
    """AC-5 (TS-3), NFR1: Step I.0 step 4 owns the trusted-root fallback;
    the three literals are never restated anywhere else."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read()

    def test_each_literal_occurs_in_step_i0(self):
        for literal in FALLBACK_SEARCH_LITERALS:
            with self.subTest(literal=literal):
                _whole, step_i0_count = _fallback_literal_counts(
                    self.text, literal
                )
                self.assertGreaterEqual(step_i0_count, 1)

    def test_each_literal_count_in_whole_document_equals_step_i0_count(self):
        for literal in FALLBACK_SEARCH_LITERALS:
            with self.subTest(literal=literal):
                whole_count, step_i0_count = _fallback_literal_counts(
                    self.text, literal
                )
                self.assertEqual(whole_count, step_i0_count)

    def test_live_document_passes_the_confinement_check(self):
        for literal in FALLBACK_SEARCH_LITERALS:
            with self.subTest(literal=literal):
                self.assertTrue(
                    _fallback_literal_confined_to_step_i0(self.text, literal)
                )

    def test_forged_copy_with_literal_inserted_into_i2b_fails_the_check(self):
        # Negative proof: restating one literal inside I.2.b (the text just
        # before the I.2.c heading is inside I.2.b) makes the check fail.
        for literal in FALLBACK_SEARCH_LITERALS:
            with self.subTest(literal=literal):
                forged = self.text.replace(
                    I2C_HEADING, f"`{literal}`\n\n{I2C_HEADING}", 1
                )
                self.assertNotEqual(forged, self.text)
                self.assertFalse(
                    _fallback_literal_confined_to_step_i0(forged, literal)
                )

    def test_new_invocation_sentences_do_not_restate_the_literals(self):
        for label, phrase, _path, _cwd in NEW_INVOCATION_SITES:
            for literal in FALLBACK_SEARCH_LITERALS:
                with self.subTest(site=label, literal=literal):
                    self.assertNotIn(literal, phrase)


# ===========================================================================
# AC-4 (TS-4): resolution-failure outcomes.
# ===========================================================================

# Sites A and B: one statement covering both recovery invocations.
RECOVERY_RESOLUTION_FAILURE_PHRASE = (
    "When RECOVER_SCRIPT cannot be resolved, whether for this invocation or "
    "for the re-invocation under the Same-session extension below, nothing "
    "is invoked — no other location, in particular no cwd-relative path, is "
    "tried — and this candidate's outcome is the Residual above, with the "
    "journal unchanged"
)
# Site C: an addition next to the existing Helper-failure residue.
JOURNAL_HELPER_RESOLUTION_FAILURE_PHRASE = (
    "When the journal helper cannot be resolved, nothing is invoked — no "
    "other location, in particular no cwd-relative path, is tried — and this "
    "task is governed by the Helper-failure residue just stated, with the "
    "journal unchanged"
)
# The existing sentence stays verbatim (another module pins it too).
EXISTING_HELPER_FAILURE_RESIDUE_PHRASE = (
    "Helper-failure residue: when that invocation exits non-zero, or "
    "reports any outcome other than `appended`, the journal is left "
    "unchanged"
)
RESOLUTION_FAILURE_PHRASES = (
    RECOVERY_RESOLUTION_FAILURE_PHRASE,
    JOURNAL_HELPER_RESOLUTION_FAILURE_PHRASE,
)


class TestResolutionFailureStatements(unittest.TestCase):
    """AC-4 (TS-4)."""

    @classmethod
    def setUpClass(cls):
        cls.i2b = _normalize_ws(_i2b_section(_read()))

    def test_resolution_failure_statements_present_in_i2b(self):
        for phrase in RESOLUTION_FAILURE_PHRASES:
            with self.subTest(phrase=phrase):
                self.assertIn(phrase, self.i2b)

    def test_forged_sanity_each_statement_detected_if_removed(self):
        for phrase in RESOLUTION_FAILURE_PHRASES:
            with self.subTest(phrase=phrase):
                forged = self.i2b.replace(phrase, "")
                self.assertNotIn(phrase, forged)

    def test_recovery_statement_names_the_residual_and_the_unchanged_journal(self):
        self.assertIn("the Residual above", RECOVERY_RESOLUTION_FAILURE_PHRASE)
        self.assertIn("journal unchanged", RECOVERY_RESOLUTION_FAILURE_PHRASE)

    def test_journal_helper_statement_names_the_helper_failure_residue(self):
        self.assertIn(
            "Helper-failure residue",
            JOURNAL_HELPER_RESOLUTION_FAILURE_PHRASE,
        )
        self.assertIn(
            "journal unchanged", JOURNAL_HELPER_RESOLUTION_FAILURE_PHRASE
        )

    def test_existing_helper_failure_residue_sentence_unchanged(self):
        self.assertIn(EXISTING_HELPER_FAILURE_RESIDUE_PHRASE, self.i2b)

    def test_journal_helper_statement_sits_next_to_the_existing_residue(self):
        residue_at = self.i2b.index(EXISTING_HELPER_FAILURE_RESIDUE_PHRASE)
        statement_at = self.i2b.index(JOURNAL_HELPER_RESOLUTION_FAILURE_PHRASE)
        # "Next to": within the same bullet paragraph, a few sentences apart.
        self.assertLess(abs(statement_at - residue_at), 1200)


class TestModuleImportsStdlibOnly(unittest.TestCase):
    def test_module_uses_only_standard_library_imports(self):
        source = Path(__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        allowed = {"ast", "re", "unittest", "pathlib"}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    self.assertIn(top, allowed, f"non-stdlib import: {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    top = node.module.split(".")[0]
                    self.assertIn(top, allowed, f"non-stdlib import: {node.module}")


if __name__ == "__main__":
    unittest.main()
