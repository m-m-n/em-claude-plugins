# Threat Model: test-hook-precedence-wording

## Verdict
no-trust-boundary

## Rationale
Inspected: TASK.md (minimal tier; SPEC.md and REQUIREMENTS.md are subtracted) and the single task task0001, whose domains are [config-infra]. None of auth / input-handling / external-io / data-persistence applies, so the analysis ran at standard depth.

The change rewrites English prose only (comments, docstrings and assertion-message strings) in tests/test_guardrail_hooks_migration.py, tests/test_muse_guard_registration.py and tests/test_hooks_registration.py. Assertion expressions, expected values, EXPECTED_BASH_GUARD_ORDER, test names, em-workflow/hooks/hooks.json and the hook scripts stay unchanged, so the registration order the tests pin and every guard decision keep their current behavior. The change introduces no input source, external service, process interaction, privilege change or prompt interpolation; no data or control crosses between parties of different trust.
