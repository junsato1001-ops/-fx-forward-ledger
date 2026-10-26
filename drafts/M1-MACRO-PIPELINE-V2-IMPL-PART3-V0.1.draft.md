# M1-MACRO-PIPELINE-V2 Implementation Spec — Part 3: Parent / Issuance(DRAFT v0.1)

- 状態: **DRAFT v0.1**(Claude、2026-10-27)。むすびさんの監査待ち。Freeze 候補ではない。
- 前の版: v0(blob 80679676…)。書き換えずに残してある。
- v0 からの変更: むすびさんの判断(2026-10-27 02:03 JST、v0 = REVIEW PASS WITH REVISIONS)を反映した。
  1. **F-P3-12(BLOCKING / REVISE)**: V1 の Forward の期間を gap にする案を取り下げた。**推定の履歴は継続し、予測の series だけを分ける**。V2 の履歴の境界 B より前の Origin は、V1 の core が本来使う V1 の台帳の記録を read-only で使い、B 以後は V2 の台帳だけを使う(§12)。
  2. **F-P3-1(REVISE)**: S0 の親の確認を、V2 自身が Storage Verification Gate の不変条件を検証する形に改めた。V1 の Actions の成功は補助の証拠に下げた(§7.2)。
  3. **F-P3-2・F-P3-10(REVISE)**: V1 の非公開の保管場所を実行時に読まない。開発用 snapshot の非公開の部分を、V2 の非公開の保管場所に**バイトで同じに写し**、source の commit・blob・SHA-256 を manifest に残す。通常の V2 の発行の実行環境は、V1 の credential を持たない(§3.1、§10)。
  4. **F-P3-6(REVISE)**: 合成のデータの関門に加えて、**固定の fixture の入力**で、V1 の orchestration と、V1 の core + V2 の adapter の出力をバイトで比べる関門を加えた。性能の値は見ない(§3.2)。
  5. **F-P3-11(ACCEPT / CLOSE WITH CLARIFICATION)**: 「最後の attempt」を、予定の時刻が 08:20 の attempt と定義した。08:30 以後に始まった attempt は TOO_LATE で、unavailable の行を後から発行しない(§8.3)。
  6. 決定を記録した: F-P3-3・F-P3-4・F-P3-5・F-P3-9 = ACCEPT / CLOSE、F-P3-7 = DEFER → Part 4、F-P3-8 = DEFER → C2 の選定(§13)。
  7. 修正: v0 §7.3 の ECB の履歴の path を `data/eurofxref-hist.csv` と書いていたのは誤り。V1 の path は `data/ecb/eurofxref-hist.csv`(V1 の forward/issue.py の DATA)。
  8. 追加(Claude): F-P3-13(履歴の境界 B の定義と、受け入れの試験の行の置き場所)。
- 前提(Freeze 済み):
  - **M1-MACRO-PIPELINE-V2-REQUIREMENTS-V0.7**(SHA-256 edf27751…)。以下「Requirements」。
  - **M1-MACRO-PIPELINE-V2-IMPL-PART1-V0.5**(SHA-256 c63a0927…)と Erratum E1。以下「Part 1」。
  - **M1-MACRO-PIPELINE-V2-IMPL-PART2-V0.4**(SHA-256 6e9082a4…)。以下「Part 2」。
  - M1-MACRO-V1 の凍結済みの仕様(Impl Part 1 V1.2、Part 3 V1、Part 4 V1、Data Availability Matrix V1 など)と実装(Code_SHA256 d3c77eba…)。以下「V1」。
- この Part の範囲: V1 の S0 の親の行の read-only の確認、feature readiness、10 回の発行の attempt、idempotency、COMPLETE の transaction、08:30 の締め切り、V2 の台帳。
- **この Part は Requirements・Part 1・Part 2・V1 を再設計しない。** 統計モデル、特徴量の定義、推定、評価の仕様は V1 のまま(Requirements §0、§2 の 4)。Requirements が決めていない点や、V1 の構造から来る境界の問題は §13 に Finding として分けて書く。
- このメモではしないこと: V1 の変更、V2 の発行の実行、較正と試験、Development Replay、Holdout の計算。M1-MACRO の予測の値・β・μ・J*・CRPS などは読まない。

---

## 1. この Part が実現するもの

| 出どころ | 内容 | この Part の実現箇所 |
|---|---|---|
| Requirements §4、§4.1 | acquisition → feature readiness → S0 parent readiness → M1 issuance。03:20 から発行。canonical な decision が SUCCESS で COMPLETE していることを確かめる | §5、§6 |
| Requirements §4.3 | V1 は read-only、V1 の commit の SHA を記録、Storage Verification Gate と同じ検証を V2 で行う、V1 への書き込みの権限を持たない | §7、§10 |
| Requirements §4.4 | 10 回の attempt、A・C から起動、idempotency、二重の発行なし、attempt の結果を追記のみで記録 | §4、§9 |
| Requirements §4.1、§7.5 | 08:30 の締め切り、V1 Part 4 §3 の Verified_At_UTC 規則 | §9.3 |
| Requirements §7.1 の 2 | Holdout の 5 ペアに触れない | §11 |
| Part 1 §9.6 | 発行の attempt は canonical な decision の COMPLETE の時刻を activity API で確かめ、03:20:00 を過ぎていれば UNDETERMINED として扱う | §6.2 |
| Part 2 §8 | main_entry_time | §6.2、§7.4 |

Issuance Gate の判定(08:15 の S0 cutoff、08:45〜09:15 の adjudication)は Part 4 で扱う。この Part は、Part 4 が判定に使う記録を残す。

## 2. V2 が発行するもの

- **モデルは M1-MACRO-V1 のまま**(Requirements §0)。V2 が出す行は、V1 Impl Part 3 §6 の 3 つの台帳(m1_macro_features、m1_macro_estimation、m1_macro_forecasts)と COMPLETE の記録(m1_macro_issue_commits)、締め切りの監査(m1_macro_issue_deadline)と同じ列・同じ直列化(V1 Impl Part 4 §2)で、**V2 repository** に書く。
- **V2 の行の区分**(Requirements §2 の 2): 列は増やさず、Run_ID を `V2-<経路>-<実行の ID>` の形にする(例: `V2-A-40251069713-1`)。V1 の Run_ID(`<数字>-<数字>`)と形が重ならない。置き場所(V2 repository)と Run_ID の両方で区別する(§13 の F-P3-4)。
- 対象は Forward の 3 ペア(USDJPY、CHFJPY、INRJPY)と、凍結済みの ORIGIN_TARGET_MAP_V1 の正式な (Origin, Horizon) だけ。

## 3. コードの同一性

V2 の発行は、統計の計算を V1 と同じにしなければならない。そこで、コードを 2 つに分ける(§13 の F-P3-6)。

| 区分 | 中身 | 扱い |
|---|---|---|
| **V1 の計算の core** | V1 の m1macro/ の特徴量・推定・予測・S0 との接続の計算(features、rates、cftc_feature、cftc_parse、cftc_rules、cftc_schedule、uscal、jpcal、tz、estimation、solver、forecast、s0link、pipeline、canon、schema)、frozen/(S0 の参照実装 v1.1、ORIGIN_TARGET_MAP_V1、M0)、forward/ledger_builder.py、env/(image の digest、lock ファイル) | V1 の CODE_MANIFEST_V1 にあるファイルを**バイトで同じに**写し、起動のたびに SHA-256 を V1 の CODE_MANIFEST_V1 の値と照合する(Part 1 F-P1-8 と同じ)。一致しなければ発行しない |
| **V2 の adapter** | 入出力だけを置き換える部分: CFTC の snapshot を canonical な decision から渡す、S0 の親の行と ECB の履歴を V1 の固定した commit から読む、台帳を V2 repository に書く、attempt の制御 | V2 の Code_SHA の対象。統計の計算をしない |

- V1 の `forward_run.py`(V1 の発行の orchestration)は、入出力と計算が混ざっているので、そのままは使わない。V2 の adapter は、V1 の `build_rows_for_origin` と**同じ順序で同じ core の関数を呼ぶ**。
### 3.1 V1 の開発用 snapshot の非公開の部分(F-P3-2・F-P3-10)

- V1 の core の推定は、開発用 snapshot(V1 Impl Part 1 V1.2 §6)を使う。そのうち米国債の原データは、V1 の非公開の保管場所(junsato1001-ops/fx-ledger-private-raw)にある。
- **V2 の通常の実行環境は、V1 の非公開の保管場所を読まない。** 代わりに、V2 の準備の段階で 1 回だけ、次を行う。
  1. 一度だけ使う、読み取りだけの credential で、V1 の非公開の保管場所の開発用 snapshot の非公開の部分を取得する。
  2. V2 の非公開の保管場所(§10.3)に、**バイトで同じに**写す。
  3. 写したファイルごとに、source の repository、commit、path、Git blob、SHA-256 を記録した manifest を作る。各 SHA-256 が、V1 の公開の開発用 snapshot の manifest(V1 の `data/m1macro/dev_snapshot/manifest.json`)の値と一致することを確かめる。
  4. 使い終わった credential を破棄する。この 1 回の作業の記録(manifest と確認の結果)を V2 repository に残す。
- V2 の発行の実行では、写したものの SHA-256 を manifest と照合してから使う。一致しなければ発行しない(PIPELINE_FAILURE)。

### 3.2 同一性の関門(F-P3-6)

実装の候補の段階で、次の 2 つを行う。どちらも M1-MACRO の実データの予測の値・β・μ などを読まず、表示もしない。

| 関門 | 入力 | 比べるもの |
|---|---|---|
| 合成のデータ | 合成の入力(V1 の synth.py と同じ考え方) | V1 の orchestration(V1 の `build_rows_for_origin` を V1 の repository の形で呼ぶ)と、V1 の core + V2 の adapter の出力を、**バイトで**比べる |
| 固定の fixture | 性能の評価に使わない、固定の fixture の入力(V1 の Freeze の前に使った非性能の fixture、または新しく固定した fixture。中身と SHA-256 を事前に固定する) | 同上 |

- 比べるのは program の同一性(同じ入力から同じバイト列ができること)であり、実際の市場の予測の値との比較ではない。
- 結果として記録するのは、一致・不一致と、一致しなかったファイルの名前と hash だけ。値は記録しない。

## 4. 発行の attempt の起動(Requirements §4.4)

### 4.1 時刻

```
JST:  03:20  04:00  05:00  06:00  07:00  07:30  07:45  08:00  08:10  08:20
UTC:  18:20  19:00  20:00  21:00  22:00  22:30  22:45  23:00  23:10  23:20(前日)
```

- A: 10 本の cron。C: 同じ 10 の時刻を起動できるようにする。毎回の両方の起動は要求しない(Requirements §4.4)。案: C も 10 の時刻すべてを起動する(要求の量は §13 の F-P3-8)。

### 4.2 Target_Origin

- 予定の時刻 S は、A は Part 1 §5.3、C は Part 1 §6.4 の規則で決める。
- **Target_Origin = S の JST の日付**。その日に正式な Horizon が 1 つもなければ、何もせずに attempt の記録に NOT_AN_ORIGIN と書いて終わる。
- 起動の時点で runner の時計が 08:30:00 JST(Target_Origin の日)を過ぎていれば、何もせずに TOO_LATE と書いて終わる。締め切りの後に予測を出さない V1 の規則(Impl Part 3 §3 の 1)と同じ。

### 4.3 強制 failover の窓(Part 1 §10 で後に回した部分)

- 案: 強制 failover の窓で止める経路は、発行の attempt の起動も止める(Part 1 §10 の取得・decision と同じ範囲に加える)。
- 強制 failover の窓は、Issuance Gate の分母に入らない(Requirements §6.5)。発行の結果は記録だけする。
- Part 4 の adjudication を同じ窓で止めるかは、Part 4 で決める。Failover Gate 全体として、Part 4 で固定する(§13 の F-P3-7)。

## 5. 1 回の attempt の手順(概要)

```
 0. 前提の確認       Code_SHA、V1 の core のコピーの照合、Target_Origin(§4.2)
 1. idempotency      V2 の台帳に、その Origin の各 Horizon の COMPLETE があるか(§9.1)。すべてあれば ALREADY_COMPLETE で終わる
 2. acquisition      canonical な decision を読み、COMPLETE の時刻と結果を確かめる(§6)
 3. 親               V1 の固定した commit で、S0 の親の行を確かめる(§7)
 4. 特徴量           米国債・財務省・CFTC の公表日程を取得し、特徴量を作る(§8)
 5. 計算             V1 の core で、残りの Horizon の行を作る(§3)
 6. transaction      V1 Part 4 §3 の手順を V2 の台帳に(§9)
 7. 記録             attempt の結果を追記のみで記録する(§10.2)
```

- 手順 2・3・4 のどれかで「まだ」と判断した場合は、COMPLETE を書かずに終わり、後の attempt に任せる(§6.3、§7.5、§8.3)。

## 6. acquisition state を読む(Requirements §4.1、Part 1 §9.6)

### 6.1 canonical な decision

- V2 main の `records/decision/decisions.csv` で、Target_Origin の COMPLETE の行のうち、V2 main の履歴で最初に入ったものを canonical とする(Part 1 §9.5)。
- その判定の行の SHA-256 が COMPLETE の行の記録と一致することを確かめる。

### 6.2 COMPLETE の時刻

- canonical な COMPLETE の行を含む commit の `main_entry_time`(Part 2 §8)を、この attempt の実行の中で activity API から求め、保存する(pages、Audit_Repo_Commit_SHA を attempt の記録に残す)。
- `Main_Entered_At ≤ T_info + 20 分(03:20:00 JST)` なら期限内。過ぎていれば、その Origin の acquisition state は **UNDETERMINED**(Part 1 §9.6)。
- `main_entry_time` が UNRESOLVED なら、この attempt では決めない(ACQUISITION_STATE_PENDING として終わり、後の attempt に任せる)。

### 6.3 結果による分岐

| acquisition state | この attempt の動き |
|---|---|
| canonical な COMPLETE がまだない | ACQUISITION_STATE_PENDING で終わる。後の attempt に任せる。03:20 を過ぎた後の attempt でも COMPLETE がなければ、§6.2 と同じく UNDETERMINED |
| SUCCESS(期限内) | 手順 3 に進む。選ばれた snapshot(Selected_Execution_ID、Selected_Content_SHA256)を手順 4 で使う |
| FAILURE、または UNDETERMINED | **M1 の行を発行しない**。attempt の記録に ACQUISITION_NOT_SUCCESS と書いて終わる(Requirements §4.1 の「SUCCESS で COMPLETE していることを確かめてから進む」。§13 の F-P3-3) |

## 7. S0 の親の行の確認(Requirements §4.3)

### 7.1 読む場所

- V1 の repository(public)を read-only で取り込み、その時点の main の HEAD の SHA を **V1_Parent_Commit_SHA** として attempt の記録に残す。以下の確認は、すべてこの commit の上で行う。
- V2 の credential は、V1 の repository に書き込めない(§10.1)。

### 7.2 V2_S0_PARENT_CHECK(Storage Verification Gate の不変条件を V2 自身が検証する。F-P3-1)

V1 の `forward/verify.py` は、S0 を書いた run 自身が、その run の期待する行(`expected_this_run.json`。commit されない)と手元のファイルを、origin/main から読み直したものと照合する。読む側の V2 は、この入力を再現しない。代わりに、**verify.py が守る不変条件を、固定した V1_Parent_Commit_SHA の上で V2 自身が検証する**。

```
V2_S0_PARENT_CHECK(Origin, Horizon, V1_Parent_Commit_SHA) → PARENT_OK(Run_ID) | PARENT_NOT_READY(reason) | PARENT_INVALID(reason)
```

**正式の検査(すべて V2 自身が行う。順に)**

| # | 不変条件 | 通らなかったとき |
|---|---|---|
| P1 | **serialization**: `ledger/forecasts.csv` と `ledger/runs.csv` が UTF-8 の CSV として厳密に読め、ヘッダーが V1 の forward/issue.py の列と完全に一致する | PARENT_INVALID(LEDGER_FORMAT) |
| P2 | **一意性**: USDJPY・CHFJPY・INRJPY のそれぞれについて、Model = `S0-EMPCLIM-STD-EXP-V1`、その Origin・Horizon の行がちょうど 1 つある | 0 なら PARENT_NOT_READY(PARENT_ROWS_MISSING)。2 つ以上なら PARENT_INVALID(PARENT_ROWS_DUPLICATED) |
| P3 | **Run_ID の結合**: 3 つの行の Run_ID が同じで、`ledger/runs.csv` にその Run_ID の行がちょうど 1 つあり、Mode = `formal` | PARENT_INVALID(RUN_JOIN) |
| P4 | **締め切り**: 3 つの行の Issued_At_UTC が、その Origin の 08:30:00 JST 以下 | PARENT_INVALID(PARENT_LATE) |
| P5 | **ECB の履歴の hash**: §7.3 で決める ECB の履歴のファイルの SHA-256 が、runs.csv のその Run_ID の Data_CSV_SHA256 と一致し、その最後の日付が Data_Last_Date と一致する | PARENT_INVALID(ECB_HISTORY_HASH) |
| P6 | **pool の決定論的な再生成**: V1 の core の s0link で、§7.3 の ECB の履歴から S0 の pool を凍結済みの S0 のコードで再生成し、3 つの行の Pool_N・Mean_Z・Q10_Z・Q90_Z・Decision_Class と照合する(V1 Impl Part 3 §4 と同じ) | PARENT_INVALID(POOL_MISMATCH) |

- すべて通れば PARENT_OK(Run_ID)。
- 各検査は、保存した入力(固定した commit のファイル)だけで決まる純粋な関数とする。Part 4 は、同じ V1_Parent_Commit_SHA で再計算する。

**補助の証拠(正式の検査ではない)**

- Run_ID の `<run_id>-<run_attempt>` について、V1 の repository の Actions の API で、workflow が `.github/workflows/forward.yml`、event が `schedule`、conclusion が `success`、「Storage Verification Gate」の step が `success` であることを問い合わせ、応答を保存する。
- 結果は attempt の記録に残すが、PARENT_OK の条件にはしない。正式の検査と食い違う場合(例: 正式の検査は通るが、V1 の verify の step が success でない)は、監査の記録として Part 4 に報告する。

**読む範囲**

- V2 が V1 の台帳から読むのは、P1〜P6 に要る列と行だけである。ここで読むのは、S0 の 3 行、runs.csv の 1 行、§7.3 の ECB の履歴。V1 の M1-MACRO の台帳は、§12 の推定の履歴のためにだけ、V1 の core が使う列を、プログラムで読む。どれも画面に出さず、記録には hash だけを残す。

### 7.3 S0 の pool の再生成に使う ECB の履歴

- V1 の S0 は、発行のたびに ECB の履歴を V1 の repository の **`data/ecb/eurofxref-hist.csv`** に書く(V1 の forward/issue.py の DATA)。
- V2 は、**S0 の 3 行を V1 の main に初めて入れた commit**(V1_Parent_Commit_SHA から履歴をたどり、`ledger/forecasts.csv` にその 3 行が初めて現れる commit)の tree にある `data/ecb/eurofxref-hist.csv` を、read-only で読む。それは、その S0 の run が書いたファイルである。
- その SHA-256 は、P5 で runs.csv の Data_CSV_SHA256 と照合する。
- V1 の M1 の発行は、発行の時点の V1 の main のファイルを読む。V2 は、S0 の run が書いた時点のファイルを使う点で、より厳密に固定する(§13 の F-P3-9)。

### 7.4 Part 4 のための記録

- Part 4 は、S0 の親が 08:15:00 JST までに使えるようになったかを、V1 の repository の activity API で判定する(Requirements §7.5)。この Part は、PARENT_OK を得た attempt の記録に、V1_Parent_Commit_SHA と、3 つの行の Run_ID を残す。Part 4 はこれを手がかりに、S0 の行を V1 の main に入れた commit を特定する。

### 7.5 結果による分岐

- PARENT_NOT_READY の Horizon は、この attempt では発行しない。後の attempt に任せる(V1 の PARENT_ROWS_MISSING と同じ扱い)。
- PARENT_INVALID の Horizon も発行しない。attempt の記録に理由を残す(後の attempt で直ることは想定しないが、確かめ直すことは妨げない)。
- 一部の Horizon だけ PARENT_OK の場合は、PARENT_OK の Horizon だけを手順 4 以降に進める(Issuance の単位は (Origin, Horizon)。Requirements §6.5)。

## 8. 特徴量(feature readiness)

### 8.1 取得するもの(V1 と同じ)

- V1 の発行と同じく、attempt の中で次を取得する: 米国債の利回り(Y−1 年と Y 年の年次ファイル)、財務省の国債金利(全期間と当年)、CFTC の公表日程。取得と検査は V1 の core の関数(sources、rates、cftc_schedule)をそのまま使う。
- 保存:
  - 米国債の原データ: **V2 の非公開の保管場所**(§10.3)。V2 repository には、取得元の識別、取得時刻、バイト数、SHA-256 だけ(V1 Impl Part 1 V1.2 §4 と同じ扱い)。
  - 財務省と CFTC の公表日程: V2 repository に公開で保存する(V1 と同じ)。

### 8.2 CFTC の snapshot

- F_POS には、canonical な decision が選んだ snapshot **1 つだけ**を、V1 の `cftc_feature.forward` に渡す(snapshots = [選んだ snapshot])。Retrieved_At は manifest の Retrieved_At_Runner、normal は Content_Check = OK、SHA-256 は Content_SHA256。
- V2 の USABLE の条件(時計の不確かさで窓を狭めた条件)は、V1 の窓の条件より厳しいので、選んだ snapshot は V1 の `forward` の窓の検査にも通る。通らなければ、実装の誤りとして発行しない(PIPELINE_FAILURE)。
- V1 の公表日程の規則(`cftc_schedule.for_tinfo`)、古さの判定などは、V1 の core のまま。

### 8.3 取得に失敗した場合(FEATURE_NOT_READY)

- V1 の Data Availability Matrix V1 §5 の (b) は、「T_info より後の**すべての**実行で取得の要求が失敗した」場合に ABSTAIN_SYSTEM(FEATURE_UNAVAILABLE)とする。
- **決定**(F-P3-11): 米国債・財務省・CFTC の公表日程のどれかの取得に失敗した attempt は、**最後の attempt** でなければ、発行せずに FEATURE_NOT_READY として終わり、後の attempt に任せる。
- **最後の attempt** は、予定の時刻 S が 08:20 JST の attempt(A・C のどちらから起動したものでも)である。cron の名前ではなく、予定の時刻で決める。それより前の予定の時刻の attempt が、遅れて 08:20 以後に始まっても、最後の attempt ではない。
- 最後の attempt では、失敗した特徴量を V1 の規則どおり unavailable として計算し、発行する。
- 最後の attempt が遅れて 08:30:00 JST 以後に始まった場合は、§4.2 のとおり TOO_LATE で、何も発行しない。unavailable の行を締め切りの後に発行することはしない。
- 結果として、最後の attempt が起動しない、または 08:30 以後に始まった日には、取得に失敗し続けた Origin の行は発行されない。Issuance Gate では、その unit が Issuance-Eligible なら、V2 の側の理由による未発行として扱われる(Requirements §7.5)。

## 9. transaction(V1 Impl Part 4 §3 を V2 の台帳に)

### 9.1 idempotency

- V2 の `ledger/m1_macro_issue_commits.csv` に、その (Origin, Horizon) を含む COMPLETE の行がすでにあれば、その Horizon は ALREADY_COMPLETE として何もしない(Requirements §4.4)。

### 9.2 手順

V1 Impl Part 4 §3 の手順 1〜9 を、V2 の台帳に対して同じ順序で行う。違いは次だけである。

| 手順 | V1 | V2 |
|---|---|---|
| 4・7 の push が競合で失敗 | `git pull --rebase` の後に同じ行で push し直す(最大 5 回) | 手順 4(3 つの台帳の行): V1 と同じ。**手順 7(COMPLETE の行)**: rebase で載せ直さない。V2 main を取り込み直し、その (Origin, Horizon) の COMPLETE がすでにあれば、自分の COMPLETE の commit を捨てて ALREADY_COMPLETE で終わる。なければ、取り込み直した main の上で手順 6 から作り直して push する(§13 の F-P3-5) |
| 二重の発行の防止 | workflow の concurrency の group | A と C は同じ group を共有できないので、上の COMPLETE の push の規則と、手順 1 の前の確認で防ぐ |
| 手順 9 の締め切りの監査 | `audit_log/m1_macro_issue_deadline.csv` | V2 repository の同じ path |

- 手順 4 で push した 3 つの台帳の行で、COMPLETE がないものは UNCOMMITTED として残る(V1 Impl Part 3 §6.4 と同じ)。COMPLETE の競争に負けた attempt の行も、これに当たる。
- 同じ (Origin, Horizon) に COMPLETE の Run が 2 つ以上ある状態は、仕様違反として Part 4 の監査の対象にする(V1 Impl Part 4 §3 と同じ)。

### 9.3 締め切り(Requirements §4.1 の意図した非対称性)

- `Verified_At_UTC`(手順 8 の読み戻しが終わった runner の時刻)≤ その Origin の 08:30:00 JST のときだけ ON_TIME。V1 Impl Part 4 §3 の規則をそのまま使う。TSA の時計の検査はかけない(Requirements §4.1)。
- runner の時刻の記録の形式は V1 と同じ(V1 Impl Part 4 の形式)。Part 2 §2.1 のマイクロ秒の形式は、この欄には使わない(V1 との互換性のため)。

## 10. 記録・credential・保管場所

### 10.1 credential(Requirements §7.1 の 5)

| 用途 | 対象 | 権限 |
|---|---|---|
| V2 の台帳・記録の書き込み | V2 repository | contents の書き込み |
| V2 の米国債の原データ | V2 の非公開の保管場所(§10.3) | contents の書き込み |
| V1 の台帳・ECB の履歴の読み取り | V1 の repository(public) | token なし |
| V1 の Actions の記録の読み取り(補助の証拠) | V1 の repository の Actions の API | 公開の情報の読み取り。V1 に書ける権限を持たない token に限る |
| V1 の開発用 snapshot の非公開の部分の写し(準備の段階で 1 回だけ) | V1 の非公開の保管場所 | 一度だけ使う読み取りだけの credential。使い終わったら破棄し、**V2 の通常の実行環境には置かない**(§3.1) |

- **V2 の通常の実行環境(取得・decision・発行・adjudication)は、V1 の repository にも、V1 の非公開の保管場所にも、書き込みの権限を持つ credential を持たない。V1 の非公開の保管場所を読む credential も持たない**(F-P3-2・F-P3-10)。試験の前に、使う credential の権限の範囲を記録して確かめる(Requirements §7.1 の 5)。

### 10.2 attempt の記録(`records/issuance/attempts.csv`、追記のみ)

列(案): Issuance_Execution_ID、Path、Target_Origin、Scheduled_At、Job_Started_At_Runner、Horizons、Acquisition_Decision_Ref(canonical な decision の行の SHA-256)、Acquisition_Complete_Main_Entered_At、Acquisition_State、V1_Parent_Commit_SHA、Parent_Run_ID、Parent_Check(Horizon ごとの PARENT_OK / NOT_READY / INVALID と理由)、Feature_Fetch(取得ごとの状態)、Result(ALREADY_COMPLETE / ACQUISITION_STATE_PENDING / ACQUISITION_NOT_SUCCESS / PARENT_NOT_READY / PARENT_INVALID / FEATURE_NOT_READY / COMPLETE / LOST_COMPLETE_RACE / PIPELINE_FAILURE / TOO_LATE / NOT_AN_ORIGIN / PATH_DISABLED_FAILOVER)、Run_ID(発行した場合)、Evidence(保存した API の応答などの SHA-256 の一覧)、Code_SHA。

- 証拠のファイルは `records/issuance/<Target_Origin>/<Issuance_Execution_ID>/` に置く。

### 10.3 V2 の非公開の保管場所

- 米国債の原データは公開しない(V1 Impl Part 1 V1.2 §4)。V2 は V1 の非公開の保管場所に書けない(§10.1)ので、**V2 専用の非公開の保管場所**(例: 新しい private repository)を作る。force push と削除を禁止する。
- V1 と同じく、保存の後に別の clone から読み戻して SHA-256 を確かめる。
- V1 の開発用 snapshot の非公開の部分の写し(§3.1)も、ここに置く。

## 11. Holdout(Requirements §7.1 の 2)

- V2 の発行は、Forward の 3 ペアだけを扱う。V1 の core の Holdout の検査(`estimation.HoldoutBreach`)をそのまま使う。
- V1 の開発用 snapshot には、共有の macro の原データ(米国債・財務省・CFTC)と ECB の全通貨の履歴が含まれる。V2 はそれを、V1 の core と同じ使い方(Forward の 3 ペアの計算)にだけ使う。Holdout の 5 ペアの pair 固有の値を read / derive / calculate しない。

## 12. 推定の入力の履歴(E_{t,h}。F-P3-12 を改めた)

### 12.1 原則(決定)

- **推定の履歴は継続し、予測の series だけを分ける。** V2 は新しい統計の Trial ではなく、pipeline の変更である(Requirements §0)。V2 の開始の時点で V1 なら使えた過去の Origin の群を捨てると、推定の情報の集合 E_{t,h} が変わり、同じ Origin・同じ特徴量でも β が変わりうる。それは「統計モデルは変えない」という V2 の根本の条件に反する。
- 禁止するのは、V1 の**予測の結果**を V2 の性能の series に混ぜることである。V1 の過去の特徴量の台帳を、統計モデルが既定で使う履歴として読むことは禁止しない。

### 12.2 V1 の core が使う履歴(事実)

V1 の `forward_run.forward_groups` と `build_rows_for_origin` は、Origin t の推定に次を使う。

| Origin i の範囲 | 特徴量 | S0 の行 | 実現値 | pool |
|---|---|---|---|---|
| i < V1 の最初の Forward の Origin(Horizon ごと) | 開発用 snapshot からの再構成 | 再構成 | 再構成 | 再構成 |
| V1 の最初の Forward の Origin ≤ i < t | V1 の `ledger/m1_macro_features.csv` のうち、COMPLETE の Run の行 | V1 の `ledger/forecasts.csv` の S0 の行 | V1 の `ledger/outcomes.csv` の OBSERVED で、Recorded_At ≤ T_info(t) の行 | ECB の履歴から再生成し、S0 の行と照合 |

### 12.3 V2 の履歴(案)

V2 の adapter は、V1 の `forward_groups` と同じ規則で、**特徴量の出どころだけ**を次のように分ける。ほかの入力(再構成、S0 の行、実現値、pool)は、V1 の core と同じものを、V1 の固定した commit から read-only で読む。

| Origin i の範囲 | 特徴量の出どころ |
|---|---|
| i < V1 の最初の Forward の Origin | 開発用 snapshot からの再構成(V1 と同じ。§3.1 の写しを使う) |
| V1 の最初の Forward の Origin ≤ i < B | **V1 の `ledger/m1_macro_features.csv`**(COMPLETE の Run の行。V1 の core と同じ選び方) |
| B ≤ i < t | **V2 の Forward の `ledger/m1_macro_features.csv`**(COMPLETE の Run の行) |

- **B(V2 の履歴の境界)**: V2 の Forward の最初の Origin(Horizon ごと。Requirements §0 の「Acceptance Gate の PASS と実装の Freeze の後の最初の予定された Origin」)。B は、V2 の Forward の開始の記録(別の preregistration の記録)で固定する(§13 の F-P3-13)。
- V1 の台帳の行は、attempt の V1_Parent_Commit_SHA の上で読み、その SHA を記録する。V1 の台帳は追記のみなので、i < B の行は、後の commit で読んでも変わらない。Part 4 は同じ commit で再計算する。
- V1 の台帳の、i ≥ B の特徴量の行は、V2 の推定に使わない(V1 の Forward は続くが、B 以後の V2 の履歴は V2 の台帳だけ)。

### 12.4 受け入れの試験の期間の発行(案)

- Requirements の Reliability・Failover・Issuance の試験の期間(B より前)にも、V2 は発行する(Issuance Gate)。この期間の発行の推定の履歴は、B がまだないので、**すべて V1 の core と同じ**(§12.2 の表のまま。特徴量は V1 の台帳)とする。
- 試験の期間の V2 の行は、V2 repository の **`ledger_acceptance/`** に置き、Forward の `ledger/` と分ける。試験の期間の行は、V2 の推定の履歴にも、V2 の性能の series にも入れない(§13 の F-P3-13)。

## 13. Finding

| # | 内容 | 分類 | この版の扱い |
|---|---|---|---|
| F-P3-1 | **verify.py を読む側で実行し直せない。** V1 の Storage Verification Gate は、S0 を書いた run 自身の `expected_this_run.json`(commit されない)と手元のファイルを使う。Requirements §4.3 の「同じ検証の論理を V2 の側で実行し直す」は、文字どおりには実装できない | Requirements の文言と V1 の構造の食い違い / **REVISE(v0.1 で反映)** | §7.2。V2 自身が P1〜P6(serialization、一意性、Run_ID の結合、締め切り、ECB の履歴の hash、pool の決定論的な再生成)を検証する。V1 の Actions の成功は補助の証拠 |
| F-P3-2 | **V1 の非公開の保管場所の読み取り。** V1 の core の推定は、開発用 snapshot の非公開の部分(米国債の過去の原データ)を使う。V2 は、V1 の非公開の保管場所を読む必要がある | V1 の構造からの帰結 / **REVISE(v0.1 で反映)** | §3.1。準備の段階で 1 回だけ、V2 の非公開の保管場所にバイトで同じに写し、source の commit・blob・SHA-256 を manifest に残す。通常の実行環境は V1 の credential を持たない |
| F-P3-3 | **acquisition が SUCCESS でない Origin の扱い。** Requirements §4.1 は「SUCCESS で COMPLETE していることを確かめてから進む」とする。V1 の意味では、CFTC の snapshot がない Origin でも、M1 の行は ABSTAIN_SYSTEM(FEATURE_UNAVAILABLE)として発行される | Requirements の文言と V1 の発行の意味の違い / **ACCEPT / CLOSE** | §6.3。M1 の行を発行しない。評価での分母と欠けた Origin の扱いは、Part 4 と V2 の評価の仕様で固定する |
| F-P3-4 | **V2 の行の区分。** 列を増やさず、Run_ID の形(`V2-…`)と置き場所で区別する | 実装上の選択 / **ACCEPT / CLOSE** | §2 |
| F-P3-5 | **COMPLETE の push の競合。** V1 は push の失敗で `git pull --rebase` して同じ行を push し直す。A・C が同時に走ると、rebase で COMPLETE が 2 回入りうる | 実装上の選択(Requirements §4.4 の具体化)/ **ACCEPT / CLOSE** | §9.2。COMPLETE の commit は rebase しない |
| F-P3-6 | **V1 の core と V2 の adapter の分離、同一性の確認。** V1 の forward_run.py は入出力と計算が混ざっている | 実装上の選択 / **REVISE(v0.1 で反映)** | §3.2。合成のデータに加えて、固定の fixture の入力で、V1 の orchestration と V1 の core + V2 の adapter の出力をバイトで比べる。性能の値は見ない |
| F-P3-7 | **強制 failover の窓の発行。** | Part 1 §10 で後に回した部分 / **DEFER → Part 4** | §4.3 の案を Part 4 で Failover Gate 全体として固定する |
| F-P3-8 | **発行の起動の量。** A・C ともに 10 回なら、1 日 20 回の job になる。取得と decision も合わせると、GitHub Actions と C の provider の利用の量が増える | 運用の確認 / **DEFER → C2 の選定** | C2 の provider の選定で、量と料金を確かめる |
| F-P3-9 | **ECB の履歴の読み取り。** S0 の pool の再生成に、V1 の repository の `data/ecb/eurofxref-hist.csv` を、固定した commit で読む | 実装上の選択 / **ACCEPT / CLOSE** | §7.3。v0.1 で、読む commit を S0 の 3 行を初めて入れた commit に固定し、path を `data/ecb/eurofxref-hist.csv` に直した |
| F-P3-10 | **Requirements §7.1 の 5 の「V1 の repository」の範囲。** V1 の非公開の保管場所(fx-ledger-private-raw)も、V1 の repository に含めて扱う | Requirements の解釈 / **REVISE(v0.1 で反映。F-P3-2 と同じ)** | §10.1。通常の実行環境は、V1 のどちらの repository にも書けず、V1 の非公開の保管場所を読む credential も持たない |
| F-P3-11 | **特徴量の取得の失敗で、後の attempt を待つ。** V1 の実装は、取得に失敗するとすぐに unavailable として発行する。V1 の Data Availability Matrix の (b) は「T_info より後のすべての実行で失敗した」場合の ABSTAIN を定める | orchestration の選択(統計の規則は変えない)/ **ACCEPT / CLOSE WITH CLARIFICATION** | §8.3。最後の attempt は予定の時刻 08:20 の attempt。08:30 以後に始まれば TOO_LATE で、unavailable の行を後から出さない |
| F-P3-12 | **推定の履歴の出どころ。** V2 の series は、V2 の最初の Forward の Origin から V2 の台帳だけを使い、V1 の Forward の期間は gap とする | モデルの同一性と series の分離に関わる選択 / **BLOCKING / REVISE(v0.1 で反映)** | §12。gap の案を取り下げた。B より前は V1 の core が使う V1 の台帳の記録を read-only で使い、B 以後は V2 の台帳だけ。予測の series は完全に分ける |
| F-P3-13 | **履歴の境界 B と、受け入れの試験の期間の行。** B を V2 の Forward の最初の Origin とし、別の preregistration の記録で固定する。試験の期間の発行は、推定の履歴を V1 の core と同じにし、行を `ledger_acceptance/` に分けて、V2 の履歴にも性能の series にも入れない | 追加(Claude)。Requirements §0 の具体化 | §12.3、§12.4。むすびさんに判断していただきたい |

## 14. むすびさんに判断してほしいこと

1. **F-P3-12(§12)**: 推定の履歴を、B より前は V1 の台帳、B 以後は V2 の台帳とする分け方。V1 の core と比べて、特徴量の出どころだけを分ける(ほかの入力は V1 と同じものを V1 の固定した commit から読む)。
2. **F-P3-13(§12.3、§12.4)**: B = V2 の Forward の最初の Origin とし、別の記録で固定すること。試験の期間の発行は V1 と同じ履歴を使い、行を `ledger_acceptance/` に分けること。
3. **F-P3-1(§7.2)**: P1〜P6 の不変条件。とくに P5(ECB の履歴の hash を runs.csv の Data_CSV_SHA256 と照合)と、§7.3 で読む commit を「S0 の 3 行を初めて入れた commit」に固定すること。
4. **F-P3-2・F-P3-10(§3.1、§10.1)**: 1 回だけの写しの手順と、通常の実行環境が V1 の credential を持たないこと。
5. **F-P3-6(§3.2)**: 固定の fixture の選び方(V1 の既存の非性能の fixture を使うか、新しく固定するか)。
6. **F-P3-11(§8.3)**: 最後の attempt の定義と、それが起動しない日の帰結。
