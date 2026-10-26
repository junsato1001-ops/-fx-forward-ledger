# M1-MACRO-PIPELINE-V2 Implementation Spec — Part 4: Adjudication / Acceptance / Audit(DRAFT v0.1)

- 状態: **DRAFT v0.1**(Claude、2026-10-27)。むすびさんの監査待ち。Freeze 候補ではない。
- v0 からの変更(むすびさんの v0 の監査、2026-10-27 02:30 JST): §7.3 に activity の pages の完全性の fail-closed の規則(F-P4-5)、§7.2・§7.6 を「09:12 の証拠の締め切り + 09:12〜09:15 の finalizer」に作り直し(F-P4-4)、§9.2 に発行と adjudication の条件を追加(新しい F-P4-10)、§11 の S4 の意味を固定(F-P4-6)、§4・§13 の置き場所を V2 repository に決定(F-P4-8)、§14・§15 を更新。v0 は drafts/ にそのまま残す。
- 前提(Freeze 済み):
  - **M1-MACRO-PIPELINE-V2-REQUIREMENTS-V0.7**(SHA-256 edf27751…)。以下「Requirements」。
  - **Part 1 V0.5**(c63a0927…)と Erratum E1、**Part 2 V0.4**(6e9082a4…)、**Part 3 V0.3**(115d8bc4…)。
- この Part の範囲: 試験の順序と事前の記録、較正(Calibration Spec)、08:45〜09:15 の adjudication、Reliability・Failover・Issuance・Determinism / Audit・Safety の各 Gate の判定の手順、Acceptance PASS の最終の条件、独立した再計算。Part 1〜3 から送られた項目(F-P3-7、Part 2 §11 など)を受ける。
- **この Part は Requirements と Part 1〜3 を再設計しない。** Gate の閾値・分母・状態遷移は Requirements §6.5・§7・§10.6 のまま。この Part は、それを判定の手順・記録・関数に落とす。Requirements が決めていない点は §14 に Finding として分けて書く。
- **この Part で決めないこと**: V2 の予測性能の評価の仕様(予測の series の分母、欠けた Origin の扱い、確認的な解析)。Requirements §0 のとおり、別に Freeze する。この Part が扱うのは pipeline の受け入れである。
- このメモではしないこと: V1 の変更、較正と試験の開始、Development Replay、Holdout の計算。

---

## 1. 受け入れまでの順序

```
 (1) V2 の実装の候補(1 つの Code_SHA)
 (2) 実装の関門        fixture(Part 1 FX-Y1〜Y9、Part 3 の同一性の関門)、credential の範囲、Code_SHA の範囲  (§3)
 (3) 事前の記録        Calibration Record(較正の開始日)と Test Plan Record(試験の窓と failover の窓)を preregistration に置く  (§4)
 (4) 較正              7 暦日。A・C それぞれ合格すること                                                    (§5)
 (5) 受け入れの試験    通常の 60 窓 + 強制 failover の 4 窓。毎日、decision・発行・adjudication              (§6〜§8)
 (6) 独立した監査      Determinism / Audit Gate の再計算                                                    (§10)
 (7) Acceptance Record 5 つの Gate の判定                                                                  (§12)
 (8) 実装の Freeze     (1) と同じ Code_SHA を Freeze する
 (9) V2 の Forward の開始の記録   B を固定する(Part 3 §12.3)
```

- **(1)〜(7) は、1 つの実装の候補の Code_SHA で通して行う。** 途中でコード・config・container の image のどれかを変えたら、その候補の較正と試験は無効とし、新しい候補で (2) からやり直す(V1 の G1〜G9 と同じ考え方)。
- 較正と試験は、同じ経路・同じ実行環境で行う(Requirements §10.6)。

## 2. この Part が受ける項目

| 出どころ | 内容 | この Part |
|---|---|---|
| Requirements §6.5、§7.5 | adjudication、Issuance-Eligible Unit、状態遷移 | §7、§8.3 |
| Requirements §7.1〜§7.4 | Safety、Reliability、Determinism / Audit、Failover の各 Gate | §8、§9、§10、§11 |
| Requirements §10.6 | 較正の条件(Calibration Spec) | §5 |
| Part 1 §5.4、§10 | 起動しなかった回の数え方(TRIGGER_NOT_STARTED)、failover で止める範囲の残り | §5.4、§9 |
| Part 2 §11 | 独立した再計算(R の別の実装、時計、G、失効の情報、Revocation_Conflict_Check、Execution_ID) | §10 |
| Part 3 §7.2、§7.4、§9.2 | 補助の証拠と正式の検査の食い違いの報告、S0 の親の 08:15 の判定、COMPLETE の重複の監査 | §7、§10 |
| F-P3-7 | 強制 failover の窓での発行と adjudication の範囲 | §9 |

## 3. 実装の関門(試験の前)

すべて通ることを、試験の前の条件とする。一つでも通らなければ、較正にも試験にも進まない。

| # | 関門 | 出どころ |
|---|---|---|
| IG1 | Part 1 の年越しの fixture FX-Y1〜Y9 が、V1 の固定版の tzdata の環境で通る(FX-Y9: 5,761 / 0 / 4) | Part 1 §8.7 |
| IG2 | Part 3 の同一性の関門(合成のデータと専用の fixture。Fixture_ID・SHA-256・generator・expected scope を事前に固定)で、バイトが一致する | Part 3 §3.2 |
| IG3 | V1 の core のコピーが、V1 の CODE_MANIFEST_V1 と一致する | Part 1 §4.1、§8.4、Part 3 §3 |
| IG4 | V2 の Code_SHA の対象が、取得・decision・発行・adjudication・監査のすべての部分を含む | Requirements §7.1 の 3 |
| IG5 | credential の範囲の記録(用途・対象・権限)を作り、V2 の通常の実行環境に、V1 の repository と V1 の非公開の保管場所に書ける credential、V1 の非公開の保管場所を読める credential がないことを確かめる | Requirements §7.1 の 5、Part 3 §3.1、§10.1 |
| IG6 | V1 の開発用 snapshot の非公開の部分の写しの manifest が、V1 の公開の manifest と一致する | Part 3 §3.1 |
| IG7 | TSA の選定の記録と C2 の provider の選定の記録が preregistration にあり、config の値と一致する | Part 2 §12、F-P2-6、F-P3-8 |

## 4. 事前の記録

- この節と §5・§12 の「preregistration」は、**V2 repository の `preregistration/`** を指す(§13、§14 の F-P4-8)。V1 repository の `preregistration/` には、V2 の実装の開始の前の設計の Freeze の履歴(V1 の Freeze、V2 の Requirements、Part 1〜4)だけを置く。

### 4.1 Calibration Record(較正の前に preregistration に置く)

- Code_SHA、較正の開始日(JST の暦日)と終了日(開始日 + 6 日)、§5 の予定の時刻の一覧、TSA の構成。
- 記録を置いた後に、較正の開始日を変えない。

### 4.2 Test Plan Record(試験の前に preregistration に置く)

- **Test_Start_Origin**: 試験の最初の Origin。較正の合格の記録の後で、最初に来る Origin のうち、Test Plan Record を置いた日の翌日以後のもの(案)。
- **試験の窓の並び**: Test_Start_Origin から始まる、少なくとも 1 つの Horizon を持つ Origin の日を、順に 1, 2, 3, … と番号付けする(ORIGIN_TARGET_MAP_V1 の is_formal_origin による)。
- **強制 failover の窓(案)**: 番号 **13・29・45・61** の 4 つ。止める経路は **13 = A、29 = C、45 = A、61 = C**。それ以外の番号の窓が通常の窓で、順に 60 個に達するまで(番号 1〜64)。
  - この番号の規則は、この Part で固定する。Test Plan Record には、番号の規則から決まる具体的な日付を書く。結果を見て選び直さない(Requirements §7.4)。
  - 4 つの窓は試験期間に散らばり、A と C がそれぞれ 2 回、交互に来る。
- 試験の期間の長さの目安: 1 週間に約 6 つの Origin の日があるので、64 窓は約 11 週間。
- Test Plan Record を置いた後に、Test_Start_Origin と failover の窓を変えない。

## 5. 較正(Calibration Spec V1。Requirements §10.6)

### 5.1 固定する値(Requirements §10.6 のまま)

較正期間 = 連続 7 暦日、経路ごとに実際に開始された実行の clock-check pair が 100 組以上、時刻源 = R1・R2 だけ、RTT_max = 2.0 秒、p_min = 0.99(経路ごと)、ε = 6.0 秒。

### 5.2 予定の時刻(案)

- A・C のそれぞれで、**30 分ごと**に 1 回(A は毎時 07 分と 37 分、C は毎時 22 分と 52 分。UTC)。7 日で、経路ごとに 336 回の予定。
- 理由: V1 で観測した GitHub の schedule の起動の割合(約 50%)でも、A で 100 組以上の実行が見込めるようにする。数を見てから足すことはしない。

### 5.3 1 回の較正の実行

```
1. 起動の記録(trigger_log)を push する
2. CAL_PRE の記録を作り、R1・R2 に要求する         (Part 2 §3 と同じ形。Schema_Version = CAL_V1、Stage = CAL_PRE)
3. 10 秒待つ(取得の時間の代わり。案)
4. CAL_POST の記録を作り、R1・R2 に要求する        (Stage = CAL_POST。Random_Nonce は別に作る)
5. R1・R2 の失効の情報をそれぞれ取得する
6. すべてを 1 つの commit にして V2 main に push する
```

- CFTC の取得はしない(較正は時計の証拠だけを測る。Requirements §10.6)。
- 失効の情報は、**その実行が自分で取得したもの**で検証する。Part 2 §6.3 の canonical の選択は使わない(§14 の F-P4-2)。

### 5.4 判定

- **実際に開始された実行**: その予定の時刻 S について、経路の実行の記録(A は GitHub Actions の run、C は provider の実行の記録。Part 2 §10.6 の verify_execution が EXECUTION_CONFIRMED)がある実行。
- **TRIGGER_NOT_STARTED**: 予定したのに、実行の記録がない回。別に集計し、分母に入れない(Requirements §10.6)。
- 実行が開始されたのに、6 の push が V2 main にない回は、**開始されたが失敗した回**として分母に入れる。
- 1 回の実行の合格: CAL_PRE と CAL_POST の両方で、Part 2 §7.1 の使える測定(verify_r が R_VALID、RTT ≤ 2.0 秒)が 1 つ以上あり、Part 2 §7.2 の [e_lo, e_hi] が `max(|e_lo|, |e_hi|) ≤ 6.0 秒` を満たす。
- **経路ごとの合格**: 開始された実行が 100 回以上、かつ、そのうち合格の割合が 0.99 以上。A と C を合算しない。
- 較正の結果は Calibration Result Record として preregistration に置く。不合格なら、ε などを変えずに、設計を変えて新しい Calibration Spec を Freeze し、やり直す(Requirements §10.6)。

## 6. 受け入れの試験の日々の運用

各試験窓(Origin の日)で、Part 1〜3 のとおりに動かす。

| 時刻(JST) | 段階 | 定めている Part |
|---|---|---|
| 前日 21:05〜01:35 | 取得(A・C) | Part 1 |
| 03:15〜03:20 | acquisition decision | Part 1 §9、Part 2 |
| 03:20〜08:20 | 発行の attempt(`ledger_acceptance/` に書く) | Part 3 |
| 08:45〜09:15 | adjudication | この Part §7 |

- 試験の期間の発行の行は、`ledger_acceptance/` に置く(Part 3 §12.4)。

## 7. adjudication(08:45〜09:15。Requirements §7.5)

### 7.1 時刻

```
08:15:00 JST  S0 Eligibility Cutoff
08:30:00 JST  Issuance Deadline(V1 Part 4 の Verified_At_UTC 規則)
08:45:00 JST  Issuance_Adjudication_Time(adjudication を開始できる時刻。V2 の証拠の cutoff)
09:12:00 JST  Adjudication_Evidence_Cutoff(証拠の候補の締め切り。§7.6)
09:12〜09:15  finalizer の窓(閉じた証拠の集合から、純粋な関数で全 unit を判定する。§7.6)
09:15:00 JST  Adjudication_Deadline
```

### 7.2 起動と開始の検査(案)

- A・C の両方から起動できる。A は 08:45 と 08:50 の cron、C も同じ時刻(案)。
- **開始の検査**: adjudication の job は、最初に**開始の marker の commit**(Adjudication_Execution_ID、Target_Origin、経路)を V2 main に push する。その commit の `main_entry_time`(Part 2 §8)が **08:45:00 JST 以上**であることを確かめてから、判定の証拠を取り込む。08:45:00 より前なら、その job は判定をせずに終わる(Requirements §7.5 の「08:45 より前に始まった adjudication は無効」)(§14 の F-P4-3)。
- marker の main_entry_time が UNRESOLVED なら、決まるまで待つ。決まらないまま 09:12:00 を過ぎた job は、証拠の候補を push しない。
- 08:45 からの job は**証拠の候補を集めるだけ**で、COMPLETE を書かない(§7.6)。COMPLETE を書くのは 09:12 からの finalizer だけである。

### 7.3 証拠の集合を閉じる

| 証拠 | 閉じ方 |
|---|---|
| V2 の証拠(canonical な decision、`ledger_acceptance/` の COMPLETE と締め切りの監査、attempt の記録) | V2 main に **08:45:00 JST 以前に入った** commit だけ。V2 の activity API(Part 2 §8)で決める。V2_Adj_Audit_Commit_SHA を記録する |
| V1 の S0 の親 | **V1_Cutoff_Commit**: V1 の repository の activity API の記録のうち、V1 の main の branch の push で timestamp が 08:15:00 JST 以下の最後の記録の `after`。08:15:00 の時点の V1 の main の状態である(§7.4) |

- 08:45 より後に V2 main に入った証拠(遅れて push された締め切りの監査の行など)は、その Origin の判定に使わない。08:15 より後に V1 の main に入った S0 の行も使わない。
- V1 の activity の pages、V2 の activity の pages は、Part 2 §8 と同じ二層(不純な取得と純粋な判定)で取得・保存する。
- **V1 の activity の pages の完全性(fail-closed。§14 の F-P4-5)**: V1_Cutoff_Commit を決めてよいのは、保存した V1 の pages が次の両方を満たすときだけである。
  1. 最も新しい page から順に、page の欠けなく(Part 2 §8 の page の連続の検査に通る)、08:15:00 JST 以下の timestamp を持つ V1 の main の push の記録まで届いている。
  2. その範囲に Part 2 §8.4 の異常(順序の矛盾、`before` と直前の push の `after` のつながりの切れ、重複する id の内容の違いなど)がない。
- 満たさないとき(pages が途中で切れている、08:15:00 以下の push の記録まで届かない、API の保持の範囲を超えている、異常がある)は、**最後の push を推測しない**。V1_Cutoff_Commit は決まらず、その Origin のすべての unit は ELIGIBILITY_UNDETERMINED になる(§7.6 の U1・U2)。

### 7.4 Issuance-Eligible Unit の判定(unit = (Origin, Horizon))

```
Issuance-Eligible(Origin, Horizon)
  ⇔ acquisition state(canonical な decision。COMPLETE ≤ 03:20:00) = SUCCESS
  かつ V2_S0_PARENT_CHECK(Origin, Horizon, V1_Cutoff_Commit) = PARENT_OK      (Part 3 §7.2 の P1〜P6)
```

- V1_Cutoff_Commit の上で P1〜P6 に通ることは、「3 ペアの S0 の親の行が、server 側の証拠の上で 08:15:00 までに V1 の main にあり、検証に PASS している」ことと同じである(Requirements §7.5)。P5 の ECB の履歴は、S0 の行を初めて入れた commit(V1_Cutoff_Commit の祖先)の tree から読む(Part 3 §7.3)。
- **PARENT_NOT_READY_BY_CUTOFF**: V1_Cutoff_Commit が決まり、P1〜P6 のどれかに通らない(行がない、または検証に PASS しない)ことが確定した。
- **ELIGIBILITY_UNDETERMINED**: 09:12:00 で閉じた証拠の集合(§7.6)から V1_Cutoff_Commit を決められない(§7.6 の U1・U2)。この区分は finalizer が閉じた集合から純粋な関数で作るものだけであり、job の取得の失敗(API の失敗、object を取得できないなど)からは作らない。job の取得の失敗は、その job が COMPLETE を書かない理由にしかならない(§7.6)。

### 7.5 発行の結果の判定(Issuance-Eligible Unit ごと)

- V2_Adj_Audit_Commit_SHA の `ledger_acceptance/m1_macro_issue_commits.csv` で、その (Origin, Horizon) を含む COMPLETE の行のうち、V2 main の履歴で最初のもの(canonical)を探す。
- canonical な COMPLETE の Run_ID について、`ledger_acceptance/` の締め切りの監査に Deadline_Status = ON_TIME の行がある(V1 Part 4 §3 の規則。Verified_At_UTC ≤ 08:30:00 JST)。
- 両方あれば **ISSUED_ON_TIME**。なければ **NOT_ISSUED_ON_TIME**(理由は attempt の記録から: 未発行、不完全、LATE、PARENT_INVALID など)。V2 の側の理由として Issuance Gate の FAIL に数える。
- 同じ (Origin, Horizon) に COMPLETE の Run が 2 つ以上あれば、**DUPLICATE_COMPLETE** を記録する(Determinism / Audit Gate の違反。§10)。

### 7.6 証拠の締め切り(09:12)と finalizer(09:12〜09:15)(§14 の F-P4-4)

**(a) 証拠の候補(08:45〜09:12)**

- §7.2 の開始の検査に通った job は、V1 の activity の pages と V2 の activity の pages を取得し、**Adjudication Evidence Candidate** として `records/adjudication/<Target_Origin>/evidence/<Adjudication_Execution_ID>/` に push する。
- 候補の中身: 取得した pages(取得の不純な層の記録と SHA-256)、その pages から純粋な関数で求めた V1_Cutoff_Commit(または「決まらない」とその理由)、P1〜P6 に要る V1 の object の path と git object id(V1_Cutoff_Commit の tree と、P5 の ECB の履歴の commit の tree から)、Code_SHA。V1 の object の中身そのものは置かない(object id で内容が決まるため)。
- 候補は判定ではない。候補を push した job も、COMPLETE を書かない。
- 取得に失敗した job は、候補を push しないか、取得できた範囲だけを候補として push する(不完全な pages は、(c) で完全な page の組として数えられないだけである)。

**(b) 閉じた証拠の集合**

- **Adjudication_Evidence_Cutoff = 09:12:00 JST**。閉じた証拠の集合 = その Origin の候補のうち、候補の commit の V2 の `main_entry_time`(Part 2 §8)が 09:12:00 JST 以下のもの全部。
- 09:12:00 より後に V2 main に入った候補は、その Origin の判定に使わない(記録には残す)。

**(c) finalizer(09:12〜09:15)**

- A・C の両方から起動できる。A は 09:12 と 09:13 の cron、C も同じ時刻(案)。finalizer は最初に自分の開始の marker を push し、その main_entry_time が 09:12:00 JST より後であることを確かめる。
- finalizer は、閉じた集合を V2 の activity の pages(finalizer 自身が取得し、Part 2 §8 の完全性の検査に通ったもの)で確定する。確定できなければ、その finalizer は COMPLETE を書かない。
- 閉じた集合から、次の**純粋な関数**で全 unit を判定する。入力は閉じた集合と、git object id で内容が決まる V1 の object と V2 の commit だけである。
  1. 閉じた集合のうち、§7.3 の完全性の 1・2 を満たす V1 の pages を持つ候補を「完全な候補」とする。
  2. **U1**: 完全な候補が 1 つもない → その Origin のすべての unit は ELIGIBILITY_UNDETERMINED(理由 NO_COMPLETE_V1_PAGES_IN_CLOSED_SET)。
  3. **U2**: 完全な候補の V1_Cutoff_Commit が 1 つに一致しない → すべての unit は ELIGIBILITY_UNDETERMINED(理由 V1_CUTOFF_CONFLICT)。server 側の記録は同じなので、完全な候補どうしの不一致は異常として扱い、どれかを選ばない。
  4. 一致すれば、それを V1_Cutoff_Commit とする。§7.4 の P1〜P6、§7.5 の発行の結果(V2 の 08:45 以前の証拠。§7.3)を求める。
- 純粋な関数に要る object(V1 の object、V2 の commit)を finalizer が取得できなければ、**その finalizer は COMPLETE を書かない**。ELIGIBILITY_UNDETERMINED にもしない。もう一方の経路の finalizer が取得できれば、同じ内容の判定を書く。どちらも 09:15:00 までに書けなければ、ADJUDICATION_NOT_COMPLETED_BY_DEADLINE になる。
- この規則で、COMPLETE の判定の中身は閉じた集合だけで決まり、どの finalizer が先に push したかに依らない。job ごとの未解決の状態から COMPLETE が書かれることはない。

**(d) COMPLETE と期限**

- COMPLETE の行 = 判定の中身(canonical JSON。Part 2 §3)とその SHA-256(Judgement_SHA256)+ 書いた finalizer の Adjudication_Execution_ID と経路。idempotency・canonical・COMPLETE の書き方は Part 1 §9.4〜§9.5 の decision と同じ(最初に V2 main に入った COMPLETE が canonical。COMPLETE の commit は rebase しない)。
- 2 つ目の COMPLETE が入った場合、その Judgement_SHA256 が canonical のものと違えば、Determinism / Audit Gate の違反として記録する(§10)。
- **Adjudication_Completed_At** = canonical な COMPLETE の commit の V2 の main_entry_time。09:15:00 JST 以下なら期限内。過ぎていれば、その Origin のすべての unit は ADJUDICATION_NOT_COMPLETED_BY_DEADLINE(Requirements §7.5)。

### 7.7 adjudication の記録(`records/adjudication/adjudications.csv`、追記のみ)

Target_Origin、Adjudication_Execution_ID、Path、Start_Marker_Main_Entered_At、閉じた証拠の集合(候補の commit と main_entry_time の一覧、09:12:00 より後の候補の一覧)、完全な候補の一覧、V2_Adj_Audit_Commit_SHA、V1_Cutoff_Commit(または U1・U2)、Judgement_SHA256、Acquisition_State(と canonical な decision の行の SHA-256)、unit ごとの区分(Issuance-Eligible / PARENT_NOT_READY_BY_CUTOFF と P1〜P6 の結果 / ELIGIBILITY_UNDETERMINED と理由)、Issuance-Eligible の unit ごとの ISSUED_ON_TIME / NOT_ISSUED_ON_TIME と Run_ID、DUPLICATE_COMPLETE の有無、Part 3 の補助の証拠(V1 の Actions)と正式の検査の食い違い、保存した pages の SHA-256、Code_SHA。COMPLETE の行は decision と同じ形。

## 8. Reliability Gate(Requirements §7.2)と Issuance Gate(§7.5)の集計

### 8.1 通常の窓の結果

窓 w(Test Plan Record の通常の窓)ごとに:

- canonical な decision の COMPLETE がある、かつ その main_entry_time ≤ 03:20:00 JST → その Window_Result(SUCCESS / FAILURE と Cause_Code)。
- ない、または 03:20:00 を過ぎた → **FAILURE(UNDETERMINED)**(Part 1 §9.6)。

### 8.2 Reliability Gate の判定

- 通常の窓を番号の順に並べる。failover の窓は飛ばす(Requirements §7.2)。
- **2 個続けて FAILURE が出た時点で、Reliability Gate = FAIL**(即時。§12.2)。
- 60 窓が終わって FAILURE が 2 個以下なら PASS、3 個以上なら FAIL。
- 原因コードの内訳(NO_ACQUISITION、OUTSIDE_WINDOW、…、UNDETERMINED)は報告するが、どれも除外しない。

### 8.3 Issuance Gate の判定

- 分母: 通常の 60 窓に属する unit のうち、Issuance-Eligible のもの(canonical な adjudication による)。
- **FAIL** の条件(一つでも当たれば):
  - Issuance-Eligible の unit で NOT_ISSUED_ON_TIME が 1 件以上。
  - ELIGIBILITY_UNDETERMINED が 1 件以上。
  - ADJUDICATION_NOT_COMPLETED_BY_DEADLINE が 1 件以上。
- Issuance-Eligible の unit が 0 件 → **INSUFFICIENT_ISSUANCE_EVIDENCE**(PASS にしない)。
- 上のどれにも当たらず、Issuance-Eligible の unit が 1 件以上あり、そのすべてが ISSUED_ON_TIME → PASS。
- PARENT_NOT_READY_BY_CUTOFF の件数は、必ず報告する。acquisition が FAILURE の窓の unit は N/A。

## 9. Failover Gate と強制 failover の窓の範囲(Requirements §7.4。F-P3-7)

### 9.1 止める範囲(案。Failover Gate 全体として固定する)

強制 failover の窓で止める経路は、次の**すべて**を止める。

| 段階 | 止めるもの | 出どころ |
|---|---|---|
| 取得 | 取得の trigger と実行 | Part 1 §10 |
| acquisition decision | decision の trigger | Part 1 §10 |
| 失効の情報の候補の収集 | (decision の job の中で行うので、decision と一緒に止まる) | Part 2 §6.3 |
| 発行 | 発行の attempt の trigger | Part 3 §4.3(案)をここで固定 |
| adjudication | adjudication の trigger | この Part |

- 止める経路の job は、起動しても何もせず、trigger_log に PATH_DISABLED_FAILOVER と記録して終わる。

### 9.2 判定

- 強制 failover の窓 f の SUCCESS の条件:
  1. 残った経路だけで、canonical な acquisition decision が 03:20:00 までに COMPLETE し、Window_Result = SUCCESS(Part 1 §10)。
  2. 止めた経路の job が、PATH_DISABLED_FAILOVER の trigger_log の行のほかに、V2 main に何も書いていない(取得の attempt、失効の情報の候補、decision、発行、adjudication の証拠の候補・marker・COMPLETE のどれも)。
  3. **発行(§14 の F-P4-10)**: canonical な adjudication でその窓の Issuance-Eligible の unit が 1 つ以上あり、そのすべてが ISSUED_ON_TIME であり、その canonical な COMPLETE の Run が残った経路の発行で作られている。ELIGIBILITY_UNDETERMINED の unit が 1 つでもあれば、この条件を満たさない。
  4. **adjudication(§14 の F-P4-10)**: 残った経路の finalizer の canonical な COMPLETE があり、Adjudication_Completed_At ≤ 09:15:00 JST。
- 4 つの窓のすべてが SUCCESS なら Failover Gate = PASS。1 つでも FAILURE なら FAIL。
- **Issuance-Eligible の unit が 0 の窓**(V1 の親が 08:15 までにそろわなかったなど。V2 の側の失敗ではない): 条件 3 を確かめられないので、SUCCESS にも FAILURE にもせず **FAILOVER_ISSUANCE_NOT_EXERCISED** とする。そのような窓が 1 つでもあれば、Failover Gate は PASS にならない(Issuance Gate の INSUFFICIENT_ISSUANCE_EVIDENCE と同じ考え方。窓を足して取り直すことはしない。Requirements の 4 つの窓を変えないため)。結果は INSUFFICIENT_FAILOVER_EVIDENCE とし、Acceptance は PASS にならない。むすびさんに確かめていただきたい(§15)。
- 条件 3・4 は Requirements §6.5 の「記録だけ」より厳しい。Failover Gate の判定に使うだけであり、強制 failover の窓は引き続き **Issuance Gate の分母に入れない**(§8 は変えない)。

## 10. Determinism / Audit Gate と独立した再計算(Requirements §7.3、Part 2 §11)

### 10.1 独立した監査の実装

- 監査は、production のコードとは**別の実装**で行う(Part 2 F-P2-9)。少なくとも、R の検証、正規の JSON の検査、main_entry_time、時計の区間、attempt_status、Revocation_Conflict_Check、V2_S0_PARENT_CHECK、§7・§8 の判定を、別に実装する。
- 監査の実装の Code_SHA も記録する。監査の実装は、production の記録を読むだけで、V2 main に書くのは監査の結果の記録だけ。

### 10.2 再計算の対象と、一致の条件

| 対象 | 再計算 | 一致の条件 |
|---|---|---|
| 正規の記録 | manifest・PRE・POST の時刻・decision・adjudication の各記録の正規性と hash | すべて一致 |
| R | 保存した資料だけで verify_r(別の実装)。TSA に問い合わせない | 同じ t_R、同じ R_VALID / R_INVALID |
| 失効の情報 | Candidates・Valid・Canonical の選択、**Revocation_Conflict_Check を Valid の全体から** | 同じ |
| 時計 | clock_interval、健全性、窓、前後関係、decision の開始の判定 | 同じ |
| G と main_entry_time | 保存した pages と記録した Audit_Repo_Commit_SHA で再計算(現在の HEAD を読まない) | 同じ t_G、同じ Main_Entered_At |
| Execution_ID | 保存した応答で verify_execution | 同じ |
| attempt と窓 | attempt_status、Included / Excluded、Window_Result、Cause_Code、snapshot の選択(V1 と同じ規則) | すべての窓で同じ |
| S0 の親 | V2_S0_PARENT_CHECK を同じ V1 の commit で | 同じ |
| adjudication | §7.4・§7.5 の区分 | すべての unit で同じ |
| Gate の集計 | §8・§9 | 同じ |

- **Determinism / Audit Gate = PASS** ⇔ すべての対象で一致し、かつ DUPLICATE_COMPLETE(decision・発行・adjudication のどれか)が 0 件、かつ adjudication の 2 つ目以降の COMPLETE で Judgement_SHA256 が canonical と違うものが 0 件(§7.6 (d))。
- 一致しないものが 1 つでもあれば FAIL。記録は書き換えない(Part 1 §6.4 と同じ)。

### 10.3 API の照合(保持期間の中だけ)

- 監査は、GitHub の activity API・Actions の API に問い合わせ直し、保存した pages・応答と食い違いがないかを確かめる。食い違いは監査の記録に残す。
- 保持期間を過ぎた後は、保存したものだけで再計算する(G_LONG_TERM_SELF_CONTAINED = false)。
- Part 3 の補助の証拠(V1 の Actions の Storage Verification Gate)と正式の検査の食い違いも、ここで報告する。Gate の判定には使わない。

### 10.4 監査の時期(案)

- **日々**: 各試験窓の adjudication の後に、その窓の再計算を行い、記録する。
- **最後**: 試験の終わりに、すべての窓について通して再計算する。Determinism / Audit Gate の判定は、最後の再計算で行う。

## 11. Safety Gate(Requirements §7.1)

| # | 検査 | 方法 |
|---|---|---|
| S1 | V1 の data/m1macro/ と ledger/ に V2 の行がない | V1 の repository の該当の path を、試験の開始の時点と終わりの時点で走査し、`V2-` で始まる Run_ID と V2 の path がないことを確かめる。試験の期間の V1 の main への push の記録(V1 の activity API)に、V2 の credential の主体による push がないことも確かめる |
| S2 | Holdout の 5 ペアに触れない | V2 のコードの静的な検査(Holdout の 5 ペアの名前を、V1 の core の HOLDOUT_PAIRS の検査の外で参照しない)と、V2 の記録の走査(5 ペアの pair 固有の値がない)。V1 の core の HoldoutBreach が一度も起きていないこと |
| S3 | すべての経路の部分が Code_SHA の対象 | §3 の IG4 を、試験の終わりにもう一度確かめる |
| S4 | 取得の記録と結合の経路が完全 | **必要な監査・provenance の記録がそろい、暗号的に、または結合の経路で検証できる形で結び付いていること。provenance の判定が VALID か INVALID かには依らない**。すべての attempt で、Part 2 §10 の検査 1(PROVENANCE)の (a)〜(c)・(e) の記録がそろい、互いの hash・commit の結合が検証できる。PROVENANCE_INVALID の判定そのものは S4 の違反ではない(Reliability の FAILURE の原因コード)。INVALID を後から独立に検証するための記録の鎖が欠けていれば、判定が VALID・INVALID のどちらでも S4 の違反(§14 の F-P4-6) |
| S5 | V1 に書ける credential がない | §3 の IG5 を、試験の終わりにもう一度確かめる |

- **一つでも違反があれば、その時点で Safety Gate = FAIL**(即時)。

## 12. Acceptance の判定

### 12.1 Acceptance PASS の条件

```
Acceptance PASS ⇔ 実装の関門(§3)がすべて通った
              かつ 較正が A・C ともに合格した(§5)
              かつ Safety Gate = PASS
              かつ Reliability Gate = PASS
              かつ Determinism / Audit Gate = PASS
              かつ Failover Gate = PASS
              かつ Issuance Gate = PASS(INSUFFICIENT_ISSUANCE_EVIDENCE でない)
              かつ (1)〜(7) をすべて同じ 1 つの Code_SHA で行った
```

### 12.2 FAIL が確定した場合

- Safety の違反、Reliability の 2 個連続の FAILURE、failover の窓の FAILURE、Issuance の FAIL の条件のどれかが確定した時点で、**Acceptance = FAIL** を記録する。
- FAIL が確定した後も、運用を止めずに診断のために続けてよいが、その後のデータは、この候補の Acceptance の判定にも、新しい候補の判定にも使わない(§14 の F-P4-7)。
- 新しい候補は、設計の変更(Finding として記録)→ 新しい Code_SHA → §3 の実装の関門 → 新しい Calibration Record と較正 → 新しい Test Plan Record → 試験、の順でやり直す。前の候補の較正と試験のデータは引き継がない。

### 12.3 Acceptance Record

- preregistration に置く。Code_SHA、較正の結果、各 Gate の判定と内訳、PARENT_NOT_READY_BY_CUTOFF の件数、原因コードの内訳、独立した監査の実装の Code_SHA と結果、Test Plan Record への参照。

## 13. 記録の置き場所(V2 repository)

| path | 中身 |
|---|---|
| `records/adjudication/` | adjudication の記録、marker、保存した pages |
| `records/calibration/` | 較正の実行の記録(CAL_PRE・CAL_POST・token・失効の情報) |
| `records/audit/` | 独立した監査の結果(日々と最後) |
| `preregistration/`(**V2 repository**。§14 の F-P4-8) | Calibration Record、Calibration Result Record、Test Plan Record、Acceptance Record、V2 の Forward の開始の記録(B。Part 3 §12.3) |
| `records/adjudication/<Target_Origin>/evidence/` | 証拠の候補(§7.6 (a)) |

- V1 repository の `preregistration/` には、V2 の実装の開始の前の設計の Freeze の履歴(V1 の Freeze、V2 の Requirements、Part 1〜4 とその Erratum)だけを置く。V2 の候補に固有の記録は置かない。V2 の実行環境は V1 に書く credential を持たない(Part 3 の F-P3-10)ので、記録の作成の経路は V2 の側の 1 本になる。

## 14. Finding

| # | 内容 | 分類 | この版の扱い |
|---|---|---|---|
| F-P4-1 | **試験の窓の番号と failover の窓の位置。** 番号 13・29・45・61、止める経路は A・C・A・C | 実装上の選択(Requirements §7.4 の具体化) | ACCEPT / CLOSE(むすびさん、v0 の監査)。§4.2。この Part で規則を固定し、Test Plan Record で日付を固定する |
| F-P4-2 | **較正の失効の情報。** 較正の実行は、自分で取得した失効の情報で検証する。Part 2 §6.3 の canonical の選択は decision の A・C の競争を避けるためのものであり、較正の実行は 1 つ 1 つが独立の単位で競争がない。失効の情報を得られないことも「clock evidence を安定して得られるか」の一部として、較正の不合格に数える | 実装上の選択 | ACCEPT / CLOSE(むすびさん、v0 の監査)。§5.3 |
| F-P4-3 | **adjudication の開始の検査。** Requirements §7.5 は「08:45 より前に始まった adjudication は無効」とする。decision と違い、TSA ではなく、開始の marker の commit の V2 の main_entry_time(server 側)で確かめる | 実装上の選択 | ACCEPT / CLOSE(むすびさん、v0 の監査。TSA は足さない)。§7.2 |
| F-P4-4 | **ELIGIBILITY_UNDETERMINED と競争。** v0 では、09:12 まで判定できない job が ELIGIBILITY_UNDETERMINED を COMPLETE でき、09:12 の前後に別の job が判定できた場合、canonical な COMPLETE が競争の結果に依った(Part 2 で除いた「同じ閉じた証拠なのに push の順で意味が変わる」状態) | Requirements の状態(§7.5)と、Part 2 の決定論の方針との間の残り | BLOCKING / REVISE(むすびさん、v0 の監査)→ v0.1 で作り直し: 09:12:00 = 証拠の候補の締め切り、09:12〜09:15 = finalizer の窓。ELIGIBILITY_UNDETERMINED は閉じた集合から純粋な関数で作るものだけ(U1・U2)。job の取得の失敗からは COMPLETE を書かない。§7.2、§7.4、§7.6 |
| F-P4-5 | **V1_Cutoff_Commit。** 08:15:00 の時点の V1 の main を、V1 の activity API の最後の push の `after` で決める。S0 の行がそこにあることで、「08:15 までに使えるようになった」を表す | 実装上の選択 | ACCEPT / CLOSE WITH CLARIFICATION(むすびさん、v0 の監査)。08:15 以前の pages の完全性を証明できなければ最後の push を推測せず ELIGIBILITY_UNDETERMINED、を §7.3 に明記した。§7.3、§7.4、§7.6 の U1・U2 |
| F-P4-6 | **S4 の範囲。** PROVENANCE_INVALID の attempt を、すべて Safety の違反にはしない(PROVENANCE_INVALID は Reliability の FAILURE の原因コードでもあるため)。記録の欠け(manifest、PRE、token の hash の不一致など、結合の経路そのものの欠け)だけを S4 の違反にする | Requirements §7.1 の 4 と §6.2 の重なりの整理 | ACCEPT / CLOSE WITH CLARIFICATION(むすびさん、v0 の監査)。S4 の意味を「必要な監査・provenance の記録がそろい、検証できる形で結び付いていること。判定が VALID か INVALID かには依らない」に固定した(§11) |
| F-P4-7 | **FAIL が確定した後のデータ。** 診断のために運用を続けてもよいが、Acceptance の判定には使わない | 実装上の選択 | ACCEPT / CLOSE(むすびさん、v0 の監査)。§12.2 |
| F-P4-8 | **V2 の事前の記録の置き場所。** これまでの Freeze の記録は V1 の repository の preregistration/ にある。V2 の実装が始まった後の記録(Calibration、Test Plan、Acceptance)を、V2 repository に置くか、V1 の repository の preregistration/ に置くか。V1 の repository に置く場合、V2 の実行環境は V1 に書けないので、記録の作成は V2 の実行環境の外(人の手の作業)で行う | 運用の選択 | 決定(むすびさん、v0 の監査): **V2 repository**。V1 の preregistration/ = V2 の実装の開始の前の設計の Freeze の履歴、V2 の preregistration/ = 候補に固有の Calibration・Calibration Result・Test Plan・Acceptance・Forward の開始(B)の記録。§4、§13 |
| F-P4-9 | **較正の予定の頻度と TSA の量。** 30 分ごとで、経路ごとに 7 日で 336 回。1 回あたり最大 8 回の TSA の要求(2 局 × PRE・POST × 再試行)で、較正だけで最大 5,376 回 | 運用の確認 | DEFER → TSA の選定の記録(むすびさん、v0 の監査)。頻度の案(30 分ごと、10 秒の待ち)は v0.1 に進めてよい。R-ACC-13 で 5,376 回の規模が許されることを確かめてから正式に確定する。§5.2 |
| F-P4-10 | **強制 failover の窓の SUCCESS の範囲。** v0 の §9.2 は 03:20 の acquisition の SUCCESS までだった。F-P3-7 を閉じるには、残った経路だけで、Issuance-Eligible の unit がすべて ISSUED_ON_TIME になり、adjudication が 09:15 までに COMPLETE することも要る。Issuance-Eligible の unit が 0 の窓は FAILOVER_ISSUANCE_NOT_EXERCISED とし、Failover Gate を PASS にしない案 | Requirements §6.5(「記録だけ」)より厳しい条件の追加。Issuance Gate の分母は変えない | REVISE(むすびさん、v0 の監査)→ v0.1 の §9.2 の条件 3・4。0 の窓の扱いは案。むすびさんに確かめていただきたい |

## 15. むすびさんに判断してほしいこと

1. **F-P4-4 の作り直し(§7.6)**: 証拠の候補(08:45〜09:12)→ 09:12:00 の締め切り → finalizer(09:12〜09:15)が閉じた集合から純粋な関数で全 unit を判定する。ELIGIBILITY_UNDETERMINED は U1(完全な V1 の pages を持つ候補がない)と U2(完全な候補の V1_Cutoff_Commit が一致しない)だけ。object を取得できない finalizer は COMPLETE を書かない。
2. **U2 の扱い**: 完全な候補どうしの V1_Cutoff_Commit の不一致を、どれかを選ばずに ELIGIBILITY_UNDETERMINED とする案でよいか。
3. **V1 の object を候補に入れない案(§7.6 (a))**: 候補には git object id だけを置き、中身は finalizer が id で取得する。内容は id で決まるので、取得できた finalizer の判定は同じになる。
4. **F-P4-10(§9.2)**: 条件 3・4 の追加と、Issuance-Eligible の unit が 0 の窓を FAILOVER_ISSUANCE_NOT_EXERCISED(Failover Gate を PASS にしない)とする案。
5. **F-P4-5・F-P4-6・F-P4-8 の明文化**(§7.3、§11 の S4、§4・§13)が、v0 の監査の判定と合っているか。
