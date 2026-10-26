# M1-MACRO-PIPELINE-V2 — pipeline 要件メモ(DRAFT v0.7 — Requirements Freeze Candidate FINAL)

- 状態: **DRAFT v0.7 — Requirements Freeze Candidate FINAL**(Claude、2026-10-26)。むすびさんの確認待ち。**まだ Freeze していない。** むすびさんの最終監査(v0.6)で、この 3 点が正しく統合されれば Requirements 側に Freeze を妨げる未決事項はない、とされた。
- 前の版: v0(blob ede24e7e…)、v0.1(blob b7e4aa92…)、v0.2(blob b2e3a9d4…)、v0.3(blob 7212a97b…)、v0.4(blob 1a698237…)、v0.5(blob 3368b461…)、v0.6(blob 597e0a03…)。どれも書き換えずに残してある。
- v0.6 からの変更: むすびさんの最終監査(2026-10-26 16:02 JST、v0.6 = FREEZE CANDIDATE REVIEW PASS WITH 3 CLOSURE FIXES)の 3 点だけを統合した。**新しい設計は加えていない。**
  1. **Issuance_Adjudication_Time = 08:45:00 JST**。08:15 の S0 cutoff → 08:30 の issuance deadline → 08:45 の adjudication。08:45 に 1 回だけ判定し、append-only で確定する。08:45 の時点で V1 の server 側の証拠を得られず、S0 が 08:15 までにあったかを判定できなければ **ELIGIBILITY_UNDETERMINED → Issuance Gate FAIL**(分母から除かない)(§6.5、§7.5)。
  2. **Issuance の単位 = (Origin, Horizon)**。Reliability の単位は Origin / T_info の窓のまま。各 unit が Issuance-Eligible になるには、その Horizon の USDJPY・CHFJPY・INRJPY の 3 ペアすべての正式の S0 の親が 08:15 までにそろい、検証に PASS していることを要する。「Eligible の窓」を **Issuance-Eligible Unit** に改めた(§6.5、§7.5)。
  3. **Issuance の ON_TIME は V1 Part 4 の Verified_At_UTC 規則をそのまま継承する。** TSA による時計の検査を発行の締め切りに適用しないことを、**意図した非対称性**として明記した(§4.1)。
- v0.6 までの変更の経緯は、前の版の冒頭を参照。
- 根拠: OPS-FORWARD-01(blob 17b02eae…)、OPS-FORWARD-02(blob 052251bc…)、F14-a(V2 PIPELINE-DESIGN FINDING / CONFIRMED)、F8-a・F11-a(Freeze の記録で使った activity API の照合と、その落とし穴)。
- このメモではしないこと: V1 の workflow・code・config の変更、V2 の本番取得、Development Replay、Holdout の計算。

---

## 0. 名称と位置づけ(決定済み。v0.2 から変更なし)

- **名称(暫定)は M1-MACRO-PIPELINE-V2。** 新しい統計 Trial にはしない。予測モデル、特徴量、推定の方法、評価の仕様は M1-MACRO-V1 をそのまま引き継ぐ。
- 変えるのは acquisition / trigger / provenance / issuance orchestration だけ。
- **V1 の Forward は V1 のまま続ける。** V1 の 104 週の確認的な証拠を、途中から V2 に付け替えない。
- **Pipeline V2 の Forward の開始点**: Acceptance Gate の PASS と、実装の Freeze の完了を待ち、その後の最初の予定された Origin とする。V1 の 104 週の series には混ぜない。
- **V2 の series の役割**は、次の 2 つに分ける。期間と評価の仕様は、それぞれ別に Freeze してから決める。
  - pipeline の信頼性の証拠
  - 予測性能の証拠
- V2 にも自動的に別の 104 週を設ける、ということはまだ決めない。統計モデルが V1 と同じだからである。

## 1. 観測された事実(v0.2 から変更なし)

| 項目 | 2026-10-20〜10-25(main に統合した 2026-10-20T12:08Z の後) |
|---|---|
| 予定された定時実行 | 12 回(cron "40 15,17 * * *"、6 日分) |
| 実際に起動した定時実行 | **6 回**(1 日 1 回)。15:40Z に起動した回は 0 回 |
| 起動した時刻 | 10/20 19:33:29Z、10/21 19:33:35Z、10/22 19:26:25Z、10/23 19:31:25Z、10/24 18:20:30Z、10/25 18:32:25Z |
| 起動したときの CFTC の取得 | 6 回とも成功 |
| T_info の窓に入った取得 | **0 / 6 日** |
| M1 の発行(Origin 10/22 1D、10/23 1D、10/25 1W/4W) | すべて COMPLETE / ON_TIME。FORECAST は 0 件(12 行すべて ABSTAIN_SYSTEM / FEATURE_UNAVAILABLE) |
| 取得から main への push(server 時刻)までの遅れ(V1、6 件) | 2〜5 秒。6 件とも push が 1 回目で通った場合 |
| 根本原因 | 特定していない |

- この版では、新しい運用の記録は読んでいない。Origin 2026-10-26 以降の結果は OPS-FORWARD の次の記録で扱う。

## 2. 守る原則(v0.2 から変更なし)

1. **V1 は変えない。**
2. **V1 と V2 を分ける。**
   - V2 の設計、試験、試験取得は、**別の repository** で行う(決定済み)。V1 の canonical な Forward(この repository の data/m1macro/ と ledger/m1_macro_*)には、物理的に触れない。
   - V2 の行には、V2 の検証用であることを示す区分を付けて、論理的にも分ける。
3. **救済しない。** V2 で取得した snapshot を V1 の発行に使わない。
4. **範囲は acquisition / trigger / provenance / issuance orchestration に限る。** 統計モデル、特徴量の定義、評価の仕様は変えない。S0 のモデルも変えない。
5. **基準は事前に固定する。** Acceptance Gate の閾値、δ、ε は、V2 の試験 telemetry を見る前に固定する。
6. **単一障害点を減らす。**

## 3. 取得の窓、記録、使えるかの判定

### 3.1 窓(凍結済みの規則。変えない)

- Origin t の CFTC snapshot として使えるのは、取得の時刻が (T_info(t) − 6h, T_info(t)] にあるものだけ。
- T_info は Origin の日の 03:00 JST。窓は前日の 12:00Z から 18:00Z まで。
- 窓の中に複数あれば、最も遅いものを使う。

V2 は、この規則を変えない。V2 が加えるのは、「取得の時刻が窓の中にあった」と監査の上で主張できることを求める**V2 provenance acceptance rule** である(§3.4、§10。決定)。

- これは V1 の feature / data-availability の定義を変えるものではない。
- この規則は、V1 の規則で使えるものを減らす方向にしか働かず、増やす方向には働かない。
- 時計の不確かさのために窓の境界の近くで判定できない取得は、fail-closed で捨てる(§10.4)。

### 3.2 取得 1 回ごとの記録(必須)

| 欄 | 意味 | どこに記録するか |
|---|---|---|
| Target_Origin | この取得が対象とする Origin(trigger の時点で決まる) | manifest |
| Acquisition_Path_ID | 取得した経路(A、C など) | manifest |
| Execution_ID | 取得した実行の ID | manifest |
| Retrieved_At_Runner | 取得した実行環境の時計の値。応答の本文を受け取り終えた時点の UTC | manifest |
| Content_SHA256 | 取得した原ファイルのバイト列の SHA-256 | manifest |
| Clock_Check_Pre | 取得の前に測った runner の時計の検査(§10) | manifest |
| Manifest_SHA256 | Acquisition_Manifest の正規のバイト列の SHA-256 | anchor の記録 |
| Clock_Check_Post | 取得の後に測った runner の時計の検査(§10) | anchor の記録 |
| Anchor_G | G の証拠と検証の結果(§9.2) | anchor の記録 |
| Anchor_R[i] | i 番目の TSA の token と検証の結果(§9.3) | anchor の記録 |
| Valid_Anchor_Timestamps | 検証に通った anchor の時刻の集合(§9.1) | 判定の記録 |
| Server_Anchored_At | 派生値。`min(Valid_Anchor_Timestamps)`(§9.1) | 判定の記録 |
| Attempt_Status | USABLE、または §6.2 の原因コード | 判定の記録 |

- Server_Anchored_At は**生データの欄ではない**。G と R の個別の時刻と証拠を残したうえで、そこから決まる値である。片方の anchor の時刻だけを残して、もう片方を消すことはしない。
- 「実行した時刻」だけを示す証拠(外部の scheduler の実行記録など)は、それだけでは anchor にならない(§9.5)。

### 3.3 Acquisition_Manifest(追加)

取得 1 回ごとに、anchor より前に manifest を 1 つ作る。G と R は、どちらもこの manifest を anchor する。

- 中身: Target_Origin、Acquisition_Path_ID、Execution_ID、Retrieved_At_Runner、Content_SHA256、原ファイルの repository 内の path、Clock_Check_Pre。
- 正規のバイト列: key を固定の順に並べた JSON、UTF-8、改行は LF、末尾に改行を 1 つ。正規化の手順は V2 の Code_SHA の対象にする。
- manifest は、anchor を取ったあとに書き換えない。anchor に関係する情報(token、API 応答、Clock_Check_Post)は、別のファイル(anchor の記録)に書く。manifest に token を入れると、hash が循環するからである。
- こうすると、Retrieved_At_Runner の値そのものも anchor に縛られる。anchor を取ったあとで Retrieved_At_Runner を書き換えれば、Manifest_SHA256 が合わなくなる。

結合の経路:

```
G:  activity の記録 → commit → tree → manifest のバイト列 → Content_SHA256 → 原ファイルのバイト列
R:  timestamp token の messageImprint → Manifest_SHA256 → manifest のバイト列 → Content_SHA256 → 原ファイルのバイト列
```

### 3.4 使えるかの判定(決定)

取得 1 回が USABLE であるのは、次がすべて成り立つときである。

```
(1) provenance が完全で、照合に通る                                      (§3.2、§3.3)
(2) 時計の健全性の検査に通る:  max(|e_lo|, |e_hi|) ≤ ε                  (§10.3)
(3) 時計の不確かさを入れても窓の中:
        Retrieved_At_Runner − e_hi > T_info − 6h
        Retrieved_At_Runner − e_lo ≤ T_info                              (§10.4)
(4) 有効な anchor が 1 つ以上ある:  |Valid_Anchor_Timestamps| ≥ 1         (§9.1)
(5) 前後関係の整合:  Retrieved_At_Runner ≤ Server_Anchored_At + ε          (§10.5)
(6) anchor が遅れていない:  Server_Anchored_At ≤ T_info + δ,  δ = 300 秒   (§9.4)
```

- δ = 300 秒、**ε = 6.0 秒**(§10.6)。どちらも決定。
- (1)〜(6) は、すべて Decision_Time(§6.4)の時点で判定する。G が (4) の有効な anchor に入るのは、Decision_Time までに GitHub の API に直接問い合わせて検証できた場合だけである(§9.2)。
- (3) は v0.2 の `Retrieved_At_Runner ∈ (T_info − 6h, T_info]` を、時計の不確かさの分だけ内側に狭めたものである。e_lo = e_hi = 0 なら v0.2 と一致する。

## 4. 対象にする orchestration

```
CFTC acquisition → [Decision_Time: acquisition state を確定] → feature readiness → S0 parent readiness → M1 issuance
```

S0 のモデルは変えない。対象は、この順に行う運用の仕組みである。

### 4.1 acquisition の判定と発行を分ける(決定)

- Decision_Time(= T_info + 15 分、通常は 03:15 JST)に、その Origin の **acquisition state を不可逆に確定する**(§6.4)。
- M1 の issuance orchestration は、Decision_Time の**後に**始める。
- 発行には、確定した acquisition state に加えて、**feature readiness と S0 parent readiness** が必要である。
- 発行は、単一の固定の時刻ではなく、**固定の attempt schedule と最終の deadline** で行う。最終の deadline は既存どおり **08:30 JST**(V1 の Part 3・Part 4 と同じ。締め切りの判定は V1 Part 4 §3 の Verified_At_UTC ≤ 08:30 JST の規則をそのまま引き継ぐ)。
- **意図した非対称性(決定)**: acquisition の provenance では、TSA による runner の時計の検査を要求する(§10)。一方、Issuance の ON_TIME は V1 との互換性を優先し、V1 Part 4 の Verified_At_UTC の規則を継承する。この非対称性は既知の設計上の性質であり、V2 では変更しない。V2 の目的は F14-a を起点とした pipeline の再設計であって、発行の締め切りの意味そのものを定義し直すことではないからである。

### 4.2 S0 parent readiness との整合(v0.5 で確認した事実)

**凍結済みの V1 の仕様から確認したこと**(preregistration/ の M1-MACRO-IMPL-PART3-V1、PART4-V1、forward/issue.py)

1. M1 の発行は、**同じ Origin の S0 の行が正式の台帳に書かれ、Storage Verification Gate(verify.py)が SUCCESS になった後に始める**。親の行は V1 の repository の origin/main から読む(Part 4 の §3 の前提)。
2. S0 は、V1 の forward-ledger の workflow(forward/issue.py)が発行する。発行するのは **Origin の当日(JST)で、08:30 JST より前の実行だけ**。準備ができていなければ、同じ日の後の実行で再試行する。08:30 を過ぎた Origin には予測を出さない。
3. forward-ledger の定時の予定は 00:40、02:40、04:40、06:40、07:55 JST(と、締め切り後の 09:15 JST)。

**実行記録から確認したこと**(Actions の実行のメタデータだけ。台帳の値は見ていない)

2026-10-21〜10-26 の Origin の日について、08:30 JST より前に起動した forward-ledger の定時実行:

| Origin の日 | 1 回目の起動(JST) | 結果 | 2 回目の起動(JST) | 結果(実行の終了) |
|---|---|---|---|---|
| 10-21 | 04:34 | failure | 07:39 | success |
| 10-22 | 04:36 | failure | 07:45 | success(07:46) |
| 10-23 | 04:29 | failure | 07:45 | success(07:46) |
| 10-24 | 04:32 | success | 07:37 | success(07:39) |
| 10-25 | 03:21 | failure | 06:52 | success(06:54) |
| 10-26 | 03:33 | failure | 07:02 | success(07:04) |

- 00:40 と 02:40 JST の予定は、この 6 日間で一度も起動していない。起動した回も、予定より約 2〜3 時間遅れている。M1 の CFTC の取得で見た GitHub の定時実行の問題(F14-a)と同じ傾向である。
- 1 回目の起動の多くが failure になっている。原因は調べていない(この版の範囲の外。V1 の運用の記録で扱う)。
- 結果として、この 6 日間では、**S0 の親の行が使えるようになるのは、ほとんどの日で 06:54〜07:46 JST、つまり締め切りの 45〜95 分前**だった。

**ここから言えること**

- V2 の発行は、V1 の S0 の発行に依存する。V2 は V1 を変えないので、**S0 の起動の信頼性を V2 の側で直すことはできない**。S0 が 08:30 までに出なければ、V2 の M1 も親がないので発行できない。この分は Issuance Gate の分母から事前の規則で分ける(§6.5、§7.5)。
- S0 が締め切りの近くで使えるようになっても、発行の機会が複数残るように attempt を置く(§4.4)。これは 6 日間の観測値に合わせ込むためではなく、設計の原則である。

### 4.3 V2 が S0 の親の行を読む方法(決定)

- V2 は、V1 の repository の正式の台帳を**読むだけ**で、書かない。読んだ時点の V1 の commit の SHA を記録する。
- V1 の Part 4 と同じく、親の行について V1 の Storage Verification Gate と同じ検証の論理(Freeze 済みの verify.py)を **V2 の側で実行し直し**、SUCCESS になることを発行の前に確かめる。この検証の実装も V2 の Code_SHA の対象にする。
- **V2 の実行の credential には、V1 の repository への書き込みの権限を与えない**(「書かない」だけでなく「書けない」)。§7.1 の 5 で確かめる。
- V1 の data/ と ledger/ に V2 の行がないことは、§7.1 の 1 で機械的に確かめる。
- V1 の S0 の台帳に入っているのは Forward の 3 ペア(USDJPY、CHFJPY、INRJPY)だけである(forward/ledger_builder.py の PAIRS、forward/config.json の sealed_holdout)。S0 の行を読んでも、Holdout の 5 ペアには触れない(§7.1 の 2)。

### 4.4 発行の attempt schedule と idempotency(決定)

- **attempt schedule(JST)**: 03:20 / 04:00 / 05:00 / 06:00 / 07:00 / 07:30 / 07:45 / 08:00 / 08:10 / 08:20。
- **最終の deadline**: 08:30 JST。ON_TIME の判定は V1 Part 4 §3 の規則(Verified_At_UTC ≤ 08:30 JST)をそのまま引き継ぐ。
- **起動**: A と C の両方の経路から、同じ attempt schedule を起動できるようにする。10 個の時刻のすべてを毎回両方の経路から起動することは要求しない。要求するのは、「schedule そのものが起動しない」という F14-a 型の障害に耐えることである。
- **idempotency**: 各 attempt は、始めに、同じ Origin・Horizon について正式の COMPLETE の transaction がすでにあるかを確かめる。あれば **ALREADY_COMPLETE** として何も書かずに終わる。
- **二重の発行を起こさない**: 2 つの attempt が同時に走っても、COMPLETE が 2 回記録されることはあってはならない。V1 Part 3 §6.4・Part 4 §3 の transaction の手順(最後の COMPLETE の追記と読み戻し)を V2 でも使い、COMPLETE の追記の前に同じ Origin・Horizon の COMPLETE があれば、追記せずに ALREADY_COMPLETE で終わる。push が競合で拒否された attempt は、取り込み直したあとで COMPLETE の有無を確かめ直し、あれば書かずに終わる。
- 各 attempt の結果(起動した経路、開始の時刻、ALREADY_COMPLETE / PARENT_NOT_READY / FEATURE_NOT_READY / COMPLETE / FAILED など)は、追記のみで記録する。

## 5. 候補と位置づけ(v0.1 から変更なし)

- **主候補**: A(GitHub の中で、早い時刻に何度も起動する)、C(外部の独立した trigger)、E(冗長化。本命だが、採用はまだ Freeze しない)、F(監視と通知)。
- **補欠**: B、D。
- **最初に比べる構成**: A + C を、F で監視する。

## 6. 試験の単位と、SUCCESS / FAILURE への写像(決定)

### 6.1 試験の単位

- 1 回の試験は、M1 の Origin がある T_info の窓 1 つ(試験窓)。
- 試験窓 w に属する取得は、manifest の Target_Origin が w の Origin であるものとする。時刻で振り分けない。窓の外で行われた取得も、その窓の取得として数えて OUTSIDE_WINDOW と記録するためである。

### 6.2 取得 1 回ごとの判定(固定した順に検査する)

検査は次の順に行い、最初に通らなかった段階の原因コードを、その取得の Attempt_Status とする。すべて通れば USABLE。

| 順 | 検査 | 通らなかったときのコード |
|---|---|---|
| 1 | §3.2・§3.3 の記録がそろい、manifest の正規化と Content_SHA256 の再計算が一致し、Execution_ID と Acquisition_Path_ID が実在の記録と一致する | PROVENANCE_INVALID |
| 2 | 取得した中身が、V1 と同じ内容の検査に通る | CONTENT_INVALID(決定) |
| 3 | 時計の健全性の検査(§3.4 の (2)) | CLOCK_INVALID(sanity) |
| 4 | 時計の不確かさを入れた窓の判定(§3.4 の (3)) | OUTSIDE_WINDOW |
| 5 | 有効な anchor が 1 つ以上ある(§3.4 の (4)) | NO_VALID_SERVER_ANCHOR |
| 6 | 前後関係の整合(§3.4 の (5)) | CLOCK_INVALID(consistency) |
| 7 | anchor の遅れ(§3.4 の (6)) | ANCHOR_LATE |

### 6.3 試験窓の判定

```
試験窓 w が SUCCESS  ⇔  w に属する取得のうち、Attempt_Status = USABLE のものが 1 つ以上ある
それ以外は すべて FAILURE
```

- 使う snapshot は、USABLE のもののうち Retrieved_At_Runner が最も遅いもの(§3.1 の規則のまま)。
- FAILURE の窓には、原因コードを記録する。
  - w に属する取得が 1 つもない: **NO_ACQUISITION**
  - 取得はあるが USABLE がない: 検査の順で**最も先まで進んだ取得**のコードを主な原因とする。同じ段階で止まった取得が複数あれば、Retrieved_At_Runner が最も遅いものを採る。ほかの取得のコードも、すべて残す。
  - Decision_Time までに判定が終わらなかった(検証の job が動かなかった、など): **UNDETERMINED**(決定)。これも FAILURE とする。「判定できなかった」を分母から外すと、pipeline の障害を後から欠測として扱えてしまうからである。
- **原因コードは分類のためのものであって、Reliability Gate から外す理由にはならない。** どのコードの FAILURE も、§7.2 の失敗の 1 回として数える。2 回続けて FAILURE なら、その時点で即 FAIL。

### 6.4 判定の時点(Decision_Time)

- 試験窓 w の判定は、Decision_Time(w) に 1 回だけ行い、append-only で記録する。
- **原則(決定)**: Decision_Time(w) は、T_info(w) + δ に、anchor の取得・G と R の検証・SUCCESS / FAILURE の確定に要する**固定の buffer** を加えた時刻とする。`Decision_Time > T_info + 300s` だけでは足りない。
- **値(決定)**: `Decision_Time(w) = T_info(w) + 15 分`。通常は 03:15 JST。anchor の期限 03:05 から 10 分の buffer がある。
- Decision_Time に確定するのは **acquisition state だけ**である。forecast の発行はその後に別に行う(§4.1)。
- 03:15 以後に G が見つかったり、TSA の証拠が届いたりしても、その窓の FAILURE を SUCCESS に変えない。
- Decision_Time のあとに証拠が出てきても、FAILURE を SUCCESS に変えない(救済しない)。
- あとの独立の監査で、判定が実装の誤りのために間違っていたとわかった場合は、記録を書き換えず、Determinism / Audit Gate(§7.3)の FAIL として扱う。

### 6.5 Reliability と Issuance の状態遷移(決定。分母を混ぜない)

**単位(決定)**

- **Reliability の単位** = 一意の Origin / T_info の窓(通常の 60 窓)。
- **Issuance の単位** = **(Origin, Horizon)**。たとえば 1 つの Origin に 1W と 4W があれば、acquisition の Reliability では 1 窓、Issuance では 2 unit(1W で 1 unit、4W で 1 unit)である。
- Issuance の unit は、通常の 60 窓の Origin に属する (Origin, Horizon) だけである。

**状態遷移(決定)**

通常の 60 窓に属する Issuance の unit u = (Origin, Horizon) のそれぞれは、08:45:00 JST の adjudication(§7.5)で、次のどれか 1 つに必ず落ちる。

| acquisition state(03:15 の Decision_Time) | S0 の親(その Horizon の 3 ペア、08:15:00 JST まで) | Reliability Gate への寄与(窓ごと) | Issuance Gate での扱い(unit ごと) |
|---|---|---|---|
| FAILURE(原因コードは §6.3) | (問わない) | **FAILURE 1 個** | **N/A**(分母に入れない) |
| SUCCESS | 3 ペアすべてそろい、検証に PASS(§7.5) | SUCCESS | **評価する**(Issuance-Eligible Unit) |
| SUCCESS | そろっていない、または検証に PASS していないことが、server 側の証拠で確定した | SUCCESS | **PARENT_NOT_READY_BY_CUTOFF**。N/A(分母に入れない。件数は必ず記録して報告する) |
| SUCCESS | 08:45 の時点で server 側の証拠を得られず、**判定できない** | SUCCESS | **ELIGIBILITY_UNDETERMINED → Issuance Gate FAIL**(分母から除かない) |

- Reliability Gate の分母は、**通常の 60 窓すべて**である。NO_ACQUISITION などの FAILURE も分母に入る(§7.2)。
- Issuance Gate の分母は、**通常の 60 窓に属する unit のうち、Issuance-Eligible Unit だけ**である(§7.5)。
- ELIGIBILITY_UNDETERMINED を分母から落とすと、API の障害などで「親があったか分からない unit」を除外できてしまい、Gate の抜け道になる。そのため、除外せずに FAIL とする。
- 03:15 の Decision_Time と 08:45 の adjudication は、完全に別のものである。03:15 は acquisition state だけを確定し、08:45 は issuance の eligibility と結果を確定する。
- この表は試験の前に固定し、試験の途中や後で分母の定義を変えない。
- 強制 failover の 4 窓は、どちらの Gate の分母にも入らない(§7.4)。その窓の発行の結果は記録だけする。

## 7. Acceptance Gate(5 群。すべて AND で判定する)

### 7.1 Safety Gate — 1 件でも違反すれば FAIL

1. V1 の repository の data/m1macro/ と ledger/ に、V2 の行が 0 件であること(機械で確認する)。
2. **Historical Reserve Holdout の 5 ペアについて、pair 固有の market data、return、volatility、feature、forecast、score、correlation、class frequency、その他の派生値を一切 read / derive / calculate しないこと。** 共有の macro raw source である CFTC snapshot そのものの取得は、Holdout contact と数えない(既存の Holdout Seal と整合させるため)。
3. V2 の取得経路のすべての部分(manifest の正規化、G と R の検証、時計の検査、§6 の判定を含む)が、V2 の Code_SHA の対象であること。
4. すべての取得について、§3.2 の記録と、§3.3 の結合の経路が完全であること。
5. **V2 のどの実行の credential(A、C、検証の job、発行の attempt)も、V1 の repository への書き込みの権限を持たないこと。** 試験の前に、使う credential の権限の範囲を記録して確かめる(§4.3)。

### 7.2 Reliability Gate(決定済み。数え方を明確にした)

- **対象は通常の構成の試験窓だけ(決定)。** A や C を意図的に止めた強制 failover の窓は、通常の構成の自然な信頼性を測る試行ではなく、意図的な介入なので、ここには含めない(§7.4)。較正期間のデータ(§10.6)も含めない。
- **(N, k) = (60, 2)**: 通常の試験窓 60 個で、FAILURE が 2 個以下なら PASS。
- **2 個続けて FAILURE なら、その時点で即 FAIL**(60 個の終了を待たない)。「続けて」は、通常の試験窓を Origin の順に並べた列で数える。間に強制 failover の窓が挟まっても、その窓は飛ばして数える(決定。Reliability Gate と Failover Gate を混ぜないため)。
- §6.2・§6.3 のどの原因コードによる FAILURE も、1 個として数える。NO_ACQUISITION、OUTSIDE_WINDOW、ANCHOR_LATE、PROVENANCE_INVALID、CONTENT_INVALID、CLOCK_INVALID、NO_VALID_SERVER_ANCHOR、UNDETERMINED のどれも、除外しない。
- 二項分布で計算した運用特性(むすびさんが独立に再計算して一致を確認):
  - 真の成功率が 90% なら PASS する確率は約 5.30%(誤って採用する確率)。
  - 真の成功率が 98% なら PASS する確率は約 88.13%。
- **この Gate を通っても、成功率が 98% であることを 60 回で証明したことにはならない。** 示すのは「成功率 90% 程度の経路を、約 5% の確率でしか誤って採用しない」ということまでである。
- **上の運用特性は、各回が独立だと仮定した参考値である。Failover Gate を通過しても、独立性が証明されるわけではない。** GitHub の障害のように複数の回にまとめて効く失敗があれば、実際の誤採用の確率は参考値より高くなりうる。
- 2 個連続で即 FAIL とする規則を加えたので、実際に PASS する確率は上の参考値より少し低くなる(より厳しい)。

### 7.3 Determinism / Audit Gate

- snapshot を選ぶ規則が V1 と同じであること。
- hash を計算し直すと一致すること(Content_SHA256、Manifest_SHA256、保存した API 応答と token の hash)。
- **R**: 保存した資料(token、証明書の鎖、失効の情報、manifest、原ファイル)**だけ**から独立に再検証し、同じ t_R,i になること。
- **G**: Decision_Time に行った同時点の検証(G_CONTEMPORANEOUS_VALID)の記録・保存した応答の hash・結果を再計算し、**当時の判定の手順が決定論的に正しかった**ことを確かめる。GitHub 側の記録が保持期間のあとに消えた場合に、保存した応答だけから GitHub 由来であることを再証明できることは**要求しない**(G_LONG_TERM_SELF_CONTAINED = false)。
- 上の 2 つの結果から、同じ Valid_Anchor_Timestamps と Server_Anchored_At になること。
- 経路と実行の ID が、実在の記録と一致すること。
- §6 の判定を、保存した記録から独立にやり直すと、すべての試験窓で同じ SUCCESS / FAILURE と原因コードになること。

### 7.4 Failover Gate(決定)

- **強制 failover の窓は、Reliability の 60 窓とは別枠。** 最小構成は、A を止める窓 2 個と C を止める窓 2 個の、計 4 個。
- 試験全体の最小構成は、**通常の窓 60 個 + 強制 failover の窓 4 個**。
- **置き方(決定)**: 4 つの窓は 60 窓の後にまとめず、**試験期間の中に時間的に散らして置く**。A 停止の 2 窓と C 停止の 2 窓も、それぞれ散らす。
- **試験を始める前に、4 つの Origin を完全に固定する**(決定)。試験の途中で、結果を見てから選び直さない。
- 強制 failover の窓も、§6 と同じ規則で SUCCESS / FAILURE に写す。**4 個すべてが SUCCESS であること**を要求する。1 個でも FAILURE なら Failover Gate は FAIL。
- この Gate が確かめるのは冗長な経路が働くことであって、各回の独立性ではない(§7.2)。

### 7.5 Issuance Gate(決定)

**時刻の役割(決定)**

```
08:15:00 JST  S0 cutoff                 親が間に合ったか
08:30:00 JST  issuance deadline          V2 の発行が間に合ったか(V1 Part 4 の Verified_At_UTC 規則)
08:45:00 JST  Issuance_Adjudication_Time その事実を確定して記録する監査の時刻
```

- 08:45:00 JST に **1 回だけ**判定し、結果は append-only で確定する。その後に V1 の側に遅れて S0 が現れても、過去の判定は変えない。

**Issuance-Eligible Unit の定義(決定)**

```
Issuance-Eligible(Origin, Horizon)
    ⇔  acquisition state(Origin の窓) = SUCCESS
    かつ その Horizon について、USDJPY・CHFJPY・INRJPY の 3 ペアすべての V1 の正式の S0 の親の行が、
         server 側の証拠の上で 08:15:00 JST までに使えるようになっていて、
    かつ それらの行が V1 の Storage Verification Gate と同じ検証(§4.3)に PASS している
```

- **Eligibility の cutoff は 08:15:00 JST**(最後の attempt の 08:20 ではない)。08:20 に S0 が使えるようになって 08:20 の attempt と競合する、という曖昧さを消すためである。
- 「server 側の証拠の上で使えるようになった時刻」は、G と同じ考え方で決める。S0 の親の行を含む V1 の commit が V1 の main に入ったことを示す V1 の repository の activity API の記録の timestamp を、08:45 の adjudication の時点で API に直接問い合わせて確かめる(§9.2 の手順と同じ。commit の author / committer の日時は使わない)。
- 08:45 の時点で、この server 側の証拠を得られず判定できなければ、その unit は **ELIGIBILITY_UNDETERMINED** とし、**Issuance Gate は FAIL** とする(§6.5)。

**合格の条件**

- **すべての Issuance-Eligible Unit の 100% で、V2 の発行が COMPLETE かつ ON_TIME であること。**
- Issuance-Eligible Unit で、V2 の側の理由で未発行・不完全・締め切り超過が **1 件でもあれば、Issuance Gate は FAIL**。
- ELIGIBILITY_UNDETERMINED の unit が **1 件でもあれば、Issuance Gate は FAIL**。
- 08:15:00 JST までに S0 の親(3 ペア)がそろわなかったことが server 側の証拠で確定した unit は **PARENT_NOT_READY_BY_CUTOFF** とし、分母から除く。ただし必ず記録し、件数を報告する。これは V2 の失敗を隠すための欠測の処理ではなく、V2 が制御できない範囲を、事前の規則で分けるものである。
- **Issuance-Eligible Unit が 0 件なら、PASS にしない。INSUFFICIENT_ISSUANCE_EVIDENCE とする。**

## 8. 判断済みの事項

| # | 事項 | 状態 |
|---|---|---|
| 1 | Reliability Gate | 決定: (60, 2)、2 個連続の FAILURE で即 FAIL。原因コードは除外の理由にならない |
| 2 | 使えるかの判定 | 決定: §3.4 の 6 条件。δ = 300 秒、ε = 6.0 秒 |
| 3 | 正式な anchor | 決定: G または R の 1 つ以上。X は補助の provenance |
| 4 | Server_Anchored_At | 決定: `min(Valid_Anchor_Timestamps)`。有効な anchor が 0 なら NO_VALID_SERVER_ANCHOR → FAILURE |
| 5 | δ | 決定: 300 秒 |
| 6 | G の時刻源 | 決定: commit の author / committer の日時は使わない。server 側の証拠だけを使う |
| 7 | ANCHOR_LATE の扱い | 決定: Reliability の失敗 1 回として数える |
| 8 | V2 の Forward の開始点と評価 | 決定(v0.2 のまま) |
| 9 | 試験の置き場所 | 決定: 別の repository |
| 10 | G の有効性 | 決定: G_CONTEMPORANEOUS_VALID のときだけ有効。G_LONG_TERM_SELF_CONTAINED = false |
| 11 | TSA | 決定: R1・R2 の 2 局(運営者も trust / root の鎖も異なる)。A_max = 1.0 秒。R-ACC-1〜13 を採用 |
| 12 | 時計の証拠 | 決定: 主系統は TSA。HTTPS の Date と NTP は補助。事前の較正期間を設け、較正の前に条件を Freeze する |
| 13 | Failover の窓 | 決定: Reliability の 60 窓とは別枠。最小 4 窓(A 停止 2、C 停止 2)。すべて SUCCESS が必要 |
| 14 | 窓を狭める規則 | 決定: V2 provenance acceptance rule。V1 の定義は変えない |
| 15 | CONTENT_INVALID、UNDETERMINED | 決定: 正式に採用。どちらも FAILURE |
| 16 | Decision_Time | 決定: T_info + 15 分(通常 03:15 JST)。acquisition state だけを不可逆に確定する |
| 17 | ε | 決定: E1。ε = D_max + RTT_max + 2·A_max = 2.0 + 2.0 + 2·1.0 = **6.0 秒**(engineering budget) |
| 18 | 較正 | 決定: 連続 7 暦日、経路ごとに実行済みの pair が 100 組以上、p_min = 0.99 を経路ごとに判定。分母は実際に開始された実行。起動しなかった回は TRIGGER_NOT_STARTED として別に集計 |
| 19 | 「2 個連続」と failover の置き方 | 決定: 通常の 60 窓だけの列で数える。failover の 4 窓は散らして置き、開始前に Origin を固定する |
| 20 | TSA がない場合の時計の検査 | 決定: 補助の系統への fallback はしない。CLOCK_INVALID(sanity) |
| 21 | PRE の記録 | 決定: §10.3 の正規の JSON |
| 22 | Holdout の境界 | 決定: §7.1 の 2 |
| 23 | 発行と acquisition の分離 | 決定: §4.1。最終の deadline は 08:30 JST |
| 24 | 発行の attempt schedule | 決定: §4.4 の 10 時刻。A・C の両経路から起動可能。idempotent(ALREADY_COMPLETE)。二重の発行なし |
| 25 | S0 の親の読み方 | 決定: §4.3。read-only、V1 の commit SHA を記録、検証を V2 で再実行。V1 への書き込みの権限を持たない |
| 26 | Issuance Gate | 決定: §7.5。cutoff 08:15:00 JST、すべての Issuance-Eligible Unit で 100% COMPLETE かつ ON_TIME、0 件なら INSUFFICIENT_ISSUANCE_EVIDENCE |
| 29 | Issuance_Adjudication_Time | 決定: 08:45:00 JST に 1 回だけ判定、append-only。判定できなければ ELIGIBILITY_UNDETERMINED → Issuance Gate FAIL |
| 30 | Issuance の単位 | 決定: (Origin, Horizon)。その Horizon の 3 ペアすべての S0 の親が必要。Reliability の単位は Origin / T_info の窓 |
| 31 | Issuance の ON_TIME の時計 | 決定: V1 Part 4 の Verified_At_UTC 規則を継承。TSA の検査は適用しない(意図した非対称性。§4.1) |
| 27 | 分母の分離 | 決定: §6.5 の状態遷移 |
| 28 | TSA の要求の量 | 決定: R-ACC-13 を具体化。試験の開始前に確認。不明なら候補から外す |

## 9. server anchor

### 9.1 Server_Anchored_At の定義(決定)

```
Valid_Anchor_Timestamps = { t_G   | G の検証に通り、manifest との結合を確認できた }
                        ∪ { t_R,i | i 番目の TSA の検証に通り、manifest との結合を確認できた }

Server_Anchored_At = min(Valid_Anchor_Timestamps)     (集合が空でないとき)
集合が空            → NO_VALID_SERVER_ANCHOR → その取得は USABLE でない
```

- **定義(機械的)**: Server_Anchored_At は、**採用された有効な anchor の群のうち、最も早い anchor の timestamp** である。この定義の外の意味づけは、判定に使わない。
- 「有効」とは、その anchor に固有の検証(§9.2 または §9.3)に通り、**さらに対象の Content_SHA256 との結合まで確認できた**ことをいう。G については、さらに Decision_Time までに GitHub の API に直接問い合わせて確認できたこと(G_CONTEMPORANEOUS_VALID)を要する。時刻の文字列があるだけでは有効にならない。
- **G と R の証拠の力は同じではない。** R は、署名された timestamp の token として、TSA に問い合わせずに後から独立に検証できる。G は、Decision_Time の時点で GitHub の server 側の記録と照合する仕組みであり、自己完結した署名付きの timestamp ではない(§9.2)。それぞれ別の検証手順を持ち、どちらの手順も Freeze の対象にする。
- 補足(判定には使わない): R については、min は「署名された証拠として最も早く存在が確かめられる時刻」に近い意味を持つ。G については、そこまでの意味は主張しない。
- min を使うと、「有効な anchor が 1 つ以上あればよい」という採用の規則と論理的に一致する。§3.4 の (6) は「T_info + δ までに有効な anchor が 1 つでもある」と同じ意味になる。
- §3.4 の (5) は min に対して検査する。min がこの条件を満たせば、ほかの anchor の時刻もすべて満たす。

### 9.2 G — GitHub の server 側の証拠(検証の手順)

**時刻源**

- 使うのは、GitHub の repository activity API(`GET /repos/{owner}/{repo}/activity`)の記録の timestamp だけ。これは GitHub が push を受け付けたときに server 側で記録する値である。
- **commit の author date と committer date は、正式な anchor に使わない。** どちらも push する側が自由に書けるからである。記録はしてよいが、判定には使わない。

**取得の側(acquisition の run)で行うこと**

1. 原ファイルと manifest を、1 つの commit に入れる。anchor の記録(R の token を含む)も同じ commit に入れてよい。manifest を変えないので循環しない。
2. V2 の repository の決まった branch に push する。この branch には force push と削除を禁止する設定をかける。

**検証の側(取得とは別の job)で行うこと**

1. activity API を呼び、応答のバイト列を**そのまま**保存し、その SHA-256 を記録する。呼んだ時刻(runner の時計)と HTTP の status、応答 header の Date も記録する。
2. 次を満たす記録 a を探す。
   - a.ref が決まった branch で、a.activity_type が push、または branch を作った最初の push を表すもの(F11-a: activity API では、branch の最初の push が push ではなく branch_creation として記録される)。
   - commit C(manifest を含む commit)が a.after と同じか、a.after の祖先である。
   - C が a.before と同じでも、a.before の祖先でもない(C はこの push で初めて branch に入った)。
3. 条件を満たす記録が複数あれば、timestamp が最も早いものを採る。force push を禁止しているので、通常は 1 つである。
4. 結合を確認する: C の tree の中の manifest の path にある blob を読み、§3.3 の正規化をやり直して一致を確認し、manifest の Content_SHA256 と、同じ tree の原ファイルのバイト列の SHA-256 が一致することを確認する。
5. すべて通れば、t_G = a.timestamp。

**G が有効にならない場合**

- 条件を満たす記録が見つからない、結合が確認できない、API が失敗した。
- Decision_Time までに検証の job が実行されなかった、または終わらなかった。

**G の 2 段階の区別(決定)**

| 区分 | 値 | 意味 |
|---|---|---|
| G_CONTEMPORANEOUS_VALID | true / false | Decision_Time までに、検証の job が GitHub の API に直接問い合わせ、上の手順に通った。**G が有効な anchor になるのは、これが true のときだけ** |
| G_LONG_TERM_SELF_CONTAINED | **常に false** | API の記録が保持期間を過ぎたあとに、保存した応答・自前の hash・TSA だけで「GitHub が発行した記録である」ことまで完全に独立に証明できる、とは主張しない |

- 保存した応答は、自分で保存したものなので、それだけでは第三者の証拠にならない。研究者の側で書き換えることができるからである。
- 保存した応答に R を付けることは**推奨する**(付けておけば、「その応答のバイト列が、その時刻までに存在した」ことは示せる)。ただし、R が示すのは**そのバイト列が存在したこと**であって、**そのバイト列を GitHub が発行したこと**ではない。したがって、R を付けても G を長期の自己完結型の anchor に格上げしない。これは要件にもしない。
- activity API の記録の保持期間は保証されていない。あとの監査で取り直せなくなっても、Decision_Time の時点の判定は変えない(§6.4)。
- 長期にわたって自己完結した検証ができる anchor は R だけである。R を残す大きな理由の 1 つがここにある。

### 9.3 R — RFC 3161 の時刻証明(Acceptance Requirements と検証の手順)

**要求の仕方(取得の側)**

- messageImprint は `SHA-256(manifest の正規のバイト列)` = Manifest_SHA256。hashAlgorithm は SHA-256(OID 2.16.840.1.101.3.4.2.1)。
- 要求ごとに nonce を付け、certReq = true にする。
- 要求を送った時刻と、応答を受け取った時刻(runner の時計)を記録する。§10 の時計の検査にも使う。
- 応答の DER のバイト列をそのまま保存し、その SHA-256 を記録する。

**TSA の Acceptance Requirements(候補を選ぶ前に固定する)**

| # | 要件 |
|---|---|
| R-ACC-1 | RFC 3161 の TimeStampResp を返す。状態が granted(または grantedWithMods で、変更の内容が記録されている) |
| R-ACC-2 | messageImprint に SHA-256 を受け付ける。SHA-1 の imprint しか返さない TSA は不可 |
| R-ACC-3 | token の署名の algorithm が SHA-256 以上。SHA-1 による署名は不可 |
| R-ACC-4 | TSTInfo に **accuracy** がある。その値が **A_max = 1.0 秒** 以下(決定)。accuracy がない TSA、または 1 秒を超える TSA は R として不適格。A_max は runner の ε とは別の量であり、A_max = 1 秒から ε = 1 秒を導かない |
| R-ACC-5 | **genTime** を UTC で返す。秒の小数があれば、その桁のまま記録する。丸めない |
| R-ACC-6 | 要求の nonce を応答にそのまま返す |
| R-ACC-7 | 署名に使った証明書を token に入れる(certReq に応える)。署名者の証明書を ESSCertID / ESSCertIDv2 で token に結び付けている |
| R-ACC-8 | TSA の policy の OID が決まっていて、公開されている。使う OID を固定し、記録する |
| R-ACC-9 | 署名の証明書の extendedKeyUsage が timeStamping だけ(critical) |
| R-ACC-10 | **取得の時点で**、証明書の鎖(root まで)と、失効の情報(CRL または OCSP の応答)を取得して保存できる |
| R-ACC-11 | token、署名、messageImprint、hash algorithm、証明書の鎖を、**TSA に問い合わせずに、後から独立に再検証できる**(保存した資料と OpenSSL などの一般的な実装だけで) |
| R-ACC-12 | HTTPS / TLS が正しいことは、token の正しさの根拠にしない。token は署名だけで検証する |
| R-ACC-13 | 公開されている可用性の情報、運営者、利用の条件が記録できる。さらに、**較正 + 64 の試験窓 + 通常の運用で想定する attempt の数**を含む要求の量が、その TSA の公開された利用条件・rate limit・fair-use policy の上で許されることを、**試験の開始前に確認する**(決定)。確認できなければ、「たぶん大丈夫」で進めず、その TSA を正式な候補から外す |

R-ACC-1〜13 は採用(決定)。

**数(決定)**

- **TSA は R1・R2 の 2 局。** 2 局は、**運営者が異なり、かつ trust / root の鎖も異なる**こと。同じ運営者の別の endpoint は、2 局と数えない。
- どちらにも、同じ manifest に対して要求する。
- 有効な anchor は G、R1、R2 の 3 つのうち 1 つ以上あればよい(§9.1)。TSA が 1 つ落ちても R は残り、GitHub が落ちても R は残る。
- 具体的な TSA は、Acceptance Requirements を Freeze したあとで選ぶ。この版では選ばない。

**検証の手順(検証の側)**

1. 保存した DER を読み、状態、TSTInfo(policy、messageImprint、serialNumber、genTime、accuracy、nonce)を取り出す。
2. messageImprint の hashAlgorithm が SHA-256 で、hashedMessage が Manifest_SHA256 と一致する。
3. nonce が要求の nonce と一致する。
4. 署名を、保存した証明書の鎖で検証する(例: `openssl ts -verify -in <token> -digest <Manifest_SHA256> -CAfile <root> -untrusted <中間>`)。検証の時刻は genTime とし、保存した失効の情報で、その時点に証明書が失効していなかったことを確認する。
5. policy の OID、accuracy ≤ A_max、署名の algorithm を確認する。
6. 結合を確認する: manifest の正規化をやり直して Manifest_SHA256 と一致し、manifest の Content_SHA256 と原ファイルの SHA-256 が一致する。
7. すべて通れば、t_R,i = genTime。

### 9.4 δ(決定: 300 秒)

- **δ = 300 秒。**
- この値は、V1 の 6 件の実測(2〜5 秒)から導いたものではない。6 件は少なく、しかもすべて push が 1 回目で通った場合なので、遅れの分布の上限をこの実測だけから推定することはできない。
- δ = 300 秒は、通常の commit・push・TSA の処理に十分な運用の余裕を与えつつ、T_info からかなり遅れて証拠になった取得を除くための、**保守的な監査上の上限**として事前に固定する。
- V2 の試験 telemetry を見てから変えない。

### 9.5 X — 外部の scheduler / provider の実行記録(補助)

- X は Execution_ID の裏付けとして記録する。正式な anchor にはしない。
- 理由: 実行した時刻は示せても、取得した中身との結合を X だけでは得られない(§3.2)。
- X の記録と Execution_ID が食い違えば、PROVENANCE_INVALID とする。

## 10. runner の時計の健全性(独立の要件。ε = 6.0 秒)

### 10.1 なぜ独立の要件にするか

- §3.4 の (3) は runner の時計の値で窓の判定をする。δ は窓の上端の側(取得が遅すぎる場合)を server 側の時刻で押さえるが、**窓の下端の側**(取得が T_info − 6h より前だった場合)は、anchor では押さえられない。早すぎる取得は、anchor の時刻も早いので、δ の条件に通ってしまうからである。
- したがって、runner の時計の誤差を、取得のたびに外部の時刻で測り、証拠として残す必要がある。

### 10.2 時計の誤差のモデル

- 真の時刻を t、runner の時計の値を r(t) = t + e とする。e が runner の時計の誤差である。
- 外部の時刻源に問い合わせ、runner の時計で送った時刻 r_send と受け取った時刻 r_recv を記録し、応答の中の外部の時刻を S とする。外部の時刻源の不確かさ(自分の時計の誤差と、表示の桁)を u_S とする。
- 外部の時刻 S は、真の時刻で送ってから受け取るまでの間に付けられたので、次が成り立つ。

```
e ∈ [ r_send − S − u_S ,  r_recv − S + u_S ]
```

- 幅は RTT + 2·u_S である。RTT が大きい測定は、それだけ誤差の幅が広くなる。

### 10.3 測定の手順

**時刻源(決定)**

| 系統 | 時刻源 | 位置づけ |
|---|---|---|
| 主 | RFC 3161 の TSA(R1・R2)の genTime。u_S は token の accuracy(≤ A_max = 1.0 秒) | 正式な clock evidence。§3.4 の (2)・(3) と ε の判定は、この系統の測定だけで行う |
| 補助 | 独立した複数の host の HTTPS の応答の Date header | 記録はするが、ε の判定の主な根拠にはしない。秒の桁でしか表示されず、host 自身の時計の誤差が明示されないため |
| 補助の診断 | NTP の問い合わせ | 実行環境から使える場合に記録する。診断にだけ使う |

**手順(決定)**

- 取得の**直前**(Clock_Check_Pre)と**直後**(Clock_Check_Post)に測る。
- Clock_Check_Pre: R1・R2 に要求する。この時点ではまだ manifest がないので、messageImprint には **PRE の記録**の SHA-256 を使う(決定)。
  - PRE の記録は、次の key をこの順に持つ正規の JSON: `Schema_Version`、`Execution_ID`、`Target_Origin`、`Acquisition_Path_ID`、`Stage`(値は "PRE")、`Random_Nonce`。
  - 正規化は Acquisition_Manifest と同じ: key の順は固定、UTF-8、改行は LF、末尾の改行はちょうど 1 つ。
  - この正規のバイト列の SHA-256 を、RFC 3161 の messageImprint に渡す。PRE の記録そのものも保存する。
  - RFC 3161 の要求の nonce は、Random_Nonce とは**別に**使う。
  - これにより、どの Execution の、どの Origin の、どの経路の、取得の前の時計の検査だったかが、token に結び付く。
- Clock_Check_Post: R1・R2 への manifest の anchor の要求(§9.3)が、そのまま Clock_Check_Post を兼ねる。
- RTT(r_recv − r_send)が RTT_max を超えた測定は、正式な測定として使わない(RTT_max = 2.0 秒。§10.6)。
- 直前と直後のそれぞれで、使える測定が 1 つ以上あることを要する。各測定から e の区間を出し、使える測定の区間を**合わせた範囲**(区間の和の最小と最大)を [e_lo, e_hi] とする。取得の間に時計が動いた分も含めるためである。
- 健全性の条件(§3.4 の (2)): `max(|e_lo|, |e_hi|) ≤ ε`。満たさなければ CLOCK_INVALID(sanity)。直前か直後のどちらかで使える測定がない場合も CLOCK_INVALID(sanity)とする。
- 補助と補助の診断の測定は、主系統の結果と食い違えば記録に残すが、判定は変えない。

**この手順の帰結(決定として受け入れた)**

- 主系統を TSA にしたので、USABLE になるには、直前と直後の両方で R1・R2 の少なくとも 1 局が応答している必要がある。anchor としては R を必須にしていない(G だけでもよい)が、**時計の検査では TSA が事実上必須になる**。
- **補助の系統(HTTPS の Date、NTP)への自動の fallback は作らない。** PRE か POST で R1・R2 のどちらからも有効な clock evidence が得られなければ、CLOCK_INVALID(sanity)で、その取得は使えない。これは意図した fail-closed である。fallback を認めると、「通常は強い時計の証拠、障害のときだけ弱い時計の証拠」という二重の基準になるからである。可用性は、運営者も root も異なる 2 局で確保する。

### 10.4 窓の両端に時計の不確かさを入れる

真の取得の時刻は [Retrieved_At_Runner − e_hi, Retrieved_At_Runner − e_lo] のどこかにある。この区間の全体が窓の中にあることを要求する。

```
下端:  Retrieved_At_Runner − e_hi  >  T_info − 6h
上端:  Retrieved_At_Runner − e_lo  ≤  T_info
```

- 満たさなければ OUTSIDE_WINDOW。
- 窓の端の近くで、時計の不確かさのために窓の中か外か決められない取得は、使わない(fail-closed)。窓の幅 6 時間に対して、ε が秒の単位なら、狭まる分はごくわずかである。
- この規則は V2 provenance acceptance rule である(決定)。V1 の窓 (T_info − 6h, T_info] の定義は変えない(§3.1)。

### 10.5 前後関係の整合(§3.4 の (5))

```
Retrieved_At_Runner ≤ Server_Anchored_At + ε
```

- anchor は取得のあとでしか付けられない。この条件が破れていれば、runner の時計か anchor の時刻のどちらかがおかしいので、CLOCK_INVALID(consistency)とする。どちらがおかしいかは区別しない。

### 10.6 ε と較正期間(決定)

**ε(決定: E1)**

```
ε = D_max + RTT_max + 2·A_max = 2.0 + 2.0 + 2·1.0 = 6.0 秒
```

- この式は、**真の時計の誤差を推定する式ではない。保守的な engineering budget** である。D_max は runner の時計の真の誤差として許す大きさ、RTT_max は clock evidence として採用する測定の RTT の上限、A_max は TSA の accuracy の上限。
- **判定の時の [e_lo, e_hi] は、各測定の実測値(r_send、r_recv、genTime、accuracy)から直接計算する**(§10.2、§10.3)。たとえば実測の RTT が 0.4 秒なら、区間は 0.4 秒で作る。RTT_max = 2.0 秒を区間に使うのではない。RTT_max は、それを超えた測定を clock evidence として採用しないための上限である。
- ε は §3.4 の (2) と (5) で同じ値を使う。
- V1 の push の遅れ(2〜5 秒)は、ε の根拠にしない。A_max = 1.0 秒から ε = 1.0 秒を導くこともしない。
- E2(候補の梯子から選ぶ方式)は採らない。pipeline の provenance の閾値なので、telemetry を見て ε を選ぶ自由度そのものを消す。

**較正(決定)**

| 項目 | 値 |
|---|---|
| 較正期間 | 連続 7 暦日 |
| 測定回数 | A 経路、C 経路の**それぞれ**で、**実際に開始された**較正の実行の clock-check pair(PRE と POST の組)が 100 組以上 |
| 時刻源 | §10.3 の主系統(R1・R2)だけ |
| RTT_max | 2.0 秒 |
| p_min | 0.99 |
| 合格の条件(経路ごと) | **実際に開始された**較正の実行のうち 99% 以上で、PRE と POST の両方について、正式な TSA の測定が少なくとも 1 局から得られ、各測定が RTT ≤ 2.0 秒を満たし、最終的な `max(|e_lo|, |e_hi|) ≤ 6.0 秒` を満たす |

- **A と C を合算して 99% にしない。A と C の両方が、それぞれ合格すること。**
- **分母(決定)**: 較正が測るのは「起動した環境で、TSA による clock evidence を安定して得られるか」である。予定したのに起動しなかった回は **TRIGGER_NOT_STARTED** として別に集計し、較正の分母には入れない。起動するかどうかは Reliability Gate が測る(Reliability の試験では、起動しなければ NO_ACQUISITION で FAILURE になる)。こうして「時計の品質」と「起動の信頼性」を混ぜない。
- 較正で測るのは時計の証拠だけ。CFTC の取得の成否や、試験窓の SUCCESS / FAILURE は見ない。
- 較正期間のデータは、Reliability の 60 窓にも、failover の 4 窓にも入れない。
- 較正は、Reliability の試験で使うのと同じ経路と同じ実行環境で行う。
- **不合格のとき**: 同じ較正のデータを見ながら ε を 6 秒から 10 秒などに変えることは禁止。設計を変え、新しい Calibration Spec を Freeze し、新しく較正をやり直す。
- 較正の条件は、較正を始める前に Freeze する。

## 11. Freeze に向けた状態

- むすびさんの v0.6 の最終監査で残った 3 点(Issuance_Adjudication_Time、Issuance の単位、ON_TIME の時計)は、この版で本文に統合した(§4.1、§6.5、§7.5、§8 の 29〜31)。
- むすびさんの最終監査の結果によれば、この 3 点が正しく統合されれば、Requirements 側に Freeze を妨げる未決事項はない。
- 現在の状態: V1 = FREEZE / PASS / CLOSE のまま変更なし。Development Replay = NOT STARTED。Historical Reserve Holdout = SEALED。V2 の試験 = 未開始(較正も未開始)。
