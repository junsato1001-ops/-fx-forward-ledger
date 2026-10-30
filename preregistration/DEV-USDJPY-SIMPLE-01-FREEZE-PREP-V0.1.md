# DEV-USDJPY-SIMPLE-01 — Freeze 前パッケージ(DRAFT v0.1)

- 状態: **DRAFT v0.1**(Claude、2026-10-30)。むすびさんの Freeze 前の最終監査待ち。**Freeze ではない。実行の承認でもない。**
- v0(commit f7c10618、blob 97eaadcd、SHA-256 927fd976…)からの変更(むすびさんの監査 REVISE MINOR、2026-10-30 17:04 JST):
  1. **§3.2 allowlist の境界を厳密にした**: 非 allowlist の列の raw bytes が入力を通過し、列の境界を特定するために走査されることだけを許す。Date・JPY・USD 以外の field value を、文字列・数値その他の値として materialize・decode・保存・返却・logging しない。1 行の全欄を文字列にしてから選ぶ実装(Python の `csv.reader`・`csv.DictReader` など)を禁止した。
  2. **§5.2・§7 preflight の結果を Freeze の記録に追記しない**: Freeze の記録は Freeze の時点で完全に固定し、その後変更しない。preflight の結果は別の artifact に保存し、台帳の PREFLIGHT の event で記録する。
  v0 は drafts/ にそのまま残す。
- 対象の仕様: `drafts/DEV-USDJPY-SIMPLE-01-SPEC-V0.3.draft.md`(commit 17cc7c6d、blob 647fcc19、SHA-256 13e7e330…。むすびさんの差分監査 PASS)。**このパッケージは v0.3 の本文を変えない。** v0.3 §14 の 5 項目を埋める付属の記録として、Freeze のときに仕様と一緒に固定する。
- 決定(純さん・むすびさん、2026-10-30 16:58 JST):
  1. S0 の出所 = (a) 作り直しを正 + (b) 照合できるときだけ照合
  2. allowlist = 案 (i)。案 (ii) は却下。**新しく V1 の全列を読む検査は行わない**
  3. 実行の場所 = 新しい専用の repository
  4. 台帳 = V1 の `preregistration/DEV-TRIAL-REGISTRY.csv`、event の形の追記のみ
- 照合した V1 の commit: `17cc7c6d7c2489038bbffd07b95fd3db1d1697ac`(V1 main)。この版で読んだのはコードの構造・入出力とファイルの SHA-256 だけで、データの値・成績は見ていない。何も実行していない。

---

## 1. ECB スナップショット(v0.3 §2.3、§14-1)

| 項目 | 値 |
|---|---|
| ファイル | V1 repository の `tests/fixtures/eurofxref-hist_20261009.zip` |
| SHA-256 | `f36e0affc225bc572cc589d4183352c5815f178769f04c2b27a452567c6f7649` |
| Git blob(V1 main 17cc7c6d) | `88b4dcdbca1a062d78a1a85b7a9112199451ad9b` |
| 中身 | `eurofxref-hist.csv` の 1 ファイル(1,926,001 bytes) |
| 根拠 | EVAL-SPEC-V1 §6(Development の締め切りのスナップショット)。凍結した `frozen/formal_forecast_ledger_v1.py` の EXPECTED_ZIP。M1-VOL-SHRINK-V1.impl.json、M1-MACRO-IMPL-PART1 も同じもの |

- 新しい repository には、このファイルを**バイトの同一性を確かめた写し**として置く(SHA-256 の照合に通らなければ止まる)。
- **注意**: このファイルは Holdout の 5 ペアの通貨の列も含む(EVAL-SPEC-V1 §6 の Holdout のスナップショットも同じ f36e0aff…)。§3 の allowlist が必須である。

## 2. 親 S0 の出所(v0.3 §11.3、§14-2)

### 2.1 前提: (b) 単独は技術的に不可能

凍結した S0 v1.1(`frozen/s0_empclim_std_exp_v1_1.py`)の出力の列は、Pool_N・Mean_Z・Q10_Z・Q90_Z・Point・確率・PI などの**要約だけ**で、pool の点 {Z_i} を含まない。この Challenger は pool 全体をずらした分布の CRPS を必要とするので、発行済みの S0 の行を読むだけでは作れない。

### 2.2 決定: (a) 作り直しを正、(b) は照合

- **正**: 凍結した S0 v1.1 の関数で、USD/JPY 1D の pool を作り直す。Challenger の分布は、この pool と σ_M0 から作る。
- **照合(b)**: V1 の ledger に、同じキーの S0 の COMPLETE かつ ON_TIME の行があるときだけ、Pool_N・Mean_Z・Q10_Z・Q90_Z・Decision_Class の文字列を照合する。**食い違えば PIPELINE_FAILURE**。
- V1 の行がない、または LATE の場合は、**照合できなかったことを記録するだけで、発行は止めない**(V1 の運用の障害をこの Trial に伝えない)。
- 先例: M1-MACRO-V1 の `m1macro/s0link.py`(凍結した S0 で pool を作り直し、発行済みの S0 の行と照合し、食い違いは PIPELINE_FAILURE。M1 は自分で pool を作らない)。この Trial は同じ考え方を採る。s0link.py そのものは V1 の Code_SHA の対象なので、呼び出さずに、同じ規則を新しい repository の中に書く。
- Development では、照合の相手になる発行済みの行がない(Development の期間の S0 の行は V1 の Forward の ledger にない)。Development での S0 の正しさは §3.3 の構成による同一性で担保する。

## 3. 実装の仕様(v0.3 §14-3)

### 3.1 訂正(前回の報告)

前回、「`frozen/formal_forecast_ledger_v1.py` と、それと等価な `forward/ledger_builder.py` は全通貨を数値としてメモリに持つ」と報告した。正確には:

- `frozen/formal_forecast_ledger_v1.py`: CSV の全列を `csv.DictReader` で読み、**全列を数値に変換して**メモリに持つ。
- `forward/ledger_builder.py`(V1 の CODE_MANIFEST_V1 の対象、SHA-256 5d3b91c7…): `csv.DictReader` で行を読み(全列が文字列として一時的に行の辞書に入る)、**数値に変換するのは JPY・USD・CHF・INR の 4 列だけ**。

どちらも、この Trial の allowlist の要求(Date・JPY・USD 以外を保持しない)を満たさない。決定 2 のとおり、この Trial はどちらの読み取りの関数も呼ばない。

### 3.2 allowlist の境界(決定 2 の具体化。v0.1 で厳密化)

**境界の定義(Freeze に書く)**: 非 allowlist の列の raw bytes が入力のストリームを通過し、列の境界(区切りの `,` と行の終わり)を特定するために走査されること自体は許容する。ただし、`Date`・`JPY`・`USD` 以外の **field value を、文字列・数値その他の値として materialize、decode、保存、返却、logging してはならない**。

- bytes が通過し区切りを判定されること ≠ Holdout の値を field value として読むこと。

**実装の要件**:

1. **見出しの行**: 見出しの行だけは decode し、`Date`・`JPY`・`USD` の位置(何番目の欄か)を決める。見出しの名前は列の名前であって値ではない。見出しから取り出して保持するのは、この 3 つの位置の番号だけである。ほかの列の名前を変数・ログ・出力に残さない。`Date`・`JPY`・`USD` のどれかがない、または重複するなら止まる。
2. **データの行**: 各行を bytes のまま走査し、区切りの `,` を数えて、上の 3 つの位置の欄の bytes の範囲だけを切り出す。**切り出した 3 つの欄だけ**を decode し、Date は日付に、JPY・USD は数値(空や `N/A` は欠測)に変換する。ほかの欄の範囲は切り出さず、decode せず、変数に入れない。
3. **禁止する実装**: Python の `csv.reader`・`csv.DictReader`、`str.split(",")` のように **1 行の全欄を文字列(または値)の並びとして作ってから選ぶ方法**、pandas などでの読み込みは使わない。
4. **引用符の扱い(fail-closed)**: ECB のファイルは引用符を使わない形式である。行の中に `"` が現れたら、区切りの判定が単純でなくなるので、**止まる**(推測で読み進めない)。
5. **戻り値**: 読み取りの関数は (Date, JPY, USD) の並びだけを返す。

**検査(実装の監査で確かめる)**:

1. 読み取りの関数の戻り値の列が、正確に `Date`・`JPY`・`USD` であることを assert する。
2. 見出しに `Date`・`JPY`・`USD` がない・重複する、データの行に `"` がある、欄の数が見出しと違う、の各場合に止まることを確かめる。
3. 単体の検査は**合成の CSV だけ**で行う。架空の通貨の列に目印の値(例: 目立つ固有の文字列)を入れ、その目印が、戻り値・関数の中で作られる値・ログ・例外のメッセージのどこにも現れないことを確かめる(実装の上で、目印を含む bytes の範囲が切り出されないことを含む)。**実際のスナップショットの Holdout の列を使った検査はしない。**
4. コードの静的な検査で、`csv` module・`split(",")`・pandas の読み込みが読み取りの経路にないことを確かめる。

- **新しく V1 の全列を読む検査はしない**(決定 2)。前回の私の案「V1 の既存の検査を 1 回動かして USD/JPY の行の hash を作る」は取り下げる。

### 3.3 台帳の行の作り方と、凍結台帳との同一性の根拠

- 台帳の行(Origin、Last_Available_Fix、Target_Start、Target_End、Sigma_H、Realized_LogReturn、Prereq_Status、Outcome_Status など)は、V1 の `forward/ledger_builder.py` の `make_one()`(「凍結台帳の one() の正確な複製」、V1 の Implementation Freeze で凍結台帳 e4edb850… とのバイトの一致が確かめられたもの)と**同じ処理**で作る。
- `make_one()` のある通貨の組の行は、その組の (日付, レート) の系列と、ファイル全体の日付の一覧(`obs`。Date の列だけから決まる)だけに依存する。したがって、allowlist の 3 列から作った USD/JPY の系列と日付の一覧を入れれば、凍結台帳の USD/JPY の行と**構成上同じ**になる。
- 実装の形: 新しい repository に、V1 の `forward/ledger_builder.py` の `make_one()` と、凍結の M0 v1.2・ORIGIN_TARGET_MAP_V1・S0 v1.1 を、**SHA-256 を確かめた固定の写し**として置き、読み込む前に照合する。`read_ecb_zip()` と `pair_series()` は使わず、§3.2 の読み取りの関数で置き換える。
- 既存の照合の証拠: ledger_builder と凍結台帳の同一性は、V1 の Implementation Freeze(CODE_MANIFEST_V1、`tests/test_reproduce_frozen.py`)ですでに確かめられている。この Trial はその証拠を参照するだけで、新しく全列を読んで確かめ直さない。

### 3.4 参照する凍結のコード(固定の写しとして置く)

| V1 のファイル | SHA-256 | Git blob(V1 main 17cc7c6d) | 使い方 |
|---|---|---|---|
| `frozen/m0_walkforward_v1_2.py` | `4ca2f37ab729d08f24f008d75c5ceb95f11d79d5bf9575941f44ffd32a77e3d5` | `6d03099942a0cabb3eb6f0f971e2039ecba97f3e` | σ_M0(VOL_STATE_V1) |
| `frozen/origin_target_map_v1.py` | `902f0b43a84a0ec309a6e99b6617ca2816e240054bd77e9dbf7d3b2812f3c988` | `de8f724f03e03aaa0c46bd873e03a3b4818e5393` | Origin・Target・TARGET の暦 |
| `frozen/s0_empclim_std_exp_v1_1.py` | `84c317661e6798b906063a50fc416c9d594708ffcfbb6010a5bd83f636487676` | `c89a067ad0701eb0e5c90614690ca3be9dac0153` | S0 の pool の作り直し(§2) |
| `forward/ledger_builder.py` | `5d3b91c7a666b9f7d5c12db88dbbf969ebceef5386bbabb22f13e3e907de25a0` | `9c1cbecda3e69aa1de9c5ffc165816d234d8ec90` | `make_one()` だけを使う(§3.3) |
| `m1macro/s0link.py` | `cac6a6dc7bb4ab993e4eb8610b668d2c2b11de28ad65869953076366f66b21bb` | `ce3da74220c83532b704b432d4f5e291b67ac0bd` | 呼び出さない。規則の先例としてだけ参照(§2.2) |

- 上の 3 つの frozen と ledger_builder の SHA-256 は、V1 の CODE_MANIFEST_V1(`preregistration/M1-MACRO-IMPL-CODE-V1.freeze.json`)の値と一致する。

### 3.5 そのほかの実装の要件

| 項目 | 内容 |
|---|---|
| 言語 | Python 3(版を固定)。β の推定は、乱数を使わない決定的な方法(線形計画で J の最小値を求め、その範囲で ‖β‖₂ を最小にする。MODEL-PART2C-V1 §5)。外部の package を使うなら版と hash を固定する |
| F_MOM | v0.3 §3.3 どおり、v から **20 TARGET publication days 前**の日を ORIGIN_TARGET_MAP_V1 の暦で数える。その日の USD/JPY の fix が系列にない(PAIR_COMPONENT_GAP など)なら FEATURE_PREREQ_UNAVAILABLE |
| 必須の検査 | ① 入力の SHA-256(zip と §3.4 の写し)② allowlist(§3.2)③ S0 の作り直しの検査(§2.2)④ DEFAULT_PARENT の行と β = 0 の行が S0 と完全に一致 ⑤ Target_End ≤ 2026-10-09 の外の機会が 1 件もないことの assert ⑥ Holdout の 5 ペアの名前・通貨の記号がコード・設定・出力に現れないことの静的な検査 ⑦ Gate の計算のコードの SHA-256 を、実行の前に Freeze の記録に書く |
| 出力の制限 | §5 の preflight は、日付・件数・状態だけを出す。本実行の成果物は v0.3 §10・§13 のとおり |

## 4. 実行の場所(決定 3)

- **新しい専用の repository**(名前は純さんが決める。例: `junsato1001-ops/-fx-dev-trials`)。作成は純さんの作業(このセッションからは repository を作れない)。
- 最小の権限:
  - V1 の credential を持たない。V2 の credential も持たない(この Trial は V2 に書かない)。
  - Holdout の通貨の列を扱うコードを持たない(§3.2、§3.5 ⑥)。
  - workflow は手動の起動だけ。schedule を持たない。**Forward の workflow を持たない**(Forward は承認されていない)。
  - 書き込みは、その repository の中の決められた場所だけ。
- V1・V2 は読み取り専用の依存として扱う。§1 のスナップショットと §3.4 のコードは、SHA-256 を確かめた固定の写しとして置く(V1 の repository を実行の時に参照しない)。

## 5. Development の最初の Origin と preflight(v0.3 §14-5)

### 5.1 規則(Freeze に書く)

最初の評価の Origin = USD/JPY 1D の formal な Origin のうち、次がすべてそろう最初のもの:

1. 台帳の行が FORECAST_READY(M0 の 252 本の warm-up。`make_one()` の `j < 252` の判定)
2. S0 が FORECAST(N_overlap_equiv ≥ 100)
3. F_MOM が定義できる

### 5.2 preflight(Freeze と実装の監査の後、Development の本実行の前に 1 回)

- 出力するのは、**日付・件数・状態だけ**:
  - 最初の評価の Origin、最初の ESTIMATED の Origin(N_WARMUP = 250 に達する Origin)
  - 状態ごとの件数(Prereq_Status、S0 の Decision_Class、Outcome_Status、FEATURE_PREREQ_UNAVAILABLE、METRIC_UNDEFINED_ZERO_SCALE)
  - Gate の対象の件数 N_EVAL(NOT_EVALUABLE かどうかの判定に使う件数そのもの)
- **出力しないもの**: 価格、σ_M0、pool の値、F_MOM の値、β、損失、d_t、D̄、p 値、そのほかの成績の情報。
- **preflight の結果は、Freeze の記録に追記しない。** Freeze の記録(freeze.json)は Freeze の時点で完全に固定し、その後変更しない(変更すると Freeze の記録そのものの SHA-256 が変わるため)。
- preflight の結果は、**別の artifact**(例: 実行の repository の `DEV-USDJPY-SIMPLE-01-PREFLIGHT.json`)として保存する。その SHA-256、実行の commit、run の ID を、§6 の台帳に **`Registry_Event = PREFLIGHT`** の行として追記する。
- preflight の件数を見てから仕様を変えることはしない。変えるなら、この Trial を台帳の ABORT の event で終え、別の Trial_ID とする。

### 5.3 暦だけからの見込み(非拘束)

- ECB の USD/JPY は 1999 年から。M0 の warm-up(約 1 年)、S0 の 1D の N ≥ 100(約 5 か月)、N_WARMUP = 250(約 1 年)から、Gate の対象は 2001 年ごろから 2026-10-09 までで、**約 6,000 件**になる見込み。
- これは**非拘束の calendar-only の見込み**である。実際の Gate の対象は、S0 が FORECAST、F_MOM が定義できる、σ_M0 > 0、Outcome = OBSERVED などの条件を通るので、preflight の値で確定する。

## 6. DEV-TRIAL-REGISTRY(決定 4、event の形)

- 置き場所: V1 の repository の `preregistration/DEV-TRIAL-REGISTRY.csv`(CODE_MANIFEST_V1 の外。研究の設計と試行の履歴の台帳)。
- **追記のみ。過去の行は更新しない。** 1 行 = 1 つの event。同じ Trial_ID の行を時系列で読めば、その Trial の履歴になる。
- 列:

```
Event_Seq, Trial_ID, Registry_Event, Event_At_JST, Research_Question_ID, Spec_File, Spec_SHA256,
Freeze_Commit, Challenger_Summary, Registry_Count_At_Design, Execution_Repo, Execution_Commit,
Execution_Run_ID, Result_Class, Note
```

- `Registry_Event`: `FREEZE` / `PREFLIGHT` / `EXECUTION_RESULT` / `ABORT`
- `Result_Class`(EXECUTION_RESULT の行だけ): `FORWARD_CANDIDATE_ELIGIBLE` / `NOT_ELIGIBLE` / `NOT_EVALUABLE`
- `Research_Question_ID`: 同じ研究の問いへの繰り返しの Trial を数える(この Trial は案として `USDJPY-1D-PRICE-ONLY-LOCATION`)
- `Registry_Count_At_Design`: 設計の時点での、同じ Research_Question_ID の Trial の数(この Trial は 0)

## 7. Freeze の時に記録に入るもの(案)

Freeze の記録(freeze.json)に、次を書く:

1. v0.3 の仕様の SHA-256 と blob、このパッケージの SHA-256 と blob
2. §1 のスナップショットの SHA-256
3. §3.4 の参照コードの SHA-256(と V1 の CODE_MANIFEST_V1 との一致)
4. §2.2 の S0 の出所の決定
5. §3.2 の allowlist の境界の定義
6. §4 の実行の repository の名前と最初の commit(repository は Freeze の前に作る。Freeze の後に記録へ書き足さない)
7. §5.1 の最初の Origin の規則と、「preflight は Freeze の後・Development の本実行の前に行い、結果は別の artifact と台帳の PREFLIGHT の event で記録する。Freeze の記録は変更しない」という規則
8. §6 の台帳の列と、FREEZE の event の行

## 8. むすびさんに確かめていただきたいこと

1. §1・§3.4 の SHA-256 と blob(私の計算の値。独立の確認をお願いしたい)。
2. §3.2 の厳密化した allowlist の境界と、実装の要件・検査が、v0.3 §2.3 の「読ませない」と同じ強さになっているか。
3. §3.3 の「構成上同じ」という同一性の根拠で、新しい全列の読み取りなしに足りるか。
4. §5.2 の preflight の出力の範囲(N_EVAL の件数を Freeze の前に見ることを含む)。

## 9. 状態

- P3 = IN PROGRESS(無関係)
- DEV-USDJPY-SIMPLE-01: v0.3 = DIFFERENTIAL AUDIT PASS / NOT FROZEN、Freeze 前パッケージ v0 = REVISE MINOR / PRESERVED、v0.1 = DRAFT
- Development = NOT STARTED、V1 Development Replay = NOT STARTED
- Forward = NOT AUTHORIZED
- Holdout(RFX-HOLDOUT-A-V1、5 ペア)= SEALED
