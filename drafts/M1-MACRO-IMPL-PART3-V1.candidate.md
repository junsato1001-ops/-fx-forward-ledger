# M1-MACRO Implementation Spec — Part 3: 状態・予測・台帳(案 v1)

- 状態: **v1 FREEZE CANDIDATE**(Claude、2026-10-17)。v0(Git blob fe48a9c5…)に対するむすびの監査(2026-10-17 06:20 JST、全文を取得して監査、CONDITIONAL PASS)を反映した。
- v0 からの変更:
  1. DA Safety Veto を「評価の側の規則」と定義しない。発行の層では適用しないことだけを定め、新しい決定の方針はこの Part で作らない(§3)。
  2. クラス確率の正規の計算を、Freeze 済みの Model Part 1 §2 に忠実な y の空間の比較にした。z の空間の2分探索は、正規の計算と完全に一致することを試験で保証した場合だけの高速化とする(§5.3)。
  3. 3つの台帳への書き込みを、最後に書く commit の記録(m1_macro_issue_commits.csv)で一つの発行にまとめ、COMPLETE の記録がある Run の行だけを正式の発行とする(§6.4)。途中で失敗した行は消さず、UNCOMMITTED として扱う。書き込みと読み戻しの手順の詳細は Part 4 で定める。
  4. pool の SHA-256 の正規の直列化(バイト列の作り方)を Part 4 で固定することを明記した(§4)。
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
- ABSTAIN_MODEL(モデルが自分の判断で予測を控えること)は、M1-MACRO-V1 の予測の発行では発生しない。M1-MACRO-V1 は予測を控える規則を持たない。
- **M1-MACRO-V1 の予測の発行の層では、DA Safety Veto を適用しない。** DA Safety Veto を使った方向の解釈・決定は、予測の分布を発行することとは別の層であり、その扱いは EVAL-SPEC-V1、または将来 Freeze される決定の方針(Model Part 1 §6 の「別に定める決定の方針」)に従う。**この Part 3 は、新しい決定の方針を定義しない。**
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
- 組み立てた E_{t,h} の入力(群の鍵、x_g、σ_g、y_g、ω_g、pool の SHA-256)を決まった順序(Impl Part 2 §9)で並べた正規の表現の SHA-256 を、E_Input_SHA256 として推定の台帳に記録する。同じ (t, h) を後で再計算するとき、まずこの値が一致することを確かめる。pool と E の入力の正規の直列化(binary64 の生のバイト列か、17 桁の文字列と区切りか、並べる順序、エンディアンなど)は、Part 4 で曖昧さなく固定する。

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
| P_Down、P_Neutral、P_Up(**正規の計算**。σ_M0 ≥ 0 のすべての場合) | pool の各点で x'_j = fl(fl(σ_M0 · Z_j) + μ)、境界 b = fl(0.25 · σ_M0) として、x'_j < −b を Down、−b ≤ x'_j ≤ +b を Neutral(両端を含む)、x'_j > +b を Up と数え、件数 / N | Model Part 1 §2 の y の空間の定義(x'_i = σ_M0 · Z_i + μ、b_t = 0.25 · σ_M0)にそのまま従う。乗算と加算は別々に丸める(融合積和 FMA を使わない) |
| 同(σ_M0 = 0 の場合の帰結) | 上の正規の計算で、すべての点が x'_j = μ、b = 0 になる。μ < 0 なら P_Down = 1、μ > 0 なら P_Up = 1 | S0 の σ = 0 の扱い(Point 0、P_Neutral 1)とは μ = 0 で一致する(μ = 0 なら §5.2 で S0 の文字列を写す)。尺度で割る指標は EVAL-SPEC-V1 §4.1a により METRIC_UNDEFINED_ZERO_SCALE |

- **境界の近くでは、y の空間の比較と z の空間の比較(Z_j + μ/σ と ±0.25)が、binary64 の丸めのために 1 点違う分類になりうる。** 確率は予測そのものなので、正規の計算は上の y の空間の比較だけとする。
- 高速化: x'_j は Z_j について単調(丸めは単調、σ_M0 ≥ 0)なので、並べた pool に対して、**同じ y の空間の比較**を使った2分探索で数えてよい。z の空間の比較や他の近道を使う場合は、全点を y の空間で順に数えた正規の結果と完全に一致することを実装の試験で保証した場合に限る。一致しない場合は正規の計算を使う。
- 確率の件数 / N は、S0 と同じく Python の整数 / 整数(binary64 への正しい丸め)。
- CRPS などの評価は、Model Part 1 §2 のとおり、ずらした離散分布そのものについて EVAL-SPEC-V1 で行う。ここでは計算しない。

## 6. 台帳

既存の正式の台帳のファイル(forecasts、outcomes、runs)の列は変えない。M1-MACRO 用に、次の3つのファイルと、発行のまとまりを記録する commit の台帳(§6.4)を ledger/ に新しく作る。すべて追記のみ(append-only)で、既存のバイトを書き換えない。書いた後に、既存の Storage Verification Gate(verify.py)と同じ方法で、push した内容を読み戻して確かめる。

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

### 6.4 書き換えないことと、一つの発行としてのまとまり(commit の記録)

- 発行した行は、後でデータが改訂されても、コードの誤りが見つかっても、書き換えない。誤りの訂正は、新しい Version の仕様とコードで行い、元の行は残す。
- 追記のみのファイルでは、途中で失敗した行を消せない(たとえば特徴量と推定の行は push できたが、予測の行で失敗した場合)。そこで、**4つ目の台帳 m1_macro_issue_commits.csv に、3つの台帳への書き込みと読み戻しの確認がすべて済んだ後で、最後に1行を追記する。** 列: Run_ID、Origin、Horizon の集合、3つの台帳それぞれについてその Run で追記した行の範囲と SHA-256、Status = COMPLETE、Committed_At_UTC。
- **正式の発行とは、m1_macro_issue_commits.csv に COMPLETE の行がある Run_ID の行だけである。** COMPLETE の行がない Run_ID の行は、消さずに残し、UNCOMMITTED として扱う(評価にも推定の E にも使わない)。
- UNCOMMITTED の行しかない (p, t, h) は、締め切りまでに正式に発行できなかったものとして、§3 の 1(ABSTAIN_SYSTEM)に当たる。締め切りの前なら、新しい Run_ID で発行し直してよい(古い行は UNCOMMITTED のまま残る)。
- 書き込み、push、読み戻し、commit の記録の正確な手順と失敗時の扱いは Part 4 で定める。

## 7. 封印との関係

- 台帳に β、μ、J_Star を書くのは、**M1-MACRO の実装が Freeze された後の Forward の発行だけ**である。この時点では、仕様とコードはすべて Freeze されていて、値を見て変える余地がない(変えるなら新しい Version)。
- 実装の Freeze より前に、実データで β・μ・J_Star を計算して台帳やファイルに書くことはしない。Impl Part 2 §11 の盲検の実行も、これらを出力しない。
- 過去の再構築の期間の β・予測をいつ計算し、いつ見てよいかは、Part 4(決定性・再生・封印)で定める。
- 台帳の値から計算する成績(CRPS、方向、M1 と S0 の差など)は、EVAL-SPEC-V1 §5.5 の確認的な解析(最初の確認的 Origin から 104 週後に1回)まで計算しない。途中の成績の閲覧はしない。

## 8. 実装の検査(Part 4 の検査の一部)

1. μ = 0 の行は、S0 の行と Point・PI・確率の文字列が完全に一致する。
2. 最初の ESTIMATED の Origin より前の FORECAST は、すべて S0 と完全に一致する(Model 2-D §3)。
3. 確率の高速化した数え方は、全点を y の空間で順に調べた正規の数え方と完全に一致する(§5.3)。
4. E_{t,h} を組み立て直すと、E_Input_SHA256 が一致する。
5. 判定の順序(§3)の各分岐を、合成の入力で1つずつ通す試験。
6. ホールドアウトのペアの行が1つも作られないこと。
7. 3つの台帳の書き込みの途中で失敗させた試験で、COMPLETE の行が書かれず、その行が正式の発行として扱われないこと(§6.4)。

## 9. むすびに確認してほしいこと

1. §3 の DA Safety Veto の書き方(発行の層では適用しない。新しい決定の方針は定義しない)が、監査の要求のとおりか。
2. §5.3 の正規の確率の計算(y の空間、x'_j = fl(fl(σ Z_j) + μ)、b = fl(0.25 σ))と、高速化の条件でよいか。
3. §6.4 の commit の記録(m1_macro_issue_commits.csv、COMPLETE のある Run だけが正式、途中の行は UNCOMMITTED として残す)でよいか。手順の詳細は Part 4 に送る。
