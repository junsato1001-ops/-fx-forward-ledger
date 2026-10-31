# DEV-USDJPY-SIMPLE-02 — Freeze Candidate(DRAFT V0)

- 状態: **FREEZE CANDIDATE V0(Claude、2026-10-31)**。むすびさんの Freeze 前監査待ち。**Freeze ではない。preflight・Development の承認でもない。**
- 付属のファイル(どちらも案):
  - `drafts/DEV-USDJPY-SIMPLE-02-FREEZE-CANDIDATE-V0.freeze.candidate.json` — `preregistration/DEV-USDJPY-SIMPLE-02.freeze.json` の案(実装の 27 ファイルの blob・SHA-256 を含む)
  - `drafts/DEV-USDJPY-SIMPLE-02-FREEZE-CANDIDATE-V0.registry.candidate.csv` — 台帳の行の案
- この版では `preregistration/` に何も書かない。データを読まない。何も実行しない。

## 1. 01 の ABORT と 02 の関係

| 項目 | 内容 |
|---|---|
| 01 の Freeze | commit d00e348d(記録)、cb276490(台帳 Event_Seq 1)。**有効な履歴としてそのまま残す** |
| 01 の ABORT | 台帳 Event_Seq 2(commit 853e7509)。むすびさんの判定(2026-10-31 19:02 JST)、救済の案 A |
| 事故 | 01 の凍結実装 a7921007 の workflow の 26 行目が YAML として不正(plain scalar の中の `:all: `。01 の実装 v0.2 で Claude が入れ、文字列だけの静的検査で見逃した)。GitHub が workflow を読めず、dispatch は HTTP 422、push の run 41190736222・41108650695 は jobs = 0・artifacts = 0。preflight は始まらず、snapshot は読まれず、成績の情報の観測の証拠はない |
| 02 の修正 | pip install の `run:` の値を二重引用符で囲む(命令は同一)、YAML の回帰の検査 `tests/test_workflow_yaml.py`、Trial ID の機械的な変更、config.json の `supersedes`(むすびさん: 残してよい) |
| 02 の監査 | 実装 2212653b = DIFFERENTIAL AUDIT PASS(むすびさん、2026-10-31 19:07 JST) |
| 科学の内容 | 01 と同一(SPEC v0.3、FREEZE-PREP v0.1、モデル、推定、Gate、統計、パラメータ、snapshot、vendor、runtime の固定)。config.json の 01 との違いは `trial_id`・`authorization_file`・`supersedes` だけ(Claude の機械的な比較) |

## 2. 継承する凍結の仕様

- SPEC v0.3 と FREEZE-PREP v0.1 は、d00e348d で凍結済みの `preregistration/DEV-USDJPY-SIMPLE-01-SPEC-V0.3.md`(blob 647fcc19)と `…-FREEZE-PREP-V0.1.md`(blob bb3617b8)を**参照で継承する。写しを新しく作らない。**
- 読み替えの規則(JSON `frozen_documents.inheritance_rule`): 文書の中の `DEV-USDJPY-SIMPLE-01` は、Trial_ID・trial の directory・AUTHORIZATION.json の path・成果物の名前・records の path・実行の branch についてだけ `DEV-USDJPY-SIMPLE-02` と読む。ほかは何も読み替えない。
- 01 の freeze.json(blob 242ef882)の内容のうち、Trial に依存しない部分(snapshot、S0 の出所、allowlist の境界、Gate、report-only の境界、最初の Origin の規則、結果の保存の手順)をそのまま写した。

## 3. Freeze の対象

- 実装: `-fx-dev-trials` `impl/dev-usdjpy-simple-02`、commit **2212653b9602cfea32f23ea28b2aa5aeb3214ec2**、tree **8ed09862631203ac4787f330b02619a5fd04b220**(27 ファイル)
- 実行の commit の規則: 2212653b の子孫で、tree 8ed09862 との違いが `trials/DEV-USDJPY-SIMPLE-02/AUTHORIZATION.json` と、以前の保存の commit が加えた `records/DEV-USDJPY-SIMPLE-02/` だけ。実行は `exec/dev-usdjpy-simple-02`。
- freeze.json は自分の Freeze の commit の SHA・時刻を持たない(01 の Errata E1 の教訓)。`authorization_file.freeze_commit` は台帳を参照する固定の文字列。

## 4. Freeze の前に解決が要る点

### F-02-1(Claude の発見): GitHub の既定の branch が壊れた workflow を持っている

- GitHub は、workflow_dispatch の workflow が**既定の branch に**あることを求める。現在の既定の branch は `impl/dev-usdjpy-simple-01`(壊れた 01 の workflow)。Claude が API で確かめた: `GET /actions/workflows` の name は `.github/workflows/dev-trial.yml`(path のまま = GitHub が読めていない)。
- このままでは、02 の branch に正しい workflow があっても、01 と同じ 422 になる可能性が高い。
- 案: Freeze の前に、純さんが repository の設定で既定の branch を `impl/dev-usdjpy-simple-02` に変える(tree は変わらない)。その後、実行せずに `GET /actions/workflows` の name が `dev-trial` になる(GitHub が読めた)ことを確かめ、その出力を Freeze の記録 `implementation.workflow_validity_evidence.github_recognition` に書く。これはむすびさんの「実行せずに GitHub が workflow を認識していることを確認する」に当たる。
- このセッションから既定の branch を変えられるかは試していない(承認の範囲の外)。

### F-02-2: PRE-FLIGHT BOUNDARY RULING を 02 に適用するか

- 01 の ruling(ce89162c)は「現行の凍結実装 a7921007 に対する解釈」と書かれている。02 の `preflight()`・`preflight_summary()`・`run_model()` は、trial の directory と成果物の名前を除いて同一。
- 案: 02 は同じ ruling を参照で適用する(JSON `execution_protocol.preflight_boundary_ruling`)。新しい ruling の文書が要るかどうかを、むすびさんに決めていただきたい。

### F-02-3: Registry_Count_At_Design

- 決めずに置く。Freeze の commit A の前に、凍結済みの数え方で測る(FREEZE の event の数。同じ Research_Question_ID の全 event の一覧も出す)。01 の FREEZE が数えられる見込みだが、値は実測で書く。予想外の結果なら何も commit せずに止まる。

### 記録する静的な証拠(Freeze の時)

- PyYAML の版と、02 の workflow(blob 2da72acd)の parse の結果。Claude の手元では PyYAML 6.0.3 で parse でき、trigger は `workflow_dispatch` だけ(参考。Freeze の時に取り直して記録する)。
- `tests/test_workflow_yaml.py` は、01 の workflow では失敗し(構造の検査が fail、parse が error)、02 では通ることを Claude が確かめた。

## 5. Freeze の手順(案)

1. F-02-1 の設定の変更と、実行しない認識の確認。
2. count の確認。
3. V1 commit A: `preregistration/DEV-USDJPY-SIMPLE-02.freeze.json` の 1 ファイルだけを加える(継承する文書の写しは作らない)。
4. V1 commit B: `DEV-TRIAL-REGISTRY.csv` に 02 の FREEZE の event、`registry.csv` に 1 行。
5. `-fx-dev-trials` の tree は変えない。AUTHORIZATION.json は作らない。

## 6. 状態

- DEV-USDJPY-SIMPLE-01 = FREEZE(履歴)/ ABORT
- DEV-USDJPY-SIMPLE-02 = 実装 DIFFERENTIAL AUDIT PASS / Freeze Candidate V0 = DRAFT / NOT FROZEN
- preflight = NOT AUTHORIZED、Development = NOT AUTHORIZED、Forward = NOT AUTHORIZED、Holdout = SEALED
