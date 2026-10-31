# DEV-USDJPY-SIMPLE-02 — Freeze Candidate(DRAFT V0.1)

- 状態: **FREEZE CANDIDATE V0.1(Claude、2026-11-01)**。むすびさんの Freeze 前監査待ち。**Freeze ではない。preflight・Development・Forward の承認でもない。**
- 02 の Freeze Candidate V0(V1 commit 699b0b3e)は**変更せず残す**。V0.1 は、純さんの 2026-11-01 07:19 JST の指示の 7 項目を明示し、Freeze の前に取れる証拠を記録した版。
- 付属: `drafts/DEV-USDJPY-SIMPLE-02-FREEZE-CANDIDATE-V0.1.freeze.candidate.json`(freeze.json の案)。台帳の行の案は V0 の `…-V0.registry.candidate.csv` をそのまま使う(変更なし)。
- この版では `preregistration/` に何も書かない。データを読まない。何も実行しない(下の検査は合成データだけ、または API の読み取りだけ)。

## 1. 01 → 02 の継承の関係

- DEV-USDJPY-SIMPLE-01 は **ABORT 済み**。Event_Seq 1 の FREEZE(Freeze commit d00e348d、registry commit cb276490)は**有効な履歴として維持**し、Event_Seq 2 に ABORT を記録済み(commit 853e7509)。
- 02 は 01 の科学の設計を変えない。01 で判明した workflow の YAML の不備を直した**後継の Trial** である。

## 2. 科学の仕様の継承

- 02 は、01 の SPEC v0.3 と FREEZE-PREP v0.1 を**そのまま継承**する。scientific spec、model、estimator、Gate、statistics、parameters は変えていない。
- 継承元は、01 の名前を含む凍結済みのファイル(写しは作らない):

| 文書 | path | 凍結の commit | blob | SHA-256 |
|---|---|---|---|---|
| SPEC v0.3 | `preregistration/DEV-USDJPY-SIMPLE-01-SPEC-V0.3.md` | d00e348d | 647fcc19fd1c8624bee0fed369bab07b53de237f | `13e7e3306050d39e47cd669a075f3aaa1caf15e33619894885a70f5f5a191bab` |
| FREEZE-PREP v0.1 | `preregistration/DEV-USDJPY-SIMPLE-01-FREEZE-PREP-V0.1.md` | d00e348d | bb3617b8a2f7eb0481d95d5d98f53d134b8e2fa4 | `b6f545de900a5bc03c630b8b109dec2d789bd860b2af837eb6b7935949d2a917` |
| 01 の freeze.json(Trial に依存しない部分の出所) | `preregistration/DEV-USDJPY-SIMPLE-01.freeze.json` | d00e348d | 242ef882f46742345284b5b10674f94468ac532d | `ae552e73f26d406c804c7bcf0ab215bf1e91cebc291ce3ece2e28f4db7368c31` |

- 読み替えの規則: 文書の中の `DEV-USDJPY-SIMPLE-01` は、Trial_ID・trial の directory・AUTHORIZATION.json の path・成果物の名前・records の path・実行の branch についてだけ `DEV-USDJPY-SIMPLE-02` と読む。ほかは何も読み替えない。

## 3. Implementation

- commit **2212653b9602cfea32f23ea28b2aa5aeb3214ec2**、tree **8ed09862631203ac4787f330b02619a5fd04b220**(27 ファイル。JSON に全件の blob・SHA-256)。DIFFERENTIAL AUDIT PASS(むすびさん)。
- `supersedes` の項目は残す(むすびさん: provenance として残してよい)。
- 01(a7921007)からの変更の範囲は次に限られる(JSON `supersedes.change_scope_01_to_02`):
  1. YAML の quoting の修正(pip install の `run:` の値を二重引用符で囲む。命令は同一)
  2. YAML の回帰の検査の追加(`tests/test_workflow_yaml.py`)
  3. Trial ID・path などの機械的な変更、と provenance の `supersedes`
- config.json の 01 との違いは `trial_id`・`authorization_file`・`supersedes` だけ(Claude の機械的な比較)。

## 4. 01 の workflow の事故

- 01 では、凍結した workflow が YAML として GitHub Actions に読み込まれず、**preflight は開始されなかった**。jobs = 0、artifacts = 0(run 41190736222・41108650695。むすびさんが独立確認)。**snapshot は読まれていない**。performance information: **NO EVIDENCE OF OBSERVATION**。
- 02 では、問題の pip の `run:` の scalar を quote し、回帰の検査を加えた。

## 5. Registry_Count_At_Design

- **今は値を推測・固定しない。** 02 の Freeze の commit A の直前に、凍結済みの数え方(`Registry_Event = FREEZE` かつ `Research_Question_ID = USDJPY-1D-PRICE-ONLY-LOCATION` の相異なる Trial_ID の数)で機械的に測り、同じ Research_Question_ID の全 event の一覧と、`preregistration/`・`drafts/` の grep の結果と一緒に、実測の値と証拠を commit B の message と台帳の行に記録する。予想外の結果なら何も commit せずに止まる。
- **測定の前の状態(参考。値ではない)**: V1 main 07ad276e の `preregistration/DEV-TRIAL-REGISTRY.csv`(blob 785bec42、SHA-256 3fe84043…)には次の 2 つの event がある。
  - 1: DEV-USDJPY-SIMPLE-01 FREEZE(2026-10-31T04:14:00+09:00)
  - 2: DEV-USDJPY-SIMPLE-01 ABORT(2026-10-31T19:03:32+09:00)
- 699b0b3e の後、V1 の `preregistration/`・`drafts/` に変更はない(bot の定期の commit だけ)。

## 6. workflow の有効性

「push の後に failed run が出なかった」ことは**主な証拠にしない**。

| 検証 | 結果(2026-10-31T22:19Z、Claude の実行) |
|---|---|
| 静的な parse(PyYAML 6.0.3)、02 の workflow(blob 2da72acd、SHA-256 1eca40d5…) | **parse OK**。triggers = `workflow_dispatch` だけ、jobs = `trial` |
| 対照: 01 の workflow(a7921007) | parse ERROR `mapping values are not allowed here`、line 26、column 71 |
| 回帰の検査 `tests/test_workflow_yaml.py` | 01 の workflow では失敗(構造の検査 FAIL、parse ERROR)、02 では通過 |
| GitHub の認識(実行なし、`GET /actions/workflows`) | **まだ確認できない**。既定の branch が `impl/dev-usdjpy-simple-01` のままで、name は path のまま(`.github/workflows/dev-trial.yml`)= GitHub は 01 の壊れたファイルを読んでいる |

- **F-02-1(未解決)**: GitHub が 02 の workflow を認識していることを実行なしで示すには、既定の branch を `impl/dev-usdjpy-simple-02` に変える必要がある(repository の設定。tree は変わらない。純さんの作業)。変更の後に `GET /actions/workflows` の name が `dev-trial` になることを確かめ、Freeze の記録に書く。
- 静的な parse は Freeze の時に同じ blob で取り直して記録する。
- 実際の preflight は実行しない。

## 7. テストの結果の扱い

- 「44 tests pass」は **Claude の実行の結果**(2212653b、`python devtrial/run.py selftest`、合成データだけ、Python 3.13.17・numpy 2.5.3(手元、hash の照合なし)・PyYAML 6.0.3、2026-10-31T22:19Z)。**むすびさんが独立に実行したものではない。**

## 8. 未解決(V0 から引き継ぎ)

- F-02-1: 既定の branch の変更と、実行しない認識の確認(§6)
- F-02-2: 01 の PRE-FLIGHT BOUNDARY RULING(ce89162c)を 02 に参照で適用するか、新しい ruling の文書を作るか
- F-02-3: Registry_Count_At_Design の Freeze の時の実測(§5)

## 9. 状態

- DEV-USDJPY-SIMPLE-01 = FREEZE(履歴)/ ABORT
- DEV-USDJPY-SIMPLE-02 = 実装 DIFFERENTIAL AUDIT PASS / Freeze Candidate V0.1 = DRAFT / NOT FROZEN
- preflight・Development・Forward = NOT AUTHORIZED、Holdout = SEALED
