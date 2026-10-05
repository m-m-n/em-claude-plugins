---
title: "codex-repo-hook-trust"
created_date: 2026-10-05
status: draft
---

# codex-repo-hook-trust - 要件定義書

## 1. 概要

### 1.1 背景
feature-docs/codex-interactive-guard-hook/THREAT-MODEL.md の TB-3 に、レビュー対象のリポジトリが作業ディレクトリ側の Codex 設定（.codex/ 等）に持ち込んだ hook が実行されるかどうかという未解決事項が残っている。

### 1.2 目的
- レビュー対象のリポジトリが作業ディレクトリ側の Codex 設定（.codex/ 等）に持ち込んだ hook が、em-workflow / em-review の Codex 起動で信頼確認なしに実行されない状態にする。
- THREAT-MODEL.md TB-3 の未解決事項を、Codex 0.160.0 で実挙動を確かめた記録と一緒に閉じる。

### 1.3 スコープ
- 対象: em-workflow/scripts/run_codex_exec.sh、em-review/scripts/run_codex_exec.sh、tests/、feature-docs/codex-repo-hook-trust/、feature-docs/codex-interactive-guard-hook/THREAT-MODEL.md
- 対象外: vertex-review プラグイン（vertex-reviewer）、feature-docs/codex-interactive-guard-hook/SPEC.md、Notion タスクの暫定緩和策欄の更新（14.2 の A4〜A6）

## 2. ビジネス要件

### 2.1 ビジネス目標
- レビュー対象のリポジトリが作業ディレクトリ側の Codex 設定（.codex/ 等）に持ち込んだ hook が、em-workflow / em-review の Codex 起動で信頼確認なしに実行されない状態にする。
- THREAT-MODEL.md TB-3 の未解決事項を、Codex 0.160.0 で実挙動を確かめた記録と一緒に閉じる。

### 2.2 対象ユーザー
該当なし

### 2.3 期待される効果
- 2.1 のビジネス目標を参照

## 3. ユースケース

該当なし

## 4. 機能要件

### 4.1 機能一覧
| ID | 機能名 | 説明 | 状態 |
|----|--------|------|------|
| FR1 | Codex 0.160.0 での実挙動の確認 | 各起動経路で作業ディレクトリ側の hook 定義が実行されるかを確かめる | confirmed |
| FR2 | 確認結果の記録 | FR1 の結果を feature-docs/codex-repo-hook-trust/ 配下に記録する | confirmed |
| FR3 | 実行される経路の起動を変える | リポジトリ側の hook が実行された経路で、作業ディレクトリ側の設定層を読まない起動に変える | confirmed |
| FR4 | 実行されない場合の TB-3 への記録 | どの経路でも実行されなかった場合、TB-3 に記録して未解決事項を閉じる | confirmed |
| FR5 | リポジトリ側 hook の非実行を確かめるテスト | FR3 を適用した場合、非実行を確かめるテストを tests/ に足す | confirmed |
| FR6 | ラッパーのコメントの更新 | 両ラッパーの Interactive-guard hook 節のコメントを FR1・FR3 に合わせる | confirmed |

### 4.2 機能詳細

#### FR1: Codex 0.160.0 での実挙動の確認

**説明**: Codex 0.160.0 で次の起動ごとに、作業ディレクトリ（-C で渡すディレクトリ）側の Codex 設定にある hook 定義が実行されるかを確かめる。

- (a) em-workflow/scripts/run_codex_exec.sh の既定経路（--ignore-user-config あり）
- (b) 同じラッパーの --litellm MODEL 経路（--ignore-user-config なし、-p litellm）
- (c) em-review/scripts/run_codex_exec.sh（既定経路のみ）

**ビジネスルール**:
- --litellm 経路では、ユーザー設定でそのプロジェクトが信頼済みの場合と未信頼の場合の両方を確かめる。
- 確認はラッパーが組み立てる argv と同じフラグ構成（--dangerously-bypass-hook-trust、--ignore-rules、ラッパー自身の -c hooks.PreToolUse を含む）で行う。
- 確認対象の hook 定義の範囲は 14.2 の A2 による。

#### FR2: 確認結果の記録

**説明**: FR1 の結果を、起動経路ごと・hook 定義の置き場所ごとに、実行された／されなかったと、使った Codex のバージョン、固定した設定・コマンドとあわせて記録する。

**出力**:
- 確認結果の記録: feature-docs/codex-repo-hook-trust/ 配下に置く。

#### FR3: 実行される経路の起動を変える

**説明**: FR1 でリポジトリ側の hook が実行された起動経路について、ラッパーの起動を作業ディレクトリ側の設定層を読まない形に変える。

**ビジネスルール**:
- 変更は em-workflow と em-review の両方の run_codex_exec.sh に、該当する経路で入れる。
- 次は維持する。
    - ラッパー自身の interactive-guard hook（-c hooks.PreToolUse）の登録
    - --ignore-rules
    - 既定経路の --ignore-user-config
    - --litellm 経路の -p litellm -m MODEL
- 起動変更の手段は 14.2 の A1 による。

#### FR4: 実行されない場合の TB-3 への記録

**説明**: FR1 でどの起動経路でもリポジトリ側の hook が実行されなかった場合は、feature-docs/codex-interactive-guard-hook/THREAT-MODEL.md の TB-3 にその確認結果を記録し、Rationale にある「Configuration layers the wrapper does not author」の未解決事項を閉じる。

#### FR5: リポジトリ側 hook の非実行を確かめるテスト

**説明**: FR3 を適用した場合は、リポジトリ側の hook が実行されないことを確かめるテストを tests/ に足す。

**ビジネスルール**:
- 対象は FR3 で変えたすべての起動経路で、readonly と readwrite の両モードとする。
- テストの構成は 14.2 の A3 による。

#### FR6: ラッパーのコメントの更新

**説明**: 両ラッパーの Interactive-guard hook 節のコメント（em-workflow 151–156 行、em-review 124–129 行付近）を、FR1 の結果と FR3 の変更（適用した場合）に合わせる。

## 5. 非機能要件

### 5.1 パフォーマンス要件
該当なし

### 5.2 セキュリティ要件
- NFR1: FR1 の確認と FR5 のテストでは、利用者の実際の ~/.codex（CODEX_HOME）を読み書きしない。信頼済みの記録、認証情報、litellm プロファイルは一時ディレクトリ内に置く。
- NFR5: 記録とテストの出力に LITELLM_API_KEY や認証情報の値を含めない。

### 5.3 可用性要件
該当なし

### 5.4 保守性要件
- NFR2: テストコードは Python 標準ライブラリだけを使う（test/README.md）。
- NFR4: 両ラッパーへの変更は同じ変更の中で入れる。
- NFR6: SPEC・計画・受け入れ条件にプラグインの version の変更を書かない（.claude/rules/core-plugin-version-bump.md）。

### 5.5 互換性要件
- NFR3: 既存のラッパー契約を維持する。
    - 1 回の実行で codex exec を 1 回だけ起動する
    - usage 文言と受け付けるフラグは変えない
    - プロンプトは argv の最後
    - em-workflow ラッパーに 2>&1 を足さない
    - em-review ラッパーの 2>&1 は 1 箇所のまま
    - em-review ラッパーは --litellm を受け付けない

## 6. UI/UX要件

該当なし（UI を持たない変更）

## 7. データ要件

該当なし

## 8. 外部連携

### 8.1 連携システム
| システム名 | 連携方法 | データ |
|------------|----------|--------|
| Codex 0.160.0 | ラッパー（run_codex_exec.sh）からの codex exec 起動 | 作業ディレクトリ側の Codex 設定、hook 定義 |

### 8.2 API仕様要件
該当なし

## 9. 制約条件

### 9.1 技術的制約
- 5 章の NFR1〜NFR6 を参照

### 9.2 ビジネス上の制約
該当なし

### 9.3 スケジュール制約
該当なし

### 9.4 宣言された変更集合

このフィーチャー固有のパスは手動で列挙せず、create-plan で `workflow.yaml` の各タスクの `files` から導出する（`references/phases/create-plan-phase.md`）。

**デフォルトメンバー**（SPEC作成者が明示的に除外しない限り、常に宣言に含まれる）:
- `feature-docs/codex-repo-hook-trust/**`
- `test-docs/codex-repo-hook-trust/**`

`feature-docs/codex-repo-hook-trust/**` に含まれるもの: `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、およびデザインステップが生成するデザイン成果物。生成主体は各フェーズドキュメントおよび `references/phase-state.md` を参照（引用のみ、ルールは再掲しない）。

`test-docs/codex-repo-hook-trust/**` に含まれるもの: `{T}.tests.yaml`（パス形式: `test-docs/codex-repo-hook-trust/{T}.tests.yaml`）。生成主体は `implement-phase.md` を参照（引用のみ、ルールは再掲しない）。

**意味論**:
- デフォルトのメンバーは、SPEC作成者が明示的に除外しない限り宣言に含まれる。除外は意図的な絞り込みであり、記載漏れによる省略ではない。
- この宣言はスーパーセット（superset）の主張であり、実際の変更集合は宣言に含まれる（CONTAINED IN）必要がある。実際には生成されないパスが宣言されていても違反にはならない。implementタスクを1つも生成しないフィーチャーは `test-docs/codex-repo-hook-trust/` ディレクトリを生成しないが、宣言された `test-docs/codex-repo-hook-trust/**` は依然として正しい。

## 10. 想定される課題とリスク

### 10.1 技術的課題
該当なし

### 10.2 ビジネスリスク
該当なし

## 11. 成功基準

### 11.1 受け入れ基準
- [ ] AC1: FR2 の記録があり、em-workflow 既定経路、em-workflow --litellm 経路（信頼済み・未信頼）、em-review の各起動について、作業ディレクトリ側の hook 定義が Codex 0.160.0 で実行されたかどうかが書かれている。
- [ ] AC2: FR1 で実行された経路がある場合、その経路のラッパー起動ではリポジトリ側の hook が実行されず、FR5 のテストが通る。ラッパー自身の interactive-guard hook の登録は残っている。
- [ ] AC3: FR1 で実行された経路が無い場合、feature-docs/codex-interactive-guard-hook/THREAT-MODEL.md の TB-3 にその確認結果が記録され、未解決事項として残っていない。
- [ ] AC4: `python3 -m unittest discover -s tests` が通る。
- [ ] AC5: 両ラッパーのコメントが FR1 の結果と実際の起動の形に一致している。

### 11.2 KPI
該当なし

## 12. テストシナリオ

### 12.1 テスト観点
- [ ] TS1（FR3 適用時、stub）: stub の codex を PATH の先頭に置き HOME と CODEX_HOME を一時ディレクトリにした状態で、FR3 で変えた各経路・両モードの argv（と環境）に、作業ディレクトリ側の設定層を読まないための指定が入っていることを確かめる。指定を外した偽の argv で失敗することも確かめる（非空虚性）。
- [ ] TS2（FR3 適用時、実 Codex）: 一時リポジトリの作業ディレクトリ側設定に、実行されると目印ファイルを書く hook を置き、ラッパー経由で Codex を起動して目印ファイルが作られないことを確かめる。codex が無い、またはバージョンが 0.160.0 でない環境ではスキップする。
- [ ] TS3（回帰）: tests/test_codex_hook_wrapper_args.py、tests/test_consultation_harness_chain.py、tests/test_codex_wrapper_single_invocation.py、tests/test_codex_reviewer_temp_file_isolation.py が通る。FR3 で固定値が変わる箇所は、変更後の起動に合わせて更新する。

## 13. 用語定義

| 用語 | 定義 |
|------|------|
| 作業ディレクトリ | ラッパーが Codex に -C で渡すディレクトリ |
| リポジトリ側の hook | 作業ディレクトリ側の Codex 設定（.codex/ 等）にある hook 定義 |
| 既定経路 | --litellm を付けないラッパー起動（--ignore-user-config あり） |
| --litellm 経路 | em-workflow ラッパーの --litellm MODEL 起動（--ignore-user-config なし、-p litellm -m MODEL） |

## 14. 確認事項

### 14.1 確認済み事項
なし

### 14.2 未確認・保留事項
- [ ] A1（影響度: 高）: FR3 の起動変更の手段（Codex のフラグ、-c による上書き、起動専用の設定ディレクトリなど）は FR1 の確認結果を見て実装時に決める。どの手段でも、リポジトリ側の hook が実行されないこととラッパー自身の interactive-guard hook が動くことの両方を満たす。両方を満たせない経路では、リポジトリ側の hook が実行されないことを優先し、その経路で guard が動かなくなることを THREAT-MODEL.md TB-3 に記録する。
- [ ] A2（影響度: 中）: FR1 で確かめる「作業ディレクトリ側の hook 定義」は、Codex 0.160.0 が作業ディレクトリ側から読む hook の置き場所すべて（例: .codex/config.toml の hooks 表、別ファイルの hook 定義があればそれも）と、PreToolUse 以外を含むすべての hook イベントを対象にする。ラッパーの -c hooks.PreToolUse が同じキーのリポジトリ側定義を上書きするかどうかも記録する。
- [ ] A3（影響度: 中）: FR5 のテストは TS1（stub による argv の固定。常に実行）と TS2（実 Codex。0.160.0 が無ければスキップ）の 2 つで構成する。
- [ ] A4（影響度: 低）: Codex 側に修正版は無い。リポジトリ内では FR3 / FR4 を対応とし、Notion タスクの暫定緩和策欄の更新はこの機能の成果物に含めない。
- [ ] A5（影響度: 低）: FR4 の記録先は feature-docs/codex-interactive-guard-hook/THREAT-MODEL.md とする。feature-docs/codex-interactive-guard-hook/SPEC.md は過去の機能の記録として変えない。
- [ ] A6（影響度: 低）: em-workflow の --litellm 経路は question-resolution.md の相談手順と review 系の呼び出しの両方から使われるラッパー経路で、FR3 の変更対象はラッパー側だけとする。vertex-review プラグイン（vertex-reviewer）は別プラグインなので対象外とする。
- [ ] A7（影響度: 低）: プラグインの version は main への push 時に Actions が patch を上げる。この変更で minor / major は上げない。

## 15. 参考資料

- feature-docs/codex-interactive-guard-hook/THREAT-MODEL.md: TB-3
- em-workflow/scripts/run_codex_exec.sh
- em-review/scripts/run_codex_exec.sh
