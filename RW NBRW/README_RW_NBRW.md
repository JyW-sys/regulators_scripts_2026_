# RW NBRW Regulatory Lists

National Bank of Rwanda (BNR / NBRW) — Jira DECD-6292. The bnr.rw site is a React SPA: each supervision page's "chart of documents" is served by a JSON endpoint (`/fsbs`, `/fsmf`, `/fsins`, `/fspens`, `/fsps`). The scraper resolves each target document **by name** on the endpoint (pdf filenames change with every monthly re-upload, e.g. `...-April_2026_DG6v9R9.pdf`), downloads the pdf with `requests`, and parses it — no Selenium needed.

| RegCtry | RegCode | ListNr | ListLabel | ListName | URL | Comments |
|---------|---------|--------|-----------|----------|-----|----------|
| RW | NBRW | 1 | 1 | List of Licensed Banks | https://www.bnr.rw/banksupervision | "List of Supervised Banks" pdf via `/fsbs`. **Image-based pdf** → OCR (img2table + Tesseract). 11 banks; Category column is a merged cell, filled down. |
| RW | NBRW | 2 | 1 | List of MFIs | https://www.bnr.rw/microfinance | "List of Supervised Deposit-taking Microfinance Institutions" pdf via `/fsmf`. Text pdf → pdfplumber. 70 MFIs; District→City, Province→Address_2, Category→License_Type. |
| RW | NBRW | 4 | 2 | List of Licensed Insurance and Reinsurance Brokers | https://www.bnr.rw/insurances | "List of Licensed Insurance and Reinsurance Brokers" pdf via `/fsins`. Text pdf. 21 brokers; License Number→InternalID_1 ("NA" left empty). |
| RW | NBRW | 5 | 4 | List of Pension service providers | https://www.bnr.rw/pensions | "List of Pension service providers" pdf via `/fspens`. **Image-based pdf** → OCR. 14 rows in 4 sections (Corporate Trustee / Administrators / Investment Managers / Custodians → License_Type); same firm may appear once per role. |
| RW | NBRW | 6 | 4 | List of Payment System institutions | https://www.bnr.rw/paymentsystem | "Licensed Institutions as of ..." pdf via `/fsps` (newest by date wins). Text pdf. 47 PSPs; the ✓ columns (E-Money Issuer / Aggregator / Remittance) → License_Type. |
| RW | NBRW | 7 | 2 | List of Insurance Companies | https://www.bnr.rw/insurances | NEW LIST (2026). "List of Insurance Companies" pdf via `/fsins`. Text pdf. 18 insurers; section (Public/Private/Micro/Captive/HMO/Mutual)→CoType, insurance category→License_Type; Phone/Fax/Website/Email regex-extracted from the free-text details column. |

## Notes

- RegulationType = `Regulated` for all rows (all lists are positive/licensed registers).
- Lists 1 and 5 render every cell as an embedded image (no text layer) → `extract_table_rows_ocr` uses img2table + TesseractOCR per project convention; runs on the Windows production box (`Tesseract-OCR\` at repo root). Parsers identify rows by name, not by the tiny running-number cells, which OCR unreliably.
- Some source typos are kept verbatim (e.g. MMI's e-mail `unfo@mmi.gov.rw`, Old Mutual's `...@oldmutal.rw`).
- List 6 title says "Licensed Institutions as of June 2026 (or most recent year)" — the name match `Licensed Institutions as of` + newest `date_last_modified` keeps it current.
