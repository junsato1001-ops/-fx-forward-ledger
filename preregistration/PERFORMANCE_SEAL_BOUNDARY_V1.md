# PERFORMANCE_SEAL_BOUNDARY_V1 — 監査で「見てよいもの」と「見てはいけないもの」の境界

- 状態: 運用規則(2026-10-16、Claude起草、むすびの指示に基づく)
- 適用期間: M1-MACRO の仕様がFreezeされるまで(PERFORMANCE_SEAL の期間)
- この文書はモデル仕様ではない。モデルの数値・判定には影響しない。

## 1. 判定のための基準

ある計算が **「予測の値(またはそれから導いた量)」と「同じキーの実現値 y」の両方を入力にとる** なら、それは成績(performance)の計算であり、封印期間中は禁止。
片方だけを入力にとる計算は、成績ではない。

キー = (Model, Pair, Origin, Horizon)。実現値 y = `ledger/outcomes.csv` の Realized_LogReturn、または ECB の生データから計算した Target_Start〜Target_End の対数リターン。

## 2. 許可(Forecast Correctness)

| 区分 | 例 |
|---|---|
| 予測の再計算 | 発行時のデータ(Last_Available_Fix までに切り詰め)とFreeze済みコードから、予測の各欄(σ、確率、Point、PI、Pool_N、Decision_Class 等)を独立に計算し直し、発行値と一致するか確認する |
| 発行の手続き | 予定起点の数、締切前の発行(Issued_At_UTC)、ABSTAIN_SYSTEM の理由、データとコードのSHA-256、Storage Verification Gate の結果 |
| 実現値の記録の正しさ | outcomes.csv の値を ECB の生データから計算し直して一致を確認する(予測とは結合しない) |
| 状態 | Decision_Class / Outcome_Status(OBSERVED・PENDING・UNAVAILABLE)の件数と遷移 |
| 仕様が要求する同一性 | 例: M1 の DEFAULT_PARENT 状態の行が S0 と一致すること(spec 4.4) |

## 3. 禁止(Performance — 封印中)

- 損失: CRPS、RPS、Brier、Log Loss、Interval Score、QLIKE を実現値に対して計算すること(σの推定に使う過去データ上の QLIKE は M1 の仕様の一部であり、発行コードの中でだけ許される)
- 的中・外れ、方向の一致、区間に入ったか(coverage)、PIT、残差 y − Point、z = y/σ の実現値
- 上記のモデル間比較、ペア別の比較、時系列の推移の図
- 予測と実現値を同じ表・同じ図に並べて表示すること(計算しなくても目視で成績が分かるため)

予測同士の差(例: σ_M1 と σ_M0 の差)は成績ではないが、仕様が要求する同一性の確認以外では集計しない。

## 4. 監査記録の書き方

監査記録には次の2欄を必ず分けて書く。

| 欄 | 内容 |
|---|---|
| Forecast_Correctness | PASS / FAIL と、その根拠(再計算の一致件数、SHA、Gate) |
| Performance | 常に `SEALED_NOT_EVALUATED`(封印期間中) |

封印期間中に誤って成績に当たる計算をした、または表示を見た場合は、隠さずに `SEAL_BREACH` として日時・内容・見た範囲を記録し、むすびと純に報告する。

## 5. M1-VOL-SHRINK-V1 の位置づけ(再確認)

M1-VOL-SHRINK-V1 は確認的な Challenger ではなく Shadow / Pipeline Pilot である。2026-10-18 からの Forward 記録は「104週後の昇格判定」を意味しない。
Freeze済みの Pilot 完了条件(12項目)を実運用で満たした時点で `PILOT_OBJECTIVE_ACHIEVED` として Pilot 工程を閉じ、Shadow monitoring に移す。
