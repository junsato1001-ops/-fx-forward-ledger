# DEV-USDJPY-SIMPLE-01 — Freeze Candidate V0.1 Errata E1(DRAFT)

- 状態: **DRAFT(Claude、2026-10-31)**。むすびさんの確認待ち。**Freeze ではない。**
- 対象: Freeze Candidate V0.1(V1 commit c8b169de)。**V0.1 の 3 ファイルは変更しない。** この errata は、Freeze のときに V0.1 の JSON 案をどう埋めるかの解釈だけを訂正する。
- 発見: Freeze の実行の途中、commit A の前(むすびさん、純さん経由 2026-10-31 04:04 JST)。V1 への書き込みは 0 件(V1 main = c8b169de のまま。Claude が `git ls-remote` で確認)。
- 原因: V0.1 の JSON 案(Claude 作成)の `execution_protocol.authorization_file.freeze_commit` が `<FREEZE_COMMIT>`(freeze.json を加える commit A 自身の SHA)を freeze.json の中に書くことを求めていた。commit の SHA はその tree(freeze.json を含む)から決まるので、自己参照になり、事前に確定できない。**Claude の設計の誤り。**

## E1-1 訂正

freeze.json の `execution_protocol.authorization_file.freeze_commit` の値を次の固定の文字列にする(SHA を書かない):

```
"recorded as Freeze_Commit in the FREEZE event of preregistration/DEV-TRIAL-REGISTRY.csv (and in preregistration/registry.csv); AUTHORIZATION.json freeze_commit must equal that value"
```

- commit A の実際の SHA は、これまでの設計どおり commit B の 2 つの台帳(`DEV-TRIAL-REGISTRY.csv` の FREEZE の event、`registry.csv` の行)にだけ書く。循環はない。
- 後で作る `AUTHORIZATION.json` の `freeze_commit` には、台帳に書かれた commit A の SHA を書く(AUTHORIZATION.json は Freeze の後に作るので循環はない)。

## E1-2 埋める値と埋めない値の区別(全数)

Claude が V0.1 の 3 ファイルの `<...>` をすべて洗い出した結果:

| 場所 | 文字列 | Freeze で |
|---|---|---|
| JSON `approved_by` | `<純's explicit Freeze decision, JST timestamp>`、`<verdict, JST timestamp>` | 埋める(commit A。純さんの決定の時刻、むすびさんの最終監査の判定と時刻) |
| JSON `execution_protocol.authorization_file.freeze_commit` | `<FREEZE_COMMIT>` | **E1-1 の固定の文字列に置き換える(SHA を書かない)** |
| JSON `execution_protocol.result_preservation` | `<mode>`、`<run_id>`、`<name>`、`<sha256>`、`<sha>` | **埋めない**(後の保存の手順の書式。そのまま固定する) |
| JSON `gate` | `< 0.05`(不等号) | 対象外(placeholder ではない) |
| JSON `status_of_this_file` | 項目ごと | 削除する(V0.1 §5 のとおり) |
| CSV FILE 1(DEV-TRIAL-REGISTRY) | `<FREEZE_COMMIT>`、`<FREEZE_COMMIT_TIME_JST>` | 埋める(commit B。commit A の SHA と commit A の時刻) |
| CSV FILE 2(registry.csv) | `<FREEZE_DATE_JST>`、`<FREEZE_COMMIT>`、`<COMMIT_TIME>` | 埋める(commit B。既存の行と同じ形) |

- freeze.json の中に、commit A・commit B の SHA と時刻は 1 つも書かない。

## E1-3 変わらないもの

- Freeze の対象(SPEC v0.3、Freeze-prep v0.1、実装 a7921007 / tree 29d72c50、runtime)、実行の commit の規則、結果の保存の手順、Registry_Count_At_Design の確認、手順(確認 → commit A → commit B)。
- E1 自体は Freeze の記録に参照として書く(freeze.json の `freeze_source_notes` に「Freeze Candidate V0.1 + Errata E1 の SHA-256・blob」)。

## E1-4 状態

- Freeze の実行 = BLOCKED BEFORE COMMIT A(V1 への書き込み 0 件)
- Freeze の再開には、むすびさんの E1 の確認と、純さんの再開の明示の指示が要る
- AUTHORIZATION.json = 未作成、preflight = NOT AUTHORIZED、Development = NOT STARTED、Holdout = SEALED
