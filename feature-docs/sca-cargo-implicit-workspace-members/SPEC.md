# Feature: sca-cargo-implicit-workspace-members

## Overview

SCA 軸 2 の cargo スキャン単位で、ルートの Cargo.toml が `[workspace]` を持ち、ルートの依存テーブルに path 依存があるとき、直接依存の集合を不完全（complete=False）として扱う。これにより、path 依存で暗黙にワークスペースメンバーになったクレートの直接依存に対する advisory を、推移的依存として捨てずに cargo の判定不能件数の注記（cargo_directness_undetermined）に残す。

## Objectives

- SCA 軸 2 の cargo スキャン単位で、Cargo の path 依存によって暗黙にワークスペースメンバーになったクレートがあるとき、メンバー側の直接依存に対する advisory が推移的依存として黙って捨てられないようにする
- その advisory を、既存の判定不能件数の注記（cargo_directness_undetermined）に残す

## Acceptance Criteria

- [ ] AC1（FR1, FR4）: `members` の無い `[workspace]` と `member = { path = "member" }` を持つルートの Cargo.toml で、宣言されていないクレートに閾値以上の advisory があるとき、finding は出ず、`skipped` は false、`skip_reason` は None のまま、summary の末尾に cargo の判定不能注記が件数 1 で出る。
- [ ] AC2（FR1, FR4）: `members = []` の `[workspace]` と path 依存を持つルートの Cargo.toml で、AC1 と同じ結果になる。
- [ ] AC3（FR1）: path を持つエントリが `dev-dependencies`、`build-dependencies`、`target.<cfg>` 配下の依存テーブル、サブテーブルの形のいずれにあっても、AC1 と同じく判定不能として数えられる。
- [ ] AC4（FR2）: `[workspace.dependencies]` に `member = { path = "member" }` があり、ルートの `[dependencies]` に `member = { workspace = true }` があるとき、宣言されていないクレートの advisory は判定不能として数えられる。
- [ ] AC5（FR4）: FR1 / FR2 で不完全になったマニフェストでも、ルートで宣言されたクレートの advisory は finding になり、判定不能として数えられない。severity が判定済みで閾値未満の未宣言の advisory は数えられない。
- [ ] AC6（FR3）: path 依存を持たない、`members` 省略または空配列のワークスペースでは、宣言されていないクレートの advisory は推移的依存として扱われ、判定不能注記は出ない（既存の `test_ac4_a_workspace_without_members_is_complete` と `test_ac4_a_workspace_with_an_empty_members_list_is_complete` が変更なしで通る）。参照されない `[workspace.dependencies]` の path エントリだけのとき、および `[workspace]` の無いマニフェストに path 依存があるときも同じ。
- [ ] AC7（NFR1, NFR3, NFR4, NFR5）: `python3 -m unittest discover -s tests` が通る。既存のテストは変更しない。

## Technical Requirements

### Functional Requirements

- **FR1:** path 依存を持つワークスペースを不完全として扱う。Cargo.toml に `[workspace]` テーブルがあり、ルートの依存テーブル（トップレベルと各 `target.<cfg>` 配下の `dependencies` / `dev-dependencies` / `build-dependencies`）に `path` キーを持つエントリが 1 つ以上あるとき、直接依存の集合を不完全（complete=False）にする。`[workspace]` に `members` が無い場合と、`members` が空配列の場合の両方に適用する。インライン表の形（`member = { path = "member" }`）とサブテーブルの形（`[dependencies.member]` に `path = "member"`）の両方を対象にする。
- **FR2:** `workspace = true` で継承した path も対象にする。ルートの依存テーブルにある `workspace = true` のエントリで、同じマニフェストの `[workspace.dependencies]` にある同じキーのエントリが `path` キーを持つ表であるとき、そのエントリも path を持つエントリとして扱い、FR1 と同じく直接依存の集合を不完全にする。
- **FR3:** path 依存の無いワークスペースは完全のまま。`members` が無い、または空配列の `[workspace]` で、ルートの依存テーブルに path を持つエントリ（FR2 の継承分を含む）が無いときは、従来どおり直接依存の集合を完全として扱う。どのルートのエントリからも参照されない `[workspace.dependencies]` の path エントリだけでは不完全にしない。`[workspace]` テーブルの無いマニフェストは、path 依存があっても従来どおり完全として扱う。
- **FR4:** 不完全な集合での advisory の扱いは既存の規則のまま。FR1 / FR2 で不完全になった集合でも、ルートで宣言されて解決済みの名前（`package` によるリネーム後の名前を含む）に一致する advisory は直接依存の finding のままとする。一致しない advisory は既存の規則に従う。severity が判定済みで閾値未満のものは数えずに捨て、それ以外は finding にせず、推移的依存としても扱わず、cargo の判定不能件数に 1 件として数える。`skipped` と `skip_reason` は変えない。
- **FR5:** 回帰テスト。`tests/` 配下に、`members` の省略と空配列のそれぞれについて path 依存と組み合わせたケース、継承した path のケース、target 配下のケース、path 依存の無いワークスペースが完全のまま残るケースを確かめるテストを置く。

### Non-Functional Requirements

- **NFR1 - 依存:** 標準ライブラリだけを使う。tomllib は既存のガード付き import を通す。実行時とテスト時の依存を増やさない。
- **NFR2 - 読み取り範囲:** path 依存先やメンバーのマニフェストは読まない。新しいファイルを開く経路を足さない。
- **NFR3 - 例外:** マニフェストの内容によって例外が scan の外に出ない。`_cargo_direct_dependency_names` は引き続き例外を投げない。
- **NFR4 - 結果の文言:** summary と skip_reason には固定トークンと件数だけを載せる。マニフェストのパス、path の値、パッケージ名、advisory の本文は載せない。
- **NFR5 - 互換性:** pip / npm / go の挙動は変えない。既存の cargo のテストは変更なしで通る。
- **NFR6 - version:** プラグインの version は編集しない（`.claude/rules/core-plugin-version-bump.md`）。

## Assumptions

- A1: `workspace = true` で `[workspace.dependencies]` から path を継承するルートのエントリも、path を持つエントリとして扱い complete=False にする（FR2）。
- A2: path を持つエントリは、path の指す先がワークスペースのディレクトリ配下かどうか、`[workspace]` の `exclude` に含まれるかどうかを問わず、不完全の条件に数える。
- A3: `[patch]` / `[replace]` の path エントリは対象外とし、依存テーブル（target 配下を含む）だけを見る。
- A4: 変更範囲は `em-workflow/scripts/scan-dependencies.py`（`_cargo_workspace_view` / `_cargo_direct_dependency_names` とその docstring）とテストに限る。完了済みの feature `sca-directness-resolution` の SPEC.md（FR5）と THREAT-MODEL.md は編集しない。
- A5: メンバーや path 依存先のマニフェストは引き続き読まない（既存の `test_ac4_member_manifests_are_not_read` が固定している）。

## Implementation Approach

### Architecture

変更対象は `em-workflow/scripts/scan-dependencies.py` の `_cargo_workspace_view` / `_cargo_direct_dependency_names` とその docstring。読むのはルートの Cargo.toml だけ（NFR2 / A5）。

### Data Flow

```
ルートの Cargo.toml
  → _cargo_workspace_view / _cargo_direct_dependency_names
      [workspace] あり かつ ルートの依存テーブルに path を持つエントリ（FR2 の継承分を含む）あり → complete=False（FR1 / FR2）
      それ以外 → 従来どおり（FR3）
  → advisory の分類（FR4）
      ルートで宣言された名前に一致 → 直接依存の finding
      不一致・severity 判定済みで閾値未満 → 数えずに捨てる
      不一致・それ以外（complete=False のとき） → cargo の判定不能件数に 1 件として数える
```

### API Design

該当なし

### Database Schema

該当なし

### Dependencies

**Internal Dependencies:**
- `em-workflow/scripts/scan-dependencies.py` の既存の cargo 判定と判定不能注記（cargo_directness_undetermined）

**External Dependencies:**
- なし（標準ライブラリのみ。tomllib は既存のガード付き import を通す）

### File Structure

```
em-workflow/
└── scripts/
    └── scan-dependencies.py   # _cargo_workspace_view / _cargo_direct_dependency_names と docstring
tests/                         # FR5 の回帰テスト
```

## Declared Change Set

上記の feature 固有のパスは手書きの一覧ではなく、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

feature 固有のパスに加えて、ワークフローが生成する次の 2 つを既定で宣言する。

- `feature-docs/sca-cargo-implicit-workspace-members/**`
- `test-docs/sca-cargo-implicit-workspace-members/**`

`feature-docs/sca-cargo-implicit-workspace-members/**` は `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、design ステップの成果物を含む。これらはフェーズ文書と `references/phase-state.md` が生成・所有する。

`test-docs/sca-cargo-implicit-workspace-members/**` は `test-docs/sca-cargo-implicit-workspace-members/{T}.tests.yaml`（タスクごとのテスト記録）を含む。`implement-phase.md` が生成・所有する。

この 2 つの既定エントリは、明示的に外さない限り宣言に含まれる。

この宣言は上位集合の宣言で、verify 時に観測される実際の変更集合は宣言された集合に含まれていればよい（一致は求めない）。宣言したパスが実際には生成されなくても違反ではない。

## Test Scenarios

### Unit Tests

- [ ] TS1（AC1）: `[workspace]`（members なし）+ `member = { path = "member" }` のルートと、`member/Cargo.toml` に advisory のあるクレートの宣言を置き、cargo-audit の代わりのスタブがそのクレートの advisory を返す。finding 0 件、判定不能注記 1 件を確かめる。メンバーのマニフェストを読んでいないことも確かめる。
- [ ] TS2（AC2）: `members = []` と path 依存の組み合わせで TS1 と同じ結果になる。
- [ ] TS3（AC3）: path エントリを dev-dependencies / build-dependencies / `target.'cfg(unix)'.dependencies` / `[dependencies.member]` のサブテーブルに置いた各ケース（subTest）で判定不能が 1 件になる。
- [ ] TS4（AC4）: `[workspace.dependencies]` の path エントリを `workspace = true` で継承するケースで判定不能が 1 件になる。`package` によるリネームが付いた継承でも同じで、リネーム後の名前の advisory は finding になる。
- [ ] TS5（AC5）: path 依存のあるワークスペースで、ルートで宣言された serde の advisory が finding になり注記が出ない。未宣言で severity が判定済み・閾値未満の advisory は数えられない。
- [ ] TS6（AC6）: 参照されない `[workspace.dependencies]` の path エントリだけを持つワークスペース、および `[workspace]` の無い `[package]` マニフェストの path 依存で、未宣言の advisory が推移的依存として扱われ注記が出ない。

### Integration Tests

- [ ] TS7（AC7）: 全テストスイートの実行（`python3 -m unittest discover -s tests`）。

### E2E Tests

**Existing E2E tests**: なし
**Run command**: 未検出

該当なし

### Edge Cases

- [ ] `members` の省略と空配列の両方（TS1 / TS2）
- [ ] インライン表とサブテーブルの形、target 配下の依存テーブル（TS3）
- [ ] `workspace = true` による継承と `package` によるリネーム（TS4）
- [ ] 参照されない `[workspace.dependencies]` の path エントリだけのとき、`[workspace]` の無いマニフェストの path 依存（TS6）

### Performance Tests

該当なし

## Security Considerations

- **Input Validation:** マニフェストの内容によって例外が scan の外に出ない。`_cargo_direct_dependency_names` は引き続き例外を投げない（NFR3）。
- **Data Protection:** summary と skip_reason には固定トークンと件数だけを載せる。マニフェストのパス、path の値、パッケージ名、advisory の本文は載せない（NFR4）。
- **読み取り範囲:** path 依存先やメンバーのマニフェストは読まない。新しいファイルを開く経路を足さない（NFR2）。
- 認証、認可、XSS、SQL インジェクション、CSRF は該当なし。

## Error Handling

マニフェストの内容によって例外が scan の外に出ない（NFR3）。`skipped` と `skip_reason` は変えない（FR4）。

## Performance Optimization

該当なし

## Success Criteria

- [ ] FR1〜FR5 が実装され、テストされている
- [ ] TS1〜TS7 が通る
- [ ] 既存のテストが変更なしで通る（NFR5）
- [ ] プラグインの version を編集していない（NFR6）

## Open Questions

なし

## References

- `.claude/rules/core-plugin-version-bump.md`
- `feature-docs/sca-directness-resolution/SPEC.md`（編集しない）
