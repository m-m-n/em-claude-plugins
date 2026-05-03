---
name: sdd
description: SDD ワークフロー全体を自動実行する統合エントリポイント。sdd.yaml の進捗を参照し、未完了ステップを順次走らせる。引数で status / update-spec サブコマンドにも切り替え可能
argument-hint: "[path | status [path] | update-spec [path]]"
disable-model-invocation: true
allowed-tools: Read, Write, Glob, Grep, Bash, AskUserQuestion, Skill
---

# SDD Orchestrator

SDD ワークフロー（create-spec → create-plan → verify-plan → implement → check → verify）を統合的に実行する。`sdd.yaml` に記録された進捗から未完了ステップを判定し、連続して自動実行する。

## 設計方針

- 人間の判断が必要な場面は、下位 skill がそれぞれ `AskUserQuestion` で解決する。このオーケストレーターでは追加の確認を挟まない。
- 途中で中断された場合は、次回 `/em-sdd:sdd` を実行すれば `sdd.yaml` から自然に再開される。
- 全ての下位 skill（`sdd.1-create-spec` 等）は `disable-model-invocation: true` のため、ユーザーは `/em-sdd:sdd` 経由か `/em-sdd:sdd.<step>` を直接叩く形でのみ呼び出す。

## 引数処理

`$ARGUMENTS` の先頭トークンを解析して分岐する。

| 先頭トークン | 動作 |
|-------------|------|
| `status` | Skill tool で `em-sdd:sdd.status` を呼ぶ。残りの引数を渡す。完了したら終了 |
| `update-spec` | Skill tool で `em-sdd:sdd.update-spec` を呼ぶ。残りの引数を渡す。完了したら終了 |
| 空 | ワークフロー自動実行（引数なし）に進む |
| その他（パス等） | ワークフロー自動実行（そのまま feature path として扱う）に進む |

## ワークフロー自動実行

### Step A: feature directory の決定

1. `$ARGUMENTS` にパスが指定されていれば、それを feature directory として使う
2. なければ Glob で `doc/tasks/*/sdd.yaml` を探す
   - 1件のみ見つかった場合: そのディレクトリを使う
   - 複数見つかった場合: `AskUserQuestion` で選択
   - 0件の場合: 新規 feature とみなし、Skill tool で `em-sdd:sdd.1-create-spec` を引数なしで呼ぶ。完了後に `doc/tasks/*/sdd.yaml` を再探索して確定し、次のループに進む

### Step B: 次ステップ決定＆実行ループ

以下を繰り返す:

1. `doc/tasks/{feature}/sdd.yaml` を Read
   - YAML parse エラー: ユーザーに報告して終了
2. `workflow` 配列を順に走査し、最初の `status != "completed"` エントリを見つける
   - すべて `completed`: `SDD ワークフロー完了` と表示して終了
3. ステップ ID を skill 名にマッピング:

   | step id | skill |
   |---------|-------|
   | create-spec | `em-sdd:sdd.1-create-spec` |
   | create-plan | `em-sdd:sdd.2-create-plan` |
   | verify-plan | `em-sdd:sdd.3-verify-plan` |
   | implement | `em-sdd:sdd.4-implement` |
   | check | `em-sdd:sdd.5-check` |
   | verify | `em-sdd:sdd.6-verify` |

4. 実行開始を通知: `▶ {step-id} を実行します`（emoji は使わず `-> {step-id}` でもよい）
5. Skill tool でその skill を呼ぶ。引数には feature directory のパスを渡す
6. 呼び出しから戻ったら `sdd.yaml` を Read し直す
7. 該当ステップの status を確認:
   - `completed` → ループ継続（1. に戻る）
   - `in_progress` のまま → スキル実行が早期終了した可能性。**同じステップを最大1回まで再実行する**（再試行カウンタはステップごとに保持）。再試行後も `in_progress` のままなら現在の status を報告して中断
   - `failed` / `needs_update` → 「ユーザー判断で中断 or 何か問題発生」と解釈し、現在の status を報告してループを抜けて終了

### Step C: 終了報告

以下のいずれかを必ず出力して終わる:

- **全ステップ完了**: `SDD ワークフロー完了: {feature}`
- **中断**: `{step-id} が {status} のため中断。再開するには /em-sdd:sdd を実行してください`
- **エラー**: エラー内容とリカバリ案（YAML 不正なら `git restore` 案内など。下位 skill が既に案内している場合は重複させない）

## 注意

- **下位 skill の guard と干渉しない**: 各下位 skill は自前で完了済みステップの再実行確認などを行う。オーケストレーター側でそれを先回りしない。
- **引数の渡し方**: ワークフロー skill の多くは `$ARGUMENTS` に feature path を期待しているため、`em-sdd:sdd.1-create-spec <path>` のように Skill tool 呼び出し時に引数を渡す。新規 feature の初回呼び出し時のみ引数なし。
- **未知の step id**: マッピング表に無い step id（旧ワークフローの `review` 等）が見つかった場合は、そのステップをスキップして次に進む。
- **sdd.status / sdd.update-spec の独立ルート**: `/em-sdd:sdd status` と `/em-sdd:sdd update-spec` はワークフロー実行ループに入らず、該当 skill を単発で呼ぶだけ。

$ARGUMENTS
