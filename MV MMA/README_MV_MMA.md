# MV MMA — Maldives Monetary Authority

Scraper for the Maldives' central bank/regulator, **MMA** (mma.gov.mv).

- **Jira:** DECD-6136 (parent epic DECD-3438 — Regulators 2026 Crawlers)
- **RegCtry:** `MV`
- **RegCode:** `MMA` (confirmed on the regulators maintenance site)
- **RegulationType:** `Regulated`
- **Script:** `MV MMA_v_1.ipynb`
- **Output:** `MV MMA SQL Ready <timestamp>.xlsx` (sheet `SQL Ready`), saved in this folder
- **Run:** plain `requests` + `BeautifulSoup` + `pdfplumber` — **no browser needed.** The site
  is an AngularJS SPA, but each `#/` route just loads a **static partial HTML file** that is
  directly fetchable (`partials/...`). There is no JSON API for the registers — the data is
  hardcoded in the partials. `verify=False` for the corporate TLS proxy, and the response
  encoding is **forced to UTF-8** (the server omits the charset header; requests' latin-1
  fallback turns `Malé` into `MalÃ©`).

## Lists (ticket ListNr → source; ticket skips ListNr 2)

| ListNr | `ListName` (ticket) | `ListLabel` | Source partial / file | Count (2026-07-13) |
|---|---|---|---|--:|
| 1 | Register of Banks | 1 | `partials/financialStability/registerofbanks.html` | 9 |
| 3 | Register of Insurance Providers | 2 | `partials/financialStability/insuranceProvidors.html` (site's spelling) | 5 |
| 4 | Register of Insurance Brokers | 2 | date-stamped PDF, link resolved each run | 12 |
| 5 | Register of Licensed Payment Service Providers | 4 | `partials/paymentsinfrastructure/registerofserviceproviders.html` | 8 |

## Parsing decisions

- **HTML comments are stripped before parsing** — the partials keep former entities (e.g. HSBC)
  and stale addresses inside `<!-- -->` blocks.
- Contact blocks mix address lines with `Tel:`/`Fax:`/`Email:` labels (value inline **or on the
  next line**), bare e-mails (some `mailto:` hrefs are malformed — link *text* is used), bare
  website URLs, `ZIP, City` lines and a "Republic of Maldives" line (dropped; `Cntry = MV`).
  Malé / Hulhumalé (any apostrophe variant) → `City`, 5-digit codes → `Zip`.
- **List 1:** name = `h3`; first `<address>` = local branch contact. Foreign branches also have
  a "Details of Head Office" block (`div[ng-show*=viewDetails]`) → `Name - Mother Company`,
  `Address_1 - Mother company`, `Phone - Mother company`, and the last line (country, with
  "Republic of" prefix stripped) → `Cntry - Mother company` (IN/PK/LK/MU seen). UI artifacts
  ("View", "Less Information", "Website:") are filtered out of that block.
- **List 3:** name + website from `h4 > a`.
- **List 4:** the PDF filename is **date-stamped** (`insurance-brokers-03052026.pdf`) — the
  current link is resolved each run from the insurance-sector partial by link text. Parsed with
  `pdfplumber.extract_tables()`: columns No / Name / Principal / Responsible Officer / Contact
  Details / Registered Address. Contact cell split on `Telephone:`/`Fax:`/`Email:` (line-wrapped
  e-mails rejoined). The footer "Updated on 21 April 2026" → `ListValidityDate` (2026-04-21).
  **Principal ("All Local Insurers") and Responsible Officer have no sqldict field** — not
  captured; flag if the ticket owner wants them.
- **List 5:** `Licensed Payment Service` bullet list → `License_Type` (joined with `; `).
  Names keep their "(via Western Union)"-style parentheticals verbatim.
  Dhiraagu Fintech's phone is the short code "123" — as published.

## Last run

- 2026-07-13 (v1): **34** entities. `MV MMA SQL Ready 2026-07-13 10.50.46.xlsx`.
