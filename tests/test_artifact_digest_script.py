"""Tests for task0001 (feature-docs/worker-digest-ownership): the artifact
digest script `em-workflow/scripts/artifact-digest.py`.

Every behavioural test runs the script with the test interpreter as a child
process inside a temporary directory and checks its stdout bytes, stderr and
exit code against the CLI contract in IMPLEMENTATION.md ("Digest script CLI
contract"). Each call carries a timeout, so a hang (for example on a FIFO)
becomes a failure instead of a stuck suite.

Covers task0001 Acceptance Criteria
(feature-docs/worker-digest-ownership/tasks/task0001.md):

- AC-1 (FR7, TS6): the digest of an empty file and of the three bytes `abc`
  equals the published FIPS 180 sha256 test-vector value, rendered
  `sha256:` + 64 lowercase hexadecimal digits, exit 0. The vectors are
  hard-coded below; they are not recomputed with the algorithm the script
  uses.
- AC-2 (FR7, TS6): one element per argument, in argument order, duplicates
  kept, `path` equal to the argument verbatim.
- AC-3 (FR7, TS6): `-x.md`, `--`, `-` and `--help` are file names, never
  options.
- AC-4 (FR7, TS6): paths with spaces and Japanese characters are echoed as
  unescaped UTF-8 whatever the child's locale.
- AC-5 (FR7, TS7): a path with no entry is `error: missing`, the other
  arguments are still hashed, exit 1.
- AC-6 (FR7, TS7, TM-6): directory / symlink / dangling symlink / FIFO are
  `not_a_regular_file` and never block; a regular file that cannot be read
  is `unreadable`.
- AC-7 (FR7, NFR3, TS10): no argument exits 2 with usage on stderr and empty
  stdout; the script imports only standard-library modules and no
  process-spawning facility.

The import / facility checks below read the script source with `ast` and
are paired with a negative proof (a forged source that must trip the same
check) so a check that matches nothing cannot pass silently.
"""

import ast
import json
import os
import re
import socket
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "em-workflow" / "scripts" / "artifact-digest.py"

# Upper bound for one child process. Interpreter start-up is far below this;
# only a hang can reach it.
CALL_TIMEOUT_SECONDS = 20

# Published FIPS 180 sha256 test vectors (hard-coded on purpose, see header).
EMPTY_DIGEST = (
    "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
)
ABC_DIGEST = (
    "sha256:ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
)
TWO_BLOCK_INPUT = b"abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq"
TWO_BLOCK_DIGEST = (
    "sha256:248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1"
)
MILLION_A_DIGEST = (
    "sha256:cdc76e5c9914fb9281a1c7e284d73e67f1809a48a497200e046d39ccc7112cd0"
)

DIGEST_FORMAT = re.compile(r"\Asha256:[0-9a-f]{64}\Z")

IS_ROOT = hasattr(os, "geteuid") and os.geteuid() == 0

# Environment variables that decide how the child interpreter decodes its
# arguments and encodes its standard streams.
LOCALE_VARIABLES = (
    "LANG",
    "LANGUAGE",
    "LC_ALL",
    "LC_CTYPE",
    "PYTHONUTF8",
    "PYTHONIOENCODING",
    "PYTHONCOERCECLOCALE",
)


def clean_env(**overrides):
    """The current environment without every locale / encoding variable,
    plus `overrides`."""
    env = {k: v for k, v in os.environ.items() if k not in LOCALE_VARIABLES}
    env.update(overrides)
    return env


def run_python(argv, cwd=None, env=None):
    """Run `sys.executable *argv`, turning a timeout into a failure."""
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


def run_digest(*paths, cwd=None, env=None):
    return run_python([str(SCRIPT), *paths], cwd=cwd, env=env)


def decode_array(proc):
    """Decode stdout as the single JSON array the contract promises."""
    text = proc.stdout.decode("utf-8")
    value = json.loads(text)
    if not isinstance(value, list):
        raise AssertionError(f"stdout is not a JSON array: {text!r}")
    return value


def ok(path, digest):
    return {"path": path, "sha256": digest}


def failed(path, error):
    return {"path": path, "sha256": None, "error": error}


class DigestCase(unittest.TestCase):
    """Base class: a temporary directory per test and diagnostics that show
    the child's streams when an assertion on its result fails."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)

    def write(self, name, data=b""):
        path = self.tmp / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def digest(self, *paths, cwd=None, env=None):
        return run_digest(*paths, cwd=cwd if cwd is not None else self.tmp,
                          env=env)

    def assert_array(self, proc, expected, exit_code):
        detail = (
            f"stdout={proc.stdout!r} stderr={proc.stderr!r} "
            f"exit={proc.returncode}"
        )
        self.assertEqual(proc.returncode, exit_code, detail)
        self.assertTrue(proc.stdout.endswith(b"\n"), detail)
        self.assertEqual(decode_array(proc), expected, detail)


# ---------------------------------------------------------------- AC-1 ----


class TestDigestValues(DigestCase):
    """AC-1: the digest value, its rendering, and raw-byte hashing."""

    def test_ac1_empty_file_has_the_published_empty_vector(self):
        self.write("empty.md", b"")
        proc = self.digest("empty.md")
        self.assert_array(proc, [ok("empty.md", EMPTY_DIGEST)], 0)

    def test_ac1_abc_file_has_the_published_abc_vector(self):
        self.write("abc.md", b"abc")
        proc = self.digest("abc.md")
        self.assert_array(proc, [ok("abc.md", ABC_DIGEST)], 0)

    def test_ac1_digest_is_sha256_prefix_plus_64_lowercase_hex(self):
        self.write("abc.md", b"abc")
        element = decode_array(self.digest("abc.md"))[0]
        self.assertRegex(element["sha256"], DIGEST_FORMAT)

    def test_ac1_two_block_message_matches_the_published_vector(self):
        self.write("two-block.md", TWO_BLOCK_INPUT)
        proc = self.digest("two-block.md")
        self.assert_array(proc, [ok("two-block.md", TWO_BLOCK_DIGEST)], 0)

    def test_ac1_file_spanning_many_read_chunks_matches_the_vector(self):
        # One million bytes is far larger than any sensible read chunk, so
        # the chunked read loop is exercised across many iterations.
        self.write("million-a.bin", b"a" * 1_000_000)
        proc = self.digest("million-a.bin")
        self.assert_array(proc, [ok("million-a.bin", MILLION_A_DIGEST)], 0)

    def test_ac1_bytes_are_hashed_raw_without_newline_translation(self):
        # CRLF, a lone CR and NUL must reach the hash untouched. The
        # reference digest comes from hashlib here: the test checks that
        # the script performs no text-mode translation, not the algorithm.
        import hashlib

        data = b"line1\r\nline2\rline3\x00\xff\xfe\n"
        self.write("raw.bin", data)
        expected = "sha256:" + hashlib.sha256(data).hexdigest()
        proc = self.digest("raw.bin")
        self.assert_array(proc, [ok("raw.bin", expected)], 0)

    def test_ac1_stderr_is_empty_on_success(self):
        self.write("abc.md", b"abc")
        self.assertEqual(self.digest("abc.md").stderr, b"")


# ---------------------------------------------------------------- AC-2 ----


class TestMultiplePaths(DigestCase):
    """AC-2: one element per argument, order and duplicates preserved."""

    def test_ac2_one_element_per_argument_in_argument_order(self):
        self.write("a.md", b"")
        self.write("b.md", b"abc")
        self.write("c.md", TWO_BLOCK_INPUT)
        proc = self.digest("c.md", "a.md", "b.md")
        self.assert_array(
            proc,
            [
                ok("c.md", TWO_BLOCK_DIGEST),
                ok("a.md", EMPTY_DIGEST),
                ok("b.md", ABC_DIGEST),
            ],
            0,
        )

    def test_ac2_same_path_twice_yields_two_elements(self):
        self.write("a.md", b"abc")
        proc = self.digest("a.md", "a.md")
        self.assert_array(
            proc, [ok("a.md", ABC_DIGEST), ok("a.md", ABC_DIGEST)], 0
        )

    def test_ac2_duplicates_are_kept_between_other_arguments(self):
        self.write("a.md", b"")
        self.write("b.md", b"abc")
        proc = self.digest("a.md", "b.md", "a.md")
        self.assert_array(
            proc,
            [
                ok("a.md", EMPTY_DIGEST),
                ok("b.md", ABC_DIGEST),
                ok("a.md", EMPTY_DIGEST),
            ],
            0,
        )

    def test_ac2_path_is_the_argument_verbatim_not_normalised(self):
        self.write("sub/a.md", b"abc")
        args = ["sub/a.md", "./sub/a.md", "sub//a.md", "sub/../sub/a.md"]
        proc = self.digest(*args)
        self.assert_array(proc, [ok(a, ABC_DIGEST) for a in args], 0)

    def test_ac2_absolute_and_relative_forms_of_one_file_both_echo(self):
        absolute = str(self.write("a.md", b"abc"))
        proc = self.digest("a.md", absolute)
        self.assert_array(
            proc, [ok("a.md", ABC_DIGEST), ok(absolute, ABC_DIGEST)], 0
        )

    def test_ac2_each_element_digest_belongs_to_its_own_file(self):
        names = ["one.md", "two.md", "three.md"]
        contents = [b"", b"abc", TWO_BLOCK_INPUT]
        digests = [EMPTY_DIGEST, ABC_DIGEST, TWO_BLOCK_DIGEST]
        for name, data in zip(names, contents):
            self.write(name, data)
        proc = self.digest(*names)
        self.assert_array(
            proc, [ok(n, d) for n, d in zip(names, digests)], 0
        )


# ---------------------------------------------------------------- AC-3 ----


class TestHyphenPaths(DigestCase):
    """AC-3: arguments beginning with a hyphen are file names."""

    HYPHEN_NAMES = ("-x.md", "--", "-", "--help")

    def setUp(self):
        super().setUp()
        # Distinct content per name so a digest is tied to its own file.
        self.contents = {
            "-x.md": (b"", EMPTY_DIGEST),
            "--": (b"abc", ABC_DIGEST),
            "-": (TWO_BLOCK_INPUT, TWO_BLOCK_DIGEST),
            "--help": (b"a" * 1_000_000, MILLION_A_DIGEST),
        }
        for name, (data, _) in self.contents.items():
            self.write(name, data)

    def test_ac3_each_hyphen_name_alone_is_hashed_as_a_file(self):
        for name in self.HYPHEN_NAMES:
            with self.subTest(name=name):
                proc = self.digest(name)
                self.assert_array(
                    proc, [ok(name, self.contents[name][1])], 0
                )

    def test_ac3_all_hyphen_names_together_are_hashed_in_order(self):
        proc = self.digest(*self.HYPHEN_NAMES)
        self.assert_array(
            proc,
            [ok(n, self.contents[n][1]) for n in self.HYPHEN_NAMES],
            0,
        )

    def test_ac3_no_help_or_usage_text_is_produced(self):
        for name in self.HYPHEN_NAMES:
            with self.subTest(name=name):
                proc = self.digest(name)
                self.assertEqual(proc.stderr, b"")
                self.assertNotIn(b"usage", proc.stdout.lower())

    def test_ac3_absent_option_like_names_are_missing_not_options(self):
        # None of these exists; each must be reported as a missing path
        # (exit 1, a JSON array), never interpreted as an option.
        names = ["-h", "-V", "--version", "-o", "--output=x"]
        proc = self.digest(*names)
        self.assert_array(proc, [failed(n, "missing") for n in names], 1)
        self.assertEqual(proc.stderr, b"")


# ---------------------------------------------------------------- AC-4 ----


class TestNonAsciiPaths(DigestCase):
    """AC-4: spaces and Japanese characters, also under a non-UTF-8 locale."""

    DIRECTORY = "仕様 ドキュメント"
    FILE = "日本語 の ファイル.md"
    JAPANESE_ONLY = "要件.md"
    SPACES_ONLY = "with some  spaces.md"

    def setUp(self):
        super().setUp()
        self.nested = f"{self.DIRECTORY}/{self.FILE}"
        self.write(self.nested, b"abc")
        self.write(self.JAPANESE_ONLY, b"")
        self.write(self.SPACES_ONLY, TWO_BLOCK_INPUT)
        self.args = [self.nested, self.JAPANESE_ONLY, self.SPACES_ONLY]
        self.expected = [
            ok(self.nested, ABC_DIGEST),
            ok(self.JAPANESE_ONLY, EMPTY_DIGEST),
            ok(self.SPACES_ONLY, TWO_BLOCK_DIGEST),
        ]

    def assert_unescaped_utf8(self, proc):
        detail = f"stdout={proc.stdout!r} stderr={proc.stderr!r}"
        for text in (self.DIRECTORY, self.FILE, self.JAPANESE_ONLY):
            self.assertIn(text.encode("utf-8"), proc.stdout, detail)
        self.assertNotIn(b"\\u", proc.stdout, detail)

    def test_ac4_decoded_paths_equal_the_arguments(self):
        proc = self.digest(*self.args, env=clean_env(LC_ALL="C.UTF-8"))
        self.assert_array(proc, self.expected, 0)

    def test_ac4_raw_stdout_holds_the_characters_as_unescaped_utf8(self):
        proc = self.digest(*self.args, env=clean_env(LC_ALL="C.UTF-8"))
        self.assert_unescaped_utf8(proc)

    def test_ac4_c_locale_yields_the_same_output(self):
        proc = self.digest(*self.args, env=clean_env(LC_ALL="C"))
        self.assert_array(proc, self.expected, 0)
        self.assert_unescaped_utf8(proc)

    def test_ac4_ascii_only_interpreter_encodings_yield_the_same_output(self):
        # UTF-8 mode and locale coercion are both disabled and the standard
        # streams are forced to ASCII: the child's filesystem encoding and
        # text-stream encoding are then not UTF-8 at all.
        env = clean_env(
            LC_ALL="C",
            PYTHONUTF8="0",
            PYTHONCOERCECLOCALE="0",
            PYTHONIOENCODING="ascii",
        )
        proc = self.digest(*self.args, env=env)
        self.assert_array(proc, self.expected, 0)
        self.assert_unescaped_utf8(proc)

    def test_ac4_absolute_path_with_japanese_and_spaces_is_echoed(self):
        absolute = str(self.tmp / self.nested)
        proc = self.digest(absolute, env=clean_env(LC_ALL="C"))
        self.assert_array(proc, [ok(absolute, ABC_DIGEST)], 0)

    def test_ac4_japanese_name_that_is_missing_is_echoed_unescaped(self):
        name = "存在しない 文書.md"
        proc = self.digest(name, env=clean_env(LC_ALL="C"))
        self.assert_array(proc, [failed(name, "missing")], 1)
        self.assertIn(name.encode("utf-8"), proc.stdout)


# ---------------------------------------------------------------- AC-5 ----


class TestMissingEntries(DigestCase):
    """AC-5: a path with no entry is `missing`; the rest is still hashed."""

    def test_ac5_missing_path_yields_null_digest_and_missing_error(self):
        proc = self.digest("nope.md")
        self.assert_array(proc, [failed("nope.md", "missing")], 1)

    def test_ac5_other_arguments_still_carry_their_digests(self):
        self.write("a.md", b"abc")
        self.write("c.md", b"")
        proc = self.digest("a.md", "nope.md", "c.md")
        self.assert_array(
            proc,
            [
                ok("a.md", ABC_DIGEST),
                failed("nope.md", "missing"),
                ok("c.md", EMPTY_DIGEST),
            ],
            1,
        )

    def test_ac5_missing_first_and_last_keep_positions(self):
        self.write("b.md", b"abc")
        proc = self.digest("first-missing.md", "b.md", "last-missing.md")
        self.assert_array(
            proc,
            [
                failed("first-missing.md", "missing"),
                ok("b.md", ABC_DIGEST),
                failed("last-missing.md", "missing"),
            ],
            1,
        )

    def test_ac5_empty_argument_is_reported_missing(self):
        proc = self.digest("")
        self.assert_array(proc, [failed("", "missing")], 1)

    def test_ac5_missing_directory_component_is_missing(self):
        proc = self.digest("no-such-dir/a.md")
        self.assert_array(proc, [failed("no-such-dir/a.md", "missing")], 1)

    def test_ac5_path_below_a_regular_file_is_missing(self):
        self.write("plain.md", b"abc")
        proc = self.digest("plain.md/child.md")
        self.assert_array(proc, [failed("plain.md/child.md", "missing")], 1)

    def test_ac5_failure_element_has_exactly_path_sha256_error(self):
        element = decode_array(self.digest("nope.md"))[0]
        self.assertEqual(set(element), {"path", "sha256", "error"})
        self.assertIsNone(element["sha256"])

    def test_ac5_success_element_has_exactly_path_and_sha256(self):
        self.write("a.md", b"abc")
        element = decode_array(self.digest("a.md"))[0]
        self.assertEqual(set(element), {"path", "sha256"})

    def test_ac5_exit_is_zero_when_every_path_has_a_digest(self):
        self.write("a.md", b"abc")
        self.assertEqual(self.digest("a.md").returncode, 0)


# ---------------------------------------------------------------- AC-6 ----


class TestNonRegularEntries(DigestCase):
    """AC-6 / TM-6: only regular files are read; nothing blocks."""

    def assert_not_regular(self, name):
        proc = self.digest(name)
        self.assert_array(proc, [failed(name, "not_a_regular_file")], 1)

    def test_ac6_directory_is_not_a_regular_file(self):
        (self.tmp / "a-directory").mkdir()
        self.assert_not_regular("a-directory")

    def test_ac6_symlink_to_a_regular_file_is_not_followed(self):
        self.write("target.md", b"abc")
        os.symlink("target.md", self.tmp / "link.md")
        self.assert_not_regular("link.md")

    def test_ac6_symlink_result_never_carries_the_target_digest(self):
        self.write("target.md", b"abc")
        os.symlink("target.md", self.tmp / "link.md")
        proc = self.digest("link.md")
        element = decode_array(proc)[0]
        self.assertIsNone(element["sha256"], proc.stdout)
        self.assertNotIn(ABC_DIGEST.encode("ascii"), proc.stdout)

    def test_ac6_dangling_symlink_is_not_a_regular_file(self):
        os.symlink("does-not-exist.md", self.tmp / "dangling.md")
        self.assert_not_regular("dangling.md")

    def test_ac6_symlink_to_a_directory_is_not_a_regular_file(self):
        (self.tmp / "a-directory").mkdir()
        os.symlink("a-directory", self.tmp / "dir-link")
        self.assert_not_regular("dir-link")

    def test_ac6_symlink_loop_is_not_a_regular_file(self):
        os.symlink("loop-b", self.tmp / "loop-a")
        os.symlink("loop-a", self.tmp / "loop-b")
        self.assert_not_regular("loop-a")

    @unittest.skipUnless(hasattr(os, "mkfifo"), "os.mkfifo is unavailable")
    def test_ac6_fifo_is_not_a_regular_file_and_does_not_block(self):
        os.mkfifo(self.tmp / "a-fifo")
        self.assert_not_regular("a-fifo")

    @unittest.skipUnless(hasattr(os, "mkfifo"), "os.mkfifo is unavailable")
    def test_ac6_symlink_to_a_fifo_does_not_block(self):
        os.mkfifo(self.tmp / "a-fifo")
        os.symlink("a-fifo", self.tmp / "fifo-link")
        self.assert_not_regular("fifo-link")

    @unittest.skipUnless(
        hasattr(socket, "AF_UNIX"), "AF_UNIX sockets are unavailable"
    )
    def test_ac6_socket_is_not_a_regular_file(self):
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.addCleanup(sock.close)
        # Bind through a relative name from inside the temp directory: a
        # socket path is limited to about 100 bytes.
        old_cwd = os.getcwd()
        os.chdir(self.tmp)
        try:
            sock.bind("a-socket")
        finally:
            os.chdir(old_cwd)
        self.assert_not_regular("a-socket")

    @unittest.skipUnless(
        os.path.exists("/dev/null")
        and stat.S_ISCHR(os.stat("/dev/null").st_mode),
        "/dev/null is not a character device here",
    )
    def test_ac6_character_device_is_not_a_regular_file(self):
        proc = self.digest("/dev/null")
        self.assert_array(
            proc, [failed("/dev/null", "not_a_regular_file")], 1
        )

    @unittest.skipUnless(hasattr(os, "mkfifo"), "os.mkfifo is unavailable")
    def test_ac6_non_regular_entry_does_not_stop_the_other_arguments(self):
        self.write("a.md", b"abc")
        (self.tmp / "a-directory").mkdir()
        os.mkfifo(self.tmp / "a-fifo")
        os.symlink("a.md", self.tmp / "link.md")
        proc = self.digest(
            "a.md", "a-directory", "a-fifo", "nope.md", "link.md", "a.md"
        )
        self.assert_array(
            proc,
            [
                ok("a.md", ABC_DIGEST),
                failed("a-directory", "not_a_regular_file"),
                failed("a-fifo", "not_a_regular_file"),
                failed("nope.md", "missing"),
                failed("link.md", "not_a_regular_file"),
                ok("a.md", ABC_DIGEST),
            ],
            1,
        )

    def test_ac6_unreadable_regular_file_is_reported_unreadable(self):
        if IS_ROOT:
            self.skipTest(
                "running as root: permission denial cannot be produced"
            )
        path = self.write("secret.md", b"abc")
        path.chmod(0o000)
        self.addCleanup(path.chmod, 0o600)
        if os.access(path, os.R_OK):
            self.skipTest(
                "this filesystem still permits reading a mode-000 file"
            )
        proc = self.digest("secret.md")
        self.assert_array(proc, [failed("secret.md", "unreadable")], 1)

    def test_ac6_unreadable_file_does_not_stop_the_other_arguments(self):
        if IS_ROOT:
            self.skipTest(
                "running as root: permission denial cannot be produced"
            )
        self.write("a.md", b"abc")
        path = self.write("secret.md", b"abc")
        path.chmod(0o000)
        self.addCleanup(path.chmod, 0o600)
        if os.access(path, os.R_OK):
            self.skipTest(
                "this filesystem still permits reading a mode-000 file"
            )
        proc = self.digest("secret.md", "a.md")
        self.assert_array(
            proc,
            [failed("secret.md", "unreadable"), ok("a.md", ABC_DIGEST)],
            1,
        )


# A driver that makes the script's inspection step lie: every path-based
# lstat / stat call reports the same regular file, whatever the path really
# is. That is exactly what the script would observe if the entry were
# swapped for a FIFO, a symlink or a directory after inspection and before
# reading, so the read step must not rely on the inspection result.
# File-descriptor based calls stay truthful.
SWAP_DRIVER = """\
import os
import runpy
import sys

script, template = sys.argv[1], sys.argv[2]
template_stat = os.lstat(template)
real_lstat, real_stat = os.lstat, os.stat


def lying_lstat(path, *args, **kwargs):
    if isinstance(path, int):
        return real_lstat(path, *args, **kwargs)
    return template_stat


def lying_stat(path, *args, **kwargs):
    if isinstance(path, int):
        return real_stat(path, *args, **kwargs)
    return template_stat


os.lstat = lying_lstat
os.stat = lying_stat
sys.argv = [script] + sys.argv[3:]
runpy.run_path(script, run_name="__main__")
"""


class TestEntrySwappedAfterInspection(DigestCase):
    """TM-6 (design flow step 2.3): the regular-file determination holds for
    the handle actually read."""

    def setUp(self):
        super().setUp()
        self.template = self.write("template.md", b"abc")
        self.driver = self.write("swap-driver.py", SWAP_DRIVER.encode())

    def run_swapped(self, *paths):
        return run_python(
            [str(self.driver), str(SCRIPT), str(self.template), *paths],
            cwd=self.tmp,
        )

    def test_ac6_driver_control_a_real_regular_file_is_still_hashed(self):
        self.write("real.md", b"abc")
        proc = self.run_swapped("real.md")
        self.assert_array(proc, [ok("real.md", ABC_DIGEST)], 0)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "os.mkfifo is unavailable")
    def test_ac6_fifo_swapped_in_after_inspection_does_not_block(self):
        os.mkfifo(self.tmp / "swapped-fifo")
        proc = self.run_swapped("swapped-fifo")
        self.assert_array(
            proc, [failed("swapped-fifo", "not_a_regular_file")], 1
        )

    def test_ac6_symlink_swapped_in_after_inspection_is_not_followed(self):
        self.write("target.md", b"abc")
        os.symlink("target.md", self.tmp / "swapped-link")
        proc = self.run_swapped("swapped-link")
        self.assert_array(
            proc, [failed("swapped-link", "not_a_regular_file")], 1
        )
        self.assertNotIn(ABC_DIGEST.encode("ascii"), proc.stdout)

    def test_ac6_directory_swapped_in_after_inspection_is_not_hashed(self):
        (self.tmp / "swapped-dir").mkdir()
        proc = self.run_swapped("swapped-dir")
        self.assert_array(
            proc, [failed("swapped-dir", "not_a_regular_file")], 1
        )

    def test_ac6_entry_removed_after_inspection_is_missing(self):
        proc = self.run_swapped("removed.md")
        self.assert_array(proc, [failed("removed.md", "missing")], 1)


# ---------------------------------------------------------------- AC-7 ----

# Modules that start a child process or hand control to another program.
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
        "popen2",
        "commands",
    }
)
# Attributes of `os` (or names imported from it) that spawn a process.
SPAWNING_OS_NAMES = frozenset(
    {"system", "popen", "startfile", "fork", "forkpty"}
)
SPAWNING_OS_PREFIXES = ("exec", "spawn", "posix_spawn")


def is_spawning_os_name(name):
    return name in SPAWNING_OS_NAMES or name.startswith(SPAWNING_OS_PREFIXES)


def imported_modules(source):
    """Top-level names of every module the source imports."""
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
    """Every process-spawning facility the source imports or uses."""
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
    return {
        m for m in imported_modules(source)
        if m not in sys.stdlib_module_names
    }


class TestUsageAndIsolation(DigestCase):
    """AC-7: no-argument usage, standard library only, no spawning."""

    def test_ac7_no_argument_exits_2_with_usage_on_stderr(self):
        proc = run_digest(cwd=self.tmp)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertIn(b"usage", proc.stderr.lower())

    def test_ac7_no_argument_leaves_stdout_empty(self):
        proc = run_digest(cwd=self.tmp)
        # Guard against a vacuous pass (a script that never ran also leaves
        # stdout empty): the call must have reached the usage path.
        self.assertIn(b"usage", proc.stderr.lower())
        self.assertEqual(proc.stdout, b"")

    def test_ac7_script_imports_only_standard_library_modules(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertEqual(non_stdlib_modules(source), set())

    def test_ac7_script_imports_no_process_spawning_facility(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertEqual(spawning_facilities(source), set())

    def test_ac7_script_import_set_is_not_empty(self):
        # Non-vacuity: the extraction read real imports.
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("hashlib", imported_modules(source))

    def test_ac7_non_stdlib_import_is_detected(self):
        forged = "import json\nimport yaml\nfrom requests import get\n"
        self.assertEqual(non_stdlib_modules(forged), {"yaml", "requests"})

    def test_ac7_spawning_imports_and_calls_are_detected(self):
        # The forged source is only parsed with `ast`, never executed: it is
        # the negative proof that the facility check really matches.
        forged = (
            "import subprocess\n"
            "import os\n"
            "from os import system\n"
            "from multiprocessing import Pool\n"
            "os.popen('x')\n"
            "os.execvp('x', ['x'])\n"
            "os.posix_spawn('x', ['x'], {})\n"
        )
        self.assertEqual(
            spawning_facilities(forged),
            {
                "subprocess",
                "multiprocessing",
                "os.system",
                "os.popen",
                "os.execvp",
                "os.posix_spawn",
            },
        )

    def test_ac7_harmless_os_usage_is_not_flagged(self):
        harmless = "import os\nos.read(0, 1)\nos.fstat(0)\nos.open('x', 0)\n"
        self.assertEqual(spawning_facilities(harmless), set())

    def test_ac7_non_utf8_argument_is_an_internal_failure_exit_2(self):
        # An argument that is not valid UTF-8 has no JSON representation:
        # exit 2, a message on stderr, no array on stdout.
        proc = run_python([str(SCRIPT), b"bad-\xff-name.md"], cwd=self.tmp)
        self.assertEqual(proc.returncode, 2, proc.stderr)
        self.assertEqual(proc.stdout, b"")
        # The message names the problem (this also rules out a script that
        # never ran, whose interpreter error carries no such wording).
        self.assertIn(b"UTF-8", proc.stderr)


# ------------------------------------------------- supporting properties ----


class TestScriptFileProperties(unittest.TestCase):
    """The script file's header: shebang and module docstring (design:
    'Other properties')."""

    @classmethod
    def setUpClass(cls):
        cls.source = SCRIPT.read_text(encoding="utf-8")
        cls.docstring = ast.get_docstring(ast.parse(cls.source)) or ""

    def test_first_line_is_a_python3_shebang(self):
        first_line = self.source.splitlines()[0]
        self.assertRegex(first_line, r"\A#!.*\bpython3\b")

    def test_docstring_cites_the_protocol_side_description(self):
        self.assertIn("references/artifact-digest.md", self.docstring)

    def test_docstring_lists_the_three_exit_codes(self):
        for code in ("0", "1", "2"):
            with self.subTest(code=code):
                self.assertRegex(
                    self.docstring, rf"(?m)^\s*{code}\b.*"
                )

    def test_docstring_says_this_is_not_input_digest_nor_a_git_blob_id(self):
        normalised = " ".join(self.docstring.split())
        self.assertIn("input_digest", normalised)
        self.assertIn("R1", normalised)
        self.assertIn("git blob", normalised)

    def test_script_does_not_parse_options(self):
        imported = imported_modules(self.source)
        self.assertEqual(
            imported & {"argparse", "optparse", "getopt", "click"}, set()
        )

    def test_this_test_file_has_no_dispatch_looking_string(self):
        # The repository-wide dispatch-parity scan reads every test file;
        # none may spell out a worker dispatch.
        text = Path(__file__).read_text(encoding="utf-8")
        needle = "subagent_type" + "="
        self.assertNotIn(needle, text)


if __name__ == "__main__":
    unittest.main()
