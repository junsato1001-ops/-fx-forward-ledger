# DEV-USDJPY-SIMPLE-02 — Freeze Candidate(DRAFT V0.2)

- 状態: **FREEZE CANDIDATE V0.2(Claude、2026-11-01)**。むすびさんの最終確認待ち。**Freeze ではない。**
- V0.1(03c174c3)= CONDITIONAL PASS / 3 ITEMS TO CLOSE(むすびさん、純さん経由 2026-11-01 07:30 JST)。V0・V0.1 は変更せず残す。
- 付属: `drafts/DEV-USDJPY-SIMPLE-02-FREEZE-CANDIDATE-V0.2.freeze.candidate.json`。台帳の行の案は V0 の `…-V0.registry.candidate.csv` のまま(変更なし)。
- V0.1 からの変更は下の 4 点だけ。ほか(継承の関係、継承する文書、実装 2212653b / tree 8ed09862、事故の記述、Registry_Count の手順、workflow の静的な証拠、テストの結果の扱い)は V0.1 のまま。

## 1. F-02-1 = CLOSED / DEFAULT BRANCH CHANGE NOT REQUIRED

- 既定の branch は変えない。Freeze 前の構文の証拠は、静的な parse(blob 2da72acd、PyYAML 6.0.3)、01 の対照(line 26 で ERROR)、回帰の検査(01 FAIL / 02 PASS)で十分とする(むすびさんの判定)。
- Freeze の後、preflight の dispatch の前またはその時に、GitHub が workflow を dispatch の対象として認識しなければ、**その時点で STOP**。実行可能性を迂回しない(手元での実行、同じ Trial_ID での workflow の変更、新しい明示の決定なしの repository の設定の変更はしない)。JSON `execution_protocol.github_dispatchability`。
- V0.1 の「Freeze の時に GitHub の認識を記録する」placeholder は削除した。Freeze 前の観測(name が path のまま)は観測の記録として残す。

## 2. F-02-2 = CLOSED / APPLY BY REFERENCE

- JSON `execution_protocol.preflight_boundary_ruling` に、むすびさんの文言のとおり記録した: scientific/preflight execution semantics are unchanged from 01; therefore the 01 PRE-FLIGHT BOUNDARY RULING (commit ce89162c、blob 1ebe5a5e、SHA-256 406316a6…) is incorporated by reference for 02. This does not amend the inherited SPEC or FREEZE-PREP.

## 3. F-02-3 = OPEN UNTIL FREEZE EXECUTION / BY DESIGN

- 変更なし。Freeze の実行の直前に機械的に測る。予想外なら commit A を作らずに止まる。

## 4. NumPy の wheel の SHA-256 の証拠の強さの訂正

- V0.1 の「The numpy wheel SHA-256 was confirmed by むすび from PyPI」を削除し、次に訂正した(`sha256_verification` と `implementation.runtime.numpy.source`):
  - NumPy wheel SHA-256 remains Claude-declared / carried from the audited runtime-pinning record; independent primary-source PyPI verification by むすび is not established.
- **経緯(事実として記録)**: この値は、2026-10-31 03:37 JST に純さんから中継されたメッセージで Claude に渡された。そのメッセージは「むすびが PyPI の一次情報で直接確認した」と述べていた。Claude はそれをそのまま実装の注記と記録に書いた。むすびさんの監査の記録(2026-11-01)では、その確認は確立していない。Claude は PyPI に届かない。
- **fail-closed の性質**: `pip --require-hashes` は、固定した値と SHA-256 が違う wheel を拒否する。値が誤っていれば install が止まるだけで、別のファイルが入ることはない。

### F-02-4(新しく残る点。むすびさんに決めていただきたい)

- 同じ帰属の記述が、科学にも動作にも影響しない注記として、次に残っている:
  1. 実装の tree 2212653b の `requirements.txt` の 4 行目の comment と `IMPLEMENTATION-NOTES.md` の I-7
  2. 凍結済みの 01 の記録 `preregistration/DEV-USDJPY-SIMPLE-01.freeze.json`(変えられない)
- 案: 02 の Freeze の記録(`evidence_strength_corrections`)が 02 についてこれらの帰属を上書きすることを明記し、tree はそのままにする。tree の注記も直すべきと判断される場合は、新しい実装の commit と差分監査が要る(Freeze の対象の commit が変わる)。

## 5. 状態

- DEV-USDJPY-SIMPLE-01 = FREEZE(履歴)/ ABORT
- DEV-USDJPY-SIMPLE-02 = 実装 DIFFERENTIAL AUDIT PASS / Freeze Candidate V0.2 = DRAFT / NOT FROZEN
- Freeze・preflight・Development・Forward = NOT AUTHORIZED、Holdout = SEALED
