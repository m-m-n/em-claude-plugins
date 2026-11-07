#!/usr/bin/env python3
"""Review result classification and coverage determination (em-workflow
plugin, task0003 of feature-docs/large-diff-review-coverage; FR3, FR4, FR8,
FR9, FR11, FR13, FR14, FR18, NFR3, NFR4, NFR6).

The review phase's orchestrator -- never a reviewer -- runs this script. It
decides, from run_ids, run statuses and shard manifests alone, which results
count as failed and which perspectives went unreviewed or only partly
reviewed. It reads no diff text and no file of the reviewed tree, so no
review content can reach the orchestrator's context through it.

CLI contract:
    python3 review-coverage.py INPUT_DOCUMENT
  Exactly one argument: the path of the input document. The script defines
  no options: the argument is a file name even when it begins with `-`. Any
  other argument count is a usage error.

Input document: one UTF-8 JSON object whose `operation` member selects one
of two operations. A missing member, a member not listed for the selected
operation, an unknown operation or a repeated key is invalid input.

  classify_results   members: results
      results   a list of objects with exactly `run_id` (non-empty string),
                `origin` (`codex`, `litellm` or `claude`, the harness the
                orchestrator recorded at dispatch), `finding_count` (integer
                of 0 or more) and `summary` (string).
      Output: {"results": [{"run_id", "status"}, ...]} in input order.
      `status` is `failed` exactly when `origin` is `litellm`,
      `finding_count` is 0 and `summary` is identical, character for
      character, to `litellm model output truncated` or
      `litellm returned non-JSON output` (no trimming, no case folding, no
      prefix match). Every other result is `completed`.

  coverage   members: perspectives, passes, perspective_runs
      perspectives      the Task-dispatched perspectives of the round, in
                        dispatch order: unique names of letters, digits,
                        `_` and `-`, never `vulnerability`.
      passes            a list of objects with exactly `loop` (integer of 0
                        or more, unique; loop 0 is required), `fixed_files`
                        (paths the fix of that loop changed) and `manifest`
                        (the review-shards output, verbatim: exactly the
                        keys limit, total_chars, split, files, shards,
                        shard_cap, dispatched_shards, excess_shards; the
                        files are partitioned by the shards; every shard
                        index is dispatched or excess, not both). The
                        coverage universe is the file list of the pass with
                        the highest loop.
      perspective_runs  rows as recorded, in recording order. Only `run_id`,
                        `perspective`, `role`, `status` (`completed`,
                        `skipped` or `failed`) and `source` are read; any
                        other key is ignored. Rows with `role` `evaluator`
                        or `source` `tool` are skipped before any other row
                        check.
      Output: {"unreviewed_perspectives": [...],
               "partially_reviewed_perspectives":
                   [{"perspective", "unreviewed_files", "reason"}, ...]}
      Both lists follow the order of `perspectives` and are always present.

run_id grammar (D1):
    {perspective}[@s{k}]#[loop{N}.]{chain_index|fallback}
  `k` and `N` are integers of 1 or more without leading zeros; the chain
  index is a canonical integer of 0 or more (no leading zeros). The
  perspective part must equal the row's `perspective`. A run_id is invalid
  when it repeats an earlier row's run_id, names a loop with no pass, has a
  shard index on a pass whose manifest is unsplit, names a shard that is not
  in the pass's `dispatched_shards`, or (for a perspective other than
  `spec`) has no shard index on a split pass.

Coverage rules (D5, D8):
  * Rows are grouped by perspective, shard and loop; the last row of a group
    decides it. A run without a shard covers every file of its pass
    manifest; a run with shard k covers shard k of its pass.
  * A file's last change loop is the highest loop whose `fixed_files` holds
    it, or 0. A file is reviewed for a perspective when a group that ended
    `completed` covers it in a pass whose loop is at or above that loop.
  * A perspective is unreviewed when no group ended `completed`, or when the
    universe is not empty and no file is reviewed.
  * Any other perspective with an unreviewed file, or `spec` with a rescue
    run, is partial. A spec rescue run is any spec row with a shard index,
    whatever its status or pass. Its presence anywhere in the round adds
    `spec_rescue` to spec's reason and makes spec partial even with no
    unreviewed file, unless spec is unreviewed.
  * `reason` joins the tokens that apply with `,` and no space, in this
    order. Each token is judged over the perspective's unreviewed files:
      changed_after_review  a completed group covered the file in a pass
                            before its last change loop
      shard_cap_exceeded    the file is in an excess shard of a pass at or
                            after its last change loop
      run_not_completed     in a pass at or after its last change loop, the
                            file is in a dispatched shard, or the
                            perspective ran a no-shard group in that pass;
                            since the file is unreviewed, that unit did not
                            end `completed`
      spec_rescue           spec ran rescue runs this round

Paths: every path is project-relative and `/`-separated. A path that is
empty, absolute, holds a `..` segment, NUL, CR or LF, or begins with `-`,
makes the input invalid.

Output: stdout carries one JSON object, UTF-8 encoded whatever the locale,
non-ASCII characters unescaped, stable key order, followed by a newline.

Exit codes:
    0   success
    2   usage error, invalid input, an input document that cannot be read
        or parsed, or an unexpected failure; a message on stderr and
        nothing on stdout

Isolation: standard library only. The script reads only the input document,
starts no child process, opens no network connection and writes no file.
"""

import json
import re
import sys

PROGRAM = "review-coverage"

USAGE = (
    "usage: python3 review-coverage.py INPUT_DOCUMENT\n"
    "  INPUT_DOCUMENT is the path of one UTF-8 JSON object whose `operation`\n"
    "  member is classify_results or coverage.\n"
    "  Exit codes: 0 success, 2 usage error, invalid input or failure.\n"
)

OPERATION_MEMBERS = {
    "classify_results": ("results",),
    "coverage": ("perspectives", "passes", "perspective_runs"),
}

ORIGINS = frozenset({"codex", "litellm", "claude"})
LITELLM_EMPTY_SUMMARIES = (
    "litellm model output truncated",
    "litellm returned non-JSON output",
)

STATUSES = frozenset({"completed", "skipped", "failed"})
MANIFEST_KEYS = (
    "limit",
    "total_chars",
    "split",
    "files",
    "shards",
    "shard_cap",
    "dispatched_shards",
    "excess_shards",
)

SPEC = "spec"
VULNERABILITY = "vulnerability"

CHANGED_AFTER_REVIEW = "changed_after_review"
SHARD_CAP_EXCEEDED = "shard_cap_exceeded"
RUN_NOT_COMPLETED = "run_not_completed"
SPEC_RESCUE = "spec_rescue"
REASON_ORDER = (
    CHANGED_AFTER_REVIEW,
    SHARD_CAP_EXCEEDED,
    RUN_NOT_COMPLETED,
    SPEC_RESCUE,
)

_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*")
_RUN_ID = re.compile(
    r"(?P<perspective>[A-Za-z0-9][A-Za-z0-9_-]*)"
    r"(?:@s(?P<shard>[1-9][0-9]*))?"
    r"#(?:loop(?P<loop>[1-9][0-9]*)\.)?"
    r"(?P<last>0|[1-9][0-9]*|fallback)"
)


class InputError(ValueError):
    """The input document is invalid; reported on stderr with exit code 2."""


# ------------------------------------------------------------ validation ----


def _show(value):
    text = repr(value)
    return text if len(text) <= 60 else text[:57] + "..."


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _check_count(value, where):
    if not _is_int(value) or value < 0:
        raise InputError(f"{where} must be an integer of 0 or more, got {_show(value)}")
    return value


def _check_list(value, where):
    if not isinstance(value, list):
        raise InputError(f"{where} must be a list, got {_show(value)}")
    return value


def _check_object(value, where, keys):
    """`value` must be an object with exactly the members `keys`."""
    if not isinstance(value, dict):
        raise InputError(f"{where} must be an object, got {_show(value)}")
    for name in keys:
        if name not in value:
            raise InputError(f"{where}: the member {name} is missing")
    for name in value:
        if name not in keys:
            raise InputError(f"{where}: the member {name} is not accepted")
    return value


def _check_path(value, where):
    if not isinstance(value, str) or value == "":
        raise InputError(f"{where}: a path must be a non-empty string, got {_show(value)}")
    if "\x00" in value or "\r" in value or "\n" in value:
        raise InputError(f"{where}: a path must not hold NUL, CR or LF, got {_show(value)}")
    if value.startswith("/"):
        raise InputError(f"{where}: an absolute path is not accepted, got {_show(value)}")
    if value.startswith("-"):
        raise InputError(f"{where}: a path must not begin with `-`, got {_show(value)}")
    if ".." in value.split("/"):
        raise InputError(f"{where}: a `..` segment is not accepted, got {_show(value)}")
    return value


def _check_results(results):
    _check_list(results, "results")
    for position, result in enumerate(results):
        where = f"results[{position}]"
        _check_object(result, where, ("run_id", "origin", "finding_count", "summary"))
        run_id = result["run_id"]
        if not isinstance(run_id, str) or run_id == "":
            raise InputError(f"{where}.run_id must be a non-empty string, got {_show(run_id)}")
        origin = result["origin"]
        if not isinstance(origin, str) or origin not in ORIGINS:
            raise InputError(
                f"{where}.origin must be one of {sorted(ORIGINS)}, got {_show(origin)}"
            )
        _check_count(result["finding_count"], f"{where}.finding_count")
        if not isinstance(result["summary"], str):
            raise InputError(
                f"{where}.summary must be a string, got {_show(result['summary'])}"
            )


def _check_perspectives(perspectives):
    _check_list(perspectives, "perspectives")
    seen = set()
    for position, name in enumerate(perspectives):
        where = f"perspectives[{position}]"
        if not isinstance(name, str) or _NAME.fullmatch(name) is None:
            raise InputError(
                f"{where} must be a name of letters, digits, `_` and `-`, got {_show(name)}"
            )
        if name == VULNERABILITY:
            raise InputError(f"{where}: `{VULNERABILITY}` is not a Task-dispatched perspective")
        if name in seen:
            raise InputError(f"{where}: the perspective {name} is repeated")
        seen.add(name)


class _Pass:
    """One validated coverage pass (D3)."""

    __slots__ = (
        "loop",
        "fixed_files",
        "files",
        "file_set",
        "split",
        "shard_paths",
        "shard_of",
        "dispatched",
        "excess",
    )


def _check_index_list(value, where, shard_indexes):
    _check_list(value, where)
    seen = set()
    for index in value:
        if not _is_int(index):
            raise InputError(f"{where} must hold integers, got {_show(index)}")
        if index not in shard_indexes:
            raise InputError(f"{where}: {index} is not a shard index of the manifest")
        if index in seen:
            raise InputError(f"{where}: the index {index} is repeated")
        seen.add(index)
    return seen


def _check_manifest(manifest, where, built):
    _check_object(manifest, where, MANIFEST_KEYS)
    for name in ("limit", "total_chars", "shard_cap"):
        _check_count(manifest[name], f"{where}.{name}")
    if not isinstance(manifest["split"], bool):
        raise InputError(f"{where}.split must be a boolean, got {_show(manifest['split'])}")

    files = []
    for position, entry in enumerate(_check_list(manifest["files"], f"{where}.files")):
        item = f"{where}.files[{position}]"
        _check_object(entry, item, ("path", "chars"))
        files.append(_check_path(entry["path"], f"{item}.path"))
        _check_count(entry["chars"], f"{item}.chars")
    file_set = set(files)
    if len(file_set) != len(files):
        raise InputError(f"{where}.files: a path is repeated")

    shard_paths = {}
    shard_of = {}
    for position, entry in enumerate(_check_list(manifest["shards"], f"{where}.shards")):
        item = f"{where}.shards[{position}]"
        _check_object(entry, item, ("index", "paths", "chars"))
        index = entry["index"]
        if not _is_int(index) or index < 1:
            raise InputError(f"{item}.index must be an integer of 1 or more, got {_show(index)}")
        if index in shard_paths:
            raise InputError(f"{item}: the shard index {index} is repeated")
        _check_count(entry["chars"], f"{item}.chars")
        paths = []
        for path_position, path in enumerate(_check_list(entry["paths"], f"{item}.paths")):
            path = _check_path(path, f"{item}.paths[{path_position}]")
            if path not in file_set:
                raise InputError(f"{item}: the path {_show(path)} is not in files")
            if path in shard_of:
                raise InputError(f"{item}: the path {_show(path)} is in more than one shard")
            shard_of[path] = index
            paths.append(path)
        shard_paths[index] = tuple(paths)
    for path in files:
        if path not in shard_of:
            raise InputError(f"{where}: the file {_show(path)} is in no shard")

    dispatched = _check_index_list(
        manifest["dispatched_shards"], f"{where}.dispatched_shards", shard_paths
    )
    excess = _check_index_list(manifest["excess_shards"], f"{where}.excess_shards", shard_paths)
    if dispatched & excess:
        raise InputError(f"{where}: a shard is both dispatched and excess")
    if dispatched | excess != set(shard_paths):
        raise InputError(f"{where}: every shard must be dispatched or excess")

    built.files = tuple(files)
    built.file_set = frozenset(files)
    built.split = manifest["split"]
    built.shard_paths = shard_paths
    built.shard_of = shard_of
    built.dispatched = frozenset(dispatched)
    built.excess = frozenset(excess)


def _check_passes(passes):
    """Validate `passes`; returns the passes by loop."""
    _check_list(passes, "passes")
    by_loop = {}
    for position, entry in enumerate(passes):
        where = f"passes[{position}]"
        _check_object(entry, where, ("loop", "fixed_files", "manifest"))
        loop = entry["loop"]
        if not _is_int(loop) or loop < 0:
            raise InputError(f"{where}.loop must be an integer of 0 or more, got {_show(loop)}")
        if loop in by_loop:
            raise InputError(f"{where}: the loop {loop} is repeated")
        built = _Pass()
        built.loop = loop
        fixed = [
            _check_path(path, f"{where}.fixed_files[{index}]")
            for index, path in enumerate(_check_list(entry["fixed_files"], f"{where}.fixed_files"))
        ]
        built.fixed_files = frozenset(fixed)
        _check_manifest(entry["manifest"], f"{where}.manifest", built)
        by_loop[loop] = built
    if 0 not in by_loop:
        raise InputError("passes: the pass of loop 0 is required")
    return by_loop


def _parse_run_id(run_id):
    """(perspective, shard or None, loop, chain) of a D1 run_id."""
    match = _RUN_ID.fullmatch(run_id)
    if match is None:
        raise InputError(f"run_id {_show(run_id)} does not fit {{perspective}}[@s{{k}}]#[loop{{N}}.]{{chain}}")
    try:
        shard = None if match["shard"] is None else int(match["shard"])
        loop = 0 if match["loop"] is None else int(match["loop"])
    except ValueError:
        raise InputError(f"run_id {_show(run_id)} holds a number that is too large") from None
    return match["perspective"], shard, loop


def _read_rows(perspectives, passes, rows):
    """Validate `rows`; returns (groups, rescue_seen).

    `groups` maps (perspective, shard or None, loop) to the status of the
    last row of that group, in recording order.
    """
    _check_list(rows, "perspective_runs")
    known = set(perspectives)
    groups = {}
    seen_run_ids = set()
    rescue_seen = False
    for position, row in enumerate(rows):
        where = f"perspective_runs[{position}]"
        if not isinstance(row, dict):
            raise InputError(f"{where} must be an object, got {_show(row)}")
        if row.get("role") == "evaluator" or row.get("source") == "tool":
            continue
        for name in ("run_id", "perspective", "role", "status", "source"):
            if name not in row:
                raise InputError(f"{where}: the member {name} is missing")
            if not isinstance(row[name], str):
                raise InputError(f"{where}.{name} must be a string, got {_show(row[name])}")
        status = row["status"]
        if status not in STATUSES:
            raise InputError(f"{where}.status must be one of {sorted(STATUSES)}, got {_show(status)}")
        perspective = row["perspective"]
        if perspective not in known:
            raise InputError(f"{where}: the perspective {_show(perspective)} is not in this round")
        run_id = row["run_id"]
        id_perspective, shard, loop = _parse_run_id(run_id)
        if id_perspective != perspective:
            raise InputError(
                f"{where}: the run_id {_show(run_id)} does not belong to the perspective {perspective}"
            )
        if run_id in seen_run_ids:
            raise InputError(f"{where}: the run_id {_show(run_id)} is repeated")
        seen_run_ids.add(run_id)
        if loop not in passes:
            raise InputError(f"{where}: the run_id {_show(run_id)} names loop {loop}, which has no pass")
        pass_ = passes[loop]
        if shard is None:
            if pass_.split and perspective != SPEC:
                raise InputError(
                    f"{where}: the run_id {_show(run_id)} has no shard index on a split pass"
                )
        else:
            if not pass_.split:
                raise InputError(
                    f"{where}: the run_id {_show(run_id)} has a shard index on an unsplit pass"
                )
            if shard not in pass_.dispatched:
                raise InputError(
                    f"{where}: the shard {shard} of the run_id {_show(run_id)} is not dispatched"
                )
            if perspective == SPEC:
                rescue_seen = True
        groups[(perspective, shard, loop)] = status
    return groups, rescue_seen


# ------------------------------------------------------------ operations ----


def classify_results(results):
    """The `classify_results` operation (D6) over a validated list."""
    classified = []
    for result in results:
        failed = (
            result["origin"] == "litellm"
            and result["finding_count"] == 0
            and result["summary"] in LITELLM_EMPTY_SUMMARIES
        )
        classified.append(
            {"run_id": result["run_id"], "status": "failed" if failed else "completed"}
        )
    return classified


def compute_coverage(perspectives, by_loop, groups, rescue_seen):
    """The `coverage` operation (D5) over validated input.

    `by_loop` maps each loop to its pass; `groups` and `rescue_seen` come
    from `_read_rows`.
    """
    last_change = {}
    for loop, pass_ in by_loop.items():
        for path in pass_.fixed_files:
            if last_change.get(path, 0) < loop:
                last_change[path] = loop
    universe = by_loop[max(by_loop)].files

    # covered[perspective][loop]: files a group that ended completed covers.
    covered = {}
    for (perspective, shard, loop), status in groups.items():
        if status != "completed":
            continue
        pass_ = by_loop[loop]
        paths = pass_.files if shard is None else pass_.shard_paths[shard]
        covered.setdefault(perspective, {}).setdefault(loop, set()).update(paths)

    def is_reviewed(coverage, path):
        since = last_change.get(path, 0)
        return any(loop >= since and path in paths for loop, paths in coverage.items())

    unreviewed = []
    partial = []
    for perspective in perspectives:
        coverage = covered.get(perspective, {})
        reviewed = {path for path in universe if is_reviewed(coverage, path)}
        if not coverage or (universe and not reviewed):
            unreviewed.append(perspective)
            continue
        unreviewed_files = sorted(path for path in universe if path not in reviewed)
        rescue = perspective == SPEC and rescue_seen
        if not unreviewed_files and not rescue:
            continue

        tokens = set()
        for path in unreviewed_files:
            since = last_change.get(path, 0)
            if any(loop < since and path in paths for loop, paths in coverage.items()):
                tokens.add(CHANGED_AFTER_REVIEW)
            for loop, pass_ in by_loop.items():
                if loop < since or path not in pass_.file_set:
                    continue
                shard = pass_.shard_of[path]
                if shard in pass_.excess:
                    tokens.add(SHARD_CAP_EXCEEDED)
                if shard in pass_.dispatched or (perspective, None, loop) in groups:
                    tokens.add(RUN_NOT_COMPLETED)
        if rescue:
            tokens.add(SPEC_RESCUE)
        partial.append(
            {
                "perspective": perspective,
                "unreviewed_files": unreviewed_files,
                "reason": ",".join(token for token in REASON_ORDER if token in tokens),
            }
        )
    return {
        "unreviewed_perspectives": unreviewed,
        "partially_reviewed_perspectives": partial,
    }


# -------------------------------------------------------------------- CLI ----


def _reject_constant(name):
    raise ValueError(f"the constant {name} is not valid JSON")


def _reject_repeated_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"the key {key!r} is repeated")
        result[key] = value
    return result


def _read_document(path):
    try:
        with open(path, "rb") as handle:
            raw = handle.read()
    except OSError as exc:
        raise InputError(f"cannot read the input document: {exc}") from None
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        raise InputError("the input document is not valid UTF-8") from None
    try:
        document = json.loads(
            text,
            parse_constant=_reject_constant,
            object_pairs_hook=_reject_repeated_keys,
        )
    except (ValueError, RecursionError) as exc:
        raise InputError(f"the input document is not valid JSON: {exc}") from None
    if not isinstance(document, dict):
        raise InputError("the input document must be a JSON object")
    return document


def _run(document):
    operation = document.get("operation")
    if not isinstance(operation, str) or operation not in OPERATION_MEMBERS:
        raise InputError(
            f"operation must be one of {sorted(OPERATION_MEMBERS)}, got {_show(operation)}"
        )
    members = OPERATION_MEMBERS[operation]
    for name in members:
        if name not in document:
            raise InputError(f"{operation}: the member {name} is missing")
    for name in document:
        if name != "operation" and name not in members:
            raise InputError(f"{operation}: the member {name} is not accepted")

    if operation == "classify_results":
        _check_results(document["results"])
        return {"results": classify_results(document["results"])}

    _check_perspectives(document["perspectives"])
    passes = _check_passes(document["passes"])
    groups, rescue_seen = _read_rows(
        document["perspectives"], passes, document["perspective_runs"]
    )
    return compute_coverage(document["perspectives"], passes, groups, rescue_seen)


def _fail(message, usage=False):
    sys.stderr.write(f"{PROGRAM}: {message}\n")
    if usage:
        sys.stderr.write(USAGE)
    sys.stderr.flush()


def main(argv=None):
    """Run the CLI; `argv` excludes the program name. Returns the exit code."""
    if argv is None:
        argv = sys.argv[1:]
    try:
        if len(argv) != 1:
            _fail(f"expected exactly one argument, got {len(argv)}", usage=True)
            return 2
        result = _run(_read_document(argv[0]))
        output = (
            json.dumps(
                result,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")
        sys.stdout.buffer.write(output)
        sys.stdout.buffer.flush()
        return 0
    except InputError as exc:
        _fail(str(exc))
        return 2
    except Exception as exc:  # noqa: BLE001 -- last-resort exit-2 safety net
        _fail(f"unexpected failure: {exc!r}")
        return 2


if __name__ == "__main__":
    sys.exit(main())
