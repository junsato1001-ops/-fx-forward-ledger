# OPS-FORWARD-01 — M1-MACRO-V1 最初の 1D Forward Origin(2026-10-22)の運用記録

- 作成: Claude, 2026-10-22 09:11 JST
- 種類: Forward の運用の記録(acquisition / issuance telemetry、F14-a の追跡)
- 確認した範囲: 状態の列だけを読んだ。予測の値(確率、Point、PI)、β、μ、J*、CRPS、成績は読んでいない。
- 確認した時点の main: 7a597a8。Code_SHA256 は d3c77eba…77d4 で、凍結した値と同じ。

## 1. 取得(acquisition telemetry)

| 予定(cron "40 15,17 * * *") | 実際 |
|---|---|
| 2026-10-21T15:40Z(10/22 00:40 JST) | 起動せず |
| 2026-10-21T17:40Z(10/22 02:40 JST) | 起動が遅れた。run **39662696481** は event schedule、**2026-10-21T19:33:35Z** に起動、success。CFTC の取得は 19:33:53Z で、**T_info(18:00Z)より後**。どの Origin の窓 (T_info − 6h, T_info] にも入らない |

main に移してから予定は 6 回あった。起動したのは 2 回で、2 回とも予定の約 1 時間 53 分後に起動した。

- 10/20 の 2 回目の予定: 19:33Z に起動(run 39484473314)
- 10/21 の 2 回目の予定: 19:33Z に起動(run 39662696481)

残りの 4 回は起動していない。

## 2. 発行(issuance telemetry)

発行の run は **39689057756**。event は workflow_run(S0 forward-ledger の run 39688841396 が success になった後)、起動は 2026-10-21T22:47:49Z、success。Code_SHA256 は d3c77eba…。

凍結したコードが実際に記録した内容は次のとおり。

| 台帳 | 内容 |
|---|---|
| features(Origin 2026-10-22) | T_info 2026-10-21T18:00:00Z。F_US OK、F_JP OK。**F_POS ABSTAIN_SYSTEM / FEATURE_UNAVAILABLE / CFTC_PRE_TINFO_SNAPSHOT_UNAVAILABLE**。snapshot の Retrieved_At は空 |
| estimation(2026-10-22, 1D) | Parameter_State **NOT_EVALUATED**。Solver_Status と Solver_Subreason は空 |
| forecasts(2026-10-22, 1D) | USDJPY、CHFJPY、INRJPY の 3 行すべてが **ABSTAIN_SYSTEM / FEATURE_UNAVAILABLE**。Parent は S0-EMPCLIM-STD-EXP-V1、Issued_At は 2026-10-21T22:49:03Z |
| issue_commits | Run 39689057756-1、Horizons 1D、features 1 行 / estimation 1 行 / forecasts 3 行、**Status COMPLETE**、Committed_At 2026-10-21T22:49:46Z |
| issue_deadline | Committed_At 22:49:46Z、Verified_At 22:49:48Z、Deadline 2026-10-21T23:30:00Z、**Deadline_Status ON_TIME** |

**判定に使う区分: (a)** 正式な COMPLETE の行が、締め切りまでに(ON_TIME で)作られた。**(b)** の NOT_ISSUED(発行の処理まで到達しなかった場合)ではない。

- 3 つのペアがすべて ABSTAIN になったのは、F_POS(円の CFTC の建玉)が 3 ペアとも同じ特徴量 N(p) に入っているためで、仕様どおりの結果である。
- 推定に使えるペアが 1 つもないので、(t, h) の推定はせず、NOT_EVALUATED と記録した(Part 3 §3 の注)。

## 3. 観測のまとめ

- 凍結した availability の規則と fail-closed の規則は、記録の上では仕様どおりに動いた。
  - 取得を救済する処理も、規則を迂回する処理も入っていない。
  - 発行の transaction は COMPLETE で、ON_TIME だった。
- 取得できなかった原因は、GitHub の schedule が起動しなかったことと遅れたことにある。コードとデータの問題ではない(F14-a。V2 の pipeline-design の材料)。
- 参考: S0 の forward-ledger は、10/21 19:36Z の schedule run(39663176408)が failure だった。その後の 22:45Z の run(39688841396)は success。

## 4. 変えなかったこと

- workflow、コード、config には手を加えていない。凍結外の取得経路も加えていない。
- Development Replay はまだ始めていない。Holdout は SEALED のまま。
