# IMPL-FINDINGS-08 — F1-e / F1-d 最終監査と F7-a 実装

- 作成: Claude, 2026-10-19 (JST)
- 対象: M1-MACRO-V1 implementation candidate(未 Freeze)。branch m1macro-dev
  - F7-a: commit e72e2d8a876ce816e7ccc463efb193600d5880e1
  - F8-a〜F8-d: commit 15bb31dec4ed5e1ec552d0c4c4cd95520769fbd2
- 監査範囲: m1macro/freeze_record.py, m1macro/gate_verdict.py, m1macro/gates.py(集計部分), .github/workflows/m1macro_freeze_record.yml, .github/workflows/m1macro_gates.yml(aggregate), m1macro/test_freeze_record.py
- 状態: Performance Seal INTACT / Holdout SEALED / Code_SHA NOT FROZEN / Formal G1–G9 NOT STARTED。実データ・sealed 出力は一切読んでいない(今回の作業はすべて合成データとコードのみ)

## 0. 結論

**F1 = CORRECTION CANDIDATE(CLOSE ではない)。**

むすびさんが挙げた確認項目は、修正前のコードでも本筋では満たされていました。ただし監査の途中で fail-closed 側の穴が 4 つ見つかりました。

- F8-a: fresh audit がいずれ必ず失敗する。
- F8-b: fresh audit が git の履歴と結びついていない。
- F8-c: gate 結果の出所(provenance)を検証していない。
- F8-d: Formal G5–G8 が使った snapshot を Freeze 側で照合していない。

4 つとも修正候補を実装し、negative test を付けました。どれも検査を厳しくする方向の変更で、solver、criterion、反復上限、入力値は変えていません。F1 を CLOSE するかどうかは、むすびさんの監査の後になります。

F7-a(むすびさん採用済み)は実装しました(§1)。

## 1. F7-a の実装(ACCEPTED → IMPLEMENTED)

| 箇所 | 内容 |
|---|---|
| `gates.th_keyset(keys)` | 出現をすべて数える(重複も 1 件ずつ数える)。返り値は `n`, `n_unique`, `n_duplicate`、および distinct key を整列して連結した SHA-256 |
| G5 (`g5_summary.json`) | 期待 universe `ctx.th` の `th_universe`(**ctx.th 自身の一意性を独立に検査**) |
| G6 aggregate | G6 の行の `th_keyset` |
| G7 shardsum | dict にキー付けする**前の**行数 `n_rows_A` / `n_rows_B` |
| gate_verdict G5 | `th_universe_unique`: `n == n_unique == Σn_th` かつ `n_duplicate == 0` |
| gate_verdict G6 | `th_rows_unique`: `len(G6 rows) == n_unique == expected_n_th` かつ重複 0。`th_keyset_equals_universe`: G6 の key 集合の SHA-256 が universe の SHA-256 と等しい |
| gate_verdict G7 | `no_duplicate_rows`: `n_rows_A == n_rows_B == expected_n_th` |

- 重複を除いたり、自動で修復したりする処理は入れていません。重複が 1 件でもあれば、その Gate は FAIL です。
- key 集合の照合を加えたので、「件数は合っているが重複 1 件と欠損 1 件が打ち消し合う」場合と、「universe の外の key が混じる」場合も FAIL になります。
- test_gate_unique.py(dev_suite に登録)で確認した FAIL 事例:
  - universe 自身の重複
  - G6 の重複と欠損の打ち消し合い
  - universe 外の key
  - key 集合の欠落(古い形式の集計)
  - universe の欠落
  - G7 の行の重複
  - G7 の行数の欠落
- 合成データで shardsum と aggregate を通し、重複行がそのまま件数に現れることを確認しました(G6 は n_th 5、n_duplicate 1。G7 は n_rows_A 5、n_run_A 4)。
- むすびさんの判断に従い、development G6 の再実行はしません。Formal では F7-a を含む固定 candidate で G1–G9 を最初から実行します。

## 2. 監査結果: むすびさんの確認項目

### F1-e

| 確認項目 | 修正前 | 根拠と修正後 |
|---|---|---|
| COMPLETE marker commit と server 側の push event が一意に対応する | 条件付きで OK | `find_push` は `ref=refs/heads/main` かつ `after == Marker_Commit` の push が **ちょうど 1 件**の場合だけ通す。ただし**1 ページ目(100 件)しか見ていなかった**(F8-a)。修正後は全ページを読み、加えて `before == Marker_Commit^` と `actor == github-actions[bot]` を要求する |
| 0 件 → REJECTED | OK | 固定待機(12 回 × 15 秒)の後に PUSH_EVENT_NOT_FOUND → REJECTED。test: `missing` |
| 複数件 → REJECTED | OK | PUSH_EVENT_NOT_UNIQUE は待機せず即確定。test: unit_find_push |
| timeout / API 障害 → REJECTED | OK(試験を追加) | 待機を使い切ると ACTIVITY_API_FAILED。**修正前はこの経路に試験がなかった**ので追加した(sleep 11 回で確定) |
| fresh audit で同じ server timestamp を再取得できる | **NG(F8-a)** | 1 ページ目しか読まないため、main への push が 100 件を超えると marker の push が見えなくなる。main への push は repo 作成(10/16)からの約 3 日で 86 件あり、Freeze から数日で fresh audit が必ず PUSH_EVENT_NOT_FOUND になる。誤って PASS にする方向ではなく誤って FAIL にする方向だが、「後から再確認できる」という要件を満たさない。修正後は全ページを読む |
| 正式な D2 が T_marker,push,server < A_first(h) | OK | `d2_ok`: すべての h で `marker_push < af[h]`(strict)。runner の時刻は D2 の証拠に使わない。test: push が A_first ちょうど → REJECTED、1 秒前 → FINAL |

秒未満を切り捨てても判定が緩くならないことを再確認しました。

- A_first は秒単位の整数時刻です。真の push 時刻が A_first 以上なら、切り捨てた値も A_first 以上になります。
- Recorded 時刻 < push 時刻であれば、切り捨てた後も Recorded ≤ push が保たれます。
- activity API の timestamp の形式は `YYYY-MM-DDTHH:MM:SSZ` で、`parse_utc` と一致することを実際の API で確認しました。

### F1-d

| 確認項目 | 結果 |
|---|---|
| FORMAL run であること | OK。`run_class.txt == FORMAL` でなければ GATE_RESULTS_NOT_FORMAL。development blind の結果は Freeze に使えない(test あり) |
| 固定 candidate と同じ Code_SHA / commit | OK。結果側の `code_sha256.txt` は host が再計算した Code_SHA256 と一致し、`source_commit.txt` は candidate、checkout HEAD は candidate |
| G1–G9 すべて PASS を、Freeze 側が拒否不能な形で検査している | OK。保存された `gates_verdict.json` を、Freeze 側で結果ファイルから再計算した verdict と比較し、完全一致かつ all_pass を要求する。`gate_results` は transaction の前に呼ばれ、失敗すれば何も書かない |
| **結果が実際に正式な gates run から出たものか** | **NG(F8-c)**。`m1macro-gates-results` の内容をそのまま信用していた。書き込み権限のある者が自前で作った結果を commit すれば、検査をすべて通せた |
| **Formal の G5–G8 がどの snapshot を読んだか** | **NG(F8-d)**。結果ファイルに snapshot の識別子がなく、record の Dev_Snapshot と照合していなかった |

## 3. Findings と修正候補

### F8-a(Major): activity API の 1 ページ目しか読まない

- **問題**: `activity_lookup` が `per_page=100` の 1 ページ目しか読みません。そのため次の 2 点が起きます。
  - fresh audit が、Freeze から数日で必ず FAIL する。
  - 一意性の判定が 1 ページ目の中だけになっている。
- **修正**:
  - `Link: rel="next"` を最後のページまでたどります。上限は 100 ページ(10,000 件)で、超えたら ACTIVITY_PAGES_EXCEEDED として fail closed にします。途中までのリストでは判定しません。
  - 次の 2 条件を追加しました。
    - `before == Marker_Commit^`: その push が marker commit の親から main を進めたこと。
    - `actor == github-actions[bot]`: workflow による push であること。
  - 親 commit が求められない場合は、push event を問い合わせずに MARKER_PARENT_UNKNOWN で REJECTED にします。
  - 「一意でない」「親が一致しない」「actor が一致しない」は待機せず即確定です。
- **試験**:
  - 3 ページ目にある event を発見できる。
  - 親の不一致と actor の不一致は即 FAIL になり、待機しない。
  - 無限に続くページは ACTIVITY_PAGES_EXCEEDED。
  - API が止まり続ける場合は ACTIVITY_API_FAILED。
  - 親が不明な場合は REJECTED で、push の問い合わせをしない。
- **残るリスク(要判断)**: GitHub が activity の履歴をどれだけ保持するかは、公開文書で確認できませんでした。将来古い event が消えれば、fresh audit は FAIL します。これも誤って FAIL にする方向で、誤って PASS にはなりません。fresh audit で server 側の再取得を必須にするのは「Formal 監査の期間中だけ」でよいか、むすびさんの判断をお願いします。期間外については、Freeze 時の監査 row と F8-b の git による結び付けを証拠とする案を提案します。

### F8-b(Minor〜Major): fresh audit が git の履歴に結びついていない

- **問題**: 3 ファイルの内容と activity の照合はしていました。しかし、監査 row の `Marker_Commit` が実際に「その marker と record を持つ commit」かどうかは見ていませんでした。
- **修正**: `git_binding()` を追加しました。次をすべて満たすことを要求します。
  - `Marker_Commit` が HEAD の祖先である。
  - `Marker_Commit` が現在の marker と record の bytes をそのまま持つ。
  - `Marker_Commit` の親はまだ marker を持たない。
  - `Record_Main_Commit` が record の bytes を持ち、`Marker_Commit` の祖先である。
- fresh audit が PASS になる条件は「3 ファイルが FINAL」かつ「git_binding」かつ「server anchor の一致」です。
- **試験**:
  - 実 git で FINAL まで進めた tree は PASS する。
  - 次の場合はすべて FAIL する。
    - activity id の不一致
    - 時刻の 1 秒のずれ
    - event の消失
    - 監査 row が別の commit を指している
    - marker が後の commit で書き換えられている
    - git 履歴のない 3 ファイル

### F8-c(Major): gate 結果の provenance を検証していない

- **問題**: Freeze 側は、results branch にあるファイルの中身が整合していることしか確認していませんでした。
- **修正**:
  - aggregate が `run_provenance.json`(run_id, run_attempt, ref_name, sha)を書きます。
  - Freeze 側は次のすべてを要求します。
    - Actions API の `runs/{id}/attempts/{n}` について:
      - path が `.github/workflows/m1macro_gates.yml`
      - head_branch が `m1macro-gates`
      - head_sha が candidate
      - event が push、status が completed、conclusion が success
      - id と attempt が一致する
    - results commit の push が activity 上で一意で、親が一致し、actor が github-actions[bot] である。
  - Freeze record の Gate_Results に Gates_Run(Run_ID, Run_Attempt)を記録します。
  - 拒否コード: GATE_PROVENANCE_MISSING, GATE_RUN_MISMATCH, GATE_RUN_LOOKUP_FAILED, GATE_RESULTS_PUSH_EVENT_*。
- **試験**: 次の 13 通りが、それぞれ正しいコードで拒否されることを確認しました。
  - provenance なし、または中身が空
  - devblind の ref
  - commit の不一致
  - 次の各項目の不一致: head_branch, head_sha, workflow path, conclusion, status, attempt
  - API の障害
  - results の push が見つからない
  - results の push の actor が違う

### F8-d(Minor): snapshot の結び付けがない

- **修正**:
  - G5 と G6–G8 の各 shard が `snapshot_manifest_sha256`(dev snapshot の manifest.json の SHA-256)を記録します。manifest の中の各ファイルの SHA-256 は、`load_dev_snapshot` が読み込み時に検証しています。
  - verdict 側は次を要求します。
    - G5: 64 桁の hex であること。
    - G7: 全 shard の値の集合が `[G5 の値]` と一致すること。
  - Freeze 側は、その値が Freeze 時点の main の manifest と等しいことを要求します(GATE_SNAPSHOT_MISMATCH)。
  - record の Dev_Snapshot には Manifest_SHA256 を追加しました。
- **試験**:
  - 2 種類の snapshot が混在する
  - 別の snapshot
  - G5 に snapshot がない
  - Freeze 側の snapshot が違う、または指定がない

### F8-e(Observation: 要確認、変更なし)

REJECTED になった transaction も、record・marker・audit を main に残します。「1 Version につき Freeze は 1 回」の規則により、その Version ではもう Freeze できません。

例えば、activity API が 180 秒止まっただけでも Version を使い切ります。これは設計どおりの fail-closed で、変更はしていません。この場合の再試行は、新しい Version の識別子を立てる仕様手続きになることを、運用上の前提として確認してください。

### F8-f(Observation: 提案のみ)

`is_final` と fresh audit は、record 内の Gate_Results(Results_Commit, Files_SHA256)を再検証していません。Freeze 時に検証済みなので、今回は変更していません。必要であれば、fresh audit に「Results_Commit の各ファイルの SHA-256 の一致と verdict の再計算」を加えられます。

## 4. 試験と確認

- ローカル(合成データ): 次はすべて ok。
  - test_freeze_record(全経路)
  - test_gate_unique
  - test_freeze_gate
  - test_manifest_gate
  - test_deadline_gate
  - test_forward_commit
- test_forward_run は highspy が必要なので、CI で確認しました。
- dev CI(pinned image、合成データのみ): 次の 2 本とも 25/25 PASS(test_forward_run, test_gate_unique を含む)。
  - run 39169480702(e72e2d8): m1macro-dev-results 259cb59
  - run 39169976687(15bb31d): m1macro-dev-results 9018f34
- manifest: 変更したファイルはすべて CODE_MANIFEST_V1 の対象です(m1macro/*.py、m1macro_gates.yml)。最終 candidate の Code_SHA にはこれらすべてが含まれます。

## 5. 現在の状態

| 項目 | 状態 |
|---|---|
| G5/G6/G7/G8/G9(development blind) | PASS(IMPL-FINDINGS-07) |
| F7-a | ACCEPTED → IMPLEMENTED(e72e2d8)、むすびさんの確認待ち |
| F1(F1-e/F1-d) | CORRECTION CANDIDATE(F8-a〜F8-d)。CLOSE ではない |
| F8-a 残余(activity の保持期間) / F8-e / F8-f | むすびさんの判断待ち |
| candidate readiness | NOT YET |
| candidate Freeze | NOT YET |
| Code_SHA | NOT FROZEN |
| Formal G1–G9 | NOT STARTED |
| Performance Seal | INTACT |
| Holdout | SEALED |
