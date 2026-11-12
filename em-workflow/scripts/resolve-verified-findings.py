#!/usr/bin/env python3
"""resolve-verified-findings.py -- rewrite the deferred spec findings that a
passed verify round resolved.

Contract: feature-docs/verify-pass-resolves-deferred-findings/IMPLEMENTATION.md
(C1 verify-step fields, C2 command line, C3 mapping file, C4 rewritten finding
shape, C5 token format, C6 latest-round selection) and
feature-docs/verify-pass-resolves-deferred-findings/tasks/task0001.md.

Usage:
  resolve-verified-findings.py --feature-dir DIR --mapping FILE --verified-commit SHA

`DIR` is the feature's `feature-docs/{feature}` directory in the integration
worktree: `DIR/workflow.yaml` is read, and the latest `DIR/reviews/roundN.yaml`
is read and, when something is rewritten, replaced. `FILE` is the JSON mapping
file (an object whose keys are stable_ids and whose values are arrays of
acceptance-criteria IDs). `SHA` is the integration-branch commit the verify
commands ran against: 40 or 64 lowercase hexadecimal characters.

A mapping entry is rewritten only when all of these hold: the verify step's
`result` is `pass` and its `round` is 1 or more; the entry's key is a token
equal to the `stable_id` of exactly one finding of the latest round record;
that finding's `resolution` is `deferred`, its `severity` is `critical` or
`high` and its `category` is `spec`; the entry's ID list is non-empty and every
element is a member of the verify step's `passed_ids`. A rewritten finding
gets `resolution: fixed`, the fixed-format `resolution_reason` and a
`verify_resolution` mapping (verify round, verified commit, criteria IDs, the
previous resolution and the previous reason). Every other value is kept.

Output on success (exit 0): one JSON object on one stdout line,
  {"review_round": N, "verify_round": N, "fixed": [{"stable_id": ...,
   "criteria_ids": [...]}, ...], "not_applied": N}
Output on failure (exit non-zero): stdout stays empty and stderr holds one line
with one of the codes
  invalid-arguments, invalid-commit, invalid-workflow, invalid-mapping,
  missing-round-record, invalid-round-record.
Exit status 2 is invalid-arguments; every other failure exits 1. A failure to
replace the record is reported as invalid-round-record, with the record left
as it was.

Boundaries: YAML is read with safe load only, and a document that safe load
refuses is a structural error. Every input is read and checked before the
first write; on any failure nothing is written. The only file ever written is
the latest review round record, replaced as a whole through a temporary file
in the same directory and an atomic rename. Of a finding the script reads only
`stable_id`, `resolution`, `severity`, `category` and `resolution_reason` (the
last only to carry it over); it never reads SPEC.md, VERIFICATION.md or any
free text to decide anything. stdout and stderr carry only values that were
validated against the token format (stable_ids that exist in the record, IDs
that are members of `passed_ids`), round numbers, counts and the error codes
above. The script runs no git command and writes no workflow.yaml.
"""

import json
import os
import re
import stat
import sys
import tempfile

sys.dont_write_bytecode = True

try:
    import yaml
except Exception:  # reported as the structural error of the first YAML file
    yaml = None

OPTIONS = ("--feature-dir", "--mapping", "--verified-commit")

# C5: 1 to 64 characters, first an ASCII letter or digit, then ASCII letters,
# digits, '.', '_' or '-'.
TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
COMMIT_RE = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
ROUND_FILE_RE = re.compile(r"round([1-9][0-9]*)\.yaml")

MAX_INPUT_BYTES = 8 * 1024 * 1024

# Dump with a width no line reaches, so that no text is re-wrapped.
DUMP_WIDTH = 2**30

INVALID_ARGUMENTS = "invalid-arguments"
INVALID_COMMIT = "invalid-commit"
INVALID_WORKFLOW = "invalid-workflow"
INVALID_MAPPING = "invalid-mapping"
MISSING_ROUND_RECORD = "missing-round-record"
INVALID_ROUND_RECORD = "invalid-round-record"


class Failure(Exception):
    """A structural error; `code` is the only text that is ever printed."""

    def __init__(self, code):
        super().__init__(code)
        self.code = code


# -- arguments ----------------------------------------------------------------


def parse_args(argv):
    values = {}
    i = 0
    while i < len(argv):
        name, equals, value = argv[i].partition("=")
        if name not in OPTIONS or name in values:
            raise Failure(INVALID_ARGUMENTS)
        if equals:
            i += 1
        else:
            if i + 1 >= len(argv):
                raise Failure(INVALID_ARGUMENTS)
            value = argv[i + 1]
            i += 2
        values[name] = value
    for name in OPTIONS:
        if name not in values:
            raise Failure(INVALID_ARGUMENTS)
    if not values["--feature-dir"] or not values["--mapping"]:
        raise Failure(INVALID_ARGUMENTS)
    if not COMMIT_RE.fullmatch(values["--verified-commit"]):
        raise Failure(INVALID_COMMIT)
    return values["--feature-dir"], values["--mapping"], values["--verified-commit"]


# -- reading ------------------------------------------------------------------


def read_text(path, code):
    """The UTF-8 text of a regular file of bounded size; `code` on any failure."""
    try:
        if not stat.S_ISREG(os.stat(path).st_mode):
            raise Failure(code)
        with open(path, "rb") as handle:
            data = handle.read(MAX_INPUT_BYTES + 1)
        if len(data) > MAX_INPUT_BYTES:
            raise Failure(code)
        return data.decode("utf-8")
    except Failure:
        raise
    except Exception:
        raise Failure(code)


def load_yaml(text, code):
    """Safe load only; whatever safe load refuses is the structural error."""
    if yaml is None:
        raise Failure(code)
    try:
        return yaml.safe_load(text)
    except Exception:
        raise Failure(code)


def is_token(value):
    return isinstance(value, str) and TOKEN_RE.fullmatch(value) is not None


def read_workflow(feature_dir):
    """Return (result, verify round, passed_ids set) of the verify step."""
    code = INVALID_WORKFLOW
    doc = load_yaml(read_text(os.path.join(feature_dir, "workflow.yaml"), code), code)
    if not isinstance(doc, dict):
        raise Failure(code)
    steps = doc.get("workflow")
    if not isinstance(steps, list):
        raise Failure(code)
    verify_steps = [s for s in steps if isinstance(s, dict) and s.get("id") == "verify"]
    if len(verify_steps) != 1:
        raise Failure(code)
    step = verify_steps[0]

    result = step.get("result")
    if result is not None and not (isinstance(result, str) and result in ("pass", "fail")):
        raise Failure(code)

    verify_round = 0
    if "round" in step:
        verify_round = step["round"]
        if isinstance(verify_round, bool) or not isinstance(verify_round, int) or verify_round < 0:
            raise Failure(code)

    passed_ids = frozenset()
    if "passed_ids" in step:
        ids = step["passed_ids"]
        if not isinstance(ids, list) or not all(is_token(i) for i in ids):
            raise Failure(code)
        passed_ids = frozenset(ids)
    return result, verify_round, passed_ids


def read_mapping(path):
    """The C3 mapping as a dict (insertion order = mapping order)."""
    code = INVALID_MAPPING
    text = read_text(path, code)
    try:
        mapping = json.loads(text)
    except Exception:
        raise Failure(code)
    if not isinstance(mapping, dict):
        raise Failure(code)
    for ids in mapping.values():
        if not isinstance(ids, list) or not all(isinstance(i, str) for i in ids):
            raise Failure(code)
    return mapping


def select_round_record(feature_dir):
    """C6: the record with the numerically largest N among `roundN.yaml`
    (N without leading zeros) in DIR/reviews. Returns (N, path)."""
    reviews = os.path.join(feature_dir, "reviews")
    try:
        names = os.listdir(reviews)
    except Exception:
        raise Failure(MISSING_ROUND_RECORD)
    best = None
    for name in names:
        match = ROUND_FILE_RE.fullmatch(name)
        if match is None:
            continue
        digits = match.group(1)
        key = (len(digits), digits)
        if best is None or key > best[0]:
            best = (key, digits, name)
    if best is None:
        raise Failure(MISSING_ROUND_RECORD)
    try:
        number = int(best[1])
    except Exception:
        raise Failure(INVALID_ROUND_RECORD)
    return number, os.path.join(reviews, best[2])


def read_round_record(path):
    """Return the parsed record; its `findings` is a list of mappings."""
    code = INVALID_ROUND_RECORD
    try:
        mode = os.lstat(path).st_mode
    except Exception:
        raise Failure(code)
    # The record is replaced, not edited in place: a link or anything that is
    # not a regular file is refused so that the write cannot land elsewhere.
    if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
        raise Failure(code)
    record = load_yaml(read_text(path, code), code)
    if not isinstance(record, dict):
        raise Failure(code)
    findings = record.get("findings")
    if not isinstance(findings, list) or not all(isinstance(f, dict) for f in findings):
        raise Failure(code)
    return record


# -- eligibility and rewrite ------------------------------------------------------


def apply_mapping(mapping, findings, verify_round, passed_ids, verified_commit):
    """Rewrite the eligible findings in place; return the `fixed` summary list."""
    by_id = {}
    for finding in findings:
        stable_id = finding.get("stable_id")
        if isinstance(stable_id, str):
            by_id.setdefault(stable_id, []).append(finding)

    fixed = []
    for key, ids in mapping.items():
        if not is_token(key):
            continue
        matches = by_id.get(key, [])
        if len(matches) != 1:
            continue
        finding = matches[0]
        if finding.get("resolution") != "deferred":
            continue
        if finding.get("severity") not in ("critical", "high"):
            continue
        if finding.get("category") != "spec":
            continue
        if not ids or not all(i in passed_ids for i in ids):
            continue

        criteria = list(dict.fromkeys(ids))
        previous_reason = finding.get("resolution_reason")
        finding["resolution"] = "fixed"
        finding["resolution_reason"] = (
            f"resolved by verify round {verify_round}: "
            f"acceptance criteria {', '.join(criteria)} passed"
        )
        finding["verify_resolution"] = {
            "verify_round": verify_round,
            "verified_commit": verified_commit,
            "criteria_ids": criteria,
            "previous_resolution": "deferred",
            "previous_resolution_reason": previous_reason,
        }
        fixed.append({"stable_id": key, "criteria_ids": list(criteria)})
    return fixed


# -- writing ----------------------------------------------------------------------


def replace_record(path, record):
    """Replace the record as a whole: write a sibling temporary file, then
    rename it over the record. Any failure leaves the record as it was and no
    temporary file behind."""
    try:
        text = yaml.safe_dump(
            record,
            sort_keys=False,
            allow_unicode=True,
            default_flow_style=False,
            width=DUMP_WIDTH,
        )
        reloaded = yaml.safe_load(text)
        if not isinstance(reloaded, dict) or not isinstance(reloaded.get("findings"), list):
            raise Failure(INVALID_ROUND_RECORD)
        mode = stat.S_IMODE(os.stat(path).st_mode)
        directory = os.path.dirname(path) or "."
        fd, temporary = tempfile.mkstemp(prefix=".resolve-", suffix=".tmp", dir=directory)
    except Failure:
        raise
    except Exception:
        raise Failure(INVALID_ROUND_RECORD)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


# -- main -------------------------------------------------------------------------


def run(argv):
    feature_dir, mapping_path, verified_commit = parse_args(argv)
    result, verify_round, passed_ids = read_workflow(feature_dir)
    mapping = read_mapping(mapping_path)
    review_round, record_path = select_round_record(feature_dir)
    record = read_round_record(record_path)

    fixed = []
    if result == "pass" and verify_round >= 1:
        fixed = apply_mapping(mapping, record["findings"], verify_round, passed_ids, verified_commit)
    if fixed:
        try:
            replace_record(record_path, record)
        except Failure:
            raise
        except BaseException:
            raise Failure(INVALID_ROUND_RECORD)
    return {
        "review_round": review_round,
        "verify_round": verify_round,
        "fixed": fixed,
        "not_applied": len(mapping) - len(fixed),
    }


def main(argv):
    try:
        summary = run(argv)
    except Failure as failure:
        sys.stderr.write(failure.code + "\n")
        return 2 if failure.code == INVALID_ARGUMENTS else 1
    except Exception:
        # Fail closed and print nothing but a code. The writing step is the
        # last one, so nothing has been written when an unexpected error
        # occurs before it; the record itself is the only thing it can name.
        sys.stderr.write(INVALID_ROUND_RECORD + "\n")
        return 1
    sys.stdout.write(json.dumps(summary, ensure_ascii=True) + "\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
