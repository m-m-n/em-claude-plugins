# Feature: version-bump-missing-base

## Overview

`.github/workflows/plugin-version-bump.yml` の push 時の基点の決定を変え、base commit（BEFORE）を取得できない push でも AFTER の第 1 親を基点にして変更プラグインの version を上げる。workflow_dispatch で失われた version 更新を取り戻せるようにし、main への non-fast-forward 更新を禁止するルールセットの定義をリポジトリに置く。要件は `feature-docs/version-bump-missing-base/REQUIREMENTS.md` を参照する。

## Objectives

- main に入ったプラグインの変更が、base commit を取得できない push でも version の更新を伴い、インストール済みプラグインに届く
- Actions の version 更新コミットを含まない push で origin/main が置き換わらない
- 既に失われた em-workflow の version 更新を、人の操作 1 回で取り戻せる

## User Stories

### US1: push 時の version 自動更新
As a マーケットプレイス利用者, I want to main に入ったプラグインの変更が base commit を取得できない push でも version の更新を伴うこと, so that インストール済みプラグインに変更が届く.

**Acceptance Criteria:**
- [ ] AC-1: BEFORE が clone に無く origin から取得できるとき、BEFORE を基点に比較し、変更プラグインの version を上げて exit 0 で終わる
- [ ] AC-2: BEFORE を取得できないとき、および全ゼロのとき、AFTER の第 1 親を基点にし、`::warning::` を出し、変更プラグインの version を上げて exit 0 で終わる
- [ ] AC-3: 基点を取得できず AFTER に第 1 親も無いとき、非 0 で終了し、plugin.json と marketplace.json は変わらない
- [ ] AC-4: 再現手順（Actions の更新コミットを含まない commit で main を置き換えた後の push）を一時リポジトリで再現したとき、AFTER の version は基点の version より大きくなり、plugin.json と marketplace.json の値は一致する
- [ ] AC-5: AFTER の version が基点と同じか低いとき、大きい方の patch を 1 上げた値が両 JSON に書かれる
- [ ] AC-6: AFTER の version が基点より高いとき、version は変わらず、bumped は空になる
- [ ] AC-7: 基点に plugin.json が無いプラグインと、version が MAJOR.MINOR.PATCH の形でないプラグインは上げない
- [ ] AC-12: workflow と template はバイト単位で同一で、どちらにも base commit が無いときに exit 0 で終わる skip の分岐が無い

### US2: workflow_dispatch による version の手動更新
As a リポジトリの保守者, I want to plugin と min_version を指定して workflow_dispatch を 1 回実行すること, so that 既に失われた version 更新を取り戻せる.

**Acceptance Criteria:**
- [ ] AC-8: workflow_dispatch で現在の version が min_version 以下かつ major・minor が同じとき、実行後の version は min_version より大きく、その patch は min_version の patch + 1 で、両 JSON の値は一致する
- [ ] AC-9: workflow_dispatch で現在の version が min_version を超えているとき、ファイルは変わらず、bumped は空で、exit 0 で終わる
- [ ] AC-10: workflow_dispatch で plugin が未登録、または min_version が MAJOR.MINOR.PATCH の形でないとき、非 0 で終了しファイルは変わらない
- [ ] AC-11: workflow_dispatch は main 以外の ref では version 更新のステップを実行しない

### US3: non-fast-forward の禁止とマージ後の手順
As a リポジトリの保守者, I want to non-fast-forward を禁止するルールセットの定義とマージ後の手順がリポジトリにあること, so that Actions の version 更新コミットを含まない push で origin/main が置き換わらない.

**Acceptance Criteria:**
- [ ] AC-13: ルールセット定義ファイルは non_fast_forward のルールだけを持ち、bypass_actors が空で、enforcement が active、対象が main である
- [ ] AC-14: マージ後の人の手順（ルールセットの作成と確認、workflow_dispatch の実行、キャッシュへの反映の確認）が文書にある
- [ ] AC-15: create.md の「動き」が FR1〜FR5 の挙動を述べている
- [ ] AC-16: `python3 -m unittest discover -s tests` が exit 0 で終わる

## Technical Requirements

### Functional Requirements
- **FR1:** push 時の基点の決定。push で動くとき、BEFORE（github.event.before）が 40 桁 hex かつ全ゼロでなく clone にあれば BEFORE を基点にする。clone に無ければ `git fetch origin <BEFORE>` を 1 回だけ試し、取れたら BEFORE を基点にする。取れないとき、全ゼロのとき、40 桁 hex でないときは AFTER の第 1 親を基点にし、その旨を `::warning::` で出して続行する。AFTER に第 1 親も無ければ、ファイルを変えずに非 0 で終了する。skip を出して exit 0 で終わる分岐は残さない。
- **FR2:** 変更プラグインの検出。基点と AFTER の差分に含まれるファイルから、`.claude-plugin/plugin.json` を持つ最も近い祖先ディレクトリをプラグインとして集める。
- **FR3:** version の比較と上げ方。変更プラグインごとに、基点の plugin.json と AFTER の plugin.json の version を整数 3 要素（MAJOR.MINOR.PATCH）で比べる。AFTER が基点と同じか低いときは、大きい方の patch を 1 上げた値を plugin.json と marketplace.json の同じ name のエントリ（version を持つもの）に書く。AFTER が基点より高いときは上げない。基点に plugin.json が無いプラグイン（新規追加）は上げない。どちらかの version が MAJOR.MINOR.PATCH の形でないプラグインは上げない。
- **FR4:** workflow_dispatch による手動の version 更新。workflow に workflow_dispatch を足す。入力は plugin（marketplace.json に登録済みのプラグイン名、必須）と min_version（MAJOR.MINOR.PATCH、必須）。main でだけ動く。対象の現在の version が min_version 以下で、major と minor が min_version と同じなら、min_version の patch を 1 上げた値を plugin.json と marketplace.json に書く。現在の version が min_version を超えていれば、ファイルを変えずに成功で終わる。plugin が未登録、または min_version が MAJOR.MINOR.PATCH の形でないときは、ファイルを変えずに非 0 で終了する。
- **FR5:** 更新結果の出力と main への取り込み。push と workflow_dispatch のどちらでも、上げたプラグインを `name@version` のカンマ区切りで GITHUB_OUTPUT の bumped に書く。上げなかったときは空にする。bumped が空でないとき、既存の PR 作成・マージのステップで main に取り込む。
- **FR6:** workflow と template の一致。`.github/workflows/plugin-version-bump.yml` と `plugin-dev/skills/plugin-dev/templates/plugin-version-bump.yml` はバイト単位で同一にする。
- **FR7:** non-fast-forward を禁止するルールセットの定義。main への non-fast-forward 更新を禁止するルールセットの定義を、リポジトリ内のファイルとして置く。ルールは non_fast_forward だけ、bypass_actors は空、enforcement は active、対象は main。既存の main ルールセットは変えない。
- **FR8:** マージ後に人が行う手順の文書。PR マージ後に人が行う手順を文書に書く。(a) gh api によるルールセットの作成と、作成後の確認。(b) workflow_dispatch を plugin と min_version を指定して 1 回実行し、version が上がったことを確かめる手順。(c) マーケットプレイスの更新と Claude Code の再起動で、インストール済みキャッシュに main の内容が届いたことを確かめる手順。
- **FR9:** plugin-dev の説明の更新。`plugin-dev/skills/plugin-dev/references/create.md` の「動き」を、FR1〜FR5 の挙動（基点の決定と `::warning::`、基点を取れないときの非 0 終了、version の比較規則、workflow_dispatch の入力と挙動）に合わせる。
- **FR10:** 再発を検出するテスト。`tests/` の unittest（標準ライブラリだけ）が workflow の YAML から heredoc を 1 つだけ抜き出し、一時ディレクトリの bare リポジトリと `git clone --no-local` で作った clone の上で実行する。終了コード、GITHUB_OUTPUT、plugin.json と marketplace.json の中身、workflow と template のバイト一致を確かめる。ルールセット定義ファイルの中身（FR7）も確かめる。

### Non-Functional Requirements
- **NFR1 - Dependencies:** workflow 内のスクリプトは Python 標準ライブラリと git だけを使う
- **NFR2 - Structure:** workflow の YAML に含まれる heredoc は 1 つだけ。push と workflow_dispatch の処理はその 1 つに入れる
- **NFR3 - Test isolation:** テストはネットワークに出ず、`~/.claude` を読まず、一時ディレクトリの中だけで git を操作する
- **NFR4 - Version:** この feature の変更は plugin.json と marketplace.json の version を変えない
- **NFR5 - Documentation:** SPEC・計画・受け入れ条件に具体的な version の値を書かない

## Implementation Approach

### Architecture

**System Architecture:**
```
┌──────────────────────────────────────────────┐
│ GitHub Actions: plugin-version-bump.yml      │
│   trigger: push (main) / workflow_dispatch   │
├──────────────────────────────────────────────┤
│ heredoc スクリプト（1 つ、Python 標準ライブラリ + git） │
│   push: 基点の決定 → 変更プラグイン検出 → 比較・更新 │
│   workflow_dispatch: 入力検証 → 比較・更新         │
├──────────────────────────────────────────────┤
│ GITHUB_OUTPUT: bumped                         │
├──────────────────────────────────────────────┤
│ 既存の PR 作成・マージのステップ（bumped が空でないとき） │
└──────────────────────────────────────────────┘
```

**Component Diagram:**
```
.github/workflows/plugin-version-bump.yml
  == (バイト一致) plugin-dev/skills/plugin-dev/templates/plugin-version-bump.yml
  └─ heredoc スクリプト
       ├─ 読み書き: <plugin>/.claude-plugin/plugin.json
       └─ 読み書き: .claude-plugin/marketplace.json

.github/rulesets/main-non-fast-forward.json   (FR7)
.github/rulesets/README.md                    (FR8 (a))
README.md のメンテナンスの節                    (FR8 (b)(c))

tests/ の unittest (FR10)
  ├─ 読む: workflow の YAML（heredoc を 1 つ抜き出す）、template、ルールセット定義
  └─ 実行: 一時ディレクトリの bare リポジトリ + git clone --no-local の clone
```

### Data Flow

push:
```
github.event.before (BEFORE), AFTER
  → 基点の決定 (FR1)
      BEFORE が 40 桁 hex・全ゼロでない・clone にある → BEFORE
      clone に無い → git fetch origin <BEFORE> を 1 回 → 取れたら BEFORE
      それ以外 → AFTER の第 1 親 + ::warning::
      第 1 親も無い → ファイルを変えずに非 0 で終了
  → 基点と AFTER の差分 → 変更プラグイン (FR2)
  → version 比較と更新 (FR3) → plugin.json / marketplace.json
  → GITHUB_OUTPUT bumped (FR5) → 空でなければ PR 作成・マージ
```

workflow_dispatch（main でだけ動く）:
```
inputs: plugin, min_version
  → 入力検証（未登録の plugin / 形の違う min_version → ファイルを変えずに非 0）
  → 現在の version と min_version の比較 (FR4)
      現在 <= min_version、major・minor 同じ → min_version の patch + 1 を両 JSON に書く
      現在 <= min_version、major か minor が違う → ファイルを変えずに非 0（A2）
      現在 > min_version → ファイルを変えずに成功
  → GITHUB_OUTPUT bumped (FR5) → 空でなければ push 時と同じ PR 作成・マージ（A3）
```

### API Design

#### workflow_dispatch の入力

| 入力 | 必須 | 形 | 内容 |
|------|------|----|------|
| plugin | 必須 | 文字列 | marketplace.json に登録済みのプラグイン名 |
| min_version | 必須 | MAJOR.MINOR.PATCH | 比較の下限にする version |

#### GITHUB_OUTPUT

| キー | 値 |
|------|----|
| bumped | 上げたプラグインの `name@version` のカンマ区切り。上げなかったときは空 |

#### ルールセット定義ファイル

`.github/rulesets/main-non-fast-forward.json` に、GitHub REST API のルールセット作成ペイロードの形の JSON を置く（A4）。

| 項目 | 値 |
|------|----|
| 対象 | main |
| rules | non_fast_forward だけ |
| bypass_actors | 空 |
| enforcement | active |

### Database Schema

該当なし

### Dependencies

**Internal Dependencies:**
- 既存の PR 作成・マージのステップ: bumped が空でないとき、push と workflow_dispatch の両方で使う（FR5、A3）
- `plugin-dev/skills/plugin-dev/templates/plugin-version-bump.yml`: workflow とバイト単位で同一にする（FR6）
- `plugin-dev/skills/plugin-dev/references/create.md`: 「動き」を FR1〜FR5 に合わせる（FR9）

**External Dependencies:**
- Python 標準ライブラリ: workflow 内のスクリプトとテスト（NFR1、FR10）
- git: 基点の決定、差分の取得、テスト用の一時リポジトリ（NFR1、FR10）
- GitHub REST API（gh api）: マージ後の人の手順でルールセットを作成する（FR8 (a)）

### File Structure

```
.github/
├── workflows/
│   └── plugin-version-bump.yml          # FR1〜FR5、FR6
└── rulesets/
    ├── main-non-fast-forward.json       # FR7（A4 による SPEC の決定）
    └── README.md                        # FR8 (a)（A5 による SPEC の決定）
plugin-dev/skills/plugin-dev/
├── templates/
│   └── plugin-version-bump.yml          # FR6
└── references/
    └── create.md                        # FR9
README.md                                # FR8 (b)(c)、メンテナンスの節（A5 による SPEC の決定）
tests/
└── (unittest ファイル)                    # FR10、NFR3
```

### SPEC の決定（A4・A5）

- A4: ルールセット定義の置き場所とファイル名は `.github/rulesets/main-non-fast-forward.json` とする。
- A5: マージ後の人の手順の文書の置き場所は次のとおりとする。
    - (a) ルールセットの作成と確認: `.github/rulesets/README.md`
    - (b) workflow_dispatch の実行と確認、(c) キャッシュへの反映の確認: リポジトリルートの `README.md` のメンテナンスの節
- (b) の入力値は A6 に従い、plugin を em-workflow、min_version を失われた Actions 更新コミットの記録した version として人の手順にだけ書く。SPEC・計画・受け入れ条件には値を書かない（NFR5）。

## Declared Change Set

This section states the create-plan derivation instead of a hand-authored
list: the feature-specific paths above are derived at create-plan from
every task's `files` entries in `workflow.yaml`
(`references/phases/create-plan-phase.md`).

Every SPEC declares, by default, the following two workflow-generated
entries in addition to the feature-specific paths above:

- `feature-docs/version-bump-missing-base/**`
- `test-docs/version-bump-missing-base/**`

`feature-docs/version-bump-missing-base/**` covers `REQUIREMENTS.md`, `SPEC.md`,
`IMPLEMENTATION.md`, `workflow.yaml`, `phase-state/`, `tasks/`,
`reviews/roundN.yaml`, `VERIFICATION.md`, `retrospect.yaml`, and the design
artifacts the design step produces. These are generated and owned by the
phase documents and by `references/phase-state.md`; this section cites them
and restates none of their rules.

`test-docs/version-bump-missing-base/**` covers `test-docs/version-bump-missing-base/{T}.tests.yaml`, the
per-task test record. It is generated and owned by `implement-phase.md`;
this section cites it and restates none of its rules.

These two default entries are part of the declaration unless the SPEC
author explicitly removes them; their absence is never assumed by
silence — removal is a deliberate, explicit narrowing.

This declaration is a SUPERSET assertion: the actual change set observed
at verification time must be CONTAINED IN the declared set, not equal to
it. A feature that produces no implement tasks generates no
`test-docs/version-bump-missing-base/` directory at all; the declared
`test-docs/version-bump-missing-base/**` entry is still correct in that case — a declared
path that never materializes is not a violation.

## Test Scenarios

テストはすべて `tests/` の unittest（標準ライブラリだけ）で、`python3 -m unittest discover -s tests` で走る。ネットワークに出ず、`~/.claude` を読まず、一時ディレクトリの中だけで git を操作する（NFR3）。

### Unit Tests
- [ ] TS-1: workflow の YAML から heredoc を抜き出す - ちょうど 1 つ抜き出せる
- [ ] TS-2: workflow と template を比べる - バイト単位で一致する
- [ ] TS-3: ルールセット定義ファイルの中身を読む - non_fast_forward のルールだけを持ち、bypass_actors が空で、enforcement が active、対象が main である

### Integration Tests
抜き出した heredoc を、一時ディレクトリの bare リポジトリと `git clone --no-local` で作った clone の上で実行する。

- [ ] TS-4: 通常: BEFORE が clone にあり、プラグイン配下が変わった push - patch が 1 上がる
- [ ] TS-5: BEFORE が bare リポジトリで到達不能（ref から外した commit）、bare 側で uploadpack.allowAnySHA1InWant を有効にする - fetch で取得でき、BEFORE を基点に比較して version を上げ、exit 0 で終わる
- [ ] TS-6: BEFORE が bare リポジトリにも無い - 第 1 親を基点にし、stdout に `::warning::` を出す
- [ ] TS-7: BEFORE が全ゼロ - 第 1 親を基点にし、`::warning::` を出す
- [ ] TS-8: BEFORE が取得できず AFTER が root commit - 非 0 で終了し、両 JSON は変わらない
- [ ] TS-9: 再現手順: 更新コミットを積んだ後、それを含まない merge commit で main を置き換え、次の push を流す - AFTER の version が基点の version より大きくなり、plugin.json と marketplace.json の値が一致する
- [ ] TS-10: 基点より AFTER の version が低い / 同じ / 高い の 3 通り - 低い・同じでは大きい方の patch を 1 上げた値が両 JSON に書かれる。高いでは version は変わらず bumped は空
- [ ] TS-11: 新規プラグイン、MAJOR.MINOR.PATCH でない version - 上げない
- [ ] TS-12: marketplace.json の version を持たないエントリ - 書き換えない
- [ ] TS-13: workflow_dispatch: 現在 <= min_version（major・minor 同じ）、現在 > min_version、未登録の plugin、形の違う min_version、現在 <= min_version で major・minor が違う - それぞれ FR4 と A2 の挙動になる（min_version の patch + 1 を両 JSON に書く / ファイルを変えず exit 0 で bumped は空 / ファイルを変えず非 0 / ファイルを変えず非 0 / ファイルを変えず非 0）
- [ ] TS-14: GITHUB_OUTPUT の bumped の値（空を含む） - 上げたプラグインの `name@version` のカンマ区切り、上げなかったときは空

### E2E Tests
**Existing E2E tests**: None
**Run command**: Not detected

### Edge Cases
- 上の TS-5〜TS-8、TS-10〜TS-13 に含む。

### Performance Tests
- 該当なし

## Security Considerations

- **Authentication:** 該当なし
- **Authorization:** workflow_dispatch は main でだけ version 更新のステップを実行する（FR4、AC-11）。ルールセットは bypass_actors を空にする（FR7）
- **Input Validation:** workflow_dispatch の plugin は marketplace.json に登録済みであること、min_version は MAJOR.MINOR.PATCH の形であることを確かめ、違えばファイルを変えずに非 0 で終了する（FR4）
- **Data Protection:** 該当なし
- **XSS Prevention:** 該当なし
- **SQL Injection Prevention:** 該当なし
- **CSRF Protection:** 該当なし

## Error Handling

### Error Codes

| Code | Description | Exit | User Message |
|------|-------------|------|--------------|
| ERR_001 | 基点を決められない（BEFORE を基点にできず、AFTER に第 1 親も無い） | 非 0 | 基点を決められない旨 |
| ERR_002 | workflow_dispatch の plugin が marketplace.json に未登録 | 非 0 | plugin が未登録の旨 |
| ERR_003 | workflow_dispatch の min_version が MAJOR.MINOR.PATCH の形でない | 非 0 | min_version の形が違う旨 |
| ERR_004 | workflow_dispatch で現在の version が min_version 以下だが major か minor が違う（A2） | 非 0 | major・minor が違う旨 |
| WARN_001 | BEFORE を基点にできず AFTER の第 1 親を基点にした | 0（続行） | `::warning::` |

### Error Flow

```
エラー条件を検出 → plugin.json と marketplace.json を変えない → 非 0 で終了
第 1 親を基点にした → ::warning:: を出す → 続行
```

## Performance Optimization

### Performance Goals
- 該当なし

### Optimization Strategies
- 該当なし

### Caching Strategy
- 該当なし

## Success Criteria

- [ ] All functional requirements are implemented and tested
- [ ] All test scenarios pass
- [ ] Security requirements are satisfied
- [ ] Documentation is complete
- [ ] Code review is completed
- [ ] `python3 -m unittest discover -s tests` が exit 0 で終わる（AC-16）
- [ ] この feature の変更で plugin.json と marketplace.json の version が変わっていない（NFR4）

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

- なし

## Assumptions

- A1: BEFORE が 40 桁 hex でないとき（形が不正）は、取得できないときと同じく第 1 親を基点にする
- A2: workflow_dispatch で現在の version が min_version 以下だが major か minor が違うときは、ファイルを変えずに非 0 で終了する
- A3: workflow_dispatch の version 更新は、push 時と同じ PR 作成・マージのステップを使う
- A4: ルールセット定義は GitHub REST API のルールセット作成ペイロードの形の JSON として `.github/` 配下に置く。置き場所とファイル名は SPEC で決める（決定は「SPEC の決定（A4・A5）」）
- A5: マージ後の人の手順の文書の置き場所は SPEC で決める（決定は「SPEC の決定（A4・A5）」）
- A6: マージ後の workflow_dispatch の入力は、plugin が em-workflow、min_version が失われた Actions 更新コミットの記録した version。この値は人の手順にだけ書き、受け入れ条件には書かない
- A7: GitHub へのルールセット適用、workflow_dispatch の実行、マーケットプレイス更新と再起動は、この実行では行わない（PR マージ後の人の手順）
- A8: plugin-dev の template を変えると plugin-dev の patch は Actions が上げる。この feature で version は手で変えない
- A9: 既存の GitHub ルールセット main（deletion / non_fast_forward / pull_request、admin の bypass は always）は変えない

## Implementation Phases (if applicable)

### Phase 1: リポジトリ内の変更
**Goals:** FR1〜FR10 をリポジトリ内で満たす
**Deliverables:**
- `.github/workflows/plugin-version-bump.yml` と `plugin-dev/skills/plugin-dev/templates/plugin-version-bump.yml`
- `.github/rulesets/main-non-fast-forward.json` と `.github/rulesets/README.md`
- `README.md` のメンテナンスの節
- `plugin-dev/skills/plugin-dev/references/create.md`
- `tests/` の unittest

### Phase 2: PR マージ後の人の手順（この実行では行わない、A7）
**Goals:** ルールセットの適用と、失われた em-workflow の version 更新の回復
**Deliverables:**
- ルールセットの作成と確認（FR8 (a)）
- workflow_dispatch の 1 回の実行と確認（FR8 (b)）
- マーケットプレイスの更新と Claude Code の再起動による、キャッシュへの反映の確認（FR8 (c)）

## References

- 要件定義書: `feature-docs/version-bump-missing-base/REQUIREMENTS.md`
