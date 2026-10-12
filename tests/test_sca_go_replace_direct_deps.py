"""Tests for sca-go-replace-direct-deps task0001: a go.mod `replace` of a
non-indirect require adds the replacement MODULE to the Go direct set of
`scan-dependencies.py`.

Covers the task's Acceptance Criteria
(feature-docs/sca-go-replace-direct-deps/tasks/task0001.md):

- AC-1 (TS1): single-line replace -> the replacement's advisory is a finding
  or is counted under `go_severity_undetermined`.
- AC-2 (TS2): the same for `replace ( ... )` blocks.
- AC-3 (TS3, TS12; TM-2): directory-path replacements add nothing, and no
  file is read from a replace directive's path.
- AC-4 (TS4, TS5): indirect / absent / version-mismatched sources, and the
  versioned-over-unversioned selection rule.
- AC-5 (TS6, TS7; TM-1): parser-level direct set, edge forms, malformed lines.
- AC-6 (TS11; TM-3): output safety for the non-contributing cases.
- AC-7 (TS9): the three documentation sites describe the new behaviour.
- AC-8 (TS8, TS10): test hygiene.

Per Test Notes: no real go, govulncheck or network. The govulncheck stub
harness, the stream builders and the capture-derived OSV objects are the ones
of tests/test_sca_go_govulncheck_real_output.py. That module is loaded by file
path under a distinct name and only its helpers are used here, so discovery
never collects its test cases a second time from this module and the module
itself stays untouched. This module imports only the standard library.
"""

import ast
import builtins
import importlib.util
import json
import os
import re
import sys
import unittest
from pathlib import Path
from unittest import mock

TESTS_DIR = Path(__file__).resolve().parent

_HELPERS_PATH = TESTS_DIR / "test_sca_go_govulncheck_real_output.py"
_helpers_spec = importlib.util.spec_from_file_location(
    "_sca_go_govulncheck_real_output_helpers", _HELPERS_PATH
)
helpers = importlib.util.module_from_spec(_helpers_spec)
_helpers_spec.loader.exec_module(helpers)

SCAN = helpers.SCAN
SCRIPT_PATH = helpers.SCRIPT_PATH

# AC-1 / AC-2 names, exactly as the criteria state them. The advisory objects
# of the capture are on golang.org/x/text, so the replacement is that module.
SOURCE = "example.org/text"
TARGET = helpers.VULN_MODULE  # golang.org/x/text
REQUIRE_SOURCE = f"require {SOURCE} v0.3.6"

# Marker-bearing names for the output-safety cases (AC-6): the marker is in
# the source and the replacement side of every replace directive.
MARK = "zz-marker-5e1f"
M_SRC = f"example.org/{MARK}-src"
M_DST = f"golang.org/x/{MARK}-dst"
M_MID = f"example.org/{MARK}-mid"
M_OTHER = f"example.org/{MARK}-other"

HEADER = "module example.com/vulnprobe\n\ngo 1.20\n\n"


def gomod(*body):
    """A go.mod holding `body` lines (each line may itself span lines)."""
    return HEADER + "".join(line + "\n" for line in body)


def replace_lines(form, *entries):
    """The replace directive(s) holding `entries` in the given form: one
    single-line directive per entry, or one block holding all of them."""
    if form == "single-line":
        return "\n".join(f"replace {entry}" for entry in entries)
    return "replace (\n" + "".join(f"\t{entry}\n" for entry in entries) + ")"


FORMS = ("single-line", "block")


def module_stream(module, determined):
    """Config object, one advisory on `module`, its module-level finding. The
    advisory has a critical CVSS v3 vector when `determined`, none otherwise."""
    severity = [helpers.cvss(helpers.V31_CRITICAL)] if determined else None
    return helpers.severity_stream(severity, module=module)


# The directory-path forms of FR3, with a placeholder for the directory name.
DIRECTORY_FORMS = (
    "./{n}", "../{n}", "/{n}", ".\\{n}", "..\\{n}", "\\{n}", "C:\\{n}",
    ".", "..", "./{n} v1.0.0",
)


def directory_path_cases(source, name):
    """`(label, go_mod, advisory module)`: the source required directly and
    replaced by each directory-path form, in both replace forms."""
    cases = []
    for template in DIRECTORY_FORMS:
        target = template.format(n=name)
        module = target.partition(" ")[0]
        for form in FORMS:
            cases.append((
                f"{target} ({form})",
                gomod(f"require {source} v0.3.6", replace_lines(form, f"{source} => {target}")),
                module,
            ))
    return cases


def selection_cases(source, target, middle, other):
    """`(label, go_mod, advisory module)` for AC-4: the advisory is on a
    module that must NOT be added."""
    req = f"require {source} v0.3.6"
    cases = []
    for form in FORMS:
        cases.extend([
            (
                f"indirect source ({form})",
                gomod(f"require {source} v0.3.6 // indirect",
                      replace_lines(form, f"{source} => {target} v0.3.6")),
                target,
            ),
            (
                f"no require of the source ({form})",
                gomod(f"require {other} v1.0.0",
                      replace_lines(form, f"{source} => {target} v0.3.6")),
                target,
            ),
            (
                f"no require at all ({form})",
                gomod(replace_lines(form, f"{source} => {target} v0.3.6")),
                target,
            ),
            (
                f"versioned replace with another version ({form})",
                gomod(req, replace_lines(form, f"{source} v0.3.5 => {target} v0.3.6")),
                target,
            ),
            (
                f"unversioned module replace loses to the matching versioned one ({form})",
                gomod(req, replace_lines(form, f"{source} v0.3.6 => {middle} v0.3.6",
                                         f"{source} => {target} v0.3.6")),
                target,
            ),
            (
                f"matching versioned local replace, no fallback ({form})",
                gomod(req, replace_lines(form, f"{source} v0.3.6 => ./local",
                                         f"{source} => {target} v0.3.6")),
                target,
            ),
            (
                f"matching versioned directory path with a version, no fallback ({form})",
                gomod(req, replace_lines(form, f"{source} v0.3.6 => ./local v1.0.0",
                                         f"{source} => {target} v0.3.6")),
                target,
            ),
            (
                f"chained replacement ({form})",
                gomod(req, replace_lines(form, f"{source} => {middle} v0.3.6",
                                         f"{middle} => {target} v0.3.6")),
                target,
            ),
        ])
    return cases


# TM-1: replace lines that are not `src [v] => dst [v]`. Each one is written
# in the single-line and in the block form.
def malformed_entries(source, target):
    return {
        "glued arrow on both sides": f"{source}=>{target} v0.3.6",
        "glued arrow on the right": f"{source} =>{target} v0.3.6",
        "glued arrow on the left": f"{source}=> {target} v0.3.6",
        "glued arrow after a source version": f"{source} v0.3.6=>{target} v0.3.6",
        "missing right side": f"{source} =>",
        "missing right side after a source version": f"{source} v0.3.6 =>",
        "missing left side": f"=> {target} v0.3.6",
        "no arrow": f"{source} {target} v0.3.6",
        "extra token after the replacement": f"{source} => {target} v0.3.6 extra",
        "extra token before the arrow": f"{source} v0.3.6 extra => {target} v0.3.6",
        "doubled arrow": f"{source} => => {target} v0.3.6",
        "doubled arrow with the replacement path missing": f"{source} => => {target}",
        "doubled arrow after a source version": f"{source} v0.3.6 => => {target}",
        "second arrow after the replacement": f"{source} => {target} => v0.3.6",
        "unbalanced opening quote": f'{source} => "{target} v0.3.6',
        "unbalanced closing quote": f'{source} => {target} "',
        "stray opening parenthesis": f"{source} => {target} (",
        "parentheses around the entry": f"( {source} => {target} v0.3.6 )",
        "empty quoted replacement path": f'{source} => "" v0.3.6',
        "arrow only": "=>",
        "nothing": "",
    }


def malformed_cases(source, target):
    cases = []
    for label, entry in malformed_entries(source, target).items():
        for form in FORMS:
            go_mod = gomod(f"require {source} v0.3.6", replace_lines(form, entry))
            cases.append((f"{label} ({form})", go_mod, target))
    return cases


class ReplaceCase(helpers.GoScanCase):
    """The harness of the Go govulncheck tests plus replace-specific asserts."""

    def run_module(self, go_mod, module, determined):
        return self.replay(module_stream(module, determined), go_mod=go_mod)

    def assertAdded(self, go_mod, module, severity="critical"):
        """The advisory on `module` is a finding of `module` when it has a
        CVSS v3 vector, and is counted when it has none."""
        result = self.run_module(go_mod, module, True)
        finding = self.single_finding(result)
        self.assertEqual(finding["severity"], severity)
        self.assertEqual(SCAN.recover_package_advisory(finding)[0], module)
        self.assertEqual(finding["file"], "go.mod")
        self.assertConforms(result)
        counted = self.run_module(go_mod, module, False)
        self.assertCompletedClean(counted, undetermined=1)

    def assertNotAdded(self, go_mod, module):
        """The advisory on `module` is neither a finding nor counted."""
        self.assertCompletedClean(self.run_module(go_mod, module, True))
        self.assertCompletedClean(self.run_module(go_mod, module, False))


# ---------------------------------------------------------------------------
# AC-1 (FR1, FR2, FR4; TS1): the single-line replace.
# ---------------------------------------------------------------------------

class TestSingleLineReplace(ReplaceCase):
    GO_MOD = gomod(REQUIRE_SOURCE, f"replace {SOURCE} => {TARGET} v0.3.6")

    def test_ac1_the_replacement_module_is_direct_finding_and_count(self):
        self.assertAdded(self.GO_MOD, TARGET)

    def test_ac1_a_high_vector_gives_a_high_finding_on_the_replacement(self):
        stream = helpers.severity_stream([helpers.cvss(helpers.V31_HIGH)], module=TARGET)
        finding = self.single_finding(self.replay(stream, go_mod=self.GO_MOD))
        self.assertEqual(finding["severity"], "high")
        self.assertEqual(SCAN.recover_package_advisory(finding)[0], TARGET)

    def test_ac1_a_vector_below_high_gives_no_finding_and_no_count(self):
        stream = helpers.severity_stream([helpers.cvss(helpers.V31_MEDIUM)], module=TARGET)
        self.assertCompletedClean(self.replay(stream, go_mod=self.GO_MOD))

    def test_ac1_the_original_require_path_stays_direct(self):
        self.assertAdded(self.GO_MOD, SOURCE)

    def test_ac1_without_the_replace_the_replacement_module_is_not_direct(self):
        self.assertNotAdded(gomod(REQUIRE_SOURCE), TARGET)

    def test_ac1_a_versioned_source_equal_to_the_require_version_adds_the_replacement(self):
        self.assertAdded(gomod(REQUIRE_SOURCE, f"replace {SOURCE} v0.3.6 => {TARGET} v0.3.6"), TARGET)

    def test_ac1_the_replacement_version_does_not_have_to_equal_the_require_version(self):
        self.assertAdded(gomod(REQUIRE_SOURCE, f"replace {SOURCE} => {TARGET} v0.3.7"), TARGET)

    def test_ac1_a_replace_before_the_require_is_applied_the_same_way(self):
        self.assertAdded(gomod(f"replace {SOURCE} => {TARGET} v0.3.6", REQUIRE_SOURCE), TARGET)

    def test_ac1_the_replace_beside_other_directives_and_a_block_require(self):
        go_mod = gomod(
            "require (\n\texample.org/a v1.0.0\n" f"\t{SOURCE} v0.3.6\n" "\texample.org/b v1.0.0 // indirect\n)",
            "exclude example.org/c v1.0.0",
            f"replace {SOURCE} => {TARGET} v0.3.6",
            "retract v0.0.1",
        )
        self.assertAdded(go_mod, TARGET)

    def test_ac1_a_go_sum_target_takes_the_replace_from_the_sibling_go_mod(self):
        self.write("go.mod", self.GO_MOD)
        self.write("go.sum", f"{TARGET} v0.3.6 h1:x\n")
        self.install_go(module_stream(TARGET, True))
        finding = self.single_finding(self.scan(["go.sum"]))
        self.assertEqual(finding["file"], "go.sum")
        self.assertEqual(SCAN.recover_package_advisory(finding)[0], TARGET)


# ---------------------------------------------------------------------------
# AC-2 (FR1, FR2; TS2): the replace block.
# ---------------------------------------------------------------------------

class TestBlockReplace(ReplaceCase):
    def test_ac2_a_block_holding_only_the_replace(self):
        go_mod = gomod(REQUIRE_SOURCE, f"replace (\n\t{SOURCE} => {TARGET} v0.3.6\n)")
        self.assertAdded(go_mod, TARGET)

    def test_ac2_a_block_with_other_entries_and_comment_lines(self):
        go_mod = gomod(
            REQUIRE_SOURCE,
            "replace (\n"
            "\t// forks pinned for the audit\n"
            "\texample.org/other v1.0.0 => example.org/other-fork v1.0.1 // noted\n"
            "\n"
            f"\t{SOURCE} => {TARGET} v0.3.6 // the one under test\n"
            "\texample.org/third => ./third\n"
            "\t// ) a comment that mentions a closing parenthesis\n"
            ")",
        )
        self.assertAdded(go_mod, TARGET)

    def test_ac2_a_block_with_a_versioned_source(self):
        go_mod = gomod(REQUIRE_SOURCE, f"replace (\n\t{SOURCE} v0.3.6 => {TARGET} v0.3.6\n)")
        self.assertAdded(go_mod, TARGET)

    def test_ac2_the_block_before_the_require(self):
        go_mod = gomod(f"replace (\n\t{SOURCE} => {TARGET} v0.3.6\n)", REQUIRE_SOURCE)
        self.assertAdded(go_mod, TARGET)

    def test_ac2_the_require_in_a_block_and_the_replace_in_a_block(self):
        go_mod = gomod(
            f"require (\n\t{SOURCE} v0.3.6\n)", f"replace (\n\t{SOURCE} => {TARGET} v0.3.6\n)"
        )
        self.assertAdded(go_mod, TARGET)

    def test_ac2_the_original_require_path_stays_direct(self):
        go_mod = gomod(REQUIRE_SOURCE, f"replace (\n\t{SOURCE} => {TARGET} v0.3.6\n)")
        self.assertAdded(go_mod, SOURCE)

    def test_ac2_an_entry_after_a_closed_block_is_not_a_block_entry(self):
        go_mod = gomod(
            REQUIRE_SOURCE,
            "replace (\n\texample.org/other => example.org/fork v1.0.0\n)",
            f"{SOURCE} => {TARGET} v0.3.6",
        )
        self.assertNotAdded(go_mod, TARGET)

    def test_ac2_entries_of_another_block_kind_are_not_replace_entries(self):
        go_mod = gomod(
            REQUIRE_SOURCE, f"exclude (\n\t{SOURCE} => {TARGET} v0.3.6\n)",
        )
        self.assertNotAdded(go_mod, TARGET)

    def test_ac2_the_parenthesis_glued_to_the_keyword(self):
        go_mod = gomod(REQUIRE_SOURCE, f"replace(\n\t{SOURCE} => {TARGET} v0.3.6\n)")
        self.assertAdded(go_mod, TARGET)


# ---------------------------------------------------------------------------
# AC-3 (FR3, NFR3; TS3, TS12; TM-2): directory-path replacements add nothing.
# ---------------------------------------------------------------------------

class TestDirectoryPathReplacements(ReplaceCase):
    def test_ac3_each_directory_path_form_adds_nothing(self):
        for label, go_mod, module in directory_path_cases(SOURCE, "x"):
            with self.subTest(replacement=label):
                self.assertNotAdded(go_mod, module)

    def test_ac3_the_original_require_path_stays_direct_beside_a_local_replace(self):
        go_mod = gomod(REQUIRE_SOURCE, f"replace {SOURCE} => ./x")
        self.assertAdded(go_mod, SOURCE)

    def test_ac3_a_replacement_without_a_version_is_not_a_module_replacement(self):
        self.assertNotAdded(gomod(REQUIRE_SOURCE, f"replace {SOURCE} => {TARGET}"), TARGET)

    def test_ac3_the_parser_rule_for_directory_paths(self):
        parse = SCAN._go_mod_direct_modules
        directory_paths = (
            ".", "..", "./x", "../x", ".\\x", "..\\x", "/x", "\\x",
            "C:\\x", "c:/x", "Z:", "a:b",
        )
        for path in directory_paths:
            with self.subTest(path=path):
                go_mod = gomod(REQUIRE_SOURCE, f"replace {SOURCE} => {path} v1.0.0")
                self.assertEqual(parse(go_mod), {SOURCE})
        module_paths = (
            TARGET, ".hidden.example/x", "...", "x.org/./y", "example.org:8080/x",
            "1:x", "\u00e9:x",
        )
        for path in module_paths:
            with self.subTest(path=path):
                go_mod = gomod(REQUIRE_SOURCE, f"replace {SOURCE} => {path} v1.0.0")
                self.assertEqual(parse(go_mod), {SOURCE, path})

    def scan_recording_opens(self):
        """`(result, paths)`: the scan of go.mod with every path passed to
        `open` during it."""
        real_open = builtins.open
        opened = []

        def recording_open(file, *args, **kwargs):
            opened.append(os.fspath(file) if isinstance(file, (str, os.PathLike)) else file)
            return real_open(file, *args, **kwargs)

        with mock.patch("builtins.open", recording_open):
            result = self.scan(["go.mod"])
        return result, [p for p in opened if isinstance(p, str)]

    def test_ac3_tm2_a_local_replace_to_an_outside_directory_reads_nothing_from_it(self):
        # The outside directory is a sibling of the project root and holds its
        # own go.mod requiring module M. M's advisory must have no effect, and
        # nothing may be opened below the outside directory.
        outside_module = "example.org/outside-module"
        self.write("go.mod", gomod(f"require {outside_module} v1.0.0"), base=self.outside)
        for label, target in (
            ("relative", "../outside"),
            ("relative with a trailing slash", "../outside/"),
            ("absolute", str(self.outside)),
        ):
            for form in FORMS:
                for determined in (True, False):
                    with self.subTest(replacement=label, form=form, determined=determined):
                        go_mod = gomod(REQUIRE_SOURCE, replace_lines(form, f"{SOURCE} => {target}"))
                        self.go_project(go_mod)
                        self.install_go(module_stream(outside_module, determined))
                        result, opened = self.scan_recording_opens()
                        self.assertCompletedClean(result)
                        self.assertEqual([p for p in opened if str(self.outside) in p], [])

    def test_ac3_tm2_the_recording_would_see_a_read_of_the_outside_go_mod(self):
        # Guards the recording above: a read of the outside go.mod, made the
        # way the script reads go.mod, does show up in the recorded paths.
        self.write("go.mod", gomod(REQUIRE_SOURCE))
        outside_go_mod = self.write("go.mod", gomod(), base=self.outside)
        self.install_go(module_stream(SOURCE, True))
        real_open = builtins.open
        opened = []

        def recording_open(file, *args, **kwargs):
            opened.append(os.fspath(file) if isinstance(file, (str, os.PathLike)) else file)
            return real_open(file, *args, **kwargs)

        with mock.patch("builtins.open", recording_open):
            with builtins.open(outside_go_mod, "rb"):
                pass
        self.assertEqual(opened, [str(outside_go_mod)])


# ---------------------------------------------------------------------------
# AC-4 (FR2, FR3, FR5; TS4, TS5): which replaces apply.
# ---------------------------------------------------------------------------

class TestSelectionRules(ReplaceCase):
    def test_ac4_nothing_is_added_when_the_replace_does_not_apply(self):
        for label, go_mod, module in selection_cases(SOURCE, TARGET, "example.org/middle", "example.org/other"):
            with self.subTest(case=label):
                self.assertNotAdded(go_mod, module)

    def test_ac4_a_versioned_replace_equal_to_the_require_version_adds_its_replacement(self):
        for form in FORMS:
            with self.subTest(form=form):
                go_mod = gomod(REQUIRE_SOURCE, replace_lines(form, f"{SOURCE} v0.3.6 => {TARGET} v0.3.6"))
                self.assertAdded(go_mod, TARGET)

    def test_ac4_the_versioned_replace_wins_and_only_its_replacement_is_added(self):
        middle = "example.org/middle"
        for form in FORMS:
            for order in ("versioned first", "unversioned first"):
                entries = [f"{SOURCE} v0.3.6 => {middle} v0.3.6", f"{SOURCE} => {TARGET} v0.3.6"]
                if order == "unversioned first":
                    entries.reverse()
                with self.subTest(form=form, order=order):
                    go_mod = gomod(REQUIRE_SOURCE, replace_lines(form, *entries))
                    self.assertAdded(go_mod, middle)
                    self.assertNotAdded(go_mod, TARGET)

    def test_ac4_an_unversioned_replace_applies_when_the_versioned_one_does_not_match(self):
        go_mod = gomod(
            REQUIRE_SOURCE,
            f"replace {SOURCE} v0.3.5 => example.org/middle v0.3.5",
            f"replace {SOURCE} => {TARGET} v0.3.6",
        )
        self.assertAdded(go_mod, TARGET)
        self.assertNotAdded(go_mod, "example.org/middle")

    def test_ac4_the_original_require_path_stays_direct_when_nothing_is_added(self):
        go_mod = gomod(REQUIRE_SOURCE, f"replace {SOURCE} v0.3.5 => {TARGET} v0.3.6")
        self.assertAdded(go_mod, SOURCE)

    def test_ac4_an_indirect_require_marker_with_words_still_blocks_the_replace(self):
        go_mod = gomod(
            f"require {SOURCE} v0.3.6 // indirect; used by foo", f"replace {SOURCE} => {TARGET} v0.3.6"
        )
        self.assertNotAdded(go_mod, TARGET)

    def test_ac4_a_comment_that_only_mentions_indirect_leaves_the_require_direct(self):
        go_mod = gomod(
            f"require {SOURCE} v0.3.6 // not indirect", f"replace {SOURCE} => {TARGET} v0.3.6"
        )
        self.assertAdded(go_mod, TARGET)


# ---------------------------------------------------------------------------
# AC-5 (FR1, FR4, FR5; TS6, TS7; TM-1): the parser-level direct set.
# ---------------------------------------------------------------------------

parse = SCAN._go_mod_direct_modules


class TestParserDirectSet(unittest.TestCase):
    def test_ac5_the_direct_set_holds_the_original_path_and_the_replacement_path(self):
        for form in FORMS:
            with self.subTest(form=form):
                go_mod = gomod(REQUIRE_SOURCE, replace_lines(form, f"{SOURCE} => {TARGET} v0.3.6"))
                self.assertEqual(parse(go_mod), {SOURCE, TARGET})

    def test_ac5_the_set_is_the_same_when_the_replace_precedes_the_require(self):
        for form in FORMS:
            for require in (REQUIRE_SOURCE, f"require (\n\t{SOURCE} v0.3.6\n)"):
                with self.subTest(form=form, require=require):
                    replace = replace_lines(form, f"{SOURCE} => {TARGET} v0.3.6")
                    self.assertEqual(
                        parse(gomod(replace, require)), parse(gomod(require, replace))
                    )
                    self.assertEqual(parse(gomod(replace, require)), {SOURCE, TARGET})

    def test_ac5_quoted_paths_on_both_sides(self):
        cases = {
            "double-quoted": f'"{SOURCE}" => "{TARGET}" v0.3.6',
            "back-quoted": f"`{SOURCE}` => `{TARGET}` v0.3.6",
            "mixed": f'"{SOURCE}" v0.3.6 => `{TARGET}` v0.3.6',
        }
        for label, entry in cases.items():
            for form in FORMS:
                with self.subTest(quoting=label, form=form):
                    go_mod = gomod(REQUIRE_SOURCE, replace_lines(form, entry))
                    self.assertEqual(parse(go_mod), {SOURCE, TARGET})
        quoted_require = gomod(f'require "{SOURCE}" v0.3.6', f"replace {SOURCE} => {TARGET} v0.3.6")
        self.assertEqual(parse(quoted_require), {SOURCE, TARGET})

    def test_ac5_quoted_versions_are_compared_unquoted(self):
        go_mod = gomod(f'require {SOURCE} "v0.3.6"', f'replace {SOURCE} "v0.3.6" => {TARGET} "v0.3.6"')
        self.assertEqual(parse(go_mod), {SOURCE, TARGET})

    def test_ac5_trailing_comments(self):
        for form in FORMS:
            with self.subTest(form=form):
                replace = replace_lines(form, f"{SOURCE} => {TARGET} v0.3.6 // pinned for audit")
                self.assertEqual(parse(gomod(REQUIRE_SOURCE, replace)), {SOURCE, TARGET})

    def test_ac5_a_comment_never_supplies_the_arrow_or_the_replacement(self):
        for form in FORMS:
            cases = {
                "arrow in the comment": f"{SOURCE} // => {TARGET} v0.3.6",
                "replacement in the comment": f"{SOURCE} => // {TARGET} v0.3.6",
                "full-line comment": f"// {SOURCE} => {TARGET} v0.3.6",
            }
            for label, entry in cases.items():
                with self.subTest(case=label, form=form):
                    go_mod = gomod(REQUIRE_SOURCE, replace_lines(form, entry))
                    self.assertEqual(parse(go_mod), {SOURCE})

    def test_ac5_a_comment_after_a_valid_replace_does_not_add_a_second_replacement(self):
        go_mod = gomod(REQUIRE_SOURCE, f"replace {SOURCE} => {TARGET} v0.3.6 // was => example.org/old v1.0.0")
        self.assertEqual(parse(go_mod), {SOURCE, TARGET})

    def test_ac5_crlf_line_endings(self):
        for form in FORMS:
            for require in (REQUIRE_SOURCE, f"require (\n\t{SOURCE} v0.3.6\n)"):
                with self.subTest(form=form, require=require):
                    go_mod = gomod(require, replace_lines(form, f"{SOURCE} => {TARGET} v0.3.6"))
                    self.assertEqual(parse(go_mod.replace("\n", "\r\n")), {SOURCE, TARGET})

    def test_ac5_a_chained_replacement_adds_only_the_first_replacement(self):
        for form in FORMS:
            with self.subTest(form=form):
                replace = replace_lines(
                    form, f"{SOURCE} => {M_MID} v0.3.6", f"{M_MID} => {TARGET} v0.3.6"
                )
                self.assertEqual(parse(gomod(REQUIRE_SOURCE, replace)), {SOURCE, M_MID})

    def test_ac5_a_directly_required_replacement_is_replaced_in_its_own_right(self):
        go_mod = gomod(
            REQUIRE_SOURCE,
            f"require {M_MID} v1.0.0",
            f"replace {SOURCE} => {M_MID} v0.3.6",
            f"replace {M_MID} => {TARGET} v0.3.6",
        )
        self.assertEqual(parse(go_mod), {SOURCE, M_MID, TARGET})

    def test_ac5_the_selection_is_made_per_require_entry(self):
        go_mod = gomod(
            f"require {SOURCE} v1.0.0",
            f"require {SOURCE} v2.0.0",
            f"replace {SOURCE} v1.0.0 => example.org/for-v1 v1.0.0",
            f"replace {SOURCE} => example.org/for-others v1.0.0",
        )
        self.assertEqual(
            parse(go_mod), {SOURCE, "example.org/for-v1", "example.org/for-others"}
        )

    def test_ac5_only_a_non_indirect_entry_of_the_source_triggers_the_replace(self):
        go_mod = gomod(
            f"require {SOURCE} v1.0.0 // indirect",
            f"require {SOURCE} v2.0.0",
            f"replace {SOURCE} v1.0.0 => example.org/for-v1 v1.0.0",
        )
        self.assertEqual(parse(go_mod), {SOURCE})

    def test_ac5_replace_lines_do_not_disturb_the_require_derived_set(self):
        go_mod = gomod(
            "require (\n\texample.org/a v1.0.0\n\texample.org/b v1.0.0 // indirect\n)",
            "replace example.org/a => example.org/a-fork v1.0.0",
            "replace example.org/b => example.org/b-fork v1.0.0",
            "exclude example.org/c v1.0.0",
        )
        self.assertEqual(parse(go_mod), {"example.org/a", "example.org/a-fork"})

    def test_ac5_tm1_malformed_replace_lines_contribute_nothing(self):
        for label, entry in malformed_entries(SOURCE, TARGET).items():
            for form in FORMS:
                with self.subTest(case=label, form=form):
                    go_mod = gomod(REQUIRE_SOURCE, replace_lines(form, entry))
                    self.assertEqual(parse(go_mod), {SOURCE})

    def test_ac5_tm1_a_malformed_line_does_not_disturb_the_valid_lines_around_it(self):
        expected = {
            SOURCE, "example.org/before", "golang.org/x/before",
            "example.org/after", "golang.org/x/after",
        }
        for label, entry in malformed_entries(SOURCE, TARGET).items():
            for form in FORMS:
                with self.subTest(case=label, form=form):
                    go_mod = gomod(
                        REQUIRE_SOURCE,
                        "require example.org/before v1.0.0",
                        "require example.org/after v1.0.0",
                        "replace example.org/before => golang.org/x/before v1.0.0",
                        replace_lines(form, entry),
                        "replace example.org/after v1.0.0 => golang.org/x/after v1.0.0",
                    )
                    self.assertEqual(parse(go_mod), expected)

    def test_ac5_tm1_a_malformed_block_entry_does_not_end_or_extend_the_block(self):
        go_mod = gomod(
            REQUIRE_SOURCE,
            f"replace (\n\t{SOURCE}=>{TARGET} v0.3.6\n\t{SOURCE} => {M_MID} v0.3.6\n)",
            f"require {M_OTHER} v1.0.0",
        )
        self.assertEqual(parse(go_mod), {SOURCE, M_MID, M_OTHER})

    def test_ac5_tm1_a_replace_keyword_alone_contributes_nothing(self):
        self.assertEqual(parse(gomod(REQUIRE_SOURCE, "replace")), {SOURCE})
        self.assertEqual(parse(gomod(REQUIRE_SOURCE, "replace (")), {SOURCE})


class TestMalformedReplaceKeepsTheGoModReadable(ReplaceCase):
    def test_ac5_tm1_a_malformed_replace_leaves_the_unit_completed_with_its_require_set(self):
        for label, go_mod, module in malformed_cases(SOURCE, TARGET):
            with self.subTest(case=label):
                # The unit stays readable: completed, not skipped, and the
                # require-derived direct set still produces its finding.
                self.assertAdded(go_mod, SOURCE)
                self.assertNotAdded(go_mod, module)


# ---------------------------------------------------------------------------
# AC-6 (NFR3; TS11; TM-3): output safety for the non-contributing cases.
# ---------------------------------------------------------------------------

class TestOutputSafety(ReplaceCase):
    def non_contributing_cases(self):
        return [
            *directory_path_cases(M_SRC, MARK + "-dir"),
            *selection_cases(M_SRC, M_DST, M_MID, M_OTHER),
            *malformed_cases(M_SRC, M_DST),
        ]

    def test_ac6_every_case_carries_the_marker_and_the_cases_are_numerous(self):
        cases = self.non_contributing_cases()
        self.assertGreater(len(cases), 60)
        for label, go_mod, _module in cases:
            with self.subTest(case=label):
                self.assertIn(MARK, go_mod)

    def test_ac6_the_result_is_completed_clean_with_known_tokens_and_no_marker(self):
        for label, go_mod, module in self.non_contributing_cases():
            with self.subTest(case=label):
                result = self.run_module(go_mod, module, True)
                self.assertFalse(result["skipped"], result)
                self.assertIsNone(result["skip_reason"])
                self.assertEqual(result["findings"], [])
                self.assertRegex(result["summary"], helpers.SUMMARY_SHAPE)
                self.assertEqual(result["summary"], helpers.scanned_summary(0))
                self.assertNotIn(MARK, json.dumps(result, sort_keys=True))

    def test_ac6_a_counted_advisory_keeps_the_note_counts_only(self):
        # Beside a replace that adds nothing, an advisory that IS counted (on
        # the directly required source) yields the existing note only.
        go_mod = gomod(f"require {M_SRC} v0.3.6", f"replace {M_SRC} => ./{MARK}-dir")
        result = self.run_module(go_mod, M_SRC, False)
        self.assertFalse(result["skipped"], result)
        self.assertIsNone(result["skip_reason"])
        self.assertEqual(result["summary"], helpers.scanned_summary(0, 1))
        self.assertNotIn(MARK, json.dumps(result, sort_keys=True))

    def test_ac6_a_contributing_replace_adds_no_note_token_and_no_path_text(self):
        go_mod = gomod(REQUIRE_SOURCE, f"replace {SOURCE} => {TARGET} v0.3.6")
        result = self.run_module(go_mod, TARGET, False)
        self.assertEqual(result["summary"], helpers.scanned_summary(0, 1))
        self.assertRegex(result["summary"], helpers.SUMMARY_SHAPE)
        self.assertIsNone(result["skip_reason"])
        for text in (SOURCE, TARGET, "replace", "=>"):
            self.assertNotIn(text, result["summary"])


# ---------------------------------------------------------------------------
# AC-7 (FR6; TS9): the three documentation sites.
# ---------------------------------------------------------------------------

def _plain(text):
    """`text` with comment markers removed and whitespace collapsed."""
    lines = [re.sub(r"^\s*#\s?", "", line) for line in text.splitlines()]
    return " ".join(" ".join(lines).split())


class TestDocumentationSites(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        source = SCRIPT_PATH.read_text(encoding="utf-8")
        match = re.search(
            r"^# -{20,}\n# Go normalization.*?\n# -{20,}\n", source, re.MULTILINE | re.DOTALL
        )
        assert match is not None, "the Go normalization section comment is missing"
        cls.sites = {
            "Go normalization section comment": _plain(match.group(0)),
            "_go_mod_direct_modules docstring": _plain(SCAN._go_mod_direct_modules.__doc__),
            "normalize_go docstring": _plain(SCAN.normalize_go.__doc__),
        }

    def test_ac7_every_site_describes_the_replace_contribution(self):
        for name, text in self.sites.items():
            with self.subTest(site=name):
                self.assertRegex(text, r"(?i)\breplace\b")
                self.assertRegex(text, r"(?i)\breplacement\b")

    def test_ac7_no_site_says_that_replace_contributes_nothing(self):
        stale = re.compile(r"(?i)\breplace\b.*\bcontribut\w*\s+nothing")
        for name, text in self.sites.items():
            for sentence in re.split(r"(?<=[.;])\s+", text):
                with self.subTest(site=name, sentence=sentence[:60]):
                    self.assertIsNone(stale.search(sentence))

    def test_ac7_the_old_require_only_wording_is_gone(self):
        doc = _plain(SCAN._go_mod_direct_modules.__doc__)
        self.assertNotIn("Only the single-line `require m v`", doc)


# ---------------------------------------------------------------------------
# AC-8 (NFR1, NFR2; TS8, TS10): test hygiene.
# ---------------------------------------------------------------------------

class TestModuleHygiene(unittest.TestCase):
    def test_ac8_this_module_imports_only_the_standard_library_and_no_network_module(self):
        tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imported.add(node.module.split(".")[0])
        self.assertEqual({m for m in imported if m not in sys.stdlib_module_names}, set())
        self.assertEqual(
            imported & {"subprocess", "socket", "urllib", "http", "ssl", "ftplib", "smtplib"}, set()
        )

    def test_ac8_discovery_collects_only_test_cases_defined_in_this_module(self):
        suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
        collected = []

        def walk(item):
            if isinstance(item, unittest.TestSuite):
                for child in item:
                    walk(child)
            else:
                collected.append(type(item))

        walk(suite)
        self.assertGreater(len(collected), 0)
        self.assertEqual({cls.__module__ for cls in collected}, {__name__})

    def test_ac8_the_stub_harness_is_the_existing_one_not_a_copy(self):
        self.assertTrue(issubclass(ReplaceCase, helpers.GoScanCase))
        self.assertIs(ReplaceCase.install_go, helpers.GoScanCase.install_go)
        self.assertEqual(helpers.write_stub.__module__, helpers.__name__)
        self.assertEqual(Path(helpers.__file__), _HELPERS_PATH)


if __name__ == "__main__":
    unittest.main()
