# M1-MACRO Model Spec — Part 2-D: Warm-up(案 v0)

- 状態: DRAFT(Claude、2026-10-17)。むすびの監査待ち。
- 前提(すべて Freeze 済み): EVAL-SPEC-V1、M1-MACRO-TRANSFORM-PART1/2A/2B-V1、M1-MACRO-MODEL-PART1/2A/2B/2C-V1
- 封印: 係数、損失の値、特徴量の値、成績は見ていない。§4 の日付は、Freeze 済みの ORIGIN_TARGET_MAP_V1(暦)だけから計算した。
- 範囲: (1) β を推定し始める条件(閾値と数え方)、(2) 閾値に届かない間の Decision_Class と出力。むすびの指示どおり、この2つを同時に閉じる。符号の制約は次の段。

## 1. 閾値に届かない間の扱い: 親(S0)に戻して FORECAST を出す

**案: 閾値に届かない (t, h) では β_{t,h} = 0 とし(Parameter_State = DEFAULT_PARENT)、Decision_Class = FORECAST とする。** 出力は Model Part 1 §3 の入れ子の関係により、S0 と完全に一致する。

理由:

1. **特徴量が欠けているのとは違う**。Transformation Part 2-A §5 で区別したとおり、warm-up の間は N(p) の特徴量はそろっている。事前に決めた推定の規則が「まだ推定しない(β = 0)」と決めているだけで、黙って特徴量を落とすこと(禁止事項)には当たらない。
2. **M1-VOL と同じ扱い**。M1-VOL-SHRINK-V1 は parameter warm-up の間 w = 0(DEFAULT_PARENT)で FORECAST を出し、EVAL-SPEC-V1 §4.2 も M1-VOL について「warm-up 不足を MODEL_PREREQ_UNAVAILABLE にしない」としている。
3. **評価への影響が保守的**。DEFAULT_PARENT の機会では M1-MACRO と S0 の損失の差がちょうど 0 になる。比較の平均 D̄ は 0 の方向に薄まり、優越の判定は出にくくなる(有利にはならない)。

代わりの案(閾値に届かない間は MODEL_PREREQ_UNAVAILABLE)を採らない理由:

- Decision coverage への直接の影響はないが、Prerequisite readiness が下がり、共通標本から外れる。Horizon によっては共通標本が空になり、EVAL-SPEC-V1 §5 の検定が定義できなくなる。
- DEFAULT_PARENT なら、その期間は「M1-MACRO は S0 と同じ予測を出した」という事実として記録でき、比較からも除外されない。

**評価での記録(EVAL-SPEC-V1 を変えずに追加で報告するもの)**:

- Horizon ごとに、DEFAULT_PARENT の FORECAST の件数と割合を、性能の指標と並べて報告する。
- 参考として、ESTIMATED の機会だけに限った D̄ も記述統計として示してよい(主判定は EVAL-SPEC-V1 のとおり全共通標本)。状態は暦と推定の規則だけで決まり、結果を見て決まるのではないので、選択の偏りは生じない。

## 2. 推定を始める条件(閾値と数え方)

**案: M1-VOL と同じ数え方と閾値を、M1-MACRO の規則として改めて採用する(自動的な継承ではなく、この文書での選択)。**

- N_param,t,h = |E_{t,h}| × min(1, 名目の起点の間隔 / 名目のホライズンの暦日数)
  - |E_{t,h}| は Model Part 2-B の推定に使える過去の Origin の数(使えるペアが1つ以上ある Origin を1つと数える。ペアの数は数えない)
  - 係数: 1D ×1、1W ×1、4W ×1/4
- N_param,t,h ≥ 250 なら β を推定する(Parameter_State = ESTIMATED)。それ未満なら β = 0(DEFAULT_PARENT)。

理由:

1. **重なりを考えた標本の大きさ**。4W の対象期間は、週次の Origin の間で 4つずつ重なる。重なった残差は強く相関するので、推定に使える情報の量は Origin の数の約 1/4 になる。S0(N_overlap_equiv)と M1-VOL(N_param)も、同じ考え方で数えている。
2. **プロジェクトの中での一貫性**。推定を始める条件を、S0・M1-VOL・M1-MACRO で同じ情報量の単位にそろえる。M1-MACRO の係数は Horizon あたり最大3つで、M1-VOL の1つより多い。そのため、閾値を M1-VOL より低くする理由はない。
3. **値を見ずに決めている**。閾値 250 は M1-VOL で監査・Freeze 済みの値で、M1-MACRO の係数や成績とは無関係に決まっている。

一度 ESTIMATED になった Horizon は、E_{t,h} が時間とともに増えるだけなので、DEFAULT_PARENT に戻らない。

## 3. 実装の検査

- **S0 との一致**: 各 Horizon で最初に ESTIMATED になる Origin より前の機会では、M1-MACRO の出力が S0 と完全に一致しなければならない(M1-VOL §4.4 と同じ種類の検査)。
- ESTIMATED の後に、たまたま β* = 0 になった場合も、出力は S0 と一致する。ただし Parameter_State は ESTIMATED のまま記録する。

## 4. 帰結(暦から計算。値は見ていない)

2010-12-08 以降のすべての Origin で特徴量がそろったと仮定した場合の、最初の ESTIMATED の Origin(実際はこれより遅くなりうる):

| Horizon | 最初の ESTIMATED(案) | 参考: 重なりを数えない場合 |
|---|---|---|
| 1D | 2011-11 | 2011-11 |
| 1W | 2015-10 | 2015-10 |
| 4W | **2030-03** | 2015-10 |

**重要**: この案では、4W の M1-MACRO-V1 は 2030年ごろまで DEFAULT_PARENT(S0 と同じ予測)になる。M1-MACRO の確認的な Forward(Freeze 後の最初の Origin から 104週)の間、4W では M1-MACRO と S0 の差がちょうど 0 になり、4W の判定は INCONCLUSIVE になる(検定の族は EVAL-SPEC-V1 のとおり 6仮説のまま)。M1-MACRO-V1 の確認的な証拠は、実質的に 1D と 1W から得ることになる。

## 5. むすびに判断してほしいこと

1. 閾値に届かない間は β = 0(DEFAULT_PARENT)で FORECAST を出す案でよいか。
2. 閾値と数え方を M1-VOL と同じ(重なりを考えた Origin の数 ≥ 250、4W ×1/4)にする案でよいか。
3. **その帰結として、4W を V1 の確認的な期間で事実上検証しないことを受け入れるか。**
   - 受け入れない場合の代わりの案は「重なりを数えない(相異なる Origin の数 ≥ 250)」。この場合、4W は 2015-10 から推定できるが、重なりで実際の情報量が少ない中で、3つの係数を推定することになる。
   - どちらを選ぶ場合も、この帰結(暦から決まる日付)を知ったうえでの選択であることを記録に残す。帰結は暦だけから決まり、成績の情報は含まない。
