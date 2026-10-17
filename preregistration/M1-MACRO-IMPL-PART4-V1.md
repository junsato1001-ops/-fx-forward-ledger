# M1-MACRO Implementation Spec — Part 4: 決定性・再生・封印(案 v1)

- 状態: **v1 FREEZE CANDIDATE**(Claude、2026-10-17)。v0(Git blob 27cc3414…)に対するむすびの監査(2026-10-17 07:35 JST、全文を取得して監査、CONDITIONAL PASS)を反映した。
- v0 からの変更:
  1. POOL_V1 の同じ値の並べ方の矛盾を直した。数値の昇順、同じ値は16進の文字列の ASCII 昇順なので、+0.0 が −0.0 より先(§2.2)。
  2. 「ハッシュは CPU によらない」の書き方を直した。CPU によらないのは、確定した binary64 の値を直列化してハッシュにする規則である。演算の結果が CPU で違えば、その結果を含むハッシュ(Beta_SHA256 など)も違う(§1)。
  3. 締め切りの判定を transaction の完了の時点にした。手順 8 の読み戻しが終わった時刻 Verified_At_UTC が締め切り以前の場合だけ ON_TIME とし、別の監査の記録に Run_ID、Committed_At_UTC、Verified_At_UTC、Deadline_Status を残す。確認的な評価は COMPLETE かつ ON_TIME の行だけを使う(§3)。
  4. Forward の予測の行に Evidence_Class の列を加える案を取り下げた。Freeze 済みの Part 3 は変えない。分離は置き場所(ledger/ と replay/)と COMPLETE・ON_TIME で行う(§7)。
- 前提(すべて Freeze 済み): M1-MACRO-IMPL-PART1-V1、PART2-V1、PART3-V1、M1-MACRO-MODEL-PART1/2A〜2E-V1、M1-MACRO-TRANSFORM-PART1/2A/2B-V1、EVAL-SPEC-V1、PERFORMANCE_SEAL_BOUNDARY_V1、正式の Forward 台帳(forward/issue.py、verify.py)
- 封印: 実データの β、μ、損失、成績は見ていない。
- 範囲: Implementation Spec の最後の層。(1) 実行環境とコードの固定、(2) 正規の直列化とハッシュ、(3) 発行の transaction の手順、(4) 実装の Freeze までの検証の関門、(5) 封印を開ける手順と、過去の再生の結果を見てよい範囲、(6) 再生の結果と Forward の証拠の分離、(7) Freeze 後の変更の扱い。Part 3 から渡された3つの宿題(transaction の完全な順序、pool と E_Input の正規の直列化、過去の再生の β・μ の解禁の時期)をここで閉じる。

## 1. 実行環境の固定

| 項目 | 固定の方法 |
|---|---|
| 実行の場所 | GitHub Actions。ジョブは、digest(sha256)で指定したコンテナのイメージの中で走らせる(タグだけで指定しない) |
| Python とパッケージ | Python の版はイメージで固定。パッケージ(numpy、highspy、tzdata など)は、版とハッシュを書いたロックファイルから `pip install --require-hashes` で入れる |
| タイムゾーンのデータ | IANA のデータは tzdata パッケージの版で固定する(OS のタイムゾーンのデータを使わない)。JST・ET の変換(Impl Part 1 §1)はこれで決まる |
| 環境変数 | PYTHONHASHSEED=0、TZ=UTC、LC_ALL=C.UTF-8、OMP_NUM_THREADS=1、OPENBLAS_NUM_THREADS=1、MKL_NUM_THREADS=1 |
| 並列 | 推定と予測の計算は1つのプロセス、1つのスレッドで行う(Impl Part 2 §9) |

- **ビットの一致の範囲**: 同じイメージ・同じロックファイル・同じ種類の CPU では、β*、μ、予測の各欄、各ハッシュがビットで一致することを求める。GitHub Actions の runner の CPU は選べないので、CPU が違う場合はビットの一致を保証しない。そのときは Impl Part 2 §10 の許容誤差の中での一致を求める。**台帳に COMPLETE で発行した値が正式の記録であり、再計算は照合だけに使う。**
- **ハッシュと CPU の関係**: 同じ確定した binary64 の値に対する正規の直列化(§2)と SHA-256 は、CPU や環境によらず同じになる。ただし、演算の結果そのものが CPU の違いで異なる場合、その結果を含むハッシュ(Beta_SHA256 など)が一致することまでは要求しない。入力だけから決まるハッシュ(Pool_SHA256、E_Input_SHA256。入力は読み取った値と Freeze 済みの S0 の発行値で決まる)と、演算の結果を含むハッシュ(Beta_SHA256)を、ひとまとめに「CPU によらない」とは扱わない。同じ Freeze の環境で走る Forward ではビットの一致を求め、別の CPU での照合は Impl Part 2 §10 の許容誤差で行う(二層の構造)。

## 2. 正規の直列化とハッシュ

### 2.1 共通の規則

| 項目 | 規則 |
|---|---|
| 文字コード | UTF-8、BOM なし |
| 改行 | LF(\n)。最後の行の後にも LF を1つ置く |
| 区切り | カンマ(,)。値に区切りや改行が入らない形式だけを使う(引用符を使わない) |
| 浮動小数点(binary64) | IEEE 754 の binary64 を big-endian の 8 バイトにし、小文字の16進 16 文字で書く(Python: `struct.pack('>d', x).hex()`)。+0.0 は 0000000000000000、−0.0 は 8000000000000000 で区別する |
| NaN・無限大 | 書かない。直列化の対象に現れたら、その時点で失敗(Impl Part 2 §8 の NONFINITE、または PIPELINE_FAILURE) |
| 整数 | 10 進の ASCII。先頭の 0 や + を付けない |
| 日付・時刻 | 日付は YYYY-MM-DD。時刻は UTC で YYYY-MM-DDTHH:MM:SSZ |
| 文字列 | ペア名、Horizon(1D・1W・4W)、状態の名前など、ASCII の決まった語だけ |
| 版の見出し | 各直列化の1行目に、形式の名前と版(例: POOL_V1)を書く。形式を変えたら版の名前を変える |
| ハッシュ | 直列化したバイト列全体の SHA-256(小文字の16進 64 文字) |

### 2.2 pool(POOL_V1)

```
POOL_V1
<Pair>,<Origin>,<Horizon>,<N>
<Z_1 の16進>
...
<Z_N の16進>
```

- Z は数値の昇順に並べる。数値として等しい場合は、16進の文字列の ASCII 昇順で並べる。したがって +0.0(0000000000000000)が −0.0(8000000000000000)より先になる。
- Pool_SHA256 はこのバイト列の SHA-256。

### 2.3 推定の入力 E_{t,h}(E_INPUT_V1)

```
E_INPUT_V1
<Origin t>,<Horizon h>,<|E_{t,h}|>,<N_Groups>
<Origin i>,<Pair>,<|P_i|>,<x_US>,<x_JP>,<x_POS>,<σ_g>,<y_g>,<Pool_SHA256>
...
```

- 群の行は (Origin i の昇順, Pair の ASCII 順) に並べる(Impl Part 2 §9 と同じ順序)。
- x、σ、y は §2.1 の16進。x_US は USDJPY 以外では +0.0(0000000000000000)。
- 重み ω_g = 1 / (|E_{t,h}| · |P_i|) は、2つの整数(1行目の |E| と各行の |P_i|)で正確に表し、浮動小数点の値は書かない。
- E_Input_SHA256 はこのバイト列の SHA-256(Part 3 §4)。

### 2.4 推定の結果(BETA_V1)

```
BETA_V1
<Origin t>,<Horizon h>,<Parameter_State>,<β_US>,<β_JP>,<β_POS>
```

- β は §2.1 の16進。DEFAULT_PARENT は +0.0。ESTIMATION_FAILED・NOT_EVALUATED では β の欄を空にする。
- Beta_SHA256 はこのバイト列の SHA-256。§5 の盲検の検査で、β の値そのものを見ずに、2回の実行の一致を確かめるために使う。

### 2.5 台帳の行

- 台帳の CSV は Python の csv モジュールで、lineterminator = "\n"、quoting = QUOTE_MINIMAL、列の順序は Part 3 §6 の順で書く。浮動小数点の欄は、台帳では人が読める "%.17g" の文字列(既存の台帳と同じ)とする。§2.1 の16進は、ハッシュ用の直列化だけで使う。
- 行の SHA-256 は、その行のバイト列(最後の LF を含む)の SHA-256。
- 範囲の SHA-256 は、その Run で1つのファイルに追記したすべての行のバイト列を、書いた順につなげたものの SHA-256。

## 3. 発行の transaction の手順

Part 3 §6.4 の commit の記録を、次の順序で行う。M1-MACRO の発行は、同じ Origin の S0 の行が正式の台帳に書かれ、既存の Storage Verification Gate(verify.py)が SUCCESS になった後に始める(親の行を origin/main から読む)。

1. **行を作る**: その Run で発行するすべての行(特徴量・推定・予測)を、メモリの上で作る。
2. **正規化とハッシュ**: 各行を §2.5 で直列化し、行の SHA-256 と、ファイルごとの範囲の SHA-256 を計算する。
3. **追記**: 3つの台帳(m1_macro_features.csv、m1_macro_estimation.csv、m1_macro_forecasts.csv)に追記する。
4. **push**: commit して origin/main に push する。push が競合で失敗した場合は、`git pull --rebase` の後に同じ行で push し直す(行の内容は変えない)。上限は 5 回。
5. **読み戻し**: `git fetch` の後、origin/main の3つのファイルを読み、その Run の行がそれぞれちょうど1回ずつ、バイトで同じに存在し、範囲の SHA-256 が手順 2 と一致することを確かめる。
6. **COMPLETE の追記**: m1_macro_issue_commits.csv に1行を追記する。列: Run_ID、Origin、Horizons、Features_Rows、Features_Range_SHA256、Estimation_Rows、Estimation_Range_SHA256、Forecasts_Rows、Forecasts_Range_SHA256、Status = COMPLETE、Committed_At_UTC。
7. **push**: 手順 4 と同じ。
8. **COMPLETE の読み戻し**: origin/main の m1_macro_issue_commits.csv に、手順 6 の行がちょうど1回、バイトで同じに存在することを確かめる。**ここまで通って、transaction は完了する。**

失敗したとき:

- 手順 1〜5 のどこかで失敗した場合、COMPLETE の行は書かない。追記済みの行は UNCOMMITTED として残る(Part 3 §6.4)。締め切りの前なら、新しい Run_ID で手順 1 からやり直してよい。
- 手順 7 の push が成功したかどうか分からない場合(手順 8 の読み戻しの失敗など)、**origin/main に COMPLETE の行があるかどうかだけで決める。** 後の Run で読み戻して、あれば正式、なければ UNCOMMITTED。COMPLETE の行を同じ Run_ID で2回書かない。
- **締め切り(transaction の完了の時点で判定する)**:
  - Committed_At_UTC は COMPLETE の行を作った時刻(手順 6 の直前の runner の時計)であり、**それだけでは締め切りを守ったことを示さない。**
  - 手順 8 の読み戻しが終わった時刻を、同じ runner の時計で Verified_At_UTC として記録する。**Verified_At_UTC ≤ その Origin の発行の締め切り(08:30 JST)の場合だけ ON_TIME** とする。
  - 手順 9 として、監査の記録 audit_log/m1_macro_issue_deadline.csv(追記のみ)に1行を追記して push する。列: Run_ID、Origin、Committed_At_UTC、Verified_At_UTC、Deadline_UTC、Deadline_Status(ON_TIME / LATE)。
  - Verified_At_UTC が締め切りより後なら LATE とする。COMPLETE の行は追記のみの証跡として残るが、その行は正式の Forward の証拠に使わない(Part 3 §3 の 1、LATE_ISSUE)。
  - 手順 8 の後に締め切りを過ぎた場合や、手順 9 の push が失敗した場合など、ON_TIME の記録が origin/main にない Run は、ON_TIME として扱わない(安全側)。後の Run が、別の Run の ON_TIME を後から書くことはしない。
  - **確認的な評価のコードは、COMPLETE の行があり、かつ audit_log に Deadline_Status = ON_TIME の行がある Run_ID の行だけを使う。**
- 同じ (p, t, h) に COMPLETE の Run が2つ以上ある状態は、仕様違反として監査の対象にする。手順 1 の前に、origin/main にその (p, t, h) の COMPLETE の行がすでにあれば、その Run は発行しない。
- 同時に2つの発行が走らないよう、workflow に concurrency の group を設定する。

## 4. コードと設定のハッシュ

- **Code_SHA256**: M1-MACRO の発行に関わるすべてのファイル(コード、ロックファイル、config、Freeze 済みの S0 のモジュールなど)について、(パス, そのファイルの SHA-256)をパスの ASCII 順に並べた一覧(CODE_MANIFEST_V1、§2.1 の規則)の SHA-256。既存の台帳の Code_SHA256 と同じ考え方。
- **config**: M1-MACRO の config(Impl Part 1 の列名・URL・例外の表・祝日の表、Impl Part 2 §7 の定数、Part 3 §2 の最初の Forward の Origin、米国債の非公開の保管場所の識別など)を1つのファイルにまとめ、Code_SHA256 に含める。
- **実装の Freeze の記録**(preregistration/M1-MACRO-IMPL-CODE-V1.freeze.json): commit のハッシュ、Code_SHA256、CODE_MANIFEST_V1 の全体、コンテナのイメージの digest、ロックファイルの SHA-256、開発用の snapshot(Impl Part 1 §6)の各ファイルの SHA-256、最初の Forward の Origin(Horizon ごと)、§5 の関門の結果の記録への参照。
- 発行のたびに、実行中のコードから計算した Code_SHA256 が Freeze の記録と一致することを確かめる。一致しなければ発行しない(PIPELINE_FAILURE)。

## 5. 実装の Freeze までの検証の関門

次をすべて、Freeze する予定の候補のコード(同じ Code_SHA256)で通す。どれかを通すためにコードや設定を変えた場合は、変えた後の Code_SHA256 で、最初からすべてやり直す。

| 関門 | 内容 | 見てよい結果 |
|---|---|---|
| G1 合成データ(Part 2) | Impl Part 2 §12 の例 A〜E を本番のコードで再現する | すべて(合成データ) |
| G2 実データと同じ大きさの合成データ | 群 12000・pool 6000 で、時間、収束、ε_tie の余裕(負の側の値と独立の実装との差が 10⁻¹⁴ 以下。Impl Part 2 §11) | すべて(合成データ) |
| G3 独立の実装との照合(合成) | Impl Part 2 §10 の基準 | すべて(合成データ) |
| G4 台帳の transaction | 一時的な試験用のリポジトリで、§3 の各手順の失敗と、締め切りの直前・直後の完了を人為的に起こし、COMPLETE と ON_TIME・LATE が正しく記録されることを確かめる。Part 3 §8 の 5〜7 | すべて(試験用のデータ) |
| G5 特徴量と暦(実データ) | Impl Part 1 の読み取り、値の日付、Usable_From、CALENDAR_INTEGRITY の検査 | Impl Part 1 §9 で許した範囲(入力値、特徴量の値、日付、状態) |
| G6 盲検の実行(実データ、Impl Part 2 §11 の 2) | 過去のすべての (t, h) で、本番と独立の実装を両方走らせる | 終了の状態、反復の数、UB − LB、Φ(β₂) − LB、照合の合否と差の大きさ、失敗の subreason だけ |
| G7 決定性(実データ、盲検) | 同じ環境で本番の実装を2回、最初から走らせ、すべての (t, h) で E_Input_SHA256 と Beta_SHA256(§2.4)が一致することを確かめる | ハッシュが一致したかどうかと、一致しなかった件数だけ。β の値は見ない |
| G8 S0 との入れ子(実データ、盲検) | DEFAULT_PARENT と μ = 0 の行が、S0 の行と文字列で完全に一致すること(Part 3 §8 の 1・2) | 一致した件数と一致しなかった件数だけ |
| G9 ホールドアウト | ホールドアウトのペアの行・計算が1つもないこと | 件数(0 であること) |

- G6〜G8 では、β、β の符号、μ、J*、CRPS、予測の値(確率・Point・PI)、M1 と S0 の差を、表示も保存もしない。結果のファイルには、上の「見てよい結果」の列だけを書く。
- 関門の結果は drafts/ ではなく audit/ の下に、コードの Code_SHA256 とともに記録し、むすびの監査を受ける。
- 関門で問題が見つかって変えてよいのは、数値の実装の問題だけ(Impl Part 2 §11)。定数を変える場合は Part 2 の新しい版で再監査する。

## 6. 封印を開ける手順と、過去の再生の結果

### 6.1 順序

1. §5 の関門をすべて通す。
2. むすびの監査を受けて、実装の Freeze を記録する(§4)。この記録で、最初の Forward の Origin(Part 3 §2)が決まる。
3. **封印を開ける記録**(preregistration/M1-MACRO-V1-SEAL-OPENING.json)を、実装の Freeze の記録の後の commit として書く。内容: 実装の Freeze の commit、§5 の関門の結果への参照、開ける日時。
4. 封印を開けた後に限り、過去の再生(§6.2)を計算し、見てよい。

### 6.2 過去の再生

- **目的**: 記述と診断だけ。Forward の予測の状態をつくるためのものではない。各 (t, h) の β は最初から解くので(Impl Part 2 §9)、Forward の発行は過去の β に依存しない。過去の再生をしなくても Forward は発行できる。
- **計算**: Freeze したコードと開発用の snapshot で、過去のすべての (t, h) の β*、μ、予測の各欄を計算する。
- **置き場所**: replay/ の下の別のファイル。**ledger/ には書かない。** 各行に Evidence_Class = DEVELOPMENT_REPLAY を書く。
- **使い方**: β の時間の推移、warm-up や失敗の件数、開発期間の成績などを、記述の統計として見てよい。EVAL-SPEC-V1 で、開発期間の成績は確認的な証拠に使わない。
- **再生の結果を見て、M1-MACRO-V1 の仕様、コード、config、最初の Forward の Origin を変えることはしない。** 再生から得た考えは、新しい Version(別の Trial)の設計の材料にだけ使える。
- 封印を開けた後でも、ホールドアウトの5ペアは計算しない(RFX-HOLDOUT-A-V1 は別の手続きで開ける)。

## 7. 再生と Forward の証拠の分離

| | 過去の再生 | Forward |
|---|---|---|
| 置き場所 | replay/ | ledger/(m1_macro_*.csv) |
| Evidence_Class の列 | あり(値は DEVELOPMENT_REPLAY) | **加えない**(Freeze 済みの Part 3 §6.2 の列のまま) |
| 正式な記録か | いいえ(いつでも計算し直せる) | はい(COMPLETE かつ ON_TIME の行だけ。追記のみ) |
| 確認的な評価 | 使わない | EVAL-SPEC-V1 §5.5(最初の確認的 Origin から 104 週後に1回) |

- 確認的な評価のコードは、ledger/ の、COMPLETE かつ ON_TIME(§3)の行で、Origin が最初の Forward の Origin 以後のものだけを読む。replay/ のファイル、UNCOMMITTED の行、LATE の行を読んだら止まる(assert)。Forward と再生の分離は、置き場所と COMPLETE・ON_TIME の状態だけで行い、Forward の行に列を加えない。
- Forward の推定の E_{t,h} は、過去の Origin の群を、開発用の snapshot から Part 3 §4 の規則で組み立てる。これは「過去の再生の予測」を使うのではなく、過去の入力(特徴量・S0 の pool・実現値)を使うものである。

## 8. 米国債の原データの保管(Impl Part 1 §4 の具体化)

- 非公開の保管場所: 純さんが用意する非公開のリポジトリ(候補の名前は fx-ledger-private-raw。作成後の正式な名前を config に書く)。
- 取得のたびに、原データのバイト列を非公開のリポジトリに commit し、公開の側の treasury_raw_manifest.csv に1行を追記する。列: Retrieved_At_UTC、Source_URL、Byte_Count、SHA256、Private_Repository、Private_Path、Private_Commit。
- 原データを使う計算は、非公開のリポジトリから読んだバイト列の SHA-256 が、公開の manifest の値と一致することを確かめてから行う。一致しなければ PIPELINE_FAILURE。
- 公開の manifest を先に(または同じ Run で)push しておくことで、非公開の側を後から差し替えても、ハッシュの不一致で見つかる(むすびの 04:38 の整理)。
- 非公開のリポジトリを GitHub Actions から読み書きする認証情報は、リポジトリの secrets に置き、ログに出さない。

## 9. Freeze 後の変更

- 実装の Freeze の後に、仕様・コード・config・環境のどれかを変えることは、M1-MACRO-V1 の中ではしない。変える場合は新しい Version(例: M1-MACRO-V1.1 または V2)として、新しい Freeze と新しい最初の Forward の Origin を定める。古い行は残す。
- 発行した行が仕様に反していたことが後で分かった場合: 行は書き換えない。incidents/ の下に記録(日時、該当する行の範囲、内容、原因)を追記する。その不具合が確認的な評価に与える影響の扱いは、評価の前に、成績を見ずに決めて記録する。
- 外部の変化(取得元の URL や形式の変更など)で取得できなくなった場合は、Impl Part 1 の失敗の状態(ABSTAIN_SYSTEM)になる。取得元を黙って置き換えない。置き換えるには新しい Version が必要。

## 10. むすびに確認してほしいこと

1. §2.2 の同じ値の並べ方(数値の昇順、同じ値は16進の ASCII 昇順で +0.0 が先)で、矛盾が解けたか。
2. §1 のハッシュと CPU の関係の書き方(入力だけから決まるハッシュと、演算の結果を含むハッシュを分けた)でよいか。
3. §3 の締め切りの判定(Verified_At_UTC ≤ 締め切りの場合だけ ON_TIME、audit_log に記録、ON_TIME の記録がない Run は安全側で ON_TIME としない、確認的な評価は COMPLETE かつ ON_TIME だけ)でよいか。
4. §7 で Forward の行に Evidence_Class の列を加えないことにした。
