---
title: "codex-hook-tty-reaper-anchor-identity"
created_date: 2026-10-27
status: draft
---

# codex-hook-tty-reaper-anchor-identity - 要件定義書

## 1. 概要

### 1.1 背景
`codex-hook-tty-reaper.py` では、祖先チェーンを確認してからスナップショットを取るまでの間に、起点の PID が別プロセスに再利用されることがある。

### 1.2 目的
祖先チェーンを確認してからスナップショットを取るまでの間に起点の PID が別プロセスに再利用されても、起点の子孫でないプロセスに信号が届かないようにする。

### 1.3 スコープ
- 対象: `em-workflow/scripts/codex-hook-tty-reaper.py` と `em-review/scripts/codex-hook-tty-reaper.py`（バイト単位で同一の 2 つのコピー）
- 対象: `tests/test_codex_hook_tty_reaper.py`（回帰テストの追加）
- 対象外: `plugin.json` / `marketplace.json` の version、`.claude/rules/hook-tests.md`
- デザインステップ: 省略（UI やビジュアルの要素がない）

## 2. ビジネス要件

### 2.1 ビジネス目標
- 起点の PID が祖先チェーンの読み取りとスナップショットの間で別プロセスに再利用されても、起点の子孫でないプロセスに信号が届かない。

### 2.2 対象ユーザー
該当なし

### 2.3 期待される効果
- 起点の子孫でないプロセスに SIGTERM / SIGKILL が送られない。

## 3. ユースケース

該当なし

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 | 説明 | 優先度 |
|----|--------|------|--------|
| FR1 | 起点の同一性の照合 | 祖先チェーン読み取り時の起点の開始時刻と、スナップショット上の起点の開始時刻を照合する | 高 |
| FR2 | 2 つのコピーの同一性 | 2 つのコピーを同じ変更で直し、バイト単位で同一に保つ | 高 |
| FR3 | docstring の更新 | モジュール docstring の Flow に FR1 の照合を書き足す | 高 |
| FR4 | 回帰テスト | 起点の PID が再割り当てされた状態で信号が送られないことを確かめるテストを追加する | 高 |

### 4.2 機能詳細

#### FR1: 起点の同一性の照合

**説明**: 祖先チェーンを読んだときに記録した起点の開始時刻と、スナップショット上の起点の開始時刻を照合する。一致しなければ何も止めない（pidfd を開かず、信号を送らない）。起点の開始時刻は、`_ancestor_chain` が祖先チェーンを読むときに読んだ値を使う。

**ビジネスルール**:
- 開始時刻が一致しないときは、pidfd を開かず、SIGTERM も SIGKILL も送らない。
- 開始時刻の差が 1 ティックだけでも一致しないものとして扱う。
- 親（ppid）だけが付け替わった起点は、開始時刻が同じなら同じプロセスとして扱う。
- 起点とフックの間のプロセスがフック実行中に終了しても、起点の開始時刻が一致すれば止める処理を続ける。

**エラーケース**:
| エラー | 条件 | 対応 |
|--------|------|------|
| 起点の不一致 | スナップショット上の起点の開始時刻が、祖先チェーン読み取り時の値と違う | 何も止めない（pidfd を開かず、信号を送らない） |

#### FR2: 2 つのコピーの同一性

**説明**: `em-workflow/scripts/codex-hook-tty-reaper.py` と `em-review/scripts/codex-hook-tty-reaper.py` を同じ変更で直し、バイト単位で同一に保つ。

#### FR3: docstring の更新

**説明**: モジュール docstring の Flow に FR1 の照合を書き足す。10 ステップの構成と、`TestModuleDocstring` が固定している語句（ステップ 4 / 6 の語句）は保つ。

#### FR4: 回帰テスト

**説明**: 起点の PID が祖先チェーンの読み取りとスナップショットの間で別プロセスに再割り当てされ、再割り当て先の子孫に標準入力が `/dev/pts/*` のプロセスがある状態を作り、信号が送られないことを確かめるテストを `tests/test_codex_hook_tty_reaper.py` に追加する。

## 5. 非機能要件

### 5.1 パフォーマンス要件
該当なし

### 5.2 セキュリティ要件
- NFR4: PID を指定した信号送信（`os.kill`）を追加しない。

### 5.3 可用性要件
該当なし

### 5.4 保守性要件
- NFR1: 標準ライブラリだけを使う。
- NFR2: どの経路でも終了コードは 0 で、標準出力・標準エラーには何も書かない。
- NFR3: 既存テストはすべて変えずに通す。

### 5.5 互換性要件
- NFR3 に同じ。

## 6. UI/UX要件

該当なし

## 7. データ要件

該当なし

## 8. 外部連携

該当なし

## 9. 制約条件

### 9.1 技術的制約
- 標準ライブラリだけを使う（NFR1）。
- PID を指定した信号送信（`os.kill`）を追加しない（NFR4）。
- 2 つのコピーはバイト単位で同一に保つ（FR2）。
- Flow の 10 ステップ構成と、`TestModuleDocstring` が固定しているステップ 4 / 6 の語句は残す。

### 9.2 ビジネス上の制約
- `plugin.json` / `marketplace.json` の version は変えない。
- `.claude/rules/hook-tests.md` は変えない。

### 9.3 スケジュール制約
該当なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/codex-hook-tty-reaper-anchor-identity/**`
- `test-docs/codex-hook-tty-reaper-anchor-identity/**`

`feature-docs/codex-hook-tty-reaper-anchor-identity/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/codex-hook-tty-reaper-anchor-identity/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/codex-hook-tty-reaper-anchor-identity/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/{feature}/` ディレクトリを生成しないが、宣言された `test-docs/{feature}/**` は依然として正しい。

## 10. 想定される課題とリスク

該当なし

## 11. 成功基準

### 11.1 受け入れ基準
- [ ] AC1（FR1, FR4）: 祖先チェーン読み取り時の起点と、スナップショット上の同じ PID のプロセスで開始時刻が違い、再割り当て先の子孫に標準入力が `/dev/pts/*` のプロセスがある。このとき SIGTERM も SIGKILL も送られず、pidfd も開かれない。このテストは修正前のコードでは失敗する。
- [ ] AC2（FR1, NFR3）: 起点がスナップショットまで同じプロセス（開始時刻が同じ）なら、これまでどおり対象が止まる。親（ppid）だけが付け替わった起点も同じプロセスとして扱う。
- [ ] AC3（FR2）: 2 つのコピーがバイト単位で同一（`TestCopies` が通る）。
- [ ] AC4（FR3）: docstring の Flow に FR1 の照合が書かれていて、ステップ数は 10 のまま（`TestModuleDocstring` が通る）。
- [ ] AC5（NFR1, NFR2, NFR3, NFR4）: `python3 -m unittest tests.test_codex_hook_tty_reaper` と `python3 -m unittest discover -s tests` が通る。

### 11.2 KPI
該当なし

## 12. テストシナリオ

### 12.1 テスト観点
- [ ] 異常系 TS1（AC1）: インプロセスで実行する。`_snapshot` を差し替え（または `on_stat` を使い）、祖先チェーンを読んだ後・スナップショットの前に、起点の PID の項目を開始時刻が後のプロセス X に置き換え、X の子孫に標準入力が `/dev/pts/*` のプロセスを置く。`world.sent` と `world.open_calls` が空であることを確かめる。
- [ ] 境界値 TS2（AC1）: TS1 と同じ配置で、開始時刻の差が 1 ティックだけのとき（起点より 1 ティック後）も何も止めない。
- [ ] 正常系 TS3（AC2）: 祖先チェーンを読んだ後・スナップショットの前に、起点の ppid だけを変える（開始時刻は同じ）。起点の子孫で標準入力が `/dev/pts/*` の対象が止まる。
- [ ] 正常系 TS4（AC2, AC3, AC4, AC5）: 既存の `TestTargetSelection` / `TestAncestorChainRule` / `TestLinkRule` / `TestCopies` / `TestModuleDocstring` などを含め、テストスイート全体が通る。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| 起点 | 祖先チェーンを読む対象となるプロセス。止める対象は起点の子孫に限る |
| 開始時刻 | プロセスの開始時刻。起点の同一性の照合に使う |

## 14. 確認事項

### 14.1 確認済み事項

- [x] 照合方法: 起点の開始時刻を照合する（`requirement.anchor-identity.approach` の回答: `anchor_start_time`）。
- [x] 中間プロセスの終了: 起点とフックの間のプロセスがフック実行中に終了しても、起点の開始時刻が一致すれば止める処理を続ける。
- [x] 既存テスト: すべて変えずに通す。Flow の 10 ステップ構成と、`TestModuleDocstring` が固定しているステップ 4 / 6 の語句は残す。
- [x] 回帰テストの置き場所: 既存の `tests/test_codex_hook_tty_reaper.py` に追加する。
- [x] version: `plugin.json` / `marketplace.json` の version は変えない。
- [x] `.claude/rules/hook-tests.md`: 変えない。

### 14.2 未確認・保留事項
なし

## 15. 参考資料

- `em-workflow/scripts/codex-hook-tty-reaper.py`
- `em-review/scripts/codex-hook-tty-reaper.py`
- `tests/test_codex_hook_tty_reaper.py`
