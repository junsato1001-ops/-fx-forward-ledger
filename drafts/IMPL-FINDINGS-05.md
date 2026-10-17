# IMPL-FINDINGS-05 — Freeze 記録の二段階 transaction(F1)、再取得の防止(F4)、開発の盲検の実行 G5〜G8(F5)

- 作成: Claude、2026-10-18(JST)
- 対象のコード: branch `m1macro-dev`、commit `5d1e28f`(candidate ではない。Code_SHA256 は固定していない)。開発の盲検の実行は `85ab1af` で行った(5d1e28f との差は試験のファイル1つだけ)
- 根拠: むすびの IMPL-FINDINGS-04 への判定(2026-10-18): F1 = 案(b) + 二段階の Freeze transaction、F2 = APPROVED、F4 = 取得用 branch の削除 + one-shot guard、F5 = 開発の盲検の実行 G5〜G8 へ進行
- 封印: 実データで β、β の符号、μ、J*、CRPS、予測、M1 と S0 の差は外に出していない。G5〜G8 の出力は Part 4 で固定した allow-list の欄だけ。
- 状態: candidate Freeze NOT YET / Code_SHA256 NOT FROZEN / Formal G1〜G9 NOT STARTED / Freeze-finalization はむすびの監査まで hard stop / Performance Seal INTACT / Historical Reserve Holdout SEALED

## 結論

1. F1 の Freeze 記録の仕組みを実装した。開発の試験は固定したコンテナで 22 項目すべて PASS(run 39053854675)。transaction の形(§1)の監査を求める。
2. F4 の one-shot guard を実装した。取得用の branch は、この作業環境からは削除できなかった(HTTP 403)ので、純さんが GitHub の画面で削除し、削除を確かめた(§2)。
3. F5 の開発の盲検の実行は全 job が完走した。G5・G7・G8 は PASS。**G6 は独立の実装の側で 307 / 4756 件が基準を満たさず FAIL**(本番の実装の証明は全件 1e-13 以内)。独立の実装を直す必要があり、ここで止める(§4 F5-a)。

## ① F1: Freeze 記録の二段階 transaction

ファイル: `m1macro/freeze_record.py`、workflow `.github/workflows/m1macro_freeze_record.yml`(branch `m1macro-freeze` への push で動く)。

### 手順

| 段 | 書くもの | 確かめること |
|---|---|---|
| 0 事前 | なし | コンテナと runner の両方で Code_SHA256 を計算して一致。生成した CODE_MANIFEST_V1 の D10 Gate が PASS。D2 Pre-Freeze Gate が main に対して PASS。A_first(h) を runner でも独立に計算し、コンテナの値と一致。checkout が candidate の commit。正式の関門の結果(`m1macro-gates-results/<Code_SHA256>/`、run_class FORMAL、同じ commit、suite 全 PASS、manifest Gate PASS)がある。GitHub の API で、この run の attempt の run_started_at(サーバーの時刻)を取り、head_sha が candidate であることを確かめる。今の時刻 < min A_first(h)。main に Freeze の3つのファイルのどれかがあれば停止(1つの Version に Freeze は1回) |
| A 記録 | `preregistration/M1-MACRO-IMPL-CODE-V1.freeze.json` | push → 読み戻しでバイトが一致 → その時刻 Record_Reread_At_UTC |
| B COMPLETE | `preregistration/M1-MACRO-IMPL-CODE-V1.freeze_complete.csv` に1行。**Recorded_At_UTC = A の読み戻しが成功した後の runner の時刻** | push → 読み戻しで行がちょうど1回 → その時刻 Marker_Reread_At_UTC |
| C 監査 | `audit_log/m1_macro_freeze_audit.csv` に1行。Anchor_Status、D2_Status、Freeze_Status(FINAL / REJECTED) | push → 読み戻しで行がちょうど1回 |

- T_freeze_recorded := COMPLETE の行の Recorded_At_UTC(むすびの定義どおり)。
- Anchor Gate: Run_Started_At_Server_UTC ≤ Record_Reread_At_UTC ≤ Recorded_At_UTC ≤ Marker_Reread_At_UTC。
- D2 Freeze-finalization Gate: Recorded_At_UTC < A_first(h)、すべての h(厳密)。A_first(h) = T_info(first(h)) − 6 時間(F2)。
- 比較は記録した秒の単位の文字列の値で行う(記録と判定が食い違わないため)。

### Freeze の成立の条件(Forward の発行が使う)

`forward_commit._freeze_ok` を変えた。以前は記録のファイルの Code_SHA256 だけを見ていた。今は main の tree で次のすべてを求める(`freeze_record.is_final`)。

- 記録の Code_SHA256 が、実行中のコードの Code_SHA256 と一致(Forward の compute では、記録の First_Forward_Origin が config と一致することも求める)。
- COMPLETE の行がちょうど1行で、記録のバイト列の SHA-256、パス、Code_SHA256 に結び付いている。
- 監査の行がちょうど1行で、同じ Run_ID・Run_Attempt・Recorded_At_UTC・Record_Reread_At_UTC。Anchor・D2 が PASS、FINAL。
- 監査の行の時刻を読み直して Anchor・D2 を再判定し、A_first を記録の first と窓から計算し直して一致。

### 試験(`test_freeze_record`、一時的な git のリポジトリ)

- 成功 → FINAL。2回目の Freeze は書く前に停止(FREEZE_ALREADY_RECORDED)。
- runner の時計がサーバーの開始より前 → Anchor FAIL、REJECTED、成立しない。
- Recorded_At_UTC = A_first(1D) ちょうど → D2 FAIL(厳密)。1秒前 → FINAL(Marker の読み戻しが A_first より後でもよい)。
- A・B・C の push の失敗、A・B の読み戻しの失敗 → 停止、成立しない(途中まで書いた行は main に残る)。
- 改ざん: 記録のバイト、COMPLETE の重複、監査の時刻・状態・A_first の書き換え、監査の行の削除 → すべて成立しない。
- 記録のファイルだけがある状態では、Forward の compute は REFUSED_NOT_FROZEN のまま(`test_forward_run`)。

### 各時刻の出どころ(むすび 2026-10-18 03:11 の確認事項)

| 時刻 | 取得のコード | 時計 | 外から値を入れられるか |
|---|---|---|---|
| Run_Started_At_Server_UTC | `server_run_start()`: GitHub REST API `GET /repos/{repo}/actions/runs/{run_id}/attempts/{attempt}` の `run_started_at`。応答の head_sha・id・run_attempt が、この run と candidate に一致することを確かめる | **GitHub のサーバー** | 入力の欄はない(push で起動、workflow_dispatch の入力なし)。run_id・attempt は GitHub が設定する環境変数。値を変えるには freeze_record.py か workflow を書き換える必要があり、それは Code_SHA256 を変える(→ 正式の関門の結果と一致せず停止) |
| Record_Reread_At_UTC | `transaction()` の `t_rec = now()`、`now = datetime.now(UTC)` | runner の時計 | 同上(コードを変えない限り不可) |
| Recorded_At_UTC(= T_freeze_recorded) | `recorded = now()` | runner の時計 | 同上 |
| Marker_Reread_At_UTC | `t_mark = now()` | runner の時計 | 同上 |

**判定**: むすびの懸念のとおり、4つのうち3つは同じ runner の時計で、サーバーの独立した anchor は下限の1つ(実行の開始)だけである。したがって、今の Anchor Gate が実質的に保証するのは「runner の時計がサーバーの開始時刻より前に戻っていない」ことまでで、runner の時計が**遅れている**誤差(Freeze を実際より早く見せる方向)は、job の長さの分までしか抑えられない。上限の独立した anchor はない。

**上限の anchor の候補(F1-e、まだ実装していない)**: GitHub の REST API `GET /repos/{repo}/activity` は、main への push ごとに、サーバーが記録した時刻(timestamp)と、push の後の commit(after)を返す。2026-10-18 に実物で確かめた(例: main の push 8ed83c2 → 2026-10-17T15:41:44Z、その commit の committer の時刻 15:41:43Z)。COMPLETE の行を載せた commit の push の時刻を、サーバーの時刻として C の段で取り、Marker_Push_At_Server_UTC として記録できる。そのうえで、

- Anchor: Run_Started_At_Server_UTC ≤ Recorded_At_UTC ≤ Marker_Push_At_Server_UTC
- D2: **Marker_Push_At_Server_UTC < A_first(h)**(COMPLETE の行が main に載った時刻を、サーバーの時計で上から押さえる)

とすれば、境界の判定がサーバーの2つの時刻に挟まれ、runner の時計の誤差に頼らなくなる。ただし、activity の API の反映の遅れ・取りこぼしの扱い(何秒待つか、見つからなければ REJECTED にするか)を決める必要がある。

### むすびに判断を求める点

- **F1-a**: C の読み戻しだけが失敗した場合、監査の行は main に届いているので、main の上では FINAL になる。run は失敗と報告する。「成立は main の状態で決まる」(Part 4 の UNKNOWN_PENDING_REREAD と同じ考え方)としたが、よいか。
- **F1-b**: D2 の比較に使う時刻を、むすびの定義どおり Recorded_At_UTC にした。COMPLETE の行が実際に main に載ったのは Recorded_At_UTC と Marker_Reread_At_UTC の間である。より厳しくするなら、Marker_Reread_At_UTC < A_first(h) も求められる(実際の差は数秒〜数十秒)。どちらにするか。
- **F1-c**: runner の時計がサーバーより進んでいる・遅れている誤差のうち、Anchor Gate で検出できないものは、job の長さ(最大 30 分)以内に限られる。A_first との余裕が 30 分より十分大きければ問題にならない。運用上、Freeze は A_first の少なくとも数時間前に行う、としてよいか(Gate の新しい数値にはしない)。
- **F1-d**: 「正式の関門の結果がある」ことの確認は、suite の全 PASS と manifest Gate の PASS だけを機械で見ている。G5〜G9 の合否は、むすびが結果を監査してから Freeze の branch に push する、という人の手順に頼っている。G5〜G9 の合否の基準も機械の確認に入れるべきか。
- **F1-e**: 上の表のとおり、上限の独立した anchor がない。サーバーの push の時刻(activity の API)を加え、D2 をその時刻で判定する形に変えるか。変えるなら、API に反映されない場合は REJECTED(fail closed)とすることを提案する。

## ② F4: 再取得の防止

- workflow `m1macro_snapshot_acquire.yml` の最初の段に one-shot guard を加えた。main に `data/m1macro/dev_snapshot/manifest.json` がある、または非公開のリポジトリに `m1macro_dev_snapshot/` がある場合、何も取得せずに失敗する。非公開の側に保存する直前にも同じ確認をする。`snapshot_acq.py` も、checkout した tree に canonical の manifest があれば acquire を拒む。
- branch `m1macro-acquire` の削除は、この作業環境からはできなかった。git の push での削除は途中で切断され、GitHub の API での削除は「この経路では書き込みが許されていない」(HTTP 403)。方針の拒否なので、別の経路では試さず、純さんに依頼した。
- guard だけでは防げない場合: guard は、guard を含む commit を push したときにだけ働く。`m1macro-acquire` という名前の branch を古い commit(guard を含まない)で作り直すと、古い workflow が動く。branch の削除でこの経路は今は閉じている。作り直しまで防ぐには、GitHub のリポジトリの設定(Rules)で `m1macro-acquire` という名前の branch の作成を禁止する方法がある(純さんの操作が必要。未実施)。
- 既存の run 39045282957、commit f0606fb、snapshot の来歴はそのまま残る(f0606fb は m1macro-dev の祖先)。
- **削除の完了(2026-10-18 04:10 JST、純さんが GitHub の画面で削除)**。fresh に確かめた結果: `git ls-remote` で refs/heads/m1macro-acquire は 0 件。GitHub の API `GET /branches/m1macro-acquire` は 404(Branch not found)。リモートの branch は main、m1macro-dev、m1macro-dev-results、m1macro-devblind の4つ。f0606fb は m1macro-dev の祖先としてたどれる。取得の workflow の実行は run 39045282957 の1件だけで、削除の前後で新しい実行はない。main は 87b1e82 のまま。

## ③ F5: 開発の盲検の実行 G5〜G8

- 実行: run 39055250042(2026-10-17T17:46:57Z〜23:05:41Z、全 22 job 成功)、branch `m1macro-devblind`、commit 85ab1af、Code_SHA256 `34c0c91b…4bc42`(開発の値。固定していない)
- 結果: branch `m1macro-devblind-results`(commit 55ff2d3)、ディレクトリ `34c0c91b…4bc42/`、run_class.txt = DEVELOPMENT_BLIND
- 読んだのは allow-list の欄だけ(g5_summary、g678_summary、g6_records の t・h・state・反復・差・合否・例外の型)。β、β の符号、μ、J*、CRPS、予測、M1 と S0 の差、G7 の生のハッシュは見ていない(そもそも出力にない)。
- 同じ run の suite: 22/22 PASS。D10 manifest Gate: PASS(72 件、workflow 5件)。D2 Pre-Freeze Gate: FIRST_FORWARD_ORIGIN_NOT_SET で FAIL(この段階では想定どおり)。

| 関門 | 結果 | 判定(開発) |
|---|---|---|
| G5 特徴量・暦 | Origin 8559。F_US・F_JP はすべて OK。F_POS: OK 4714、未収録の期間 3678、Feature Gate で除外 63、公表予定が過ぎた 104。米国債 9204 日(1990-01-02〜2026-10-16)、財務省 12958 日(1974-09-24〜2026-10-15)、CFTC 1062 報告(2006-06-13〜2026-10-13)。Holdout の行 0 | PASS(下の暦の不一致は監査の記録) |
| G6 推定の検証 | (t, h) 10007 件。ESTIMATED 4756、DEFAULT_PARENT 756、NOT_EVALUATED 4495。**本番の証明: 4756 件すべて UB − LB と Φ(β₂) − LB が 1e-13 以内**(最大 1.0e-13 未満、反復は 1 段目最大 55・2 段目最大 12)。**全項目の合格は 4449 / 4756** | **FAIL(独立の実装の側、下の F5-a)** |
| G7 再現 | 10007 件で、実行 A と B の E_Input の SHA-256 の不一致 0、β の SHA-256 または状態の不一致 0 | PASS |
| G8 μ = 0 の行 | 1962 行すべてが S0 の値と一致(不一致 0) | PASS |

**G6 の不合格 307 件の内訳(allow-list の欄だけで分けた)**

| 群 | 件数 | 何が起きたか |
|---|---|---|
| 独立の実装の例外 | 240(1D 225、1W 8、4W 7) | 本番は終わって証明の欄が記録されている。その後の独立の実装(群が 4000 以下のときの `solve_epigraph`)が RuntimeError。理由は「LP の状態が 0 でない」か「200 回で収束しない」のどちらか。設計どおり例外の型の名前だけを記録しているので、どちらかは分からない。t は 2011-12-13〜2026-07-19 に散らばる |
| 独立の実装の証明が 1e-13 に届かない | 67(すべて 1D) | 群が 4000 を超えるときの `solve_kelley_fast` が反復の上限 600 に達して、証明できないまま戻った(合格した同じ方法の反復は最大 56)。UB・β・μ の一致はすべて合格。独立の実装の UB − LB は 1e-13〜1e-12 が 51 件、1e-12 以上が 16 件(最大 1.6e-12) |

- 本番の実装の不合格は 0。どちらの群も、検証のための独立の実装の側の問題である(以前の G3 の開発の試験の欠陥と同じ種類)。
- ただし正式の G6 なら FAIL である。candidate に進む前に、独立の実装を直す必要がある(Impl Part 2 §11 の「実装だけの欠陥の修正」の範囲)。

**G5 の米国の暦の不一致 20 件(2010 年以降、監査の記録だけ、値は変えていない)**

- 「予定どおりなら公表があるはずだが、ない」12 件: Good Friday 11 件(2011、2013、2014、2016〜2020、2022、2024、2025)と、2012-10-30(ハリケーン Sandy による市場の閉鎖)。
- 「予定にない日に公表がある」8 件: 2010-12-31、2021-12-31(1 月 1 日の振替の連邦の休日)、2017-11-10、2023-11-10(Veterans Day の振替)、2021-06-18(Juneteenth の初年の振替)、2025-01-09(国の追悼の日の連邦の閉鎖)、2025-12-24、2025-12-26(大統領令による連邦の閉鎖)。いずれも連邦政府は休みでも債券市場は開いていた日。
- どれも理由が説明できる。日本の暦(2026 年以降)の不一致は 0。

**結果の分離(F5 の仕組み)**

- 正式の関門の結果と混ざらないように、gates の workflow を、branch `m1macro-devblind` からの実行では結果を `m1macro-devblind-results` に書き、run_class を DEVELOPMENT_BLIND と記録するようにした。Freeze 記録は run_class FORMAL の結果だけを受け付ける。
- negative test(commit 5d1e28f、`test_freeze_record.gate_results_negative`、一時的な git のリポジトリの結果の branch に実際に置いて `gate_results()` を呼ぶ): FORMAL → 受理。DEVELOPMENT_BLIND → GATE_RESULTS_NOT_FORMAL。run_class のファイルがない → GATE_RESULTS_NOT_FORMAL。別の commit → GATE_RESULTS_NOT_FOR_CANDIDATE。suite に FAIL → GATE_SUITE_NOT_PASS。manifest Gate が FAIL → GATE_MANIFEST_NOT_PASS。
- 補足: 結果の branch を分ける仕組みは workflow の中の判定(trigger の branch 名)なので、誰かが m1macro-devblind-results の中身を m1macro-gates-results に手で写した場合は防げない。その場合も run_class.txt が DEVELOPMENT_BLIND のままなら拒否される。run_class.txt まで書き換えられると見分けられない(結果の branch への人の書き込みは、正式の関門の手順の外の操作として監査で見る)。

## ④ 新しい Finding

1. **F1-a〜F1-e**(§1): Freeze 記録の細部。特に F1-e(上限のサーバーの anchor がなく、4つの時刻のうち3つが runner の時計)。
2. **F5-a(停止、判断が必要)**: 開発の盲検の G6 で、独立の実装が 307 / 4756 件で基準を満たさない(240 件は例外、67 件は反復の上限)。本番の実装は全件で証明が 1e-13 以内。直すのは独立の実装(m1macro/indep.py)だけで、本番の推定・仕様は変えない。原因を特定するための選択肢:
   - (i) 合成のデータで、群の数・同順位・退化した形を変えて、独立の実装を手元で負荷の試験をする(実データを使わないので封印の外)。
   - (ii) 盲検の出力に、構造だけの診断の欄を加える: 失敗の種類の符号(EPIGRAPH_LP_STATUS_<数>、EPIGRAPH_MAXR、KELLEY_MAXIT、EXACT_LB_NONE の回数)と、群の数・カットの数。値ではないが、Part 4 で固定した allow-list を広げることになるので、むすびの承認が要る。
   - 提案: まず (i)。それで再現できなければ (ii) を求める。修正の後は、開発の盲検の G6 をもう一度通す(G5・G7・G8 も同じ実行で再び出る)。
3. **F5-b(報告)**: G6 の計算時間の合計は約 62 時間(20 に分けて、1 回の実行が約 5 時間 20 分)。1 つの分割は上限 350 分に対して約 5 時間 18 分かかった。正式の関門でも同じ量なので、上限に近い。分割の数を増やすか、上限を延ばすかを、正式の関門の前に決めておく必要がある。
4. **F4**: guard の実装と branch の削除の両方が済んだ(§2)。CLOSED にするかの判定を求める。

## 状態

- D8 / D10 / D2(Pre-Freeze)= development PASS(むすび判定済み)
- F1 = IMPLEMENTED / AUDIT PENDING(F1-a〜e)
- F4 = guard IMPLEMENTED、branch 削除 DONE(確認済み)/ CLOSED の判定待ち
- F5 = development blind G5・G7・G8 PASS、**G6 FAIL(独立の実装、F5-a)**
- candidate Freeze = NOT YET / Code_SHA256 = NOT FROZEN / Formal G1〜G9 = NOT STARTED
- Performance Seal = INTACT / Historical Reserve Holdout = SEALED
