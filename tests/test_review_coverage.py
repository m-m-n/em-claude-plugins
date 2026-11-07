"""Tests for task0003 (feature-docs/large-diff-review-coverage): the result
classification and coverage determination script
`em-workflow/scripts/review-coverage.py`.

The script has two operations. `classify_results` decides which schema-valid
litellm results count as failed (D6). `coverage` computes
`unreviewed_perspectives` and `partially_reviewed_perspectives` (D5) from
run_ids (D1), run statuses and the shard manifests of the passes (D3, D8).
Neither operation reads diff text. The tests build manifests by hand in the
review-shards output shape; review-shards itself is never run here.

The hyphenated script is loaded by file path for the in-process checks
(`main()` with the input document in a temporary file) and run as a child
process for the command line checks. Every child process carries a timeout, so
a hang becomes a failure. Importing this module never touches the script: it
is loaded on first use.

Covers task0003 Acceptance Criteria
(feature-docs/large-diff-review-coverage/tasks/task0003.md):

- AC-1 (FR3, TM-5; TS-2): the failed decision and input order
  (TestClassifyResults, TestClassifyResultsRejectsInvalidInput).
- AC-2 (FR8; TS-6): the run_id grammar, duplicates and ignored rows
  (TestRunIdGrammar, TestDuplicateRunIds, TestIgnoredRows).
- AC-3 (FR9, FR4; TS-6, TS-5): shard-level replacement and the
  unreviewed decision (TestShardLevelReplacement, TestUnreviewedPerspectives).
- AC-4 (FR13; TS-5): partial entries, sorted files and reason tokens
  (TestPartiallyReviewedPerspectives, TestReasonTokens).
- AC-5 (FR14; TS-5): post-fix invalidation (TestPostFixInvalidation).
- AC-6 (FR11; TS-5): spec rescue runs (TestSpecRescueRuns).
- AC-7 (TM-6, TM-9, NFR3, NFR4, NFR6, FR18; TS-11, TS-12, TS-13): output
  shape, path rules, ignored row keys, determinism and the standard-library
  constraint (TestOutputShape, TestPathRules, TestRowKeysAreIgnored,
  TestDeterminism, TestInputDocumentChecks, TestCoverageInputChecks,
  TestCommandLineContract, TestStandardLibraryOnly).
"""

import ast
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / "em-workflow" / "scripts" / "review-coverage.py"
THIS_MODULE = Path(__file__).resolve()

CALL_TIMEOUT_SECONDS = 30

TRUNCATED = "litellm model output truncated"
NON_JSON = "litellm returned non-JSON output"

FILE_A = "src/a.py"
FILE_B = "src/b.py"
FILE_C = "src/c.py"
FILE_D = "src/d.py"
FILE_E = "src/e.py"

MANIFEST_KEYS = [
    "limit",
    "total_chars",
    "split",
    "files",
    "shards",
    "shard_cap",
    "dispatched_shards",
    "excess_shards",
]


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
            "review_coverage_under_test", SCRIPT
        )
        module = importlib.util.module_from_spec(spec)
        previous = sys.dont_write_bytecode
        sys.dont_write_bytecode = True
        try:
            spec.loader.exec_module(module)
        finally:
            sys.dont_write_bytecode = previous
        _LOADED = module
    return _LOADED


# --------------------------------------------------------------- runners ----


class Outcome:
    """The exit code, raw stdout bytes and decoded stderr of one run."""

    def __init__(self, code, stdout, stderr):
        self.code = code
        self.stdout = stdout
        self.stderr = stderr

    def data(self):
        return json.loads(self.stdout.decode("utf-8"))


def run_path(path):
    """Run `main([path])` in this process, capturing both streams."""
    out = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
    err = io.StringIO()
    with mock.patch.object(sys, "stdout", out), mock.patch.object(sys, "stderr", err):
        code = script_module().main([path])
        out.flush()
        stdout = out.buffer.getvalue()
    return Outcome(code, stdout, err.getvalue())


def run_bytes(raw):
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "input.json")
        with open(path, "wb") as handle:
            handle.write(raw)
        return run_path(path)


def run_doc(document):
    return run_bytes(json.dumps(document).encode("utf-8"))


def run_child(args, env=None):
    completed = subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        timeout=CALL_TIMEOUT_SECONDS,
        env=env,
    )
    return Outcome(
        completed.returncode, completed.stdout, completed.stderr.decode("utf-8")
    )


def run_child_doc(document, env=None):
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "input.json")
        with open(path, "wb") as handle:
            handle.write(json.dumps(document).encode("utf-8"))
        return run_child([path], env=env)


# -------------------------------------------------------------- builders ----


def item(run_id="security#0", origin="litellm", count=0, summary=TRUNCATED):
    return {
        "run_id": run_id,
        "origin": origin,
        "finding_count": count,
        "summary": summary,
    }


def classify_doc(results):
    return {"operation": "classify_results", "results": results}


def classify(results):
    outcome = run_doc(classify_doc(results))
    assert outcome.code == 0, outcome.stderr
    return outcome.data()


def manifest(*shards, cap=None):
    """A manifest in the review-shards output shape.

    Each positional argument is the list of paths of one shard, in index
    order. One shard is an unsplit manifest; more than one is split. `cap` is
    `shard_cap`: the first `cap` indexes are dispatched, the rest excess.
    """
    shards = [list(paths) for paths in shards]
    count = len(shards)
    cap = count if cap is None else cap
    indexes = list(range(1, count + 1))
    all_paths = sorted(path for paths in shards for path in paths)
    return {
        "limit": 200000,
        "total_chars": 1000 * len(all_paths),
        "split": count > 1,
        "files": [{"path": path, "chars": 1000} for path in all_paths],
        "shards": [
            {"index": index, "paths": sorted(paths), "chars": 1000 * len(paths)}
            for index, paths in zip(indexes, shards)
        ],
        "shard_cap": cap,
        "dispatched_shards": indexes[:cap],
        "excess_shards": indexes[cap:],
    }


def unsplit(*paths):
    return manifest(list(paths))


def make_pass(loop, pass_manifest, fixed=()):
    return {"loop": loop, "fixed_files": list(fixed), "manifest": pass_manifest}


def row(run_id, status="completed", role="primary", source="codex", **extra):
    perspective = re.split("[@#]", run_id)[0]
    entry = {
        "run_id": run_id,
        "perspective": perspective,
        "role": role,
        "status": status,
        "source": source,
    }
    entry.update(extra)
    return entry


def coverage_doc(perspectives, passes, runs):
    return {
        "operation": "coverage",
        "perspectives": list(perspectives),
        "passes": passes,
        "perspective_runs": runs,
    }


def coverage(perspectives, passes, runs):
    outcome = run_doc(coverage_doc(perspectives, passes, runs))
    assert outcome.code == 0, outcome.stderr
    return outcome.data()


def entry(perspective, files, reason):
    return {
        "perspective": perspective,
        "unreviewed_files": list(files),
        "reason": reason,
    }


def expected(unreviewed=(), partial=()):
    return {
        "unreviewed_perspectives": list(unreviewed),
        "partially_reviewed_perspectives": list(partial),
    }


def split_three(cap=None):
    return manifest([FILE_A], [FILE_B], [FILE_C], cap=cap)


def unsplit_three():
    return unsplit(FILE_A, FILE_B, FILE_C)


def loop_zero_only(pass_manifest):
    return [make_pass(0, pass_manifest)]


class RejectionMixin:
    def assert_rejected(self, outcome, label=""):
        self.assertEqual(outcome.code, 2, f"{label}: {outcome.stderr!r}")
        self.assertEqual(outcome.stdout, b"", label)
        self.assertTrue(outcome.stderr.strip(), f"{label}: no stderr message")
        self.assertTrue(
            outcome.stderr.startswith("review-coverage: "),
            f"{label}: stderr does not start with the program name: {outcome.stderr!r}",
        )


# ====================================================== AC-1: classification


CLASSIFICATION_CASES = [
    ("litellm, zero findings, truncated summary", "litellm", 0, TRUNCATED, "failed"),
    ("litellm, zero findings, non-JSON summary", "litellm", 0, NON_JSON, "failed"),
    ("codex with the truncated summary", "codex", 0, TRUNCATED, "completed"),
    ("codex with the non-JSON summary", "codex", 0, NON_JSON, "completed"),
    ("claude with the truncated summary", "claude", 0, TRUNCATED, "completed"),
    ("claude with the non-JSON summary", "claude", 0, NON_JSON, "completed"),
    ("litellm, one finding, truncated", "litellm", 1, TRUNCATED, "completed"),
    ("litellm, many findings, non-JSON", "litellm", 7, NON_JSON, "completed"),
    ("litellm, zero findings, empty summary", "litellm", 0, "", "completed"),
    ("litellm, zero findings, ordinary summary", "litellm", 0, "no issues", "completed"),
    ("trailing space", "litellm", 0, TRUNCATED + " ", "completed"),
    ("leading space", "litellm", 0, " " + TRUNCATED, "completed"),
    ("trailing newline", "litellm", 0, TRUNCATED + "\n", "completed"),
    ("leading tab", "litellm", 0, "\t" + NON_JSON, "completed"),
    ("trailing carriage return", "litellm", 0, NON_JSON + "\r", "completed"),
    ("upper case", "litellm", 0, TRUNCATED.upper(), "completed"),
    ("capitalized", "litellm", 0, "Litellm model output truncated", "completed"),
    ("title case non-JSON", "litellm", 0, "litellm returned non-json output", "completed"),
    ("added prefix", "litellm", 0, "error: " + TRUNCATED, "completed"),
    ("added suffix", "litellm", 0, TRUNCATED + " (retry)", "completed"),
    ("added period", "litellm", 0, NON_JSON + ".", "completed"),
    ("a prefix of the fixed string", "litellm", 0, TRUNCATED[:-1], "completed"),
    ("a suffix of the fixed string", "litellm", 0, NON_JSON[1:], "completed"),
    ("both fixed strings joined", "litellm", 0, TRUNCATED + NON_JSON, "completed"),
    ("no-break space inside", "litellm", 0, "litellm model output truncated", "completed"),
    ("zero-width space appended", "litellm", 0, NON_JSON + "​", "completed"),
    ("full-width letters", "litellm", 0, "ｌｉｔｅｌｌｍ ｍｏｄｅｌ ｏｕｔｐｕｔ ｔｒｕｎｃａｔｅｄ", "completed"),
]


class TestClassifyResults(unittest.TestCase):
    """AC-1 (FR3, TM-5; TS-2)."""

    def test_status_follows_origin_findings_and_exact_summary(self):
        results = [
            item(f"case{index}#0", origin, count, summary)
            for index, (_, origin, count, summary, _) in enumerate(CLASSIFICATION_CASES)
        ]
        statuses = {r["run_id"]: r["status"] for r in classify(results)["results"]}
        for index, (label, _, _, _, want) in enumerate(CLASSIFICATION_CASES):
            with self.subTest(label):
                self.assertEqual(statuses[f"case{index}#0"], want)

    def test_failed_is_exactly_the_two_litellm_cases(self):
        results = [
            item(f"case{index}#0", origin, count, summary)
            for index, (_, origin, count, summary, _) in enumerate(CLASSIFICATION_CASES)
        ]
        failed = [r["run_id"] for r in classify(results)["results"] if r["status"] == "failed"]
        self.assertEqual(failed, ["case0#0", "case1#0"])

    def test_every_origin_with_every_count_and_summary_is_classified_alone(self):
        for origin in ("codex", "litellm", "claude"):
            for count in (0, 1, 2):
                for summary in (TRUNCATED, NON_JSON, "other"):
                    want = (
                        "failed"
                        if origin == "litellm" and count == 0 and summary != "other"
                        else "completed"
                    )
                    with self.subTest(origin=origin, count=count, summary=summary):
                        got = classify([item("x#0", origin, count, summary)])
                        self.assertEqual(got, {"results": [{"run_id": "x#0", "status": want}]})

    def test_results_come_back_in_input_order(self):
        run_ids = ["zeta#0", "alpha@s2#1", "mid#loop1.fallback", "alpha@s1#0", "beta#2"]
        results = [
            item(run_id, "litellm" if index % 2 == 0 else "codex", 0, TRUNCATED)
            for index, run_id in enumerate(run_ids)
        ]
        got = classify(results)["results"]
        self.assertEqual([r["run_id"] for r in got], run_ids)
        self.assertEqual(
            [r["status"] for r in got],
            ["failed", "completed", "failed", "completed", "failed"],
        )

    def test_an_empty_list_gives_an_empty_list(self):
        self.assertEqual(classify([]), {"results": []})

    def test_output_holds_only_run_id_and_status_and_never_echoes_the_summary(self):
        sentinel = "SENTINEL-summary-text-9f3a"
        outcome = run_doc(classify_doc([item("x#0", "claude", 2, sentinel)]))
        self.assertEqual(outcome.code, 0)
        self.assertEqual(list(outcome.data()), ["results"])
        self.assertEqual(list(outcome.data()["results"][0]), ["run_id", "status"])
        self.assertNotIn(sentinel.encode("utf-8"), outcome.stdout)


BAD_CLASSIFY_ITEMS = [
    ("missing run_id", {"origin": "codex", "finding_count": 0, "summary": ""}),
    ("missing origin", {"run_id": "x#0", "finding_count": 0, "summary": ""}),
    ("missing finding_count", {"run_id": "x#0", "origin": "codex", "summary": ""}),
    ("missing summary", {"run_id": "x#0", "origin": "codex", "finding_count": 0}),
    ("extra key", dict(item("x#0", "codex", 0, ""), source="litellm")),
    ("extra key skip_reason", dict(item("x#0", "codex", 0, ""), skip_reason="x")),
    ("run_id not a string", item(5)),
    ("run_id empty", item("")),
    ("origin unknown", item("x#0", "vertex")),
    ("origin upper case", item("x#0", "LiteLLM")),
    ("origin empty", item("x#0", "")),
    ("origin null", item("x#0", None)),
    ("origin number", item("x#0", 5)),
    ("count true", item("x#0", "codex", True)),
    ("count false", item("x#0", "codex", False)),
    ("count negative", item("x#0", "codex", -1)),
    ("count float", item("x#0", "codex", 1.5)),
    ("count float zero", item("x#0", "litellm", 0.0)),
    ("count string", item("x#0", "codex", "0")),
    ("count null", item("x#0", "codex", None)),
    ("summary null", item("x#0", "codex", 0, None)),
    ("summary number", item("x#0", "codex", 0, 5)),
    ("summary list", item("x#0", "codex", 0, [])),
    ("item is a list", ["x#0", "codex", 0, ""]),
    ("item is a string", "x#0"),
    ("item is null", None),
]


class TestClassifyResultsRejectsInvalidInput(RejectionMixin, unittest.TestCase):
    """AC-1: invalid items exit 2 with a stderr message and empty stdout."""

    def test_each_invalid_item_exits_2(self):
        for label, bad in BAD_CLASSIFY_ITEMS:
            with self.subTest(label):
                self.assert_rejected(run_doc(classify_doc([item("ok#0"), bad])), label)

    def test_one_invalid_item_rejects_the_whole_call(self):
        outcome = run_doc(classify_doc([item("a#0", "codex", 0, "fine"), item("b#0", "bogus")]))
        self.assert_rejected(outcome)

    def test_results_that_is_not_a_list_exits_2(self):
        for bad in (None, {}, "x", 5, {"run_id": "x#0"}):
            with self.subTest(repr(bad)):
                self.assert_rejected(run_doc(classify_doc(bad)))

    def test_a_missing_or_extra_document_member_exits_2(self):
        self.assert_rejected(run_doc({"operation": "classify_results"}))
        self.assert_rejected(run_doc(dict(classify_doc([]), perspectives=[])))


# ====================================================== AC-2: run_id grammar

ALL_NAMES = ["security", "performance", "architecture", "spec", "comprehensive"]
LOOPS = (0, 1, 2, 10)


def layout_passes(layout):
    """Passes of loops 0, 1, 2 and 10, all unsplit ("U") or all split ("S")."""
    build = unsplit_three if layout == "U" else split_three
    return [make_pass(loop, build()) for loop in LOOPS]


GRAMMAR_ACCEPTED = [
    # run_id, layout, expected result for a single completed row of that run_id
    ("security#0", "U", expected()),
    ("security#10", "U", expected()),
    ("security#fallback", "U", expected()),
    ("security#loop1.0", "U", expected()),
    ("comprehensive#loop2.fallback", "U", expected()),
    ("security#loop10.12", "U", expected()),
    ("performance@s2#1", "S", expected(partial=[entry("performance", [FILE_A, FILE_C], "run_not_completed")])),
    ("architecture@s3#loop1.0", "S", expected(partial=[entry("architecture", [FILE_A, FILE_B], "run_not_completed")])),
    ("performance@s2#loop10.12", "S", expected(partial=[entry("performance", [FILE_A, FILE_C], "run_not_completed")])),
    ("spec@s1#fallback", "S", expected(partial=[entry("spec", [FILE_B, FILE_C], "run_not_completed,spec_rescue")])),
    ("spec#0", "S", expected()),
    ("spec#loop2.fallback", "S", expected()),
]

GRAMMAR_REJECTED = [
    # label, layout, run_id (the row's perspective is the part before @ and #)
    ("zero shard index", "S", "performance@s0#1"),
    ("leading-zero shard index", "S", "performance@s01#1"),
    ("shard index not a number", "S", "performance@sx#1"),
    ("shard index missing", "S", "performance@s#1"),
    ("shard marker upper case", "S", "performance@S1#1"),
    ("shard marker without s", "S", "performance@1#1"),
    ("two shard markers", "S", "performance@s1@s2#1"),
    ("shard without chain part", "S", "performance@s2"),
    ("zero loop", "U", "security#loop0.0"),
    ("leading-zero loop", "U", "security#loop01.0"),
    ("loop without chain segment", "U", "security#loop1"),
    ("loop with empty chain segment", "U", "security#loop1."),
    ("loop marker upper case", "U", "security#Loop1.0"),
    ("loop without number", "U", "security#loop.0"),
    ("loop given twice", "U", "security#loop1.loop1.0"),
    ("missing # part", "U", "security"),
    ("empty chain segment", "U", "security#"),
    ("chain not a number", "U", "security#x"),
    ("chain word with a suffix", "U", "security#fallbacks"),
    ("chain word capitalized", "U", "security#Fallback"),
    ("negative chain index", "U", "security#-1"),
    ("signed chain index", "U", "security#+1"),
    ("leading-zero chain index", "U", "security#00"),
    ("leading-zero chain index 01", "U", "security#01"),
    ("fractional chain index", "U", "security#1.5"),
    ("full-width digit chain index", "U", "security#１"),
    ("arabic-indic digit chain index", "U", "security#٣"),
    ("full-width digit shard index", "S", "performance@s２#1"),
    ("leading space", "U", " security#0"),
    ("trailing space", "U", "security#0 "),
    ("trailing newline", "U", "security#0\n"),
    ("double hash", "U", "security##0"),
    ("loop after a second hash", "U", "security#loop1.#0"),
    ("empty perspective part", "U", "#0"),
    ("loop with no pass", "U", "security#loop3.0"),
    ("large loop with no pass", "U", "security#loop999999999999999999999.0"),
    ("shard on an unsplit pass", "U", "performance@s1#1"),
    ("shard on an unsplit pass in a later loop", "U", "performance@s1#loop1.0"),
    ("shard missing from the pass", "S", "performance@s4#1"),
    ("shard missing from a later pass", "S", "performance@s4#loop2.1"),
    ("non-spec run without shard on a split pass", "S", "security#0"),
    ("non-spec fallback without shard on a split pass", "S", "security#fallback"),
    ("non-spec loop run without shard on a split pass", "S", "security#loop1.0"),
    ("spec rescue on an unsplit pass", "U", "spec@s1#0"),
]


class TestRunIdGrammar(RejectionMixin, unittest.TestCase):
    """AC-2 (FR8; TS-6): every D1 form is accepted, malformed forms exit 2."""

    def test_every_run_id_form_is_accepted_and_attributed_to_its_shard(self):
        for run_id, layout, want in GRAMMAR_ACCEPTED:
            with self.subTest(run_id):
                got = coverage([row(run_id)["perspective"]], layout_passes(layout), [row(run_id)])
                self.assertEqual(got, want)

    def test_malformed_run_ids_and_misplaced_shards_exit_2(self):
        for label, layout, run_id in GRAMMAR_REJECTED:
            with self.subTest(label):
                outcome = run_doc(
                    coverage_doc(ALL_NAMES, layout_passes(layout), [row(run_id)])
                )
                self.assert_rejected(outcome, label)

    def test_a_run_for_an_excess_shard_exits_2_whatever_its_status(self):
        passes = [make_pass(0, split_three(cap=2))]
        for run_id in ("performance@s3#0", "spec@s3#0", "performance@s3#fallback"):
            for status in ("completed", "skipped", "failed"):
                with self.subTest(run_id=run_id, status=status):
                    outcome = run_doc(coverage_doc(ALL_NAMES, passes, [row(run_id, status)]))
                    self.assert_rejected(outcome, run_id)

    def test_a_run_for_a_shard_the_pass_does_not_have_exits_2_whatever_its_status(self):
        for status in ("completed", "skipped", "failed"):
            with self.subTest(status):
                outcome = run_doc(
                    coverage_doc(ALL_NAMES, layout_passes("S"), [row("performance@s4#1", status)])
                )
                self.assert_rejected(outcome, status)

    def test_a_perspective_mismatch_exits_2(self):
        passes = layout_passes("U")
        for label, bad in (
            ("different known perspective", dict(row("security#0"), perspective="performance")),
            ("different perspective with shard form", dict(row("performance@s2#1"), perspective="security")),
            ("run_id of a longer name", dict(row("securityx#0"), perspective="security")),
            ("run_id of a prefix name", dict(row("secur#0"), perspective="security")),
            ("run_id of another case", dict(row("Security#0"), perspective="security")),
        ):
            with self.subTest(label):
                self.assert_rejected(run_doc(coverage_doc(ALL_NAMES, passes, [bad])), label)

    def test_a_run_id_that_is_not_a_string_exits_2(self):
        for bad in (5, None, ["security#0"], {"a": 1}, True):
            with self.subTest(repr(bad)):
                self.assert_rejected(
                    run_doc(coverage_doc(ALL_NAMES, layout_passes("U"), [dict(row("security#0"), run_id=bad)]))
                )

    def test_a_row_without_a_run_id_exits_2(self):
        bad = row("security#0")
        del bad["run_id"]
        self.assert_rejected(run_doc(coverage_doc(ALL_NAMES, layout_passes("U"), [bad])))

    def test_a_row_for_a_perspective_outside_the_round_exits_2(self):
        for name in ("unknown", "vulnerability", "Security", ""):
            with self.subTest(repr(name)):
                bad = dict(row("security#0"), perspective=name, run_id=f"{name}#0")
                self.assert_rejected(run_doc(coverage_doc(["security"], layout_passes("U"), [bad])))

    def test_a_skipped_status_is_still_a_valid_row_with_a_valid_run_id(self):
        got = coverage(["security"], layout_passes("U"), [row("security#0", "skipped", skip_reason="rate_limited")])
        self.assertEqual(got, expected(unreviewed=["security"]))


class TestDuplicateRunIds(RejectionMixin, unittest.TestCase):
    """AC-2: a run_id repeated by a later row exits 2."""

    def test_the_same_run_id_twice_exits_2_whatever_the_statuses(self):
        for first, second in (
            ("skipped", "completed"),
            ("completed", "completed"),
            ("failed", "skipped"),
        ):
            with self.subTest(first=first, second=second):
                outcome = run_doc(
                    coverage_doc(
                        ["security"],
                        layout_passes("U"),
                        [row("security#0", first), row("security#0", second)],
                    )
                )
                self.assert_rejected(outcome)

    def test_a_duplicate_with_other_rows_between_exits_2(self):
        runs = [row("security#0", "skipped"), row("performance#0"), row("security#1"), row("security#0")]
        self.assert_rejected(run_doc(coverage_doc(ALL_NAMES, layout_passes("U"), runs)))

    def test_the_same_chain_index_in_different_shards_is_not_a_duplicate(self):
        runs = [row("performance@s1#0"), row("performance@s2#0"), row("performance@s3#0")]
        got = coverage(["performance"], layout_passes("S"), runs)
        self.assertEqual(got, expected())

    def test_the_same_chain_index_in_different_loops_is_not_a_duplicate(self):
        runs = [row("security#0"), row("security#loop1.0"), row("security#loop2.0")]
        got = coverage(["security"], layout_passes("U"), runs)
        self.assertEqual(got, expected())

    def test_shard_one_and_a_run_without_a_shard_are_different_run_ids(self):
        runs = [row("spec#0", "failed"), row("spec@s1#0", "completed")]
        got = coverage(["spec"], layout_passes("S"), runs)
        self.assertEqual(got["unreviewed_perspectives"], [])

    def test_repeated_evaluator_and_tool_rows_are_not_duplicates(self):
        runs = [
            row("security#0"),
            {"run_id": "evaluator", "role": "evaluator", "source": "claude", "status": "completed"},
            {"run_id": "evaluator", "role": "evaluator", "source": "claude", "status": "failed"},
            {"run_id": "vulnerability#tool", "perspective": "vulnerability", "role": "primary", "source": "tool", "status": "completed"},
            {"run_id": "vulnerability#tool", "perspective": "vulnerability", "role": "primary", "source": "tool", "status": "completed"},
        ]
        self.assertEqual(coverage(["security"], layout_passes("U"), runs), expected())


EVALUATOR_ROW = {
    "run_id": "evaluator",
    "role": "evaluator",
    "source": "claude",
    "status": "completed",
}
TOOL_ROW = {
    "run_id": "vulnerability#tool",
    "perspective": "vulnerability",
    "role": "primary",
    "source": "tool",
    "status": "completed",
}


class TestIgnoredRows(unittest.TestCase):
    """AC-2 (FR8): `vulnerability#tool` and `evaluator` rows are ignored."""

    def setUp(self):
        self.passes = layout_passes("U")
        self.runs = [row("security#0"), row("performance#0", "skipped")]
        self.base = coverage(["security", "performance"], self.passes, self.runs)

    def test_the_base_case_is_what_the_other_tests_compare_against(self):
        self.assertEqual(self.base, expected(unreviewed=["performance"]))

    def test_evaluator_and_tool_rows_change_nothing(self):
        runs = self.runs + [EVALUATOR_ROW, TOOL_ROW]
        self.assertEqual(coverage(["security", "performance"], self.passes, runs), self.base)

    def test_a_tool_row_cannot_review_a_perspective(self):
        tool_for_performance = dict(row("performance#1"), source="tool")
        runs = self.runs + [tool_for_performance]
        self.assertEqual(coverage(["security", "performance"], self.passes, runs), self.base)

    def test_an_evaluator_role_row_for_a_perspective_cannot_review_it(self):
        sneaky = dict(row("performance#1"), role="evaluator")
        runs = self.runs + [sneaky]
        self.assertEqual(coverage(["security", "performance"], self.passes, runs), self.base)

    def test_ignored_rows_are_skipped_before_any_row_check(self):
        malformed = [
            {"role": "evaluator"},
            {"source": "tool"},
            {"run_id": 5, "role": "evaluator", "perspective": 7, "status": "bogus", "source": 1},
            {"run_id": "not a run id", "perspective": "nobody", "role": "primary", "source": "tool", "status": "x"},
            {"run_id": "security#0", "perspective": "security", "role": "evaluator", "status": "completed", "source": "claude"},
        ]
        for bad in malformed:
            with self.subTest(repr(bad)):
                runs = self.runs + [bad]
                self.assertEqual(coverage(["security", "performance"], self.passes, runs), self.base)

    def test_a_tool_row_in_a_split_round_does_not_need_a_shard(self):
        got = coverage(["security"], layout_passes("S"), [TOOL_ROW, EVALUATOR_ROW])
        self.assertEqual(got, expected(unreviewed=["security"]))


# ================================================= AC-3: shard-level results


class TestShardLevelReplacement(unittest.TestCase):
    """AC-3 (FR9; TS-6): one shard's last result never affects another's."""

    def setUp(self):
        self.passes = loop_zero_only(split_three())

    def run_performance(self, runs):
        return coverage(["performance"], self.passes, runs)

    def test_a_skipped_shard_leaves_the_other_shards_completed_result_in_effect(self):
        runs = [
            row("performance@s1#0"),
            row("performance@s2#0", "skipped", skip_reason="rate_limited"),
            row("performance@s2#1", "skipped", skip_reason="scratchpad_unavailable"),
            row("performance@s3#0", "failed"),
            row("performance@s3#fallback"),
        ]
        self.assertEqual(
            self.run_performance(runs),
            expected(partial=[entry("performance", [FILE_B], "run_not_completed")]),
        )

    def test_a_failed_last_result_of_one_shard_leaves_the_others_in_effect(self):
        runs = [
            row("performance@s1#0"),
            row("performance@s2#0"),
            row("performance@s3#0", "failed"),
        ]
        self.assertEqual(
            self.run_performance(runs),
            expected(partial=[entry("performance", [FILE_C], "run_not_completed")]),
        )

    def test_the_last_row_in_perspective_runs_order_decides_a_group(self):
        runs = [
            row("performance@s1#1"),
            row("performance@s1#0", "skipped"),
            row("performance@s2#1", "skipped"),
            row("performance@s2#0"),
            row("performance@s3#0"),
        ]
        self.assertEqual(
            self.run_performance(runs),
            expected(partial=[entry("performance", [FILE_A], "run_not_completed")]),
        )

    def test_a_later_row_of_one_shard_never_replaces_another_shards_row(self):
        runs = [
            row("performance@s2#0"),
            row("performance@s1#0", "skipped"),
            row("performance@s3#0"),
            row("performance@s1#1", "failed"),
        ]
        self.assertEqual(
            self.run_performance(runs),
            expected(partial=[entry("performance", [FILE_A], "run_not_completed")]),
        )

    def test_a_group_whose_last_row_is_completed_covers_its_shard_after_earlier_failures(self):
        runs = [
            row("performance@s1#0", "failed"),
            row("performance@s1#1", "skipped"),
            row("performance@s1#fallback"),
            row("performance@s2#0"),
            row("performance@s3#0"),
        ]
        self.assertEqual(self.run_performance(runs), expected())

    def test_a_completed_row_followed_by_a_later_failure_does_not_count(self):
        runs = [
            row("performance@s1#0"),
            row("performance@s1#1", "failed"),
            row("performance@s2#0"),
            row("performance@s3#0"),
        ]
        self.assertEqual(
            self.run_performance(runs),
            expected(partial=[entry("performance", [FILE_A], "run_not_completed")]),
        )

    def test_perspectives_do_not_share_groups(self):
        runs = [
            row("performance@s1#0"),
            row("performance@s2#0"),
            row("performance@s3#0"),
            row("architecture@s1#0", "skipped"),
            row("architecture@s2#0"),
            row("architecture@s3#0"),
        ]
        got = coverage(["performance", "architecture"], self.passes, runs)
        self.assertEqual(
            got,
            expected(partial=[entry("architecture", [FILE_A], "run_not_completed")]),
        )

    def test_on_an_unsplit_pass_the_last_chain_result_decides(self):
        passes = loop_zero_only(unsplit_three())
        replaced = coverage(["security"], passes, [row("security#0", "skipped"), row("security#1")])
        lost = coverage(["security"], passes, [row("security#0"), row("security#fallback", "failed")])
        self.assertEqual(replaced, expected())
        self.assertEqual(lost, expected(unreviewed=["security"]))


class TestUnreviewedPerspectives(unittest.TestCase):
    """AC-3 (FR4): perspectives without a completed group are unreviewed."""

    def test_groups_that_all_end_skipped_or_failed_leave_the_perspective_unreviewed(self):
        passes = loop_zero_only(split_three())
        for first, second in (
            ("skipped", "skipped"),
            ("failed", "failed"),
            ("skipped", "failed"),
            ("failed", "skipped"),
        ):
            with self.subTest(first=first, second=second):
                runs = [
                    row("performance@s1#0", first, skip_reason="rate_limited"),
                    row("performance@s2#0", second, skip_reason="scratchpad_unavailable"),
                ]
                self.assertEqual(
                    coverage(["performance"], passes, runs),
                    expected(unreviewed=["performance"]),
                )

    def test_retryable_and_non_retryable_skips_are_alike(self):
        passes = loop_zero_only(unsplit_three())
        for reason in (
            "rate_limited",
            "budget_exhausted",
            "harness_unavailable",
            "review_data_too_large",
            "scratchpad_unavailable",
            "anything_else",
        ):
            with self.subTest(reason):
                runs = [row("security#0", "skipped", skip_reason=reason)]
                self.assertEqual(
                    coverage(["security"], passes, runs), expected(unreviewed=["security"])
                )

    def test_a_perspective_with_no_row_is_unreviewed(self):
        passes = loop_zero_only(unsplit_three())
        got = coverage(["security", "performance"], passes, [row("security#0")])
        self.assertEqual(got, expected(unreviewed=["performance"]))

    def test_no_rows_at_all_leaves_every_perspective_unreviewed_in_order(self):
        passes = loop_zero_only(unsplit_three())
        got = coverage(["spec", "architecture", "security"], passes, [])
        self.assertEqual(got, expected(unreviewed=["spec", "architecture", "security"]))

    def test_both_lists_follow_the_order_of_perspectives(self):
        passes = loop_zero_only(split_three())
        runs = [
            row("performance@s1#0"),
            row("performance@s2#0", "failed"),
            row("performance@s3#0"),
            row("architecture@s1#0"),
            row("architecture@s2#0"),
            row("architecture@s3#0", "failed"),
        ]
        names = ["spec", "security", "performance", "comprehensive", "architecture"]
        got = coverage(names, passes, runs)
        self.assertEqual(got["unreviewed_perspectives"], ["spec", "security", "comprehensive"])
        self.assertEqual(
            [e["perspective"] for e in got["partially_reviewed_perspectives"]],
            ["performance", "architecture"],
        )
        reversed_got = coverage(list(reversed(names)), passes, runs)
        self.assertEqual(reversed_got["unreviewed_perspectives"], ["comprehensive", "security", "spec"])
        self.assertEqual(
            [e["perspective"] for e in reversed_got["partially_reviewed_perspectives"]],
            ["architecture", "performance"],
        )

    def test_a_completed_group_whose_files_were_all_changed_afterwards_is_unreviewed(self):
        passes = [
            make_pass(0, unsplit(FILE_A)),
            make_pass(1, unsplit(FILE_A), fixed=[FILE_A]),
        ]
        got = coverage(["security"], passes, [row("security#0")])
        self.assertEqual(got, expected(unreviewed=["security"]))

    def test_an_empty_universe_with_a_completed_group_is_fully_reviewed(self):
        for empty in (manifest([]), dict(manifest([]), shards=[], dispatched_shards=[])):
            with self.subTest(shards=empty["shards"]):
                passes = loop_zero_only(empty)
                got = coverage(
                    ["security", "performance", "spec"],
                    passes,
                    [row("security#0"), row("performance#0", "skipped")],
                )
                self.assertEqual(got, expected(unreviewed=["performance", "spec"]))

    def test_no_perspectives_gives_two_empty_lists(self):
        self.assertEqual(coverage([], loop_zero_only(unsplit_three()), []), expected())


# ===================================================== AC-4: partial entries


class TestPartiallyReviewedPerspectives(unittest.TestCase):
    """AC-4 (FR13; TS-5)."""

    def test_a_completed_group_with_an_unreviewed_file_is_partial_not_unreviewed(self):
        runs = [
            row("performance@s1#0"),
            row("performance@s2#0", "failed"),
            row("performance@s3#0", "skipped"),
        ]
        got = coverage(["performance"], loop_zero_only(split_three()), runs)
        self.assertEqual(
            got,
            expected(partial=[entry("performance", [FILE_B, FILE_C], "run_not_completed")]),
        )
        self.assertEqual(got["unreviewed_perspectives"], [])

    def test_a_perspective_is_never_in_both_lists(self):
        runs = [
            row("performance@s1#0"),
            row("performance@s2#0", "failed"),
            row("architecture@s1#0", "failed"),
            row("architecture@s2#0", "failed"),
        ]
        got = coverage(["performance", "architecture", "security"], loop_zero_only(split_three()), runs)
        partial = {e["perspective"] for e in got["partially_reviewed_perspectives"]}
        self.assertEqual(partial, {"performance"})
        self.assertEqual(got["unreviewed_perspectives"], ["architecture", "security"])
        self.assertFalse(partial & set(got["unreviewed_perspectives"]))

    def test_both_lists_are_present_and_empty_when_nothing_qualifies(self):
        runs = [row("security#0"), row("performance#fallback")]
        outcome = run_doc(coverage_doc(["security", "performance"], loop_zero_only(unsplit_three()), runs))
        self.assertEqual(outcome.code, 0)
        self.assertEqual(
            outcome.data(),
            {"unreviewed_perspectives": [], "partially_reviewed_perspectives": []},
        )

    def test_entries_hold_exactly_perspective_files_and_reason_in_that_order(self):
        runs = [row("performance@s1#0"), row("performance@s2#0", "failed"), row("performance@s3#0")]
        got = coverage(["performance"], loop_zero_only(split_three()), runs)
        self.assertEqual(
            list(got["partially_reviewed_perspectives"][0]),
            ["perspective", "unreviewed_files", "reason"],
        )

    def test_unreviewed_files_are_sorted_by_code_point_whatever_the_input_order(self):
        names = ["src/é.py", FILE_B, "Src/Z.py", FILE_A]
        shards = [["src/ok.py"], [names[0], names[1]], [names[2]], [names[3]]]
        built = manifest(*shards)
        built["files"] = list(reversed(built["files"]))
        for shard in built["shards"]:
            shard["paths"] = list(reversed(shard["paths"]))
        got = coverage(["performance"], loop_zero_only(built), [row("performance@s1#0")])
        self.assertEqual(
            got["partially_reviewed_perspectives"][0]["unreviewed_files"],
            ["Src/Z.py", FILE_A, FILE_B, "src/é.py"],
        )

    def test_a_non_ascii_path_is_written_unescaped(self):
        built = manifest(["src/ok.py"], ["docs/日本語.md"])
        outcome = run_doc(
            coverage_doc(["performance"], loop_zero_only(built), [row("performance@s1#0")])
        )
        self.assertEqual(outcome.code, 0)
        self.assertIn("日本語".encode("utf-8"), outcome.stdout)
        self.assertNotIn(b"\\u", outcome.stdout)

    def test_the_universe_is_the_file_list_of_the_last_pass(self):
        first = manifest([FILE_A], [FILE_B])
        last = manifest([FILE_A], [FILE_B], [FILE_D])
        passes = [make_pass(0, first), make_pass(1, last, fixed=[FILE_D])]
        runs = [row("performance@s1#0"), row("performance@s2#0")]
        got = coverage(["performance"], passes, runs)
        self.assertEqual(
            got,
            expected(partial=[entry("performance", [FILE_D], "run_not_completed")]),
        )
        shrunk = [make_pass(0, last), make_pass(1, first)]
        got = coverage(["performance"], shrunk, [row("performance@s1#0"), row("performance@s2#0"), row("performance@s3#0")])
        self.assertEqual(got, expected())


class TestReasonTokens(unittest.TestCase):
    """AC-4: the D5 reason tokens, joined by a comma in the fixed order."""

    def test_run_not_completed_alone(self):
        runs = [row("performance@s1#0"), row("performance@s2#0", "failed"), row("performance@s3#0")]
        got = coverage(["performance"], loop_zero_only(split_three()), runs)
        self.assertEqual(got["partially_reviewed_perspectives"][0]["reason"], "run_not_completed")

    def test_shard_cap_exceeded_alone(self):
        runs = [row("performance@s1#0"), row("performance@s2#0")]
        got = coverage(["performance"], loop_zero_only(split_three(cap=2)), runs)
        self.assertEqual(
            got,
            expected(partial=[entry("performance", [FILE_C], "shard_cap_exceeded")]),
        )

    def test_a_dispatched_shard_with_no_row_at_all_is_run_not_completed(self):
        runs = [row("performance@s1#0")]
        got = coverage(["performance"], loop_zero_only(split_three()), runs)
        self.assertEqual(
            got,
            expected(partial=[entry("performance", [FILE_B, FILE_C], "run_not_completed")]),
        )

    def test_cap_token_comes_before_run_not_completed_whatever_the_file_order(self):
        # FILE_B (run_not_completed) sorts before FILE_C (shard_cap_exceeded).
        runs = [row("performance@s1#0"), row("performance@s2#0", "failed")]
        got = coverage(["performance"], loop_zero_only(split_three(cap=2)), runs)
        self.assertEqual(
            got,
            expected(
                partial=[
                    entry("performance", [FILE_B, FILE_C], "shard_cap_exceeded,run_not_completed")
                ]
            ),
        )

    def test_changed_after_review_comes_before_the_cap_token(self):
        passes = [
            make_pass(0, manifest([FILE_A], [FILE_B], [FILE_C])),
            make_pass(1, manifest([FILE_A], [FILE_B], [FILE_C], cap=2), fixed=[FILE_C]),
        ]
        runs = [
            row("performance@s1#0"),
            row("performance@s2#0"),
            row("performance@s3#0"),
        ]
        got = coverage(["performance"], passes, runs)
        self.assertEqual(
            got,
            expected(
                partial=[
                    entry("performance", [FILE_C], "changed_after_review,shard_cap_exceeded")
                ]
            ),
        )

    def test_all_four_tokens_appear_in_the_fixed_order(self):
        shards = [[FILE_A, FILE_E], [FILE_B], [FILE_C], [FILE_D]]
        passes = [
            make_pass(0, manifest(*shards, cap=3)),
            make_pass(1, manifest(*shards, cap=3), fixed=[FILE_A]),
        ]
        runs = [
            row("spec#0", "failed"),
            row("spec#fallback", "failed", role="fallback", source="claude"),
            row("spec@s1#0"),
            row("spec@s2#0", "failed"),
            row("spec@s3#0"),
            row("spec@s1#loop1.0", "skipped"),
        ]
        got = coverage(["spec"], passes, runs)
        self.assertEqual(
            got,
            expected(
                partial=[
                    entry(
                        "spec",
                        [FILE_A, FILE_B, FILE_D],
                        "changed_after_review,shard_cap_exceeded,run_not_completed,spec_rescue",
                    )
                ]
            ),
        )

    def test_tokens_come_from_every_pass_at_or_after_the_last_change(self):
        # FILE_C sits in an excess shard of loop 0 and in a failed shard of loop 1.
        passes = [make_pass(0, split_three(cap=2)), make_pass(1, split_three())]
        runs = [
            row("performance@s1#0"),
            row("performance@s2#0"),
            row("performance@s1#loop1.0"),
            row("performance@s2#loop1.0"),
            row("performance@s3#loop1.0", "failed"),
        ]
        got = coverage(["performance"], passes, runs)
        self.assertEqual(
            got,
            expected(
                partial=[entry("performance", [FILE_C], "shard_cap_exceeded,run_not_completed")]
            ),
        )

    def test_the_reason_has_no_space_and_no_duplicate_token(self):
        shards = [[FILE_A], [FILE_B], [FILE_C]]
        passes = [make_pass(0, manifest(*shards)), make_pass(1, manifest(*shards), fixed=[FILE_A, FILE_B])]
        runs = [row("performance@s1#0"), row("performance@s2#0"), row("performance@s3#0")]
        reason = coverage(["performance"], passes, runs)["partially_reviewed_perspectives"][0]["reason"]
        self.assertEqual(reason, "changed_after_review,run_not_completed")
        self.assertNotIn(" ", reason)
        tokens = reason.split(",")
        self.assertEqual(len(tokens), len(set(tokens)))


# ========================================= AC-5: post-fix invalidation (FR14)


class TestPostFixInvalidation(unittest.TestCase):
    """AC-5 (FR14; TS-5)."""

    def three_passes(self, fixed_by_loop):
        return [
            make_pass(loop, split_three(), fixed=fixed_by_loop.get(loop, ()))
            for loop in (0, 1, 2)
        ]

    def test_a_pre_fix_completed_run_does_not_cover_a_file_the_fix_changed(self):
        passes = [make_pass(0, unsplit_three()), make_pass(1, unsplit_three(), fixed=[FILE_B])]
        got = coverage(["security"], passes, [row("security#0")])
        self.assertEqual(
            got,
            expected(partial=[entry("security", [FILE_B], "changed_after_review,run_not_completed")]),
        )

    def test_a_completed_re_review_of_the_changed_file_covers_it(self):
        passes = [make_pass(0, unsplit_three()), make_pass(1, unsplit_three(), fixed=[FILE_B])]
        got = coverage(["security"], passes, [row("security#0"), row("security#loop1.0")])
        self.assertEqual(got, expected())

    def test_a_re_review_that_did_not_complete_leaves_the_changed_file_unreviewed(self):
        passes = [make_pass(0, unsplit_three()), make_pass(1, unsplit_three(), fixed=[FILE_B])]
        for status in ("skipped", "failed"):
            with self.subTest(status):
                runs = [row("security#0"), row("security#loop1.0", status)]
                got = coverage(["security"], passes, runs)
                self.assertEqual(
                    got,
                    expected(
                        partial=[entry("security", [FILE_B], "changed_after_review,run_not_completed")]
                    ),
                )

    def test_a_file_no_fix_changed_keeps_its_earlier_coverage(self):
        passes = self.three_passes({1: [FILE_B]})
        runs = [
            row("performance@s1#0"),
            row("performance@s2#0"),
            row("performance@s3#0"),
            row("performance@s2#loop1.0"),
        ]
        self.assertEqual(coverage(["performance"], passes, runs), expected())

    def test_a_later_pass_with_no_completed_run_does_not_undo_unchanged_coverage(self):
        passes = self.three_passes({1: [FILE_B]})
        runs = [
            row("performance@s1#0"),
            row("performance@s2#0"),
            row("performance@s3#0"),
            row("performance@s2#loop1.0"),
            row("performance@s1#loop2.0", "failed"),
            row("performance@s2#loop2.0", "skipped"),
            row("performance@s3#loop2.0", "failed"),
        ]
        self.assertEqual(coverage(["performance"], passes, runs), expected())

    def test_the_highest_fix_loop_decides_the_last_change(self):
        passes = self.three_passes({1: [FILE_B], 2: [FILE_B]})
        completed_through_loop_one = [
            row("performance@s1#0"),
            row("performance@s2#0"),
            row("performance@s3#0"),
            row("performance@s2#loop1.0"),
        ]
        got = coverage(["performance"], passes, completed_through_loop_one)
        self.assertEqual(
            got,
            expected(
                partial=[entry("performance", [FILE_B], "changed_after_review,run_not_completed")]
            ),
        )
        with_loop_two = completed_through_loop_one + [row("performance@s2#loop2.0")]
        self.assertEqual(coverage(["performance"], passes, with_loop_two), expected())

    def test_a_pass_at_or_after_the_last_change_covers_the_file(self):
        passes = self.three_passes({1: [FILE_B]})
        runs = [
            row("performance@s1#0"),
            row("performance@s2#0"),
            row("performance@s3#0"),
            row("performance@s2#loop2.0"),
        ]
        self.assertEqual(coverage(["performance"], passes, runs), expected())

    def test_pass_order_in_the_input_does_not_matter(self):
        passes = self.three_passes({1: [FILE_B], 2: [FILE_A]})
        runs = [
            row("performance@s1#0"),
            row("performance@s2#0"),
            row("performance@s3#0"),
            row("performance@s2#loop1.0"),
        ]
        in_order = coverage(["performance"], passes, runs)
        shuffled = coverage(["performance"], [passes[2], passes[0], passes[1]], runs)
        self.assertEqual(in_order, shuffled)
        self.assertEqual(
            in_order,
            expected(
                partial=[entry("performance", [FILE_A], "changed_after_review,run_not_completed")]
            ),
        )

    def test_a_changed_file_in_an_excess_shard_of_the_re_review_is_cap_exceeded(self):
        passes = [
            make_pass(0, split_three()),
            make_pass(1, split_three(cap=2), fixed=[FILE_C]),
        ]
        runs = [
            row("performance@s1#0"),
            row("performance@s2#0"),
            row("performance@s3#0"),
            row("performance@s1#loop1.0"),
            row("performance@s2#loop1.0"),
        ]
        got = coverage(["performance"], passes, runs)
        self.assertEqual(
            got,
            expected(
                partial=[entry("performance", [FILE_C], "changed_after_review,shard_cap_exceeded")]
            ),
        )

    def test_a_pre_change_failure_is_not_a_reason_for_the_final_content(self):
        passes = [
            make_pass(0, split_three()),
            make_pass(1, split_three(cap=2), fixed=[FILE_C]),
        ]
        runs = [
            row("performance@s1#0"),
            row("performance@s2#0"),
            row("performance@s3#0", "failed"),
            row("performance@s1#loop1.0"),
            row("performance@s2#loop1.0"),
        ]
        got = coverage(["performance"], passes, runs)
        self.assertEqual(
            got,
            expected(partial=[entry("performance", [FILE_C], "shard_cap_exceeded")]),
        )

    def test_a_file_changed_by_the_fix_of_one_perspectives_pass_is_judged_per_perspective(self):
        passes = [make_pass(0, unsplit_three()), make_pass(1, unsplit_three(), fixed=[FILE_B])]
        runs = [
            row("security#0"),
            row("security#loop1.0"),
            row("performance#0"),
            row("performance#loop1.0", "failed"),
        ]
        got = coverage(["security", "performance"], passes, runs)
        self.assertEqual(
            got,
            expected(
                partial=[entry("performance", [FILE_B], "changed_after_review,run_not_completed")]
            ),
        )

    def test_a_completed_run_before_the_fix_is_not_counted_by_a_later_unrelated_pass(self):
        passes = [
            make_pass(0, unsplit(FILE_A, FILE_B)),
            make_pass(1, unsplit(FILE_A, FILE_B), fixed=[FILE_A, FILE_B]),
        ]
        got = coverage(["security"], passes, [row("security#0"), row("security#loop1.0", "failed")])
        self.assertEqual(got, expected(unreviewed=["security"]))

    def test_fixed_files_at_loop_zero_change_nothing(self):
        passes = [make_pass(0, unsplit_three(), fixed=[FILE_A, FILE_B])]
        self.assertEqual(coverage(["security"], passes, [row("security#0")]), expected())


# ======================================================= AC-6: spec rescue


class TestSpecRescueRuns(unittest.TestCase):
    """AC-6 (FR11; TS-5): a spec rescue run is any spec row with a shard."""

    FULL_DIFF_FAILED = [
        row("spec#0", "failed"),
        row("spec#1", "skipped", skip_reason="review_data_too_large"),
        row("spec#fallback", "failed", role="fallback", source="claude"),
    ]

    def test_every_rescue_shard_completing_still_leaves_spec_partial(self):
        runs = self.FULL_DIFF_FAILED + [
            row("spec@s1#0"),
            row("spec@s2#0"),
            row("spec@s3#0"),
        ]
        got = coverage(["spec"], loop_zero_only(split_three()), runs)
        self.assertEqual(got, expected(partial=[entry("spec", [], "spec_rescue")]))

    def test_a_later_full_diff_completion_does_not_clear_the_rescue_mark(self):
        passes = [make_pass(0, split_three()), make_pass(1, split_three(), fixed=[FILE_A])]
        runs = self.FULL_DIFF_FAILED + [
            row("spec@s1#0"),
            row("spec@s2#0"),
            row("spec@s3#0"),
            row("spec#loop1.0"),
        ]
        got = coverage(["spec"], passes, runs)
        self.assertEqual(got, expected(partial=[entry("spec", [], "spec_rescue")]))

    def test_a_rescue_mark_of_an_earlier_pass_survives_a_failed_rescue_shard_later(self):
        passes = [make_pass(0, split_three()), make_pass(1, split_three(), fixed=[FILE_A])]
        runs = self.FULL_DIFF_FAILED + [
            row("spec@s1#0"),
            row("spec@s2#0"),
            row("spec@s3#0"),
            row("spec#loop1.0"),
            row("spec@s1#loop1.0", "failed"),
        ]
        got = coverage(["spec"], passes, runs)
        self.assertEqual(got, expected(partial=[entry("spec", [], "spec_rescue")]))

    def test_spec_with_only_failed_rescue_groups_and_no_completed_run_is_unreviewed(self):
        runs = self.FULL_DIFF_FAILED + [
            row("spec@s1#0", "failed"),
            row("spec@s2#0", "skipped", skip_reason="rate_limited"),
            row("spec@s3#0", "failed"),
        ]
        got = coverage(["spec"], loop_zero_only(split_three()), runs)
        self.assertEqual(got, expected(unreviewed=["spec"]))

    def test_spec_with_only_a_failed_rescue_run_and_nothing_else_is_unreviewed(self):
        got = coverage(["spec"], loop_zero_only(split_three()), [row("spec@s1#0", "failed")])
        self.assertEqual(got, expected(unreviewed=["spec"]))

    def test_a_partly_completed_rescue_lists_the_files_of_the_shards_that_did_not_complete(self):
        runs = self.FULL_DIFF_FAILED + [
            row("spec@s1#0"),
            row("spec@s2#0", "failed"),
            row("spec@s3#0", "skipped"),
        ]
        got = coverage(["spec"], loop_zero_only(split_three()), runs)
        self.assertEqual(
            got,
            expected(partial=[entry("spec", [FILE_B, FILE_C], "run_not_completed,spec_rescue")]),
        )

    def test_files_in_excess_shards_stay_unreviewed_for_spec_rescue(self):
        runs = self.FULL_DIFF_FAILED + [row("spec@s1#0"), row("spec@s2#0")]
        got = coverage(["spec"], loop_zero_only(split_three(cap=2)), runs)
        self.assertEqual(
            got,
            expected(
                partial=[
                    entry("spec", [FILE_C], "shard_cap_exceeded,run_not_completed,spec_rescue")
                ]
            ),
        )

    def test_a_completed_full_diff_run_without_rescue_is_fully_reviewed(self):
        runs = [row("spec#0", "failed"), row("spec#fallback", role="fallback", source="claude")]
        got = coverage(["spec"], loop_zero_only(split_three()), runs)
        self.assertEqual(got, expected())

    def test_a_completed_full_diff_run_covers_every_file_of_a_split_pass(self):
        got = coverage(["spec"], loop_zero_only(split_three(cap=1)), [row("spec#0")])
        self.assertEqual(got, expected())

    def test_a_shard_form_run_of_another_perspective_is_not_a_rescue_run(self):
        runs = [row("performance@s1#0"), row("performance@s2#0"), row("performance@s3#0")]
        self.assertEqual(coverage(["performance"], loop_zero_only(split_three()), runs), expected())

    def test_the_rescue_mark_only_belongs_to_spec(self):
        runs = self.FULL_DIFF_FAILED + [
            row("spec@s1#0"),
            row("spec@s2#0"),
            row("spec@s3#0"),
            row("security@s1#0"),
            row("security@s2#0"),
            row("security@s3#0"),
        ]
        got = coverage(["spec", "security"], loop_zero_only(split_three()), runs)
        self.assertEqual(got, expected(partial=[entry("spec", [], "spec_rescue")]))

    def test_a_rescue_run_in_a_loop_pass_counts_for_the_round(self):
        passes = [make_pass(0, unsplit_three()), make_pass(1, split_three(), fixed=[FILE_A])]
        runs = [
            row("spec#0"),
            row("spec#loop1.0", "failed"),
            row("spec@s1#loop1.0"),
            row("spec@s2#loop1.0"),
            row("spec@s3#loop1.0"),
        ]
        got = coverage(["spec"], passes, runs)
        self.assertEqual(got, expected(partial=[entry("spec", [], "spec_rescue")]))

    def test_a_rescue_row_with_a_tool_source_is_not_a_rescue_run(self):
        runs = [row("spec#0"), dict(row("spec@s1#0"), source="tool")]
        self.assertEqual(coverage(["spec"], loop_zero_only(split_three()), runs), expected())


# ========================================================= AC-7: the contract


def mixed_round():
    """A round with an unreviewed, a partial and a fully reviewed perspective."""
    passes = [
        make_pass(0, split_three(cap=2)),
        make_pass(1, split_three(cap=2), fixed=[FILE_A]),
    ]
    runs = [
        row("performance@s1#0"),
        row("performance@s2#0", "failed"),
        row("architecture@s1#0"),
        row("architecture@s2#0"),
        row("architecture@s1#loop1.0"),
        row("architecture@s2#loop1.0"),
        row("comprehensive@s1#0", "skipped"),
        row("spec#0"),
        row("spec#loop1.0"),
        dict(EVALUATOR_ROW),
        dict(TOOL_ROW),
    ]
    return coverage_doc(["performance", "architecture", "comprehensive", "spec"], passes, runs)


class TestOutputShape(unittest.TestCase):
    """AC-7 (TM-9, NFR3): exactly two keys, stable order, no absolute path."""

    def test_the_output_has_exactly_the_two_keys_in_order(self):
        outcome = run_doc(mixed_round())
        self.assertEqual(outcome.code, 0)
        self.assertEqual(
            list(outcome.data()),
            ["unreviewed_perspectives", "partially_reviewed_perspectives"],
        )

    def test_the_mixed_round_result(self):
        self.assertEqual(
            run_doc(mixed_round()).data(),
            expected(
                unreviewed=["performance", "comprehensive"],
                partial=[entry("architecture", [FILE_C], "shard_cap_exceeded")],
            ),
        )

    def test_the_output_is_one_utf8_json_line(self):
        outcome = run_doc(mixed_round())
        self.assertTrue(outcome.stdout.endswith(b"\n"))
        self.assertEqual(outcome.stdout.count(b"\n"), 1)
        outcome.stdout.decode("utf-8")

    def test_no_output_path_is_absolute_and_every_path_is_one_of_the_inputs(self):
        outcome = run_doc(mixed_round())
        known = {FILE_A, FILE_B, FILE_C}
        for partial in outcome.data()["partially_reviewed_perspectives"]:
            for path in partial["unreviewed_files"]:
                self.assertFalse(path.startswith("/"), path)
                self.assertIn(path, known)

    def test_the_output_never_contains_text_from_row_extras(self):
        sentinel = "SENTINEL-row-text-4c1e"
        doc = mixed_round()
        for runs_row in doc["perspective_runs"]:
            runs_row["summary"] = sentinel
            runs_row["model"] = sentinel
        outcome = run_doc(doc)
        self.assertEqual(outcome.code, 0)
        self.assertNotIn(sentinel.encode("utf-8"), outcome.stdout)


BAD_PATHS = [
    ("absolute path", "/etc/passwd"),
    ("absolute path in the project", "/src/a.py"),
    ("parent segment first", "../x.py"),
    ("parent segment inside", "src/../x.py"),
    ("parent segment last", "src/.."),
    ("parent segment alone", ".."),
    ("NUL", "src/a\x00.py"),
    ("CR", "src/a\r.py"),
    ("LF", "src/a\n.py"),
    ("leading dash", "-rf"),
    ("leading dash option-like", "--output=x"),
    ("empty path", ""),
    ("not a string", 5),
    ("null", None),
]

GOOD_AWKWARD_PATHS = ["..hidden/x.py", "src/..x", "src/-dash.py", "src/a b.py", "src/é.py"]


class TestPathRules(RejectionMixin, unittest.TestCase):
    """AC-7 (TM-9): project-relative paths only, in every input position."""

    POSITIONS = ("manifest of the only pass", "manifest of the last pass", "fixed_files")

    @staticmethod
    def put_path(built, path):
        """Replace FILE_A by `path` in both `files` and the shard that holds it."""
        for single in built["files"]:
            if single["path"] == FILE_A:
                single["path"] = path
        for shard in built["shards"]:
            shard["paths"] = [path if p == FILE_A else p for p in shard["paths"]]
        return built

    def with_path_in(self, where, path):
        shards = [[FILE_A], [FILE_B]]
        if where == "manifest of the only pass":
            passes = [make_pass(0, self.put_path(manifest(*shards), path))]
        elif where == "manifest of the last pass":
            passes = [
                make_pass(0, manifest(*shards)),
                make_pass(1, self.put_path(manifest(*shards), path)),
            ]
        else:
            passes = [make_pass(0, manifest(*shards)), make_pass(1, manifest(*shards), fixed=[path])]
        return coverage_doc(["performance"], passes, [row("performance@s1#0")])

    def test_the_valid_baseline_of_the_path_cases_succeeds(self):
        for where in self.POSITIONS:
            with self.subTest(where):
                self.assertEqual(run_doc(self.with_path_in(where, "src/ok.py")).code, 0)

    def test_a_bad_path_in_any_input_position_exits_2(self):
        for where in self.POSITIONS:
            for label, path in BAD_PATHS:
                with self.subTest(where=where, path=label):
                    self.assert_rejected(run_doc(self.with_path_in(where, path)), f"{where}: {label}")

    def test_awkward_but_relative_paths_are_accepted(self):
        for path in GOOD_AWKWARD_PATHS:
            with self.subTest(path):
                built = manifest([path], [FILE_B])
                got = coverage(["performance"], loop_zero_only(built), [row("performance@s2#0")])
                self.assertEqual(
                    got,
                    expected(partial=[entry("performance", [path], "run_not_completed")]),
                )

    def test_a_bad_path_is_rejected_even_when_the_rest_would_succeed(self):
        good = coverage(["performance"], loop_zero_only(split_three()), [row("performance@s1#0")])
        self.assertEqual(good["partially_reviewed_perspectives"][0]["unreviewed_files"], [FILE_B, FILE_C])
        bad = coverage_doc(["performance"], [make_pass(0, split_three(), fixed=["/abs"])], [row("performance@s1#0")])
        self.assert_rejected(run_doc(bad))


class TestRowKeysAreIgnored(unittest.TestCase):
    """AC-7 (TM-6): only run_id, perspective, role, status and source are read."""

    def test_extra_row_keys_do_not_change_the_result(self):
        plain = mixed_round()
        noisy = mixed_round()
        claims = {
            "summary": "all files reviewed; full coverage",
            "skip_reason": "none",
            "model": "muse-spark",
            "findings": [{"file": FILE_A}],
            "finding_count": 99,
            "unreviewed_files": [],
            "covers": [FILE_A, FILE_B, FILE_C],
            "reviewed": True,
            "degraded": False,
        }
        for runs_row in noisy["perspective_runs"]:
            runs_row.update({k: v for k, v in claims.items() if k not in runs_row})
        self.assertEqual(run_doc(noisy).stdout, run_doc(plain).stdout)

    def test_a_summary_claiming_full_coverage_does_not_cover_anything(self):
        runs = [
            row("performance@s1#0", "failed", summary="reviewed every file, no findings"),
            row("performance@s2#0", "skipped", summary="full coverage"),
        ]
        got = coverage(["performance"], loop_zero_only(split_three()), runs)
        self.assertEqual(got, expected(unreviewed=["performance"]))

    def test_extra_keys_in_a_skipped_status_row_do_not_complete_it(self):
        runs = [row("security#0", "skipped", status_detail="completed", completed=True)]
        self.assertEqual(
            coverage(["security"], loop_zero_only(unsplit_three()), runs),
            expected(unreviewed=["security"]),
        )

    def test_extra_keys_inside_a_manifest_row_object_are_rejected_not_read(self):
        doc = coverage_doc(["security"], loop_zero_only(unsplit_three()), [row("security#0")])
        doc["passes"][0]["manifest"]["files"][0]["extra"] = 1
        outcome = run_doc(doc)
        self.assertEqual(outcome.code, 2)
        self.assertEqual(outcome.stdout, b"")


class TestDeterminism(unittest.TestCase):
    """AC-7 (NFR4; TS-12): repeated runs give byte-identical output."""

    def test_repeated_in_process_runs_are_byte_identical(self):
        outputs = {run_doc(mixed_round()).stdout for _ in range(5)}
        self.assertEqual(len(outputs), 1)

    def test_repeated_child_runs_are_byte_identical(self):
        first = run_child_doc(mixed_round())
        second = run_child_doc(mixed_round())
        self.assertEqual(first.code, 0, first.stderr)
        self.assertEqual(first.stdout, second.stdout)
        self.assertEqual(first.stdout, run_doc(mixed_round()).stdout)

    def test_hash_randomization_does_not_change_the_output(self):
        outputs = set()
        for seed in ("0", "1", "12345"):
            env = dict(os.environ, PYTHONHASHSEED=seed)
            outcome = run_child_doc(mixed_round(), env=env)
            self.assertEqual(outcome.code, 0, outcome.stderr)
            outputs.add(outcome.stdout)
        self.assertEqual(len(outputs), 1)

    def test_the_input_order_of_manifest_files_does_not_change_the_output(self):
        doc = mixed_round()
        shuffled = mixed_round()
        for single in shuffled["passes"]:
            single["manifest"]["files"].reverse()
            for shard in single["manifest"]["shards"]:
                shard["paths"].reverse()
        self.assertEqual(run_doc(shuffled).stdout, run_doc(doc).stdout)

    def test_classification_is_byte_identical_too(self):
        doc = classify_doc([item("a#0"), item("b#0", "codex", 0, NON_JSON)])
        self.assertEqual(run_doc(doc).stdout, run_doc(doc).stdout)
        self.assertEqual(run_child_doc(doc).stdout, run_doc(doc).stdout)


class TestInputDocumentChecks(RejectionMixin, unittest.TestCase):
    """The document-level checks shared by both operations."""

    def test_an_unknown_or_missing_operation_exits_2(self):
        for operation in (None, "", "classify", "COVERAGE", 5, ["coverage"]):
            with self.subTest(repr(operation)):
                self.assert_rejected(run_doc({"operation": operation, "results": []}))
        self.assert_rejected(run_doc({"results": []}))

    def test_a_member_of_the_other_operation_exits_2(self):
        doc = coverage_doc(["security"], loop_zero_only(unsplit_three()), [])
        self.assert_rejected(run_doc(dict(doc, results=[])))
        self.assert_rejected(run_doc(dict(classify_doc([]), passes=[])))

    def test_a_missing_member_exits_2(self):
        doc = coverage_doc(["security"], loop_zero_only(unsplit_three()), [])
        for name in ("perspectives", "passes", "perspective_runs"):
            with self.subTest(name):
                self.assert_rejected(run_doc({k: v for k, v in doc.items() if k != name}))

    def test_a_document_that_is_not_an_object_exits_2(self):
        for raw in (b"[]", b"null", b"5", b'"x"', b"true"):
            with self.subTest(raw):
                self.assert_rejected(run_bytes(raw))

    def test_invalid_json_exits_2(self):
        for raw in (b"", b"{", b"not json", b'{"operation": }', b"{'operation': 'coverage'}"):
            with self.subTest(raw):
                self.assert_rejected(run_bytes(raw))

    def test_invalid_utf8_exits_2(self):
        self.assert_rejected(run_bytes(b'{"operation": "classify_results", "results": [], "x": "\xff"}'))

    def test_non_finite_numbers_exit_2(self):
        raw = b'{"operation": "classify_results", "results": [{"run_id": "x#0", "origin": "codex", "finding_count": NaN, "summary": ""}]}'
        self.assert_rejected(run_bytes(raw))
        raw = raw.replace(b"NaN", b"Infinity")
        self.assert_rejected(run_bytes(raw))

    def test_a_repeated_key_exits_2(self):
        raw = b'{"operation": "classify_results", "results": [], "results": []}'
        self.assert_rejected(run_bytes(raw))

    def test_deep_nesting_exits_2_instead_of_crashing(self):
        raw = b'{"operation": "classify_results", "results": ' + b"[" * 100000 + b"]" * 100000 + b"}"
        self.assert_rejected(run_bytes(raw))


class TestCoverageInputChecks(RejectionMixin, unittest.TestCase):
    """The `coverage` input checks (pre-conditions of the contract)."""

    def doc(self, **changes):
        base = coverage_doc(["security"], loop_zero_only(unsplit_three()), [row("security#0")])
        base.update(changes)
        return base

    def test_the_valid_baseline_succeeds(self):
        self.assertEqual(run_doc(self.doc()).code, 0)

    def test_perspectives_must_be_unique_names_without_vulnerability(self):
        for label, bad in (
            ("not a list", "security"),
            ("a duplicate", ["security", "security"]),
            ("vulnerability", ["security", "vulnerability"]),
            ("vulnerability alone", ["vulnerability"]),
            ("a number", [5]),
            ("null", [None]),
            ("empty name", [""]),
            ("a name with a hash", ["sec#urity"]),
            ("a name with an at sign", ["sec@urity"]),
            ("a name with a space", ["sec urity"]),
            ("a name with a newline", ["security\n"]),
        ):
            with self.subTest(label):
                self.assert_rejected(run_doc(self.doc(perspectives=bad)), label)

    def test_passes_must_be_a_list_of_complete_objects(self):
        good = loop_zero_only(unsplit_three())[0]
        for label, bad in (
            ("not a list", {"loop": 0}),
            ("an item that is not an object", [good, 5]),
            ("a missing loop", [{k: v for k, v in good.items() if k != "loop"}]),
            ("a missing fixed_files", [{k: v for k, v in good.items() if k != "fixed_files"}]),
            ("a missing manifest", [{k: v for k, v in good.items() if k != "manifest"}]),
            ("an extra key", [dict(good, note="x")]),
            ("no passes", []),
        ):
            with self.subTest(label):
                self.assert_rejected(run_doc(self.doc(passes=bad)), label)

    def test_loops_must_be_unique_non_negative_integers_and_loop_zero_present(self):
        for label, bad in (
            ("loop zero missing", [make_pass(1, unsplit_three())]),
            ("a duplicate loop", [make_pass(0, unsplit_three()), make_pass(0, unsplit_three())]),
            ("a negative loop", [make_pass(0, unsplit_three()), make_pass(-1, unsplit_three())]),
            ("a boolean loop", [make_pass(0, unsplit_three()), make_pass(True, unsplit_three())]),
            ("a float loop", [make_pass(0.0, unsplit_three())]),
            ("a string loop", [make_pass("0", unsplit_three())]),
            ("a null loop", [make_pass(None, unsplit_three())]),
        ):
            with self.subTest(label):
                self.assert_rejected(run_doc(self.doc(passes=bad)), label)

    def test_a_gap_in_the_loops_is_accepted(self):
        passes = [make_pass(0, unsplit_three()), make_pass(2, unsplit_three(), fixed=[FILE_A])]
        got = coverage(["security"], passes, [row("security#0"), row("security#loop2.0")])
        self.assertEqual(got, expected())

    def test_fixed_files_must_be_a_list_of_paths(self):
        for label, bad in (("a string", FILE_A), ("null", None), ("a mapping", {FILE_A: 1}), ("a number", 5)):
            with self.subTest(label):
                passes = [make_pass(0, unsplit_three())]
                passes[0]["fixed_files"] = bad
                self.assert_rejected(run_doc(self.doc(passes=passes)), label)

    def test_the_manifest_must_have_exactly_the_review_shards_keys(self):
        for key in MANIFEST_KEYS:
            with self.subTest(missing=key):
                passes = loop_zero_only(unsplit_three())
                del passes[0]["manifest"][key]
                self.assert_rejected(run_doc(self.doc(passes=passes)), key)
        passes = loop_zero_only(unsplit_three())
        passes[0]["manifest"]["extra"] = 1
        self.assert_rejected(run_doc(self.doc(passes=passes)), "extra key")

    def test_manifest_member_types_are_checked(self):
        bad_values = {
            "limit": ("x", None, 1.5, True),
            "total_chars": ("x", None, -1, True),
            "split": ("false", None, 0, 1),
            "files": ("x", None, {}, [5], [{"path": FILE_A}], [{"path": FILE_A, "chars": -1}], [{"path": FILE_A, "chars": "1"}]),
            "shards": ("x", None, {}, [5], [{"index": 1, "paths": [FILE_A]}], [{"index": 0, "paths": [], "chars": 0}], [{"index": "1", "paths": [], "chars": 0}]),
            "shard_cap": ("x", None, -1, 1.5, True),
            "dispatched_shards": ("x", None, [True], ["1"], [1.5]),
            "excess_shards": ("x", None, [True], ["1"], [1.5]),
        }
        for key, values in bad_values.items():
            for bad in values:
                with self.subTest(key=key, value=repr(bad)):
                    passes = loop_zero_only(unsplit_three())
                    passes[0]["manifest"][key] = bad
                    self.assert_rejected(run_doc(self.doc(passes=passes)), key)

    def test_the_manifest_must_be_consistent(self):
        def build(change):
            passes = loop_zero_only(split_three())
            change(passes[0]["manifest"])
            return self.doc(passes=passes, perspective_runs=[row("security@s1#0")])

        def path_not_in_files(m):
            m["shards"][0]["paths"] = ["src/zzz.py"]

        def file_in_two_shards(m):
            m["shards"][1]["paths"].append(FILE_A)

        def file_in_no_shard(m):
            m["shards"][2]["paths"] = []

        def repeated_file(m):
            m["files"].append(dict(m["files"][0]))

        def repeated_shard_index(m):
            m["shards"][1]["index"] = 1

        def dispatched_unknown(m):
            m["dispatched_shards"] = [1, 2, 9]
            m["excess_shards"] = [3]

        def overlap(m):
            m["dispatched_shards"] = [1, 2, 3]
            m["excess_shards"] = [3]

        def shard_in_neither(m):
            m["dispatched_shards"] = [1, 2]
            m["excess_shards"] = []

        def repeated_dispatched(m):
            m["dispatched_shards"] = [1, 1, 2]
            m["excess_shards"] = [3]

        for label, change in (
            ("a shard path outside files", path_not_in_files),
            ("a file in two shards", file_in_two_shards),
            ("a file in no shard", file_in_no_shard),
            ("a repeated file", repeated_file),
            ("a repeated shard index", repeated_shard_index),
            ("a dispatched index that is no shard", dispatched_unknown),
            ("a shard both dispatched and excess", overlap),
            ("a shard neither dispatched nor excess", shard_in_neither),
            ("a repeated dispatched index", repeated_dispatched),
        ):
            with self.subTest(label):
                self.assert_rejected(run_doc(build(change)), label)

    def test_rows_must_be_objects_with_known_statuses(self):
        for label, bad in (
            ("a row that is not an object", "security#0"),
            ("a row that is null", None),
            ("an unknown status", dict(row("security#0"), status="done")),
            ("a status in another case", dict(row("security#0"), status="Completed")),
            ("a status that is not a string", dict(row("security#0"), status=True)),
            ("a missing status", {k: v for k, v in row("security#0").items() if k != "status"}),
            ("a missing perspective", {k: v for k, v in row("security#0").items() if k != "perspective"}),
            ("a perspective that is not a string", dict(row("security#0"), perspective=["security"])),
            ("a missing role", {k: v for k, v in row("security#0").items() if k != "role"}),
            ("a missing source", {k: v for k, v in row("security#0").items() if k != "source"}),
            ("a role that is not a string", dict(row("security#0"), role=5)),
            ("a source that is not a string", dict(row("security#0"), source=5)),
        ):
            with self.subTest(label):
                self.assert_rejected(run_doc(self.doc(perspective_runs=[bad])), label)

    def test_perspective_runs_must_be_a_list(self):
        for bad in (None, {}, "x", 5):
            with self.subTest(repr(bad)):
                self.assert_rejected(run_doc(self.doc(perspective_runs=bad)))

    def test_a_row_for_an_unlisted_perspective_exits_2(self):
        runs = [row("security#0"), row("performance#0")]
        self.assert_rejected(run_doc(self.doc(perspective_runs=runs)))

    def test_source_litellm_and_claude_fallback_rows_are_read_alike(self):
        runs = [
            row("security#0", "skipped", source="codex"),
            row("security#1", "failed", source="litellm", model="muse-spark"),
            row("security#fallback", "completed", role="fallback", source="claude"),
        ]
        self.assertEqual(
            coverage(["security"], loop_zero_only(unsplit_three()), runs), expected()
        )


class TestCommandLineContract(RejectionMixin, unittest.TestCase):
    """AC-7 (NFR6): the script interface of the Conventions section."""

    def test_a_successful_run_exits_0_with_json_on_stdout_and_nothing_on_stderr(self):
        outcome = run_child_doc(mixed_round())
        self.assertEqual(outcome.code, 0, outcome.stderr)
        self.assertEqual(outcome.stderr, "")
        self.assertEqual(outcome.data(), run_doc(mixed_round()).data())

    def test_the_classification_runs_as_a_child_process(self):
        outcome = run_child_doc(classify_doc([item("a#0"), item("b#0", "claude")]))
        self.assertEqual(outcome.code, 0, outcome.stderr)
        self.assertEqual(
            outcome.data(),
            {"results": [{"run_id": "a#0", "status": "failed"}, {"run_id": "b#0", "status": "completed"}]},
        )

    def test_any_argument_count_but_one_is_a_usage_error(self):
        for args in ([], ["one", "two"], ["a", "b", "c"]):
            with self.subTest(args):
                outcome = run_child(args)
                self.assert_rejected(outcome)
                self.assertIn("usage: python3 review-coverage.py", outcome.stderr)

    def test_an_argument_beginning_with_a_dash_is_a_file_name(self):
        for name in ("-h", "--help", "-x.json"):
            with self.subTest(name):
                outcome = run_child([name])
                self.assert_rejected(outcome)
                self.assertIn("cannot read", outcome.stderr)

    def test_a_missing_or_unreadable_input_exits_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            for target in (os.path.join(tmp, "absent.json"), tmp):
                outcome = run_child([target])
                self.assert_rejected(outcome)
                self.assertIn("cannot read the input document", outcome.stderr)

    def test_the_output_does_not_depend_on_the_locale(self):
        doc = coverage_doc(
            ["performance"],
            loop_zero_only(manifest(["src/ok.py"], ["docs/日本語.md"])),
            [row("performance@s1#0")],
        )
        env = {k: v for k, v in os.environ.items() if k not in (
            "LANG", "LANGUAGE", "LC_ALL", "LC_CTYPE", "PYTHONUTF8", "PYTHONIOENCODING", "PYTHONCOERCECLOCALE",
        )}
        env["LC_ALL"] = "C"
        outcome = run_child_doc(doc, env=env)
        self.assertEqual(outcome.code, 0, outcome.stderr)
        self.assertIn("日本語".encode("utf-8"), outcome.stdout)

    def test_every_error_names_the_program_on_stderr(self):
        outcome = run_child_doc({"operation": "nope"})
        self.assert_rejected(outcome)
        self.assertIn("review-coverage", outcome.stderr)


# ------------------------------------------------- standard-library check ----


def imported_modules(source):
    """The top-level name of every import in `source`; relative imports
    appear as dotted names beginning with `.`."""
    modules = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            modules.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                modules.add("." * node.level + (node.module or ""))
            else:
                modules.add(node.module.split(".")[0])
    return modules


def non_stdlib_modules(source):
    return {m for m in imported_modules(source) if m not in sys.stdlib_module_names}


FORBIDDEN_FACILITIES = {
    "subprocess",
    "socket",
    "urllib",
    "http",
    "ftplib",
    "smtplib",
    "shutil",
    "tempfile",
    "multiprocessing",
    "ctypes",
}


class TestStandardLibraryOnly(unittest.TestCase):
    """AC-7 (NFR6; TS-13): standard library only, `unittest` for the tests."""

    def test_the_script_imports_only_standard_library_modules(self):
        self.assertEqual(non_stdlib_modules(SCRIPT.read_text(encoding="utf-8")), set())

    def test_this_module_imports_only_standard_library_modules(self):
        self.assertEqual(non_stdlib_modules(THIS_MODULE.read_text(encoding="utf-8")), set())

    def test_this_module_uses_unittest_and_no_other_test_framework(self):
        modules = imported_modules(THIS_MODULE.read_text(encoding="utf-8"))
        self.assertIn("unittest", modules)
        self.assertFalse(modules & {"pytest", "nose", "nose2", "hypothesis", "mock"})

    def test_the_checker_flags_third_party_and_relative_imports(self):
        source = "import json\nimport yaml\nfrom requests import get\nfrom . import sibling\n"
        self.assertEqual(non_stdlib_modules(source), {"yaml", "requests", "."})
        self.assertEqual(non_stdlib_modules("import json\nfrom unittest import mock\n"), set())

    def test_the_script_starts_no_process_and_opens_no_network_facility(self):
        found = imported_modules(SCRIPT.read_text(encoding="utf-8")) & FORBIDDEN_FACILITIES
        self.assertEqual(found, set())

    def test_the_facility_checker_flags_a_forged_import(self):
        forged = "import json\nimport subprocess\nfrom urllib import request\n"
        self.assertEqual(imported_modules(forged) & FORBIDDEN_FACILITIES, {"subprocess", "urllib"})

    def test_the_script_opens_only_the_input_document(self):
        tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
        modes = []
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "open"
            ):
                mode = "r"
                if len(node.args) > 1 and isinstance(node.args[1], ast.Constant):
                    mode = node.args[1].value
                modes.append(mode)
        self.assertEqual(modes, ["rb"])


if __name__ == "__main__":
    unittest.main()
