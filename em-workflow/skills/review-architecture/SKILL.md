---
name: review-architecture
description: アーキテクチャ観点のレビュー知識（em-workflow 動的注入用）。レイヤー違反・循環依存・神クラス・破壊的インターフェース変更・重大な SOLID 違反を検出する基準を汎用レビュアーに与えます。オーケストレーター指示以外で自発的にロードするものではありません。
user-invocable: false
---

# Review Perspective: Architecture

This skill defines WHAT the architecture perspective flags. Discipline comes
from the reviewer agent + review-protocol.md.

## What to flag (architecture only)

- **Layer violations**: domain importing infrastructure, UI reaching into
  the DB, presenter calling the controller, etc.
- **Cyclic dependencies**: package A → B → A present in the reviewed code.
- **God class / god function**: a class or function that absorbs unrelated
  responsibilities, especially when the change expands the issue further.
- **Breaking interface changes**: public APIs / exported types / DB schema
  changed without migration; callers not updated consistently.
- **Severe SOLID violations**: clear SRP / OCP / LSP / ISP / DIP breaks
  (control-flag parameters, downcast-required dispatch, leaking concrete
  types through the interface).
- **Coupling / abstraction smells with concrete cost**: shotgun surgery,
  primitive obsession around critical domain concepts, inverted control
  flow.
- **Contract drift between SSOT and consumers** when reviewing
  protocol/manifest-style codebases.

## What NOT to flag

Subjective taste, "could be cleaner" without concrete maintenance cost.

## category

Every finding MUST have `"category": "architecture"`.
