# M1-MACRO-PIPELINE-V2 — pipeline 要件メモ(DRAFT v0.3)

- 状態: **DRAFT v0.3**(Claude、2026-10-26)。むすびさんの監査待ち。**Freeze 候補ではない**。Freeze 候補に上げるかどうかは、この版の監査のあとでむすびさんが決める。
- 前の版: v0(blob ede24e7e…)、v0.1(blob b7e4aa92…)、v0.2(blob b2e3a9d4…)。どれも書き換えずに残してある。
- v0.2 からの変更: むすびさんの判断(2026-10-26 05:27 JST、v0.2 = REVIEW PASS WITH REVISIONS)と、その後の採用の決定(2026-10-26 11:20 JST)を反映した。
  1. **Server_Anchored_At を派生値として定義した**: `min(Valid_Anchor_Timestamps)`。有効な anchor が 0 なら NO_VALID_SERVER_ANCHOR で、その試験窓は FAILURE(§9.1)。
  2. **正式な anchor は G または R。** X は補助の provenance のまま(§9.5)。
  3. **δ = 300 秒を決定とした**(§9.4)。V1 の 6 件の実測から導いた値ではないことを明記した。
  4. **G の検証手順を仕様にした**(§9.2)。commit の author / committer の日時は使わない。中身との結合は commit → tree → manifest → Content_SHA256。server 側の API 応答は、そのまま保存して hash を取る。
  5. **R(TSA)の Acceptance Requirements を仕様にした**(§9.3)。accuracy、genTime の精度、取得時点の証明書の鎖の保存、token・署名・message imprint・hash algorithm・証明書を後から独立に再検証できること。
  6. **runner の時計の健全性を独立の要件にした**(§10)。外部の時刻と RTT で検査する。窓の上端と下端の両方に時計の不確かさを入れた。**ε は数値を固定しない。**
  7. **試験窓を必ず SUCCESS か FAILURE に写す規則を定めた**(§6)。ANCHOR_LATE を含む原因分類は、Reliability Gate から除外しない。
  8. 追加: Acquisition_Manifest(§3.3)。G と R が同じ manifest を anchor するようにして、結合の経路を 1 本にした。
- 根拠: OPS-FORWARD-01(blob 17b02eae…)、OPS-FORWARD-02(blob 052251bc…)、F14-a(V2 PIPELINE-DESIGN FINDING / CONFIRMED)、F8-a・F11-a(Freeze の記録で使った activity API の照合と、その落とし穴)。
- このメモではしないこと: V1 の workflow・code・config の変更、V2 の本番取得、Development Replay、Holdout の計算。

---

## 0. 名称と位置づけ(決定済み。v0.2 から変更なし)

- **名称(暫定)は M1-MACRO-PIPELINE-V2。** 新しい統計 Trial にはしない。予測モデル、特徴量、推定の方法、評価の仕様は M1-MACRO-V1 をそのまま引き継ぐ。
- 変えるのは acquisition / trigger / provenance / issuance orchestration だけ。
- **V1 の Forward は V1 のまま続ける。** V1 の 104 週の確認的な証拠を、途中から V2 に付け替えない。
- **Pipeline V2 の Forward の開始点**: Acceptance Gate の PASS と、実装の Freeze の完了を待ち、その後の最初の予定された Origin とする。V1 の 104 週の series には混ぜない。
- **V2 の series の役割**は、次の 2 つに分ける。期間と評価の仕様は、それぞれ別に Freeze してから決める。
  - pipeline の信頼性の証拠
  - 予測性能の証拠
- V2 にも自動的に別の 104 週を設ける、ということはまだ決めない。統計モデルが V1 と同じだからである。

## 1. 観測された事実(v0.2 から変更なし)

| 項目 | 2026-10-20〜10-25(main に統合した 2026-10-20T12:08Z の後) |
|---|---|
| 予定された定時実行 | 12 回(cron "40 15,17 * * *"、6 日分) |
| 実際に起動した定時実行 | **6 回**(1 日 1 回)。15:40Z に起動した回は 0 回 |
| 起動した時刻 | 10/20 19:33:29Z、10/21 19:33:35Z、10/22 19:26:25Z、10/23 19:31:25Z、10/24 18:20:30Z、10/25 18:32:25Z |
| 起動したときの CFTC の取得 | 6 回とも成功 |
| T_info の窓に入った取得 | **0 / 6 日** |
| M1 の発行(Origin 10/22 1D、10/23 1D、10/25 1W/4W) | すべて COMPLETE / ON_TIME。FORECAST は 0 件(12 行すべて ABSTAIN_SYSTEM / FEATURE_UNAVAILABLE) |
| 取得から main への push(server 時刻)までの遅れ(V1、6 件) | 2〜5 秒。6 件とも push が 1 回目で通った場合 |
| 根本原因 | 特定していない |

- この版では、新しい運用の記録は読んでいない。Origin 2026-10-26 以降の結果は OPS-FORWARD の次の記録で扱う。

## 2. 守る原則(v0.2 から変更なし)

1. **V1 は変えない。**
2. **V1 と V2 を分ける。**
   - V2 の設計、試験、試験取得は、**別の repository** で行う(決定済み)。V1 の canonical な Forward(この repository の data/m1macro/ と ledger/m1_macro_*)には、物理的に触れない。
   - V2 の行には、V2 の検証用であることを示す区分を付けて、論理的にも分ける。
3. **救済しない。** V2 で取得した snapshot を V1 の発行に使わない。
4. **範囲は acquisition / trigger / provenance / issuance orchestration に限る。** 統計モデル、特徴量の定義、評価の仕様は変えない。S0 のモデルも変えない。
5. **基準は事前に固定する。** Acceptance Gate の閾値、δ、ε は、V2 の試験 telemetry を見る前に固定する。
6. **単一障害点を減らす。**

## 3. 取得の窓、記録、使えるかの判定

### 3.1 窓(凍結済みの規則。変えない)

- Origin t の CFTC snapshot として使えるのは、取得の時刻が (T_info(t) − 6h, T_info(t)] にあるものだけ。
- T_info は Origin の日の 03:00 JST。窓は前日の 12:00Z から 18:00Z まで。
- 窓の中に複数あれば、最も遅いものを使う。

V2 は、この規則を変えない。V2 が加えるのは、「取得の時刻が窓の中にあった」と主張するための**証拠の基準**である(§3.4、§10)。この基準は、V1 の規則で使えるものを減らす方向にしか働かず、増やす方向には働かない(§11 の論点 6)。

### 3.2 取得 1 回ごとの記録(必須)

| 欄 | 意味 | どこに記録するか |
|---|---|---|
| Target_Origin | この取得が対象とする Origin(trigger の時点で決まる) | manifest |
| Acquisition_Path_ID | 取得した経路(A、C など) | manifest |
| Execution_ID | 取得した実行の ID | manifest |
| Retrieved_At_Runner | 取得した実行環境の時計の値。応答の本文を受け取り終えた時点の UTC | manifest |
| Content_SHA256 | 取得した原ファイルのバイト列の SHA-256 | manifest |
| Clock_Check_Pre | 取得の前に測った runner の時計の検査(§10) | manifest |
| Manifest_SHA256 | Acquisition_Manifest の正規のバイト列の SHA-256 | anchor の記録 |
| Clock_Check_Post | 取得の後に測った runner の時計の検査(§10) | anchor の記録 |
| Anchor_G | G の証拠と検証の結果(§9.2) | anchor の記録 |
| Anchor_R[i] | i 番目の TSA の token と検証の結果(§9.3) | anchor の記録 |
| Valid_Anchor_Timestamps | 検証に通った anchor の時刻の集合(§9.1) | 判定の記録 |
| Server_Anchored_At | 派生値。`min(Valid_Anchor_Timestamps)`(§9.1) | 判定の記録 |
| Attempt_Status | USABLE、または §6.2 の原因コード | 判定の記録 |

- Server_Anchored_At は**生データの欄ではない**。G と R の個別の時刻と証拠を残したうえで、そこから決まる値である。片方の anchor の時刻だけを残して、もう片方を消すことはしない。
- 「実行した時刻」だけを示す証拠(外部の scheduler の実行記録など)は、それだけでは anchor にならない(§9.5)。

### 3.3 Acquisition_Manifest(追加)

取得 1 回ごとに、anchor より前に manifest を 1 つ作る。G と R は、どちらもこの manifest を anchor する。

- 中身: Target_Origin、Acquisition_Path_ID、Execution_ID、Retrieved_At_Runner、Content_SHA256、原ファイルの repository 内の path、Clock_Check_Pre。
- 正規のバイト列: key を固定の順に並べた JSON、UTF-8、改行は LF、末尾に改行を 1 つ。正規化の手順は V2 の Code_SHA の対象にする。
- manifest は、anchor を取ったあとに書き換えない。anchor に関係する情報(token、API 応答、Clock_Check_Post)は、別のファイル(anchor の記録)に書く。manifest に token を入れると、hash が循環するからである。
- こうすると、Retrieved_At_Runner の値そのものも anchor に縛られる。anchor を取ったあとで Retrieved_At_Runner を書き換えれば、Manifest_SHA256 が合わなくなる。

結合の経路:

```
G:  activity の記録 → commit → tree → manifest のバイト列 → Content_SHA256 → 原ファイルのバイト列
R:  timestamp token の messageImprint → Manifest_SHA256 → manifest のバイト列 → Content_SHA256 → 原ファイルのバイト列
```

### 3.4 使えるかの判定(決定済みの部分と未定の部分)

取得 1 回が USABLE であるのは、次がすべて成り立つときである。

```
(1) provenance が完全で、照合に通る                                      (§3.2、§3.3)
(2) 時計の健全性の検査に通る:  max(|e_lo|, |e_hi|) ≤ ε                  (§10.3)
(3) 時計の不確かさを入れても窓の中:
        Retrieved_At_Runner − e_hi > T_info − 6h
        Retrieved_At_Runner − e_lo ≤ T_info                              (§10.4)
(4) 有効な anchor が 1 つ以上ある:  |Valid_Anchor_Timestamps| ≥ 1         (§9.1)
(5) 前後関係の整合:  Retrieved_At_Runner ≤ Server_Anchored_At + ε          (§10.5)
(6) anchor が遅れていない:  Server_Anchored_At ≤ T_info + δ,  δ = 300 秒   (§9.4)
```

- δ = 300 秒は決定。**ε は未定**(§10.6)。ε が決まるまで、(2)、(3)、(5) は Freeze できない。
- (3) は v0.2 の `Retrieved_At_Runner ∈ (T_info − 6h, T_info]` を、時計の不確かさの分だけ内側に狭めたものである。e_lo = e_hi = 0 なら v0.2 と一致する。

## 4. 対象にする orchestration(v0.1 から変更なし)

```
CFTC acquisition → feature readiness → S0 parent readiness → M1 issuance
```

S0 のモデルは変えない。対象は、この順に行う運用の仕組みである。

## 5. 候補と位置づけ(v0.1 から変更なし)

- **主候補**: A(GitHub の中で、早い時刻に何度も起動する)、C(外部の独立した trigger)、E(冗長化。本命だが、採用はまだ Freeze しない)、F(監視と通知)。
- **補欠**: B、D。
- **最初に比べる構成**: A + C を、F で監視する。

## 6. 試験の単位と、SUCCESS / FAILURE への写像(決定を反映)

### 6.1 試験の単位

- 1 回の試験は、M1 の Origin がある T_info の窓 1 つ(試験窓)。
- 試験窓 w に属する取得は、manifest の Target_Origin が w の Origin であるものとする。時刻で振り分けない。窓の外で行われた取得も、その窓の取得として数えて OUTSIDE_WINDOW と記録するためである。

### 6.2 取得 1 回ごとの判定(固定した順に検査する)

検査は次の順に行い、最初に通らなかった段階の原因コードを、その取得の Attempt_Status とする。すべて通れば USABLE。

| 順 | 検査 | 通らなかったときのコード |
|---|---|---|
| 1 | §3.2・§3.3 の記録がそろい、manifest の正規化と Content_SHA256 の再計算が一致し、Execution_ID と Acquisition_Path_ID が実在の記録と一致する | PROVENANCE_INVALID |
| 2 | 取得した中身が、V1 と同じ内容の検査に通る | CONTENT_INVALID(追加。§11 の論点 7) |
| 3 | 時計の健全性の検査(§3.4 の (2)) | CLOCK_INVALID(sanity) |
| 4 | 時計の不確かさを入れた窓の判定(§3.4 の (3)) | OUTSIDE_WINDOW |
| 5 | 有効な anchor が 1 つ以上ある(§3.4 の (4)) | NO_VALID_SERVER_ANCHOR |
| 6 | 前後関係の整合(§3.4 の (5)) | CLOCK_INVALID(consistency) |
| 7 | anchor の遅れ(§3.4 の (6)) | ANCHOR_LATE |

### 6.3 試験窓の判定

```
試験窓 w が SUCCESS  ⇔  w に属する取得のうち、Attempt_Status = USABLE のものが 1 つ以上ある
それ以外は すべて FAILURE
```

- 使う snapshot は、USABLE のもののうち Retrieved_At_Runner が最も遅いもの(§3.1 の規則のまま)。
- FAILURE の窓には、原因コードを記録する。
  - w に属する取得が 1 つもない: **NO_ACQUISITION**
  - 取得はあるが USABLE がない: 検査の順で**最も先まで進んだ取得**のコードを主な原因とする。同じ段階で止まった取得が複数あれば、Retrieved_At_Runner が最も遅いものを採る。ほかの取得のコードも、すべて残す。
  - Decision_Time までに判定が終わらなかった(検証の job が動かなかった、など): **UNDETERMINED**(追加。§11 の論点 7)。これも FAILURE とする。
- **原因コードは分類のためのものであって、Reliability Gate から外す理由にはならない。** どのコードの FAILURE も、§7.2 の失敗の 1 回として数える。2 回続けて FAILURE なら、その時点で即 FAIL。

### 6.4 判定の時点(Decision_Time)

- 試験窓 w の判定は、Decision_Time(w) に 1 回だけ行い、append-only で記録する。
- Decision_Time(w) は、T_info(w) + δ より後で、かつ Origin w の M1 の発行の判定より前とする。具体的な時刻は、V1 の発行の予定時刻に合わせて決める(§11 の論点 8)。
- Decision_Time のあとに証拠が出てきても、FAILURE を SUCCESS に変えない(救済しない)。
- あとの独立の監査で、判定が実装の誤りのために間違っていたとわかった場合は、記録を書き換えず、Determinism / Audit Gate(§7.3)の FAIL として扱う。

## 7. Acceptance Gate(4 群。すべて AND で判定する)

### 7.1 Safety Gate — 1 件でも違反すれば FAIL

1. V1 の repository の data/m1macro/ と ledger/ に、V2 の行が 0 件であること(機械で確認する)。
2. Holdout には、取得でも計算でも一切触れないこと。
3. V2 の取得経路のすべての部分(manifest の正規化、G と R の検証、時計の検査、§6 の判定を含む)が、V2 の Code_SHA の対象であること。
4. すべての取得について、§3.2 の記録と、§3.3 の結合の経路が完全であること。

### 7.2 Reliability Gate(決定済み。数え方を明確にした)

- **(N, k) = (60, 2)**: 60 個の試験窓で、FAILURE が 2 個以下なら PASS。
- **2 個続けて FAILURE なら、その時点で即 FAIL**(60 個の終了を待たない)。「続けて」は Origin の順で数える。
- §6.2・§6.3 のどの原因コードによる FAILURE も、1 個として数える。NO_ACQUISITION、OUTSIDE_WINDOW、ANCHOR_LATE、PROVENANCE_INVALID、CONTENT_INVALID、CLOCK_INVALID、NO_VALID_SERVER_ANCHOR、UNDETERMINED のどれも、除外しない。
- 二項分布で計算した運用特性(むすびさんが独立に再計算して一致を確認):
  - 真の成功率が 90% なら PASS する確率は約 5.30%(誤って採用する確率)。
  - 真の成功率が 98% なら PASS する確率は約 88.13%。
- **この Gate を通っても、成功率が 98% であることを 60 回で証明したことにはならない。** 示すのは「成功率 90% 程度の経路を、約 5% の確率でしか誤って採用しない」ということまでである。
- **上の運用特性は、各回が独立だと仮定した参考値である。Failover Gate を通過しても、独立性が証明されるわけではない。** GitHub の障害のように複数の回にまとめて効く失敗があれば、実際の誤採用の確率は参考値より高くなりうる。
- 2 個連続で即 FAIL とする規則を加えたので、実際に PASS する確率は上の参考値より少し低くなる(より厳しい)。

### 7.3 Determinism / Audit Gate

- snapshot を選ぶ規則が V1 と同じであること。
- hash を計算し直すと一致すること(Content_SHA256、Manifest_SHA256、保存した API 応答と token の hash)。
- G と R の検証を、保存した証拠から独立にやり直すと、同じ Valid_Anchor_Timestamps と Server_Anchored_At になること。
- 経路と実行の ID が、実在の記録と一致すること。
- §6 の判定を、保存した記録から独立にやり直すと、すべての試験窓で同じ SUCCESS / FAILURE と原因コードになること。

### 7.4 Failover Gate(v0.1 から変更なし)

- A だけを止める回と、C だけを止める回を、事前に固定する。
- 止めた回でも、もう一方の経路で窓の中の取得が成立すること。
- この Gate が確かめるのは冗長な経路が働くことであって、各回の独立性ではない(§7.2)。
- 止めた回を Reliability Gate の 60 個に含めるかどうかは未定(§11 の論点 5)。

## 8. 判断済みの事項と残りの論点

| # | 事項 | 状態 |
|---|---|---|
| 1 | Reliability Gate | 決定: (60, 2)、2 個連続の FAILURE で即 FAIL。原因コードは除外の理由にならない |
| 2 | 使えるかの判定 | 決定: §3.4 の 6 条件。**ε は未定** |
| 3 | 正式な anchor | 決定: G または R の 1 つ以上。X は補助の provenance |
| 4 | Server_Anchored_At | 決定: `min(Valid_Anchor_Timestamps)`。有効な anchor が 0 なら NO_VALID_SERVER_ANCHOR → FAILURE |
| 5 | δ | 決定: 300 秒 |
| 6 | G の時刻源 | 決定: commit の author / committer の日時は使わない。server 側の証拠だけを使う |
| 7 | ANCHOR_LATE の扱い | 決定: Reliability の失敗 1 回として数える |
| 8 | V2 の Forward の開始点と評価 | 決定(v0.2 のまま) |
| 9 | 試験の置き場所 | 決定: 別の repository |
| 10 | ε の値と、決め方 | **未定**(§10.6) |
| 11 | TSA の数、accuracy の上限など | **未定**(§9.3 の案を監査していただく) |
| 12 | §11 の論点 1〜8 | **未定** |

## 9. server anchor

### 9.1 Server_Anchored_At の定義(決定)

```
Valid_Anchor_Timestamps = { t_G   | G の検証に通り、manifest との結合を確認できた }
                        ∪ { t_R,i | i 番目の TSA の検証に通り、manifest との結合を確認できた }

Server_Anchored_At = min(Valid_Anchor_Timestamps)     (集合が空でないとき)
集合が空            → NO_VALID_SERVER_ANCHOR → その取得は USABLE でない
```

- 「有効」とは、その anchor に固有の検証(§9.2 または §9.3)に通り、**さらに対象の Content_SHA256 との結合まで確認できた**ことをいう。時刻の文字列があるだけでは有効にならない。
- G と R は同じ格ではない。それぞれ別の検証手順を持ち、どちらの手順も Freeze の対象にする。
- min を使う理由: 「最も早く第三者が検証できるようになった時刻」を表すため。また、「有効な anchor が 1 つ以上あればよい」という採用の規則と論理的に一致する。§3.4 の (6) は「T_info + δ までに有効な anchor が 1 つでもある」と同じ意味になる。
- §3.4 の (5) は min に対して検査する。min がこの条件を満たせば、ほかの anchor の時刻もすべて満たす。

### 9.2 G — GitHub の server 側の証拠(検証の手順)

**時刻源**

- 使うのは、GitHub の repository activity API(`GET /repos/{owner}/{repo}/activity`)の記録の timestamp だけ。これは GitHub が push を受け付けたときに server 側で記録する値である。
- **commit の author date と committer date は、正式な anchor に使わない。** どちらも push する側が自由に書けるからである。記録はしてよいが、判定には使わない。

**取得の側(acquisition の run)で行うこと**

1. 原ファイルと manifest を、1 つの commit に入れる。anchor の記録(R の token を含む)も同じ commit に入れてよい。manifest を変えないので循環しない。
2. V2 の repository の決まった branch に push する。この branch には force push と削除を禁止する設定をかける。

**検証の側(取得とは別の job)で行うこと**

1. activity API を呼び、応答のバイト列を**そのまま**保存し、その SHA-256 を記録する。呼んだ時刻(runner の時計)と HTTP の status、応答 header の Date も記録する。
2. 次を満たす記録 a を探す。
   - a.ref が決まった branch で、a.activity_type が push、または branch を作った最初の push を表すもの(F11-a: activity API では、branch の最初の push が push ではなく branch_creation として記録される)。
   - commit C(manifest を含む commit)が a.after と同じか、a.after の祖先である。
   - C が a.before と同じでも、a.before の祖先でもない(C はこの push で初めて branch に入った)。
3. 条件を満たす記録が複数あれば、timestamp が最も早いものを採る。force push を禁止しているので、通常は 1 つである。
4. 結合を確認する: C の tree の中の manifest の path にある blob を読み、§3.3 の正規化をやり直して一致を確認し、manifest の Content_SHA256 と、同じ tree の原ファイルのバイト列の SHA-256 が一致することを確認する。
5. すべて通れば、t_G = a.timestamp。

**G が有効にならない場合**

- 条件を満たす記録が見つからない、結合が確認できない、API が失敗した。
- Decision_Time までに検証の job が実行されなかった。

**保存した API 応答の位置づけ(監査の上での注意)**

- 保存した応答は、自分で保存したものなので、それだけでは第三者の証拠にならない。研究者の側で書き換えることができるからである。
- そこで、G は**検証の job が API から直接取り直して確認できた場合に限り**有効とする。保存した応答は、その確認の記録と、後の監査のための控えとして使う。
- activity API の記録の保持期間は保証されていない。あとの監査で取り直せなくなっても、Decision_Time の時点の判定は変えない(§6.4)。ただし、その場合の後の監査は、保存した応答と、それが入った commit の G・R に頼ることになる。保存した応答の commit にも R を付けることを推奨する(§11 の論点 4)。

### 9.3 R — RFC 3161 の時刻証明(Acceptance Requirements と検証の手順)

**要求の仕方(取得の側)**

- messageImprint は `SHA-256(manifest の正規のバイト列)` = Manifest_SHA256。hashAlgorithm は SHA-256(OID 2.16.840.1.101.3.4.2.1)。
- 要求ごとに nonce を付け、certReq = true にする。
- 要求を送った時刻と、応答を受け取った時刻(runner の時計)を記録する。§10 の時計の検査にも使う。
- 応答の DER のバイト列をそのまま保存し、その SHA-256 を記録する。

**TSA の Acceptance Requirements(候補を選ぶ前に固定する)**

| # | 要件 |
|---|---|
| R-ACC-1 | RFC 3161 の TimeStampResp を返す。状態が granted(または grantedWithMods で、変更の内容が記録されている) |
| R-ACC-2 | messageImprint に SHA-256 を受け付ける。SHA-1 の imprint しか返さない TSA は不可 |
| R-ACC-3 | token の署名の algorithm が SHA-256 以上。SHA-1 による署名は不可 |
| R-ACC-4 | TSTInfo に **accuracy** がある。その値が A_max 以下(A_max は未定。§11 の論点 2) |
| R-ACC-5 | **genTime** を UTC で返す。秒の小数があれば、その桁のまま記録する。丸めない |
| R-ACC-6 | 要求の nonce を応答にそのまま返す |
| R-ACC-7 | 署名に使った証明書を token に入れる(certReq に応える)。署名者の証明書を ESSCertID / ESSCertIDv2 で token に結び付けている |
| R-ACC-8 | TSA の policy の OID が決まっていて、公開されている。使う OID を固定し、記録する |
| R-ACC-9 | 署名の証明書の extendedKeyUsage が timeStamping だけ(critical) |
| R-ACC-10 | **取得の時点で**、証明書の鎖(root まで)と、失効の情報(CRL または OCSP の応答)を取得して保存できる |
| R-ACC-11 | token、署名、messageImprint、hash algorithm、証明書の鎖を、**TSA に問い合わせずに、後から独立に再検証できる**(保存した資料と OpenSSL などの一般的な実装だけで) |
| R-ACC-12 | HTTPS / TLS が正しいことは、token の正しさの根拠にしない。token は署名だけで検証する |
| R-ACC-13 | 公開されている可用性の情報、運営者、利用の条件(回数の制限など)が記録できる |

**数の案**

- **運営者も root の CA も異なる TSA を 2 つ使う**(R1、R2)。どちらも同じ manifest に対して要求する。
- 有効な anchor は G、R1、R2 の 3 つのうち 1 つ以上あればよい(§9.1)。TSA が 1 つ落ちても R は残り、GitHub が落ちても R は残る。
- 具体的な TSA は、上の要件を Freeze したあとで選ぶ。この版では選ばない。

**検証の手順(検証の側)**

1. 保存した DER を読み、状態、TSTInfo(policy、messageImprint、serialNumber、genTime、accuracy、nonce)を取り出す。
2. messageImprint の hashAlgorithm が SHA-256 で、hashedMessage が Manifest_SHA256 と一致する。
3. nonce が要求の nonce と一致する。
4. 署名を、保存した証明書の鎖で検証する(例: `openssl ts -verify -in <token> -digest <Manifest_SHA256> -CAfile <root> -untrusted <中間>`)。検証の時刻は genTime とし、保存した失効の情報で、その時点に証明書が失効していなかったことを確認する。
5. policy の OID、accuracy ≤ A_max、署名の algorithm を確認する。
6. 結合を確認する: manifest の正規化をやり直して Manifest_SHA256 と一致し、manifest の Content_SHA256 と原ファイルの SHA-256 が一致する。
7. すべて通れば、t_R,i = genTime。

### 9.4 δ(決定: 300 秒)

- **δ = 300 秒。**
- この値は、V1 の 6 件の実測(2〜5 秒)から導いたものではない。6 件は少なく、しかもすべて push が 1 回目で通った場合なので、遅れの分布の上限をこの実測だけから推定することはできない。
- δ = 300 秒は、通常の commit・push・TSA の処理に十分な運用の余裕を与えつつ、T_info からかなり遅れて証拠になった取得を除くための、**保守的な監査上の上限**として事前に固定する。
- V2 の試験 telemetry を見てから変えない。

### 9.5 X — 外部の scheduler / provider の実行記録(補助)

- X は Execution_ID の裏付けとして記録する。正式な anchor にはしない。
- 理由: 実行した時刻は示せても、取得した中身との結合を X だけでは得られない(§3.2)。
- X の記録と Execution_ID が食い違えば、PROVENANCE_INVALID とする。

## 10. runner の時計の健全性(独立の要件。ε は未定)

### 10.1 なぜ独立の要件にするか

- §3.4 の (3) は runner の時計の値で窓の判定をする。δ は窓の上端の側(取得が遅すぎる場合)を server 側の時刻で押さえるが、**窓の下端の側**(取得が T_info − 6h より前だった場合)は、anchor では押さえられない。早すぎる取得は、anchor の時刻も早いので、δ の条件に通ってしまうからである。
- したがって、runner の時計の誤差を、取得のたびに外部の時刻で測り、証拠として残す必要がある。

### 10.2 時計の誤差のモデル

- 真の時刻を t、runner の時計の値を r(t) = t + e とする。e が runner の時計の誤差である。
- 外部の時刻源に問い合わせ、runner の時計で送った時刻 r_send と受け取った時刻 r_recv を記録し、応答の中の外部の時刻を S とする。外部の時刻源の不確かさ(自分の時計の誤差と、表示の桁)を u_S とする。
- 外部の時刻 S は、真の時刻で送ってから受け取るまでの間に付けられたので、次が成り立つ。

```
e ∈ [ r_send − S − u_S ,  r_recv − S + u_S ]
```

- 幅は RTT + 2·u_S である。RTT が大きい測定は、それだけ誤差の幅が広くなる。

### 10.3 測定の手順(案)

- 取得の**直前**(Clock_Check_Pre)と**直後**(Clock_Check_Post)に測る。
- 時刻源の候補:
  - (a) R の TSA の応答の genTime。u_S は token の accuracy。R の要求そのものが Clock_Check_Post を兼ねられる。
  - (b) 独立した複数の host の HTTPS の応答の Date header。表示は秒の桁なので、u_S は 1 秒に、その host の時計の誤差を加えたものになる。後者は公表されていないことが多い。
  - (c) NTP の問い合わせ。GitHub の runner などの環境から NTP が使えるかは確認していない(実現できるかの確認が必要)。
- 各回の測定から e の区間を出し、直前と直後の区間を**合わせた範囲**(区間の和の最小と最大)を [e_lo, e_hi] とする。取得の間に時計が動いた分も含めるためである。
- 健全性の条件(§3.4 の (2)): `max(|e_lo|, |e_hi|) ≤ ε`。満たさなければ CLOCK_INVALID(sanity)。時刻源に問い合わせられなかった場合も CLOCK_INVALID(sanity)とする。
- どの時刻源を正式に使い、いくつ要求するかは未定(§11 の論点 1)。

### 10.4 窓の両端に時計の不確かさを入れる

真の取得の時刻は [Retrieved_At_Runner − e_hi, Retrieved_At_Runner − e_lo] のどこかにある。この区間の全体が窓の中にあることを要求する。

```
下端:  Retrieved_At_Runner − e_hi  >  T_info − 6h
上端:  Retrieved_At_Runner − e_lo  ≤  T_info
```

- 満たさなければ OUTSIDE_WINDOW。
- 窓の端の近くで、時計の不確かさのために窓の中か外か決められない取得は、使わない(fail-closed)。窓の幅 6 時間に対して、ε が秒の単位なら、狭まる分はごくわずかである。

### 10.5 前後関係の整合(§3.4 の (5))

```
Retrieved_At_Runner ≤ Server_Anchored_At + ε
```

- anchor は取得のあとでしか付けられない。この条件が破れていれば、runner の時計か anchor の時刻のどちらかがおかしいので、CLOCK_INVALID(consistency)とする。どちらがおかしいかは区別しない。

### 10.6 ε(未定)と、決め方の案

- ε は、runner の時計の誤差として許す大きさの上限である。§3.4 の (2) と (5) で同じ ε を使う。
- V1 の push の遅れ(2〜5 秒)は、時計の誤差とは別の量なので、ε の根拠にしない。
- **決め方の案**: Reliability の試験の前に、**時計の検査だけを行う較正の期間**を、期間と手順を事前に宣言したうえで設ける。
  - 較正の期間に測るのは、§10.3 の e の区間だけ。CFTC の取得の成否や、試験窓の SUCCESS / FAILURE は見ない。
  - 較正の期間のデータは、Reliability Gate の 60 個に入れない。
  - ε は、較正の結果と時刻源の u_S から、事前に決めた式で出し、Reliability の試験の前に固定する。式そのものも較正の前に固定する。
- この案を採るかどうか、採る場合の式は、§11 の論点 1 でむすびさんに判断していただく。

## 11. この版でむすびさんに判断してほしいこと

1. **時計の検査**: 正式な時刻源((a) TSA の genTime、(b) 複数の host の Date header、(c) NTP)と、その数。§10.6 の較正の期間の案を採るか。採るなら、ε を出す式。
2. **A_max**: TSA の accuracy の上限。候補は 1 秒。accuracy を返さない TSA は R-ACC-4 で不可になる。
3. **TSA の数**: 運営者と root の CA が異なる 2 つ(案)でよいか。
4. **G の位置づけ**: G は、検証の job が API から直接取り直して確認できた場合に限り有効とする案(§9.2)でよいか。保存した API 応答の commit にも R を付けることを要件にするか。
5. **Failover の回**: A だけ、または C だけを止めた試験窓を、Reliability Gate の 60 個に含めるか。含めないなら、試験の総数と順番をどう固定するか。
6. **窓を狭める規則と V1 の関係**: §10.4 で、時計の不確かさの分だけ窓を内側に狭める。V1 の凍結した窓の規則を変えるものではなく、V2 の provenance の基準として扱ってよいか。
7. **追加した原因コード**: CONTENT_INVALID(中身の検査に通らない)と UNDETERMINED(Decision_Time までに判定が終わらない)を加えた。どちらも FAILURE。よいか。
8. **Decision_Time**: T_info + δ より後で、M1 の発行の判定より前、とした。具体的な時刻を、V1 の発行の予定に合わせて次の版で決めるか。
