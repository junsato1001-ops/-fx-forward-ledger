# M1-MACRO Model Spec — Part 2-D: Warm-up(案 v0)

- 状態: **v1 FREEZE CANDIDATE**(Claude、2026-10-17)。v0(Git blob d0752d42…)に対するむすびの監査(2026-10-17 04:11 JST、全文を取得して監査、CONDITIONAL PASS)を反映した。
- v0 からの変更:
  1. 推定を始める条件を、すべての Horizon で「相異なる Origin の数 ≥ 250」にした。4W の ×1/4 は採用しない(§2)。v0 の「×1/4 は実効的な標本の大きさ」という説明は、重なりだけからは導けないので撤回した。
  2. 250 を独立な観測の数や実効的な標本の大きさと呼ばないことを明記した(§2)。
  3. ESTIMATED の機会だけの D̄ を、事前に決めた状態による記述的な条件付きの統計量とし、主判定に使わないと書き直した(§1)。
  4. warm-up の状態の規則と、現在の Origin の特徴量の欠測を区別した。特徴量が欠けたときは欠測の方針に従い、親の予測には切り替えない(§2)。
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
- 参考として、ESTIMATED の機会だけに限った D̄ を示してよい。これは事前に決めた状態による、記述的な条件付きの統計量であり、主判定には使わない(主判定は EVAL-SPEC-V1 のとおり全共通標本)。状態は結果を見て決まるのではないが、ESTIMATED の機会は時期や推定の成熟度が DEFAULT_PARENT の機会と異なる部分集合なので、全体の性能と同じものとして解釈しない。

## 2. 推定を始める条件(閾値と数え方)

**案: すべての Horizon で、推定に使える相異なる Origin の数が 250 以上なら β を推定する。**

- N_warmup,t,h = |E_{t,h}|(Model Part 2-B の推定に使える過去の Origin の数。使えるペアが1つ以上ある Origin を1つと数える。ペアの数は数えない)
- N_warmup,t,h ≥ 250 なら β を推定する(Parameter_State = ESTIMATED)。それ未満なら β = 0(DEFAULT_PARENT)。
- 1D・1W・4W で同じ。**4W の ×1/4(M1-VOL の N_param の係数)は採用しない。**

**250 の意味(言い過ぎないための明記)**: 250 は「250個の独立な観測」や実効的な標本の大きさではない。特に 4W では、週次の Origin の対象期間が重なり、結果は互いに依存する。250 は、モデルの推定を始めるための、事前に決めた最低限の相異なる Origin の数(minimum distinct-origin count)である。統計的に十分であることを示したものではない。

理由:

1. **閾値 250 は値を見ずに決まっている**。M1-VOL で監査・Freeze 済みの値で、M1-MACRO の係数や成績とは無関係である。M1-MACRO の係数は Horizon あたり最大3つで、M1-VOL の1つより多いので、これより低くする理由はない。
2. **重なりは、推定を始める条件ではなく評価の側で扱う**。4W の結果が重なって依存することで、検定に使える実効的な情報が減る問題は、EVAL-SPEC-V1 のブロック bootstrap(4W のブロック長 12)が扱う。warm-up は「β の推定を始めてよい最低限の履歴の量」を決めるもので、役割が違う。Model Part 2-B でも、重なりを目的関数の重みでは補正しないと決めている。
3. **Freeze 済みの3つの Horizon の設計を生かす**。Transformation Part 2-B で、係数を Horizon ごとに別に推定すると決めた。×1/4 を使うと、4W の推定が始まるのは暦の上で最も早くても 2030年3月ごろになり、確認的な Forward の間、4W の M1-MACRO が構造上まったく作動しない(§4)。その代償を払う根拠は、現在の仕様からは見いだせない。
4. **M1-VOL の ×1/4 は M1-VOL の仕様の選択である**。Model Part 2-B で、M1-VOL の N_param を自動では引き継がないと決めている。

### 一度 ESTIMATED になった後

- 一度 warm-up の閾値を満たした Horizon は、その後、warm-up の不足を理由に DEFAULT_PARENT に戻ることはない(E_{t,h} は時間とともに増えるだけなので)。
- **これは warm-up の状態についての規則であり、特徴量の欠測とは別である。** 現在の Origin で N(p) の特徴量が欠けた場合や、親の S0 が予測を出していない場合は、Freeze 済みの欠測の方針(M1-MACRO-TRANSFORM-PART2A-V1)と Model Part 1 §5 に従い、MODEL_PREREQ_UNAVAILABLE または ABSTAIN_SYSTEM(FEATURE_UNAVAILABLE)とする。**このときに DEFAULT_PARENT(親の予測)に切り替えることは禁止する。**
- 同じく、warm-up の閾値に届く前でも、現在の Origin で特徴量が欠けていれば、欠測の方針が優先する(DEFAULT_PARENT の FORECAST は、特徴量がそろっている場合に限る)。

## 3. 実装の検査

- **S0 との一致**: 各 Horizon で最初に ESTIMATED になる Origin より前の FORECAST では、M1-MACRO の出力が S0 と完全に一致しなければならない(M1-VOL §4.4 と同じ種類の検査)。
- ESTIMATED の後に、たまたま β* = 0 になった場合も、出力は S0 と一致する。ただし Parameter_State は ESTIMATED のまま記録する。

## 4. 帰結(暦から計算。値は見ていない)

2010-12-08 以降のすべての Origin で特徴量がそろったと仮定した場合の、最初の ESTIMATED の Origin(実際はこれより遅くなりうる):

| Horizon | 最初の ESTIMATED(この案: 相異なる Origin ≥ 250) | 参考: 4W に ×1/4 を使った場合(採らない) |
|---|---|---|
| 1D | 2011-11 | 2011-11 |
| 1W | 2015-10 | 2015-10 |
| 4W | 2015-10 | 2030-03 |

この案では、確認的な Forward の時点で、3つの Horizon のすべてで β を推定している見込みである。この帰結(暦から決まる日付)を知ったうえでの選択であることを、ここに記録する。帰結は暦だけから決まり、成績の情報は含まない。

## 5. 次(符号の制約)

むすびの順序の最後の段。係数に事前の符号の制約を置くかどうかを決める。
