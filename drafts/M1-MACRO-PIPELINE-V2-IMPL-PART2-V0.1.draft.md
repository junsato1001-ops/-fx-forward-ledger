# M1-MACRO-PIPELINE-V2 Implementation Spec — Part 2: Provenance / Clock / Anchor(DRAFT v0.1)

- 状態: **DRAFT v0.1**(Claude、2026-10-27)。むすびさんの監査待ち。Freeze 候補ではない。
- 前の版: v0(blob 69fe4c70…)。書き換えずに残してある。
- v0 からの変更: むすびさんの判断(2026-10-27 01:28 JST、v0 = REVIEW PASS WITH REVISIONS)の 7 点と F-P2-11 を反映した。新しい設計は広げていない。
  1. **F-P2-1(ACCEPT / CLOSE WITH ERRATUM)**: PRE は 6 つの key、CFTC_Source_Year は manifest だけ。Part 1 の本文は変えず、別の記録 Erratum E1 で記録する(§3.1)。
  2. **F-P2-3(ACCEPT / CLOSE)**: runner の時刻の正規の解像度を 1 マイクロ秒と定義し、OS の値を floor でその格子に写す。打ち消し合いを根拠にしない(§2.1)。
  3. **F-P2-4(REVISE)**: 失効の情報は attempt ごとではなく、decision の実行の中で TSA の局ごとに 1 組取得する。その情報自身の署名・有効性・新しさを verify_r で検査する(§6.3)。
  4. **main_entry_time の監査の入力を固定**: decision の証拠に **Audit_Repo_Commit_SHA** を残し、Part 4 は現在の main の HEAD ではなく、その commit から到達できる object だけを使う(§8)。
  5. **F-P2-6(DEFER / NOT BLOCKING YET)**: Execution_ID の実在の確認の interface を、A・C 共通で先に固定した。C の provider に固有の部分は config で後から埋める(§10.6)。
  6. **F-P2-8(REVISE)**: 再試行を含む、すべての要求と応答を保存し、R-ACC に通ったすべての応答を R の有効な候補、RTT ≤ 2.0 秒も満たすすべての応答を時計の測定とする(§4.1、§5、§7.1、§10.5)。
  7. **F-P2-9(ACCEPT / CLOSE)**、**F-P2-7(ACCEPT / CLOSE)**。
  8. **F-P2-11(追加)**: 内部の表現は有理数。出力は有限桁の 10 進で表せる値だけを直列化し、表せなければ fail-closed(§2.1)。
- 前提(Freeze 済み):
  - **M1-MACRO-PIPELINE-V2-REQUIREMENTS-V0.7**(SHA-256 edf27751…、Freeze commit b2571b79…)。以下「Requirements」。
  - **M1-MACRO-PIPELINE-V2-IMPL-PART1-V0.5**(SHA-256 c63a0927…、blob 101f7cd4…、Freeze commit cbb9d609…)。以下「Part 1」。
- この Part の範囲: 正規の直列化、PRE の記録、Acquisition_Manifest、anchor の記録、R1・R2(RFC 3161)、時計の区間、G、`main_entry_time`、Content / Manifest の結合、Part 1 §9.4 の手順 3 が呼ぶ検査の関数。
- **この Part は Requirements と Part 1 を再設計しない。** 決まった数値(δ = 300 秒、ε = 6.0 秒、RTT_max = 2.0 秒、A_max = 1.0 秒)、Gate、状態、時刻を、関数・記録・artifact に落とす。Requirements や Part 1 と食い違う点、どちらも決めていない実装上の選択は、§13 に Finding として分けて書く。凍結済みの文書の文言は変えない。
- 置き場所: この草案は V1 の repository の drafts/ に置く。V2 の実装は V2 repository に置く(Part 1 §3)。
- このメモではしないこと: V1 の変更、TSA の具体的な選定、C2 の provider の選定、較正と試験の開始、Development Replay、Holdout の計算。

---

## 1. この Part が実現するもの

| 出どころ | 内容 | この Part の実現箇所 |
|---|---|---|
| Requirements §3.2、§3.3 | 取得 1 回ごとの記録、Acquisition_Manifest、結合の経路 | §4、§5、§10 |
| Requirements §9.1 | Valid_Anchor_Timestamps、Server_Anchored_At = min | §10.5 |
| Requirements §9.2 | G(activity API、G_CONTEMPORANEOUS_VALID、G_LONG_TERM_SELF_CONTAINED = false) | §8、§9 |
| Requirements §9.3 | R1・R2 の要求、R-ACC-1〜13、検証の手順 | §6 |
| Requirements §10.2〜§10.5 | 時計の誤差のモデル、PRE と POST、窓の両端、前後関係 | §3、§7 |
| Requirements §7.3 | R は保存資料だけで再検証、G は同時点の検証の記録を決定論的に再計算 | §11 |
| Part 1 §7.2 | attempt の手順 1・3・5・6 | §3、§4、§5、§6 |
| Part 1 §9.3 | decision の開始の検査(Stage = "DECISION_START") | §3.3、§7.6 |
| Part 1 §9.4 の手順 3 | 検査 1・3・4・5・6・7 の中身 | §10 |
| Part 1 §9.7 | `main_entry_time(commit C) → Main_Entered_At \| UNRESOLVED` | §8 |

## 2. 共通の規則

### 2.1 時刻の表現と算術

- 時刻はすべて UTC。うるう秒は扱わない(POSIX の秒)。
- **runner の時計の値**(r_send、r_recv、Retrieved_At_Runner、Job_Started_At_Runner など): 形式は `YYYY-MM-DDTHH:MM:SS.ffffffZ`(Part 1 §8.3)。**正規の runner の時刻の解像度を 1 マイクロ秒と定義し**、OS の時計の値を `time.time_ns() // 1000`(floor)でその格子に写す(F-P2-3)。マイクロ秒より細かい桁は、正規の値の一部ではない。
- **TSA の genTime**: token の中の GeneralizedTime の文字列をそのまま保存し(R-ACC-5)、計算には小数の桁をすべて使う。
- **activity API の timestamp**: `^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$` に一致する文字列だけを受け付ける(秒の単位。Part 1 §9.7 の 3)。一致しなければ、その記録は異常として扱う(§8.4)。
- **算術(F-P2-11)**: 時刻と区間の内部の表現は**有理数**(分子と分母の整数の組)とし、浮動小数点を使わない。この Part の計算は加算・減算・比較・最小・最大・絶対値だけで、除算を使わない。
- **区間や差の出力の形式**: 有限桁の 10 進で正確に表せる値だけを、秒を単位とする 10 進の文字列に直列化する。符号は負のときだけ `-`、指数表記は使わず、小数部の末尾の 0 は書かない。0 は `0`。例: `-0.0123`、`1.5`、`0`。
- 有限桁の 10 進で表せない値(分母に 2 と 5 以外の素因数を持つ値)を直列化しようとした場合は、**fail-closed** とする。decision の job は判定をせず、COMPLETE を書かずに終わる(実装の誤りを示すので、Part 4 の監査の記録に残す)。
- 比較は正確な値どうしで行う(丸めない)。

### 2.2 正規の JSON(PRE の記録、manifest、時刻の記録に共通)

Requirements §3.3・§10.3 の「key の順は固定、UTF-8、改行は LF、末尾の改行はちょうど 1 つ」を、次のように一意にする。

- 値はすべて**文字列**(数値・真偽値・null・入れ子を使わない)。
- 文字列は ASCII の印字可能な文字(0x20〜0x7E)だけ。それ以外を含む値は作らない(作ろうとしたら、その attempt は失敗として記録する)。
- key の集合と順序は、記録の種類ごとの schema(§3、§4、§5)で固定する。足りない key、余分な key、順序の違いは不正。
- 直列化: Python の `json.dumps(obj, ensure_ascii=True, indent=1, separators=(",", ": "))` と同じ出力に、`\n` を 1 つ加えたもの。key の順は schema の順。
- **正規性の検査**: バイト列を読み、key の順序を保って解析し、schema と一致し、同じ規則で直列化し直したバイト列が元と一致すること。一致しなければ不正。
- この規則の実装は V2 の Code_SHA の対象にする(Requirements §3.3)。

## 3. PRE の記録と DECISION_START の記録

### 3.1 PRE の記録(Requirements §10.3 のまま)

key と順序(Requirements §10.3 で固定済み。この Part では変えない):

| # | key | 値 |
|---|---|---|
| 1 | Schema_Version | `PRE_V1` |
| 2 | Execution_ID | attempt の Execution_ID(Part 1 §5.4、§6.4) |
| 3 | Target_Origin | `YYYY-MM-DD`(Part 1 §4.2) |
| 4 | Acquisition_Path_ID | `A` または `C` |
| 5 | Stage | `PRE` |
| 6 | Random_Nonce | OS の暗号学的な乱数源から 16 バイトを取り、小文字の 16 進 32 文字にしたもの |

- 保存先: `records/acquisition/<Target_Origin>/<Execution_ID>/anchor/pre_record.json`(Part 1 §3)。
- **CFTC_Source_Year は PRE の記録に入れない。** Part 1 §8.1 の「manifest と PRE の記録に書く」は Requirements §10.3 と食い違うので、Requirements を上位の規範として「manifest にだけ書く」と解釈する。この解釈は、Part 1 の本文を変えずに **Erratum E1**(`preregistration/M1-MACRO-PIPELINE-V2-IMPL-PART1-V0.5.errata.md`)に記録する(F-P2-1)。

### 3.2 PRE の時計の測定

- `messageImprint = SHA-256(PRE の記録の正規のバイト列)` で、R1・R2 のそれぞれに §6.1 の要求を送る。
- 再試行を含む、各要求の r_send・r_recv、要求と応答の DER を保存する(§5)。
- これらの hash と時刻は manifest の Clock_Check_Pre の欄に書く(§4)。manifest が anchor されることで、PRE の測定の記録も anchor に縛られる。

### 3.3 DECISION_START の記録(Part 1 §9.3)

- 形は PRE の記録と同じ 6 つの key。Requirements §10.3 が固定したのは取得の PRE の記録であり、この記録は別の種類である。
  - Schema_Version = `DECISION_START_V1`、Execution_ID = decision の job の Decision_Execution_ID、Target_Origin、Acquisition_Path_ID = decision の job の経路、Stage = `DECISION_START`、Random_Nonce。
- 保存先: `records/decision/<Target_Origin>/<Decision_Execution_ID>/start_record.json`。
- R1・R2 への要求、保存、区間の計算は §3.2・§7 と同じ。開始の判定は §7.6。

## 4. Acquisition_Manifest(Requirements §3.3)

### 4.1 schema(key と順序)

Requirements §3.3 の 7 項目(Target_Origin、Acquisition_Path_ID、Execution_ID、Retrieved_At_Runner、Content_SHA256、原ファイルの path、Clock_Check_Pre)をすべて含み、Part 1 が manifest に書くと定めたもの(CFTC_Source_Year、Content_Check)と、決定論的な再計算に必要なものを加える(§13 の F-P2-2)。

| # | key | 値 | 出どころ |
|---|---|---|---|
| 1 | Schema_Version | `ACQ_MANIFEST_V1` | — |
| 2 | Target_Origin | `YYYY-MM-DD` | Requirements §3.3 |
| 3 | Acquisition_Path_ID | `A` / `C` | Requirements §3.3 |
| 4 | Execution_ID | Part 1 §5.4、§6.4 | Requirements §3.3 |
| 5 | Scheduled_At | 予定の時刻 S(UTC、秒) | Part 1 §5.3、§6.4 |
| 6 | Job_Started_At_Runner | job の開始の runner の時刻 | Part 1 §7.3 |
| 7 | CFTC_Source_Year | `YYYY` | Part 1 §8.1 |
| 8 | Source_URL | 取得した URL | Part 1 §8.1 |
| 9 | Fetch_Status | `OK` / `FETCH_FAILED` | Part 1 §8.3 |
| 10 | Retrieved_At_Runner | 応答の本文を受け取り終えた直後の runner の時刻。FETCH_FAILED のときは失敗が確定した直後の時刻 | Requirements §3.3、Part 1 §8.3 |
| 11 | Content_Path | V2 repository の中の原ファイルの path。FETCH_FAILED のときは空 | Requirements §3.3 |
| 12 | Content_Byte_Count | 10 進の文字列。FETCH_FAILED のときは空 | — |
| 13 | Content_SHA256 | 小文字の 16 進 64 文字。FETCH_FAILED のときは空 | Requirements §3.3 |
| 14 | Content_Check | `OK` / `PARSE_FAILED` / `EMPTY` / `CALENDAR_INTEGRITY` / `NOT_FETCHED` | Part 1 §8.4 |
| 15 | Prev_Accepted_Execution_ID | 検査 3 の「前回」に使った snapshot の Execution_ID。前回がなければ空 | Part 1 §8.5(再計算のため) |
| 16 | Prev_Accepted_Content_SHA256 | 同じ snapshot の Content_SHA256。前回がなければ空 | 同上 |
| 17 | Pre_Record_SHA256 | PRE の記録の正規のバイト列の SHA-256 | Requirements §3.3 の Clock_Check_Pre |
| 18〜21 | Pre_R1_1_Request_SHA256、Pre_R1_1_Response_SHA256、Pre_R1_1_Send_At_Runner、Pre_R1_1_Recv_At_Runner | R1 への PRE の 1 回目の要求の DER の SHA-256、応答の DER の SHA-256、r_send、r_recv。送れなかった・応答がなかった項目は空 | 同上 |
| 22〜25 | Pre_R1_2_* | R1 への 2 回目(再試行。§6.1)について同じ。再試行しなかったときはすべて空 | 同上 |
| 26〜29 | Pre_R2_1_* | R2 の 1 回目について同じ | 同上 |
| 30〜33 | Pre_R2_2_* | R2 の 2 回目について同じ | 同上 |
| 34 | Code_SHA | 実行したコードの V2 の Code_SHA | Requirements §7.1 の 3 |

- 再試行を含む、すべての要求と応答を manifest に書く(F-P2-8)。成功した測定を後から捨てない。
- 保存先: `records/acquisition/<Target_Origin>/<Execution_ID>/manifest.json`。
- `Manifest_SHA256 = SHA-256(manifest の正規のバイト列)`。

### 4.2 作る時点

Part 1 §7.2 の手順 5。手順 1〜4 の結果がそろった後で作り、作った後は書き換えない(Requirements §3.3)。

## 5. anchor の記録(Requirements §3.2)

`records/acquisition/<Target_Origin>/<Execution_ID>/anchor/` に、次を置く。どれも追記のみで、manifest とは別のファイルである(manifest に token を入れると hash が循環するため。Requirements §3.3)。

| ファイル | 中身 |
|---|---|
| `pre_record.json` | §3.1 |
| `pre_R{i}_{k}.tsq`、`pre_R{i}_{k}.tsr` | PRE の要求と応答の DER(i = 1、2。k = 送った順の 1、2) |
| `post_R{i}_{k}.tsq`、`post_R{i}_{k}.tsr` | POST(manifest の anchor)の要求と応答の DER |
| `post_timing.json` | POST の各要求の r_send・r_recv(§5.1) |
| `chain_R{i}/` | 取得の時点で得た、署名の証明書から root までの鎖(PEM、R-ACC-10) |

- 失効の情報は attempt では取得しない。decision の実行の中で、TSA の局ごとに 1 組取得する(§6.3、F-P2-4)。

### 5.1 `post_timing.json` の schema

Schema_Version(`POST_TIMING_V1`)、Execution_ID、Manifest_SHA256、そして i = 1、2 と k = 1、2 のそれぞれについて Post_R{i}_{k}_Send_At_Runner、Post_R{i}_{k}_Recv_At_Runner(R1_1、R1_2、R2_1、R2_2 の順。再試行を含むすべての要求。値がなければ空)。正規の JSON(§2.2)。

- POST の runner の時刻は、manifest の後に測るので、manifest にも TSA にも縛られない。縛るのは、この記録を含む commit が V2 main に入った server 側の時刻だけである(§13 の F-P2-5)。

## 6. R — RFC 3161(Requirements §9.3)

### 6.1 要求(取得の側。不純な手続き)

- TimeStampReq: version 1、messageImprint の hashAlgorithm は SHA-256(OID 2.16.840.1.101.3.4.2.1)、hashedMessage は対象の SHA-256、reqPolicy は config に固定した局ごとの policy の OID、nonce は OS の乱数源からの 64 bit の正の整数(Random_Nonce とは別。Requirements §10.3)、certReq = TRUE。
- HTTP の POST、`Content-Type: application/timestamp-query`。HTTPS の成否は token の正しさの根拠にしない(R-ACC-12)。
- **r_send** は要求を送り始める直前、**r_recv** は応答の本文を受け取り終えた直後の runner の時刻。
- 通信の時間切れは 30 秒(案)。**RTT が 2.0 秒を超えた応答も保存し、anchor としては有効でありうる**。時計の測定としてだけ使わない(Requirements §10.3)。
- 局ごと・段階ごとに、失敗したら 3 秒後に 1 回だけ再試行する(案)。再試行の結果を見て、さらに要求を足すことはしない。再試行を含むすべての要求と応答を保存する(F-P2-8)。
- R1 と R2 は並行して送ってよい。
- 応答を受け取ったら、その局の鎖を組み立てて保存する(§6.3)。失効の情報は attempt では取得しない。

### 6.2 検証の関数(純粋)

```
verify_r(resp_der, req_der, expected_imprint, chain, revocation_set, cfg_tsa) → R_VALID(genTime, accuracy) | R_INVALID(reason)
```

入力はすべて保存した資料と、Code_SHA の対象の config だけ。ネットワークに触れない。同じ入力からは常に同じ出力を返す(Requirements §7.3、R-ACC-11)。

検査の順(最初に通らなかったものを reason にする):

| # | 検査 | reason |
|---|---|---|
| 1 | resp_der が TimeStampResp として読める。status が granted、または grantedWithMods で変更の内容が記録されている(R-ACC-1) | R_PARSE / R_STATUS |
| 2 | req_der が TimeStampReq として読め、messageImprint・nonce・reqPolicy が §6.1 のとおり | R_REQUEST_MISMATCH |
| 3 | TSTInfo の messageImprint の hashAlgorithm が SHA-256(R-ACC-2)、hashedMessage が expected_imprint と一致 | R_IMPRINT |
| 4 | TSTInfo の nonce が要求の nonce と一致(R-ACC-6) | R_NONCE |
| 5 | TSTInfo の policy が cfg_tsa の policy の OID と一致(R-ACC-8) | R_POLICY |
| 6 | accuracy がある、かつ accuracy ≤ A_max = 1.0 秒(R-ACC-4) | R_ACCURACY |
| 7 | genTime が UTC の GeneralizedTime として読める(R-ACC-5) | R_GENTIME |
| 8 | 署名の algorithm が SHA-256 以上(R-ACC-3)。署名者の証明書が ESSCertID / ESSCertIDv2 で token に結び付いている(R-ACC-7) | R_SIGNATURE_ALG / R_ESSCERTID |
| 9 | 署名者の証明書の extendedKeyUsage が timeStamping だけで critical(R-ACC-9) | R_EKU |
| 10 | 署名が、保存した鎖で、cfg_tsa に固定した root の指紋まで検証できる。検証の時刻は genTime | R_CHAIN |
| 11 | revocation_set(§6.3。decision の実行の中で、その局について取得した 1 組)自身が有効である: CRL なら発行者の署名が鎖で検証でき、OCSP の応答なら許された応答者の署名が検証できる。新しさの条件(§6.3)を満たす | R_REVOCATION_INVALID / R_REVOCATION_STALE / R_REVOCATION_UNAVAILABLE |
| 12 | その revocation_set で、鎖のどの証明書も genTime の時点で失効していない。失効の理由が keyCompromise の証明書があれば、日付によらず不可(案) | R_REVOKED |

- 有効なら、genTime(正確な値)と accuracy(秒の正確な値)を返す。
- 使う暗号の library は、実装の候補の段階で決めて版を固定する。Part 4 の監査では、**別の実装**(例: 固定版の OpenSSL の `ts -verify` と、失効の検査)で同じ結果になることを確かめる(§13 の F-P2-9)。

### 6.3 鎖と失効の情報(R-ACC-10。F-P2-4 を改めた)

- **鎖**: attempt の側で、応答の中の証明書と、cfg_tsa に固定した中間・root の証明書から組み立て、PEM で保存する(§5)。
- **失効の情報(決定: decision の実行の中で、局ごとに 1 組)**:
  - canonical な acquisition decision になりうる各 decision の job は、DECISION_START の測定(§7.6)の**後に**、R1・R2 のそれぞれについて、署名者の証明書(と中間の証明書)の失効の情報を、cfg_tsa に固定した OCSP の応答者または CRL の URL から 1 組取得する。
  - 保存先: `records/decision/<Target_Origin>/<Decision_Execution_ID>/revocation_R{i}/`。取得した DER と、取得の要求の URL・HTTP の status を、正規の JSON の meta とともに保存し、SHA-256 を decision の行に記録する。
  - この 1 組で、その decision が評価するすべての attempt(Included_Attempts。Part 1 §9.7)の PRE・POST の token と、DECISION_START の token を検証する。同じ decision の証拠の集合で、同じ局を一貫して検証できる。
- **新しさの条件**(verify_r の検査 11):
  - CRL: thisUpdate が、その局について検証するすべての token の genTime 以上であり、nextUpdate があればそれが取得した時点(runner の時刻)以上である。
  - OCSP の応答: producedAt と thisUpdate が、検証するすべての token の genTime 以上であり、nextUpdate があればそれが取得した時点以上である。status は good。
  - 満たさなければ R_REVOCATION_STALE。
  - CRL の発行の間隔が長い局では、取得した CRL の thisUpdate が窓の中の genTime より前になり、STALE になりうる。TSA の選定では、OCSP を提供しているか、CRL の発行の間隔が十分に短いかを確かめる(TSA の選定の記録の確認項目に加える)。
- **取得できない場合**: 取得の失敗、または STALE の局は、03:19:00 JST まで間隔を置いて取得し直す(§12)。それでも有効な 1 組が得られなければ、その局のすべての token を R_REVOCATION_UNAVAILABLE または R_REVOCATION_STALE とし(その局は anchor にも時計にも使えない)、残りの証拠で判定して COMPLETE してよい。
  - main_entry_time の UNRESOLVED(Part 1 §9.7 の 4。判定をせずに終わる)と扱いが違うのは、UNRESOLVED では「判定に使う attempt の集合」そのものが決まらないのに対し、ここでは集合は決まっていて、ある局の証拠が検証できないだけだからである。検証できない証拠を無効として扱う側は、SUCCESS を FAILURE に変えることはあっても、逆はない(fail-closed)。
  - すべての job が 03:19:00 まで取得し直してから判定するので、どの job が先に COMPLETE するかで結果が変わる場合は、その時間の中で取得できたかどうかの違いに限られる。

## 7. 時計(Requirements §10)

### 7.1 1 回の測定の区間

TSA の応答 m(再試行を含むすべての応答。F-P2-8)について、verify_r が R_VALID を返し、かつ `RTT_m = r_recv − r_send ≤ RTT_max = 2.0 秒` のとき、m は**時計の測定として使える**。そのとき:

```
e_m ∈ [ r_send − genTime − accuracy ,  r_recv − genTime + accuracy ]
```

- r_send・r_recv・genTime・accuracy は**実測の値**を使う。RTT_max と A_max は採否の上限であり、区間の計算には使わない(Requirements §10.6 の判定 2026-10-26)。
- PRE の測定の expected_imprint は Pre_Record_SHA256、POST の測定の expected_imprint は Manifest_SHA256、DECISION_START の測定の expected_imprint は start_record の SHA-256。

### 7.2 attempt の区間

```
clock_interval(attempt) → (e_lo, e_hi) | CLOCK_NO_PRE | CLOCK_NO_POST
```

- PRE の使える測定が 1 つ以上、POST の使える測定が 1 つ以上必要。どちらかが 0 なら CLOCK_NO_PRE / CLOCK_NO_POST(どちらも Requirements §6.2 の検査 3 で CLOCK_INVALID(sanity))。
- `e_lo = min(使える測定の下端)`、`e_hi = max(使える測定の上端)`(Requirements §10.3)。
- 補助の系統(HTTPS の Date、NTP)は記録しても、ここには入れない。fallback しない(Requirements §10.3)。

### 7.3 健全性(Requirements §3.4 の (2))

`max(|e_lo|, |e_hi|) ≤ ε = 6.0 秒`。満たさなければ CLOCK_INVALID(sanity)。

### 7.4 窓(Requirements §3.4 の (3)、§10.4)

```
Retrieved_At_Runner − e_hi > T_info − 6h
Retrieved_At_Runner − e_lo ≤ T_info
```

満たさなければ OUTSIDE_WINDOW。T_info = Target_Origin の日の 03:00:00 JST(= 前日の 18:00:00Z)。

### 7.5 前後関係(Requirements §3.4 の (5)、§10.5)

`Retrieved_At_Runner ≤ Server_Anchored_At + ε`。満たさなければ CLOCK_INVALID(consistency)。

### 7.6 decision の開始の判定(Part 1 §9.3)

```
decision_start_ok(start_record, measurements, Job_Start_At_Runner, Decision_Time) → OK | START_TOO_EARLY | START_CLOCK_UNAVAILABLE
```

- 順序: DECISION_START の要求 → 失効の情報の取得(§6.3)→ この判定。DECISION_START の token も、その decision の revocation_set で verify_r にかける。
- DECISION_START の使える測定(§7.1)が 1 つ以上必要。0 なら START_CLOCK_UNAVAILABLE。
- 使える測定の区間を合わせて [e_lo, e_hi] とし、`Job_Start_At_Runner − e_hi ≥ Decision_Time` なら OK、そうでなければ START_TOO_EARLY。
- OK でなければ、decision の job は判定をせずに終わる(Part 1 §9.3)。

## 8. `main_entry_time`(Part 1 §9.7 の interface)

むすびさんの指示(2026-10-27 01:21 JST): 保存した API の応答から後日に独立に再計算しても同じ値になる、純粋で決定論的な証拠の関数として定義する。

### 8.1 二つの層

| 層 | 中身 | 性質 |
|---|---|---|
| 証拠の取得 `fetch_activity()` | V2 repository の activity API を問い合わせ、応答のバイト列と、ページ送りに必要な header をそのまま保存する | 不純(ネットワーク)。decision の job の実行の中でだけ行う |
| 判定 `main_entry_time(C, pages, repo@Audit_Repo_Commit_SHA, cfg)` | 保存した pages と、V2 repository の **Audit_Repo_Commit_SHA から到達できる** git の object だけから判定する | **純粋**。ネットワークにも時計にも、現在の main の HEAD にも触れない |

### 8.2 証拠の取得

- 問い合わせ: `GET /repos/{owner}/{V2 repository}/activity?ref=refs/heads/{V2 main の branch}&per_page=100`。activity_type で絞らない(push と branch_creation のほかに、異常の種類も見るため。§8.4)。
- ページ送り: 応答の `Link` header の `rel="next"` をたどり、`next` がなくなるまで、すべてのページを読む。最大 100 ページ(V1 の F8-a と同じ)。超えたら取得の失敗。
- 各ページについて、要求の URL、HTTP の status、`Link` header の値、本文のバイト列を、順に保存する。保存先: `records/decision/<Target_Origin>/<Decision_Execution_ID>/activity/page_NNN.{meta.json,body.json}`(NNN = 001 から)。meta は正規の JSON(Schema_Version = `ACTIVITY_PAGE_META_V1`、Request_URL、HTTP_Status、Link_Header、Body_SHA256)。
- 取得の途中で失敗したら、それまでの pages も保存するが、§8.3 の完全性の検査で不完全になる。

### 8.2a 監査に使う repository の状態(Audit_Repo_Commit_SHA)

- decision の job は、判定に使う V2 main を取り込んだ時点の HEAD の commit の SHA を **Audit_Repo_Commit_SHA** として decision の行に記録する。問い合わせ直して取り込み直した場合は、**判定に使った最後の取り込み**の HEAD を記録する。
- Part 1 §9.4 の手順 2 の attempt の列挙、§8.3 の祖先の判定、§9 の結合の確認は、すべて Audit_Repo_Commit_SHA から到達できる object の上で行う。
- Part 4 が後日に再計算するときも、同じ Audit_Repo_Commit_SHA を使う。**現在の main の HEAD を暗黙に読むことは禁止する**。
- V2 main は force push と削除を禁止しているので、Audit_Repo_Commit_SHA とそこから到達できる object は、後日も V2 repository に残る。

### 8.3 判定の関数(純粋)

```
main_entry_time(C, pages, repo@Audit_Repo_Commit_SHA, cfg) → (Main_Entered_At, Activity_ID, Actor_Login, Activity_Type) | UNRESOLVED(reason)
```

手順:

1. **完全性**: pages が 1 ページ目から順につながっていること(各ページの Link の next が、次のページの Request_URL と一致し、最後のページに next がない)、すべての HTTP_Status が 200、すべての本文が JSON の配列として読めること。満たさなければ UNRESOLVED(ACTIVITY_INCOMPLETE)。
2. **記録の集合**: すべてのページの要素を集め、`id` で重複を除く。同じ `id` で中身が違えば UNRESOLVED(ACTIVITY_INCONSISTENT)。
3. **候補**: 次をすべて満たす記録 a を候補とする。
   - `a.ref` が `refs/heads/{V2 main の branch}`。
   - C が `a.after` と同じか、`a.after` の祖先である。
   - `a.before` が 40 個の 0 であるか、または C が `a.before` と同じでも `a.before` の祖先でもない。
   - 祖先の判定は、Audit_Repo_Commit_SHA から到達できる object の上で行う(`git merge-base --is-ancestor` と同じ意味)。
   - C が Audit_Repo_Commit_SHA から到達できないなら UNRESOLVED(NOT_IN_AUDIT_STATE)。
   - `a.after` が Audit_Repo_Commit_SHA から到達できない記録は、候補にしない。force push を禁止しているので、そのような記録は Audit_Repo_Commit_SHA を取り込んだ後の push であり、すでに到達できる C を初めて main に入れた記録ではありえない。
4. **候補がない**なら UNRESOLVED(NOT_FOUND)。decision の job は、これを「まだ反映されていない」として問い合わせ直す(Part 1 §9.7 の 4)。
5. **最も早い候補**: timestamp が最も早いもの(Requirements §9.2)。同じ timestamp の候補が複数あれば、`id` の数値が最小のもの。
6. **異常の検査**(§8.4)に当たれば UNRESOLVED(その reason)。
7. 結果: `Main_Entered_At = a.timestamp`(§2.1 の形式。加工しない)、Activity_ID = a.id、Actor_Login = a.actor.login、Activity_Type = a.activity_type。

### 8.4 異常(fail-closed。案)

| 異常 | reason |
|---|---|
| 最も早い候補の activity_type が push でも branch_creation でもない(force_push、pr_merge、merge_queue_merge など) | ACTIVITY_TYPE_NOT_ALLOWED |
| activity_type と topology が合わない(before が 40 個の 0 なのに branch_creation でない、またはその逆。V1 の F11-a と同じ考え方) | ACTIVITY_KIND_TOPOLOGY_MISMATCH |
| 記録の集合に、V2 main の branch の force_push または branch_deletion がある | BRANCH_HISTORY_REWRITTEN |
| timestamp が §2.1 の形式でない | ACTIVITY_TIMESTAMP_FORMAT |

- V2 main は force push と削除を禁止している(Requirements §9.2)。それでも履歴が書き換えられた記録があれば、祖先の関係による判定が信用できないので、どの commit についても UNRESOLVED にする(§13 の F-P2-7)。
- Actor_Login が経路の許す actor か(A なら `github-actions[bot]`、C なら config に固定した C の push の主体)は、この関数では判定しない。返した値を、§10 の PROVENANCE の検査で使う。

### 8.5 決定論

- 同じ (C, pages, Audit_Repo_Commit_SHA, cfg) からは常に同じ結果になる。使う object は Audit_Repo_Commit_SHA から到達できるものに限るので、その後に V2 main に何が push されても結果は変わらない。
- decision の job が問い合わせ直した場合(Part 1 §9.7 の 4)は、**判定に使った最後の取得の pages** を保存し、判定の行に記録する。Part 4 は、その pages から同じ結果を再計算する。
- activity API の記録の保持期間が過ぎた後でも、保存した pages から同じ結果を再計算できる。ただし、その pages を GitHub が発行したことまでは、保存物だけからは証明しない(G_LONG_TERM_SELF_CONTAINED = false、Requirements §9.2)。

## 9. G(Requirements §9.2)

```
verify_g(attempt, pages, repo@Audit_Repo_Commit_SHA, cfg) → G_VALID(t_G) | G_INVALID(reason)
```

1. C = その attempt の manifest を含む commit(V2 main の履歴で、`records/acquisition/<Target_Origin>/<Execution_ID>/manifest.json` を最初に加えた commit)。
2. `main_entry_time(C, pages, repo@Audit_Repo_Commit_SHA, cfg)` が UNRESOLVED なら G_INVALID(その reason)。
3. **結合**(Requirements §3.3 の G の経路): C の tree の manifest の blob を読み、§2.2 の正規性の検査に通り、その SHA-256 が Manifest_SHA256 と一致する。manifest の Content_SHA256 が、同じ tree の Content_Path の blob のバイト列の SHA-256 と一致する(FETCH_FAILED の attempt では内容の結合がないので G_INVALID(NO_CONTENT))。
4. **同時点**(G_CONTEMPORANEOUS_VALID): pages は canonical な acquisition decision の実行の中で取得したものでなければならない。これは、pages の hash が canonical な decision の行に記録され、その COMPLETE の行を含む commit が V2 main に入った server 側の時刻が 03:20:00 JST 以下であることで示される(Part 1 §9.6)。この確認は decision を使う側(Part 3、Part 4)が行う。decision の job 自身は、自分が取得した pages だけを使う。
5. 通れば `t_G = Main_Entered_At`。

- G_LONG_TERM_SELF_CONTAINED は常に false(Requirements §9.2)。

## 10. attempt の検査(Part 1 §9.4 の手順 3)

```
attempt_status(attempt, pages, repo@Audit_Repo_Commit_SHA, revocation_sets, execution_evidence, cfg) → USABLE | 原因コード
```

Requirements §6.2 の順で検査し、最初に通らなかったもののコードを返す。Part 1 §9.7 で Included になった attempt だけに使う。

| 順 | 検査(この Part での中身) | コード |
|---|---|---|
| 1 | **PROVENANCE**: (a) manifest と PRE の記録が §2.2 の正規性に通る。(b) path の Target_Origin・Execution_ID と manifest の値が一致し、PRE の記録の Execution_ID・Target_Origin・Acquisition_Path_ID が manifest と一致する。(c) manifest の Pre_* の hash が保存した PRE の記録・要求・応答と一致する。(d) CFTC_Source_Year を Part 1 §8.1 で計算し直して一致する。(e) Content_SHA256 と Content_Byte_Count が保存した原ファイルと一致する。(f) Content_Check を、保存した原ファイルと Prev_Accepted_*(Part 1 §8.5 の規則で決まるものと一致すること)から計算し直して一致する。(g) Code_SHA が V2 の実装の Freeze の値と一致する。(h) Execution_ID が実在の実行の記録と一致する(§10.6 の verify_execution が EXECUTION_CONFIRMED)。(i) §8 の Actor_Login が、その経路に許した主体である | PROVENANCE_INVALID |
| 2 | **CONTENT**: Content_Check = OK | CONTENT_INVALID |
| 3 | **CLOCK(sanity)**: §7.2 の区間があり、§7.3 を満たす | CLOCK_INVALID(sanity) |
| 4 | **窓**: §7.4 | OUTSIDE_WINDOW |
| 5 | **anchor**: §10.5 の Valid_Anchor_Timestamps が空でない | NO_VALID_SERVER_ANCHOR |
| 6 | **CLOCK(consistency)**: §7.5 | CLOCK_INVALID(consistency) |
| 7 | **anchor の遅れ**: Server_Anchored_At ≤ T_info + δ(δ = 300 秒) | ANCHOR_LATE |

### 10.5 Valid_Anchor_Timestamps と Server_Anchored_At(Requirements §9.1)

```
Valid_Anchor_Timestamps = { t_G | verify_g が G_VALID }
                        ∪ { genTime(m) | m は R1・R2 の POST の応答(再試行を含むすべて)、verify_r が R_VALID、expected_imprint = Manifest_SHA256 }
Server_Anchored_At = min(Valid_Anchor_Timestamps)
```

- 有効な POST の応答はすべて候補にする(F-P2-8)。Requirements §9.1 の min(Valid_Anchor_Timestamps) に、そのまま対応する。
- genTime に accuracy を足し引きしない(Requirements §9.1 のとおり。§13 の F-P2-10)。
- G と R の個別の時刻と証拠は、どちらも判定の行に残す(Requirements §3.2)。

### 10.6 Execution_ID の実在の確認(Requirements §7.3。F-P2-6 の interface)

二つの層に分ける(§8 と同じ考え方)。

```
fetch_execution_record(path, execution_id) → saved evidence           (不純。decision の実行の中でだけ行う)
verify_execution(path, execution_id, manifest, saved evidence, cfg)
    → EXECUTION_CONFIRMED | EXECUTION_NOT_FOUND | EXECUTION_MISMATCH | EXECUTION_UNVERIFIABLE   (純粋)
```

- **保存**: 要求の URL、HTTP の status、応答の本文のバイト列を、`records/decision/<Target_Origin>/<Decision_Execution_ID>/execution/<Execution_ID>.{meta.json,body}` に保存し、SHA-256 を decision の行に記録する。meta は正規の JSON。
- **状態**:
  - EXECUTION_CONFIRMED: 記録が存在し、cfg の照合の項目がすべて一致する。
  - EXECUTION_NOT_FOUND: 提供者が「その ID の実行はない」と応答した。
  - EXECUTION_MISMATCH: 記録はあるが、照合の項目が一致しない。
  - EXECUTION_UNVERIFIABLE: 取得に失敗した、または応答を解釈できない。
  - CONFIRMED 以外は、§10 の検査 1 で PROVENANCE_INVALID。UNVERIFIABLE の場合は、03:19:00 JST まで取得し直してから判定する(§6.3 と同じ扱い)。
- **照合の項目**(経路ごとに cfg で固定する):
  - A(GitHub Actions): `GET /repos/{owner}/{V2 repository}/actions/runs/{run_id}/attempts/{run_attempt}`。workflow の path が A の取得の workflow、event が `schedule`、`github.event.schedule` に当たる cron の文字列が manifest の Scheduled_At と整合する(Part 1 §5.3)、実行の開始が Scheduled_At より後。
  - C(provider): 実行の ID、起動した job の名前、予定の時刻(payload)が manifest の Scheduled_At と Target_Origin に一致する、実行の開始が Scheduled_At より後。endpoint、認証、応答の項目の読み方は、**C2 の provider の選定の記録で決め、config に書く**。interface(入力・保存の形・状態)は、この節で先に固定する。

## 11. 決定論と監査(Requirements §7.3、Part 4 への interface)

| 対象 | Part 4 で行う再計算 | 使う資料 |
|---|---|---|
| R | verify_r を**別の実装**でも実行し、同じ結果になる | anchor の記録だけ(TSA に問い合わせない) |
| 時計 | clock_interval、§7.3〜§7.6 | anchor の記録、manifest、post_timing、start_record |
| G | main_entry_time と verify_g を、判定に使った保存の pages で再計算する | 保存の pages、**Audit_Repo_Commit_SHA から到達できる** object |
| 失効の情報 | verify_r の検査 11・12 を、decision の revocation_set で再計算する | decision の revocation_R{i}/ |
| Execution_ID | verify_execution を再計算する | decision の execution/ |
| attempt | attempt_status | 上のすべて |

- Part 4 は、activity API に問い合わせ直して、保存の pages と食い違いがないかも確かめる(保持期間の中に限る)。食い違いは監査の記録に残す。保持期間を過ぎた後は、保存の pages だけで再計算する。

## 12. config に固定する値(Code_SHA の対象)

| 名前 | 値 | 出どころ |
|---|---|---|
| DELTA | 300 秒 | Requirements §9.4 |
| EPSILON | 6.0 秒 | Requirements §10.6 |
| RTT_MAX | 2.0 秒 | Requirements §10.6 |
| A_MAX | 1.0 秒 | Requirements §9.3 |
| TSA_HTTP_TIMEOUT | 30 秒 | 案 |
| TSA_RETRY | 1 回、3 秒後 | 案 |
| ACTIVITY_MAX_PAGES | 100 | V1 の F8-a と同じ |
| ACTIVITY_REPOLL | 10 秒ごと、03:19:00 JST まで | Part 1 §9.7 の 4(間隔は案) |
| REVOCATION_REFETCH | 10 秒ごと、03:19:00 JST まで | §6.3(間隔は案) |
| EXECUTION_REFETCH | 10 秒ごと、03:19:00 JST まで | §10.6(間隔は案) |
| TSA_R1、TSA_R2 | URL、policy の OID、root と中間の証明書と指紋、OCSP の応答者または CRL の URL | TSA の選定の記録(別の記録。まだ決めていない。OCSP の提供、または CRL の発行の間隔を確認する。§6.3) |
| EXECUTION_A、EXECUTION_C | §10.6 の照合の項目。C は endpoint・認証・応答の読み方を含む | A は V2 の workflow の path。C は C2 の provider の選定の記録 |
| ALLOWED_ACTORS | A: `github-actions[bot]`。C: C2 の provider の選定の記録で決める | Part 1 §6.3 |

## 13. Finding

凍結済みの文書の文言は変えない。

| # | 内容 | 分類 | この版の扱い |
|---|---|---|---|
| F-P2-1 | **Part 1 §8.1 と Requirements §10.3 の食い違い。** Part 1 §8.1 は「CFTC_Source_Year は manifest と PRE の記録に書く」とする。Requirements §10.3 は PRE の記録の key を 6 つに固定しており、CFTC_Source_Year を入れる場所がない | 凍結済みの文書どうしの食い違い / **ACCEPT / CLOSE WITH ERRATUM** | §3.1。Part 1 の本文・SHA・Freeze commit は変えず、Erratum E1(drafts/M1-MACRO-PIPELINE-V2-IMPL-PART1-V0.5.errata.draft.md。確認の後に preregistration/ に置く)で記録する |
| F-P2-2 | **manifest の key は Requirements §3.3 の 7 項目より多い。** Part 1 が manifest に書くと定めたもの(CFTC_Source_Year、Content_Check)と、決定論的な再計算に要るもの(Prev_Accepted_*、Scheduled_At など)を足した | 実装上の選択 | Requirements §3.3 の列挙を、manifest が必ず含む最小の集合と読んだ。足したものは、すべて anchor の前に決まる事実である |
| F-P2-3 | **runner の時刻の読み取り。** OS の時計はナノ秒で読めるが、Part 1 §8.3 の形式はマイクロ秒。ナノ秒からマイクロ秒にするには、どこかで丸めか切り捨てが要る | **ACCEPT / CLOSE** | §2.1。正規の runner の時刻の解像度を 1 マイクロ秒と定義し、OS の値を floor でその格子に写す。F-P1-2 の「切り捨てなし」は、固定した形式のマイクロ秒をさらに秒などに落とさないという意味として扱う |
| F-P2-4 | **失効の情報を attempt ごとに取得する。** R-ACC-10 の「取得の時点で」をそのまま実装すると、CRL / OCSP の取得先も 1 つの依存先になる。取得できなければ、その局は anchor にも時計にも使えない | **REVISE(反映済み)** | §6.3。decision の実行の中で局ごとに 1 組。その情報自身の署名・有効性・新しさを verify_r で検査する。取得できない局は 03:19 まで取り直し、それでもなければその局の token を無効として判定する(**Claude が補った細部。再監査で確かめていただきたい**)。CRL の発行の間隔が長い局は STALE になりうるので、TSA の選定で確かめる |
| F-P2-5 | **POST の runner の時刻は TSA に縛られない。** POST の r_send・r_recv は manifest の後に測るので、縛るのは post_timing.json を含む commit の G の時刻だけである | Requirements の構造からの帰結 | 記録だけする。変えない |
| F-P2-6 | **Execution_ID の実在の確認**(Requirements §7.3)。A は GitHub Actions の run の API で確かめられる。C は provider の記録(X)によるので、provider を選ぶまで手順を決められない | **DEFER / NOT BLOCKING YET** | §10.6 で interface(入力・保存の形・状態)を A・C 共通に固定した。A の照合の項目は定義した。C の endpoint などは C2 の provider の選定の記録で config に埋める |
| F-P2-7 | **activity の記録の異常の扱い。** Requirements §9.2 は「候補が複数あれば timestamp が最も早いもの」とだけ書いている。この Part は、それに加えて、force_push・branch_deletion の記録や、許さない種類の記録があれば UNRESOLVED にする | 実装上の選択(Requirements より厳しい側)/ **ACCEPT / CLOSE** | §8.4 |
| F-P2-8 | **再試行した要求の扱い。** | **REVISE(反映済み)** | すべての要求と応答を保存し(§4.1、§5)、R-ACC に通ったすべての応答を R の有効な候補に、RTT ≤ 2.0 秒も満たすすべての応答を時計の測定にする(§7.1、§10.5) |
| F-P2-9 | **R の検証の二つの実装**。decision の検証と Part 4 の監査で、別の実装を使う | 実装上の選択 / **ACCEPT / CLOSE** | production の検証と Part 4 の独立の検証を別の実装にする。library と版は実装の候補の段階で Freeze の対象に入れる |
| F-P2-10 | **genTime の accuracy を anchor の時刻に入れない。** Requirements §9.1 は Server_Anchored_At = min(timestamps) と定めている。accuracy(最大 1 秒)の分、真の時刻は genTime より早いことも遅いこともある。activity API の timestamp も秒の単位である | Requirements のとおり | 変えない。δ = 300 秒に対して 1 秒の幅であることを記録する |
| F-P2-11 | **有限桁の 10 進の主張の誤り。** v0 §2.1 の「入力はすべて有限桁の 10 進数なので、結果も有限桁の 10 進数になる」は、除算を含めば一般には成り立たない | 仕様の文の誤り(むすびさんの指摘)/ **CLOSE(反映済み)** | §2.1。内部は有理数、除算を使わない、表せない値の直列化は fail-closed |

## 14. むすびさんに判断してほしいこと

1. **Erratum E1**(drafts/M1-MACRO-PIPELINE-V2-IMPL-PART1-V0.5.errata.draft.md)の文面。確認の後、同じバイト列を preregistration/ に置く。
2. **§6.3 の細部(F-P2-4)**: 失効の情報を取得できない局は 03:19 まで取り直し、それでもなければその局の token を無効として判定する扱い(main_entry_time の UNRESOLVED と違い、COMPLETE してよい)。新しさの条件(CRL の thisUpdate、OCSP の producedAt が genTime 以上)。
3. **§8.2a の Audit_Repo_Commit_SHA**: Audit_Repo_Commit_SHA から到達できない `a.after` の記録を候補にしない規則でよいか。
4. **§10.6**: Execution_ID の確認の interface と状態、A の照合の項目。
5. §12 の「案」の値(再試行・再取得の間隔)。
