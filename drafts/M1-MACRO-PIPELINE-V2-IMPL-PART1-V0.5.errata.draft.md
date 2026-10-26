# M1-MACRO-PIPELINE-V2-IMPL-PART1-V0.5 — Erratum E1(DRAFT)

- 状態: **DRAFT**(Claude、2026-10-27)。むすびさんの確認の後、`preregistration/M1-MACRO-PIPELINE-V2-IMPL-PART1-V0.5.errata.md` に同じバイト列で置く(むすびさんの指示 2026-10-27 01:28 JST)。
- 対象: M1-MACRO-PIPELINE-V2-IMPL-PART1-V0.5(preregistration/、SHA-256 c63a092725860a02af8bddffb458c59575bf02c38a8a98f74c148853a960cde5、blob 101f7cd49ec5e2991230faf084deb3e03785290a、Freeze commit cbb9d60936272da81f5b5a87eed4b8138a667fa0)。
- 出どころ: M1-MACRO-PIPELINE-V2 Implementation Spec Part 2 の F-P2-1(drafts/M1-MACRO-PIPELINE-V2-IMPL-PART2-V0.draft.md、blob 69fe4c70…)。むすびさんの判定: ACCEPT / CLOSE WITH ERRATUM(2026-10-27 01:28 JST)。

## E1. Part 1 §8.1 の「CFTC_Source_Year は manifest と PRE の記録に書く」

**該当の文**(Part 1 V0.5、271 行目):

> CFTC_Source_Year は manifest と PRE の記録に書く。decision は manifest の CFTC_Source_Year を §8.1 の規則で計算し直し、一致しなければ PROVENANCE_INVALID とする。

**食い違い**: M1-MACRO-PIPELINE-V2-REQUIREMENTS-V0.7 §10.3 は、PRE の記録の key を `Schema_Version`、`Execution_ID`、`Target_Origin`、`Acquisition_Path_ID`、`Stage`、`Random_Nonce` の 6 つに、この順で固定している。CFTC_Source_Year を PRE の記録に入れる場所はない。

**解釈(規範)**:

1. Requirements を上位の規範とする。この文の「と PRE の記録」の部分は効力を持たない。CFTC_Source_Year は **manifest にだけ**書く。
2. 文の残り(manifest に書くこと、decision が §8.1 の規則で計算し直し、一致しなければ PROVENANCE_INVALID とすること)は、そのまま有効である。
3. PRE の記録は Requirements §10.3 の 6 つの key のままとする。
4. Part 2 以降の仕様と実装は、この解釈を使う。

**変えないもの**:

- Part 1 V0.5 の本文、SHA-256、blob、Freeze commit、registry の行は変えない。Part 1 を再 Freeze しない。
- これは統計の規則でも運用の規則でもない。凍結済みの文書どうしの食い違いを、上位の規範に従って解消する記録である。CFTC_Source_Year の決め方(Part 1 §8.1 の規則)、manifest での anchor、decision での再計算は、どれも変わらない。
