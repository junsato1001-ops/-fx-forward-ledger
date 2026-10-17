# M1-MACRO Data Availability Matrix v1

- 状態: **v1.1 FROZEN**(2026-10-16 JST)。むすびの再監査(10/16 23:36、CONDITIONAL PASS / FREEZE READY AFTER MINOR REVISION)で求められた3点を修正し、全文の SHA-256 を取り直して Freeze した。以後この表は変更しない(変更する場合は新しい版と理由を残す)。
- 封印の確認: 候補系列の値は一つも取得していない。リターンとの関係、成績、ホールドアウトのペアにも触れていない。公表の仕組みと利用条件だけから作った。
- 版の履歴:
  - v0: 初版
  - v1(draft、SHA-256 706d011b…): T_info の推奨と欠測規則の案を追加
  - v1.1 FINAL CANDIDATE(SHA-256 89d7a690…): 決定事項を反映し、CFTCの公表日の再構築規則と利用条件の確認結果を追加。原油(C5)を除外し、VIX(C3)を利用条件で保留にした
  - v1.1 FROZEN(この版): むすびの3点の修正を反映した。(1) VIX を LICENSE_UNRESOLVED で正式に除外し、代わりの系列に触れた文を削除した。(2) CFTC 2025年は、公式に確定した公表日があればそれを使い、予定しかなければ安全側の上限を使う。(3) TFF の開始日を未確定に戻した。履歴ファイルの Report Date を公表日として扱わないことを明記し、確認を実装前の Gate にした

## 0. 決定事項(むすび 2026-10-16 23:26 で ACCEPT)

| 項目 | 決定 |
|---|---|
| T_info | **Origin D の 03:00:00 JST**(Freeze候補)。03:00 より後に公表された情報は、07:55 の実行で取得できてもその Origin では使わない |
| as-of 結合 | Publication_Timestamp ≤ T_info |
| 日次系列の staleness | **その系列自身の公表営業日カレンダー**で数える(土日・祝日は数えない)。通常の日程で期待される値の日付から、**さらに 2 source-business-days** を超えて新しい値がない場合は STALE → MODEL_PREREQ_UNAVAILABLE(2日は Freeze候補) |
| CFTC | 日数ではなく、公式の公表日程と特別告知に従う |
| 本番での取得失敗 | T_info 時点で本来取得できる最新値を取得できなかった場合は **ABSTAIN_SYSTEM**。古い値への暗黙の代用はしない |
| 構造的な欠測 | MODEL_PREREQ_UNAVAILABLE |
| 原油 C5 | M1-MACRO V1 から除外。Reason_Code = **DATA_FEASIBILITY_FAIL_POINT_IN_TIME**(成績を見て外したのではない。将来、別の Version / Trial で入手可能性を確定できれば戻せる) |
| VIX の 2003年の算出方法変更 | 入手可能性の問題ではなく、Transformation Spec で扱う予定だった。VIX が V1 から除外されたため、V1 では扱わない(VIX を戻す将来の版で決める) |
| 残りの確認事項 | 特徴量の設計より先に片付ける(この版で実施) |

## 1. 定義

- **Origin D**: 予測の起点日(JST)。締切は D の 08:30 JST。
- **T_info**: D の 03:00 JST。
- **公表時刻が日ごとに記録されていない系列**: 「通常の公表時刻 + 安全マージン」から決まる **値の日付の規則**(value-date rule)で代える。その規則で、過去のどの日でも T_info までに公表済みだったと言えることを根拠とともに示す。
- **公表日が一部しか記録されていない系列**(CFTC): 公表時刻の **上限**(実際の公表はこれより遅くない、と一次資料で言える時刻)で結合する。実際より遅い時刻で結合しても情報が減るだけで、未来の情報は混ざらない。実際より早い時刻で結合することは禁止。

## 2. Matrix

| # | 系列 | 公表の仕組み(一次資料) | 値の日付 / 公表時刻の規則 | 改訂・断層 | 判定 |
|---|---|---|---|---|---|
| C1/C2 | 米国債の名目利回り(Daily Treasury Par Yield Curve) | 入力は各営業日 15:30 ET頃の気配。掲載は「通常 18:00 ET まで」、遅れることがある | 期待する値の日付 = **D−1(暦日)より前の、米国の最後の公表営業日**。掲載から T_info まで 22時間以上の余裕がある | 公表値の遡及修正の記載はない(Treasury は曲線を変更し得る、としている)。算出方法の変更 2021-12-06、20年債の再導入 2020-05-20 | **USABLE_WITH_LAG** |
| C6 | 米国の実質利回り(Daily Treasury Par Real Yield Curve) | C1 と同じ | C1 と同じ | 2021-12 の算出方法変更の影響あり。2003年から | **USABLE_WITH_LAG** |
| C1/C2 | 日本国債の利回り(財務省 国債金利情報) | 入力は日本証券業協会の公社債店頭売買参考統計値(**当日 15:00 時点**の売り気配と買い気配の仲値。指定協会員が報告)。3次スプラインで補間。掲載は翌営業日 9:30頃(現行)、2010年の開始時は 11:00頃 | 期待する値の日付 = **D より前の日本の最後の営業日の、さらに前の営業日** | 訂正の扱いは記載がない。本番では取得ごとの snapshot を保存して、過去の値が後から変わっていないかを毎回照合する | **USABLE_WITH_LAG** |
| C3 | VIX(終値) | Cboe の履歴CSVは「Updated Daily」(更新の時刻は記載なし)。1990年から | C1 と同じ規則 | 2003年の算出方法変更(V1 では除外のため扱わない) | **除外**(LICENSE_UNRESOLVED、§4。入手可能性は USABLE_WITH_LAG で問題なかった) |
| C4 | CFTC 建玉明細(日本円) | 通常は火曜時点のデータを **金曜 15:30 ET** に公表。CFTC は **過去の公表日の一覧を提供しておらず、確認できるのは直近13か月分だけ**。公表後の過去データは改訂しない(COT ページの FAQ) | §3 の再構築規則で求めた公表時刻の上限 ≤ T_info | 改訂なし | **USABLE_WITH_EVENT_DATE_RECONSTRUCTION**(§3 の Gate を通ることが条件) |
| C5 | 原油(WTI) | 一次資料で公表時刻と遅れを確定できなかった | — | — | **除外**(DATA_FEASIBILITY_FAIL_POINT_IN_TIME) |
| C7 | 日銀・FOMC の会合日程 | 日銀は日程変更を個別に公表している(例: 2020-03-16 付で、3月の会合を 18・19日から 16日に前倒し、同日に開催) | 告知は **公表日の翌日の T_info から**使う(公表日に告知された変更は、時刻が分からないので当日の Origin では使わない) | 臨時会合・前倒しは当日の告知があり得る | **USABLE_WITH_EVENT_DATE_RECONSTRUCTION**(過去の告知の一覧を作ることが条件) |
| — | 為替介入の実績(財務省) | 事後に公表 | 特徴量には使わない | — | 特徴量から除外 |

## 3. CFTC の公表時刻の再構築規則(案)

CFTC が過去の公表日の完全な一覧を出していないため、次の順で **公表時刻の上限** を決める。

1. **特別告知で公表日が明示されている週**: その日の 15:30 ET。
   - **2025年の政府閉鎖**: 公表日の表がある(Historical Special Announcements、2025-12-09 付)。9/30 の報告は 11/19(水)に公表され、12/23 の報告(12/29 公表)で通常の日程に戻ったとされる。
     - 優先順位: **公式に実際の公表日が確認できる報告はその日を使う**。予定(tentative / anticipated)しか残っていない報告だけ、予定日の翌営業日を上限とする(安全側)。
     - 「確認できる」の基準: その公表日の当日以降の日付を持つ CFTC の公式資料が、公表が済んだことを示していること。2025-12-09 付の告知では、12/09 までの日付は告知の時点で過去なので確認済みとして扱う。12/10〜12/29 の日付は、同じ告知の中では予定にあたる。そのため、実装前の Gate で後日の公式資料による確認を探し、見つからなければ予定日の翌営業日を上限にする。
   - 2025-01: Carter 元大統領の国葬のため、その週の報告は月曜 1/13 に公表。
   - 2018-12-05: Bush 元大統領の国葬で政府が閉庁。
2. **政府閉鎖で、公表日の一部しか分からない期間**: 期間中に溜まった報告は、すべて **「通常の日程に戻った」と告知された最初の公表日** の 15:30 ET で使えるものとする。
   - **2013年**: 10/1 の報告(本来 10/4 公表)は 10/25 に公表。以後は「10/28 の週に2本、11/4 の週に少なくとも2本」とされ、**11/8 の公表で通常の日程に戻る見込み**とされた(CFTC Release 6745-13)。→ 溜まった報告はすべて 2013-11-08 15:30 ET から使う。
   - **2018〜2019年**: 最後の公表は 2018-12-21。12/24 の報告は 2019-02-01 に公表され、その後は毎週火曜と金曜に1本ずつ(CFTC Release 7864-19)。通常の日程に戻った日付は公式資料では未確認(二次資料では 2019-03-08)。→ **Gate**: 公式資料で通常の日程に戻った日付を確定できない場合は、2018-12-24〜2019-03-05 の報告を特徴量に使わず、該当する Origin は MODEL_PREREQ_UNAVAILABLE にする。
   - **それより前の政府閉鎖**(1995〜96年など): CFTC の告知ページに記録がない。→ 閉鎖期間の開始から、閉鎖が終わった後の最初の金曜の4週間後までの報告は使わない(MODEL_PREREQ_UNAVAILABLE)。
3. **祝日の週**(告知がない場合): 2026年の公表日程では、水〜金に連邦の祝日がある週の公表は **翌週の月曜** になっている(1/5、6/22、7/6、11/16、11/30、12/28)。2008年の告知は「祝日で1日遅れる」としている。→ 安全側の規則として、**火〜金のどこかに連邦の祝日がある週は、翌週の月曜 15:30 ET を上限**とする。火曜が祝日の週は、月曜時点のデータになる(2018-12 の告知)。
4. **早く公表された例**: 2014-07-04 に、7/7 公表予定の報告が誤って公表された。規則上は予定の 7/7 を使う(遅い方なので安全)。
5. **それ以外の週**: 金曜 15:30 ET。

**JST での意味**: 金曜 15:30 ET は土曜 04:30(夏)/ 05:30(冬)JST なので、日曜の Origin(1W・4W)で使える。月曜に公表がずれた週は、その週の日曜の Origin では使えず、翌週に回る。

**実装前の Gate**:

- CFTC TFF の利用開始可能日は、年次ファイルと JAPANESE YEN の契約コードの存在を、実装前の Gate で一次資料から確定する(現時点では未確定。CFTC の過去ファイルは、2009年以降の年次ファイルと、別の 2006〜2016年のファイルが並ぶ構造になっている)。
- **履歴ファイルや Historical Viewable に記載された Report Date を、Publication Date として扱わない**(Historical Viewable はページ上の日付が report date だと明記している)。公表時刻は必ず上の規則で別に決める。
- 上の規則で、使う範囲のすべての報告について公表時刻の上限を決められること。決められない報告は、使わないことを明示する。

円の契約: JAPANESE YEN - CHICAGO MERCANTILE EXCHANGE。契約コード 097741 は候補で、未確定。各年の年次ファイルに存在するかと過去の変遷を、上の Gate で確認する。

## 4. 利用条件

| ソース | 確認結果 | 判定 |
|---|---|---|
| ECB | 出典を明記すれば利用可(運用中) | 公開リポジトリに原データを置く |
| CFTC | 「CFTC のウェブサイトにある政府情報は public domain で、自由に配布・複製できる」(CFTC Web Policy)。利用時は CFTC の出典表示を求めている | 原データを置く(出典を明記) |
| 財務省 | 特記のない限り **公共データ利用規約 第1.0版(PDL1.0)** を適用(財務省サイトの利用について)。PDL1.0 は出典の記載を条件に複製・公衆送信・翻案・商用利用を認め、**CC BY 4.0 と互換**。数値データは著作権の対象外 | 原データを置く(出典と PDL1.0 を明記。加工した場合は加工したことを明記) |
| U.S. Treasury | サイトの方針ページに、著作権に関する文言は見つからなかった。連邦政府の著作物として著作権の対象外と考えられる | **残りの確認事項**(低リスク)。確認できるまでは SHA-256 と取得時刻だけを公開し、原データは置かない |
| Cboe(VIX) | 「Cboe の Content を使うには事前の承認が必要で、双方が license agreement に署名するまで使用は認められない」(Use of Cboe Content) | **LICENSE_UNRESOLVED → V1 から除外** |

**VIX(C3)の決定**: M1-MACRO V1 から除外する。Reason_Code = **LICENSE_UNRESOLVED**(むすび 10/16 23:36 承認)。

- 予測の成績を見た後の変数選択ではなく、Data Feasibility / Licensing Gate による事前の除外である。
- 第三者の配信(FRED の VIXCLS など)を使っても、元の権利は Cboe にあるので解決しない。
- 将来、利用の承認が得られれば、別の Version / Trial で戻せる。

## 5. 欠測・取得失敗の規則(確定案)

| 種類 | 判定のしかた | 扱い |
|---|---|---|
| (a) 構造的な欠測 | 系列がまだない期間、CFTC の再構築で使えない報告(§3) | MODEL_PREREQ_UNAVAILABLE |
| (b) 本番での取得失敗 | T_info より後のすべての実行で、取得の要求そのものが失敗した(接続できない、エラー、ファイルが壊れている) | ABSTAIN_SYSTEM(理由 FEATURE_UNAVAILABLE)。古い値で代用しない |
| (c) ソース側の公表の遅れ | 取得は成功したが、期待する日付の値がまだない | その系列の公表営業日で 2日まで、直前の値を使う(staleness を記録する)。超えたら STALE → MODEL_PREREQ_UNAVAILABLE |

注意が必要な点:

1. **(b) と (c) の区別**: 取得が成功してファイルの中身が読めたかどうかで機械的に決める。中身が読めたのに期待する日付がなければ (c)、読めなければ (b)。
2. **過去と本番の非対称性**: 過去の再構築では (b) は起きない。(c) も、米国債や日本国債では過去の公表の遅れの記録がないので、「遅れはなかった」として扱うことになる。本番だけで (b)・(c) が起きる。件数は運用の指標として記録する(成績ではない)。
3. **公表営業日のカレンダー**: 過去の再構築では、確定した系列に値がある日を公表営業日とする。ハリケーンや国葬による臨時の休場は、事前に告知されないこともある。この点について、カレンダーの決め方が staleness の数え方にだけ影響し、値には影響しないことを Transformation Spec に明記する。
4. **本番で T_info より後に取得した値**: 07:55 の実行で取得したファイルには、T_info より後に公表された値(例: 夏時間の D−1 の米国債)が含まれることがある。値の日付の規則で必ず除外し、除外したことを記録する。
5. **過去の値の書き換え**: 本番では取得ごとに snapshot と SHA-256 を保存する。前回の snapshot と比べて過去の値が変わっていたら、その事実を記録する。発行済みの特徴量は書き換えない(M1-VOL の「発行済みσは変更不可」と同じ考え方)。

## 6. 残りの確認事項と Gate

| 項目 | 状態 |
|---|---|
| CFTC 2018〜2019年の「通常の日程に戻った日」の公式資料 | 未確定。確定できなければ §3 の規則でその期間を使わない(どちらでも Freeze は可能) |
| CFTC TFF の利用開始可能日と、円の契約コードの存在・変遷 | 実装前の Gate(§3)。Report Date を公表日として扱わない |
| CFTC 2025年の 12/10〜12/29 の公表が済んだことの公式確認 | 実装前の Gate(§3)。見つからなければ予定日の翌営業日を上限にする |
| 日銀・FOMC の過去の日程告知の一覧 | 作業が必要(日銀は告知ページが残っている) |
| U.S. Treasury の利用条件の文言 | 低リスク。確認できるまで原データは公開しない |

## 7. 再監査の結果(むすび 2026-10-16 23:36)

- 判定: CONDITIONAL PASS / FREEZE READY AFTER MINOR REVISION → 3点を修正して Freeze。
- CFTC の公表時刻の上限の方式: 原則承認(2013年の 11/8 までの不使用、2018〜19年の Gate を含む)。
- 欠測 (b)・(c) の区別: 承認。fetch / parse の成否を最初の分岐にする。
  - fetch / parse に失敗 → ABSTAIN_SYSTEM / FEATURE_UNAVAILABLE
  - 成功したが、期待する値の日付がない → ソース側の遅れとして判定
  - 許容内 → 最後に使える値を使う
  - 上限を超えた → MODEL_PREREQ_UNAVAILABLE / STALE
- Performance Seal: 維持(この表はモデルの成績に一切触れていない)。
- 次の段階: この表は触らずに、Transformation Spec に進む。

## 出典
- [U.S. Treasury — Treasury Yield Curve Methodology](https://home.treasury.gov/policy-issues/financing-the-government/interest-rate-statistics/treasury-yield-curve-methodology)
- [Federal Reserve Board — H.15](https://www.federalreserve.gov/releases/h15/)
- [財務省 — 国債金利情報の提供について](https://www.mof.go.jp/jgbs/reference/interest_rate/p220226.htm)、[別添PDF](https://www.mof.go.jp/jgbs/reference/interest_rate/p220226_1.pdf)、[公表時刻(FAQ)](https://www.mof.go.jp/faq/jgbs/04hf.htm)、[財務省サイトの利用について](https://www.mof.go.jp/notice.html)
- [デジタル庁 — 公共データ利用規約 第1.0版](https://www.digital.go.jp/resources/open_data/public_data_license_v1.0)
- [野村證券 証券用語解説 — 公社債店頭売買参考統計値](https://www.nomura.co.jp/terms/japan/ko/kousyasai-tentou.html)(15時時点の気配。二次資料。日本証券業協会の資料で裏付けるのが望ましい)
- [CFTC — COT Reports(FAQ)](https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm)、[Release Schedule](https://cftc.gov/MarketReports/CommitmentsofTraders/ReleaseSchedule/index.htm)、[Historical Special Announcements](https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalSpecialAnnouncements/index.htm)、[Release 6745-13(2013年)](https://www.cftc.gov/PressRoom/PressReleases/6745-13)、[Release 6738-13](https://www.cftc.gov/PressRoom/PressReleases/6738-13)、[Release 7864-19(2019年)](https://www.cftc.gov/PressRoom/PressReleases/7864-19)、[Web Policy](https://www.cftc.gov/webpolicy/index.htm)
- [CFTC — Historical Viewable(ページ上の日付は report date)](https://www.cftc.gov/MarketReports/CommitmentsofTraders/HistoricalViewable/index.htm)
- [Saxo — CFTC releases COT schedule(2019年、二次資料)](https://home.saxo/content/articles/commodities/cftc-releases-cot-schedule-30012019)
- [Cboe — VIX Historical Data](https://www.cboe.com/en/tradable-products/vix/vix-historical-data/)、[Use of Cboe Content](https://www.cboe.com/use-of-content)
- [日本銀行 — 金融政策決定会合の日程変更(2020年3月16日)](https://www.boj.or.jp/mopo/mpmsche_minu/m_ref/rel200316l.htm)
