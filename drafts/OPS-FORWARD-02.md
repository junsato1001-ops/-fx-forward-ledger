# OPS-FORWARD-02 — M1-MACRO-V1 の 1W・4W 最初の Forward Origin(2026-10-25)の運用記録

- 作成: Claude, 2026-10-25 09:12 JST
- 種類: Forward の運用記録(取得と発行の状態の観測)。F14-a の追跡を兼ねる。OPS-FORWARD-01 の続き。
- 確認した範囲: 状態を表す列だけを読んだ。予測の値(確率、Point、PI)、β、μ、J*、CRPS、成績は読んでいない。
- 確認した時点の main: 8ed7c92。Code_SHA256 は d3c77eba…77d4(凍結値)。
- 原因は推測していない。記録しているのは観測した事実だけ。

## 1. 取得の観測

対象 Origin 2026-10-25 の T_info は 2026-10-24T18:00Z(10/25 03:00 JST)。使える取得の窓は (2026-10-24T12:00Z, 18:00Z]。

時系列(03:10 JST に確認した事実は書き換えず、その後の観測は追記として足している):

| 時点 | 観測 |
|---|---|
| 2026-10-24T15:40Z の予定(10/25 00:40 JST) | 起動していない |
| 2026-10-24T17:40Z の予定(10/25 02:40 JST) | 18:13Z(03:10 JST に確認した時点)まで未起動 |
| **その後の追記** | 18:20:30Z に schedule run **40120250199** が遅れて起動した(conclusion success)。CFTC の取得は **18:20:52Z** で、T_info を 20 分 52 秒過ぎているため使えない |

結論: 2026-10-25 の T_info までに、使える CFTC snapshot は存在しなかった。

## 2. 発行の観測(1W と 4W を別々に確認)

発行の run は **40136262281**(event workflow_run。S0 の forward-ledger の run 40136132160 が success になった後に起動)。起動 2026-10-24T21:54:27Z、conclusion success、Code_SHA256 d3c77eba…。

### 共通(特徴量、Origin 2026-10-25)

T_info 2026-10-24T18:00:00Z。F_US OK、F_JP OK。**F_POS は ABSTAIN_SYSTEM / FEATURE_UNAVAILABLE / CFTC_PRE_TINFO_SNAPSHOT_UNAVAILABLE**。snapshot の Retrieved_At は空。

### 1W

| 台帳 | 凍結コードが記録した値 |
|---|---|
| estimation (2026-10-25, 1W) | Parameter_State **NOT_EVALUATED**、N_Warmup 797、Solver_Status と Solver_Subreason は空 |
| forecasts | USDJPY、CHFJPY、INRJPY の 3 行すべて **ABSTAIN_SYSTEM / FEATURE_UNAVAILABLE**(Issued_At 2026-10-24T21:55:37Z) |

### 4W

| 台帳 | 凍結コードが記録した値 |
|---|---|
| estimation (2026-10-25, 4W) | Parameter_State **NOT_EVALUATED**、N_Warmup 794、Solver_Status と Solver_Subreason は空 |
| forecasts | USDJPY、CHFJPY、INRJPY の 3 行すべて **ABSTAIN_SYSTEM / FEATURE_UNAVAILABLE**(Issued_At 2026-10-24T21:55:37Z) |

### transaction(1W と 4W を 1 つで発行)

| 台帳 | 値 |
|---|---|
| issue_commits | Run 40136262281-1、Horizons **1W;4W**、features 1 行 / estimation 2 行 / forecasts 6 行、**Status COMPLETE**、Committed_At 2026-10-24T21:56:56Z |
| issue_deadline | Committed_At 21:56:56Z、Verified_At 21:56:57Z、Deadline 2026-10-24T23:30:00Z、**ON_TIME** |

**区分**: 1W と 4W はどちらも **(a) 正式な COMPLETE の ABSTAIN を、期限内(ON_TIME)に発行**した。(b) NOT_ISSUED ではない。

- 1W と 4W は同じ Origin の 1 回の transaction で発行された。期限内に発行できる Horizon は 1 回でまとめて発行する仕様(IMPL-FINDINGS-04 F3)。
- 3 ペアすべてが ABSTAIN になったのは、F_POS が 3 ペアに共通の特徴量だから。推定に使えるペアが 1 つもないので、推定は行わず NOT_EVALUATED になった(Part 3 §3 の注)。
- N_Warmup(797 と 794)は件数の欄で、warm-up の閾値 250 を超えている。推定しなかった理由は warm-up 不足ではなく、特徴量が使えなかったこと。

## 3. 統合からの累計(OPS-FORWARD-01 からの続き)

### 3.1 定時実行(cron "40 15,17 * * *")の起動実績

main への統合は 2026-10-20T12:08Z。対象は 2026-10-20〜10-24 の 5 日で、予定は 1 日 2 回(15:40Z と 17:40Z)の計 10 回。

| 日(UTC) | 15:40Z の予定 | 17:40Z の予定 | 実際に起動した schedule run | 起動時刻 | CFTC の取得時刻 | その日の T_info(18:00Z)の窓に入るか |
|---|---|---|---|---|---|---|
| 10/20 | 起動なし | ― | 39484473314 | 19:33:29Z | 19:33:50Z | 入らない |
| 10/21 | 起動なし | ― | 39662696481 | 19:33:35Z | 19:33:53Z | 入らない |
| 10/22 | 起動なし | ― | 39840064610 | 19:26:25Z | 19:26:46Z | 入らない |
| 10/23 | 起動なし | ― | 40012075427 | 19:31:25Z | 19:31:44Z | 入らない |
| 10/24 | 起動なし | ― | 40120250199 | 18:20:30Z | 18:20:52Z | 入らない |

- 起動したのは 10 回中 **5 回**で、1 日に 1 回ずつだった。
- 5 回とも 17:40Z より後に起動している。17:40Z との差は、1:53、1:53、1:46、1:51、0:40。どの予定の起動なのかは、GitHub の記録からは区別できない。
- 15:40Z の時刻に起動した run は 0 回。
- T_info までに使える CFTC snapshot は **0 回**。

### 3.2 M1 の発行(最初の Origin 以降)

| Origin | Horizon | 発行の run | Decision_Class / Reason_Code | F_POS Subreason | COMPLETE | 期限 |
|---|---|---|---|---|---|---|
| 2026-10-22 | 1D | 39689057756 | ABSTAIN_SYSTEM / FEATURE_UNAVAILABLE(3 ペア) | CFTC_PRE_TINFO_SNAPSHOT_UNAVAILABLE | COMPLETE | ON_TIME |
| 2026-10-23 | 1D | 39867358347 | ABSTAIN_SYSTEM / FEATURE_UNAVAILABLE(3 ペア) | CFTC_PRE_TINFO_SNAPSHOT_UNAVAILABLE | COMPLETE | ON_TIME |
| 2026-10-25 | 1W、4W | 40136262281 | ABSTAIN_SYSTEM / FEATURE_UNAVAILABLE(3 ペア × 2) | CFTC_PRE_TINFO_SNAPSHOT_UNAVAILABLE | COMPLETE | ON_TIME |

- 最初の Origin 以降に予定された M1 の Origin は 3 つ(10/22 1D、10/23 1D、10/25 1W/4W。10/24 は土曜で 1D の Origin ではない)。3 つとも COMPLETE かつ ON_TIME で、NOT_ISSUED と LATE は 0 件。
- 予測行 12 行はすべて ABSTAIN_SYSTEM / FEATURE_UNAVAILABLE。FORECAST は 0 件。
- F_US と F_JP は毎回 OK。ABSTAIN になった理由は、毎回 F_POS の pre-T_info snapshot がなかったことだけ。

### 3.3 参考: S0 の forward-ledger(M1 の発行を起動する側)

- 10/21 19:36Z の schedule run 39663176408 と、10/24 18:21Z の schedule run 40120328104 が failure だった。そのあとに連なった M1 の workflow_run(39663469743、40120478553)は skipped。
- どちらの日も、後の S0 の run が success になり、M1 の発行はそのあとに行われた。

## 4. 変更しなかったこと

workflow、コード、config は変えていない。凍結外の取得経路も足していない。Development Replay は始めていない。Holdout は SEALED のまま。

## 5. むすびさんに判定してほしいこと

F14-a を個別の Observation として追跡し続けるか、V2 の pipeline-design finding として正式に切り出すか。

判断材料として、次の観測がそろっている。

- 定時実行の起動は 10 回中 5 回で、すべて遅れていた。
- 使える CFTC snapshot は 0 回だった。
- その結果、最初の 3 つの Origin で M1 の FORECAST は 0 件だった。
