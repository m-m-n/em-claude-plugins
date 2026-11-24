# Feature: env-route-partial-overrun-check

## Overview

destructive-guard の env 経路で、extglob の 2 つの読み方のうち片方だけが overrun を立てたとき、上限内に収まった読み方が復号した notion ペアの本文と command を再走査のキューに積み、破壊的なコマンドを deny にする。overrun による scan-budget の ask は従来どおり保持する。要件は `REQUIREMENTS.md` を参照する。

## Objectives

- destructive-guard の env 経路で、extglob の 2 つの読み方のうち片方だけが上限を超えた（overrun）とき、上限内に収まった読み方が復号した notion ペアの本文と command も検査に回し、破壊的なコマンドを deny にする。
- overrun による scan-budget の ask は従来どおり残す。

## User Stories

このフィーチャーはフック内部の判定ロジックの修正で、ユーザーストーリーは定めない。受け入れ基準は次のとおり。

**Acceptance Criteria:**
- [ ] AC-1: env 経路のペイロードで、片方の読み方だけが overrun を立て、もう片方の読み方が復号した notion ペアの command が破壊的（例: `git branch -D example`）なとき、対話実行（`CLAUDE_BATCH` なし）の判定は deny で、理由 ID はその破壊的コマンドのもの（例: `git-branch-force-delete`）になり、`scan-budget-exceeded` にはならない。（FR1、FR3）
- [ ] AC-2: AC-1 と同じ形で、上限内の読み方の command が破壊的でないとき、判定は従来どおり ask（`scan-budget-exceeded`）になる。（FR2）
- [ ] AC-3: overrun が 1 番目の読み方で立った場合と 2 番目の読み方で立った場合、入ったときの extglob 設定が off の場合と on の場合のすべての組み合わせで、上限内の読み方の本文と command が結果に入り、overrun を立てた読み方の項目は入らない。overrun は立ったまま報告される。（FR1、FR4、FR5）
- [ ] AC-4: 両方の読み方が overrun を立てた場合と、読み方が 1 つだけで overrun を立てた場合は、何も積まれず ask になる（従来どおり）。（FR7）
- [ ] AC-5: 上限内の読み方の charge を足すと予算を超えるとき、何も積まれず scan-budget の ask になる。（FR6）
- [ ] AC-6: env 経路以外の overrun の挙動と unrestorable の扱いは変わらない。既存の `destructive-guard-cases.json` のケースと `tests/test_destructive_guard_env_route.py` のテストがすべて通る（結果の形を変えたことで必要になる既存テストの期待値の更新は除く）。（FR7、NFR2、NFR3、NFR5）

## Technical Requirements

### Functional Requirements
- **FR1:** 上限内の読み方の項目を検査に回す。env 経路（`_args_json_env_payload_values()` / `_args_json_env_body_readings()` / `_args_json_env_combine()`）で 2 つの読み方がそれぞれ結果を返し、一方が overrun を立て、もう一方が立てなかったとき、立てなかった読み方が復号した候補本文と command 文字列を、通常の `--args-json` の値と同じように再走査のキューに積む（`_queue_args_json_chunks()` の手順 3 と同じ扱い。キューの各項目はペイロードの語に結び付ける）。
- **FR2:** overrun の ask は残す。FR1 の場合も、overrun による scan-budget の ask（`SCAN_BUDGET_ASK`、`scan-budget-exceeded`）を従来どおり保持し、その実行の残りでは `--args-json` の手順を止める（`_DeferredAsks.stop_args_json()`）。
- **FR3:** deny を ask より優先する。FR1 で積んだ項目の再走査で deny が出たら、保持された ask より deny を判定にする。既存の「deny はどの保留中の ask にも勝つ」仕組み（`_DeferredAsks.settle()` と `main()` の扱い）で実現する。
- **FR4:** overrun を立てた読み方の項目は積まない。overrun を立てた読み方が見つけた本文と command は、上限内に収まった値も含めて従来どおり検査に回さない（D3 と同じく、overrun を立てたものからは何も積まない）。
- **FR5:** 重複排除と charge は上限内の読み方だけで行う。積む項目と charge は、上限内に収まった読み方だけの和集合として、既存の規則（各文字列 1 回、同じ項目は 1 回だけ charge、1 つの読み方の中の重複は残す）で求める。overrun を立てた読み方の項目は、重複排除と charge の比較対象にしない。overrun を立てた読み方が先に読まれても、上限内の読み方の項目が欠けることはない。
- **FR6:** 予算の判定。FR5 の charge を足すと scan の予算を超えるときは、従来どおり何も積まずに scan-budget の ask を保持する。
- **FR7:** 変えない場合。次の場合の挙動は変えない。読み方が 1 つだけで overrun を立てた場合と、2 つの読み方の両方が overrun を立てた場合（何も積まずに ask）。どちらの読み方も overrun を立てない場合。unrestorable の扱い（`args-json-unrestorable` の ask を保持し、積むかどうかには影響しない）。env 経路以外（通常の mcp-bridge run の文、静的に復元したコマンド語の lifted notion の文）で overrun が立った場合（文の値を何も積まずに ask）。

### Non-Functional Requirements
- **NFR1 - テスト:** テストは標準ライブラリだけで書く。`em-workflow/hooks/tests/destructive-guard-cases.json` に、攻撃シナリオを全体の判定で確かめるケースを足す。理由 ID（rule）を固定し、`CLAUDE_BATCH` は立てない（batch では ask が deny に格下げされ、区別がつかなくなるため）。`tests/test_destructive_guard_env_route.py` に、env 経路の結果を読み方ごとに確かめる単体テストを足す。
- **NFR2 - 既存ケースの保持:** 既存の deny / ask のケースは消さない（`.claude/rules/hook-tests.md`）。
- **NFR3 - テストの実行:** 変更後、`python3 em-workflow/hooks/tests/run-destructive-guard.py` と `python3 -m unittest tests.test_destructive_guard_env_route` がどちらも通る。
- **NFR4 - version:** プラグインの version は触らない（`.claude/rules/core-plugin-version-bump.md`、main への push で Actions が patch を上げる）。
- **NFR5 - 既存の性質の保持:** env 経路が `_lex_unreadable_met`、`_lex_extglob_met`、`_lex_extglob` の 3 つの状態を、入ったときの値に戻す性質（env-route-lex-flag-isolation FR1、FR2）と、extglob の単位を記録しない性質（NFR2）は保つ。

## Implementation Approach

### Architecture

変更箇所は `em-workflow/hooks/destructive-guard.py` の次の 2 つ。

- `_args_json_env_combine()`（`for reading in readings:` のループ）: 現在は 2 つの読み方の overrun を OR でまとめている。
- `_queue_args_json_chunks()`: overrun が立つと値を何も積まずに戻る分岐を持つ。

### Data Flow

2 つの読み方がそれぞれ結果を返した場合の流れ（FR1〜FR7）。

```
2 つの読み方の結果
  ├─ どちらも overrun なし → 従来どおり（FR7）
  ├─ 両方が overrun → 何も積まずに scan-budget の ask を保持（FR7）
  └─ 片方だけが overrun
       ├─ overrun を立てた読み方の項目は捨てる（FR4）
       ├─ 上限内の読み方の項目だけで重複排除と charge を求める（FR5）
       ├─ charge を足すと予算を超える → 何も積まずに scan-budget の ask を保持（FR6）
       └─ 予算内 → 上限内の読み方の本文と command を再走査のキューに積む（FR1）
                   scan-budget の ask を保持し、残りの --args-json の手順を止める（FR2）
                   再走査で deny → deny が判定になる（FR3）
                   再走査で deny なし → scan-budget の ask が判定になる（FR2）
```

### API Design

該当なし。

### Database Schema

該当なし。

### Dependencies

**Internal Dependencies:**
- env-route-lex-flag-isolation: FR1、FR2、NFR2 の性質を保つ（NFR5）。
- `_DeferredAsks`: `stop_args_json()` と `settle()` を既存のまま使う（FR2、FR3）。

**External Dependencies:**
- なし（標準ライブラリのみ。NFR1）。

### File Structure

```
em-workflow/hooks/
├── destructive-guard.py                 # _args_json_env_combine() / _queue_args_json_chunks()
└── tests/
    └── destructive-guard-cases.json     # 全体判定のケースを追加（TS-1, TS-2）
tests/
└── test_destructive_guard_env_route.py  # 単体テストを追加（TS-3, TS-5）。TestBothReadings が影響を受ける
```

## Declared Change Set

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

固有のパスに加えて、次の 2 つのワークフロー生成物をデフォルトで宣言する。

- `feature-docs/env-route-partial-overrun-check/**`
- `test-docs/env-route-partial-overrun-check/**`

`feature-docs/env-route-partial-overrun-check/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/env-route-partial-overrun-check/**` に含まれるもの: `test-docs/env-route-partial-overrun-check/{T}.tests.yaml`（タスクごとのテスト記録）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

この 2 つのデフォルトのメンバーは、SPEC 作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載が無いことで除外とはみなさない。

この宣言はスーパーセット（superset）の主張であり、verify 時に観測される実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。一致する必要はない。implement タスクを 1 つも生成しないフィーチャーは `test-docs/env-route-partial-overrun-check/` ディレクトリを生成しないが、宣言された `test-docs/env-route-partial-overrun-check/**` は依然として正しい。宣言されたパスが生成されないことは違反にならない。

## Test Scenarios

### Integration Tests
- [ ] TS-1: 全体判定（cases.json、deny、rule 固定、batch なし）。ペイロードは、extglob off では構文エラーとして捨てられる行（`a=(@(x)); ...`）の上に、`MAX_ARGS_JSON_DEPTH`（100）を超える入れ子の `--args-json` を持つ notion 呼び出しを置き、別の行に `{"command":"git branch -D example"}` の notion 呼び出しを置く。lift には `BASH_FUNC_mcp-bridge` の代入を使う（既存の TS-6 ケースと同じ形）。extglob on の読み方だけが overrun を立て、off の読み方が command を復号する。この形で実際に片方だけが overrun を立てることは、実装時にフックで確かめる。 - 判定は deny で、理由 ID は破壊的コマンドのもの（AC-1）
- [ ] TS-2: 全体判定（cases.json、ask、rule `scan-budget-exceeded`）。TS-1 と同じ形で、command を無害なもの（例: `echo hi`）にする。 - 判定は ask（`scan-budget-exceeded`）（AC-2）

### Unit Tests
- [ ] TS-3: 単体テスト。既存の `fake_read_values` の方法で、読み方ごとの結果（overrun あり / なし）を差し替える。overrun を立てる読み方（1 番目 / 2 番目）と入ったときの extglob 設定の全組み合わせで、結果に入る本文、command、charge と、overrun が立ったまま報告されることを確かめる。overrun を立てた読み方と上限内の読み方が同じ文字列を返す場合も含める。 - 上限内の読み方の項目だけが結果に入り、overrun は立ったまま報告される（AC-3）
- [ ] TS-4: 単体テストまたは全体判定。両方の読み方が overrun を立てる場合と、読み方が 1 つだけで overrun を立てる場合。 - 何も積まれない（AC-4）
- [ ] TS-5: 単体テスト。上限内の読み方の charge を予算より大きくする。 - 何も積まれず scan-budget の ask が保持される（AC-5）

### Regression Tests
- [ ] TS-6: 回帰。`run-destructive-guard.py` と `tests.test_destructive_guard_env_route` を全件通す。 - すべて通る（AC-6）

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

## Security Considerations

- **Input Validation:** env 経路で片方の読み方だけが overrun を立てたとき、上限内の読み方が復号した本文と command を再走査し、破壊的なコマンドを deny にする（FR1、FR3）。
- 認証・認可・XSS・SQL インジェクション・CSRF: 該当なし。

## Error Handling

該当なし。判定の理由 ID は既存のもの（`scan-budget-exceeded`、`args-json-unrestorable`、破壊的コマンドごとの理由 ID）を使う。

## Performance Optimization

該当なし。

## Success Criteria

- [ ] FR1〜FR7 が実装され、テストされている
- [ ] TS-1〜TS-6 がすべて通る
- [ ] NFR1〜NFR5 を満たす

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

なし。

## References

- 要件定義書: `feature-docs/env-route-partial-overrun-check/REQUIREMENTS.md`
- フックのテストの規則: `.claude/rules/hook-tests.md`
- プラグインの version の扱い: `.claude/rules/core-plugin-version-bump.md`
- env-route-lex-flag-isolation: FR1、FR2、NFR2
