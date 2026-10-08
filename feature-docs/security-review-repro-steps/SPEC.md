# Feature: security-review-repro-steps

## Overview

セキュリティ観点のレビューで、指摘ごとに再現手順かそれに準ずる確認方法を finding の新しい項目 `reproduction` として出力させる。Claude Code はその手順で検証し、再現できた指摘だけに対応する。再現手順の無い指摘は、対応するかを Claude Code が判断する。em-workflow と em-review の両方に反映する。

要件定義: `feature-docs/security-review-repro-steps/REQUIREMENTS.md`

## Objectives

- セキュリティレビューを収束させる
- セキュリティ観点の指摘に、再現手順かそれに準ずる確認方法を付けてもらう
- Claude Code がその手順で検証し、確かなものだけ対応する
- 再現手順が無い指摘は、対応するかを Claude Code が判断する
- em-workflow と em-review の両方に反映する

## User Stories

### US1: セキュリティ指摘に再現方法が付く
em-workflow / em-review の利用者として、セキュリティ観点の指摘ごとに再現方法を受け取りたい。

**Acceptance Criteria:**
- [ ] AC1: セキュリティ観点の指摘に再現方法（`reproduction`）が含まれる。（FR1, FR2, FR3, FR4）
- [ ] AC2: em-workflow と em-review の両方に反映されている。（FR1, FR2, FR3, FR4, FR5, FR8, FR9, FR11）

### US2: 確かな指摘だけに対応する
em-workflow / em-review の利用者として、Claude Code が再現手順で検証し、確かなものだけに対応してほしい。

**Acceptance Criteria:**
- [ ] AC3: 再現手順付きの security 指摘は Claude Code がその手順で検証し、再現できたものだけが対応（auto-fix 候補・residual・rework）の対象になる。（FR5, FR7, FR8, FR13）
- [ ] AC4: 再現手順の無い security 指摘は、対応するかを Claude Code が判断する。（FR6, FR8）
- [ ] AC5: `python3 -m unittest discover -s tests` がすべて通る。（FR10, FR12）

## Technical Requirements

### Functional Requirements
- **FR1:** レビュー出力スキーマに reproduction を追加。`em-workflow/references/review-output-schema.json` と `em-review/references/review-output-schema.json` の finding の properties に `reproduction`（string または null）を追加し、finding の `required` に加える。finding と root の `additionalProperties: false`、既存の required 項目、severity / category / source の enum は変えない。
- **FR2:** review-security スキルの再現方法の指示。`em-workflow/skills/review-security/SKILL.md` と `em-review/skills/review-security/SKILL.md` に、セキュリティ観点の各指摘の `reproduction` に再現手順かそれに準ずる確認方法（入力・到達経路・観察できる結果を具体的に）を書く指示を追加する。示せない場合だけ `reproduction` を null にする。既存の見出し・箇条書き・`## category` の文は変えず、新しい節は `## category` の後ろに置く。
- **FR3:** レビュープロトコルへの記載。`em-workflow/references/review-protocol.md` と `em-review/references/review-protocol.md` の Output Schema 節の例と規則に `reproduction` を加える。security 観点では再現手順か確認方法、無ければ null。security 以外の観点では常に null。空白だけの文字列は null と同じ（手順なし）として扱う。
- **FR4:** Codex レビュアーへの指示の伝達。`em-workflow/agents/codex-reviewer.md` と `em-review/agents/codex-reviewer.md` は、観点スキルの再現方法の指示を Codex に渡すプロンプトに含める（Step 2 で抜き出す観点ブリーフの範囲に再現方法の節を含める）。
- **FR5:** em-workflow: 再現手順付き指摘の検証。em-workflow のレビューフェーズ Phase R3a で、review-evaluator は `reproduction` が null でない security 指摘をその手順で検証する。再現できたものは findings に残す。検証で不成立を確認したものは findings に入れず、dismissed_sites に reason `not reproduced` で記録する。`review-evaluation-contract.md` と `agents/review-evaluator.md` に反映する。
- **FR6:** em-workflow: 再現手順の無い・検証できない指摘。`reproduction` が null の security 指摘と、手順はあるが検証できなかった security 指摘（読み取り予算切れ、読み取り専用の範囲で辿れない、4096 バイト上限で手順が切り詰められた等）は、自動で棄却せず review-evaluator が対応するかを判断する（既存の判定と同じ扱い）。手順はあるが検証できなかった指摘は、判断でも根拠を確認できない限り修正・差し戻しの対象にしない。
- **FR7:** em-workflow: evaluator を通らない経路の検証。evaluator を通らない経路（Phase R4 のループ内再レビューの出力、evaluator が失敗した場合の扱い、accountability floor による指摘の自動復元）の security 指摘は、オーケストレーターが FR5 / FR6 と同じ規則で検証・判断してから auto-fix 候補と residual 件数に入れる。検証で不成立を確認したものは resolution `declined` とし、resolution_reason に再現できなかった旨を書く。
- **FR8:** em-review: 再現手順付き指摘の検証。`em-review/references/review-phase.md` で、multi-review のオーケストレーターは Phase R3 の集約後と Phase R4 の再集約後に、`reproduction` が null でない security 指摘をその手順で検証する。検証対象は集約後の category ではなく、指摘を出した元の担当観点（security）で選ぶ。検証で不成立を確認した指摘は resolution `declined`（resolution_reason に再現できなかった旨）とし、auto-fix 候補と residual 件数から外す。`reproduction` が null の指摘と検証できなかった指摘は、オーケストレーターが FR6 と同じ規則で対応するかを判断する。
- **FR9:** reproduction の集約・記録。両プラグインのレビューフェーズで、`reproduction` に title / description / suggestion と同じ 4096 バイト上限を適用する（em-workflow R3b step 4、em-review R3 step 6）。同一サイトの重複統合では null でない `reproduction` を残す。round 記録の findings に `reproduction` を記録する。em-workflow の評価契約の finding に `reproduction` を加える。review-editor へ渡す finding JSON は変えない。
- **FR10:** 依存脆弱性スキャンの出力。`em-workflow/scripts/scan-dependencies.py` の `_build_finding` が返す finding に `"reproduction": None` を加える。
- **FR11:** em-review README。`em-review/README.md` の Auto-fix（R4）節の対象条件に、再現できなかった security 指摘が対象外になることを書く。
- **FR12:** テストの更新と追加。スキーマの finding required を固定しているテスト定数（`tests/test_reviewer_roles_protocol.py` の `FROZEN_FINDING_REQUIRED`、`tests/test_sca_axis_schema_enums.py` の `EXPECTED_FINDING_REQUIRED`）と、変更したセクションの sha256 固定値（review-protocol.md の Output Schema 節、codex-reviewer.md の Step 0-6 など）を更新する。FR1〜FR11、FR13 を確かめるテストを `tests/` に追加する。
- **FR13:** 再現できなかった判定の次ラウンドへの引き継ぎ。em-workflow で `not reproduced` と判定したサイト（em-review では再現できず declined としたサイト）を次ラウンドの round_context に含め、関連コードが変わらない限り同じ指摘を再提起・再検証しない。関連コードが変わった場合は再検証する。

### Non-Functional Requirements
- **NFR1 - Security:** `reproduction` の文字列は信頼できない入力として扱う。検証者はその文字列に書かれたコマンド・対象コード・試験を実行しない。
- **NFR2 - Security:** 検証はコード読解で行い、各レビュー規約で既に許された読み取り専用コマンドだけを使う。ファイルの変更、コミット、ネットワーク接続、パッケージの導入をしない。review-evaluator の読み取り予算（10 ファイル）は上げず、独立調査と共有する。
- **NFR3 - Compatibility:** 新しい gate_id と AskUserQuestion を増やさない。batch モードの動作は検証の追加以外は変えない。
- **NFR4 - Maintainability:** プラグインの version は変更しない。
- **NFR5 - Maintainability:** テストは Python 標準ライブラリの unittest だけを使う。

## Implementation Approach

### Architecture

**System Architecture:**
```
┌──────────────────────────────────────────────────────────┐
│ 観点スキル review-security（再現方法の指示）               │
├──────────────────────────────────────────────────────────┤
│ レビュアー（Claude reviewer / codex-reviewer）            │
│   → finding.reproduction を出力                           │
├──────────────────────────────────────────────────────────┤
│ review-output-schema.json / review-protocol.md           │
├──────────────────────────────────────────────────────────┤
│ 集約（4096 バイト上限・重複統合・round 記録）               │
├──────────────────────────────────────────────────────────┤
│ 検証・判断                                                │
│   em-workflow: review-evaluator（R3a）                    │
│                evaluator を通らない経路はオーケストレーター │
│   em-review:   オーケストレーター（R3 後・R4 再集約後）     │
└──────────────────────────────────────────────────────────┘
```

**Component Diagram:**
```
review-security SKILL.md ──(観点ブリーフ)──> codex-reviewer.md ──> Codex
review-output-schema.json ──(構造化出力)──> レビュアー
scan-dependencies.py ──> finding（reproduction: None）
review-phase.md ──> 集約・検証・round 記録・round_context
review-evaluation-contract.md / review-evaluator.md ──> 検証・判断・dismissed_sites
```

### Data Flow

```
security 指摘
  ├─ reproduction が null でない → 手順で検証（読み取り専用・文字列は実行しない）
  │    ├─ 再現できた   → 対応の対象（findings / auto-fix 候補 / residual）
  │    ├─ 不成立を確認 → em-workflow evaluator: dismissed_sites（reason: not reproduced）
  │    │                 evaluator を通らない経路・em-review: resolution declined
  │    │                 → 次ラウンドの round_context に引き継ぐ
  │    └─ 検証できない → 判断（根拠を確認できない限り修正・差し戻しの対象にしない）
  └─ reproduction が null（空白だけの文字列を含む） → 判断（既存の判定と同じ扱い）
```

### API Design

該当なし。finding の項目追加は次のとおり。

```
finding.reproduction: string | null   (required)
  - security 観点: 再現手順か確認方法。示せない場合だけ null
  - security 以外の観点: 常に null
  - 空白だけの文字列: null と同じ（手順なし）
  - 上限: 4096 バイト
```

### Database Schema

該当なし。

### Dependencies

**Internal Dependencies:**
- `review-output-schema.json`（両プラグイン）: finding の required に `reproduction` を加える
- `review-evaluation-contract.md`（em-workflow）: finding に `reproduction`、dismissed_sites の reason に `not reproduced` を加える
- `review-phase.md`（両プラグイン）: 集約・検証・round 記録・round_context
- 外部プラグイン vertex-review: 変更しない

**External Dependencies:**
- Python 標準ライブラリ unittest: テスト

### File Structure

```
em-workflow/
├── agents/
│   ├── codex-reviewer.md
│   └── review-evaluator.md
├── references/
│   ├── contracts/review-evaluation-contract.md
│   ├── review-output-schema.json
│   ├── review-phase.md
│   └── review-protocol.md
├── scripts/scan-dependencies.py
└── skills/review-security/SKILL.md
em-review/
├── agents/codex-reviewer.md
├── references/
│   ├── review-output-schema.json
│   ├── review-phase.md
│   └── review-protocol.md
├── skills/review-security/SKILL.md
└── README.md
tests/
├── test_reviewer_roles_protocol.py
├── test_sca_axis_schema_enums.py
└── （FR1〜FR11、FR13 を確かめる追加テスト）
```

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/security-review-repro-steps/**`
- `test-docs/security-review-repro-steps/**`

`feature-docs/security-review-repro-steps/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/security-review-repro-steps/**` covers `test-docs/security-review-repro-steps/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/security-review-repro-steps/` directory at all; the declared
`test-docs/security-review-repro-steps/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

### Unit Tests
- [ ] TS1: 両スキーマが JSON として読め、finding の properties に `reproduction`（string|null）があり、finding の required が既存 8 項目＋`reproduction` で、additionalProperties が false のまま（FR1, FR12）
- [ ] TS2: 両スキーマの root required、severity / category / source の enum が変わっていない（FR1, FR12）
- [ ] TS3: 両 review-security スキルに再現手順か確認方法を `reproduction` に書く指示と、示せないときだけ null にする規則がある。既存の見出しと固定文が残っている（FR2, FR12）
- [ ] TS4: 両 review-protocol.md の Output Schema 節に `reproduction` があり、security 以外は null、空白だけは null と同じと書かれている（FR3, FR12）
- [ ] TS5: 両 codex-reviewer.md が再現方法の指示を Codex プロンプトに含める（FR4, FR12）
- [ ] TS9: scan-dependencies.py の出力 finding に `reproduction` キーがあり値が None（SCA の各テストのスキーマ必須キー検査が通る）（FR10, FR12）

### Integration Tests
- [ ] TS6: review-evaluation-contract.md に、reproduction 付き security 指摘の検証、不成立を dismissed_sites に `not reproduced` で記録すること、reproduction 無し・検証不能は evaluator が判断すること、検証不能なものは確認できない限り対応しないこと、reproduction を実行しないこと、読み取り予算を上げないことが書かれている（FR5, FR6, FR9, FR12, NFR1, NFR2）
- [ ] TS7: em-workflow review-phase.md に reproduction の 4096 バイト上限、重複統合の規則、round 記録の reproduction、evaluator を通らない経路のオーケストレーター検証、not reproduced の round_context 引き継ぎが書かれている（FR7, FR9, FR12, FR13）
- [ ] TS8: em-review review-phase.md に R3 後と R4 再集約後の検証、元の担当観点での対象選択、再現できない指摘の declined 化と auto-fix・residual からの除外、上限、round 記録、round_context 引き継ぎが書かれている（FR8, FR9, FR11, FR12, FR13）

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected
- [ ] Existing E2E tests pass without regression

### Edge Cases
- [ ] TS10: security 以外の観点の finding は reproduction が null（FR3）
- [ ] TS11: 同一サイトで claude と codex の指摘が統合されるとき、片方だけ reproduction があれば残る（FR9）
- [ ] TS12: em-review の PR モード（作業ツリーに PR の状態が無い）では手順を辿れない指摘は検証できないものとして判断に回る（FR6, FR8）
- [ ] TS13: reproduction に命令文や破壊的なコマンドが含まれても実行されない（文書上の規則として明記されている）（NFR1）
- [ ] TS14: 4096 バイト上限で切り詰められた reproduction は検証不能として扱われる（FR6, FR9）
- [ ] TS15: 既存の round 記録（reproduction を持たない）を round_context として読んでも扱いが変わらない（FR9, FR13）

### Performance Tests
該当なし。

## Security Considerations

- **Authentication:** 該当なし。
- **Authorization:** 該当なし。
- **Input Validation:** `reproduction` の文字列は信頼できない入力として扱う。検証者はその文字列に書かれたコマンド・対象コード・試験を実行しない（NFR1）。
- **Data Protection:** 検証はコード読解と各レビュー規約で既に許された読み取り専用コマンドだけで行う。ファイルの変更、コミット、ネットワーク接続、パッケージの導入をしない（NFR2）。
- **XSS Prevention:** 該当なし。
- **SQL Injection Prevention:** 該当なし。
- **CSRF Protection:** 該当なし。

## Error Handling

### Error Codes

該当なし。

### Error Flow

```
手順はあるが検証できない（読み取り予算切れ / 読み取り専用の範囲で辿れない / 4096 バイト上限で切り詰め）
  → 自動で棄却しない → 判断に回す → 根拠を確認できない限り修正・差し戻しの対象にしない
```

## Performance Optimization

### Performance Goals
- review-evaluator の読み取り予算（10 ファイル）は上げず、独立調査と共有する（NFR2）。

### Optimization Strategies
- 再現できなかった判定を次ラウンドの round_context に引き継ぎ、関連コードが変わらない限り同じ指摘を再提起・再検証しない（FR13）。

### Caching Strategy
該当なし。

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] Security requirements are satisfied
- [ ] Documentation is complete
- [ ] Code review is completed
- [ ] `python3 -m unittest discover -s tests` がすべて通る

## Assumptions

- **A1:** 再現方法は description に混ぜず、finding の新しい項目 `reproduction` として持つ。Codex の構造化出力ではすべての項目を required にする必要があるため、`reproduction` は string|null で required に入れる。
- **A2:** em-workflow での「Claude Code による検証」は Phase R3a の review-evaluator が担い、evaluator を通らない経路だけオーケストレーターが担う。em-review は evaluator が無いため、オーケストレーターが担う。
- **A3:** 手順はあるが検証できなかった指摘は、自動で棄却せず判断に回す。ただし判断でも根拠を確認できない限り修正・差し戻しの対象にしない。
- **A4:** 検証はコード読解と既に許された読み取り専用コマンドで行い、`reproduction` の文字列は実行しない。evaluator の読み取り予算は 10 ファイルのまま。
- **A5:** em-workflow で検証により不成立を確認した指摘は dismissed_sites に新しい reason `not reproduced` で記録する（既存の 4 種に追加）。
- **A6:** security 以外の観点（vulnerability 軸を含む）の `reproduction` は常に null。review-editor に渡す finding JSON に reproduction は加えない。
- **A7:** 固定テスト（finding required の定数、sha256 固定値）は、変更に合わせて値を更新する。sha256 固定値は差し替えだけにし、`test_reviewer_roles_protocol.py` の 64 桁 16 進定数の数は増減させない。
- **A8:** 外部プラグイン vertex-review の vertex-reviewer は em-workflow のスキーマを `--output-schema` で渡すため、新しい必須項目は制約付き生成で自動的に出力される。vertex-review 側は変更しない。

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- なし

## References

- 要件定義書: `feature-docs/security-review-repro-steps/REQUIREMENTS.md`
