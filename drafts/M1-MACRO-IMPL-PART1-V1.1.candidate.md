# M1-MACRO Implementation Spec — Part 1: 入力と point-in-time のデータ契約(V1.1 案)- 状態: **V1.1 FREEZE CANDIDATE**(Claude、2026-10-17)。Freeze 済みの M1-MACRO-IMPL-PART1-V1(SHA-256 bf4c63d4…)に、実装中に見つかった先読みの穴の対策を加えた版。むすびの判断(2026-10-17 18:25 JST、drafts/IMPL-FINDINGS-01.md への回答)に従う。
- V1 からの変更(範囲は CFTC の Forward での取得と利用可否の規則だけ。統計モデル、変換、Transformation・Model・EVAL の仕様は変えない):
  1. **CFTC Forward Snapshot Gate を加えた(§2.3.1)。** Forward で CFTC の報告を使うには、Usable_From ≤ T_info に加えて、その報告を含む公式の原ファイルの snapshot が T_info 以前に取得されたことを、取得時刻の記録で示さなければならない(二重の Gate)。
  2. T_info までに必要な snapshot を正常に取得・検証できなかった場合は、その Origin の F_POS を ABSTAIN_SYSTEM(FEATURE_UNAVAILABLE)とする。T_info より後の snapshot や、前の Origin のための snapshot に切り替えて FORECAST を出すことはしない(§2.3.1、§7)。
  3. §3 の取得の時刻に、CFTC の T_info より前の取得を加えた。
  4. CFTC の過去の公表日の Gate の残り(Matrix §6)を、むすびが承認した内容(IMPL-FINDINGS-01 の確認事項 1、CFTC HISTORICAL RELEASE GATE = PASS / CLOSE)で閉じ、例外の表の中身を記録した(§2.3.2)。
- 理由: V1 では、今後 config の表にない遅れ(新しい国葬・閉鎖・臨時の遅れ)が起きると、規則 ⑤ が金曜 15:30 ET を返す一方、実際の公表は T_info より後になりうる。取得は T_info より後にも行うので、T_info の時点では存在しなかった報告が特徴量に入りうる(information-set violation)。
。
- 前提(すべて Freeze 済み): M1-MACRO-DATA-AVAILABILITY-V1(以下 Matrix)、M1-MACRO-TRANSFORM-PART1/2A/2B-V1、M1-MACRO-MODEL-PART1〜2E-V1、EVAL-SPEC-V1、S0(参照実装 v1.1)、ORIGIN_TARGET_MAP_V1
- 役割: Freeze 済みの仕様を、一意に・決定的に実行できるようにする。**モデルを変えない。** 実装上の選択を、成績を見て決めることは禁止(§8)。
- Implementation Spec の分割: Part 1 データと入力(この文書) → Part 2 推定とソルバー → Part 3 状態・予測・台帳 → Part 4 決定性・再生・封印。

## 1. 時刻と暦の基本

| 項目 | 定義 |
|---|---|
| Origin D | ORIGIN_TARGET_MAP_V1 の正式な起点日(JST の日付) |
| T_info(D) | D の 03:00:00 JST(Matrix §0)。すべての時刻は UTC に直して保存し、JST・ET の変換は IANA のタイムゾーン(Asia/Tokyo、America/New_York)で行う |
| 公表営業日の暦(source-business-day) | 系列ごとに別。**その系列に値がある日付の集合**とする(Matrix §5 注3)。米国債 = Treasury の系列に値がある日、日本国債 = 財務省の系列に値がある日 |
| 過去の再構築での暦 | 実装の Freeze 時点の snapshot(§6)に値がある日付 |
| 本番での暦 | その実行で**正常に**取得し、**正常に**読み取った公式の系列の snapshot に値がある日付(§1.1 の検査を通ったものに限る) |

### 1.1 暦を取得の失敗で変えない(silent calendar drift の防止)

公表営業日の暦は、正常に取得・読み取りした公式の系列の snapshot で観測された日付の集合から作る。**取得や読み取りの失敗による欠落を、営業日でない日と解釈して暦を作り直してはならない。** 正常であることを確かめられない場合は、Matrix V1 §5 と Transformation 2-A の失敗の状態(ABSTAIN_SYSTEM、FEATURE_UNAVAILABLE)に移る。

正常であることの検査(すべてを満たさなければ正常としない):

1. HTTP の状態が成功で、ファイルを最後まで読み取れた(読み取りの例外がない)。
2. 期待する列(config で固定した列名)がすべてある。
3. **前回まで受け入れた snapshot にある日付が、今回の snapshot から消えていない**(重なる期間について。値の改訂は §5 で記録するが、日付が消えることは許さない)。消えていれば ABSTAIN_SYSTEM(FEATURE_UNAVAILABLE、subreason = CALENDAR_INTEGRITY)。
4. 今回の snapshot の最後の日付が、前回の snapshot の最後の日付より前ではない。

## 2. 系列ごとの契約

### 2.1 米国債2年(F_US)

| 項目 | 内容 |
|---|---|
| 取得元 | U.S. Treasury「Daily Treasury Par Yield Curve Rates」の CSV(年ごとのファイル、公式の archive を含む)。正確な URL と列名は、実装の前に見出しだけで確かめて config に固定する |
| データセットの識別(固定) | dataset identity = **Daily Treasury Par Yield Curve Rates**、maturity = **2 Yr**。この値は、Treasury の daily par yield curve から読み取る固定満期点(CMT)であり、特定の2年国債の銘柄の市場利回りではない。別の2年の系列(Real Yield、Bill Rates、FRED の DGS2 など)に、黙って置き換えない |
| 値の日付 v(Origin D) | **D − 1(暦日)より前の、米国債の公表営業日のうち最後の日**(Matrix §2) |
| 20日前 | 米国債の公表営業日で v から 20 日前の日 v−20 |
| 欠測・古さ | 取得と読み取りは成功したが v の値がない場合、ソース側の遅れ。直前の値を使い、公表営業日で 2 日まで許す(Matrix §5、Transformation 2-A)。超えたら FEATURE_STALE。取得や読み取りに失敗した場合は ABSTAIN_SYSTEM(FEATURE_UNAVAILABLE) |
| 単位 | 利回りはパーセント(%)で公表される。1% = 100bp なので、F_US = y(v) − y(v−20)(% の差がそのまま 100bp 単位の値になる)。計算は小数の誤差を避けるため、公表された文字列を10進数(Decimal)として読んで差を取る |
| 改訂 | 取得ごとに snapshot を保存し、過去の値が前回の snapshot から変わっていたら記録する。発行済みの特徴量は書き換えない |

### 2.2 日本国債2年(F_JP)

| 項目 | 内容 |
|---|---|
| 取得元 | 財務省「国債金利情報」の CSV(過去分 jgbcm_all.csv、当月分 jgbcm.csv)。和暦の日付を西暦に直す。列名(2年)は実装の前に見出しだけで確かめて config に固定する |
| 値の日付 u(Origin D) | **D より前の日本の最後の公表営業日の、さらに前の公表営業日**(Matrix §2、2 営業日遅れ) |
| 20日前 | 財務省の公表営業日で u から 20 日前の日 u−20 |
| 欠測・古さ・単位・改訂 | 2.1 と同じ |

### 2.3 CFTC TFF 日本円(F_POS)

| 項目 | 内容 |
|---|---|
| 取得元 | CFTC Historical Compressed の TFF Futures Only の年次ファイル(fut_fin_txt_YYYY.zip、fin_fut_txt_2006_2016.zip)。本番では当年のファイル |
| 対象 | CFTC_Contract_Market_Code = 097741(CFTC Gate) |
| 使う列 | Leveraged Funds の Long と Short、総建玉。列名は実装の前に年次ファイルの見出しだけで確かめて config に固定する(Transformation Part 1) |
| 報告日 | Report_Date の列(ファイルによって書式が違う: YYYY-MM-DD、MM/DD/YYYY、M/D/YYYY 時刻つき。CFTC Gate で確認済み) |
| 2つの時刻 | 報告ごとに Usable_From(公表時刻の上限)と Expected_Release(通常の公表規則での時刻)を計算し、**別々のフィールドとして保存する**(Transformation 2-A、等しいと決め打ちしない) |
| Usable_From の計算 | Matrix §3 の規則をこの順で適用する。①特別告知で公表日が確定している報告(2025年の政府閉鎖の表のうち、確認できた日付、2025-01 の国葬の週など)、②公表日の一部しか分からない政府閉鎖の期間(2013年 → 2013-11-08 15:30 ET、2018〜2019年 → Gate の規則、それ以前 → 使わない)、③祝日の週(火〜金に連邦の祝日 → 翌週月曜 15:30 ET)、④早い公表(2014-07)は予定どおり、⑤それ以外は金曜 15:30 ET |
| 例外の表 | ①②の日付は config の表として固定する(出典の URL つき)。表に載っていない例外を実行時に推測で加えない |
| 連邦の祝日 | 米国の連邦の祝日の規則(法定の祝日)と、臨時の休み(国葬の日など、Matrix §3 の告知にあるもの)を config の表として固定する |
| 利用開始 | Origin 2010-12-08(CFTC Gate)。それより前は FEATURE_NOT_YET_AVAILABLE |
| 古さ | Transformation 2-A §2.3(次の報告の Expected_Release を過ぎても Usable_From に達していなければ FEATURE_STALE) |
| 本番の公表日程 | 本番では、CFTC の公式の Release Schedule と特別告知を、実行のたびに取得して保存する。Expected_Release はそれから決める |

#### 2.3.1 CFTC Forward Snapshot Gate(V1.1 で追加)

Origin ごとに、T_info より前に、公式の CFTC の原ファイル(その時点の当年の年次ファイル)を取得し、原データのバイト列、Retrieved_At_UTC、SHA-256 を保存する。

- **使える snapshot**: Retrieved_At_UTC が、その Origin の取得の窓 (T_info − 6 時間, T_info] の中にあり、§1.1 の正常性の検査を通った snapshot だけを、その Origin の F_POS の計算に使ってよい。窓の中に複数あれば、Retrieved_At_UTC が最も遅いものを使う。
- **使える報告**: Forward の Origin で F_POS に使う報告 R は、次の両方を満たすものに限る。
  1. Usable_From(R) ≤ T_info(V1 の規則 ①〜⑤)
  2. R がその Origin の使える snapshot に含まれている
  この2つを満たす報告のうち、報告日が最も新しいものを使う。
- **取得の失敗**: T_info までに、使える snapshot を正常に取得・検証できなかった場合、その Origin の F_POS は ABSTAIN_SYSTEM(FEATURE_UNAVAILABLE、subreason = CFTC_PRE_TINFO_SNAPSHOT_UNAVAILABLE)とする。**T_info より後に取得した snapshot、または前の Origin のための snapshot に切り替えて FORECAST を成立させない。**
- **公表の遅れとの区別**: 使える snapshot はあるが、期待する報告がまだ含まれていない場合は、取得の失敗ではない。直前の報告を使い、古さは V1 のとおり Expected_Release で判定する(FEATURE_STALE になりうる)。
- 本質的な条件は、Retrieved_At_UTC が T_info 以前であることを記録で示せることであり、取得の実行の予定時刻ではない。予定時刻(§3)は config で固定する。
- Release Schedule と特別告知は、引き続き Expected_Release(古さの判定)と監査の記録に使う。先読みを防ぐ最終の証拠は、T_info より前の snapshot とする。
- 過去の再構築の期間(Forward より前の Origin)には、T_info より前の snapshot は存在しないので、この Gate は適用しない。V1 の規則 ①〜⑤ と例外の表(§2.3.2)だけで判定する。
- 保存: snapshot の原データは公開リポジトリに保存する(CFTC は public domain、§4)。Retrieved_At_UTC、バイト数、SHA-256 を特徴量の台帳(Impl Part 3 §6.1)に記録する。

#### 2.3.2 例外の表の中身(Matrix §6 の Gate を閉じた結果)

むすびが承認した内容(2026-10-17 18:25 JST、CFTC HISTORICAL RELEASE GATE = PASS / CLOSE)。config の表として固定する。

| 報告日 | Usable_From(上限) | 根拠 |
|---|---|---|
| 2013-10-01〜2013-10-29 の報告 | 2013-11-08 15:30 ET | Release 6745-13(規則 ②) |
| 2018-12-24〜2019-03-05 の報告 | なし(FEATURE_GATE_EXCLUDED) | Release 7864-19。通常の日程に戻った日付の公式記録がない(規則 ②) |
| 2025-01-07 の週の報告 | 2025-01-13 15:30 ET | 2025-01-07 付の告知(国葬。規則 ①) |
| 2025-09-30 | 2025-11-19 15:30 ET | 2025-12-09 付の告知の表(実際の公表) |
| 2025-10-07 | 2025-11-21 15:30 ET | 同上 |
| 2025-10-14 | 2025-11-25 15:30 ET | 同上 |
| 2025-10-21 | 2025-12-02 15:30 ET | 同上 |
| 2025-10-28 | 2025-12-05 15:30 ET | 同上 |
| 2025-11-04 | 2025-12-09 15:30 ET | 同上 |
| 2025-11-10 | 2025-12-11 15:30 ET | 予定 12-10 の翌営業日(公表が済んだ公式の確認なし。Matrix §3 の 1) |
| 2025-11-18 | 2025-12-15 15:30 ET | 予定 12-12 の翌営業日 |
| 2025-11-25 | 2025-12-16 15:30 ET | 予定 12-15 の翌営業日 |
| 2025-12-02 | 2025-12-18 15:30 ET | 予定 12-17 の翌営業日 |
| 2025-12-09 | 2025-12-22 15:30 ET | 予定 12-19 の翌営業日 |
| 2025-12-16 | 2025-12-24 15:30 ET | 予定 12-23 の翌営業日 |
| 2025-12-23 | 2025-12-30 15:30 ET | 予定 12-29 の翌営業日 |

- 翌営業日は、米国の連邦の祝日の表(§2.3)で数える。
- 臨時の休み(連邦の祝日の表に加えるもの): 2018-12-05(Bush 元大統領の国葬)、2025-01-09(Carter 元大統領の国葬)。

### 2.4 親モデル S0 との接続

- M1-MACRO は、S0 が同じ (p, t, h) で発行した値(Pool の Z_i、σ_M0、Point、Decision_Class)を入力に使う。S0 を計算し直さない。
- 過去の再生では Freeze 済みの S0 の出力(参照実装 v1.1 の出力、SHA-256 で照合)を使う。本番では台帳に発行済みの S0 の行を使う。
- S0 の行が FORECAST でなければ、M1-MACRO は MODEL_PREREQ_UNAVAILABLE(PARENT_PREREQ_UNAVAILABLE)。
- 推定の損失(Model 2-A)には、各過去の機会で S0 が発行した Pool の Z_i と σ_M0 が必要になる。S0 の台帳の行に Pool の全点が保存されていない場合は、Freeze 済みの S0 のコードで同じ入力から決定的に再生成し、Pool_N・Mean_Z・Q10_Z・Q90_Z が台帳の値と一致することを確かめてから使う。一致しなければ PIPELINE_FAILURE とする。

## 3. 取得の仕組み

- 取得は GitHub Actions で行う(この作業環境からは取得元に接続できないため)。
- 1回の実行で、必要なすべての取得元のファイルを取得し、取得時刻(UTC)、HTTP の状態、バイト数、SHA-256 を記録する。
- 取得は T_info より後の実行(Matrix §3: 04:40 / 06:40 / 07:55 JST)で行う。どの実行で取得しても、**値の日付の規則と Usable_From で T_info 以前に使えたものだけを使う**(実行の時刻によって使う値が変わらない)。
- **CFTC だけは、これに加えて T_info より前の取得を行う**(§2.3.1)。予定時刻は 00:40 と 02:40 JST(config で固定)。どちらも、その Origin の取得の窓 (T_info − 6 時間, T_info] の中にある。

## 4. 原データの保存

| 取得元 | 保存場所(案) | 根拠 |
|---|---|---|
| CFTC | 公開リポジトリに原ファイルを保存 | public domain(CFTC Web Policy、Matrix §4) |
| 財務省 | 公開リポジトリに原ファイルを保存し、出典と PDL1.0 を明記 | PDL1.0(Matrix §4) |
| U.S. Treasury | **原データ(取得したバイト列そのもの)は、公開しない変更不可の保管場所(private immutable storage)に保存する。** 公開リポジトリには、取得元の識別情報、取得時刻(UTC)、バイト数、SHA-256(必要なら HTTP のメタデータ)だけを保存する。将来、公開での再配布の可否が確認できても、M1-MACRO-V1 の保存方式は変えない | 公開できないと判断したのではない(米国連邦政府の著作物については 17 U.S.C. §105 の原則がある)。Freeze 済みの Matrix §4 の条件を覆す、この特定のデータセットについての一次資料の根拠が確認できていないため |

## 5. 改訂の検出

- 取得のたびに、前回の snapshot と比べて、過去の日付の値が変わったかを機械的に確かめる。変わっていれば、日付・旧値・新値を記録する。
- 発行済みの特徴量・β・予測は書き換えない。

## 6. 過去の再生に使う snapshot

- 実装の Freeze の時点で、3つの取得元の過去分を1回だけ取得し、SHA-256 を付けて固定する(開発用の snapshot)。
- 過去の再生(Implementation Part 4)は、この snapshot だけを使う。
- ECB の価格は、M0・S0 と同じ開発用の snapshot(f36e0aff…、2026-10-09 まで)を使う。

## 7. 本番の欠測と失敗の判定の順序

Transformation 2-A と Matrix §5 の判定を、次の順序で機械的に行う。

1. 取得(HTTP)の失敗、読み取り(parse)の失敗、または §1.1 の正常性の検査に通らない → ABSTAIN_SYSTEM(FEATURE_UNAVAILABLE。§1.1 の検査3・4に通らない場合は subreason = CALENDAR_INTEGRITY)。F_POS について、T_info までに使える snapshot がない場合も、ここに当たる(subreason = CFTC_PRE_TINFO_SNAPSHOT_UNAVAILABLE、§2.3.1)
2. Origin が特徴量の利用開始より前 → MODEL_PREREQ_UNAVAILABLE(FEATURE_NOT_YET_AVAILABLE)
3. Gate で使えないとした期間 → MODEL_PREREQ_UNAVAILABLE(FEATURE_GATE_EXCLUDED)
4. 期待する値の日付がない、許容された古さを超えた → MODEL_PREREQ_UNAVAILABLE(FEATURE_STALE)
5. 変化を計算できない(20日前の値がない、総建玉が 0 または欠けている) → MODEL_PREREQ_UNAVAILABLE(FEATURE_NOT_COMPUTABLE、subreason を分けて記録)

## 8. 禁止すること(実装の選択を装ったモデルの調整)

- 取得元、列、日付の解釈、例外の表、祝日の表などを、成績(損失・係数・的中など)を見て選ぶ・変えること
- 入力や特徴量の値を見たこと(§9)を理由に、変換、取得元、遅れ、切り捨て、特徴量の選択などを変えること
- 同じ系列の別の取得元(FRED など)を試して、成績で選ぶこと
- 実装の Freeze の後に、これらを変えること(変える場合は新しい Version / Trial)

## 9. 実装の検証で見てよいもの(Performance Seal の境界)

Model Spec はすべて Freeze 済みなので、実装を正しく検証するために、入力と特徴量の値を見ることを許す。以前の「特徴量の値を見ない」は、モデルの設計中の保護だった。

| 区分 | 内容 |
|---|---|
| **許す** | 取得した原データの値、読み取った入力の値、特徴量の計算の単体検査に必要な中間値、F_US・F_JP・F_POS の値、日付、Usable_From、Expected_Release、欠測の状態 |
| **禁止(封印を続ける)** | β、μ、M1-MACRO の予測分布、M1-MACRO と S0 の損失の差、CRPS などの成績、方向の成績、確認的な統計量、およびそれらから作れてモデルの選択に使える集計 |

入力と特徴量の値を見たことを理由に、変換、取得元、遅れ、切り捨て、特徴量の選択などを変えることは禁止する(§8、Transformation Part 1 §6 のロック)。

## 10. 実装の前提として必要なこと

- 米国債の原データを保存する、公開しない変更不可の保管場所(§4)。特定のサービスに限定しない。純さんの非公開のリポジトリなどが候補で、用意は純さんに依頼する。
