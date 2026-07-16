"""Tests for em-workflow/hooks/hooks.json registration (task0005).

Covers task0005 Acceptance Criteria AC-3 and AC-4:

- AC-3: hooks.json registers Stop / PreToolUse(Task) / SubagentStop entries
  referencing the three queue-loop hook scripts, while keeping the existing
  PreToolUse(Bash) bash_guard.py entry intact.
- AC-4: the registration test passes and fails meaningfully -- invalid JSON,
  a missing entry, or a missing referenced script file each produce a
  detectable failure.

Note on `queue_stop_guard.py` / `queue_launch_guard.py` / `queue_failure_net.py`:
those scripts are delivered by sibling tasks (task0002-task0004; see
feature-docs/implement-phase-queue/tasks/task0005.md, Design section). Until
those branches merge alongside this one, TestReferencedScriptFilesExist is
expected to fail for those three filenames -- that is not a defect in this
task's own deliverable (the wiring in hooks.json), which is covered
independently by TestHooksJsonRegistersRequiredEntries and
TestValidationDetectsBrokenConfigs.
"""

import json
import re
import tempfile
import unittest
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent / "em-workflow"
HOOKS_JSON_PATH = PLUGIN_ROOT / "hooks" / "hooks.json"

# (event, matcher or None for "no matcher filter", script filename)
REQUIRED_ENTRIES = [
    ("PreToolUse", "Bash", "bash_guard.py"),
    ("PreToolUse", "Task", "queue_launch_guard.py"),
    ("Stop", None, "queue_stop_guard.py"),
    ("SubagentStop", None, "queue_failure_net.py"),
]

_SCRIPT_COMMAND_RE = re.compile(r"hooks/([A-Za-z0-9_.-]+\.py)")


def find_matching_hook_entries(config, event, matcher, script_filename):
    """Return the command-hook dicts registered under `event` whose matcher
    matches (or all of them, when matcher is None) and whose command string
    references script_filename."""
    results = []
    for group in config.get("hooks", {}).get(event, []):
        if matcher is not None and group.get("matcher") != matcher:
            continue
        for hook in group.get("hooks", []):
            if script_filename in hook.get("command", ""):
                results.append(hook)
    return results


def extract_script_path(command, plugin_root):
    """Resolve the script file a hook `command` string references (the
    `${CLAUDE_PLUGIN_ROOT}/hooks/<name>.py` pattern) to a filesystem path
    under plugin_root. Returns None if the command does not match the
    pattern."""
    match = _SCRIPT_COMMAND_RE.search(command)
    if not match:
        return None
    return plugin_root / "hooks" / match.group(1)


def validate_hooks_config(config, plugin_root):
    """Validate a parsed hooks.json `config` against REQUIRED_ENTRIES.

    Returns a list of human-readable error strings; empty means valid. Pure
    function over an already-parsed dict, so it is reusable both against the
    real repository hooks.json and against fabricated fixtures (AC-4).
    """
    errors = []
    for event, matcher, script_filename in REQUIRED_ENTRIES:
        matches = find_matching_hook_entries(config, event, matcher, script_filename)
        if not matches:
            errors.append(
                f"missing entry: event={event!r} matcher={matcher!r} "
                f"script={script_filename!r}"
            )
            continue
        for hook in matches:
            script_path = extract_script_path(hook.get("command", ""), plugin_root)
            if script_path is None:
                errors.append(
                    f"command does not reference a resolvable script path: "
                    f"{hook.get('command')!r}"
                )
            elif not script_path.is_file():
                errors.append(f"referenced script file does not exist: {script_path}")
    return errors


class TestHooksJsonIsValidJson(unittest.TestCase):
    def test_hooks_json_is_valid_json(self):
        raw = HOOKS_JSON_PATH.read_text()
        try:
            json.loads(raw)
        except json.JSONDecodeError as exc:
            self.fail(f"hooks.json is not valid JSON: {exc}")


class TestHooksJsonRegistersRequiredEntries(unittest.TestCase):
    """Structural registration checks -- independent of whether the
    sibling-delivered script files exist on disk yet."""

    @classmethod
    def setUpClass(cls):
        cls.config = json.loads(HOOKS_JSON_PATH.read_text())

    def test_existing_bash_guard_entry_is_preserved(self):
        matches = find_matching_hook_entries(
            self.config, "PreToolUse", "Bash", "bash_guard.py"
        )
        self.assertTrue(
            matches, "existing PreToolUse(Bash) bash_guard.py entry must remain"
        )

    def test_task_launch_guard_is_registered(self):
        matches = find_matching_hook_entries(
            self.config, "PreToolUse", "Task", "queue_launch_guard.py"
        )
        self.assertTrue(
            matches,
            "PreToolUse(Task) entry referencing queue_launch_guard.py must be registered",
        )

    def test_stop_guard_is_registered(self):
        matches = find_matching_hook_entries(
            self.config, "Stop", None, "queue_stop_guard.py"
        )
        self.assertTrue(
            matches, "Stop entry referencing queue_stop_guard.py must be registered"
        )

    def test_subagent_stop_failure_net_is_registered(self):
        matches = find_matching_hook_entries(
            self.config, "SubagentStop", None, "queue_failure_net.py"
        )
        self.assertTrue(
            matches,
            "SubagentStop entry referencing queue_failure_net.py must be registered",
        )


class TestReferencedScriptFilesExist(unittest.TestCase):
    """Existence of every script hooks.json references, relative to the
    plugin root. The three queue_*.py scripts are owned by sibling tasks
    (task0002-task0004); this check holds once those branches are merged
    alongside this one (task0005.md Design section)."""

    @classmethod
    def setUpClass(cls):
        cls.config = json.loads(HOOKS_JSON_PATH.read_text())

    def test_all_referenced_scripts_exist(self):
        errors = validate_hooks_config(self.config, PLUGIN_ROOT)
        missing = [e for e in errors if e.startswith("referenced script file")]
        self.assertEqual(missing, [], "\n".join(missing))


class TestValidationDetectsBrokenConfigs(unittest.TestCase):
    """AC-4: proof that validate_hooks_config fails meaningfully on invalid
    JSON, a missing entry, and a missing script file -- using fabricated
    fixtures, independent of the real repository's current merge state."""

    def test_invalid_json_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            bad_path = Path(tmp) / "hooks.json"
            bad_path.write_text("{ this is not valid json")
            with self.assertRaises(json.JSONDecodeError):
                json.loads(bad_path.read_text())

    def test_missing_required_entry_is_detected(self):
        config = {"hooks": {"PreToolUse": [], "Stop": [], "SubagentStop": []}}
        errors = validate_hooks_config(config, PLUGIN_ROOT)
        self.assertTrue(
            any(e.startswith("missing entry") for e in errors),
            "an empty hooks config must report missing entries",
        )

    def test_missing_script_file_is_detected(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake_root = Path(tmp)
            (fake_root / "hooks").mkdir()
            # Only 3 of the 4 required scripts exist on disk; queue_stop_guard.py
            # is intentionally absent.
            for name in (
                "bash_guard.py",
                "queue_launch_guard.py",
                "queue_failure_net.py",
            ):
                (fake_root / "hooks" / name).write_text("")

            def cmd(name):
                return f'python3 "${{CLAUDE_PLUGIN_ROOT}}"/hooks/{name}'

            config = {
                "hooks": {
                    "PreToolUse": [
                        {
                            "matcher": "Bash",
                            "hooks": [{"type": "command", "command": cmd("bash_guard.py")}],
                        },
                        {
                            "matcher": "Task",
                            "hooks": [
                                {"type": "command", "command": cmd("queue_launch_guard.py")}
                            ],
                        },
                    ],
                    "Stop": [
                        {"hooks": [{"type": "command", "command": cmd("queue_stop_guard.py")}]}
                    ],
                    "SubagentStop": [
                        {
                            "hooks": [
                                {"type": "command", "command": cmd("queue_failure_net.py")}
                            ]
                        }
                    ],
                }
            }
            errors = validate_hooks_config(config, fake_root)
            missing_script_errors = [
                e for e in errors if e.startswith("referenced script file does not exist")
            ]
            self.assertEqual(len(missing_script_errors), 1)
            self.assertIn("queue_stop_guard.py", missing_script_errors[0])


if __name__ == "__main__":
    unittest.main()
