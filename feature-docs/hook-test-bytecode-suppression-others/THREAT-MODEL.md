# Threat Model: hook-test-bytecode-suppression-others

## Verdict
no-trust-boundary

## Rationale
Inspected SPEC.md, REQUIREMENTS.md and the two task plans (tier: full; task
domains: `config-infra` only, none of the four depth-adjusting domains). The
change is confined to seven test modules under `tests/`, which load
first-party hook files from the same repository into the test process and, at
most, start those same hooks as child interpreters with bytecode writing
disabled. No data crosses between parties of different trust: there is no
user or external input, no external service, no file from outside the project,
no untrusted text reaching an LLM prompt, and no privilege change. The only
state touched is the test process's own bytecode flag, a correctness concern
covered by the task Acceptance Criteria (SPEC.md FR1, FR2, EC1), not a
security threat.
