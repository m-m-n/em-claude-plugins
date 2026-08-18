"""Tests for task0001 (recycled-task-id-contract): the machine-readable hook
classification table in `em-workflow/references/implement-phase.md`, and the
single pin test comparing it against the real hook sources.

Covers task0001 Acceptance Criteria
(feature-docs/recycled-task-id-contract/tasks/task0001.md):

- AC-4 (FR5): the document contains exactly one machine-readable hook
  classification table meeting the table contract (unique anchor, the four
  queue-hook rows -- no more, no fewer -- a repo-relative path column, and a
  fixed two-value classification vocabulary).
- AC-6 (FR5, NFR4): exactly one pin test compares every parsed table row
  against its hook source using one uniform observation rule; the module
  proves the pin is not a no-op -- an inverted-classification sample
  produces a non-empty disagreement list, and a row whose path does not
  resolve fails.
- AC-7 (NFR1, NFR3): standard-library-only imports; no file under
  `em-workflow/hooks/` is written by this module (read-only access via
  `Path.is_file` / `Path.read_text`).

This module owns three separable steps (task plan Design section), so the
pin stays a single test while its parts remain provable on their own:

1. `parse_classification_table` -- parses the table's rows from the document
   text (default: the document itself). Raises `ClassificationTableError` on
   a missing/duplicated anchor, a missing table, or a malformed row (wrong
   column count, or an unrecognized classification value) -- never a silent
   skip (table contract's Consumer obligation).
2. `reads_per_task_status` -- observes ONE hook source directly: does it
   read `tasks.{T}.status`? Defined once, applied uniformly to every row --
   no per-hook special-casing. Considers only executable content: comments
   (absent from the AST to begin with) and docstrings (blanked before
   unparsing) are excluded before the search, because `queue_taskstop_net.py`
   mentions the workflow state file only in its module docstring --
   explicitly disclaiming that it ever touches it there -- and a raw text
   search over the whole file would misclassify it as reading it. The
   signal itself is the AND of two conditions, not a bare "workflow.yaml"
   substring search (which alone cannot distinguish reading per-task status
   from any other reason to touch the file, e.g. `bash_guard.py` extracting
   `*_command` fields): "workflow.yaml" appears in the stripped source, AND
   a defined-and-called function whose own name denotes deriving a per-task
   status exists in the module. Raises `ClassificationTableError` if the
   given path does not resolve to an existing file (table contract's
   Consumer obligation).
3. `compare_table_to_sources` -- the list of disagreements between each
   row's documented classification and the observation of its own source;
   an empty list iff documentation and implementation agree. Propagates
   `reads_per_task_status`'s failure for a row whose path does not resolve,
   rather than silently skipping it.

`tests/test_recycled_task_id_consistency.py` imports `parse_classification_
table`, `READS_STATUS` and `DOES_NOT_READ_STATUS` from this module rather
than duplicating the parser or restating a classification (NFR4 -- one
parser, one source of truth for the table's shape and vocabulary).
"""

import ast
import re
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
IMPLEMENT_PHASE_PATH = REPO_ROOT / "em-workflow" / "references" / "implement-phase.md"

# Table contract (FR5): a stable textual anchor (caption line) immediately
# preceding the table, unique in the document, that the parser locates it
# by.
TABLE_ANCHOR = "**Hook classification table**"

# Table contract: fixed two-value classification vocabulary.
READS_STATUS = "reads `tasks.{T}.status`"
DOES_NOT_READ_STATUS = "does not read `tasks.{T}.status`"
VALID_CLASSIFICATIONS = (READS_STATUS, DOES_NOT_READ_STATUS)

# AC-4: the exact four queue hooks I.2.a's classification names -- no more,
# no fewer (table contract's Rows clause). A structural, not-a-classification
# guard (NFR4): this set names which files are covered, not what each one's
# classification is.
EXPECTED_HOOK_FILENAMES = frozenset(
    {
        "queue_launch_guard.py",
        "queue_stop_guard.py",
        "queue_failure_net.py",
        "queue_taskstop_net.py",
    }
)


class ClassificationTableError(ValueError):
    """A missing/duplicated table anchor, a missing table, a malformed row,
    an unrecognized classification value, or (from `reads_per_task_status`)
    a hook path that does not resolve to an existing file -- table
    contract's Consumer obligation: never a silent skip."""


def read_document():
    return IMPLEMENT_PHASE_PATH.read_text(encoding="utf-8")


def parse_classification_table(text=None):
    """Parse the machine-readable hook classification table.

    Input: the document text (default: implement-phase.md itself). Output:
    a list of (hook_path, classification) tuples, in document order.

    Raises `ClassificationTableError` on a missing anchor, a duplicated
    anchor (the table contract requires it be unique), a missing table
    immediately after it, a malformed row (not exactly two pipe-delimited
    columns), or an unrecognized classification value.

    Does NOT check that each hook path resolves to an existing file -- that
    precondition belongs to `reads_per_task_status` (Design point 2), so a
    row with a broken path parses successfully and fails later, at
    observation time, rather than being silently dropped here.
    """
    if text is None:
        text = read_document()

    first = text.find(TABLE_ANCHOR)
    if first == -1:
        raise ClassificationTableError(
            f"hook classification table anchor {TABLE_ANCHOR!r} not found"
        )
    if text.find(TABLE_ANCHOR, first + 1) != -1:
        raise ClassificationTableError(
            f"hook classification table anchor {TABLE_ANCHOR!r} is not "
            "unique in the document"
        )

    after_anchor = text[first + len(TABLE_ANCHOR) :]
    # The anchor sits inside a caption paragraph that may continue (and
    # word-wrap) past the anchor phrase itself; the table starts only after
    # that paragraph ends (a blank line).
    parts = after_anchor.split("\n\n", 1)
    remainder = parts[1] if len(parts) == 2 else ""
    lines = remainder.splitlines()

    idx = 0
    while idx < len(lines) and lines[idx].strip() == "":
        idx += 1

    table_lines = []
    while idx < len(lines) and lines[idx].strip().startswith("|"):
        table_lines.append(lines[idx].strip())
        idx += 1

    if len(table_lines) < 3:
        raise ClassificationTableError(
            "no markdown table with at least one row found immediately "
            "after the hook classification table anchor"
        )

    _header, separator, *row_lines = table_lines
    if not row_lines:
        raise ClassificationTableError(
            "hook classification table has a header and separator but no "
            "rows"
        )

    rows = []
    for row_line in row_lines:
        cells = [cell.strip() for cell in row_line.strip("|").split("|")]
        if len(cells) != 2:
            raise ClassificationTableError(
                f"malformed classification table row (expected exactly 2 "
                f"columns): {row_line!r}"
            )
        hook_cell, classification_cell = cells
        hook_path = hook_cell.strip("`").strip()
        classification = classification_cell.strip()
        if classification not in VALID_CLASSIFICATIONS:
            raise ClassificationTableError(
                f"unrecognized classification value {classification!r} for "
                f"{hook_path!r}; expected one of {VALID_CLASSIFICATIONS}"
            )
        rows.append((hook_path, classification))

    return rows


def _strip_docstrings(source):
    """Return `source` with every module/class/function docstring blanked
    out. Comments are already absent from the AST, so unparsing after this
    step yields text with both comments and docstrings excluded --
    "executable content" as the observation rule requires."""
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            body = node.body
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                body[0].value = ast.Constant(value="")
    return ast.unparse(tree)


# The observation rule's actual signal (not a bare substring search over
# "workflow.yaml"): a defined-and-referenced name that itself denotes
# extracting a PER-TASK status out of the parsed workflow state -- e.g.
# `task_statuses_from_workflow`. A module can mention "workflow.yaml" (a
# glob pattern, a docstring disclaimer, a *_command extraction unrelated to
# task status -- see bash_guard.py) without ever deriving a per-task status
# from it; this pattern requires BOTH "task" and "status" to co-occur in one
# identifier, so it only fires on code that names the thing the table's
# vocabulary is actually about.
_TASK_STATUS_NAME_RE = re.compile(r"task[a-z_]*status|status[a-z_]*task", re.IGNORECASE)


def reads_per_task_status(hook_path):
    """Observe one hook source directly: does it read `tasks.{T}.status`?

    Defined once, applied uniformly to every row -- no per-hook
    special-casing. Strips comments and docstrings before searching
    (`_strip_docstrings`), because `queue_taskstop_net.py` mentions the
    workflow state file only in its module docstring -- explicitly
    disclaiming that it ever touches it there -- and a raw text search over
    the whole file would misclassify it.

    The signal is NOT a bare `"workflow.yaml" in source` check (that only
    proves the file references the workflow state file at all -- a module
    can do that for an unrelated purpose, e.g. `bash_guard.py` extracts
    `*_command` fields and never looks at any task's status). Instead this
    walks the AST for a defined function whose own name denotes deriving a
    PER-TASK status (matches `_TASK_STATUS_NAME_RE`: both "task" and
    "status" co-occur in one identifier) that is also actually CALLED
    somewhere in the module -- a merely-defined-but-dead helper proves
    nothing was read. `workflow.yaml` must additionally appear in the
    (docstring-stripped) executable source, so the two conditions are
    ANDed: a per-task-status accessor is defined and invoked, AND the
    module's executable code references the workflow state file.

    Precondition: `hook_path` resolves to an existing file -- otherwise
    `ClassificationTableError` (table contract's Consumer obligation).
    """
    path = Path(hook_path)
    if not path.is_file():
        raise ClassificationTableError(
            f"hook source does not resolve to an existing file: {hook_path!r}"
        )
    source = path.read_text(encoding="utf-8")
    stripped = _strip_docstrings(source)
    if "workflow.yaml" not in stripped:
        return False

    tree = ast.parse(stripped)
    task_status_fn_names = {
        node.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        and _TASK_STATUS_NAME_RE.search(node.name)
    }
    if not task_status_fn_names:
        return False

    called_names = {
        node.func.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }
    return bool(task_status_fn_names & called_names)


def compare_table_to_sources(rows):
    """The list of disagreements between each row's documented
    classification and the observation of its own source. Empty list iff
    documentation and implementation agree (Design point 3). A row whose
    path does not resolve is not silently skipped: `reads_per_task_status`
    raises, and that propagates out of this function too."""
    disagreements = []
    for hook_path, classification in rows:
        observed = (
            READS_STATUS
            if reads_per_task_status(REPO_ROOT / hook_path)
            else DOES_NOT_READ_STATUS
        )
        if observed != classification:
            disagreements.append((hook_path, classification, observed))
    return disagreements


class TestParseClassificationTable(unittest.TestCase):
    """AC-4 (FR5): the document contains exactly one machine-readable hook
    classification table meeting the table contract."""

    @classmethod
    def setUpClass(cls):
        cls.rows = parse_classification_table()

    def test_parses_the_real_document_without_error(self):
        self.assertIsInstance(self.rows, list)
        self.assertTrue(self.rows)

    def test_exactly_four_rows(self):
        self.assertEqual(len(self.rows), 4)

    def test_row_hook_names_match_the_four_queue_hooks_no_more_no_fewer(self):
        names = {Path(path).name for path, _ in self.rows}
        self.assertEqual(names, set(EXPECTED_HOOK_FILENAMES))

    def test_every_row_path_is_repo_relative_and_resolves(self):
        for hook_path, _ in self.rows:
            self.assertFalse(Path(hook_path).is_absolute(), hook_path)
            self.assertTrue(
                (REPO_ROOT / hook_path).is_file(),
                f"{hook_path} does not resolve to an existing file",
            )

    def test_every_classification_is_from_the_fixed_vocabulary(self):
        for _, classification in self.rows:
            self.assertIn(classification, VALID_CLASSIFICATIONS)

    def test_anchor_is_unique_in_the_document(self):
        text = read_document()
        self.assertEqual(text.count(TABLE_ANCHOR), 1)


class TestParseClassificationTableFailureModes(unittest.TestCase):
    """Edge cases (task plan Test Notes): missing anchor; a table missing
    entirely; a malformed row; an unrecognized classification value; a
    duplicated anchor. Never a silent skip -- each raises."""

    def test_missing_anchor_raises(self):
        with self.assertRaises(ClassificationTableError):
            parse_classification_table("no table anywhere in this text.")

    def test_missing_table_after_anchor_raises(self):
        text = TABLE_ANCHOR + " caption text.\n\nno table follows, just prose.\n"
        with self.assertRaises(ClassificationTableError):
            parse_classification_table(text)

    def test_header_and_separator_but_no_rows_raises(self):
        text = (
            TABLE_ANCHOR
            + " caption.\n\n"
            + "| Hook | Classification |\n"
            + "|---|---|\n"
        )
        with self.assertRaises(ClassificationTableError):
            parse_classification_table(text)

    def test_malformed_row_wrong_column_count_raises(self):
        text = (
            TABLE_ANCHOR + " caption.\n\n"
            "| Hook | Classification |\n"
            "|---|---|\n"
            "| only-one-column |\n"
        )
        with self.assertRaises(ClassificationTableError):
            parse_classification_table(text)

    def test_unrecognized_classification_value_raises(self):
        text = (
            TABLE_ANCHOR + " caption.\n\n"
            "| Hook | Classification |\n"
            "|---|---|\n"
            "| `em-workflow/hooks/queue_stop_guard.py` | sometimes reads it |\n"
        )
        with self.assertRaises(ClassificationTableError):
            parse_classification_table(text)

    def test_duplicated_anchor_raises(self):
        text = (
            TABLE_ANCHOR
            + " caption one.\n"
            + TABLE_ANCHOR
            + " caption two.\n\n"
            + "| Hook | Classification |\n"
            + "|---|---|\n"
            + f"| `em-workflow/hooks/queue_stop_guard.py` | {READS_STATUS} |\n"
        )
        with self.assertRaises(ClassificationTableError):
            parse_classification_table(text)

    def test_well_formed_table_parses_to_the_expected_row(self):
        # Non-vacuity guard for the failure-mode tests above: proves a
        # correctly-shaped table of this same construction DOES parse, so
        # the failures above are attributable to the specific defect
        # introduced, not to some unrelated formatting mistake.
        text = (
            TABLE_ANCHOR + " caption.\n\n"
            "| Hook | Classification |\n"
            "|---|---|\n"
            f"| `em-workflow/hooks/queue_stop_guard.py` | {READS_STATUS} |\n"
        )
        rows = parse_classification_table(text)
        self.assertEqual(
            rows, [("em-workflow/hooks/queue_stop_guard.py", READS_STATUS)]
        )


class TestObserveHookSource(unittest.TestCase):
    """The observation rule (defined once, applied uniformly): strips
    comments and docstrings before searching, so a hook that mentions the
    workflow state file only in its module docstring is not misclassified
    by a raw text search."""

    def test_queue_stop_guard_reads_status(self):
        self.assertTrue(
            reads_per_task_status(
                REPO_ROOT / "em-workflow/hooks/queue_stop_guard.py"
            )
        )

    def test_queue_launch_guard_does_not_read_status(self):
        self.assertFalse(
            reads_per_task_status(
                REPO_ROOT / "em-workflow/hooks/queue_launch_guard.py"
            )
        )

    def test_queue_failure_net_does_not_read_status(self):
        self.assertFalse(
            reads_per_task_status(
                REPO_ROOT / "em-workflow/hooks/queue_failure_net.py"
            )
        )

    def test_queue_taskstop_net_does_not_read_status(self):
        # This hook's module docstring explicitly says it "never touches
        # `workflow.yaml`" -- but it SAYS "workflow.yaml" while saying so.
        # A raw text search over the whole file would find that mention and
        # misclassify the hook as reading it; the observation rule strips
        # the docstring first and correctly classifies it as not reading.
        self.assertFalse(
            reads_per_task_status(
                REPO_ROOT / "em-workflow/hooks/queue_taskstop_net.py"
            )
        )

    def test_raw_text_search_would_have_misclassified_queue_taskstop_net(self):
        # Proof that the docstring-stripping step above is load-bearing,
        # not incidental: without it, the raw source DOES contain the
        # workflow-state-file marker (in prose, disclaiming exactly what
        # the naive search would conclude).
        raw = (
            REPO_ROOT / "em-workflow/hooks/queue_taskstop_net.py"
        ).read_text(encoding="utf-8")
        self.assertIn("workflow.yaml", raw)

    def test_unresolvable_path_raises(self):
        with self.assertRaises(ClassificationTableError):
            reads_per_task_status(
                REPO_ROOT / "em-workflow/hooks/does_not_exist.py"
            )

    def test_bash_guard_reads_workflow_yaml_but_not_task_status(self):
        # Real negative counter-example (finding 56b64fea7f61b999): this
        # hook's `declared_commands` reads workflow.yaml on purpose, but
        # only to extract *_command fields -- it never derives a per-task
        # status. A bare `"workflow.yaml" in source` rule would misclassify
        # it as reading status; the AND'd per-task-status-accessor signal
        # correctly says False.
        path = REPO_ROOT / "em-workflow/hooks/bash_guard.py"
        self.assertIn("workflow.yaml", path.read_text(encoding="utf-8"))
        self.assertFalse(reads_per_task_status(path))

    def _write_and_observe(self, source):
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, encoding="utf-8"
        ) as fh:
            fh.write(source)
            tmp_path = Path(fh.name)
        try:
            return reads_per_task_status(tmp_path)
        finally:
            tmp_path.unlink()

    def test_bare_workflow_yaml_mention_without_status_accessor_is_false(self):
        # Non-triviality: a module that merely mentions "workflow.yaml" in
        # executable code, with no per-task-status accessor defined or
        # called, must NOT be classified as reading status. Pins down that
        # the rule is the AND of both signals, not the workflow.yaml
        # substring alone.
        source = (
            "import glob\n"
            "PATTERN = 'feature-docs/*/workflow.yaml'\n"
            "def find_files():\n"
            "    return glob.glob(PATTERN)\n"
        )
        self.assertFalse(self._write_and_observe(source))

    def test_removing_the_status_carveout_flips_observation_to_false(self):
        # Non-trivial fixed test required by finding 56b64fea7f61b999: a
        # synthetic source modeled on queue_stop_guard.py, with ONLY its
        # recycled-task-id carve-out's status read removed (the
        # `task_statuses_from_workflow` definition and call site both
        # deleted, everything else -- including the "workflow.yaml"
        # glob-pattern string -- left intact), must observe as False. This
        # proves the rule tracks the actual status-reading carve-out, not
        # merely the presence of the "workflow.yaml" string in the file.
        with_carveout = (
            "import glob\n"
            "import os\n"
            "\n"
            "def task_statuses_from_workflow(path):\n"
            "    return {'task0001': 'pending'}\n"
            "\n"
            "def evaluate_feature(path):\n"
            "    statuses = task_statuses_from_workflow(path)\n"
            "    return statuses.get('task0001') == 'pending'\n"
            "\n"
            "def active_candidates(root):\n"
            "    pattern = os.path.join(root, '*', 'feature-docs', '*', 'workflow.yaml')\n"
            "    return sorted(glob.glob(pattern))\n"
        )
        self.assertTrue(self._write_and_observe(with_carveout))

        without_carveout = (
            "import glob\n"
            "import os\n"
            "\n"
            "def evaluate_feature(path):\n"
            "    return False\n"
            "\n"
            "def active_candidates(root):\n"
            "    pattern = os.path.join(root, '*', 'feature-docs', '*', 'workflow.yaml')\n"
            "    return sorted(glob.glob(pattern))\n"
        )
        self.assertFalse(self._write_and_observe(without_carveout))


class TestNonVacuityGuards(unittest.TestCase):
    """Structural guards over the parsed table (not restated
    classifications, NFR4): at least one row of each classification value
    exists, and every parsed path resolves to an existing file."""

    @classmethod
    def setUpClass(cls):
        cls.rows = parse_classification_table()

    def test_at_least_one_row_reads_status(self):
        self.assertGreaterEqual(
            sum(1 for _, c in self.rows if c == READS_STATUS), 1
        )

    def test_at_least_one_row_does_not_read_status(self):
        self.assertGreaterEqual(
            sum(1 for _, c in self.rows if c == DOES_NOT_READ_STATUS), 1
        )

    def test_every_row_path_resolves(self):
        for hook_path, _ in self.rows:
            self.assertTrue(
                (REPO_ROOT / hook_path).is_file(),
                f"{hook_path} does not resolve to an existing file",
            )


class TestHookClassificationPin(unittest.TestCase):
    """AC-6 (FR5, NFR4): the single pin test. Compares every parsed table
    row against its own hook source using the one uniform observation rule;
    documentation and implementation agree iff the disagreement list is
    empty. This is the ONLY pin test in this module -- no per-hook pin, no
    second pin (task plan Out of Scope)."""

    def test_documented_classification_matches_observed_classification_for_every_row(
        self,
    ):
        rows = parse_classification_table()
        disagreements = compare_table_to_sources(rows)
        self.assertEqual(disagreements, [])


class TestPinIsNotAVacuousCheck(unittest.TestCase):
    """AC-6: proof the pin above is not a no-op. An inverted-classification
    sample (one real row's classification swapped) produces a non-empty
    disagreement list; a row whose path does not resolve fails outright
    rather than silently passing."""

    def test_inverted_classification_produces_a_disagreement(self):
        rows = parse_classification_table()
        hook_path, classification = rows[0]
        inverted = (
            DOES_NOT_READ_STATUS
            if classification == READS_STATUS
            else READS_STATUS
        )
        tampered_rows = [(hook_path, inverted)] + list(rows[1:])
        disagreements = compare_table_to_sources(tampered_rows)
        self.assertEqual(len(disagreements), 1)
        self.assertEqual(disagreements[0][0], hook_path)
        self.assertEqual(disagreements[0][1], inverted)

    def test_row_with_unresolvable_path_fails(self):
        rows = [("em-workflow/hooks/does_not_exist.py", DOES_NOT_READ_STATUS)]
        with self.assertRaises(ClassificationTableError):
            compare_table_to_sources(rows)

    def test_agreeing_table_produces_no_disagreements(self):
        # Companion to the inversion proof above: an UNtampered table over
        # the real hooks produces zero disagreements, so the inversion
        # test's non-empty result is attributable to the tamper, not to the
        # comparator always returning something.
        rows = parse_classification_table()
        self.assertEqual(compare_table_to_sources(rows), [])


if __name__ == "__main__":
    unittest.main()
