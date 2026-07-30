# ZW RBZI

## Regulator Information

- **Country/Region Code**: ZW
- **Regulator Code**: RBZI
- **Full Name**: Reserve Bank of Zimbabwe
- **Website**: https://www.rbz.co.zw/
- **Jira**: https://moodysdatapipeline.atlassian.net/browse/DECD-6328

## Script

- **Current Version**: `ZW_RBZI_v1.py`
- **Approach**: the RBZ site is behind a Radware ("perfdrive") bot-management challenge — plain `requests` gets served a captcha page instead of the file, for both the listing pages and the file downloads themselves. The script opens the banking-institutions listing page once with **DrissionPage** (real Chrome) to clear the challenge, harvests the resulting session cookies + User-Agent, then hands those to a `requests.Session` to download all 3 source files directly (PDF, PDF, XLSX).

## List Types

| ListNr | ListName | URL | Comments |
|--------|----------|-----|----------|
| 1 | List of Operating Banking Institutions | https://www.rbz.co.zw/index.php/regulation-supervision/regulation-supervision/banking-institutions | Click on download and extract all entities from the PDF |
| 2 | List of Registered Microfinance Institutions | https://www.rbz.co.zw/index.php/regulation-supervision/regulation-supervision/micro-finance-institutions | Click on download and extract all entities from the PDF |
| 3 | List of Licensed Money Transfer agents and Bureaux de Change | https://www.rbz.co.zw/index.php/regulation-supervision/capital-flows-management/authorised-dealers-with-limited-authority | NEW LIST! Click on "Licenced Institutions for the Year 2026" to open the Excel file and extract all entities |

Direct file URLs (found via the page's "Download" links, not the Jira-listed landing pages):
- List 1: `.../documents/bank_sup/Operating_Banking_Institutes/Consolidated_Website_Information_-_January_2026.pdf`
- List 2: `.../documents/bank_sup/Registered_Microfinance_/LIST_OF_REGISTERED_MICROFINANCE_INSTIUTIIONS_AS_AT_31_MARCH_2026.pdf`
- List 3: `.../documents/Regulations_Acts/2026/ADLA/LICENCED_INSTITUTIONS_FOR_YEAR_2026_1.xlsx`

## Page structure & parsing

### List 1 — Operating Banking Institutions (PDF, 26 institutions)

A "business-card" profile PDF: each institution is a section headed by a 14.0pt name heading, followed by ~11pt label:value lines (`Name`, `Head Office`, `Contact Details`, `Website and Social Media`, `Type of Bank`, `Date of Establishment`, `History`, `Ownership`). Critically, the label and value columns are **not vertically synchronised per rendered line** — e.g. the `Contact Details` label can visually sit next to `Harare`, which is actually the tail of the *previous* field's wrapped address, not a genuine Contact Details value. Fields are therefore extracted from content-anchored index ranges (locate each label's row, treat all text between two consecutive labels as one blob) and pulled out by regex (`Tel:`, `Fax:`, email pattern, `P.O. Box` pattern), not by fixed line-by-line label:value pairing — same approach as `PW_PFIC`.

### List 2 — Registered Microfinance Institutions (PDF, 339 institutions)

A numbered two-column table (`No.` / `Name` / `Head Office Address`) spanning two un-restarted-numbering sections: **CREDIT-ONLY MICROFINANCE INSTITUTIONS** (1–332) then **DEPOSIT TAKING MICROFINANCE INSTITUTIONS** (1–7). `pdfplumber`'s `extract_tables()` silently drops rows that straddle a page break, so rows are reconstructed from raw words instead: numbered tokens in the left margin are treated as row anchors, every other word on the page is assigned to its nearest anchor by vertical distance (handles addresses wrapping both above *and* below their own row), then split into Name/Address columns by an x0 threshold. Section transitions are tracked by the exact vertical position of the section-heading text (not just "does this page contain the heading string"), since the DEPOSIT TAKING heading appears mid-page after several CREDIT-ONLY rows on the transition page. Header/heading text bleeding into the first or last row of a page/section is explicitly excluded.

### List 3 — ADLA Licensed Institutions (XLSX, 72 entities)

A single sheet with no proper header row object: row 7 is the document title, row 8 the column headers (`No.` / `Name of Institution` / `Licence Number`), then 3 un-numbered tier-heading rows each followed by numbered entries — **TIER 1** "Carry-out Inbound and Outbound Remittances as well as local buying and Selling of foreign currency" (1–24), **TIER 2** "Carry-out Inbound Remittances as well as local buying and Selling of foreign currency" (25–48), **TIER 3** "Carry-out local buying and Selling of foreign currency only" (49–72). No address/phone/email/website on this list — Name + Licence Number only.

## Field mapping

| sqldict field | List 1 (Banks) | List 2 (Microfinance) | List 3 (ADLA) |
|---|---|---|---|
| Name | `Name` label value | Name column | Name of Institution column |
| Address_1 | Head Office blob minus phone/fax/email/PO Box/boilerplate | Address column | — |
| Address_2 | `P.O. Box ...` extracted from the blob | — | — |
| City | guessed from a fixed Zimbabwean city list (`Harare`, `Bulawayo`, etc.) found in Address_1 | same guess against Address_1 | — |
| Phone / Fax | `Tel:` / `Fax:` regex matches | — | — |
| Email | email-pattern regex match | — | — |
| Website | `Website and Social Media` value | — | — |
| License_Type | `Type of Bank` value | Section name ("Credit-Only Microfinance Institutions" / "Deposit Taking Microfinance Institutions") | Tier description |
| RegulationDate | `Date of Establishment` value | — | — |
| Name - Mother Company | `Ownership` value, raw (e.g. "AFC Holdings Limited 100%") — not further parsed | — | — |
| InternalID_1 | — | row number within its section | Licence Number |
| Cntry / RegCtry | `ZW` | `ZW` | `ZW` |
| RegulationType | `Regulated` | `Regulated` | `Regulated` |
| ListLabel | `1` — bank-only list | `1` — deposit-taking/lending institutions supervised by RBZ's Bank Supervision division (same `bank_sup` URL path as List 1) | `4` — money transfer agents / bureaux de change, not a bank or insurance list (judgment call, per `PG BPNG` precedent) |
| ListLanguage | `EN` | `EN` | `EN` |
| RegCode / ListCode | RBZI / 1 | RBZI / 2 | RBZI / 3 |
| ListProcessDate | run date (`%Y-%m-%d`) | run date | run date |

## Notes / QA

- **Total 437 rows**: List 1 = 26, List 2 = 339 (332 Credit-Only + 7 Deposit Taking, no gaps in either numbering), List 3 = 72 (24 per tier).
- **9 expected cross-list duplicate names** (case-insensitive), all legitimate dual/triple licensing, not a parsing error:
  - List 1 ↔ List 2 (bank also microfinance-registered): *African Century Limited*, *EmpowerBank Limited*, *Mukuru Financial Services Zimbabwe Limited*.
  - List 1 ↔ List 3 (bank also holds an ADLA money-transfer/FX licence): *AFC Commercial Bank Limited*, *Ecobank Zimbabwe Limited*, *National Building Society*, *NMB Bank Limited*, *Stanbic Bank Zimbabwe Limited*.
  - List 2 ↔ List 3: *African Century Limited*.
  - A few additional List 1 ↔ List 2 near-matches exist under slightly different name strings (e.g. List 1's "INNBUCKS MICROBANK LIMITED" vs List 2's "InnBucks Microbank Limited (formerly Ndoro Microfinance Bank)") — not deduplicated since the strings genuinely differ, left as-is.
- List 1 (banks) has complete Name/Address_1/License_Type coverage for all 26 institutions; Phone/Fax/Email/Website are populated for most but not all rows — several institutions use contact-detail formats (e.g. "Toll free numbers...") not covered by the `Tel:`/`Fax:` regex, so those fields are blank rather than force-parsed. `Name - Mother Company` carries the raw `Ownership` text as-is (e.g. "100% ABCHL") — not split into a clean parent-company name.
- List 2 (microfinance) has complete Name/Address_1 coverage for all 339 rows; City is a best-effort guess against a fixed Zimbabwean city list and will be blank where the address doesn't mention a recognized city.
- List 3 (ADLA) has no address/phone/email/website in the source at all — this is a Name + Licence Number + Tier listing only.
- No encoding red flags detected (`Ã©`, `â€™`, `Â `, `?{3,}` runs — none found).
- No baseline exists yet in `qa_positive_combined/` for this regulator (new folder).
