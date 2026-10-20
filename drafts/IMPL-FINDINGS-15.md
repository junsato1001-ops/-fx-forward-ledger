# IMPL-FINDINGS-15 — M1-MACRO-V1 の封印を開ける記録(Seal Opening record)

- 作成: Claude, 2026-10-21 (JST)
- 前提: むすびさんの判定(2026-10-21 01:47 JST)
  - IMPL-FINDINGS-14 = PASS
  - Implementation Freeze = PASS / CLOSE
  - Code_SHA256 d3c77eba…77d4 = FROZEN
- 状態: **Performance Seal INTACT**。この記録は、むすびさんの監査が PASS した時点で有効になる。Historical Reserve Holdout は SEALED のままで、この記録とは関係しない。

## 1. 記録

| 項目 | 値 |
|---|---|
| ファイル | `preregistration/M1-MACRO-V1-SEAL-OPENING.json` |
| commit | **`0029187e7ca8d3fc4b56252e43a3881535c958c0`**(main。親は b6edf91 で、Freeze の記録 6a90d1d / 07bdae9 / 93e90b7 と取り込み 2e8edae より後) |
| Git blob | `0c7eba5a81dc2a8ee15c3decc2b6ba3d567ba091` |
| ファイルの SHA-256 | `1095b255ff954fc4d674926469680fe7c04e85603ea5eef82593d941a0bbe6a2` |
| server push(activity API) | id 47156701192、before b6edf91、after 0029187、**2026-10-20T16:48:24Z**(2026-10-21 01:48:24 JST) |
| main の Code_SHA256(push 後) | d3c77eba…77d4(変わらない。preregistration/ は manifest の対象外) |

この commit で加えたのはこのファイル 1 つだけで、ほかのファイルには触れていない。

## 2. 内容(Part 4 §6.1 の 3 が求める 3 項目)

1. **実装の Freeze の commit**: 次の値を記載した。
   - record の commit 6a90d1d(SHA-256 bb18b3f3…)、marker の commit 07bdae9、audit の commit 93e90b7
   - Freeze の run 39419835148、Freeze_Status FINAL、marker push 47126707625(2026-10-20T12:07:23Z)
   - Code_SHA256 d3c77eba…、candidate bdf1bfe…、main への取り込み 2e8edae、First_Forward_Origin
   - fresh audit(blob fdd3c3c4…、WINDOW、pass)
   - むすびさんの CLOSE(IMPL-FINDINGS-14、blob 5372937c…)
2. **§5 の関門の結果への参照**: 次の値を記載した。
   - Formal run 39291810501/1、m1macro-gates-results の commit f3c2b0a、結果の dir = Code_SHA
   - gates_verdict.json の SHA-256 68db717b…fc7d、All_Pass true
   - 監査 IMPL-FINDINGS-13(blob fb70ad2d…)
   - candidate-1 の Formal(39196332834 / 234accb)は「PASS, but superseded before Freeze by F11-a」と明記し、この Freeze の証拠ではないとした。
3. **開ける日時**: 「このファイルを main に加えた commit の GitHub server の push 時刻」と定義した。runner の時計や人が書いた時刻は使わず、activity API で誰でも照合できる。
   - 実際の値は **2026-10-20T16:48:24Z** だった。
   - **効力が生じるのは、むすびさんがこの記録と commit の監査を PASS した時点**とした。それまで Performance Seal は INTACT。

## 3. 開けるもの・開けないもの(記録に明記)

- **開けるもの**: Part 4 §6.2 の開発用の再生だけ。
  - 計算: 凍結したコード(上の Code_SHA256)と one-shot の開発用 snapshot で、過去のすべての (t, h) を計算する。
  - 置き場所: replay/ にだけ書き、全行に Evidence_Class = DEVELOPMENT_REPLAY を付ける。
  - 用途: 記述と診断だけ。
- **開けないもの**:
  - Historical Reserve Holdout(RFX-HOLDOUT-A-V1)。5 つのペアは SEALED のままで、計算もしない。
  - ledger/(Forward)。再生の行は ledger/ に書かない。確認的な評価は、最初の Forward Origin 以降の COMPLETE かつ ON_TIME の行だけを読む(EVAL-SPEC-V1 §5.5)。
- **拘束する規則**:
  - 再生の結果を見て、M1-MACRO-V1 の仕様・コード・config・最初の Forward Origin を変えない(Part 4 §6.2)。
  - 再生から得た考えは、新しい Version(別の Trial)の設計の材料にだけ使う。
  - 開発期間の成績は、確認的な証拠に使わない。

## 4. 確認をお願いしたい点

- 「開ける日時 = この commit の server push 時刻、効力はむすびさんの監査 PASS の時点」という定義でよいか。
  - 監査 PASS の時刻を別に記録すべきであれば、追記だけの別記録として残す(このファイルは書き換えない)。
- PASS をいただいた後も、再生(§6.2)は改めて指示をいただいてから計算する。

## 5. 現在の状態

| 項目 | 状態 |
|---|---|
| M1-MACRO の統計仕様 | FREEZE / PASS |
| M1-MACRO の実装 | FREEZE / PASS / CLOSE |
| Code_SHA256 | d3c77eba…77d4 / FROZEN |
| Forward の最初の Origin | 1D 2026-10-22、1W/4W 2026-10-25 / FIXED |
| Seal Opening record | 作成済み(0029187)。むすびさんの監査待ち |
| Performance Seal | **INTACT** |
| Historical Reserve Holdout | SEALED |
