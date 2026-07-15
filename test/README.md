# Test Instructions for AI Agents

This document provides guidelines for AI agents when writing and executing tests.

## Test Framework

Python standard library `unittest` (Python 3.14, no external dependencies).

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
