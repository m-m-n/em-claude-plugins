"""Tests for em-workflow/hooks/hooks.json registration (task0005; extended by
taskstop-journal-failed-event task0003).

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

Covers taskstop-journal-failed-event task0003 Acceptance Criteria AC-7 and
AC-8: hooks.json gains two further registrations from sibling tasks
(`queue_agent_index.py` from task0001, `queue_taskstop_net.py` from
task0002) added under whatever tool-call event they wire up to. Rather than
hardcoding those filenames here (which task0003's own Test Notes call out as
brittle -- it would need editing every time a further hook is added), the
`TestEveryRegisteredHookIsWellFormed` class below is driven entirely from
hooks.json's actual parsed contents: it walks every hook entry under every
event, whatever they are, and asserts each one individually is well-formed
(referenced script exists, plugin-root-relative `python3` command form,
standard `timeout: 15`). This is meaningful at any merge order -- run before
task0001/task0002 merge, it validates the four pre-existing entries; run
after, it validates all six -- without ever needing to know in advance how
many hooks or which filenames are registered.
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
    # The subagent-launch tool is `Agent` in current Claude Code versions
    # and `Task` in older ones — the matcher must cover both, or the guard
    # silently never fires (fail-open) on one of them.
    ("PreToolUse", "Task|Agent", "queue_launch_guard.py"),
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


# Standard shape every hook registration in this plugin must follow
# (worktree-task-workflow / IMPLEMENTATION.md Conventions: "Registration").
STANDARD_HOOK_TIMEOUT = 15
_PLUGIN_ROOT_PYTHON3_COMMAND_RE = re.compile(
    r'^python3 "\$\{CLAUDE_PLUGIN_ROOT\}"/hooks/[A-Za-z0-9_.-]+\.py$'
)


def iter_all_hook_commands(config):
    """Yield (event, matcher, hook_dict) for every command-hook entry
    registered anywhere in a parsed hooks.json config, regardless of event
    name or matcher value.

    This deliberately does NOT enumerate a fixed list of expected events or
    scripts -- it walks whatever the manifest currently declares, so it
    stays meaningful as further hooks (and possibly further event types,
    e.g. a PostToolUse entry from a sibling task) are registered without
    needing this test to be edited.
    """
    for event, groups in config.get("hooks", {}).items():
        for group in groups:
            matcher = group.get("matcher")
            for hook in group.get("hooks", []):
                yield event, matcher, hook


def validate_hook_entry_shape(hook, plugin_root):
    """Validate a single hook-command dict's registration shape:

    - its `command` uses the plugin-root-relative `python3` form
      (`python3 "${CLAUDE_PLUGIN_ROOT}"/hooks/<name>.py`, verbatim shape);
    - its `timeout` equals the standard value (STANDARD_HOOK_TIMEOUT);
    - the script file its command references exists on disk under
      plugin_root.

    Returns a list of human-readable error strings; empty means valid.
    """
    errors = []
    command = hook.get("command", "")
    if not _PLUGIN_ROOT_PYTHON3_COMMAND_RE.match(command):
        errors.append(
            f"command does not use the plugin-root-relative python3 form: {command!r}"
        )
    if hook.get("timeout") != STANDARD_HOOK_TIMEOUT:
        errors.append(
            f"timeout is not the standard {STANDARD_HOOK_TIMEOUT}: "
            f"{hook.get('timeout')!r} (command={command!r})"
        )
    script_path = extract_script_path(command, plugin_root)
    if script_path is None:
        errors.append(
            f"command does not reference a resolvable script path: {command!r}"
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
            self.config, "PreToolUse", "Task|Agent", "queue_launch_guard.py"
        )
        self.assertTrue(
            matches,
            "PreToolUse(Task|Agent) entry referencing queue_launch_guard.py must be registered",
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


class TestEveryRegisteredHookIsWellFormed(unittest.TestCase):
    """taskstop-journal-failed-event task0003 AC-7/AC-8: manifest-driven
    assertions covering EVERY hook entry hooks.json currently declares --
    including any registrations added by sibling tasks in this feature --
    rather than a hardcoded list of hook filenames or event names.

    Meaningful at any merge order: whatever hooks.json currently contains is
    exactly what gets validated, so this suite is green before task0001 and
    task0002 merge their own entries (validating today's four) and remains
    green afterwards (validating all of them, whatever count that ends up
    being)."""

    @classmethod
    def setUpClass(cls):
        cls.config = json.loads(HOOKS_JSON_PATH.read_text())
        cls.entries = list(iter_all_hook_commands(cls.config))

    def test_at_least_the_four_baseline_hooks_are_registered(self):
        self.assertGreaterEqual(
            len(self.entries),
            4,
            "hooks.json must register at least the four baseline hooks "
            "(bash_guard, queue_launch_guard, queue_stop_guard, queue_failure_net)",
        )

    def test_every_registered_hook_command_is_well_formed(self):
        errors = []
        for event, matcher, hook in self.entries:
            for err in validate_hook_entry_shape(hook, PLUGIN_ROOT):
                errors.append(f"[event={event!r} matcher={matcher!r}] {err}")
        self.assertEqual(errors, [], "\n".join(errors))

    def test_no_duplicate_script_registered_twice_under_the_same_event(self):
        # A copy/merge-conflict artifact (e.g. a hook entry pasted in twice
        # by a parent-side-adoption re-implementation) would otherwise pass
        # every other check here silently.
        seen = {}
        duplicates = []
        for event, matcher, hook in self.entries:
            script_path = extract_script_path(hook.get("command", ""), PLUGIN_ROOT)
            key = (event, str(script_path))
            if key in seen:
                duplicates.append(key)
            seen[key] = True
        self.assertEqual(
            duplicates, [], f"script(s) registered more than once under the same event: {duplicates}"
        )


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
                            "matcher": "Task|Agent",
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


class TestValidateHookEntryShapeDetectsMalformedEntries(unittest.TestCase):
    """AC-7's three checks (script existence, command form, standard
    timeout), proven independently with fabricated fixtures so a future
    regression in any single check is caught even if the real hooks.json
    happens to be well-formed in the other two respects."""

    def _well_formed_hook(self, name="queue_launch_guard.py"):
        return {
            "type": "command",
            "command": f'python3 "${{CLAUDE_PLUGIN_ROOT}}"/hooks/{name}',
            "timeout": STANDARD_HOOK_TIMEOUT,
        }

    def test_well_formed_entry_produces_no_errors(self):
        errors = validate_hook_entry_shape(self._well_formed_hook(), PLUGIN_ROOT)
        self.assertEqual(errors, [])

    def test_wrong_timeout_is_detected(self):
        hook = self._well_formed_hook()
        hook["timeout"] = 30
        errors = validate_hook_entry_shape(hook, PLUGIN_ROOT)
        self.assertTrue(
            any("timeout is not the standard" in e for e in errors),
            errors,
        )

    def test_missing_timeout_is_detected(self):
        hook = self._well_formed_hook()
        del hook["timeout"]
        errors = validate_hook_entry_shape(hook, PLUGIN_ROOT)
        self.assertTrue(
            any("timeout is not the standard" in e for e in errors),
            errors,
        )

    def test_non_plugin_root_relative_command_is_detected(self):
        hook = self._well_formed_hook()
        hook["command"] = "python3 hooks/queue_launch_guard.py"
        errors = validate_hook_entry_shape(hook, PLUGIN_ROOT)
        self.assertTrue(
            any("plugin-root-relative python3 form" in e for e in errors),
            errors,
        )

    def test_non_python3_command_is_detected(self):
        hook = self._well_formed_hook()
        hook["command"] = 'python "${CLAUDE_PLUGIN_ROOT}"/hooks/queue_launch_guard.py'
        errors = validate_hook_entry_shape(hook, PLUGIN_ROOT)
        self.assertTrue(
            any("plugin-root-relative python3 form" in e for e in errors),
            errors,
        )

    def test_missing_script_file_is_detected(self):
        hook = self._well_formed_hook(name="does_not_exist_anywhere.py")
        errors = validate_hook_entry_shape(hook, PLUGIN_ROOT)
        self.assertTrue(
            any("referenced script file does not exist" in e for e in errors),
            errors,
        )


if __name__ == "__main__":
    unittest.main()
