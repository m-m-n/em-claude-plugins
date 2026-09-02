"""Tests for the guardrail hook / rule migration into the em-workflow plugin.

Four PreToolUse guard hooks (`gitleaks-precommit.sh`, `kill-guard.py`,
`gitleaks-write-guard.sh`, `destructive-guard.py`) and two rule documents
(`branch-session-scope.md`, `workflow-failure-recovery.md`) previously lived
in the user's global `~/.claude/` configuration and were registered from
`~/.claude/settings.json`. They now ship with the plugin, which makes three
properties repository invariants rather than facts about one machine:

1. **Order.** All four PreToolUse(Bash) guards live in ONE matcher group, so
   `hooks.json`'s array order IS the execution order.
   `destructive-guard.py` returns a blanket `allow` for anything its
   blocklist does not match, which ends the permission decision for that
   call — it must therefore run LAST, after `bash_guard.py` has had the
   chance to apply the workflow command-approval gate. A reordering that
   put it earlier would silently disable that gate while every other test
   in this repository stayed green.

2. **Fail-open gitleaks resolution.** Both gitleaks hooks resolve the binary
   `command -v` first, then the mise shims path, and scan nothing at all
   when neither resolves. Turning that into fail-closed would block every
   commit and every file write on a machine without gitleaks installed. The
   resolution order and all three outcomes are exercised here as behaviour
   (subprocess runs against fabricated `gitleaks` binaries), not as a text
   match on the source.

3. **The rules are reachable.** A reference document nothing points at is
   dead weight; each of the two migrated rules must be cited from at least
   one other file under `em-workflow/`.

Registration *shape* (interpreter/extension pairing, per-script timeouts,
referenced files existing) is the manifest-driven job of
tests/test_hooks_registration.py and is deliberately not duplicated here.

Standard library only, per test/README.md.
"""

import json
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_ROOT = REPO_ROOT / "em-workflow"
HOOKS_DIR = PLUGIN_ROOT / "hooks"
HOOKS_JSON_PATH = HOOKS_DIR / "hooks.json"
REFERENCES_DIR = PLUGIN_ROOT / "references"

MIGRATED_HOOK_FILES = (
    "gitleaks-precommit.sh",
    "kill-guard.py",
    "gitleaks-write-guard.sh",
    "destructive-guard.py",
)

# The execution order the PreToolUse(Bash) group must declare, verbatim.
# `failed-run-cleanup-guard.py` runs after `bash_guard.py` and before
# `destructive-guard.py`'s blanket allow (failed-run-cleanup-guard
# IMPLEMENTATION.md decision D1).
EXPECTED_BASH_GUARD_ORDER = [
    "gitleaks-precommit.sh",
    "kill-guard.py",
    "bash_guard.py",
    "failed-run-cleanup-guard.py",
    "destructive-guard.py",
]

MIGRATED_RULE_FILES = (
    "branch-session-scope.md",
    "workflow-failure-recovery.md",
)

REPO_RULES_DIR = REPO_ROOT / ".claude" / "rules"

# Every rule file present today, discovered rather than hand-typed so a
# rename does not leave a stale name behind the way `plugin-version-bump.md`
# did (decision `ac11-stale-guard`, phase-state/rework.yaml
# pending_decisions[0]).
REPO_RULE_FILES = tuple(sorted(p.name for p in REPO_RULES_DIR.glob("*.md")))

# The subset this project cannot lose without noticing: rules carrying the
# `core-` prefix convention. Named explicitly (not derived) so that deleting
# one of these fails loudly, naming the missing rule (see
# .claude/rules/core-plugin-structure.md's own naming rationale).
CORE_REPO_RULE_FILES = (
    "core-plugin-structure.md",
    "core-plugin-version-bump.md",
)


def _missing_rule_files(names, rules_dir):
    """The subset of `names` that does not exist as a file under `rules_dir`."""
    return [n for n in names if not (rules_dir / n).is_file()]


def _empty_rule_files(names, rules_dir):
    """The subset of `names` whose file under `rules_dir` has zero bytes."""
    return [n for n in names if (rules_dir / n).stat().st_size == 0]


def _rule_files_without_a_level1_heading(names, rules_dir):
    """The subset of `names` whose file does not open on a level-1 heading
    (a line starting with a single `# `), i.e. does not name what it
    governs."""
    return [
        n
        for n in names
        if not (rules_dir / n).read_text().lstrip().startswith("# ")
    ]

# Binaries the two shell hooks need on PATH regardless of whether gitleaks
# itself resolves. Symlinked into each test's sandboxed PATH so that the
# absence of `gitleaks` can be simulated without also breaking the script.
SANDBOX_PATH_BINARIES = ("bash", "cat", "jq", "grep", "git")

# Resolved in the PARENT's PATH: the sandbox deliberately strips PATH down,
# so the interpreter itself has to be named absolutely.
BASH = shutil.which("bash")


def _script_filenames_in(group):
    """The bare script filenames a hooks.json matcher group registers, in
    declaration order."""
    names = []
    for hook in group.get("hooks", []):
        command = hook.get("command", "")
        names.append(command.rsplit("/", 1)[-1])
    return names


def _pretooluse_group(config, matcher):
    groups = [
        g for g in config.get("hooks", {}).get("PreToolUse", [])
        if g.get("matcher") == matcher
    ]
    if len(groups) != 1:
        raise AssertionError(
            f"expected exactly one PreToolUse group with matcher {matcher!r}, "
            f"found {len(groups)}"
        )
    return groups[0]


def _write_executable(path, body):
    path.write_text(body)
    path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)


class GitleaksHookSandbox:
    """A temporary HOME + PATH in which `gitleaks` resolution is fully
    controlled: PATH contains only symlinks to the handful of real binaries
    the hooks call, plus whatever fake `gitleaks` a test installs."""

    def __init__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        self.home = self.root / "home"
        self.bin = self.root / "bin"
        self.home.mkdir()
        self.bin.mkdir()
        for name in SANDBOX_PATH_BINARIES:
            real = shutil.which(name)
            if real is None:
                raise unittest.SkipTest(f"{name} is not available on PATH")
            (self.bin / name).symlink_to(real)

    def close(self):
        self._tmp.cleanup()

    @property
    def shims_dir(self):
        return self.home / ".local" / "share" / "mise" / "shims"

    def install_path_gitleaks(self, body):
        _write_executable(self.bin / "gitleaks", body)

    def install_shim_gitleaks(self, body):
        self.shims_dir.mkdir(parents=True, exist_ok=True)
        _write_executable(self.shims_dir / "gitleaks", body)

    def env(self):
        return {
            "HOME": str(self.home),
            "PATH": str(self.bin),
            # Keeps bash from sourcing anything that could re-add a real
            # gitleaks to PATH behind the test's back.
            "BASH_ENV": "",
        }

    def run_hook(self, script_name, payload):
        if BASH is None:
            raise unittest.SkipTest("bash is not available on PATH")
        return subprocess.run(
            [BASH, str(HOOKS_DIR / script_name)],
            input=json.dumps(payload),
            capture_output=True,
            text=True,
            env=self.env(),
        )


# A fake gitleaks that reports "secret found" the way the hooks ask it to
# (`--exit-code 9`), and one that reports a clean scan.
LEAK_FOUND = "#!/usr/bin/env bash\nexit 9\n"
NO_LEAK = "#!/usr/bin/env bash\nexit 0\n"

WRITE_PAYLOAD = {
    "tool_input": {
        "file_path": "/tmp/example.env",
        "content": "AWS_SECRET_ACCESS_KEY=not-a-real-secret",
    }
}
COMMIT_PAYLOAD = {"tool_input": {"command": "git commit -m 'x'"}, "cwd": "/tmp"}


class TestMigratedHookFilesArePresentAndExecutable(unittest.TestCase):
    """The four guard scripts ship with the plugin, with their executable
    bit intact (they are launched through an explicit interpreter, but the
    bit is what lets them still be run directly for debugging)."""

    def test_every_migrated_hook_file_exists(self):
        missing = [n for n in MIGRATED_HOOK_FILES if not (HOOKS_DIR / n).is_file()]
        self.assertEqual(missing, [], f"missing migrated hook files: {missing}")

    def test_every_migrated_hook_file_is_executable(self):
        not_executable = [
            n
            for n in MIGRATED_HOOK_FILES
            if (HOOKS_DIR / n).is_file()
            and not os.access(HOOKS_DIR / n, os.X_OK)
        ]
        self.assertEqual(
            not_executable, [], f"migrated hooks lack the executable bit: {not_executable}"
        )


class TestPreToolUseBashGuardOrder(unittest.TestCase):
    """The blanket-allow guard runs last -- see this module's docstring."""

    @classmethod
    def setUpClass(cls):
        cls.config = json.loads(HOOKS_JSON_PATH.read_text())

    def test_bash_guards_are_declared_in_the_required_order(self):
        group = _pretooluse_group(self.config, "Bash")
        self.assertEqual(_script_filenames_in(group), EXPECTED_BASH_GUARD_ORDER)

    def test_destructive_guard_is_last(self):
        group = _pretooluse_group(self.config, "Bash")
        names = _script_filenames_in(group)
        self.assertEqual(
            names[-1],
            "destructive-guard.py",
            "destructive-guard.py returns a blanket allow and must run after "
            f"every other Bash guard; order is {names}",
        )

    def test_bash_guard_still_precedes_the_blanket_allow(self):
        names = _script_filenames_in(_pretooluse_group(self.config, "Bash"))
        self.assertLess(
            names.index("bash_guard.py"),
            names.index("destructive-guard.py"),
            "the workflow command-approval gate must be consulted before the "
            "blanket allow ends the decision",
        )

    def test_write_edit_multiedit_registers_the_write_guard(self):
        group = _pretooluse_group(self.config, "Write|Edit|MultiEdit")
        self.assertIn("gitleaks-write-guard.sh", _script_filenames_in(group))


class GitleaksResolutionTestCase(unittest.TestCase):
    def setUp(self):
        self.sandbox = GitleaksHookSandbox()
        self.addCleanup(self.sandbox.close)


class TestGitleaksWriteGuardResolution(GitleaksResolutionTestCase):
    def test_blocks_the_write_when_a_path_gitleaks_reports_a_leak(self):
        self.sandbox.install_path_gitleaks(LEAK_FOUND)
        result = self.sandbox.run_hook("gitleaks-write-guard.sh", WRITE_PAYLOAD)
        self.assertEqual(result.returncode, 2, result.stderr)

    def test_allows_the_write_when_gitleaks_reports_no_leak(self):
        self.sandbox.install_path_gitleaks(NO_LEAK)
        result = self.sandbox.run_hook("gitleaks-write-guard.sh", WRITE_PAYLOAD)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_falls_back_to_the_mise_shim_when_gitleaks_is_not_on_path(self):
        self.sandbox.install_shim_gitleaks(LEAK_FOUND)
        result = self.sandbox.run_hook("gitleaks-write-guard.sh", WRITE_PAYLOAD)
        self.assertEqual(result.returncode, 2, result.stderr)

    def test_path_gitleaks_takes_precedence_over_the_mise_shim(self):
        self.sandbox.install_path_gitleaks(NO_LEAK)
        self.sandbox.install_shim_gitleaks(LEAK_FOUND)
        result = self.sandbox.run_hook("gitleaks-write-guard.sh", WRITE_PAYLOAD)
        self.assertEqual(
            result.returncode,
            0,
            "the PATH binary must win over the mise shim: " + result.stderr,
        )

    def test_fails_open_when_gitleaks_cannot_be_resolved_at_all(self):
        result = self.sandbox.run_hook("gitleaks-write-guard.sh", WRITE_PAYLOAD)
        self.assertEqual(
            result.returncode,
            0,
            "a machine without gitleaks must not have every write blocked: "
            + result.stderr,
        )


class TestGitleaksPrecommitResolution(GitleaksResolutionTestCase):
    def test_fails_open_when_gitleaks_cannot_be_resolved_at_all(self):
        result = self.sandbox.run_hook("gitleaks-precommit.sh", COMMIT_PAYLOAD)
        self.assertEqual(
            result.returncode,
            0,
            "a machine without gitleaks must not have every commit blocked: "
            + result.stderr,
        )

    def test_ignores_commands_that_are_not_a_git_commit(self):
        self.sandbox.install_path_gitleaks(LEAK_FOUND)
        result = self.sandbox.run_hook(
            "gitleaks-precommit.sh", {"tool_input": {"command": "ls -la"}, "cwd": "/tmp"}
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_source_resolves_path_before_the_mise_shim(self):
        """The precommit hook's happy path needs a real repository to drive
        end-to-end, so the ORDER of its two resolution branches is pinned on
        the source here; the outcomes themselves are proven behaviourally by
        the write-guard cases above, which share the identical block."""
        source = (HOOKS_DIR / "gitleaks-precommit.sh").read_text()
        self.assertIn("command -v gitleaks", source)
        self.assertIn(".local/share/mise/shims/gitleaks", source)
        self.assertLess(
            source.index("command -v gitleaks"),
            source.index(".local/share/mise/shims/gitleaks"),
            "PATH resolution must be attempted before the mise shim fallback",
        )


class TestMigratedRulesAreReferenced(unittest.TestCase):
    """A reference document nothing cites is dead weight."""

    def test_every_migrated_rule_exists_under_references(self):
        missing = [n for n in MIGRATED_RULE_FILES if not (REFERENCES_DIR / n).is_file()]
        self.assertEqual(missing, [], f"missing migrated rules: {missing}")

    def test_every_migrated_rule_is_cited_from_elsewhere_in_the_plugin(self):
        uncited = []
        for name in MIGRATED_RULE_FILES:
            citing = []
            for path in PLUGIN_ROOT.rglob("*.md"):
                if path.name == name or "__pycache__" in path.parts:
                    continue
                if name in path.read_text():
                    citing.append(str(path.relative_to(REPO_ROOT)))
            if not citing:
                uncited.append(name)
        self.assertEqual(
            uncited, [], f"migrated rules cited from nowhere in the plugin: {uncited}"
        )


class TestReadmeDocumentsTheClassifierSideEffect(unittest.TestCase):
    """The plugin silently turns off Claude Code's auto mode classifier for
    Bash; a user installing it has to be able to find that out."""

    @classmethod
    def setUpClass(cls):
        cls.readme = (PLUGIN_ROOT / "README.md").read_text()

    def test_readme_names_the_opt_out_flag(self):
        self.assertIn("ALLOW_NON_DESTRUCTIVE", self.readme)

    def test_readme_states_the_classifier_is_bypassed(self):
        self.assertIn("classifier", self.readme)

    def test_readme_names_every_bundled_guard_hook(self):
        missing = [n for n in MIGRATED_HOOK_FILES if n not in self.readme]
        self.assertEqual(missing, [], f"guard hooks undocumented in README: {missing}")

    def test_readme_records_the_known_gap(self):
        self.assertIn("gcloud projects add-iam-policy-binding", self.readme)


# This class used to assert that the root CLAUDE.md pointed at
# `.claude/rules/` and named every rule file -- a CLAUDE.md-as-index
# convention that current policy has retired: CLAUDE.md now carries only the
# product's value and the users it serves, and every rule lives under
# `.claude/rules/` with nothing indexing it from CLAUDE.md. Those two
# assertions are replaced below by assertions of equal strength evaluated
# directly against `.claude/rules/` (non-empty, self-naming via a level-1
# heading), per decision `ac11-stale-guard` (phase-state/rework.yaml
# pending_decisions[0]).
class TestRepositoryRulesAreInPlace(unittest.TestCase):
    """The repository-specific rules moved out of the user's global
    configuration and into the repository they actually govern."""

    def test_every_repository_rule_exists(self):
        missing = _missing_rule_files(REPO_RULE_FILES, REPO_RULES_DIR)
        self.assertEqual(missing, [], f"missing repository rules: {missing}")

    def test_repository_rule_list_is_not_empty(self):
        self.assertNotEqual(REPO_RULE_FILES, ())

    def test_existence_check_fails_for_a_rule_that_does_not_exist(self):
        missing = _missing_rule_files(
            REPO_RULE_FILES + ("does-not-exist.md",), REPO_RULES_DIR
        )
        self.assertEqual(missing, ["does-not-exist.md"])

    def test_existence_check_fails_against_an_empty_rules_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            missing = _missing_rule_files(REPO_RULE_FILES, Path(tmp))
        self.assertEqual(sorted(missing), sorted(REPO_RULE_FILES))
        self.assertNotEqual(missing, [])

    def test_core_prefixed_rules_are_present(self):
        missing = _missing_rule_files(CORE_REPO_RULE_FILES, REPO_RULES_DIR)
        self.assertEqual(missing, [], f"missing core repository rules: {missing}")

    def test_every_repository_rule_file_is_non_empty(self):
        empty = _empty_rule_files(REPO_RULE_FILES, REPO_RULES_DIR)
        self.assertEqual(empty, [], f"empty repository rule files: {empty}")

    def test_non_empty_check_fails_for_an_empty_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            rules_dir = Path(tmp)
            (rules_dir / "empty.md").write_text("")
            empty = _empty_rule_files(("empty.md",), rules_dir)
        self.assertEqual(empty, ["empty.md"])

    def test_every_repository_rule_file_names_what_it_governs(self):
        missing_heading = _rule_files_without_a_level1_heading(
            REPO_RULE_FILES, REPO_RULES_DIR
        )
        self.assertEqual(
            missing_heading,
            [],
            f"repository rule files without a level-1 heading: {missing_heading}",
        )

    def test_heading_check_fails_for_a_file_without_a_level_1_heading(self):
        with tempfile.TemporaryDirectory() as tmp:
            rules_dir = Path(tmp)
            (rules_dir / "no-heading.md").write_text("no heading here\n")
            missing_heading = _rule_files_without_a_level1_heading(
                ("no-heading.md",), rules_dir
            )
        self.assertEqual(missing_heading, ["no-heading.md"])


if __name__ == "__main__":
    unittest.main()
