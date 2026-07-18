---
name: review-license
description: ライセンス整合観点のレビュー知識（em-workflow 動的注入用）。diff が依存マニフェストや vendored コードに触れたとき裁量層で追加され、新規依存のライセンスが project.license と両立するかを references/license-compat.md の基準で検査します。オーケストレーター指示以外で自発的にロードするものではありません。
user-invocable: false
---

# Review Perspective: License

This skill defines WHAT the license perspective flags. Discipline (protocol,
budget, schema, read-only) comes from the reviewer agent + review-protocol.md.

## Inputs

- `project_license` from your input block (SPDX id or `none`). If the field
  is absent, detect it from `{project_root}/LICENSE*` (title line). When it
  is `none`, only flag unknown-license and strong/network-copyleft additions
  (they narrow the future license choice) at severity ≤ medium.
- Compatibility criteria: Read
  `${CLAUDE_PLUGIN_ROOT}/references/license-compat.md`. If the path does not
  resolve, Glob `$HOME/.claude/plugins` / `$HOME/.claude/skills` for
  `**/em-workflow/*/references/license-compat.md`. Never read it from cwd.

## What to flag (license only)

- **Incompatible new dependency**: a dependency ADDED by the diff whose
  license conflicts with `project_license` per license-compat.md. Strong or
  network copyleft entering a permissive project is `critical`.
- **Unknown-license dependency**: added dependency whose license cannot be
  determined from the manifest/lockfile/registry evidence in the repo.
- **Vendored/copied code**: source added by the diff carrying a license
  header or LICENSE file that conflicts with `project_license`, or copied
  code whose required attribution/notice was stripped.
- **Contradictory license metadata**: changes to LICENSE or manifest license
  fields (package.json `license`, Cargo.toml `[package] license`, etc.) that
  contradict each other or the actual dependency set.
- **LGPL in static-linking ecosystems** (Go, Rust, single-binary deploys):
  flag for explicit confirmation (`medium`), per license-compat.md rule 4.

## What NOT to flag

- Pre-existing dependencies the diff does not touch.
- Dev-only tooling that is not distributed with the artifact, unless its
  output embeds its own code.
- Legal speculation beyond license-compat.md — for genuinely ambiguous
  cases, recommend human/legal review instead of inventing a verdict.

## category

Every finding MUST have `"category": "license"`.
