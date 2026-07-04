---
name: infra-impl
description: インフラ・設定実装の知識（em-workflow implementer 動的注入用）。CI・ビルドスクリプト・設定・環境配線の作法、検証可能性を軸にしたテスト戦略、品質チェックリストと落とし穴を提供します。タスクの skills に infra-impl が指定されたときに implementer がロードします。
user-invocable: false
---

# Implementation Skill: Infra (config / CI / build / tooling)

Layer-specific knowledge for tasks whose primary output is configuration or
automation. TDD discipline comes from `tdd-testing`; this adds the infra
strategy (where "test" usually means "provable execution").

## Principles

- **Reproducibility first**: same input, same result — pin versions
  (toolchains, actions, base images, lockfiles) per project convention;
  "latest" is a bug unless the plan says otherwise.
- **Fail loud, fail early**: scripts run with strict modes (`set -euo
  pipefail` in bash), explicit exit codes, and error messages that name the
  failing step. Silent fallbacks hide breakage.
- **Idempotency**: setup/config scripts runnable twice without damage;
  guards over "run once" assumptions.
- **Secrets stay out of files**: wire through the project's secret
  mechanism (CI secrets, env indirection); never commit tokens, and never
  echo them into logs.
- **Least surprise in CI**: cache keys derive from the exact inputs
  (lockfile hashes); jobs declare needs explicitly; matrix entries stay
  minimal and intentional.

## Config hygiene

- One SSOT per setting: derive, don't repeat, a value across files. When
  duplication is forced (tool limitations), add a comment pointing at the
  SSOT.
- Environment differences are data (per-env files/vars), not branching
  logic scattered through scripts.
- Comments in config explain WHY (constraints, gotchas), not what the next
  line does.

## Verification strategy (execution IS the test)

- The primary check: run the thing. Build script → run the build; CI
  change → run the pipeline (or its runnable local equivalent, e.g. the
  project's lint/dry-run harness); config → boot the component consuming it.
- Use dry-run/validate modes where the toolchain has them
  (`--dry-run`, config-check subcommands, schema validation) and wire them
  into the task's acceptance evidence.
- Assert failure paths too: a guard script must be shown to FAIL on the bad
  input it guards against.
- What cannot be executed inside the worktree (deploy steps, remote-only
  CI): state exactly that in your report as manual-verification items with
  the command to run.

## Pitfalls

- Quoting/word-splitting bugs in shell (paths with spaces); prefer arrays
  and `"$var"` everywhere.
- Non-portable assumptions (GNU-only flags, host-specific paths, implicit
  cwd) — respect the project's declared platforms.
- Cache poisoning: over-broad cache keys serving stale dependencies.
- CI steps that pass because they silently did nothing (empty glob, `|| true`).
- Permission/security drift: world-writable artifacts, tokens with broader
  scope than the task needs, `curl | sh` installs (hard-refused by the
  command gate anyway).
