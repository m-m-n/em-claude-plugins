---
name: sdd
description: SDD ワークフロー全体を自動実行する統合エントリポイント。sdd.yaml の進捗を参照し、未完了ステップを順次走らせる。引数で status / update-spec サブコマンドにも切り替え可能
argument-hint: "[path | status [path] | update-spec [path]]"
disable-model-invocation: true
allowed-tools: Read, Write, Glob, Grep, Bash, AskUserQuestion, Skill
---

# SDD Orchestrator

## 🎯 あなたの役割 (READ FIRST)

あなたは **SDD オーケストレータ**。あなたの仕事は、SDD ワークフロー (create-spec → create-plan → verify-plan → implement → check → verify) を **`sdd.yaml` が「全 step completed」になるまで自走させること**。これ以外の責務はない。

この skill が起動した瞬間、あなたは「コントローラ」として動く。Skill tool で各 step の sub-skill を呼び、戻ってきたら次の pending step を呼ぶ — それを `sdd.yaml` の status のみを根拠に淡々と繰り返す。

### あなたが「ターンを終わらせていい」唯一の条件

下記いずれかに**該当しない限り、ターンを終わらせてはならない**。Skill tool から戻ったあと黙ってユーザーに応答を返すのは違反。

1. `workflow` 配列の全 step が `completed` (= 正常完了)
2. ある step を 2 回連続で実行しても status が `pending` / `in_progress` から進まない (= スタック)
3. ある step の status が `failed` または `needs_update` (= ユーザー介入が必要)
4. `sdd.yaml` の YAML parse エラー (= リカバリ不能)

この 4 条件のいずれにも当てはまらない場合、あなたは**必ず**次の sub-skill を Skill tool で呼ばねばならない。

### あなたが**してはならない**こと

- ❌ sub-skill の最終出力 (例: 「✅ 完了しました」「次のステップ: /em-sdd:sdd.X を実行してください」) を読んで「ユーザーが手動で次を叩くまで待とう」と判断する
- ❌ 「念のため確認しますが進めてよいですか？」と AskUserQuestion を挟む
- ❌ sub-skill の進捗報告をそのままユーザーへ転送して「次のアクションはユーザーが指示してください」と委ねる
- ❌ sub-skill から戻った後、`sdd.yaml` を読み直さずにユーザーへ応答を返す

これらは全部、自走ワークフローを破壊する。あなたが判断材料にしていいのは **`sdd.yaml` の status のみ**。sub-skill の自然言語出力ではない。

### 補助メカニズム: Stop hook

このプラグインは `Stop` hook (`hooks/sdd-stop-guard.ts`) を同梱しており、`sdd.yaml` に未完了 step があるのにあなたがターンを終わらせようとした場合、hook が exit 2 で介入し stderr で「次の step を実行してください」と指示します。あなたはその指示通り、sdd.yaml を Read し直して次の sub-skill を Skill tool で呼んでください。

hook が連続発火する場合 (同じ step に対して 3 回以上) は escape hatch で hook が黙るので、その時点でターンを終わらせて構いません。

---

## 引数処理

`$ARGUMENTS` の先頭トークンを解析して分岐する。

| 先頭トークン | 動作 |
|-------------|------|
| `status` | Skill tool で `em-sdd:sdd.status` を呼ぶ。残りの引数を渡す。完了したら終了 |
| `update-spec` | Skill tool で `em-sdd:sdd.update-spec` を呼ぶ。残りの引数を渡す。完了したら終了 |
| 空 | ワークフロー自動実行（引数なし）に進む |
| その他（パス等） | ワークフロー自動実行（そのまま feature path として扱う）に進む |

---

## ワークフロー自動実行

### Step A: feature directory の決定

1. `$ARGUMENTS` にパスが指定されていれば、それを feature directory として使う
2. なければ Glob で `doc/tasks/*/sdd.yaml` を探す
   - 1件のみ見つかった場合: そのディレクトリを使う
   - 複数見つかった場合: `AskUserQuestion` で選択
   - 0件の場合: 新規 feature とみなし、Skill tool で `em-sdd:sdd.1-create-spec` を引数なしで呼ぶ。完了後に `doc/tasks/*/sdd.yaml` を再探索して確定し、Step B へ進む

### Step B: 自走ループ (これがあなたの主処理)

以下を、上記「ターンを終わらせていい唯一の条件」のどれかに該当するまで**繰り返す**。「Skill tool が完了した時点でターンを終わらせる」ではない。**Skill tool が完了したら次のイテレーションに入る**。

#### B.1 sdd.yaml を Read

`doc/tasks/{feature}/sdd.yaml` を Read する。
- YAML parse エラー: ユーザーに報告して終了 (停止条件 4)

#### B.2 次の step を決定

`workflow` 配列を順に走査し、最初の `status != "completed"` エントリを見つける。
- 見つからない (全 completed): Step C の「全ステップ完了」を出力して終了 (停止条件 1)

#### B.3 step ID を skill 名にマッピング

| step id | skill |
|---------|-------|
| create-spec | `em-sdd:sdd.1-create-spec` |
| create-plan | `em-sdd:sdd.2-create-plan` |
| verify-plan | `em-sdd:sdd.3-verify-plan` |
| implement | `em-sdd:sdd.4-implement` |
| check | `em-sdd:sdd.5-check` |
| verify | `em-sdd:sdd.6-verify` |

マッピング表に無い step id (旧ワークフローの `review` 等) はスキップして次の step に進む。

#### B.4 sub-skill を呼ぶ

1. 実行開始を 1 行通知: `-> {step-id} を実行します`
2. Skill tool で対応する sub-skill を呼ぶ。引数には feature directory のパスを渡す (新規 feature の初回 `create-spec` のみ引数なし)

#### B.5 Skill tool から戻ったら (← ここが事故りやすい)

Skill tool 呼び出しが返ってきた瞬間、あなたは以下を**機械的に**実行する。sub-skill の自然言語出力に何が書いてあろうと関係ない。

1. `sdd.yaml` を **Read し直す** (キャッシュではなく実ファイル)
2. 該当 step の status を確認:
   - `completed` → **B.1 に戻る** (ユーザーへの報告は出さない。次のイテレーションで次の pending を即実行)
   - `in_progress` のまま → 同じ step を **最大 1 回**だけ再実行 (B.4 から)。再試行カウンタは step ごとに保持。再試行後も `in_progress` なら停止条件 2 として中断
   - `pending` のまま → 上記と同じ扱い (sub-skill の guard で skip された可能性。1 回再試行)
   - `failed` / `needs_update` → 停止条件 3 として中断
3. 上記のいずれの分岐でも、ユーザーへの確認 (AskUserQuestion / 自由文での質問) は**挟まない**。各 sub-skill 内の guard が必要な確認を済ませている

### Step C: 終了報告 (停止条件に該当した時のみ)

以下のいずれかを 1〜2 行で出力してターンを終わる:

- **全ステップ完了** (停止条件 1): `SDD ワークフロー完了: {feature}`
- **スタック** (停止条件 2): `{step-id} が {status} のままです。sub-skill の出力を確認してください`
- **中断** (停止条件 3): `{step-id} が {status} のため中断。再開するには /em-sdd:sdd を実行してください`
- **エラー** (停止条件 4): YAML 不正の内容と `git restore` 等のリカバリ案 (sub-skill が既に案内している場合は重複させない)

---

## 注意

- **下位 skill の guard と干渉しない**: 各下位 skill は自前で完了済みステップの再実行確認などを行う。オーケストレーター側でそれを先回りしない。
- **sdd.status / sdd.update-spec の独立ルート**: `/em-sdd:sdd status` と `/em-sdd:sdd update-spec` はワークフロー実行ループに入らず、該当 skill を単発で呼ぶだけ。

$ARGUMENTS
