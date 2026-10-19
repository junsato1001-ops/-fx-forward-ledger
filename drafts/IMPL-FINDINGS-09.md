# IMPL-FINDINGS-09: F8-a〜F8-f 確定実装と14日 server 再検証ルール、F8-e 不可逆ルール

- 作成: Claude、2026-10-19 (JST)
- 対象: M1-MACRO-V1 implementation candidate(未 Freeze)。branch m1macro-dev
  - F8-a〜F8-d: commit 15bb31dec4ed5e1ec552d0c4c4cd95520769fbd2(IMPL-FINDINGS-08 で CORRECTION APPROVED)
  - F8-f、14日ルール、F8-e: commit **4f214364a120a0418881e654dd76ebb206699cc4**
- dev CI: run 39185130883、m1macro-dev-results 1b67dfe。**26/26 PASS**(新規 test_freeze_audit を含む)
- 状態: Performance Seal INTACT、Holdout SEALED、Code_SHA NOT FROZEN、Formal G1–G9 NOT STARTED。実データと sealed 出力には触れていない(合成データとコードのみ)

## 0. 結論

むすびさんの判断(IMPL-FINDINGS-08 への回答)で求められた次の5点を実装しました。

1. F8-a〜F8-d を確定版として実装した。
2. F8-f を実装した。
3. 14日の server 再検証ルール(SERVER_REVERIFY_WINDOW)を実装した。
4. F8-e の不可逆ルール(REJECTED になった Version は使い切り)を実装した。
5. actor の一致は補助条件として扱い、証明の本体は Actions run provenance とした。

negative test はすべて意図どおりに FAIL または REFUSED になることを確認しました。solver、criterion、反復上限、入力値は変更していません。

**F1 は CLOSE 可能な状態(CLOSE CANDIDATE)にあると判断します。** CLOSE の判定はむすびさんにお願いします。candidate Freeze と Formal G1–G9 には進んでいません。

§4 に、むすびさんの判断の前提について事実の訂正が1点あります。設計の結論は変わりません。

## 1. 実装の内容

### 1.1 F8-f: fresh audit で gate の証拠鎖を再検証する

fresh audit は、record の `Gate_Results.Results_Commit` の時点の結果を再検証します。branch の tip ではありません。モデルは再実行せず、Freeze の根拠になった証拠鎖をたどり直すだけです。

| 再検証項目 | 方法 |
|---|---|
| Results_Commit が results branch 上に残っている | `merge-base --is-ancestor Results_Commit tip`。branch が書き換えられていれば GATE_RESULTS_COMMIT_NOT_ON_BRANCH |
| run provenance と workflow の同一性 | `run_provenance.json` を Actions API の `runs/{id}/attempts/{n}` と照合する。照合項目は path `.github/workflows/m1macro_gates.yml`、branch `m1macro-gates`、head_sha = candidate、push、completed/success |
| candidate commit と Code_SHA256 | 結果側の `source_commit.txt` と `code_sha256.txt` が、record の Candidate_Commit・Code_SHA256 と一致する |
| FORMAL run class | `run_class.txt == FORMAL` |
| snapshot binding | g5 の `snapshot_manifest_sha256` が record の `Dev_Snapshot.Manifest_SHA256` と一致する。全 shard が同じ値であることは verdict 側で確認する |
| raw gate results から verdict を再計算し一致する | suite、g5、g678、exits から verdict を再計算し、保存済みの `gates_verdict.json` と完全一致すること |
| G1〜G9 all PASS | 再計算した verdict の all_pass |
| ファイルの同一性 | 結果ファイル全部の SHA-256、Gates_Run、Results_Push(id と時刻)が record と一致する |
| 監査に使うコード = candidate | 監査するコードの Code_SHA256 が record と一致すること。verdict の再計算に candidate 自身の gate_verdict を使うため |

Freeze 時の `gate_results` と fresh audit は、同じ関数を使います(`results_commit` と `server_required` だけが違う)。そのため、2つの経路で検査が食い違うことはありません。

### 1.2 SERVER_REVERIFY_WINDOW = 14日

- `SERVER_REVERIFY_WINDOW = timedelta(days=14)`。起点は Marker_Push_At_Server_UTC です。現在時刻には GitHub の server 時刻(API 応答の Date ヘッダ)を使います。
- **WINDOW**(push から14日以内。14日ちょうども含む): server の記録(marker push、gates run、results push)をすべて再取得し、すべて一致する必要があります。1つでも取得できなければ fresh audit は FAIL です。
- **server 時刻が取得できない場合**も WINDOW として扱います。厳しい側に倒しています。
- **LONG_TERM**(14日を超えた後):
  - server の記録が取得できない(NOT_FOUND、API 障害)場合は許容し、Freeze 時の監査 row と F8-b の git binding を長期証拠とします。
  - 取得できた記録が一致しない場合は、どのモードでも FAIL です。不一致には、時刻・id・parent・actor・run の各項目のずれと、一意でないことを含みます。
  - git binding、write-once、gate 証拠の file 部分は、どのモードでも必須です。

### 1.3 F8-e: REJECTED は使い切り(不可逆)

- `freeze_state()` は main 上の3ファイルを NONE / FINAL / REJECTED / INCOMPLETE に分類します。transaction を開始できるのは **NONE だけ**です。拒否コードは次のとおりです。
  - REJECTED → `VERSION_CONSUMED_REJECTED`
  - FINAL → `FREEZE_ALREADY_FINAL`
  - INCOMPLETE → `VERSION_INCOMPLETE_PRIOR_TRANSACTION`
- REJECTED の行が1つでもあれば、その後に何を追記しても状態は REJECTED のままで、復活しません。
- **write-once**: record、marker、audit はそれぞれ main の履歴の中で**ちょうど1つの commit** で書かれ、その後は一度も触れられていないことを要求します。
  - それぞれの commit は Record_Main_Commit、Marker_Commit、Marker_Commit の子孫でなければなりません。
  - REJECTED の行を後の commit で FINAL に書き換えた場合、内容だけ見れば3ファイル検査を通ります。しかし write-once が FAIL になるので、fresh audit は FAIL します(test で確認済み)。
- 「API の呼び出しが1回失敗した」だけでは Version は消費されません。固定の再試行枠(15秒 × 12回)の中は同じ transaction の続きです。この枠を使い切り、REJECTED の監査 row が commit された時点で Version が消費されます。

### 1.4 actor の扱い

`actor == github-actions[bot]` は補助条件で、これだけを workflow 実行の証明とはしません。docstring にもそう明記しました。

- gate 結果の証明は、Actions run provenance で結びつけています(F8-c)。
- marker 側の証明は、同じ run の `run_started_at` と head_sha の照合、および push の after と before の一致で結びつけています。

## 2. negative test

test_freeze_audit.py は新規で、dev_suite に登録しました。実 git repo と合成の gate 結果、偽の GitHub API を使い、ネットワークにはつながずに実行します。

| ケース | 期待 | 結果 |
|---|---|---|
| WINDOW で全項目を検証済み | PASS | PASS |
| WINDOW の境界(ちょうど14日)で marker が見つからない | FAIL | FAIL |
| WINDOW で marker が見つからない / API 障害 / 時刻が1秒ずれる | FAIL | FAIL(3通り) |
| WINDOW で gates run を参照できない / results push が見つからない / results push の id が違う | FAIL | FAIL(3通り) |
| server 時刻が取得できず、marker が見つからない | FAIL(WINDOW 扱い) | FAIL |
| LONG_TERM で server 記録がすべて取得できない | PASS | PASS |
| LONG_TERM で全項目を検証済み | PASS | PASS |
| LONG_TERM で marker の時刻のずれ / parent の不一致 / 一意でない | FAIL | FAIL(3通り) |
| LONG_TERM で run の head_sha の不一致 / conclusion が failure | FAIL | FAIL(2通り) |
| LONG_TERM で results push の actor の不一致 / id の不一致 | FAIL | FAIL(2通り) |
| 監査に使うコードが candidate でない | FAIL | FAIL |
| results branch が書き換えられた → 元に戻した | FAIL → PASS | FAIL → PASS |
| audit file を後の commit で変更した(行の内容は同じ) → 元に戻した | FAIL → PASS | FAIL → PASS |
| REJECTED の Version で transaction をやり直す | REFUSED | VERSION_CONSUMED_REJECTED |
| REJECTED の行を FINAL 風の行に書き換えて commit した | FAIL | FAIL(三ファイル検査は通るが write_once で落ちる) |
| unit: 14日の境界(含む)/ 14日+1秒 / 時刻不明 | WINDOW / LONG_TERM / WINDOW | 一致 |
| unit: freeze_state の6通り(REJECTED の後に FINAL を追記しても REJECTED のまま) | | 一致 |

既存の test(test_freeze_record、test_gate_unique、test_forward_commit、test_freeze_gate、test_deadline_gate、test_manifest_gate)も、この変更に合わせて更新したうえで PASS しています。dev CI では 26 test がすべて PASS しました。

## 3. CODE_MANIFEST の対象

変更したファイルは m1macro/freeze_record.py、test_freeze_record.py、test_freeze_audit.py、dev_suite.py です。すべて CODE_MANIFEST_V1 の対象で、最終 candidate の Code_SHA に含まれます。

## 4. 事実の訂正: 保持期間の根拠(設計の結論は変わらない)

むすびさんが根拠に挙げた GitHub の告知(2024-11-08)を原文で確認しました。90日から30日への短縮(2025-01-30 から適用)の対象は、**Events API**(`/repos/{owner}/{repo}/events` など)、Atom feed、`/timeline`、`/dashboard-feed` です。

この実装が使っているのは **`/repos/{owner}/{repo}/activity`(List repository activities)** で、告知の対象一覧には入っていません。このため「activity API の保持期間は30日」という前提は確認できておらず、保持期間は依然として公開文書では不明です。

ただし、14日の窓という結論は変わりません。

- 30日より短いので、もし30日が当てはまっても余裕があります。
- 保持期間が不明でも、窓を過ぎた後に記録が消えて「誤って FAIL になる」ことはありません。窓を過ぎれば LONG_TERM に移るためです。

確定した仕様として残す場合は、根拠の文言を「Events API の30日を保守的な参照値とする。activity API の保持期間は公開文書なし」としておくことを提案します。

## 5. 確認事項(1点)

**INCOMPLETE の扱い**: 前の transaction が audit row の commit より前で止まった場合が該当します。例えば record の push までは済んだが、marker の push が5回とも失敗したケースです。この状態は Version を消費します。理由は次の2つです。

- その Version で FINAL に到達する経路がない。
- 再試行を認めると、REJECTED と同じ理由で状態遷移が複雑になる。

むすびさんの規則は「正式に REJECTED が commit された時点で消費」でした。この INCOMPLETE の状態も同じく消費として扱ってよいか、確認をお願いします。

- 現在の実装は消費として扱っています(fail closed)。
- 消費しない扱いにするなら、仕様の変更になります。

## 6. 現在の状態

| 項目 | 状態 |
|---|---|
| F7-a | PASS / CLOSED |
| F8-a〜F8-d | IMPLEMENTED(15bb31d)。むすびさんの再監査待ち |
| F8-e(不可逆ルール) | IMPLEMENTED(4f21436) |
| F8-f | IMPLEMENTED(4f21436) |
| 14日 server 再検証ルール | IMPLEMENTED(4f21436) |
| F1 | **CLOSE CANDIDATE**(判定はむすびさん) |
| development blind G5〜G9 | PASS |
| candidate readiness | NOT YET(F1 CLOSE の後に判定) |
| candidate Freeze | NOT YET |
| Code_SHA | NOT FROZEN |
| Formal G1〜G9 | NOT STARTED |
| Performance Seal | INTACT |
| Holdout | SEALED |
