#!/usr/bin/env python3
"""Deterministic tier evaluator (em-workflow plugin, task0001 of
feature-docs/tier-decision-staged-jev; FR3/FR4/FR5/FR8/FR9/NFR1).

Turns one already-collected final-reading score object plus the two tool
availability booleans into one of the three run tiers -- `full` / `reduced`
/ `minimal` -- with zero model inference (NFR1) and zero invocation of its
own: the orchestrator performs the Jev and Codex calls (task0003's job, not
this script's) and hands the result here.

CLI contract:
    decide-tier.py [rules-table-path]
  Reads exactly one JSON mapping on stdin, writes exactly one JSON mapping
  to stdout, and always exits 0 -- a missing, malformed or invalid input
  yields the safest tier (`full`, removes nothing) with a `reason` naming
  what was missing or invalid, never an interactive prompt and never a
  non-zero exit. `rules-table-path` is optional and defaults to this
  plugin's own references/tier-rules.yaml.

Input shape (single final reading only -- the legacy two-reading `readings`
shape is rejected, see below):
    {
      "jev_available": true,
      "codex_available": true,
      "final_score": {
        "probabilities": {"0": 0.09, "1": 0.90, "2": 0.01, "3": 0.00},
        "expectation_clear": 0.6,
        "confidence": 0.75
      }
    }
  `final_score` is required when both flags are true; it may be absent or
  null otherwise, and is then ignored (an unusable Jev/Codex call already
  decides the tier before `final_score` is examined). `expectation_clear`
  and `confidence` are recorded verbatim but never used as a threshold
  member -- the tier is decided from `probabilities` alone.

  An input carrying the legacy `readings` member (the two-reading payload
  from the predecessor feature) is rejected as invalid input: tier `full`,
  whatever else it carries. No compatibility shim is added for it.

Output shape:
    {
      "tier": "minimal",
      "decided_by": "threshold_rows:minimal",
      "reason": "...",
      "observed": {"jev_available": true, "codex_available": true,
                   "final_score": {...}}
    }
  No non-finite value (NaN / Infinity / -Infinity) can appear anywhere in
  the emitted bytes -- a downstream strict JSON parser must be able to
  decode every byte this script writes.

Decision order (IMPLEMENTATION.md SC-1):
  (0) input shape: not an object, legacy `readings` present, or a flag
      missing/non-boolean gives full as invalid input.
  (1) `jev_available` false gives full via the `jev_unusable` fallback.
  (2) `codex_available` false gives full via the `jev_only_usable`
      fallback -- the final Jev call is skipped, so `final_score` is never
      examined in this case, regardless of what it would have decided.
  (3) `final_score.probabilities` is validated: buckets `"0"`-`"3"` all
      present and no other key, each a finite real number in [0, 1], and
      the four-bucket sum within `probability_sum_tolerance` of 1 -- a
      failure gives full with the offending bucket or the computed sum in
      the reason.
  (4) `threshold_rows` are evaluated top-down; the first row whose declared
      members all match wins.

Row interpretation is data-driven: a threshold row is read for the
threshold members it declares -- not for its `id` -- and the evaluator
carries no numeric default for any of them (NFR1). A row declaring no
threshold member at all is the only unconditional fallthrough. A row
declaring at least one member always has its declared comparisons
evaluated. A row declaring a member with no numeric floor in the rule
table, or a missing/non-numeric `probability_sum_tolerance`, is a rule-table
defect: the evaluator gives full immediately with a reason naming the
missing member, rather than falling through to the next row.

`decided_by` vocabulary (IMPLEMENTATION.md SC-3): `threshold_rows:minimal`,
`threshold_rows:reduced`, `threshold_rows:full` when a threshold row
decided the tier; `fallback_matrix:jev_unusable` and
`fallback_matrix:jev_only_usable` for the two named fallbacks;
`fallback_matrix:malformed_input` for every other case (invalid input,
legacy input, rule-table defects, and failed probability validation) --
consumers rely on only the `threshold_rows:` prefix distinction and never
depend on the exact text of the malformed-input value.
The predecessor feature's two-reading disagreement fallback no longer
exists: with only one reading, there is nothing left to disagree with.

PyYAML is a runtime dependency of the em-workflow plugin (IMPLEMENTATION.md
Technology Stack), used here to parse references/tier-rules.yaml. It is NOT
a test dependency -- tests load this module via importlib and call its
functions directly, the same technique tests/test_check_plugin_invariants.py
already uses for check-plugin-invariants.py, rather than importing yaml
themselves (NFR7).
"""

import json
import math
import sys
from pathlib import Path

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_RULES_PATH = SCRIPT_DIR.parent / "references" / "tier-rules.yaml"

# The tier that removes nothing -- the fail-safe default for every
# unresolved condition on the decision path (fail-safe, never fail-open).
SAFEST_TIER = "full"

# The single decided_by value used for every fallback that is NOT one of
# the two named availability fallbacks below (SC-3): invalid input shape,
# legacy `readings` input, rule-table defects, and failed probability
# validation all funnel into this one value. No consumer depends on its
# exact text.
DECIDED_BY_MALFORMED = "fallback_matrix:malformed_input"
DECIDED_BY_JEV_UNUSABLE = "fallback_matrix:jev_unusable"
DECIDED_BY_JEV_ONLY_USABLE = "fallback_matrix:jev_only_usable"

# Fields every threshold row carries that are NOT a threshold member -- the
# row's own bookkeeping, not something to compare an observation against.
# Any OTHER key on a row is a declared threshold member, recognized or not.
ROW_METADATA_KEYS = frozenset({"id", "order", "tier", "description"})

# The bucket keys a final score's `probabilities` map must carry -- exactly
# these four, no more, no fewer.
BUCKET_KEYS = ("0", "1", "2", "3")

# The fixed correspondence between a recognized threshold-member key (as it
# appears in a rules-table row) and the bucket(s) of `probabilities` it
# sums. This vocabulary itself is not a threshold numeric literal (NFR1) --
# it is the structural knowledge of which bucket(s) a given member name
# refers to; the FLOOR each member is compared against is always read from
# the row, never from a default supplied here.
THRESHOLD_MEMBERS = {
    "bucket0_floor": {
        "buckets": ("0",),
        "label": "probabilities['0']",
    },
    "bucket0_1_sum_floor": {
        "buckets": ("0", "1"),
        "label": "probabilities['0']+probabilities['1']",
    },
}


def _load_rules(rules_path):
    """Parse the rule table at `rules_path`. Raises on I/O or YAML errors --
    callers are responsible for converting that into a fail-safe result."""
    with open(rules_path, encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def _safest_result(reason, decided_by, observed):
    return {
        "tier": SAFEST_TIER,
        "decided_by": decided_by,
        "reason": reason,
        "observed": observed,
    }


def _numeric(value):
    """Return `value` if it is a real number (bool excluded, since bool is a
    subclass of int in Python and `True >= 0.80` is not a meaningful
    probability comparison), else None."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value


def _validate_probabilities(final_score, tolerance):
    """Validate one final score's `probabilities` map (SC-1 step 3).

    Returns (ok, values, reason). `values` is a bucket-key -> float mapping
    when `ok` is True, else None. `reason` is empty when `ok` is True."""
    if not isinstance(final_score, dict):
        return False, None, "missing or non-object 'final_score'"

    probabilities = final_score.get("probabilities")
    if not isinstance(probabilities, dict):
        return False, None, "missing or non-object 'probabilities' in final_score"

    present = set(probabilities.keys())
    missing = [key for key in BUCKET_KEYS if key not in present]
    if missing:
        return (
            False,
            None,
            f"final_score.probabilities is missing bucket '{missing[0]}'",
        )

    extra = sorted(key for key in present if key not in BUCKET_KEYS)
    if extra:
        return (
            False,
            None,
            f"final_score.probabilities has an unexpected bucket key '{extra[0]}'",
        )

    values = {}
    for bucket in BUCKET_KEYS:
        numeric = _numeric(probabilities.get(bucket))
        if numeric is None:
            return (
                False,
                None,
                f"final_score.probabilities['{bucket}'] is not a number",
            )
        value = float(numeric)
        if not math.isfinite(value) or value < 0.0 or value > 1.0:
            return (
                False,
                None,
                f"final_score.probabilities['{bucket}']={value!r} is non-finite "
                "or outside the closed unit interval [0, 1]",
            )
        values[bucket] = value

    if tolerance is None:
        return (
            False,
            None,
            "rule table is missing a numeric 'probability_sum_tolerance'",
        )

    total = sum(values[bucket] for bucket in BUCKET_KEYS)
    diff = abs(total - 1.0)
    if diff > tolerance:
        return (
            False,
            None,
            f"final_score.probabilities sum to {total}, which differs from 1 "
            f"by more than the rule table's probability_sum_tolerance ({tolerance})",
        )

    return True, values, ""


def evaluate_row(row, values):
    """Evaluate one threshold row against already-validated bucket
    `values`, purely from the threshold members the row itself declares.

    Returns one of:
      ("match", reason)   -- the row's tier is the decision.
      ("no_match", None)  -- continue to the next row.
      ("defect", reason)  -- the row declares a member with no numeric
                             floor in the rule table; the caller must stop
                             and return SAFEST_TIER immediately, naming the
                             member, rather than falling through.
    """
    declared_keys = [key for key in row if key not in ROW_METADATA_KEYS]
    if not declared_keys:
        # The only row shape that may be returned without a comparison.
        return ("match", "unconditional row: no threshold member declared")

    comparisons = []
    for member_key in declared_keys:
        spec = THRESHOLD_MEMBERS.get(member_key)
        if spec is None:
            # An unrecognized (e.g. renamed) threshold member: the
            # evaluator carries no correspondence and no numeric default
            # for it, so this row can never be satisfied.
            return ("no_match", None)

        floor = _numeric(row.get(member_key))
        if floor is None:
            row_id = row.get("id", "?")
            return (
                "defect",
                f"threshold row {row_id!r} is missing a numeric value for "
                f"{member_key!r}",
            )

        value = sum(values[bucket] for bucket in spec["buckets"])
        comparisons.append((spec["label"], value, floor))
        if value < floor:
            return ("no_match", None)

    reason = " and ".join(
        f"{label}={value} >= {floor}" for label, value, floor in comparisons
    )
    return ("match", reason)


def evaluate_thresholds(rules, values):
    """Evaluate `threshold_rows` from `rules` against validated bucket
    `values`, in file order; the first row whose declared members all
    match wins.

    Returns (tier, row_id, reason, ok). `ok` is False when the rule table
    itself is defective (a declared member with no floor, a matched row
    with no usable `id`, no threshold_rows to evaluate at all, or no row
    matched and no fallthrough row exists) -- `tier` and `row_id` are then
    None and `reason` names the defect. `row_id` is the matched row's `id`
    (the vocabulary `decided_by` is built from); `tier` is the matched
    row's `tier` value, falling back to its `id` when `tier` is absent --
    the two may legitimately differ (a row's `id` need not equal its
    `tier`).
    """
    threshold_rows = rules.get("threshold_rows") if isinstance(rules, dict) else None
    if not isinstance(threshold_rows, list) or not threshold_rows:
        return (None, None, "rule table has no threshold_rows to evaluate", False)

    for row in threshold_rows:
        if not isinstance(row, dict):
            continue
        outcome, reason = evaluate_row(row, values)
        if outcome == "defect":
            return (None, None, reason, False)
        if outcome == "match":
            row_id = row.get("id")
            tier = row.get("tier", row_id)
            if not isinstance(tier, str) or not tier:
                return (
                    None,
                    None,
                    f"threshold row {row_id!r} declares no usable tier",
                    False,
                )
            if not isinstance(row_id, str) or not row_id:
                return (
                    None,
                    None,
                    f"threshold row (tier={tier!r}) declares no usable 'id'",
                    False,
                )
            return (tier, row_id, reason, True)
        # "no_match": fall through to the next row.

    return (
        None,
        None,
        "no threshold row matched and no fallthrough row exists",
        False,
    )


def _build_observed(jev_available, codex_available, final_score):
    return {
        "jev_available": jev_available,
        "codex_available": codex_available,
        "final_score": final_score,
    }


def decide(payload, rules):
    """Pure decision function: one input mapping + the parsed rule table in,
    one output mapping out. Never raises for a malformed/incomplete
    `payload` -- always resolves to a result mapping."""
    if not isinstance(payload, dict):
        return _safest_result(
            "input was not a JSON object", DECIDED_BY_MALFORMED, payload
        )

    if "readings" in payload:
        # D4: the legacy two-reading payload is rejected, not translated.
        return _safest_result(
            "legacy 'readings' input (two-reading payload) is not accepted; "
            "provide a single 'final_score' instead",
            DECIDED_BY_MALFORMED,
            payload,
        )

    jev_available = payload.get("jev_available")
    if not isinstance(jev_available, bool):
        return _safest_result(
            "missing or non-boolean 'jev_available'",
            DECIDED_BY_MALFORMED,
            payload,
        )

    codex_available = payload.get("codex_available")
    if not isinstance(codex_available, bool):
        return _safest_result(
            "missing or non-boolean 'codex_available'",
            DECIDED_BY_MALFORMED,
            payload,
        )

    final_score = payload.get("final_score")
    observed = _build_observed(jev_available, codex_available, final_score)

    if not jev_available:
        return _safest_result(
            "judgement skill unusable (non-zero Jev exit status or "
            "explicitly reported unavailable)",
            DECIDED_BY_JEV_UNUSABLE,
            observed,
        )

    if not codex_available:
        return _safest_result(
            "Codex pre-survey unusable; the final Jev call is skipped",
            DECIDED_BY_JEV_ONLY_USABLE,
            observed,
        )

    tolerance = None
    if isinstance(rules, dict):
        tolerance = _numeric(rules.get("probability_sum_tolerance"))

    ok, values, reason = _validate_probabilities(final_score, tolerance)
    if not ok:
        return _safest_result(reason, DECIDED_BY_MALFORMED, observed)

    tier, row_id, row_reason, row_ok = evaluate_thresholds(rules, values)
    if not row_ok:
        return _safest_result(row_reason, DECIDED_BY_MALFORMED, observed)

    return {
        "tier": tier,
        "decided_by": f"threshold_rows:{row_id}",
        "reason": row_reason,
        "observed": observed,
    }


def _finite_safe(value):
    """Recursively replace non-finite floats (NaN / Infinity / -Infinity)
    with their string representation, so the JSON encoding of `value` never
    carries a bare non-finite token -- a downstream strict JSON parser must
    be able to decode every byte this script writes."""
    if isinstance(value, float) and not math.isfinite(value):
        return repr(value)
    if isinstance(value, dict):
        return {key: _finite_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_finite_safe(item) for item in value]
    return value


def _emit(result):
    """Serialize `result` to stdout as one line of JSON, sanitized so no
    non-finite token can reach the emitted bytes."""
    safe_result = _finite_safe(result)
    try:
        print(json.dumps(safe_result, allow_nan=False))
    except (TypeError, ValueError):  # pragma: no cover - defensive
        print(
            json.dumps(
                _safest_result(
                    "result could not be serialized safely",
                    DECIDED_BY_MALFORMED,
                    None,
                )
            )
        )


def main(argv):
    rules_path = argv[1] if len(argv) > 1 else str(DEFAULT_RULES_PATH)

    try:
        raw_stdin = sys.stdin.read()
    except Exception as exc:  # pragma: no cover - defensive, stdin itself broken
        _emit(_safest_result(f"could not read stdin: {exc}", DECIDED_BY_MALFORMED, None))
        return 0

    try:
        payload = json.loads(raw_stdin) if raw_stdin.strip() else None
        if payload is None:
            result = _safest_result(
                "empty stdin: no input payload was provided",
                DECIDED_BY_MALFORMED,
                None,
            )
        else:
            try:
                rules = _load_rules(rules_path)
            except Exception as exc:
                result = _safest_result(
                    f"could not load rule table {rules_path}: {exc}",
                    DECIDED_BY_MALFORMED,
                    payload if isinstance(payload, dict) else None,
                )
            else:
                result = decide(payload, rules)
    except json.JSONDecodeError as exc:
        result = _safest_result(
            f"malformed JSON on stdin: {exc}", DECIDED_BY_MALFORMED, None
        )
    except Exception as exc:  # pragma: no cover - defensive, never surfaces a crash
        result = _safest_result(
            f"unexpected error: {exc}", DECIDED_BY_MALFORMED, None
        )

    _emit(result)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
