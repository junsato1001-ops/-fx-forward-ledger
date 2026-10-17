# M1-MACRO Implementation Spec — Part 1: 入力と point-in-time のデータ契約(案 v0)

- 状態: DRAFT(Claude、2026-10-17)。むすびの監査待ち。
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
| 本番での暦 | その実行で取得したファイルに値がある日付 |

## 2. 系列ごとの契約

### 2.1 米国債2年(F_US)

| 項目 | 内容 |
|---|---|
| 取得元 | U.S. Treasury「Daily Treasury Par Yield Curve Rates」の CSV(年ごとのファイル)。正確な URL と列名(2年の列)は、実装の前に見出しだけで確かめて config に固定する |
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

### 2.4 親モデル S0 との接続

- M1-MACRO は、S0 が同じ (p, t, h) で発行した値(Pool の Z_i、σ_M0、Point、Decision_Class)を入力に使う。S0 を計算し直さない。
- 過去の再生では Freeze 済みの S0 の出力(参照実装 v1.1 の出力、SHA-256 で照合)を使う。本番では台帳に発行済みの S0 の行を使う。
- S0 の行が FORECAST でなければ、M1-MACRO は MODEL_PREREQ_UNAVAILABLE(PARENT_PREREQ_UNAVAILABLE)。
- 推定の損失(Model 2-A)には、各過去の機会で S0 が発行した Pool の Z_i と σ_M0 が必要になる。S0 の台帳の行に Pool の全点が保存されていない場合は、Freeze 済みの S0 のコードで同じ入力から決定的に再生成し、Pool_N・Mean_Z・Q10_Z・Q90_Z が台帳の値と一致することを確かめてから使う。一致しなければ PIPELINE_FAILURE とする。

## 3. 取得の仕組み

- 取得は GitHub Actions で行う(この作業環境からは取得元に接続できないため)。
- 1回の実行で、必要なすべての取得元のファイルを取得し、取得時刻(UTC)、HTTP の状態、バイト数、SHA-256 を記録する。
- 取得は T_info より後の実行(Matrix §3: 04:40 / 06:40 / 07:55 JST)で行う。どの実行で取得しても、**値の日付の規則と Usable_From で T_info 以前に使えたものだけを使う**(実行の時刻によって使う値が変わらない)。

## 4. 原データの保存

| 取得元 | 保存場所(案) | 根拠 |
|---|---|---|
| CFTC | 公開リポジトリに原ファイルを保存 | public domain(CFTC Web Policy、Matrix §4) |
| 財務省 | 公開リポジトリに原ファイルを保存し、出典と PDL1.0 を明記 | PDL1.0(Matrix §4) |
| U.S. Treasury | **未決(§9 の判断事項)**。Matrix §4 は、利用条件の文言を確認できるまで原データを公開リポジトリに置かず、SHA-256 と取得時刻だけを公開すると定めている | 利用条件の文言が一次資料でまだ見つかっていない |

## 5. 改訂の検出

- 取得のたびに、前回の snapshot と比べて、過去の日付の値が変わったかを機械的に確かめる。変わっていれば、日付・旧値・新値を記録する。
- 発行済みの特徴量・β・予測は書き換えない。

## 6. 過去の再生に使う snapshot

- 実装の Freeze の時点で、3つの取得元の過去分を1回だけ取得し、SHA-256 を付けて固定する(開発用の snapshot)。
- 過去の再生(Implementation Part 4)は、この snapshot だけを使う。
- ECB の価格は、M0・S0 と同じ開発用の snapshot(f36e0aff…、2026-10-09 まで)を使う。

## 7. 本番の欠測と失敗の判定の順序

Transformation 2-A と Matrix §5 の判定を、次の順序で機械的に行う。

1. 取得(HTTP)の失敗、または読み取り(parse)の失敗 → ABSTAIN_SYSTEM(FEATURE_UNAVAILABLE)
2. Origin が特徴量の利用開始より前 → MODEL_PREREQ_UNAVAILABLE(FEATURE_NOT_YET_AVAILABLE)
3. Gate で使えないとした期間 → MODEL_PREREQ_UNAVAILABLE(FEATURE_GATE_EXCLUDED)
4. 期待する値の日付がない、許容された古さを超えた → MODEL_PREREQ_UNAVAILABLE(FEATURE_STALE)
5. 変化を計算できない(20日前の値がない、総建玉が 0 または欠けている) → MODEL_PREREQ_UNAVAILABLE(FEATURE_NOT_COMPUTABLE、subreason を分けて記録)

## 8. 禁止すること(実装の選択を装ったモデルの調整)

- 取得元、列、日付の解釈、例外の表、祝日の表などを、成績(損失・係数・的中など)を見て選ぶ・変えること
- 同じ系列の別の取得元(FRED など)を試して、成績で選ぶこと
- 実装の Freeze の後に、これらを変えること(変える場合は新しい Version / Trial)

## 9. むすびと純さんに決めてほしいこと

1. **米国債の原データの保存**。次のどれにするか。
   - (a) Matrix の規則どおり、公開リポジトリには SHA-256 と取得時刻だけを置き、原データは公開しない場所(純さんの非公開のリポジトリなど)に保存する。再現の監査には、その場所への権限が要る。
   - (b) 米国連邦政府の著作物は原則として著作権の対象外であり、数値のデータでもあることを理由に、公開リポジトリに保存する。この場合は Matrix の規則を変えることになるので、Matrix の新しい版(理由つき)を作る。
   - (c) 公開リポジトリには、M1-MACRO が実際に使った値の日付の2年金利だけを保存する(原ファイルは保存しない)。これも Matrix の規則の解釈の変更になる。
   私の推奨は (a)。再現の監査には権限の管理が増えるが、Freeze 済みの規則を変えずに済む。
2. **実装の検査で、候補系列の値を見てよいか**。読み取りの正しさ(日付の変換、列の対応、単位)を確かめるには、取得した値の一部を見る必要がある。推奨: **特徴量の入力値(金利、建玉)を読み取りの正しさの確認のために見ることは許す。係数、損失、M1-MACRO の予測、S0 との比較、成績は見ない**(Implementation の Freeze まで)。モデルの仕様はすべて Freeze 済みなので、入力値を見てもモデルを変える余地はない。
