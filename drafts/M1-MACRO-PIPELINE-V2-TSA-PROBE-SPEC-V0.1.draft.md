# M1-MACRO-PIPELINE-V2 — TSA Pre-Selection Probe Spec(DRAFT v0.1)

- 状態: **DRAFT v0.1**(Claude、2026-10-27)。むすびさんの監査待ち。probe はまだ実行しない。
- v0 からの変更(むすびさんの v0 の監査、2026-10-27 05:32 JST): §6.1 で policy の観測を「policy discovery の証拠」に限定、§6.2 から 0.99 による使える / 使えないの判定を削除して記述的な判定に変更、6 時間の新しさを token ごとに評価する形に変更(主判定)、§9 を更新。v0 は drafts/ にそのまま残す。
- 区分: **PROBE / NON-FORMAL / PRE-SELECTION**。Calibration でも受け入れの試験でもない。
- 上位(Freeze 済み、この記録で変えない): Requirements V0.7 §9.3、Part 2 V0.4 §6、Part 4 V0.2 §5。
- 関連: TSA Selection Record DRAFT v0(commit ec325170、blob e80a87f6。**書き換えない**)。むすびさんの v0 の監査(2026-10-27 04:26 JST)の指示:「V2 repository 作成 → NON-FORMAL TSA probe 仕様を事前記録 → probe 実行 → TSA Selection v0.1」。
- この記録は、probe を**実行する前に**、何を、どこで、何回、どう測り、結果をどう読むかを固定する。結果を見てから測り方・読み方を変えない。

---

## 1. 目的

1. TSA Selection v0 の PENDING のうち、token と PKI の実物で決まるもの(R-ACC-1〜11)を、実際の応答で判定できるようにする。
2. **TSA-F1・TSA-F2** を推測でなく数字で判定する。すなわち、失効の情報(OCSP の producedAt・thisUpdate・nextUpdate、CRL の thisUpdate・nextUpdate)の発行の時刻が、token の genTime と比べてどれだけ新しいかを測る。
3. 経路 A の実行環境(GitHub-hosted runner)から、候補の TSA と OCSP・CRL の取得先に届くことを確かめる。

## 2. 分離の規則(むすびさんの指示のとおり)

- 予測・forecast を作らない。M1 のコード・特徴量・ledger を読まない。
- V1 の repository に書かない。V1 の credential を持たない(Part 3 の F-P3-10 と同じ)。
- Calibration・Acceptance の分母に入れない。probe の token を R として、どの Origin の anchor にも使わない。
- Holdout に触れない(ペアのデータを一切読まない)。
- 測るのは、token・証明書の鎖・OCSP・CRL・時刻の差・到達性だけ。
- probe の結果は TSA Selection Record の証拠にだけ使う。

## 3. 実行の場所

- **V2 repository の probe の専用の workflow**(`.github/workflows/tsa-probe.yml`)。GitHub-hosted runner(ubuntu の固定の image の版を記録する)。
- token の権限: その workflow の `GITHUB_TOKEN` の `contents: write`(V2 repository だけ)。ほかの secret は、無料の局では使わない。
- 有料の局(C-GMO)は、契約の後に認証情報を V2 repository の secret に置く。値はどこにも記録・表示しない。契約の前は probe しない。
- **経路 C(C2)からの到達性**は、この probe では測らない。C2 の provider の選定の後に、同じ手順の別の版で測る(TSA-F4・TSA-F7)。それまで、どの局も「A・C の両方から使える」とはしない。
- 保存先: V2 repository の `probe/tsa/<Probe_Run_ID>/`。`records/`・`ledger*/`・`preregistration/` とは分ける。
- 道具: runner の OpenSSL(版を記録)と、固定の版の Python の script(SHA-256 を記録)。probe の script は V2 の実装の候補の Code_SHA の対象ではない(実装の前の調査の道具)。

## 4. 対象の局(TSA Selection v0 のむすびさんの優先の順)

| 順 | 候補 | endpoint | probe の条件 |
|---|---|---|---|
| 1 | C-GMO | 契約の後に決まる | 契約・購入の後。それまで対象外 |
| 2 | C-DC | `http://timestamp.digicert.com` | すぐに対象にできる |
| 3 | C-GS | `http://timestamp.globalsign.com/tsa/r6advanced1` | すぐに対象にできる |
| — | C-SG・C-SGQ | — | **対象外**(NOT SELECTED / CLOSE) |
| — | その他 | — | この版では対象外 |

## 5. 測り方

### 5.1 共通の要求

- TimeStampReq は Part 2 §6.1 と同じ形: version 1、SHA-256、nonce(OS の乱数の 64 bit の正の整数)、certReq = TRUE。
- reqPolicy は**付けない**(policy の OID はまだ固定していないので、TSA の既定の policy を観測する。選定の後の実装では Part 2 §6.1 のとおり付ける)。
- messageImprint は、`SHA-256("M1-MACRO-PIPELINE-V2 TSA PROBE " + Probe_Run_ID + " " + 局の ID + " " + 連番)`。実在の資料の hash を送らない。
- HTTP の時間切れ 30 秒、失敗したら 3 秒後に 1 回だけ再試行(Part 2 §14 の案と同じ)。それ以上は足さない。
- 要求の直前と応答の直後の runner の時刻(UTC、マイクロ秒)を記録する。
- 応答が HTTP 429・403・503、または TSA の status が rejection のときは、**その局のその run の残りの要求をやめる**。結果を見て要求を足さない。

### 5.2 P1 — token の検査(1 回だけ。手動の起動)

- 各局に 5 回、要求の間を 20 秒以上あけて要求する。
- 保存: tsq・tsr の DER、HTTP の status・header、`openssl ts -reply -text` の出力。
- 記録(token ごと): status(と grantedWithMods なら statusString・failInfo)、policy の OID、accuracy(seconds・millis・micros)、genTime の文字列そのまま、nonce の一致、messageImprint の algorithm と一致、署名の algorithm、ESSCertID / ESSCertIDv2 の有無と値、token の中の証明書の一覧。

### 5.3 P2 — 証明書と鎖(P1 の token から)

- 署名者の証明書の EKU(critical か、timeStamping だけか)、AIA の OCSP の URL と caIssuers の URL、CDP の CRL の URL、発行者、serial、有効期間。
- AIA の caIssuers から中間の証明書を取得し、同じ項目を記録する。root まで組み立て、各証明書の DER と SHA-256 の指紋を保存する。
- root が OS の trust store にあるかを記録する(参考。判定には使わない)。

### 5.4 P3 — 失効の情報の新しさ(48 時間、1 時間ごと)

- 起動: schedule で 1 時間ごと(毎時 41 分 UTC。案)を 48 回。GitHub の schedule の遅れ・欠けはそのまま記録し、**欠けた回を足さない**。
- 1 回の中の手順(局ごと):
  1. token を 1 つ要求する(t_tok_send、t_tok_recv、genTime を記録)。
  2. 応答の直後に、署名者の証明書の OCSP(AIA の URL)と CRL(CDP の URL)を取得する(t_fetch1)。
  3. 中間の証明書の OCSP と CRL も同じく取得する。
  4. **15 分待って**、2・3 をもう一度取得する(t_fetch2)。decision の job が 03:15〜03:18 に失効の情報を集める状況(Part 2 §6.3)に近づけるため。
- 記録(取得ごと): URL、HTTP の status・header(`Cache-Control`・`Age`・`Last-Modified`・`Expires` を含む)、DER と SHA-256、OCSP なら responseStatus・certStatus・producedAt・thisUpdate・nextUpdate・応答者の証明書、CRL なら thisUpdate・nextUpdate・CRL number、対象の証明書が載っているか。
- 1 局あたりの TSA の要求の数: 48 回 × 1 ×(再試行で最大 2)= 最大 96 回。P1 と合わせて最大 106 回。

### 5.5 P4 — 独立の再検証(ネットワークなし)

- P1〜P3 で保存したものだけを使い、別の process でネットワークを切った状態で `openssl ts -verify`(imprint・token・鎖)と、OCSP・CRL の署名の検証をやり直す。結果を記録する。

## 6. 結果の読み方(事前に固定する)

### 6.1 R-ACC-1〜11

- P1・P2・P4 の結果に、Part 2 §6.2 の検査 1〜10 と 12(a) を機械的に当てはめる。
- **policy(R-ACC-8)**: reqPolicy を付けていないので、検査 2 の reqPolicy と検査 5 は行わない。観測した policy の OID は **policy discovery の証拠**としてだけ記録する。「Part 2 の reqPolicy の検査・policy の検査に PASS した」とは扱わない。policy の OID は Selection の時に固定し、実装で Part 2 §6.1・§6.2 のとおり検査する。
- 5 つの token のどれか 1 つでも通らない検査がある局は、その R-ACC を FAIL とする(5 つの中から都合のよいものを選ばない)。
- grantedWithMods は、変更の内容が読めるときだけ受け付ける。読めなければ R-ACC-1 FAIL。

### 6.2 TSA-F1(新しさ)の記述的な結果

- **この probe には合否の閾値を置かない。** Requirements §10.6 の p_min = 0.99 は正式な Calibration の Gate であり、この pre-selection の探索の probe とは母集団・標本の設計・目的が違う。48 回の観測で 0.99 の判定はできない(47/48 ≈ 0.979)。48/48 でも、真の割合が 0.99 以上であることの立証にはならない。0.99 による判定は Calibration まで使わない。
- 発行の時刻 = OCSP は producedAt、CRL は thisUpdate。局ごと、証明書(署名者・中間)ごと、取得先(OCSP・CRL)ごとに、次を出す。

| 指標 | 定義 | 対応する上位の状況 |
|---|---|---|
| **Fresh_vs_same_token(fetch1)** | P3 の各回で、t_fetch1 の取得の発行の時刻 ≥ その回の token の genTime。pass の数 / 対象の数 | 較正(Part 4 §5.3。CAL_POST の数秒後の取得) |
| **Fresh_vs_same_token(fetch2)** | 同じく t_fetch2(約 15 分後)の取得について | 参考 |
| **Fresh_vs_window_attempts** | 各回の t_fetch2 の取得 f について、genTime が [t_fetch2 − 6 時間, t_fetch2) に入る P3 の token の**それぞれ**について個別に「f の発行の時刻 ≥ token の genTime」を評価する。全回を通した pass の数 / 対象の数(対の数)と、f ごとの内訳 | decision(窓の中のすべての attempt の token を、03:15〜03:18 に集めた失効の情報で検査する。Part 2 §6.2 の検査 11 は token ごとに成り立つ必要がある) |
| Max_genTime_window(派生) | 各 f について、f の発行の時刻 ≥ 6 時間の中の genTime の最大値か | 派生の統計。主判定に使わない |
| Lag | 取得の時刻 − 発行の時刻 の分布(最小・中央・最大)。発行の時刻の更新の間隔(階段の幅)、HTTP の cache の header | OCSP・CRL が要求ごとに作られるのか、数時間・日の周期か、CDN の cache があるかを見る |

- **記述的な判定**(局ごと、署名者の証明書、取得先ごと。Fresh_vs_same_token(fetch1) と Fresh_vs_window_attempts のそれぞれについて):
  - 対象のすべてが pass → **NO_STALE_OBSERVED_IN_PROBE**
  - 1 件以上の fail → **STALE_OBSERVED_IN_PROBE**(件数と、その時刻を記録する)
  - 対象が 0(取得の失敗など)→ **NOT_OBSERVED**
- この判定は「使える / 使えない」を意味しない。probe の観測の記述である。
- 中間の証明書の結果は、同じ形で出すが、**TSA-F2 の判断のための資料**としてだけ使う(検査 11 を中間に適用するかは TSA-F2 で決める)。
- 結果は TSA Selection v0.1 に記録し、TSA-F1(Part 2 への Finding の要否)と TSA-F2 の判断を、むすびさんに回す。ここで検査 11 を緩めることはしない。
- 欠けた回(schedule の遅れ・欠け、取得の失敗)は補わない。欠けは対象の数から除くのではなく、NOT_OBSERVED の回として件数を記録する。

### 6.3 TSA-F4(到達性)

- 経路 A からの到達性: P1・P3 で、TSA・OCSP・CRL のそれぞれの要求の成功の割合と RTT の分布を記録する。RTT ≤ 2.0 秒の割合も出す(Requirements §10.6 の RTT_max。参考)。
- 経路 C は §3 のとおり測らない。

## 7. 記録

- probe の実行ごとに `probe/tsa/<Probe_Run_ID>/manifest.json`: Probe_Run_ID、起動の種類(dispatch / schedule)、予定の時刻、開始の時刻、runner の image、OpenSSL の版、script の SHA-256、この仕様の SHA-256、局の一覧、保存した file の SHA-256 の一覧。
- 全回の終わりに、§6 の数を出す集計(純粋な関数。保存したものだけを読む)を行い、その結果と集計の script の SHA-256 を `probe/tsa/SUMMARY-<日付>.json` に置く。
- これらを、TSA Selection v0.1 の証拠として参照する(v0 は書き換えない)。

## 8. この仕様の外のこと

- R-ACC-13 の書面の確認(P5): C-DC・C-GS の provider への問い合わせ、C-GMO の見積もり・契約は、純さんの作業として別に行い、回答の文書を保存する。probe では測らない。
- probe は Calibration の開始ではない。V2 の実装の候補もまだない。

## 9. むすびさんに判断してほしいこと

1. §6.1 の policy discovery の扱いと、§6.2 の記述的な判定(NO_STALE_OBSERVED_IN_PROBE / STALE_OBSERVED_IN_PROBE / NOT_OBSERVED)と Fresh_vs_window_attempts の定義が、v0 の監査の指示と合っているか。
2. 欠けた回を NOT_OBSERVED として数える扱い(§6.2 の末尾)。
3. この版を Freeze Candidate 相当として、V2 repository の作成の後に workflow を置いてよいか。
