# PW PFIC

## Regulator Information

- **Country/Region Code**: PW
- **Regulator Code**: PFIC
- **Full Name**: Palau Financial Institutions Commission
- **Website**: https://ropfic.org/
- **Jira**: https://moodysdatapipeline.atlassian.net/browse/DECD-6348

## Script

- **Current Version**: `PW_PFIC_v1.py`
- **Approach**: single HTML page behind an nginx-based WAF (plain `requests` returns 403). Rendered with **DrissionPage** (real Chrome, same pattern as `PG BPNG`/`DO SSDO`), then parsed with BeautifulSoup.

## List Types

| ListNr | ListName | URL | Comments |
|--------|----------|-----|----------|
| 1 | Active banks in the Republic of Palau | https://ropfic.org/central-registry/ | Extract only the entities under the subtitle "Active Banks in the Republic of Palau" |

## Page structure & parsing

The "Central Registry" page lists, in document order: an `<h3>` "Active Banks in the Republic of Palau" heading, followed by 5 `<h5>` bank-name headings each with a few `<p>` detail lines (address, `Tel:`/`Fax:`/website, and a `Home Country: ... Date of Charter: ... License Status: ...` line) — then four more `<h3>` sections (Closed Banks, Denied Applications, Withdrawn Applications, Under Review), each holding an HTML `<table>`.

Per the Jira Comments field, **only the 5 active banks under the first `<h3>` are extracted**; the scraper walks siblings from that heading and stops as soon as it hits the next `<h3>`, so the 4 tables (closed/denied/withdrawn/under-review banks) are never touched.

One bank (Palau Investment Bank, Ltd.) has an extra leading note paragraph ("Formerly Palau Construction Bank...") before its address block — the parser identifies each field by regex/content (`P.O. Box` → address, `Tel:` → phone/fax/website, `Home Country:` → charter date) rather than by fixed paragraph position, so it isn't thrown off by the extra note.

## Field mapping

| sqldict field | Source |
|---------------|--------|
| Name | text of each `<h5>` bank name |
| Address_1 | the `P.O. Box ...` paragraph |
| City | `Koror` (present in every address) |
| Zip | trailing 5-digit code in the address (`96940` for all 5) |
| Phone / Fax | parsed from the `Tel: ... Fax: ...` paragraph |
| Website | trailing `www....` token in the same paragraph, when present (2 of 5 banks have none) |
| RegulationDate | `Date of Charter` from the metadata paragraph |
| Cntry | `PW` |
| RegulationType | `Regulated` |
| ListName | `Active banks in the Republic of Palau` |
| ListLabel | `1` — bank-only list |
| ListLanguage | `EN` |
| RegCtry / RegCode / ListCode | PW / PFIC / 1 |
| ListProcessDate | run date (`%Y-%m-%d`) |

## Notes / QA

- **Total 5 entities**, matching the 5 `<h5>` headings under "Active Banks in the Republic of Palau" exactly.
- The page's own "Home Country" field (Palau/Guam/Hawaii per bank) was **not** mapped to `Cntry` — `Cntry` follows project convention of the regulator's own jurisdiction (`PW`), consistent with e.g. `UG IRAUG` where foreign entities still get the regulator's country.
- All 5 rows have complete Address/Phone/Fax; Website is populated for 3/5 (Bank of Guam, Bank of Hawaii, Bank Pacific) and blank for 2/5 (Asia Pacific Commercial Bank, Palau Investment Bank) — genuinely absent on the source page, not a parsing gap.
- No duplicate names; no encoding red flags.
- No baseline exists yet in `qa_positive_combined/` for this regulator (new folder).
