# DEV-USDJPY-SIMPLE-01 — Freeze Candidate(DRAFT V0.1)

- 状態: **FREEZE CANDIDATE V0.1(Claude、2026-10-31)**。むすびさんの最終監査待ち。**Freeze ではない。preflight・Development の実行の承認でもない。**
- V0(V1 commit 75eb8020、blob a84a15d3)= REVISE MINOR(F-FC-1)。**V0 の 3 ファイルは変更せず残す。**
- 付属のファイル(どちらも案):
  - `drafts/DEV-USDJPY-SIMPLE-01-FREEZE-CANDIDATE-V0.1.freeze.candidate.json` — Freeze の記録の案(実装の 26 ファイルの blob・SHA-256、runtime、実行・保存の規則)
  - `drafts/DEV-USDJPY-SIMPLE-01-FREEZE-CANDIDATE-V0.1.registry.candidate.csv` — 台帳の行の案
- この版では V1 の `preregistration/` に何も書かない。データを読まない。何も実行しない。

## 1. V0 からの変更

| 項目 | V0 | V0.1 |
|---|---|---|
| 実装 | 7ad94415、tree deb2d0c0(25 ファイル) | **a792100770aac264dab2a996aa2af04e92db1984、tree 29d72c501dc49b2e5602e7fc1ec6c873ea2f7088(26 ファイル)** |
| F-FC-1 runtime | 未解決 | **RESOLVED / PASS**: Python 3.13.17、numpy 2.5.3 の wheel SHA-256 a5fa86b8…e25321(PyPI、むすびさんが確認)を `--require-hashes` で固定、Actions を commit SHA で固定 |
| F-FC-2 結果の保存 | 案 | **ACCEPTED(修正つき)**: 人に依存しない固定の手順(§3) |
| F-FC-3 Freeze-prep v0.1 | 確認待ち | **PASS / READY FOR FREEZE PREPARATION / NOT FROZEN / NOT EXECUTION-AUTHORIZED** |
| F-FC-4 main | 案 | **ACCEPTED**: `main` を作らない |
| Registry_Count_At_Design | 0(案) | 0(案)。**Freeze の時に機械的に確かめてから確定**(§4) |
| 実行の commit の規則 | AUTHORIZATION.json だけ | AUTHORIZATION.json と、以前の保存の commit が加えた `records/DEV-USDJPY-SIMPLE-01/` のファイルだけ(§2) |
| SHA-256 の扱い | Claude の申告 | **Claude-declared unless independently verified**(numpy の wheel の SHA-256 はむすびさんが PyPI で確認) |

## 2. 実行の commit の規則(更新)

- 実行の commit は a7921007 の子孫で、tree 29d72c50 との違いが次だけであること:
  1. `trials/DEV-USDJPY-SIMPLE-01/AUTHORIZATION.json` の追加・変更
  2. それより前の保存の commit(§3)が加えた `records/DEV-USDJPY-SIMPLE-01/` の下のファイル(コードはこれを読まない)
- ほかに違いがあれば、この Trial ではない(ABORT の event と新しい Trial_ID)。
- **変更の理由**: preflight の結果を §3 で保存すると、その後の本実行の commit の tree に `records/` が入る。V0 の規則のままだと、本実行が規則に反してしまう。
- 実行は `exec/dev-usdjpy-simple-01` の branch で行い、`impl/dev-usdjpy-simple-01` は動かさない。`main` は作らない。

## 3. 結果の artifact の長期保存(F-FC-2、固定の手順)

1. workflow の run は、成果物のファイルごとに path と SHA-256 を log に出し(run.py の既存の出力)、Actions の artifact として upload する。
2. artifact を取得し、各ファイルの SHA-256 を計算し直して、その run の log の値と照合する。食い違い・欠けがあれば **PRESERVATION_FAILURE** と記録する(ファイルを直したり作り直したりしない)。
3. ファイルをバイトのまま、`-fx-dev-trials` の `records/DEV-USDJPY-SIMPLE-01/<mode>/<run_id>/` に、それだけを加える commit で保存する(実行の branch の上)。保存したファイルは後から変更・削除しない。
4. 保存の commit、run の ID、実行の commit、ファイルごとの SHA-256 を、DEV-TRIAL-REGISTRY の event の行(PREFLIGHT または EXECUTION_RESULT)に書く。Note の形: `artifact_files=<name>:<sha256>[|...]; records_commit=<sha>; workflow_run=<run_id>; preservation=OK|PRESERVATION_FAILURE`。

- 保存の commit は実行の commit ではない。§2 の 2 によって、後の実行の tree にあってよい。
- 台帳の列は Freeze 前パッケージ v0.1 §6 のまま変えず、保存の情報は Note に決まった形で書く。

## 4. Registry_Count_At_Design の機械的な確認(Freeze の時)

- Freeze の commit A の前に、Freeze のもとにする V1 の commit で次を行う:
  1. `preregistration/DEV-TRIAL-REGISTRY.csv` の中で、`Registry_Event = FREEZE` かつ `Research_Question_ID = USDJPY-1D-PRICE-ONLY-LOCATION` の Trial_ID の数(ファイルがなければ 0)。
  2. `preregistration/` と `drafts/` の全体で、DEV-USDJPY-SIMPLE-01 のファイル以外にこの Research_Question_ID の文字列がないこと。
- 使った命令、もとにした commit、出力を commit B の message に書く。
- 0 でなければ Freeze を止め、何も commit せずに報告する。
- 現時点(V1 main 75eb8020)では `DEV-TRIAL-REGISTRY.csv` は存在しない(参考。確定は Freeze の時)。

## 5. Freeze の手順(純さんの決定の後。V0 から変更なし、対象の commit だけ更新)

1. §4 の確認。
2. V1 commit A: `preregistration/` に SPEC v0.3・Freeze-prep v0.1 のバイトの写し(blob 647fcc19・bb3617b8 と一致すること)と、`DEV-USDJPY-SIMPLE-01.freeze.json`(JSON 案の `<...>` を埋め、`status_of_this_file` を除いたもの)。
3. V1 commit B: `registry.csv` に 1 行、`DEV-TRIAL-REGISTRY.csv` を新設して FREEZE の event。
4. `-fx-dev-trials` は何も変えない。`AUTHORIZATION.json` は作らない。

## 6. 引き継ぐもの(V0 で承認済み、変更なし)

- `report_only_boundary`(方向の診断 3 指標を、後から Gate・確認的な証拠・DA Safety Veto に昇格させない)
- Gate の定義、数値のパラメータ、allowlist の境界、S0 の出所、最初の Origin の規則
- `Research_Question_ID = USDJPY-1D-PRICE-ONLY-LOCATION`、台帳の event の形

## 7. 状態

- SPEC v0.3 = PASS / NOT FROZEN、Freeze-prep v0.1 = PASS / READY FOR FREEZE PREPARATION
- 実装 a7921007 = IMPLEMENTATION AUDIT PASS(runtime の固定を含む)
- Freeze Candidate V0 = REVISE MINOR / PRESERVED、V0.1 = DRAFT
- preflight = NOT AUTHORIZED、Development = NOT STARTED、Forward = NOT AUTHORIZED
- V1 = 変更なし(この版は `drafts/` だけ)、Historical Reserve Holdout = SEALED
