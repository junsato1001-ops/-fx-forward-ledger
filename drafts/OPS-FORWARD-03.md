# OPS-FORWARD-03 — M1-MACRO-V1 の CFTC 年次ファイルの年越し: KNOWN UPCOMING RISK WINDOW(事前登録)

- 作成: Claude, 2026-10-26 22:29 JST(むすびさんの判断 2026-10-26 22:25 JST により事前登録する)
- 種類: Forward の運用記録。**事前登録**(結果を見る前に、予見されるリスクの範囲と、観測で確かめることを固定する)。OPS-FORWARD-01・02 の続き。
- 区分: **V1 OPERATIONAL FINDING / FROZEN-BEHAVIOR LIMITATION**。V1 violation ではない。V1 は凍結済みの仕様どおりに動いている。
- 状態: **EXPECTED_RISK**。2027 年 1 月の各 Origin で実際に起きたことを観測したら、この記録は書き換えずに、別の追記の記録で OBSERVED に切り替える。
- 出どころ: M1-MACRO-PIPELINE-V2 Implementation Spec Part 1 の F-P1-1・F-P1-10(drafts/M1-MACRO-PIPELINE-V2-IMPL-PART1-V0.1.draft.md、V0.2.draft.md)。
- 確認した範囲: V1 の凍結済みのコード(m1macro/forward_run.py、sources.py、cftc_rules.py、uscal.py、frozen/origin_target_map_v1.py)と、開発用 snapshot の CFTC 年次ファイルの **Report_Date の日付だけ**。建玉の値、予測の値(確率、Point、PI)、β、μ、J*、CRPS、成績は読んでいない。
- この記録ではしないこと: V1 の workflow・code・config・data・ledger の変更。

## 1. V1 の凍結済みの挙動(事実)

- V1 の CFTC の T_info より前の取得(`m1macro/forward_run.py` の `cftc_snapshot`)は、取得するファイルの年を、**実行時の JST の年**で決める(`year = now.astimezone(JST).year`、URL は `sources.cftc_year_url(year)` = `https://www.cftc.gov/files/dea/history/fut_fin_txt_<year>.zip`)。
- これは、凍結済みの M1-MACRO-IMPL-PART1-V1.2 §2.3 の「本番では当年のファイル」のとおりである。
- V1 の予定の取得時刻は 00:40 と 02:40 JST で、どちらも Origin の日の JST である。したがって、Origin が 1 月の日なら、V1 は新しい年のファイルを取る。

## 2. 構造から予見されること(過去のデータで確かめた事実と、そこからの予見)

**確かめた事実**(開発用 snapshot の Report_Date の日付と、V1 の `cftc_rules.usable_from` による。時刻の換算は作業環境の system の zoneinfo で行った。V1 の固定版の tzdata 2024.2 ではない)

- CFTC の年次ファイル(2017〜2026)には、その年の日付の Report_Date の報告だけが入っている。
- 2011〜2026 の毎年、1 月 1 日から 6〜15 日間の Origin では、T_info の時点で使える最新の報告は**前年のファイル**にあった。

| 年 | 前年のファイルにあった期間(Origin の日) |
|---|---|
| 2011 | 01-01〜01-08 |
| 2012 | 01-01〜01-07 |
| 2013 | 01-01〜01-12 |
| 2014 | 01-01〜01-11 |
| 2015 | 01-01〜01-10 |
| 2016 | 01-01〜01-09 |
| 2017 | 01-01〜01-07 |
| 2018 | 01-01〜01-06 |
| 2019 | 01-01〜01-15 |
| 2020 | 01-01〜01-11 |
| 2021 | 01-01〜01-09 |
| 2022 | 01-01〜01-08 |
| 2023 | 01-01〜01-07 |
| 2024 | 01-01〜01-06 |
| 2025 | 01-01〜01-14 |
| 2026 | 01-01〜01-10 |

**予見(EXPECTED_RISK。まだ観測していない)**

- 2027 年について、V1 の `cftc_rules.usable_from` で計算すると、Origin 2027-01-01〜01-09 では使える最新の報告は 2026-12-22 または 2026-12-29(2026 年のファイル)、Origin 2027-01-10 以降は 2027-01-05(2027 年のファイル)になる。
- この期間の V1 の正式な Origin(凍結済みの ORIGIN_TARGET_MAP_V1 の `is_formal_origin` による):

| Origin | Horizon | V1 が取るファイル | 使える最新の報告があるファイル |
|---|---|---|---|
| 2027-01-03(日) | 1W、4W | 2027 | 2026 |
| 2027-01-04(月) | 1D | 2027 | 2026 |
| 2027-01-05(火) | 1D | 2027 | 2026 |
| 2027-01-06(水) | 1D | 2027 | 2026 |
| 2027-01-07(木) | 1D | 2027 | 2026 |
| 2027-01-08(金) | 1D | 2027 | 2026 |

- 計 6 つの Origin の日、7 つの (Origin, Horizon)。2027-01-01(金)は TARGET の休日、01-02・01-09 は土曜日で、正式な Origin ではない。
- 予見される経路(どれになるかは観測で確かめる。ここでは決めない):
  - (a) 2027 年のファイルがまだ CFTC にない → 取得の失敗(FETCH_FAILED)
  - (b) ファイルはあるが報告が 0 件 → EMPTY
  - (c) ファイルはあるが、T_info の時点で使える報告がない → V1 の特徴量の規則で NO_USABLE_REPORT など
  - いずれの場合も、その Origin の F_POS は使えず、M1 の行は ABSTAIN_SYSTEM などになると予見される。
- **F14-a との関係**: V1 の定時の取得が窓の中で起動しない問題(F14-a)が続けば、この期間の Origin は年のことと関係なく、使える snapshot がない。この記録のリスクは F14-a とは独立した、別の原因である。観測では、2 つを分けて記録する(起動した取得が窓の中にあったか、取ったファイルの年はどれか)。

## 3. 観測で確かめること(2027 年 1 月)

上の 6 つの Origin の日と、比較のための 2027-01-10(日、1W・4W)について、それぞれ次を記録する。状態を表す列だけを読み、予測の値と成績は読まない。

1. その Origin の窓 (T_info − 6h, T_info] の中に、V1 の CFTC の取得が起動したか(F14-a の観測)。
2. 起動した取得の URL の年、HTTP の結果(成功 / FETCH_FAILED)、Normal と Subreason(fetches の記録)。
3. その Origin の F_POS の状態と理由(OK / ABSTAIN_SYSTEM / MODEL_PREREQ_UNAVAILABLE と subreason)。
4. その Origin の M1 の発行の状態(COMPLETE / ON_TIME と Decision_Class の件数)。

- 観測の結果は、この記録を書き換えずに、別の記録(OPS-FORWARD の次の番号)で EXPECTED_RISK から OBSERVED に切り替える。
- 予見と違う結果になった場合も、そのまま記録する。この記録の予見に合わせて解釈を変えない。

## 4. この記録の位置づけ

- V1 は変更しない。V1 の確認的な評価(104 週)の規則も変えない。この期間の行は、V1 の凍結済みの規則で扱われる。
- V2 では、Source_Year を Target_Origin から決める規則で、この問題を避ける(M1-MACRO-PIPELINE-V2 Implementation Spec Part 1 §8.1)。これは V2 の実装の決定であり、V1 の記録や証拠には遡って適用しない。
