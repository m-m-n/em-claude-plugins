"""Registration invariants for `muse_guard.py` across both plugins
(feature-docs/muse-spark-contributor-consent/tasks/task0001.md AC-8).

Registration *shape* generic to every hook in em-workflow (interpreter/
extension pairing, per-script timeouts, referenced files existing) is
already the manifest-driven job of tests/test_hooks_registration.py and is
not duplicated here. This module covers what is specific to
muse_guard.py's own registration: that BOTH plugins declare it (em-review
had no `hooks/hooks.json` before this feature), that the verbatim command
form and timeout match the pin in IMPLEMENTATION.md, that em-workflow's
copy sits ahead of destructive-guard.py, and that neither file registers
any script twice under one event.

Standard library only, per test/README.md.
"""

import importlib.util
import json
import os
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

PLUGIN_ROOTS = {
    "em-workflow": REPO_ROOT / "em-workflow",
    "em-review": REPO_ROOT / "em-review",
}

# Verbatim form and timeout pinned in IMPLEMENTATION.md Shared Components,
# "Hook registration form".
PINNED_COMMAND = 'python3 "${CLAUDE_PLUGIN_ROOT}"/hooks/muse_guard.py'
PINNED_TIMEOUT = 15


def _load_hooks_config(plugin_root):
    path = plugin_root / "hooks" / "hooks.json"
    return json.loads(path.read_text(encoding="utf-8")), path


def _bash_pretooluse_groups(config):
    return [
        g
        for g in config.get("hooks", {}).get("PreToolUse", [])
        if g.get("matcher") == "Bash"
    ]


def _script_filenames_in_order(group):
    names = []
    for hook in group.get("hooks", []):
        command = hook.get("command", "")
        names.append(command.rsplit("/", 1)[-1])
    return names


def _find_muse_guard_hook(config):
    """The single hook-command dict registered under PreToolUse(Bash) whose
    command references muse_guard.py, or None."""
    for group in _bash_pretooluse_groups(config):
        for hook in group.get("hooks", []):
            if "muse_guard.py" in hook.get("command", ""):
                return hook
    return None


class TestHooksJsonIsValidJsonForBothPlugins(unittest.TestCase):
    def test_both_plugins_hooks_json_parse(self):
        for name, root in PLUGIN_ROOTS.items():
            with self.subTest(plugin=name):
                config, path = _load_hooks_config(root)
                self.assertIsInstance(config, dict, f"{path} did not parse to an object")


class TestBothPluginsRegisterMuseGuard(unittest.TestCase):
    def test_both_plugins_register_muse_guard_under_pretooluse_bash(self):
        for name, root in PLUGIN_ROOTS.items():
            with self.subTest(plugin=name):
                config, path = _load_hooks_config(root)
                hook = _find_muse_guard_hook(config)
                self.assertIsNotNone(hook, f"muse_guard.py not registered under PreToolUse(Bash) in {path}")

    def test_the_command_form_is_verbatim_identical_in_both_plugins(self):
        for name, root in PLUGIN_ROOTS.items():
            with self.subTest(plugin=name):
                config, _ = _load_hooks_config(root)
                hook = _find_muse_guard_hook(config)
                self.assertEqual(hook.get("command"), PINNED_COMMAND)

    def test_the_timeout_is_identical_in_both_plugins(self):
        for name, root in PLUGIN_ROOTS.items():
            with self.subTest(plugin=name):
                config, _ = _load_hooks_config(root)
                hook = _find_muse_guard_hook(config)
                self.assertEqual(hook.get("timeout"), PINNED_TIMEOUT)


class TestEmWorkflowOrderingAgainstDestructiveGuard(unittest.TestCase):
    """muse_guard.py must sit ahead of destructive-guard.py's blanket allow
    (task0001.md Design, "Registration"; IMPLEMENTATION.md decision D-B is
    unrelated -- this is about destructive-guard.py's own trailing `allow`
    ending the decision first)."""

    @classmethod
    def setUpClass(cls):
        cls.config, cls.path = _load_hooks_config(PLUGIN_ROOTS["em-workflow"])
        groups = _bash_pretooluse_groups(cls.config)
        assert len(groups) == 1, f"expected exactly one PreToolUse(Bash) group, found {len(groups)}"
        cls.order = _script_filenames_in_order(groups[0])

    def test_muse_guard_precedes_destructive_guard(self):
        self.assertIn("muse_guard.py", self.order)
        self.assertIn("destructive-guard.py", self.order)
        self.assertLess(
            self.order.index("muse_guard.py"),
            self.order.index("destructive-guard.py"),
            f"muse_guard.py must run before destructive-guard.py's blanket allow; order={self.order}",
        )

    def test_destructive_guard_remains_last_among_decision_capable_guards(self):
        # heredoc-stdin-guard.py (heredoc-stdin-guard task0001) runs after
        # destructive-guard.py too, but it never returns a permission
        # decision -- only `updatedInput` or nothing (heredoc-stdin-guard
        # IMPLEMENTATION.md D4) -- so its tail position does not reopen
        # the "blanket allow ends the decision" gate this test protects.
        decision_capable = [n for n in self.order if n != "heredoc-stdin-guard.py"]
        self.assertEqual(decision_capable[-1], "destructive-guard.py")

    def test_extracted_order_matches_the_pinned_ordered_guard_constant(self):
        # Imports the sibling module's own EXPECTED_BASH_GUARD_ORDER
        # constant (rather than hardcoding a second copy of it here) so the
        # two tests can never silently drift apart.
        spec = importlib.util.spec_from_file_location(
            "_test_guardrail_hooks_migration_for_registration_pin",
            REPO_ROOT / "tests" / "test_guardrail_hooks_migration.py",
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        self.assertEqual(self.order, module.EXPECTED_BASH_GUARD_ORDER)


class TestNoDuplicateRegistrationUnderOneEvent(unittest.TestCase):
    def test_no_script_is_registered_twice_under_the_same_event_in_either_plugin(self):
        for name, root in PLUGIN_ROOTS.items():
            with self.subTest(plugin=name):
                config, path = _load_hooks_config(root)
                seen = {}
                duplicates = []
                for event, groups in config.get("hooks", {}).items():
                    for group in groups:
                        for hook in group.get("hooks", []):
                            command = hook.get("command", "")
                            script = command.rsplit("/", 1)[-1]
                            key = (event, script)
                            if key in seen:
                                duplicates.append(key)
                            seen[key] = True
                self.assertEqual(duplicates, [], f"duplicate registration(s) in {path}: {duplicates}")


class TestEveryReferencedScriptExists(unittest.TestCase):
    """Every script either hooks.json file references resolves to a real
    file under that plugin's hooks/ directory -- covers em-review's file,
    which is new for this feature (em-workflow's own pre-existing entries
    are already covered by tests/test_hooks_registration.py)."""

    def test_every_hooks_json_referenced_script_exists(self):
        for name, root in PLUGIN_ROOTS.items():
            with self.subTest(plugin=name):
                config, path = _load_hooks_config(root)
                missing = []
                for groups in config.get("hooks", {}).values():
                    for group in groups:
                        for hook in group.get("hooks", []):
                            command = hook.get("command", "")
                            script_name = command.rsplit("/", 1)[-1]
                            script_path = root / "hooks" / script_name
                            if not script_path.is_file():
                                missing.append(str(script_path))
                self.assertEqual(missing, [], f"missing script file(s): {missing}")


class TestMuseGuardItselfIsExecutableInBothPlugins(unittest.TestCase):
    """The executable bit specifically for muse_guard.py -- not a
    repository-wide claim (several pre-existing `.py` hooks, launched via
    an explicit `python3` interpreter the same way muse_guard.py is, do not
    carry the bit either, since it is not functionally required for that
    invocation form)."""

    def test_muse_guard_is_executable_in_both_plugins(self):
        for name, root in PLUGIN_ROOTS.items():
            with self.subTest(plugin=name):
                script_path = root / "hooks" / "muse_guard.py"
                self.assertTrue(script_path.is_file())
                self.assertTrue(os.access(script_path, os.X_OK))


if __name__ == "__main__":
    unittest.main()
