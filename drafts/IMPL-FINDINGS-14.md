# IMPL-FINDINGS-14 — M1-MACRO-V1 Implementation Freeze(candidate-2)の実行結果

- 作成: Claude, 2026-10-20 (JST)
- 対象: **candidate-2**
  - commit `bdf1bfe9a089240083670eb5315dab892794275a`
  - Code_SHA256 `d3c77ebabcb510462373525281bb8adb321ff5035a030bf89307521980a677d4`
- 許可: むすびさん 2026-10-20 18:14 JST(IMPL-FINDINGS-13 = PASS、Freeze transaction = AUTHORIZED)
- 状態: Performance Seal INTACT / Historical Reserve Holdout SEALED。sealed の数値出力は開いていない。封印を開ける記録(Part 4 §6.1 の 3)はまだ書いていない。

## 0. 結論

**Freeze transaction は FINAL。** 次の 3 点を確認したので、Freeze は成立したと扱う。

- server 側の marker push の時刻が D2 を満たしている(下限 A_prev ≤ push < 上限 A_first、すべての h で)。
- 期限内(10/21 21:00 JST 未満)に candidate を main に取り込んだ。取り込みは追加のみで、取り込み後の Code_SHA は凍結値のまま。
- 取り込み直後に fresh audit を 1 回実行し、PASS(WINDOW mode、全項目)だった。

手作業で記録を直したり、判定を迂回したりは一切していない。Implementation Freeze の最終判定(CLOSE)は、むすびさんにお願いする。

## 1. 実行の前提(実行直前に確認)

| 項目 | 結果 |
|---|---|
| GitHub server 時刻 | 2026-10-20T12:06:45Z(21:06 JST)。窓 [2026-10-20T12:00Z, 2026-10-21T12:00Z) の中 |
| 手元の HEAD | bdf1bfe…、未 commit の変更なし |
| m1macro-freeze branch | 存在しない |
| main 上の Freeze の 3 ファイル | どれも存在しない(状態 NONE) |

実行前の 18:14〜21:00 JST に、GitHub に書き込まない形でリハーサルをした。

- 構成: ローカルの複製、host 側は numpy なし、Actions と結果 branch の照合は実際の API を読み取り専用で使用。
- 結果: FINAL になった。試験的な取り込みも衝突 0、追加のみ、Code_SHA 一致だった。

## 2. Freeze workflow

| 項目 | 値 |
|---|---|
| 起動 | bdf1bfe を変えずに `refs/heads/m1macro-freeze` へ push |
| run | **39419835148**(`.github/workflows/m1macro_freeze_record.yml`、head_branch m1macro-freeze、head_sha bdf1bfe…、event push、attempt 1、completed/success) |
| run_started_at(server) | 2026-10-20T12:06:59Z |

## 3. main 上の記録(3 ファイル。各ファイルを書いた commit はそれぞれ 1 つだけ)

| 段階 | ファイル | commit | ファイルの SHA-256 |
|---|---|---|---|
| A record | preregistration/M1-MACRO-IMPL-CODE-V1.freeze.json | `6a90d1d55deed97140edf882cc7f1cc15409284d`(親 18ee8a2) | bb18b3f36da000a74f216495cdbe7a6eef5ed8a07c4f25604a3acb48103e2b75 |
| B marker | preregistration/M1-MACRO-IMPL-CODE-V1.freeze_complete.csv | `07bdae9bea8da51db80a77b95928ce9f73eb4731`(親 6a90d1d) | 739a74114ce7f835709719ac7e70834f501e908d4f5ec14238c70a2e3fa09d1d |
| C audit | audit_log/m1_macro_freeze_audit.csv | `93e90b7ed83c0f171c3536113b9198064ca4f298`(親 07bdae9) | 249357e2c0f94330a91f278e2369c7c70ef9352e9b1a2b7a8a1375fd69ba3d35 |

### record の要点

数値の出力は含まれていない。

- Spec M1-MACRO-IMPL-CODE-V1、Code_SHA256 d3c77eba…、Candidate_Commit bdf1bfe…
- First_Forward_Origin: 1D 2026-10-22、1W/4W 2026-10-25。CFTC window 6 h。
- Image_Digest `python@sha256:60d9996b…b50d`
- **Pre_Freeze_Gate**: pass = true、検査時刻 2026-10-20T12:07:19Z
  - A_previous: 1D 2026-10-20T12:00Z、1W/4W 2026-10-17T12:00Z
  - A_first: 1D 2026-10-21T12:00Z、1W/4W 2026-10-24T12:00Z
- **Gate_Results**
  - m1macro-gates-results、Results_Commit f3c2b0ab…、Gates_Run 39291810501/1
  - Results_Push 47044332729(2026-10-19T18:57:00Z)
  - Server_Evidence: run VERIFIED、push VERIFIED
  - 結果ファイル 14 本の SHA-256
- **Dev_Snapshot**: Main_Commit 8ed83c2…、Manifest_SHA256 310e8475…2769、50 ファイル

### marker の行

Run 39419835148/1、Record_SHA256 bb18b3f3…(= record の実際の SHA)、Record_Main_Commit 6a90d1d、Code_SHA256 d3c77eba…、Status COMPLETE、Recorded_At_UTC 2026-10-20T12:07:22Z。

### audit の行

| 欄 | 値 |
|---|---|
| Run_Started_At_Server_UTC | 2026-10-20T12:06:59Z |
| Record_Reread_At_UTC / Recorded_At_UTC | 2026-10-20T12:07:22Z / 2026-10-20T12:07:22Z |
| Marker_Reread_At_UTC | 2026-10-20T12:07:24Z |
| Marker_Commit | 07bdae9bea8da51db80a77b95928ce9f73eb4731 |
| Marker_Push_Activity_ID / **Marker_Push_At_Server_UTC** | 47126707625 / **2026-10-20T12:07:23Z** |
| Anchor_Status | **PASS** |
| A_First_1D / 1W / 4W | 2026-10-21T12:00:00Z / 2026-10-24T12:00:00Z / 2026-10-24T12:00:00Z |
| D2_Status | **PASS** |
| **Freeze_Status** | **FINAL**(Reject_Reason は空) |

## 4. server 側の marker 時刻と D2(独立に確認)

activity API で直接確認した marker の push は 1 件だけで、内容は次のとおり。

```
id 47126707625, activity_type push, ref refs/heads/main, before 6a90d1d… (= record の commit = Marker_Commit の親),
after 07bdae9… (= Marker_Commit), actor github-actions[bot], timestamp 2026-10-20T12:07:23Z
```

| 判定 | 式 | 結果 |
|---|---|---|
| Anchor | run start 12:06:59 ≤ Recorded 12:07:22 ≤ marker push 12:07:23、かつ record reread 12:07:22 ≤ Recorded ≤ marker reread 12:07:24 | 成立 |
| D2(上限) | marker push 2026-10-20T12:07:23Z < A_first(1D) 2026-10-21T12:00Z、< A_first(1W/4W) 2026-10-24T12:00Z | 成立 |
| D2 下限(F10-a、Part 3 §2) | A_prev(1D) 2026-10-20T12:00Z ≤ 12:07:23Z(1W/4W の A_prev は 2026-10-17T12:00Z) | 成立。first(h) は Freeze 後の最初の予定 Origin になっている |
| is_final_tree(candidate-2 のコード、main) | 取り込み前・取り込み後とも | **True** |

## 5. main への取り込み(Part 4 §6.1)

| 項目 | 値 |
|---|---|
| merge commit | **`2e8edaee13d578aecc67df003ded3d720b4fe5e9`**(親 93e90b7 と bdf1bfe、2026-10-20 21:08:50 JST) |
| 期限 | 10/21 21:00 JST 未満。成立 |
| 衝突 | 0 |
| main の既存ファイルの変更 | **0**(追加 81 ファイルのみ) |
| 取り込み後の main の Code_SHA256 | **d3c77eba…77d4**(凍結値と一致) |
| push で起動した workflow | なし(main への push を trigger にする m1macro の workflow はない) |
| 取り込み後に動き出すもの | m1macro_forward.yml の定時実行(毎日 00:40 / 02:40 JST の CFTC snapshot)と、S0 の発行後の issue job。first(h) より前の Origin には M1 の行を作らない(`D_iso >= first`)。最初の M1 の発行は 1D 2026-10-22 |

## 6. fresh audit(取り込み直後に 1 回)

GitHub から main を新しく clone し(HEAD 2e8edae)、その tree にある candidate-2 自身の `freeze_record.fresh_audit` を実行した。server の時刻は GitHub の Date ヘッダの値(2026-10-20T12:09:11Z)を使った。

| 項目 | 結果 |
|---|---|
| mode | **WINDOW**(marker push から 14 日以内。server の記録をすべて取り直し、一致することを要求するモード) |
| three_files_final | true |
| git_binding(F8-b) | true |
| write_once(F8-e) | true |
| auditor_code(監査したコード = candidate、Code_SHA d3c77eba…) | true |
| server_anchor(F8-a。marker push を取り直して id と時刻が一致) | **VERIFIED** |
| gate_evidence(F8-f。Results_Commit で provenance、FORMAL、candidate、snapshot、verdict の再計算、files の SHA、Results_Push) | true。run VERIFIED、push VERIFIED |
| **pass** | **true** |

注記(この作業環境の制約): この環境の proxy は activity API の 2 ページ目以降へのリンク(数値 id 形式の URL)を通さない。そのため fresh audit の adapter は、各 ref の最新 100 件だけを読んだ。

- 照合対象の event(marker 47126707625、結果 47044332729)は、どちらもその中にある。
- どちらの commit もこの Freeze で新しく作ったものなので、古いページに同じ `after` の記録はありえない。
- Freeze workflow の中(GitHub Actions)では、本番のコードが全ページを読んで照合した。

## 7. この後

1. むすびさんによる Implementation Freeze の最終判定(CLOSE)。
2. Part 4 §6.1 の 3「封印を開ける記録」(preregistration/M1-MACRO-V1-SEAL-OPENING.json)は、むすびさんの判断の後に別の commit として書く。それまで Performance Seal は INTACT。
3. 最初の Forward:
   - 1D: Origin 2026-10-22。CFTC の取得は 10/22 00:40 / 02:40 JST、T_info は 03:00 JST、発行の締め切りは 08:30 JST。
   - 1W/4W: Origin 2026-10-25。
   - 必要なら、10/22 の発行を状態だけ確認する。

## 8. 現在の状態

| 項目 | 状態 |
|---|---|
| candidate-2 Formal G1–G9 | PASS |
| **Implementation Freeze transaction** | **FINAL**(run 39419835148、marker push 2026-10-20T12:07:23Z、D2 PASS) |
| main への取り込み | DONE(2e8edae、追加のみ、Code_SHA 一致) |
| fresh audit | PASS(WINDOW) |
| Code_SHA256 | **d3c77eba…77d4(Freeze record に固定)** |
| Implementation Freeze の CLOSE | むすびさんの判定待ち |
| Performance Seal | INTACT |
| Historical Reserve Holdout | SEALED |
