"""Tests for task0001 (batch-stop-contract): the terminal-line contract SSOT
document and its pointer in `batch-mode.md`.

Covers task0001 Acceptance Criteria
(feature-docs/batch-stop-contract/tasks/task0001.md):

- AC-1: `em-workflow/references/batch-terminal-line.md` exists, carries the
  seven fixed level-2 headings in order, defines the prefix literal and the
  fixed four-field order, states that the same prefix/fields are used for
  both terminal states, states no external tool is needed, and states
  emission happens only in a batch-mode run.
- AC-2: the `## Stop reason codes` section's table extracts to exactly the
  nine fixed codes (no duplicate, no empty member), documents `none` as
  reserved for `state=completed`, and states every stop line also carries a
  `step` field and a `detail` field.
- AC-3: the `## Stop point coverage` section binds each of the nine
  stop-point keys to exactly one reason code (bidirectional coverage), each
  row naming a source document.
- AC-4: the `## No line on a wait turn` section states stop condition 5
  emits no line; the `## Field values` section defines the `no-step`
  sentinel and its condition.
- AC-5: the `## Responsibility boundary` section states no status operation
  against the external task-management service, and that `detail` carries
  no confidential information.
- AC-6: `batch-mode.md` names the contract document, restates none of its
  literals, keeps its Non-packet gates table row count unchanged, and still
  satisfies IMPLEMENTATION.md D7's constraints.
- AC-7: the prefix literal occurs, among all files under `em-workflow/`,
  only in `references/batch-terminal-line.md`, and within that file only
  inside fenced example blocks.
- AC-8: this module is discovered by `python3 -m unittest discover -s
  tests`, imports the Python standard library only (`os`, `re`, `unittest`,
  `pathlib` -- no third-party or project dependency), and every matcher it
  defines carries a negative proof plus a non-vacuity guard.

Test authoring follows IMPLEMENTATION.md's "Test authoring (NFR4)"
convention (the pattern of `tests/test_routeback_reset_scope_version_bump.py`):
durable invariants over fixed literals wherever a literal would go stale,
negative proof + non-vacuity guard per matcher, pure regression guards over
retained wording exempted. All assertions read raw file text
(`Path.read_text`), matching `tests/test_reference_sweep.py`'s convention, so
a literal hidden inside a fenced block is still seen by the sweep in AC-7.

Matcher -> negative-proof inventory:

- `_assert_well_formed_code_list` (reason-code table extractor validation):
  negative proofs are `test_duplicate_code_is_rejected` and
  `test_empty_first_cell_is_rejected`; non-vacuity guards are
  `test_duplicate_table_is_otherwise_well_formed` and
  `test_empty_cell_table_is_otherwise_well_formed`.
- `_assert_bidirectional_coverage` (coverage table extractor validation):
  negative proofs are `test_missing_key_is_rejected`,
  `test_code_outside_set_is_rejected` and
  `test_duplicate_stop_point_key_is_rejected`; non-vacuity guards are the
  corresponding `..._parses_into_a_non_empty_pair_of_sets` tests.
- Regression guards over retained `batch-mode.md` wording (AC-6's row-count,
  catch-all, diff-size-row and per-command-row checks) are exempt from a
  negative proof per IMPLEMENTATION.md's Test authoring note -- they pin
  content this task does not change, they do not introduce a new matcher.

Edge cases (Test Notes): a reason code mentioned only in prose (not a table
row) must not be picked up by the extractor
(`test_extractor_ignores_reason_codes_mentioned_only_in_prose`); a
stop-point key listed twice must fail
(`test_duplicate_stop_point_key_is_rejected`); the AC-7 sweep walks every
file under `em-workflow/` via `os.walk`, never a hand-maintained allowlist.

Rework round 1 (task0004, feature-docs/batch-stop-contract/tasks/task0004.md)
extends the module above -- the pinned sets grow from nine to eleven members
and gain one matcher per new contract statement, each with its own negative
proof and non-vacuity guard (this addendum uses task0004's own AC numbering,
distinct from the task0001 numbering above):

- AC-1: the reason-code table extracts to exactly eleven codes (the nine
  above plus `feature_resolution_aborted` and `docs_commit_conflict_aborted`),
  and the section's stated count ("eleven") equals the table's row count
  (`test_section_stated_count_equals_table_row_count`).
- AC-2: the coverage table binds all eleven stop-point keys exactly once,
  and the full key->code pairing (not merely the two sets) matches the
  pinned mapping, including the two new rows
  (`test_pairing_matches_expected_key_code_mapping`).
- AC-3: the `no-step` bullet's stop-point set is extracted structurally
  (backtick tokens, not a substring search) and checked as a set relation
  against the real coverage table
  (`test_no_step_bullet_names_the_stop_points_as_a_set`).
- AC-4: the coverage section states a phase-specific-wins precedence rule
  after the table, naming the three overlapping stop points
  (`test_precedence_rule_stated`; matcher
  `_assert_precedence_rule_stated`; negative proof
  `test_missing_precedence_rule_is_rejected`; non-vacuity guard
  `test_forged_section_still_parses_into_a_complete_well_formed_table`).
- AC-5: `## Line format` states the `detail` normalization rule
  (`test_states_detail_normalization_rule`; matcher
  `_assert_detail_normalization_stated`; negative proof
  `test_missing_normalization_rule_is_rejected`; non-vacuity guard
  `test_forged_body_is_otherwise_well_formed`).
- AC-6: `## No line on a wait turn` states the general rule (not reached
  either terminal state -> no line), naming the implement launch/wake
  turns as further instances, while retaining the stop-condition-5 wording
  as a pure regression guard (`test_states_general_no_line_rule`,
  `test_states_stop_condition_5_emits_no_line`).
- AC-7: every coverage row's Source cell resolves to an existing file under
  `em-workflow/`, and the third-column intro sentence claims only naming,
  not ownership (`test_source_paths_resolve_to_existing_files`,
  `test_source_column_intro_claims_only_naming`; matcher
  `_assert_source_paths_resolve`; negative proof
  `test_nonexistent_source_path_is_rejected`; non-vacuity guard
  `test_forged_row_is_otherwise_well_formed_and_extracted`).
- AC-8: this task modifies no test module that pre-dates the feature (this
  module is the feature's own, created by task0001); the whole-suite run
  and the plugin invariant checker are exercised outside this module, per
  the implementer's report.

TestCoverageMatcherNegativeProofs' expected pair counts are derived from
`len(_KEY_CODE_PAIRS_IN_ORDER)` rather than re-pinned as literals (Test
Notes trap), so the eleven-member set change does not silently make those
non-vacuity guards vacuous.

Rework round 2 (develop-once-option task0003,
feature-docs/develop-once-option/tasks/task0003.md) extends the module
above again -- a third terminal-line `state` value (`phase_done`, marking
a `--once` phase-boundary turn) is added to the domain, `step`'s meaning
is clarified, and the two count-bearing sentences that pinned the domain
at two members are replaced with non-counting phrasing (this addendum
uses task0003's own AC numbering, distinct from the task0001 / task0004
numbering above):

- AC-1: the `state` bullet's domain now includes `phase_done`, stated
  with its `reason=none` / non-empty single-line `detail` / same-prefix/
  same-fields/same-order conditions
  (`test_field_values_state_domain_includes_phase_done`,
  `test_field_values_phase_done_conditions_stated`).
- AC-2: a consumer that sees `state=phase_done` re-launches the same
  feature
  (`test_field_values_phase_done_consumer_relaunches_same_feature`).
- AC-3: `step` names the step EXECUTED in that turn, never the step the
  next launch resumes at, and is `verify` at the verify-fail rework
  boundary (`test_field_values_step_names_the_executed_step`,
  `test_field_values_step_at_verify_fail_rework_is_verify`).
- AC-4: the `state` bullet and the `## No line on a wait turn` sentence
  no longer pin the domain's size at two
  (`test_no_document_wording_states_a_terminal_state_count`); the
  pre-existing assertion pinning the old "either ... two terminal
  states" wording (`test_states_general_no_line_rule`) is updated in
  this same change rather than left to go stale (IMPLEMENTATION.md D4).
- AC-5: no new test -- this criterion is the pre-existing regression
  guards (heading order/count, reason-code count, coverage table,
  `state=completed` / `state=stopped` semantics, prefix-in-fence scope)
  staying green unmodified, proving the addition did not disturb them.
- AC-6: the `batch-mode.md` pointer guard (D2) is extended from the
  four-field-name / prefix / reason-code / sentinel checks to the full
  `state` value set, via its own matcher
  (`_assert_no_state_value_literal`), with a negative proof, a
  non-vacuity guard and a false-positive proof over ordinary
  `completed` / `skipped` / `stopped` step-status vocabulary
  (`TestStateValueGuardMatcher`).
- AC-7: no new test -- the whole-suite run and the stdlib-only imports
  (unchanged: `os`, `re`, `unittest`, `pathlib`) are verified by the
  implementer's report, per IMPLEMENTATION.md's Test authoring
  convention.

Rework round 3 (develop-once-option task0003, feature-docs/develop-once-
option/tasks/task0005.md, review round 1 D9) fixes a contract-drift defect
introduced by rework round 2: the `state` domain grew to include
`phase_done`, but the `reason` and `step` value-domain descriptions were
left in their pre-`phase_done` wording in two places each. This addendum
uses task0005's own AC numbering, distinct from the numbering above:

- AC-1 / AC-2: `none`'s reserved range (D9 rule 1) is stated identically
  at both sites -- the `## Field values` `reason` bullet and the `##
  Stop reason codes` closing prose -- naming both `state=completed` and
  `state=phase_done`, with the old `state=completed`-only restrictive
  phrasing removed from both
  (`test_field_values_reason_bullet_reserved_for_non_stop_states`,
  `test_none_documented_as_reserved_for_non_stop_states`; matcher
  `_assert_none_reserved_for_non_stop_states_stated`).
- AC-3: both sites' negative proof + non-vacuity guard live in
  `TestNoneReservedRangeMatcherNegativeProofs`, replacing (strengthening,
  not deleting) the pre-task0005
  `test_none_documented_as_reserved_for_completed`, whose bare
  `none`/`reserved`/`state=completed` co-occurrence check passed even
  with the old restrictive phrasing still present -- the exact defect
  this rework fixes.
- AC-4 / AC-5: the `step` bullet's rule precedence (D9 rule 2) and the
  Step C outcome asymmetry are each stated explicitly
  (`test_field_values_step_precedence_stated`,
  `test_field_values_step_c_asymmetry_stated`; matchers
  `_assert_step_precedence_stated`, `_assert_step_c_asymmetry_stated`).
- AC-6: both matchers' negative proof + non-vacuity guard use the same
  forged sample -- the exact pre-task0005 `step` bullet text, which
  states the general rule and the two now-precedent rules but neither
  the priority relation nor the Step C asymmetry
  (`TestStepPrecedenceMatcherNegativeProof`,
  `TestStepCAsymmetryMatcherNegativeProof`).
- AC-7: no new test -- the pre-existing regression guards (heading
  order/count, eleven reason codes with `Applies to state` all
  `stopped`, coverage table, task0003's `phase_done` wording) staying
  green unmodified, plus the implementer's report on the whole-suite run.
"""

import os
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"
CONTRACT_PATH = PLUGIN_ROOT / "references" / "batch-terminal-line.md"
BATCH_MODE_PATH = PLUGIN_ROOT / "references" / "batch-mode.md"

PREFIX = "EM_WORKFLOW_TERMINAL:"
SENTINEL = "no-step"

# IMPLEMENTATION.md Shared Components -- fixed by the plan, not renegotiated
# here.
CONTRACT_HEADINGS = [
    "Purpose",
    "Line format",
    "Field values",
    "Stop reason codes",
    "Stop point coverage",
    "No line on a wait turn",
    "Responsibility boundary",
]

REASON_CODES = frozenset(
    {
        "step_stuck",
        "step_needs_intervention",
        "workflow_yaml_unparseable",
        "git_setup_aborted",
        "gate_fail_closed",
        "gate_option_unavailable",
        "implement_task_failed",
        "verify_rework_cap_reached",
        "completion_aborted",
        # rework round 1 (D9): closes the two previously-uncovered stops.
        "feature_resolution_aborted",
        "docs_commit_conflict_aborted",
    }
)

STOP_POINT_KEYS = frozenset(
    {
        "stop-condition-2",
        "stop-condition-3",
        "stop-condition-4",
        "stop-condition-6",
        "fail-closed-abort",
        "policy-option-unavailable",
        "implement-second-failure",
        "verify-rework-cap",
        "step-c-abort",
        # rework round 1 (D9): closes the two previously-uncovered stops.
        "step-a-abort",
        "docs-commit-conflict",
    }
)

# The no-step sentinel's stop points (AC-3) -- a subset of STOP_POINT_KEYS,
# checked as a set relation against the real coverage table, not as prose.
NO_STEP_STOP_POINTS = frozenset({"stop-condition-6", "step-a-abort", "step-c-abort"})

# The full `state` value domain (D1, develop-once-option task0003) --
# re-declared locally per the Cross-module isolation convention rather
# than imported from another test module.
STATE_VALUES = frozenset({"completed", "stopped", "phase_done"})

# The `--once` phase-boundary value alone (D1): contract-only vocabulary
# that occurs nowhere else, so D2 rule 2 checks its bare literal for
# absence too, not just the `state={value}` shape.
ONCE_BOUNDARY_STATE_VALUE = "phase_done"

# develop-once-option task0005 (D9 rule 1): the old restrictive phrasing,
# verbatim from before this task, that limited `none`'s use to
# `state=completed` alone at each of the two sites this task synchronizes.
# Used both to build forged negative-proof samples and to assert the real
# document no longer contains them.
NONE_RESERVED_OLD_PHRASE_FIELD_VALUES = "(used only when `state=completed`)"
NONE_RESERVED_OLD_PHRASE_STOP_REASON_CODES = "is reserved for `state=completed`;"

# Ordered pairing used only to build forged coverage samples below -- the
# contract itself treats both STOP_POINT_KEYS and REASON_CODES as unordered.
_KEY_CODE_PAIRS_IN_ORDER = [
    ("stop-condition-2", "step_stuck"),
    ("stop-condition-3", "step_needs_intervention"),
    ("stop-condition-4", "workflow_yaml_unparseable"),
    ("stop-condition-6", "git_setup_aborted"),
    ("fail-closed-abort", "gate_fail_closed"),
    ("policy-option-unavailable", "gate_option_unavailable"),
    ("implement-second-failure", "implement_task_failed"),
    ("verify-rework-cap", "verify_rework_cap_reached"),
    ("step-c-abort", "completion_aborted"),
    # rework round 1 (D9): closes the two previously-uncovered stops.
    ("step-a-abort", "feature_resolution_aborted"),
    ("docs-commit-conflict", "docs_commit_conflict_aborted"),
]

HEADING_RE = re.compile(r"^## (.+?)\s*$", re.MULTILINE)
BACKTICK_CELL_RE = re.compile(r"^`([^`]*)`$")


def _read(path):
    return path.read_text(encoding="utf-8")


def _normalize(text):
    """Collapses all whitespace runs (including line wraps) to a single
    space, matching the convention in tests/test_batch_policies.py, so a
    multi-word prose phrase check does not depend on exactly where the
    source file happens to wrap a line. Never used for table extraction,
    which depends on newlines to delimit rows."""
    return re.sub(r"\s+", " ", text)


def _sections(text):
    """Splits `text` into a dict keyed by level-2 heading text (without the
    leading `## `), each value the body up to the next level-2 heading (or
    end of text). Dict insertion order matches document order, so a caller
    can check heading order via `list(sections.keys())`."""
    matches = list(HEADING_RE.finditer(text))
    sections = {}
    for i, match in enumerate(matches):
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections[match.group(1)] = text[start:end]
    return sections


def _table_rows(section_text):
    """Yields each data row of a Markdown table in `section_text` as a list
    of cell strings, skipping the header row and the `---` separator row.
    Rows are located by the leading/trailing `|` convention used throughout
    this repository's docs (see tests/test_reference_sweep.py)."""
    raw_rows = []
    for line in section_text.splitlines():
        stripped = line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            continue
        cells = [c.strip() for c in stripped.strip("|").split("|")]
        if all(c and set(c) <= {"-", " ", ":"} for c in cells):
            continue  # separator row, e.g. |---|---|---|
        raw_rows.append(cells)
    return raw_rows[1:] if raw_rows else []


def _first_column_code(cell):
    """Extracts the code from a single-backticked cell (`` `code` ``), or
    None when the cell is not of that exact shape -- covers both "not
    backticked" and "empty" malformed cells uniformly."""
    match = BACKTICK_CELL_RE.match(cell)
    if match is None:
        return None
    return match.group(1) or None


def _extract_reason_code_table(section_text):
    """Parses the `## Stop reason codes` table's first column into a list
    of codes, duplicates and malformed (None) entries preserved rather than
    deduplicated -- validation is the caller's job
    (`_assert_well_formed_code_list`). Returns [] when no table rows are
    found (a bare list, not None, since a Markdown table with zero data
    rows and one with a wholly absent table are both "nothing to extract"
    here; callers needing to distinguish parse failure use the row count)."""
    rows = _table_rows(section_text)
    return [_first_column_code(row[0]) for row in rows]


def _assert_well_formed_code_list(test, codes):
    """Validation for the reason-code extractor: no cell failed to parse as
    a single backticked code (a None entry), and no code repeats."""
    test.assertNotIn(
        None, codes, "a reason-code table row's first cell is not a single "
        "backticked, non-empty code"
    )
    test.assertEqual(
        len(codes), len(set(codes)), f"duplicate reason code(s) in {codes}"
    )


def _extract_coverage_table(section_text):
    """Parses the `## Stop point coverage` table into (stop_point_key,
    reason_code) pairs from the first two backticked columns."""
    rows = _table_rows(section_text)
    return [(_first_column_code(row[0]), _first_column_code(row[1])) for row in rows]


def _assert_bidirectional_coverage(test, pairs, expected_keys, expected_codes):
    """Validation for the coverage extractor: every stop-point key appears
    exactly once (multiset equality against `expected_keys`), every bound
    code is a member of `expected_codes`, and every one of `expected_codes`
    is used by at least one row (multiset equality collapsed to set
    equality, since a code used twice still satisfies "at least one")."""
    keys_seen = [key for key, _code in pairs]
    codes_seen = [code for _key, code in pairs]
    test.assertNotIn(
        None, keys_seen, "a coverage row's stop-point key is not a single "
        "backticked, non-empty token"
    )
    test.assertNotIn(
        None, codes_seen, "a coverage row's reason code is not a single "
        "backticked, non-empty token"
    )
    test.assertEqual(
        sorted(keys_seen),
        sorted(expected_keys),
        "every stop-point key must appear exactly once",
    )
    test.assertEqual(
        set(codes_seen),
        set(expected_codes),
        "every reason code must be used by at least one row, and no bound "
        "code may lie outside the closed set",
    )


def _forged_coverage_table(pairs):
    # `_table_rows` always drops its first parsed row as the table header
    # (matching every real table in this document), so a forged sample must
    # carry a header + separator row too, or it silently loses one data row.
    header = "| Stop point | Reason code | Source |\n|---|---|---|\n"
    return header + "".join(
        f"| `{key}` | `{code}` | `skills/develop/SKILL.md` |\n" for key, code in pairs
    )


def _extract_coverage_source_cells(section_text):
    """Parses the `## Stop point coverage` table's third column (raw cell
    text, backticks included) for each data row -- companion to
    `_extract_coverage_table`, which only extracts the first two columns."""
    return [row[2] for row in _table_rows(section_text)]


def _assert_source_paths_resolve(test, cells):
    """Validation for the Source-column extractor (AC-7): every cell is a
    single backticked, plugin-relative path that resolves to an existing
    file under `em-workflow/`. Deliberately does NOT use `subTest` -- a
    `subTest`-scoped `AssertionError` is swallowed locally rather than
    propagated to a caller's `assertRaises`, which would break the negative
    proof (`test_nonexistent_source_path_is_rejected`)."""
    for cell in cells:
        path_str = _first_column_code(cell)
        test.assertIsNotNone(
            path_str, f"source cell is not a single backticked path: {cell!r}"
        )
        test.assertTrue(
            (PLUGIN_ROOT / path_str).is_file(),
            f"source path does not resolve to an existing file under "
            f"em-workflow/: {path_str}",
        )


NO_STEP_BULLET_RE = re.compile(
    r"`no-step` applies whenever.*?(?=\n- `|\Z)", re.DOTALL
)
_HYPHENATED_BACKTICK_TOKEN_RE = re.compile(r"`([a-z0-9]+(?:-[a-z0-9]+)+)`")


def _extract_no_step_stop_points(field_values_section_text):
    """Extracts the set of backticked, hyphenated stop-point keys named in
    the `no-step` bullet of `## Field values` (AC-3) -- a structural
    extraction (via the bullet's backtick tokens), not a prose substring
    search. `no-step` itself is excluded (it also matches the hyphenated
    backtick-token shape but is the sentinel, not a stop-point key)."""
    match = NO_STEP_BULLET_RE.search(field_values_section_text)
    if match is None:
        return set()
    tokens = set(_HYPHENATED_BACKTICK_TOKEN_RE.findall(match.group(0)))
    return tokens - {"no-step"}


def _assert_precedence_rule_stated(test, coverage_section_text):
    """Validation for the precedence-rule matcher (AC-4): the coverage
    section states that a phase-specific stop point takes precedence over
    the generic `stop-condition-N` rows, names the three overlapping cases,
    and restricts `stop-condition-3`'s meaning to the states no
    phase-specific row covers."""
    normalized = _normalize(coverage_section_text)
    test.assertIn(
        "phase-specific stop point takes precedence over the generic",
        normalized,
    )
    for key in ("implement-second-failure", "verify-rework-cap", "docs-commit-conflict"):
        with test.subTest(key=key):
            test.assertIn(f"`{key}`", coverage_section_text)
    test.assertIn("`stop-condition-3`", coverage_section_text)
    test.assertIn("`failed`", coverage_section_text)
    test.assertIn("`needs_update`", coverage_section_text)
    test.assertIn("no phase-specific row covers", normalized)


def _assert_detail_normalization_stated(test, line_format_section_text):
    """Validation for the `detail`-normalization matcher (AC-5): the `##
    Line format` section states the CR/LF/TAB-to-space rule, the
    space-collapsing rule, and the non-empty placeholder fallback."""
    normalized = _normalize(line_format_section_text)
    test.assertIn("CR", line_format_section_text)
    test.assertIn("LF", line_format_section_text)
    test.assertIn("TAB", line_format_section_text)
    test.assertIn("single space", normalized)
    test.assertIn("collapse", normalized.lower())
    test.assertIn("placeholder", normalized.lower())
    test.assertIn("non-empty", normalized.lower())


def _assert_no_state_value_literal(test, text, state_values, boundary_value):
    """D2's `state`-value guard shape (develop-once-option task0003),
    implemented independently by this module and
    `tests/test_batch_stop_contract_skill_wiring.py` (task0002): for
    every value in `state_values`, the `state={value}` form (bare,
    backticked or quoted) must be absent from `text`; additionally
    `boundary_value`'s bare literal must be absent on its own, since it
    is contract-only vocabulary that occurs nowhere else. Ordinary
    step-status words (`completed` / `stopped` / `skipped`) are never
    checked bare here -- only the `state=` shape and the boundary value
    are -- so this cannot false-positive on that vocabulary."""
    for value in sorted(state_values):
        for spelling in (f"state={value}", f"`state={value}`", f'"state={value}"'):
            test.assertNotIn(
                spelling, text, f"found forbidden literal: {spelling!r}"
            )
    test.assertNotIn(
        boundary_value,
        text,
        f"found forbidden bare literal: {boundary_value!r}",
    )


def _assert_none_reserved_for_non_stop_states_stated(test, section_text, old_phrase):
    """R-A (develop-once-option task0005, D9 rule 1): `none` is reserved
    for the non-stop terminal states -- `state=completed` and
    `state=phase_done` -- named together in the same passage, with the
    old `state=completed`-only restrictive phrasing (`old_phrase`,
    verbatim from before this task) gone. Applied identically at both
    sites this task synchronizes: the `## Field values` `reason` bullet
    and the `## Stop reason codes` closing prose."""
    normalized = _normalize(section_text)
    test.assertIn("`none`", section_text)
    test.assertIn("reserved", normalized)
    test.assertIn("`state=completed`", section_text)
    test.assertIn("`state=phase_done`", section_text)
    test.assertIn("non-stop terminal state", normalized)
    test.assertNotIn(old_phrase, section_text)


def _assert_step_precedence_stated(test, field_values_section_text):
    """R-B (develop-once-option task0005, D9 rule 2): the general
    executed-step rule, and the two rules that take precedence over it
    (the `no-step` sentinel; `state=completed` -> `retrospect`), stated
    with a readable priority relation rather than three unordered
    sentences."""
    normalized = _normalize(field_values_section_text)
    test.assertIn("names the step EXECUTED in that turn", normalized)
    test.assertIn("take precedence over the general rule", normalized)
    test.assertIn("`no-step`", field_values_section_text)
    test.assertIn("`state=completed`", field_values_section_text)
    test.assertIn("`retrospect`", field_values_section_text)


def _assert_step_c_asymmetry_stated(test, field_values_section_text):
    """R-B (develop-once-option task0005, D9 rule 2): a Step C turn's
    value differs by outcome -- `retrospect` on normal completion,
    `no-step` on `step-c-abort` -- stated explicitly rather than left to
    be inferred from the precedence rules alone."""
    normalized = _normalize(field_values_section_text)
    test.assertIn("Step C is not a `workflow.yaml` step", normalized)
    test.assertIn("normal completion is `retrospect`", normalized)
    test.assertIn("`step-c-abort` is `no-step`", normalized)


def _iter_em_workflow_files(plugin_root):
    for dirpath, _dirnames, filenames in os.walk(plugin_root):
        for filename in filenames:
            yield Path(dirpath) / filename


class TestContractDocumentStructure(unittest.TestCase):
    """AC-1."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(CONTRACT_PATH)
        cls.sections = _sections(cls.text)

    def test_document_exists(self):
        self.assertTrue(CONTRACT_PATH.is_file())

    def test_seven_level_2_headings_in_order(self):
        self.assertEqual(list(self.sections.keys()), CONTRACT_HEADINGS)

    def test_prefix_literal_is_defined(self):
        self.assertIn(PREFIX, self.text)

    def test_fixed_four_field_order(self):
        section = self.sections["Line format"]
        for field in ("state", "step", "reason", "detail"):
            with self.subTest(field=field):
                self.assertIn(f"`{field}`", section)
        order = [section.index(f"`{f}`") for f in ("state", "step", "reason", "detail")]
        self.assertEqual(order, sorted(order))

    def test_states_same_prefix_and_fields_for_both_terminal_states(self):
        section = self.sections["Line format"]
        self.assertIn("same prefix and the same four fields", _normalize(section))
        self.assertIn("`state=completed`", section)
        self.assertIn("`state=stopped`", section)

    def test_states_no_external_tool_needed(self):
        self.assertIn("no external tool", _normalize(self.sections["Line format"]))

    def test_states_batch_only_emission(self):
        self.assertIn(
            "only in a batch-mode run", _normalize(self.sections["Line format"])
        )

    def test_states_detail_normalization_rule(self):
        """AC-5: CR/LF/TAB each become a single space, runs of spaces
        collapse, and an empty normalized value is replaced by a fixed
        non-empty placeholder."""
        _assert_detail_normalization_stated(self, self.sections["Line format"])

    def test_field_values_detail_bullet_consistent_with_normalization(self):
        """AC-5: `## Field values`'s `detail` bullet remains consistent with
        the normalization rule -- in particular it still promises a
        non-empty value, which the placeholder fallback is what makes
        true."""
        detail_bullet_text = self.sections["Field values"]
        self.assertIn("non-empty", detail_bullet_text)

    def test_field_values_state_domain_includes_phase_done(self):
        """AC-1 (develop-once-option task0003, D1): the `state` bullet's
        value domain now includes the third value `phase_done` alongside
        the original `completed` / `stopped`."""
        section = self.sections["Field values"]
        for value in ("completed", "stopped", "phase_done"):
            with self.subTest(value=value):
                self.assertIn(f"`{value}`", section)

    def test_field_values_phase_done_conditions_stated(self):
        """AC-1: `phase_done` is emitted with `reason=none` and a
        non-empty, single-line `detail`, using the same prefix, the same
        four fields and the same field order as every other terminal
        line."""
        section = _normalize(self.sections["Field values"])
        self.assertIn("`reason=none`", section)
        self.assertIn("non-empty, single-line `detail`", section)
        self.assertIn("same prefix", section)
        self.assertIn("same four fields", section)
        self.assertIn("same field order", section)

    def test_field_values_phase_done_consumer_relaunches_same_feature(self):
        """AC-2: a consumer that sees `state=phase_done` re-launches the
        same feature to continue it."""
        section = _normalize(self.sections["Field values"])
        self.assertIn("`state=phase_done`", section)
        self.assertIn("re-launches the same feature", section)

    def test_field_values_step_names_the_executed_step(self):
        """AC-3: `step` always names the step EXECUTED in that turn,
        never the step the next launch resumes at."""
        section = _normalize(self.sections["Field values"])
        self.assertIn("names the step EXECUTED in that turn", section)
        self.assertIn("never the step the next", section)
        self.assertIn("launch resumes at", section)

    def test_field_values_step_at_verify_fail_rework_is_verify(self):
        """AC-3: at the verify-fail rework boundary, `step`'s value is
        `verify`, even though the next launch resumes at `implement`."""
        section = _normalize(self.sections["Field values"])
        self.assertIn(
            "verify-fail rework boundary the value is `verify`", section
        )
        self.assertIn("next launch resumes at `implement`", section)

    def test_field_values_reason_bullet_reserved_for_non_stop_states(self):
        """AC-1 (develop-once-option task0005, D9 rule 1): the `##
        Field values` `reason` bullet states `none` is reserved for the
        non-stop terminal states, naming both `state=completed` and
        `state=phase_done`, with the old `state=completed`-only
        restrictive phrasing gone."""
        _assert_none_reserved_for_non_stop_states_stated(
            self,
            self.sections["Field values"],
            NONE_RESERVED_OLD_PHRASE_FIELD_VALUES,
        )

    def test_field_values_step_precedence_stated(self):
        """AC-4 (develop-once-option task0005, D9 rule 2): the `step`
        bullet states the general executed-step rule and the two rules
        that take precedence over it with a readable priority relation."""
        _assert_step_precedence_stated(self, self.sections["Field values"])

    def test_field_values_step_c_asymmetry_stated(self):
        """AC-5 (develop-once-option task0005, D9 rule 2): the `step`
        bullet states that a Step C turn's value differs by outcome --
        `retrospect` on normal completion, `no-step` on
        `step-c-abort`."""
        _assert_step_c_asymmetry_stated(self, self.sections["Field values"])

    def test_no_document_wording_states_a_terminal_state_count(self):
        """AC-4 (FR11, IMPLEMENTATION.md D4): neither of the two
        originally count-pinning sentences (the `state` bullet's "closed
        set of two values", the `## No line on a wait turn` opening
        sentence's "two terminal states") states a fixed number of
        terminal states any more."""
        self.assertNotIn("two values", self.text)
        self.assertNotIn("two terminal states", self.text)


class TestStopReasonCodes(unittest.TestCase):
    """AC-2."""

    @classmethod
    def setUpClass(cls):
        cls.section = _sections(_read(CONTRACT_PATH))["Stop reason codes"]
        cls.codes = _extract_reason_code_table(cls.section)

    def test_table_has_rows(self):
        self.assertTrue(self.codes)

    def test_codes_are_well_formed(self):
        _assert_well_formed_code_list(self, self.codes)

    def test_extracted_set_equals_the_eleven_fixed_codes(self):
        self.assertEqual(set(self.codes), REASON_CODES)

    def test_section_stated_count_equals_table_row_count(self):
        """AC-1: the section's stated count (prose) equals the table's
        data-row count -- both must have moved from nine to eleven
        together."""
        self.assertIn("eleven", self.section.lower())
        self.assertNotIn("nine", self.section.lower())
        self.assertEqual(len(self.codes), 11)
        self.assertEqual(len(self.codes), len(REASON_CODES))

    def test_none_documented_as_reserved_for_non_stop_states(self):
        """AC-2 (develop-once-option task0005, D9 rule 1). Replaces the
        pre-task0005 `test_none_documented_as_reserved_for_completed`,
        which only checked `none` / `reserved` / `state=completed`
        co-occurrence and therefore passed even with the old
        `state=completed`-only restrictive phrasing still in place (the
        contract drift this task fixes): the closing prose now states
        the same non-stop reserved range as the `## Field values`
        `reason` bullet, naming both `state=completed` and
        `state=phase_done`, with the old restrictive phrasing gone."""
        _assert_none_reserved_for_non_stop_states_stated(
            self, self.section, NONE_RESERVED_OLD_PHRASE_STOP_REASON_CODES
        )

    def test_states_step_and_detail_fields_also_carried(self):
        self.assertIn("`step`", self.section)
        self.assertIn("`detail`", self.section)

    def test_extractor_ignores_reason_codes_mentioned_only_in_prose(self):
        sample = (
            "| Code | Meaning | Applies to `state` |\n"
            "|---|---|---|\n"
            "| `step_stuck` | a stuck step | `stopped` |\n"
            "\n"
            "The code `git_setup_aborted` is mentioned here in prose only, "
            "never as a table row.\n"
        )
        self.assertEqual(_extract_reason_code_table(sample), ["step_stuck"])


FORGED_DUPLICATE_CODE_TABLE = (
    "| Code | Meaning | Applies to `state` |\n"
    "|---|---|---|\n"
    "| `step_stuck` | first occurrence | `stopped` |\n"
    "| `step_stuck` | second occurrence | `stopped` |\n"
)

FORGED_EMPTY_CELL_TABLE = (
    "| Code | Meaning | Applies to `state` |\n"
    "|---|---|---|\n"
    "| `step_stuck` | well formed row | `stopped` |\n"
    "|  | missing code | `stopped` |\n"
)


class TestReasonCodeExtractorNegativeProofs(unittest.TestCase):
    """NFR4: negative proof + non-vacuity guard for the reason-code table
    validator (`_assert_well_formed_code_list`)."""

    def test_duplicate_table_is_otherwise_well_formed(self):
        codes = _extract_reason_code_table(FORGED_DUPLICATE_CODE_TABLE)
        self.assertEqual(codes, ["step_stuck", "step_stuck"])

    def test_duplicate_code_is_rejected(self):
        codes = _extract_reason_code_table(FORGED_DUPLICATE_CODE_TABLE)
        with self.assertRaises(AssertionError):
            _assert_well_formed_code_list(self, codes)

    def test_empty_cell_table_is_otherwise_well_formed(self):
        codes = _extract_reason_code_table(FORGED_EMPTY_CELL_TABLE)
        self.assertEqual(len(codes), 2)
        self.assertEqual(codes[0], "step_stuck")

    def test_empty_first_cell_is_rejected(self):
        codes = _extract_reason_code_table(FORGED_EMPTY_CELL_TABLE)
        with self.assertRaises(AssertionError):
            _assert_well_formed_code_list(self, codes)


# Forged samples for the reserved-range matcher's negative proof /
# non-vacuity guard (AC-3, develop-once-option task0005): the exact old
# wording at each of the two sites, verbatim from before this task, so a
# regression back to the old restrictive phrasing reproduces exactly this
# forged text.
FORGED_FIELD_VALUES_REASON_BULLET_OLD_RESTRICTIVE = (
    "- `reason` — one of the eleven stop reason codes listed below, or the "
    "reserved value `none` (used only when `state=completed`)."
)

FORGED_STOP_REASON_CODES_PROSE_OLD_RESTRICTIVE = (
    "The value `none` is reserved for `state=completed`; it is not itself a "
    "stop reason code and is never used together with `state=stopped`. Every "
    "stop line also carries a `step` field alongside `reason`, and always "
    "carries a `detail` field."
)


class TestNoneReservedRangeMatcherNegativeProofs(unittest.TestCase):
    """NFR3: negative proof + non-vacuity guard for the reserved-range
    matcher (`_assert_none_reserved_for_non_stop_states_stated`, AC-3,
    develop-once-option task0005), exercised over both sites this task
    synchronizes."""

    def test_field_values_forged_bullet_is_otherwise_well_formed(self):
        """Non-vacuity: the forged bullet is well-formed reason-bullet
        prose (mentions `none` / `reserved` / `state=completed`) -- the
        rejection below is caused by the missing `state=phase_done` and
        the old restrictive phrasing, not by unrelated malformation."""
        self.assertIn("`none`", FORGED_FIELD_VALUES_REASON_BULLET_OLD_RESTRICTIVE)
        self.assertIn("reserved", FORGED_FIELD_VALUES_REASON_BULLET_OLD_RESTRICTIVE)
        self.assertIn(
            "`state=completed`", FORGED_FIELD_VALUES_REASON_BULLET_OLD_RESTRICTIVE
        )

    def test_field_values_old_restrictive_phrasing_is_rejected(self):
        with self.assertRaises(AssertionError):
            _assert_none_reserved_for_non_stop_states_stated(
                self,
                FORGED_FIELD_VALUES_REASON_BULLET_OLD_RESTRICTIVE,
                NONE_RESERVED_OLD_PHRASE_FIELD_VALUES,
            )

    def test_stop_reason_codes_forged_prose_is_otherwise_well_formed(self):
        """Non-vacuity: the forged prose is well-formed (mentions `none`
        / `reserved` / `state=completed` / `step` / `detail`) -- the
        rejection below is caused by the missing `state=phase_done` and
        the old restrictive phrasing, not by unrelated malformation."""
        self.assertIn("`none`", FORGED_STOP_REASON_CODES_PROSE_OLD_RESTRICTIVE)
        self.assertIn("reserved", FORGED_STOP_REASON_CODES_PROSE_OLD_RESTRICTIVE)
        self.assertIn(
            "`state=completed`", FORGED_STOP_REASON_CODES_PROSE_OLD_RESTRICTIVE
        )
        self.assertIn("`step`", FORGED_STOP_REASON_CODES_PROSE_OLD_RESTRICTIVE)
        self.assertIn("`detail`", FORGED_STOP_REASON_CODES_PROSE_OLD_RESTRICTIVE)

    def test_stop_reason_codes_old_restrictive_phrasing_is_rejected(self):
        with self.assertRaises(AssertionError):
            _assert_none_reserved_for_non_stop_states_stated(
                self,
                FORGED_STOP_REASON_CODES_PROSE_OLD_RESTRICTIVE,
                NONE_RESERVED_OLD_PHRASE_STOP_REASON_CODES,
            )


# Forged sample for the step-precedence / Step C asymmetry matchers'
# negative proof (AC-6, develop-once-option task0005): the exact old
# `step` bullet, verbatim from before this task -- well-formed prose that
# states the general rule and the two now-precedent rules, but without the
# explicit priority relation or the Step C asymmetry statement.
FORGED_OLD_STEP_BULLET_WITHOUT_PRECEDENCE = (
    "`step` — a `workflow.yaml` step id (`create-spec`, `design`, "
    "`create-plan`, `implement`, `review`, `verify`, `retrospect`), or the "
    "single sentinel `no-step`. `no-step` applies whenever no "
    "`workflow.yaml` step is in effect at the stop point: "
    "`stop-condition-6` (Step 0's git-setup abort), `step-a-abort` (Step "
    "A's feature-resolution failure), and `step-c-abort` (Step C's abort "
    "— every workflow step has already completed by then, and the stop "
    "happens outside any of them). `step` always names the step EXECUTED "
    "in that turn, never the step the next launch resumes at; at the "
    "verify-fail rework boundary the value is `verify`, even though the "
    "next launch resumes at `implement`. On `state=completed` the value "
    "is always `retrospect` — the final workflow step, which a completed "
    "run has always reached."
)


class TestStepPrecedenceMatcherNegativeProof(unittest.TestCase):
    """NFR3: negative proof + non-vacuity guard for the step-precedence
    matcher (`_assert_step_precedence_stated`, AC-6, develop-once-option
    task0005)."""

    def test_forged_old_bullet_is_otherwise_well_formed(self):
        self.assertIn(
            "names the step EXECUTED in that turn",
            _normalize(FORGED_OLD_STEP_BULLET_WITHOUT_PRECEDENCE),
        )
        self.assertIn("`no-step`", FORGED_OLD_STEP_BULLET_WITHOUT_PRECEDENCE)
        self.assertIn("`retrospect`", FORGED_OLD_STEP_BULLET_WITHOUT_PRECEDENCE)

    def test_missing_precedence_wording_is_rejected(self):
        with self.assertRaises(AssertionError):
            _assert_step_precedence_stated(
                self, FORGED_OLD_STEP_BULLET_WITHOUT_PRECEDENCE
            )


class TestStepCAsymmetryMatcherNegativeProof(unittest.TestCase):
    """NFR3: negative proof + non-vacuity guard for the Step C asymmetry
    matcher (`_assert_step_c_asymmetry_stated`, AC-6, develop-once-option
    task0005)."""

    def test_forged_old_bullet_is_otherwise_well_formed(self):
        self.assertIn("`step-c-abort`", FORGED_OLD_STEP_BULLET_WITHOUT_PRECEDENCE)
        self.assertIn("`retrospect`", FORGED_OLD_STEP_BULLET_WITHOUT_PRECEDENCE)

    def test_missing_asymmetry_wording_is_rejected(self):
        with self.assertRaises(AssertionError):
            _assert_step_c_asymmetry_stated(
                self, FORGED_OLD_STEP_BULLET_WITHOUT_PRECEDENCE
            )


class TestStopPointCoverage(unittest.TestCase):
    """AC-2, AC-4, AC-7."""

    @classmethod
    def setUpClass(cls):
        cls.section = _sections(_read(CONTRACT_PATH))["Stop point coverage"]
        cls.pairs = _extract_coverage_table(cls.section)

    def test_table_has_rows(self):
        self.assertTrue(self.pairs)

    def test_bidirectional_coverage(self):
        _assert_bidirectional_coverage(self, self.pairs, STOP_POINT_KEYS, REASON_CODES)

    def test_pairing_matches_expected_key_code_mapping(self):
        """AC-2: the full table (not merely its key-set and code-set) must
        match the pinned pairing exactly -- in particular the two new rows
        `step-a-abort` -> `feature_resolution_aborted` and
        `docs-commit-conflict` -> `docs_commit_conflict_aborted`."""
        self.assertEqual(dict(self.pairs), dict(_KEY_CODE_PAIRS_IN_ORDER))

    def test_each_row_names_a_source_document(self):
        rows = _table_rows(self.section)
        for row in rows:
            with self.subTest(row=row):
                self.assertTrue(row[2].strip())

    def test_source_paths_resolve_to_existing_files(self):
        """AC-7: every Source cell is a single backticked, plugin-relative
        path that resolves to an existing file under `em-workflow/`."""
        cells = _extract_coverage_source_cells(self.section)
        _assert_source_paths_resolve(self, cells)

    def test_source_column_intro_claims_only_naming(self):
        """AC-7: the sentence introducing the third column claims only that
        the document names/specifies the stop point -- not that it "owns
        (defines)" the stop point (Design section 5)."""
        self.assertNotIn("owns (defines)", self.section)
        self.assertIn("names the document", _normalize(self.section))

    def test_precedence_rule_stated(self):
        """AC-4: a phase-specific stop point takes precedence over the
        generic `stop-condition-N` rows."""
        _assert_precedence_rule_stated(self, self.section)


FORGED_MISSING_KEY_TABLE = _forged_coverage_table(_KEY_CODE_PAIRS_IN_ORDER[:-1])
# Filters by key rather than relying on "step-c-abort" being positionally
# last -- D9 appended two pairs after it, so a positional [:-1] would instead
# collide with the last-appended pair and (mis-)produce a duplicate key.
FORGED_CODE_OUTSIDE_SET_TABLE = _forged_coverage_table(
    [pair for pair in _KEY_CODE_PAIRS_IN_ORDER if pair[0] != "step-c-abort"]
    + [("step-c-abort", "bogus_code")]
)
FORGED_DUPLICATE_KEY_TABLE = _forged_coverage_table(
    _KEY_CODE_PAIRS_IN_ORDER[:-1] + [("stop-condition-2", "completion_aborted")]
)


class TestCoverageMatcherNegativeProofs(unittest.TestCase):
    """NFR4: negative proof + non-vacuity guard for the bidirectional
    coverage validator (`_assert_bidirectional_coverage`).

    Expected pair counts are derived from `len(_KEY_CODE_PAIRS_IN_ORDER)`
    rather than re-pinned as literals, so a future change to the pinned set
    cannot silently make these non-vacuity guards vacuous (Test Notes
    trap)."""

    def test_missing_key_table_parses_into_a_non_empty_pair_of_sets(self):
        pairs = _extract_coverage_table(FORGED_MISSING_KEY_TABLE)
        self.assertEqual(len(pairs), len(_KEY_CODE_PAIRS_IN_ORDER) - 1)
        self.assertTrue({key for key, _code in pairs})
        self.assertTrue({code for _key, code in pairs})

    def test_missing_key_is_rejected(self):
        pairs = _extract_coverage_table(FORGED_MISSING_KEY_TABLE)
        with self.assertRaises(AssertionError):
            _assert_bidirectional_coverage(self, pairs, STOP_POINT_KEYS, REASON_CODES)

    def test_code_outside_set_table_parses_into_a_non_empty_pair_of_sets(self):
        pairs = _extract_coverage_table(FORGED_CODE_OUTSIDE_SET_TABLE)
        self.assertEqual(len(pairs), len(_KEY_CODE_PAIRS_IN_ORDER))
        self.assertTrue({key for key, _code in pairs})
        self.assertTrue({code for _key, code in pairs})

    def test_code_outside_set_is_rejected(self):
        pairs = _extract_coverage_table(FORGED_CODE_OUTSIDE_SET_TABLE)
        with self.assertRaises(AssertionError):
            _assert_bidirectional_coverage(self, pairs, STOP_POINT_KEYS, REASON_CODES)

    def test_duplicate_stop_point_key_table_parses_into_a_non_empty_pair_of_sets(self):
        pairs = _extract_coverage_table(FORGED_DUPLICATE_KEY_TABLE)
        self.assertEqual(len(pairs), len(_KEY_CODE_PAIRS_IN_ORDER))
        self.assertTrue({key for key, _code in pairs})
        self.assertTrue({code for _key, code in pairs})

    def test_duplicate_stop_point_key_is_rejected(self):
        pairs = _extract_coverage_table(FORGED_DUPLICATE_KEY_TABLE)
        with self.assertRaises(AssertionError):
            _assert_bidirectional_coverage(self, pairs, STOP_POINT_KEYS, REASON_CODES)


# Real table content (well-formed, complete) with no precedence-rule prose
# after it -- exercises `_assert_precedence_rule_stated` in isolation from
# `_assert_bidirectional_coverage`.
FORGED_COVERAGE_SECTION_WITHOUT_PRECEDENCE = _forged_coverage_table(
    _KEY_CODE_PAIRS_IN_ORDER
)


class TestPrecedenceMatcherNegativeProof(unittest.TestCase):
    """NFR4: negative proof + non-vacuity guard for the precedence-rule
    validator (`_assert_precedence_rule_stated`, AC-4)."""

    def test_forged_section_still_parses_into_a_complete_well_formed_table(self):
        pairs = _extract_coverage_table(FORGED_COVERAGE_SECTION_WITHOUT_PRECEDENCE)
        _assert_bidirectional_coverage(self, pairs, STOP_POINT_KEYS, REASON_CODES)

    def test_missing_precedence_rule_is_rejected(self):
        with self.assertRaises(AssertionError):
            _assert_precedence_rule_stated(
                self, FORGED_COVERAGE_SECTION_WITHOUT_PRECEDENCE
            )


# A `## Line format` body stating only the one-physical-line guarantee --
# well-formed prose, but missing the detail-normalization rule.
FORGED_LINE_FORMAT_WITHOUT_DETAIL_NORMALIZATION = (
    "The terminal line is always exactly one physical line -- it is never "
    "wrapped. The same prefix and the same four fields are used whether the "
    "run completed normally or stopped."
)


class TestDetailNormalizationMatcherNegativeProof(unittest.TestCase):
    """NFR4: negative proof + non-vacuity guard for the detail-normalization
    validator (`_assert_detail_normalization_stated`, AC-5)."""

    def test_forged_body_is_otherwise_well_formed(self):
        self.assertIn(
            "one physical line", FORGED_LINE_FORMAT_WITHOUT_DETAIL_NORMALIZATION
        )

    def test_missing_normalization_rule_is_rejected(self):
        with self.assertRaises(AssertionError):
            _assert_detail_normalization_stated(
                self, FORGED_LINE_FORMAT_WITHOUT_DETAIL_NORMALIZATION
            )


# A coverage row naming a Source document that does not exist under
# em-workflow/ -- otherwise well-formed and picked up cleanly by both
# extractors.
FORGED_NONEXISTENT_SOURCE_ROW_TABLE = (
    "| Stop point | Reason code | Source |\n"
    "|---|---|---|\n"
    "| `stop-condition-2` | `step_stuck` | `references/does-not-exist.md` |\n"
)


class TestSourcePathMatcherNegativeProof(unittest.TestCase):
    """NFR4: negative proof + non-vacuity guard for the Source-path
    resolvability validator (`_assert_source_paths_resolve`, AC-7)."""

    def test_forged_row_is_otherwise_well_formed_and_extracted(self):
        pairs = _extract_coverage_table(FORGED_NONEXISTENT_SOURCE_ROW_TABLE)
        self.assertEqual(pairs, [("stop-condition-2", "step_stuck")])
        cells = _extract_coverage_source_cells(FORGED_NONEXISTENT_SOURCE_ROW_TABLE)
        self.assertEqual(cells, ["`references/does-not-exist.md`"])

    def test_nonexistent_source_path_is_rejected(self):
        cells = _extract_coverage_source_cells(FORGED_NONEXISTENT_SOURCE_ROW_TABLE)
        with self.assertRaises(AssertionError):
            _assert_source_paths_resolve(self, cells)


class TestNoLineOnWaitTurnAndSentinel(unittest.TestCase):
    """AC-3, AC-6."""

    @classmethod
    def setUpClass(cls):
        cls.sections = _sections(_read(CONTRACT_PATH))

    def test_states_stop_condition_5_emits_no_line(self):
        """AC-6: regression guard over TS-4's retained wording -- keep
        asserting the retained "stop condition 5" phrase so this guarantee
        does not silently disappear when the rule is generalized."""
        section = _normalize(self.sections["No line on a wait turn"])
        self.assertIn("stop condition 5", section)
        self.assertIn("no terminal line", section)

    def test_states_general_no_line_rule(self):
        """AC-6 (task0004 rework round 1); AC-4 (develop-once-option
        task0003 rework round 2): the general rule -- a turn that has
        not reached any terminal state emits no line -- with the
        implement launch/wake turns named as further instances alongside
        stop condition 5. The wording moved from "either ... two
        terminal states" to a non-counting form once a third terminal
        state (`phase_done`) exists, so this assertion's checked phrase
        is updated in the same change that rewrites the sentence
        (IMPLEMENTATION.md D4) -- it still pins the underlying rule, not
        merely the count-free rephrasing."""
        section = _normalize(self.sections["No line on a wait turn"])
        self.assertIn("has not reached any", section)
        self.assertIn("terminal state", section)
        self.assertIn("launch", section)
        self.assertIn("wake", section)
        self.assertIn("implement", section)

    def test_field_values_defines_the_sentinel_and_its_condition(self):
        section = self.sections["Field values"]
        self.assertIn(f"`{SENTINEL}`", section)
        self.assertIn("no `workflow.yaml` step is in effect", _normalize(section))

    def test_no_step_bullet_names_the_stop_points_as_a_set(self):
        """AC-3: the `no-step` bullet's stop-point set equals exactly
        {stop-condition-6, step-a-abort, step-c-abort}, asserted as a set
        relation against the real coverage table (not a prose substring)."""
        coverage_section = _sections(_read(CONTRACT_PATH))["Stop point coverage"]
        coverage_keys = {key for key, _code in _extract_coverage_table(coverage_section)}
        extracted = _extract_no_step_stop_points(self.sections["Field values"])
        self.assertEqual(extracted, NO_STEP_STOP_POINTS)
        self.assertTrue(
            extracted <= coverage_keys,
            "every no-step stop point must be a key of the coverage table",
        )


class TestResponsibilityBoundary(unittest.TestCase):
    """AC-5."""

    @classmethod
    def setUpClass(cls):
        cls.section = _sections(_read(CONTRACT_PATH))["Responsibility boundary"]

    def test_states_no_status_operation_against_external_service(self):
        section = _normalize(self.section)
        self.assertIn("no status operation", section)
        self.assertIn("external task-management service", section)

    def test_states_detail_carries_no_confidential_information(self):
        self.assertIn("`detail`", self.section)
        self.assertIn("no confidential information", _normalize(self.section))


class TestBatchModePointer(unittest.TestCase):
    """AC-6."""

    @classmethod
    def setUpClass(cls):
        cls.text = _read(BATCH_MODE_PATH)
        cls.sections = _sections(cls.text)

    def test_names_the_contract_document(self):
        self.assertIn("references/batch-terminal-line.md", self.text)

    def test_restates_no_contract_literal(self):
        self.assertNotIn(PREFIX, self.text)
        for code in sorted(REASON_CODES):
            with self.subTest(code=code):
                self.assertNotIn(code, self.text)
        self.assertNotIn(SENTINEL, self.text)
        for field in ("state=", "step=", "reason=", "detail="):
            with self.subTest(field=field):
                self.assertNotIn(field, self.text)

    def test_restates_no_state_value_shape(self):
        """AC-6 (FR10, D2, develop-once-option task0003): the literal-
        absence guard is extended to the grown three-member `state`
        value set. The pre-existing whole-file `state=` substring check
        above already subsumes every spelling of `state={value}` for any
        value, so this test additionally proves the checked value SET is
        the grown domain (not the stale two), and that the `--once`
        boundary value's bare literal (D2 rule 2) is absent too."""
        _assert_no_state_value_literal(
            self, self.text, STATE_VALUES, ONCE_BOUNDARY_STATE_VALUE
        )

    def test_non_packet_gates_table_row_count_unchanged(self):
        rows = _table_rows(self.sections["Non-packet gates"])
        self.assertEqual(len(rows), 10)

    def test_d7_pinned_strings_still_absent(self):
        self.assertNotIn("decision table", self.text.lower())
        self.assertNotIn("決定表", self.text)
        self.assertNotIn("rework.spec-change", self.text)
        self.assertNotIn("failed_items", self.text)

    def test_catch_all_paragraph_unchanged(self):
        self.assertIn("ten rows above", self.text)

    def test_diff_size_gate_row_unchanged(self):
        match = re.search(r"^\|.*diff-size gate.*\|$", self.text, re.MULTILINE)
        self.assertIsNotNone(match, "diff-size gate row not found in batch-mode.md")
        self.assertIn("unlisted-gate fallback", match.group(0))

    def test_per_command_approval_row_unchanged(self):
        match = re.search(
            r"^\|.*Per-command approval fallback.*\|$", self.text, re.MULTILINE
        )
        self.assertIsNotNone(
            match, "per-command approval fallback row not found in batch-mode.md"
        )
        self.assertIn("per literal command string", match.group(0))


# Forged batch-mode.md-shaped excerpts for the state-value guard matcher's
# negative proof / non-vacuity guard / false-positive proof (AC-6, D2,
# develop-once-option task0003).
FORGED_BATCH_MODE_EXCERPT_WITH_STATE_VALUE = (
    "See `references/batch-terminal-line.md` for the field grammar. "
    "After a `--once` launch reaches a phase boundary, the run emits "
    "`state=phase_done` as its terminal line."
)

FORGED_BATCH_MODE_EXCERPT_WITH_BARE_BOUNDARY_VALUE = (
    "See `references/batch-terminal-line.md` for the field grammar. "
    "The phase_done outcome ends a --once launch's turn."
)

FORGED_BATCH_MODE_EXCERPT_WITH_STEP_STATUS_WORDS = (
    "workflow.yaml marks a step `completed` (or `skipped` for design "
    "only); a task that instead ends `stopped` is reported separately."
)


class TestStateValueGuardMatcher(unittest.TestCase):
    """NFR4: negative proof + non-vacuity guard for the state-value guard
    matcher (`_assert_no_state_value_literal`, AC-6, D2, develop-once-
    option task0003)."""

    def test_forged_state_value_excerpt_is_otherwise_well_formed(self):
        self.assertIn(
            "references/batch-terminal-line.md",
            FORGED_BATCH_MODE_EXCERPT_WITH_STATE_VALUE,
        )

    def test_state_value_shape_is_rejected(self):
        with self.assertRaises(AssertionError):
            _assert_no_state_value_literal(
                self,
                FORGED_BATCH_MODE_EXCERPT_WITH_STATE_VALUE,
                STATE_VALUES,
                ONCE_BOUNDARY_STATE_VALUE,
            )

    def test_forged_bare_boundary_excerpt_is_otherwise_well_formed(self):
        self.assertIn(
            "references/batch-terminal-line.md",
            FORGED_BATCH_MODE_EXCERPT_WITH_BARE_BOUNDARY_VALUE,
        )

    def test_bare_boundary_literal_is_rejected(self):
        with self.assertRaises(AssertionError):
            _assert_no_state_value_literal(
                self,
                FORGED_BATCH_MODE_EXCERPT_WITH_BARE_BOUNDARY_VALUE,
                STATE_VALUES,
                ONCE_BOUNDARY_STATE_VALUE,
            )

    def test_step_status_vocabulary_excerpt_is_otherwise_well_formed(self):
        for word in ("completed", "skipped", "stopped"):
            with self.subTest(word=word):
                self.assertIn(
                    word, FORGED_BATCH_MODE_EXCERPT_WITH_STEP_STATUS_WORDS
                )

    def test_step_status_vocabulary_does_not_false_positive(self):
        """AC-6: bare `completed` / `skipped` / `stopped`, used as
        ordinary workflow.yaml step-status words (never in the
        `state={value}` shape, never the boundary value's bare literal),
        must not trip the guard."""
        _assert_no_state_value_literal(
            self,
            FORGED_BATCH_MODE_EXCERPT_WITH_STEP_STATUS_WORDS,
            STATE_VALUES,
            ONCE_BOUNDARY_STATE_VALUE,
        )

    def test_step_status_vocabulary_occurs_in_a_real_pointer_document(self):
        """Non-vacuity grounding (Test Notes): `completed` / `skipped` /
        `stopped` are not merely hypothetical words invented for the
        forged sample above -- a real, stable document under
        `em-workflow/` genuinely uses them as ordinary workflow.yaml
        step-status vocabulary (D2), and this task's guard matcher
        raises nothing when run over that real prose. `batch-mode.md`
        itself does not yet use these words (it is not this document
        that is being false-positive-tested here -- that is
        `test_restates_no_state_value_shape` above -- this test proves
        the matcher's tolerance against real prose that does), so
        `implement-phase.md` grounds the proof instead."""
        real_text = _read(PLUGIN_ROOT / "references" / "implement-phase.md")
        for word in ("completed", "skipped", "stopped"):
            with self.subTest(word=word):
                self.assertIn(word, real_text)
        _assert_no_state_value_literal(
            self, real_text, STATE_VALUES, ONCE_BOUNDARY_STATE_VALUE
        )


class TestPrefixUniqueness(unittest.TestCase):
    """AC-7. The sweep walks every file under em-workflow/ via os.walk --
    never a hand-maintained allowlist (Test Notes edge case)."""

    def test_prefix_occurs_only_in_the_contract_document(self):
        offenders = []
        for path in _iter_em_workflow_files(PLUGIN_ROOT):
            if path == CONTRACT_PATH:
                continue
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            if PREFIX in text:
                offenders.append(str(path.relative_to(REPO_ROOT)))
        self.assertEqual(offenders, [], f"prefix leaked into: {offenders}")

    def test_prefix_appears_in_the_contract_document(self):
        self.assertIn(PREFIX, _read(CONTRACT_PATH))

    def test_prefix_occurs_only_inside_fenced_blocks(self):
        text = _read(CONTRACT_PATH)
        segments = text.split("```")
        outside_segments = segments[0::2]
        inside_segments = segments[1::2]
        for segment in outside_segments:
            self.assertNotIn(PREFIX, segment)
        self.assertTrue(any(PREFIX in segment for segment in inside_segments))


if __name__ == "__main__":
    unittest.main()
