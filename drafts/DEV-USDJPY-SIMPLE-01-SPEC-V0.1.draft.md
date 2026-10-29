# DEV-USDJPY-SIMPLE-01 — Development 診断 Trial 仕様(SPEC CANDIDATE v0.1)

- 状態: **SPEC CANDIDATE v0.1**(Claude、2026-10-30)。むすびさんの監査と純さんの判断の前のレビューの候補。**Freeze ではない。実行の承認でもない。**
- 合意の経緯: ミッチーさんの提案(System-level Observer)→ むすびさんの修正 → Claude の Freeze 照合 → 純さんの方針の決定(2026-10-30 05:52 JST: V1 を Development の計算から外す、金利差の Challenger を外す、δ を入れない、Development は Target_End ≤ 2026-10-09、Holdout は 5 ペア)→ むすびさんの判定(2026-10-30 05:57 JST)。
- 変更の規則: Freeze の後は書き換えない。変更は**別の Trial_ID** とし、§12 の台帳に加える。

---

## 0. 目的と非目的

**目的**: 2026-10-09 までに Target_End が確定した Development の情報だけを使い、S0 を親として、USD/JPY の 20 source-business-day の momentum で位置 μ だけを動かす 1 本の Challenger について、**1D で prospective Forward の候補にする資格があるか**を、事前に固定した統計的な選択の規則(Development Gate)で診断する。

**非目的(明記)**:
- 予測力の確認ではない。Development の結果は確認的な証拠にしない(EVAL-SPEC-V1 §6)。
- 経済的に意味のある効果の確認ではない。δ・Δ_min は定義しない(EVAL-SPEC-V1 §7)。
- Forward の開始の承認ではない。Gate の通過は **FORWARD_CANDIDATE_ELIGIBLE** までであり、**FORWARD_AUTHORIZED ではない**(§10)。
- 既存の Trial(M0・S0・M1-VOL-SHRINK-V1・M1-MACRO-V1)の判定を読み替えない。USD/JPY だけの結果で既存の結論を変えない。

## 1. 既存の Freeze との関係

### 1.1 EVAL-SPEC-V1(SHA-256 fdb11fcf…)から自動的に継承するもの

| 項目 | 内容 | EVAL-SPEC-V1 |
|---|---|---|
| 主の損失 | L = CRPS(F, y) / σ_M0,t。離散経験分布は §3.1 の式(fair CRPS を使わない) | §3.1 |
| σ_M0 | M0 v1.2 の VOL_STATE_V1(`frozen/m0_walkforward_v1_2.py`) | §1 |
| 主指標の対象 | σ_M0,t が有限かつ > 0 の機会。0 なら METRIC_UNDEFINED_ZERO_SCALE として除外し件数を報告 | §4.1a |
| 共通標本 | 比べる全モデルが FORECAST かつ Outcome = OBSERVED | §4.1 |
| Coverage | Decision coverage の非劣化 −2.0pp | §4.2 |
| Decision_Class・Outcome の状態 | §2.1・§2.2 の区分 | §2 |
| 推論の方式 | Politis–Romano stationary bootstrap、B = 10,000、片側の p 値の式、`Generator(PCG64(20261016))` を検定ごとに初期化、Newey–West HAC(Bartlett、lag = ブロック長)は sensitivity | §5.1〜§5.4 |
| 副指標・較正 | RPS・Brier・IS/σ_M0・PI80 coverage・Verification-Rank Calibration は記述のみ | §3.2、§3.4 |
| クラス境界 | b_t = 0.25 · σ_M0,t | §3.3 |
| Origin と Target | ORIGIN_TARGET_MAP_V1(`frozen/origin_target_map_v1.py`) | §1 |
| Forward での判定(将来、Forward が承認された場合) | 最初の確認的 Origin から 104 週後に 1 回だけ | §5.5 |

### 1.2 継承しないもの(この Trial で新しく固定する。§7〜§9)

- Holm の族の構造(EVAL-SPEC-V1 の「3 Horizon × 2 方向」とは違う)
- 判定の対象を ESTIMATED の機会に絞ること
- DA Safety Veto(どの Freeze にも具体的な規則がない)

### 1.3 V1 の Freeze の規則を、この Trial が**明示的に採用**するもの(自動の適用ではない)

M1-MACRO-V1 のモデルの Freeze は V1 にだけ効く。この Trial は、結果を見ずに、同じ規則を自分の規則として採用する(§3〜§5)。採用の元: MODEL-PART1-V1、PART2A〜2E-V1、TRANSFORM-PART2A-V1。

### 1.4 触れないもの

- **M1-MACRO-V1**: Development の標本で計算しない。V1 Development Replay = NOT STARTED を維持し、SEAL-OPENING の記録を使わない。
- **金利差の Challenger**: この Trial に入れない(V1 の F_US・F_JP と情報が強く重なるため)。
- **Historical Reserve Holdout(RFX-HOLDOUT-A-V1: GBPJPY・AUDJPY・CADJPY・SGDJPY・KRWJPY)**: 読まない、導出しない、計算しない(§2.3)。
- **Forward の期間**: M0・S0・M1-VOL・M1-MACRO の Forward の実現値を使わない(PERFORMANCE_SEAL)。

## 2. データと標本

### 2.1 対象

- ペア: USD/JPY だけ。
- Horizon: **1D = 主**、**1W = 記述と診断だけ**、4W = 対象外。

### 2.2 Development の機会

- ORIGIN_TARGET_MAP_V1 の formal な Origin で、**Target_End ≤ 2026-10-09** のものだけ。
- 実現値 y は、§2.3 の固定したスナップショットからだけ計算する。Forward の領域の実現値(`ledger/outcomes.csv` の Forward の行など)を読まない。
- 予測の計算に使う情報も、各 Origin の Last_Available_Fix までに切り詰める(point-in-time)。

### 2.3 入力のデータと読み取りの防壁

- 入力: ECB `eurofxref-hist` の**固定したスナップショット**。Freeze の記録に SHA-256 を書き、計算の前に照合する(一致しなければ止まる)。候補: M0・S0 の Development に使ったスナップショット(Freeze の前に特定する)。
- **列の allowlist**: 読み取りの関数は `Date`・`JPY`・`USD` の列だけを返す。それ以外の列(GBP・AUD・CAD・SGD・KRW を含む)は、値を読み込む前に捨てる。「使わない」ではなく「読ませない」。実装の監査でこれを確かめる。
- USD/JPY = JPY_per_EUR / USD_per_EUR(ECB のクロスの既存の定義)。

## 3. モデル

### 3.1 親と参照

- **親(主比較の相手)**: S0-EMPCLIM-STD-EXP-V1(参照実装 `frozen/s0_empclim_std_exp_v1_1.py`)。USD/JPY の Development で計算する。
- **尺度**: M0 v1.2 の σ_M0(EVAL-SPEC-V1 が要求する範囲で計算する)。
- M0・S0 の Development の成績は、EVAL-SPEC-V1 §3.1 の注記のとおりすでに見られている。この Trial で新しく見る成績は Challenger のものだけである。

### 3.2 Challenger: MOM20-S0SHIFT(仮称)

- 予測分布(MODEL-PART1-V1 §2 を採用): 各点 x'_i = σ_M0,t · Z_i + μ_t(i = 1..N、各 1/N)。pool {Z_i}、N、σ_M0,t は **S0 と同じ**。
- μ_t = β_h · F_MOM(t)。**切片なし**(MODEL-PART1-V1 §3 を採用)。β_h = 0 なら S0 と完全に一致する。
- Point・PI80・クラス確率・CRPS は、ずらした分布から MODEL-PART1-V1 §2 と同じ方法で計算する。

### 3.3 特徴量

```
F_MOM(t) = log( P(v) / P(v − 20) )
```

- P = USD/JPY の ECB の正準 fix。
- v = Origin t の Last_Available_Fix(ORIGIN_TARGET_MAP_V1。締め切りまでに公表済みの最後の fix)。
- v − 20 = v から 20 TARGET publication days 前の fix。
- 単位は対数リターンのまま。**標準化しない**(標準化の窓という自由度を入れない)。
- 窓 20 は、V1 の F_US・F_JP の「20 source-business-days の変化」の慣行から取る。データを見て選んでいない。**この Trial では窓を 1 つだけとし、ほかの窓を試さない**(§12)。
- 0 は「20 日間動いていない」という中立の点。

## 4. 推定(V1 の規則を採用)

- 損失: ℓ_i(β) = CRPS(F^{S0}_i(· − β F_MOM(i)), y_i) / σ_M0,i(MODEL-PART2A-V1)。
- 推定の標本 E_{t,h}: Target_End_i ≤ Last_Available_Fix_t の過去の機会のうち、S0 が FORECAST、F_MOM が定義でき、σ_M0,i が有限かつ > 0、y_i が OBSERVED のもの。時点ごとに過去へ広げる(prequential。MODEL-PART2B-V1)。
- 集計: Origin ごとに等しい重み(1 ペアなので Origin の中の平均は自明)。対象期間の重なりを重みで補正しない(MODEL-PART2B-V1 §4)。
- 正則化なし(λ = 0)。最小値が 1 点に決まらないときは ‖β‖₂ 最小で決める(MODEL-PART2C-V1 §5)。乱数を使わない決定的な方法(線形計画など)で解く。
- 符号の制約なし(MODEL-PART2E-V1)。
- Horizon ごとに別に推定する(1D と 1W で共有しない)。

## 5. warm-up と欠測(V1 の規則を採用)

- **warm-up**: E_{t,h} の相異なる Origin の数が **250 以上**になるまで、β_h = 0(Parameter_State = DEFAULT_PARENT。出力は S0 と完全に一致)で FORECAST を出す。一度 ESTIMATED になれば戻らない(MODEL-PART2D-V1)。
- **欠測**(TRANSFORM-PART2A-V1 の考え方を採用):
  - 親の S0 が FORECAST でなければ MODEL_PREREQ_UNAVAILABLE(PARENT_PREREQ_UNAVAILABLE)。
  - F_MOM を作れない(v − 20 の fix が履歴にない)なら MODEL_PREREQ_UNAVAILABLE(FEATURE_PREREQ_UNAVAILABLE)。
  - 特徴量を黙って落とさない。欠測のときに DEFAULT_PARENT に切り替えない。
- **実装の検査**: DEFAULT_PARENT の行と、β = 0 になった ESTIMATED の行は、S0 と完全に一致しなければならない。

## 6. 主比較

- **USD/JPY 1D、MOM20-S0SHIFT vs S0**。
- d_t = L_challenger,t − L_S0,t。1 ペアなので d̄_t = d_t。D̄ = (1/T) Σ_t d_t(EVAL-SPEC-V1 §5.1 の形)。

## 7. Development Gate の対象の機会

- Gate は、EVAL-SPEC-V1 §4.1 の共通標本のうち、**Challenger の Parameter_State = ESTIMATED** の 1D の機会だけで計算する(DEFAULT_PARENT の機会は d = 0 なので含めない)。この絞り込みは、この Trial の規則である。
- DEFAULT_PARENT の機会の件数と、全体の共通標本での D̄ も記述として報告する(Gate には使わない)。
- **NOT_EVALUABLE**: Gate の対象の 1D の相異なる Origin が **250 未満**なら、Gate を判定せず NOT_EVALUABLE とする。Forward の候補にしない。

## 8. 推論とブロック長

- ブロック長(Origin の単位): **1D = 4、1W = 1** を固定する。EVAL-SPEC-V1 §5.2 の値で、3 ペアの Origin cluster の M0 vs S0 の系列から決まった値である。この Trial では計算し直さない(この Trial の新しいデータや Challenger の値に依存させないため)。
- 検定: 1D の片側の優越(H0: D ≥ 0、H1: D < 0)の p_sup。p_inf(劣後の方向)は記述として報告する。
- HAC: §1.1 のとおり sensitivity として併記する。

## 9. 多重性と DA Safety Veto

- **多重性**: Gate の検定は 1 つ(1D の優越)なので、Gate の中の調整はしない。1W・p_inf・副指標・較正は記述だけで、Gate に使わない。Trial をまたぐ多重性は §12 の台帳で扱う。
- **DA Safety Veto**: Development Gate には入れない。方向の診断(クラスの的中の記述など)は記述として報告するが、その値を見て Veto の閾値を決めない。**DA Safety Veto の正式な規則を別の仕様として Freeze することを、Forward の承認の前提条件とする**(§10)。

## 10. Development Gate と、その後

**Gate の判定(すべてを満たせば FORWARD_CANDIDATE_ELIGIBLE)**:

1. §7 の対象が 250 Origin 以上ある(満たさなければ NOT_EVALUABLE)。
2. p_sup < **α_dev = 0.05**(EVAL-SPEC-V1 の α と同じ値)。
3. Coverage の非劣化: Decision coverage(Challenger) ≥ Decision coverage(S0) − 2.0pp。
4. 1D で SENSITIVITY_DISAGREEMENT(bootstrap と HAC の符号付きの判定が逆向き)がない。

満たさなければ **NOT_ELIGIBLE**。条件を変えて同じ Trial_ID で再実行しない。

**Gate の後(FORWARD_CANDIDATE_ELIGIBLE でも、Forward は自動では始まらない)**。Forward の承認には、少なくとも次がすべて要る:

1. DA Safety Veto の正式な規則の Freeze(§9)。
2. Forward の発行の経路の仕様と、その Freeze(§11)。
3. Forward の Trial の仕様の Freeze(この Trial の Challenger をそのまま使うこと、確認的な判定は EVAL-SPEC-V1 §5.5)。
4. 純さんの明示の承認。

## 11. Forward の発行の経路について、今から固定する禁止事項

- V1 の `ledger/` にも `replay/` にも書かない。
- V1 の凍結された Code_SHA(d3c77eba…)の対象のコードと workflow を変えない。V1 の repository に、このモデルを足さない。
- V2 の pipeline に載せる場合は、V2 の Requirements の範囲の変更として**新しい版**を作り、監査と Freeze を経る(Freeze 済みの V2 の文書を読み替えない)。
- 経路の具体的な選択は、Gate が FORWARD_CANDIDATE_ELIGIBLE の場合にだけ決める(経路の選択は成績の調整ではない)。

## 12. Development の Trial の台帳(新設の規則)

- `preregistration/DEV-TRIAL-REGISTRY.csv`(追記のみ。案)に、**すべての Development の Trial を、結果に関係なく**記録する: Trial_ID、仕様の SHA-256、Freeze の commit、Challenger の定義の要約、実行の commit、結果の区分(FORWARD_CANDIDATE_ELIGIBLE / NOT_ELIGIBLE / NOT_EVALUABLE / ABORTED)、記録の日時。
- 失敗した Trial、途中で止めた Trial も消さない。
- 後の Trial(例: 窓を変えた momentum)は、台帳の件数と結果を知ったうえで設計し、その Trial の仕様に台帳の時点の件数を書く。Trial_ID を変えても、data snooping は消えないためである。

## 13. 記録と成果物(実装の仕様で詳細を決める)

- 置き場所: V1 の `ledger/`・`replay/`、V2 の `records/`・`ledger*`・`probe/` のどれとも別の場所(実装の仕様で決める)。
- 予測の行(Origin、Horizon、Decision_Class、Parameter_State、β_h、F_MOM とその fix の日付、μ、σ_M0、Pool_N、Point、PI、クラス確率)、損失、Gate の計算、スナップショットの SHA-256、コードの SHA-256 を保存する。
- Gate の結果は、§12 の台帳の行と、Gate の記録の 2 つに書く。

## 14. この版で決めていないこと(Freeze の前に必要)

1. §2.3 の ECB スナップショットの特定と SHA-256。
2. 実装の仕様(言語、読み取りの allowlist の実装、検査の一覧、成果物の置き場所、実行の環境)。
3. §12 の台帳の正確な列と置き場所。
4. Development の最初の Origin(M0 の 252 本、S0 の N_overlap_equiv ≥ 100、F_MOM の 20 本の前提がそろう最初の Origin。暦と履歴の長さだけから決まり、成績を見ずに計算できる)。

## 15. 新しく選んだ主要な数値のハイパーパラメータ(参考)

| 値 | 由来 |
|---|---|
| momentum の窓 20 | V1 の F_US・F_JP の 20 source-business-days の慣行 |
| α_dev = 0.05 | EVAL-SPEC-V1 の α |
| warm-up と NOT_EVALUABLE の下限 250 | MODEL-PART2D-V1 の warm-up の閾値 |

これ以外の決定事項(DA Safety Veto の将来の定義、スナップショットの SHA、実装の仕様、台帳の規則など)は、§9〜§14 に分けて書いた。

## 16. 状態

- P3 = IN PROGRESS(この Trial とは無関係)
- DEV-USDJPY-SIMPLE-01 = SPEC CANDIDATE v0.1 / NOT FROZEN
- V1 Development Replay = NOT STARTED
- この Trial の Development の実行 = NOT STARTED
- Forward = NOT AUTHORIZED
- Holdout(RFX-HOLDOUT-A-V1、5 ペア)= SEALED
