# IMPL-FINDINGS-11 — Formal G1–G9(candidate-1)の結果監査と、Freeze を妨げる F11-a

- 作成: Claude, 2026-10-19 (JST)
- 対象: candidate-1。commit `6f9e09d14efe99760743316f2bfe93e07bc4a7f4`、Code_SHA256 `62afaf46774a76b3dcec22c0f60223e71c91d6f01a7076948ce2597386e70b2b`
- Formal run: **39196332834**(m1macro_gates.yml、branch m1macro-gates、attempt 1)
- 結果: m1macro-gates-results の commit `234accb87ba890caa454ef9abf64e38e0a4fcf9f`(この branch の最初で唯一の commit)
- 状態: Performance Seal INTACT / Holdout SEALED / Code_SHA NOT FROZEN / candidate Freeze NOT YET。sealed の数値出力は開いていない

## 0. 結論

1. **Formal G1–G9 は全項目 PASS。** verdict を candidate 自身の gate_verdict で結果ファイルから再計算すると、保存値と完全に一致した。all_pass = true。完全性、provenance、Code_SHA と candidate の結び付き、snapshot の結び付きも、すべて確認できた。
2. **ただし、candidate-1 のコードのままでは Freeze transaction が必ず拒否される(F11-a)。** 結果 branch への最初の push を、GitHub の activity API は `push` ではなく **`branch_creation`** として記録する。F8-c の照合は `push` しか探さないので、Freeze は `GATE_RESULTS_PUSH_EVENT_NOT_FOUND` で止まる。拒否は何も書く前に起きるので、Version は消費されない(fail closed)。
3. 進め方の選択肢を 2 つ示す(§4)。どちらにするかを、むすびさんに決めていただきたい。Freeze はしていない。コードも config も変えていない(修正案は別 branch に退避し、candidate には入れていない)。

## 1. 読んだもの・読んでいないもの

- **読んだ(allow-list)**: run_class.txt、source_commit.txt、code_sha256.txt、exits.txt、gates_verdict.json、g5_summary.json、g678_summary.json、run_provenance.json、manifest_gate.json、suite.json(合否だけ)、freeze_gate_pre.json。ほかに Actions API、activity API、job の時刻。
- **読んでいない**: g6_records.jsonl、g5_features_reconstruction.csv、shard ごとの出力。β、β の符号、μ、J*、予測、CRPS、M1−S0 差は一切見ていない。
- 本文に載せている G6 の最大値は、実装 A と B の一致度(差)の allow-list 集計値で、sealed 値そのものではない。

## 2. Formal G1–G9 の監査結果

| 項目 | 結果 |
|---|---|
| run_class | **FORMAL** |
| source_commit | 6f9e09d…(= candidate-1) |
| code_sha256.txt | 62afaf46…b2b(= candidate)。manifest_gate も同じ値で、77 entries、pass、violations なし。workflow の集合は manifest と repository で一致 |
| run_provenance.json | run_id 39196332834、attempt 1、ref m1macro-gates、sha 6f9e09d… |
| Actions API(attempts/1) | id、attempt、path `.github/workflows/m1macro_gates.yml`、head_branch m1macro-gates、head_sha 6f9e09d…、event push、completed/success。すべて provenance と一致 |
| m1macro-gates の実行 | この branch の run は 39196332834 の 1 本だけ |
| job | **43/43 success**(suite、g5、g678 × 40、aggregate)。timeout 0。exits.txt は空 |
| suite | 26/26 PASS |
| 期待 (t,h) | G5 n_th = 1D 7111 + 1W 1448 + 4W 1448 = **10007**。universe は n = n_unique = 10007、重複 0 |
| G6 | n_th 10007。key 集合は n = n_unique = 10007、重複 0、universe と同じ SHA-256。errors 0、ESTIMATED 4756 件すべて PASS(n_pass_all = 4756)、subreason なし |
| G6 の各基準 | \|UB−LB\| 9.9988e-14 ≤ 1e-13、\|Φ(β₂)−LB\| 9.9897e-14 ≤ 1e-13、独立実装の gap 9.99e-15、\|UB_A−UB_B\| 9.64e-14 ≤ 2e-13、‖Δβ‖∞ 4.48e-7 ≤ 1e-6、μ/σ 6.60e-6 ≤ 1e-4。**すべて PASS** |
| G7 | n_shards 40。n_keys = n_run_A = n_run_B = n_rows_A = n_rows_B = 10007。E_input / β の不一致 0 |
| G8 | 1962 件すべて一致、不一致 0 |
| G9 | holdout の行 0、breach なし |
| snapshot の結び付き | G5 と全 shard が同じ manifest SHA `310e8475…2769` を記録しており、これは main の dev_snapshot/manifest.json と一致 |
| verdict の再計算 | candidate-1 の gate_verdict.py で再計算した結果は保存値と**完全一致**。G1〜G9、RUN、SUITE_ALL のすべてが PASS |
| 実行時間 | g678 は最長 55.4 分(shard 14)、最短 30.4 分(timeout は 350 分)。全体の wall clock は 1 時間 48 分(03:47Z〜05:35Z) |

**freeze_gate_pre.json が `pass: false` なのは正常。** 検査時刻 2026-10-19T04:29:34Z が、Freeze 窓の下限 2026-10-20T12:00Z(prev(1D) = 10/21 の A_first)より前なので、`CHECK_TIME_BEFORE_PREVIOUS_ORIGIN:1D` になっている。これは「Formal を実行した時点では、まだ Freeze できない」という記録であり、Formal の合否とは関係しない。上限側(A_first 1D 2026-10-21T12:00Z、1W/4W 2026-10-24T12:00Z)の値は readiness と同じ。

開発用の盲検(IMPL-FINDINGS-07)と比べると、G6 の差の最大値、状態ごとの件数、G8 の件数はすべて同じだった。同じ snapshot と同じ数値経路なので、予想どおり。

## 3. F11-a(Blocker): 結果 branch の最初の push は `branch_creation` として記録される

**観測**: activity API で m1macro-gates-results を見ると、記録は次の 1 件だけで、`activity_type=push` で問い合わせると 0 件だった。

```
id 46968308924, activity_type = branch_creation, ref = refs/heads/m1macro-gates-results,
before = 0000000000000000000000000000000000000000, after = 234accb8…, actor = github-actions[bot],
timestamp = 2026-10-19T05:35:06Z
```

ほかの branch でも同じだった。m1macro-gates の最初の push と、devblind の最初の push も `branch_creation` になっている。2 回目以降の push が `push` になる。

**影響**:
- `gate_results`(F8-c)は、結果 commit の event を `kind = push` で探す。
- 結果 commit に親がない場合も、照合の前提が「push で、before の検査を省く」になっていた。
- そのため Freeze の `run()` は、180 秒待った後に `GATE_RESULTS_PUSH_EVENT_NOT_FOUND` で**何も書かずに拒否**する。Version は消費されないが、candidate-1 のコードでは Freeze できない。
- fresh audit も同じ関数を使うので、同じように FAIL する。

**なぜ試験で見つからなかったか**: 試験は偽の API を使い、「最初の push も push として記録される」と仮定していた。実際の GitHub の分類と照合したのは今回が初めてだった。

**修正案**(branch `m1macro-c2-prep`、commit `fb5e415`。**candidate ではない**。workflow も走らせていない):
- 結果 commit に親がなければ、`branch_creation` かつ `before = 40 個の 0` を要求する。
- 親があれば、これまでどおり `push` かつ `before = 親` を要求する。
- API への問い合わせも `activity_type=<kind>` にする。
- 試験には、今回の実際の event の記録をそのまま使った。kind を取り違えると NOT_FOUND、不正な kind は拒否、親が合わなければ MISMATCH、問い合わせ URL の確認。ローカルの freeze 系の試験はすべて ok。

**実データでの確認(読み取り専用)**: 修正案のコードで、candidate-1 の実際の Formal 結果に `gate_results` を通した(API は gh 経由)。
- 結果: Gates_Run 39196332834/1 = VERIFIED、Results_Push 46968308924(2026-10-19T05:35:06Z)= VERIFIED、snapshot 一致、verdict 一致。
- 同じ確認を candidate-1 の規則で行うと `PUSH_EVENT_NOT_FOUND` になり、予測どおりの失敗が再現した。

## 4. 進め方の選択肢(判断をお願いします)

### 案 A: candidate-2(F11-a の修正を入れる)

- 修正を入れた candidate-2 を作り、Code_SHA を計算し直し、readiness → むすびさんの判定 → Formal G1–G9(約 2 時間)を最初からやり直す。
- 日付は candidate-1 と同じにする。Freeze 窓(10/20 21:00〜10/21 21:00 JST)には十分間に合う。
- 長所: 規則そのものが正しくなり、将来 branch を作り直す場合にも壊れない。
- 短所: readiness を通った candidate-1 を捨てることになる。手順も 1 周増える。

### 案 B: candidate-1 のまま、同じ run を re-run する(コードは変えない)

- 同じ run 39196332834 を GitHub の画面から「Re-run all jobs」で再実行する(attempt 2)。
  - 2 回目の結果 commit は 234accb を親に持つので、event は `push` になり、candidate-1 のコードのままで F8-c を満たす。
  - Freeze と fresh audit が照合するのは attempt 2 の provenance と結果 commit になる。
- 長所: candidate-1(readiness PASS、Code_SHA 62afaf46…)を一切触らない。
- 短所:
  - 同じ candidate の Formal を 2 回走らせることになる。1 回目は全 PASS で、選択の余地はないが、その事実は Freeze record と監査に明記する必要がある。
  - 2 回目が 1 回目と違う結果(どこかの FAIL)になった場合の扱いを、先に決めておく必要がある。提案は「2 回目の FAIL は FAIL として candidate-1 を断念する」。
  - F11-a の規則は「最初の結果 commit では成立しない」まま凍結される。この Version では結果 commit が 2 つ目以降になるので、実害はない。
  - **API の書き込みはこの作業環境から通らない(proxy 403)ので、re-run は純さんの手で押していただく必要がある。**

### Claude の推奨

**案 A を推奨します。** 案 B は手早いが、次の 3 点を抱えたまま凍結することになります。

- 照合規則に既知の誤りがある。
- 同じ candidate の Formal を 2 回走らせ、それを説明する例外的な手順が要る。
- 手作業の再実行が要る。

案 A でも、今日中に Formal を終えて Freeze 窓に間に合います。むすびさんが「readiness を通った candidate を触らない価値」の方を重く見るなら、案 B も妥当です。

## 5. 現在の状態

| 項目 | 状態 |
|---|---|
| Formal G1–G9(candidate-1、run 39196332834) | 全項目 PASS(verdict の再計算一致、provenance、完全性、snapshot) |
| F11-a | **BLOCKER**。修正案は m1macro-c2-prep の fb5e415(candidate ではない) |
| candidate-1 の Freeze 可否 | 現在のコードでは不可(拒否は書き込み前に起きるので、Version は消費されない) |
| 案 A / 案 B | むすびさんの判断待ち |
| candidate Freeze | NOT YET |
| Code_SHA | candidate-1 として固定、未 Freeze |
| Freeze 窓 | 2026-10-20 21:00 JST 以上、2026-10-21 21:00 JST 未満(変更しない) |
| Performance Seal | INTACT |
| Historical Reserve Holdout | SEALED |
