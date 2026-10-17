# M1-VOL-SHRINK-V1 仕様(Pilot、Freeze候補)

- 文書ID: M1-VOL-SHRINK-V1
- 状態: FREEZE CANDIDATE v1(むすび監査の判断3点・修正2点を反映、最終確認待ち)
- 役割: **Shadow / Pipeline Pilot**。正式昇格を狙う確認的Trialではない。目的はonline更新・immutable issuance・保存・outcome更新・scoringまでを本番の仕組みで通すこと。
- 親モデル: S0-EMPCLIM-STD-EXP-V1(w = 0 のとき M1 は S0 と一致する)
- 評価: EVAL-SPEC-V1(SHA-256 fdb11fcf…)に従う。主比較は M1 vs S0。DA Safety Veto は N/A。
- 変更規則: Freeze後は書き換えない。変更は新Version + 理由 + 新Trial。

---

## 1. 記号

| 記号 | 定義 |
|---|---|
| p, t, h | Pair、Origin、Horizon(1D/1W/4W) |
| L_t | Origin t の Last_Available_Fix(ORIGIN_TARGET_MAP_V1) |
| H_t | Target Start→End の canonical interval数 |
| r_{p,s} | Pair p の canonical one-session log-return(ECBクロスレート、ledgerと同じ計算) |
| v_EWMA,p,t | VOL_STATE_V1 の1セッション分散(L_t までの252本、M0 v1.2 の `finite_ewma_variance`) |
| σ_M0,p,t | √(H_t · v_EWMA,p,t)。クラス境界と尺度に使う(全モデル共通) |
| y | 実現log-return log(P_End / P_Start) |

## 2. 分散モデル

- **v_long,p,t** = Pair p の、日付が L_t 以下の**全** canonical one-session log-return の二乗平均 mean(r²)(平均を引かない。**各 Pair 自身の最初の canonical return から**累積。一律の開始年は設けない)
- **v_M1,p,t,h(w)** = w · v_long,p,t + (1 − w) · v_EWMA,p,t、w ∈ [0, 1]
- **σ_M1,p,t,h** = √(H_t · v_M1,p,t,h(w_{t,h}))

## 3. w の推定(online、prequential)

各 Origin t、Horizon h ごとに、Pair共通の1パラメータ w_{t,h} を推定する。

### 3.1 推定標本 E_{t,h}
3ペアの過去の機会 i(同じHorizon h)のうち、次をすべて満たすもの:
- Target_End_i ≤ L_t(Origin t の時点で結果が確定している)
- σ_M0,i が有限かつ > 0(VOL_STATE_V1 が定義済み)
- Outcome = OBSERVED、y_i が有限
- H_i > 0
- v_long,i と v_EWMA,i がともに**有限かつ > 0**(grid の端点 w = 0、w = 1 でも QLIKE を定義できる)

v_long,i と v_EWMA,i は、**過去の Origin i 時点**の値(point-in-time)を使う。

### 3.2 損失と選択
- 候補 w ∈ G = {0.00, 0.01, …, 1.00}(101点)
- QLIKE_i(w) = log(σ²_i(w)) + y_i² / σ²_i(w)、σ²_i(w) = H_i · (w·v_long,i + (1 − w)·v_EWMA,i)
- **Origin cluster 等重み**で平均する: 各 Origin について、その Origin で E_{t,h} に入る Pair の QLIKE を平均して Q̄_o(w) = mean_p QLIKE_{p,o}(w) とし、Q̄_h(w) = mean_o Q̄_o(w) とする(EVAL-SPEC-V1 と同じ単位。INRJPY の有無で時期の重みが変わらない)
- Q̄_h(w) を最小にする w を採用。同点なら小さい w。
- これは推定であり、過去に発行した σ_M1,i を書き換えるものではない。

### 3.3 Parameter warmup
- N_param,t,h = E_{t,h} に含まれる**相異なる Origin の数** × min(1, 名目起点間隔 / 名目ホライズン暦日数)
  (1D・1W: ×1、4W: ×1/4。同じOriginの3ペアは1つと数える)
- N_param ≥ 250 なら w_{t,h} を推定(Parameter_State = ESTIMATED)
- N_param < 250 なら **w_{t,h} = 0**(Parameter_State = DEFAULT_PARENT)。このときも Decision_Class は FORECAST。
- 決定(むすび監査): **相異なる Origin の数**で数える。4W は約1,000週(約19年)が必要で、それまでは w = 0(S0)として FORECAST を継続する。同じ Origin の3ペアを独立に数えない原則(EVAL-SPEC-V1 の Origin cluster)と一致させるため。

## 4. 予測分布

### 4.1 標準化残差のpool
- Z_M1,i = y_i / σ_M1,i。σ_M1,i は**過去の Origin i で発行した値**(遡及して再計算しない)
- Pool_{p,t,h} = 同じ Pair・同じ Horizon の過去の機会 i で、Target_End_i ≤ L_t、Outcome = OBSERVED、σ_M1,i が有限かつ > 0 のもの
- Distribution warmup: S0 と同じ N_overlap_equiv ≥ 100(1D・1W: N ≥ 100、4W: N ≥ 400、Pair別)。不足なら M1_WARMUP_INSUFFICIENT(Decision_Class = MODEL_PREREQ_UNAVAILABLE)

### 4.2 発行する分布
- 各 Z_M1,i に確率 1/N を置き、σ_M1,t 倍した離散経験分布 x_i = σ_M1,t · Z_M1,i
- **Point** = σ_M1,t · mean(Z_M1)
- **PI80** = σ_M1,t · [Z_(k10), Z_(k90)]、昇順1始まり、k10 = (N+9)//10、k90 = (9N+9)//10
- **クラス確率**(境界は共通の b_t = 0.25 · σ_M0,t、y空間で比較):
  - P_Down = #{x_i < −b_t} / N
  - P_Neutral = #{−b_t ≤ x_i ≤ +b_t} / N
  - P_Up = #{x_i > +b_t} / N
- CDF(CRPS計算用)は上の離散分布そのもの

### 4.3 特殊な場合
| 状況 | 扱い |
|---|---|
| σ_M0,t が未定義(VOL warmup 不足) | MODEL_PREREQ_UNAVAILABLE(M0_VOL_WARMUP_INSUFFICIENT) |
| σ_M1,t = 0 | 分布は 0 に退化: Point 0、PI [0, 0]、Neutral 1 |
| σ_M1,t が非有限 | 予測を出さず ABSTAIN_SYSTEM(PIPELINE_FAILURE)。仕様違反として監査 |
| E_{t,h} の全機会で QLIKE を定義できない | w = 0(DEFAULT_PARENT) |

### 4.4 S0 との一致(実装検査)
- **最初に ESTIMATED へ移行する以前の、連続した DEFAULT_PARENT 期間**では、M1 が過去に発行した σ もすべて σ_M0 と一致する。したがって、学習に使う pool の対象が同じであれば、M1 の出力は S0 と完全一致しなければならない(自己検査とClaude独立照合の必須項目)。
- 一度でも ESTIMATED を経験した後に w が 0 へ戻った場合は、σ_M1,t = σ_M0,t になっても過去の Z_M1 pool は S0 と同一ではないため、この完全一致条件は**適用しない**。
- 判定は Pair × Horizon ごとではなく Horizon ごと(w は Pair 共通)に、「その Horizon で最初に ESTIMATED になった Origin」より前の期間で行う。

## 5. 発行記録(immutable)

各予測行に次を保存し、以後書き換えない:
Model = M1-VOL-SHRINK-V1、w_{t,h}、Parameter_State、N_param、v_long、v_EWMA、σ_M1、σ_M0、Pool_N、Mean_Z、Q10_Z、Q90_Z、Point、P_Down/P_Neutral/P_Up、PI10/PI90、Decision_Class、Reason_Code、Issued_At_UTC、Data_Zip_SHA256、Code_SHA256、Run_ID

## 6. Historical prequential replay(初期化)

- Freeze済みのコードを、開発期間(ECB snapshot f36e0aff…、2026-10-09まで)の全 Origin に**日付順**で適用し、各 Origin で「w 推定 → σ_M1 発行 → 結果確定分の Z を pool に追加」を繰り返す。
- replay で得た各回の w・σ_M1・Z_M1 の履歴は、Freeze時にSHA-256を取り、変更不可とする。Forward はこの状態から継続する。
- **replay は初期化であり、性能の証拠ではない**(EVAL-SPEC-V1 §6 の Development に属する)。

## 7. Forward と Holdout

- Forward(Shadow): Freeze commit 後の最初の scheduled Origin から、M0・S0 と同じ台帳・同じワークフローで発行する。
- Historical Reserve Holdout(RFX-HOLDOUT-A-V1): EVAL-SPEC-V1・本仕様・実装コードhash のFreeze後に1回だけ評価する。補助的証拠。

## 8. Pilot完了条件

以下がすべて通れば **PILOT_OBJECTIVE_ACHIEVED** として Pilot工程を Close し、以後は Shadow monitoring(記録のみ)とする。予測成績の良し悪しは完了条件に含めない。

1. scheduled opportunity の生成
2. M0/S0/M1 の予測生成
3. prequential な w 更新(Parameter_State の遷移を含む)
4. 発行した σ の immutable 保存
5. Storage Verification Gate(readback 一致)
6. PENDING の記録と PENDING → OBSERVED の更新
7. UNAVAILABLE の処理
8. EVAL-SPEC-V1 に従うスコア生成(封印期間中は運用テレメトリーとしての生成確認のみ、値は見ない)
9. common sample の生成
10. prerequisite readiness / decision coverage / operational completion の生成
11. 監査 manifest・hash の再現
12. 独立実装との照合(§4.4 の S0 一致を含む)

## 9. 改訂履歴(Freeze前)

- v0(SHA-256 336f66f6…): 初版
- v1: むすび監査を反映 — §3.3 N_param は相異なる Origin 数、§3.2 QLIKE は Origin cluster 等重み、§2 v_long は各 Pair の最初の canonical return から、§3.1 推定標本の条件を「有限かつ > 0」「y_i 有限」「H_i > 0」に厳密化、§4.4 S0 完全一致の検査を最初の ESTIMATED 移行前の期間に限定
