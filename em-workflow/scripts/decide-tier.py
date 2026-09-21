#!/usr/bin/env python3
"""Deterministic tier evaluator (em-workflow plugin, task0001/task0012,
FR1/FR4/FR13/NFR1).

Turns already-collected observations (Jev's score object(s) plus the two
tool availability booleans) into one of the three run tiers -- `full` /
`reduced` / `minimal` -- with zero model inference (NFR1) and zero
invocation of its own: the orchestrator performs the Jev and Codex calls
(task0003's job, not this script's) and hands the results here.

CLI contract:
    decide-tier.py [rules-table-path]
  Reads exactly one JSON mapping on stdin, writes exactly one JSON mapping
  to stdout, and always exits 0 -- a missing, malformed or incomplete input
  yields the safest tier (`full`, removes nothing) with a `reason` naming
  what was missing or invalid, never an interactive prompt and never a
  non-zero exit. `rules-table-path` is optional and defaults to this
  plugin's own references/tier-rules.yaml.

Input shape -- single reading (today's shape, still accepted):
    {
      "jev_available": true,
      "codex_available": true,
      "basis": "description_plus_code",
      "score": {
        "probabilities": {"0": 0.81, "1": 0.10},
        "expectation_clear": 0.6,
        "confidence": 0.75
      }
    }

Input shape -- two readings (task0012):
    {
      "jev_available": true,
      "codex_available": true,
      "readings": [
        {"basis": "description_only", "score": {...}},
        {"basis": "description_plus_code", "score": {...}}
      ]
    }
  `readings` may carry one or two reading objects. When both are present
  and evaluate to different tiers, the result is the tier that removes
  nothing (task0012 AC-6).

Output shape:
    {
      "tier": "minimal",
      "decided_by": "threshold_rows:minimal",
      "reason": "...",
      "observed": {"jev_available": true, "codex_available": true,
                   "basis": "description_plus_code", "score": {...}}
    }
  `observed` carries a `readings` list instead of a flat `basis`/`score`
  pair when more than one reading was supplied. No non-finite value (NaN /
  Infinity / -Infinity) can appear anywhere in the emitted bytes -- a
  downstream strict JSON parser must be able to decode every byte this
  script writes (task0012 AC-5).

Row interpretation is data-driven (task0012): a threshold row is read for
the threshold members it declares -- not for its `id` -- and the evaluator
carries no numeric default for any of them. A row declaring no threshold
member at all is the only unconditional fallthrough; a row declaring at
least one member always has its declared comparisons evaluated, including
a row whose `id` the evaluator does not otherwise recognize. Probability
and clarity observations are accepted only when finite and within the
closed unit interval [0, 1] -- an observation outside that set yields the
tier that removes nothing with a reason naming the offending member,
regardless of what any other declared member would have decided.

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
# unresolved condition on the decision path (IMPLEMENTATION.md Conventions,
# "Fail-safe, never fail-open").
SAFEST_TIER = "full"

# Fields every threshold row carries that are NOT a threshold member -- the
# row's own bookkeeping, not something to compare an observation against.
# Any OTHER key on a row is a declared threshold member, recognized or not
# (task0012 AC-1/AC-2: a row's threshold members are read structurally, not
# by branching on the row's `id`).
ROW_METADATA_KEYS = frozenset({"id", "order", "tier", "description"})

# The fixed correspondence between a recognized threshold-member key (as it
# appears in a rules-table row) and the raw observation(s) it constrains.
# This vocabulary itself is not a "threshold numeric literal" or a "row
# identifier literal" (task0012 AC-1) -- it is the structural knowledge of
# which field in the score object a given member name refers to; the FLOOR
# each member is compared against is always read from the row, never from
# a default supplied here.
THRESHOLD_MEMBERS = {
    "p0_floor": {
        "raw": ("p0",),
        "compute": lambda raw: raw["p0"],
        "label": "score.probabilities['0']",
    },
    "expectation_clear_floor": {
        "raw": ("expectation_clear",),
        "compute": lambda raw: raw["expectation_clear"],
        "label": "score.expectation_clear",
    },
    "bucket_sum_floor": {
        "raw": ("p0", "p1"),
        "compute": lambda raw: raw["p0"] + raw["p1"],
        "label": "score.probabilities['0'] + score.probabilities['1']",
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


def _raw_lookup(score, raw_name):
    """Read a single raw observation out of `score` without validating it
    -- presence, numeric-ness, finiteness and range are all judged by
    `_classify_raw_observation`, not here."""
    if not isinstance(score, dict):
        return None
    if raw_name == "expectation_clear":
        return score.get("expectation_clear")
    probabilities = score.get("probabilities")
    if not isinstance(probabilities, dict):
        return None
    if raw_name == "p0":
        return probabilities.get("0")
    if raw_name == "p1":
        return probabilities.get("1")
    return None


def _classify_raw_observation(raw_value):
    """Classify one raw observation. Returns (status, numeric_value):
    - "absent": the observation is missing (or explicitly null).
    - "non_numeric": present but not a real number.
    - "invalid_range": a real number, but non-finite or outside [0, 1] --
      probability and clarity observations are accepted only within the
      closed unit interval (task0012 AC-4).
    - "valid": a finite real number within [0, 1].
    """
    if raw_value is None:
        return ("absent", None)
    numeric = _numeric(raw_value)
    if numeric is None:
        return ("non_numeric", None)
    value = float(numeric)
    if not math.isfinite(value) or value < 0.0 or value > 1.0:
        return ("invalid_range", value)
    return ("valid", value)


def evaluate_row(row, score):
    """Evaluate one threshold row against `score`, purely from the
    threshold members the row itself declares (task0012 AC-1/AC-2).

    Returns one of:
      ("match", reason)    -- the row's tier is the decision.
      ("no_match", None)   -- continue to the next row.
      ("invalid", reason)  -- a declared member's observation was
                              non-finite or out of range; the caller must
                              stop and return SAFEST_TIER immediately,
                              regardless of any other row (task0012 AC-4).
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
            # for it, so this row can never be satisfied (task0012 AC-1).
            return ("no_match", None)

        floor = _numeric(row.get(member_key))
        if floor is None:
            # The rules table declares this member but its own floor value
            # is missing/non-numeric -- the row cannot be evaluated.
            return ("no_match", None)

        raw_values = {}
        for raw_name in spec["raw"]:
            raw_value = _raw_lookup(score, raw_name)
            status, numeric_value = _classify_raw_observation(raw_value)
            if status == "invalid_range":
                return (
                    "invalid",
                    f"{spec['label']}={numeric_value!r} is non-finite or "
                    f"outside the closed unit interval [0, 1] "
                    f"(declared member: {member_key})",
                )
            if status in ("absent", "non_numeric"):
                return ("no_match", None)
            raw_values[raw_name] = numeric_value

        comparison_value = spec["compute"](raw_values)
        comparisons.append((member_key, spec["label"], comparison_value, floor))
        if comparison_value < floor:
            return ("no_match", None)

    reason = " and ".join(
        f"{label}={value} >= {floor} ({member_key})"
        for member_key, label, value, floor in comparisons
    )
    return ("match", reason)


def evaluate_thresholds(rules, score):
    """Evaluate `threshold_rows` from `rules` against `score`, in file
    order; the first row whose declared members all match wins.

    Returns (tier, row_id, reason, invalid). `invalid` is True when a
    declared threshold member's observation was non-finite or outside
    [0, 1] -- `tier` is already SAFEST_TIER in that case and `row_id` is
    None (no rule-table row decided the result; the reason names the
    offending observation instead).
    """
    threshold_rows = rules.get("threshold_rows") if isinstance(rules, dict) else None
    if not isinstance(threshold_rows, list) or not threshold_rows:
        return (SAFEST_TIER, None, "rule table has no threshold_rows to evaluate", False)

    for row in threshold_rows:
        if not isinstance(row, dict):
            continue
        outcome, reason = evaluate_row(row, score)
        if outcome == "invalid":
            return (SAFEST_TIER, None, reason, True)
        if outcome == "match":
            row_id = row.get("id")
            tier = row.get("tier", row_id)
            return (tier, row_id, reason, False)
        # "no_match": fall through to the next row.

    return (
        SAFEST_TIER,
        None,
        "no threshold row matched and no fallthrough row exists",
        False,
    )


def _normalize_readings(payload):
    """Return a list of one or two reading dicts (each carrying `basis`
    and `score`), or None if the `readings` shape itself is malformed.
    Accepts either the top-level `basis`/`score` pair (the pre-task0012
    single-reading shape) or a `readings` list carrying one or two such
    pairs (task0012 AC-6). A single reading via `readings` behaves
    identically to the top-level shape -- there is no separate
    availability-fallback shape to accept."""
    readings_field = payload.get("readings")
    if readings_field is not None:
        if not isinstance(readings_field, list) or not (1 <= len(readings_field) <= 2):
            return None
        readings = []
        for reading in readings_field:
            if not isinstance(reading, dict):
                return None
            readings.append(reading)
        return readings
    return [{"basis": payload.get("basis"), "score": payload.get("score")}]


def _build_observed(jev_available, codex_available, readings):
    """Echo the observed input. A single reading keeps the flat
    `basis`/`score` shape callers already depend on; more than one reading
    is echoed as a `readings` list instead."""
    if len(readings) == 1:
        reading = readings[0]
        return {
            "jev_available": jev_available,
            "codex_available": codex_available,
            "basis": reading.get("basis") if isinstance(reading, dict) else None,
            "score": reading.get("score") if isinstance(reading, dict) else None,
        }
    return {
        "jev_available": jev_available,
        "codex_available": codex_available,
        "readings": [
            {
                "basis": reading.get("basis") if isinstance(reading, dict) else None,
                "score": reading.get("score") if isinstance(reading, dict) else None,
            }
            for reading in readings
        ],
    }


def decide(payload, rules):
    """Pure decision function: one input mapping + the parsed rule table in,
    one output mapping out. Never raises for a malformed/incomplete
    `payload` -- always resolves to a result mapping."""
    if not isinstance(payload, dict):
        return _safest_result(
            "input was not a JSON object", "fallback_matrix:malformed_input", payload
        )

    jev_available = payload.get("jev_available")
    if not isinstance(jev_available, bool):
        return _safest_result(
            "missing or non-boolean 'jev_available'",
            "fallback_matrix:malformed_input",
            payload,
        )

    codex_available = payload.get("codex_available")
    if not isinstance(codex_available, bool):
        return _safest_result(
            "missing or non-boolean 'codex_available'",
            "fallback_matrix:malformed_input",
            payload,
        )

    readings = _normalize_readings(payload)
    if readings is None:
        return _safest_result(
            "malformed 'readings': expected one or two reading objects",
            "fallback_matrix:malformed_input",
            {
                "jev_available": jev_available,
                "codex_available": codex_available,
                "readings": payload.get("readings"),
            },
        )

    if not jev_available:
        # fallback_matrix: jev_unusable -- decides full regardless of
        # codex_available (FR13).
        return _safest_result(
            "judgement skill unusable (non-zero Jev exit status or "
            "explicitly reported unavailable)",
            "fallback_matrix:jev_unusable",
            _build_observed(jev_available, codex_available, readings),
        )

    evaluations = []
    for reading in readings:
        score = reading.get("score") if isinstance(reading, dict) else None
        if not isinstance(score, dict):
            return _safest_result(
                "missing or non-object 'score'",
                "fallback_matrix:malformed_input",
                _build_observed(jev_available, codex_available, readings),
            )
        tier, row_id, reason, invalid = evaluate_thresholds(rules, score)
        evaluations.append(
            {
                "basis": reading.get("basis"),
                "tier": tier,
                "row_id": row_id,
                "reason": reason,
                "invalid": invalid,
            }
        )

    observed = _build_observed(jev_available, codex_available, readings)

    distinct_tiers = {evaluation["tier"] for evaluation in evaluations}
    if len(distinct_tiers) > 1:
        # Two readings evaluated to different tiers -- fall to the tier
        # that removes nothing (task0012 AC-6).
        return {
            "tier": SAFEST_TIER,
            "decided_by": "fallback_matrix:readings_disagree",
            "reason": "readings disagree: "
            + ", ".join(f"{e['basis']}={e['tier']}" for e in evaluations),
            "observed": observed,
        }

    chosen = evaluations[0]
    if chosen["invalid"]:
        decided_by = "fallback_matrix:invalid_observation"
    elif chosen["row_id"]:
        decided_by = f"threshold_rows:{chosen['row_id']}"
    else:
        decided_by = "fallback_matrix:malformed_rules"

    return {
        "tier": chosen["tier"],
        "decided_by": decided_by,
        "reason": chosen["reason"],
        "observed": observed,
    }


def _finite_safe(value):
    """Recursively replace non-finite floats (NaN / Infinity / -Infinity)
    with their string representation, so the JSON encoding of `value` never
    carries a bare non-finite token -- a downstream strict JSON parser must
    be able to decode every byte this script writes (task0012 AC-5)."""
    if isinstance(value, float) and not math.isfinite(value):
        return repr(value)
    if isinstance(value, dict):
        return {key: _finite_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_finite_safe(item) for item in value]
    return value


def _emit(result):
    """Serialize `result` to stdout as one line of JSON, sanitized so no
    non-finite token can reach the emitted bytes (task0012 AC-5)."""
    safe_result = _finite_safe(result)
    try:
        print(json.dumps(safe_result, allow_nan=False))
    except (TypeError, ValueError):  # pragma: no cover - defensive
        print(
            json.dumps(
                _safest_result(
                    "result could not be serialized safely",
                    "fallback_matrix:error",
                    None,
                )
            )
        )


def main(argv):
    rules_path = argv[1] if len(argv) > 1 else str(DEFAULT_RULES_PATH)

    try:
        raw_stdin = sys.stdin.read()
    except Exception as exc:  # pragma: no cover - defensive, stdin itself broken
        _emit(_safest_result(f"could not read stdin: {exc}", "fallback_matrix:error", None))
        return 0

    try:
        payload = json.loads(raw_stdin) if raw_stdin.strip() else None
        if payload is None:
            result = _safest_result(
                "empty stdin: no input payload was provided",
                "fallback_matrix:malformed_input",
                None,
            )
        else:
            try:
                rules = _load_rules(rules_path)
            except Exception as exc:
                result = _safest_result(
                    f"could not load rule table {rules_path}: {exc}",
                    "fallback_matrix:error",
                    payload if isinstance(payload, dict) else None,
                )
            else:
                result = decide(payload, rules)
    except json.JSONDecodeError as exc:
        result = _safest_result(
            f"malformed JSON on stdin: {exc}", "fallback_matrix:malformed_input", None
        )
    except Exception as exc:  # pragma: no cover - defensive, never surfaces a crash
        result = _safest_result(
            f"unexpected error: {exc}", "fallback_matrix:error", None
        )

    _emit(result)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
