# IMPL-FINDINGS-10 — candidate-1 の組み立てと readiness の機械確認

- 作成: Claude, 2026-10-19 (JST)
- **candidate commit: `6f9e09d14efe99760743316f2bfe93e07bc4a7f4`**(branch m1macro-dev)
- **Code_SHA256(CODE_MANIFEST_V1、77 entries): `62afaf46774a76b3dcec22c0f60223e71c91d6f01a7076948ce2597386e70b2b`**
  - これは候補の値で、まだ Freeze していない。Formal G1–G9 と Freeze transaction は、この Code_SHA256 に結びつけて実行する。
- dev CI: run 39187671463(結果は m1macro-dev-results 8d46f84)、**26/26 PASS**。
- readiness の機械確認: `tools/m1macro_candidate/readiness.py` で **23/23 PASS**。
  - このスクリプトは manifest の対象外だが、candidate commit には含めた。
- 状態: Performance Seal INTACT、Holdout SEALED、Code_SHA NOT FROZEN、Formal G1–G9 NOT STARTED。実データ・sealed 出力は見ていない。

## 0. 結論

これまでの修正をすべて含む単一の candidate を組み立て、むすびさんが挙げた項目を機械的に確認しました。結果は全項目 PASS です。

組み立ての途中で、修正候補が 2 つ出ました。

- **F10-a**: Part 3 §2 の「Freeze より後の最初の Origin」という下限が、どこでも検査されていなかった。
- **F10-b**: Formal のコードに、試験用の行数制限という debug 経路が残っていた。

どちらも fail-closed 側の修正として candidate に含めました。統計仕様、solver、criterion、反復の上限、入力は変えていません。

candidate readiness の最終判定、F10-a/F10-b の採否、§3 の日程の承認をむすびさんにお願いします。

## 1. 組み立て内容(candidate-1 で加えたもの)

| 項目 | 内容 |
|---|---|
| config | `first_forward_origin`: **1D 2026-10-22(木)、1W 2026-10-25(日)、4W 2026-10-25(日)**。`config_version` は `M1-MACRO-IMPL-CODE-V1-candidate-1`、`pending` は `[]` |
| A_first(h) = T_info − 6h | 1D: **2026-10-21T12:00:00Z**(10/21 21:00 JST)。1W と 4W: **2026-10-24T12:00:00Z**(10/24 21:00 JST) |
| F10-a | Pre-Freeze Gate に下限を追加した。条件は `A_first(prev(h)) ≤ 検査時刻`。prev(h) は first(h) の直前の正式な Origin。Freeze record には Pre-Freeze Gate の結果を保存し、`is_final` で `marker push ≥ A_first(prev(h))` を要求する |
| F10-b | gates.py から `M1_GATE_LIMIT`(smoke test 用の行数制限)を削除した |
| readiness.py | 機械確認のスクリプト(§2) |

`pending` から外した項目のうち、「first forward origin」は今回の設定で解消しました。「series URLs and column names」は、m1macro/sources.py の固定 URL と、config の `cftc_columns`(dev run で列名を照合済み)で解消済みと判断しました。

## 2. 機械確認の結果(readiness.py、23 項目)

| 区分 | 確認項目 | 結果 |
|---|---|---|
| 全修正を含む | candidate の祖先に次の commit がすべてある: 83f5025(独立実装の厳密な LB)、9cfd825(F5-a)、5abe8aa(§6 の min-norm)、5045178(1e−14)、f2aa130(40 shard)、e72e2d8(F7-a)、15bb31d(F8-a〜d)、4f21436(F8-f、14日、F8-e) | PASS |
| 固定値 | solver 定数(EPS_TIE 1e−13、LAMBDA_LEV 0.3、BOX_B 10、CAND_SIZES 8/12/16/24、STAGE1_MAX 3000、STAGE2_MAX 100、LP_TOL 1e−10)がコード・config・凍結値の 3 つで一致する | PASS |
| | 独立実装の内部精度 REFINE_TOL = 1e−14 | PASS |
| | 照合基準 UB ≤ 2e−13、β ≤ 1e−6、μ ≤ 1e−4(コード上の文字列で確認)、verdict の ε_tie = 1e−13 | PASS |
| | 40 shard が 3 か所すべてで一致する(gate_verdict.N_SHARDS、workflow の N_SHARDS、matrix 0..39) | PASS |
| | SERVER_REVERIFY_WINDOW = 14 日、activity の retry = 12 回 × 15 秒 | PASS |
| | INCOMPLETE と REJECTED は終端状態。record だけがある状態で transaction を始めると VERSION_INCOMPLETE_PRIOR_TRANSACTION で拒否される | PASS |
| manifest | D10 manifest gate が PASS。m1macro/*.py、config、m1macro_*.yml がすべて CODE_MANIFEST_V1 に入っている | PASS |
| config | first_forward_origin が具体的な日付で、pending が空 | PASS |
| | frozen_specs の 4 つの SHA-256 が、main の `preregistration/*.freeze.json` の値とも、`.md` 本体の SHA-256 とも一致する | PASS |
| D2 | Pre-Freeze Gate(上限と下限の両方)が、Freeze 窓の始点と終点の 1 秒前で PASS する。main 側には取得の記録も M1 の台帳の行もない | PASS |
| | 現在時刻が窓の終わりを過ぎていない | PASS |
| snapshot | main の `data/m1macro/dev_snapshot` に触れた commit は 8ed83c2 の 1 つだけ。private commit f424840 が記録されている。manifest の SHA-256 は 310e8475…2769 | PASS |
| | 再取得の guard がある(CANONICAL_SNAPSHOT_EXISTS) | PASS |
| dev/debug | Formal のコードが読む環境変数は GITHUB_RUN_ID、GITHUB_RUN_ATTEMPT、GITHUB_REPOSITORY、GITHUB_TOKEN、GITHUB_WORKFLOW だけ。動的な読み出しもない | PASS(F10-b の後) |
| | Formal の workflow が tools/、dev_indep_stress、STRESS_ を参照していない | PASS |
| | m1macro_dev.yml は m1macro-dev への push だけで動き、Formal の結果 branch に書かない | PASS |
| | FORMAL の結果が書かれるのは branch m1macro-gates からだけ | PASS |
| 変更禁止 | Formal と Freeze が、この Code_SHA256 と candidate commit に結びついている(拒否コード GATE_RESULTS_NOT_FOR_CANDIDATE、CODE_SHA_HOST_CONTAINER_MISMATCH、CHECKOUT_NOT_CANDIDATE、GATE_RUN_MISMATCH) | PASS |
| | worktree が clean(commit されていない変更がない) | PASS |

「candidate の後に統計仕様や solver の criterion を変えない」という条件は、運用で守るものではなく、仕組みで担保しています。仕様の hash は config(Code_SHA の対象)に入っており、Formal・Freeze・fresh audit は同じ Code_SHA256 を要求します。どこか 1 文字でも変えれば Code_SHA が変わり、Formal G1 からやり直しになります。

## 3. Findings と判断のお願い

### F10-a(Major、修正候補): Part 3 §2 の下限が検査されていなかった

**仕様**: 凍結済みの Part 3 §2 は「最初の Forward Origin は、実装の Freeze の commit の時刻より後の、最初の予定された Origin」と定めています。

**問題**: これまでの D2 は、上限(Freeze < A_first(first(h)))しか検査していませんでした。そのため、予定より早く Freeze すると、Freeze と first(h) の間にある Origin が黙って飛ばされ、§2 に反します。

**修正**:
- Pre-Freeze Gate に下限を加えました。条件は「直前の正式な Origin prev(h) の A_first が、検査時刻以前であること」です。早すぎる場合は CHECK_TIME_BEFORE_PREVIOUS_ORIGIN で、**何かを書く前に拒否**します。したがって **Version は消費されず**、窓が開くまで待てば実行できます。
- Freeze record に gate の結果を保存し、`is_final` で `marker push ≥ A_first(prev(h))` を再確認します。

**帰結**: 3 つの Horizon に共通の Freeze 窓ができます。

- 窓 = [max_h A_first(prev(h)), min_h A_first(first(h)))
- candidate-1 では **2026-10-20T12:00Z(10/20 火 21:00 JST)以上、2026-10-21T12:00Z(10/21 水 21:00 JST)未満**の 24 時間です。
- 下限を決めているのは 1D です(prev = 10/21)。1W と 4W の prev は 10/18 で、この下限はすでに過ぎています。

**試験**:
- 境界ちょうどは PASS、その 1 秒前は FAIL。
- 窓が重ならない first(h) の組み合わせは、どの時刻でも PASS しない。
- 直前の Origin が見つからない場合は FAIL。
- record の gate 結果が不正な場合(push が A_prev より前、pass = false、gate 結果がない、A_first が食い違う)は FINAL にならない。正しい対照ケースは FINAL になる。

### F10-b(Minor): debug 経路の除去

gates.py の `M1_GATE_LIMIT` を削除しました。この環境変数を設定すると G6〜G8 の対象行が減る経路です。設定しても verdict の all_th_covered で FAIL になるため、fail-closed ではありました。それでも Formal のコードに debug 用の分岐を残さないために削除しました。

### 日程(承認をお願いします)

候補-1 の日付は、次の日程を前提にしています。

1. 本日(10/19): むすびさんによる readiness 判定の後、branch m1macro-gates に push して Formal G1–G9 を実行する。前回の実績では全体で約 2 時間。
2. 10/20: むすびさんが Formal の結果を監査する。
3. **10/20 21:00 JST から 10/21 21:00 JST の間に、Freeze transaction を実行する。**
4. Freeze が FINAL になった後、**10/21 21:00 JST より前**に candidate を main に取り込む(Part 4 §6.1)。
   - 1D の最初の T_info は 10/22 03:00 JST で、取得はその前の 00:40 / 02:40 JST に行う。取り込みが間に合わなければ、取得の時刻に workflow が main にない。
   - 取り込みの後も、Code_SHA の対象のファイルが candidate と同一であることは、fresh audit(監査するコード = candidate)で確認できる。

窓に間に合わない場合は、日付を変えた candidate-2 を作り、G1 からやり直します。余裕を取りたい場合は、1D の first を **2026-10-23**(窓は 10/21 水 21:00 〜 10/22 木 21:00 JST)にする案もあります。どちらの日付にするかを決めてください。変更する場合は、Formal の前なので、作り直しの費用は小さいです。

## 4. 現在の状態

| 項目 | 状態 |
|---|---|
| F1、F7-a、F8-a〜f | CLOSED |
| development blind G5〜G9 | PASS |
| candidate assembly | **DONE(candidate-1: 6f9e09d / Code_SHA 62afaf46…b2b)** |
| F10-a / F10-b | CORRECTION CANDIDATE(むすびさんの判断待ち) |
| first_forward_origin の日付と Freeze 窓 | 承認待ち |
| candidate readiness | FINAL CHECK PENDING(むすびさん) |
| candidate Freeze | NOT YET |
| Code_SHA | NOT FROZEN |
| Formal G1〜G9 | NOT STARTED(m1macro-gates にはまだ push していない) |
| Performance Seal | INTACT |
| Historical Reserve Holdout | SEALED |
