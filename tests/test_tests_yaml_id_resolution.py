"""Record check: every `acceptance_tests.*.tests` ID in every
`test-docs/**/*.tests.yaml` record is a canonical unittest ID that resolves.

The check enumerates every record under the repository's `test-docs/`
(`REPO_ROOT` is the parent of the directory holding this module, never the
working directory), reads `acceptance_tests.*.tests` per the supported record
notation (SC-2 in IMPLEMENTATION.md), judges every ID per the canonical ID and
resolution criterion (SC-1), and fails once per record file with every
extraction and resolution error listed (FR5, FR9). Each error line carries the
file, the AC (or the record-level marker `(record)`), the ID when one applies,
and a short English reason.

Resolution (SC-1): the ID must be dot-separated Python identifiers whose first
segment is exactly `tests` (no import happens for anything else); the longest
leading part that names a module is imported and the remaining segments are
looked up as attributes straight from the class and module dictionaries, so
nothing resolved is called; the result must be a module, a unittest test case
class (not the base class itself), or a function defined on such a class or an
ancestor other than the base class and its own ancestors; and the standard
loader's load-by-name must then raise nothing, record no error and return no
failed-test placeholder in the suite (which is walked, never run). The module
search path is restored to its exact prior value after every check.

This module imports the standard library only (NFR1) and no other test module.
Importing it performs record enumeration only: records may name this module
itself, which is then imported a second time under its `tests.` name.

Covers task0001 Acceptance Criteria
(feature-docs/tests-yaml-test-id-resolution/tasks/task0001.md):

- AC-1 (FR7, FR4, TS-6): every supported notation form
  (TestExtractionForms).
- AC-2 (FR7, TS-6): unsupported notation, duplicate AC key, duplicate tests
  key, missing tests key, missing acceptance_tests (TestExtractionErrors).
- AC-3 (FR8, TS-7): empty lists, unreadable records, the zero-record guard
  (TestEmptyListsAndUnreadableRecords, TestZeroRecordGuardBehavior).
- AC-4 (FR5, FR6, TS-4, TM-1): one message listing every invalid ID, the
  syntax gate before any import (TestSyntaxGate, TestRecordCheckMessage).
- AC-5 (FR6, TS-5, TM-2): resolution without execution
  (TestResolutionWithoutExecution).
- AC-6 (FR6, TM-3): search path and module cache
  (TestSearchPathAndModuleCache).
- AC-7 (FR9, TS-8): one deterministic test name per record
  (TestPerRecordTests).
- AC-8 (NFR1, NFR2, NFR3, TS-10): standard library only, collected by the
  normal run (TestModuleSelfInspection, TestNormalRunCollection).

The generated `TestRecordResolution` (one test per real record) and
`TestZeroRecordGuard` are the check itself; the fixture-based tests above
build per-record tests for temporary roots with the same generators.
"""

import ast
import contextlib
import hashlib
import importlib
import importlib.util
import os
import re
import shutil
import sys
import tempfile
import textwrap
import types
import unittest
from collections import namedtuple
from pathlib import Path
from unittest import mock

# --- constants ---------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
RECORD_SUFFIX = ".tests.yaml"
RECORD_MARKER = "(record)"

# `acs`: {AC key: [ID, ...]} for every AC extracted without error, in file
# order. `errors`: [(AC key or RECORD_MARKER, reason), ...].
Extraction = namedtuple("Extraction", ["acs", "errors"])

_RECOVERABLE = (Exception, SystemExit)


# --- record enumeration (FR5, FR8) ---------------------------------------------


# `records`: sorted repository-relative POSIX paths of the records found.
# `errors`: [(repository-relative POSIX path of a directory under `test-docs/`
# that could not be listed, short reason), ...] sorted by path.
Scan = namedtuple("Scan", ["records", "errors"])


def scan_records(root):
    """One walk of `<root>/test-docs/`: the records found and the directories
    that could not be listed. A directory whose listing fails is a scan error
    and the walk goes on with the rest, so nothing raises. A `test-docs/`
    that does not exist is not a scan error: it leaves no record, which the
    zero-record guard reports. Enumeration only: no record is read."""
    root = Path(root)
    top = root / "test-docs"
    found = []
    errors = []

    def on_error(exc):
        named = exc.filename is not None
        where = Path(os.fsdecode(exc.filename)) if named else top
        if named and where == top and isinstance(exc, FileNotFoundError):
            return
        try:
            rel = where.relative_to(root).as_posix()
        except ValueError:
            rel = where.as_posix()
        errors.append((rel, f"{type(exc).__name__}: {exc.strerror or exc}"))

    for directory, _dirnames, filenames in os.walk(top, onerror=on_error):
        for name in filenames:
            if name.endswith(RECORD_SUFFIX):
                found.append(Path(directory, name).relative_to(root).as_posix())
    return Scan(sorted(found), sorted(errors))


def enumerate_records(root):
    """Sorted repository-relative POSIX paths of every file below
    `<root>/test-docs/` whose name ends in `.tests.yaml`, at any depth.
    Enumeration only: no record is read. Directories that could not be listed
    are left out silently here; `scan_records` reports them."""
    return scan_records(root).records


# --- extractor: SC-2, the supported record notation (FR4, FR7, FR8) -------------
#
# The record is read as UTF-8 text, line by line, and never imported. Only
# `acceptance_tests.*.tests` is read; every other value is opaque text bounded
# by indentation, so a `tests:` or dash line inside it is never an ID.


class _Unsupported(Exception):
    """A notation outside SC-2; the message is the short reason."""


def _split_lines(text):
    return text.replace("\r\n", "\n").replace("\r", "\n").split("\n")


def _indent_of(line):
    """(number of leading spaces, the line without them)."""
    stripped = line.lstrip(" ")
    return len(line) - len(stripped), stripped


def _is_blank(line):
    return not line.strip(" \t")


def _is_ignorable(line):
    """Blank lines and full-line comments are ignored at every structural level."""
    return _is_blank(line) or line.lstrip(" ").startswith("#")


def _comment_or_empty(rest):
    """True when `rest` (the text after a colon) is empty or only a comment."""
    if _is_blank(rest):
        return True
    return rest[:1] in (" ", "\t") and rest.lstrip(" \t").startswith("#")


def _require_comment_or_end(rest):
    if not _comment_or_empty(rest):
        raise _Unsupported("unexpected text after the scalar")


def _is_dash(stripped):
    return stripped == "-" or stripped.startswith("- ") or stripped.startswith("-\t")


def _read_quoted(text, start):
    """The single-line quoted scalar opening at `text[start]`: (value, index
    after the closing quote). Inside single quotes two quotes stand for one;
    inside double quotes backslash-quote and backslash-backslash are the only
    escapes."""
    quote = text[start]
    value = []
    i = start + 1
    while i < len(text):
        char = text[i]
        if quote == "'":
            if char == "'":
                if text[i + 1 : i + 2] == "'":
                    value.append("'")
                    i += 2
                    continue
                return "".join(value), i + 1
        else:
            if char == "\\" and text[i + 1 : i + 2] in ('"', "\\"):
                value.append(text[i + 1])
                i += 2
                continue
            if char == '"':
                return "".join(value), i + 1
        value.append(char)
        i += 1
    raise _Unsupported("quoted scalar is not closed on its line")


def _check_plain(value):
    """A plain scalar must be one line of text, not a mapping, a sequence or a
    flow collection."""
    if not value:
        raise _Unsupported("empty scalar")
    first = value[0]
    if first in ",[]{}#&*!|>%@`":
        raise _Unsupported(f"unsupported leading character {first!r} in a scalar")
    if first in "-?:" and (len(value) == 1 or value[1] in " \t"):
        raise _Unsupported("nested sequence or mapping where a scalar is expected")
    if re.search(r":(?:[ \t]|$)", value):
        raise _Unsupported("mapping where a scalar is expected")


def _read_item_scalar(text):
    """The single-line scalar of a block sequence item (text after the dash
    and its spaces), with an optional trailing comment."""
    if text[0] in "'\"":
        value, end = _read_quoted(text, 0)
        _require_comment_or_end(text[end:])
        return value
    comment = re.search(r"[ \t]#", text)
    value = (text[: comment.start()] if comment else text).rstrip(" \t")
    _check_plain(value)
    return value


def _read_flow_sequence(text):
    """The one-line flow sequence opening at `text[0]`: a list of scalars. An
    optional comment may follow the closing bracket."""
    n = len(text)

    def skip(i):
        while i < n and text[i] in " \t":
            i += 1
        return i

    items = []
    i = skip(1)
    if i < n and text[i] == "]":
        i += 1
    else:
        while True:
            if i >= n:
                raise _Unsupported("flow sequence is not closed on its line")
            if text[i] in "'\"":
                value, i = _read_quoted(text, i)
            else:
                j = i
                while j < n and text[j] not in ",]":
                    if text[j] in "[{}":
                        raise _Unsupported("nested flow collection")
                    if text[j] == "#" and j > i and text[j - 1] in " \t":
                        raise _Unsupported("comment inside the flow sequence")
                    j += 1
                if j >= n:
                    raise _Unsupported("flow sequence is not closed on its line")
                value = text[i:j].strip(" \t")
                _check_plain(value)
                i = j
            items.append(value)
            i = skip(i)
            if i >= n:
                raise _Unsupported("flow sequence is not closed on its line")
            if text[i] == ",":
                i = skip(i + 1)
                continue
            if text[i] == "]":
                i += 1
                break
            raise _Unsupported("unexpected text in the flow sequence")
    _require_comment_or_end(text[i:])
    return items


def _parse_key_line(content):
    """(key, text after the colon) when `content` (a line without its leading
    spaces) is `key: ...` with a plain or single-line quoted key, else None."""
    if not content:
        return None
    first = content[0]
    if first in "'\"":
        try:
            key, end = _read_quoted(content, 0)
        except _Unsupported:
            return None
        while end < len(content) and content[end] in " \t":
            end += 1
        if content[end : end + 1] == ":" and (end + 1 == len(content) or content[end + 1] in " \t"):
            return key, content[end + 1 :]
        return None
    if first in ",[]{}#&*!|>%@`":
        return None
    if first in "-?:" and (len(content) == 1 or content[1] in " \t"):
        return None
    colon = re.search(r":(?:[ \t]|$)", content)
    if colon is None:
        return None
    key_text = content[: colon.start()]
    if re.search(r"[ \t]#", key_text):
        return None
    key = key_text.rstrip(" \t")
    if not key:
        return None
    return key, content[colon.start() + 1 :]


class _RecordParser:
    """Reads one record's text per SC-2 and collects every error."""

    def __init__(self, text):
        self.lines = _split_lines(text)
        self.errors = []

    def add_error(self, ac, reason):
        self.errors.append((ac, reason))

    def unsupported(self, ac, index, detail):
        self.add_error(ac, f"unsupported notation at line {index + 1}: {detail}")

    # -- helpers over the line list --

    def skip_deeper(self, index, indent, limit):
        """The first index at or after `index` whose line is neither ignorable
        nor indented deeper than `indent`."""
        lines = self.lines
        while index < limit and (_is_ignorable(lines[index]) or _indent_of(lines[index])[0] > indent):
            index += 1
        return index

    def skip_opaque(self, index, key_indent, limit):
        """An opaque value ends at the first line that is neither blank nor
        indented deeper than its key (a comment line inside the body is body
        text; a less indented one ends it)."""
        lines = self.lines
        while index < limit and (_is_blank(lines[index]) or _indent_of(lines[index])[0] > key_indent):
            index += 1
        return index

    # -- top level --

    def parse(self):
        lines = self.lines
        n = len(lines)
        i = 0
        seen_key = False
        seen_marker = False
        acceptance = 0
        acs = {}
        while i < n:
            line = lines[i]
            if _is_ignorable(line):
                i += 1
                continue
            indent, stripped = _indent_of(line)
            if stripped.startswith("\t"):
                self.unsupported(RECORD_MARKER, i, "tab in indentation")
                i += 1
                continue
            if indent == 0 and not seen_key and not seen_marker and re.fullmatch(r"---[ \t]*(#.*)?", line):
                seen_marker = True
                i += 1
                continue
            if indent != 0:
                self.unsupported(RECORD_MARKER, i, "indented line outside any value")
                i += 1
                continue
            parsed = _parse_key_line(line)
            if parsed is None:
                self.unsupported(RECORD_MARKER, i, "top-level line is not a key")
                i += 1
                continue
            seen_key = True
            key, rest = parsed
            if key != "acceptance_tests":
                i = self.skip_opaque(i + 1, 0, n)
                continue
            acceptance += 1
            end = i + 1
            while end < n and (_is_ignorable(lines[end]) or _indent_of(lines[end])[0] > 0):
                end += 1
            if acceptance > 1:
                self.unsupported(RECORD_MARKER, i, "second acceptance_tests")
            elif not _comment_or_empty(rest):
                self.unsupported(RECORD_MARKER, i, "inline value after acceptance_tests:")
            else:
                acs = self.parse_acceptance(i + 1, end)
            i = end
        if acceptance == 0:
            self.add_error(RECORD_MARKER, "missing acceptance_tests")
        return acs

    # -- AC level --

    def parse_acceptance(self, start, end):
        lines = self.lines
        ac_indent = None
        ids_by_ac = {}
        bad = set()
        seen = set()
        k = start
        while k < end:
            line = lines[k]
            if _is_ignorable(line):
                k += 1
                continue
            indent, stripped = _indent_of(line)
            if stripped.startswith("\t"):
                self.unsupported(RECORD_MARKER, k, "tab in indentation")
                k += 1
                continue
            if ac_indent is None:
                ac_indent = indent
            if indent != ac_indent:
                self.unsupported(RECORD_MARKER, k, "inconsistent indentation of AC keys")
                k = self.skip_deeper(k + 1, indent, end)
                continue
            parsed = _parse_key_line(stripped)
            if parsed is None:
                self.unsupported(RECORD_MARKER, k, "line is not an AC key")
                k = self.skip_deeper(k + 1, indent, end)
                continue
            ac_key, rest = parsed
            body_end = k + 1
            while body_end < end and (
                _is_ignorable(lines[body_end]) or _indent_of(lines[body_end])[0] > ac_indent
            ):
                body_end += 1
            errors_before = len(self.errors)
            ids = self.parse_ac(ac_key, k, rest, body_end)
            if ac_key in seen:
                self.add_error(ac_key, "duplicate AC key")
                bad.add(ac_key)
            seen.add(ac_key)
            if ids is None or len(self.errors) > errors_before:
                bad.add(ac_key)
            else:
                ids_by_ac[ac_key] = ids
            k = body_end
        return {ac: ids for ac, ids in ids_by_ac.items() if ac not in bad}

    # -- field level --

    def parse_ac(self, ac_key, key_index, rest, body_end):
        lines = self.lines
        if not _comment_or_empty(rest):
            self.unsupported(ac_key, key_index, "inline value after the AC key")
        field_indent = None
        tests_count = 0
        tests_ids = None
        f = key_index + 1
        while f < body_end:
            line = lines[f]
            if _is_ignorable(line):
                f += 1
                continue
            indent, stripped = _indent_of(line)
            if stripped.startswith("\t"):
                self.unsupported(ac_key, f, "tab in indentation")
                f += 1
                continue
            if field_indent is None:
                field_indent = indent
            if indent != field_indent:
                self.unsupported(ac_key, f, "inconsistent indentation of fields")
                f = self.skip_deeper(f + 1, indent, body_end)
                continue
            parsed = _parse_key_line(stripped)
            if parsed is None:
                self.unsupported(ac_key, f, "line is not a field key")
                f = self.skip_deeper(f + 1, indent, body_end)
                continue
            name, field_rest = parsed
            if name != "tests":
                f = self.skip_opaque(f + 1, field_indent, body_end)
                continue
            tests_count += 1
            if tests_count > 1:
                self.add_error(ac_key, "duplicate tests key")
            ids, f = self.parse_tests(ac_key, f, field_rest, field_indent, body_end)
            if tests_count == 1:
                tests_ids = ids
        if tests_count == 0:
            self.add_error(ac_key, "missing tests key")
        return tests_ids

    def parse_tests(self, ac_key, key_index, rest, key_indent, limit):
        """The value of a `tests` key: (IDs or None on an error, next index)."""
        lines = self.lines
        value = rest.lstrip(" \t")
        if value.startswith("["):
            try:
                return _read_flow_sequence(value), key_index + 1
            except _Unsupported as exc:
                self.unsupported(ac_key, key_index, str(exc))
                return None, key_index + 1
        if not _comment_or_empty(rest):
            self.unsupported(ac_key, key_index, "tests value is neither a block list nor a one-line flow list")
            return None, self.skip_deeper(key_index + 1, key_indent, limit)
        f = key_index + 1
        while f < limit and _is_ignorable(lines[f]):
            f += 1
        neither = "tests key has neither a value nor items"
        if f >= limit:
            self.unsupported(ac_key, key_index, neither)
            return None, key_index + 1
        first_indent, first = _indent_of(lines[f])
        if first.startswith("\t"):
            self.unsupported(ac_key, f, "tab in indentation")
            return None, f + 1
        if not _is_dash(first):
            if first_indent > key_indent:
                self.unsupported(ac_key, f, "tests value is not a block sequence of scalars")
                return None, self.skip_deeper(f + 1, key_indent, limit)
            self.unsupported(ac_key, key_index, neither)
            return None, key_index + 1
        if first_indent < key_indent:
            self.unsupported(ac_key, key_index, neither)
            return None, key_index + 1
        item_indent = first_indent
        ids = []
        clean = True
        while f < limit:
            line = lines[f]
            if _is_ignorable(line):
                f += 1
                continue
            indent, stripped = _indent_of(line)
            if stripped.startswith("\t"):
                self.unsupported(ac_key, f, "tab in indentation")
                clean = False
                f += 1
                continue
            if indent < item_indent:
                break
            if indent > item_indent:
                self.unsupported(ac_key, f, "tests item continues or nests on a deeper line (multi-line or nested value)")
                clean = False
                f = self.skip_deeper(f + 1, item_indent, limit)
                continue
            if not _is_dash(stripped):
                break
            content = stripped[1:].lstrip(" \t")
            try:
                if content == "" or content.startswith("#"):
                    raise _Unsupported("empty tests item")
                ids.append(_read_item_scalar(content))
            except _Unsupported as exc:
                self.unsupported(ac_key, f, str(exc))
                clean = False
            f += 1
        return (ids if clean else None), f


def extract_text(text):
    """Extract `acceptance_tests.*.tests` from the text of one record (SC-2).
    Never raises for a malformed record: every problem is an entry in
    `errors`, and an AC with an error is left out of `acs`."""
    parser = _RecordParser(text)
    acs = parser.parse()
    return Extraction(acs, parser.errors)


def extract_record(path):
    """Read the record at `path` as UTF-8 and extract it. A record that cannot
    be read or decoded is an error, never an empty list (FR8)."""
    try:
        raw = Path(path).read_bytes()
    except OSError as exc:
        return Extraction({}, [(RECORD_MARKER, f"unreadable record: {exc.strerror or exc}")])
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        return Extraction(
            {}, [(RECORD_MARKER, f"unreadable record: not valid UTF-8 ({exc.reason} at byte {exc.start})")]
        )
    return extract_text(text)


# --- resolver: SC-1, canonical test ID and resolution criterion (FR6) -----------
#
# Nothing resolved is called and no test is run. Attribute lookups read class
# and module dictionaries directly, so no descriptor or `__getattr__` runs.

_MISSING = object()


def canonical_id_failure(test_id):
    """SC-1 step 1, the syntax gate: dot-separated identifiers whose first
    segment is exactly `tests`. Returns a reason, or None when the ID passes."""
    parts = test_id.split(".")
    if parts[0] != "tests":
        return "not a canonical ID: the first dot-separated segment must be 'tests'"
    for part in parts:
        if not part.isidentifier():
            return f"not a canonical ID: segment {part!r} is not a Python identifier"
    return None


def _tests_modules():
    return {name: module for name, module in sys.modules.items() if name == "tests" or name.startswith("tests.")}


@contextlib.contextmanager
def _resolution_scope(root):
    """The root at the front of the module search path for the duration of the
    block; the path is restored to its exact prior value in every case. For a
    root other than the real repository, the module-cache entries for `tests`
    and everything under it are set aside and restored afterwards, with the
    entries the block created discarded (TM-3)."""
    isolate = Path(root).resolve() != REPO_ROOT
    saved_path = list(sys.path)
    saved_modules = _tests_modules() if isolate else {}
    for name in saved_modules:
        del sys.modules[name]
    sys.path.insert(0, str(root))
    importlib.invalidate_caches()
    try:
        yield
    finally:
        sys.path[:] = saved_path
        if isolate:
            for name in _tests_modules():
                del sys.modules[name]
            sys.modules.update(saved_modules)
            sys.path_importer_cache.pop(str(root), None)


def _one_line(exc):
    text = " ".join(str(exc).split())
    return text if len(text) <= 300 else text[:297] + "..."


def _import_failure(name, exc):
    return f"module import failed: importing {name} raised {type(exc).__name__}: {_one_line(exc)}"


def _class_attribute(cls, name):
    """(defining class, value) of `name` found in the class dictionaries along
    the MRO, or (None, _MISSING). Nothing is called."""
    for klass in cls.__mro__:
        namespace = vars(klass)
        if name in namespace:
            return klass, namespace[name]
    return None, _MISSING


def _is_test_case_class(obj):
    return isinstance(obj, type) and issubclass(obj, unittest.TestCase) and obj is not unittest.TestCase


def _structural_failure(test_id):
    """SC-1 step 2: import the longest leading part that names a module, look
    up the remaining segments as attributes, and require a module, a test
    case class, or a function defined on a test case class (or one of its
    ancestors) other than the unittest base class and its own ancestors."""
    parts = test_id.split(".")
    try:
        module = importlib.import_module(parts[0])
    except _RECOVERABLE as exc:
        return _import_failure(parts[0], exc)
    depth = 1
    while depth < len(parts) and "__path__" in vars(module):
        name = ".".join(parts[: depth + 1])
        try:
            spec = importlib.util.find_spec(name)
            if spec is None:
                break
            module = importlib.import_module(name)
        except _RECOVERABLE as exc:
            return _import_failure(name, exc)
        depth += 1
    where = ".".join(parts[:depth])
    obj = module
    parent = None
    defining = None
    for segment in parts[depth:]:
        if isinstance(obj, types.ModuleType):
            defining, value = None, vars(obj).get(segment, _MISSING)
        elif isinstance(obj, type):
            defining, value = _class_attribute(obj, segment)
        else:
            return f"not a test case class: {where} is a {type(obj).__name__}, not a class or module"
        if value is _MISSING:
            return f"attribute not found: {where} has no attribute {segment!r}"
        parent, obj = obj, value
        where = f"{where}.{segment}"
    if isinstance(obj, types.ModuleType):
        return None
    if isinstance(obj, type):
        if _is_test_case_class(obj):
            return None
        if obj is unittest.TestCase:
            return f"not a test case class: {where} is the unittest base class itself"
        return f"not a test case class: {where} is not derived from unittest.TestCase"
    if not isinstance(parent, type):
        return f"not a test case class: {where} is a {type(obj).__name__}, not a test case class"
    if not _is_test_case_class(parent):
        return f"not a test case class: {where.rsplit('.', 1)[0]} is not derived from unittest.TestCase"
    if defining in unittest.TestCase.__mro__:
        return f"not a test method: {where} is available only through the unittest base class"
    if not isinstance(obj, types.FunctionType):
        return f"not a test method: {where} is a {type(obj).__name__}, not a function"
    return None


def _walk_suite(suite):
    for item in suite:
        if isinstance(item, unittest.TestSuite):
            yield from _walk_suite(item)
        else:
            yield item


def _loader_failure(test_id):
    """SC-1 step 3: the standard loader's load-by-name on a fresh loader. A
    failure is an exception, an entry in the loader's error list, or a failed
    test placeholder in the returned suite, walked without running it."""
    loader = unittest.TestLoader()
    try:
        suite = loader.loadTestsFromName(test_id)
    except _RECOVERABLE as exc:
        return f"loader raised {type(exc).__name__}: {_one_line(exc)}"
    if loader.errors:
        lines = [line for line in loader.errors[0].strip().splitlines() if line.strip()]
        return "loader error recorded: " + (_one_line(lines[-1]) if lines else "(empty)")
    for case in _walk_suite(suite):
        if type(case).__name__ == "_FailedTest":
            return f"loader returned a failed test: {case.id()}"
    return None


def loader_failure(root, test_id):
    """The SC-1 step 3 result alone, with `root` on the module search path."""
    with _resolution_scope(root):
        return _loader_failure(test_id)


def resolve_id(root, test_id):
    """Judge one ID against `root` per SC-1. Returns None when it resolves,
    else a short English reason. An ID that fails the syntax gate is never
    imported and never reaches the loader."""
    reason = canonical_id_failure(test_id)
    if reason is not None:
        return reason
    with _resolution_scope(root):
        reason = _structural_failure(test_id)
        if reason is not None:
            return reason
        return _loader_failure(test_id)


# --- record check and per-record tests (FR5, FR9) --------------------------------


def format_error(rel, ac, test_id, reason):
    parts = [rel, ac] + ([test_id] if test_id is not None else []) + [reason]
    return ": ".join(parts)


def format_failure(rel, lines):
    return f"{rel}: {len(lines)} error(s) in this record\n" + "\n".join("  " + line for line in lines)


def check_record(root, rel):
    """The full list of error lines for one record: every extraction error,
    plus a resolution error for every invalid ID of every AC that was
    extracted without error. Nothing stops at the first error."""
    extraction = extract_record(Path(root) / rel)
    lines = [format_error(rel, ac, None, reason) for ac, reason in extraction.errors]
    outcomes = {}
    for ac, ids in extraction.acs.items():
        for test_id in ids:
            if test_id not in outcomes:
                outcomes[test_id] = resolve_id(root, test_id)
            if outcomes[test_id] is not None:
                lines.append(format_error(rel, ac, test_id, outcomes[test_id]))
    return lines


def record_test_names(records):
    """One deterministic, unique, valid-identifier test name per record path,
    derived from the path. Names that collide after sanitising get a short
    digest of their own path, so the same set of records always yields the
    same names."""
    sanitised = [re.sub(r"[^0-9A-Za-z]", "_", rel) for rel in records]
    counts = {}
    for name in sanitised:
        counts[name] = counts.get(name, 0) + 1
    names = []
    taken = set()
    for rel, name in zip(records, sanitised):
        candidate = "test_record__" + name
        if counts[name] > 1:
            candidate += "_" + hashlib.sha1(rel.encode("utf-8", "surrogateescape")).hexdigest()[:8]
        base = candidate
        serial = 1
        while candidate in taken:
            serial += 1
            candidate = f"{base}_{serial}"
        taken.add(candidate)
        names.append(candidate)
    return names


def _record_test(root, rel):
    def test(self):
        lines = check_record(root, rel)
        if lines:
            self.fail(format_failure(rel, lines))

    test.__doc__ = f"{rel} extracts and every ID resolves"
    return test


def make_record_test_class(root, class_name="TestRecords"):
    """A test case class with one test per record of `root`. Building it
    enumerates records only; extraction and resolution run when a test runs.
    The scan that finds the records also finds the directories that could not
    be listed; they never stop the building and are kept on the class as
    `scan_errors`, to be handed to `make_scan_error_test_class`."""
    records, scan_errors = scan_records(root)
    namespace = {
        "__module__": __name__,
        "__doc__": f"One test per test-docs/**/*.tests.yaml record under {root}.",
        "scan_errors": tuple(scan_errors),
    }
    for rel, name in zip(records, record_test_names(records)):
        method = _record_test(root, rel)
        method.__name__ = name
        method.__qualname__ = f"{class_name}.{name}"
        namespace[name] = method
    return type(class_name, (unittest.TestCase,), namespace)


def make_zero_record_guard_class(root, class_name="TestZeroRecordGuard"):
    """FR8: a test that fails when enumeration of `root` finds no record."""

    def test_at_least_one_record_is_found(self):
        if not enumerate_records(root):
            self.fail(f"no test-docs/**/*{RECORD_SUFFIX} record found under {root}")

    return type(
        class_name,
        (unittest.TestCase,),
        {"__module__": __name__, "test_at_least_one_record_is_found": test_at_least_one_record_is_found},
    )


def format_scan_failure(errors):
    return f"{len(errors)} scan error(s): directories under test-docs/ that could not be listed\n" + "\n".join(
        f"  {rel}: {reason}" for rel, reason in errors
    )


def make_scan_error_test_class(scan_errors, class_name="TestScanErrors"):
    """FR3: a test case class with one test that fails when `scan_errors` (the
    `(repository-relative path, reason)` pairs of `scan_records`) is not empty,
    listing every path and reason in its message, and passes when it is."""
    errors = tuple(scan_errors)

    def test_every_test_docs_directory_could_be_listed(self):
        if errors:
            self.fail(format_scan_failure(errors))

    return type(
        class_name,
        (unittest.TestCase,),
        {
            "__module__": __name__,
            "scan_errors": errors,
            "test_every_test_docs_directory_could_be_listed": test_every_test_docs_directory_could_be_listed,
        },
    )


def imported_top_level_modules(source):
    """The top-level module name of every import in `source`, in source order;
    a relative import is reported with its leading dots."""
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found.append((node.lineno, node.col_offset, [a.name.split(".")[0] for a in node.names]))
        elif isinstance(node, ast.ImportFrom):
            top = (node.module or "").split(".")[0]
            found.append((node.lineno, node.col_offset, ["." * node.level + top if node.level else top]))
    return [name for _line, _col, names in sorted(found, key=lambda f: f[:2]) for name in names]


# The real repository's tests, found by the normal run with no registration.
# Building them enumerates records only (a record may name this module, which
# is then imported a second time under its `tests.` name). The one scan that
# builds the per-record tests also yields the directories that could not be
# listed; `TestScanErrors` fails for them without stopping the import.
TestRecordResolution = make_record_test_class(REPO_ROOT, "TestRecordResolution")
TestScanErrors = make_scan_error_test_class(TestRecordResolution.scan_errors, "TestScanErrors")
TestZeroRecordGuard = make_zero_record_guard_class(REPO_ROOT, "TestZeroRecordGuard")


# --- fixture helpers ---------------------------------------------------------

RECORD_REL = "test-docs/fixture-feature/task0001.tests.yaml"


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_root(case, records=None, modules=None, raw_records=None, extra_files=None):
    """A temporary root holding `test-docs/...` records, a fixture `tests`
    package (a regular package, so it can never merge with the real
    namespace package) with the given modules, and any extra files."""
    tmp = tempfile.TemporaryDirectory()
    case.addCleanup(tmp.cleanup)
    root = Path(tmp.name).resolve()
    _write(root / "tests" / "__init__.py", "")
    for name, source in (modules or {}).items():
        _write(root / "tests" / (name + ".py"), textwrap.dedent(source))
    for rel, text in (records or {}).items():
        _write(root / rel, text)
    for rel, data in (raw_records or {}).items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_bytes(data)
    for rel, text in (extra_files or {}).items():
        _write(root / rel, textwrap.dedent(text))
    return root


def _quote(text):
    return "'" + text.replace("'", "''") + "'"


def simple_record(acs):
    """A record in the canonical block style; every ID is single-quoted so
    free text and path forms stay one scalar."""
    out = ["task_id: task0001", "baseline_failures: []", "final_failures: []", "acceptance_tests:"]
    for ac, ids in acs.items():
        out.append(f"  {ac}:")
        if ids:
            out.append("    tests:")
            out.extend(f"      - {_quote(test_id)}" for test_id in ids)
        else:
            out.append("    tests: []")
        out.append("    red_confirmed: true")
    return "\n".join(out) + "\n"


def run_generated(test_class):
    """Run the generated per-record tests of `test_class` with an inner runner
    and return the result. These are the check's own tests, never the targets
    the records name."""
    suite = unittest.TestLoader().loadTestsFromTestCase(test_class)
    result = unittest.TestResult()
    suite.run(result)
    return result


def failure_texts(result):
    """{test method name: failure text} for every failed or errored test."""
    texts = {}
    for test, text in result.failures + result.errors:
        texts[test.id().rsplit(".", 1)[-1]] = text
    return texts


@contextlib.contextmanager
def real_tests_modules_set_aside():
    """Take the real `tests` package modules out of the module cache so a test
    starts from a known-empty state, and put them back afterwards."""
    def tests_names():
        return [n for n in sys.modules if n == "tests" or n.startswith("tests.")]
    saved = {n: sys.modules[n] for n in tests_names()}
    for name in saved:
        del sys.modules[name]
    try:
        yield
    finally:
        for name in tests_names():
            del sys.modules[name]
        sys.modules.update(saved)


MARKER_MODULE = '''
import unittest

MARKER = {marker!r}


def touch():
    open(MARKER, "w").close()


def make_marker():
    touch()


class Plain:
    def test_plain(self):
        touch()


class CallableObject:
    def __call__(self, *args, **kwargs):
        touch()


class Mixin:
    def test_from_mixin(self):
        touch()


class TestA(unittest.TestCase):
    callable_attr = CallableObject()
    plain_attr = 3

    def test_one(self):
        touch()


class TestB(Mixin, unittest.TestCase):
    pass


class TestC(unittest.TestCase, Mixin):
    pass


class TestBase(unittest.TestCase):
    def test_inherited(self):
        touch()


class TestChild(TestBase):
    pass


BaseAlias = unittest.TestCase
'''

DYNAMIC_MODULE = '''
MARKER = {marker!r}


def __getattr__(name):
    open(MARKER, "w").close()
    raise AttributeError(name)
'''

LOAD_TESTS_MODULE = '''
import unittest


class TestA(unittest.TestCase):
    def test_one(self):
        pass


def load_tests(loader, tests, pattern):
    raise RuntimeError("load-tests-boom")
'''


def marker_root(case, modules=None, **kwargs):
    """A root whose `tests.fx_marker` module creates a marker file whenever a
    test body runs, a resolved callable is called, or a module is imported
    from outside the `tests` package. Returns (root, marker path)."""
    marker = Path(tempfile.mkdtemp(prefix="marker-")).resolve() / "marker"
    case.addCleanup(shutil.rmtree, marker.parent, ignore_errors=True)
    extra = {
        "evil_import_marker.py": f"""
            open({str(marker)!r}, "w").close()

            def make():
                pass
            """,
    }
    all_modules = {
        "fx_marker": MARKER_MODULE.format(marker=str(marker)),
        "fx_dynamic": DYNAMIC_MODULE.format(marker=str(marker)),
        "fx_load_tests": LOAD_TESTS_MODULE,
    }
    all_modules.update(modules or {})
    root = make_root(case, modules=all_modules, extra_files=extra, **kwargs)
    return root, marker


# --- AC-1: the SC-2 forms ------------------------------------------------------

FORMS_RECORD = r"""---
task_id: task0001
baseline_failures:
  - tests.not_read.Baseline.test_one
  - "tests.not_read.Baseline.test_two"
final_failures: [tests.not_read.Final.test_three]
acceptance_tests:
  # a full-line comment between the keys is ignored
  AC-1:
    tests:
      - tests.a.B.c
      - tests.a.B.d
    red_confirmed: true
  AC-2:
    tests:
    - tests.a.B.e
    - tests.a.B.f
    red_confirmed: true
  AC-3:
    tests: [tests.a.B.g, tests.a.B.h]
  AC-4:
    tests: []
  AC-5:
    tests:
      - 'tests.q.single'
      - "tests.q.double"
      - 'tests.q.it''s'
      - "tests.q.say \"x\""
  AC-6:
    tests:   # trailing comment on the key line
      - tests.c.D.e   # trailing comment on an item
      - "tests.c.D.f" # comment after a quoted item
      - 'tests.c.D.g # not a comment'
    tests_other: [tests.not_read.Other.test_four]
  D4-parser-unavailable:
    tests:
      - tests.d4.X.y
    red_reason: |
      Body text.
      tests:
        - tests.body.not_read
      - tests.dash.not_read
      # tests.comment.not_read
    red_confirmed: false
  AC-8:
    red_reason: >
      Folded body
      tests: [tests.folded.not_read]
      - tests.folded.dash.not_read
    tests: [tests.after.folded, 'tests.after.folded2']   # flow list with a comment
notes: |
  tests:
    - tests.top.notes.not_read
"""

FORMS_EXPECTED = {
    "AC-1": ["tests.a.B.c", "tests.a.B.d"],
    "AC-2": ["tests.a.B.e", "tests.a.B.f"],
    "AC-3": ["tests.a.B.g", "tests.a.B.h"],
    "AC-4": [],
    "AC-5": ["tests.q.single", "tests.q.double", "tests.q.it's", 'tests.q.say "x"'],
    "AC-6": ["tests.c.D.e", "tests.c.D.f", "tests.c.D.g # not a comment"],
    "D4-parser-unavailable": ["tests.d4.X.y"],
    "AC-8": ["tests.after.folded", "tests.after.folded2"],
}


class TestExtractionForms(unittest.TestCase):
    """AC-1 (FR7, FR4, TS-6): every SC-2 form yields exactly the expected IDs
    per AC and nothing from opaque values."""

    def extract(self, text):
        extraction = extract_text(text)
        self.assertEqual(extraction.errors, [], extraction.errors)
        return extraction.acs

    def test_every_supported_form_yields_exactly_the_expected_ids_per_ac(self):
        acs = self.extract(FORMS_RECORD)
        self.assertEqual(list(acs), list(FORMS_EXPECTED))
        self.assertEqual(acs, FORMS_EXPECTED)

    def test_opaque_values_never_contribute_ids(self):
        every_id = [i for ids in self.extract(FORMS_RECORD).values() for i in ids]
        self.assertEqual([i for i in every_id if "not_read" in i], [])

    def test_failure_lists_in_block_and_flow_form_are_not_extracted(self):
        text = (
            "baseline_failures:\n  - tests.x.A.test_one\n"
            "final_failures: [tests.x.A.test_two]\n"
            "acceptance_tests:\n  AC-1:\n    tests: []\n"
        )
        self.assertEqual(self.extract(text), {"AC-1": []})

    def test_hash_inside_a_quoted_item_is_not_a_comment(self):
        text = (
            "acceptance_tests:\n  AC-1:\n    tests:\n"
            "      - 'tests.a # b'\n      - \"tests.c # d\"   # real comment\n"
        )
        self.assertEqual(self.extract(text), {"AC-1": ["tests.a # b", "tests.c # d"]})

    def test_comment_line_inside_an_opaque_body_is_body_text(self):
        text = (
            "acceptance_tests:\n  AC-1:\n    red_reason: |\n      first\n"
            "      # tests: [tests.not_read.A.b]\n      last\n"
            "    tests:\n      - tests.read.A.b\n"
        )
        self.assertEqual(self.extract(text), {"AC-1": ["tests.read.A.b"]})

    def test_opaque_body_line_less_indented_than_its_key_ends_the_body(self):
        text = (
            "acceptance_tests:\n  AC-1:\n    red_reason: >\n      body\n"
            "    tests:\n      - tests.read.A.b\n"
            "  AC-2:\n    red_reason: >\n      body\n    tests: [tests.read.A.c]\n"
        )
        self.assertEqual(
            self.extract(text), {"AC-1": ["tests.read.A.b"], "AC-2": ["tests.read.A.c"]}
        )

    def test_ac_keys_other_than_ac_n_are_accepted(self):
        text = "acceptance_tests:\n  D4-parser-unavailable:\n    tests: [tests.a.B.c]\n  x:\n    tests: []\n"
        self.assertEqual(self.extract(text), {"D4-parser-unavailable": ["tests.a.B.c"], "x": []})

    def test_quoted_keys_are_accepted(self):
        text = "'acceptance_tests':\n  \"AC-1\":\n    'tests': [tests.a.B.c]\n"
        self.assertEqual(self.extract(text), {"AC-1": ["tests.a.B.c"]})

    def test_crlf_line_endings_are_accepted(self):
        text = "acceptance_tests:\r\n  AC-1:\r\n    tests:\r\n      - tests.a.B.c\r\n"
        self.assertEqual(self.extract(text), {"AC-1": ["tests.a.B.c"]})

    def test_tests_item_indent_equal_to_the_key_ends_at_the_next_field(self):
        text = (
            "acceptance_tests:\n  AC-1:\n    tests:\n    - tests.a.B.c\n"
            "    red_confirmed: true\n  AC-2:\n    tests:\n    - tests.a.B.d\n"
        )
        self.assertEqual(self.extract(text), {"AC-1": ["tests.a.B.c"], "AC-2": ["tests.a.B.d"]})


# --- AC-2: extraction errors ---------------------------------------------------


def _ac_record(body):
    return "task_id: task0001\nacceptance_tests:\n" + body


class TestExtractionErrors(unittest.TestCase):
    """AC-2 (FR7, TS-6): each unsupported form fails with a message naming the
    record file, the AC (or the record-level marker) and the matching reason."""

    def check(self, text):
        root = make_root(self, records={RECORD_REL: text})
        return root, check_record(root, RECORD_REL)

    def assert_error(self, lines, ac, reason):
        self.assertTrue(
            any(RECORD_REL in line and f": {ac}: " in line and reason in line for line in lines),
            f"no error line with file, AC {ac!r} and {reason!r} in {lines}",
        )

    def test_unsupported_notations_inside_an_ac_name_the_file_the_ac_and_the_notation(self):
        cases = {
            "mapping item": "  AC-1:\n    tests:\n      - name: tests.a.B.c\n",
            "nested sequence": "  AC-1:\n    tests:\n      - - tests.a.B.c\n",
            "multi-line plain item": "  AC-1:\n    tests:\n      - tests.a.B\n        continued\n",
            "multi-line quoted item": "  AC-1:\n    tests:\n      - 'tests.a\n        .B'\n",
            "empty item": "  AC-1:\n    tests:\n      - \n",
            "flow list spanning lines": "  AC-1:\n    tests: [tests.a.B.c,\n      tests.a.B.d]\n",
            "inline scalar": "  AC-1:\n    tests: tests.a.B.c\n",
            "flow mapping": "  AC-1:\n    tests: {a: b}\n",
            "inline value after the AC key": "  AC-1: tests.a.B.c\n    tests: []\n",
            "tab in indentation": "  AC-1:\n    tests: []\n    \tred_confirmed: true\n",
            "inconsistent field indentation": "  AC-1:\n    tests: []\n      red_confirmed: true\n",
            "trailing text after a quoted item": "  AC-1:\n    tests:\n      - 'tests.a.B' extra\n",
            "empty flow element": "  AC-1:\n    tests: [tests.a.B.c, ]\n",
            "nested flow list": "  AC-1:\n    tests: [[tests.a.B.c]]\n",
        }
        for label, body in cases.items():
            with self.subTest(label):
                _, lines = self.check(_ac_record(body))
                self.assert_error(lines, "AC-1", "unsupported notation")

    def test_a_dedented_comment_ends_the_opaque_body_and_the_lines_after_it_are_unsupported(self):
        body = (
            "  AC-1:\n    red_reason: |\n      first\n  # dedented comment\n"
            "      still body?\n    tests: []\n"
        )
        _, lines = self.check(_ac_record(body))
        self.assert_error(lines, "AC-1", "unsupported notation at line 7")

    def test_unsupported_notation_message_carries_the_line_number(self):
        _, lines = self.check(_ac_record("  AC-1:\n    tests: tests.a.B.c\n"))
        self.assert_error(lines, "AC-1", "unsupported notation at line 4")

    def test_second_acceptance_tests_is_unsupported_notation(self):
        text = _ac_record("  AC-1:\n    tests: []\n") + "acceptance_tests:\n  AC-2:\n    tests: []\n"
        _, lines = self.check(text)
        self.assert_error(lines, "(record)", "unsupported notation")

    def test_inline_value_after_acceptance_tests_is_unsupported_notation(self):
        _, lines = self.check("task_id: task0001\nacceptance_tests: {}\n")
        self.assert_error(lines, "(record)", "unsupported notation")

    def test_a_tests_key_with_neither_value_nor_items_is_unsupported_notation(self):
        for label, body in {
            "followed by another field": "  AC-1:\n    tests:\n    red_confirmed: true\n",
            "at the end of the file": "  AC-1:\n    tests:\n",
            "followed only by a comment": "  AC-1:\n    tests:   # nothing\n    red_confirmed: true\n",
        }.items():
            with self.subTest(label):
                _, lines = self.check(_ac_record(body))
                self.assert_error(lines, "AC-1", "neither a value nor items")

    def test_duplicate_ac_key_is_reported_with_the_ac(self):
        _, lines = self.check(_ac_record("  AC-1:\n    tests: []\n  AC-1:\n    tests: []\n"))
        self.assert_error(lines, "AC-1", "duplicate AC key")

    def test_duplicate_tests_key_is_reported_with_the_ac(self):
        _, lines = self.check(_ac_record("  AC-1:\n    tests: []\n    tests: [tests.a.B.c]\n"))
        self.assert_error(lines, "AC-1", "duplicate tests key")

    def test_missing_tests_key_is_reported_with_the_ac(self):
        _, lines = self.check(_ac_record("  AC-1:\n    tests: []\n  AC-2:\n    red_confirmed: true\n"))
        self.assert_error(lines, "AC-2", "missing tests key")
        self.assertFalse(any(": AC-1: " in line for line in lines), lines)

    def test_missing_acceptance_tests_is_reported_with_the_record_level_marker(self):
        _, lines = self.check("task_id: task0001\nbaseline_failures: []\n")
        self.assert_error(lines, "(record)", "missing acceptance_tests")

    def test_each_error_makes_the_per_record_test_fail_naming_the_file_and_the_ac(self):
        root = make_root(
            self, records={RECORD_REL: _ac_record("  AC-1:\n    tests: tests.a.B.c\n")}
        )
        texts = failure_texts(run_generated(make_record_test_class(root)))
        self.assertEqual(len(texts), 1)
        (text,) = texts.values()
        self.assertIn(RECORD_REL, text)
        self.assertIn("AC-1", text)
        self.assertIn("unsupported notation", text)

    def test_all_extraction_errors_are_collected_not_only_the_first(self):
        body = (
            "  AC-1:\n    tests: tests.a.B.c\n"
            "  AC-2:\n    red_confirmed: true\n"
            "  AC-3:\n    tests: []\n    tests: []\n"
        )
        _, lines = self.check(_ac_record(body))
        self.assert_error(lines, "AC-1", "unsupported notation")
        self.assert_error(lines, "AC-2", "missing tests key")
        self.assert_error(lines, "AC-3", "duplicate tests key")

    def test_an_ac_with_an_extraction_error_gets_no_resolution_errors(self):
        text = _ac_record("  AC-1:\n    tests:\n      - tests.nope.A.b\n      - name: x\n")
        _, lines = self.check(text)
        self.assertFalse(any("tests.nope.A.b" in line for line in lines), lines)


# --- AC-3: empty lists, unreadable records, the zero-record guard -------------


class TestEmptyListsAndUnreadableRecords(unittest.TestCase):
    """AC-3 (FR8, TS-7)."""

    def test_a_record_whose_every_ac_is_an_empty_list_passes(self):
        root = make_root(
            self,
            records={RECORD_REL: simple_record({"AC-1": [], "AC-2": [], "D4-x": []})},
        )
        self.assertEqual(check_record(root, RECORD_REL), [])
        self.assertEqual(failure_texts(run_generated(make_record_test_class(root))), {})

    def test_a_record_that_cannot_be_decoded_as_utf8_fails_instead_of_reading_as_empty(self):
        raw = b"task_id: task0001\nacceptance_tests:\n  AC-1:\n    tests: []\n    red_reason: \xff\xfe\n"
        root = make_root(self, raw_records={RECORD_REL: raw})
        lines = check_record(root, RECORD_REL)
        self.assertEqual(len(lines), 1, lines)
        self.assertIn(RECORD_REL, lines[0])
        self.assertIn("unreadable record", lines[0])
        self.assertEqual(len(failure_texts(run_generated(make_record_test_class(root)))), 1)

    def test_a_record_that_cannot_be_read_fails_instead_of_reading_as_empty(self):
        root = make_root(self)
        (root / "test-docs" / "feature").mkdir(parents=True)
        (root / RECORD_REL).parent.mkdir(parents=True, exist_ok=True)
        os.symlink(root / "does-not-exist", root / RECORD_REL)
        lines = check_record(root, RECORD_REL)
        self.assertEqual(len(lines), 1, lines)
        self.assertIn("unreadable record", lines[0])

    def test_a_tests_key_with_neither_value_nor_items_fails_instead_of_reading_as_empty(self):
        text = _ac_record("  AC-1:\n    tests:\n    red_confirmed: true\n")
        root = make_root(self, records={RECORD_REL: text})
        lines = check_record(root, RECORD_REL)
        self.assertEqual(len(lines), 1, lines)
        self.assertIn("neither a value nor items", lines[0])

    def test_an_empty_file_fails_as_a_missing_acceptance_tests(self):
        root = make_root(self, records={RECORD_REL: ""})
        lines = check_record(root, RECORD_REL)
        self.assertEqual(len(lines), 1, lines)
        self.assertIn("missing acceptance_tests", lines[0])


class TestZeroRecordGuardBehavior(unittest.TestCase):
    """AC-3 (FR8, TS-7): a root without any record makes the guard fail."""

    def guard_result(self, root):
        return run_generated(make_zero_record_guard_class(root))

    def test_guard_fails_for_a_root_without_test_docs(self):
        root = make_root(self)
        result = self.guard_result(root)
        self.assertEqual(len(result.failures) + len(result.errors), 1)
        self.assertEqual(result.testsRun, 1)

    def test_guard_fails_when_test_docs_holds_no_tests_yaml_file(self):
        root = make_root(
            self,
            records={
                "test-docs/f/task0001.tests.yml": "x: 1\n",
                "test-docs/f/task0001.tests.yaml.bak": "x: 1\n",
                "test-docs/f/notes.md": "x\n",
            },
        )
        (root / "test-docs" / "f" / "dir.tests.yaml").mkdir()
        self.assertEqual(len(self.guard_result(root).failures), 1)

    def test_guard_passes_when_one_record_exists(self):
        root = make_root(self, records={RECORD_REL: simple_record({"AC-1": []})})
        result = self.guard_result(root)
        self.assertEqual((result.testsRun, len(result.failures), len(result.errors)), (1, 0, 0))

    def test_guard_failure_message_says_no_record_was_found(self):
        root = make_root(self)
        (text,) = failure_texts(self.guard_result(root)).values()
        self.assertIn("no", text)
        self.assertIn(".tests.yaml", text)


LOCKED_DIR_REL = "test-docs/locked-feature"
LOCKED_RECORD_REL = LOCKED_DIR_REL + "/task0009.tests.yaml"


def permission_error(path):
    """The error a directory listing raises when the directory is not readable."""
    return PermissionError(13, "Permission denied", str(path))


@contextlib.contextmanager
def listing_fails(failures):
    """`os.scandir` (the directory-listing primitive of `os.walk`) raises
    `failures[str(path)]` for exactly those directories and lists every other
    one for real. Only the block is affected."""
    real_scandir = os.scandir

    def scandir(path="."):
        error = failures.get(os.fspath(path))
        if error is not None:
            raise error
        return real_scandir(path)

    with mock.patch.object(os, "scandir", scandir):
        yield


class TestRecordEnumeration(unittest.TestCase):
    """Enumeration of `test-docs/**/*.tests.yaml` (FR5)."""

    def test_lists_nested_records_sorted_with_repository_relative_posix_paths(self):
        root = make_root(
            self,
            records={
                "test-docs/b/task0002.tests.yaml": "x: 1\n",
                "test-docs/a/task0001.tests.yaml": "x: 1\n",
                "test-docs/a/deeper/still/task0003.tests.yaml": "x: 1\n",
                "test-docs/a/ignored.yaml": "x: 1\n",
                "elsewhere/task0004.tests.yaml": "x: 1\n",
            },
        )
        self.assertEqual(
            enumerate_records(root),
            [
                "test-docs/a/deeper/still/task0003.tests.yaml",
                "test-docs/a/task0001.tests.yaml",
                "test-docs/b/task0002.tests.yaml",
            ],
        )

    def test_a_root_without_test_docs_has_no_records(self):
        self.assertEqual(enumerate_records(make_root(self)), [])

    def test_the_real_repository_root_is_the_parent_of_the_tests_directory(self):
        self.assertEqual(REPO_ROOT, Path(__file__).resolve().parent.parent)
        self.assertTrue((REPO_ROOT / "test-docs").is_dir())

    def test_real_repository_enumeration_does_not_depend_on_the_working_directory(self):
        before = enumerate_records(REPO_ROOT)
        start = os.getcwd()
        elsewhere = tempfile.TemporaryDirectory()
        self.addCleanup(elsewhere.cleanup)
        self.addCleanup(os.chdir, start)
        os.chdir(elsewhere.name)
        self.assertEqual(enumerate_records(REPO_ROOT), before)
        self.assertTrue(before)

    # -- scan errors (FR3): directories under test-docs/ that cannot be listed --

    def test_a_subdirectory_that_cannot_be_listed_is_recorded_and_the_readable_record_is_kept(self):
        """AC-1 (FR3, TS-3)."""
        root = make_root(self, records={RECORD_REL: "x: 1\n", LOCKED_RECORD_REL: "x: 1\n"})
        locked = root / LOCKED_DIR_REL
        with listing_fails({str(locked): permission_error(locked)}):
            scan = scan_records(root)
        self.assertEqual(scan.records, [RECORD_REL])
        self.assertEqual(len(scan.errors), 1, scan.errors)
        ((rel, reason),) = scan.errors
        self.assertEqual(rel, LOCKED_DIR_REL)
        self.assertIn("PermissionError", reason)
        self.assertIn("Permission denied", reason)

    def test_a_scan_error_path_is_repository_relative_and_posix_for_a_deeply_nested_directory(self):
        """AC-1 (FR3)."""
        deep_rel = "test-docs/a/b/c"
        root = make_root(self, records={RECORD_REL: "x: 1\n", deep_rel + "/task0002.tests.yaml": "x: 1\n"})
        deep = root / deep_rel
        with listing_fails({str(deep): permission_error(deep)}):
            scan = scan_records(root)
        self.assertEqual([rel for rel, _reason in scan.errors], [deep_rel])
        self.assertEqual(scan.records, [RECORD_REL])

    def test_a_listing_failure_of_the_test_docs_root_other_than_a_missing_root_is_recorded(self):
        """AC-1 (FR3): only a root that does not exist is left to the zero-record guard."""
        root = make_root(self, records={RECORD_REL: "x: 1\n"})
        top = root / "test-docs"
        with listing_fails({str(top): permission_error(top)}):
            scan = scan_records(root)
        self.assertEqual(scan.records, [])
        self.assertEqual([rel for rel, _reason in scan.errors], ["test-docs"])
        self.assertIn("PermissionError", scan.errors[0][1])

    def test_a_subdirectory_that_disappears_during_the_scan_is_recorded(self):
        """AC-1 (FR3): a missing subdirectory is a scan error; only a missing root is not."""
        root = make_root(self, records={RECORD_REL: "x: 1\n", LOCKED_RECORD_REL: "x: 1\n"})
        gone = root / LOCKED_DIR_REL
        error = FileNotFoundError(2, "No such file or directory", str(gone))
        with listing_fails({str(gone): error}):
            scan = scan_records(root)
        self.assertEqual([rel for rel, _reason in scan.errors], [LOCKED_DIR_REL])
        self.assertIn("FileNotFoundError", scan.errors[0][1])
        self.assertEqual(scan.records, [RECORD_REL])

    def test_every_unlistable_directory_is_recorded_in_path_order(self):
        """AC-1 (FR3)."""
        root = make_root(
            self,
            records={
                RECORD_REL: "x: 1\n",
                "test-docs/z-locked/a.tests.yaml": "x: 1\n",
                "test-docs/a-locked/a.tests.yaml": "x: 1\n",
            },
        )
        failures = {
            str(root / "test-docs" / name): permission_error(root / "test-docs" / name)
            for name in ("z-locked", "a-locked")
        }
        with listing_fails(failures):
            scan = scan_records(root)
        self.assertEqual([rel for rel, _reason in scan.errors], ["test-docs/a-locked", "test-docs/z-locked"])
        self.assertEqual(scan.records, [RECORD_REL])

    def test_a_root_without_test_docs_records_no_scan_error_and_no_record(self):
        """AC-4 (FR3): the missing root stays with the zero-record guard."""
        scan = scan_records(make_root(self))
        self.assertEqual((scan.records, scan.errors), ([], []))

    def test_a_tree_that_lists_cleanly_records_no_scan_error(self):
        """AC-4 (FR3)."""
        root = make_root(self, records={RECORD_REL: "x: 1\n", LOCKED_RECORD_REL: "x: 1\n"})
        scan = scan_records(root)
        self.assertEqual(scan.errors, [])
        self.assertEqual(scan.records, enumerate_records(root))

    def test_enumerate_records_keeps_its_plain_list_return_when_a_directory_cannot_be_listed(self):
        """AC-5 (SPEC A3, NFR3): the return shape is a list of path strings, errors or not."""
        root = make_root(self, records={RECORD_REL: "x: 1\n", LOCKED_RECORD_REL: "x: 1\n"})
        locked = root / LOCKED_DIR_REL
        with listing_fails({str(locked): permission_error(locked)}):
            found = enumerate_records(root)
        self.assertIs(type(found), list)
        self.assertEqual(found, [RECORD_REL])
        self.assertTrue(all(type(rel) is str for rel in found))
        self.assertEqual(enumerate_records(root), sorted([RECORD_REL, LOCKED_RECORD_REL]))


class TestScanErrorReporting(unittest.TestCase):
    """FR3: a directory that cannot be listed is the failure of a test the
    normal run collects, with the module import and the readable records
    unaffected."""

    ERRORS = [
        ("test-docs/a/locked", "PermissionError: Permission denied"),
        ("test-docs/b", "FileNotFoundError: No such file or directory"),
    ]

    def test_a_non_empty_error_list_fails_naming_every_path_and_reason(self):
        """AC-2 (FR3, SPEC AC-3)."""
        result = run_generated(make_scan_error_test_class(self.ERRORS))
        self.assertEqual(result.testsRun, 1)
        texts = failure_texts(result)
        self.assertEqual(len(texts), 1, texts)
        (text,) = texts.values()
        for rel, reason in self.ERRORS:
            with self.subTest(rel):
                self.assertTrue(
                    any(rel in line and reason in line for line in text.splitlines()),
                    f"no line with both {rel!r} and {reason!r} in {text!r}",
                )

    def test_an_empty_error_list_passes(self):
        """AC-2 (FR3, SPEC AC-3)."""
        result = run_generated(make_scan_error_test_class([]))
        self.assertEqual((result.testsRun, len(result.failures), len(result.errors)), (1, 0, 0))

    def test_the_scan_error_class_is_a_test_case_with_exactly_one_test(self):
        """AC-2 (FR3, NFR2): a plain TestCase subclass with exactly one test, named as asked."""
        test_class = make_scan_error_test_class(self.ERRORS, "TestFixtureScanErrors")
        self.assertTrue(issubclass(test_class, unittest.TestCase))
        self.assertEqual(test_class.__name__, "TestFixtureScanErrors")
        self.assertEqual(test_class.__module__, __name__)
        self.assertEqual(len(unittest.TestLoader().getTestCaseNames(test_class)), 1)

    def test_scan_errors_found_while_generating_the_record_class_reach_the_scan_error_class(self):
        """AC-3 (FR3): the single scan yields the readable records and the errors."""
        root = make_root(
            self,
            records={RECORD_REL: simple_record({"AC-1": []}), LOCKED_RECORD_REL: simple_record({"AC-1": []})},
        )
        locked = root / LOCKED_DIR_REL
        with listing_fails({str(locked): permission_error(locked)}):
            record_class = make_record_test_class(root)
        scan_class = make_scan_error_test_class(record_class.scan_errors)
        self.assertEqual(
            unittest.TestLoader().getTestCaseNames(record_class), record_test_names([RECORD_REL])
        )
        self.assertEqual([rel for rel, _reason in record_class.scan_errors], [LOCKED_DIR_REL])
        self.assertEqual(failure_texts(run_generated(record_class)), {})
        (text,) = failure_texts(run_generated(scan_class)).values()
        self.assertIn(LOCKED_DIR_REL, text)
        self.assertIn("PermissionError", text)

    def test_a_root_without_test_docs_fails_only_the_zero_record_guard(self):
        """AC-4 (FR3): no scan error, so the scan-error test passes; the guard fails as at base."""
        root = make_root(self)
        record_class = make_record_test_class(root)
        self.assertEqual(tuple(record_class.scan_errors), ())
        scan_result = run_generated(make_scan_error_test_class(record_class.scan_errors))
        self.assertTrue(scan_result.wasSuccessful())
        self.assertEqual(len(failure_texts(run_generated(make_zero_record_guard_class(root)))), 1)

    def test_a_scan_error_does_not_stop_the_import_of_the_module_or_its_generation(self):
        """AC-3 (FR3): the module-level generation runs against the real repository
        with one real directory made unlistable; a fresh copy of this module is
        executed so the module-level statements themselves are what run."""
        real_records = enumerate_records(REPO_ROOT)
        blocked_rel = Path(real_records[0]).parent.as_posix()
        blocked = REPO_ROOT / blocked_rel
        spec = importlib.util.spec_from_file_location("fx_checker_with_scan_error", Path(__file__).resolve())
        module = importlib.util.module_from_spec(spec)
        with listing_fails({str(blocked): permission_error(blocked)}):
            spec.loader.exec_module(module)
        readable = [rel for rel in real_records if not Path(rel).is_relative_to(blocked_rel)]
        self.assertEqual(
            sorted(unittest.TestLoader().getTestCaseNames(module.TestRecordResolution)),
            sorted(record_test_names(readable)),
        )
        self.assertEqual([rel for rel, _reason in module.TestScanErrors.scan_errors], [blocked_rel])
        self.assertTrue(issubclass(module.TestScanErrors, unittest.TestCase))
        (text,) = failure_texts(run_generated(module.TestScanErrors)).values()
        self.assertIn(blocked_rel, text)
        self.assertIn("PermissionError", text)

    def test_the_real_repository_scan_error_test_passes(self):
        """AC-6 (FR3, NFR3): the real tree lists cleanly, so the module-level scan-error test passes."""
        self.assertEqual(list(TestScanErrors.scan_errors), scan_records(REPO_ROOT).errors)
        result = run_generated(TestScanErrors)
        self.assertEqual((result.testsRun, result.wasSuccessful()), (1, True))


# --- AC-4: the record check message, the syntax gate ---------------------------


class TestSyntaxGate(unittest.TestCase):
    """SC-1 step 1: the canonical ID form."""

    def test_canonical_ids_pass_the_gate(self):
        for test_id in ("tests", "tests.test_x", "tests.test_x.TestY", "tests.test_x.TestY.test_z", "tests._a1.B_2"):
            with self.subTest(test_id):
                self.assertIsNone(canonical_id_failure(test_id))

    def test_everything_else_fails_the_gate_with_a_reason(self):
        for test_id in (
            "",
            "test_x.TestY.test_z",
            "tests/test_x.py::TestY::test_z",
            "tests/test_x.py",
            "test_*",
            "tests.test_*",
            "tests.",
            "tests..x",
            ".tests.x",
            "Tests.x",
            "tests.1x",
            "tests.x y",
            "tests.x-y",
            "tests.x\n",
            " tests.x",
            "tests.x ",
            "full suite: python3 -m unittest discover -s tests",
            "os.system",
        ):
            with self.subTest(test_id):
                reason = canonical_id_failure(test_id)
                self.assertIsNotNone(reason)
                self.assertIn("not a canonical ID", reason)


class TestRecordCheckMessage(unittest.TestCase):
    """AC-4 (FR5, FR6, TS-4, TM-1): one test, one message, every invalid ID."""

    INVALID = {
        "nonexistent module": "tests.no_such_module.TestA.test_one",
        "nonexistent class": "tests.fx_marker.NoSuchClass",
        "nonexistent method": "tests.fx_marker.TestA.no_such_method",
        "no tests prefix": "fx_marker.TestA.test_one",
        "path form": "tests/test_fx.py::TestA::test_one",
        "free text": "the whole suite passes (see notes)",
    }

    def make(self):
        root, marker = marker_root(
            self,
            records={
                RECORD_REL: simple_record(
                    {
                        "AC-1": ["tests.fx_marker.TestA.test_one"],
                        "AC-2": list(self.INVALID.values()),
                        "D4-other": ["tests.fx_marker.TestB.test_from_mixin"],
                    }
                )
            },
        )
        return root, marker

    def test_one_failing_test_lists_the_file_the_ac_every_id_and_a_reason_for_each(self):
        root, _ = self.make()
        texts = failure_texts(run_generated(make_record_test_class(root)))
        self.assertEqual(len(texts), 1, texts)
        (text,) = texts.values()
        self.assertIn(RECORD_REL, text)
        for label, test_id in self.INVALID.items():
            with self.subTest(label):
                (line,) = [l for l in text.splitlines() if test_id in l]
                self.assertIn(RECORD_REL, line)
                self.assertIn(": AC-2: ", line)
                reason = line.split(test_id + ": ", 1)[1]
                self.assertTrue(reason.strip(), line)

    def test_valid_ids_and_other_acs_are_not_listed(self):
        root, _ = self.make()
        (text,) = failure_texts(run_generated(make_record_test_class(root))).values()
        self.assertNotIn("AC-1", text)
        self.assertNotIn("D4-other", text)
        self.assertNotIn("test_from_mixin", text)

    def test_first_line_names_the_record_and_the_number_of_errors(self):
        root, _ = self.make()
        (text,) = failure_texts(run_generated(make_record_test_class(root))).values()
        (head,) = [l for l in text.splitlines() if "error(s) in this record" in l]
        self.assertIn(RECORD_REL, head)
        self.assertIn(f"{len(self.INVALID)} error(s)", head)

    def test_a_record_with_only_valid_ids_has_no_error_lines(self):
        root, marker = marker_root(
            self,
            records={RECORD_REL: simple_record({"AC-1": ["tests.fx_marker.TestA.test_one"]})},
        )
        self.assertEqual(check_record(root, RECORD_REL), [])
        self.assertFalse(marker.exists())

    def test_an_id_outside_the_tests_package_is_rejected_before_any_import(self):
        root, marker = marker_root(
            self,
            records={
                RECORD_REL: simple_record(
                    {"AC-1": ["evil_import_marker", "evil_import_marker.make", "tests/../evil_import_marker"]}
                )
            },
        )
        lines = check_record(root, RECORD_REL)
        self.assertEqual(len(lines), 3, lines)
        for line in lines:
            self.assertIn("not a canonical ID", line)
        self.assertFalse(marker.exists(), "the syntax gate must reject before any import (TM-1)")
        self.assertNotIn("evil_import_marker", sys.modules)

    def test_the_evil_module_would_have_created_the_marker_if_it_had_been_imported(self):
        root, marker = marker_root(self)
        self.addCleanup(sys.modules.pop, "evil_import_marker", None)
        sys.path.insert(0, str(root))
        self.addCleanup(sys.path.remove, str(root))
        importlib.invalidate_caches()
        importlib.import_module("evil_import_marker")
        self.assertTrue(marker.exists())

    def test_an_id_with_duplicates_across_acs_is_reported_for_each_ac(self):
        root = make_root(
            self,
            records={RECORD_REL: simple_record({"AC-1": ["tests.nope.A.b"], "AC-2": ["tests.nope.A.b"]})},
        )
        lines = check_record(root, RECORD_REL)
        self.assertEqual(len(lines), 2, lines)
        self.assertIn(": AC-1: ", lines[0])
        self.assertIn(": AC-2: ", lines[1])


# --- AC-5: resolution without execution (TM-2) --------------------------------


class TestResolutionWithoutExecution(unittest.TestCase):
    """AC-5 (FR6, TS-5, TM-2)."""

    PASSING = (
        "tests.fx_marker",
        "tests.fx_marker.TestA",
        "tests.fx_marker.TestA.test_one",
        "tests.fx_marker.TestB",
        "tests.fx_marker.TestB.test_from_mixin",
        "tests.fx_marker.TestC.test_from_mixin",
        "tests.fx_marker.TestChild.test_inherited",
        "tests",
    )
    FAILING = {
        "tests.fx_marker.make_marker": "not a test case class",
        "tests.fx_marker.Plain": "not a test case class",
        "tests.fx_marker.Plain.test_plain": "not a test case class",
        "tests.fx_marker.CallableObject": "not a test case class",
        "tests.fx_marker.BaseAlias": "not a test case class",
        "tests.fx_marker.TestA.test_one.deeper": "not a test case class",
        "tests.fx_marker.TestA.callable_attr": "not a test method",
        "tests.fx_marker.TestA.plain_attr": "not a test method",
        "tests.fx_marker.TestA.assertEqual": "not a test method",
        "tests.fx_marker.TestA.run": "not a test method",
        "tests.fx_marker.TestA.__init__": "not a test method",
        "tests.fx_marker.TestA.no_such_method": "attribute not found",
        "tests.fx_marker.NoSuchClass": "attribute not found",
        "tests.no_such_module": "attribute not found",
        "tests.no_such_module.TestA.test_one": "attribute not found",
    }

    def setUp(self):
        self.root, self.marker = marker_root(self)

    def test_module_class_and_method_ids_of_a_marker_test_module_pass_without_running_anything(self):
        for test_id in self.PASSING:
            with self.subTest(test_id):
                self.assertIsNone(resolve_id(self.root, test_id))
        self.assertFalse(self.marker.exists(), "resolution must not run a test body")

    def test_callables_and_non_test_case_attributes_are_rejected_and_nothing_is_called(self):
        for test_id, reason in self.FAILING.items():
            with self.subTest(test_id):
                self.assertIn(reason, resolve_id(self.root, test_id) or "")
        self.assertFalse(self.marker.exists(), "resolution must not call a resolved object")

    def test_a_method_available_only_through_the_unittest_base_class_is_rejected(self):
        self.assertIn("not a test method", resolve_id(self.root, "tests.fx_marker.TestA.assertEqual"))

    def test_a_test_method_inherited_from_a_non_base_mixin_is_accepted(self):
        self.assertIsNone(resolve_id(self.root, "tests.fx_marker.TestB.test_from_mixin"))
        self.assertIsNone(resolve_id(self.root, "tests.fx_marker.TestC.test_from_mixin"))

    def test_a_nonexistent_method_on_an_existing_class_fails_through_the_loader_error_path(self):
        reason = loader_failure(self.root, "tests.fx_marker.TestA.no_such_method")
        self.assertIsNotNone(reason)
        self.assertIn("loader error recorded", reason)
        self.assertNotIn("loader raised", reason)

    def test_a_nonexistent_module_fails_through_the_loader_error_path_too(self):
        reason = loader_failure(self.root, "tests.no_such_module.TestA.test_one")
        self.assertIsNotNone(reason)
        self.assertIn("loader error recorded", reason)

    def test_the_loader_confirms_a_real_method_without_a_failure(self):
        self.assertIsNone(loader_failure(self.root, "tests.fx_marker.TestA.test_one"))
        self.assertFalse(self.marker.exists())

    def test_a_module_that_exists_but_raises_while_importing_is_reported_with_the_import_error(self):
        root = make_root(
            self,
            modules={"fx_raises": "raise RuntimeError('boom-while-importing')\n", "fx_syntax": "def (:\n"},
        )
        reason = resolve_id(root, "tests.fx_raises.TestA.test_one")
        self.assertIn("module import failed", reason)
        self.assertIn("RuntimeError", reason)
        self.assertIn("boom-while-importing", reason)
        reason = resolve_id(root, "tests.fx_syntax")
        self.assertIn("module import failed", reason)
        self.assertIn("SyntaxError", reason)

    def test_a_module_level_getattr_is_never_triggered_by_the_attribute_lookup(self):
        reason = resolve_id(self.root, "tests.fx_dynamic.anything")
        self.assertIn("attribute not found", reason)
        self.assertFalse(self.marker.exists(), "attribute lookup must not run module code")

    def test_a_module_whose_load_tests_raises_passes_the_structure_and_fails_at_the_loader(self):
        with _resolution_scope(self.root):
            self.assertIsNone(_structural_failure("tests.fx_load_tests"))
        reason = resolve_id(self.root, "tests.fx_load_tests")
        self.assertIn("loader error recorded", reason)
        self.assertIn("load-tests-boom", reason)

    def test_a_module_that_exits_while_importing_does_not_end_the_run(self):
        root = make_root(self, modules={"fx_exit": "import sys\nsys.exit(3)\n"})
        reason = resolve_id(root, "tests.fx_exit")
        self.assertIn("module import failed", reason)

    def test_a_loader_that_raises_is_reported_as_a_failure(self):
        with mock.patch.object(unittest.TestLoader, "loadTestsFromName", side_effect=RuntimeError("loader-boom")):
            reason = loader_failure(self.root, "tests.fx_marker.TestA.test_one")
        self.assertIn("loader raised", reason)
        self.assertIn("loader-boom", reason)

    def test_a_failed_test_placeholder_in_a_nested_suite_is_reported_without_running_it(self):
        class _FailedTest(unittest.TestCase):
            def test_placeholder(self):
                raise AssertionError("the placeholder must not be run")

        suite = unittest.TestSuite([unittest.TestSuite([_FailedTest("test_placeholder")])])
        with mock.patch.object(unittest.TestLoader, "loadTestsFromName", return_value=suite):
            reason = loader_failure(self.root, "tests.fx_marker.TestA.test_one")
        self.assertIn("loader returned a failed test", reason)

    def test_a_suite_without_a_placeholder_is_not_a_failure(self):
        suite = unittest.TestSuite([unittest.TestSuite()])
        with mock.patch.object(unittest.TestLoader, "loadTestsFromName", return_value=suite):
            self.assertIsNone(loader_failure(self.root, "tests.fx_marker.TestA.test_one"))


# --- AC-6: search path and module cache (TM-3) --------------------------------


class TestSearchPathAndModuleCache(unittest.TestCase):
    """AC-6 (FR6, TM-3)."""

    IDS = (
        "tests.fx_marker.TestA.test_one",
        "tests.fx_marker",
        "tests.fx_marker.NoSuchClass",
        "tests.no_such_module",
        "fx_marker.TestA.test_one",
        "tests.fx_raises",
    )

    def setUp(self):
        self.root, self.marker = marker_root(
            self, modules={"fx_raises": "raise RuntimeError('boom')\n"}
        )

    def test_search_path_is_identical_after_every_resolution_including_failures(self):
        path_object = sys.path
        for test_id in self.IDS:
            with self.subTest(test_id):
                before = list(sys.path)
                resolve_id(self.root, test_id)
                self.assertEqual(list(sys.path), before)
                self.assertIs(sys.path, path_object)

    def test_search_path_is_restored_when_resolution_raises(self):
        before = list(sys.path)
        with mock.patch(f"{__name__}._loader_failure", side_effect=RuntimeError("raised")):
            with self.assertRaises(RuntimeError):
                resolve_id(self.root, "tests.fx_marker.TestA.test_one")
        self.assertEqual(list(sys.path), before)
        self.assertFalse([n for n in sys.modules if n.startswith("tests.fx_")])

    def test_search_path_is_restored_when_resolution_changes_it(self):
        modules = {"fx_mutates": "import sys\nsys.path.insert(0, '/nonexistent-extra')\n"}
        root = make_root(self, modules=modules)
        before = list(sys.path)
        resolve_id(root, "tests.fx_mutates")
        self.assertEqual(list(sys.path), before)

    def test_root_is_at_the_front_of_the_search_path_only_for_the_duration_of_the_call(self):
        seen = []

        def capture(test_id):
            seen.append(sys.path[0])
            return None

        for root in (self.root, REPO_ROOT):
            with self.subTest(root=str(root)):
                seen.clear()
                before = list(sys.path)
                with mock.patch(f"{__name__}._loader_failure", side_effect=capture):
                    resolve_id(root, "tests")
                self.assertEqual(seen, [str(root)])
                self.assertEqual(list(sys.path), before)

    def test_syntax_gate_failures_never_touch_the_search_path_or_the_module_cache(self):
        _RecordingList.mutations = 0
        with mock.patch.object(sys, "path", new=_RecordingList(sys.path)):
            resolve_id(self.root, "not.a.canonical.id")
        self.assertEqual(_RecordingList.mutations, 0)

    def test_fixture_resolutions_leave_no_fixture_module_in_the_module_cache(self):
        before = {n: id(m) for n, m in sys.modules.items() if n == "tests" or n.startswith("tests.")}
        for test_id in self.IDS:
            resolve_id(self.root, test_id)
        after = {n: id(m) for n, m in sys.modules.items() if n == "tests" or n.startswith("tests.")}
        self.assertEqual(after, before)
        for name, module in list(sys.modules.items()):
            file = getattr(module, "__file__", None)
            self.assertFalse(file and str(file).startswith(str(self.root)), f"{name} from the fixture root")

    def test_real_modules_cached_before_a_fixture_resolution_are_restored_afterwards(self):
        with real_tests_modules_set_aside():
            self.assertIsNone(resolve_id(REPO_ROOT, "tests.test_tests_yaml_id_resolution"))
            real_tests = sys.modules["tests"]
            real_module = sys.modules["tests.test_tests_yaml_id_resolution"]
            self.assertIsNone(resolve_id(self.root, "tests.fx_marker.TestA.test_one"))
            self.assertIs(sys.modules["tests"], real_tests)
            self.assertIs(sys.modules["tests.test_tests_yaml_id_resolution"], real_module)
            self.assertNotIn("tests.fx_marker", sys.modules)

    def test_fixture_outcomes_are_the_same_whether_or_not_the_real_repository_tests_ran_first(self):
        ids = ("tests.fx_marker.TestA.test_one", "tests.test_tests_yaml_id_resolution", "tests.fx_marker.Nope")

        def outcomes():
            return {i: resolve_id(self.root, i) for i in ids}

        with real_tests_modules_set_aside():
            first = outcomes()
            self.assertIsNone(resolve_id(REPO_ROOT, "tests.test_tests_yaml_id_resolution"))
            self.assertIsNotNone(resolve_id(REPO_ROOT, "tests.fx_marker"))
            second = outcomes()
        self.assertEqual(first, second)
        self.assertIsNone(first["tests.fx_marker.TestA.test_one"])
        self.assertIn("attribute not found", first["tests.test_tests_yaml_id_resolution"])

    def test_real_repository_outcomes_are_the_same_after_fixture_resolutions(self):
        with real_tests_modules_set_aside():
            first = resolve_id(REPO_ROOT, "tests.test_tests_yaml_id_resolution")
            resolve_id(self.root, "tests.fx_marker")
            second = resolve_id(REPO_ROOT, "tests.test_tests_yaml_id_resolution")
        self.assertEqual((first, second), (None, None))

    def test_a_fixture_package_never_sees_the_real_tests_package(self):
        reason = resolve_id(self.root, "tests.test_tests_yaml_id_resolution")
        self.assertIn("attribute not found", reason)


class _RecordingList(list):
    """A list that counts mutations, standing in for `sys.path`."""

    mutations = 0

    def _count(name):
        original = getattr(list, name)

        def method(self, *args, **kwargs):
            type(self).mutations += 1
            return original(self, *args, **kwargs)

        return method

    insert = _count("insert")
    append = _count("append")
    remove = _count("remove")
    pop = _count("pop")
    __setitem__ = _count("__setitem__")
    __delitem__ = _count("__delitem__")
    extend = _count("extend")


# --- AC-7: one test per record, a new failure shows up -----------------------


class TestPerRecordTests(unittest.TestCase):
    """AC-7 (FR9, TS-8)."""

    def test_every_record_yields_its_own_deterministic_unique_test_name(self):
        records = [
            "test-docs/a/task0001.tests.yaml",
            "test-docs/a/task0002.tests.yaml",
            "test-docs/b/task0001.tests.yaml",
            "test-docs/a/deeper/task0001.tests.yaml",
        ]
        names = record_test_names(records)
        self.assertEqual(len(names), len(records))
        self.assertEqual(len(set(names)), len(records))
        self.assertEqual(names, record_test_names(list(records)))
        for name, rel in zip(names, records):
            self.assertTrue(name.isidentifier(), name)
            self.assertTrue(name.startswith("test"), name)
            self.assertIn(re.sub(r"[^0-9A-Za-z]", "_", rel), name)

    def test_names_that_collide_after_sanitising_are_told_apart_deterministically(self):
        records = [
            "test-docs/a-b/task0001.tests.yaml",
            "test-docs/a_b/task0001.tests.yaml",
            "test-docs/a.b/task0001.tests.yaml",
            "test-docs/other/task0001.tests.yaml",
        ]
        names = record_test_names(records)
        self.assertEqual(len(set(names)), len(records), names)
        self.assertEqual(names, record_test_names(records))
        self.assertEqual(names, record_test_names(records[::-1])[::-1])
        for name in names:
            self.assertTrue(name.isidentifier(), name)

    def test_a_name_does_not_change_when_an_unrelated_record_is_added(self):
        records = ["test-docs/a/task0001.tests.yaml", "test-docs/b/task0001.tests.yaml"]
        before = dict(zip(records, record_test_names(records)))
        more = sorted(records + ["test-docs/c/task0001.tests.yaml"])
        after = dict(zip(more, record_test_names(more)))
        for rel in records:
            self.assertEqual(before[rel], after[rel])

    def test_non_ascii_paths_still_give_valid_unique_identifiers(self):
        records = ["test-docs/日本/task0001.tests.yaml", "test-docs/中国/task0001.tests.yaml"]
        names = record_test_names(records)
        self.assertEqual(len(set(names)), 2, names)
        for name in names:
            self.assertTrue(name.isidentifier(), name)
            self.assertTrue(name.isascii(), name)

    def test_the_generated_class_holds_one_test_per_record_of_the_root(self):
        root = make_root(
            self,
            records={
                "test-docs/a/task0001.tests.yaml": simple_record({"AC-1": []}),
                "test-docs/a/task0002.tests.yaml": simple_record({"AC-1": []}),
                "test-docs/b/task0001.tests.yaml": simple_record({"AC-1": []}),
            },
        )
        test_class = make_record_test_class(root)
        loaded = unittest.TestLoader().getTestCaseNames(test_class)
        self.assertEqual(sorted(loaded), sorted(record_test_names(enumerate_records(root))))
        result = run_generated(test_class)
        self.assertEqual((result.testsRun, result.wasSuccessful()), (3, True))

    def test_a_new_invalid_id_in_a_second_record_adds_exactly_that_records_test_to_the_failed_names(self):
        first, second = "test-docs/a/task0001.tests.yaml", "test-docs/b/task0001.tests.yaml"
        valid = ["tests.fx_marker.TestA.test_one"]
        root, _ = marker_root(
            self,
            records={
                first: simple_record({"AC-1": valid + ["tests.no_such.A.b"]}),
                second: simple_record({"AC-1": valid}),
            },
        )
        names = dict(zip(enumerate_records(root), record_test_names(enumerate_records(root))))
        before = set(failure_texts(run_generated(make_record_test_class(root))))
        self.assertEqual(before, {names[first]})
        (root / second).write_text(
            simple_record({"AC-1": valid + ["tests.fx_marker.NoSuchClass"]}), encoding="utf-8"
        )
        after = set(failure_texts(run_generated(make_record_test_class(root))))
        self.assertEqual(after - before, {names[second]})
        self.assertEqual(before - after, set())

    def test_each_failing_record_fails_in_its_own_test_with_its_own_message(self):
        root = make_root(
            self,
            records={
                "test-docs/a/task0001.tests.yaml": simple_record({"AC-1": ["tests.no_such.A.b"]}),
                "test-docs/b/task0001.tests.yaml": simple_record({"AC-9": ["tests.no_such.C.d"]}),
            },
        )
        texts = failure_texts(run_generated(make_record_test_class(root)))
        self.assertEqual(len(texts), 2)
        by_record = {}
        for text in texts.values():
            rel = [r for r in enumerate_records(root) if r in text]
            self.assertEqual(len(rel), 1, text)
            by_record[rel[0]] = text
        self.assertIn("tests.no_such.A.b", by_record["test-docs/a/task0001.tests.yaml"])
        self.assertNotIn("tests.no_such.C.d", by_record["test-docs/a/task0001.tests.yaml"])
        self.assertIn("tests.no_such.C.d", by_record["test-docs/b/task0001.tests.yaml"])

    def test_the_real_repository_class_has_one_test_per_real_record(self):
        names = unittest.TestLoader().getTestCaseNames(TestRecordResolution)
        self.assertEqual(sorted(names), sorted(record_test_names(enumerate_records(REPO_ROOT))))


# --- AC-8: standard library only, collected by the normal run ----------------


class TestModuleSelfInspection(unittest.TestCase):
    """AC-8 (NFR1, TS-10)."""

    def test_the_module_imports_only_standard_library_top_level_modules(self):
        source = Path(__file__).read_text(encoding="utf-8")
        imported = imported_top_level_modules(source)
        self.assertTrue(imported)
        self.assertEqual([m for m in imported if m not in sys.stdlib_module_names], [])

    def test_no_repository_or_test_module_is_imported(self):
        imported = imported_top_level_modules(Path(__file__).read_text(encoding="utf-8"))
        self.assertEqual([m for m in imported if m == "tests" or m.startswith("test_")], [])
        self.assertEqual([m for m in imported if m.startswith(".")], [])

    def test_the_inspection_reports_third_party_repository_and_relative_imports(self):
        source = "import os\nimport yaml\nfrom tests import test_x\nfrom . import y\nfrom .z import w\nimport os.path\n"
        self.assertEqual(
            imported_top_level_modules(source), ["os", "yaml", "tests", ".", ".z", "os"]
        )

    def test_the_inspection_sees_imports_inside_functions(self):
        source = "def f():\n    import yaml\n    from test_other import g\n"
        self.assertEqual(imported_top_level_modules(source), ["yaml", "test_other"])


class TestNormalRunCollection(unittest.TestCase):
    """AC-8 (NFR2, TS-10): `python3 -m unittest discover -s tests` collects the
    per-record tests and the zero-record guard with no registration."""

    def test_discovery_of_the_tests_directory_collects_the_record_tests_and_the_guard(self):
        tests_dir = Path(__file__).resolve().parent
        saved_path = list(sys.path)
        try:
            suite = unittest.TestLoader().discover(str(tests_dir), pattern=Path(__file__).name)
        finally:
            sys.path[:] = saved_path
        ids = []

        def walk(item):
            if isinstance(item, unittest.TestSuite):
                for child in item:
                    walk(child)
            else:
                ids.append(item.id())

        walk(suite)
        self.assertFalse([i for i in ids if "_FailedTest" in i], ids[:5])
        record_ids = [i for i in ids if ".TestRecordResolution." in i]
        guard_ids = [i for i in ids if ".TestZeroRecordGuard." in i]
        self.assertEqual(len(record_ids), len(enumerate_records(REPO_ROOT)))
        self.assertTrue(record_ids)
        self.assertEqual(len(guard_ids), 1)

    def test_discovery_of_the_tests_directory_collects_the_scan_error_test_with_no_registration(self):
        """AC-6 (FR3, NFR2): the module-level scan-error class is found by discovery."""
        tests_dir = Path(__file__).resolve().parent
        saved_path = list(sys.path)
        try:
            suite = unittest.TestLoader().discover(str(tests_dir), pattern=Path(__file__).name)
        finally:
            sys.path[:] = saved_path
        ids = []

        def walk(item):
            if isinstance(item, unittest.TestSuite):
                for child in item:
                    walk(child)
            else:
                ids.append(item.id())

        walk(suite)
        self.assertFalse([i for i in ids if "_FailedTest" in i], ids[:5])
        self.assertEqual(len([i for i in ids if ".TestScanErrors." in i]), 1)

    def test_module_import_performs_enumeration_only(self):
        source = Path(__file__).read_text(encoding="utf-8")
        tree = ast.parse(source)
        top_level_calls = [
            n.value.func.id
            for n in tree.body
            if isinstance(n, ast.Assign) and isinstance(n.value, ast.Call) and isinstance(n.value.func, ast.Name)
        ]
        self.assertIn("make_record_test_class", top_level_calls)
        for name in top_level_calls:
            self.assertNotIn(name, ("extract_record", "extract_text", "resolve_id", "check_record"))


if __name__ == "__main__":
    unittest.main()
