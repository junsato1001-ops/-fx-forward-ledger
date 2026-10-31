# DEV-USDJPY-SIMPLE-01 — PRE-FLIGHT BOUNDARY RULING

- 種別: 監査記録(凍結後の監査判断)。**Freeze の本文・freeze.json を変更しない。**
- 判断者: むすび(PRE-FLIGHT AUTHORIZATION AUDIT = PASS。純さん経由 2026-10-31 13:39 JST)
- 記録の方法: 案 (a)(むすびさんの判断 2026-10-31 18:52 JST の中継、純さんの承認 2026-10-31 18:53 JST)
- 対象: DEV-USDJPY-SIMPLE-01(Freeze commit d00e348d7d6bf229b30fc284f2802c65ead101c5、registry commit cb276490bd7c57a2fccb6ce06afb53b47b68e695)、凍結実装 `junsato1001-ops/-fx-dev-trials` a792100770aac264dab2a996aa2af04e92db1984(tree 29d72c501dc49b2e5602e7fc1ec6c873ea2f7088)
- 参照される場所: `trials/DEV-USDJPY-SIMPLE-01/AUTHORIZATION.json` の `boundary_ruling`、DEV-TRIAL-REGISTRY の PREFLIGHT の event の Note
- 記録者: Claude(以下の本文はむすびさんの判定の文言を写したもの)

## 背景(Claude が提示した実装の事実)

- 凍結実装の `preflight()` は `load_inputs()` の後に `model.run_model()` を全部実行し、`preflight_summary()` で件数に要約する。内部では台帳、σ_M0、実現の対数リターン、S0 の pool、F_MOM、β_t、μ、loss_ch・loss_s0 がメモリの上で計算される。
- `gate()`・bootstrap・HAC・`diagnostics()`・`challenger_row()` は実行されず、D̄・p 値は計算されない。
- 出力は日付(first_evaluation_origin、first_estimated_origin、last_in_scope_origin)、状態ごとの件数、N_EVAL、n_eval_min、evaluable だけ。stdout には artifact の path と SHA-256 だけを出す。

## 判定

**PRE-FLIGHT AUTHORIZATION AUDIT = PASS。** 現行 Trial を ABORT して作り直す必要はない。

PASS の意味は限定する: preflight 内部で Development と共通する決定論的計算を実行することは許容する。ただし、その中間値・性能値を観測・保存・出力・ログ化・Gate 判定に使用してはならない。

### 根拠

- 凍結済み FREEZE-PREP §5.2 の規範文は「preflight では Development 計算を実行してはならない」ではなく、「出力するのは、日付・件数・状態だけ」である。仕様が明示的に規制している対象は preflight から外部に出る情報であり、β や loss を内部で一時的に計算すること自体を禁止する規定は、凍結文言から導けない。
- 実装では run_model() 内部で β、μ、loss_ch、loss_s0 等は計算されるが、preflight の成果物には出ない。Gate、bootstrap、HAC、diagnostics は preflight では実行されず、D̄ や p 値も計算されない。「内部計算が存在する」ことと「Development 結果を観測する」ことは区別できる。

### ABORT にしない理由

- 「内部で β や loss を計算しただけでも §5.2 違反」と解釈すると、凍結後に初めて §5.2 へ書かれていない禁止条件を追加することになる。Freeze 後に仕様の意味を厳しく拡張し、その新解釈を理由にコード変更 → Trial ABORT とするのは、事前登録の目的から見ても望ましくない。
- 今回の内部計算は、決定論的・一時的・非保存・非表示である。preflight を先に実行することでモデルを調整したり、β を選び直したり、Gate 条件を変更したりする情報経路もない。情報リークによる研究者自由度の増加も認めない。

## PRE-FLIGHT BOUNDARY RULING(境界)

1. run_model() 内部で、N_EVAL および状態判定を生成するために凍結実装どおり β・μ・loss 等が一時的に計算されることは、FREEZE-PREP v0.1 §5.2 違反とは扱わない。
2. 許容理由は §5.2 が preflight の「出力」を制限しており、内部計算禁止を規定していないため。
3. ただし preflight では、β、μ、loss、D̄、p 値、方向成績、その他の性能情報を表示・保存・ログ・成果物・registry へ出してはならない。
4. Gate、bootstrap、HAC、diagnostics その他の Development 評価処理を追加実行してはならない。
5. preflight 結果を見てモデル、仕様、Gate、実装、Trial 条件を変更して同一 Trial を継続してはならない。
6. この判定は現行の凍結実装 a7921007… に対する解釈であり、将来の Trial 一般への仕様変更ではない。

## 状態(記録の時点)

- DEV-USDJPY-SIMPLE-01 = FROZEN / PASS、PRE-FLIGHT AUTHORIZATION AUDIT = PASS
- PREFLIGHT = AUTHORIZED(preflight のみ。純さん 2026-10-31 18:53 JST)
- DEVELOPMENT = NOT AUTHORIZED、FORWARD = NOT AUTHORIZED、HOLDOUT = SEALED
