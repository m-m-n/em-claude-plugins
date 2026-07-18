# License Compatibility (em-workflow SSOT)

Shared knowledge for three consumers: the implementation-planner (library-
selection constraint), the `review-license` perspective skill, and the
`/em-workflow:gen-license` procedure (`references/gen-license.md`). This file
states WHAT is compatible; each consumer defines its own process.

## Project license detection

- Look for `LICENSE`, `LICENSE.md`, `LICENSE.txt`, `COPYING` at the project
  root. Identify the SPDX id from the text (title line + distinctive
  phrases). Common ids: `MIT`, `Apache-2.0`, `BSD-2-Clause`, `BSD-3-Clause`,
  `ISC`, `MPL-2.0`, `LGPL-2.1-only`/`-or-later`, `LGPL-3.0-only`,
  `GPL-2.0-only`/`-or-later`, `GPL-3.0-only`, `AGPL-3.0-only`,
  `Unlicense`, `CC0-1.0`.
- No file → `none`. Text present but not identifiable → treat as `unknown`
  and ask the user instead of guessing.

## Dependency-license categories

- **Permissive**: MIT, BSD-2-Clause, BSD-3-Clause, ISC, Zlib, Unlicense,
  CC0-1.0, Apache-2.0 (see caveat below).
- **Weak copyleft** (scope limited to the library/files themselves):
  MPL-2.0, LGPL-2.1, LGPL-3.0.
- **Strong copyleft** (combined distributed work must follow): GPL-2.0,
  GPL-3.0.
- **Network copyleft** (network use counts as distribution): AGPL-3.0.

## Can a project under license P depend on a library under license L?

The question is directional: what does DISTRIBUTING the combined work under
P require of L?

1. **Permissive L** → compatible with any P. Keep the library's copyright
   notice (all of them require attribution).
2. **Apache-2.0 L** → compatible with any P EXCEPT `GPL-2.0-only` projects
   (patent-clause incompatibility; `GPL-2.0-or-later` and GPL-3.0 projects
   are fine).
3. **MPL-2.0 L** → compatible with any P when the library is used as-is;
   modifications to the MPL-covered files themselves must remain MPL-2.0.
4. **LGPL L** → compatible when the library remains replaceable (dynamic
   linking). In static-linking ecosystems (Go, Rust, single-binary deploys)
   the relink-ability condition is hard to satisfy — flag for explicit user
   confirmation instead of auto-approving.
5. **GPL L** → the combined distributed work must be GPL: incompatible with
   any non-GPL P. Within the family: `GPL-2.0-only` L is incompatible with a
   GPL-3.0 project (and vice versa); `GPL-2.0-or-later` L is compatible with
   GPL-3.0.
6. **AGPL L** → like GPL, and network service use also triggers the
   obligation. Incompatible with any non-AGPL P.
7. **Unknown / proprietary / no license** → not usable without
   investigation. "No license" means all rights reserved, not public domain.
8. **Dual-licensed L** → choose the compatible option and record WHICH one
   was chosen.
9. **Dev-only dependencies** (build/test tooling not distributed with the
   artifact) generally do not constrain P — flag only when the tool embeds
   its own code into the shipped output.

`project.license: none` (no LICENSE file yet): there is no constraint to
violate, but strong/network-copyleft and unknown-license additions still
deserve a note — they narrow the future license choice.

## Conflict resolution vocabulary (shared by all consumers)

- **replace**: 互換ライセンスの別ライブラリへ差し替える
- **relicense**: プロジェクトのライセンスを依存に合わせて変更する
  （LICENSE の再生成は `/em-workflow:gen-license`、workflow 進行中は
  workflow.yaml `project.license` の更新も伴う）
- **isolate**: プロセス分離等で結合を断つ（上級。自動判断せず、必ず
  ユーザー判断に委ねる）

Beyond this table, do not improvise legal verdicts — recommend human/legal
review for anything genuinely ambiguous.
