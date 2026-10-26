# M1-MACRO-PIPELINE-V2 Implementation Spec — Part 1: Acquisition / Trigger(DRAFT v0.3 — Freeze Candidate)

- 状態: **DRAFT v0.3 — FREEZE CANDIDATE**(Claude、2026-10-26)。むすびさんの Part 1 最終 Freeze 監査待ち。**まだ Freeze していない。**
- 前の版: v0(blob 76b0b6be…)、v0.1(blob d63a7862…)、v0.2(blob ce268470…)。どれも書き換えずに残してある。
- **v0.2 からの変更(closure 版)**: むすびさんの判断(2026-10-26 22:56 JST、v0.2 = FREEZE CANDIDATE REVIEW PASS)により、**状態のラベルだけ**を更新した。設計・規則・数値・fixture は v0.2 から一字も変えていない。変えたのは、この見出しと状態の行、§11 の F-P1-1・F-P1-7・F-P1-10 の状態の欄、§12 だけである。
  - F-P1-1 = ACCEPT / CLOSE、F-P1-7 = ACCEPT / CLOSE、OPS-FORWARD-03 = AUDIT PASS / PREREGISTRATION ACCEPTED、Part 1 = FREEZE CANDIDATE。
- v0.1 から v0.2 への変更: むすびさんの判断(2026-10-26 22:25 JST、Part 1 v0.1 = REVIEW PASS WITH REVISIONS)を反映した。新しい設計は広げていない。
  1. **F-P1-1(CONFIRMED / RULE REFINEMENT REQUIRED BEFORE CLOSE)**: k̂(t) を **Source_Year を決めるためだけ**の値に限定した。Report_Date を生成・予測する正式なモデルではない。TABLE_USABLE を最優先にし、Source_Year が**一意に決まる場合だけ**使う。一意性は「狭い候補」と「広い候補」の 2 つの集合で年が一致することと定義し、一致しなければ SOURCE_YEAR_UNDETERMINED とした。取得の後に Report_Date を補正しない。120 日の探索の範囲は採用(§8.1)。
  2. **F-P1-7**: 同じ Retrieved_At_Runner の tie-break を、V2 main の履歴の順から、artifact に固有の値(Content_SHA256 の辞書順の最大、次に Manifest_SHA256)に変えた(§8.6)。
  3. **FX-Y8 を追加した**(§8.7)。FX-Y3 の期待値を、一意性の規則に合わせて改めた。
  4. 決定を記録した: F-P1-2・F-P1-4(上限 1 回)・F-P1-6・F-P1-9 の採用、A・C の取得の時刻、Part 2→3→4 の順(§11、§12)。
  5. **F-P1-10** は V1 OPERATIONAL FINDING / FROZEN-BEHAVIOR LIMITATION とし、KNOWN UPCOMING RISK WINDOW として OPS-FORWARD に事前登録する(別の記録 drafts/OPS-FORWARD-03.md。この Part の本文は変えない)。
- v0 から v0.1 への変更の経緯は、v0.1 の冒頭を参照。
- 前提(Freeze 済み): **M1-MACRO-PIPELINE-V2-REQUIREMENTS-V0.7**(preregistration/、SHA-256 edf27751…、blob 21cb5c13…、Freeze commit b2571b79…)。以下「Requirements」。
- この Part の範囲: A・C の経路、Target_Origin、取得の実行、CFTC の取得、03:15〜03:20 の acquisition decision の transaction。
- ほかの Part(予定):
  - Part 2 — Provenance / Clock / Anchor(正規の manifest、PRE の記録、R1・R2、G、時計の区間、Content / Manifest の SHA、server anchor)
  - Part 3 — Parent / Issuance(V1 の S0 の read-only の検証、10 回の attempt、idempotency、COMPLETE の transaction、08:30 の締め切り)
  - Part 4 — Adjudication / Acceptance / Audit(08:45〜09:15 の adjudication、各 Gate、監査の証拠の決定論的な再生、fail-closed の状態の写像)
- **この Part は Requirements を再設計しない。** Requirements で決まった数値・Gate・状態を、どの関数・状態・artifact・transaction が実現するかに落とす。Requirements と食い違う点や、Requirements が決めていない実装上の選択は、§11 に Finding として分けて書く。Requirements の文言は変えない。
- 置き場所: この草案は V1 の repository の drafts/ に置く(決定、2026-10-26)。V2 の実装は、V1 とは別の repository(以下「V2 repository」)に置く(Requirements §2)。V2 repository はまだ作っていない。
- このメモではしないこと: V1 の workflow・code・config・data・ledger の変更、V2 の取得の実行、較正と試験の開始、Development Replay、Holdout の計算。

---

## 1. Requirements との対応(この Part が実現するもの)

| Requirements | 内容 | この Part の実現箇所 |
|---|---|---|
| §3.1 | 窓 (T_info − 6h, T_info]、最も遅い使える snapshot | §8.6(選択)、§9.4(判定) |
| §3.2 | Target_Origin、Acquisition_Path_ID、Execution_ID、Retrieved_At_Runner | §4、§5.3、§6.4、§7.2 |
| §3.3 | Acquisition_Manifest | 作るのは §7.2 の手順の中。形と正規化は Part 2 |
| §3.4 | USABLE の 6 条件 | 判定の順序は §9.4。各条件の中身は Part 2 |
| §5 | A・C の主候補 | §5(A)、§6(C) |
| §6.1〜§6.3 | 試験窓、Target_Origin での帰属、7 段階の検査、窓の SUCCESS / FAILURE と原因コード | §9.4 |
| §6.4 | 03:15 開始可能、03:20 期限、A・C から起動、idempotent、canonical、server 側の COMPLETE 時刻、救済しない | §9 |
| §7.1 の 1・3・5 | V1 に V2 の行がない、全経路が Code_SHA の対象、V1 への書き込み権限がない | §3、§6.3 |
| §7.4 | 強制 failover の窓で経路を止める | §10 |
| §10.3 | Clock_Check_Pre と Post | 呼び出す位置だけ §7.2。中身は Part 2 |

## 2. 用語

- **trigger**: 取得や判定の job を起動するもの。A は GitHub Actions の schedule、C は GitHub の外の scheduler(§6)。
- **attempt**: 1 回の取得の実行。1 つの Target_Origin に属し、1 つの Acquisition_Manifest を作る(作る前に失敗した場合は §7.4)。
- **decision**: 1 つの Origin について、03:15〜03:20 に acquisition state を確定する transaction(§9)。
- **V2 main**: V2 repository の正式の branch。force push と削除を禁止する(Requirements §9.2)。

## 3. V2 repository のうち、この Part に関わる部分

V2 repository の具体的な名前と全体の構成は、実装の段階で決める。この Part が前提にするのは次の点だけである。

| パス(V2 repository の中) | 中身 | 書き方 |
|---|---|---|
| `data/cftc/<YYYY>/<Target_Origin>/<Execution_ID>.zip` | 取得した原ファイル(CFTC は public domain) | 追記のみ。上書きしない |
| `records/acquisition/<Target_Origin>/<Execution_ID>/manifest.json` | Acquisition_Manifest(Part 2 の正規のバイト列) | 追記のみ |
| `records/acquisition/<Target_Origin>/<Execution_ID>/pre.json` | PRE の記録(Part 2) | 追記のみ |
| `records/acquisition/<Target_Origin>/<Execution_ID>/anchor/` | R1・R2 の token と証明書の鎖など(Part 2) | 追記のみ |
| `records/acquisition/attempts.csv` | attempt の台帳(§7.3) | 追記のみ |
| `records/acquisition/trigger_log.csv` | 起動の記録(§5.4、§6.4、§7.4) | 追記のみ |
| `records/acquisition/accepted_dates/` | 中身の検査に通った snapshot の日付の一覧(§8.5) | 追記のみ |
| `records/decision/decisions.csv` | decision の台帳(§9.5) | 追記のみ |
| `config/v2_config.json` | §4〜§10 の固定値(Code_SHA の対象) | 変更は新しい Code_SHA |

- V2 のどの credential も、V1 の repository への書き込みの権限を持たない(Requirements §7.1 の 5)。V1 から読むものは、Origin の暦の参照実装(§4.1)と、Part 3 の S0 の行だけである。この Part では V1 の data/ と ledger/ は読まない。
- 実装のコード、config、証明書、container の image digest、workflow は、すべて V2 の Code_SHA の対象にする(Requirements §7.1 の 3)。Code_SHA の作り方は V1 の CODE_MANIFEST_V1 と同じ考え方にし、詳細は Part 4 で決める。

## 4. Origin の暦と Target_Origin

### 4.1 Origin の暦

- Origin とその Horizon は、Freeze 済みの ORIGIN_TARGET_MAP_V1(V1 の frozen/origin_target_map_v1.py、V1 の CODE_MANIFEST_V1 の対象)の `is_formal_origin(date, horizon)` で決める。1D は TARGET の公表日、1W・4W は毎週日曜である。
- V2 は、このファイルを**バイト単位で同じコピー**として V2 repository に置き、V2 の Code_SHA の対象にする。コピーの SHA-256 が V1 の CODE_MANIFEST_V1 に記録された値と一致することを、起動時に確かめる。一致しなければ、その job は何もせずに失敗する(PROVENANCE_INVALID の扱いではなく、起動の失敗として §7.4 の trigger_log に記録する)。
- 試験窓は、1 つ以上の Horizon を持つ Origin の日ごとに 1 つ(Requirements §6.1、§6.5)。
- T_info(t) = Origin t の日の 03:00:00 JST(Requirements §3.1。V1 の Data Availability Matrix と同じ)。

### 4.2 Target_Origin の決め方

- Target_Origin は、**起動の時点で決め、attempt の中では変えない**。manifest と PRE の記録に書く(Requirements §3.2、§10.3)。
- 試験窓への帰属は Target_Origin で決め、取得の時刻では決めない(Requirements §6.1)。
- 決め方は経路ごとに違う(A は §5.3、C は §6.4)。どちらの場合も、決めた Target_Origin が §4.1 の暦にない場合は、取得をせずに trigger_log に NOT_AN_ORIGIN と記録して終わる。

## 5. A 経路(GitHub Actions の schedule)

### 5.1 位置づけ

- A は、V2 repository の GitHub Actions の schedule で起動する。Requirements §5 の「GitHub の中で、早い時刻に何度も起動する」案である。
- F14-a のとおり、GitHub の schedule は遅れたり起動しなかったりする。A だけに頼らないために C を置く(§6)。

### 5.2 起動の時刻(案)

```
cron(UTC)        JST
5 12 * * *       21:05
5 13 * * *       22:05
5 14 * * *       23:05
5 15 * * *       00:05(翌日)
5 16 * * *       01:05(翌日)
```

- 窓は前日の 12:00Z〜18:00Z(21:00〜03:00 JST)である。V1 で観測した遅れ(約 2〜3 時間)があっても、早い時刻の起動の多くが窓の中に入るように、窓の前半に寄せる。
- **早く取得しても中身は変わらない。** CFTC の公表は金曜 15:30 ET(19:30Z または 20:30Z)で、窓(12:00Z〜18:00Z)の中に公表が入ることはない。窓の中のどの時刻の snapshot も、同じ報告を含む。窓の中の最も遅いものを使う規則(§3.1)はそのまま守る。
- 時刻は config に固定し、Code_SHA の対象にする。試験の telemetry を見てから変えない。

### 5.3 A の Target_Origin

- GitHub の schedule の event は、どの cron で起動したか(`github.event.schedule` の cron の文字列)を渡すが、予定の日付は渡さない。そこで次の規則で決める。
  1. 起動した cron の文字列から、**job の開始時刻(runner の時計)以前で最も新しい、その cron の予定時刻** S を求める。
  2. S を含む窓 (T_info(t) − 6h, T_info(t)] を持つ Origin t を Target_Origin とする。S がどの Origin の窓にも入らない場合は NOT_AN_ORIGIN。
- この規則は、遅れが 24 時間より短ければ、予定どおりの Origin を指す。遅れて T_info を過ぎてから起動した場合も、Target_Origin は予定の Origin のままなので、その取得は予定の Origin の窓の外として記録される(§7.4)。
- 遅れが 24 時間以上になると、1 日後の Origin を指してしまう。これを避けるため、job の開始時刻と S の差が 20 時間を超えたら、取得をせずに trigger_log に TRIGGER_TOO_LATE と記録して終わる(案。§11 の F-P1-4)。

### 5.4 A の起動の記録

- A の job は、最初に trigger_log に 1 行を追記する(Path = A、cron の文字列、S、Target_Origin、Execution_ID = `A-<GitHub の run_id>-<run_attempt>`、job の開始時刻(runner の時計))。
- 予定したのに起動しなかった回は、記録が何も残らない。起動しなかった回は、予定の一覧と trigger_log の差として、Part 4 の集計で数える(較正では TRIGGER_NOT_STARTED、Requirements §10.6)。

## 6. C 経路(GitHub の外の trigger)— 候補の比較

C の実行環境は、この Part ではまだ決めない。むすびさんに選んでいただくために、要件と候補を比べる(決定、2026-10-26)。

### 6.1 C に求めること(Requirements から)

| # | 要件 | 根拠 |
|---|---|---|
| C-R1 | GitHub Actions の schedule に依存せずに起動する | Requirements §5、§6.4、§7.5(F14-a 型の単一障害点を避ける) |
| C-R2 | 取得、03:15〜03:20 の decision、08:45〜09:15 の adjudication、発行の attempt を起動できる | Requirements §6.4、§4.4、§7.5 |
| C-R3 | V2 の Code_SHA と同じコードで動く(取得の手順を A と変えない) | Requirements §7.1 の 3、§7.3 |
| C-R4 | V1 の repository への書き込みの権限を持たない。持つ権限は V2 repository への書き込みと、必要な外部への接続だけ | Requirements §7.1 の 5 |
| C-R5 | 時計は TSA で検査するので、実行環境の時計の精度そのものは要求しない。ただし RTT ≤ 2.0 秒で TSA に届くこと | Requirements §10.3、§10.6 |
| C-R6 | 実行の ID と起動の記録を残せる(X は補助の provenance) | Requirements §9.5 |
| C-R7 | 純さんの手元の機械の電源や接続に依存しない(03:15〜03:20、08:45〜09:15 に無人で動く) | Requirements §6.4、§7.5 |

### 6.2 候補

| 候補 | 起動 | 実行 | C-R1 | C-R3 | 主な注意点 |
|---|---|---|---|---|---|
| **C1. 外部の scheduler → GitHub の workflow_dispatch** | GitHub の外の scheduler が、V2 repository の workflow を API で起動する | GitHub の runner(A と同じ環境) | 起動は満たす。実行は GitHub に依存 | 満たしやすい(A と同じ workflow・同じ image) | GitHub の API や runner の障害は A と共通の故障の領域。scheduler に V2 repository の Actions を起動する token を置く |
| **C2. 外部の scheduler → 外部の container の実行** | GitHub の外の scheduler | GitHub の外の container の実行環境(A と同じ container の image digest) | 起動も実行も GitHub から独立 | 同じ image digest を使えば満たせる | 取得の結果を V2 repository に push する token を外部に置く。G の anchor は push の後に付くので GitHub に依存するが、R は独立 |
| **C3. 外部の軽量な関数の実行(container ではない)** | GitHub の外の scheduler | 言語の runtime が限られた関数の実行環境 | 満たす | **満たしにくい**(V1 と同じ pinned container を動かせない場合、取得の手順のコードが A と別物になる) | Code_SHA と決定論の要件を二重に管理することになる |
| **C4. 純さんの手元の PC のタスク スケジューラ** | 手元の PC | 手元の PC | 満たす | 満たせる | **C-R7 を満たさない**(電源・スリープ・接続)。03:15 や 08:45 の判定を任せられない |

- 具体的な事業者の製品(クラウドの scheduler と container の実行の組み合わせなど)の制限・料金・時刻の精度は、この版では調べていない。選ぶ前に、公式の資料で確かめる。
- C1 と C2 は排他ではない。

### 6.3 C2 の位置づけ(決定: Preferred Architecture Candidate)

- **C2 = Preferred Architecture Candidate とする。C2 を Freeze はしない**(むすびさんの判断、2026-10-26 17:04 JST)。
- C2 を正式に採用する前に、provider を選び、その環境で Requirements §10.6 の 7 日間の較正を A・C それぞれで通す必要がある。較正と Reliability の試験は同じ実行環境で行う。
- C2 を推す理由:
  1. 外部の scheduler と外部の container は、GitHub-hosted runner とは別の execution domain なので、C1 より F14-a に対する独立性が強い。
  2. A と同じ container の image digest を使えば、取得の手順のコードを 1 つに保てる(C-R3)。
- **GitHub への依存を 2 種類に分けて評価する。**

| 依存 | A | C1 | C2 |
|---|---|---|---|
| GitHub の scheduler / runner(起動と実行) | あり | 実行はあり | **なし** |
| GitHub への保存(V2 main への push、activity API) | あり | あり | **あり** |

  - C2 でも、取得の結果は V2 main に push しなければ attempt として数えない(§7.4)。また、decision は V2 main から attempt を読み、G の検証と COMPLETE の時刻は V2 の activity API による(Requirements §6.4、§9.2)。したがって、**GitHub への保存が止まっている間は、C2 でも窓は成立しない**。これは Requirements が server 側の時刻を V2 の activity API に置いたことの帰結であり、この Part では変えない。
  - C2 で確かめるべきなのは、GitHub の scheduler / runner が止まっている(F14-a 型)ときに、C2 だけで「取得 → TSA → V2 main への保存 → decision の起動 → canonical な decision」まで成立することである。GitHub の保存そのものが止まっている場合に成立しないことは、既知の限界として記録する(§11 の F-P1-11)。
- C2 を選ぶ場合も、push の credential は V2 repository だけに限る(fine-grained な token で、対象の repository を V2 だけにし、権限を contents の書き込みだけにする)。V1 の repository は public なので、読むのに token は要らない。
- 決めていただきたいのは、C1 / C2 / その組み合わせのどれにするか。具体的な製品の選定は、その後に別の記録で行う(§12 の 1)。

### 6.4 C の Target_Origin と起動の記録

- C は、起動のたびに、**予定の時刻 S と Target_Origin を起動の payload に入れて渡す**(A と違い、予定の日付を明示できる)。job は §5.3 と同じ規則で S から Target_Origin を計算し直し、payload の値と一致しなければ、取得をせずに trigger_log に TARGET_MISMATCH と記録して終わる。
- C の取得の起動の時刻(案): 21:35、23:35、01:35 JST。A と時刻をずらす。
- Execution_ID = `C-<実行環境の実行 ID>`。C2 の場合は、外部の実行環境の実行 ID を記録し、X(補助の provenance)としても保存する(Requirements §9.5)。
- 起動の記録は §5.4 と同じ形で trigger_log に追記する(Path = C)。

## 7. 取得の実行(attempt)

### 7.1 前提の確認(取得の前。失敗したら取得しない)

1. 動いているコードの Code_SHA が、V2 の実装の Freeze の記録の値と一致する(V1 の `_freeze_ok` と同じ考え方)。
2. §4.1 の暦のコピーの SHA-256 が一致する。
3. Target_Origin が決まり、§4.2 の検査に通る。
4. 経路が強制 failover で止められていない(§10)。

どれかに通らなければ、§7.4 の扱いにする。

### 7.2 手順(1 回の attempt)

```
 1. Clock_Check_Pre      PRE の記録を作り、R1・R2 に要求する                       [Part 2]
 2. CFTC の取得          §8 の手順。原ファイルのバイト列と Retrieved_At_Runner を得る [§8]
 3. Content_SHA256       原ファイルのバイト列の SHA-256                               [Part 2]
 4. 中身の検査           §8.4。結果は manifest に書く(USABLE の判定は §9 で行う)    [§8]
 5. Acquisition_Manifest manifest を作り、正規のバイト列と Manifest_SHA256 を得る     [Part 2]
 6. R の anchor          R1・R2 に Manifest_SHA256 を要求する(Clock_Check_Post を兼ねる)[Part 2]
 7. 保存と push          原ファイル、manifest、PRE、token などを 1 つの commit にし、V2 main に push [§7.3]
```

- 手順 1 から 6 の間に、窓や USABLE の判定はしない。判定は §9 の decision だけが行う。attempt は証拠を作って残すだけである。
- 手順 2 で取得に失敗しても、手順 5〜7 は行う(manifest に取得の失敗を書く)。これは「取得を試みたが失敗した」証拠を残し、Decision でこの attempt を PROVENANCE_INVALID や CONTENT_INVALID として数えられるようにするためである。
- 手順 7 の push が競合で拒否されたら、取り込み直して、自分の commit を載せ直して push する。載せ直しで中身は変えない(追記だけなので、他の commit と同じファイルを変えることはない)。push を 5 回試みて通らなければ、その attempt は push されないまま終わる(§7.4)。

### 7.3 attempt の台帳(`records/acquisition/attempts.csv`)

列(案): Execution_ID、Path、Target_Origin、Scheduled_At(S)、Job_Started_At_Runner、Retrieved_At_Runner、Fetch_Status(OK / FETCH_FAILED)、Content_Check(§8.4 の結果)、Content_SHA256、Manifest_SHA256、Manifest_Path、Pushed_Commit(push の後に分かるので空にし、§9 の decision が git の履歴から補う)。

- この台帳は便利のためのもので、判定の正本ではない。判定の正本は manifest と anchor の記録であり、§9 の decision は manifest から直接読む。台帳と manifest が食い違えば、PROVENANCE_INVALID の側に倒す(Part 2 の照合で検出する)。

### 7.4 取得をしなかった場合と、push されなかった場合

| 場合 | 記録 | Reliability での扱い |
|---|---|---|
| §7.1 の前提に通らない(Code_SHA、暦、Target_Origin、failover) | trigger_log に理由を 1 行(NOT_AN_ORIGIN、TRIGGER_TOO_LATE、TARGET_MISMATCH、CODE_SHA_MISMATCH、CALENDAR_MISMATCH、PATH_DISABLED_FAILOVER) | attempt ではないので、その窓の attempt の数に入らない。ほかに attempt がなければ NO_ACQUISITION(Requirements §6.3) |
| 取得したが、push が通らなかった | V2 main には何も残らない。runner に残った資料は、Part 4 の監査の記録として別に集める(正式の判定には使わない) | 判定の時点で V2 main にない attempt は存在しないものとして扱う。ほかになければ NO_ACQUISITION |
| T_info より後に起動した | §7.5 の上限の中なら diagnostic として取得して保存する。上限を超えたら trigger_log に LATE_DIAGNOSTIC_LIMIT_REACHED と記録して取得しない | USABLE にはならない(§7.5) |

- trigger_log の行は、attempt の帰属にも判定にも使わない。監査と、Requirements §10.6 の TRIGGER_NOT_STARTED の集計に使う。

### 7.5 T_info より後の取得(late diagnostic attempt)

- **位置づけ(決定)**: T_info より後に開始した取得は、実行して保存してよい。F14-a 型の事実(trigger は遅れたが、CFTC の取得そのものは成功した、など)を残すためである。ただし、**USABLE の候補にはしない**。真の取得の時刻の区間全体が (T_info − 6h, T_info] に入らなければ USABLE にならない(Requirements §3.4 の (3))ので、T_info より後に開始した取得は、formal な snapshot として救済できない。
- **上限(案。事前に固定する)**: 1 つの Target_Origin につき、**経路ごとに late diagnostic attempt は 1 回まで**とする。
  - 起動の時点で、job の開始時刻(runner の時計)が T_info(Target_Origin) より後なら late とみなす。この区分は TSA の要求の量を抑えるための運用上のもので、USABLE の判定には使わない(USABLE の判定は §9 の decision が TSA の時計の区間で行う)。
  - その経路のその Target_Origin で、すでに late diagnostic attempt が V2 main にあれば、取得をせずに trigger_log に LATE_DIAGNOSTIC_LIMIT_REACHED と記録して終わる。
  - 結果を見て追加の取得をすることは禁止する。late diagnostic attempt は、予定した起動(A は §5.2、C は §6.4)が遅れて起動した場合にだけ生じ、別の起動を足すことはしない。
  - TSA の要求の量への影響は、1 つの Origin につき最大で 2 回(A と C)× PRE と POST × 2 局 = 8 回の増加である。
- **原因コードへの影響**: late diagnostic attempt があると、それがなければ NO_ACQUISITION だった窓が OUTSIDE_WINDOW になることがある。これは Requirements §6.3 の原因コードの規則(最も先まで進んだ attempt のコードを主な原因とする)によるもので、**窓の SUCCESS / FAILURE と Reliability Gate への寄与は変わらない**(どちらも FAILURE 1 個)。
- 予定から 20 時間を超えて遅れた起動は、late diagnostic attempt としても取得しない(TRIGGER_TOO_LATE、§5.3)。

## 8. CFTC の取得

### 8.1 取得元と URL

- 取得元は V1 と同じ: CFTC の Historical Compressed の TFF Futures Only の年次ファイル(`fut_fin_txt_<YYYY>.zip`)。URL の組み立ては V1 の `sources.cftc_year_url` と同じ。
- **年 YYYY(CFTC_Source_Year)を runner の現在の時刻から直接決めることは禁止する**(F-P1-1、決定)。V2 で守るのは V1 の CFTC のデータの意味(T_info 以前の snapshot の中で、Usable_From ≤ T_info を満たす最新の報告を使う)であって、年越しのときの URL の組み立ての偶然の挙動ではない。
- 決める順序(決定):

```
scheduled slot S → Target_Origin t(§5.3、§6.4)→ T_info(t)
  → k̂_N(t)、k̂_B(t)(下の規則。Source_Year を決めるためだけの値)
  → CFTC_Source_Year(t) = 2 つの年が一致すればその年、しなければ SOURCE_YEAR_UNDETERMINED
  → URL = sources.cftc_year_url(CFTC_Source_Year(t))
```

- **k̂ の位置づけ(決定)**: k̂ は **CFTC_Source_Year を決めるためだけ**に使う。CFTC の Report_Date を生成・予測する正式なモデルではない。CFTC の公表は「通常」火曜日のデータを金曜 15:30 ET に出すが、休日などで変わり、公式の特別告知に例外がある(2020-12-21 の月曜日のデータなど)。したがって、どの一般の暦の規則も、Report_Date を完全には再現できない前提で扱う。
- **規則(V1 の凍結済みの関数だけを使う)**:

```
T(t)  = T_info(t) の日付 − 120 日 ≤ d ≤ T_info(t) の日付 で、
        V1 cftc_rules.usable_from(d) が None でなく、かつ ≤ T_info(t) である d の集合

狭い候補 N(d) ⇔ d が TABLE_USABLE の鍵にある(V1 cftc_rules。最優先)
              または d が火曜日で、CFTC の休日ではない(V1 uscal.is_cftc_holiday)
              または d が月曜日で、翌日の火曜日が CFTC の休日である
広い候補 B(d) ⇔ d が TABLE_USABLE の鍵にある
              または d が月曜日か火曜日である(休日かどうかを問わない)

k̂_N(t) = max{ d ∈ T(t) : N(d) }
k̂_B(t) = max{ d ∈ T(t) : B(d) }

year(k̂_N(t)) = year(k̂_B(t)) なら  CFTC_Source_Year(t) = その年
それ以外(どちらかが存在しない場合を含む)なら  SOURCE_YEAR_UNDETERMINED
```

  - **一意性の意味**: 広い候補は、2010-12〜2026-10 の実際の報告日をすべて含む(実際の報告日はすべて月曜日か火曜日だった。§8.7)。狭い候補は、通常の規則による最も確からしい報告日である。2 つの集合で年が一致すれば、実際の報告日がこの 2 つの規則のどちらに従っていても年は変わらない、とみなす。一致しなければ、年を推測しない。
  - **TABLE_USABLE を最優先**: TABLE_USABLE の鍵は、両方の集合に入れる。表にある報告日は、曜日の規則より先に候補になる。
  - SOURCE_YEAR_UNDETERMINED の場合、その attempt は取得をせずに trigger_log に SOURCE_YEAR_UNDETERMINED と記録して終わる。その窓に USABLE がなければ、Reliability では FAILURE(NO_ACQUISITION)になる。
  - **取得の後に補正しない**: 取ったファイルの中身(Report_Date の一覧)を見て、Source_Year や k̂ を直したり、別の年のファイルを取り直したりはしない。取ったファイルの中でどの報告を使うかは、V1 の cftc_feature の規則のまま決まる。
  - CFTC の年次ファイルには、その年の日付の Report_Date の報告だけが入っている(2017〜2026 の全ファイルで確認。§8.7)。したがって、Source_Year の年のファイルが、使える最新の報告を含むファイルである。
  - 探索の範囲は 120 日(決定)。
- CFTC_Source_Year は manifest と PRE の記録に書く。decision は manifest の CFTC_Source_Year を §8.1 の規則で計算し直し、一致しなければ PROVENANCE_INVALID とする。
- この規則で決まるのは**どのファイルを取るか**だけである。取ったファイルの中でどの報告を使うか、古さの判定(FEATURE_STALE)などは、V1 の cftc_feature の規則のまま変えない。

### 8.2 接続

- V1 Part 1 V1.2 §3 の transport implementation decision をそのまま使う。システムの CA の一覧を置き換えず、Sectigo Public Server Authentication Root R46 のルート証明書 1 つを加えて TLS を検証する。証明書のファイルを V2 の Code_SHA の対象にし、期待する指紋を config に固定して起動時に照合する。接続先は CFTC のホスト名に限る。検証を切らない。

### 8.3 取得と Retrieved_At_Runner

- 1 回の attempt の中の取得は、V1 と同じく最大 2 回(間隔 5 秒)試みる。
- **Retrieved_At_Runner は、応答の本文を受け取り終えた直後の runner の時計の UTC** とする(Requirements §3.2)。V1 の `sources.fetch` は秒に切り捨てて記録しているが、V2 では**マイクロ秒まで、切り捨てずに**記録する(§11 の F-P1-2)。形式は `YYYY-MM-DDTHH:MM:SS.ffffffZ`。
- HTTP の status が 200 でない、接続に失敗した、時間切れになった場合は Fetch_Status = FETCH_FAILED。本文の内容は記録しない(V1 と同じく、値の漏れを避ける)。

### 8.4 中身の検査(Requirements §6.2 の 2、CONTENT_INVALID)

V1 の `forward_run.cftc_snapshot` と同じ検査を、同じ順で行う。

1. `cftc_parse.parse_zip` で読める(読めなければ PARSE_FAILED)。
2. 報告が 1 件以上ある(なければ EMPTY)。
3. `rates.calendar_integrity(前回の受け入れた日付, 今回の日付)` が空(そうでなければ CALENDAR_INTEGRITY)。

- 結果は manifest に Content_Check として書く(OK / PARSE_FAILED / EMPTY / CALENDAR_INTEGRITY)。OK 以外は decision で CONTENT_INVALID になる。
- 使う関数(cftc_parse、rates の該当部分)は、V1 の Freeze 済みのファイルの**バイト単位で同じコピー**を V2 に置く。§4.1 と同じく、SHA-256 が V1 の CODE_MANIFEST_V1 の値と一致することを起動時に確かめる。

### 8.5 「前回の受け入れた日付」

- V2 は、V1 の data/ を読まない。前回の受け入れた日付は、**V2 repository の中で、同じ CFTC_Source_Year のファイルについて、検査 3 まで通った最後の snapshot**(窓の中かどうかは問わない)の日付の一覧とする(F-P1-9)。V1 の `_prev_accepted` と同じ考え方だが、年をまたいで比べない。
- その CFTC_Source_Year の最初の snapshot には前回がないので、検査 3 は通る。V1 の Forward の最初の取得と同じ扱いである(§11 の F-P1-3)。
- 「最後の」は、V2 main の git の履歴の順(push の順)で決める。runner の時計では決めない。

### 8.6 snapshot の選択

- 1 つの窓で USABLE な attempt が複数あれば、Retrieved_At_Runner が最も遅いものを使う(Requirements §6.3、V1 と同じ規則)。
- **tie-break(決定案。F-P1-7)**: Retrieved_At_Runner が同じ attempt が複数あれば、**Content_SHA256 の辞書順(16 進の小文字の文字列)で最大**のものを使う。それも同じなら(同じバイト列の取得)、**Manifest_SHA256 の辞書順で最大**のものを使う。Manifest_SHA256 は Execution_ID を含むので、異なる attempt で一致することはない。
  - V2 main への push の順や、A・C の競争の順には依存しない。
  - V1 の `cftc_feature.forward` も、同じ時刻の snapshot を `(retrieved_at_utc, sha256)` の最大で選んでおり、Content_SHA256 による tie-break は V1 の選び方と一致する。
- 選んだ snapshot の Execution_ID と Content_SHA256 を decision に書く(§9.5)。Part 3 の発行は、これだけを使う。

### 8.7 年越しの fixture(必須。実装の Freeze の前に通す)

**検証済みの事実(2026-10-26、Claude)**

V1 の開発用 snapshot の CFTC の年次ファイル(data/m1macro/dev_snapshot/cftc/、2017〜2026)から **Report_Date の日付だけ**を読み(建玉の値は読んでいない)、V1 の `cftc_rules.usable_from` と `uscal` で確かめた。時刻の換算には、作業用の環境の system の zoneinfo を使った(V1 の固定版の tzdata 2024.2 ではない。2011〜2026 の日付の範囲では、結果に影響する違いはないと考えるが、fixture は固定版の環境で実行し直す)。

1. 2017〜2026 の各年次ファイルで、すべての Report_Date の年がファイルの年と一致した。
2. 2010-12〜2026-10 の実際の報告日は、**すべて月曜日か火曜日**だった。
3. 狭い候補に当てはまらない実際の報告日が 2 件あった(2014-11-11 火曜で Veterans Day、2020-12-21 月曜)。どちらも広い候補には入る。
4. **v0.2 の一意性の規則を、2011-01-01〜2026-10-13 のすべての日(5,765 日)に当てはめた**:
   - 年が一意に決まり、実際のファイルにある使える最新の報告の年と一致: **5,761 日**
   - 年が一意に決まったが、実際と一致しない: **0 日**
   - SOURCE_YEAR_UNDETERMINED: **4 日**(2013-01-09〜01-12。2013-01-01 が火曜日の休日で、狭い候補では 2012-12-31 の月曜日、広い候補では 2013-01-01 の火曜日になり、年が分かれる。実際の報告日は 2012-12-31 だった)
5. 今後の年越し(12 月 20 日〜1 月 20 日): 2027・2028・2029 は SOURCE_YEAR_UNDETERMINED が 0 日。**2030 は 2030-01-09〜01-12 の 4 日**(2030-01-01 が火曜日)。この 4 日は、fail-closed のために V2 では FAILURE になりうる既知の費用である。
6. v0.1 の規則(狭い候補だけ)では、2013-01-09〜12 も年が決まり、結果は正しかった。v0.2 の規則は、それを UNDETERMINED に変える。正しく決まっていた日を捨てる代わりに、狭い候補の規則が外れた場合に誤った年のファイルを取ることを防ぐ。

**fixture(必須)**

| # | 内容 | 期待 |
|---|---|---|
| FX-Y1 | 2011〜2026 の各年の 12 月 20 日〜1 月 20 日のすべての Origin | §8.1 で年が決まった Origin では、開発用 snapshot の実際の使える最新の報告の年と一致する。決まらない Origin は FX-Y3 のとおり |
| FX-Y2 | 12 月 31 日 → 1 月 1 日をまたぐ取得(Target_Origin が 1 月 1 日の窓で、12 月 31 日 21:05 JST と 1 月 1 日 00:05 JST に起動) | 2 つの attempt の CFTC_Source_Year が同じ(runner の現在の年に依存しない) |
| FX-Y3 | 1 月 1 日が火曜日の年 | 2013-01-09〜01-12 と 2030-01-09〜01-12 は SOURCE_YEAR_UNDETERMINED。2019 年は 2018-12-24〜2019-03-05 の除外の期間にかかるため、2019-01 の Origin の年は 2018(FX-Y6) |
| FX-Y4 | 2027 年の年越し(1 月 1 日が金曜日) | Origin 2027-01-01〜01-09 は 2026、01-10 以降は 2027(V1 の関数で計算した期待値) |
| FX-Y5 | 2028 年の年越し(1 月 1 日が土曜日) | Origin 2028-01-01〜01-08 は 2027、01-09 以降は 2028 |
| FX-Y6 | 2018-12-24〜2019-03-05 の除外の期間(usable_from = None) | 2019 年 1〜3 月の Origin の年は 2018 |
| FX-Y7 | 候補が 1 つもない場合 | 取得をせず SOURCE_YEAR_UNDETERMINED |
| FX-Y8 | 前年のファイルの最後に受け入れた snapshot の後に、新しい年のファイルの最初の snapshot を取る | 新しい年のファイルの検査 3(calendar_integrity)に、前年の日付を「前回」として渡さない(前回なしとして扱う)。前年のファイルの後の取得には、前年の最後に受け入れた日付を渡す(§8.5) |
| FX-Y9 | 2011-01-01〜2026-10-13 のすべての日 | §8.7 の 4 の件数(一致 5,761、不一致 0、UNDETERMINED 4)と一致する |

- FX-Y1 の期待値を作るときも、読むのは Report_Date の日付だけにする。

## 9. acquisition decision(03:15〜03:20)

### 9.1 時刻(Requirements §6.4)

```
T_info + 15 分(03:15:00 JST)  Decision_Time(開始できる時刻)
T_info + 20 分(03:20:00 JST)  Acquisition_Decision_Deadline
```

### 9.2 起動

- A: 03:15 と 03:17 JST の 2 本の cron(18:15Z、18:17Z)。
- C: 03:15 JST に 1 回、03:17 JST にもう 1 回。
- どの起動も、Target_Origin を §5.3・§6.4 と同じ規則で決める(予定の時刻 S は 03:15 または 03:17 JST)。その日が Origin でなければ何もしない。
- その Origin が強制 failover の窓で、この経路が止める側なら、判定をせずに trigger_log に PATH_DISABLED_FAILOVER と記録して終わる(§10)。

### 9.3 開始の検査

- 判定の job は、runner の時計が `Decision_Time + ε` を過ぎるまで待ってから、TSA で時計を測る(Part 2 の PRE と同じ形の記録。Stage = "DECISION_START")。
- **開始が Decision_Time より前でないこと**を、測った時計の区間で確かめる: `Job_Start_At_Runner − e_hi ≥ Decision_Time`。満たさなければ、判定をせずに終わる(Requirements §6.4 の「03:15 より前に始まった判定は無効」)。TSA から時計の証拠を得られない場合も、判定をせずに終わる(§11 の F-P1-5)。

### 9.4 判定の手順

1. V2 main を取り込み、Target_Origin の decision の COMPLETE がすでにあれば、**ALREADY_COMPLETE** として何も書かずに終わる(idempotency)。
2. V2 main の `records/acquisition/<Target_Origin>/` にある attempt を、すべて集める(Target_Origin による帰属、Requirements §6.1)。
3. attempt ごとに、Requirements §6.2 の 7 段階の検査を順に行い、Attempt_Status を決める。
   - 1(PROVENANCE)・3(CLOCK sanity)・5(anchor)・6(CLOCK consistency)の中身は Part 2 の関数を呼ぶ。
   - G の検証は、**この判定の実行の中で** V2 repository の activity API に直接問い合わせて行う(Requirements §9.2 の G_CONTEMPORANEOUS_VALID)。
   - 2(CONTENT)は manifest の Content_Check を読む。4(窓)は Part 2 の時計の区間で判定する。7(anchor の遅れ)は Server_Anchored_At ≤ T_info + δ。
4. 窓の結果を決める(Requirements §6.3): USABLE が 1 つ以上なら SUCCESS、なければ FAILURE と主な原因コード。attempt が 1 つもなければ NO_ACQUISITION。
5. SUCCESS なら §8.6 で snapshot を選ぶ。
6. decision の行を作り、§9.5 の台帳に追記する。続けて同じ Target_Origin の COMPLETE の行を追記する。
7. push する。競合で拒否されたら取り込み直し、手順 1 に戻る(すでに COMPLETE があれば ALREADY_COMPLETE で終わる。なければ、取り込んだ後の状態で手順 2 からやり直す)。
8. 読み戻し: V2 main に、手順 6 の COMPLETE の行がちょうど 1 回、バイトで同じに存在することを確かめる。

### 9.5 decision の台帳(`records/decision/decisions.csv`)

- 判定の行(Origin ごとに 1 行。案): Target_Origin、Decision_Execution_ID、Path、Job_Start_At_Runner、Start_Clock_Evidence(Part 2 の記録への参照)、Window_Result(SUCCESS / FAILURE)、Cause_Code、Attempts(Execution_ID と Attempt_Status の一覧の正規の文字列)、Selected_Execution_ID、Selected_Content_SHA256、Server_Anchored_At(選んだ snapshot のもの)、G 検証の API 応答の SHA-256 の一覧、Code_SHA。
- COMPLETE の行: Target_Origin、Decision_Execution_ID、判定の行のバイト列の SHA-256、Status = COMPLETE。
- **canonical** は、V2 main の git の履歴で最初に入った COMPLETE の行である(Requirements §6.4)。force push を禁止しているので、履歴の順は push の順と一致する。

### 9.6 COMPLETE の時刻と 03:20 の期限

- Acquisition_Decision_Completed_At は、canonical な COMPLETE の行を含む commit が V2 main に入ったことを示す、V2 repository の activity API の記録の timestamp である(Requirements §6.4)。判定の job 自身は、この値を判定に使わない(push の後でしか分からないため)。
- この値が 03:20:00 JST 以下かどうかは、**この decision を使う側**が確かめる。
  - Part 3 の発行の attempt は、acquisition state を読むときに、activity API で canonical な COMPLETE の timestamp を確かめ、03:20:00 を過ぎていれば UNDETERMINED として扱う。
  - Part 4 の監査は、同じことを独立にやり直す。
- 03:20 を過ぎて入った COMPLETE は、監査の記録としては残るが、その窓は UNDETERMINED → Reliability FAILURE(Requirements §6.3、§6.4)。
- 判定の job が動かず、COMPLETE が 1 つもない場合も UNDETERMINED → FAILURE。

## 10. 強制 failover の窓での経路の停止(Requirements §7.4。F-P1-6 を改めた)

- 強制 failover の 4 つの Origin と、そのどれで A・C のどちらを止めるかは、試験の開始前に config に固定する(Code_SHA の対象)。
- **止める範囲(決定)**: 止める経路の、Part 1 に属する次のすべてを止める。
  1. 取得の trigger(A は §5.2 の cron、C は §6.4 の起動)
  2. 取得の実行(attempt)
  3. acquisition decision の trigger(§9.2)
- 止める経路の job は、起動しても §7.1 の 4(取得)と §9.2(decision)で止められていることを確かめ、何もせずに trigger_log に PATH_DISABLED_FAILOVER と記録して終わる。
- **成立の条件(決定)**: 残った経路**だけ**で、`Target_Origin の決定 → PRE → 取得 → Part 2 の provenance と anchor → 03:15〜03:20 の canonical な acquisition decision` まで到達しなければ、その failover の窓は SUCCESS にしない。止めた経路の job が何かを書いた場合(PATH_DISABLED_FAILOVER の trigger_log の行を除く)は、その窓は SUCCESS にしない。
  - これにより、「A を止めたのに A の decision の trigger が生きていて、C の取得を A が確定した」という見かけの冗長性で PASS することを防ぐ。
- Part 3 の発行と Part 4 の 08:45〜09:15 の adjudication まで同じ窓で片方の経路を止めるかは、**この Part では決めない**。後の Part と合わせて、Failover Gate 全体として固定する。
- 強制 failover の窓は、Reliability Gate と Issuance Gate の分母に入らない(Requirements §6.5)。その区分は decision の行には書かず、config の一覧で Part 4 が決める。

## 11. Finding(この Part を書く中で出た実装上の選択と確認)

Requirements の文言は変えない。以下は、Requirements が決めていない実装上の選択か、確認が要る点である。

| # | 内容 | 分類 | この版の扱い |
|---|---|---|---|
| F-P1-1 | **年の変わり目のファイル。** CFTC_Source_Year を runner の現在の年から決めない。Target_Origin → k̂ → 年で決める | Implementation Finding / **ACCEPT / CLOSE** | §8.1 の規則で確定。2013-01-09〜12 と 2030-01-09〜12 の UNDETERMINED は既知の費用として受け入れる。結果を見てから例外を足すことは禁止。仕様上の CLOSE であり、実装の Freeze の前に、V1 の固定版の tzdata の環境で fixture FX-Y1〜Y9 を実行し直して PASS させる(とくに FX-Y9 の 5,761 / 0 / 4 の再現) |
| F-P1-2 | **Retrieved_At_Runner の桁。** マイクロ秒、丸め・切り捨てなし | **ACCEPT / CLOSE 候補** | §8.3。境界で誤って USABLE の側に入る可能性を減らす fail-closed の方向の実装であり、V1 の data-availability の規則を広げるものではない |
| F-P1-3 | **前回の受け入れた日付の初期値。** V2 の最初の snapshot には前回がなく、検査 3 は自動的に通る | 実装上の選択(V1 の Forward の最初と同じ) | V1 と同じにした。較正期間に取得も行って前回を作るかは、較正が時計だけを測るという Requirements §10.6 に反するので、しない |
| F-P1-4 | **T_info より後の取得。** diagnostic として保存してよいが、USABLE の候補にはしない | **ACCEPT / CLOSE 候補** | §7.5。Late_Diagnostic_Max = 1 per Target_Origin × Acquisition_Path_ID(決定) |
| F-P1-5 | **decision の開始の検査。** Requirements §6.4 の「03:15 より前に始まった判定は無効」を、TSA で測った時計の区間で確かめる(§9.3)。TSA から時計の証拠を得られなければ判定をしない。この場合、ほかの経路の判定が成立しなければ UNDETERMINED → FAILURE になる | 実装上の選択(「開始」の測り方は Requirements にない) | TSA の時計の証拠で確かめる案にした |
| F-P1-6 | **強制 failover の窓で止める範囲。** | **REVISE(反映済み)** | §10。取得の trigger・取得の実行・acquisition decision の trigger をすべて止め、残った経路だけで canonical な decision まで到達することを要求する。Part 3・Part 4 の範囲は後で Failover Gate 全体として決める |
| F-P1-7 | **同じ Retrieved_At_Runner の attempt が 2 つある場合の選択**(§8.6) | 実装上の選択 / **ACCEPT / CLOSE** | canonical な順は Retrieved_At_Runner → max(Content_SHA256) → max(Manifest_SHA256) の完全な順序。push の順や A・C の競争に依存しない。V1 の選び方とも一致する |
| F-P1-8 | **ORIGIN_TARGET_MAP_V1 と CFTC の関数のコピー**(§4.1、§8.1、§8.4)。V1 のファイルを V2 にバイトで同じに写し、V1 の CODE_MANIFEST_V1 の値と照合する。§8.1 で使う cftc_rules と uscal も対象 | 実装上の選択 | V1 の repository からの読み取りではなく、写しと照合にした(V2 の Code_SHA を V2 の中で閉じるため) |
| F-P1-9 | **前回の受け入れた日付を同じ CFTC_Source_Year に限る**(§8.5)。限らないと、遅れて起動した前年のファイルの取得が、新しい年のファイルとの比較で CALENDAR_INTEGRITY になり、本来の OUTSIDE_WINDOW ではなく CONTENT_INVALID と記録される | **ACCEPT** | 同じ年に限る。年をまたいで前年の日付を渡さないことを FX-Y8 で確かめる。窓の SUCCESS / FAILURE は変わらない |
| F-P1-10 | **V1 の年の規則の見落とし(V1 の運用の記録として報告するだけ)。** V1 の `forward_run.cftc_snapshot` は実行時の JST の年のファイルを取る。過去の報告日で確かめると、毎年 1 月 1 日から 6〜15 日間(2011〜2026)、使える最新の報告は前年のファイルにある。V1 がこの期間に窓の中で取得すると、報告のない新しい年のファイル(または存在しないファイル)を取り、F_POS は使えない。次は 2027-01-01〜01-09 の Origin が当たる | **V1 OPERATIONAL FINDING / FROZEN-BEHAVIOR LIMITATION**(V1 violation ではない) | V1 は変更しない。**KNOWN UPCOMING RISK WINDOW** として OPS-FORWARD-03 に事前登録した(blob 0adebc40…、SHA-256 47019fb2…。**AUDIT PASS / PREREGISTRATION ACCEPTED**、Project の audit/ にも同じバイト列で写した)。2027 年 1 月の各 Origin で実際に起きたことを観測し、次の番号の記録で EXPECTED_RISK から OBSERVED に切り替える |
| F-P1-11 | **C2 でも残る GitHub への保存の依存。** V2 main への push と V2 の activity API が止まっている間は、C2 でも窓は成立しない | 既知の限界(Requirements §6.4・§9.2 の帰結) | §6.3。この Part では変えない。C2 の評価は「GitHub の scheduler / runner の障害のときに C2 だけで成立するか」で行う |

## 12. 決定済みの事項

**2026-10-26 22:25 JST(むすびさん)**

- F-P1-2(マイクロ秒、丸め・切り捨てなし)、F-P1-4(late diagnostic は Target_Origin × 経路ごとに 1 回)、F-P1-6(取得の trigger・取得・decision の trigger を止める)、F-P1-9(同じ Source_Year に限る)を採用。
- A の取得の時刻: 21:05 / 22:05 / 23:05 / 00:05 / 01:05 JST。C の取得の時刻: 21:35 / 23:35 / 01:35 JST(§5.2、§6.4)。
- Part の順: Part 1 → Part 2(Provenance / Clock / Anchor)→ Part 3(Parent / Issuance)→ Part 4(Adjudication / Acceptance / Audit)。
- 120 日の探索の範囲。

**2026-10-26 22:56 JST(むすびさん)**

- F-P1-1 = ACCEPT / CLOSE(§8.1 の一意性の規則。UNDETERMINED の 4 日の費用を受け入れる)。
- F-P1-7 = ACCEPT / CLOSE(§8.6 の完全な順序)。
- OPS-FORWARD-03 = AUDIT PASS / PREREGISTRATION ACCEPTED。
- Part 1 = FREEZE CANDIDATE。

**次の段階**

- Part 1 の最終 Freeze 監査(むすびさん): Requirements V0.7 との逐条の整合、未解決の Finding がないこと、fixture と試験の前提、Part 2 との interface の境界。
- 実装の Freeze の前に必要なこと(この Part の Freeze とは別): V1 の固定版の tzdata の環境での fixture FX-Y1〜Y9 の PASS。C2 の provider の選定と較正(§6.3)。
