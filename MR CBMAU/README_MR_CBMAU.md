# MR CBMAU — Banque Centrale de Mauritanie

- **Jira:** DECD-5810 (epic DECD-3438, Regulators 2026 – Internal Crawlers)
- **Source site:** https://www.bcm.mr
- **Language:** French (translate entity fields → English)
- **RegCtry / RegCode:** MR / CBMAU
- **RegulationType:** Regulated

## Lists (from Jira ticket)

| ListNr | ListName | URL | Notes |
|---|---|---|---|
| 1 | Banques agréées par la BCM | https://www.bcm.mr/page/etablissements-agrees/826 | Extract entities from the **image-PDF** under this ListName (OCR) |
| 2 | Établissements de paiement et de monnaie électronique agréés | https://www.bcm.mr/page/etablissements-agrees/826 | Extract entities from the **image-PDF** under this ListName (OCR) |
| 3 | Institutions de Microfinance (IMF) agréées | https://www.bcm.mr/page/etablissements-agrees/826 or https://bo.bcm.mr/sites/default/files/2025-10/imf_bcm_tableau_10.25.pdf | Click "Listes IMF" at bottom to open PDF; extract entities from the "Dénomination" column |

## Status
- [x] v1 scraper built — `MR_CBMAU_v1.py` (2026-07-01)
- [x] List 3 (IMF) validated on Mac — 31 institutions (text PDF, no OCR)
- [ ] Lists 1 & 2 (OCR) — **run on the Windows server** (bundled Tesseract-OCR); not
      executable on the dev Mac (no tesseract binary). Expected results below.

## Implementation notes (v1)
- The public page is a React SPA; content comes from the Drupal JSON:API:
  `https://bo.bcm.mr/fr/jsonapi/node/page?filter[drupal_internal__nid]=826`.
  `field_content.value` HTML holds the two inline images (lists 1–2) and the IMF PDF link
  (list 3). The scraper reads those URLs from the API so filenames can change month to month.
- **List 1 (Banques)** = inline PNG `image_0.png` → OCR with **img2table** `TesseractOCR` +
  `Image(...).extract_tables(borderless_tables=False)` (bordered table → cells extracted
  natively; same pattern as LC FSRALC / GN BCRG). Columns: Nom | Code (BANKxxx) | Short Name.
- **List 2 (Paiement/e-monnaie)** = inline PNG `image_2.png` → same img2table path. Columns:
  Nom | Catégorie. A "Transfert de fonds" separator row (name == category) is skipped.
- **List 3 (IMF)** = `imf_bcm_tableau_10.25.pdf`, a real **text** PDF → pdfplumber; the
  "Dénomination" column is the Name, "Sigle" → InternalID_1, "Catégorie" → Typology.
- OCR needs the bundled `Tesseract-OCR\` on PATH (wired at the repo root); List 3 needs no OCR.

## Expected results for Windows validation (2026-07 snapshot)
- **List 1 — 17 banks:** BNM (BANK002), BAMIS (003), CHB/CHBANK (004), GBM (006), BEA (007),
  BCI (008), ORABANK (009), BMCI (010), SGM (012), ABM (013), BIM (015), BMS (017), BPM (018),
  BFI (021), BMI (024), IBM/International Bank of Mauritanie (025), AUB/Algerian Union Bank (026).
- **List 2 — 11 entities:** GAZA PAY SA, MOOV MONEY MAURITEL SA, CADORIM SA, SALAM PAY SA,
  E-CASH SA, E-LEBNE SA, MAURITANIE PAY SA, E-MONEY (CHINGUITEL), MATTEL MONEY, EL Weva Telecom,
  Tadamoun Telecom. (Categories: Paiement / Monnaie Électronique / Transfert de fonds.)
- **List 3 — 31 IMF institutions** (Catégorie A: 11, B: 19, C: 1). ✔ validated.
- **Total expected: 59 entities** once run on Windows (17 + 11 + 31).
