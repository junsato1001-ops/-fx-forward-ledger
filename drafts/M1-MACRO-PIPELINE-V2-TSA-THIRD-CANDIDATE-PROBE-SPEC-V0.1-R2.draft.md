# M1-MACRO-PIPELINE-V2 — TSA Third-Candidate Probe Spec(DRAFT V0.1, revision 2)

- 状態: **DRAFT V0.1, revision 2**(Claude、2026-10-28)。むすびさんの差分監査待ち。probe はまだ実行しない。
- revision 1(V1 repository commit 1dd2b20c、blob 97a21e7a)からの変更(むすびさんの監査、2026-10-28 18:35 JST): **F-TC-S1** 判定の集合を Part 2 §6.2 の check の番号に統一(§1、§6)、**F-TC-S2** 3 区分の条件を厳密化(§6)、§5.3 の T2 を「保存した鎖についての観測」と明記。測る項目・対象の局・段階は変えていない。revision 1 は drafts/ にそのまま残す。
- 区分: **PROBE / NON-FORMAL / PRE-SELECTION**。Calibration でも受け入れの試験でもない。
- **独立の新しい probe** である。凍結した TSA-PROBE-SPEC V0.1(C-DC・C-GS、P1 完了、P3 は 2026-10-29 00:41 UTC から)は、閉じた事前登録としてそのまま残し、ここで拡張しない(むすびさんの指示、2026-10-28 18:32 JST)。
- 上位(凍結済み、この記録で変えない): Requirements V0.7 §9.3、Part 2 V0.4 §6、Part 4 V0.2 §5、TSA-PROBE-SPEC V0.1(測り方・読み方の規則の参照元)。
- 関連: 第 3 候補の調査の記録 DRAFT v0(V1 repository、commit 32d89d06、blob 87f0f3a3)。優先の順 C-CT → C-DCEU → C-JP(むすびさん承認)。
- この記録は、probe を**実行する前に**、何を、どこで、何回、どう測り、結果をどう読むかを固定する。

---

## 1. 目的と範囲

- 対象は **C-CT(Certum、`http://time.certum.pl`)だけ**。
- この仕様は**第一段階だけ**を固定する: 5 つの token による P1 相当の検査(**Part 2 §6.2 の checks 1–10 と 12(a)**。以下「対象の checks」)。
- **48 時間の新しさの観測(P3 相当)は、この仕様に含めない。** 第一段階で hard failure(R-ACC の不通)がない場合にだけ、別の仕様を新しく作り、監査と Freeze を経てから行う(二段階方式)。
- R-ACC-13(量・頻度の許可)は probe で測らない。Certum への書面の確認で扱う(§8)。
- **Part 2 の検査 11 は変えない。** TSA-F1 の判断は、C-DC・C-GS の P3 の完了の後に行う。

## 2. 分離の規則(TSA-PROBE-SPEC V0.1 §2 と同じ)

- 予測・forecast を作らない。M1 のコード・特徴量・ledger を読まない。
- V1 の repository に書かない。V1 の credential を持たない。
- Calibration・Acceptance の分母に入れない。probe の token を R として、どの Origin の anchor にも使わない。
- Holdout に触れない。
- 測るのは、token・証明書の鎖・OCSP・CRL・時刻・到達性だけ。
- **進行中の C-DC・C-GS の P3 に影響を与えない**: P3 が使う `probe/tsa_probe.py`・`probe/tsa_probe_config.json`・`.github/workflows/tsa-probe.yml` を変更しない。結果は `probe/tsa/` と別の場所に置く。

## 3. 実行の場所と道具

- V2 repository の GitHub-hosted runner(`ubuntu-24.04`。image の版を記録する)。経路 A だけ。
- **script**: 実装の監査に PASS した `probe/tsa_probe.py`(blob 67777db1…、SHA-256 f15735c2…)を**変更せずに**使う。新しい挙動は足さない。
  - 設定は**別の config の file**(例: `probe/tsa_third_config.json`)を、script の環境変数 `TSA_PROBE_CONFIG` で渡す。
  - 結果の置き場所は script の `--out-root` で **`probe/tsa-third/`** にする。
- **workflow**: 別の file(例: `.github/workflows/tsa-third-probe.yml`)。手動の起動(workflow_dispatch)だけで、**schedule を持たない**。mode は p1・p4・summary だけを受け付ける。権限は既存の workflow と同じ(この repository の `GITHUB_TOKEN`、`contents: write`、secret なし)。commit の step は `probe/tsa-third/` の外の変更を拒否する。
- 実装(新しい config と workflow)は、この仕様の Freeze の後に作り、実装の監査に PASS してから main に入れて実行する。

## 4. 対象の局

| ID | endpoint | 運営者 | 文書にある鎖 |
|---|---|---|---|
| C-CT | `http://time.certum.pl` | Asseco Data Systems S.A.(CERTUM) | Certum Timestamp 2025 ← Certum Timestamping 2021 CA ← Certum Trusted Network CA 2(調査の記録の [S1]) |

## 5. 測り方(TSA-PROBE-SPEC V0.1 §5.1〜§5.3・§5.5 と同じ)

### 5.1 共通の要求

- TimeStampReq: version 1、SHA-256、nonce(OS の乱数の 64 bit の正の整数)、certReq = TRUE、**reqPolicy は付けない**。
- messageImprint = `SHA-256("M1-MACRO-PIPELINE-V2 TSA PROBE " + Probe_Run_ID + " " + 局の ID + " " + 連番)`。
- HTTP の時間切れ 30 秒、失敗したら 3 秒後に 1 回だけ再試行。それ以上は足さない。
- HTTP 429・403・503、または PKIStatus が 0(granted)・1(grantedWithMods)以外なら、**再試行せずに**その run の残りの要求をやめる(F-TP-I1 の修正後の挙動)。
- 要求の直前と応答の直後の runner の時刻(UTC、マイクロ秒)を記録する。

### 5.2 P1 相当(1 回だけ。手動の起動)

- C-CT に 5 回、要求の間を **20 秒以上**あけて要求する。TSA への要求は最大 10 回(再試行を含む)。
- 保存と記録は TSA-PROBE-SPEC V0.1 §5.2 と同じ(tsq・tsr の DER、HTTP の status・header、`openssl ts -reply -text`、status・policy・accuracy・genTime の文字列・nonce・imprint・署名の algorithm・ESSCertID(v2)・token の中の証明書)。
- 2 回目の P1 は起動しない(script が拒否する)。

### 5.3 証明書と鎖(P2 相当)

- V0.1 §5.3 と同じ。署名者・中間の証明書の EKU・AIA・CDP・発行者・serial・有効期間、root までの鎖の DER と SHA-256 の指紋、OS の trust store にあるか(参考)。
- **鎖の root が GlobalSign の root(Root CA - R6 など)に繋がらないこと**(T2)を、保存した鎖の subject・issuer・指紋で記録する。これは**この probe で保存した鎖についての観測**として記録する。「Certum に GlobalSign の root へ至る別の鎖が存在しない」という、すべての PKI の経路についての否定の証明にはしない。

### 5.4 失効の情報(1 回だけ)

- V0.1 の P1 と同じく、5 つの token の後に、署名者と中間の証明書の OCSP と CRL を 1 回ずつ取得する(check 12(a) と P4 の資料)。
- 発行の時刻(producedAt・thisUpdate)と token の genTime の関係は**記録するだけ**で、この仕様では新しさの判定をしない(1 回の観測から一般化しない)。

### 5.5 P4 相当(ネットワークなし)

- V0.1 §5.5 と同じ。保存したものだけで、ネットワークを切った状態で `openssl ts -verify` と、OCSP・CRL の署名の検証をやり直す。

## 6. 結果の読み方(事前に固定する)

- Part 2 §6.2 の検査 1〜10 と 12(a) を機械的に当てはめる(V0.1 §6.1 と同じ)。
- 検査 2 の reqPolicy と検査 5 は行わない。観測した policy の OID は **policy discovery の証拠**としてだけ記録する。
- **5 つの token のどれか 1 つでも通らない検査がある R-ACC は FAIL**。都合のよい token を選ばない。
- grantedWithMods は、変更の内容が読めるときだけ受け付ける。
- **第一段階の結論**(この仕様が出すのはこれだけ):
  - **STAGE1_NO_HARD_FAILURE** = 規定の 5 つの token がすべて得られ、その 5 つのどれにも、対象の checks の FAIL がない。第二段階(新しさの観測の仕様)を作ってよい。
  - **STAGE1_HARD_FAILURE** = 得られた証拠だけで、対象の checks の少なくとも 1 つの FAIL が確定した(得られた token が 5 つ未満でもよい。HTTP 200 で返った本文が TimeStampResp として使えない、または PKIStatus が 0・1 以外の場合は check 1 の FAIL)。どの check かを記録する。C-CT はこの probe の範囲で R の候補から外れる見込みとして、TSA Selection に記録する。
  - **STAGE1_NOT_OBSERVED** = STAGE1_HARD_FAILURE を確定できず、かつ規定の 5 つの token を取得できなかったため、第一段階の判定ができない(到達できない、HTTP 429・403・503 による停止など)。同じ仕様で取り直さない。扱いはむすびさんに判断していただく。
  - 3 つの区分は、この順(HARD_FAILURE の確定 → 5 つがそろって FAIL なし → それ以外)で一意に決める。
- §5.4 の失効の情報の時刻は、TSA-F1・TSA-F2 の資料として記録するだけで、第一段階の結論に入れない。
- 判定は check の番号だけで行う。check 10(保存した鎖での署名の検証)は、P4 相当の結果(ネットワークなしの検証)で判定する。
- R-ACC の番号との対応は、判定には使わない(参考: R-ACC-12 は検証の規則で N/A、R-ACC-13 は測らない。§8)。

## 7. 記録

- `probe/tsa-third/<Probe_Run_ID>/manifest.json`: V0.1 §7 と同じ項目(Probe_Run_ID、起動の種類、開始の時刻、runner の image、OpenSSL の版、script の SHA-256、config の SHA-256、**この仕様**の SHA-256、局の一覧、保存した file の SHA-256 の一覧)。
- 集計: script の summary mode を `--out-root probe/tsa-third` で行い、`probe/tsa-third/SUMMARY-<日付>.json` に置く。P3 の項目は空になる(P3 を行わないため)。
- これらを TSA Selection の証拠として参照する。既存の記録は書き換えない。

## 8. この仕様の外のこと — Certum への書面の確認(R-ACC-13)

むすびさんの指示のとおり、次の 5 点を、具体的な数を示して書面で確認する。「利用できます」だけでは R-ACC-13 の証拠にしない。問い合わせは純さんの作業。

1. `http://time.certum.pl` に対して、自動化された RFC 3161 の要求を、研究・システムの運用の目的で送ってよいか。
2. 1 局あたり最大 5,760 回の事前の試験(較正と受け入れの試験)と、採用の後の年間最大約 15,000 回を許すか。
3. 同じ秒に最大 4 回の要求(burst)が起きてよいか。
4. この利用が「私人・非営利・無料」の対象になるか。対象外なら、必要な契約と料金。
5. rate limit・fair-use・自動化されたアクセス・SLA など、上の量を禁止・制限する条件があるか。

- この probe の第一段階(TSA への要求は最大 10 回)を、書面の回答の前に行ってよいかは、むすびさんに判断していただく(§9)。

## 9. むすびさんに判断してほしいこと

1. 監査済みの `probe/tsa_probe.py` を変更せずに、別の config・別の out-root・別の workflow(schedule なし)で動かす構成(§3)。
2. 第一段階の結論の 3 区分(STAGE1_NO_HARD_FAILURE / STAGE1_HARD_FAILURE / STAGE1_NOT_OBSERVED)と、失効の情報の時刻を判定に入れない扱い(§5.4、§6)。
3. 鎖の root が GlobalSign の root に繋がらないこと(T2)を記録する項目(§5.3)。
4. 第一段階(最大 10 回の要求)を、Certum の書面の回答の前に行ってよいか(§8 の末尾)。
