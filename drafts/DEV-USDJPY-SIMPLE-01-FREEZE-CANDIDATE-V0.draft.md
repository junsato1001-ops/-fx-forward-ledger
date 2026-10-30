# DEV-USDJPY-SIMPLE-01 — Freeze Candidate(DRAFT V0)

- 状態: **FREEZE CANDIDATE V0(Claude、2026-10-31)**。むすびさんの Freeze 内容の最終監査待ち。**Freeze ではない。preflight・Development の実行の承認でもない。**
- 前提: Implementation Candidate v0.1 `7ad94415bbf21a69523307a1bb4bcf47925763d8` = IMPLEMENTATION AUDIT PASS(むすび、純さん経由 2026-10-31 03:25 JST)。この候補は**その commit を変更しない**。
- 付属のファイル(どちらも案):
  - `drafts/DEV-USDJPY-SIMPLE-01-FREEZE-CANDIDATE-V0.freeze.candidate.json` — Freeze の記録(freeze.json)の案
  - `drafts/DEV-USDJPY-SIMPLE-01-FREEZE-CANDIDATE-V0.registry.candidate.csv` — 台帳の行の案(DEV-TRIAL-REGISTRY の新設 + FREEZE の event、registry.csv の 1 行)
- この版では V1 の `preregistration/` に何も書かない。データを読まない。何も実行しない。

## 1. Freeze で固定するもの

| 対象 | 識別子 | 状態 |
|---|---|---|
| 仕様 SPEC v0.3 | blob 647fcc19、SHA-256 13e7e330…(commit 17cc7c6d) | むすび差分監査 PASS |
| Freeze 前パッケージ v0.1 | blob bb3617b8、SHA-256 b6f545de…(commit fb4381e7) | **監査結果の記録を確認したい(F-FC-3)** |
| 実装 | `-fx-dev-trials` commit 7ad94415、tree deb2d0c0、25 ファイル(blob・SHA-256 は JSON 案に全件) | Implementation Audit PASS |
| スナップショット | SHA-256 f36e0aff…、blob 88b4dcdb | 実装の中に同一の写し |
| 数値のパラメータ | config.json(blob 590bae41)の値 | 実装の一部として固定 |
| 報告だけの境界 | 方向の診断 3 指標を含む(むすびさんの 2026-10-31 の文言を記録に入れた) | — |

SHA-256 はすべて Claude の申告値として記録する(むすびさんが再計算した値は区別して書く)。

## 2. Freeze の手順(純さんの決定の後に行う。案)

1. V1 commit A: 次の 3 ファイルを `preregistration/` に追加する。
   - `DEV-USDJPY-SIMPLE-01-SPEC-V0.3.md`(draft のバイトの写し。blob 647fcc19 と一致すること)
   - `DEV-USDJPY-SIMPLE-01-FREEZE-PREP-V0.1.md`(draft のバイトの写し。blob bb3617b8 と一致すること)
   - `DEV-USDJPY-SIMPLE-01.freeze.json`(JSON 案の `<...>` を埋め、`status_of_this_file` を除いたもの)
2. V1 commit B: `preregistration/registry.csv` に 1 行を追記し、`preregistration/DEV-TRIAL-REGISTRY.csv` を新設して FREEZE の event の行を書く(Freeze_Commit = commit A)。これまでの Freeze と同じ 2 commit の形。
3. `-fx-dev-trials` は Freeze で**何も変えない**。実装は commit の hash と tree の hash で固定する。
4. `AUTHORIZATION.json` は Freeze では作らない。

## 3. Freeze の後の実行の規則(記録に入れる。案)

- 順番: Freeze → preflight の別の承認 → preflight → Development の本実行の別の承認 → 本実行。
- **実行の commit の規則**: 実行の commit は実装の commit 7ad94415 の子孫で、tree deb2d0c0 との違いが `trials/DEV-USDJPY-SIMPLE-01/AUTHORIZATION.json` の追加・変更だけであること。ほかに違いがあれば、この Trial ではない(ABORT の event と新しい Trial_ID)。実行は別の branch(案: `exec/dev-usdjpy-simple-01`)で行い、`impl/dev-usdjpy-simple-01` は動かさない。
- `AUTHORIZATION.json` の項目(run.py が要求する): `trial_id`、`modes`、`freeze_commit`(= V1 commit A)、`authorized_by`、`authorized_at_jst`。preflight の承認では `modes = ["preflight"]` だけ。

## 4. Freeze の前に決めたい未解決の点

### F-FC-1(Claude の自己申告): 実行の環境の固定が Freeze 前パッケージ §3.5 に足りない

- §3.5 は「Python 3(版を固定)」「外部の package を使うなら版と hash を固定する」と書いている。
- 監査 PASS の実装の workflow は、`python-version: "3.13"`(patch の版なし)、`pip install numpy==2.5.3`(**hash なし**)、`actions/checkout@v4`・`actions/setup-python@v5`・`actions/upload-artifact@v4`(tag で、commit の hash ではない)。
- このセッションからは PyPI に届かないので、numpy の wheel の hash をここで取れない。
- 選択肢:
  - **(A)** 実装を直す(推奨): `requirements.txt` に `numpy==2.5.3 --hash=sha256:…` を置いて `pip install --require-hashes`、Python の patch の版を固定、actions を commit の hash で固定し、実行時に版と wheel の hash を provenance に書く。**実装の変更なので新しい commit になり、むすびさんの差分監査が要る。** Freeze はその commit を対象にする。hash は純さん・むすびさんが pypi.org で確かめた値を使うか、synthetic だけの `selftest` を 1 回 workflow で動かして取る(この dispatch にも承認が要る)。
  - **(B)** 7ad94415 のまま Freeze し、「版の固定だけで hash の固定はない」という逸脱を記録に明記する。provenance には numpy・Python の版だけが残る。
- Development の結果を見る前に決める必要がある(結果を見てから環境の差を言い訳にできないようにするため)。

### F-FC-2(Claude の自己申告): 結果の artifact の保存先が決まっていない

- 現在の workflow は結果を GitHub Actions の artifact として upload するだけで、repository に commit しない。Actions の artifact は保存期限で消える(既定 90 日)。`.gitignore` は `trials/*/results/` を除外している。
- 案: 実行の後、Claude が artifact を取得し、SHA-256 を照合してから、`-fx-dev-trials` の別の場所(案: `records/DEV-USDJPY-SIMPLE-01/`)に commit する。台帳の PREFLIGHT・EXECUTION_RESULT の event に、artifact の SHA-256、run の ID、保存の commit を書く。
- これは実装のコードを変えずにできる(保存の commit は実行の commit とは別。§3 の実行の commit の規則の対象外とすることを記録に書く)。

### F-FC-3: Freeze 前パッケージ v0.1 の監査の結果

- このセッションの記録から、v0.1 に対するむすびさんの判定の文言を確かめられなかった(v0 は REVISE MINOR)。実装はこの v0.1 に従って作り、Implementation Audit で PASS になっている。Freeze の記録の `freeze_prep.audit` に書く判定を確かめていただきたい。

### F-FC-4: `main` の branch

- `-fx-dev-trials` には `main` がなく、`impl/dev-usdjpy-simple-01` が既定の branch になっている。workflow_dispatch は既定の branch にある workflow を使い、実行は任意の branch で指定できるので、Freeze にも実行にも `main` は要らない。
- 案: `main` は作らない(Freeze の対象は commit の hash)。作る場合は、7ad94415 を指すだけにするかどうかを別に決める。

## 5. むすびさんに確かめていただきたいこと

1. JSON 案の内容(特に `execution_commit_rule`、`report_only_boundary`、`frozen_parameters`)。
2. F-FC-1 の (A)・(B) のどちらにするか。
3. F-FC-2 の保存の案。
4. F-FC-3 の判定の文言。
5. 台帳の `Research_Question_ID = USDJPY-1D-PRICE-ONLY-LOCATION`、`Registry_Count_At_Design = 0`。

## 6. 状態

- DEV-USDJPY-SIMPLE-01: SPEC v0.3 = PASS / NOT FROZEN、実装 7ad94415 = IMPLEMENTATION AUDIT PASS、Freeze Candidate V0 = DRAFT
- preflight = NOT AUTHORIZED、Development = NOT STARTED、Forward = NOT AUTHORIZED
- V1 = 変更なし(この版は `drafts/` だけ)、V1 Development Replay = NOT STARTED
- Historical Reserve Holdout = SEALED
