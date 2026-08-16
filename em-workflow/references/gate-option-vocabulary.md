# Gate Option Vocabulary (em-workflow)

Referenced by `references/batch-policies.yaml`'s header comment and by
`references/question-resolution.md`'s Batch resolution sequence. This
document is the SSOT for the correspondence rule between a select gate's
policy `option_id` and the option_ids its issuing site actually offers, for
the canonical, machine-readable format an issuing document uses to declare
those option_ids, and for the registry of gates that rule cannot be checked
against mechanically.

## Correspondence rule

For every gate whose `references/batch-policies.yaml` entry is
`action: select` with an `option_id`, that `option_id` must be among the
option_ids the gate's issuing site declares it offers.
`references/batch-policies.yaml` is the authoritative side of this
relationship: reconciliation always moves the issuing site toward the
policy file, never the policy file toward the issuing site.

## Why it matters

`references/question-resolution.md`'s Batch resolution sequence applies a
policy's `option_id` to the gate's question and, when that option ID is not
present among the question's own `options[].option_id`, treats the mismatch
as a protocol error and aborts the phase — at a gate that is otherwise a
non-blocking preference. The correspondence rule exists to make that
protocol-error abort unreachable at every select gate this document's
registry does not exempt.

## Canonical declaration format

An issuing document declares the option_ids it offers for a gate in a
dedicated level-2 section headed exactly `## Gate option vocabulary`. The
section holds one Markdown table, whose header row names, in this order, a
gate-id column, an option-id column and a meaning column. Each data row
carries:

1. exactly one backtick-quoted `gate_id` in the first cell;
2. exactly one backtick-quoted `option_id` in the second cell;
3. a non-empty prose meaning in the third cell.

One row per offered option — a gate whose select decision offers three
options occupies three rows, one per option_id. The set of option_ids a
document offers for a gate is exactly the second-cell values of the rows
whose first cell names that gate; nothing outside this block counts toward
it.

### Why not `## Gate identifiers`

`em-workflow/scripts/validate-worker-output.py` — a frozen script — derives
a gate registry by scanning, in each worker contract, the section headed
`## Gate identifiers` for backtick-quoted tokens of the `namespace.name`
shape, attributing each found gate to that contract's worker and then
enforcing the policy's `option_id` for it. Only one contract carries that
section today, which is exactly why the wider fixture corpus is free to
reuse other gate_ids with unrelated option vocabularies. Declaring an
option vocabulary inside `## Gate identifiers`, or adding that heading to a
contract that lacks it, would silently start enforcing policy option_ids
against that whole fixture corpus and would contradict an existing test
that pins one gate as worker-unattributed. The declaration format therefore
uses its own, distinct level-2 heading — `## Gate option vocabulary` — so a
future editor does not "simplify" the two headings back into one.

## Issuing-site map

The association from a gate_id to the document paths whose
`## Gate option vocabulary` section must declare that gate is pinned in
exactly one place: the correspondence-check module under `tests/`. This
document cites that module as where the map lives and does not restate its
rows — one map, one place.

## Exemption registry

A gate listed in `references/batch-policies.yaml` as `action: select` with
an `option_id` can, in principle, be one this document's correspondence
rule cannot be checked against mechanically. This table is the ONLY source
of such exemptions: the correspondence-check module holds no exemption list
of its own, so a gate is exempted only by appearing here, with a reason and
a compensating guarantee. An absent registry file — for example while this
document and the check that consumes it are still merging in from separate
tasks — is read as zero exemptions, never as a reason to skip the check.

| gate_id | reason | compensating guarantee |
|---------|--------|-------------------------|

This registry currently holds zero rows: every `action: select` gate that
carries an `option_id` is checked mechanically today, and none of them is
exempted.

## Scope

This document introduces no policy decision and no gate's option vocabulary
of its own. `references/batch-policies.yaml` remains the single policy
table.
