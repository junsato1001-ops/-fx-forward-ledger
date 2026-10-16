# Evaluation Spec v1(Freeze候補)

- 文書ID: EVAL-SPEC-V1
- 状態: FREEZE CANDIDATE v1(むすび監査4点反映済み、最終確認待ち)
- 作成: Claude、2026-10-16 JST
- 対象: 予測分布そのものの統計的評価。売買・資産配分の効用(utility)は対象外(DECISION_POLICY_V1で別途定義)。
- 変更規則: Freeze後は書き換えない。変更が必要な場合は新Version + 変更理由 + 新Trialとする。M0/S0/M1の結果を見て本仕様を動かすことは禁止。

---

## 1. 用語と対象

| 項目 | 定義 |
|---|---|
| 予測機会(opportunity) | (Pair, Origin, Horizon) の1組。Formal scheduleはORIGIN_TARGET_MAP_V1 |
| Horizon | 1D / 1W / 4W。**Horizonごとに独立に評価**し、Horizon間で損失を合算しない |
| Origin cluster | 同じ (Origin, Horizon) をもつ全Pairの機会の集まり。JPY共通要因のため、Pairを独立標本とみなさない |
| 親モデル(parent) | Challengerの主比較相手。M1-VOL系の親はS0。M1-MACROの親は事前登録時に指定する |
| σ_M0,t | Origin t における VOL_STATE_V1 のσ(M0 v1.2)。全モデル共通の尺度とクラス境界に使う |
| y | 実現log-return log(P_End / P_Start) |
| z | y / σ_M0,t |

## 2. 状態とOutcome

### 2.1 予測の状態(Decision_Class)
| 値 | 意味 |
|---|---|
| FORECAST | 予測を発行した |
| MODEL_PREREQ_UNAVAILABLE | 事前Freeze済みの構造的前提が不足(例: M0の252本warmup、S0のN_overlap_equiv不足) |
| ABSTAIN_MODEL | 前提はそろうが、モデル自身の事前規則で見送った |
| ABSTAIN_SYSTEM | 本来出せたのに運用失敗(NOT_ISSUED / DATA_UNAVAILABLE / LATE_ISSUE / PIPELINE_FAILURE / STORAGE_FAILURE 等、理由コード必須) |
| NOT_APPLICABLE | PRE_LISTING / PRE_SCOPE |

### 2.2 Outcomeの状態(予測の状態とは別フィールド)
| 値 | 意味 |
|---|---|
| OBSERVED | Target_EndとTarget_Startのfixが取得でき、yが確定 |
| PENDING | 評価時刻において、Target_Endのfixが暦上まだ公表時刻に達していない |
| UNAVAILABLE | 公表済みのはずなのに値がない |

結果取得の失敗によって、正常に出した予測のDecision_Classを変更しない。

## 3. 評価指標(すべて損失。小さいほど良い。正規化はしない)

### 3.1 主指標(Primary)
**L = CRPS(F_t, y) / σ_M0,t**

- 正規分布 N(μ, s²) の場合: CRPS = s · [ w(2Φ(w) − 1) + 2φ(w) − 1/√π ]、w = (y − μ)/s
- 離散経験分布(点 x_1..x_N に各1/N)の場合:
  CRPS = (1/N) Σ_i |x_i − y| − (1/(2N²)) Σ_i Σ_j |x_i − x_j|
  (N(N−1)で割る「fair CRPS」は使わない)
- 注記: 主指標CRPS/σ_M0は、M0/S0開発結果と検出力診断を見た後に選定した。開発期間での本指標の成績は確認的証拠に使わない。

### 3.2 副指標(Secondary、記述統計のみ。Gateに使わない)
- **RPS**(3クラス、正規化なし): Σ_{k=1}^{2} (P_k^cum − O_k^cum)²
- **Multiclass Brier**: Σ_{c∈{D,N,U}} (p_c − o_c)²
- **Interval Score / σ_M0,t**(α = 0.2):
  IS = (u − l) + (2/α)(l − y)·1(y < l) + (2/α)(y − u)·1(y > u)、l,u は80%予測区間
- **PI80 coverage**: 1(l ≤ y ≤ u)

### 3.3 クラス定義(全モデル共通)
- 境界 b_t = κ·σ_M0,t、κ = 0.25
- Down: y < −b_t / Neutral: −b_t ≤ y ≤ +b_t(両端を含む)/ Up: y > +b_t
- Challengerがσを変えても、クラス境界と実現クラスの判定は σ_M0,t で行う

### 3.4 較正診断(Diagnostic only、Gateに使わない)
- 離散経験分布: L = #{x_i < y}、E = #{x_i = y}、区間 [L/(N+1), (L+E+1)/(N+1)] の質量1を、区間長に比例して10個のbin [0,0.1), [0.1,0.2), …, [0.9,1.0] に配る(乱数を使わない)
- 連続分布(M0): PIT = F(y) を該当binに1として数える
- 名称: Deterministic Verification-Rank Calibration

### 3.5 方向性指標
- DA Safety Vetoは方向情報を主張するモデルにのみ適用。M0・S0・M1-VOL系は N/A。

## 4. 共通標本と分母

### 4.1 精度比較の共通標本
比較する**全モデルがFORECAST** かつ **Outcome = OBSERVED** の機会のみ。

### 4.1a Primary Metric Eligibility(尺度で割る指標の対象)
- CRPS/σ_M0 と IS/σ_M0 は、共通標本のうち **σ_M0,t が有限かつ σ_M0,t > 0** の機会だけを対象とする。
- σ_M0,t = 0 の機会は、予測を無効にせず Decision_Class も変更しないが、尺度で割る指標については **METRIC_UNDEFINED_ZERO_SCALE** として除外する。除外件数は Horizon・Pair・モデル比較ごとに必ず報告する。
- 除外条件はFreeze済みの親M0のσだけで決まり、Challengerの出力には依存しない。
- 非有限の σ_M0 は本来FORECASTにならないため、発生した場合は仕様違反として監査対象とする。
- RPS・Multiclass Brier・PI80 coverage は σ_M0,t = 0 でも定義できるため、共通標本全体で計算する。
- §5 の検定と §5.1 の R は、この Primary Metric Eligible 集合を使う。

### 4.2 Coverage(精度と必ず併記。モデル別・Horizon別)
S = 予定機会のうち NOT_APPLICABLE を除いた件数
| 指標 | 定義 |
|---|---|
| Prerequisite readiness | (S − MODEL_PREREQ_UNAVAILABLE) / S |
| Decision coverage | FORECAST / (FORECAST + ABSTAIN_MODEL) |
| Operational completion | 1 − ABSTAIN_SYSTEM / (S − MODEL_PREREQ_UNAVAILABLE) |

- Coverage非劣化: Decision coverage(Challenger) ≥ Decision coverage(親) − 2.0pp。満たさない場合はCOVERAGE_FAIL。
- M1-VOLはParameter warmup中もw = 0(親S0に縮退、Parameter_State = DEFAULT_PARENT)でFORECASTを出す。warmup不足をMODEL_PREREQ_UNAVAILABLEにしない。

## 5. 推測(inference)

### 5.1 検定統計量
- 機会ごとの損失差 d = L_challenger − L_parent
- Origin cluster ごとに、その (Origin, Horizon) の共通標本にあるPairの d を平均して d̄_t を作る
- 主統計量 **D̄ = (1/T) Σ_t d̄_t**(Originごとに等しい重み。T = 共通標本のOrigin cluster数)
- 相対値を報告する場合は、Origin cluster ごとに L̄_model,t = その (Origin, Horizon) の Primary Metric Eligible なPairの L の平均 を作り、
  **R = mean_t(L̄_challenger,t) / mean_t(L̄_parent,t) − 1** とする(D̄と同じOrigin等重み、同じ集合。比の平均は使わない)

### 5.2 Block bootstrap(主判定)
- 方式: Politis–Romano stationary bootstrap を Origin cluster の時系列 {d̄_t} に適用(同じOriginのPairは常に一緒に抜く)
- 平均ブロック長(Origin単位、2026-10-16 Freeze): **1D = 4、1W = 1、4W = 12**
  (算出規則: 開発期間のM0 vs S0の d̄_t 系列に Politis–White(2004)/Patton–Politis–White(2009)の b_SB を適用し、B_h = max(下限, ⌈b_SB⌉)、下限 1D=1・1W=1・4W=4。b_SB = 3.04 / 0.84 / 11.94)
- 反復回数: 10,000
- 乱数: NumPy `Generator(PCG64(20261016))`。各検定(モデル組 × Horizon)ごとに新たに同じseedで初期化する
- 片側p値(B = 10,000):
  - 優越(H0: D ≥ 0、H1: D < 0): p_sup = (1 + #{b : D̄*_b − D̄ ≤ D̄}) / (B + 1)
  - 劣後(H0: D ≤ 0、H1: D > 0): p_inf = (1 + #{b : D̄*_b − D̄ ≥ D̄}) / (B + 1)
- 信頼区間: D̄*_b のパーセンタイル(片側95%上限 = 95パーセンタイル、下限 = 5パーセンタイル)

### 5.3 判定(Horizonごと)
- 多重性: **Challenger × 親の比較ごとに、3 Horizon × 2方向 = 6仮説を1つの族**とし、Holm法(族全体で α = 0.05)で調整する。優越と劣後を別の族として扱うことはしない。

| 判定 | 条件 |
|---|---|
| SUPERIOR_STAT | そのHorizonの p_sup が Holm調整後 < 0.05 |
| INFERIOR_STAT | そのHorizonの p_inf が Holm調整後 < 0.05 |
| INCONCLUSIVE | どちらも満たさない |
| INFERENCE_ERROR | 同じHorizonで両方向とも調整後 < 0.05(理論上起きない。判定を出さず監査する) |

- これは「統計的に親より損失が小さいか」の判定であり、実務上の優位(Δ_min)や非劣化(δ)の判定ではない(§7)。

### 5.4 Sensitivity(主判定を上書きしない)
- HAC: {d̄_t} に Newey–West(Bartlett kernel、lag = B_h)を適用した t検定を併記
- bootstrapとHACで符号付きの判定が逆向きになった場合は **SENSITIVITY_DISAGREEMENT** と明記

### 5.5 Confirmatory look
- 確認的解析は、各Challengerの最初の確認的Originから **104週後に1回だけ** 行う(途中の成績閲覧・中間解析なし)。
- 104週時点で SUPERIOR_STAT でなければ、統計的優越性は確認されなかったものとして Confirmatory Trial を終了する。
- **EVAL-SPEC-V1 単独では、Challengerの昇格・不採用を決定しない**(INCONCLUSIVE は「劣っている」を意味しない)。親モデルは、別途Freezeされた Decision/Promotion Policy による変更がない限り、運用基準として継続する。

## 6. 標本の区分

| 区分 | 範囲 | 用途 |
|---|---|---|
| Development | 2026-10-09までの全履歴(3ペア) | 構造確認・バグ検出・診断のみ。確認的証拠にしない |
| Historical Reserve Holdout | RFX-HOLDOUT-A-V1(GBPJPY・AUDJPY・CADJPY・SGDJPY・KRWJPY)、ECB snapshot f36e0aff…(2026-10-09まで) | 開封条件(Evaluation Spec・M1 Spec・M1 code hashのFreeze)を満たした後に1回だけ評価。補助的証拠(Forwardの代替にしない、5ペアを独立5回とみなさない) |
| Forward(確認的) | 各モデルのFreeze後、最初のscheduled Origin以降 | 唯一の確認的証拠。M0/S0は1W・4W 2026-10-18、1D 2026-10-19から。dry-runはNに含めない |

- M1-MACROの確認標本は T_freeze(M1-MACRO)後の最初のscheduled Originから。M0/S0との正式なpaired比較のNもそこから数える。

## 7. δ・Δ_min(非劣化margin・最小実務改善量)

- **UNDEFINED_PENDING_DECISION_POLICY**
- 理由: 予測から売買・資産配分への写像(保有資産、取引コスト、許容損失、最大drawdown等)が未定義であり、経済的な許容量を根拠をもって置けないため。検出しやすさからの逆算や慣習値の仮置きは行わない。
- DECISION_POLICY_V1 で事前規定した後、別仕様としてFreezeする。それまでは、§5.3の統計判定のみを行い、昇格判断には用いない。

## 8. Forward成績の封印(PERFORMANCE_SEAL)

- 性質: **procedural, not access-controlled**(公開リポジトリのため、技術的な遮断ではなく手続上の規律)
- 封印期間: M1-MACRO Freezeまで(以後は §5.5 の確認的解析時点まで、該当Challengerについて継続)
- 見てよいもの(運用テレメトリー): ワークフローの成否、予測件数、締切遵守、readback検証、SHA、PENDING→OBSERVED更新、ABSTAIN_SYSTEM、データ取得障害、予測値そのものの再計算照合
- 見ないもの: CRPS・RPS・Brier・IS・較正・的中/外れの集計・M0/S0の差・Pair別成績
- 成績計算コードは、M1-MACRO Freezeまで公開リポジトリに置かない。

## 9. 事前登録の証拠鎖

- 各モデル仕様のFreeze時に、仕様書SHA-256・実装SHA-256・config SHA-256・Freeze時刻を公開リポジトリ(junsato1001-ops/-fx-forward-ledger)にcommitし、そのcommit hashをFormal Forecast Logに保存する。
- 本Evaluation Spec v1も、Freeze時に同じ方法で記録する。

## 10. 未決・別仕様に送る事項

| 事項 | 扱い |
|---|---|
| δ・Δ_min | DECISION_POLICY_V1(§7) |
| M1-VOL-SHRINK-V1 の詳細 | M1 Pilot仕様で別途Freeze(v_long、w推定、Parameter warmup N_overlap_equiv ≥ 250 は合意済み) |
| M1-MACRO の親・特徴量・データ源 | M1-MACRO事前登録で定義 |
| block_length.py(d13fe41e…)のコード監査 | Freezeの必須条件にしない。状態は **BLOCK_LENGTH_CODE_AUDIT = NOT_INDEPENDENTLY_VERIFIED_BY_MUSUBI**。後からコード監査してPASSしても B = {4, 1, 12} は変更しない。重大な実装バグが見つかった場合のみ、EVAL-SPEC-V1を改変せず新Version/新Trialとする |

## 改訂履歴(Freeze前)
- 候補v0(SHA-256 5cca9dce…): 初版
- 候補v1: むすび監査の4点を反映 — §4.1a σ_M0 = 0/非有限の指標対象規則、§5.1 R をOrigin等重みに統一、§5.2–5.3 劣後側p値と6仮説Holm族・INFERENCE_ERROR、§5.5 統計判定と昇格判断の分離。§10 にコード監査状態を追記
