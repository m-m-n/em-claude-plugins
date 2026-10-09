# Test Instructions for AI Agents

This document provides guidelines for AI agents when writing and executing tests.

## Test Framework

Python standard library `unittest` (Python 3.14). This "no external
dependencies" rule is scoped to test code: tests never import a
third-party package and never assume one is installed. It does not extend
to the plugin's runtime scripts — `em-workflow/scripts/validate-worker-output.py`
and `em-workflow/scripts/check-plugin-invariants.py` depend on PyYAML,
which is a runtime dependency of the plugin, not a test dependency.

## Test Execution

### Unit Tests
```bash
python3 -m unittest discover -s tests
```

## Test File Organization

All test files live in the repository-root `tests/` directory, named
`test_*.py`. Tests for a plugin's scripts/hooks reference their targets by
path (e.g. `em-workflow/hooks/bash_guard.py`); there is no installable
package.

## Writing Tests

### Test Naming Conventions

- Files: `test_<target>.py` (e.g. `test_stop_hook.py`)
- Classes: `Test<Behavior>` extending `unittest.TestCase`
- Methods: `test_<condition>_<expected_result>`

### Test Structure

- Hook scripts are tested by invoking them as subprocesses with JSON on
  stdin (the same contract Claude Code uses) and asserting on exit code and
  stdout/stderr.
- Shell scripts (e.g. `merge-task.sh`) are tested against throwaway git
  repositories created in a temporary directory per test.
- Use environment-variable overrides provided by the scripts under test
  (e.g. `EM_WORKFLOW_APPROVALS`) to isolate state; never touch real
  `~/.claude` state from tests.

## Adding New Tests

Add a `test_*.py` file under `tests/`; `unittest discover` picks it up
automatically. No registration step is needed.

## Common Patterns

- `tempfile.TemporaryDirectory()` for isolated filesystem fixtures.
- `subprocess.run([...], input=json.dumps(payload), capture_output=True)`
  for hook-contract tests.

## Test Docs Records (`test-docs/**/*.tests.yaml`)

Each task records its acceptance tests in a `*.tests.yaml` file under
`test-docs/`. The record check `tests/test_tests_yaml_id_resolution.py` reads
every such record and fails once per record file on any extraction or
resolution error.

### Test ID format

Each element of an AC's `tests` list is a test ID. IDs start with `tests.` and
are dot-separated: `tests.<module>`, `tests.<module>.<Class>` and
`tests.<module>.<Class>.<method>`. IDs are accepted at module, class or
method level.

An ID is accepted when it is judged as under
`python3 -m unittest discover -s tests` run from the repository root, where
the repository root and `tests/` are both on the module search path. The steps
below run in order, and the first failing step ends the evaluation of that
ID.

1. Syntax gate: the ID consists of two or more dot-separated segments, each a
   valid Python identifier, and the first segment is exactly `tests`. File
   paths, `path::Class::method` forms, wildcards, abbreviations and free text
   fail here, before any import.
2. Structural resolution: the longest leading part of the ID that names an
   importable module is imported, and the remaining segments are looked up as
   attributes without calling anything. A module that exists but fails while
   importing fails with the import error. The final object must be a module;
   a class derived from `unittest.TestCase`, other than `unittest.TestCase`
   itself; or a method of such a class, defined on that class or on one of its
   ancestors that is neither `unittest.TestCase` nor an ancestor of it. A
   missing module or attribute, a class not derived from `unittest.TestCase`,
   a module-level function or any other callable, and a method available only
   through `unittest.TestCase` fail. A method ID whose last segment is a dunder
   name (for example `__init__`) is rejected as `not a test method`, even when
   the test class defines it.
3. Loader confirmation: the ID is passed to `loadTestsFromName` of a fresh
   `unittest.TestLoader`. It fails when the call raises, when the loader's
   `errors` list gains an entry, when the loader returns something that is not
   a suite, when an exception is raised while walking the returned suite, or
   when the returned suite, walked recursively without being run, contains a
   failed-test placeholder.

Test method bodies are never executed. Loader confirmation, like ordinary test
collection, instantiates the test classes (including any custom `__init__`)
and runs `load_tests` hooks.

The record check puts the repository root at the front of the module search
path for the duration of each check and restores the exact prior value
afterwards, also when a step raises.

### Record notation read by the record check

`tests/test_tests_yaml_id_resolution.py` is the record check. It reads a
record as UTF-8 text, line by line, with spaces-only indentation, and
understands only this subset of YAML:

- Ignored lines: blank lines and full-line comments (first non-space
  character `#`) at every structural level, and one optional document start
  marker `---` before the first top-level key.
- Keys: a plain or single-line quoted key followed by a colon. A trailing
  comment (whitespace, then `#`, outside quotes) is allowed on every key line
  and every `tests` item line.
- Top level: keys at column 0. `acceptance_tests` occurs exactly once and has
  nothing after its colon except an optional comment.
- AC level: the keys one level under `acceptance_tests`, all at one common
  indentation. Every key name is accepted as an AC key (`AC-n` or any other
  name, such as `D4-parser-unavailable`). An AC key has nothing after its
  colon except an optional comment.
- Field level: the keys one level under an AC key, all at one common
  indentation. Exactly one field is `tests`.
- `tests` value, in one of two forms:
  - Flow sequence: on the key line, an opening bracket, zero or more
    comma-separated single-line scalars, a closing bracket, then an optional
    comment; `[]` is the empty list.
  - Block sequence: nothing on the key line except an optional comment,
    followed by one or more items, all at one indentation equal to or deeper
    than the `tests` key's indentation; each item is a dash, a space, one
    single-line scalar and an optional comment.
- Scalars inside `tests` are plain, single-quoted or double-quoted, each on
  one line. Inside single quotes two consecutive single quotes stand for one;
  inside double quotes backslash-quote and backslash-backslash are the only
  escapes.
- Opaque values: every top-level key other than `acceptance_tests`, and every
  field other than `tests`, is opaque. Its value is the rest of its key line
  plus every following line that is blank or indented deeper than that key.
  Opaque lines are never interpreted: lines starting with `tests:` or a dash
  inside them are never IDs. This covers block scalars (`|` and `>`, with or
  without indicators) such as a multi-line `red_reason`, and
  `baseline_failures` / `final_failures` in any form; none of them is ever
  extracted.

Each error names the record path and the AC key, or a record-level marker when
no AC applies. An extraction failure is never treated as an empty list. The
error conditions are:

- Unsupported notation: any structural line outside the rules above, for
  example a tab in indentation, a `tests` item that is a mapping, a sequence,
  multi-line or empty, a flow sequence spanning lines, an inline value after
  `acceptance_tests:` or after an AC key, inconsistent indentation within one
  level, a second `acceptance_tests`, or a `tests` key with neither a value
  nor items.
- Duplicate AC key.
- Duplicate `tests` key within one AC.
- Missing `tests` key in an AC.
- Missing `acceptance_tests`.
- Unreadable record: the file cannot be read or cannot be decoded as UTF-8.
