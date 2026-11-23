# Feature: resume-steps-actor-labels

## Overview

em-workflow の停止からの復帰手順（`resume_conditions` と停止時の報告。対話実行の報告を含む）で、各手順に「AI がやれる」か「人の判断が要る」かを示すラベルを付ける。AI がやれる手順を先に並べる。

## Objectives

- 停止からの復帰手順の各手順で、AI がやれるのか人の判断が要るのかを示す。AI の手順を先に並べ、振り分けや後続の実行で、AI がやれる手順を人の作業として扱わないようにする。

## Technical Requirements

### Functional Requirements

- **FR1: 各手順の先頭のラベル** — `resume_conditions` の復帰手順は、どれも次の 2 つの固定ラベルのどちらか 1 つで始まる。
    - 「AI がやれる」
    - 「人の判断が要る（理由: X）」
    - X は次の 3 語のどれか 1 つ。「物理的に人しかできない」「戻せない変更の承認」「価値判断」
- **FR2: 例外なく AI を先にする** — 「AI がやれる」手順はすべて、「人の判断が要る」手順より前に並ぶ。人の判断の後でしか実行できない AI の作業は、別の手順にしない。その人の手順の中に「判断の後、AI が ... を実行する」と書く。「人の判断が要る」手順の後に「AI がやれる」手順が来ることはない。
- **FR3: 人の手順の理由** — 「人の判断が要る」手順は、FR1 のとおりラベルの中に 3 つの理由のどれか 1 つを持つ。3 つの理由のどれかに当てはまるときだけ「人の判断が要る」とし、それ以外の手順はすべて「AI がやれる」とする。
- **FR4: 規則の置き場所は batch-terminal-line.md** — FR1〜FR3 は `em-workflow/references/batch-terminal-line.md` の `## Field values` にある既存の `resume_conditions` の箇条の中に、続きの文か字下げした下位の箇条として書く。新しい `## ` 見出しと、新しい最上位の ``- `key` `` 箇条は足さない。
- **FR5: 停止時の報告から規則を引き、同じ形にする** — `em-workflow/skills/develop/SKILL.md` の `## 停止時の報告（停止条件 2-4 のみ）` で、3 つの箇条（スタック / 中断 / YAML エラー）は一字一句変えない。その後ろに新しい段落を足し、`references/batch-terminal-line.md` の `resume_conditions` の規則を引く。その段落では、停止時の報告が載せる復帰手順が、バッチでも対話実行でも同じ形（ラベル付き、AI が先、人の手順ごとに理由）を取ることを述べる。3 つの雛形が指す手順もこれに含む。
- **FR6: Result format の例をラベル付きにする** — `batch-terminal-line.md` の `## Result format` の例のうち、`resume_conditions` の行をラベル付きの値に差し替える。値は物理的に 1 行のままにし、複数の手順は `\n` エスケープでつなぐ。例はちょうど 8 行で、8 つのキーをこの順のまま保つ。`tests/test_batch_stop_contract.py` の `RESULT_FORMAT_TEXT` を同じ変更の中で更新する。`## Escaping` は変えない。
- **FR7: 固定するテスト** — 新しい unittest モジュール（例: `tests/test_resume_steps_actor_labels.py`）で次の 4 つを固定する。
    - (a) `batch-terminal-line.md` の `## Field values` にある `resume_conditions` の箇条の中の、5 つの固定文字列と並び順の規則（人の手順の中に書き込む規則を含む）。
    - (b) `SKILL.md` の停止時の報告の段落が `batch-terminal-line.md` を引き、対話実行の報告も同じ形を取ると述べていること。
    - (c) ラベル付きの Result format の例。「AI がやれる」で始まり、「人の判断が要る」の後に「AI がやれる」が来ないこと。
    - (d) どの照合も、変更前の文を模した偽の文を通さないこと（否定の証明）。

### Non-Functional Requirements

- **NFR1: 値の形式は変えない** — `resume_conditions` の値の形式の規則は変えない。`state` が `stopped` のときは空白以外を含み、それ以外では空。`detail` の正規化を通さない。`## Escaping` の規則、CR/LF/TAB の扱い、受け手側の制約も変えない。ラベルについて、出力側・受け手側の拒否規則は足さない。
- **NFR2: 既存の固定を保つ** — 既存のテストは、`RESULT_FORMAT_TEXT`（FR6）を除いて変更せずに通る。
    - 停止時の報告の見出しは変えず、空白を除いた先頭部分が `PRE_CHANGE_STOP_REPORT_SECTION` と一致したままにする。
    - 3 つの箇条は一字一句変えない。
    - 停止時の報告の見出しと `## バッチ構造化結果` の間に `## ` 見出しを置かない。
    - `CONTRACT_HEADINGS` は変えない。
    - `## Field values` の箇条の正規表現は、8 つのキーをこの順で返したままにする。
    - `resume_conditions` の箇条は既存の次の句を保つ。'non-whitespace whenever `state` is `stopped`'、'never empty and never whitespace-only'、'empty for every other `state`'、'NOT put through `detail`'s normalization'、'survive as'、'carried in full inside `resume_conditions`'
- **NFR3: SKILL.md の文字列の制約** — `SKILL.md` に足す段落には、次のどれも入れない。
    - 理由コード
    - 手順が無いことを示す番兵の値
    - 8 つのフィールド名すべての同時出現
    - AskUserQuestion（ファイル内の出現数は 7 のまま）
    - 'decision: stop' / 'needs_rework' / 'classification'
    - 2 つ目の `${CLAUDE_PLUGIN_ROOT}/references/batch-mode.md`
    - 'Legacy review-failure recovery' の文
- **NFR4: version** — プラグインの version は手で変えない。

## Implementation Approach

### File Structure

```
em-workflow/
├── references/
│   └── batch-terminal-line.md        # resume_conditions の箇条に規則を追記、Result format の例を差し替え
└── skills/
    └── develop/
        └── SKILL.md                  # 停止時の報告の 3 箇条の後に段落を追加
tests/
├── test_batch_stop_contract.py       # RESULT_FORMAT_TEXT を更新
└── test_resume_steps_actor_labels.py # 新規（名前は例）
```

## Declared Change Set

機能固有のパスは手で並べない。create-plan で、`workflow.yaml` の各タスクの `files` から導く（`references/phases/create-plan-phase.md`）。

それに加えて、ワークフローが生成する次の 2 つを既定で宣言する。

- `feature-docs/resume-steps-actor-labels/**`
- `test-docs/resume-steps-actor-labels/**`

この宣言は上位集合の宣言で、検証時に観測した変更の集合が宣言の集合に含まれていればよい。宣言したパスが作られなくても違反ではない。

## Test Scenarios

### Unit Tests

- [ ] TS-1: `batch-terminal-line.md` から `## Field values` を切り出し、`resume_conditions` の箇条を次の最上位の箇条の手前までに絞る - 5 つの固定文字列があること。変更前の箇条を模した偽の文は照合を通らないこと。
- [ ] TS-2: 同じ箇条で、AI を先にする規則と「判断の後、AI が」と書き込む規則を確かめる - 両方があること。ラベルだけで並び順の規則が無い偽の文は通らないこと。
- [ ] TS-3: `SKILL.md` の `## 停止時の報告（停止条件 2-4 のみ）` から `## バッチ構造化結果` までを切り出す - YAML エラーの箇条の後のまとまりが `references/batch-terminal-line.md` を名指しし、対話実行の報告も同じ形を取ると述べていること。変更前の節の文は照合を通らないこと。
- [ ] TS-4: `## Result format` の YAML のコードブロックを取り出し、`resume_conditions` の値をデコードして、デコードした改行で分ける - 各手順が 2 つのラベルのどちらかで始まること。「人の判断が要る」手順の後に「AI がやれる」手順が来ないこと。人のラベルが 3 つの理由のちょうど 1 つを持つこと。現在のラベルの無い例は通らないこと。例が 8 行で 8 つのキーを持つこと。

### Integration Tests

- [ ] TS-5: テスト一式を実行する - `tests/test_batch_quiet_output_skill_wiring.py`、`tests/test_review_gate_abort_skill_wiring.py`、`tests/test_batch_stop_contract.py` の既存の固定が、`RESULT_FORMAT_TEXT` の更新を含めて通ること。

### E2E Tests

**Existing E2E tests**: None
**Run command**: Not detected

## Success Criteria

- [ ] AC1（FR1, FR3, FR4）: `batch-terminal-line.md` の `## Field values` の `resume_conditions` の箇条が、各手順は「AI がやれる」か「人の判断が要る（理由: X）」で始まり、X は「物理的に人しかできない」「戻せない変更の承認」「価値判断」のどれかであると述べている。
- [ ] AC2（FR2）: 同じ箇条が、「AI がやれる」手順は例外なく「人の判断が要る」手順より前に並ぶと述べている。人の判断に依存する AI の作業は、その人の手順の中に「判断の後、AI が ... を実行する」と書くと述べている。
- [ ] AC3（FR5）: `SKILL.md` の停止時の報告の節が 3 つの箇条を一字一句保ち、その後ろの段落が `references/batch-terminal-line.md` を引いて、停止時の報告の復帰手順は対話実行の報告を含めて同じ形を取ると述べている。
- [ ] AC4（FR6）: `## Result format` の例の `resume_conditions` の値がラベル付き、物理的に 1 行、AI が先で、例が 8 行と 8 つのキーを保っている。`## Escaping` は変更前とバイト単位で同じ。
- [ ] AC5（FR7）: 新しい unittest モジュールが AC1〜AC4 を固定し、照合ごとに変更前を模した偽の文による否定の証明を持つ。
- [ ] AC6（NFR1, NFR2, NFR3）: `python3 -m unittest discover -s tests` が通る。

## Assumptions

- a1: ラベルの機械的な検証は足さない。この規則は中身の規則で、値の形式の規則は変えない。
- a2: 案内が「または」でつないだ選択肢を示すとき、各選択肢をそれぞれ 1 つの手順とし、それぞれにラベルを付ける。
- a3: 作業不要の停止の「再開不要」のように手順を持たない案内にはラベルを付けない。その `SKILL.md` の文は変えない。
- a4: 場面ごとの再開条件の段落（`batch-terminal-line.md` の書き込み拒否、`implement-phase.md` の中断の終端コミット / 書き込み拒否、`review-phase.md` の仕様変更ゲートの中断）は文言を変えない。出力するときのラベル付けは一般の規則に従う。
- a5: 各手順はそれぞれ新しい行から始める。バッチでは、改行は既存の `\n` エスケープとして残る。
- a6: 手順の文の言語にかかわらず、ラベルは固定の日本語の文字列とする。
- a7: version は手で上げない。

## Open Questions

なし
