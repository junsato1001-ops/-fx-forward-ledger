# fx-forward-ledger

為替予測研究プロジェクト(佐藤純・むすび・Claude)の **Formal Forward Ledger(正式フォワード予測台帳)** です。

Freeze済みの基準モデル M0 と S0 が、**締切(08:30 JST)より前に** 出した予測を、改変できない形で毎日記録します。
GitHubのcommit時刻とpush記録が、「結果が出る前に予測していた」ことの第三者的な証拠になります。

## 記録しているもの

| 項目 | 内容 |
|---|---|
| 通貨ペア | USDJPY / CHFJPY / INRJPY(ECB参照レートから作るクロスレート) |
| モデル | `M0-RW0`(M0仕様 v1.2)、`S0-EMPCLIM-STD-EXP-V1`(S0参照実装 v1.1)、`M1-VOL-SHRINK-V1`(Shadow / Pipeline Pilot、親S0、仕様 `preregistration/M1-VOL-SHRINK-V1.md`) |
| ホライズン | 1D(TARGET営業日ごと)、1W・4W(毎週日曜) |
| 締切 | 各起点日の 08:30 JST。使える情報は直前のTARGET営業日のECB公表値まで |
| 最初の正式起点 | 1W・4W: 2026-10-18(日)、1D: 2026-10-19(月)(`forward/config.json`) |
| データ源 | https://www.ecb.europa.eu/stats/eurofxref/eurofxref-hist.zip(毎回SHA-256を記録) |

## ファイル

- `ledger/forecasts.csv` … 予測(またはABSTAIN_SYSTEMの記録)。1行 = モデル × ペア × 起点 × ホライズン
- `ledger/outcomes.csv` … 実現値。`OBSERVED` または `UNAVAILABLE`。行がないものは `PENDING`(Target_Endのfixがまだ公表されていない)
- `ledger/runs.csv` … 実行ログ(データのSHA-256、最終日、件数、状態)
- `data/ecb/` … 取得したECBファイル(CSV)と、取得ごとのSHA-256(`snapshots.csv`)
- `frozen/` … Freeze済みモジュール(変更禁止。SHA-256を毎回照合)
- `forward/` … フォワード運用のコード(`issue.py` 発行、`verify.py` 保存確認、`ledger_builder.py` 台帳生成)
- `tests/test_reproduce_frozen.py` … 毎回の実行前に、Freeze済みの出力をバイト単位で再現できることを確認するゲート

## 運用ルール

1. **追記のみ**。既存の行は書き換えも削除もしない(コードが追記前後のバイトを照合)。
2. **締切を過ぎた起点には予測を出さない**。締切までに出せなかった起点は `ABSTAIN_SYSTEM`(理由: `NOT_ISSUED` / `DATA_UNAVAILABLE` / `LATE_ISSUE`)として残す。
3. **予測に使うデータは Last_Available_Fix までに切り詰める**(未来データの混入防止)。
4. **Storage Verification Gate**: push後にリモートから読み直し、この実行で書いた全行が全項目一致した場合だけ SUCCESS。それ以外はワークフローが失敗(赤)になる。
5. 結果の取得に失敗しても、正常に出した予測は `FORECAST` のまま(`Outcome_Status` だけが `UNAVAILABLE` になる)。
6. 封印中のホールドアウト `RFX-HOLDOUT-A-V1`(GBPJPY・AUDJPY・CADJPY・SGDJPY・KRWJPY)は、このリポジトリでは一切計算しない。ECBの生ファイルには含まれるが、列を読まない。

## 実行スケジュール(GitHub Actions)

JST 00:40 / 02:40 / 04:40 / 06:40 / 07:55 に発行を試み、09:15 に締切後の整理(未発行の記録と結果の取得)を行います。
手動実行(`workflow_dispatch`)は既定で `dryrun` になり、`ledger_dryrun/` にだけ書きます。

## Freeze済みモジュールのSHA-256

| ファイル | SHA-256 |
|---|---|
| m0_walkforward_v1_2.py | 4ca2f37ab729d08f24f008d75c5ceb95f11d79d5bf9575941f44ffd32a77e3d5 |
| origin_target_map_v1.py | 902f0b43a84a0ec309a6e99b6617ca2816e240054bd77e9dbf7d3b2812f3c988 |
| s0_empclim_std_exp_v1_1.py | 84c317661e6798b906063a50fc416c9d594708ffcfbb6010a5bd83f636487676 |
| formal_forecast_ledger_v1.py | b6ffcf34fe6fc605c5a7d7f4953831778bdb9ff45effdf4f3d04535886b16d77 |

再現ゲートの期待値: ECB snapshot `f36e0aff…`(2026-10-09まで)→ 台帳 `e4edb850…` → S0出力 `98e94866…`

## 注意

このリポジトリは研究用の予測記録です。投資判断の推奨ではありません。
ECB参照レートの出典: European Central Bank, Euro foreign exchange reference rates.
