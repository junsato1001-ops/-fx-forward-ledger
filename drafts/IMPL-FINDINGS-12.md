# IMPL-FINDINGS-12 — candidate-2 の組み立て(F11-a 修正)と readiness

- 作成: Claude, 2026-10-19 (JST)
- **candidate-2 commit: `bdf1bfe9a089240083670eb5315dab892794275a`**(branch m1macro-dev)
- **Code_SHA256(CODE_MANIFEST_V1、78 entries): `d3c77ebabcb510462373525281bb8adb321ff5035a030bf89307521980a677d4`**(candidate。まだ Freeze していない)
- dev CI: run 39228791748(m1macro-dev-results b99a62f)、**27/27 PASS**(新規の test_activity_kind を含む)
- readiness の機械確認: `tools/m1macro_candidate/readiness.py`、**24/24 PASS**
- 状態: Performance Seal INTACT / Holdout SEALED / Code_SHA NOT FROZEN / Formal G1–G9(candidate-2)NOT STARTED。実データと sealed 出力は見ていない

## 0. 結論

むすびさんの判断(案 A)に従い、F11-a の修正を入れた candidate-2 を組み立てた。むすびさんが必須とした、実際の GitHub の記録を使った positive / negative の fixture を固定し、すべて期待どおりの結果になった。

candidate-1 との違いは次の 3 点だけ。統計仕様、solver、criterion、snapshot、first_forward_origin の日付、Freeze 窓は変えていない。

- F11-a の修正
- 必須の fixture
- config_version

candidate-1 の Formal PASS(run 39196332834)は、candidate-2 に**継承しない**。正式な履歴としては「PASS, but superseded before Freeze by F11-a implementation correction」のまま残す。

candidate-2 の readiness の最終判定をお願いしたい。PASS であれば、candidate-2 をそのまま m1macro-gates に結び、Formal G1–G9 を最初からすべて実行する。

## 1. candidate-1 からの変更(すべて)

| commit | 内容 |
|---|---|
| fb5e415 | **F11-a**: 結果 commit の activity type を git の topology から一意に決める。**親なし(root)なら `branch_creation` かつ `before = 0×40`、親ありなら `push` かつ `before = 親`**。どちらの場合も `after = Results_Commit`。「branch_creation か push のどちらか」を許す形にはしていない。API への問い合わせも `activity_type=<決めた kind>` にした。Actions run provenance、actor の補助確認、ref、server timestamp、candidate との結び付きはそのまま |
| bdf1bfe | 必須の fixture(test_activity_kind.py、dev_suite に登録)、config_version を `M1-MACRO-IMPL-CODE-V1-candidate-2` に、readiness の確認項目を追加(fb5e415 と 6f9e09d が祖先にあること、F11-a の規則がコードにあること) |

`git diff 6f9e09d bdf1bfe` で変わるファイル: m1macro/freeze_record.py、test_freeze_record.py、test_freeze_audit.py、test_activity_kind.py(新規)、dev_suite.py、config(config_version だけ)、tools/m1macro_candidate/readiness.py(manifest の対象外)。

## 2. 必須の fixture(実際の GitHub の記録を使う)

使った記録はこの repository で実際に作られたもので、内容はそのまま。

- **branch_creation 46968308924**: m1macro-gates-results の root commit 234accb8…。Formal run 39196332834 の結果。before は 0。
- **push 46955708825**: m1macro-dev-results の commit 8d46f84f…。親は 1b67dfef…。

### 2.1 単体の試験(本番の find_push に実際の記録を渡す)

| ケース | 期待 | 結果 |
|---|---|---|
| root の commit を branch_creation として照合 | PASS | PASS |
| 親ありの commit を push として照合 | PASS | PASS |
| root の記録を push と偽る | FAIL | PUSH_EVENT_NOT_FOUND |
| 親ありの記録を branch_creation と偽る | FAIL | PUSH_EVENT_NOT_FOUND |
| root で before が 0 でない | FAIL | PUSH_EVENT_PARENT_MISMATCH |
| 親ありで before が違う | FAIL | PUSH_EVENT_PARENT_MISMATCH |
| after が違う | FAIL | PUSH_EVENT_NOT_FOUND |
| ref が違う | FAIL | PUSH_EVENT_NOT_FOUND |
| actor が違う | FAIL | PUSH_EVENT_ACTOR_MISMATCH |
| 同じ after の記録が 2 件ある | FAIL | PUSH_EVENT_NOT_UNIQUE |
| kind が push と branch_creation のどちらでもない | FAIL | PUSH_EVENT_KIND_INVALID |

### 2.2 end to end(一時的な repository で本番の gate_results を通す)

| ケース | 期待 | 結果 |
|---|---|---|
| root の結果 commit に、branch_creation の記録 | PASS(Results_Push = 46968308924) | PASS |
| root の結果 commit に、push の記録しかない | FAIL | GATE_RESULTS_PUSH_EVENT_NOT_FOUND |
| root で before が 0 でない / after が違う / ref が違う | FAIL | PARENT_MISMATCH / NOT_FOUND / NOT_FOUND |
| 親ありの結果 commit(3 commit 目)に、push の記録 | PASS(Results_Push = 46955708825) | PASS |
| 親ありの結果 commit に、branch_creation の記録しかない | FAIL | GATE_RESULTS_PUSH_EVENT_NOT_FOUND |
| 親ありで before が違う / after が違う / ref が違う | FAIL | PARENT_MISMATCH / NOT_FOUND / NOT_FOUND |
| 親ありで push と branch_creation の両方の記録がある | push だけが使われる | PASS(46955708825) |

IMPL-FINDINGS-11 では、修正案のコードで candidate-1 の実際の Formal 結果を読み取り専用で照合し、run と結果 push の両方が VERIFIED になった。この結果は今回も変わらない(F11-a の修正は fb5e415 のまま)。

### 2.3 candidate-2 の Formal で実際に起きること

m1macro-gates-results にはすでに candidate-1 の commit 234accb があるので、candidate-2 の結果 commit は**親あり → push** の経路で照合される。root の経路(branch_creation)は、candidate-1 の実際の記録で確認済み。

## 3. readiness(24 項目、すべて PASS)

IMPL-FINDINGS-10 の 23 項目に `f11a_kind_from_topology` を加えた。主な値は次のとおり。

| 項目 | 値 |
|---|---|
| 祖先にある修正 | 83f5025、9cfd825、5abe8aa、5045178、f2aa130、e72e2d8、15bb31d、4f21436、6f9e09d、fb5e415 |
| solver と基準 | 凍結値のまま(EPS_TIE 1e−13、LP_TOL 1e−10、STAGE1/2 3000/100、REFINE 1e−14、UB 2e−13、β 1e−6、μ 1e−4) |
| 40 分割、14 日の窓、12 × 15 秒、INCOMPLETE/REJECTED の終端 | PASS |
| manifest | D10 gate PASS、78 entries(test_activity_kind.py が加わった) |
| first_forward_origin | 1D 2026-10-22、1W/4W 2026-10-25(変更なし) |
| Freeze 窓 | **2026-10-20T12:00Z 以上(10/20 21:00 JST)、2026-10-21T12:00Z 未満(10/21 21:00 JST)**(変更なし) |
| frozen_specs の hash | main の freeze.json と .md の両方と一致 |
| snapshot | main 8ed83c2 の 1 commit だけ。manifest は 310e8475…2769 |
| dev / debug の経路 | なし |

現在時刻での D2_PRE_FREEZE が `pass: false` になっているのは、窓の前だからで正常。`pre_freeze_gate_passable_in_window = true` は「窓の中では gate が成り立つことを確かめた」という意味で、「今 Freeze できる」という意味ではない。

## 4. この後の流れ

1. むすびさんが candidate-2 の readiness を判定する。
2. PASS なら、commit bdf1bfe を一切変えずに branch m1macro-gates に push する。fast-forward になり、candidate-1 の commit 6f9e09d は履歴に残る。Formal G1–G9 を最初からすべて実行する(約 2 時間)。
3. allow-list だけを使った監査(IMPL-FINDINGS-13)をする。
4. むすびさんが Formal の結果を監査する。
5. Freeze の許可が出たら、窓の中で Freeze transaction を実行する。
6. 10/21 21:00 JST より前に、main へ取り込む。

窓に間に合わない場合は、境界を緩めずに candidate-2 を断念する。日付を後ろへずらした新しい candidate を作り、G1 からやり直す。

## 5. 現在の状態

| 項目 | 状態 |
|---|---|
| candidate-1 Formal | PASS / SUPERSEDED FOR FREEZE(F11-a) |
| candidate-1 Freeze | NOT AUTHORIZED |
| F11-a | 修正済み(fb5e415)と fixture 固定済み(bdf1bfe)。むすびさんの監査待ち |
| candidate-2 assembly | DONE(bdf1bfe / d3c77eba…77d4) |
| candidate-2 readiness | 24/24 PASS。最終判定はむすびさん |
| Formal G1–G9(candidate-2) | NOT STARTED |
| candidate Freeze | NOT YET |
| Code_SHA | NOT FROZEN |
| Performance Seal | INTACT |
| Historical Reserve Holdout | SEALED |
