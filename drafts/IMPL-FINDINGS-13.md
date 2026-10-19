# IMPL-FINDINGS-13 — Formal G1–G9(candidate-2)の結果監査

- 作成: Claude, 2026-10-20 (JST)
- 対象: **candidate-2**
  - commit `bdf1bfe9a089240083670eb5315dab892794275a`
  - Code_SHA256 `d3c77ebabcb510462373525281bb8adb321ff5035a030bf89307521980a677d4`
- Formal run: **39291810501**(m1macro_gates.yml、branch m1macro-gates、attempt 1)
- 結果 commit: m1macro-gates-results の `f3c2b0abdc14dc912e2f33e40a729ca5f745ba32`(親は candidate-1 の結果 234accb8…)
- 状態: Performance Seal INTACT / Holdout SEALED / Code_SHA NOT FROZEN / Freeze NOT AUTHORIZED YET。sealed の数値出力は開いていない。

## 0. 結論

**candidate-2 の Formal G1–G9 は全項目 PASS。** 次の点をすべて確認した。

- 判定(verdict)を candidate-2 自身の gate_verdict で結果ファイルから計算し直すと、保存値と完全に一致し、all_pass = true。
- 40/40 shard が完走し、全 10007 件がそろい、重複は 0。
- 全 shard が同じ snapshot を読んでいる。
- run は FORMAL の provenance を持ち、candidate commit と Code_SHA に結び付いている。

**追加の確認として、F11-a の実地の照合も PASS。**

- 結果 commit は non-root(親あり)で、activity API 上ちょうど 1 件の `push` として記録されている。
- candidate-2 の `freeze_record.gate_results` を実際の API に読み取り専用で通すと、Results_Push・Server_Evidence ともに VERIFIED になった。

Freeze transaction は実行していない。むすびさんの Formal 結果監査と Freeze の許可を待つ。

## 1. 読んだもの・読んでいないもの

- **読んだもの(allow-list)**: run_class.txt、source_commit.txt、code_sha256.txt、exits.txt、gates_verdict.json、g5_summary.json、g678_summary.json、run_provenance.json、manifest_gate.json、suite.json(合否だけ)、freeze_gate_pre.json。ほかに Actions API、activity API、job の時刻を見た。
- **読んでいないもの**: g6_records.jsonl、g5_features_reconstruction.csv、shard ごとの出力。β、β の符号、μ、J*、予測、CRPS、M1−S0 差は一切見ていない。
- 以下に出てくる G6 の最大値は、実装 A と B の差(一致度)の allow-list 集計値であり、sealed 値ではない。

## 2. Formal G1–G9 の監査

| 項目 | 結果 |
|---|---|
| run_class | **FORMAL** |
| source_commit | bdf1bfe…(candidate-2 と一致) |
| code_sha256.txt | d3c77eba…77d4(candidate-2 と一致)。manifest_gate も同じ値で、78 entries、pass、violations なし。workflow の集合は manifest と repository で一致 |
| run_provenance.json | run_id 39291810501、attempt 1、ref m1macro-gates、sha bdf1bfe… |
| Actions API(attempts/1) | id、attempt、path `.github/workflows/m1macro_gates.yml`、head_branch m1macro-gates、head_sha bdf1bfe…、event push、completed/success。すべて provenance と一致 |
| m1macro-gates の run | 39196332834(candidate-1、superseded)と 39291810501(candidate-2)の 2 本だけ |
| job | **43/43 success**、timeout 0、exits.txt は空 |
| suite | 27/27 PASS(test_activity_kind を含む) |
| 期待 (t,h) | G5 n_th = 7111 + 1448 + 1448 = **10007**。universe は n = n_unique = 10007、重複 0、holdout の行 0 |
| G6 | n_th 10007。key 集合は n_unique 10007、重複 0、universe と同じ SHA。errors 0、ESTIMATED 4756 件すべて PASS |
| G6 の基準 | \|UB−LB\| 9.9988e-14、\|Φ(β₂)−LB\| 9.9897e-14、独立実装の gap 9.99e-15、\|UB_A−UB_B\| 9.64e-14、‖Δβ‖∞ 4.48e-7、μ/σ 6.60e-6。**すべて基準内**(1e-13 / 1e-13 / 1e-13 / 2e-13 / 1e-6 / 1e-4) |
| G7 | 40 shard。n_keys = n_run_A/B = n_rows_A/B = 10007。E_input / β の不一致 0 |
| G8 | 1962 件中 1962 件一致、不一致 0 |
| G9 | holdout の行 0、breach なし |
| snapshot binding | G5 と全 shard が `310e8475…2769` を記録。main の dev_snapshot/manifest.json と一致 |
| verdict の再計算 | candidate-2 の gate_verdict.py で計算し直した値が保存値と**完全一致**。G1〜G9、RUN、SUITE_ALL がすべて PASS |
| 実行時間 | g678 は最長 54.7 分(shard 33)、最短 30.9 分。全体の wall clock は 1 時間 47 分(17:10Z〜18:57Z) |

**freeze_gate_pre.json の `pass: false` は正常。** 検査時刻(2026-10-19T17:10:36Z)が窓の下限(2026-10-20T12:00Z)より前なので、`CHECK_TIME_BEFORE_PREVIOUS_ORIGIN:1D` になっている。A_first と A_previous の値は readiness と同じ。

G6・G7・G8 の件数と差の最大値は、candidate-1 の Formal および開発用の盲検とすべて同じだった。candidate-2 の変更は Freeze の照合部分だけで、数値の経路は変えていないので、予想どおりの結果である。

## 3. F11-a の実地の確認(今回の追加項目)

### 3.1 結果 branch の topology と activity の記録

| commit | 親 | activity の記録 |
|---|---|---|
| 234accb8…(candidate-1 の結果) | なし(root) | **branch_creation** 46968308924。before = 0×40、actor github-actions[bot]、2026-10-19T05:35:06Z |
| **f3c2b0ab…(candidate-2 の結果)** | **234accb8…** | **push 47044332729**。before = 234accb8…、after = f3c2b0ab…、actor github-actions[bot]、2026-10-19T18:57:00Z。`activity_type=push` で問い合わせると、after = f3c2b0ab… の記録は**この 1 件だけ** |

### 3.2 candidate-2 のコードで照合する(読み取り専用。API は gh 経由で実データ)

`freeze_record.gate_results(".", d3c77eba…, bdf1bfe…, snapshot=310e8475…)` の結果は次のとおり。

- git の topology から決まった照合の種類: commit f3c2b0ab…、parent 234accb8…、kind = **push**
- Gates_Run: 39291810501 / attempt 1 → **VERIFIED**
- Results_Push: Activity_ID 47044332729、At_Server_UTC 2026-10-19T18:57:00Z → **VERIFIED**
- 結果の 14 ファイルの SHA-256、FORMAL、candidate、snapshot、verdict の再計算もすべて通過した。

Freeze の際にはこの関数が同じ照合を行い、その出力を Freeze record の Gate_Results に記録する。

## 4. Freeze transaction の手順(許可が出た後)

1. 実行時刻は Freeze の窓の中: **2026-10-20 21:00 JST 以上、2026-10-21 21:00 JST 未満**。
2. candidate-2 の commit(bdf1bfe)を変えずに branch m1macro-freeze へ push する。これで m1macro_freeze_record.yml が動く。
3. workflow の中で次の処理が順に行われる。
   - Code_SHA を container と host の両方で計算し直す。
   - D10 の manifest gate を通す。
   - Pre-Freeze Gate を通す。下限と上限の両方を、main の状態に対して確かめる。
   - gate_results で F1-d、F8-c、F8-d、F11-a を確かめる。
   - record → COMPLETE marker → audit の順に main へ書く。
   - server の時刻で D2 を確かめる。
   - 結果は FINAL か REJECTED のどちらかになる。REJECTED なら、その Version は消費される。
4. FINAL になった後、**10/21 21:00 JST より前に** candidate を main に取り込む(Part 4 §6.1)。M1 のコードと workflow は、まだ main に入っていない。
5. 14 日以内に fresh audit を 1 回実行する。

窓に間に合わない場合は、境界を緩めずに candidate-2 を断念する。

## 5. 現在の状態

| 項目 | 状態 |
|---|---|
| candidate-1 | Formal PASS / SUPERSEDED(F11-a) |
| **candidate-2 Formal G1–G9(run 39291810501)** | **全項目 PASS**(verdict の再計算一致、provenance、完全性、snapshot、F11-a の実地照合) |
| Code_SHA | candidate-2 として固定、まだ Freeze していない |
| Freeze transaction | むすびさんの許可待ち。窓は 10/20 21:00 JST から 10/21 21:00 JST まで |
| Performance Seal | INTACT |
| Historical Reserve Holdout | SEALED |
