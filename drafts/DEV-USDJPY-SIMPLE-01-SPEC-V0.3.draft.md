# DEV-USDJPY-SIMPLE-01 — Development 診断 Trial 仕様(SPEC CANDIDATE v0.3)

- 状態: **SPEC CANDIDATE v0.3**(Claude、2026-10-30)。むすびさんの差分監査待ち。**Freeze ではない。実行の承認でもない。**
- v0.1(V1 repository、commit b83be3fd、blob fac24b0e、SHA-256 7ac945f3…)と v0.2(commit f8b3c41a、blob 96ab0f9d、SHA-256 cc1a68e1…)は、レビューの履歴として drafts/ にそのまま残す。
- v0.2 からの変更(むすびさんの v0.2 の差分監査 REVISE MINOR、2026-10-30 16:43 JST):
  A. **Forward の確認的な仮説を 1D の優越の 1 本にした**。劣後は安全性の報告・記述とする(§11.1)。v0.2 の「1D × 2 方向の Holm」は Claude が独自に入れたもので、確定していなかった。
  B. §7 の「ブロックの数(T / 4、T / 12)」の報告の要求を削除した。stationary bootstrap のブロック長は平均の長さであり、固定長のブロックの数ではないため。
  C. §11.3 の親 S0 の出所に、むすびさんの第一候補 (a) とその理由を記録した。**決定はしていない**(§14 の OPEN のまま)。
- v0.1 から v0.2 への変更(ミッチーさんの監査 REVISE、むすびさんの判定、純さんの決定、2026-10-30 16:33 JST):
  1. **1W を削除**。比較は USD/JPY × 1D × S0 vs MOM20-S0SHIFT の 1 つだけ(§2.1)。
  2. **HAC を Gate から外した**(v0.1 の条件 4 は EVAL-SPEC-V1 §5.4 と矛盾していた)。HAC は必ず報告する(§8、§10)。
  3. Development の p 値を **p_dev**(選択の score)と呼び、有意性の証明ではないと明記(§8)。
  4. **Coverage を Gate から外した**。構造の検査として記録する(§10)。
  5. **N_WARMUP と N_EVAL_MIN を別のパラメータにした**(§5、§7)。
  6. Gate の **estimand** を明記し、全体の共通標本を事前に固定した sensitivity にした(§7)。
  7. ブロック長: 主 = 4、sensitivity = 12(Gate を上書きしない)(§8)。
  8. **非定常性の screen**(後半の D̄ < 0)を Gate に追加し、前半・後半の D̄ と β_t の推移を記述にした(§9、§10)。
  9. **β の引き継ぎ**: Development から Forward へ推定の履歴を途切れさせず、同じ規則で更新し続ける(§11.2)。
  10. **Forward の評価に影響する環境**を、Development の実行の前に固定する項目として §11 に書いた。
  11. DA Safety Veto の書き方を Freeze に合わせた(§9.2)。
  12. `MOM20` は特徴量の名前であって方向の仮説ではないこと、窓 20 は探索を防ぐための慣行的な窓であることを明記(§3.3)。
  13. Trial の台帳は可視化と隠蔽の防止であって、data snooping の補正ではないと直した(§12)。
- 変更の規則: Freeze の後は書き換えない。変更は**別の Trial_ID** とし、§12 の台帳に加える。

---

## 0. 目的と非目的

**目的**: 2026-10-09 までに Target_End が確定した Development の情報だけを使い、S0 を親として、USD/JPY の 20 fix の過去リターン(F_MOM)で位置 μ だけを prequential に動かす 1 本の Challenger について、**warm-up の後の USD/JPY 1D で S0 を改善したか**を診断し、事前に固定した選択の規則(Development Gate)で、prospective Forward の候補にする資格があるかを決める。

**この Trial が答えられる問いは狭い(明記)**:
- 分かるのは、上の 1 つのモデルの、warm-up の後の 1D の性能だけである。
- 「momentum 一般に予測力があるか」「ほかの窓にも予測力があるか」「V1 より良いか」は分からない。NOT_ELIGIBLE でも、ほかの単純なモデルを否定しない。

**非目的**:
- 予測力の確認ではない。Development の結果は確認的な証拠にしない(EVAL-SPEC-V1 §6)。
- 経済的に意味のある効果の確認ではない。δ・Δ_min は定義しない(EVAL-SPEC-V1 §7)。
- Forward の開始の承認ではない。Gate の通過は **FORWARD_CANDIDATE_ELIGIBLE** までであり、**FORWARD_AUTHORIZED ではない**(§10)。
- 既存の Trial(M0・S0・M1-VOL-SHRINK-V1・M1-MACRO-V1)の判定を読み替えない。

## 1. 既存の Freeze との関係

### 1.1 EVAL-SPEC-V1(SHA-256 fdb11fcf…)から自動的に継承するもの

| 項目 | 内容 | EVAL-SPEC-V1 |
|---|---|---|
| 主の損失 | L = CRPS(F, y) / σ_M0,t。離散経験分布は §3.1 の式(fair CRPS を使わない) | §3.1 |
| σ_M0 | M0 v1.2 の VOL_STATE_V1(`frozen/m0_walkforward_v1_2.py`) | §1 |
| 主指標の対象 | σ_M0,t が有限かつ > 0 の機会。0 なら METRIC_UNDEFINED_ZERO_SCALE として除外し件数を報告 | §4.1a |
| 共通標本 | 比べる全モデルが FORECAST かつ Outcome = OBSERVED | §4.1 |
| Decision_Class・Outcome の状態 | §2.1・§2.2 の区分 | §2 |
| 推論の方式 | Politis–Romano stationary bootstrap、B = 10,000、片側の p 値の式、`Generator(PCG64(20261016))` を検定ごとに初期化、Newey–West HAC(Bartlett、lag = ブロック長)は sensitivity(主判定を上書きしない) | §5.1〜§5.4 |
| 副指標・較正 | RPS・Brier・IS/σ_M0・PI80 coverage・Verification-Rank Calibration は記述のみ | §3.2、§3.4 |
| クラス境界 | b_t = 0.25 · σ_M0,t | §3.3 |
| Origin と Target | ORIGIN_TARGET_MAP_V1(`frozen/origin_target_map_v1.py`) | §1 |
| Coverage の非劣化 −2.0pp | Development Gate には使わない(§10)。将来の Forward の確認的な判定では継承する(§11) | §4.2 |
| Forward での判定 | 最初の確認的 Origin から 104 週後に 1 回だけ。途中の成績を見ない | §5.5、§8 |

### 1.2 継承しないもの(この Trial で新しく固定する)

- Holm の族の構造(EVAL-SPEC-V1 の「3 Horizon × 2 方向」とは違う。この Trial の確認的な仮説は 1D の優越の 1 本だけ。§9.1、§11.1)
- Gate の対象を ESTIMATED の機会に絞ること(§7)
- 非定常性の screen(§10)
- ブロック長の sensitivity(§8)

### 1.3 V1 の Freeze の規則を、この Trial が**明示的に採用**するもの(自動の適用ではない)

M1-MACRO-V1 のモデルの Freeze は V1 にだけ効く。この Trial は、結果を見ずに、同じ規則を自分の規則として採用する(§3〜§5)。採用の元: MODEL-PART1-V1、PART2A〜2E-V1、TRANSFORM-PART2A-V1。

### 1.4 触れないもの

- **M1-MACRO-V1**: Development の標本で計算しない。V1 Development Replay = NOT STARTED を維持し、SEAL-OPENING の記録を使わない。
- **金利差の Challenger**: この Trial に入れない(V1 の F_US・F_JP と情報が強く重なるため)。
- **Historical Reserve Holdout(RFX-HOLDOUT-A-V1: GBPJPY・AUDJPY・CADJPY・SGDJPY・KRWJPY の 5 ペア)**: 読まない、導出しない、計算しない(§2.3)。
- **Forward の期間の成績**: M0・S0・M1-VOL・M1-MACRO の Forward の成績を計算しない・見ない(PERFORMANCE_SEAL)。§11.2 の学習の入力の例外だけを、その条件のもとで認める。

## 2. データと標本

### 2.1 対象

- ペア: USD/JPY だけ。
- Horizon: **1D だけ**。1W・4W はこの Trial に含めない(生成もしない)。

### 2.2 Development の機会

- ORIGIN_TARGET_MAP_V1 の formal な 1D の Origin で、**Target_End ≤ 2026-10-09** のものだけ。
- 実現値 y は、§2.3 の固定したスナップショットからだけ計算する。Forward の領域の実現値を読まない。
- 予測の計算に使う情報も、各 Origin の Last_Available_Fix までに切り詰める(point-in-time)。

### 2.3 入力のデータと読み取りの防壁

- 入力: ECB `eurofxref-hist` の**固定したスナップショット**。Freeze の記録に SHA-256 を書き、計算の前に照合する(一致しなければ止まる)。候補: M0・S0 の Development に使ったスナップショット(Freeze の前に特定する)。
- **列の allowlist**: 読み取りの関数は `Date`・`JPY`・`USD` の列だけを返す。それ以外の列(GBP・AUD・CAD・SGD・KRW を含む)は、値を読み込む前に捨てる。「使わない」ではなく「読ませない」。実装の監査でこれを確かめる。
- USD/JPY = JPY_per_EUR / USD_per_EUR(ECB のクロスの既存の定義)。

## 3. モデル

### 3.1 親と参照

- **親(主比較の相手)**: S0-EMPCLIM-STD-EXP-V1(参照実装 `frozen/s0_empclim_std_exp_v1_1.py`)。USD/JPY 1D の Development で計算する。
- **尺度**: M0 v1.2 の σ_M0(EVAL-SPEC-V1 が要求する範囲で計算する)。
- M0・S0 の Development の成績は、EVAL-SPEC-V1 §3.1 の注記のとおりすでに見られている。この Trial で新しく見る成績は Challenger のものだけである。

### 3.2 Challenger: MOM20-S0SHIFT(仮称)

- 予測分布(MODEL-PART1-V1 §2 を採用): 各点 x'_i = σ_M0,t · Z_i + μ_t(i = 1..N、各 1/N)。pool {Z_i}、N、σ_M0,t は **S0 と同じ**。
- μ_t = β_t · F_MOM(t)。**切片なし**(MODEL-PART1-V1 §3 を採用)。β_t = 0 なら S0 と完全に一致する。
- Point・PI80・クラス確率・CRPS は、ずらした分布から MODEL-PART1-V1 §2 と同じ方法で計算する。

### 3.3 特徴量

```
F_MOM(t) = log( P(v) / P(v − 20) )
```

- P = USD/JPY の ECB の正準 fix。
- v = Origin t の Last_Available_Fix(ORIGIN_TARGET_MAP_V1。締め切りまでに公表済みの最後の fix)。
- v − 20 = v から 20 TARGET publication days 前の fix。
- 単位は対数リターンのまま。**標準化しない**(標準化の窓という自由度を入れない)。
- **窓 20 について**: 探索を防ぐために、結果を見ずに 1 つだけ固定した慣行的な窓(V1 の F_US・F_JP の「20 source-business-days の変化」と同じ長さ)である。20 が有効だと期待する根拠があるとは主張しない。この Trial では窓を 1 つだけとし、ほかの窓を試さない(§12)。
- **名前について**: `MOM20` は特徴量の名前であって、予測の方向の仮説ではない。β は符号の制約がない(§4)ので、学習される関係は momentum(β > 0)でも reversal(β < 0)でもありうる。
- 0 は「20 fix の間に動いていない」という中立の点。

## 4. 推定(V1 の規則を採用)

- 損失: ℓ_i(β) = CRPS(F^{S0}_i(· − β F_MOM(i)), y_i) / σ_M0,i(MODEL-PART2A-V1)。
- 推定の標本 E_t: Target_End_i ≤ Last_Available_Fix_t の過去の機会のうち、S0 が FORECAST、F_MOM が定義でき、σ_M0,i が有限かつ > 0、y_i が OBSERVED のもの。時点ごとに過去へ広げる(prequential。MODEL-PART2B-V1)。
- 集計: Origin ごとに等しい重み(1 ペアなので Origin の中の平均は自明)。対象期間の重なりを重みで補正しない(MODEL-PART2B-V1 §4)。
- 正則化なし(λ = 0)。最小値が 1 点に決まらないときは ‖β‖₂ 最小で決める(MODEL-PART2C-V1 §5)。乱数を使わない決定的な方法(線形計画など)で解く。
- 符号の制約なし(MODEL-PART2E-V1)。

## 5. warm-up と欠測(V1 の規則を採用)

- **N_WARMUP = 250**(MODEL-PART2D-V1 の閾値を採用): E_t の相異なる Origin の数が 250 以上になるまで、β_t = 0(Parameter_State = DEFAULT_PARENT。出力は S0 と完全に一致)で FORECAST を出す。一度 ESTIMATED になれば戻らない。N_WARMUP は「β を推定し始める最低限の履歴の量」であり、§7 の N_EVAL_MIN とは別のパラメータである。
- **欠測**(TRANSFORM-PART2A-V1 の考え方を採用):
  - 親の S0 が FORECAST でなければ MODEL_PREREQ_UNAVAILABLE(PARENT_PREREQ_UNAVAILABLE)。
  - F_MOM を作れない(v − 20 の fix が履歴にない)なら MODEL_PREREQ_UNAVAILABLE(FEATURE_PREREQ_UNAVAILABLE)。
  - 特徴量を黙って落とさない。欠測のときに DEFAULT_PARENT に切り替えない。
- **実装の検査**: DEFAULT_PARENT の行と、β_t = 0 になった ESTIMATED の行は、S0 と完全に一致しなければならない。

## 6. 主比較

- **USD/JPY 1D、MOM20-S0SHIFT vs S0**。
- d_t = L_challenger,t − L_S0,t。1 ペアなので d̄_t = d_t。D̄ = (1/T) Σ_t d_t(EVAL-SPEC-V1 §5.1 の形)。

## 7. Gate の対象と estimand

- **estimand**: **post-warm-up の条件付きの性能**。すなわち、Challenger の Parameter_State = ESTIMATED の 1D の機会(EVAL-SPEC-V1 §4.1 の共通標本のうち)での D̄。これは V1 の全共通標本による主判定とは別の量である。
- ESTIMATED は過去の Origin の数だけで決まり、その期間の成績を見て選ぶものではない。Forward は ESTIMATED のまま始まり、warm-up をやり直さない(§11.2)ので、Forward の候補を選ぶ対象としてはこの estimand が近い。
- ESTIMATED の機会は履歴の後ろ側にある。この estimand は「warm-up の後の期間の性能」であって、全期間の性能ではない。
- **全体の共通標本の D̄**(DEFAULT_PARENT の機会を含む)は、**事前に固定した sensitivity** として必ず併記する。Gate には使わない。
- **N_EVAL_MIN = 250**: Gate の対象の相異なる 1D の Origin が 250 未満なら、Gate を判定せず **NOT_EVALUABLE** とし、Forward の候補にしない。N_EVAL_MIN は件数の下限であり、**検出力や実効標本数を保証する値ではない**。「250 あるから統計的に十分」と解釈しない。実際の Origin の数 T と、D̄ の bootstrap の信頼区間(平均ブロック長 4)を必ず報告する。

## 8. 推論

- **主判定**: Gate の対象の {d_t} に stationary bootstrap(平均ブロック長 **4**、B = 10,000、seed `PCG64(20261016)`)。片側の優越(H0: D ≥ 0、H1: D < 0)の p 値を **p_dev** と呼ぶ。
- **p_dev の意味**: Forward の候補を選ぶための**選択上の統計の score** である。Development では、M0・S0 の結果の閲覧、主指標の選定、ブロック長の決定などがすでに行われているので、p_dev に通常の確認的な第一種の過誤の解釈を与えない。**予測力の有意性の証明ではない。**
- ブロック長 4 は EVAL-SPEC-V1 §5.2 の 1D の値(3 ペアの Origin cluster の M0 vs S0 の系列から決まった値)であり、この Trial の損失の差の系列に最適だという根拠はない。そのため次の sensitivity を事前に固定する。
- **sensitivity(どれも Gate を上書きしない。必ず報告する)**:
  - ブロック長 **12** の stationary bootstrap の p 値(12 は EVAL-SPEC-V1 §5.2 にすでにある値)。主判定と符号付きの判定が逆向きなら **BLOCK_SENSITIVITY_DISAGREEMENT** と記録する。
  - Newey–West HAC(Bartlett、lag = 4)の t 検定。逆向きなら **SENSITIVITY_DISAGREEMENT** と記録する(EVAL-SPEC-V1 §5.4)。
  - 劣後の方向の p 値(p_inf)。

## 9. 多重性と DA Safety Veto

### 9.1 多重性

- Gate の検定は 1 つ(1D の優越)なので、Gate の中の調整はしない。p_inf・sensitivity・副指標・較正は記述だけで、Gate に使わない。
- Trial をまたぐ多重性は、§12 の台帳で**記録し可視化する**。台帳そのものは data snooping の補正ではない。最終的な判断は、独立した Forward で行う。

### 9.2 DA Safety Veto

- MOM20-S0SHIFT は位置をずらすモデルなので、EVAL-SPEC-V1 §3.5(MODEL-PART1-V1 §6 と同じ考え方)により、DA Safety Veto の**適用の対象**である(N/A ではない)。
- ただし、具体的な規則はどの Freeze にも定義されていない。EVAL-SPEC-V1 §5.3 の統計的な判定には Veto が入っておらず、§5.5 は「EVAL-SPEC-V1 単独では昇格を決めない」としている。
- したがって、この Trial では:
  - Development Gate に Veto を入れない。
  - 予測の分布の Forward(§11)の開始の条件にも Veto を入れない。
  - 方向の診断(クラスの的中などの記述)は報告するが、その値を見て Veto の閾値を決めない。
  - Veto の正式な規則は、昇格の判断(DECISION_POLICY)に使う前に、別の仕様として Freeze する。Development の結果を見て Veto を設計し、それを予測の発行や見送りに使うことはしない。

## 10. Development Gate

**主 Gate(すべてを満たせば FORWARD_CANDIDATE_ELIGIBLE)**:

1. §7 の Gate の対象が **N_EVAL_MIN = 250** 以上ある(満たさなければ **NOT_EVALUABLE**)。
2. 主判定(ブロック長 4)の **p_dev < 0.05**(α_dev = 0.05 は EVAL-SPEC-V1 の α と同じ値)。
3. **非定常性の screen**: Gate の対象の ESTIMATED の Origin を時系列の順に前半・後半に 2 等分し、**後半の D̄ < 0**(点推定。追加の検定や p 値は使わない)。対象の数が奇数のときは**後半を 1 件多くする**。

条件 2 または 3 を満たさなければ **NOT_ELIGIBLE**。条件を変えて同じ Trial_ID で再実行しない。

**非定常性の screen の意味**: 後半でも優越が統計的に示されたという意味ではない。全期間の改善が古い時期だけによって生じていないことを確かめる、**最低限の recency screen** である。

**Gate には使わず、必ず報告するもの**:
- 全体の共通標本の D̄(§7)
- 前半の D̄、後半の D̄
- β_t の符号と大きさの推移(各 Origin の β_t)
- ブロック長 12 の sensitivity と BLOCK_SENSITIVITY_DISAGREEMENT の有無
- HAC の sensitivity と SENSITIVITY_DISAGREEMENT の有無
- p_inf
- Coverage(Decision coverage など。この設計では S0 にも Challenger にも ABSTAIN_MODEL の規則がないので、構造的に両者とも 100% になる見込み。独立の安全性の証拠とはみなさない)
- 実際の Origin の数 T、D̄ の bootstrap の信頼区間
- DEFAULT_PARENT の機会の件数、METRIC_UNDEFINED_ZERO_SCALE の件数
- 副指標・較正・方向の診断(記述のみ)

**Gate の後**: FORWARD_CANDIDATE_ELIGIBLE でも、Forward は自動では始まらない。Forward の承認には、少なくとも次がすべて要る:

1. Forward の発行の経路(vendor・保存の場所など)の仕様と、その Freeze(§11.4)。
2. Forward の Trial の仕様の Freeze(§11.1〜§11.3 を変えずに引き継ぐこと)。
3. 純さんの明示の承認。

(DA Safety Veto の Freeze は Forward の開始の条件ではない。§9.2)

## 11. Forward の評価に影響する環境(Development の実行の前に固定する)

Development の結果を見てから評価の環境を選べないように、次をこの Trial の Freeze に含める。

### 11.1 予定・発行・判定

| 項目 | 固定する内容 |
|---|---|
| Horizon | 1D だけ |
| Origin・cutoff・Target・正準 fix | ORIGIN_TARGET_MAP_V1(08:30 JST の cutoff、TARGET publication days) |
| 予定の機会 | Forward の最初の Origin 以後の、ORIGIN_TARGET_MAP_V1 の formal な 1D の Origin のすべて |
| 発行の締め切りと遅延 | V1 Part 4 の Verified_At の規則(ON_TIME / LATE)を採用する。LATE の行は確認的な評価に使わない |
| 欠測・発行の失敗 | EVAL-SPEC-V1 §2.1 の Decision_Class(ABSTAIN_SYSTEM と理由のコード、MODEL_PREREQ_UNAVAILABLE)。結果の取得の失敗で Decision_Class を変えない(§2.2) |
| 確認的な判定 | 最初の確認的 Origin から 104 週後に 1 回だけ(EVAL-SPEC-V1 §5.5)。途中の成績を見ない(PERFORMANCE_SEAL を、この Challenger について 104 週の時点まで継続。§8) |
| 確認的な仮説 | **1D の優越の 1 本だけ**(H0: D ≥ 0、H1: D < 0。MOM20-S0SHIFT vs S0)。α = 0.05、仮説が 1 つなので多重性の調整はしない。p_sup < 0.05 なら SUPERIOR_STAT、そうでなければ「優越は確認されなかった」(EVAL-SPEC-V1 §5.5 と同じく、劣っていることを意味しない)。主判定は stationary bootstrap(平均ブロック長 4) |
| 劣後 | **確認的な仮説にしない**。劣後の方向の p 値(p_inf)と D̄ の信頼区間を、安全性の報告・記述として必ず報告する |
| sensitivity・併記 | HAC(lag = 4)とブロック長 12 は sensitivity(主判定を上書きしない)。Coverage の非劣化 −2.0pp を併記(EVAL-SPEC-V1 §4.2) |
| 親 | S0-EMPCLIM-STD-EXP-V1。比較の相手の Forward の S0 の予測の出所は §11.3 |

### 11.2 β と推定の履歴の引き継ぎ

- **推定の履歴を途切れさせない**。Development から Forward まで、§4 の同じ規則で、各 Origin で β_t を推定し直し続ける。warm-up も推定の履歴もリセットしない(Forward は ESTIMATED のまま始まる)。
- **2026-10-09 より後に確定した outcome**(Forward の開始の前のものを含む)も、推定の標本 E_t に入れる。ただし、各 Origin t の Last_Available_Fix_t の時点で**利用可能になったものだけ**を入れる(Target_End_i ≤ Last_Available_Fix_t。将来の情報が混ざらない)。
- **PERFORMANCE_SEAL との関係**: 10-09 より後のキーは S0 の Forward の期間である。推定の目的関数は S0 の分布と y を同じキーで使うので、PERFORMANCE_SEAL_BOUNDARY_V1 §1 の形に当たる。そこで、同 §3 の先例(「推定に使う過去データ上の損失は、仕様の一部であり、発行のコードの中でだけ許される」)に従い、次の条件のもとでだけ認める:
  1. 10-09 より後の outcome は、**凍結した発行のコードの中で、学習の入力としてだけ**使う。
  2. 学習の過程の損失の値や集計を、**人間に表示しない**・記録として出力しない。
  3. **β_t そのものは、発行の行に記録する**(MODEL-PART1-V1 §7 と同じ)。
- Development の実行は 2026-10-09 までの機会だけを扱い、10-09 より後の outcome を学習にも使わない(§2.2)。10-09 より後の outcome を学習に使うのは、Forward の発行のコードの中だけである。

### 11.3 親 S0 の Forward の予測の出所

- **Freeze の前に決める**(§14。この版では決めていない): (a) Forward の発行の経路で、同じ凍結コードで S0 を計算し直す、または (b) V1 の ledger の S0 の発行済みの行(COMPLETE・ON_TIME)を読むだけにする。どちらでも、S0 の予測と y を組み合わせた成績の計算は、104 週の時点まで行わない。
- むすびさんの第一候補は **(a)**(2026-10-30 16:43 JST)。理由: Challenger は各 Origin の S0 の pool と σ_M0 を必要とする。V1 の ledger の完成した行だけに頼ると、V1 の側の発行の障害・LATE・欠損が、この Trial の親のモデルの生成まで左右しうる。最終の決定は、実装の設計と既存の S0 のコードの入出力を確かめてから行う。
- Challenger の予測は、各 Origin で、その Origin の親の S0 の pool と σ_M0 から作る(§3.2)。

### 11.4 Forward の発行の経路について、今から固定する禁止事項

- V1 の `ledger/` にも `replay/` にも書かない。
- V1 の凍結された Code_SHA(d3c77eba…)の対象のコードと workflow を変えない。V1 の repository に、このモデルを足さない。
- V2 の pipeline に載せる場合は、V2 の Requirements の範囲の変更として**新しい版**を作り、監査と Freeze を経る(Freeze 済みの V2 の文書を読み替えない)。
- vendor・保存の場所などの具体的な選択は、Gate が FORWARD_CANDIDATE_ELIGIBLE の場合にだけ決める。これらは予測の値と評価に影響しない範囲に限る(影響する項目は §11.1〜§11.3 ですでに固定した)。

## 12. Development の Trial の台帳(新設の規則)

- `preregistration/DEV-TRIAL-REGISTRY.csv`(追記のみ。案)に、**すべての Development の Trial を、結果に関係なく**記録する: Trial_ID、仕様の SHA-256、Freeze の commit、Challenger の定義の要約、実行の commit、結果の区分(FORWARD_CANDIDATE_ELIGIBLE / NOT_ELIGIBLE / NOT_EVALUABLE / ABORTED)、記録の日時。
- 失敗した Trial、途中で止めた Trial も消さない。
- 台帳の目的は、過去の試行を可視化し、失敗を隠せないようにし、後の解釈で試行の数を確かめられるようにすることである。**台帳そのものは data snooping の補正ではない。**
- 後の Trial(例: 窓を変えた momentum)は、台帳の件数と結果を知ったうえで設計し、その Trial の仕様に台帳の時点の件数を書く。同じ研究の問いへの繰り返しの Trial の数と、Forward に送った候補の総数を、プロジェクト全体で管理する。

## 13. 記録と成果物(実装の仕様で詳細を決める)

- 置き場所: V1 の `ledger/`・`replay/`、V2 の `records/`・`ledger*`・`probe/` のどれとも別の場所(実装の仕様で決める)。
- 予測の行(Origin、Decision_Class、Parameter_State、β_t、F_MOM とその fix の日付、μ、σ_M0、Pool_N、Point、PI、クラス確率)、損失、Gate の計算、スナップショットの SHA-256、コードの SHA-256 を保存する。
- Gate の結果は、§12 の台帳の行と、Gate の記録の 2 つに書く。

## 14. この版で決めていないこと(Freeze の前に必要)

1. §2.3 の ECB スナップショットの特定と SHA-256。
2. §11.3 の親 S0 の Forward の予測の出所(a / b)。
3. 実装の仕様(言語、読み取りの allowlist の実装、検査の一覧、成果物の置き場所、実行の環境)。
4. §12 の台帳の正確な列と置き場所。
5. Development の最初の Origin(M0 の 252 本、S0 の N_overlap_equiv ≥ 100、F_MOM の 20 本の前提がそろう最初の 1D の Origin。暦と履歴の長さだけから決まり、成績を見ずに計算できる)。

## 15. 新しく選んだ主要な数値のハイパーパラメータ(参考)

| 値 | 由来 |
|---|---|
| momentum の窓 20 | V1 の F_US・F_JP の 20 source-business-days の慣行(探索を防ぐための固定) |
| α_dev = 0.05 | EVAL-SPEC-V1 の α |
| N_WARMUP = 250 | MODEL-PART2D-V1 の warm-up の閾値 |
| N_EVAL_MIN = 250 | N_WARMUP と同じ値の、別のパラメータ(件数の下限。検出力の根拠はない) |
| ブロック長 4(主)・12(sensitivity) | EVAL-SPEC-V1 §5.2 の既存の値 |
| 非定常性の screen の分け方(2 等分、奇数なら後半を 1 件多く)と閾値 0 | この Trial の新しい規則 |

これ以外の決定事項は、§9〜§14 に分けて書いた。

## 16. 状態

- P3 = IN PROGRESS(この Trial とは無関係)
- DEV-USDJPY-SIMPLE-01 = SPEC CANDIDATE v0.3 / NOT FROZEN
- V1 Development Replay = NOT STARTED
- この Trial の Development の実行 = NOT STARTED
- Forward = NOT AUTHORIZED
- Holdout(RFX-HOLDOUT-A-V1、5 ペア)= SEALED
