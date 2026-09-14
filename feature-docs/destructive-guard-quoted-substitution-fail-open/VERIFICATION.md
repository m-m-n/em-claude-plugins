# Verification Document: destructive-guard-quoted-substitution-fail-open

## Overview

**Feature**: destructive-guard-quoted-substitution-fail-open /
**SPEC.md**: `feature-docs/destructive-guard-quoted-substitution-fail-open/SPEC.md` /
**IMPLEMENTATION.md**: `feature-docs/destructive-guard-quoted-substitution-fail-open/IMPLEMENTATION.md`

統合後の検証手順。タスク単位の受け入れ条件は各タスク計画側にある。

## Build Verification

- Command: `python3 em-workflow/scripts/check-plugin-invariants.py .`
  （`workflow.yaml` project.components の `plugin_invariants.build_command`）
- Expected: 終了コード 0、失敗チェックの出力なし
- 他コンポーネント（`main` / `destructive_guard_hook`）に build_command は無い。

## Test Verification

- Command (hook suite): `python3 em-workflow/hooks/tests/run-destructive-guard.py`
  （`destructive_guard_hook.test_command`）
- Command (repository suite): `python3 -m unittest discover -s tests`
  （`main.test_command`）
- Expected: いずれも終了コード 0。hook suite は FAIL 行なしで `N/N passed` を出力する。
- Coverage target: 本フィーチャーは期待値表の追加であり行カバレッジの目標値を持たない。
  代わりに「SPEC.md の 8 形すべてにケースが存在すること」を到達度の指標とする。

### Test Scenarios from SPEC.md

| ID | Scenario | Expected Result | Test Type |
|----|----------|-----------------|-----------|
| TS1 | 二重引用符で囲んだ置換 + 親参照 + safe ルート着地 | deny（実測一致） | Unit |
| TS2 | 単一引用符で囲んだ形。実シェルでは置換が展開されないが、静的解析としては fail-closed 側に倒れることを固定する | deny（実測一致） | Unit |
| TS3 | バッククォート置換を二重引用符で囲んだ形（両スペル対称性のバッククォート側） | deny（実測一致） | Unit |
| TS4 | 着地先を `dist` に変えた引用符付き形 | deny（実測一致） | Unit |
| TS5 | 着地先を `node_modules` に変えた引用符付き形 | deny（実測一致） | Unit |
| TS6 | 着地先を `.cache` に変えた引用符付き形 | deny（実測一致） | Unit |
| TS7 | 引用符内で置換の前に実テキストが密着する形 | deny（実測一致） | Unit |
| TS8 | 引用符内で置換の後ろに実テキストが密着する形 | deny（実測一致） | Unit |
| TS9 | 対照として、変更前から存在する裸形ケース群が変更後も同じ期待判定・同じコマンド文字列で残っていること | 既存のまま deny（削除・改変ゼロ） | Unit |
| TS10 | スイート全体の実行 | 全件 ok、終了コード 0 | Integration |
| TS11 | 凍結ファイル（判定層・実行層）に差分が無いこと、および version が 2 ファイルで同一の新しい patch 値に上がっていること | 差分ゼロ / version 一致 | Integration |

TS1-TS8 の「実測一致」は、同じコマンド文字列を現行フックへ通した観測値と期待値が
一致することを指す。観測が `allow` になった形があれば、それは fail-open の再現であり、
検証失敗として扱う（IMPLEMENTATION.md D3）。

## Code Quality Verification

- Format: `workflow.yaml` の全コンポーネントで `format_command` は空。フォーマッタ実行は
  行わない。
- Static analysis: 静的解析コマンドの設定は無い。代わりに、ケース表と 2 つのマニフェスト
  が JSON としてパースできることを構文健全性の確認とする（TS10 / TS11 に内包）。

## SPEC.md Compliance

### Success Criteria

| ID | Criterion | How to Verify |
|----|-----------|---------------|
| AC1 | 攻撃シナリオ 5 形すべてに対応するケースが存在し、期待判定が fail-closed 側 | ケース表を読み、TS1-TS8 の各形に対応するエントリと判定値を確認 |
| AC2 | 引用符種別（二重 / 単一 / バッククォート + 二重）ごとに 1 件以上の deny ケース | ケース表の追加分を種別ごとに数える |
| AC3 | 着地先 `dist` / `node_modules` / `.cache` それぞれに引用符付き deny ケース | ケース表の追加分を着地先ごとに数える |
| AC4 | 置換の前密着・後ろ密着の双方に引用符付き deny ケース | ケース表の追加分を形ごとに確認 |
| AC5 | 追加ケースの期待判定が現行フックの実測判定と一致 | スイート実行（TS10）が全件 ok であること |
| AC6 | 変更前の全ケースが同じ期待判定・同じコマンド文字列で残存 | 変更前後のケース表を比較し、既存部分の一致と件数差が追加件数と等しいことを確認 |
| AC7 | `em-workflow/hooks/destructive-guard.py` に差分が無い | 統合差分の対象ファイル一覧を確認 |
| AC8 | hook suite が終了コード 0 で全件 ok | `python3 em-workflow/hooks/tests/run-destructive-guard.py` |
| AC9 | リポジトリスイートが変更前と同じく成功 | `python3 -m unittest discover -s tests` |
| AC10 | plugin.json と marketplace.json の em-workflow version が同一の新しい patch 値 | 両ファイルの version 値を突き合わせる |

### Functional Requirements Coverage

| Requirement | Tasks | Verification |
|-------------|-------|--------------|
| FR1 | task0001 | TS1-TS8（8 形のエントリ存在 + スイート ok） |
| FR2 | task0001 | TS1-TS8（期待値 = 実測。スイート ok が一致の証拠） |
| FR3 | task0001 | TS9（変更前後の既存部分の一致と件数差の確認） |
| FR4 | task0001, task0002 | TS11（判定層の差分ゼロ。統合差分の対象ファイル一覧で確認） |
| FR5 | task0001 | TS10（3 要素配列としてランナーがアンパックできること）+ 手動 M1（ラベル様式の目視） |
| FR6 | task0002 | TS11（2 ファイルの version 一致と patch 前進） |
| FR7 | task0001 | TS10（終了コード 0、FAIL 行なし） |
| NFR1 | task0001 | TS10（外部状態に依存せず、どの環境でも同じ判定になること。連続 2 回の実行で同一結果） |
| NFR2 | task0001 | TS10（実行時間がケース数に比例）+ TS11（実行層 `run-destructive-guard.py` の差分ゼロ） |
| NFR3 | task0001 | TS10（ケース表が JSON としてパースできなければスイートが 1 件も起動しない） |
| NFR4 | task0001 | TS10（標準ライブラリのみで実行が完了する。新規依存の導入なし） |

## E2E Testing

`workflow.yaml` の全コンポーネントで `e2e_test_command` は空。プロジェクトに E2E
フレームワークは無いため、このフィーチャーに自動 E2E は存在しない。

## Manual Testing (E2E Not Possible)

- [ ] M1: 追加したケースのラベルを目視し、既存のカテゴリ接頭辞様式に揃っていること、
      および「引用符付きでも裸形と同じ判定になること」を検証している旨が読み取れることを
      確認する（FR5）。
- [ ] M2: 追加位置が既存の裸形の双子エントリ群の直後にあり、対照関係が読んで分かる並びに
      なっていることを確認する。
- [ ] M3: モックとの目視照合は不要（design ステップは skipped、UI を持たない変更）。

## Performance / Security Verification (if applicable)

- Security: 本フィーチャーは destructive-guard の fail-closed 性の固定を目的とする。
  追加した 8 形の実測がすべて fail-closed 側（`deny`、または理由を明記した `ask`）で
  あることを確認する。1 件でも `allow` があれば fail-open の再現であり、検証は失敗と
  する。
- Security: 判定層に差分が無いこと（TS11）により、本変更が実行時の判定挙動を変えて
  いないことを確認する。
- Performance: スイート実行時間はケース数に比例（1 ケース = サブプロセス 1 本）。追加
  8 件ぶんの増加に収まっていることを実行時間の目視で確認する（NFR2）。

## Verification Summary

| Category | Items | Automated | E2E | Manual |
|----------|-------|-----------|-----|--------|
| Test scenarios (TS1-TS11) | 11 | 11 | 0 | 0 |
| Success criteria (AC1-AC10) | 10 | 6（AC5-AC10） | 0 | 4（AC1-AC4: ケース表の読み取り確認） |
| Manual items (M1-M3) | 3 | 0 | 0 | 3 |
| Build / invariants | 1 | 1 | 0 | 0 |
