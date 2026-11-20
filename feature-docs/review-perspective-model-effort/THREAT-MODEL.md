# Threat Model: review-perspective-model-effort

## Verdict
threats-identified

## Rationale
Inspected: SPEC.md, REQUIREMENTS.md and the files the plan changes — the two
`run_codex_exec.sh` wrappers, the two `reviewers.yaml` registries, the two
`codex-reviewer.md` agents, both `review-protocol.md` and `review-phase.md`
documents, both READMEs, `.claude/skills/security-review-model/SKILL.md`, the
version manifests and the tests. Tier: full. Domains that set the depth:
`input-handling` (task0001) deepens TB-1; `data-persistence` (task0004) is
discussed below.

One trust boundary exists. The `effort` string reaches the wrapper as a
command-line argument written by its caller, the codex-reviewer agent, which
also reads untrusted reviewed content (the diff and files). The wrapper embeds
that string into a TOML-parsed `-c` override of the Codex launch. This is the
only place where the new value crosses into a more privileged interpreter.

Hops that are not trust boundaries:

- `reviewers.yaml` → orchestrator → codex-reviewer input block. The registry
  is a file of the installed plugin, at the same trust level as the agent and
  reference documents that read it. The `model` value already travels this
  path. FR7 deliberately adds no allow-list check here; the wrapper check of
  TB-1 is the only validation the value gets.
- The round record field `effort` (task0004, domain `data-persistence`). The
  orchestrator writes the value from its own dispatch data into its own round
  record. No party of a different trust level writes or reads it across a
  boundary, so task0004's files appear in no `Boundary files` line.

## Trust Boundaries

### TB-1: wrapper `--effort` argument into the Codex launch configuration
Crossing: the `--effort LEVEL` value, written into the wrapper's argv by its
caller (the codex-reviewer agent, whose context holds untrusted reviewed
content), into a `-c 'model_reasoning_effort="LEVEL"'` TOML override that
configures the `codex exec` launch.
Boundary files: em-workflow/scripts/run_codex_exec.sh, em-review/scripts/run_codex_exec.sh
Depth: deep (input-handling)

| STRIDE category | Threat | Mitigation ID | Mitigation | Implemented by | Verified by |
|---|---|---|---|---|---|
| Elevation of privilege | A value carrying a double quote, backslash, whitespace or other TOML syntax closes the effort string and injects further configuration into the launch (for example a looser sandbox or approval setting), so the read-only review launch gains capabilities it must not have (FR3, NFR2). | TM-1 | The wrapper embeds LEVEL only when it matches `^[a-z]+$`; a missing or non-matching value exits 1 with a one-line stderr message and launches no `codex exec`. | task0001 AC-4 | VERIFICATION.md Performance / Security Verification item TM-1 (TS-5) |
