# IMPL-FINDINGS-07 — development blind G6 再実行(40 shard)の結果

- 作成: Claude, 2026-10-19 (JST)
- 対象: M1-MACRO-V1 implementation candidate (未 Freeze)
- 状態: Performance Seal INTACT / Historical Reserve Holdout SEALED / Code_SHA NOT FROZEN / Formal G1–G9 NOT STARTED

## 0. 結論

**development blind G5–G8: PASS(gates_verdict.json all_pass = true)。**
G6 は 40/40 shard 完走、全 (t,h) 集約、errors 0、全 ESTIMATED 行で §10 criterion 全 PASS。

ただし、これは development blind の結果です。candidate readiness ではありません。次は F1-e/F1-d の最終監査(§5)です。candidate Freeze はしていません。

## 1. 実行の同定

| 項目 | 値 |
|---|---|
| workflow run | 39149207082(m1macro-gates, event push, branch m1macro-devblind) |
| source commit | f2aa13065fcdc691a2ffd2fb618ae4cdb3d71338 |
| run_class.txt | DEVELOPMENT_BLIND |
| Code_SHA256(この commit の manifest 値。Freeze ではない) | 2486cfa4c152e2d24ed3c8e6d74dba3b9c9a1b20a25a19edfdd2460d7a12a48b |
| 結果 commit | m1macro-devblind-results 8be142e90aa0c4e092ce565ea05f0e8e18d99b8f |
| 入力 | one-shot development snapshot(main 8ed83c2 / private f424840 / run 39045282957)。再取得なし |
| dev CI(同 commit) | run 39149205510 success |

## 2. 読んだもの・読んでいないもの

- 読んだもの(allow-list): run_class.txt, source_commit.txt, exits.txt, gates_verdict.json, g5_summary.json, g678_summary.json。あとは Actions API のジョブ状態と開始・終了時刻だけです。
- 読んでいないもの: g6_records.jsonl, g5_features_reconstruction.csv、shard 個別の出力。β、β の符号、μ、J*、予測、CRPS、M1−S0 差は一切見ていません。
- 本文には、sealed numeric output は載せていません。載せたのは criterion の PASS/FAIL と件数、実行時間だけです。

## 3. 完全性の確認(F5-b 条件)

| 確認項目 | 結果 |
|---|---|
| 全ジョブ | 43/43 completed/success(suite, g5, g678 ×40, aggregate) |
| G6–G8 shard | 40/40 success。timeout 0、キャンセル 0 |
| exits.txt | 空(非ゼロ exit なし)→ RUN PASS |
| 期待対象数(G5 n_th 合計) | 1D 7111 + 1W 1448 + 4W 1448 = **10007** |
| G6 集約行数 n_th | **10007**(一致) |
| G7 n_keys / n_run_A / n_run_B | 10007 / 10007 / 10007(一致) |
| G7 n_shards | 40 = N_SHARDS |
| 欠損 | 0(n_run_A = n_run_B = n_keys = 期待数) |
| 重複 | 0。根拠は下記で、F7-a の注記あり |

重複が 0 と言える根拠は次の 2 点です。
- shard ごとの (t,h) は dict のキー数で数えています。shard 内に重複があれば、n_keys の合計は 10007 を下回ります。
- shard 間は ctx.th の index を n_shards で割った剰余で分けており、互いに素です。

## 4. Gate ごとの判定(gates_verdict.json, gate_verdict.py で機械計算)

| Gate | 判定 | checks |
|---|---|---|
| G1 | PASS | suite_present, tests_pass, all_ok |
| G2 | PASS | tests_pass, margin_ok |
| G3 | PASS | tests_pass, all_pass |
| G4 | PASS | tests_pass |
| SUITE_ALL | PASS | 24 tests |
| G5 | PASS | summary_present, n_origins_positive, every_origin_has_three_statuses |
| **G6** | **PASS** | summary_present, all_th_covered, no_errors, all_estimated_pass, ub_minus_lb_le_eps, phi2_minus_lb_le_eps |
| G7 | PASS | all_shards, both_runs_complete, e_input_identical, beta_identical |
| G8 | PASS | summary_present, no_mismatch, all_match |
| G9 | PASS | holdout_rows_zero, no_holdout_breach |
| RUN | PASS | exits_file_present, no_job_exit_codes |
| all_pass | **true** | |

### G6 の criterion 別(Impl Part 2 §10、基準は変えていない)

| criterion | 基準 | 結果 |
|---|---|---|
| errors | 0 | 0(error_types 空、subreasons 空) |
| 推定対象のうち全項目 PASS | n_pass_all = n_estimated | 4756 = 4756 |
| (1) §5 \|UB−LB\| | ≤ 1e-13 | PASS(最大 9.9988e-14) |
| (1) §6 \|Φ(β₂)−LB\| | ≤ 1e-13 | PASS(最大 9.9897e-14) |
| (1) 独立実装 gap | ≤ 1e-13 | PASS(最大 9.99e-15) |
| (2) \|UB_A−UB_B\| | ≤ 2e-13 | PASS(最大 9.64e-14) |
| (3) ‖Δβ‖∞ | ≤ 1e-6 | PASS(最大 4.48e-7) |
| μ/σ 照合 | ≤ 1e-4 | PASS(最大 6.60e-6) |

- 表の最大値は、実装 A と B の**一致度**(差)の集計値です。β や μ そのものではありません。どれも g678_summary.json の allow-list 項目です。
- 状態別件数: ESTIMATED 4756、DEFAULT_PARENT 756、NOT_EVALUATED 4495。合計 10007 で、ERROR 状態は 0 です。

## 5. 実行時間(F5-b の記録)

| 項目 | 値 |
|---|---|
| g678 shard job 時間 | 最大 54.3 分(shard 11)、最小 28.9 分 |
| job timeout 設定 | 350 分。最大値でも余裕は約 6.4 倍 |
| shard job 時間の合計 | 1773.9 分 |
| G6 solver 時間の合計(total_sec) | 85764.4 秒(約 23.8 時間。A run 側) |
| wall clock(run 全体) | 17:21:33Z〜19:13:37Z(約 1 時間 52 分) |
| timeout | 0 |

40 shard に分けたことで、前回の 20 shard で起きた timeout は再発しませんでした。前回は 12 shard が timeout し、shard 6 が強制終了しています。

## 6. Findings

### F7-a(Minor、設計上の注記。今回の判定には影響なし)

(t,h) が一意であることは、G5 と G6 の両方が使う ctx.th に依存しています。gate はこれを独立には検査していません。

- shard 内の重複は dict のキー数で検出できます。shard 間は index 分割なので重複しません。
- ただし ctx.th 自体に重複があった場合は、期待数と集約数の両方に同じように数えられてしまいます。
- 提案: Formal 前に、aggregate で `len({(t,h)}) == n_th` を明示的に検査することを提案します。具体的には、G6 rows の (t,h) が一意であることを gate_verdict の check にします。
- これは gate を厳しくする方向の変更です。criterion、solver、上限値には触れません。採否はむすびさんの判断を待ちます。今回は実装していません。

### F7-b(Observation: F6-b の CAUTION に関連)

‖Δβ‖∞ の最大は 4.48e-7 で、基準 1e-6 の約 45% でした。合成データで観測した production β* と exact min-norm 点の差(最大 9.4e-7)より小さく、今回の実データでは基準内に収まっています。

- 余裕は大きくありません。F6-b の扱いは維持します。今後 1e-6 を超えたら G6 FAIL のまま止め、基準は変えずに原因を切り分けます。
- §5 と §6 の最大 9.99e-14 は、production の停止条件(≤ 1e-13)のすぐ下にあります。これは停止規則から当然そうなる値で、異常ではありません。

## 7. 現在の状態と次の手順

| 項目 | 状態 |
|---|---|
| G6(development blind) | **PASS**(前回の FAIL を置き換える) |
| G5/G7/G8/G9(development blind) | PASS |
| F1(F1-e/F1-d) | AUDIT PENDING。次に最終監査 |
| F7-a | むすびさんの判断待ち |
| candidate readiness | 判定しない(F1 監査の後) |
| candidate Freeze | NOT YET |
| Code_SHA | NOT FROZEN |
| Formal G1–G9 | NOT STARTED |
| Performance Seal | INTACT |
| Holdout | SEALED |

次の作業: F1-e/F1-d のコード、negative test、fresh-audit 経路の最終監査を行い、IMPL-FINDINGS-08 として出します。F1 を CLOSE するかどうかは、むすびさんが判断します。
