# IMPL-FINDINGS-04 — IMPL-FINDINGS-03 修正仕様(D8・D10・D2)の実装結果、取得済み snapshot の検証、hard stop 1件

- 作成: Claude、2026-10-18(JST)
- 対象のコード: branch `m1macro-dev`、commit `5a10458`(candidate ではない。Code_SHA256 は固定していない。開発の値は b4e54d58…)
- 根拠の仕様: IMPL-FINDINGS-03 修正仕様(D8・D10・D2)、むすび最終監査 PASS / CLOSED(2026-10-18)
- 封印: 実データで β、β の符号、μ、J*、CRPS、予測、M1 と S0 の差は計算していない。今回見たのは、snapshot のファイルの SHA-256、バイト数、件数、commit の記録だけ。
- 状態: D1〜D11 ALL CLOSED / candidate Freeze NOT YET / Code_SHA256 NOT FROZEN / Formal G1〜G9 NOT STARTED / Performance Seal INTACT / Historical Reserve Holdout SEALED

## 結論

1. D8・D10・D2 を実装した。開発の試験は固定したコンテナで 21 項目すべて PASS(run 39049555087)。
2. one-shot snapshot は、**この作業の前に、すでに1回だけ取得されていた**(10/18 00:29 JST、run 39045282957)。今回は取得を行っていない。fresh reread で 50 ファイルすべての SHA-256 とバイト数が一致した。
3. **hard stop ③ に該当**: Freeze の時刻を記録する、監査可能な仕組み(push・reread の後に確定する Recorded_At_UTC)は、リポジトリにまだ存在しない。既存の Freeze registry の時刻は git の committer の時刻(手元で設定できる値)である。代替の方式は決めていない。むすびの判断を求める(§4 F1)。

## ① D8・D10・D2 の実装結果

| 項目 | ファイル(m1macro/) | 内容 | 試験 |
|---|---|---|---|
| D8 Option B | `deadline_gate.py`、`forward_commit.py`、`forward_run.py` | NOT_ISSUED の判定を「締め切りの時点で ON_TIME の COMPLETE がない」に変えた(以前の f0606fb は「COMPLETE がない」で判定していたため、LATE の COMPLETE が先にあると NOT_ISSUED が書かれなかった)。後刻の COMPLETE は LATE としてだけ成立する。予測の行は書かない | `test_deadline_gate` PASS |
| D10 | `manifest_gate.py`、`m1macro_gates.yml` | 生成された CODE_MANIFEST_V1 そのものを検査。必須5件(manifest.py、この Gate、指定の workflow 3件)と、集合の一致 {リポジトリの m1macro_*.yml} = {manifest の workflow}。各項目の SHA-256 も照合 | `test_manifest_gate` PASS |
| D2 | `freeze_gate.py`、`m1macro_gates.yml` | Pre-Freeze Gate を gates の suite に組み込んだ(main の取得・台帳の行を読む)。Freeze-finalization Gate は関数だけ(§4 F1) | `test_freeze_gate` PASS |

**D8 の Gate(すべて fail-closed)**

- `commit-tx` の前に、同期した tree で `deadline_gate.check()`。違反があれば何も書かずに停止(DEADLINE_AUDIT_GATE_PRE)。
- 書き込みの後に、remote を読み直して同じ検査と、監査のファイルが実行前のバイト列をそのまま先頭に持つこと(追記だけ)を確かめる(DEADLINE_AUDIT_GATE_POST)。
- Forward の workflow で、`commit-tx` の前に監査のファイルの git の全履歴が追記だけであることを確かめる(`deadline_gate.py history`)。仕様の「行の hash を過去 run と照合」を、バイト列の先頭一致で実装した(行の hash の照合より強い)。
- 検査の項目: NOT_ISSUED の後の ON_TIME、NOT_ISSUED の重複、NOT_ISSUED の行の形(時刻の欄が空、Deadline_UTC が Origin の 08:30 JST)、予測の台帳の NOT_ISSUED・LATE_ISSUE の行、Deadline_Status と Verified_At_UTC の整合、COMPLETE のない監査の行、同じ (Origin, Horizon) の二重発行。
- 一時的な git のリポジトリでの試験: NOT_ISSUED → 後刻 COMPLETE/LATE は PASS(NOT_ISSUED の行は不変、official_run_ids は空)。逆の順序(LATE の COMPLETE が先)でも NOT_ISSUED が書かれる。時計を締め切り前にして ON_TIME を作ると POST で停止し、その後のすべての実行が PRE で停止する。

**D10 の独立性**: manifest_gate は manifest.py と canon.py を import しない。リポジトリの側は `os.scandir` と名前の規則で数え、manifest は自前で解析し、SHA-256 も自前で計算する。試験で、manifest.py の PATTERNS から workflow を外した状態で manifest を生成すると、Gate が FAIL することを確かめた。現在の manifest は 69 件、workflow 4件(dev、forward、gates、snapshot_acquire)で PASS。

**D2 の現状**: config の first_forward_origin がまだ空なので、Pre-Freeze Gate は FIRST_FORWARD_ORIGIN_NOT_SET で FAIL する(この段階では想定どおり)。

## ② snapshot の一回性・immutable 化・fresh reread

| 確認 | 結果 | 証拠 |
|---|---|---|
| 取得の実行 | 1回だけ | workflow `m1macro-dev-snapshot-acquire` の実行の記録は run 39045282957 の1件だけ(2026-10-17T15:29:42Z 開始、成功、branch m1macro-acquire、commit f0606fb、event push) |
| 書き込み(公開の側) | 1回だけ | main で `data/m1macro/` を変えた commit は 8ed83c2(2026-10-17T15:41:43Z)の1件だけ。main の HEAD は 8ed83c2 のまま |
| 書き込み(非公開の側) | 1回だけ | fx-ledger-private-raw で `m1macro_dev_snapshot/` を変えた commit は f424840(15:41:40Z、メッセージに run 39045282957)の1件だけ。リポジトリの commit は全部で2件(もう1件は以前の接続の試験) |
| fresh reread(公開) | 13 / 13 一致 | 新しく clone した main の git object から、MOF 2件・CFTC 11件の SHA-256 とバイト数を計算し、manifest.json と照合。manifest.json の SHA-256 は 310e8475…2769 |
| fresh reread(非公開) | 37 / 37 一致 | 新しく clone した非公開のリポジトリの commit f424840 から、米国債 37 件の SHA-256 とバイト数を照合。ディレクトリに余分なファイルはない |
| 公開の treasury_raw_manifest.csv | 37 / 37 一致 | URL、取得時刻、バイト数、SHA-256 が manifest.json と一致。Private_Commit はすべて f424840 |

取得は、もう一方の作業(Claude、session 013SB…)が、むすびの D1 の承認を受けて行った。今回の作業(session 01SF2…)は取得の workflow を動かしていない。

**残っている危険**: branch `m1macro-acquire`(f0606fb)が残っている。この branch に push すると、取得の workflow がもう一度動く。削除するか、保護の設定をするかの判断を求める(§4 F4)。

## ③ Recorded_At_UTC の実体(hard stop)

- 既存の Freeze registry(`preregistration/registry.csv`)の列は Spec_ID、Spec_SHA256、Freeze_Date_JST、Freeze_Commit、Commit_Time、Note。**Recorded_At_UTC の列はない。**
- Commit_Time は git の committer の時刻と一致する(例: 555cb66 → 2026-10-16T14:27:04+09:00、00f3609 → 2026-10-17T16:26:37+09:00)。この時刻は、commit を作る側が自由に設定できる(GIT_COMMITTER_DATE など)。これまでの Freeze の commit は、Claude の作業環境で作られている。
- 各 `*.freeze.json` には時刻の欄がない。
- 実装の Freeze の記録(`preregistration/M1-MACRO-IMPL-CODE-V1.freeze.json`、Impl Part 4 §4)は、まだ存在しない。それを書く workflow や transaction もない。
- 台帳の transaction の Verified_At_UTC(ledger_tx.py の手順 8)は、GitHub の runner の時計で、push と reread の後に記録される。ただし、これは発行のための仕組みで、Freeze の記録には使われていない。

したがって「既存の Freeze registry で採用している、push/reread 後に確定する監査可能な記録時刻」は、実体がない。むすびの指示どおり、ここで止めた。

## ④ 新しい Finding

### F1(hard stop、判断が必要): Freeze の記録の時刻の出どころ

T_freeze_recorded の正規の出どころを決める必要がある。参考として、考えられる形を挙げる(どれも実装していない)。

- (a) Freeze の記録を書く専用の workflow(GitHub Actions)。runner の時計で push・reread の後の時刻を Recorded_At_UTC として記録し、その run の ID も記録する。run の開始時刻は GitHub のサーバーが付ける値で、公開のリポジトリなら誰でも API で照合できる。
- (b) (a) に加えて、Recorded_At_UTC が、その run のサーバー側の開始時刻以上で、かつ記録の commit を読み直した時刻以下であることを Gate で確かめる。
- (c) 外部の時刻証明(RFC 3161 の時刻認証局など)。外部の通信と、新しい依存が増える。

### F2(確認を求める): A_first(h) の定義

A_first(h) = T_info(first(h)) − 6 時間(前日の 21:00 JST)とした。本番の CFTC の選択の規則が、取得の時刻が (T_info − 6 時間, T_info] のものをその Origin に属するとしているため、「属する取得が起こりうる最も早い時刻」はこの値になる。予定の 00:40 JST より早いので、安全側である。6 時間は `cftc_feature.WINDOW`(config の cftc_snapshot_window_hours と同じ)から取り、手で入力していない。00:40 JST(予定の時刻)を境界にすべきなら変える。

### F3(報告): D8 の判定の単位と、混ざった状態

- 監査の記録の列(Freeze 済みの Part 4 §3)には Horizon がないので、NOT_ISSUED は Origin ごとの1行である。どの Horizon が欠けたかは、Freeze 済みの ORIGIN_TARGET_MAP と COMPLETE の行から一意に決まる。
- 1回の transaction は、その Origin の期限内のすべての Horizon をまとめて発行する。したがって、同じ Origin で ON_TIME の Horizon と欠けた Horizon が混ざる状態は、作り方から起こらない。もし起これば PARTIAL_ISSUANCE で停止する。

### F4(判断が必要): 取得の branch の扱い

branch `m1macro-acquire` を削除する(run の記録には commit f0606fb が残る)か、残して保護するか。

### F5(判断が必要): F1 が閉じるまでの進め方

D2 の Freeze-finalization Gate は F1 に依存するが、開発の盲検の実行(G5〜G8)は Freeze の時刻に依存しない。F1 の判断を待つ間に、開発の盲検の実行に進んでよいか。
