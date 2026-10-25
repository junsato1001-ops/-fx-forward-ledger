# M1-MACRO-PIPELINE-V2 — pipeline 要件メモ(DRAFT v0.1)

- 状態: **DRAFT v0.1**(Claude、2026-10-26)。むすびさんの監査待ち。保存も Freeze もしていない。
- 前版: DRAFT v0(drafts/M2-PREP-V2-PIPELINE-REQUIREMENTS-v0.md、blob ede24e7e…)。v0 は書き換えずに残す。
- v0 からの変更点: むすびさんのレビュー(2026-10-26 05:13 JST、DRAFT REVIEW PASS WITH REVISIONS)の判断 §8-1〜§8-5 を反映した。
  1. 名称と位置づけを決めた(§0)。
  2. 範囲を acquisition / trigger / provenance / issuance orchestration に広げた。S0 への依存も範囲に入れた(§2、§4)。
  3. server 側の時刻を必須にした。時刻の欄は分けて持つ(§3)。
  4. 候補の位置づけを決めた。A・C・E・F を主候補、B・D を補欠とし、最初に比べる構成を「A + C を F で監視」とした(§5)。
  5. Acceptance Gate を 4 群に分けた。Reliability Gate の数値は、試験日数と許容する失敗の数を組にして決める方式にし、選択肢を示した(§7)。
- 根拠: OPS-FORWARD-01(blob 17b02eae…)、OPS-FORWARD-02(blob 052251bc…)、F14-a(V2 PIPELINE-DESIGN FINDING / CONFIRMED)
- このメモではしないこと: V1 の workflow・code・config の変更、V2 の本番の取得、Development Replay、Holdout の計算。

---

## 0. 名称と位置づけ(決定済み)

- **名称(暫定): M1-MACRO-PIPELINE-V2**
- 新しい統計 Trial にはしない。予測モデル、特徴量、推定の方法、評価の仕様は、M1-MACRO-V1 をそのまま引き継ぐ。
- 変えるのは、データを運ぶ配管だけ: **acquisition / trigger / provenance / issuance orchestration**。
- **V1 の Forward は V1 のまま続ける。** V1 の 104 週の確認的な証拠を、途中から V2 に付け替えない。
- Pipeline V2 は別の series として扱い、Forward の開始点を新しく持つ。V2 の series をどう評価するかは別に定める(§8)。

## 1. 観測された事実

v0 の §1 から変更なし。要点は次のとおり。

- 予定されていた起動 10 回のうち、実際に起動したのは 5 回。5 回とも遅れて起動した。15:40Z ちょうどに起動した回は 0 回。
- T_info の窓に入る CFTC の取得は 0 回(5 日中)。そのため FORECAST は 0 件(12 行すべて ABSTAIN_SYSTEM)。
- 3 回とも COMPLETE / ON_TIME で、F_US と F_JP は毎回 OK。
- S0 の schedule run の失敗が 2 回あった。どちらも、後の run で回復している。
- 根本原因は特定していない。遅れの上限や傾向が今後も同じとは限らない。

## 2. 守る原則

1. **V1 は変えない。** V1 の workflow、時刻、取得経路、Code_SHA を後から変えない。
2. **V1 と V2 を分ける。**
   - V2 の設計、試験、試験取得は、V1 の data/m1macro/ と ledger/m1_macro_* に混ぜない。
   - 物理的に分ける: path、branch、repository のいずれかを別にする。
   - 論理的に分ける: V2 の行には、V2 の検証用であることを示す区分を付ける。
3. **救済しない。** V2 の経路で取った snapshot を、V1 の発行に使わない。
4. **範囲を限る。統計モデル、特徴量の定義、評価の仕様は変えない。V2 で変えるのは acquisition / trigger / provenance / issuance orchestration だけ。**
   - CFTC Forward Snapshot Gate の意味(§3)と、S0 のモデル自体も変えない。
5. **基準は事前に固定する。** Acceptance Gate の閾値は、V2 の試験 telemetry を見る前に固定する。
6. **単一障害点を減らす。** 起動の遅れや抜けがどれだけ起きるかは分からない、という前提で設計する。

## 3. 取得の窓と時刻の記録

### 3.1 窓(凍結済みの規則。変えない)

- Origin t の CFTC snapshot として使えるのは、取得の時刻が **(T_info(t) − 6h, T_info(t)]** に入るものだけ。T_info は Origin の日の 03:00 JST(前日の 12:00Z〜18:00Z)。
- 窓の中に複数あれば、最も遅いものを使う。

### 3.2 時刻と出所の記録(必須)

server 側の時刻は**必須**にする。ただし Retrieved_At を server の時刻で置き換えることはしない。少なくとも次の欄を**別々に**持つ。

| 欄 | 意味 |
|---|---|
| Retrieved_At_Runner | 取得した実行環境の時計の値。V1 の Retrieved_At と同じ意味 |
| Server_Anchored_At | 第三者が照合できる server 側の時刻。その取得が、その時点までに存在したことの証拠 |
| Content_SHA256 | 取得した原ファイルの SHA-256 |
| Acquisition_Path_ID | どの経路で取ったか(例: A-gh-cron、C-external) |
| Execution_ID | 取得した実行の ID(run の ID など)。provenance の照合に使う |

- 「データが使えるかの判定に使う時刻」と「第三者が検証する時刻」を混同しない。二つの時刻の関係の決め方は §8 の論点にする。例えば、Server_Anchored_At が T_info を過ぎた取得を除くかどうか。
- **どの server anchor を使うかは、まだ決めない。** commit の push 時刻(activity API)は、GitHub の中で取得する経路には使える。一方、候補 C(外部から起動)では GitHub の外で取得する可能性がある。全経路に使える server 側の証拠を、設計の段階で比べる。

## 4. 対象にする orchestration(S0 への依存も含める)

V2 の範囲は次の連鎖全体とする。S0 のモデルは変えない。

```
CFTC acquisition → feature readiness → S0 parent readiness → M1 issuance
```

| 段 | V1 の現状 | V1 で観測した弱点 |
|---|---|---|
| CFTC acquisition | GitHub の `schedule` が 1 日 2 回。どちらも窓の終わりに近い時刻 | 起動 5/10、すべて遅延、窓に入る取得 0/5 |
| feature readiness | 発行の run の中で Treasury、MOF、CFTC の公表予定を取得する | この期間は問題なし(F_US、F_JP は毎回 OK) |
| S0 parent readiness | S0 の forward-ledger(`schedule`)の成功が前提 | schedule run の failure が 2 回(後の run で回復) |
| M1 issuance | S0 が成功した後の `workflow_run` で起動する | S0 が失敗すると skipped になり、S0 の後続の成功を待つ |

## 5. 候補と位置づけ(決定済み)

| # | 候補 | 位置づけ | 理由 |
|---|---|---|---|
| A | GitHub の中で、窓の早い時刻から複数回 cron を置く | **主候補** | 起動の機会を増やせる。各回を冪等にできる |
| C | GitHub の外の scheduler から起動する(`workflow_dispatch` / `repository_dispatch`) | **主候補** | GitHub の schedule とは別の failure domain になる |
| E | 冗長化(複数の経路を組み合わせる) | **本命。ただし採用は Freeze しない** | 異なる failure domain を組み合わせられる |
| F | 窓の途中の監視と通知(救済の取得はしない) | **主候補(補助)** | 失敗に早く気づける。原則 3 は守る |
| B | 1 つの長い job が窓の中で取得を繰り返す | 補欠 | job が起動しなければ、全ての取得機会を失う。job 自体が単一障害点になる |
| D | self-hosted runner や外部の host | 補欠 | 機械、回線、電源、時刻同期、保守が新しい単一障害点になる |

**最初に比べる構成: A(GitHub の中の早期・複数回)+ C(独立した外部の trigger)を、F で監視する。**

比べる観点は v0 の §6 と同じ: 監査可能性、障害耐性、凍結との整合、秘密情報、コスト、運用の負担、CFTC への負荷、S0 への依存。

## 6. 試験の単位(提案)

- 1 回の試験 = **M1 の Origin がある 1 つの T_info の窓**。1D の営業日と、1W/4W の日曜が対象。暦の上の毎日ではない。
- 成功 = その窓の中で、正常な取得が 1 つ以上ある。加えて §3.2 の欄がそろっていて、照合に通る。
- 失敗 = それ以外。取得がない場合、窓の外の取得しかない場合、証跡が欠けている場合を含む。

## 7. Acceptance Gate(4 群。試験を始める前に固定する)

### 7.1 Safety Gate — 1 件でも違反すれば FAIL

1. V1 の data/m1macro/ と ledger/ に、V2 の行が 0 件であること(機械で確認する)。
2. Holdout の 5 ペアに、取得も計算も一切触れないこと。
3. V2 の取得経路のすべての部分が、V2 の Code_SHA の対象であること。凍結されていない経路で取った行は 0 件。
4. すべての取得で、provenance(§3.2 の 5 つの欄)が完全に記録されていること。

### 7.2 Reliability Gate — 試験日数と、許容する失敗の数を組で決める

- 成功率だけで決めない。たとえば 30 日の試験で 99% を要求すると、実質は 30 回中 30 回を要求することになる。
- **組 (N 回、許容する失敗 k 回) を事前に固定する。** 判定は「失敗が k 回以下なら PASS」。
- 選ぶ材料として、1 回ごとの真の成功率 p のもとで PASS する確率を、正確な二項分布で計算した。
  - LB95 は「失敗がちょうど k 回のときの、p の片側 95% 下限」。
  - 回どうしが独立という仮定を置いた計算。GitHub の障害のように複数の回にまとめて効く失敗があると、この数字は楽観的になる。その分は 7.4 の Failover Gate で補う。

| N(回) | k | LB95 | p = 0.90 で PASS(誤って採用する確率) | p = 0.95 で PASS | p = 0.98 で PASS | p = 0.99 で PASS |
|---|---|---|---|---|---|---|
| 30 | 0 | 0.905 | 0.042 | 0.215 | 0.545 | 0.740 |
| 30 | 1 | 0.851 | 0.184 | 0.554 | 0.879 | 0.964 |
| 45 | 1 | 0.899 | 0.052 | 0.335 | 0.773 | 0.925 |
| 60 | 2 | 0.899 | 0.053 | 0.417 | 0.881 | 0.978 |
| 60 | 3 | 0.876 | 0.137 | 0.647 | 0.968 | 0.997 |
| 90 | 3 | 0.916 | 0.017 | 0.336 | 0.893 | 0.987 |

- 案 1: **(60, 2)**。p = 0.90 で誤って採用する確率は約 5%。p = 0.98 なら約 88% の確率で PASS する。
- 案 2: **(90, 3)**。誤って採用する確率は約 2%、p = 0.98 で PASS する確率は約 89%。ただし時間がかかる。
- (30, 0) は短いが、p = 0.98 でも PASS する確率は約 55% しかない。
- 合わせて決めるもの: **連続して失敗してよい回数の上限**。案は 1 回(2 回連続で失敗したら FAIL)。

### 7.3 Determinism / Audit Gate

1. snapshot の選び方(窓、最も遅いもの、SHA-256 で同順位を決める)が V1 と同じであること。独立に作った検査で、すべての回について同じ snapshot を選べること。
2. すべての取得について Content_SHA256 を計算し直すと、記録と一致すること。
3. Server_Anchored_At を第三者の手順で取り直すと、記録と一致すること。
4. Acquisition_Path_ID と Execution_ID が、実在する実行の記録と一致すること。

### 7.4 Failover Gate

1. 試験期間の中で、経路を 1 つずつ意図的に止める回を、事前に決めておく。A だけを止める回と、C だけを止める回の両方を含める。
2. 止めた回でも、もう一方の経路で窓の中の取得が成功すること。
3. 止める回の日付と回数は試験の前に固定する。試験の結果を見てから選ばない。

## 8. むすびさんに判断してほしいこと

1. **Reliability Gate の組**: (60, 2)、(90, 3)、またはその他。合わせて、連続して失敗してよい回数の上限。
2. **時刻の関係**: 使えるかどうかの判定は、これまでどおり Retrieved_At_Runner で行うか。そのうえで、Server_Anchored_At が T_info + δ を過ぎた取得は除くか。除く場合の δ の値。
3. **server anchor の候補**: commit の push 時刻(GitHub の中の経路)、外部の時刻認証(RFC 3161 など)、外部 scheduler の実行記録。どれを比べるか。
4. **Pipeline V2 の series の評価**: V2 の Forward の開始点と、確認的な評価をどう定めるか。V1 の 104 週とは別にする。
5. **試験の置き場所**: 別の repository にするか、同じ repository の別の branch / path にするか。物理的な分離の度合いを決める。
