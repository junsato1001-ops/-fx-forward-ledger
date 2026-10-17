# IMPL-FINDINGS-03 — M1-MACRO 実装候補: 5つの部分の組み立て完了と、candidate 固定の前に判断が必要な事項

- 作成: Claude、2026-10-18(JST)
- 対象のコード: branch `m1macro-dev`、commit `83f5025`(この文書の時点。まだ candidate として固定していない。Code_SHA256 も固定していない)
- 封印: 実データで β、β の符号、μ、J*、CRPS、予測、M1 と S0 の差は、一度も計算していない。見たのは、Impl Part 1 §9 で許された範囲(取得したファイルの見出し、日付の範囲、件数、CFTC の日本円の行の原データの数、証明書の情報)だけ。
- 開発の検査の結果(G1〜G3 を含む)は、正式の関門には数えない(むすび 22:37)。

## 1. 組み立てたもの(むすび 22:51 の5項目の順)

| 項目 | ファイル(m1macro/) | 要点 |
|---|---|---|
| 1. CFTC の読み取りと R46 の固定 | `cftc_parse.py`、`tls.py`、`certs/SectigoPublicServerAuthenticationRootR46.pem`、`cftc_schedule.py` | 列名は 2006〜2016 と 2017〜2026 の全ファイルの見出しで確認して config に固定。R46 の SHA-256 指紋 `7bb647a6…5a06` を config に固定し、起動時に照合(一致しなければ例外)。追加の root は CFTC のホスト名だけに使う。システムの CA は置き換えない。指紋は Mozilla の CA 収録の記録(Bugzilla 1840432)と runner の信頼ストアの両方で一致を確認 |
| 2. 取得の仕組み | `sources.py`、`forward_run.py`(cftc-snapshot、fetch)、`forward_commit.py`(commit-data)、`snapshot_acq.py`、workflow `m1macro_forward.yml`、`m1macro_snapshot_acquire.yml` | CFTC の T_info より前の取得(00:40、02:40 JST)。米国債の原データは非公開のリポジトリにだけ置き、公開の側には treasury_raw_manifest.csv(Part 4 §8 の列)。財務省・CFTC の原データ、Release Schedule の HTML は公開の側に置く。正常性の検査(§1.1 の 1〜4)と、受け入れた日付の一覧(日付だけ)を記録 |
| 3. 過去の特徴量と E_{t,h} | `features.py`、`pipeline.py`、`estimation.py`、`s0link.reconstruct()` | 再構築の期間は、ECB の開発用 snapshot から M0 の台帳と S0 の出力を作り直し、Freeze 済みの SHA-256(e4edb850…、98e94866…)とバイトで一致することを確かめ、**その同じ S0 の実行から pool を取り出す**(別の経路で pool を作らない。むすび 22:51)。E_INPUT_V1 は Part 4 §2.3 のとおり |
| 4. 状態・予測・台帳と G4 | `ledger_tx.py`、`gitrepo.py`、`forward_run.py`(compute)、`forward_commit.py`(commit-tx) | Part 4 §3 の 9 手順。G4 は、メモリ上の試験に加えて、**一時的な git のリポジトリ**(bare の remote と pre-receive hook で push を拒否させる)で、手順 4・5・7・8・9 の失敗、締め切りの直前・直後・ちょうど、COMPLETE の重複を試験 |
| 5. G5〜G9 の実行 | `gates.py`、workflow `m1macro_gates.yml` | 出力は許可した欄の一覧(allow-list)に通したものだけ。例外は型の名前だけを記録。コンテナの stdout/stderr は捨てる。G7 の2回の実行のハッシュはコンテナの外に出さず、一致の件数だけを出す |

ほかに: `manifest.py`(CODE_MANIFEST_V1 と Code_SHA256。対象のファイルの集合を固定)、`schema.py`(台帳の列の順序)。

## 2. 開発中に見つけて直したこと(数値・実装の問題だけ。モデル・変換・取得元は変えていない)

1. **CFTC 2006〜2016 のファイルの数の書き方**: 建玉の数が `30369.000000` の形。整数であることを確かめてから整数にする(小数部が 0 でなければ読み取りの失敗)。
2. **米国債の読み取り**: 同じ日付が2回あるときの検査が、代入の後に比べていたため働いていなかった。代入の前に比べるように直した。
3. **独立の実装が Part 2 §10 の基準 1 を自分では満たしていなかった**: 群 12000・pool 6000 の合成データで、独立の実装の UB − LB が 3〜9 × 10⁻¹³(浮動小数点の線形計画の下界の精度で止まっていた)。独立の実装に、自分のコード(Cramer の公式と正確な双対の確認)で下界を正確に証明する段を加えた。結果: 5.4 × 10⁻¹⁴ と 7.6 × 10⁻¹⁴、反復 40〜41 回。G3 と G6 の合否に「独立の実装の UB − LB ≤ ε_tie」を加えた(以前の開発の G3 はこれを見ていなかった)。本番の実装は変えていない。
4. **PRE_LISTING の行の Last_Available_Fix が空**: (t, h) の LAF をペアの間で比べるとき、空の行を除くようにした。

## 3. candidate を固定する前に、むすびの判断が必要なこと

### D1. 開発用 snapshot の取得(Impl Part 1 §6「1回だけ」)を、今行ってよいか

- 取得するもの: 米国債の全年のファイル(1990〜2026 の 37 ファイル。非公開の側だけ)、財務省(jgbcm_all.csv、jgbcm.csv)、CFTC(fin_fut_txt_2006_2016.zip、fut_fin_txt_2017〜2026.zip)。
- 取得の前の確認(check モード。原データはどこにも保存せず、日付の範囲と件数だけ): 50 ファイルすべて取得と読み取りに成功。米国債 1990-01-02〜2026-10-16、財務省 1974-09-24〜2026-10-15、CFTC の日本円の報告 2006-06-13〜2026-10-13、建玉の欠けや 0 はなし。
- 保存の先: 公開の側 `data/m1macro/dev_snapshot/`(manifest.json に各ファイルの SHA-256)、非公開の側 `m1macro_dev_snapshot/treasury/`。公開の treasury_raw_manifest.csv に Private_Commit を記録。非公開の側は新しく clone して SHA-256 を読み戻して確かめる。
- 今行う理由: G5〜G8 にはこの snapshot が要る。candidate を固定する前に、**開発の盲検の実行**(Impl Part 2 §11 の 2、承認済み)で数値の問題を見つけておくと、候補の作り直しと G1 からのやり直しを減らせる。snapshot のバイト列はコードではないので Code_SHA256 には入らず、実装の Freeze の記録(Part 4 §4)に各ファイルの SHA-256 を書く。
- 取得は「1回だけ」なので、取得の workflow(`m1macro_snapshot_acquire.yml`、branch `m1macro-acquire` への push でだけ動く)は、むすびの承認の後に1回だけ動かす。

### D2. 最初の Forward の Origin(Part 3 §2「実装の Freeze の時点で config に固定」)

config は Code_SHA256 の対象なので、candidate を固定する時点で値を書く必要があるが、値は「Freeze の commit の時刻より後の最初の予定された Origin」で、Freeze の時刻にしか決まらない。

- 案 (a)(推奨): candidate の config に、予定する Freeze の日より後の具体的な日付を Horizon ごとに書く。Freeze の commit は、その Origin の T_info(03:00 JST)より前、かつ CFTC の T_info より前の取得(前日の 00:40 JST)が main で動き始める前に行う。間に合わなければ、日付を変えた新しい candidate にする(G1 からやり直し)。
- 案 (b): コードが Freeze の記録の commit の時刻から規則で決める。仕様の文言(config に固定)からは外れる。
- 現在の実装: config の `first_forward_origin` を読む。値がなければ compute は何もしない(REFUSED_NOT_FROZEN)。

### D3. Forward の E に入れる実現値の行

正式の Outcome の台帳から、`Outcome_Status = OBSERVED`、`Target_End ≤ LAF_t`、**かつ `Recorded_At_UTC ≤ T_info(t)`** の行だけを使う。最後の条件は、同じ (t, h) を後で組み立て直したときに E_Input_SHA256 が一致するため(Part 3 §8 の 4)と、T_info を情報の締め切りとする原則のため。T_info の後に記録された実現値は、その t の E に入らない(次の t で入る)。

### D4. Forward の E に入れる特徴量の行

COMPLETE の行がある Run の特徴量の行を使い、ON_TIME は求めない(LATE の Run の特徴量も、Origin i の時点で記録した値であることは変わらないため)。UNCOMMITTED の行は使わない。ON_TIME も求めるべきなら変える。

### D5. CFTC の Release Schedule のページの年

公式のページは1年分だけを載せる。T_info の米国東部の年とページの年が同じときだけ使い、違えば ABSTAIN_SYSTEM(CFTC_RELEASE_SCHEDULE_UNAVAILABLE)にする。年の変わり目に、CFTC が新しい年のページを出すまでの間、F_POS は止まる可能性がある(安全側)。

### D6. Forward の Origin の S0 の pool

Forward の過去の Origin i の pool は、Freeze 済みの S0 のコードを、S0 の実行が保存した `data/ecb/eurofxref-hist.csv` を LAF_t までに切ったものに走らせて作り直し、台帳の S0 の行(Pool_N、Mean_Z、Q10_Z、Q90_Z、Decision_Class)と一致することを確かめてから使う。一致しなければ PIPELINE_FAILURE。

### D7. 米国債の元の値の文字列

Freeze 済みの Part 3 §6.1 は、特徴量の台帳(公開)に元の値の文字列(y(v)、y(v−20))を書くと定めている。1 Origin あたり2つの値。仕様どおりにする。ただし G5 の公開の出力(再構築の期間のすべての Origin の表)では、米国債の元の値の欄を `PRIVATE_SOURCE` に置き換えた(原データをまとめて再配布しないため)。

### D8. 締め切りまでに発行できなかった Origin の行

既存の Forward 台帳と同じく、締め切りを過ぎても COMPLETE の行がない (t, h) には、ABSTAIN_SYSTEM(NOT_ISSUED、当日なら LATE_ISSUE)の予測の行を transaction で書く。1回の実行で複数の Origin を書くときの Run_ID は `<実行の ID>-<番号>`。これらの締め切りの記録は、作り方から LATE になる。確認的な評価は、COMPLETE かつ ON_TIME の行がない (p, t, h) を ABSTAIN_SYSTEM として扱うので、結果は変わらない。

### D9. どこで何を動かすか

- 数値の計算(特徴量、E、推定、予測の値)は、固定したコンテナのイメージの中で動かす。git と token は使わない。
- 台帳への書き込み(commit-data、commit-tx)は runner の上で、標準ライブラリだけで動かす(数値の計算はしない)。コンテナのイメージには git がない。
- 一時的な git のリポジトリを使う試験(G4)だけ、試験のコンテナに git を入れて動かす。本番のコンテナには入れない。

### D10. Code_SHA256 の対象のファイル

`m1macro/` のすべての .py、config、certs、fixtures、`env/` の4つのファイル、Freeze 済みの M0・ORIGIN_TARGET_MAP・S0 のモジュール、`forward/ledger_builder.py`、ECB の開発用 snapshot(tests/fixtures)、`.github/workflows/m1macro_*.yml`。一覧は `m1macro/manifest.py` の PATTERNS に固定した。

### D11. G6〜G8 の実行の方法

20 に分けた並列の job で、各 job が同じコンテナの中で、実行 A(本番と独立の実装、G8)と実行 B(本番だけ、最初から)を走らせる。G7 は各 job の中で A と B のハッシュを比べ、件数だけを出す。G6 の記録の欄: t、h、状態、subreason、反復の数、UB − LB、Φ(β₂) − LB、独立の実装の方法・反復・UB − LB、差の大きさ(d_UB、‖Δβ‖∞、max |Δμ| / σ)、合否、例外の型の名前、時間。β、μ、UB(= J*)の値は出さない。

## 4. この後の順序(提案)

1. D1〜D11 についての、むすびの判断。
2. (D1 が承認されたら)開発用 snapshot を1回だけ取得する。
3. 開発の盲検の実行(G5〜G8 と同じ形。正式の関門ではない)で、数値の問題がないかを見る。出力は許可した欄だけ。
4. 数値の問題があれば直す(Impl Part 2 §11 の範囲だけ)。最初の Forward の Origin を config に書く(D2)。
5. candidate を固定する(CODE_MANIFEST_V1 → Code_SHA256)。全体をむすびが監査する。
6. 同じ Code_SHA256 で、正式の G1〜G9 を branch `m1macro-gates` で走らせる。
7. 実装の Freeze の記録 → main への取り込み → 封印を開ける記録。
