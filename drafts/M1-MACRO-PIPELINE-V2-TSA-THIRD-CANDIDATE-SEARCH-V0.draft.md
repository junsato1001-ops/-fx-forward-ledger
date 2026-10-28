# M1-MACRO-PIPELINE-V2 — TSA Selection: third-candidate search(DRAFT v0)

- 状態: **DRAFT v0 / RESEARCH RECORD**(Claude、2026-10-28)。むすびさんの監査待ち。
- 位置づけ: TSA Selection の**別のトラック**。凍結した TSA-PROBE-SPEC V0.1(C-DC・C-GS)には何も足さない。むすびさんの指示(2026-10-28 18:28 JST):「C-GS と operator が異なる」+「trust / root の系統も独立」+「R-ACC-1〜13 を満たせる可能性」を条件に探す。
- 書き換えない記録: TSA Selection Record DRAFT v0(ec325170)、TSA-PROBE-SPEC V0.1(凍結)、P1 の結果(V2 repository bc6529b0)。
- この版の証拠は**公開文書だけ**。token は 1 つも取っていない。どの候補も PASS にしない。

## 1. 背景(P1 の監査の結果)

- C-DC = P1 で R-ACC-4 FAIL(5 つの token のどれにも accuracy がない)。P3 では観測を続ける。
- C-GS = P1 の検査 1〜10・12(a) で候補を維持。運営者 GlobalSign nv-sa、root は GlobalSign Root CA - R6(P1 の鎖)。
- R1・R2 には、C-GS と**別の運営者 group** で、**別の root の系統**の局がもう 1 つ要る(Requirements §9.3、TSA-F6)。GMO グローバルサイン(C-GMO)は C-GS と同じ group なので組にならない。

## 2. 条件(むすびさんの指示をそのまま)

| # | 条件 |
|---|---|
| T1 | 運営者が GlobalSign の group(GlobalSign nv-sa、GMO グローバルサイン)と異なる |
| T2 | root の系統が GlobalSign の root(Root CA - R6 など)と独立(cross-sign で GlobalSign の root に繋がらない) |
| T3 | R-ACC-1〜13 を満たせる可能性がある。とくに R-ACC-4(TSTInfo の accuracy ≤ 1 秒)と R-ACC-13(量・頻度の書面の条件) |

## 3. 候補(公開文書から)

| ID | 運営者 | endpoint | 文書にある root / 鎖 | 文書にある accuracy | 量・利用の条件 | T1 | T2 | T3 の見込み | 証拠 |
|---|---|---|---|---|---|---|---|---|---|
| **C-CT** | Asseco Data Systems S.A.(ブランド CERTUM、ポーランド) | `http://time.certum.pl` | 署名者「Certum Timestamp 2025」← Certum Timestamping 2021 CA ← **Certum Trusted Network CA 2** | 「100 ms」(高負荷で 200 ms)。ただし同じ文書の §5.1 に「1 秒より大きい精度」という食い違う記述がある | 「技術的な制限なしにすべての者に発行」。私人・非営利は原則無料、それ以外は価格表。**要求の量の上限の記述なし** | 文書上は満たす | 文書上は満たす(未確認) | accuracy は有望。R-ACC-13 は書面の確認が要る(この研究が「私人・非営利」に当たるかを含む) | [S1] |
| **C-DCEU** | DigiCert Europe(DigiCert, Inc. の group) | `http://ts.quovadisglobal.com/eu`・`/ch` | DigiCert Europe の発行 CA | ±1 秒(文書) | IP address の登録。契約 | 満たす(DigiCert と GlobalSign は別) | 未確認 | IP の登録が経路 A と両立しない可能性(TSA-F4)。C-DC の公開の局とは別のサービスなので、P1 の accuracy の結果は流用しない | TSA Selection v0 [E2][E3] |
| C-SSL | SSL.com | `https://ts-c2pa.ssl.com`(API key) | 未確認 | 記述なし | 年 2,500 / 10,000、超過は追加 | 満たす | 未確認 | 量が足りない可能性。C2PA の用途 | TSA Selection v0 [E10] |
| C-JP | 日本の認定時刻認証業務(セイコーソリューションズ、アマノ、サイエンスパーク、ウイングアーク 1st など) | 契約の後 | 未確認 | 認定の要件で UTC(NICT) との差 1 秒以内 | 有料の契約 | 満たす | 未確認 | RFC 3161 の endpoint・量・価格が未確認。セイコーは 2024 年に API の提供を発表([S3]) | TSA Selection v0 [E9][E11]、[S3] |
| C-FT | FreeTSA(運営者の法人名の記述なし) | 文書に endpoint の記述なし(証明書と OCSP・CRL はある) | 自前の「FreeTSA CA Primary Root」 | 記述なし | 「abuse しない」以外の条件なし。SLA なし | 運営者が不明確 | 自前の root | 運営者・条件が R-ACC-13 に記録できない見込み。優先しない | [S2] |
| — | Sectigo | — | — | — | 15 秒の間隔 | — | — | NOT SELECTED / CLOSE(変えない) | — |

## 4. 提案(むすびさんに判断していただきたい)

1. **C-CT(Certum)を第 3 候補の第一位**として扱う。T1・T2 を文書上満たし、accuracy の記述が最も強い(100 ms)。
2. C-CT の確認は、次の 2 本で並行する。
   - **書面の確認(R-ACC-13)**: Asseco(Certum)への問い合わせ。1 局あたり受け入れまで最大 5,760 回・通常の運用で年最大約 15,000 回・同じ秒に最大 4 回の要求が、利用条件(と料金)の上で許されるか。この研究の利用が「私人・非営利」に当たるか。問い合わせは純さんの作業(TSA Selection v0 §8)。
   - **token の実物(R-ACC-1〜11)**: 凍結した V0.1 には足さず、**別の probe の仕様**(例: TSA-PROBE-SPEC V0.2 または「第 3 候補の P1 だけの仕様」)を新しく事前に固定して行う。P1 と同じ規則(5 回、20 秒の間隔、§6.1 の機械的な当てはめ)と、必要なら P3 と同じ 48 時間の観測。
3. C-DCEU は、IP の登録の方式(GitHub-hosted runner の IP の範囲を登録できるか、認証の方式の別案があるか)を DigiCert に確認できるまで、第二位で保留。
4. C-JP は、価格と RFC 3161 の endpoint が分かるまで調査を続ける(第三位)。
5. C-FT は優先しない。

## 5. 先に共有しておくべき見込み(TSA-F1)

- P1 では、C-DC・C-GS の両方で、失効の情報の発行の時刻(OCSP の producedAt、CRL の thisUpdate)が token の genTime より前だった。
- 第 3 候補も、大手の CA の OCSP・CRL の運用であれば、同じ傾向になる可能性が高い。C-CT の OCSP(`http://ocsp.certum.pl`)も同じ確認が要る。
- したがって、第 3 候補を探しても、**Part 2 の検査 11 の問題(TSA-F1)は候補を替えるだけでは解けない可能性がある**。この判断は P3 の 48 時間の数字(とくに Fresh_vs_same_token と Fresh_vs_window_attempts)を見てから、むすびさんに回す。ここでは検査 11 を変えない。

## 6. 証拠(2026-10-28 JST に参照)

| # | 文書 | 要点 |
|---|---|---|
| S1 | Certum「Polityka Urzędu Znacznika Czasu」v1.7(2025-02-03、現行)https://certum.pl/pl/wp-content/uploads/2025/01/Polityka-Urzedu-Znacznika-Czasu_v1.7.pdf | 運営者 Asseco Data Systems S.A.、`http://time.certum.pl`、policy OID 1.2.616.1.113527.2.5.1.11、精度 100 ms(高負荷で 200 ms。§5.1 に食い違う記述)、鎖 Certum Timestamp 2025 ← Certum Timestamping 2021 CA ← Certum Trusted Network CA 2、CRL・OCSP の URL、私人・非営利は原則無料。参考: 旧版 v1.1(2002)https://files.certum.eu/documents/repsitory/5-doc-archive/5TSAP/CERTUM-CA-TSA-CP-1.1.pdf |
| S2 | FreeTSA「Certification Practice Statement」https://www.freetsa.org/freetsa_cps.html | 運営者の法人名・accuracy・利用条件の記述なし。自前の root、OCSP・CRL |
| S3 | クラウド Watch(2024-05-16)「セイコーソリューションズ eviDaemon」https://cloud.watch.impress.co.jp/docs/news/1591736.html | API による提供の発表。RFC 3161・精度・料金の記述なし |

## 7. むすびさんに判断してほしいこと

1. §4 の優先の順(C-CT → C-DCEU → C-JP、C-FT は優先しない)。
2. C-CT の token の実物を取るための**新しい probe の仕様**を作ってよいか。その形(V0.2 として C-CT を足すか、第 3 候補だけの別の仕様にするか)。
3. Certum への書面の問い合わせの内容(§4 の 2)。
4. §5 の見込みを、P3 の結果を待って TSA-F1 の判断に回す扱い。
