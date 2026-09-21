#!/usr/bin/env python3
"""Deterministic tier evaluator (em-workflow plugin, task0001, FR1/FR4/FR5/
FR13/NFR1).

Turns already-collected observations (Jev's score object plus the two tool
availability booleans) into one of the three run tiers -- `full` / `reduced`
/ `minimal` -- with zero model inference (NFR1) and zero invocation of its
own: the orchestrator performs the Jev and Codex calls (task0003's job, not
this script's) and hands the results here.

CLI contract:
    decide-tier.py [rules-table-path]
  Reads exactly one JSON mapping on stdin, writes exactly one JSON mapping
  to stdout, and always exits 0 -- a missing, malformed or incomplete input
  yields the safest tier (`full`, removes nothing) with a `reason` naming
  what was missing, never an interactive prompt and never a non-zero exit.
  `rules-table-path` is optional and defaults to this plugin's own
  references/tier-rules.yaml.

Input shape:
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

Output shape:
    {
      "tier": "minimal",
      "decided_by": "threshold_rows:minimal",
      "reason": "...",
      "observed": {"jev_available": true, "codex_available": true,
                   "basis": "description_plus_code", "score": {...}}
    }

PyYAML is a runtime dependency of the em-workflow plugin (IMPLEMENTATION.md
Technology Stack), used here to parse references/tier-rules.yaml. It is NOT
a test dependency -- tests load this module via importlib and call its
functions directly, the same technique tests/test_check_plugin_invariants.py
already uses for check-plugin-invariants.py, rather than importing yaml
themselves (NFR7).
"""

import json
import sys
from pathlib import Path

import yaml

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_RULES_PATH = SCRIPT_DIR.parent / "references" / "tier-rules.yaml"

# The tier that removes nothing -- the fail-safe default for every
# unresolved condition on the decision path (IMPLEMENTATION.md Conventions,
# "Fail-safe, never fail-open").
SAFEST_TIER = "full"


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


def _bucket(probabilities, key):
    if not isinstance(probabilities, dict):
        return None
    return _numeric(probabilities.get(key))


def evaluate_thresholds(rules, score):
    """Evaluate `threshold_rows` from `rules` against `score`, in file
    order; the first row whose required members are present AND satisfied
    wins. A row whose required member is absent (or non-numeric) does not
    match and evaluation falls through to the next row -- never raises.

    Returns (tier, row_id, reason). Falls back to (SAFEST_TIER, None, ...)
    if the rule table carries no threshold_rows at all.
    """
    threshold_rows = rules.get("threshold_rows") if isinstance(rules, dict) else None
    if not isinstance(threshold_rows, list) or not threshold_rows:
        return (SAFEST_TIER, None, "rule table has no threshold_rows to evaluate")

    probabilities = score.get("probabilities") if isinstance(score, dict) else None
    expectation_clear = (
        _numeric(score.get("expectation_clear")) if isinstance(score, dict) else None
    )
    p0 = _bucket(probabilities, "0")
    p1 = _bucket(probabilities, "1")

    for row in threshold_rows:
        if not isinstance(row, dict):
            continue
        row_id = row.get("id")
        tier = row.get("tier", row_id)

        if row_id == "minimal":
            p0_floor = row.get("p0_floor", 0.80)
            clarity_floor = row.get("expectation_clear_floor", 0.5)
            if p0 is not None and expectation_clear is not None:
                if p0 >= p0_floor and expectation_clear >= clarity_floor:
                    return (
                        tier,
                        row_id,
                        f"P(0)={p0} >= {p0_floor} and "
                        f"expectation_clear={expectation_clear} >= {clarity_floor}",
                    )
            continue

        if row_id == "reduced":
            p0_floor = row.get("p0_floor", 0.40)
            sum_floor = row.get("bucket_sum_floor", 0.85)
            if p0 is not None and p1 is not None:
                bucket_sum = p0 + p1
                if p0 >= p0_floor and bucket_sum >= sum_floor:
                    return (
                        tier,
                        row_id,
                        f"P(0)={p0} >= {p0_floor} and "
                        f"P(0)+P(1)={bucket_sum} >= {sum_floor}",
                    )
            continue

        # `full`, or any future unconditional fallthrough row: matches
        # whenever reached, since nothing above it matched.
        return (
            tier,
            row_id,
            "no higher-tier threshold row matched (fell through to the "
            "removes-nothing row)",
        )

    # Every row was a conditional row (minimal/reduced) and none matched,
    # with no unconditional fallthrough row present in the table.
    return (SAFEST_TIER, None, "no threshold row matched and no fallthrough row exists")


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

    observed = {
        "jev_available": jev_available,
        "codex_available": codex_available,
        "basis": payload.get("basis"),
        "score": payload.get("score"),
    }

    if not jev_available:
        # fallback_matrix: jev_unusable -- decides full regardless of
        # codex_available (FR13).
        return _safest_result(
            "judgement skill unusable (non-zero Jev exit status or "
            "explicitly reported unavailable)",
            "fallback_matrix:jev_unusable",
            observed,
        )

    score = payload.get("score")
    if not isinstance(score, dict):
        return _safest_result(
            "missing or non-object 'score'", "fallback_matrix:malformed_input", observed
        )

    tier, row_id, reason = evaluate_thresholds(rules, score)
    decided_by = f"threshold_rows:{row_id}" if row_id else "fallback_matrix:malformed_rules"
    return {
        "tier": tier,
        "decided_by": decided_by,
        "reason": reason,
        "observed": observed,
    }


def main(argv):
    rules_path = argv[1] if len(argv) > 1 else str(DEFAULT_RULES_PATH)

    try:
        raw_stdin = sys.stdin.read()
    except Exception as exc:  # pragma: no cover - defensive, stdin itself broken
        result = _safest_result(f"could not read stdin: {exc}", "fallback_matrix:error", None)
        print(json.dumps(result))
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

    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
