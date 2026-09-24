"""Shared, non-test helper for the `## Exemption registry` section of
`em-workflow/references/gate-option-vocabulary.md`.

This module's file name begins with an underscore and does not match
`test*.py` on purpose: `unittest discover` only collects `test*.py` files,
and this module defines no `TestCase` subclass, so it must stay outside
that collection net. It holds only the section extractor, the row parser,
the row validator and the exemption loader (IMPLEMENTATION.md Shared
Components) -- the contract both `tests/test_gate_option_vocabulary_doc.py`
and `tests/test_gate_option_vocabulary.py` build their assertions against.
It imports only standard-library modules (NFR1).

Error-handling policy -- loud failure, fail-safe degrade
(IMPLEMENTATION.md Conventions): a malformed registry row, a registry
section without a table, or an invalid exemption raises `ValueError`; this
module never catches and suppresses one of its own. Exactly three
conditions degrade to zero exemptions instead of raising, all of them
fail-safe because zero exemptions means every select gate stays checked:

1. the registry path is not a regular file (`load_exempt_gate_ids`);
2. reading the file fails with an OS-level error (`load_exempt_gate_ids`);
3. the document holds no `## Exemption registry` section at all
   (`extract_exemption_registry_section` returns `None`, which
   `load_exempt_gate_ids` turns into an empty set).

Everything else -- a present section with no pipe-table line, a data row
with the wrong cell count, a row that fails validation -- raises.
"""

import os


EXEMPTION_REGISTRY_HEADING = "## Exemption registry"


def extract_exemption_registry_section(text):
    """Isolate the registry section of a registry document (FR1).

    Returns the section body: the text after the FIRST line that consists
    exactly of the heading `## Exemption registry` (trailing whitespace on
    that line is allowed), up to but not including the next line that
    begins with `## `, or to end of text. A line beginning with `### ` does
    not end the section. A `### Exemption registry` line, or
    `## Exemption registry` appearing anywhere other than at the start of
    its own line, is not a section start. Returns `None` (the no-section
    result) when no qualifying heading line exists. Never raises for
    string input.
    """
    lines = text.splitlines(keepends=True)

    start_idx = None
    for i, line in enumerate(lines):
        if line.rstrip() == EXEMPTION_REGISTRY_HEADING:
            start_idx = i
            break
    if start_idx is None:
        return None

    end_idx = len(lines)
    for j in range(start_idx + 1, len(lines)):
        if lines[j].startswith("## "):
            end_idx = j
            break

    return "".join(lines[start_idx + 1 : end_idx])


def parse_exemption_table_rows(section_text):
    """Turn the section's pipe table into rows (FR2).

    `section_text` must be a non-null result of
    `extract_exemption_registry_section`. A pipe-table line is a line
    whose content, after surrounding whitespace is removed, begins with a
    pipe character. The first two pipe-table lines (header row, separator
    row) are skipped. Returns a list with one 3-tuple of whitespace-
    stripped cell texts per remaining line, in document order.

    Raises `ValueError` when the section holds no pipe-table line at all,
    and when a data line does not split into exactly 3 cells (the message
    quotes the offending line).
    """
    table_lines = [
        line for line in section_text.splitlines() if line.strip().startswith("|")
    ]
    if not table_lines:
        raise ValueError("no Markdown table found in exemption registry section")

    data_lines = table_lines[2:]  # skip header row + separator row
    rows = []
    for line in data_lines:
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 3:
            raise ValueError(f"exemption row does not have exactly 3 cells: {line!r}")
        rows.append(tuple(cells))
    return rows


def _derive_gate_id(gate_cell):
    """Shared gate_id derivation rule (IMPLEMENTATION.md Shared
    Components): a row's gate_id is its first cell with every leading and
    trailing backtick character removed, then leading and trailing
    whitespace removed."""
    return gate_cell.strip("`").strip()


def validate_exemption_rows(rows, select_ids):
    """Check parsed rows (FR3).

    `rows` must be a result of `parse_exemption_table_rows`; `select_ids`
    is a set of gate-id strings. Returns a list of violation strings,
    empty when every row is valid. For each row: a gate_id not in
    `select_ids` yields a violation containing
    "not an `action: select` entry"; an empty reason cell yields one
    containing "missing a reason"; an empty compensating-guarantee cell
    yields one containing "missing a compensating guarantee". Never
    raises.
    """
    violations = []
    for gate_cell, reason_cell, guarantee_cell in rows:
        gate_id = _derive_gate_id(gate_cell)
        if gate_id not in select_ids:
            violations.append(
                f"{gate_id!r} is not an `action: select` entry of batch-policies.yaml"
            )
        if not reason_cell:
            violations.append(f"{gate_id!r} row is missing a reason")
        if not guarantee_cell:
            violations.append(f"{gate_id!r} row is missing a compensating guarantee")
    return violations


def load_exempt_gate_ids(registry_path, select_ids):
    """Produce the exempt gate-id set for the correspondence sweep (FR5).

    `registry_path` is a filesystem path. `select_ids` is REQUIRED (no
    default) and is the `action: select` gate-id set. In order:

    1. path is not a regular file -> empty set;
    2. reading fails with an OS-level error -> empty set;
    3. extractor returns no-section -> empty set;
    4. otherwise the parser runs and its `ValueError` propagates
       unchanged;
    5. the validator runs and, when it returns any violation, this
       function raises `ValueError` whose message contains every
       violation string;
    6. otherwise returns the set of gate_ids of the parsed rows.
    """
    registry_path = os.fspath(registry_path)
    if not os.path.isfile(registry_path):
        return set()

    try:
        with open(registry_path, encoding="utf-8") as fh:
            text = fh.read()
    except OSError:
        return set()

    section = extract_exemption_registry_section(text)
    if section is None:
        return set()

    rows = parse_exemption_table_rows(section)

    violations = validate_exemption_rows(rows, select_ids)
    if violations:
        raise ValueError("; ".join(violations))

    return {_derive_gate_id(gate_cell) for gate_cell, _reason, _guarantee in rows}
