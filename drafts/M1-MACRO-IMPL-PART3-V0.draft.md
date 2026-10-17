# M1-MACRO Implementation Spec — Part 3: 状態・予測・台帳(案 v0)

- 状態: DRAFT(Claude、2026-10-17)。むすびの監査待ち。
- 前提(すべて Freeze 済み): M1-MACRO-MODEL-PART1/2A〜2E-V1、M1-MACRO-TRANSFORM-PART1/2A/2B-V1、M1-MACRO-IMPL-PART1-V1(データと入力)、M1-MACRO-IMPL-PART2-V1(推定とソルバー)、EVAL-SPEC-V1、S0(参照実装 v1.1)、ORIGIN_TARGET_MAP_V1、正式の Forward 台帳(forward/issue.py、締め切り 08:30 JST)
- 封印: 実データの β、μ、損失、成績は見ていない。
- 範囲: 各 (p, t, h) で、M1-MACRO の判定をどの順で決め、予測の値をどう計算し、何を台帳に書くか。推定の中身(Part 2)、データの取得(Part 1)、決定性・再生・封印の手順(Part 4)は扱わない。

## 1. 対象と時刻

| 項目 | 内容 |
|---|---|
| ペア | USDJPY、CHFJPY、INRJPY(開発・Forward の3ペア)。**ホールドアウトの5ペアには予測を出さず、計算もしない**(RFX-HOLDOUT-A-V1 の封印。ホールドアウトでの検証は、封印を開ける手続きを別に定めてから) |
| Horizon | 1D、1W、4W |
| Origin | ORIGIN_TARGET_MAP_V1 の正式な起点日 |
| 情報の締め切り | T_info(t) = Origin の日の 03:00 JST(Matrix、Impl Part 1) |
| 発行の締め切り | 08:30 JST(正式の Forward 台帳と同じ)。締め切りを過ぎた Origin には予測を出さない |
| 親 | 同じ (p, t, h) で S0 が台帳に発行した行 |

## 2. M1-MACRO の Forward の開始

- M1-MACRO の最初の Forward の Origin(Horizon ごと)は、**実装の Freeze の時点で config に固定する**。値は、実装の Freeze の commit の時刻より後の、最初の予定された Origin とする。
- それより前の Origin に、さかのぼって M1-MACRO の行を発行しない(台帳に行を作らない)。
- EVAL-SPEC-V1 §5.5 の「最初の確認的 Origin」は、この Origin とする。104 週の数え始めもここから。

## 3. 判定の順序(各 (p, t, h))

次の順に調べ、最初に当てはまったものを Decision_Class と Reason_Code にする。

| 順 | 条件 | Decision_Class | Reason_Code(subreason) |
|---|---|---|---|
| 1 | 発行の締め切りまでに行を発行できなかった | ABSTAIN_SYSTEM | NOT_ISSUED / DATA_UNAVAILABLE / LATE_ISSUE(既存の Forward 台帳と同じ規則) |
| 2 | 親の S0 が NOT_APPLICABLE | NOT_APPLICABLE | S0 の Reason_Code をそのまま(PRE_LISTING、PRE_SCOPE) |
| 3 | M1-MACRO の処理の失敗(コード・入力の整合の失敗) | ABSTAIN_SYSTEM | PIPELINE_FAILURE |
| 4 | 親の S0 が ABSTAIN_SYSTEM | ABSTAIN_SYSTEM | PARENT_ABSTAIN_SYSTEM |
| 5 | N(p) の特徴量の取得・読み取りの失敗、暦の整合の失敗(Impl Part 1 §1.1、§7 の 1) | ABSTAIN_SYSTEM | FEATURE_UNAVAILABLE(CALENDAR_INTEGRITY など) |
| 6 | 親の S0 が MODEL_PREREQ_UNAVAILABLE | MODEL_PREREQ_UNAVAILABLE | PARENT_PREREQ_UNAVAILABLE |
| 7 | N(p) の特徴量の前提(Impl Part 1 §7 の 2〜5) | MODEL_PREREQ_UNAVAILABLE | FEATURE_NOT_YET_AVAILABLE / FEATURE_GATE_EXCLUDED / FEATURE_STALE / FEATURE_NOT_COMPUTABLE |
| 8 | warm-up に届かない(|E_{t,h}| < 250、Model 2-D) | FORECAST | (空)。Parameter_State = DEFAULT_PARENT、β = 0 |
| 9 | 推定の失敗(Impl Part 2 §8) | ABSTAIN_SYSTEM | SOLVER_FAILURE(subreason)。Parameter_State = ESTIMATION_FAILED |
| 10 | それ以外 | FORECAST | (空)。Parameter_State = ESTIMATED |

注:

- システムの失敗(3〜5)を、前提の不足(6、7)より先に判定する。取得や処理に失敗した状態では、前提が満たされているかを正しく確かめられないため(Impl Part 1 §7 の順序と同じ考え方)。
- 特徴量の失敗・不足は、そのペアの N(p) の特徴量だけで判定する。F_US だけが失敗した場合、USDJPY は 5 または 7 になるが、CHFJPY・INRJPY は影響を受けない。
- 8〜10 の β は (t, h) ごとに1つ(3ペアで共有)。推定は、その (t, h) で 1〜7 を通ったペアが1つ以上ある場合だけ行う。1つもない場合は推定せず、推定の台帳(§6.3)に Parameter_State = NOT_EVALUATED と記録する。
- ABSTAIN_MODEL(モデルが自分の判断で予測を控えること)は、V1 では発生しない。M1-MACRO-V1 は予測を控える規則を持たない。DA Safety Veto(Model Part 1 §6、EVAL-SPEC-V1 §3.5)は評価の側の規則であり、発行の判定には使わない(§9 の確認事項)。
- Model 2-D §2 のとおり、6・7・9 に当たったときに親の予測(DEFAULT_PARENT)に切り替えることは禁止する。

## 4. 推定に使う過去の機会 E_{t,h} の組み立て(point-in-time)

Model 2-B §2 の定義を、台帳から次のように組み立てる。

| 要素 | 過去の再構築の期間(Forward の開始より前の Origin) | Forward の期間 |
|---|---|---|
| 特徴量の値と状態 | 開発用の snapshot(Impl Part 1 §6)から、Freeze 済みのコードで、**その Origin i の T_info の時点の規則で**計算した値 | M1-MACRO の特徴量の台帳(§6.1)に、Origin i で記録した値。**後で取得し直した値や改訂後の値で置き換えない** |
| 親の S0 の行(Decision_Class、σ_M0、Pool_N など) | Freeze 済みの S0 の出力(参照実装 v1.1、SHA-256 で照合) | 台帳に発行済みの S0 の行 |
| S0 の pool {Z_ij} | Freeze 済みの S0 のコードで同じ入力から再生成し、Pool_N・Mean_Z・Q10_Z・Q90_Z が S0 の行と一致することを確かめる(Impl Part 1 §2.4)。一致しなければ PIPELINE_FAILURE | 同左 |
| 実現値 y_i と Outcome | Freeze 済みの評価のコードが開発用の snapshot から計算した値 | 正式の Outcome の台帳の行(OBSERVED のもの) |

- **改訂の逆流の防止**: E_{t,h} の特徴量は、Origin i で発行した(または、その時点の規則で再構築した)値だけを使う。Origin t の時点で取得したファイルの過去の値(改訂されているかもしれない)で、過去の Origin の特徴量を計算し直さない(Impl Part 1 §5)。
- 群 (p, i) が P_i に入るのは、Origin i で N(p) の特徴量がすべて状態 OK、S0 が FORECAST、Outcome が OBSERVED かつ Target_End_i ≤ Last_Available_Fix_t、σ_M0 が有限かつ > 0 のとき(Model 2-B §2)。
- 再構築の期間と Forward の期間の間に、どちらの資料にも行がない Origin がある場合(たとえば開発用の snapshot の最後の日付から、正式の台帳の最初の Origin までの間)、その Origin は E に入らない。件数を推定の台帳に記録する。補って埋めない。
- 組み立てた E_{t,h} の入力(群の鍵、x_g、σ_g、y_g、ω_g、pool の SHA-256)を決まった順序(Impl Part 2 §9)で並べた正規の表現の SHA-256 を、E_Input_SHA256 として推定の台帳に記録する。同じ (t, h) を後で再計算するとき、まずこの値が一致することを確かめる。

## 5. 予測の値の計算

### 5.1 μ

μ_{p,t,h} = math.fsum([β_k · F_k for k in N(p)])(各積を binary64 で丸めてから、正しく丸めた和)。CHFJPY・INRJPY では β_US を使わない。β は Impl Part 2 の β*(binary64)、F は Impl Part 1 §3(Part 2 §3)の binary64。

### 5.2 μ = 0 のとき: S0 の値をそのまま写す

μ が正確に 0.0(DEFAULT_PARENT、β* = 0、特徴量がすべて 0 など)のとき、Point_LogReturn、PI10、PI90、P_Down、P_Neutral、P_Up は、**S0 の行の文字列をそのまま写す**。計算し直さない。

- これにより、Model Part 1 §3 の入れ子の関係(μ = 0 なら S0 と完全に一致)が、文字列のレベルで保証される。Model 2-D §3 の検査(最初の ESTIMATED より前の FORECAST は S0 と完全に一致)はこれで満たされる。
- −0.0 も 0.0 として扱う。

### 5.3 μ ≠ 0 のとき

S0 の行の値を binary64 として読み(17 桁の文字列は往復で同じビットになる)、次の式で計算し、17 桁("%.17g")で書く。

| 欄 | 計算 | 根拠 |
|---|---|---|
| Point_LogReturn | fl(Point_S0 + μ) | Model Part 1 §2: Point = σ · mean(Z) + μ。S0 の Point = σ · mean(Z) |
| PI10、PI90 | fl(PI10_S0 + μ)、fl(PI90_S0 + μ) | 同じ順位の点に μ を足す |
| P_Down、P_Neutral、P_Up(σ_M0 > 0) | d = fl(μ / σ_M0) として、pool の各点で z'_j = fl(Z_j + d) を作り、z'_j < −κ を Down、−κ ≤ z'_j ≤ +κ を Neutral(両端を含む)、z'_j > +κ を Up と数え、件数 / N | Model Part 1 §2 の y の空間の定義(x'_j < −0.25σ など)と、σ > 0 なら数学的に同じ。z の空間で数えるのは、S0 と同じ κ = 0.25 との比較にし、μ = 0 で S0 と同じ数え方になるようにするため |
| 同(σ_M0 = 0) | すべての点が μ になる。μ < 0 なら P_Down = 1、μ > 0 なら P_Up = 1(境界 b = 0) | Model Part 1 §2 を σ = 0 にそのまま当てはめたもの。S0 の σ = 0 の扱い(Point 0、P_Neutral 1)とは μ = 0 で一致する。尺度で割る指標は EVAL-SPEC-V1 §4.1a により METRIC_UNDEFINED_ZERO_SCALE |

- z'_j は Z_j について単調(丸めは単調)なので、並べた pool に対して2分探索で数えてよい。数えた結果は、すべての点を順に調べた場合と同じでなければならない(実装の検査)。
- 確率の件数 / N は、S0 と同じく Python の整数 / 整数(binary64 への正しい丸め)。
- CRPS などの評価は、Model Part 1 §2 のとおり、ずらした離散分布そのものについて EVAL-SPEC-V1 で行う。ここでは計算しない。

## 6. 台帳

既存の正式の台帳のファイル(forecasts、outcomes、runs)の列は変えない。M1-MACRO 用に、次の3つのファイルを ledger/ に新しく作る。すべて追記のみ(append-only)で、既存のバイトを書き換えない。書いた後に、既存の Storage Verification Gate(verify.py)と同じ方法で、push した内容を読み戻して確かめる。

### 6.1 特徴量の台帳(m1_macro_features.csv、Origin ごとに1行)

Origin、T_info_UTC、各特徴量(F_US、F_JP、F_POS)について: 値("%.17g")、状態(OK / Impl Part 1 §7 の状態)、値の日付(F_US は v と v−20、F_JP は u と u−20)、元の値の文字列(利回り y(v)、y(v−20) など、公表された文字列のまま)、F_POS は Report_Date、Usable_From_UTC、Expected_Release_UTC、Long、Short、Total_OI。取得元ごとに: 取得時刻(UTC)、バイト数、SHA-256、識別情報(米国債は非公開の保管場所のパス。Impl Part 1 §4)。Code_SHA256、Run_ID。

- 特徴量はペアと Horizon によらないので、Origin ごとに1行にする。予測の行はこの行を Origin で参照する。
- Horizon によって Origin の暦が違う場合も、同じ日付の Origin は1行を共有する。

### 6.2 予測の台帳(m1_macro_forecasts.csv、(p, t, h) ごとに1行)

既存の FORECAST_FIELDS と同じ意味の列(Model = M1-MACRO-V1、Pair、Origin、Horizon、Cutoff_JST、Last_Available_Fix、Target_Start、Target_End、Point_LogReturn、P_Down、P_Neutral、P_Up、PI10、PI90、Pool_N、Mean_Z、Q10_Z、Q90_Z、Decision_Class、Reason_Code、Issued_At_UTC、Code_SHA256、Run_ID)に加えて:

- Parent = S0-EMPCLIM-STD-EXP-V1、Parent_Run_ID(参照した S0 の行の Run_ID)、Sigma_M0
- Parameter_State(ESTIMATED / DEFAULT_PARENT / ESTIMATION_FAILED、該当しない場合は空)
- Beta_US(USDJPY のみ)、Beta_JP、Beta_POS、Mu(すべて "%.17g")
- Feature_Row_Origin(§6.1 の参照)
- Estimation_Row_Key(§6.3 の参照)

### 6.3 推定の台帳(m1_macro_estimation.csv、(t, h) ごとに1行)

Origin、Horizon、Parameter_State(ESTIMATED / DEFAULT_PARENT / ESTIMATION_FAILED / NOT_EVALUATED)、N_Warmup = |E_{t,h}|、N_Groups、N_Gap_Origins(§4 の、資料がなく E に入らなかった Origin の数)、N_Excluded_Zero_Scale(σ_M0 = 0 で除外した群の数)、E_Input_SHA256、Beta_US、Beta_JP、Beta_POS、Solver_Status、Solver_Subreason、Stage1_Iterations、Stage2_Iterations、UB_minus_LB、Phi_beta2_minus_LB(Impl Part 2 の確認の値。10 進の文字列)、J_Star、Code_SHA256、Run_ID。

- J_Star は学習データ上の損失である。§7 の封印の規則に従う。

### 6.4 書き換えないこと

- 発行した行は、後でデータが改訂されても、コードの誤りが見つかっても、書き換えない。誤りの訂正は、新しい Version の仕様とコードで行い、元の行は残す。
- 予測の行・推定の行・特徴量の行のどれかを書けなかった場合、その Origin の M1-MACRO の行は発行しない(§3 の 1 で、締め切り後に ABSTAIN_SYSTEM)。3つの台帳の間で、片方だけが書かれた状態を正式の発行としない。

## 7. 封印との関係

- 台帳に β、μ、J_Star を書くのは、**M1-MACRO の実装が Freeze された後の Forward の発行だけ**である。この時点では、仕様とコードはすべて Freeze されていて、値を見て変える余地がない(変えるなら新しい Version)。
- 実装の Freeze より前に、実データで β・μ・J_Star を計算して台帳やファイルに書くことはしない。Impl Part 2 §11 の盲検の実行も、これらを出力しない。
- 過去の再構築の期間の β・予測をいつ計算し、いつ見てよいかは、Part 4(決定性・再生・封印)で定める。
- 台帳の値から計算する成績(CRPS、方向、M1 と S0 の差など)は、EVAL-SPEC-V1 §5.5 の確認的な解析(最初の確認的 Origin から 104 週後に1回)まで計算しない。途中の成績の閲覧はしない。

## 8. 実装の検査(Part 4 の検査の一部)

1. μ = 0 の行は、S0 の行と Point・PI・確率の文字列が完全に一致する。
2. 最初の ESTIMATED の Origin より前の FORECAST は、すべて S0 と完全に一致する(Model 2-D §3)。
3. 確率の2分探索の数え方は、全点を順に調べた数え方と一致する。
4. E_{t,h} を組み立て直すと、E_Input_SHA256 が一致する。
5. 判定の順序(§3)の各分岐を、合成の入力で1つずつ通す試験。
6. ホールドアウトのペアの行が1つも作られないこと。

## 9. むすびに確認してほしいこと

1. §3 の順序、特に「システムの失敗(3〜5)を前提の不足(6・7)より先に判定する」ことでよいか。新しい Reason_Code の PARENT_ABSTAIN_SYSTEM を加えてよいか。
2. ABSTAIN_MODEL が V1 で発生しないこと、DA Safety Veto を発行の判定に使わず評価の側の規則とすることでよいか(Model Part 1 §6 は「別に定める決定の方針に従う」としている。その方針はまだ定めていない)。
3. §4 の、E_{t,h} の特徴量を Origin i で記録した値だけから作る(改訂後の値で計算し直さない)規則と、資料のない Origin を E から外す(補わない)規則でよいか。
4. §5.2 の、μ = 0 のときに S0 の文字列を写す規則と、§5.3 の確率を z の空間(z'_j = Z_j + μ/σ)で数える規則でよいか。σ_M0 = 0 の扱いでよいか。
5. §6 の、M1-MACRO 用に3つの台帳のファイルを新しく作る(既存のファイルの列は変えない)構成でよいか。
6. §7 の、β・μ・J_Star を台帳に書くのは実装の Freeze 後の Forward の発行だけとする規則でよいか。
