# UG IRAUG

## Regulator Information

- **Country/Region Code**: UG
- **Regulator Code**: IRAUG
- **Full Name**: Insurance Regulatory Authority of Uganda
- **Website**: https://ira.go.ug/
- **Jira**: https://moodysdatapipeline.atlassian.net/browse/DECD-6303

## Script

- **Current Version**: `UG_IRAUG_v1.py`
- **Approach**: 8 published PDF registers, each a direct URL. PDFs are downloaded with `requests` (`verify=False`, desktop User-Agent, `urllib3` warnings disabled) into `tempfolder/`, then parsed with **`pdfplumber`** (pure-python text extraction — every PDF is text-based, no OCR needed).

## List Types

| ListNr | ListName | URL | Comments |
|--------|----------|-----|----------|
| 1 | Licensed Insurance Companies | https://ira.go.ug/wp-content/uploads/2026/01/Licensed-Insurance-Companies.pdf | Life + General + Micro-insurance sections. |
| 2 | Authorised Takaful Insurance Companies | https://ira.go.ug/wp-content/uploads/2026/01/Approved-Takful-Companies.pdf | Single entity. |
| 3 | Authorised Insurance Brokers | https://ira.go.ug/wp-content/uploads/2026/06/AUTHORISED-INSURANCE-BROKERS-2.pdf | Reinsurance brokers + insurance brokers. |
| 4 | Authorised Re-Insurance Companies | https://ira.go.ug/wp-content/uploads/2026/01/Approved-Re-Insurance-Companies.pdf | |
| 5 | Authorised Health Membership Organizations | https://ira.go.ug/wp-content/uploads/2026/01/Approved-HMOs.pdf | Single entity. |
| 6 | Authorised Bancassurance Companies | https://ira.go.ug/wp-content/uploads/2026/01/Bancassurance.pdf | Banks acting as bancassurance agents. |
| 7 | DAP-Authorized Companies | https://ira.go.ug/wp-content/uploads/2025/01/DAP-AUTHORISED.pdf | Un-numbered layout. |
| 8 | List of accredited foreign companies | https://ira.go.ug/wp-content/uploads/2026/07/LIST-OF-ACCREDITED-COMPANIES-2026-As-at-23RD-JUNE-2026-1.pdf | Foreign reinsurers, reinsurance brokers, fraud investigators, regional-treaty reinsurers. |

## PDF structure & parsing modes

All PDFs share the IRA letterhead/footer, a title line, then entity entries. Three layouts are handled:

- **`uganda`** (lists 1-6) — numbered, two-column "business-card" layout. Each page is cropped into a left and a right column at the gutter just left of the right column's `N.` markers, so the two columns never bleed into each other. The **Name** is the text after the `N.` marker; wrapped names (e.g. a trailing `Limited` on the next line) are appended until the name ends with a company suffix (`Ltd`/`Limited`/`Plc`/`MDI`) or an address line begins.
- **`dap`** (list 7) — no `N.` markers; a company name is a line immediately followed by an address line. Two columns, same crop split.
- **`foreign`** (list 8) — numbered, single-column; single-line names (only a bare company-suffix continuation line is appended).

Address / Phone / Email / Website are pulled from each entity's detail block; `City` = `Kampala` when the address contains it (blank for most foreign entities).

## Field mapping

| sqldict field | Source |
|---------------|--------|
| Name | text after the `N.` marker (or the name line in the DAP list) |
| Address_1 | address lines of the entry (contact lines removed) |
| City | `Kampala` when present in the address |
| Phone | `Tel:` value |
| Email | first e-mail address in the entry |
| Website | `Website:` / `Web:` value |
| Cntry | `UG` |
| RegulationType | `Regulated` |
| ListName | exact name per table above |
| ListLabel | `2` — all lists are insurance-sector |
| ListLanguage | `EN` |
| RegCtry / RegCode / ListCode | UG / IRAUG / 1-8 |
| ListProcessDate | run date (`%Y-%m-%d`) |

## Notes / QA

- **Total 213 entities** — List 1: 31, List 2: 1, List 3: 57, List 4: 2, List 5: 1, List 6: 22, List 7: 3, List 8: 96.
- All 8 PDFs are text-extractable; none required OCR. If a future edition is published as a scanned image, that list should be re-run on the Windows production box (Tesseract + poppler) — this Mac has neither installed.
- **ListLabel = 2** for every row (insurance regulator).
- One cross-list duplicate is expected: *Jubilee Life Insurance Company of Uganda* appears on both List 1 (licensed insurer) and List 7 (DAP-authorized) — same entity under two programmes, not a parsing error.
- Fill rates: Address 211/213, Email 204/213, Website 104/213, Phone 116/213, City 115/213. Blanks are genuine — most List 8 foreign reinsurers publish only an e-mail, no phone/website/city.
