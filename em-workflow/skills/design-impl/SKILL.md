---
name: design-impl
description: デザイン実装の知識（em-workflow implementer 動的注入用）。UI デザイン・スタイリング・レイアウトの原則、アクセシビリティ、E2E 寄りのテスト戦略、品質チェックリストと落とし穴を提供します。タスクの skills に design-impl が指定されたときに implementer がロードします。
user-invocable: false
---

# Implementation Skill: Design (UI / styling / layout)

Layer-specific knowledge for tasks whose primary output is visual. TDD
discipline itself comes from the preloaded `tdd-testing` skill — this skill
supplies the design-layer strategy on top.

## Principles

- **Follow the project's existing design system first**: tokens (colors,
  spacing, typography), component variants, naming. Introduce a new token
  only when the task plan says so; hardcoded one-off values are the top
  design-debt source.
- **Layout robustness over pixel perfection**: content of varying length,
  wrapping, overflow, empty states, and small viewports are part of the
  deliverable, not extras. Wide content scrolls inside its own container;
  the page never scrolls horizontally.
- **Relative units and intrinsic sizing** (flex/grid, max-width, min-height:
  0 for scrollable flex children) over fixed dimensions.
- **States are design**: hover, focus-visible, active, disabled, loading,
  error, empty. A component without designed states is half-implemented.
- **Theme-awareness**: if the project supports light/dark themes, verify
  both; never hardcode a color that bypasses the theme mechanism.

## Accessibility (non-negotiable baseline)

- Semantic elements over div-soup (`button`, `nav`, `label` + `for`, heading
  hierarchy without level skips).
- Keyboard operability: focus order matches visual order; visible focus
  indicator; no keyboard traps; Escape closes what it opened.
- Contrast: body text ≥ 4.5:1, large text/UI graphics ≥ 3:1.
- Images/icons that convey meaning get text alternatives; decorative ones
  are hidden from AT.
- Motion respects `prefers-reduced-motion`.

## Test strategy (E2E-leaning)

- Prefer rendered-output verification: E2E / component-render tests
  asserting visible text, roles, states — not CSS property values.
- Assert accessibility contracts in tests (role, accessible name, focus
  behavior) — they double as behavior tests and survive restyling.
- Visual regression snapshots only where the project already has the harness.
- What cannot be automated (subjective spacing, cross-device rendering):
  list it explicitly in your report as manual-verification items — the
  tdd-testing skill's poor-fit rules apply.

## Pitfalls

- Styling leaking outside the task's scope: global selector changes ripple
  everywhere — scope styles to the component per project convention.
- z-index escalation wars; prefer stacking-context fixes.
- Absolute positioning to "make it look right" that breaks at other content
  lengths.
- Removing outline without a replacement focus style.
- Overriding the design system inline instead of extending it where the
  plan calls for a variant.
