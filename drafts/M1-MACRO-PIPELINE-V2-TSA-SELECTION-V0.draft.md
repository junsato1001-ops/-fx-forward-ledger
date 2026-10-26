# M1-MACRO-PIPELINE-V2 — TSA Selection Record(DRAFT v0)

- 状態: **DRAFT v0**(Claude、2026-10-27)。むすびさんの監査待ち。Freeze 候補ではない。
- 上位仕様(Freeze 済み、この記録で変えない):
  - **Requirements V0.7**(SHA-256 edf27751…)§9.3(R-ACC-1〜13、R1・R2 の数)、§10.3(主系統 = TSA)、§10.6(較正)。以下「Requirements」。
  - **Part 2 V0.4**(6e9082a4…)§6.1(要求)、§6.2(verify_r の検査 1〜12)、§6.3(鎖と失効の情報)、§14(config の TSA_R1・TSA_R2、TSA_HTTP_TIMEOUT・TSA_RETRY)。
  - **Part 4 V0.2**(8d57262c…)§5.2・§5.3(較正の予定と手順)、§14 の F-P4-9(要求の量。DEFER → この記録)。
  - Part 1 V0.5(c63a0927…)§5.2・§6.4・§7.5・§9.2(起動の回数)。

---

## 1. 目的と境界

- 目的: M1-MACRO-PIPELINE-V2 の R1・R2 として使える TSA を、R-ACC-1〜13 に照らして選ぶための記録。
- この記録の範囲は **TSA の選定だけ**である。
- **しないこと**: V1 の変更、Requirements・Part 1〜4 の変更、較正と受け入れの試験の開始、Implementation Freeze、Development Replay、Holdout の計算。
- 判定の規則:
  - 各 R-ACC は **PASS / FAIL / PENDING / N/A(設計で満たす)** のどれか。
  - **推測で PASS にしない。** 公開文書・契約条件・provider の書面の回答・実際の token の検査のどれかの証拠がなければ PENDING。
  - token の中身で決まる条件(R-ACC-1〜7・9・10・11)は、**実際の応答の DER を検査するまで PASS にしない**(文書の記述は補助の証拠)。
  - R1・R2 のどちらかに FAIL または PENDING が 1 つでも残れば、**TSA Selection = PASS にしない**。
- 秘密の情報(API の key、契約の認証情報、秘密鍵)はこの記録に書かない。書くのは、それを置く場所の名前だけ。

### 1.1 この版の調査の制約(重要)

- この版の調査は、**公開の Web 文書だけ**で行った(2026-10-27 03:00〜03:40 JST)。
- Claude の作業環境からは、TSA の endpoint・OCSP の応答者に**直接接続できなかった**(HTTP の接続がすべて失敗。network の allowlist の外)。したがって、この版には**実際の token・鎖・失効の情報の検査の結果が 1 つもない**。
- 一部の provider の文書(FreeTSA、総務省の認定時刻認証業務の一覧、Entrust の TPS)は、取得できなかった。§2.3 に「未調査」として残す。
- この制約のため、この版の結論は全候補 PENDING または NOT SELECTED である(§7)。§6 に、PENDING を解くための probe の手順(案)を置く。

---

## 2. 候補 TSA

### 2.1 R1・R2 の組の条件(Requirements §9.3「数」)

- R1・R2 は、**運営者が異なり、かつ trust / root の鎖も異なる**。同じ運営者の別の endpoint は 2 局と数えない。
- この記録では、「運営者が異なる」を**企業の group の単位**で判定する案とする(§8 の TSA-F6)。たとえば DigiCert, Inc. と DigiCert Europe、GlobalSign NV/SA と GMO グローバルサイン株式会社は、それぞれ同じ group として、組にしない。

### 2.2 評価した候補

| ID | endpoint(公開文書に書かれたもの) | 運営者 | root(文書に書かれたもの) | 方式・認証・契約 | 主な証拠 |
|---|---|---|---|---|---|
| **C-DC** | `http://timestamp.digicert.com` | DigiCert, Inc. | DigiCert Trusted Root G4。中間 DigiCert Trusted G4 TimeStamping RSA4096 SHA256 2025 CA1。responder の証明書は SHA-256 / SHA-384 / SHA-512 の 3 種(2026-09-03 に交換) | 無料・認証なし。利用条件・量の記述は見つからない | [E1] |
| **C-DCEU** | `http://ts.quovadisglobal.com/eu`、`…/ch` | DigiCert Europe(DigiCert, Inc. の group) | DigiCert Europe の発行 CA(例: DigiCert QV G3 TS EUR RSA4096 RSASSA-PSS 2025 CA1)。root は文書の参照先(未取得) | **IP address を DigiCert に登録**。利用は DigiCert Europe の証明書の保有者に限られうる。契約(MSA・Subscriber Agreement) | [E2][E3] |
| **C-GS** | `http://timestamp.globalsign.com/tsa/r6advanced1` | GlobalSign NV/SA(GMO の group) | 未確認(path の名前から R6 の系統と推測されるが、推測なので記録しない) | 無料・認証なしと見られる。利用条件・量の記述は見つからない | [E4](第三者のページ。2021 年の移行の記述が古い)[E5] |
| **C-SG** | `http://timestamp.sectigo.com` | Sectigo | 未確認 | 無料・認証なし。**script で複数の要求を送るときは、要求の間を 15 秒以上あける**ように求めている | [E6] |
| **C-SGQ** | `http://timestamp.sectigo.com/qualified` | Sectigo (Europe) S.L. | 未確認(TSU の証明書と CRL は sectigo.com/legal に公開) | eIDAS 準拠。15 秒の指示は C-SG と同じページ。subscriber agreement で制限がありうる | [E6][E7] |
| **C-GMO** | 未確認(契約の後に発行される URL と認証情報) | GMO グローバルサイン株式会社(GlobalSign の group) | 未確認 | **有料**。認定タイムスタンプ(総務大臣の認定。UTC(NICT) との差 1 秒以内が認定の要件)。**購入した数を超えて要求できない**。**1 秒に 5 回を超えて要求しない**(上位の license を除く)。URL・認証情報を第三者と共有しない | [E8][E9] |
| **C-SSL** | `https://ts-c2pa.ssl.com` | SSL.com | 未確認 | **API key が必要**。C2PA 用。ECC(RSA は要望で)。年間の数: 無料の tier で 2,500、premium で 10,000、それを超える分は追加・bulk(価格は非公開) | [E10] |

### 2.3 未調査の候補(次の版で調べる)

- 日本の認定時刻認証業務の他の事業者(セイコーソリューションズ、アマノ、サイエンスパーク「iScign」、ウイングアーク 1st など。[E11])。認定の要件に「UTC(NICT) との差 1 秒以内」がある([E9])ので、R-ACC-4 の候補になりうる。量・endpoint・RFC 3161 の方式は未確認。
- Entrust(TPS を取得できなかった)、FreeTSA(公式のページを取得できなかった)、Apple・Microsoft の TSA(署名の用途の限定があるかどうか未確認)。

---

## 3. R-ACC-1〜13 の判定表

- 確認日時はすべて 2026-10-27 JST(03:00〜03:40)。証拠の番号は §9。
- 「文書」= 公開文書の記述(補助の証拠)。「token」= 実際の応答の DER の検査(この版では 0 件)。
- **R-ACC-12** は TSA の性質ではなく、こちらの検証の規則である。Part 2 §6.1・§6.2 で「HTTPS の成否を token の正しさの根拠にしない」と決めてあるので、全候補で **N/A(設計で満たす)** とする。HTTP の endpoint(TLS なし)でも、この規則のもとでは token の正しさに影響しない。

### 3.1 C-DC(DigiCert 公開)

| R-ACC | 判定 | 根拠 | 証拠 |
|---|---|---|---|
| 1 status | PENDING | token なし | — |
| 2 SHA-256 の imprint | PENDING | 文書に記述なし(responder の証明書の名前に SHA-256 があるだけ) | [E1] |
| 3 署名 ≥ SHA-256 | PENDING | 同上 | [E1] |
| 4 accuracy ≤ 1 秒 | PENDING | 文書に記述なし。**accuracy が TSTInfo にあるかは token でしか確かめられない** | — |
| 5 genTime(UTC、小数) | PENDING | token なし | — |
| 6 nonce | PENDING | token なし | — |
| 7 certReq・ESSCertID(v2) | PENDING | token なし | — |
| 8 policy OID | PENDING | 公開の endpoint の policy OID の記述が見つからない | [E1] |
| 9 EKU = timeStamping のみ・critical | PENDING | 公開の証明書を検査していない(取得できない) | [E1] |
| 10 鎖と失効の情報の取得 | PENDING | 鎖は公開されている。OCSP・CRL の URL と、**失効の情報の発行の時刻の新しさ**(§4)は未確認 | [E1] |
| 11 独立の再検証 | PENDING | token なし | — |
| 12 TLS を根拠にしない | N/A | Part 2 §6.1・§6.2 | — |
| 13 運営者・条件・量 | **PENDING** | 運営者は記録できる。**利用条件・rate limit・fair-use の公開の記述が見つからない**。§5 の量が許されることを確認できない。書面の確認が要る | [E1] |

### 3.2 C-DCEU(DigiCert Europe、qualified)

| R-ACC | 判定 | 根拠 | 証拠 |
|---|---|---|---|
| 1 | PENDING | token なし | — |
| 2 | PENDING(文書は肯定) | 文書: 受け付ける hash は SHA-256・SHA-384・SHA-512 | [E2] §6.2.1 |
| 3 | PENDING(文書は肯定) | 文書: RSA(3072 bit 以上)・RSASSA-PSS・ECDSA P-256 | [E2] §6.2.1 |
| 4 | PENDING(文書は肯定) | 文書: 「declared accuracy of ±1 second with respect to UTC」。TSTInfo の accuracy の field は token で確かめる | [E2] §6.2.2 |
| 5〜7 | PENDING | token なし | — |
| 8 | PENDING(文書は肯定) | 文書: policy OID 1.3.6.1.4.1.8024.0.2000.6。token の policy と一致することを確かめてから固定する | [E2] §5.2 |
| 9 | PENDING | 証明書を検査していない | — |
| 10 | PENDING(文書は一部肯定) | 文書: certificate status は CRL または OCSP。新しさ(§4)は未確認 | [E2] §6.2.5 |
| 11 | PENDING | token なし | — |
| 12 | N/A | — | — |
| 13 | **PENDING(実現の可能性に疑問)** | **IP address の登録が要る**。経路 A(GitHub Actions の hosted runner)は IP address が固定されないので、登録の方式と両立しない可能性が高い(§8 の TSA-F4)。量の記述なし。契約の条件が未確認 | [E3][E2] §6.2.8 |

### 3.3 C-GS(GlobalSign 公開)

| R-ACC | 判定 | 根拠 | 証拠 |
|---|---|---|---|
| 1〜11 | PENDING | 公式の技術文書(policy OID・accuracy・鎖)を取得できていない。endpoint は第三者のページの記述だけ | [E4][E5] |
| 12 | N/A | — | — |
| 13 | **PENDING** | 公開の endpoint の利用条件・量の記述が見つからない | [E4][E5] |

### 3.4 C-SG(Sectigo 公開)・C-SGQ(Sectigo qualified)

| R-ACC | C-SG | C-SGQ | 根拠 | 証拠 |
|---|---|---|---|---|
| 1 | PENDING | PENDING | token なし | — |
| 2 | PENDING(文書は肯定) | PENDING(文書は肯定) | RFC 3161 では、指定した hash から RSA/SHA-256・384・512 を選ぶ。eIDAS DS: SHA-256・384・512 を受け付ける | [E6][E7] |
| 3 | PENDING(文書は肯定) | PENDING(文書は肯定) | eIDAS DS: sha256WithRSAEncryption | [E7] |
| 4 | PENDING | PENDING(文書は肯定) | eIDAS DS: 「±1 second of a trusted UTC time source」。C-SG は記述なし | [E7] |
| 5〜7 | PENDING | PENDING | token なし | — |
| 8 | PENDING | PENDING | eIDAS DS の OID 1.3.6.1.4.1.6449.1.2.1.9 は「certificate policy identifier」と書かれており、TSTInfo の policy かどうか未確認 | [E7] |
| 9 | PENDING | PENDING | 証明書を検査していない | — |
| 10 | PENDING | PENDING(**CRL だけ**) | eIDAS DS は失効の確認を CRL だけで説明し、OCSP に触れない。CRL の発行の間隔が長ければ §4 の問題が直接に出る | [E7] |
| 11 | PENDING | PENDING | token なし | — |
| 12 | N/A | N/A | — | — |
| 13 | **FAIL(現在の上位仕様のもとで)** | **FAIL(同)** | provider は「script で複数の要求を送るときは間を 15 秒以上」と求めている。上位仕様の固定値・案は、再試行が 3 秒後(Part 2 §14 TSA_RETRY)、較正の PRE → POST が 10 秒(Part 4 §5.3)、A・C・decision の job の並行(Part 1 §9.2: 03:15・03:17 に最大 4 本)で、15 秒の間隔を守れない。上位仕様を変えずにこの局を使うことはできない | [E6] |

### 3.5 C-GMO(認定タイムスタンプ byGMO)

| R-ACC | 判定 | 根拠 | 証拠 |
|---|---|---|---|
| 1〜3 | PENDING | 約款に技術仕様の記述なし。TP/TPS(jp.globalsign.com/repository)は未取得 | [E8] |
| 4 | PENDING(制度の上では肯定) | 認定の要件:「発行する(した)タイムスタンプと当該時刻源との時刻差が 1 秒以内」(時刻源は UTC(NICT))。TSTInfo の accuracy の field は token で確かめる | [E9] |
| 5〜11 | PENDING | 未調査・token なし | — |
| 12 | N/A | — | — |
| 13 | **PENDING(量の条件は明示)** | 約款: 購入した数を超えて要求できない。1 秒に 5 回を超えない。**量と頻度の条件が書面で公開されている唯一の候補**。§5 の量を購入できるか、価格、契約の主体、経路 A・C の両方から同じ認証情報で使えるか(「第三者と共有しない」の解釈を含む)が未確認 | [E8] |

### 3.6 C-SSL(SSL.com C2PA TSA)

| R-ACC | 判定 | 根拠 | 証拠 |
|---|---|---|---|
| 1〜11 | PENDING | accuracy・policy OID・hash の記述なし。ECC が既定 | [E10] |
| 12 | N/A | — | — |
| 13 | **PENDING** | 年間の数が公開されている(2,500 / 10,000)。§5 の量(1 局あたり、受け入れまでで最大 5,760、通常の運用で年最大約 15,000)は、無料の tier を超える。premium でも年間の通常の運用の最大値を超えうる。bulk の条件は非公開 | [E10] |

### 3.7 R-ACC-1 の grantedWithMods の扱い(Part 2 の規則を維持)

- status が grantedWithMods の応答は、**変更の内容が記録されている場合にだけ**受け付ける(Requirements R-ACC-1、Part 2 §6.2 の検査 1)。
- probe(§6)で grantedWithMods が返った局は、その応答の statusString・failInfo と、要求との違い(policy・nonce・hash など)をすべて保存し、この記録に追記する。変更の内容が読めなければ、その局の R-ACC-1 は FAIL。

---

## 4. 失効の情報の新しさ(Part 2 §6.2 の検査 11)— 選定の前提を揺るがしうる点

これは個々の候補の問題ではなく、**どの候補でも起こりうる構造の問題**なので、別の節にする。

- Part 2 §6.2 の検査 11: canonical な失効の情報の**発行の時刻**(CRL の thisUpdate、OCSP の応答の producedAt)が、その token の **genTime 以上**でなければ R_REVOCATION_STALE。
- **時間の関係**:
  - 取得の attempt の token は 21:00〜03:00 JST の間に作られる。失効の情報は 03:15〜03:18 に集める(Part 2 §6.3)。canonical なものの発行の時刻は、その窓の最後の attempt の genTime(03:00 近く)以上でなければならない。
  - **較正**では、CAL_POST の token の**数秒後**に失効の情報を取得する(Part 4 §5.3)。発行の時刻が CAL_POST の genTime 以上 = **取得の直前の数秒〜数十秒の間に署名された失効の情報**が要る。
- **一般的な運用との食い違い**: OCSP の応答者は、応答を**事前に作っておいてよい**(pre-produced responses)。producedAt は「応答者がその応答に署名した時刻」である([E12] §2.4・§2.5)。大きな CA の OCSP は、CDN で配る事前に作った応答が一般的で、producedAt が取得の時刻より数時間〜数日前になることがある(これは一般論で、候補ごとには未確認)。中間の証明書の CRL は、offline の root が長い間隔で発行することが多い。
- **帰結(未確認の見込み)**: 失効の情報が「要求のたびに署名される OCSP」でない局では、検査 11 で多くの token が STALE になりうる。とくに較正では、ほぼすべての回が STALE になりうる。両局がそうなら、Requirements §10.6 の p_min = 0.99 に届かない。
- **この記録でしないこと**: 検査 11 を緩める、解釈を変える。それは Freeze 済みの Part 2 の変更であり、この記録では行わない。§8 の TSA-F1・TSA-F2 として、むすびさんに判断していただく。
- **選定の確認項目(Part 2 §6.3 の末尾の指示を具体化)**: 各候補について、署名者の証明書と中間の証明書のそれぞれで、
  1. OCSP の URL があるか(AIA)、CRL の URL(CDP)、
  2. OCSP の応答の producedAt と、取得の時刻との差(多数回の取得で分布をとる)、
  3. CRL の thisUpdate・nextUpdate の間隔、
  を probe で測る(§6 の P3)。

---

## 5. 要求の量(F-P4-9、R-ACC-13)

### 5.1 1 局あたりの最大の数(上位仕様の値から計算)

- F-P4-9 の「較正だけで最大 5,376 回」は、**R1・R2 の合計**である(336 回 × 2 経路 × PRE・POST × 2 局 × 再試行 2)。**1 局あたりは 2,688 回**。
- R-ACC-13 は「較正 + 64 の試験窓 + 通常の運用で想定する attempt の数」を求めるので、全部を数える。

| 区分 | 計算(1 局あたり、最大) | 数 |
|---|---|---|
| 較正(7 日) | 336 回 × 2 経路 × (PRE + POST) × 2(再試行を含む) | **2,688** |
| 1 つの Origin の日 | 取得の attempt: A 5 回(Part 1 §5.2)+ C 3 回(§6.4)= 8 回 × (PRE + POST) × 2 = 32。late diagnostic の上限による増加: 2 経路 × (PRE + POST) × 2 = 8(Part 1 §7.5。保守的に加算)。DECISION_START: decision の job 最大 4 本(Part 1 §9.2)× 1 × 2 = 8 | **48** |
| 受け入れの試験(64 窓) | 64 × 48 | **3,072** |
| **受け入れまでの合計** | 2,688 + 3,072 | **5,760** |
| 通常の運用(1 年) | 約 6 Origin / 週 × 52 週 ≈ 312 日 × 48 | **約 14,976 / 年** |

- 再試行のない通常の日の目安は、1 局あたり 1 日 20 回程度(8 attempt × 2 + 4)。上の表は**上限**であり、許容の確認は上限で行う(推測で目安の値を使わない)。
- 強制 failover の窓は止めた経路が要求しないので、上限より少ない。上限のまま数える。

### 5.2 瞬間の頻度

- R1・R2 は並行に送ってよい(Part 2 §6.1)。1 局に対して同じ時刻に重なりうるのは、03:15・03:17 の decision の job(最大 4 本)の DECISION_START。最悪で**同じ秒に 4 回**、再試行で 3 秒後にさらに 4 回。
- C-GMO の「1 秒に 5 回まで」には収まる見込み(4 ≤ 5)。C-SG・C-SGQ の「15 秒以上あける」には収まらない(§3.4)。

### 5.3 各候補の確認の状態

| 候補 | 公開された量の条件 | 1 局あたり 5,760(受け入れまで)+ 約 15,000 / 年 | 判定 |
|---|---|---|---|
| C-DC | なし | 確認できない | PENDING(書面の確認が要る) |
| C-DCEU | なし(IP の登録) | 確認できない | PENDING |
| C-GS | なし | 確認できない | PENDING(書面の確認が要る) |
| C-SG / C-SGQ | 要求の間 15 秒以上 | 頻度の条件に反する | FAIL(現在の上位仕様のもとで) |
| C-GMO | 購入した数まで、5 回 / 秒まで | 購入の数しだい。頻度は収まる見込み | PENDING(見積もりと契約) |
| C-SSL | 年 2,500 / 10,000、超過は追加 | 無料の tier では足りない | PENDING(bulk の条件) |

- 公開の条件がない局(C-DC・C-GS)について、Requirements R-ACC-13 は「確認できなければ…正式な候補から外す」である。**provider の書面の回答**(または有料の契約の条件)を得るまで PENDING とし、得られなければ NOT SELECTED にする。

---

## 6. PENDING を解く手順(案。むすびさんの判断の後に行う)

- **実行の場所**: Claude の作業環境からは TSA に届かない(§1.1)。案は次のどちらか。
  - (a) 純さんの PC の OpenSSL で probe を行い、DER のバイト列をそのまま保存して渡していただく。
  - (b) V2 repository の作成の後、probe の専用の workflow(V1 の credential なし、V1 に書かない)で行う。
- **probe は較正でも試験でもない。** 結果は Calibration の分母にも Gate にも入れない。dummy の imprint(固定の文字列の SHA-256)だけを送る。
- **量**: 1 局あたり P1・P2 で 10 回以内。要求の間は 20 秒以上(C-SG の条件より長く)。

| probe | 内容 | 判定する R-ACC |
|---|---|---|
| P1 | 1 局に 5 回、nonce・certReq = true・SHA-256 で要求し、tsq・tsr の DER を保存。`openssl ts -reply -text` で status・policy・accuracy・genTime・nonce・署名の algorithm・ESSCertID(v2)を記録 | 1〜8 |
| P2 | 応答の中の署名者の証明書を取り出し、EKU(critical、timeStamping のみ)・AIA(OCSP)・CDP(CRL)を記録。鎖を root まで組み立てて保存し、root の指紋を記録 | 9、10 |
| P3 | 署名者と中間の証明書のそれぞれについて、OCSP と CRL を 48 時間、1 時間ごとに取得し、producedAt・thisUpdate・nextUpdate と取得の時刻の差を記録 | 10、§4 |
| P4 | P1〜P3 の資料だけで、ネットワークなしに `openssl ts -verify` と失効の検査をやり直す | 11 |
| P5 | 量の条件の書面の確認(C-DC・C-GS は provider への問い合わせ、C-GMO・C-SSL は見積もりと契約の条件) | 13 |

---

## 7. 固定する対象(SELECTED になった局について記録する。この版では空)

| 項目 | R1 | R2 |
|---|---|---|
| endpoint の URL(scheme・host・path) | — | — |
| 運営者(法人名、group) | — | — |
| policy の OID(TSTInfo の値) | — | — |
| root の証明書と SHA-256 の指紋 | — | — |
| 中間の証明書と指紋 | — | — |
| 署名者の証明書の発行者・serial・有効期間(交換の予定を含む) | — | — |
| OCSP の応答者の URL、CRL の URL、その発行の間隔の実測(P3) | — | — |
| 要求の方式(HTTP POST、Content-Type、認証の方式。認証情報そのものは書かず、置き場所の名前だけ) | — | — |
| TSA_HTTP_TIMEOUT = 30 秒・TSA_RETRY = 1 回 3 秒後(Part 2 §14)との両立 | — | — |
| 量の条件と、その証拠(書面・契約の識別子) | — | — |
| 選定の後に証明書が交換された場合の扱い | §8 の TSA-F5 | §8 の TSA-F5 |

- 実装では、この表の値を config(Code_SHA の対象)に固定し、別の endpoint・root に差し替えない。差し替えが要るときは Finding として記録し、この記録の新しい版を作る。

---

## 8. 結論と Finding

### 8.1 結論(この版)

| 候補 | 状態 | 理由 |
|---|---|---|
| C-DC | **PENDING** | token の検査が 0 件。量の公開の条件なし |
| C-DCEU | **PENDING** | 同上。IP の登録が経路 A と両立しない可能性(TSA-F4)。C-DC と同じ group なので、C-DC との組は不可 |
| C-GS | **PENDING** | 公式の技術文書が未取得。量の公開の条件なし |
| C-SG | **NOT SELECTED** | R-ACC-13 FAIL(15 秒の間隔。現在の上位仕様と両立しない) |
| C-SGQ | **NOT SELECTED** | 同上 |
| C-GMO | **PENDING** | 量の条件は明示。購入・価格・技術仕様が未確認。C-GS と同じ group なので、C-GS との組は不可 |
| C-SSL | **PENDING** | 量の条件が足りない可能性。技術仕様が未確認 |

- **R1 = PENDING、R2 = PENDING。TSA Selection = PENDING。** どの候補も R-ACC-1〜13 の全部を満たすことが確認されていない。
- 組の候補(運営者と root が異なる組)の例: C-DC と C-GS、C-DC と C-GMO、C-GMO と(日本の他の認定事業者)。どれも未確定。

### 8.2 Finding

| # | 内容 | 分類 | 扱いの案 |
|---|---|---|---|
| TSA-F1 | **失効の情報の新しさ(Part 2 §6.2 の検査 11)。** 事前に作った OCSP・CRL では、発行の時刻が genTime より前になりやすい。とくに較正では、取得の数秒前に署名された失効の情報が要る。要求のたびに署名する OCSP を持つ局がなければ、検査 11 のもとで R が使えない可能性がある | Freeze 済みの Part 2 と、外部の PKI の一般的な運用との食い違い(見込み。P3 で確かめる) | この記録では検査 11 を変えない。P3 の実測の後、どの候補も満たさなければ、Part 2 への Finding(Erratum または設計の変更)として、むすびさんに判断していただく |
| TSA-F2 | **検査 11 の対象の範囲。** Part 2 §6.3 は「署名者の証明書(と中間の証明書)」の失効の情報を集めるが、検査 11 の「発行の時刻 ≥ genTime」が中間の証明書の CRL にも適用されるかが本文から一意に読めない。適用されるなら、offline の root が発行する CRL ではほぼ常に STALE になる | Part 2 の解釈 | むすびさんに解釈を決めていただく(Erratum の要否を含む) |
| TSA-F3 | **F-P4-9 の数の数え方。** 5,376 は R1・R2 の合計で、1 局あたりは 2,688。R-ACC-13 は試験の窓と通常の運用も含むので、1 局あたり受け入れまで最大 5,760、通常の運用で年最大約 15,000 で確認する | F-P4-9 の具体化 | §5.1 の数で確認する案 |
| TSA-F4 | **IP の登録が要る局と経路 A。** GitHub Actions の hosted runner は IP address が固定されない。IP の登録を条件とする局(C-DCEU)は、経路 A から使えない可能性が高い | 実現の可能性 | IP の登録が要る局は、経路 A・C の両方から使えることが確認できるまで候補にしない案 |
| TSA-F5 | **証明書の交換。** C-DC は 2026-09-03 に responder の証明書を交換し、「少なくとも 15 か月ごと」に更新するとしている。受け入れの試験の途中の交換は、config に固定した鎖・指紋と食い違う | 運用 | 固定するのは root の指紋と policy の OID とし、署名者の証明書は token の中の証明書と ESSCertID で結び付ける案。交換の予定が受け入れの期間に重なる局は、事前に記録する |
| TSA-F6 | **「運営者が異なる」の単位。** 同じ企業の group の別の法人(DigiCert と DigiCert Europe、GlobalSign と GMO グローバルサイン)を別の運営者と数えるか | Requirements §9.3 の解釈 | 保守的に group の単位で判定する案 |
| TSA-F7 | **認証情報の共有と経路 C。** 有料の局(C-GMO)は「URL・認証情報を第三者と共有しない」とする。経路 C の C2 の provider の実行環境に認証情報を置くことが「第三者の利用」に当たるかを、契約の前に provider に確認する | C2 の選定と関連 | C2 の provider の選定の記録と同時に確認する |

---

## 9. 証拠(すべて 2026-10-27 JST に参照)

| # | 文書 | 要点 |
|---|---|---|
| E1 | DigiCert KnowledgeBase「RFC3161 compliant Time Stamp Authority (TSA) server」(INFO4231、Last Modified 09/19/2026)https://knowledge.digicert.com/general-information/rfc3161-compliant-time-stamp-authority-server | URL、鎖の file 名、2026-09-03 の交換、15 か月ごとの更新。量・policy・accuracy の記述なし |
| E2 | DigiCert Europe TSPPS v3.1(2026-10-14)https://www.digicert.com/content/dam/digicert/pdfs/legal/digicert-europe-tspp-3-01.pdf | OID 1.3.6.1.4.1.8024.0.2000.6、±1 秒、hash、CRL または OCSP、100% の可用性は保証しない |
| E3 | DigiCert KnowledgeBase「Timestamp server」(QuoVadis、Last Modified 04/04/2025)https://knowledge.digicert.com/quovadis/general-information/timestamp-server | ts.quovadisglobal.com/eu・/ch、IP address の登録 |
| E4 | TBS Certificates FAQ「globalsign_cs_timestamp」(Last edited 12/16/2025)https://www.tbs-certificates.co.uk/FAQ/en/globalsign_cs_timestamp.html | r6advanced1 の URL(第三者のページ。内容は 2021 年の時点) |
| E5 | GlobalSign「Timestamping SaaS」https://globalsign.com/timestamp-service | RFC 3161、256 bit の hash。量・accuracy の記述なし |
| E6 | Sectigo「Time Stamping Server」(ページの日付 2018-10-03)https://sectigo.com/resources/time-stamping-server | URL(標準・qualified)、「15 seconds or more between each one」、hash の選び方 |
| E7 | Sectigo eIDAS TSA Disclosure Statement v1.0.3(2023-01-13)https://www.sectigo.com/uploads/legal/eIDAS/Sectigo_eIDAS_TSA_DS_v1.0.3.pdf(参考: v1.0.1 https://www.sectigo.com/uploads/legal/Sectigo-eIDAS-TSA-DS-v1.0.1.pdf) | ±1 秒、SHA-256・384・512、sha256WithRSA、CRL のみの記述、OID |
| E8 | GMO グローバルサイン「認定タイムスタンプ byGMO サービス利用約款」v1.0(2024-05-22)https://jp.globalsign.com/repository/common/ats/TermsOfUse_v1.0.pdf | 購入した数まで、1 秒 5 回まで、認証情報の共有の禁止 |
| E9 | 総務省「タイムスタンプの国による認定制度」https://www.soumu.go.jp/main_content/000742673.pdf | UTC(NICT) との差 1 秒以内 |
| E10 | SSL.com「Timestamping」https://www.ssl.com/products/content-authenticity/timestamping/ | ts-c2pa.ssl.com、API key、年 2,500 / 10,000 |
| E11 | 総務省 報道資料「認定時刻認証業務の認定」(令和 7 年 8 月 8 日)https://www.soumu.go.jp/menu_news/s-news/01cyber01_02000001_00245.html | サイエンスパーク「iScign」、ウイングアーク 1st の認定 |
| E12 | IETF draft-ietf-pkix-rfc2560bis-14(RFC 6960 の草案)§2.4・§2.5 https://datatracker.ietf.org/doc/draft-ietf-pkix-rfc2560bis/14/ | pre-produced responses、producedAt = 応答者が署名した時刻 |

- E1〜E12 は Web の取得の時点の内容であり、provider が後で変えうる。SELECTED にする前に、該当の文書の PDF・HTML を保存して SHA-256 を記録する(この版では保存していない)。

## 10. むすびさんに判断してほしいこと

1. **§1.1 の制約**のもとで、この版を「調査の途中の記録」として受けてよいか。PASS / FAIL は token と書面の証拠が出るまで付けない方針。
2. **TSA-F1・TSA-F2**: 検査 11 の新しさの条件が、一般的な OCSP・CRL の運用で満たせない見込み。P3 の実測を先に行うか、先に Part 2 の解釈を決めるか。
3. **§6 の probe の実行の場所**: (a) 純さんの PC、(b) V2 repository の probe の専用の workflow。
4. **C-SG・C-SGQ を NOT SELECTED** としてよいか(15 秒の条件。上位仕様を変えて使う案は採らない)。
5. **TSA-F3〜F7** の扱いの案。
6. 次に調べる候補(§2.3 の日本の認定事業者など)の優先。
