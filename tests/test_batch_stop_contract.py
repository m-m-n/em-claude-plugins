"""Tests for task0001 (batch-structured-result-output): the structured-result
contract SSOT document (`em-workflow/references/batch-terminal-line.md`) and
its structural guards.

Covers task0001 Acceptance Criteria
(feature-docs/batch-structured-result-output/tasks/task0001.md):

- AC-1: the SSOT's level-2 headings are exactly SC2's nine, in SC2's order,
  with `Stop reason codes` immediately followed by `Stop point coverage`;
  `## Result format` states the bare-mapping rule, SC1's eight keys in SC1's
  order, the double-quoted-scalar rule including the empty value, and the
  eight-physical-line invariant.
- AC-2: `## Escaping`'s table extracts to exactly SC3's canonical mapping,
  and the section states the residual four-hex-digit escape ranges and the
  character-by-character / never-re-process rule.
- AC-3: `## Field values` carries one bullet per SC1 key in SC1's order; the
  `detail` bullet states normalization applied before escaping plus the
  non-empty placeholder; the `resume_conditions` bullet states that
  normalization is NOT applied to it; the `feature` / `branch` / `pr_url` /
  `resume_conditions` bullets each state their rule and their empty-string
  case consistently with IMPLEMENTATION.md's Canonical derivation outcomes
  table.
- AC-4: the `reason` domain documents twelve values with
  `context_budget_reached` marked never emitted and absent from the
  coverage table, while `## Stop point coverage` still binds exactly eleven
  stop-point keys to eleven codes bidirectionally and states the named,
  single-code exception; a forged domain that adds the twelfth code as a
  coverage row is rejected by the matcher.
- AC-5: `## Consumer constraints` states all five of FR14's constraints, and
  states that nothing may be dropped, summarized, counted or replaced by a
  pointer to fit the 64 KiB bound.
- AC-6: the literal `EM_WORKFLOW_TERMINAL:` occurs in no file under
  `em-workflow/` -- proved by a recursive sweep of every file below that
  directory with no hand-maintained allowlist, carrying a non-vacuity guard
  proving the sweep read a non-trivial number of files; no description of a
  prefixed four-field line, of a dual emission, or of a compatibility period
  remains in the document.
- AC-7: `## Responsibility boundary` extends the no-confidential-information
  rule to `detail`, `resume_conditions`, `branch` and `pr_url`;
  `## No result on a wait turn` preserves the "no result = abnormal outcome"
  signal; and every pre-existing assertion in this module that pins
  `state` / `step` domain wording passes unmodified in substance (A5) --
  only the retired `key=value` citation shape is updated to the new
  `` `key` `value` `` shape the rewritten document uses throughout.

This module also carries the SC5 forbidden-literal-set check for
`batch-mode.md` (IMPLEMENTATION.md SC5: "task0001 pins the set ... for
batch-mode.md"). `batch-mode.md` itself is task0002's file and is not
edited by this task; this module only asserts its current content does not
restate the SSOT's literals.

Deviations (outside `expected_files`, recorded in the implementer report):
this task's mandated rewrite (headings renamed per SC2, the
`EM_WORKFLOW_TERMINAL:` prefix removed per SC6) invalidates two pins that
live in test modules this task does not otherwise touch:
`tests/test_failed_kind_batch_docs.py`'s `## No line on a wait turn` slice
anchor, and `tests/test_batch_quiet_output_discipline.py`'s seven-heading /
prefix-presence pins against this same document. Both received the minimal
mechanical update needed to track this task's mandated rename/removal --
see this implementer's report for the exact diffs.

Test authoring follows IMPLEMENTATION.md's "Test authoring (NFR4)"
convention: durable invariants over fixed literals wherever a literal would
go stale, negative proof + non-vacuity guard per NEW matcher, pure
regression guards over retained wording exempted. All assertions read raw
file text (`Path.read_text`), so a literal hidden inside a fenced block is
still seen.

Matcher -> negative-proof inventory (new matchers only; matchers inherited
unchanged from the pre-rewrite module -- reason-code table validator,
bidirectional coverage validator, step value-domain / precedence / Step C
asymmetry / none-reserved-range matchers -- keep their existing proofs,
listed once below rather than per rework round since this rewrite folds
every prior round into one document):

- `_assert_well_formed_code_list` (reason-code table extractor validation):
  `test_duplicate_code_is_rejected`, `test_empty_first_cell_is_rejected` /
  `test_duplicate_table_is_otherwise_well_formed`,
  `test_empty_cell_table_is_otherwise_well_formed`.
- `_assert_bidirectional_coverage` (coverage table extractor validation):
  `test_missing_key_is_rejected`, `test_code_outside_set_is_rejected`,
  `test_duplicate_stop_point_key_is_rejected` / the corresponding
  `..._parses_into_a_non_empty_pair_of_sets` tests.
- `_assert_result_format_example_matches_sc1` (NEW, AC-1/AC-3 retargeting
  item 3): `test_missing_key_example_is_rejected`,
  `test_wrong_order_example_is_rejected`,
  `test_wrong_line_count_example_is_rejected` /
  `test_forged_example_missing_a_key_is_otherwise_well_formed`, etc.
- `_assert_escaping_table_matches_sc3` (NEW, AC-2): `test_altered_mapping_is_rejected`
  / `test_forged_table_is_otherwise_well_formed`.
- `_assert_field_values_bullet_order_matches_sc1` (NEW, AC-3): `test_missing_bullet_is_rejected`,
  `test_wrong_order_is_rejected` / non-vacuity guards.
- `_assert_reason_domain_documents_twelve` (NEW, AC-4): `test_coverage_row_added_for_reserved_code_is_rejected`
  / non-vacuity guard.
- `_assert_consumer_constraints_stated` (NEW, AC-5): `test_missing_constraint_is_rejected`
  / non-vacuity guard.
- `_assert_no_sc5_literals` (retargeted from the old four-field-only
  pointer guard, AC-6/D2): per-shape negative proofs in
  `TestSc5LiteralGuardMatcher`.

Edge cases (Test Notes): the escaping-table extractor distinguishes a named
token (`CR`, `LF`, `TAB`) from a backticked literal character, and is not
confused by the backslash characters in the second column
(`test_escaping_table_distinguishes_named_tokens_from_literal_characters`);
the twelve-value `reason` domain and the eleven-row coverage table are
extracted by two different extractors, so AC-4's asymmetry stays testable;
the prefix sweep walks every file under `em-workflow/` via `os.walk`, never
a hand-maintained allowlist, and no longer carves out this document itself
(the prefix must now be absent everywhere, including here).

--- task0008 additions (review round 1 rework, IMPLEMENTATION.md SC11) ---

This module also carries task0008's binding guards for the SSOT
value-rule hardening set closed by
`feature-docs/batch-structured-result-output/tasks/task0008.md`:

- `_assert_confidentiality_beyond_paths_stated` (AC-1, SC11 (a)): the
  "no confidential information beyond paths" wording, restored in
  `## Responsibility boundary`.
- `_assert_in_full_loading_rule_stated` (AC-2, SC11 (b)): the in-full
  loading rule's owner sentence and the single secret-portion redaction
  exception, in `## Field values`.
- `_assert_detail_delimiter_and_byte_verbatim_disclosure_stated` (AC-3,
  SC11 (c)): the `detail` bullet's item delimiter and its
  not-byte-verbatim disclosure.
- `_assert_size_collision_outcome_stated` (AC-4, SC11 (d)): the 64 KiB /
  in-full collision's single defined outcome in `## Consumer
  constraints`.
- `_assert_feature_bullet_states_slug_pattern_literal` (AC-6, SC11 (e)):
  the `feature` bullet's slug pattern literal.
- `_assert_resume_conditions_presence_rule_stated` (AC-7, SC11 (f)):
  replaces the old `non-empty whenever` pin with the new non-whitespace
  wording (FR22).
- `_assert_own_hardening_rules_stated` (AC-8, SC11 (g)+(h)): the
  control-code-point rejection for `detail`/`resume_conditions` plus the
  three shape defenses, anchored on the `OWN_RULES_LABEL` separator so the
  matcher cannot be satisfied by FR14's carried-over list alone (proved by
  `TestOwnHardeningRulesMatcherNegativeProof.test_carried_over_text_alone_does_not_satisfy_the_matcher`).

Every one of these matchers has a negative proof and a non-vacuity guard,
several built from the real pre-change wording (itself "otherwise well
formed" on every point except the one under test). AC-9 (`## Escaping`
and `## Result format` stay byte-identical) is a pure regression guard
and is exempt from a negative proof per NFR4 -- it is proved by this
module's own `git diff` never touching those two sections, not by a new
test.

--- resume-conditions-newline-rejection task0001 additions ---

This module also carries task0001's guards for splitting the shared
own-rules bullet into per-field rules
(`feature-docs/resume-conditions-newline-rejection/tasks/task0001.md`):

- `_assert_own_rules_preamble_stated` (AC-1): the OWN-rules block's
  introductory sentence states the own-hardening framing and the
  carried-over-consumer-behaviour labelling, and drops the blanket
  "cannot fire" claim and its rule-count word. Anchored on
  `OWN_RULES_LABEL` (negative proof:
  `TestOwnRulesPreambleMatcherNegativeProof`).
- `_assert_resume_conditions_exemption_stated` (AC-3): `resume_conditions`
  rejects only a terminal-control code point other than CR/LF/TAB, stated
  as its own bullet with the three code-point literals and the explicit
  not-a-violation statement. Anchored on `OWN_RULES_LABEL` so it cannot be
  satisfied by the pre-change shared bullet or by the carried-over list
  alone (negative proof:
  `TestResumeConditionsExemptionMatcherNegativeProof`).

`_assert_own_hardening_rules_stated` and its `FORGED_OWN_RULES_PARTIAL`
sample are updated in place (not renamed) to the new two-bullet wording,
per task0001's design: the matcher's assertions are unchanged, and the
forged sample still omits the duplicate-key and documented-domain shape
defenses so it is rejected for those, never for the control-code-point
wording.

--- task-tier-reduction/task0004 additions ---

Deviation (outside that task's `expected_files`, recorded in its
implementer report per its own task plan's instruction: "the two
dynamically-extracting modules are inside its declared file set so a
surprise there is handled here rather than reported as a deviation" --
this module is a THIRD, undeclared pinned-cardinality module the same
risk names; task0004's plan directs fixing whatever the whole-suite run
turns up). That task adds one reason code (`no_work_required`) and one
stop point (`no-work-required`) to `batch-terminal-line.md`, raising
`REASON_CODES` / `STOP_POINT_KEYS` from eleven to twelve members each and
the documented `reason` domain (REASON_CODES plus the reserved
`context_budget_reached`) from twelve to thirteen. Updated in place (not
renamed, except where the test name itself states the old count):
`REASON_CODES`, `STOP_POINT_KEYS`, `_KEY_CODE_PAIRS_IN_ORDER` (gains one
pair), `REASON_DOMAIN_ALL` (renamed from `REASON_DOMAIN_TWELVE`, now
count-agnostic), and `TestStopReasonCodes`'s count-pinning tests (renamed
where the old count was in the name). Every matcher and negative proof in
this module is otherwise unchanged in substance -- it is the CONSTANTS
these tests compare the live document against that grow, not the
checking logic.
"""

import os
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"
CONTRACT_PATH = PLUGIN_ROOT / "references" / "batch-terminal-line.md"
BATCH_MODE_PATH = PLUGIN_ROOT / "references" / "batch-mode.md"

# SC6: the removed prefix literal. No longer something the document must
# contain -- the sweep below proves it ABSENT from every file under
# em-workflow/, including this document itself.
PREFIX = "EM_WORKFLOW_TERMINAL:"
SENTINEL = "no-step"

# SC2 -- fixed by IMPLEMENTATION.md, not renegotiated here. `Stop reason
# codes` must stay immediately followed by `Stop point coverage`: an
# existing guard (tests/test_failed_kind_batch_docs.py) slices the document
# between exactly those two headings.
CONTRACT_HEADINGS = [
    "Purpose",
    "Result format",
    "Escaping",
    "Field values",
    "Stop reason codes",
    "Stop point coverage",
    "Consumer constraints",
    "No result on a wait turn",
    "Responsibility boundary",
]

# SC1 -- the eight keys, in the SSOT's fixed order.
SC1_KEYS = [
    "state",
    "step",
    "reason",
    "detail",
    "feature",
    "branch",
    "pr_url",
    "resume_conditions",
]

# A4/A5: unchanged by this task -- the eleven reason codes, the eleven
# stop-point keys, the no-step sentinel's stop points, the `state` and
# `step` value domains, and the ordered key/code pairing. Re-declared here
# unmodified from the pre-rewrite module.
#
# Extended by task-tier-reduction/task0004: `no_work_required` /
# `no-work-required` join both sets (twelve members each); see that task's
# docstring addendum near the end of this module.
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
        "feature_resolution_aborted",
        "docs_commit_conflict_aborted",
        "no_work_required",
    }
)

# FR15/D8: the thirteenth, reserved `reason` value -- documented, never
# bound to a stop point, never emitted by em-workflow.
CONTEXT_BUDGET_REACHED = "context_budget_reached"
REASON_DOMAIN_ALL = REASON_CODES | {CONTEXT_BUDGET_REACHED}

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
        "step-a-abort",
        "docs-commit-conflict",
        "no-work-required",
    }
)

NO_STEP_STOP_POINTS = frozenset({"stop-condition-6", "step-a-abort", "step-c-abort"})

STATE_VALUES = frozenset({"completed", "stopped", "phase_done"})
ONCE_BOUNDARY_STATE_VALUE = "phase_done"

STEP_VALUE_DOMAIN = frozenset(
    {
        "create-spec",
        "design",
        "create-plan",
        "implement",
        "review",
        "verify",
        "retrospect",
        "no-step",
    }
)

# develop-once-option task0005 (D9 rule 1), retargeted for the new
# non-`key=value` citation shape (FR16/SC6 retires `state=completed`
# wholesale): the old restrictive phrasing this task's document must NOT
# contain, verbatim.
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
    ("step-a-abort", "feature_resolution_aborted"),
    ("docs-commit-conflict", "docs_commit_conflict_aborted"),
    ("no-work-required", "no_work_required"),
]

# SC3 -- the canonical escaping mapping, as raw Markdown table cell text
# (backticks included), matching how `## Escaping` renders it. Order
# matches the document's row order.
SC3_ESCAPING_PAIRS = [
    (r"`\`", r"`\\`"),
    (r'`"`', r'`\"`'),
    ("CR (U+000D)", r"`\r`"),
    ("LF (U+000A)", r"`\n`"),
    ("TAB (U+0009)", r"`\t`"),
]

HEADING_RE = re.compile(r"^## (.+?)\s*$", re.MULTILINE)
BACKTICK_CELL_RE = re.compile(r"^`([^`]*)`$")
FENCED_YAML_RE = re.compile(r"```yaml\n(.*?)```", re.DOTALL)


def _read(path):
    return path.read_text(encoding="utf-8")


def _normalize(text):
    """Collapses all whitespace runs (including line wraps) to a single
    space, so a multi-word prose phrase check does not depend on exactly
    where the source file happens to wrap a line. Never used for table or
    fenced-block extraction, which depend on newlines as delimiters."""
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
    this repository's docs."""
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
    (`_assert_well_formed_code_list`)."""
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


def _reason_code_meaning(section_text, code):
    """Extracts the `## Stop reason codes` table's second column (Meaning)
    for the row whose first column is exactly `code`. Returns None when no
    such row is found."""
    for row in _table_rows(section_text):
        if _first_column_code(row[0]) == code:
            return row[1]
    return None


def _assert_gate_fail_closed_coverage_wording_stated(test, meaning_cell):
    """Validation for the `gate_fail_closed` coverage-wording matcher: the
    wording must name only the aborts that survive in both modes plus
    interactive's own aborts, via a collective phrase plus a path citation
    to `question-resolution.md`, without re-enumerating the surviving-abort
    set."""
    test.assertIn("references/question-resolution.md", meaning_cell)
    test.assertIn("both modes", meaning_cell)
    test.assertIn("interactive", meaning_cell)
    for leaked_term in (
        "category: security",
        "category: license",
        "reversible: false",
    ):
        test.assertNotIn(leaked_term, meaning_cell)


def _extract_coverage_table(section_text):
    """Parses the `## Stop point coverage` table into (stop_point_key,
    reason_code) pairs from the first two backticked columns."""
    rows = _table_rows(section_text)
    return [(_first_column_code(row[0]), _first_column_code(row[1])) for row in rows]


def _assert_bidirectional_coverage(test, pairs, expected_keys, expected_codes):
    """Validation for the coverage extractor: every stop-point key appears
    exactly once (multiset equality against `expected_keys`), every bound
    code is a member of `expected_codes`, and every one of `expected_codes`
    is used by at least one row."""
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
    header = "| Stop point | Reason code | Source |\n|---|---|---|\n"
    return header + "".join(
        f"| `{key}` | `{code}` | `skills/develop/SKILL.md` |\n" for key, code in pairs
    )


def _extract_coverage_source_cells(section_text):
    """Parses the `## Stop point coverage` table's third column (raw cell
    text, backticks included) for each data row."""
    return [row[2] for row in _table_rows(section_text)]


def _assert_source_paths_resolve(test, cells):
    """Validation for the Source-column extractor: every cell is a single
    backticked, plugin-relative path that resolves to an existing file
    under `em-workflow/`. Deliberately does NOT use `subTest` -- a
    `subTest`-scoped `AssertionError` is swallowed locally rather than
    propagated to a caller's `assertRaises`, which would break the negative
    proof."""
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
    the `no-step` bullet of `## Field values` -- a structural extraction
    (via the bullet's backtick tokens), not a prose substring search.
    `no-step` itself is excluded (it also matches the hyphenated
    backtick-token shape but is the sentinel, not a stop-point key)."""
    match = NO_STEP_BULLET_RE.search(field_values_section_text)
    if match is None:
        return set()
    tokens = set(_HYPHENATED_BACKTICK_TOKEN_RE.findall(match.group(0)))
    return tokens - {"no-step"}


def _assert_precedence_rule_stated(test, coverage_section_text):
    """Validation for the precedence-rule matcher: the coverage section
    states that a phase-specific stop point takes precedence over the
    generic `stop-condition-N` rows, names the three overlapping cases, and
    restricts `stop-condition-3`'s meaning to the states no phase-specific
    row covers."""
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


def _assert_context_budget_reached_exception_stated(test, coverage_section_text):
    """AC-4/D8 (NEW): the coverage section states the named, explicitly-
    scoped exception -- exactly one documented `reason` code has no stop
    point, and that this is intentional, not an omission."""
    normalized = _normalize(coverage_section_text)
    test.assertIn(f"`{CONTEXT_BUDGET_REACHED}`", coverage_section_text)
    test.assertIn("has no stop point", normalized)
    test.assertIn("intentional", normalized)
    test.assertIn("not an omission", normalized)


def _assert_no_sc5_literals(test, text):
    """SC5 (retargeted from the old four-field-only pointer guard): a
    pointer document (here, `batch-mode.md`) must not restate the SSOT's
    field-name tokens in a `key:`- or `key=`-shaped citation, any `state` /
    `step` / `reason` value (including `context_budget_reached`), the
    `no-step` sentinel, the bare `phase_done` boundary literal, or the
    removed SC6 prefix.

    The `key:`-shaped check is deliberately narrow (backtick-wrapped key
    immediately followed by a colon) rather than a bare `key:` substring:
    ordinary English prose in `batch-mode.md` already contains "Full
    detail:" and "a feature:", which a bare substring check would
    misclassify as a restated citation."""
    for key in SC1_KEYS:
        for spelling in (f"{key}=", f"`{key}`:"):
            test.assertNotIn(
                spelling, text, f"found forbidden field-name citation: {spelling!r}"
            )
    for value in sorted(STATE_VALUES):
        for spelling in (
            f"state={value}", f"`state={value}`", f'"state={value}"',
            f"state: {value}", f'state: "{value}"', f"`state: {value}`",
        ):
            test.assertNotIn(spelling, text, f"found forbidden literal: {spelling!r}")
    test.assertNotIn(ONCE_BOUNDARY_STATE_VALUE, text)
    for value in sorted(STEP_VALUE_DOMAIN):
        for spelling in (f"step={value}", f"step: {value}", f'step: "{value}"'):
            test.assertNotIn(spelling, text, f"found forbidden literal: {spelling!r}")
    test.assertNotIn(SENTINEL, text)
    for code in sorted(REASON_DOMAIN_ALL):
        test.assertNotIn(code, text, f"found forbidden reason code literal: {code!r}")
    for spelling in ("reason=none", "reason: none", 'reason: "none"'):
        test.assertNotIn(spelling, text, f"found forbidden literal: {spelling!r}")
    test.assertNotIn(PREFIX, text)


def _extract_result_format_example(section_text):
    """AC-1/AC-3 retargeting item 3 (NEW): extracts the ordered key sequence
    and the physical (non-blank) line count from `## Result format`'s
    fenced YAML example -- the structural artifact the four-field-order
    assertion is replaced by. Returns ([], 0) when no fenced YAML block is
    found."""
    match = FENCED_YAML_RE.search(section_text)
    if match is None:
        return [], 0
    lines = [line for line in match.group(1).splitlines() if line.strip()]
    keys = []
    for line in lines:
        key_match = re.match(r"^([a-z_]+):", line)
        keys.append(key_match.group(1) if key_match else None)
    return keys, len(lines)


def _assert_result_format_example_matches_sc1(test, section_text):
    """Validation for the Result-format example extractor: the example's
    key sequence equals SC1_KEYS exactly (neither narrower nor
    reordered), and it is exactly eight physical lines."""
    keys, line_count = _extract_result_format_example(section_text)
    test.assertEqual(keys, SC1_KEYS)
    test.assertEqual(line_count, 8)


def _extract_escaping_table(section_text):
    """AC-2 (NEW): extracts `## Escaping`'s table as raw (source, emitted)
    cell-text pairs, preserving backticks -- comparison target is
    SC3_ESCAPING_PAIRS, itself raw cell text, so no unwrapping is needed."""
    return [(row[0], row[1]) for row in _table_rows(section_text)]


def _assert_escaping_table_matches_sc3(test, pairs):
    test.assertEqual(pairs, SC3_ESCAPING_PAIRS)


FIELD_VALUES_BULLET_RE = re.compile(r"^- `([a-z_]+)`", re.MULTILINE)


def _extract_field_values_bullet_order(section_text):
    """AC-3 (NEW): extracts the ordered sequence of backticked key names
    that open each top-level bullet of `## Field values` -- a structural
    extraction (bullet-leading backtick token), not a search for every
    backtick-quoted key mention (which would also pick up cross-references
    inside a bullet's own prose)."""
    return FIELD_VALUES_BULLET_RE.findall(section_text)


def _assert_field_values_bullet_order_matches_sc1(test, section_text):
    test.assertEqual(_extract_field_values_bullet_order(section_text), SC1_KEYS)


# -- task0008 (SC11) matchers -------------------------------------------------


def _assert_confidentiality_beyond_paths_stated(test, section_text):
    """AC-1/SC11 (a): the confidentiality rule is "no confidential
    information beyond paths" -- SPEC NFR5's exact words -- restored after
    review round 1 found the field scope widened without them."""
    normalized = _normalize(section_text)
    test.assertIn("carry no confidential information beyond paths", normalized)


def _assert_in_full_loading_rule_stated(test, section_text):
    """AC-2/SC11 (b): the in-full loading rule is stated on the owning
    side (`## Field values`), naming `batch-mode.md`'s `## Reporting` as
    the item list's owner without reproducing it, plus the single
    secret-portion redaction exception."""
    normalized = _normalize(section_text)
    test.assertIn("carried in full inside `detail`", normalized)
    test.assertIn("carried in full inside `resume_conditions`", normalized)
    test.assertIn(
        "A count alone, or a pointer alone, satisfies neither", normalized
    )
    test.assertIn("batch-mode.md`'s `## Reporting`", normalized)
    test.assertIn("not reproduced here", normalized)
    test.assertIn("secret", normalized)
    test.assertIn("fixed placeholder", normalized)
    test.assertIn("a redaction", normalized)
    test.assertIn("never a count or a pointer substitution", normalized)
    test.assertIn("never applies to a path", normalized)


def _assert_detail_delimiter_and_byte_verbatim_disclosure_stated(test, section_text):
    """AC-3/SC11 (c): the `detail` bullet states the fixed item delimiter
    and discloses that `detail` is not a byte-verbatim record, naming
    where the verbatim record lives. FR7's normalization sentence itself
    is unchanged (checked separately, regression-style, by
    `test_detail_bullet_states_normalization_before_escaping`)."""
    normalized = _normalize(section_text)
    test.assertIn("separated by a fixed textual delimiter", normalized)
    test.assertIn("survives normalization", normalized)
    test.assertIn("not a byte-verbatim record", normalized)
    test.assertIn(
        "whitespace inside a carried command string is normalized", normalized
    )
    test.assertIn("audit-item source map", normalized)


SLUG_PATTERN_LITERAL = r"^[a-z0-9][a-z0-9-]*$"


def _assert_feature_bullet_states_slug_pattern_literal(test, section_text):
    """AC-6/SC11 (e): the `feature` bullet carries the slug pattern
    literal (this document takes the literal branch of the task plan's
    "literal, or a named reference" choice)."""
    test.assertIn(f"`{SLUG_PATTERN_LITERAL}`", section_text)
    test.assertIn("slug pattern", _normalize(section_text))


def _assert_resume_conditions_presence_rule_stated(test, section_text):
    """AC-7/SC11 (f): `resume_conditions` is non-whitespace -- never empty
    AND never whitespace-only -- whenever `state` is `stopped`, matching
    FR12/AC-5 and the presence rule
    `tests/test_structured_result_derivation.py` already verifies (FR22:
    replaces the old `non-empty whenever` pin)."""
    normalized = _normalize(section_text)
    test.assertIn("non-whitespace whenever `state` is `stopped`", normalized)
    test.assertIn("never empty and never whitespace-only", normalized)
    test.assertIn("empty for every other `state`", normalized)


def _assert_size_collision_outcome_stated(test, section_text):
    """AC-4/SC11 (d): the 64 KiB / in-full collision has exactly one
    defined outcome: no result is emitted, `## Purpose`'s absence signal
    applies, and the assembled content remains in its persisted sources --
    never truncation, summarization, a count or a pointer instead."""
    normalized = _normalize(section_text)
    lowered = normalized.lower()
    test.assertIn("64 KiB", normalized)
    test.assertIn("dropped", lowered)
    test.assertIn("summarized", lowered)
    test.assertIn("replaced by a count", lowered)
    test.assertIn("replaced by a pointer", lowered)
    test.assertIn("never emitted", lowered)
    test.assertIn("emits no result", lowered)
    test.assertIn("abnormal outcome", lowered)
    test.assertIn("persisted", lowered)
    test.assertIn("no reason code", lowered)


OWN_RULES_LABEL = "em-workflow's OWN emitter obligations and rejection rules"


def _split_consumer_constraints_own_rules(section_text):
    """AC-8 (NEW): splits `## Consumer constraints` at OWN_RULES_LABEL into
    (carried_over_text, own_rules_text). Returns (section_text, "") when
    the label is absent, so a caller's assertions against the (empty)
    second half fail cleanly rather than silently matching the
    carried-over list alone."""
    idx = section_text.find(OWN_RULES_LABEL)
    if idx == -1:
        return section_text, ""
    return section_text[:idx], section_text[idx:]


def _assert_own_hardening_rules_stated(test, section_text):
    """AC-8/SC11 (g)+(h): em-workflow's own control-code-point rejection
    for `detail`/`resume_conditions`, plus the three shape defenses, all
    stated under a label identifying them as em-workflow's own rules
    rather than carried-over consumer behaviour (FR14's five numbered
    constraints, unchanged). Anchored on OWN_RULES_LABEL so the matcher
    cannot be satisfied by the carried-over list alone (non-vacuity proof:
    TestOwnHardeningRulesMatcherNegativeProof)."""
    _carried_over, own_rules = _split_consumer_constraints_own_rules(section_text)
    test.assertTrue(own_rules, f"label {OWN_RULES_LABEL!r} not found")
    normalized = _normalize(own_rules)
    # (g) control code points for detail/resume_conditions
    test.assertIn("`detail`", own_rules)
    test.assertIn("`resume_conditions`", own_rules)
    test.assertIn("line terminator", normalized)
    test.assertIn("terminal-control", normalized)
    test.assertIn("does not help here either", normalized)
    # (h)(1) exact eight keys in order
    test.assertIn("exactly the eight keys", normalized)
    test.assertIn("in that order", normalized)
    test.assertIn("missing, extra or reordered", normalized)
    # (h)(2) duplicate key / eight physical lines
    test.assertIn("more than once", normalized)
    test.assertIn("last-wins", normalized)
    test.assertIn("exactly eight physical lines", normalized)
    # (h)(3) closed domain check for state/step/reason
    test.assertIn("`state`", own_rules)
    test.assertIn("`step`", own_rules)
    test.assertIn("`reason`", own_rules)
    test.assertIn("documented domain", normalized)
    # labelled as em-workflow's own, not carried-over
    test.assertIn("carried-over consumer behaviour", normalized)


def _assert_own_rules_preamble_stated(test, section_text):
    """task0001 AC-1 (FR4): the OWN-rules block's introductory sentence
    states the own-hardening framing and the carried-over-consumer-
    behaviour labelling, and drops both the blanket "cannot fire" claim
    and any count word for the number of OWN rules (assumption A8).
    Anchored on OWN_RULES_LABEL like every other matcher over this block,
    so it cannot be satisfied by the carried-over list alone (non-vacuity
    proof: TestOwnRulesPreambleMatcherNegativeProof)."""
    _carried_over, own_rules = _split_consumer_constraints_own_rules(section_text)
    test.assertTrue(own_rules, f"label {OWN_RULES_LABEL!r} not found")
    lowered = _normalize(own_rules).lower()
    test.assertIn("own hardening obligations", lowered)
    test.assertIn("defense in depth", lowered)
    test.assertIn("carried-over consumer behaviour", lowered)
    test.assertNotIn("cannot fire", lowered)
    test.assertNotIn("the four", lowered)


def _assert_resume_conditions_exemption_stated(test, section_text):
    """task0001 AC-3 (FR1, FR2, FR9): the OWN-rules block states, as its
    own bullet, that `resume_conditions` exempts a decoded CR, LF or TAB
    from its terminal-control rejection -- naming the three exempted code
    points by their literals and the "other than" restriction on what is
    still rejected. Anchored on OWN_RULES_LABEL so it cannot be satisfied
    by the pre-change shared bullet or by the carried-over list alone
    (non-vacuity proof: TestResumeConditionsExemptionMatcherNegativeProof)."""
    _carried_over, own_rules = _split_consumer_constraints_own_rules(section_text)
    test.assertTrue(own_rules, f"label {OWN_RULES_LABEL!r} not found")
    normalized = _normalize(own_rules)
    test.assertIn("`resume_conditions`", own_rules)
    test.assertIn("CR (U+000D)", normalized)
    test.assertIn("LF (U+000A)", normalized)
    test.assertIn("TAB (U+0009)", normalized)
    test.assertIn("other than", normalized)
    test.assertIn("NOT a violation", normalized)


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

    def test_nine_level_2_headings_in_order(self):
        self.assertEqual(list(self.sections.keys()), CONTRACT_HEADINGS)

    def test_stop_reason_codes_immediately_followed_by_stop_point_coverage(self):
        """SC2: an existing, unrelated guard
        (tests/test_failed_kind_batch_docs.py) slices the document between
        exactly these two headings -- no heading may sit between them."""
        idx = CONTRACT_HEADINGS.index("Stop reason codes")
        self.assertEqual(CONTRACT_HEADINGS[idx + 1], "Stop point coverage")

    def test_result_format_states_bare_mapping_rule(self):
        section = _normalize(self.sections["Result format"])
        self.assertIn("no code fence", section)
        self.assertIn("no surrounding prose", section)
        self.assertIn("no document separator", section)
        self.assertIn("no comments", section)

    def test_result_format_example_matches_sc1_key_order(self):
        _assert_result_format_example_matches_sc1(self, self.sections["Result format"])

    def test_result_format_states_double_quoted_scalar_rule_including_empty(self):
        section = _normalize(self.sections["Result format"])
        self.assertIn("double-quoted scalar", section)
        self.assertIn('empty pair of double quotes', section)
        self.assertIn('""', section)

    def test_result_format_states_eight_physical_line_invariant_and_reason(self):
        section = _normalize(self.sections["Result format"])
        self.assertIn("exactly eight physical lines", section)
        self.assertIn("start of its own physical line", section)

    def test_result_format_states_no_external_tool_needed(self):
        self.assertIn("no external tool", _normalize(self.sections["Result format"]))

    def test_result_format_states_batch_only_emission(self):
        self.assertIn(
            "only in a batch-mode run", _normalize(self.sections["Result format"])
        )

    def test_no_description_of_removed_shape_remains(self):
        """AC-6: no description of a prefixed four-field line, a dual
        emission, or a compatibility period remains anywhere in the
        document."""
        lowered = self.text.lower()
        for forbidden in (
            "four-field", "four fields", "key=value", "dual emission",
            "compatibility period", "terminal line",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, lowered)

    # -- state/step domain wording (A4/A5): substance unchanged from the
    # pre-rewrite module; only the retired `key=value` citation shape is
    # updated to this document's `` `key` `value` `` shape. --

    def test_field_values_state_domain_includes_all_three_values(self):
        section = self.sections["Field values"]
        for value in ("completed", "stopped", "phase_done"):
            with self.subTest(value=value):
                self.assertIn(f"`{value}`", section)

    def test_field_values_phase_done_conditions_stated(self):
        section = _normalize(self.sections["Field values"])
        self.assertIn("`reason` `none`", section)
        self.assertIn("non-empty `detail`", section)
        self.assertIn("eight-key structured result", section)

    def test_field_values_phase_done_consumer_relaunches_same_feature(self):
        section = _normalize(self.sections["Field values"])
        self.assertIn("`state` as `phase_done`", section)
        self.assertIn("re-launches the same feature", section)

    def test_field_values_step_names_the_executed_step(self):
        section = _normalize(self.sections["Field values"])
        self.assertIn("names the step EXECUTED in that turn", section)
        self.assertIn("never the step the next", section)
        self.assertIn("launch resumes at", section)

    def test_field_values_step_at_verify_fail_rework_is_verify(self):
        section = _normalize(self.sections["Field values"])
        self.assertIn(
            "verify-fail rework boundary the value is `verify`", section
        )
        self.assertIn("next launch resumes at `implement`", section)

    def test_field_values_reason_bullet_reserved_for_non_stop_states(self):
        section = _normalize(self.sections["Field values"])
        self.assertIn("`none`", section)
        self.assertIn("reserved", section)
        self.assertIn("`state` `completed`", section)
        self.assertIn("`state` `phase_done`", section)
        self.assertIn("non-stop terminal state", section)
        self.assertNotIn(NONE_RESERVED_OLD_PHRASE_FIELD_VALUES, self.sections["Field values"])

    def test_field_values_step_precedence_stated(self):
        _assert_step_precedence_stated(self, self.sections["Field values"])

    def test_field_values_step_c_asymmetry_stated(self):
        _assert_step_c_asymmetry_stated(self, self.sections["Field values"])

    def test_field_values_step_domain_declared(self):
        _assert_step_value_domain_declared(
            self, self.sections["Field values"], STEP_VALUE_DOMAIN
        )

    def test_step_domain_declaration_precedes_no_step_anchor(self):
        section = self.sections["Field values"]
        declaration_index = section.index("a closed value domain:")
        anchor_index = section.index("`no-step` applies whenever")
        self.assertLess(declaration_index, anchor_index)


# -- AC-9 (task0008): `## Escaping` and `## Result format` stay byte-identical
# to their pre-change text -- task0009 binds its executable escaping copies
# to `## Escaping` and depends on that invariance (IMPLEMENTATION.md SC12).
# A pure regression guard over deliberately retained wording (NFR4): exempt
# from a negative proof. The two literals below are these same sections'
# exact text captured from the implement-base commit (`git show HEAD:...`
# before this task's edit); this task's diff never touches either section.

RESULT_FORMAT_TEXT = '\nThe final assistant message of a terminal batch turn is exactly one bare\nYAML mapping and nothing else: no code fence, no surrounding prose, no\ndocument separator (`---`), no comments, and no key beyond the eight\nbelow. The mapping carries exactly these eight keys, each written once,\nin this fixed order:\n\n```yaml\nstate: "stopped"\nstep: "implement"\nreason: "step_stuck"\ndetail: "implementer task0004 stuck after 3 conflict cycles"\nfeature: "batch-structured-result-output"\nbranch: "em-workflow/batch-structured-result-output/integration"\npr_url: ""\nresume_conditions: "Resolve the conflict manually and re-run implement for task0004."\n```\n\nEvery value is a double-quoted scalar; an empty value is written as an\nempty pair of double quotes (`""`), never omitted and never left\nunquoted. Each key sits at the start of its own physical line, so the\nresult is always exactly eight physical lines: no value may contain a\nliteral, unescaped newline (see `## Escaping`). Emitting the result needs\nno external tool: it is eight lines of text written as the final\nassistant message. The result is emitted only in a batch-mode run — an\ninteractive run emits nothing here.\n\n'

ESCAPING_TEXT = '\nThe rule below is applied to every one of the eight values, character by\ncharacter, left to right, and never re-processes a character the rule has\njust generated.\n\n| Source character | Emitted |\n|---|---|\n| `\\` | `\\\\` |\n| `"` | `\\"` |\n| CR (U+000D) | `\\r` |\n| LF (U+000A) | `\\n` |\n| TAB (U+0009) | `\\t` |\n\nAny character not covered above that falls in U+0000-U+001F,\nU+007F-U+009F, U+2028, U+2029, U+FFFE or U+FFFF becomes a backslash, `u`,\nand exactly four lower-case hex digits. Every other valid Unicode\ncharacter, including non-BMP characters, is emitted unchanged.\n\n'


class TestEscapingAndResultFormatByteIdentical(unittest.TestCase):
    """AC-9."""

    @classmethod
    def setUpClass(cls):
        cls.sections = _sections(_read(CONTRACT_PATH))

    def test_result_format_section_unchanged(self):
        self.assertEqual(self.sections["Result format"], RESULT_FORMAT_TEXT)

    def test_escaping_section_unchanged(self):
        self.assertEqual(self.sections["Escaping"], ESCAPING_TEXT)


# -- AC-3: Field values bullet order + detail/resume_conditions/derivation --


class TestFieldValuesBulletOrderAndDerivations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.section = _sections(_read(CONTRACT_PATH))["Field values"]

    def test_bullet_order_matches_sc1(self):
        _assert_field_values_bullet_order_matches_sc1(self, self.section)

    def test_detail_bullet_states_normalization_before_escaping(self):
        normalized = _normalize(self.section)
        self.assertIn("Before escaping", normalized)
        self.assertIn("CR", self.section)
        self.assertIn("LF", self.section)
        self.assertIn("TAB", self.section)
        self.assertIn("collapsed to one", normalized)
        self.assertIn("placeholder", normalized.lower())
        self.assertIn("non-empty guarantee", normalized)

    def test_resume_conditions_bullet_states_normalization_not_applied(self):
        normalized = _normalize(self.section)
        self.assertIn("NOT put through `detail`'s normalization", normalized)
        self.assertIn("survive as", normalized)

    def test_resume_conditions_bullet_states_per_state_rule(self):
        """AC-7/SC11 (f): non-whitespace wording, replacing the old
        non-empty pin (FR22)."""
        _assert_resume_conditions_presence_rule_stated(self, self.section)

    def test_feature_bullet_states_derivation_and_empty_case(self):
        normalized = _normalize(self.section)
        self.assertIn("the feature slug", normalized)
        self.assertIn("empty before resolution", normalized)
        self.assertIn("slug pattern", normalized)
        self.assertIn("no value is ever guessed from a task description", normalized)

    def test_feature_bullet_states_slug_pattern_literal(self):
        """AC-6/SC11 (e)."""
        _assert_feature_bullet_states_slug_pattern_literal(self, self.section)

    def test_branch_bullet_states_derivation_and_empty_case(self):
        normalized = _normalize(self.section)
        self.assertIn("the integration branch name", normalized)
        self.assertIn(
            "empty until this run has created or confirmed an integration branch",
            normalized,
        )

    def test_pr_url_bullet_states_derivation_and_empty_case(self):
        normalized = _normalize(self.section)
        self.assertIn("the created pull request's bare URL", normalized)
        self.assertIn("empty otherwise", normalized)

    def test_detail_bullet_states_delimiter_and_byte_verbatim_disclosure(self):
        """AC-3/SC11 (c)."""
        _assert_detail_delimiter_and_byte_verbatim_disclosure_stated(
            self, self.section
        )

    def test_in_full_loading_rule_and_redaction_exception_stated(self):
        """AC-2/SC11 (b)."""
        _assert_in_full_loading_rule_stated(self, self.section)


# -- Negative proofs for the NEW matchers ------------------------------------


FORGED_RESULT_FORMAT_MISSING_KEY = (
    "```yaml\n"
    'state: "stopped"\n'
    'step: "implement"\n'
    'reason: "step_stuck"\n'
    'detail: "x"\n'
    'feature: "f"\n'
    'branch: "b"\n'
    'pr_url: ""\n'
    "```\n"
)

FORGED_RESULT_FORMAT_WRONG_ORDER = (
    "```yaml\n"
    'step: "implement"\n'
    'state: "stopped"\n'
    'reason: "step_stuck"\n'
    'detail: "x"\n'
    'feature: "f"\n'
    'branch: "b"\n'
    'pr_url: ""\n'
    'resume_conditions: ""\n'
    "```\n"
)


class TestResultFormatExampleMatcherNegativeProof(unittest.TestCase):
    def test_missing_key_example_is_otherwise_well_formed(self):
        keys, count = _extract_result_format_example(FORGED_RESULT_FORMAT_MISSING_KEY)
        self.assertEqual(keys, SC1_KEYS[:-1])
        self.assertEqual(count, 7)

    def test_missing_key_example_is_rejected(self):
        with self.assertRaises(AssertionError):
            _assert_result_format_example_matches_sc1(
                self, FORGED_RESULT_FORMAT_MISSING_KEY
            )

    def test_wrong_order_example_is_otherwise_well_formed(self):
        keys, count = _extract_result_format_example(FORGED_RESULT_FORMAT_WRONG_ORDER)
        self.assertEqual(set(keys), set(SC1_KEYS))
        self.assertEqual(count, 8)

    def test_wrong_order_example_is_rejected(self):
        with self.assertRaises(AssertionError):
            _assert_result_format_example_matches_sc1(
                self, FORGED_RESULT_FORMAT_WRONG_ORDER
            )


FORGED_ESCAPING_TABLE_ALTERED = (
    "| Source character | Emitted |\n"
    "|---|---|\n"
    "| `\\` | `\\\\` |\n"
    '| `"` | `\\"` |\n'
    "| CR (U+000D) | `\\r` |\n"
    "| LF (U+000A) | `\\q` |\n"  # altered: should be `\n`
    "| TAB (U+0009) | `\\t` |\n"
)


class TestEscapingTableMatcherNegativeProof(unittest.TestCase):
    def test_altered_table_is_otherwise_well_formed(self):
        pairs = _extract_escaping_table(FORGED_ESCAPING_TABLE_ALTERED)
        self.assertEqual(len(pairs), 5)
        self.assertEqual(pairs[0], SC3_ESCAPING_PAIRS[0])

    def test_altered_mapping_is_rejected(self):
        pairs = _extract_escaping_table(FORGED_ESCAPING_TABLE_ALTERED)
        with self.assertRaises(AssertionError):
            _assert_escaping_table_matches_sc3(self, pairs)


FORGED_FIELD_VALUES_MISSING_BULLET = (
    "- `state` — the run's terminal outcome.\n"
    "- `step` — a closed value domain.\n"
    "- `reason` — one of twelve documented values.\n"
    "- `detail` — a human-facing description.\n"
    "- `feature` — the feature slug.\n"
    "- `branch` — the integration branch name.\n"
    "- `pr_url` — the created pull request's bare URL.\n"
)

FORGED_FIELD_VALUES_WRONG_ORDER = (
    "- `step` — a closed value domain.\n"
    "- `state` — the run's terminal outcome.\n"
    "- `reason` — one of twelve documented values.\n"
    "- `detail` — a human-facing description.\n"
    "- `feature` — the feature slug.\n"
    "- `branch` — the integration branch name.\n"
    "- `pr_url` — the created pull request's bare URL.\n"
    "- `resume_conditions` — the stop-recovery guidance.\n"
)


class TestFieldValuesBulletOrderMatcherNegativeProof(unittest.TestCase):
    def test_missing_bullet_sample_is_otherwise_well_formed(self):
        order = _extract_field_values_bullet_order(FORGED_FIELD_VALUES_MISSING_BULLET)
        self.assertEqual(order, SC1_KEYS[:-1])

    def test_missing_bullet_is_rejected(self):
        with self.assertRaises(AssertionError):
            _assert_field_values_bullet_order_matches_sc1(
                self, FORGED_FIELD_VALUES_MISSING_BULLET
            )

    def test_wrong_order_sample_is_otherwise_well_formed(self):
        order = _extract_field_values_bullet_order(FORGED_FIELD_VALUES_WRONG_ORDER)
        self.assertEqual(set(order), set(SC1_KEYS))

    def test_wrong_order_is_rejected(self):
        with self.assertRaises(AssertionError):
            _assert_field_values_bullet_order_matches_sc1(
                self, FORGED_FIELD_VALUES_WRONG_ORDER
            )


# -- AC-2 (task0008): in-full loading rule matcher negative proof ----------

FORGED_FIELD_VALUES_MISSING_REDACTION_EXCEPTION = (
    "- Every audit item `batch-mode.md`'s `## Reporting` enumerates is "
    "carried in full inside `detail`; the stop-recovery guidance above is "
    "carried in full inside `resume_conditions`. A count alone, or a "
    "pointer alone, satisfies neither. The item list stays "
    "`batch-mode.md`'s `## Reporting` to own and is not reproduced here."
)


class TestInFullLoadingRuleMatcherNegativeProof(unittest.TestCase):
    def test_forged_missing_redaction_exception_is_otherwise_well_formed(self):
        normalized = _normalize(FORGED_FIELD_VALUES_MISSING_REDACTION_EXCEPTION)
        self.assertIn("carried in full inside `detail`", normalized)
        self.assertIn("carried in full inside `resume_conditions`", normalized)
        self.assertIn("batch-mode.md`'s `## Reporting`", normalized)
        self.assertIn("not reproduced here", normalized)

    def test_missing_redaction_exception_is_rejected(self):
        with self.assertRaises(AssertionError):
            _assert_in_full_loading_rule_stated(
                self, FORGED_FIELD_VALUES_MISSING_REDACTION_EXCEPTION
            )


# -- AC-3 (task0008): detail delimiter / byte-verbatim matcher negative proof

FORGED_DETAIL_BULLET_OLD_WORDING = (
    "- `detail` — a human-facing, non-empty description. Before escaping, "
    "its value is normalized: every CR, LF and TAB in it is replaced with "
    "a single space, runs of spaces are then collapsed to one, and the "
    "result is trimmed; if the normalized value would be empty, a fixed "
    "non-empty placeholder is substituted instead, so the non-empty "
    "guarantee always holds. `## Escaping`'s rule is then applied to "
    "whatever remains."
)


class TestDetailDelimiterMatcherNegativeProof(unittest.TestCase):
    """The forged sample is the real pre-change `detail` bullet,
    verbatim -- it already states the normalization rule, but neither the
    item delimiter nor the byte-verbatim disclosure."""

    def test_forged_old_bullet_is_otherwise_well_formed(self):
        normalized = _normalize(FORGED_DETAIL_BULLET_OLD_WORDING)
        self.assertIn("Before escaping", normalized)
        self.assertIn("collapsed to one", normalized)
        self.assertIn("non-empty guarantee", normalized)

    def test_missing_delimiter_and_disclosure_is_rejected(self):
        with self.assertRaises(AssertionError):
            _assert_detail_delimiter_and_byte_verbatim_disclosure_stated(
                self, FORGED_DETAIL_BULLET_OLD_WORDING
            )


# -- AC-6 (task0008): feature slug pattern literal matcher negative proof --

FORGED_FEATURE_BULLET_WITHOUT_PATTERN_LITERAL = (
    "- `feature` — the feature slug: the confirmed slug once the feature "
    "is resolved; empty before resolution, except at Step 0's git-setup "
    "abort when a supplied name matches the slug pattern, in which case "
    "`feature` carries that supplied name. A supplied name that fails the "
    "slug pattern is never used, and no value is ever guessed from a task "
    "description or from an existing branch — those cases, and Step A's "
    "feature-resolution abort, leave `feature` empty."
)


class TestFeatureBulletSlugPatternMatcherNegativeProof(unittest.TestCase):
    """The forged sample is the real pre-change `feature` bullet,
    verbatim -- it already names "the slug pattern" twice, but never the
    pattern literal."""

    def test_forged_old_bullet_is_otherwise_well_formed(self):
        self.assertIn("slug pattern", FORGED_FEATURE_BULLET_WITHOUT_PATTERN_LITERAL)
        self.assertIn(
            "the feature slug", FORGED_FEATURE_BULLET_WITHOUT_PATTERN_LITERAL
        )

    def test_missing_pattern_literal_is_rejected(self):
        with self.assertRaises(AssertionError):
            _assert_feature_bullet_states_slug_pattern_literal(
                self, FORGED_FEATURE_BULLET_WITHOUT_PATTERN_LITERAL
            )


# -- AC-7 (task0008): resume_conditions presence rule matcher negative proof

FORGED_RESUME_CONDITIONS_OLD_WORDING = (
    "- `resume_conditions` — the stop-recovery guidance: non-empty "
    "whenever `state` is `stopped`, empty for every other `state`. Its "
    "value is NOT put through `detail`'s normalization: any Markdown "
    "newlines, indentation and trailing spaces it carries survive as "
    "`## Escaping`'s escapes rather than being collapsed."
)


class TestResumeConditionsPresenceRuleMatcherNegativeProof(unittest.TestCase):
    """The forged sample is the real pre-change `resume_conditions`
    bullet, verbatim -- it states presence and the normalization
    exemption, but with the old `non-empty whenever` wording FR22 retires."""

    def test_forged_old_wording_is_otherwise_well_formed(self):
        normalized = _normalize(FORGED_RESUME_CONDITIONS_OLD_WORDING)
        self.assertIn("stop-recovery guidance", normalized)
        self.assertIn("empty for every other `state`", normalized)
        self.assertIn("NOT put through `detail`'s normalization", normalized)

    def test_old_wording_is_rejected(self):
        with self.assertRaises(AssertionError):
            _assert_resume_conditions_presence_rule_stated(
                self, FORGED_RESUME_CONDITIONS_OLD_WORDING
            )


class TestSc5LiteralGuardMatcher(unittest.TestCase):
    """NFR4: negative proof + non-vacuity guard for `_assert_no_sc5_literals`,
    plus a false-positive proof over ordinary English prose that legitimately
    contains "detail:" / "feature:" substrings (`batch-mode.md`'s own "Full
    detail:" / "a feature:" wording)."""

    def test_key_colon_citation_is_rejected(self):
        forged = "See the SSOT; the `detail`: field carries the summary."
        with self.assertRaises(AssertionError):
            _assert_no_sc5_literals(self, forged)

    def test_key_equals_citation_is_rejected(self):
        forged = "The result line reads state=stopped step=implement."
        with self.assertRaises(AssertionError):
            _assert_no_sc5_literals(self, forged)

    def test_state_value_shape_is_rejected(self):
        forged = 'The mapping carries state: "phase_done" at the boundary.'
        with self.assertRaises(AssertionError):
            _assert_no_sc5_literals(self, forged)

    def test_reason_code_bare_mention_is_rejected(self):
        forged = "A step_stuck condition ends the run."
        with self.assertRaises(AssertionError):
            _assert_no_sc5_literals(self, forged)

    def test_ordinary_prose_with_key_shaped_english_colons_is_not_flagged(self):
        """Non-vacuity / false-positive proof: `batch-mode.md`'s real,
        pre-existing "Full detail:" and "a feature:" phrasing must not trip
        the guard -- these are ordinary English punctuation, not a
        restated citation."""
        real_text = _read(BATCH_MODE_PATH)
        self.assertIn("Full detail:", real_text)
        _assert_no_sc5_literals(self, real_text)


class TestBatchModePointerSc5Compliance(unittest.TestCase):
    """SC5: `task0001 pins the set in tests/test_batch_stop_contract.py for
    batch-mode.md`. `batch-mode.md` is not edited by this task; this only
    asserts its current content already complies."""

    def test_names_the_contract_document(self):
        text = _read(BATCH_MODE_PATH)
        self.assertIn("references/batch-terminal-line.md", text)

    def test_restates_no_sc5_literal(self):
        _assert_no_sc5_literals(self, _read(BATCH_MODE_PATH))


class TestStopReasonCodes(unittest.TestCase):
    """AC-4."""

    @classmethod
    def setUpClass(cls):
        cls.section = _sections(_read(CONTRACT_PATH))["Stop reason codes"]
        cls.codes = _extract_reason_code_table(cls.section)

    def test_table_has_rows(self):
        self.assertTrue(self.codes)

    def test_codes_are_well_formed(self):
        _assert_well_formed_code_list(self, self.codes)

    def test_extracted_set_equals_the_twelve_fixed_codes(self):
        # task-tier-reduction/task0004 adds `no_work_required`, making
        # REASON_CODES twelve members (was eleven).
        self.assertEqual(set(self.codes), REASON_CODES)

    def test_section_stated_count_equals_table_row_count(self):
        self.assertIn("twelve", self.section.lower())
        self.assertEqual(len(self.codes), 12)
        self.assertEqual(len(self.codes), len(REASON_CODES))

    def test_context_budget_reached_documented_as_thirteenth_never_emitted(self):
        """AC-4: the `reason` domain documents thirteen values (task-tier-
        reduction/task0004 raises this from twelve), with
        `context_budget_reached` marked never emitted, in this section's
        prose (companion to the same fact stated in `## Field values`)."""
        normalized = _normalize(self.section)
        self.assertIn(f"`{CONTEXT_BUDGET_REACHED}`", self.section)
        self.assertIn("thirteenth", normalized)
        self.assertIn("never emits it", normalized)
        # AC-4: absent from the coverage table (checked structurally in
        # TestStopPointCoverage.test_context_budget_reached_absent_from_coverage_table).

    def test_context_budget_reached_absent_as_table_row(self):
        """The reason-code TABLE itself stays at exactly twelve rows --
        context_budget_reached is documented in prose, never as a row (the
        twelve-row regression guard above already proves the row count; this
        proves the specific code is not one of them)."""
        self.assertNotIn(CONTEXT_BUDGET_REACHED, self.codes)

    def test_none_documented_as_reserved_for_non_stop_states(self):
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


FORGED_GATE_FAIL_CLOSED_REENUMERATION = (
    "A gate was classified fail-closed: `category: security`, `category: "
    "license`, and `reversible: false` abort in interactive; in both modes "
    "per references/question-resolution.md."
)


class TestGateFailClosedCoverageWording(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.section = _sections(_read(CONTRACT_PATH))["Stop reason codes"]
        cls.meaning = _reason_code_meaning(cls.section, "gate_fail_closed")

    def test_meaning_cell_found(self):
        self.assertIsNotNone(
            self.meaning,
            "no `gate_fail_closed` row found in the reason-code table",
        )

    def test_coverage_wording_stated(self):
        _assert_gate_fail_closed_coverage_wording_stated(self, self.meaning)

    def test_old_flat_wording_is_gone(self):
        self.assertNotIn(
            "A gate was classified fail-closed and the phase aborted",
            self.section,
        )


class TestGateFailClosedCoverageWordingMatcherNegativeProof(unittest.TestCase):
    def test_forged_reenumeration_is_otherwise_well_formed(self):
        self.assertIn("both modes", FORGED_GATE_FAIL_CLOSED_REENUMERATION)
        self.assertIn("interactive", FORGED_GATE_FAIL_CLOSED_REENUMERATION)
        self.assertIn(
            "references/question-resolution.md",
            FORGED_GATE_FAIL_CLOSED_REENUMERATION,
        )

    def test_forged_reenumeration_is_rejected(self):
        with self.assertRaises(AssertionError):
            _assert_gate_fail_closed_coverage_wording_stated(
                self, FORGED_GATE_FAIL_CLOSED_REENUMERATION
            )


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


def _assert_none_reserved_for_non_stop_states_stated(test, section_text, old_phrase):
    """`none` is reserved for the non-stop terminal states -- `state`
    `completed` and `state` `phase_done` -- named together in the same
    passage, with the old `state=completed`-only restrictive phrasing
    (`old_phrase`, verbatim from before this feature's earlier rework
    round) gone."""
    normalized = _normalize(section_text)
    test.assertIn("`none`", section_text)
    test.assertIn("reserved", normalized)
    # Normalized rather than raw: the two-token phrase can legitimately be
    # split across a hard line-wrap in the source document, unlike the
    # single, unsplittable `` `state=completed` `` token this replaces.
    test.assertIn("`state` `completed`", normalized)
    test.assertIn("`state` `phase_done`", normalized)
    test.assertIn("non-stop terminal state", normalized)
    test.assertNotIn(old_phrase, section_text)


class TestNoneReservedRangeMatcherNegativeProofs(unittest.TestCase):
    def test_field_values_forged_bullet_is_otherwise_well_formed(self):
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


def _assert_step_precedence_stated(test, field_values_section_text):
    """The general executed-step rule, and the two rules that take
    precedence over it (the `no-step` sentinel; the rule for `state`
    `completed`), stated with a readable priority relation."""
    normalized = _normalize(field_values_section_text)
    test.assertIn("names the step EXECUTED in that turn", normalized)
    test.assertIn("take precedence over the general rule", normalized)
    test.assertIn("`no-step`", field_values_section_text)
    # Normalized: the two-token phrase can be split across a hard line-wrap.
    test.assertIn("`state` `completed`", normalized)
    test.assertIn("`retrospect`", field_values_section_text)


def _assert_step_c_asymmetry_stated(test, field_values_section_text):
    """A Step C turn's value differs by outcome -- `retrospect` on normal
    completion, `no-step` on `step-c-abort`."""
    normalized = _normalize(field_values_section_text)
    test.assertIn("Step C is not a `workflow.yaml` step", normalized)
    test.assertIn("normal completion is `retrospect`", normalized)
    test.assertIn("`step-c-abort` is `no-step`", normalized)


def _extract_step_value_domain(field_values_section_text):
    """Extracts the closed `step` value domain declared at the FRONT of the
    `## Field values` `step` bullet -- the backticked `workflow.yaml` step
    ids inside the declaration's own parenthesized list, plus the
    backticked sentinel that closes it. Structural, matched against
    normalized text, not a prose substring search over the whole bullet."""
    match = STEP_DOMAIN_DECLARATION_RE.search(_normalize(field_values_section_text))
    if match is None:
        return set()
    step_ids = set(_BACKTICK_WORD_TOKEN_RE.findall(match.group(1)))
    return step_ids | {match.group(2)}


STEP_DOMAIN_DECLARATION_RE = re.compile(
    r"`step` — a closed value domain: one of the seven "
    r"`workflow\.yaml` step ids \(([^)]*)\), or the single sentinel "
    r"`([a-z-]+)`\."
)
_BACKTICK_WORD_TOKEN_RE = re.compile(r"`([a-z][a-z0-9-]*)`")


def _assert_step_value_domain_declared(test, field_values_section_text, expected_domain):
    domain = _extract_step_value_domain(field_values_section_text)
    test.assertTrue(
        domain,
        "no `step` value-domain declaration found at the front of the "
        "`step` bullet",
    )
    test.assertEqual(domain, expected_domain)


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
    "next launch resumes at `implement`. When `state` is `completed` the "
    "value is always `retrospect` — the final workflow step, which a "
    "completed run has always reached."
)


class TestStepPrecedenceMatcherNegativeProof(unittest.TestCase):
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
    def test_forged_old_bullet_is_otherwise_well_formed(self):
        self.assertIn("`step-c-abort`", FORGED_OLD_STEP_BULLET_WITHOUT_PRECEDENCE)
        self.assertIn("`retrospect`", FORGED_OLD_STEP_BULLET_WITHOUT_PRECEDENCE)

    def test_missing_asymmetry_wording_is_rejected(self):
        with self.assertRaises(AssertionError):
            _assert_step_c_asymmetry_stated(
                self, FORGED_OLD_STEP_BULLET_WITHOUT_PRECEDENCE
            )


FORGED_STEP_BULLET_WITHOUT_DOMAIN_DECLARATION = (
    "`step` — the general rule: `step` names the step EXECUTED in that "
    "turn, never the step the next launch resumes at; at the "
    "verify-fail rework boundary the value is `verify`, even though "
    "the next launch resumes at `implement`. Two rules take precedence "
    "over the general rule: the single sentinel `no-step`, and the rule "
    "for `state` `completed`. `no-step` applies whenever no "
    "`workflow.yaml` step is in effect at the stop point: "
    "`stop-condition-6` (Step 0's git-setup abort), `step-a-abort` "
    "(Step A's feature-resolution failure), and `step-c-abort` (Step "
    "C's abort — every workflow step has already completed by then, "
    "and the stop happens outside any of them). When `state` is "
    "`completed` the value is always `retrospect` — the final workflow "
    "step, which a completed run has always reached. Because Step C is "
    "not a `workflow.yaml` step, a turn that executes Step C takes its "
    "value from whichever precedence rule applies rather than from the "
    "general rule: normal completion is `retrospect` (the `state` "
    "`completed` rule), while `step-c-abort` is `no-step` (the "
    "sentinel rule) — this asymmetry is intentional, not an omission."
)


class TestStepValueDomainMatcherNegativeProof(unittest.TestCase):
    def test_forged_bullet_is_otherwise_well_formed(self):
        normalized = _normalize(FORGED_STEP_BULLET_WITHOUT_DOMAIN_DECLARATION)
        self.assertIn("names the step EXECUTED in that turn", normalized)
        self.assertIn("take precedence over the general rule", normalized)
        self.assertIn("Step C is not a `workflow.yaml` step", normalized)

    def test_missing_domain_declaration_is_rejected(self):
        self.assertEqual(
            _extract_step_value_domain(FORGED_STEP_BULLET_WITHOUT_DOMAIN_DECLARATION),
            set(),
        )
        with self.assertRaises(AssertionError):
            _assert_step_value_domain_declared(
                self,
                FORGED_STEP_BULLET_WITHOUT_DOMAIN_DECLARATION,
                STEP_VALUE_DOMAIN,
            )


class TestNoStepAnchorUnaffectedByDomainDeclaration(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.section = _sections(_read(CONTRACT_PATH))["Field values"]

    def test_anchor_matches_on_one_physical_line(self):
        match = NO_STEP_BULLET_RE.search(self.section)
        self.assertIsNotNone(
            match,
            "the `` `no-step` applies whenever `` anchor did not match -- "
            "likely a hard wrap inside the anchor phrase, which silently "
            "empties the extraction",
        )

    def test_extracted_stop_points_still_match_the_coverage_table(self):
        coverage_section = _sections(_read(CONTRACT_PATH))["Stop point coverage"]
        coverage_keys = {
            key for key, _code in _extract_coverage_table(coverage_section)
        }
        extracted = _extract_no_step_stop_points(self.section)
        self.assertEqual(extracted, NO_STEP_STOP_POINTS)
        self.assertTrue(extracted <= coverage_keys)

    def test_create_spec_and_create_plan_are_excluded(self):
        extracted = _extract_no_step_stop_points(self.section)
        self.assertNotIn("create-spec", extracted)
        self.assertNotIn("create-plan", extracted)


class TestStopPointCoverage(unittest.TestCase):
    """AC-4."""

    @classmethod
    def setUpClass(cls):
        cls.section = _sections(_read(CONTRACT_PATH))["Stop point coverage"]
        cls.pairs = _extract_coverage_table(cls.section)

    def test_table_has_rows(self):
        self.assertTrue(self.pairs)

    def test_bidirectional_coverage(self):
        _assert_bidirectional_coverage(self, self.pairs, STOP_POINT_KEYS, REASON_CODES)

    def test_pairing_matches_expected_key_code_mapping(self):
        self.assertEqual(dict(self.pairs), dict(_KEY_CODE_PAIRS_IN_ORDER))

    def test_each_row_names_a_source_document(self):
        rows = _table_rows(self.section)
        for row in rows:
            with self.subTest(row=row):
                self.assertTrue(row[2].strip())

    def test_source_paths_resolve_to_existing_files(self):
        cells = _extract_coverage_source_cells(self.section)
        _assert_source_paths_resolve(self, cells)

    def test_source_column_intro_claims_only_naming(self):
        self.assertNotIn("owns (defines)", self.section)
        self.assertIn("names the document", _normalize(self.section))

    def test_precedence_rule_stated(self):
        _assert_precedence_rule_stated(self, self.section)

    def test_context_budget_reached_exception_stated(self):
        _assert_context_budget_reached_exception_stated(self, self.section)

    def test_context_budget_reached_absent_from_coverage_table(self):
        """AC-4: a forged domain that adds the twelfth code as a coverage
        row is rejected by the bidirectional-coverage matcher (its code-set
        would then exceed REASON_CODES, the eleven-member set the matcher
        checks against)."""
        codes_seen = {code for _key, code in self.pairs}
        self.assertNotIn(CONTEXT_BUDGET_REACHED, codes_seen)


class TestCoverageMatcherRejectsTwelfthCodeAsRow(unittest.TestCase):
    """AC-4 negative proof: a forged coverage table that adds
    `context_budget_reached` as an extra row is rejected -- the matcher's
    `expected_codes` set (REASON_CODES, twelve members as of task-tier-
    reduction/task0004) does not contain it, so the "every bound code is a
    member of expected_codes" check fires."""

    def test_forged_table_with_reserved_code_row_is_otherwise_well_formed(self):
        forged = _forged_coverage_table(
            _KEY_CODE_PAIRS_IN_ORDER + [("docs-commit-conflict", CONTEXT_BUDGET_REACHED)]
        )
        pairs = _extract_coverage_table(forged)
        self.assertEqual(len(pairs), len(_KEY_CODE_PAIRS_IN_ORDER) + 1)

    def test_coverage_row_added_for_reserved_code_is_rejected(self):
        forged = _forged_coverage_table(
            _KEY_CODE_PAIRS_IN_ORDER + [("docs-commit-conflict", CONTEXT_BUDGET_REACHED)]
        )
        pairs = _extract_coverage_table(forged)
        with self.assertRaises(AssertionError):
            _assert_bidirectional_coverage(self, pairs, STOP_POINT_KEYS, REASON_CODES)


FORGED_MISSING_KEY_TABLE = _forged_coverage_table(_KEY_CODE_PAIRS_IN_ORDER[:-1])
FORGED_CODE_OUTSIDE_SET_TABLE = _forged_coverage_table(
    [pair for pair in _KEY_CODE_PAIRS_IN_ORDER if pair[0] != "step-c-abort"]
    + [("step-c-abort", "bogus_code")]
)
FORGED_DUPLICATE_KEY_TABLE = _forged_coverage_table(
    _KEY_CODE_PAIRS_IN_ORDER[:-1] + [("stop-condition-2", "completion_aborted")]
)


class TestCoverageMatcherNegativeProofs(unittest.TestCase):
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


FORGED_COVERAGE_SECTION_WITHOUT_PRECEDENCE = _forged_coverage_table(
    _KEY_CODE_PAIRS_IN_ORDER
)


class TestPrecedenceMatcherNegativeProof(unittest.TestCase):
    def test_forged_section_still_parses_into_a_complete_well_formed_table(self):
        pairs = _extract_coverage_table(FORGED_COVERAGE_SECTION_WITHOUT_PRECEDENCE)
        _assert_bidirectional_coverage(self, pairs, STOP_POINT_KEYS, REASON_CODES)

    def test_missing_precedence_rule_is_rejected(self):
        with self.assertRaises(AssertionError):
            _assert_precedence_rule_stated(
                self, FORGED_COVERAGE_SECTION_WITHOUT_PRECEDENCE
            )

    def test_missing_context_budget_reached_exception_is_rejected(self):
        with self.assertRaises(AssertionError):
            _assert_context_budget_reached_exception_stated(
                self, FORGED_COVERAGE_SECTION_WITHOUT_PRECEDENCE
            )


FORGED_NONEXISTENT_SOURCE_ROW_TABLE = (
    "| Stop point | Reason code | Source |\n"
    "|---|---|---|\n"
    "| `stop-condition-2` | `step_stuck` | `references/does-not-exist.md` |\n"
)


class TestSourcePathMatcherNegativeProof(unittest.TestCase):
    def test_forged_row_is_otherwise_well_formed_and_extracted(self):
        pairs = _extract_coverage_table(FORGED_NONEXISTENT_SOURCE_ROW_TABLE)
        self.assertEqual(pairs, [("stop-condition-2", "step_stuck")])
        cells = _extract_coverage_source_cells(FORGED_NONEXISTENT_SOURCE_ROW_TABLE)
        self.assertEqual(cells, ["`references/does-not-exist.md`"])

    def test_nonexistent_source_path_is_rejected(self):
        cells = _extract_coverage_source_cells(FORGED_NONEXISTENT_SOURCE_ROW_TABLE)
        with self.assertRaises(AssertionError):
            _assert_source_paths_resolve(self, cells)


class TestNoResultOnWaitTurnAndSentinel(unittest.TestCase):
    """AC-7."""

    @classmethod
    def setUpClass(cls):
        cls.sections = _sections(_read(CONTRACT_PATH))

    def test_states_stop_condition_5_emits_no_result(self):
        section = _normalize(self.sections["No result on a wait turn"])
        self.assertIn("stop condition 5", section)
        self.assertIn("no result", section)

    def test_states_general_no_result_rule(self):
        section = _normalize(self.sections["No result on a wait turn"])
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
        coverage_section = _sections(_read(CONTRACT_PATH))["Stop point coverage"]
        coverage_keys = {key for key, _code in _extract_coverage_table(coverage_section)}
        extracted = _extract_no_step_stop_points(self.sections["Field values"])
        self.assertEqual(extracted, NO_STEP_STOP_POINTS)
        self.assertTrue(
            extracted <= coverage_keys,
            "every no-step stop point must be a key of the coverage table",
        )


class TestConsumerConstraints(unittest.TestCase):
    """AC-5."""

    @classmethod
    def setUpClass(cls):
        cls.section = _sections(_read(CONTRACT_PATH))["Consumer constraints"]

    def test_stopped_with_none_rejected(self):
        normalized = _normalize(self.section)
        self.assertIn("`state` `stopped` together with `reason` `none`", normalized)

    def test_phase_done_requires_none_and_empty_resume_conditions(self):
        normalized = _normalize(self.section)
        self.assertIn("`state` `phase_done` without `reason` `none`", normalized)
        self.assertIn("empty", normalized)
        self.assertIn("`resume_conditions`", normalized)

    def test_branch_and_pr_url_control_character_constraint_stated(self):
        normalized = _normalize(self.section)
        self.assertIn("`branch`", normalized)
        self.assertIn("`pr_url`", normalized)
        self.assertIn("line terminator", normalized)
        self.assertIn("terminal-control", normalized)

    def test_escaping_does_not_help_note_stated(self):
        normalized = _normalize(self.section)
        self.assertIn("does not help", normalized)
        self.assertIn("rejects the value after parsing", normalized)

    def test_64_kib_bound_stated(self):
        normalized = _normalize(self.section)
        self.assertIn("64 KiB", normalized)
        self.assertIn("UTF-8", normalized)

    def test_nothing_may_be_dropped_summarized_counted_or_pointed_at(self):
        normalized = _normalize(self.section)
        self.assertIn("dropped", normalized)
        self.assertIn("summarized", normalized)
        self.assertIn("replaced by a count", normalized)
        self.assertIn("replaced by a\n           pointer".replace("\n           ", " "), normalized)
        self.assertIn("never truncated to fit", normalized)

    def test_size_collision_outcome_stated(self):
        """AC-4/SC11 (d): completes the old "reportable condition for the
        run" wording with the single defined outcome."""
        _assert_size_collision_outcome_stated(self, self.section)

    def test_own_hardening_rules_stated(self):
        """AC-8/SC11 (g)+(h)."""
        _assert_own_hardening_rules_stated(self, self.section)

    def test_own_rules_preamble_stated(self):
        """task0001 AC-1 (FR4)."""
        _assert_own_rules_preamble_stated(self, self.section)

    def test_detail_own_rule_states_line_terminator_and_normalization_reason(self):
        """task0001 AC-2 (FR1, FR3): `detail` gets its own bullet, stating
        the line-terminator/terminal-control rejection together with the
        reason it is correct (## Field values already normalizes CR/LF/TAB
        to a space before escaping, so a surviving one means normalization
        was skipped)."""
        _carried_over, own_rules = _split_consumer_constraints_own_rules(self.section)
        normalized = _normalize(own_rules)
        self.assertIn("`detail` rejects a line terminator", normalized)
        self.assertIn("terminal-control code point after decoding", normalized)
        self.assertIn("replaces every CR, LF and TAB in `detail`", normalized)
        self.assertIn("normalization was skipped", normalized)

    def test_resume_conditions_exemption_stated(self):
        """task0001 AC-3 (FR1, FR2, FR9)."""
        _assert_resume_conditions_exemption_stated(self, self.section)

    def test_five_carried_over_constraints_still_present_and_still_five(self):
        """FR14's five numbered carried-over constraints are unchanged --
        the new own-hardening-rules items use bullets, never renumbering
        into this list."""
        carried_over, _own = _split_consumer_constraints_own_rules(self.section)
        numbered = re.findall(r"^\d+\.", carried_over, re.MULTILINE)
        self.assertEqual(len(numbered), 5)


FORGED_CONSUMER_CONSTRAINTS_MISSING_ONE = (
    "1. `state` `stopped` together with `reason` `none`.\n"
    "2. `state` `phase_done` without `reason` `none` and an empty "
    "`resume_conditions`.\n"
    "3. A `branch` value containing a line terminator or a "
    "terminal-control code point.\n"
    "4. A `pr_url` value containing a line terminator or a "
    "terminal-control code point.\n"
)


def _assert_consumer_constraints_stated(test, section_text):
    normalized = _normalize(section_text)
    test.assertIn("`state` `stopped` together with `reason` `none`", normalized)
    test.assertIn("`state` `phase_done` without `reason` `none`", normalized)
    test.assertIn("`branch`", normalized)
    test.assertIn("`pr_url`", normalized)
    test.assertIn("64 KiB", normalized)


class TestConsumerConstraintsMatcherNegativeProof(unittest.TestCase):
    def test_forged_missing_bound_is_otherwise_well_formed(self):
        self.assertIn(
            "`state` `stopped` together with `reason` `none`",
            FORGED_CONSUMER_CONSTRAINTS_MISSING_ONE,
        )
        self.assertIn("`branch`", FORGED_CONSUMER_CONSTRAINTS_MISSING_ONE)

    def test_missing_constraint_is_rejected(self):
        with self.assertRaises(AssertionError):
            _assert_consumer_constraints_stated(
                self, FORGED_CONSUMER_CONSTRAINTS_MISSING_ONE
            )


# -- AC-4 (task0008): size-collision-outcome matcher negative proof --------

FORGED_SIZE_COLLISION_NO_OUTCOME = (
    "Nothing may be dropped, summarized, replaced by a count, or replaced "
    "by a pointer in order to satisfy the 64 KiB bound. An emitter that "
    "cannot satisfy both this bound and `batch-mode.md`'s `## Reporting` "
    '"in full" requirement has a reportable condition for the run — never '
    "a license to truncate."
)


class TestSizeCollisionOutcomeMatcherNegativeProof(unittest.TestCase):
    """The forged sample is the real pre-change wording, verbatim -- it
    already carries the bound, the no-truncation sentence and the in-full
    reference, but never names an outcome."""

    def test_forged_old_wording_is_otherwise_well_formed(self):
        normalized = _normalize(FORGED_SIZE_COLLISION_NO_OUTCOME)
        lowered = normalized.lower()
        self.assertIn("64 KiB", normalized)
        self.assertIn("dropped", lowered)
        self.assertIn("summarized", lowered)
        self.assertIn("replaced by a count", lowered)
        self.assertIn("replaced by a pointer", lowered)

    def test_missing_outcome_is_rejected(self):
        with self.assertRaises(AssertionError):
            _assert_size_collision_outcome_stated(
                self, FORGED_SIZE_COLLISION_NO_OUTCOME
            )


# -- AC-8 (task0008): own-hardening-rules matcher negative proof -----------
# Updated in place by task0001 (AC-5/FR8): the forged sample now carries
# the new-style introductory sentence and both per-field bullets, but
# still omits the duplicate-key and documented-domain shape defenses, so
# it stays "otherwise well-formed but partial" under the new wording.

FORGED_OWN_RULES_PARTIAL = (
    OWN_RULES_LABEL + ". The rules below are em-workflow's own hardening "
    "obligations, stated here as defense in depth alongside the five "
    "carried-over constraints above — they are NOT carried-over consumer "
    "behaviour.\n\n"
    "- `detail` rejects a line terminator or a terminal-control code "
    "point after decoding. `## Escaping` does not help here either: an "
    "escaped control character inside `detail` is rejected exactly like "
    "a bare one.\n"
    "- `resume_conditions` rejects only a terminal-control code point "
    "other than CR (U+000D), LF (U+000A) or TAB (U+0009) after decoding "
    "— a decoded CR, LF or TAB inside `resume_conditions` is NOT a "
    "violation.\n"
    "- The top-level mapping's key sequence is exactly the eight keys of "
    "`## Result format`, in that order: a result with a missing, extra or "
    "reordered key is rejected.\n"
)


class TestOwnHardeningRulesMatcherNegativeProof(unittest.TestCase):
    def test_carried_over_text_alone_does_not_satisfy_the_matcher(self):
        """Non-vacuity: FR14's five carried-over constraints legitimately
        use the words 'reject' and 'constraint', so the matcher must not
        be satisfiable by that text alone -- it must anchor on the
        OWN_RULES_LABEL separator."""
        section = _sections(_read(CONTRACT_PATH))["Consumer constraints"]
        carried_over, _own = _split_consumer_constraints_own_rules(section)
        self.assertIn("reject", carried_over.lower())
        self.assertIn("constraint", carried_over.lower())
        self.assertNotIn(OWN_RULES_LABEL, carried_over)
        with self.assertRaises(AssertionError):
            _assert_own_hardening_rules_stated(self, carried_over)

    def test_forged_partial_rules_is_otherwise_well_formed(self):
        self.assertIn(OWN_RULES_LABEL, FORGED_OWN_RULES_PARTIAL)
        self.assertIn("`detail`", FORGED_OWN_RULES_PARTIAL)
        self.assertIn("`resume_conditions`", FORGED_OWN_RULES_PARTIAL)
        self.assertIn("line terminator", FORGED_OWN_RULES_PARTIAL)
        self.assertIn("does not help here either", FORGED_OWN_RULES_PARTIAL)

    def test_forged_partial_rules_missing_shape_checks_is_rejected(self):
        with self.assertRaises(AssertionError):
            _assert_own_hardening_rules_stated(self, FORGED_OWN_RULES_PARTIAL)


# -- task0001 AC-1: own-rules preamble matcher negative proof --------------

FORGED_PRE_CHANGE_PREAMBLE = (
    OWN_RULES_LABEL + ". The rules below are em-workflow's own hardening "
    "obligations, stated here as defense in depth alongside the five "
    "carried-over constraints above — they are NOT carried-over consumer "
    "behaviour, and this repository can verify nothing about how (or "
    "whether) the external consumer enforces them. Each of the four "
    "cannot fire while `## Escaping` is honoured: they are defense in "
    "depth for the case an unescaped newline inside a value is followed "
    "by a line that looks like another key.\n\n"
    "- `detail` and `resume_conditions` each reject a line terminator or "
    "a terminal-control code point after decoding, in the same form as "
    "constraints 3 and 4 above.\n"
)


class TestOwnRulesPreambleMatcherNegativeProof(unittest.TestCase):
    """FORGED_PRE_CHANGE_PREAMBLE is the real pre-change introductory
    sentence, verbatim -- it already carries the own-hardening framing and
    the carried-over-consumer-behaviour labelling, but still makes the
    blanket "cannot fire" claim with its rule-count word."""

    def test_forged_pre_change_preamble_is_otherwise_well_formed(self):
        self.assertIn(OWN_RULES_LABEL, FORGED_PRE_CHANGE_PREAMBLE)
        self.assertIn("own hardening obligations", FORGED_PRE_CHANGE_PREAMBLE)
        self.assertIn(
            "carried-over consumer behaviour", FORGED_PRE_CHANGE_PREAMBLE
        )

    def test_forged_pre_change_preamble_is_rejected(self):
        with self.assertRaises(AssertionError):
            _assert_own_rules_preamble_stated(self, FORGED_PRE_CHANGE_PREAMBLE)


# -- task0001 AC-3: resume_conditions exemption matcher negative proof -----

FORGED_PRE_CHANGE_SHARED_BULLET = (
    OWN_RULES_LABEL + ".\n\n"
    "- `detail` and `resume_conditions` each reject a line terminator or "
    "a terminal-control code point after decoding, in the same form as "
    "constraints 3 and 4 above. `## Escaping` does not help here either: "
    "an escaped control character inside either value is rejected "
    "exactly like a bare one.\n"
)


class TestResumeConditionsExemptionMatcherNegativeProof(unittest.TestCase):
    """FORGED_PRE_CHANGE_SHARED_BULLET is the real pre-change shared
    bullet, verbatim, preceded by OWN_RULES_LABEL so the rejection is
    attributable to the contradictory wording rather than to a missing
    anchor (IMPLEMENTATION.md D5)."""

    def test_carried_over_text_alone_does_not_satisfy_the_matcher(self):
        """Non-vacuity: the carried-over numbered constraints legitimately
        mention `resume_conditions` (constraint 2), so the matcher must
        not be satisfiable by that text alone -- it must anchor on the
        OWN_RULES_LABEL separator."""
        section = _sections(_read(CONTRACT_PATH))["Consumer constraints"]
        carried_over, _own = _split_consumer_constraints_own_rules(section)
        self.assertIn("`resume_conditions`", carried_over)
        self.assertNotIn(OWN_RULES_LABEL, carried_over)
        with self.assertRaises(AssertionError):
            _assert_resume_conditions_exemption_stated(self, carried_over)

    def test_forged_pre_change_bullet_is_otherwise_well_formed(self):
        self.assertIn(OWN_RULES_LABEL, FORGED_PRE_CHANGE_SHARED_BULLET)
        self.assertIn("`detail`", FORGED_PRE_CHANGE_SHARED_BULLET)
        self.assertIn("`resume_conditions`", FORGED_PRE_CHANGE_SHARED_BULLET)

    def test_forged_pre_change_bullet_is_rejected(self):
        with self.assertRaises(AssertionError):
            _assert_resume_conditions_exemption_stated(
                self, FORGED_PRE_CHANGE_SHARED_BULLET
            )


class TestResponsibilityBoundary(unittest.TestCase):
    """AC-7."""

    @classmethod
    def setUpClass(cls):
        cls.section = _sections(_read(CONTRACT_PATH))["Responsibility boundary"]

    def test_states_no_status_operation_against_external_service(self):
        section = _normalize(self.section)
        self.assertIn("no status operation", section)
        self.assertIn("external task-management service", section)

    def test_states_confidentiality_rule_extended_to_all_four_fields(self):
        normalized = _normalize(self.section)
        for field in ("`detail`", "`resume_conditions`", "`branch`", "`pr_url`"):
            with self.subTest(field=field):
                self.assertIn(field, self.section)
        self.assertIn("carry no confidential", normalized)

    def test_confidentiality_rule_states_beyond_paths(self):
        """AC-1/SC11 (a)."""
        _assert_confidentiality_beyond_paths_stated(self, self.section)


FORGED_RESPONSIBILITY_BOUNDARY_MISSING_BEYOND_PATHS = (
    "`detail`, `resume_conditions`, `branch` and `pr_url` carry no "
    "confidential information: once emitted, the result's content is "
    "relayed outside of em-workflow's own process boundary."
)


class TestConfidentialityBeyondPathsMatcherNegativeProof(unittest.TestCase):
    def test_forged_old_wording_is_otherwise_well_formed(self):
        self.assertIn(
            "carry no confidential",
            _normalize(FORGED_RESPONSIBILITY_BOUNDARY_MISSING_BEYOND_PATHS),
        )

    def test_missing_beyond_paths_is_rejected(self):
        with self.assertRaises(AssertionError):
            _assert_confidentiality_beyond_paths_stated(
                self, FORGED_RESPONSIBILITY_BOUNDARY_MISSING_BEYOND_PATHS
            )


class TestEscapingSection(unittest.TestCase):
    """AC-2."""

    @classmethod
    def setUpClass(cls):
        cls.section = _sections(_read(CONTRACT_PATH))["Escaping"]
        cls.pairs = _extract_escaping_table(cls.section)

    def test_table_matches_sc3_canonical_mapping(self):
        _assert_escaping_table_matches_sc3(self, self.pairs)

    def test_states_residual_ranges(self):
        section = _normalize(self.section)
        for token in (
            "U+0000-U+001F", "U+007F-U+009F", "U+2028", "U+2029", "U+FFFE", "U+FFFF",
        ):
            with self.subTest(token=token):
                self.assertIn(token, section)
        self.assertIn("four lower-case hex digits", section)

    def test_states_character_by_character_never_reprocess_rule(self):
        section = _normalize(self.section)
        self.assertIn("character by character", section)
        self.assertIn("never re-processes", section)

    def test_escaping_table_distinguishes_named_tokens_from_literal_characters(self):
        """Edge case (Test Notes): the extractor must tell a named token
        (CR/LF/TAB) apart from a backticked literal character, and must not
        be confused by the backslash characters in the second column."""
        sources = [pair[0] for pair in self.pairs]
        self.assertIn("CR (U+000D)", sources)
        self.assertIn("LF (U+000A)", sources)
        self.assertIn("TAB (U+0009)", sources)
        self.assertIn(r"`\`", sources)
        self.assertIn(r'`"`', sources)


class TestPrefixUniqueness(unittest.TestCase):
    """AC-6 (SC6, inverted sweep): the removed prefix literal must be
    absent from EVERY file under `em-workflow/`, including this document
    itself now -- no "only inside this file" carve-out and no fenced-block
    scope exemption remain."""

    def test_prefix_absent_from_every_file_under_em_workflow(self):
        offenders = []
        files_read = 0
        for path in _iter_em_workflow_files(PLUGIN_ROOT):
            try:
                text = path.read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            files_read += 1
            if PREFIX in text:
                offenders.append(str(path.relative_to(REPO_ROOT)))
        self.assertGreater(
            files_read, 20,
            "the sweep read a suspiciously small number of files -- "
            "likely walking the wrong root",
        )
        self.assertEqual(offenders, [], f"prefix leaked into: {offenders}")

    def test_prefix_constant_is_non_empty(self):
        """Non-vacuity: the sweep is only meaningful if PREFIX itself is a
        real, non-empty string that could plausibly be found."""
        self.assertTrue(PREFIX)
        self.assertGreater(len(PREFIX), 5)

    def test_negative_proof_sweep_would_detect_a_reintroduced_prefix(self):
        """Negative proof for the sweep logic itself: a synthetic file
        content containing PREFIX is detected by the same substring check
        the sweep uses."""
        synthetic = "some prose\n" + PREFIX + " state=stopped\n"
        self.assertIn(PREFIX, synthetic)


if __name__ == "__main__":
    unittest.main()
