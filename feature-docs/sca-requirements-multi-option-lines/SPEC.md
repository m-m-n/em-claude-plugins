# Feature: sca-requirements-multi-option-lines

## Overview

requirements ファイルの 1 行に複数のオプションがあるとき、行内のどの位置にある `-r` の参照先も辿り、そこで宣言したパッケージを直接依存として数える。オプション行は shlex.split で分割し、`-r` / `-c` / `-e` とその長い形式、および長いオプションの省略形を位置に関係なく扱う。オプション行を解釈できないときは集合を `complete=False` にし、既存の `pip_directness_undetermined` ノートで報告する。UI は無い。

## Objectives

- requirements ファイルの 1 行に複数のオプションがあっても、`-r` の参照先で宣言したパッケージを直接依存として数える。
- `-r` の参照先で宣言した直接依存の high / critical の advisory を、推移的依存として黙って捨てない。
- THREAT-MODEL の TB-1 / TM-5 が防ぐ経路の抜けを塞ぐ。

## User Stories

requirements_analysis にユーザーストーリーは無い。受け入れ条件を以下に示す。

### Acceptance Criteria

- [ ] **AC1:** requirements.txt が `-c constraints.txt -r deps.txt` の 1 行だけで、deps.txt が vuln-pkg を宣言している。直接依存の集合は {vuln-pkg} で `complete=True` になる。vuln-pkg の high の advisory はちょうど 1 件の finding になり、判定不能のノートは出ない。constraints.txt は開かない。
- [ ] **AC2:** `--index-url https://x/simple -r deps.txt` は AC1 と同じ結果になり、ネットワーク接続は発生しない。
- [ ] **AC3:** 1 行の `-r a.txt -r b.txt` では、a.txt と b.txt の両方の名前が直接依存になる。`-c c.txt --requirement=b.txt`、`-c c.txt -rb.txt`、`--index-url URL --requirement b.txt` の形式でも参照先を辿る。
- [ ] **AC4:** 分割できないオプション行（例: `-c a -r "deps.txt`）は `complete=False` になる。宣言されていない high の advisory は pip の判定不能として 1 件数えられる。例外は発生しない。
- [ ] **AC5:** 値の無い `--index-url URL -r` は `complete=False` になる。
- [ ] **AC6:** 行の途中にある include にも封じ込めが効く。`-c a -r ../outside/x.txt` は開かず、集合は不完全になる。`--index-url URL -r https://...` は取得せず、集合は不完全になる。
- [ ] **AC7:** 行頭以外の `-e` を読む。`-c a -e ./pkg` や `--index-url URL -e git+https://...` で名前が得られない場合、集合は `complete=False` になる。`--index-url URL --editable=<名前のある値>` で名前が得られた場合、その名前は直接依存になる。
- [ ] **AC8:** 長いオプションの省略形は `complete=False` になる（例: `--requirem deps.txt`、`--requirem=deps.txt`、`-c a --editab ./pkg`）。deps.txt は開かない。
- [ ] **AC9:** `python3 -m unittest discover -s tests` と `python3 em-workflow/scripts/check-plugin-invariants.py .` の両方が通る。

## Technical Requirements

### Functional Requirements

- **FR1:** 行内の位置に関係なく `-r` を辿る — `-` で始まる論理行を shlex.split（POSIX モード）でトークンに分割する。行内のどの位置にあっても `-r X`、`-rX`、`--requirement X`、`--requirement=X` を include として扱う。include は既存の規則で辿る: パスは include 元のファイルからの相対で解決する、参照先はプロジェクトルート内に限る、URL は取得しない、各ファイルは高々 1 回だけ開く。1 行に複数の include があれば、すべて辿る。オプションの値は直後のトークンをそのまま使う。
- **FR2:** 同じ行の制約 — `-c` / `--constraint` は、どの形式・どの位置でも参照先を開かず、集合を不完全にしない。同じ行に `-r` があっても同じ扱いにする。
- **FR3:** 分割に失敗したら不完全にする — shlex がオプション行を分割できない場合（閉じていない引用符、末尾のエスケープなど）、その行からは何も取らず、集合を `complete=False` にする。他の行・他のファイルは引き続き読む。例外を外に出さない。
- **FR4:** 値の無い `-r` — 行末にあって値の無い `-r` / `--requirement`、または空の `--requirement=` は、既存の規則と同じく集合を `complete=False` にする。
- **FR5:** 任意の位置の `-e` / `--editable` — オプション行のどの位置にあっても `-e X`、`-eX`、`--editable X`、`--editable=X` を読む。値は次のトークン、または連結部分 / `=` の後ろの部分とする。`_requirement_name` が名前を返したら、その名前を直接依存とする。名前が得られない、または値が無い場合は集合を `complete=False` にする。行頭の `-e` も同じトークン規則を使うため、値は「行の残り全体」から「次のトークン」に変わる。
- **FR6:** 長いオプションの省略形は不完全にする — `--` で始まるトークンは `=` より前の部分を取り出す。その部分が `--requirement` または `--editable` の真の接頭辞で、かつ `--` より長い場合、集合を `complete=False` にする。値は解釈せず、ファイルも開かない。`--re` や `--e` のような曖昧な接頭辞も同じ扱いにする。単独の `--` は省略形とみなさず、無視する。
- **FR7:** その他のオプション行 — FR1・FR2・FR5・FR6 のいずれの形式も含まないオプション行は、`--index-url` や `--hash=` を含め、従来どおり無視する。完全性は変えない。未知のオプショントークンも無視する。
- **FR8:** 判定不能の報告 — 不完全な集合は、既存の `pip_directness_undetermined` ノートだけで報告する。報告するのは、宣言名に一致しなかった advisory のうち、閾値以上または重大度不明のものの件数とする。新しいノートのトークンは追加しない。

### Non-Functional Requirements

- **NFR1 - 標準ライブラリのみ:** 標準ライブラリだけを使う。shlex は標準ライブラリなので、TestStandardLibraryOnly は引き続き通る。
- **NFR2 - 例外を出さない:** リゾルバは例外を送出しない。分割の失敗も含む（TM-4）。
- **NFR3 - 封じ込め:** ルート外のファイルを開かず、URL を取得しない（TM-1 / TM-2）。行の途中の include、`-e`、省略形のトークンも対象に含む。
- **NFR4 - サマリーの内容:** サマリーのノートは固定トークンと件数だけで組み立てる。shlex のエラー文、行の内容、パス名は含めない（TM-6）。
- **NFR5 - 既存テスト:** `tests/test_scan_dependencies_pip_directness.py` の既存テストは、変更なしですべて通る。
- **NFR6 - バージョン:** em-workflow の version を変えない。

## Implementation Approach

### Architecture

**Component Diagram:**
```
requirements ファイル
  └─ 論理行
       ├─ `-` で始まらない行 → 従来どおりの処理（A5）
       └─ `-` で始まるオプション行
            └─ shlex.split（POSIX モード）
                 ├─ 失敗 → その行から何も取らない / complete=False（FR3）
                 └─ トークン列を走査
                      ├─ -r / --requirement 系 → include を辿る（FR1）/ 値なし → complete=False（FR4）
                      ├─ -c / --constraint 系  → 開かない / 完全性を変えない（FR2）
                      ├─ -e / --editable 系    → _requirement_name で名前を得る（FR5）
                      ├─ --requirement / --editable の省略形 → complete=False（FR6）
                      └─ その他のトークン      → 無視（FR7）
```

### Data Flow

```
requirements ファイル → オプション行の解析 → 直接依存の名前の集合 + complete
                                          ↓
pip-audit の advisory → 宣言名との照合 → finding / pip_directness_undetermined の件数（FR8）
```

### Dependencies

**Internal Dependencies:**
- 既存の include の規則: 相対パスの解決、プロジェクトルート内への封じ込め、URL を取得しないこと、各ファイルを高々 1 回だけ開くこと（FR1）。
- `_requirement_name`: `-e` / `--editable` の値から名前を得る（FR5）。
- `pip_directness_undetermined` ノート: 判定不能の報告（FR8）。

**External Dependencies:**
- shlex（Python 標準ライブラリ）: オプション行の分割（NFR1）。

### File Structure

```
em-workflow/scripts/scan-dependencies.py          # requirements のオプション行の解析
tests/test_scan_dependencies_pip_directness.py    # 既存テスト（変更なしで通る）
```

## Declared Change Set

このセクションは手書きのリストではなく、create-plan での導出を記す。上記の機能固有のパスは、create-plan で `workflow.yaml` の各タスクの `files` エントリから導出する（`references/phases/create-plan-phase.md`）。

すべての SPEC は、上記の機能固有のパスに加えて、ワークフローが生成する次の 2 つのエントリを既定で宣言する。

- `feature-docs/sca-requirements-multi-option-lines/**`
- `test-docs/sca-requirements-multi-option-lines/**`

`feature-docs/sca-requirements-multi-option-lines/**` は `REQUIREMENTS.md`、`SPEC.md`、`IMPLEMENTATION.md`、`workflow.yaml`、`phase-state/`、`tasks/`、`reviews/roundN.yaml`、`VERIFICATION.md`、`retrospect.yaml`、および design ステップが生成する成果物を含む。これらはフェーズ文書と `references/phase-state.md` が生成・所有する。このセクションはそれらを参照するだけで、規則は再掲しない。

`test-docs/sca-requirements-multi-option-lines/**` はタスクごとのテスト記録 `test-docs/sca-requirements-multi-option-lines/{T}.tests.yaml` を含む。これは `implement-phase.md` が生成・所有する。このセクションはそれを参照するだけで、規則は再掲しない。

この 2 つの既定エントリは、SPEC の作成者が明示的に外さない限り宣言に含まれる。記載が無いことをもって外したとはみなさない。外す場合は、意図した明示的な絞り込みとして行う。

この宣言は上位集合としての主張である。検証時に観測される実際の変更集合は、宣言した集合に含まれていればよく、一致する必要はない。implement タスクを生成しない機能では `test-docs/sca-requirements-multi-option-lines/` ディレクトリ自体が生成されないが、宣言した `test-docs/sca-requirements-multi-option-lines/**` のエントリはその場合も正しい。宣言したパスが実在しないことは違反ではない。

## Test Scenarios

### Unit Tests

- [ ] **TS1**（AC1）: `-c constraints.txt -r deps.txt` について、リゾルバの結果（名前 / complete）を確認し、OpenRecorder が constraints.txt を一度も開いていないことを確認し、pip-audit の代替を通したスキャン全体（finding 1 件、判定不能のノートなし）を確認する。
- [ ] **TS2**（AC2）: `--index-url https://x/simple -r deps.txt` について、TS1 と同じ確認に加え、NetworkGuard が接続の試行を記録していないことを確認する。
- [ ] **TS3**（AC3）: 1 行に複数の `-r` トークンがある場合と、各形式の組み合わせを subTest として書く。
- [ ] **TS4**（AC4）: 分割できない行（閉じていない引用符、末尾のエスケープ）で、`complete=False`、判定不能の advisory が 1 件、例外なしになる。
- [ ] **TS5**（AC5）: 値の無い `--index-url URL -r` で `complete=False` になる。
- [ ] **TS6**（AC6）: `..`、絶対パス、URL を使う行の途中の include で、OpenRecorder / NetworkGuard がファイルを開いていないこと・ネットワークにアクセスしていないことを示し、`complete=False` になる。
- [ ] **TS7**（AC7）: 行頭以外の `-e` / `--editable` / `--editable=` を、名前の無い値と名前のある値の 2 通りで試し、complete と名前を確認する。
- [ ] **TS8**（AC8）: `--requirement` と `--editable` の省略形を、空白区切りと `=` の両方で書き、`complete=False` になり参照先が一度も開かれないことを確認する。

### Integration Tests

- [ ] **TS9**（AC9）: 既存のスイート（`python3 -m unittest discover -s tests`）とプラグインの不変条件チェック（`python3 em-workflow/scripts/check-plugin-invariants.py .`）を実行する。

### E2E Tests

**Existing E2E tests**: なし
**Run command**: 検出なし

### Edge Cases

- [ ] 1 行に複数の include: すべて辿る（FR1）。
- [ ] 同じ行の `-c` と `-r`: `-r` は辿り、`-c` の参照先は開かない（FR2）。
- [ ] 閉じていない引用符・末尾のエスケープ: その行から何も取らず `complete=False`、例外なし（FR3）。
- [ ] 行末の値の無い `-r` / `--requirement`、空の `--requirement=`: `complete=False`（FR4）。
- [ ] 行頭の `-e`: 値は次のトークン（FR5）。
- [ ] `--re`・`--e` のような曖昧な接頭辞: `complete=False`（FR6）。
- [ ] 単独の `--`: 省略形とみなさず無視する（FR6）。
- [ ] `--index-url`・`--hash=`・未知のオプショントークンだけの行: 無視し、完全性を変えない（FR7）。

## Security Considerations

- **Input Validation:** オプション行は shlex.split で分割し、分割できない行からは何も取らず `complete=False` にする（FR3）。`--requirement` / `--editable` の省略形は値を解釈せず `complete=False` にする（FR6）。
- **ファイルアクセスの封じ込め:** 行の途中の include、`-e`、省略形のトークンも含め、ルート外のファイルを開かない（NFR3、TM-1）。
- **ネットワーク:** URL を取得しない（NFR3、TM-2）。
- **出力:** サマリーのノートは固定トークンと件数だけで組み立て、shlex のエラー文・行の内容・パス名を含めない（NFR4、TM-6）。

## Error Handling

### Error Flow

```
shlex.split の失敗 → その行から何も取らない → complete=False → pip_directness_undetermined の件数で報告
値の無い -r / 空の --requirement= → complete=False
名前の得られない -e / 値の無い -e → complete=False
--requirement / --editable の省略形 → complete=False（値を解釈せず、ファイルも開かない）
```

- リゾルバは例外を外に出さない（FR3、NFR2）。
- 報告は既存の `pip_directness_undetermined` ノートだけで行い、新しいノートのトークンは追加しない（FR8）。

## Assumptions

- **A1:** 1 行に複数の `-r` があれば、すべて辿る。`-c` と `-r` が同じ行にあれば、`-r` は辿り、`-c` の参照先は開かない。行に `-e` があっても、その行の `-r` は辿る。pip が実際に読む範囲より多く辿ることがあるが、余分に辿っても直接依存が増えるだけで、advisory が捨てられることはない。
- **A2:** 分割には POSIX モードの shlex.split を使う。オプションの値は次のトークンをそのまま使う。
- **A3:** 未知のオプショントークンは無視し、集合を不完全にしない。
- **A4:** 既存の `pip_directness_undetermined` ノートだけを使う。例外の文言と行の内容はサマリーに書かない。
- **A5:** 要件名で始まる行（`-` で始まらない行）は従来どおりに扱う。
- **A6:** em-workflow の version は変えない。
- **A7:** 行頭以外の `-e` / `--editable` の値は `-r` と同じ方法で読む（FR5）。
- **A8:** `--requirement` / `--editable` の長いオプションの省略形は集合を不完全にし、スキャナは解決を試みない（FR6）。

## Success Criteria

- [ ] FR1〜FR8 が実装され、テストされている
- [ ] NFR1〜NFR6 を満たす
- [ ] TS1〜TS9 がすべて通る
- [ ] AC1〜AC9 をすべて満たす

## Open Questions

> **Note**: 未解決の要件は workflow.yaml で `status: tbd` として管理されています。
> plan フェーズの実行前に解決してください。

なし

## References

- 該当箇所: `em-workflow/scripts/scan-dependencies.py`（`_requirements_option` と `_pip_requirements_direct_names`）
- 既存テスト: `tests/test_scan_dependencies_pip_directness.py`
- THREAT-MODEL: TB-1、TM-1、TM-2、TM-4、TM-5、TM-6
