# Threat Model: scenario-id-fence-scope

## Verdict
no-applicable-threat

## Rationale
Inspected SPEC.md (reduced tier, no REQUIREMENTS.md and no DESIGN.md) and the
function it changes, `find_hyphenless_scenario_ids` in
`em-workflow/scripts/validate-worker-output.py`. The `input-handling` domain set
the analysis depth.

One trust boundary exists: VERIFICATION.md and task plans written by an LLM
worker are read by the deterministic validator. No STRIDE category
realistically applies to this change at that boundary. The change only moves
which text regions the form check skips. The function stays a pure text scan
(NFR1), grants nothing, and returns only matched scenario IDs. Its callers keep
the existing read path, which bounds the size and refuses symlinks, so the line
scan adds no new exposure or resource path.

A worker can keep a hyphen-less ID out of the check by leaving a line-start
fence unclosed. SPEC.md accepts this as A1. The check enforces a format rule:
the read side accepts both ID forms and no security decision depends on the
form, so no mitigation is written for it.

task0001 declares `input-handling`. Its files appear in no `Boundary files`
line because the short form has none; the reasoning above covers that domain.
