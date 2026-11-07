"""Tests for task0002 (feature-docs/large-diff-review-coverage): the review
input measurement, shard split and dispatch cap script
`em-workflow/scripts/review-shards.py`.

The script measures the review input of each changed file in characters,
splits the input into file-level shards above 200,000 characters, applies the
per-perspective shard cap, and prints only paths, character counts and shard
composition. The tests run it as a child process with one input-document
argument, and load it by file path for direct checks of its functions. Shell
and `git` related behavior runs in disposable git repositories in temporary
directories; nothing touches the network.

Covers task0002 Acceptance Criteria
(feature-docs/large-diff-review-coverage/tasks/task0002.md):

- AC-1 (FR5): per-file measurement (TestMeasurement, TestCharacterCounting).
- AC-2 (FR6, NFR1): the 200,000-character split (TestSplit).
- AC-3 (FR7, TM-3): the per-perspective shard cap (TestShardCap).
- AC-4 (NFR4): byte-identical output in any `changed_files` order
  (TestDeterminism).
- AC-5 (NFR3, TM-9): the output contract and the absence of diff text
  (TestOutputContract).
- AC-6 (TM-1, TM-2): invalid input, FIFO and symlink refusal, literal
  pathspecs and no execution of configured drivers (TestInvalidInput,
  TestRefusalBeforeAnyRead, TestLiteralPathspecs, TestConfiguredDrivers).
- AC-7 (FR18, NFR6): standard library only (TestStandardLibraryOnly).

Every child process carries a timeout, so a script that wrongly opens a FIFO
fails a test instead of hanging it. Large inputs are a few files of 100,000
to 250,000 characters; no test creates load beyond that.
"""

import ast
import importlib.util
import json
import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "em-workflow" / "scripts" / "review-shards.py"
THIS_MODULE = Path(__file__).resolve()

CALL_TIMEOUT_SECONDS = 60
LIMIT = 200_000
OUTPUT_KEYS = [
    "limit",
    "total_chars",
    "split",
    "files",
    "shards",
    "shard_cap",
    "dispatched_shards",
    "excess_shards",
]
SENTINEL = "SENTINEL-4c1e9a7b52d3"
ZERO_ID = "0" * 40
ERROR_PREFIX = b"review-shards: "
ROOT_DEFAULT = object()


def load_script():
    spec = importlib.util.spec_from_file_location("review_shards_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    previous = sys.dont_write_bytecode
    sys.dont_write_bytecode = True
    try:
        spec.loader.exec_module(module)
    finally:
        sys.dont_write_bytecode = previous
    return module


# ------------------------------------------------------------- helpers ----


class Workspace:
    """A temporary directory holding a project tree, an input-document
    location outside it, and a private home so a user's git configuration
    does not leak into a run."""

    def __init__(self, test):
        self._temp = tempfile.TemporaryDirectory()
        test.addCleanup(self._temp.cleanup)
        base = Path(self._temp.name).resolve()
        self.base = base
        self.root = base / "project"
        self.root.mkdir()
        self.outside = base / "outside"
        self.outside.mkdir()
        self.home = base / "home"
        self.home.mkdir()
        self.counter = 0

    def write(self, name, data):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if isinstance(data, str):
            data = data.encode("utf-8")
        path.write_bytes(data)
        return path

    def environment(self, extra=None):
        environment = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("GIT_")
        }
        environment["HOME"] = str(self.home)
        environment["XDG_CONFIG_HOME"] = str(self.home / "xdg")
        environment.update(extra or {})
        return environment

    def git(self, *arguments, extra_environment=None):
        environment = self.environment(extra_environment)
        environment.update(
            {
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_AUTHOR_NAME": "Test",
                "GIT_AUTHOR_EMAIL": "test@example.invalid",
                "GIT_COMMITTER_NAME": "Test",
                "GIT_COMMITTER_EMAIL": "test@example.invalid",
            }
        )
        completed = subprocess.run(
            ["git", *arguments],
            cwd=self.root,
            env=environment,
            capture_output=True,
            timeout=CALL_TIMEOUT_SECONDS,
        )
        if completed.returncode != 0:
            raise AssertionError(
                f"git {' '.join(arguments)} failed: {completed.stderr.decode()}"
            )
        return completed.stdout.decode("utf-8", errors="replace")

    def init_repo(self):
        self.git("init", "-q")
        return self

    def commit_all(self, message="commit"):
        self.git("add", "-A")
        self.git("commit", "-q", "-m", message)
        return self.git("rev-parse", "HEAD").strip()

    def blob_id(self, name):
        return self.git("hash-object", "--", name).strip()

    def document(self, files, mode="diff", base="HEAD", count=1, root=ROOT_DEFAULT):
        return {
            "project_root": str(self.root) if root is ROOT_DEFAULT else root,
            "review_mode": mode,
            "diff_base": base if mode == "diff" else None,
            "changed_files": list(files),
            "perspective_count": count,
        }

    def run(self, document, extra_environment=None, raw=None):
        """Run the script on `document` (or on the raw text `raw`); returns
        the CompletedProcess with bytes output."""
        self.counter += 1
        path = self.base / f"input-{self.counter}.json"
        if raw is None:
            path.write_text(json.dumps(document), encoding="utf-8")
        elif isinstance(raw, bytes):
            path.write_bytes(raw)
        else:
            path.write_text(raw, encoding="utf-8")
        return self.run_arguments([str(path)], extra_environment)

    def run_arguments(self, arguments, extra_environment=None):
        return subprocess.run(
            [sys.executable, str(SCRIPT), *arguments],
            cwd=self.outside,
            env=self.environment(extra_environment),
            capture_output=True,
            timeout=CALL_TIMEOUT_SECONDS,
        )

    def measure(self, document, extra_environment=None):
        """Run, require success, and return the parsed output object."""
        completed = self.run(document, extra_environment)
        if completed.returncode != 0:
            raise AssertionError(
                f"exit {completed.returncode}: {completed.stderr.decode()}"
            )
        return json.loads(completed.stdout.decode("utf-8"))

    def install_git_shim(self):
        """A `git` that only records that it ran; returns (PATH environment,
        marker path)."""
        shim_dir = self.base / "shim"
        shim_dir.mkdir(exist_ok=True)
        marker = self.base / "git-shim-ran"
        shim = shim_dir / "git"
        shim.write_text(f'#!/bin/sh\ntouch "{marker}"\nexit 99\n', encoding="utf-8")
        shim.chmod(0o755)
        path = f"{shim_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        return {"PATH": path}, marker


def assert_failed_cleanly(test, completed):
    """The run exited 2 with a message from the script on stderr and nothing
    on stdout. The message prefix proves the script itself refused the run."""
    test.assertEqual(
        completed.returncode, 2, completed.stderr.decode("utf-8", "replace")
    )
    test.assertEqual(completed.stdout, b"")
    test.assertTrue(
        completed.stderr.startswith(ERROR_PREFIX),
        completed.stderr[:200],
    )


def modified_diff_text(name, old_blob, new_blob, old_line, new_line):
    """The `git diff` text of a one-line file whose only line changed, as the
    script's options produce it (full index ids, a/ and b/ prefixes)."""
    return (
        f"diff --git a/{name} b/{name}\n"
        f"index {old_blob}..{new_blob} 100644\n"
        f"--- a/{name}\n"
        f"+++ b/{name}\n"
        "@@ -1 +1 @@\n"
        f"-{old_line}\n"
        f"+{new_line}\n"
    )


def added_diff_text(name, new_blob, lines):
    body = "".join(f"+{line}\n" for line in lines)
    return (
        f"diff --git a/{name} b/{name}\n"
        "new file mode 100644\n"
        f"index {ZERO_ID}..{new_blob}\n"
        "--- /dev/null\n"
        f"+++ b/{name}\n"
        f"@@ -0,0 +1,{len(lines)} @@\n"
        f"{body}"
    )


def synthetic_counts(sizes):
    return [(f"f{index:03d}.txt", size) for index, size in enumerate(sizes)]


# ------------------------------------------------------------------ AC-1 ----


class TestMeasurement(unittest.TestCase):
    """AC-1 (FR5): what each mode counts for each kind of file."""

    def test_diff_mode_counts_a_tracked_modified_file_by_its_diff_text(self):
        workspace = Workspace(self).init_repo()
        workspace.write("a.txt", "old line\n")
        workspace.commit_all()
        old_blob = workspace.blob_id("a.txt")
        workspace.write("a.txt", "new line\n")
        expected = modified_diff_text(
            "a.txt", old_blob, workspace.blob_id("a.txt"), "old line", "new line"
        )
        result = workspace.measure(workspace.document(["a.txt"]))
        self.assertEqual(result["files"], [{"path": "a.txt", "chars": len(expected)}])
        self.assertGreater(len(expected), len("new line\n"))
        self.assertEqual(result["total_chars"], len(expected))

    def test_a_non_ascii_path_is_counted_with_its_literal_name_in_the_diff(self):
        workspace = Workspace(self).init_repo()
        name = "日本語/ファイル.txt"
        workspace.write(name, "old line\n")
        workspace.commit_all()
        old_blob = workspace.blob_id(name)
        workspace.write(name, "new line\n")
        expected = modified_diff_text(
            name, old_blob, workspace.blob_id(name), "old line", "new line"
        )
        result = workspace.measure(workspace.document([name]))
        self.assertEqual(result["files"], [{"path": name, "chars": len(expected)}])

    def test_diff_mode_counts_an_untracked_file_by_its_content(self):
        workspace = Workspace(self).init_repo()
        workspace.write("tracked.txt", "tracked\n")
        workspace.commit_all()
        workspace.write("fresh.txt", "alpha\nbeta\n")
        result = workspace.measure(workspace.document(["fresh.txt"]))
        self.assertEqual(result["files"], [{"path": "fresh.txt", "chars": 11}])

    def test_diff_mode_counts_an_unchanged_tracked_file_by_its_content(self):
        workspace = Workspace(self).init_repo()
        workspace.write("same.txt", "unchanged text\n")
        workspace.commit_all()
        result = workspace.measure(workspace.document(["same.txt"]))
        self.assertEqual(result["files"], [{"path": "same.txt", "chars": 15}])

    def test_whole_codebase_mode_counts_content_without_running_git(self):
        workspace = Workspace(self)
        workspace.write("src/one.py", "x" * 1234)
        workspace.write("two.txt", "short")
        shim_environment, marker = workspace.install_git_shim()
        result = workspace.measure(
            workspace.document(["src/one.py", "two.txt"], mode="whole-codebase"),
            shim_environment,
        )
        self.assertEqual(
            result["files"],
            [{"path": "src/one.py", "chars": 1234}, {"path": "two.txt", "chars": 5}],
        )
        self.assertFalse(marker.exists(), "git was run in whole-codebase mode")

    def test_diff_mode_does_run_the_shimmed_git(self):
        # Positive control for the shim the other tests rely on.
        workspace = Workspace(self).init_repo()
        workspace.write("a.txt", "text\n")
        workspace.commit_all()
        shim_environment, marker = workspace.install_git_shim()
        completed = workspace.run(workspace.document(["a.txt"]), shim_environment)
        self.assertTrue(marker.exists())
        assert_failed_cleanly(self, completed)

    def test_a_staged_rename_counts_the_per_path_diff_text(self):
        workspace = Workspace(self).init_repo()
        workspace.write("old.txt", "alpha\nbeta\n")
        workspace.commit_all()
        workspace.git("mv", "old.txt", "new.txt")
        expected = added_diff_text(
            "new.txt", workspace.blob_id("new.txt"), ["alpha", "beta"]
        )
        result = workspace.measure(workspace.document(["new.txt"]))
        self.assertEqual(result["files"], [{"path": "new.txt", "chars": len(expected)}])
        self.assertNotEqual(len(expected), len("alpha\nbeta\n"))

    def test_a_rename_in_the_working_tree_counts_the_content_of_the_new_path(self):
        workspace = Workspace(self).init_repo()
        workspace.write("old.txt", "alpha\nbeta\n")
        workspace.commit_all()
        os.rename(workspace.root / "old.txt", workspace.root / "new.txt")
        result = workspace.measure(workspace.document(["new.txt"]))
        self.assertEqual(result["files"], [{"path": "new.txt", "chars": 11}])

    def test_a_binary_file_counts_the_per_path_diff_text(self):
        workspace = Workspace(self).init_repo()
        workspace.write("blob.dat", b"\x00\x01\x02" * 700)
        workspace.commit_all()
        old_blob = workspace.blob_id("blob.dat")
        workspace.write("blob.dat", b"\x00\x03\x04" * 700)
        expected = (
            "diff --git a/blob.dat b/blob.dat\n"
            f"index {old_blob}..{workspace.blob_id('blob.dat')} 100644\n"
            "Binary files a/blob.dat and b/blob.dat differ\n"
        )
        result = workspace.measure(workspace.document(["blob.dat"]))
        self.assertEqual(result["files"], [{"path": "blob.dat", "chars": len(expected)}])
        self.assertLess(len(expected), 2100)

    def test_a_repository_without_a_commit_counts_content(self):
        workspace = Workspace(self).init_repo()
        workspace.write("staged.txt", "staged text\n")
        workspace.git("add", "staged.txt")
        workspace.write("loose.txt", "loose\n")
        result = workspace.measure(workspace.document(["loose.txt", "staged.txt"]))
        self.assertEqual(
            result["files"],
            [{"path": "loose.txt", "chars": 6}, {"path": "staged.txt", "chars": 12}],
        )

    def test_a_commit_id_base_measures_against_that_commit(self):
        workspace = Workspace(self).init_repo()
        workspace.write("a.txt", "first\n")
        first = workspace.commit_all("first")
        first_blob = workspace.blob_id("a.txt")
        workspace.write("a.txt", "second\n")
        workspace.commit_all("second")
        workspace.write("a.txt", "third\n")
        expected = modified_diff_text(
            "a.txt", first_blob, workspace.blob_id("a.txt"), "first", "third"
        )
        result = workspace.measure(workspace.document(["a.txt"], base=first))
        self.assertEqual(result["files"], [{"path": "a.txt", "chars": len(expected)}])

    def test_a_commit_id_missing_from_the_repository_fails(self):
        workspace = Workspace(self).init_repo()
        workspace.write("a.txt", "text\n")
        workspace.commit_all()
        completed = workspace.run(workspace.document(["a.txt"], base="1" * 40))
        assert_failed_cleanly(self, completed)

    def test_head_outside_a_repository_fails(self):
        workspace = Workspace(self)
        workspace.write("a.txt", "text\n")
        completed = workspace.run(workspace.document(["a.txt"]))
        assert_failed_cleanly(self, completed)

    def test_no_changed_files_gives_an_empty_unsplit_result_without_git(self):
        workspace = Workspace(self)
        shim_environment, marker = workspace.install_git_shim()
        result = workspace.measure(workspace.document([]), shim_environment)
        self.assertEqual(result["total_chars"], 0)
        self.assertEqual(result["files"], [])
        self.assertFalse(result["split"])
        self.assertEqual(result["shards"], [{"index": 1, "paths": [], "chars": 0}])
        self.assertFalse(marker.exists())


class TestReadOnly(unittest.TestCase):
    """AC-1 (FR5): a measurement changes no file of the reviewed tree, no
    object, ref or configuration of the repository, and nothing staged. (git
    itself may refresh the stat data cached in the index, as for any
    `git diff`; that file is left out of the comparison.)"""

    def snapshot(self, root):
        return {
            str(path.relative_to(root)): path.read_bytes()
            for path in sorted(root.rglob("*"))
            if path.is_file()
            and not path.is_symlink()
            and path != root / ".git" / "index"
        }

    def test_diff_mode_leaves_the_tree_and_the_staged_content_unchanged(self):
        workspace = Workspace(self).init_repo()
        workspace.write("a.txt", "kept\n")
        workspace.write("b.txt", "changed\n")
        workspace.write("c.txt", "staged\n")
        workspace.commit_all()
        workspace.write("b.txt", "changed again\n")
        workspace.write("c.txt", "staged then edited\n")
        workspace.git("add", "c.txt")
        workspace.write("c.txt", "edited after staging\n")
        workspace.write("d.txt", "untracked\n")
        before = self.snapshot(workspace.root)
        staged_before = workspace.git("ls-files", "-s")
        result = workspace.measure(
            workspace.document(["a.txt", "b.txt", "c.txt", "d.txt"])
        )
        self.assertEqual(len(result["files"]), 4)
        self.assertEqual(self.snapshot(workspace.root), before)
        self.assertEqual(workspace.git("ls-files", "-s"), staged_before)


class TestCharacterCounting(unittest.TestCase):
    """AC-1 (FR5): characters are counted after UTF-8 decoding with invalid
    bytes replaced."""

    @classmethod
    def setUpClass(cls):
        cls.module = load_script()

    def test_characters_not_bytes_are_counted(self):
        workspace = Workspace(self)
        workspace.write("jp.txt", "日本語のテキスト")
        result = workspace.measure(
            workspace.document(["jp.txt"], mode="whole-codebase")
        )
        self.assertEqual(result["files"], [{"path": "jp.txt", "chars": 8}])

    def test_each_invalid_byte_counts_as_one_replacement_character(self):
        workspace = Workspace(self)
        workspace.write("bad.bin", b"ab\xff\xfecd")
        result = workspace.measure(
            workspace.document(["bad.bin"], mode="whole-codebase")
        )
        self.assertEqual(result["files"], [{"path": "bad.bin", "chars": 6}])

    def test_chunked_counting_equals_one_shot_decoding_at_every_split(self):
        samples = [
            "plain ascii".encode(),
            "あいう日本語🙂 mixed é".encode(),
            b"ab\xff\xfecd",
            "tail cut".encode()[:-1] + "é".encode()[:1],
            b"\xf0\x9f\x99",
            b"\xe3\x81\xe3\x81\x82",
            b"",
        ]
        for sample in samples:
            expected = len(sample.decode("utf-8", errors="replace"))
            for cut in range(len(sample) + 1):
                with self.subTest(sample=sample, cut=cut):
                    chunks = [sample[:cut], sample[cut:]]
                    self.assertEqual(self.module._count_chunks(chunks), expected)

    def test_a_multibyte_character_across_the_read_chunk_boundary(self):
        module = load_script()
        module.READ_CHUNK_BYTES = 5
        workspace = Workspace(self)
        text = "あ" * 7 + "x"
        workspace.write("jp.txt", text)
        self.assertEqual(module.count_content(str(workspace.root), "jp.txt"), 8)


# ------------------------------------------------------------------ AC-2 ----


class TestSplit(unittest.TestCase):
    """AC-2 (FR6, NFR1): the split at 200,000 characters."""

    @classmethod
    def setUpClass(cls):
        cls.module = load_script()

    def build(self, sizes, count=1):
        return self.module.build_result(synthetic_counts(sizes), count)

    def assert_shard_invariants(self, result, counts):
        paths = [path for path, _ in counts]
        sizes = dict(counts)
        seen = [path for shard in result["shards"] for path in shard["paths"]]
        self.assertEqual(sorted(seen), sorted(paths))
        self.assertEqual(len(seen), len(set(seen)))
        self.assertEqual(
            [shard["index"] for shard in result["shards"]],
            list(range(1, len(result["shards"]) + 1)),
        )
        self.assertEqual(seen, sorted(paths))
        for shard in result["shards"]:
            self.assertEqual(shard["chars"], sum(sizes[p] for p in shard["paths"]))
            if len(shard["paths"]) > 1:
                self.assertLessEqual(shard["chars"], LIMIT)

    def test_a_total_at_the_limit_is_not_split(self):
        result = self.build([100_000, 100_000])
        self.assertFalse(result["split"])
        self.assertEqual(result["total_chars"], LIMIT)
        self.assertEqual(len(result["shards"]), 1)
        self.assertEqual(result["shards"][0]["index"], 1)
        self.assertEqual(
            result["shards"][0]["paths"], ["f000.txt", "f001.txt"]
        )
        self.assertEqual(result["limit"], LIMIT)

    def test_a_total_below_the_limit_is_one_shard_with_every_path(self):
        result = self.build([10, 20, 30])
        self.assertFalse(result["split"])
        self.assertEqual(
            result["shards"],
            [{"index": 1, "paths": ["f000.txt", "f001.txt", "f002.txt"], "chars": 60}],
        )

    def test_a_total_one_above_the_limit_is_split(self):
        counts = synthetic_counts([100_000, 100_000, 1])
        result = self.module.build_result(counts, 1)
        self.assertTrue(result["split"])
        self.assertEqual(result["total_chars"], LIMIT + 1)
        self.assertEqual(
            [shard["paths"] for shard in result["shards"]],
            [["f000.txt", "f001.txt"], ["f002.txt"]],
        )
        self.assert_shard_invariants(result, counts)

    def test_shards_are_filled_next_fit_not_best_fit(self):
        counts = synthetic_counts([120_000, 100_000, 90_000, 60_000])
        result = self.module.build_result(counts, 1)
        self.assertEqual(
            [shard["paths"] for shard in result["shards"]],
            [["f000.txt"], ["f001.txt", "f002.txt"], ["f003.txt"]],
        )
        self.assert_shard_invariants(result, counts)

    def test_a_shard_may_be_exactly_the_limit(self):
        counts = synthetic_counts([150_000, 50_000, 1])
        result = self.module.build_result(counts, 1)
        self.assertEqual(
            [(s["paths"], s["chars"]) for s in result["shards"]],
            [(["f000.txt", "f001.txt"], LIMIT), (["f002.txt"], 1)],
        )

    def test_a_file_over_the_limit_forms_its_own_shard(self):
        counts = synthetic_counts([30_000, 250_000, 40_000, 10_000])
        result = self.module.build_result(counts, 1)
        self.assertEqual(
            [(s["paths"], s["chars"]) for s in result["shards"]],
            [
                (["f000.txt"], 30_000),
                (["f001.txt"], 250_000),
                (["f002.txt", "f003.txt"], 50_000),
            ],
        )
        self.assert_shard_invariants(result, counts)

    def test_a_single_file_over_the_limit_is_a_split_result_with_one_shard(self):
        result = self.build([LIMIT + 1])
        self.assertTrue(result["split"])
        self.assertEqual(len(result["shards"]), 1)
        self.assertEqual(result["shards"][0]["chars"], LIMIT + 1)

    def test_a_file_of_exactly_the_limit_is_not_oversized(self):
        counts = synthetic_counts([LIMIT, 1])
        result = self.module.build_result(counts, 1)
        self.assertEqual(
            [shard["paths"] for shard in result["shards"]],
            [["f000.txt"], ["f001.txt"]],
        )

    def test_empty_files_do_not_start_shards(self):
        counts = synthetic_counts([0, 150_000, 0, 60_000, 0])
        result = self.module.build_result(counts, 1)
        self.assertEqual(
            [shard["paths"] for shard in result["shards"]],
            [["f000.txt", "f001.txt", "f002.txt"], ["f003.txt", "f004.txt"]],
        )
        self.assert_shard_invariants(result, counts)

    def test_invariants_hold_over_varied_size_lists(self):
        size_lists = [
            [1] * 5,
            [199_999, 2, 199_999, 2],
            [100_000] * 5,
            [LIMIT, LIMIT, LIMIT],
            [60_000, 70_000, 80_000, 90_000, 100_000, 110_000],
            [250_000, 1, 250_000, 1, 250_000],
            [0, 0, LIMIT + 1, 0],
        ]
        for sizes in size_lists:
            counts = synthetic_counts(sizes)
            with self.subTest(sizes=sizes):
                result = self.module.build_result(counts, 1)
                self.assertEqual(result["split"], sum(sizes) > LIMIT)
                self.assert_shard_invariants(result, counts)

    def test_shards_follow_path_code_point_order(self):
        workspace = Workspace(self)
        names = ["b.txt", "B.txt", "a/b.txt", "a.txt", "é.txt", "Z.txt"]
        for name in names:
            workspace.write(name, "x" * 70_000)
        result = workspace.measure(
            workspace.document(names, mode="whole-codebase")
        )
        ordered = sorted(names)
        self.assertEqual(ordered[:2], ["B.txt", "Z.txt"])
        self.assertLess(ordered.index("a.txt"), ordered.index("a/b.txt"))
        self.assertEqual([entry["path"] for entry in result["files"]], ordered)
        flattened = [path for shard in result["shards"] for path in shard["paths"]]
        self.assertEqual(flattened, ordered)
        self.assertEqual(
            [shard["paths"] for shard in result["shards"]],
            [ordered[0:2], ordered[2:4], ordered[4:6]],
        )

    def test_real_files_split_end_to_end(self):
        workspace = Workspace(self)
        workspace.write("a.txt", "a" * 120_000)
        workspace.write("b.txt", "b" * 100_000)
        workspace.write("c.txt", "c" * 250_000)
        result = workspace.measure(
            workspace.document(["a.txt", "b.txt", "c.txt"], mode="whole-codebase")
        )
        self.assertTrue(result["split"])
        self.assertEqual(result["total_chars"], 470_000)
        self.assertEqual(
            [(s["index"], s["paths"], s["chars"]) for s in result["shards"]],
            [
                (1, ["a.txt"], 120_000),
                (2, ["b.txt"], 100_000),
                (3, ["c.txt"], 250_000),
            ],
        )


# ------------------------------------------------------------------ AC-3 ----


class TestShardCap(unittest.TestCase):
    """AC-3 (FR7, TM-3): the per-perspective shard cap."""

    @classmethod
    def setUpClass(cls):
        cls.module = load_script()

    def shard_sizes(self, shard_count):
        # Every file is over half the limit, so every file is its own shard.
        return [150_000] * shard_count

    def test_cap_and_dispatch_split_below_at_and_above_the_cap(self):
        for count in range(1, 7):
            cap = 24 // count
            for shard_count in (cap - 1, cap, cap + 1):
                with self.subTest(perspectives=count, shards=shard_count):
                    counts = synthetic_counts(self.shard_sizes(shard_count))
                    result = self.module.build_result(counts, count)
                    self.assertEqual(len(result["shards"]), shard_count)
                    self.assertEqual(result["shard_cap"], cap)
                    self.assertEqual(
                        result["dispatched_shards"],
                        list(range(1, min(shard_count, cap) + 1)),
                    )
                    self.assertEqual(
                        result["excess_shards"],
                        list(range(cap + 1, shard_count + 1)),
                    )

    def test_cap_is_floor_of_twenty_four_over_the_count_for_every_count(self):
        counts = synthetic_counts([1])
        for count in range(1, 25):
            with self.subTest(perspectives=count):
                result = self.module.build_result(counts, count)
                self.assertEqual(result["shard_cap"], 24 // count)
                self.assertLessEqual(count * result["shard_cap"], 24)
                self.assertGreaterEqual(result["shard_cap"], 1)

    def test_excess_shards_are_the_shards_at_the_end_of_the_path_order(self):
        counts = synthetic_counts([150_000] * 5)
        result = self.module.build_result(counts, 6)
        self.assertEqual(result["dispatched_shards"], [1, 2, 3, 4])
        self.assertEqual(result["excess_shards"], [5])
        self.assertEqual(result["shards"][4]["paths"], ["f004.txt"])

    def test_an_unsplit_pass_dispatches_its_single_shard(self):
        result = self.module.build_result(synthetic_counts([10]), 24)
        self.assertEqual(result["shard_cap"], 1)
        self.assertEqual(result["dispatched_shards"], [1])
        self.assertEqual(result["excess_shards"], [])

    def test_the_cap_applies_end_to_end(self):
        workspace = Workspace(self)
        names = ["a.txt", "b.txt", "c.txt"]
        for name in names:
            workspace.write(name, name[0] * 150_000)
        result = workspace.measure(
            workspace.document(names, mode="whole-codebase", count=24)
        )
        self.assertEqual(result["shard_cap"], 1)
        self.assertEqual(result["dispatched_shards"], [1])
        self.assertEqual(result["excess_shards"], [2, 3])


# ------------------------------------------------------------------ AC-4 ----


class TestDeterminism(unittest.TestCase):
    """AC-4 (NFR4): the same input in any order gives identical bytes."""

    ORDERS = (
        ["a.txt", "b/c.txt", "d.txt", "e.txt"],
        ["e.txt", "d.txt", "b/c.txt", "a.txt"],
        ["d.txt", "a.txt", "e.txt", "b/c.txt"],
    )

    def prepare(self, workspace):
        workspace.write("a.txt", "a" * 90_000)
        workspace.write("b/c.txt", "c" * 90_000)
        workspace.write("d.txt", "d" * 90_000)
        workspace.write("e.txt", "e" * 20)

    def test_whole_codebase_output_is_identical_in_any_order_and_run(self):
        workspace = Workspace(self)
        self.prepare(workspace)
        outputs = set()
        for order in self.ORDERS:
            for _ in range(2):
                completed = workspace.run(
                    workspace.document(order, mode="whole-codebase", count=3)
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
                outputs.add(completed.stdout)
        self.assertEqual(len(outputs), 1)

    def test_diff_output_is_identical_in_any_order_and_run(self):
        workspace = Workspace(self).init_repo()
        self.prepare(workspace)
        workspace.commit_all()
        workspace.write("a.txt", "A" * 90_000)
        workspace.write("d.txt", "D" * 90_000)
        workspace.write("e.txt", "E" * 20)
        outputs = set()
        for order in self.ORDERS:
            for _ in range(2):
                completed = workspace.run(workspace.document(order, count=3))
                self.assertEqual(completed.returncode, 0, completed.stderr)
                outputs.add(completed.stdout)
        self.assertEqual(len(outputs), 1)
        result = json.loads(outputs.pop().decode("utf-8"))
        self.assertEqual(
            [entry["path"] for entry in result["files"]],
            sorted(self.ORDERS[0]),
        )


# ------------------------------------------------------------------ AC-5 ----


class TestOutputContract(unittest.TestCase):
    """AC-5 (NFR3, TM-9): exactly the contract keys, project-relative paths,
    and no diff text on any stream."""

    def test_the_output_object_has_exactly_the_eight_keys_in_order(self):
        workspace = Workspace(self)
        workspace.write("a.txt", "text")
        completed = workspace.run(
            workspace.document(["a.txt"], mode="whole-codebase")
        )
        self.assertEqual(completed.returncode, 0)
        text = completed.stdout.decode("utf-8")
        self.assertTrue(text.endswith("\n"))
        self.assertEqual(text.count("\n"), 1)
        self.assertEqual(list(json.loads(text)), OUTPUT_KEYS)
        self.assertEqual(completed.stderr, b"")

    def test_nested_objects_have_exactly_their_keys(self):
        workspace = Workspace(self)
        workspace.write("a.txt", "text")
        result = workspace.measure(
            workspace.document(["a.txt"], mode="whole-codebase")
        )
        self.assertEqual(list(result["files"][0]), ["path", "chars"])
        self.assertEqual(list(result["shards"][0]), ["index", "paths", "chars"])

    def test_every_path_is_project_relative(self):
        workspace = Workspace(self)
        workspace.write("deep/er/file.txt", "text")
        workspace.write("top.txt", "text")
        completed = workspace.run(
            workspace.document(["top.txt", "deep/er/file.txt"], mode="whole-codebase")
        )
        self.assertEqual(completed.returncode, 0)
        self.assertNotIn(str(workspace.root).encode(), completed.stdout)
        result = json.loads(completed.stdout.decode("utf-8"))
        paths = [entry["path"] for entry in result["files"]]
        paths += [path for shard in result["shards"] for path in shard["paths"]]
        for path in paths:
            self.assertFalse(Path(path).is_absolute(), path)
            self.assertNotIn("..", path.split("/"))
            self.assertTrue((workspace.root / path).is_file(), path)

    def test_non_ascii_paths_are_written_unescaped(self):
        workspace = Workspace(self)
        workspace.write("日本/ファイル.txt", "text")
        completed = workspace.run(
            workspace.document(["日本/ファイル.txt"], mode="whole-codebase")
        )
        self.assertIn("日本/ファイル.txt".encode("utf-8"), completed.stdout)

    def test_a_sentinel_in_the_changed_content_never_reaches_a_stream(self):
        workspace = Workspace(self).init_repo()
        workspace.write("a.txt", "before\n")
        workspace.commit_all()
        workspace.write("a.txt", f"{SENTINEL} after\n")
        workspace.write("new.txt", f"{SENTINEL} untracked\n")
        completed = workspace.run(workspace.document(["a.txt", "new.txt"]))
        self.assertEqual(completed.returncode, 0)
        self.assertNotIn(SENTINEL.encode(), completed.stdout)
        self.assertNotIn(SENTINEL.encode(), completed.stderr)

    def test_a_sentinel_in_whole_codebase_content_never_reaches_a_stream(self):
        workspace = Workspace(self)
        workspace.write("a.txt", f"{SENTINEL}\n")
        completed = workspace.run(
            workspace.document(["a.txt"], mode="whole-codebase")
        )
        self.assertEqual(completed.returncode, 0)
        self.assertNotIn(SENTINEL.encode(), completed.stdout)
        self.assertNotIn(SENTINEL.encode(), completed.stderr)

    def test_a_sentinel_never_reaches_stderr_when_git_fails(self):
        workspace = Workspace(self).init_repo()
        workspace.write("a.txt", f"{SENTINEL}\n")
        workspace.commit_all()
        workspace.write("a.txt", f"{SENTINEL} changed\n")
        completed = workspace.run(workspace.document(["a.txt"], base="2" * 40))
        assert_failed_cleanly(self, completed)
        self.assertNotIn(SENTINEL.encode(), completed.stderr)


# ------------------------------------------------------------------ AC-6 ----


class TestInvalidInput(unittest.TestCase):
    """AC-6 (TM-1, TM-2): each invalid input exits 2 with a stderr message and
    nothing on stdout."""

    def assert_rejected(self, workspace, document=None, raw=None, extra=None):
        completed = workspace.run(document, extra_environment=extra, raw=raw)
        assert_failed_cleanly(self, completed)

    def valid_workspace(self):
        workspace = Workspace(self).init_repo()
        workspace.write("a.txt", "text\n")
        workspace.commit_all()
        return workspace

    def test_the_document_shape_is_enforced(self):
        workspace = self.valid_workspace()
        good = workspace.document(["a.txt"])
        missing = dict(good)
        del missing["perspective_count"]
        extra = dict(good, unexpected=1)
        cases = {
            "array": json.dumps([good]),
            "string": json.dumps("text"),
            "null": "null",
            "empty": "",
            "not json": "{not json",
            "missing key": json.dumps(missing),
            "extra key": json.dumps(extra),
            "duplicate key": json.dumps(good).replace(
                '"review_mode"', '"perspective_count": 1, "review_mode"', 1
            ),
            "nan constant": json.dumps(good).replace('"perspective_count": 1', '"perspective_count": NaN'),
            "invalid utf-8": b'{"project_root": "\xff"}',
        }
        for label, raw in cases.items():
            with self.subTest(label):
                self.assert_rejected(workspace, raw=raw)

    def test_the_argument_count_is_enforced(self):
        workspace = Workspace(self)
        for arguments in ([], ["a", "b"]):
            with self.subTest(arguments):
                completed = workspace.run_arguments(arguments)
                assert_failed_cleanly(self, completed)

    def test_an_unreadable_document_is_rejected(self):
        workspace = Workspace(self)
        for target in (workspace.base / "missing.json", workspace.base):
            with self.subTest(target=target.name):
                completed = workspace.run_arguments([str(target)])
                assert_failed_cleanly(self, completed)

    def test_project_root_must_be_an_absolute_existing_directory(self):
        workspace = self.valid_workspace()
        file_path = workspace.write("plain.txt", "x")
        for label, root in {
            "relative": "project",
            "dot": ".",
            "empty": "",
            "missing": str(workspace.base / "no-such-dir"),
            "a file": str(file_path),
            "number": 7,
            "null": None,
            "nul": str(workspace.root) + "\x00",
        }.items():
            with self.subTest(label):
                self.assert_rejected(
                    workspace, workspace.document(["a.txt"], root=root)
                )

    def test_review_mode_must_be_a_known_mode(self):
        workspace = self.valid_workspace()
        for mode in ("Diff", "whole_codebase", "", None, 1):
            with self.subTest(mode=mode):
                document = workspace.document(["a.txt"])
                document["review_mode"] = mode
                self.assert_rejected(workspace, document)

    def test_diff_base_rules_per_mode(self):
        workspace = self.valid_workspace()
        for base in (None, "main", "head", "A" * 40, "a" * 39, "a" * 41, " " + "a" * 39, 5):
            with self.subTest(mode="diff", base=base):
                document = workspace.document(["a.txt"])
                document["diff_base"] = base
                self.assert_rejected(workspace, document)
        for base in ("HEAD", "a" * 40, "", 0):
            with self.subTest(mode="whole-codebase", base=base):
                document = workspace.document(["a.txt"], mode="whole-codebase")
                document["diff_base"] = base
                self.assert_rejected(workspace, document)

    def test_changed_files_must_be_a_list_of_unique_strings(self):
        workspace = self.valid_workspace()
        workspace.write("b.txt", "b")
        for label, files in {
            "string": "a.txt",
            "object": {"a.txt": 1},
            "null": None,
            "number entry": ["a.txt", 3],
            "null entry": [None],
            "duplicate": ["a.txt", "b.txt", "a.txt"],
        }.items():
            for mode in ("diff", "whole-codebase"):
                with self.subTest(label, mode=mode):
                    document = workspace.document(["a.txt"], mode=mode)
                    document["changed_files"] = files
                    self.assert_rejected(workspace, document)

    def test_unsafe_path_strings_are_rejected(self):
        workspace = self.valid_workspace()
        workspace.write("-dash.txt", "x")
        workspace.write("sub/inner.txt", "x")
        unsafe = {
            "absolute": "/etc/hostname",
            "absolute inside": str(workspace.root / "a.txt"),
            "dotdot first": "../a.txt",
            "dotdot middle": "sub/../a.txt",
            "dotdot only": "..",
            "nul": "a.txt\x00",
            "carriage return": "a.txt\r",
            "line feed": "a\n.txt",
            "leading dash": "-dash.txt",
            "leading dash option": "--output=x",
            "empty": "",
            "dot segment": "./a.txt",
            "empty segment": "sub//inner.txt",
            "trailing slash": "sub/",
            "lone surrogate": "a\ud800.txt",
        }
        for label, path in unsafe.items():
            for mode in ("diff", "whole-codebase"):
                with self.subTest(label, mode=mode):
                    self.assert_rejected(
                        workspace, workspace.document([path], mode=mode)
                    )

    def test_a_path_that_is_not_a_regular_file_is_rejected(self):
        workspace = self.valid_workspace()
        (workspace.root / "directory").mkdir()
        for label, name in {"missing": "absent.txt", "directory": "directory"}.items():
            for mode in ("diff", "whole-codebase"):
                with self.subTest(label, mode=mode):
                    self.assert_rejected(
                        workspace, workspace.document([name], mode=mode)
                    )

    def test_a_symlink_is_refused(self):
        workspace = self.valid_workspace()
        secret = workspace.outside / "secret.txt"
        secret.write_text("outside\n", encoding="utf-8")
        os.symlink("a.txt", workspace.root / "link-inside.txt")
        os.symlink(secret, workspace.root / "link-outside.txt")
        os.symlink(workspace.outside, workspace.root / "link-dir")
        os.symlink("no-target", workspace.root / "link-dangling.txt")
        for name in (
            "link-inside.txt",
            "link-outside.txt",
            "link-dangling.txt",
            "link-dir/secret.txt",
        ):
            for mode in ("diff", "whole-codebase"):
                with self.subTest(name, mode=mode):
                    self.assert_rejected(
                        workspace, workspace.document([name], mode=mode)
                    )

    def test_a_fifo_is_refused_without_being_opened(self):
        workspace = self.valid_workspace()
        fifo = workspace.root / "pipe.txt"
        os.mkfifo(fifo)
        self.assertTrue(stat.S_ISFIFO(os.lstat(fifo).st_mode))
        for mode in ("diff", "whole-codebase"):
            with self.subTest(mode=mode):
                try:
                    self.assert_rejected(
                        workspace, workspace.document(["pipe.txt"], mode=mode)
                    )
                except subprocess.TimeoutExpired:
                    self.fail("the script blocked: it opened the FIFO")

    def test_perspective_count_must_be_an_integer_from_one_to_twenty_four(self):
        workspace = self.valid_workspace()
        for count in (0, -1, 25, 100, "3", 2.5, 3.0, True, False, None, [1]):
            with self.subTest(count=count):
                document = workspace.document(["a.txt"])
                document["perspective_count"] = count
                self.assert_rejected(workspace, document)

    def test_the_boundary_counts_are_accepted(self):
        workspace = self.valid_workspace()
        for count in (1, 24):
            with self.subTest(count=count):
                result = workspace.measure(workspace.document(["a.txt"], count=count))
                self.assertEqual(result["shard_cap"], 24 // count)


class TestRefusalBeforeAnyRead(unittest.TestCase):
    """AC-6 (TM-2): every path is checked before any read or `git` run."""

    def test_an_invalid_later_path_stops_the_run_before_git(self):
        workspace = Workspace(self).init_repo()
        workspace.write("a.txt", "text\n")
        workspace.commit_all()
        os.symlink("a.txt", workspace.root / "z-link.txt")
        shim_environment, marker = workspace.install_git_shim()
        completed = workspace.run(
            workspace.document(["a.txt", "z-link.txt"]), shim_environment
        )
        assert_failed_cleanly(self, completed)
        self.assertFalse(marker.exists(), "git ran before every path was checked")

    def test_a_fifo_after_valid_files_in_whole_codebase_mode_does_not_block(self):
        workspace = Workspace(self)
        workspace.write("a.txt", "text\n")
        os.mkfifo(workspace.root / "z-pipe.txt")
        try:
            completed = workspace.run(
                workspace.document(["a.txt", "z-pipe.txt"], mode="whole-codebase")
            )
        except subprocess.TimeoutExpired:
            self.fail("the script blocked: it opened the FIFO")
        assert_failed_cleanly(self, completed)


class TestLiteralPathspecs(unittest.TestCase):
    """AC-6 (TM-1): a name with pathspec magic is measured as that literal
    file only."""

    MAGIC_NAMES = ("*.txt", "[ab].txt", ":(top)a.txt", ":(exclude)a.txt", "?.txt")

    def test_each_magic_name_is_measured_as_the_literal_file(self):
        for magic in self.MAGIC_NAMES:
            with self.subTest(name=magic):
                workspace = Workspace(self).init_repo()
                workspace.write("a.txt", "a old\n")
                workspace.write("b.txt", "b old\n")
                workspace.write(magic, "magic old\n")
                workspace.git("--literal-pathspecs", "add", "-A")
                workspace.git("commit", "-q", "-m", "base")
                old_blob = workspace.git(
                    "--literal-pathspecs", "rev-parse", f"HEAD:{magic}"
                ).strip()
                workspace.write("a.txt", "a" * 5000 + "\n")
                workspace.write("b.txt", "b" * 5000 + "\n")
                workspace.write(magic, "magic new\n")
                expected = modified_diff_text(
                    magic,
                    old_blob,
                    workspace.git("hash-object", "--", magic).strip(),
                    "magic old",
                    "magic new",
                )
                result = workspace.measure(workspace.document([magic]))
                self.assertEqual(
                    result["files"], [{"path": magic, "chars": len(expected)}]
                )
                self.assertLess(len(expected), 300)

    def test_an_untracked_magic_name_counts_its_own_content_only(self):
        workspace = Workspace(self).init_repo()
        workspace.write("a.txt", "a" * 5000)
        workspace.commit_all()
        workspace.write("*.txt", "tiny")
        workspace.write("a.txt", "a" * 5001)
        result = workspace.measure(workspace.document(["*.txt"]))
        self.assertEqual(result["files"], [{"path": "*.txt", "chars": 4}])


class TestConfiguredDrivers(unittest.TestCase):
    """AC-6 (TM-1): no driver named by the repository's configuration is
    run while measuring."""

    def make_script(self, workspace, marker):
        script = workspace.base / "driver.sh"
        script.write_text(
            f'#!/bin/sh\ntouch "{marker}"\ncat "$1" 2>/dev/null\nexit 0\n',
            encoding="utf-8",
        )
        script.chmod(0o755)
        return script

    def prepare(self, workspace):
        workspace.write("conv.txt", "before\n")
        workspace.write(".gitattributes", "conv.txt diff=marker\n")
        workspace.commit_all()
        workspace.write("conv.txt", "after\n")

    def test_a_text_conversion_driver_is_never_run(self):
        workspace = Workspace(self).init_repo()
        marker = workspace.base / "textconv-ran"
        script = self.make_script(workspace, marker)
        self.prepare(workspace)
        workspace.git("config", "diff.marker.textconv", str(script))
        # Positive control: a plain diff does run the configured driver.
        workspace.git("diff", "HEAD", "--", "conv.txt")
        self.assertTrue(marker.exists(), "the control diff did not run the driver")
        marker.unlink()
        result = workspace.measure(workspace.document(["conv.txt"]))
        self.assertFalse(marker.exists(), "the text-conversion driver was run")
        self.assertGreater(result["files"][0]["chars"], len("after\n"))

    def test_an_external_diff_program_is_never_run(self):
        workspace = Workspace(self).init_repo()
        marker = workspace.base / "external-ran"
        script = self.make_script(workspace, marker)
        self.prepare(workspace)
        workspace.git("config", "diff.external", str(script))
        workspace.git("diff", "HEAD", "--", "conv.txt")
        self.assertTrue(marker.exists(), "the control diff did not run the program")
        marker.unlink()
        workspace.measure(workspace.document(["conv.txt"]))
        self.assertFalse(marker.exists(), "the external diff program was run")

    def test_an_external_diff_variable_is_never_run(self):
        workspace = Workspace(self).init_repo()
        marker = workspace.base / "variable-ran"
        script = self.make_script(workspace, marker)
        self.prepare(workspace)
        workspace.git(
            "diff", "HEAD", "--", "conv.txt",
            extra_environment={"GIT_EXTERNAL_DIFF": str(script)},
        )
        self.assertTrue(marker.exists(), "the control diff did not run the program")
        marker.unlink()
        workspace.measure(
            workspace.document(["conv.txt"]),
            {"GIT_EXTERNAL_DIFF": str(script)},
        )
        self.assertFalse(marker.exists(), "GIT_EXTERNAL_DIFF was honored")

    def test_a_filesystem_monitor_hook_is_never_run(self):
        workspace = Workspace(self).init_repo()
        marker = workspace.base / "fsmonitor-ran"
        hook = workspace.base / "fsmonitor.sh"
        hook.write_text(f'#!/bin/sh\ntouch "{marker}"\nprintf "\\0"\n', encoding="utf-8")
        hook.chmod(0o755)
        self.prepare(workspace)
        workspace.git("config", "core.fsmonitor", str(hook))
        workspace.git("diff", "HEAD", "--", "conv.txt")
        if not marker.exists():
            self.skipTest("this git does not run the configured fsmonitor hook")
        marker.unlink()
        workspace.measure(workspace.document(["conv.txt"]))
        self.assertFalse(marker.exists(), "the filesystem monitor hook was run")

    def test_repository_steering_variables_are_ignored(self):
        workspace = Workspace(self).init_repo()
        self.prepare(workspace)
        bait = workspace.base / "bait"
        bait.mkdir()
        expected = workspace.measure(workspace.document(["conv.txt"]))
        steered = workspace.measure(
            workspace.document(["conv.txt"]),
            {"GIT_DIR": str(bait), "GIT_WORK_TREE": str(bait), "GIT_INDEX_FILE": str(bait / "x")},
        )
        self.assertEqual(steered, expected)


# ------------------------------------------------------------------ AC-7 ----


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


def non_stdlib_modules(source):
    return {m for m in imported_modules(source) if m not in sys.stdlib_module_names}


class TestStandardLibraryOnly(unittest.TestCase):
    """AC-7 (FR18, NFR6)."""

    def test_the_script_imports_only_standard_library_modules(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertGreater(len(imported_modules(source)), 0)
        self.assertEqual(non_stdlib_modules(source), set())

    def test_this_module_imports_only_standard_library_modules(self):
        source = THIS_MODULE.read_text(encoding="utf-8")
        self.assertGreater(len(imported_modules(source)), 0)
        self.assertEqual(non_stdlib_modules(source), set())

    def test_the_check_rejects_forged_sources(self):
        self.assertEqual(non_stdlib_modules("import os\nimport yaml\n"), {"yaml"})
        self.assertEqual(
            non_stdlib_modules("from requests.adapters import HTTPAdapter\n"),
            {"requests"},
        )
        self.assertEqual(
            non_stdlib_modules("def f():\n    import numpy as np\n"), {"numpy"}
        )
        self.assertEqual(non_stdlib_modules("from . import helper\n"), {"."})
        self.assertEqual(non_stdlib_modules("import json\nimport os.path\n"), set())

    def test_the_test_module_uses_unittest_and_temporary_directories(self):
        source = THIS_MODULE.read_text(encoding="utf-8")
        self.assertIn("unittest", imported_modules(source))
        self.assertIn("tempfile", imported_modules(source))
        for forbidden in ("pytest", "nose", "hypothesis"):
            self.assertNotIn(forbidden, imported_modules(source))


if __name__ == "__main__":
    unittest.main()
