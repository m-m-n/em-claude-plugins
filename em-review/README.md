# em-review

em-workflow のレビューフェーズのスタンドアロン版。SDD を通さない日常のコードレビューを `/em-review:multi-review` 一発で実行する。

現在の `git diff HEAD`（+ untracked ファイル。diff が無ければコードベース全体）を対象に、観点を動的選択して観点スキル注入型の汎用レビュアーを並列起動し、bounded auto-fix とレビュー記録の書き出しまで行う。GitHub PR の番号 / URL を渡せば `gh pr diff` ベースの report-only レビューもできる。**コミットは一切しない**（修正はワーキングツリーに残り、git の扱いはユーザーに委ねる）。

## フロー

```
/em-review:multi-review [PR番号|PR URL] [--report-only] [--records <dir>]
    │
    ├─ R0  引数解析・records_base 解決（デフォルト /tmp/em-review/{repo-key}/）
    │        SSOT 解決（fail-closed）・レビュー対象決定（diff / whole-codebase / pr-diff + サイズゲート）
    │        パス検証 → diff_cmd_quoted 構築、SPEC.md 探索、codex 可用性プローブ、
    │        {records_base}/reviews-*/round*.yaml から round_context 構築（nit 蒸し返し防止）
    ├─ R1  観点選択（2 層: 機械フロア + 裁量追加のみ）
    ├─ R2  ファンアウト（1 メッセージで N 並列 Task、条件により Codex 二重化）
    ├─ R3  集約・サニタイズ・クロスモデル一致スコアリング
    ├─ R4  bounded auto-fix（≤ 3 ループ、--report-only でスキップ、PR モードは常にスキップ、コミットなし）
    ├─ R5  {records_base}/reviews-{YYYYMMDD-HHMM}/round1.yaml へ記録
    └─ R6  日本語レポート
```

## コマンド

| コマンド | 用途 |
|---------|------|
| `/em-review:multi-review` | 並列多観点レビュー + auto-fix（≤ 3 ループ）+ 記録 + レポート |
| `/em-review:multi-review --report-only` | auto-fix をスキップしてレポートのみ（別名: `--no-auto-fix`, `--no-fix`） |
| `/em-review:multi-review --records <dir>` | 記録の保存先を指定（デフォルト: `/tmp/em-review/{repo-key}/`） |
| `/em-review:multi-review <PR番号\|PR URL>` | GitHub PR を `gh pr diff` ベースでレビュー（report-only 固定） |

## アーキテクチャ: エージェント 3 枚 + スキル注入

観点ごとにエージェントを持たず、汎用レビュアーに観点知識をスキルとして注入する（「規律は静的プリロード、ドメイン知識は動的注入」）。

### エージェント

| エージェント | 役割 | 静的プリロード |
|-------------|------|---------------|
| reviewer | 汎用 Claude レビュアー（観点はスキル注入） | — |
| codex-reviewer | 汎用 GPT/Codex レビュアー（クロスバリデーション用） | codex-prompting |
| review-editor | auto-fix 適用専用（Read/Edit のみの最小権限） | — |

### 観点スキル（レジストリ `references/reviewers.yaml`）

`review-security` / `review-performance` / `review-architecture` / `review-spec` / `review-comprehensive`。

spec 観点は SPEC.md が見つかったときだけ実行される（不在時はクリーンにスキップ）。comprehensive は Claude 専用（横断的な広さは第二モデルへの委譲に馴染まないため）。

## 動的レビュー選択（2 層）

1. **機械層**: 通常はフロア = `baseline`（comprehensive）+（SPEC.md があれば spec）。cwd に em-workflow の `feature-docs/{feature}/workflow.yaml` があり tasks が現在の diff をカバーしていれば、その domains / complexity 宣言で `references/review-rules.yaml` を決定的に評価してもよい。
2. **裁量層**: オーケストレーターが diff を見て観点を**追加のみ**できる（削除不可）。追加理由は round 記録に残る。

Codex クロスバリデーションは強度の軸として分離: complexity high のタスクを含む（workflow.yaml 併用時）、または最終選択セットに security が入った場合に発動し、`codex_supported: true` の観点が claude + codex で二重実行される。

## 信頼度スコアリング

| 状況 | スコア |
|------|--------|
| Claude + Codex 一致（同一観点・同一サイト ±5 行） | 95 |
| Claude のみ | 60 |
| Codex のみ | 50 |
| spec — Claude のみ（codex スキップ時） | 70 |
| comprehensive（設計上 Claude のみ） | 65 |
| 複数観点が同一サイトを指摘 | +15（上限 100） |

## Auto-fix（R4）

対象 = `severity ∈ {critical, high}` かつ `category != spec` かつ suggestion 非空。候補は機械的に 3 分類される:

- **auto-applicable**: 矛盾のない unified-diff 提案 → **承認プロンプトなしで**適用
- **conflict**: 同一サイトに非互換の提案 → グループごとに AskUserQuestion
- **needs-judgment**: 自然言語 / 複数代替案の提案 → finding ごとに AskUserQuestion

適用は `review-editor` サブエージェント（Read/Edit のみ）へディスパッチし、スコープはオーケストレーターの content-hash delta（BACKUP_DIR スナップショット × `git hash-object`）で検証する。複数ファイルにまたがるループは wave-parallel、単一ファイルは sequential。生産的なループの後は全レビュアーを再実行して収束判定する（`clean` / `loop-cap` / `no-progress`）。

> ⚠️ auto-applicable な diff は内容の人間レビューなし（構造検証のみ）でワーキングツリーに到達する。信頼していない diff（コントリビューターのブランチ等）には `--report-only` を使うこと。

## PR レビュー（report-only 固定）

`/em-review:multi-review 123` や `/em-review:multi-review https://github.com/owner/repo/pull/123` で GitHub PR をレビューできる。

- `gh` CLI（認証済み）が必要。オーケストレーターが `gh pr diff` を 1 回だけ実行して `{records_dir}/pr.diff` に落とし、各レビュアーはそのファイルを読む（codex サンドボックスはネットワーク不可のため、これが唯一 diff を事前実体化するモード）。
- PR のコードは working tree に存在しないため **auto-fix は常にスキップ**される（termination: `pr-mode`）。
- 可能なら `git fetch origin pull/{n}/head` で PR head を取り込み、レビュアーは `git show {sha}:<path>` で周辺コードを読む（ローカルオブジェクト読取りのみ。fetch できなければ diff 内容のみでレビュー）。

## レビュー記録

各実行の findings と処理結果（fixed / declined / deferred + 理由）を `{records_base}/reviews-{YYYYMMDD-HHMM}/round1.yaml` に書き出す。

- **デフォルトの records_base は `/tmp/em-review/{リポジトリ名}-{git common dir の hash8}`**。プロジェクトディレクトリを汚さず、同じリポジトリなら次回も同じ場所が解決されるため、`declined` 済み findings の蒸し返し抑止（round_context）がフラグなしで機能する。再起動で消える点はデフォルトの割り切り。
- **`--records <dir>` で任意の場所に切り替えられる**（例: `--records ./tmp` でプロジェクト内に永続化）。指定は人間起点なので containment 検査はしない（自己責任）。round_context も指定した records_base 配下から読む。

## 要件

- git（無くても whole-codebase モードで動作する）
- Codex CLI（任意 — 無ければ GPT クロスバリデーションはクリーンにスキップ）
- gh CLI（任意 — PR レビュー時のみ必須）

## ファイル構成

```
em-review/
├── .claude-plugin/plugin.json
├── README.md                          (this file)
├── scripts/
│   └── run_codex_exec.sh              (Codex CLI wrapper: read-only sandbox, timeout, stdin redirect)
├── references/
│   ├── review-phase.md                (R0–R6 orchestration protocol — /em-review:multi-review が inline 実行)
│   ├── review-protocol.md             (全レビュアー共通プロトコル SSOT)
│   ├── review-output-schema.json      (findings の JSON Schema)
│   ├── reviewers.yaml                 (観点レジストリ)
│   ├── review-rules.yaml              (機械層のルール表)
│   └── codex-cli.yaml                 (wrapper 設定: timeout)
├── skills/
│   ├── multi-review/SKILL.md          (エントリポイント → /em-review:multi-review)
│   ├── review-security/SKILL.md       (動的注入用・user-invocable: false)
│   ├── review-performance/SKILL.md
│   ├── review-architecture/SKILL.md
│   ├── review-spec/SKILL.md
│   ├── review-comprehensive/SKILL.md
│   └── codex-prompting/SKILL.md       (codex-reviewer 静的プリロード用)
└── agents/
    ├── reviewer.md                    (汎用 Claude レビュアー)
    ├── codex-reviewer.md              (汎用 GPT/Codex レビュアー)
    └── review-editor.md               (auto-fix 適用専用)
```
