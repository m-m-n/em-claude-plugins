"""Tests for task0001 (feature-docs/worker-self-write-digest): the self-write
digest script `em-workflow/scripts/self-write-digest.py`.

The script identifies the paths a worker dispatch legitimately wrote (the
self-write set) from the orchestrator-observed change set, and builds the
return-time `digest_source` in which each of those paths carries its
dispatch-time digest. The tests load the hyphenated script by file path for
the unit and scenario checks, and run it as a child process for the command
line checks. The R1-normalized digest is computed inside this module, from
the normalization procedure of `references/contracts/worker-envelope.md`
(Rule R1); the script itself never hashes.

Covers task0001 Acceptance Criteria
(feature-docs/worker-self-write-digest/tasks/task0001.md):

- AC-1 (FR2, FR3; TS-5, TS-6, TS-7; TM-1, TM-2): identification admits
  exactly the paths the membership matrix admits (TestMembershipMatrix,
  TestRegenerateTargets, TestTargetPrecedence, TestAllowedRootContainment,
  TestObservedChangesOnly).
- AC-2 (FR1, NFR1; TS-7, TS-13): the substitution contract
  (TestSubstitution).
- AC-3 (FR1, FR3, FR11; TS-1, TS-2, TS-3): designer, implementation-planner
  and rework-planner self-writes are not stale (TestScenarioDigests).
- AC-4 (FR4, FR11; TS-4, TS-6): every other change is still stale
  (TestOtherChangesStayStale).
- AC-5 (FR5; TS-2, TS-3): `validate-worker-output.py --dry-run-apply` with
  the substituted digest_source (TestValidatorDryRunApply).
- AC-6 (FR6, FR7; TS-8; TM-4): resume reproduction
  (TestResumeReproduction).
- AC-7 (FR10; TM-3): the command line contract (TestCliContract,
  TestCliRejections, TestIsolation, TestScriptFileProperties).

Also covers task0001 of feature-docs/self-write-digest-path-normalization
(allowed-root containment agrees with scope validation):

- AC-1 (TS-1): TestPathNormalizationReproduction.
- AC-2 (TS-2, TS-3): the later rows of CONTAINMENT_CASES.
- AC-3 (TS-4): TestNoSegmentRoots.
- AC-4 (TS-5; TM-1): TestContainmentAgreesWithScopeValidation, which loads
  `validate-worker-output.py` by file path (only this module does).
- AC-5 (TS-7): TestNormalizationDocstrings (the document half is in
  test_self_write_digest_docs.py).
- AC-6 (TS-6): TestIsolation, the module-loading facility checks.

Every child process carries a timeout, so a hang becomes a failure.
"""

import ast
import contextlib
import copy
import hashlib
import importlib.util
import inspect
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "em-workflow" / "scripts" / "self-write-digest.py"
VALIDATOR = REPO_ROOT / "em-workflow" / "scripts" / "validate-worker-output.py"
ARTIFACT_DIGEST = REPO_ROOT / "em-workflow" / "scripts" / "artifact-digest.py"
PATCH_FIXTURES = (
    REPO_ROOT / "em-workflow" / "references" / "fixtures" / "workflow-patch"
)

CALL_TIMEOUT_SECONDS = 30

ACTIONS = (
    "create",
    "replace_own",
    "replace_authorized",
    "extend_only",
    "regenerate",
    "preserve",
)
KINDS = ("created", "modified", "deleted")

LOCALE_VARIABLES = (
    "LANG",
    "LANGUAGE",
    "LC_ALL",
    "LC_CTYPE",
    "PYTHONUTF8",
    "PYTHONIOENCODING",
    "PYTHONCOERCECLOCALE",
)


# ------------------------------------------------------------ the module ----

_LOADED = None


def script_module():
    """The script, loaded by file path on first use.

    Loading is lazy so that importing this test module never touches the
    script (the record check imports every test module without running it).
    """
    global _LOADED
    if _LOADED is None:
        spec = importlib.util.spec_from_file_location(
            "self_write_digest_under_test", SCRIPT
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _LOADED = module
    return _LOADED


_VALIDATOR_LOADED = None


def validator_module():
    """`validate-worker-output.py`, loaded by file path on first use.

    It is the reference for allowed-root containment
    (`path_is_contained_in_root`). Only the tests load it: the script under
    test never does. Loading is lazy so that importing this test module
    executes neither script.
    """
    global _VALIDATOR_LOADED
    if _VALIDATOR_LOADED is None:
        spec = importlib.util.spec_from_file_location(
            "validate_worker_output_reference", VALIDATOR
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _VALIDATOR_LOADED = module
    return _VALIDATOR_LOADED


# ------------------------------------------------------------- builders ----


def fake(label):
    """A placeholder `sha256:` digest string derived from a label."""
    return "sha256:" + hashlib.sha256(label.encode("utf-8")).hexdigest()


def r1_digest(digest_source):
    """R1 normalization: sort every object's keys, compact separators,
    non-ASCII unescaped, sha256 of the UTF-8 bytes."""
    text = json.dumps(
        digest_source,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def make_source(digest_inputs, **overrides):
    """A digest_source with the seven structural members."""
    source = {
        "worker": "implementation-planner",
        "mode": "interactive",
        "workflow_blob": "8f17c04",
        "digest_inputs": dict(digest_inputs),
        "value_inputs": {"task_description": fake("task description")},
        "answers_digest": fake("answers"),
        "write_policy_digest": fake("write policy"),
    }
    source.update(overrides)
    return source


def change(path, kind):
    return {"path": path, "kind": kind}


def target(path, action, source=None):
    entry = {"path": path, "action": action, "expect_digest": None}
    if source is not None:
        entry["source"] = source
    return entry


def identify(changes, targets, roots):
    return script_module().identify_self_writes(
        copy.deepcopy(changes), {"targets": copy.deepcopy(targets)}, list(roots)
    )


class Scenario:
    """One dispatch / return pair, with the policy that governed it."""

    def __init__(
        self,
        dispatch_inputs,
        current_inputs,
        changes,
        targets,
        roots,
        dispatch_overrides=None,
        current_overrides=None,
    ):
        self.dispatch = make_source(dispatch_inputs, **(dispatch_overrides or {}))
        self.current = make_source(current_inputs, **(current_overrides or {}))
        self.changes = changes
        self.targets = targets
        self.roots = roots

    def write_policy(self):
        return {"targets": copy.deepcopy(self.targets)}

    def run(self):
        """(self_write_set, substituted digest_source) through the module."""
        return script_module().identify_and_substitute(
            copy.deepcopy(self.dispatch),
            copy.deepcopy(self.current),
            copy.deepcopy(self.changes),
            self.write_policy(),
            list(self.roots),
        )

    def document(self):
        return {
            "operation": "identify_and_substitute",
            "dispatch_digest_source": copy.deepcopy(self.dispatch),
            "current_digest_source": copy.deepcopy(self.current),
            "observed_changes": copy.deepcopy(self.changes),
            "write_policy": self.write_policy(),
            "allowed_write_roots": list(self.roots),
        }

    @property
    def dispatch_digest(self):
        return r1_digest(self.dispatch)

    @property
    def current_digest(self):
        return r1_digest(self.current)


FEATURE = "feature-docs/example"
SPEC = f"{FEATURE}/SPEC.md"
REQUIREMENTS = f"{FEATURE}/REQUIREMENTS.md"
IMPLEMENTATION = f"{FEATURE}/IMPLEMENTATION.md"
VERIFICATION = f"{FEATURE}/VERIFICATION.md"
THREAT_MODEL = f"{FEATURE}/THREAT-MODEL.md"
TASKS_ROOT = f"{FEATURE}/tasks"
TASK_1 = f"{TASKS_ROOT}/task0001.md"
TASK_2 = f"{TASKS_ROOT}/task0002.md"
TASK_3 = f"{TASKS_ROOT}/task0003.md"
TOKENS_YAML = "design-system/tokens.yaml"
TOKENS_HTML = "design-system/tokens.html"
CONTRACT = "em-workflow/references/contracts/planner-contract.md"


def designer_scenario():
    """TS-1: tokens.yaml modified under extend_only, tokens.html modified
    under regenerate with that source."""
    dispatch = {
        SPEC: fake("spec"),
        TOKENS_YAML: fake("tokens.yaml v1"),
        TOKENS_HTML: fake("tokens.html v1"),
        "em-workflow/references/contracts/designer-contract.md": fake("designer"),
    }
    current = dict(dispatch)
    current[TOKENS_YAML] = fake("tokens.yaml v2")
    current[TOKENS_HTML] = fake("tokens.html v2")
    return Scenario(
        dispatch,
        current,
        [change(TOKENS_YAML, "modified"), change(TOKENS_HTML, "modified")],
        [
            target(TOKENS_YAML, "extend_only"),
            target(TOKENS_HTML, "regenerate", source=TOKENS_YAML),
        ],
        [f"{FEATURE}/design/mockups"],
    )


def planner_scenario():
    """TS-2: IMPLEMENTATION / VERIFICATION / THREAT-MODEL modified under
    replace_own, a new task plan created under the tasks/ root."""
    dispatch = {
        SPEC: fake("spec"),
        REQUIREMENTS: fake("requirements"),
        IMPLEMENTATION: fake("implementation v1"),
        VERIFICATION: fake("verification v1"),
        THREAT_MODEL: fake("threat model v1"),
        TASK_1: fake("task0001 v1"),
        TASK_2: fake("task0002 v1"),
        CONTRACT: fake("planner contract"),
    }
    current = dict(dispatch)
    current[IMPLEMENTATION] = fake("implementation v2")
    current[VERIFICATION] = fake("verification v2")
    current[THREAT_MODEL] = fake("threat model v2")
    current[TASK_3] = fake("task0003 v1")
    return Scenario(
        dispatch,
        current,
        [
            change(IMPLEMENTATION, "modified"),
            change(VERIFICATION, "modified"),
            change(THREAT_MODEL, "modified"),
            change(TASK_3, "created"),
        ],
        [
            target(IMPLEMENTATION, "replace_own"),
            target(VERIFICATION, "replace_own"),
            target(THREAT_MODEL, "replace_own"),
        ],
        [TASKS_ROOT],
    )


def rework_scenario():
    """TS-3: IMPLEMENTATION / VERIFICATION modified under replace_own, a new
    file created under the tasks/ root."""
    dispatch = {
        SPEC: fake("spec"),
        IMPLEMENTATION: fake("implementation v1"),
        VERIFICATION: fake("verification v1"),
        THREAT_MODEL: fake("threat model v1"),
        TASK_1: fake("task0001 v1"),
        "em-workflow/references/contracts/rework-planner-contract.md": fake(
            "rework planner contract"
        ),
    }
    current = dict(dispatch)
    current[IMPLEMENTATION] = fake("implementation v2")
    current[VERIFICATION] = fake("verification v2")
    current[TASK_2] = fake("task0002 v1")
    return Scenario(
        dispatch,
        current,
        [
            change(IMPLEMENTATION, "modified"),
            change(VERIFICATION, "modified"),
            change(TASK_2, "created"),
        ],
        [
            target(IMPLEMENTATION, "replace_own"),
            target(VERIFICATION, "replace_own"),
        ],
        [TASKS_ROOT],
    )


# ----------------------------------------------------- child processes ----


def clean_env(**overrides):
    env = {k: v for k, v in os.environ.items() if k not in LOCALE_VARIABLES}
    env.update(overrides)
    return env


def run_python(argv, cwd=None, env=None):
    """`sys.executable *argv`, a timeout turned into a failure."""
    try:
        return subprocess.run(
            [sys.executable, *argv],
            cwd=cwd,
            env=env,
            capture_output=True,
            timeout=CALL_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        raise AssertionError(
            f"child process did not return within {CALL_TIMEOUT_SECONDS}s "
            f"(hang): {argv!r}"
        ) from None


def run_script(*args, cwd=None, env=None):
    return run_python([str(SCRIPT), *[str(a) for a in args]], cwd=cwd, env=env)


def decode_output(proc):
    """The single JSON object the contract promises on stdout."""
    value = json.loads(proc.stdout.decode("utf-8"))
    if not isinstance(value, dict):
        raise AssertionError(f"stdout is not a JSON object: {proc.stdout!r}")
    return value


class TempDirCase(unittest.TestCase):
    def setUp(self):
        holder = tempfile.TemporaryDirectory()
        self.addCleanup(holder.cleanup)
        self.tmp = Path(os.path.realpath(holder.name))

    def write_json(self, name, value):
        path = self.tmp / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return path

    def write_bytes(self, name, data):
        path = self.tmp / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def cli(self, document, name="input.json"):
        """Run the CLI on `document` written to the temp directory."""
        path = self.write_json(name, document)
        return run_script(path, cwd=self.tmp)

    def assert_succeeded(self, proc):
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stderr, b"")

    def assert_rejected(self, proc):
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertEqual(proc.stdout, b"")
        # A rejection explains itself on stderr, led by the script's own name.
        # This rules out a child that never reached the script: the
        # interpreter's "can't open file" error also exits 2 with empty
        # stdout, but it carries no such lead.
        self.assertTrue(
            proc.stderr.startswith(b"self-write-digest: "), proc.stderr
        )
        self.assertNotIn(b"Traceback", proc.stderr)


# ------------------------------------------------------------------ AC-1 ----

MATRIX_TARGETS = [
    target("m/create.md", "create"),
    target("m/replace_own.md", "replace_own"),
    target("m/replace_authorized.md", "replace_authorized"),
    target("m/extend_only.yaml", "extend_only"),
    target("m/regen.html", "regenerate", source="m/extend_only.yaml"),
    target("m/preserve.md", "preserve"),
]
MATRIX_ROOTS = ["m/root"]

# (row label, path, member when created, modified, deleted)
MATRIX_ROWS = [
    ("create target", "m/create.md", (True, False, False)),
    ("replace_own target", "m/replace_own.md", (False, True, False)),
    ("replace_authorized target", "m/replace_authorized.md", (False, True, False)),
    ("extend_only target", "m/extend_only.yaml", (False, True, False)),
    ("preserve target", "m/preserve.md", (False, False, False)),
    ("not a target, inside an allowed root", "m/root/new.md", (True, False, False)),
    ("neither a target nor inside a root", "m/other/new.md", (False, False, False)),
]


class TestMembershipMatrix(unittest.TestCase):
    """AC-1: every cell of the matrix (regenerate row: TestRegenerateTargets)."""

    def test_ac1_every_non_regenerate_cell_follows_the_matrix(self):
        for label, path, cells in MATRIX_ROWS:
            for kind, is_member in zip(KINDS, cells):
                with self.subTest(row=label, kind=kind):
                    got = identify(
                        [change(path, kind)], MATRIX_TARGETS, MATRIX_ROOTS
                    )
                    self.assertEqual(got, [path] if is_member else [])

    def test_ac1_the_table_covers_every_action_and_both_root_rows(self):
        # Non-vacuity: a table that dropped a row would pass trivially.
        self.assertEqual({t["action"] for t in MATRIX_TARGETS}, set(ACTIONS))
        labels = {label for label, _, _ in MATRIX_ROWS}
        self.assertIn("not a target, inside an allowed root", labels)
        self.assertIn("neither a target nor inside a root", labels)
        self.assertEqual(
            sum(cell for _, _, cells in MATRIX_ROWS for cell in cells), 5
        )

    def test_ac1_the_result_is_a_list_ascending_without_duplicates(self):
        changes = [
            change("m/root/b.md", "created"),
            change("m/create.md", "created"),
            change("m/root/a.md", "created"),
            change("m/replace_own.md", "modified"),
        ]
        got = identify(changes, MATRIX_TARGETS, MATRIX_ROOTS)
        self.assertIsInstance(got, list)
        self.assertEqual(
            got,
            ["m/create.md", "m/replace_own.md", "m/root/a.md", "m/root/b.md"],
        )

    def test_ac1_no_observed_change_gives_an_empty_set(self):
        self.assertEqual(identify([], MATRIX_TARGETS, MATRIX_ROOTS), [])

    def test_ac1_a_modified_file_covered_only_by_a_root_is_not_admitted(self):
        # TM-2
        got = identify([change("m/root/existing.md", "modified")], [], ["m/root"])
        self.assertEqual(got, [])

    def test_ac1_a_modified_preserve_target_is_not_admitted(self):
        # TM-2
        got = identify(
            [change("m/preserve.md", "modified")],
            [target("m/preserve.md", "preserve")],
            ["m"],
        )
        self.assertEqual(got, [])


class TestRegenerateTargets(unittest.TestCase):
    """AC-1: a regenerate target is admitted only through its source."""

    SOURCE = "m/extend_only.yaml"
    REGEN = "m/regen.html"

    def ids(self, changes, targets=None):
        return identify(changes, targets or MATRIX_TARGETS, MATRIX_ROOTS)

    def test_ac1_modified_with_its_source_admitted_is_a_member(self):
        got = self.ids(
            [change(self.SOURCE, "modified"), change(self.REGEN, "modified")]
        )
        self.assertEqual(got, [self.SOURCE, self.REGEN])

    def test_ac1_modified_while_its_source_did_not_change_is_not_a_member(self):
        # TM-2
        self.assertEqual(self.ids([change(self.REGEN, "modified")]), [])

    def test_ac1_a_source_that_is_not_a_member_does_not_admit_the_target(self):
        for kind in ("created", "deleted"):
            with self.subTest(source_kind=kind):
                got = self.ids(
                    [change(self.SOURCE, kind), change(self.REGEN, "modified")]
                )
                self.assertNotIn(self.REGEN, got)

    def test_ac1_a_source_admitted_as_a_created_file_admits_the_target(self):
        targets = [
            target("m/seed.txt", "create"),
            target("m/out.html", "regenerate", source="m/seed.txt"),
        ]
        got = identify(
            [change("m/seed.txt", "created"), change("m/out.html", "modified")],
            targets,
            [],
        )
        self.assertEqual(got, ["m/out.html", "m/seed.txt"])

    def test_ac1_only_the_modified_kind_is_admitted_for_a_regenerate_target(self):
        for kind in ("created", "deleted"):
            with self.subTest(kind=kind):
                got = self.ids(
                    [change(self.SOURCE, "modified"), change(self.REGEN, kind)]
                )
                self.assertEqual(got, [self.SOURCE])

    def test_ac1_a_source_that_is_itself_a_regenerate_target_never_admits(self):
        targets = [
            target("m/seed.yaml", "extend_only"),
            target("m/mid.html", "regenerate", source="m/seed.yaml"),
            target("m/leaf.html", "regenerate", source="m/mid.html"),
        ]
        got = identify(
            [
                change("m/seed.yaml", "modified"),
                change("m/mid.html", "modified"),
                change("m/leaf.html", "modified"),
            ],
            targets,
            [],
        )
        # mid.html follows seed.yaml; leaf.html's source is itself a
        # regenerate target, so it is never admitted.
        self.assertEqual(got, ["m/mid.html", "m/seed.yaml"])

    def test_ac1_two_regenerate_targets_naming_each_other_admit_neither(self):
        targets = [
            target("m/a.html", "regenerate", source="m/b.html"),
            target("m/b.html", "regenerate", source="m/a.html"),
        ]
        got = identify(
            [change("m/a.html", "modified"), change("m/b.html", "modified")],
            targets,
            [],
        )
        self.assertEqual(got, [])

    def test_ac1_a_regenerate_target_naming_itself_is_not_admitted(self):
        got = identify(
            [change("m/a.html", "modified")],
            [target("m/a.html", "regenerate", source="m/a.html")],
            [],
        )
        self.assertEqual(got, [])

    def test_ac1_a_preserve_source_never_admits_the_target(self):
        targets = [
            target("m/seed.yaml", "preserve"),
            target("m/out.html", "regenerate", source="m/seed.yaml"),
        ]
        got = identify(
            [change("m/seed.yaml", "modified"), change("m/out.html", "modified")],
            targets,
            [],
        )
        self.assertEqual(got, [])

    def test_ac1_a_regenerate_target_with_a_dot_dot_path_is_not_admitted(self):
        targets = [
            target("m/seed.yaml", "extend_only"),
            target("../out.html", "regenerate", source="m/seed.yaml"),
        ]
        got = identify(
            [change("m/seed.yaml", "modified"), change("../out.html", "modified")],
            targets,
            [],
        )
        self.assertEqual(got, ["m/seed.yaml"])

    def test_ac1_a_source_with_a_dot_dot_path_never_admits_the_target(self):
        targets = [
            target("../seed.yaml", "extend_only"),
            target("m/out.html", "regenerate", source="../seed.yaml"),
        ]
        got = identify(
            [change("../seed.yaml", "modified"), change("m/out.html", "modified")],
            targets,
            [],
        )
        self.assertEqual(got, [])


class TestTargetPrecedence(unittest.TestCase):
    """AC-1: a path listed in targets is judged by its target, even when it
    also lies under an allowed write root."""

    ROOTS = ["m/root"]

    def test_ac1_a_preserve_target_under_a_root_is_not_admitted_as_created(self):
        got = identify(
            [change("m/root/keep.md", "created")],
            [target("m/root/keep.md", "preserve")],
            self.ROOTS,
        )
        self.assertEqual(got, [])

    def test_ac1_a_replace_own_target_under_a_root_is_not_admitted_as_created(self):
        got = identify(
            [change("m/root/own.md", "created")],
            [target("m/root/own.md", "replace_own")],
            self.ROOTS,
        )
        self.assertEqual(got, [])

    def test_ac1_a_replace_own_target_under_a_root_is_admitted_as_modified(self):
        got = identify(
            [change("m/root/own.md", "modified")],
            [target("m/root/own.md", "replace_own")],
            self.ROOTS,
        )
        self.assertEqual(got, ["m/root/own.md"])

    def test_ac1_a_create_target_outside_every_root_is_admitted_as_created(self):
        got = identify(
            [change("elsewhere/new.md", "created")],
            [target("elsewhere/new.md", "create")],
            self.ROOTS,
        )
        self.assertEqual(got, ["elsewhere/new.md"])

    def test_ac1_a_create_target_under_a_root_is_not_admitted_as_modified(self):
        got = identify(
            [change("m/root/new.md", "modified")],
            [target("m/root/new.md", "create")],
            self.ROOTS,
        )
        self.assertEqual(got, [])


# (label, roots, path, member when created)
CONTAINMENT_CASES = [
    ("file directly inside the root", ["docs/x"], "docs/x/a.md", True),
    ("deeply nested file", ["docs/x"], "docs/x/sub/deep/a.md", True),
    ("sibling directory whose name extends the root's", ["docs/x"], "docs/x2/a.md", False),
    ("sibling file whose name extends the root's", ["docs/x"], "docs/xa.md", False),
    ("trailing slash on the root, inside", ["docs/x/"], "docs/x/a.md", True),
    ("trailing slash on the root, extending sibling", ["docs/x/"], "docs/x2/a.md", False),
    ("the root itself", ["docs/x"], "docs/x", False),
    ("the root itself, root written with a slash", ["docs/x/"], "docs/x", False),
    ("the root itself, path written with a slash", ["docs/x"], "docs/x/", False),
    ("the parent of the root", ["docs/x"], "docs", False),
    ("the second of several roots", ["other", "docs/x/"], "docs/x/a.md", True),
    ("a root listed with and without a slash", ["docs/x", "docs/x/"], "docs/x/a.md", True),
    ("no root at all", [], "docs/x/a.md", False),
    ("an empty root admits nothing", [""], "a.md", False),
    ("a slash-only root admits nothing", ["/"], "a.md", False),
    ("an absolute path", ["docs/x"], "/docs/x/a.md", False),
    ("an absolute path under an absolute root", ["/docs/x"], "/docs/x/a.md", False),
    ("a dot-dot segment in the middle", ["docs/x"], "docs/x/../y/a.md", False),
    ("a leading dot-dot segment", ["docs/x"], "../docs/x/a.md", False),
    ("dot-dot only inside a file name", ["docs/x"], "docs/x/a..b.md", True),
    ("a root containing a dot-dot segment", ["docs/../x"], "x/a.md", False),
    # task0001 of self-write-digest-path-normalization (AC-2): the root and
    # the path are normalized like validate-worker-output.py does it.
    ("a dot-prefixed root, file directly inside", ["./docs/x"], "docs/x/a.md", True),
    ("a dot-prefixed root, extending sibling", ["./docs/x"], "docs/x2/a.md", False),
    ("a dot-prefixed root, the root itself", ["./docs/x"], "docs/x", False),
    ("a dot-prefixed root, a dot-dot segment", ["./docs/x"], "docs/x/../y/a.md", False),
    ("a dot segment in the path", ["docs/x"], "docs/./x/a.md", True),
    ("a backslash-separated root", ["docs\\x"], "docs/x/a.md", True),
    ("a backslash-separated path", ["docs/x"], "docs\\x\\a.md", True),
    ("a backslash-separated path with a dot-dot segment", ["docs/x"], "docs\\x\\..\\y.md", False),
    (
        "the reproduction pair: a dot-prefixed root with a trailing slash",
        ["./feature-docs/example/tasks/"],
        "feature-docs/example/tasks/task0004.md",
        True,
    ),
    ("a dot-only root admits a top-level file", ["."], "a.md", True),
    ("a dot-only root admits a nested file", ["."], "docs/x/a.md", True),
    ("a dot-slash-only root admits a top-level file", ["./"], "a.md", True),
    ("a dot-slash-only root admits a nested file", ["./"], "docs/x/a.md", True),
]


class TestAllowedRootContainment(unittest.TestCase):
    """AC-1: segment-wise containment; absolute and dot-dot never admitted."""

    def test_ac1_containment_table(self):
        for label, roots, path, is_member in CONTAINMENT_CASES:
            with self.subTest(case=label):
                got = identify([change(path, "created")], [], roots)
                self.assertEqual(got, [path] if is_member else [])

    def test_ac1_an_absolute_create_target_is_never_admitted(self):
        got = identify(
            [change("/abs/new.md", "created")],
            [target("/abs/new.md", "create")],
            [],
        )
        self.assertEqual(got, [])

    def test_ac1_a_dot_dot_replace_own_target_is_never_admitted(self):
        got = identify(
            [change("docs/../SPEC.md", "modified")],
            [target("docs/../SPEC.md", "replace_own")],
            [],
        )
        self.assertEqual(got, [])

    def test_ac1_a_dot_dot_create_target_is_never_admitted(self):
        got = identify(
            [change("../new.md", "created")],
            [target("../new.md", "create")],
            [],
        )
        self.assertEqual(got, [])


class TestNoSegmentRoots(unittest.TestCase):
    """task0001 of self-write-digest-path-normalization, AC-3: a safe root
    that keeps no segment (`.`, `./`) contains every safe relative path, but
    still admits creations only; an empty or absolute root admits nothing."""

    PATHS = ("a.md", "docs/x/a.md")

    def test_ac3_a_no_segment_root_admits_a_created_file(self):
        for root in (".", "./"):
            for path in self.PATHS:
                with self.subTest(root=root, path=path):
                    got = identify([change(path, "created")], [], [root])
                    self.assertEqual(got, [path])

    def test_ac3_a_no_segment_root_does_not_admit_a_modified_file(self):
        for root in (".", "./"):
            for path in self.PATHS:
                with self.subTest(root=root, path=path):
                    got = identify([change(path, "modified")], [], [root])
                    self.assertEqual(got, [])

    def test_ac3_a_no_segment_root_does_not_admit_a_deleted_file(self):
        for root in (".", "./"):
            with self.subTest(root=root):
                got = identify([change("a.md", "deleted")], [], [root])
                self.assertEqual(got, [])

    def test_ac3_an_empty_root_admits_nothing(self):
        self.assertEqual(identify([change("a.md", "created")], [], [""]), [])

    def test_ac3_a_slash_only_root_admits_nothing(self):
        self.assertEqual(identify([change("a.md", "created")], [], ["/"]), [])


# (path, root): every row is judged by `path_is_contained_in_root` of
# validate-worker-output.py, whatever its result. Both results occur.
ROOT_CROSS_CHECK = [
    # dot segments in a root and in a path
    ("docs/x/a.md", "./docs/x"),
    ("docs/x/a.md", "docs/./x"),
    ("docs/x/a.md", "docs/x/."),
    ("docs/./x/a.md", "docs/x"),
    ("./docs/x/a.md", "docs/x"),
    ("./docs/x/a.md", "./docs/x/"),
    ("docs/x2/a.md", "./docs/x"),
    ("docs/x", "./docs/x"),
    # empty segments: doubled and trailing slashes
    ("docs//x/a.md", "docs/x"),
    ("docs/x/a.md", "docs//x//"),
    ("docs/x/a.md", "docs/x/"),
    ("docs/x/", "docs/x"),
    ("docs/x/", "docs/x/"),
    ("docs/x//a.md", "docs//x"),
    # backslash separators on each side
    ("docs\\x\\a.md", "docs/x"),
    ("docs/x/a.md", "docs\\x"),
    ("docs\\x\\a.md", "docs\\x\\"),
    ("docs\\x2\\a.md", "docs\\x"),
    ("docs/x\\a.md", "docs\\x/"),
    ("\\docs\\x\\a.md", "docs/x"),
    # a root that keeps no segment
    ("a.md", "."),
    ("docs/x/a.md", "."),
    ("a.md", "./"),
    ("docs/x/a.md", "./"),
    ("a.md", "\\"),
    ("docs/x/a.md", "\\"),
    ("a.md", ".\\"),
    ("a.md", "./."),
    ("docs/x/a.md", ".//"),
    # a path that keeps no segment
    (".", "."),
    ("./", "./"),
    ("./.", "docs/x"),
    (".", "docs/x"),
    ("\\", "docs/x"),
    # NUL in a path and in a root
    ("docs/x/a\x00.md", "docs/x"),
    ("docs/x/a.md", "docs/\x00x"),
    ("docs/x/a.md", "docs\x00"),
    ("a.md", "\x00"),
    ("a\x00.md", "."),
    # dot-dot segments, written with `/` and with `\`
    ("docs/x/../y/a.md", "docs/x"),
    ("docs/x/../y/a.md", "."),
    ("docs\\x\\..\\y.md", "docs/x"),
    ("docs/x/..\\y.md", "docs/x"),
    ("docs/x/a.md", "docs/../x"),
    ("docs/x/a.md", "docs\\..\\x"),
    ("../docs/x/a.md", "docs/x"),
    ("docs/x/a.md", ".."),
    ("a.md", "../"),
    ("docs/x/a..b.md", "docs/x"),
    # an absolute path and an absolute root
    ("/docs/x/a.md", "docs/x"),
    ("/docs/x/a.md", "/docs/x"),
    ("docs/x/a.md", "/docs/x"),
    ("/a.md", "."),
    ("a.md", "/"),
    # the empty-string root
    ("a.md", ""),
    ("docs/x/a.md", ""),
    # plain containment, for reference
    ("docs/x/a.md", "docs/x"),
    ("docs/x/sub/deep/a.md", "docs/x"),
    ("docs/x2/a.md", "docs/x"),
    ("docs/xa.md", "docs/x"),
    ("docs/x", "docs/x"),
    ("docs", "docs/x"),
    ("feature-docs/example/tasks/task0004.md", "./feature-docs/example/tasks/"),
]


class TestContainmentAgreesWithScopeValidation(unittest.TestCase):
    """task0001 of self-write-digest-path-normalization, AC-4 (TM-1): a
    `created` non-target path is a self-write exactly when scope validation
    (`validate-worker-output.py`) holds it contained in the root, so no path
    the reference refuses enters the self-write set."""

    def member(self, path, root):
        return identify([change(path, "created")], [], [root]) == [path]

    def test_ac4_membership_equals_the_reference_for_every_row(self):
        reference = validator_module().path_is_contained_in_root
        for path, root in ROOT_CROSS_CHECK:
            with self.subTest(path=path, root=root):
                self.assertEqual(
                    self.member(path, root),
                    reference(path, root),
                )

    def test_ac4_the_table_holds_rows_of_both_reference_results(self):
        # Non-vacuity: a table of one result would pass a constant function.
        reference = validator_module().path_is_contained_in_root
        results = {reference(path, root) for path, root in ROOT_CROSS_CHECK}
        self.assertEqual(results, {True, False})

    def test_ac4_the_table_covers_every_required_shape(self):
        paths_and_roots = ROOT_CROSS_CHECK
        shapes = {
            "dot segment in a root": any(
                "." in root.replace("\\", "/").split("/") and root != "."
                for _, root in paths_and_roots
            ),
            "dot segment in a path": any(
                "." in path.replace("\\", "/").split("/") for path, _ in paths_and_roots
            ),
            "doubled slash": any(
                "//" in path or "//" in root for path, root in paths_and_roots
            ),
            "trailing slash": any(
                path.endswith("/") or root.endswith("/") for path, root in paths_and_roots
            ),
            "backslash in a path": any("\\" in path for path, _ in paths_and_roots),
            "backslash in a root": any("\\" in root for _, root in paths_and_roots),
            "dot-only root": any(root == "." for _, root in paths_and_roots),
            "dot-slash-only root": any(root == "./" for _, root in paths_and_roots),
            "backslash-only root": any(root == "\\" for _, root in paths_and_roots),
            "NUL in a path": any("\x00" in path for path, _ in paths_and_roots),
            "NUL in a root": any("\x00" in root for _, root in paths_and_roots),
            "dot-dot written with a slash": any(
                ".." in path.split("/") or ".." in root.split("/")
                for path, root in paths_and_roots
            ),
            "dot-dot written with a backslash": any(
                ".." in path.split("\\") or ".." in root.split("\\")
                for path, root in paths_and_roots
            ),
            "absolute path": any(path.startswith("/") for path, _ in paths_and_roots),
            "absolute root": any(root.startswith("/") for _, root in paths_and_roots),
            "empty root": any(root == "" for _, root in paths_and_roots),
        }
        self.assertEqual([name for name, found in shapes.items() if not found], [])

    def test_ac4_single_root_containment_cases_agree_with_the_reference(self):
        reference = validator_module().path_is_contained_in_root
        for label, roots, path, is_member in CONTAINMENT_CASES:
            if len(roots) != 1:
                continue
            with self.subTest(case=label):
                self.assertEqual(is_member, reference(path, roots[0]))


class TestPathNormalizationReproduction(TempDirCase):
    """task0001 of self-write-digest-path-normalization, AC-1 (TS-1): a
    worker's own `created` file under a `./`-prefixed allowed write root is a
    self-write, so the return-time digest equals the dispatch-time one."""

    ROOT = "./feature-docs/example/tasks/"
    CREATED = "feature-docs/example/tasks/task0004.md"

    def scenario(self):
        dispatch = {
            SPEC: fake("spec"),
            IMPLEMENTATION: fake("implementation v1"),
        }
        current = dict(dispatch)
        current[self.CREATED] = fake("task0004 v1")
        return Scenario(
            dispatch,
            current,
            [change(self.CREATED, "created")],
            [],
            [self.ROOT],
        )

    def test_ac1_a_created_file_under_a_dot_prefixed_root_is_a_self_write(self):
        scenario = self.scenario()
        proc = self.cli(scenario.document())
        self.assert_succeeded(proc)
        output = decode_output(proc)
        self.assertIn(self.CREATED, output["self_write_set"])
        self.assertEqual(r1_digest(output["digest_source"]), scenario.dispatch_digest)

    def test_ac1_the_current_digest_differs_so_the_check_is_not_vacuous(self):
        scenario = self.scenario()
        self.assertNotIn(self.CREATED, scenario.dispatch["digest_inputs"])
        self.assertIn(self.CREATED, scenario.current["digest_inputs"])
        self.assertNotEqual(scenario.current_digest, scenario.dispatch_digest)

    def test_ac1_a_root_that_does_not_cover_the_file_leaves_the_result_stale(self):
        scenario = self.scenario()
        scenario.roots = ["./feature-docs/example/other/"]
        proc = self.cli(scenario.document())
        self.assert_succeeded(proc)
        output = decode_output(proc)
        self.assertEqual(output["self_write_set"], [])
        self.assertNotEqual(
            r1_digest(output["digest_source"]), scenario.dispatch_digest
        )


class TestObservedChangesOnly(unittest.TestCase):
    """AC-1 (TM-1, TS-5): only the observed change set admits a path."""

    def test_ac1_the_identification_has_no_written_artifacts_input(self):
        module = script_module()
        for name in ("identify_self_writes", "identify_and_substitute"):
            with self.subTest(function=name):
                parameters = inspect.signature(getattr(module, name)).parameters
                self.assertEqual(
                    [p for p in parameters if "written" in p or "artifact" in p],
                    [],
                )

    def test_ac1_a_path_missing_from_the_observed_changes_is_not_admitted(self):
        # TS-5: SPEC.md is a replace_own target and might be reported in a
        # worker's written_artifacts, but the observed change set excludes it.
        scenario = planner_scenario()
        scenario.targets = scenario.targets + [target(SPEC, "replace_own")]
        scenario.current["digest_inputs"][SPEC] = fake("spec changed unseen")
        members, substituted = scenario.run()
        self.assertNotIn(SPEC, members)
        self.assertEqual(
            substituted["digest_inputs"][SPEC], fake("spec changed unseen")
        )
        self.assertNotEqual(r1_digest(substituted), scenario.dispatch_digest)

    def test_ac1_an_observed_path_no_entry_permits_is_not_admitted(self):
        members, _ = planner_scenario().run()
        self.assertNotIn(SPEC, members)
        scenario = planner_scenario()
        scenario.changes = scenario.changes + [change(SPEC, "modified")]
        members, _ = scenario.run()
        self.assertNotIn(SPEC, members)


# ------------------------------------------------------------------ AC-2 ----


class TestSubstitution(unittest.TestCase):
    """AC-2: the substitution contract."""

    def substitute(self, current, dispatch_inputs, members):
        return script_module().substitute_self_writes(
            current, dispatch_inputs, members
        )

    def test_ac2_the_output_has_exactly_the_current_top_level_members(self):
        current = make_source({"a.md": fake("a2")}, extra={"carried": [1, 2]})
        out = self.substitute(current, {"a.md": fake("a1")}, ["a.md"])
        self.assertEqual(set(out), set(current))

    def test_ac2_every_member_but_digest_inputs_equals_the_current_one(self):
        current = make_source(
            {"a.md": fake("a2")},
            extra={"carried": {"nested": [1, 2]}},
            workflow_blob="current-blob",
            answers_digest=fake("current answers"),
        )
        out = self.substitute(current, {"a.md": fake("a1")}, ["a.md"])
        for name in current:
            if name == "digest_inputs":
                continue
            with self.subTest(member=name):
                self.assertEqual(out[name], current[name])

    def test_ac2_a_self_written_path_present_at_dispatch_carries_its_old_value(self):
        current = make_source({"a.md": fake("a2"), "b.md": fake("b2")})
        out = self.substitute(
            current, {"a.md": fake("a1"), "b.md": fake("b1")}, ["a.md"]
        )
        self.assertEqual(out["digest_inputs"]["a.md"], fake("a1"))
        self.assertEqual(out["digest_inputs"]["b.md"], fake("b2"))

    def test_ac2_a_self_written_path_absent_at_dispatch_is_absent(self):
        current = make_source({"a.md": fake("a1"), "new.md": fake("new")})
        out = self.substitute(current, {"a.md": fake("a1")}, ["new.md"])
        self.assertNotIn("new.md", out["digest_inputs"])
        self.assertEqual(out["digest_inputs"], {"a.md": fake("a1")})

    def test_ac2_every_other_path_keeps_its_current_value_or_absence(self):
        current = make_source({"keep.md": fake("keep now"), "plain.md": fake("p")})
        dispatch_inputs = {
            "keep.md": fake("keep then"),
            "gone.md": fake("gone then"),
            "plain.md": fake("p"),
        }
        out = self.substitute(current, dispatch_inputs, ["plain.md"])
        self.assertEqual(out["digest_inputs"]["keep.md"], fake("keep now"))
        self.assertNotIn("gone.md", out["digest_inputs"])
        self.assertEqual(out["digest_inputs"]["plain.md"], fake("p"))

    def test_ac2_a_self_written_path_in_the_dispatch_map_returns_even_if_absent_now(self):
        current = make_source({"a.md": fake("a1")})
        out = self.substitute(current, {"b.md": fake("b1")}, ["b.md"])
        self.assertEqual(
            out["digest_inputs"], {"a.md": fake("a1"), "b.md": fake("b1")}
        )

    def test_ac2_a_self_write_path_that_is_no_digest_input_has_no_effect(self):
        current = make_source({"a.md": fake("a1")})
        out = self.substitute(current, {"a.md": fake("a1")}, ["not/an/input.md"])
        self.assertEqual(out, current)

    def test_ac2_an_empty_self_write_set_returns_the_current_digest_source(self):
        current = make_source({"a.md": fake("a2")})
        out = self.substitute(current, {"a.md": fake("a1")}, [])
        self.assertEqual(out, current)

    def test_ac2_digest_inputs_stay_path_ascending(self):
        current = make_source({"b.md": fake("b2"), "d.md": fake("d")})
        out = self.substitute(
            current, {"a.md": fake("a1"), "c.md": fake("c1")}, ["c.md", "a.md"]
        )
        self.assertEqual(list(out["digest_inputs"]), ["a.md", "b.md", "c.md", "d.md"])

    def test_ac2_the_inputs_are_not_mutated(self):
        current = make_source({"a.md": fake("a2"), "new.md": fake("n")})
        dispatch_inputs = {"a.md": fake("a1")}
        members = ["new.md", "a.md"]
        before = copy.deepcopy((current, dispatch_inputs, members))
        self.substitute(current, dispatch_inputs, members)
        self.assertEqual((current, dispatch_inputs, members), before)

    def test_ac2_the_output_shares_no_structure_with_the_input(self):
        current = make_source({"a.md": fake("a2")}, extra={"carried": [1, 2]})
        before = copy.deepcopy(current)
        out = self.substitute(current, {"a.md": fake("a1")}, ["a.md"])
        out["digest_inputs"]["zzz.md"] = "x"
        out["value_inputs"]["task_description"] = "x"
        out["extra"]["carried"].append(3)
        self.assertEqual(current, before)

    def test_ac2_repeated_calls_give_identical_output(self):
        current = make_source({"a.md": fake("a2"), "new.md": fake("n")})
        first = self.substitute(current, {"a.md": fake("a1")}, ["new.md", "a.md"])
        second = self.substitute(current, {"a.md": fake("a1")}, ["new.md", "a.md"])
        self.assertEqual(first, second)
        self.assertEqual(r1_digest(first), r1_digest(second))

    def test_ac2_a_create_target_absent_at_dispatch_is_absent_in_the_output(self):
        # TS-7, through identify-and-substitute.
        scenario = Scenario(
            {SPEC: fake("spec")},
            {SPEC: fake("spec"), IMPLEMENTATION: fake("implementation v1")},
            [change(IMPLEMENTATION, "created")],
            [target(IMPLEMENTATION, "create")],
            [],
        )
        members, substituted = scenario.run()
        self.assertEqual(members, [IMPLEMENTATION])
        self.assertNotIn(IMPLEMENTATION, substituted["digest_inputs"])
        self.assertEqual(r1_digest(substituted), scenario.dispatch_digest)
        self.assertNotEqual(scenario.current_digest, scenario.dispatch_digest)

    def test_ac2_identify_and_substitute_keeps_the_seven_structural_members(self):
        # TS-13
        scenario = planner_scenario()
        _, substituted = scenario.run()
        self.assertEqual(set(substituted), set(scenario.current))
        self.assertEqual(
            set(substituted),
            {
                "worker",
                "mode",
                "workflow_blob",
                "digest_inputs",
                "value_inputs",
                "answers_digest",
                "write_policy_digest",
            },
        )

    def test_ac2_identify_and_substitute_with_no_change_returns_the_current(self):
        scenario = planner_scenario()
        scenario.changes = []
        members, substituted = scenario.run()
        self.assertEqual(members, [])
        self.assertEqual(substituted, scenario.current)

    def test_ac2_identify_and_substitute_uses_the_dispatch_digest_inputs_map(self):
        scenario = planner_scenario()
        members, substituted = scenario.run()
        for path in members:
            with self.subTest(path=path):
                if path in scenario.dispatch["digest_inputs"]:
                    self.assertEqual(
                        substituted["digest_inputs"][path],
                        scenario.dispatch["digest_inputs"][path],
                    )
                else:
                    self.assertNotIn(path, substituted["digest_inputs"])


# ------------------------------------------------------------------ AC-3 ----


class TestScenarioDigests(unittest.TestCase):
    """AC-3: legitimate self-writes are not stale; the current digest_source
    without the substitution (the pre-fix behaviour) is."""

    def assert_not_stale(self, scenario, expected_set):
        members, substituted = scenario.run()
        self.assertEqual(members, expected_set)
        self.assertEqual(r1_digest(substituted), scenario.dispatch_digest)
        # The pre-fix comparison would have reported this dispatch stale.
        self.assertNotEqual(scenario.current_digest, scenario.dispatch_digest)

    def test_ac3_designer_extend_only_with_regenerated_html_is_not_stale(self):
        self.assert_not_stale(designer_scenario(), [TOKENS_HTML, TOKENS_YAML])

    def test_ac3_planner_replan_with_a_new_task_plan_is_not_stale(self):
        self.assert_not_stale(
            planner_scenario(), [IMPLEMENTATION, THREAT_MODEL, VERIFICATION, TASK_3]
        )

    def test_ac3_rework_planner_with_a_new_task_plan_is_not_stale(self):
        self.assert_not_stale(
            rework_scenario(), [IMPLEMENTATION, VERIFICATION, TASK_2]
        )

    def test_ac3_the_planner_scenario_with_many_new_task_plans_is_not_stale(self):
        scenario = planner_scenario()
        for number in range(4, 9):
            path = f"{TASKS_ROOT}/task{number:04d}.md"
            scenario.current["digest_inputs"][path] = fake(path)
            scenario.changes.append(change(path, "created"))
        members, substituted = scenario.run()
        self.assertEqual(len(members), 4 + 5)
        self.assertEqual(r1_digest(substituted), scenario.dispatch_digest)


# ------------------------------------------------------------------ AC-4 ----


class TestOtherChangesStayStale(unittest.TestCase):
    """AC-4: any change that is not a permitted self-write keeps the
    substituted digest different from the dispatch-time digest."""

    def assert_stale(self, scenario):
        _, substituted = scenario.run()
        self.assertNotEqual(r1_digest(substituted), scenario.dispatch_digest)

    def assert_not_stale(self, scenario):
        _, substituted = scenario.run()
        self.assertEqual(r1_digest(substituted), scenario.dispatch_digest)

    def test_ac4_spec_changing_alongside_legitimate_self_writes_is_stale(self):
        for observed in (True, False):
            with self.subTest(spec_in_observed_changes=observed):
                scenario = planner_scenario()
                scenario.current["digest_inputs"][SPEC] = fake("spec edited")
                if observed:
                    scenario.changes.append(change(SPEC, "modified"))
                self.assert_stale(scenario)

    def test_ac4_spec_is_never_substituted_even_when_observed(self):
        scenario = planner_scenario()
        scenario.current["digest_inputs"][SPEC] = fake("spec edited")
        scenario.changes.append(change(SPEC, "modified"))
        members, substituted = scenario.run()
        self.assertNotIn(SPEC, members)
        self.assertEqual(substituted["digest_inputs"][SPEC], fake("spec edited"))

    def test_ac4_each_non_file_member_differing_is_stale(self):
        overrides = {
            "value_inputs": {"task_description": fake("other description")},
            "answers_digest": fake("other answers"),
            "write_policy_digest": fake("other policy"),
            "workflow_blob": "other-blob",
        }
        for member, value in overrides.items():
            with self.subTest(member=member):
                scenario = planner_scenario()
                scenario.current[member] = value
                self.assert_stale(scenario)

    def test_ac4_a_non_file_member_differing_alone_is_stale(self):
        overrides = {
            "value_inputs": {"task_description": fake("other description")},
            "answers_digest": fake("other answers"),
            "write_policy_digest": fake("other policy"),
            "workflow_blob": "other-blob",
        }
        for member, value in overrides.items():
            with self.subTest(member=member):
                scenario = Scenario(
                    {SPEC: fake("spec")},
                    {SPEC: fake("spec")},
                    [],
                    [],
                    [],
                    current_overrides={member: value},
                )
                self.assert_stale(scenario)

    def test_ac4_an_existing_file_modified_under_a_root_alone_is_stale(self):
        def build(modified):
            current = {TASK_1: fake("task0001 v2" if modified else "task0001 v1")}
            return Scenario(
                {TASK_1: fake("task0001 v1")},
                current,
                [change(TASK_1, "modified")] if modified else [],
                [],
                [TASKS_ROOT],
            )

        self.assert_not_stale(build(False))
        scenario = build(True)
        members, _ = scenario.run()
        self.assertEqual(members, [])
        self.assert_stale(scenario)

    def test_ac4_a_modified_preserve_target_is_stale(self):
        def build(modified):
            return Scenario(
                {TOKENS_YAML: fake("v1")},
                {TOKENS_YAML: fake("v2" if modified else "v1")},
                [change(TOKENS_YAML, "modified")] if modified else [],
                [target(TOKENS_YAML, "preserve")],
                [],
            )

        self.assert_not_stale(build(False))
        scenario = build(True)
        members, _ = scenario.run()
        self.assertEqual(members, [])
        self.assert_stale(scenario)

    def test_ac4_html_changed_without_its_regenerate_source_is_stale(self):
        def build(modified):
            return Scenario(
                {TOKENS_YAML: fake("y1"), TOKENS_HTML: fake("h1")},
                {
                    TOKENS_YAML: fake("y1"),
                    TOKENS_HTML: fake("h2" if modified else "h1"),
                },
                [change(TOKENS_HTML, "modified")] if modified else [],
                [
                    target(TOKENS_YAML, "extend_only"),
                    target(TOKENS_HTML, "regenerate", source=TOKENS_YAML),
                ],
                [],
            )

        self.assert_not_stale(build(False))
        scenario = build(True)
        members, _ = scenario.run()
        self.assertEqual(members, [])
        self.assert_stale(scenario)

    def test_ac4_a_deleted_input_is_stale(self):
        scenario = planner_scenario()
        del scenario.current["digest_inputs"][CONTRACT]
        scenario.changes.append(change(CONTRACT, "deleted"))
        self.assert_stale(scenario)

    def test_ac4_a_deleted_replace_own_target_is_stale(self):
        scenario = planner_scenario()
        del scenario.current["digest_inputs"][IMPLEMENTATION]
        scenario.changes = [change(IMPLEMENTATION, "deleted")]
        members, _ = scenario.run()
        self.assertEqual(members, [])
        self.assert_stale(scenario)

    def test_ac4_an_unobserved_change_to_a_target_is_stale(self):
        scenario = planner_scenario()
        scenario.changes = [
            c for c in scenario.changes if c["path"] != THREAT_MODEL
        ]
        self.assert_stale(scenario)


# ------------------------------------------------------------------ AC-5 ----


class TestValidatorDryRunApply(TempDirCase):
    """AC-5: `validate-worker-output.py --kind workflow-patch --dry-run-apply`
    with the script's substituted digest_source."""

    def run_validator(self, group, worker, scenario, digest_source):
        fixture = PATCH_FIXTURES / group / "valid-dry-run-apply"
        patch = json.loads((fixture / "input.json").read_text(encoding="utf-8"))
        patch["base_input_digest"] = scenario.dispatch_digest
        patch["base_workflow_blob"] = scenario.dispatch["workflow_blob"]
        patch_path = self.write_json("patch.json", patch)
        workflow_path = self.write_json(
            "workflow.json",
            json.loads((fixture / "workflow.json").read_text(encoding="utf-8")),
        )
        source_path = self.write_json("digest-source.json", digest_source)
        return run_python(
            [
                str(VALIDATOR),
                "--kind",
                "workflow-patch",
                "--worker",
                worker,
                "--input",
                str(patch_path),
                "--workflow",
                str(workflow_path),
                "--digest-source",
                str(source_path),
                "--dry-run-apply",
            ]
        )

    def substituted_through_the_cli(self, scenario):
        proc = self.cli(scenario.document(), name="self-write.json")
        self.assert_succeeded(proc)
        return decode_output(proc)["digest_source"]

    def error_codes(self, proc):
        return {e["code"] for e in json.loads(proc.stdout.decode("utf-8"))["errors"]}

    def check_group(self, group, worker, scenario):
        substituted = self.substituted_through_the_cli(scenario)
        ok = self.run_validator(group, worker, scenario, substituted)
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        self.assertEqual(ok.stdout, b"")
        stale = self.run_validator(group, worker, scenario, scenario.current)
        self.assertEqual(stale.returncode, 1, stale.stdout + stale.stderr)
        self.assertIn("stale-input-digest", self.error_codes(stale))

    def test_ac5_a_replace_planning_patch_is_not_stale_with_the_substitution(self):
        self.check_group(
            "replace_planning", "implementation-planner", planner_scenario()
        )

    def test_ac5_an_append_rework_patch_is_not_stale_with_the_substitution(self):
        self.check_group("append_rework", "rework-planner", rework_scenario())

    def test_ac5_a_changed_spec_still_reports_stale_with_the_substitution(self):
        scenario = planner_scenario()
        scenario.current["digest_inputs"][SPEC] = fake("spec edited")
        scenario.changes.append(change(SPEC, "modified"))
        substituted = self.substituted_through_the_cli(scenario)
        proc = self.run_validator(
            "replace_planning", "implementation-planner", scenario, substituted
        )
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("stale-input-digest", self.error_codes(proc))


# ------------------------------------------------------------------ AC-6 ----


class TestResumeReproduction(TempDirCase):
    """AC-6: a persisted `dispatch_digest_inputs` / `self_write_set` pair
    reproduces the recorded `input_digest`, and an edited self-written
    artifact is still detected through its recorded artifact digest."""

    def artifact_digest(self, relative):
        proc = run_python([str(ARTIFACT_DIGEST), relative], cwd=self.tmp)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        (element,) = json.loads(proc.stdout.decode("utf-8"))
        return element["sha256"]

    def write_artifact(self, relative, text):
        path = self.tmp / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return self.artifact_digest(relative)

    def build_run(self):
        """A completed planner run, as the return-time sequence leaves it."""
        implementation_v0 = self.write_artifact(IMPLEMENTATION, "plan v0\n")
        verification_v0 = self.write_artifact(VERIFICATION, "verification v0\n")
        dispatch_inputs = {
            SPEC: fake("spec"),
            IMPLEMENTATION: implementation_v0,
            VERIFICATION: verification_v0,
        }
        implementation_v1 = self.write_artifact(IMPLEMENTATION, "plan v1\n")
        verification_v1 = self.write_artifact(VERIFICATION, "verification v1\n")
        task_digest = self.write_artifact(TASK_3, "task plan\n")
        current_inputs = {
            SPEC: fake("spec"),
            IMPLEMENTATION: implementation_v1,
            VERIFICATION: verification_v1,
            TASK_3: task_digest,
        }
        scenario = Scenario(
            dispatch_inputs,
            current_inputs,
            [
                change(IMPLEMENTATION, "modified"),
                change(VERIFICATION, "modified"),
                change(TASK_3, "created"),
            ],
            [
                target(IMPLEMENTATION, "replace_own"),
                target(VERIFICATION, "replace_own"),
            ],
            [TASKS_ROOT],
        )
        proc = self.cli(scenario.document(), name="return-time.json")
        self.assert_succeeded(proc)
        output = decode_output(proc)
        self.assertEqual(r1_digest(output["digest_source"]), scenario.dispatch_digest)
        state = {
            "schema_version": 1,
            "feature": "example",
            "phase": "create-plan",
            "status": "completed",
            "generation": 1,
            "last_input_digest": scenario.dispatch_digest,
            "active_request_id": None,
            "worker_runs": [
                {
                    "request_id": "create-plan-run-0001",
                    "status": "discarded_stale",
                    "input_digest": fake("an earlier dispatch"),
                    "output_digest": fake("earlier output"),
                },
                {
                    "request_id": "create-plan-run-0002",
                    "status": "completed",
                    "input_digest": scenario.dispatch_digest,
                    "output_digest": fake("output"),
                    "dispatch_digest_inputs": copy.deepcopy(
                        scenario.dispatch["digest_inputs"]
                    ),
                    "self_write_set": output["self_write_set"],
                },
            ],
            "artifacts": [
                {
                    "path": path,
                    "sha256": self.artifact_digest(path),
                    "produced_by": "create-plan-run-0002",
                }
                for path in output["self_write_set"]
            ],
        }
        return scenario, state

    def selected_run(self, state):
        runs = [
            run
            for run in state["worker_runs"]
            if run["input_digest"] == state["last_input_digest"]
        ]
        return runs[-1]

    def resume_digest(self, state, current_digest_source):
        run = self.selected_run(state)
        proc = self.cli(
            {
                "operation": "substitute_only",
                "current_digest_source": current_digest_source,
                "dispatch_digest_inputs": run["dispatch_digest_inputs"],
                "self_write_set": run["self_write_set"],
            },
            name="resume.json",
        )
        self.assert_succeeded(proc)
        output = decode_output(proc)
        self.assertEqual(output["self_write_set"], sorted(set(run["self_write_set"])))
        return r1_digest(output["digest_source"])

    def test_ac6_the_phase_state_document_with_the_two_fields_is_accepted(self):
        _, state = self.build_run()
        path = self.write_json("create-plan.json", state)
        proc = run_python(
            [
                str(VALIDATOR),
                "--kind",
                "phase-state",
                "--worker",
                "implementation-planner",
                "--input",
                str(path),
            ]
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)

    def test_ac6_the_persisted_fields_reproduce_the_recorded_input_digest(self):
        scenario, state = self.build_run()
        run = self.selected_run(state)
        self.assertEqual(run["request_id"], "create-plan-run-0002")
        self.assertEqual(
            self.resume_digest(state, scenario.current), run["input_digest"]
        )
        self.assertEqual(run["input_digest"], state["last_input_digest"])
        # The current digest_source alone is not the recorded digest.
        self.assertNotEqual(scenario.current_digest, run["input_digest"])

    def test_ac6_an_edited_self_written_artifact_is_detected_by_its_digest(self):
        scenario, state = self.build_run()
        run = self.selected_run(state)
        recorded = {a["path"]: a["sha256"] for a in state["artifacts"]}
        self.assertEqual(set(recorded), set(run["self_write_set"]))
        for path, sha in recorded.items():
            self.assertEqual(self.artifact_digest(path), sha)

        edited = self.write_artifact(IMPLEMENTATION, "plan edited after the run\n")
        current = copy.deepcopy(scenario.current)
        current["digest_inputs"][IMPLEMENTATION] = edited

        # The substituted digest still matches ...
        self.assertEqual(self.resume_digest(state, current), run["input_digest"])
        # ... so the edit is caught by the artifact body comparison.
        self.assertNotEqual(self.artifact_digest(IMPLEMENTATION), recorded[IMPLEMENTATION])
        for path in run["self_write_set"]:
            if path != IMPLEMENTATION:
                self.assertEqual(self.artifact_digest(path), recorded[path])

    def test_ac6_an_edit_outside_the_set_is_still_stale_on_resume(self):
        scenario, state = self.build_run()
        run = self.selected_run(state)
        current = copy.deepcopy(scenario.current)
        current["digest_inputs"][SPEC] = fake("spec edited after the run")
        self.assertNotEqual(self.resume_digest(state, current), run["input_digest"])


# ------------------------------------------------------------------ AC-7 ----


def identify_document():
    return planner_scenario().document()


def substitute_only_document():
    scenario = planner_scenario()
    return {
        "operation": "substitute_only",
        "current_digest_source": scenario.current,
        "dispatch_digest_inputs": scenario.dispatch["digest_inputs"],
        "self_write_set": [THREAT_MODEL, IMPLEMENTATION],
    }


DOCUMENT_BUILDERS = {
    "identify_and_substitute": identify_document,
    "substitute_only": substitute_only_document,
}


def with_member(document, name, value):
    changed = copy.deepcopy(document)
    changed[name] = value
    return changed


class TestCliContract(TempDirCase):
    """AC-7: argument count, both operations, the output object."""

    def test_ac7_no_argument_exits_2_with_usage_on_stderr(self):
        proc = run_script(cwd=self.tmp)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn(b"usage", proc.stderr.lower())
        self.assertEqual(proc.stdout, b"")

    def test_ac7_two_arguments_exit_2_with_empty_stdout(self):
        path = self.write_json("input.json", identify_document())
        proc = run_script(path, path, cwd=self.tmp)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn(b"usage", proc.stderr.lower())
        self.assertEqual(proc.stdout, b"")

    def test_ac7_identify_and_substitute_writes_the_documented_object(self):
        scenario = planner_scenario()
        proc = self.cli(scenario.document())
        self.assert_succeeded(proc)
        output = decode_output(proc)
        self.assertEqual(set(output), {"self_write_set", "digest_source"})
        members, substituted = scenario.run()
        self.assertEqual(output["self_write_set"], members)
        self.assertEqual(output["digest_source"], substituted)
        self.assertEqual(r1_digest(output["digest_source"]), scenario.dispatch_digest)

    def test_ac7_substitute_only_writes_the_documented_object(self):
        document = substitute_only_document()
        proc = self.cli(document)
        self.assert_succeeded(proc)
        output = decode_output(proc)
        self.assertEqual(set(output), {"self_write_set", "digest_source"})
        self.assertEqual(output["self_write_set"], [IMPLEMENTATION, THREAT_MODEL])
        expected = script_module().substitute_self_writes(
            document["current_digest_source"],
            document["dispatch_digest_inputs"],
            document["self_write_set"],
        )
        self.assertEqual(output["digest_source"], expected)

    def test_ac7_substitute_only_echoes_the_set_sorted_and_de_duplicated(self):
        document = substitute_only_document()
        document["self_write_set"] = ["b/z.md", "a/y.md", "b/z.md", "a/y.md"]
        proc = self.cli(document)
        self.assert_succeeded(proc)
        self.assertEqual(
            decode_output(proc)["self_write_set"], ["a/y.md", "b/z.md"]
        )

    def test_ac7_stdout_is_one_json_line_ending_in_a_newline(self):
        for operation, build in DOCUMENT_BUILDERS.items():
            with self.subTest(operation=operation):
                proc = self.cli(build())
                self.assert_succeeded(proc)
                self.assertTrue(proc.stdout.endswith(b"\n"))
                self.assertEqual(proc.stdout.count(b"\n"), 1)
                json.loads(proc.stdout.decode("utf-8"))

    def test_ac7_non_ascii_characters_are_written_unescaped_as_utf8(self):
        scenario = planner_scenario()
        name = f"{TASKS_ROOT}/設計メモ 1.md"
        scenario.current["digest_inputs"][name] = fake(name)
        scenario.changes.append(change(name, "created"))
        for label, env in (
            ("default", None),
            ("c-locale", clean_env(LC_ALL="C", PYTHONIOENCODING="ascii")),
        ):
            with self.subTest(environment=label):
                path = self.write_json("input.json", scenario.document())
                proc = run_script(path, cwd=self.tmp, env=env)
                self.assert_succeeded(proc)
                self.assertIn(name.encode("utf-8"), proc.stdout)
                self.assertNotIn(b"\\u", proc.stdout)
                self.assertIn(name, decode_output(proc)["self_write_set"])

    def test_ac7_an_empty_observed_change_set_returns_the_current_digest_source(self):
        scenario = planner_scenario()
        scenario.changes = []
        proc = self.cli(scenario.document())
        self.assert_succeeded(proc)
        output = decode_output(proc)
        self.assertEqual(output["self_write_set"], [])
        self.assertEqual(output["digest_source"], scenario.current)

    def test_ac7_paths_in_the_document_need_not_exist_and_nothing_is_written(self):
        proc = self.cli(identify_document())
        self.assert_succeeded(proc)
        self.assertEqual([p.name for p in self.tmp.iterdir()], ["input.json"])
        for relative in (IMPLEMENTATION, TASK_3, TOKENS_YAML):
            self.assertFalse((self.tmp / relative).exists())

    def test_ac7_the_command_line_names_only_the_input_document(self):
        # Option-like names are file names, never options: nothing but the
        # input document's own path is taken from the command line.
        for name in ("-", "--", "--help", "-x.json", "-h"):
            with self.subTest(name=name):
                self.write_json(name, identify_document())
                proc = run_script(name, cwd=self.tmp)
                self.assert_succeeded(proc)
                self.assertEqual(
                    set(decode_output(proc)), {"self_write_set", "digest_source"}
                )

    def test_ac7_no_path_from_the_document_is_ever_read_or_followed(self):
        # A document path that is a symlink to a file with other content, or
        # a directory, changes nothing: the script reads only the document.
        outside = self.tmp / "outside.md"
        outside.write_text("other", encoding="utf-8")
        link = self.tmp / "feature-docs" / "example"
        link.parent.mkdir(parents=True)
        os.symlink(self.tmp, link)
        before = sorted(p.name for p in self.tmp.iterdir())
        proc = self.cli(identify_document())
        self.assert_succeeded(proc)
        after = sorted(p.name for p in self.tmp.iterdir())
        self.assertEqual(after, sorted(before + ["input.json"]))
        self.assertEqual(outside.read_text(encoding="utf-8"), "other")


def rejection_cases():
    """(label, document builder) pairs that must exit 2 with empty stdout."""
    cases = []
    for operation, build in DOCUMENT_BUILDERS.items():
        for member in build():
            if member == "operation":
                continue
            cases.append(
                (
                    f"{operation}: missing {member}",
                    lambda build=build, member=member: {
                        k: v for k, v in build().items() if k != member
                    },
                )
            )
        cases.append(
            (
                f"{operation}: missing operation",
                lambda build=build: {
                    k: v for k, v in build().items() if k != "operation"
                },
            )
        )
        cases.append(
            (
                f"{operation}: extra member",
                lambda build=build: with_member(build(), "unexpected", []),
            )
        )
    cases += [
        (
            "identify_and_substitute: written_artifacts is no input",
            lambda: with_member(identify_document(), "written_artifacts", [SPEC]),
        ),
        (
            "identify_and_substitute: a substitute_only member",
            lambda: with_member(identify_document(), "self_write_set", []),
        ),
        (
            "substitute_only: an identify_and_substitute member",
            lambda: with_member(substitute_only_document(), "observed_changes", []),
        ),
        (
            "unknown operation",
            lambda: with_member(identify_document(), "operation", "identify"),
        ),
        (
            "operation is not a string",
            lambda: with_member(identify_document(), "operation", ["substitute_only"]),
        ),
        ("an empty document", lambda: {}),
        ("a document that is a list", lambda: [identify_document()]),
        ("a document that is null", lambda: None),
    ]
    bad_changes = {
        "an entry that is a string": ["a.md"],
        "an entry that is a list": [["a.md", "created"]],
        "an entry without path": [{"kind": "created"}],
        "an entry without kind": [{"path": "a.md"}],
        "an empty path": [{"path": "", "kind": "created"}],
        "a non-string path": [{"path": 3, "kind": "created"}],
        "an unknown kind": [{"path": "a.md", "kind": "renamed"}],
        "a null kind": [{"path": "a.md", "kind": None}],
        "a repeated path with one kind": [
            {"path": "a.md", "kind": "created"},
            {"path": "a.md", "kind": "created"},
        ],
        "a repeated path with two kinds": [
            {"path": "a.md", "kind": "created"},
            {"path": "a.md", "kind": "modified"},
        ],
        "a mapping instead of a list": {"path": "a.md", "kind": "created"},
        "a string instead of a list": "a.md",
        "null": None,
    }
    for label, value in bad_changes.items():
        cases.append(
            (
                f"observed_changes: {label}",
                lambda value=value: with_member(
                    identify_document(), "observed_changes", value
                ),
            )
        )
    bad_policies = {
        "a list": [],
        "no targets member": {},
        "targets is a mapping": {"targets": {}},
        "a target that is a string": {"targets": ["a.md"]},
        "a target without path": {"targets": [{"action": "create"}]},
        "a target with an empty path": {"targets": [{"path": "", "action": "create"}]},
        "a target without action": {"targets": [{"path": "a.md"}]},
        "an unknown action": {"targets": [{"path": "a.md", "action": "overwrite"}]},
        "regenerate without source": {
            "targets": [{"path": "a.html", "action": "regenerate"}]
        },
        "regenerate with an empty source": {
            "targets": [{"path": "a.html", "action": "regenerate", "source": ""}]
        },
        "a repeated target path": {
            "targets": [
                {"path": "a.md", "action": "create"},
                {"path": "a.md", "action": "preserve"},
            ]
        },
    }
    for label, value in bad_policies.items():
        cases.append(
            (
                f"write_policy: {label}",
                lambda value=value: with_member(
                    identify_document(), "write_policy", value
                ),
            )
        )
    for label, value in {
        "a string": "tasks",
        "a mapping": {"tasks": 1},
        "an element that is not a string": ["tasks", 3],
    }.items():
        cases.append(
            (
                f"allowed_write_roots: {label}",
                lambda value=value: with_member(
                    identify_document(), "allowed_write_roots", value
                ),
            )
        )
    for member in ("dispatch_digest_source", "current_digest_source"):
        for label, value in {
            "a list": [],
            "no digest_inputs": {"worker": "x"},
            "digest_inputs is a list": {"digest_inputs": []},
            "a non-string digest": {"digest_inputs": {"a.md": 3}},
            "a null digest": {"digest_inputs": {"a.md": None}},
        }.items():
            cases.append(
                (
                    f"{member}: {label}",
                    lambda member=member, value=value: with_member(
                        identify_document(), member, value
                    ),
                )
            )
    for label, value in {
        "a list": [],
        "a non-string digest": {"a.md": 3},
        "a null digest": {"a.md": None},
    }.items():
        cases.append(
            (
                f"dispatch_digest_inputs: {label}",
                lambda value=value: with_member(
                    substitute_only_document(), "dispatch_digest_inputs", value
                ),
            )
        )
    for label, value in {
        "a string": "a.md",
        "a mapping": {"a.md": 1},
        "an element that is not a string": ["a.md", 3],
        "null": None,
    }.items():
        cases.append(
            (
                f"self_write_set: {label}",
                lambda value=value: with_member(
                    substitute_only_document(), "self_write_set", value
                ),
            )
        )
    cases.append(
        (
            "substitute_only: current_digest_source without digest_inputs",
            lambda: with_member(
                substitute_only_document(), "current_digest_source", {"worker": "x"}
            ),
        )
    )
    return cases


class TestCliRejections(TempDirCase):
    """AC-7: every invalid input is exit 2 with empty stdout."""

    def test_ac7_invalid_documents_are_rejected(self):
        cases = rejection_cases()
        self.assertGreater(len(cases), 60)
        for label, build in cases:
            with self.subTest(case=label):
                proc = self.cli(build())
                self.assert_rejected(proc)

    def test_ac7_the_rejection_names_the_member_at_fault(self):
        proc = self.cli(
            with_member(identify_document(), "observed_changes", [{"path": "a.md"}])
        )
        self.assert_rejected(proc)
        self.assertIn(b"observed_changes", proc.stderr)
        proc = self.cli(
            {k: v for k, v in identify_document().items() if k != "write_policy"}
        )
        self.assertIn(b"write_policy", proc.stderr)

    def test_ac7_unparsable_documents_are_rejected(self):
        raw_documents = {
            "not json": b"{not json",
            "an empty file": b"",
            "only whitespace": b"  \n",
            "trailing garbage": json.dumps(identify_document()).encode() + b" x",
            "invalid utf-8": b'{"operation": "\xff"}',
            "a byte order mark": b"\xef\xbb\xbf" + json.dumps(identify_document()).encode(),
            "a NaN constant": b'{"operation": "substitute_only", "x": NaN}',
            "a truncated document": json.dumps(identify_document()).encode()[:-20],
            "deeply nested arrays": b"[" * 100000 + b"]" * 100000,
        }
        for label, data in raw_documents.items():
            with self.subTest(document=label):
                self.write_bytes("input.json", data)
                proc = run_script(self.tmp / "input.json", cwd=self.tmp)
                self.assert_rejected(proc)

    def test_ac7_an_unreadable_input_document_is_rejected(self):
        for label, argument in (
            ("a missing file", self.tmp / "absent.json"),
            ("a directory", self.tmp),
            ("an empty name", ""),
        ):
            with self.subTest(document=label):
                proc = run_script(argument, cwd=self.tmp)
                self.assert_rejected(proc)

    def test_ac7_an_unexpected_failure_exits_2_with_empty_stdout(self):
        module = script_module()
        path = self.write_json("input.json", identify_document())
        stdout = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
        stderr = io.StringIO()
        with mock.patch.object(
            module, "identify_and_substitute", side_effect=RuntimeError("boom")
        ), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = module.main([str(path)])
        stdout.flush()
        self.assertEqual(code, 2)
        self.assertEqual(stdout.buffer.getvalue(), b"")
        self.assertIn("boom", stderr.getvalue())

    def test_ac7_main_in_process_returns_0_and_writes_one_object(self):
        module = script_module()
        path = self.write_json("input.json", identify_document())
        stdout = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = module.main([str(path)])
        stdout.flush()
        self.assertEqual(code, 0, stderr.getvalue())
        self.assertEqual(
            set(json.loads(stdout.buffer.getvalue().decode("utf-8"))),
            {"self_write_set", "digest_source"},
        )

    def test_ac7_module_level_checks_reject_the_malformed_policy_shapes(self):
        module = script_module()
        for label, targets in (
            (
                "repeated path",
                [target("a.md", "create"), target("a.md", "preserve")],
            ),
            ("unknown action", [target("a.md", "overwrite")]),
            ("regenerate without source", [target("a.html", "regenerate")]),
        ):
            with self.subTest(case=label):
                with self.assertRaises(module.InputError):
                    module.identify_self_writes([], {"targets": targets}, [])


# -------------------------------------------------- isolation, docstring ----

SPAWNING_MODULES = frozenset(
    {
        "subprocess",
        "multiprocessing",
        "pty",
        "asyncio",
        "concurrent",
        "ctypes",
        "posix",
        "_posixsubprocess",
    }
)
SPAWNING_OS_NAMES = frozenset({"system", "popen", "startfile", "fork", "forkpty"})
SPAWNING_OS_PREFIXES = ("exec", "spawn", "posix_spawn")
HASHING_MODULES = frozenset({"hashlib", "hmac", "zlib", "binascii"})
FILE_WRITING_ATTRIBUTES = frozenset({"write_text", "write_bytes", "mkdir", "touch"})


def is_spawning_os_name(name):
    return name in SPAWNING_OS_NAMES or name.startswith(SPAWNING_OS_PREFIXES)


def imported_modules(source):
    modules = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                modules.add(node.module.split(".")[0])
            else:
                modules.add("." * node.level + (node.module or ""))
    return modules


def spawning_facilities(source):
    found = set(imported_modules(source) & SPAWNING_MODULES)
    for node in ast.walk(ast.parse(source)):
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and node.value.id == "os"
            and is_spawning_os_name(node.attr)
        ):
            found.add(f"os.{node.attr}")
        elif isinstance(node, ast.ImportFrom) and node.module == "os":
            found.update(
                f"os.{alias.name}"
                for alias in node.names
                if is_spawning_os_name(alias.name)
            )
    return found


def non_stdlib_modules(source):
    return {m for m in imported_modules(source) if m not in sys.stdlib_module_names}


def open_modes(source):
    """The literal mode of every `open(...)` call (`r` when none is given)."""
    modes = set()
    for node in ast.walk(ast.parse(source)):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "open"
        ):
            mode = "r"
            if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
                mode = node.args[1].value
            for keyword in node.keywords:
                if keyword.arg == "mode" and isinstance(keyword.value, ast.Constant):
                    mode = keyword.value.value
            modes.add(mode)
    return modes


LOADING_MODULES = frozenset({"importlib", "runpy", "imp", "pkgutil", "zipimport"})


def loading_facilities(source):
    """The module-loading facilities `source` imports or calls."""
    found = set(imported_modules(source) & LOADING_MODULES)
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Name) and node.id == "__import__":
            found.add("__import__")
    return found


def file_writing_calls(source):
    return {
        node.attr
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Attribute) and node.attr in FILE_WRITING_ATTRIBUTES
    }


class TestIsolation(unittest.TestCase):
    """AC-7: standard library only; no hashing, child process or file write."""

    @classmethod
    def setUpClass(cls):
        cls.source = SCRIPT.read_text(encoding="utf-8")

    def test_ac7_the_script_imports_only_standard_library_modules(self):
        self.assertEqual(non_stdlib_modules(self.source), set())

    def test_ac7_the_import_set_is_not_empty(self):
        # Non-vacuity: the extraction read real imports.
        self.assertIn("json", imported_modules(self.source))

    def test_ac7_the_script_imports_no_process_spawning_facility(self):
        self.assertEqual(spawning_facilities(self.source), set())

    def test_ac7_the_script_imports_no_hashing_module(self):
        self.assertEqual(imported_modules(self.source) & HASHING_MODULES, set())

    def test_ac6_the_script_imports_no_module_loading_facility(self):
        # task0001 of self-write-digest-path-normalization, AC-6 (NFR1): the
        # script cannot load validate-worker-output.py at runtime.
        self.assertEqual(loading_facilities(self.source), set())

    def test_ac6_forged_sources_trip_the_module_loading_check(self):
        self.assertEqual(
            loading_facilities(
                "import importlib.util\nfrom runpy import run_path\n"
                "import pkgutil\n__import__('x')\n"
            ),
            {"importlib", "runpy", "pkgutil", "__import__"},
        )
        self.assertEqual(loading_facilities("import json\nimport sys\n"), set())

    def test_ac7_the_script_only_opens_files_for_binary_reading(self):
        self.assertEqual(open_modes(self.source), {"rb"})
        self.assertEqual(file_writing_calls(self.source), set())

    def test_ac7_the_script_parses_no_options(self):
        self.assertEqual(
            imported_modules(self.source) & {"argparse", "optparse", "getopt", "click"},
            set(),
        )

    def test_ac7_forged_sources_trip_each_check(self):
        # Negative proofs, parsed with `ast` and never executed.
        self.assertEqual(
            non_stdlib_modules("import json\nimport yaml\nfrom requests import get\n"),
            {"yaml", "requests"},
        )
        self.assertEqual(
            spawning_facilities(
                "import subprocess\nimport os\nfrom os import system\n"
                "from multiprocessing import Pool\nos.popen('x')\n"
                "os.execvp('x', ['x'])\nos.posix_spawn('x', ['x'], {})\n"
            ),
            {
                "subprocess",
                "multiprocessing",
                "os.system",
                "os.popen",
                "os.execvp",
                "os.posix_spawn",
            },
        )
        self.assertEqual(spawning_facilities("import os\nos.read(0, 1)\n"), set())
        self.assertEqual(
            open_modes("open('a')\nopen('a', 'wb')\nopen('a', mode='a')\n"),
            {"r", "wb", "a"},
        )
        self.assertEqual(
            file_writing_calls("p.write_text('x')\np.write_bytes(b'x')\np.read_text()\n"),
            {"write_text", "write_bytes"},
        )
        self.assertEqual(
            imported_modules("import hashlib\nfrom zlib import crc32\n")
            & HASHING_MODULES,
            {"hashlib", "zlib"},
        )


class TestScriptFileProperties(unittest.TestCase):
    """AC-7: the shebang and the module docstring (the CLI contract)."""

    @classmethod
    def setUpClass(cls):
        cls.source = SCRIPT.read_text(encoding="utf-8")
        cls.docstring = ast.get_docstring(ast.parse(cls.source)) or ""

    def test_the_first_line_is_a_python3_shebang(self):
        self.assertRegex(self.source.splitlines()[0], r"\A#!.*\bpython3\b")

    def test_the_docstring_cites_rule_r1_in_one_paragraph(self):
        paragraphs = [" ".join(p.split()) for p in self.docstring.split("\n\n")]
        needed = (
            "references/contracts/worker-envelope.md",
            "Rule R1",
            "Recomputation and comparison timing",
        )
        self.assertTrue(
            any(all(token in paragraph for token in needed) for paragraph in paragraphs),
            self.docstring,
        )

    def test_the_docstring_states_the_command_line_contract(self):
        normalised = " ".join(self.docstring.split())
        for token in (
            "identify_and_substitute",
            "substitute_only",
            "self_write_set",
            "digest_source",
            "observed_changes",
            "write_policy",
            "allowed_write_roots",
            "dispatch_digest_inputs",
            "current_digest_source",
            "dispatch_digest_source",
        ):
            with self.subTest(token=token):
                self.assertIn(token, normalised)

    def test_the_docstring_lists_the_exit_codes_0_and_2(self):
        for code in ("0", "2"):
            with self.subTest(code=code):
                self.assertRegex(self.docstring, rf"(?m)^\s*{code}\b.*")

    def test_the_script_does_not_compute_a_digest_in_its_docstring_contract(self):
        normalised = " ".join(self.docstring.split())
        self.assertIn("computes no", normalised)


class TestNormalizationDocstrings(unittest.TestCase):
    """task0001 of self-write-digest-path-normalization, AC-5: the module
    docstring (its `allowed_write_roots` description) and the docstrings of
    `_segments` and `_check_allowed_roots` state the normalization the
    allowed-root containment applies."""

    SEPARATOR = "`\\` is equivalent to `/`"
    DROPPED = "empty and `.` segments are dropped"
    UNSAFE = "empty, starts with `/`, contains NUL or has a `..` segment"
    NEVER = r"never contains.{0,40}never contained"
    NO_SEGMENTS = r"no segments left.{0,80}contains every relative path"

    @classmethod
    def setUpClass(cls):
        tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
        cls.module_doc = " ".join((ast.get_docstring(tree) or "").split())
        cls.function_docs = {
            node.name: " ".join((ast.get_docstring(node) or "").split())
            for node in tree.body
            if isinstance(node, ast.FunctionDef)
        }

    def assert_states_separator_and_dropped(self, text):
        self.assertIn(self.SEPARATOR, text)
        self.assertIn(self.DROPPED, text)

    def assert_states_whole_rule(self, text):
        self.assert_states_separator_and_dropped(text)
        self.assertIn(self.UNSAFE, text)
        self.assertRegex(text, self.NEVER)
        self.assertRegex(text, self.NO_SEGMENTS)

    def test_ac5_the_module_docstring_states_the_normalization(self):
        self.assert_states_whole_rule(self.module_doc)

    def test_ac5_the_module_docstring_keeps_the_comparison_lexical(self):
        self.assertIn("compared lexically, segment by segment", self.module_doc)
        self.assertRegex(self.module_doc, r"no path is resolved against the filesystem")

    def test_ac5_segments_states_the_separator_and_the_dropped_segments(self):
        self.assert_states_separator_and_dropped(self.function_docs["_segments"])

    def test_ac5_check_allowed_roots_states_the_normalization(self):
        self.assert_states_whole_rule(self.function_docs["_check_allowed_roots"])

    def test_ac5_the_docstring_probe_fires_on_text_without_the_rule(self):
        # Control: the old wording states none of it.
        old = (
            "the envelope's top-level list of strings. Roots and paths are "
            "compared lexically, segment by segment."
        )
        with self.assertRaises(AssertionError):
            self.assert_states_whole_rule(old)


if __name__ == "__main__":
    unittest.main()
